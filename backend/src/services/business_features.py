from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable, Literal, Mapping

BusinessType = Literal["confectionery", "flower_shop", "cafe_restaurant", "other"]
InventoryStatus = Literal["fresh", "discounted", "expired"]

VALID_BUSINESS_TYPES: set[str] = {"confectionery", "flower_shop", "cafe_restaurant", "other"}


@dataclass(frozen=True)
class BusinessTypeFeatureSet:
    code: BusinessType
    label: str
    supports_perishable_inventory: bool
    supports_custom_visual_requests: bool
    default_shelf_life_hours: int | None
    default_discount_after_hours: int | None
    default_discount_percent: Decimal
    custom_item_label: str | None


@dataclass(frozen=True)
class InventoryDiscountResult:
    status: InventoryStatus
    original_price: Decimal
    effective_price: Decimal
    discount_percent: Decimal
    age_hours: Decimal
    expires_in_hours: Decimal


@dataclass(frozen=True)
class BusinessMetrics:
    total_orders: int
    completed_orders: int
    gross_revenue: Decimal
    total_costs: Decimal
    net_profit: Decimal
    unique_customers: int
    repeat_customers: int
    inbound_messages: int
    outbound_messages: int
    inventory_value: Decimal


BUSINESS_TYPE_FEATURES: dict[BusinessType, BusinessTypeFeatureSet] = {
    "confectionery": BusinessTypeFeatureSet(
        code="confectionery",
        label="Konditer mağazası",
        supports_perishable_inventory=True,
        supports_custom_visual_requests=True,
        default_shelf_life_hours=72,
        default_discount_after_hours=36,
        default_discount_percent=Decimal("15"),
        custom_item_label="Fərdi tort / şirniyyat vizualı",
    ),
    "flower_shop": BusinessTypeFeatureSet(
        code="flower_shop",
        label="Gül mağazası",
        supports_perishable_inventory=True,
        supports_custom_visual_requests=True,
        default_shelf_life_hours=48,
        default_discount_after_hours=24,
        default_discount_percent=Decimal("20"),
        custom_item_label="Fərdi buket vizualı",
    ),
    "cafe_restaurant": BusinessTypeFeatureSet(
        code="cafe_restaurant",
        label="Kafe / Restoran",
        supports_perishable_inventory=False,
        supports_custom_visual_requests=False,
        default_shelf_life_hours=None,
        default_discount_after_hours=None,
        default_discount_percent=Decimal("0"),
        custom_item_label=None,
    ),
    "other": BusinessTypeFeatureSet(
        code="other",
        label="Digər biznes",
        supports_perishable_inventory=False,
        supports_custom_visual_requests=False,
        default_shelf_life_hours=None,
        default_discount_after_hours=None,
        default_discount_percent=Decimal("0"),
        custom_item_label=None,
    ),
}


def money(value: Any) -> Decimal:
    if value is None or value == "":
        return Decimal("0.00")
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        return Decimal("0.00")


def normalize_business_type(value: str | None) -> BusinessType:
    if value in VALID_BUSINESS_TYPES:
        return value  # type: ignore[return-value]
    return "other"


def feature_set_for(value: str | None) -> BusinessTypeFeatureSet:
    return BUSINESS_TYPE_FEATURES[normalize_business_type(value)]


