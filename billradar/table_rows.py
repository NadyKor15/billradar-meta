"""This computer as a witness to what the model read. Muse Glimmer reads the sheet here as printed rows; a line the
model read counts as seen when its code and its amounts stand where a line of a bill prints them: on one row, or on that
row and the payment and adjustment rows under it, up to the next service or a total. A share may be printed as two
columns, a deductible and a coinsurance. A number placed on a line that does not print it (a subtotal read into a line)
is not seen. Nothing here calls a model."""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from itertools import combinations
from decimal import Decimal

import numpy as np

from billradar import redact
from billradar.case import Document, Line, parse_money

BALANCE_WORDS = re.compile(r"(?i)balance|amount due|you owe|total due")
NOT_THE_BALANCE = re.compile(r"(?i)\bfees?\b|\bif\b|\bnot paid\b|\bprevious\b|\bprior\b|\binsurance\s+(?:balance|pending|due)"
                             r"|due from insurance|pending insurance")
NOT_THE_LINE = re.compile(r"(?i)total|balance|amount due|you owe")  # the summary under the lines starts here
PART_OF_THE_LINE = re.compile(r"(?i)insurance|payment|adjust|discount|write.?off|patient resp|your (?:share|resp)|copay"
                              r"|coinsurance|deductible")
STARTS_WITH_A_DATE = re.compile(r"^\W*(?:\d{1,2}/\d{1,2}/\d{2,4}|[A-Z][a-z]{2} \d{1,2}, \d{4})")
THIS_SERVICE = re.compile(r"(?i)balance due on these services")
MOVED = re.compile(r"(?i)balance transferred|transferred to")
BROKEN_CENTS = re.compile(r"(\d)\.\s+\.?\s*(\d{2})(?!\d)")  # "$467. .86": a crease through the amount
SERVICE_CODE = redact.SERVICE_CODE


TILTS = [round(i / 500, 3) for i in range(-20, 21) if i]  # 2.3 degrees either way: more than that, the sheet goes back
MIN_WORDS_FOR_TILT = 12
CLEARLY_BETTER = 1.25


@dataclass
class Row:
    text: str
    amounts: set[Decimal]
    codes: set[str]


@dataclass
class Witness:
    seen: int = 0
    total: int = 0
    unseen: list[int] = field(default_factory=list)  # line numbers the device could not confirm


def _tilt(lines: list) -> float:
    """How far the print runs downhill, per pixel across: a sheet lying a little crooked, as most do. Printed rows make the
    tops of the words line up at the right slope. A sheet that already lines up stays as read."""
    if len(lines) < MIN_WORDS_FOR_TILT:
        return 0.0
    boxes = np.array([[*x.box.mean(axis=0), np.ptp(x.box[:, 1])] for x in lines], dtype=float)
    xs, ys = boxes[:, 0], boxes[:, 1]
    step = max(2.0, float(np.median(boxes[:, 2])) / 3)

    def crisp(slope: float) -> float:
        y = ys - slope * xs
        return float((np.bincount(((y - y.min()) / step).astype(int)) ** 2).sum())

    best = max(TILTS, key=crisp)
    if abs(best) >= TILTS[-1]:  # leaning at the bound or past it: not a slight lean, and not ours to level
        return 0.0
    return float(best) if crisp(best) > CLEARLY_BETTER * crisp(0.0) else 0.0


def groups(lines: list) -> list[list]:
    """OCR lines of one printed row together, top to bottom. On a crooked sheet the far end of a row stands lower than its
    start, by half a row or more: rows are compared as if the sheet lay straight."""
    tilt = _tilt(lines)
    level = [(x, replace(x, box=x.box - np.column_stack([np.zeros(len(x.box)), tilt * x.box[:, 0]]))) for x in lines] if tilt \
        else [(x, x) for x in lines]
    grouped: list[list] = []
    for line, flat in sorted(level, key=lambda p: (float(p[1].box[:, 1].min()), float(p[1].box[:, 0].min()))):
        row = next((r for r in grouped if redact._same_row(r[0][1], flat)), None)
        (row.append((line, flat)) if row is not None else grouped.append([(line, flat)]))
    return [[line for line, _ in row] for row in grouped]


def rows(lines: list) -> list[Row]:
    """OCR lines joined into printed rows, top to bottom, each row left to right."""
    grouped = groups(lines)
    out = []
    for group in grouped:
        text = BROKEN_CENTS.sub(r"\1.\2", " ".join(x.text for x in sorted(group, key=lambda x: float(x.box[:, 0].min()))))
        amounts = {abs(v) for v in (parse_money(m.group()) for m in redact.AMOUNT_ON_LINE.finditer(text)) if v is not None}
        out.append(Row(text, amounts, {m.group(1) for m in SERVICE_CODE.finditer(text)}))
    return out


