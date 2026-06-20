"""core.utils 工具函数测试。"""

import pytest

from src.core.utils import mask_cookie_for_log


@pytest.mark.parametrize(
    ("cookie", "expected"),
    [
        ("", "***"),
        ("short", "***"),
        ("a" * 11, "***"),
        ("a" * 19, "***"),
        ("a" * 20, "aaaaaaaa***aaaa"),
        ("0123456789012345678901234", "01234567***1234"),
    ],
)
def test_mask_cookie_for_log(cookie: str, expected: str) -> None:
    assert mask_cookie_for_log(cookie) == expected
