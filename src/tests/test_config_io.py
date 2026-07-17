"""Tests for Web config merge helpers."""

import errno

import pytest
import yaml

from src.settings import config_writer
from src.settings.config_writer import (
    ConfigValueUpdate,
    apply_config_updates,
    run_write_transaction,
)
from src.web.config_io import merge_config_to_yaml


def test_merge_config_to_yaml_preserves_existing_fields_and_removes_empty_accounts(tmp_path):
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        """
checkin:
  enable: true
  email: old@example.com
  password: secret
  accounts:
    - email: a@example.com
      password: p
  push_channels: [main]
push_channel:
  - name: main
    type: demo
    user_id: old-user
  - name: stale
    type: demo
""".lstrip(),
        encoding="utf-8",
    )

    merged = merge_config_to_yaml(
        config_path,
        {
            "checkin": {
                "time": "09:15",
                "accounts": [],
                "push_channels": ["ops"],
            },
            "push_channel": [
                {
                    "name": "main",
                    "type": "demo",
                }
            ],
        },
    )

    data = yaml.safe_load(merged)
    assert data["checkin"]["enable"] is True
    assert data["checkin"]["email"] == "old@example.com"
    assert data["checkin"]["password"] == "secret"
    assert data["checkin"]["time"] == "09:15"
    assert "accounts" not in data["checkin"]
    assert data["checkin"]["push_channels"] == ["ops"]
    assert data["push_channel"] == [{"name": "main", "type": "demo"}]


def test_merge_config_to_yaml_handles_missing_config_file(tmp_path):
    config_path = tmp_path / "missing.yml"

    merged = merge_config_to_yaml(config_path, {"app": {"base_url": "http://example.test"}})

    assert yaml.safe_load(merged) == {"app": {"base_url": "http://example.test"}}


@pytest.mark.parametrize(
    ("initial_enable", "initial_time", "new_enable", "new_time"),
    [
        (False, "21:00", True, "22:15"),
        (True, "22:15", False, "20:05"),
    ],
)
def test_merge_config_to_yaml_applies_weibo_cookie_refresh_fields(
    tmp_path,
    initial_enable,
    initial_time,
    new_enable,
    new_time,
):
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        "\n".join(
            [
                "weibo:",
                f"  cookie_refresh_enable: {str(initial_enable).lower()}",
                f'  cookie_refresh_time: "{initial_time}"',
                "  cookie: preserved-cookie",
                "",
            ]
        ),
        encoding="utf-8",
    )

    merged = merge_config_to_yaml(
        config_path,
        {
            "weibo": {
                "cookie_refresh_enable": new_enable,
                "cookie_refresh_time": new_time,
            }
        },
    )

    data = yaml.safe_load(merged)
    assert data["weibo"]["cookie_refresh_enable"] is new_enable
    assert data["weibo"]["cookie_refresh_time"] == new_time
    assert data["weibo"]["cookie"] == "preserved-cookie"


@pytest.mark.asyncio
async def test_apply_config_updates_preserves_comments_quotes_and_unrelated_edits(tmp_path):
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        """
weibo:
  # keep this comment
  cookie: "old-cookie"
  uids: "123"
weibo_chaohua:
  cookie: "old-chaohua"
""".lstrip(),
        encoding="utf-8",
    )

    result = await apply_config_updates(
        config_path,
        [ConfigValueUpdate(("weibo", "cookie"), "old-cookie", "new-cookie")],
    )

    content = config_path.read_text(encoding="utf-8")
    assert result.wrote_file is True
    assert result.changed_paths == ("weibo.cookie",)
    assert "# keep this comment" in content
    assert 'cookie: "new-cookie"' in content
    assert 'uids: "123"' in content
    assert "old-chaohua" in content


@pytest.mark.asyncio
async def test_apply_config_updates_detects_conflict_without_writing(tmp_path):
    config_path = tmp_path / "config.yml"
    original = "weibo:\n  cookie: current\n"
    config_path.write_text(original, encoding="utf-8")

    result = await apply_config_updates(
        config_path,
        [ConfigValueUpdate(("weibo", "cookie"), "stale", "new")],
    )

    assert result.wrote_file is False
    assert result.conflict_paths == ("weibo.cookie",)
    assert config_path.read_text(encoding="utf-8") == original


@pytest.mark.asyncio
async def test_write_transaction_falls_back_for_bind_mounted_file(tmp_path, monkeypatch):
    config_path = tmp_path / "config.yml"
    config_path.write_text("weibo:\n  enable: true\n", encoding="utf-8")

    def busy_replace(source, target):
        raise OSError(errno.EBUSY, "bind mount")

    monkeypatch.setattr(config_writer.os, "replace", busy_replace)

    await run_write_transaction(
        config_path,
        lambda: "weibo:\n  enable: false\n",
    )

    assert yaml.safe_load(config_path.read_text(encoding="utf-8"))["weibo"]["enable"] is False
