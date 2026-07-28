import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Literal, cast

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from config.app_config import settings
from config.deps import get_db
from models.models import User
from services.auth import create_jwt_token, decode_jwt_token, hash_password, verify_password
from services.business_features import feature_set_for, normalize_business_type
from services.company import ensure_user_company
from services.instagram_data import get_instagram_and_wp_statuses
from services.subscriptions import check_access_not_locked, ensure_company_subscription
from services.zernio_integrator import IntegratorZernio, upsert_zernio_company_profile

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger(__name__)

UserRole = Literal["admin", "company_user"]


class LoginRequest(BaseModel):
    email: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=255)


class LoginResponse(BaseModel):
    user_id: str
    email: str
    role: UserRole
    company_id: str | None
    token: str


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=255)
    new_password: str = Field(min_length=8, max_length=255)


class ChangePasswordResponse(BaseModel):
    ok: bool = True


class CreateCompanyUserRequest(BaseModel):
    email: str = Field(min_length=1, max_length=255)
    instagram_account_name: str = Field(min_length=1, max_length=255)
    temporary_password: str = Field(min_length=1, max_length=255)
    business_type: Literal["confectionery", "flower_shop", "cafe_restaurant", "other"] = "other"
    package_code: Literal["basic", "full"] = "basic"


class CreateCompanyUserResponse(BaseModel):
    user_id: str
    email: str
    company_id: str | None
    company_name: str
    business_type: str
    business_type_label: str
    temporary_password: str


class UserClaims(BaseModel):
    user_id: str
    email: str
    role: UserRole
    company_id: str | None = None


class CurrentUserResponse(UserClaims):
    ig_activated: bool = False
    wp_activated: bool = False
    ig_enabled: bool = False
    wp_enabled: bool = False


async def _load_active_user(db: AsyncSession, user_id: str | uuid.UUID) -> User:
    result = await db.execute(select(User).where(User.id == user_id, User.is_active.is_(True)).limit(1))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User no longer exists or is inactive")
    return user


async def get_current_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> UserClaims:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")

    payload = decode_jwt_token(authorization[7:], settings.JWT_SECRET)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    try:
        claims = UserClaims.model_validate(payload)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid token claims") from exc

    db_user = await _load_active_user(db, claims.user_id)
    if db_user.role not in {"admin", "company_user"}:
        raise HTTPException(status_code=403, detail="Unsupported user role")
    if db_user.role == "company_user" and db_user.instagram_company_id:
        await check_access_not_locked(db, db_user.instagram_company_id)

    return UserClaims(
        user_id=str(db_user.id),
        email=db_user.email,
        role=cast(UserRole, db_user.role),
        company_id=str(db_user.instagram_company_id) if db_user.instagram_company_id else None,
    )


async def get_admin_user(user: UserClaims = Depends(get_current_user)) -> UserClaims:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)) -> LoginResponse:
    result = await db.execute(select(User).where(User.email == request.email, User.is_active.is_(True)).limit(1))
    user = result.scalar_one_or_none()

    if not user or not verify_password(request.password, user.password_hash):
        logger.warning("Failed login attempt for email=%s", request.email)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if user.role not in {"admin", "company_user"}:
        raise HTTPException(status_code=403, detail="Unsupported user role")
    user_role = cast(UserRole, user.role)

    if user_role == "company_user":
        await ensure_user_company(db, user)
        if user.instagram_company_id:
            await check_access_not_locked(db, user.instagram_company_id)

    company_id = str(user.instagram_company_id) if user.instagram_company_id else None
    token = create_jwt_token(
        user_id=str(user.id),
        email=user.email,
        role=user_role,
        company_id=company_id,
        secret=settings.JWT_SECRET,
    )

    logger.info("User logged in: email=%s, role=%s", user.email, user.role)
    return LoginResponse(user_id=str(user.id), email=user.email, role=user_role, company_id=company_id, token=token)


