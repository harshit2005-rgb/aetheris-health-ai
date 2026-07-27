"""Datetime utility functions.

All datetimes are stored as ``TIMESTAMPTZ`` in UTC. Conversion to the user's
display timezone happens at the API/UI boundary. These utilities make that
convention easy to follow.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

#: ISO 8601 format string with explicit timezone, e.g. ``2026-08-15T09:30:00Z``.
ISO_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
ISO_FORMAT_WITH_TZ = "%Y-%m-%dT%H:%M:%S%z"
DATE_FORMAT = "%Y-%m-%d"


def utc_now() -> datetime:
    """Return the current UTC timestamp with timezone awareness.

    :returns: A timezone-aware :class:`datetime` in UTC.
    """
    return datetime.now(UTC)


def utc_today() -> date:
    """Return today's date in UTC.

    :returns: Today's :class:`date` in the UTC timezone.
    """
    return utc_now().date()


def format_iso(dt: datetime) -> str:
    """Format a datetime as an ISO 8601 string in UTC.

    :param dt: The datetime to format.
    :returns: A string like ``2026-08-15T09:30:00Z``.
    """
    return dt.astimezone(UTC).strftime(ISO_FORMAT)


def parse_iso(value: str) -> datetime:
    """Parse an ISO 8601 string into a timezone-aware datetime.

    Supports formats:
    - ``2026-08-15T09:30:00Z``
    - ``2026-08-15T09:30:00+05:30``
    - ``2026-08-15T09:30:00.000Z``

    :param value: The ISO 8601 string.
    :returns: A timezone-aware :class:`datetime`.
    :raises ValueError: If the string cannot be parsed.
    """
    # Handle trailing Z
    cleaned = value.replace("Z", "+00:00")
    # Handle optional microseconds
    try:
        return datetime.fromisoformat(cleaned)
    except ValueError:
        pass

    # Try with explicit format
    for fmt in [ISO_FORMAT_WITH_TZ, "%Y-%m-%dT%H:%M:%S.%f%z"]:
        try:
            return datetime.strptime(cleaned, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue

    raise ValueError(f"Cannot parse datetime string: {value}")


def to_timezone(dt: datetime, tz_name: str) -> datetime:
    """Convert a datetime to a different timezone.

    :param dt: The source datetime (timezone-aware).
    :param tz_name: IANA timezone name (e.g. ``Asia/Kolkata``).
    :returns: The datetime converted to the target timezone.
    """
    import zoneinfo

    tz = zoneinfo.ZoneInfo(tz_name)
    return dt.astimezone(tz)


def to_utc(dt: datetime) -> datetime:
    """Ensure a datetime is in UTC.

    If the datetime is naive, it is assumed to be UTC. If it is
    timezone-aware, it is converted to UTC.

    :param dt: The source datetime.
    :returns: A UTC timezone-aware datetime.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def start_of_day(dt: datetime | None = None, tz_name: str = "UTC") -> datetime:
    """Return the start of the day (midnight) for the given datetime.

    :param dt: The reference datetime. Defaults to now.
    :param tz_name: IANA timezone for the day boundary.
    :returns: The start of the day in UTC.
    """
    ref = dt or utc_now()
    local = to_timezone(ref, tz_name)
    start_local = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return to_utc(start_local)


def end_of_day(dt: datetime | None = None, tz_name: str = "UTC") -> datetime:
    """Return the end of the day (23:59:59.999999) for the given datetime.

    :param dt: The reference datetime. Defaults to now.
    :param tz_name: IANA timezone for the day boundary.
    :returns: The end of the day in UTC.
    """
    ref = dt or utc_now()
    return start_of_day(ref, tz_name) + timedelta(days=1) - timedelta(microseconds=1)


def date_range(
    start: date | datetime,
    end: date | datetime,
    step_days: int = 1,
) -> list[date]:
    """Generate a list of dates in a range.

    :param start: Start date (inclusive).
    :param end: End date (inclusive).
    :param step_days: Number of days between dates. Defaults to 1.
    :returns: List of :class:`date` objects in the range.
    """
    if isinstance(start, datetime):
        start = start.date()
    if isinstance(end, datetime):
        end = end.date()

    delta = end - start
    return [start + timedelta(days=i) for i in range(delta.days + 1) if i % step_days == 0]


def age(birth_date: date, reference: date | None = None) -> int:
    """Calculate the age in years from a birth date.

    :param birth_date: The date of birth.
    :param reference: The reference date. Defaults to today in UTC.
    :returns: Age in years.
    """
    ref = reference or utc_today()
    years = ref.year - birth_date.year
    if (ref.month, ref.day) < (birth_date.month, birth_date.day):
        years -= 1
    return years


__all__ = [
    "age",
    "date_range",
    "end_of_day",
    "format_iso",
    "parse_iso",
    "start_of_day",
    "to_timezone",
    "to_utc",
    "utc_now",
    "utc_today",
]
