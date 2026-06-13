"""Tests for Web config merge helpers."""

import yaml

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
