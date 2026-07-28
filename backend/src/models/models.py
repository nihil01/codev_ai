import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import VECTOR
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.db import Base


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="admin")
    instagram_company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instagram_companies.id", ondelete="CASCADE"), nullable=True
    )
    whatsapp_company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("whatsapp_cloud_integrations.id", ondelete="SET NULL"), nullable=True
    )
    ig_activated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    wp_activated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class InstagramCompany(Base):
    __tablename__ = "instagram_companies"

    id: Mapped[uuid.UUID] = uuid_pk()
    instagram_account_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    instagram_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    instagram_account_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    instagram_profile_picture_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class ZernioCompanyProfile(Base):
    __tablename__ = "zernio_company_profiles"
    __table_args__ = (
        UniqueConstraint("company_id", name="uq_zernio_company_profiles_company"),
        UniqueConstraint("zernio_profile_id", name="uq_zernio_company_profiles_profile"),
        Index("ix_zernio_company_profiles_user_id", "user_id"),
        Index("ix_zernio_company_profiles_company_email", "company_email"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instagram_companies.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    zernio_profile_id: Mapped[str] = mapped_column(Text, nullable=False)
    profile_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    company_email: Mapped[str] = mapped_column(Text, nullable=False)
    company_profile: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class ZernioInstagramConnectedAccount(Base):
    __tablename__ = "zernio_instagram_connected_accounts"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "zernio_account_id",
            name="uq_zernio_instagram_connected_accounts_company_account",
        ),
        UniqueConstraint(
            "zernio_account_id",
            name="uq_zernio_instagram_connected_accounts_account",
        ),
        Index("ix_zernio_instagram_connected_accounts_company_id", "company_id"),
        Index("ix_zernio_instagram_connected_accounts_profile_id", "zernio_profile_id"),
        Index("ix_zernio_instagram_connected_accounts_instagram_account_id", "instagram_account_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instagram_companies.id", ondelete="CASCADE"), nullable=False
    )
    zernio_profile_id: Mapped[str] = mapped_column(Text, nullable=False)
    zernio_account_id: Mapped[str] = mapped_column(Text, nullable=False)
    instagram_account_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    username: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    account_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class ZernioWhatsAppConnectedAccount(Base):
    __tablename__ = "zernio_whatsapp_connected_accounts"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "zernio_account_id",
            name="uq_zernio_whatsapp_connected_accounts_company_account",
        ),
        UniqueConstraint(
            "zernio_account_id",
            name="uq_zernio_whatsapp_connected_accounts_account",
        ),
        Index("ix_zernio_whatsapp_connected_accounts_company_id", "company_id"),
        Index("ix_zernio_whatsapp_connected_accounts_profile_id", "zernio_profile_id"),
        Index("ix_zernio_whatsapp_connected_accounts_whatsapp_account_id", "whatsapp_account_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instagram_companies.id", ondelete="CASCADE"), nullable=False
    )
    zernio_profile_id: Mapped[str] = mapped_column(Text, nullable=False)
    zernio_account_id: Mapped[str] = mapped_column(Text, nullable=False)
    whatsapp_account_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    username: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    account_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class ZernioWebhookEvent(Base):
    __tablename__ = "zernio_webhook_events"
    __table_args__ = (
        Index("ix_zernio_webhook_events_company_id", "company_id"),
        Index("ix_zernio_webhook_events_zernio_account_id", "zernio_account_id"),
        Index("ix_zernio_webhook_events_zernio_profile_id", "zernio_profile_id"),
        Index("ix_zernio_webhook_events_received_at", "received_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instagram_companies.id", ondelete="SET NULL"), nullable=True
    )
    zernio_profile_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    zernio_account_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    platform: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    headers: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class InstagramToken(Base):
    __tablename__ = "instagram_tokens"

    id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("instagram_companies.id", ondelete="CASCADE"), nullable=False)
    token_kind: Mapped[str] = mapped_column(String(32), nullable=False, default="long_lived", server_default=text("'long_lived'"))
    access_token: Mapped[str] = mapped_column(Text, nullable=False)
    permissions: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    refresh_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class InstagramSystemPrompt(Base):
    __tablename__ = "instagram_system_prompts"

    id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("instagram_companies.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="Default prompt", server_default=text("'Default prompt'"))
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class CompanyKnowledgeBaseEntry(Base):
    __tablename__ = "company_knowledge_base_entries"

    id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("instagram_companies.id", ondelete="CASCADE"), nullable=False)
    entry_type: Mapped[str] = mapped_column(String(32), nullable=False, default="text", server_default=text("'text'"))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    quantity_available: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    embedding: Mapped[list[float] | None] = mapped_column(VECTOR(1536), nullable=True)


