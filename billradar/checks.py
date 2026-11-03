"""Money and deadline checks over one family's case: plain code, no model, every sum traceable to printed values.

`run` turns a `Case` into a `Report`. The checks share one `Book` of debts and take their sums off it in a fixed
order (doubles, credits, overcharges, out-of-network, prices, then the hospital's discount on what is left), so a
dollar is never counted twice. A sum that does not fit what the papers still ask stays as a question without a sum.
The texts, the `math` keys and their order are part of the contract: they go into the prompts of the verifying model.
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from billradar import days, fpl, ledger, policy
from billradar.case import Case, Document, DocKind, Line, Role
from billradar.ledger import SAME_STAY_DAYS as EPISODE_GAP_DAYS
from billradar.ledger import Book, Step, account_key, line_step
from billradar.ledger import name_words as _name_words
from billradar.ledger import who as _who

CENT = Decimal("0.01")


def _q(x: Decimal) -> Decimal:
    """Cents, halves away from zero. Infinity and values too wide for the context raise InvalidOperation."""
    return x.quantize(CENT, rounding=ROUND_HALF_UP)


def _add_months(d: date, months: int) -> date:
    """Same day of the month `months` away, or the last day of that month when it is shorter."""
    year, month0 = divmod(d.year * 12 + d.month - 1 + months, 12)
    if not 1 <= year <= 9999:
        raise ValueError(d)
    return date(year, month0 + 1, min(d.day, calendar.monthrange(year, month0 + 1)[1]))


def _ref(pol: policy.Policy, fragment: str) -> str:
    return f"{pol.policy_id}#{fragment}"


def _note(title: str, detail: str, evidence: list[Evidence] | None = None, refs: list[str] | None = None,
          math: dict[str, str] | None = None) -> Finding:
    """A no-money note: what was checked and why there is nothing to take off."""
    return Finding(kind=Kind.NM, title=title, detail=detail, evidence=evidence or [], policy_refs=refs or [],
                   math=math or {})


class Kind(StrEnum):
    E1 = "E1"
    E2 = "E2"
    E3 = "E3"
    E4 = "E4"
    B1 = "B1"
    B2 = "B2"  # a bill for the baby that no insurance statement covers
    P1 = "P1"
    F1 = "F1"
    F2 = "F2"
    F3 = "F3"
    N1 = "N1"
    A1 = "A1"
    I1 = "I1"
    C1 = "C1"
    C2 = "C2"
    NM = "NM"


class Evidence(BaseModel):
    doc_id: str
    line_no: int | None = None
    note: str = ""


class Finding(BaseModel):
    kind: Kind
    title: str
    detail: str
    amount: Decimal | None = None  # what may come off; None for dates and no-money notes
    deadline: date | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    policy_refs: list[str] = Field(default_factory=list)
    math: dict[str, str] = Field(default_factory=dict)  # every number the result came from
    trace: list[Step] = Field(default_factory=list)  # the printed values a sum stands on
    severity: Literal["high", "borderline"] | None = None  # borderline -> "worth asking", shown without a sum
    confidence: float | None = None  # from the verifier, 0..1; None until it has looked
    laws: list[str] = Field(default_factory=list)  # protection ids in policies, "<policy_id>#<fragment>"
    explain: str | None = None  # the finding in plain words, for the family


class Report(BaseModel):
    case_id: str
    policy_id: str
    fpl_pct: Decimal
    findings: list[Finding]
    no_money: list[Finding]
    held_back: list[Finding]  # cited quotes not verified -> not shown to the family
    total_may_come_off: Decimal
    apply_by: date | None
    worth_asking: list[Finding] = Field(default_factory=list)  # borderline: no sum, a question to ask
    apply_by_sure: bool = True  # False: the date stands, to be checked with the hospital
    not_sent: list[str] = Field(default_factory=list)  # sheets that stayed on the device: to photograph again


def episodes(bills: list[Document]) -> list[list[Document]]:
    """Bills grouped into hospital stays. A stay takes every bill whose service began within a week of the stay's
    first bill; bills with no service date make one last group. The papers are the same objects, the input is untouched."""
    dated = sorted((b for b in bills if b.service_from), key=lambda b: b.service_from)
    reach = timedelta(days=EPISODE_GAP_DAYS)
    groups: list[list[Document]] = []
    start = 0
    while start < len(dated):
        stop = start + 1
        while stop < len(dated) and dated[stop].service_from - dated[start].service_from <= reach:
            stop += 1
        groups.append(dated[start:stop])
        start = stop
    undated = [b for b in bills if not b.service_from]
    if undated:
        groups.append(undated)
    return groups


def _is_facility_code(code: str) -> bool:
    import re
    return bool(re.fullmatch(r"0\d{3}", code.strip()))


def is_hospital_bill(case: Case, doc: Document) -> bool:
    """Is this bill from the hospital whose policy we check (not from a doctors' group)?
    The hospital's name printed on its bills (`letterhead`) and the provider share a distinctive word."""
    if not case.letterhead or not doc.provider:
        return True
    return bool(_name_words(case.letterhead) & _name_words(doc.provider))


def one_office_per_account(docs: list[Document], letterhead: str) -> list[Document]:
    """Papers of one account come from one office. A doctor's statement often prints the hospital as the place of
    service ("Seaside Regional Hospital (IP)") while its coupon says "make check payable to Women First OB/GYN":
    when the papers of an account name the hospital and another office, the account is that office's."""
    if not letterhead:
        return docs
    home = _name_words(letterhead)
    office: dict[str, str] = {}
    for d in docs:
        acct = account_key(d.account_ref)
        if acct and d.provider and not (home & _name_words(d.provider)):
            office.setdefault(acct, d.provider)
    # a paper of that account read with the hospital's name or with no name at all is the office's too
    return [d.model_copy(update={"provider": office[account_key(d.account_ref)]})
            if account_key(d.account_ref) in office and (not d.provider or home & _name_words(d.provider)) else d for d in docs]


def hospital_bills(case: Case) -> list[Document]:
    return [b for b in case.bills() if is_hospital_bill(case, b)]


def one_per_account(bills: list[Document]) -> list[Document]:
    """A statement and an itemized bill of the same account are one debt, not two.
    Keep one paper per account: the statement over the itemized bill, then the newest."""
    keep: dict[str, Document] = {}
    loose = []
    for b in bills:
        acct = account_key(b.account_ref)
        if not acct:
            loose.append(b)
            continue
        cur = keep.get(acct)
        rank = (b.kind == DocKind.HOSPITAL_STATEMENT, b.statement_date or date.min)
        if cur is None or rank > (cur.kind == DocKind.HOSPITAL_STATEMENT, cur.statement_date or date.min):
            keep[acct] = b
    kept = [b for b in bills if b in loose or keep.get(account_key(b.account_ref)) is b]
    # the statement may carry a guarantor number and the itemized bill the account number: same patient and same
    # balance is the same debt too: one paper per (patient, balance), the statement over the itemized bill, the one
    # that prints a coupon amount, then the newest
    best: dict[tuple, Document] = {}
    for b in kept:
        if not b.patient_balance:
            continue
        k = (_who(b), b.patient_balance)
        rank = (b.kind == DocKind.HOSPITAL_STATEMENT, b.amount_due_coupon is not None, b.statement_date or date.min)
        cur = best.get(k)
        if cur is None or rank > (cur.kind == DocKind.HOSPITAL_STATEMENT, cur.amount_due_coupon is not None,
                                  cur.statement_date or date.min):
            best[k] = b
    return [b for b in kept if not b.patient_balance or best[(_who(b), b.patient_balance)] is b]


def _printed(d: Document) -> tuple | None:
    """What makes two papers the same paper: every number and reference on it, none of the words the reader may
    spell differently. None for a paper with no number on it: nothing says two of those are one."""
    money = (d.total_charges, d.insurance_paid, d.fa_discount, d.patient_balance, d.due_from_insurance, d.amount_due_coupon)
    lines = tuple((ln.service_date, ln.code.strip().upper(), ln.charges, ln.insurance_paid, ln.adjustment,
                   ln.fa_discount, ln.patient_responsibility) for ln in d.lines)
    if not lines and all(m is None for m in money):
        return None
    return (d.kind, _who(d), d.account_ref.strip(), d.claim_ref.strip(), d.statement_date, d.page_no, d.page_count, money, lines)


def distinct_documents(docs: list[Document]) -> tuple[list[Document], list[tuple[str, str]]]:
    """One sheet photographed twice, or a photo and a PDF of it, is one paper: every sum on it counts once.
    Returns the papers kept and (copy, kept) pairs."""
    first: dict[tuple, Document] = {}
    kept, copies = [], []
    for d in docs:
        key = _printed(d)
        if key is not None and key in first:
            copies.append((d.doc_id, first[key].doc_id))
            continue
        if key is not None:
            first[key] = d
        kept.append(d)
    return kept, copies


def has_discount(doc: Document) -> bool:
    """Help is already applied: a non-zero discount, of either sign, is printed on the sheet or on any of its lines."""
    printed = [doc.fa_discount, *(ln.fa_discount for ln in doc.lines)]
    return any(value is not None and value != 0 for value in printed)



def doubt(f: Finding, why: str) -> None:
    """The finding stays, without a sum: "worth checking", with the reason."""
    f.severity = "borderline"
    f.math["why_unsure"] = why


def settle(book: Book, f: Finding, doc_id: str) -> None:
    """A confirmed sum comes off its debt, or it is not confirmed. A sum resting on a sheet read with a doubt takes
    nothing off: it will be shown without a sum, and the discount is worked out on the whole debt."""
    unread = sorted({e.doc_id for e in f.evidence} & book.shaky)
    if unread and f.amount:
        doubt(f, f"{', '.join(unread)} could not be read in full: take a new photo of it")
    if f.amount and f.severity != "borderline" and (why := book.take(doc_id, f.amount)):
        doubt(f, why)


def _insurance_lines(case: Case, bill: Document, line: Line, used: set) -> tuple[Document, list[Line], bool] | None:
    """The insurance statement's line for this bill line; for a bill line with no code, every line of its claim.
    One insurance line answers for one bill line. The last value says the plan reversed a line of this claim
    without printing which."""
    for eob in case.eobs():
        if eob.patient and bill.patient and eob.patient != bill.patient:
            continue
        lines = ledger.effective_lines(eob)
        free = [el for el in lines.lines if (eob.doc_id, el.line_no) not in used]
        if line.claim_ref:
            claim = [el for el in free if el.claim_ref == line.claim_ref]
            hits = claim if not line.code else [el for el in claim if not el.code or el.code == line.code][:1]
        else:
            hits = [el for el in free if line.service_date and line.code and el.service_date == line.service_date
                    and el.code == line.code][:1]
        if hits:
            return eob, hits, any(u.claim_ref == hits[0].claim_ref for u in lines.unpaired)
    return None


def _overcharge(bill: Document, line: Line, eob: Document, theirs: list[Line], says: Decimal, diff: Decimal,
                evidence: list[Evidence], base: dict[str, str], reversal: bool, book: Book) -> Finding:
    """E1 for one bill line. On a sheet that prints a discount and a balance only the part of the overcharge the
    discount has not already covered is the family's."""
    asked = line.patient_responsibility
    amount = diff
    math = dict(base)
    trace = [line_step(bill, line, "patient_responsibility", "the bill asks")]
    trace += [line_step(eob, el, "patient_responsibility", "your insurance says") for el in theirs]
    balance, discount = bill.patient_balance, bill.fa_discount
    if balance is not None and discount:
        whole = balance + abs(discount)
        math["share_left_after_discount"] = f"{balance}/{whole}"
        if whole != 0:
            amount = _q(diff * balance / whole)
        trace.append(Step(doc_id=bill.doc_id, field="patient_balance", printed=balance, role="balance"))
        trace.append(Step(doc_id=bill.doc_id, field="fa_discount", printed=discount, role="discount"))
    math["counts_toward_total"] = str(amount)

    where = (f"{eob.doc_id}, line {theirs[0].line_no}" if len(theirs) == 1
             else f"{eob.doc_id}, lines {', '.join(str(el.line_no) for el in theirs)}")
    detail = (f"Line {line.line_no} on sheet {bill.doc_id} asks ${asked:,.2f}. Your insurance statement ({where}) "
              f"says you owe ${says:,.2f} for the same service.")
    if amount != diff:
        detail += f" Your discount already covers part of it, so ${amount:,.2f} of it is yours."
    f = Finding(kind=Kind.E1, title=f"Bill asks ${diff:,.2f} more than your insurance says", detail=detail,
                amount=amount, evidence=evidence, math=math, trace=trace)
    if reversal:
        doubt(f, "the insurance statement reverses a line of this claim without saying which one")
    settle(book, f, bill.doc_id)
    return f


def check_e1(case: Case, repeats: set, book: Book) -> tuple[list[Finding], list[Finding]]:
    """Bill lines that ask the family for more than the insurance statement leaves it, as E1 findings, and
    a note for each line where the two agree. One statement line answers one bill line, matched or not."""
    findings: list[Finding] = []
    matches: list[Finding] = []
    used: set = set()
    for bill in case.bills():
        for line in bill.lines:
            asked = line.patient_responsibility
            if asked is None or (bill.doc_id, line.line_no) in repeats:
                continue
            answer = _insurance_lines(case, bill, line, used)
            if answer is None:
                continue
            eob, theirs, reversal = answer
            if any(el.patient_responsibility is None for el in theirs):
                continue  # nothing to compare with: the statement lines stay free for the next bill line
            used.update((eob.doc_id, el.line_no) for el in theirs)
            says = sum((el.patient_responsibility for el in theirs), Decimal(0))
            diff = _q(asked - says)
            evidence = [Evidence(doc_id=bill.doc_id, line_no=line.line_no)]
            evidence += [Evidence(doc_id=eob.doc_id, line_no=el.line_no) for el in theirs]
            base = {"bill_patient_responsibility": str(asked), "eob_patient_responsibility": str(says),
                    "difference": str(diff)}
            if diff > 0:
                findings.append(_overcharge(bill, line, eob, theirs, says, diff, evidence, base, reversal, book))
            else:
                matches.append(_note(
                    f"Sheet {bill.doc_id[1:]} line {line.line_no} matches your insurance statement",
                    f"Both say ${asked:,.2f}. Nothing to dispute here.", evidence=evidence, math=base))
    return findings, matches



def _assistance_stop(case: Case, pol: policy.Policy, fpl_pct: Decimal, tier: policy.Tier | None,
                     total: Decimal) -> Finding | None:
    """The one answer that ends the check before any discount is worked out; None when the family can be helped."""
    profile = case.profile
    if profile.insured and not pol.covers_insured_balances:
        return _note("This hospital's policy does not cover what insurance leaves you to pay",
                     f"{pol.hospital}: financial assistance is for uninsured patients. Your copays, deductible and "
                     "coinsurance are not covered by it. Check the bill against your insurance statement instead.",
                     refs=[_ref(pol, "uninsured-only")])
    if tier is None:
        top = pol.tiers[-1] if pol.tiers else None
        return _note("Your income is above this policy's limit",
                     f"Your household income is {fpl_pct}% of the federal poverty guideline. "
                     f"This policy helps households up to {top.max_fpl_pct if top else 0}%.",
                     refs=[_ref(pol, top.fragment)] if top else [], math={"fpl_pct": str(fpl_pct)})
    limit = pol.liquid_assets_limit_for_free_care
    if (tier.discount_pct == 100 and limit is not None and profile.liquid_assets is not None
            and profile.liquid_assets >= limit):
        return _note("Free care needs savings under the policy's limit",
                     f"Your income fits the 100% level, but this policy also asks for savings under ${limit:,.0f}. "
                     "Ask the hospital how it treats your case.", refs=[_ref(pol, "liquid-assets")])
    minimum = pol.min_request_total
    if minimum is not None and total <= minimum:
        return _note(f"Balances are under the ${minimum:,.0f} minimum",
                     f"All your balances together are ${total:,.2f}. "
                     f"This policy considers requests of more than ${minimum:,.0f}.",
                     refs=[_ref(pol, "min-request")], math={"total_balance": str(total)})
    return None


def check_assistance(case: Case, pol: policy.Policy, fpl_pct: Decimal, book: Book) -> tuple[list[Finding], list[Finding]]:
    """The hospital's financial assistance. Each stay's bills without a discount get F1 (nothing applied in the
    stay) or F3 (a bill of the same stay has it), worked out on what is left of the debt after the checks before
    this one; then the yearly-income cap. Notes say why there is no help, or what is out of the policy's reach."""
    profile = case.profile
    # the hospital's debts that still ask the family for money, each with what its head paper is owed
    reviewed: list[tuple] = []
    for debt in book.debts:
        if is_hospital_bill(case, debt.head):
            owed = debt.head.owed or debt.asked or Decimal(0)
            if owed > 0:
                reviewed.append((debt, owed))
    # a hospital letter with no account number and no dates that asks exactly what an account of the hospital asks is
    # that account again (n2 S10: "a balance of $12,018.10 remains on this account"), not a second debt
    keyed = {owed for debt, owed in reviewed if ledger.account_key(debt.head.account_ref)}
    reviewed = [(debt, owed) for debt, owed in reviewed
                if ledger.account_key(debt.head.account_ref) or debt.head.service_from or owed not in keyed]
    # a debt with no single amount is worked out on its head's balance and confirms nothing
    lefts = [owed if debt.left is None else debt.left for debt, owed in reviewed]
    total = sum(lefts, Decimal(0))

    notes: list[Finding] = []
    for bill in one_per_account(hospital_bills(case)):
        if bill.due_from_insurance and not bill.owed:
            notes.append(_note(
                f"Sheet {bill.doc_id}: waiting for insurance",
                f"${bill.due_from_insurance:,.2f} is due from insurance, not from you, so nothing comes off it yet. "
                "If the plan refuses it, ask for the same help on this bill.",
                evidence=[Evidence(doc_id=bill.doc_id)]))
    doctors = [b for b in case.bills() if not is_hospital_bill(case, b) and (b.owed or 0) > 0]
    if doctors:
        names = sorted({b.provider for b in doctors})
        scope = next((frag for frag in ("facilities-only", "facility-only") if frag in pol.fragments), None)
        notes.append(_note(
            "Doctors' bills are outside the hospital's assistance policy",
            f"{', '.join(names)} bill separately. This policy covers the hospital and its own doctors only; "
            "ask each office whether it has its own help program.",
            evidence=[Evidence(doc_id=b.doc_id) for b in doctors], refs=[_ref(pol, scope)] if scope else []))
    if not reviewed:
        return [], notes

    tier = pol.tier_for(fpl_pct)
    stop = _assistance_stop(case, pol, fpl_pct, tier, total)
    if stop is not None:
        return [], [stop, *notes]

    limit = pol.liquid_assets_limit_for_free_care
    free_care = tier.discount_pct == 100 and limit is not None
    savings_unknown = free_care and profile.liquid_assets is None
    caveat = f" This level also needs savings under ${limit:,.0f}." if savings_unknown else ""
    refs = [_ref(pol, tier.fragment)]
    if profile.insured and pol.covers_insured_balances and "insured-balances" in pol.fragments:
        refs.append(_ref(pol, "insured-balances"))
    if free_care:
        refs.append(_ref(pol, "liquid-assets"))

    by_head = {debt.head.doc_id: (debt, owed) for debt, owed in reviewed}
    found: list[Finding] = []
    for stay in episodes([debt.head for debt, _ in reviewed]):
        helped = [b for b in stay if any(has_discount(p) for p in by_head[b.doc_id][0].papers)]
        helped_ids = {b.doc_id for b in helped}
        for bill in stay:
            if bill.doc_id in helped_ids:
                continue
            debt, owed = by_head[bill.doc_id]
            left = owed if debt.left is None else debt.left
            asks = left + debt.taken  # what the sheet asked before anything came off it
            saving = _q(left * Decimal(tier.discount_pct) / 100)
            math = {"balance": str(asks), "minus_overcharge": str(debt.taken), "fpl_pct": str(fpl_pct),
                    "discount_pct": str(tier.discount_pct), "saving": str(saving)}
            bare = Evidence(doc_id=bill.doc_id, note="no discount")
            if helped:
                other = helped[0]
                whose = "the baby's" if profile.role_of(bill.patient) == Role.NEWBORN else "this"
                kind, evidence = Kind.F3, [Evidence(doc_id=other.doc_id, note="discount applied"), bare]
                title = f"Discount on sheet {other.doc_id}, not on {whose} bill"
                detail = (f"Same hospital stay. Financial assistance is on sheet {other.doc_id}, but sheet "
                          f"{bill.doc_id} still asks ${asks:,.2f}. At your income level the policy gives "
                          f"{tier.discount_pct}% off.{caveat}")
            else:
                kind, evidence = Kind.F1, [bare]
                title = "You likely qualify for financial assistance"
                detail = (f"Household of {profile.household_size}, income ${profile.annual_income:,.0f}: "
                          f"{fpl_pct}% of the poverty guideline. The policy gives {tier.discount_pct}% off at "
                          f"this level. Sheet {bill.doc_id} has no discount yet.{caveat}")
            f = Finding(kind=kind, title=title, detail=detail, amount=saving, evidence=evidence,
                        policy_refs=list(refs), math=math, trace=list(debt.steps))
            if savings_unknown:
                doubt(f, f"free care also depends on savings we do not know:{caveat}")
            settle(book, f, bill.doc_id)
            found.append(f)

    cap_pct = pol.income_cap_pct
    if found and cap_pct is not None and "income-cap" in pol.fragments:
        cap = _q(profile.annual_income * Decimal(cap_pct) / 100)
        # unconfirmed sums count too; zeros add nothing and must not change the printed places of the rest
        still_owed = (sum((left for left in lefts if left), Decimal(0))
                      - sum((f.amount for f in found if f.amount), Decimal(0)))
        if still_owed > cap:
            heads = [debt.head.doc_id for debt, _ in reviewed]
            f = Finding(
                kind=Kind.F1, title=f"Capped at {cap_pct}% of your yearly income",
                detail=(f"After the discount you would still owe ${still_owed:,.2f}. "
                        f"The policy caps it at {cap_pct}% of household income: ${cap:,.2f}."),
                amount=_q(still_owed - cap), evidence=[Evidence(doc_id=h) for h in heads],
                policy_refs=[_ref(pol, "income-cap")],
                math={"owed_after_discount": str(still_owed), "cap": str(cap)},
                trace=[step for debt, _ in reviewed for step in debt.steps])
            if why := book.take_across(heads, f.amount):
                doubt(f, why)
            found.append(f)
    return found, notes



def after_stay_bills(case: Case) -> list[Document]:
    """Hospital bills for the stay itself: a statement for care that ended before the latest stay began (prenatal
    visits, say) is not the first bill after discharge, even when it came later."""
    bills = hospital_bills(case)
    starts = [b.service_from for b in bills if b.service_from]
    stay = max(starts, default=None)
    return [b for b in bills if not (stay and (b.service_to or b.service_from) and (b.service_to or b.service_from) < stay)]


@dataclass
class Window:
    """The time to apply for one stay's bills: every rule that gives a date, and the latest of them."""
    first: Document
    flagged: bool
    candidates: dict[str, date]
    deadline: date
    paid: tuple[date, str] | None = None  # the payment the window counts from, and the paper that prints it


def _after_service(day: date, n: int) -> date:
    """A policy's "one year" is a year, leap day or not; other periods are counted in days."""
    return _add_months(day, 12) if n == 365 else day + timedelta(days=n)


def _hospital_paper(case: Case, d: Document) -> bool:
    """A paper about the hospital's own claim: a doctor's insurance statement could push the date too late."""
    if d.kind == DocKind.EOB:
        return any(_is_facility_code(ln.code) for ln in d.lines) or bool(
            case.letterhead and _name_words(case.letterhead) & _name_words(d.provider))
    return d in case.bills() and is_hospital_bill(case, d)


def _dates_of_care(d: Document) -> list[date]:
    return [ln.service_date for ln in d.lines if ln.service_date] + [x for x in (d.service_from, d.service_to) if x]


def _about_this_stay(d: Document, group: list[Document], alone: bool) -> bool:
    """Lines of the paper fall inside the stay. A paper that prints no dates counts only when there is one stay."""
    dated = _dates_of_care(d)
    begin = [b.service_from for b in group if b.service_from]
    end = [b.service_to or b.service_from for b in group if b.service_to or b.service_from]
    if not dated or not begin:
        return alone
    return any(min(begin) <= x <= max(end) for x in dated)


def _payments(case: Case, group: list[Document], alone: bool) -> list[tuple[date, str]]:
    papers = [d for d in case.documents if _hospital_paper(case, d) and _about_this_stay(d, group, alone)]
    paid = [(d.insurance_payment_date, d.doc_id) for d in papers if d.insurance_payment_date]
    # Most EOBs print only their own date. For the hospital's claims that date stands for the payment.
    return paid + [(d.statement_date, d.doc_id) for d in papers
                   if d.kind == DocKind.EOB and not d.insurance_payment_date and d.statement_date]


DAYS_RULE = "policy: days after first bill"
SERVICE_RULE = "policy: one year after service"
FEDERAL_RULE = "federal: 240 days after first bill"


def _first_bill(stay: list[Document]) -> tuple[Document, bool]:
    """The bill the deadlines count from, and whether a sheet itself says it is the first after discharge: the
    earliest dated sheet so marked, else the earliest dated bill, else (no dates at all) the stay's first paper."""
    dated = [b for b in stay if b.statement_date]
    marked = [b for b in dated if b.first_after_discharge]
    pool = marked or dated
    return (min(pool, key=lambda b: b.statement_date) if pool else stay[0]), bool(marked)


def _stay_deadlines(case: Case, rule: dict, stay: list[Document], first: Document,
                    only_stay: bool) -> tuple[dict[str, date], tuple[date, str] | None]:
    """The dates the policy and the federal rule give for one stay, in a fixed order, and the insurance payment the
    payment rule counted from."""
    given: list[tuple[str, date]] = []
    billed = first.statement_date
    if "after_first_statement_days" in rule and billed:
        given.append((DAYS_RULE, billed + timedelta(days=rule["after_first_statement_days"])))
    care_ends = [b.service_to or b.service_from for b in stay if b.service_to or b.service_from]
    if "after_service_days" in rule and care_ends:
        given.append((SERVICE_RULE, _after_service(max(care_ends), rule["after_service_days"])))
    last_paid = None
    if "after_last_insurance_payment_months" in rule:
        payments = _payments(case, stay, only_stay)
        if payments:
            last_paid = max(payments)  # the latest date; on a tie the larger sheet name
            given.append((PAID_RULE, _add_months(last_paid[0], rule["after_last_insurance_payment_months"])))
    if billed:
        given.append((FEDERAL_RULE, billed + timedelta(days=240)))
    return dict(given), last_paid


def windows(case: Case, pol: policy.Policy) -> list[Window]:
    """One window per stay that still asks the family for money: each rule that can name a date gives a candidate
    and the family gets the latest. Soonest deadline first; stays with the same date keep their order."""
    stays = episodes(hospital_bills(case))  # paid stays too: they decide whether a paper without dates is about "the" stay
    found: list[Window] = []
    for stay in stays:
        if not any((b.owed or 0) > 0 for b in stay):
            continue
        first, flagged = _first_bill(stay)
        candidates, paid = _stay_deadlines(case, pol.window, stay, first, len(stays) == 1)
        if candidates:
            found.append(Window(first, flagged, candidates, max(candidates.values()), paid))
    return sorted(found, key=lambda w: w.deadline)


def _window_doubts(case: Case) -> tuple[list[str], list[str]]:
    """What can still move the date: bills of a stay with no bill date at all, and papers with a date the window counts
    from and nothing that says which stay they are about."""
    every = episodes(hospital_bills(case))
    undated = [b.doc_id for g in every if not any(b.statement_date for b in g) for b in g if (b.owed or 0) > 0]
    astray = [d.doc_id for d in case.documents if len(every) > 1 and _hospital_paper(case, d) and not _dates_of_care(d)
              and (d.insurance_payment_date or (d.kind == DocKind.EOB and d.statement_date))]
    return undated, astray


def nearest_window(found: list[Window], today: date) -> Window | None:
    """The soonest date still open: a stay's bills stay in the total until that stay's window closes. All gone: the last."""
    return next((w for w in found if not days.passed(w.deadline, today)), found[-1] if found else None)


def check_window(case: Case, pol: policy.Policy) -> Finding | None:
    found = windows(case, pol)
    chosen = nearest_window(found, case.today)
    if chosen is None:
        return None
    first = chosen.first
    refs = [f"{pol.policy_id}#{pol.window['fragment']}"] if pol.window else []
    refs.append("federal-501r#application-period")
    later = [w for w in found if w.deadline > chosen.deadline]
    detail = ((f"First bill after discharge: sheet {first.doc_id}, {first.statement_date:%b %-d, %Y}."
               + ("" if chosen.flagged else " No sheet says 'first bill', so we used the earliest hospital bill we have."))
              if first.statement_date else
              f"No paper gives the date of the first bill for this care (sheet {first.doc_id}), so we counted from the care itself."
              ) + (f" Bills for later care have a later date: {later[-1].deadline:%b %-d, %Y} (sheet {later[-1].first.doc_id})."
                   if later else "")
    misread = [b.doc_id for b in hospital_bills(case) if not b.statement_date and (b.doubts or b.unreadable) and b is not first]
    f = Finding(
        kind=Kind.F2, title=f"Apply by {chosen.deadline:%b %-d, %Y}", detail=detail, deadline=chosen.deadline,
        evidence=[Evidence(doc_id=first.doc_id, note="first bill after discharge")]
                 + [Evidence(doc_id=d, note="its date could not be read") for d in misread], policy_refs=refs,
        math={k: v.isoformat() for k, v in chosen.candidates.items()}
             | ({"paid_on": chosen.paid[0].isoformat(), "paid_sheet": chosen.paid[1]} if chosen.paid else {}))
    winner = max(chosen.candidates, key=lambda k: chosen.candidates[k])
    from_payment = chosen.paid and winner == PAID_RULE
    stands_in = from_payment and not any(d.insurance_payment_date == chosen.paid[0] for d in case.documents)
    f.detail += (f" This date is 12 months after {chosen.paid[0]:%b %-d, %Y} (sheet {chosen.paid[1]})." if from_payment
                 else f" This date counts from {COUNTS_FROM.get(winner, winner)}.")
    undated, astray = _window_doubts(case)
    if stands_in:
        doubt(f, f"no paper prints the payment date: this counts from the date of your plan's statement on {chosen.paid[1]}. "
                 "Check the date with the hospital")
    if undated:  # a new photo of the bill can move the date, so it is one to ask about, not one to count on
        doubt(f, f"{', '.join(undated)} shows no bill date: take a new photo of it")
        f.math["retake"] = ",".join(undated)
    elif astray:
        doubt(f, f"{', '.join(astray)} does not say which stay it is about, and it could move this date")
    return f


PAID_RULE = "policy: 12 months after last insurance payment"
COUNTS_FROM = {"policy: one year after service": "one year after your care", "policy: days after first bill": "the first bill",
               "federal: 240 days after first bill": "240 days after the first bill"}


def window_today(case: Case, report: Report) -> Report:
    """A report is stored, and the day moves on: when its date has gone by since, the date to apply by is the next one
    still open for the bills in the case. Only the date changes; the money was worked out once."""
    old = next((f for f in report.findings + report.worth_asking if f.kind == Kind.F2), None)
    if old is None:
        return report
    kept, _ = distinct_documents(plausible_dates(case).documents)
    fresh = check_window(case.model_copy(update={"documents": kept}), policy.load(case.policy_id))
    if fresh is None or fresh.deadline == old.deadline:
        return report
    new = old.model_copy(update={"title": fresh.title, "detail": fresh.detail, "deadline": fresh.deadline, "evidence": fresh.evidence,
                                 "math": fresh.math | {k: v for k, v in old.math.items() if k == "why_unsure"}})
    swap = lambda found: [new if f is old else f for f in found]
    return report.model_copy(update={"findings": swap(report.findings), "worth_asking": swap(report.worth_asking),
                                     "apply_by": new.deadline})


def plausible_dates(case: Case) -> Case:
    """A date after today cannot be on a paper already in the family's hands: it was misread, and it could move a
    deadline by months. It is left empty and the sheet goes back for a new photo. So is a bill dated before its service."""
    def seen(d: Document) -> Document:
        update: dict = {}
        said = []
        for name in ("statement_date", "service_from", "service_to", "insurance_payment_date"):
            value = getattr(d, name)
            if value and value > case.today:
                update[name] = None
                said.append(f"{d.doc_id}: {name} {value.isoformat()} is after today; left empty")
        lines = [ln.model_copy(update={"service_date": None}) if ln.service_date and ln.service_date > case.today else ln
                 for ln in d.lines]
        if lines != d.lines:
            update["lines"] = lines
            said.append(f"{d.doc_id}: a line's date is after today; left empty")
        begun = update.get("service_from", d.service_from)
        billed = update.get("statement_date", d.statement_date)
        if d.kind != DocKind.EOB and begun and billed and billed < begun:
            said.append(f"{d.doc_id}: dated {billed.isoformat()}, before the service it bills ({begun.isoformat()})")
        fresh = [x for x in said if x not in d.doubts]
        if fresh:
            update["doubts"] = d.doubts + fresh
        return d.model_copy(update=update) if update else d

    docs = [seen(d) for d in case.documents]
    return case if docs == case.documents else case.model_copy(update={"documents": docs})


# --- N1 / A1 / I1: protections the papers can show -------------------------------------------

SPECIALTY_WORDS = ("anesthes", "radiolog", "patholog", "neonat", "emergency")
OUT_OF_NETWORK_WORDS = ("out of network", "out-of-network", "non-participating", "nonparticipating", "non-par ")


def _out_of_network(case: Case, doc: Document) -> bool:
    if "out_of_network" in case.profile.context:
        return True
    texts = [ln.description.lower() for ln in doc.lines]
    for eob in case.eobs():
        texts += [ln.description.lower() for ln in eob.lines if ln.claim_ref and ln.claim_ref in _claims(doc)]
    return any(w in t for t in texts for w in OUT_OF_NETWORK_WORDS)


def _claims(doc: Document) -> set[str]:
    return {r for r in [doc.claim_ref, *(ln.claim_ref for ln in doc.lines)] if r}


def nsa_kind_of(case: Case, doc: Document) -> str | None:
    """'nsa-ancillary' for an out-of-network specialist's bill, 'nsa-emergency' for emergency care, else None."""
    if not case.profile.insured or is_hospital_bill(case, doc) and "er_visit" not in case.profile.context:
        return None
    provider = doc.provider.lower()
    if "er_visit" in case.profile.context or "emergency" in provider:
        return "nsa-emergency" if _out_of_network(case, doc) else None
    if any(w in provider for w in SPECIALTY_WORDS) and _out_of_network(case, doc):
        return "nsa-ancillary"
    return None


def check_nsa(case: Case, prior: list[Finding], book: Book) -> list[Finding]:
    """An out-of-network specialist or emergency bill. If E1 already caught the overcharge line by line,
    the law is added to that finding (the dollar is counted once). Otherwise what the debt asks is
    compared with what the insurance statement leaves the patient for the same claims."""
    from billradar import laws
    out: list[Finding] = []
    for debt in book.debts:
        bill = debt.head
        which = nsa_kind_of(case, bill)
        if not which or not (debt.asked or bill.owed or 0) > 0:
            continue
        ids = {p.doc_id for p in debt.papers}
        refs = laws.refs_for(which)
        caught = [f for f in prior if f.kind == Kind.E1 and f.evidence and f.evidence[0].doc_id in ids]
        for f in caught:
            f.laws = list(dict.fromkeys(f.laws + refs))
        if caught:
            continue
        claims = {c for p in debt.papers for c in _claims(p)}
        eob_lines = [(e, ln) for e in case.eobs() for ln in ledger.effective_lines(e).lines
                     if ln.claim_ref and ln.claim_ref in claims and ln.patient_responsibility is not None]
        cite = "45 CFR 149.420" if which == "nsa-ancillary" else "45 CFR 149.410"
        asks = debt.left if debt.left is not None else bill.owed  # what came off this debt before is not asked twice
        if not eob_lines:
            out.append(Finding(
                kind=Kind.N1, severity="borderline",
                title=f"Out-of-network bill from {bill.provider}: ask for in-network rates",
                detail=(f"Sheet {bill.doc_id} asks ${asks:,.2f}. Under the No Surprises Act ({cite}) "
                        "you owe only your in-network share. We found no insurance statement for it yet: ask your "
                        "insurance how much you owe for this claim."),
                evidence=[Evidence(doc_id=bill.doc_id)], laws=refs, policy_refs=refs,
                math={"patient_balance": str(asks)}))
            continue
        share = _q(sum((ln.patient_responsibility for _, ln in eob_lines), Decimal(0)))
        diff = _q(asks - share)
        if diff <= 0:
            continue
        out.append(f := Finding(
            kind=Kind.N1, severity="high",
            title=f"Out-of-network bill asks ${diff:,.2f} more than your in-network share",
            detail=(f"Sheet {bill.doc_id} from {bill.provider} asks ${asks:,.2f}. Your insurance "
                    f"statement leaves you ${share:,.2f} for the same claims. Under the No Surprises Act ({cite}) "
                    "this provider can bill you only your in-network share."),
            amount=diff, evidence=[Evidence(doc_id=bill.doc_id)] + [
                Evidence(doc_id=e.doc_id, line_no=ln.line_no) for e, ln in eob_lines],
            laws=refs, policy_refs=refs,
            trace=list(debt.steps) + [line_step(e, ln, "patient_responsibility", "your insurance says") for e, ln in eob_lines],
            math={"patient_balance": str(asks), "eob_patient_share": str(share),
                  "difference": str(diff)}))
        printed = {ln.claim_ref for _, ln in eob_lines}
        untold = sorted(claims - printed) or [str(ln.line_no) for p in debt.papers for ln in p.lines
                                              if (ln.patient_responsibility or 0) > 0 and not (ln.claim_ref or p.claim_ref)]
        if untold:  # a claim with no statement is not an overcharge: the plan has not said what is owed on it
            doubt(f, f"no insurance statement in your papers for {', '.join(untold)}")
        settle(book, f, bill.doc_id)
    return out


def check_appeal(case: Case, prior: list[Finding]) -> list[Finding]:
    """A denied claim line that leaves the family owing money. A claim already explained as the baby
    billed under mom's ID (B1) is left to B1: the fix there is a corrected claim, not an appeal."""
    from billradar import laws
    if not case.profile.insured:
        return []
    b1_lines = {(e.doc_id, e.line_no) for f in prior if f.kind == Kind.B1 for e in f.evidence}
    out = []
    for eob in case.eobs():
        b1_claims = {ln.claim_ref or eob.claim_ref for ln in eob.lines if (eob.doc_id, ln.line_no) in b1_lines}
        lines = [ln for ln in eob.lines if laws.denied(ln) and (ln.patient_responsibility or 0) > 0
                 and (ln.claim_ref or eob.claim_ref) not in b1_claims]
        if not lines or not eob.statement_date:
            continue
        codes = sorted({c.strip() for ln in lines for c in ln.denial_codes.split(",") if c.strip()})
        said = (f"Insurance statement {eob.doc_id} ({eob.statement_date:%b %-d, %Y}) paid nothing on "
                f"{len(lines)} line{'s' if len(lines) != 1 else ''} (code {', '.join(codes)}).")
        ev = [Evidence(doc_id=eob.doc_id, line_no=ln.line_no, note="denied") for ln in lines]
        if not laws.employer_plan(case, eob):  # 180 days is the rule for employer plans; others can give far fewer
            out.append(Finding(
                kind=Kind.A1, severity="borderline", title="Ask your plan for the last day to appeal",
                detail=(f"{said} An employer health plan must give you at least {laws.APPEAL_DAYS} days to appeal, "
                        "and other plans can give fewer. Ask your plan which date applies to you."),
                evidence=ev, laws=laws.refs_for("appeal-180-days"), policy_refs=[laws.APPEAL_REF],
                math={"notice_date": eob.statement_date.isoformat()}))
            continue
        deadline = laws.appeal_deadline(eob.statement_date)
        out.append(Finding(
            kind=Kind.A1, severity="high", title=f"Appeal the denial by {deadline:%b %-d, %Y}",
            detail=f"{said} An employer health plan must give you at least {laws.APPEAL_DAYS} days to appeal.",
            deadline=deadline, evidence=ev, laws=laws.refs_for("appeal-180-days"), policy_refs=[laws.APPEAL_REF],
            math={"notice_date": eob.statement_date.isoformat(), "days": str(laws.APPEAL_DAYS)}))
    return out


def check_itemized(case: Case) -> list[Finding]:
    from billradar import laws
    if laws.hospital(case).get("state") != "FL":
        return []
    itemized = {b.account_ref.strip() for b in case.bills() if b.kind == DocKind.ITEMIZED_BILL}
    same_debt = {(_who(b), b.patient_balance) for b in case.bills() if b.kind == DocKind.ITEMIZED_BILL}
    missing = [b for b in hospital_bills(case) if b.kind == DocKind.HOSPITAL_STATEMENT and (b.patient_balance or 0) > 0
               and not (b.account_ref.strip() and b.account_ref.strip() in itemized)
               and (_who(b), b.patient_balance) not in same_debt]  # its itemized bill is already in the pile
    if not missing or any(b.kind == DocKind.ITEMIZED_BILL and not b.account_ref.strip() for b in case.bills()):
        return []
    refs = laws.refs_for("itemized-bill-7-days")
    return [Finding(
        kind=Kind.I1, severity="borderline", title="Ask for the itemized bill",
        detail=(f"Sheet{'s' if len(missing) > 1 else ''} {', '.join(b.doc_id for b in missing)} "
                f"show{'' if len(missing) > 1 else 's'} a total without every charge. Line-by-line errors can hide "
                "there. A Florida hospital must send the itemized bill within 7 days of your request."),
        evidence=[Evidence(doc_id=b.doc_id, note="no itemized bill") for b in missing],
        laws=refs, policy_refs=refs, math={"letter": "itemized"})]


def check_cash(case: Case, repeats: set, book: Book) -> list[Finding]:
    """No insurance: each hospital line whose charge is units x the published gross charge, on a bill that
    shows no self-pay discount, should cost the published cash price. A code that is listed but whose charge
    fits no single published price is borderline: ask for the cash price, no sum."""
    from billradar import prices
    index = prices.load(case.policy_id)
    if case.profile.insured or index is None:
        return []
    out, seen = [], set()
    when = _published(index.last_updated_on)
    for bill in hospital_bills(case):
        if has_discount(bill) or (bill.owed or 0) <= 0:
            continue
        for ln in bill.lines:
            if not ln.code or not ln.charges or ln.charges <= 0 or ln.adjustment or (bill.doc_id, ln.line_no) in repeats:
                continue
            printed_twice = (id(book.debt(bill.doc_id)), ln.service_date, ln.code, ln.charges)
            if printed_twice in seen:  # the same line on the statement and on its itemized copy
                continue
            seen.add(printed_twice)
            hit = prices.match(index, ln.code, ln.charges)
            if hit is None:
                continue
            src = {"mrf_url": index.url, "mrf_updated": index.last_updated_on, "mrf_version": index.version}
            ev = [Evidence(doc_id=bill.doc_id, line_no=ln.line_no)]
            if hit == "ambiguous":
                cash = sorted({p.cash for p in index.candidates(ln.code)})
                out.append(Finding(
                    kind=Kind.C1, severity="borderline", title=f"Ask for the cash price of code {ln.code}",
                    detail=(f"Line {ln.line_no} on sheet {bill.doc_id} charges ${ln.charges:,.2f}. {index.hospital} "
                            f"publishes cash prices for this code from ${cash[0]:,.2f}"
                            + (f" to ${cash[-1]:,.2f}" if len(cash) > 1 else "")
                            + f" (prices as of the hospital's publication date, {when}). Ask which applies."),
                    evidence=ev, math=src | {"code": ln.code, "charge": str(ln.charges)}))
                continue
            price, units = hit
            amount = _q(units * (price.gross - price.cash))
            owed = ln.patient_responsibility if ln.patient_responsibility is not None else ln.charges
            amount = min(amount, owed)
            if amount <= 0:
                continue
            out.append(f := Finding(
                kind=Kind.C1, title=f"Cash price is ${amount:,.2f} lower on line {ln.line_no}",
                detail=(f"Line {ln.line_no} on sheet {bill.doc_id} charges ${ln.charges:,.2f}"
                        + (f" ({units} x ${price.gross:,.2f})" if units > 1 else "")
                        + f". {index.hospital} publishes ${price.cash:,.2f} as its cash price for "
                        f"{price.description} (code {price.code}), prices as of the hospital's publication "
                        f"date, {when}. Without insurance, ask to be billed the cash price."),
                amount=amount, evidence=ev, trace=[line_step(bill, ln, "charges", "the line's charge")],
                math=src | {"code": price.code, "code_type": price.code_type, "description": price.description,
                            "setting": price.setting, "gross": str(price.gross), "cash": str(price.cash),
                            "units": str(units), "charge": str(ln.charges), "mrf_row": str(price.row)}))
            settle(book, f, bill.doc_id)
    return out


DRG_CODE = re.compile(r"^(?:MS-?)?DRG\s*#?\s*(\d{3})$", re.I)


def check_plan_rate(case: Case, book: Book) -> list[Finding]:
    """Insured, with the plan named in the profile: what the plan allowed for a hospital claim line
    (charges minus the contract adjustment) against the rate the hospital publishes for that plan.

    Firm rates (case rate, fee schedule, per diem) with the family owing the whole allowed amount (a deductible)
    give a sum: the excess. Otherwise (coinsurance, or a rate the hospital computes as a percent of charges)
    the finding is borderline: ask the plan to reprocess, no sum."""
    from billradar import prices
    plan, index = case.profile.plan, prices.load(case.policy_id)
    if not case.profile.insured or plan is None or index is None:
        return []
    out = []
    when = _published(index.last_updated_on)
    for eob in case.eobs():
        if case.letterhead and eob.provider and not (_name_words(case.letterhead) & _name_words(eob.provider)):
            continue  # a doctor's claim: the hospital's file has the hospital's rates only
        for ln in eob.lines:
            if not ln.code or ln.charges is None or ln.adjustment is None:
                continue
            m = DRG_CODE.match(ln.code.strip())
            ctype, code = ("MS-DRG", m.group(1)) if m else (None, ln.code.strip().upper())
            found = (index.plan_rates(plan.payer, plan.plan_name, ctype, code) if ctype else
                     [r for t in prices.CODE_TYPES for r in index.plan_rates(plan.payer, plan.plan_name, t, code)])
            if not found:
                continue
            allowed = _q(ln.charges - abs(ln.adjustment))
            dollars = {r.dollar for r in found}
            rate = found[0]
            src = {"plan_payer": plan.payer, "plan_name": plan.plan_name, "code": code, "code_type": rate.code_type,
                   "allowed": str(allowed), "mrf_url": index.url, "mrf_updated": index.last_updated_on,
                   "mrf_version": index.version}
            ev = [Evidence(doc_id=eob.doc_id, line_no=ln.line_no)]
            label = f"{plan.payer} {plan.plan_name}"
            if len(dollars) > 1:
                if allowed > min(dollars):
                    out.append(Finding(
                        kind=Kind.C2, severity="borderline", title=f"Check the plan's rate for code {code}",
                        detail=(f"Your plan allowed ${allowed:,.2f} on line {ln.line_no} of {eob.doc_id}. "
                                f"{index.hospital} publishes several {label} rates for this code, from "
                                f"${min(dollars):,.2f} to ${max(dollars):,.2f} (prices as of the hospital's "
                                f"publication date, {when}). Ask the plan which applies."),
                        evidence=ev, math=src | {"rates": ",".join(str(d) for d in sorted(dollars))}))
                continue
            if allowed <= rate.dollar + Decimal("1.00"):
                continue
            excess = _q(allowed - rate.dollar)
            share = ln.patient_responsibility if ln.patient_responsibility is not None else Decimal(0)
            firm = rate.methodology in prices.FIRM
            sure = firm and share >= allowed  # the family owes all of it: every extra dollar is theirs
            amount = min(excess, share) if sure else None
            math = src | {"rate": str(rate.dollar), "methodology": rate.methodology, "description": rate.description,
                          "setting": rate.setting, "mrf_row": str(rate.row), "excess": str(excess),
                          "patient_share": str(share)}
            if not sure and share > 0:
                math["amount_if_confirmed"] = str(_q(share * excess / allowed))
            kind_of_rate = rate.methodology if firm else "an estimate the hospital computes from its charges"
            hers = [d for d in book.debts if _who(d.head) == _who(eob) and is_hospital_bill(case, d.head)]
            if len(hers) == 1:  # the debt this claim's money sits on: the family's hospital bill
                ev = ev + [Evidence(doc_id=hers[0].head.doc_id)]
            out.append(f := Finding(
                kind=Kind.C2, severity="high" if sure else "borderline",
                title=(f"Plan allowed ${excess:,.2f} over its published rate" if sure else
                       f"Plan allowed more than its published rate for code {code}"),
                detail=(f"Line {ln.line_no} of insurance statement {eob.doc_id}: the plan allowed ${allowed:,.2f}. "
                        f"{index.hospital} publishes ${rate.dollar:,.2f} for {label}, {rate.description} "
                        f"({kind_of_rate}), prices as of the hospital's publication date, {when}. "
                        + ("You were asked to pay the whole allowed amount, so the difference is yours to dispute."
                           if sure else "Ask the plan to reprocess the claim at the published rate.")),
                amount=amount, evidence=ev, math=math,
                trace=[line_step(eob, ln, n, "the plan's line") for n in ("charges", "adjustment", "patient_responsibility")
                       if getattr(ln, n) is not None]))
            if len(hers) == 1:
                settle(book, f, hers[0].head.doc_id)
            elif f.amount:
                doubt(f, "no single hospital bill in your papers carries this claim")
    return out


def _published(iso: str) -> str:
    try:
        return date.fromisoformat(iso).strftime("%b %-d, %Y")
    except ValueError:
        return iso or "date not given"


def _laws_for(case: Case, f: Finding) -> list[str]:
    from billradar import laws
    nonprofit = laws.hospital(case).get("nonprofit")
    extra: list[str] = []
    if f.kind in (Kind.F1, Kind.F3) and nonprofit:
        extra = laws.refs_for("agb-limit") + laws.refs_for("fap-refund")
    elif f.kind == Kind.F2 and nonprofit:
        extra = laws.refs_for("fap-240-days")
    return list(dict.fromkeys(f.laws + extra))



def _cleaned(case: Case) -> tuple[Case, list[tuple[str, str]]]:
    """The case as it is counted: no dates from the future, and one paper photographed twice is one paper.
    Returns it with the (copy, kept) pairs of the papers dropped."""
    work = plausible_dates(case)
    kept, copies = distinct_documents(work.documents)
    return (work.model_copy(update={"documents": kept}) if copies else work), copies


def _take_doubles_and_doubt_credits(sheet: list[Finding], book: Book) -> None:
    """Doubles come off their debts first. A credit takes nothing off: while the papers of its account ask money
    (what is printed, not what the doubles left of it) it is only a question."""
    for f in sheet:
        if f.kind == Kind.E2:
            settle(book, f, f.evidence[0].doc_id)
    for f in sheet:
        if f.kind != Kind.E3 or not f.amount or f.severity == "borderline":
            continue
        debt = book.debt(f.evidence[0].doc_id)
        if debt is not None and (debt.asked is None or debt.asked > 0):
            doubt(f, "this account also asks you for money: ask whether the credit is already taken off")


def _agreeing_lines(matches: list[Finding], candidates: list[Finding]) -> list[Finding]:
    """The "nothing to dispute" notes whose pair of lines carries no finding on either line. Line number 0 is
    no number: a finding on it flags nothing."""
    flagged = {(e.doc_id, e.line_no) for f in candidates for e in f.evidence if e.line_no}
    return [m for m in matches if not any((e.doc_id, e.line_no) in flagged for e in m.evidence)]


def _same_paper_notes(copies: list[tuple[str, str]]) -> list[Finding]:
    return [_note(f"{copy} is the same paper as {kept}", "We counted it once.",
                  evidence=[Evidence(doc_id=kept), Evidence(doc_id=copy, note="same paper")])
            for copy, kept in copies]


def _finish(candidates: list[Finding], work: Case, book: Book) -> tuple[list[Finding], list[Finding]]:
    """Laws, severity and plain words for every finding; a sum or date on a sheet read with a doubt becomes a
    question; a finding that cites a quote that does not verify is held back, with the reason in its text."""
    from billradar import explain
    shown: list[Finding] = []
    held_back: list[Finding] = []
    for f in candidates:
        f.laws = [ref for ref in _laws_for(work, f) if policy.verified(ref)]
        if f.severity != "borderline":
            f.severity = "high"
        if f.explain is None:
            f.explain = explain.finding(f.kind.value)
        unread = sorted({e.doc_id for e in f.evidence} & book.shaky)
        if unread and (f.amount is not None or f.deadline is not None):
            doubt(f, f"{', '.join(unread)} could not be read in full: take a new photo of it")
        unverified = [ref for ref in f.policy_refs if not policy.verified(ref)]
        if unverified:
            held_back.append(f.model_copy(update={"detail": f"{f.detail} [held back: unverified {', '.join(unverified)}]"}))
        else:
            shown.append(f)
    return shown, held_back


def run(case: Case) -> Report:
    """The whole review of a case. The order in which checks take money off the book is part of the result:
    doubles, credits, overcharges, out-of-network, prices, then the hospital's discount on what is left."""
    from billradar import sheet_checks  # sheet_checks imports this module: not at the top

    pol = policy.load(case.policy_id)
    year = pol.fpg_year if pol.fpg_year is not None else fpl.latest_year()
    pct = fpl.percent_of_guideline(case.profile.annual_income, case.profile.household_size, year)

    work, copies = _cleaned(case)
    book = Book(work)

    sheet = sheet_checks.run(work)
    _take_doubles_and_doubt_credits(sheet, book)
    # evidence comes in pairs (first print, repeat): the repeats are already off the debt as doubles
    repeats = {(e.doc_id, e.line_no) for f in sheet if f.kind == Kind.E2 for e in f.evidence[1::2]}

    overcharges, matches = check_e1(work, repeats, book)
    out_of_network = check_nsa(work, overcharges, book)
    cash = check_cash(work, repeats, book)
    plan_rate = check_plan_rate(work, book)
    help_found, help_notes = check_assistance(work, pol, pct, book)
    apply_by = check_window(work, pol) if help_found else None
    candidates = (overcharges + sheet + out_of_network + cash + plan_rate + help_found + ([apply_by] if apply_by else [])
                  + check_appeal(work, sheet) + check_itemized(work))

    notes = help_notes + _agreeing_lines(matches, candidates) + _same_paper_notes(copies)
    shown, held_back = _finish(candidates, work, book)
    report = Report(case_id=case.case_id, policy_id=case.policy_id, fpl_pct=pct, findings=shown,
                    no_money=[n for n in notes if all(policy.verified(ref) for ref in n.policy_refs)],
                    held_back=held_back, total_may_come_off=Decimal(0), apply_by=None)
    return split_borderline(report)


NO_SUM = {  # the words of a finding that lost its sum: a sum we do not stand behind is not in the sentence either
    Kind.E1: ("A line asks more than your insurance says",
              "This bill and your insurance statement do not agree on this line. Check them before you pay."),
    Kind.E2: ("The same service may be billed twice", "The same service appears twice. Ask the office to check it."),
    Kind.E3: ("There may be a credit on this account", "The papers show a credit. Ask the office whether it is still yours."),
    Kind.N1: ("Out-of-network bill: ask for your in-network share",
              "This bill and your insurance statement do not agree. Ask your insurance what your in-network share is."),
    Kind.C1: ("Ask for the cash price", "The hospital publishes a lower cash price for this line. Ask which price applies."),
    Kind.C2: ("Check the plan's rate", "The plan may have allowed more than the rate the hospital publishes. Ask the plan."),
}


def split_borderline(report: Report) -> Report:
    """Borderline findings move to `worth_asking` without a sum; the total counts confirmed money only."""
    sure, ask = [], list(report.worth_asking)
    for f in report.findings:
        if f.severity == "borderline":
            if f.amount is not None:
                title, detail = NO_SUM.get(f.kind, (f.title, f.detail))
                f = f.model_copy(update={"amount": None, "title": title, "detail": detail,
                                         "math": f.math | {"amount_if_confirmed": str(f.amount)}})
            ask.append(f)
        else:
            sure.append(f)
    total = sum((f.amount for f in sure if f.amount is not None), Decimal(0))
    apply_by = next((f.deadline for f in sure + ask if f.kind == Kind.F2), None)  # a doubted date is still the date to act by
    return report.model_copy(update={"findings": sure, "worth_asking": ask, "total_may_come_off": _q(total), "apply_by": apply_by,
                                     "apply_by_sure": not any(f.kind == Kind.F2 for f in ask)})


__all__ = ["run", "Report", "Finding", "Kind", "Evidence", "episodes", "DocKind"]
