"""Tests for continuous multi-day leave numbering across planner uploads."""

import sys
from datetime import date
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "packages" / "server" / "app"))

from services.leave_day_numbering import (
    ExistingHolidayRef,
    base_event_name,
    is_restart_header_name,
    renumber_leave_series,
)


def test_base_event_name_strips_day_suffix():
    assert base_event_name("WINTER BREAK - DAY 4") == "WINTER BREAK"
    assert base_event_name("winter break - day 11") == "WINTER BREAK"
    assert base_event_name("HOLI") == "HOLI"


def test_restart_header_detection():
    assert is_restart_header_name(
        "CHRISTMAS & COMMENCEMENT OF WINTER BREAK", "WINTER BREAK"
    )
    assert is_restart_header_name("COMMENCEMENT OF SUMMER BREAK", "SUMMER BREAK")
    assert not is_restart_header_name("WINTER BREAK - DAY 1", "WINTER BREAK")
    assert not is_restart_header_name("WINTER BREAK", "WINTER BREAK")
    assert not is_restart_header_name("HOLI", "WINTER BREAK")


def test_renumber_continues_across_dec_and_jan_uploads():
    existing = [
        ExistingHolidayRef(id="d1", holiday_date=date(2026, 12, 28), holiday_name="WINTER BREAK - DAY 1"),
        ExistingHolidayRef(id="d2", holiday_date=date(2026, 12, 29), holiday_name="WINTER BREAK - DAY 2"),
        ExistingHolidayRef(id="d3", holiday_date=date(2026, 12, 30), holiday_name="WINTER BREAK - DAY 3"),
        ExistingHolidayRef(id="d4", holiday_date=date(2026, 12, 31), holiday_name="WINTER BREAK - DAY 4"),
    ]
    new_events = [
        {"event_date": "2027-01-01", "event_name": "WINTER BREAK - DAY 1", "holiday_type": "Holidays"},
        {"event_date": "2027-01-02", "event_name": "WINTER BREAK - DAY 2", "holiday_type": "Holidays"},
        {"event_date": "2027-01-03", "event_name": "WINTER BREAK - DAY 3", "holiday_type": "Holidays"},
    ]

    renumbered, updates = renumber_leave_series(new_events=new_events, existing=existing)

    by_date = {str(event["event_date"]): event["event_name"] for event in renumbered}
    assert by_date["2027-01-01"] == "WINTER BREAK - DAY 5"
    assert by_date["2027-01-02"] == "WINTER BREAK - DAY 6"
    assert by_date["2027-01-03"] == "WINTER BREAK - DAY 7"
    assert updates == []


def test_renumber_starts_new_series_when_gap_means_leave_is_starting_again():
    existing = [
        ExistingHolidayRef(id="d1", holiday_date=date(2026, 12, 28), holiday_name="WINTER BREAK - DAY 1"),
        ExistingHolidayRef(id="d2", holiday_date=date(2026, 12, 29), holiday_name="WINTER BREAK - DAY 2"),
        ExistingHolidayRef(id="j1", holiday_date=date(2027, 1, 10), holiday_name="WINTER BREAK - DAY 15"),
    ]
    # A later, separate winter-break-looking run months afterward.
    new_events = [
        {"event_date": "2027-10-01", "event_name": "WINTER BREAK - DAY 1", "holiday_type": "Holidays"},
        {"event_date": "2027-10-02", "event_name": "WINTER BREAK - DAY 2", "holiday_type": "Holidays"},
    ]

    renumbered, updates = renumber_leave_series(new_events=new_events, existing=existing)

    by_date = {str(event["event_date"]): event["event_name"] for event in renumbered}
    assert by_date["2027-10-01"] == "WINTER BREAK - DAY 1"
    assert by_date["2027-10-02"] == "WINTER BREAK - DAY 2"
    assert updates == []


def test_renumber_starts_new_series_when_current_extract_has_commencement_header():
    existing = [
        ExistingHolidayRef(id="old1", holiday_date=date(2026, 6, 1), holiday_name="SUMMER BREAK - DAY 1"),
        ExistingHolidayRef(id="old2", holiday_date=date(2026, 6, 2), holiday_name="SUMMER BREAK - DAY 2"),
    ]
    new_events = [
        {
            "event_date": "2027-05-15",
            "event_name": "COMMENCEMENT OF SUMMER BREAK",
            "holiday_type": "Holidays",
        },
        {"event_date": "2027-05-16", "event_name": "SUMMER BREAK - DAY 1", "holiday_type": "Holidays"},
        {"event_date": "2027-05-17", "event_name": "SUMMER BREAK - DAY 2", "holiday_type": "Holidays"},
    ]

    renumbered, updates = renumber_leave_series(new_events=new_events, existing=existing)

    by_date = {str(event["event_date"]): event["event_name"] for event in renumbered}
    assert by_date["2027-05-15"] == "COMMENCEMENT OF SUMMER BREAK"
    assert by_date["2027-05-16"] == "SUMMER BREAK - DAY 1"
    assert by_date["2027-05-17"] == "SUMMER BREAK - DAY 2"
    assert updates == []


def test_unrelated_upload_does_not_rewrite_previous_leave_series():
    existing = [
        ExistingHolidayRef(id="d1", holiday_date=date(2026, 12, 28), holiday_name="WINTER BREAK - DAY 1"),
        ExistingHolidayRef(id="j1", holiday_date=date(2027, 1, 1), holiday_name="WINTER BREAK - DAY 1"),
    ]
    new_events = [
        {"event_date": "2027-03-04", "event_name": "HOLI", "holiday_type": "Holidays"},
    ]

    renumbered, updates = renumber_leave_series(new_events=new_events, existing=existing)

    assert renumbered[0]["event_name"] == "HOLI"
    assert updates == []


