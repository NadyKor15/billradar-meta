"""Checks that need no hospital policy: what the family's own papers say about each other.

Each check reads a case, leaves it as it is and returns new findings: a service billed twice (E2), a credit left on a
sheet (E3), one sheet naming two sums (E4), the baby's care under mom's insurance (B1), a bill for the baby with no
insurance statement behind it (B2) and missing pages (P1). The wording, the order of `evidence` and the order of the
`math` keys all travel into the review request, so they are part of the result.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from datetime import date
from decimal import Decimal

from billradar import ledger
from billradar.case import Case, DocKind, Document, Line, Role, Source
from billradar.checks import Evidence, Finding, Kind, is_hospital_bill
from billradar.ledger import line_step

# Newborn and neonatal care: CPT 9946x and 9947x; revenue codes 017x (nursery).


def _is_newborn_code(code: str) -> bool:
    c = code.strip().upper()
    return bool(re.fullmatch(r"994[67]\d", c) or re.fullmatch(r"0?17\d", c))


def _usd(value: Decimal) -> str:
    return f"${value:,.2f}"


def _day(value: date) -> str:
    return value.strftime("%b %-d, %Y")


def _sheet_no(doc_id: str) -> str:
    return doc_id[1:]


def _here(paper: Document, line: Line | None = None, note: str = "") -> Evidence:
    return Evidence(doc_id=paper.doc_id, line_no=line.line_no if line else None, note=note)


def _lent_days(lines: list[Line]) -> dict[tuple[str, Decimal | None], date]:
    """The one service day of each code and price on a paper. A twin with two different days lends none."""
    days: dict[tuple[str, Decimal | None], set[date]] = {}
    for ln in lines:
        if ln.code and ln.service_date:
            days.setdefault((ln.code.upper(), ln.charges), set()).add(ln.service_date)
    return {twin: next(iter(seen)) for twin, seen in days.items() if len(seen) == 1}


def _repeats(paper: Document) -> Iterator[tuple[Line, Line, date | None]]:
    """(first, repeated, day) for each line equal to a line above it on this paper, always measured from the first.

    An insurance statement keeps its undated lines (day None); any other paper drops a line that has no day of its own
    and none to borrow."""
    lines = ledger.effective_lines(paper).lines
    keeps_undated = paper.kind == DocKind.EOB
    lent = {} if keeps_undated else _lent_days(lines)
    firsts: dict[tuple[date | None, str, Decimal], Line] = {}
    for ln in lines:
        if not ln.code or ln.charges is None:
            continue
        code = ln.code.upper()
        day = ln.service_date or lent.get((code, ln.charges))
        if day is None and not keeps_undated:
            continue
        key = (day, code, ln.charges)
        if key in firsts:
            yield firsts[key], ln, day
        else:
            firsts[key] = ln


def _asked_again(line: Line) -> Decimal | None:
    share = line.patient_responsibility
    return share if share is not None and share > 0 else None


def _double(paper: Document, first: Line, second: Line, day: date) -> Finding:
    share = _asked_again(second)
    detail = f"Lines {first.line_no} and {second.line_no} are the same code {second.code} on {_day(day)} for {_usd(second.charges)} each."
    trace = []
    if share is not None:
        detail += f" You are asked to pay {_usd(share)} for the second one."
        trace.append(line_step(paper, second, "patient_responsibility", "asked for the second one"))
    return Finding(kind=Kind.E2, title=f"Same service billed twice on sheet {_sheet_no(paper.doc_id)}", detail=detail, amount=share,
                   evidence=[_here(paper, first), _here(paper, second)], trace=trace,
                   math={"code": second.code, "service_date": day.isoformat(), "charges": str(second.charges),
                         "second_patient_responsibility": "0" if share is None else str(share)})


def _join(finding: Finding, paper: Document, first: Line, second: Line) -> None:
    """The same double on another paper: one more proof, and the sum if the finding still has none."""
    finding.evidence += [_here(paper, first, "also twice here"), _here(paper, second)]
    share = _asked_again(second)
    if finding.amount is None and share is not None:
        finding.amount = share
        finding.math["second_patient_responsibility"] = str(share)
        finding.math["amount_from"] = paper.doc_id
        finding.trace.append(line_step(paper, second, "patient_responsibility", "your insurance shows for the second one"))
        finding.detail += f" Your insurance statement shows {_usd(share)} for the second one."


def _pages_of_one_bill(case: Case) -> list[list[Document]]:
    """Itemized pages of one bill: the same account and the same office. A late charge is often posted again on the
    last page, under a heading of its own."""
    groups: dict[tuple[str, frozenset], list[Document]] = {}
    for d in case.documents:
        key = ledger.account_key(d.account_ref)
        if d.kind == DocKind.ITEMIZED_BILL and key:
            groups.setdefault((key, frozenset(ledger.name_words(d.provider or ""))), []).append(d)
    return [pages for pages in groups.values() if len(pages) > 1]


def _page_double(case: Case, first_paper: Document, first: Line, paper: Document, second: Line, day: date) -> Finding:
    share = _asked_again(second)
    detail = (f"Sheet {_sheet_no(first_paper.doc_id)} line {first.line_no} and sheet {_sheet_no(paper.doc_id)} line "
              f"{second.line_no} are the same code {second.code} on {_day(day)} for {_usd(second.charges)} each, "
              "on two pages of one bill.")
    trace = []
    if share is not None:
        trace.append(line_step(paper, second, "patient_responsibility", "asked for the second one"))
    elif case.profile.insured is False and second.charges and second.charges > 0:
        share = second.charges  # no insurance on file: the family is asked the whole charge again
        trace.append(line_step(paper, second, "charges", "the second charge, asked in full with no insurance on file"))
    if share is not None:
        detail += f" You are asked to pay {_usd(share)} for the second one."
    return Finding(kind=Kind.E2, title=f"Same service billed twice on sheets {_sheet_no(first_paper.doc_id)} and "
                   f"{_sheet_no(paper.doc_id)}", detail=detail, amount=share,
                   evidence=[_here(first_paper, first), _here(paper, second)], trace=trace,
                   math={"code": second.code, "service_date": day.isoformat(), "charges": str(second.charges),
                         "second_patient_responsibility": str(_asked_again(second) or 0),
                         "second_charge_asked_in_full": "0" if share is None or _asked_again(second) else str(share), "pages": "1"})


def page_doubles(case: Case, found: list[Finding]) -> list[Finding]:
    """A line printed again on another page of the same bill, not already part of a double found on one paper."""
    taken = {(e.doc_id, e.line_no) for f in found for e in f.evidence}
    out: list[Finding] = []
    for pages in _pages_of_one_bill(case):
        firsts: dict[tuple[date, str, Decimal], tuple[Document, Line]] = {}
        for paper in pages:
            lines = ledger.effective_lines(paper).lines
            lent = _lent_days(lines)
            for ln in lines:
                if not ln.code or ln.charges is None:
                    continue
                day = ln.service_date or lent.get((ln.code.upper(), ln.charges))
                if day is None:
                    continue
                key = (day, ln.code.upper(), ln.charges)
                if key not in firsts:
                    firsts[key] = (paper, ln)
                    continue
                first_paper, first = firsts[key]
                if first_paper.doc_id == paper.doc_id or {(first_paper.doc_id, first.line_no), (paper.doc_id, ln.line_no)} & taken:
                    continue
                out.append(_page_double(case, first_paper, first, paper, ln, day))
                taken |= {(first_paper.doc_id, first.line_no), (paper.doc_id, ln.line_no)}
    return out


def duplicates(case: Case) -> list[Finding]:
    """A service billed twice counts once, however many papers print the double: bills first, statements join them."""
    found: list[Finding] = []
    latest_of_day: dict[tuple[date, str], Finding] = {}
    latest_of_price: dict[tuple[str, Decimal], Finding] = {}
    for paper in sorted(case.documents, key=lambda d: d.kind == DocKind.EOB):
        for first, second, day in _repeats(paper):
            code = second.code.upper()
            earlier = latest_of_price.get((code, second.charges)) if day is None else latest_of_day.get((day, code))
            if earlier is not None and earlier.evidence[0].doc_id != paper.doc_id:
                _join(earlier, paper, first, second)
            elif day is not None:
                latest_of_day[day, code] = latest_of_price[code, second.charges] = _double(paper, first, second, day)
                found.append(latest_of_day[day, code])
            elif earlier is not None:
                raise TypeError(f"an undated double on {paper.doc_id} has no day to name")
    return found + page_doubles(case, found)


INSIDE = "The sum this sheet asks for looks like it already took this credit off, so it is not extra money back."
PAYMENT_LINE = re.compile(r"(?i)^\W*(?:\w+\s+)?payments?\b|\bpayment received\b|^\W*paid\b|\bthank you\b")


def _newest_first(bills: list[Document]) -> list[Document]:
    dated = sorted((b for b in bills if b.statement_date), key=lambda b: b.statement_date, reverse=True)
    return dated + [b for b in bills if not b.statement_date]


def _same_account(a: Document, b: Document) -> bool:
    key = ledger.account_key(a.account_ref)
    return bool(key) and key == ledger.account_key(b.account_ref)


def _paper_asking(case: Case, counts: Callable[[Document], bool]) -> Document | None:
    return next((d for d in case.documents if (d.amount_due_coupon or 0) > 0 and counts(d)), None)


def _to_check(credit: Decimal, opening: str, sheet_asks: str, payer: Document, evidence: list[Evidence], step: ledger.Step,
              printed: tuple[str, Decimal]) -> Finding:
    """A sum asked on a paper seems to hold this credit already: something to check, not money back."""
    detail = (f"{opening} Sheet {_sheet_no(payer.doc_id)}{sheet_asks} asks {_usd(payer.amount_due_coupon)}, which looks to include it "
              "already. Check that it stays there; it is not counted as money back.")
    return Finding(kind=Kind.E3, severity="borderline", title=f"Check the {_usd(credit)} credit stays taken off", detail=detail,
                   evidence=evidence, trace=[step], explain=INSIDE, math={printed[0]: str(printed[1]), "applied_on": payer.doc_id})


def _balance_credit(case: Case, sheet: Document) -> Finding:
    balance = sheet.patient_balance
    credit = abs(balance)
    step = ledger.Step(doc_id=sheet.doc_id, field="patient_balance", printed=balance, role="balance in your favor")
    payer = _paper_asking(case, lambda d: d is not sheet and _same_account(d, sheet))
    no = _sheet_no(sheet.doc_id)
    if payer is None:
        return Finding(kind=Kind.E3, title=f"You have a {_usd(credit)} credit on sheet {no}",
                       detail="The balance is in your favor. Ask for a refund instead of leaving it on the account.",
                       amount=credit, evidence=[_here(sheet)], trace=[step], math={"patient_balance": str(balance)})
    return _to_check(credit, f"Sheet {no} shows a {_usd(credit)} credit.", " of the same account", payer,
                     [_here(sheet), _here(payer)], step, ("patient_balance", balance))


def _credit_line(case: Case, sheet: Document, line: Line) -> Finding:
    share = line.patient_responsibility
    credit = abs(share)
    step = line_step(sheet, line, "patient_responsibility", "a credit on the line")
    payer = _paper_asking(case, lambda d: d is sheet or _same_account(d, sheet))
    if payer is not None:
        opening = f"Line {line.line_no} of sheet {_sheet_no(sheet.doc_id)} shows a {_usd(credit)} credit."
        return _to_check(credit, opening, "", payer, [_here(sheet, line), _here(payer)], step, ("line_patient_responsibility", share))
    words = f" ({line.description})" if line.description else ""
    return Finding(kind=Kind.E3, severity="borderline", title=f"{_usd(credit)} you overpaid is still on sheet {_sheet_no(sheet.doc_id)}",
                   detail=f"Line {line.line_no} shows a credit of {_usd(credit)}{words}. Ask the office to refund it or to show it taken off what you owe.",
                   amount=credit, evidence=[_here(sheet, line)], trace=[step],
                   math={"line_patient_responsibility": str(share),
                         "why_unsure": "a credit line may already be inside the balance this sheet asks"})


def credits(case: Case) -> list[Finding]:
    """Money in the family's favor: one credit per account, one finding per printed credit line, bills only."""
    found: list[Finding] = []
    accounts_settled: set[str] = set()
    lines_counted: set[tuple[str, str, date | None, Decimal]] = set()
    for sheet in _newest_first(case.bills()):
        account = ledger.account_key(sheet.account_ref) or sheet.doc_id
        if (sheet.patient_balance or 0) < 0:
            if account not in accounts_settled:
                accounts_settled.add(account)
                found.append(_balance_credit(case, sheet))
            continue
        for line in sheet.lines:
            share = line.patient_responsibility
            mark = (account, line.code, line.service_date, share)
            if (share or 0) < 0 and not PAYMENT_LINE.search(line.description) and mark not in lines_counted:
                lines_counted.add(mark)
                found.append(_credit_line(case, sheet, line))
    return found


