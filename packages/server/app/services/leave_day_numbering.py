"""Continuous DAY numbering for multi-day leaves across planner uploads."""

from __future__ import annotations

import datetime as datetime
import re
from dataclasses import dataclass
from typing import Any, Optional

_DAY_SUFFIX_RE = re.compile(r"\s*-\s*DAY\s+\d+\s*$", re.IGNORECASE)

# Allow Fri→Mon style gaps when a leave spans a weekend between planner pages.
_DEFAULT_MAX_GAP_DAYS = 3

_RESTART_MARKERS = (
    "COMMENCEMENT",
    "COMMENCES",
    "BEGINNING OF",
    "START OF",
    "STARTS",
)


def base_event_name(name: str) -> str:
    """Strip a trailing ' - DAY N' suffix and normalize."""
    return _DAY_SUFFIX_RE.sub("", (name or "")).strip().upper()


def has_day_suffix(name: str) -> bool:
    return bool(_DAY_SUFFIX_RE.search(name or ""))


def _as_date(value: Any) -> Optional[datetime.date]:
    if isinstance(value, datetime.date) and not isinstance(value, datetime.datetime):
        return value
    if isinstance(value, datetime.datetime):
        return value.date()
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


@dataclass(frozen=True)
class ExistingHolidayRef:
    id: Any
    holiday_date: datetime.date
    holiday_name: str


@dataclass(frozen=True)
class HolidayNameUpdate:
    id: Any
    holiday_name: str


def is_restart_header_name(name: str, base: str) -> bool:
    """
    True for labels like 'CHRISTMAS & COMMENCEMENT OF WINTER BREAK'
    that mark the start of a leave, not a numbered leave day.
    """
    normalized = (name or "").strip().upper()
    base_name = base.strip().upper()
    if not normalized or not base_name:
        return False
    if base_name not in normalized:
        return False
    if normalized == base_name or has_day_suffix(normalized):
        return False
    return any(marker in normalized for marker in _RESTART_MARKERS)


def dates_are_continuous(
    earlier: datetime.date,
    later: datetime.date,
    *,
    max_gap_days: int = _DEFAULT_MAX_GAP_DAYS,
) -> bool:
    """True when later continues earlier (overlap or small calendar gap)."""
    if later <= earlier:
        return True
    return (later - earlier).days <= max_gap_days


def renumber_leave_series(
    *,
    new_events: list[dict[str, Any]],
    existing: list[ExistingHolidayRef],
    max_gap_days: int = _DEFAULT_MAX_GAP_DAYS,
) -> tuple[list[dict[str, Any]], list[HolidayNameUpdate]]:
    """
    Assign `BASE - DAY N` names for multi-day leaves.

    Continuation rules (per leave base name):
    1. Look for the same leave already saved for the class.
    2. If that prior run is date-continuous with this extract, and this extract does
       not introduce a new commencement/start header after that prior run, continue
       DAY numbering from the previous upload.
    3. Otherwise treat this extract as a new leave series starting at DAY 1.
    """
    updated_events = [dict(event) for event in new_events]

    existing_by_base: dict[str, list[dict[str, Any]]] = {}
    for holiday in existing:
        base = base_event_name(holiday.holiday_name)
        if not base:
            continue
        existing_by_base.setdefault(base, []).append(
            {
                "kind": "existing",
                "id": holiday.id,
                "date": holiday.holiday_date,
                "name": holiday.holiday_name,
            }
        )

    new_by_base: dict[str, list[dict[str, Any]]] = {}
    for index, event in enumerate(updated_events):
        name = str(event.get("event_name") or "").strip()
        event_date = _as_date(event.get("event_date"))
        base = base_event_name(name)
        if not base or event_date is None:
            continue
        # Commencement/header rows are not leave days to number.
        if is_restart_header_name(name, base):
            continue
        new_by_base.setdefault(base, []).append(
            {
                "kind": "new",
                "index": index,
                "date": event_date,
                "name": name,
            }
        )

    name_updates: list[HolidayNameUpdate] = []

    for base, new_items in new_by_base.items():
        existing_items = existing_by_base.get(base, [])
        continue_previous = _should_continue_previous_series(
            base=base,
            existing_items=existing_items,
            new_items=new_items,
            all_new_events=updated_events,
            max_gap_days=max_gap_days,
        )

        if continue_previous:
            items = _existing_contiguous_with_new(
                existing_items=existing_items,
                new_items=new_items,
                max_gap_days=max_gap_days,
            ) + list(new_items)
        else:
            if not _should_number_new_batch(new_items):
                continue
            items = list(new_items)

        dates = sorted({item["date"] for item in items})
        if len(dates) <= 1 and not continue_previous:
            continue

        name_by_date = {
            event_date: f"{base} - DAY {day_number}"
            for day_number, event_date in enumerate(dates, start=1)
        }

        for item in items:
            numbered_name = name_by_date[item["date"]]
            if item["kind"] == "existing":
                if str(item["name"]).strip().upper() != numbered_name:
                    name_updates.append(
                        HolidayNameUpdate(id=item["id"], holiday_name=numbered_name)
                    )
            else:
                updated_events[item["index"]]["event_name"] = numbered_name

    return updated_events, name_updates


