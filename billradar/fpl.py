"""Federal poverty line by household size, and a family's income as a percent of it.

Hospitals publish financial-assistance discounts as tiers of this percent, so the number
computed here decides which tier a family falls into.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

GUIDELINES = {
    2026: {"base": [15960, 21640, 27320, 33000, 38680, 44360, 50040, 55720], "each_extra": 5680},
}


SOURCE = {2026: "HHS poverty guidelines 2026, 48 contiguous states and DC, 91 FR 1797 (January 15, 2026)"}


def latest_year() -> int:
    return max(GUIDELINES)


def guideline(household_size: int, year: int = 2026) -> Decimal:
    if household_size < 1:
        raise ValueError("household size must be at least 1")
    table = GUIDELINES[year]
    rows = table["base"]
    listed = min(household_size, len(rows))
    # Integer arithmetic, so a huge household is not cut to the decimal context's precision.
    return Decimal(rows[listed - 1] + (household_size - listed) * table["each_extra"])


def percent_of_guideline(annual_income: Decimal, household_size: int, year: int = 2026) -> Decimal:
    # Order sets which error wins: scaling trips on an unreadable income or a signalling NaN before the
    # household and year are looked at; infinity and an oversized result only fail at the final quantize.
    scaled_income = Decimal(annual_income) * 100
    poverty_line = guideline(household_size, year)
    return (scaled_income / poverty_line).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
