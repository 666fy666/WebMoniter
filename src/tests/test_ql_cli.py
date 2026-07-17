"""青龙 CLI smoke 测试。"""

import subprocess
import sys

from src.ql.compat import load_config_from_env


def test_ql_list_includes_ikuuu_checkin() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "src.ql", "--list"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "ikuuu_checkin" in result.stdout
    assert "weibo_cookie_refresh" not in result.stdout


def test_rainyun_ql_single_account_env_builds_accounts(monkeypatch) -> None:
    monkeypatch.setenv("WEBMONITER_RAINYUN_ENABLE", "true")
    monkeypatch.setenv("WEBMONITER_RAINYUN_USERNAME", " user ")
    monkeypatch.setenv("WEBMONITER_RAINYUN_PASSWORD", " pass ")
    monkeypatch.setenv("WEBMONITER_RAINYUN_API_KEY", " key ")

    cfg = load_config_from_env("rainyun_checkin")

    assert cfg["rainyun_enable"] is True
    assert cfg["rainyun_accounts"] == [{"username": "user", "password": "pass", "api_key": "key"}]
