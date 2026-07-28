from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.models import (
    InstagramCompany,
    InstagramConversation,
    InstagramDataDeletionRequest,
    InstagramMessage,
    InstagramSystemPrompt,
    InstagramToken,
    InstagramWebhookEvent,
    User,
)


@dataclass(frozen=True)
class CompanyActivationStatus:
    wp_activated: bool
    wp_enabled: bool
    ig_enabled: bool
    ig_activated: bool


async def find_company_by_meta_user_id(db: AsyncSession, user_id: str) -> InstagramCompany | None:
    if not user_id:
        return None

    result = await db.execute(
        select(InstagramCompany).where(InstagramCompany.instagram_account_id == user_id).limit(1)
    )
    return result.scalar_one_or_none()


async def get_instagram_and_wp_statuses(db: AsyncSession, user_id: str) -> CompanyActivationStatus | None:
    if not user_id:
        return None

    user = await db.get(User, UUID(str(user_id)))
    if not user or not user.is_active:
        return None

    ig_has_active_token = False
    if user.instagram_company_id:
        token_result = await db.execute(
            select(InstagramToken.id)
            .where(
                InstagramToken.company_id == user.instagram_company_id,
                InstagramToken.is_active.is_(True),
            )
            .limit(1)
        )
        ig_has_active_token = token_result.scalar_one_or_none() is not None

    return CompanyActivationStatus(
        ig_enabled=bool(user.ig_activated),
        wp_enabled=bool(user.wp_activated),
        ig_activated=bool(ig_has_active_token),
        wp_activated=bool(user.wp_activated and user.whatsapp_company_id),
    )


async def handle_deauthorize(db: AsyncSession, user_id: str, payload: Mapping[str, object]) -> None:
    _ = payload
    company = await find_company_by_meta_user_id(db, user_id)
    if not company:
        await db.commit()
        return

    now = datetime.now(timezone.utc)
    await db.execute(
        update(User)
        .where(User.instagram_company_id == company.id)
        .values(instagram_company_id=None, ig_activated=False, updated_at=now)
    )
    await db.execute(delete(InstagramCompany).where(InstagramCompany.id == company.id))
    await db.commit()


async def handle_delete_data(
    db: AsyncSession,
    user_id: str,
    confirmation_code: UUID,
    payload: Mapping[str, object],
) -> None:
    company = await find_company_by_meta_user_id(db, user_id)

    db.add(
        InstagramDataDeletionRequest(
            confirmation_code=confirmation_code,
            company_id=company.id if company else None,
            request_payload=dict(payload),
            status="completed",
        )
    )

    if not company:
        await db.commit()
        return

    now = datetime.now(timezone.utc)
    await db.execute(delete(InstagramMessage).where(InstagramMessage.company_id == company.id))
    await db.execute(delete(InstagramWebhookEvent).where(InstagramWebhookEvent.company_id == company.id))
    await db.execute(delete(InstagramConversation).where(InstagramConversation.company_id == company.id))
    await db.execute(delete(InstagramSystemPrompt).where(InstagramSystemPrompt.company_id == company.id))
    await db.execute(delete(InstagramToken).where(InstagramToken.company_id == company.id))
    await db.execute(
        update(User)
        .where(User.instagram_company_id == company.id)
        .values(instagram_company_id=None, ig_activated=False, updated_at=now)
    )
    await db.execute(delete(InstagramCompany).where(InstagramCompany.id == company.id))
    await db.commit()


async def instagram_mid_exists(db: AsyncSession, *, instagram_mid: str) -> bool:
    result = await db.execute(select(InstagramMessage.id).where(InstagramMessage.instagram_mid == instagram_mid).limit(1))
    return result.scalar_one_or_none() is not None
