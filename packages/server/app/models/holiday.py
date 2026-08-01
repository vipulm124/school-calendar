import datetime

from sqlalchemy import TIMESTAMP, VARCHAR, ForeignKey, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base
from uuid import UUID
from datetime import date
from sqlalchemy import Date, func

class Holiday(Base):
    __tablename__ = "holiday"
    __table_args__ = {"schema": "calendar"}
    holiday_name: Mapped[str] = mapped_column(VARCHAR(100), nullable=False)
    holiday_date: Mapped[date] = mapped_column(
        Date,                      # 1. Corrected to native Postgres DATE type
        server_default=func.current_date(),  # 2. Corrected to dynamic database-side default
    )
    holiday_type_id: Mapped[UUID] = mapped_column(ForeignKey("calendar.holiday_type.id"), nullable=False)
    student_class_id: Mapped[UUID] = mapped_column(ForeignKey("calendar.student_class.id"), nullable=False)
