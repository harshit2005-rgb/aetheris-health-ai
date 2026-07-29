"""Tests for :mod:`app.utils.money`."""

from __future__ import annotations

from decimal import Decimal

from app.utils.money import (
    add_money,
    apply_discount,
    apply_tax,
    as_money,
    format_money,
    money_to_str,
    multiply_money,
)


class TestAsMoney:
    def test_from_int(self) -> None:
        assert as_money(100) == Decimal("100.00")

    def test_from_float(self) -> None:
        assert as_money(99.99) == Decimal("99.99")

    def test_from_string(self) -> None:
        assert as_money("1500.50") == Decimal("1500.50")

    def test_from_decimal(self) -> None:
        assert as_money(Decimal("200.00")) == Decimal("200.00")

    def test_rounds_to_two_places(self) -> None:
        assert as_money("10.999") == Decimal("11.00")
        assert as_money("10.001") == Decimal("10.00")


class TestAddMoney:
    def test_adds_values(self) -> None:
        result = add_money(Decimal("10.50"), Decimal("20.25"), Decimal("5.25"))
        assert result == Decimal("36.00")


class TestMultiplyMoney:
    def test_multiply(self) -> None:
        result = multiply_money(Decimal("10.50"), Decimal("3"))
        assert result == Decimal("31.50")

    def test_multiply_by_fraction(self) -> None:
        result = multiply_money(Decimal("100.00"), Decimal("0.18"))
        assert result == Decimal("18.00")


class TestApplyTax:
    def test_18_percent_tax(self) -> None:
        tax = apply_tax(Decimal("1000.00"), Decimal("18"))
        assert tax == Decimal("180.00")


class TestApplyDiscount:
    def test_10_percent_discount(self) -> None:
        discounted = apply_discount(Decimal("1000.00"), Decimal("10"))
        assert discounted == Decimal("900.00")


class TestFormatMoney:
    def test_format_inr(self) -> None:
        result = format_money(Decimal("1499.00"), "INR")
        assert "₹" in result
        assert "1,499.00" in result

    def test_format_usd(self) -> None:
        result = format_money(Decimal("99.99"), "USD")
        assert "$" in result


class TestMoneyToStr:
    def test_converts_to_string(self) -> None:
        assert money_to_str(Decimal("1499.00")) == "1499.00"
