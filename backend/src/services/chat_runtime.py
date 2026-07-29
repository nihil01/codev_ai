import json
import logging
from datetime import datetime, timezone
from typing import Mapping, TypedDict

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from models.auxilary_models import *
from services.prompt_defaults import DEFAULT_SYSTEM_PROMPT_AZ
from services.subscriptions import check_usage_available, increment_usage, is_voice_payload
from services.security import validate_text_message, MAX_TEXT_LENGTH

logger = logging.getLogger(__name__)


MAX_HISTORY_MESSAGES = 10
MAX_PROMPT_LENGTH = 3000


class CompanyRuntime(TypedDict):
    id: object
    instagram_account_id: str
    username: str | None
    access_token: str
    prompt_text: str


class CompanyLookup(TypedDict):
    id: object
    instagram_account_id: str
    username: str | None


class ChatHistoryMessage(TypedDict):
    role: Literal["user", "assistant"]
    content: str


async def get_company_runtime(session: AsyncSession, instagram_account_id: str) -> CompanyRuntime | None:
    query = text(
        """
        select
            c.id,
            c.instagram_account_id,
            c.instagram_username as username,
            t.access_token,
            coalesce(p.prompt_text, :default_prompt) as prompt_text
        from instagram_companies c
        join users u on u.instagram_company_id = c.id and u.ig_activated = true and u.is_active = true
        join instagram_tokens t on t.company_id = c.id and t.is_active = true
        left join lateral (
            select prompt_text
            from instagram_system_prompts
            where company_id = c.id
            order by version desc, updated_at desc
            limit 1
        ) p on true
        where c.instagram_account_id = :id
        limit 1
        """
    )

    result = await session.execute(
        query,
        {
            "id": instagram_account_id,
            "default_prompt": DEFAULT_SYSTEM_PROMPT_AZ,
        },
    )
    company = result.mappings().first()
    if not company:
        logger.warning("Company runtime not found for instagram_account_id=%s", instagram_account_id)
        return None

    return CompanyRuntime(
        id=company["id"],
        instagram_account_id=str(company["instagram_account_id"]),
        username=str(company["username"]) if company["username"] else None,
        access_token=str(company["access_token"]),
        prompt_text=str(company["prompt_text"]),
    )


async def get_company_by_username(session: AsyncSession, username: str) -> CompanyLookup | None:
    result = await session.execute(
        text(
            """
            select id, instagram_account_id, instagram_username as username
            from instagram_companies
            where lower(instagram_username) = lower(:username)
            limit 1
            """
        ),
        {"username": username.strip()},
    )
    row = result.mappings().first()
    if not row:
        return None

    return CompanyLookup(
        id=row["id"],
        instagram_account_id=str(row["instagram_account_id"]),
        username=str(row["username"]) if row["username"] else None,
    )


async def set_active_prompt_by_username(
    session: AsyncSession,
    username: str,
    prompt_text: str,
    title: str = "Client prompt",
) -> bool:
    company = await get_company_by_username(session, username)
    if not company:
        return False

    now = datetime.now(timezone.utc)

    await session.execute(
        text(
            """
            update instagram_system_prompts
            setupdated_at = :now
            where company_id = :company_id
            """
        ),
        {"company_id": company["id"], "now": now},
    )

    await session.execute(
        text(
            """
            insert into instagram_system_prompts (
                company_id,
                title,
                prompt_text,
                version,
                created_at,
                updated_at
            )
            values (
                :company_id,
                :title,
                :prompt_text,
                coalesce((
                    select max(version) + 1
                    from instagram_system_prompts
                    where company_id = :company_id
                ), 1),
                :now,
                :now
            )
            """
        ),
        {
            "company_id": company["id"],
            "title": title,
            "prompt_text": prompt_text,
            "now": now,
        },
    )

    await session.commit()
    logger.info("Updated active system prompt for username=%s", username)
    return True


