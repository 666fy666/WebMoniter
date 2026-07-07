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
from src.settings.loader_specs import CONFIG_MAPPINGS
from src.web.routers import config as config_router


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
    assert "checkin" in body["sections"]
    assert body["push_channel_types"]["wecom_bot"]["fields"] == ["key"]
    checkin = next(task for task in body["tasks"] if task["job_id"] == "ikuuu_checkin")
    assert checkin["config_section"] == "checkin"
    assert checkin["push_container_id"] == "checkin_push_channels"


@pytest.mark.asyncio
async def test_config_metadata_api_requires_login(monkeypatch) -> None:
    monkeypatch.setattr(config_router, "check_login", lambda session_id: False)

    response = await config_router.get_config_metadata_api(
        SimpleNamespace(session={"session_id": "bad"})
    )

    assert response.status_code == 401
