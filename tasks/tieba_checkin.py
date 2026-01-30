"""百度贴吧每日签到任务模块

贴吧自动签到：
- 使用配置文件中的 Cookie（须包含 BDUSS）作为参数
- 支持每天固定时间（默认 08:10）自动签到
- 项目启动时若启用也会执行一次签到
- 接入项目统一推送模板
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import random
import time
from dataclasses import dataclass

import requests

from src.config import AppConfig, get_config, is_in_quiet_hours, parse_checkin_time
from src.job_registry import register_task
from src.push_channel.manager import UnifiedPushManager, build_push_manager
from src.utils import mask_cookie_for_log

logger = logging.getLogger(__name__)

# 贴吧 API 常量
TBS_URL = "http://tieba.baidu.com/dc/common/tbs"
LIKE_URL = "http://c.tieba.baidu.com/c/f/forum/like"
SIGN_URL = "http://c.tieba.baidu.com/c/c/forum/sign"
LOGIN_INFO_URL = "https://zhidao.baidu.com/api/loginInfo"
SIGN_KEY = "tiebaclient!!!"


@dataclass
class TiebaCheckinConfig:
    """贴吧签到相关配置（支持多 Cookie）"""

    enable: bool
    cookie: str  # 单条 Cookie，兼容旧配置
    cookies: list[str]  # 多 Cookie 列表，非空时优先使用
    time: str

    @classmethod
    def from_app_config(cls, config: AppConfig) -> TiebaCheckinConfig:
        cookies: list[str] = getattr(config, "tieba_cookies", None) or []
        single = (config.tieba_cookie or "").strip()
        if not cookies and single:
            cookies = [single]
        return cls(
            enable=config.tieba_enable,
            cookie=single,
            cookies=cookies,
            time=(config.tieba_time or "08:10").strip() or "08:10",
        )

    def validate(self) -> bool:
        """校验配置是否完整"""
        if not self.enable:
            logger.debug("贴吧签到未启用，跳过执行")
            return False

        effective = self.cookies if self.cookies else ([self.cookie] if self.cookie else [])
        if not effective or not any(c.strip() for c in effective):
            logger.error("贴吧签到配置不完整，已跳过执行，缺少字段: tieba.cookie 或 tieba.cookies")
            return False

        for c in effective:
            if not c.strip():
                continue
            cookie_dict = {
                item.split("=")[0].strip(): item.split("=", 1)[1].strip()
                for item in c.split(";")
                if "=" in item
            }
            if not cookie_dict.get("BDUSS"):
                logger.warning("贴吧 Cookie 中未找到 BDUSS，该条签到可能失败")

        return True


def _run_tieba_sign_sync(cookie: str) -> tuple[bool, str, int, int, int, int]:
    """
    在同步上下文中执行贴吧签到（供 asyncio.to_thread 调用）。

    Returns:
        (login_ok, user_name_or_error, success_count, exist_count, error_count, total)
        - 登录失败时: (False, error_message, 0, 0, 0, 0)
        - 签到完成: (True, user_name, success, exist, error, total)
    """
    session = requests.Session()
    session.headers.update(
        {
            "Host": "tieba.baidu.com",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Connection": "keep-alive",
        }
    )

    cookie_dict = {
        item.split("=")[0].strip(): item.split("=", 1)[1].strip()
        for item in cookie.split(";")
        if "=" in item
    }
    requests.utils.add_dict_to_cookiejar(session.cookies, cookie_dict)
    bduss = cookie_dict.get("BDUSS", "")

    def _request(url: str, method: str = "get", data: dict | None = None, retry: int = 3) -> dict:
        for i in range(retry):
            try:
                if method.lower() == "get":
                    resp = session.get(url, timeout=10)
                else:
                    resp = session.post(url, data=data, timeout=10)
                resp.raise_for_status()
                return resp.json()
            except Exception:
                if i == retry - 1:
                    raise
                time.sleep(2)
        return {}

    def _encode_data(data: dict) -> dict:
        s = "".join(f"{k}={data[k]}" for k in sorted(data.keys()))
        sign = hashlib.md5((s + SIGN_KEY).encode("utf-8")).hexdigest().upper()
        data = dict(data)
        data["sign"] = sign
        return data

    # 获取 tbs 与登录态
    try:
        result = _request(TBS_URL)
    except Exception as e:
        return False, f"请求 TBS 失败: {e}", 0, 0, 0, 0

    if result.get("is_login", 0) == 0:
        return False, "登录失败，Cookie 可能已过期", 0, 0, 0, 0

    tbs = result.get("tbs", "")
    user_name = "贴吧用户"
    try:
        login_info = _request(LOGIN_INFO_URL)
        user_name = login_info.get("userName", user_name)
    except Exception:
        pass

    # 获取关注的贴吧列表
    forums: list[dict] = []
    page_no = 1
    sign_data_base = {
        "_client_type": "2",
        "_client_version": "9.7.8.0",
        "_phone_imei": "000000000000000",
        "model": "MI+5",
        "net_type": "1",
    }

    while True:
        data = {
            "BDUSS": bduss,
            "_client_type": "2",
            "_client_version": "9.7.8.0",
            "page_no": str(page_no),
            "page_size": "200",
            "timestamp": str(int(time.time())),
        }
        data = _encode_data(data)
        try:
            res = _request(LIKE_URL, "post", data)
        except Exception as e:
            logger.warning("贴吧签到：获取贴吧列表出错: %s", e)
            break

        if "forum_list" in res:
            flist = res["forum_list"]
            if isinstance(flist, dict):
                for key in ["non-gconforum", "gconforum"]:
                    if key in flist:
                        forums.extend(flist[key])
            elif isinstance(flist, list):
                forums.extend(flist)

        if str(res.get("has_more")) != "1":
            break
        page_no += 1
        time.sleep(1)

    if not forums:
        return True, user_name, 0, 0, 0, 0

    # 逐个签到
    success, exist, err = 0, 0, 0
    total = len(forums)

    for idx, forum in enumerate(forums):
        forum_name = forum.get("name", "")
        forum_id = forum.get("id", "")
        time.sleep(random.uniform(1, 2))

        try:
            data = dict(sign_data_base)
            data.update(
                {
                    "BDUSS": bduss,
                    "fid": forum_id,
                    "kw": forum_name,
                    "tbs": tbs,
                    "timestamp": str(int(time.time())),
                }
            )
            data = _encode_data(data)
            result = _request(SIGN_URL, "post", data)

            err_code = result.get("error_code")
            if err_code == "0":
                success += 1
                logger.debug("贴吧签到：[%s/%s] %s 签到成功", idx + 1, total, forum_name)
            elif err_code == "160002":
                exist += 1
                logger.debug("贴吧签到：[%s/%s] %s 今日已签到", idx + 1, total, forum_name)
            else:
                err += 1
                logger.warning(
                    "贴吧签到：[%s/%s] %s 失败: %s",
                    idx + 1,
                    total,
                    forum_name,
                    result.get("error_msg", err_code),
                )
        except Exception as e:
            err += 1
            logger.warning("贴吧签到：[%s/%s] %s 异常: %s", idx + 1, total, forum_name, e)

    return True, user_name, success, exist, err, total


async def run_tieba_checkin_once() -> None:
    """执行一次贴吧签到流程（支持多 Cookie），并接入统一推送。"""
    app_config = get_config(reload=True)
    cfg = TiebaCheckinConfig.from_app_config(app_config)

    if not cfg.validate():
        return

    effective_cookies = [c.strip() for c in cfg.cookies if c.strip()]
    if not effective_cookies and cfg.cookie:
        effective_cookies = [cfg.cookie.strip()]
    logger.info("贴吧签到：开始执行（共 %d 个 Cookie）", len(effective_cookies))

    import aiohttp

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
        push_manager: UnifiedPushManager | None = await build_push_manager(
            app_config.push_channel_list,
            session,
            logger,
            init_fail_prefix="贴吧签到：",
        )
        if push_manager is None:
            logger.warning("贴吧签到：未配置任何启用的推送通道，将仅在日志中记录结果")

        for idx, cookie_str in enumerate(effective_cookies):
            cfg_one = TiebaCheckinConfig(
                enable=cfg.enable,
                cookie=cookie_str,
                cookies=[cookie_str],
                time=cfg.time,
            )
            logger.debug("贴吧签到：正在处理第 %d/%d 个账号", idx + 1, len(effective_cookies))

            try:
                login_ok, user_name_or_err, success, exist, err, total = await asyncio.to_thread(
                    _run_tieba_sign_sync, cookie_str
                )
            except Exception as e:
                logger.error("贴吧签到：第 %d 个账号执行异常: %s", idx + 1, e, exc_info=True)
                await _send_tieba_push(
                    push_manager,
                    title="贴吧签到失败",
                    description=f"执行异常：{e}",
                    success=False,
                    cfg=cfg_one,
                )
                continue

            if not login_ok:
                logger.error("贴吧签到：❌ 第 %d 个账号 %s", idx + 1, user_name_or_err)
                await _send_tieba_push(
                    push_manager,
                    title="贴吧签到失败：登录失败",
                    description=user_name_or_err,
                    success=False,
                    cfg=cfg_one,
                )
            else:
                logger.info(
                    "贴吧签到：第 %d 个账号 账号=%s 成功=%s 已签=%s 失败=%s 总计=%s",
                    idx + 1,
                    user_name_or_err,
                    success,
                    exist,
                    err,
                    total,
                )
                summary = f"成功: {success}，已签: {exist}，失败: {err}，总计: {total}"
                await _send_tieba_push(
                    push_manager,
                    title="贴吧签到完成",
                    description=summary,
                    success=True,
                    cfg=cfg_one,
                    detail=f"账号: {user_name_or_err}\n{summary}",
                )

        if push_manager is not None:
            await push_manager.close()

    logger.info("贴吧签到：结束（共处理 %d 个账号）", len(effective_cookies))


async def _send_tieba_push(
    push_manager: UnifiedPushManager | None,
    title: str,
    description: str,
    success: bool,
    cfg: TiebaCheckinConfig,
    detail: str | None = None,
) -> None:
    """通过统一推送通道发送贴吧签到结果。"""
    if push_manager is None:
        return

    app_cfg = get_config()
    if is_in_quiet_hours(app_cfg):
        logger.debug("贴吧签到：免打扰时段，不发送推送")
        return

    masked = mask_cookie_for_log(cfg.cookie)
    status_emoji = "✅" if success else "❌"
    body = (
        f"{status_emoji} Cookie: {masked}\n{detail or description}\n\n贴吧签到时间配置: {cfg.time}"
    )

    try:
        await push_manager.send_news(
            title=f"{title}（{masked}）",
            description=body,
            to_url="https://tieba.baidu.com",
            picurl="https://cn.bing.com/th?id=OHR.DubrovnikHarbor_ZH-CN8590217905_1920x1080.jpg",
            btntxt="打开贴吧",
        )
    except Exception as exc:
        logger.error("贴吧签到：发送推送失败: %s", exc, exc_info=True)


def _get_tieba_trigger_kwargs(config: AppConfig) -> dict:
    """供注册表与配置热重载使用。"""
    hour, minute = parse_checkin_time(config.tieba_time)
    return {"minute": minute, "hour": hour}


register_task("tieba_checkin", run_tieba_checkin_once, _get_tieba_trigger_kwargs)
