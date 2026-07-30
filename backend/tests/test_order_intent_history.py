import asyncio
from types import SimpleNamespace

from models.auxilary_models import OrderIntent
from services import openai_messaging
from services.openai_messaging import (
    build_history_text,
    detect_order_intent,
    hydrate_order_intent_customer_fields,
    is_course_guidance_request,
)


def test_build_history_text_preserves_role_content_history():
    history = [
        {"role": "user", "content": "I want the Palo Alto course"},
        {"role": "assistant", "content": "Which schedule works for you?"},
    ]

    assert build_history_text(history) == (
        "user: I want the Palo Alto course\n"
        "assistant: Which schedule works for you?"
    )


def test_course_guidance_phrases_are_detected_without_llm_guesswork():
    phrases = [
        "Hansı kurslarınız var?",
        "Ümumiyyətlə hansı sahələr üzrə tədris edirsiniz?",
        "Bilmirəm, seçimdə kömək edin",
        "Какие направления у вас есть?",
        "Не знаю, какой курс выбрать",
        "What courses do you offer?",
    ]

    assert all(is_course_guidance_request(phrase) for phrase in phrases)
    assert not is_course_guidance_request("Palo Alto kursunun qiyməti nə qədərdir?")


def test_catalog_request_overrides_incorrect_llm_question(monkeypatch):
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=(
                        '{"wants_order": true, "course_guidance_requested": false, '
                        '"ready_to_submit": false, "missing_fields": ["product_title"], '
                        '"next_question": "Hansı kursla maraqlanırsınız?"}'
                    )
                )
            )
        ]
    )
    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=lambda **_: response)
        )
    )
    monkeypatch.setattr(openai_messaging, "get_openai_client", lambda: client)

    intent = asyncio.run(
        detect_order_intent(
            user_text="Ümumiyyətlə hansı sahələr üzrə tədris edirsiniz?",
            history=[],
            knowledge_context="Palo Alto, Python, DevOps",
        )
    )

    assert intent.course_guidance_requested is True
    assert intent.ready_to_submit is False
    assert intent.missing_fields == []
    assert intent.next_question is None


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


def test_course_catalog_request_is_answered_by_bot_instead_of_repeating_question():
    course_intent = OrderIntent(
        wants_order=True,
        course_guidance_requested=True,
        ready_to_submit=False,
        detected_language="az",
        product_title=None,
        missing_fields=["product_title"],
        next_question="Hansı kursla maraqlanırsınız?",
    )

    hydrated = hydrate_order_intent_customer_fields(course_intent)

    assert hydrated.course_guidance_requested is True
    assert hydrated.ready_to_submit is False
    assert hydrated.missing_fields == []
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
