import json
import time

from aiohttp import ClientResponseError

from . import PushChannel


class WeComApps(PushChannel):
    """企业微信应用推送通道（textcard/news 描述约 500 字节限制，见官方文档 发送应用消息）"""

    max_content_bytes = 500

    def __init__(self, config, session=None):
        super().__init__(config, session)
        self.corp_id = str(config.get("corp_id", ""))
        self.agent_id = str(config.get("agent_id", ""))
        self.corp_secret = str(config.get("corp_secret", ""))
        self.touser = str(config.get("touser", "@all"))  # 接收消息的用户ID，默认@all
        self._token: str | None = None
        self._token_expires_at: float = 0
        if self.corp_id == "" or self.agent_id == "" or self.corp_secret == "":
            self.logger.error(f"【推送_{self.name}】配置不完整，推送功能将无法正常使用")

    async def _get_wechat_access_token(self):
        """获取企业微信 access_token"""
        current_time = time.time()

        # 如果token还有效（提前5分钟刷新），直接返回
        if self._token and current_time < self._token_expires_at - 300:
            return self._token

        url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={self.corp_id}&corpsecret={self.corp_secret}"

        try:
            session = await self._get_session()
            async with session.get(url) as response:
                response.raise_for_status()
                result = await response.json()

                if result.get("errcode") != 0:
                    raise Exception(f"获取token失败: {result.get('errmsg', '未知错误')}")

                self._token = result["access_token"]
                # token有效期通常是7200秒，这里设置为7000秒以提前刷新
                self._token_expires_at = current_time + 7000
                return self._token
        except Exception as e:
            self.logger.error(f"获取企业微信token失败: {e}")
            raise

    async def push(self, title, content, jump_url=None, pic_url=None, extend_data=None):
        """推送消息"""
        access_token = await self._get_wechat_access_token()
        push_url = "https://qyapi.weixin.qq.com/cgi-bin/message/send"
        params = {"access_token": access_token}
        body = {
            "touser": self.touser,
            "agentid": self.agent_id,
            "safe": 0,
            "enable_id_trans": 0,
            "enable_duplicate_check": 0,
            "duplicate_check_interval": 1800,
        }

        # 微博封面：优先使用 resize 后的企微专用图（1068×455），符合企微图文消息推荐尺寸
        pic_to_use = pic_url
        if extend_data and extend_data.get("wecom_pic_url"):
            pic_to_use = extend_data["wecom_pic_url"]

        if pic_to_use is None:
            body["msgtype"] = "textcard"
            body["textcard"] = {
                "title": title,
                "description": content,
                "url": jump_url or "",
                "btntxt": extend_data.get("btntxt", "打开详情") if extend_data else "打开详情",
            }
        else:
            body["msgtype"] = "news"
            body["news"] = {
                "articles": [
                    {
                        "title": title,
                        "description": content,
                        "url": jump_url or "",
                        "picurl": pic_to_use,
                    }
                ]
            }

        try:
            session = await self._get_session()
            async with session.post(
                push_url,
                params=params,
                data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json"},
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
