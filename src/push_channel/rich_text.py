"""推送正文的结构化文本与安全渲染。"""

from __future__ import annotations

import html
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal
from urllib.parse import quote, urlsplit

RichTextFormat = Literal["plain", "markdown", "html"]

_MARKDOWN_SPECIAL_RE = re.compile(r"([\\`*_{}\[\]()#+\-.!|>])")


def _safe_http_url(value: object) -> str:
    """仅保留可作为推送链接目标的 HTTP(S) URL。"""
    raw = str(value or "").strip()
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
    return raw


def _escape_markdown(text: str) -> str:
    return _MARKDOWN_SPECIAL_RE.sub(r"\\\1", text)


def _markdown_url(url: str) -> str:
    # Markdown 链接目标中的括号和空白必须编码，避免破坏链接语法。
    return quote(url, safe=":/?&=#%+@,;~!$'*-._")


@dataclass(frozen=True, slots=True)
class RichTextSegment:
    """一段纯文本、隐藏链接文字，或带安全图片源的微博表情。"""

    text: str
    url: str = ""
    image_url: str = ""

    @property
    def is_link(self) -> bool:
        return bool(self.url)

    @property
    def is_emoji(self) -> bool:
        return bool(self.image_url)

    def to_dict(self) -> dict[str, str]:
        if self.image_url:
            return {"type": "emoji", "text": self.text, "src": self.image_url}
        if self.url:
            return {"type": "link", "text": self.text, "url": self.url}
        return {"type": "text", "text": self.text}


class RichText:
    """可按纯文本、Markdown 或 HTML 安全渲染的正文。"""

    __slots__ = ("segments",)

    def __init__(self, segments: Iterable[RichTextSegment] | None = None):
        self.segments = tuple(self._merge_segments(segments or ()))

    @staticmethod
    def _merge_segments(segments: Iterable[RichTextSegment]) -> list[RichTextSegment]:
        merged: list[RichTextSegment] = []
        for item in segments:
            text = str(item.text or "")
            image_url = _safe_http_url(item.image_url)
            url = "" if image_url else _safe_http_url(item.url)
            if not text:
                continue
            segment = RichTextSegment(text=text, url=url, image_url=image_url)
            if (
                merged
                and not segment.is_link
                and not segment.is_emoji
                and not merged[-1].is_link
                and not merged[-1].is_emoji
            ):
                previous = merged[-1]
                merged[-1] = RichTextSegment(previous.text + text)
            else:
                merged.append(segment)
        return merged

    @classmethod
    def text(cls, value: object) -> RichText:
        return cls([RichTextSegment(str(value or ""))])

    @classmethod
    def from_dicts(cls, raw_segments: object) -> RichText:
        if not isinstance(raw_segments, list):
            return cls()
        segments: list[RichTextSegment] = []
        for raw in raw_segments:
            if not isinstance(raw, dict):
                continue
            text = str(raw.get("text") or "")
            segment_type = raw.get("type")
            if segment_type == "emoji":
                image_url = _safe_http_url(raw.get("src"))
                segments.append(RichTextSegment(text, image_url=image_url))
                continue
            url = raw.get("url") if segment_type == "link" else ""
            segments.append(RichTextSegment(text, _safe_http_url(url)))
        return cls(segments)

    def to_dicts(self) -> list[dict[str, str]]:
        return [segment.to_dict() for segment in self.segments]

    def plain_text(self) -> str:
        """只拼接可见文字，不会把链接目标字段追加到正文。"""
        return "".join(segment.text for segment in self.segments)

    def __bool__(self) -> bool:
        return bool(self.segments)

    def __add__(self, other: RichText) -> RichText:
        if not isinstance(other, RichText):
            return NotImplemented
        return RichText((*self.segments, *other.segments))

    def _render_segment(self, segment: RichTextSegment, output_format: RichTextFormat) -> str:
        if output_format == "plain":
            return segment.text
        if output_format == "html":
            label = html.escape(segment.text)
            if segment.url:
                return f'<a href="{html.escape(segment.url, quote=True)}">{label}</a>'
            return label

        label = _escape_markdown(segment.text)
        if segment.url:
            return f"[{label}]({_markdown_url(segment.url)})"
        return label

    def render(
        self,
        output_format: RichTextFormat = "plain",
        max_bytes: int | None = None,
    ) -> str:
        """安全渲染，并在需要时按完整片段截断，绝不截断富文本语法。"""
        rendered = [self._render_segment(segment, output_format) for segment in self.segments]
        full = "".join(rendered)
        if max_bytes is None or len(full.encode("utf-8")) <= max_bytes:
            return full
        if max_bytes <= 0:
            return ""

        ellipsis = self._render_segment(RichTextSegment("……"), output_format)
        ellipsis_size = len(ellipsis.encode("utf-8"))
        if max_bytes <= ellipsis_size:
            return "" if max_bytes < 3 else "…"

        budget = max_bytes - ellipsis_size
        result: list[str] = []
        used = 0
        for segment, rendered_segment in zip(self.segments, rendered, strict=True):
            segment_size = len(rendered_segment.encode("utf-8"))
            if used + segment_size <= budget:
                result.append(rendered_segment)
                used += segment_size
                continue

            # 链接整体放不下时只保留可见标题，避免输出半截 URL 或损坏语法。
            remaining_text = segment.text
            partial: list[str] = []
            for char in remaining_text:
                rendered_char = self._render_segment(RichTextSegment(char), output_format)
                char_size = len(rendered_char.encode("utf-8"))
                if used + char_size > budget:
                    break
                partial.append(rendered_char)
                used += char_size
            result.extend(partial)
            break

        result.append(ellipsis)
        final = "".join(result)
        # 防御性保证；理论上上述预算已经满足限制。
        if len(final.encode("utf-8")) > max_bytes:
            return "……" if len("……".encode()) <= max_bytes else ""
        return final


class RichTextBuilder:
    """便于监控器组合正文的轻量构建器。"""

    def __init__(self) -> None:
        self._segments: list[RichTextSegment] = []

    def text(self, value: object) -> RichTextBuilder:
        text = str(value or "")
        if text:
            self._segments.append(RichTextSegment(text))
        return self

    def link(self, label: object, url: object) -> RichTextBuilder:
        text = str(label or "").strip() or "网页链接"
        safe_url = _safe_http_url(url)
        self._segments.append(RichTextSegment(text, safe_url))
        return self

    def emoji(self, alt: object, image_url: object) -> RichTextBuilder:
        """追加微博内联表情；地址异常时保留可读的 alt 文字。"""
        text = str(alt or "").strip()
        if not text:
            return self
        safe_url = _safe_http_url(image_url)
        self._segments.append(RichTextSegment(text, image_url=safe_url))
        return self

    def rich(self, value: RichText) -> RichTextBuilder:
        self._segments.extend(value.segments)
        return self

    def build(self) -> RichText:
        return RichText(self._segments)
