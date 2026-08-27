"""Unit tests for :func:`~app.services.doctor_service.generate_slots`.

The slot algorithm is a pure function, so these need no database, no fixtures,
and no clock. That is the whole reason it was factored out of the service:
module spec §16 asks for the generation algorithm to be tested against
availability, leaves and bookings, and §14 asks specifically for a DST
transition — none of which is pleasant to set up through a repository.

Times in assertions are local wall-clock in the zone under test, because that
is how a clinic reads its own schedule.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import pytest

from app.core.exceptions import ValidationError
from app.models.doctor import SlotStatus
from app.services.doctor_service import BookedInterval, generate_slots

if TYPE_CHECKING:
    from app.schemas.doctor import SlotResponse

IST = "Asia/Kolkata"
LONDON = "Europe/London"

#: A plain Monday in a zone with no DST, for the non-edge-case tests.
ORDINARY_DAY = date(2026, 8, 17)


def _local(zone_name: str, on: date, hour: int, minute: int = 0) -> datetime:
    """Build a local wall-clock instant in ``zone_name``."""
    return datetime.combine(on, time(hour, minute), tzinfo=ZoneInfo(zone_name))


def _starts(slots: list[SlotResponse]) -> list[str]:
    """Return each slot's local start as ``HH:MM``, for readable assertions."""
    return [slot.start.strftime("%H:%M") for slot in slots]


def _statuses(slots: list[SlotResponse]) -> list[str]:
    """Return each slot's status value."""
    return [slot.status.value for slot in slots]


class TestBasicGeneration:
    """Windows in, slots out."""

    def test_window_divides_into_slots(self) -> None:
        slots = generate_slots(
            target_date=ORDINARY_DAY,
            availability=[(time(9), time(10), 15)],
            leaves=[],
            booked=[],
            timezone=IST,
        )

        assert _starts(slots) == ["09:00", "09:15", "09:30", "09:45"]
        assert set(_statuses(slots)) == {"available"}

    def test_no_availability_yields_no_slots(self) -> None:
        """A day the doctor does not work is empty, not an error."""
        assert (
            generate_slots(
                target_date=ORDINARY_DAY, availability=[], leaves=[], booked=[], timezone=IST
            )
            == []
        )

    def test_trailing_partial_slot_is_dropped(self) -> None:
        """A remainder shorter than the slot duration is not bookable.

        09:00-09:50 at 20 minutes fits two slots; the last 10 minutes cannot
        hold an appointment and must not be offered as if it could.
        """
        slots = generate_slots(
            target_date=ORDINARY_DAY,
            availability=[(time(9), time(9, 50), 20)],
            leaves=[],
            booked=[],
            timezone=IST,
        )

        assert _starts(slots) == ["09:00", "09:20"]

    def test_multiple_windows_are_merged_in_order(self) -> None:
        """Two windows in one day produce one chronological list."""
        slots = generate_slots(
            target_date=ORDINARY_DAY,
            availability=[(time(14), time(15), 30), (time(9), time(10), 30)],
            leaves=[],
            booked=[],
            timezone=IST,
        )

        assert _starts(slots) == ["09:00", "09:30", "14:00", "14:30"]

    def test_window_shorter_than_one_slot_yields_nothing(self) -> None:
        """A 10-minute window cannot host a 15-minute slot."""
        slots = generate_slots(
            target_date=ORDINARY_DAY,
            availability=[(time(9), time(9, 10), 15)],
            leaves=[],
            booked=[],
            timezone=IST,
        )

        assert slots == []

    def test_slots_carry_the_requested_zone(self) -> None:
        """Slot times come back in the hospital's zone, not UTC."""
        slots = generate_slots(
            target_date=ORDINARY_DAY,
            availability=[(time(9), time(9, 15), 15)],
            leaves=[],
            booked=[],
            timezone=IST,
        )

        assert slots[0].start.utcoffset() == ZoneInfo(IST).utcoffset(slots[0].start)


class TestLeaves:
    """Leave intervals subtract from availability (module spec §4, rule 3)."""

    def test_slot_inside_a_leave_is_on_leave(self) -> None:
        leave = (_local(IST, ORDINARY_DAY, 9, 15), _local(IST, ORDINARY_DAY, 9, 30))

        slots = generate_slots(
            target_date=ORDINARY_DAY,
            availability=[(time(9), time(10), 15)],
            leaves=[leave],
            booked=[],
            timezone=IST,
        )

        assert _statuses(slots) == ["available", "on_leave", "available", "available"]

    def test_leave_covering_the_whole_window_marks_every_slot(self) -> None:
        leave = (_local(IST, ORDINARY_DAY, 8), _local(IST, ORDINARY_DAY, 18))

        slots = generate_slots(
            target_date=ORDINARY_DAY,
            availability=[(time(9), time(10), 15)],
            leaves=[leave],
            booked=[],
            timezone=IST,
        )

        assert set(_statuses(slots)) == {"on_leave"}
        assert len(slots) == 4

    def test_touching_leave_does_not_block_the_slot(self) -> None:
        """Intervals are half-open, so a leave starting at 09:15 leaves
        09:00-09:15 bookable. Getting this wrong silently loses a slot at the
        edge of every leave."""
        leave = (_local(IST, ORDINARY_DAY, 9, 15), _local(IST, ORDINARY_DAY, 10))

        slots = generate_slots(
            target_date=ORDINARY_DAY,
            availability=[(time(9), time(9, 15), 15)],
            leaves=[leave],
            booked=[],
            timezone=IST,
        )

        assert _statuses(slots) == ["available"]

    def test_partial_overlap_still_marks_the_slot(self) -> None:
        """A leave covering one minute of a slot still makes it unbookable."""
        leave = (_local(IST, ORDINARY_DAY, 9, 14), _local(IST, ORDINARY_DAY, 9, 16))

        slots = generate_slots(
            target_date=ORDINARY_DAY,
            availability=[(time(9), time(9, 30), 15)],
            leaves=[leave],
            booked=[],
            timezone=IST,
        )

        assert _statuses(slots) == ["on_leave", "on_leave"]


