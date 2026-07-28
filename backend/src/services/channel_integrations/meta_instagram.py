from __future__ import annotations

import logging
from typing import Any, Mapping
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from services.instagram_data import instagram_mid_exists
from services.instagram_oauth import get_instagram_customer_profile
from services.instagram_signature import verify_signature_ig
from services.webhooks import handle_message

from .types import ConnectionStartResult, ConnectionStatusResult, WebhookHandleResult

logger = logging.getLogger(__name__)


class MetaInstagramProvider:
    """Current official Meta Instagram implementation behind a provider boundary."""

    channel = "instagram"
    provider_name = "meta_official"

    def verify_webhook_signature(self, body: bytes, signature: str | None) -> bool:
        return bool(signature and verify_signature_ig(body, signature))

    async def handle_webhook_payload(
        self,
        session: AsyncSession,
        payload: Mapping[str, Any],
    ) -> WebhookHandleResult:
        handled = 0
        skipped = 0

        entries = payload.get("entry", [])
        if not isinstance(entries, list):
            return WebhookHandleResult(self.channel, self.provider_name, skipped=1)

        for entry in entries:
            if not isinstance(entry, Mapping):
                skipped += 1
                continue

            messaging_events = entry.get("messaging", [])
            if not isinstance(messaging_events, list):
                skipped += 1
                continue

            for message_event in messaging_events:
                if not isinstance(message_event, dict):
                    skipped += 1
                    continue

                message = message_event.get("message")
                if not isinstance(message, Mapping):
                    logger.info(
                        "Skipping non-message Instagram event keys=%s",
                        list(message_event.keys()),
                    )
                    skipped += 1
                    continue

                sender_id = message_event.get("sender", {}).get("id")
                recipient_id = message_event.get("recipient", {}).get("id")
                mid = message.get("mid")
                is_echo = bool(message.get("is_echo"))
                text_message = (message.get("text") or "").strip()

                if not sender_id or not recipient_id:
                    logger.warning("Skipping event without sender/recipient: %s", message_event)
                    skipped += 1
                    continue

                if is_echo:
                    logger.info("Skipping Instagram echo message mid=%s", mid)
                    skipped += 1
                    continue

                if not mid:
                    logger.warning("Skipping Instagram message without mid: %s", message_event)
                    skipped += 1
                    continue

                if not text_message:
                    logger.info("Skipping non-text Instagram message mid=%s", mid)
                    skipped += 1
                    continue

                if await instagram_mid_exists(session, instagram_mid=str(mid)):
                    logger.warning(
                        "Skipping already saved Instagram message mid=%s sender=%s recipient=%s",
                        mid,
                        sender_id,
                        recipient_id,
                    )
                    skipped += 1
                    continue

                profile = await get_instagram_customer_profile(
                    session,
                    sender_id=str(sender_id),
                    recipient_id=str(recipient_id),
                )

                await handle_message(message_event, profile, session)
                handled += 1

        return WebhookHandleResult(
            channel=self.channel,
            provider=self.provider_name,
            handled=handled,
            skipped=skipped,
        )

    async def start_connection(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        payload: Mapping[str, Any],
    ) -> ConnectionStartResult:
        raise HTTPException(
            status_code=501,
            detail="Instagram Meta connection is still handled by routers.instagram_auth; move it here when changing providers.",
        )

    async def get_connection_status(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
    ) -> ConnectionStatusResult:
        raise HTTPException(
            status_code=501,
            detail="Instagram Meta status is still handled by crm_api routes; move it here when changing providers.",
        )

    async def disconnect(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
    ) -> ConnectionStatusResult:
        raise HTTPException(
            status_code=501,
            detail="Instagram Meta disconnect is still handled by crm_api routes; move it here when changing providers.",
        )
