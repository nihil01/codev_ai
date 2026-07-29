from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import PurePosixPath
from typing import Any, Literal, Mapping, cast

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from db.db import SessionLocal
from services.chat_runtime import persist_message
from services.conversation_control import can_bot_reply, mark_outbound_activity
from services.instagram_messaging import send_message as send_instagram_message
from services.whatsapp_cloud import persist_whatsapp_cloud_message, send_whatsapp_cloud_message
from services.zernio_integrator import IntegratorZernio, get_latest_zernio_tiktok_connected_account
from services.zernio_webhooks import _extract_zernio_sent_message_id, persist_zernio_whatsapp_message, send_zernio_inbox_message

logger = logging.getLogger(__name__)
BAKU_TIMEZONE = timezone(timedelta(hours=4))

DEFAULT_REMINDER_MESSAGE = (
    "Здравствуйте! Хотели мягко напомнить о нашем диалоге. "
    "Если вопрос ещё актуален — напишите, мы рядом и поможем."
)


def _money(value: str | None) -> Decimal | None:
    if value is None or not value.strip():
        return None
    try:
        amount = Decimal(value.strip().replace(",", "."))
    except InvalidOperation as exc:
        raise ValueError("Price must be a valid decimal number") from exc
    if amount < 0:
        raise ValueError("Price cannot be negative")
    return amount.quantize(Decimal("0.01"))


def _format_money(value: Any) -> str | None:
    if value is None:
        return None
    return str(Decimal(str(value)).quantize(Decimal("0.01")))


def automation_settings_row(row: Mapping[str, Any], *, tenant_id: uuid.UUID) -> dict[str, Any]:
    return {
        "tenant_id": str(tenant_id),
        "client_reminder_enabled": bool(row.get("client_reminder_enabled", False)),
        "client_reminder_delay_minutes": int(row.get("client_reminder_delay_minutes") or 120),
        "client_reminder_message": str(row.get("client_reminder_message") or DEFAULT_REMINDER_MESSAGE),
        "autoposting_enabled": bool(row.get("autoposting_enabled", False)),
        "instagram_comments_enabled": bool(row.get("instagram_comments_enabled", True)),
        "linkedin_connected": bool(row.get("linkedin_connected", False)),
        "tiktok_connected": bool(row.get("tiktok_connected", False)),
        "content_calendar_enabled": bool(row.get("content_calendar_enabled", False)),
        "flower_price_adaptation_enabled": bool(row.get("flower_price_adaptation_enabled", False)),
        "default_event_reminder_hours": int(row.get("default_event_reminder_hours") or 24),
    }


async def _linkedin_connection_is_valid(db: AsyncSession, tenant_id: uuid.UUID) -> bool:
    result = await db.execute(
        text(
            """
            select exists (
                select 1
                from social_posting_connections
                where company_id = :tenant_id
                  and platform = 'linkedin'
                  and status = 'connected'
                  and nullif(btrim(coalesce(external_account_id, '')), '') is not null
                  and nullif(btrim(coalesce(metadata->>'zernio_account_id', '')), '') is not null
            )
            """
        ),
        {"tenant_id": tenant_id},
    )
    return bool(result.scalar_one())


async def load_automation_settings(db: AsyncSession, tenant_id: uuid.UUID) -> dict[str, Any]:
    result = await db.execute(
        text(
            """
            select *
            from company_automation_settings
            where company_id = :tenant_id
            limit 1
            """
        ),
        {"tenant_id": tenant_id},
    )
    row = result.mappings().first()
    settings = dict(row) if row else {}
    settings["linkedin_connected"] = await _linkedin_connection_is_valid(db, tenant_id)
    return automation_settings_row(settings, tenant_id=tenant_id)


