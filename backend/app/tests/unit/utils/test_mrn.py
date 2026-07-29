"""Unit tests for :mod:`app.utils.mrn`.

MRN formatting is the one place a hospital-configured string is interpolated,
so the template allowlist gets as much attention as the happy path.
"""

from __future__ import annotations

import pytest

from app.utils.mrn import (
    DEFAULT_MRN_TEMPLATE,
    MRN_MAX_LENGTH,
    InvalidMrnTemplateError,
    format_mrn,
    validate_mrn_template,
)


class TestFormatMrn:
    """Rendering an MRN from a template."""

    def test_format_mrn_default_template_pads_sequence_to_five_digits(self) -> None:
        assert format_mrn(DEFAULT_MRN_TEMPLATE, year=2026, sequence=42) == "MRN-2026-00042"

    def test_format_mrn_first_patient_renders_sequence_one(self) -> None:
        assert format_mrn(DEFAULT_MRN_TEMPLATE, year=2026, sequence=1) == "MRN-2026-00001"

    def test_format_mrn_sequence_beyond_padding_width_is_not_truncated(self) -> None:
        # A hospital that passes 99,999 patients must keep getting valid MRNs,
        # not silently wrap around to a value already in use.
        assert format_mrn(DEFAULT_MRN_TEMPLATE, year=2026, sequence=123456) == "MRN-2026-123456"

    def test_format_mrn_honours_a_custom_template(self) -> None:
        assert format_mrn("AH/{year}/{seq:04d}", year=2026, sequence=7) == "AH/2026/0007"

    def test_format_mrn_rejects_a_render_longer_than_the_column(self) -> None:
        # patients.mrn is VARCHAR(30); a longer value would fail at INSERT time
        # with an opaque database error instead of a clear configuration error.
        oversized = "HOSPITAL-PREFIX-VERY-LONG-{year}-{seq:05d}"
        with pytest.raises(InvalidMrnTemplateError, match=str(MRN_MAX_LENGTH)):
            format_mrn(oversized, year=2026, sequence=1)


class TestValidateMrnTemplate:
    """Template allowlist enforcement."""

    @pytest.mark.parametrize(
        "template",
        [
            "MRN-{year}-{seq:05d}",
            "{seq}",
            "AH/{year}/{seq:04d}",
            "P {seq:08d}",
            "MRN_{seq:03d}",
        ],
        ids=["default", "bare_seq", "slashes", "space", "underscore"],
    )
    def test_validate_mrn_template_accepts_allowed_forms(self, template: str) -> None:
        validate_mrn_template(template)  # must not raise

    def test_validate_mrn_template_rejects_an_empty_template(self) -> None:
        with pytest.raises(InvalidMrnTemplateError, match="must not be empty"):
            validate_mrn_template("")

    def test_validate_mrn_template_rejects_a_template_without_a_sequence(self) -> None:
        # Without {seq} every patient in a year would get the same MRN, and the
        # unique constraint would reject the second registration.
        with pytest.raises(InvalidMrnTemplateError, match="seq"):
            validate_mrn_template("MRN-{year}")

    @pytest.mark.parametrize(
        "template",
        [
            "MRN-{seq.__class__}",
            "MRN-{seq!r}",
            "MRN-{0}",
            "MRN-{hospital_name}-{seq}",
            "MRN-{seq:%Y}",
        ],
        ids=["attribute_access", "conversion", "positional", "unknown_name", "bad_format_spec"],
    )
    def test_validate_mrn_template_rejects_unsupported_syntax(self, template: str) -> None:
        # str.format on a stored template is an injection surface: attribute
        # access can walk from an int to module globals. The allowlist has to
        # reject anything that is not {year} or {seq}.
        with pytest.raises(InvalidMrnTemplateError):
            validate_mrn_template(template)

    def test_format_mrn_never_evaluates_a_rejected_template(self) -> None:
        # Validation must happen before interpolation, otherwise the check is
        # decorative.
        with pytest.raises(InvalidMrnTemplateError):
            format_mrn("{seq.__class__.__mro__}", year=2026, sequence=1)
