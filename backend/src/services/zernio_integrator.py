from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from zernio import Zernio

from config.app_config import settings

logger = logging.getLogger(__name__)

SocialNetwork = Literal["instagram", "whatsapp", "tiktok"]


def _jsonable(value: Any) -> Any:
    """Convert SDK return objects into JSONB-safe primitives."""
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_jsonable(item) for item in value]

    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return _jsonable(model_dump())

    dict_method = getattr(value, "dict", None)
    if callable(dict_method):
        return _jsonable(dict_method())

    if hasattr(value, "__dict__"):
        return _jsonable(vars(value))
    return str(value)


def _object_payload(value: Any, *, error_message: str) -> dict[str, Any]:
    payload = _jsonable(value)
    if not isinstance(payload, dict):
        raise ValueError(error_message)
    return payload


def _extract_profile_id(profile_payload: Mapping[str, Any]) -> str:
    profile_id = profile_payload.get("_id") or profile_payload.get("id") or profile_payload.get("profile_id")
    if not profile_id:
        raise ValueError("Zernio profile payload does not contain profile id")
    return str(profile_id)


def _extract_account_profile_id(account_payload: Mapping[str, Any]) -> str | None:
    profile_value = account_payload.get("profileId") or account_payload.get("profile_id") or account_payload.get("profile")
    if isinstance(profile_value, Mapping):
        profile_id = profile_value.get("_id") or profile_value.get("id") or profile_value.get("profile_id")
        return str(profile_id) if profile_id else None
    return str(profile_value) if profile_value else None


def _extract_connected_accounts_payload(result: Any) -> list[dict[str, Any]]:
    payload = _jsonable(result)
    if isinstance(payload, Mapping):
        accounts = payload.get("accounts") or payload.get("data") or payload.get("items") or []
    else:
        accounts = payload

    if not isinstance(accounts, Sequence) or isinstance(accounts, str | bytes | bytearray):
        raise ValueError("Zernio list_accounts response does not contain accounts list")

    normalized_accounts: list[dict[str, Any]] = []
    for account in accounts:
        if isinstance(account, Mapping):
            normalized_accounts.append(dict(account))
    return normalized_accounts


def _account_platform(account_payload: Mapping[str, Any]) -> str:
    return str(account_payload.get("platform") or account_payload.get("network") or "").lower()


def _is_instagram_account(account_payload: Mapping[str, Any]) -> bool:
    return _account_platform(account_payload) == "instagram"


def _is_whatsapp_account(account_payload: Mapping[str, Any]) -> bool:
    return _account_platform(account_payload) == "whatsapp"


def _is_tiktok_account(account_payload: Mapping[str, Any]) -> bool:
    return _account_platform(account_payload) in {"tiktok", "tik_tok", "tik-tok"}


def _extract_zernio_account_id(account_payload: Mapping[str, Any]) -> str:
    account_id = account_payload.get("_id") or account_payload.get("id") or account_payload.get("account_id")
    if not account_id:
        raise ValueError("Zernio connected account does not contain account id")
    return str(account_id)


def _extract_instagram_account_id(account_payload: Mapping[str, Any]) -> str | None:
    account_id = (
        account_payload.get("instagramAccountId")
        or account_payload.get("instagram_account_id")
        or account_payload.get("instagramUserId")
        or account_payload.get("instagram_user_id")
        or account_payload.get("externalAccountId")
        or account_payload.get("external_account_id")
        or account_payload.get("userId")
        or account_payload.get("user_id")
    )
    return str(account_id) if account_id else None


def _extract_tiktok_account_id(account_payload: Mapping[str, Any]) -> str | None:
    account_id = (
        account_payload.get("tiktokAccountId")
        or account_payload.get("tikTokAccountId")
        or account_payload.get("tiktok_account_id")
        or account_payload.get("tik_tok_account_id")
        or account_payload.get("openId")
        or account_payload.get("open_id")
        or account_payload.get("externalAccountId")
        or account_payload.get("external_account_id")
        or account_payload.get("userId")
        or account_payload.get("user_id")
    )
    return str(account_id) if account_id else None


def _extract_whatsapp_account_id(account_payload: Mapping[str, Any]) -> str | None:
    account_id = (
        account_payload.get("whatsappAccountId")
        or account_payload.get("whatsapp_account_id")
        or account_payload.get("whatsappUserId")
        or account_payload.get("whatsapp_user_id")
        or account_payload.get("phoneNumberId")
        or account_payload.get("phone_number_id")
        or account_payload.get("externalAccountId")
        or account_payload.get("external_account_id")
        or account_payload.get("userId")
        or account_payload.get("user_id")
    )
    return str(account_id) if account_id else None


