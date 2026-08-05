import base64
import json
import logging
import uuid
from pathlib import Path
from typing import Sequence

from openai import OpenAI
from pydantic import ValidationError

from config.app_config import settings
from models.auxilary_models import OrderIntent
from services.object_storage import build_object_key, config_from_settings, upload_bytes_to_object_storage

logger = logging.getLogger(__name__)
_openai_client: OpenAI | None = None


def get_openai_client() -> OpenAI:
    global _openai_client
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    if _openai_client is None:
        _openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _openai_client


async def create_embedding(text: str) -> list[float]:
    response = get_openai_client().embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )

    return response.data[0].embedding


PRODUCT_DESCRIPTION_LANGUAGES: dict[str, tuple[str, str, str]] = {
    "az": (
        "Azerbaijani",
        "Sən biznesin bilik bazası üçün faktlara əsaslanan məhsul təsviri yazırsan. "
        "Şəkildə aydın görünməyən brend, qiymət, stok vəziyyəti, material və xüsusiyyətləri uydurma. "
        "Yalnız fotodan əminliklə başa düşülənləri Azərbaycan dilində təsvir et.",
        "Şirkətin AI botu üçün fotoya əsasən qısa məhsul təsviri yarat.",
    ),
    "en": (
        "English",
        "You write factual product descriptions for a business knowledge base. "
        "Do not invent a brand, price, availability, material, or characteristics unless they are clearly visible. "
        "Describe only what can be confidently understood from the photo, in English.",
        "Create a short product description from the photo for the company's AI bot.",
    ),
    "ru": (
        "Russian",
        "Ты составляешь фактологичное описание товара для базы знаний бизнеса. "
        "Не выдумывай бренд, цену, наличие, материал или характеристики, если их не видно. "
        "Опиши только то, что можно уверенно понять по фото, на русском языке.",
        "Создай короткое описание товара по фотографии для AI-бота компании.",
    ),
}


def normalize_product_description_language(language: str | None) -> str:
    value = (language or "az").strip().lower()
    return value if value in PRODUCT_DESCRIPTION_LANGUAGES else "az"


def product_photo_description_fallback(language: str | None) -> str:
    normalized = normalize_product_description_language(language)
    if normalized == "en":
        return "AI could not automatically describe the photo. Add the product description manually."
    if normalized == "ru":
        return "AI не смог автоматически описать фотографию. Добавь описание товара вручную."
    return "AI fotonu avtomatik təsvir edə bilmədi. Məhsul təsvirini əl ilə əlavə edin."


def generate_product_photo_description(image_path: Path, mime_type: str, language: str | None = "az") -> str:
    normalized_language = normalize_product_description_language(language)
    _, system_prompt, user_prompt = PRODUCT_DESCRIPTION_LANGUAGES[normalized_language]
    try:
        image_bytes = image_path.read_bytes()
        encoded = base64.b64encode(image_bytes).decode("ascii")
        response = get_openai_client().chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": user_prompt,
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{encoded}"},
                        },
                    ],
                },
            ],
            temperature=0.2,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception:
        logger.exception("AI product photo description failed")
        return product_photo_description_fallback(normalized_language)


def generate_custom_product_preview_image(prompt: str, company_id: uuid.UUID) -> str | None:
    """Generate and store a custom bouquet/cake preview image.

    Returns a browser-readable R2/CDN URL. Failures are non-fatal because the CRM
    can still show/send the generated visual prompt to a manager.
    """
    try:
        response = get_openai_client().images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size="1024x1024",
        )
        if not response.data:
            return None
        image_b64 = response.data[0].b64_json
        if not image_b64:
            return None
        image_bytes = base64.b64decode(image_b64)
        key = build_object_key(
            company_id=company_id,
            folder="custom-products",
            filename="ai-preview.png",
        )
        return upload_bytes_to_object_storage(
            config=config_from_settings(settings),
            key=key,
            content=image_bytes,
            content_type="image/png",
        )
    except Exception:
        logger.exception("AI custom product preview generation failed")
        return None


def transcribe_audio_bytes(audio_bytes: bytes, *, filename: str = "voice.ogg", content_type: str | None = None) -> str | None:
    try:
        import io

        file_obj = io.BytesIO(audio_bytes)
        file_obj.name = filename
        response = get_openai_client().audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=file_obj,
            response_format="text",
        )
        text = str(response or "").strip()
        return text or None
    except Exception:
        logger.exception("AI voice transcription failed content_type=%s filename=%s", content_type, filename)
        return None


