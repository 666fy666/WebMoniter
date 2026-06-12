"""虎牙直播监控模块"""

import asyncio
import json
import logging
import re
from datetime import datetime

import aiohttp
from aiohttp import ClientSession, ClientTimeout

from src.monitors.base import BaseMonitor, CookieExpiredError
from src.settings.config import AppConfig, get_config, is_in_quiet_hours

# 硬编码的 User-Agent
HUYA_USER_AGENT = "Mozilla/5.0 (Linux; Android 5.0; SM-G900P Build/LRX21T) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Mobile Safari/537.36"
# 硬编码的 Cookie（空字符串，不需要 cookie）
HUYA_COOKIE = ""

# 预编译正则表达式
RE_PROFILE = re.compile(r'"tProfileInfo":({.*?})')
RE_STATUS = re.compile(r'"eLiveStatus":(\d+)')
# 当前房间的封面：来自 roomInfo.tLiveInfo/tReplayInfo 的 sScreenshot（页面中第一个非空即当前房间）
RE_SCREENSHOT = re.compile(r'"sScreenshot":"(https?:\\u002F\\u002F[^"]+)"')

# 开播/下播推送无主播图时的默认图片
HUYA_DEFAULT_PIC = "https://cn.bing.com/th?id=OHR.DolbadarnCastle_ZH-CN5397592090_1920x1080.jpg"