async def upsert_automation_settings(db: AsyncSession, tenant_id: uuid.UUID, payload: Mapping[str, Any]) -> dict[str, Any]:
    reminder_message = str(payload.get("client_reminder_message") or "").strip() or DEFAULT_REMINDER_MESSAGE
    result = await db.execute(
        text(
            """
            insert into company_automation_settings (
                company_id,
                client_reminder_enabled,
                client_reminder_delay_minutes,
                client_reminder_message,
                autoposting_enabled,
                instagram_comments_enabled,
                linkedin_connected,
                tiktok_connected,
                content_calendar_enabled,
                flower_price_adaptation_enabled,
                default_event_reminder_hours
            ) values (
                :company_id,
                :client_reminder_enabled,
                :client_reminder_delay_minutes,
                :client_reminder_message,
                :autoposting_enabled,
                :instagram_comments_enabled,
                :linkedin_connected,
                :tiktok_connected,
                :content_calendar_enabled,
                :flower_price_adaptation_enabled,
                :default_event_reminder_hours
            )
            on conflict (company_id) do update set
                client_reminder_enabled = excluded.client_reminder_enabled,
                client_reminder_delay_minutes = excluded.client_reminder_delay_minutes,
                client_reminder_message = excluded.client_reminder_message,
                autoposting_enabled = excluded.autoposting_enabled,
                instagram_comments_enabled = excluded.instagram_comments_enabled,
                tiktok_connected = excluded.tiktok_connected,
                content_calendar_enabled = excluded.content_calendar_enabled,
                flower_price_adaptation_enabled = excluded.flower_price_adaptation_enabled,
                default_event_reminder_hours = excluded.default_event_reminder_hours,
                updated_at = now()
            returning *
            """
        ),
        {
            "company_id": tenant_id,
            "client_reminder_enabled": bool(payload.get("client_reminder_enabled", False)),
            "client_reminder_delay_minutes": int(payload.get("client_reminder_delay_minutes") or 120),
            "client_reminder_message": reminder_message,
            "autoposting_enabled": bool(payload.get("autoposting_enabled", False)),
            "instagram_comments_enabled": bool(payload.get("instagram_comments_enabled", True)),
            "linkedin_connected": False,
            "tiktok_connected": bool(payload.get("tiktok_connected", False)),
            "content_calendar_enabled": bool(payload.get("content_calendar_enabled", False)),
            "flower_price_adaptation_enabled": bool(payload.get("flower_price_adaptation_enabled", False)),
            "default_event_reminder_hours": int(payload.get("default_event_reminder_hours") or 24),
        },
    )
    row = dict(result.mappings().one())
    await _sync_tiktok_connection_placeholder(db, tenant_id, bool(payload.get("tiktok_connected", False)))
    row["linkedin_connected"] = await _linkedin_connection_is_valid(db, tenant_id)
    await db.commit()
    return automation_settings_row(row, tenant_id=tenant_id)


async def _sync_tiktok_connection_placeholder(db: AsyncSession, tenant_id: uuid.UUID, enabled: bool) -> None:
    await db.execute(
        text(
            """
            insert into social_posting_connections (company_id, platform, status, connected_at)
            values (:company_id, 'tiktok', :status, case when :is_connected then now() else null end)
            on conflict (company_id, platform) do update set
                status = excluded.status,
                connected_at = case when :is_connected then coalesce(social_posting_connections.connected_at, now()) else null end,
                updated_at = now()
            """
        ),
        {
            "company_id": tenant_id,
            "status": "connected" if enabled else "planned",
            "is_connected": enabled,
        },
    )


