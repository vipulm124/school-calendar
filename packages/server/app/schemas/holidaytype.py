from pydantic import BaseModel, field_validator
from uuid import UUID

def _uppercase_text(value: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValueError("must not be empty")
    return cleaned.upper()

class HolidayTypeCreateRequest(BaseModel):
    """Request model for creating a new holiday type."""
    holiday_type: str
    holiday_description: str

    @field_validator("holiday_type", mode="before")
    @classmethod
    def uppercase_holiday_type(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("must be a string")
        return _uppercase_text(value)



class HolidayTypeUpdateRequest(BaseModel):
    """Request model for updating an existing holiday type."""
    id: UUID
    holiday_type: str
    holiday_description: str

    
    @field_validator("holiday_type", mode="before")
    @classmethod
    def uppercase_holiday_type(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("must be a string")
        return _uppercase_text(value)