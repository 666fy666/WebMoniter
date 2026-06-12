"""配置工具函数测试。"""

import pytest

from src.settings.config import parse_checkin_time


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
