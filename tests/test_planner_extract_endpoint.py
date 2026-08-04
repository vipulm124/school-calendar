"""Tests for planner extract endpoint."""

import sys
from datetime import date
from io import BytesIO
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

sys.path.append(str(Path(__file__).resolve().parents[1] / "packages" / "server" / "app"))

from api.v1.planner.router import planner_router
from schemas.planner_ocr import CellCategory, ParsedPlannerEvent, PlannerParseResult


def _png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (40, 40), color=(120, 190, 90)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_extract_endpoint_returns_parsed_events(monkeypatch):
    app = FastAPI()
    app.include_router(planner_router, prefix="/planner")

    fake_result = PlannerParseResult(
        planner_title="PLANNER 2026-2027 (FS1 - III)",
        events=[
            ParsedPlannerEvent(
                event_date=date(2026, 3, 4),
                event_name="HOLI",
                holiday_type="Holidays",
                category=CellCategory.HOLIDAYS,
            ),
            ParsedPlannerEvent(
                event_date=date(2026, 3, 27),
                event_name="NEW SESSION COMMENCES",
                holiday_type="PTC",
                category=CellCategory.PTC,
            ),
        ],
    )

    class FakeController:
        async def extract_from_upload(self, *, image):  # noqa: ARG002
            return {
                "planner_title": fake_result.planner_title,
                "event_count": len(fake_result.events),
                "preview": [
                    "1. 2026-03-04 — HOLI [Holiday]",
                    "2. 2026-03-27 — NEW SESSION COMMENCES [PTC]",
                ],
                "events": [event.model_dump(mode="json") for event in fake_result.events],
            }

    monkeypatch.setattr("api.v1.planner.router.PlannerController", FakeController)

    client = TestClient(app)
    response = client.post(
        "/planner/extract",
        files={"image": ("planner.png", _png_bytes(), "image/png")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["details"]["event_count"] == 2
    assert payload["details"]["events"][0]["event_name"] == "HOLI"
    assert payload["details"]["events"][1]["holiday_type"] == "PTC"


def test_extract_endpoint_rejects_non_image():
    app = FastAPI()
    app.include_router(planner_router, prefix="/planner")

    client = TestClient(app)
    response = client.post(
        "/planner/extract",
        files={"image": ("notes.txt", b"not an image", "text/plain")},
    )

    assert response.status_code == 400
