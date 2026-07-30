from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any, Literal, TypedDict, cast

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from services.chat_runtime import fetch_recent_chat_history, persist_message
from services.customer_orders import create_customer_order
from services.knowledge_base import build_knowledge_context, find_relevant_knowledge_entries
from services.manager_notifications import notify_managers_about_order
from services.openai_messaging import detect_order_intent, generate_reply, hydrate_order_intent_customer_fields
from services.prompt_defaults import DEFAULT_COMMENT_SYSTEM_PROMPT_AZ, DEFAULT_SYSTEM_PROMPT_AZ
from services.voice_transcription import extract_audio_url, is_audio_message_type, transcribe_audio_url
from services.subscriptions import check_usage_available, increment_usage, is_voice_payload
from services.conversation_control import (
    HANDOFF_INTENTS,
    can_bot_reply,
    classify_intent_from_order_intent,
    handoff_to_manager,
    mark_outbound_activity,
    notify_human_message,
    update_inbound_window,
    update_message_intent,
)
from services.webhooks import build_order_confirmation_message

logger = logging.getLogger(__name__)

SENSITIVE_HEADER_NAMES = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "x-zernio-signature",
    "x-hub-signature",
    "x-hub-signature-256",
}

ACCOUNT_ID_KEYS = (
    "zernioAccountId",
    "zernio_account_id",
    "accountId",
    "account_id",
    "accountID",
    "account",
)

PROFILE_ID_KEYS = (
    "zernioProfileId",
    "zernio_profile_id",
    "profileId",
    "profile_id",
    "profile",
)

PLATFORM_KEYS = ("platform", "network", "channel", "socialNetwork", "social_network")
EVENT_TYPE_KEYS = ("event", "eventType", "event_type", "type", "action")


class ZernioAccountLookup(TypedDict):
    company_id: uuid.UUID
    platform_account_id: str | None
    username: str | None
    display_name: str | None


class ZernioCompanyRuntime(TypedDict):
    company_id: uuid.UUID
    prompt_text: str
    bot_enabled: bool


class ParsedZernioMessage(TypedDict):
    platform: Literal["instagram", "whatsapp"]
    direction: Literal["inbound", "outbound"]
    zernio_account_id: str
    zernio_profile_id: str | None
    zernio_conversation_id: str
    external_message_id: str
    customer_id: str
    customer_username: str | None
    customer_name: str | None
    text: str
    message_type: str | None
    has_media: bool
    sent_at: datetime | None


class ParsedZernioComment(TypedDict):
    platform: Literal["instagram"]
    zernio_account_id: str
    zernio_profile_id: str | None
    platform_comment_id: str
    platform_post_id: str
    zernio_post_id: str | None
    parent_comment_id: str | None
    author_id: str
    author_username: str | None
    author_name: str | None
    author_picture: str | None
    text: str
    created_at: datetime | None
    is_reply: bool
    is_ad_comment: bool
    ad_id: str | None
    ad_title: str | None


def jsonable(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [jsonable(item) for item in value]
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")

    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return jsonable(model_dump())

    dict_method = getattr(value, "dict", None)
    if callable(dict_method):
        return jsonable(dict_method())

    if hasattr(value, "__dict__"):
        return jsonable(vars(value))
    return str(value)


def sanitize_headers(headers: Mapping[str, str]) -> dict[str, str]:
    sanitized: dict[str, str] = {}
    for key, value in headers.items():
        normalized_key = key.lower()
        sanitized[key] = "***" if normalized_key in SENSITIVE_HEADER_NAMES else value
    return sanitized


def _extract_nested_id(value: Any) -> str | None:
    if isinstance(value, Mapping):
        nested = value.get("_id") or value.get("id") or value.get("account_id") or value.get("profile_id")
        return str(nested) if nested else None
    return str(value) if value else None


def _walk_for_key(payload: Any, keys: tuple[str, ...]) -> str | None:
    if isinstance(payload, Mapping):
        for key in keys:
            if key in payload:
                value = _extract_nested_id(payload[key])
                if value:
                    return value
        for value in payload.values():
            found = _walk_for_key(value, keys)
            if found:
                return found
    elif isinstance(payload, Sequence) and not isinstance(payload, str | bytes | bytearray):
        for item in payload:
            found = _walk_for_key(item, keys)
            if found:
                return found
    return None


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text_value = str(value).strip()
    return text_value or None


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _parse_iso_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, int | float):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (ValueError, OSError):
            return None

    text_value = str(value).strip()
    if not text_value:
        return None
    if text_value.endswith("Z"):
        text_value = f"{text_value[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text_value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _normalize_platform(value: Any) -> Literal["instagram", "whatsapp"] | None:
    platform = str(value or "").strip().lower()
    if platform in {"instagram", "ig"}:
        return "instagram"
    if platform in {"whatsapp", "whatsapp_cloud", "wp", "wa"}:
        return "whatsapp"
    return None


def _normalize_direction(value: Any) -> Literal["inbound", "outbound"] | None:
    direction = str(value or "").strip().lower()
    if direction in {"incoming", "inbound", "received", "customer"}:
        return "inbound"
    if direction in {"outgoing", "outbound", "sent", "company", "business"}:
        return "outbound"
    return None


def extract_zernio_account_id(payload: Mapping[str, Any]) -> str | None:
    account = _mapping(payload.get("account"))
    account_id = _string_or_none(account.get("id") or account.get("_id"))
    return account_id or _walk_for_key(payload, ACCOUNT_ID_KEYS)


def extract_zernio_profile_id(payload: Mapping[str, Any]) -> str | None:
    account = _mapping(payload.get("account"))
    profile_id = _string_or_none(account.get("profileId") or account.get("profile_id"))
    return profile_id or _walk_for_key(payload, PROFILE_ID_KEYS)


def extract_platform(payload: Mapping[str, Any]) -> str | None:
    message = _mapping(payload.get("message"))
    account = _mapping(payload.get("account"))
    platform = _normalize_platform(message.get("platform") or account.get("platform") or _walk_for_key(payload, PLATFORM_KEYS))
    return platform


