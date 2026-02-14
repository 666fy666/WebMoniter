"""雨云签到任务模块

雨云自动签到脚本（参考 Jielumoon/Rainyun-Qiandao）：
- 使用 Selenium + 账号密码 + ddddocr 完成签到（非 API Key 方式）
- 支持多账号，每账号独立 Cookie 缓存
- 支持每天固定时间（默认 08:30）自动签到
- 项目启动时也会执行一次签到
- 签到后检查游戏云服务器到期，可选自动续费
"""

from __future__ import annotations

import asyncio
import logging

import aiohttp

from src.config import AppConfig, get_config, is_in_quiet_hours, parse_checkin_time
from src.job_registry import register_task
from src.push_channel.manager import build_push_manager
from tasks.rainyun.config_adapter import RainyunAccountConfig
from tasks.rainyun.runner import run_single_account

logger = logging.getLogger(__name__)


def _build_accounts_from_config(config: AppConfig) -> list[RainyunAccountConfig]:
    """从 AppConfig 构建 RainyunAccountConfig 列表"""
    accounts: list[RainyunAccountConfig] = []
    raw = getattr(config, "rainyun_accounts", None) or []

    auto_renew = getattr(config, "rainyun_auto_renew", True)
    renew_product_ids = list(getattr(config, "rainyun_renew_product_ids", None) or [])

    for a in raw:
        if not isinstance(a, dict):
            continue
        username = str(a.get("username", "")).strip()
        password = str(a.get("password", "")).strip()
        api_key = str(a.get("api_key", "")).strip()

        if not username or not password:
            continue

        accounts.append(
            RainyunAccountConfig(
                username=username,
                password=password,
                api_key=api_key,
                display_name=username,
                renew_product_ids=renew_product_ids,
                auto_renew=auto_renew,
            )
        )
    return accounts


async def _run_single_account_async(
    account: RainyunAccountConfig,
    renew_threshold_days: int,
    push_manager,
    *,
    chrome_overrides: dict | None = None,
) -> tuple[bool, str]:
    """在线程池中运行 run_single_account（同步函数）"""
    overrides = {"renew_threshold_days": renew_threshold_days}
    if chrome_overrides:
        overrides.update(chrome_overrides)
    loop = asyncio.get_event_loop()
    ok, msg = await loop.run_in_executor(
        None,
        lambda: run_single_account(account, **overrides),
    )
    return ok, msg


async def run_rainyun_checkin_once() -> None:
    """执行一次完整的雨云签到流程（支持多账号，使用 Rainyun-Qiandao 的 Selenium 流程）"""
    app_config = get_config(reload=True)

    if not app_config.rainyun_enable:
        logger.debug("雨云签到未启用，跳过执行")
        return

    accounts = _build_accounts_from_config(app_config)
    if not accounts:
        logger.error(
            "雨云签到配置不完整，已跳过执行。请配置 rainyun.accounts（每项需 username、password，api_key 可选用于续费）"
        )
        return

    renew_threshold_days = getattr(app_config, "rainyun_renew_threshold_days", 7)
    push_channels = getattr(app_config, "rainyun_push_channels", None) or []

    logger.info("雨云签到：开始执行签到任务（共 %d 个账号）", len(accounts))

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
        push_manager = await build_push_manager(
            app_config.push_channel_list,
            session,
            logger,
            init_fail_prefix="雨云签到：",
            channel_names=push_channels if push_channels else None,
        )

        if push_manager is None:
            logger.warning("雨云签到：未配置任何推送通道，将仅在日志中记录结果")

        # Chrome/Chromium 路径（config 优先，否则由 runner 从环境变量读取）
        chrome_overrides = {}
        if getattr(app_config, "rainyun_chrome_bin", ""):
            chrome_overrides["chrome_bin"] = app_config.rainyun_chrome_bin
        if getattr(app_config, "rainyun_chromedriver_path", ""):
            chrome_overrides["chromedriver_path"] = app_config.rainyun_chromedriver_path

        success_count = 0
        for idx, account in enumerate(accounts, start=1):
            logger.info(
                "雨云签到：正在处理第 %d/%d 个账号 %s", idx, len(accounts), account.username
            )
            try:
                ok, msg = await _run_single_account_async(
                    account, renew_threshold_days, push_manager, chrome_overrides=chrome_overrides
                )
                if ok:
                    success_count += 1

                await _send_checkin_push(
                    push_manager,
                    title="雨云签到成功" if ok else "雨云签到失败",
                    msg=msg,
                    success=ok,
                    account_name=account.username,
                )
            except Exception as exc:
                logger.error("雨云签到：账号 %s 执行异常：%s", account.username, exc, exc_info=True)
                await _send_checkin_push(
                    push_manager,
                    title="雨云签到失败",
                    msg=f"账号 {account.username} 执行异常：{exc}",
                    success=False,
                    account_name=account.username,
                )

        if push_manager is not None:
            await push_manager.close()

    logger.info("雨云签到：任务执行完成（成功 %d/%d 个账号）", success_count, len(accounts))


async def _send_checkin_push(
    push_manager,
    title: str,
    msg: str,
    success: bool,
    account_name: str,
) -> None:
    """发送签到结果推送"""
    if push_manager is None:
        return

    app_cfg = get_config()
    if is_in_quiet_hours(app_cfg):
        logger.debug("雨云签到：免打扰时段，不发送推送")
        return

    status_emoji = "✅" if success else "❌"
    description = f"{status_emoji} 账号：{account_name}\n{msg}"

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
