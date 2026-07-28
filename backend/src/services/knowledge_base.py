import uuid
from datetime import datetime, timezone
from typing import Literal, Mapping, cast

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from models.models import CompanyKnowledgeBaseEntry, InstagramCompany
from services.openai_messaging import create_embedding

KnowledgeEntryType = Literal["text", "product_photo"]
MAX_KNOWLEDGE_CONTEXT_CHARS = 3500
DEFAULT_KNOWLEDGE_LIMIT = 5


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _entry_mapping(entry: CompanyKnowledgeBaseEntry) -> Mapping[str, object]:
    return {
        "id": entry.id,
        "company_id": entry.company_id,
        "entry_type": entry.entry_type,
        "title": entry.title,
        "content": entry.content,
        "source_url": entry.source_url,
        "image_url": entry.image_url,
        "image_mime_type": entry.image_mime_type,
        "quantity_available": entry.quantity_available,
        "created_at": entry.created_at,
        "updated_at": entry.updated_at,
    }


def normalize_search_terms(query: str) -> list[str]:
    return [part.strip() for part in query.replace("\n", " ").split(" ") if len(part.strip()) >= 2][:8]


async def ensure_company_exists(db: AsyncSession, company_id: uuid.UUID) -> None:
    company = await db.get(InstagramCompany, company_id)
    if not company:
        raise ValueError("Company not found")


async def list_knowledge_entries(db: AsyncSession, company_id: uuid.UUID) -> list[Mapping[str, object]]:
    result = await db.execute(
        select(CompanyKnowledgeBaseEntry)
        .where(CompanyKnowledgeBaseEntry.company_id == company_id)
        .order_by(CompanyKnowledgeBaseEntry.updated_at.desc(), CompanyKnowledgeBaseEntry.created_at.desc())
    )
    return [_entry_mapping(entry) for entry in result.scalars().all()]


async def create_text_knowledge_entry(
    db: AsyncSession,
    company_id: uuid.UUID,
    title: str,
    content: str,
    source_url: str | None = None,
    quantity_available: int | None = None,
) -> Mapping[str, object]:
    now = now_utc()
    clean_title = title.strip()
    clean_content = content.strip()
    clean_source_url = source_url.strip() if source_url else None

    vector_data = await create_embedding(
        build_knowledge_embedding_text(entry_type="text", title=clean_title, content=clean_content)
    )

    entry = CompanyKnowledgeBaseEntry(
        id=uuid.uuid4(),
        company_id=company_id,
        entry_type="text",
        title=clean_title,
        content=clean_content,
        source_url=clean_source_url,
        quantity_available=quantity_available,
        embedding=vector_data,
        created_at=now,
        updated_at=now,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return _entry_mapping(entry)


async def create_photo_knowledge_entry(
    db: AsyncSession,
    company_id: uuid.UUID,
    title: str,
    image_url: str,
    image_mime_type: str,
    ai_description: str,
    quantity_available: int | None = None,
) -> Mapping[str, object]:
    now = now_utc()
    clean_title = title.strip()
    content = ai_description.strip() or "Описание товара по фотографии пока недоступно."

    vector_data = await create_embedding(
        build_knowledge_embedding_text(entry_type="product_photo", title=clean_title, content=content)
    )

    entry = CompanyKnowledgeBaseEntry(
        id=uuid.uuid4(),
        company_id=company_id,
        entry_type="product_photo",
        title=clean_title,
        content=content,
        image_url=image_url,
        image_mime_type=image_mime_type,
        quantity_available=quantity_available,
        embedding=vector_data,
        created_at=now,
        updated_at=now,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return _entry_mapping(entry)


def build_knowledge_embedding_text(entry_type: str, title: str, content: str) -> str:
    return "\n".join([
        f"Тип записи: {entry_type}",
        f"Название: {title.strip()}",
        f"{content.strip()}",
    ])


async def get_knowledge_entry(db: AsyncSession, company_id: uuid.UUID, entry_id: uuid.UUID) -> Mapping[str, object]:
    result = await db.execute(
        select(CompanyKnowledgeBaseEntry).where(
            CompanyKnowledgeBaseEntry.id == entry_id,
            CompanyKnowledgeBaseEntry.company_id == company_id,
        ).limit(1)
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise ValueError("Knowledge entry not found")
    return _entry_mapping(entry)


async def delete_knowledge_entry(db: AsyncSession, company_id: uuid.UUID, entry_id: uuid.UUID) -> None:
    result = await db.execute(
        delete(CompanyKnowledgeBaseEntry).where(
            CompanyKnowledgeBaseEntry.company_id == company_id,
            CompanyKnowledgeBaseEntry.id == entry_id,
        )
    )
    if result.rowcount == 0:
        raise ValueError("Knowledge entry not found")
    await db.commit()


async def find_relevant_knowledge_entries(
    db: AsyncSession,
    company_id: uuid.UUID,
    query: str,
    limit: int = 5,
) -> list[Mapping[str, object]]:
    # pgvector similarity ordering is not expressible cleanly through the current
    # model without a custom operator wrapper, so this is the one intentional raw
    # fragment left in this service.
    query_embedding = await create_embedding(query)
    query_embedding_sql = f"[{','.join(str(value) for value in query_embedding)}]"

    result = await db.execute(
        text(
            """
            select
                id,
                company_id,
                entry_type,
                title,
                content,
                source_url,
                image_url,
                image_mime_type,
                quantity_available,
                created_at,
                updated_at,
                1 - (embedding <=> CAST(:query_embedding AS vector)) as similarity
            from company_knowledge_base_entries
            where company_id = :company_id
              and embedding is not null
            order by embedding <=> CAST(:query_embedding AS vector)
            limit :limit
            """
        ),
        {"company_id": company_id, "query_embedding": query_embedding_sql, "limit": limit},
    )

    return [cast(Mapping[str, object], row) for row in result.mappings().all()]


def build_knowledge_context(entries: list[Mapping[str, object]]) -> str:
    if not entries:
        return ""

    chunks: list[str] = []
    total = 0
    for entry in entries:
        title = str(entry.get("title") or "Без названия")
        content = str(entry.get("content") or "").strip()
        quantity = entry.get("quantity_available")
        if not content:
            continue
        chunk = f"### {title}\n{content}"
        if quantity is not None:
            chunk += f"\nОстаток/stock quantity: {quantity}. If requested quantity is greater than this or stock is 0, clearly tell the customer that the requested amount is unavailable and offer only the available quantity."
        if total + len(chunk) > MAX_KNOWLEDGE_CONTEXT_CHARS:
            break
        chunks.append(chunk)
        total += len(chunk)

    return "\n\n".join(chunks)