def extract_event_type(payload: Mapping[str, Any]) -> str | None:
    return _walk_for_key(payload, EVENT_TYPE_KEYS)


def parse_zernio_comment_payload(payload: Mapping[str, Any]) -> ParsedZernioComment | None:
    event_type = extract_event_type(payload)
    if event_type != "comment.received":
        return None

    comment = _mapping(payload.get("comment"))
    post = _mapping(payload.get("post"))
    account = _mapping(payload.get("account"))
    author = _mapping(comment.get("author"))
    ad = _mapping(comment.get("ad"))

    platform = _normalize_platform(comment.get("platform") or account.get("platform"))
    zernio_account_id = extract_zernio_account_id(payload)
    platform_comment_id = _string_or_none(comment.get("id"))
    platform_post_id = _string_or_none(comment.get("platformPostId") or comment.get("platform_post_id") or post.get("platformPostId"))
    author_id = _string_or_none(author.get("id"))

    if platform != "instagram" or not zernio_account_id or not platform_comment_id or not platform_post_id or not author_id:
        return None

    return {
        "platform": "instagram",
        "zernio_account_id": zernio_account_id,
        "zernio_profile_id": extract_zernio_profile_id(payload),
        "platform_comment_id": platform_comment_id,
        "platform_post_id": platform_post_id,
        "zernio_post_id": _string_or_none(comment.get("postId") or comment.get("post_id") or post.get("id")),
        "parent_comment_id": _string_or_none(comment.get("parentCommentId") or comment.get("parent_comment_id")),
        "author_id": author_id,
        "author_username": _string_or_none(author.get("username")),
        "author_name": _string_or_none(author.get("name")),
        "author_picture": _string_or_none(author.get("picture")),
        "text": _string_or_none(comment.get("text") or comment.get("message")) or "",
        "created_at": _parse_iso_datetime(comment.get("createdAt") or comment.get("created_at") or payload.get("timestamp")),
        "is_reply": bool(comment.get("isReply") or comment.get("is_reply")),
        "is_ad_comment": bool(ad),
        "ad_id": _string_or_none(ad.get("id")),
        "ad_title": _string_or_none(ad.get("title")),
    }


def parse_zernio_message_payload(payload: Mapping[str, Any]) -> ParsedZernioMessage | None:
    event_type = extract_event_type(payload)
    if event_type and not str(event_type).startswith("message."):
        return None

    message = _mapping(payload.get("message"))
    conversation = _mapping(payload.get("conversation"))
    account = _mapping(payload.get("account"))
    sender = _mapping(message.get("sender"))

    platform = _normalize_platform(message.get("platform") or account.get("platform"))
    direction = _normalize_direction(message.get("direction"))
    zernio_account_id = extract_zernio_account_id(payload)

    if not platform or not direction or not zernio_account_id:
        return None

    external_message_id = _string_or_none(
        message.get("platformMessageId")
        or message.get("platform_message_id")
        or message.get("id")
        or payload.get("id")
    )
    attachments = message.get("attachments")
    has_media = isinstance(attachments, Sequence) and not isinstance(attachments, str | bytes | bytearray) and bool(attachments)
    text_message = _string_or_none(message.get("text") or message.get("body") or message.get("caption")) or ""
    message_type = _string_or_none(message.get("type")) or ("media" if has_media else "text")
    if not text_message and (is_audio_message_type(message_type) or has_media):
        audio_url = extract_audio_url(payload)
        if audio_url:
            # Async transcription is done later in persist_parsed_zernio_message.
            text_message = ""

    participant_id = _string_or_none(
        conversation.get("participantId")
        or conversation.get("participant_id")
        or conversation.get("platformConversationId")
        or conversation.get("platform_conversation_id")
    )
    sender_id = _string_or_none(sender.get("id"))
    customer_id = sender_id if direction == "inbound" else participant_id
    customer_id = customer_id or participant_id or sender_id or _string_or_none(conversation.get("id"))

    zernio_conversation_id = _string_or_none(
        conversation.get("id") or message.get("conversationId") or message.get("conversation_id")
    )

    if not external_message_id or not customer_id or not zernio_conversation_id:
        return None

    customer_username = _string_or_none(
        (sender.get("username") if direction == "inbound" else None)
        or conversation.get("participantUsername")
        or conversation.get("participant_username")
        or sender.get("username")
    )
    customer_name = _string_or_none(
        (sender.get("name") if direction == "inbound" else None)
        or conversation.get("participantName")
        or conversation.get("participant_name")
        or sender.get("name")
    )

    return ParsedZernioMessage(
        platform=platform,
        direction=direction,
        zernio_account_id=zernio_account_id,
        zernio_profile_id=extract_zernio_profile_id(payload),
        zernio_conversation_id=zernio_conversation_id,
        external_message_id=external_message_id,
        customer_id=customer_id,
        customer_username=customer_username,
        customer_name=customer_name,
        text=text_message,
        message_type=message_type,
        has_media=has_media,
        sent_at=_parse_iso_datetime(message.get("sentAt") or message.get("sent_at") or payload.get("timestamp")),
    )


