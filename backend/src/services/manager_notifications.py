import secrets
import uuid
from collections.abc import Mapping
from datetime import timedelta
from typing import Any, Literal, cast

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config.app_config import settings
from services.conversation_control import utcnow

from services.customer_orders import mark_customer_order_sent_to_manager

ManagerChannel = Literal["instagram", "whatsapp", "telegram"]


def _normalize_channel(value: str) -> ManagerChannel:
    if value not in {"instagram", "whatsapp", "telegram"}:
        raise ValueError("Unsupported manager channel")
    raise ValueError("Use the Telegram manager connect link instead of manual manager creation")


def build_manager_order_message(order: Mapping[str, Any]) -> str:
    lines = [
        "🛒 New order",
        f"Channel: {order['channel']}",
        f"Customer ID: {order['customer_id']}",
    ]

    if order.get("customer_name"):
        lines.append(f"Customer name: {order['customer_name']}")
    if order.get("customer_phone"):
        lines.append(f"Phone: {order['customer_phone']}")
    if order.get("product_title"):
        lines.append(f"Product: {order['product_title']}")
    if order.get("product_price"):
        lines.append(f"Price: {order['product_price']}")
    if order.get("quantity"):
        lines.append(f"Quantity: {order['quantity']}")
    if order.get("delivery_required") is not None:
        lines.append(f"Delivery: {'yes' if order['delivery_required'] else 'no'}")
    if order.get("delivery_address"):
        lines.append(f"Address: {order['delivery_address']}")
    if order.get("delivery_time"):
        lines.append(f"Time: {order['delivery_time']}")
    if order.get("customer_comment"):
        lines.append(f"Comment: {order['customer_comment']}")

    return "\n".join(lines)


async def _send_telegram_order_message(*, chat_id: int, message_text: str) -> str | None:
    if not settings.telegram_bot_token:
        raise RuntimeError("Telegram bot token is not configured")

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": message_text},
        )
    data = response.json()
    if not response.is_success or not data.get("ok"):
        raise RuntimeError(str(data))
    return str(data.get("result", {}).get("message_id") or "") or None


async def list_company_managers(db: AsyncSession, company_id: uuid.UUID) -> list[Mapping[str, Any]]:
    result = await db.execute(
        text(
            """
            select
                id,
                company_id,
                'telegram'::text as channel,
                telegram_chat_id::text as recipient_id,
                display_name,
                is_active,
                telegram_user_id,
                telegram_chat_id,
                telegram_username,
                first_name,
                last_name,
                language_code,
                registered_at,
                last_seen_at,
                created_at,
                updated_at
            from telegram_company_managers
            where company_id = :company_id
            order by is_active desc, display_name asc, registered_at asc
            """
        ),
        {"company_id": company_id},
    )
    return [cast(Mapping[str, Any], row) for row in result.mappings().all()]


async def create_telegram_manager_connect_link(
    db: AsyncSession,
    *,
    company_id: uuid.UUID,
    created_by_user_id: uuid.UUID | None,
    ttl_minutes: int = 30,
) -> str:
    if not settings.telegram_bot_username:
        raise ValueError("Telegram bot username is not configured")

    token = secrets.token_urlsafe(24)
    expires_at = utcnow() + timedelta(minutes=ttl_minutes)
    await db.execute(
        text(
            """
            insert into telegram_manager_registration_tokens (
                company_id, created_by_user_id, token, expires_at, created_at
            ) values (
                :company_id, :created_by_user_id, :token, :expires_at, now()
            )
            """
        ),
        {
            "company_id": company_id,
            "created_by_user_id": created_by_user_id,
            "token": token,
            "expires_at": expires_at,
        },
    )
    await db.commit()
    username = settings.telegram_bot_username.strip().lstrip("@")
    return f"https://t.me/{username}?start=manager_{token}"


