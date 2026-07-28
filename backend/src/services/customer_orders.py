import json
import uuid
from collections.abc import Mapping
from typing import Any, cast

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from datetime import datetime, timezone


def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def build_order_summary(
    *,
    channel: str,
    customer_id: str,
    customer_name: str | None,
    customer_phone: str | None,
    product_title: str | None,
    product_price: str | None,
    quantity: int | None,
    delivery_required: bool | None,
    delivery_address: str | None,
    delivery_time: str | None,
    customer_comment: str | None,
) -> str:
    lines = [
        "New order",
        f"Channel: {channel}",
        f"Customer ID: {customer_id}",
    ]

    if customer_name:
        lines.append(f"Name: {customer_name}")

    if customer_phone:
        lines.append(f"Phone: {customer_phone}")

    if product_title:
        lines.append(f"Product: {product_title}")

    if product_price:
        lines.append(f"Price: {product_price}")

    if quantity:
        lines.append(f"Quantity: {quantity}")

    if delivery_required is not None:
        lines.append(f"Delivery: {'yes' if delivery_required else 'no'}")

    if delivery_address:
        lines.append(f"Delivery address: {delivery_address}")

    if delivery_time:
        lines.append(f"Delivery time: {delivery_time}")

    if customer_comment:
        lines.append(f"Comment: {customer_comment}")

    return "\n".join(lines)


async def create_customer_order(
    db: AsyncSession,
    *,
    company_id: uuid.UUID,
    channel: str,
    customer_id: str,
    conversation_id: uuid.UUID | None = None,
    source_message_id: str | None = None,
    customer_name: str | None = None,
    customer_phone: str | None = None,
    product_title: str | None = None,
    product_price: str | None = None,
    quantity: int | None = None,
    delivery_required: bool | None = None,
    delivery_address: str | None = None,
    delivery_time: str | None = None,
    customer_comment: str | None = None,
    raw_intent_payload: dict[str, Any] | None = None,
) -> Mapping[str, Any]:
    order_id = uuid.uuid4()
    now = now_utc()

    raw_summary = build_order_summary(
        channel=channel,
        customer_id=customer_id,
        customer_name=customer_name,
        customer_phone=customer_phone,
        product_title=product_title,
        product_price=product_price,
        quantity=quantity,
        delivery_required=delivery_required,
        delivery_address=delivery_address,
        delivery_time=delivery_time,
        customer_comment=customer_comment,
    )

    result = await db.execute(
        text(
            """
            insert into customer_orders (
                id,
                company_id,
                channel,
                customer_id,
                conversation_id,
                source_message_id,
                customer_name,
                customer_phone,
                product_title,
                product_price,
                quantity,
                delivery_required,
                delivery_address,
                delivery_time,
                customer_comment,
                raw_summary,
                raw_intent_payload,
                status,
                created_at,
                updated_at
            ) values (
                :id,
                :company_id,
                :channel,
                :customer_id,
                :conversation_id,
                :source_message_id,
                :customer_name,
                :customer_phone,
                :product_title,
                :product_price,
                :quantity,
                :delivery_required,
                :delivery_address,
                :delivery_time,
                :customer_comment,
                :raw_summary,
                cast(:raw_intent_payload as jsonb),
                'new',
                :now,
                :now
            )
            on conflict (company_id, channel, source_message_id)
            do update set
                updated_at = customer_orders.updated_at
            returning
                id,
                company_id,
                channel,
                customer_id,
                conversation_id,
                source_message_id,
                customer_name,
                customer_phone,
                product_title,
                product_price,
                quantity,
                delivery_required,
                delivery_address,
                delivery_time,
                customer_comment,
                raw_summary,
                raw_intent_payload,
                status,
                manager_notified_at,
                created_at,
                updated_at
            """
        ),
        {
            "id": order_id,
            "company_id": company_id,
            "channel": channel,
            "customer_id": customer_id,
            "conversation_id": conversation_id,
            "source_message_id": source_message_id,
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "product_title": product_title,
            "product_price": product_price,
            "quantity": quantity,
            "delivery_required": delivery_required,
            "delivery_address": delivery_address,
            "delivery_time": delivery_time,
            "customer_comment": customer_comment,
            "raw_summary": raw_summary,
            "raw_intent_payload": json.dumps(raw_intent_payload or {}, ensure_ascii=False),
            "now": now,
        },
    )

    await db.commit()

    row = result.mappings().one()
    return cast(Mapping[str, Any], row)


async def mark_customer_order_sent_to_manager(
    db: AsyncSession,
    *,
    order_id: uuid.UUID,
) -> None:
    await db.execute(
        text(
            """
            update customer_orders
            set status = 'sent_to_manager',
                manager_notified_at = now(),
                updated_at = now()
            where id = :order_id
            """
        ),
        {
            "order_id": order_id,
        },
    )

    await db.commit()