async def resolve_zernio_account(
    db: AsyncSession,
    *,
    platform: str | None,
    zernio_account_id: str | None,
    zernio_profile_id: str | None,
) -> ZernioAccountLookup | None:
    if platform == "instagram" and zernio_account_id:
        result = await db.execute(
            text(
                """
                select company_id, instagram_account_id as platform_account_id, username, display_name
                from zernio_instagram_connected_accounts
                where zernio_account_id = :zernio_account_id
                order by last_seen_at desc nulls last, updated_at desc nulls last
                limit 1
                """
            ),
            {"zernio_account_id": zernio_account_id},
        )
        row = result.mappings().first()
        if row:
            return ZernioAccountLookup(
                company_id=cast(uuid.UUID, row["company_id"]),
                platform_account_id=_string_or_none(row["platform_account_id"]),
                username=_string_or_none(row["username"]),
                display_name=_string_or_none(row["display_name"]),
            )

    if platform == "whatsapp" and zernio_account_id:
        result = await db.execute(
            text(
                """
                select company_id, whatsapp_account_id as platform_account_id, username, display_name
                from zernio_whatsapp_connected_accounts
                where zernio_account_id = :zernio_account_id
                order by last_seen_at desc nulls last, updated_at desc nulls last
                limit 1
                """
            ),
            {"zernio_account_id": zernio_account_id},
        )
        row = result.mappings().first()
        if row:
            return ZernioAccountLookup(
                company_id=cast(uuid.UUID, row["company_id"]),
                platform_account_id=_string_or_none(row["platform_account_id"]),
                username=_string_or_none(row["username"]),
                display_name=_string_or_none(row["display_name"]),
            )

    if zernio_profile_id:
        result = await db.execute(
            text(
                """
                select company_id, null::text as platform_account_id, null::text as username, profile_name as display_name
                from zernio_company_profiles
                where zernio_profile_id = :zernio_profile_id
                limit 1
                """
            ),
            {"zernio_profile_id": zernio_profile_id},
        )
        row = result.mappings().first()
        if row:
            return ZernioAccountLookup(
                company_id=cast(uuid.UUID, row["company_id"]),
                platform_account_id=None,
                username=None,
                display_name=_string_or_none(row["display_name"]),
            )

    return None


async def resolve_company_id_for_zernio_event(
    db: AsyncSession,
    *,
    zernio_account_id: str | None,
    zernio_profile_id: str | None,
    platform: str | None = None,
) -> uuid.UUID | None:
    account = await resolve_zernio_account(
        db,
        platform=platform,
        zernio_account_id=zernio_account_id,
        zernio_profile_id=zernio_profile_id,
    )
    return account["company_id"] if account else None


async def _mark_zernio_event_processed(db: AsyncSession, event_id: uuid.UUID, processed: bool) -> None:
    await db.execute(
        text(
            """
            update zernio_webhook_events
            set processed = :processed,
                processed_at = case when :processed then now() else processed_at end
            where id = :event_id
            """
        ),
        {"event_id": event_id, "processed": processed},
    )


async def persist_zernio_whatsapp_message(
    session: AsyncSession,
    *,
    company_id: uuid.UUID,
    customer_id: str,
    company_account_id: str,
    direction: Literal["inbound", "outbound"],
    text_message: str,
    whatsapp_mid: str,
    payload: Mapping[str, Any],
    customer_name: str | None,
    customer_phone: str | None,
    sent_at: datetime | None,
    sender_type: str | None = None,
    manager_id: uuid.UUID | None = None,
    zernio_conversation_id: str | None = None,
) -> tuple[uuid.UUID, uuid.UUID | None]:
    now = datetime.now(timezone.utc)
    message_time = sent_at or now

    existing_result = await session.execute(
        text(
            """
            select id
            from whatsapp_messages
            where company_id = :company_id and whatsapp_mid = :whatsapp_mid
            limit 1
            """
        ),
        {"company_id": company_id, "whatsapp_mid": whatsapp_mid},
    )
    existing_message_id = existing_result.scalar_one_or_none()
    if existing_message_id:
        conversation_result = await session.execute(
            text("select conversation_id from whatsapp_messages where id = :id"),
            {"id": existing_message_id},
        )
        return cast(uuid.UUID, conversation_result.scalar_one()), cast(uuid.UUID, existing_message_id)

    usage_kind = "voice_message" if is_voice_payload(payload, _string_or_none(payload.get("message", {}).get("type") if isinstance(payload.get("message"), Mapping) else None)) else "text_message"
    await check_usage_available(session, company_id, usage_kind)

    await session.execute(
        text(
            """
            insert into whatsapp_conversations (
                company_id,
                conversation_whatsapp_id,
                zernio_conversation_id,
                customer_whatsapp_id,
                customer_phone,
                customer_name,
                last_message_at,
                created_at,
                updated_at
            ) values (
                :company_id,
                :conversation_whatsapp_id,
                :zernio_conversation_id,
                :customer_id,
                :customer_phone,
                :customer_name,
                :message_time,
                :now,
                :now
            )
            on conflict (company_id, customer_whatsapp_id)
            do update set
                conversation_whatsapp_id = coalesce(excluded.conversation_whatsapp_id, whatsapp_conversations.conversation_whatsapp_id),
                zernio_conversation_id = coalesce(excluded.zernio_conversation_id, whatsapp_conversations.zernio_conversation_id),
                customer_phone = coalesce(excluded.customer_phone, whatsapp_conversations.customer_phone),
                customer_name = coalesce(excluded.customer_name, whatsapp_conversations.customer_name),
                last_message_at = greatest(
                    coalesce(whatsapp_conversations.last_message_at, excluded.last_message_at),
                    excluded.last_message_at
                ),
                updated_at = excluded.updated_at
            """
        ),
        {
            "company_id": company_id,
            "conversation_whatsapp_id": zernio_conversation_id or customer_id,
            "zernio_conversation_id": zernio_conversation_id,
            "customer_id": customer_id,
            "customer_phone": customer_phone,
            "customer_name": customer_name,
            "message_time": message_time,
            "now": now,
        },
    )

    conversation_result = await session.execute(
        text(
            """
            select id
            from whatsapp_conversations
            where company_id = :company_id and customer_whatsapp_id = :customer_id
            limit 1
            """
        ),
        {"company_id": company_id, "customer_id": customer_id},
    )
    conversation_id = cast(uuid.UUID, conversation_result.scalar_one())

    sender_id = customer_id if direction == "inbound" else company_account_id
    recipient_id = company_account_id if direction == "inbound" else customer_id

    message_result = await session.execute(
        text(
            """
            insert into whatsapp_messages (
                conversation_id,
                company_id,
                whatsapp_mid,
                sender_whatsapp_id,
                recipient_whatsapp_id,
                direction,
                message_text,
                message_type,
                has_media,
                message_payload,
                sent_at,
                created_at,
                sender_type,
                manager_id,
                external_message_id
            ) values (
                :conversation_id,
                :company_id,
                :whatsapp_mid,
                :sender_id,
                :recipient_id,
                :direction,
                :message_text,
                :message_type,
                :has_media,
                cast(:message_payload as jsonb),
                :sent_at,
                :now,
                :sender_type,
                :manager_id,
                :external_message_id
            )
            on conflict (company_id, whatsapp_mid) where whatsapp_mid is not null
            do update set
                conversation_id = excluded.conversation_id,
                sender_whatsapp_id = excluded.sender_whatsapp_id,
                recipient_whatsapp_id = excluded.recipient_whatsapp_id,
                direction = excluded.direction,
                message_text = coalesce(excluded.message_text, whatsapp_messages.message_text),
                message_type = coalesce(excluded.message_type, whatsapp_messages.message_type),
                has_media = excluded.has_media,
                message_payload = coalesce(excluded.message_payload, whatsapp_messages.message_payload),
                sent_at = coalesce(excluded.sent_at, whatsapp_messages.sent_at),
                sender_type = coalesce(excluded.sender_type, whatsapp_messages.sender_type),
                manager_id = coalesce(excluded.manager_id, whatsapp_messages.manager_id),
                external_message_id = coalesce(excluded.external_message_id, whatsapp_messages.external_message_id)
            returning id
            """
        ),
        {
            "conversation_id": conversation_id,
            "company_id": company_id,
            "whatsapp_mid": whatsapp_mid,
            "external_message_id": whatsapp_mid,
            "sender_id": sender_id,
            "recipient_id": recipient_id,
            "direction": direction,
            "message_text": text_message,
            "message_type": _string_or_none(payload.get("message", {}).get("type") if isinstance(payload.get("message"), Mapping) else None) or "text",
            "has_media": bool(payload.get("message", {}).get("attachments") if isinstance(payload.get("message"), Mapping) else False),
            "message_payload": json.dumps(jsonable(payload), ensure_ascii=False),
            "sender_type": sender_type or ("customer" if direction == "inbound" else "bot"),
            "manager_id": manager_id,
            "sent_at": message_time,
            "now": now,
        },
    )
    message_id = cast(uuid.UUID | None, message_result.scalar_one_or_none())
    if message_id is not None:
        await increment_usage(session, company_id, usage_kind)
    return conversation_id, message_id


