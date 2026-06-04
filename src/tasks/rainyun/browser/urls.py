"""URL 构建"""

from src.tasks.rainyun.config_adapter import RainyunRunConfig


def build_app_url(config: RainyunRunConfig, path: str) -> str:
    base = config.app_base_url.rstrip("/")
    path = path.lstrip("/")
    return f"{base}/{path}"
