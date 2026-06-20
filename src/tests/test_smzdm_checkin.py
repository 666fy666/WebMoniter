"""什么值得买签到 API 响应解析辅助函数测试。"""

from src.tasks.smzdm_checkin import (
    _smzdm_api_success,
    _smzdm_data,
    _smzdm_error_msg,
)


def test_smzdm_api_success_codes() -> None:
    assert _smzdm_api_success({"error_code": 0})
    assert _smzdm_api_success({"error_code": "0"})
    assert _smzdm_api_success({"error_code": None, "data": {}})
    assert not _smzdm_api_success({"error_code": "11111"})
    assert not _smzdm_api_success({"error_code": 4})
    assert not _smzdm_api_success(None)
    assert not _smzdm_api_success([])


def test_smzdm_data_handles_null_and_non_dict() -> None:
    assert _smzdm_data({"data": {"token": "abc"}}) == {"token": "abc"}
    assert _smzdm_data({"data": None}) == {}
    assert _smzdm_data({"data": []}) == {}


def test_smzdm_error_msg() -> None:
    assert _smzdm_error_msg({"error_msg": " 失败 "}, "默认") == "失败"
    assert _smzdm_error_msg({}, "默认") == "默认"