async def register_telegram_company_manager(
    db: AsyncSession,
    *,
    token: str,
    telegram_user_id: int,
    telegram_chat_id: int,
    telegram_username: str | None,
    first_name: str | None,
    last_name: str | None,
    language_code: str | None = None,
) -> Mapping[str, Any]:
    token_result = await db.execute(
        text(
            """
            select id, company_id
            from telegram_manager_registration_tokens
            where token = :token
              and used_at is null
              and expires_at > now()
            limit 1
            for update
            """
        ),
        {"token": token},
    )
    token_row = token_result.mappings().first()
    if not token_row:
        await db.rollback()
        raise ValueError("Registration link is expired or already used")

    display_parts = [part for part in [first_name, last_name] if part]
    display_name = " ".join(display_parts).strip() or (f"@{telegram_username}" if telegram_username else str(telegram_user_id))

    manager_id = uuid.uuid4()
    result = await db.execute(
        text(
            """
            insert into telegram_company_managers (
                id, company_id, telegram_user_id, telegram_chat_id, telegram_username,
                first_name, last_name, display_name, language_code,
                is_active, registered_at, last_seen_at, created_at, updated_at
            ) values (
                :id, :company_id, :telegram_user_id, :telegram_chat_id, :telegram_username,
                :first_name, :last_name, :display_name, :language_code,
                true, now(), now(), now(), now()
            )
            on conflict (company_id, telegram_user_id)
            do update set
                telegram_chat_id = excluded.telegram_chat_id,
                telegram_username = excluded.telegram_username,
                first_name = excluded.first_name,
                last_name = excluded.last_name,
                display_name = excluded.display_name,
                language_code = excluded.language_code,
                is_active = true,
                last_seen_at = now(),
                updated_at = now()
            returning
                id,
                company_id,
                'telegram'::text as channel,
                telegram_chat_id::text as recipient_id,
                display_name,
                is_active,
                telegram_user_id,
                telegram_chat_id,
                telegram_username,
                first_name,
                last_name,
                language_code,
                registered_at,
                last_seen_at,
                created_at,
                updated_at
            """
        ),
        {
            "id": manager_id,
            "company_id": token_row["company_id"],
            "telegram_user_id": telegram_user_id,
            "telegram_chat_id": telegram_chat_id,
            "telegram_username": telegram_username,
            "first_name": first_name,
            "last_name": last_name,
            "display_name": display_name,
            "language_code": language_code,
        },
    )
    await db.execute(
        text("update telegram_manager_registration_tokens set used_at = now() where id = :id"),
        {"id": token_row["id"]},
    )
    await db.commit()
    return cast(Mapping[str, Any], result.mappings().one())


async def upsert_company_manager(
    db: AsyncSession,
    *,
    company_id: uuid.UUID,
    channel: str,
    recipient_id: str,
    display_name: str,
    is_active: bool = True,
) -> Mapping[str, Any]:
    normalized_channel = _normalize_channel(channel)
    manager_id = uuid.uuid4()
    result = await db.execute(
        text(
            """
            insert into company_managers (
                id, company_id, channel, recipient_id, display_name, is_active, created_at, updated_at
            ) values (
                :id, :company_id, :channel, :recipient_id, :display_name, :is_active, now(), now()
            )
            on conflict (company_id, channel, recipient_id)
            do update set
                display_name = excluded.display_name,
                is_active = excluded.is_active,
                updated_at = now()
            returning id, company_id, channel, recipient_id, display_name, is_active, created_at, updated_at
            """
        ),
        {
            "id": manager_id,
            "company_id": company_id,
            "channel": normalized_channel,
            "recipient_id": recipient_id.strip(),
            "display_name": display_name.strip(),
            "is_active": is_active,
        },
    )
    await db.commit()
    return cast(Mapping[str, Any], result.mappings().one())


