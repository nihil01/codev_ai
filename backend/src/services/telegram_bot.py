import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from config.app_config import settings
from db.db import SessionLocal
from services.manager_notifications import register_telegram_company_manager

logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик команды /start. Регистрирует менеджера по deep-link payload
    manager_<token>, созданному CRM для конкретной компании.
    """

    user = update.effective_user
    message = update.effective_message
    chat = update.effective_chat

    if not user or not message or not chat:
        return

    payload = context.args[0].strip() if context.args else ""
    logger.info(
        "Telegram /start received: user_id=%s username=%s payload=%s",
        user.id,
        user.username,
        payload[:32],
    )

    if payload.startswith("manager_"):
        token = payload.removeprefix("manager_").strip()
        try:
            async with SessionLocal() as db:
                row = await register_telegram_company_manager(
                    db,
                    token=token,
                    telegram_user_id=user.id,
                    telegram_chat_id=chat.id,
                    telegram_username=user.username,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    language_code=user.language_code,
                )
            await message.reply_text(
                f"✅ You are registered as a company manager.\nName: {row['display_name']}"
            )
        except ValueError as exc:
            await message.reply_text(f"❌ Registration link is invalid: {exc}")
        except Exception:
            logger.exception("Telegram manager registration failed")
            await message.reply_text("❌ Could not register the manager. Please create a new link in CRM.")
        return

    await message.reply_text(
        "Hi! The bot is running. To register as a manager, open the link from CRM."
    )

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Echo the user message."""
    await update.message.reply_text(update.message.text)


def build_bot() -> Application:
    """
    Создает Telegram Application и регистрирует обработчики.
    Здесь НЕ запускаем polling.
    """

    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")

    application = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    # on non command i.e message - echo the message on Telegram
    # application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    return application


async def start_bot() -> Application | None:
    """
    Запускает Telegram polling внутри уже работающего event loop FastAPI.
    """

    if not settings.telegram_polling_enabled:
        logger.info("Telegram polling is disabled by TELEGRAM_POLLING_ENABLED=false")
        return None

    application = build_bot()

    try:
        await application.initialize()

        if application.updater is None:
            raise RuntimeError("Telegram Updater was not initialized")

        # Важно, если ранее у бота был установлен webhook.
        # Polling и webhook одновременно использовать нельзя.
        await application.bot.delete_webhook(
            drop_pending_updates=False
        )

        await application.start()

        await application.updater.start_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=False,
        )

        logger.info("Telegram bot polling started successfully")

        return application

    except Exception:
        logger.exception("Failed to start Telegram bot")

        if application.updater and application.updater.running:
            await application.updater.stop()

        if application.running:
            await application.stop()

        await application.shutdown()

        raise


async def stop_bot(application: Application | None) -> None:
    """
    Корректно останавливает polling и закрывает HTTP-сессию Telegram.
    """

    if application is None:
        return

    logger.info("Stopping Telegram bot...")

    if application.updater and application.updater.running:
        await application.updater.stop()

    if application.running:
        await application.stop()

    await application.shutdown()

    logger.info("Telegram bot stopped successfully")