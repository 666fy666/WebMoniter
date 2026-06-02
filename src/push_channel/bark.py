from aiohttp import ClientResponseError

from src.log_manager import _current_job_id

from . import PushChannel

# 保存到 Bark 历史记录的消息有效期（秒），到期后自动删除
_BARK_HISTORY_TTL_SECONDS = 1 * 24 * 60 * 60


def _bark_group_from_extend_data(extend_data: dict | None) -> str | None:
    """按 Bark 文档的 group 参数：优先显式 bark_group，其次青龙式 query_task_config.name，最后当前调度任务 job_id。"""
    if extend_data:
        g = extend_data.get("bark_group")
        if g is not None and str(g).strip():
            return str(g).strip()
        q = extend_data.get("query_task_config")
        if isinstance(q, dict):
            n = q.get("name")
            if n is not None and str(n).strip():
                return str(n).strip()
    jid = _current_job_id.get()
    if jid:
        return str(jid).strip() or None
    return None


class Bark(PushChannel):
    """Bark 推送通道（使用 V2 API，body 无明确官方限制，保守限制）"""

    max_content_bytes = 4096

    def __init__(self, config, session=None):
        super().__init__(config, session)
        self.server_url = str(config.get("server_url", "https://api.day.app")).rstrip("/")
        self.key = str(config.get("key", ""))
        if self.key == "":
            self.logger.error(f"【推送_{self.name}】配置不完整，推送功能将无法正常使用")

    async def push(self, title, content, jump_url=None, pic_url=None, extend_data=None):
        """推送消息"""
        push_url = f"{self.server_url}/push"

        payload = {
            "device_key": self.key,
            "title": title,
            "body": content,
            "ttl": _BARK_HISTORY_TTL_SECONDS,
        }
        if jump_url:
            payload["url"] = jump_url

        group = _bark_group_from_extend_data(extend_data)
        if group:
            payload["group"] = group

        if extend_data:
            avatar_url = extend_data.get("avatar_url")
            if avatar_url:
                payload["icon"] = avatar_url

        try:
            session = await self._get_session()
            async with session.post(push_url, json=payload) as response:
                response.raise_for_status()
                result = await response.json()
                if result.get("code") == 200:
                    self.logger.debug(f"【推送_{self.name}】成功")
                    return {"status": "success"}
                else:
                    error_msg = result.get("message", "未知错误")
                    raise Exception(f"推送失败: {error_msg}")
        except ClientResponseError as e:
            self.logger.error(f"【推送_{self.name}】请求失败: {e}")
            raise
        except Exception as e:
            self.logger.error(f"【推送_{self.name}】推送失败: {e}")
            raise
