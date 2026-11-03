"""Read-only second look at a finished report.

Every amount and date a finding states is worked out again here from the sheets, the policy file, the
family's profile and (for two kinds) the hospital's price file, never from the finding's own `math`.
The checker only reports: it does not change a finding or a letter. It also builds the request for the
second model and turns that model's answer into notes.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from billradar import checks, prices
from billradar import fpl, policy
from billradar import writer
from billradar.case import Case, DocKind, LocalDetails
from billradar.checks import Finding, Kind, Report
from billradar.ledger import name_words
from billradar.meta_client import MetaClient
from billradar.writer import Letter

CENT = Decimal("0.01")
RISKY_WORDS = ["diagnos", "treatment plan", "medical advice", "you should take", "we will send", "guarantee",
               "we promise", "you will get", "lawsuit", "sue "]


def _q(x: Decimal) -> Decimal:
    """Whole cents, a half cent going away from zero whatever the ambient rounding is."""
    return x.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass
class Issue:
    subject: str  # "F3 #1", "letter dispute", ...
    severity: str  # "error" (do not show as is), "doubt" (shown without its sum) or "note"
    what: str


@dataclass
class Verdict:
    issues: list[Issue] = field(default_factory=list)
    checked: int = 0
    model_notes: list[dict] = field(default_factory=list)
    checker: str = "Muse Wonder"  # the model that read the findings, as shown on screen

    @property
    def ok(self) -> bool:
        return not any(i.severity == "error" for i in self.issues)

    def errors_for(self, subject: str) -> list[Issue]:
        return [i for i in self.issues if i.severity == "error" and i.subject == subject]


def subject(f: Finding, n: int) -> str:
    """"F1 #2 on D3": the paper in the name, so a reviewer cannot pin one finding's note on its twin."""
    doc = f.evidence[0].doc_id if f.evidence else ""
    return f"{f.kind.value} #{n}" + (f" on {doc}" if doc else "")



def _line(case: Case, doc_id: str, line_no: int | None):
    """(paper, line) for a pointer; the paper alone when there is no line number or no such line."""
    paper = next((d for d in case.documents if d.doc_id == doc_id), None)
    if paper is None or line_no is None:
        return paper, None
    return paper, next((ln for ln in paper.lines if ln.line_no == line_no), None)


def _expect_e1(case: Case, f: Finding) -> Decimal | None:
    """What the bill asks above the insurance statements' shares, after the share a discount already took."""
    head, rest = f.evidence[0], f.evidence[1:]
    bill, bill_line = _line(case, head.doc_id, head.line_no)
    if bill_line is None or bill_line.patient_responsibility is None or not rest:
        return None
    others = []
    for e in rest:
        _, ln = _line(case, e.doc_id, e.line_no)
        if ln is None or ln.patient_responsibility is None:
            return None
        others.append(ln.patient_responsibility)
    gap = bill_line.patient_responsibility - sum(others, Decimal(0))
    discount, balance = bill.fa_discount, bill.patient_balance
    if discount and balance is not None:
        gap = gap * (balance / (balance + abs(discount)))
    return _q(gap)


def _tier_pct(case: Case) -> Decimal | None:
    """Discount percent of the first policy tier that fits the family's income."""
    pol = policy.load(case.policy_id)
    year = pol.fpg_year if pol.fpg_year is not None else fpl.latest_year()
    guide = fpl.guideline(case.profile.household_size, year)
    tenths = (case.profile.annual_income * 100 / guide).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    whole = int(tenths)
    for tier in pol.tiers:
        if whole <= tier.max_fpl_pct:
            return Decimal(tier.discount_pct)
    return None


def _letters(ref: str) -> str:
    return "".join(ch for ch in ref.upper() if ch.isalnum())


def _one_office(a, b) -> bool:
    x, y = name_words(a.provider), name_words(b.provider)
    return not x or not y or bool(x & y)