class IntegratorZernio:
    def __init__(self) -> None:
        if not settings.zernio_api_key:
            raise RuntimeError("ZERNIO_API_KEY/ZERNIO_KEY is not configured")
        self.client = Zernio(api_key=settings.zernio_api_key)

    async def create_company_profile(self, company_email: str, company_uuid: uuid.UUID) -> dict[str, Any]:
        return await asyncio.to_thread(self._create_company_profile_sync, company_email, company_uuid)

    def _create_company_profile_sync(self, company_email: str, company_uuid: uuid.UUID) -> dict[str, Any]:
        result = self.client.profiles.create_profile(
            name=company_email,
            description=str(company_uuid),
        )

        result_payload = _object_payload(result, error_message="Zernio create_profile response is not an object")
        profile_payload = result_payload.get("profile")
        if not isinstance(profile_payload, Mapping):
            raise ValueError("Zernio create_profile response does not contain profile object")

        profile_payload = _object_payload(profile_payload, error_message="Zernio profile payload is not an object")
        profile_id = _extract_profile_id(profile_payload)

        logger.info("Zernio profile created profile_id=%s company_uuid=%s", profile_id, company_uuid)
        return profile_payload

    async def connect_social_network(
        self,
        network_type: SocialNetwork,
        profile_id: str,
        *,
        redirect_url: str | None = None,
    ) -> str:
        return await asyncio.to_thread(self._connect_social_network_sync, network_type, profile_id, redirect_url)

    def _connect_social_network_sync(
        self,
        network_type: SocialNetwork,
        profile_id: str,
        redirect_url: str | None = None,
    ) -> str:
        request_kwargs: dict[str, str] = {
            "profile_id": profile_id,
            "platform": network_type,
        }
        if redirect_url:
            request_kwargs["redirect_url"] = redirect_url

        result = self.client.connect.get_connect_url(
            **request_kwargs,
        )

        result_payload = _object_payload(result, error_message="Zernio connect response is not an object")
        auth_url = result_payload.get("authUrl") or result_payload.get("auth_url") or result_payload.get("url")
        if not auth_url:
            raise ValueError("Zernio connect response does not contain authUrl/auth_url")

        return str(auth_url)

    async def get_connected_accounts(self, profile_id: str) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._get_connected_accounts_sync, profile_id)

    async def create_post(
        self,
        *,
        title: str | None,
        content: str,
        platforms: list[dict[str, Any]],
        media_items: list[Any] | None = None,
        scheduled_for: datetime | str | None = None,
        publish_now: bool = False,
        is_draft: bool = False,
        metadata: dict[str, Any] | None = None,
        tiktok_settings: Any | None = None,
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            self._create_post_sync,
            title,
            content,
            platforms,
            media_items,
            scheduled_for,
            publish_now,
            is_draft,
            metadata,
            tiktok_settings,
        )

    def _create_post_sync(
        self,
        title: str | None,
        content: str,
        platforms: list[dict[str, Any]],
        media_items: list[Any] | None,
        scheduled_for: datetime | str | None,
        publish_now: bool,
        is_draft: bool,
        metadata: dict[str, Any] | None,
        tiktok_settings: Any | None,
    ) -> dict[str, Any]:
        scheduled_value = scheduled_for.isoformat() if isinstance(scheduled_for, datetime) else scheduled_for
        kwargs: dict[str, Any] = {
            "title": title,
            "content": content,
            "platforms": platforms,
            "media_items": media_items or [],
            "scheduled_for": scheduled_value,
            "publish_now": publish_now,
            "is_draft": is_draft,
            "metadata": metadata or {},
        }
        if tiktok_settings:
            kwargs["tiktok_settings"] = tiktok_settings
        result = self.client.posts.create_post(**kwargs)
        payload = _jsonable(result)
        return payload if isinstance(payload, dict) else {"value": payload}

    async def send_inbox_message(self, *, account_id: str, conversation_id: str, text_message: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._send_inbox_message_sync, account_id, conversation_id, text_message)

    async def send_private_reply_to_comment(self, *, account_id: str, post_id: str, comment_id: str, message: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._send_private_reply_to_comment_sync, account_id, post_id, comment_id, message)

    def _send_private_reply_to_comment_sync(self, account_id: str, post_id: str, comment_id: str, message: str) -> dict[str, Any]:
        logger.info(
            "ZERNIO API: send_private_reply_to_comment account=%s post=%s comment=%s message_len=%d",
            account_id, post_id, comment_id, len(message),
        )
        logger.info("ZERNIO API: message_text=%s", message[:300])

        result = self.client.comments.send_private_reply_to_comment(
            post_id=post_id,
            comment_id=comment_id,
            account_id=account_id,
            message=message,
        )

        logger.info("ZERNIO API: result=%s", result)
        payload = _jsonable(result)
        logger.info("ZERNIO API: payload=%s", payload)

        return payload if isinstance(payload, dict) else {"value": payload}

    async def delete_account(self, account_id: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._delete_account_sync, account_id)

    async def delete_post(self, post_id: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._delete_post_sync, post_id)

    def _delete_post_sync(self, post_id: str) -> dict[str, Any]:
        result = self.client.posts.delete_post(post_id=post_id)
        payload = _jsonable(result)
        return payload if isinstance(payload, dict) else {"value": payload}

    def _delete_account_sync(self, account_id: str) -> dict[str, Any]:
        result = self.client.accounts.delete_account(account_id=account_id)
        payload = _jsonable(result)
        return payload if isinstance(payload, dict) else {"value": payload}

    def _send_inbox_message_sync(self, account_id: str, conversation_id: str, text_message: str) -> dict[str, Any]:
        result = self.client.messages.send_inbox_message(
            conversation_id=conversation_id,
            account_id=account_id,
            message=text_message,
        )
        payload = _jsonable(result)
        return payload if isinstance(payload, dict) else {"value": payload}

    def _get_connected_accounts_sync(self, profile_id: str) -> list[dict[str, Any]]:
        result = self.client.accounts.list_accounts()
        accounts = _extract_connected_accounts_payload(result)

        profile_accounts = [
            account
            for account in accounts
            if _extract_account_profile_id(account) == profile_id
        ]
        logger.info("Fetched Zernio connected accounts profile_id=%s count=%s", profile_id, len(profile_accounts))
        return profile_accounts


