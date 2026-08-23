"""Tests for calendar query helpers and Telegram query buttons."""

import sys
from datetime import date
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1] / "packages" / "server" / "app"))

from api.v1.telegram.router import telegram_router
from services.calendar_query import (
    CalendarEventView,
    CalendarQueryIntent,
    parse_query_callback,
    parse_query_text,
    _collapse_multi_day,
    _format_list,
    _format_single,
)
from services.telegram_bot import query_actions_keyboard
from services.telegram_session import telegram_sessions


def test_query_actions_keyboard_shape():
    keyboard = query_actions_keyboard()
    flat = [btn["callback_data"] for row in keyboard["inline_keyboard"] for btn in row]
    assert flat == [
        "query:upcoming",
        "query:this_month",
        "query:next_ptm",
        "query:last_ptm",
    ]


def test_parse_query_callback_and_text():
    assert parse_query_callback("query:next_ptm") == CalendarQueryIntent.NEXT_PTM
    assert parse_query_text("Next PTM") == CalendarQueryIntent.NEXT_PTM
    assert parse_query_text("upcoming holidays") == CalendarQueryIntent.UPCOMING
    assert parse_query_text("5-A") is None


def test_collapse_multi_day_and_format():
    events = [
        CalendarEventView("WINTER BREAK - DAY 1", date(2026, 12, 28), "HOLIDAYS"),
        CalendarEventView("WINTER BREAK - DAY 2", date(2026, 12, 29), "HOLIDAYS"),
        CalendarEventView("HOLI", date(2027, 3, 4), "HOLIDAYS"),
    ]
    collapsed = _collapse_multi_day(events)
    assert collapsed[0].name == "WINTER BREAK"
    assert collapsed[0].event_date == date(2026, 12, 28)
    assert collapsed[0].end_date == date(2026, 12, 29)
    assert collapsed[1].name == "HOLI"

    text = _format_list(
        title="Upcoming holidays for 5-A",
        events=collapsed,
        empty="none",
        today=date(2026, 12, 20),
    )
    assert "WINTER BREAK —" in text
    assert "HOLI" in text

    single = _format_single(
        title="Next PTM for 5-A",
        event=CalendarEventView("OPEN HOUSE", date(2027, 2, 15), "PTC"),
        today=date(2027, 2, 1),
    )
    assert "OPEN HOUSE" in single
    assert "in 14 days" in single


def test_class_set_shows_query_buttons(monkeypatch):
    telegram_sessions.clear(55)

    class FakeBot:
        def __init__(self):
            self.sent = []
            self.markups = []

        async def send_message(self, *, chat_id, text, parse_mode="HTML", reply_markup=None):  # noqa: ARG002
            self.sent.append(text)
            self.markups.append(reply_markup)
            return True

        async def answer_callback_query(self, *, callback_query_id, text=None):  # noqa: ARG002
            return True

    fake_bot = FakeBot()
    app = FastAPI()
    app.include_router(telegram_router)
    monkeypatch.setattr("api.v1.telegram.router.config.TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setattr("api.v1.telegram.router.TelegramBotService", lambda: fake_bot)
    client = TestClient(app)

    response = client.post(
        "/telegram/webhook",
        json={
            "update_id": 10,
            "message": {"chat": {"id": 55}, "from": {"id": 1}, "text": "5-A"},
        },
    )
    assert response.status_code == 200
    assert response.json()["details"]["action"]["action"] == "class_set"
    assert fake_bot.markups[-1]["inline_keyboard"][0][0]["callback_data"] == "query:upcoming"


def test_query_button_callback_answers(monkeypatch):
    telegram_sessions.clear(56)
    session = telegram_sessions.get(56)
    session.class_name = "5"
    session.section_name = "A"
    session.class_label = "5-A"

    class FakeBot:
        def __init__(self):
            self.sent = []
            self.markups = []
            self.answered = []

        async def send_message(self, *, chat_id, text, parse_mode="HTML", reply_markup=None):  # noqa: ARG002
            self.sent.append(text)
            self.markups.append(reply_markup)
            return True

        async def answer_callback_query(self, *, callback_query_id, text=None):  # noqa: ARG002
            self.answered.append(callback_query_id)
            return True

    class FakeQueryService:
        async def answer(self, **kwargs):  # noqa: ARG002
            return "Next PTM for 5-A:\nOPEN HOUSE — Mon, 15 Feb 2027 (in 12 days)"

    class FakeAsyncSession:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, *args):  # noqa: ARG002
            return False

    fake_bot = FakeBot()
    app = FastAPI()
    app.include_router(telegram_router)
    monkeypatch.setattr("api.v1.telegram.router.config.TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setattr("api.v1.telegram.router.TelegramBotService", lambda: fake_bot)
    monkeypatch.setattr("api.v1.telegram.router.CalendarQueryService", lambda: FakeQueryService())
    monkeypatch.setattr("api.v1.telegram.router.AsyncSessionLocal", lambda: FakeAsyncSession())
    client = TestClient(app)

    response = client.post(
        "/telegram/webhook",
        json={
            "update_id": 11,
            "callback_query": {
                "id": "cb-1",
                "data": "query:next_ptm",
                "from": {"id": 1},
                "message": {"chat": {"id": 56}},
            },
        },
    )
    assert response.status_code == 200
    body = response.json()["details"]["action"]
    assert body["action"] == "calendar_query"
    assert body["intent"] == "next_ptm"
    assert "OPEN HOUSE" in fake_bot.sent[-1]
    assert fake_bot.markups[-1]["inline_keyboard"][1][0]["callback_data"] == "query:next_ptm"