def _shares_add_up(a, b) -> bool:
    """A itemizes B: a bill with no balance of its own whose shares are B's balance."""
    if a.kind != DocKind.ITEMIZED_BILL or a.patient_balance is not None or a.amount_due_coupon is not None:
        return False
    shares = sum((ln.patient_responsibility for ln in a.lines if ln.patient_responsibility and ln.patient_responsibility > 0), Decimal(0))
    return shares > 0 and shares in (b.patient_balance, b.amount_due_coupon)


def _same_money(a, b) -> bool:
    if _letters(a.account_ref) and _letters(a.account_ref) == _letters(b.account_ref):
        return True
    if not _one_office(a, b) or (a.service_from and b.service_from and abs((a.service_from - b.service_from).days) > 7):
        return False
    return (bool(a.patient_balance) and a.patient_balance == b.patient_balance) or _shares_add_up(a, b) or _shares_add_up(b, a)


def _papers(case: Case, doc_id: str) -> list:
    """The checker's own walk: the bills that ask for the same money as this one, without the checks' book."""
    bills = case.bills()
    found = [b for b in bills if b.doc_id == doc_id]
    for b in bills:
        if b not in found and any(_same_money(b, x) for x in found):
            found.append(b)
    return found


def _ceiling(papers: list) -> Decimal | None:
    """What the papers ask from the family, read again: the newest paper that prints a sum."""
    newest = sorted(papers, key=lambda d: d.statement_date.toordinal() if d.statement_date else 0, reverse=True)
    for d in newest:
        if d.amount_due_coupon is not None or d.patient_balance is not None:
            if d.patient_balance is not None and d.due_from_insurance == d.patient_balance:
                return Decimal(0)
            return max(x for x in (d.amount_due_coupon, d.patient_balance, Decimal(0)) if x is not None)
    shares = [ln.patient_responsibility for d in papers for ln in d.lines[:] if d is papers[0] and (ln.patient_responsibility or 0) > 0]
    return sum(shares, Decimal(0)) if shares else None


def _the_bill(case: Case, f: Finding) -> str | None:
    """The bill a finding takes money from."""
    bills = {b.doc_id for b in case.bills()}
    target = next((e.doc_id for e in f.evidence if e.note == "no discount"), None)
    return target or next((e.doc_id for e in f.evidence if e.doc_id in bills), None)


DEBT_KINDS = (Kind.E1, Kind.E2, Kind.N1, Kind.C1, Kind.C2)


def _expect_discount(case: Case, f: Finding, report: Report) -> Decimal | None:
    target = next((e for e in f.evidence if e.note == "no discount"), None)
    if target is None:
        return None
    papers = _papers(case, target.doc_id)
    pct, ceiling = _tier_pct(case), _ceiling(papers)
    if pct is None or ceiling is None:
        return None
    ids = {p.doc_id for p in papers}
    taken = sum((x.amount for x in report.findings if x.kind in DEBT_KINDS and x.amount and _the_bill(case, x) in ids),
                Decimal(0))
    return _q((ceiling - taken) * pct / 100)


def _value(case: Case, step) -> Decimal | None:
    d, ln = _line(case, step.doc_id, step.line_no)
    holder = ln if step.line_no is not None else d
    return getattr(holder, step.field, None) if holder is not None else None


def _trace_problem(case: Case, f: Finding) -> str:
    if not f.trace:
        return "no trace to what the sheets print"
    for step in f.trace:
        if _value(case, step) != step.printed:
            where = f"line {step.line_no} of {step.doc_id}" if step.line_no else step.doc_id
            return f"{where} does not print {step.printed}"
    return ""


