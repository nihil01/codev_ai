from __future__ import annotations

import json
import secrets
import uuid
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, cast

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config.app_config import settings

ConversationChannel = Literal["instagram", "whatsapp"]
ConversationMode = Literal["bot", "human", "paused", "closed"]
ConversationAction = Literal["take", "return_bot", "pause", "close"]

HANDOFF_INTENTS = {"ORDER", "BOOKING", "PRICE_REQUEST", "HOT_LEAD", "COMPLAINT", "PAYMENT_QUESTION"}

CONVERSATION_TABLES: dict[str, str] = {
    "instagram": "instagram_conversations",
    "whatsapp": "whatsapp_conversations",
    "whatsapp_cloud": "whatsapp_cloud_conversations",
}

MESSAGE_TABLES: dict[str, tuple[str, str]] = {
    "instagram": ("instagram_messages", "instagram_mid"),
    "whatsapp": ("whatsapp_messages", "whatsapp_mid"),
    "whatsapp_cloud": ("whatsapp_cloud_messages", "whatsapp_mid"),
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _table_for_channel(channel: str, *, cloud: bool = False) -> str:
    if channel == "instagram":
        return CONVERSATION_TABLES["instagram"]
    if channel == "whatsapp":
        return CONVERSATION_TABLES["whatsapp_cloud" if cloud else "whatsapp"]
    raise ValueError("Unsupported conversation channel")


def _message_table_for_channel(channel: str, *, cloud: bool = False) -> tuple[str, str]:
    if channel == "instagram":
        return MESSAGE_TABLES["instagram"]
    if channel == "whatsapp":
        return MESSAGE_TABLES["whatsapp_cloud" if cloud else "whatsapp"]
    raise ValueError("Unsupported message channel")


def classify_intent_from_order_intent(order_intent: Any, text_message: str) -> tuple[str, float]:
    text_value = text_message.lower()
    if getattr(order_intent, "wants_order", False):
        return "ORDER", float(getattr(order_intent, "confidence", 0.8) or 0.8)
    if any(word in text_value for word in ("price", "цена", "стоимость", "qiymət", "neçəyə", "сколько")):
        return "PRICE_REQUEST", 0.65
    if any(word in text_value for word in ("жалоба", "şikayət", "complaint", "недоволен", "problem", "problem var")):
        return "COMPLAINT", 0.75
    if any(word in text_value for word in ("бронь", "booking", "reserve", "rezerv", "бронировать")):
        return "BOOKING", 0.7
    return "GENERAL", 0.4


async def record_audit(
    db: AsyncSession,
    *,
    company_id: uuid.UUID,
    channel: str,
    conversation_id: uuid.UUID,
    actor_type: str,
    actor_id: uuid.UUID | None,
    action: str,
    old_mode: str | None,
    new_mode: str | None,
    details: Mapping[str, Any] | None = None,
) -> None:
    await db.execute(
        text(
            """
            insert into conversation_audit_log (
                company_id, channel, conversation_id, actor_type, actor_id, action,
                old_mode, new_mode, details, created_at
            ) values (
                :company_id, :channel, :conversation_id, :actor_type, :actor_id, :action,
                :old_mode, :new_mode, cast(:details as jsonb), now()
            )
            """
        ),
        {
            "company_id": company_id,
            "channel": channel,
            "conversation_id": conversation_id,
            "actor_type": actor_type,
            "actor_id": actor_id,
            "action": action,
            "old_mode": old_mode,
            "new_mode": new_mode,
            "details": json.dumps(dict(details or {}), ensure_ascii=False),
        },
    )


async def get_conversation_state(
    db: AsyncSession,
    *,
    channel: ConversationChannel,
    conversation_id: uuid.UUID,
    cloud: bool = False,
    lock: bool = False,
) -> Mapping[str, Any] | None:
    table_name = _table_for_channel(channel, cloud=cloud)
    suffix = " for update" if lock else ""
    result = await db.execute(
        text(
            f"""
            select id, company_id, mode, assigned_manager_id, bot_paused_at, bot_paused_reason,
                   last_user_message_at, messaging_window_expires_at,
                   last_manager_message_at, last_bot_message_at,
                   status, priority, version
            from {table_name}
            where id = :conversation_id
            limit 1
            {suffix}
            """
        ),
        {"conversation_id": conversation_id},
    )
    row = result.mappings().first()
    return cast(Mapping[str, Any] | None, row)


async def update_inbound_window(
    db: AsyncSession,
    *,
    channel: ConversationChannel,
    conversation_id: uuid.UUID,
    message_time: datetime | None = None,
    cloud: bool = False,
) -> Mapping[str, Any] | None:
    table_name = _table_for_channel(channel, cloud=cloud)
    now = message_time or utcnow()
    result = await db.execute(
        text(
            f"""
            update {table_name}
            set last_user_message_at = :now,
                messaging_window_expires_at = :expires_at,
                status = case when status = 'closed' then 'open' else status end,
                updated_at = :now,
                version = version + 1
            where id = :conversation_id
            returning id, company_id, mode, assigned_manager_id, messaging_window_expires_at, status, priority
            """
        ),
        {"conversation_id": conversation_id, "now": now, "expires_at": now + timedelta(hours=24)},
    )
    return cast(Mapping[str, Any] | None, result.mappings().first())


async def mark_outbound_activity(
    db: AsyncSession,
    *,
    channel: ConversationChannel,
    conversation_id: uuid.UUID,
    sender_type: Literal["bot", "manager"],
    manager_id: uuid.UUID | None = None,
    cloud: bool = False,
) -> None:
    table_name = _table_for_channel(channel, cloud=cloud)
    column = "last_manager_message_at" if sender_type == "manager" else "last_bot_message_at"
    await db.execute(
        text(
            f"""
            update {table_name}
            set {column} = now(),
                assigned_manager_id = coalesce(:manager_id, assigned_manager_id),
                updated_at = now(),
                version = version + 1
            where id = :conversation_id
            """
        ),
        {"conversation_id": conversation_id, "manager_id": manager_id},
    )


async def update_message_intent(
    db: AsyncSession,
    *,
    channel: ConversationChannel,
    company_id: uuid.UUID,
    external_message_id: str,
    intent: str,
    confidence: float,
    cloud: bool = False,
) -> None:
    table_name, mid_column = _message_table_for_channel(channel, cloud=cloud)
    await db.execute(
        text(
            f"""
            update {table_name}
            set intent = :intent,
                intent_confidence = :confidence,
                sender_type = case when direction = 'inbound' then 'customer' else coalesce(sender_type, 'bot') end,
                external_message_id = coalesce(external_message_id, {mid_column})
            where company_id = :company_id and {mid_column} = :external_message_id
            """
        ),
        {
            "company_id": company_id,
            "external_message_id": external_message_id,
            "intent": intent,
            "confidence": confidence,
        },
    )


async def can_bot_reply(
    db: AsyncSession,
    *,
    channel: ConversationChannel,
    conversation_id: uuid.UUID,
    cloud: bool = False,
) -> bool:
    state = await get_conversation_state(db, channel=channel, conversation_id=conversation_id, cloud=cloud)
    if not state:
        return False
    if str(state.get("mode") or "bot") != "bot":
        return False
    expires_at = state.get("messaging_window_expires_at")
    return isinstance(expires_at, datetime) and expires_at > utcnow()


async def choose_manager_user(db: AsyncSession, company_id: uuid.UUID) -> uuid.UUID | None:
    result = await db.execute(
        text(
            """
            select id
            from users
            where instagram_company_id = :company_id
              and role = 'company_user'
              and is_active = true
            order by telegram_notifications_enabled desc, updated_at desc nulls last, created_at asc
            limit 1
            """
        ),
        {"company_id": company_id},
    )
    return cast(uuid.UUID | None, result.scalar_one_or_none())


async def send_telegram_notification(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    company_id: uuid.UUID,
    channel: str | None,
    conversation_id: uuid.UUID | None,
    notification_type: str,
    message_text: str,
    crm_url: str | None = None,
) -> bool:
    if not user_id or not settings.telegram_bot_token:
        await _log_telegram_notification(db, user_id=user_id, company_id=company_id, channel=channel, conversation_id=conversation_id, notification_type=notification_type, message_text=message_text, status="failed", error_text="Telegram is not configured or user is missing")
        return False

    user_result = await db.execute(
        text("select telegram_chat_id, telegram_notifications_enabled from users where id = :user_id limit 1"),
        {"user_id": user_id},
    )
    user = user_result.mappings().first()
    chat_id = user.get("telegram_chat_id") if user else None
    if not user or not chat_id or not user.get("telegram_notifications_enabled"):
        await _log_telegram_notification(db, user_id=user_id, company_id=company_id, channel=channel, conversation_id=conversation_id, notification_type=notification_type, message_text=message_text, status="failed", error_text="Telegram is not connected")
        return False

    reply_markup = None
    if crm_url or conversation_id:
        buttons: list[list[dict[str, str]]] = []
        if crm_url:
            buttons.append([{"text": "Open chat in CRM", "url": crm_url}])
        if conversation_id and channel:
            buttons.append([
                {"text": "Take chat", "callback_data": f"take:{channel}:{conversation_id}"},
                {"text": "Snooze 10 min", "callback_data": f"snooze:{channel}:{conversation_id}:10"},
            ])
        reply_markup = {"inline_keyboard": buttons}

    payload: dict[str, Any] = {"chat_id": chat_id, "text": message_text}
    if reply_markup:
        payload["reply_markup"] = reply_markup

    status = "failed"
    telegram_message_id = None
    error_text = None
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage", json=payload)
            data = response.json()
            if not response.is_success or not data.get("ok"):
                raise RuntimeError(str(data))
            telegram_message_id = str(data.get("result", {}).get("message_id") or "") or None
            status = "sent"
    except Exception as exc:  # noqa: BLE001 - notification failure must not break CRM flow
        error_text = str(exc)[:1000]

    await _log_telegram_notification(db, user_id=user_id, company_id=company_id, channel=channel, conversation_id=conversation_id, notification_type=notification_type, message_text=message_text, status=status, error_text=error_text, telegram_message_id=telegram_message_id)
    return status == "sent"


async def _log_telegram_notification(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    company_id: uuid.UUID,
    channel: str | None,
    conversation_id: uuid.UUID | None,
    notification_type: str,
    message_text: str,
    status: str,
    error_text: str | None = None,
    telegram_message_id: str | None = None,
) -> None:
    await db.execute(
        text(
            """
            insert into telegram_notification_log (
                company_id, user_id, channel, conversation_id, notification_type,
                message_text, telegram_message_id, status, error_text, created_at, sent_at
            ) values (
                :company_id, :user_id, :channel, :conversation_id, :notification_type,
                :message_text, :telegram_message_id, :status, :error_text, now(), :sent_at
            )
            """
        ),
        {
            "company_id": company_id,
            "user_id": user_id,
            "channel": channel,
            "conversation_id": conversation_id,
            "notification_type": notification_type,
            "message_text": message_text,
            "telegram_message_id": telegram_message_id,
            "status": status,
            "sent_at": utcnow() if status == "sent" else None,
            "error_text": error_text,
        },
    )


def format_window_left(expires_at: Any) -> str:
    if not isinstance(expires_at, datetime):
        return "—"
    seconds = int((expires_at - utcnow()).total_seconds())
    if seconds <= 0:
        return "closed"
    hours, rem = divmod(seconds, 3600)
    minutes = rem // 60
    return f"{hours}h {minutes}m"


async def handoff_to_manager(
    db: AsyncSession,
    *,
    channel: ConversationChannel,
    conversation_id: uuid.UUID,
    intent: str,
    confidence: float,
    source_message_id: str,
    source_text: str,
    customer_label: str | None = None,
    cloud: bool = False,
) -> uuid.UUID | None:
    table_name = _table_for_channel(channel, cloud=cloud)
    state = await get_conversation_state(db, channel=channel, conversation_id=conversation_id, cloud=cloud, lock=True)
    if not state:
        return None
    company_id = cast(uuid.UUID, state["company_id"])
    old_mode = str(state.get("mode") or "bot")
    manager_id = await choose_manager_user(db, company_id)

    result = await db.execute(
        text(
            f"""
            update {table_name}
            set mode = 'human',
                assigned_manager_id = :manager_id,
                bot_paused_at = now(),
                bot_paused_reason = :reason,
                priority = 'high',
                status = 'pending',
                updated_at = now(),
                version = version + 1
            where id = :conversation_id
            returning messaging_window_expires_at
            """
        ),
        {"conversation_id": conversation_id, "manager_id": manager_id, "reason": f"intent:{intent}"},
    )
    updated = result.mappings().first() or {}
    await record_audit(
        db,
        company_id=company_id,
        channel=channel,
        conversation_id=conversation_id,
        actor_type="bot",
        actor_id=None,
        action="auto_handoff",
        old_mode=old_mode,
        new_mode="human",
        details={"intent": intent, "confidence": confidence, "source_message_id": source_message_id},
    )

    crm_url = f"{settings.app_base_url.rstrip('/')}/crm?conversation={conversation_id}"
    message_text = (
        "🔥 New lead\n\n"
        f"Customer: {customer_label or '—'}\n"
        f"Channel: {channel.title()}\n"
        f"Intent: {intent}\n"
        f"Message: “{source_text[:500]}”\n\n"
        f"Reply window left: {format_window_left(updated.get('messaging_window_expires_at'))}"
    )
    await send_telegram_notification(
        db,
        user_id=manager_id,
        company_id=company_id,
        channel=channel,
        conversation_id=conversation_id,
        notification_type=intent.lower(),
        message_text=message_text,
        crm_url=crm_url,
    )
    return manager_id


async def notify_human_message(
    db: AsyncSession,
    *,
    channel: ConversationChannel,
    conversation_id: uuid.UUID,
    text_message: str,
    customer_label: str | None = None,
    cloud: bool = False,
) -> None:
    state = await get_conversation_state(db, channel=channel, conversation_id=conversation_id, cloud=cloud)
    if not state:
        return
    company_id = cast(uuid.UUID, state["company_id"])
    manager_id = cast(uuid.UUID | None, state.get("assigned_manager_id")) or await choose_manager_user(db, company_id)
    crm_url = f"{settings.app_base_url.rstrip('/')}/crm?conversation={conversation_id}"
    message_text = (
        "💬 New message in manual chat\n\n"
        f"Customer: {customer_label or '—'}\n"
        f"Channel: {channel.title()}\n"
        f"Message: “{text_message[:500]}”\n\n"
        f"Reply window left: {format_window_left(state.get('messaging_window_expires_at'))}"
    )
    await send_telegram_notification(db, user_id=manager_id, company_id=company_id, channel=channel, conversation_id=conversation_id, notification_type="human_chat_message", message_text=message_text, crm_url=crm_url)


async def apply_conversation_action(
    db: AsyncSession,
    *,
    channel: ConversationChannel,
    conversation_id: uuid.UUID,
    actor_id: uuid.UUID,
    action: ConversationAction,
    cloud: bool = False,
) -> Mapping[str, Any]:
    table_name = _table_for_channel(channel, cloud=cloud)
    state = await get_conversation_state(db, channel=channel, conversation_id=conversation_id, cloud=cloud, lock=True)
    if not state:
        raise ValueError("Conversation not found")

    old_mode = str(state.get("mode") or "bot")
    company_id = cast(uuid.UUID, state["company_id"])
    now = utcnow()

    if action == "take":
        new_mode = "human"
        assigned_manager_id = actor_id
        status = "pending"
        priority = "high"
        paused_at = now
        reason = "manual_takeover"
    elif action == "return_bot":
        new_mode = "bot"
        assigned_manager_id = None
        status = "open"
        priority = str(state.get("priority") or "normal")
        paused_at = None
        reason = None
    elif action == "pause":
        new_mode = "paused"
        assigned_manager_id = cast(uuid.UUID | None, state.get("assigned_manager_id")) or actor_id
        status = "pending"
        priority = str(state.get("priority") or "normal")
        paused_at = now
        reason = "manual_pause"
    else:
        new_mode = "closed"
        assigned_manager_id = cast(uuid.UUID | None, state.get("assigned_manager_id"))
        status = "closed"
        priority = str(state.get("priority") or "normal")
        paused_at = now
        reason = "manual_close"

    result = await db.execute(
        text(
            f"""
            update {table_name}
            set mode = :mode,
                assigned_manager_id = :assigned_manager_id,
                bot_paused_at = :bot_paused_at,
                bot_paused_reason = :bot_paused_reason,
                status = :status,
                priority = :priority,
                updated_at = now(),
                version = version + 1
            where id = :conversation_id
            returning id, company_id, mode, assigned_manager_id, bot_paused_at, bot_paused_reason,
                      last_user_message_at, messaging_window_expires_at,
                      last_manager_message_at, last_bot_message_at, status, priority, created_at, updated_at
            """
        ),
        {
            "conversation_id": conversation_id,
            "mode": new_mode,
            "assigned_manager_id": assigned_manager_id,
            "bot_paused_at": paused_at,
            "bot_paused_reason": reason,
            "status": status,
            "priority": priority,
        },
    )
    row = cast(Mapping[str, Any], result.mappings().one())
    await record_audit(db, company_id=company_id, channel=channel, conversation_id=conversation_id, actor_type="manager", actor_id=actor_id, action=action, old_mode=old_mode, new_mode=new_mode)
    await db.commit()
    return row


async def create_telegram_connect_link(db: AsyncSession, *, user_id: uuid.UUID) -> str:
    if not settings.telegram_bot_username:
        raise ValueError("TELEGRAM_BOT_USERNAME is not configured")
    token = secrets.token_urlsafe(32)
    await db.execute(
        text(
            """
            insert into telegram_connect_tokens (user_id, token, expires_at, created_at)
            values (:user_id, :token, :expires_at, now())
            """
        ),
        {"user_id": user_id, "token": token, "expires_at": utcnow() + timedelta(minutes=15)},
    )
    await db.commit()
    return f"https://t.me/{settings.telegram_bot_username}?start=connect_{token}"


async def bind_telegram_token(
    db: AsyncSession,
    *,
    token: str,
    chat_id: int,
    telegram_user_id: int,
    username: str | None,
) -> bool:
    token_result = await db.execute(
        text(
            """
            select id, user_id
            from telegram_connect_tokens
            where token = :token and used_at is null and expires_at > now()
            limit 1
            for update
            """
        ),
        {"token": token},
    )
    row = token_result.mappings().first()
    if not row:
        await db.rollback()
        return False
    await db.execute(
        text(
            """
            update users
            set telegram_chat_id = :chat_id,
                telegram_user_id = :telegram_user_id,
                telegram_username = :username,
                telegram_notifications_enabled = true,
                updated_at = now()
            where id = :user_id
            """
        ),
        {"user_id": row["user_id"], "chat_id": chat_id, "telegram_user_id": telegram_user_id, "username": username},
    )
    await db.execute(text("update telegram_connect_tokens set used_at = now() where id = :id"), {"id": row["id"]})
    await db.commit()
    return True


async def disable_telegram_notifications(db: AsyncSession, *, user_id: uuid.UUID) -> None:
    await db.execute(
        text("update users set telegram_notifications_enabled = false, updated_at = now() where id = :user_id"),
        {"user_id": user_id},
    )
    await db.commit()
