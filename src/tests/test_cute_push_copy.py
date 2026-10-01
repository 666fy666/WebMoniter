"""统一轻可爱推送文案测试。"""

from src.push_channel.cute_copy import style_push_description
from src.push_channel.rich_text import RichTextBuilder


def test_style_push_description_keeps_original_details():
    description = style_push_description("品赞签到成功", "获得 10 积分")

    assert description.endswith("获得 10 积分")


def test_style_push_description_preserves_rich_text_links():
    original = (
        RichTextBuilder().text("查看 ").link("网页链接", "https://example.com/detail").build()
    )

    description = style_push_description("Demo 任务执行完成", original)

    assert description.plain_text().endswith("查看 网页链接")
    assert 'href="https://example.com/detail"' in description.render("html")


def test_style_push_description_leaves_weibo_copy_unchanged():
    original = RichTextBuilder().text("💬 Ta说：\n　　正文").build()

    assert style_push_description("💬 小鱼 发了条微博～", original) is original