class TestBookings:
    """Booked appointments subtract from availability (module spec §4, rule 4)."""

    def test_booked_slot_reports_its_appointment(self) -> None:
        appointment_id = uuid.uuid4()
        booked = [
            BookedInterval(
                _local(IST, ORDINARY_DAY, 9, 30),
                _local(IST, ORDINARY_DAY, 9, 45),
                appointment_id,
            )
        ]

        slots = generate_slots(
            target_date=ORDINARY_DAY,
            availability=[(time(9), time(10), 15)],
            leaves=[],
            booked=booked,
            timezone=IST,
        )

        assert _statuses(slots) == ["available", "available", "booked", "available"]
        assert slots[2].appointment_id == appointment_id
        # Only the booked slot carries an id.
        assert [s.appointment_id for s in slots if s.appointment_id] == [appointment_id]

    def test_leave_wins_over_a_booking(self) -> None:
        """A doctor on leave cannot see a patient even if the slot is booked.

        Reporting ``on_leave`` rather than ``booked`` is what tells reception
        the appointment needs reassigning (module spec §5.3 step 3).
        """
        overlap_start = _local(IST, ORDINARY_DAY, 9, 0)
        overlap_end = _local(IST, ORDINARY_DAY, 9, 15)

        slots = generate_slots(
            target_date=ORDINARY_DAY,
            availability=[(time(9), time(9, 15), 15)],
            leaves=[(overlap_start, overlap_end)],
            booked=[BookedInterval(overlap_start, overlap_end, uuid.uuid4())],
            timezone=IST,
        )

        assert _statuses(slots) == ["on_leave"]
        assert slots[0].appointment_id is None


class TestDaylightSaving:
    """Module spec §14: availability is wall-clock and resolves in the hospital zone."""

    def test_spring_forward_drops_the_hour_that_does_not_exist(self) -> None:
        """On 2026-03-29 London goes 01:00 GMT straight to 02:00 BST.

        A nominal 01:00-02:00 slot spans zero real seconds, so it must not be
        offered — booking into a minute that never happens is worse than
        showing one slot fewer.
        """
        slots = generate_slots(
            target_date=date(2026, 3, 29),
            availability=[(time(0), time(4), 60)],
            leaves=[],
            booked=[],
            timezone=LONDON,
        )

        assert _starts(slots) == ["00:00", "02:00", "03:00"]
        # Every surviving slot is a real hour.
        for slot in slots:
            elapsed = slot.end.astimezone(ZoneInfo("UTC")) - slot.start.astimezone(ZoneInfo("UTC"))
            assert elapsed.total_seconds() == 3600

    def test_fall_back_keeps_the_repeated_hour_as_one_slot(self) -> None:
        """On 2026-10-25 London repeats 01:00-02:00.

        MVP behaviour: the ambiguous hour is emitted as a single slot spanning
        both passes, so it reads as 120 real minutes. Deliberate — it never
        double-books, it only leaves the doctor slack. Pinned here so that
        splitting it later is a visible, intentional change rather than an
        accidental one.
        """
        slots = generate_slots(
            target_date=date(2026, 10, 25),
            availability=[(time(0), time(4), 60)],
            leaves=[],
            booked=[],
            timezone=LONDON,
        )

        assert _starts(slots) == ["00:00", "01:00", "02:00", "03:00"]

        utc = ZoneInfo("UTC")
        durations = [
            (s.end.astimezone(utc) - s.start.astimezone(utc)).total_seconds() / 60 for s in slots
        ]
        assert durations == [60, 120, 60, 60]

    def test_ordinary_day_in_a_dst_zone_is_unaffected(self) -> None:
        """Away from a transition, a DST zone behaves like any other."""
        slots = generate_slots(
            target_date=date(2026, 6, 15),
            availability=[(time(9), time(12), 60)],
            leaves=[],
            booked=[],
            timezone=LONDON,
        )

        assert _starts(slots) == ["09:00", "10:00", "11:00"]


class TestInvalidInput:
    """Failure modes."""

    def test_unknown_timezone_is_a_validation_error(self) -> None:
        """A bad hospital timezone must surface as a 422, not a 500."""
        with pytest.raises(ValidationError):
            generate_slots(
                target_date=ORDINARY_DAY,
                availability=[(time(9), time(10), 15)],
                leaves=[],
                booked=[],
                timezone="Mars/Olympus_Mons",
            )


class TestSlotStatusEnum:
    """The status vocabulary the API promises (module spec §9)."""

    def test_exactly_three_statuses_exist(self) -> None:
        assert {s.value for s in SlotStatus} == {"available", "booked", "on_leave"}
