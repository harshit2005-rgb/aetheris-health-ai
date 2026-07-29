"""Slug generation utilities.

Produces URL-safe slugs from arbitrary strings. Used for hospital slugs,
service codes, and any resource that needs a human-readable URL identifier.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Final

#: Characters allowed in slugs.
_SLUG_OK: Final[re.Pattern[str]] = re.compile(r"[^a-z0-9-]")


def slugify(value: str, max_length: int = 100) -> str:
    """Convert a string to a URL-safe slug.

    Converts to lowercase, replaces non-ASCII characters with their ASCII
    equivalents, replaces whitespace and underscores with hyphens, strips
    leading/trailing hyphens, and collapses multiple hyphens.

    **Examples:**

    - ``"My Hospital"`` → ``\"my-hospital\"``
    - ``"St. Mary's Clinic\"`` → ``\"st-marys-clinic\"``
    - ``"  Apollo  Hospitals  Group  \"`` → ``\"apollo-hospitals-group\"``

    :param value: The input string.
    :param max_length: Maximum slug length. Longer slugs are truncated.
    :returns: A URL-safe slug.
    :raises ValueError: If the resulting slug is empty.
    """
    # Normalize unicode characters to their ASCII equivalents.
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")

    # Lowercase
    slug = ascii_value.lower()

    # Replace underscores and whitespace with hyphens
    slug = re.sub(r"[_\s]+", "-", slug)

    # Remove any remaining invalid characters
    slug = _SLUG_OK.sub("", slug)

    # Collapse multiple hyphens
    slug = re.sub(r"-{2,}", "-", slug)

    # Strip leading/trailing hyphens
    slug = slug.strip("-")

    # Truncate to max_length
    if max_length and len(slug) > max_length:
        slug = slug[:max_length].rstrip("-")

    if not slug:
        raise ValueError(f"Slugification produced an empty string from: {value!r}")

    return slug


def is_valid_slug(value: str) -> bool:
    """Check if a string is a valid slug.

    :param value: The string to check.
    :returns: ``True`` if the string matches the slug pattern.
    """
    return bool(re.fullmatch(r"[a-z0-9]([a-z0-9-]*[a-z0-9])?", value))


__all__ = [
    "is_valid_slug",
    "slugify",
]
