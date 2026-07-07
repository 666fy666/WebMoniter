"""iKuuu/SSPanel ikuuu签到任务模块

iKuuu 自动签到脚本：
- 自动从 ikuuu.club 提取可用域名，无需手动配置域名/URL
- 支持每天固定时间（默认 08:00）自动签到
- 项目启动时也会执行一次签到
"""

from __future__ import annotations

import asyncio
import base64
import html
import json
import logging
import os
import re
import shutil
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any
from urllib.parse import urlparse

import aiohttp
from bs4 import BeautifulSoup

from src.core.paths import DATA_DIR
from src.jobs.registry import register_task
from src.jobs.task_outcome import TASK_FAILED, TASK_SUCCESS
from src.push_channel.manager import UnifiedPushManager, build_push_manager
from src.settings.config import AppConfig, get_config, is_in_quiet_hours, parse_checkin_time

logger = logging.getLogger(__name__)

# ikuuu 域名发现入口；后几个是历史上出现过的“最新域名公告页”，用于入口被拦截时兜底。
_IKUUU_DISCOVERY_URL = "http://ikuuu.club"
_IKUUU_DISCOVERY_URLS = (
    "https://ikuuu.club",
    "http://ikuuu.club",
    "https://ikuuu.eu",
    "https://ikuuu.de",
    "https://ikuuu.pro",
)
_IKUUU_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
_IKUUU_MAX_RETRIES = 5
_IKUUU_RETRY_DELAY_SECONDS = 2
_IKUUU_PRIMARY_DOMAIN = "ikuuu.win"
_IKUUU_DOMAIN_CACHE_FILE = DATA_DIR / "ikuuu_domain_cache.json"
_IKUUU_DOMAIN_CACHE_MAX_AGE_SECONDS = 7 * 24 * 60 * 60

# 当前登录页白名单里出现的实际域名；非白名单域名会被前端跳转到 ikuuu.win。
_IKUUU_LOGIN_PAGE_DOMAINS = (
    "ikuuu.win",
    "ikuuu.co",
    "ikuuu.ltd",
    "ikuuu.org",
    "ikuuu.live",
    "ikuuu.one",
    "ikuuu.dev",
    "ikuuu.eu",
    "ikuuu.uk",
    "ikuuu.art",
    "ikuuu.boo",
    "ikuuu.fyi",
    "ikuuu.me",
    "ikuuu.pw",
    "ikuuu.top",
    "ikuuu.de",
    "ikuuu.nl",
    "ikuuu.ch",
)
_IKUUU_LEGACY_DOMAINS = (
    "ikuuu.pro",
    "ikuuu.com",
    "ikuuu.cc",
)
_IKUUU_RECENT_DOMAINS = tuple(dict.fromkeys((*_IKUUU_LOGIN_PAGE_DOMAINS, *_IKUUU_LEGACY_DOMAINS)))
_IKUUU_FAST_FALLBACK_DOMAINS = (
    "ikuuu.eu",
    "ikuuu.de",
    "ikuuu.fyi",
    "ikuuu.nl",
    "ikuuu.org",
    "ikuuu.pw",
)

# ikuuu 历史使用过的 TLD，按首字母分组
# 用于解析混淆 JS 中被拆分的域名片段（如 'uuu.f' + 混淆函数() → ikuuu.fyi）
_IKUUU_TLD_CANDIDATES: dict[str, list[str]] = {
    "a": ["art"],
    "b": ["bar", "biz"],
    "c": ["co", "com", "cam"],
    "d": ["de", "dev"],
    "e": ["eu"],
    "f": ["fyi", "fun"],
    "g": ["group"],
    "i": ["io"],
    "m": ["me"],
    "n": ["nl", "net"],
    "o": ["one", "org"],
    "p": ["pro"],
    "s": ["site", "store"],
    "t": ["top", "tv"],
    "u": ["us"],
    "w": ["world", "win"],
}


@dataclass
class _DomainProbeResult:
    domain: str
    score: int
    elapsed_ms: int
    reason: str


_IKUUU_DOMAIN_RE = re.compile(
    r"(?<![a-z0-9-])(?:https?://)?(?:www\.)?(ikuuu\.[a-z]{2,12})(?![a-z0-9-])",
    re.IGNORECASE,
)


def _normalize_ikuuu_domain(raw: str) -> str | None:
    """把 URL/文本片段归一成 ikuuu.xxx 域名。"""
    value = (raw or "").strip().lower()
    if not value:
        return None
    match = _IKUUU_DOMAIN_RE.search(value)
    if not match:
        return None
    domain = match.group(1).rstrip(".")
    if domain == "ikuuu.club":
        return None
    return domain


def _add_domain_candidate(
    candidates: dict[str, int], raw_domain: str, score: int, source: str
) -> None:
    domain = _normalize_ikuuu_domain(raw_domain)
    if not domain:
        return
    candidates[domain] = max(candidates.get(domain, 0), score)
    logger.debug("ikuuu签到：域名候选 %s 来源=%s 分数=%d", domain, source, score)


