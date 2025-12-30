"""微博监控模块"""

import asyncio
from datetime import datetime

import aiohttp
from aiohttp import ClientSession, ClientTimeout

from src.config import AppConfig, get_config, is_in_quiet_hours
from src.cookie_cache_manager import cookie_cache
from src.monitor import BaseMonitor


class CookieExpiredError(Exception):
    """Cookie失效异常"""

    pass


class WeiboMonitor(BaseMonitor):
    """微博监控类"""

    def __init__(self, config: AppConfig, session: ClientSession | None = None):
        super().__init__(config, session)
        self.weibo_config = config.get_weibo_config()
        self.old_data_dict: dict[str, tuple] = {}
        # Cookie失效处理标志和锁，确保只处理一次
        self._cookie_expired_handled = False
        self._cookie_expired_lock = asyncio.Lock()
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
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
                    "Accept": "application/json, text/plain, */*",
                    "Referer": "https://www.weibo.com/",
                    "Cookie": self.weibo_config.cookie,
                    "X-Requested-With": "XMLHttpRequest",
                },
                timeout=ClientTimeout(total=10),
            )
            self._own_session = True
        else:
            # 如果session已存在，更新Cookie（用于热重载）
            self.session.headers["Cookie"] = self.weibo_config.cookie
        return self.session

    async def load_old_info(self):
        """从数据库加载旧信息"""
        try:
            sql = "SELECT UID, 用户名, 认证信息, 简介, 粉丝数, 微博数, 文本, mid FROM weibo"
            results = await self.db.execute_query(sql)
            self.old_data_dict = {row[0]: row for row in results}
            # 检查是否是首次创建数据库（表为空）
            self._is_first_time = len(self.old_data_dict) == 0
        except Exception as e:
            self.logger.error(f"加载旧数据失败: {e}")
            self.old_data_dict = {}
            self._is_first_time = True  # 出错时也认为是首次创建

    async def get_info(self, uid: str) -> dict:
        """获取微博信息"""
        session = await self._get_session()
        info_url = f"https://www.weibo.com/ajax/profile/info?uid={uid}"
        con_url = f"https://www.weibo.com/ajax/statuses/mymblog?uid={uid}&page=1&feature=0"

        # 并发请求两个接口
        async with session.get(info_url) as info_resp, session.get(con_url) as con_resp:
            info_resp.raise_for_status()
            con_resp.raise_for_status()

            res_info = await info_resp.json()
            res_list = await con_resp.json()

            # 检测cookie是否失效
            if res_info.get("ok") == -100 or res_list.get("ok") == -100:
                raise CookieExpiredError("微博Cookie已失效，需要重新登录")

        # 解析用户信息
        user_info = res_info["data"]["user"]
        data = {
            "UID": user_info["idstr"],
            "用户名": user_info["screen_name"],
            "认证信息": user_info.get("verified_reason", "人气博主"),
            "简介": user_info["description"] if user_info["description"] else "peace and love",
            "粉丝数": user_info["followers_count_str"],
            "微博数": str(user_info["statuses_count"]),
        }

        # 解析最新微博内容
        wb_list = res_list["data"]["list"]
        if not wb_list:
            data["文本"] = "无内容"
            data["mid"] = "0"
            return data

        # 找到第一个非置顶微博
        target_idx = 0
        for idx, item in enumerate(wb_list):
            if item.get("isTop", 0) == 1:
                continue
            else:
                target_idx = idx
                break

        target_wb = wb_list[target_idx]

        spacing = "\n          "
        text = "          " + target_wb["text_raw"]

        # 图片处理
        pic_ids = target_wb.get("pic_ids", [])
        if pic_ids:
            text += f"{spacing}[图片]  *  {len(pic_ids)}      (详情请点击噢!)"

        # URL 结构处理
        url_struct = target_wb.get("url_struct", [])
        if url_struct:
            text += f"{spacing}#{url_struct[0]['url_title']}#"

        text += f"{spacing}           {target_wb['created_at']}"

        data["文本"] = text
        data["mid"] = str(target_wb["mid"])

        return data

    def check_info(self, data: dict, old_info: tuple) -> int:
        """
        比对信息
        返回差值：正数表示新增，负数表示删除，0表示无变化
        """
        if len(old_info) < 7:
            return 1  # 数据不完整，默认有变化

        old_text = old_info[6] if len(old_info) > 6 else ""
        if data["文本"] != old_text:
            try:
                old_count = int(old_info[5]) if len(old_info) > 5 else 0
                new_count = int(data["微博数"])
                return new_count - old_count
            except (ValueError, TypeError):
                return 1  # 无法计算时默认有变化
        return 0

    async def process_user(self, uid: str):
        """处理单个用户"""
        try:
            new_data = await self.get_info(uid)
            # 成功获取数据，如果之前被标记为过期，现在标记为有效
            if not cookie_cache.is_valid("weibo"):
                await cookie_cache.mark_valid("weibo")
                self.logger.info("微博Cookie已恢复有效")
                # Cookie恢复有效时，重置处理标志
                self._cookie_expired_handled = False
        except CookieExpiredError as e:
            # Cookie失效，统一处理（只记录一次日志，只发送一次推送）
            async with self._cookie_expired_lock:
                # 双重检查，确保只处理一次
                if not self._cookie_expired_handled:
                    self._cookie_expired_handled = True
                    self.logger.error(f"检测到Cookie失效: {e}")
                    await cookie_cache.mark_expired("weibo")
                    # 只有在未发送过提醒时才发送
                    if not cookie_cache.is_notified("weibo"):
                        await self.push_cookie_expired_notification()
                        await cookie_cache.mark_notified("weibo")
            return  # 不再抛出异常，直接返回
        except Exception as e:
            self.logger.error(f"获取用户 {uid} 数据失败: {e}")
            return

        if uid in self.old_data_dict:
            old_info = self.old_data_dict[uid]
            diff = self.check_info(new_data, old_info)

            if diff == 0:
                self.logger.debug(f"{new_data['用户名']} 最近在摸鱼🐟")
            else:
                # 更新数据
                sql = (
                    "UPDATE weibo SET 用户名=%(用户名)s, 认证信息=%(认证信息)s, 简介=%(简介)s, "
                    "粉丝数=%(粉丝数)s, 微博数=%(微博数)s, 文本=%(文本)s, mid=%(mid)s WHERE UID=%(UID)s"
                )
                await self.db.execute_update(sql, new_data)

                if diff > 0:
                    self.logger.info(f"{new_data['用户名']} 发布了{diff}条微博😍")
                else:
                    self.logger.info(f"{new_data['用户名']} 删除了{abs(diff)}条微博😞")

                await self.push_notification(new_data, diff)
        else:
            # 新用户插入
            sql = (
                "INSERT INTO weibo (UID, 用户名, 认证信息, 简介, 粉丝数, 微博数, 文本, mid) "
                "VALUES (%(UID)s, %(用户名)s, %(认证信息)s, %(简介)s, %(粉丝数)s, %(微博数)s, %(文本)s, %(mid)s)"
            )
            await self.db.execute_insert(sql, new_data)

            if self._is_first_time:
                self.logger.info(f"{new_data['用户名']} 新收录（首次创建数据库，跳过推送）")
            else:
                self.logger.info(f"{new_data['用户名']} 发布了新微博😍 (新收录)")
                await self.push_notification(new_data, 1)

    async def push_notification(self, data: dict, diff: int):
        """发送推送通知"""
        # 检查是否在免打扰时段内
        if is_in_quiet_hours(self.config):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            action = "发布" if diff > 0 else "删除"
            count = abs(diff)
            self.logger.info(
                f"[免打扰时段] {data['用户名']} {action}了{count}条weibo（{timestamp}），已跳过推送"
            )
            return

        action = "发布" if diff > 0 else "删除"
        count = abs(diff)

        try:
            await self.push.send_news(
                title=f"{data['用户名']} {action}了{count}条weibo",
                description=(
                    f"Ta说:👇\n{data['文本']}\n"
                    f"{'=' * 30}\n"
                    f"认证:{data['认证信息']}\n\n"
                    f"简介:{data['简介']}"
                ),
                picurl="https://cn.bing.com/th?id=OHR.DubrovnikHarbor_ZH-CN8590217905_1920x1080.jpg",
                to_url=f"https://m.weibo.cn/detail/{data['mid']}",
                btntxt="阅读全文",
            )
        except Exception as e:
            self.logger.error(f"推送失败: {e}")

    async def push_cookie_expired_notification(self):
        """发送Cookie失效提醒"""
        if not self.push:
            self.logger.warning("推送服务未初始化，无法发送Cookie失效提醒")
            return

        try:
            await self.push.send_news(
                title="⚠️ 微博Cookie已失效",
                description=(
                    "微博监控检测到Cookie已过期，需要重新登录更新Cookie。\n\n"
                    "请及时更新config.yml文件中的微博Cookie配置，以确保监控正常运行。"
                ),
                picurl="https://cn.bing.com/th?id=OHR.DubrovnikHarbor_ZH-CN8590217905_1920x1080.jpg",
                to_url="https://weibo.com/login.php",
                btntxt="前往登录",
            )
            self.logger.info("已发送Cookie失效提醒到企业微信")
        except Exception as e:
            self.logger.error(f"发送Cookie失效提醒失败: {e}")

    async def run(self):
        """运行监控"""
        # 热重载：重新加载config.yml文件中的配置（如果文件被修改）
        old_cookie = self.weibo_config.cookie
        new_config = get_config(reload=False)  # 使用自动检测，不需要强制重载
        self.config = new_config
        self.weibo_config = new_config.get_weibo_config()
        new_cookie = self.weibo_config.cookie

        # 检测Cookie是否变化
        if old_cookie != new_cookie:
            self.logger.info(
                f"检测到Cookie已更新，使用新的Cookie (旧Cookie长度: {len(old_cookie)}, 新Cookie长度: {len(new_cookie)})"
            )
            # Cookie更新后，重置过期状态和提醒状态
            # mark_valid会自动重置notified标志
            await cookie_cache.mark_valid("weibo")
            # 如果session已存在，更新headers中的Cookie
            if self.session is not None:
                self.session.headers["Cookie"] = new_cookie
                self.logger.debug("已更新session headers中的Cookie")
        else:
            self.logger.debug(f"Cookie未变化 (长度: {len(old_cookie)})")

        # 重置Cookie失效处理标志
        self._cookie_expired_handled = False

        self.logger.info(f"开始执行{self.monitor_name}")

        # 在执行任务前检查Cookie状态
        # 如果标记为无效，尝试验证一次（可能Cookie已恢复但缓存未更新）
        if not cookie_cache.is_valid("weibo"):
            self.logger.warning(f"{self.monitor_name} Cookie标记为过期，尝试验证...")
            # 尝试获取前几个用户的数据来验证Cookie是否真的无效（改进：不因单个用户失败就跳过所有）
            if self.weibo_config.uids:
                verification_success = False
                verification_errors = 0
                max_verification_attempts = min(3, len(self.weibo_config.uids))  # 最多尝试3个用户

                for i in range(max_verification_attempts):
                    try:
                        test_uid = self.weibo_config.uids[i]
                        await self.get_info(test_uid)
                        # 如果成功获取数据，说明Cookie实际有效，恢复状态
                        await cookie_cache.mark_valid("weibo")
                        self.logger.info("Cookie验证成功，已恢复有效状态")
                        verification_success = True
                        break
                    except CookieExpiredError:
                        verification_errors += 1
                        # 如果所有验证都失败，才跳过执行
                        if verification_errors >= max_verification_attempts:
                            self.logger.warning(
                                f"{self.monitor_name} Cookie验证失败（已尝试{verification_errors}个用户），跳过本次执行"
                            )
                            self.logger.info("─" * 30)
                            return
                    except Exception as e:
                        # 其他错误（如网络错误），不立即跳过，继续尝试下一个用户
                        self.logger.debug(
                            f"Cookie验证时发生错误（用户{self.weibo_config.uids[i]}）: {e}，继续尝试..."
                        )
                        verification_errors += 1
                        if verification_errors >= max_verification_attempts:
                            self.logger.warning(
                                f"{self.monitor_name} Cookie验证失败（已尝试{verification_errors}个用户），跳过本次执行"
                            )
                            self.logger.info("─" * 30)
                            return

                if not verification_success:
                    self.logger.warning(f"{self.monitor_name} Cookie验证未成功，跳过本次执行")
                    self.logger.info("─" * 30)
                    return
            else:
                # 没有用户ID，无法验证，跳过执行
                self.logger.warning(f"{self.monitor_name} 无用户ID，跳过本次执行")
                self.logger.info("─" * 30)
                return
        try:
            # 检查是否有用户需要监控
            if not self.weibo_config.uids:
                self.logger.warning(f"{self.monitor_name} 没有配置用户ID，跳过本次执行")
                self.logger.info("─" * 30)
                return

            # 创建信号量控制并发数
            semaphore = asyncio.Semaphore(self.weibo_config.concurrency)

            async def process_with_semaphore(uid: str):
                """使用信号量包装的处理函数"""
                async with semaphore:
                    return await self.process_user(uid)

            tasks = [process_with_semaphore(uid) for uid in self.weibo_config.uids]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # 检查并记录异常
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    self.logger.error(f"处理用户 {self.weibo_config.uids[i]} 时出错: {result}")
        except Exception as e:
            self.logger.error(f"{self.monitor_name}执行失败: {e}")
            raise
        finally:
            self.logger.info(f"执行完成{self.monitor_name}")
            self.logger.info("─" * 30)

    @property
    def monitor_name(self) -> str:
        """监控器名称"""
        return "微博监控🖼️  🖼️  🖼️"