def two_amounts(case: Case) -> list[Finding]:
    """One side of a sheet says nothing is owed while the other asks a sum. Two sums side by side are normal."""
    found: list[Finding] = []
    for paper in case.documents:
        balance, coupon = paper.patient_balance, paper.amount_due_coupon
        if balance is None or coupon is None or (balance == 0) == (coupon == 0):
            continue
        found.append(Finding(kind=Kind.E4, title=f"Sheet {_sheet_no(paper.doc_id)} asks two different amounts",
                             detail=(f"It says your balance is {_usd(balance)} and also asks you to pay {_usd(coupon)}. "
                                     "Do not pay until the office explains which one is right."),
                             evidence=[_here(paper)], math={"patient_balance": str(balance), "amount_due_coupon": str(coupon)}))
    return found


def _role(case: Case, paper: Document) -> Role:
    return case.profile.role_of(paper.patient)


def _baby_has_statement(case: Case) -> bool:
    return any(_role(case, d) == Role.NEWBORN for d in case.eobs())


def _asks_for_the_baby(case: Case, paper: Document) -> bool:
    if _role(case, paper) != Role.NEWBORN or paper.kind in (DocKind.EOB, DocKind.ITEMIZED_BILL):
        return False
    if (paper.owed or 0) <= 0 or not paper.statement_date or not paper.provider:
        return False
    return paper.kind != DocKind.HOSPITAL_STATEMENT or not is_hospital_bill(case, paper)


