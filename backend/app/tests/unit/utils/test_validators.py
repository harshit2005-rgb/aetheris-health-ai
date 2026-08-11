"""Tests for :mod:`app.utils.validators`."""

from __future__ import annotations

from app.utils.validators import (
    is_strong_password,
    is_valid_email,
    is_valid_mrn,
    is_valid_uuid,
    password_errors,
)


class TestIsValidEmail:
    def test_valid_email(self) -> None:
        assert is_valid_email("user@example.com") is True

    def test_valid_email_subdomain(self) -> None:
        assert is_valid_email("user@sub.example.com") is True

    def test_invalid_missing_at(self) -> None:
        assert is_valid_email("userexample.com") is False

    def test_invalid_empty(self) -> None:
        assert is_valid_email("") is False


class TestIsStrongPassword:
    def test_valid_password(self) -> None:
        assert is_strong_password("CorrectHorseBattery#42") is True

    def test_too_short(self) -> None:
        assert is_strong_password("Ab1!") is False

    def test_no_upper(self) -> None:
        assert is_strong_password("correcthorsebattery#42") is False

    def test_no_lower(self) -> None:
        assert is_strong_password("CORRECTHORSEBATTERY#42") is False

    def test_no_digit(self) -> None:
        assert is_strong_password("CorrectHorseBattery#!") is False

    def test_no_symbol(self) -> None:
        assert is_strong_password("CorrectHorseBattery42") is False


class TestPasswordErrors:
    def test_returns_errors_for_short_password(self) -> None:
        errors = password_errors("Ab1!")
        assert len(errors) >= 1

    def test_empty_errors_for_valid(self) -> None:
        errors = password_errors("CorrectHorseBattery#42")
        assert errors == []


class TestIsValidMrn:
    def test_valid_mrn(self) -> None:
        assert is_valid_mrn("MRN-2026-00042") is True

    def test_invalid_format(self) -> None:
        assert is_valid_mrn("invalid") is False


class TestIsValidUuid:
    def test_valid_uuid(self) -> None:
        assert is_valid_uuid("550e8400-e29b-41d4-a716-446655440000") is True

    def test_invalid_uuid(self) -> None:
        assert is_valid_uuid("not-a-uuid") is False
