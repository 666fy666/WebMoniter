"""任务公共辅助函数测试。"""

import logging

import pytest

from src.settings.config import AppConfig
from src.tasks import common


def test_normalized_string_items_prefers_multi_values() -> None:
    assert common.normalized_string_items([" a ", "", "b"], single="fallback") == [
        "a",
        "b",
    ]
    assert common.normalized_string_items([], single=" fallback ") == ["fallback"]
    assert common.normalized_string_items([], single="") == []


def test_normalized_accounts_prefers_valid_multi_accounts() -> None:
    accounts = [
        {"email": " a@example.com ", "password": "p"},
        {"email": "missing-password", "password": ""},
        "not-a-dict",
    ]

    assert common.normalized_accounts(accounts, ("email", "password")) == [
        {"email": "a@example.com", "password": "p"}
    ]


def test_normalized_accounts_falls_back_to_single_account() -> None:
    assert common.normalized_accounts(
        [],
        ("email", "password"),
        single_account={"email": " one@example.com ", "password": " secret "},
    ) == [{"email": "one@example.com", "password": "secret"}]
    assert (
        common.normalized_accounts(
            [],
            ("email", "password"),
            single_account={"email": "one@example.com", "password": ""},
        )
        == []
    )


def test_cron_kwargs_and_any_success() -> None:
    config = AppConfig(checkin_time="07:35")

    assert common.cron_kwargs_from_config(config, "checkin_time", "08:00") == {
        "hour": "7",
        "minute": "35",
    }
    assert common.any_success(
        [
            common.AccountRunResult(False, "failed"),
            common.AccountRunResult(True, "ok"),
        ]
    )
    assert not common.any_success([common.AccountRunResult(False, "failed")])


@pytest.mark.asyncio
async def test_send_text_if_allowed_skips_quiet_hours(monkeypatch) -> None:
    class FakePush:
        def __init__(self) -> None:
            self.sent = False

        async def send_text(self, **kwargs) -> None:
            self.sent = True

    push = FakePush()
    monkeypatch.setattr(common, "is_in_quiet_hours", lambda config: True)

    sent = await common.send_text_if_allowed(
        push,
        AppConfig(),
        logging.getLogger(__name__),
        quiet_log="quiet",
        error_log="error: %s",
        title="title",
        content="content",
    )

    assert sent is False
    assert push.sent is False


@pytest.mark.asyncio
async def test_push_manager_context_closes_on_exit(monkeypatch) -> None:
    class FakeManager:
        def __init__(self) -> None:
            self.closed = False

        async def close(self) -> None:
            self.closed = True

    manager = FakeManager()

    async def fake_build_push_manager(
        push_channel_list,
        session,
        logger,
        *,
        init_fail_prefix,
        channel_names,
    ):
        assert push_channel_list == [{"name": "main", "type": "demo"}]
        assert channel_names == ["main"]
        return manager

    monkeypatch.setattr(common, "build_push_manager", fake_build_push_manager)

    with pytest.raises(RuntimeError):
        async with common.push_manager_context(
            AppConfig(push_channel_list=[{"name": "main", "type": "demo"}]),
            logging.getLogger(__name__),
            push_channels=["main"],
        ) as push:
            assert push is manager
            raise RuntimeError("boom")

    assert manager.closed is True
