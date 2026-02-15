"""AI 助手配置模块 - 从 config.yml 的 ai_assistant 节点读取"""

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

# Provider 与 api_base 的默认映射（主流厂商）
DEFAULT_API_BASES = {
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "zhipu": "https://open.bigmodel.cn/api/paas/v4",
    "moonshot": "https://api.moonshot.cn/v1",
    "ollama": "http://localhost:11434/v1",
    "openai_compatible": "",  # 需用户填写 api_base
}


@dataclass
class AIConfig:
    """AI 助手配置"""

    enable: bool = False
    provider: str = "openai"
    api_base: str = ""
    api_key: str = ""
    model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    chroma_persist_dir: str = "data/ai_assistant_chroma"
    rate_limit_per_minute: int = 10
    max_history_rounds: int = 10

    def get_api_base(self) -> str:
        """获取有效的 api_base，优先使用配置值，否则用 provider 默认值"""
        if self.api_base and self.api_base.strip():
            return self.api_base.strip().rstrip("/")
        return DEFAULT_API_BASES.get(self.provider, "https://api.openai.com/v1")

    def get_api_key(self) -> str:
        """获取 API Key，优先环境变量 AI_ASSISTANT_API_KEY"""
        env_key = os.environ.get("AI_ASSISTANT_API_KEY", "").strip()
        if env_key:
            return env_key
        return (self.api_key or "").strip()


_config_cache: AIConfig | None = None


def get_ai_config(reload: bool = False) -> AIConfig:
    """从 config.yml 读取 ai_assistant 配置"""
    global _config_cache
    if _config_cache is not None and not reload:
        return _config_cache

    config_path = Path("config.yml")
    if not config_path.exists():
        _config_cache = AIConfig()
        return _config_cache

    try:
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception:
        _config_cache = AIConfig()
        return _config_cache

    raw = data.get("ai_assistant") if isinstance(data, dict) else None
    if not raw or not isinstance(raw, dict):
        _config_cache = AIConfig()
        return _config_cache

    _config_cache = AIConfig(
        enable=bool(raw.get("enable", False)),
        provider=str(raw.get("provider", "openai")),
        api_base=str(raw.get("api_base", "")),
        api_key=str(raw.get("api_key", "")),
        model=str(raw.get("model", "gpt-4o-mini")),
        embedding_model=str(raw.get("embedding_model", "text-embedding-3-small")),
        chroma_persist_dir=str(raw.get("chroma_persist_dir", "data/ai_assistant_chroma")),
        rate_limit_per_minute=int(raw.get("rate_limit_per_minute", 10)),
        max_history_rounds=int(raw.get("max_history_rounds", 10)),
    )
    return _config_cache


def is_ai_enabled() -> bool:
    """是否启用 AI 助手（配置 enable 且已安装必要依赖）"""
    cfg = get_ai_config()
    if not cfg.enable:
        return False
    # 检查是否可导入 openai/httpx（AI 依赖）
    try:
        import openai  # noqa: F401
    except ImportError:
        try:
            import httpx  # noqa: F401
        except ImportError:
            return False
    return True
