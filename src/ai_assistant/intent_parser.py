"""AI 助手 - 语义意图解析：识别「关闭XX监控」「开启XX监控」「删除XX主播Y」等可执行操作"""

import re
from typing import NamedTuple

# 平台 -> list_key 映射（监控列表字段）
PLATFORM_LIST_KEYS = {
    "weibo": "uids",
    "huya": "rooms",
    "bilibili": "uids",
    "douyin": "douyin_ids",
    "douyu": "rooms",
    "xhs": "profile_ids",
}

# 平台显示名/别名 -> config.yml 中的 section key
PLATFORM_TO_CONFIG_KEY = {
    "微博": "weibo",
    "weibo": "weibo",
    "虎牙": "huya",
    "huya": "huya",
    "哔哩哔哩": "bilibili",
    "b站": "bilibili",
    "bilibili": "bilibili",
    "抖音": "douyin",
    "douyin": "douyin",
    "斗鱼": "douyu",
    "douyu": "douyu",
    "小红书": "xhs",
    "xhs": "xhs",
}

CONFIG_KEY_TO_DISPLAY = {
    "weibo": "微博",
    "huya": "虎牙",
    "bilibili": "哔哩哔哩",
    "douyin": "抖音",
    "douyu": "斗鱼",
    "xhs": "小红书",
}


class ToggleMonitorIntent(NamedTuple):
    """开关监控意图"""
    platform_key: str
    enable: bool
    display_name: str


def parse_toggle_monitor_intent(message: str) -> ToggleMonitorIntent | None:
    """
    解析用户消息，识别「关闭XX监控」「开启XX监控」类意图。
    返回 ToggleMonitorIntent 或 None（未识别到可执行意图）。
    """
    msg = message.strip()
    if not msg:
        return None

    # 匹配：关闭/开启 + [平台名] + 监控
    # 支持变体：关闭抖音监控、关闭抖音、停用抖音监控、把抖音关掉、开启抖音监控 等
    close_patterns = [
        r"关闭\s*([^\s]+)\s*监控",
        r"关闭\s*([^\s]+)(?:\s|$)",
        r"停用\s*([^\s]+)\s*监控",
        r"停用\s*([^\s]+)(?:\s|$)",
        r"关掉\s*([^\s]+)\s*监控",
        r"关掉\s*([^\s]+)(?:\s|$)",
        r"禁用\s*([^\s]+)\s*监控",
        r"把\s*([^\s]+)\s*关(?:掉|闭)",
        r"关(?:掉|闭)\s*([^\s]+)\s*监控",
    ]
    open_patterns = [
        r"开启\s*([^\s]+)\s*监控",
        r"开启\s*([^\s]+)(?:\s|$)",
        r"启用\s*([^\s]+)\s*监控",
        r"启用\s*([^\s]+)(?:\s|$)",
        r"打开\s*([^\s]+)\s*监控",
    ]

    for pat in close_patterns:
        m = re.search(pat, msg)
        if m:
            platform_raw = m.group(1).strip().lower()
            key = _resolve_platform(platform_raw)
            if key:
                return ToggleMonitorIntent(
                    platform_key=key,
                    enable=False,
                    display_name=CONFIG_KEY_TO_DISPLAY.get(key, key),
                )

    for pat in open_patterns:
        m = re.search(pat, msg)
        if m:
            platform_raw = m.group(1).strip().lower()
            key = _resolve_platform(platform_raw)
            if key:
                return ToggleMonitorIntent(
                    platform_key=key,
                    enable=True,
                    display_name=CONFIG_KEY_TO_DISPLAY.get(key, key),
                )

    return None


class ConfigPatchIntent(NamedTuple):
    """配置列表增删意图"""
    platform_key: str
    list_key: str
    operation: str  # add | remove
    value: str
    display_name: str


