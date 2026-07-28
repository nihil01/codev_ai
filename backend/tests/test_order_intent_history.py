from models.auxilary_models import OrderIntent
from services.openai_messaging import build_history_text, hydrate_order_intent_customer_fields


def test_build_history_text_preserves_role_content_history_for_order_intent():
    history = [
        {"role": "user", "content": "Привет я хочу оформить заказ на булку с маком"},
        {"role": "assistant", "content": "Пожалуйста, укажите ваше имя."},
        {"role": "user", "content": "Орхан Нарбеков"},
        {"role": "assistant", "content": "Пожалуйста, укажите ваш номер телефона."},
        {"role": "user", "content": "+994501234567"},
    ]

    history_text = build_history_text(history)

    assert "user: Привет я хочу оформить заказ на булку с маком" in history_text
    assert "assistant: Пожалуйста, укажите ваше имя." in history_text
    assert "user: Орхан Нарбеков" in history_text
    assert "user: +994501234567" in history_text
    assert "unknown:" not in history_text


def test_hydrate_order_intent_uses_reliable_whatsapp_customer_fields_for_repeat_orders():
    order_intent = OrderIntent(
        wants_order=True,
        ready_to_submit=True,
        confidence=0.95,
        detected_language="Azerbaijani",
        product_title="Bulka",
        product_price="3 AZN",
        quantity=10,
        delivery_required=False,
        missing_fields=["customer_name", "customer_phone"],
        next_question="Zəhmət olmasa, adınızı və telefon nömrənizi verə bilərsiniz?",
    )

    hydrated = hydrate_order_intent_customer_fields(
        order_intent,
        customer_name="Orkhan",
        customer_phone="994519738342",
    )

    assert hydrated.ready_to_submit is True
    assert hydrated.customer_name == "Orkhan"
    assert hydrated.customer_phone == "994519738342"
    assert hydrated.missing_fields == []
    assert hydrated.next_question is None


def test_hydrate_order_intent_downgrades_inconsistent_ready_state_without_known_customer_fields():
    order_intent = OrderIntent(
        wants_order=True,
        ready_to_submit=True,
        product_title="Bulka",
        quantity=10,
        delivery_required=False,
        missing_fields=["customer_name", "customer_phone"],
        next_question="Zəhmət olmasa, adınızı və telefon nömrənizi verə bilərsiniz?",
    )

    hydrated = hydrate_order_intent_customer_fields(order_intent)

    assert hydrated.ready_to_submit is False
    assert hydrated.missing_fields == ["customer_name", "customer_phone"]
    assert hydrated.next_question
