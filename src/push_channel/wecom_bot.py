import json

from aiohttp import ClientResponseError

from . import PushChannel


class WeComBot(PushChannel):
    """企业微信机器人推送通道"""

    def __init__(self, config, session=None):
        super().__init__(config, session)
        self.key = str(config.get("key", ""))
        if self.key == "":
            self.logger.error(f"【推送_{self.name}】配置不完整，推送功能将无法正常使用")

    async def push(self, title, content, jump_url=None, pic_url=None, extend_data=None):
        """推送消息"""
        push_url = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send"
        headers = {"Content-Type": "application/json"}
        params = {"key": self.key}
        body = {
            "msgtype": "news",
            "news": {
                "articles": [
                    {
                        "title": title,
                        "description": content,
                        "url": jump_url or "",
                    }
                ]
            },
        }

        if pic_url is not None:
            body["news"]["articles"][0]["picurl"] = pic_url

        try:
            session = await self._get_session()
            async with session.post(
                push_url, headers=headers, params=params, data=json.dumps(body).encode("utf-8")
            ) as response:
                response.raise_for_status()
                result = await response.json()

                if result.get("errcode") != 0:
                    error_msg = result.get("errmsg", "未知错误")
                    raise Exception(f"推送失败: {error_msg}")

                self.logger.debug(f"【推送_{self.name}】成功")
                return {"status": "success"}
        except ClientResponseError as e:
            self.logger.error(f"【推送_{self.name}】请求失败: {e}")
            raise
        except Exception as e:
            self.logger.error(f"【推送_{self.name}】推送失败: {e}")
            raise
