from aiohttp import ClientResponseError

from . import PushChannel


class ServerChan3(PushChannel):
    """Server酱 3 推送通道（desp 最大 64KB，与 Turbo 类似）"""

    max_content_bytes = 65536  # 64KB

    def __init__(self, config, session=None):
        super().__init__(config, session)
        self.send_key = str(config.get("send_key", ""))
        self.uid = str(config.get("uid", ""))
        self.tags = config.get("tags", None)
        if self.send_key == "" or self.uid == "":
            self.logger.error(f"【推送_{self.name}】配置不完整，推送功能将无法正常使用")

    async def push(self, title, content, jump_url=None, pic_url=None, extend_data=None):
        """推送消息"""
        push_url = f"https://{self.uid}.push.ft07.com/send/{self.send_key}.send"
        data = {
            "title": title,
            "desp": f"{content}\n\n[点我直达]({jump_url})" if jump_url else content,
        }
        if pic_url:
            data["desp"] += f"\n\n![]({pic_url})"
        if self.tags:
            data["tags"] = self.tags

        try:
            session = await self._get_session()
            async with session.post(push_url, data=data) as response:
                response.raise_for_status()
                result = await response.json()
                if result.get("code") == 0:
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
