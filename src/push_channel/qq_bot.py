import time

from aiohttp import ClientResponseError

from . import PushChannel


class QQBot(PushChannel):
    """QQ 机器人推送通道"""

    def __init__(self, config, session=None):
        super().__init__(config, session)
        self.base_url = str(config.get("base_url", "")).rstrip("/")
        self.app_id = str(config.get("app_id", ""))
        self.app_secret = str(config.get("app_secret", ""))
        self.push_target_list = config.get("push_target_list", [])
        self.channel_id_name_dict = {}
        self._initialized = False
        self._access_token: str | None = None
        self._token_expires_at: float = 0
        if (
            self.base_url == ""
            or self.app_id == ""
            or self.app_secret == ""
            or len(self.push_target_list) == 0
        ):
            self.logger.error(f"【推送_{self.name}】配置不完整，推送功能将无法正常使用")

    async def _get_access_token(self):
        """获取QQ频道机器人 access_token"""
        current_time = time.time()

        # 如果token还有效（提前5分钟刷新），直接返回
        if self._access_token and current_time < self._token_expires_at - 300:
            return self._access_token

        url = "https://api.q.qq.com/api/gettoken"
        params = {
            "grant_type": "client_credential",
            "appid": self.app_id,
            "secret": self.app_secret,
        }

        try:
            session = await self._get_session()
            async with session.get(url, params=params) as response:
                response.raise_for_status()
                result = await response.json()

                if result.get("errcode") != 0:
                    raise Exception(f"获取access_token失败: {result.get('errmsg', '未知错误')}")

                self._access_token = result["access_token"]
                # token有效期通常是7200秒，这里设置为7000秒以提前刷新
                expires_in = result.get("expires_in", 7200)
                self._token_expires_at = current_time + min(expires_in - 200, 7000)
                return self._access_token
        except Exception as e:
            self.logger.error(f"获取QQ频道机器人access_token失败: {e}")
            raise

    async def get_headers(self):
        """获取请求头（异步方法，需要先获取access_token）"""
        access_token = await self._get_access_token()
        return {"Authorization": f"Bot {self.app_id}.{access_token}"}

    async def initialize(self):
        """初始化目标频道（异步）"""
        if self._initialized:
            return

        if not self.base_url or not self.app_id or not self.app_secret or not self.push_target_list:
            return

        try:
            # 初始化目标频道
            guild_id_name_dict = await self._init_guild_id_name_dict()
            for guild_id, guild_name in guild_id_name_dict.items():
                await self._init_channels(guild_id, guild_name)

            if len(self.channel_id_name_dict) == 0:
                self.logger.error(f"【推送_{self.name}】未找到推送目标频道，推送功能将无法正常使用")
            else:
                self.logger.info(
                    f"【推送_{self.name}】初始化完成，找到 {len(self.channel_id_name_dict)} 个目标频道"
                )
                self._initialized = True
        except Exception as e:
            self.logger.error(f"【推送_{self.name}】初始化失败: {e}")

    async def _init_guild_id_name_dict(self) -> dict:
        """初始化频道ID和名称字典"""
        guild_name_list = [str(item["guild_name"]) for item in self.push_target_list]
        guild_id_name_dict = {}

        url = f"{self.base_url}/users/@me/guilds"
        try:
            session = await self._get_session()
            headers = await self.get_headers()
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                result = await response.json()
                for item in result:
                    if item["name"] in guild_name_list:
                        guild_id_name_dict[item["id"]] = item["name"]
        except Exception as e:
            self.logger.error(f"【推送_{self.name}】获取频道列表失败: {e}")

        return guild_id_name_dict

    async def _init_channels(self, guild_id, guild_name):
        """初始化子频道"""
        channel_name_list = [
            str(channel)
            for item in self.push_target_list
            if item["guild_name"] == guild_name
            for channel in item["channel_name_list"]
        ]

        url = f"{self.base_url}/guilds/{guild_id}/channels"
        try:
            session = await self._get_session()
            headers = await self.get_headers()
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                result = await response.json()
                for item in result:
                    # 只获取文字子频道
                    if item["name"] in channel_name_list and item["type"] == 0:
                        self.channel_id_name_dict[item["id"]] = f'{guild_name}->{item["name"]}'
        except Exception as e:
            self.logger.error(f"【推送_{self.name}】获取子频道列表失败: {e}")

    async def push(self, title, content, jump_url=None, pic_url=None, extend_data=None):
        """推送消息"""
        # 如果未初始化，先初始化
        if not self._initialized:
            await self.initialize()

        if not self.channel_id_name_dict:
            self.logger.warning(f"【推送_{self.name}】未找到推送目标频道，跳过推送")
            return

        errors = []
        auth_headers = await self.get_headers()
        for channel_id, channel_name in self.channel_id_name_dict.items():
            push_url = f"{self.base_url}/channels/{channel_id}/messages"
            headers = {"Content-Type": "application/json"}
            headers.update(auth_headers)
            body = {"content": f"{title}\n\n{content}"}

            if pic_url is not None:
                body["content"] += "\n\n"
                body["image"] = pic_url

            try:
                session = await self._get_session()
                async with session.post(push_url, headers=headers, json=body) as response:
                    response.raise_for_status()
                    self.logger.debug(f"【推送_{self.name}】【{channel_name}】成功")
            except ClientResponseError as e:
                error_msg = f"【推送_{self.name}】【{channel_name}】请求失败: {e}"
                self.logger.error(error_msg)
                errors.append(error_msg)
            except Exception as e:
                error_msg = f"【推送_{self.name}】【{channel_name}】推送失败: {e}"
                self.logger.error(error_msg)
                errors.append(error_msg)

        if errors:
            raise Exception(f"部分推送失败: {errors}")

        return {"status": "success"}