def _load_cached_ikuuu_domain() -> str | None:
    try:
        raw = json.loads(_IKUUU_DOMAIN_CACHE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    domain = _normalize_ikuuu_domain(str(raw.get("domain", "")))
    updated_at = float(raw.get("updated_at", 0) or 0)
    if not domain:
        return None
    if time.time() - updated_at > _IKUUU_DOMAIN_CACHE_MAX_AGE_SECONDS:
        logger.debug("ikuuu签到：缓存域名 %s 已过期", domain)
        return None
    return domain


def _save_cached_ikuuu_domain(domain: str, source: str) -> None:
    normalized = _normalize_ikuuu_domain(domain)
    if not normalized:
        return
    try:
        _IKUUU_DOMAIN_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _IKUUU_DOMAIN_CACHE_FILE.write_text(
            json.dumps(
                {"domain": normalized, "source": source, "updated_at": time.time()},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.debug("ikuuu签到：写入域名缓存失败：%s", exc)


async def _ikuuu_host_resolves(host: str, port: int) -> bool:
    """在 aiohttp 请求前先解析域名，避免不可达域名产生 shielded future 噪声。"""
    try:
        loop = asyncio.get_running_loop()
        await asyncio.wait_for(
            loop.getaddrinfo(host, port, type=socket.SOCK_STREAM),
            timeout=3,
        )
        return True
    except (asyncio.TimeoutError, OSError) as exc:
        logger.debug("ikuuu签到：域名 %s DNS 解析失败或超时：%s", host, exc)
        return False


async def _ikuuu_url_resolves(url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.hostname
    if not host:
        return False
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return await _ikuuu_host_resolves(host, port)


def _extract_literal_joined_chunks(text: str) -> list[str]:
    """粗略还原 JS 中连续字符串字面量拼接出来的片段。"""
    chunks: list[str] = []
    pattern = re.compile(r"""(?:(['"])(?:\\.|(?!\1).)*\1\s*\+\s*)+(['"])(?:\\.|(?!\2).)*\2""")
    for expr_match in pattern.finditer(text):
        expr = expr_match.group(0)
        if "ik" not in expr.lower() and "uuu" not in expr.lower():
            continue
        parts = re.findall(r"""(['"])((?:\\.|(?!\1).)*)\1""", expr)
        joined = "".join(part for _, part in parts)
        if joined:
            chunks.append(joined)
    return chunks


def _extract_origin_body_variants(text: str) -> list[str]:
    """部分 ikuuu 页面把真实 HTML 放在 originBody 的 base64 字符串里。"""
    variants: list[str] = []
    for match in re.finditer(r"""originBody\s*=\s*["']([A-Za-z0-9+/=]+)["']""", text):
        try:
            decoded = base64.b64decode(match.group(1)).decode("utf-8")
        except Exception:
            continue
        if decoded:
            variants.append(decoded)
    return variants


def _extract_domain_candidates_from_text(
    text: str, candidates: dict[str, int], *, source: str, base_score: int
) -> set[str]:
    """从 HTML/JS/纯文本中提取完整候选域名，并返回不完整 TLD 首字母。"""
    if not text:
        return set()

    partial_chars: set[str] = set()
    variants = [text, html.unescape(text)]
    variants.extend(_extract_literal_joined_chunks(text))
    variants.extend(_extract_origin_body_variants(text))

    for idx, content in enumerate(variants):
        variant_score = max(base_score - idx, 1)

        for match in _IKUUU_DOMAIN_RE.finditer(content):
            _add_domain_candidate(candidates, match.group(1), variant_score, source)

        for ext in re.findall(
            r"""['"]ikuuu['"]\s*\+\s*['"]\.([a-z]{1,12})""",
            content,
            re.IGNORECASE,
        ):
            ext = ext.lower()
            if len(ext) >= 2:
                _add_domain_candidate(candidates, f"ikuuu.{ext}", variant_score, source)
            else:
                partial_chars.add(ext)

        for ext in re.findall(r"""['"]uuu\.([a-z]{1,12})['"]""", content, re.IGNORECASE):
            ext = ext.lower()
            if len(ext) >= 2:
                _add_domain_candidate(candidates, f"ikuuu.{ext}", variant_score, source)
            else:
                partial_chars.add(ext)

    return {char for char in partial_chars if char}


async def _fetch_discovery_page(
    session: aiohttp.ClientSession, url: str
) -> tuple[str, str, str] | None:
    """获取域名公告页，返回原始 URL、最终 URL、HTML。"""
    if not await _ikuuu_url_resolves(url):
        return None

    try:
        async with session.get(
            url,
            headers={"User-Agent": _IKUUU_USER_AGENT},
            timeout=aiohttp.ClientTimeout(total=5, connect=3, sock_read=3),
            allow_redirects=True,
        ) as resp:
            text = await resp.text(errors="ignore")
            logger.debug(
                "ikuuu签到：域名发现入口 %s 返回 HTTP %s，最终地址 %s",
                url,
                resp.status,
                resp.url,
            )
            return url, str(resp.url), text
    except Exception as exc:  # noqa: BLE001
        logger.debug("ikuuu签到：域名发现入口 %s 访问失败：%s", url, exc)
        return None


async def _probe_domain(session: aiohttp.ClientSession, domain: str) -> _DomainProbeResult | None:
    """验证候选域名是否像真实 iKuuu 登录站点。"""
    started = perf_counter()
    login_url = f"https://{domain}/auth/login"
    if not await _ikuuu_host_resolves(domain, 443):
        return None

    try:
        async with session.get(
            login_url,
            headers={
                "User-Agent": _IKUUU_USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
            timeout=aiohttp.ClientTimeout(total=5, connect=3, sock_read=3),
            allow_redirects=True,
        ) as resp:
            text = await resp.text(errors="ignore")
            elapsed_ms = int((perf_counter() - started) * 1000)
            body_variants = [text, *_extract_origin_body_variants(text)]
            bodies = [variant.lower() for variant in body_variants if variant]
            final_domain = _normalize_ikuuu_domain(str(resp.url))

            if resp.status >= 500:
                return None

            has_login_form = any(
                ('id="email"' in body or 'name="email"' in body or "email" in body)
                and ('id="password"' in body or 'name="password"' in body or "password" in body)
                for body in bodies
            )
            is_domain_notice = any("ikuuuvpn" in body and "2019-2026" in body for body in bodies)

            if has_login_form:
                return _DomainProbeResult(domain, 100, elapsed_ms, "login-form")

            if final_domain == domain and not is_domain_notice and resp.status in {200, 301, 302}:
                return _DomainProbeResult(domain, 60, elapsed_ms, f"http-{resp.status}")

            if final_domain and final_domain != domain:
                return _DomainProbeResult(final_domain, 55, elapsed_ms, f"redirect:{domain}")

    except Exception as exc:  # noqa: BLE001
        logger.debug("ikuuu签到：候选域名 %s 探测失败：%s", domain, exc)
    return None


async def _probe_domains(
    session: aiohttp.ClientSession, candidates: dict[str, int]
) -> list[_DomainProbeResult]:
    """并发探测候选域名，按探测结果从优到劣排序。"""
    if not candidates:
        return []

    semaphore = asyncio.Semaphore(8)

    async def probe_one(domain: str) -> _DomainProbeResult | None:
        async with semaphore:
            result = await _probe_domain(session, domain)
            if result:
                result.score += min(candidates.get(result.domain, candidates.get(domain, 0)), 50)
                logger.debug(
                    "ikuuu签到：候选域名 %s 探测通过，分数=%d，耗时=%dms，原因=%s",
                    result.domain,
                    result.score,
                    result.elapsed_ms,
                    result.reason,
                )
            return result

    ordered_domains = sorted(candidates, key=lambda d: (-candidates[d], d))[:32]
    results = await asyncio.gather(*(probe_one(domain) for domain in ordered_domains))
    valid_results = [result for result in results if result is not None]
    valid_results.sort(key=lambda item: (-item.score, item.elapsed_ms, item.domain))
    return valid_results


async def _probe_recent_domains(session: aiohttp.ClientSession) -> str | None:
    """优先验证最近可用域名，成功时避免依赖公告页。"""
    primary_result = await _probe_domain(session, _IKUUU_PRIMARY_DOMAIN)
    if primary_result:
        logger.info(
            "ikuuu签到：使用主域名 %s（已验证，耗时 %dms）",
            primary_result.domain,
            primary_result.elapsed_ms,
        )
        return primary_result.domain

    fast_candidates = {
        domain: max(35 - idx, 1) for idx, domain in enumerate(_IKUUU_FAST_FALLBACK_DOMAINS)
    }
    probe_results = await _probe_domains(session, fast_candidates)
    if not probe_results:
        return None

    selected = probe_results[0].domain
    logger.info(
        "ikuuu签到：使用近期可用域名 %s（已验证，候选 %d 个，耗时 %dms）",
        selected,
        len(fast_candidates),
        probe_results[0].elapsed_ms,
    )
    return selected


async def _extract_ikuuu_domain() -> str | None:
    """从 ikuuu.club 自动提取可用域名（如 ikuuu.nl、ikuuu.fyi 等）

    ikuuu.club 页面使用混淆 JS 动态渲染域名列表，域名不在纯文本中，
    而是以字符串拼接方式藏在 JavaScript 源码里，例如：
      'ikuuu' + '.nl'       →  完整 TLD 可直接提取
      '://ik' + 'uuu.f' + 混淆函数()  →  TLD 被拆分，只能拿到首字母 'f'
    因此需要对原始 HTML 源码做多种模式匹配，对于只提取到首字母的情况，
    通过 HTTP 探测已知 TLD 候选列表来还原完整域名。

    流程：
    1. 访问 ikuuu.club（可能重定向或展示包含混淆 JS 的域名页面）
    2. 从最终 URL、原始 HTML/JS 源码中提取 ikuuu.xxx 格式的域名
    3. 对于只拿到 TLD 首字母的片段，通过 HTTP 探测补全
    4. 优先返回已验证可打开登录页的高分域名
    """
    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=8),
            connector=aiohttp.TCPConnector(limit=16),
        ) as session:
            scored_candidates: dict[str, int] = {}
            partial_chars: set[str] = set()

            cached_domain = _load_cached_ikuuu_domain()
            if cached_domain:
                cached_result = await _probe_domain(session, cached_domain)
                if cached_result:
                    logger.info(
                        "ikuuu签到：使用缓存域名 %s（已验证，耗时 %dms）",
                        cached_result.domain,
                        cached_result.elapsed_ms,
                    )
                    _save_cached_ikuuu_domain(cached_result.domain, "cache-verified")
                    return cached_result.domain
                logger.debug("ikuuu签到：缓存域名 %s 当前验证失败，将继续自动发现", cached_domain)

            recent_domain = await _probe_recent_domains(session)
            if recent_domain:
                _save_cached_ikuuu_domain(recent_domain, "recent")
                return recent_domain

            fetched_pages = await asyncio.gather(
                *(_fetch_discovery_page(session, url) for url in _IKUUU_DISCOVERY_URLS)
            )
            fetched_pages = [page for page in fetched_pages if page is not None]

            for source_url, final_url, raw_html in fetched_pages:
                _add_domain_candidate(scored_candidates, final_url, 70, f"redirect:{source_url}")
                partial_chars.update(
                    _extract_domain_candidates_from_text(
                        raw_html,
                        scored_candidates,
                        source=source_url,
                        base_score=60,
                    )
                )

                soup = BeautifulSoup(raw_html, "html.parser")
                partial_chars.update(
                    _extract_domain_candidates_from_text(
                        soup.get_text(" ", strip=True),
                        scored_candidates,
                        source=f"text:{source_url}",
                        base_score=45,
                    )
                )
                for a_tag in soup.find_all("a", href=True):
                    _add_domain_candidate(
                        scored_candidates, str(a_tag["href"]), 65, f"link:{source_url}"
                    )

            for domain in list(scored_candidates):
                tld = domain.split(".")[-1]
                if len(tld) == 1:
                    partial_chars.add(tld)

            for char in sorted(partial_chars):
                if any(domain.split(".")[-1].startswith(char) for domain in scored_candidates):
                    continue
                for tld in _IKUUU_TLD_CANDIDATES.get(char, []):
                    _add_domain_candidate(scored_candidates, f"ikuuu.{tld}", 25, f"partial:{char}")

            for domain in _IKUUU_RECENT_DOMAINS:
                _add_domain_candidate(scored_candidates, domain, 10, "recent")

            probe_results = await _probe_domains(session, scored_candidates)
            if probe_results:
                selected = probe_results[0].domain
                logger.info(
                    "ikuuu签到：自动发现域名 %s（已验证，候选 %d 个，耗时 %dms）",
                    selected,
                    len(scored_candidates),
                    probe_results[0].elapsed_ms,
                )
                _save_cached_ikuuu_domain(selected, "discovery")
                return selected

            extracted_domains = [
                domain
                for domain in sorted(scored_candidates, key=scored_candidates.get, reverse=True)
                if scored_candidates[domain] >= 40
            ]
            if extracted_domains:
                selected = extracted_domains[0]
                logger.warning(
                    "ikuuu签到：候选域名未能完成在线验证，回退使用解析分数最高的 %s（候选: %s）",
                    selected,
                    ", ".join(extracted_domains[:8]),
                )
                return selected

        logger.debug("ikuuu签到：本轮未能从 %s 提取或验证到可用域名", _IKUUU_DISCOVERY_URL)
        return None

    except Exception as exc:  # noqa: BLE001
        logger.error("ikuuu签到：自动提取域名失败：%s", exc, exc_info=True)
        return None


async def _extract_ikuuu_domain_with_retry() -> str | None:
    """最多尝试 5 次自动发现 ikuuu 可用域名。"""
    for attempt in range(1, _IKUUU_MAX_RETRIES + 1):
        if attempt > 1:
            logger.info("ikuuu签到：第 %d/%d 次重试自动发现域名", attempt, _IKUUU_MAX_RETRIES)

        domain = await _extract_ikuuu_domain()
        if domain:
            if attempt > 1:
                logger.info("ikuuu签到：域名发现重试成功：%s", domain)
            return domain

        if attempt < _IKUUU_MAX_RETRIES:
            logger.info(
                "ikuuu签到：第 %d/%d 次域名发现失败，%d 秒后重试",
                attempt,
                _IKUUU_MAX_RETRIES,
                _IKUUU_RETRY_DELAY_SECONDS,
            )
            await asyncio.sleep(_IKUUU_RETRY_DELAY_SECONDS)

    logger.error("ikuuu签到：连续 %d 次域名发现失败", _IKUUU_MAX_RETRIES)
    return None


@dataclass
class CheckinConfig:
    """签到相关配置（可表示单账号或用于多账号时的公共字段）"""

    enable: bool
    domain: str  # 自动发现的域名，如 ikuuu.nl
    email: str
    password: str
    time: str
    accounts: list[dict]  # 多账号列表 [{"email": str, "password": str}, ...]，执行时优先遍历此列表
    push_channels: list[str]  # 推送通道名称列表，为空时使用全部通道

    @property
    def login_url(self) -> str:
        """登录地址（由域名自动构建）"""
        return f"https://{self.domain}/auth/login"

    @property
    def checkin_url(self) -> str:
        """签到接口地址（由域名自动构建）"""
        return f"https://{self.domain}/user/checkin"

    @property
    def user_page_url(self) -> str:
        """用户信息页地址（由域名自动构建）"""
        return f"https://{self.domain}/user"

    @classmethod
    def from_app_config(cls, config: AppConfig, domain: str) -> CheckinConfig:
        # 多账号优先：checkin_accounts 非空时使用，否则用单账号组一条
        if getattr(config, "checkin_accounts", None):
            accounts = [
                {
                    "email": str(a.get("email", "")).strip(),
                    "password": str(a.get("password", "")).strip(),
                }
                for a in config.checkin_accounts
                if isinstance(a, dict)
            ]
        else:
            accounts = [
                {
                    "email": (config.checkin_email or "").strip(),
                    "password": (config.checkin_password or "").strip(),
                }
            ]
        first = accounts[0] if accounts else {"email": "", "password": ""}
        push_channels: list[str] = getattr(config, "checkin_push_channels", None) or []
        return cls(
            enable=config.checkin_enable,
            domain=domain,
            email=first.get("email", ""),
            password=first.get("password", ""),
            time=config.checkin_time.strip() or "08:00",
            accounts=accounts,
            push_channels=push_channels,
        )

    def with_account(self, email: str, password: str) -> CheckinConfig:
        """返回仅替换邮箱/密码的副本，用于单账号登录与推送。"""
        return CheckinConfig(
            enable=self.enable,
            domain=self.domain,
            email=email,
            password=password,
            time=self.time,
            accounts=self.accounts,
            push_channels=self.push_channels,
        )

    def validate(self) -> bool:
        """校验配置是否完整"""
        if not self.enable:
            logger.info("ikuuu签到未启用，跳过执行；请在 config.yml 中设置 checkin.enable: true")
            return False

        missing_fields: list[str] = []
        if not self.domain:
            missing_fields.append("域名（自动发现失败）")
        if not self.accounts:
            missing_fields.append("checkin.accounts 或 checkin.email/password")
        else:
            valid_accounts = [a for a in self.accounts if a.get("email") and a.get("password")]
            if not valid_accounts:
                missing_fields.append("至少一个账号需包含 checkin.email 与 checkin.password")

        if missing_fields:
            logger.error("ikuuu签到配置不完整，已跳过执行，缺少字段: %s", ", ".join(missing_fields))
            return False

        return True


def _mask_email(email: str) -> str:
    """对邮箱做部分脱敏，用于日志输出"""
    if "@" not in email:
        return email
    name, domain = email.split("@", 1)
    if len(name) <= 3:
        masked_name = name[0] + "***" if name else "***"
    else:
        masked_name = name[:3] + "***"
    return f"{masked_name}@{domain}"


class _IkuuuBrowserUnavailableError(RuntimeError):
    """浏览器或 WebDriver 环境缺失，重试域名无法恢复。"""


def _binary_version(path: str) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            [path, "--version"],
            capture_output=True,
            check=False,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)

    output = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())
    if result.returncode != 0:
        return False, output or f"exit code {result.returncode}"
    return True, output


def _major_version_from_text(text: str) -> int | None:
    match = re.search(r"\b(\d+)\.", text)
    return int(match.group(1)) if match else None


def _binary_major_version(path: str | None) -> int | None:
    if not path:
        return None
    ok, detail = _binary_version(path)
    if not ok:
        return None
    return _major_version_from_text(detail)


def _log_unusable_browser_binary(kind: str, path: str, detail: str, *, warning: bool) -> None:
    if warning:
        logger.warning("ikuuu签到：忽略不可用 %s: %s (%s)", kind, path, detail)
    else:
        logger.debug("ikuuu签到：忽略不可用 %s: %s (%s)", kind, path, detail)


def _is_usable_browser_binary(path: str, *, warning: bool = False) -> bool:
    ok, detail = _binary_version(path)
    if not ok:
        _log_unusable_browser_binary("Chrome/Chromium", path, detail, warning=warning)
        return False
    logger.debug("ikuuu签到：检测到 Chrome/Chromium: %s (%s)", path, detail.splitlines()[0])
    return True


def _is_usable_chromedriver(
    path: str, *, browser_major: int | None = None, warning: bool = False
) -> bool:
    ok, detail = _binary_version(path)
    if not ok:
        _log_unusable_browser_binary("chromedriver", path, detail, warning=warning)
        return False

    driver_major = _major_version_from_text(detail)
    if browser_major and driver_major and driver_major != browser_major:
        message = f"{detail.splitlines()[0]}，与浏览器主版本 {browser_major} 不匹配"
        _log_unusable_browser_binary("chromedriver", path, message, warning=warning)
        return False

    logger.debug("ikuuu签到：检测到 chromedriver: %s (%s)", path, detail.splitlines()[0])
    return True


def _is_chromedriver_version_mismatch(exc: BaseException) -> bool:
    msg = str(exc)
    return "only supports Chrome version" in msg and "Current browser version" in msg


def _is_webdriver_environment_error(exc: BaseException) -> bool:
    msg = str(exc)
    markers = (
        "unexpectedly exited",
        "Unable to obtain driver",
        "cannot find Chrome binary",
        "requires the chromium snap",
        "snap install chromium",
    )
    return any(marker in msg for marker in markers)


def _clear_chromedriver_cache() -> None:
    cache = Path.home() / ".cache" / "selenium" / "chromedriver"
    if cache.is_dir():
        shutil.rmtree(cache, ignore_errors=True)
        logger.info("ikuuu签到：已清除 Selenium chromedriver 缓存: %s", cache)


def _resolve_chromedriver_via_manager(chrome_bin: str | None) -> str | None:
    """通过 Selenium Manager 获取与当前 Chrome 主版本匹配的 chromedriver。"""
    try:
        from selenium.webdriver.common.selenium_manager import SeleniumManager
    except ModuleNotFoundError:
        return None

    args = ["--browser", "chrome"]
    if chrome_bin:
        args.extend(["--browser-path", chrome_bin])
    try:
        output = SeleniumManager().binary_paths(args)
        path = output.get("driver_path", "")
        if path and os.path.isfile(path):
            logger.debug("ikuuu签到：Selenium Manager 选用 chromedriver: %s", path)
            return path
    except Exception as exc:  # noqa: BLE001
        logger.warning("ikuuu签到：Selenium Manager 获取 chromedriver 失败: %s", exc)
    return None


def _default_chrome_binary() -> str | None:
    candidates = [
        os.environ.get("CHROME_BIN", "").strip(),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
    ]
    for path in candidates:
        if path and os.path.isfile(path) and _is_usable_browser_binary(path):
            return path
    return None


def _default_chromedriver_path(
    browser_bin: str | None = None,
    *,
    include_auto_candidates: bool = True,
) -> str | None:
    browser_major = _binary_major_version(browser_bin)
    configured = os.environ.get("CHROMEDRIVER_PATH", "").strip()
    if configured:
        if os.path.exists(configured) and _is_usable_chromedriver(
            configured,
            browser_major=browser_major,
            warning=True,
        ):
            return configured
        logger.warning("ikuuu签到：配置的 CHROMEDRIVER_PATH 不可用，将尝试 Selenium Manager: %s", configured)

    if not include_auto_candidates:
        return None

    candidates = (
        shutil.which("chromedriver") or "",
        "/usr/bin/chromedriver",
        "/usr/local/bin/chromedriver",
        "/usr/lib/chromium/chromedriver",
        "/usr/lib/chromium-browser/chromedriver",
    )
    seen: set[str] = set()
    for path in candidates:
        if not path or path in seen:
            continue
        seen.add(path)
        if os.path.exists(path) and _is_usable_chromedriver(
            path,
            browser_major=browser_major,
            warning=False,
        ):
            return path
    return None


def _create_ikuuu_webdriver(webdriver, service_cls, options, chrome_bin: str | None):
    driver_path = _default_chromedriver_path(chrome_bin, include_auto_candidates=False)
    if driver_path:
        try:
            return webdriver.Chrome(service=service_cls(driver_path), options=options)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "ikuuu签到：chromedriver %s 启动失败，将尝试 Selenium Manager: %s",
                driver_path,
                exc,
            )
            if _is_chromedriver_version_mismatch(exc):
                _clear_chromedriver_cache()

    for attempt in range(2):
        resolved = _resolve_chromedriver_via_manager(chrome_bin)
        try:
            if resolved:
                return webdriver.Chrome(service=service_cls(resolved), options=options)
            return webdriver.Chrome(options=options)
        except Exception as exc:  # noqa: BLE001
            if attempt == 0 and _is_chromedriver_version_mismatch(exc):
                logger.warning("ikuuu签到：chromedriver 与 Chrome 版本不匹配，清除缓存后重试: %s", exc)
                _clear_chromedriver_cache()
                continue
            if _is_webdriver_environment_error(exc):
                raise _IkuuuBrowserUnavailableError(f"Chrome WebDriver 初始化失败: {exc}") from exc
            raise

    driver_path = _default_chromedriver_path(chrome_bin, include_auto_candidates=True)
    if driver_path:
        try:
            return webdriver.Chrome(service=service_cls(driver_path), options=options)
        except Exception as exc:  # noqa: BLE001
            raise _IkuuuBrowserUnavailableError(f"Chrome WebDriver 初始化失败: {exc}") from exc

    raise _IkuuuBrowserUnavailableError("无法初始化 Chrome WebDriver")


