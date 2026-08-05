from __future__ import annotations

import uuid
from typing import Any, Mapping, cast

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config.app_config import settings

DEFAULT_INTENT_PROMPT = settings.order_intent_sys_prompt.strip()


def resolve_intent_prompt(value: str | None) -> str:
    normalized = (value or "").strip()
    return normalized or DEFAULT_INTENT_PROMPT


async def load_intent_prompt(db: AsyncSession, company_id: uuid.UUID) -> Mapping[str, Any] | None:
    result = await db.execute(
        text(
            """
            select c.id as company_id,
                   c.display_name,
                   c.instagram_username as username,
                   coalesce(p.title, 'Söhbət intenti promptu') as title,
                   coalesce(p.prompt_text, :default_prompt) as prompt_text,
                   coalesce(p.version, 1) as version
            from instagram_companies c
            left join company_intent_prompts p on p.company_id = c.id
            where c.id = :company_id
            limit 1
            """
        ),
        {"company_id": company_id, "default_prompt": DEFAULT_INTENT_PROMPT},
    )
    return cast(Mapping[str, Any] | None, result.mappings().first())


async def get_intent_prompt_text(db: AsyncSession, company_id: uuid.UUID) -> str:
    row = await load_intent_prompt(db, company_id)
    return resolve_intent_prompt(str(row["prompt_text"]) if row else None)


async def upsert_intent_prompt(
    db: AsyncSession,
    company_id: uuid.UUID,
    *,
    title: str | None,
    prompt_text: str,
) -> Mapping[str, Any] | None:
    normalized_prompt = resolve_intent_prompt(prompt_text)
    normalized_title = (title or "").strip() or "Söhbət intenti promptu"
    result = await db.execute(
        text(
            """
            insert into company_intent_prompts (company_id, title, prompt_text)
            select id, :title, :prompt_text
            from instagram_companies
            where id = :company_id
            on conflict (company_id) do update set
                title = excluded.title,
                prompt_text = excluded.prompt_text,
                version = company_intent_prompts.version + 1,
                updated_at = now()
            returning company_id
            """
        ),
        {"company_id": company_id, "title": normalized_title, "prompt_text": normalized_prompt},
    )
    if result.scalar_one_or_none() is None:
        return None
    await db.commit()
    return await load_intent_prompt(db, company_id)
