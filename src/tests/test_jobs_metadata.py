"""任务与配置元数据一致性测试。"""

import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from src.jobs import registry
from src.jobs.enable_fields import (
    MONITOR_JOB_ENABLE_FIELD_MAP,
    TASK_JOB_ENABLE_FIELD_MAP,
)
from src.jobs.metadata import (
    CONFIG_SECTION_ORDER,
    MONITOR_MODULES,
    MONITOR_SPECS,
    PUSH_CHANNEL_SPECS,
    TASK_ENV_MAP,
    TASK_MODULES,
    TASK_SPECS,
    get_task_spec,
)
from src.push_channel import _channel_type_to_class
from src.settings.config import AppConfig
from src.settings.loader_specs import CONFIG_MAPPINGS
from src.web.routers import config as config_router
from src.web.routers import pages as pages_router
from src.web.templating import STATIC_ASSET_VERSION, templates


def test_metadata_drives_legacy_registry_exports() -> None:
    assert MONITOR_MODULES == [spec.module for spec in MONITOR_SPECS]
    assert TASK_MODULES == [spec.module for spec in TASK_SPECS]
    assert registry.MONITOR_MODULES is MONITOR_MODULES
    assert registry.TASK_MODULES is TASK_MODULES


def test_enable_maps_are_generated_from_task_specs() -> None:
    assert MONITOR_JOB_ENABLE_FIELD_MAP == {
        spec.job_id: spec.enable_field for spec in MONITOR_SPECS if spec.enable_field
    }
    assert TASK_JOB_ENABLE_FIELD_MAP == {
        spec.job_id: spec.enable_field
        for spec in TASK_SPECS
        if spec.enable_field and not spec.plugin_only
    }
    assert TASK_JOB_ENABLE_FIELD_MAP["ikuuu_checkin"] == "checkin_enable"
    assert "demo_task" not in TASK_JOB_ENABLE_FIELD_MAP


def test_ql_env_map_is_generated_from_task_specs() -> None:
    assert TASK_ENV_MAP["aliyun_checkin"] == (
        "ALIYUN",
        {"REFRESH_TOKEN": "aliyun_refresh_token", "TIME": "aliyun_time"},
    )
    assert TASK_ENV_MAP["demo_task"][0] == "DEMO_TASK"


def test_ql_env_map_fields_exist_on_app_config() -> None:
    fields = set(AppConfig.model_fields)
    for job_id, (_, env_map) in TASK_ENV_MAP.items():
        for env_name, field_name in env_map.items():
            if field_name.startswith("plugins."):
                continue
            assert field_name in fields, f"{job_id}: {env_name}->{field_name}"


def test_config_section_order_covers_loader_and_frontend_extras() -> None:
    for section in CONFIG_MAPPINGS:
        assert section in CONFIG_SECTION_ORDER
    assert CONFIG_SECTION_ORDER[-3:] == ("quiet_hours", "push_channel", "plugins")


def test_config_section_order_matches_frontend_template() -> None:
    html = Path("src/webUI/templates/config.html").read_text(encoding="utf-8")
    js = Path("src/webUI/static/js/config.js").read_text(encoding="utf-8")
    template_sections = tuple(re.findall(r'data-section="([^"]+)"', html))

    assert template_sections == CONFIG_SECTION_ORDER
    assert "/api/config/metadata" in js
    assert 'config.js?v={{ static_version }}' in html
    assert "cookie_refresh_enable: weiboCookieRefreshEnable" in js
    assert "cookie_refresh_time:" in js
    assert 'data-module="system"' in html
    assert 'id="mysql_password"' in html
    assert "refreshDatabaseStatus" in js
    assert "'/api/database/test'" in js


def test_config_page_asset_uses_shared_static_version() -> None:
    context = pages_router._page_context(SimpleNamespace(), "配置管理", "config")

    assert "config_js_version" not in context
    assert STATIC_ASSET_VERSION == "1"
    assert templates.env.globals["static_version"] == STATIC_ASSET_VERSION


def test_frontend_fallback_metadata_matches_backend() -> None:
    js = Path("src/webUI/static/js/config.js").read_text(encoding="utf-8")
    fallback_sections_match = re.search(
        r"const FALLBACK_CONFIG_SECTIONS = \[(.*?)\];",
        js,
        re.S,
    )
    assert fallback_sections_match is not None
    fallback_sections = tuple(re.findall(r"'([^']+)'", fallback_sections_match.group(1)))

    push_types_match = re.search(r"let pushChannelTypes = \{(.*?)\n\};", js, re.S)
    assert push_types_match is not None
    fallback_push_types = set(re.findall(r"^\s*'([^']+)':\s*\{", push_types_match.group(1), re.M))

    assert fallback_sections == CONFIG_SECTION_ORDER
    assert fallback_push_types == {spec.type for spec in PUSH_CHANNEL_SPECS}


