"""End-to-end planner image extraction via Azure Foundry vision LLM."""

from __future__ import annotations

from typing import Optional

from schemas.planner_ocr import CellCategory, PlannerParseResult
from services.azure_foundry_planner import AzureFoundryPlannerService


class PlannerOcrPipeline:
    """Extract Holidays (green) and PTC (yellow) events from a planner photo."""

    def __init__(self, *, foundry_service: Optional[AzureFoundryPlannerService] = None) -> None:
        self.foundry_service = foundry_service or AzureFoundryPlannerService()

    async def extract_events(
        self, image_bytes: bytes, *, content_type: str = "image/jpeg"
    ) -> PlannerParseResult:
        return await self.foundry_service.extract_events(image_bytes, content_type=content_type)

    @staticmethod
    def preview_lines(result: PlannerParseResult) -> list[str]:
        lines: list[str] = []
        for index, event in enumerate(result.events, start=1):
            label = "Holiday" if event.category == CellCategory.HOLIDAYS else "PTC"
            lines.append(
                f"{index}. {event.event_date.isoformat()} — {event.event_name} [{label}]"
            )
        return lines