def _login_and_get_cookie_sync(cfg: CheckinConfig) -> str | None:
    """通过浏览器登录站点并获取 Cookie。"""
    logger.debug("ikuuu签到：使用账号 %s 登录", _mask_email(cfg.email))

    try:
        from selenium import webdriver
        from selenium.common.exceptions import TimeoutException
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions
        from selenium.webdriver.support.ui import WebDriverWait
    except ModuleNotFoundError as exc:
        logger.error("ikuuu签到：缺少 Selenium 依赖，请使用 Docker full 镜像运行")
        logger.debug("ikuuu签到：Selenium 导入失败：%s", exc)
        return None

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1280,800")
    options.add_argument("--lang=zh-CN")
    options.add_argument(f"--user-agent={_IKUUU_USER_AGENT}")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    chrome_bin = _default_chrome_binary()
    if chrome_bin:
        options.binary_location = chrome_bin
    else:
        raise _IkuuuBrowserUnavailableError(
            "未找到 Chrome/Chromium 浏览器，请安装 google-chrome-stable 或 chromium 后重试"
        )

    driver = None

    try:
        driver = _create_ikuuu_webdriver(webdriver, Service, options, chrome_bin)

        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": """
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                """
            },
        )

        wait = WebDriverWait(driver, 20)
        logger.debug("ikuuu签到：打开登录页 %s", cfg.login_url)
        driver.get(cfg.login_url)

        email_input = wait.until(
            expected_conditions.presence_of_element_located((By.CSS_SELECTOR, "#email"))
        )
        password_input = wait.until(
            expected_conditions.presence_of_element_located((By.CSS_SELECTOR, "#password"))
        )
        email_input.clear()
        email_input.send_keys(cfg.email)
        password_input.clear()
        password_input.send_keys(cfg.password)

        try:
            verify_button = WebDriverWait(driver, 5).until(
                expected_conditions.element_to_be_clickable((By.CSS_SELECTOR, ".geetest_btn_click"))
            )
            verify_button.click()
            logger.debug("ikuuu签到：已点击验证按钮")
        except TimeoutException:
            logger.debug("ikuuu签到：未发现验证按钮，继续提交登录")

        time.sleep(2)
        wait.until(
            expected_conditions.element_to_be_clickable((By.CSS_SELECTOR, 'button[type="submit"]'))
        ).click()
        time.sleep(5)

        cookies = driver.get_cookies()
        cookie_string = "; ".join(
            f"{cookie['name']}={cookie['value']}"
            for cookie in cookies
            if cookie.get("name") and cookie.get("value") is not None
        )
        if not cookie_string:
            logger.error("ikuuu签到：浏览器登录后未获取到 Cookie")
            return None

        logger.debug("ikuuu签到：浏览器登录完成，已获取 Cookie")
        return cookie_string

    except _IkuuuBrowserUnavailableError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("ikuuu签到：登录过程中发生错误：%s", exc, exc_info=True)
        return None
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:  # noqa: BLE001
                pass


async def _login_and_get_cookie(session: aiohttp.ClientSession, cfg: CheckinConfig) -> str | None:
    """登录站点并获取 Cookie，失败时最多重试 5 次。session 参数保留给现有调用链。"""
    _ = session
    masked_email = _mask_email(cfg.email)

    for attempt in range(1, _IKUUU_MAX_RETRIES + 1):
        if attempt > 1:
            logger.info(
                "ikuuu签到：账号 %s 第 %d/%d 次重试登录（域名：%s）",
                masked_email,
                attempt,
                _IKUUU_MAX_RETRIES,
                cfg.domain,
            )

        try:
            cookie = await asyncio.to_thread(_login_and_get_cookie_sync, cfg)
        except _IkuuuBrowserUnavailableError as exc:
            logger.error(
                "ikuuu签到：账号 %s 浏览器环境不可用，跳过后续登录重试：%s",
                masked_email,
                exc,
            )
            return None

        if cookie:
            if attempt > 1:
                logger.info("ikuuu签到：账号 %s 登录重试成功", masked_email)
            return cookie

        if attempt >= _IKUUU_MAX_RETRIES:
            break

        logger.warning(
            "ikuuu签到：账号 %s 第 %d/%d 次登录失败，准备重新发现域名后重试",
            masked_email,
            attempt,
            _IKUUU_MAX_RETRIES,
        )
        new_domain = await _extract_ikuuu_domain_with_retry()
        if new_domain and new_domain != cfg.domain:
            logger.info("ikuuu签到：登录失败后切换域名：%s -> %s", cfg.domain, new_domain)
            cfg.domain = new_domain

        await asyncio.sleep(_IKUUU_RETRY_DELAY_SECONDS)

    logger.error("ikuuu签到：账号 %s 连续 %d 次登录失败", masked_email, _IKUUU_MAX_RETRIES)
    return None


async def _checkin(
    session: aiohttp.ClientSession, cfg: CheckinConfig, cookie: str
) -> tuple[bool, str]:
    """执行签到"""
    headers = {
        "User-Agent": _IKUUU_USER_AGENT,
        "Origin": cfg.checkin_url.rsplit("/user", 1)[0] if "/user" in cfg.checkin_url else "",
        "Referer": (
            cfg.checkin_url.rsplit("/checkin", 1)[0] if "/checkin" in cfg.checkin_url else ""
        ),
        "Cookie": cookie,
    }

    try:
        async with session.post(cfg.checkin_url, headers=headers) as resp:
            try:
                data: dict[str, Any] = await resp.json(content_type=None)
            except Exception as exc:  # noqa: BLE001
                logger.error("ikuuu签到：解析签到响应失败：%s", exc, exc_info=True)
                return False, "解析签到响应失败"

        msg = str(data.get("msg") or "未知结果")
        if data.get("ret") == 1:
            logger.info("ikuuu签到：✅ 签到成功：%s", msg)
            return True, msg

        if "已经签到" in msg or "已签到" in msg:
            logger.info("ikuuu签到：ℹ️ 今日已签到：%s", msg)
            return True, msg

        logger.error("ikuuu签到：❌ 签到失败：%s", msg)
        return False, msg

    except Exception as exc:  # noqa: BLE001
        logger.error("ikuuu签到：签到请求失败：%s", exc, exc_info=True)
        return False, f"签到请求失败：{exc}"


async def _get_user_traffic(
    session: aiohttp.ClientSession, cfg: CheckinConfig, cookie: str
) -> str | None:
    """获取并输出流量信息，返回用于推送的流量摘要文本，失败则返回 None。"""

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0"
        ),
        "Referer": cfg.user_page_url,
        "Cookie": cookie,
    }

    try:
        async with session.get(cfg.user_page_url, headers=headers) as resp:
            text = await resp.text()

        # 部分站点将正文放在 script 的 base64(originBody) 中，需先解码再解析
        html_to_parse = text
        origin_body_match = re.search(
            r'originBody\s*=\s*"([A-Za-z0-9+/=]+)"',
            text,
            re.DOTALL,
        )
        if origin_body_match:
            try:
                decoded = base64.b64decode(origin_body_match.group(1)).decode("utf-8")
                if "card-statistic-2" in decoded or "剩余流量" in decoded:
                    html_to_parse = decoded
            except Exception:  # 解码失败则仍用原始 HTML
                pass

        soup = BeautifulSoup(html_to_parse, "html.parser")

        traffic_cards = soup.find_all("div", class_="card-statistic-2")
        if not traffic_cards:
            logger.debug("ikuuu签到：未找到流量统计信息")
            return None

        lines: list[str] = []
        for card in traffic_cards:
            header = card.find("h4")
            if header and "剩余流量" in header.text:
                body = card.find("div", class_="card-body")
                if body:
                    remaining_traffic = re.sub(r"\s+", " ", body.get_text(strip=True))
                    logger.debug("ikuuu签到：剩余流量 %s", remaining_traffic)
                    lines.append(f"📈 剩余流量：{remaining_traffic}")

                stats = card.find("div", class_="card-stats-title")
                if stats:
                    today_used_text = re.sub(r"\s+", " ", stats.get_text(strip=True))
                    match = re.search(r":\s*(.+)", today_used_text)
                    if match:
                        today_used = match.group(1).strip()
                        logger.debug("ikuuu签到：今日已用 %s", today_used)
                        lines.append(f"📊 今日已用：{today_used}")
                    else:
                        logger.debug("ikuuu签到：今日使用 %s", today_used_text)
                        lines.append(f"📊 今日使用情况：{today_used_text}")

        return "\n".join(lines) if lines else None

    except Exception as exc:  # noqa: BLE001
        logger.error("ikuuu签到：获取流量信息失败：%s", exc, exc_info=True)
        return None


async def run_checkin_once() -> bool:
    """执行一次完整的 iKuuu/SSPanel 签到流程（支持多账号：登录 → 签到 → 获取流量信息 → 推送）"""
    app_config = get_config(reload=True)

    if not app_config.checkin_enable:
        logger.info("ikuuu签到未启用，跳过执行；请在 config.yml 中设置 checkin.enable: true")
        return TASK_FAILED

    # 自动发现 ikuuu 可用域名
    logger.info("ikuuu签到：正在自动发现可用域名...")
    domain = await _extract_ikuuu_domain_with_retry()
    if not domain:
        logger.error("ikuuu签到：无法自动发现可用域名，跳过本次执行")
        return TASK_FAILED

    cfg = CheckinConfig.from_app_config(app_config, domain=domain)

    if not cfg.validate():
        return TASK_FAILED

    valid_accounts = [a for a in cfg.accounts if a.get("email") and a.get("password")]
    logger.info("ikuuu签到：开始执行（共 %d 个账号）", len(valid_accounts))

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
        push_manager: UnifiedPushManager | None = await build_push_manager(
            app_config.push_channel_list,
            session,
            logger,
            init_fail_prefix="ikuuu签到：",
            channel_names=cfg.push_channels if cfg.push_channels else None,
        )
        if push_manager is None:
            logger.warning("ikuuu签到：未配置任何推送通道，将仅在日志中记录结果")

        success_count = 0
        for idx, account in enumerate(valid_accounts):
            cfg_one = cfg.with_account(account["email"], account["password"])
            logger.debug("ikuuu签到：正在处理第 %d/%d 个账号", idx + 1, len(valid_accounts))

            cookie = await _login_and_get_cookie(session, cfg_one)
            if not cookie:
                logger.error("ikuuu签到：❌ 账号 %s 登录失败", _mask_email(cfg_one.email))
                await _send_checkin_push(
                    push_manager,
                    title="ikuuu签到失败：登录失败",
                    msg="登录失败，无法获取 Cookie，请检查账号、密码或站点状态。",
                    success=False,
                    cfg=cfg_one,
                )
                continue

            _save_cached_ikuuu_domain(cfg_one.domain, "login")
            ok, checkin_msg = await _checkin(session, cfg_one, cookie)
            if ok:
                success_count += 1
            traffic_info = await _get_user_traffic(session, cfg_one, cookie)
            title = "ikuuu签到成功" if ok else "ikuuu签到失败"
            await _send_checkin_push(
                push_manager,
                title=title,
                msg=checkin_msg,
                success=ok,
                cfg=cfg_one,
                traffic_info=traffic_info,
            )

        if push_manager is not None:
            await push_manager.close()

    logger.info("ikuuu签到：结束（成功 %d/%d 个账号）", success_count, len(valid_accounts))
    return TASK_SUCCESS if success_count > 0 else TASK_FAILED


async def _send_checkin_push(
    push_manager: UnifiedPushManager | None,
    title: str,
    msg: str,
    success: bool,
    cfg: CheckinConfig,
    traffic_info: str | None = None,
) -> None:
    """通过统一推送通道发送签到结果，可选附带流量信息。"""
    if push_manager is None:
        return

    # 免打扰时段内只记录日志，不推送
    app_cfg = get_config()
    if is_in_quiet_hours(app_cfg):
        logger.debug("ikuuu签到：免打扰时段，不发送推送")
        return

    masked_email = _mask_email(cfg.email)
    status_emoji = "✅" if success else "❌"
    description = f"{status_emoji} 账号：{masked_email}\n" f"{msg}\n"
    if traffic_info:
        description += f"\n【流量信息】\n{traffic_info}\n"
    description += (
        f"\n当前域名：{cfg.domain}\n" f"登录地址：{cfg.login_url}\n" f"签到接口：{cfg.checkin_url}"
    )

    try:
        await push_manager.send_news(
            title=f"{title}",
            description=description,
            to_url=cfg.user_page_url,
            picurl="https://cn.bing.com/th?id=OHR.DubrovnikHarbor_ZH-CN8590217905_1920x1080.jpg",
            btntxt="查看账户",
            event_type="checkin_ikuuu",
            event_data={
                "success": success,
                "account": masked_email,
                "message": msg,
                "has_traffic_info": bool(traffic_info),
                "domain": cfg.domain,
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("ikuuu签到：发送签到结果推送失败：%s", exc, exc_info=True)


def _get_checkin_trigger_kwargs(config: AppConfig) -> dict:
    """供注册表与配置热重载使用。"""
    hour, minute = parse_checkin_time(config.checkin_time)
    return {"minute": minute, "hour": hour}


register_task(
    "ikuuu_checkin",
    run_checkin_once,
    _get_checkin_trigger_kwargs,
    description="ikuuu 每日签到",
)
