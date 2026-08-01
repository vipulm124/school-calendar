from fastapi import APIRouter, Depends, Request
from core import get_db, Response
from sqlalchemy.orm import Session
from api.v1.studentclass.controller import StudentClassController
from schemas import HolidayTypeCreateRequest
from api.v1.holidaytype.controller import HolidayTypeController
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

holiday_type_router = APIRouter(prefix="/holiday-type", tags=["Holiday Type"])

@holiday_type_router.post("/")
async def create_holiday_type(request: Request, holiday_type: HolidayTypeCreateRequest, session: AsyncSession = Depends(get_db)):
    """
    Create a new student class.

    Args:
        request (Request): The FastAPI request object.
        student_class (StudentClassCreateRequest): The student class data.

    Returns:
        dict: A dictionary containing the created student class data.
    """
    holiday_type_response = await HolidayTypeController().create_holiday_type(request=request, session=session, holiday_type_data=holiday_type)
    return Response.success(body=holiday_type_response, message="Holiday type created successfully.", status_code=200)

@holiday_type_router.get("/")
async def get_holiday_types(session: AsyncSession = Depends(get_db)):
    """
    Retrieve all holiday types.

    Args:
        session (AsyncSession): The database session.

    Returns:
        dict: A dictionary containing the list of holiday types.
    """
    # Logic to retrieve all holiday types from the database
    all_holiday_types = await HolidayTypeController().get_all_holiday_types(session=session)

    return all_holiday_types

@holiday_type_router.get("/{holiday_type_id}")
async def get_holiday_type(holiday_type_id: UUID, session: AsyncSession = Depends(get_db)):
    """
    Retrieve a holiday type by its ID.

    Args:
        holiday_type_id (UUID): The ID of the holiday type to retrieve.
        session (AsyncSession): The database session.

    Returns:
        dict: A dictionary containing the retrieved holiday type.
    """
    # Logic to retrieve a holiday type from the database
    holiday_type = await HolidayTypeController().get_holiday_type(session=session, holiday_type_id=holiday_type_id)

    return holiday_type
