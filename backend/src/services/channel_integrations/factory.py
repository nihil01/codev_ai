from __future__ import annotations

from config.app_config import settings

from .meta_instagram import MetaInstagramProvider
from .meta_whatsapp import MetaWhatsAppCloudProvider
from .types import ChannelIntegrationProvider

META_OFFICIAL = "meta_official"


def _normalize_provider(value: str | None) -> str:
    return (value or META_OFFICIAL).strip().lower().replace("-", "_")


def get_instagram_provider() -> ChannelIntegrationProvider:
    provider = _normalize_provider(settings.instagram_integration_provider)
    if provider == META_OFFICIAL:
        return MetaInstagramProvider()
    raise ValueError(f"Unsupported Instagram integration provider: {provider}")


def get_whatsapp_provider() -> ChannelIntegrationProvider:
    provider = _normalize_provider(settings.whatsapp_integration_provider)
    if provider == META_OFFICIAL:
        return MetaWhatsAppCloudProvider()
    raise ValueError(f"Unsupported WhatsApp integration provider: {provider}")
