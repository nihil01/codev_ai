import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from services.chat_runtime import (
    fetch_recent_chat_history,
    get_company_runtime,
    persist_message,
)
from services.customer_orders import create_customer_order
from services.business_features import build_inventory_unavailable_reply, find_order_stock_conflict
from services.manager_notifications import notify_managers_about_order
from services.instagram_messaging import send_message
from services.knowledge_base import build_knowledge_context, find_relevant_knowledge_entries
from services.openai_messaging import generate_reply, detect_order_intent, hydrate_order_intent_customer_fields
from services.voice_transcription import extract_audio_url, is_audio_message_type, transcribe_audio_url
from services.conversation_control import (
    HANDOFF_INTENTS,
    can_bot_reply,
    classify_intent_from_order_intent,
    handoff_to_manager,
    notify_human_message,
    update_inbound_window,
    update_message_intent,
    mark_outbound_activity,
)

logger = logging.getLogger(__name__)

def build_order_confirmation_message(language: str | None) -> str:
    if language == "az":
        return (
            "Təşəkkür edirik, sifarişiniz qəbul olundu. "
            "Menecer tezliklə sizinlə əlaqə saxlayacaq."
        )

    if language == "ru":
        return (
            "Спасибо, заказ принят. "
            "Менеджер скоро свяжется с вами для подтверждения."
        )

    return "Thank you, your order has been accepted. A manager will contact you soon."