def _unmatched_baby(case: Case, paper: Document) -> Finding:
    age = (case.today - paper.statement_date).days
    ending = (f"It is {age} days old, so send the baby's insurance details now." if age > 30
              else "Send the baby's insurance details before it becomes yours to pay.")
    return Finding(kind=Kind.B2, title=f"Send the baby's insurance details to {paper.provider}",
                   detail=(f"Sheet {_sheet_no(paper.doc_id)} from {paper.provider}, dated {_day(paper.statement_date)}, asks {_usd(paper.owed)} "
                           f"for the baby's care, and no insurance statement in your papers covers the baby. {ending}"),
                   evidence=[_here(paper)],
                   math={"patient_balance": str(paper.owed), "statement_date": paper.statement_date.isoformat(), "days_since": str(age)})


def baby_not_matched(case: Case) -> list[Finding]:
    """An office asks for money for the baby and no insurance statement in the papers covers the baby."""
    if _baby_has_statement(case):
        return []
    return [_unmatched_baby(case, d) for d in case.documents if _asks_for_the_baby(case, d)]


def _unexplained_baby_bill(case: Case) -> Document | None:
    """The baby's first bill with an insurance credit that no statement for the baby explains."""
    if _baby_has_statement(case):
        return None
    return next((b for b in case.bills() if _role(case, b) == Role.NEWBORN and (b.insurance_paid or 0) < 0), None)


