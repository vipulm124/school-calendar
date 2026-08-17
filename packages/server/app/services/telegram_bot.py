"""Telegram Bot API helpers for photo download and chat replies."""

from __future__ import annotations

import html
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import httpx

from core.config import config

TELEGRAM_API_BASE = "https://api.telegram.org"
MAX_MESSAGE_CHARS = 3500
IMAGE_DOCUMENT_MIME_PREFIXES = ("image/",)
IMAGE_DOCUMENT_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
    ".heic",
    ".heif",
    ".heics",
    ".heifs",
    ".bmp",
    ".tif",
    ".tiff",
}


class TelegramBotError(RuntimeError):
    """Raised when Telegram Bot API calls fail."""


@dataclass
class TelegramImage:
    """Downloaded image payload from a Telegram message."""

    content: bytes
    filename: str
    content_type: str
    file_id: str


class TelegramBotService:
    """Thin client around Telegram Bot API using TELEGRAM_BOT_TOKEN."""

    def __init__(self, *, bot_token: Optional[str] = None, timeout_seconds: float = 60.0) -> None:
        self.bot_token = bot_token if bot_token is not None else config.TELEGRAM_BOT_TOKEN
        self.timeout_seconds = timeout_seconds

    def _ensure_token(self) -> None:
        if not self.bot_token:
            raise TelegramBotError("TELEGRAM_BOT_TOKEN is not configured.")

    def _api_url(self, method: str) -> str:
        self._ensure_token()
        return f"{TELEGRAM_API_BASE}/bot{self.bot_token}/{method}"

    async def send_message(
        self,
        *,
        chat_id: int | str,
        text: str,
        parse_mode: Optional[str] = "HTML",
        reply_markup: Optional[dict[str, Any]] = None,
    ) -> bool:
        """Send one or more chat messages, chunking long text."""
        chunks = _chunk_text(text, MAX_MESSAGE_CHARS)
        if not chunks:
            return False

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            for index, chunk in enumerate(chunks):
                payload: dict[str, Any] = {"chat_id": chat_id, "text": chunk}
                if parse_mode:
                    payload["parse_mode"] = parse_mode
                # Attach buttons only on the final chunk.
                if reply_markup is not None and index == len(chunks) - 1:
                    payload["reply_markup"] = reply_markup
                response = await client.post(self._api_url("sendMessage"), json=payload)
                if response.status_code >= 400:
                    raise TelegramBotError(
                        f"sendMessage failed ({response.status_code}): {response.text}"
                    )
        return True

    async def answer_callback_query(
        self,
        *,
        callback_query_id: str,
        text: Optional[str] = None,
    ) -> bool:
        payload: dict[str, Any] = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(self._api_url("answerCallbackQuery"), json=payload)
        if response.status_code >= 400:
            raise TelegramBotError(
                f"answerCallbackQuery failed ({response.status_code}): {response.text}"
            )
        return True

    async def download_image_from_message(self, message: dict[str, Any]) -> TelegramImage:
        """Download the best photo or image document attached to a message."""
        file_id, filename, content_type = _resolve_image_file(message)
        file_path = await self._get_file_path(file_id)
        content = await self._download_file(file_path)
        if not content:
            raise TelegramBotError("Downloaded Telegram image is empty.")
        return TelegramImage(
            content=content,
            filename=filename,
            content_type=content_type,
            file_id=file_id,
        )

    async def _get_file_path(self, file_id: str) -> str:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(self._api_url("getFile"), params={"file_id": file_id})
        if response.status_code >= 400:
            raise TelegramBotError(f"getFile failed ({response.status_code}): {response.text}")
        payload = response.json()
        if not payload.get("ok"):
            raise TelegramBotError(f"getFile returned error: {payload}")
        file_path = (payload.get("result") or {}).get("file_path")
        if not file_path:
            raise TelegramBotError("getFile response missing file_path.")
        return str(file_path)

    async def _download_file(self, file_path: str) -> bytes:
        self._ensure_token()
        url = f"{TELEGRAM_API_BASE}/file/bot{self.bot_token}/{file_path}"
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(url)
        if response.status_code >= 400:
            raise TelegramBotError(
                f"file download failed ({response.status_code}): {response.text}"
            )
        return response.content


