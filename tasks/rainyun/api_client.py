"""雨云 API 客户端（参考 Jielumoon/Rainyun-Qiandao api/client.py）"""

import logging
import time

import requests

from tasks.rainyun.config_adapter import RainyunRunConfig

logger = logging.getLogger(__name__)


class RainyunAPIError(Exception):
    """雨云 API 调用异常"""


class RainyunAPI:
    """雨云 API 客户端"""

    def __init__(self, api_key: str, config: RainyunRunConfig | None = None):
        self.api_key = api_key
        self.config = config or RainyunRunConfig(
            rainyun_user="",
            rainyun_pwd="",
            rainyun_api_key=api_key,
            display_name="",
            cookie_file="",
        )
        self.api_base_url = self.config.api_base_url.rstrip("/")
        self.request_timeout = 15
        self.max_retries = 3
        self.retry_delay = 2.0
        self.headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json",
        }

    def _request(self, method: str, endpoint: str, data: dict | None = None) -> dict:
        url = f"{self.api_base_url}{endpoint}"
        last_error = None
        prefix = f"用户 {self.config.display_name} " if self.config.display_name else ""

        for attempt in range(1, self.max_retries + 1):
            try:
                if method.upper() == "GET":
                    response = requests.get(url, headers=self.headers, timeout=self.request_timeout)
                else:
                    response = requests.post(
                        url,
                        headers=self.headers,
                        json=data,
                        timeout=self.request_timeout,
                    )
                result = response.json()
                api_code = result.get("code")
                api_message = result.get("message", "未知错误")
                if api_code != 200:
                    raise RainyunAPIError(f"API 返回错误 [{api_code}]: {api_message}")
                return result.get("data", {})
            except requests.RequestException as e:
                last_error = e
                if attempt < self.max_retries:
                    logger.warning(
                        "%s请求失败 (第 %d 次): %s，%ss 后重试...",
                        prefix,
                        attempt,
                        e,
                        self.retry_delay,
                    )
                    time.sleep(self.retry_delay)
                    continue
                raise RainyunAPIError(f"网络请求失败 (已重试 {self.max_retries} 次): {last_error}")

        raise RainyunAPIError(f"请求失败: {last_error}")

    def get_server_ids(self, product_type: str = "rgs") -> list:
        data = self._request("GET", f"/product/id_list?product_type={product_type}")
        return data.get(product_type, [])

    def get_server_detail(self, server_id: int) -> dict:
        return self._request("GET", f"/product/rgs/{server_id}/")

    def get_user_points(self) -> int:
        data = self._request("GET", "/user/")
        return data.get("Points", 0)

    def renew_server(self, server_id: int, days: int = 7) -> dict:
        payload = {
            "duration_day": days,
            "product_id": server_id,
            "product_type": "rgs",
        }
        return self._request("POST", "/product/point_renew", payload)
