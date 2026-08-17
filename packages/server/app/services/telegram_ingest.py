"""Persist Telegram-extracted planner events into holiday_type + holiday tables."""

from __future__ import annotations

import datetime as datetime
import re
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from crud import HolidayCrud, HolidayTypeCrud, StudentClassCrud
from schemas import HolidayCreateRequest, HolidayTypeCreateRequest, StudentClassCreateRequest
from services.leave_day_numbering import (
    ExistingHolidayRef,
    renumber_leave_series,
)

_CLASS_SPLIT = re.compile(r"^(.+?)[\s\-–—]+(.+)$")


def parse_class_label(raw: str) -> tuple[str, str, str]:
    """
    Parse user class input into (class_name, section_name, display_label).

    Examples:
      "5-A" -> ("5", "A", "5-A")
      "FS1" -> ("FS1", "-", "FS1")
    """
    label = re.sub(r"\s+", " ", (raw or "").strip())
    if not label:
        raise ValueError("Class name cannot be empty.")

    match = _CLASS_SPLIT.match(label)
    if match:
        class_name = match.group(1).strip()
        section_name = match.group(2).strip() or "-"
    else:
        class_name = label
        section_name = "-"

    if not class_name:
        raise ValueError("Class name cannot be empty.")
    class_name = class_name.upper()
    section_name = section_name.upper()
    label = f"{class_name}-{section_name}" if section_name != "-" else class_name
    return class_name, section_name, label


