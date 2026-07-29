import json
import logging
import tempfile
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, Mapping, cast

import httpx
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile
from sqlalchemy import text, bindparam
from sqlalchemy.ext.asyncio import AsyncSession

from config.app_config import settings
from config.deps import get_db
from models.auxilary_models import *
from routers.admin_auth import UserClaims, get_admin_user, get_current_user
from services.business_features import (
    BUSINESS_TYPE_FEATURES,
    build_custom_visual_prompt,
    compute_inventory_discount,
    feature_set_for,
    money,
    normalize_business_type,
)
from services.automation import (
    create_calendar_event,
    create_social_post_draft,
    delete_social_post_draft,
    list_calendar_events,
    list_social_connections,
    list_social_post_drafts,
    load_automation_settings,
    publish_social_post_draft,
    reject_social_post_draft,
    schedule_social_post_draft,
    upsert_automation_settings,
)
from services.broadcasts import create_and_send_broadcast, list_broadcast_campaigns
from services.chat_runtime import fetch_recent_chat_history, persist_message, get_company_runtime
from services.conversation_control import (
    apply_conversation_action,
    create_telegram_connect_link,
    disable_telegram_notifications,
    mark_outbound_activity,
)
from services.company import set_instagram_bot_enabled
from services.customer_orders import create_customer_order
from services.manager_notifications import (
    create_telegram_manager_connect_link,
    delete_company_manager,
    list_company_managers,
    notify_managers_about_order,
    update_company_manager,
    upsert_company_manager,
)
from services.message_activity import load_message_activity
from services.knowledge_base import (
    create_photo_knowledge_entry,
    create_text_knowledge_entry,
    delete_knowledge_entry,
    ensure_company_exists,
    list_knowledge_entries, find_relevant_knowledge_entries, build_knowledge_context,
)
from services.object_storage import (
    build_object_key,
    config_from_settings,
    normalize_public_object_url,
    upload_bytes_to_object_storage,
)
from services.subscriptions import (
    consume_usage,
    ensure_company_subscription,
    get_monthly_usage,
    get_subscription_response,
    require_autoposting,
    update_company_subscription,
)
from services.openai_messaging import (
    detect_order_intent,
    generate_custom_product_preview_image,
    generate_product_photo_description,
    generate_reply,
    normalize_product_description_language,
)
from services.prompt_defaults import DEFAULT_SYSTEM_PROMPT_AZ
from services.whatsapp_cloud import disconnect_whatsapp_cloud_integration
from services.zernio_integrator import (
    IntegratorZernio,
    _extract_linkedin_account_id,
    _extract_zernio_account_id,
    _is_linkedin_account,
    disconnect_zernio_instagram_connected_accounts,
    disconnect_zernio_tiktok_connected_accounts,
    disconnect_zernio_whatsapp_connected_accounts,
    get_latest_zernio_tiktok_connected_account,
    get_latest_zernio_whatsapp_connected_account,
    get_zernio_profile_id,
    list_zernio_instagram_connected_account_ids,
    list_zernio_tiktok_connected_account_ids,
    list_zernio_whatsapp_connected_account_ids,
    upsert_zernio_company_profile,
    upsert_zernio_instagram_connected_accounts,
    upsert_zernio_tiktok_connected_accounts,
    upsert_zernio_whatsapp_connected_accounts,
)
from services.zernio_webhooks import (
    DEFAULT_COMMENT_SYSTEM_PROMPT,
    _extract_zernio_sent_message_id,
    get_comment_prompt,
    persist_zernio_whatsapp_message,
    send_zernio_inbox_message,
)

router = APIRouter(prefix="/api", tags=["crm"])
logger = logging.getLogger(__name__)
BAKU_TIMEZONE = timezone(timedelta(hours=4))

DEFAULT_SYSTEM_PROMPT = DEFAULT_SYSTEM_PROMPT_AZ


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _slug_to_account_id(slug: str) -> str:
    normalized = slug.strip().lower().replace(" ", "-")
    return f"crm_{normalized[:56]}"


def _zernio_connect_redirect_url(platform: str, tenant_id: uuid.UUID) -> str:
    return f"{settings.app_base_url.rstrip('/')}/zernio/callback?platform={platform}&tenant_id={tenant_id}"


def _tenant_row(row: Mapping[str, object]) -> TenantResponse:
    business_type = normalize_business_type(str(row.get("business_type") or "other"))
    return TenantResponse(
        id=str(row["id"]),
        name=str(row["display_name"] or row["username"] or row["instagram_account_id"]),
        slug=str(row["username"] or row["instagram_account_id"]),
        business_type=business_type,
        business_type_label=BUSINESS_TYPE_FEATURES[business_type].label,
        is_active=not bool(row.get("access_locked")),
        package_code=cast(Literal["basic", "full"], str(row.get("package_code") or "basic")),
        access_locked=bool(row.get("access_locked")),
    )


def _channel_row(row: Mapping[str, object]) -> ChannelResponse:
    return ChannelResponse(
        id=str(row["id"]),
        tenant_id=str(row["id"]),
        platform="instagram",
        external_account_id=str(row["instagram_account_id"]),
        display_name=str(row["display_name"] or row["username"] or row["instagram_account_id"]),
    )


def _knowledge_row(row: Mapping[str, object]) -> KnowledgeEntryResponse:
    entry_type = str(row["entry_type"])
    if entry_type not in {"text", "product_photo"}:
        entry_type = "text"
    return KnowledgeEntryResponse(
        id=str(row["id"]),
        company_id=str(row["company_id"]),
        entry_type=cast(Literal["text", "product_photo"], entry_type),
        title=str(row["title"]),
        content=str(row["content"]),
        source_url=str(row["source_url"]) if row.get("source_url") else None,
        image_url=normalize_public_object_url(
            url=str(row["image_url"]) if row.get("image_url") else None,
            config=config_from_settings(settings),
        ),
        image_mime_type=str(row["image_mime_type"]) if row.get("image_mime_type") else None,
        quantity_available=int(cast(Any, row["quantity_available"])) if row.get("quantity_available") is not None else None,
        created_at=cast(datetime, row["created_at"]),
        updated_at=cast(datetime, row["updated_at"]),
    )


def _manager_row(row: Mapping[str, object]) -> ManagerResponse:
    return ManagerResponse(
        id=str(row["id"]),
        company_id=str(row["company_id"]),
        channel="telegram",
        recipient_id=str(row["recipient_id"]),
        display_name=str(row["display_name"]),
        is_active=bool(row["is_active"]),
        telegram_user_id=int(cast(Any, row["telegram_user_id"])) if row.get("telegram_user_id") is not None else None,
        telegram_chat_id=int(cast(Any, row["telegram_chat_id"])) if row.get("telegram_chat_id") is not None else None,
        telegram_username=str(row["telegram_username"]) if row.get("telegram_username") else None,
        first_name=str(row["first_name"]) if row.get("first_name") else None,
        last_name=str(row["last_name"]) if row.get("last_name") else None,
        language_code=str(row["language_code"]) if row.get("language_code") else None,
        registered_at=cast(datetime | None, row.get("registered_at")),
        last_seen_at=cast(datetime | None, row.get("last_seen_at")),
        created_at=cast(datetime, row["created_at"]),
        updated_at=cast(datetime, row["updated_at"]),
    )


def _broadcast_row(row: Mapping[str, object]) -> BroadcastCampaignResponse:
    target = str(row["target"])
    if target not in {"instagram", "whatsapp", "both"}:
        target = "both"
    return BroadcastCampaignResponse(
        id=str(row["id"]),
        company_id=str(row["company_id"]),
        target=cast(Literal["instagram", "whatsapp", "both"], target),
        message_text=str(row["message_text"]),
        status=str(row["status"]),
        requested_count=int(cast(Any, row["requested_count"] or 0)),
        sent_count=int(cast(Any, row["sent_count"] or 0)),
        failed_count=int(cast(Any, row["failed_count"] or 0)),
        created_at=cast(datetime, row["created_at"]),
        updated_at=cast(datetime, row["updated_at"]),
        completed_at=cast(datetime | None, row["completed_at"]),
    )


def _assert_company_access(tenant_id: uuid.UUID, user: UserClaims) -> None:
    if user.role == "admin":
        return
    if user.company_id != str(tenant_id):
        raise HTTPException(status_code=403, detail="Company access denied")


def _decimal_text(value: object) -> str:
    return f"{money(value):.2f}"


def _nullable_decimal_text(value: object) -> str | None:
    if value is None or value == "":
        return None
    return _decimal_text(value)


def _comment_status(value: object) -> Literal["new", "suggested", "replied", "ignored", "converted"]:
    status = str(value or "new")
    if status not in {"new", "suggested", "replied", "ignored", "converted"}:
        status = "new"
    return cast(Literal["new", "suggested", "replied", "ignored", "converted"], status)


def _comment_row(row: Mapping[str, object]) -> InstagramCommentResponse:
    return InstagramCommentResponse(
        id=str(row["id"]),
        company_id=str(row["company_id"]),
        thread_id=str(row["thread_id"]),
        zernio_account_id=str(row["zernio_account_id"]),
        platform_comment_id=str(row["platform_comment_id"]),
        platform_post_id=str(row["platform_post_id"]),
        zernio_post_id=str(row["zernio_post_id"]) if row.get("zernio_post_id") else None,
        parent_comment_id=str(row["parent_comment_id"]) if row.get("parent_comment_id") else None,
        author_id=str(row["author_id"]),
        author_username=str(row["author_username"]) if row.get("author_username") else None,
        author_name=str(row["author_name"]) if row.get("author_name") else None,
        author_picture=str(row["author_picture"]) if row.get("author_picture") else None,
        text=str(row["text_message"] or ""),
        is_reply=bool(row["is_reply"]),
        is_ad_comment=bool(row["is_ad_comment"]),
        ad_id=str(row["ad_id"]) if row.get("ad_id") else None,
        ad_title=str(row["ad_title"]) if row.get("ad_title") else None,
        status=_comment_status(row.get("status")),
        ai_suggested_reply=str(row["ai_suggested_reply"]) if row.get("ai_suggested_reply") else None,
        ai_generated_at=cast(datetime | None, row.get("ai_generated_at")),
        replied_at=cast(datetime | None, row.get("replied_at")),
        converted_at=cast(datetime | None, row.get("converted_at")),
        created_at=cast(datetime, row["created_at"]),
        inserted_at=cast(datetime, row["inserted_at"]),
    )


def _thread_row(row: Mapping[str, object], comments: list[InstagramCommentResponse] | None = None) -> CommentThreadResponse:
    inbound_count = int(cast(Any, row.get("inbound_comment_count") or 0))
    converted_count = int(cast(Any, row.get("converted_comment_count") or 0))
    return CommentThreadResponse(
        id=str(row["id"]),
        company_id=str(row["company_id"]),
        zernio_account_id=str(row["zernio_account_id"]),
        platform_post_id=str(row["platform_post_id"]),
        zernio_post_id=str(row["zernio_post_id"]) if row.get("zernio_post_id") else None,
        post_permalink=str(row["post_permalink"]) if row.get("post_permalink") else None,
        post_caption=str(row["post_caption"]) if row.get("post_caption") else None,
        comment_count=int(cast(Any, row.get("comment_count") or 0)),
        inbound_comment_count=inbound_count,
        replied_comment_count=int(cast(Any, row.get("replied_comment_count") or 0)),
        converted_comment_count=converted_count,
        conversion_rate=round((converted_count / inbound_count) * 100, 2) if inbound_count else 0.0,
        last_comment_at=cast(datetime | None, row.get("last_comment_at")),
        updated_at=cast(datetime, row["updated_at"]),
        comments=comments or [],
    )


def _order_row(row: Mapping[str, object]) -> CustomerOrderResponse:
    status = str(row["status"])
    if status not in {"new", "sent_to_manager", "accepted", "paid", "completed", "cancelled", "done"}:
        status = "new"
    revenue = money(row.get("revenue_amount"))
    cost = money(row.get("cost_amount"))
    return CustomerOrderResponse(
        id=str(row["id"]),
        company_id=str(row["company_id"]),
        channel=str(row["channel"]),
        customer_id=str(row["customer_id"]),
        conversation_id=str(row["conversation_id"]) if row.get("conversation_id") else None,
        source_message_id=str(row["source_message_id"]) if row.get("source_message_id") else None,
        customer_name=str(row["customer_name"]) if row.get("customer_name") else None,
        customer_phone=str(row["customer_phone"]) if row.get("customer_phone") else None,
        product_title=str(row["product_title"]) if row.get("product_title") else None,
        product_price=str(row["product_price"]) if row.get("product_price") else None,
        quantity=cast(int | None, row.get("quantity")),
        delivery_required=cast(bool | None, row.get("delivery_required")),
        delivery_address=str(row["delivery_address"]) if row.get("delivery_address") else None,
        delivery_time=str(row["delivery_time"]) if row.get("delivery_time") else None,
        customer_comment=str(row["customer_comment"]) if row.get("customer_comment") else None,
        raw_summary=str(row["raw_summary"]),
        status=cast(OrderStatus, status),
        revenue_amount=_nullable_decimal_text(row.get("revenue_amount")),
        cost_amount=_nullable_decimal_text(row.get("cost_amount")),
        gross_profit=_decimal_text(revenue - cost),
        manager_notified_at=cast(datetime | None, row.get("manager_notified_at")),
        paid_at=cast(datetime | None, row.get("paid_at")),
        completed_at=cast(datetime | None, row.get("completed_at")),
        cancelled_at=cast(datetime | None, row.get("cancelled_at")),
        created_at=cast(datetime, row["created_at"]),
        updated_at=cast(datetime, row["updated_at"]),
    )


