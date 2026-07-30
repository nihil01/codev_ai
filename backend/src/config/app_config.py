import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_base_url: str = os.getenv("APP_BASE_URL", "http://127.0.0.1:8300/")
    redirect_uri: str = os.getenv("REDIRECT_URI", "http://127.0.0.1:8300/auth/callback")

    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_bot_username: str = os.getenv("TELEGRAM_BOT_USERNAME", "")
    telegram_polling_enabled: bool = os.getenv("TELEGRAM_POLLING_ENABLED", "false").lower() in {"1", "true", "yes", "on"}

    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    JWT_SECRET: str = os.getenv("JWT_SECRET", "")

    # Meta webhook/OAuth settings stay empty unless the official provider is used.
    VERIFY_TOKEN: str = os.getenv("VERIFY_TOKEN", "")
    INSTAGRAM_APP_SECRET: str = os.getenv("INSTAGRAM_APP_SECRET", os.getenv("META_APP_SECRET", ""))
    meta_app_id: str = os.getenv("META_APP_ID", os.getenv("INSTAGRAM_APP_ID", ""))
    meta_app_secret: str = os.getenv("META_APP_SECRET", os.getenv("INSTAGRAM_APP_SECRET", ""))
    meta_api_version: str = os.getenv("META_API_VERSION", "v21.0")

    # Codev is a single-owner application. Credentials are provisioned only
    # through the environment and never receive source-controlled defaults.
    single_user_email: str = os.getenv("SINGLE_USER_EMAIL", "")
    single_user_password: str = os.getenv("SINGLE_USER_PASSWORD", "")
    single_user_display_name: str = os.getenv("SINGLE_USER_DISPLAY_NAME", "Codev")

    zernio_api_key: str = os.getenv("ZERNIO_API_KEY", os.getenv("ZERNIO_KEY", ""))
    zernio_webhook_secret: str = os.getenv("ZERNIO_WEBHOOK_SEC", "")

    instagram_integration_provider: str = os.getenv("INSTAGRAM_INTEGRATION_PROVIDER", "meta_official")
    whatsapp_integration_provider: str = os.getenv("WHATSAPP_INTEGRATION_PROVIDER", "meta_official")

    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://codev:codev@localhost:5465/codev",
    )
    object_storage_endpoint_url: str = os.getenv("OBJECT_STORAGE_ENDPOINT_URL", os.getenv("R2_ENDPOINT_URL", ""))
    object_storage_access_key_id: str = os.getenv("OBJECT_STORAGE_ACCESS_KEY_ID", os.getenv("R2_ACCESS_KEY_ID", ""))
    object_storage_secret_access_key: str = os.getenv("OBJECT_STORAGE_SECRET_ACCESS_KEY", os.getenv("R2_SECRET_ACCESS_KEY", ""))
    object_storage_bucket: str = os.getenv("OBJECT_STORAGE_BUCKET", os.getenv("R2_BUCKET", "codev"))
    object_storage_region: str = os.getenv("OBJECT_STORAGE_REGION", "auto")
    object_storage_public_base_url: str = os.getenv(
        "OBJECT_STORAGE_PUBLIC_BASE_URL",
        os.getenv("R2_PUBLIC_BASE_URL", ""),
    )

    pyway_database_host: str = os.getenv("PYWAY_DATABASE_HOST", "localhost")
    pyway_database_port: str = os.getenv("PYWAY_DATABASE_PORT", "5465")
    pyway_database_name: str = os.getenv("PYWAY_DATABASE_NAME", "codev")
    pyway_database_username: str = os.getenv("PYWAY_DATABASE_USERNAME", "codev")
    pyway_database_password: str = os.getenv("PYWAY_DATABASE_PASSWORD", "")

    order_intent_sys_prompt: str = """
    You are a course-interest extraction engine for an education business chatbot.

    Understand customer messages in any language, especially Azerbaijani and Russian.
    Detect whether the customer is interested in a course and extract the specific course.
    The legacy JSON field names must remain unchanged for API compatibility:
    - wants_order means wants_course_information or wants_to_enroll
    - product_title means course_title
    - product_price means course_price

    Return ONLY valid JSON. Do not add explanations.

    Rules:
    1. Detect the customer's language and put its ISO code into detected_language (az, ru, or en).
    2. Set wants_order=true when the customer asks about a specific course, its price, schedule,
       syllabus, duration, format, enrollment, or otherwise shows interest in studying that course.
    3. Set course_guidance_requested=true when the customer asks which courses or study areas are available,
       asks for recommendations or help choosing, or says they do not know which course they want. In this
       case keep product_title null unless a course is explicitly known. This state means the conversational
       assistant must present suitable options from the knowledge base instead of repeating "which course?".
    4. Set manager_handoff_requested=true only when the latest customer message explicitly asks
       to speak with a manager, asks to be called/contacted, or explicitly agrees to be contacted by a manager
       after the assistant offered this. A bare "yes" counts only when the previous assistant message clearly
       offered manager contact. When manager_handoff_requested=true and the course is present in history,
       also set wants_order=true and carry that course into product_title. Do not treat merely naming a course
       or asking about its syllabus, price, schedule, website, or format as manager consent.
    5. Set ready_to_submit=true only when a specific course_title is known AND
       manager_handoff_requested=true. Otherwise ready_to_submit=false.
    6. If the course is unclear and course_guidance_requested=false, missing_fields must contain only
       "product_title" and next_question must ask which course interests the customer, in their language.
       If course_guidance_requested=true, missing_fields must be empty and next_question must be null.
    7. If the course is known but manager consent was not given, missing_fields must be empty and
       next_question must be null. The conversational assistant will answer the customer's question.
    8. Use the knowledge base to identify the course title and price. Never invent facts.
    9. Never ask for quantity, delivery, address, customer name, or phone. Name and phone are optional.
    10. Always return quantity, delivery_required, delivery_address, and delivery_time as null.
    11. Preserve useful customer wishes (for example evening group or online format) in comment.

    JSON shape:
    {
      "wants_order": boolean,
      "course_guidance_requested": boolean,
      "manager_handoff_requested": boolean,
      "ready_to_submit": boolean,
      "confidence": number,
      "detected_language": string | null,
      "product_title": string | null,
      "product_price": string | null,
      "quantity": null,
      "customer_name": string | null,
      "customer_phone": string | null,
      "delivery_required": null,
      "delivery_address": null,
      "delivery_time": null,
      "comment": string | null,
      "missing_fields": string[],
      "next_question": string | null
    }
    """


settings = Settings()
