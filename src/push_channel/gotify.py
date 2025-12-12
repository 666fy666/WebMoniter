from aiohttp import ClientResponseError

from . import PushChannel


class Gotify(PushChannel):
    """Gotify 推送通道"""

    def __init__(self, config, session=None):
        super().__init__(config, session)
        self.web_server_url = str(config.get("web_server_url", ""))
        if self.web_server_url == "":
            self.logger.error(f"【推送_{self.name}】配置不完整，推送功能将无法正常使用")

    async def push(self, title, content, jump_url=None, pic_url=None, extend_data=None):
        """推送消息"""
        headers = {
            "Content-Type": "application/json",
        }
        body = {
            "title": title,
            "message": content,
            "priority": 5,
        }
        if jump_url:
            body["extras"] = {"client::display": {"contentType": "text/markdown"}}
            body["message"] = f"{content}\n\n[点击查看]({jump_url})"

        try:
            session = await self._get_session()
            async with session.post(self.web_server_url, headers=headers, json=body) as response:
                response.raise_for_status()
                self.logger.info(f"【推送_{self.name}】成功")
                return {"status": "success"}
        except ClientResponseError as e:
            self.logger.error(f"【推送_{self.name}】请求失败: {e}")
            raise
        except Exception as e:
            self.logger.error(f"【推送_{self.name}】推送失败: {e}")
            raise