def generate_reply(
    system_prompt: str,
    user_text: str,
    history: Sequence[dict[str, str]] | None = None,
    knowledge_context: str | None = None,
    order_intent: OrderIntent | None = None,
) -> str:
    try:
        if not system_prompt:
            logger.warning("System prompt is empty; fallback message returned")
            return "Hazırda sorğunu emal edə bilmirəm. Zəhmət olmasa, hesab sahibi ilə əlaqə saxlayın."

        full_system_prompt = system_prompt

        if knowledge_context:
            full_system_prompt += (
                "\n\n"
                "Şirkətin faktiki bilik bazası aşağıdadır. Konkret biznes məlumatları üçün yalnız bu mənbədən istifadə et. "
                "Bu faktları davranış qaydaları ilə qarışdırma. "
                "Cavab bilik bazasında yoxdursa, məlumatı menecerdən dəqiqləşdirəcəyini dürüst şəkildə bildir.\n\n"
                f"BİLİK BAZASI:\n{knowledge_context}"
            )

        if order_intent:
            full_system_prompt += (
                "\n\n"
                "KURS MARAĞI BARƏDƏ MƏLUMAT:\n"
                f"Müştəri kursla maraqlanır: {order_intent.wants_order}\n"
                f"Müştəriyə kurs seçimi üzrə istiqamət lazımdır: {order_intent.course_guidance_requested}\n"
                f"Müştəri menecerlə əlaqəyə razıdır: {order_intent.manager_handoff_requested}\n"
                f"Müraciət menecerə ötürülməyə hazırdır: {order_intent.ready_to_submit}\n"
                f"Müştərinin dili: {order_intent.detected_language}\n"
                f"Maraqlandığı kurs: {order_intent.product_title}\n"
                f"Kursun qiyməti: {order_intent.product_price}\n"
                f"Müştərinin adı (mövcuddursa): {order_intent.customer_name}\n"
                f"Müştərinin telefonu (mövcuddursa): {order_intent.customer_phone}\n"
                f"Qeyd: {order_intent.comment}\n"
                f"Çatışmayan sahələr: {', '.join(order_intent.missing_fields) if order_intent.missing_fields else 'yoxdur'}\n"
                f"Müştəriyə növbəti sual: {order_intent.next_question}\n\n"
                "Kurs müraciəti ilə işləmə qaydaları:\n"
                "1. Müştərinin son sualına əvvəlcə birbaşa və təbii cavab ver; əvvəlki cavabı təkrarlama.\n"
                "2. Müştəri mövcud kursları, istiqamətləri və ya seçim üçün kömək istəyirsə, bilik bazasındakı "
                "kursları sadala, hər biri barədə qısa faydalı məlumat ver və marağına uyğun seçim etməyə kömək et. "
                "Belə sorğuya yalnız 'Hansı kursla maraqlanırsınız?' sualı ilə cavab vermə.\n"
                "3. Müştəri sadəcə kursun adını yazıbsa, bilik bazasındakı uyğun məlumatı qısa təqdim et və nəyi öyrənmək istədiyini soruş.\n"
                "4. Proqram, qiymət, qrafik, müddət, format, sayt və digər sualları menecerə yönləndirmədən özün cavablandır.\n"
                "5. Cavab bilik bazasında yoxdursa, bunu dürüst bildir və yalnız onda menecerin əlaqə saxlamasını istəyib-istəmədiyini soruş.\n"
                "6. Müştəri qeydiyyata hazırdırsa, fərdi konsultasiya istəyirsə və ya söhbətdə təbii ehtiyac yaranıbsa, "
                "menecerin əlaqə saxlamasını təklif et və sual formasında açıq razılıq gözlə.\n"
                "7. Açıq razılıq olmadan müraciətin menecerə ötürüldüyünü demə. Hər cavabda menecer təklifini təkrarlama.\n"
                "8. next_question doldurulubsa, onu cavabın əsası kimi istifadə et.\n"
                "9. Say, çatdırılma, ünvan, ad və telefon soruşma.\n"
                "10. Yalnız Azərbaycan dilində cavab ver və kurs barədə fakt uydurma.\n"
            )

        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": full_system_prompt,
            }
        ]

        if history:
            messages.extend(history)

        messages.append(
            {
                "role": "user",
                "content": user_text,
            }
        )

        response = get_openai_client().chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.7,
        )

        ai_text = (response.choices[0].message.content or "").strip()

        if not ai_text:
            logger.warning("Empty AI response received")
            return "Sorry, I can not proceed your request now 🙏"

        return ai_text

    except Exception:
        logger.exception("AI generate_reply failed")
        return "Sorry, I can not proceed your request now 🙏"