async def persist_message(
    session: AsyncSession,
    *,
    company_id: str,
    customer_id: str,
    company_account_id: str,
    direction: str,
    text_message: str,
    instagram_mid: str | None,
    payload: Mapping[str, object],
    username: str | None,
    sent_at: datetime | None = None,
    sender_type: str | None = None,
    manager_id: str | None = None,
) -> object:
    # Validate and truncate text message
    text_message = validate_text_message(text_message)

    now = datetime.now(timezone.utc)
    message_time = sent_at or now

    await session.execute(
        text(
            """
            insert into instagram_conversations (
                company_id,
                customer_instagram_id,
                customer_username,
                last_message_at,
                created_at,
                updated_at
            )
            values (:company_id, :customer_id, :customer_username, :now, :now, :now)
            on conflict (company_id, customer_instagram_id)
            do update set
                last_message_at = excluded.last_message_at,
                updated_at = excluded.updated_at
            """
        ),
        {
            "company_id": company_id,
            "customer_id": customer_id,
            "customer_username": username,
            "now": message_time,
        },
    )

    conversation_result = await session.execute(
        text(
            """
            select id from instagram_conversations
            where company_id = :company_id and customer_instagram_id = :customer_id
            limit 1
            """
        ),
        {"company_id": company_id, "customer_id": customer_id},
    )
    conversation_id = conversation_result.scalar_one()

    sender_id = customer_id if direction == "inbound" else company_account_id
    recipient_id = company_account_id if direction == "inbound" else customer_id

    usage_kind = "voice_message" if is_voice_payload(payload) else "text_message"
    await check_usage_available(session, company_id, usage_kind)

    message_insert = await session.execute(
        text(
            """
            insert into instagram_messages (
                conversation_id,
                company_id,
                instagram_mid,
                sender_instagram_id,
                recipient_instagram_id,
                direction,
                message_text,
                message_payload,
                sent_at,
                created_at,
                sender_type,
                manager_id,
                external_message_id
            )
            values (
                :conversation_id,
                :company_id,
                :instagram_mid,
                :sender_id,
                :recipient_id,
                :direction,
                :message_text,
                cast(:message_payload as jsonb),
                :now,
                :now,
                :sender_type,
                :manager_id,
                :external_message_id
            )
            on conflict (company_id, instagram_mid) do nothing
            returning id
            """
        ),
        {
            "conversation_id": conversation_id,
            "company_id": company_id,
            "instagram_mid": instagram_mid,
            "external_message_id": instagram_mid,
            "sender_id": sender_id,
            "recipient_id": recipient_id,
            "direction": direction,
            "message_text": text_message,
            "message_payload": json.dumps(payload, ensure_ascii=False),
            "sender_type": sender_type or ("customer" if direction == "inbound" else "bot"),
            "manager_id": manager_id,
            "now": message_time,
        },
    )

    if message_insert.scalar_one_or_none() is not None:
        await increment_usage(session, company_id, usage_kind)

    await session.commit()
    return conversation_id


async def fetch_recent_chat_history(
    session: AsyncSession,
    *,
    company_id: str,
    customer_id: str,
    limit: int = MAX_HISTORY_MESSAGES,
) -> list[ChatHistoryMessage]:
    result = await session.execute(
        text(
            """
            select direction, message_text
            from instagram_messages m
            join instagram_conversations c on c.id = m.conversation_id
            where m.company_id = :company_id
              and c.customer_instagram_id = :customer_id
              and m.message_text is not null
            order by m.created_at desc
            limit :limit
            """
        ),
        {"company_id": company_id, "customer_id": customer_id, "limit": limit},
    )

    history: list[ChatHistoryMessage] = []
    for row in reversed(result.mappings().all()):
        role: Literal["user", "assistant"] = "user" if row["direction"] == "inbound" else "assistant"
        history.append({"role": role, "content": str(row["message_text"] or "")})

    return history
