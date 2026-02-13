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

# 支持开关的配置节（监控 + 定时任务等）：显示名/别名 -> section_key
TOGGLE_SECTION_NAMES = {
    # 监控（与 PLATFORM 重复的用 CONFIG_KEY_TO_DISPLAY）
    "微博": "weibo", "weibo": "weibo",
    "虎牙": "huya", "huya": "huya",
    "哔哩哔哩": "bilibili", "b站": "bilibili", "bilibili": "bilibili",
    "抖音": "douyin", "douyin": "douyin",
    "斗鱼": "douyu", "douyu": "douyu",
    "小红书": "xhs", "xhs": "xhs",
    # 定时任务
    "超话": "weibo_chaohua", "超话签到": "weibo_chaohua", "微博超话": "weibo_chaohua",
    "ikuuu": "checkin", "checkin": "checkin", "签到": "checkin",
    "贴吧": "tieba", "百度贴吧": "tieba", "tieba": "tieba",
    "雨云": "rainyun", "rainyun": "rainyun", "雨云签到": "rainyun",
    "阿里云盘": "aliyun", "aliyun": "aliyun", "阿里云盘签到": "aliyun",
    "什么值得买": "smzdm", "值得买": "smzdm", "smzdm": "smzdm",
    "夸克": "kuake", "kuake": "kuake", "夸克签到": "kuake",
    "天气": "weather", "weather": "weather", "天气推送": "weather",
    "日志清理": "log_cleanup", "log_cleanup": "log_cleanup",
    "免打扰": "quiet_hours", "quiet_hours": "quiet_hours",
}

