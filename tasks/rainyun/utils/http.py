"""HTTP 工具"""

import logging
import os

import requests

from tasks.rainyun.config_adapter import RainyunRunConfig

logger = logging.getLogger(__name__)


def download_bytes(
    url: str,
    *,
    timeout: int = 10,
    max_retries: int = 3,
    retry_delay: float = 2.0,
) -> bytes:
    last_error: str | None = None
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(url, timeout=timeout)
            if response.status_code == 200 and response.content:
                return response.content
            last_error = f"status_code={response.status_code}"
            logger.warning("下载图片失败 (第 %d 次): %s, URL: %s", attempt, last_error, url)
        except requests.RequestException as e:
            last_error = str(e)
            logger.warning("下载图片失败 (第 %d 次): %s, URL: %s", attempt, e, url)
        if attempt < max_retries:
            import time

            time.sleep(retry_delay)
    raise RuntimeError(f"下载图片失败，已重试 {max_retries} 次: {last_error}, URL: {url}")


def download_to_file(
    url: str,
    output_path: str,
    config: RainyunRunConfig,
) -> bool:
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    for attempt in range(1, config.download_max_retries + 1):
        try:
            response = requests.get(url, timeout=config.download_timeout)
            if response.status_code == 200:
                with open(output_path, "wb") as f:
                    f.write(response.content)
                return True
            logger.warning(
                "下载图片失败 (第 %d 次): status_code=%s, URL: %s",
                attempt,
                response.status_code,
                url,
            )
        except requests.RequestException as e:
            logger.warning("下载图片失败 (第 %d 次): %s, URL: %s", attempt, e, url)
        if attempt < config.download_max_retries:
            import time

            time.sleep(config.download_retry_delay)
    logger.error("下载图片失败，已重试 %d 次, URL: %s", config.download_max_retries, url)
    return False
