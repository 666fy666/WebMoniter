import json
import mimetypes
import os
import tempfile
import time
import uuid

from aiohttp import ClientResponseError, FormData

from . import PushChannel


class FeishuApps(PushChannel):
    """飞书自建应用推送通道"""

    def __init__(self, config, session=None):
        super().__init__(config, session)
        self.app_id = str(config.get("app_id", ""))
        self.app_secret = str(config.get("app_secret", ""))
        self.receive_id_type = str(config.get("receive_id_type", ""))
        self.receive_id = str(config.get("receive_id", ""))
        self._token: str | None = None
        self._token_expires_at: float = 0
        if (
            self.app_id == ""
            or self.app_secret == ""
            or self.receive_id_type == ""
            or self.receive_id == ""
        ):
            self.logger.error(f"【推送_{self.name}】配置不完整，推送功能将无法正常使用")

    async def _get_tenant_access_token(self):
        """获取飞书 tenant_access_token"""
        current_time = time.time()

        # 如果token还有效（提前5分钟刷新），直接返回
        if self._token and current_time < self._token_expires_at - 300:
            return self._token

        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/"
        headers = {"Content-Type": "application/json; charset=utf-8"}
        body = {"app_id": self.app_id, "app_secret": self.app_secret}

        try:
            session = await self._get_session()
            async with session.post(url, headers=headers, json=body) as response:
                response.raise_for_status()
                result = await response.json()

                if result.get("code") != 0:
                    raise Exception(f"获取token失败: {result.get('msg', '未知错误')}")

                self._token = result["tenant_access_token"]
                # token有效期通常是7200秒，这里设置为7000秒以提前刷新
                self._token_expires_at = current_time + 7000
                return self._token
        except Exception as e:
            self.logger.error(f"获取飞书tenant_access_token失败: {e}")
            raise

    async def _get_img_key(self, pic_url: str):
        """下载并上传图片到飞书，返回img_key"""
        # 下载图片
        self.logger.info(f"【推送_{self.name}】开始下载图片：{pic_url}")
        temp_file = None
        try:
            session = await self._get_session()
            async with session.get(pic_url, ssl=False) as response:
                response.raise_for_status()
                content_type = response.headers.get("Content-Type", "")
                extension = mimetypes.guess_extension(content_type)
                if not extension:
                    extension = ".jpg"

                # 创建临时文件
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=extension)
                async for chunk in response.content.iter_chunked(8192):
                    temp_file.write(chunk)
                temp_file.close()

            self.logger.info(f"【推送_{self.name}】下载图片{pic_url}成功")

            # 上传图片
            tenant_access_token = await self._get_tenant_access_token()
            if tenant_access_token is None:
                if temp_file:
                    os.unlink(temp_file.name)
                return None

            url = "https://open.feishu.cn/open-apis/im/v1/images"
            headers = {"Authorization": f"Bearer {tenant_access_token}"}

            # 使用 FormData 上传文件
            form_data = FormData()
            form_data.add_field("image_type", "message")
            form_data.add_field(
                "image",
                open(temp_file.name, "rb"),
                filename=f"{uuid.uuid4()}{extension}",
                content_type=content_type,
            )

            async with session.post(url, headers=headers, data=form_data) as response:
                response.raise_for_status()
                result = await response.json()

                if result.get("code") != 0:
                    raise Exception(f"上传图片失败: {result.get('msg', '未知错误')}")

                img_key = result["data"]["image_key"]
                self.logger.info(f"【推送_{self.name}】上传图片成功，img_key: {img_key}")
                return img_key
        except Exception as e:
            self.logger.error(f"【推送_{self.name}】处理图片失败: {e}")
            return None
        finally:
            # 删除临时文件
            if temp_file and os.path.exists(temp_file.name):
                os.unlink(temp_file.name)

    async def push(self, title, content, jump_url=None, pic_url=None, extend_data=None):
        """推送消息"""
        tenant_access_token = await self._get_tenant_access_token()
        if tenant_access_token is None:
            raise Exception("获取tenant_access_token失败")

        url = f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type={self.receive_id_type}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {tenant_access_token}",
        }
        card_elements = [{"tag": "markdown", "content": content}]

        if pic_url is not None:
            img_key = await self._get_img_key(pic_url)
            if img_key is not None:
                card_elements.append(
                    {
                        "alt": {"content": "", "tag": "plain_text"},
                        "img_key": img_key,
                        "tag": "img",
                    }
                )

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

        card_content = {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": "blue",
                "title": {"content": title, "tag": "plain_text"},
            },
            "elements": card_elements,
        }
        body = {
            "receive_id": self.receive_id,
            "msg_type": "interactive",
            "content": json.dumps(card_content),
        }

        try:
            session = await self._get_session()
            async with session.post(url, headers=headers, json=body) as response:
                response.raise_for_status()
                result = await response.json()

                if result.get("code") != 0:
                    error_msg = result.get("msg", "未知错误")
                    raise Exception(f"推送失败: {error_msg}")

                self.logger.info(f"【推送_{self.name}】成功")
                return {"status": "success"}
        except ClientResponseError as e:
            self.logger.error(f"【推送_{self.name}】请求失败: {e}")
            raise
        except Exception as e:
            self.logger.error(f"【推送_{self.name}】推送失败: {e}")
            raise
