"""One debt, one line: every dollar counted once and never more than the family is asked for.

Each case here is a class from MONEY-AUDIT-2026-10-31 (M1..M8, R5..R7) with the expected numbers worked out by hand.
All cases are SYNTHETIC. Income 85,000 for a household of 4 is 257.6% of the guideline: 85% off at Memorial."""

import re
from datetime import date
from decimal import Decimal

import pytest

from billradar import checks, finding_text, ledger, pipeline, prices, reader, sheet_checks, verifier
from billradar.case import Case, DocKind, Document, Line, Person, Profile, Role, Source
from billradar.checks import Kind
from billradar.policies import source

needs_text = pytest.mark.skipif(not all(source.is_cached(p) for p in source.SOURCES),
                                reason="run scripts/fetch_policies.py first")
HOSPITAL = "Seaside Regional Hospital"
OFFICE = "Women First OB/GYN"
D = date(2025, 8, 4)


def make(*docs: Document, insured=True, context=(), people=None) -> Case:
    prof = Profile(household_size=4, annual_income=Decimal(85000), liquid_assets=Decimal(6000), insured=insured,
                   context=list(context),
                   people=people or [Person(token="PATIENT_1", role=Role.MOTHER), Person(token="PATIENT_2", role=Role.NEWBORN)])
    return Case(case_id="t", policy_id="memorial-2026-05", today=date(2026, 10, 26), profile=prof, documents=list(docs),
                letterhead=HOSPITAL)


def L(n, code, charges, share, **kw) -> Line:
    return Line(line_no=n, service_date=kw.pop("service_date", D), code=code,
                charges=Decimal(charges) if charges is not None else None,
                patient_responsibility=Decimal(share) if share is not None else None, **kw)


def paper(doc_id, kind=DocKind.HOSPITAL_STATEMENT, patient="PATIENT_1", provider=HOSPITAL, **kw) -> Document:
    for k in ("patient_balance", "amount_due_coupon", "due_from_insurance", "fa_discount"):
        if isinstance(kw.get(k), str):
            kw[k] = Decimal(kw[k])
    return Document(doc_id=doc_id, source=Source.PAPER, kind=kind, patient=patient, provider=provider, **kw)


def eob(doc_id, *lines, **kw) -> Document:
    return paper(doc_id, DocKind.EOB, provider=kw.pop("provider", "Sample Health Plan"), lines=list(lines), **kw)


def sums(report, kind) -> list[Decimal]:
    return [f.amount for f in report.findings if f.kind == kind]


def doubted(report, kind) -> list:
    return [f for f in report.worth_asking if f.kind == kind]


# --- M1: a repeated line is the duplicate, not also an overcharge ---------------------------

@needs_text
def test_a_repeated_line_is_one_duplicate_and_not_also_an_overcharge():
    bill = paper("S1", provider=OFFICE, patient_balance="200.00",
                 lines=[L(1, "99213", "500.00", "100.00", claim_ref="C1"), L(2, "99213", "500.00", "100.00", claim_ref="C1")])
    report = checks.run(make(bill, eob("S2", L(1, "99213", "500.00", "40.00", claim_ref="C1"))))
    assert sums(report, Kind.E2) == [Decimal("100.00")]
    assert sums(report, Kind.E1) == [Decimal("60.00")]  # line 1 against the one insurance line, once
    assert report.total_may_come_off == Decimal("160.00")


# --- M2: one debt on several papers ---------------------------------------------------------

@needs_text
def test_monthly_statements_of_one_account_are_one_no_surprises_finding():
    bills = [paper(f"S{i}", provider="Coastal Anesthesia Group", account_ref="[ACCT_1]", patient_balance="900.00",
                   claim_ref="C1", statement_date=date(2025, 9 + i, 1)) for i in (1, 2, 3)]
    report = checks.run(make(*bills, eob("S4", L(1, "01960", "4944.00", "200.00", claim_ref="C1")),
                             context=["out_of_network"]))
    assert sums(report, Kind.N1) == [Decimal("700.00")]
    assert report.total_may_come_off == Decimal("700.00")


@needs_text
def test_a_credit_printed_on_every_statement_of_an_account_is_one_credit():
    bills = [paper(f"S{i}", provider=OFFICE, account_ref="[ACCT_1]", patient_balance="-40.00",
                   statement_date=date(2025, 9 + i, 1)) for i in (1, 2, 3)]
    report = checks.run(make(*bills))
    assert sums(report, Kind.E3) == [Decimal("40.00")]
    assert report.total_may_come_off == Decimal("40.00")