async def get_zernio_profile_id(db: AsyncSession, company_id: uuid.UUID) -> str | None:
    result = await db.execute(
        text(
            """
            select zernio_profile_id
            from zernio_company_profiles
            where company_id = :company_id
            limit 1
            """
        ),
        {"company_id": company_id},
    )
    profile_id = result.scalar_one_or_none()
    return str(profile_id) if profile_id else None


async def upsert_zernio_company_profile(
    db: AsyncSession,
    *,
    company_id: uuid.UUID,
    user_id: uuid.UUID | None,
    company_email: str,
    company_profile: Mapping[str, Any] | str,
) -> None:
    """Persist the company_profile returned by Zernio SDK.

    Kept in a separate table so the existing Instagram/WhatsApp production schema
    stays stable and the Zernio profile can evolve independently.
    """
    now = datetime.now(timezone.utc)
    profile_payload = _jsonable(company_profile)
    if not isinstance(profile_payload, dict):
        profile_payload = {"value": profile_payload}

    zernio_profile_id = (
        profile_payload.get("_id")
        or profile_payload.get("id")
        or profile_payload.get("profile_id")
        or profile_payload.get("value")
    )
    if not zernio_profile_id:
        raise ValueError("Zernio company_profile does not contain profile id")

    profile_name = profile_payload.get("name")

    await db.execute(
        text(
            """
            insert into zernio_company_profiles (
                company_id,
                user_id,
                zernio_profile_id,
                profile_name,
                company_email,
                company_profile,
                created_at,
                updated_at
            ) values (
                :company_id,
                :user_id,
                :zernio_profile_id,
                :profile_name,
                :company_email,
                cast(:company_profile as jsonb),
                :now,
                :now
            )
            on conflict (company_id) do update set
                user_id = excluded.user_id,
                zernio_profile_id = excluded.zernio_profile_id,
                profile_name = excluded.profile_name,
                company_email = excluded.company_email,
                company_profile = excluded.company_profile,
                updated_at = excluded.updated_at
            """
        ),
        {
            "company_id": company_id,
            "user_id": user_id,
            "zernio_profile_id": str(zernio_profile_id),
            "profile_name": str(profile_name) if profile_name is not None else None,
            "company_email": company_email,
            "company_profile": json.dumps(profile_payload, ensure_ascii=False),
            "now": now,
        },
    )
    await db.commit()