def social_connection_row(row: Mapping[str, Any]) -> dict[str, Any]:
    platform = str(row["platform"])
    return {
        "id": str(row["id"]),
        "company_id": str(row["company_id"]),
        "platform": cast(Literal["instagram", "linkedin", "tiktok"], platform),
        "status": str(row["status"]),
        "external_account_id": str(row["external_account_id"]) if row.get("external_account_id") else None,
        "display_name": str(row["display_name"]) if row.get("display_name") else None,
        "connected_at": row.get("connected_at"),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


async def list_social_connections(db: AsyncSession, tenant_id: uuid.UUID) -> list[dict[str, Any]]:
    result = await db.execute(
        text(
            """
            select *
            from social_posting_connections
            where company_id = :company_id
            order by platform
            """
        ),
        {"company_id": tenant_id},
    )
    return [social_connection_row(dict(row)) for row in result.mappings().all()]


def _event_price_strategy(settings: Mapping[str, Any], event_at: datetime, base_price: Decimal | None) -> tuple[Decimal | None, dict[str, Any]]:
    if base_price is None:
        return None, {}
    enabled = bool(settings.get("flower_price_adaptation_enabled"))
    if not enabled:
        return base_price, {"enabled": False}

    now = datetime.now(timezone.utc)
    normalized_event_at = event_at if event_at.tzinfo else event_at.replace(tzinfo=timezone.utc)
    hours_until_event = max(0.0, (normalized_event_at - now).total_seconds() / 3600)
    if hours_until_event <= 6:
        multiplier = Decimal("1.30")
    elif hours_until_event <= 24:
        multiplier = Decimal("1.15")
    elif hours_until_event <= 72:
        multiplier = Decimal("1.05")
    else:
        multiplier = Decimal("1.00")
    adjusted = (base_price * multiplier).quantize(Decimal("0.01"))
    return adjusted, {"enabled": True, "hours_until_event": round(hours_until_event, 2), "multiplier": str(multiplier)}


def calendar_event_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "company_id": str(row["company_id"]),
        "title": str(row["title"]),
        "description": str(row["description"]) if row.get("description") else None,
        "event_type": str(row["event_type"]),
        "event_at": row["event_at"],
        "customer_id": str(row["customer_id"]) if row.get("customer_id") else None,
        "order_id": str(row["order_id"]) if row.get("order_id") else None,
        "flower_type": str(row["flower_type"]) if row.get("flower_type") else None,
        "base_price": _format_money(row.get("base_price")),
        "adjusted_price": _format_money(row.get("adjusted_price")),
        "price_strategy": row.get("price_strategy") or {},
        "reminder_sent_at": row.get("reminder_sent_at"),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


async def create_calendar_event(db: AsyncSession, tenant_id: uuid.UUID, payload: Mapping[str, Any]) -> dict[str, Any]:
    settings = await load_automation_settings(db, tenant_id)
    base_price = _money(cast(str | None, payload.get("base_price")))
    event_at = cast(datetime, payload["event_at"])
    adjusted_price, price_strategy = _event_price_strategy(settings, event_at, base_price)
    result = await db.execute(
        text(
            """
            insert into company_calendar_events (
                company_id, title, description, event_type, event_at, customer_id,
                order_id, flower_type, base_price, adjusted_price, price_strategy
            ) values (
                :company_id, :title, :description, :event_type, :event_at, :customer_id,
                :order_id, :flower_type, :base_price, :adjusted_price, cast(:price_strategy as jsonb)
            )
            returning *
            """
        ),
        {
            "company_id": tenant_id,
            "title": str(payload["title"]).strip(),
            "description": payload.get("description"),
            "event_type": payload.get("event_type") or "order",
            "event_at": event_at,
            "customer_id": payload.get("customer_id"),
            "order_id": payload.get("order_id"),
            "flower_type": payload.get("flower_type"),
            "base_price": base_price,
            "adjusted_price": adjusted_price,
            "price_strategy": json.dumps(price_strategy),
        },
    )
    row = result.mappings().one()
    await db.commit()
    return calendar_event_row(dict(row))


async def list_calendar_events(db: AsyncSession, tenant_id: uuid.UUID) -> list[dict[str, Any]]:
    result = await db.execute(
        text(
            """
            select *
            from company_calendar_events
            where company_id = :company_id
            order by event_at asc
            limit 100
            """
        ),
        {"company_id": tenant_id},
    )
    return [calendar_event_row(dict(row)) for row in result.mappings().all()]


def social_post_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "company_id": str(row["company_id"]),
        "platform": str(row["platform"]),
        "title": str(row["title"]) if row.get("title") else None,
        "caption": str(row["caption"]),
        "media_urls": row.get("media_urls") or [],
        "scheduled_for": row.get("scheduled_for"),
        "status": str(row["status"]),
        "zernio_post_id": str(row["zernio_post_id"]) if row.get("zernio_post_id") else None,
        "publish_result": row.get("publish_result") or {},
        "published_at": row.get("published_at"),
        "last_attempt_at": row.get("last_attempt_at"),
        "error_message": str(row["error_message"]) if row.get("error_message") else None,
        "metadata": row.get("metadata") or {},
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


async def list_social_post_drafts(db: AsyncSession, tenant_id: uuid.UUID) -> list[dict[str, Any]]:
    result = await db.execute(
        text(
            """
            select *
            from social_post_drafts
            where company_id = :company_id
            order by coalesce(scheduled_for, created_at) desc
            limit 100
            """
        ),
        {"company_id": tenant_id},
    )
    return [social_post_row(dict(row)) for row in result.mappings().all()]


def _scheduled_for_in_baku(value: Any) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, datetime):
        raise ValueError("scheduled_for must be a valid datetime")
    if value.tzinfo is None:
        return value.replace(tzinfo=BAKU_TIMEZONE)
    return value.astimezone(BAKU_TIMEZONE)


def _assert_future_schedule(value: Any) -> None:
    scheduled_for = _scheduled_for_in_baku(value)
    if scheduled_for and scheduled_for <= datetime.now(BAKU_TIMEZONE):
        raise ValueError("Schedule time must be in the future by Baku time (GMT+4)")


async def create_social_post_draft(db: AsyncSession, tenant_id: uuid.UUID, payload: Mapping[str, Any]) -> dict[str, Any]:
    platform = str(payload.get("platform") or "instagram").lower()
    if platform not in {"instagram", "linkedin", "tiktok"}:
        raise ValueError("Unsupported autoposting platform")
    caption = str(payload.get("caption") or "").strip()
    if not caption:
        raise ValueError("Caption is required")
    media_urls = payload.get("media_urls") or []
    if not isinstance(media_urls, list):
        raise ValueError("media_urls must be a list")
    scheduled_for = _scheduled_for_in_baku(payload.get("scheduled_for"))
    _assert_future_schedule(scheduled_for)
    requested_status = str(payload.get("status") or "").strip().lower()
    if requested_status and requested_status not in {"draft", "pending_review", "scheduled"}:
        raise ValueError("Unsupported post draft status")
    status = requested_status or ("scheduled" if scheduled_for else "draft")
    result = await db.execute(
        text(
            """
            insert into social_post_drafts (
                company_id, platform, title, caption, media_urls, scheduled_for, status, metadata
            ) values (
                :company_id, :platform, :title, :caption, cast(:media_urls as jsonb), :scheduled_for, :status, cast(:metadata as jsonb)
            )
            returning *
            """
        ),
        {
            "company_id": tenant_id,
            "platform": platform,
            "title": str(payload.get("title")).strip() if payload.get("title") else None,
            "caption": caption,
            "media_urls": json.dumps([str(url).strip() for url in media_urls if str(url).strip()], ensure_ascii=False),
            "scheduled_for": scheduled_for,
            "status": status,
            "metadata": json.dumps(payload.get("metadata") or {}, ensure_ascii=False),
        },
    )
    row = result.mappings().one()
    await db.commit()
    created = social_post_row(dict(row))
    if status == "scheduled" and scheduled_for and created["media_urls"]:
        try:
            return await publish_social_post_draft(db, tenant_id, uuid.UUID(str(created["id"])), publish_now=False)
        except Exception:
            logger.exception("Failed to create scheduled Zernio post draft_id=%s", created["id"])
            raise
    return created


