from __future__ import annotations

import html
import io
import json
import uuid
import zipfile
from datetime import datetime
from typing import Any, Iterable, Mapping, Sequence, cast

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

LEAD_STATUSES = (
    "new",
    "interested",
    "contacted",
    "qualified",
    "enrolled",
    "not_interested",
    "lost",
    "archived",
)
LEAD_PLATFORMS = ("instagram", "facebook", "tiktok", "whatsapp", "manual")
LEAD_SOURCES = (
    "instagram_dm",
    "facebook_messenger",
    "tiktok_dm",
    "whatsapp",
    "ad",
    "website",
    "instagram_comment",
    "manual",
)

EXPORT_COLUMNS = (
    ("first_name", "Ad"),
    ("last_name", "Soyad"),
    ("username", "İstifadəçi adı"),
    ("phone", "Telefon"),
    ("email", "E-poçt"),
    ("platform", "Platforma"),
    ("profile_link", "Profil keçidi"),
    ("interested_in", "Maraqlandığı kurs"),
    ("status", "Lead statusu"),
    ("lead_source", "Mənbə"),
    ("last_interaction_at", "Son əlaqə"),
    ("first_interaction_at", "İlk əlaqə"),
    ("ai_summary", "AI xülasəsi"),
    ("tags", "Teqlər"),
    ("notes", "Qeydlər"),
    ("assigned_to", "Məsul şəxs"),
    ("next_follow_up_at", "Növbəti əlaqə"),
)


def normalize_lead_status(value: str) -> str:
    normalized = value.strip().lower().replace(" ", "_").replace("-", "_")
    if normalized not in LEAD_STATUSES:
        raise ValueError(f"Unsupported lead status: {value}")
    return normalized


def _display_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(item) for item in value)
    rendered = str(value)
    if rendered.startswith(("=", "+", "-", "@")):
        return "'" + rendered
    return rendered


def _column_name(index: int) -> str:
    value = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        value = chr(65 + remainder) + value
    return value