@needs_text
def test_two_papers_of_one_account_against_one_insurance_line_count_once():
    a = paper("S1", provider=OFFICE, account_ref="[ACCT_1]", patient_balance="100.00", statement_date=date(2025, 9, 1),
              lines=[L(1, "99213", "500.00", "100.00", claim_ref="C1")])
    b = paper("S2", DocKind.ITEMIZED_BILL, provider=OFFICE, account_ref="[ACCT_1]", patient_balance="100.00",
              statement_date=date(2025, 9, 20), lines=[L(1, "99213", "500.00", "100.00", claim_ref="C1")])
    report = checks.run(make(a, b, eob("S3", L(1, "99213", "500.00", "40.00", claim_ref="C1"))))
    assert sums(report, Kind.E1) == [Decimal("60.00")]


# --- M3, M5: what came off a debt comes off before the discount -----------------------------

@needs_text
def test_an_overcharge_found_on_the_itemized_copy_comes_off_before_the_discount():
    stmt = paper("S1", account_ref="[ACCT_1]", patient_balance="800.00", statement_date=date(2025, 9, 1),
                 service_from=D, service_to=D)
    itemized = paper("S2", DocKind.ITEMIZED_BILL, account_ref="[ACCT_1]", patient_balance="800.00",
                     statement_date=date(2025, 8, 20), service_from=D, service_to=D,
                     lines=[L(1, "99213", "900.00", "300.00", claim_ref="C1")])
    report = checks.run(make(stmt, itemized, eob("S3", L(1, "99213", "900.00", "100.00", claim_ref="C1"))))
    assert sums(report, Kind.E1) == [Decimal("200.00")]
    assert sums(report, Kind.F1) == [Decimal("510.00")]  # 85% of 800 - 200
    assert report.total_may_come_off == Decimal("710.00")


@needs_text
def test_a_no_surprises_overcharge_comes_off_before_the_discount():
    bill = paper("S1", patient_balance="2000.00", claim_ref="C1", statement_date=date(2025, 9, 1), service_from=D, service_to=D,
                 account_ref="[ACCT_1]")
    report = checks.run(make(bill, eob("S2", L(1, "99283", "4000.00", "1000.00", claim_ref="C1")),
                             context=["er_visit", "out_of_network"]))
    assert sums(report, Kind.N1) == [Decimal("1000.00")]
    assert sums(report, Kind.F1) == [Decimal("850.00")]  # 85% of what is left, not of the whole bill
    assert report.total_may_come_off == Decimal("1850.00")


# --- M4: the cash price on a debt that has a duplicate --------------------------------------

@pytest.fixture
def cash_prices(monkeypatch):
    """A stand-in for the hospital's price file: one code, gross $1,000, cash $400."""
    class Index:
        url, last_updated_on, version, hospital = "https://example.org/file", "2026-05-27", "1", HOSPITAL

    price = prices.Price("CPT", "99285", "ER visit", "outpatient", Decimal(1000), Decimal(400), 7)
    monkeypatch.setattr(prices, "load", lambda policy_id: Index())
    monkeypatch.setattr(prices, "match", lambda index, code, charge: (price, 1))


@needs_text
def test_the_cash_price_skips_a_repeated_line_and_stops_at_the_debt(cash_prices):
    dup = paper("S1", patient_balance="2000.00", statement_date=date(2025, 9, 1), service_from=D, service_to=D,
                lines=[L(1, "99285", "1000.00", "1000.00"), L(2, "99285", "1000.00", "1000.00")])
    other = paper("S2", patient_balance="5000.00", statement_date=date(2025, 9, 1), service_from=D, service_to=D,
                  patient="PATIENT_2")
    report = checks.run(make(dup, other, insured=False))
    assert sums(report, Kind.E2) == [Decimal("1000.00")]
    assert sums(report, Kind.C1) == [Decimal("600.00")]  # line 1 only; line 2 is the duplicate
    assert sorted(sums(report, Kind.F1)) == [Decimal("340.00"), Decimal("4250.00")]  # 85% of 400 and of 5,000
    assert report.total_may_come_off == Decimal("6190.00")


# --- M6: a line with no code against a claim of several lines -------------------------------