async def _load_business_settings(db: AsyncSession, tenant_id: uuid.UUID) -> Mapping[str, object]:
    result = await db.execute(
        text(
            """
            select
                c.id as company_id,
                coalesce(bs.business_type, 'other') as business_type,
                bs.auto_discount_enabled,
                bs.default_shelf_life_hours,
                bs.default_discount_after_hours,
                coalesce(bs.default_discount_percent, 0) as default_discount_percent
            from instagram_companies c
            left join company_business_settings bs on bs.company_id = c.id
            where c.id = :tenant_id
            limit 1
            """
        ),
        {"tenant_id": tenant_id},
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Client space not found")
    return cast(Mapping[str, object], row)


def _business_settings_response(tenant_id: uuid.UUID, row: Mapping[str, object]) -> BusinessSettingsResponse:
    business_type = normalize_business_type(str(row.get("business_type") or "other"))
    features = BUSINESS_TYPE_FEATURES[business_type]
    return BusinessSettingsResponse(
        tenant_id=str(tenant_id),
        business_type=business_type,
        business_type_label=features.label,
        supports_perishable_inventory=features.supports_perishable_inventory,
        supports_custom_visual_requests=features.supports_custom_visual_requests,
        custom_item_label=features.custom_item_label,
        auto_discount_enabled=bool(row.get("auto_discount_enabled")),
        default_shelf_life_hours=cast(int | None, row.get("default_shelf_life_hours")),
        default_discount_after_hours=cast(int | None, row.get("default_discount_after_hours")),
        default_discount_percent=_decimal_text(row.get("default_discount_percent")),
    )



async def _instagram_integration_response(
    db: AsyncSession,
    tenant_id: uuid.UUID,
) -> InstagramIntegrationResponse:
    company_result = await db.execute(
        text(
            """
            select
                c.id,
                c.instagram_account_id,
                c.instagram_username as username,
                c.display_name,
                c.instagram_account_type,
                c.instagram_profile_picture_url,
                coalesce(u.ig_activated, false) as ig_enabled,
                coalesce(u.wp_activated, false) as wp_enabled
            from instagram_companies c
            left join users u on u.instagram_company_id = c.id and u.is_active = true
            where c.id = :tenant_id
            order by case when u.role = 'company_user' then 0 else 1 end
            limit 1
            """
        ),
        {"tenant_id": tenant_id},
    )

    company = company_result.mappings().first()

    if not company:
        raise HTTPException(status_code=404, detail="Client space not found")

    token_result = await db.execute(
        text(
            """
            select id
            from instagram_tokens
            where company_id = :tenant_id
              and is_active = true
            limit 1
            """
        ),
        {"tenant_id": tenant_id},
    )

    active_token = token_result.mappings().first()

    zernio_account_result = await db.execute(
        text(
            """
            select
                zernio_account_id,
                instagram_account_id,
                username,
                display_name,
                account_payload
            from zernio_instagram_connected_accounts
            where company_id = :tenant_id
            order by last_seen_at desc nulls last, updated_at desc nulls last
            limit 1
            """
        ),
        {"tenant_id": tenant_id},
    )
    zernio_account = zernio_account_result.mappings().first()

    ig_enabled = bool(company["ig_enabled"])
    wp_enabled = bool(company["wp_enabled"])
    ig_activated = active_token is not None or zernio_account is not None

    account_payload = zernio_account.get("account_payload") if zernio_account else None
    if not isinstance(account_payload, Mapping):
        account_payload = {}

    zernio_user_id = None
    if zernio_account:
        zernio_user_id = (
            zernio_account.get("instagram_account_id")
            or account_payload.get("instagramAccountId")
            or account_payload.get("instagram_user_id")
            or account_payload.get("externalAccountId")
            or zernio_account.get("zernio_account_id")
        )

    return InstagramIntegrationResponse(
        tenant_id=str(company["id"]),
        ig_activated=ig_activated,
        ig_enabled=ig_enabled if ig_activated else False,
        wp_activated=wp_enabled,
        wp_enabled=wp_enabled,
        user_id=(
            str(company["instagram_account_id"])
            if company.get("instagram_account_id")
            else str(zernio_user_id) if zernio_user_id else None
        ),
        username=(
            str(company["username"])
            if company.get("username")
            else str(zernio_account["username"]) if zernio_account and zernio_account.get("username") else None
        ),
        display_name=(
            str(company["display_name"])
            if company.get("display_name")
            else str(zernio_account["display_name"]) if zernio_account and zernio_account.get("display_name") else None
        ),
        account_type=(
            str(company["instagram_account_type"])
            if company.get("instagram_account_type")
            else "zernio"
            if zernio_account
            else None
        ),
        profile_picture_url=(
            str(company["instagram_profile_picture_url"])
            if company.get("instagram_profile_picture_url")
            else str(account_payload.get("profilePictureUrl") or account_payload.get("profile_picture_url"))
            if account_payload.get("profilePictureUrl") or account_payload.get("profile_picture_url")
            else None
        ),
    )

@router.get("/tenants", response_model=list[TenantResponse])
async def list_tenants(db: AsyncSession = Depends(get_db)) -> list[TenantResponse]:
    result = await db.execute(
        text(
            """
            select
                c.id,
                c.instagram_account_id,
                c.instagram_username as username,
                c.display_name,
                c.created_at,
                coalesce(bs.business_type, 'other') as business_type,
                coalesce(cs.package_code, 'basic') as package_code,
                coalesce(cs.access_locked, false) as access_locked
            from instagram_companies c
            left join company_business_settings bs on bs.company_id = c.id
            left join company_subscriptions cs on cs.company_id = c.id
            order by c.created_at desc nulls last, c.display_name asc nulls last
            """
        )
    )
    return [_tenant_row(cast(Mapping[str, object], row)) for row in result.mappings().all()]


@router.get("/admin/tenants/{tenant_id}/subscription", response_model=CompanySubscriptionResponse)
async def get_admin_company_subscription(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: UserClaims = Depends(get_admin_user),
) -> CompanySubscriptionResponse:
    _ = admin
    await ensure_company_exists(db, tenant_id)
    return CompanySubscriptionResponse(**await get_subscription_response(db, tenant_id))


@router.put("/admin/tenants/{tenant_id}/subscription", response_model=CompanySubscriptionResponse)
async def update_admin_company_subscription(
    tenant_id: uuid.UUID,
    payload: CompanySubscriptionUpdate,
    db: AsyncSession = Depends(get_db),
    admin: UserClaims = Depends(get_admin_user),
) -> CompanySubscriptionResponse:
    _ = admin
    await ensure_company_exists(db, tenant_id)
    subscription = await update_company_subscription(
        db,
        tenant_id,
        package_code=payload.package_code,
        access_locked=payload.access_locked,
        locked_reason=payload.locked_reason,
    )
    usage = await get_monthly_usage(db, tenant_id)
    return CompanySubscriptionResponse(**{
        **subscription,
        "company_id": str(subscription["company_id"]),
        "usage_period": datetime.now(timezone.utc).strftime("%Y-%m"),
        **usage,
    })


@router.post("/tenants", status_code=201, response_model=TenantResponse)
async def create_tenant(payload: TenantCreate, db: AsyncSession = Depends(get_db)) -> TenantResponse:
    now = _now()
    tenant_id = uuid.uuid4()
    account_id = _slug_to_account_id(payload.slug)

    existing = await db.execute(
        text(
            """
            select id
            from instagram_companies
            where instagram_account_id = :account_id or lower(instagram_username) = lower(:username)
            limit 1
            """
        ),
        {"account_id": account_id, "username": payload.slug.strip()},
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Client space already exists")

    await db.execute(
        text(
            """
            insert into instagram_companies (
                id,
                instagram_account_id,
                instagram_username,
                display_name,
                created_at,
                updated_at
            ) values (
                :id,
                :instagram_account_id,
                :username,
                :display_name,
                :now,
                :now
            )
            """
        ),
        {
            "id": tenant_id,
            "instagram_account_id": account_id,
            "username": payload.slug.strip(),
            "display_name": payload.name.strip(),
            "now": now,
        },
    )
    await db.execute(
        text(
            """
            insert into instagram_system_prompts (
                id,
                company_id,
                title,
                prompt_text,
                version,
                created_at,
                updated_at
            ) values (
                :id,
                :company_id,
                'Default prompt',
                :prompt_text,
                1,
                :now,
                :now
            )
            """
        ),
        {"id": uuid.uuid4(), "company_id": tenant_id, "prompt_text": DEFAULT_SYSTEM_PROMPT, "now": now},
    )
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
            "company_id": tenant_id,
            "business_type": normalize_business_type(payload.business_type),
            "features": json.dumps({
                "supports_perishable_inventory": feature_set_for(payload.business_type).supports_perishable_inventory,
                "supports_custom_visual_requests": feature_set_for(payload.business_type).supports_custom_visual_requests,
                "custom_item_label": feature_set_for(payload.business_type).custom_item_label,
            }, ensure_ascii=False),
            "shelf_life": feature_set_for(payload.business_type).default_shelf_life_hours,
            "discount_after": feature_set_for(payload.business_type).default_discount_after_hours,
            "discount_percent": feature_set_for(payload.business_type).default_discount_percent,
            "auto_discount_enabled": feature_set_for(payload.business_type).supports_perishable_inventory,
            "now": now,
        },
    )
    await ensure_company_subscription(db, tenant_id)
    await db.commit()

    business_type = normalize_business_type(payload.business_type)
    return TenantResponse(
        id=str(tenant_id),
        name=payload.name.strip(),
        slug=payload.slug.strip(),
        business_type=business_type,
        business_type_label=BUSINESS_TYPE_FEATURES[business_type].label,
        is_active=True,
        package_code="basic",
        access_locked=False,
    )


