import uuid
from datetime import datetime, timezone
from typing import Any, Literal, Mapping, cast

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

PackageCode = Literal["basic", "full"]
UsageKind = Literal["text_message", "voice_message", "ai_video"]

PACKAGE_LIMITS: dict[str, dict[str, int | None | bool]] = {
    "basic": {
        "monthly_text_messages_limit": 4000,
        "monthly_voice_messages_limit": 1000,
        "monthly_ai_videos_limit": 0,
        "autoposting_enabled": False,
    },
    "full": {
        "monthly_text_messages_limit": None,
        "monthly_voice_messages_limit": None,
        "monthly_ai_videos_limit": 50,
        "autoposting_enabled": True,
    },
}


def normalize_package(value: str | None) -> PackageCode:
    package = (value or "basic").strip().lower()
    if package not in PACKAGE_LIMITS:
        raise ValueError("Unsupported package")
    return cast(PackageCode, package)


def current_period() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


async def ensure_company_subscription(db: AsyncSession, company_id: uuid.UUID | str, package_code: str = "basic") -> dict[str, Any]:
    package = normalize_package(package_code)
    limits = PACKAGE_LIMITS[package]
    result = await db.execute(
        text(
            """
            insert into company_subscriptions (
                company_id, package_code, monthly_text_messages_limit,
                monthly_voice_messages_limit, monthly_ai_videos_limit,
                autoposting_enabled, access_locked, created_at, updated_at
            ) values (
                :company_id, :package_code, :text_limit,
                :voice_limit, :ai_video_limit,
                :autoposting_enabled, false, now(), now()
            )
            on conflict (company_id) do update set
                updated_at = company_subscriptions.updated_at
            returning *
            """
        ),
        {
            "company_id": company_id,
            "package_code": package,
            "text_limit": limits["monthly_text_messages_limit"],
            "voice_limit": limits["monthly_voice_messages_limit"],
            "ai_video_limit": limits["monthly_ai_videos_limit"],
            "autoposting_enabled": limits["autoposting_enabled"],
        },
    )
    return dict(result.mappings().one())


async def get_company_subscription(db: AsyncSession, company_id: uuid.UUID | str) -> dict[str, Any]:
    result = await db.execute(
        text("select * from company_subscriptions where company_id = :company_id limit 1"),
        {"company_id": company_id},
    )
    row = result.mappings().first()
    if row:
        return dict(row)
    return await ensure_company_subscription(db, company_id)


async def update_company_subscription(
    db: AsyncSession,
    company_id: uuid.UUID,
    *,
    package_code: str,
    access_locked: bool,
    locked_reason: str | None = None,
) -> dict[str, Any]:
    package = normalize_package(package_code)
    limits = PACKAGE_LIMITS[package]
    result = await db.execute(
        text(
            """
            insert into company_subscriptions (
                company_id, package_code, monthly_text_messages_limit,
                monthly_voice_messages_limit, monthly_ai_videos_limit,
                autoposting_enabled, access_locked, locked_reason,
                locked_at, created_at, updated_at
            ) values (
                :company_id, :package_code, :text_limit,
                :voice_limit, :ai_video_limit,
                :autoposting_enabled, :access_locked, :locked_reason,
                case when :access_locked then now() else null end, now(), now()
            )
            on conflict (company_id) do update set
                package_code = excluded.package_code,
                monthly_text_messages_limit = excluded.monthly_text_messages_limit,
                monthly_voice_messages_limit = excluded.monthly_voice_messages_limit,
                monthly_ai_videos_limit = excluded.monthly_ai_videos_limit,
                autoposting_enabled = excluded.autoposting_enabled,
                access_locked = excluded.access_locked,
                locked_reason = excluded.locked_reason,
                locked_at = case when excluded.access_locked then coalesce(company_subscriptions.locked_at, now()) else null end,
                updated_at = now()
            returning *
            """
        ),
        {
            "company_id": company_id,
            "package_code": package,
            "text_limit": limits["monthly_text_messages_limit"],
            "voice_limit": limits["monthly_voice_messages_limit"],
            "ai_video_limit": limits["monthly_ai_videos_limit"],
            "autoposting_enabled": limits["autoposting_enabled"],
            "access_locked": access_locked,
            "locked_reason": locked_reason,
        },
    )
    await db.commit()
    return dict(result.mappings().one())


async def get_monthly_usage(db: AsyncSession, company_id: uuid.UUID | str, period: str | None = None) -> dict[str, int]:
    usage_period = period or current_period()
    result = await db.execute(
        text(
            """
            select
                coalesce(sum(text_messages_used), 0)::int as text_messages_used,
                coalesce(sum(voice_messages_used), 0)::int as voice_messages_used,
                coalesce(sum(ai_videos_used), 0)::int as ai_videos_used
            from company_usage_counters
            where company_id = :company_id and usage_period = :usage_period
            """
        ),
        {"company_id": company_id, "usage_period": usage_period},
    )
    row = result.mappings().one()
    return {"text_messages_used": int(row["text_messages_used"]), "voice_messages_used": int(row["voice_messages_used"]), "ai_videos_used": int(row["ai_videos_used"])}