@needs_text
@pytest.mark.parametrize("shares", [("9.00", "18.00"), ("18.00", "9.00")])
def test_a_line_with_no_code_is_compared_with_the_whole_claim(shares):
    bill = paper("S1", provider=OFFICE, patient_balance="27.00", lines=[L(1, "", "60.00", "27.00", claim_ref="C1")])
    report = checks.run(make(bill, eob("S2", L(1, "99213", "40.00", shares[0], claim_ref="C1"),
                                       L(2, "85025", "20.00", shares[1], claim_ref="C1"))))
    assert sums(report, Kind.E1) == [] and report.total_may_come_off == 0


@needs_text
def test_a_line_with_no_code_over_the_whole_claim_is_the_difference():
    bill = paper("S1", provider=OFFICE, patient_balance="30.00", lines=[L(1, "", "60.00", "30.00", claim_ref="C1")])
    report = checks.run(make(bill, eob("S2", L(1, "99213", "40.00", "9.00", claim_ref="C1"),
                                       L(2, "85025", "20.00", "18.00", claim_ref="C1"))))
    assert sums(report, Kind.E1) == [Decimal("3.00")]


@needs_text
def test_a_claim_with_a_share_not_read_is_not_compared():
    bill = paper("S1", provider=OFFICE, patient_balance="30.00", lines=[L(1, "", "60.00", "30.00", claim_ref="C1")])
    report = checks.run(make(bill, eob("S2", L(1, "99213", "40.00", "9.00", claim_ref="C1"),
                                       L(2, "85025", "20.00", None, claim_ref="C1"))))
    assert sums(report, Kind.E1) == [] and not doubted(report, Kind.E1)


# --- M7: a claim reprocessed by the plan ----------------------------------------------------

def reprocessed() -> Document:
    return eob("S2", L(1, "99213", "500.00", "100.00", claim_ref="C1"),
               L(2, "99213", "-500.00", "-100.00", claim_ref="C1"),
               L(3, "99213", "500.00", "200.00", claim_ref="C1"))


def test_a_cancelled_line_and_its_reversal_are_gone():
    assert [ln.line_no for ln in ledger.effective_lines(reprocessed()).lines] == [3]
    assert ledger.effective_lines(reprocessed()).unpaired == []


@needs_text
def test_a_reprocessed_claim_is_neither_an_overcharge_nor_a_duplicate():
    bill = paper("S1", provider=OFFICE, patient_balance="200.00", lines=[L(1, "99213", "500.00", "200.00", claim_ref="C1")])
    report = checks.run(make(bill, reprocessed()))
    assert sums(report, Kind.E1) == [] and sums(report, Kind.E2) == [] and not doubted(report, Kind.E2)
    assert report.total_may_come_off == 0


@needs_text
def test_a_reversal_with_no_pair_leaves_no_confirmed_sum_on_that_claim():
    bill = paper("S1", provider=OFFICE, patient_balance="300.00", lines=[L(1, "99213", "500.00", "300.00", claim_ref="C1")])
    plan = eob("S2", L(1, "99213", "500.00", "200.00", claim_ref="C1"), L(2, "99213", "-400.00", "-50.00", claim_ref="C1"))
    report = checks.run(make(bill, plan))
    assert sums(report, Kind.E1) == [] and doubted(report, Kind.E1)
    assert report.total_may_come_off == 0


# --- M8: the family must be asked for it ----------------------------------------------------

@needs_text
def test_a_double_line_only_on_the_insurance_statement_is_not_confirmed_money():
    lab = paper("S1", provider="Coastline Lab", patient_balance="0.00")
    plan = eob("S2", L(1, "85025", "80.00", "10.00"), L(2, "85025", "80.00", "10.00"))
    bill_line = paper("S3", provider=OFFICE, patient_balance="55.00", lines=[L(1, "85025", "80.00", "55.00", claim_ref="C9")])
    report = checks.run(make(lab, plan, bill_line))
    # the bill prints the service once and the statement twice: the family has not been asked twice
    assert sums(report, Kind.E2) == [] and doubted(report, Kind.E2)
    assert report.total_may_come_off == 0


# --- the ceiling itself ---------------------------------------------------------------------

