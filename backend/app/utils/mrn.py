"""Medical Record Number (MRN) generator.

MRNs are human-readable, hospital-scoped identifiers for patients.
Format: ``MRN-{YEAR}-{SEQUENCE}`` (e.g. ``MRN-2026-00042``).

The sequence is stored externally (database sequence or Redis counter)
and passed to the generator — this module is pure computation.
"""

from __future__ import annotations

import re
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


# ── Per-hospital configurable templates ──────────────────────────────────────
# docs/modules/03-patient-management.md §4 rule 2 requires the MRN format to be
# configurable per hospital, stored in mrn_sequences.format_template.
# ``generate_mrn`` above renders the default format; the functions below render
# an arbitrary stored template. Both produce the same string for the default.

#: Default per-hospital MRN template (``docs/modules/03-patient-management.md`` §8).
DEFAULT_MRN_TEMPLATE: Final[str] = "MRN-{year}-{seq:05d}"

#: Maximum MRN length — matches ``patients.mrn VARCHAR(30)``
#: (``docs/05-DATABASE_DESIGN.md`` §2.7).
MRN_MAX_LENGTH: Final[int] = 30

#: The only placeholders a template may contain. Templates come from tenant
#: configuration, and :meth:`str.format` on untrusted input can reach into
#: object attributes (``{seq.__class__}``), so the template is matched against
#: this allowlist *before* it is ever formatted.
_ALLOWED_PLACEHOLDER: Final[re.Pattern[str]] = re.compile(r"\{(?:year|seq(?::0\d{1,2}d)?)\}")

#: Literal text permitted between placeholders. Deliberately narrow: letters,
#: digits, hyphen, underscore, slash, and space.
_ALLOWED_LITERAL: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9\-_/ ]*")


class InvalidMrnTemplateError(ValueError):
    """Raised when an MRN template contains unsupported syntax.

    This is a configuration error, not a user-input error: templates are set
    per hospital, never submitted through the patient API.
    """


def validate_mrn_template(template: str) -> None:
    """Validate an MRN template against the placeholder allowlist.

    :param template: The template string, e.g. ``MRN-{year}-{seq:05d}``.
    :raises InvalidMrnTemplateError: If the template is empty, contains an
        unknown placeholder, or contains characters outside the allowlist.
    """
    if not template:
        msg = "MRN template must not be empty."
        raise InvalidMrnTemplateError(msg)

    position = 0
    saw_sequence = False
    while position < len(template):
        literal = _ALLOWED_LITERAL.match(template, position)
        # ``match`` with a ``*`` pattern always succeeds; it may match empty.
        if literal is not None and literal.end() > position:
            position = literal.end()
            continue

        placeholder = _ALLOWED_PLACEHOLDER.match(template, position)
        if placeholder is None:
            msg = (
                f"Unsupported MRN template syntax at position {position}: {template!r}. "
                "Only the {year} and {seq} placeholders and the characters "
                "[A-Za-z0-9-_/ ] are permitted."
            )
            raise InvalidMrnTemplateError(msg)
        if placeholder.group().startswith("{seq"):
            saw_sequence = True
        position = placeholder.end()

    if not saw_sequence:
        msg = f"MRN template must contain a {{seq}} placeholder: {template!r}"
        raise InvalidMrnTemplateError(msg)


def format_mrn(template: str, *, year: int, sequence: int) -> str:
    """Render an MRN from a stored template, a year, and a sequence value.

    Unlike :func:`generate_mrn` this accepts an arbitrary per-hospital
    template and does not cap the sequence at :data:`SEQUENCE_WIDTH` digits —
    a hospital past 99,999 patients must keep getting valid, unique MRNs.

    :param template: The hospital's MRN template.
    :param year: Four-digit calendar year the MRN is issued in.
    :param sequence: The hospital's next sequence value (1-based).
    :returns: The rendered MRN.
    :raises InvalidMrnTemplateError: If the template fails validation, or if
        rendering produces a value longer than :data:`MRN_MAX_LENGTH`.
    """
    validate_mrn_template(template)

    mrn = template.format(year=year, seq=sequence)

    if len(mrn) > MRN_MAX_LENGTH:
        msg = (
            f"Rendered MRN {mrn!r} is {len(mrn)} characters, "
            f"which exceeds the {MRN_MAX_LENGTH}-character column limit."
        )
        raise InvalidMrnTemplateError(msg)

    return mrn


__all__ = [
    "DEFAULT_MRN_TEMPLATE",
    "MRN_MAX_LENGTH",
    "MRN_PREFIX",
    "SEQUENCE_WIDTH",
    "InvalidMrnTemplateError",
    "format_mrn",
    "generate_mrn",
    "parse_mrn",
    "validate_mrn_template",
]
