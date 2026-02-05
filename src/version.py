"""版本信息模块"""

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

# GitHub 仓库信息
GITHUB_OWNER = "666fy666"
GITHUB_REPO = "WebMoniter"
GITHUB_RELEASES_URL = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases"
GITHUB_API_LATEST_RELEASE = (
    f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
)


def get_version() -> str:
    """
    获取当前应用版本号。
    优先从 importlib.metadata 读取（已安装包），
    失败则从 pyproject.toml 直接解析。
    """
    try:
        return version("web-monitor")
    except PackageNotFoundError:
        pass

    # 从 pyproject.toml 直接读取
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    if pyproject_path.exists():
        import re

        content = pyproject_path.read_text(encoding="utf-8")
        match = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
        if match:
            return match.group(1)

    return "unknown"


# 缓存版本号
__version__ = get_version()
