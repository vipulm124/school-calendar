"""Azure AI Foundry vision LLM client for school planner extraction."""

from __future__ import annotations

import base64
import json
import re
from datetime import date
from typing import Any, Optional
from urllib.parse import urlparse

import httpx

from core.config import config
from schemas.planner_ocr import CellCategory, ParsedPlannerEvent, PlannerParseResult
from services.leave_day_numbering import base_event_name

EXTRACT_SYSTEM_PROMPT = """You extract school planner calendar events from an image.

Return ONLY valid JSON with this shape:
{
  "planner_title": "string or null",
  "events": [
    {
      "event_date": "YYYY-MM-DD",
      "event_name": "string",
      "category": "Holidays" | "PTC"
    }
  ]
}

Rules:
- Include ONLY green cells as category "Holidays".
- Include ONLY yellow cells as category "PTC".
- IGNORE pink/rose weekend cells.
- IGNORE blue/red/orange/purple/grey/white working days and other non-green/non-yellow cells.
- event_name is the text inside the cell (e.g. HOLI, GOOD FRIDAY, OPEN HOUSE).
- Build the full date from the month header (e.g. MARCH 2026) plus the day number in the cell.
- If a green cell has no label, use the nearest break label when obvious (e.g. SUMMER BREAK / WINTER BREAK).
- Multi-day / long-running leaves MUST use unique day-numbered names.
  When the same leave spans multiple dates (e.g. several green cells that are all WINTER BREAK or SUMMER BREAK),
  name them chronologically as:
    WINTER BREAK - DAY 1
    WINTER BREAK - DAY 2
    WINTER BREAK - DAY 3
  Do the same for SUMMER BREAK or any other repeated multi-day leave label.
  Never output the exact same event_name more than once.
- Single-day holidays keep their normal name (e.g. HOLI, GOOD FRIDAY).
- Do not invent events that are not visible.
- Sort events by date ascending.
"""

_ENDPOINT_SUFFIXES = (
    "/openai/v1/responses",
    "/openai/v1/chat/completions",
    "/openai/v1",
    "/models/chat/completions",
    "/models",
    "/chat/completions",
    "/responses",
)


class AzureFoundryError(RuntimeError):
    """Raised when Azure Foundry chat completion fails."""


