"""Unit tests for :mod:`app.utils.phone`."""

from __future__ import annotations

import pytest

from app.utils.phone import is_e164, normalize_phone


class TestNormalizePhone:
    """Stripping human formatting before validation."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("+919812345678", "+919812345678"),
            ("  +919812345678  ", "+919812345678"),
            ("+91 98123-45678", "+919812345678"),
            ("+91 (981) 234.5678", "+919812345678"),
        ],
        ids=["already_clean", "surrounding_space", "spaces_and_hyphens", "parens_and_dots"],
    )
    def test_normalize_phone_strips_formatting(self, raw: str, expected: str) -> None:
        assert normalize_phone(raw) == expected

    def test_normalize_phone_returns_empty_string_for_whitespace_only(self) -> None:
        assert normalize_phone("   ") == ""


class TestIsE164:
    """E.164 validation."""

    @pytest.mark.parametrize(
        "value",
        ["+919812345678", "+14155552671", "+442071838750", "+6834002"],
        ids=["india", "usa", "uk", "shortest_real_number"],
    )
    def test_is_e164_accepts_valid_numbers(self, value: str) -> None:
        assert is_e164(value)

    @pytest.mark.parametrize(
        "value",
        [
            "919812345678",
            "+0919812345678",
            "+9198",
            "+9198123456789012345",
            "+91981234567a",
            "+91 98123 45678",
            "",
        ],
        ids=[
            "missing_plus",
            "leading_zero_country_code",
            "too_short",
            "too_long",
            "contains_letter",
            "unnormalized_spaces",
            "empty",
        ],
    )
    def test_is_e164_rejects_invalid_numbers(self, value: str) -> None:
        assert not is_e164(value)
