
from typing import Dict

from crud import HolidayTypeCrud
from schemas import HolidayTypeCreateRequest, HolidayTypeUpdateRequest
from sqlalchemy.orm import Session
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

class HolidayTypeController:
    """Controller for handling holiday related operations."""

    def __init__(self):
        self.holiday_crud = HolidayTypeCrud()

    async def create_holiday_type(self, request: Request, session: AsyncSession, holiday_type_data: HolidayTypeCreateRequest) -> Dict:
        """Create a new holiday type."""
        # Logic to create a new holiday type in the database
        return await self.holiday_crud.create_holiday_type(
            session=session,
            create_obj=holiday_type_data,
            unique_identifier="system"  # Replace with actual user identifier
        )

    async def get_all_holiday_types(self, session: AsyncSession):
        """Retrieve all holiday types."""
        # Logic to retrieve all holiday types from the database
        return await self.holiday_crud.get_multi(session=session, skip=0, limit=100)

    async def get_holiday_type(self, session: AsyncSession, holiday_type_id: UUID):
        """Retrieve a holiday type by its ID."""
        # Logic to retrieve a holiday type from the database
        return await self.holiday_crud.get(session=session, field=self.holiday_crud.model.id, value=holiday_type_id)

    async def update_holiday_type(self, holiday_type_id: UUID, updated_data: HolidayTypeUpdateRequest):
        """Update an existing holiday type."""
        # Logic to update a holiday type in the database
        pass

    async def delete_holiday_type(self, holiday_type_id: UUID):
        """Delete a holiday type by its ID."""
        # Logic to delete a holiday type from the database
        pass