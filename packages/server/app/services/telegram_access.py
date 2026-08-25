"""Approve / deny Telegram bot access requests."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from core.config import config
from crud.telegram_access import TelegramAccessCrud
from services.telegram_bot import TelegramBotService


def access_request_keyboard(telegram_user_id: str) -> dict[str, Any]:
    uid = str(telegram_user_id)
    return {
        "inline_keyboard": [
            [
                {
                    "text": "✅  Approve",
                    "callback_data": f"access:approve:{uid}",
                    "style": "success",
                },
                {
                    "text": "❌  Deny",
                    "callback_data": f"access:deny:{uid}",
                    "style": "danger",
                },
            ]
        ]
    }


def parse_access_callback(data: str) -> Optional[tuple[str, str]]:
    """Return (action, telegram_user_id) for access:approve|deny:<id>."""
    raw = (data or "").strip().lower()
    parts = raw.split(":")
    if len(parts) != 3 or parts[0] != "access":
        return None
    action, target_id = parts[1], parts[2]
    if action not in {"approve", "deny"} or not target_id:
        return None
    return action, target_id


class TelegramAccessService:
    def __init__(self) -> None:
        self.crud = TelegramAccessCrud()

    async def is_db_approved(self, *, session: AsyncSession, telegram_user_id: str) -> bool:
        row = await self.crud.get_by_telegram_user_id(
            session=session, telegram_user_id=str(telegram_user_id)
        )
        return bool(row and row.status == "approved")

    async def request_access(
        self,
        *,
        session: AsyncSession,
        bot: TelegramBotService,
        telegram_user_id: str,
        chat_id: int | str,
        from_user: dict[str, Any],
    ) -> dict[str, Any]:
        display_name = _display_name(from_user)
        username = from_user.get("username")
        username_str = f"@{username}" if username else None

        row, should_notify = await self.crud.upsert_pending_request(
            session=session,
            telegram_user_id=str(telegram_user_id),
            chat_id=str(chat_id),
            display_name=display_name,
            username=username_str,
        )

        if row.status == "approved":
            await bot.send_message(
                chat_id=chat_id,
                text="You already have access. Send a class name (e.g. 5-A) to begin.",
                parse_mode=None,
            )
            return {"ok": True, "action": "already_approved", "user_id": str(telegram_user_id)}

        if should_notify:
            await bot.send_message(
                chat_id=chat_id,
                text=(
                    "Access request sent to the admin.\n"
                    f"Your Telegram user_id: {telegram_user_id}\n"
                    "You will be notified when it is approved."
                ),
                parse_mode=None,
            )
            notified = await self._notify_admins(
                bot=bot,
                telegram_user_id=str(telegram_user_id),
                display_name=display_name,
                username=username_str,
            )
            return {
                "ok": True,
                "action": "access_requested",
                "user_id": str(telegram_user_id),
                "notified_admins": notified,
                "already_pending": False,
            }

        await bot.send_message(
            chat_id=chat_id,
            text=(
                "Your access request is already pending admin approval.\n"
                f"Your Telegram user_id: {telegram_user_id}"
            ),
            parse_mode=None,
        )
        return {
            "ok": True,
            "action": "access_pending",
            "user_id": str(telegram_user_id),
            "notified_admins": 0,
            "already_pending": True,
        }

    async def handle_admin_decision(
        self,
        *,
        session: AsyncSession,
        bot: TelegramBotService,
        admin_user_id: str,
        action: str,
        target_user_id: str,
    ) -> dict[str, Any]:
        status = "approved" if action == "approve" else "denied"
        row = await self.crud.set_status(
            session=session,
            telegram_user_id=target_user_id,
            status=status,
            updated_by=f"admin:{admin_user_id}",
        )
        if row is None:
            return {"ok": False, "action": "access_user_missing", "user_id": target_user_id}

        # Notify the requester if we know their chat.
        if row.chat_id:
            if status == "approved":
                text = (
                    "Your access was approved.\n"
                    "Send your class name (e.g. 5-A), then use the question buttons."
                )
            else:
                text = "Your access request was denied by the admin."
            try:
                await bot.send_message(chat_id=row.chat_id, text=text, parse_mode=None)
            except Exception:
                pass

        return {
            "ok": True,
            "action": f"access_{status}",
            "user_id": target_user_id,
            "display_name": row.display_name,
        }

    async def _notify_admins(
        self,
        *,
        bot: TelegramBotService,
        telegram_user_id: str,
        display_name: Optional[str],
        username: Optional[str],
    ) -> int:
        lines = [
            "New bot access request",
            f"Name: {display_name or '(unknown)'}",
            f"Username: {username or '(none)'}",
            f"User id: {telegram_user_id}",
            "",
            "Approve to let them use calendar queries.",
        ]
        text = "\n".join(lines)
        keyboard = access_request_keyboard(telegram_user_id)
        notified = 0
        for admin_id in config.ADMIN_USER_ID:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=text,
                    parse_mode=None,
                    reply_markup=keyboard,
                )
                notified += 1
            except Exception:
                # Admin must have started the bot at least once for DMs to work.
                continue
        return notified


def _display_name(from_user: dict[str, Any]) -> str:
    first = str(from_user.get("first_name") or "").strip()
    last = str(from_user.get("last_name") or "").strip()
    full = f"{first} {last}".strip()
    return full or str(from_user.get("username") or from_user.get("id") or "Unknown")
