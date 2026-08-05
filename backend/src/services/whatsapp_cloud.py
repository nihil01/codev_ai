import json
import logging
import re
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Literal, Mapping, NotRequired, TypedDict, cast

import httpx
from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from config.app_config import settings
from models.models import User, WhatsAppCloudIntegration
from services.business_features import build_inventory_unavailable_reply, find_order_stock_conflict
from services.customer_orders import create_customer_order
from services.knowledge_base import build_knowledge_context, find_relevant_knowledge_entries
from services.intent_prompts import get_intent_prompt_text
from services.manager_notifications import notify_managers_about_order
from services.openai_messaging import detect_order_intent, generate_reply, hydrate_order_intent_customer_fields
from services.prompt_defaults import DEFAULT_SYSTEM_PROMPT_AZ
from services.subscriptions import check_usage_available, increment_usage, is_voice_payload
from services.voice_transcription import transcribe_whatsapp_cloud_audio


def _graph_url(path: str) -> str:
    return f"https://graph.facebook.com/{settings.meta_api_version}/{path}"

def generate_whatsapp_registration_pin() -> str:
    return "".join(str(secrets.randbelow(10)) for _ in range(6))

def validate_whatsapp_pin(pin: str) -> str:
    pin = pin.strip()

    if not re.fullmatch(r"\d{6}", pin):
        raise HTTPException(
            status_code=400,
            detail="PIN must be exactly 6 digits",
        )

    return pin

async def exchange_embedded_signup_code(code: str) -> str:
    request_data = {
        "client_id": settings.meta_app_id,
        "client_secret": settings.meta_app_secret,
        "code": code,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            _graph_url("oauth/access_token"),
            params=request_data,
        )

    if response.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "Failed to exchange WhatsApp Embedded Signup code",
                "status_code": response.status_code,
                "body": response.text,
            },
        )

    data = response.json()
    print(data)

    access_token = data.get("access_token")

    if not access_token:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "Meta did not return access_token",
                "body": data,
            },
        )

    return str(access_token)


async def fetch_phone_number_info(phone_number_id: str, access_token: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            _graph_url(f"/{phone_number_id}"),
            params={
                "fields": "display_phone_number,verified_name,quality_rating",
                "access_token": access_token,
            },
        )
    return response.json() if response.status_code < 400 else {}


async def subscribe_waba_to_webhooks(waba_id: str, access_token: str) -> bool:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            _graph_url(f"{waba_id}/subscribed_apps"),
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

    if response.status_code >= 400:
        print(
            "subscribe_waba_to_webhooks failed status=%s body=%s",
            response.status_code,
            response.text,
        )
        return False

    print(
        "WABA subscribed to webhooks successfully waba_id=%s response=%s",
        waba_id,
        response.text,
    )

    return True

async def register_whatsapp_cloud_phone_number(
    db: AsyncSession,
    integration_id: uuid.UUID,
    pin: str,
) -> dict[str, Any]:
    register_pin = validate_whatsapp_pin(pin)

    result = await db.execute(
        text(
            """
            select id, phone_number_id, access_token
            from whatsapp_cloud_integrations
            where id = :integration_id
              and disconnected_at is null
            limit 1
            """
        ),
        {"integration_id": integration_id},
    )

    row = result.mappings().first()

    if not row:
        raise HTTPException(
            status_code=404,
            detail="WhatsApp Cloud integration not found",
        )

    phone_number_id = str(row["phone_number_id"])
    access_token = str(row["access_token"])

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            _graph_url(f"{phone_number_id}/register"),
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json={
                "messaging_product": "whatsapp",
                "pin": register_pin,
            },
        )

    if response.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "Failed to register WhatsApp phone number",
                "status_code": response.status_code,
                "body": response.text,
            },
        )

    await db.execute(
        text(
            """
            update whatsapp_cloud_integrations
            set registration_pin = :pin,
                registered_at = now(),
                updated_at = now()
            where id = :integration_id
            """
        ),
        {
            "integration_id": integration_id,
            "pin": register_pin,
        },
    )

    await db.commit()

    return {
        "integration_id": str(integration_id),
        "phone_number_id": phone_number_id,
        "registered": True,
    }