def _ceiling_doubts(case: Case, report: Report, names: list[str]) -> list[Issue]:
    """Sums on one debt are not more than the debt, and no printed line pays twice, on the checker's own path."""
    out, spent, lines = [], {}, set()
    for f, s in zip(report.findings, names):
        if f.amount is None or f.kind not in DEBT_KINDS + (Kind.F1, Kind.F3) or "cap" in f.math:
            continue
        doc_id = _the_bill(case, f)
        if doc_id is None:
            out.append(Issue(s, "doubt", "no bill in the papers asks for this"))
            continue
        line = f.evidence[1] if f.kind == Kind.E2 and len(f.evidence) > 1 else f.evidence[0]
        if f.kind in (Kind.E1, Kind.E2, Kind.C1):
            if (line.doc_id, line.line_no) in lines:
                out.append(Issue(s, "doubt", f"line {line.line_no} of {line.doc_id} is counted more than once"))
                continue
            lines.add((line.doc_id, line.line_no))
        papers = _papers(case, doc_id)
        key = tuple(sorted(p.doc_id for p in papers))
        ceiling = _ceiling(papers)
        if ceiling is None or spent.get(key, Decimal(0)) + f.amount > ceiling:
            out.append(Issue(s, "doubt", f"this is more than the papers ask ({ceiling})"))
            continue
        spent[key] = spent.get(key, Decimal(0)) + f.amount
    return out


def _paid_for(case: Case, stay: list, alone: bool) -> list:
    """Payments on the hospital's claims for this stay, read again. A doctor's statement does not count."""
    begin = min((b.service_from for b in stay if b.service_from), default=None)
    end = max((b.service_to or b.service_from for b in stay if b.service_from), default=None)
    out = []
    bills = {b.doc_id for b in case.bills()}
    for d in case.documents:
        facility = any(len(ln.code) == 4 and ln.code.startswith("0") and ln.code.isdigit() for ln in d.lines)
        named = bool(case.letterhead and name_words(case.letterhead) & name_words(d.provider))
        if d.kind == DocKind.EOB and not (facility or named):
            continue
        if d.kind != DocKind.EOB and not (d.doc_id in bills and (named or not case.letterhead or not d.provider)):
            continue
        printed = [ln.service_date for ln in d.lines if ln.service_date] + [x for x in (d.service_from, d.service_to) if x]
        inside = any(begin <= x <= end for x in printed) if printed and begin else alone
        if inside and d.insurance_payment_date:
            out.append(d.insurance_payment_date)
        elif inside and d.kind == DocKind.EOB and d.statement_date:
            out.append(d.statement_date)
    return out


_MONTH_DAYS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def _month_length(year: int, month: int) -> int:
    leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    return 29 if month == 2 and leap else _MONTH_DAYS[month - 1]


def _add_months(p, months: int):
    """Calendar months later, same day or the last day of a shorter month."""
    start = p.year * 12 + p.month - 1
    if not isinstance(months, int):
        raise TypeError("months must be a whole number")
    year, month0 = divmod(start + months, 12)
    return p.replace(year=year, month=month0 + 1, day=min(p.day, _month_length(year, month0 + 1)))


def _stays(bills: list) -> list[list]:
    """Bills grouped into stays: a bill joins the stay of the earliest bill when its service starts within 7 days
    of that one; bills with no service start make one last stay."""
    stays: list[list] = []
    began = None
    for b in sorted((b for b in bills if b.service_from), key=lambda b: b.service_from):
        if began is not None and (b.service_from - began).days <= 7:
            stays[-1].append(b)
        else:
            stays.append([b])
            began = b.service_from
    loose = [b for b in bills if not b.service_from]
    return stays + [loose] if loose else stays


def _stay_deadline(case: Case, window: dict, stay: list, only_stay: bool) -> date | None:
    marked = [b.statement_date for b in stay if b.first_after_discharge and b.statement_date]
    printed = marked or [b.statement_date for b in stay if b.statement_date]
    if not printed:
        return None
    first = min(printed)
    options = [first + timedelta(days=240)]
    after_statement = window.get("after_first_statement_days")
    if after_statement is not None:
        options.append(first + timedelta(days=after_statement))
    after_service = window.get("after_service_days")
    last_days = [b.service_to or b.service_from for b in stay if b.service_to or b.service_from]
    if after_service is not None and last_days:
        last = max(last_days)
        options.append(_add_months(last, 12) if after_service == 365 else last + timedelta(days=after_service))
    months = window.get("after_last_insurance_payment_months")
    payments = _paid_for(case, stay, only_stay) if months is not None else []
    if payments:
        options.append(_add_months(max(payments), months))
    return max(options)


