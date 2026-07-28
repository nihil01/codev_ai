import uuid
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any, Literal, cast

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from services.chat_runtime import persist_message
from services.instagram_messaging import send_message as send_instagram_message
from services.whatsapp_cloud import persist_whatsapp_cloud_message, send_whatsapp_cloud_message

BroadcastTarget = Literal["instagram", "whatsapp", "both"]
BroadcastChannel = Literal["instagram", "whatsapp"]


def _normalize_target(value: str) -> BroadcastTarget:
    if value not in {"instagram", "whatsapp", "both"}:
        raise ValueError("Unsupported broadcast target")
    return cast(BroadcastTarget, value)


def _extract_whatsapp_message_id(send_result: Mapping[str, Any]) -> str | None:
    messages = send_result.get("messages")
    if isinstance(messages, list) and messages:
        first = messages[0]
        if isinstance(first, Mapping) and first.get("id"):
            return str(first["id"])
    return None


async def list_broadcast_campaigns(db: AsyncSession, company_id: uuid.UUID) -> list[Mapping[str, Any]]:
    result = await db.execute(
        text(
            """
            select id, company_id, target, message_text, status, requested_count, sent_count, failed_count,
                   created_at, updated_at, completed_at
            from broadcast_campaigns
            where company_id = :company_id
            order by created_at desc
            limit 50
            """
        ),
        {"company_id": company_id},
    )
    return [cast(Mapping[str, Any], row) for row in result.mappings().all()]


async def _load_instagram_recipients(db: AsyncSession, company_id: uuid.UUID) -> list[Mapping[str, Any]]:
    result = await db.execute(
        text(
            """
            select distinct on (customer_instagram_id)
                'instagram'::text as channel,
                id as conversation_id,
                customer_instagram_id::text as recipient_id
            from instagram_conversations
            where company_id = :company_id
              and customer_instagram_id is not null
              and customer_instagram_id <> ''
            order by customer_instagram_id, coalesce(last_message_at, created_at) desc
            """
        ),
        {"company_id": company_id},
    )
    return [cast(Mapping[str, Any], row) for row in result.mappings().all()]


async def _load_whatsapp_recipients(db: AsyncSession, company_id: uuid.UUID) -> list[Mapping[str, Any]]:
    result = await db.execute(
        text(
            """
            select distinct on (c.customer_whatsapp_id)
                'whatsapp'::text as channel,
                c.id as conversation_id,
                c.customer_whatsapp_id::text as recipient_id,
                c.customer_phone::text as customer_phone,
                c.customer_name::text as customer_name,
                c.integration_id,
                i.phone_number_id::text as phone_number_id,
                i.waba_id::text as waba_id,
                i.access_token::text as access_token
            from whatsapp_cloud_conversations c
            join whatsapp_cloud_integrations i on i.id = c.integration_id
            where c.company_id = :company_id
              and c.customer_whatsapp_id is not null
              and c.customer_whatsapp_id <> ''
              and i.disconnected_at is null
              and i.registered_at is not null
            order by c.customer_whatsapp_id, coalesce(c.last_message_at, c.created_at) desc
            """
        ),
        {"company_id": company_id},
    )
    return [cast(Mapping[str, Any], row) for row in result.mappings().all()]


async def _load_recipients(
    db: AsyncSession,
    company_id: uuid.UUID,
    target: BroadcastTarget,
) -> list[Mapping[str, Any]]:
    recipients: list[Mapping[str, Any]] = []

    if target in {"instagram", "both"}:
        recipients.extend(await _load_instagram_recipients(db, company_id))

    if target in {"whatsapp", "both"}:
        recipients.extend(await _load_whatsapp_recipients(db, company_id))

    return recipients