def integration_to_response_row(
    integration: WhatsAppCloudIntegration,
    *,
    tenant_id: uuid.UUID,
) -> dict[str, Any]:
    connected = integration.disconnected_at is None
    registered = integration.registered_at is not None

    return {
        "id": integration.id,
        "whatsapp_integration_id": integration.id,
        "status": "connected" if connected else "disconnected",
        "tenant_id": tenant_id,
        "business_id": integration.meta_business_id,
        "waba_id": integration.waba_id,
        "phone_number_id": integration.phone_number_id,
        "display_phone_number": integration.display_phone_number,
        "verified_name": integration.verified_name,
        "quality_rating": integration.quality_rating,
        "webhook_subscribed": integration.webhook_subscribed,
        "connected": connected,
        "registered": registered,
        "pin_required": connected and not registered,
    }


async def _get_tenant_owner_user(db: AsyncSession, tenant_id: uuid.UUID) -> User:
    result = await db.execute(
        select(User)
        .where(
            User.instagram_company_id == tenant_id,
            User.is_active.is_(True),
        )
        .limit(1)
    )

    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="Client user for tenant not found",
        )

    return user


async def upsert_whatsapp_cloud_integration(
    db: AsyncSession,
    *,
    company_id: uuid.UUID,
    business_id: str | None,
    waba_id: str,
    phone_number_id: str,
    access_token: str,
    display_phone_number: str | None,
    verified_name: str | None,
    quality_rating: str | None,
    webhook_subscribed: bool,
) -> dict[str, Any]:
    owner = await _get_tenant_owner_user(db, company_id)
    now = datetime.now(timezone.utc)

    integration: WhatsAppCloudIntegration | None = None

    if owner.whatsapp_company_id:
        integration = await db.get(WhatsAppCloudIntegration, owner.whatsapp_company_id)

    if integration is None:
        result = await db.execute(
            select(WhatsAppCloudIntegration)
            .where(WhatsAppCloudIntegration.phone_number_id == phone_number_id)
            .limit(1)
        )
        integration = result.scalar_one_or_none()

    if integration is None:
        integration = WhatsAppCloudIntegration(
            meta_business_id=business_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            access_token=access_token,
            display_phone_number=display_phone_number,
            verified_name=verified_name,
            quality_rating=quality_rating,
            webhook_subscribed=webhook_subscribed,
            connected_at=now,
            disconnected_at=None,
            created_at=now,
            updated_at=now,
        )
        db.add(integration)
        await db.flush()
    else:
        integration.meta_business_id = business_id
        integration.waba_id = waba_id
        integration.phone_number_id = phone_number_id
        integration.access_token = access_token
        integration.display_phone_number = display_phone_number
        integration.verified_name = verified_name
        integration.quality_rating = quality_rating
        integration.webhook_subscribed = webhook_subscribed
        integration.connected_at = now
        integration.disconnected_at = None
        integration.updated_at = now

    owner.whatsapp_company_id = integration.id
    owner.wp_activated = True
    owner.updated_at = now

    await db.flush()
    response_row = integration_to_response_row(integration, tenant_id=company_id)

    await db.commit()

    return response_row


async def get_whatsapp_cloud_integration(db: AsyncSession, company_id: uuid.UUID) -> dict[str, Any] | None:
    owner = await _get_tenant_owner_user(db, company_id)
    if not owner.whatsapp_company_id:
        return None

    integration = await db.get(WhatsAppCloudIntegration, owner.whatsapp_company_id)
    if not integration:
        return None

    return integration_to_response_row(integration, tenant_id=company_id)


async def disconnect_whatsapp_cloud_integration(db: AsyncSession, company_id: uuid.UUID) -> None:
    owner = await _get_tenant_owner_user(db, company_id)
    now = datetime.now(timezone.utc)

    if owner.whatsapp_company_id:
        integration = await db.get(WhatsAppCloudIntegration, owner.whatsapp_company_id)
        if integration:
            integration.disconnected_at = now
            integration.updated_at = now

    owner.whatsapp_company_id = None
    owner.wp_activated = False
    owner.updated_at = now
    await db.commit()


