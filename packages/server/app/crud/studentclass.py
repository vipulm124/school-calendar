
from .base import BaseCrud
from models import StudentClass
from schemas import StudentClassCreateRequest, StudentClassUpdateRequest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
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
        class_name_norm = str(class_name).strip().upper()
        section_name_norm = str(section_name).strip().upper()
        query = select(self.model).where(
            func.upper(self.model.class_name) == class_name_norm,
            func.upper(self.model.section_name) == section_name_norm,
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
        class_name_norm = str(class_name).strip().upper()
        query = select(self.model).where(
            func.upper(self.model.class_name) == class_name_norm,
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
        # Schema validators already uppercase; keep defense-in-depth for direct callers.
        create_obj.class_name = str(create_obj.class_name).strip().upper()
        create_obj.section_name = str(create_obj.section_name).strip().upper()

        existing_class = await self.get_by_class_name(session=session, class_name=create_obj.class_name)
        if existing_class:
            raise HTTPException(status_code=400, detail=f"Student class with class name '{create_obj.class_name}' already exists.")
        
        new_student_class = await self.create(session=session, create_obj=create_obj, unique_identifier=unique_identifier) 
        new_interview_data = {"id":  new_student_class.id, "class_name": new_student_class.class_name, "section_name": new_student_class.section_name}

        return new_interview_data

