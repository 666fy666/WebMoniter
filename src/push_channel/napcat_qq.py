from aiohttp import ClientResponseError

from . import PushChannel


class NapCatQQ(PushChannel):
    """
    NapCatQQ 推送通道
    Author: https://github.com/YingChengxi
    See: https://github.com/nfe-w/aio-dynamic-push/issues/50
    """

    def __init__(self, config, session=None):
        super().__init__(config, session)
        self.api_url = str(config.get("api_url", "")).rstrip("/")
        self.token = str(config.get("token", ""))
        _user_id = config.get("user_id", None)
        self.user_id = str(_user_id) if _user_id else None
        _group_id = config.get("group_id", None)
        self.group_id = str(_group_id) if _group_id else None
        _at_qq = config.get("at_qq", None)
        self.at_qq = str(_at_qq) if _at_qq else None
        if not self.api_url or (not self.user_id and not self.group_id):
            self.logger.error(f"【推送_{self.name}】配置不完整，推送功能将无法正常使用")
        if self.user_id and self.group_id:
            self.logger.error(f"【推送_{self.name}】配置错误，不能同时设置 user_id 和 group_id")

    async def push(self, title, content, jump_url=None, pic_url=None, extend_data=None):
        """推送消息"""
        message = [{"type": "text", "data": {"text": f"{title}\n\n{content}"}}]

        if pic_url:
            message.append({"type": "text", "data": {"text": "\n\n"}})
            message.append({"type": "image", "data": {"file": pic_url}})

        if jump_url:
            message.append({"type": "text", "data": {"text": f"\n\n原文: {jump_url}"}})

        if self.at_qq:
            message.append({"type": "text", "data": {"text": "\n\n"}})
            message.append({"type": "at", "data": {"qq": f"{self.at_qq}"}})

        payload = {
            "user_id": self.user_id,
            "group_id": self.group_id,
            "message": message,
        }
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        api_endpoint = f"{self.api_url}/send_msg"

        try:
            session = await self._get_session()
            async with session.post(api_endpoint, headers=headers, json=payload) as response:
                response.raise_for_status()
                resp_data = await response.json()

                if resp_data.get("status") == "ok" and resp_data.get("retcode") == 0:
                    self.logger.info(f"【推送_{self.name}】消息发送成功")
                    return {"status": "success"}
                else:
                    error_msg = resp_data.get("message", "未知错误")
                    raise Exception(f"API返回错误: {error_msg}")
        except ClientResponseError as e:
            self.logger.error(f"【推送_{self.name}】请求失败: {e}")
            raise
        except Exception as e:
            self.logger.error(f"【推送_{self.name}】发送消息时出现异常: {e}")
            raise