def _baby_bill_note(bill: Document) -> tuple[str, dict[str, str]]:
    """The sentence naming the baby's bill and the math keys it adds, in their order."""
    waiting = bill.owed == 0 and bill.due_from_insurance not in (None, 0)
    shown = bill.patient_balance if waiting else bill.owed
    credit = abs(bill.insurance_paid)
    math = {"baby_bill": bill.doc_id, "baby_insurance_credit": str(credit)}
    balance_words = ""
    if shown is not None:
        math["baby_balance"] = str(shown)
        balance_words = f" {_usd(shown)}" + (" due from insurance" if waiting else "")
    if waiting:
        math["baby_waiting"] = "yes"
    word = "sheet" if bill.doc_id.startswith("S") else "file"
    return (f" The hospital already bills the baby's account ({word} {_sheet_no(bill.doc_id)}){balance_words} and shows an insurance credit of "
            f"{_usd(credit)} that no insurance statement in your papers explains: ask for the statement behind it."), math


def _denial_sentence(denied: list[Line], total: Decimal, reasons: set[str]) -> str:
    counted = "1 line" if len(denied) == 1 else f"{len(denied)} lines"
    why = f" (reason {', '.join(sorted(reasons))})" if reasons else ""
    return f"{counted} for {_usd(total)} were denied{why}. "


