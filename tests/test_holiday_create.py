import asyncio
import sys
from datetime import date
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import Date
from sqlalchemy.orm import Mapped, mapped_column

sys.path.append(str(Path(__file__).resolve().parents[1] / "packages" / "server" / "app"))

from crud.base import BaseCrud
from models.base import Base


class DummyModel(Base):
    __tablename__ = "dummy_model"
    holiday_date: Mapped[date] = mapped_column(Date)
    holiday_type_id: Mapped[str] = mapped_column()


class DummyCreateRequest(BaseModel):
    holiday_date: date
    holiday_type_id: UUID


def test_base_crud_create_preserves_date_objects():
    crud = BaseCrud(model=DummyModel)

    async def fake_commit_and_refresh(*, session, db_obj):
        assert isinstance(db_obj.holiday_date, date)
        assert db_obj.holiday_date == date(2026, 8, 15)
        assert isinstance(db_obj.holiday_type_id, str)
        assert db_obj.holiday_type_id == "b37af6a6-988b-4dba-bc90-22a62412b4d5"
        return db_obj

    crud._commit_and_refresh = fake_commit_and_refresh

    asyncio.run(
        crud.create(
            session=object(),
            create_obj=DummyCreateRequest(
                holiday_date=date(2026, 8, 15),
                holiday_type_id=UUID("b37af6a6-988b-4dba-bc90-22a62412b4d5"),
            ),
            unique_identifier="system",
        )
    )