@needs_text
def test_what_goes_over_the_debt_stays_a_finding_without_a_sum():
    bill = paper("S1", provider=OFFICE, patient_balance="100.00",
                 lines=[L(1, "99213", "500.00", "90.00", claim_ref="C1"), L(2, "85025", "400.00", "90.00", claim_ref="C2")])
    report = checks.run(make(bill, eob("S2", L(1, "99213", "500.00", "10.00", claim_ref="C1"),
                                       L(2, "85025", "400.00", "10.00", claim_ref="C2"))))
    assert sums(report, Kind.E1) == [Decimal("80.00")]
    (f,) = doubted(report, Kind.E1)
    assert f.amount is None and "more than" in f.math["why_unsure"]
    assert report.total_may_come_off == Decimal("80.00")


def test_a_debt_is_every_paper_that_asks_for_the_same_money():
    case = make(paper("D1", account_ref="[ACCT_8]", patient_balance="1555.23", statement_date=date(2025, 4, 5)),
                paper("D2", DocKind.ITEMIZED_BILL, account_ref="[ACCT_1]", patient_balance="1555.23"),
                paper("S9", provider="Meridian", account_ref="[ACCT_4]", patient_balance="393.64", page_no=1, page_count=3),
                paper("S10", provider="Meridian", account_ref="[ACCT_4]", patient_balance="393.64", page_no=2, page_count=3),
                paper("S11", provider="Meridian", patient="", patient_balance="393.64", page_no=3, page_count=3))
    book = ledger.Book(case)
    assert sorted(sorted(p.doc_id for p in d.papers) for d in book.debts) == [["D1", "D2"], ["S10", "S11", "S9"]]


@pytest.mark.parametrize("sheet,want", [
    (dict(patient_balance="500.00"), "500.00"),
    (dict(patient_balance="20.00", amount_due_coupon="719.03"), "719.03"),      # a subtotal next to the account's coupon
    (dict(amount_due_coupon="719.03"), "719.03"),
    (dict(patient_balance="1490.25", due_from_insurance="1490.25"), "0"),       # all of it is asked from the plan
    (dict(patient_balance="0.00", amount_due_coupon="719.03"), None),           # two answers: E4
    (dict(patient_balance="719.03", amount_due_coupon="0.00"), None),
    (dict(lines=[L(1, "99213", "90.00", "30.00"), L(2, "85025", "20.00", "5.00")]), "35.00"),  # shares, no balance
    (dict(lines=[L(1, "99213", "90.00", None)]), None),                          # nothing printed
])
def test_what_a_debt_asks(sheet, want):
    (debt,) = ledger.Book(make(paper("S1", provider=OFFICE, **sheet))).debts
    assert debt.asked == (Decimal(want) if want is not None else None)


def test_the_newest_statement_says_what_is_asked():
    old = paper("S1", provider=OFFICE, account_ref="[ACCT_1]", patient_balance="910.00", statement_date=date(2025, 9, 1))
    new = paper("S2", provider=OFFICE, account_ref="[ACCT_1]", patient_balance="800.00", statement_date=date(2025, 10, 1))
    (debt,) = ledger.Book(make(old, new)).debts
    assert debt.asked == Decimal("800.00")


# --- R5: a line read without a date ---------------------------------------------------------

@needs_text
def test_a_line_without_a_date_takes_one_only_when_there_is_one_to_take():
    bill = paper("S1", provider=OFFICE, patient_balance="90.00", lines=[
        L(1, "99213", "150.00", "30.00", service_date=date(2026, 1, 5)),
        L(2, "99213", "150.00", "30.00", service_date=date(2026, 2, 9)),
        L(3, "99213", "150.00", "30.00", service_date=None)])
    report = checks.run(make(bill))
    assert sums(report, Kind.E2) == [] and report.total_may_come_off == 0


# --- R6: what the family is asked, not what is printed --------------------------------------

def baby_letter(**kw) -> Document:
    return paper("S4", patient="PATIENT_2", provider="Little Harbor Pediatrics", statement_date=date(2026, 9, 1), **kw)


def test_a_bill_that_asks_the_plan_is_not_a_bill_to_the_family():
    assert sheet_checks.baby_not_matched(make(baby_letter(patient_balance="412.00", due_from_insurance="412.00"))) == []


def test_a_bill_that_asks_the_family_says_so():
    (f,) = sheet_checks.baby_not_matched(make(baby_letter(patient_balance="412.00")))
    assert "$412.00" in f.detail