def _care_under_mother(sheet: Document, newborn: list[Line], baby_bill: Document | None) -> Finding:
    reasons = {ln.denial_codes.strip() for ln in newborn} - {""}
    denied = [ln for ln in sheet.lines
              if ln.denial_codes.strip() in reasons
              or (_is_newborn_code(ln.code) and ln.insurance_paid == 0 and (ln.charges or 0) > 0)]
    total = sum((ln.charges for ln in denied if ln.charges), Decimal(0))  # a free line adds nothing, not even its ".00"
    codes = ", ".join(sorted({ln.code for ln in newborn}))
    member = f" (member {sheet.member_ref})" if sheet.member_ref else ""
    detail = f"Sheet {_sheet_no(sheet.doc_id)} lists newborn care ({codes}) for mom{member}. "
    if denied:
        detail += _denial_sentence(denied, total, reasons)
    detail += "Ask the insurer and the provider to bill it under the baby, or add the baby to the plan, before the balance moves to you."
    evidence = [_here(sheet, ln, ln.denial_codes) for ln in denied or newborn]
    math = {"codes": codes, "denied_lines": str(len(denied)), "denied_total": str(total)}
    if baby_bill is not None:
        sentence, baby_math = _baby_bill_note(baby_bill)
        detail += sentence
        math |= baby_math
        evidence.append(_here(baby_bill, note="baby's bill"))
    return Finding(kind=Kind.B1, title="Baby's care is billed under mom's insurance", detail=detail, evidence=evidence, math=math)


def baby_under_mother(case: Case) -> list[Finding]:
    """Newborn care on a sheet of the mother: the fix is a corrected bill, not an appeal."""
    baby_bill = _unexplained_baby_bill(case)
    found: list[Finding] = []
    for sheet in case.documents:
        newborn = [ln for ln in sheet.lines if _is_newborn_code(ln.code)]
        if newborn and _role(case, sheet) == Role.MOTHER:
            found.append(_care_under_mother(sheet, newborn, baby_bill))
    return found


FAMILY = {DocKind.EOB: "eob", DocKind.HOSPITAL_STATEMENT: "bill", DocKind.ITEMIZED_BILL: "bill"}


def _sheet_order(d: Document) -> tuple[int, str]:
    digits = re.sub(r"\D", "", d.doc_id)
    return (int(digits) if digits else 0, d.doc_id)


