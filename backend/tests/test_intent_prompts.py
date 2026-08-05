from config.app_config import settings
from services.intent_prompts import DEFAULT_INTENT_PROMPT, resolve_intent_prompt


def test_default_intent_prompt_is_the_existing_course_classifier() -> None:
    assert DEFAULT_INTENT_PROMPT == settings.order_intent_sys_prompt.strip()


def test_company_intent_prompt_overrides_default_without_accepting_blank_text() -> None:
    assert resolve_intent_prompt("  Şirkətə özəl intent promptu  ") == "Şirkətə özəl intent promptu"
    assert resolve_intent_prompt("   ") == DEFAULT_INTENT_PROMPT