async def _ensure_social_account_not_linked_elsewhere(
    db: AsyncSession,
    *,
    table_name: Literal["zernio_instagram_connected_accounts", "zernio_whatsapp_connected_accounts", "zernio_tiktok_connected_accounts"],
    company_id: uuid.UUID,
    zernio_account_id: str,
    external_account_column: Literal["instagram_account_id", "whatsapp_account_id", "tiktok_account_id"],
    external_account_id: str | None,
    platform_label: str,
) -> None:
    result = await db.execute(
        text(
            f"""
            select company_id
            from {table_name}
            where company_id <> :company_id
              and (
                zernio_account_id = :zernio_account_id
                or (
                  cast(:external_account_id as text) is not null
                  and {external_account_column} = cast(:external_account_id as text)
                )
              )
            limit 1
            """
        ),
        {
            "company_id": company_id,
            "zernio_account_id": zernio_account_id,
            "external_account_id": external_account_id,
        },
    )
    conflicting_company_id = result.scalar_one_or_none()
    if conflicting_company_id:
        raise ValueError(
            f"{platform_label} account is already linked to another business: {conflicting_company_id}"
        )


async def upsert_zernio_instagram_connected_accounts(
    db: AsyncSession,
    *,
    company_id: uuid.UUID,
    zernio_profile_id: str,
    accounts: Sequence[Mapping[str, Any]],
) -> int:
    """Persist Instagram accounts returned by Zernio without touching Meta production tables."""
    now = datetime.now(timezone.utc)
    saved_count = 0

    for account in accounts:
        account_payload = _object_payload(account, error_message="Zernio account payload is not an object")
        if not _is_instagram_account(account_payload):
            continue

        account_profile_id = _extract_account_profile_id(account_payload)
        if account_profile_id and account_profile_id != zernio_profile_id:
            continue

        zernio_account_id = _extract_zernio_account_id(account_payload)
        instagram_account_id = _extract_instagram_account_id(account_payload)
        await _ensure_social_account_not_linked_elsewhere(
            db,
            table_name="zernio_instagram_connected_accounts",
            company_id=company_id,
            zernio_account_id=zernio_account_id,
            external_account_column="instagram_account_id",
            external_account_id=instagram_account_id,
            platform_label="Instagram",
        )
        username = account_payload.get("username") or account_payload.get("userName")
        display_name = account_payload.get("displayName") or account_payload.get("display_name") or account_payload.get("name")

        await db.execute(
            text(
                """
                insert into zernio_instagram_connected_accounts (
                    company_id,
                    zernio_profile_id,
                    zernio_account_id,
                    instagram_account_id,
                    username,
                    display_name,
                    account_payload,
                    last_seen_at,
                    created_at,
                    updated_at
                ) values (
                    :company_id,
                    :zernio_profile_id,
                    :zernio_account_id,
                    :instagram_account_id,
                    :username,
                    :display_name,
                    cast(:account_payload as jsonb),
                    :now,
                    :now,
                    :now
                )
                on conflict (company_id, zernio_account_id) do update set
                    zernio_profile_id = excluded.zernio_profile_id,
                    instagram_account_id = excluded.instagram_account_id,
                    username = excluded.username,
                    display_name = excluded.display_name,
                    account_payload = excluded.account_payload,
                    last_seen_at = excluded.last_seen_at,
                    updated_at = excluded.updated_at
                """
            ),
            {
                "company_id": company_id,
                "zernio_profile_id": zernio_profile_id,
                "zernio_account_id": zernio_account_id,
                "instagram_account_id": instagram_account_id,
                "username": str(username) if username is not None else None,
                "display_name": str(display_name) if display_name is not None else None,
                "account_payload": json.dumps(account_payload, ensure_ascii=False),
                "now": now,
            },
        )
        saved_count += 1

    await db.commit()
    return saved_count