logger = logging.getLogger(__name__)
MAX_HISTORY_MESSAGES = 10


class WhatsAppCloudRuntime(TypedDict):
    company_id: uuid.UUID
    integration_id: uuid.UUID
    phone_number_id: str
    waba_id: str | None
    display_phone_number: str | None
    access_token: str
    prompt_text: str


class WhatsAppCloudSendResponse(TypedDict):
    messaging_product: NotRequired[str]
    contacts: NotRequired[list[dict[str, Any]]]
    messages: NotRequired[list[dict[str, Any]]]


async def get_whatsapp_cloud_runtime_by_phone_number(
    session: AsyncSession,
    phone_number_id: str,
) -> WhatsAppCloudRuntime | None:
    result = await session.execute(
        text(
            """
            select
                c.id as company_id,
                w.id as integration_id,
                w.phone_number_id,
                w.waba_id,
                w.display_phone_number,
                w.access_token,
                coalesce(p.prompt_text, :default_prompt) as prompt_text
            from whatsapp_cloud_integrations w
            join users u on u.whatsapp_company_id = w.id
                and u.wp_activated = true
                and u.is_active = true
            join instagram_companies c on c.id = u.instagram_company_id
            left join instagram_system_prompts p on p.company_id = c.id
            where w.phone_number_id = :phone_number_id
              and w.disconnected_at is null
            order by p.version desc nulls last, p.updated_at desc nulls last
            limit 1
            """
        ),
        {
            "phone_number_id": phone_number_id,
            "default_prompt": DEFAULT_SYSTEM_PROMPT_AZ,
        },
    )
    row = result.mappings().first()
    if not row:
        logger.warning("WhatsApp Cloud runtime not found for phone_number_id=%s", phone_number_id)
        return None

    return WhatsAppCloudRuntime(
        company_id=cast(uuid.UUID, row["company_id"]),
        integration_id=cast(uuid.UUID, row["integration_id"]),
        phone_number_id=str(row["phone_number_id"]),
        waba_id=str(row["waba_id"]) if row["waba_id"] else None,
        display_phone_number=str(row["display_phone_number"]) if row["display_phone_number"] else None,
        access_token=str(row["access_token"]),
        prompt_text=str(row["prompt_text"]),
    )


