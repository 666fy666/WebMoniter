"""统一轻可爱推送文案测试。"""

import pytest

from src.push_channel.cute_copy import style_push_description, style_push_title
from src.push_channel.rich_text import RichTextBuilder


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("主播 开播了🐯🐯🐯", "🎙️ 主播 开播啦～"),
        ("主播 下播了💤💤💤", "🌙 主播 下播休息啦～"),
        ("小鱼 发动态了📕", "✨ 小鱼 发了条新动态～"),
        ("【B站】【小鱼】投稿了", "✨ 【B站】【小鱼】带来一份新投稿～"),
        ("品赞签到成功", "🎉 品赞签到成功啦～"),
        ("品赞签到失败", "🥺 品赞签到失败，这次遇到一点小状况"),
        ("科技玩家签到结果", "📮 科技玩家签到结果来啦～"),
        ("今日天气：杭州", "🌤️ 今日天气：杭州来报到啦～"),
        ("双色球开奖通知（第 1 期）", "🎱 双色球开奖通知（第 1 期）新鲜出炉啦～"),
        ("🍪 微博 Cookie 失效啦", "🍪 微博 Cookie 失效啦"),
    ],
)
def test_style_push_title_uses_consistent_cute_voice(raw, expected):
    assert style_push_title(raw) == expected


def test_style_push_description_keeps_original_details():
    description = style_push_description("品赞签到成功", "获得 10 积分")

    assert description == "🎁 好耶，今天的任务顺利完成啦～\n\n获得 10 积分"


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
