"""通用工具函数"""


def mask_cookie_for_log(cookie: str) -> str:
    """对 Cookie 做部分脱敏，用于日志与推送描述。"""
    if not cookie or len(cookie) < 20:
        return "***"
    return cookie[:8] + "***" + cookie[-4:] if len(cookie) > 12 else "***"
