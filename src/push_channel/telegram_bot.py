import json

from aiohttp import ClientResponseError

from . import PushChannel


class TelegramBot(PushChannel):
    """Telegram 机器人推送通道"""

    def __init__(self, config, session=None):
        super().__init__(config, session)
        self.api_token = str(config.get("api_token", ""))
        self.chat_id = str(config.get("chat_id", ""))
        if self.api_token == "" or self.chat_id == "":
            self.logger.error(f"【推送_{self.name}】配置不完整，推送功能将无法正常使用")

    async def push(self, title, content, jump_url=None, pic_url=None, extend_data=None):
        """推送消息"""
        push_url = f"https://api.telegram.org/bot{self.api_token}/sendMessage"
        headers = {"Content-Type": "application/json"}

        # 构建消息文本
        text_parts = [f"*{title}*"]
        if jump_url:
            text_parts.append(f"[点击查看]({jump_url})")
        text_parts.append(f"\n`{content}`")
        text = "\n".join(text_parts)

        body = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown",
        }
        if pic_url is not None:
            body["link_preview_options"] = {"is_disabled": False, "url": pic_url}

        try:
            session = await self._get_session()
            async with session.post(
                push_url, headers=headers, data=json.dumps(body).encode("utf-8")
            ) as response:
                response.raise_for_status()
                result = await response.json()

                if not result.get("ok"):
                    error_msg = result.get("description", "未知错误")
                    raise Exception(f"推送失败: {error_msg}")

                self.logger.info(f"【推送_{self.name}】成功")
                return {"status": "success"}
        except ClientResponseError as e:
            self.logger.error(f"【推送_{self.name}】请求失败: {e}")
            raise
        except Exception as e:
            self.logger.error(f"【推送_{self.name}】推送失败: {e}")
            raise
