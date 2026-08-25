"""Tests for Telegram access request callbacks."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "packages" / "server" / "app"))

from services.telegram_access import access_request_keyboard, parse_access_callback


def test_parse_access_callback():
    assert parse_access_callback("access:approve:8057453587") == ("approve", "8057453587")
    assert parse_access_callback("access:deny:123") == ("deny", "123")
    assert parse_access_callback("query:upcoming") is None
    assert parse_access_callback("access:maybe:1") is None


def test_access_request_keyboard():
    keyboard = access_request_keyboard("8057453587")
    flat = [btn["callback_data"] for row in keyboard["inline_keyboard"] for btn in row]
    assert flat == ["access:approve:8057453587", "access:deny:8057453587"]
