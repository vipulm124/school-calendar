"""Tests for Telegram table formatting and photo webhook extract flow."""

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
)


def test_format_events_table_with_rows():
    text = format_events_table(
        planner_title="PLANNER 2026-2027",
        events=[
            {
                "event_date": "2026-03-04",
                "holiday_type": "Holidays",
                "event_name": "HOLI",
            },
            {
                "event_date": "2026-03-27",
                "holiday_type": "PTC",
                "event_name": "NEW SESSION COMMENCES",
            },
        ],
    )
    assert "PLANNER 2026-2027" in text
    assert "Found 2 events." in text
    assert "<pre>" in text
    assert "HOLI" in text
    assert "PTC" in text
    assert "Date" in text


def test_format_events_table_empty():
    text = format_events_table(events=[], planner_title=None)
    assert "Found 0 events." in text
    assert "No Holidays/PTC found" in text


def test_message_has_image_detects_photo_and_document():
    assert message_has_image({"photo": [{"file_id": "x"}]}) is True
    assert message_has_image({"document": {"mime_type": "image/png", "file_id": "y"}}) is True
    assert message_has_image({"document": {"file_name": "scan.HEIC", "file_id": "z"}}) is True
    assert message_has_image({"text": "hello"}) is False


def test_webhook_photo_extract_returns_table(monkeypatch):
    app = FastAPI()
    app.include_router(telegram_router)

    class FakeBot:
        def __init__(self, *args, **kwargs):  # noqa: ARG002
            self.sent: list[tuple] = []

        async def send_message(self, *, chat_id, text, parse_mode="HTML"):  # noqa: ARG002
            self.sent.append((chat_id, text, parse_mode))
            return True

        async def download_image_from_message(self, message):  # noqa: ARG002
            return TelegramImage(
                content=b"fake-bytes",
                filename="planner.jpg",
                content_type="image/jpeg",
                file_id="file-1",
            )

    fake_bot = FakeBot()

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

    monkeypatch.setattr("api.v1.telegram.router.config.TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setattr("api.v1.telegram.router.TelegramBotService", lambda: fake_bot)
    monkeypatch.setattr("api.v1.telegram.router.PlannerController", FakeController)

    client = TestClient(app)
    response = client.post(
        "/telegram/webhook",
        json={
            "update_id": 1,
            "message": {
                "message_id": 10,
                "chat": {"id": 42},
                "from": {"id": 99},
                "photo": [
                    {"file_id": "small", "width": 90, "height": 90},
                    {"file_id": "large", "width": 800, "height": 1200},
                ],
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["details"]["extract"]["ok"] is True
    assert payload["details"]["extract"]["event_count"] == 1
    assert len(fake_bot.sent) == 2
    assert "Processing image" in fake_bot.sent[0][1]
    assert "HOLI" in fake_bot.sent[1][1]
    assert "<pre>" in fake_bot.sent[1][1]


def test_webhook_text_sends_help(monkeypatch):
    app = FastAPI()
    app.include_router(telegram_router)

    class FakeBot:
        def __init__(self):
            self.sent = []

        async def send_message(self, *, chat_id, text, parse_mode="HTML"):  # noqa: ARG002
            self.sent.append(text)
            return True

    fake_bot = FakeBot()
    monkeypatch.setattr("api.v1.telegram.router.config.TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setattr("api.v1.telegram.router.TelegramBotService", lambda: fake_bot)

    client = TestClient(app)
    response = client.post(
        "/telegram/webhook",
        json={
            "update_id": 2,
            "message": {
                "chat": {"id": 7},
                "from": {"id": 1},
                "text": "hello",
            },
        },
    )
    assert response.status_code == 200
    assert "Send a planner photo" in fake_bot.sent[0]
