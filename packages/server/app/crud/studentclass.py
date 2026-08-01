
from .base import BaseCrud
from models import StudentClass
from schemas import StudentClassCreateRequest, StudentClassUpdateRequest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException

class StudentClassCrud(BaseCrud[StudentClass, StudentClassCreateRequest, StudentClassUpdateRequest]):
    def __init__(self):
        super().__init__(model=StudentClass)


    async def get_by_class_name_and_section_name(self, *, session: AsyncSession, class_name: str, section_name: str):
        """
        Retrieve a student class by its class name and section name.
        Args:
            session: The database session.
            class_name: The name of the class.
            section_name: The name of the section.
        Returns:
            StudentClass | None: The retrieved student class, or None if not found.
        """
        query = select(self.model).where(
            self.model.class_name == class_name,
            self.model.section_name == section_name,
            self.model.is_deleted.is_(False),
        )
        result = await session.execute(query)
        return result.scalars().first()

    async def get_by_class_name(self, *, session: AsyncSession, class_name: str):
        """
        Retrieve a student class by its class name.
        Args:
            session: The database session.
            class_name: The name of the class.
        Returns:
            StudentClass | None: The retrieved student class, or None if not found.
        """
        query = select(self.model).where(
            self.model.class_name == class_name,
            self.model.is_deleted.is_(False),
        )
        result = await session.execute(query)
        return result.scalars().first()

    async def create_student_class(self, *, session: AsyncSession, create_obj: StudentClassCreateRequest, unique_identifier: str):
        """
        Create a new student class.
        Args:
            session: The database session.
            create_obj: The data for creating the student class.
            unique_identifier: A unique identifier for tracking who created the record.
        Returns:
            StudentClass: The created student class.
        """
        existing_class = await self.get_by_class_name(session=session, class_name=create_obj.class_name)
        if existing_class:
            raise HTTPException(status_code=400, detail=f"Student class with class name '{create_obj.class_name}' already exists.")
        
        new_student_class = await self.create(session=session, create_obj=create_obj, unique_identifier=unique_identifier) 
        new_interview_data = {"id":  new_student_class.id, "class_name": new_student_class.class_name, "section_name": new_student_class.section_name}

        return new_interview_data