def _expect_deadline(case: Case):
    """The date to apply by, worked out from the bills, the insurance papers and the policy's window."""
    window = policy.load(case.policy_id).window
    stays = _stays(checks.hospital_bills(case))
    deadlines = []
    for stay in stays:
        if not any(b.owed is not None and b.owed > 0 for b in stay):
            continue
        d = _stay_deadline(case, window, stay, len(stays) == 1)
        if d is not None:
            deadlines.append(d)
    if not deadlines:
        return None
    still_open = [d for d in deadlines if d >= case.today]
    return min(still_open) if still_open else max(deadlines)


def _names(report: Report) -> list[str]:
    """Subject names of the findings, each kind numbered from 1 in report order."""
    seen: dict[str, int] = {}
    out = []
    for f in report.findings:
        seen[f.kind.value] = seen.get(f.kind.value, 0) + 1
        out.append(subject(f, seen[f.kind.value]))
    return out


def _expect_e2(case: Case, f: Finding) -> Decimal | None:
    """The repeats are the 2nd, 4th... evidence lines: the first of them that prints a positive share."""
    for e in f.evidence[1::2]:
        _, ln = _line(case, e.doc_id, e.line_no)
        if ln is not None and ln.patient_responsibility is not None and ln.patient_responsibility > 0:
            return ln.patient_responsibility
    if f.math.get("pages") == "1" and case.profile.insured is False:  # a page double with no insurance: the charge itself
        _, ln = _line(case, f.evidence[1].doc_id, f.evidence[1].line_no)
        if ln is not None and ln.charges and ln.charges > 0:
            return ln.charges
    return None


def _expect_c1(case: Case, f: Finding) -> Decimal | None:
    """A charge above the hospital's published price: units x (gross - cash), at most what the line still asks."""
    index = prices.load(case.policy_id)
    if index is None:
        return None
    _, ln = _line(case, f.evidence[0].doc_id, f.evidence[0].line_no)
    if ln is None or not ln.charges:
        return None
    hit = prices.match(index, ln.code, ln.charges)
    if not isinstance(hit, tuple):
        return None
    listed, units = hit
    saving = _q(units * (listed.gross - listed.cash))
    asked = ln.patient_responsibility if ln.patient_responsibility is not None else ln.charges
    return min(saving, asked)


_DRG = re.compile(r"\s*(?:MS-?)?DRG\s*#?\s*", re.I)


def _expect_c2(case: Case, f: Finding) -> Decimal | None:
    """What the plan allowed above its published rate, at most the family's share of the line."""
    index = prices.load(case.policy_id)
    _, ln = _line(case, f.evidence[0].doc_id, f.evidence[0].line_no)
    if index is None or ln is None or ln.charges is None or ln.adjustment is None:
        return None
    drg = _DRG.match(ln.code)
    if drg:
        code_type, code = "MS-DRG", ln.code[drg.end():]
    else:
        code_type, code = f.math.get("code_type", ""), ln.code
    plan = case.profile.plan
    rates = {r.dollar for r in index.plan_rates(plan.payer, plan.plan_name, code_type, code.strip().upper())}
    if len(rates) != 1:
        return None
    over = _q(ln.charges - abs(ln.adjustment) - rates.pop())
    return min(over, ln.patient_responsibility or Decimal(0))