def parse_config_patch_intent(message: str) -> ConfigPatchIntent | None:
    """
    解析「删除虎牙主播100」「添加虎牙房间200」「移除B站用户xxx」类意图。
    返回 ConfigPatchIntent 或 None。
    """
    msg = message.strip()
    if not msg or len(msg) < 5:
        return None

    # 删除/移除 模式：(pattern, platform_key)
    remove_rules = [
        (r"(?:删除|移除|去掉)\s*(?:虎牙|huya)\s*(?:主播|房间)?\s*(\S+)", "huya"),
        (r"(?:删除|移除|去掉)\s*(?:斗鱼|douyu)\s*(?:主播|房间)?\s*(\S+)", "douyu"),
        (r"(?:删除|移除|去掉)\s*(?:微博|weibo)\s*(?:用户|uid)?\s*(\S+)", "weibo"),
        (r"(?:删除|移除|去掉)\s*(?:哔哩哔哩|b站|bilibili)\s*(?:用户|uid)?\s*(\S+)", "bilibili"),
        (r"(?:删除|移除|去掉)\s*(?:抖音|douyin)\s*(?:主播|号)?\s*(\S+)", "douyin"),
        (r"(?:删除|移除|去掉)\s*(?:小红书|xhs)\s*(?:用户|profile)?\s*(\S+)", "xhs"),
        (r"(?:虎牙|huya)\s*(?:删除|移除)\s*(\S+)", "huya"),
        (r"(?:删除|移除)\s*虎牙主播\s*(\S+)", "huya"),
    ]
    for pat, platform_key in remove_rules:
        m = re.search(pat, msg, re.IGNORECASE)
        if m:
            list_key = PLATFORM_LIST_KEYS.get(platform_key)
            if list_key:
                value = m.group(1).strip().rstrip("。,.!?")
                return ConfigPatchIntent(
                    platform_key=platform_key,
                    list_key=list_key,
                    operation="remove",
                    value=value,
                    display_name=CONFIG_KEY_TO_DISPLAY.get(platform_key, platform_key),
                )

    # 添加/加入 模式
    add_rules = [
        (r"(?:添加|加入|增加)\s*(?:虎牙|huya)\s*(?:主播|房间)?\s*(\S+)", "huya"),
        (r"(?:添加|加入|增加)\s*(?:斗鱼|douyu)\s*(?:主播|房间)?\s*(\S+)", "douyu"),
        (r"(?:添加|加入|增加)\s*(?:微博|weibo)\s*(?:用户|uid)?\s*(\S+)", "weibo"),
        (r"(?:添加|加入|增加)\s*(?:哔哩哔哩|b站|bilibili)\s*(?:用户|uid)?\s*(\S+)", "bilibili"),
        (r"(?:添加|加入|增加)\s*(?:抖音|douyin)\s*(?:主播|号)?\s*(\S+)", "douyin"),
        (r"(?:添加|加入|增加)\s*(?:小红书|xhs)\s*(?:用户|profile)?\s*(\S+)", "xhs"),
    ]
    for pat, platform_key in add_rules:
        m = re.search(pat, msg, re.IGNORECASE)
        if m:
            list_key = PLATFORM_LIST_KEYS.get(platform_key)
            if list_key:
                value = m.group(1).strip().rstrip("。,.!?")
                return ConfigPatchIntent(
                    platform_key=platform_key,
                    list_key=list_key,
                    operation="add",
                    value=value,
                    display_name=CONFIG_KEY_TO_DISPLAY.get(platform_key, platform_key),
                )

    return None


def _resolve_platform(raw: str) -> str | None:
    """将用户输入的平台名解析为 config 的 section key"""
    raw = raw.strip().lower()
    # 直接匹配
    for display, key in PLATFORM_TO_CONFIG_KEY.items():
        if display.lower() == raw or key == raw:
            return key
    # 部分匹配（避免「抖音监控」只取到「抖音」）
    if "微博" in raw or raw == "wb":
        return "weibo"
    if "虎牙" in raw or raw == "hy":
        return "huya"
    if "哔哩" in raw or "b站" in raw or raw in ("blbl", "bilibili"):
        return "bilibili"
    if "抖音" in raw or raw == "dy":
        return "douyin"
    if "斗鱼" in raw or raw == "douyu":
        return "douyu"
    if "小红书" in raw or raw in ("xhs", "xhsh"):
        return "xhs"
    return None