async def create_and_send_broadcast(
    db: AsyncSession,
    *,
    company_id: uuid.UUID,
    target: str,
    message_text: str,
) -> Mapping[str, Any]:
    normalized_target = _normalize_target(target)
    campaign_id = uuid.uuid4()

    company_result = await db.execute(
        text(
            """
            select c.id, c.instagram_account_id, t.access_token
            from instagram_companies c
            left join instagram_tokens t on t.company_id = c.id and t.is_active = true
            where c.id = :company_id
            order by t.updated_at desc nulls last
            limit 1
            """
        ),
        {"company_id": company_id},
    )
    company = company_result.mappings().first()
    if not company:
        raise ValueError("Client space not found")

    recipients = await _load_recipients(db, company_id, normalized_target)

    await db.execute(
        text(
            """
            insert into broadcast_campaigns (
                id, company_id, target, message_text, status, requested_count, sent_count, failed_count,
                created_at, updated_at
            ) values (
                :id, :company_id, :target, :message_text, 'running', :requested_count, 0, 0,
                now(), now()
            )
            """
        ),
        {
            "id": campaign_id,
            "company_id": company_id,
            "target": normalized_target,
            "message_text": message_text,
            "requested_count": len(recipients),
        },
    )
    await db.commit()

    sent_count = 0
    failed_count = 0

    for recipient in recipients:
        channel = cast(BroadcastChannel, str(recipient["channel"]))
        conversation_id = cast(uuid.UUID | None, recipient.get("conversation_id"))
        recipient_id = str(recipient["recipient_id"])
        status = "failed"
        external_message_id: str | None = None
        error_text: str | None = None

        try:
            if channel == "instagram":
                if not company.get("access_token"):
                    raise RuntimeError("Instagram token is not active")

                send_result = await send_instagram_message(
                    instagram_account_id=str(company["instagram_account_id"]),
                    access_token=str(company["access_token"]),
                    recipient_id=recipient_id,
                    text=message_text,
                )
                external_message_id = send_result.get("message_id")
                await persist_message(
                    db,
                    company_id=str(company_id),
                    customer_id=recipient_id,
                    company_account_id=str(company["instagram_account_id"]),
                    direction="outbound",
                    text_message=message_text,
                    instagram_mid=external_message_id,
                    payload={"broadcast_campaign_id": str(campaign_id), "send_result": send_result},
                    username=recipient_id,
                )
            else:
                send_result = await send_whatsapp_cloud_message(
                    phone_number_id=str(recipient["phone_number_id"]),
                    access_token=str(recipient["access_token"]),
                    recipient_id=recipient_id,
                    text_message=message_text,
                )
                external_message_id = _extract_whatsapp_message_id(send_result)
                if not external_message_id:
                    raise RuntimeError("WhatsApp Cloud did not return message id")

                await persist_whatsapp_cloud_message(
                    db,
                    company_id=company_id,
                    integration_id=cast(uuid.UUID, recipient["integration_id"]),
                    phone_number_id=str(recipient["phone_number_id"]),
                    waba_id=str(recipient["waba_id"]) if recipient.get("waba_id") else None,
                    customer_id=recipient_id,
                    customer_phone=str(recipient["customer_phone"]) if recipient.get("customer_phone") else None,
                    customer_name=str(recipient["customer_name"]) if recipient.get("customer_name") else None,
                    sender_id=str(recipient["phone_number_id"]),
                    recipient_id=recipient_id,
                    direction="outbound",
                    text_message=message_text,
                    whatsapp_mid=external_message_id,
                    message_type="text",
                    has_media=False,
                    payload={"broadcast_campaign_id": str(campaign_id), "send_result": send_result},
                )

            status = "sent"
            sent_count += 1
        except Exception as exc:  # noqa: BLE001 - per-recipient failure is tracked
            error_text = str(exc)[:1000]
            failed_count += 1

        now = datetime.now(timezone.utc)
        sent_at = now if status == "sent" else None

        await db.execute(
            text(
                """
                insert into broadcast_recipients (id,
                                                  campaign_id,
                                                  company_id,
                                                  channel,
                                                  recipient_id,
                                                  conversation_id,
                                                  status,
                                                  external_message_id,
                                                  error_text,
                                                  created_at,
                                                  sent_at)
                values (:id,
                        :campaign_id,
                        :company_id,
                        :channel,
                        :recipient_id,
                        :conversation_id,
                        :status,
                        :external_message_id,
                        :error_text,
                        :now,
                        :sent_at)
                on conflict (campaign_id, channel, recipient_id) do nothing
                """
            ),
            {
                "id": uuid.uuid4(),
                "campaign_id": campaign_id,
                "company_id": company_id,
                "channel": channel,
                "recipient_id": recipient_id,
                "conversation_id": conversation_id,
                "status": status,
                "external_message_id": external_message_id,
                "error_text": error_text,
                "now": now,
                "sent_at": sent_at,
            },
        )

        await db.commit()

    final_status = "completed"
    if failed_count and sent_count:
        final_status = "partial"
    elif failed_count and not sent_count:
        final_status = "failed"

    result = await db.execute(
        text(
            """
            update broadcast_campaigns
            set status = :status,
                sent_count = :sent_count,
                failed_count = :failed_count,
                updated_at = now(),
                completed_at = now()
            where id = :campaign_id and company_id = :company_id
            returning id, company_id, target, message_text, status, requested_count, sent_count, failed_count,
                      created_at, updated_at, completed_at
            """
        ),
        {
            "campaign_id": campaign_id,
            "company_id": company_id,
            "status": final_status,
            "sent_count": sent_count,
            "failed_count": failed_count,
        },
    )
    await db.commit()
    return cast(Mapping[str, Any], result.mappings().one())