def test_config_sample_contains_metadata_sections() -> None:
    sample = yaml.safe_load(Path("config/config.yml.sample").read_text(encoding="utf-8"))

    for section in CONFIG_SECTION_ORDER:
        assert section in sample


def test_push_channel_specs_match_registered_channel_types() -> None:
    assert {spec.type for spec in PUSH_CHANNEL_SPECS} == set(_channel_type_to_class)
    assert get_task_spec("weibo_monitor").push_container_id == "weibo_push_channels"
    assert get_task_spec("__missing__") is None


@pytest.mark.asyncio
async def test_config_metadata_api_shape(monkeypatch) -> None:
    monkeypatch.setattr(config_router, "check_login", lambda session_id: session_id == "ok")

    response = await config_router.get_config_metadata_api(
        SimpleNamespace(session={"session_id": "ok"})
    )
    body = json.loads(response.body)

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "checkin" in body["sections"]
    assert body["push_channel_types"]["wecom_bot"]["fields"] == ["key"]
    checkin = next(task for task in body["tasks"] if task["job_id"] == "ikuuu_checkin")
    assert checkin["config_section"] == "checkin"
    assert checkin["push_container_id"] == "checkin_push_channels"
    refresh = next(task for task in body["tasks"] if task["job_id"] == "weibo_cookie_refresh")
    assert refresh["config_section"] == "weibo"
    assert refresh["default_time"] == "21:00"
    assert refresh["env_prefix"] is None


@pytest.mark.asyncio
async def test_config_metadata_api_requires_login(monkeypatch) -> None:
    monkeypatch.setattr(config_router, "check_login", lambda session_id: False)

    response = await config_router.get_config_metadata_api(
        SimpleNamespace(session={"session_id": "bad"})
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_config_api_disables_cache(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yml").write_text(
        "weibo:\n  cookie_refresh_enable: true\n  cookie_refresh_time: '20:30'\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config_router, "check_login", lambda session_id: session_id == "ok")

    response = await config_router.get_config_api(
        SimpleNamespace(session={"session_id": "ok"}),
        format="json",
    )
    body = json.loads(response.body)

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert body["config"]["weibo"] == {
        "cookie_refresh_enable": True,
        "cookie_refresh_time": "20:30",
    }


@pytest.mark.asyncio
async def test_database_status_api_is_authenticated_and_contains_no_credentials(monkeypatch) -> None:
    monkeypatch.setattr(config_router, "check_login", lambda session_id: session_id == "ok")
    monkeypatch.setattr(
        config_router,
        "get_database_status",
        lambda: _async_value(
            {
                "configured": True,
                "active_backend": "mysql",
                "mysql_reachable": True,
                "sqlite_healthy": True,
                "sync_state": "in_sync",
                "pending_changes": 0,
                "last_sync_at": None,
                "message": "已同步",
            }
        ),
    )

    response = await config_router.get_database_status_api(
        SimpleNamespace(session={"session_id": "ok"})
    )
    body = json.loads(response.body)

    assert response.status_code == 200
    assert body["active_backend"] == "mysql"
    assert "password" not in body
    assert "host" not in body


async def _async_value(value):
    return value


class _JsonRequest:
    session = {"session_id": "ok"}

    def __init__(self, payload):
        self.payload = payload

    async def json(self):
        return self.payload


@pytest.mark.asyncio
async def test_database_connection_api_tests_unsaved_values_without_returning_password(monkeypatch) -> None:
    tested = []
    monkeypatch.setattr(config_router, "check_login", lambda session_id: session_id == "ok")
    monkeypatch.setattr(config_router, "get_config", lambda: AppConfig())

    async def fake_test(config):
        tested.append(config)

    monkeypatch.setattr(config_router, "test_database_config", fake_test)
    response = await config_router.test_database_connection_api(
        _JsonRequest(
            {
                "mysql": {
                    "enabled": True,
                    "host": "db.internal",
                    "user": "monitor",
                    "password": "private-value",
                    "database": "webmoniter",
                }
            }
        )
    )
    body = json.loads(response.body)

    assert response.status_code == 200
    assert tested[0].mysql_password == "private-value"
    assert "private-value" not in response.body.decode()
    assert body["success"] is True
