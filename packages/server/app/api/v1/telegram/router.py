"""Telegram webhook endpoint."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request

from api.v1.planner.controller import PlannerController
from core import Response
from core.config import config
from core.session import AsyncSessionLocal
from services.calendar_query import (
    CalendarQueryIntent,
    CalendarQueryService,
    parse_query_callback,
    parse_query_text,
)
from services.telegram_access import (
    TelegramAccessService,
    parse_access_callback,
)
from services.telegram_bot import (
    TelegramBotService,
    format_events_table,
    message_has_image,
    query_actions_keyboard,
    upload_reject_keyboard,
)
from services.telegram_ingest import TelegramIngestService, parse_class_label
from services.telegram_session import (
    TelegramSessionState,
    telegram_sessions,
)

telegram_router = APIRouter(prefix="/telegram", tags=["Telegram"])

UPLOAD_KEYWORDS = {"upload", "save", "yes", "confirm", "y"}
REJECT_KEYWORDS = {"reject", "no", "cancel", "discard", "n"}
HELP_KEYWORDS = {"/start", "/help", "help", "hi", "hello"}


@telegram_router.post("/webhook")
async def telegram_webhook(request: Request):
    """
    Handle Telegram updates.

    Flow: class name → planner photo → preview table → Upload / Reject buttons.
    With a class set, query buttons answer upcoming / next / last / this month.
    """
    try:
        update: dict[str, Any] = await request.json()
    except Exception:
        update = {}

    bot = TelegramBotService()

    update_id = update.get("update_id")
    callback_query = update.get("callback_query") or {}
    message = update.get("message") or update.get("edited_message") or {}
    if callback_query:
        message = callback_query.get("message") or message

    chat = message.get("chat") or {}
    chat_id = chat.get("id", None)
    from_user = (callback_query.get("from") if callback_query else None) or message.get("from") or {}
    user_id = from_user.get("id", None)

    text = (message.get("text") or "").strip()
    callback_data = str(callback_query.get("data") or "").strip()
    has_photo = bool(message.get("photo")) and not callback_query
    has_document = bool(message.get("document")) and not callback_query

    # Allowlist: config admins/allowed + DB-approved users.
    # Unknown users trigger an access request to admins (Approve / Deny).
    if chat_id is not None and user_id is not None:
        access_action = parse_access_callback(callback_data)
        if access_action is not None:
            # Admins handle approve/deny even before general allow checks.
            callback_id = str(callback_query.get("id") or "")
            if callback_id:
                try:
                    await bot.answer_callback_query(callback_query_id=callback_id)
                except Exception:
                    pass
            if not _is_admin(user_id):
                return await unauthorized_response(bot=bot, chat_id=chat_id, user_id=user_id)
            action_summary = await _handle_access_decision(
                bot=bot,
                admin_user_id=str(user_id),
                action=access_action[0],
                target_user_id=access_action[1],
            )
            return Response.success(
                body={
                    "ok": True,
                    "message": "Access decision processed",
                    "from_user_id": user_id,
                    "action": action_summary,
                },
                message="Access decision processed",
                status_code=200,
            )

        if not await _user_may_access(user_id):
            return await _handle_access_request(
                bot=bot,
                chat_id=chat_id,
                user_id=user_id,
                from_user=from_user,
            )

    # Photo/document ingest is admin-only.
    if message_has_image(message) and chat_id is not None and user_id is not None:
        if not _is_admin(user_id):
            return await unauthorized_response(bot=bot, chat_id=chat_id, user_id=user_id)

    telegram_reply_sent = False
    telegram_reply_error: Optional[str] = None
    action_summary: Optional[dict[str, Any]] = None

    if chat_id is not None and config.TELEGRAM_BOT_TOKEN:
        try:
            action_summary = await _dispatch_update(
                bot=bot,
                chat_id=chat_id,
                user_id=user_id,
                message=message if not callback_query else {},
                text=text if not callback_query else "",
                callback_query=callback_query or None,
            )
            telegram_reply_sent = True
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
        "callback_data": callback_data or None,
        "has_photo": has_photo,
        "has_document": has_document,
        "telegram_reply_sent": telegram_reply_sent,
        "telegram_reply_error": telegram_reply_error,
        "action": action_summary,
    }
    return Response.success(
        body=body,
        message="Telegram update acknowledged.",
        status_code=200,
    )


def _is_admin(user_id: Any) -> bool:
    return str(user_id) in config.ADMIN_USER_ID


def _is_env_allowed(user_id: Any) -> bool:
    uid = str(user_id)
    return uid in config.ADMIN_USER_ID or uid in config.ALLOWED_USER_ID


async def _user_may_access(user_id: Any) -> bool:
    if _is_env_allowed(user_id):
        return True
    async with AsyncSessionLocal() as db:
        return await TelegramAccessService().is_db_approved(
            session=db, telegram_user_id=str(user_id)
        )


async def _handle_access_request(
    *,
    bot: TelegramBotService,
    chat_id: int | str,
    user_id: Any,
    from_user: dict[str, Any],
) -> Response:
    async with AsyncSessionLocal() as db:
        summary = await TelegramAccessService().request_access(
            session=db,
            bot=bot,
            telegram_user_id=str(user_id),
            chat_id=chat_id,
            from_user=from_user,
        )
    return Response.success(
        body={"ok": True, "message": "Access request handled", "action": summary},
        message="Access request handled",
        status_code=200,
    )


async def _handle_access_decision(
    *,
    bot: TelegramBotService,
    admin_user_id: str,
    action: str,
    target_user_id: str,
) -> dict[str, Any]:
    async with AsyncSessionLocal() as db:
        summary = await TelegramAccessService().handle_admin_decision(
            session=db,
            bot=bot,
            admin_user_id=admin_user_id,
            action=action,
            target_user_id=target_user_id,
        )

    if summary.get("ok"):
        label = summary.get("display_name") or target_user_id
        if action == "approve":
            note = f"Approved access for {label} ({target_user_id})."
        else:
            note = f"Denied access for {label} ({target_user_id})."
        try:
            await bot.send_message(chat_id=admin_user_id, text=note, parse_mode=None)
        except Exception:
            pass
    return summary


async def _dispatch_update(
    *,
    bot: TelegramBotService,
    chat_id: int | str,
    user_id: Any,
    message: dict[str, Any],
    text: str,
    callback_query: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    session = telegram_sessions.get(chat_id)

    if callback_query:
        callback_id = str(callback_query.get("id") or "")
        data = str(callback_query.get("data") or "").strip().lower()
        if callback_id:
            await bot.answer_callback_query(callback_query_id=callback_id)

        query_intent = parse_query_callback(data)
        if query_intent is not None:
            return await _handle_calendar_query(
                bot=bot,
                chat_id=chat_id,
                session=session,
                intent=query_intent,
            )

        if data in REJECT_KEYWORDS:
            session.clear_pending_events()
            await bot.send_message(
                chat_id=chat_id,
                text="Data upload is rejected.",
                parse_mode=None,
                reply_markup=query_actions_keyboard() if session.class_label else None,
            )
            return {"ok": True, "action": "rejected"}

        if data in UPLOAD_KEYWORDS:
            if not _is_admin(user_id):
                await bot.send_message(
                    chat_id=chat_id,
                    text="Unauthorized user. Only admin users can upload planner photos.",
                    parse_mode=None,
                    reply_markup=query_actions_keyboard() if session.class_label else None,
                )
                return {"ok": False, "action": "unauthorized_upload", "user_id": user_id}
            return await _handle_upload(bot=bot, chat_id=chat_id, session=session)

        await bot.send_message(
            chat_id=chat_id,
            text="Unknown action. Use the buttons below.",
            parse_mode=None,
            reply_markup=upload_reject_keyboard()
            if session.state == TelegramSessionState.AWAITING_CONFIRM
            else (query_actions_keyboard() if session.class_label else None),
        )
        return {"ok": True, "action": "unknown_callback"}

    normalized = text.lower().strip()

    if message_has_image(message):
        if not _is_admin(user_id):
            await bot.send_message(
                chat_id=chat_id,
                text="Unauthorized user. Only admin users can upload planner photos.",
                parse_mode=None,
                reply_markup=query_actions_keyboard() if session.class_label else None,
            )
            return {"ok": False, "action": "unauthorized_upload", "user_id": user_id}
        return await _handle_image_extract(bot=bot, chat_id=chat_id, message=message, session=session)

    if not text:
        await bot.send_message(
            chat_id=chat_id,
            text=_help_text(session),
            parse_mode=None,
            reply_markup=query_actions_keyboard() if session.class_label else None,
        )
        return {"ok": True, "action": "help"}

    if normalized in HELP_KEYWORDS:
        await bot.send_message(
            chat_id=chat_id,
            text=_help_text(session),
            parse_mode=None,
            reply_markup=query_actions_keyboard() if session.class_label else None,
        )
        return {"ok": True, "action": "help"}

    if session.state == TelegramSessionState.AWAITING_CONFIRM:
        # Keep text commands as a fallback; buttons are preferred.
        if normalized in REJECT_KEYWORDS:
            session.clear_pending_events()
            await bot.send_message(
                chat_id=chat_id,
                text="Data upload is rejected.",
                parse_mode=None,
                reply_markup=query_actions_keyboard() if session.class_label else None,
            )
            return {"ok": True, "action": "rejected"}

        if normalized in UPLOAD_KEYWORDS:
            if not _is_admin(user_id):
                await bot.send_message(
                    chat_id=chat_id,
                    text="Unauthorized user. Only admin users can upload planner photos.",
                    parse_mode=None,
                    reply_markup=query_actions_keyboard() if session.class_label else None,
                )
                return {"ok": False, "action": "unauthorized_upload", "user_id": user_id}
            return await _handle_upload(bot=bot, chat_id=chat_id, session=session)

        await bot.send_message(
            chat_id=chat_id,
            text="Pending extract found. Tap Upload or Reject.",
            parse_mode=None,
            reply_markup=upload_reject_keyboard(),
        )
        return {"ok": True, "action": "awaiting_confirm"}

    query_intent = parse_query_text(text)
    if query_intent is not None:
        return await _handle_calendar_query(
            bot=bot,
            chat_id=chat_id,
            session=session,
            intent=query_intent,
        )

    # Any other text is treated as class name (asked first).
    try:
        class_name, section_name, label = parse_class_label(text)
    except ValueError as exc:
        await bot.send_message(chat_id=chat_id, text=str(exc), parse_mode=None)
        return {"ok": False, "action": "invalid_class"}

    session.class_name = class_name
    session.section_name = section_name
    session.class_label = label
    session.clear_pending_events()
    session.state = TelegramSessionState.AWAITING_PHOTO
    await bot.send_message(
        chat_id=chat_id,
        text=(
            f"Class set to {label}.\n\n"
            "What would you like to check?"
        ),
        parse_mode=None,
        reply_markup=query_actions_keyboard(),
    )
    return {"ok": True, "action": "class_set", "class_label": label}


async def _handle_calendar_query(
    *,
    bot: TelegramBotService,
    chat_id: int | str,
    session,
    intent: CalendarQueryIntent,
) -> dict[str, Any]:
    if not session.class_name or not session.section_name:
        await bot.send_message(
            chat_id=chat_id,
            text="Please send the class name first (e.g. 5-A), then tap a question.",
            parse_mode=None,
        )
        return {"ok": False, "action": "query_need_class", "intent": intent.value}

    async with AsyncSessionLocal() as db:
        answer = await CalendarQueryService().answer(
            session=db,
            intent=intent,
            class_name=session.class_name,
            section_name=session.section_name,
            class_label=session.class_label,
        )

    await bot.send_message(
        chat_id=chat_id,
        text=answer,
        parse_mode=None,
        reply_markup=query_actions_keyboard(),
    )
    return {"ok": True, "action": "calendar_query", "intent": intent.value}


async def _handle_image_extract(
    *,
    bot: TelegramBotService,
    chat_id: int | str,
    message: dict[str, Any],
    session,
) -> dict[str, Any]:
    if not session.class_name or not session.section_name:
        await bot.send_message(
            chat_id=chat_id,
            text=(
                "Please send the class name first (e.g. 5-A), "
                "then send the planner photo."
            ),
            parse_mode=None,
        )
        return {"ok": False, "action": "need_class", "event_count": 0}

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
            reply_markup=query_actions_keyboard(),
        )
        return {"ok": False, "action": "extract_failed", "error": detail, "event_count": 0}

    events = result.get("events") or []
    # Continue multi-day leave numbering from holidays already saved for this class
    # (e.g. WINTER BREAK spanning Dec photo + Jan photo).
    async with AsyncSessionLocal() as db:
        events = await TelegramIngestService().continue_leave_day_numbers(
            session=db,
            class_name=session.class_name,
            section_name=session.section_name,
            events=events,
        )

    table = format_events_table(
        events=events,
        planner_title=result.get("planner_title"),
    )
    await bot.send_message(chat_id=chat_id, text=table, parse_mode="HTML")

    if not events:
        session.clear_pending_events()
        await bot.send_message(
            chat_id=chat_id,
            text="Nothing to upload. Send another photo, or ask about the calendar.",
            parse_mode=None,
            reply_markup=query_actions_keyboard(),
        )
        return {
            "ok": True,
            "action": "extract_empty",
            "event_count": 0,
            "planner_title": result.get("planner_title"),
        }

    session.planner_title = result.get("planner_title")
    session.events = events
    session.state = TelegramSessionState.AWAITING_CONFIRM
    await bot.send_message(
        chat_id=chat_id,
        text=f"Class: {session.class_label}\nChoose an action:",
        parse_mode=None,
        reply_markup=upload_reject_keyboard(),
    )
    return {
        "ok": True,
        "action": "extract_ready",
        "event_count": len(events),
        "planner_title": result.get("planner_title"),
        "class_label": session.class_label,
    }


async def _handle_upload(
    *,
    bot: TelegramBotService,
    chat_id: int | str,
    session,
) -> dict[str, Any]:
    if not session.events or not session.class_name or not session.section_name:
        session.clear_pending_events()
        await bot.send_message(
            chat_id=chat_id,
            text="No pending data to upload. Send a class name, then a planner photo.",
            parse_mode=None,
            reply_markup=query_actions_keyboard() if session.class_label else None,
        )
        return {"ok": False, "action": "nothing_to_upload"}

    await bot.send_message(chat_id=chat_id, text="Uploading data…")

    async with AsyncSessionLocal() as db:
        try:
            summary = await TelegramIngestService().save_events(
                session=db,
                class_name=session.class_name,
                section_name=session.section_name,
                events=session.events,
            )
        except Exception as exc:  # noqa: BLE001
            await bot.send_message(
                chat_id=chat_id,
                text=f"Upload failed.\n{exc}",
                parse_mode=None,
                reply_markup=query_actions_keyboard(),
            )
            return {"ok": False, "action": "upload_failed", "error": str(exc)}

    created = summary["created"]
    skipped = summary["skipped"]
    renamed = summary.get("renamed") or 0
    skipped_existing = summary.get("skipped_existing") or []
    errors = summary.get("errors") or []
    types_used = ", ".join(summary["holiday_types_used"]) or "none"
    class_label = session.class_label
    session.clear_pending_events()

    lines = [
        "Data uploaded successfully.",
        f"Class: {class_label}",
        f"Created: {created}",
        f"Skipped: {skipped}",
        f"Holiday types: {types_used}",
    ]
    if renamed:
        lines.append(f"Renumbered existing leave days: {renamed}")
    if skipped_existing:
        lines.append("Skipped because they already exist:")
        lines.extend(f"- {name}" for name in skipped_existing[:20])
        if len(skipped_existing) > 20:
            lines.append(f"- …and {len(skipped_existing) - 20} more")
    if errors:
        lines.append("Other skip reasons:")
        lines.extend(f"- {err}" for err in errors[:10])

    await bot.send_message(
        chat_id=chat_id,
        text="\n".join(lines),
        parse_mode=None,
        reply_markup=query_actions_keyboard(),
    )
    return {"ok": True, "action": "uploaded", **summary}


def _help_text(session) -> str:
    class_line = (
        f"Current class: {session.class_label}\n"
        if session.class_label
        else "No class set yet.\n"
    )
    return (
        "School Calendar bot\n"
        f"{class_line}"
        "1) Send class name first (e.g. 5-A)\n"
        "2) Tap a question button (Upcoming / Next PTM / …)\n"
        "3) Admins can also send a planner photo to Upload"
    )


async def unauthorized_response(bot: TelegramBotService, chat_id: int | str, user_id: int | str) -> Response:
    try:
        await bot.send_message(
            chat_id=chat_id,
            text="Unauthorized. Only admin users can upload planner photos.",
            parse_mode=None,
        )
        telegram_reply_sent = True
    except Exception as send_exc:  # noqa: BLE001
        telegram_reply_error = str(send_exc)
        telegram_reply_sent = False
        return Response.success(
            body={
                "ok": True,
                "message": "Unauthorized user",
                "user_id": user_id,
                "telegram_reply_sent": telegram_reply_sent,
                "telegram_reply_error": telegram_reply_error,
            },
            message="Unauthorized user",
            status_code=200,
        )

    return Response.success(
        body={
            "ok": True,
            "message": "Unauthorized user",
            "user_id": user_id,
            "telegram_reply_sent": telegram_reply_sent,
        },
        message="Unauthorized user",
        status_code=200,
    )