def _extract_zernio_post_id(payload: Mapping[str, Any]) -> str | None:
    for key in ("id", "postId", "post_id", "_id"):
        value = payload.get(key)
        if value:
            return str(value)
    post = payload.get("post")
    if isinstance(post, Mapping):
        return _extract_zernio_post_id(post)
    return None


async def _account_for_social_post(db: AsyncSession, tenant_id: uuid.UUID, platform: str) -> Mapping[str, Any] | None:
    if platform == "instagram":
        result = await db.execute(
            text(
                """
                select zernio_account_id, coalesce(display_name, username, instagram_account_id, zernio_account_id) as display_name
                from zernio_instagram_connected_accounts
                where company_id = :company_id
                order by last_seen_at desc nulls last, created_at desc
                limit 1
                """
            ),
            {"company_id": tenant_id},
        )
        return result.mappings().first()
    if platform == "tiktok":
        return await get_latest_zernio_tiktok_connected_account(db, tenant_id)
    if platform == "linkedin":
        result = await db.execute(
            text(
                """
                select metadata->>'zernio_account_id' as zernio_account_id,
                       coalesce(display_name, external_account_id, metadata->>'zernio_account_id') as display_name
                from social_posting_connections
                where company_id = :company_id
                  and platform = 'linkedin'
                  and status = 'connected'
                  and btrim(coalesce(external_account_id, '')) <> ''
                  and btrim(coalesce(metadata->>'zernio_account_id', '')) <> ''
                limit 1
                """
            ),
            {"company_id": tenant_id},
        )
        return result.mappings().first()
    return None


def _zernio_platform_payload(platform: str, zernio_account_id: str) -> list[dict[str, str]]:
    return [{"platform": platform, "accountId": zernio_account_id}]


def _media_type_for_url(url: str) -> str:
    ext = PurePosixPath(url.split("?", 1)[0]).suffix.lower()
    if ext in {".mp4", ".mov", ".webm", ".m4v"}:
        return "video"
    return "image"


def _default_tiktok_settings() -> dict[str, Any]:
    return {
        "privacy_level": "PUBLIC_TO_EVERYONE",
        "allow_comment": True,
        "allow_duet": True,
        "allow_stitch": True,
        "content_preview_confirmed": True,
        "express_consent_given": True,
    }


async def publish_social_post_draft(db: AsyncSession, tenant_id: uuid.UUID, draft_id: uuid.UUID, *, publish_now: bool = True) -> dict[str, Any]:
    result = await db.execute(
        text("select * from social_post_drafts where id = :id and company_id = :company_id limit 1"),
        {"id": draft_id, "company_id": tenant_id},
    )
    row = result.mappings().first()
    if not row:
        raise ValueError("Post draft not found")
    if str(row["status"]) == "published":
        return social_post_row(dict(row))

    platform = str(row["platform"])
    account = await _account_for_social_post(db, tenant_id, platform)
    if not account:
        raise ValueError(f"No connected {platform} account for autoposting")

    zernio_account_id = str(account.get("zernio_account_id") or "").strip()
    if not zernio_account_id:
        raise ValueError(f"No connected {platform} account for autoposting")
    media_urls = row.get("media_urls") or []
    if platform == "tiktok" and not media_urls:
        raise ValueError("TikTok autoposting requires at least one public video/photo URL")

    media_items = [{"type": _media_type_for_url(str(url)), "url": str(url)} for url in media_urls]
    platforms = _zernio_platform_payload(platform, zernio_account_id)
    scheduled_for = row.get("scheduled_for") if not publish_now else None
    tiktok_settings = _default_tiktok_settings() if platform == "tiktok" else None

    await db.execute(
        text("update social_post_drafts set status = 'publishing', last_attempt_at = now(), error_message = null where id = :id"),
        {"id": draft_id},
    )
    await db.commit()

    try:
        publish_result = await IntegratorZernio().create_post(
            title=str(row["title"]) if row.get("title") else None,
            content=str(row["caption"]),
            platforms=platforms,
            media_items=media_items,
            scheduled_for=scheduled_for,
            publish_now=publish_now,
            is_draft=False,
            metadata={"crm_draft_id": str(draft_id), "company_id": str(tenant_id)},
            tiktok_settings=tiktok_settings,
        )
    except Exception as exc:
        await db.execute(
            text("update social_post_drafts set status = 'failed', error_message = :error, updated_at = now() where id = :id"),
            {"id": draft_id, "error": str(exc)[:2000]},
        )
        await db.commit()
        raise

    zernio_post_id = _extract_zernio_post_id(publish_result)
    if publish_now:
        updated = await db.execute(
            text(
                """
                update social_post_drafts
                set status = 'published',
                    zernio_post_id = :zernio_post_id,
                    publish_result = cast(:publish_result as jsonb),
                    published_at = now(),
                    updated_at = now()
                where id = :id
                returning *
                """
            ),
            {
                "id": draft_id,
                "zernio_post_id": zernio_post_id,
                "publish_result": json.dumps(publish_result, ensure_ascii=False),
            },
        )
    else:
        updated = await db.execute(
            text(
                """
                update social_post_drafts
                set status = 'scheduled',
                    zernio_post_id = :zernio_post_id,
                    publish_result = cast(:publish_result as jsonb),
                    updated_at = now()
                where id = :id
                returning *
                """
            ),
            {
                "id": draft_id,
                "zernio_post_id": zernio_post_id,
                "publish_result": json.dumps(publish_result, ensure_ascii=False),
            },
        )
    await db.commit()
    return social_post_row(dict(updated.mappings().one()))


