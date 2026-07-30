from typing import Any, cast

import pytest

from services.channel_integrations.factory import (
    META_OFFICIAL,
    get_instagram_provider,
    get_whatsapp_provider,
)
from routers import instagram_webhook


def test_default_channel_providers_are_available_without_optional_env(monkeypatch) -> None:
    monkeypatch.delenv("INSTAGRAM_INTEGRATION_PROVIDER", raising=False)
    monkeypatch.delenv("WHATSAPP_INTEGRATION_PROVIDER", raising=False)

    instagram = get_instagram_provider()
    whatsapp = get_whatsapp_provider()

    assert instagram.provider_name == META_OFFICIAL
    assert whatsapp.provider_name == META_OFFICIAL


def test_default_providers_can_validate_webhook_signatures_without_optional_env() -> None:
    instagram = get_instagram_provider()
    whatsapp = get_whatsapp_provider()

    assert instagram.verify_webhook_signature(b"{}", "sha256=invalid") is False
    assert whatsapp.verify_webhook_signature(b"{}", "sha256=invalid") is False


@pytest.mark.asyncio
async def test_zernio_delivery_to_legacy_webhooks_path_is_dispatched(monkeypatch) -> None:
    expected = {"ok": True, "provider": "zernio", "stored": True}

    async def fake_zernio_handler(request, *, path, db):
        assert path == ""
        assert db == "db"
        return expected

    class FakeRequest:
        headers = {"x-zernio-signature": "sha256=test"}

    monkeypatch.setattr(
        instagram_webhook,
        "handle_zernio_webhook_request",
        fake_zernio_handler,
    )

    result = await instagram_webhook.webhook_wp(
        cast(Any, FakeRequest()),
        db=cast(Any, "db"),
    )

    assert result == expected
