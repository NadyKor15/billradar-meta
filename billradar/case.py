"""One family's case: what was read from their paper sheets and digital files, typed, next to their local profile.

The vision model only reads text. Amounts and dates become values here, in plain code, and text that is not exactly one
amount or one date has no value: nothing is guessed or cleaned up. No I/O, no network, no other billradar module.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


MINUS = "-−–"
AMOUNT = re.compile(
    rf"(?P<open>\()?\s*(?P<before>[{MINUS}])?\s*\$?\s*(?P<after>[{MINUS}])?\s*"
    r"(?P<number>(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{2})?|\.\d{2})"
    rf"\s*(?P<tail>[{MINUS}]|(?i:cr|credit))?\s*(?P<close>\))?")


def parse_money(text: str | None) -> Decimal | None:
    """The whole text must be an amount: '$3,215.40' -> 3215.40, '(312.40)', '$-40.00', '40.00-' and '40.00 CR' are
    negative. Anything else gives None and is never cleaned into a number: '$2,4' is a cut $2,4xx.xx, not $24, and
    '$[MEMBER_1].00' is a cover token, not $1."""
    if text is None:
        return None
    m = AMOUNT.fullmatch(text.strip())
    if m is None or bool(m["open"]) != bool(m["close"]):
        return None
    value = Decimal(m["number"].replace(",", "")).quantize(Decimal("0.01"))
    return -value if m["open"] or m["before"] or m["after"] or m["tail"] else value


# The two printed forms: separator, then each field in printed order with the digit counts it may have.
_DATE_FORMS = (
    ("-", {"year": (4,), "month": (2,), "day": (2,)}),
    ("/", {"month": (1, 2), "day": (1, 2), "year": (4,)}),
)


def parse_date(text: str | None) -> date | None:
    """The whole text must be one date, 2025-08-11 or 8/11/2025 (always month first), in digits of any script.

    Anything else gives None, a calendar day that does not exist too: deadlines hang on dates, so none is built from a
    part of the text. reader.py relies on None for a range. A non-empty value that is not text raises.
    """
    if not text:
        return None
    printed = text.strip()
    for separator, widths in _DATE_FORMS:
        pieces = printed.split(separator)
        if len(pieces) != len(widths):
            continue
        if all(piece.isdecimal() and len(piece) in allowed for piece, allowed in zip(pieces, widths.values())):
            try:
                return date(**{field: int(piece) for field, piece in zip(widths, pieces)})
            except ValueError:
                return None
    return None


class DocKind(StrEnum):
    HOSPITAL_STATEMENT = "hospital_statement"
    ITEMIZED_BILL = "itemized_bill"
    EOB = "eob"
    FA_LETTER = "fa_letter"
    PAYMENT_RECEIPT = "payment_receipt"
    OTHER = "other"


class Source(StrEnum):
    PAPER = "paper"
    PDF = "pdf"
    SCREENSHOT = "screenshot"


class Line(BaseModel):
    """One printed line: a charge on a bill, or a claim line on an EOB."""

    line_no: int
    service_date: date | None = None
    code: str = ""
    description: str = ""
    charges: Decimal | None = None
    insurance_paid: Decimal | None = None
    adjustment: Decimal | None = None
    fa_discount: Decimal | None = None
    patient_responsibility: Decimal | None = None
    claim_ref: str = ""
    denial_codes: str = ""  # remark/denial codes as printed, e.g. "X17" or "X05, X42"


class Document(BaseModel):
    doc_id: str  # "S1".."Sn" for paper sheets (number shown on screen), "D1".. for digital files
    source: Source
    kind: DocKind
    patient: str = ""  # a token from the local profile, e.g. "PATIENT_1"; never a real name
    provider: str = ""
    account_ref: str = ""
    claim_ref: str = ""
    statement_date: date | None = None
    service_from: date | None = None
    service_to: date | None = None
    first_after_discharge: bool = False
    insurance_payment_date: date | None = None
    total_charges: Decimal | None = None
    insurance_paid: Decimal | None = None
    fa_discount: Decimal | None = None
    patient_balance: Decimal | None = None
    due_from_insurance: Decimal | None = None  # what the bill says it is asking the insurer for, not the family
    amount_due_coupon: Decimal | None = None  # the "PAY THIS AMOUNT" box, when the sheet has one
    device_balance: bool = False  # the balance was read on the device: both model reads left it out
    member_ref: str = ""  # insurance member ID as printed (a token)
    page_no: int | None = None  # "Page 2 of 5" -> 2, 5
    page_count: int | None = None
    unreadable: bool = False  # the model could not read it; the family is asked for a new photo
    doubts: list[str] = Field(default_factory=list)  # read text that is no amount or date: no sum stands on this sheet
    lines: list[Line] = Field(default_factory=list)

    @property
    def owed(self) -> Decimal | None:
        """What the family is asked for. A balance that is all due from insurance is not theirs yet."""
        if self.patient_balance is not None and self.due_from_insurance == self.patient_balance:
            return Decimal(0)
        return self.patient_balance


class Role(StrEnum):
    MOTHER = "mother"
    NEWBORN = "newborn"
    PATIENT = "patient"  # an adult's own stay: surgery, an emergency visit
    OTHER = "other"


class Person(BaseModel):
    token: str
    role: Role
    name: str = ""  # shown on this device only; the cloud sees the token
    birth_date: str = ""  # local only, for the hospital form
    relationship: str = ""  # "Self", "Daughter", ... as the form asks
    employer: str = ""


class LocalDetails(BaseModel):
    """What only the family's letters and forms need. Never sent to any model."""

    street: str = ""
    city: str = ""
    state: str = ""
    zip: str = ""
    phone: str = ""
    spouse_monthly_gross: Decimal | None = None
    other_monthly_income: Decimal | None = None
    rent: Decimal | None = None
    electricity: Decimal | None = None
    phone_bill: Decimal | None = None
    checking: Decimal | None = None
    savings: Decimal | None = None
    residence_value: Decimal | None = None
    tokens: dict[str, str] = Field(default_factory=dict)  # "ACCT_1" -> the real account number


