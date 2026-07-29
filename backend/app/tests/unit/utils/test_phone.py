"""Tests for :mod:`app.utils.phone`."""

from __future__ import annotations

from app.utils.phone import is_e164, mask, normalize, strip_non_digits


class TestStripNonDigits:
    def test_strips_dashes(self) -> None:
        assert strip_non_digits("+91-9876543210") == "+919876543210"

    def test_strips_spaces(self) -> None:
        assert strip_non_digits("+91 98765 43210") == "+919876543210"


class TestIsE164:
    def test_valid_e164(self) -> None:
        assert is_e164("+919876543210") is True

    def test_invalid_no_plus(self) -> None:
        assert is_e164("9876543210") is False

    def test_invalid_short(self) -> None:
        assert is_e164("+91123") is False


class TestNormalize:
    def test_international_format(self) -> None:
        assert normalize("+919876543210") == "+919876543210"

    def test_indian_mobile_10_digits(self) -> None:
        assert normalize("9876543210") == "+919876543210"

    def test_indian_mobile_with_leading_zero(self) -> None:
        assert normalize("09876543210") == "+919876543210"


class TestMask:
    def test_masks_all_but_last_4(self) -> None:
        masked = mask("+919876543210", visible_digits=4)
        assert masked.endswith("3210")
        assert masked.startswith("*")

    def test_full_reveal_for_short(self) -> None:
        assert mask("1234", visible_digits=4) == "1234"
