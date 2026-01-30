from aiohttp import ClientResponseError

from . import PushChannel


class Webhook(PushChannel):
    """Webhook 推送通道"""

    def __init__(self, config, session=None):
        super().__init__(config, session)
        self.webhook_url = str(config.get("webhook_url", ""))
        self.request_method = str(config.get("request_method", "GET")).upper()
        if self.webhook_url == "":
            self.logger.error(f"【推送_{self.name}】配置不完整，推送功能将无法正常使用")

    async def push(self, title, content, jump_url=None, pic_url=None, extend_data=None):
        """推送消息"""
        if not self.webhook_url:
            self.logger.warning(f"【推送_{self.name}】推送地址为空，跳过推送")
            return

        push_url = self.webhook_url.replace("{{title}}", title).replace("{{content}}", content)

        try:
            session = await self._get_session()
            if self.request_method == "GET":
                async with session.get(push_url) as response:
                    response.raise_for_status()
                    self.logger.debug(f"【推送_{self.name}】成功")
                    return {"status": "success"}
            elif self.request_method == "POST":
                data = extend_data if extend_data else {}
                async with session.post(push_url, json=data) as response:
                    response.raise_for_status()
                    self.logger.debug(f"【推送_{self.name}】成功")
                    return {"status": "success"}
            else:
                raise ValueError(f"不支持的请求方法：{self.request_method}")
        except ClientResponseError as e:
            self.logger.error(f"【推送_{self.name}】请求失败: {e}")
            raise
        except Exception as e:
            self.logger.error(f"【推送_{self.name}】推送失败: {e}")
            raise
