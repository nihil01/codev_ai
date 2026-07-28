import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.models import InstagramCompany, InstagramToken, User

logger = logging.getLogger(__name__)


async def check_profile_exists(db: AsyncSession, company_profile_name: str) -> bool:
    result = await db.execute(
        select(InstagramCompany.id).where(InstagramCompany.instagram_username == company_profile_name).limit(1)
    )
    return result.scalar_one_or_none() is not None


async def upsert_company(
    db: AsyncSession,
    instagram_account_id: str,
    username: str | None,
    name: str | None,
    token: str,
    expires_in: int,
    user_id: uuid.UUID | None = None,
    account_type: str | None = None,
    profile_picture_url: str | None = None,
) -> uuid.UUID:
    now = datetime.now(timezone.utc)
    display_name = name or username or instagram_account_id

    user: User | None = None
    if user_id:
        user = await db.get(User, user_id)
        if not user or not user.is_active:
            raise HTTPException(status_code=404, detail="CRM user not found")

        conflict = await db.execute(
            select(User.id)
            .join(InstagramCompany, User.instagram_company_id == InstagramCompany.id)
            .where(InstagramCompany.instagram_account_id == instagram_account_id, User.id != user_id)
            .limit(1)
        )
        if conflict.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Instagram account is already linked to another user")

    company: InstagramCompany | None = None

    # Company users can configure WhatsApp before Instagram OAuth. In that case
    # they already own a placeholder tenant row. OAuth must upgrade that same
    # row instead of creating a new company, otherwise WhatsApp/KB/managers stay
    # attached to the old tenant and the frontend loses company_id.
    if user and user.instagram_company_id:
        company = await db.get(InstagramCompany, user.instagram_company_id)

    if company is None:
        result = await db.execute(
            select(InstagramCompany).where(InstagramCompany.instagram_account_id == instagram_account_id).limit(1)
        )
        company = result.scalar_one_or_none()

    if company is None:
        company = InstagramCompany(
            id=uuid.uuid4(),
            instagram_account_id=instagram_account_id,
            instagram_username=username,
            display_name=display_name,
            instagram_account_type=account_type,
            instagram_profile_picture_url=profile_picture_url,
            created_at=now,
            updated_at=now,
        )
        db.add(company)
        await db.flush()
    else:
        company.instagram_username = username
        company.display_name = display_name
        company.instagram_account_type = account_type
        company.instagram_profile_picture_url = profile_picture_url
        company.updated_at = now

    if user:
        user.instagram_company_id = company.id
        user.ig_activated = True
        user.updated_at = now

    await db.execute(
        update(InstagramToken)
        .where(InstagramToken.company_id == company.id, InstagramToken.is_active.is_(True))
        .values(is_active=False, updated_at=now)
    )

    db.add(
        InstagramToken(
            id=uuid.uuid4(),
            company_id=company.id,
            access_token=token,
            issued_at=now,
            expires_at=now + timedelta(seconds=expires_in),
            refresh_after=now + timedelta(seconds=max(expires_in - 86400, 0)),
            is_active=True,
            created_at=now,
            updated_at=now,
        )
    )

    await db.commit()
    logger.info(
        "Instagram OAuth linked user_id=%s company_id=%s instagram_account_id=%s username=%s",
        user_id,
        company.id,
        instagram_account_id,
        username,
    )
    return company.id


async def ensure_user_company(
    db: AsyncSession,
    user: User,
    display_name: str | None = None,
) -> uuid.UUID:
    if user.instagram_company_id:
        return user.instagram_company_id

    placeholder_account_id = f"crm_user_{user.id.hex}"

    result = await db.execute(
        select(InstagramCompany).where(
            InstagramCompany.instagram_account_id == placeholder_account_id
        )
    )
    existing_company = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)

    if existing_company:
        user.instagram_company_id = existing_company.id
        user.updated_at = now
        await db.commit()
        await db.refresh(user)
        return existing_company.id

    company = InstagramCompany(
        id=uuid.uuid4(),
        instagram_account_id=placeholder_account_id,
        instagram_username=None,
        display_name=display_name or user.email,
        instagram_account_type=None,
        instagram_profile_picture_url=None,
        created_at=now,
        updated_at=now,
    )

    db.add(company)
    await db.flush()

    user.instagram_company_id = company.id
    user.updated_at = now

    await db.commit()
    await db.refresh(user)

    return company.id

async def set_instagram_bot_enabled(db: AsyncSession, company_id: uuid.UUID, enabled: bool) -> None:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        update(User)
        .where(User.instagram_company_id == company_id)
        .values(ig_activated=enabled, updated_at=now)
        .returning(User.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Client user for company not found")
    await db.commit()


async def set_wp_bot_enabled(db: AsyncSession, company_id: uuid.UUID, enabled: bool) -> None:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        update(User)
        .where(User.instagram_company_id == company_id)
        .values(wp_activated=enabled, updated_at=now)
        .returning(User.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Client user for company not found")
    await db.commit()


async def deauthorize_instagram_company(db: AsyncSession, company_id: uuid.UUID) -> None:
    company = await db.get(InstagramCompany, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Client company not found")

    now = datetime.now(timezone.utc)
    await db.execute(
        update(User)
        .where(User.instagram_company_id == company_id)
        .values(instagram_company_id=None, ig_activated=False, updated_at=now)
    )
    await db.execute(delete(InstagramCompany).where(InstagramCompany.id == company_id))
    await db.commit()
    logger.info("Instagram deauthorized and company deleted for company_id=%s", company_id)
