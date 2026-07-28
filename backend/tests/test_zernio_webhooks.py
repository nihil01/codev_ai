import json
import inspect
from pathlib import Path

from services.zernio_webhooks import _extract_zernio_sent_message_id, parse_zernio_message_payload, persist_zernio_whatsapp_message


def load_sample(name: str) -> dict:
    return json.loads((Path(__file__).parent / "fixtures" / name).read_text())


def test_parse_instagram_message_received_payload():
    parsed = parse_zernio_message_payload(load_sample("zernio_instagram_message_received.json"))

    assert parsed is not None
    assert parsed["platform"] == "instagram"
    assert parsed["direction"] == "inbound"
    assert parsed["zernio_account_id"] == "6a3859815f7d1751ab34afcc"
    assert parsed["zernio_profile_id"] == "6a384fdd0ba364270ea39d0e"
    assert parsed["zernio_conversation_id"] == "6a38d04f5f7d1751ab4691ac"
    assert parsed["customer_id"] == "1382442530307621"
    assert parsed["customer_username"] == "orkhanar"
    assert parsed["text"] == "Merhaba"
    assert parsed["sent_at"] is not None
    assert parsed["sent_at"].isoformat() == "2026-06-22T06:29:47.688000+00:00"


def test_parse_instagram_outgoing_payload_keeps_customer_participant():
    parsed = parse_zernio_message_payload(load_sample("zernio_instagram_message_outgoing.json"))

    assert parsed is not None
    assert parsed["platform"] == "instagram"
    assert parsed["direction"] == "outbound"
    assert parsed["zernio_account_id"] == "6a3b64259d9472faaecd089f"
    assert parsed["zernio_conversation_id"] == "6a3b660c9d9472faaecd1413"
    assert parsed["customer_id"] == "1382442530307621"
    assert parsed["customer_username"] == "orkhanar"
    assert parsed["customer_name"] == "Orik"
    assert parsed["text"] == "salam, necesiniz ?"


def test_parse_ignores_non_message_events():
    assert parse_zernio_message_payload({"event": "account.connected", "account": {"id": "a"}}) is None


def test_extract_zernio_sent_message_id_from_common_shapes():
    assert _extract_zernio_sent_message_id({"messageId": "m1"}) == "m1"
    assert _extract_zernio_sent_message_id({"message": {"id": "m2"}}) == "m2"
    assert _extract_zernio_sent_message_id({"messages": [{"id": "m3"}]}) == "m3"


def test_whatsapp_message_persist_is_idempotent_by_company_mid():
    source = inspect.getsource(persist_zernio_whatsapp_message)
    assert "on conflict (company_id, whatsapp_mid) where whatsapp_mid is not null" in source
    assert "returning id" in source