def test_renumber_does_not_merge_unrelated_same_label_without_day_suffix():
    existing = [
        ExistingHolidayRef(id="a", holiday_date=date(2026, 11, 10), holiday_name="OPEN HOUSE"),
    ]
    new_events = [
        {"event_date": "2027-02-15", "event_name": "OPEN HOUSE", "holiday_type": "PTC"},
    ]

    renumbered, updates = renumber_leave_series(new_events=new_events, existing=existing)

    assert renumbered[0]["event_name"] == "OPEN HOUSE"
    assert updates == []


def test_renumber_keeps_continuous_days_when_second_image_is_reuploaded():
    """Re-extracting Jan after Dec+Jan are saved must not restart at DAY 1."""
    existing = [
        ExistingHolidayRef(id="d1", holiday_date=date(2026, 12, 28), holiday_name="WINTER BREAK - DAY 1"),
        ExistingHolidayRef(id="d2", holiday_date=date(2026, 12, 29), holiday_name="WINTER BREAK - DAY 2"),
        ExistingHolidayRef(id="d3", holiday_date=date(2026, 12, 30), holiday_name="WINTER BREAK - DAY 3"),
        ExistingHolidayRef(id="d4", holiday_date=date(2026, 12, 31), holiday_name="WINTER BREAK - DAY 4"),
        ExistingHolidayRef(id="j1", holiday_date=date(2027, 1, 1), holiday_name="WINTER BREAK - DAY 5"),
        ExistingHolidayRef(id="j2", holiday_date=date(2027, 1, 2), holiday_name="WINTER BREAK - DAY 6"),
        ExistingHolidayRef(id="j3", holiday_date=date(2027, 1, 3), holiday_name="WINTER BREAK - DAY 7"),
    ]
    new_events = [
        {"event_date": "2027-01-01", "event_name": "WINTER BREAK - DAY 1", "holiday_type": "Holidays"},
        {"event_date": "2027-01-02", "event_name": "WINTER BREAK - DAY 2", "holiday_type": "Holidays"},
        {"event_date": "2027-01-03", "event_name": "WINTER BREAK - DAY 3", "holiday_type": "Holidays"},
    ]

    renumbered, updates = renumber_leave_series(new_events=new_events, existing=existing)

    by_date = {str(event["event_date"]): event["event_name"] for event in renumbered}
    assert by_date["2027-01-01"] == "WINTER BREAK - DAY 5"
    assert by_date["2027-01-02"] == "WINTER BREAK - DAY 6"
    assert by_date["2027-01-03"] == "WINTER BREAK - DAY 7"
    assert updates == []


def test_renumber_fixes_preview_and_db_when_jan_was_saved_as_day_1():
    existing = [
        ExistingHolidayRef(id="d1", holiday_date=date(2026, 12, 28), holiday_name="WINTER BREAK - DAY 1"),
        ExistingHolidayRef(id="d2", holiday_date=date(2026, 12, 29), holiday_name="WINTER BREAK - DAY 2"),
        ExistingHolidayRef(id="j1", holiday_date=date(2027, 1, 1), holiday_name="WINTER BREAK - DAY 1"),
        ExistingHolidayRef(id="j2", holiday_date=date(2027, 1, 2), holiday_name="WINTER BREAK - DAY 2"),
    ]
    new_events = [
        {"event_date": "2027-01-01", "event_name": "WINTER BREAK - DAY 1", "holiday_type": "Holidays"},
        {"event_date": "2027-01-02", "event_name": "WINTER BREAK - DAY 2", "holiday_type": "Holidays"},
    ]

    renumbered, updates = renumber_leave_series(new_events=new_events, existing=existing)

    by_date = {str(event["event_date"]): event["event_name"] for event in renumbered}
    assert by_date["2027-01-01"] == "WINTER BREAK - DAY 3"
    assert by_date["2027-01-02"] == "WINTER BREAK - DAY 4"
    by_id = {update.id: update.holiday_name for update in updates}
    assert by_id["j1"] == "WINTER BREAK - DAY 3"
    assert by_id["j2"] == "WINTER BREAK - DAY 4"


def test_christmas_commencement_on_prior_page_does_not_block_jan_continuation():
    """A commencement header dated before the saved run must not force a restart."""
    existing = [
        ExistingHolidayRef(id="d1", holiday_date=date(2026, 12, 28), holiday_name="WINTER BREAK - DAY 1"),
        ExistingHolidayRef(id="d2", holiday_date=date(2026, 12, 29), holiday_name="WINTER BREAK - DAY 2"),
        ExistingHolidayRef(id="d3", holiday_date=date(2026, 12, 30), holiday_name="WINTER BREAK - DAY 3"),
        ExistingHolidayRef(id="d4", holiday_date=date(2026, 12, 31), holiday_name="WINTER BREAK - DAY 4"),
    ]
    new_events = [
        {
            "event_date": "2026-12-25",
            "event_name": "CHRISTMAS & COMMENCEMENT OF WINTER BREAK",
            "holiday_type": "Holidays",
        },
        {"event_date": "2027-01-01", "event_name": "WINTER BREAK - DAY 1", "holiday_type": "Holidays"},
        {"event_date": "2027-01-02", "event_name": "WINTER BREAK - DAY 2", "holiday_type": "Holidays"},
    ]

    renumbered, updates = renumber_leave_series(new_events=new_events, existing=existing)

    by_date = {str(event["event_date"]): event["event_name"] for event in renumbered}
    assert by_date["2026-12-25"] == "CHRISTMAS & COMMENCEMENT OF WINTER BREAK"
    assert by_date["2027-01-01"] == "WINTER BREAK - DAY 5"
    assert by_date["2027-01-02"] == "WINTER BREAK - DAY 6"
    assert updates == []
