from config.app_config import settings
from services.webhooks import build_order_confirmation_message


def test_intent_prompt_is_course_specific_and_does_not_request_shop_fields():
    prompt = settings.order_intent_sys_prompt.lower()

    assert "course" in prompt
    assert "which course" in prompt
    assert "explicitly agrees to be contacted by a manager" in prompt
    assert "do not treat merely naming a course" in prompt
    assert "carry that course into product_title" in prompt
    assert "course_guidance_requested=true" in prompt
    assert "asks which courses or study areas are available" in prompt
    assert "never ask for quantity" in prompt
    assert "always return quantity" in prompt
    assert "name and phone are optional" in prompt


def test_confirmation_message_refers_to_course_request():
    assert "kurs" in build_order_confirmation_message("az").lower()
    assert "курс" in build_order_confirmation_message("ru").lower()
    assert "course" in build_order_confirmation_message("en").lower()
    assert "order" not in build_order_confirmation_message("en").lower()