async def upsert_zernio_whatsapp_connected_accounts(
    db: AsyncSession,
    *,
    company_id: uuid.UUID,
    zernio_profile_id: str,
    accounts: Sequence[Mapping[str, Any]],
) -> int:
    """Persist WhatsApp accounts returned by Zernio without touching official WhatsApp Cloud tables."""
    now = datetime.now(timezone.utc)
    saved_count = 0

    for account in accounts:
        account_payload = _object_payload(account, error_message="Zernio account payload is not an object")
        if not _is_whatsapp_account(account_payload):
            continue

        account_profile_id = _extract_account_profile_id(account_payload)
        if account_profile_id and account_profile_id != zernio_profile_id:
            continue

        zernio_account_id = _extract_zernio_account_id(account_payload)
        whatsapp_account_id = _extract_whatsapp_account_id(account_payload)
        await _ensure_social_account_not_linked_elsewhere(
            db,
            table_name="zernio_whatsapp_connected_accounts",
            company_id=company_id,
            zernio_account_id=zernio_account_id,
            external_account_column="whatsapp_account_id",
            external_account_id=whatsapp_account_id,
            platform_label="WhatsApp",
        )
        username = account_payload.get("username") or account_payload.get("userName") or account_payload.get("phone")
        display_name = account_payload.get("displayName") or account_payload.get("display_name") or account_payload.get("name")

        await db.execute(
            text(
                """
                insert into zernio_whatsapp_connected_accounts (
                    company_id,
                    zernio_profile_id,
                    zernio_account_id,
                    whatsapp_account_id,
                    username,
                    display_name,
                    account_payload,
                    last_seen_at,
                    created_at,
                    updated_at
                ) values (
                    :company_id,
                    :zernio_profile_id,
                    :zernio_account_id,
                    :whatsapp_account_id,
                    :username,
                    :display_name,
                    cast(:account_payload as jsonb),
                    :now,
                    :now,
                    :now
                )
                on conflict (company_id, zernio_account_id) do update set
                    zernio_profile_id = excluded.zernio_profile_id,
                    whatsapp_account_id = excluded.whatsapp_account_id,
                    username = excluded.username,
                    display_name = excluded.display_name,
                    account_payload = excluded.account_payload,
                    last_seen_at = excluded.last_seen_at,
                    updated_at = excluded.updated_at
                """
            ),
            {
                "company_id": company_id,
                "zernio_profile_id": zernio_profile_id,
                "zernio_account_id": zernio_account_id,
                "whatsapp_account_id": whatsapp_account_id,
                "username": str(username) if username is not None else None,
                "display_name": str(display_name) if display_name is not None else None,
                "account_payload": json.dumps(account_payload, ensure_ascii=False),
                "now": now,
            },
        )
        saved_count += 1

    await db.commit()
    return saved_count


async def list_zernio_instagram_connected_account_ids(db: AsyncSession, company_id: uuid.UUID) -> list[str]:
    result = await db.execute(
        text(
            """
            select zernio_account_id
            from zernio_instagram_connected_accounts
            where company_id = :company_id
            order by last_seen_at desc nulls last, updated_at desc nulls last
            """
        ),
        {"company_id": company_id},
    )
    return [str(row[0]) for row in result.all() if row[0]]


async def list_zernio_whatsapp_connected_account_ids(db: AsyncSession, company_id: uuid.UUID) -> list[str]:
    result = await db.execute(
        text(
            """
            select zernio_account_id
            from zernio_whatsapp_connected_accounts
            where company_id = :company_id
            order by last_seen_at desc nulls last, updated_at desc nulls last
            """
        ),
        {"company_id": company_id},
    )
    return [str(row[0]) for row in result.all() if row[0]]


async def disconnect_zernio_instagram_connected_accounts(db: AsyncSession, company_id: uuid.UUID) -> None:
    await db.execute(
        text("delete from zernio_instagram_connected_accounts where company_id = :company_id"),
        {"company_id": company_id},
    )
    await db.execute(
        text(
            """
            update users
            set ig_activated = false,
                updated_at = now()
            where instagram_company_id = :company_id
            """
        ),
        {"company_id": company_id},
    )
    await db.commit()


async def disconnect_zernio_whatsapp_connected_accounts(db: AsyncSession, company_id: uuid.UUID) -> None:
    await db.execute(
        text("delete from zernio_whatsapp_connected_accounts where company_id = :company_id"),
        {"company_id": company_id},
    )
    await db.execute(
        text(
            """
            update users
            set wp_activated = false,
                updated_at = now()
            where instagram_company_id = :company_id
            """
        ),
        {"company_id": company_id},
    )
    await db.commit()