def _parse_whatsapp_timestamp(timestamp: str | int | None) -> datetime:
    if timestamp is None:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromtimestamp(int(timestamp), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return datetime.now(timezone.utc)


async def persist_whatsapp_cloud_message(
    session: AsyncSession,
    *,
    company_id: uuid.UUID,
    integration_id: uuid.UUID,
    phone_number_id: str,
    waba_id: str | None,
    customer_id: str,
    customer_phone: str | None,
    customer_name: str | None,
    sender_id: str,
    recipient_id: str,
    direction: Literal["inbound", "outbound"],
    text_message: str,
    whatsapp_mid: str | None,
    message_type: str | None,
    has_media: bool,
    payload: Mapping[str, Any],
    sent_at: datetime | None = None,
) -> tuple[uuid.UUID, uuid.UUID | None]:
    now = datetime.now(timezone.utc)
    message_time = sent_at or now

    await session.execute(
        text(
            """
            insert into whatsapp_cloud_conversations (
                company_id,
                integration_id,
                phone_number_id,
                waba_id,
                customer_whatsapp_id,
                customer_phone,
                customer_name,
                last_message_at,
                created_at,
                updated_at
            ) values (
                :company_id,
                :integration_id,
                :phone_number_id,
                :waba_id,
                :customer_id,
                :customer_phone,
                :customer_name,
                :message_time,
                :now,
                :now
            )
            on conflict (company_id, integration_id, customer_whatsapp_id)
            do update set
                phone_number_id = excluded.phone_number_id,
                waba_id = excluded.waba_id,
                customer_phone = coalesce(excluded.customer_phone, whatsapp_cloud_conversations.customer_phone),
                customer_name = coalesce(excluded.customer_name, whatsapp_cloud_conversations.customer_name),
                last_message_at = greatest(
                    coalesce(whatsapp_cloud_conversations.last_message_at, excluded.last_message_at),
                    excluded.last_message_at
                ),
                updated_at = excluded.updated_at
            """
        ),
        {
            "company_id": company_id,
            "integration_id": integration_id,
            "phone_number_id": phone_number_id,
            "waba_id": waba_id,
            "customer_id": customer_id,
            "customer_phone": customer_phone,
            "customer_name": customer_name,
            "message_time": message_time,
            "now": now,
        },
    )

    conversation_result = await session.execute(
        text(
            """
            select id
            from whatsapp_cloud_conversations
            where company_id = :company_id
              and integration_id = :integration_id
              and customer_whatsapp_id = :customer_id
            limit 1
            """
        ),
        {
            "company_id": company_id,
            "integration_id": integration_id,
            "customer_id": customer_id,
        },
    )
    conversation_id = cast(uuid.UUID, conversation_result.scalar_one())

    usage_kind = "voice_message" if is_voice_payload(payload, message_type) else "text_message"
    await check_usage_available(session, company_id, usage_kind)

    message_result = await session.execute(
        text(
            """
            insert into whatsapp_cloud_messages (
                conversation_id,
                company_id,
                integration_id,
                whatsapp_mid,
                sender_whatsapp_id,
                recipient_whatsapp_id,
                direction,
                message_text,
                message_type,
                has_media,
                message_payload,
                sent_at,
                created_at
            ) values (
                :conversation_id,
                :company_id,
                :integration_id,
                :whatsapp_mid,
                :sender_id,
                :recipient_id,
                :direction,
                :message_text,
                :message_type,
                :has_media,
                cast(:message_payload as jsonb),
                :sent_at,
                :now
            )
            on conflict (company_id, whatsapp_mid) where whatsapp_mid is not null do nothing
            returning id
            """
        ),
        {
            "conversation_id": conversation_id,
            "company_id": company_id,
            "integration_id": integration_id,
            "whatsapp_mid": whatsapp_mid,
            "sender_id": sender_id,
            "recipient_id": recipient_id,
            "direction": direction,
            "message_text": text_message,
            "message_type": message_type,
            "has_media": has_media,
            "message_payload": json.dumps(payload, ensure_ascii=False),
            "sent_at": message_time,
            "now": now,
        },
    )
    message_id = cast(uuid.UUID | None, message_result.scalar_one_or_none())
    if message_id is not None:
        await increment_usage(session, company_id, usage_kind)
    await session.commit()
    return conversation_id, message_id


async def fetch_recent_whatsapp_cloud_history(
    session: AsyncSession,
    *,
    company_id: uuid.UUID,
    integration_id: uuid.UUID,
    customer_id: str,
    limit: int = MAX_HISTORY_MESSAGES,
) -> list[dict[str, str]]:
    result = await session.execute(
        text(
            """
            select direction, message_text
            from whatsapp_cloud_messages m
            join whatsapp_cloud_conversations c on c.id = m.conversation_id
            where m.company_id = :company_id
              and m.integration_id = :integration_id
              and c.customer_whatsapp_id = :customer_id
              and m.message_text is not null
            order by m.created_at desc
            limit :limit
            """
        ),
        {
            "company_id": company_id,
            "integration_id": integration_id,
            "customer_id": customer_id,
            "limit": limit,
        },
    )

    history: list[dict[str, str]] = []
    for row in reversed(result.mappings().all()):
        role = "user" if row["direction"] == "inbound" else "assistant"
        history.append({"role": role, "content": str(row["message_text"] or "")})
    return history


async def send_whatsapp_cloud_message(
    *,
    phone_number_id: str,
    access_token: str,
    recipient_id: str,
    text_message: str,
) -> WhatsAppCloudSendResponse:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            _graph_url(f"{phone_number_id}/messages"),
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json={
                "messaging_product": "whatsapp",
                "to": recipient_id,
                "type": "text",
                "text": {"preview_url": False, "body": text_message},
            },
        )

    if response.status_code >= 400:
        logger.error("WhatsApp Cloud send failed status=%s body=%s", response.status_code, response.text)
        return {}

    return cast(WhatsAppCloudSendResponse, response.json())


