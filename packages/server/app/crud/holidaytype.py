
from .base import BaseCrud
from models import HolidayType
from schemas import HolidayTypeCreateRequest, HolidayTypeUpdateRequest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException

class HolidayTypeCrud(BaseCrud[HolidayType, HolidayTypeCreateRequest, HolidayTypeUpdateRequest]):
    def __init__(self):
        super().__init__(model=HolidayType)


    async def get_by_holiday_type_name(self, *, session: AsyncSession, holiday_type: str):
        """
        Retrieve a holiday type by its name.
        Args:
            session: The database session.
            holiday_type: The name of the holiday type.
        Returns:
            HolidayType | None: The retrieved holiday type, or None if not found.
        """
        query = select(self.model).where(
            self.model.holiday_type == holiday_type,
            self.model.is_deleted.is_(False),
        )
        result = await session.execute(query)
        return result.scalars().first()



    async def get_by_holiday_type_id(self, *, session: AsyncSession, holiday_type_id: int):
        """
        Retrieve a holiday type by its ID.
        Args:
            session: The database session.
            holiday_type_id: The ID of the holiday type.
        Returns:
            HolidayType | None: The retrieved holiday type, or None if not found.
        """
        query = select(self.model).where(
            self.model.id == holiday_type_id,
            self.model.is_deleted.is_(False),
        )
        result = await session.execute(query)
        return result.scalars().first()



    async def create_holiday_type(self, *, session: AsyncSession, create_obj: HolidayTypeCreateRequest, unique_identifier: str):
        """
        Create a new holiday type.
        Args:
            session: The database session.
            create_obj: The data for creating the holiday type.
            unique_identifier: A unique identifier for tracking who created the record.
        Returns:
            HolidayType: The created holiday type.
        """
        existing_type = await self.get_by_holiday_type_name(session=session, holiday_type=create_obj.holiday_type)
        if existing_type:
            raise HTTPException(status_code=400, detail=f"Holiday type with name '{create_obj.holiday_type}' already exists.")

        new_holiday_type = await self.create(session=session, create_obj=create_obj, unique_identifier=unique_identifier)
        new_interview_data = {"id": new_holiday_type.id, "holiday_type": new_holiday_type.holiday_type}

        return new_interview_data

