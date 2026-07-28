from datetime import datetime, timedelta, timezone
from decimal import Decimal

from services.business_features import (
    BUSINESS_TYPE_FEATURES,
    compute_inventory_discount,
    normalize_business_type,
    summarize_business_metrics,
)


def test_normalize_business_type_rejects_unknown_values():
    assert normalize_business_type("flower_shop") == "flower_shop"
    assert normalize_business_type("cafe_restaurant") == "cafe_restaurant"
    assert normalize_business_type("bad") == "other"
    assert normalize_business_type(None) == "other"


def test_business_type_features_expose_perishable_and_custom_visual_capabilities():
    assert BUSINESS_TYPE_FEATURES["flower_shop"].supports_perishable_inventory is True
    assert BUSINESS_TYPE_FEATURES["flower_shop"].supports_custom_visual_requests is True
    assert BUSINESS_TYPE_FEATURES["confectionery"].supports_perishable_inventory is True
    assert BUSINESS_TYPE_FEATURES["confectionery"].supports_custom_visual_requests is True
    assert BUSINESS_TYPE_FEATURES["cafe_restaurant"].supports_perishable_inventory is False


def test_compute_inventory_discount_applies_rule_after_age_threshold():
    now = datetime(2026, 6, 23, 12, tzinfo=timezone.utc)
    fresh = compute_inventory_discount(
        original_price=Decimal("100"),
        received_at=now - timedelta(hours=3),
        shelf_life_hours=24,
        discount_after_hours=6,
        discount_percent=Decimal("20"),
        now=now,
    )
    old = compute_inventory_discount(
        original_price=Decimal("100"),
        received_at=now - timedelta(hours=8),
        shelf_life_hours=24,
        discount_after_hours=6,
        discount_percent=Decimal("20"),
        now=now,
    )
    expired = compute_inventory_discount(
        original_price=Decimal("100"),
        received_at=now - timedelta(hours=30),
        shelf_life_hours=24,
        discount_after_hours=6,
        discount_percent=Decimal("20"),
        now=now,
    )

    assert fresh.status == "fresh"
    assert fresh.effective_price == Decimal("100.00")
    assert old.status == "discounted"
    assert old.effective_price == Decimal("80.00")
    assert expired.status == "expired"
    assert expired.effective_price == Decimal("0.00")


def test_summarize_business_metrics_counts_revenue_profit_and_repeat_customers():
    metrics = summarize_business_metrics(
        orders=[
            {"customer_id": "c1", "status": "completed", "revenue": "100", "cost": "40"},
            {"customer_id": "c1", "status": "completed", "revenue": "50", "cost": "20"},
            {"customer_id": "c2", "status": "new", "revenue": "30", "cost": "10"},
        ],
        inbound_messages=7,
        outbound_messages=3,
        inventory_value="250.50",
    )

    assert metrics.total_orders == 3
    assert metrics.completed_orders == 2
    assert metrics.gross_revenue == Decimal("150.00")
    assert metrics.total_costs == Decimal("60.00")
    assert metrics.net_profit == Decimal("90.00")
    assert metrics.repeat_customers == 1
    assert metrics.inbound_messages == 7
    assert metrics.outbound_messages == 3
    assert metrics.inventory_value == Decimal("250.50")