def _expect_n1(case: Case, report: Report, f: Finding, name: str, out: list[Issue]) -> Decimal | None:
    """What the bill still asks after what E1/E2 findings took off it and the shares the insurance lines print.
    Adds a doubt to `out` when a claim printed on the bill's papers has no insurance line behind it."""
    head = f.evidence[0]
    bill, _ = _line(case, head.doc_id, head.line_no)
    shares, answered = [], set()
    for e in f.evidence[1:]:
        _, ln = _line(case, e.doc_id, e.line_no)
        if ln is not None:
            answered.add(ln.claim_ref)
            if ln.patient_responsibility is not None:
                shares.append(ln.patient_responsibility)
    papers = _papers(case, head.doc_id)
    printed = {r for p in papers for r in [p.claim_ref, *(ln.claim_ref for ln in p.lines)] if r}
    if printed - answered:
        out.append(Issue(name, "doubt", "a claim on this bill has no insurance statement in the papers"))
    ceiling = _ceiling(papers)
    if bill is None or ceiling is None or not shares:
        return None
    ids = {p.doc_id for p in papers}
    taken = sum((x.amount for x in report.findings
                 if x.kind in (Kind.E1, Kind.E2) and x.amount and _the_bill(case, x) in ids), Decimal(0))
    return _q(ceiling - taken - sum(shares, Decimal(0)))


def _recompute_e1(case, report, f, name, out):
    return _expect_e1(case, f)


def _recompute_e2(case, report, f, name, out):
    return _expect_e2(case, f)


def _recompute_e3(case, report, f, name, out):
    """A credit stays taken off: the size of its line, or of the paper's balance when there is no such line."""
    head = f.evidence[0]
    paper, ln = _line(case, head.doc_id, head.line_no)
    if f.amount is not None and paper is not None:
        ceiling = _ceiling(_papers(case, paper.doc_id))
        if ceiling is not None and ceiling > 0:
            out.append(Issue(name, "doubt", "the papers of this account still ask for money"))
    held = ln.patient_responsibility if ln is not None else paper.patient_balance if paper is not None else None
    return abs(held) if held is not None else None


def _recompute_discount(case, report, f, name, out):
    return _expect_discount(case, f, report) if "fpl_pct" in f.math else None


def _recompute_c1(case, report, f, name, out):
    return _expect_c1(case, f) if f.amount is not None and f.evidence else None


def _recompute_c2(case, report, f, name, out):
    if f.amount is None or not f.evidence or case.profile.plan is None:
        return None
    return _expect_c2(case, f)


def _recompute_n1(case, report, f, name, out):
    return _expect_n1(case, report, f, name, out) if f.evidence else None


# Each recompute may add doubts to `out`, which come before the comparison; it returns the value or None.
_RECOMPUTE = {
    Kind.E1: _recompute_e1, Kind.E2: _recompute_e2, Kind.E3: _recompute_e3,
    Kind.F1: _recompute_discount, Kind.F3: _recompute_discount,
    Kind.C1: _recompute_c1, Kind.C2: _recompute_c2, Kind.N1: _recompute_n1,
}


def _deadline_issues(case: Case, f: Finding, name: str) -> list[Issue]:
    want = _expect_deadline(case)
    if f.deadline == want:
        return []
    return [Issue(name, "error", f"deadline {f.deadline} but the sheets and policy give {want}")]


def _kind_issues(case: Case, report: Report, f: Finding, name: str) -> list[Issue]:
    """The comparison of a finding's sum (or date) with the value worked out here, with the doubts that go before it."""
    if f.kind == Kind.F2:
        return _deadline_issues(case, f, name)
    out: list[Issue] = []
    recompute = _RECOMPUTE.get(f.kind)
    expected = recompute(case, report, f, name, out) if recompute else None
    if f.amount is None:
        return out
    if expected is None:
        if "cap" not in f.math:
            out.append(Issue(name, "note", "amount could not be recomputed independently"))
    elif expected != f.amount:
        out.append(Issue(name, "error", f"amount {f.amount} but recomputed from the sheets: {expected}"))
    return out


def _finding_issues(case: Case, report: Report, f: Finding, name: str) -> list[Issue]:
    out: list[Issue] = []
    if f.amount is not None:
        problem = _trace_problem(case, f)
        if problem:
            out.append(Issue(name, "doubt", problem))
    for e in f.evidence:
        paper, ln = _line(case, e.doc_id, e.line_no)
        if paper is None:
            out.append(Issue(name, "error", f"points to {e.doc_id}, which is not in the case"))
        elif e.line_no is not None and ln is None:
            out.append(Issue(name, "error", f"points to line {e.line_no} of {e.doc_id}, which does not exist"))
    for ref in f.policy_refs:
        if not policy.verified(ref):
            out.append(Issue(name, "error", f"quote {ref} is not on its page"))
    return out + _kind_issues(case, report, f, name)