def compute_inventory_discount(
    *,
    original_price: Decimal,
    received_at: datetime,
    shelf_life_hours: int | None,
    discount_after_hours: int | None,
    discount_percent: Decimal,
    now: datetime | None = None,
) -> InventoryDiscountResult:
    now = now or datetime.now(timezone.utc)
    if received_at.tzinfo is None:
        received_at = received_at.replace(tzinfo=timezone.utc)

    age = Decimal(str((now - received_at).total_seconds() / 3600)).quantize(Decimal("0.01"))
    shelf_life = Decimal(str(shelf_life_hours or 0))
    expires_in = (shelf_life - age).quantize(Decimal("0.01")) if shelf_life_hours else Decimal("0.00")
    price = money(original_price)

    if shelf_life_hours and age >= Decimal(str(shelf_life_hours)):
        return InventoryDiscountResult(
            status="expired",
            original_price=price,
            effective_price=Decimal("0.00"),
            discount_percent=Decimal("100.00"),
            age_hours=age,
            expires_in_hours=expires_in,
        )

    if discount_after_hours is not None and age >= Decimal(str(discount_after_hours)) and discount_percent > 0:
        percent = money(discount_percent)
        effective = (price * (Decimal("100") - percent) / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return InventoryDiscountResult(
            status="discounted",
            original_price=price,
            effective_price=effective,
            discount_percent=percent,
            age_hours=age,
            expires_in_hours=expires_in,
        )

    return InventoryDiscountResult(
        status="fresh",
        original_price=price,
        effective_price=price,
        discount_percent=Decimal("0.00"),
        age_hours=age,
        expires_in_hours=expires_in,
    )


def summarize_business_metrics(
    *,
    orders: Iterable[dict[str, Any]],
    inbound_messages: int,
    outbound_messages: int,
    inventory_value: Any,
) -> BusinessMetrics:
    rows = list(orders)
    completed = [row for row in rows if str(row.get("status") or "").lower() in {"completed", "paid", "done"}]
    revenue = sum((money(row.get("revenue")) for row in completed), Decimal("0.00"))
    costs = sum((money(row.get("cost")) for row in completed), Decimal("0.00"))

    customer_counts: dict[str, int] = {}
    for row in rows:
        customer_id = str(row.get("customer_id") or "").strip()
        if customer_id:
            customer_counts[customer_id] = customer_counts.get(customer_id, 0) + 1

    return BusinessMetrics(
        total_orders=len(rows),
        completed_orders=len(completed),
        gross_revenue=money(revenue),
        total_costs=money(costs),
        net_profit=money(revenue - costs),
        unique_customers=len(customer_counts),
        repeat_customers=sum(1 for count in customer_counts.values() if count >= 2),
        inbound_messages=int(inbound_messages),
        outbound_messages=int(outbound_messages),
        inventory_value=money(inventory_value),
    )


def build_inventory_unavailable_reply(*, language: str | None, product_title: str, requested_quantity: int | None, available_quantity: int) -> str:
    requested = requested_quantity or 1
    product = product_title or "product"
    if language == "az":
        if available_quantity <= 0:
            return f"Təəssüf ki, {product} hazırda stokda yoxdur. İstəsəniz, alternativ təklif edə bilərəm."
        return f"Təəssüf ki, {requested} ədəd {product} sifariş etmək mümkün deyil — stokda cəmi {available_quantity} ədəd qalıb. İstəsəniz, {available_quantity} ədəd üçün sifarişi davam etdirə bilərik."
    if language == "ru":
        if available_quantity <= 0:
            return f"К сожалению, {product} сейчас нет в наличии. Могу предложить альтернативу."
        return f"К сожалению, заказать {requested} шт. {product} нельзя — в наличии осталось только {available_quantity}. Можем продолжить заказ на {available_quantity} шт."
    if available_quantity <= 0:
        return f"Unfortunately, {product} is currently out of stock. I can suggest an alternative."
    return f"Unfortunately, you cannot order {requested} x {product}; only {available_quantity} is left in stock. We can continue with {available_quantity} if that works."


def find_order_stock_conflict(
    *,
    product_title: str | None,
    requested_quantity: int | None,
    knowledge_entries: Iterable[Mapping[str, Any]],
) -> tuple[str, int, int] | None:
    if not product_title:
        return None
    requested = requested_quantity or 1
    normalized_product = product_title.strip().lower()
    if not normalized_product:
        return None

    best_match: Mapping[str, Any] | None = None
    for entry in knowledge_entries:
        quantity = entry.get("quantity_available")
        if quantity is None:
            continue
        title = str(entry.get("title") or "").strip().lower()
        content = str(entry.get("content") or "").strip().lower()
        if normalized_product in title or title in normalized_product or normalized_product in content:
            best_match = entry
            break
        if best_match is None:
            best_match = entry

    if best_match is None:
        return None
    quantity_value = best_match.get("quantity_available")
    if quantity_value is None:
        return None
    try:
        available = int(quantity_value)
    except (TypeError, ValueError):
        return None
    if available <= 0 or requested > available:
        return (str(best_match.get("title") or product_title), requested, available)
    return None


def build_custom_visual_prompt(*, business_type: str | None, title: str, description: str, budget: str | None = None) -> str:
    features = feature_set_for(business_type)
    base = "photorealistic product preview, clean commercial lighting, high detail"
    if features.code == "flower_shop":
        domain = "custom flower bouquet arrangement, florist composition, fresh flowers"
    elif features.code == "confectionery":
        domain = "custom cake or pastry design, confectionery presentation, edible decoration"
    else:
        domain = "custom business product concept"
    budget_part = f", approximate budget: {budget}" if budget else ""
    return f"{base}, {domain}, title: {title}, customer request: {description}{budget_part}"
