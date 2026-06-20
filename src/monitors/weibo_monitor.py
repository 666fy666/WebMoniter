"""微博监控模块"""

import asyncio
import json
import logging
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import aiohttp
from aiohttp import ClientSession, ClientTimeout
from PIL import Image, ImageOps

from src.core.http import create_certifi_connector
from src.core.paths import DATA_DIR
from src.monitors.base import BaseMonitor, CookieExpiredError
from src.settings.config import AppConfig, get_config, is_in_quiet_hours


class WeiboMonitor(BaseMonitor):
    """微博监控类"""

    def __init__(self, config: AppConfig, session: ClientSession | None = None):
        super().__init__(config, session)
        self.weibo_config = config.get_weibo_config()
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
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
                    "Accept": "application/json, text/plain, */*",
                    "Referer": "https://www.weibo.com/",
                    "Cookie": self.weibo_config.cookie,
                    "X-Requested-With": "XMLHttpRequest",
                },
                timeout=ClientTimeout(total=10),
                connector=create_certifi_connector(),
            )
            self._own_session = True
        else:
            # 如果session已存在，更新Cookie（用于热重载）
            self.session.headers["Cookie"] = self.weibo_config.cookie
        return self.session

    async def load_old_info(self):
        """从数据库加载旧信息"""
        try:
            sql = "SELECT UID, 用户名, 认证信息, 简介, 粉丝数, 微博数, 文本, mid, 图片 FROM weibo"
            results = await self.db.execute_query(sql)
            self.old_data_dict = {row[0]: row for row in results}
            # 检查是否是首次创建数据库（表为空）
            self._is_first_time = len(self.old_data_dict) == 0
        except Exception as e:
            self.logger.error(f"加载旧数据失败: {e}")
            self.old_data_dict = {}
            self._is_first_time = True  # 出错时也认为是首次创建

    def _has_wecom_apps_channel(self) -> bool:
        """检查是否有企业微信应用推送通道"""
        if not self.push:
            return False
        # 检查 UnifiedPushManager 中是否有企业微信应用推送通道
        for channel in getattr(self.push, "push_channels", []):
            if channel.type == "wecom_apps":
                return True
        return False

    def _sanitize_username(self, username: str) -> str:
        """将用户名转换为适合作为文件夹名的安全字符串"""
        # 替换 Windows 与常见文件系统中的非法字符
        return re.sub(r'[\\/:*?"<>|]', "_", username).strip() or "unknown_user"

    def _get_weibo_data_dir(self) -> Path:
        """获取用于存放微博相关数据的根目录（data/weibo）"""
        data_dir = DATA_DIR / "weibo"
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir

    def _sanitize_path_part(self, value: str) -> str:
        """将微博 mid 等动态值转换为安全的单层路径名。"""
        safe_value = re.sub(r"[^0-9A-Za-z._-]", "_", str(value or "")).strip()
        return safe_value or "0"

    def _build_weibo_img_url(self, *parts: str) -> str:
        """构造 /weibo_img 静态图片 URL，路径片段统一做 URL 编码。"""
        return "/weibo_img/" + "/".join(quote(str(part), safe="") for part in parts)

    def _get_post_thumbnail_path(self, image_path: Path) -> Path:
        """正文原图旁边的缩略图路径。"""
        return image_path.with_name(f"{image_path.stem}.thumb.jpg")

    def _make_post_thumbnail(self, image_path: Path, thumb_path: Path) -> bool:
        """为微博正文图片生成列表缩略图；失败不影响原图展示。"""
        try:
            with Image.open(image_path) as img:
                img = ImageOps.exif_transpose(img)
                img.thumbnail((480, 480), Image.Resampling.LANCZOS)
                if img.mode in ("RGBA", "LA", "P"):
                    bg = Image.new("RGB", img.size, (255, 255, 255))
                    if img.mode == "P":
                        img = img.convert("RGBA")
                    bg.paste(img, mask=img.getchannel("A") if img.mode in ("RGBA", "LA") else None)
                    img = bg
                else:
                    img = img.convert("RGB")
                thumb_path.parent.mkdir(parents=True, exist_ok=True)
                img.save(thumb_path, "JPEG", quality=82, optimize=True)
            return True
        except Exception as e:
            self.logger.debug("生成微博正文图片缩略图失败（已忽略）: %s", e)
            return False

    def _add_pic_url(self, urls: list[str], url: str | None) -> None:
        """追加去重后的图片 URL，兼容微博返回的 // 开头地址。"""
        if not isinstance(url, str):
            return
        cleaned = url.strip()
        if not cleaned:
            return
        if cleaned.startswith("//"):
            cleaned = f"https:{cleaned}"
        if cleaned not in urls:
            urls.append(cleaned)

    def _collect_pic_candidates_from_info(self, info: dict) -> list[str]:
        """从单张微博图片信息里提取由高清到低清的候选 URL。"""
        candidates: list[str] = []
        if not isinstance(info, dict):
            return candidates

        for key in ("largest", "original", "mw2000", "mw1024", "large", "bmiddle", "thumbnail"):
            value = info.get(key)
            if isinstance(value, dict):
                self._add_pic_url(candidates, value.get("url") or value.get("src"))
            elif isinstance(value, str):
                self._add_pic_url(candidates, value)

        for key in ("url", "pic_url"):
            self._add_pic_url(candidates, info.get(key))

        return candidates

    def _extract_pic_url_candidates(
        self,
        pic_ids: list | None,
        pic_infos: dict | None,
        pics: list | None = None,
    ) -> list[list[str]]:
        """按微博图片顺序提取每张图的下载候选 URL；视频不参与处理。"""
        result: list[list[str]] = []
        safe_pic_infos = pic_infos if isinstance(pic_infos, dict) else {}
        ordered_ids = [str(pic_id) for pic_id in (pic_ids or []) if pic_id]
        if not ordered_ids and safe_pic_infos:
            ordered_ids = [str(pic_id) for pic_id in safe_pic_infos.keys()]

        for pic_id in ordered_ids:
            info = safe_pic_infos.get(pic_id)
            candidates = self._collect_pic_candidates_from_info(info)
            if candidates:
                result.append(candidates)

        if result or not isinstance(pics, list):
            return result

        for pic in pics:
            if not isinstance(pic, dict):
                continue
            if str(pic.get("type") or "").lower() == "video":
                continue
            candidates = self._collect_pic_candidates_from_info(pic)
            if candidates:
                result.append(candidates)
        return result

    def _remove_path(self, path: Path) -> None:
        """删除文件或目录；仅用于微博本地图片目录维护。"""
        if not path.exists():
            return
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()

    def _commit_post_image_dir(self, user_dir: Path, post_mid: str, temp_dir: Path | None) -> Path:
        """
        将临时图片目录切换为 posts/<mid>，并移除同一用户其他旧微博图片目录。

        temp_dir 为 None 时只保留当前 mid 目录；若当前 mid 目录不存在，则清空旧目录。
        """
        posts_dir = user_dir / "posts"
        posts_dir.mkdir(parents=True, exist_ok=True)
        target_dir = posts_dir / self._sanitize_path_part(post_mid)
        keep_names = {target_dir.name}
        if temp_dir is not None:
            keep_names.add(temp_dir.name)

        for child in posts_dir.iterdir():
            if child.name in keep_names:
                continue
            self._remove_path(child)

        if temp_dir is not None:
            if target_dir.exists():
                self._remove_path(target_dir)
            shutil.move(str(temp_dir), str(target_dir))

        return target_dir

    async def _download_image(self, url: str, save_path: Path) -> bool:
        """下载单张图片到指定路径，失败时仅记录日志；已存在则跳过。"""
        if not url:
            return False

        # 如果文件已存在，跳过下载，避免重复请求
        if save_path.exists():
            self.logger.debug("微博图片已存在，跳过下载: %s", save_path)
            return True

        try:
            session = await self._get_session()

            # 部分字段可能是用分号拼接的多个候选 URL，这里逐个尝试
            candidates = [u.strip() for u in str(url).split(";") if u.strip()]
            if not candidates:
                return False

            last_status: int | None = None

            for candidate in candidates:
                async with session.get(candidate) as resp:
                    last_status = resp.status
                    if resp.status != 200:
                        # 非 200 则尝试下一个候选
                        continue

                    content = await resp.read()
                    save_path.parent.mkdir(parents=True, exist_ok=True)
                    save_path.write_bytes(content)
                    self.logger.debug("已保存微博头像到: %s (URL: %s)", save_path, candidate)
                    return True

            # 所有候选都失败，记录最后一次状态码和原始 URL 串
            self.logger.warning(
                "下载微博头像失败，所有候选 URL 均返回非 200（最后状态码: %s）, 原始URL: %s",
                last_status,
                url,
            )
            return False
        except Exception as e:
            self.logger.warning("下载微博头像失败: %s, URL: %s", e, url)
            return False

    async def _download_post_image(self, candidates: list[str], save_path: Path) -> bool:
        """按候选 URL 下载一张最新微博图片，成功落盘后返回 True。"""
        urls: list[str] = []
        for item in candidates:
            for candidate in str(item).split(";"):
                self._add_pic_url(urls, candidate)
        if not urls:
            return False

        try:
            session = await self._get_session()
            last_status: int | None = None

            for candidate in urls:
                async with session.get(candidate) as resp:
                    last_status = resp.status
                    if resp.status != 200:
                        continue

                    content = await resp.read()
                    if not content:
                        continue

                    save_path.parent.mkdir(parents=True, exist_ok=True)
                    save_path.write_bytes(content)
                    self.logger.debug("已保存微博正文图片到: %s (URL: %s)", save_path, candidate)
                    return True

            self.logger.warning(
                "下载微博正文图片失败，所有候选 URL 均返回非 200（最后状态码: %s）",
                last_status,
            )
            return False
        except Exception as e:
            self.logger.warning("下载微博正文图片失败: %s", e)
            return False

    async def _save_post_images(self, data: dict) -> list[str]:
        """
        保存当前数据库微博对应的正文图片到 data/weibo/<用户名>/posts/<mid>/。

        先下载到临时目录，再替换当前 mid 目录；同一用户只保留数据库当前微博的图片。
        """
        username = data.get("用户名") or "unknown_user"
        safe_username = self._sanitize_username(username)
        post_mid = self._sanitize_path_part(data.get("mid") or "0")
        user_dir = self._get_weibo_data_dir() / safe_username
        candidates_by_pic = data.get("_pic_url_candidates") or []
        image_urls: list[str] = []

        if not candidates_by_pic or post_mid == "0":
            self._commit_post_image_dir(user_dir, post_mid, None)
            data["图片"] = json.dumps(image_urls, ensure_ascii=False)
            return image_urls

        posts_dir = user_dir / "posts"
        temp_dir = posts_dir / f".{post_mid}.{uuid.uuid4().hex}.tmp"
        temp_dir.mkdir(parents=True, exist_ok=False)

        try:
            for index, candidates in enumerate(candidates_by_pic, start=1):
                save_path = temp_dir / f"{index:02d}.jpg"
                if await self._download_post_image(candidates, save_path):
                    self._make_post_thumbnail(save_path, self._get_post_thumbnail_path(save_path))
                    image_urls.append(
                        self._build_weibo_img_url(
                            safe_username,
                            "posts",
                            post_mid,
                            save_path.name,
                        )
                    )

            if image_urls:
                self._commit_post_image_dir(user_dir, post_mid, temp_dir)
            else:
                self._remove_path(temp_dir)
                self._commit_post_image_dir(user_dir, post_mid, None)
        except Exception as e:
            self._remove_path(temp_dir)
            image_urls = []
            self.logger.warning("保存微博正文图片时发生异常（已忽略）: %s", e)

        data["图片"] = json.dumps(image_urls, ensure_ascii=False)
        return image_urls

    def _resize_cover_for_wecom(self, cover_path: Path, wecom_path: Path) -> bool:
        """
        将微博封面图 resize 为企业微信图文消息推荐尺寸 1068×455，并保存为 JPG。
        企业微信 picurl 建议：大图 1068×455，文件建议 1MB 以下。
        失败时仅记录日志，不影响主流程。
        """
        try:
            with Image.open(cover_path) as img:
                img = img.convert("RGB")
                # 企业微信图文消息推荐大图尺寸
                target_w, target_h = 1068, 455
                img_resized = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
                wecom_path.parent.mkdir(parents=True, exist_ok=True)
                # 质量 85 通常能保证 <1MB，同时兼顾清晰度
                img_resized.save(wecom_path, "JPEG", quality=85, optimize=True)
            self.logger.debug("已生成企业微信专用封面: %s", wecom_path)
            return True
        except Exception as e:
            self.logger.debug("生成企业微信封面失败（已忽略）: %s", e)
            return False

    async def _save_user_images(self, user_info: dict) -> None:
        """
        将微博用户主页中的头像、封面图保存到 data/weibo/<用户名>/ 目录下。

        包含：profile_image_url、avatar_large、avatar_hd、cover_image_phone。

        说明：
        - 微博返回的图片链接带有 Expires 与 ssig 等参数，属于临时链接；
        - 这里在监控获取到数据、链接仍然有效时尽快下载并持久化到本地；
        - 如果链接已经过期或下载失败，只记录日志，不影响主流程。
        """
        try:
            username = user_info.get("screen_name") or "unknown_user"
            safe_username = self._sanitize_username(username)
            user_dir = self._get_weibo_data_dir() / safe_username

            profile_url = user_info.get("profile_image_url") or ""
            avatar_large_url = user_info.get("avatar_large") or ""
            avatar_hd_url = user_info.get("avatar_hd") or ""
            cover_image_phone_url = user_info.get("cover_image_phone") or ""

            # 如果都没有可用链接，直接返回
            if not any([profile_url, avatar_large_url, avatar_hd_url, cover_image_phone_url]):
                return

            # 固定文件名，便于后续引用
            tasks: list[asyncio.Task] = []

            if profile_url:
                tasks.append(
                    asyncio.create_task(
                        self._download_image(profile_url, user_dir / "profile_image.jpg")
                    )
                )
            if avatar_large_url:
                tasks.append(
                    asyncio.create_task(
                        self._download_image(avatar_large_url, user_dir / "avatar_large.jpg")
                    )
                )
            if avatar_hd_url:
                tasks.append(
                    asyncio.create_task(
                        self._download_image(avatar_hd_url, user_dir / "avatar_hd.jpg")
                    )
                )
            if cover_image_phone_url:
                tasks.append(
                    asyncio.create_task(
                        self._download_image(
                            cover_image_phone_url, user_dir / "cover_image_phone.jpg"
                        )
                    )
                )

            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            # 防御性处理，避免头像下载影响监控主流程
            self.logger.warning("保存微博头像时发生异常（已忽略）: %s", e)

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

        # 在链接仍然有效时，尝试将头像图片保存到本地 data/weibo/<用户名>/ 目录
        await self._save_user_images(user_info)

        verified_reason = user_info.get("verified_reason", "人气博主")
        user_description = (
            user_info["description"] if user_info["description"] else "peace and love"
        )
        data = {
            "UID": user_info["idstr"],
            "用户名": user_info["screen_name"],
            "认证信息": verified_reason,
            "简介": user_description,
            "粉丝数": user_info["followers_count_str"],
            "微博数": str(user_info["statuses_count"]),
        }

        # 解析最新微博内容
        wb_list = res_list["data"]["list"]
        if not wb_list:
            data["文本"] = "无内容"
            data["mid"] = "0"
            data["图片"] = "[]"
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
        text_raw = target_wb["text_raw"]
        pic_ids = target_wb.get("pic_ids", [])
        pic_infos = target_wb.get("pic_infos", {})
        pics = target_wb.get("pics", [])
        url_struct = target_wb.get("url_struct", [])
        created_at = target_wb["created_at"]

        spacing = "\n          "
        prefix = "          "

        # 保留完整的正文，不进行截断（截断逻辑移到推送时处理）
        text = prefix + text_raw

        # 图片处理
        if pic_ids:
            text += f"{spacing}[图片]  *  {len(pic_ids)}      (详情请点击噢!)"

        # URL 结构处理
        if url_struct:
            text += f"{spacing}#{url_struct[0]['url_title']}#"

        text += f"\n\n{created_at}"

        data["文本"] = text
        data["mid"] = str(target_wb["mid"])
        data["图片"] = "[]"
        # 保存原始数据，用于推送时动态处理
        data["_text_raw"] = text_raw
        data["_pic_ids"] = pic_ids
        data["_pic_url_candidates"] = self._extract_pic_url_candidates(pic_ids, pic_infos, pics)
        data["_url_struct"] = url_struct
        data["_created_at"] = created_at

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
            await self.mark_cookie_valid()
        except CookieExpiredError as e:
            # Cookie失效，使用基类统一处理
            await self.handle_cookie_expired(e)
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
                await self._save_post_images(new_data)

                # 更新数据
                sql = (
                    "UPDATE weibo SET 用户名=%(用户名)s, 认证信息=%(认证信息)s, 简介=%(简介)s, "
                    "粉丝数=%(粉丝数)s, 微博数=%(微博数)s, 文本=%(文本)s, mid=%(mid)s, "
                    "图片=%(图片)s WHERE UID=%(UID)s"
                )
                updated = await self.db.execute_update(sql, new_data)
                if not updated:
                    self.logger.error("更新 %s 微博数据失败，跳过推送", new_data["用户名"])
                    return

                if diff > 0:
                    self.logger.info(f"{new_data['用户名']} 发布了{diff}条微博😍")
                else:
                    self.logger.info(f"{new_data['用户名']} 删除了{abs(diff)}条微博😞")

                await self.push_notification(new_data, diff)
        else:
            await self._save_post_images(new_data)

            # 新用户插入
            sql = (
                "INSERT INTO weibo (UID, 用户名, 认证信息, 简介, 粉丝数, 微博数, 文本, mid, 图片) "
                "VALUES (%(UID)s, %(用户名)s, %(认证信息)s, %(简介)s, %(粉丝数)s, "
                "%(微博数)s, %(文本)s, %(mid)s, %(图片)s)"
            )
            inserted = await self.db.execute_insert(sql, new_data)
            if not inserted:
                self.logger.error("插入 %s 微博数据失败，跳过推送", new_data["用户名"])
                return

            if self._is_first_time:
                self.logger.info(f"{new_data['用户名']} 新收录（首次创建数据库，跳过推送）")
            else:
                self.logger.info(f"{new_data['用户名']} 发布了新微博😍 (新收录)")
                await self.push_notification(new_data, 1)

    def _build_description_for_channel(self, channel, data: dict) -> str:
        """构建推送描述内容，各渠道字数限制由 UnifiedPushManager 统一截断处理。"""
        return (
            f"Ta说:👇\n{data['文本']}\n"
            f"{'=' * 20}\n"
            f"认证:{data['认证信息']}\n\n"
            f"简介:{data['简介']}"
        )

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

        # 为方案一/方案二准备封面图信息：
        # - 方案一：如果配置了 base_url，则优先构造对外可访问的封面图 URL 供大部分通道使用；
        # - 方案二：同时将本地路径通过 extend_data.local_pic_path 传给支持本地上传的通道（如 Telegram）。
        # 同时，为 Bark 等通道准备头像 icon（extend_data.avatar_url）。
        cover_pic_url = None
        local_pic_path = None
        avatar_url = None
        wecom_pic_url = None
        try:
            safe_username = self._sanitize_username(data.get("用户名", "unknown_user"))
            user_dir = self._get_weibo_data_dir() / safe_username

            # 封面图（用于大图展示）
            cover_path = user_dir / "cover_image_phone.jpg"
            if cover_path.is_file():
                local_pic_path = str(cover_path)

                # 如果配置了 base_url，则构造 HTTP 访问地址
                base_url = (self.config.base_url or "").rstrip("/")
                if base_url:
                    cover_pic_url = f"{base_url}/weibo_img/{safe_username}/cover_image_phone.jpg"
                    # 若有企业微信通道，生成 resize 后的封面（1068×455）供企微使用
                    if self._has_wecom_apps_channel():
                        wecom_path = user_dir / "cover_image_phone_wecom.jpg"
                        if self._resize_cover_for_wecom(cover_path, wecom_path):
                            wecom_pic_url = (
                                f"{base_url}/weibo_img/{safe_username}/cover_image_phone_wecom.jpg"
                            )

            # 头像（用于 Bark icon）
            profile_path = user_dir / "profile_image.jpg"
            if profile_path.is_file():
                base_url = (self.config.base_url or "").rstrip("/")
                if base_url:
                    avatar_url = f"{base_url}/weibo_img/{safe_username}/profile_image.jpg"
        except Exception as e:
            self.logger.debug("构造本地封面图路径失败（已忽略）: %s", e)

        try:
            extend_data: dict | None = None
            # 将本地封面图路径传递给支持本地上传图片的通道
            if local_pic_path:
                extend_data = {"local_pic_path": local_pic_path}
            # 为 Bark 等通道传递头像 URL，用作 icon
            if avatar_url:
                if extend_data is None:
                    extend_data = {}
                extend_data["avatar_url"] = avatar_url
            # 为企业微信通道传递 resize 后的封面 URL（1068×455，符合企微图文消息推荐尺寸）
            if wecom_pic_url:
                if extend_data is None:
                    extend_data = {}
                extend_data["wecom_pic_url"] = wecom_pic_url

            # 使用 description_func 为各通道生成描述，超限时由 UnifiedPushManager 统一截断
            await self.push.send_news(
                title=f"{data['用户名']} {action}了{count}条weibo",
                description="",  # 这个值会被 description_func 覆盖
                description_func=lambda channel: self._build_description_for_channel(channel, data),
                # 方案一：如果有封面图 URL 则优先使用；否则仍然使用原先的固定 Bing 图
                picurl=cover_pic_url
                or "https://cn.bing.com/th?id=OHR.DubrovnikHarbor_ZH-CN8590217905_1920x1080.jpg",
                to_url=f"https://m.weibo.cn/detail/{data['mid']}",
                btntxt="阅读全文",
                extend_data=extend_data,
                event_type="weibo",
                event_data={
                    "username": data.get("用户名"),
                    "text": (data.get("文本") or "")[:500],
                    "verified": data.get("认证信息"),
                    "intro": data.get("简介"),
                    "mid": data.get("mid"),
                    "action": action,
                    "count": count,
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
                title="⚠️ 微博Cookie已失效",
                description=(
                    "微博监控检测到Cookie已过期，需要重新登录更新Cookie。\n\n"
                    "请及时更新config.yml文件中的微博Cookie配置，以确保监控正常运行。"
                ),
                picurl="https://cn.bing.com/th?id=OHR.DubrovnikHarbor_ZH-CN8590217905_1920x1080.jpg",
                to_url="https://weibo.com/login.php",
                btntxt="前往登录",
            )
            self.logger.info("已发送Cookie失效提醒")
        except Exception as e:
            self.logger.error(f"发送Cookie失效提醒失败: {e}")

    @property
    def platform_name(self) -> str:
        """平台名称"""
        return "weibo"

    @property
    def push_channel_names(self) -> list[str] | None:
        """推送通道名称列表"""
        channels = getattr(self.config, "weibo_push_channels", None)
        return channels if channels else None

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
            await self.mark_cookie_valid()
            # 如果session已存在，更新headers中的Cookie
            if self.session is not None:
                self.session.headers["Cookie"] = new_cookie
                self.logger.debug("已更新session headers中的Cookie")
        else:
            self.logger.debug(f"Cookie未变化 (长度: {len(old_cookie)})")

        self.logger.debug("开始执行 %s", self.monitor_name)

        # 在执行任务前检查Cookie状态
        # 如果标记为无效，尝试验证一次（可能Cookie已恢复但缓存未更新）
        from src.storage.cookie_cache import get_cookie_cache

        cookie_cache = get_cookie_cache()
        if not cookie_cache.is_valid(self.platform_name):
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
                        await self.mark_cookie_valid()
                        self.logger.info("Cookie验证成功，已恢复有效状态")
                        verification_success = True
                        break
                    except CookieExpiredError:
                        verification_errors += 1
                        # 如果所有验证都失败，才跳过执行
                        if verification_errors >= max_verification_attempts:
                            self.logger.warning(
                                "%s Cookie验证失败（已尝试%d个用户），跳过本次执行",
                                self.monitor_name,
                                verification_errors,
                            )
                            return
                    except Exception as e:
                        self.logger.debug(
                            "Cookie验证时发生错误（用户%s）: %s，继续尝试",
                            self.weibo_config.uids[i],
                            e,
                        )
                        verification_errors += 1
                        if verification_errors >= max_verification_attempts:
                            self.logger.warning(
                                "%s Cookie验证失败（已尝试%d个用户），跳过本次执行",
                                self.monitor_name,
                                verification_errors,
                            )
                            return

                if not verification_success:
                    self.logger.warning("%s Cookie验证未成功，跳过本次执行", self.monitor_name)
                    return
            else:
                self.logger.warning("%s 无用户ID，跳过本次执行", self.monitor_name)
                return
        try:
            if not self.weibo_config.uids:
                self.logger.warning("%s 没有配置用户ID，跳过本次执行", self.monitor_name)
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
            self.logger.error("%s 执行失败: %s", self.monitor_name, e)
            raise
        finally:
            self.logger.debug("执行完成 %s", self.monitor_name)

    @property
    def monitor_name(self) -> str:
        """监控器名称"""
        return "微博监控🖼️  🖼️  🖼️"


async def run_weibo_monitor() -> None:
    """运行微博监控任务（支持配置热重载）。由调度器与注册表调用。"""
    config = get_config(reload=True)
    logger_instance = logging.getLogger(__name__)
    logger_instance.debug(
        "微博监控：已重新加载配置文件 (Cookie长度: %s 字符)", len(config.weibo_cookie)
    )
    async with WeiboMonitor(config) as monitor:
        await monitor.run()


def _get_weibo_trigger_kwargs(config: AppConfig) -> dict:
    """供注册表与配置热重载使用。"""
    return {"seconds": config.weibo_monitor_interval_seconds}


# 自注册到任务注册表（由 src.jobs.registry.discover_and_import 导入时执行）
from src.jobs.registry import register_monitor

register_monitor(
    "weibo_monitor",
    run_weibo_monitor,
    _get_weibo_trigger_kwargs,
    description="微博动态监控",
)
