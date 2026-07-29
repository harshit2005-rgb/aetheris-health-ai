"""Tests for :mod:`app.utils.mrn`."""

from __future__ import annotations

import pytest

from app.utils.mrn import generate_mrn, parse_mrn


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
