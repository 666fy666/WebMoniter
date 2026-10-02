import pytest
import yaml

from src.web import config_service
from src.web.routers.v1 import read_log_chunk


@pytest.mark.asyncio
async def test_masked_secret_survives_reordering_and_conflicting_write(tmp_path):
    path = tmp_path / "config.yml"
    path.write_text(
        "checkin:\n  accounts:\n    - email: a\n      password: first-secret\n    - email: b\n      password: second-secret\n"
    )
    response = config_service.read_config(path)
    assert "first-secret" not in str(response)
    patch = response["config"]
    patch["checkin"]["accounts"].reverse()
    await config_service.write_config(response["version"], patch, path=path)
    saved = yaml.safe_load(path.read_text())
    assert saved["checkin"]["accounts"][0]["password"] == "second-secret"
    with pytest.raises(config_service.ConfigConflictError):
        await config_service.write_config(response["version"], patch, path=path)


@pytest.mark.asyncio
async def test_clear_secret_and_preserve_other_section(tmp_path):
    path = tmp_path / "config.yml"
    path.write_text("weibo:\n  cookie: secret\nhuya:\n  rooms: '123'\n")
    response = config_service.read_config(path)
    await config_service.write_config(response["version"], {"weibo": {"cookie": ""}}, path=path)
    saved = yaml.safe_load(path.read_text())
    assert saved["weibo"]["cookie"] == ""
    assert saved["huya"]["rooms"] == "123"


def test_log_cursor_handles_append_partial_lines_and_rotation(tmp_path):
    path = tmp_path / "main.log"
    path.write_text("第一行\n第二行\n")
    first = read_log_chunk(path, None, 100)
    assert first["lines"] == ["第一行\n", "第二行\n"]
    assert read_log_chunk(path, first["cursor"], 100)["lines"] == []
    with path.open("a") as stream:
        stream.write("第三")
    assert read_log_chunk(path, first["cursor"], 100)["lines"] == []
    with path.open("a") as stream:
        stream.write("行\n")
    assert read_log_chunk(path, first["cursor"], 100)["lines"] == ["第三行\n"]
    path.rename(tmp_path / "old.log")
    path.write_text("new\n")
    assert read_log_chunk(path, first["cursor"], 100)["reset"] is True


def test_log_chunk_is_bounded(tmp_path):
    path = tmp_path / "main.log"
    path.write_text("x" * 1024 * 1024 + "\n")
    result = read_log_chunk(path, None, 1000)
    assert sum(len(s) for s in result["lines"]) <= 256 * 1024


def test_metadata_covers_all_task_sections():
    metadata = config_service.metadata()
    for spec in metadata["tasks"]:
        if not spec["plugin_only"]:
            assert spec["config_section"] in metadata["defaults"]


def test_metadata_does_not_enable_missing_sections():
    defaults = config_service.metadata()["defaults"]
    assert defaults["push_channel"] == []
    for section in defaults.values():
        if isinstance(section, dict):
            for key in ("enable", "enabled", "cookie_refresh_enable"):
                assert section.get(key, False) is False


def test_log_budget_preserves_open_file(tmp_path):
    import logging

    from src.jobs.log_manager import enforce_log_budget

    active = tmp_path / "main.log"
    old = tmp_path / "main.log.1"
    old.write_text("x" * 100)
    handler = logging.FileHandler(active)
    logging.root.addHandler(handler)
    try:
        active.write_text("current")
        enforce_log_budget(tmp_path, limit=10)
        assert not old.exists()
        assert active.read_text() == "current"
    finally:
        logging.root.removeHandler(handler)
        handler.close()


def test_masks_nested_headers_without_masking_cookie_refresh_controls():
    result = config_service.mask(
        {
            "cookie": "private",
            "cookie_refresh_enable": False,
            "cookie_refresh_time": "21:00",
            "headers": {"X-Custom-Credential": "nested-private"},
        }
    )
    assert result["cookie_refresh_enable"] is False
    assert result["cookie_refresh_time"] == "21:00"
    assert "private" not in str(result)
    assert result["cookie"].startswith("__KEEP_SECRET__:")
    assert result["headers"]["X-Custom-Credential"].startswith("__KEEP_SECRET__:")
