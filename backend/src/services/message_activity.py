from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


MESSAGE_EVENTS_CTE = """
message_events as (
    select
        m.created_at as event_at,
        m.direction,
        c.customer_instagram_id::text as customer_id,
        coalesce(nullif(c.customer_username, ''), c.customer_instagram_id::text) as customer_label,
        'instagram'::text as channel
    from instagram_messages m
    join instagram_conversations c
      on c.id = m.conversation_id
     and c.company_id = m.company_id
     and c.company_id = :company_id
    where m.company_id = :company_id

    union all

    select
        m.created_at as event_at,
        m.direction,
        c.customer_whatsapp_id::text as customer_id,
        coalesce(nullif(c.customer_name, ''), nullif(c.customer_phone, ''), c.customer_whatsapp_id::text) as customer_label,
        'whatsapp'::text as channel
    from whatsapp_cloud_messages m
    join whatsapp_cloud_conversations c
      on c.id = m.conversation_id
     and c.company_id = m.company_id
     and c.company_id = :company_id
    where m.company_id = :company_id

    union all

    select
        m.created_at as event_at,
        m.direction,
        c.customer_whatsapp_id::text as customer_id,
        coalesce(nullif(c.customer_name, ''), nullif(c.customer_phone, ''), c.customer_whatsapp_id::text) as customer_label,
        'whatsapp'::text as channel
    from whatsapp_messages m
    join whatsapp_conversations c
      on c.id = m.conversation_id
     and c.company_id = m.company_id
     and c.company_id = :company_id
    where m.company_id = :company_id
),
period_events as (
    select *
    from message_events
    where (event_at at time zone 'Asia/Baku')::date between cast(:date_from as date) and cast(:date_to as date)
)
"""


def _int(value: Any) -> int:
    return int(value or 0)


def _customer_row(row: Any) -> dict[str, Any]:
    return {
        "customer_id": str(row["customer_id"]),
        "customer_label": str(row["customer_label"] or row["customer_id"]),
        "channel": str(row["channel"]),
        "message_count": _int(row["message_count"]),
        "today_message_count": _int(row["today_message_count"]),
        "last_message_at": row["last_message_at"],
    }


