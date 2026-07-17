"""微博监控模块"""

import asyncio
import html
import json
import logging
import re
import shutil
import uuid
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlsplit

import aiohttp
from aiohttp import ClientSession, ClientTimeout
from bs4 import BeautifulSoup, NavigableString, Tag
from PIL import Image, ImageOps

from src.core.http import create_certifi_connector
from src.core.paths import DATA_DIR
from src.monitors.base import BaseMonitor, CookieExpiredError
from src.push_channel.rich_text import RichText, RichTextBuilder, RichTextSegment
from src.settings.config import AppConfig, get_config, is_in_quiet_hours

POST_IMAGE_TIMEOUT = ClientTimeout(total=180, sock_connect=20, sock_read=90)
POST_IMAGE_HEADERS = {
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    "Referer": "https://weibo.com/",
}

WEIBO_CONTENT_TYPES = {"repost", "video", "image", "text"}
WEIBO_EMOJI_ALT_PATTERN = re.compile(r"^\[[^\[\]\r\n]{1,50}\]$")
WEIBO_CONTENT_SEGMENTS_INDEX = 10
WEIBO_TAGS_INDEX = 11
WEIBO_CONTENT_TYPE_INDEX = 12
WEIBO_VIDEO_COVER_INDEX = 13


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
            sql = (
                "SELECT UID, 用户名, 认证信息, 简介, 粉丝数, 微博数, 文本, mid, 图片, "
                "转发微博, 正文结构, 标签, 内容类型, 视频封面 FROM weibo"
            )
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

    def _same_mid(self, left: object, right: object) -> bool:
        """比较两个 mid，忽略空值和路径安全化差异。"""
        left_mid = self._sanitize_path_part(str(left or ""))
        right_mid = self._sanitize_path_part(str(right or ""))
        return left_mid != "0" and left_mid == right_mid

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

    @staticmethod
    def _looks_like_video_payload(payload: object) -> bool:
        """识别微博普通视频和混合媒体中的视频数据。"""
        if not isinstance(payload, dict):
            return False

        markers = (
            payload.get("type"),
            payload.get("object_type"),
            payload.get("media_type"),
        )
        if any(str(marker or "").strip().lower() == "video" for marker in markers):
            return True

        media_info = payload.get("media_info")
        return isinstance(media_info, dict) and any(
            key in media_info
            for key in (
                "stream_url",
                "stream_url_hd",
                "mp4_hd_url",
                "mp4_sd_url",
                "playback_list",
            )
        )

    def _iter_video_payloads(self, status: dict) -> list[dict]:
        """返回一条微博中所有可用于提取封面的独立视频数据。"""
        if not isinstance(status, dict):
            return []

        payloads: list[dict] = []
        seen: set[int] = set()

        def append(payload: object, *, force: bool = False) -> None:
            if not isinstance(payload, dict):
                return
            marker = id(payload)
            if marker in seen or (not force and not self._looks_like_video_payload(payload)):
                return
            seen.add(marker)
            payloads.append(payload)

        append(status.get("page_info"))
        if isinstance(status.get("media_info"), dict):
            append(status)

        mix_media_info = status.get("mix_media_info")
        if isinstance(mix_media_info, dict):
            items = mix_media_info.get("items")
            if isinstance(items, list):
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    data = item.get("data")
                    is_video = str(item.get("type") or "").strip().lower() == "video"
                    append(data if isinstance(data, dict) else item, force=is_video)

        pic_infos = status.get("pic_infos")
        if isinstance(pic_infos, dict):
            for info in pic_infos.values():
                append(info)

        pics = status.get("pics")
        if isinstance(pics, list):
            for item in pics:
                if not isinstance(item, dict):
                    continue
                data = item.get("data")
                is_video = str(item.get("type") or "").strip().lower() == "video"
                append(data if isinstance(data, dict) else item, force=is_video)

        return payloads

    def _extract_pic_url_candidates(
        self,
        pic_ids: list | None,
        pic_infos: dict | None,
        pics: list | None = None,
        mix_media_info: dict | None = None,
    ) -> list[list[str]]:
        """按微博图片顺序提取每张图的下载候选 URL；视频不参与处理。"""
        result: list[list[str]] = []
        safe_pic_infos = pic_infos if isinstance(pic_infos, dict) else {}
        ordered_ids = [str(pic_id) for pic_id in (pic_ids or []) if pic_id]
        if not ordered_ids and safe_pic_infos:
            ordered_ids = [str(pic_id) for pic_id in safe_pic_infos.keys()]

        for pic_id in ordered_ids:
            info = safe_pic_infos.get(pic_id)
            if self._looks_like_video_payload(info):
                continue
            candidates = self._collect_pic_candidates_from_info(info)
            if candidates:
                result.append(candidates)

        if result:
            return result

        if isinstance(pics, list):
            for pic in pics:
                if not isinstance(pic, dict) or self._looks_like_video_payload(pic):
                    continue
                candidates = self._collect_pic_candidates_from_info(pic)
                if candidates:
                    result.append(candidates)

        if result or not isinstance(mix_media_info, dict):
            return result

        items = mix_media_info.get("items")
        if not isinstance(items, list):
            return result
        for item in items:
            if not isinstance(item, dict):
                continue
            if str(item.get("type") or "").strip().lower() == "video":
                continue
            data = item.get("data")
            if not isinstance(data, dict) or self._looks_like_video_payload(data):
                continue
            candidates = self._collect_pic_candidates_from_info(data)
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

    def _parse_post_image_urls(self, raw_images: object) -> list[str]:
        """解析数据库中的微博正文图片 JSON。"""
        if isinstance(raw_images, list):
            values = raw_images
        elif isinstance(raw_images, str) and raw_images.strip():
            try:
                values = json.loads(raw_images)
            except json.JSONDecodeError:
                return []
        else:
            return []
        return [item for item in values if isinstance(item, str) and item]

    @staticmethod
    def _parse_rich_text_segments(raw_segments: object) -> RichText:
        """解析数据库或内存中的结构化正文。"""
        if isinstance(raw_segments, RichText):
            return raw_segments
        if isinstance(raw_segments, list):
            values = raw_segments
        elif isinstance(raw_segments, str) and raw_segments.strip():
            try:
                values = json.loads(raw_segments)
            except json.JSONDecodeError:
                return RichText()
        else:
            return RichText()
        return RichText.from_dicts(values)

    @staticmethod
    def _dump_rich_text_segments(content: RichText | object) -> str:
        if isinstance(content, RichText):
            rich = content
        elif isinstance(content, str) and content.strip():
            try:
                rich = RichText.from_dicts(json.loads(content))
            except json.JSONDecodeError:
                rich = RichText()
        else:
            rich = RichText.from_dicts(content)
        return json.dumps(rich.to_dicts(), ensure_ascii=False)

    @staticmethod
    def _parse_weibo_tags(raw_tags: object) -> list[str]:
        if isinstance(raw_tags, list):
            values = raw_tags
        elif isinstance(raw_tags, str) and raw_tags.strip():
            try:
                values = json.loads(raw_tags)
            except json.JSONDecodeError:
                return []
        else:
            return []
        result: list[str] = []
        for value in values:
            tag = str(value or "").strip()
            if tag and tag not in result:
                result.append(tag)
        return result

    def _dump_weibo_tags(self, raw_tags: object) -> str:
        return json.dumps(self._parse_weibo_tags(raw_tags), ensure_ascii=False)

    def _parse_retweeted_status(self, raw_status: object) -> dict:
        """解析数据库或内存中的转发微博 JSON。"""
        if isinstance(raw_status, dict):
            status = raw_status
        elif isinstance(raw_status, str) and raw_status.strip():
            try:
                status = json.loads(raw_status)
            except json.JSONDecodeError:
                return {}
        else:
            return {}

        if not isinstance(status, dict):
            return {}

        images = status.get("images")
        if not isinstance(images, list):
            images = []
        clean_images = [item.strip() for item in images if isinstance(item, str) and item.strip()]

        content = self._parse_rich_text_segments(status.get("content_segments"))
        text = str(status.get("text") or "").strip()
        if not content and text:
            content = RichText.text(text)
        elif content:
            text = content.plain_text().strip()
        tags = self._parse_weibo_tags(status.get("tags"))
        video_cover = str(status.get("video_cover") or "").strip()
        content_type = str(status.get("content_type") or "").strip().lower()
        if content_type not in WEIBO_CONTENT_TYPES:
            content_type = "video" if video_cover else ("image" if clean_images else "text")

        parsed = {
            "user_id": str(status.get("user_id") or "").strip(),
            "user_name": str(status.get("user_name") or "").strip(),
            "verified": str(status.get("verified") or "").strip(),
            "text": text,
            "content_segments": content.to_dicts(),
            "tags": tags,
            "content_type": content_type,
            "created_at": str(status.get("created_at") or "").strip(),
            "mid": str(status.get("mid") or "").strip(),
            "images": clean_images,
            "video_cover": video_cover,
            "source_unavailable": bool(status.get("source_unavailable")),
        }
        if not any(
            [
                parsed["user_id"],
                parsed["user_name"],
                parsed["text"],
                parsed["created_at"],
                parsed["mid"],
                parsed["images"],
                parsed["video_cover"],
                parsed["source_unavailable"],
            ]
        ):
            return {}
        if not parsed["user_name"]:
            parsed["user_name"] = "未知用户"
        return parsed

    def _dump_retweeted_status(self, status: dict | None) -> str:
        """将转发微博结构序列化为数据库字段。"""
        parsed = self._parse_retweeted_status(status or {})
        return json.dumps(parsed, ensure_ascii=False) if parsed else "{}"

    def _retweeted_content_signature(self, raw_status: object) -> tuple:
        """生成转发微博内容签名；图片本地路径不参与内容变化判断。"""
        status = self._parse_retweeted_status(raw_status)
        if not status:
            return ()
        return (
            status.get("user_id", ""),
            status.get("user_name", ""),
            status.get("verified", ""),
            self._normalize_weibo_text_for_compare(status.get("text", "")),
            json.dumps(status.get("content_segments") or [], ensure_ascii=False, sort_keys=True),
            tuple(status.get("tags") or []),
            status.get("content_type", "text"),
            status.get("created_at", ""),
            status.get("mid", ""),
            bool(status.get("source_unavailable")),
        )

    def _retweeted_statuses_equivalent(self, left: object, right: object) -> bool:
        """判断两个转发微博结构是否为同一份展示内容。"""
        return self._retweeted_content_signature(left) == self._retweeted_content_signature(right)

    def _get_local_post_image_path(self, image_url: str) -> Path | None:
        """将 /weibo_img/... URL 转回本地路径，仅用于检查已保存图片是否存在。"""
        prefix = "/weibo_img/"
        if not isinstance(image_url, str) or not image_url.startswith(prefix):
            return None

        parts = [unquote(part) for part in image_url[len(prefix) :].split("/") if part]
        if not parts or any(
            part in ("", ".", "..") or "\\" in part or "/" in part for part in parts
        ):
            return None

        root = self._get_weibo_data_dir().resolve()
        path = root.joinpath(*parts).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            return None
        return path

    def _local_post_image_exists(self, image_url: str) -> bool:
        """检查数据库图片 URL 对应的本地文件是否还可用。"""
        image_path = self._get_local_post_image_path(image_url)
        return bool(image_path and image_path.is_file() and image_path.stat().st_size > 0)

    def _needs_post_image_retry(self, data: dict, old_info: tuple) -> bool:
        """同一条微博未变化时，判断是否需要补偿下载缺失正文图片。"""
        expected_count = len(data.get("_pic_url_candidates") or [])
        if expected_count <= 0:
            return False

        old_mid = str(old_info[7]) if len(old_info) > 7 else ""
        if self._sanitize_path_part(old_mid) != self._sanitize_path_part(data.get("mid") or "0"):
            return False

        old_images = self._parse_post_image_urls(old_info[8] if len(old_info) > 8 else "")
        available_count = sum(
            1 for image_url in old_images if self._local_post_image_exists(image_url)
        )
        return len(old_images) < expected_count or available_count < min(
            len(old_images), expected_count
        )

    def _needs_retweeted_image_retry(self, data: dict, old_info: tuple) -> bool:
        """同一条微博未变化时，判断是否需要补偿下载被转发微博图片。"""
        expected_count = len(data.get("_retweeted_pic_url_candidates") or [])
        if expected_count <= 0:
            return False

        old_mid = str(old_info[7]) if len(old_info) > 7 else ""
        if self._sanitize_path_part(old_mid) != self._sanitize_path_part(data.get("mid") or "0"):
            return False

        new_retweeted = self._parse_retweeted_status(data.get("转发微博"))
        old_retweeted = self._parse_retweeted_status(old_info[9] if len(old_info) > 9 else "")
        if not new_retweeted or not old_retweeted:
            return False
        if self._sanitize_path_part(new_retweeted.get("mid") or "0") != self._sanitize_path_part(
            old_retweeted.get("mid") or "0"
        ):
            return False

        old_images = self._parse_post_image_urls(old_retweeted.get("images"))
        available_count = sum(
            1 for image_url in old_images if self._local_post_image_exists(image_url)
        )
        return len(old_images) < expected_count or available_count < min(
            len(old_images), expected_count
        )

    def _needs_video_cover_retry(self, data: dict, old_info: tuple) -> bool:
        """同一条视频微博封面缺失时，在后续轮询补偿下载。"""
        if not data.get("_video_cover_url_candidates"):
            return False
        old_mid = str(old_info[7]) if len(old_info) > 7 else ""
        if not self._same_mid(old_mid, data.get("mid")):
            return False
        old_cover = (
            str(old_info[WEIBO_VIDEO_COVER_INDEX] or "")
            if len(old_info) > WEIBO_VIDEO_COVER_INDEX
            else ""
        )
        return not old_cover or not self._local_post_image_exists(old_cover)

    def _needs_retweeted_video_cover_retry(self, data: dict, old_info: tuple) -> bool:
        """同一条被转发视频的封面缺失时补偿下载。"""
        if not data.get("_retweeted_video_cover_url_candidates"):
            return False
        if not self._same_mid(old_info[7] if len(old_info) > 7 else "", data.get("mid")):
            return False
        new_retweeted = self._parse_retweeted_status(data.get("转发微博"))
        old_retweeted = self._parse_retweeted_status(old_info[9] if len(old_info) > 9 else "")
        if not new_retweeted or not old_retweeted:
            return False
        if not self._same_mid(new_retweeted.get("mid"), old_retweeted.get("mid")):
            return False
        old_cover = str(old_retweeted.get("video_cover") or "")
        return not old_cover or not self._local_post_image_exists(old_cover)

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
                # 正文图片补偿替换目录时，保留与图片灯箱无关的视频封面和原微博媒体。
                for name in (
                    "video_cover.jpg",
                    "video_cover.thumb.jpg",
                    "video_cover_wecom.jpg",
                    "retweeted",
                ):
                    source = target_dir / name
                    destination = temp_dir / name
                    if source.exists() and not destination.exists():
                        shutil.move(str(source), str(destination))
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

        session = await self._get_session()
        last_status: int | None = None
        last_error = ""

        for candidate in urls:
            temp_path = save_path.with_name(f".{save_path.name}.{uuid.uuid4().hex}.download")
            try:
                async with session.get(
                    candidate,
                    headers=POST_IMAGE_HEADERS,
                    timeout=POST_IMAGE_TIMEOUT,
                ) as resp:
                    last_status = resp.status
                    if resp.status != 200:
                        continue

                    save_path.parent.mkdir(parents=True, exist_ok=True)
                    written = 0
                    with temp_path.open("wb") as file:
                        async for chunk in resp.content.iter_chunked(64 * 1024):
                            if not chunk:
                                continue
                            file.write(chunk)
                            written += len(chunk)

                    if written == 0:
                        self._remove_path(temp_path)
                        continue

                    temp_path.replace(save_path)
                    self.logger.debug("已保存微博正文图片到: %s (URL: %s)", save_path, candidate)
                    return True
            except (aiohttp.ClientError, TimeoutError, OSError) as e:
                self._remove_path(temp_path)
                last_error = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
                self.logger.debug(
                    "微博正文图片候选 URL 下载失败（继续尝试）: %s, URL: %s",
                    last_error,
                    candidate,
                )
                continue

        self.logger.warning(
            "下载微博正文图片失败，所有候选 URL 均不可用（最后状态码: %s, 最后异常: %s）",
            last_status,
            last_error or "无",
        )
        return False

    async def _refresh_post_pic_url_candidates(self, uid: str, mid: str) -> list[list[str]]:
        """重新请求微博列表，刷新当前 mid 的临时图片链接。"""
        if not uid or not mid or mid == "0":
            return []

        try:
            session = await self._get_session()
            url = f"https://www.weibo.com/ajax/statuses/mymblog?uid={uid}&page=1&feature=0"
            async with session.get(url) as resp:
                resp.raise_for_status()
                result = await resp.json()

            if result.get("ok") == -100:
                self.logger.warning("刷新微博正文图片链接失败：微博 Cookie 已失效")
                return []

            wb_list = result.get("data", {}).get("list", [])
            for item in wb_list:
                if str(item.get("mid") or "") != str(mid):
                    continue
                return self._extract_pic_url_candidates(
                    item.get("pic_ids", []),
                    item.get("pic_infos", {}),
                    item.get("pics", []),
                    item.get("mix_media_info", {}),
                )
        except Exception as e:
            self.logger.debug("刷新微博正文图片链接失败（已忽略）: %s", e)

        return []

    async def _refresh_retweeted_pic_url_candidates(
        self, uid: str, mid: str, retweeted_mid: str
    ) -> list[list[str]]:
        """重新请求微博列表，刷新被转发微博图片的临时链接。"""
        if not uid or not mid or mid == "0" or not retweeted_mid or retweeted_mid == "0":
            return []

        try:
            session = await self._get_session()
            url = f"https://www.weibo.com/ajax/statuses/mymblog?uid={uid}&page=1&feature=0"
            async with session.get(url) as resp:
                resp.raise_for_status()
                result = await resp.json()

            if result.get("ok") == -100:
                self.logger.warning("刷新被转发微博图片链接失败：微博 Cookie 已失效")
                return []

            wb_list = result.get("data", {}).get("list", [])
            for item in wb_list:
                if str(item.get("mid") or "") != str(mid):
                    continue
                retweeted_status = item.get("retweeted_status")
                if not isinstance(retweeted_status, dict):
                    return []
                if str(retweeted_status.get("mid") or "") != str(retweeted_mid):
                    return []
                return self._extract_pic_url_candidates(
                    retweeted_status.get("pic_ids", []),
                    retweeted_status.get("pic_infos", {}),
                    retweeted_status.get("pics", []),
                    retweeted_status.get("mix_media_info", {}),
                )
        except Exception as e:
            self.logger.debug("刷新被转发微博图片链接失败（已忽略）: %s", e)

        return []

    def _get_weibo_xsrf_token(self) -> str:
        """从微博 Cookie 中提取 XSRF-TOKEN，用于部分 ajax 接口。"""
        match = re.search(r"(?:^|;\s*)XSRF-TOKEN=([^;]+)", self.weibo_config.cookie or "")
        return unquote(match.group(1)) if match else ""

    @staticmethod
    def _is_long_text_status(status: dict) -> bool:
        """长文本标记或超过九图时，详情接口可能包含更完整正文。"""
        value = status.get("isLongText")
        is_long = False
        if isinstance(value, bool):
            is_long = value
        elif isinstance(value, int):
            is_long = value == 1
        elif isinstance(value, str):
            is_long = value.strip().lower() in {"1", "true"}
        if is_long:
            return True
        try:
            return int(status.get("pic_num") or 0) > 9
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _normalize_weibo_text_for_compare(text: object) -> str:
        """归一化微博文本，避免不可见字符或 HTML 转义造成重复补偿。"""
        value = html.unescape(str(text or ""))
        value = value.replace("\r\n", "\n").replace("\r", "\n")
        value = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", value)
        value = re.sub(r"[ \t]+", " ", value)
        value = "\n".join(line.strip() for line in value.split("\n"))
        value = re.sub(r"\n{3,}", "\n\n", value)
        return value.strip()

    def _texts_equivalent(self, left: object, right: object) -> bool:
        """判断两段微博展示文本是否等价。"""
        return self._normalize_weibo_text_for_compare(
            left
        ) == self._normalize_weibo_text_for_compare(right)

    @staticmethod
    def _parse_created_at_value(value: object) -> datetime | None:
        """解析微博接口或数据库文本里的 created_at，用于判断微博新旧。"""
        if isinstance(value, datetime):
            return value

        raw = str(value or "").strip()
        if not raw:
            return None

        normalized = raw.replace("\r\n", "\n").replace("\r", "\n")
        if "\n\n" in normalized:
            raw = normalized.rsplit("\n\n", 1)[-1].strip()

        formats = (
            "%a %b %d %H:%M:%S %z %Y",
            "%b %d %H:%M:%S %z %Y",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
        )
        for fmt in formats:
            try:
                return datetime.strptime(raw, fmt)
            except (ValueError, TypeError):
                continue

        match = re.match(
            r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+"
            r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+"
            r"(\d{1,2})\s+(\d{2}):(\d{2}):(\d{2})\s+([+-]\d{4})\s+(\d{4})$",
            raw,
        )
        if not match:
            return None

        months = {
            "Jan": 1,
            "Feb": 2,
            "Mar": 3,
            "Apr": 4,
            "May": 5,
            "Jun": 6,
            "Jul": 7,
            "Aug": 8,
            "Sep": 9,
            "Oct": 10,
            "Nov": 11,
            "Dec": 12,
        }
        try:
            month, day, hour, minute, second, tz, year = match.groups()
            sign = 1 if tz.startswith("+") else -1
            offset_hours = int(tz[1:3])
            offset_minutes = int(tz[3:5])
            offset = timezone(sign * timedelta(hours=offset_hours, minutes=offset_minutes))
            return datetime(
                int(year),
                months[month],
                int(day),
                int(hour),
                int(minute),
                int(second),
                tzinfo=offset,
            )
        except (KeyError, TypeError, ValueError):
            return None

    @staticmethod
    def _as_naive_utc(value: datetime) -> datetime:
        """统一 datetime 可比较性；无时区值按原值比较。"""
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            return value
        return value.astimezone(UTC).replace(tzinfo=None)

    def _created_at_relation_to_old(self, data: dict, old_info: tuple) -> int | None:
        """比较新旧微博发布时间：1 新于旧，0 相同，-1 早于旧，None 表示无法判断。"""
        new_created_at = self._parse_created_at_value(data.get("_created_at") or data.get("文本"))
        old_created_at = self._parse_created_at_value(old_info[6] if len(old_info) > 6 else "")
        if not new_created_at or not old_created_at:
            return None

        new_value = self._as_naive_utc(new_created_at)
        old_value = self._as_naive_utc(old_created_at)
        if new_value > old_value:
            return 1
        if new_value < old_value:
            return -1
        return 0

    def _mid_relation_to_old(self, data: dict, old_info: tuple) -> int | None:
        """比较微博 mid：1 新于旧，0 相同，-1 早于旧，None 表示无法判断。"""
        old_mid = self._sanitize_path_part(old_info[7] if len(old_info) > 7 else "")
        new_mid = self._sanitize_path_part(data.get("mid", ""))
        if not old_mid.isdigit() or not new_mid.isdigit():
            return None

        old_value = int(old_mid)
        new_value = int(new_mid)
        if new_value > old_value:
            return 1
        if new_value < old_value:
            return -1
        return 0

    def _is_stale_status_snapshot(self, data: dict, old_info: tuple) -> bool:
        """判断接口返回的最新微博是否并不比数据库中已记录的微博更新。"""
        old_mid = old_info[7] if len(old_info) > 7 else ""
        new_mid = data.get("mid", "")
        if self._same_mid(old_mid, new_mid):
            return False
        relation = self._created_at_relation_to_old(data, old_info)
        if relation is None:
            return False
        if relation < 0:
            return True
        if relation > 0:
            return False
        mid_relation = self._mid_relation_to_old(data, old_info)
        return mid_relation is None or mid_relation <= 0

    @staticmethod
    def _extract_status_body_from_display_text(text: object) -> str:
        """从数据库展示文本中取正文部分，去掉时间和本地追加的图片提示。"""
        value = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
        if "\n\n" in value:
            value = value.rsplit("\n\n", 1)[0]

        lines = []
        for line in value.split("\n"):
            stripped = line.strip()
            if re.fullmatch(r"\[图片\]\s+\*\s+\d+.*", stripped):
                continue
            lines.append(stripped)
        return "\n".join(lines).strip()

    @staticmethod
    def _strip_long_text_marker(text: str) -> str:
        """去掉微博列表截断文本末尾的省略/展开标记。"""
        return re.sub(r"(?:\.{3}|…|全文|展开全文)+$", "", text).strip()

    @staticmethod
    def _safe_weibo_link_url(value: object) -> str:
        """规范化微博正文链接，仅允许 HTTP(S)，不发起额外网络请求。"""
        raw = html.unescape(str(value or "")).strip()
        if raw.startswith("//"):
            raw = f"https:{raw}"
        if re.search(r"[\x00-\x20\x7f]", raw):
            return ""
        try:
            parsed = urlsplit(raw)
            _ = parsed.port
        except ValueError:
            return ""
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            return ""

        if (
            parsed.hostname in {"weibo.cn", "www.weibo.cn"}
            and parsed.path.rstrip("/") == "/sinaurl"
        ):
            target = parse_qs(parsed.query).get("u", [""])[0]
            if target:
                try:
                    target_parsed = urlsplit(target)
                    _ = target_parsed.port
                except ValueError:
                    target_parsed = None
                if (
                    target_parsed
                    and target_parsed.scheme.lower() in {"http", "https"}
                    and target_parsed.hostname
                    and not re.search(r"[\x00-\x20\x7f]", target)
                ):
                    return target
        return raw

    @staticmethod
    def _normalize_rich_text(value: RichText) -> RichText:
        """清理微博 HTML 产生的多余空白，同时保持链接片段边界。"""
        cleaned: list[RichTextSegment] = []
        for segment in value.segments:
            text = segment.text.replace("\r\n", "\n").replace("\r", "\n")
            text = text.replace("\xa0", " ")
            text = re.sub(r"[ \t]+\n", "\n", text)
            text = re.sub(r"\n[ \t]+", "\n", text)
            text = re.sub(r"\n{3,}", "\n\n", text)
            if text:
                cleaned.append(RichTextSegment(text, segment.url, segment.image_url))

        if not cleaned:
            return RichText()
        first = cleaned[0]
        cleaned[0] = RichTextSegment(first.text.lstrip(), first.url, first.image_url)
        last = cleaned[-1]
        cleaned[-1] = RichTextSegment(last.text.rstrip(), last.url, last.image_url)
        return RichText(cleaned)

    def _parse_weibo_html_rich_text(self, value: object) -> RichText:
        """将微博 HTML 解析为安全的文本/链接片段。"""
        raw = str(value or "")
        if not raw:
            return RichText()
        soup = BeautifulSoup(raw, "html.parser")

        def parse_nodes(nodes) -> RichText:
            builder = RichTextBuilder()
            for node in nodes:
                if isinstance(node, NavigableString):
                    builder.text(str(node))
                    continue
                if not isinstance(node, Tag):
                    continue

                name = (node.name or "").lower()
                if name == "br":
                    builder.text("\n")
                    continue
                if name == "img":
                    alt = str(node.get("alt") or "").strip()
                    image_url = self._safe_weibo_link_url(node.get("src") or node.get("data-src"))
                    if alt and image_url and WEIBO_EMOJI_ALT_PATTERN.fullmatch(alt):
                        builder.emoji(alt, image_url)
                    else:
                        builder.text(alt)
                    continue
                if name in {"script", "style"}:
                    continue
                if name == "a":
                    label_rich = parse_nodes(node.children)
                    label = label_rich.plain_text().strip() or "网页链接"
                    href = self._safe_weibo_link_url(node.get("href"))
                    is_topic = label.startswith("#") and label.endswith("#")
                    is_mention = label.startswith("@")
                    if href and not is_topic and not is_mention:
                        label = self._without_visible_urls(label)
                        builder.link(label, href)
                    else:
                        builder.rich(label_rich if label_rich else RichText.text(label))
                    continue

                child_rich = parse_nodes(node.children)
                builder.rich(child_rich)
                if name in {"p", "div"} and not child_rich.plain_text().endswith("\n"):
                    builder.text("\n")
            return builder.build()

        return self._normalize_rich_text(parse_nodes(soup.contents))

    def _apply_url_struct_fallback(self, content: RichText, url_struct: object) -> RichText:
        """用接口元数据还原链接，并确保正文中不留下可见网址。"""
        link_metadata: list[tuple[str, str, str]] = []
        if isinstance(url_struct, list):
            for raw_item in url_struct:
                if not isinstance(raw_item, dict):
                    continue
                short_url = self._safe_weibo_link_url(raw_item.get("short_url"))
                target_url = self._safe_weibo_link_url(
                    raw_item.get("long_url") or raw_item.get("ori_url") or short_url
                )
                if not short_url or not target_url:
                    continue
                label = str(raw_item.get("url_title") or "网页链接").strip() or "网页链接"
                label = self._without_visible_urls(label)
                link_metadata.append((short_url, target_url, label))

        # HTML 中已经存在的链接仍使用 url_struct 的 long_url 和标题回填。
        enriched: list[RichTextSegment] = []
        for segment in content.segments:
            if not segment.is_link:
                enriched.append(segment)
                continue
            target_url = segment.url
            label = self._without_visible_urls(segment.text.strip() or "网页链接")
            for short_url, long_url, metadata_label in link_metadata:
                if target_url in {short_url, long_url}:
                    target_url = long_url
                    if label == "网页链接":
                        label = metadata_label
                    break
            enriched.append(RichTextSegment(label, target_url))

        # HTML 只有纯文本短链时，按原位置替换，不把链接标题额外拼到正文中。
        segments = enriched
        for short_url, target_url, label in link_metadata:
            replaced: list[RichTextSegment] = []
            for segment in segments:
                if segment.is_link or segment.is_emoji or short_url not in segment.text:
                    replaced.append(segment)
                    continue
                parts = segment.text.split(short_url)
                for index, part in enumerate(parts):
                    if part:
                        replaced.append(RichTextSegment(part))
                    if index < len(parts) - 1:
                        replaced.append(RichTextSegment(label, target_url))
            segments = replaced

        # 兼容没有 url_struct 的裸地址：保留点击目标，但可见文字统一为“网页链接”。
        visible_url_pattern = re.compile(r"https?://[^\s<>'\"\]\[）)]+", re.IGNORECASE)
        hidden_urls: list[RichTextSegment] = []
        for segment in segments:
            if segment.is_link or segment.is_emoji:
                hidden_urls.append(segment)
                continue
            cursor = 0
            for match in visible_url_pattern.finditer(segment.text):
                if match.start() > cursor:
                    hidden_urls.append(RichTextSegment(segment.text[cursor : match.start()]))
                safe_url = self._safe_weibo_link_url(match.group(0))
                hidden_urls.append(RichTextSegment("网页链接", safe_url))
                cursor = match.end()
            if cursor < len(segment.text):
                hidden_urls.append(RichTextSegment(segment.text[cursor:]))
        return RichText(hidden_urls)

    def _get_status_rich_text(self, status: dict) -> RichText:
        """读取列表微博正文，优先使用带链接信息的 HTML。"""
        html_text = status.get("text")
        if isinstance(html_text, str) and html_text.strip():
            content = self._parse_weibo_html_rich_text(html_text)
        else:
            content = RichText.text(str(status.get("text_raw") or "").strip())
        if not content:
            content = RichText.text(str(status.get("text_raw") or "").strip())
        return self._apply_url_struct_fallback(content, status.get("url_struct"))

    @staticmethod
    def _extract_weibo_tags(text: object) -> list[str]:
        """从可见正文中提取有序、去重的话题标签。"""
        tags: list[str] = []
        seen: set[str] = set()
        for match in re.finditer(r"#([^#\n]{1,100})#", str(text or "")):
            tag = match.group(1).strip()
            if tag and tag not in seen:
                seen.add(tag)
                tags.append(tag)
        return tags

    def _get_weibo_content_type(self, status: dict) -> str:
        """按转发、视频、图文、文字的优先级识别微博类型。"""
        if isinstance(status.get("retweeted_status"), dict) and status.get("retweeted_status"):
            return "repost"
        if self._iter_video_payloads(status):
            return "video"
        if status.get("pic_ids") or status.get("pics"):
            return "image"
        mix_media_info = status.get("mix_media_info")
        if isinstance(mix_media_info, dict) and mix_media_info.get("items"):
            return "image"
        return "text"

    def _extract_video_cover_candidates(self, status: dict) -> list[str]:
        """提取普通视频或混合媒体视频的封面候选。"""
        candidates: list[str] = []
        seen_objects: set[int] = set()

        def append_cover(value: object, depth: int = 0) -> None:
            if depth > 4:
                return
            if isinstance(value, str):
                self._add_pic_url(candidates, self._safe_weibo_link_url(value))
                return
            if not isinstance(value, dict):
                return

            marker = id(value)
            if marker in seen_objects:
                return
            seen_objects.add(marker)

            raw_url = value.get("url") or value.get("src") or value.get("pic_url")
            safe_url = self._safe_weibo_link_url(raw_url)
            pid = str(value.get("pid") or value.get("pic_id") or "").strip()
            if safe_url and pid:
                parsed = urlsplit(safe_url)
                self._add_pic_url(
                    candidates,
                    f"{parsed.scheme}://{parsed.netloc}/large/{pid}",
                )
            self._add_pic_url(candidates, safe_url)

            for candidate in self._collect_pic_candidates_from_info(value):
                self._add_pic_url(
                    candidates,
                    self._safe_weibo_link_url(candidate),
                )

            for key in (
                "page_pic",
                "pic_info",
                "big_pic_info",
                "pic_big",
                "pic_middle",
                "pic_small",
                "poster",
                "poster_url",
                "cover",
                "cover_url",
                "cover_image",
                "cover_image_url",
                "thumbnail",
            ):
                append_cover(value.get(key), depth + 1)

        for payload in self._iter_video_payloads(status):
            append_cover(payload.get("page_pic"))
            append_cover(payload.get("pic_info"))
            media_info = payload.get("media_info")
            if isinstance(media_info, dict):
                append_cover(media_info.get("big_pic_info"))
                for key in (
                    "poster",
                    "poster_url",
                    "cover",
                    "cover_url",
                    "cover_image",
                    "cover_image_url",
                ):
                    append_cover(media_info.get(key))
        return candidates

    @staticmethod
    def _clean_weibo_html_text(text: object) -> str:
        """兼容旧调用：将微博 HTML 降级为不含链接目标的纯文本。"""
        value = html.unescape(str(text or ""))
        value = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
        value = re.sub(r"</p\s*>", "\n", value, flags=re.IGNORECASE)
        value = re.sub(r"<[^>]+>", "", value)
        value = re.sub(r"\n{3,}", "\n\n", value)
        return value.strip()

    async def _extract_retweeted_status(
        self, status: dict
    ) -> tuple[dict, list[list[str]], list[str], bool]:
        """解析被转发微博、正文图片候选和视频封面候选。"""
        retweeted_status = status.get("retweeted_status")
        if not isinstance(retweeted_status, dict) or not retweeted_status:
            return {}, [], [], False

        user = retweeted_status.get("user")
        if not isinstance(user, dict):
            user = {}

        mid = str(retweeted_status.get("mid") or "").strip()
        user_name = str(
            user.get("screen_name") or retweeted_status.get("screen_name") or ""
        ).strip()
        content = self._get_status_rich_text(retweeted_status)
        text_raw = content.plain_text().strip()

        source_unavailable = bool(
            retweeted_status.get("deleted")
            or retweeted_status.get("state") == "deleted"
            or (not mid and not text_raw and not user_name)
        )
        if source_unavailable and not text_raw:
            text_raw = "原微博已不可见"
            content = RichText.text(text_raw)

        long_text_content = await self._fetch_long_text_rich(retweeted_status)
        if long_text_content:
            content = long_text_content
            text_raw = content.plain_text().strip()

        pic_ids = retweeted_status.get("pic_ids", [])
        pic_infos = retweeted_status.get("pic_infos", {})
        pics = retweeted_status.get("pics", [])
        candidates = self._extract_pic_url_candidates(
            pic_ids,
            pic_infos,
            pics,
            retweeted_status.get("mix_media_info", {}),
        )
        video_cover_candidates = self._extract_video_cover_candidates(retweeted_status)
        content_type = self._get_weibo_content_type(retweeted_status)

        retweeted = {
            "user_id": str(user.get("idstr") or user.get("id") or "").strip(),
            "user_name": user_name or "未知用户",
            "verified": str(user.get("verified_reason") or "").strip(),
            "text": text_raw,
            "content_segments": content.to_dicts(),
            "tags": self._extract_weibo_tags(text_raw),
            "content_type": content_type,
            "created_at": str(retweeted_status.get("created_at") or "").strip(),
            "mid": mid,
            "images": [],
            "video_cover": "",
            "source_unavailable": source_unavailable,
        }
        return (
            self._parse_retweeted_status(retweeted),
            candidates,
            video_cover_candidates,
            bool(long_text_content),
        )

    def _is_long_text_backfill(self, new_data: dict, old_info: tuple) -> bool:
        """判断本次文本变化是否为同一条微博从截断正文补成完整长文本。"""
        if not new_data.get("_long_text_fetched"):
            return False
        old_mid = old_info[7] if len(old_info) > 7 else ""
        if not self._same_mid(old_mid, new_data.get("mid")):
            return False

        old_body = self._normalize_weibo_text_for_compare(
            self._extract_status_body_from_display_text(old_info[6] if len(old_info) > 6 else "")
        )
        new_body = self._normalize_weibo_text_for_compare(
            self._extract_status_body_from_display_text(new_data.get("文本", ""))
        )
        if not old_body or not new_body or old_body == new_body:
            return False

        old_prefix = self._strip_long_text_marker(old_body)
        old_has_marker = old_prefix != old_body
        prefixes = [old_prefix] if old_has_marker else []

        list_body = self._normalize_weibo_text_for_compare(new_data.get("_list_text_raw", ""))
        list_prefix = self._strip_long_text_marker(list_body)
        list_has_marker = bool(list_body and list_prefix and list_prefix != list_body)
        old_matches_list_text = bool(
            list_body
            and (
                old_body == list_body
                or old_body.startswith(list_body)
                or list_body.startswith(old_prefix)
            )
        )
        if list_has_marker and old_matches_list_text:
            prefixes.append(list_prefix)

        return any(
            prefix and len(new_body) > len(prefix) and new_body.startswith(prefix)
            for prefix in prefixes
        )

    def _is_retweeted_long_text_backfill(self, new_data: dict, old_status: object) -> bool:
        """判断被转发原微博是否从同一条截断正文补成完整长文。"""
        if not new_data.get("_retweeted_long_text_fetched"):
            return False
        current = self._parse_retweeted_status(new_data.get("转发微博"))
        previous = self._parse_retweeted_status(old_status)
        if (
            not current
            or not previous
            or not self._same_mid(current.get("mid"), previous.get("mid"))
        ):
            return False

        old_text = self._normalize_weibo_text_for_compare(previous.get("text"))
        new_text = self._normalize_weibo_text_for_compare(current.get("text"))
        old_prefix = self._strip_long_text_marker(old_text)
        return bool(
            old_prefix
            and old_prefix != old_text
            and len(new_text) > len(old_prefix)
            and new_text.startswith(old_prefix)
        )

    def _rich_text_from_long_text_data(self, data: object) -> RichText:
        """从桌面或移动详情响应中解析完整正文。"""
        if not isinstance(data, dict):
            return RichText()
        html_content = data.get("longTextContent")
        if isinstance(html_content, str) and html_content.strip():
            content = self._parse_weibo_html_rich_text(html_content)
        else:
            content = RichText.text(str(data.get("longTextContent_raw") or "").strip())
        return self._apply_url_struct_fallback(content, data.get("url_struct"))

    async def _fetch_mobile_long_text_rich(self, status: dict) -> RichText | None:
        """使用移动端详情接口作为桌面 longtext 的非鉴权降级。"""
        status_id = status.get("mid") or status.get("id")
        if not status_id:
            self.logger.debug("微博长文本缺少 mid/id，无法使用移动端详情降级")
            return None
        try:
            session = await self._get_session()
            async with session.get(
                "https://m.weibo.cn/statuses/extend",
                params={"id": str(status_id)},
                headers={
                    "Referer": f"https://m.weibo.cn/detail/{status_id}",
                    "MWeibo-Pwa": "1",
                    "X-Requested-With": "XMLHttpRequest",
                },
            ) as resp:
                resp.raise_for_status()
                result = await resp.json()

            if result.get("ok") == -100:
                raise CookieExpiredError("微博Cookie已失效，需要重新登录")
            if result.get("ok") != 1:
                self.logger.debug("微博移动端长文本接口未成功: %s", status_id)
                return None
            content = self._rich_text_from_long_text_data(result.get("data"))
            return content or None
        except CookieExpiredError:
            raise
        except Exception as e:
            self.logger.debug("微博移动端长文本降级失败（id=%s）: %s", status_id, e)
            return None

    async def _fetch_long_text_rich(self, status: dict) -> RichText | None:
        """补取完整正文；桌面端优先，移动端用于非鉴权降级。"""
        if not self._is_long_text_status(status):
            return None

        long_text_id = status.get("mblogid")
        if long_text_id:
            try:
                session = await self._get_session()
                headers: dict[str, str] = {}
                xsrf_token = self._get_weibo_xsrf_token()
                if xsrf_token:
                    headers["X-XSRF-TOKEN"] = xsrf_token

                async with session.get(
                    "https://www.weibo.com/ajax/statuses/longtext",
                    params={"id": str(long_text_id)},
                    headers=headers or None,
                ) as resp:
                    resp.raise_for_status()
                    result = await resp.json()

                if result.get("ok") == -100:
                    raise CookieExpiredError("微博Cookie已失效，需要重新登录")
                content = self._rich_text_from_long_text_data(result.get("data"))
                if content:
                    return content
                self.logger.debug("微博桌面长文本接口未返回正文: %s", long_text_id)
            except CookieExpiredError:
                raise
            except Exception as e:
                self.logger.debug("微博桌面长文本接口失败（id=%s）: %s", long_text_id, e)
        else:
            self.logger.debug("微博列表项标记为长文本但缺少 mblogid，尝试移动端详情")

        return await self._fetch_mobile_long_text_rich(status)

    async def _fetch_long_text_content(self, status: dict) -> str | None:
        """兼容旧调用，返回不显示实际 URL 的完整正文纯文本。"""
        content = await self._fetch_long_text_rich(status)
        return content.plain_text() if content else None

    async def _download_image_indices_to_temp(
        self,
        candidates_by_pic: list[list[str]],
        temp_dir: Path,
    ) -> list[int]:
        """下载一批微博图片到临时目录，并返回已落盘的图片序号。"""
        saved_indices: list[int] = []
        for index, candidates in enumerate(candidates_by_pic, start=1):
            save_path = temp_dir / f"{index:02d}.jpg"
            if save_path.exists() and save_path.stat().st_size > 0:
                saved_indices.append(index)
                continue

            if await self._download_post_image(candidates, save_path):
                self._make_post_thumbnail(save_path, self._get_post_thumbnail_path(save_path))
                saved_indices.append(index)

        return saved_indices

    async def _download_post_images_to_temp(
        self,
        candidates_by_pic: list[list[str]],
        temp_dir: Path,
        safe_username: str,
        post_mid: str,
    ) -> list[str]:
        """下载一批正文图片到临时目录，并按图片序号返回已落盘的本地 URL。"""
        saved_indices = await self._download_image_indices_to_temp(candidates_by_pic, temp_dir)
        return [
            self._build_weibo_img_url(safe_username, "posts", post_mid, f"{index:02d}.jpg")
            for index in saved_indices
        ]

    def _commit_retweeted_image_dir(
        self,
        user_dir: Path,
        post_mid: str,
        retweeted_mid: str,
        temp_dir: Path | None,
    ) -> Path:
        """将被转发微博图片临时目录切换到 posts/<mid>/retweeted/<retweeted_mid>。"""
        retweeted_root = user_dir / "posts" / self._sanitize_path_part(post_mid) / "retweeted"
        retweeted_root.mkdir(parents=True, exist_ok=True)
        target_dir = retweeted_root / self._sanitize_path_part(retweeted_mid)
        keep_names = {target_dir.name}
        if temp_dir is not None:
            keep_names.add(temp_dir.name)

        for child in retweeted_root.iterdir():
            if child.name in keep_names:
                continue
            self._remove_path(child)

        if temp_dir is not None:
            if target_dir.exists():
                # 被转发微博图片补偿时，视频封面应继续独立保留。
                for name in (
                    "video_cover.jpg",
                    "video_cover.thumb.jpg",
                    "video_cover_wecom.jpg",
                ):
                    source = target_dir / name
                    destination = temp_dir / name
                    if source.exists() and not destination.exists():
                        shutil.move(str(source), str(destination))
                self._remove_path(target_dir)
            shutil.move(str(temp_dir), str(target_dir))

        return target_dir

    async def _save_post_images(self, data: dict, keep_existing: bool = False) -> list[str]:
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
        existing_urls = self._parse_post_image_urls(data.get("图片"))
        existing_available_count = sum(
            1 for image_url in existing_urls if self._local_post_image_exists(image_url)
        )

        if not candidates_by_pic or post_mid == "0":
            if keep_existing:
                image_urls = existing_urls
            else:
                self._commit_post_image_dir(user_dir, post_mid, None)
            data["图片"] = json.dumps(image_urls, ensure_ascii=False)
            return image_urls

        expected_count = len(candidates_by_pic)
        posts_dir = user_dir / "posts"
        temp_dir = posts_dir / f".{post_mid}.{uuid.uuid4().hex}.tmp"
        temp_dir.mkdir(parents=True, exist_ok=False)

        try:
            image_urls = await self._download_post_images_to_temp(
                candidates_by_pic,
                temp_dir,
                safe_username,
                post_mid,
            )

            if len(image_urls) < expected_count:
                refreshed_candidates = await self._refresh_post_pic_url_candidates(
                    str(data.get("UID") or ""),
                    str(data.get("mid") or ""),
                )
                if refreshed_candidates:
                    expected_count = max(expected_count, len(refreshed_candidates))
                    data["_pic_url_candidates"] = refreshed_candidates
                    image_urls = await self._download_post_images_to_temp(
                        refreshed_candidates,
                        temp_dir,
                        safe_username,
                        post_mid,
                    )

            if (
                keep_existing
                and existing_urls
                and len(image_urls) <= existing_available_count
                and len(image_urls) < expected_count
            ):
                self._remove_path(temp_dir)
                data["图片"] = json.dumps(existing_urls, ensure_ascii=False)
                self.logger.warning(
                    "%s 微博正文图片补偿下载未改善，保留已有本地图片 %s/%s 张",
                    username,
                    existing_available_count,
                    expected_count,
                )
                return existing_urls

            if image_urls:
                self._commit_post_image_dir(user_dir, post_mid, temp_dir)
            else:
                self._remove_path(temp_dir)
                if not keep_existing:
                    self._commit_post_image_dir(user_dir, post_mid, None)
        except Exception as e:
            self._remove_path(temp_dir)
            image_urls = existing_urls if keep_existing else []
            self.logger.warning("保存微博正文图片时发生异常（已忽略）: %s", e)

        data["图片"] = json.dumps(image_urls, ensure_ascii=False)
        return image_urls

    async def _save_retweeted_images(self, data: dict, keep_existing: bool = False) -> list[str]:
        """
        保存被转发微博图片到 data/weibo/<用户名>/posts/<mid>/retweeted/<retweeted_mid>/。

        转发内容跟随当前监控用户的最新微博目录，便于同一条微博被替换时整体清理。
        """
        retweeted = self._parse_retweeted_status(data.get("转发微博"))
        if not retweeted:
            data["转发微博"] = "{}"
            return []

        username = data.get("用户名") or "unknown_user"
        safe_username = self._sanitize_username(username)
        post_mid = self._sanitize_path_part(data.get("mid") or "0")
        retweeted_mid = self._sanitize_path_part(retweeted.get("mid") or "0")
        user_dir = self._get_weibo_data_dir() / safe_username
        candidates_by_pic = data.get("_retweeted_pic_url_candidates") or []
        existing_urls = self._parse_post_image_urls(retweeted.get("images"))
        existing_available_count = sum(
            1 for image_url in existing_urls if self._local_post_image_exists(image_url)
        )
        image_urls: list[str] = []

        if not candidates_by_pic or post_mid == "0" or retweeted_mid == "0":
            if keep_existing:
                image_urls = existing_urls
            else:
                self._commit_retweeted_image_dir(user_dir, post_mid, retweeted_mid, None)
            retweeted["images"] = image_urls
            data["转发微博"] = self._dump_retweeted_status(retweeted)
            return image_urls

        expected_count = len(candidates_by_pic)
        retweeted_root = user_dir / "posts" / post_mid / "retweeted"
        temp_dir = retweeted_root / f".{retweeted_mid}.{uuid.uuid4().hex}.tmp"
        temp_dir.mkdir(parents=True, exist_ok=False)

        try:
            saved_indices = await self._download_image_indices_to_temp(candidates_by_pic, temp_dir)
            image_urls = [
                self._build_weibo_img_url(
                    safe_username,
                    "posts",
                    post_mid,
                    "retweeted",
                    retweeted_mid,
                    f"{index:02d}.jpg",
                )
                for index in saved_indices
            ]

            if len(image_urls) < expected_count:
                refreshed_candidates = await self._refresh_retweeted_pic_url_candidates(
                    str(data.get("UID") or ""),
                    str(data.get("mid") or ""),
                    str(retweeted.get("mid") or ""),
                )
                if refreshed_candidates:
                    expected_count = max(expected_count, len(refreshed_candidates))
                    data["_retweeted_pic_url_candidates"] = refreshed_candidates
                    saved_indices = await self._download_image_indices_to_temp(
                        refreshed_candidates,
                        temp_dir,
                    )
                    image_urls = [
                        self._build_weibo_img_url(
                            safe_username,
                            "posts",
                            post_mid,
                            "retweeted",
                            retweeted_mid,
                            f"{index:02d}.jpg",
                        )
                        for index in saved_indices
                    ]

            if (
                keep_existing
                and existing_urls
                and len(image_urls) <= existing_available_count
                and len(image_urls) < expected_count
            ):
                self._remove_path(temp_dir)
                retweeted["images"] = existing_urls
                data["转发微博"] = self._dump_retweeted_status(retweeted)
                self.logger.warning(
                    "%s 被转发微博图片补偿下载未改善，保留已有本地图片 %s/%s 张",
                    username,
                    existing_available_count,
                    expected_count,
                )
                return existing_urls

            if image_urls:
                self._commit_retweeted_image_dir(user_dir, post_mid, retweeted_mid, temp_dir)
            else:
                self._remove_path(temp_dir)
                if not keep_existing:
                    self._commit_retweeted_image_dir(user_dir, post_mid, retweeted_mid, None)
        except Exception as e:
            self._remove_path(temp_dir)
            image_urls = existing_urls if keep_existing else []
            self.logger.warning("保存被转发微博图片时发生异常（已忽略）: %s", e)

        retweeted["images"] = image_urls
        data["转发微博"] = self._dump_retweeted_status(retweeted)
        return image_urls

    async def _save_video_cover(self, data: dict, keep_existing: bool = False) -> str:
        """保存主微博视频封面，字段为空时不影响普通图片。"""
        candidates = data.get("_video_cover_url_candidates") or []
        existing_url = str(data.get("视频封面") or "").strip()
        if keep_existing and existing_url and self._local_post_image_exists(existing_url):
            existing_path = self._get_local_post_image_path(existing_url)
            if existing_path:
                thumb = self._get_post_thumbnail_path(existing_path)
                if not thumb.exists():
                    self._make_post_thumbnail(existing_path, thumb)
            return existing_url

        post_mid = self._sanitize_path_part(data.get("mid") or "0")
        if not candidates or post_mid == "0":
            data["视频封面"] = existing_url if keep_existing else ""
            return str(data["视频封面"])

        safe_username = self._sanitize_username(data.get("用户名") or "unknown_user")
        save_path = (
            self._get_weibo_data_dir() / safe_username / "posts" / post_mid / "video_cover.jpg"
        )
        local_url = self._build_weibo_img_url(safe_username, "posts", post_mid, "video_cover.jpg")
        try:
            if await self._download_post_image(candidates, save_path):
                self._make_post_thumbnail(save_path, self._get_post_thumbnail_path(save_path))
                data["视频封面"] = local_url
                return local_url
        except Exception as e:
            self.logger.warning("保存微博视频封面失败（已忽略）: %s", e)

        data["视频封面"] = existing_url if keep_existing else ""
        return str(data["视频封面"])

    async def _save_retweeted_video_cover(self, data: dict, keep_existing: bool = False) -> str:
        """保存被转发微博的视频封面。"""
        retweeted = self._parse_retweeted_status(data.get("转发微博"))
        if not retweeted:
            return ""
        candidates = data.get("_retweeted_video_cover_url_candidates") or []
        existing_url = str(retweeted.get("video_cover") or "").strip()
        if keep_existing and existing_url and self._local_post_image_exists(existing_url):
            existing_path = self._get_local_post_image_path(existing_url)
            if existing_path:
                thumb = self._get_post_thumbnail_path(existing_path)
                if not thumb.exists():
                    self._make_post_thumbnail(existing_path, thumb)
            return existing_url

        post_mid = self._sanitize_path_part(data.get("mid") or "0")
        retweeted_mid = self._sanitize_path_part(retweeted.get("mid") or "0")
        if not candidates or post_mid == "0" or retweeted_mid == "0":
            retweeted["video_cover"] = existing_url if keep_existing else ""
            data["转发微博"] = self._dump_retweeted_status(retweeted)
            return str(retweeted["video_cover"])

        safe_username = self._sanitize_username(data.get("用户名") or "unknown_user")
        save_path = (
            self._get_weibo_data_dir()
            / safe_username
            / "posts"
            / post_mid
            / "retweeted"
            / retweeted_mid
            / "video_cover.jpg"
        )
        local_url = self._build_weibo_img_url(
            safe_username,
            "posts",
            post_mid,
            "retweeted",
            retweeted_mid,
            "video_cover.jpg",
        )
        try:
            if await self._download_post_image(candidates, save_path):
                self._make_post_thumbnail(save_path, self._get_post_thumbnail_path(save_path))
                retweeted["video_cover"] = local_url
                data["转发微博"] = self._dump_retweeted_status(retweeted)
                return local_url
        except Exception as e:
            self.logger.warning("保存被转发微博视频封面失败（已忽略）: %s", e)

        retweeted["video_cover"] = existing_url if keep_existing else ""
        data["转发微博"] = self._dump_retweeted_status(retweeted)
        return str(retweeted["video_cover"])

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

    def _get_timeline_statuses(self, wb_list: list) -> list[dict]:
        """获取用于监控的微博列表，优先跳过置顶微博。"""
        statuses = [
            item for item in wb_list if isinstance(item, dict) and item.get("isTop", 0) != 1
        ]
        if statuses:
            return statuses
        return [item for item in wb_list if isinstance(item, dict)]

    def _collect_candidate_new_statuses(
        self, statuses: list[dict], old_mid: str | None
    ) -> tuple[list[dict], bool]:
        """收集旧 mid 之前的新微博候选，返回顺序为最新到最旧。"""
        if not old_mid or self._sanitize_path_part(old_mid) == "0":
            return [], False

        candidate_statuses: list[dict] = []
        for status in statuses:
            if self._same_mid(status.get("mid"), old_mid):
                return candidate_statuses, True
            candidate_statuses.append(status)
        return candidate_statuses, False

    async def _build_status_data(self, base_data: dict, target_wb: dict) -> dict:
        """将微博列表中的单条微博解析成数据库/推送共用结构。"""
        data = dict(base_data)
        content = self._get_status_rich_text(target_wb)
        list_text_raw = content.plain_text().strip()
        long_text_content = await self._fetch_long_text_rich(target_wb)
        if long_text_content:
            content = long_text_content
        text_raw = content.plain_text().strip()

        pic_ids = target_wb.get("pic_ids", [])
        if not isinstance(pic_ids, list):
            pic_ids = []
        pic_infos = target_wb.get("pic_infos", {})
        pics = target_wb.get("pics", [])
        url_struct = target_wb.get("url_struct", [])
        if not isinstance(url_struct, list):
            url_struct = []
        created_at = str(target_wb.get("created_at") or "")
        (
            retweeted_status,
            retweeted_pic_candidates,
            retweeted_video_cover_candidates,
            retweeted_long_text_fetched,
        ) = await self._extract_retweeted_status(target_wb)
        content_type = self._get_weibo_content_type(target_wb)
        tags = self._extract_weibo_tags(text_raw)
        video_cover_candidates = self._extract_video_cover_candidates(target_wb)
        pic_candidates = self._extract_pic_url_candidates(
            pic_ids,
            pic_infos,
            pics,
            target_wb.get("mix_media_info", {}),
        )

        spacing = "\n          "
        prefix = "          "

        text = prefix + text_raw

        if pic_candidates:
            text += f"{spacing}[图片]  *  {len(pic_candidates)}      (详情请点击噢!)"

        text += f"\n\n{created_at}"

        data["文本"] = text
        data["mid"] = str(target_wb.get("mid") or "0")
        data["图片"] = "[]"
        data["转发微博"] = self._dump_retweeted_status(retweeted_status)
        data["正文结构"] = self._dump_rich_text_segments(content)
        data["标签"] = self._dump_weibo_tags(tags)
        data["内容类型"] = content_type
        data["视频封面"] = ""
        data["_text_raw"] = text_raw
        data["_list_text_raw"] = list_text_raw
        data["_long_text_fetched"] = bool(long_text_content)
        data["_content_rich_text"] = content
        data["_pic_ids"] = pic_ids
        data["_pic_url_candidates"] = pic_candidates
        data["_retweeted_pic_url_candidates"] = retweeted_pic_candidates
        data["_video_cover_url_candidates"] = video_cover_candidates
        data["_retweeted_video_cover_url_candidates"] = retweeted_video_cover_candidates
        data["_retweeted_long_text_fetched"] = retweeted_long_text_fetched
        data["_url_struct"] = url_struct
        data["_created_at"] = created_at

        return data

    async def get_info(self, uid: str, old_mid: str | None = None) -> dict:
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
            data["转发微博"] = "{}"
            data["正文结构"] = "[]"
            data["标签"] = "[]"
            data["内容类型"] = "text"
            data["视频封面"] = ""
            data["_candidate_new_posts"] = []
            data["_old_mid_found"] = False
            return data

        statuses = self._get_timeline_statuses(wb_list)
        if not statuses:
            data["文本"] = "无内容"
            data["mid"] = "0"
            data["图片"] = "[]"
            data["转发微博"] = "{}"
            data["正文结构"] = "[]"
            data["标签"] = "[]"
            data["内容类型"] = "text"
            data["视频封面"] = ""
            data["_candidate_new_posts"] = []
            data["_old_mid_found"] = False
            return data

        candidate_statuses, old_mid_found = self._collect_candidate_new_statuses(statuses, old_mid)
        parsed_by_mid: dict[str, dict] = {}

        async def parse_status(status: dict) -> dict:
            cache_key = str(status.get("mid") or id(status))
            if cache_key not in parsed_by_mid:
                parsed_by_mid[cache_key] = await self._build_status_data(data, status)
            return parsed_by_mid[cache_key]

        latest_data = await parse_status(statuses[0])
        candidate_posts = [await parse_status(status) for status in candidate_statuses]
        latest_data["_candidate_new_posts"] = candidate_posts
        latest_data["_old_mid_found"] = old_mid_found

        return latest_data

    def check_info(self, data: dict, old_info: tuple) -> int:
        """
        比对信息
        返回差值：正数表示新增，负数表示删除，0表示无变化
        """
        if len(old_info) < 7:
            return 1  # 数据不完整，默认有变化

        old_mid = old_info[7] if len(old_info) > 7 else ""
        new_mid = data.get("mid", "")
        mid_changed = self._sanitize_path_part(old_mid) != self._sanitize_path_part(new_mid)

        if mid_changed:
            relation = self._created_at_relation_to_old(data, old_info)
            try:
                old_count = int(old_info[5]) if len(old_info) > 5 else 0
                new_count = int(data["微博数"])
                diff = new_count - old_count
            except (ValueError, TypeError):
                diff = 1

            if relation is not None:
                mid_relation = self._mid_relation_to_old(data, old_info)
                if relation > 0 or (relation == 0 and mid_relation == 1):
                    return diff if diff > 0 else 1
                return diff if diff < 0 else 0
            return diff if diff != 0 else 1

        return 0

    async def _get_info_for_process(self, uid: str, old_mid: str | None = None) -> dict:
        """获取用户信息；兼容测试或扩展中旧签名的 get_info monkeypatch。"""
        if not old_mid:
            return await self.get_info(uid)
        try:
            return await self.get_info(uid, old_mid=old_mid)
        except TypeError as e:
            if "old_mid" not in str(e) or "unexpected keyword" not in str(e):
                raise
            return await self.get_info(uid)

    def _data_to_old_info_tuple(self, data: dict) -> tuple:
        """将当前微博数据转换为 old_data_dict 使用的行结构。"""
        return (
            data["UID"],
            data["用户名"],
            data["认证信息"],
            data["简介"],
            data["粉丝数"],
            data["微博数"],
            data["文本"],
            data["mid"],
            data["图片"],
            data["转发微博"],
            data["正文结构"],
            data["标签"],
            data["内容类型"],
            data["视频封面"],
        )

    def _get_posts_to_push(self, data: dict, diff: int) -> list[dict]:
        """根据接口候选与差值生成逐条推送列表，返回顺序为旧到新。"""
        candidates = [
            post for post in data.get("_candidate_new_posts", []) if isinstance(post, dict)
        ]
        if diff <= 0 or not candidates:
            return [data]

        if data.get("_old_mid_found"):
            selected = candidates
        else:
            selected = candidates[:diff]
        return list(reversed(selected)) or [data]

    async def process_user(self, uid: str):
        """处理单个用户"""
        old_info = self.old_data_dict.get(uid)
        old_mid = str(old_info[7]) if old_info and len(old_info) > 7 else None
        try:
            new_data = await self._get_info_for_process(uid, old_mid)
            # 成功获取数据，如果之前被标记为过期，现在标记为有效
            await self.mark_cookie_valid()
        except CookieExpiredError as e:
            # Cookie失效，使用基类统一处理
            await self.handle_cookie_expired(e)
            return  # 不再抛出异常，直接返回
        except Exception as e:
            self.logger.error(f"获取用户 {uid} 数据失败: {e}")
            return

        new_data.setdefault("转发微博", "{}")
        new_data.setdefault("正文结构", "[]")
        new_data.setdefault("标签", "[]")
        new_data.setdefault("内容类型", "text")
        new_data.setdefault("视频封面", "")
        new_data.setdefault("_retweeted_pic_url_candidates", [])
        new_data.setdefault("_video_cover_url_candidates", [])
        new_data.setdefault("_retweeted_video_cover_url_candidates", [])
        new_data.setdefault("_retweeted_long_text_fetched", False)

        if old_info:
            diff = self.check_info(new_data, old_info)

            if diff == 0:
                if self._is_stale_status_snapshot(new_data, old_info):
                    return

                old_retweeted_status = old_info[9] if len(old_info) > 9 else "{}"
                text_changed = not self._texts_equivalent(
                    new_data["文本"], old_info[6] if len(old_info) > 6 else ""
                )
                retweeted_changed = not self._retweeted_statuses_equivalent(
                    new_data.get("转发微博"),
                    old_retweeted_status,
                )
                old_segments = (
                    old_info[WEIBO_CONTENT_SEGMENTS_INDEX]
                    if len(old_info) > WEIBO_CONTENT_SEGMENTS_INDEX
                    else "[]"
                )
                old_tags = old_info[WEIBO_TAGS_INDEX] if len(old_info) > WEIBO_TAGS_INDEX else "[]"
                old_content_type = (
                    old_info[WEIBO_CONTENT_TYPE_INDEX]
                    if len(old_info) > WEIBO_CONTENT_TYPE_INDEX
                    else "text"
                )
                metadata_changed = any(
                    [
                        self._dump_rich_text_segments(
                            self._parse_rich_text_segments(new_data.get("正文结构"))
                        )
                        != self._dump_rich_text_segments(
                            self._parse_rich_text_segments(old_segments)
                        ),
                        self._dump_weibo_tags(new_data.get("标签"))
                        != self._dump_weibo_tags(old_tags),
                        str(new_data.get("内容类型") or "text") != str(old_content_type or "text"),
                    ]
                )
                should_push_long_text = (
                    text_changed and self._is_long_text_backfill(new_data, old_info)
                ) or (
                    retweeted_changed
                    and self._is_retweeted_long_text_backfill(
                        new_data,
                        old_retweeted_status,
                    )
                )
                should_update_db = text_changed or retweeted_changed or metadata_changed
                if len(old_info) > 8:
                    new_data["图片"] = old_info[8]
                if len(old_info) > WEIBO_VIDEO_COVER_INDEX:
                    new_data["视频封面"] = old_info[WEIBO_VIDEO_COVER_INDEX]
                if retweeted_changed:
                    new_retweeted = self._parse_retweeted_status(new_data.get("转发微博"))
                    old_retweeted = self._parse_retweeted_status(old_retweeted_status)
                    if (
                        new_retweeted
                        and old_retweeted
                        and self._sanitize_path_part(new_retweeted.get("mid") or "0")
                        == self._sanitize_path_part(old_retweeted.get("mid") or "0")
                    ):
                        new_retweeted["images"] = old_retweeted.get("images") or []
                        new_retweeted["video_cover"] = old_retweeted.get("video_cover") or ""
                        new_data["转发微博"] = self._dump_retweeted_status(new_retweeted)
                    await self._save_retweeted_images(new_data, keep_existing=True)
                    await self._save_retweeted_video_cover(new_data, keep_existing=True)
                else:
                    new_data["转发微博"] = old_retweeted_status

                if self._needs_post_image_retry(new_data, old_info):
                    image_urls = await self._save_post_images(new_data, keep_existing=True)
                    should_update_db = True
                    self.logger.info(
                        "%s 微博正文图片已补偿下载 %s/%s 张",
                        new_data["用户名"],
                        len(image_urls),
                        len(new_data.get("_pic_url_candidates") or []),
                    )

                if self._needs_retweeted_image_retry(new_data, old_info):
                    image_urls = await self._save_retweeted_images(new_data, keep_existing=True)
                    should_update_db = True
                    self.logger.info(
                        "%s 被转发微博图片已补偿下载 %s/%s 张",
                        new_data["用户名"],
                        len(image_urls),
                        len(new_data.get("_retweeted_pic_url_candidates") or []),
                    )

                if self._needs_video_cover_retry(new_data, old_info):
                    saved_cover = await self._save_video_cover(new_data, keep_existing=True)
                    if saved_cover and self._local_post_image_exists(saved_cover):
                        should_update_db = True
                        self.logger.info("%s 微博视频封面已补偿下载", new_data["用户名"])
                    else:
                        self.logger.debug("%s 微博视频封面本轮补偿未成功", new_data["用户名"])

                if self._needs_retweeted_video_cover_retry(new_data, old_info):
                    saved_cover = await self._save_retweeted_video_cover(
                        new_data, keep_existing=True
                    )
                    if saved_cover and self._local_post_image_exists(saved_cover):
                        should_update_db = True
                        self.logger.info("%s 被转发微博视频封面已补偿下载", new_data["用户名"])
                    else:
                        self.logger.debug(
                            "%s 被转发微博视频封面本轮补偿未成功",
                            new_data["用户名"],
                        )

                if should_update_db:
                    sql = (
                        "UPDATE weibo SET 用户名=%(用户名)s, 认证信息=%(认证信息)s, 简介=%(简介)s, "
                        "粉丝数=%(粉丝数)s, 微博数=%(微博数)s, 文本=%(文本)s, mid=%(mid)s, "
                        "图片=%(图片)s, 转发微博=%(转发微博)s, 正文结构=%(正文结构)s, "
                        "标签=%(标签)s, 内容类型=%(内容类型)s, 视频封面=%(视频封面)s "
                        "WHERE UID=%(UID)s"
                    )
                    updated = await self.db.execute_update(sql, new_data)
                    if not updated:
                        self.logger.error("%s 微博数据补偿写入数据库失败", new_data["用户名"])
                    else:
                        self.old_data_dict[uid] = self._data_to_old_info_tuple(new_data)
                        if should_push_long_text:
                            self.logger.info("%s 微博长文本已补全并写入数据库", new_data["用户名"])
                            await self.push_notification(
                                new_data, 1, notification_reason="long_text_backfill"
                            )
                self.logger.debug(f"{new_data['用户名']} 最近在摸鱼🐟")
            else:
                await self._save_post_images(new_data)
                await self._save_retweeted_images(new_data)
                await self._save_video_cover(new_data)
                await self._save_retweeted_video_cover(new_data)

                # 更新数据
                sql = (
                    "UPDATE weibo SET 用户名=%(用户名)s, 认证信息=%(认证信息)s, 简介=%(简介)s, "
                    "粉丝数=%(粉丝数)s, 微博数=%(微博数)s, 文本=%(文本)s, mid=%(mid)s, "
                    "图片=%(图片)s, 转发微博=%(转发微博)s, 正文结构=%(正文结构)s, "
                    "标签=%(标签)s, 内容类型=%(内容类型)s, 视频封面=%(视频封面)s "
                    "WHERE UID=%(UID)s"
                )
                updated = await self.db.execute_update(sql, new_data)
                if not updated:
                    self.logger.error("更新 %s 微博数据失败，跳过推送", new_data["用户名"])
                    return

                posts_to_push: list[dict] = []
                if diff > 0:
                    posts_to_push = self._get_posts_to_push(new_data, diff)
                    push_count = len(posts_to_push)
                    if push_count == diff:
                        self.logger.info(f"{new_data['用户名']} 发布了{push_count}条微博😍")
                    else:
                        self.logger.info(
                            "%s 微博数增加 %d，本次识别到 %d 条新微博",
                            new_data["用户名"],
                            diff,
                            push_count,
                        )
                else:
                    self.logger.info(f"{new_data['用户名']} 删除了{abs(diff)}条微博😞")

                self.old_data_dict[uid] = self._data_to_old_info_tuple(new_data)

                if diff > 0:
                    if len(posts_to_push) > 1:
                        self.logger.info(
                            "%s 本次检测到 %d 条新微博，将逐条推送",
                            new_data["用户名"],
                            len(posts_to_push),
                        )
                    for post_data in posts_to_push:
                        await self.push_notification(post_data, 1)
                else:
                    await self.push_notification(new_data, diff)
        else:
            await self._save_post_images(new_data)
            await self._save_retweeted_images(new_data)
            await self._save_video_cover(new_data)
            await self._save_retweeted_video_cover(new_data)

            # 新用户插入
            sql = (
                "INSERT INTO weibo (UID, 用户名, 认证信息, 简介, 粉丝数, 微博数, 文本, mid, "
                "图片, 转发微博, 正文结构, 标签, 内容类型, 视频封面) "
                "VALUES (%(UID)s, %(用户名)s, %(认证信息)s, %(简介)s, %(粉丝数)s, "
                "%(微博数)s, %(文本)s, %(mid)s, %(图片)s, %(转发微博)s, %(正文结构)s, "
                "%(标签)s, %(内容类型)s, %(视频封面)s)"
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

            self.old_data_dict[uid] = self._data_to_old_info_tuple(new_data)

    @staticmethod
    def _without_visible_urls(value: object) -> str:
        """兼容旧数据：任何裸露 URL 在推送可见文本中都只显示统一标题。"""
        return re.sub(
            r"(?:https?:)?//[^\s<>'\"\]\[）)]+",
            "网页链接",
            str(value or ""),
            flags=re.IGNORECASE,
        )

    def _get_push_content(self, data: dict) -> RichText:
        """读取主微博正文；新数据保留链接，旧数据安全降级为标题文本。"""
        rich = data.get("_content_rich_text")
        if not isinstance(rich, RichText):
            rich = self._parse_rich_text_segments(data.get("正文结构"))
        if not rich:
            body = self._extract_status_body_from_display_text(data.get("文本", ""))
            rich = RichText.text(body)
        return self._apply_url_struct_fallback(rich, data.get("_url_struct"))

    def _get_retweeted_push_content(self, retweeted: dict) -> RichText:
        rich = self._parse_rich_text_segments(retweeted.get("content_segments"))
        if not rich:
            rich = RichText.text(retweeted.get("text", ""))
        return self._apply_url_struct_fallback(rich, [])

    def _strip_push_tags(self, content: RichText, tags: list[str]) -> RichText:
        """从推送正文移除已单独展示的话题，保留链接片段与其原有顺序。"""
        clean_tags = [tag.strip() for tag in tags if str(tag or "").strip()]
        if not content or not clean_tags:
            return content

        pattern = re.compile(
            "|".join(
                rf"#{re.escape(tag)}#" for tag in sorted(set(clean_tags), key=len, reverse=True)
            )
        )
        segments: list[RichTextSegment] = []
        for segment in content.segments:
            text = pattern.sub("", segment.text)
            text = re.sub(r"[ \t]{2,}", " ", text)
            text = re.sub(r"[ \t]*\n[ \t]*", "\n", text)
            if text:
                segments.append(RichTextSegment(text, segment.url, segment.image_url))
        return self._normalize_rich_text(RichText(segments))

    def _append_push_profile(self, builder: RichTextBuilder, data: dict) -> None:
        verified = self._without_visible_urls(data.get("认证信息")).strip()
        intro = self._without_visible_urls(data.get("简介")).strip()
        if verified:
            builder.text(f"\n\n✨ 认证：{verified}")
        if intro:
            builder.text(f"\n🌱 简介：{intro}")

    def _build_description_for_channel(
        self,
        channel,
        data: dict,
        diff: int = 1,
        notification_reason: str = "status",
    ) -> RichText:
        """构建不暴露实际网址的结构化推送正文。"""
        del channel  # 渲染格式由 UnifiedPushManager 根据通道统一选择。
        builder = RichTextBuilder()
        username = self._without_visible_urls(data.get("用户名") or "这位博主")

        if diff < 0:
            builder.text(f"🍃 看起来 {username} 收起了 {abs(diff)} 条微博，先悄悄记下来啦～")
            self._append_push_profile(builder, data)
            return builder.build()

        retweeted = self._parse_retweeted_status(data.get("转发微博"))
        content = self._get_push_content(data)
        tags = self._parse_weibo_tags(data.get("标签"))
        content = self._strip_push_tags(content, tags)
        if retweeted:
            repost_text = self._normalize_weibo_text_for_compare(content.plain_text())
            if repost_text in {"转发微博", "转发"}:
                repost_text = ""
            if repost_text:
                builder.text("💬 转发时说：\n　　").rich(content)
            else:
                builder.text("💬 悄悄转发，没有留下文字～")
            if tags:
                visible_tags = " ".join(f"#{self._without_visible_urls(tag)}#" for tag in tags)
                builder.text(f"\n🏷️ {visible_tags}")

            builder.text(
                "\n\n────────\n"
                f"🌷 原微博来自 @{self._without_visible_urls(retweeted.get('user_name') or '未知用户')}\n"
            )
            original_tags = self._parse_weibo_tags(retweeted.get("tags"))
            original = self._strip_push_tags(
                self._get_retweeted_push_content(retweeted),
                original_tags,
            )
            original_images = retweeted.get("images") or []
            original_image_count = max(
                len(original_images),
                len(data.get("_retweeted_pic_url_candidates") or []),
            )
            original_type = retweeted.get("content_type") or "text"
            if retweeted.get("source_unavailable"):
                builder.text("这条原微博暂时看不到啦～")
            elif original:
                builder.text("　　").rich(original)
            elif original_image_count:
                builder.text(f"原微博没有写正文，留下了 {original_image_count} 张图片～")
            else:
                builder.text("原微博没有留下正文～")

            if original_type == "video" or retweeted.get("video_cover"):
                builder.text("\n🎬 原微博带了一个视频，点“阅读全文”就能看～")
            if original_image_count:
                builder.text(f"\n🖼️ 原微博有 {original_image_count} 张图片")
            if original_tags:
                visible_tags = " ".join(
                    f"#{self._without_visible_urls(tag)}#" for tag in original_tags
                )
                builder.text(f"\n🏷️ {visible_tags}")
        else:
            if notification_reason == "long_text_backfill":
                builder.text("📝 正文已经补完整啦：\n")
            elif content:
                builder.text("💬 Ta说：\n")
            if content:
                builder.text("　　").rich(content)
            elif data.get("内容类型") == "video":
                builder.text("🎬 新视频已经准备好啦，点“阅读全文”就能看～")
            else:
                builder.text("这条微博没有留下正文～")

            image_count = max(
                len(self._parse_post_image_urls(data.get("图片"))),
                len(data.get("_pic_url_candidates") or []),
            )
            if image_count:
                builder.text(f"\n🖼️ * {image_count}")
            if tags:
                visible_tags = " ".join(f"#{self._without_visible_urls(tag)}#" for tag in tags)
                builder.text(f"\n🏷️ {visible_tags}")

        self._append_push_profile(builder, data)
        return builder.build()

    def _build_push_title(
        self,
        data: dict,
        diff: int,
        notification_reason: str = "status",
    ) -> str:
        username = self._without_visible_urls(data.get("用户名") or "这位博主")
        if notification_reason == "long_text_backfill":
            return f"📝 {username} 的微博正文补充完整啦"
        if diff < 0:
            return f"🍃 {username} 悄悄收起了 {abs(diff)} 条微博"
        content_type = str(data.get("内容类型") or "").strip().lower()
        titles = {
            "repost": f"✨ {username} 转发了一条微博～",
            "video": f"🎬 {username} 分享了一条新视频～",
            "image": f"🖼️ {username} 发来一条新图文～",
            "text": f"💬 {username} 发了条微博～",
        }
        return titles.get(content_type, f"🌟 {username} 有一条新微博～")

    def _public_weibo_image_url(self, image_path: Path) -> str:
        """将微博本地图片路径转换为配置的公开地址。"""
        base_url = (self.config.base_url or "").rstrip("/")
        if not base_url:
            return ""
        try:
            relative = image_path.resolve().relative_to(self._get_weibo_data_dir().resolve())
        except ValueError:
            return ""
        return f"{base_url}{self._build_weibo_img_url(*relative.parts)}"

    def _select_push_cover(self, data: dict) -> tuple[str, Path | None]:
        """按当前视频、原微博视频、主页封面顺序选择推送封面。"""
        retweeted = self._parse_retweeted_status(data.get("转发微博"))
        sources = [
            (
                data.get("视频封面"),
                data.get("_video_cover_url_candidates") or [],
            ),
            (
                retweeted.get("video_cover") if retweeted else "",
                data.get("_retweeted_video_cover_url_candidates") or [],
            ),
        ]
        has_base_url = bool((self.config.base_url or "").strip())
        for stored_url, remote_candidates in sources:
            local_path = self._get_local_post_image_path(str(stored_url or ""))
            if local_path and (not local_path.is_file() or local_path.stat().st_size <= 0):
                local_path = None
            if has_base_url and local_path:
                return self._public_weibo_image_url(local_path), local_path
            if not has_base_url:
                remote_url = next(
                    (
                        safe_url
                        for candidate in remote_candidates
                        if (safe_url := self._safe_weibo_link_url(candidate))
                    ),
                    "",
                )
                if local_path or remote_url:
                    return remote_url, local_path

        safe_username = self._sanitize_username(data.get("用户名", "unknown_user"))
        profile_cover = self._get_weibo_data_dir() / safe_username / "cover_image_phone.jpg"
        if profile_cover.is_file() and profile_cover.stat().st_size > 0:
            return self._public_weibo_image_url(profile_cover), profile_cover
        return "", None

    async def push_notification(
        self,
        data: dict,
        diff: int,
        notification_reason: str = "status",
    ):
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

        if not self.push:
            return

        retweeted = self._parse_retweeted_status(data.get("转发微博"))
        action = "发布" if diff > 0 else "删除"
        count = abs(diff)

        # 为方案一/方案二准备封面图信息：
        # - 方案一：如果配置了 base_url，则优先构造对外可访问的封面图 URL 供大部分通道使用；
        # - 方案二：同时将本地路径通过 extend_data.local_pic_path 传给支持本地上传的通道（如 Telegram）。
        # 同时，为 Bark 等通道准备头像 icon（extend_data.avatar_url）。
        cover_pic_url = ""
        local_pic_path: Path | None = None
        avatar_url = None
        wecom_pic_url = None
        try:
            safe_username = self._sanitize_username(data.get("用户名", "unknown_user"))
            user_dir = self._get_weibo_data_dir() / safe_username
            cover_pic_url, local_pic_path = self._select_push_cover(data)
            if local_pic_path and self._has_wecom_apps_channel():
                wecom_path = local_pic_path.with_name(f"{local_pic_path.stem}_wecom.jpg")
                if self._resize_cover_for_wecom(local_pic_path, wecom_path):
                    wecom_pic_url = self._public_weibo_image_url(wecom_path)

            # 头像（用于 Bark icon）
            profile_path = user_dir / "profile_image.jpg"
            if profile_path.is_file():
                avatar_url = self._public_weibo_image_url(profile_path) or None
        except Exception as e:
            self.logger.debug("构造本地封面图路径失败（已忽略）: %s", e)

        try:
            extend_data: dict = {"hide_visible_jump_url": True}
            # 将本地封面图路径传递给支持本地上传图片的通道
            if local_pic_path:
                extend_data["local_pic_path"] = str(local_pic_path)
            # 为 Bark 等通道传递头像 URL，用作 icon
            if avatar_url:
                extend_data["avatar_url"] = avatar_url
            # 为企业微信通道传递 resize 后的封面 URL（1068×455，符合企微图文消息推荐尺寸）
            if wecom_pic_url:
                extend_data["wecom_pic_url"] = wecom_pic_url

            description = self._build_description_for_channel(
                None,
                data,
                diff=diff,
                notification_reason=notification_reason,
            )
            safe_retweeted = None
            if retweeted:
                original = self._get_retweeted_push_content(retweeted)
                safe_retweeted = {
                    "user_name": self._without_visible_urls(retweeted.get("user_name")),
                    "text": original.plain_text(),
                    "tags": [
                        self._without_visible_urls(tag)
                        for tag in self._parse_weibo_tags(retweeted.get("tags"))
                    ],
                    "content_type": retweeted.get("content_type") or "text",
                    "mid": retweeted.get("mid") or "",
                    "source_unavailable": bool(retweeted.get("source_unavailable")),
                }

            await self.send_push_news(
                title=self._build_push_title(data, diff, notification_reason),
                description=description,
                description_func=lambda channel: self._build_description_for_channel(
                    channel,
                    data,
                    diff=diff,
                    notification_reason=notification_reason,
                ),
                picurl=cover_pic_url
                or "https://cn.bing.com/th?id=OHR.DubrovnikHarbor_ZH-CN8590217905_1920x1080.jpg",
                to_url=f"https://m.weibo.cn/detail/{data['mid']}",
                btntxt="阅读全文",
                extend_data=extend_data,
                event_type="weibo",
                event_data={
                    "username": data.get("用户名"),
                    "text": description.plain_text()[:500],
                    "verified": data.get("认证信息"),
                    "intro": data.get("简介"),
                    "mid": data.get("mid"),
                    "action": action,
                    "count": count,
                    "is_repost": bool(retweeted),
                    "content_type": data.get("内容类型") or "text",
                    "tags": [
                        self._without_visible_urls(tag)
                        for tag in self._parse_weibo_tags(data.get("标签"))
                    ],
                    "retweeted_status": safe_retweeted,
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
            await self.send_push_news(
                title="🍪 微博 Cookie 失效啦",
                description=RichText.text(
                    "微博的登录状态悄悄过期啦～\n\n"
                    "请重新登录并更新 config.yml 里的微博 Cookie，监控就能继续工作啦。"
                ),
                picurl="https://cn.bing.com/th?id=OHR.DubrovnikHarbor_ZH-CN8590217905_1920x1080.jpg",
                to_url="https://weibo.com/login.php",
                btntxt="前往登录",
                extend_data={"hide_visible_jump_url": True},
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