class Plan(BaseModel):
    """The family's health plan as the hospital's price file names it, e.g. Aetna / Qualified Health Plan."""

    payer: str
    plan_name: str


class Profile(BaseModel):
    """Kept on the device. Only tokens and the numbers the checks need."""

    household_size: int
    annual_income: Decimal
    liquid_assets: Decimal | None = None
    insured: bool = True
    people: list[Person] = Field(default_factory=list)
    local: LocalDetails = Field(default_factory=LocalDetails)
    context: list[str] = Field(default_factory=list)  # chips the family set, e.g. "er_visit", "out_of_network"
    plan: Plan | None = None  # to compare with the plan's rates in the hospital's public price file

    @field_validator("household_size")
    @classmethod
    def _size(cls, v: int) -> int:
        if v < 1:
            raise ValueError("household_size must be >= 1")
        return v

    def role_of(self, token: str) -> Role:
        """The role of the first person holding exactly this token, Role.OTHER when nobody does."""
        return next((person.role for person in self.people if person.token == token), Role.OTHER)


class Case(BaseModel):
    case_id: str
    letterhead: str = ""  # name printed on the sheets (demo: a fictional hospital)
    policy_id: str  # which real public policy the case is checked against
    today: date
    demo: bool = False  # sample data: every generated document carries a SAMPLE stamp
    profile: Profile
    documents: list[Document]

    def doc(self, doc_id: str) -> Document:
        """The case's own first document with this id. Callers catch the bare StopIteration when there is none."""
        for document in self.documents:
            if document.doc_id == doc_id:
                return document
        raise StopIteration

    def bills(self) -> list[Document]:
        """The hospital's bills in pile order. A kind left as plain text counts: a member equals its value."""
        return [d for d in self.documents if d.kind in (DocKind.HOSPITAL_STATEMENT, DocKind.ITEMIZED_BILL)]

    def eobs(self) -> list[Document]:
        """The insurer's letters in pile order, matched by value like bills()."""
        return [d for d in self.documents if d.kind == DocKind.EOB]