async def get_zernio_company_runtime(
    db: AsyncSession,
    *,
    company_id: uuid.UUID,
    platform: Literal["instagram", "whatsapp"],
) -> ZernioCompanyRuntime | None:
    enabled_column = "ig_activated" if platform == "instagram" else "wp_activated"
    result = await db.execute(
        text(
            f"""
            select
                c.id as company_id,
                coalesce(p.prompt_text, :default_prompt) as prompt_text,
                coalesce(u.{enabled_column}, false) as bot_enabled
            from instagram_companies c
            join users u on u.instagram_company_id = c.id and u.is_active = true
            left join instagram_system_prompts p on p.company_id = c.id
            where c.id = :company_id
            order by p.version desc nulls last, p.updated_at desc nulls last
            limit 1
            """
        ),
        {
            "company_id": company_id,
            "default_prompt": DEFAULT_SYSTEM_PROMPT_AZ,
        },
    )
    row = result.mappings().first()
    if not row:
        return None
    return ZernioCompanyRuntime(
        company_id=cast(uuid.UUID, row["company_id"]),
        prompt_text=str(row["prompt_text"]),
        bot_enabled=bool(row["bot_enabled"]),
    )


async def fetch_recent_zernio_whatsapp_history(
    session: AsyncSession,
    *,
    company_id: uuid.UUID,
    customer_id: str,
    limit: int = 10,
) -> list[dict[str, str]]:
    result = await session.execute(
        text(
            """
            select direction, message_text
            from whatsapp_messages m
            join whatsapp_conversations c on c.id = m.conversation_id
            where m.company_id = :company_id
              and c.customer_whatsapp_id = :customer_id
              and m.message_text is not null
            order by m.created_at desc
            limit :limit
            """
        ),
        {"company_id": company_id, "customer_id": customer_id, "limit": limit},
    )

    history: list[dict[str, str]] = []
    for row in reversed(result.mappings().all()):
        role = "user" if row["direction"] == "inbound" else "assistant"
        history.append({"role": role, "content": str(row["message_text"] or "")})
    return history


def _extract_zernio_sent_message_id(send_result: Mapping[str, Any]) -> str | None:
    # Use the provider/platform id whenever available. Zernio's generic `id` is
    # an internal record id, while outbound webhooks are deduplicated by
    # `platformMessageId` (Instagram/WhatsApp message id).
    for key in ("platformMessageId", "platform_message_id", "messageId", "message_id"):
        value = _string_or_none(send_result.get(key))
        if value:
            return value

    message = send_result.get("message")
    if isinstance(message, Mapping):
        nested = _extract_zernio_sent_message_id(message)
        if nested:
            return nested

    messages = send_result.get("messages")
    if isinstance(messages, Sequence) and not isinstance(messages, str | bytes | bytearray) and messages:
        first = messages[0]
        if isinstance(first, Mapping):
            nested = _extract_zernio_sent_message_id(first)
            if nested:
                return nested

    return _string_or_none(send_result.get("id"))


async def send_zernio_inbox_message(
    *,
    account_id: str,
    conversation_id: str,
    text_message: str,
) -> dict[str, Any]:
    from services.zernio_integrator import IntegratorZernio

    result = await IntegratorZernio().send_inbox_message(
        account_id=account_id,
        conversation_id=conversation_id,
        text_message=text_message,
    )
    payload = jsonable(result)
    return payload if isinstance(payload, dict) else {"value": payload}


