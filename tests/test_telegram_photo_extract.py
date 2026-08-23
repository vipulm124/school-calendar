"""Tests for Telegram extract + upload/reject flow."""

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1] / "packages" / "server" / "app"))

from api.v1.telegram.router import telegram_router
from services.telegram_bot import (
    TelegramImage,
    format_events_table,
    message_has_image,
    upload_reject_keyboard,
)
from services.telegram_ingest import parse_class_label
from services.telegram_session import TelegramSessionState, telegram_sessions


def _client(monkeypatch, fake_bot, fake_controller=None, fake_ingest=None):
    app = FastAPI()
    app.include_router(telegram_router)
    monkeypatch.setattr("api.v1.telegram.router.config.TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setattr("api.v1.telegram.router.TelegramBotService", lambda: fake_bot)
    if fake_controller is not None:
        monkeypatch.setattr("api.v1.telegram.router.PlannerController", fake_controller)
    if fake_ingest is not None:
        monkeypatch.setattr("api.v1.telegram.router.TelegramIngestService", fake_ingest)
    return TestClient(app)


class FakeBot:
    def __init__(self, *args, **kwargs):  # noqa: ARG002
        self.sent: list[str] = []
        self.markups: list[dict | None] = []
        self.answered_callbacks: list[str] = []

    async def send_message(self, *, chat_id, text, parse_mode="HTML", reply_markup=None):  # noqa: ARG002
        self.sent.append(text)
        self.markups.append(reply_markup)
        return True

    async def answer_callback_query(self, *, callback_query_id, text=None):  # noqa: ARG002
        self.answered_callbacks.append(callback_query_id)
        return True

    async def download_image_from_message(self, message):  # noqa: ARG002
        return TelegramImage(
            content=b"fake-bytes",
            filename="planner.jpg",
            content_type="image/jpeg",
            file_id="file-1",
        )


class FakeController:
    async def extract_from_bytes(self, *, image_bytes, content_type, filename):  # noqa: ARG002
        return {
            "planner_title": "PLANNER 2026-2027",
            "event_count": 1,
            "preview": ["1. 2026-03-04 — HOLI [Holiday]"],
            "events": [
                {
                    "event_date": "2026-03-04",
                    "holiday_type": "Holidays",
                    "event_name": "HOLI",
                    "category": "Holidays",
                }
            ],
        }


class FakeIngestPassthrough:
    async def continue_leave_day_numbers(self, *, session, class_name, section_name, events):  # noqa: ARG002
        return events

    async def save_events(self, *, session, class_name, section_name, events, unique_identifier="telegram"):  # noqa: ARG002
        return {
            "student_class_id": "abc",
            "created": len(events),
            "skipped": 0,
            "skipped_existing": [],
            "errors": [],
            "holiday_types_used": ["Holidays"],
        }


class FakeAsyncSession:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, *args):  # noqa: ANN002
        return False


def test_parse_class_label():
    assert parse_class_label("5-A") == ("5", "A", "5-A")
    assert parse_class_label("FS1") == ("FS1", "-", "FS1")


def test_upload_reject_keyboard_shape():
    keyboard = upload_reject_keyboard()
    assert keyboard["inline_keyboard"][0][0]["callback_data"] == "upload"
    assert keyboard["inline_keyboard"][0][1]["callback_data"] == "reject"


def test_format_events_table_with_rows():
    text = format_events_table(
        planner_title="PLANNER 2026-2027",
        events=[
            {"event_date": "2026-03-04", "holiday_type": "Holidays", "event_name": "HOLI"},
        ],
    )
    assert "Found 1 event." in text
    assert "HOLI" in text


def test_message_has_image_detects_photo_and_document():
    assert message_has_image({"photo": [{"file_id": "x"}]}) is True
    assert message_has_image({"text": "hello"}) is False


def test_photo_without_class_asks_for_class(monkeypatch):
    telegram_sessions.clear(42)
    fake_bot = FakeBot()
    client = _client(monkeypatch, fake_bot, FakeController)

    response = client.post(
        "/telegram/webhook",
        json={
            "update_id": 1,
            "message": {
                "chat": {"id": 42},
                "from": {"id": 99},
                "photo": [{"file_id": "large", "width": 800, "height": 1200}],
            },
        },
    )
    assert response.status_code == 200
    assert response.json()["details"]["action"]["action"] == "need_class"
    assert "class name first" in fake_bot.sent[0].lower()


