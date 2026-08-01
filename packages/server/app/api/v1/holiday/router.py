from fastapi import APIRouter, Depends, Request
from core import get_db, Response
from sqlalchemy.orm import Session
from api.v1.holiday.controller import HolidayController
from schemas import HolidayCreateRequest
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
import datetime as datetime

holiday_router = APIRouter(prefix="/holiday", tags=["Holiday"])

@holiday_router.post("/")
async def create_holiday(request: Request, holiday: HolidayCreateRequest, session: AsyncSession = Depends(get_db)):
    """
    Create a new holiday.

    Args:
        request (Request): The FastAPI request object.
        holiday (HolidayCreateRequest): The holiday data.

    Returns:
        dict: A dictionary containing the created holiday data.
    """
    holiday_response = await HolidayController().create_holiday(request=request, session=session, holiday_data=holiday)
    return Response.success(body=holiday_response, message="Holiday created successfully.", status_code=200)

@holiday_router.get("/")
async def get_holidays(session: AsyncSession = Depends(get_db)):
    """
    Retrieve all holidays.

    Args:
        session (AsyncSession): The database session.

    Returns:
        dict: A dictionary containing the list of holidays.
    """
    # Logic to retrieve all holidays from the database
    all_holidays = await HolidayController().get_all_holidays(session=session)

    return all_holidays

@holiday_router.get("/{holiday_id}")
async def get_holiday(holiday_id: UUID, session: AsyncSession = Depends(get_db)):
    """
    Retrieve a holiday by its ID.

    Args:
        holiday_id (UUID): The ID of the holiday to retrieve.
        session (AsyncSession): The database session.

    Returns:
        dict: A dictionary containing the retrieved holiday.
    """
    # Logic to retrieve a holiday from the database
    holiday = await HolidayController().get_holiday(session=session, holiday_id=holiday_id)

    return holiday


@holiday_router.get("/class/{student_class_id}")
async def get_holidays_for_class(student_class_id: UUID, session: AsyncSession = Depends(get_db)):
    """
    Retrieve holidays for a specific student class.

    Args:
        student_class_id (UUID): The ID of the student class.
        session (AsyncSession): The database session.

    Returns:
        dict: A dictionary containing the list of holidays for the class.
    """
    date = datetime.date.today().replace(month=1, day=1)
    holidays = await HolidayController().get_holiday_for_a_class_after_a_date(session=session, student_class_id=student_class_id, date=date)

    return holidays