async def delete_social_post_draft(db: AsyncSession, tenant_id: uuid.UUID, draft_id: uuid.UUID) -> dict[str, Any]:
    result = await db.execute(
        text("select * from social_post_drafts where id = :id and company_id = :company_id limit 1"),
        {"id": draft_id, "company_id": tenant_id},
    )
    row = result.mappings().first()
    if not row:
        raise ValueError("Post draft not found")

    post = social_post_row(dict(row))
    if post["status"] == "published" or post.get("published_at"):
        raise ValueError("Published posts cannot be deleted from CRM")

    zernio_delete_result: dict[str, Any] | None = None
    zernio_post_id = post.get("zernio_post_id")
    if zernio_post_id:
        zernio_delete_result = await IntegratorZernio().delete_post(str(zernio_post_id))

    await db.execute(
        text("delete from social_post_drafts where id = :id and company_id = :company_id"),
        {"id": draft_id, "company_id": tenant_id},
    )
    await db.commit()
    return {"deleted": True, "zernio_delete_result": zernio_delete_result, "post": post}


async def schedule_social_post_draft(db: AsyncSession, tenant_id: uuid.UUID, draft_id: uuid.UUID, scheduled_for: datetime) -> dict[str, Any]:
    scheduled_for_baku = _scheduled_for_in_baku(scheduled_for)
    _assert_future_schedule(scheduled_for_baku)
    result = await db.execute(
        text("select * from social_post_drafts where id = :id and company_id = :company_id limit 1"),
        {"id": draft_id, "company_id": tenant_id},
    )
    row = result.mappings().first()
    if not row:
        raise ValueError("Post draft not found")
    post = social_post_row(dict(row))
    if post["status"] in {"published", "rejected"} or post.get("published_at"):
        raise ValueError("Only unpublished post drafts can be scheduled")
    if post.get("zernio_post_id"):
        raise ValueError("Post is already scheduled in Zernio")

    await db.execute(
        text(
            """
            update social_post_drafts
            set status = 'scheduled', scheduled_for = :scheduled_for, error_message = null, updated_at = now()
            where id = :id and company_id = :company_id
            """
        ),
        {"id": draft_id, "company_id": tenant_id, "scheduled_for": scheduled_for_baku},
    )
    await db.commit()
    return await publish_social_post_draft(db, tenant_id, draft_id, publish_now=False)


async def reject_social_post_draft(db: AsyncSession, tenant_id: uuid.UUID, draft_id: uuid.UUID) -> dict[str, Any]:
    result = await db.execute(
        text(
            """
            update social_post_drafts
            set status = 'rejected', updated_at = now()
            where id = :id
              and company_id = :company_id
              and status <> 'published'
              and published_at is null
            returning *
            """
        ),
        {"id": draft_id, "company_id": tenant_id},
    )
    row = result.mappings().first()
    if not row:
        raise ValueError("Post draft not found or already published")
    await db.commit()
    return social_post_row(dict(row))


async def process_scheduled_social_posts_once(db: AsyncSession) -> int:
    rows = await db.execute(
        text(
            """
            select d.id, d.company_id
            from social_post_drafts d
            join company_automation_settings s on s.company_id = d.company_id
            where s.autoposting_enabled = true
              and d.status = 'scheduled'
              and d.zernio_post_id is null
              and d.scheduled_for is not null
              and d.scheduled_for <= now()
            order by d.scheduled_for asc
            limit 10
            """
        )
    )
    published = 0
    for row in rows.mappings().all():
        try:
            await publish_social_post_draft(db, cast(uuid.UUID, row["company_id"]), cast(uuid.UUID, row["id"]))
            published += 1
        except Exception:
            logger.exception("Scheduled social post publish failed draft_id=%s", row["id"])
    return published


