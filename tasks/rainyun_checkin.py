"""雨云签到任务模块

雨云自动签到脚本：
- 使用 API Key 进行认证
- 支持多 API Key（多账号）
- 支持腾讯验证码自动完成（TCaptcha）
- 支持每天固定时间（默认 08:30）自动签到
- 项目启动时也会执行一次签到
"""

from __future__ import annotations

import base64
import hashlib
import io
import logging
import time
from dataclasses import dataclass
from typing import Any

import aiohttp

from src.config import AppConfig, get_config, is_in_quiet_hours, parse_checkin_time
from src.job_registry import register_task
from src.push_channel.manager import UnifiedPushManager, build_push_manager

logger = logging.getLogger(__name__)

# 雨云 API 配置
RAINYUN_API_BASE = "https://api.v2.rainyun.com"
CAPTCHA_BASE_URL = "https://turing.captcha.qcloud.com"
CAPTCHA_AID = "2039519451"


@dataclass
class RainyunCheckinConfig:
    """雨云签到配置（可表示单账号或用于多账号时的公共字段）"""

    enable: bool
    api_key: str  # 单账号 API Key（多账号时为第一个）
    time: str
    api_keys: list[str]  # 多 API Key 列表，执行时优先遍历此列表
    push_channels: list[str]

    @classmethod
    def from_app_config(cls, config: AppConfig) -> RainyunCheckinConfig:
        push_channels: list[str] = getattr(config, "rainyun_push_channels", None) or []
        # 多 API Key 优先：rainyun_api_keys 非空时使用，否则用单 API Key 组一条
        if getattr(config, "rainyun_api_keys", None):
            api_keys = [k.strip() for k in config.rainyun_api_keys if k and k.strip()]
        else:
            single_key = (config.rainyun_api_key or "").strip()
            api_keys = [single_key] if single_key else []
        first_key = api_keys[0] if api_keys else ""
        return cls(
            enable=config.rainyun_enable,
            api_key=first_key,
            time=config.rainyun_time.strip() or "08:30",
            api_keys=api_keys,
            push_channels=push_channels,
        )

    def validate(self) -> bool:
        """校验配置是否完整"""
        if not self.enable:
            logger.debug("雨云签到未启用，跳过执行")
            return False

        if not self.api_keys:
            logger.error(
                "雨云签到配置不完整，已跳过执行，缺少字段: rainyun.api_key 或 rainyun.api_keys"
            )
            return False

        valid_keys = [k for k in self.api_keys if k]
        if not valid_keys:
            logger.error("雨云签到配置不完整，已跳过执行，至少需要一个有效的 API Key")
            return False

        return True

    def with_api_key(self, api_key: str) -> RainyunCheckinConfig:
        """返回仅替换 API Key 的副本，用于单账号签到与推送"""
        return RainyunCheckinConfig(
            enable=self.enable,
            api_key=api_key,
            time=self.time,
            api_keys=self.api_keys,
            push_channels=self.push_channels,
        )


def _mask_api_key(api_key: str) -> str:
    """对 API Key 做部分脱敏，用于日志输出"""
    if len(api_key) <= 8:
        return api_key[:2] + "***" if api_key else "***"
    return api_key[:4] + "***" + api_key[-4:]


def _get_common_headers(api_key: str) -> dict[str, str]:
    """获取公共请求头"""
    return {
        "accept": "application/json, text/plain, */*",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
        "cache-control": "no-cache",
        "pragma": "no-cache",
        "sec-ch-ua": '"Not;A=Brand";v="99", "Microsoft Edge";v="139", "Chromium";v="139"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "referer": "https://app.rainyun.com/",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0"
        ),
        "x-api-key": api_key,
    }


