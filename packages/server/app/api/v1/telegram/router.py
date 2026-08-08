"""Telegram webhook endpoint."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request

from api.v1.planner.controller import PlannerController
from core import Response
from core.config import config
from services.telegram_bot import (
    TelegramBotService,
    format_events_table,
    message_has_image,
)

telegram_router = APIRouter(prefix="/telegram", tags=["Telegram"])


@telegram_router.post("/webhook")
async def telegram_webhook(request: Request):
    """
    Handle Telegram updates.

    Photos/image documents are extracted via the planner pipeline and replied as a table.
    """
    try:
        update: dict[str, Any] = await request.json()
    except Exception:
        update = {}

    update_id = update.get("update_id")
    message = update.get("message") or update.get("edited_message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    from_user = message.get("from") or {}
    text = message.get("text")
    has_photo = bool(message.get("photo"))
    has_document = bool(message.get("document"))

    telegram_reply_sent = False
    telegram_reply_error: Optional[str] = None
    extract_summary: Optional[dict[str, Any]] = None

    bot = TelegramBotService()
    if chat_id is not None and config.TELEGRAM_BOT_TOKEN:
        try:
            if message_has_image(message):
                extract_summary = await _handle_image_extract(
                    bot=bot,
                    chat_id=chat_id,
                    message=message,
                )
                telegram_reply_sent = True
            else:
                help_text = (
                    "School Calendar bot is online.\n"
                    "Send a planner photo to extract Holidays (green) and PTC (yellow)."
                )
                telegram_reply_sent = await bot.send_message(chat_id=chat_id, text=help_text)
        except Exception as exc:  # noqa: BLE001 - keep webhook 200 for Telegram retries
            telegram_reply_error = str(exc)
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"Could not process that update.\n{exc}",
                    parse_mode=None,
                )
                telegram_reply_sent = True
            except Exception as send_exc:  # noqa: BLE001
                telegram_reply_error = f"{telegram_reply_error}; reply failed: {send_exc}"

    body = {
        "ok": True,
        "message": "Telegram webhook acknowledged",
        "update_id": update_id,
        "chat_id": chat_id,
        "from_user_id": from_user.get("id"),
        "text": text,
        "has_photo": has_photo,
        "has_document": has_document,
        "telegram_reply_sent": telegram_reply_sent,
        "telegram_reply_error": telegram_reply_error,
        "extract": extract_summary,
    }
    return Response.success(
        body=body,
        message="Telegram update acknowledged.",
        status_code=200,
    )


async def _handle_image_extract(
    *,
    bot: TelegramBotService,
    chat_id: int | str,
    message: dict[str, Any],
) -> dict[str, Any]:
    await bot.send_message(chat_id=chat_id, text="Processing image…")

    image = await bot.download_image_from_message(message)
    try:
        result = await PlannerController().extract_from_bytes(
            image_bytes=image.content,
            content_type=image.content_type,
            filename=image.filename,
        )
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        await bot.send_message(
            chat_id=chat_id,
            text=f"Extraction failed.\n{detail}",
            parse_mode=None,
        )
        return {"ok": False, "error": detail, "event_count": 0}

    table = format_events_table(
        events=result.get("events") or [],
        planner_title=result.get("planner_title"),
    )
    await bot.send_message(chat_id=chat_id, text=table, parse_mode="HTML")
    return {
        "ok": True,
        "event_count": result.get("event_count", 0),
        "planner_title": result.get("planner_title"),
    }