def build_leads_workbook(rows: Iterable[Mapping[str, object]]) -> bytes:
    matrix = [[label for _, label in EXPORT_COLUMNS]]
    matrix.extend([[_display_value(row.get(key)) for key, _ in EXPORT_COLUMNS] for row in rows])

    strings: list[str] = []
    string_indexes: dict[str, int] = {}
    for row in matrix:
        for value in row:
            if value not in string_indexes:
                string_indexes[value] = len(strings)
                strings.append(value)

    sheet_rows: list[str] = []
    for row_number, row in enumerate(matrix, start=1):
        cells = []
        for column_number, value in enumerate(row, start=1):
            ref = f"{_column_name(column_number)}{row_number}"
            cells.append(f'<c r="{ref}" t="s"><v>{string_indexes[value]}</v></c>')
        sheet_rows.append(f'<row r="{row_number}">{"".join(cells)}</row>')

    shared_items = "".join(f"<si><t>{html.escape(value)}</t></si>" for value in strings)
    files = {
        "[Content_Types].xml": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>
</Types>""",
        "_rels/.rels": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""",
        "xl/workbook.xml": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Leads" sheetId="1" r:id="rId1"/></sheets></workbook>""",
        "xl/_rels/workbook.xml.rels": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>
</Relationships>""",
        "xl/sharedStrings.xml": f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="{sum(len(row) for row in matrix)}" uniqueCount="{len(strings)}">{shared_items}</sst>''',
        "xl/worksheets/sheet1.xml": f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><dimension ref="A1:Q{max(len(matrix), 1)}"/><sheetViews><sheetView workbookViewId="0"/></sheetViews><sheetFormatPr defaultRowHeight="15"/><sheetData>{"".join(sheet_rows)}</sheetData><autoFilter ref="A1:Q{max(len(matrix), 1)}"/></worksheet>''',
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return buffer.getvalue()


async def sync_conversation_leads(db: AsyncSession, company_id: uuid.UUID) -> None:
    await db.execute(
        text(
            """
            insert into crm_leads (
                company_id, platform, external_id, conversation_id, first_name, username, phone,
                profile_link, lead_source, first_interaction_at, last_interaction_at
            )
            select company_id, platform, external_id,
                   (array_agg(conversation_id order by last_interaction_at desc nulls last))[1],
                   max(first_name), max(username), max(phone), max(profile_link),
                   max(lead_source), min(first_interaction_at), max(last_interaction_at)
            from (
                select c.company_id, 'instagram'::varchar as platform, c.customer_instagram_id::text as external_id, c.id as conversation_id,
                       null::varchar as first_name, c.customer_username as username,
                       null::varchar as phone,
                       case when c.customer_username is not null then 'https://www.instagram.com/' || c.customer_username else null end as profile_link,
                       'instagram_dm'::varchar as lead_source, c.created_at as first_interaction_at, c.last_message_at as last_interaction_at
                from instagram_conversations c where c.company_id = :company_id
                union all
                select c.company_id, 'whatsapp'::varchar, c.customer_whatsapp_id::text, c.id,
                       c.customer_name, null::varchar, c.customer_phone, null::text,
                       'whatsapp'::varchar, c.created_at, c.last_message_at
                from whatsapp_cloud_conversations c where c.company_id = :company_id
                union all
                select c.company_id, 'whatsapp'::varchar, c.customer_whatsapp_id::text, c.id,
                       c.customer_name, null::varchar, c.customer_phone, null::text,
                       'whatsapp'::varchar, c.created_at, c.last_message_at
                from whatsapp_conversations c where c.company_id = :company_id
            ) source
            group by company_id, platform, external_id
            on conflict (company_id, platform, external_id) do update set
                conversation_id = excluded.conversation_id,
                first_name = coalesce(crm_leads.first_name, excluded.first_name),
                username = coalesce(crm_leads.username, excluded.username),
                phone = coalesce(crm_leads.phone, excluded.phone),
                profile_link = coalesce(crm_leads.profile_link, excluded.profile_link),
                is_deleted = false,
                deleted_at = null,
                first_interaction_at = least(crm_leads.first_interaction_at, excluded.first_interaction_at),
                last_interaction_at = case
                    when crm_leads.last_interaction_at is null then excluded.last_interaction_at
                    when excluded.last_interaction_at is null then crm_leads.last_interaction_at
                    else greatest(crm_leads.last_interaction_at, excluded.last_interaction_at)
                end
            """
        ),
        {"company_id": company_id},
    )
    await db.commit()


async def list_leads(
    db: AsyncSession,
    company_id: uuid.UUID,
    *,
    q: str | None = None,
    status: str | None = None,
    platform: str | None = None,
    interested_in: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    limit: int = 300,
    offset: int = 0,
) -> Sequence[Mapping[str, Any]]:
    await sync_conversation_leads(db, company_id)
    search = f"%{q.strip().lower()}%" if q and q.strip() else None
    course = f"%{interested_in.strip().lower()}%" if interested_in and interested_in.strip() else None
    result = await db.execute(
        text(
            """
            select * from crm_leads
            where company_id = :company_id
              and is_deleted = false
              and (cast(:search as text) is null or lower(concat_ws(' ', first_name, last_name, username, phone, email, external_id, interested_in, notes, array_to_string(tags, ' '))) like cast(:search as text))
              and (cast(:status as varchar) is null or status = cast(:status as varchar))
              and (cast(:platform as varchar) is null or platform = cast(:platform as varchar))
              and (cast(:course as text) is null or lower(coalesce(interested_in, '')) like cast(:course as text))
              and (cast(:from_date as timestamptz) is null or coalesce(first_interaction_at, created_at) >= cast(:from_date as timestamptz))
              and (cast(:to_date as timestamptz) is null or coalesce(first_interaction_at, created_at) < date_trunc('day', cast(:to_date as timestamptz)) + interval '1 day')
            order by last_interaction_at desc nulls last, created_at desc
            limit :limit offset :offset
            """
        ),
        {
            "company_id": company_id,
            "search": search,
            "status": status,
            "platform": platform,
            "course": course,
            "from_date": from_date,
            "to_date": to_date,
            "limit": limit,
            "offset": offset,
        },
    )
    return result.mappings().all()


async def get_lead(db: AsyncSession, company_id: uuid.UUID, lead_id: uuid.UUID) -> Mapping[str, Any] | None:
    await sync_conversation_leads(db, company_id)
    result = await db.execute(
        text("select * from crm_leads where id = :lead_id and company_id = :company_id and is_deleted = false limit 1"),
        {"lead_id": lead_id, "company_id": company_id},
    )
    return result.mappings().first()


async def update_lead(
    db: AsyncSession,
    company_id: uuid.UUID,
    lead_id: uuid.UUID,
    changes: Mapping[str, object],
    *,
    manual_editor: str | None = None,
) -> Mapping[str, Any] | None:
    allowed = {
        "first_name", "last_name", "username", "phone", "email", "profile_link",
        "interested_in", "status", "lead_source", "ai_summary", "tags", "notes",
        "assigned_to", "next_follow_up_at",
    }
    values = {key: value for key, value in changes.items() if key in allowed}
    if not values:
        return await get_lead(db, company_id, lead_id)
    if values.get("status") is not None:
        values["status"] = normalize_lead_status(str(values["status"]))
    assignments = ", ".join(f"{key} = :{key}" for key in values)
    parameters = {**values, "lead_id": lead_id, "company_id": company_id}
    if manual_editor:
        assignments += ", manually_updated_at = now(), manually_updated_by = :manual_editor"
        parameters["manual_editor"] = manual_editor
    result = await db.execute(
        text(f"update crm_leads set {assignments}, updated_at = now() where id = :lead_id and company_id = :company_id and is_deleted = false returning *"),
        parameters,
    )
    row = result.mappings().first()
    await db.commit()
    return row


async def delete_lead(db: AsyncSession, company_id: uuid.UUID, lead_id: uuid.UUID) -> bool:
    result = await db.execute(
        text("update crm_leads set is_deleted = true, deleted_at = now(), updated_at = now() where id = :lead_id and company_id = :company_id and is_deleted = false returning id"),
        {"lead_id": lead_id, "company_id": company_id},
    )
    deleted = result.scalar_one_or_none() is not None
    await db.commit()
    return deleted


async def conversation_history(
    db: AsyncSession,
    company_id: uuid.UUID,
    platform: str,
    conversation_id: uuid.UUID | None,
) -> Sequence[Mapping[str, Any]]:
    if not conversation_id or platform not in {"instagram", "whatsapp"}:
        return []
    if platform == "instagram":
        query = """
            select id::text, direction, coalesce(message_text, '') as text,
                   coalesce(sent_at, created_at) as created_at
            from instagram_messages
            where company_id = :company_id and conversation_id = :conversation_id
            order by coalesce(sent_at, created_at) asc
        """
    else:
        query = """
            select id::text, direction, coalesce(message_text, '') as text,
                   coalesce(sent_at, created_at) as created_at
            from whatsapp_cloud_messages
            where company_id = :company_id and conversation_id = :conversation_id
            union all
            select id::text, direction, coalesce(message_text, '') as text,
                   coalesce(sent_at, created_at) as created_at
            from whatsapp_messages
            where company_id = :company_id and conversation_id = :conversation_id
            order by created_at asc
        """
    result = await db.execute(text(query), {"company_id": company_id, "conversation_id": conversation_id})
    return result.mappings().all()


async def upsert_course_inquiry_lead(
    db: AsyncSession,
    company_id: uuid.UUID,
    *,
    channel: str,
    customer_id: str,
    conversation_id: uuid.UUID | None,
    customer_name: str | None,
    customer_phone: str | None,
    interested_in: str | None,
) -> Mapping[str, Any]:
    normalized_platform = channel.lower() if channel.lower() in {"instagram", "whatsapp"} else "manual"
    source = f"{normalized_platform}_dm" if normalized_platform != "manual" else "course_inquiry"
    result = await db.execute(
        text(
            """
            insert into crm_leads (
                company_id, platform, external_id, conversation_id,
                first_name, phone, interested_in, status, lead_source,
                first_interaction_at, last_interaction_at, metadata
            ) values (
                :company_id, :platform, :external_id, :conversation_id,
                :customer_name, :customer_phone, :interested_in, 'interested', :lead_source,
                now(), now(), cast(:metadata as jsonb)
            )
            on conflict (company_id, platform, external_id)
            do update set
                conversation_id = coalesce(excluded.conversation_id, crm_leads.conversation_id),
                first_name = coalesce(excluded.first_name, crm_leads.first_name),
                phone = coalesce(excluded.phone, crm_leads.phone),
                interested_in = coalesce(excluded.interested_in, crm_leads.interested_in),
                status = case
                    when crm_leads.status in ('archived', 'not_interested', 'enrolled') then crm_leads.status
                    else 'interested'
                end,
                lead_source = excluded.lead_source,
                is_deleted = false,
                deleted_at = null,
                last_interaction_at = now(),
                updated_at = now()
            returning *
            """
        ),
        {
            "company_id": company_id,
            "platform": normalized_platform,
            "external_id": customer_id,
            "conversation_id": conversation_id,
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "interested_in": interested_in,
            "lead_source": source,
            "metadata": json.dumps({"course_inquiry": True}, ensure_ascii=False),
        },
    )
    return cast(Mapping[str, Any], result.mappings().one())


async def upsert_comment_lead(
    db: AsyncSession,
    company_id: uuid.UUID,
    *,
    external_id: str,
    username: str | None,
    source_comment_id: uuid.UUID,
) -> None:
    result = await db.execute(
        text(
            """
            insert into crm_leads (
                company_id, platform, external_id, username, profile_link, status,
                lead_source, first_interaction_at, last_interaction_at, source_comment_id
            ) values (
                :company_id, 'instagram', :external_id, :username,
                case when cast(:username as text) is not null then 'https://www.instagram.com/' || cast(:username as text) else null end,
                'new', 'instagram_comment', now(), now(), :source_comment_id
            )
            on conflict (company_id, platform, external_id) do update set
                username = coalesce(crm_leads.username, excluded.username),
                profile_link = coalesce(crm_leads.profile_link, excluded.profile_link),
                source_comment_id = coalesce(crm_leads.source_comment_id, excluded.source_comment_id),
                is_deleted = false,
                deleted_at = null,
                last_interaction_at = now(),
                updated_at = now()
            returning id
            """
        ),
        {
            "company_id": company_id,
            "external_id": external_id,
            "username": username,
            "source_comment_id": source_comment_id,
        },
    )
    lead_id = result.scalar_one()
    await db.execute(
        text(
            """
            update instagram_comments
            set lead_id = :lead_id,
                status = 'converted',
                converted_at = coalesce(converted_at, now()),
                updated_at = now()
            where id = :comment_id
              and company_id = :company_id
            """
        ),
        {"lead_id": lead_id, "comment_id": source_comment_id, "company_id": company_id},
    )
    await db.execute(
        text(
            """
            update instagram_comment_threads t
            set replied_comment_count = stats.replied_comments,
                converted_comment_count = stats.converted_comments,
                updated_at = now()
            from (
                select thread_id,
                       count(*) filter (where status in ('replied', 'converted'))::int as replied_comments,
                       count(*) filter (where status = 'converted')::int as converted_comments
                from instagram_comments
                where thread_id = (select thread_id from instagram_comments where id = :comment_id and company_id = :company_id)
                group by thread_id
            ) stats
            where t.id = stats.thread_id
              and t.company_id = :company_id
            """
        ),
        {"comment_id": source_comment_id, "company_id": company_id},
    )
