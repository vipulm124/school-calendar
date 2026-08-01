
from typing import Dict, Optional

from crud import HolidayCrud
from schemas import HolidayTypeUpdateRequest
from schemas import HolidayCreateRequest, HolidayUpdateRequest
from sqlalchemy.orm import Session
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
import datetime as datetime

class HolidayController:
    """Controller for handling holiday related operations."""

    def __init__(self):
        self.holiday_crud = HolidayCrud()

    async def create_holiday(self, request: Request, session: AsyncSession, holiday_data: HolidayCreateRequest) -> Dict:
        """Create a new holiday."""
        # Logic to create a new holiday in the database
        return await self.holiday_crud.create_holiday(
            session=session,
            create_obj=holiday_data,
            unique_identifier="system"  # Replace with actual user identifier
        )

    async def get_all_holidays(self, session: AsyncSession):
        """Retrieve all holidays."""
        # Logic to retrieve all holidays from the database
        return await self.holiday_crud.get_multi(session=session, skip=0, limit=100)

    async def get_holiday(self, session: AsyncSession, holiday_id: UUID):
        """Retrieve a holiday by its ID."""
        # Logic to retrieve a holiday from the database
        return await self.holiday_crud.get_by_holiday_id(session=session, holiday_id=holiday_id)


    async def get_holiday_for_a_class_after_a_date(self, session: AsyncSession, student_class_id: Optional[UUID] = None, date: Optional[datetime.date] = None):
            """Retrieve a holiday by its ID."""
            # Logic to retrieve a holiday from the database
            return await self.holiday_crud.get_holidays_after_date(session=session, student_class_id=student_class_id, date=date)
        

    async def delete_holiday(self, holiday_id: UUID):
        """Delete a holiday by its ID."""
        # Logic to delete a holiday from the database
        pass