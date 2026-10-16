"""Phone number utilities.

Validates and formats phone numbers in E.164 format where possible.
Supports Indian mobile numbers by default with extendable country rules.
"""

from __future__ import annotations

import re
from typing import Final

#: Basic E.164 pattern: ``+`` followed by country code and number.
E164_PATTERN: Final[re.Pattern[str]] = re.compile(r"^\+[1-9]\d{6,14}$")

#: Indian mobile number pattern (after +91).
IN_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[6-9]\d{9}$")

#: Indian landline pattern (STD code + number).
IN_LANDLINE_PATTERN: Final[re.Pattern[str]] = re.compile(r"^0\d{2,4}\d{6,8}$")

#: Allowed characters in a raw phone input.
_DIGITS_ONLY: Final[re.Pattern[str]] = re.compile(r"[^\d+]")


def strip_non_digits(value: str) -> str:
    """Remove non-digit characters from a phone number string.

    :param value: The raw phone input.
    :returns: Digits only, preserving a leading ``+``.
    """
    return _DIGITS_ONLY.sub("", value)


def is_e164(value: str) -> bool:
    """Check if a phone number is in valid E.164 format.

    :param value: The phone number string.
    :returns: ``True`` if the number is valid E.164.
    """
    return bool(E164_PATTERN.match(strip_non_digits(value)))


def normalize(value: str) -> str:
    """Normalize a phone number to E.164 format.

    Handles common Indian formats:
    - ``9876543210`` → ``+919876543210``
    - ``+919876543210`` → ``+919876543210``
    - ``09876543210`` → ``+919876543210`` (if it matches Indian mobile)
    - ``022-12345678`` → ``02212345678`` (landline, not E.164 by default)

    :param value: The raw phone input.
    :returns: The normalized E.164 string, or the cleaned input if not recognized.
    """
    cleaned = strip_non_digits(value)

    if cleaned.startswith("+"):
        return cleaned

    # Indian mobile: 10 digits starting with 6-9
    if IN_PATTERN.match(cleaned):
        return f"+91{cleaned}"

    # Indian mobile with leading 0
    if cleaned.startswith("0") and IN_PATTERN.match(cleaned[1:]):
        return f"+91{cleaned[1:]}"

    # Landline: keep as-is if it's a known pattern
    if IN_LANDLINE_PATTERN.match(cleaned):
        return cleaned

    # Unknown format — return cleaned digits
    return cleaned


def mask(value: str, visible_digits: int = 4) -> str:
    """Mask a phone number for display, showing only the last N digits.

    :param value: The phone number.
    :param visible_digits: Number of trailing digits to reveal.
    :returns: The masked number (e.g. ``+91******3210``).
    """
    cleaned = strip_non_digits(value)
    if len(cleaned) <= visible_digits:
        return cleaned

    prefix = cleaned[:-visible_digits]
    suffix = cleaned[-visible_digits:]
    return f"{'*' * len(prefix)}{suffix}"


__all__ = [
    "is_e164",
    "mask",
    "normalize",
    "strip_non_digits",
]