async def build_zernio_ai_reply(
    db: AsyncSession,
    *,
    company_id: uuid.UUID,
    platform: Literal["instagram", "whatsapp"],
    customer_id: str,
    customer_name: str | None,
    customer_phone: str | None,
    conversation_id: uuid.UUID,
    source_message_id: str,
    text_message: str,
) -> str | None:
    runtime = await get_zernio_company_runtime(db, company_id=company_id, platform=platform)
    if not runtime:
        logger.warning("Zernio AI skipped: runtime not found company_id=%s platform=%s", company_id, platform)
        return None
    if not runtime["bot_enabled"]:
        logger.info("Zernio AI skipped: bot disabled company_id=%s platform=%s", company_id, platform)
        return None
    if not text_message.strip():
        logger.info("Zernio AI skipped: empty/non-text message company_id=%s platform=%s", company_id, platform)
        return None

    if platform == "instagram":
        history: list[dict[str, str]] = [
            {"role": str(item["role"]), "content": str(item["content"])}
            for item in await fetch_recent_chat_history(db, company_id=str(company_id), customer_id=customer_id)
        ]
    else:
        history = await fetch_recent_zernio_whatsapp_history(db, company_id=company_id, customer_id=customer_id)

    knowledge_entries = await find_relevant_knowledge_entries(db, company_id=company_id, query=text_message)
    knowledge_context = build_knowledge_context(knowledge_entries)
    order_intent = await detect_order_intent(
        user_text=text_message,
        history=history,
        knowledge_context=knowledge_context,
    )
    order_intent = hydrate_order_intent_customer_fields(
        order_intent,
        customer_name=customer_name,
        customer_phone=customer_phone,
    )
    intent, intent_confidence = classify_intent_from_order_intent(order_intent, text_message)
    await update_message_intent(
        db,
        channel=platform,
        company_id=company_id,
        external_message_id=source_message_id,
        intent=intent,
        confidence=intent_confidence,
    )

    if not await can_bot_reply(db, channel=platform, conversation_id=conversation_id):
        await notify_human_message(
            db,
            channel=platform,
            conversation_id=conversation_id,
            text_message=text_message,
            customer_label=customer_name or customer_phone or customer_id,
        )
        await db.commit()
        logger.info("Zernio AI skipped: conversation is not in BOT mode or 24h window is closed conversation_id=%s", conversation_id)
        return None

    if intent in HANDOFF_INTENTS and not order_intent.wants_order:
        await handoff_to_manager(
            db,
            channel=platform,
            conversation_id=conversation_id,
            intent=intent,
            confidence=intent_confidence,
            source_message_id=source_message_id,
            source_text=text_message,
            customer_label=customer_name or customer_phone or customer_id,
        )
        await db.commit()
        logger.info("Zernio conversation handed off to manager conversation_id=%s intent=%s", conversation_id, intent)
        return None

    if order_intent.wants_order and not order_intent.ready_to_submit and order_intent.next_question:
        return order_intent.next_question

    if order_intent.wants_order and order_intent.ready_to_submit:
        order = await create_customer_order(
            db=db,
            company_id=company_id,
            channel=platform,
            customer_id=customer_id,
            conversation_id=conversation_id,
            source_message_id=source_message_id,
            customer_name=order_intent.customer_name or customer_name,
            customer_phone=order_intent.customer_phone or customer_phone,
            product_title=order_intent.product_title,
            product_price=order_intent.product_price,
            quantity=order_intent.quantity,
            delivery_required=order_intent.delivery_required,
            delivery_address=order_intent.delivery_address,
            delivery_time=order_intent.delivery_time,
            customer_comment=order_intent.comment,
            raw_intent_payload=order_intent.model_dump(),
        )
        await notify_managers_about_order(db, order_id=order["id"])
        return build_order_confirmation_message(order_intent.detected_language)

    return generate_reply(
        system_prompt=runtime["prompt_text"],
        user_text=text_message,
        history=history,
        knowledge_context=knowledge_context,
        order_intent=order_intent,
    )


async def _instagram_message_exists(db: AsyncSession, *, company_id: uuid.UUID, message_id: str) -> bool:
    result = await db.execute(
        text(
            """
            select 1
            from instagram_messages
            where company_id = :company_id and instagram_mid = :message_id
            limit 1
            """
        ),
        {"company_id": company_id, "message_id": message_id},
    )
    return result.scalar_one_or_none() is not None


async def _whatsapp_message_exists(db: AsyncSession, *, company_id: uuid.UUID, message_id: str) -> bool:
    result = await db.execute(
        text(
            """
            select 1
            from whatsapp_messages
            where company_id = :company_id and whatsapp_mid = :message_id
            limit 1
            """
        ),
        {"company_id": company_id, "message_id": message_id},
    )
    return result.scalar_one_or_none() is not None