def test_class_then_photo_then_reject_button(monkeypatch):
    telegram_sessions.clear(42)
    fake_bot = FakeBot()
    monkeypatch.setattr("api.v1.telegram.router.AsyncSessionLocal", lambda: FakeAsyncSession())
    client = _client(monkeypatch, fake_bot, FakeController, lambda: FakeIngestPassthrough())

    client.post(
        "/telegram/webhook",
        json={"update_id": 1, "message": {"chat": {"id": 42}, "from": {"id": 1}, "text": "5-A"}},
    )
    photo_resp = client.post(
        "/telegram/webhook",
        json={
            "update_id": 2,
            "message": {
                "chat": {"id": 42},
                "from": {"id": 1},
                "photo": [{"file_id": "large", "width": 800, "height": 1200}],
            },
        },
    )
    assert photo_resp.json()["details"]["action"]["action"] == "extract_ready"
    assert any(m and "inline_keyboard" in m for m in fake_bot.markups)
    assert telegram_sessions.get(42).state == TelegramSessionState.AWAITING_CONFIRM

    reject_resp = client.post(
        "/telegram/webhook",
        json={
            "update_id": 3,
            "callback_query": {
                "id": "cb-1",
                "data": "reject",
                "from": {"id": 1},
                "message": {"chat": {"id": 42}, "message_id": 9},
            },
        },
    )
    assert reject_resp.json()["details"]["action"]["action"] == "rejected"
    assert "Data upload is rejected." in fake_bot.sent[-1]
    assert "cb-1" in fake_bot.answered_callbacks
    assert telegram_sessions.get(42).events == []


def test_class_then_photo_then_upload_button_with_skip_reason(monkeypatch):
    telegram_sessions.clear(77)
    fake_bot = FakeBot()

    class FakeIngest:
        async def continue_leave_day_numbers(self, *, session, class_name, section_name, events):  # noqa: ARG002
            return events

        async def save_events(self, *, session, class_name, section_name, events, unique_identifier="telegram"):  # noqa: ARG002
            return {
                "student_class_id": "abc",
                "created": 1,
                "skipped": 2,
                "skipped_existing": [
                    "WINTER BREAK - DAY 1 (2026-12-24)",
                    "WINTER BREAK - DAY 2 (2026-12-25)",
                ],
                "errors": [],
                "holiday_types_used": ["Holidays"],
            }

    monkeypatch.setattr("api.v1.telegram.router.AsyncSessionLocal", lambda: FakeAsyncSession())
    client = _client(monkeypatch, fake_bot, FakeController, lambda: FakeIngest())

    client.post(
        "/telegram/webhook",
        json={"update_id": 1, "message": {"chat": {"id": 77}, "from": {"id": 1}, "text": "5-A"}},
    )
    client.post(
        "/telegram/webhook",
        json={
            "update_id": 2,
            "message": {
                "chat": {"id": 77},
                "from": {"id": 1},
                "photo": [{"file_id": "large", "width": 800, "height": 1200}],
            },
        },
    )
    upload_resp = client.post(
        "/telegram/webhook",
        json={
            "update_id": 3,
            "callback_query": {
                "id": "cb-2",
                "data": "upload",
                "from": {"id": 1},
                "message": {"chat": {"id": 77}, "message_id": 11},
            },
        },
    )
    assert upload_resp.status_code == 200
    assert upload_resp.json()["details"]["action"]["action"] == "uploaded"
    assert upload_resp.json()["details"]["action"]["created"] == 1
    final = fake_bot.sent[-1]
    assert "Data uploaded successfully." in final
    assert "Skipped because they already exist:" in final
    assert "WINTER BREAK - DAY 1 (2026-12-24)" in final


def test_help_command(monkeypatch):
    telegram_sessions.clear(9)
    fake_bot = FakeBot()
    client = _client(monkeypatch, fake_bot)
    response = client.post(
        "/telegram/webhook",
        json={"update_id": 1, "message": {"chat": {"id": 9}, "from": {"id": 1}, "text": "/help"}},
    )
    assert response.json()["details"]["action"]["action"] == "help"
    assert "tap a question button" in fake_bot.sent[-1].lower()
    assert "Upload or Reject" in fake_bot.sent[-1]
