from __future__ import annotations

from typing import Any, Mapping
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from services.instagram_signature import verify_signature_wp
from services.whatsapp_cloud import handle_whatsapp_cloud_webhook_payload

from .types import ConnectionStartResult, ConnectionStatusResult, WebhookHandleResult


class MetaWhatsAppCloudProvider:
    """Current official WhatsApp Cloud implementation behind a provider boundary."""

    channel = "whatsapp"
    provider_name = "meta_official"

    def verify_webhook_signature(self, body: bytes, signature: str | None) -> bool:
        return bool(signature and verify_signature_wp(body, signature))

    async def handle_webhook_payload(
        self,
        session: AsyncSession,
        payload: Mapping[str, Any],
    ) -> WebhookHandleResult:
        await handle_whatsapp_cloud_webhook_payload(session, payload)
        return WebhookHandleResult(channel=self.channel, provider=self.provider_name)

    async def start_connection(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        payload: Mapping[str, Any],
    ) -> ConnectionStartResult:
        raise HTTPException(
            status_code=501,
            detail="WhatsApp Cloud connection is still handled by crm_api routes; move it here when changing providers.",
        )

    async def get_connection_status(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
    ) -> ConnectionStatusResult:
        raise HTTPException(
            status_code=501,
            detail="WhatsApp Cloud status is still handled by crm_api routes; move it here when changing providers.",
        )

    async def disconnect(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
    ) -> ConnectionStatusResult:
        raise HTTPException(
            status_code=501,
            detail="WhatsApp Cloud disconnect is still handled by crm_api routes; move it here when changing providers.",
        )
