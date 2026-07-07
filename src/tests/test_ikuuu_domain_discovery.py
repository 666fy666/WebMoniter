from __future__ import annotations

import pytest

from src.tasks import ikuuu_checkin

pytestmark = pytest.mark.asyncio


class _NoNetworkSession:
    def get(self, *args, **kwargs):
        raise AssertionError("session.get should not be called for an unresolvable host")


async def test_fetch_discovery_page_skips_unresolvable_host(monkeypatch):
    async def unresolvable(host: str, port: int) -> bool:
        return False

    monkeypatch.setattr(ikuuu_checkin, "_ikuuu_host_resolves", unresolvable)

    result = await ikuuu_checkin._fetch_discovery_page(
        _NoNetworkSession(),
        "https://ikuuu.invalid",
    )

    assert result is None


async def test_probe_domain_skips_unresolvable_host(monkeypatch):
    async def unresolvable(host: str, port: int) -> bool:
        return False

    monkeypatch.setattr(ikuuu_checkin, "_ikuuu_host_resolves", unresolvable)

    result = await ikuuu_checkin._probe_domain(_NoNetworkSession(), "ikuuu.invalid")

    assert result is None
