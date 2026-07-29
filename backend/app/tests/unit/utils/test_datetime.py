"""Unit tests for :mod:`app.utils.datetime`.

Age arithmetic decides which patients a search returns, so the boundary cases
(birthday today, birthday tomorrow, leap day) are tested explicitly.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.utils.datetime import age_in_years, subtract_years, utc_now, utc_today


class TestAgeInYears:
    """Whole-year age calculation."""

    def test_age_in_years_counts_completed_years(self) -> None:
        assert age_in_years(date(1988, 3, 14), as_of=date(2026, 7, 27)) == 38

    def test_age_in_years_counts_the_birthday_itself(self) -> None:
        assert age_in_years(date(1988, 7, 27), as_of=date(2026, 7, 27)) == 38

    def test_age_in_years_excludes_a_birthday_that_has_not_arrived(self) -> None:
        assert age_in_years(date(1988, 7, 28), as_of=date(2026, 7, 27)) == 37

    def test_age_in_years_of_a_newborn_is_zero(self) -> None:
        assert age_in_years(date(2026, 7, 27), as_of=date(2026, 7, 27)) == 0

    def test_age_in_years_treats_a_leap_day_birthday_as_first_of_march(self) -> None:
        # 29 February 2000, evaluated on 28 February 2025 (not a leap year):
        # the birthday has not arrived yet.
        assert age_in_years(date(2000, 2, 29), as_of=date(2025, 2, 28)) == 24
        assert age_in_years(date(2000, 2, 29), as_of=date(2025, 3, 1)) == 25

    def test_age_in_years_is_negative_for_a_future_date(self) -> None:
        # Callers reject future dates explicitly; this must not quietly clamp
        # to zero and make a future DOB look like a newborn.
        assert age_in_years(date(2027, 1, 1), as_of=date(2026, 7, 27)) < 0

    def test_age_in_years_defaults_to_today(self) -> None:
        assert age_in_years(utc_today()) == 0


class TestSubtractYears:
    """Calendar-year subtraction."""

    def test_subtract_years_returns_the_same_day_and_month(self) -> None:
        assert subtract_years(date(2026, 7, 27), 40) == date(1986, 7, 27)

    def test_subtract_years_by_zero_is_the_identity(self) -> None:
        assert subtract_years(date(2026, 7, 27), 0) == date(2026, 7, 27)

    def test_subtract_years_clamps_a_leap_day_to_the_28th(self) -> None:
        # 2025 is not a leap year, so 29 February does not exist there.
        assert subtract_years(date(2024, 2, 29), 1) == date(2023, 2, 28)

    def test_subtract_years_rejects_a_negative_count(self) -> None:
        with pytest.raises(ValueError, match="must not be negative"):
            subtract_years(date(2026, 7, 27), -1)


class TestUtcHelpers:
    """UTC clock helpers."""

    def test_utc_now_is_timezone_aware(self) -> None:
        # docs/06-API_STANDARDS.md §17: no naive datetimes, ever.
        assert utc_now().tzinfo is not None

    def test_utc_today_matches_utc_now(self) -> None:
        assert utc_today() == utc_now().date()
