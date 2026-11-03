"""The ceiling on random cases: whatever the papers look like, no debt gives up more than it asks and no line pays twice.

The cases are SYNTHETIC and seeded. The test keeps its own count of what each account asks, written apart from
ledger.py and from the checker: one account per bill family, the newest statement's balance."""

import random
from datetime import date, timedelta
from decimal import Decimal

import pytest

from billradar import checks, pipeline
from billradar.case import Case, DocKind, Document, Line, Person, Profile, Role, Source
from billradar.checks import Kind
from billradar.policies import source

needs_text = pytest.mark.skipif(not all(source.is_cached(p) for p in source.SOURCES),
                                reason="run scripts/fetch_policies.py first")
CASES = 2000
HOSPITAL = "Seaside Regional Hospital"
OFFICES = [HOSPITAL, "Women First OB/GYN", "Coastal Anesthesia Group", "Little Harbor Pediatrics"]
CODES = ["99213", "01960", "85025", "0110", "59409", "99285"]


def money(r: random.Random, low: int, high: int) -> Decimal:
    return Decimal(r.randint(low * 100, high * 100)) / 100


def random_case(seed: int) -> tuple[Case, dict[str, Decimal]]:
    r = random.Random(seed)
    day = date(2025, 3, 1) + timedelta(days=r.randint(0, 200))
    docs: list[Document] = []
    asked: dict[str, Decimal] = {}
    n = 0
    eob_lines: list[Line] = []
    for account in range(r.randint(1, 3)):
        provider, ref = r.choice(OFFICES), f"[ACCT_{account + 1}]"
        patient = r.choice(["PATIENT_1", "PATIENT_2"])
        balance = money(r, 20, 4000)
        lines: list[Line] = []
        for k in range(r.randint(0, 5)):
            claim = f"C{account}{k}"
            code, charges, share = r.choice(CODES), money(r, 100, 3000), money(r, 5, 900)
            ln = Line(line_no=len(lines) + 1, service_date=day, code=code, charges=charges,
                      patient_responsibility=share if r.random() < 0.8 else None, claim_ref=claim)
            lines.append(ln)
            twice = r.random() < 0.3  # the same line printed twice
            if twice:
                lines.append(ln.model_copy(update={"line_no": len(lines) + 1}))
            if r.random() < 0.6:
                share_on_plan = money(r, 0, 500)
                for _ in range(2 if twice and r.random() < 0.5 else 1):  # the plan may print the double too
                    eob_lines.append(Line(line_no=len(eob_lines) + 1, service_date=day, code=code, charges=charges,
                                          patient_responsibility=share_on_plan, claim_ref=claim))
        for copy in range(r.randint(1, 3)):  # monthly statements of one account, the newest counts
            n += 1
            when = day + timedelta(days=30 * copy)
            amount = balance if r.random() < 0.7 else money(r, 20, 4000)
            docs.append(Document(doc_id=f"S{n}", source=Source.PAPER, patient=patient, provider=provider, account_ref=ref,
                                 kind=DocKind.HOSPITAL_STATEMENT if r.random() < 0.7 else DocKind.ITEMIZED_BILL,
                                 statement_date=when, service_from=day, service_to=day, patient_balance=amount,
                                 lines=[x.model_copy() for x in lines]))
            asked[ref] = amount  # the last one written is the newest
    if eob_lines:
        n += 1
        docs.append(Document(doc_id=f"S{n}", source=Source.PAPER, kind=DocKind.EOB, patient="", provider="Plan",
                             statement_date=day + timedelta(days=20), lines=eob_lines))
    prof = Profile(household_size=r.randint(2, 5), annual_income=Decimal(r.randint(20, 120)) * 1000,
                   liquid_assets=Decimal(1000), insured=r.random() < 0.8,
                   context=r.choice([[], ["out_of_network"], ["er_visit", "out_of_network"]]),
                   people=[Person(token="PATIENT_1", role=Role.MOTHER), Person(token="PATIENT_2", role=Role.NEWBORN)])
    return Case(case_id=f"r{seed}", letterhead=HOSPITAL, policy_id="memorial-2026-05", today=date(2026, 10, 26),
                profile=prof, documents=docs), asked


def account_of(case: Case, f) -> str | None:
    bills = {b.doc_id: b for b in case.bills()}
    target = next((e.doc_id for e in f.evidence if e.note == "no discount"), None)
    doc = target or next((e.doc_id for e in f.evidence if e.doc_id in bills), None)
    return bills[doc].account_ref if doc else None


def broken(case: Case, asked: dict[str, Decimal], report) -> list[str]:
    out, spent, lines, plan_lines = [], {}, [], []
    for f in report.findings:
        if f.amount is None:
            continue
        if f.kind in (Kind.E1, Kind.E2, Kind.C1):
            line = f.evidence[1] if f.kind == Kind.E2 else f.evidence[0]
            lines.append((line.doc_id, line.line_no))
        if f.kind == Kind.E1:
            plan_lines += [(e.doc_id, e.line_no) for e in f.evidence[1:]]
        if "cap" in f.math or f.kind == Kind.E3:
            continue
        acct = account_of(case, f)
        if acct is None:
            out.append(f"{f.kind} has no bill behind it")
            continue
        spent[acct] = spent.get(acct, Decimal(0)) + f.amount
    out += [f"{a}: {s} on {asked[a]} asked" for a, s in spent.items() if s > asked[a]]
    if len(lines) != len(set(lines)):
        out.append(f"a line counted twice: {lines}")
    if len(plan_lines) != len(set(plan_lines)):
        out.append(f"an insurance line answered for two bill lines: {plan_lines}")
    total = sum((f.amount for f in report.findings if f.amount is not None), Decimal(0))
    if total.quantize(Decimal("0.01")) != report.total_may_come_off:
        out.append("the total is not the sum of the findings")
    return out


@needs_text
def test_no_debt_gives_up_more_than_it_asks_on_random_cases():
    problems, sums = [], 0
    for seed in range(CASES):
        case, asked = random_case(seed)
        report = checks.run(case)
        sums += sum(1 for f in report.findings if f.amount)
        problems += [f"seed {seed}: {p}" for p in broken(case, asked, report)]
    assert problems == []
    assert sums > CASES  # must light: the cases do produce sums to check


@needs_text
def test_the_count_above_can_see_a_broken_case():
    """Must light on the test's own count: double one sum and it is reported."""
    for seed in range(50):
        case, asked = random_case(seed)
        report = checks.run(case)
        f = next((x for x in report.findings if x.amount and x.kind == Kind.E1), None)
        if f is None:
            continue
        f.amount = asked[account_of(case, f)] + Decimal("1.00")
        assert any("asked" in p for p in broken(case, asked, report))
        return
    pytest.fail("no E1 in 50 cases")


@needs_text
def test_the_checker_agrees_on_random_cases():
    held = 0
    for seed in range(CASES // 4):
        case, asked = random_case(seed)
        report, _ = pipeline.check_and_hold(case, checks.run(case))
        held += len(report.held_back)
        assert broken(case, asked, report) == [], seed
    assert held == 0