async def handle_message(
    event: dict,
    profile: dict[str, str] | None,
    session: AsyncSession,
) -> None:
    sender_id = event.get("sender", {}).get("id")
    recipient_id = event.get("recipient", {}).get("id")
    message = event.get("message", {})

    text_message = (message.get("text") or "").strip()
    mid = message.get("mid")
    is_echo = bool(message.get("is_echo"))
    message_type = str(message.get("type") or "").strip().lower()

    logger.info(
        "New Instagram event detected sender=%s recipient=%s mid=%s echo=%s",
        sender_id,
        recipient_id,
        mid,
        is_echo,
    )

    if not sender_id or not recipient_id:
        logger.warning("Skipping Instagram event without sender/recipient payload=%s", event)
        return

    if is_echo:
        logger.info("Skipping Instagram echo message mid=%s", mid)
        return

    if not text_message and (is_audio_message_type(message_type) or message.get("attachments")):
        audio_url = extract_audio_url(event)
        if audio_url:
            transcript = await transcribe_audio_url(audio_url)
            if transcript:
                text_message = transcript.strip()
                message["voice_transcription"] = text_message

    if not text_message:
        logger.info("Skipping non-text Instagram message mid=%s type=%s", mid, message_type)
        return

    if not mid:
        logger.warning("Skipping Instagram message without mid sender=%s recipient=%s", sender_id, recipient_id)
        return

    if sender_id == recipient_id:
        logger.warning("Blocked self-loop Instagram message sender=%s", sender_id)
        return

    company = await get_company_runtime(session, recipient_id)

    if not company:
        logger.warning("Unknown company for recipient instagram id=%s", recipient_id)
        return

    company_id = uuid.UUID(str(company["id"]))
    instagram_account_id = str(company["instagram_account_id"])
    access_token = str(company["access_token"])
    system_prompt = str(company["prompt_text"])

    customer_username = profile.get("username") if profile else None
    customer_name_from_profile = profile.get("name") if profile else None

    conversation_id = await persist_message(
        session,
        company_id=str(company_id),
        customer_id=sender_id,
        company_account_id=recipient_id,
        direction="inbound",
        text_message=text_message,
        instagram_mid=mid,
        payload=event,
        username=customer_username,
    )

    conversation_uuid = uuid.UUID(str(conversation_id))
    await update_inbound_window(
        session,
        channel="instagram",
        conversation_id=conversation_uuid,
    )

    history = await fetch_recent_chat_history(
        session,
        company_id=str(company_id),
        customer_id=sender_id,
    )

    knowledge_entries = await find_relevant_knowledge_entries(
        session,
        company_id=str(company_id),
        query=text_message,
    )

    knowledge_context = build_knowledge_context(knowledge_entries)

    order_intent = await detect_order_intent(
        user_text=text_message,
        history=history,
        knowledge_context=knowledge_context,
    )
    order_intent = hydrate_order_intent_customer_fields(
        order_intent,
        customer_name=customer_name_from_profile or customer_username,
        customer_phone=None,
    )
    stock_conflict = find_order_stock_conflict(
        product_title=order_intent.product_title,
        requested_quantity=order_intent.quantity,
        knowledge_entries=knowledge_entries,
    )

    logger.info(
        "Order intent detected mid=%s wants_order=%s ready_to_submit=%s missing_fields=%s",
        mid,
        order_intent.wants_order,
        order_intent.ready_to_submit,
        order_intent.missing_fields,
    )

    intent, intent_confidence = classify_intent_from_order_intent(order_intent, text_message)
    await update_message_intent(
        session,
        channel="instagram",
        company_id=company_id,
        external_message_id=mid,
        intent=intent,
        confidence=intent_confidence,
    )

    if not await can_bot_reply(session, channel="instagram", conversation_id=conversation_uuid):
        await notify_human_message(
            session,
            channel="instagram",
            conversation_id=conversation_uuid,
            text_message=text_message,
            customer_label=customer_name_from_profile or customer_username or sender_id,
        )
        await session.commit()
        logger.info("Instagram AI skipped: conversation is not in BOT mode or 24h window is closed conversation_id=%s", conversation_uuid)
        return

    if intent in HANDOFF_INTENTS and not order_intent.wants_order:
        await handoff_to_manager(
            session,
            channel="instagram",
            conversation_id=conversation_uuid,
            intent=intent,
            confidence=intent_confidence,
            source_message_id=mid,
            source_text=text_message,
            customer_label=customer_name_from_profile or customer_username or sender_id,
        )
        await session.commit()
        logger.info("Instagram conversation handed off to manager conversation_id=%s intent=%s", conversation_uuid, intent)
        return

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
            channel="instagram",
            customer_id=sender_id,
            conversation_id=conversation_id,
            source_message_id=mid,
            customer_name=order_intent.customer_name or customer_name_from_profile or customer_username,
            customer_phone=order_intent.customer_phone,
            product_title=order_intent.product_title,
            product_price=order_intent.product_price,
            quantity=order_intent.quantity,
            delivery_required=order_intent.delivery_required,
            delivery_address=order_intent.delivery_address,
            delivery_time=order_intent.delivery_time,
            customer_comment=order_intent.comment,
            raw_intent_payload=order_intent.model_dump(),
        )

        logger.info(
            "Customer order created order_id=%s company_id=%s channel=instagram mid=%s",
            order["id"],
            company_id,
            mid,
        )

        sent_to_managers = await notify_managers_about_order(
            session,
            order_id=order["id"],
        )

        logger.info(
            "Customer order manager notifications sent order_id=%s sent_count=%s",
            order["id"],
            sent_to_managers,
        )

        reply = build_order_confirmation_message(order_intent.detected_language)

    else:
        reply = generate_reply(
            system_prompt=system_prompt,
            user_text=text_message,
            history=history,
            knowledge_context=knowledge_context,
            order_intent=order_intent,
        )

    if not await can_bot_reply(session, channel="instagram", conversation_id=conversation_uuid):
        await session.commit()
        logger.info("Instagram AI send cancelled after recheck: conversation_id=%s", conversation_uuid)
        return

    send_result = await send_message(
        instagram_account_id=recipient_id,
        access_token=access_token,
        recipient_id=sender_id,
        text=reply,
    )

    await persist_message(
        session,
        company_id=str(company_id),
        customer_id=sender_id,
        company_account_id=recipient_id,
        direction="outbound",
        text_message=reply,
        instagram_mid=send_result.get("message_id"),
        payload=send_result,
        username=customer_username,
    )

    await mark_outbound_activity(
        session,
        channel="instagram",
        conversation_id=conversation_uuid,
        sender_type="bot",
    )
    await session.commit()

    logger.info(
        "Handled Instagram message mid=%s for company=%s",
        mid,
        instagram_account_id,
    )
