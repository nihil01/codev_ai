import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from config.app_config import settings
from config.deps import get_db
from services.channel_integrations import get_instagram_provider, get_whatsapp_provider
from routers.zernio_webhook import handle_zernio_webhook_request

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/webhooks")
@router.get("/webhook")
async def verify(hub_mode: str, hub_challenge: str, hub_verify_token: str):
    if hub_mode != "subscribe":
        raise HTTPException(status_code=400, detail="Invalid hub.mode")

    if hub_verify_token != settings.VERIFY_TOKEN:
        raise HTTPException(403)

    logger.info("Webhook verification succeeded")
    return PlainTextResponse(hub_challenge)


@router.post("/webhooks")
async def webhook_wp(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    # Older Zernio registrations may still target /webhooks. Dispatch by the
    # signed provider header instead of treating that payload as Meta Cloud.
    if request.headers.get("x-zernio-signature"):
        return await handle_zernio_webhook_request(request, path="", db=db)

    body = await request.body()
    signature = request.headers.get("x-hub-signature-256")

    logger.info("New WhatsApp Meta webhook event")

    provider = get_whatsapp_provider()

    if not signature:
        logger.warning("Missing webhook signature header")
        raise HTTPException(status_code=400)

    if not provider.verify_webhook_signature(body, signature):
        logger.warning("WhatsApp webhook signature verification failed provider=%s", provider.provider_name)
        raise HTTPException(status_code=403)

    payload = await request.json()

    result = await provider.handle_webhook_payload(db, payload)

    return {"ok": True, "provider": result.provider, "handled": result.handled, "skipped": result.skipped}

@router.post("/webhook")
async def webhook_ig(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    body = await request.body()
    signature = request.headers.get("x-hub-signature-256")

    print("New IG event!")

    provider = get_instagram_provider()

    if not signature:
        logger.warning("Missing webhook signature header")
        raise HTTPException(status_code=400)

    if not provider.verify_webhook_signature(body, signature):
        logger.warning("Instagram webhook signature verification failed provider=%s", provider.provider_name)
        raise HTTPException(status_code=403)

    payload = await request.json()
    result = await provider.handle_webhook_payload(db, payload)

    return {"ok": True, "provider": result.provider, "handled": result.handled, "skipped": result.skipped}