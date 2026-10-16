"""Money and currency utility functions.

Money is always represented as :class:`Decimal` with precision ``NUMERIC(15, 2)``.
Never use ``float`` for money. These utilities make safe arithmetic the default.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

#: Default decimal precision for monetary values.
MONEY_PRECISION = Decimal("0.01")


def as_money(value: Any) -> Decimal:
    """Convert a value to a Decimal with 2 decimal places.

    :param value: An int, float, string, or Decimal.
    :returns: A :class:`Decimal` rounded to 2 decimal places.
    :raises ValueError: If the value cannot be converted.
    """
    if isinstance(value, Decimal):
        return value.quantize(MONEY_PRECISION, rounding=ROUND_HALF_UP)
    if isinstance(value, float):
        return Decimal(str(value)).quantize(MONEY_PRECISION, rounding=ROUND_HALF_UP)
    if isinstance(value, int):
        return Decimal(value).quantize(MONEY_PRECISION, rounding=ROUND_HALF_UP)
    if isinstance(value, str):
        return Decimal(value).quantize(MONEY_PRECISION, rounding=ROUND_HALF_UP)

    raise ValueError(f"Cannot convert {type(value).__name__} to money.")


def format_money(value: Decimal, currency: str = "INR") -> str:
    """Format a monetary value as a human-readable string.

    :param value: The monetary value.
    :param currency: ISO 4217 currency code.
    :returns: A formatted string (e.g. ``₹1,499.00`` for INR, ``$1,499.00`` for USD).
    """
    formatted = f"{value:,.2f}"

    symbols = {
        "INR": "₹",
        "USD": "$",
        "EUR": "€",
        "GBP": "£",
        "JPY": "¥",
        "AUD": "A$",
        "CAD": "C$",
        "SGD": "S$",
    }

    symbol = symbols.get(currency, f"{currency} ")
    return f"{symbol}{formatted}"


def add_money(*values: Decimal) -> Decimal:
    """Add multiple monetary values safely.

    :param values: The values to add.
    :returns: The sum, rounded to 2 decimal places.
    """
    total = sum(values, Decimal("0"))
    return total.quantize(MONEY_PRECISION, rounding=ROUND_HALF_UP)


def multiply_money(value: Decimal, multiplier: Decimal) -> Decimal:
    """Multiply a monetary value by a multiplier.

    :param value: The monetary value.
    :param multiplier: The multiplier (e.g. quantity, tax rate).
    :returns: The product, rounded to 2 decimal places.
    """
    result = value * multiplier
    return result.quantize(MONEY_PRECISION, rounding=ROUND_HALF_UP)


def apply_tax(amount: Decimal, tax_rate_pct: Decimal) -> Decimal:
    """Calculate the tax amount for a given net amount.

    :param amount: The net monetary amount.
    :param tax_rate_pct: Tax rate as a percentage (e.g. ``Decimal('18')`` for 18%).
    :returns: The tax amount, rounded to 2 decimal places.
    """
    return multiply_money(amount, tax_rate_pct / Decimal("100"))


def apply_discount(amount: Decimal, discount_pct: Decimal) -> Decimal:
    """Calculate the discounted amount.

    :param amount: The original monetary amount.
    :param discount_pct: Discount percentage (e.g. ``Decimal('10')`` for 10% off).
    :returns: The discounted amount, rounded to 2 decimal places.
    """
    discount = multiply_money(amount, discount_pct / Decimal("100"))
    return add_money(amount, -discount)


def money_to_str(value: Decimal) -> str:
    """Render a monetary value as a JSON-safe decimal string.

    :param value: The monetary value.
    :returns: A string like ``\"1499.00\"``.
    """
    return str(value.quantize(MONEY_PRECISION, rounding=ROUND_HALF_UP))


__all__ = [
    "MONEY_PRECISION",
    "add_money",
    "apply_discount",
    "apply_tax",
    "as_money",
    "format_money",
    "money_to_str",
    "multiply_money",
]
