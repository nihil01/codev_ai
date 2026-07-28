from services.business_features import build_inventory_unavailable_reply, find_order_stock_conflict
from services.voice_transcription import extract_audio_url, extract_whatsapp_cloud_audio_media_id, is_audio_message_type


def test_find_order_stock_conflict_detects_requested_quantity_above_available():
    conflict = find_order_stock_conflict(
        product_title="bulka",
        requested_quantity=3,
        knowledge_entries=[{"title": "Bulka", "content": "fresh bread", "quantity_available": 1}],
    )

    assert conflict is not None
    assert conflict == ("Bulka", 3, 1)
    assert "заказать 3" in build_inventory_unavailable_reply(
        language="ru",
        product_title=conflict[0],
        requested_quantity=conflict[1],
        available_quantity=conflict[2],
    )


def test_find_order_stock_conflict_ignores_untracked_quantity():
    assert find_order_stock_conflict(
        product_title="bulka",
        requested_quantity=3,
        knowledge_entries=[{"title": "Bulka", "content": "fresh bread", "quantity_available": None}],
    ) is None


def test_voice_payload_extractors_support_zernio_and_whatsapp_cloud_shapes():
    payload = {
        "message": {
            "type": "voice",
            "attachments": [{"mimeType": "audio/ogg", "downloadUrl": "https://cdn.example/voice.ogg"}],
        }
    }

    assert is_audio_message_type("voice")
    assert extract_audio_url(payload) == "https://cdn.example/voice.ogg"
    assert extract_whatsapp_cloud_audio_media_id({"type": "audio", "audio": {"id": "media-1"}}) == "media-1"
