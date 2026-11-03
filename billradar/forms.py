"""Papers the family signs and carries themselves, filled in on this device.

There are two: the hospital's public Financial Evaluation Form (2310-10040, a flat PDF with no form fields), where the
case's values are drawn beside the labels printed on the blank, and the appeal form of a made-up insurer, drawn from
nothing. Nothing is sent anywhere and no model sees these values. Each form also reports which fields it filled and
which the family still has to write by hand.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import Color
from reportlab.pdfgen import canvas

from billradar import appeal, checks, writer
from billradar.case import Case, Profile, Role
from billradar.policies import source

PAGE_H = 792.0  # Letter; pdftotext measures y from the top, reportlab from the bottom
INK = Color(0.05, 0.2, 0.45)
STAMP = Color(0.85, 0.15, 0.15, alpha=0.55)

MEMORIAL_FEF = {
    "account": (36, 122), "mr": (362, 122),
    "patient": (112, 146.5), "street": (112, 156.5), "phone": (406, 156.5),
    "city": (52, 166.5), "state": (274, 166.5), "zip": (418, 166.5),
    "row0": 280, "row_h": 16.2, "cols": (36, 228, 334, 434),
    "salary": (212, 412), "spouse": (212, 425.5), "other": (212, 439),
    "rent": (464, 412), "electricity": (464, 425.5), "phone_bill": (464, 439),
    "checking": (257, 477), "savings": (257, 489), "residence": (257, 501),
}


@dataclass
class FilledForm:
    pdf: bytes
    filled: list[str]  # which fields got a value
    left_for_you: list[str]  # which fields the family still has to write by hand


SHEET = (612, PAGE_H)
CENT = Decimal("0.01")
FAMILY_ROWS = 6  # the table on the blank has no room for a seventh
TABLE_LAYOUT = ("row0", "row_h", "cols")  # entries of MEMORIAL_FEF that are not a single field's place
LOCAL_MONEY = {"spouse": "spouse_monthly_gross", "other": "other_monthly_income", "rent": "rent",
               "electricity": "electricity", "phone_bill": "phone_bill", "checking": "checking", "savings": "savings",
               "residence": "residence_value"}  # form key -> field of LocalDetails


def _amount(x: Decimal | None) -> str:
    return "" if x is None else f"{x.quantize(CENT, rounding=ROUND_HALF_UP):,.2f}"


def _hospital_account(case: Case) -> str:
    """The account number to print. The mother's bills beat anyone else's, then a covered [ACCT...] number beats a
    printed guarantor code, then the earlier bill wins. A token this device cannot resolve stays off the paper."""
    numbered = [b for b in checks.after_stay_bills(case) if b.account_ref]
    numbered = numbered or [b for b in case.bills() if b.account_ref]
    if not numbered:
        return ""

    def rank(bill) -> tuple[bool, bool]:
        return case.profile.role_of(bill.patient) != Role.MOTHER, not bill.account_ref.startswith("[ACCT")

    ref = min(numbered, key=rank).account_ref  # min keeps the first of equals
    tokens = case.profile.local.tokens
    return tokens.get(ref.strip("[]"), "" if ref.startswith("[") else ref)


def _family_rows(profile: Profile) -> dict[str, str]:
    """One row per named person, then blank rows for those the household counts but the case does not name."""
    named = ["|".join((p.name, p.birth_date, p.relationship, p.employer)) for p in profile.people[:FAMILY_ROWS]]
    blanks = [""] * (min(profile.household_size or 0, FAMILY_ROWS) - len(named))
    return {f"member{i}": row for i, row in enumerate(named + blanks)}


def memorial_values(case: Case) -> dict[str, str]:
    profile = case.profile
    local = profile.local
    return {
        "account": _hospital_account(case),
        "mr": "",  # the case has no medical record number
        "patient": next((p.name for p in profile.people if p.role == Role.MOTHER), ""),
        "street": local.street, "phone": local.phone, "city": local.city, "state": local.state, "zip": local.zip,
        "salary": _amount(profile.annual_income / 12),  # exact division first: cents are rounded once, in _amount
        **{key: _amount(getattr(local, field)) for key, field in LOCAL_MONEY.items()},
        **_family_rows(profile),
    }


def _memorial_layer(case: Case, values: dict[str, str], fields: list[str]):
    """The values, and on a sample case its margin stamps, as a page to lay over the blank."""
    out = io.BytesIO()
    c = canvas.Canvas(out, pagesize=SHEET)
    c.setFillColor(INK)
    c.setFont("Helvetica", 9.5)
    for key in fields:
        x, from_top = MEMORIAL_FEF[key]
        if values[key]:
            c.drawString(x, PAGE_H - from_top, values[key])
    for i in range(FAMILY_ROWS):
        y = PAGE_H - (MEMORIAL_FEF["row0"] + i * MEMORIAL_FEF["row_h"])
        for x, cell in zip(MEMORIAL_FEF["cols"], values.get(f"member{i}", "").split("|")):
            if cell:
                c.drawString(x, y, cell)
    if case.demo:
        c.setFillColor(STAMP)
        c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(306, PAGE_H - 16,
                            "SAMPLE - FICTIONAL DATA · Filled by BillRadar for a demo. Not a real application.")
        rules = writer.demo_rules(case)
        if rules:
            c.setFont("Helvetica", 7)
            c.drawCentredString(306, 14, rules)
    c.showPage()
    c.save()
    return PdfReader(out).pages[0]


def fill_memorial(case: Case) -> FilledForm:
    blank = source.form_path("memorial-fef")
    if not blank.exists():
        raise FileNotFoundError("run scripts/fetch_policies.py to download the blank form")
    values = memorial_values(case)
    fields = [k for k in MEMORIAL_FEF if k not in TABLE_LAYOUT]
    rows = [k for k in (f"member{i}" for i in range(FAMILY_ROWS)) if k in values]

    pages = PdfReader(blank).pages
    pages[0].merge_page(_memorial_layer(case, values, fields))
    form = PdfWriter()  # a new file: the family's form carries none of the blank's properties
    for page in pages:
        form.add_page(page)
    out = io.BytesIO()
    form.write(out)

    everything = fields + rows
    return FilledForm(pdf=out.getvalue(),
                      filled=[k for k in everything if values[k]],
                      left_for_you=[k for k in everything if not values[k] and k != "mr"]
                      + ["signature", "date", "witness"])


# --- the insurer's member appeal form ------------------------------------------------------

APPEAL_FIELDS = [  # (key, label) in the order they appear on the form and on the copy of the portal
    ("patient_name", "Patient name"), ("member_id", "Member ID"), ("claim_number", "Claim number"),
    ("service_dates", "Date(s) of service"), ("provider", "Provider or hospital"),
    ("denial_date", "Date on the denial notice"), ("denial_codes", "Remark code(s) on the notice"),
    ("amount", "Amount in dispute ($)"), ("street", "Street address"), ("city", "City"), ("state", "State"),
    ("zip", "ZIP"), ("phone", "Phone"), ("reason", "Why you disagree"), ("attachments", "Documents attached"),
]


EDGE_RGB = (0.55, 0.6, 0.65)
LABEL_RGB = (0.35, 0.38, 0.42)
FIELD_GAP = 6


def _appeal_heading(c: canvas.Canvas, plan) -> None:
    c.setFont("Helvetica-Bold", 15)
    c.drawString(46, 744, plan.insurer)
    c.setFont("Helvetica", 11)
    c.drawString(46, 726, "Member Appeal Form")
    c.setFont("Helvetica", 8.5)
    for i, line in enumerate(plan.appeals_to):
        c.drawRightString(566, 748 - 11 * i, line)


def _appeal_fields(c: canvas.Canvas, values: dict[str, str]) -> float:
    """Draw every box, filled or not, and return the height just below the last one."""
    c.setStrokeColorRGB(*EDGE_RGB)
    top = 690
    for key, label in APPEAL_FIELDS:
        height = 34 if key == "reason" else 22
        c.rect(46, top - height, 520, height, stroke=1, fill=0)
        c.setFillColorRGB(*LABEL_RGB)
        c.setFont("Helvetica", 7.5)
        c.drawString(50, top - 9, label)
        if values.get(key):
            c.setFillColor(INK)
            c.setFont("Helvetica", 9.5)
            c.drawString(52, top - 19, values[key][:110])
        top -= height + FIELD_GAP
    return top


def _appeal_signature(c: canvas.Canvas, below: float) -> None:
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica", 8)
    c.drawString(46, below - 4, "By signing, I ask the plan to review its decision on the claim above.")
    c.line(46, below - 40, 346, below - 40)
    c.line(380, below - 40, 566, below - 40)
    c.drawString(46, below - 50, "Signature of member or authorized representative")
    c.drawString(380, below - 50, "Date")


def _appeal_stamp(c: canvas.Canvas, demo: bool) -> None:
    """Across the page on every copy: the insurer is not real, whatever the case is."""
    c.saveState()
    c.translate(306, 430)
    c.rotate(18)
    c.setFillColor(STAMP)
    c.setFont("Helvetica-Bold", 30)
    c.drawCentredString(0, 0, "SAMPLE - FICTIONAL DATA" if demo else "SAMPLE - FICTIONAL INSURER")
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(0, -22, "Demo form of a made-up insurer. Not a real appeal.")
    c.restoreState()


def fill_insurer_appeal(case: Case, plan, denial) -> FilledForm:
    values = appeal.form_values(case, plan, denial)
    out = io.BytesIO()
    c = canvas.Canvas(out, pagesize=SHEET, invariant=1)
    _appeal_heading(c, plan)
    _appeal_signature(c, _appeal_fields(c, values))
    _appeal_stamp(c, case.demo)
    c.showPage()
    c.save()

    keys = [key for key, _ in APPEAL_FIELDS]
    return FilledForm(pdf=out.getvalue(),
                      filled=[k for k in keys if values.get(k)],
                      left_for_you=[k for k in keys if not values.get(k)] + ["signature", "date"])
