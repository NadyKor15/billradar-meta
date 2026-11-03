"""One answer on every surface: has this date gone by, and how long is left.

Findings are stored with their dates and without a day count: the count belongs to the day the family reads it.
"""

from __future__ import annotations

from datetime import date


CHECK_DATE = "check it with the hospital"  # the date stands, but no paper prints what it counts from


def passed(day: date, today: date) -> bool:
    return day < today


def passed_title(kind: str, day: date | None, today: date) -> str:
    """The heading of a date gone by; "" while it is open. `kind`: F2 the application, A1 the appeal."""
    what = {"F2": "apply", "A1": "appeal"}.get(kind)
    if not what or not day or not passed(day, today):
        return ""
    return f"The last day to {what} was {day:%b %-d, %Y}"


def left(day: date, today: date) -> str:
    n = (day - today).days
    if n < 0:
        return "This date has passed; you can still ask, and ask for any refusal in writing."
    if n == 0:
        return "Today is the last day."
    return f"{n} day{'s' if n != 1 else ''} left."