def numbers_of(line: Line) -> set[Decimal]:
    parts = (line.charges, line.insurance_paid, line.adjustment, line.fa_discount, line.patient_responsibility)
    return {abs(v) for v in parts if v}


def _line_at(printed: list[Row], i: int) -> set[Decimal]:
    """The amounts of the line a row starts: the row, the amount above a code printed under its description, and the
    payment and adjustment rows below, up to the next service or a total."""
    amounts = set(printed[i].amounts)
    if not amounts and i:
        amounts |= printed[i - 1].amounts
    for r in printed[i + 1:]:
        if THIS_SERVICE.search(r.text):  # the service's own balance: the last row of its line
            amounts |= r.amounts
            if r.amounts:
                break
            continue
        part = PART_OF_THE_LINE.search(r.text)
        date_only = STARTS_WITH_A_DATE.fullmatch(r.text.strip())
        if r.codes or NOT_THE_LINE.search(r.text) or (STARTS_WITH_A_DATE.match(r.text) and not part and not date_only):
            break
        if part:
            amounts |= r.amounts
    return amounts


def _holds(line: Line, amounts: set[Decimal]) -> bool:
    """Every amount is printed. The share may be two columns of the row: a deductible and a coinsurance."""
    share = abs(line.patient_responsibility) if line.patient_responsibility else None
    if not (numbers_of(line) - {share}) <= amounts:
        return False
    return share is None or share in amounts or share in {a + b for a, b in combinations(amounts, 2)}


def seen(line: Line, printed: list[Row]) -> bool:
    code = line.code.strip()
    return any((not code or code in r.codes) and _holds(line, _line_at(printed, i)) for i, r in enumerate(printed))


def witness(doc: Document, printed: list[Row]) -> Witness:
    out = Witness()
    for line in doc.lines:
        if not numbers_of(line):
            continue
        out.total += 1
        if seen(line, printed):
            out.seen += 1
        else:
            out.unseen.append(line.line_no)
    return out


NAMES_A_SUM = re.compile(r"(?i)balance|amount|you owe|total due|pay this|patient resp|discount|assistance")


def named(value: Decimal, printed: list[Row]) -> bool:
    """The device reads this sum on a row that names it, or under a heading that does. The same number printed for
    something else is not it."""
    return any(abs(value) in r.amounts and (NAMES_A_SUM.search(r.text) or (i and NAMES_A_SUM.search(printed[i - 1].text)))
               for i, r in enumerate(printed))


def confirms(doc: Document, step, printed: list[Row]) -> bool:
    """One printed value a confirmed sum stands on, read by the device where the paper prints it: on that line of the
    paper, or a paper's own sum where it is named."""
    value = abs(step.printed)
    if step.line_no is None:
        return named(value, printed)
    line = next((ln for ln in doc.lines if ln.line_no == step.line_no), None)
    if line is None:
        return False
    code = line.code.strip()
    rows = [i for i, r in enumerate(printed) if not code or code in r.codes]
    same_code = [ln.line_no for ln in doc.lines if ln.code.strip() == code]
    if code and len(rows) == len(same_code):  # lines of a code stand in the order they are printed: each on its own row
        rows = [rows[same_code.index(line.line_no)]]
    held = [_line_at(printed, i) for i in rows]
    if not held:
        return False
    if code:  # a line that cannot be placed stands only on what every row of its code prints
        direct = all(value in amounts for amounts in held)
    else:
        direct = any(value in amounts for amounts in held)
    return direct or (step.field == "patient_responsibility" and _adds_up(line)
                      and any(value in {a + b for a, b in combinations(amounts, 2)} for amounts in held))


def _adds_up(line: Line) -> bool:
    parts = (line.insurance_paid, line.adjustment, line.patient_responsibility)
    if line.charges is None or any(p is None for p in parts):
        return False
    return abs(sum((abs(p) for p in parts), abs(line.fa_discount or 0)) - line.charges) <= Decimal("0.01")


def last_balance(printed: list[Row]) -> Decimal | None:
    """The last balance a sheet prints, as the device reads it: the sheet's own last word on what is due."""
    found = [r for r in printed if BALANCE_WORDS.search(r.text) and not NOT_THE_BALANCE.search(r.text) and r.amounts]
    if not found:
        return None
    text = found[-1].text
    amounts = list(redact.AMOUNT_ON_LINE.finditer(text))
    if not amounts:
        return None
    value = parse_money(amounts[-1].group())
    if value is None:
        return None
    credit = text[:amounts[-1].start()].rstrip().endswith(("(", "-", "\u2212")) or text[amounts[-1].end():].lstrip()[:2].upper() in ("CR", "- ")
    if THIS_SERVICE.search(text) and not credit and not any(MOVED.search(r.text) for r in printed):
        return None  # what is left of one service says nothing about the sheet, unless it is money back or the sheet moved its balance
    return -abs(value) if credit else value