async def persist_parsed_zernio_message(
    db: AsyncSession,
    *,
    event_id: uuid.UUID,
    payload: Mapping[str, Any],
    parsed: ParsedZernioMessage,
) -> dict[str, Any]:
    if parsed["direction"] == "inbound" and not parsed["text"].strip() and (
        is_audio_message_type(parsed.get("message_type")) or parsed.get("has_media")
    ):
        audio_url = extract_audio_url(payload)
        if audio_url:
            transcript = await transcribe_audio_url(audio_url)
            if transcript:
                parsed = ParsedZernioMessage(**{**parsed, "text": transcript.strip()})
                if isinstance(payload, dict):
                    payload.setdefault("voice_transcription", transcript.strip())

    account = await resolve_zernio_account(
        db,
        platform=parsed["platform"],
        zernio_account_id=parsed["zernio_account_id"],
        zernio_profile_id=parsed["zernio_profile_id"],
    )
    if not account:
        logger.warning(
            "Zernio message skipped: account mapping not found platform=%s zernio_account_id=%s profile_id=%s",
            parsed["platform"],
            parsed["zernio_account_id"],
            parsed["zernio_profile_id"],
        )
        return {"handled": 0, "skipped": 1, "skip_reason": "account_mapping_not_found"}

    company_id = account["company_id"]
    platform_account_id = account["platform_account_id"] or parsed["zernio_account_id"]
    duplicate = False
    message_row_id: uuid.UUID | None = None

    if parsed["platform"] == "instagram":
        duplicate = await _instagram_message_exists(db, company_id=company_id, message_id=parsed["external_message_id"])
        conversation_id = await persist_message(
            db,
            company_id=str(company_id),
            customer_id=parsed["customer_id"],
            company_account_id=platform_account_id,
            direction=parsed["direction"],
            text_message=parsed["text"],
            instagram_mid=parsed["external_message_id"],
            payload=payload,
            username=parsed["customer_username"] or parsed["customer_name"],
            sent_at=parsed["sent_at"],
        )
        await db.execute(
            text(
                """
                update instagram_conversations
                set zernio_conversation_id = :zernio_conversation_id
                where id = :conversation_id
                """
            ),
            {"conversation_id": conversation_id, "zernio_conversation_id": parsed["zernio_conversation_id"]},
        )
    else:
        duplicate = await _whatsapp_message_exists(db, company_id=company_id, message_id=parsed["external_message_id"])
        conversation_id, message_row_id = await persist_zernio_whatsapp_message(
            db,
            company_id=company_id,
            customer_id=parsed["customer_id"],
            company_account_id=platform_account_id,
            direction=parsed["direction"],
            text_message=parsed["text"],
            whatsapp_mid=parsed["external_message_id"],
            payload=payload,
            customer_name=parsed["customer_name"] or parsed["customer_username"],
            customer_phone=parsed["customer_id"],
            sent_at=parsed["sent_at"],
            zernio_conversation_id=parsed["zernio_conversation_id"],
        )

    if parsed["direction"] == "inbound":
        await update_inbound_window(
            db,
            channel=parsed["platform"],
            conversation_id=cast(uuid.UUID, conversation_id),
        )

    await _mark_zernio_event_processed(db, event_id, True)
    await db.commit()

    result: dict[str, Any] = {
        "handled": 1,
        "skipped": 0,
        "channel": parsed["platform"],
        "company_id": str(company_id),
        "conversation_id": str(conversation_id),
        "message_row_id": str(message_row_id) if message_row_id else None,
        "message_id": parsed["external_message_id"],
        "ai_replied": False,
    }

    if duplicate:
        result["skip_reason"] = "duplicate_message"
        return result
    if parsed["direction"] != "inbound":
        result["skip_reason"] = "outbound_echo"
        return result

    reply = await build_zernio_ai_reply(
        db,
        company_id=company_id,
        platform=parsed["platform"],
        customer_id=parsed["customer_id"],
        customer_name=parsed["customer_name"] or parsed["customer_username"],
        customer_phone=parsed["customer_id"] if parsed["platform"] == "whatsapp" else None,
        conversation_id=cast(uuid.UUID, conversation_id),
        source_message_id=parsed["external_message_id"],
        text_message=parsed["text"],
    )
    if not reply:
        result["skip_reason"] = "ai_reply_not_generated"
        return result

    if not await can_bot_reply(db, channel=parsed["platform"], conversation_id=cast(uuid.UUID, conversation_id)):
        result["skip_reason"] = "conversation_mode_changed_before_send"
        await db.commit()
        return result

    send_result = await send_zernio_inbox_message(
        account_id=parsed["zernio_account_id"],
        conversation_id=parsed["zernio_conversation_id"],
        text_message=reply,
    )
    outbound_mid = _extract_zernio_sent_message_id(send_result) or f"zernio-outbound-{uuid.uuid4()}"

    if parsed["platform"] == "instagram":
        await persist_message(
            db,
            company_id=str(company_id),
            customer_id=parsed["customer_id"],
            company_account_id=platform_account_id,
            direction="outbound",
            text_message=reply,
            instagram_mid=outbound_mid,
            payload=send_result,
            username=parsed["customer_username"] or parsed["customer_name"],
        )
    else:
        await persist_zernio_whatsapp_message(
            db,
            company_id=company_id,
            customer_id=parsed["customer_id"],
            company_account_id=platform_account_id,
            direction="outbound",
            text_message=reply,
            whatsapp_mid=outbound_mid,
            payload=send_result,
            customer_name=parsed["customer_name"] or parsed["customer_username"],
            customer_phone=parsed["customer_id"],
            sent_at=None,
            zernio_conversation_id=parsed["zernio_conversation_id"],
        )
        await db.commit()

    await mark_outbound_activity(
        db,
        channel=parsed["platform"],
        conversation_id=cast(uuid.UUID, conversation_id),
        sender_type="bot",
    )
    await db.commit()

    result["ai_replied"] = True
    result["outbound_message_id"] = outbound_mid
    return result


DEFAULT_COMMENT_SYSTEM_PROMPT = DEFAULT_COMMENT_SYSTEM_PROMPT_AZ


async def get_comment_prompt(db: AsyncSession, *, company_id: uuid.UUID) -> dict[str, Any]:
    result = await db.execute(
        text(
            """
            select title, prompt_text, version
            from instagram_comment_prompts
            where company_id = :company_id and is_active = true
            order by created_at desc
            limit 1
            """
        ),
        {"company_id": company_id},
    )
    row = result.mappings().first()
    if row:
        return {"title": str(row["title"]), "prompt_text": str(row["prompt_text"]), "version": int(cast(Any, row["version"]))}
    return {"title": "Instagram comment prompt", "prompt_text": DEFAULT_COMMENT_SYSTEM_PROMPT, "version": 1}


async def build_zernio_comment_suggestion(
    db: AsyncSession,
    *,
    company_id: uuid.UUID,
    parsed: ParsedZernioComment,
) -> str | None:
    if not parsed["text"].strip():
        return None
    prompt = await get_comment_prompt(db, company_id=company_id)
    knowledge_entries = await find_relevant_knowledge_entries(db, company_id=company_id, query=parsed["text"])
    knowledge_context = build_knowledge_context(knowledge_entries)
    history = [
        {
            "role": "user",
            "content": f"Instagram comment from {parsed['author_username'] or parsed['author_name'] or parsed['author_id']}: {parsed['text']}",
        }
    ]
    return generate_reply(
        str(prompt["prompt_text"]),
        parsed["text"],
        history=history,
        knowledge_context=knowledge_context,
    )


async def is_auto_reply_enabled(db: AsyncSession, *, company_id: uuid.UUID) -> bool:
    result = await db.execute(
        text(
            """
            select coalesce(auto_reply_enabled, false)
            from company_automation_settings
            where company_id = :company_id
            limit 1
            """
        ),
        {"company_id": company_id},
    )
    value = result.scalar_one_or_none()
    return bool(value) if value is not None else False