async def get_latest_zernio_whatsapp_connected_account(
    db: AsyncSession,
    company_id: uuid.UUID,
) -> Mapping[str, Any] | None:
    result = await db.execute(
        text(
            """
            select
                zernio_profile_id,
                zernio_account_id,
                whatsapp_account_id,
                username,
                display_name,
                account_payload,
                last_seen_at
            from zernio_whatsapp_connected_accounts
            where company_id = :company_id
            order by last_seen_at desc nulls last, updated_at desc nulls last
            limit 1
            """
        ),
        {"company_id": company_id},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def upsert_zernio_tiktok_connected_accounts(
    db: AsyncSession,
    *,
    company_id: uuid.UUID,
    zernio_profile_id: str,
    accounts: Sequence[Mapping[str, Any]],
) -> int:
    """Persist TikTok accounts returned by Zernio for posting-only integrations."""
    now = datetime.now(timezone.utc)
    saved_count = 0

    for account in accounts:
        account_payload = _object_payload(account, error_message="Zernio account payload is not an object")
        if not _is_tiktok_account(account_payload):
            continue

        account_profile_id = _extract_account_profile_id(account_payload)
        if account_profile_id and account_profile_id != zernio_profile_id:
            continue

        zernio_account_id = _extract_zernio_account_id(account_payload)
        tiktok_account_id = _extract_tiktok_account_id(account_payload)
        await _ensure_social_account_not_linked_elsewhere(
            db,
            table_name="zernio_tiktok_connected_accounts",
            company_id=company_id,
            zernio_account_id=zernio_account_id,
            external_account_column="tiktok_account_id",
            external_account_id=tiktok_account_id,
            platform_label="TikTok",
        )
        username = account_payload.get("username") or account_payload.get("userName") or account_payload.get("displayName")
        display_name = account_payload.get("displayName") or account_payload.get("display_name") or account_payload.get("name")

        await db.execute(
            text(
                """
                insert into zernio_tiktok_connected_accounts (
                    company_id,
                    zernio_profile_id,
                    zernio_account_id,
                    tiktok_account_id,
                    username,
                    display_name,
                    account_payload,
                    last_seen_at,
                    created_at,
                    updated_at
                ) values (
                    :company_id,
                    :zernio_profile_id,
                    :zernio_account_id,
                    :tiktok_account_id,
                    :username,
                    :display_name,
                    cast(:account_payload as jsonb),
                    :now,
                    :now,
                    :now
                )
                on conflict (company_id, zernio_account_id) do update set
                    zernio_profile_id = excluded.zernio_profile_id,
                    tiktok_account_id = excluded.tiktok_account_id,
                    username = excluded.username,
                    display_name = excluded.display_name,
                    account_payload = excluded.account_payload,
                    last_seen_at = excluded.last_seen_at,
                    updated_at = excluded.updated_at
                """
            ),
            {
                "company_id": company_id,
                "zernio_profile_id": zernio_profile_id,
                "zernio_account_id": zernio_account_id,
                "tiktok_account_id": tiktok_account_id,
                "username": str(username) if username is not None else None,
                "display_name": str(display_name) if display_name is not None else None,
                "account_payload": json.dumps(account_payload, ensure_ascii=False),
                "now": now,
            },
        )
        saved_count += 1

    await db.commit()
    return saved_count


async def list_zernio_tiktok_connected_account_ids(db: AsyncSession, company_id: uuid.UUID) -> list[str]:
    result = await db.execute(
        text(
            """
            select zernio_account_id
            from zernio_tiktok_connected_accounts
            where company_id = :company_id
            """
        ),
        {"company_id": company_id},
    )
    return [str(row[0]) for row in result.all()]


async def get_latest_zernio_tiktok_connected_account(
    db: AsyncSession,
    company_id: uuid.UUID,
) -> Mapping[str, Any] | None:
    result = await db.execute(
        text(
            """
            select *
            from zernio_tiktok_connected_accounts
            where company_id = :company_id
            order by last_seen_at desc nulls last, created_at desc
            limit 1
            """
        ),
        {"company_id": company_id},
    )
    return result.mappings().first()


async def disconnect_zernio_tiktok_connected_accounts(db: AsyncSession, company_id: uuid.UUID) -> None:
    await db.execute(
        text("delete from zernio_tiktok_connected_accounts where company_id = :company_id"),
        {"company_id": company_id},
    )
    await db.execute(
        text("update social_posting_connections set status = 'disabled', connected_at = null, updated_at = now() where company_id = :company_id and platform = 'tiktok'"),
        {"company_id": company_id},
    )
    await db.commit()