@router.get("/channels", response_model=list[ChannelResponse])
async def list_channels(
    tenant_id: uuid.UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> list[ChannelResponse]:
    params: dict[str, object] = {}
    if tenant_id:
        params["tenant_id"] = tenant_id

    result = await db.execute(
        text(
            f"""
            select id, instagram_account_id, instagram_username as username, display_name from instagram_companies where id = :tenant_id
            order by display_name asc nulls last, instagram_username asc nulls last
            """
        ),
        params,
    )
    return [_channel_row(cast(Mapping[str, object], row)) for row in result.mappings().all()]


@router.post("/channels", status_code=201, response_model=ChannelResponse)
async def create_channel(payload: ChannelCreate, db: AsyncSession = Depends(get_db)) -> ChannelResponse:
    if payload.platform != "instagram":
        raise HTTPException(status_code=400, detail="WhatsApp adapter is not wired in this backend yet")

    existing = await db.execute(
        text("select id from instagram_companies where id = :id limit 1"),
        {"id": payload.tenant_id},
    )
    if not existing.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Client space not found")

    conflict = await db.execute(
        text(
            """
            select id
            from instagram_companies
            where instagram_account_id = :account_id and id <> :id
            limit 1
            """
        ),
        {"account_id": payload.external_account_id.strip(), "id": payload.tenant_id},
    )
    if conflict.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Instagram account is already linked")

    await db.execute(
        text(
            """
            update instagram_companies
            set instagram_account_id = :account_id,
                display_name = :display_name,
                updated_at = :now
            where id = :id
            """
        ),
        {
            "id": payload.tenant_id,
            "account_id": payload.external_account_id.strip(),
            "display_name": payload.display_name.strip(),
            "now": _now(),
        },
    )
    await db.commit()

    return ChannelResponse(
        id=str(payload.tenant_id),
        tenant_id=str(payload.tenant_id),
        platform="instagram",
        external_account_id=payload.external_account_id.strip(),
        display_name=payload.display_name.strip(),
        is_enabled=True,
    )


@router.get("/tenants/{tenant_id}/instagram", response_model=InstagramIntegrationResponse)
async def get_instagram_integration(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> InstagramIntegrationResponse:
    _assert_company_access(tenant_id, user)

    zernio_profile_id = await get_zernio_profile_id(db, tenant_id)
    if zernio_profile_id:
        try:
            connected_accounts = await IntegratorZernio().get_connected_accounts(zernio_profile_id)
            await upsert_zernio_instagram_connected_accounts(
                db,
                company_id=tenant_id,
                zernio_profile_id=zernio_profile_id,
                accounts=connected_accounts,
            )
        except RuntimeError:
            await db.rollback()
            logger.warning("Zernio connected accounts sync skipped: SDK is not configured", exc_info=True)
        except ValueError as exc:
            await db.rollback()
            if "already linked to another business" in str(exc):
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            logger.warning("Zernio connected accounts sync returned invalid payload", exc_info=True)
        except Exception as exc:
            await db.rollback()
            if "UniqueViolationError" in str(exc) or "duplicate key value" in str(exc):
                raise HTTPException(status_code=409, detail="Instagram account is already linked to another business") from exc
            logger.warning("Zernio connected accounts sync failed", exc_info=True)

    return await _instagram_integration_response(db, tenant_id)


@router.post("/tenants/{tenant_id}/instagram/connect", response_model=InstagramConnectUrlResponse)
async def connect_instagram_with_zernio(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> InstagramConnectUrlResponse:
    _assert_company_access(tenant_id, user)

    zernio_profile_id = await _require_zernio_company_profile(db, tenant_id, user)

    try:
        auth_url = await IntegratorZernio().connect_social_network(
            "instagram",
            zernio_profile_id,
            redirect_url=_zernio_connect_redirect_url("instagram", tenant_id),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Zernio Instagram connect request failed") from exc

    return InstagramConnectUrlResponse(auth_url=auth_url)


@router.patch("/tenants/{tenant_id}/instagram/bot-status", response_model=InstagramIntegrationResponse)
async def update_instagram_bot_status(
    tenant_id: uuid.UUID,
    payload: InstagramBotStatusUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> InstagramIntegrationResponse:
    _assert_company_access(tenant_id, user)
    await set_instagram_bot_enabled(db, tenant_id, payload.enabled)
    return await _instagram_integration_response(db, tenant_id)



def _zernio_whatsapp_response(tenant_id: uuid.UUID, account: Mapping[str, Any] | None) -> WhatsAppCloudIntegrationResponse:
    if not account:
        return WhatsAppCloudIntegrationResponse(
            status="not_connected",
            tenant_id=str(tenant_id),
            business_id=None,
            waba_id="",
            phone_number_id="",
            display_phone_number=None,
            verified_name=None,
            quality_rating=None,
            webhook_subscribed=False,
            connected=False,
            registered=False,
            pin_required=False,
        )

    payload = account.get("account_payload")
    if not isinstance(payload, Mapping):
        payload = {}

    zernio_account_id = str(account.get("zernio_account_id") or "")
    whatsapp_account_id = str(account.get("whatsapp_account_id") or zernio_account_id)
    display_value = account.get("username") or payload.get("phone") or payload.get("displayPhoneNumber")
    verified_name = account.get("display_name") or payload.get("verifiedName") or payload.get("name")

    return WhatsAppCloudIntegrationResponse(
        status="connected",
        tenant_id=str(tenant_id),
        business_id=str(account.get("zernio_profile_id") or "") or None,
        waba_id=zernio_account_id,
        phone_number_id=whatsapp_account_id,
        display_phone_number=str(display_value) if display_value else None,
        verified_name=str(verified_name) if verified_name else None,
        quality_rating=str(payload.get("qualityRating")) if payload.get("qualityRating") else None,
        webhook_subscribed=True,
        connected=True,
        registered=True,
        pin_required=False,
    )


# Official WhatsApp Cloud API integration is kept for old Meta routes, but company UI uses Zernio now.


@router.post(
    "/tenants/{tenant_id}/whatsapp-cloud/connect",
    response_model=InstagramConnectUrlResponse,
)
async def connect_whatsapp_with_zernio(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> InstagramConnectUrlResponse:
    _assert_company_access(tenant_id, user)

    zernio_profile_id = await _require_zernio_company_profile(db, tenant_id, user)

    try:
        auth_url = await IntegratorZernio().connect_social_network(
            "whatsapp",
            zernio_profile_id,
            redirect_url=_zernio_connect_redirect_url("whatsapp", tenant_id),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Zernio WhatsApp connect request failed") from exc

    return InstagramConnectUrlResponse(auth_url=auth_url)



def _linkedin_response(tenant_id: uuid.UUID, connection: Mapping[str, Any] | None) -> LinkedInIntegrationResponse:
    if not connection or connection.get("status") != "connected":
        return LinkedInIntegrationResponse(tenant_id=str(tenant_id), connected=False)
    metadata = connection.get("metadata")
    if not isinstance(metadata, Mapping):
        metadata = {}
    zernio_account_id = str(metadata.get("zernio_account_id") or "").strip()
    linkedin_account_id = str(connection.get("external_account_id") or "").strip()
    if not zernio_account_id or not linkedin_account_id:
        return LinkedInIntegrationResponse(tenant_id=str(tenant_id), connected=False)
    return LinkedInIntegrationResponse(
        tenant_id=str(tenant_id),
        connected=True,
        zernio_account_id=zernio_account_id,
        linkedin_account_id=linkedin_account_id,
        username=str(metadata.get("username") or "") or None,
        display_name=str(connection.get("display_name") or metadata.get("displayName") or metadata.get("name") or "") or None,
        connected_at=cast(datetime | None, connection.get("connected_at")),
    )


async def _linkedin_connection(db: AsyncSession, tenant_id: uuid.UUID) -> Mapping[str, Any] | None:
    result = await db.execute(
        text("select status, external_account_id, display_name, metadata, connected_at from social_posting_connections where company_id = :company_id and platform = 'linkedin' limit 1"),
        {"company_id": tenant_id},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def _disable_linkedin_connection(db: AsyncSession, tenant_id: uuid.UUID) -> None:
    await db.execute(
        text(
            "update social_posting_connections set status = 'disabled', external_account_id = null, display_name = null, "
            "metadata = '{}'::jsonb, connected_at = null, updated_at = now() "
            "where company_id = :company_id and platform = 'linkedin'"
        ),
        {"company_id": tenant_id},
    )


async def _ensure_zernio_company_profile(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user: UserClaims,
) -> str | None:
    """Return the tenant's Zernio profile, provisioning it once when possible."""
    existing_profile_id = await get_zernio_profile_id(db, tenant_id)
    if existing_profile_id:
        return existing_profile_id
    if not settings.zernio_api_key:
        return None

    # Serialize provisioning per tenant. Without this lock, two browser requests
    # can create duplicate profiles in Zernio before either one reaches Postgres.
    await db.execute(
        text("select pg_advisory_xact_lock(hashtextextended(cast(:company_id as text), 0))"),
        {"company_id": str(tenant_id)},
    )
    existing_profile_id = await get_zernio_profile_id(db, tenant_id)
    if existing_profile_id:
        return existing_profile_id

    company_profile = await IntegratorZernio().create_company_profile(user.email, tenant_id)
    await upsert_zernio_company_profile(
        db,
        company_id=tenant_id,
        user_id=uuid.UUID(user.user_id),
        company_email=user.email,
        company_profile=company_profile,
    )
    profile_id = await get_zernio_profile_id(db, tenant_id)
    if not profile_id:
        raise RuntimeError("Zernio company profile was created but not persisted")
    logger.info("Provisioned Zernio company profile company_id=%s", tenant_id)
    return profile_id


async def _require_zernio_company_profile(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user: UserClaims,
) -> str:
    try:
        profile_id = await _ensure_zernio_company_profile(db, tenant_id, user)
    except RuntimeError as exc:
        await db.rollback()
        raise HTTPException(status_code=503, detail="Social integrations are temporarily unavailable") from exc
    except Exception as exc:
        await db.rollback()
        logger.warning("Zernio company profile provisioning failed", exc_info=True)
        raise HTTPException(status_code=502, detail="Social integration setup failed") from exc
    if not profile_id:
        raise HTTPException(status_code=503, detail="Social integrations are not configured on this server")
    return profile_id


@router.get("/tenants/{tenant_id}/linkedin", response_model=LinkedInIntegrationResponse)
async def get_linkedin_integration(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> LinkedInIntegrationResponse:
    _assert_company_access(tenant_id, user)
    if not settings.zernio_api_key:
        await _disable_linkedin_connection(db, tenant_id)
        await db.commit()
        return _linkedin_response(tenant_id, await _linkedin_connection(db, tenant_id))
    try:
        zernio_profile_id = await _ensure_zernio_company_profile(db, tenant_id, user)
    except RuntimeError as exc:
        await db.rollback()
        raise HTTPException(status_code=503, detail="LinkedIn integration is temporarily unavailable") from exc
    except Exception as exc:
        await db.rollback()
        logger.warning("Zernio company profile provisioning failed", exc_info=True)
        raise HTTPException(status_code=502, detail="LinkedIn integration setup failed") from exc
    if zernio_profile_id:
        try:
            accounts = await IntegratorZernio().get_connected_accounts(zernio_profile_id)
            linkedin_accounts = [item for item in accounts if _is_linkedin_account(item)]
            current_connection = await _linkedin_connection(db, tenant_id)
            current_metadata = current_connection.get("metadata") if current_connection else None
            preferred_account_id = str(current_metadata.get("zernio_account_id") or "") if isinstance(current_metadata, Mapping) else ""
            account = next(
                (item for item in linkedin_accounts if _extract_zernio_account_id(item) == preferred_account_id),
                None,
            )
            if account is None and linkedin_accounts:
                account = min(linkedin_accounts, key=_extract_zernio_account_id)
            if account:
                zernio_account_id = _extract_zernio_account_id(account)
                linkedin_account_id = _extract_linkedin_account_id(account)
                if not linkedin_account_id:
                    await _disable_linkedin_connection(db, tenant_id)
                    await db.commit()
                    raise HTTPException(status_code=502, detail="Zernio LinkedIn account is missing a stable external identity")
                display_name = account.get("displayName") or account.get("display_name") or account.get("name") or account.get("username")
                metadata = dict(account)
                metadata["zernio_account_id"] = zernio_account_id
                conflict_result = await db.execute(
                    text(
                        """
                        select company_id
                        from social_posting_connections
                        where platform = 'linkedin'
                          and status = 'connected'
                          and btrim(external_account_id) = :external_account_id
                          and company_id <> :company_id
                        limit 1
                        """
                    ),
                    {"company_id": tenant_id, "external_account_id": linkedin_account_id},
                )
                if conflict_result.scalar_one_or_none():
                    raise HTTPException(status_code=409, detail="LinkedIn account is already linked to another business")
                await db.execute(
                    text(
                        """
                        insert into social_posting_connections (company_id, platform, status, external_account_id, display_name, metadata, connected_at)
                        values (:company_id, 'linkedin', 'connected', :external_account_id, :display_name, cast(:metadata as jsonb), now())
                        on conflict (company_id, platform) do update set
                            status = 'connected', external_account_id = excluded.external_account_id,
                            display_name = excluded.display_name, metadata = excluded.metadata,
                            connected_at = case
                                when social_posting_connections.status <> 'connected'
                                  or social_posting_connections.external_account_id is distinct from excluded.external_account_id
                                then now()
                                else coalesce(social_posting_connections.connected_at, now())
                            end,
                            updated_at = now()
                        """
                    ),
                    {"company_id": tenant_id, "external_account_id": linkedin_account_id, "display_name": display_name, "metadata": json.dumps(metadata, ensure_ascii=False)},
                )
                await db.commit()
            else:
                await _disable_linkedin_connection(db, tenant_id)
                await db.commit()
        except HTTPException:
            await db.rollback()
            raise
        except RuntimeError as exc:
            await db.rollback()
            await _disable_linkedin_connection(db, tenant_id)
            await db.commit()
            raise HTTPException(status_code=503, detail="LinkedIn connection status is temporarily unavailable") from exc
        except Exception as exc:
            await db.rollback()
            await _disable_linkedin_connection(db, tenant_id)
            await db.commit()
            if "UniqueViolationError" in str(exc) or "duplicate key value" in str(exc):
                raise HTTPException(status_code=409, detail="LinkedIn account is already linked to another business") from exc
            logger.warning("Zernio LinkedIn accounts sync failed", exc_info=True)
            raise HTTPException(status_code=502, detail="LinkedIn connection status could not be verified") from exc
    else:
        await _disable_linkedin_connection(db, tenant_id)
        await db.commit()
    return _linkedin_response(tenant_id, await _linkedin_connection(db, tenant_id))


@router.post("/tenants/{tenant_id}/linkedin/connect", response_model=InstagramConnectUrlResponse)
async def connect_linkedin_with_zernio(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> InstagramConnectUrlResponse:
    _assert_company_access(tenant_id, user)
    zernio_profile_id = await _require_zernio_company_profile(db, tenant_id, user)
    try:
        auth_url = await IntegratorZernio().connect_social_network(
            "linkedin", zernio_profile_id, redirect_url=_zernio_connect_redirect_url("linkedin", tenant_id)
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Zernio LinkedIn connect request failed") from exc
    return InstagramConnectUrlResponse(auth_url=auth_url)


@router.delete("/tenants/{tenant_id}/linkedin", response_model=LinkedInIntegrationResponse)
async def disconnect_linkedin(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> LinkedInIntegrationResponse:
    _assert_company_access(tenant_id, user)
    connection = await _linkedin_connection(db, tenant_id)
    metadata = connection.get("metadata") if connection else None
    is_connected = bool(connection and connection.get("status") == "connected")
    zernio_account_id = metadata.get("zernio_account_id") if is_connected and isinstance(metadata, Mapping) else None
    if zernio_account_id:
        try:
            await _delete_zernio_accounts([str(zernio_account_id)], platform="linkedin")
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Zernio LinkedIn disconnect request failed") from exc
    await db.execute(
        text(
            "update social_posting_connections set status = 'disabled', external_account_id = null, display_name = null, "
            "metadata = '{}'::jsonb, connected_at = null, updated_at = now() "
            "where company_id = :company_id and platform = 'linkedin'"
        ),
        {"company_id": tenant_id},
    )
    await db.commit()
    return _linkedin_response(tenant_id, None)



def _tiktok_response(tenant_id: uuid.UUID, account: Mapping[str, Any] | None, creator_info: Mapping[str, Any] | None = None) -> TikTokIntegrationResponse:
    if not account:
        return TikTokIntegrationResponse(tenant_id=str(tenant_id), connected=False)
    payload = account.get("account_payload")
    if not isinstance(payload, Mapping):
        payload = {}
    return TikTokIntegrationResponse(
        tenant_id=str(tenant_id),
        connected=True,
        zernio_account_id=str(account.get("zernio_account_id")) if account.get("zernio_account_id") else None,
        tiktok_account_id=str(account.get("tiktok_account_id")) if account.get("tiktok_account_id") else None,
        username=str(account.get("username") or payload.get("username") or "") or None,
        display_name=str(account.get("display_name") or payload.get("displayName") or payload.get("name") or "") or None,
        connected_at=cast(datetime | None, account.get("created_at")),
        creator_info=dict(creator_info) if creator_info else None,
    )


@router.get("/tenants/{tenant_id}/tiktok", response_model=TikTokIntegrationResponse)
async def get_tiktok_integration(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> TikTokIntegrationResponse:
    _assert_company_access(tenant_id, user)
    zernio_profile_id = await get_zernio_profile_id(db, tenant_id)
    if zernio_profile_id:
        try:
            connected_accounts = await IntegratorZernio().get_connected_accounts(zernio_profile_id)
            await upsert_zernio_tiktok_connected_accounts(db, company_id=tenant_id, zernio_profile_id=zernio_profile_id, accounts=connected_accounts)
        except RuntimeError:
            await db.rollback()
            logger.warning("Zernio TikTok accounts sync skipped: SDK is not configured", exc_info=True)
        except ValueError as exc:
            await db.rollback()
            if "already linked to another business" in str(exc):
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            logger.warning("Zernio TikTok accounts sync returned invalid payload", exc_info=True)
        except Exception as exc:
            await db.rollback()
            if "UniqueViolationError" in str(exc) or "duplicate key value" in str(exc):
                raise HTTPException(status_code=409, detail="TikTok account is already linked to another business") from exc
            logger.warning("Zernio TikTok accounts sync failed", exc_info=True)
    account = await get_latest_zernio_tiktok_connected_account(db, tenant_id)
    if account:
        await db.execute(
            text(
                """
                insert into social_posting_connections (company_id, platform, status, external_account_id, display_name, metadata, connected_at)
                values (:company_id, 'tiktok', 'connected', :external_account_id, :display_name, cast(:metadata as jsonb), now())
                on conflict (company_id, platform) do update set
                    status = 'connected',
                    external_account_id = excluded.external_account_id,
                    display_name = excluded.display_name,
                    metadata = excluded.metadata,
                    connected_at = coalesce(social_posting_connections.connected_at, now()),
                    updated_at = now()
                """
            ),
            {
                "company_id": tenant_id,
                "external_account_id": account.get("tiktok_account_id") or account.get("zernio_account_id"),
                "display_name": account.get("display_name") or account.get("username"),
                "metadata": json.dumps(account.get("account_payload") or {}, ensure_ascii=False),
            },
        )
        await db.commit()
    return _tiktok_response(tenant_id, account)


@router.post("/tenants/{tenant_id}/tiktok/connect", response_model=InstagramConnectUrlResponse)
async def connect_tiktok_with_zernio(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> InstagramConnectUrlResponse:
    _assert_company_access(tenant_id, user)
    zernio_profile_id = await _require_zernio_company_profile(db, tenant_id, user)
    try:
        auth_url = await IntegratorZernio().connect_social_network(
            "tiktok",
            zernio_profile_id,
            redirect_url=_zernio_connect_redirect_url("tiktok", tenant_id),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Zernio TikTok connect request failed") from exc
    return InstagramConnectUrlResponse(auth_url=auth_url)


@router.delete("/tenants/{tenant_id}/tiktok", response_model=TikTokIntegrationResponse)
async def disconnect_tiktok(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> TikTokIntegrationResponse:
    _assert_company_access(tenant_id, user)
    account_ids = await list_zernio_tiktok_connected_account_ids(db, tenant_id)
    try:
        await _delete_zernio_accounts(account_ids, platform="tiktok")
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    await disconnect_zernio_tiktok_connected_accounts(db, tenant_id)
    return _tiktok_response(tenant_id, None)


async def _delete_zernio_accounts(account_ids: list[str], *, platform: str) -> list[dict[str, Any]]:
    deleted: list[dict[str, Any]] = []
    if not account_ids:
        return deleted

    client = IntegratorZernio()
    for account_id in account_ids:
        try:
            response = await client.delete_account(account_id)
        except RuntimeError:
            raise
        except Exception as exc:
            logger.warning("Zernio %s account delete failed account_id=%s", platform, account_id, exc_info=True)
            raise HTTPException(status_code=502, detail=f"Zernio {platform} account delete failed for {account_id}") from exc
        deleted.append({"account_id": account_id, "response": response})
    return deleted


@router.post("/tenants/{tenant_id}/instagram/deauthorize", response_model=InstagramIntegrationResponse)
@router.delete("/tenants/{tenant_id}/instagram", response_model=InstagramIntegrationResponse)
async def deauthorize_instagram_integration(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> InstagramIntegrationResponse:
    _assert_company_access(tenant_id, user)
    await ensure_company_exists(db, tenant_id)

    account_ids = await list_zernio_instagram_connected_account_ids(db, tenant_id)
    try:
        await _delete_zernio_accounts(account_ids, platform="instagram")
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    await disconnect_zernio_instagram_connected_accounts(db, tenant_id)
    return await _instagram_integration_response(db, tenant_id)


@router.get("/tenants/{tenant_id}/managers", response_model=list[ManagerResponse])
async def get_managers(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> list[ManagerResponse]:
    _assert_company_access(tenant_id, user)
    rows = await list_company_managers(db, tenant_id)
    return [_manager_row(row) for row in rows]


@router.post("/tenants/{tenant_id}/managers/telegram/connect-link", response_model=TelegramManagerConnectResponse)
async def create_manager_telegram_connect_link(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> TelegramManagerConnectResponse:
    _assert_company_access(tenant_id, user)
    await ensure_company_exists(db, tenant_id)
    try:
        connect_url = await create_telegram_manager_connect_link(
            db,
            company_id=tenant_id,
            created_by_user_id=uuid.UUID(user.user_id),
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return TelegramManagerConnectResponse(connect_url=connect_url)


@router.post("/tenants/{tenant_id}/managers", status_code=201, response_model=ManagerResponse)
async def create_manager(
    tenant_id: uuid.UUID,
    payload: ManagerCreate,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> ManagerResponse:
    _assert_company_access(tenant_id, user)
    await ensure_company_exists(db, tenant_id)
    try:
        row = await upsert_company_manager(
            db,
            company_id=tenant_id,
            channel=payload.channel,
            recipient_id=payload.recipient_id,
            display_name=payload.display_name,
            is_active=payload.is_active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _manager_row(row)


@router.put("/tenants/{tenant_id}/managers/{manager_id}", response_model=ManagerResponse)
async def edit_manager(
    tenant_id: uuid.UUID,
    manager_id: uuid.UUID,
    payload: ManagerUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> ManagerResponse:
    _assert_company_access(tenant_id, user)
    try:
        row = await update_company_manager(
            db,
            company_id=tenant_id,
            manager_id=manager_id,
            recipient_id=payload.recipient_id,
            display_name=payload.display_name,
            is_active=payload.is_active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _manager_row(row)


@router.delete("/tenants/{tenant_id}/managers/{manager_id}", status_code=204)
async def remove_manager(
    tenant_id: uuid.UUID,
    manager_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> None:
    _assert_company_access(tenant_id, user)
    try:
        await delete_company_manager(db, company_id=tenant_id, manager_id=manager_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/tenants/{tenant_id}/broadcasts", response_model=list[BroadcastCampaignResponse])
async def get_broadcasts(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> list[BroadcastCampaignResponse]:
    _assert_company_access(tenant_id, user)
    rows = await list_broadcast_campaigns(db, tenant_id)
    return [_broadcast_row(row) for row in rows]


@router.post("/tenants/{tenant_id}/broadcasts", status_code=201, response_model=BroadcastCampaignResponse)
async def send_broadcast(
    tenant_id: uuid.UUID,
    payload: BroadcastCreate,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> BroadcastCampaignResponse:
    _assert_company_access(tenant_id, user)
    try:
        row = await create_and_send_broadcast(
            db,
            company_id=tenant_id,
            target=payload.target,
            message_text=payload.message_text.strip(),
        )
    except ValueError as exc:
        status_code = 400 if "WhatsApp broadcast" in str(exc) or "Unsupported broadcast" in str(exc) else 404
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return _broadcast_row(row)


@router.get("/tenants/{tenant_id}/knowledge-base", response_model=list[KnowledgeEntryResponse])
async def get_knowledge_base_entries(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> list[KnowledgeEntryResponse]:
    _assert_company_access(tenant_id, user)
    rows = await list_knowledge_entries(db, tenant_id)
    return [_knowledge_row(row) for row in rows]


@router.post(
    "/tenants/{tenant_id}/knowledge-base",
    status_code=201,
    response_model=KnowledgeEntryResponse,
)
async def create_knowledge_base_text_entry(
    tenant_id: uuid.UUID,
    payload: KnowledgeTextCreate,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> KnowledgeEntryResponse:
    _assert_company_access(tenant_id, user)

    try:
        await ensure_company_exists(db, tenant_id)

        row = await create_text_knowledge_entry(
            db=db,
            company_id=tenant_id,
            title=payload.title,
            content=payload.content,
            source_url=payload.source_url,
            quantity_available=payload.quantity_available,
        )

        return _knowledge_row(row)

    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc



@router.post(
    "/tenants/{tenant_id}/knowledge-base/photos",
    status_code=201,
    response_model=KnowledgeEntryResponse,
)
async def upload_knowledge_base_photo(
    tenant_id: uuid.UUID,
    title: str = Form(..., min_length=1, max_length=255),
    price: Decimal | None = Form(default=None),
    quantity_available: int | None = Form(default=None, ge=0),
    delivery_available: str = Form(default="false"),
    description_language: str = Form(default="az"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> KnowledgeEntryResponse:
    _assert_company_access(tenant_id, user)

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image uploads are supported")

    try:
        await ensure_company_exists(db, tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    content = await file.read()

    if len(content) > 8 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image is too large; max 8MB")

    extension = Path(file.filename or "product.jpg").suffix.lower()

    if extension not in {".jpg", ".jpeg", ".png", ".webp"}:
        extension = ".jpg"

    description_language_code = normalize_product_description_language(description_language)

    with tempfile.NamedTemporaryFile(suffix=extension, delete=True) as tmp:
        tmp.write(content)
        tmp.flush()
        ai_description = generate_product_photo_description(
            Path(tmp.name),
            file.content_type,
            description_language_code,
        )

    object_key = build_object_key(
        company_id=tenant_id,
        folder="knowledge-base",
        filename=file.filename or f"product{extension}",
    )
    try:
        image_url = upload_bytes_to_object_storage(
            config=config_from_settings(settings),
            key=object_key,
            content=content,
            content_type=file.content_type,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    delivery_enabled = delivery_available.strip().lower() in {"1", "true", "yes", "on"}

    extra_info: list[str] = []

    if description_language_code == "en":
        if price is not None:
            extra_info.append(f"Price: {price} AZN")
        if quantity_available is not None:
            extra_info.append(f"Stock quantity: {quantity_available}")
        extra_info.append("Delivery is available" if delivery_enabled else "Delivery is not available")
    elif description_language_code == "ru":
        if price is not None:
            extra_info.append(f"Цена: {price} AZN")
        if quantity_available is not None:
            extra_info.append(f"Остаток: {quantity_available}")
        extra_info.append("Доставка доступна" if delivery_enabled else "Доставка недоступна")
    else:
        if price is not None:
            extra_info.append(f"Qiymət: {price} AZN")
        if quantity_available is not None:
            extra_info.append(f"Stok sayı: {quantity_available}")
        extra_info.append("Çatdırılma mövcuddur" if delivery_enabled else "Çatdırılma mövcud deyil")

    final_description = ai_description

    if extra_info:
        final_description += "\n\n" + "\n".join(extra_info)

    row = await create_photo_knowledge_entry(
        db,
        company_id=tenant_id,
        title=title,
        image_url=image_url,
        image_mime_type=file.content_type,
        ai_description=final_description,
        quantity_available=quantity_available,
    )

    return _knowledge_row(row)


@router.delete("/tenants/{tenant_id}/knowledge-base/{entry_id}", status_code=204)
async def remove_knowledge_base_entry(
    tenant_id: uuid.UUID,
    entry_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> None:
    _assert_company_access(tenant_id, user)
    try:
        await delete_knowledge_entry(db, tenant_id, entry_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/tenants/{tenant_id}/bot-settings", response_model=BotSettingsResponse)
async def get_bot_settings(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> BotSettingsResponse:
    _assert_company_access(tenant_id, user)

    result = await db.execute(
        text(
            """
            select id
            from instagram_companies
            where id = :tenant_id
            limit 1
            """
        ),
        {"tenant_id": tenant_id},
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Client space not found")

    # Company users can manage runtime bot status elsewhere, but the AI system
    # prompt is admin-only and is intentionally not exposed in this response.
    return BotSettingsResponse(
        tenant_id=str(row["id"]),
        system_prompt="",
        handoff_keywords=DEFAULT_HANDOFF_KEYWORDS,
    )


@router.put("/tenants/{tenant_id}/bot-settings", response_model=BotSettingsResponse)
async def update_bot_settings(
    tenant_id: uuid.UUID,
    payload: BotSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> BotSettingsResponse:
    _assert_company_access(tenant_id, user)

    if payload.system_prompt is not None:
        if user.role != "admin":
            raise HTTPException(status_code=403, detail="System prompt can be changed by admin only")
        raise HTTPException(
            status_code=400,
            detail="Use /api/admin/tenants/{tenant_id}/bot-prompt to update system prompt",
        )

    result = await db.execute(
        text("select id from instagram_companies where id = :tenant_id limit 1"),
        {"tenant_id": tenant_id},
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Client space not found")

    # This company endpoint intentionally does not accept or update system_prompt.
    # Prompt management is available only via /api/admin/tenants/{tenant_id}/bot-prompt.
    return BotSettingsResponse(
        tenant_id=str(row["id"]),
        system_prompt="",
        handoff_keywords=payload.handoff_keywords,
    )


@router.get("/tenants/{tenant_id}/bot-prompt", response_model=AdminBotPromptResponse)
async def get_company_bot_prompt(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> AdminBotPromptResponse:
    _assert_company_access(tenant_id, user)
    return await _load_admin_bot_prompt(db, tenant_id)


@router.put("/tenants/{tenant_id}/bot-prompt", response_model=AdminBotPromptResponse)
async def update_company_bot_prompt(
    tenant_id: uuid.UUID,
    payload: AdminBotPromptUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> AdminBotPromptResponse:
    _assert_company_access(tenant_id, user)
    return await _upsert_admin_bot_prompt(db, tenant_id, payload)


@router.get("/admin/tenants/{tenant_id}/bot-prompt", response_model=AdminBotPromptResponse)
async def get_admin_bot_prompt(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: UserClaims = Depends(get_admin_user),
) -> AdminBotPromptResponse:
    _ = admin
    return await _load_admin_bot_prompt(db, tenant_id)


@router.put("/admin/tenants/{tenant_id}/bot-prompt", response_model=AdminBotPromptResponse)
async def update_admin_bot_prompt(
    tenant_id: uuid.UUID,
    payload: AdminBotPromptUpdate,
    db: AsyncSession = Depends(get_db),
    admin: UserClaims = Depends(get_admin_user),
) -> AdminBotPromptResponse:
    _ = admin
    return await _upsert_admin_bot_prompt(db, tenant_id, payload)


async def _load_admin_bot_prompt(db: AsyncSession, tenant_id: uuid.UUID) -> AdminBotPromptResponse:
    result = await db.execute(
        text(
            """
            select
                c.id,
                c.instagram_username as username,
                c.display_name,
                p.id as prompt_id,
                coalesce(p.title, 'CRM prompt') as title,
                coalesce(p.prompt_text, :default_prompt) as prompt_text,
                p.version
            from instagram_companies c
            left join lateral (
                select id, title, prompt_text, version, updated_at
                from instagram_system_prompts
                where company_id = c.id
                order by version desc, updated_at desc
                limit 1
            ) p on true
            where c.id = :tenant_id
            limit 1
            """
        ),
        {"tenant_id": tenant_id, "default_prompt": DEFAULT_SYSTEM_PROMPT},
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Client space not found")

    return AdminBotPromptResponse(
        tenant_id=str(row["id"]),
        company_name=str(row["display_name"] or row["username"] or row["id"]),
        username=str(row["username"]) if row.get("username") else None,
        title=str(row["title"]),
        system_prompt=str(row["prompt_text"]),
        version=int(row["version"] or 1),
    )


async def _upsert_admin_bot_prompt(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    payload: AdminBotPromptUpdate,
) -> AdminBotPromptResponse:
    now = _now()
    company_result = await db.execute(
        text(
            """
            select id
            from instagram_companies
            where id = :id
            limit 1
            """
        ),
        {"id": tenant_id},
    )
    company = company_result.mappings().first()
    if not company:
        raise HTTPException(status_code=404, detail="Client space not found")

    prompt_result = await db.execute(
        text(
            """
            select id
            from instagram_system_prompts
            where company_id = :company_id
            order by version desc, updated_at desc
            limit 1
            """
        ),
        {"company_id": tenant_id},
    )
    existing_prompt = prompt_result.mappings().first()

    title = payload.title.strip() if payload.title else "CRM prompt"
    prompt_text = payload.system_prompt.strip()

    if existing_prompt:
        await db.execute(
            text(
                """
                update instagram_system_prompts
                set title = :title,
                    prompt_text = :prompt_text,
                    version = version + 1,
                    updated_at = :now
                where id = :prompt_id
                """
            ),
            {
                "prompt_id": existing_prompt["id"],
                "title": title,
                "prompt_text": prompt_text,
                "now": now,
            },
        )
    else:
        await db.execute(
            text(
                """
                insert into instagram_system_prompts (
                    id, company_id, title, prompt_text, version, created_at, updated_at
                ) values (
                    :id, :company_id, :title, :prompt_text, 1, :now, :now
                )
                """
            ),
            {
                "id": uuid.uuid4(),
                "company_id": tenant_id,
                "title": title,
                "prompt_text": prompt_text,
                "now": now,
            },
        )

    await db.execute(
        text("update instagram_companies set updated_at = :now where id = :id"),
        {"id": tenant_id, "now": now},
    )
    await db.commit()
    return await _load_admin_bot_prompt(db, tenant_id)


@router.get("/tenants/{tenant_id}/business-settings", response_model=BusinessSettingsResponse)
async def get_business_settings(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> BusinessSettingsResponse:
    _assert_company_access(tenant_id, user)
    return _business_settings_response(tenant_id, await _load_business_settings(db, tenant_id))


@router.put("/tenants/{tenant_id}/business-settings", response_model=BusinessSettingsResponse)
async def update_business_settings(
    tenant_id: uuid.UUID,
    payload: BusinessSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> BusinessSettingsResponse:
    _assert_company_access(tenant_id, user)
    if user.role != "company_user":
        raise HTTPException(status_code=403, detail="Only business users can edit business preferences")
    await ensure_company_exists(db, tenant_id)

    business_type = normalize_business_type(payload.business_type)
    features = feature_set_for(business_type)
    discount_percent = money(payload.default_discount_percent)
    if discount_percent < Decimal("0") or discount_percent > Decimal("100"):
        raise HTTPException(status_code=400, detail="Default discount percent must be between 0 and 100")

    shelf_life = payload.default_shelf_life_hours or features.default_shelf_life_hours
    discount_after = payload.default_discount_after_hours or features.default_discount_after_hours
    auto_discount_enabled = payload.auto_discount_enabled and features.supports_perishable_inventory

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
            "company_id": tenant_id,
            "business_type": business_type,
            "features": json.dumps({
                "supports_perishable_inventory": features.supports_perishable_inventory,
                "supports_custom_visual_requests": features.supports_custom_visual_requests,
                "custom_item_label": features.custom_item_label,
            }, ensure_ascii=False),
            "shelf_life": shelf_life,
            "discount_after": discount_after,
            "discount_percent": discount_percent,
            "auto_discount_enabled": auto_discount_enabled,
            "now": _now(),
        },
    )
    await db.commit()

    return _business_settings_response(tenant_id, await _load_business_settings(db, tenant_id))


@router.get("/tenants/{tenant_id}/automation-settings", response_model=AutomationSettingsResponse)
async def get_automation_settings(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> AutomationSettingsResponse:
    _assert_company_access(tenant_id, user)
    await ensure_company_exists(db, tenant_id)
    return AutomationSettingsResponse(**await load_automation_settings(db, tenant_id))


@router.put("/tenants/{tenant_id}/automation-settings", response_model=AutomationSettingsResponse)
async def update_automation_settings(
    tenant_id: uuid.UUID,
    payload: AutomationSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> AutomationSettingsResponse:
    _assert_company_access(tenant_id, user)
    if user.role != "company_user":
        raise HTTPException(status_code=403, detail="Only business users can edit automation settings")
    await ensure_company_exists(db, tenant_id)
    return AutomationSettingsResponse(**await upsert_automation_settings(db, tenant_id, payload.model_dump()))


@router.get("/tenants/{tenant_id}/social-connections", response_model=list[SocialPostingConnectionResponse])
async def get_social_connections(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> list[SocialPostingConnectionResponse]:
    _assert_company_access(tenant_id, user)
    return [SocialPostingConnectionResponse(**row) for row in await list_social_connections(db, tenant_id)]


@router.get("/tenants/{tenant_id}/calendar-events", response_model=list[CalendarEventResponse])
async def get_calendar_events(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> list[CalendarEventResponse]:
    _assert_company_access(tenant_id, user)
    return [CalendarEventResponse(**row) for row in await list_calendar_events(db, tenant_id)]


@router.post("/tenants/{tenant_id}/calendar-events", response_model=CalendarEventResponse)
async def add_calendar_event(
    tenant_id: uuid.UUID,
    payload: CalendarEventCreate,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> CalendarEventResponse:
    _assert_company_access(tenant_id, user)
    if user.role != "company_user":
        raise HTTPException(status_code=403, detail="Only business users can edit calendar events")
    await ensure_company_exists(db, tenant_id)
    try:
        row = await create_calendar_event(db, tenant_id, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CalendarEventResponse(**row)


@router.get("/tenants/{tenant_id}/contacts", response_model=list[ContactResponse])
async def get_contacts(
    tenant_id: uuid.UUID,
    q: str | None = Query(default=None, max_length=255),
    segment: Literal["all", "lead", "customer", "hot"] = "all",
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> list[ContactResponse]:
    _assert_company_access(tenant_id, user)
    search = f"%{q.strip().lower()}%" if q and q.strip() else None
    result = await db.execute(
        text(
            """
            with base_contacts as (
                select
                    c.id::text as id,
                    c.company_id,
                    'instagram'::text as channel,
                    c.customer_instagram_id::text as external_id,
                    coalesce(c.customer_username, c.customer_instagram_id)::text as display_name,
                    c.customer_username::text as username,
                    null::text as phone,
                    c.last_message_at,
                    c.last_user_message_at,
                    c.created_at
                from instagram_conversations c
                where c.company_id = :tenant_id

                union all

                select
                    c.id::text as id,
                    c.company_id,
                    'whatsapp'::text as channel,
                    c.customer_whatsapp_id::text as external_id,
                    coalesce(c.customer_name, c.customer_phone, c.customer_whatsapp_id)::text as display_name,
                    null::text as username,
                    c.customer_phone::text as phone,
                    c.last_message_at,
                    c.last_user_message_at,
                    c.created_at
                from whatsapp_conversations c
                where c.company_id = :tenant_id

                union all

                select
                    c.id::text as id,
                    c.company_id,
                    'whatsapp'::text as channel,
                    c.customer_whatsapp_id::text as external_id,
                    coalesce(c.customer_name, c.customer_phone, c.customer_whatsapp_id)::text as display_name,
                    null::text as username,
                    c.customer_phone::text as phone,
                    c.last_message_at,
                    c.last_user_message_at,
                    c.created_at
                from whatsapp_cloud_conversations c
                where c.company_id = :tenant_id
            ), order_stats as (
                select
                    channel,
                    customer_id::text as external_id,
                    count(*)::int as orders_count,
                    coalesce(sum(coalesce(revenue_amount, 0)), 0)::numeric as total_revenue
                from customer_orders
                where company_id = :tenant_id
                group by channel, customer_id
            )
            select
                b.*,
                coalesce(o.orders_count, 0) as orders_count,
                coalesce(o.total_revenue, 0) as total_revenue,
                case
                    when coalesce(o.orders_count, 0) > 0 then 'customer'
                    when b.last_user_message_at is not null and b.last_user_message_at >= now() - interval '7 days' then 'hot'
                    else 'lead'
                end as segment
            from base_contacts b
            left join order_stats o on o.channel = b.channel and o.external_id = b.external_id
            where (cast(:search as text) is null or lower(coalesce(b.display_name, '') || ' ' || coalesce(b.username, '') || ' ' || coalesce(b.phone, '') || ' ' || b.external_id) like cast(:search as text))
              and (
                cast(:segment as text) = 'all'
                or cast(:segment as text) = case
                    when coalesce(o.orders_count, 0) > 0 then 'customer'
                    when b.last_user_message_at is not null and b.last_user_message_at >= now() - interval '7 days' then 'hot'
                    else 'lead'
                end
              )
            order by b.last_message_at desc nulls last, b.created_at desc
            limit 300
            """
        ),
        {"tenant_id": tenant_id, "search": search, "segment": segment},
    )
    return [
        ContactResponse(
            id=str(row["id"]),
            company_id=str(row["company_id"]),
            channel=cast(Any, row["channel"]),
            external_id=str(row["external_id"]),
            display_name=str(row["display_name"]) if row.get("display_name") else None,
            username=str(row["username"]) if row.get("username") else None,
            phone=str(row["phone"]) if row.get("phone") else None,
            segment=str(row["segment"]),
            last_message_at=cast(datetime | None, row.get("last_message_at")),
            last_user_message_at=cast(datetime | None, row.get("last_user_message_at")),
            orders_count=int(cast(Any, row.get("orders_count") or 0)),
            total_revenue=_decimal_text(row.get("total_revenue") or 0),
            created_at=cast(datetime | None, row.get("created_at")),
        )
        for row in result.mappings().all()
    ]


@router.get("/tenants/{tenant_id}/social-posts", response_model=list[SocialPostDraftResponse])
async def get_social_post_drafts(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> list[SocialPostDraftResponse]:
    _assert_company_access(tenant_id, user)
    await require_autoposting(db, tenant_id)
    return [SocialPostDraftResponse(**row) for row in await list_social_post_drafts(db, tenant_id)]


@router.post("/tenants/{tenant_id}/social-posts", response_model=SocialPostDraftResponse)
async def add_social_post_draft(
    tenant_id: uuid.UUID,
    payload: SocialPostDraftCreate,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> SocialPostDraftResponse:
    _assert_company_access(tenant_id, user)
    await require_autoposting(db, tenant_id)
    if user.role != "company_user":
        raise HTTPException(status_code=403, detail="Only business users can create posts")
    try:
        row = await create_social_post_draft(db, tenant_id, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Zernio scheduled post creation failed") from exc
    return SocialPostDraftResponse(**row)


@router.post("/tenants/{tenant_id}/social-posts/media", response_model=SocialPostMediaUploadResponse)
async def upload_social_post_media(
    tenant_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> SocialPostMediaUploadResponse:
    _assert_company_access(tenant_id, user)
    await require_autoposting(db, tenant_id)
    if user.role != "company_user":
        raise HTTPException(status_code=403, detail="Only business users can upload post media")
    if not file.content_type or not (file.content_type.startswith("image/") or file.content_type.startswith("video/")):
        raise HTTPException(status_code=400, detail="Only image and video uploads are supported")
    content = await file.read()
    if len(content) > 100 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Media file is too large; max 100MB")
    extension = Path(file.filename or "post-media").suffix.lower()
    if extension not in {".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov", ".webm"}:
        extension = ".mp4" if file.content_type.startswith("video/") else ".jpg"
    storage_config = config_from_settings(settings)
    try:
        url = upload_bytes_to_object_storage(
            config=storage_config,
            key=build_object_key(company_id=tenant_id, folder="social-posts", filename=f"{Path(file.filename or 'post-media').stem}{extension}"),
            content=content,
            content_type=file.content_type,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return SocialPostMediaUploadResponse(url=url, content_type=file.content_type, filename=file.filename or f"post-media{extension}")


@router.post("/tenants/{tenant_id}/social-posts/{post_id}/publish", response_model=SocialPostDraftResponse)
async def publish_social_post(
    tenant_id: uuid.UUID,
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> SocialPostDraftResponse:
    _assert_company_access(tenant_id, user)
    await require_autoposting(db, tenant_id)
    if user.role != "company_user":
        raise HTTPException(status_code=403, detail="Only business users can publish posts")
    try:
        row = await publish_social_post_draft(db, tenant_id, post_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Zernio post publishing failed") from exc
    return SocialPostDraftResponse(**row)


@router.post("/tenants/{tenant_id}/social-posts/{post_id}/schedule", response_model=SocialPostDraftResponse)
async def schedule_social_post(
    tenant_id: uuid.UUID,
    post_id: uuid.UUID,
    payload: SocialPostScheduleRequest,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> SocialPostDraftResponse:
    _assert_company_access(tenant_id, user)
    await require_autoposting(db, tenant_id)
    if user.role != "company_user":
        raise HTTPException(status_code=403, detail="Only business users can schedule posts")
    try:
        row = await schedule_social_post_draft(db, tenant_id, post_id, payload.scheduled_for)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Zernio scheduled post creation failed") from exc
    return SocialPostDraftResponse(**row)


@router.post("/tenants/{tenant_id}/social-posts/{post_id}/reject", response_model=SocialPostDraftResponse)
async def reject_social_post(
    tenant_id: uuid.UUID,
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> SocialPostDraftResponse:
    _assert_company_access(tenant_id, user)
    await require_autoposting(db, tenant_id)
    if user.role != "company_user":
        raise HTTPException(status_code=403, detail="Only business users can reject posts")
    try:
        row = await reject_social_post_draft(db, tenant_id, post_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SocialPostDraftResponse(**row)


@router.delete("/tenants/{tenant_id}/social-posts/{post_id}", status_code=204)
async def delete_social_post(
    tenant_id: uuid.UUID,
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> None:
    _assert_company_access(tenant_id, user)
    await require_autoposting(db, tenant_id)
    if user.role != "company_user":
        raise HTTPException(status_code=403, detail="Only business users can delete posts")
    try:
        await delete_social_post_draft(db, tenant_id, post_id)
    except ValueError as exc:
        message = str(exc)
        if "not found" in message.lower():
            raise HTTPException(status_code=404, detail=message) from exc
        raise HTTPException(status_code=400, detail=message) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Zernio post deletion failed") from exc


@router.get("/tenants/{tenant_id}/inventory", response_model=list[InventoryItemResponse])
async def list_inventory_items(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> list[InventoryItemResponse]:
    _assert_company_access(tenant_id, user)
    result = await db.execute(
        text(
            """
            select *
            from product_inventory_items
            where company_id = :tenant_id
              and status <> 'archived'
            order by received_at desc, created_at desc
            """
        ),
        {"tenant_id": tenant_id},
    )
    return [
        InventoryItemResponse(
            id=str(row["id"]),
            company_id=str(row["company_id"]),
            title=str(row["title"]),
            category=str(row["category"]) if row.get("category") else None,
            quantity=int(cast(Any, row["quantity"] or 0)),
            unit_cost=_decimal_text(row.get("unit_cost")),
            original_price=_decimal_text(row.get("original_price")),
            effective_price=_decimal_text(row.get("effective_price")),
            discount_percent=_decimal_text(row.get("discount_percent")),
            shelf_life_hours=cast(int | None, row.get("shelf_life_hours")),
            discount_after_hours=cast(int | None, row.get("discount_after_hours")),
            status=str(row["status"]),
            received_at=cast(datetime, row["received_at"]),
            created_at=cast(datetime, row["created_at"]),
            updated_at=cast(datetime, row["updated_at"]),
        )
        for row in result.mappings().all()
    ]


@router.post("/tenants/{tenant_id}/inventory", status_code=201, response_model=InventoryItemResponse)
async def create_inventory_item(
    tenant_id: uuid.UUID,
    payload: InventoryItemCreate,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> InventoryItemResponse:
    _assert_company_access(tenant_id, user)
    settings_row = await _load_business_settings(db, tenant_id)
    features = feature_set_for(str(settings_row.get("business_type") or "other"))
    if not features.supports_perishable_inventory:
        raise HTTPException(status_code=400, detail="This business type does not support perishable inventory automation")

    now = _now()
    shelf_life = payload.shelf_life_hours or cast(int | None, settings_row.get("default_shelf_life_hours"))
    discount_after = payload.discount_after_hours or cast(int | None, settings_row.get("default_discount_after_hours"))
    discount_percent = money(payload.discount_percent if payload.discount_percent is not None else settings_row.get("default_discount_percent"))
    discount = compute_inventory_discount(
        original_price=money(payload.original_price),
        received_at=now,
        shelf_life_hours=shelf_life,
        discount_after_hours=discount_after,
        discount_percent=discount_percent,
        now=now,
    )
    item_id = uuid.uuid4()
    await db.execute(
        text(
            """
            insert into product_inventory_items (
                id, company_id, title, category, quantity, unit_cost, original_price,
                effective_price, discount_percent, shelf_life_hours, discount_after_hours,
                received_at, status, created_at, updated_at
            ) values (
                :id, :company_id, :title, :category, :quantity, :unit_cost, :original_price,
                :effective_price, :discount_percent, :shelf_life_hours, :discount_after_hours,
                :now, :status, :now, :now
            )
            """
        ),
        {
            "id": item_id,
            "company_id": tenant_id,
            "title": payload.title.strip(),
            "category": payload.category.strip() if payload.category else None,
            "quantity": payload.quantity,
            "unit_cost": money(payload.unit_cost),
            "original_price": money(payload.original_price),
            "effective_price": discount.effective_price,
            "discount_percent": discount.discount_percent,
            "shelf_life_hours": shelf_life,
            "discount_after_hours": discount_after,
            "status": discount.status,
            "now": now,
        },
    )
    await db.commit()
    result = await db.execute(
        text("select * from product_inventory_items where id = :id limit 1"),
        {"id": item_id},
    )
    row = result.mappings().one()
    return InventoryItemResponse(
        id=str(row["id"]),
        company_id=str(row["company_id"]),
        title=str(row["title"]),
        category=str(row["category"]) if row.get("category") else None,
        quantity=int(cast(Any, row["quantity"] or 0)),
        unit_cost=_decimal_text(row.get("unit_cost")),
        original_price=_decimal_text(row.get("original_price")),
        effective_price=_decimal_text(row.get("effective_price")),
        discount_percent=_decimal_text(row.get("discount_percent")),
        shelf_life_hours=cast(int | None, row.get("shelf_life_hours")),
        discount_after_hours=cast(int | None, row.get("discount_after_hours")),
        status=str(row["status"]),
        received_at=cast(datetime, row["received_at"]),
        created_at=cast(datetime, row["created_at"]),
        updated_at=cast(datetime, row["updated_at"]),
    )


@router.post("/tenants/{tenant_id}/custom-products", status_code=201, response_model=CustomProductRequestResponse)
async def create_custom_product_request(
    tenant_id: uuid.UUID,
    payload: CustomProductRequestCreate,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> CustomProductRequestResponse:
    _assert_company_access(tenant_id, user)
    settings_row = await _load_business_settings(db, tenant_id)
    business_type = normalize_business_type(str(settings_row.get("business_type") or "other"))
    features = BUSINESS_TYPE_FEATURES[business_type]
    if not features.supports_custom_visual_requests:
        raise HTTPException(status_code=400, detail="This business type does not support custom visual requests")

    now = _now()
    request_id = uuid.uuid4()
    generated_prompt = build_custom_visual_prompt(
        business_type=business_type,
        title=payload.title.strip(),
        description=payload.description.strip(),
        budget=payload.budget,
    )
    generated_image_url = generate_custom_product_preview_image(generated_prompt, tenant_id)
    await db.execute(
        text(
            """
            insert into custom_product_requests (
                id, company_id, business_type, customer_id, channel, title, description,
                budget, generated_prompt, generated_image_url, status, request_payload, created_at, updated_at
            ) values (
                :id, :company_id, :business_type, :customer_id, :channel, :title, :description,
                :budget, :generated_prompt, :generated_image_url, 'preview_ready', cast(:request_payload as jsonb), :now, :now
            )
            """
        ),
        {
            "id": request_id,
            "company_id": tenant_id,
            "business_type": business_type,
            "customer_id": payload.customer_id,
            "channel": payload.channel,
            "title": payload.title.strip(),
            "description": payload.description.strip(),
            "budget": payload.budget,
            "generated_prompt": generated_prompt,
            "generated_image_url": generated_image_url,
            "request_payload": json.dumps(payload.model_dump(), ensure_ascii=False),
            "now": now,
        },
    )
    await db.commit()
    return CustomProductRequestResponse(
        id=str(request_id),
        company_id=str(tenant_id),
        business_type=business_type,
        title=payload.title.strip(),
        description=payload.description.strip(),
        budget=payload.budget,
        generated_prompt=generated_prompt,
        generated_image_url=normalize_public_object_url(
            url=generated_image_url,
            config=config_from_settings(settings),
        ),
        status="preview_ready",
        created_at=now,
        updated_at=now,
    )


@router.get("/admin/tenants/{tenant_id}/comment-prompt", response_model=CommentPromptResponse)
async def get_comment_prompt_settings(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: UserClaims = Depends(get_admin_user),
) -> CommentPromptResponse:
    _ = admin
    prompt = await get_comment_prompt(db, company_id=tenant_id)
    return CommentPromptResponse(
        tenant_id=str(tenant_id),
        title=str(prompt["title"]),
        system_prompt=str(prompt["prompt_text"]),
        version=int(cast(Any, prompt["version"])),
    )


@router.put("/admin/tenants/{tenant_id}/comment-prompt", response_model=CommentPromptResponse)
async def update_comment_prompt_settings(
    tenant_id: uuid.UUID,
    payload: CommentPromptUpdate,
    db: AsyncSession = Depends(get_db),
    admin: UserClaims = Depends(get_admin_user),
) -> CommentPromptResponse:
    _ = admin
    title = payload.title.strip() if payload.title else "Instagram comment prompt"
    await ensure_company_exists(db, tenant_id)
    await db.execute(
        text(
            """
            update instagram_comment_prompts
            set is_active = false, updated_at = now()
            where company_id = :tenant_id and is_active = true
            """
        ),
        {"tenant_id": tenant_id},
    )
    version_result = await db.execute(
        text("select coalesce(max(version), 0) + 1 from instagram_comment_prompts where company_id = :tenant_id"),
        {"tenant_id": tenant_id},
    )
    version = int(version_result.scalar_one() or 1)
    prompt_text = payload.system_prompt.strip()
    await db.execute(
        text(
            """
            insert into instagram_comment_prompts (company_id, title, prompt_text, version, is_active, created_at, updated_at)
            values (:tenant_id, :title, :prompt_text, :version, true, now(), now())
            """
        ),
        {"tenant_id": tenant_id, "title": title, "prompt_text": prompt_text, "version": version},
    )
    await db.commit()
    return CommentPromptResponse(tenant_id=str(tenant_id), title=title, system_prompt=prompt_text, version=version)


@router.get("/tenants/{tenant_id}/comments", response_model=list[CommentThreadResponse])
async def list_instagram_comments(
    tenant_id: uuid.UUID,
    status: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> list[CommentThreadResponse]:
    _assert_company_access(tenant_id, user)
    allowed_statuses = {"new", "suggested", "replied", "ignored", "converted"}
    status_filter = status if status in allowed_statuses else None
    threads_result = await db.execute(
        text(
            """
            select distinct t.*
            from instagram_comment_threads t
            left join instagram_comments c on c.thread_id = t.id
            where t.company_id = :tenant_id
              and (cast(:status_filter as varchar) is null or c.status = cast(:status_filter as varchar))
            order by t.last_comment_at desc nulls last, t.updated_at desc
            limit 100
            """
        ),
        {"tenant_id": tenant_id, "status_filter": status_filter},
    )
    thread_rows = [dict(row) for row in threads_result.mappings().all()]
    if not thread_rows:
        return []
    thread_ids = [row["id"] for row in thread_rows]
    comments_result = await db.execute(
        text(
            """
            select *
            from instagram_comments
            where company_id = :tenant_id and thread_id in :thread_ids
              and (cast(:status_filter as varchar) is null or status = cast(:status_filter as varchar))
            order by created_at desc
            """
        ).bindparams(bindparam("thread_ids", expanding=True)),
        {"tenant_id": tenant_id, "thread_ids": thread_ids, "status_filter": status_filter},
    )
    comments_by_thread: dict[str, list[InstagramCommentResponse]] = {}
    for row in comments_result.mappings().all():
        comment = _comment_row(dict(row))
        comments_by_thread.setdefault(comment.thread_id, []).append(comment)
    return [_thread_row(row, comments_by_thread.get(str(row["id"]), [])) for row in thread_rows]


@router.get("/tenants/{tenant_id}/comments/analytics", response_model=CommentAnalyticsResponse)
async def get_comment_analytics(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> CommentAnalyticsResponse:
    _assert_company_access(tenant_id, user)
    totals_result = await db.execute(
        text(
            """
            select
                count(*)::int as total_comments,
                count(distinct author_id)::int as unique_commenters,
                count(*) filter (where status in ('replied', 'converted'))::int as replied_comments,
                count(*) filter (where status = 'converted')::int as converted_comments,
                count(*) filter (where status in ('new', 'suggested'))::int as pending_comments
            from instagram_comments
            where company_id = :tenant_id
            """
        ),
        {"tenant_id": tenant_id},
    )
    totals = totals_result.mappings().one()
    total_comments = int(cast(Any, totals["total_comments"] or 0))
    converted_comments = int(cast(Any, totals["converted_comments"] or 0))
    commenters_result = await db.execute(
        text(
            """
            select author_id, coalesce(max(nullif(author_username, '')), max(nullif(author_name, '')), author_id) as label,
                   count(*)::int as comments_count,
                   count(*) filter (where status = 'converted')::int as converted_count
            from instagram_comments
            where company_id = :tenant_id
            group by author_id
            order by comments_count desc, converted_count desc
            limit 10
            """
        ),
        {"tenant_id": tenant_id},
    )
    posts_result = await db.execute(
        text(
            """
            select platform_post_id, coalesce(max(nullif(zernio_post_id, '')), platform_post_id) as label,
                   count(*)::int as comments_count,
                   count(*) filter (where status = 'converted')::int as converted_count
            from instagram_comments
            where company_id = :tenant_id
            group by platform_post_id
            order by comments_count desc, converted_count desc
            limit 10
            """
        ),
        {"tenant_id": tenant_id},
    )
    return CommentAnalyticsResponse(
        tenant_id=str(tenant_id),
        total_comments=total_comments,
        unique_commenters=int(cast(Any, totals["unique_commenters"] or 0)),
        replied_comments=int(cast(Any, totals["replied_comments"] or 0)),
        converted_comments=converted_comments,
        pending_comments=int(cast(Any, totals["pending_comments"] or 0)),
        conversion_rate=round((converted_comments / total_comments) * 100, 2) if total_comments else 0.0,
        top_commenters=[
            {
                "author_id": str(row["author_id"]),
                "label": str(row["label"]),
                "comments_count": int(cast(Any, row["comments_count"] or 0)),
                "converted_count": int(cast(Any, row["converted_count"] or 0)),
            }
            for row in commenters_result.mappings().all()
        ],
        top_posts=[
            {
                "platform_post_id": str(row["platform_post_id"]),
                "label": str(row["label"]),
                "comments_count": int(cast(Any, row["comments_count"] or 0)),
                "converted_count": int(cast(Any, row["converted_count"] or 0)),
            }
            for row in posts_result.mappings().all()
        ],
    )


@router.patch("/tenants/{tenant_id}/comments/{comment_id}", response_model=InstagramCommentResponse)
async def update_comment_status(
    tenant_id: uuid.UUID,
    comment_id: uuid.UUID,
    payload: CommentStatusUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> InstagramCommentResponse:
    _assert_company_access(tenant_id, user)
    result = await db.execute(
        text(
            """
            update instagram_comments
            set status = :status_value,
                replied_at = case when :mark_replied then coalesce(replied_at, now()) else replied_at end,
                converted_at = case when :mark_converted then coalesce(converted_at, now()) else null end,
                updated_at = now()
            where company_id = :tenant_id and id = :comment_id
            returning *
            """
        ),
        {
            "tenant_id": tenant_id,
            "comment_id": comment_id,
            "status_value": payload.status,
            "mark_replied": payload.status in {"replied", "converted"},
            "mark_converted": payload.status == "converted",
        },
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Comment not found")
    await db.execute(
        text(
            """
            update instagram_comment_threads t
            set replied_comment_count = stats.replied_comments,
                converted_comment_count = stats.converted_comments,
                updated_at = now()
            from (
                select thread_id,
                       count(*) filter (where status in ('replied', 'converted'))::int as replied_comments,
                       count(*) filter (where status = 'converted')::int as converted_comments
                from instagram_comments
                where thread_id = :thread_id
                group by thread_id
            ) stats
            where t.id = stats.thread_id
            """
        ),
        {"thread_id": row["thread_id"]},
    )
    await db.commit()
    return _comment_row(dict(row))


class CommentPrivateReplyRequest(BaseModel):
    message: str


class AutoReplyToggle(BaseModel):
    enabled: bool


@router.get("/tenants/{tenant_id}/automation-settings/auto-reply")
async def get_auto_reply_settings(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
):
    _assert_company_access(tenant_id, user)
    result = await db.execute(
        text(
            """
            select coalesce(auto_reply_enabled, false) as enabled
            from company_automation_settings
            where company_id = :tenant_id
            limit 1
            """
        ),
        {"tenant_id": tenant_id},
    )
    row = result.mappings().first()
    return {"enabled": bool(row["enabled"]) if row else False}


@router.put("/tenants/{tenant_id}/automation-settings/auto-reply")
async def update_auto_reply_settings(
    tenant_id: uuid.UUID,
    payload: AutoReplyToggle,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
):
    _assert_company_access(tenant_id, user)
    await db.execute(
        text(
            """
            insert into company_automation_settings (company_id, auto_reply_enabled, updated_at)
            values (:tenant_id, :enabled, now())
            on conflict (company_id) do update set
                auto_reply_enabled = excluded.auto_reply_enabled,
                updated_at = now()
            """
        ),
        {"tenant_id": tenant_id, "enabled": payload.enabled},
    )
    await db.commit()
    return {"enabled": payload.enabled}


@router.post("/tenants/{tenant_id}/comments/{comment_id}/private-reply")
async def send_comment_private_reply(
    tenant_id: uuid.UUID,
    comment_id: uuid.UUID,
    payload: CommentPrivateReplyRequest,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
):
    _assert_company_access(tenant_id, user)

    # Fetch comment details + zernio_account_id
    result = await db.execute(
        text(
            """
            select c.platform_comment_id, c.platform_post_id,
                   c.zernio_account_id,
                   t.zernio_post_id
            from instagram_comments c
            join instagram_comment_threads t on t.id = c.thread_id
            where c.company_id = :tenant_id and c.id = :comment_id
            """
        ),
        {"tenant_id": tenant_id, "comment_id": comment_id},
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Comment not found")

    post_id = row["zernio_post_id"] or row["platform_post_id"]
    comment_id_str = row["platform_comment_id"]
    zernio_account_id = row["zernio_account_id"]

    if not zernio_account_id:
        raise HTTPException(status_code=400, detail="Comment has no zernio_account_id")

    # Send private reply via Zernio
    from services.zernio_integrator import IntegratorZernio

    zernio = IntegratorZernio()
    reply_result = await zernio.send_private_reply_to_comment(
        account_id=zernio_account_id,
        post_id=post_id,
        comment_id=comment_id_str,
        message=payload.message,
    )

    # Update comment status to replied
    await db.execute(
        text(
            """
            update instagram_comments
            set status = 'replied',
                replied_at = coalesce(replied_at, now()),
                updated_at = now()
            where company_id = :tenant_id and id = :comment_id
            """
        ),
        {"tenant_id": tenant_id, "comment_id": comment_id},
    )
    await db.commit()

    return {"status": "success", "reply": reply_result}


@router.get("/tenants/{tenant_id}/orders", response_model=list[CustomerOrderResponse])
async def list_customer_orders(
    tenant_id: uuid.UUID,
    status: str | None = Query(default=None),
    from_date: datetime | None = Query(default=None),
    to_date: datetime | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> list[CustomerOrderResponse]:
    _assert_company_access(tenant_id, user)
    allowed_statuses = {"new", "sent_to_manager", "accepted", "paid", "completed", "cancelled", "done"}
    status_filter = status if status in allowed_statuses else None
    result = await db.execute(
        text(
            """
            select *
            from customer_orders
            where company_id = :tenant_id
              and (cast(:status_filter as varchar) is null or status = cast(:status_filter as varchar))
              and (cast(:from_date as timestamptz) is null or created_at >= cast(:from_date as timestamptz))
              and (cast(:to_date as timestamptz) is null or created_at <= cast(:to_date as timestamptz))
            order by created_at desc
            limit :limit offset :offset
            """
        ),
        {
            "tenant_id": tenant_id,
            "status_filter": status_filter,
            "from_date": from_date,
            "to_date": to_date,
            "limit": limit,
            "offset": offset,
        },
    )
    return [_order_row(row) for row in result.mappings().all()]


@router.patch("/tenants/{tenant_id}/orders/{order_id}", response_model=CustomerOrderResponse)
async def update_customer_order(
    tenant_id: uuid.UUID,
    order_id: uuid.UUID,
    payload: CustomerOrderUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> CustomerOrderResponse:
    _assert_company_access(tenant_id, user)
    allowed_statuses = {"new", "sent_to_manager", "accepted", "paid", "completed", "cancelled", "done"}
    status_value = payload.status if payload.status in allowed_statuses else None
    revenue_value = money(payload.revenue_amount) if payload.revenue_amount is not None else None
    cost_value = money(payload.cost_amount) if payload.cost_amount is not None else None

    result = await db.execute(
        text(
            """
            update customer_orders
            set status = coalesce(cast(:status_value as varchar), status),
                revenue_amount = case
                    when cast(:revenue_value as numeric) is not null then cast(:revenue_value as numeric)
                    when cast(:status_value as varchar) in ('paid', 'completed', 'done') and revenue_amount is null then
                        coalesce(nullif(regexp_replace(coalesce(product_price, ''), '[^0-9\.]', '', 'g'), '')::numeric, 0)
                        * greatest(coalesce(quantity, 1), 1)
                    else revenue_amount
                end,
                cost_amount = case when cast(:cost_value as numeric) is not null then cast(:cost_value as numeric) else cost_amount end,
                paid_at = case
                    when cast(:status_value as varchar) in ('paid', 'completed', 'done') then coalesce(paid_at, now())
                    when cast(:status_value as varchar) in ('new', 'sent_to_manager', 'accepted', 'cancelled') then null
                    else paid_at
                end,
                completed_at = case
                    when cast(:status_value as varchar) in ('completed', 'done') then coalesce(completed_at, now())
                    when cast(:status_value as varchar) in ('new', 'sent_to_manager', 'accepted', 'paid', 'cancelled') then null
                    else completed_at
                end,
                cancelled_at = case
                    when cast(:status_value as varchar) = 'cancelled' then coalesce(cancelled_at, now())
                    when cast(:status_value as varchar) in ('new', 'sent_to_manager', 'accepted', 'paid', 'completed', 'done') then null
                    else cancelled_at
                end,
                updated_at = now()
            where id = :order_id and company_id = :tenant_id
            returning *
            """
        ),
        {
            "tenant_id": tenant_id,
            "order_id": order_id,
            "status_value": status_value,
            "revenue_value": revenue_value,
            "cost_value": cost_value,
        },
    )
    row = result.mappings().first()
    if not row:
        await db.rollback()
        raise HTTPException(status_code=404, detail="Order not found")
    await db.commit()
    return _order_row(row)


@router.get("/tenants/{tenant_id}/message-activity", response_model=MessageActivityResponse)
async def get_message_activity(
    tenant_id: uuid.UUID,
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> MessageActivityResponse:
    _assert_company_access(tenant_id, user)
    today = datetime.now(BAKU_TIMEZONE).date()
    selected_to = date_to or today
    selected_from = date_from or (selected_to - timedelta(days=13))
    if selected_from > selected_to:
        raise HTTPException(status_code=422, detail="date_from must not be after date_to")
    if (selected_to - selected_from).days > 89:
        raise HTTPException(status_code=422, detail="Date range cannot exceed 90 days")

    activity = await load_message_activity(
        db,
        tenant_id=tenant_id,
        date_from=selected_from,
        date_to=selected_to,
    )
    return MessageActivityResponse(**activity)


@router.get("/tenants/{tenant_id}/analytics", response_model=BusinessAnalyticsResponse)
async def get_business_analytics(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> BusinessAnalyticsResponse:
    _assert_company_access(tenant_id, user)
    settings = _business_settings_response(tenant_id, await _load_business_settings(db, tenant_id))

    orders_result = await db.execute(
        text(
            """
            select
                customer_id,
                status,
                coalesce(
                    revenue_amount,
                    nullif(regexp_replace(coalesce(product_price, ''), '[^0-9\.]', '', 'g'), '')::numeric * greatest(coalesce(quantity, 1), 1),
                    0
                ) as revenue,
                coalesce(cost_amount, 0) as cost
            from customer_orders
            where company_id = :tenant_id
            """
        ),
        {"tenant_id": tenant_id},
    )
    orders = [dict(row) for row in orders_result.mappings().all()]

    message_counts_result = await db.execute(
        text(
            """
            select
                coalesce(sum(case when direction = 'inbound' then 1 else 0 end), 0) as inbound,
                coalesce(sum(case when direction = 'outbound' then 1 else 0 end), 0) as outbound
            from (
                select direction from instagram_messages where company_id = :tenant_id
                union all
                select direction from whatsapp_messages where company_id = :tenant_id
                union all
                select direction from whatsapp_cloud_messages where company_id = :tenant_id
            ) messages
            """
        ),
        {"tenant_id": tenant_id},
    )
    counts = message_counts_result.mappings().first() or {"inbound": 0, "outbound": 0}

    inventory_result = await db.execute(
        text(
            """
            select
                coalesce(sum(effective_price * quantity), 0) as inventory_value,
                coalesce(sum(case when status in ('discounted', 'expired') then 1 else 0 end), 0) as stale_items,
                coalesce(sum(case when status = 'discounted' then 1 else 0 end), 0) as discounted_items
            from product_inventory_items
            where company_id = :tenant_id
              and status <> 'archived'
            """
        ),
        {"tenant_id": tenant_id},
    )
    inventory = inventory_result.mappings().first() or {}
    custom_requests_result = await db.execute(
        text("select count(*) from custom_product_requests where company_id = :tenant_id"),
        {"tenant_id": tenant_id},
    )
    custom_requests = int(custom_requests_result.scalar_one() or 0)

    top_products_result = await db.execute(
        text(
            """
            select
                coalesce(nullif(product_title, ''), 'Unknown product') as product_title,
                coalesce(sum(greatest(coalesce(quantity, 1), 1)), 0)::int as quantity_sold,
                count(*)::int as orders_count,
                coalesce(sum(coalesce(revenue_amount, nullif(regexp_replace(coalesce(product_price, ''), '[^0-9\\.]', '', 'g'), '')::numeric * greatest(coalesce(quantity, 1), 1), 0)), 0) as revenue
            from customer_orders
            where company_id = :tenant_id
              and status in ('paid', 'completed', 'done')
            group by coalesce(nullif(product_title, ''), 'Unknown product')
            order by quantity_sold desc, revenue desc, orders_count desc
            limit 10
            """
        ),
        {"tenant_id": tenant_id},
    )
    top_products = [
        {
            "product_title": str(row["product_title"]),
            "quantity_sold": int(cast(Any, row["quantity_sold"] or 0)),
            "orders_count": int(cast(Any, row["orders_count"] or 0)),
            "revenue": _decimal_text(row.get("revenue")),
        }
        for row in top_products_result.mappings().all()
    ]

    top_customers_result = await db.execute(
        text(
            """
            with order_stats as (
                select
                    customer_id,
                    coalesce(max(nullif(customer_name, '')), max(nullif(customer_phone, '')), customer_id) as customer_label,
                    count(*)::int as orders_count,
                    coalesce(sum(greatest(coalesce(quantity, 1), 1)), 0)::int as items_count,
                    coalesce(sum(coalesce(revenue_amount, nullif(regexp_replace(coalesce(product_price, ''), '[^0-9\\.]', '', 'g'), '')::numeric * greatest(coalesce(quantity, 1), 1), 0)), 0) as revenue
                from customer_orders
                where company_id = :tenant_id
                group by customer_id
            ), message_stats as (
                select customer_id, max(customer_label) as customer_label, count(*)::int as message_count
                from (
                    select c.customer_instagram_id::text as customer_id, coalesce(c.customer_username, c.customer_instagram_id::text) as customer_label
                    from instagram_messages m
                    join instagram_conversations c on c.id = m.conversation_id
                    where m.company_id = :tenant_id and m.direction = 'inbound'
                    union all
                    select c.customer_whatsapp_id::text as customer_id, coalesce(c.customer_name, c.customer_phone, c.customer_whatsapp_id::text) as customer_label
                    from whatsapp_cloud_messages m
                    join whatsapp_cloud_conversations c on c.id = m.conversation_id
                    where m.company_id = :tenant_id and m.direction = 'inbound'
                    union all
                    select c.customer_whatsapp_id::text as customer_id, coalesce(c.customer_name, c.customer_phone, c.customer_whatsapp_id::text) as customer_label
                    from whatsapp_messages m
                    join whatsapp_conversations c on c.id = m.conversation_id
                    where m.company_id = :tenant_id and m.direction = 'inbound'
                ) messages
                group by customer_id
            )
            select
                coalesce(o.customer_id, m.customer_id) as customer_id,
                coalesce(o.customer_label, m.customer_label, o.customer_id, m.customer_id) as customer_label,
                coalesce(o.orders_count, 0)::int as orders_count,
                coalesce(o.items_count, 0)::int as items_count,
                coalesce(m.message_count, 0)::int as message_count,
                coalesce(o.revenue, 0) as revenue
            from order_stats o
            full join message_stats m on m.customer_id = o.customer_id
            order by coalesce(m.message_count, 0) desc, coalesce(o.orders_count, 0) desc, coalesce(o.revenue, 0) desc
            limit 10
            """
        ),
        {"tenant_id": tenant_id},
    )
    top_customers = [
        {
            "customer_id": str(row["customer_id"]),
            "customer_label": str(row["customer_label"] or row["customer_id"]),
            "orders_count": int(cast(Any, row["orders_count"] or 0)),
            "items_count": int(cast(Any, row["items_count"] or 0)),
            "message_count": int(cast(Any, row["message_count"] or 0)),
            "revenue": _decimal_text(row.get("revenue")),
        }
        for row in top_customers_result.mappings().all()
    ]

    from services.business_features import summarize_business_metrics

    summary = summarize_business_metrics(
        orders=orders,
        inbound_messages=int(cast(Any, counts.get("inbound") or 0)),
        outbound_messages=int(cast(Any, counts.get("outbound") or 0)),
        inventory_value=inventory.get("inventory_value") or 0,
    )
    conversion_rate = round(summary.completed_orders / summary.total_orders * 100, 2) if summary.total_orders else 0.0
    return BusinessAnalyticsResponse(
        tenant_id=str(tenant_id),
        business_type=settings.business_type,
        business_type_label=settings.business_type_label,
        total_orders=summary.total_orders,
        completed_orders=summary.completed_orders,
        gross_revenue=_decimal_text(summary.gross_revenue),
        total_costs=_decimal_text(summary.total_costs),
        net_profit=_decimal_text(summary.net_profit),
        unique_customers=summary.unique_customers,
        repeat_customers=summary.repeat_customers,
        inbound_messages=summary.inbound_messages,
        outbound_messages=summary.outbound_messages,
        inventory_value=_decimal_text(summary.inventory_value),
        stale_inventory_items=int(cast(Any, inventory.get("stale_items") or 0)),
        discounted_inventory_items=int(cast(Any, inventory.get("discounted_items") or 0)),
        custom_requests=custom_requests,
        conversion_rate=conversion_rate,
        top_products=top_products,
        top_customers=top_customers,
    )


@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    tenant_id: uuid.UUID = Query(...),
    from_date: datetime | None = Query(default=None),
    to_date: datetime | None = Query(default=None),
    customer: str | None = Query(default=None, max_length=255),
    channel: Literal["all", "instagram", "whatsapp"] = Query(default="all"),
    db: AsyncSession = Depends(get_db),
) -> list[ConversationResponse]:
    params: dict[str, object] = {
        "tenant_id": tenant_id,
    }

    instagram_filters = ["company_id = :tenant_id"]
    whatsapp_filters = ["company_id = :tenant_id"]

    if from_date is not None:
        instagram_filters.append("coalesce(last_message_at, created_at) >= :from_date")
        whatsapp_filters.append("coalesce(last_message_at, created_at) >= :from_date")
        params["from_date"] = from_date

    if to_date is not None:
        instagram_filters.append("coalesce(last_message_at, created_at) <= :to_date")
        whatsapp_filters.append("coalesce(last_message_at, created_at) <= :to_date")
        params["to_date"] = to_date

    customer_search = customer.strip() if customer else ""

    if customer_search:
        instagram_filters.append(
            """
            (
                customer_instagram_id::text ilike :customer
                or coalesce(customer_username, '') ilike :customer
            )
            """
        )

        whatsapp_filters.append(
            """
            (
                customer_whatsapp_id::text ilike :customer
                or coalesce(customer_name, '') ilike :customer
                or coalesce(customer_phone, '') ilike :customer
            )
            """
        )

        params["customer"] = f"%{customer_search}%"

    conversation_parts: list[str] = []

    if channel in ("all", "instagram"):
        conversation_parts.append(
            f"""
            select
                'instagram'::varchar as channel,
                id,
                company_id,
                customer_instagram_id::text as external_conversation_id,
                customer_instagram_id::text as customer_instagram_id,
                null::text as customer_whatsapp_id,
                customer_username::text as customer_username,
                customer_username::text as customer_name,
                null::text as customer_phone,
                last_message_at,
                created_at,
                mode,
                assigned_manager_id,
                bot_paused_at,
                bot_paused_reason,
                last_user_message_at,
                messaging_window_expires_at,
                last_manager_message_at,
                last_bot_message_at,
                status,
                priority
            from instagram_conversations
            where {" and ".join(instagram_filters)}
            """
        )

    if channel in ("all", "whatsapp"):
        whatsapp_where = " and ".join(whatsapp_filters)
        conversation_parts.append(
            f"""
            select
                'whatsapp'::varchar as channel,
                id,
                company_id,
                customer_whatsapp_id::text as external_conversation_id,
                null::text as customer_instagram_id,
                customer_whatsapp_id::text as customer_whatsapp_id,
                null::text as customer_username,
                customer_name::text as customer_name,
                customer_phone::text as customer_phone,
                last_message_at,
                created_at,
                mode,
                assigned_manager_id,
                bot_paused_at,
                bot_paused_reason,
                last_user_message_at,
                messaging_window_expires_at,
                last_manager_message_at,
                last_bot_message_at,
                status,
                priority
            from whatsapp_cloud_conversations
            where {whatsapp_where}

            union all

            select
                'whatsapp'::varchar as channel,
                id,
                company_id,
                customer_whatsapp_id::text as external_conversation_id,
                null::text as customer_instagram_id,
                customer_whatsapp_id::text as customer_whatsapp_id,
                null::text as customer_username,
                customer_name::text as customer_name,
                customer_phone::text as customer_phone,
                last_message_at,
                created_at,
                mode,
                assigned_manager_id,
                bot_paused_at,
                bot_paused_reason,
                last_user_message_at,
                messaging_window_expires_at,
                last_manager_message_at,
                last_bot_message_at,
                status,
                priority
            from whatsapp_conversations
            where {whatsapp_where}
            """
        )

    conversations_sql = f"""
        select *
        from (
            {" union all ".join(conversation_parts)}
        ) conversations
        order by last_message_at desc nulls last, created_at desc
        limit 200
    """

    conversations_result = await db.execute(
        text(conversations_sql),
        params,
    )

    conversations = conversations_result.mappings().all()

    if not conversations:
        return []

    instagram_ids = [
        conversation["id"]
        for conversation in conversations
        if conversation["channel"] == "instagram"
    ]

    whatsapp_ids = [
        conversation["id"]
        for conversation in conversations
        if conversation["channel"] == "whatsapp"
    ]

    messages_by_conversation: dict[str, list[MessageResponse]] = {}

    if instagram_ids:
        instagram_messages_query = text(
            """
            select
                id,
                conversation_id,
                company_id,
                coalesce(external_message_id, instagram_mid) as external_message_id,
                direction,
                coalesce(sender_type, case when direction = 'inbound' then 'customer' else 'bot' end) as sender_type,
                manager_id,
                message_text,
                delivery_status,
                intent,
                intent_confidence,
                created_at
            from instagram_messages
            where company_id = :tenant_id
              and conversation_id in :conversation_ids
            order by created_at asc
            """
        ).bindparams(bindparam("conversation_ids", expanding=True))

        messages_result = await db.execute(
            instagram_messages_query,
            {
                "tenant_id": tenant_id,
                "conversation_ids": instagram_ids,
            },
        )

        for message in messages_result.mappings().all():
            conversation_id = str(message["conversation_id"])

            direction = str(message["direction"] or "inbound")
            if direction not in {"inbound", "outbound"}:
                direction = "inbound"

            messages_by_conversation.setdefault(conversation_id, []).append(
                MessageResponse(
                    id=str(message["id"]),
                    tenant_id=str(message["company_id"]),
                    channel="instagram",
                    direction=cast(Literal["inbound", "outbound"], direction),
                    sender_type=cast(Any, message.get("sender_type")),
                    manager_id=str(message["manager_id"]) if message.get("manager_id") else None,
                    text=str(message["message_text"] or ""),
                    status=str(message.get("delivery_status") or "sent"),
                    external_message_id=str(message["external_message_id"] or message["id"]),
                    intent=str(message["intent"]) if message.get("intent") else None,
                    intent_confidence=float(cast(Any, message["intent_confidence"])) if message.get("intent_confidence") is not None else None,
                    created_at=cast(datetime, message["created_at"]),
                )
            )

    if whatsapp_ids:
        whatsapp_messages_query = text(
            """
            select
                id,
                conversation_id,
                company_id,
                coalesce(external_message_id, whatsapp_mid) as external_message_id,
                direction,
                coalesce(sender_type, case when direction = 'inbound' then 'customer' else 'bot' end) as sender_type,
                manager_id,
                message_text,
                delivery_status,
                intent,
                intent_confidence,
                created_at
            from whatsapp_cloud_messages
            where company_id = :tenant_id
              and conversation_id in :conversation_ids

            union all

            select
                id,
                conversation_id,
                company_id,
                coalesce(external_message_id, whatsapp_mid) as external_message_id,
                direction,
                coalesce(sender_type, case when direction = 'inbound' then 'customer' else 'bot' end) as sender_type,
                manager_id,
                message_text,
                delivery_status,
                intent,
                intent_confidence,
                created_at
            from whatsapp_messages
            where company_id = :tenant_id
              and conversation_id in :conversation_ids

            order by created_at asc
            """
        ).bindparams(bindparam("conversation_ids", expanding=True))

        messages_result = await db.execute(
            whatsapp_messages_query,
            {
                "tenant_id": tenant_id,
                "conversation_ids": whatsapp_ids,
            },
        )

        for message in messages_result.mappings().all():
            conversation_id = str(message["conversation_id"])

            direction = str(message["direction"] or "inbound")
            if direction not in {"inbound", "outbound"}:
                direction = "inbound"

            messages_by_conversation.setdefault(conversation_id, []).append(
                MessageResponse(
                    id=str(message["id"]),
                    tenant_id=str(message["company_id"]),
                    channel="whatsapp",
                    direction=cast(Literal["inbound", "outbound"], direction),
                    sender_type=cast(Any, message.get("sender_type")),
                    manager_id=str(message["manager_id"]) if message.get("manager_id") else None,
                    text=str(message["message_text"] or ""),
                    status=str(message.get("delivery_status") or "sent"),
                    external_message_id=str(message["external_message_id"] or message["id"]),
                    intent=str(message["intent"]) if message.get("intent") else None,
                    intent_confidence=float(cast(Any, message["intent_confidence"])) if message.get("intent_confidence") is not None else None,
                    created_at=cast(datetime, message["created_at"]),
                )
            )

    response: list[ConversationResponse] = []

    for conversation in conversations:
        conversation_id = str(conversation["id"])
        conversation_channel = str(conversation["channel"])

        response.append(
            ConversationResponse(
                id=conversation_id,
                tenant_id=str(conversation["company_id"]),
                channel=cast(Literal["instagram", "whatsapp"], conversation_channel),
                external_conversation_id=str(conversation["external_conversation_id"]),
                customer_instagram_id=(
                    str(conversation["customer_instagram_id"])
                    if conversation.get("customer_instagram_id")
                    else None
                ),
                customer_whatsapp_id=(
                    str(conversation["customer_whatsapp_id"])
                    if conversation.get("customer_whatsapp_id")
                    else None
                ),
                customer_username=(
                    str(conversation["customer_username"])
                    if conversation.get("customer_username")
                    else None
                ),
                customer_phone=(
                    str(conversation["customer_phone"])
                    if conversation.get("customer_phone")
                    else None
                ),
                status=str(conversation.get("status") or "open"),
                mode=cast(Any, conversation.get("mode") or "bot"),
                assigned_manager_id=str(conversation["assigned_manager_id"]) if conversation.get("assigned_manager_id") else None,
                bot_paused_at=cast(datetime | None, conversation.get("bot_paused_at")),
                bot_paused_reason=str(conversation["bot_paused_reason"]) if conversation.get("bot_paused_reason") else None,
                last_user_message_at=cast(datetime | None, conversation.get("last_user_message_at")),
                messaging_window_expires_at=cast(datetime | None, conversation.get("messaging_window_expires_at")),
                last_manager_message_at=cast(datetime | None, conversation.get("last_manager_message_at")),
                last_bot_message_at=cast(datetime | None, conversation.get("last_bot_message_at")),
                priority=str(conversation.get("priority") or "normal"),
                last_message_at=cast(datetime | None, conversation["last_message_at"]),
                created_at=cast(datetime, conversation["created_at"]),
                messages=messages_by_conversation.get(conversation_id, []),
            )
        )

    return response


def _conversation_action_response(channel: Literal["instagram", "whatsapp"], row: Mapping[str, Any]) -> ConversationActionResponse:
    return ConversationActionResponse(
        id=str(row["id"]),
        tenant_id=str(row["company_id"]),
        channel=channel,
        mode=cast(Any, row["mode"]),
        assigned_manager_id=str(row["assigned_manager_id"]) if row.get("assigned_manager_id") else None,
        bot_paused_at=cast(datetime | None, row.get("bot_paused_at")),
        bot_paused_reason=str(row["bot_paused_reason"]) if row.get("bot_paused_reason") else None,
        messaging_window_expires_at=cast(datetime | None, row.get("messaging_window_expires_at")),
        status=str(row["status"]),
        priority=str(row["priority"]),
    )


def _zernio_context_from_payload(payload: Mapping[str, Any]) -> tuple[str | None, str | None]:
    account = payload.get("account") if isinstance(payload.get("account"), Mapping) else {}
    message = payload.get("message") if isinstance(payload.get("message"), Mapping) else {}
    conversation = payload.get("conversation") if isinstance(payload.get("conversation"), Mapping) else {}

    account_id = str(account.get("id") or "").strip() if isinstance(account, Mapping) else ""
    conversation_id = str(
        message.get("conversationId")
        or conversation.get("id")
        or ""
    ).strip() if isinstance(message, Mapping) and isinstance(conversation, Mapping) else ""

    return account_id or None, conversation_id or None


async def _load_zernio_manual_send_context(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    channel: Literal["instagram", "whatsapp"],
    conversation_id: uuid.UUID,
) -> Mapping[str, Any]:
    if channel == "instagram":
        result = await db.execute(
            text(
                """
                select
                    c.id,
                    c.company_id,
                    c.customer_instagram_id::text as customer_id,
                    c.customer_username::text as customer_name,
                    null::text as customer_phone,
                    c.mode,
                    c.status,
                    c.priority,
                    c.assigned_manager_id,
                    c.bot_paused_at,
                    c.bot_paused_reason,
                    c.messaging_window_expires_at,
                    m.message_payload
                from instagram_conversations c
                left join lateral (
                    select message_payload
                    from instagram_messages
                    where conversation_id = c.id
                      and message_payload is not null
                      and message_payload ? 'account'
                      and nullif(message_payload #>> '{account,id}', '') is not null
                      and nullif(coalesce(message_payload #>> '{message,conversationId}', message_payload #>> '{conversation,id}'), '') is not null
                    order by created_at desc
                    limit 1
                ) m on true
                where c.id = :conversation_id and c.company_id = :tenant_id
                limit 1
                """
            ),
            {"conversation_id": conversation_id, "tenant_id": tenant_id},
        )
    else:
        result = await db.execute(
            text(
                """
                select
                    c.id,
                    c.company_id,
                    c.customer_whatsapp_id::text as customer_id,
                    coalesce(c.customer_name, c.customer_phone, c.customer_whatsapp_id)::text as customer_name,
                    c.customer_phone::text as customer_phone,
                    c.mode,
                    c.status,
                    c.priority,
                    c.assigned_manager_id,
                    c.bot_paused_at,
                    c.bot_paused_reason,
                    c.messaging_window_expires_at,
                    m.message_payload
                from whatsapp_conversations c
                left join lateral (
                    select message_payload
                    from whatsapp_messages
                    where conversation_id = c.id
                      and message_payload is not null
                      and message_payload ? 'account'
                      and nullif(message_payload #>> '{account,id}', '') is not null
                      and nullif(coalesce(message_payload #>> '{message,conversationId}', message_payload #>> '{conversation,id}'), '') is not null
                    order by created_at desc
                    limit 1
                ) m on true
                where c.id = :conversation_id and c.company_id = :tenant_id
                limit 1
                """
            ),
            {"conversation_id": conversation_id, "tenant_id": tenant_id},
        )

    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Conversation not found")

    payload = row.get("message_payload")
    if not isinstance(payload, Mapping):
        raise HTTPException(status_code=400, detail="Zernio conversation context is missing")

    account_id, zernio_conversation_id = _zernio_context_from_payload(cast(Mapping[str, Any], payload))
    if not account_id or not zernio_conversation_id:
        raise HTTPException(status_code=400, detail="Zernio conversation context is incomplete")

    return {**row, "zernio_account_id": account_id, "zernio_conversation_id": zernio_conversation_id, "message_payload": payload}


def _message_response_from_row(channel: Literal["instagram", "whatsapp"], row: Mapping[str, Any]) -> MessageResponse:
    direction = str(row["direction"] or "outbound")
    if direction not in {"inbound", "outbound"}:
        direction = "outbound"

    return MessageResponse(
        id=str(row["id"]),
        tenant_id=str(row["company_id"]),
        channel=channel,
        direction=cast(Any, direction),
        sender_type=cast(Any, row.get("sender_type")),
        manager_id=str(row["manager_id"]) if row.get("manager_id") else None,
        text=str(row["message_text"] or ""),
        status=str(row.get("delivery_status") or "sent"),
        external_message_id=str(row.get("external_message_id") or row.get("instagram_mid") or row.get("whatsapp_mid") or row["id"]),
        intent=str(row["intent"]) if row.get("intent") else None,
        intent_confidence=float(cast(Any, row["intent_confidence"])) if row.get("intent_confidence") is not None else None,
        created_at=cast(datetime, row["created_at"]),
    )


async def _conversation_belongs_to_tenant(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    channel: Literal["instagram", "whatsapp"],
    conversation_id: uuid.UUID,
    cloud: bool = False,
) -> bool:
    table_name = "instagram_conversations" if channel == "instagram" else "whatsapp_cloud_conversations" if cloud else "whatsapp_conversations"
    result = await db.execute(
        text(f"select 1 from {table_name} where id = :conversation_id and company_id = :tenant_id limit 1"),
        {"conversation_id": conversation_id, "tenant_id": tenant_id},
    )
    return result.scalar_one_or_none() is not None


async def _apply_conversation_action_with_fallback(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    channel: Literal["instagram", "whatsapp"],
    conversation_id: uuid.UUID,
    actor_id: uuid.UUID,
    action: Literal["take", "return_bot", "pause", "close"],
) -> Mapping[str, Any]:
    cloud = False
    if not await _conversation_belongs_to_tenant(db, tenant_id=tenant_id, channel=channel, conversation_id=conversation_id, cloud=False):
        if channel != "whatsapp" or not await _conversation_belongs_to_tenant(db, tenant_id=tenant_id, channel=channel, conversation_id=conversation_id, cloud=True):
            raise HTTPException(status_code=404, detail="Conversation not found")
        cloud = True

    row = await apply_conversation_action(
        db,
        channel=channel,
        conversation_id=conversation_id,
        actor_id=actor_id,
        action=action,
        cloud=cloud,
    )
    return row


@router.post("/tenants/{tenant_id}/conversations/{channel}/{conversation_id}/take", response_model=ConversationActionResponse)
async def take_conversation(
    tenant_id: uuid.UUID,
    channel: Literal["instagram", "whatsapp"],
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> ConversationActionResponse:
    _assert_company_access(tenant_id, user)
    row = await _apply_conversation_action_with_fallback(db, tenant_id=tenant_id, channel=channel, conversation_id=conversation_id, actor_id=uuid.UUID(user.user_id), action="take")
    return _conversation_action_response(channel, row)


@router.post("/tenants/{tenant_id}/conversations/{channel}/{conversation_id}/return-bot", response_model=ConversationActionResponse)
async def return_conversation_to_bot(
    tenant_id: uuid.UUID,
    channel: Literal["instagram", "whatsapp"],
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> ConversationActionResponse:
    _assert_company_access(tenant_id, user)
    try:
        row = await _apply_conversation_action_with_fallback(db, tenant_id=tenant_id, channel=channel, conversation_id=conversation_id, actor_id=uuid.UUID(user.user_id), action="return_bot")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _conversation_action_response(channel, row)


@router.post("/tenants/{tenant_id}/conversations/{channel}/{conversation_id}/pause", response_model=ConversationActionResponse)
async def pause_conversation(
    tenant_id: uuid.UUID,
    channel: Literal["instagram", "whatsapp"],
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> ConversationActionResponse:
    _assert_company_access(tenant_id, user)
    row = await _apply_conversation_action_with_fallback(db, tenant_id=tenant_id, channel=channel, conversation_id=conversation_id, actor_id=uuid.UUID(user.user_id), action="pause")
    return _conversation_action_response(channel, row)


@router.post("/tenants/{tenant_id}/conversations/{channel}/{conversation_id}/messages", response_model=ConversationSendMessageResponse)
async def send_conversation_message(
    tenant_id: uuid.UUID,
    channel: Literal["instagram", "whatsapp"],
    conversation_id: uuid.UUID,
    payload: ConversationSendMessageRequest,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> ConversationSendMessageResponse:
    _assert_company_access(tenant_id, user)
    context = await _load_zernio_manual_send_context(db, tenant_id=tenant_id, channel=channel, conversation_id=conversation_id)

    expires_at = context.get("messaging_window_expires_at")
    if not isinstance(expires_at, datetime) or expires_at <= _now():
        raise HTTPException(status_code=400, detail="24-hour messaging window is closed")
    if str(context.get("status") or "open") == "closed" or str(context.get("mode") or "bot") == "closed":
        raise HTTPException(status_code=400, detail="Conversation is closed")

    message_text = payload.message_text.strip()
    send_result = await send_zernio_inbox_message(
        account_id=str(context["zernio_account_id"]),
        conversation_id=str(context["zernio_conversation_id"]),
        text_message=message_text,
    )
    external_message_id = _extract_zernio_sent_message_id(send_result) or f"zernio-manager-{uuid.uuid4()}"

    if channel == "instagram":
        await persist_message(
            db,
            company_id=str(tenant_id),
            customer_id=str(context["customer_id"]),
            company_account_id=str(context["zernio_account_id"]),
            direction="outbound",
            text_message=message_text,
            instagram_mid=external_message_id,
            payload=send_result,
            username=str(context["customer_name"]) if context.get("customer_name") else None,
            sender_type="manager",
            manager_id=user.user_id,
        )
        message_result = await db.execute(
            text(
                """
                select id, company_id, instagram_mid, external_message_id, direction, sender_type, manager_id,
                       message_text, delivery_status, intent, intent_confidence, created_at
                from instagram_messages
                where company_id = :tenant_id and instagram_mid = :external_message_id
                limit 1
                """
            ),
            {"tenant_id": tenant_id, "external_message_id": external_message_id},
        )
    else:
        _, message_id = await persist_zernio_whatsapp_message(
            db,
            company_id=tenant_id,
            customer_id=str(context["customer_id"]),
            company_account_id=str(context["zernio_account_id"]),
            direction="outbound",
            text_message=message_text,
            whatsapp_mid=external_message_id,
            payload=send_result,
            customer_name=str(context["customer_name"]) if context.get("customer_name") else None,
            customer_phone=str(context["customer_phone"]) if context.get("customer_phone") else None,
            sent_at=None,
            sender_type="manager",
            manager_id=uuid.UUID(user.user_id),
            zernio_conversation_id=str(context["zernio_conversation_id"]),
        )
        message_result = await db.execute(
            text(
                """
                select id, company_id, whatsapp_mid, external_message_id, direction, sender_type, manager_id,
                       message_text, delivery_status, intent, intent_confidence, created_at
                from whatsapp_messages
                where id = :message_id
                limit 1
                """
            ),
            {"message_id": message_id},
        )

    await mark_outbound_activity(db, channel=channel, conversation_id=conversation_id, sender_type="manager", manager_id=uuid.UUID(user.user_id))
    await db.commit()

    message_row = message_result.mappings().first()
    if not message_row:
        raise HTTPException(status_code=500, detail="Message was sent but not persisted")

    updated_context = await _load_zernio_manual_send_context(db, tenant_id=tenant_id, channel=channel, conversation_id=conversation_id)
    return ConversationSendMessageResponse(
        message=_message_response_from_row(channel, cast(Mapping[str, Any], message_row)),
        conversation=_conversation_action_response(channel, updated_context),
    )


@router.post("/tenants/{tenant_id}/conversations/{channel}/{conversation_id}/close", response_model=ConversationActionResponse)
async def close_conversation(
    tenant_id: uuid.UUID,
    channel: Literal["instagram", "whatsapp"],
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> ConversationActionResponse:
    _assert_company_access(tenant_id, user)
    row = await _apply_conversation_action_with_fallback(db, tenant_id=tenant_id, channel=channel, conversation_id=conversation_id, actor_id=uuid.UUID(user.user_id), action="close")
    return _conversation_action_response(channel, row)


@router.get("/me/telegram", response_model=TelegramStatusResponse)
async def get_my_telegram_status(
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> TelegramStatusResponse:
    result = await db.execute(
        text("select telegram_chat_id, telegram_username, telegram_notifications_enabled from users where id = :user_id limit 1"),
        {"user_id": uuid.UUID(user.user_id)},
    )
    row = result.mappings().first() or {}
    return TelegramStatusResponse(
        connected=bool(row.get("telegram_chat_id")),
        username=str(row["telegram_username"]) if row.get("telegram_username") else None,
        notifications_enabled=bool(row.get("telegram_notifications_enabled")),
    )


@router.post("/me/telegram/connect-link", response_model=TelegramConnectResponse)
async def create_my_telegram_connect_link(
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> TelegramConnectResponse:
    try:
        connect_url = await create_telegram_connect_link(db, user_id=uuid.UUID(user.user_id))
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return TelegramConnectResponse(connect_url=connect_url)


@router.delete("/me/telegram", response_model=TelegramStatusResponse)
async def disconnect_my_telegram(
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> TelegramStatusResponse:
    await disable_telegram_notifications(db, user_id=uuid.UUID(user.user_id))
    return TelegramStatusResponse(connected=False, username=None, notifications_enabled=False)


@router.get(
    "/tenants/{tenant_id}/whatsapp-cloud/status",
    response_model=WhatsAppCloudIntegrationResponse,
)
async def get_whatsapp_cloud_status(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> WhatsAppCloudIntegrationResponse:
    _assert_company_access(tenant_id, user)

    await ensure_company_exists(db, tenant_id)

    zernio_profile_id = await get_zernio_profile_id(db, tenant_id)
    if zernio_profile_id:
        try:
            connected_accounts = await IntegratorZernio().get_connected_accounts(zernio_profile_id)
            await upsert_zernio_whatsapp_connected_accounts(
                db,
                company_id=tenant_id,
                zernio_profile_id=zernio_profile_id,
                accounts=connected_accounts,
            )
        except RuntimeError:
            await db.rollback()
            logger.warning("Zernio WhatsApp accounts sync skipped: SDK is not configured", exc_info=True)
        except ValueError as exc:
            await db.rollback()
            if "already linked to another business" in str(exc):
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            logger.warning("Zernio WhatsApp accounts sync returned invalid payload", exc_info=True)
        except Exception as exc:
            await db.rollback()
            if "UniqueViolationError" in str(exc) or "duplicate key value" in str(exc):
                raise HTTPException(status_code=409, detail="WhatsApp account is already linked to another business") from exc
            logger.warning("Zernio WhatsApp accounts sync failed", exc_info=True)

    zernio_account = await get_latest_zernio_whatsapp_connected_account(db, tenant_id)
    if not zernio_account:
        return WhatsAppCloudIntegrationResponse(
            status="not_connected",
            tenant_id=str(tenant_id),
            business_id=None,
            waba_id="",
            phone_number_id="",
            display_phone_number=None,
            verified_name=None,
            quality_rating=None,
            webhook_subscribed=False,
            connected=False,
            registered=False,
            pin_required=False,
        )

    await db.execute(
        text(
            """
            update users
            set wp_activated = true,
                updated_at = now()
            where instagram_company_id = :tenant_id
            """
        ),
        {"tenant_id": tenant_id},
    )
    await db.commit()
    return _zernio_whatsapp_response(tenant_id, zernio_account)


@router.post(
    "/tenants/{tenant_id}/whatsapp-cloud/disconnect",
    response_model=WhatsAppCloudIntegrationResponse,
)
@router.delete(
    "/tenants/{tenant_id}/whatsapp-cloud",
    response_model=WhatsAppCloudIntegrationResponse,
)
async def disconnect_whatsapp_cloud(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user),
) -> WhatsAppCloudIntegrationResponse:
    _assert_company_access(tenant_id, user)

    await ensure_company_exists(db, tenant_id)

    account_ids = await list_zernio_whatsapp_connected_account_ids(db, tenant_id)
    try:
        await _delete_zernio_accounts(account_ids, platform="whatsapp")
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    await disconnect_zernio_whatsapp_connected_accounts(db, tenant_id)
    await disconnect_whatsapp_cloud_integration(db, tenant_id)

    return WhatsAppCloudIntegrationResponse(
        status="disconnected",
        tenant_id=str(tenant_id),
        business_id=None,
        waba_id="",
        phone_number_id="",
        display_phone_number=None,
        verified_name=None,
        quality_rating=None,
        webhook_subscribed=False,
        connected=False,
        registered=False,
        pin_required=False,
    )