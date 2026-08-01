
from sqlalchemy import VARCHAR
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base

class HolidayType(Base):
    __tablename__ = "holiday_type"
    __table_args__ = {"schema": "calendar"}
    holiday_type: Mapped[str] = mapped_column(VARCHAR(100), unique=True, nullable=False)
    holiday_description: Mapped[str] = mapped_column(VARCHAR(255), nullable=True)