def check_findings(case: Case, report: Report) -> Verdict:
    names = _names(report)
    v = Verdict(checked=len(report.findings))
    for f, name in zip(report.findings, names):
        v.issues += _finding_issues(case, report, f, name)
    v.issues += _ceiling_doubts(case, report, names)
    total = _q(sum((f.amount for f in report.findings if f.amount is not None), Decimal(0)))
    if total != report.total_may_come_off:
        v.issues.append(Issue("total", "error", f"total {report.total_may_come_off} but findings add up to {total}"))
    return v


_AMOUNT = re.compile(r"\$([\d,]+)\.(\d{2})")
_KNOWN = re.compile(r'"(-?\d{1,12}(?:\.\d+)?)"')
_TOKEN = re.compile(r"\[(?:ACCT|PATIENT|MEMBER)_\d+\]")


def _known_amounts(case: Case, report: Report) -> set[Decimal]:
    """Every number the case and the report print as a quoted token, to cents, with and without its sign."""
    known: set[Decimal] = set()
    for token in _KNOWN.findall(case.model_dump_json() + report.model_dump_json()):
        cents = Decimal(token).quantize(CENT)
        known.update((cents, abs(cents)))
    return known


def _letter_errors(letter: Letter, known: set[Decimal]) -> list[str]:
    """What is wrong in one letter's text: unknown amounts, unverified quotes, a left-in token, risky wording."""
    text = " ".join(p.text for p in letter.paragraphs)
    wrong = [f"${whole}.{cents} does not come from the case" for whole, cents in _AMOUNT.findall(text)
             if Decimal(f"{whole.replace(',', '')}.{cents}") not in known]
    wrong += [f"quote {ref} is not on its page" for ref in letter.refs if not policy.verified(ref)]
    if _TOKEN.search(text):
        wrong.append("a token is left in the letter instead of the real value")
    lowered = text.lower()
    wrong += [f"wording '{word.strip()}' sounds like advice or a promise" for word in RISKY_WORDS if word in lowered]
    return wrong


def check_letters(case: Case, report: Report, letters: list[Letter], v: Verdict | None = None) -> Verdict:
    v = Verdict() if v is None else v
    known = _known_amounts(case, report) if letters else set()
    for letter in letters:
        who = f"letter {letter.kind}"
        v.checked += 1
        v.issues += [Issue(who, "error", what) for what in _letter_errors(letter, known)]
        if letter.dropped:
            v.issues.append(Issue(who, "note", f"{len(letter.dropped)} paragraph(s) left out: quote not verified"))
    return v



MODEL = "muse-wonder-1.0"
REVIEW_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["items"],
    "properties": {"items": {"type": "array", "items": {
        "type": "object",
        "additionalProperties": False,
        "required": ["subject", "verdict", "reason"],
        "properties": {
            "subject": {"type": "string"},
            "verdict": {"type": "string", "enum": ["confirmed", "problem", "cannot_tell"]},
            "reason": {"type": "string"},
        },
    }}},
}
REVIEW_INSTRUCTIONS = """You are the second reader of the work done by BillRadar, an assistant that works with hospital bills and insurance statements. You only read and judge. You never rewrite a letter or a finding.

What you receive
- The family's case, as it was read from their papers. Its amounts are numbers.
- The errors BillRadar found (the findings). For each one you can see the sheets, the lines and the policy quotes it rests on.
- The letters.

What you return
Give one answer for every finding and every letter. Each answer is one of three verdicts:
- `confirmed`: every number, every date and every reference to a sheet follows from the case and from the quoted policy text.
- `problem`: something does not follow. Each of these is a problem: a wrong amount; a wrong date; a sheet or a line that does not say that; a quote that does not support the claim; wording that sounds like medical advice or promises an outcome. Say exactly what is wrong.
- `cannot_tell`: the case does not contain enough to check it.

Name the subject of each answer exactly as it is given in the input and write it the same way, for example "F3 #1" or "letter dispute".

Keep every answer short and specific.
"""


