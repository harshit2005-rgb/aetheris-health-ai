"""E.164 phone number helpers.

``docs/modules/03-patient-management.md`` §11 requires patient phone numbers to
be E.164 or blank. E.164 is the international format: a leading ``+``, a country
code, and up to 15 digits in total, with no separators.

Usage::

    from app.utils.phone import is_e164, normalize_phone

    normalize_phone(" +91 98123-45678 ")   # '+919812345678'
    is_e164("+919812345678")               # True
"""

from __future__ import annotations

import re

__all__ = ["E164_PATTERN", "PHONE_MAX_LENGTH", "is_e164", "normalize_phone"]

#: E.164: ``+`` then a non-zero country-code digit, then 6–14 more digits.
#:
#: The standard caps the total at 15 digits but sets no minimum. 7 is used
#: here because the shortest numbers actually in service (e.g. Niue, +683 nnnn)
#: are 7 digits including the country code — a stricter floor would reject real
#: patients, which is a worse failure than accepting a typo.
E164_PATTERN = re.compile(r"^\+[1-9]\d{5,13}$")

#: Maximum stored phone length — matches ``patients.phone VARCHAR(20)``
#: (``docs/05-DATABASE_DESIGN.md`` §2.7).
PHONE_MAX_LENGTH = 20

#: Characters humans type that carry no information in E.164.
_SEPARATORS = re.compile(r"[\s\-().]")


def normalize_phone(value: str) -> str:
    """Strip formatting separators from a phone number.

    Does not validate — call :func:`is_e164` on the result for that. Normalizing
    before validating means ``+91 98123-45678`` and ``+919812345678`` are treated
    as the same number, so a patient is not duplicated over punctuation.

    :param value: The raw phone number as entered.
    :returns: The number with whitespace, hyphens, parentheses, and dots removed.
    """
    return _SEPARATORS.sub("", value.strip())


def is_e164(value: str) -> bool:
    """Check whether a phone number is in valid E.164 form.

    :param value: The phone number to check. Not normalized first — pass the
        output of :func:`normalize_phone` if the input may contain separators.
    :returns: ``True`` if the value matches E.164.
    """
    return bool(E164_PATTERN.match(value))
