from pydantic import BaseModel, field_validator
from uuid import UUID


def _uppercase_text(value: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValueError("must not be empty")
    return cleaned.upper()


class StudentClassCreateRequest(BaseModel):
    """Request model for creating a new student class."""

    class_name: str
    section_name: str

    @field_validator("class_name", "section_name", mode="before")
    @classmethod
    def uppercase_names(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("must be a string")
        return _uppercase_text(value)


class StudentClassUpdateRequest(BaseModel):
    """Request model for updating an existing student class."""

    id: UUID
    class_name: str
    section_name: str

    @field_validator("class_name", "section_name", mode="before")
    @classmethod
    def uppercase_names(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("must be a string")
        return _uppercase_text(value)