def redacted(case: Case) -> Case:
    """A copy with no name, birth date, employer or local detail; the papers (tokens only) are shared, not copied."""
    people = [p.model_copy(update={"name": "", "birth_date": "", "employer": ""}) for p in case.profile.people]
    profile = case.profile.model_copy(update={"people": people, "local": LocalDetails(),
                                              "context": list(case.profile.context)})
    return case.model_copy(update={"profile": profile})


def _quote_of(ref: str) -> dict:
    """The policy quote a reference points at; the policy is read before the fragment id is taken."""
    parts = ref.split("#")
    pol = policy.load(parts[0])
    fragment = pol.fragment(parts[1])
    return {"ref": ref, "page": fragment.page, "text": fragment.quote}


def _finding_entry(f: Finding, name: str) -> dict:
    return {
        "subject": name, "title": f.title, "detail": f.detail,
        "amount": None if f.amount is None else str(f.amount),
        "deadline": None if f.deadline is None else f.deadline.isoformat(),
        "evidence": [{"doc_id": e.doc_id, "line_no": e.line_no, "note": e.note} for e in f.evidence],
        "math": {k: x for k, x in f.math.items() if k != "why_unsure"},
        "quotes": [_quote_of(ref) for ref in f.policy_refs],
    }


def _reference(case: Case, report: Report) -> dict:
    """The guideline and the policy's discount table the second read checks the percent against."""
    pol = policy.load(case.policy_id)
    table = [{"up_to_percent_of_guideline": t.max_fpl_pct, "discount_percent": t.discount_pct,
              "quote": f"{pol.policy_id}#{t.fragment}"} for t in pol.tiers]
    year = pol.fpg_year if pol.fpg_year is not None else fpl.latest_year()
    size = case.profile.household_size
    guideline = {"year": year, "household_size": size, "amount": str(fpl.guideline(size, year)),
                 "source": fpl.SOURCE.get(year, ""), "annual_income": str(case.profile.annual_income),
                 "percent_of_guideline": str(report.fpl_pct)}
    return {"federal_poverty_guideline": guideline, "policy_discount_table": table}


def _request(user_text: str) -> dict:
    schema = {"type": "json_schema", "name": "billradar_review", "schema": REVIEW_SCHEMA, "strict": True}
    turns = [("developer", REVIEW_INSTRUCTIONS), ("user", user_text)]
    return {"model": MODEL, "store": False, "stream": True, "reasoning": {"effort": "medium"},
            "max_output_tokens": 19000, "text": {"format": schema},
            "input": [{"role": who, "content": [{"type": "input_text", "text": text}]} for who, text in turns]}


def review_body(case: Case, report: Report, letters: list[Letter]) -> dict:
    """The request for the second read. Its text is also the recording key of the call: do not reorder anything."""
    clean = redacted(case)
    sent = writer.all_letters(clean, report) if letters else []
    findings = [_finding_entry(f, name) for f, name in zip(report.findings, _names(report))]
    reference = _reference(case, report)
    payload = {
        "case": clean.model_dump(mode="json", exclude={"case_id": True, "profile": {"local": True}}),
        "reference": reference,
        "findings": findings,
        "letters": [{"subject": f"letter {x.kind}", "text": [p.text for p in x.paragraphs], "quotes": x.refs}
                    for x in sent],
    }
    return _request(json.dumps(payload, default=str))


def checker_name(client) -> str:
    """Screen name of the model that reviews."""
    return "Muse Wonder"


