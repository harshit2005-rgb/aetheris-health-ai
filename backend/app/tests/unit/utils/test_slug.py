"""Tests for :mod:`app.utils.slug`."""

from __future__ import annotations

import pytest

from app.utils.slug import is_valid_slug, slugify


class TestSlugify:
    def test_simple_string(self) -> None:
        assert slugify("My Hospital") == "my-hospital"

    def test_handles_special_chars(self) -> None:
        assert slugify("St. Mary's Clinic") == "st-marys-clinic"

    def test_trims_and_collapses(self) -> None:
        assert slugify("  Apollo  Hospitals  Group  ") == "apollo-hospitals-group"

    def test_handles_unicode(self) -> None:
        assert slugify("José García") == "jose-garcia"

    def test_raises_on_empty_result(self) -> None:
        with pytest.raises(ValueError):
            slugify("")


class TestIsValidSlug:
    def test_valid_slug(self) -> None:
        assert is_valid_slug("my-hospital") is True

    def test_invalid_slug_with_spaces(self) -> None:
        assert is_valid_slug("my hospital") is False
