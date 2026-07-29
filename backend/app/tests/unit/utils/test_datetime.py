"""Tests for :mod:`app.utils.datetime`."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from app.utils.datetime import (
    age,
    date_range,
    end_of_day,
    format_iso,
    parse_iso,
    start_of_day,
    subtract_years,
    to_timezone,
    to_utc,
    utc_now,
    utc_today,
)


class TestUtcNow:
    def test_returns_timezone_aware_datetime(self) -> None:
        now = utc_now()
        assert now.tzinfo is not None
        assert now.tzinfo == UTC

    def test_returns_utc(self) -> None:
        now = utc_now()
        assert now.utcoffset() == timedelta(0)


class TestUtcToday:
    def test_returns_date(self) -> None:
        today = utc_today()
        assert isinstance(today, date)


class TestFormatIso:
    def test_returns_utc_string(self) -> None:
        dt = datetime(2026, 7, 27, 10, 30, 0, tzinfo=UTC)
        assert format_iso(dt) == "2026-07-27T10:30:00Z"

    def test_converts_to_utc(self) -> None:
        from zoneinfo import ZoneInfo

        dt = datetime(2026, 7, 27, 16, 0, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
        assert format_iso(dt) == "2026-07-27T10:30:00Z"


class TestParseIso:
    def test_parse_z_suffix(self) -> None:
        dt = parse_iso("2026-07-27T10:30:00Z")
        assert dt == datetime(2026, 7, 27, 10, 30, 0, tzinfo=UTC)

    def test_parse_with_offset(self) -> None:
        dt = parse_iso("2026-07-27T16:00:00+05:30")
        assert dt.hour == 16
        assert dt.minute == 0
        assert dt.utcoffset() == timedelta(hours=5, minutes=30)

    def test_raises_on_invalid(self) -> None:
        with pytest.raises(ValueError):
            parse_iso("not-a-date")


class TestAge:
    def test_age_exact_birthday(self) -> None:
        birth = date(1990, 7, 27)
        ref = date(2026, 7, 27)
        assert age(birth, ref) == 36

    def test_age_before_birthday(self) -> None:
        birth = date(1990, 8, 15)
        ref = date(2026, 7, 27)
        assert age(birth, ref) == 35

    def test_age_after_birthday(self) -> None:
        birth = date(1990, 1, 1)
        ref = date(2026, 7, 27)
        assert age(birth, ref) == 36


class TestDateRange:
    def test_single_day(self) -> None:
        start = date(2026, 7, 27)
        end = date(2026, 7, 27)
        assert date_range(start, end) == [start]

    def test_multiple_days(self) -> None:
        start = date(2026, 7, 27)
        end = date(2026, 7, 30)
        assert date_range(start, end) == [
            date(2026, 7, 27),
            date(2026, 7, 28),
            date(2026, 7, 29),
            date(2026, 7, 30),
        ]


class TestStartOfDay:
    def test_start_of_day_utc(self) -> None:
        dt = datetime(2026, 7, 27, 14, 30, 0, tzinfo=UTC)
        start = start_of_day(dt)
        assert start == datetime(2026, 7, 27, 0, 0, 0, tzinfo=UTC)


class TestEndOfDay:
    def test_end_of_day_utc(self) -> None:
        dt = datetime(2026, 7, 27, 14, 30, 0, tzinfo=UTC)
        end = end_of_day(dt)
        assert end > dt
        assert end.tzinfo == UTC


class TestToTimezone:
    def test_converts_to_ist(self) -> None:
        dt = datetime(2026, 7, 27, 10, 30, 0, tzinfo=UTC)
        ist = to_timezone(dt, "Asia/Kolkata")
        assert ist.hour == 16
        assert ist.minute == 0

    def test_roundtrip(self) -> None:
        dt = datetime(2026, 7, 27, 10, 30, 0, tzinfo=UTC)
        ist = to_timezone(dt, "Asia/Kolkata")
        back = to_timezone(ist, "UTC")
        assert back == dt


class TestToUtc:
    def test_naive_assumed_utc(self) -> None:
        dt = datetime(2026, 7, 27, 10, 30, 0)
        result = to_utc(dt)
        assert result.tzinfo == UTC
        assert result.hour == 10

    def test_aware_converted(self) -> None:
        from zoneinfo import ZoneInfo

        dt = datetime(2026, 7, 27, 16, 0, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
        result = to_utc(dt)
        assert result == datetime(2026, 7, 27, 10, 30, 0, tzinfo=UTC)


class TestSubtractYears:
    """Calendar-year subtraction — the inverse of :func:`age`."""

    def test_subtract_years_returns_the_same_day_and_month(self) -> None:
        assert subtract_years(date(2026, 7, 27), 40) == date(1986, 7, 27)

    def test_subtract_years_by_zero_is_the_identity(self) -> None:
        assert subtract_years(date(2026, 7, 27), 0) == date(2026, 7, 27)

    def test_subtract_years_clamps_a_leap_day_to_the_28th(self) -> None:
        # 2023 is not a leap year, so 29 February does not exist there.
        assert subtract_years(date(2024, 2, 29), 1) == date(2023, 2, 28)

    def test_subtract_years_rejects_a_negative_count(self) -> None:
        with pytest.raises(ValueError, match="must not be negative"):
            subtract_years(date(2026, 7, 27), -1)

    def test_subtract_years_inverts_age_at_the_boundary(self) -> None:
        # Someone born exactly N years ago today is N — this is the identity an
        # age-range filter relies on when converting bounds to birth dates.
        today = date(2026, 7, 27)
        assert age(subtract_years(today, 40), today) == 40