async def autopost_worker(*, interval_seconds: int = 300, stop_event: asyncio.Event | None = None) -> None:
    logger.info("Autopost worker started interval_seconds=%s", interval_seconds)
    while stop_event is None or not stop_event.is_set():
        try:
            async with SessionLocal() as db:
                published = await process_scheduled_social_posts_once(db)
                if published:
                    logger.info("Autopost worker published %s posts", published)
        except Exception:
            logger.exception("Autopost worker failed")
        try:
            if stop_event is None:
                await asyncio.sleep(interval_seconds)
            else:
                await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            pass
    logger.info("Autopost worker stopped")




# ─── Contextual Reminder Generation ──────────────────────────────────

REMINDER_SYSTEM_PROMPT = """Ты — вежливый AI-ассистент компании. Твоя задача — написать короткое, дружелюбное напоминание клиенту, который перестал отвечать.

Правила:
1. Напоминание должно быть на том же языке, на котором клиент вел диалог
2. Будь мягким и ненавязчивым
3. Ссылайся на контекст предыдущего разговора
4. Не продавай активно — просто напомни о себе
5. Длина: 1-2 предложения, максимум 150 символов
6. Не используй шаблонные фразы типа "Здравствуйте, хотели напомнить"
7. Начни по-человечески, как будто продолжение разговора

Примеры хороших напоминаний:
- "Салам! Dəyərli müştərimiz, əgər sualınız varsa, biz hələ də buradayıq 💬"
- "Здравствуйте! Если остались вопросы по нашему разговору — пишите, поможем 😊"
- "Hello! Just checking in — if you need anything, we're here to help!"

Формат ответа: только текст напоминания, без кавычек и пояснений."""


async def generate_contextual_reminder(
    db: AsyncSession,
    *,
    company_id: uuid.UUID,
    customer_id: str,
    channel: str,
    default_message: str,
) -> str:
    """Generate a contextual reminder based on conversation history."""
    try:
        # Fetch recent conversation history
        history = await fetch_recent_chat_history(
            db,
            company_id=str(company_id),
            customer_id=customer_id,
            limit=8,
        )

        if not history:
            return default_message

        # Detect language from conversation
        last_messages = " ".join([msg["content"] for msg in history[-3:]])
        detected_lang = _detect_language(last_messages)

        # Build context for AI
        history_text = "\n".join([
            f"{'Клиент' if msg['role'] == 'user' else 'Бот'}: {msg['content']}"
            for msg in history[-6:]
        ])

        user_prompt = f"""Контекст диалога:
{history_text}

Язык клиента: {detected_lang}

Напиши короткое напоминание на языке клиента (1-2 предложения). Ссылайся на контекст разговора."""

        reminder = generate_reply(
            system_prompt=REMINDER_SYSTEM_PROMPT,
            user_text=user_prompt,
            history=[],
        )

        # Ensure reminder is not too long
        if len(reminder) > 200:
            reminder = reminder[:197] + "..."

        logger.info(
            "Generated contextual reminder company_id=%s channel=%s lang=%s",
            company_id, channel, detected_lang,
        )
        return reminder

    except Exception as exc:
        logger.error("Failed to generate contextual reminder: %s", exc)
        return default_message


def _detect_language(text: str) -> str:
    """Simple language detection based on character patterns."""
    text_lower = text.lower()

    # Azerbaijani indicators
    az_indicators = ["ə", "ö", "ü", "ç", "ş", "ğ", "ı", "salam", "siz", "biz", "bu"]
    az_score = sum(1 for w in az_indicators if w in text_lower)

    # Russian indicators
    ru_indicators = ["ы", "э", "ъ", "щ", "здравствуйте", "спасибо", "пожалуйста", "хорошо"]
    ru_score = sum(1 for w in ru_indicators if w in text_lower)

    # English indicators
    en_indicators = ["the", "is", "are", "was", "hello", "thank", "please", "how"]
    en_score = sum(1 for w in en_indicators if w in text_lower)

    scores = {"az": az_score, "ru": ru_score, "en": en_score}
    return max(scores, key=scores.get) if max(scores.values()) > 0 else "az"

