from fastapi import APIRouter, Depends, Request
from core import get_db, Response
from sqlalchemy.orm import Session
from schemas import StudentClassCreateRequest
from api.v1.studentclass.controller import StudentClassController
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

student_class_router = APIRouter(prefix="/student-class", tags=["Student Class"])

@student_class_router.post("/")
async def create_student_class(request: Request, student_class: StudentClassCreateRequest, session: AsyncSession = Depends(get_db)):
    """
    Create a new student class.

    Args:
        request (Request): The FastAPI request object.
        student_class (StudentClassCreateRequest): The student class data.

    Returns:
        dict: A dictionary containing the created student class data.
    """
    student_class_response = await StudentClassController().create_student_class(request=request, session=session, student_class_data=student_class)
    return Response.success(body=student_class_response, message="Student class created successfully.", status_code=200)

@student_class_router.get("/")
async def get_student_classes(session: AsyncSession = Depends(get_db)):
    """
    Retrieve all student classes.

    Args:
        session (AsyncSession): The database session.

    Returns:
        dict: A dictionary containing the list of student classes.
    """
    # Logic to retrieve all student classes from the database
    all_student_classes = await StudentClassController().get_all_student_classes(session=session)

    return all_student_classes

@student_class_router.get("/{class_id}")
async def get_student_class(class_id: UUID, session: AsyncSession = Depends(get_db)):
    """
    Retrieve all student classes.

    Args:
        session (AsyncSession): The database session.

    Returns:
        dict: A dictionary containing the list of student classes.
    """
    # Logic to retrieve all student classes from the database
    student_classes = await StudentClassController().get_student_class(session=session, class_id=class_id)

    return student_classes