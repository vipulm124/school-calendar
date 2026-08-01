from sqlalchemy import VARCHAR, ForeignKey, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base

class StudentClass(Base):
    __tablename__ = "student_class"
    __table_args__ = {"schema": "calendar"}
    class_name: Mapped[str] = mapped_column(VARCHAR(100), unique=True, nullable=False)
    section_name: Mapped[str] = mapped_column(VARCHAR(10), nullable=False)
