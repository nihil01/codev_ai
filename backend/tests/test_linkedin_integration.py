import inspect
import uuid
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from routers.admin_auth import UserClaims
import routers.crm_api as crm_api
from routers.crm_api import _linkedin_response, get_linkedin_integration
from services.automation import _sync_tiktok_connection_placeholder, _zernio_platform_payload, upsert_automation_settings
from services.zernio_integrator import (
    IntegratorZernio,
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


@pytest.mark.asyncio
async def test_existing_profile_without_provider_key_still_returns_disconnected_status(monkeypatch):
    tenant_id = uuid.uuid4()

    class FakeDb:
        async def commit(self):
            return None

        async def rollback(self):
            return None

    class ForbiddenIntegrator:
        def __init__(self):
            raise AssertionError("status endpoint must not call Zernio without an API key")

    async def existing_profile(*_args, **_kwargs):
        return "stored-profile"

    async def no_connection(*_args, **_kwargs):
        return None

    monkeypatch.setattr(crm_api.settings, "zernio_api_key", "")
    monkeypatch.setattr(crm_api, "get_zernio_profile_id", existing_profile)
    monkeypatch.setattr(crm_api, "IntegratorZernio", ForbiddenIntegrator)
    monkeypatch.setattr(crm_api, "_disable_linkedin_connection", no_connection)
    monkeypatch.setattr(crm_api, "_linkedin_connection", no_connection)

    response = await get_linkedin_integration(
        tenant_id,
        cast(AsyncSession, FakeDb()),
        UserClaims(user_id=str(uuid.uuid4()), email="owner@example.com", role="company_user", company_id=str(tenant_id)),
    )

    assert response.connected is False


def test_zernio_profile_creation_uses_tenant_idempotency_key():
    tenant_id = uuid.uuid4()
    captured: dict[str, object] = {}

    class FakeProfiles:
        def create_profile(self, **kwargs):
            captured.update(kwargs)
            return {"profile": {"id": "profile-123", "name": kwargs["name"]}}

    class FakeClient:
        profiles = FakeProfiles()

    integrator = object.__new__(IntegratorZernio)
    object.__setattr__(integrator, "client", FakeClient())

    profile = integrator._create_company_profile_sync("owner@example.com", tenant_id)

    assert profile["id"] == "profile-123"
    assert captured["description"] == str(tenant_id)
    assert captured["idempotency_key"] == f"codev-company-{tenant_id}"


@pytest.mark.asyncio
async def test_missing_zernio_profile_status_is_disconnected_not_conflict(monkeypatch):
    tenant_id = uuid.uuid4()

    class FakeDb:
        async def commit(self):
            return None

    async def no_profile(*_args, **_kwargs):
        return None

    async def no_connection(*_args, **_kwargs):
        return None

    monkeypatch.setattr("routers.crm_api.get_zernio_profile_id", no_profile)
    monkeypatch.setattr("routers.crm_api._disable_linkedin_connection", no_connection)
    monkeypatch.setattr("routers.crm_api._linkedin_connection", no_connection)

    response = await get_linkedin_integration(
        tenant_id,
        cast(AsyncSession, FakeDb()),
        UserClaims(user_id=str(uuid.uuid4()), email="owner@example.com", role="company_user", company_id=str(tenant_id)),
    )

    assert response.connected is False
    assert response.tenant_id == str(tenant_id)


@pytest.mark.asyncio
async def test_missing_zernio_profile_is_provisioned_for_current_company(monkeypatch):
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    persisted: dict[str, object] = {}

    class FakeDb:
        def __init__(self):
            self.executed_params = []

        async def execute(self, _query, params=None):
            self.executed_params.append(params)
            return None

    db = FakeDb()

    class FakeIntegrator:
        async def create_company_profile(self, company_email, company_uuid):
            assert company_email == "owner@example.com"
            assert company_uuid == tenant_id
            return {"id": "profile-123", "name": company_email}

    profile_ids = iter([None, None, "profile-123"])

    async def profile_lookup(*_args, **_kwargs):
        return next(profile_ids)

    async def persist_profile(*_args, **kwargs):
        persisted.update(kwargs)

    monkeypatch.setattr(crm_api.settings, "zernio_api_key", "test-key")
    monkeypatch.setattr(crm_api, "get_zernio_profile_id", profile_lookup)
    monkeypatch.setattr(crm_api, "IntegratorZernio", FakeIntegrator)
    monkeypatch.setattr(crm_api, "upsert_zernio_company_profile", persist_profile)

    profile_id = await crm_api._ensure_zernio_company_profile(
        cast(AsyncSession, db),
        tenant_id,
        UserClaims(user_id=str(user_id), email="owner@example.com", role="company_user", company_id=str(tenant_id)),
    )

    assert profile_id == "profile-123"
    assert persisted["company_id"] == tenant_id
    assert persisted["user_id"] == user_id
    assert db.executed_params == [{"company_id": str(tenant_id)}]


def test_linkedin_post_payload_uses_only_documented_account_id_key():
    assert _zernio_platform_payload("linkedin", "zernio-account") == [
        {"platform": "linkedin", "accountId": "zernio-account"}
    ]
