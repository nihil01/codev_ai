import logging
from typing import TypedDict, cast, Any

import httpx
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from config.app_config import settings as cfg, settings
from services.company_runtime import get_company_runtime

logger = logging.getLogger(__name__)


class InstagramTokenResponse(TypedDict):
    access_token: str
    token_type: str
    user_id: str | int
    expires_in: int


class InstagramProfileResponse(TypedDict, total=False):
    user_id: str
    id: str
    username: str
    name: str
    account_type: str
    profile_picture_url: str


async def  exchange_code_for_token(code: str) -> InstagramTokenResponse:
    url = "https://api.instagram.com/oauth/access_token"

    data = {
        "client_id": cfg.INSTAGRAM_APP_ID,
        "client_secret": cfg.INSTAGRAM_APP_SECRET,
        "grant_type": "authorization_code",
        "redirect_uri": cfg.redirect_uri,
        "code": code,
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(url, data=data)

    if response.status_code >= 400:
        logger.error("exchange_code_for_token failed: %s", response.text)
        raise HTTPException(400, response.text)

    return cast(InstagramTokenResponse, response.json())

async def exchange_long_lived(short_lived_token: str) -> dict:
    url = "https://graph.instagram.com/access_token"

    params = {
        "grant_type": "ig_exchange_token",
        "client_secret": settings.INSTAGRAM_APP_SECRET,
        "access_token": short_lived_token,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url, params=params)

    try:
        data = response.json()

    except ValueError:
        logger.error(
            "exchange_long_lived failed: non-json response status=%s",
            response.status_code,
        )
        raise HTTPException(
            status_code=400,
            detail="Instagram returned non-json response",
        )

    if response.status_code >= 400:
        error = data.get("error", {})
        logger.error(
            "exchange_long_lived failed status=%s message=%s type=%s code=%s subcode=%s fbtrace_id=%s",
            response.status_code,
            error.get("message"),
            error.get("type"),
            error.get("code"),
            error.get("error_subcode"),
            error.get("fbtrace_id"),
        )

        raise HTTPException(
            status_code=400,
            detail={
                "message": error.get("message", "Instagram long-lived token exchange failed"),
                "type": error.get("type"),
                "code": error.get("code"),
                "subcode": error.get("error_subcode"),
                "fbtrace_id": error.get("fbtrace_id"),
            },
        )

    access_token = data.get("access_token")
    token_type = data.get("token_type", "bearer")
    expires_in = data.get("expires_in")

    if not access_token:
        logger.error("exchange_long_lived returned no access_token")
        raise HTTPException(
            status_code=400,
            detail="Instagram did not return long-lived access token",
        )

    if not expires_in:
        logger.warning("exchange_long_lived returned no expires_in")

    return {
        "access_token": access_token,
        "token_type": token_type,
        "expires_in": expires_in,
    }

async def get_me(token: str) -> InstagramProfileResponse:
    url = "https://graph.instagram.com/v25.0/me"

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            url,
            params={
                "fields": "user_id,username,name,account_type,profile_picture_url",
                "access_token": token,
            },
        )

        if response.status_code >= 400:
            logger.warning("get_me rich profile failed, retrying basic fields: %s", response.text)
            response = await client.get(
                url,
                params={
                    "fields": "user_id,username",
                    "access_token": token,
                },
            )

    if response.status_code >= 400:
        logger.error("get_me failed: %s", response.text)
        raise HTTPException(400, response.text)

    return cast(InstagramProfileResponse, response.json())

async def get_instagram_customer_profile(
    session: AsyncSession,
    sender_id: str,
    recipient_id: str,
) -> dict[str, Any] | None:
    company = await get_company_runtime(session, recipient_id)

    print(f"Sender ID: {sender_id}, Recipient ID: {recipient_id}")

    print("SENDING DATA")

    if not company:
        logger.warning(
            "Cannot fetch Instagram customer profile: company not found for recipient_id=%s",
            recipient_id,
        )
        return None

    access_token = company.get("access_token")

    if not access_token:
        logger.warning(
            "Cannot fetch Instagram customer profile: access token missing for recipient_id=%s",
            recipient_id,
        )
        return None

    url = f"https://graph.instagram.com/v25.0/{sender_id}"

    params = {
        "fields": "id,username,name",
        "access_token": str(access_token),
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(url, params=params)

    if response.status_code >= 400:
        logger.warning(
            "get_instagram_customer_profile failed sender_id=%s recipient_id=%s response=%s",
            sender_id,
            recipient_id,
            response.text,
        )
        return None

    return cast(dict[str, Any], response.json())