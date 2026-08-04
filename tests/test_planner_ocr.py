"""Unit tests for Azure Foundry planner extraction."""

import asyncio
import sys
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock

sys.path.append(str(Path(__file__).resolve().parents[1] / "packages" / "server" / "app"))

from schemas.planner_ocr import CellCategory
from services.azure_foundry_planner import AzureFoundryPlannerService
from services.planner_ocr_pipeline import PlannerOcrPipeline


def test_parse_model_content_extracts_holidays_and_ptc():
    content = """
    {
      "planner_title": "PLANNER 2026-2027 (FS1 - III)",
      "events": [
        {"event_date": "2026-03-04", "event_name": "HOLI", "category": "Holidays"},
        {"event_date": "2026-03-27", "event_name": "NEW SESSION COMMENCES", "category": "PTC"},
        {"event_date": "2026-04-03", "event_name": "GOOD FRIDAY", "category": "Holidays"},
        {"event_date": "bad", "event_name": "SKIP", "category": "Holidays"},
        {"event_date": "2026-03-21", "event_name": "WEEKEND", "category": "Weekend"}
      ]
    }
    """
    result = AzureFoundryPlannerService._parse_model_content(content)
    assert result.planner_title == "PLANNER 2026-2027 (FS1 - III)"
    assert len(result.events) == 3
    by_name = {event.event_name: event for event in result.events}
    assert by_name["HOLI"].event_date == date(2026, 3, 4)
    assert by_name["HOLI"].holiday_type == "Holidays"
    assert by_name["NEW SESSION COMMENCES"].category == CellCategory.PTC
    assert by_name["GOOD FRIDAY"].category == CellCategory.HOLIDAYS


def test_parse_model_content_accepts_fenced_json():
    content = """```json
{"planner_title": null, "events": [{"event_date": "2026-05-01", "event_name": "BUDDHA PURNIMA", "category": "holiday"}]}
```"""
    result = AzureFoundryPlannerService._parse_model_content(content)
    assert len(result.events) == 1
    assert result.events[0].event_name == "BUDDHA PURNIMA"


def test_pipeline_uses_foundry_service():
    fake = AsyncMock()
    fake.extract_events = AsyncMock(
        return_value=AzureFoundryPlannerService._parse_model_content(
            '{"planner_title":"T","events":[{"event_date":"2026-03-04","event_name":"HOLI","category":"Holidays"}]}'
        )
    )
    pipeline = PlannerOcrPipeline(foundry_service=fake)
    result = asyncio.run(pipeline.extract_events(b"img", content_type="image/png"))
    preview = pipeline.preview_lines(result)

    fake.extract_events.assert_awaited_once()
    assert result.events[0].event_name == "HOLI"
    assert preview[0].startswith("1. 2026-03-04 — HOLI [Holiday]")


def test_build_request_normalizes_foundry_portal_responses_url():
    svc = AzureFoundryPlannerService(
        endpoint="https://school-calendar-foundry-project.services.ai.azure.com/openai/v1/responses",
        api_key="test-key",
        deployment="gpt-5.6-sol",
        api_version="2026-07-09",  # date-style must not be appended on v1
    )
    url, payload = svc._build_request(data_url="data:image/jpeg;base64,xx")
    assert url == (
        "https://school-calendar-foundry-project.services.ai.azure.com/openai/v1/chat/completions"
    )
    assert payload["model"] == "gpt-5.6-sol"


def test_build_request_keeps_v1_api_version_query():
    svc = AzureFoundryPlannerService(
        endpoint="https://school-calendar-foundry-project.services.ai.azure.com",
        api_key="test-key",
        deployment="gpt-4o-mini",
        api_version="v1",
    )
    url, _payload = svc._build_request(data_url="data:image/jpeg;base64,xx")
    assert url.endswith("/openai/v1/chat/completions?api-version=v1")
