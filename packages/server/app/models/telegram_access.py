"""Telegram bot access allowlist / pending requests."""

from sqlalchemy import VARCHAR
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class TelegramAccessUser(Base):
    """
    Tracks who may use the Telegram bot.

    status:
      - pending: requested access, waiting for admin
      - approved: may use the bot (queries)
      - denied: rejected by admin
    """

    __tablename__ = "telegram_access_user"
    __table_args__ = {"schema": "calendar"}

    telegram_user_id: Mapped[str] = mapped_column(VARCHAR(32), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, default="pending")
    display_name: Mapped[str] = mapped_column(VARCHAR(255), nullable=True)
    username: Mapped[str] = mapped_column(VARCHAR(255), nullable=True)
    chat_id: Mapped[str] = mapped_column(VARCHAR(32), nullable=True)
