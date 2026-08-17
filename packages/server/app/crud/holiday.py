
from typing import Optional
from .base import BaseCrud
from models import Holiday
from schemas import HolidayCreateRequest, HolidayUpdateRequest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
import datetime as datetime
from uuid import UUID

class HolidayCrud(BaseCrud[Holiday, HolidayCreateRequest, HolidayUpdateRequest]):
    def __init__(self):
        super().__init__(model=Holiday)


    async def get_by_holiday_name(self, *, session: AsyncSession, holiday_name: str):
        """
        Retrieve a holiday by its name.
        Args:
            session: The database session.
            holiday_name: The name of the holiday.
        Returns:
            Holiday | None: The retrieved holiday, or None if not found.
        """
        query = select(self.model).where(
            self.model.holiday_name == holiday_name,
            self.model.is_deleted.is_(False),
        )
        result = await session.execute(query)
        return result.scalars().first()

    async def get_by_holiday_name_for_class(self, *, session: AsyncSession, student_class_id: UUID,  holiday_name: str):
        """
        Retrieve a holiday by its name for a class.
        Args:
            session: The database session.
            student_class_id: The ID of the student class.
            holiday_name: The name of the holiday.
        Returns:
            Holiday | None: The retrieved holiday, or None if not found.
        """
        query = select(self.model).where(
            self.model.holiday_name == holiday_name,
            self.model.student_class_id == str(student_class_id),
            self.model.is_deleted.is_(False),
        )
        result = await session.execute(query)
        return result.scalars().first()


    async def get_by_holiday_date_for_class(self, *, session: AsyncSession, student_class_id: UUID,  holiday_date: datetime.date):
        """
        Retrieve a holiday by its date for a class.
        Args:
            session: The database session.
            student_class_id: The ID of the student class.
            holiday_date: The date of the holiday.
        Returns:
            Holiday | None: The retrieved holiday, or None if not found.
        """
        query = select(self.model).where(
            self.model.holiday_date == holiday_date,
            self.model.student_class_id == str(student_class_id),
            self.model.is_deleted.is_(False),
        )
        result = await session.execute(query)
        return result.scalars().first()

    async def list_by_student_class(self, *, session: AsyncSession, student_class_id: UUID):
        """Return all non-deleted holidays for a student class, ordered by date."""
        query = (
            select(self.model)
            .where(
                self.model.student_class_id == str(student_class_id),
                self.model.is_deleted.is_(False),
            )
            .order_by(self.model.holiday_date.asc())
        )
        result = await session.execute(query)
        return list(result.scalars().all())

    async def update_holiday_name(
        self, *, session: AsyncSession, holiday_id: UUID, holiday_name: str, unique_identifier: str
    ):
        """Update only the holiday name for an existing row."""
        holiday = await self.get_by_holiday_id(session=session, holiday_id=holiday_id)
        if holiday is None:
            raise HTTPException(status_code=404, detail=f"Holiday with ID '{holiday_id}' not found.")
        holiday.holiday_name = holiday_name.strip().upper()
        holiday.updated_by = unique_identifier
        return await self._commit_and_refresh(session=session, db_obj=holiday)

    async def get_by_holiday_id(self, *, session: AsyncSession, holiday_id: UUID):
        """
        Retrieve a holiday by its ID.
        Args:
            session: The database session.
            holiday_id: The ID of the holiday.
        Returns:
            Holiday | None: The retrieved holiday, or None if not found.
        """
        query = select(self.model).where(
            self.model.id == str(holiday_id),
            self.model.is_deleted.is_(False),
        )
        result = await session.execute(query)
        return result.scalars().first()

    async def get_holidays_after_date(self, *, session: AsyncSession, student_class_id: Optional[UUID] = None, date: Optional[datetime.date] = None):
            """
            Retrieve holidays after a specific date.
            Args:
                session: The database session.
                date: The date to filter holidays after.
            Returns:
                List[Holiday]: The list of retrieved holidays.
            """
            cut_off_date = date or datetime.date.today()
            query = select(self.model).where(
                self.model.holiday_date > cut_off_date,
                self.model.is_deleted.is_(False),
            )
            if student_class_id:
                query = query.where(self.model.student_class_id == str(student_class_id))
            result = await session.execute(query)
            return result.scalars().all()

    async def create_holiday(self, *, session: AsyncSession, create_obj: HolidayCreateRequest, unique_identifier: str):
        """
        Create a new holiday.
        Args:
            session: The database session.
            create_obj: The data for creating the holiday.
            unique_identifier: A unique identifier for tracking who created the record.
        Returns:
            Holiday: The created holiday.
        """
        existing_holiday = await self.get_by_holiday_date_for_class(session=session, student_class_id=create_obj.student_class_id, holiday_date=create_obj.holiday_date)
        
        if existing_holiday:
            raise HTTPException(status_code=400, detail=f"Holiday on date '{create_obj.holiday_date}' already exists for class with ID '{create_obj.student_class_id}'.")

        if isinstance(create_obj.holiday_date, str):
            try:
                create_obj.holiday_date = datetime.datetime.strptime(create_obj.holiday_date, "%Y-%m-%d").date()
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=f"Invalid holiday_date format: {create_obj.holiday_date}") from exc

        new_holiday = await self.create(session=session, create_obj=create_obj, unique_identifier=unique_identifier)
        new_interview_data = {"id": new_holiday.id, "holiday_name": new_holiday.holiday_name}

        return new_interview_data