def page_runs(case: Case) -> list[list[Document]]:
    """Paper sheets of one multi-page statement, found by their page numbers in reading order.

    A run goes on while the next sheet has the same page count, a higher page number and a kind that fits
    ("other" fits anything: a continuation page often looks like nothing in particular). Provider, claim and
    date are not compared: an insurance statement prints a different doctor and claim on every page.
    Digital files are not counted: a PDF holds all its pages, and "Page 1 of 4" is only its footer."""
    runs: list[list[Document]] = []
    cur: list[Document] = []
    for d in sorted((d for d in case.documents if d.source != Source.PDF), key=_sheet_order):
        paged = bool(d.page_count and d.page_count > 1 and d.page_no)
        if cur and paged and d.page_count == cur[-1].page_count and d.page_no > cur[-1].page_no and _fits(cur, d):
            cur.append(d)
            continue
        if cur:
            runs.append(cur)
        cur = [d] if paged else []
    if cur:
        runs.append(cur)
    return _one_paper_apart(runs)


def _same_paper(a: list[Document], b: list[Document]) -> bool:
    """Pieces of one statement filmed apart: the same page count, no page twice, and something that ties them: the date
    it was printed, the account, or the office on a bill. A doctor's name proves nothing on an insurance statement."""
    if a[0].page_count != b[0].page_count or {d.page_no for d in a} & {d.page_no for d in b} or not all(_fits(a, d) for d in b):
        return False
    tied = lambda field: bool({getattr(d, field) for d in a if getattr(d, field)} & {getattr(d, field) for d in b if getattr(d, field)})  # noqa: E731
    bills = not any(d.kind == DocKind.EOB for d in a + b)
    return tied("statement_date") or tied("account_ref") or (bills and tied("provider"))


def _one_paper_apart(runs: list[list[Document]]) -> list[list[Document]]:
    """On a photo a statement's pages lie together; on a video other sheets come between them. A run with all its pages is left alone."""
    out: list[list[Document]] = []
    for run in runs:
        whole = {d.page_no for d in run} >= set(range(1, run[0].page_count + 1))
        mate = None if whole else next((o for o in out if _same_paper(o, run)), None)
        if mate is None:
            out.append(list(run))
        else:
            mate.extend(run)
    return out


def _fits(run: list[Document], d: Document) -> bool:
    families = {FAMILY[x.kind] for x in run if x.kind in FAMILY}
    return d.kind not in FAMILY or not families or FAMILY[d.kind] in families


def _page_gap(run: list[Document]) -> Finding | None:
    total = run[0].page_count
    have = {d.page_no for d in run}
    gaps = [str(n) for n in range(1, total + 1) if n not in have]
    if not gaps:
        return None
    name = "insurance statement" if any(d.kind == DocKind.EOB for d in run) else "statement"
    office = next((d.provider for d in run if d.provider and d.kind != DocKind.EOB), "")
    origin = f" from {office}" if office else ""
    listed = ", ".join(gaps)
    title = f"Page {listed} of {total} is missing" if len(gaps) == 1 else f"Pages {listed} of {total} are missing"
    return Finding(kind=Kind.P1, title=title,
                   detail=f"This {name}{origin} has {total} pages; we have {len(have)}. Totals may be on a missing page. Find or ask for pages {listed}.",
                   evidence=[_here(d, note=f"page {d.page_no} of {total}") for d in run],
                   math={"page_count": str(total), "missing": ",".join(gaps)})


def missing_pages(case: Case) -> list[Finding]:
    """Pages a statement numbers but the papers lack: the totals may be on them."""
    return [gap for gap in map(_page_gap, page_runs(case)) if gap is not None]


def run(case: Case) -> list[Finding]:
    return (duplicates(case) + credits(case) + two_amounts(case) + baby_under_mother(case) + baby_not_matched(case)
            + missing_pages(case))
