from aiohttp import ClientResponseError

from . import PushChannel


class WxPusher(PushChannel):
    """WxPusher 推送通道"""

    def __init__(self, config, session=None):
        super().__init__(config, session)
        self.app_token = str(config.get("app_token", ""))
        self.uids = config.get("uids", "")  # 用户ID列表，逗号分隔（可选）
        self.topic_ids = config.get("topic_ids", "")  # 主题ID列表，逗号分隔（可选）
        self.content_type = config.get(
            "content_type", 1
        )  # 内容类型：1-文本，2-html，3-markdown，默认1
        if self.app_token == "":
            self.logger.error(f"【推送_{self.name}】配置不完整，推送功能将无法正常使用")

    async def push(self, title, content, jump_url=None, pic_url=None, extend_data=None):
        """推送消息"""
        push_url = "https://wxpusher.zjiecode.com/api/send/message"

        # 构建消息内容
        # 根据content_type决定内容格式
        if self.content_type == 2:  # HTML格式
            message_content = f"""<div style="font-family: Arial, sans-serif;">
<h2>{title}</h2>
<p style="white-space: pre-wrap;">{content}</p>
{f'<img src="{pic_url}" alt="图片" style="max-width: 100%;" />' if pic_url else ''}
{f'<p><a href="{jump_url}" style="display: inline-block; padding: 10px 20px; background-color: #007bff; color: white; text-decoration: none; border-radius: 5px;">阅读全文</a></p>' if jump_url else ''}
</div>"""
        elif self.content_type == 3:  # Markdown格式
            message_content = f"## {title}\n\n{content}"
            if pic_url:
                message_content += f"\n\n![图片]({pic_url})"
            if jump_url:
                message_content += f"\n\n[阅读全文]({jump_url})"
        else:  # 文本格式（默认）
            message_content = f"{title}\n\n{content}"
            if jump_url:
                message_content += f"\n\n链接：{jump_url}"

        payload = {
            "appToken": self.app_token,
            "content": message_content,
            "summary": title,  # 消息摘要，使用标题
            "contentType": self.content_type,
        }

        # 添加可选参数
        if jump_url:
            payload["url"] = jump_url

        # uids 和 topicIds 至少需要提供一个
        uids_list = []
        if self.uids:
            uids_list = [uid.strip() for uid in str(self.uids).split(",") if uid.strip()]

        topic_ids_list = []
        if self.topic_ids:
            # topicIds 应该是数字列表
            try:
                topic_ids_list = [
                    int(topic_id.strip())
                    for topic_id in str(self.topic_ids).split(",")
                    if topic_id.strip()
                ]
            except ValueError:
                self.logger.warning(f"【推送_{self.name}】topic_ids 格式错误，应为数字列表")

        if uids_list:
            payload["uids"] = uids_list
        if topic_ids_list:
            payload["topicIds"] = topic_ids_list

        # 如果既没有uids也没有topicIds，记录警告
        if not uids_list and not topic_ids_list:
            self.logger.warning(f"【推送_{self.name}】未配置uids或topicIds，消息可能无法发送")

        try:
            session = await self._get_session()
            async with session.post(
                push_url, json=payload, headers={"Content-Type": "application/json"}
            ) as response:
                response.raise_for_status()
                result = await response.json()

                # wxpusher API 返回格式：{"success": true/false, "msg": "消息", "data": {...}}
                if result.get("success") is True:
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
