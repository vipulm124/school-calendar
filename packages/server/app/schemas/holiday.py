from pydantic import BaseModel
from uuid import UUID
import datetime as datetime


class HolidayCreateRequest(BaseModel):
    """Request model for creating a new holiday."""
    holiday_name: str
    holiday_date: datetime.date
    holiday_type_id: UUID
    student_class_id: UUID


class HolidayUpdateRequest(BaseModel):
    """Request model for updating an existing holiday."""
    id: UUID
    holiday_name: str
    holiday_date: datetime.date
    holiday_type_id: UUID
    student_class_id: UUID