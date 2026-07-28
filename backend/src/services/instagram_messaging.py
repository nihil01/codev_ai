import logging
from typing import NotRequired, TypedDict, cast

import httpx

logger = logging.getLogger(__name__)


class InstagramSendMessageResponse(TypedDict):
    recipient_id: NotRequired[str]
    message_id: NotRequired[str]


async def send_message(
    instagram_account_id: str,
    access_token: str,
    recipient_id: str,
    text: str,
) -> InstagramSendMessageResponse:
    url = f"https://graph.instagram.com/v25.0/{instagram_account_id}/messages"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    body = {
        "recipient": {"id": recipient_id},
        "message": {"text": text},
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(url, headers=headers, json=body)

    if response.status_code >= 400:
        logger.error(
            "Instagram API send failed status=%s body=%s",
            response.status_code,
            response.text,
        )
        return {}

    result = response.json()
    logger.info("Instagram message sent to recipient_id=%s", recipient_id)
    return cast(InstagramSendMessageResponse, result)
