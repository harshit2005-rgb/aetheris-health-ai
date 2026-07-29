"""Date and time helpers.

All datetimes in Aetheris are timezone-aware UTC in storage and on the wire
(``docs/06-API_STANDARDS.md`` §17). Naive datetimes never cross a layer
boundary.

Usage::

    from app.utils.datetime import age_in_years, utc_now

    utc_now()                                  # aware datetime in UTC
    age_in_years(date(1988, 3, 14))            # 38
"""

from __future__ import annotations

from datetime import UTC, date, datetime

__all__ = ["age_in_years", "subtract_years", "utc_now", "utc_today"]


def utc_now() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(UTC)


def utc_today() -> date:
    """Return today's date in UTC.

    Used for date-of-birth validation so the boundary does not shift with the
    server's local timezone.
    """
    return datetime.now(UTC).date()


def subtract_years(value: date, years: int) -> date:
    """Return the same calendar date ``years`` earlier.

    29 February has no counterpart in a non-leap year; it clamps to 28
    February, which is the convention every civil-age calculation uses.

    :param value: The starting date.
    :param years: Number of years to subtract. Must not be negative.
    :returns: The shifted date.
    :raises ValueError: If ``years`` is negative.
    """
    if years < 0:
        msg = "years must not be negative."
        raise ValueError(msg)
    try:
        return value.replace(year=value.year - years)
    except ValueError:
        # Only reachable for 29 February in a target year that is not a leap year.
        return value.replace(year=value.year - years, day=28)


def age_in_years(date_of_birth: date, *, as_of: date | None = None) -> int:
    """Compute a whole-year age from a date of birth.

    Birthdays that have not yet occurred in the reference year do not count, so
    someone born on 31 December is 0 for their entire first calendar year.

    :param date_of_birth: The date of birth.
    :param as_of: Reference date. Defaults to today in UTC.
    :returns: Age in completed years. Negative if ``date_of_birth`` is in the
        future — callers that reject future dates should do so explicitly
        rather than relying on this returning zero.
    """
    reference = as_of if as_of is not None else utc_today()
    years = reference.year - date_of_birth.year
    # Subtract a year when the birthday has not been reached in the reference
    # year. Comparing (month, day) tuples handles 29 February without a
    # special case: 29 Feb > 28 Feb, so a leap-day birthday counts on 1 March.
    if (reference.month, reference.day) < (date_of_birth.month, date_of_birth.day):
        years -= 1
    return years