class TelegramIngestService:
    """Get-or-create class/types and create holidays from extracted events."""

    def __init__(self) -> None:
        self.student_class_crud = StudentClassCrud()
        self.holiday_type_crud = HolidayTypeCrud()
        self.holiday_crud = HolidayCrud()

    async def resolve_student_class(
        self,
        *,
        session: AsyncSession,
        class_name: str,
        section_name: str,
        unique_identifier: str = "telegram",
        create_if_missing: bool = False,
    ) -> dict[str, Any] | None:
        """Look up (and optionally create) the student class used for ingest."""
        existing = await self.student_class_crud.get_by_class_name_and_section_name(
            session=session,
            class_name=class_name,
            section_name=section_name,
        )
        if existing:
            return {
                "id": existing.id,
                "class_name": existing.class_name,
                "section_name": existing.section_name,
            }

        by_name = await self.student_class_crud.get_by_class_name(
            session=session, class_name=class_name
        )
        if by_name:
            return {
                "id": by_name.id,
                "class_name": by_name.class_name,
                "section_name": by_name.section_name,
            }

        if not create_if_missing:
            return None

        return await self.student_class_crud.create_student_class(
            session=session,
            create_obj=StudentClassCreateRequest(
                class_name=class_name,
                section_name=section_name,
            ),
            unique_identifier=unique_identifier,
        )

    async def continue_leave_day_numbers(
        self,
        *,
        session: AsyncSession,
        class_name: str,
        section_name: str,
        events: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Continue multi-day leave DAY numbers from DB when this extract is a
        contiguous continuation (no new commencement header / not a fresh run).
        """
        student_class = await self.resolve_student_class(
            session=session,
            class_name=class_name,
            section_name=section_name,
            create_if_missing=False,
        )
        if student_class is None:
            renumbered, _ = renumber_leave_series(new_events=events, existing=[])
            return renumbered

        existing_rows = await self.holiday_crud.list_by_student_class(
            session=session,
            student_class_id=UUID(str(student_class["id"])),
        )
        existing = [
            ExistingHolidayRef(
                id=row.id,
                holiday_date=row.holiday_date,
                holiday_name=row.holiday_name,
            )
            for row in existing_rows
        ]
        renumbered, _ = renumber_leave_series(new_events=events, existing=existing)
        return renumbered

    async def save_events(
        self,
        *,
        session: AsyncSession,
        class_name: str,
        section_name: str,
        events: list[dict[str, Any]],
        unique_identifier: str = "telegram",
    ) -> dict[str, Any]:
        student_class = await self.resolve_student_class(
            session=session,
            class_name=class_name,
            section_name=section_name,
            unique_identifier=unique_identifier,
            create_if_missing=True,
        )
        assert student_class is not None
        student_class_id = UUID(str(student_class["id"]))

        existing_rows = await self.holiday_crud.list_by_student_class(
            session=session,
            student_class_id=student_class_id,
        )
        existing = [
            ExistingHolidayRef(
                id=row.id,
                holiday_date=row.holiday_date,
                holiday_name=row.holiday_name,
            )
            for row in existing_rows
        ]
        events, name_updates = renumber_leave_series(
            new_events=events,
            existing=existing,
        )

        renamed = 0
        for update in name_updates:
            await self.holiday_crud.update_holiday_name(
                session=session,
                holiday_id=UUID(str(update.id)),
                holiday_name=update.holiday_name,
                unique_identifier=unique_identifier,
            )
            renamed += 1

        type_cache: dict[str, UUID] = {}
        created = 0
        skipped = 0
        skipped_existing: list[str] = []
        errors: list[str] = []

        for event in events:
            event_name = str(event.get("event_name") or "").strip()
            holiday_type_name = str(event.get("holiday_type") or event.get("category") or "").strip()
            event_date_raw = event.get("event_date")
            if not event_name or not holiday_type_name or not event_date_raw:
                skipped += 1
                errors.append(f"{event_name or '(missing name)'}: incomplete event data")
                continue

            try:
                event_date = (
                    event_date_raw
                    if isinstance(event_date_raw, datetime.date)
                    else datetime.date.fromisoformat(str(event_date_raw)[:10])
                )
            except ValueError:
                skipped += 1
                errors.append(f"{event_name}: invalid date {event_date_raw}")
                continue

            if holiday_type_name not in type_cache:
                holiday_type = await self._get_or_create_holiday_type(
                    session=session,
                    holiday_type=holiday_type_name,
                    unique_identifier=unique_identifier,
                )
                type_cache[holiday_type_name] = UUID(str(holiday_type["id"]))

            try:
                await self.holiday_crud.create_holiday(
                    session=session,
                    create_obj=HolidayCreateRequest(
                        holiday_name=event_name,
                        holiday_date=event_date,
                        holiday_type_id=type_cache[holiday_type_name],
                        student_class_id=student_class_id,
                    ),
                    unique_identifier=unique_identifier,
                )
                created += 1
            except HTTPException as exc:
                skipped += 1
                detail = str(exc.detail)
                if exc.status_code == 400 and "already exists" in detail.lower():
                    skipped_existing.append(
                        f"{event_name} ({event_date.isoformat()})"
                    )
                else:
                    errors.append(f"{event_name}: {detail}")

        return {
            "student_class_id": str(student_class_id),
            "created": created,
            "skipped": skipped,
            "skipped_existing": skipped_existing,
            "renamed": renamed,
            "errors": errors,
            "holiday_types_used": sorted(type_cache.keys()),
        }

    async def _get_or_create_student_class(
        self,
        *,
        session: AsyncSession,
        class_name: str,
        section_name: str,
        unique_identifier: str,
    ) -> dict[str, Any]:
        result = await self.resolve_student_class(
            session=session,
            class_name=class_name,
            section_name=section_name,
            unique_identifier=unique_identifier,
            create_if_missing=True,
        )
        assert result is not None
        return result

    async def _get_or_create_holiday_type(
        self,
        *,
        session: AsyncSession,
        holiday_type: str,
        unique_identifier: str,
    ) -> dict[str, Any]:
        existing = await self.holiday_type_crud.get_by_holiday_type_name(
            session=session, holiday_type=holiday_type
        )
        if existing:
            return {"id": existing.id, "holiday_type": existing.holiday_type}

        return await self.holiday_type_crud.create_holiday_type(
            session=session,
            create_obj=HolidayTypeCreateRequest(
                holiday_type=holiday_type,
                holiday_description=f"Auto-created from Telegram planner ingest ({holiday_type})",
            ),
            unique_identifier=unique_identifier,
        )
