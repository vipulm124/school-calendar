"""Class-scoped calendar Q&A used by Telegram query buttons."""

from __future__ import annotations

import datetime as datetime
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Holiday, HolidayType
from services.leave_day_numbering import base_event_name, has_day_suffix
from services.telegram_ingest import TelegramIngestService

_DAY_NUM_RE = re.compile(r"^(.+?)\s*-\s*DAY\s+(\d+)\s*$", re.IGNORECASE)


class CalendarQueryIntent(str, Enum):
    UPCOMING = "upcoming"
    NEXT_PTM = "next_ptm"
    LAST_PTM = "last_ptm"
    THIS_MONTH = "this_month"


QUERY_CALLBACK_PREFIX = "query:"
QUERY_CALLBACKS = {
    f"{QUERY_CALLBACK_PREFIX}upcoming": CalendarQueryIntent.UPCOMING,
    f"{QUERY_CALLBACK_PREFIX}next_ptm": CalendarQueryIntent.NEXT_PTM,
    f"{QUERY_CALLBACK_PREFIX}last_ptm": CalendarQueryIntent.LAST_PTM,
    f"{QUERY_CALLBACK_PREFIX}this_month": CalendarQueryIntent.THIS_MONTH,
}

# Parent-facing synonyms → stored holiday_type values (uppercased in DB).
_PTC_TYPE_NAMES = ("PTC", "PTM")
_HOLIDAY_TYPE_NAMES = ("HOLIDAYS", "HOLIDAY")


@dataclass(frozen=True)
class CalendarEventView:
    name: str
    event_date: datetime.date
    holiday_type: str
    end_date: Optional[datetime.date] = None


class CalendarQueryService:
    """Answer upcoming / next / last / this-month questions for a class."""

    def __init__(self) -> None:
        self.ingest = TelegramIngestService()

    async def answer(
        self,
        *,
        session: AsyncSession,
        intent: CalendarQueryIntent,
        class_name: str,
        section_name: str,
        class_label: Optional[str] = None,
        today: Optional[datetime.date] = None,
    ) -> str:
        today = today or datetime.date.today()
        label = class_label or (
            f"{class_name}-{section_name}" if section_name != "-" else class_name
        )

        student_class = await self.ingest.resolve_student_class(
            session=session,
            class_name=class_name,
            section_name=section_name,
            create_if_missing=False,
        )
        if student_class is None:
            return (
                f"No saved calendar found for {label} yet.\n"
                "Send a planner photo and tap Upload first."
            )

        student_class_id = UUID(str(student_class["id"]))

        if intent == CalendarQueryIntent.UPCOMING:
            rows = await self._list_events(
                session=session,
                student_class_id=student_class_id,
                on_or_after=today,
                type_names=_HOLIDAY_TYPE_NAMES,
                order_asc=True,
                limit=40,
            )
            views = _collapse_multi_day(rows)[:8]
            return _format_list(
                title=f"Upcoming holidays for {label}",
                events=views,
                empty=f"No upcoming holidays found for {label}.",
                today=today,
            )

        if intent == CalendarQueryIntent.NEXT_PTM:
            rows = await self._list_events(
                session=session,
                student_class_id=student_class_id,
                on_or_after=today,
                type_names=_PTC_TYPE_NAMES,
                order_asc=True,
                limit=1,
            )
            if not rows:
                return f"No upcoming PTM/PTC found for {label}."
            return _format_single(
                title=f"Next PTM for {label}",
                event=rows[0],
                today=today,
            )

        if intent == CalendarQueryIntent.LAST_PTM:
            rows = await self._list_events(
                session=session,
                student_class_id=student_class_id,
                on_or_before=today - datetime.timedelta(days=1),
                type_names=_PTC_TYPE_NAMES,
                order_asc=False,
                limit=1,
            )
            if not rows:
                return f"No past PTM/PTC found for {label}."
            return _format_single(
                title=f"Last PTM for {label}",
                event=rows[0],
                today=today,
            )

        # THIS_MONTH
        month_start = today.replace(day=1)
        if today.month == 12:
            month_end = today.replace(year=today.year + 1, month=1, day=1) - datetime.timedelta(
                days=1
            )
        else:
            month_end = today.replace(month=today.month + 1, day=1) - datetime.timedelta(days=1)
        rows = await self._list_events(
            session=session,
            student_class_id=student_class_id,
            on_or_after=month_start,
            on_or_before=month_end,
            type_names=None,
            order_asc=True,
            limit=60,
        )
        views = _collapse_multi_day(rows)
        month_label = today.strftime("%B %Y")
        return _format_list(
            title=f"{month_label} for {label}",
            events=views,
            empty=f"No holidays/PTM found for {label} in {month_label}.",
            today=today,
        )

    async def _list_events(
        self,
        *,
        session: AsyncSession,
        student_class_id: UUID,
        on_or_after: Optional[datetime.date] = None,
        on_or_before: Optional[datetime.date] = None,
        type_names: Optional[tuple[str, ...]] = None,
        order_asc: bool = True,
        limit: Optional[int] = None,
    ) -> list[CalendarEventView]:
        query = (
            select(
                Holiday.holiday_name,
                Holiday.holiday_date,
                HolidayType.holiday_type,
            )
            .join(HolidayType, Holiday.holiday_type_id == HolidayType.id)
            .where(
                Holiday.student_class_id == str(student_class_id),
                Holiday.is_deleted.is_(False),
                HolidayType.is_deleted.is_(False),
            )
        )
        if on_or_after is not None:
            query = query.where(Holiday.holiday_date >= on_or_after)
        if on_or_before is not None:
            query = query.where(Holiday.holiday_date <= on_or_before)
        if type_names:
            normalized = [name.upper() for name in type_names]
            query = query.where(func.upper(HolidayType.holiday_type).in_(normalized))

        query = query.order_by(
            Holiday.holiday_date.asc() if order_asc else Holiday.holiday_date.desc(),
            Holiday.holiday_name.asc(),
        )
        if limit is not None:
            query = query.limit(limit)

        result = await session.execute(query)
        return [
            CalendarEventView(
                name=str(row.holiday_name),
                event_date=row.holiday_date,
                holiday_type=str(row.holiday_type),
            )
            for row in result.all()
        ]