def build_history_text(history: list[dict]) -> str:
    if not history:
        return ""

    lines: list[str] = []

    for item in history[-10:]:
        speaker = item.get("direction") or item.get("role") or "unknown"
        text = item.get("text") or item.get("body") or item.get("content") or ""
        if not str(text).strip():
            continue
        lines.append(f"{speaker}: {text}")

    return "\n".join(lines)


def is_course_guidance_request(user_text: str) -> bool:
    """Recognize explicit catalog/recommendation requests without relying on the LLM."""
    text = " ".join((user_text or "").casefold().split())
    guidance_markers = (
        "hansı kurs",
        "hansi kurs",
        "kurslarınız var",
        "kurslariniz var",
        "hansı sah",
        "hansi sah",
        "hansı istiqam",
        "hansi istiqam",
        "bilmirəm",
        "bilmirem",
        "seçimdə kömək",
        "secimde komek",
        "seçməyə kömək",
        "какие курс",
        "какие направлен",
        "каким направлениям",
        "не знаю, какой курс",
        "не знаю какой курс",
        "помоги выбрать",
        "помогите выбрать",
        "what courses",
        "which courses",
        "what do you teach",
        "help me choose",
        "don't know which course",
        "do not know which course",
    )
    return any(marker in text for marker in guidance_markers)


def _course_interest_question(language: str | None) -> str:
    normalized = (language or "").strip().lower()
    if normalized.startswith("ru") or "russian" in normalized:
        return "Какой курс вас интересует?"
    if normalized.startswith("en") or "english" in normalized:
        return "Which course are you interested in?"
    return "Hansı kursla maraqlanırsınız?"


def hydrate_order_intent_customer_fields(
    order_intent: OrderIntent,
    *,
    customer_name: str | None = None,
    customer_phone: str | None = None,
) -> OrderIntent:
    """Normalize a legacy order-intent payload into a course lead.

    Platform identity is sufficient to contact the lead. Name and phone are useful
    metadata but are never required. A lead becomes submittable only when a course
    is known and the customer has explicitly requested or accepted manager contact.
    Legacy commerce fields are explicitly cleared so downstream code cannot revive
    quantity or delivery questions from an inconsistent model response.
    """
    if not order_intent.wants_order:
        return order_intent

    data = order_intent.model_dump()
    if not data.get("customer_name") and customer_name:
        data["customer_name"] = customer_name
    if not data.get("customer_phone") and customer_phone:
        data["customer_phone"] = customer_phone

    data["quantity"] = None
    data["delivery_required"] = None
    data["delivery_address"] = None
    data["delivery_time"] = None

    if data.get("product_title"):
        data["missing_fields"] = []
        data["ready_to_submit"] = bool(data.get("manager_handoff_requested"))
        data["next_question"] = None
    elif data.get("course_guidance_requested"):
        data["missing_fields"] = []
        data["ready_to_submit"] = False
        data["next_question"] = None
    else:
        data["missing_fields"] = ["product_title"]
        data["ready_to_submit"] = False
        data["next_question"] = _course_interest_question(data.get("detected_language"))

    return OrderIntent.model_validate(data)


async def detect_order_intent(
    *,
    user_text: str,
    history: list[dict],
    knowledge_context: str,
    system_prompt: str | None = None,
) -> OrderIntent:
    history_text = build_history_text(history)

    user_prompt = f"""
Conversation history:
{history_text or "No previous messages."}

Knowledge base context:
{knowledge_context or "No relevant knowledge base entries found."}

Latest customer message:
{user_text}
""".strip()

    response = get_openai_client().chat.completions.create(
        model="gpt-4.1-mini",
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": (system_prompt or settings.order_intent_sys_prompt).strip(),
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content or "{}"

    guidance_requested = is_course_guidance_request(user_text)

    try:
        data = json.loads(raw)
        intent = OrderIntent.model_validate(data)
        if not guidance_requested:
            return intent

        guidance_data = intent.model_dump()
        guidance_data["wants_order"] = True
        guidance_data["course_guidance_requested"] = True
        guidance_data["manager_handoff_requested"] = False
        guidance_data["ready_to_submit"] = False
        guidance_data["missing_fields"] = []
        guidance_data["next_question"] = None
        return OrderIntent.model_validate(guidance_data)
    except (json.JSONDecodeError, ValidationError):
        return OrderIntent(
            wants_order=guidance_requested,
            course_guidance_requested=guidance_requested,
            manager_handoff_requested=False,
            ready_to_submit=False,
            confidence=0.0,
            missing_fields=[],
            next_question=None,
        )