def test_a_balance_not_read_is_not_printed_as_zero():
    mom = paper("S1", DocKind.EOB, provider="Plan", lines=[L(1, "99460", "300.00", None, denial_codes="A27", insurance_paid=Decimal(0))])
    baby = paper("S2", patient="PATIENT_2", insurance_paid=Decimal("-120.00"))
    (f,) = sheet_checks.baby_under_mother(make(mom, baby))
    assert "$0.00" not in f.detail and "baby_balance" not in f.math
    assert "$120.00" in f.detail  # must light: the printed credit is still said


@pytest.mark.parametrize("lang", ["ru", "es"])
def test_a_balance_not_read_is_left_out_of_the_translations_too(lang):
    mom = paper("S1", DocKind.EOB, provider="Plan", lines=[L(1, "99460", "300.00", None, denial_codes="A27", insurance_paid=Decimal(0))])
    baby = paper("S2", patient="PATIENT_2", insurance_paid=Decimal("-120.00"))
    case = make(mom, baby)
    (f,) = sheet_checks.baby_under_mother(case)
    _, detail = finding_text.text(f, case, lang)
    assert "120" in detail and not re.search(r"(?<![\d.,\xa0 ])\$?0[.,]00", detail)


# --- R7: credits -----------------------------------------------------------------------------

@needs_text
def test_a_payment_line_is_not_a_credit():
    bill = paper("S1", provider=OFFICE, patient_balance="0.00",
                 lines=[L(1, "99213", "150.00", "150.00"), L(2, "", None, "-150.00", description="Payment received")])
    report = checks.run(make(bill))
    assert sums(report, Kind.E3) == [] and not doubted(report, Kind.E3)


@needs_text
def test_a_credit_line_on_a_balance_still_owed_has_no_sum():
    bill = paper("S1", provider=OFFICE, patient_balance="410.00",
                 lines=[L(1, "59409", "4200.00", "435.00"), L(2, "76801", "0.00", "-25.00", description="Copay overpaid")])
    report = checks.run(make(bill))
    assert sums(report, Kind.E3) == [] and doubted(report, Kind.E3)
    assert report.total_may_come_off == 0  # 410 = 435 - 25: the $25 is already off what is asked


def test_only_bills_carry_credits():
    receipt = paper("S1", DocKind.PAYMENT_RECEIPT, patient_balance="-40.00")
    other = paper("S2", DocKind.OTHER, lines=[L(1, "", None, "-25.00")])
    assert sheet_checks.credits(make(receipt, other)) == []


# --- a subtotal is not a line (S10) ----------------------------------------------------------

def s10(**line_one) -> dict:
    first = {"line_no": 1, "code": "01960", "charges": "$4,944.00", "adjustment": "-$7,919.78",
             "patient_responsibility": "$393.64"} | line_one
    return {"documents": [{"doc_id": "S10", "kind": "hospital_statement", "patient_balance": "$393.64",
                           "lines": [first, {"line_no": 2, "code": "01960", "charges": "$4,944.00"}]}]}


def test_a_subtotal_read_into_a_line_leaves_that_line():
    docs, problems = reader.to_documents(s10(), {"S10": Source.PAPER})
    first = docs[0].lines[0]
    assert first.adjustment is None and first.patient_responsibility is None
    assert first.charges == Decimal("4944.00")
    assert docs[0].patient_balance == Decimal("393.64") and docs[0].doubts == []
    assert any("S10 line 1" in p for p in problems)


def test_a_share_larger_than_the_charge_leaves_the_line_too():
    docs, _ = reader.to_documents(s10(adjustment="", patient_responsibility="$5,000.00"), {"S10": Source.PAPER})
    assert docs[0].lines[0].patient_responsibility is None


def test_a_line_that_adds_up_keeps_its_numbers():
    docs, problems = reader.to_documents(s10(adjustment="-$3,959.89", patient_responsibility="$196.82"), {"S10": Source.PAPER})
    assert docs[0].lines[0].patient_responsibility == Decimal("196.82") and problems == []


@needs_text
def test_the_anesthesia_double_is_a_duplicate_with_the_share_from_the_insurance_statement():
    bill = paper("S10", provider="Meridian", account_ref="[ACCT_4]", patient_balance="393.64", amount_due_coupon="393.64",
                 lines=[L(1, "01960", "4944.00", None), L(2, "01960", "4944.00", None, service_date=None)])
    plan = eob("S1", L(5, "01960", "4944.00", "196.82", claim_ref="C2"), L(6, "01960", "4944.00", "196.82", claim_ref="C2"))
    report = checks.run(make(bill, plan))
    (f,) = [x for x in report.findings if x.kind == Kind.E2]
    assert f.amount == Decimal("196.82") and f.evidence[0].doc_id == "S10"
    assert sums(report, Kind.E1) == []