def _extract_sent_message_id(send_result: Mapping[str, Any]) -> str | None:
    messages = send_result.get("messages")
    if isinstance(messages, list) and messages:
        first = messages[0]
        if isinstance(first, dict) and first.get("id"):
            return str(first["id"])
    return None


def build_order_confirmation_message(language: str | None) -> str:
    if language == "az":
        return "Təşəkkür edirik, sifarişiniz qəbul olundu. Menecer tezliklə sizinlə əlaqə saxlayacaq."
    if language == "ru":
        return "Спасибо, заказ принят. Менеджер скоро свяжется с вами для подтверждения."
    return "Thank you, your order has been accepted. A manager will contact you soon."


async def handle_whatsapp_cloud_text_message(
    session: AsyncSession,
    *,
    runtime: WhatsAppCloudRuntime,
    message: Mapping[str, Any],
    contact: Mapping[str, Any] | None,
    raw_value: Mapping[str, Any],
) -> None:
    message_type = str(message.get("type") or "")
    text_payload = message.get("text") if isinstance(message.get("text"), Mapping) else {}
    text_message = str(text_payload.get("body") or "").strip() if isinstance(text_payload, Mapping) else ""
    mid = str(message.get("id") or "").strip()
    sender_id = str(message.get("from") or "").strip()

    if not mid or not sender_id:
        logger.warning("Skipping WhatsApp Cloud message without id/from payload=%s", message)
        return

    if message_type in {"audio", "voice"} and not text_message:
        transcript = await transcribe_whatsapp_cloud_audio(message, access_token=runtime["access_token"])
        if transcript:
            text_message = transcript.strip()

    if message_type != "text" and not text_message:
        logger.info("Persisting non-text WhatsApp Cloud message without AI reply mid=%s type=%s", mid, message_type)

    profile = contact.get("profile") if contact else None
    customer_name = None
    if isinstance(profile, Mapping) and profile.get("name"):
        customer_name = str(profile["name"])
    customer_phone = str(contact.get("wa_id")) if contact and contact.get("wa_id") else sender_id

    company_id = runtime["company_id"]
    integration_id = runtime["integration_id"]
    phone_number_id = runtime["phone_number_id"]

    conversation_id, inserted_message_id = await persist_whatsapp_cloud_message(
        session,
        company_id=company_id,
        integration_id=integration_id,
        phone_number_id=phone_number_id,
        waba_id=runtime["waba_id"],
        customer_id=sender_id,
        customer_phone=customer_phone,
        customer_name=customer_name,
        sender_id=sender_id,
        recipient_id=phone_number_id,
        direction="inbound",
        text_message=text_message,
        whatsapp_mid=mid,
        message_type=message_type or None,
        has_media=message_type not in {"", "text"},
        payload={"message": dict(message), "value": dict(raw_value), "voice_transcription": text_message if message_type in {"audio", "voice"} else None},
        sent_at=_parse_whatsapp_timestamp(cast(str | int | None, message.get("timestamp"))),
    )

    if inserted_message_id is None:
        logger.info("Skipping duplicate WhatsApp Cloud message mid=%s", mid)
        return

    if not text_message:
        return

    history = await fetch_recent_whatsapp_cloud_history(
        session,
        company_id=company_id,
        integration_id=integration_id,
        customer_id=sender_id,
    )

    knowledge_entries = await find_relevant_knowledge_entries(
        session,
        company_id=company_id,
        query=text_message,
    )
    knowledge_context = build_knowledge_context(knowledge_entries)

    order_intent = await detect_order_intent(
        user_text=text_message,
        history=history,
        knowledge_context=knowledge_context,
        system_prompt=await get_intent_prompt_text(session, company_id),
    )
    order_intent = hydrate_order_intent_customer_fields(
        order_intent,
        customer_name=customer_name,
        customer_phone=customer_phone or sender_id,
    )
    stock_conflict = find_order_stock_conflict(
        product_title=order_intent.product_title,
        requested_quantity=order_intent.quantity,
        knowledge_entries=knowledge_entries,
    )

    if order_intent.wants_order and stock_conflict:
        product_title, requested_quantity, available_quantity = stock_conflict
        reply = build_inventory_unavailable_reply(
            language=order_intent.detected_language,
            product_title=product_title,
            requested_quantity=requested_quantity,
            available_quantity=available_quantity,
        )
    elif order_intent.wants_order and not order_intent.ready_to_submit and order_intent.next_question:
        reply = order_intent.next_question
    elif order_intent.wants_order and order_intent.ready_to_submit:
        order = await create_customer_order(
            db=session,
            company_id=company_id,
            channel="whatsapp",
            customer_id=sender_id,
            conversation_id=conversation_id,
            source_message_id=mid,
            customer_name=order_intent.customer_name or customer_name,
            customer_phone=order_intent.customer_phone or customer_phone,
            product_title=order_intent.product_title,
            product_price=order_intent.product_price,
            quantity=order_intent.quantity,
            delivery_required=order_intent.delivery_required,
            delivery_address=order_intent.delivery_address,
            delivery_time=order_intent.delivery_time,
            customer_comment=order_intent.comment,
            raw_intent_payload=order_intent.model_dump(),
        )
        await notify_managers_about_order(session, order_id=order["id"])
        reply = build_order_confirmation_message(order_intent.detected_language)
    else:
        reply = generate_reply(
            system_prompt=runtime["prompt_text"],
            user_text=text_message,
            history=history,
            knowledge_context=knowledge_context,
            order_intent=order_intent,
        )

    send_result = await send_whatsapp_cloud_message(
        phone_number_id=phone_number_id,
        access_token=runtime["access_token"],
        recipient_id=sender_id,
        text_message=reply,
    )

    await persist_whatsapp_cloud_message(
        session,
        company_id=company_id,
        integration_id=integration_id,
        phone_number_id=phone_number_id,
        waba_id=runtime["waba_id"],
        customer_id=sender_id,
        customer_phone=customer_phone,
        customer_name=customer_name,
        sender_id=phone_number_id,
        recipient_id=sender_id,
        direction="outbound",
        text_message=reply,
        whatsapp_mid=_extract_sent_message_id(send_result),
        message_type="text",
        has_media=False,
        payload=send_result,
    )