def upload_reject_keyboard() -> dict[str, Any]:
    """Inline keyboard for confirming planner extract upload."""
    return {
        "inline_keyboard": [
            [
                {"text": "👍 Upload", "callback_data": "upload"},
                {"text": "👎 Reject", "callback_data": "reject"},
            ]
        ]
    }


def message_has_image(message: dict[str, Any]) -> bool:
    """Return True when the message contains a photo or image document."""
    if message.get("photo"):
        return True
    document = message.get("document") or {}
    mime = str(document.get("mime_type") or "").lower()
    if mime.startswith(IMAGE_DOCUMENT_MIME_PREFIXES):
        return True
    name = str(document.get("file_name") or "").lower()
    return Path(name).suffix in IMAGE_DOCUMENT_EXTENSIONS


def format_events_table(
    *,
    events: list[dict[str, Any]],
    planner_title: Optional[str] = None,
) -> str:
    """
    Format extract events as an HTML <pre> monospace table for Telegram.
    """
    safe_title = html.escape(planner_title.strip()) if planner_title else None
    header_lines: list[str] = []
    if safe_title:
        header_lines.append(safe_title)
    header_lines.append(f"Found {len(events)} event{'s' if len(events) != 1 else ''}.")

    if not events:
        body = "No Holidays/PTC found in this image."
        return "\n".join(header_lines + ["", f"<pre>{body}</pre>"])

    rows = [["Date", "Type", "Name"]]
    for event in events:
        rows.append(
            [
                str(event.get("event_date") or ""),
                str(event.get("holiday_type") or event.get("category") or ""),
                str(event.get("event_name") or ""),
            ]
        )

    col_widths = [max(len(row[i]) for row in rows) for i in range(3)]
    lines: list[str] = []
    for index, row in enumerate(rows):
        line = " | ".join(row[i].ljust(col_widths[i]) for i in range(3))
        lines.append(line)
        if index == 0:
            lines.append("-+-".join("-" * col_widths[i] for i in range(3)))

    table = "\n".join(lines)
    return "\n".join(header_lines + ["", f"<pre>{html.escape(table)}</pre>"])


def _resolve_image_file(message: dict[str, Any]) -> tuple[str, str, str]:
    photos = message.get("photo") or []
    if photos:
        # Telegram sends multiple sizes; last entry is typically the largest.
        largest = photos[-1]
        file_id = largest.get("file_id")
        if not file_id:
            raise TelegramBotError("Photo update missing file_id.")
        return str(file_id), "telegram-photo.jpg", "image/jpeg"

    document = message.get("document") or {}
    file_id = document.get("file_id")
    if not file_id:
        raise TelegramBotError("Message has no downloadable image.")

    filename = str(document.get("file_name") or "telegram-document.jpg")
    mime = str(document.get("mime_type") or "").lower()
    if not mime:
        suffix = Path(filename).suffix.lower()
        mime = {
            ".png": "image/png",
            ".webp": "image/webp",
            ".gif": "image/gif",
            ".heic": "image/heic",
            ".heif": "image/heif",
            ".heics": "image/heic-sequence",
            ".heifs": "image/heif-sequence",
        }.get(suffix, "image/jpeg")
    return str(file_id), filename, mime


def _chunk_text(text: str, max_chars: int) -> list[str]:
    cleaned = (text or "").strip()
    if not cleaned:
        return []
    if len(cleaned) <= max_chars:
        return [cleaned]

    chunks: list[str] = []
    remaining = cleaned
    while remaining:
        if len(remaining) <= max_chars:
            chunks.append(remaining)
            break
        split_at = remaining.rfind("\n", 0, max_chars)
        if split_at < max_chars // 2:
            split_at = max_chars
        chunks.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip()
    return chunks
