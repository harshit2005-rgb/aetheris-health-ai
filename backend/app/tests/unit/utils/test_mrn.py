"""Tests for :mod:`app.utils.mrn`."""

from __future__ import annotations

import pytest

from app.utils.mrn import (
    DEFAULT_MRN_TEMPLATE,
    MRN_MAX_LENGTH,
    InvalidMrnTemplateError,
    format_mrn,
    generate_mrn,
    parse_mrn,
    validate_mrn_template,
)


class TestGenerateMrn:
    def test_generates_valid_mrn(self) -> None:
        mrn = generate_mrn(year=2026, sequence=42)
        assert mrn == "MRN-2026-00042"

    def test_zero_pads_sequence(self) -> None:
        mrn = generate_mrn(year=2026, sequence=1)
        assert mrn == "MRN-2026-00001"

    def test_raises_without_sequence(self) -> None:
        with pytest.raises(ValueError):
            generate_mrn(year=2026)  # sequence is None

    def test_raises_negative_sequence(self) -> None:
        with pytest.raises(ValueError):
            generate_mrn(year=2026, sequence=-1)


class TestParseMrn:
    def test_parses_valid_mrn(self) -> None:
        result = parse_mrn("MRN-2026-00042")
        assert result is not None
        assert result["year"] == 2026
        assert result["sequence"] == 42

    def test_returns_none_for_invalid(self) -> None:
        assert parse_mrn("invalid") is None
        assert parse_mrn("MRN-26-00001") is None


# ── Per-hospital template API ────────────────────────────────────────────────
# generate_mrn above renders the default format. These cover the template-driven
# API the patient module uses, where the format is stored per hospital.


class TestFormatMrn:
    """Rendering an MRN from a stored template."""

    def test_format_mrn_matches_generate_mrn_for_the_default_template(self) -> None:
        # The two APIs must not drift: a hospital on the default template and a
        # hospital with no template row have to end up with the same MRN.
        assert format_mrn(DEFAULT_MRN_TEMPLATE, year=2026, sequence=42) == generate_mrn(
            year=2026, sequence=42
        )

    def test_format_mrn_honours_a_custom_template(self) -> None:
        assert format_mrn("AH/{year}/{seq:04d}", year=2026, sequence=7) == "AH/2026/0007"

    def test_format_mrn_does_not_cap_the_sequence_at_the_padding_width(self) -> None:
        # A hospital past 99,999 patients must keep getting valid MRNs rather
        # than colliding with one already issued.
        assert format_mrn(DEFAULT_MRN_TEMPLATE, year=2026, sequence=123456) == "MRN-2026-123456"

    def test_format_mrn_rejects_a_render_longer_than_the_column(self) -> None:
        # patients.mrn is VARCHAR(30); a longer value would fail at INSERT time
        # with an opaque database error instead of a clear configuration error.
        with pytest.raises(InvalidMrnTemplateError, match=str(MRN_MAX_LENGTH)):
            format_mrn("HOSPITAL-PREFIX-VERY-LONG-{year}-{seq:05d}", year=2026, sequence=1)


class TestValidateMrnTemplate:
    """Template allowlist enforcement."""

    @pytest.mark.parametrize(
        "template",
        ["MRN-{year}-{seq:05d}", "{seq}", "AH/{year}/{seq:04d}", "P {seq:08d}", "MRN_{seq:03d}"],
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
