from pydantic import BaseModel, Field
from uuid import UUID



class StudentClassCreateRequest(BaseModel):
    """Request model for creating a new student class."""
    class_name: str
    section_name: str



class StudentClassUpdateRequest(BaseModel):
    """Request model for updating an existing student class."""
    id: UUID
    class_name: str
    section_name: str