async def process_client_reminders_once(db: AsyncSession) -> int:
    instagram_candidates = await db.execute(
        text(
            """
            select
                c.id as conversation_id,
                c.company_id,
                c.zernio_conversation_id,
                c.customer_instagram_id,
                c.customer_username,
                c.last_user_message_at,
                s.client_reminder_delay_minutes,
                s.client_reminder_message,
                a.zernio_account_id,
                coalesce(a.instagram_account_id, ic.instagram_account_id) as company_account_id,
                t.access_token
            from instagram_conversations c
            join company_automation_settings s on s.company_id = c.company_id
            join instagram_companies ic on ic.id = c.company_id
            left join zernio_instagram_connected_accounts a on a.company_id = c.company_id
            left join instagram_tokens t on t.company_id = c.company_id and t.is_active = true
            where s.client_reminder_enabled = true
              and c.mode = 'bot'
              and c.last_user_message_at is not null
              and c.last_user_message_at <= now() - make_interval(mins => s.client_reminder_delay_minutes)
              and (c.last_bot_message_at is null or c.last_bot_message_at < c.last_user_message_at)
              and (c.last_client_reminder_sent_at is null or c.last_client_reminder_sent_at < c.last_user_message_at)
            limit 25
            """
        )
    )
    sent = 0
    for row in instagram_candidates.mappings().all():
        if not await can_bot_reply(db, channel="instagram", conversation_id=cast(uuid.UUID, row["conversation_id"])):
            continue
        # Generate contextual reminder
        message = await generate_contextual_reminder(
            db,
            company_id=row["company_id"],
            customer_id=str(row["customer_instagram_id"]),
            channel="instagram",
            default_message=str(row["client_reminder_message"] or DEFAULT_REMINDER_MESSAGE),
        )
        instagram_send_payload: Mapping[str, Any]
        outbound_mid: str
        if row.get("zernio_account_id") and row.get("zernio_conversation_id"):
            instagram_send_payload = await send_zernio_inbox_message(
                account_id=str(row["zernio_account_id"]),
                conversation_id=str(row["zernio_conversation_id"]),
                text_message=message,
            )
            outbound_mid = _extract_zernio_sent_message_id(instagram_send_payload) or f"reminder-{uuid.uuid4()}"
        elif row.get("access_token") and row.get("company_account_id"):
            instagram_send_payload = await send_instagram_message(
                instagram_account_id=str(row["company_account_id"]),
                access_token=str(row["access_token"]),
                recipient_id=str(row["customer_instagram_id"]),
                text=message,
            )
            outbound_mid = str(instagram_send_payload.get("message_id") or f"reminder-{uuid.uuid4()}")
        else:
            logger.info("Skipping Instagram reminder without send provider conversation_id=%s", row["conversation_id"])
            continue
        await persist_message(
            db,
            company_id=str(row["company_id"]),
            customer_id=str(row["customer_instagram_id"]),
            company_account_id=str(row.get("company_account_id") or row.get("zernio_account_id") or "automation"),
            direction="outbound",
            text_message=message,
            instagram_mid=outbound_mid,
            payload={"automation": "client_reminder", "send_result": instagram_send_payload},
            username=str(row["customer_username"]) if row.get("customer_username") else None,
        )
        await mark_outbound_activity(db, channel="instagram", conversation_id=cast(uuid.UUID, row["conversation_id"]), sender_type="bot")
        await db.execute(text("update instagram_conversations set last_client_reminder_sent_at = now() where id = :id"), {"id": row["conversation_id"]})
        await db.commit()
        sent += 1

    whatsapp_candidates = await db.execute(
        text(
            """
            select
                c.id as conversation_id,
                c.company_id,
                c.integration_id,
                c.phone_number_id,
                c.waba_id,
                c.customer_whatsapp_id,
                c.customer_phone,
                c.customer_name,
                s.client_reminder_delay_minutes,
                s.client_reminder_message,
                i.access_token,
                a.zernio_account_id
            from whatsapp_cloud_conversations c
            join company_automation_settings s on s.company_id = c.company_id
            left join whatsapp_cloud_integrations i on i.id = c.integration_id and i.disconnected_at is null
            left join zernio_whatsapp_connected_accounts a on a.company_id = c.company_id
            where s.client_reminder_enabled = true
              and c.mode = 'bot'
              and c.last_user_message_at is not null
              and c.last_user_message_at <= now() - make_interval(mins => s.client_reminder_delay_minutes)
              and (c.last_bot_message_at is null or c.last_bot_message_at < c.last_user_message_at)
              and (c.last_client_reminder_sent_at is null or c.last_client_reminder_sent_at < c.last_user_message_at)
            limit 25
            """
        )
    )
    for row in whatsapp_candidates.mappings().all():
        if not await can_bot_reply(db, channel="whatsapp", conversation_id=cast(uuid.UUID, row["conversation_id"])):
            continue
        message = str(row["client_reminder_message"] or DEFAULT_REMINDER_MESSAGE)
        send_payload: Mapping[str, Any]
        if row.get("access_token"):
            send_payload = await send_whatsapp_cloud_message(
                phone_number_id=str(row["phone_number_id"]),
                access_token=str(row["access_token"]),
                recipient_id=str(row["customer_whatsapp_id"]),
                text_message=message,
            )
        elif row.get("zernio_account_id"):
            send_payload = await send_zernio_inbox_message(
                account_id=str(row["zernio_account_id"]),
                conversation_id=str(row["customer_whatsapp_id"]),
                text_message=message,
            )
        else:
            logger.info("Skipping WhatsApp reminder without send provider conversation_id=%s", row["conversation_id"])
            continue
        outbound_mid = _extract_zernio_sent_message_id(send_payload) or f"reminder-{uuid.uuid4()}"
        await persist_whatsapp_cloud_message(
            db,
            company_id=cast(uuid.UUID, row["company_id"]),
            integration_id=cast(uuid.UUID, row["integration_id"]),
            phone_number_id=str(row["phone_number_id"]),
            waba_id=str(row["waba_id"] or ""),
            customer_id=str(row["customer_whatsapp_id"]),
            customer_phone=str(row["customer_phone"]) if row.get("customer_phone") else None,
            customer_name=str(row["customer_name"]) if row.get("customer_name") else None,
            sender_id=str(row["phone_number_id"]),
            recipient_id=str(row["customer_whatsapp_id"]),
            direction="outbound",
            text_message=message,
            whatsapp_mid=outbound_mid,
            message_type="text",
            has_media=False,
            payload={"automation": "client_reminder", "send_result": dict(send_payload)},
            sent_at=None,
        )
        await mark_outbound_activity(db, channel="whatsapp", conversation_id=cast(uuid.UUID, row["conversation_id"]), sender_type="bot")
        await db.execute(text("update whatsapp_cloud_conversations set last_client_reminder_sent_at = now() where id = :id"), {"id": row["conversation_id"]})
        await db.commit()
        sent += 1

    zernio_whatsapp_candidates = await db.execute(
        text(
            """
            select
                c.id as conversation_id,
                c.company_id,
                c.zernio_conversation_id,
                c.customer_whatsapp_id,
                c.customer_phone,
                c.customer_name,
                s.client_reminder_message,
                a.zernio_account_id,
                coalesce(a.whatsapp_account_id, a.zernio_account_id) as company_account_id
            from whatsapp_conversations c
            join company_automation_settings s on s.company_id = c.company_id
            left join zernio_whatsapp_connected_accounts a on a.company_id = c.company_id
            where s.client_reminder_enabled = true
              and c.mode = 'bot'
              and c.zernio_conversation_id is not null
              and c.last_user_message_at is not null
              and c.last_user_message_at <= now() - make_interval(mins => s.client_reminder_delay_minutes)
              and (c.last_bot_message_at is null or c.last_bot_message_at < c.last_user_message_at)
              and (c.last_client_reminder_sent_at is null or c.last_client_reminder_sent_at < c.last_user_message_at)
            limit 25
            """
        )
    )
    for row in zernio_whatsapp_candidates.mappings().all():
        if not await can_bot_reply(db, channel="whatsapp", conversation_id=cast(uuid.UUID, row["conversation_id"])):
            continue
        if not row.get("zernio_account_id"):
            logger.info("Skipping Zernio WhatsApp reminder without account conversation_id=%s", row["conversation_id"])
            continue
        message = str(row["client_reminder_message"] or DEFAULT_REMINDER_MESSAGE)
        send_payload = await send_zernio_inbox_message(
            account_id=str(row["zernio_account_id"]),
            conversation_id=str(row["zernio_conversation_id"]),
            text_message=message,
        )
        outbound_mid = _extract_zernio_sent_message_id(send_payload) or f"reminder-{uuid.uuid4()}"
        await persist_zernio_whatsapp_message(
            db,
            company_id=cast(uuid.UUID, row["company_id"]),
            customer_id=str(row["customer_whatsapp_id"]),
            company_account_id=str(row.get("company_account_id") or row.get("zernio_account_id") or "automation"),
            direction="outbound",
            text_message=message,
            whatsapp_mid=outbound_mid,
            payload={"automation": "client_reminder", "send_result": send_payload},
            customer_name=str(row["customer_name"]) if row.get("customer_name") else None,
            customer_phone=str(row["customer_phone"]) if row.get("customer_phone") else None,
            sent_at=None,
            sender_type="bot",
            zernio_conversation_id=str(row["zernio_conversation_id"]),
        )
        await mark_outbound_activity(db, channel="whatsapp", conversation_id=cast(uuid.UUID, row["conversation_id"]), sender_type="bot")
        await db.execute(text("update whatsapp_conversations set last_client_reminder_sent_at = now() where id = :id"), {"id": row["conversation_id"]})
        await db.commit()
        sent += 1
    return sent


async def reminder_worker(*, interval_seconds: int = 300, stop_event: asyncio.Event | None = None) -> None:
    logger.info("Client reminder worker started interval_seconds=%s", interval_seconds)
    while stop_event is None or not stop_event.is_set():
        try:
            async with SessionLocal() as db:
                sent = await process_client_reminders_once(db)
                if sent:
                    logger.info("Client reminder worker sent %s reminders", sent)
        except Exception:
            logger.exception("Client reminder worker failed")
        try:
            if stop_event is None:
                await asyncio.sleep(interval_seconds)
            else:
                await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            pass
    logger.info("Client reminder worker stopped")