def model_review(client: MetaClient, case: Case, report: Report, letters: list[Letter], v: Verdict) -> Verdict:
    """Second read by the model: its answer becomes notes, never errors. When it calls a paper absent that the
    case really holds, code overrules it."""
    v.checker = checker_name(client)
    answer = json.loads(client.respond(review_body(case, report, letters), label="wonder:review").text)
    v.model_notes = answer.get("items", [])
    have = {d.doc_id for d in case.documents}
    for item in v.model_notes:
        if item.get("verdict") != "problem":
            continue
        who = item.get("subject", "?")
        reason = item.get("reason", "")
        wrong = sorted(_says_missing(reason) & have)
        if wrong:
            ids = ", ".join(wrong)
            item["verdict"] = "overruled"
            item["code_check"] = f"{ids} is in the case: the second read was wrong here"
            v.issues.append(Issue(who, "note", f"{v.checker} said {ids} does not exist; it does (checked by code)"))
        else:
            v.issues.append(Issue(who, "note", f"{v.checker}: {reason}"))
    return v


_MISSING = re.compile(r"(?i)\b([SD]\d{1,2})\b[^.;]{0,40}?\b(?:does not exist|doesn't exist|is not in the case|"
                      r"not (?:present|found) in the case|is missing from the case)")


def _says_missing(reason: str) -> set[str]:
    """Paper ids the second read calls absent: "References sheet S10 which does not exist" -> {"S10"}."""
    return {m.group(1).upper() for m in _MISSING.finditer(reason)}


def verify(case: Case, report: Report, letters: list[Letter]) -> Verdict:
    return check_letters(case, report, letters, check_findings(case, report))


# --- confidence (Я11) ---------------------------------------------------------------------

CONFIRMED = 0.7  # below this a finding is borderline: shown under "worth asking", without a sum


def subjects(report: Report) -> dict[int, str]:
    """Subject names ("F3 #1") of the findings as the checker numbered them, by object identity."""
    counts: dict[str, int] = {}
    out = {}
    for f in report.findings:
        counts[f.kind.value] = counts.get(f.kind.value, 0) + 1
        out[id(f)] = subject(f, counts[f.kind.value])
    return out


def confidence(case: Case, f: Finding, s: str, v: Verdict) -> tuple[float, list[str]]:
    """How sure we are, 0..1, and why it is less than 1. Starts at 1: the finding already passed the checker's
    errors (sheets, lines, quotes, recomputed amounts), else it would have been held back."""
    c, why = 1.0, []
    notes = [i.what for i in v.issues if i.subject == s and i.severity == "note"]
    if any("could not be recomputed" in n for n in notes):
        c -= 0.35  # a sum with no second path is not confirmed
        why.append("amount not recomputed on a second path")
    doubts = [i.what for i in v.issues if i.subject == s and i.severity == "doubt"]
    if doubts:
        c = min(c, 0.5)
        why += doubts
    if f.kind in (Kind.F1, Kind.F3) and any(r.endswith("#liquid-assets") for r in f.policy_refs) \
            and case.profile.liquid_assets is None:
        c -= 0.2
        why.append("free care also depends on savings we do not know")
    for item in v.model_notes:
        if item.get("subject") != s:
            continue
        if item.get("verdict") == "problem":
            c -= 0.4
            why.append(f"{v.checker}: {item.get('reason', '')}")
        elif item.get("verdict") == "cannot_tell":
            c -= 0.15
            why.append(f"{v.checker} could not check it from the papers")
    return round(max(0.0, min(1.0, c)), 2), why


def grade(case: Case, report: Report, v: Verdict, names: dict[int, str] | None = None) -> Report:
    """Put a confidence on every finding; a finding under CONFIRMED becomes borderline and moves to
    "worth asking" without its sum. Read-only on the content: titles, amounts and evidence stay as they are."""
    from billradar.checks import split_borderline
    names = names or subjects(report)
    graded = []
    for f in report.findings:
        c, why = confidence(case, f, names.get(id(f), ""), v)
        update = {"confidence": c, "severity": f.severity or "high"}
        if c < CONFIRMED:
            update |= {"severity": "borderline", "math": f.math | {"why_unsure": "; ".join(why)}}
        graded.append(f.model_copy(update=update))
    asking = [f if f.confidence is not None else f.model_copy(update={"confidence": 0.5})
              for f in report.worth_asking]
    return split_borderline(report.model_copy(update={"findings": graded, "worth_asking": asking}))
