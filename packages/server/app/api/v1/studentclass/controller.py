
from typing import Dict

from crud import StudentClassCrud
from schemas import StudentClassCreateRequest, StudentClassUpdateRequest
from sqlalchemy.orm import Session
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

class StudentClassController:
    """Controller for handling student class related operations."""

    def __init__(self):
        self.student_crud = StudentClassCrud()

    async def create_student_class(self, request: Request, session: AsyncSession, student_class_data:StudentClassCreateRequest) -> Dict:
        """Create a new student class."""
        # Logic to create a new student class in the database
        return await self.student_crud.create_student_class(
            session=session,
            create_obj=student_class_data,
            unique_identifier="system"  # Replace with actual user identifier
        )

    async def get_all_student_classes(self, session: AsyncSession):
        """Retrieve all student classes."""
        # Logic to retrieve all student classes from the database
        return await self.student_crud.get_multi(session=session, skip=0, limit=100)

    async def get_student_class(self, session: AsyncSession, class_id: UUID):
        """Retrieve a student class by its ID."""
        # Logic to retrieve a student class from the database
        return await self.student_crud.get(session=session, field=self.student_crud.model.id, value=class_id)
