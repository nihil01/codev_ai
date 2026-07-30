from models.auxilary_models import OrderIntent
from services.openai_messaging import build_history_text, hydrate_order_intent_customer_fields


def test_build_history_text_preserves_role_content_history_for_course_interest():
    history = [
        {"role": "user", "content": "Python kursu ilə maraqlanıram"},
        {"role": "assistant", "content": "Python kursu barədə məlumat verim."},
        {"role": "user", "content": "Qiyməti nə qədərdir?"},
    ]

    history_text = build_history_text(history)

    assert "user: Python kursu ilə maraqlanıram" in history_text
    assert "assistant: Python kursu barədə məlumat verim." in history_text
    assert "user: Qiyməti nə qədərdir?" in history_text
    assert "unknown:" not in history_text


def test_course_lead_is_ready_when_course_is_known_without_phone_or_name():
    course_intent = OrderIntent(
        wants_order=True,
        ready_to_submit=False,
        confidence=0.95,
        detected_language="az",
        product_title="Python Backend",
        product_price="120 AZN",
        missing_fields=["customer_name", "customer_phone", "quantity", "delivery_address"],
        next_question="Telefon nömrənizi və neçə ədəd istədiyinizi yazın.",
    )

    hydrated = hydrate_order_intent_customer_fields(course_intent)

    assert hydrated.ready_to_submit is True
    assert hydrated.missing_fields == []
    assert hydrated.next_question is None
    assert hydrated.quantity is None
    assert hydrated.delivery_required is None
    assert hydrated.delivery_address is None


def test_course_lead_asks_only_which_course_when_course_is_unknown():
    course_intent = OrderIntent(
        wants_order=True,
        ready_to_submit=False,
        detected_language="ru",
        missing_fields=["customer_name", "customer_phone", "product_title", "quantity"],
        next_question="Какой товар, количество и номер телефона?",
    )

    hydrated = hydrate_order_intent_customer_fields(
        course_intent,
        customer_name="Orkhan",
        customer_phone="994519738342",
    )

    assert hydrated.ready_to_submit is False
    assert hydrated.missing_fields == ["product_title"]
    assert hydrated.next_question == "Какой курс вас интересует?"
    assert hydrated.customer_name == "Orkhan"
    assert hydrated.customer_phone == "994519738342"
