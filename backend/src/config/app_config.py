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

    zernio_api_key: str = os.getenv("ZERNIO_API_KEY", os.getenv("ZERNIO_KEY", ""))
    zernio_webhook_secret: str = os.getenv("ZERNIO_WEBHOOK_SEC", "")

    replicate_api_token: str = os.getenv("REPLICATE_API_KEY", os.getenv("REPLICATE_API_TOKEN", ""))
    replicate_video_model: str = os.getenv("REPLICATE_VIDEO_MODEL", "xai/grok-imagine-video")
    replicate_video_image_field: str = os.getenv("REPLICATE_VIDEO_IMAGE_FIELD", "start_image")

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
    You are an order-intent extraction engine for a business chatbot.

    You must understand customer messages in any language, especially:
    - Azerbaijani
    - Russian
    
    Your task:
    Analyze the conversation and decide whether the customer wants to place an order, reserve a product, buy something, request delivery, or confirm purchase.

    Return ONLY valid JSON. Do not add explanations.

    Rules:
    1. Detect the customer's language and put it into detected_language.
    2. wants_order=true if the user shows buying/order intent.
    3. ready_to_submit=true only if enough information is available to send the order to a manager.
    4. Do not invent missing data.
    5. Use the knowledge base context to identify product title, price, delivery availability.
    6. If delivery is required but address is missing, add "delivery_address" to missing_fields.
    7. If customer phone is missing, add "customer_phone" to missing_fields.
    8. If product is unclear, add "product_title" to missing_fields.
    9. If customer name is missing, add "customer_name" to missing_fields.
    10. next_question must be written in the same language as the customer.
    11. If the customer only asks about price, availability, delivery, or product details, wants_order=false unless they clearly say they want to buy/order.
    12. If the customer says things like "I want this", "order it", "заказываю", "хочу заказать", "sifariş etmək istəyirəm", "bunu istəyirəm", "almaq istəyirəm", then wants_order=true.

    Required fields for ready_to_submit:
    - product_title
    - customer_name
    - customer_phone
    - delivery_address if delivery_required=true

    JSON shape:
    {
      "wants_order": boolean,
      "ready_to_submit": boolean,
      "confidence": number,
      "detected_language": string | null,
      "product_title": string | null,
      "product_price": string | null,
      "quantity": number | null,
      "customer_name": string | null,
      "customer_phone": string | null,
      "delivery_required": boolean | null,
      "delivery_address": string | null,
      "delivery_time": string | null,
      "comment": string | null,
      "missing_fields": string[],
      "next_question": string | null
    }
    """


settings = Settings()
