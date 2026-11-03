"""Current behaviour of the poverty-guideline numbers, past what test_checks.test_fpl_2026 pins.

The text form of both results goes into the review request as it stands, so several tests compare str(), not value.
"""
from decimal import Decimal, InvalidOperation

import pytest

from billradar import fpl


def text(value):
    assert isinstance(value, Decimal)
    return str(value)


# --- guideline ------------------------------------------------------------------------------

@pytest.mark.parametrize("size,expected", [(1, "15960"), (2, "21640"), (3, "27320"), (5, "38680"), (6, "44360"),
                                           (7, "50040"), (8, "55720")])
def test_guideline_reads_a_household_inside_the_table(size, expected):
    assert text(fpl.guideline(size)) == expected


@pytest.mark.parametrize("size,expected", [(9, "61400"), (11, "72760"), (20, "123880"), (100, "578280")])
def test_guideline_adds_the_same_amount_for_each_person_past_the_table(size, expected):
    assert text(fpl.guideline(size)) == expected


def test_guideline_stays_exact_for_a_household_wider_than_decimal_precision():
    assert text(fpl.guideline(10 ** 30)) == "5680000000000000000000000000010280"


def test_guideline_is_a_whole_decimal_without_exponent():
    assert fpl.guideline(3).as_tuple().exponent == 0
    assert fpl.guideline(9).as_tuple().exponent == 0


def test_guideline_takes_its_arguments_by_name():
    assert text(fpl.guideline(household_size=3, year=2026)) == "27320"


@pytest.mark.parametrize("size", [0, -1, -100])
def test_guideline_refuses_a_household_below_one_with_the_exact_message(size):
    with pytest.raises(ValueError) as err:
        fpl.guideline(size)
    assert str(err.value) == "household size must be at least 1"


def test_guideline_judges_the_household_before_the_year():
    with pytest.raises(ValueError):
        fpl.guideline(0, 2025)


@pytest.mark.parametrize("year", [2025, 2027, 0, None, "2026"])
def test_guideline_raises_key_error_carrying_the_year_it_has_no_table_for(year):
    with pytest.raises(KeyError) as err:
        fpl.guideline(4, year)
    assert err.value.args == (year,)


@pytest.mark.parametrize("size", [None, "4"])
def test_guideline_raises_type_error_for_a_household_that_is_not_a_number(size):
    with pytest.raises(TypeError):
        fpl.guideline(size)


def test_guideline_raises_type_error_for_a_bad_household_even_when_the_year_is_missing():
    with pytest.raises(TypeError):
        fpl.guideline(None, 2025)


def test_guideline_stays_on_2026_by_default_when_a_later_year_is_loaded(monkeypatch):
    monkeypatch.setitem(fpl.GUIDELINES, 2027, {"base": [1, 2, 3], "each_extra": 1})
    assert text(fpl.guideline(3)) == "27320"
    assert text(fpl.guideline(3, 2027)) == "3"


@pytest.mark.parametrize("size,expected", [(1, "100"), (3, "300"), (4, "350"), (6, "450")])
def test_guideline_takes_the_table_length_from_the_year_shorter_than_eight(monkeypatch, size, expected):
    monkeypatch.setitem(fpl.GUIDELINES, 2099, {"base": [100, 200, 300], "each_extra": 50})
    assert text(fpl.guideline(size, 2099)) == expected


@pytest.mark.parametrize("size,expected", [(8, "800"), (9, "900"), (10, "1000"), (12, "1014")])
def test_guideline_takes_the_table_length_from_the_year_longer_than_eight(monkeypatch, size, expected):
    base = [100 * n for n in range(1, 11)]
    monkeypatch.setitem(fpl.GUIDELINES, 2099, {"base": base, "each_extra": 7})
    assert text(fpl.guideline(size, 2099)) == expected


# --- percent_of_guideline: the number ---------------------------------------------------------

