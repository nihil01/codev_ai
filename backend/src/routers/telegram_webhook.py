from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config.deps import get_db
from services.conversation_control import apply_conversation_action, bind_telegram_token
from services.manager_notifications import register_telegram_company_manager

router = APIRouter(prefix="/telegram", tags=["telegram"])
logger = logging.getLogger(__name__)


@router.post("/webhook")
async def telegram_webhook(request: Request, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    update = await request.json()

    message = update.get("message") or {}
    text_value = str(message.get("text") or "")
    if text_value.startswith("/start manager_"):
        token = text_value.split("manager_", 1)[1].strip()
        chat = message.get("chat") or {}
        sender = message.get("from") or {}
        if not chat.get("id") or not sender.get("id"):
            return {"ok": False, "error": "telegram_chat_or_user_missing"}
        try:
            row = await register_telegram_company_manager(
                db,
                token=token,
                telegram_user_id=int(str(sender.get("id"))),
                telegram_chat_id=int(str(chat.get("id"))),
                telegram_username=sender.get("username"),
                first_name=sender.get("first_name"),
                last_name=sender.get("last_name"),
                language_code=sender.get("language_code"),
            )
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "action": "manager_registered", "manager_id": str(row["id"])}

    if text_value.startswith("/start connect_"):
        token = text_value.split("connect_", 1)[1].strip()
        chat = message.get("chat") or {}
        sender = message.get("from") or {}
        if not chat.get("id") or not sender.get("id"):
            return {"ok": False, "error": "telegram_chat_or_user_missing"}
        ok = await bind_telegram_token(
            db,
            token=token,
            chat_id=int(str(chat.get("id"))),
            telegram_user_id=int(str(sender.get("id"))),
            username=sender.get("username"),
        )
        return {"ok": ok, "action": "connect"}

    callback = update.get("callback_query") or {}
    callback_data = str(callback.get("data") or "")
    if callback_data.startswith("take:"):
        sender = callback.get("from") or {}
        telegram_user_id = sender.get("id")
        user_result = await db.execute(
            text("select id from users where telegram_user_id = :telegram_user_id and telegram_notifications_enabled = true limit 1"),
            {"telegram_user_id": telegram_user_id},
        )
        user_id = user_result.scalar_one_or_none()
        if not user_id:
            return {"ok": False, "error": "telegram_user_not_bound"}

        _, channel, conversation_id_text = callback_data.split(":", 2)
        conversation_id = uuid.UUID(conversation_id_text)
        try:
            await apply_conversation_action(
                db,
                channel=channel,  # type: ignore[arg-type]
                conversation_id=conversation_id,
                actor_id=user_id,
                action="take",
                cloud=False,
            )
        except ValueError:
            if channel != "whatsapp":
                raise
            await apply_conversation_action(
                db,
                channel="whatsapp",
                conversation_id=conversation_id,
                actor_id=user_id,
                action="take",
                cloud=True,
            )
        return {"ok": True, "action": "take"}

    if callback_data.startswith("snooze:"):
        return {"ok": True, "action": "snooze"}

    return {"ok": True, "action": "ignored"}