async def update_company_manager(
    db: AsyncSession,
    *,
    company_id: uuid.UUID,
    manager_id: uuid.UUID,
    recipient_id: str,
    display_name: str,
    is_active: bool,
) -> Mapping[str, Any]:
    result = await db.execute(
        text(
            """
            update telegram_company_managers
            set display_name = :display_name,
                is_active = :is_active,
                updated_at = now()
            where id = :manager_id and company_id = :company_id
            returning
                id,
                company_id,
                'telegram'::text as channel,
                telegram_chat_id::text as recipient_id,
                display_name,
                is_active,
                telegram_user_id,
                telegram_chat_id,
                telegram_username,
                first_name,
                last_name,
                language_code,
                registered_at,
                last_seen_at,
                created_at,
                updated_at
            """
        ),
        {
            "company_id": company_id,
            "manager_id": manager_id,
            "display_name": display_name.strip(),
            "is_active": is_active,
        },
    )
    row = result.mappings().first()
    if not row:
        await db.rollback()
        raise ValueError("Manager not found")
    await db.commit()
    return cast(Mapping[str, Any], row)


async def delete_company_manager(db: AsyncSession, *, company_id: uuid.UUID, manager_id: uuid.UUID) -> None:
    existing = await db.execute(
        text("select id from telegram_company_managers where id = :manager_id and company_id = :company_id"),
        {"manager_id": manager_id, "company_id": company_id},
    )
    if not existing.scalar_one_or_none():
        await db.rollback()
        raise ValueError("Manager not found")

    await db.execute(
        text("delete from telegram_company_managers where id = :manager_id and company_id = :company_id"),
        {"manager_id": manager_id, "company_id": company_id},
    )
    await db.commit()


async def notify_managers_about_order(db: AsyncSession, *, order_id: uuid.UUID) -> int:
    order_result = await db.execute(
        text(
            """
            select o.*, c.instagram_account_id, t.access_token
            from customer_orders o
            join instagram_companies c on c.id = o.company_id
            left join instagram_tokens t on t.company_id = c.id and t.is_active = true
            where o.id = :order_id
              and o.manager_notified_at is null
            order by t.updated_at desc nulls last
            limit 1
            """
        ),
        {"order_id": order_id},
    )
    order = order_result.mappings().first()
    if not order:
        return 0

    managers_result = await db.execute(
        text(
            """
            select
                id,
                'telegram'::text as channel,
                telegram_chat_id::text as recipient_id,
                telegram_chat_id,
                display_name
            from telegram_company_managers
            where company_id = :company_id and is_active = true
            order by display_name asc, registered_at asc
            """
        ),
        {"company_id": order["company_id"]},
    )
    managers = managers_result.mappings().all()
    if not managers:
        await db.commit()
        return 0

    order_mapping = cast(Mapping[str, Any], order)
    message_text = build_manager_order_message(order_mapping)
    sent_count = 0

    for manager in managers:
        notification_id = uuid.uuid4()
        status = "failed"
        external_message_id: str | None = None
        error_text: str | None = None

        try:
            external_message_id = await _send_telegram_order_message(
                chat_id=int(cast(Any, manager["telegram_chat_id"])),
                message_text=message_text,
            )
            status = "sent"
            sent_count += 1
        except Exception as exc:  # noqa: BLE001 - notification must not break customer flow
            error_text = str(exc)[:1000]

        await db.execute(
            text(
                """
                insert into order_manager_notifications (
                    id, order_id, manager_id, telegram_manager_id, company_id, channel, recipient_id, message_text,
                    status, external_message_id, error_text, created_at, sent_at
                ) values (
                    :id, :order_id, null, :telegram_manager_id, :company_id, 'telegram', :recipient_id, :message_text,
                    cast(:status as varchar), :external_message_id, :error_text, now(), :sent_at
                )
                """
            ),
            {
                "id": notification_id,
                "order_id": order_id,
                "telegram_manager_id": manager["id"],
                "company_id": order["company_id"],
                "recipient_id": manager["recipient_id"],
                "message_text": message_text,
                "status": status,
                "sent_at": utcnow() if status == "sent" else None,
                "external_message_id": external_message_id,
                "error_text": error_text,
            },
        )

    if sent_count > 0:
        await mark_customer_order_sent_to_manager(db, order_id=order_id)
    else:
        await db.commit()

    return sent_count