@pytest.mark.parametrize("income,size,expected", [
    ("41960", 2, "193.9"),
    ("60000", 3, "219.6"),
    ("100000", 3, "366.0"),
    ("12345.67", 7, "24.7"),
    ("159600", 1, "1000.0"),
])
def test_percent_is_the_income_against_the_guideline_to_one_decimal_place(income, size, expected):
    assert text(fpl.percent_of_guideline(Decimal(income), size)) == expected


@pytest.mark.parametrize("income,size,expected", [("31920", 1, "200.0"), ("38680", 5, "100.0"), ("27860", 8, "50.0"),
                                                  ("61400", 9, "100.0"), ("78440", 12, "100.0")])
def test_percent_keeps_the_decimal_place_on_a_round_result(income, size, expected):
    assert text(fpl.percent_of_guideline(Decimal(income), size)) == expected


@pytest.mark.parametrize("income,size,expected", [
    ("7.98", 1, "0.1"),  # 0.05
    ("23.94", 1, "0.2"),  # 0.15
    ("1955.10", 1, "12.3"),  # 12.25
    ("1971.06", 1, "12.4"),  # 12.35
    ("16.50", 4, "0.1"),  # 0.05
    ("27.86", 8, "0.1"),  # 0.05
])
def test_percent_rounds_a_tie_up(income, size, expected):
    assert text(fpl.percent_of_guideline(Decimal(income), size)) == expected


@pytest.mark.parametrize("income,expected", [("7.97", "0.0"), ("1955.09", "12.2"), ("1955.11", "12.3")])
def test_percent_rounds_by_the_nearest_tenth_around_a_tie(income, expected):
    assert text(fpl.percent_of_guideline(Decimal(income), 1)) == expected


@pytest.mark.parametrize("income,expected", [("-7.98", "-0.1"), ("-1955.10", "-12.3"), ("-1971.06", "-12.4")])
def test_percent_rounds_a_negative_tie_away_from_zero(income, expected):
    assert text(fpl.percent_of_guideline(Decimal(income), 1)) == expected


def test_percent_keeps_the_sign_of_a_negative_income():
    assert text(fpl.percent_of_guideline(Decimal("-60000"), 3)) == "-219.6"


@pytest.mark.parametrize("income,expected", [(Decimal(0), "0.0"), (Decimal("0.00"), "0.0"), (0, "0.0"),
                                             (Decimal("-0.01"), "-0.0"), (Decimal("-0"), "-0.0")])
def test_percent_of_nothing_keeps_the_decimal_place_and_the_sign(income, expected):
    assert text(fpl.percent_of_guideline(income, 4)) == expected


@pytest.mark.parametrize("income", [60000, "60000", " 60000 ", "6E+4", 60000.0, Decimal("60000.00")])
def test_percent_takes_the_income_as_anything_decimal_can_read(income):
    assert text(fpl.percent_of_guideline(income, 3)) == "219.6"


def test_percent_reads_a_float_income_by_its_exact_value():
    # The float nearest to 1955.10 sits just under the tie that the decimal 1955.10 lands on.
    assert text(fpl.percent_of_guideline(1955.1, 1)) == "12.2"
    assert text(fpl.percent_of_guideline("1955.1", 1)) == "12.3"


def test_percent_of_a_vanishing_income_is_zero():
    assert text(fpl.percent_of_guideline(Decimal("1E-30"), 4)) == "0.0"


def test_percent_takes_its_arguments_by_name():
    assert text(fpl.percent_of_guideline(annual_income=Decimal("60000"), household_size=3, year=2026)) == "219.6"


def test_percent_uses_the_guideline_of_the_year_it_is_asked_for(monkeypatch):
    monkeypatch.setitem(fpl.GUIDELINES, 2099, {"base": [1000], "each_extra": 500})
    assert text(fpl.percent_of_guideline(Decimal(750), 1, 2099)) == "75.0"
    assert text(fpl.percent_of_guideline(Decimal(750), 3, 2099)) == "37.5"


