"""Medical Record Number (MRN) generator.

MRNs are human-readable, hospital-scoped identifiers for patients.
Format: ``MRN-{YEAR}-{SEQUENCE}`` (e.g. ``MRN-2026-00042``).

The sequence is stored externally (database sequence or Redis counter)
and passed to the generator — this module is pure computation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Final

#: Prefix for all MRNs.
MRN_PREFIX: Final[str] = "MRN"

#: Width of the sequence number portion (zero-padded).
SEQUENCE_WIDTH: Final[int] = 5


def generate_mrn(year: int | None = None, sequence: int | None = None) -> str:
    """Generate an MRN string.

    :param year: The year component. Defaults to the current year (UTC).
    :param sequence: The monotonic sequence number (1-based). Must be provided
        by the caller — this function does not talk to any database.
    :returns: An MRN string like ``MRN-2026-00042``.
    :raises ValueError: If *sequence* is ``None`` or negative.
    :raises ValueError: If *sequence* exceeds the maximum representable value.
    """
    if year is None:
        year = datetime.now(UTC).year

    if sequence is None:
        msg = "sequence is required — obtain it from a database sequence or Redis counter."
        raise ValueError(msg)

    if sequence < 1:
        msg = f"sequence must be >= 1, got {sequence}."
        raise ValueError(msg)

    max_seq = 10**SEQUENCE_WIDTH - 1
    if sequence > max_seq:
        msg = f"sequence {sequence} exceeds maximum {max_seq} for width {SEQUENCE_WIDTH}."
        raise ValueError(msg)

    return f"{MRN_PREFIX}-{year}-{sequence:0{SEQUENCE_WIDTH}d}"


def parse_mrn(mrn: str) -> dict[str, object] | None:
    """Parse an MRN string into its components.

    :param mrn: The MRN string to parse.
    :returns: A dict with ``prefix``, ``year``, and ``sequence``, or ``None``.
    """
    import re as _re

    pattern = _re.compile(rf"^{MRN_PREFIX}-(\d{{4}})-(\d{{{SEQUENCE_WIDTH}}})$")
    match = pattern.match(mrn)

    if not match:
        return None

    return {
        "prefix": MRN_PREFIX,
        "year": int(match.group(1)),
        "sequence": int(match.group(2)),
    }


__all__ = [
    "MRN_PREFIX",
    "SEQUENCE_WIDTH",
    "generate_mrn",
    "parse_mrn",
]