@router.post("/change-password", response_model=ChangePasswordResponse)
async def change_password(
    request: ChangePasswordRequest,
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChangePasswordResponse:
    user = await _load_active_user(db, current_user.user_id)

    if not verify_password(request.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    if verify_password(request.new_password, user.password_hash):
        raise HTTPException(status_code=400, detail="New password must be different from current password")

    user.password_hash = hash_password(request.new_password)
    user.updated_at = datetime.now(timezone.utc)
    await db.commit()

    logger.info("User changed password: user_id=%s role=%s", user.id, user.role)
    return ChangePasswordResponse()


@router.post("/users", response_model=CreateCompanyUserResponse)
async def create_company_user(
    request: CreateCompanyUserRequest,
    db: AsyncSession = Depends(get_db),
    admin: UserClaims = Depends(get_admin_user),
) -> CreateCompanyUserResponse:
    _ = admin
    result = await db.execute(select(User.id).where(User.email == request.email).limit(1))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="User with this email already exists")

    now = datetime.now(timezone.utc)
    company_uuid = uuid.uuid4()
    user = User(
        id=company_uuid,
        email=request.email,
        password_hash=hash_password(request.temporary_password),
        role="company_user",
        instagram_company_id=None,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    await db.flush()
    company_id = await ensure_user_company(db, user, request.instagram_account_name)
    await ensure_company_subscription(db, company_id, request.package_code)
    business_type = normalize_business_type(request.business_type)
    business_features = feature_set_for(business_type)
    await db.execute(
        text(
            """
            insert into company_business_settings (
                company_id,
                business_type,
                features,
                default_shelf_life_hours,
                default_discount_after_hours,
                default_discount_percent,
                auto_discount_enabled,
                created_at,
                updated_at
            ) values (
                :company_id,
                :business_type,
                cast(:features as jsonb),
                :shelf_life,
                :discount_after,
                :discount_percent,
                :auto_discount_enabled,
                :now,
                :now
            )
            on conflict (company_id) do update set
                business_type = excluded.business_type,
                features = excluded.features,
                default_shelf_life_hours = excluded.default_shelf_life_hours,
                default_discount_after_hours = excluded.default_discount_after_hours,
                default_discount_percent = excluded.default_discount_percent,
                auto_discount_enabled = excluded.auto_discount_enabled,
                updated_at = excluded.updated_at
            """
        ),
        {
            "company_id": company_id,
            "business_type": business_type,
            "features": json.dumps({
                "supports_perishable_inventory": business_features.supports_perishable_inventory,
                "supports_custom_visual_requests": business_features.supports_custom_visual_requests,
                "custom_item_label": business_features.custom_item_label,
            }, ensure_ascii=False),
            "shelf_life": business_features.default_shelf_life_hours,
            "discount_after": business_features.default_discount_after_hours,
            "discount_percent": business_features.default_discount_percent,
            "auto_discount_enabled": business_features.supports_perishable_inventory,
            "now": now,
        },
    )

    logger.info("Created company user: email=%s company_id=%s business_type=%s", request.email, company_id, business_type)

    integrator = IntegratorZernio()
    company_profile = await integrator.create_company_profile(request.email, company_id)

    await upsert_zernio_company_profile(
        db,
        company_id=company_id,
        user_id=user.id,
        company_email=request.email,
        company_profile=company_profile,
    )

    return CreateCompanyUserResponse(
        user_id=str(user.id),
        email=user.email,
        company_id=str(company_id),
        company_name=request.instagram_account_name,
        business_type=business_type,
        business_type_label=business_features.label,
        temporary_password=request.temporary_password,
    )


@router.get("/me", response_model=CurrentUserResponse)
async def get_current_user_info(
    user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CurrentUserResponse:
    statuses = await get_instagram_and_wp_statuses(db, user.user_id)
    db_user = await _load_active_user(db, user.user_id)

    if db_user.role == "company_user" and not db_user.instagram_company_id:
        await ensure_user_company(db, db_user)

    return CurrentUserResponse(
        user_id=user.user_id,
        email=user.email,
        role=user.role,
        company_id=str(db_user.instagram_company_id) if db_user.instagram_company_id else None,
        ig_activated=statuses.ig_activated if statuses else False,
        wp_activated=statuses.wp_activated if statuses else False,
        ig_enabled=statuses.ig_enabled if statuses else False,
        wp_enabled=statuses.wp_enabled if statuses else False,
    )
