"""In-memory per-chat Telegram ingest session state."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Any, Optional


class TelegramSessionState(str, Enum):
    IDLE = "idle"
    AWAITING_PHOTO = "awaiting_photo"
    AWAITING_CONFIRM = "awaiting_confirm"


@dataclass
class TelegramChatSession:
    state: TelegramSessionState = TelegramSessionState.IDLE
    class_name: Optional[str] = None
    section_name: Optional[str] = None
    class_label: Optional[str] = None
    planner_title: Optional[str] = None
    events: list[dict[str, Any]] = field(default_factory=list)

    def clear_pending_events(self) -> None:
        self.planner_title = None
        self.events = []
        if self.class_name:
            self.state = TelegramSessionState.AWAITING_PHOTO
        else:
            self.state = TelegramSessionState.IDLE

    def reset(self) -> None:
        self.state = TelegramSessionState.IDLE
        self.class_name = None
        self.section_name = None
        self.class_label = None
        self.clear_pending_events()
        self.state = TelegramSessionState.IDLE


class TelegramSessionStore:
    """Process-local session store keyed by Telegram chat id."""

    def __init__(self) -> None:
        self._sessions: dict[str, TelegramChatSession] = {}
        self._lock = Lock()

    def get(self, chat_id: int | str) -> TelegramChatSession:
        key = str(chat_id)
        with self._lock:
            session = self._sessions.get(key)
            if session is None:
                session = TelegramChatSession()
                self._sessions[key] = session
            return session

    def clear(self, chat_id: int | str) -> None:
        key = str(chat_id)
        with self._lock:
            self._sessions.pop(key, None)


telegram_sessions = TelegramSessionStore()