class InstagramConversation(Base):
    __tablename__ = "instagram_conversations"
    __table_args__ = (UniqueConstraint("company_id", "customer_instagram_id", name="uq_company_customer_conversation"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("instagram_companies.id", ondelete="CASCADE"), nullable=False)
    customer_instagram_id: Mapped[str] = mapped_column(String(128), nullable=False)
    customer_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class InstagramMessage(Base):
    __tablename__ = "instagram_messages"
    __table_args__ = (UniqueConstraint("company_id", "instagram_mid", name="uq_instagram_messages_company_mid"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("instagram_conversations.id", ondelete="CASCADE"), nullable=False)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("instagram_companies.id", ondelete="CASCADE"), nullable=False)
    instagram_mid: Mapped[str | None] = mapped_column(String(512), nullable=True)
    sender_instagram_id: Mapped[str] = mapped_column(String(128), nullable=False)
    recipient_instagram_id: Mapped[str] = mapped_column(String(128), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    message_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    message_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class InstagramWebhookEvent(Base):
    __tablename__ = "instagram_webhook_events"

    id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("instagram_companies.id", ondelete="CASCADE"), nullable=True)
    instagram_mid: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    sender_instagram_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    recipient_instagram_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, default="message", server_default=text("'message'"))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class InstagramDataDeletionRequest(Base):
    __tablename__ = "instagram_data_deletion_requests"

    id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("instagram_companies.id", ondelete="SET NULL"), nullable=True)
    confirmation_code: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, nullable=False)
    request_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="completed", server_default=text("'completed'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class WhatsAppCloudIntegration(Base):
    __tablename__ = "whatsapp_cloud_integrations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    meta_business_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    waba_id: Mapped[str] = mapped_column(Text, nullable=False)
    phone_number_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    access_token: Mapped[str] = mapped_column(Text, nullable=False)

    display_phone_number: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    quality_rating: Mapped[str | None] = mapped_column(Text, nullable=True)

    webhook_subscribed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )

    registration_pin: Mapped[str | None] = mapped_column(Text, nullable=True)
    registered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    disconnected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

