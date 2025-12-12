from aiohttp import ClientResponseError

from . import PushChannel


class PushPlus(PushChannel):
    """PushPlus 推送通道"""

    def __init__(self, config, session=None):
        super().__init__(config, session)
        self.token = str(config.get("token", ""))
        self.channel = str(config.get("channel", "wechat"))  # 推送渠道，默认wechat
        self.topic = config.get("topic", None)  # 群组代码，可选
        self.template = str(config.get("template", "html"))  # 消息模板，默认html
        self.to = config.get("to", None)  # 好友消息的接收者标识，可选
        if self.token == "":
            self.logger.error(f"【推送_{self.name}】配置不完整，推送功能将无法正常使用")

    async def push(self, title, content, jump_url=None, pic_url=None, extend_data=None):
        """推送消息"""
        push_url = "https://www.pushplus.plus/send"

        # 构建消息内容（HTML格式）
        html_content = f"""
        <div style="font-family: Arial, sans-serif;">
            <h2>{title}</h2>
            <p style="white-space: pre-wrap;">{content}</p>
            {f'<img src="{pic_url}" alt="图片" style="max-width: 100%;" />' if pic_url else ''}
            {f'<p><a href="{jump_url}" style="display: inline-block; padding: 10px 20px; background-color: #007bff; color: white; text-decoration: none; border-radius: 5px;">阅读全文</a></p>' if jump_url else ''}
        </div>
        """

        payload = {
            "token": self.token,
            "title": title,
            "content": html_content,
            "template": self.template,
        }

        # 添加可选参数
        if self.channel:
            payload["channel"] = self.channel
        if self.topic:
            payload["topic"] = self.topic
        if self.to:
            payload["to"] = self.to

        try:
            session = await self._get_session()
            async with session.post(
                push_url, json=payload, headers={"Content-Type": "application/json"}
            ) as response:
                response.raise_for_status()
                result = await response.json()

                if result.get("code") == 200:
                    self.logger.info(f"【推送_{self.name}】成功")
                    return {"status": "success"}
                else:
                    error_msg = result.get("msg", "未知错误")
                    raise Exception(f"推送失败: {error_msg}")
        except ClientResponseError as e:
            self.logger.error(f"【推送_{self.name}】请求失败: {e}")
            raise
        except Exception as e:
            self.logger.error(f"【推送_{self.name}】推送失败: {e}")
            raise