async def load_message_activity(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    date_from: date,
    date_to: date,
) -> dict[str, Any]:
    params = {"company_id": tenant_id, "date_from": date_from, "date_to": date_to}

    summary_result = await db.execute(
        text(
            f"""
            with {MESSAGE_EVENTS_CTE}
            select
                count(*)::int as total_messages,
                count(*) filter (where direction = 'inbound')::int as inbound_messages,
                count(*) filter (where direction = 'outbound')::int as outbound_messages,
                count(distinct channel || ':' || customer_id) filter (where direction = 'inbound')::int as active_customers,
                (
                    select count(*)::int
                    from message_events
                    where direction = 'inbound'
                      and (event_at at time zone 'Asia/Baku')::date = (current_timestamp at time zone 'Asia/Baku')::date
                ) as today_messages,
                (
                    select count(distinct channel || ':' || customer_id)::int
                    from message_events
                    where direction = 'inbound'
                      and (event_at at time zone 'Asia/Baku')::date = (current_timestamp at time zone 'Asia/Baku')::date
                ) as today_customers_count
            from period_events
            """
        ),
        params,
    )
    summary = summary_result.mappings().first() or {}

    daily_result = await db.execute(
        text(
            f"""
            with {MESSAGE_EVENTS_CTE},
            days as (
                select generate_series(cast(:date_from as date), cast(:date_to as date), interval '1 day')::date as day
            )
            select
                d.day,
                count(p.*) filter (where p.direction = 'inbound')::int as inbound,
                count(p.*) filter (where p.direction = 'outbound')::int as outbound,
                count(distinct p.channel || ':' || p.customer_id) filter (where p.direction = 'inbound')::int as active_customers
            from days d
            left join period_events p on (p.event_at at time zone 'Asia/Baku')::date = d.day
            group by d.day
            order by d.day
            """
        ),
        params,
    )
    daily_activity = [
        {
            "date": row["day"].isoformat(),
            "inbound": _int(row["inbound"]),
            "outbound": _int(row["outbound"]),
            "active_customers": _int(row["active_customers"]),
        }
        for row in daily_result.mappings().all()
    ]

    channel_result = await db.execute(
        text(
            f"""
            with {MESSAGE_EVENTS_CTE}
            select
                channel,
                count(*) filter (where direction = 'inbound')::int as inbound,
                count(*) filter (where direction = 'outbound')::int as outbound,
                count(distinct customer_id) filter (where direction = 'inbound')::int as active_customers
            from period_events
            group by channel
            order by channel
            """
        ),
        params,
    )
    channels_by_name = {
        str(row["channel"]): {
            "channel": str(row["channel"]),
            "inbound": _int(row["inbound"]),
            "outbound": _int(row["outbound"]),
            "active_customers": _int(row["active_customers"]),
        }
        for row in channel_result.mappings().all()
    }
    channel_activity = [
        channels_by_name.get(
            channel,
            {"channel": channel, "inbound": 0, "outbound": 0, "active_customers": 0},
        )
        for channel in ("instagram", "whatsapp")
    ]

    customer_result = await db.execute(
        text(
            f"""
            with {MESSAGE_EVENTS_CTE},
            period_customers as (
                select
                    customer_id,
                    max(customer_label) as customer_label,
                    channel,
                    count(*)::int as message_count,
                    max(event_at) as period_last_message_at
                from period_events
                where direction = 'inbound'
                group by customer_id, channel
            ),
            today_customer_counts as (
                select
                    customer_id,
                    max(customer_label) as customer_label,
                    channel,
                    count(*)::int as today_message_count,
                    max(event_at) as today_last_message_at
                from message_events
                where direction = 'inbound'
                  and (event_at at time zone 'Asia/Baku')::date = (current_timestamp at time zone 'Asia/Baku')::date
                group by customer_id, channel
            ),
            top_period as (
                select *, row_number() over (order by message_count desc, period_last_message_at desc) as rank_order
                from period_customers
                order by message_count desc, period_last_message_at desc
                limit 8
            ),
            top_today as (
                select *, row_number() over (order by today_message_count desc, today_last_message_at desc) as rank_order
                from today_customer_counts
                order by today_message_count desc, today_last_message_at desc
                limit 8
            )
            select
                'period'::text as ranking,
                p.customer_id,
                p.customer_label,
                p.channel,
                p.message_count,
                coalesce(t.today_message_count, 0)::int as today_message_count,
                greatest(p.period_last_message_at, t.today_last_message_at) as last_message_at,
                p.rank_order
            from top_period p
            left join today_customer_counts t using (customer_id, channel)

            union all

            select
                'today'::text as ranking,
                t.customer_id,
                t.customer_label,
                t.channel,
                coalesce(p.message_count, 0)::int as message_count,
                t.today_message_count,
                greatest(t.today_last_message_at, p.period_last_message_at) as last_message_at,
                t.rank_order
            from top_today t
            left join period_customers p using (customer_id, channel)
            order by ranking, rank_order
            """
        ),
        params,
    )
    customer_rows = customer_result.mappings().all()
    top_customers = [_customer_row(row) for row in customer_rows if row["ranking"] == "period"]
    today_customers = [_customer_row(row) for row in customer_rows if row["ranking"] == "today"]

    return {
        "tenant_id": str(tenant_id),
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "total_messages": _int(summary.get("total_messages")),
        "inbound_messages": _int(summary.get("inbound_messages")),
        "outbound_messages": _int(summary.get("outbound_messages")),
        "active_customers": _int(summary.get("active_customers")),
        "today_messages": _int(summary.get("today_messages")),
        "today_customers_count": _int(summary.get("today_customers_count")),
        "daily_activity": daily_activity,
        "channel_activity": channel_activity,
        "top_customers": top_customers,
        "today_customers": today_customers,
    }
