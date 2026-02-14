import json
from pathlib import Path

from aiohttp import ClientResponseError, FormData

from . import PushChannel


class TelegramBot(PushChannel):
    """Telegram 机器人推送通道（sendMessage 单条最多 4096 字符，见 Bot API 文档）"""

    max_content_bytes = 16384  # 4096 字符 × 4 字节/字符（UTF-8 上界）

    def __init__(self, config, session=None):
        super().__init__(config, session)
        self.api_token = str(config.get("api_token", ""))
        self.chat_id = str(config.get("chat_id", ""))
        if self.api_token == "" or self.chat_id == "":
            self.logger.error(f"【推送_{self.name}】配置不完整，推送功能将无法正常使用")

    async def push(self, title, content, jump_url=None, pic_url=None, extend_data=None):
        """推送消息

        支持两种方式附带图片：
        1. pic_url 为 HTTP(S) 链接时，使用链接预览；
        2. extend_data 中包含 local_pic_path 且本地文件存在时，使用 sendPhoto 上传本地图片。
        """
        local_pic_path = None
        if extend_data and isinstance(extend_data, dict):
            local_pic_path = extend_data.get("local_pic_path")
        if local_pic_path:
            local_path = Path(str(local_pic_path))
        else:
            local_path = None

        # 如果有可用的本地图片路径，优先使用 sendPhoto 上传本地图片
        if local_path and local_path.is_file():
            push_url = f"https://api.telegram.org/bot{self.api_token}/sendPhoto"

            # 构建图片说明文字（caption），Telegram 限制为最多 1024 个字符
            caption_parts = [f"*{title}*"]
            if jump_url:
                caption_parts.append(f"[点击查看]({jump_url})")
            caption_parts.append(f"\n`{content}`")
            caption = "\n".join(caption_parts)
            if len(caption) > 1024:
                caption = caption[:1018] + "......"

            form = FormData()
            form.add_field("chat_id", self.chat_id)
            form.add_field("caption", caption)
            form.add_field("parse_mode", "Markdown")
            try:
                with local_path.open("rb") as f:
                    form.add_field(
                        "photo",
                        f,
                        filename=local_path.name,
                        content_type="image/jpeg",
                    )

                    session = await self._get_session()
                    async with session.post(push_url, data=form) as response:
                        response.raise_for_status()
                        result = await response.json()

                if not result.get("ok"):
                    error_msg = result.get("description", "未知错误")
                    raise Exception(f"推送失败: {error_msg}")

                self.logger.debug(f"【推送_{self.name}】成功（本地图片上传）")
                return {"status": "success"}
            except ClientResponseError as e:
                self.logger.error(f"【推送_{self.name}】请求失败: {e}")
                raise
            except Exception as e:
                self.logger.error(f"【推送_{self.name}】发送带本地图片的消息失败: {e}")
                raise

        # 否则退回到原有逻辑：纯文本 + 可选链接预览
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

                self.logger.debug(f"【推送_{self.name}】成功")
                return {"status": "success"}
        except ClientResponseError as e:
            self.logger.error(f"【推送_{self.name}】请求失败: {e}")
            raise
        except Exception as e:
            self.logger.error(f"【推送_{self.name}】推送失败: {e}")
            raise