def _should_continue_previous_series(
    *,
    base: str,
    existing_items: list[dict[str, Any]],
    new_items: list[dict[str, Any]],
    all_new_events: list[dict[str, Any]],
    max_gap_days: int,
) -> bool:
    if not existing_items or not new_items:
        return False

    last_existing = max(item["date"] for item in existing_items)
    first_new = min(item["date"] for item in new_items)

    if _has_restart_header_after_previous(
        base=base,
        all_new_events=all_new_events,
        last_existing_date=last_existing,
        first_new_leave_date=first_new,
    ):
        return False

    # Re-upload / overlap of dates already in DB counts as the same run.
    if first_new <= last_existing:
        return True

    return dates_are_continuous(
        last_existing, first_new, max_gap_days=max_gap_days
    )


def _has_restart_header_after_previous(
    *,
    base: str,
    all_new_events: list[dict[str, Any]],
    last_existing_date: datetime.date,
    first_new_leave_date: datetime.date,
) -> bool:
    """
    Detect a new commencement/start header for this leave that belongs to the
    current extract (after the previously saved run ended).
    """
    for event in all_new_events:
        name = str(event.get("event_name") or "").strip()
        event_date = _as_date(event.get("event_date"))
        if event_date is None or not is_restart_header_name(name, base):
            continue
        if event_date <= last_existing_date:
            # Header is from the earlier period (or already-covered dates).
            continue
        if event_date <= first_new_leave_date and (
            first_new_leave_date - event_date
        ).days <= 7:
            return True
    return False


def _existing_contiguous_with_new(
    *,
    existing_items: list[dict[str, Any]],
    new_items: list[dict[str, Any]],
    max_gap_days: int,
) -> list[dict[str, Any]]:
    """Keep only the prior leave days that sit in the same contiguous run as new days."""
    new_dates = {item["date"] for item in new_items}
    existing_dates = sorted({item["date"] for item in existing_items})
    if not existing_dates:
        return []

    all_dates = sorted(set(existing_dates) | new_dates)
    clusters: list[list[datetime.date]] = []
    current = [all_dates[0]]
    for event_date in all_dates[1:]:
        if (event_date - current[-1]).days <= max_gap_days:
            current.append(event_date)
        else:
            clusters.append(current)
            current = [event_date]
    clusters.append(current)

    merge_dates: set[datetime.date] = set()
    for cluster in clusters:
        if new_dates.intersection(cluster):
            merge_dates.update(cluster)

    return [item for item in existing_items if item["date"] in merge_dates]


def _should_number_new_batch(new_items: list[dict[str, Any]]) -> bool:
    dates = {item["date"] for item in new_items}
    if len(dates) <= 1:
        return False
    if any(has_day_suffix(str(item.get("name") or "")) for item in new_items):
        return True
    return len(new_items) > 1