class AzureFoundryPlannerService:
    """Uses a Foundry vision chat model to read planner images into structured events."""

    def __init__(
        self,
        *,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        deployment: Optional[str] = None,
        api_version: Optional[str] = None,
        timeout_seconds: float = 120.0,
    ) -> None:
        self.endpoint = (endpoint if endpoint is not None else config.AZURE_FOUNDRY_ENDPOINT).rstrip("/")
        self.api_key = api_key if api_key is not None else config.AZURE_FOUNDRY_API_KEY
        self.deployment = deployment if deployment is not None else config.AZURE_FOUNDRY_DEPLOYMENT
        self.api_version = api_version if api_version is not None else config.AZURE_FOUNDRY_API_VERSION
        self.timeout_seconds = timeout_seconds

    def _ensure_configured(self) -> None:
        if not self.endpoint or not self.api_key or not self.deployment:
            raise AzureFoundryError(
                "Azure Foundry is not configured. Set AZURE_FOUNDRY_ENDPOINT, "
                "AZURE_FOUNDRY_API_KEY, and AZURE_FOUNDRY_DEPLOYMENT."
            )

    async def extract_events(self, image_bytes: bytes, *, content_type: str = "image/jpeg") -> PlannerParseResult:
        self._ensure_configured()
        mime = self._normalize_mime(content_type)
        data_url = f"data:{mime};base64,{base64.b64encode(image_bytes).decode('ascii')}"

        url, payload = self._build_request(data_url=data_url)
        headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(url, headers=headers, json=payload)

        if response.status_code >= 400:
            raise AzureFoundryError(
                f"Azure Foundry request failed ({response.status_code}): {response.text}"
            )

        body = response.json()
        content = self._extract_message_content(body)
        return self._parse_model_content(content)

    def resource_base(self) -> str:
        """Normalize portal/copied URLs down to the resource origin."""
        endpoint = self.endpoint.strip().rstrip("/")
        parsed = urlparse(endpoint)
        if not parsed.scheme or not parsed.netloc:
            raise AzureFoundryError(f"Invalid AZURE_FOUNDRY_ENDPOINT: {self.endpoint}")

        path = parsed.path.rstrip("/")
        for suffix in _ENDPOINT_SUFFIXES:
            if path.endswith(suffix):
                path = path[: -len(suffix)]
                break
        # Keep only origin; ignore leftover path fragments from portal copy-paste.
        return f"{parsed.scheme}://{parsed.netloc}"

    def _build_request(self, *, data_url: str) -> tuple[str, dict]:
        messages = [
            {"role": "system", "content": EXTRACT_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Extract Holidays (green) and PTC (yellow) from this planner page. "
                            "Respond with JSON only."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": data_url, "detail": "high"},
                    },
                ],
            },
        ]
        payload: dict[str, Any] = {
            "model": self.deployment,
            "messages": messages,
            "temperature": 1,
            "max_completion_tokens": 4000,
            "response_format": {"type": "json_object"},
        }

        base = self.resource_base()
        host = urlparse(base).netloc.lower()

        # Foundry / Azure OpenAI OpenAI-v1 style (preferred):
        # POST https://<resource>.services.ai.azure.com/openai/v1/chat/completions
        # POST https://<resource>.openai.azure.com/openai/v1/chat/completions
        if host.endswith("services.ai.azure.com") or host.endswith("openai.azure.com"):
            url = f"{base}/openai/v1/chat/completions"
            api_version = (self.api_version or "").strip()
            # Date-style versions belong to legacy deployment APIs and cause 404 on v1.
            if api_version and not re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:-preview)?", api_version):
                url = f"{url}?api-version={api_version}"
            return url, payload

        # Legacy Cognitive Services /models route
        if "/models" in self.endpoint or host.endswith("cognitiveservices.azure.com"):
            url = f"{base}/models/chat/completions"
            if self.api_version:
                url = f"{url}?api-version={self.api_version}"
            return url, payload

        # Legacy Azure OpenAI deployments route
        url = (
            f"{base}/openai/deployments/{self.deployment}/chat/completions"
            f"?api-version={self.api_version or '2024-08-01-preview'}"
        )
        payload.pop("model", None)
        return url, payload

    @staticmethod
    def _extract_message_content(body: dict[str, Any]) -> str:
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AzureFoundryError(f"Unexpected Foundry response: {body}") from exc

        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") in {"text", "output_text"}:
                    parts.append(str(item.get("text") or ""))
                elif isinstance(item, str):
                    parts.append(item)
            content = "".join(parts)

        if not isinstance(content, str):
            raise AzureFoundryError(f"Unexpected Foundry message content: {content!r}")
        return content

    @staticmethod
    def _normalize_mime(content_type: str) -> str:
        mime = (content_type or "image/jpeg").split(";")[0].strip().lower()
        if mime in {"image/jpg", "image/pjpeg"}:
            return "image/jpeg"
        if mime in {"image/heic", "image/heif", "image/heic-sequence", "image/heif-sequence"}:
            return "image/jpeg"
        if mime not in {"image/jpeg", "image/png", "image/webp", "image/gif"}:
            return "image/jpeg"
        return mime

    @classmethod
    def _parse_model_content(cls, content: str) -> PlannerParseResult:
        payload = cls._load_json_object(content)
        title = payload.get("planner_title")
        if title is not None:
            title = str(title).strip() or None

        events: list[ParsedPlannerEvent] = []
        for raw in payload.get("events") or []:
            if not isinstance(raw, dict):
                continue
            parsed = cls._parse_event(raw)
            if parsed is not None:
                events.append(parsed)

        events.sort(key=lambda event: (event.event_date, event.event_name))
        events = cls._number_repeated_leave_names(events)
        return PlannerParseResult(events=events, planner_title=title)

    @staticmethod
    def _base_event_name(name: str) -> str:
        return base_event_name(name)

    @classmethod
    def _number_repeated_leave_names(
        cls, events: list[ParsedPlannerEvent]
    ) -> list[ParsedPlannerEvent]:
        """
        Ensure multi-day leaves are unique: WINTER BREAK - DAY 1, DAY 2, ...

        Runs after LLM parse so duplicate names still save under the holiday uniqueness rule.
        """
        groups: dict[str, list[int]] = {}
        for index, event in enumerate(events):
            base = cls._base_event_name(event.event_name)
            groups.setdefault(base, []).append(index)

        updated = list(events)
        for base, indices in groups.items():
            if len(indices) <= 1:
                continue
            indices.sort(key=lambda i: (updated[i].event_date, i))
            for day_number, index in enumerate(indices, start=1):
                event = updated[index]
                updated[index] = event.model_copy(
                    update={"event_name": f"{base} - DAY {day_number}"}
                )
        return updated

    @staticmethod
    def _load_json_object(content: str) -> dict[str, Any]:
        text = (content or "").strip()
        if not text:
            raise AzureFoundryError("Foundry returned empty content.")

        fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL | re.IGNORECASE)
        if fence:
            text = fence.group(1)

        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise AzureFoundryError(f"Foundry returned non-JSON content: {content[:500]}") from exc

        if not isinstance(payload, dict):
            raise AzureFoundryError("Foundry JSON root must be an object.")
        return payload

    @staticmethod
    def _parse_event(raw: dict[str, Any]) -> Optional[ParsedPlannerEvent]:
        name = str(raw.get("event_name") or "").strip()
        date_value = raw.get("event_date")
        category_raw = str(raw.get("category") or raw.get("holiday_type") or "").strip()

        if not name or not date_value:
            return None

        try:
            event_date = date.fromisoformat(str(date_value)[:10])
        except ValueError:
            return None

        category = AzureFoundryPlannerService._normalize_category(category_raw)
        if category is None:
            return None

        holiday_type = "Holidays" if category == CellCategory.HOLIDAYS else "PTC"
        return ParsedPlannerEvent(
            event_date=event_date,
            event_name=name.upper(),
            holiday_type=holiday_type,
            category=category,
        )

    @staticmethod
    def _normalize_category(value: str) -> Optional[CellCategory]:
        normalized = value.strip().lower()
        if normalized in {"holidays", "holiday", "green"}:
            return CellCategory.HOLIDAYS
        if normalized in {"ptc", "yellow", "parent teacher consultation", "parent-teacher consultation"}:
            return CellCategory.PTC
        return None
