"""微博 Cookie 静默续期任务。"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from src.core.paths import CONFIG_YAML_FILE
from src.core.weibo_http import (
    WEIBO_CHAOHUA_LIST_URL,
    WEIBO_DESKTOP_USER_AGENT,
    WEIBO_SPA_CONFIG_URL,
    extract_weibo_login_uid,
)
from src.jobs.registry import register_task
from src.jobs.task_outcome import TASK_FAILED, TASK_SUCCESS, TaskOutcome
from src.settings.config import AppConfig, get_config, parse_checkin_time
from src.settings.config_writer import (
    ConfigUpdateResult,
    ConfigValueUpdate,
    ConfigWriteError,
    apply_config_updates,
)
from src.tasks.common import push_manager_context, send_news_if_allowed

logger = logging.getLogger(__name__)

WEIBO_HOME_URL = "https://weibo.com/"
WEIBO_MONITOR_URL = "https://www.weibo.com/ajax/statuses/mymblog"
_PAGE_LOAD_TIMEOUT_SECONDS = 60
_COOKIE_SETTLE_SECONDS = 3
_LOGIN_VALIDATION_TIMEOUT_SECONDS = 15
_BROWSER_AUTH_FALLBACK_NAMES = frozenset({"SUB"})
_LOCAL_PROXY_BYPASS = ("localhost", "127.0.0.1", "::1")
_COMMON_CHROME_NAMES = (
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
)


class CookieRefreshError(RuntimeError):
    """可安全输出的 Cookie 刷新错误，不包含 Cookie 内容。"""


@dataclass(frozen=True)
class CookieRenewalResult:
    success: bool
    cookie_string: str = ""
    error: str = ""


@dataclass(frozen=True)
class CookieValidationRequirements:
    validate_weibo: bool = False
    validate_chaohua: bool = False


@dataclass(frozen=True)
class CookieFieldSnapshot:
    path: tuple[str, ...]
    value: str | list[str]
    requires_xsrf: bool

    @property
    def label(self) -> str:
        return ".".join(self.path)

    def values(self) -> list[str]:
        if isinstance(self.value, list):
            return list(self.value)
        return [self.value]


@dataclass(frozen=True)
class RefreshSummary:
    total_targets: int
    renewed_targets: int
    unique_cookies: int
    changed_fields: tuple[str, ...]
    conflicts: tuple[str, ...]
    failures: tuple[str, ...]
    wrote_file: bool

    @property
    def success(self) -> bool:
        return (
            self.total_targets > 0
            and self.renewed_targets == self.total_targets
            and not self.conflicts
            and not self.failures
        )


def _parse_cookie_string(cookie_string: str) -> list[tuple[str, str]]:
    """解析 Cookie 请求头；value 中额外的等号会被保留。"""
    parsed: list[tuple[str, str]] = []
    for part in str(cookie_string or "").replace("\r", "").replace("\n", "").split(";"):
        name, separator, value = part.strip().partition("=")
        if not separator or not name or not value:
            continue
        parsed.append((name.strip(), value.strip()))
    return parsed


def _cookie_names(cookie_string: str) -> set[str]:
    return {name for name, _ in _parse_cookie_string(cookie_string)}


def _browser_cookie_values(cookies: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """提取 WebDriver 中属于微博域名的 Cookie，并按名称去重。"""
    values: dict[str, str] = {}
    order: list[str] = []
    for cookie in cookies:
        name = str(cookie.get("name") or "").strip()
        value = str(cookie.get("value") or "").strip()
        domain = str(cookie.get("domain") or "").lower()
        if not name or not value:
            continue
        if domain and "weibo.com" not in domain and "weibo.cn" not in domain:
            continue
        if name not in values:
            order.append(name)
        values[name] = value
    return [(name, values[name]) for name in order]


def _merge_cookie_string(
    original_cookie_string: str,
    browser_cookies: list[dict[str, Any]],
) -> str:
    """保留原 Cookie 的字段与顺序，仅合并浏览器返回的新值。"""
    browser_pairs = _browser_cookie_values(browser_cookies)
    browser_values = dict(browser_pairs)
    browser_order = [name for name, _ in browser_pairs]
    merged: list[tuple[str, str]] = []
    original_names: set[str] = set()

    for name, original_value in _parse_cookie_string(original_cookie_string):
        merged.append((name, browser_values.get(name, original_value)))
        original_names.add(name)

    for name in browser_order:
        if name not in original_names:
            merged.append((name, browser_values[name]))
            original_names.add(name)

    return "; ".join(f"{name}={value}" for name, value in merged)


def _ensure_localhost_proxy_bypass() -> None:
    """避免 HTTP(S)_PROXY 截获 Selenium 到本机 chromedriver 的连接。"""
    for env_name in ("NO_PROXY", "no_proxy"):
        existing = [item.strip() for item in os.environ.get(env_name, "").split(",") if item.strip()]
        lowered = {item.lower() for item in existing}
        for host in _LOCAL_PROXY_BYPASS:
            if host.lower() not in lowered:
                existing.append(host)
        os.environ[env_name] = ",".join(existing)


def _resolve_chrome_binary() -> str | None:
    configured = os.environ.get("CHROME_BIN", "").strip()
    if configured:
        if not Path(configured).is_file():
            raise CookieRefreshError("CHROME_BIN 指向的浏览器不存在或不可用")
        return configured
    for name in _COMMON_CHROME_NAMES:
        if candidate := shutil.which(name):
            return candidate
    return None


def _create_webdriver():
    """延迟导入 Selenium，使关闭任务时不影响精简镜像启动。"""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
    except ModuleNotFoundError as exc:
        raise CookieRefreshError(
            "未安装 Selenium；源码运行请执行 uv sync --extra rainyun，Docker 请使用 full 镜像"
        ) from exc

    _ensure_localhost_proxy_bypass()
    options = Options()
    if chrome_binary := _resolve_chrome_binary():
        options.binary_location = chrome_binary
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-first-run")
    options.add_argument(f"--user-agent={WEIBO_DESKTOP_USER_AGENT}")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    configured_driver = os.environ.get("CHROMEDRIVER_PATH", "").strip()
    if configured_driver:
        if not Path(configured_driver).is_file():
            raise CookieRefreshError("CHROMEDRIVER_PATH 指向的驱动不存在或不可用")
        return webdriver.Chrome(service=Service(configured_driver), options=options)
    return webdriver.Chrome(options=options)


def _safe_browser_error(exc: BaseException) -> str:
    if isinstance(exc, CookieRefreshError):
        return str(exc)
    name = type(exc).__name__
    if name in {"TimeoutException", "ReadTimeoutError"}:
        return "微博页面加载超时"
    if name in {
        "SessionNotCreatedException",
        "WebDriverException",
        "NoSuchDriverException",
    }:
        return "Chrome/WebDriver 启动或访问失败，请检查版本及 CHROME_BIN/CHROMEDRIVER_PATH"
    return f"刷新过程中发生异常（{name}）"


def _cookie_value(cookie_string: str, target_name: str) -> str:
    for name, value in _parse_cookie_string(cookie_string):
        if name == target_name:
            return value
    return ""


def _request_validation_payload(
    cookie_string: str,
    url: str,
    params: dict[str, str],
    label: str,
    *,
    trust_env: bool,
    xsrf_token: str = "",
    referer: str = WEIBO_HOME_URL,
) -> tuple[dict[str, Any] | None, str | None]:
    headers = {
        "User-Agent": WEIBO_DESKTOP_USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": referer,
        "Cookie": cookie_string,
        "X-Requested-With": "XMLHttpRequest",
    }
    if xsrf_token:
        headers["X-XSRF-TOKEN"] = xsrf_token

    session = requests.Session()
    session.trust_env = trust_env
    try:
        response = session.get(
            url,
            params=params,
            headers=headers,
            timeout=_LOGIN_VALIDATION_TIMEOUT_SECONDS,
        )
        if response.status_code in {401, 403}:
            return None, f"{label}拒绝当前登录态（HTTP {response.status_code}）"
        if response.status_code != 200:
            return None, f"{label}校验失败（HTTP {response.status_code}）"
        try:
            payload = response.json()
        except ValueError:
            return None, f"{label}返回了非 JSON 响应"
        if not isinstance(payload, dict) or payload.get("ok") != 1:
            return None, f"{label}返回未登录状态"
        return payload, None
    except requests.Timeout:
        return None, f"{label}校验超时"
    except requests.RequestException as exc:
        return None, f"{label}校验请求失败（{type(exc).__name__}）"
    finally:
        session.close()


def _validate_cookie_sync(
    cookie_string: str,
    requirements: CookieValidationRequirements,
    validation_uid: str,
) -> str | None:
    """用任务实际依赖的微博接口验证 Cookie，返回可安全记录的错误。"""
    if not requirements.validate_weibo and not requirements.validate_chaohua:
        return "没有可用的登录校验目标"

    xsrf_token = _cookie_value(cookie_string, "XSRF-TOKEN")
    if requirements.validate_chaohua and not xsrf_token:
        return "Cookie 缺少 XSRF-TOKEN，无法用于微博超话"

    login_uid = ""
    if requirements.validate_chaohua or (requirements.validate_weibo and not validation_uid):
        spa_payload, error = _request_validation_payload(
            cookie_string,
            WEIBO_SPA_CONFIG_URL,
            {},
            "微博登录接口",
            trust_env=requirements.validate_chaohua,
        )
        if error:
            return error
        login_uid = extract_weibo_login_uid(spa_payload)
        if not login_uid:
            return "微博登录接口未识别到完整登录账号，Cookie 可能仅为匿名会话"

    if requirements.validate_weibo and validation_uid:
        _, error = _request_validation_payload(
            cookie_string,
            WEIBO_MONITOR_URL,
            {"uid": validation_uid, "page": "1", "feature": "0"},
            "微博监控接口",
            trust_env=False,
        )
        if error:
            return error

    if requirements.validate_chaohua:
        follow_referer = (
            f"https://weibo.com/u/page/follow/{login_uid}/231093_-_chaohua"
        )
        payload, error = _request_validation_payload(
            cookie_string,
            WEIBO_CHAOHUA_LIST_URL,
            {"tabid": "231093_-_chaohua", "page": "1", "uid": login_uid},
            "微博超话接口",
            trust_env=True,
            xsrf_token=xsrf_token,
            referer=follow_referer,
        )
        if error:
            return error
        api_data = payload.get("data") if payload else None
        if not isinstance(api_data, dict) or not isinstance(api_data.get("list"), list):
            return "微博超话接口返回结构无效"

    return None


def _renew_cookie_sync(
    cookie_string: str,
    requirements: CookieValidationRequirements | None = None,
    validation_uid: str = "",
) -> CookieRenewalResult:
    """使用一个隔离的浏览器会话续期一条 Cookie。"""
    parsed = _parse_cookie_string(cookie_string)
    if not parsed:
        return CookieRenewalResult(False, error="Cookie 格式为空或无效")
    if "SUB" not in {name for name, _ in parsed}:
        return CookieRenewalResult(False, error="Cookie 缺少登录标志 SUB")

    effective_requirements = requirements or CookieValidationRequirements(validate_weibo=True)
    try:
        initial_error = _validate_cookie_sync(
            cookie_string,
            effective_requirements,
            validation_uid,
        )
    except Exception as exc:  # noqa: BLE001
        return CookieRenewalResult(
            False,
            error=f"原 Cookie 登录校验异常（{type(exc).__name__}）",
        )
    if initial_error:
        return CookieRenewalResult(
            False,
            error=f"原 Cookie 已失效或不可用：{initial_error}；请重新获取 Cookie",
        )

    driver = None
    try:
        driver = _create_webdriver()
        driver.set_page_load_timeout(_PAGE_LOAD_TIMEOUT_SECONDS)
        driver.get(WEIBO_HOME_URL)
        driver.delete_all_cookies()

        rejected = 0
        for name, value in parsed:
            try:
                driver.add_cookie(
                    {
                        "name": name,
                        "value": value,
                        "domain": ".weibo.com",
                        "path": "/",
                    }
                )
            except Exception:  # noqa: BLE001
                rejected += 1
        if driver.get_cookie("SUB") is None:
            raise CookieRefreshError("SUB Cookie 无法注入浏览器")

        driver.get(WEIBO_HOME_URL)
        try:
            from selenium.webdriver.support.ui import WebDriverWait

            WebDriverWait(driver, 15).until(
                lambda current: current.execute_script("return document.readyState") == "complete"
            )
        except Exception:  # noqa: BLE001
            logger.debug("微博 Cookie 刷新：页面 readyState 等待超时，继续检查登录 Cookie")
        time.sleep(_COOKIE_SETTLE_SECONDS)

        current_url = str(driver.current_url or "").lower()
        if "passport.weibo.com" in current_url or "login.sina.com" in current_url:
            raise CookieRefreshError("登录状态已失效，需要重新获取 Cookie")

        browser_cookies = driver.get_cookies()
        refreshed = _merge_cookie_string(cookie_string, browser_cookies)
        refreshed_names = _cookie_names(refreshed)
        if "SUB" not in refreshed_names:
            raise CookieRefreshError("续期后未检测到 SUB，登录状态已失效")
        candidate_error = _validate_cookie_sync(
            refreshed,
            effective_requirements,
            validation_uid,
        )
        browser_rotated_sub = _cookie_value(refreshed, "SUB") != _cookie_value(
            cookie_string,
            "SUB",
        )
        if candidate_error and browser_rotated_sub:
            fallback_cookies = [
                cookie
                for cookie in browser_cookies
                if str(cookie.get("name") or "") not in _BROWSER_AUTH_FALLBACK_NAMES
            ]
            fallback = _merge_cookie_string(cookie_string, fallback_cookies)
            fallback_error = _validate_cookie_sync(
                fallback,
                effective_requirements,
                validation_uid,
            )
            if fallback_error is None:
                logger.warning(
                    "微博 Cookie 刷新：浏览器旋转的 SUB 未通过接口校验，已保留原 SUB"
                )
                refreshed = fallback
                candidate_error = None
        if candidate_error:
            raise CookieRefreshError(
                f"续期候选 Cookie 未通过服务端校验：{candidate_error}；已保留原配置"
            )
        if rejected:
            logger.debug("微博 Cookie 刷新：有 %d 个非关键 Cookie 未被浏览器接受", rejected)
        return CookieRenewalResult(True, cookie_string=refreshed)
    except Exception as exc:  # noqa: BLE001
        return CookieRenewalResult(False, error=_safe_browser_error(exc))
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:  # noqa: BLE001
                pass


def _collect_field_snapshots(config: AppConfig) -> list[CookieFieldSnapshot]:
    snapshots: list[CookieFieldSnapshot] = []
    if config.weibo_cookie:
        snapshots.append(CookieFieldSnapshot(("weibo", "cookie"), config.weibo_cookie, False))
    if config.weibo_chaohua_cookie:
        snapshots.append(
            CookieFieldSnapshot(
                ("weibo_chaohua", "cookie"),
                config.weibo_chaohua_cookie,
                True,
            )
        )
    if config.weibo_chaohua_cookies:
        snapshots.append(
            CookieFieldSnapshot(
                ("weibo_chaohua", "cookies"),
                list(config.weibo_chaohua_cookies),
                True,
            )
        )
    return snapshots


def _unique_cookie_values(snapshots: list[CookieFieldSnapshot]) -> list[str]:
    unique: dict[str, None] = {}
    for snapshot in snapshots:
        for value in snapshot.values():
            normalized = str(value or "").strip()
            if normalized:
                unique.setdefault(normalized, None)
    return list(unique)


def _cookie_requirements(
    snapshots: list[CookieFieldSnapshot],
) -> dict[str, CookieValidationRequirements]:
    requirements: dict[str, CookieValidationRequirements] = {}
    for snapshot in snapshots:
        for value in snapshot.values():
            normalized = str(value or "").strip()
            if not normalized:
                continue
            current = requirements.get(normalized, CookieValidationRequirements())
            requirements[normalized] = CookieValidationRequirements(
                validate_weibo=current.validate_weibo or not snapshot.requires_xsrf,
                validate_chaohua=current.validate_chaohua or snapshot.requires_xsrf,
            )
    return requirements


def _first_validation_uid(config: AppConfig) -> str:
    return next(
        (uid.strip() for uid in str(config.weibo_uids or "").split(",") if uid.strip()),
        "",
    )


async def _renew_unique_cookies(
    cookie_values: list[str],
    requirements: dict[str, CookieValidationRequirements],
    validation_uid: str,
) -> dict[str, CookieRenewalResult]:
    results: dict[str, CookieRenewalResult] = {}
    for index, cookie_value in enumerate(cookie_values, start=1):
        logger.info("微博 Cookie 刷新：正在处理第 %d/%d 个唯一 Cookie", index, len(cookie_values))
        result = await asyncio.to_thread(
            _renew_cookie_sync,
            cookie_value,
            requirements.get(cookie_value),
            validation_uid,
        )
        results[cookie_value] = result
        if result.success:
            logger.info("微博 Cookie 刷新：第 %d 个 Cookie 续期成功", index)
        else:
            logger.error("微博 Cookie 刷新：第 %d 个 Cookie 续期失败：%s", index, result.error)
    return results


def _build_config_updates(
    snapshots: list[CookieFieldSnapshot],
    results: dict[str, CookieRenewalResult],
) -> tuple[list[ConfigValueUpdate], int, list[str]]:
    updates: list[ConfigValueUpdate] = []
    renewed_targets = 0
    failures: list[str] = []

    for snapshot in snapshots:
        proposed: list[str] = []
        field_has_success = False
        for index, original in enumerate(snapshot.values()):
            normalized = str(original or "").strip()
            item_label = (
                f"{snapshot.label}[{index + 1}]" if isinstance(snapshot.value, list) else snapshot.label
            )
            if not normalized:
                proposed.append(original)
                continue
            result = results.get(normalized)
            if result is None or not result.success:
                proposed.append(original)
                failures.append(f"{item_label}：{result.error if result else '未执行'}")
                continue
            if snapshot.requires_xsrf and "XSRF-TOKEN" not in _cookie_names(result.cookie_string):
                proposed.append(original)
                failures.append(f"{item_label}：续期结果缺少 XSRF-TOKEN")
                continue
            proposed.append(result.cookie_string)
            renewed_targets += 1
            field_has_success = True

        if not field_has_success:
            continue
        new_value: str | list[str] = proposed if isinstance(snapshot.value, list) else proposed[0]
        updates.append(
            ConfigValueUpdate(
                path=snapshot.path,
                expected=snapshot.value,
                value=new_value,
            )
        )

    return updates, renewed_targets, failures


def _format_push(summary: RefreshSummary) -> tuple[str, str]:
    if summary.success:
        title = "微博 Cookie 刷新成功"
        status = "✅ 全部 Cookie 已完成静默续期"
    elif summary.renewed_targets:
        title = "微博 Cookie 刷新部分失败"
        status = "⚠️ 部分 Cookie 已续期，其余保留旧配置"
    else:
        title = "微博 Cookie 刷新失败"
        status = "❌ 未能续期 Cookie，原配置保持不变"

    lines = [
        status,
        f"配置目标：{summary.total_targets}",
        f"续期成功：{summary.renewed_targets}",
        f"唯一 Cookie：{summary.unique_cookies}",
        f"写回字段：{len(summary.changed_fields)}",
    ]
    if summary.conflicts:
        lines.append("并发冲突：" + "、".join(summary.conflicts))
    if summary.failures:
        lines.append("失败详情：")
        lines.extend(f"- {detail}" for detail in summary.failures)
    if summary.renewed_targets and not summary.wrote_file and not summary.conflicts:
        lines.append("Cookie 值未变化，无需重写配置文件")
    return title, "\n".join(lines)


async def _send_summary(config: AppConfig, summary: RefreshSummary) -> None:
    title, description = _format_push(summary)
    async with push_manager_context(
        config,
        logger,
        push_channels=list(config.weibo_push_channels or []),
        init_fail_prefix="微博 Cookie 刷新：",
    ) as push:
        if push is None:
            logger.warning("微博 Cookie 刷新：未配置可用推送通道，将仅记录日志")
        await send_news_if_allowed(
            push,
            config,
            logger,
            quiet_log="微博 Cookie 刷新：当前处于免打扰时段，不发送结果推送",
            error_log="微博 Cookie 刷新：发送结果推送失败：%s",
            title=title,
            description=description,
            to_url=WEIBO_HOME_URL,
            picurl="",
            btntxt="打开微博",
        )


async def _send_summary_safely(config: AppConfig, summary: RefreshSummary) -> None:
    try:
        await _send_summary(config, summary)
    except Exception as exc:  # noqa: BLE001
        logger.error("微博 Cookie 刷新：结果推送流程异常（%s）", type(exc).__name__)


async def run_weibo_cookie_refresh_once() -> TaskOutcome:
    """刷新配置中的微博与微博超话 Cookie，并发送一次脱敏汇总。"""
    config = get_config(reload=True)
    snapshots = _collect_field_snapshots(config)
    unique_cookies = _unique_cookie_values(snapshots)
    requirements = _cookie_requirements(snapshots)
    total_targets = sum(
        1 for snapshot in snapshots for value in snapshot.values() if str(value or "").strip()
    )

    if not unique_cookies:
        summary = RefreshSummary(0, 0, 0, (), (), ("未配置可刷新的微博 Cookie",), False)
        logger.error("微博 Cookie 刷新：未配置可刷新的 Cookie")
        await _send_summary_safely(config, summary)
        return TASK_FAILED

    logger.info(
        "微博 Cookie 刷新：开始执行（配置目标 %d 个，唯一 Cookie %d 个）",
        total_targets,
        len(unique_cookies),
    )
    renewal_results = await _renew_unique_cookies(
        unique_cookies,
        requirements,
        _first_validation_uid(config),
    )
    updates, renewed_targets, failures = _build_config_updates(snapshots, renewal_results)

    write_result = ConfigUpdateResult((), (), (), False)
    if updates:
        try:
            write_result = await apply_config_updates(CONFIG_YAML_FILE, updates)
        except ConfigWriteError:
            message = "配置校验或写入失败，请检查 config.yml 权限与格式"
            failures.append(message)
            logger.error("微博 Cookie 刷新：%s", message)
        except Exception as exc:  # noqa: BLE001
            message = f"配置写回异常（{type(exc).__name__}）"
            failures.append(message)
            logger.error("微博 Cookie 刷新：%s", message)

    conflicts = tuple(write_result.conflict_paths)
    if conflicts:
        logger.warning("微博 Cookie 刷新：检测到配置并发修改，已跳过字段：%s", ", ".join(conflicts))
        failures.append("配置已被并发修改，冲突字段未覆盖")

    summary = RefreshSummary(
        total_targets=total_targets,
        renewed_targets=renewed_targets,
        unique_cookies=len(unique_cookies),
        changed_fields=tuple(write_result.changed_paths),
        conflicts=conflicts,
        failures=tuple(failures),
        wrote_file=write_result.wrote_file,
    )
    await _send_summary_safely(config, summary)
    logger.info(
        "微博 Cookie 刷新：执行结束（续期 %d/%d，写回字段 %d，失败 %d）",
        summary.renewed_targets,
        summary.total_targets,
        len(summary.changed_fields),
        len(summary.failures),
    )
    return TASK_SUCCESS if summary.success else TASK_FAILED


def _get_weibo_cookie_refresh_trigger_kwargs(config: AppConfig) -> dict[str, str]:
    raw = str(getattr(config, "weibo_cookie_refresh_time", "21:00") or "21:00").strip()
    if not re.fullmatch(r"(?:[01]?\d|2[0-3]):[0-5]?\d", raw):
        raw = "21:00"
    hour, minute = parse_checkin_time(raw)
    return {"minute": minute, "hour": hour}


register_task(
    "weibo_cookie_refresh",
    run_weibo_cookie_refresh_once,
    _get_weibo_cookie_refresh_trigger_kwargs,
    run_on_startup=False,
    description="微博 Cookie 自动刷新",
)