def test_percent_stays_on_2026_by_default_when_a_later_year_is_loaded(monkeypatch):
    monkeypatch.setitem(fpl.GUIDELINES, 2027, {"base": [1000], "each_extra": 500})
    assert text(fpl.percent_of_guideline(Decimal(60000), 3)) == "219.6"


# --- percent_of_guideline: the edges of Decimal -----------------------------------------------

@pytest.mark.parametrize("income,expected", [(Decimal("1E+28"), "30303030303030303030303030.3"),
                                             (Decimal("3.2E+29"), "969696969696969696969696969.7")])
def test_percent_works_up_to_twenty_eight_digits_of_result(income, expected):
    assert text(fpl.percent_of_guideline(income, 4)) == expected


@pytest.mark.parametrize("income", [Decimal("3.3E+29"), Decimal("1E+30")])
def test_percent_refuses_a_result_wider_than_twenty_eight_digits(income):
    with pytest.raises(InvalidOperation):
        fpl.percent_of_guideline(income, 4)


@pytest.mark.parametrize("income,expected", [(Decimal("NaN"), "NaN"), (Decimal("-NaN"), "-NaN"), (float("nan"), "NaN")])
def test_percent_hands_a_quiet_nan_back_as_nan(income, expected):
    assert text(fpl.percent_of_guideline(income, 4)) == expected


@pytest.mark.parametrize("income", [Decimal("Infinity"), Decimal("-Infinity"), float("inf"), Decimal("sNaN")])
def test_percent_refuses_infinity_and_signalling_nan(income):
    with pytest.raises(InvalidOperation):
        fpl.percent_of_guideline(income, 4)


@pytest.mark.parametrize("income", ["abc", "", "1,000"])
def test_percent_refuses_text_that_is_not_a_number(income):
    with pytest.raises(InvalidOperation):
        fpl.percent_of_guideline(income, 4)


@pytest.mark.parametrize("income", [None, b"1"])
def test_percent_raises_type_error_for_an_income_of_another_type(income):
    with pytest.raises(TypeError):
        fpl.percent_of_guideline(income, 4)


# --- percent_of_guideline: which error wins ---------------------------------------------------

@pytest.mark.parametrize("size", [0, -3])
def test_percent_refuses_a_household_below_one_with_the_exact_message(size):
    with pytest.raises(ValueError) as err:
        fpl.percent_of_guideline(Decimal(1000), size)
    assert str(err.value) == "household size must be at least 1"


def test_percent_raises_key_error_carrying_the_year_it_has_no_table_for():
    with pytest.raises(KeyError) as err:
        fpl.percent_of_guideline(Decimal(1000), 4, 2025)
    assert err.value.args == (2025,)


def test_percent_raises_type_error_for_a_household_that_is_not_a_number():
    with pytest.raises(TypeError):
        fpl.percent_of_guideline(Decimal(1000), None)


@pytest.mark.parametrize("income,size,year,error", [
    ("abc", 0, 2026, InvalidOperation),
    (Decimal("sNaN"), 0, 2026, InvalidOperation),
    ("abc", 4, 2025, InvalidOperation),
    (None, 0, 2026, TypeError),
    (None, None, 2026, TypeError),
])
def test_percent_blames_an_unreadable_income_before_the_household_and_the_year(income, size, year, error):
    with pytest.raises(error):
        fpl.percent_of_guideline(income, size, year)


def test_percent_blames_the_household_before_the_year():
    with pytest.raises(ValueError):
        fpl.percent_of_guideline(Decimal(1000), 0, 2025)


@pytest.mark.parametrize("income", [Decimal("Infinity"), Decimal("NaN"), Decimal("1E+30")])
def test_percent_blames_a_bad_household_before_an_income_it_cannot_finish(income):
    with pytest.raises(ValueError):
        fpl.percent_of_guideline(income, 0)


@pytest.mark.parametrize("income", [Decimal("Infinity"), Decimal("NaN"), Decimal("1E+30")])
def test_percent_blames_a_missing_year_before_an_income_it_cannot_finish(income):
    with pytest.raises(KeyError):
        fpl.percent_of_guideline(income, 4, 2025)