TOGGLE_SECTION_TO_DISPLAY = {
    "weibo": "微博", "huya": "虎牙", "bilibili": "哔哩哔哩", "douyin": "抖音", "douyu": "斗鱼", "xhs": "小红书",
    "weibo_chaohua": "微博超话签到", "checkin": "iKuuu 签到", "tieba": "百度贴吧签到", "rainyun": "雨云签到",
    "aliyun": "阿里云盘签到", "smzdm": "什么值得买签到", "kuake": "夸克签到", "weather": "天气推送",
    "log_cleanup": "日志清理", "quiet_hours": "免打扰",
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

    def _resolve_section(raw: str) -> str | None:
        r = raw.strip()
        # 先尝试监控平台
        key = _resolve_platform(r)
        if key:
            return key
        # 再尝试任务/通用节（支持「超话签到」「免打扰」等）
        for name, sec in TOGGLE_SECTION_NAMES.items():
            if name in r or r in name or (isinstance(r, str) and r.lower() == str(name).lower()):
                return sec
        return None

    for pat in close_patterns:
        m = re.search(pat, msg)
        if m:
            raw = m.group(1).strip()
            key = _resolve_section(raw) or TOGGLE_SECTION_NAMES.get(raw) or TOGGLE_SECTION_NAMES.get(raw.lower())
            if key:
                return ToggleMonitorIntent(
                    platform_key=key,
                    enable=False,
                    display_name=TOGGLE_SECTION_TO_DISPLAY.get(key, CONFIG_KEY_TO_DISPLAY.get(key, key)),
                )

    for pat in open_patterns:
        m = re.search(pat, msg)
        if m:
            raw = m.group(1).strip()
            key = _resolve_section(raw) or TOGGLE_SECTION_NAMES.get(raw) or TOGGLE_SECTION_NAMES.get(raw.lower())
            if key:
                return ToggleMonitorIntent(
                    platform_key=key,
                    enable=True,
                    display_name=TOGGLE_SECTION_TO_DISPLAY.get(key, CONFIG_KEY_TO_DISPLAY.get(key, key)),
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


class ConfigFieldIntent(NamedTuple):
    """修改标量配置意图（监控间隔、并发数、执行时间等）"""
    section_key: str
    field_key: str
    value: int | str  # int 或 "HH:MM" 时间字符串
    display_name: str


def _resolve_section_for_field(raw: str) -> str | None:
    """解析配置节 key，支持监控平台和任务名"""
    key = _resolve_platform(raw)
    if key:
        return key
    return TOGGLE_SECTION_NAMES.get(raw) or TOGGLE_SECTION_NAMES.get(raw.strip().lower())


def parse_config_field_intent(message: str) -> ConfigFieldIntent | None:
    """
    解析各类标量配置修改意图：
    - 监控间隔：虎牙监控间隔改成70秒
    - 并发数：虎牙并发改为5
    - 执行时间：超话签到时间改为23:00、免打扰22点到8点
    - 日志保留：日志保留7天
    返回 ConfigFieldIntent 或 None。
    """
    msg = message.strip()
    if not msg or len(msg) < 5:
        return None

    # 1. 监控间隔 monitor_interval_seconds
    interval_patterns = [
        r"(虎牙|huya|微博|weibo|哔哩哔哩|b站|bilibili|抖音|douyin|斗鱼|douyu|小红书|xhs)\s*监控\s*(?:间隔|配置)\s*(?:为|改成|改为|设为|修改为)\s*(\d+)\s*秒?",
        r"把\s*(虎牙|huya|微博|weibo)\s*监控\s*(?:间隔|配置)\s*(?:改为|改成)\s*(\d+)\s*秒?",
        r"(虎牙|huya|微博|weibo)\s*监控\s*间隔\s*(\d+)\s*秒",
    ]
    for pat in interval_patterns:
        m = re.search(pat, msg, re.IGNORECASE)
        if m:
            key = _resolve_platform(m.group(1).strip())
            if key and key in CONFIG_KEY_TO_DISPLAY:
                try:
                    v = int(m.group(2))
                    if 1 <= v <= 86400:
                        return ConfigFieldIntent(
                            section_key=key,
                            field_key="monitor_interval_seconds",
                            value=v,
                            display_name=CONFIG_KEY_TO_DISPLAY.get(key, key),
                        )
                except (ValueError, IndexError):
                    pass

    # 2. 并发数 concurrency
    concurrency_patterns = [
        r"(虎牙|huya|微博|weibo|哔哩哔哩|b站|bilibili|抖音|douyin|斗鱼|douyu|小红书|xhs)\s*(?:监控)?\s*并发\s*(?:为|改成|改为|设为)\s*(\d+)",
        r"(虎牙|huya|微博|weibo)\s*并发\s*(\d+)",
    ]
    for pat in concurrency_patterns:
        m = re.search(pat, msg, re.IGNORECASE)
        if m:
            key = _resolve_platform(m.group(1).strip())
            if key and key in CONFIG_KEY_TO_DISPLAY:
                try:
                    v = int(m.group(2))
                    if 1 <= v <= 20:
                        return ConfigFieldIntent(
                            section_key=key,
                            field_key="concurrency",
                            value=v,
                            display_name=CONFIG_KEY_TO_DISPLAY.get(key, key),
                        )
                except (ValueError, IndexError):
                    pass

    # 3. 执行时间 time（HH:MM）
    time_match = re.search(
        r"(\d{1,2}):(\d{2})\s*[到至\-~]\s*(\d{1,2}):(\d{2})",
        msg,
    )
    if time_match:
        # 免打扰时段：22:00 到 08:00
        try:
            h1, m1, h2, m2 = int(time_match.group(1)), int(time_match.group(2)), int(time_match.group(3)), int(time_match.group(4))
            if "免打扰" in msg or "静默" in msg:
                start = f"{h1:02d}:{m1:02d}"
                end = f"{h2:02d}:{m2:02d}"
                if 0 <= h1 <= 23 and 0 <= m1 <= 59 and 0 <= h2 <= 23 and 0 <= m2 <= 59:
                    # 返回第一个字段的修改意图，后续可扩展为同时改 start+end
                    return ConfigFieldIntent(
                        section_key="quiet_hours",
                        field_key="start_end",
                        value=f"{start},{end}",
                        display_name="免打扰时段",
                    )
        except (ValueError, IndexError):
            pass

    time_single_match = re.search(
        r"(超话|贴吧|ikuuu|签到|雨云|阿里云盘|值得买|夸克|天气|日志清理)\s*(?:签到|执行)?\s*(?:时间)?\s*(?:为|改成|改为|设为)\s*(\d{1,2}):(\d{2})",
        msg,
    )
    if time_single_match:
        task_raw = time_single_match.group(1).strip()
        h, m = int(time_single_match.group(2)), int(time_single_match.group(3))
        if 0 <= h <= 23 and 0 <= m <= 59:
            time_val = f"{h:02d}:{m:02d}"
            section_map = {
                "超话": "weibo_chaohua", "贴吧": "tieba", "ikuuu": "checkin", "签到": "checkin",
                "雨云": "rainyun", "阿里云盘": "aliyun", "值得买": "smzdm", "夸克": "kuake",
                "天气": "weather", "日志清理": "log_cleanup",
            }
            sec = section_map.get(task_raw)
            if sec:
                return ConfigFieldIntent(
                    section_key=sec,
                    field_key="time",
                    value=time_val,
                    display_name=TOGGLE_SECTION_TO_DISPLAY.get(sec, sec),
                )

    # 匹配「超话签到时间改为23:00」等
    time_gen = re.search(
        r"(超话签到|贴吧签到|ikuuu|雨云签到|阿里云盘签到|日志清理)\s*(?:时间)?\s*(?:为|改成|改为|设为)\s*(\d{1,2}):(\d{2})",
        msg,
    )
    if time_gen:
        task_raw = time_gen.group(1).strip()
        try:
            h, m = int(time_gen.group(2)), int(time_gen.group(3))
            if 0 <= h <= 23 and 0 <= m <= 59:
                time_val = f"{h:02d}:{m:02d}"
                section_map = {
                    "超话签到": "weibo_chaohua", "贴吧签到": "tieba", "ikuuu": "checkin",
                    "雨云签到": "rainyun", "阿里云盘签到": "aliyun", "日志清理": "log_cleanup",
                }
                sec = section_map.get(task_raw)
                if sec:
                    return ConfigFieldIntent(
                        section_key=sec,
                        field_key="time",
                        value=time_val,
                        display_name=TOGGLE_SECTION_TO_DISPLAY.get(sec, sec),
                    )
        except (ValueError, IndexError):
            pass

    # 4. 日志保留天数 retention_days
    retention_match = re.search(
        r"日志\s*(?:保留|保存)\s*(?:为|改成|改为|设为)?\s*(\d+)\s*天",
        msg,
    )
    if retention_match:
        try:
            v = int(retention_match.group(1))
            if 1 <= v <= 90:
                return ConfigFieldIntent(
                    section_key="log_cleanup",
                    field_key="retention_days",
                    value=v,
                    display_name="日志保留天数",
                )
        except (ValueError, IndexError):
            pass

    # 5. 免打扰单字段：免打扰开始/结束时间
    qh_start = re.search(r"免打扰\s*(?:开始|从)\s*(?:时间)?\s*(?:为|改成|改为)?\s*(\d{1,2}):(\d{2})", msg)
    if qh_start:
        try:
            h, m = int(qh_start.group(1)), int(qh_start.group(2))
            if 0 <= h <= 23 and 0 <= m <= 59:
                return ConfigFieldIntent(
                    section_key="quiet_hours",
                    field_key="start",
                    value=f"{h:02d}:{m:02d}",
                    display_name="免打扰开始时间",
                )
        except (ValueError, IndexError):
            pass
    qh_end = re.search(r"免打扰\s*(?:结束|到)\s*(?:时间)?\s*(?:为|改成|改为)?\s*(\d{1,2}):(\d{2})", msg)
    if qh_end:
        try:
            h, m = int(qh_end.group(1)), int(qh_end.group(2))
            if 0 <= h <= 23 and 0 <= m <= 59:
                return ConfigFieldIntent(
                    section_key="quiet_hours",
                    field_key="end",
                    value=f"{h:02d}:{m:02d}",
                    display_name="免打扰结束时间",
                )
        except (ValueError, IndexError):
            pass

    return None


# 自然语言任务名/别名 -> task_id 映射（供 AI 助手「执行XX任务」解析）
TASK_NAME_TO_JOB_ID = {
    "超话": "weibo_chaohua_checkin",
    "超话签到": "weibo_chaohua_checkin",
    "微博超话": "weibo_chaohua_checkin",
    "微博超话签到": "weibo_chaohua_checkin",
    "ikuuu": "ikuuu_checkin",
    "雨云": "rainyun_checkin",
    "雨云签到": "rainyun_checkin",
    "贴吧": "tieba_checkin",
    "百度贴吧": "tieba_checkin",
    "贴吧签到": "tieba_checkin",
    "阿里云盘": "aliyun_checkin",
    "阿里云盘签到": "aliyun_checkin",
    "什么值得买": "smzdm_checkin",
    "值得买": "smzdm_checkin",
    "值得买签到": "smzdm_checkin",
    "夸克": "kuake_checkin",
    "夸克签到": "kuake_checkin",
    "天气": "weather_push",
    "天气推送": "weather_push",
    "日志清理": "log_cleanup",
}


class RunTaskIntent(NamedTuple):
    """执行任务意图"""
    task_id: str
    display_name: str


def parse_run_task_intent(message: str) -> RunTaskIntent | None:
    """
    解析用户消息，识别「执行超话签到」「运行ikuuu」「立即运行贴吧签到」等意图。
    返回 RunTaskIntent 或 None（未识别到可执行任务意图）。
    """
    msg = message.strip()
    if not msg or len(msg) < 3:
        return None

    # 前缀模式：执行|运行|立即执行|立即运行|手动执行|手动运行 + 任务名
    prefix_patterns = [
        r"^(?:执行|运行|立即执行|立即运行|手动执行|手动运行|触发|跑一下)\s*(.+)",
        r"^做一下\s*(.+)",
        r"^跑\s*(.+)",
    ]
    task_name_candidates = []
    for pat in prefix_patterns:
        m = re.search(pat, msg, re.IGNORECASE)
        if m:
            task_name_candidates.append(m.group(1).strip().rstrip("。,.!?"))

    # 直接匹配：超话签到、执行超话 等（无前缀）
    if not task_name_candidates:
        for name, task_id in TASK_NAME_TO_JOB_ID.items():
            if name in msg and len(msg) <= len(name) + 6:  # 允许少量前后文，如「执行超话签到」
                task_name_candidates.append(name)
            elif msg == name or msg == f"执行{name}" or msg == f"运行{name}":
                task_name_candidates.append(name)

    # 解析任务名 -> task_id（优先匹配更长名称，如「超话签到」优于「超话」）
    TASK_DISPLAY = {
        "weibo_chaohua_checkin": "微博超话签到",
        "ikuuu_checkin": "iKuuu 签到",
        "rainyun_checkin": "雨云签到",
        "tieba_checkin": "百度贴吧签到",
        "aliyun_checkin": "阿里云盘签到",
        "smzdm_checkin": "什么值得买签到",
        "kuake_checkin": "夸克签到",
        "weather_push": "天气推送",
        "log_cleanup": "日志清理",
    }
    for raw in task_name_candidates:
        raw_lower = raw.strip().lower()
        # 按名称长度降序，优先精确匹配
        for name, task_id in sorted(TASK_NAME_TO_JOB_ID.items(), key=lambda x: -len(x[0])):
            if name in raw or raw == name or raw_lower == name.lower():
                display = TASK_DISPLAY.get(task_id, name)
                return RunTaskIntent(task_id=task_id, display_name=display)

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
