"""配置工具函数测试。"""

import pytest

from src.settings.config import AppConfig, parse_checkin_time


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("08:00", ("8", "0")),
        ("23:45", ("23", "45")),
        ("  7:5  ", ("7", "5")),
        ("", ("8", "0")),
        ("8", ("8", "0")),
        ("invalid", ("8", "0")),
        ("25:00", ("8", "0")),
    ],
)
def test_parse_checkin_time(raw: str, expected: tuple[str, str]) -> None:
    assert parse_checkin_time(raw) == expected


def test_app_config_mutable_defaults_are_isolated() -> None:
    first = AppConfig()
    second = AppConfig()

    first.push_channel_list.append({"name": "main", "type": "demo"})
    first.plugins["demo_task"] = {"enable": True}
    first.checkin_push_channels.append("main")

    assert second.push_channel_list == []
    assert second.plugins == {}
    assert second.checkin_push_channels == []