async def _get_checkin_status(
    session: aiohttp.ClientSession, headers: dict[str, str]
) -> dict[str, Any]:
    """获取签到状态"""
    try:
        async with session.get(
            f"{RAINYUN_API_BASE}/user/reward/tasks",
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                tasks = data.get("data", [])
                for task in tasks:
                    if task.get("Name") == "每日签到" and task.get("Status") == 2:
                        return {"checked_in": True, "data": data}
                return {"checked_in": False, "data": data}
            else:
                return {"error": f"获取签到状态失败，HTTP 状态码：{resp.status}"}
    except Exception as exc:
        return {"error": f"获取签到状态失败：{exc}"}


async def _get_captcha_data(
    session: aiohttp.ClientSession, headers: dict[str, str]
) -> dict[str, Any] | None:
    """获取验证码数据"""
    params = {
        "aid": CAPTCHA_AID,
        "protocol": "https",
        "accver": "1",
        "showtype": "popup",
        "ua": base64.b64encode(headers["user-agent"].encode()).decode(),
        "noheader": "1",
        "fb": "1",
        "aged": "0",
        "enableAged": "0",
        "enableDarkMode": "0",
        "grayscale": "1",
        "clientype": "2",
        "cap_cd": "",
        "uid": "",
        "lang": "zh-cn",
        "entry_url": "https://turing.captcha.gtimg.com/1/template/drag_ele.html",
        "elder_captcha": "0",
        "js": "/tcaptcha-frame.97a921e6.js",
        "login_appid": "",
        "wb": "1",
        "subsid": "9",
        "callback": "",
        "sess": "",
    }

    try:
        async with session.get(
            f"{CAPTCHA_BASE_URL}/cap_union_prehandle",
            params=params,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            text = await resp.text()
            # 移除括号并解析 JSON
            json_str = text.strip()
            if json_str.startswith("(") and json_str.endswith(")"):
                json_str = json_str[1:-1]
            import json

            return json.loads(json_str)
    except Exception as exc:
        logger.error("雨云签到：获取验证码数据失败：%s", exc)
        return None


async def _refresh_captcha_data(
    session: aiohttp.ClientSession, headers: dict[str, str], old_data: dict[str, Any]
) -> dict[str, Any] | None:
    """刷新验证码数据"""
    try:
        async with session.post(
            f"{CAPTCHA_BASE_URL}/cap_union_new_getsig",
            data={"sess": old_data.get("sess")},
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            data = await resp.json()
            if int(data.get("ret", -1)) == 0:
                old_data["data"]["dyn_show_info"] = data["data"]
                old_data["sess"] = data["sess"]
                return old_data
            return None
    except Exception as exc:
        logger.error("雨云签到：刷新验证码数据失败：%s", exc)
        return None


async def _get_captcha_images(
    session: aiohttp.ClientSession, headers: dict[str, str], data: dict[str, Any]
) -> tuple[bytes | None, bytes | None]:
    """获取验证码图片"""
    try:
        dyn_show_info = data.get("data", {}).get("dyn_show_info", {})
        bg_url = CAPTCHA_BASE_URL + dyn_show_info.get("bg_elem_cfg", {}).get("img_url", "")
        sprite_url = CAPTCHA_BASE_URL + dyn_show_info.get("sprite_url", "")

        bg_img = None
        sprite_img = None

        async with session.get(
            bg_url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)
        ) as resp:
            if resp.status == 200:
                bg_img = await resp.read()

        async with session.get(
            sprite_url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)
        ) as resp:
            if resp.status == 200:
                sprite_img = await resp.read()

        return bg_img, sprite_img
    except Exception as exc:
        logger.error("雨云签到：获取验证码图片失败：%s", exc)
        return None, None


def _find_md5_collision(target_md5: str, prefix: str) -> tuple[str, int]:
    """找到匹配的 MD5 碰撞（用于 PoW 验证）"""
    start_time = time.time()
    num = 0

    while num < 114514 * 1000:  # 设置上限避免无限循环
        current_str = prefix + str(num)
        md5_hash = hashlib.md5(current_str.encode("utf-8")).hexdigest()

        if md5_hash == target_md5:
            elapsed_ms = int((time.time() - start_time) * 1000)
            return current_str, elapsed_ms

        num += 1

    return prefix, int((time.time() - start_time) * 1000)


def _find_part_positions_simple(bg_img_bytes: bytes, sprite_img_bytes: bytes) -> list[list[int]]:
    """
    简单的图像模板匹配方法。
    使用 PIL 进行基础的模板匹配，找到需要点击的位置。
    """
    try:
        from PIL import Image

        # 打开图片
        bg_img = Image.open(io.BytesIO(bg_img_bytes)).convert("RGBA")
        sprite_img = Image.open(io.BytesIO(sprite_img_bytes)).convert("RGBA")

        # 背景图通常是 340x195 的九宫格
        # Sprite 图包含需要点击的图形

        # 获取背景图尺寸
        bg_width, bg_height = bg_img.size

        # 假设是 3x3 九宫格，每个格子的尺寸
        cell_width = bg_width // 3
        cell_height = bg_height // 3

        # 获取 sprite 图尺寸并提取第一个图形
        sprite_width, sprite_height = sprite_img.size

        # 需要找到的图形数量（通常是 3 个）
        # 这里我们使用简化的逻辑：直接基于 sprite 图尺寸估算

        positions = []

        # 简化方法：遍历九宫格，使用像素相似度匹配
        # 这是一个简化版本，实际可能需要更复杂的图像匹配

        # 提取 sprite 中的目标图形（假设在特定位置）
        # 通常 sprite 图的排列是：第一行是待选图形，第二行是背景中的位置

        # 基于简单的像素采样进行匹配
        target_regions = []

        # 假设 sprite 图包含 3 个需要找的图形，排列在顶部
        sprite_cell_width = sprite_width // 3 if sprite_width >= 90 else sprite_width
        for i in range(min(3, sprite_width // 30)):
            x_start = i * sprite_cell_width
            region = sprite_img.crop(
                (x_start, 0, min(x_start + sprite_cell_width, sprite_width), sprite_height // 2)
            )
            target_regions.append(region)

        # 遍历背景图的九宫格
        best_matches = []
        for row in range(3):
            for col in range(3):
                cell_x = col * cell_width
                cell_y = row * cell_height
                cell = bg_img.crop((cell_x, cell_y, cell_x + cell_width, cell_y + cell_height))

                # 计算与每个目标图形的相似度
                for target_idx, target in enumerate(target_regions):
                    similarity = _calculate_similarity(cell, target)
                    best_matches.append(
                        {
                            "row": row,
                            "col": col,
                            "x": cell_x + cell_width // 2,
                            "y": cell_y + cell_height // 2,
                            "target_idx": target_idx,
                            "similarity": similarity,
                        }
                    )

        # 按相似度排序，选择最佳匹配
        best_matches.sort(key=lambda m: m["similarity"], reverse=True)

        # 选择前 3 个不同位置的匹配
        selected = []
        used_positions = set()
        used_targets = set()

        for match in best_matches:
            pos_key = (match["row"], match["col"])
            if pos_key not in used_positions and match["target_idx"] not in used_targets:
                selected.append(match)
                used_positions.add(pos_key)
                used_targets.add(match["target_idx"])
                if len(selected) >= 3:
                    break

        # 按目标索引排序并返回坐标
        selected.sort(key=lambda m: m["target_idx"])
        positions = [[m["x"], m["y"]] for m in selected]

        if not positions:
            # 如果匹配失败，返回默认位置（中心点的九宫格）
            positions = [
                [cell_width // 2, cell_height // 2],
                [cell_width + cell_width // 2, cell_height // 2],
                [2 * cell_width + cell_width // 2, cell_height // 2],
            ]

        return positions

    except ImportError:
        logger.warning("雨云签到：PIL 未安装，使用默认位置")
        # 返回默认位置
        return [[57, 33], [170, 98], [283, 163]]
    except Exception as exc:
        logger.error("雨云签到：图像匹配失败：%s", exc)
        # 返回默认位置
        return [[57, 33], [170, 98], [283, 163]]


def _calculate_similarity(img1, img2) -> float:
    """计算两个图像的简单相似度"""
    try:
        from PIL import Image

        # 调整大小以便比较
        size = (30, 30)
        img1_resized = img1.resize(size, Image.Resampling.LANCZOS)
        img2_resized = img2.resize(size, Image.Resampling.LANCZOS)

        # 转换为灰度
        img1_gray = img1_resized.convert("L")
        img2_gray = img2_resized.convert("L")

        # 计算像素差异
        pixels1 = list(img1_gray.getdata())
        pixels2 = list(img2_gray.getdata())

        if len(pixels1) != len(pixels2):
            return 0.0

        diff_sum = sum(abs(p1 - p2) for p1, p2 in zip(pixels1, pixels2))
        max_diff = 255 * len(pixels1)

        similarity = 1.0 - (diff_sum / max_diff)
        return similarity

    except Exception:
        return 0.0


def _build_verify_form(
    data: dict[str, Any], positions: list[list[int]], old_verify: dict | None = None
) -> dict[str, str]:
    """构建验证表单数据"""
    import json

    # 简化版本：不使用 py_mini_racer，直接构造基本数据
    if old_verify is None:
        comm_captcha_cfg = data.get("data", {}).get("comm_captcha_cfg", {})
        pow_cfg = comm_captcha_cfg.get("pow_cfg", {})
        pow_answer, pow_calc_time = _find_md5_collision(
            pow_cfg.get("md5", ""),
            pow_cfg.get("prefix", ""),
        )
        # 简化的 collect 和 eks
        collect = "1"
        eks = ""
    else:
        collect = old_verify.get("collect", "1")
        eks = old_verify.get("eks", "")
        pow_answer = old_verify.get("pow_answer", "")
        pow_calc_time = old_verify.get("pow_calc_time", 0)

    # 构建答案
    ans = []
    for i, coord in enumerate(positions, start=1):
        if len(coord) == 2:
            x, y = coord
            ans.append({"elem_id": i, "type": "DynAnswerType_POS", "data": f"{x},{y}"})

    return {
        "collect": collect,
        "tlg": str(len(collect)),
        "eks": eks,
        "sess": data.get("sess", ""),
        "ans": json.dumps(ans),
        "pow_answer": pow_answer,
        "pow_calc_time": str(pow_calc_time),
    }


async def _complete_captcha(
    session: aiohttp.ClientSession, headers: dict[str, str], retry: int = 10
) -> dict[str, Any]:
    """完成验证码验证"""
    import json

    captcha_data = await _get_captcha_data(session, headers)
    if not captcha_data:
        return {"error": "获取验证码数据失败"}

    bg_img, sprite_img = await _get_captcha_images(session, headers, captcha_data)
    if not bg_img or not sprite_img:
        return {"error": "获取验证码图片失败"}

    form_data_cache: dict | None = None

    for i in range(retry):
        positions = _find_part_positions_simple(bg_img, sprite_img)
        form_data = _build_verify_form(captcha_data, positions, form_data_cache)

        try:
            async with session.post(
                f"{CAPTCHA_BASE_URL}/cap_union_new_verify",
                data=form_data,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                result = await resp.json()

                if int(result.get("errorCode", -1)) == 0:
                    return result

                # 验证失败，刷新验证码重试
                if i < retry - 1:
                    captcha_data["sess"] = result.get("sess", captcha_data.get("sess"))
                    captcha_data = await _refresh_captcha_data(session, headers, captcha_data)
                    if captcha_data:
                        bg_img, sprite_img = await _get_captcha_images(
                            session, headers, captcha_data
                        )
                        form_data_cache = {
                            "collect": form_data["collect"],
                            "eks": form_data["eks"],
                            "pow_answer": form_data["pow_answer"],
                            "pow_calc_time": form_data["pow_calc_time"],
                        }
                    else:
                        return {"error": "刷新验证码数据失败"}
                else:
                    return {"error": f"超出重试次数。最后认证结果: {json.dumps(result)}"}

        except Exception as exc:
            logger.error("雨云签到：验证码验证请求失败：%s", exc)
            if i >= retry - 1:
                return {"error": f"验证码验证请求失败: {exc}"}

    return {"error": "超出重试次数"}


async def _do_checkin(
    session: aiohttp.ClientSession,
    headers: dict[str, str],
    verify_result: dict[str, Any],
) -> dict[str, Any]:
    """执行签到"""
    data = {
        "task_name": "每日签到",
        "verifyCode": "",
        "vticket": verify_result.get("ticket"),
        "vrandstr": verify_result.get("randstr"),
    }

    try:
        async with session.post(
            f"{RAINYUN_API_BASE}/user/reward/tasks",
            headers=headers,
            json=data,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            return await resp.json()
    except Exception as exc:
        return {"error": f"签到请求失败：{exc}"}


async def _get_user_info(
    session: aiohttp.ClientSession, headers: dict[str, str]
) -> dict[str, Any] | None:
    """获取用户信息"""
    try:
        async with session.get(
            f"{RAINYUN_API_BASE}/user/",
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            if resp.status == 200:
                return await resp.json()
            return None
    except Exception as exc:
        logger.error("雨云签到：获取用户信息失败：%s", exc)
        return None


async def _checkin_single_account(
    session: aiohttp.ClientSession,
    push_manager: UnifiedPushManager | None,
    cfg: RainyunCheckinConfig,
    api_key: str,
    idx: int,
    total: int,
) -> bool:
    """执行单个 API Key 的签到流程，返回是否成功"""
    cfg_one = cfg.with_api_key(api_key)
    headers = _get_common_headers(api_key)
    masked_key = _mask_api_key(api_key)

    logger.debug("雨云签到：正在处理第 %d/%d 个 API Key (%s)", idx, total, masked_key)

    try:
        # 检查签到状态
        status = await _get_checkin_status(session, headers)

        if status.get("error"):
            logger.error("雨云签到：%s（API Key: %s）", status["error"], masked_key)
            await _send_checkin_push(
                push_manager,
                title="雨云签到失败",
                msg=status["error"],
                success=False,
                cfg=cfg_one,
            )
            return False

        if status.get("checked_in"):
            logger.info("雨云签到：ℹ️ 今日已签到（API Key: %s）", masked_key)
            await _send_checkin_push(
                push_manager,
                title="雨云签到提示",
                msg="今日已签到，无需重复签到",
                success=True,
                cfg=cfg_one,
            )
            return True

        # 完成验证码
        logger.info("雨云签到：正在完成验证码...（API Key: %s）", masked_key)
        verify_result = await _complete_captcha(session, headers)

        if verify_result.get("error"):
            logger.error(
                "雨云签到：验证码完成失败：%s（API Key: %s）", verify_result["error"], masked_key
            )
            await _send_checkin_push(
                push_manager,
                title="雨云签到失败",
                msg=f"验证码完成失败：{verify_result['error']}",
                success=False,
                cfg=cfg_one,
            )
            return False

        # 执行签到
        logger.info("雨云签到：正在提交签到请求...（API Key: %s）", masked_key)
        checkin_result = await _do_checkin(session, headers, verify_result)

        if checkin_result.get("error"):
            logger.error(
                "雨云签到：❌ 签到失败：%s（API Key: %s）", checkin_result["error"], masked_key
            )
            await _send_checkin_push(
                push_manager,
                title="雨云签到失败",
                msg=checkin_result["error"],
                success=False,
                cfg=cfg_one,
            )
            return False

        # 检查签到结果
        code = checkin_result.get("code")
        message = checkin_result.get("message", "")
        data = checkin_result.get("data", {})

        if code == 200:
            reward = data.get("Reward", 0) if isinstance(data, dict) else 0
            logger.info("雨云签到：✅ 签到成功！获得 %s 积分（API Key: %s）", reward, masked_key)

            # 获取用户信息
            user_info = await _get_user_info(session, headers)
            user_info_text = ""
            if user_info and user_info.get("code") == 200:
                user_data = user_info.get("data", {})
                points = user_data.get("Points", 0)
                name = user_data.get("Name", "")
                user_info_text = f"\n📊 当前积分：{points}"
                if name:
                    user_info_text = f"\n👤 用户：{name}" + user_info_text

            await _send_checkin_push(
                push_manager,
                title="雨云签到成功",
                msg=f"签到成功！获得 {reward} 积分{user_info_text}",
                success=True,
                cfg=cfg_one,
            )
            return True
        else:
            logger.error("雨云签到：❌ 签到失败：%s（API Key: %s）", message, masked_key)
            await _send_checkin_push(
                push_manager,
                title="雨云签到失败",
                msg=message or "未知错误",
                success=False,
                cfg=cfg_one,
            )
            return False

    except Exception as exc:
        logger.error(
            "雨云签到：签到过程中发生错误：%s（API Key: %s）", exc, masked_key, exc_info=True
        )
        await _send_checkin_push(
            push_manager,
            title="雨云签到失败",
            msg=f"签到过程中发生错误：{exc}",
            success=False,
            cfg=cfg_one,
        )
        return False


async def run_rainyun_checkin_once() -> None:
    """执行一次完整的雨云签到流程（支持多 API Key）"""
    app_config = get_config(reload=True)

    if not app_config.rainyun_enable:
        logger.debug("雨云签到未启用，跳过执行")
        return

    cfg = RainyunCheckinConfig.from_app_config(app_config)

    if not cfg.validate():
        return

    valid_keys = [k for k in cfg.api_keys if k]
    logger.info("雨云签到：开始执行签到任务（共 %d 个 API Key）", len(valid_keys))

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
        push_manager: UnifiedPushManager | None = await build_push_manager(
            app_config.push_channel_list,
            session,
            logger,
            init_fail_prefix="雨云签到：",
            channel_names=cfg.push_channels if cfg.push_channels else None,
        )
        if push_manager is None:
            logger.warning("雨云签到：未配置任何推送通道，将仅在日志中记录结果")

        success_count = 0
        for idx, api_key in enumerate(valid_keys, start=1):
            ok = await _checkin_single_account(
                session, push_manager, cfg, api_key, idx, len(valid_keys)
            )
            if ok:
                success_count += 1

        if push_manager is not None:
            await push_manager.close()

    logger.info("雨云签到：任务执行完成（成功 %d/%d 个 API Key）", success_count, len(valid_keys))


async def _send_checkin_push(
    push_manager: UnifiedPushManager | None,
    title: str,
    msg: str,
    success: bool,
    cfg: RainyunCheckinConfig,
) -> None:
    """发送签到结果推送"""
    if push_manager is None:
        return

    # 免打扰时段内只记录日志，不推送
    app_cfg = get_config()
    if is_in_quiet_hours(app_cfg):
        logger.debug("雨云签到：免打扰时段，不发送推送")
        return

    masked_api_key = _mask_api_key(cfg.api_key)
    status_emoji = "✅" if success else "❌"
    description = f"{status_emoji} API Key：{masked_api_key}\n{msg}"

    try:
        await push_manager.send_news(
            title=title,
            description=description,
            to_url="https://app.rainyun.com/",
            picurl="https://cn.bing.com/th?id=OHR.DubrovnikHarbor_ZH-CN8590217905_1920x1080.jpg",
            btntxt="查看账户",
        )
    except Exception as exc:
        logger.error("雨云签到：发送签到结果推送失败：%s", exc, exc_info=True)


def _get_rainyun_trigger_kwargs(config: AppConfig) -> dict:
    """供注册表与配置热重载使用"""
    hour, minute = parse_checkin_time(config.rainyun_time)
    return {"minute": minute, "hour": hour}


register_task("rainyun_checkin", run_rainyun_checkin_once, _get_rainyun_trigger_kwargs)