def parse_query_callback(data: str) -> Optional[CalendarQueryIntent]:
    return QUERY_CALLBACKS.get((data or "").strip().lower())


def parse_query_text(text: str) -> Optional[CalendarQueryIntent]:
    """Optional text aliases for the same query buttons."""
    normalized = re.sub(r"\s+", " ", (text or "").strip().lower())
    aliases = {
        "upcoming holidays": CalendarQueryIntent.UPCOMING,
        "upcoming holiday": CalendarQueryIntent.UPCOMING,
        "next ptm": CalendarQueryIntent.NEXT_PTM,
        "next ptc": CalendarQueryIntent.NEXT_PTM,
        "last ptm": CalendarQueryIntent.LAST_PTM,
        "last ptc": CalendarQueryIntent.LAST_PTM,
        "previous ptm": CalendarQueryIntent.LAST_PTM,
        "this month": CalendarQueryIntent.THIS_MONTH,
    }
    return aliases.get(normalized)


def _collapse_multi_day(events: list[CalendarEventView]) -> list[CalendarEventView]:
    """Collapse WINTER BREAK - DAY N runs into a single date-range row."""
    if not events:
        return []

    collapsed: list[CalendarEventView] = []
    index = 0
    while index < len(events):
        current = events[index]
        match = _DAY_NUM_RE.match(current.name)
        if not match:
            collapsed.append(current)
            index += 1
            continue

        base = base_event_name(current.name)
        start = current.event_date
        end = current.event_date
        holiday_type = current.holiday_type
        index += 1
        while index < len(events):
            nxt = events[index]
            if base_event_name(nxt.name) != base or not has_day_suffix(nxt.name):
                break
            if (nxt.event_date - end).days > 3:
                break
            end = nxt.event_date
            index += 1
        collapsed.append(
            CalendarEventView(
                name=base,
                event_date=start,
                end_date=end if end != start else None,
                holiday_type=holiday_type,
            )
        )
    return collapsed


def _format_single(
    *,
    title: str,
    event: CalendarEventView,
    today: datetime.date,
) -> str:
    when = _format_when(event.event_date, today=today)
    return f"{title}:\n{event.name} — {when}"


def _format_list(
    *,
    title: str,
    events: list[CalendarEventView],
    empty: str,
    today: datetime.date,
) -> str:
    if not events:
        return empty
    lines = [f"{title}:"]
    for event in events:
        if event.end_date and event.end_date != event.event_date:
            span = f"{_format_date(event.event_date)} to {_format_date(event.end_date)}"
            lines.append(f"• {event.name} — {span}")
        else:
            lines.append(f"• {event.name} — {_format_when(event.event_date, today=today)}")
    return "\n".join(lines)


def _format_when(event_date: datetime.date, *, today: datetime.date) -> str:
    label = _format_date(event_date)
    delta = (event_date - today).days
    if delta == 0:
        return f"{label} (today)"
    if delta == 1:
        return f"{label} (tomorrow)"
    if delta == -1:
        return f"{label} (yesterday)"
    if delta > 1:
        return f"{label} (in {delta} days)"
    return f"{label} ({abs(delta)} days ago)"


def _format_date(event_date: datetime.date) -> str:
    # Fri, 15 Feb 2027
    return event_date.strftime("%a, %d %b %Y")
