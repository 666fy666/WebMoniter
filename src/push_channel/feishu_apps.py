import json
import mimetypes
import time
import uuid

from aiohttp import ClientResponseError, FormData

from . import PushChannel


class FeishuApps(PushChannel):
    """飞书自建应用推送通道（消息体与单条内容有大小限制，见飞书开放文档）"""

    max_content_bytes = 12000  # 单条内容保守限制

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

    def _get_error_suggestion(self, error_code: int, error_msg: str) -> str:
        """根据错误码返回友好的错误提示和解决建议"""
        error_suggestions = {
            230006: (
                "机器人能力未激活",
                "请在飞书开发者后台启用机器人能力：\n"
                "1. 登录 https://open.feishu.cn/app\n"
                "2. 进入应用详情页\n"
                "3. 在左侧导航栏进入「功能」>「机器人」\n"
                "4. 启用「机器人」能力\n"
                "5. 创建并发布新版本使配置生效\n"
                "参考文档：https://open.feishu.cn/document/uAjLw4CM/ugTN1YjL4UTN24CO1UjN/trouble-shooting/how-to-enable-bot-ability",
            ),
            234007: (
                "应用未启用机器人功能",
                "请在飞书开发者后台启用机器人能力：\n"
                "1. 登录 https://open.feishu.cn/app\n"
                "2. 进入应用详情页\n"
                "3. 在左侧导航栏进入「功能」>「机器人」\n"
                "4. 启用「机器人」能力\n"
                "5. 创建并发布新版本使配置生效\n"
                "参考文档：https://open.feishu.cn/document/uAjLw4CM/ugTN1YjL4UTN24CO1UjN/trouble-shooting/how-to-enable-bot-ability",
            ),
            230013: (
                "用户不在机器人可用范围内",
                "请检查应用的可用范围配置：\n"
                "1. 登录 https://open.feishu.cn/app\n"
                "2. 进入应用详情页\n"
                "3. 在左侧导航栏进入「应用发布」>「版本管理与发布」\n"
                "4. 编辑版本详情，配置「可用范围」\n"
                "5. 确保目标用户（receive_id）在可用范围内\n"
                "6. 保存并发布应用",
            ),
            230002: (
                "机器人不在群组中",
                "请将机器人添加到目标群组：\n"
                "1. 在飞书客户端中打开目标群组\n"
                "2. 点击群设置\n"
                "3. 添加机器人到群组\n"
                "4. 确保机器人有发言权限",
            ),
            230027: (
                "缺少必要权限",
                "请检查应用权限配置：\n"
                "1. 登录 https://open.feishu.cn/app\n"
                "2. 进入应用详情页\n"
                "3. 在左侧导航栏进入「权限管理」\n"
                "4. 确保已申请以下权限：\n"
                "   - 获取与发送单聊、群组消息(im:message)\n"
                "   - 以应用的身份发消息(im:message:send_as_bot)\n"
                "   - 发送消息V2(im:message:send)\n"
                "5. 创建并发布新版本使权限生效",
            ),
        }

        if error_code in error_suggestions:
            title, suggestion = error_suggestions[error_code]
            return f"{title}（错误码：{error_code}）\n错误信息：{error_msg}\n\n解决方案：\n{suggestion}"
        else:
            return f"错误码：{error_code}\n错误信息：{error_msg}"

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
        try:
            session = await self._get_session()
            async with session.get(pic_url, ssl=False) as response:
                response.raise_for_status()
                content_type = response.headers.get("Content-Type", "")
                extension = mimetypes.guess_extension(content_type)
                if not extension:
                    extension = ".jpg"

                # 直接读取图片内容为字节
                image_data = await response.read()

                # 检查图片大小（飞书限制10MB）
                image_size_mb = len(image_data) / (1024 * 1024)
                if image_size_mb > 10:
                    raise Exception(f"图片大小 {image_size_mb:.2f}MB 超过限制（10MB）")
                if len(image_data) == 0:
                    raise Exception("图片大小为0，无法上传")

            self.logger.info(
                f"【推送_{self.name}】下载图片{pic_url}成功，大小: {image_size_mb:.2f}MB"
            )

            # 上传图片
            tenant_access_token = await self._get_tenant_access_token()
            if tenant_access_token is None:
                return None

            url = "https://open.feishu.cn/open-apis/im/v1/images"
            headers = {"Authorization": f"Bearer {tenant_access_token}"}

            # 使用 FormData 上传文件
            form_data = FormData()
            form_data.add_field("image_type", "message")
            form_data.add_field(
                "image",
                image_data,
                filename=f"{uuid.uuid4()}{extension}",
                content_type=content_type or "image/jpeg",
            )

            async with session.post(url, headers=headers, data=form_data) as response:
                # 读取响应内容
                response_text = await response.text()

                # 尝试解析 JSON
                try:
                    result = json.loads(response_text)
                except json.JSONDecodeError:
                    result = {"code": response.status, "msg": response_text}

                if response.status != 200:
                    error_detail = result.get("msg", "未知错误")
                    error_code = result.get("code", response.status)
                    suggestion = self._get_error_suggestion(error_code, error_detail)
                    raise Exception(f"上传图片失败: HTTP {response.status}\n{suggestion}")

                if result.get("code") != 0:
                    error_msg = result.get("msg", "未知错误")
                    error_code = result.get("code", "未知")
                    suggestion = self._get_error_suggestion(error_code, error_msg)
                    raise Exception(f"上传图片失败\n{suggestion}")

                img_key = result["data"]["image_key"]
                self.logger.info(f"【推送_{self.name}】上传图片成功，img_key: {img_key}")
                return img_key
        except ClientResponseError as e:
            error_detail = f"HTTP {e.status}, message='{e.message}', url='{e.request_info.url}'"
            self.logger.error(f"【推送_{self.name}】处理图片失败: {error_detail}")
            # 尝试从错误消息中提取错误码
            if e.status == 400:
                suggestion = self._get_error_suggestion(230006, e.message)
                self.logger.error(f"【推送_{self.name}】{suggestion}")
            return None
        except Exception as e:
            self.logger.error(f"【推送_{self.name}】处理图片失败: {e}")
            return None

    async def push(self, title, content, jump_url=None, pic_url=None, extend_data=None):
        """推送消息"""
        tenant_access_token = await self._get_tenant_access_token()
        if tenant_access_token is None:
            raise Exception("获取tenant_access_token失败")

        url = f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type={self.receive_id_type}"
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {tenant_access_token}",
        }
        card_elements = []

        # 先添加图片（如果有），图片会显示在顶部
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

        # 然后添加 markdown 内容
        card_elements.append({"tag": "markdown", "content": content})

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
                # 读取响应内容
                response_text = await response.text()

                # 尝试解析 JSON
                try:
                    result = json.loads(response_text)
                except json.JSONDecodeError:
                    result = {"code": response.status, "msg": response_text}

                if response.status != 200:
                    error_detail = result.get("msg", "未知错误")
                    error_code = result.get("code", response.status)
                    suggestion = self._get_error_suggestion(error_code, error_detail)
                    error_info = (
                        f"HTTP {response.status}, code={error_code}, message='{error_detail}'"
                    )
                    self.logger.error(f"【推送_{self.name}】请求失败: {error_info}")
                    self.logger.error(f"【推送_{self.name}】{suggestion}")
                    raise Exception(f"飞书自建应用推送失败: {error_info}\n{suggestion}")

                if result.get("code") != 0:
                    error_msg = result.get("msg", "未知错误")
                    error_code = result.get("code", "未知")
                    suggestion = self._get_error_suggestion(error_code, error_msg)
                    error_info = f"code={error_code}, msg={error_msg}"
                    self.logger.error(f"【推送_{self.name}】推送失败: {error_info}")
                    self.logger.error(f"【推送_{self.name}】{suggestion}")
                    raise Exception(f"飞书自建应用推送失败: {error_info}\n{suggestion}")

                self.logger.debug(f"【推送_{self.name}】成功")
                return {"status": "success"}
        except ClientResponseError as e:
            error_info = f"HTTP {e.status}, message='{e.message}', url='{e.request_info.url}'"
            self.logger.error(f"【推送_{self.name}】请求失败: {error_info}")
            # 尝试从错误消息中提取错误码（常见错误码）
            if e.status == 400:
                suggestion = self._get_error_suggestion(230006, e.message)
                self.logger.error(f"【推送_{self.name}】{suggestion}")
                raise Exception(f"飞书自建应用推送失败: {error_info}\n{suggestion}")
            raise Exception(f"飞书自建应用推送失败: {error_info}")
        except Exception as e:
            self.logger.error(f"【推送_{self.name}】推送失败: {e}")
            raise
