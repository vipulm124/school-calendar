"""CRUD for Telegram bot access allowlist."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import TelegramAccessUser


class TelegramAccessCrud:
    def __init__(self) -> None:
        self.model = TelegramAccessUser

    async def get_by_telegram_user_id(
        self, *, session: AsyncSession, telegram_user_id: str
    ) -> Optional[TelegramAccessUser]:
        query = select(self.model).where(
            self.model.telegram_user_id == str(telegram_user_id),
            self.model.is_deleted.is_(False),
        )
        result = await session.execute(query)
        return result.scalars().first()

    async def upsert_pending_request(
        self,
        *,
        session: AsyncSession,
        telegram_user_id: str,
        chat_id: str,
        display_name: Optional[str],
        username: Optional[str],
    ) -> tuple[TelegramAccessUser, bool]:
        """
        Create or refresh a pending access request.

        Returns (row, should_notify_admins).
        """
        existing = await self.get_by_telegram_user_id(
            session=session, telegram_user_id=telegram_user_id
        )
        if existing is None:
            row = TelegramAccessUser(
                telegram_user_id=str(telegram_user_id),
                status="pending",
                display_name=display_name,
                username=username,
                chat_id=str(chat_id),
                created_by="telegram",
                updated_by="telegram",
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row, True

        existing.chat_id = str(chat_id)
        if display_name:
            existing.display_name = display_name
        if username:
            existing.username = username
        existing.updated_by = "telegram"

        if existing.status == "approved":
            await session.commit()
            await session.refresh(existing)
            return existing, False

        should_notify = existing.status != "pending"
        existing.status = "pending"
        await session.commit()
        await session.refresh(existing)
        return existing, should_notify

    async def set_status(
        self,
        *,
        session: AsyncSession,
        telegram_user_id: str,
        status: str,
        updated_by: str,
    ) -> Optional[TelegramAccessUser]:
        row = await self.get_by_telegram_user_id(
            session=session, telegram_user_id=telegram_user_id
        )
        if row is None:
            return None
        row.status = status
        row.updated_by = updated_by
        await session.commit()
        await session.refresh(row)
        return row
