import inspect
import uuid

import pytest

from routers.crm_api import _linkedin_response
from services.automation import _sync_tiktok_connection_placeholder, _zernio_platform_payload, upsert_automation_settings
from services.zernio_integrator import (
    _extract_connected_accounts_payload,
    _extract_linkedin_account_id,
    _extract_zernio_account_id,
    _is_linkedin_account,
)


def test_linkedin_account_detection_and_external_id_extraction():
    payload = {
        "platform": "linkedin",
        "_id": "zernio-account",
        "linkedinAccountId": "urn:li:person:123",
    }

    assert _is_linkedin_account(payload) is True
    assert _extract_linkedin_account_id(payload) == "urn:li:person:123"
    assert _is_linkedin_account({"platform": "instagram"}) is False


def test_linkedin_identity_extractors_reject_blank_ids():
    assert _extract_linkedin_account_id({"externalAccountId": "   "}) is None
    with pytest.raises(ValueError, match="does not contain account id"):
        _extract_zernio_account_id({"id": "   "})


def test_connected_accounts_payload_rejects_malformed_provider_data():
    assert _extract_connected_accounts_payload({"accounts": []}) == []
    with pytest.raises(ValueError, match="does not contain accounts list"):
        _extract_connected_accounts_payload({"unexpected": []})
    with pytest.raises(ValueError, match="malformed account entry"):
        _extract_connected_accounts_payload({"accounts": [{"platform": "linkedin"}, "broken"]})


def test_linkedin_placeholder_without_zernio_account_is_not_connected():
    tenant_id = uuid.uuid4()
    response = _linkedin_response(
        tenant_id,
        {"status": "connected", "metadata": {"zernio_account_id": "placeholder"}, "external_account_id": None},
    )
    stale_response = _linkedin_response(
        tenant_id,
        {"status": "disabled", "metadata": {"zernio_account_id": "stale"}},
    )

    assert response.connected is False
    assert response.zernio_account_id is None
    assert stale_response.connected is False
    assert stale_response.zernio_account_id is None


def test_legacy_automation_payload_cannot_mutate_linkedin_lifecycle():
    upsert_source = inspect.getsource(upsert_automation_settings)
    tiktok_sync_source = inspect.getsource(_sync_tiktok_connection_placeholder)

    assert 'payload.get("linkedin_connected"' not in upsert_source
    assert "_linkedin_connection_is_valid" in upsert_source
    assert "linkedin" not in tiktok_sync_source.lower()


def test_linkedin_post_payload_uses_only_documented_account_id_key():
    assert _zernio_platform_payload("linkedin", "zernio-account") == [
        {"platform": "linkedin", "accountId": "zernio-account"}
    ]