class WhatsAppConversation(Base):
    __tablename__ = "whatsapp_conversations"
    __table_args__ = (UniqueConstraint("company_id", "customer_whatsapp_id", name="uq_company_customer_whatsapp_conversation"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("instagram_companies.id", ondelete="CASCADE"), nullable=False)
    conversation_whatsapp_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_whatsapp_id: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class WhatsAppMessage(Base):
    __tablename__ = "whatsapp_messages"

    id: Mapped[uuid.UUID] = uuid_pk()
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("whatsapp_conversations.id", ondelete="CASCADE"), nullable=False)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("instagram_companies.id", ondelete="CASCADE"), nullable=False)
    whatsapp_mid: Mapped[str | None] = mapped_column(String(512), nullable=True)
    sender_whatsapp_id: Mapped[str] = mapped_column(String(255), nullable=False)
    recipient_whatsapp_id: Mapped[str] = mapped_column(String(255), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    message_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    message_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    has_media: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    message_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class WhatsAppCloudConversation(Base):
    __tablename__ = "whatsapp_cloud_conversations"
    __table_args__ = (
        UniqueConstraint("company_id", "integration_id", "customer_whatsapp_id", name="uq_wp_cloud_company_integration_customer"),
        Index("ix_wp_cloud_conversations_company_last_message", "company_id", "last_message_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("instagram_companies.id", ondelete="CASCADE"), nullable=False)
    integration_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("whatsapp_cloud_integrations.id", ondelete="CASCADE"), nullable=False)
    phone_number_id: Mapped[str] = mapped_column(Text, nullable=False)
    waba_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    customer_whatsapp_id: Mapped[str] = mapped_column(Text, nullable=False)
    customer_phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    customer_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class WhatsAppCloudMessage(Base):
    __tablename__ = "whatsapp_cloud_messages"
    __table_args__ = (
        Index("ux_wp_cloud_messages_company_mid", "company_id", "whatsapp_mid", unique=True),
        Index("ix_wp_cloud_messages_conversation_created", "conversation_id", "created_at"),
        Index("ix_wp_cloud_messages_company_created", "company_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("whatsapp_cloud_conversations.id", ondelete="CASCADE"), nullable=False)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("instagram_companies.id", ondelete="CASCADE"), nullable=False)
    integration_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("whatsapp_cloud_integrations.id", ondelete="CASCADE"), nullable=False)
    whatsapp_mid: Mapped[str | None] = mapped_column(Text, nullable=True)
    sender_whatsapp_id: Mapped[str] = mapped_column(Text, nullable=False)
    recipient_whatsapp_id: Mapped[str] = mapped_column(Text, nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    message_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    message_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    has_media: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    message_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class CustomerOrder(Base):
    __tablename__ = "customer_orders"
    __table_args__ = (
        Index("ux_customer_orders_company_channel_source_message", "company_id", "channel", "source_message_id", unique=True),
        Index("ix_customer_orders_company_status", "company_id", "status"),
        Index("ix_customer_orders_company_created_at", "company_id", "created_at"),
        Index("ix_customer_orders_customer_id", "customer_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("instagram_companies.id", ondelete="CASCADE"), nullable=False)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    customer_id: Mapped[str] = mapped_column(Text, nullable=False)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    source_message_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    customer_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    customer_phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_price: Mapped[str | None] = mapped_column(Text, nullable=True)
    quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    delivery_required: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    delivery_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_time: Mapped[str | None] = mapped_column(Text, nullable=True)
    customer_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_summary: Mapped[str] = mapped_column(Text, nullable=False)
    raw_intent_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="new", server_default=text("'new'"))
    manager_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revenue_amount: Mapped[Any | None] = mapped_column(Numeric(12, 2), nullable=True)
    cost_amount: Mapped[Any | None] = mapped_column(Numeric(12, 2), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class CompanyManager(Base):
    __tablename__ = "company_managers"
    __table_args__ = (UniqueConstraint("company_id", "channel", "recipient_id", name="ux_company_managers_company_channel_recipient"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("instagram_companies.id", ondelete="CASCADE"), nullable=False)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    recipient_id: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class OrderManagerNotification(Base):
    __tablename__ = "order_manager_notifications"

    id: Mapped[uuid.UUID] = uuid_pk()
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customer_orders.id", ondelete="CASCADE"), nullable=False)
    manager_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("company_managers.id", ondelete="SET NULL"), nullable=True)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("instagram_companies.id", ondelete="CASCADE"), nullable=False)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    recipient_id: Mapped[str] = mapped_column(Text, nullable=False)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", server_default=text("'pending'"))
    external_message_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BroadcastCampaign(Base):
    __tablename__ = "broadcast_campaigns"

    id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("instagram_companies.id", ondelete="CASCADE"), nullable=False)
    target: Mapped[str] = mapped_column(String(32), nullable=False)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", server_default=text("'pending'"))
    requested_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    sent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BroadcastRecipient(Base):
    __tablename__ = "broadcast_recipients"
    __table_args__ = (UniqueConstraint("campaign_id", "channel", "recipient_id", name="ux_broadcast_recipients_campaign_channel_recipient"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    campaign_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("broadcast_campaigns.id", ondelete="CASCADE"), nullable=False)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("instagram_companies.id", ondelete="CASCADE"), nullable=False)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    recipient_id: Mapped[str] = mapped_column(Text, nullable=False)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", server_default=text("'pending'"))
    external_message_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
