from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class WebhookHandleResult:
    """Small, provider-neutral result for webhook dispatch diagnostics."""

    channel: str
    provider: str
    handled: int = 0
    skipped: int = 0
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ConnectionStartResult:
    """Provider-neutral connection/bootstrap response for future SDK flows."""

    channel: str
    provider: str
    redirect_url: str | None = None
    external_account_id: str | None = None
    status: str = "pending"
    raw: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ConnectionStatusResult:
    """Provider-neutral status shape used by connection adapters."""

    channel: str
    provider: str
    connected: bool
    external_account_id: str | None = None
    display_name: str | None = None
    raw: Mapping[str, Any] = field(default_factory=dict)


class ChannelIntegrationProvider(Protocol):
    """Boundary for provider-specific social channel integrations.

    Auth stays in the existing CRM/JWT layer. Only external channel connection,
    signature verification, webhook parsing, and outbound SDK/API calls belong
    behind this protocol.
    """

    channel: str
    provider_name: str

    def verify_webhook_signature(self, body: bytes, signature: str | None) -> bool:
        """Return True when this provider accepts the webhook signature."""
        ...

    async def handle_webhook_payload(
        self,
        session: AsyncSession,
        payload: Mapping[str, Any],
    ) -> WebhookHandleResult:
        """Parse and process a provider webhook payload."""
        ...

    async def start_connection(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        payload: Mapping[str, Any],
    ) -> ConnectionStartResult:
        """Start a channel connection flow.

        Existing Meta official code can keep its current routers until we cut
        over. The integrator SDK implementation should live here rather than
        leaking SDK calls into routers/components.
        """
        ...

    async def get_connection_status(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
    ) -> ConnectionStatusResult:
        """Return normalized provider connection status."""
        ...

    async def disconnect(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
    ) -> ConnectionStatusResult:
        """Disconnect/deactivate a provider channel integration."""
        ...