# --- the trace of a sum ----------------------------------------------------------------------

@needs_text
def test_every_sum_is_traced_to_values_printed_in_the_case():
    bill = paper("S1", patient_balance="2000.00", account_ref="[ACCT_1]", statement_date=date(2025, 9, 1),
                 service_from=D, service_to=D, lines=[L(1, "99213", "900.00", "300.00", claim_ref="C1"),
                                                      L(2, "01960", "900.00", "100.00", claim_ref="C2"),
                                                      L(3, "01960", "900.00", "100.00", claim_ref="C2")])
    case = make(bill, eob("S2", L(1, "99213", "900.00", "100.00", claim_ref="C1")))
    report = checks.run(case)
    assert {f.kind for f in report.findings} >= {Kind.E1, Kind.E2, Kind.F1}
    for f in report.findings:
        if f.amount is None:
            continue
        assert f.trace, f.kind
        for step in f.trace:
            doc = case.doc(step.doc_id)
            holder = next(x for x in doc.lines if x.line_no == step.line_no) if step.line_no else doc
            assert getattr(holder, step.field) == step.printed
    e1 = next(f for f in report.findings if f.kind == Kind.E1)
    assert [(s.doc_id, s.line_no, s.field, s.printed) for s in e1.trace] == [
        ("S1", 1, "patient_responsibility", Decimal("300.00")), ("S2", 1, "patient_responsibility", Decimal("100.00"))]


def confirmed_case() -> tuple[Case, checks.Report]:
    bill = paper("S1", provider=OFFICE, patient_balance="200.00",
                 lines=[L(1, "99213", "500.00", "100.00"), L(2, "99213", "500.00", "100.00")])
    case = make(bill)
    return case, checks.run(case)


@needs_text
@pytest.mark.parametrize("tamper", [
    lambda f: f.trace.clear(),                                                      # no trace at all
    lambda f: f.trace[0].__setattr__("printed", Decimal("999.00")),                 # a value the sheet does not print
    lambda f: f.trace[0].__setattr__("doc_id", "S77"),                              # a sheet that is not there
])
def test_a_sum_whose_trace_does_not_hold_is_not_confirmed(tamper):
    case, report = confirmed_case()
    tamper(report.findings[0])
    shown, _ = pipeline.check_and_hold(case, report)
    assert sums(shown, Kind.E2) == []
    (f,) = doubted(shown, Kind.E2)
    assert f.amount is None and f.math["why_unsure"]
    assert shown.total_may_come_off == 0


@needs_text
def test_the_untampered_sum_stays_confirmed():  # must light for the three above
    case, report = confirmed_case()
    shown, _ = pipeline.check_and_hold(case, report)
    assert sums(shown, Kind.E2) == [Decimal("100.00")]


# --- the verifier's own ceiling --------------------------------------------------------------

@needs_text
def test_the_checker_stops_a_sum_over_the_debt_on_its_own_path():
    case, report = confirmed_case()
    forged = report.findings[0].model_copy(deep=True)
    bigger = case.model_copy(deep=True)
    bigger.doc("S1").patient_balance = Decimal("50.00")  # the same finding, against a sheet that asks only $50
    shown, _ = pipeline.check_and_hold(bigger, report.model_copy(update={"findings": [forged]}))
    assert sums(shown, Kind.E2) == [] and doubted(shown, Kind.E2)
    assert "more than" in doubted(shown, Kind.E2)[0].math["why_unsure"]


@needs_text
def test_the_checker_counts_a_line_once():
    case, report = confirmed_case()
    twin = report.findings[0].model_copy(deep=True)
    shown, _ = pipeline.check_and_hold(case, report.model_copy(update={"findings": [report.findings[0], twin],
                                                                       "total_may_come_off": Decimal("200.00")}))
    assert len(sums(shown, Kind.E2)) == 1 and shown.total_may_come_off == Decimal("100.00")


@needs_text
def test_a_sum_with_no_second_path_is_not_confirmed():
    case, report = confirmed_case()
    f = report.findings[0]
    v = verifier.Verdict(issues=[verifier.Issue(verifier.subject(f, 1), "note", "amount could not be recomputed independently")])
    graded = verifier.grade(case, report, v)
    assert graded.total_may_come_off == 0 and doubted(graded, Kind.E2)
