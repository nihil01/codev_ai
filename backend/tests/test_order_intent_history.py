from models.auxilary_models import OrderIntent
from services.openai_messaging import build_history_text, hydrate_order_intent_customer_fields


def test_build_history_text_preserves_role_content_history():
    history = [
        {"role": "user", "content": "I want the Palo Alto course"},
        {"role": "assistant", "content": "Which schedule works for you?"},
    ]

    assert build_history_text(history) == (
        "user: I want the Palo Alto course\n"
        "assistant: Which schedule works for you?"
    )


def test_known_course_continues_with_bot_until_manager_consent():
    course_intent = OrderIntent(
        wants_order=True,
        ready_to_submit=True,
        confidence=0.95,
        detected_language="az",
        product_title="Palo Alto",
        product_price="120 AZN",
        quantity=3,
        delivery_required=True,
        delivery_address="Baku",
        missing_fields=["customer_name", "customer_phone", "delivery_address"],
        next_question="Telefon nömrəniz nədir?",
    )

    hydrated = hydrate_order_intent_customer_fields(course_intent)

    assert hydrated.ready_to_submit is False
    assert hydrated.missing_fields == []
    assert hydrated.next_question is None
    assert hydrated.quantity is None
    assert hydrated.delivery_required is None
    assert hydrated.delivery_address is None


def test_explicit_manager_consent_makes_course_lead_ready():
    course_intent = OrderIntent(
        wants_order=True,
        manager_handoff_requested=True,
        detected_language="az",
        product_title="Palo Alto",
    )

    hydrated = hydrate_order_intent_customer_fields(course_intent, customer_name="Aysel")

    assert hydrated.manager_handoff_requested is True
    assert hydrated.ready_to_submit is True
    assert hydrated.customer_name == "Aysel"
    assert hydrated.next_question is None


def test_course_interest_asks_only_which_course_when_course_is_unknown():
    course_intent = OrderIntent(
        wants_order=True,
        ready_to_submit=True,
        detected_language="ru",
        customer_name="Иван",
        customer_phone="+994501234567",
        missing_fields=["delivery_address", "quantity"],
        next_question="Какой адрес доставки?",
    )

    hydrated = hydrate_order_intent_customer_fields(course_intent)

    assert hydrated.ready_to_submit is False
    assert hydrated.missing_fields == ["product_title"]
    assert hydrated.next_question == "Какой курс вас интересует?"
