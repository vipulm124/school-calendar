from pydantic import BaseModel, field_validator
from uuid import UUID
import datetime as datetime

def _uppercase_text(value: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValueError("must not be empty")
    return cleaned.upper()

class HolidayCreateRequest(BaseModel):
    """Request model for creating a new holiday."""
    holiday_name: str
    holiday_date: datetime.date
    holiday_type_id: UUID
    student_class_id: UUID

    @field_validator("holiday_name", mode="before")
    @classmethod
    def uppercase_names(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("must be a string")
        return _uppercase_text(value)


class HolidayUpdateRequest(BaseModel):
    """Request model for updating an existing holiday."""
    id: UUID
    holiday_name: str
    holiday_date: datetime.date
    holiday_type_id: UUID
    student_class_id: UUID

    @field_validator("holiday_name", mode="before")
    @classmethod
    def uppercase_names(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("must be a string")
        return _uppercase_text(value)