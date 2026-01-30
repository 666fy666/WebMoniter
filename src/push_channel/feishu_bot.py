import base64
import hashlib
import hmac
import json
import time

from aiohttp import ClientResponseError

from . import PushChannel


class FeishuBot(PushChannel):
    """飞书机器人推送通道"""

    def __init__(self, config, session=None):
        super().__init__(config, session)
        self.webhook_key = str(config.get("webhook_key", ""))
        self.sign_secret = str(config.get("sign_secret", "")).strip()
        if self.webhook_key == "":
            self.logger.error(f"【推送_{self.name}】配置不完整，推送功能将无法正常使用")

    def _generate_sign(self) -> tuple[int, str]:
        """
        生成飞书机器人签名
        签名算法：timestamp + "\\n" + sign_secret，然后使用 HMAC-SHA256 加密，最后 Base64 编码
        参考：https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot?lang=zh-CN

        Returns:
            (timestamp, sign): 时间戳和签名的元组
        """
        timestamp = int(time.time())
        string_to_sign = f"{timestamp}\n{self.sign_secret}"
        hmac_code = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
        sign = base64.b64encode(hmac_code).decode("utf-8")
        return timestamp, sign

    async def push(self, title, content, jump_url=None, pic_url=None, extend_data=None):
        """推送消息"""
        push_url = f"https://open.feishu.cn/open-apis/bot/v2/hook/{self.webhook_key}"
        headers = {"Content-Type": "application/json"}
        card_elements = [{"tag": "markdown", "content": content}]

        # 注意：飞书机器人不支持直接上传图片，需要先上传到飞书获取img_key
        # 这里暂时跳过图片处理，如果需要可以后续实现
        # if pic_url is not None:
        #     img_key = await self._get_img_key(pic_url)
        #     if img_key is not None:
        #         card_elements.append({
        #             "alt": {"content": "", "tag": "plain_text"},
        #             "img_key": img_key,
        #             "tag": "img"
        #         })

        if jump_url:
            card_elements.append(
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "点我跳转"},
                            "type": "primary",
                            "url": jump_url,
                        }
                    ],
                }
            )

        body = {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {
                    "template": "blue",
                    "title": {"content": title, "tag": "plain_text"},
                },
                "elements": card_elements,
            },
        }

        # 如果配置了签名密钥，则添加签名校验信息
        if self.sign_secret:
            timestamp, sign = self._generate_sign()
            body["timestamp"] = timestamp
            body["sign"] = sign

        try:
            session = await self._get_session()
            async with session.post(
                push_url, headers=headers, data=json.dumps(body).encode("utf-8")
            ) as response:
                response.raise_for_status()
                result = await response.json()

                if result.get("code") != 0:
                    error_msg = result.get("msg", "未知错误")
                    raise Exception(f"推送失败: {error_msg}")

                self.logger.debug(f"【推送_{self.name}】成功")
                return {"status": "success"}
        except ClientResponseError as e:
            self.logger.error(f"【推送_{self.name}】请求失败: {e}")
            raise
        except Exception as e:
            self.logger.error(f"【推送_{self.name}】推送失败: {e}")
            raise
