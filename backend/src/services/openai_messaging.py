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
            return "Please, contact the account owner, I can not proceed your request now"

        full_system_prompt = system_prompt

        if knowledge_context:
            full_system_prompt += (
                "\n\n"
                "Фактическая база знаний компании ниже. Используй ее как источник конкретных данных бизнеса. "
                "Не смешивай эти данные с правилами поведения. "
                "Если в базе знаний нет ответа, честно скажи, что уточнишь у менеджера.\n\n"
                f"БАЗА ЗНАНИЙ:\n{knowledge_context}"
            )

        if order_intent:
            full_system_prompt += (
                "\n\n"
                "ДАННЫЕ ПО НАМЕРЕНИЮ ЗАКАЗА:\n"
                f"Клиент хочет оформить заказ: {order_intent.wants_order}\n"
                f"Заказ готов к передаче менеджеру: {order_intent.ready_to_submit}\n"
                f"Язык клиента: {order_intent.detected_language}\n"
                f"Товар: {order_intent.product_title}\n"
                f"Цена: {order_intent.product_price}\n"
                f"Количество: {order_intent.quantity}\n"
                f"Имя клиента: {order_intent.customer_name}\n"
                f"Телефон клиента: {order_intent.customer_phone}\n"
                f"Нужна доставка: {order_intent.delivery_required}\n"
                f"Адрес доставки: {order_intent.delivery_address}\n"
                f"Время доставки: {order_intent.delivery_time}\n"
                f"Комментарий: {order_intent.comment}\n"
                f"Недостающие поля: {', '.join(order_intent.missing_fields) if order_intent.missing_fields else 'нет'}\n"
                f"Следующий вопрос клиенту: {order_intent.next_question}\n\n"
                "Правила работы с заказом:\n"
                "1. Если клиент хочет оформить заказ, но данных не хватает, задай только нужный уточняющий вопрос.\n"
                "2. Если next_question заполнен, используй его как основу ответа клиенту.\n"
                "3. Если заказ готов к передаче менеджеру, подтверди клиенту, что заказ принят и менеджер скоро свяжется.\n"
                "4. Отвечай на том же языке, на котором пишет клиент.\n"
                "5. Не придумывай имя, телефон, адрес, цену или товар.\n"
                "6. Отвечай на языке клиента, указанном в пункте 4.\n"

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


def hydrate_order_intent_customer_fields(
    order_intent: OrderIntent,
    *,
    customer_name: str | None = None,
    customer_phone: str | None = None,
) -> OrderIntent:
    """Fill reliable CRM-known customer fields before deciding whether an order is ready.

    The extractor intentionally does not invent missing data from old chat history. For
    WhatsApp/Zernio, however, the platform already gives us stable customer phone/name.
    Without this hydration, repeat customers can say "order 10" and the generic reply
    model may confirm the order while the durable order path is skipped as "missing
    phone/name".
    """
    if not order_intent.wants_order:
        return order_intent

    data = order_intent.model_dump()
    if not data.get("customer_name") and customer_name:
        data["customer_name"] = customer_name
    if not data.get("customer_phone") and customer_phone:
        data["customer_phone"] = customer_phone

    missing = set(data.get("missing_fields") or [])
    if data.get("customer_name"):
        missing.discard("customer_name")
    if data.get("customer_phone"):
        missing.discard("customer_phone")
    if data.get("product_title"):
        missing.discard("product_title")
    if data.get("delivery_required") is not True or data.get("delivery_address"):
        missing.discard("delivery_address")

    required_present = bool(data.get("product_title") and data.get("customer_name") and data.get("customer_phone"))
    delivery_ready = data.get("delivery_required") is not True or bool(data.get("delivery_address"))
    data["missing_fields"] = sorted(missing)
    data["ready_to_submit"] = bool(required_present and delivery_ready and not missing)
    if data["ready_to_submit"]:
        data["next_question"] = None
    return OrderIntent.model_validate(data)


async def detect_order_intent(
    *,
    user_text: str,
    history: list[dict],
    knowledge_context: str,
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
                "content": settings.order_intent_sys_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content or "{}"

    try:
        data = json.loads(raw)
        return OrderIntent.model_validate(data)
    except (json.JSONDecodeError, ValidationError):
        return OrderIntent(
            wants_order=False,
            ready_to_submit=False,
            confidence=0.0,
            missing_fields=[],
            next_question=None,
        )