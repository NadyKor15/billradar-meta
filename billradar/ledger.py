"""What the family is asked for, debt by debt, and what has already come off it.

A debt is every paper that asks for the same money: the statements of one account, an itemized copy with another
number but the same patient and balance, the pages of one statement. Two rules hold for every sum shown as confirmed:
  - a debt gives up no more than the papers ask from the family;
  - a sum needs a debt: a double line that only the insurance statement prints is not money the family was asked for.
What does not fit stays a finding, without a sum, with the reason. The checks take from the book in a fixed order, so
the discount is worked out on what is left.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from itertools import combinations

from pydantic import BaseModel

from billradar.case import Case, DocKind, Document, Line

SAME_STAY_DAYS = 7
GENERIC_NAME_WORDS = {"hospital", "health", "healthcare", "system", "systems", "regional", "medical", "center",
                      "centre", "the", "of", "inc", "llc", "pa", "and", "care", "group", "services", "south",
                      "north", "general", "community"}  # NOT memorial, baptist: they name the hospitals of our policies (n1-n3, 03.11)


class Step(BaseModel):
    """One printed value a sum stands on: where it is and what it was used for."""

    doc_id: str
    line_no: int | None = None
    field: str
    printed: Decimal
    role: str = ""


def line_step(doc: Document, line: Line, name: str, role: str) -> Step:
    return Step(doc_id=doc.doc_id, line_no=line.line_no, field=name, printed=getattr(line, name), role=role)


def account_key(ref: str) -> str:
    """One account as one key, however it was printed or read: "A-12" and "A12", "[ACCT_1]" and "[ACCT 1]"."""
    return re.sub(r"[^A-Z0-9]", "", ref.upper())


def who(doc: Document) -> str:
    """The patient token as one key: a reader may print PATIENT_1 as "PATIENT 1"."""
    return re.sub(r"[\s_]+", "_", (doc.patient or "").strip().upper())


def name_words(name: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", name.lower()) if len(w) > 2 and w not in GENERIC_NAME_WORDS}


def _same_office(a: Document, b: Document) -> bool:
    x, y = name_words(a.provider), name_words(b.provider)
    return not x or not y or bool(x & y)


# --- lines the plan took back ---------------------------------------------------------------

@dataclass
class Effective:
    lines: list[Line]
    unpaired: list[Line] = field(default_factory=list)  # a reversal with no line it cancels


def _cancels(rev: Line, ln: Line) -> bool:
    return (ln.charges == -rev.charges and ln.code == rev.code and ln.service_date == rev.service_date
            and (rev.patient_responsibility is None or ln.patient_responsibility is None
                 or ln.patient_responsibility == -rev.patient_responsibility))


def effective_lines(doc: Document) -> Effective:
    """A claim the plan reprocessed prints the old line, its reversal and the new line: only the new one stands."""
    kept = list(doc.lines)
    unpaired = []
    for rev in [ln for ln in doc.lines if (ln.charges or 0) < 0]:
        pair = next((ln for ln in kept if (ln.charges or 0) > 0 and _cancels(rev, ln)), None)
        kept = [ln for ln in kept if ln is not rev and ln is not pair]
        if pair is None:
            unpaired.append(rev)
    return Effective(kept, unpaired)


# --- debts -----------------------------------------------------------------------------------

@dataclass
class Debt:
    papers: list[Document]
    head: Document  # the paper that stands for the debt: the statement over the itemized bill, then the newest
    asked: Decimal | None  # None: the papers do not give one amount
    steps: list[Step]  # where `asked` is printed
    taken: Decimal = Decimal(0)

    @property
    def left(self) -> Decimal | None:
        return None if self.asked is None else self.asked - self.taken


def _rank(d: Document) -> tuple:
    return (d.kind == DocKind.HOSPITAL_STATEMENT, d.amount_due_coupon is not None, d.statement_date or date.min)


def _two_answers(d: Document) -> bool:
    return d.owed is not None and d.amount_due_coupon is not None and (d.owed == 0) != (d.amount_due_coupon == 0)


def _same_stay(a: Document, b: Document) -> bool:
    """Two papers can be one debt only for care close in time. A paper that prints no date of service says nothing."""
    return not a.service_from or not b.service_from or abs((a.service_from - b.service_from).days) <= SAME_STAY_DAYS


def _shares(d: Document) -> Decimal:
    return sum(((ln.patient_responsibility or Decimal(0)) for ln in d.lines if (ln.patient_responsibility or 0) > 0), Decimal(0))


def _adds_up_to(itemized: Document, other: Document) -> bool:
    """An itemized bill that prints no balance of its own: its shares are the balance another paper asks for."""
    return (itemized.kind == DocKind.ITEMIZED_BILL and itemized.patient_balance is None and itemized.amount_due_coupon is None
            and _shares(itemized) > 0 and _shares(itemized) in (other.patient_balance, other.amount_due_coupon))


def _same_money(a: Document, b: Document) -> bool:
    if who(a) != who(b) or not _same_office(a, b) or not _same_stay(a, b):
        return False
    return bool(a.patient_balance and a.patient_balance == b.patient_balance) or _adds_up_to(a, b) or _adds_up_to(b, a)


def _says(d: Document) -> tuple[Decimal, str] | None:
    """What one paper asks: a coupon for the whole account over a subtotal next to it."""
    if d.amount_due_coupon is not None and (d.owed is None or d.amount_due_coupon >= d.owed):
        return d.amount_due_coupon, "amount_due_coupon"
    return (max(d.owed, Decimal(0)), "patient_balance") if d.owed is not None else None


def _asked(papers: list[Document], head: Document) -> tuple[Decimal | None, list[Step]]:
    if any(_two_answers(d) for d in papers):
        return None, []
    for d in sorted(papers, key=lambda p: (p.statement_date or date.min, p.kind == DocKind.HOSPITAL_STATEMENT), reverse=True):
        if d.device_balance and d.amount_due_coupon is None:  # the models left it out: a sum does not stand on the OCR alone
            return None, []
        said = _says(d)
        if said:
            value, name = said
            return value, [Step(doc_id=d.doc_id, field=name, printed=getattr(d, name), role="what the papers ask")]
    shares = [ln for ln in head.lines if (ln.patient_responsibility or 0) > 0]
    if shares:
        return (sum((ln.patient_responsibility for ln in shares), Decimal(0)),
                [line_step(head, ln, "patient_responsibility", "what the papers ask") for ln in shares])
    return None, []


def _groups(bills: list[Document], runs: list[list[Document]]) -> list[list[Document]]:
    parent = {d.doc_id: d.doc_id for d in bills}

    def root(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def join(a: Document, b: Document) -> None:
        parent[root(a.doc_id)] = root(b.doc_id)

    for a, b in combinations(bills, 2):
        if (account_key(a.account_ref) and account_key(a.account_ref) == account_key(b.account_ref)) or _same_money(a, b):
            join(a, b)
    ids = {d.doc_id: d for d in bills}
    for run in runs:  # the pages of one statement: page 3 often prints no account and no patient
        in_run = [ids[d.doc_id] for d in run if d.doc_id in ids]
        for a, b in zip(in_run, in_run[1:]):
            join(a, b)
    out: dict[str, list[Document]] = {}
    for d in bills:
        out.setdefault(root(d.doc_id), []).append(d)
    return list(out.values())


class Book:
    def __init__(self, case: Case):
        from billradar.sheet_checks import page_runs
        self.debts: list[Debt] = []
        self._of: dict[str, Debt] = {}
        self.shaky = {d.doc_id for d in case.documents if d.unreadable or d.doubts}  # no sum stands on these
        for papers in _groups(case.bills(), page_runs(case)):
            head = max(papers, key=_rank)
            asked, steps = _asked(papers, head)
            debt = Debt(papers, head, asked, steps)
            self.debts.append(debt)
            self._of |= {p.doc_id: debt for p in papers}

    def debt(self, doc_id: str) -> Debt | None:
        return self._of.get(doc_id)

    def left(self, doc_id: str) -> Decimal | None:
        debt = self.debt(doc_id)
        return debt.left if debt else None

    def taken(self, doc_id: str) -> Decimal:
        debt = self.debt(doc_id)
        return debt.taken if debt else Decimal(0)

    def take(self, doc_id: str, amount: Decimal) -> str:
        """Takes the sum off the debt of this paper. Returns "" or why it cannot stand as a confirmed sum."""
        debt = self.debt(doc_id)
        if debt is None:
            return "no bill in your papers asks you for this"
        if debt.left is None:
            return "your papers do not give one amount you are asked for"
        if amount > debt.left:
            return f"it would take off more than the ${debt.left:,.2f} your papers still ask for"
        debt.taken += amount
        return ""

    def take_across(self, doc_ids: list[str], amount: Decimal) -> str:
        """A sum over several debts (the yearly cap): from each in turn, never more than all of them hold."""
        debts = list({id(self.debt(d)): self.debt(d) for d in doc_ids if self.debt(d)}.values())
        if any(d.left is None for d in debts) or not debts:
            return "your papers do not give one amount you are asked for"
        if amount > sum((d.left for d in debts), Decimal(0)):
            return "it would take off more than your papers still ask for"
        for d in debts:
            part = min(d.left, amount)
            d.taken += part
            amount -= part
        return ""