async def handle_whatsapp_cloud_webhook_payload(
    session: AsyncSession,
    payload: Mapping[str, Any],
) -> None:
    for entry in payload.get("entry", []) if isinstance(payload.get("entry"), list) else []:
        changes = entry.get("changes", []) if isinstance(entry, Mapping) else []
        if not isinstance(changes, list):
            continue
        for change in changes:
            if not isinstance(change, Mapping):
                continue
            value = change.get("value")
            if not isinstance(value, Mapping):
                continue

            metadata = value.get("metadata") if isinstance(value.get("metadata"), Mapping) else {}
            phone_number_id = str(metadata.get("phone_number_id") or "").strip() if isinstance(metadata, Mapping) else ""
            if not phone_number_id:
                logger.info("Skipping WhatsApp Cloud change without phone_number_id")
                continue

            runtime = await get_whatsapp_cloud_runtime_by_phone_number(session, phone_number_id)
            if not runtime:
                continue

            contacts_by_wa_id: dict[str, Mapping[str, Any]] = {}
            contacts = value.get("contacts")
            if isinstance(contacts, list):
                for contact in contacts:
                    if isinstance(contact, Mapping) and contact.get("wa_id"):
                        contacts_by_wa_id[str(contact["wa_id"])] = contact

            messages = value.get("messages")
            if not isinstance(messages, list):
                continue

            for message in messages:
                if not isinstance(message, Mapping):
                    continue
                sender_id = str(message.get("from") or "")
                await handle_whatsapp_cloud_text_message(
                    session,
                    runtime=runtime,
                    message=message,
                    contact=contacts_by_wa_id.get(sender_id),
                    raw_value=value,
                )
