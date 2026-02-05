"""微博超话每日签到任务模块

微博超话自动签到：
- 使用配置文件中的 Cookie（须包含 XSRF-TOKEN）作为参数
- 支持每天固定时间（默认 23:45）自动签到
- 支持多账户批量签到
- 项目启动时若启用也会执行一次签到
- 接入项目统一推送模板
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import re
import time
from collections.abc import Callable
from dataclasses import dataclass

import requests

from src.config import AppConfig, get_config, is_in_quiet_hours, parse_checkin_time
from src.job_registry import register_task
from src.push_channel.manager import UnifiedPushManager, build_push_manager
from src.utils import mask_cookie_for_log

logger = logging.getLogger(__name__)

# 微博超话 API 常量
CHAOHUA_LIST_URL = "https://weibo.com/ajax/profile/topicContent"
CHAOHUA_SIGN_URL = "https://weibo.com/p/aj/general/button"


@dataclass
class WeiboChaohuaCheckinConfig:
    """微博超话签到相关配置（支持多 Cookie）"""

    enable: bool
    cookie: str  # 单条 Cookie，兼容旧配置
    cookies: list[str]  # 多 Cookie 列表，非空时优先使用
    time: str
    push_channels: list[str]  # 推送通道名称列表，为空时使用全部通道

    @classmethod
    def from_app_config(cls, config: AppConfig) -> WeiboChaohuaCheckinConfig:
        cookies: list[str] = getattr(config, "weibo_chaohua_cookies", None) or []
        single = (config.weibo_chaohua_cookie or "").strip()
        if not cookies and single:
            cookies = [single]
        push_channels: list[str] = getattr(config, "weibo_chaohua_push_channels", None) or []
        return cls(
            enable=config.weibo_chaohua_enable,
            cookie=single,
            cookies=cookies,
            time=(config.weibo_chaohua_time or "23:45").strip() or "23:45",
            push_channels=push_channels,
        )

    def validate(self) -> bool:
        """校验配置是否完整"""
        if not self.enable:
            logger.debug("微博超话签到未启用，跳过执行")
            return False

        effective = self.cookies if self.cookies else ([self.cookie] if self.cookie else [])
        if not effective or not any(c.strip() for c in effective):
            logger.error(
                "微博超话签到配置不完整，已跳过执行，缺少字段: weibo_chaohua.cookie 或 weibo_chaohua.cookies"
            )
            return False

        for c in effective:
            if not c.strip():
                continue
            if "XSRF-TOKEN" not in c:
                logger.warning("微博超话 Cookie 中未找到 XSRF-TOKEN，该条签到可能失败")

        return True


def _clean_cookie(cookie: str) -> str:
    """清理Cookie，处理编码问题"""
    try:
        # 移除可能的换行符和多余空格
        cookie = cookie.strip().replace("\n", "").replace("\r", "")

        # 确保Cookie是字符串格式
        if isinstance(cookie, bytes):
            cookie = cookie.decode("utf-8", errors="ignore")

        # 移除可能的非ASCII字符
        cookie = "".join(char for char in cookie if ord(char) < 128)

        return cookie
    except Exception as e:
        logger.warning(f"Cookie处理失败: {str(e)}")
        return cookie


def _get_xsrf_token(cookie: str) -> str | None:
    """从Cookie中提取XSRF-TOKEN"""
    try:
        match = re.search(r"XSRF-TOKEN=([^;]+)", cookie)
        if match:
            return match.group(1)
    except Exception:
        pass
    return None


def _get_user_info(cookie: str) -> str:
    """获取用户基本信息"""
    try:
        # 从Cookie中提取用户名或ID
        sub_match = re.search(r"SUB=([^;]+)", cookie)
        if sub_match:
            return f"用户{sub_match.group(1)[:8]}..."
    except Exception:
        pass
    return "未知用户"


def _run_weibo_chaohua_sign_sync(
    cookie: str,
    on_first_failure: Callable[[str, str], None] | None = None,
) -> tuple[bool, str, int, int, int, int]:
    """
    在同步上下文中执行微博超话签到（供 asyncio.to_thread 调用）。

    Args:
        cookie: 微博 Cookie 字符串。
        on_first_failure: 当第一个超话签到失败时调用的回调 (chaohua_name, msg)，用于立即推送异常提醒。

    Returns:
        (success, user_info_or_error, success_count, already_signed_count, fail_count, total)
        - 执行失败时: (False, error_message, 0, 0, 0, 0)
        - 签到完成: (True, user_info, success, already_signed, fail, total)
    """
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Referer": "https://weibo.com/",
            "X-Requested-With": "XMLHttpRequest",
        }
    )

    # 处理Cookie
    cookie = _clean_cookie(cookie)
    session.headers["Cookie"] = cookie

    xsrf_token = _get_xsrf_token(cookie)
    if xsrf_token:
        session.headers["X-XSRF-TOKEN"] = xsrf_token

    user_info = _get_user_info(cookie)

    def _fetch_chaohua_list(page: int = 1, collected: list | None = None) -> list[dict]:
        """获取超话列表"""
        if collected is None:
            collected = []

        params = {"tabid": "231093_-_chaohua", "page": page}

        try:
            response = session.get(CHAOHUA_LIST_URL, params=params, timeout=15)

            if response.status_code != 200:
                raise Exception(f"HTTP Error: {response.status_code}")

            if not response.text:
                raise Exception("响应内容为空")

            try:
                data = response.json()
            except json.JSONDecodeError as e:
                raise Exception(f"JSON解析失败: {str(e)}")

            if data.get("ok") != 1:
                error_msg = data.get("msg", "未知错误")
                if "login" in error_msg.lower() or "cookie" in error_msg.lower():
                    raise Exception(f"登录状态失效，请更新Cookie: {error_msg}")
                raise Exception(f"API返回错误: {error_msg}")

            api_data = data.get("data", {})
            chaohua_list = api_data.get("list", [])

            if not chaohua_list:
                return collected

            # 提取超话ID和名称
            for item in chaohua_list:
                oid = item.get("oid", "")
                if oid.startswith("1022:"):
                    chaohua_id = oid[5:]  # 去掉前缀 "1022:"
                    chaohua_name = item.get("topic_name", "")
                    if chaohua_id and chaohua_name:
                        collected.append({"id": chaohua_id, "name": chaohua_name})

            # 检查是否还有下一页
            max_page = api_data.get("max_page", 1)
            if page < max_page:
                time.sleep(0.8)  # 增加延迟
                return _fetch_chaohua_list(page + 1, collected)

            return collected

        except requests.exceptions.RequestException as e:
            raise Exception(f"网络请求失败: {str(e)}")
        except Exception as e:
            raise Exception(f"获取超话列表失败: {str(e)}")

    def _sign_chaohua(chaohua_id: str, chaohua_name: str) -> dict:
        """签到单个超话"""
        params = {
            "api": "http://i.huati.weibo.com/aj/super/checkin",
            "id": chaohua_id,
            "location": "page_100808_super_index",
            "__rnd": int(time.time() * 1000),
        }

        try:
            headers = {
                "Referer": f"https://weibo.com/p/{chaohua_id}/super_index",
            }

            response = session.get(CHAOHUA_SIGN_URL, params=params, headers=headers, timeout=15)

            if response.status_code != 200:
                return {"success": False, "msg": f"HTTP错误: {response.status_code}"}

            try:
                data = response.json()
            except json.JSONDecodeError:
                return {"success": False, "msg": "响应格式错误"}

            code = str(data.get("code", ""))
            msg = data.get("msg", "未知错误")

            # 成功的状态码: 100000(签到成功), 382004(今日已签到), 382010(其他成功状态)
            success_codes = ["100000", "382004", "382010"]
            is_success = code in success_codes

            return {
                "success": is_success,
                "code": code,
                "msg": msg,
                "already_signed": code == "382004",
            }

        except requests.exceptions.RequestException as e:
            return {"success": False, "msg": f"网络请求失败: {str(e)}"}
        except Exception as e:
            return {"success": False, "msg": f"签到失败: {str(e)}"}

    # 获取超话列表
    try:
        chaohua_list = _fetch_chaohua_list()
    except Exception as e:
        return False, f"获取超话列表失败: {str(e)}", 0, 0, 0, 0

    if not chaohua_list:
        return True, user_info, 0, 0, 0, 0

    # 开始批量签到
    success_count = 0
    already_signed_count = 0
    fail_count = 0
    total = len(chaohua_list)
    first_failure_pushed = False

    for i, chaohua in enumerate(chaohua_list, 1):
        chaohua_id = chaohua["id"]
        chaohua_name = chaohua["name"]

        logger.debug(f"微博超话签到：[{i}/{total}] {chaohua_name}")

        result = _sign_chaohua(chaohua_id, chaohua_name)

        if result["success"]:
            if result.get("already_signed"):
                logger.debug(f"微博超话签到：[{chaohua_name}] {result['msg']}")
                already_signed_count += 1
            else:
                logger.debug(f"微博超话签到：[{chaohua_name}] {result['msg']}")
                success_count += 1
        else:
            logger.warning(f"微博超话签到：[{chaohua_name}] {result['msg']}")
            fail_count += 1
            # 第一个超话签到失败时立即推送异常提醒
            if on_first_failure and not first_failure_pushed:
                first_failure_pushed = True
                try:
                    on_first_failure(chaohua_name, result.get("msg", "未知错误"))
                except Exception:  # 回调在子线程，不阻塞签到流程
                    pass

        # 添加随机延迟，避免请求过快
        if i < total:
            delay = 3 + random.uniform(0.5, 1.0)
            time.sleep(delay)

    return True, user_info, success_count, already_signed_count, fail_count, total


async def run_weibo_chaohua_checkin_once() -> None:
    """执行一次微博超话签到流程（支持多 Cookie），并接入统一推送。"""
    app_config = get_config(reload=True)
    cfg = WeiboChaohuaCheckinConfig.from_app_config(app_config)

    if not cfg.validate():
        return

    effective_cookies = [c.strip() for c in cfg.cookies if c.strip()]
    if not effective_cookies and cfg.cookie:
        effective_cookies = [cfg.cookie.strip()]
    logger.info("微博超话签到：开始执行（共 %d 个 Cookie）", len(effective_cookies))

    import aiohttp

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
        push_manager: UnifiedPushManager | None = await build_push_manager(
            app_config.push_channel_list,
            session,
            logger,
            init_fail_prefix="微博超话签到：",
            channel_names=cfg.push_channels if cfg.push_channels else None,
        )
        if push_manager is None:
            logger.warning("微博超话签到：未配置任何推送通道，将仅在日志中记录结果")

        for idx, cookie_str in enumerate(effective_cookies):
            cfg_one = WeiboChaohuaCheckinConfig(
                enable=cfg.enable,
                cookie=cookie_str,
                cookies=[cookie_str],
                time=cfg.time,
                push_channels=cfg.push_channels,
            )
            logger.debug("微博超话签到：正在处理第 %d/%d 个账号", idx + 1, len(effective_cookies))

            loop = asyncio.get_running_loop()

            def make_on_first_failure(pm, cfg):
                def schedule_push(chaohua_name: str, msg: str) -> None:
                    def _schedule() -> None:
                        asyncio.create_task(
                            _send_weibo_chaohua_push(
                                pm,
                                title="微博超话签到异常",
                                description=f"[{chaohua_name}] {msg}",
                                success=False,
                                cfg=cfg,
                                detail=f"第一个超话签到失败时推送：{chaohua_name} - {msg}",
                            )
                        )

                    loop.call_soon_threadsafe(_schedule)

                return schedule_push

            on_first_failure = (
                make_on_first_failure(push_manager, cfg_one) if push_manager else None
            )

            try:
                (
                    success,
                    user_info_or_err,
                    success_count,
                    already_signed_count,
                    fail_count,
                    total,
                ) = await asyncio.to_thread(
                    _run_weibo_chaohua_sign_sync, cookie_str, on_first_failure
                )
            except Exception as e:
                logger.error("微博超话签到：第 %d 个账号执行异常: %s", idx + 1, e, exc_info=True)
                await _send_weibo_chaohua_push(
                    push_manager,
                    title="微博超话签到失败",
                    description=f"执行异常：{e}",
                    success=False,
                    cfg=cfg_one,
                )
                continue

            if not success:
                logger.error("微博超话签到：❌ 第 %d 个账号 %s", idx + 1, user_info_or_err)
                await _send_weibo_chaohua_push(
                    push_manager,
                    title="微博超话签到失败",
                    description=user_info_or_err,
                    success=False,
                    cfg=cfg_one,
                )
            else:
                logger.info(
                    "微博超话签到：第 %d 个账号 账号=%s 成功=%s 已签=%s 失败=%s 总计=%s",
                    idx + 1,
                    user_info_or_err,
                    success_count,
                    already_signed_count,
                    fail_count,
                    total,
                )
                summary = f"成功: {success_count}，已签: {already_signed_count}，失败: {fail_count}，总计: {total}"
                await _send_weibo_chaohua_push(
                    push_manager,
                    title="微博超话签到完成",
                    description=summary,
                    success=True,
                    cfg=cfg_one,
                    detail=f"账号: {user_info_or_err}\n{summary}",
                )

        if push_manager is not None:
            await push_manager.close()

    logger.info("微博超话签到：结束（共处理 %d 个账号）", len(effective_cookies))


async def _send_weibo_chaohua_push(
    push_manager: UnifiedPushManager | None,
    title: str,
    description: str,
    success: bool,
    cfg: WeiboChaohuaCheckinConfig,
    detail: str | None = None,
) -> None:
    """通过统一推送通道发送微博超话签到结果。"""
    if push_manager is None:
        return

    app_cfg = get_config()
    if is_in_quiet_hours(app_cfg):
        logger.debug("微博超话签到：免打扰时段，不发送推送")
        return

    masked = mask_cookie_for_log(cfg.cookie)
    status_emoji = "✅" if success else "❌"
    body = f"{status_emoji} Cookie: {masked}\n{detail or description}\n\n微博超话签到时间配置: {cfg.time}"

    try:
        await push_manager.send_news(
            title=f"{title}",
            description=body,
            to_url="https://weibo.com",
            picurl="https://cn.bing.com/th?id=OHR.DubrovnikHarbor_ZH-CN8590217905_1920x1080.jpg",
            btntxt="打开微博",
        )
    except Exception as exc:
        logger.error("微博超话签到：发送推送失败: %s", exc, exc_info=True)


def _get_weibo_chaohua_trigger_kwargs(config: AppConfig) -> dict:
    """供注册表与配置热重载使用。"""
    hour, minute = parse_checkin_time(config.weibo_chaohua_time)
    return {"minute": minute, "hour": hour}


register_task(
    "weibo_chaohua_checkin", run_weibo_chaohua_checkin_once, _get_weibo_chaohua_trigger_kwargs
)