async def is_instagram_comments_enabled(db: AsyncSession, *, company_id: uuid.UUID) -> bool:
    result = await db.execute(
        text(
            """
            select coalesce(instagram_comments_enabled, true)
            from company_automation_settings
            where company_id = :company_id
            limit 1
            """
        ),
        {"company_id": company_id},
    )
    value = result.scalar_one_or_none()
    return True if value is None else bool(value)


async def persist_parsed_zernio_comment(
    db: AsyncSession,
    *,
    event_id: uuid.UUID,
    payload: Mapping[str, Any],
    parsed: ParsedZernioComment,
) -> dict[str, Any]:
    account = await resolve_zernio_account(
        db,
        platform="instagram",
        zernio_account_id=parsed["zernio_account_id"],
        zernio_profile_id=parsed["zernio_profile_id"],
    )
    if not account:
        logger.warning(
            "Zernio comment skipped: account mapping not found zernio_account_id=%s profile_id=%s",
            parsed["zernio_account_id"],
            parsed["zernio_profile_id"],
        )
        return {"handled": 0, "skipped": 1, "skip_reason": "account_mapping_not_found"}

    company_id = account["company_id"]
    if not await is_instagram_comments_enabled(db, company_id=cast(uuid.UUID, company_id)):
        logger.info("Zernio comment skipped: instagram comments disabled company_id=%s", company_id)
        return {"handled": 0, "skipped": 1, "skip_reason": "instagram_comments_disabled"}

    created_at = parsed["created_at"] or datetime.now(timezone.utc)
    payload_json = json.dumps(jsonable(payload), ensure_ascii=False)

    thread_result = await db.execute(
        text(
            """
            insert into instagram_comment_threads (
                company_id, zernio_account_id, platform_post_id, zernio_post_id,
                comment_count, inbound_comment_count, last_comment_at, updated_at
            ) values (
                :company_id, :zernio_account_id, :platform_post_id, :zernio_post_id,
                1, 1, :created_at, now()
            )
            on conflict (company_id, platform_post_id) do update set
                zernio_account_id = excluded.zernio_account_id,
                zernio_post_id = coalesce(instagram_comment_threads.zernio_post_id, excluded.zernio_post_id),
                comment_count = instagram_comment_threads.comment_count + 1,
                inbound_comment_count = instagram_comment_threads.inbound_comment_count + 1,
                last_comment_at = greatest(coalesce(instagram_comment_threads.last_comment_at, excluded.last_comment_at), excluded.last_comment_at),
                updated_at = now()
            returning id
            """
        ),
        {
            "company_id": company_id,
            "zernio_account_id": parsed["zernio_account_id"],
            "platform_post_id": parsed["platform_post_id"],
            "zernio_post_id": parsed["zernio_post_id"],
            "created_at": created_at,
        },
    )
    thread_id = cast(uuid.UUID, thread_result.scalar_one())

    suggestion = await build_zernio_comment_suggestion(db, company_id=company_id, parsed=parsed)
    status = "suggested" if suggestion else "new"

    comment_result = await db.execute(
        text(
            """
            insert into instagram_comments (
                company_id, thread_id, zernio_event_id, zernio_account_id, zernio_profile_id,
                platform_comment_id, platform_post_id, zernio_post_id, parent_comment_id,
                author_id, author_username, author_name, author_picture, text_message,
                direction, is_reply, is_ad_comment, ad_id, ad_title, status,
                ai_suggested_reply, ai_generated_at, raw_payload, created_at, updated_at
            ) values (
                :company_id, :thread_id, :zernio_event_id, :zernio_account_id, :zernio_profile_id,
                :platform_comment_id, :platform_post_id, :zernio_post_id, :parent_comment_id,
                :author_id, :author_username, :author_name, :author_picture, :text_message,
                'inbound', :is_reply, :is_ad_comment, :ad_id, :ad_title, :status,
                :ai_suggested_reply, :ai_generated_at,
                cast(:raw_payload as jsonb), :created_at, now()
            )
            on conflict (company_id, platform_comment_id) do update set
                thread_id = excluded.thread_id,
                zernio_event_id = coalesce(instagram_comments.zernio_event_id, excluded.zernio_event_id),
                text_message = excluded.text_message,
                author_username = coalesce(excluded.author_username, instagram_comments.author_username),
                author_name = coalesce(excluded.author_name, instagram_comments.author_name),
                author_picture = coalesce(excluded.author_picture, instagram_comments.author_picture),
                raw_payload = excluded.raw_payload,
                updated_at = now()
            returning id, (xmax = 0) as inserted
            """
        ),
        {
            "company_id": company_id,
            "thread_id": thread_id,
            "zernio_event_id": event_id,
            "zernio_account_id": parsed["zernio_account_id"],
            "zernio_profile_id": parsed["zernio_profile_id"],
            "platform_comment_id": parsed["platform_comment_id"],
            "platform_post_id": parsed["platform_post_id"],
            "zernio_post_id": parsed["zernio_post_id"],
            "parent_comment_id": parsed["parent_comment_id"],
            "author_id": parsed["author_id"],
            "author_username": parsed["author_username"],
            "author_name": parsed["author_name"],
            "author_picture": parsed["author_picture"],
            "text_message": parsed["text"],
            "is_reply": parsed["is_reply"],
            "is_ad_comment": parsed["is_ad_comment"],
            "ad_id": parsed["ad_id"],
            "ad_title": parsed["ad_title"],
            "status": status,
            "ai_suggested_reply": suggestion,
            "ai_generated_at": datetime.now(timezone.utc) if suggestion else None,
            "raw_payload": payload_json,
            "created_at": created_at,
        },
    )
    comment_row = comment_result.mappings().one()
    await db.execute(
        text(
            """
            update instagram_comment_threads t
            set
                comment_count = stats.total_comments,
                inbound_comment_count = stats.inbound_comments,
                replied_comment_count = stats.replied_comments,
                converted_comment_count = stats.converted_comments,
                last_comment_at = stats.last_comment_at,
                updated_at = now()
            from (
                select
                    thread_id,
                    count(*)::int as total_comments,
                    count(*) filter (where direction = 'inbound')::int as inbound_comments,
                    count(*) filter (where status in ('replied', 'converted'))::int as replied_comments,
                    count(*) filter (where status = 'converted')::int as converted_comments,
                    max(created_at) as last_comment_at
                from instagram_comments
                where thread_id = :thread_id
                group by thread_id
            ) stats
            where t.id = stats.thread_id
            """
        ),
        {"thread_id": thread_id},
    )
    await _mark_zernio_event_processed(db, event_id, True)
    await db.commit()

    # ─── AUTO-REPLY: send AI suggestion as DM if enabled ───────────
    logger.info(
        "AUTO-REPLY CHECK: suggestion=%s inserted=%s company_id=%s",
        bool(suggestion), bool(comment_row.get("inserted")), company_id,
    )

    if suggestion and comment_row.get("inserted"):
        auto_reply_on = await is_auto_reply_enabled(db, company_id=company_id)
        logger.info("AUTO-REPLY: auto_reply_enabled=%s for company_id=%s", auto_reply_on, company_id)

        if auto_reply_on:
            zernio_account_id = parsed["zernio_account_id"]
            post_id = parsed["zernio_post_id"] or parsed["platform_post_id"]
            comment_id_str = parsed["platform_comment_id"]
            author = parsed["author_username"] or parsed["author_id"]

            logger.info(
                "AUTO-REPLY: sending DM author=%s account=%s post=%s comment=%s",
                author, zernio_account_id, post_id, comment_id_str,
            )
            logger.info("AUTO-REPLY: message text=%s", suggestion[:200])

            try:
                from services.zernio_integrator import IntegratorZernio

                zernio = IntegratorZernio()
                logger.info("AUTO-REPLY: Zernio client created, calling API...")

                reply_result = await zernio.send_private_reply_to_comment(
                    account_id=zernio_account_id,
                    post_id=post_id,
                    comment_id=comment_id_str,
                    message=suggestion,
                )

                logger.info("AUTO-REPLY: API response=%s", reply_result)

                # Mark as replied
                await db.execute(
                    text(
                        """
                        update instagram_comments
                        set status = 'replied',
                            replied_at = coalesce(replied_at, now()),
                            updated_at = now()
                        where id = :comment_id
                        """
                    ),
                    {"comment_id": comment_row["id"]},
                )
                await db.commit()

                logger.info(
                    "AUTO-REPLY: SUCCESS comment_id=%s author=%s",
                    comment_row["id"], author,
                )
            except Exception as exc:
                logger.error(
                    "AUTO-REPLY: FAILED comment_id=%s author=%s error=%s",
                    comment_row["id"], author, exc,
                    exc_info=True,
                )
        else:
            logger.info("AUTO-REPLY: disabled for company_id=%s, skipping", company_id)
    else:
        logger.info("AUTO-REPLY: no suggestion or not inserted, skipping")
    # ────────────────────────────────────────────────────────────────

    return {
        "handled": 1,
        "skipped": 0,
        "channel": "instagram_comments",
        "company_id": str(company_id),
        "thread_id": str(thread_id),
        "comment_id": str(comment_row["id"]),
        "message_id": parsed["platform_comment_id"],
        "ai_suggested": bool(suggestion),
        "auto_replied": bool(suggestion) and comment_row.get("inserted"),
        "skip_reason": None if bool(comment_row["inserted"]) else "duplicate_comment_updated",
    }


