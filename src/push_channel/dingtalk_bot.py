import base64
import hashlib
import hmac
import time

from . import PushChannel


class DingtalkBot(PushChannel):
    """钉钉机器人推送通道（link 消息 text 约 4000 字符限制，见钉钉开放文档）"""

    max_content_bytes = 12000  # 约 4000 字符 UTF-8

    def __init__(self, config, session=None):
        super().__init__(config, session)
        self.access_token = str(config.get("access_token", ""))
        self.secret = str(config.get("secret", ""))  # 加签密钥，可选
        if self.access_token == "":
            self.logger.error(f"【推送_{self.name}】配置不完整，推送功能将无法正常使用")

    def _calculate_sign(self) -> tuple[str, str]:
        """
        计算钉钉机器人加签签名

        Returns:
            tuple: (timestamp, sign) 时间戳和签名值
        """
        timestamp = str(round(time.time() * 1000))
        secret_enc = self.secret.encode("utf-8")
        string_to_sign = f"{timestamp}\n{self.secret}"
        string_to_sign_enc = string_to_sign.encode("utf-8")
        hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
        sign = base64.b64encode(hmac_code).decode("utf-8")
        return timestamp, sign

    async def push(self, title, content, jump_url=None, pic_url=None, extend_data=None):
        """推送消息"""
        push_url = "https://oapi.dingtalk.com/robot/send"
        headers = {"Content-Type": "application/json"}
        params = {"access_token": self.access_token}

        # 如果配置了secret，则使用加签方式
        if self.secret:
            timestamp, sign = self._calculate_sign()
            params["timestamp"] = timestamp
            params["sign"] = sign

        body = {
            "msgtype": "link",
            "link": {
                "title": title,
                "text": content,
                "messageUrl": jump_url or "",
            },
        }

        if pic_url is not None:
            body["link"]["picUrl"] = pic_url

        await self._post_json(
            push_url,
            body,
            headers=headers,
            params=params,
            code_key="errcode",
            message_key="errmsg",
        )
        return {"status": "success"}
