"""Medical Record Number (MRN) formatting.

Pure formatting helpers — no database access. The per-hospital counter that
feeds :func:`format_mrn` lives in ``mrn_sequences`` and is read transactionally
by :class:`~app.repositories.mrn_sequence_repository.MrnSequenceRepository`;
the orchestration lives in :class:`~app.services.mrn_service.MRNService`.

MRN format is configurable per hospital
(``docs/modules/03-patient-management.md`` §4, rule 2). The default template is
``MRN-{year}-{seq:05d}`` which renders as ``MRN-2026-00042``.

Usage::

    from app.utils.mrn import DEFAULT_MRN_TEMPLATE, format_mrn

    format_mrn(DEFAULT_MRN_TEMPLATE, year=2026, sequence=42)  # 'MRN-2026-00042'
"""

from __future__ import annotations

import re

__all__ = [
    "DEFAULT_MRN_TEMPLATE",
    "MRN_MAX_LENGTH",
    "InvalidMrnTemplateError",
    "format_mrn",
    "validate_mrn_template",
]

#: Default per-hospital MRN template (``docs/modules/03-patient-management.md`` §8).
DEFAULT_MRN_TEMPLATE = "MRN-{year}-{seq:05d}"

#: Maximum MRN length — matches ``patients.mrn VARCHAR(30)``
#: (``docs/05-DATABASE_DESIGN.md`` §2.7).
MRN_MAX_LENGTH = 30

#: The only placeholders a template may contain. Templates come from tenant
#: configuration, and :meth:`str.format` on untrusted input can reach into
#: object attributes (``{seq.__class__}``), so the template is matched against
#: this allowlist *before* it is ever formatted.
_ALLOWED_PLACEHOLDER = re.compile(r"\{(?:year|seq(?::0\d{1,2}d)?)\}")

#: Literal text permitted between placeholders. Deliberately narrow: letters,
#: digits, hyphen, underscore, slash, and space.
_ALLOWED_LITERAL = re.compile(r"[A-Za-z0-9\-_/ ]*")


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
    """Render an MRN from a template, a year, and a sequence value.

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