class HuyaMonitor(BaseMonitor):
    """虎牙直播监控类"""

    def __init__(self, config: AppConfig, session: ClientSession | None = None):
        super().__init__(config, session)
        self.huya_config = config.get_huya_config()
        self.old_data_dict: dict[str, tuple] = {}
        self._is_first_time: bool = False  # 标记是否是首次创建数据库

    async def initialize(self):
        """初始化数据库和推送服务"""
        await super().initialize()
        # 加载旧数据
        await self.load_old_info()

    async def _get_session(self) -> ClientSession:
        """获取或创建session"""
        if self.session is None:
            self.session = aiohttp.ClientSession(
                headers={
                    "User-Agent": HUYA_USER_AGENT,
                    "Cookie": HUYA_COOKIE,
                },
                timeout=ClientTimeout(total=10),
            )
            self._own_session = True
        else:
            # 如果session已存在，更新User-Agent（用于热重载）
            self.session.headers["User-Agent"] = HUYA_USER_AGENT
            self.session.headers["Cookie"] = HUYA_COOKIE
        return self.session

    async def load_old_info(self):
        """从数据库加载旧信息"""
        try:
            sql = "SELECT room, name, is_live FROM huya"
            results = await self.db.execute_query(sql)
            self.old_data_dict = {row[0]: row for row in results}
            # 检查是否是首次创建数据库（表为空）
            self._is_first_time = len(self.old_data_dict) == 0
        except Exception as e:
            self.logger.error(f"加载旧数据失败: {e}")
            self.old_data_dict = {}
            self._is_first_time = True  # 出错时也认为是首次创建

    async def get_info(self, room_id: str) -> dict:
        """获取直播状态"""
        session = await self._get_session()
        url = f"https://m.huya.com/{room_id}"

        async with session.get(url) as response:
            response.raise_for_status()
            page_content = await response.text()

            # 检测cookie是否失效：如果返回403或页面包含登录相关关键词，可能cookie失效
            if response.status == 403:
                raise CookieExpiredError("虎牙Cookie已失效，返回403状态码")

            # 检查页面是否包含登录提示
            if "登录" in page_content and "请先登录" in page_content:
                raise CookieExpiredError("虎牙Cookie已失效，需要重新登录")

        # 使用预编译正则匹配
        profile_match = RE_PROFILE.search(page_content)
        status_match = RE_STATUS.search(page_content)

        if not profile_match or not status_match:
            raise ValueError(f"无法解析页面数据: {room_id}")

        profile_info = json.loads(profile_match.group(1))
        live_status = int(status_match.group(1))

        # 直播状态转换: 2代表正在直播 -> 存为 "1"，否则 "0"
        status_num = "1" if live_status == 2 else "0"

        # 每个主播对应图片：
        # - room_pic: 优先当前房间的 sScreenshot（直播/回放封面），其次 tProfileInfo.sAvatar180（主播头像）
        # - avatar_url: 始终使用 tProfileInfo.sAvatar180，用于 Bark 等通道作为 icon
        room_pic = ""
        screenshot_match = RE_SCREENSHOT.search(page_content)
        if screenshot_match:
            room_pic = screenshot_match.group(1).replace("\\u002F", "/")
        if not room_pic:
            room_pic = (profile_info.get("sAvatar180") or "").strip()

        avatar_url = (profile_info.get("sAvatar180") or "").strip()

        return {
            "room": room_id,
            "name": profile_info["sNick"],
            "is_live": status_num,
            # 用于推送和前端展示的封面图/头像链接
            "room_pic": room_pic,
            "avatar_url": avatar_url,
        }

    def check_info(self, data: dict, old_info: tuple) -> int:
        """
        比对信息
        返回值: 1(开播), 0(下播), 2(无变化)
        """
        old_status = str(old_info[2]) if len(old_info) > 2 else "0"
        if str(data["is_live"]) != old_status:
            return 1 if data["is_live"] == "1" else 0
        return 2

    async def process_room(self, room_id: str):
        """处理单个房间"""
        try:
            data = await self.get_info(room_id)
            # 成功获取数据，如果之前被标记为过期，现在标记为有效
            await self.mark_cookie_valid()
        except CookieExpiredError as e:
            # Cookie失效，使用基类统一处理
            await self.handle_cookie_expired(e)
            return  # 不再抛出异常，直接返回
        except Exception as e:
            self.logger.debug(f"获取房间 {room_id} 信息失败: {e}")
            return

        if room_id in self.old_data_dict:
            old_info = self.old_data_dict[room_id]
            res = self.check_info(data, old_info)

            if res == 2:
                self.logger.debug(f"{data['name']} 最近直播状态没变化🐟")
            else:
                # 状态或头像/封面发生变化，更新数据库
                sql = (
                    "UPDATE huya SET name=%(name)s, is_live=%(is_live)s, "
                    "room_pic=%(room_pic)s, avatar_url=%(avatar_url)s "
                    "WHERE room=%(room)s"
                )
                await self.db.execute_update(sql, data)

                status_msg = "开播啦🐯🐯🐯" if res == 1 else "下播了🐟🐟🐟"
                self.logger.info(f"{data['name']} {status_msg}")

                await self.push_notification(data, res)
        else:
            # 新录入
            sql = (
                "INSERT INTO huya (room, name, is_live, room_pic, avatar_url) "
                "VALUES (%(room)s, %(name)s, %(is_live)s, %(room_pic)s, %(avatar_url)s)"
            )
            await self.db.execute_insert(sql, data)

            if self._is_first_time:
                self.logger.info(f"新录入主播: {data['name']}（首次创建数据库，跳过推送）")
            else:
                self.logger.info(f"新录入主播: {data['name']}")
                await self.push_notification(data, 1)

    async def push_notification(self, data: dict, res: int):
        """发送推送通知"""
        # 检查是否在免打扰时段内
        if is_in_quiet_hours(self.config):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            status_text = "开播了🐯🐯🐯" if res == 1 else "下播了🐟🐟🐟"
            self.logger.info(
                f"[免打扰时段] {data['name']} {status_text}（{timestamp}），已跳过推送"
            )
            return

        # 异步获取语录
        quote = " "
        try:
            session = await self._get_session()
            async with session.get(
                "https://v1.hitokoto.cn/", timeout=ClientTimeout(total=30)
            ) as resp:
                if resp.status == 200:
                    hitokoto = await resp.json()
                    quote = f'\n{hitokoto.get("hitokoto", "")} —— {hitokoto.get("from", "")}\n'
        except Exception as e:
            self.logger.debug(f"[{data['name']}] 获取语录失败: {e}")

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status_text = "开播了🐯🐯🐯" if res == 1 else "下播了🐟🐟🐟"
        picurl = (data.get("room_pic") or "").strip() or HUYA_DEFAULT_PIC
        avatar_url = (data.get("avatar_url") or "").strip()

        try:
            extend_data = {}
            # 为 Bark 等通道传递主播头像 URL，用作 icon
            if avatar_url:
                extend_data["avatar_url"] = avatar_url

            await self.push.send_news(
                title=f"{data['name']} {status_text}",
                description=f"房间号: {data['room']}\n\n{quote}\n\n{timestamp}",
                to_url=f"https://m.huya.com/{data['room']}",
                picurl=picurl,
                extend_data=extend_data or None,
                event_type="huya",
                event_data={
                    "name": data.get("name"),
                    "room": data.get("room"),
                    "is_live": res == 1,
                    "status_text": "开播" if res == 1 else "下播",
                    "timestamp": timestamp,
                },
            )
        except Exception as e:
            self.logger.error(f"推送失败: {e}")

    async def push_cookie_expired_notification(self):
        """发送Cookie失效提醒"""
        await super().push_cookie_expired_notification()  # 调用基类方法检查推送服务
        if not self.push:
            return

        try:
            await self.push.send_news(
                title="⚠️ 虎牙Cookie已失效",
                description=(
                    "虎牙监控检测到Cookie已过期，需要重新登录更新Cookie。\n\n"
                    "请及时更新config.yml文件中的虎牙Cookie配置，以确保监控正常运行。"
                ),
                picurl=HUYA_DEFAULT_PIC,
                to_url="https://www.huya.com/login",
                btntxt="前往登录",
            )
            self.logger.info("已发送Cookie失效提醒")
        except Exception as e:
            self.logger.error(f"发送Cookie失效提醒失败: {e}")

    @property
    def platform_name(self) -> str:
        """平台名称"""
        return "huya"

    @property
    def push_channel_names(self) -> list[str] | None:
        """推送通道名称列表"""
        channels = getattr(self.config, "huya_push_channels", None)
        return channels if channels else None

    async def run(self):
        """运行监控"""
        # 热重载：重新加载config.yml文件中的配置（如果文件被修改）
        new_config = get_config(reload=False)  # 使用自动检测，不需要强制重载
        self.config = new_config
        self.huya_config = new_config.get_huya_config()

        # 如果session已存在，确保headers中的User-Agent和Cookie是最新的
        if self.session is not None:
            self.session.headers["User-Agent"] = HUYA_USER_AGENT
            self.session.headers["Cookie"] = HUYA_COOKIE

        self.logger.debug("开始执行 %s", self.monitor_name)

        # 在执行任务前检查Cookie状态
        # 如果标记为无效，尝试验证一次（可能Cookie已恢复但缓存未更新）
        from src.storage.cookie_cache import get_cookie_cache

        cookie_cache = get_cookie_cache()
        if not cookie_cache.is_valid(self.platform_name):
            self.logger.warning(f"{self.monitor_name} Cookie标记为过期，尝试验证...")
            # 尝试获取前几个房间的数据来验证Cookie是否真的无效（改进：不因单个房间失败就跳过所有）
            if self.huya_config.rooms:
                verification_success = False
                verification_errors = 0
                max_verification_attempts = min(3, len(self.huya_config.rooms))  # 最多尝试3个房间

                for i in range(max_verification_attempts):
                    try:
                        test_room = self.huya_config.rooms[i]
                        await self.get_info(test_room)
                        # 如果成功获取数据，说明Cookie实际有效，恢复状态
                        await self.mark_cookie_valid()
                        self.logger.info("Cookie验证成功，已恢复有效状态")
                        verification_success = True
                        break
                    except CookieExpiredError:
                        verification_errors += 1
                        # 如果所有验证都失败，才跳过执行
                        if verification_errors >= max_verification_attempts:
                            self.logger.warning(
                                "%s Cookie验证失败（已尝试%d个房间），跳过本次执行",
                                self.monitor_name,
                                verification_errors,
                            )
                            return
                    except Exception as e:
                        self.logger.debug(
                            "Cookie验证时发生错误（房间%s）: %s，继续尝试",
                            self.huya_config.rooms[i],
                            e,
                        )
                        verification_errors += 1
                        if verification_errors >= max_verification_attempts:
                            self.logger.warning(
                                "%s Cookie验证失败（已尝试%d个房间），跳过本次执行",
                                self.monitor_name,
                                verification_errors,
                            )
                            return

                if not verification_success:
                    self.logger.warning("%s Cookie验证未成功，跳过本次执行", self.monitor_name)
                    return
            else:
                self.logger.warning("%s 无房间ID，跳过本次执行", self.monitor_name)
                return
        try:
            if not self.huya_config.rooms:
                self.logger.warning("%s 没有配置房间ID，跳过本次执行", self.monitor_name)
                return

            # 创建信号量控制并发数
            semaphore = asyncio.Semaphore(self.huya_config.concurrency)

            async def process_with_semaphore(room_id: str):
                """使用信号量包装的处理函数"""
                async with semaphore:
                    return await self.process_room(room_id)

            tasks = [process_with_semaphore(room_id) for room_id in self.huya_config.rooms]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # 检查并记录异常
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    self.logger.error(f"处理房间 {self.huya_config.rooms[i]} 时出错: {result}")
        except Exception as e:
            self.logger.error("%s 执行失败: %s", self.monitor_name, e)
            raise
        finally:
            self.logger.debug("执行完成 %s", self.monitor_name)

    @property
    def monitor_name(self) -> str:
        """监控器名称"""
        return "虎牙直播监控🐯  🐯  🐯"


async def run_huya_monitor() -> None:
    """运行虎牙监控任务（支持配置热重载）。由调度器与注册表调用。"""
    config = get_config(reload=True)
    logger_instance = logging.getLogger(__name__)
    logger_instance.debug("虎牙监控：已重新加载配置文件")
    async with HuyaMonitor(config) as monitor:
        await monitor.run()


def _get_huya_trigger_kwargs(config: AppConfig) -> dict:
    """供注册表与配置热重载使用。"""
    return {"seconds": config.huya_monitor_interval_seconds}


# 自注册到任务注册表（由 src.jobs.registry.discover_and_import 导入时执行）
from src.jobs.registry import register_monitor

register_monitor(
    "huya_monitor",
    run_huya_monitor,
    _get_huya_trigger_kwargs,
    description="虎牙直播状态监控",
)
