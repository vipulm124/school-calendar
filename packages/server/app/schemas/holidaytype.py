from pydantic import BaseModel, Field
from uuid import UUID



class HolidayTypeCreateRequest(BaseModel):
    """Request model for creating a new holiday type."""
    holiday_type: str
    holiday_description: str



class HolidayTypeUpdateRequest(BaseModel):
    """Request model for updating an existing holiday type."""
    id: UUID
    holiday_type: str
    holiday_description: str