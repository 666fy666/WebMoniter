"""雨云配置适配器 - 将 WebMoniter 配置转为 Rainyun-Qiandao 风格"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RainyunAccountConfig:
    """单个雨云账号配置（对应 Rainyun-Qiandao 的 Account）"""

    username: str
    password: str
    api_key: str = ""
    display_name: str = ""
    cookie_file: str = ""
    renew_product_ids: list[int] = field(default_factory=list)
    auto_renew: bool = True


@dataclass
class RainyunRunConfig:
    """单次运行配置（对应 Rainyun-Qiandao 的 Config）"""

    rainyun_user: str
    rainyun_pwd: str
    rainyun_api_key: str
    display_name: str
    cookie_file: str
    app_base_url: str = "https://app.rainyun.com"
    api_base_url: str = "https://api.v2.rainyun.com"
    timeout: int = 15
    linux_mode: bool = True
    chrome_bin: str = ""
    chromedriver_path: str = ""
    chrome_low_memory: bool = False
    auto_renew: bool = True
    renew_threshold_days: int = 7
    renew_product_ids: list[int] = field(default_factory=list)
    points_to_cny_rate: int = 2000
    captcha_retry_limit: int = 5
    captcha_retry_unlimited: bool = False
    captcha_save_samples: bool = False
    download_timeout: int = 10
    download_max_retries: int = 3
    download_retry_delay: float = 2.0

    @classmethod
    def from_account(cls, account: RainyunAccountConfig, **overrides: Any) -> "RainyunRunConfig":
        # 先构建基础参数字典，再让 overrides 覆盖，避免重复传入同一关键字参数
        base = dict(
            rainyun_user=account.username,
            rainyun_pwd=account.password,
            rainyun_api_key=account.api_key,
            display_name=account.display_name or account.username,
            cookie_file=account.cookie_file,
            auto_renew=account.auto_renew,
            renew_product_ids=account.renew_product_ids or [],
        )
        base.update(overrides)
        return cls(**base)
