from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest

from services.leads import LEAD_PLATFORMS, LEAD_STATUSES, build_leads_workbook, normalize_lead_status


def test_codev_lead_status_contract_supports_course_enrollment_pipeline() -> None:
    assert LEAD_STATUSES == (
        "new",
        "interested",
        "contacted",
        "qualified",
        "enrolled",
        "not_interested",
        "lost",
        "archived",
    )
    assert normalize_lead_status("Enrolled") == "enrolled"
    assert "manual" in LEAD_PLATFORMS
    with pytest.raises(ValueError):
        normalize_lead_status("invalid")


def test_build_leads_workbook_is_real_xlsx_with_azerbaijani_course_columns() -> None:
    payload = build_leads_workbook([
        {
            "first_name": "Aysel",
            "last_name": "Əliyeva",
            "username": "aysel.network",
            "phone": "+994****2233",
            "email": "aysel@example.com",
            "platform": "instagram",
            "profile_link": "https://instagram.com/aysel.network",
            "interested_in": "CCNA",
            "status": "qualified",
            "lead_source": "instagram_dm",
            "last_interaction_at": datetime(2026, 8, 5, 10, 30, tzinfo=timezone.utc),
            "first_interaction_at": datetime(2026, 8, 1, 8, 0, tzinfo=timezone.utc),
            "ai_summary": "CCNA kursu ilə maraqlanır",
            "tags": ["CCNA", "Prioritet"],
            "notes": "Axşam zəng et",
            "assigned_to": "Orxan",
            "next_follow_up_at": datetime(2026, 8, 12, 9, 0, tzinfo=timezone.utc),
        }
    ])

    assert payload.startswith(b"PK")
    with ZipFile(BytesIO(payload)) as archive:
        assert "xl/worksheets/sheet1.xml" in archive.namelist()
        shared = archive.read("xl/sharedStrings.xml").decode("utf-8")
        assert "Ad" in shared
        assert "Maraqlandığı kurs" in shared
        assert "Növbəti əlaqə" in shared
        assert "aysel.network" in shared
        assert "Prioritet" in shared


def test_xlsx_neutralizes_formula_prefixes() -> None:
    payload = build_leads_workbook([{"first_name": "=HYPERLINK(\"https://evil.invalid\")"}])
    with ZipFile(BytesIO(payload)) as archive:
        shared = archive.read("xl/sharedStrings.xml").decode("utf-8")
    assert "&#x27;=HYPERLINK" in shared


def test_course_inquiries_and_comments_link_to_tenant_scoped_leads() -> None:
    root = Path(__file__).resolve().parents[1]
    customer_orders = (root / "src/services/customer_orders.py").read_text()
    lead_service = (root / "src/services/leads.py").read_text()
    migration = (root / "infra/flyway/sql/V3_35__link_course_inquiries_to_leads.sql").read_text()

    assert "upsert_course_inquiry_lead" in customer_orders
    assert "update customer_orders set lead_id" in customer_orders
    assert "update instagram_comments" in lead_service
    assert "foreign key (company_id, lead_id)" in migration
    assert "references crm_leads(company_id, id)" in migration
    manual_migration = (root / "infra/flyway/sql/V3_34_1__allow_manual_lead_platform.sql").read_text()
    assert "'manual'" in manual_migration
    status_migration = (root / "infra/flyway/sql/V3_36__sync_customer_order_lead_status.sql").read_text()
    assert "on delete set null (lead_id)" in status_migration
    assert "trg_customer_orders_sync_lead_status" in status_migration
    assert "'enrolled'" in status_migration
    assert "is_deleted = false" in lead_service
    assert "date_trunc('day'" in lead_service
    assert "group by company_id, platform, external_id" in lead_service
    router = (root / "src/routers/crm_api.py").read_text()
    assert "pg_advisory_xact_lock" in router
    assert "converted_comment_count = stats.converted_comments" in lead_service


def test_legacy_tenant_channels_and_conversations_routes_require_auth() -> None:
    root = Path(__file__).resolve().parents[1]
    router = (root / "src/routers/crm_api.py").read_text()

    for function_name in ("list_tenants", "create_tenant", "list_channels", "create_channel", "list_conversations"):
        start = router.index(f"async def {function_name}")
        block = router[start:start + 900]
        assert "Depends(get_current_user)" in block or "Depends(get_admin_user)" in block