async def persist_zernio_webhook_event(
    db: AsyncSession,
    *,
    payload: Mapping[str, Any],
    headers: Mapping[str, str],
) -> dict[str, Any]:
    payload_json = jsonable(payload)
    if not isinstance(payload_json, dict):
        payload_json = {"value": payload_json}

    sanitized_headers = sanitize_headers(headers)
    zernio_account_id = extract_zernio_account_id(payload_json)
    zernio_profile_id = extract_zernio_profile_id(payload_json)
    platform = extract_platform(payload_json)
    event_type = extract_event_type(payload_json)
    parsed_message = parse_zernio_message_payload(payload_json)
    parsed_comment = parse_zernio_comment_payload(payload_json)

    company_id = await resolve_company_id_for_zernio_event(
        db,
        zernio_account_id=zernio_account_id,
        zernio_profile_id=zernio_profile_id,
        platform=platform,
    )

    event_id = uuid.uuid4()
    await db.execute(
        text(
            """
            insert into zernio_webhook_events (
                id,
                company_id,
                zernio_profile_id,
                zernio_account_id,
                platform,
                event_type,
                payload,
                headers,
                processed,
                received_at
            ) values (
                :id,
                :company_id,
                :zernio_profile_id,
                :zernio_account_id,
                :platform,
                :event_type,
                cast(:payload as jsonb),
                cast(:headers as jsonb),
                false,
                now()
            )
            """
        ),
        {
            "id": event_id,
            "company_id": company_id,
            "zernio_profile_id": zernio_profile_id,
            "zernio_account_id": zernio_account_id,
            "platform": platform,
            "event_type": event_type,
            "payload": json.dumps(payload_json, ensure_ascii=False),
            "headers": json.dumps(sanitized_headers, ensure_ascii=False),
        },
    )
    await db.commit()

    message_result: dict[str, Any] = {"handled": 0, "skipped": 1, "skip_reason": "not_a_supported_zernio_event"}
    if parsed_message:
        message_result = await persist_parsed_zernio_message(
            db,
            event_id=event_id,
            payload=payload_json,
            parsed=parsed_message,
        )
    elif parsed_comment:
        message_result = await persist_parsed_zernio_comment(
            db,
            event_id=event_id,
            payload=payload_json,
            parsed=parsed_comment,
        )

    logger.info(
        "Zernio webhook stored event_id=%s company_id=%s platform=%s event_type=%s account_id=%s profile_id=%s handled=%s skipped=%s",
        event_id,
        company_id,
        platform,
        event_type,
        zernio_account_id,
        zernio_profile_id,
        message_result.get("handled"),
        message_result.get("skipped"),
    )

    return {
        "event_id": str(event_id),
        "company_id": str(company_id) if company_id else message_result.get("company_id"),
        "platform": platform,
        "event_type": event_type,
        "zernio_account_id": zernio_account_id,
        "zernio_profile_id": zernio_profile_id,
        **message_result,
    }
