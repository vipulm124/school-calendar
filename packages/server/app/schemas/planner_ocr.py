"""Schemas for planner image extraction."""

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class CellCategory(str, Enum):
    """Planner cell categories derived from background color."""

    HOLIDAYS = "Holidays"
    PTC = "PTC"
    OTHER = "Other"


class ParsedPlannerEvent(BaseModel):
    """One extracted planner event ready for preview / save."""

    event_date: date
    event_name: str
    holiday_type: str
    category: CellCategory


class PlannerParseResult(BaseModel):
    """Full parse output from a planner image."""

    events: list[ParsedPlannerEvent] = Field(default_factory=list)
    planner_title: Optional[str] = None