def is_voice_payload(payload: Mapping[str, Any] | None, explicit_message_type: str | None = None) -> bool:
    message_type = (explicit_message_type or "").lower()
    if message_type in {"audio", "voice"}:
        return True
    if not payload:
        return False
    if payload.get("voice_transcription"):
        return True
    raw_type = str(payload.get("message_type") or payload.get("type") or "").lower()
    if raw_type in {"audio", "voice"}:
        return True
    message = payload.get("message")
    if isinstance(message, Mapping):
        nested_type = str(message.get("type") or message.get("message_type") or "").lower()
        if nested_type in {"audio", "voice"} or message.get("voice") or message.get("audio"):
            return True
    attachments = payload.get("attachments")
    if isinstance(attachments, list):
        return any(isinstance(item, Mapping) and str(item.get("type") or "").lower() in {"audio", "voice"} for item in attachments)
    return False


async def increment_usage(db: AsyncSession, company_id: uuid.UUID | str, kind: UsageKind, amount: int = 1) -> None:
    if amount <= 0:
        return
    period = current_period()
    column = {
        "text_message": "text_messages_used",
        "voice_message": "voice_messages_used",
        "ai_video": "ai_videos_used",
    }[kind]
    await db.execute(
        text(
            f"""
            insert into company_usage_counters (company_id, usage_period, {column}, created_at, updated_at)
            values (:company_id, :usage_period, :amount, now(), now())
            on conflict (company_id, usage_period) do update set
                {column} = company_usage_counters.{column} + excluded.{column},
                updated_at = now()
            """
        ),
        {"company_id": company_id, "usage_period": period, "amount": amount},
    )


async def check_access_not_locked(db: AsyncSession, company_id: uuid.UUID | str) -> dict[str, Any]:
    subscription = await get_company_subscription(db, company_id)
    if subscription.get("access_locked"):
        raise HTTPException(status_code=423, detail=subscription.get("locked_reason") or "Company access is locked by administrator")
    return subscription


async def check_usage_available(db: AsyncSession, company_id: uuid.UUID | str, kind: UsageKind) -> dict[str, Any]:
    subscription = await check_access_not_locked(db, company_id)
    usage = await get_monthly_usage(db, company_id)
    if kind == "text_message":
        limit = subscription.get("monthly_text_messages_limit")
        used = usage["text_messages_used"]
        label = "monthly text messages"
    elif kind == "voice_message":
        limit = subscription.get("monthly_voice_messages_limit")
        used = usage["voice_messages_used"]
        label = "monthly voice messages"
    else:
        limit = subscription.get("monthly_ai_videos_limit")
        used = usage["ai_videos_used"]
        label = "monthly AI videos"
    if limit is not None and used >= int(limit):
        raise HTTPException(status_code=402, detail=f"Package limit reached: {label} ({used}/{limit})")
    return subscription


async def consume_usage(db: AsyncSession, company_id: uuid.UUID | str, kind: UsageKind, amount: int = 1) -> None:
    for _ in range(amount):
        await check_usage_available(db, company_id, kind)
        await increment_usage(db, company_id, kind, 1)


async def require_autoposting(db: AsyncSession, company_id: uuid.UUID | str) -> dict[str, Any]:
    subscription = await check_access_not_locked(db, company_id)
    if not bool(subscription.get("autoposting_enabled")):
        raise HTTPException(status_code=403, detail="Autoposting is not available in the current package")
    return subscription


def subscription_response(subscription: Mapping[str, Any], usage: Mapping[str, int]) -> dict[str, Any]:
    return {
        "company_id": str(subscription["company_id"]),
        "package_code": str(subscription["package_code"]),
        "monthly_text_messages_limit": subscription.get("monthly_text_messages_limit"),
        "monthly_voice_messages_limit": subscription.get("monthly_voice_messages_limit"),
        "monthly_ai_videos_limit": subscription.get("monthly_ai_videos_limit"),
        "autoposting_enabled": bool(subscription.get("autoposting_enabled")),
        "access_locked": bool(subscription.get("access_locked")),
        "locked_reason": subscription.get("locked_reason"),
        "locked_at": subscription.get("locked_at"),
        "usage_period": current_period(),
        "text_messages_used": int(usage.get("text_messages_used", 0)),
        "voice_messages_used": int(usage.get("voice_messages_used", 0)),
        "ai_videos_used": int(usage.get("ai_videos_used", 0)),
        "created_at": subscription.get("created_at"),
        "updated_at": subscription.get("updated_at"),
    }


async def get_subscription_response(db: AsyncSession, company_id: uuid.UUID | str) -> dict[str, Any]:
    subscription = await get_company_subscription(db, company_id)
    usage = await get_monthly_usage(db, company_id)
    return subscription_response(subscription, usage)
