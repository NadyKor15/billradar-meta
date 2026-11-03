"""Current behaviour of billradar/checks.py: rounding, months, stays, the overcharge check, the assistance check, the windows and run.

All cases are SYNTHETIC, the sums and dates are worked out by hand. Policies and price files are only read.
"""

import decimal
from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from billradar import checks, explain, fpl, policy, prices
from billradar.case import Case, DocKind, Document, Line, Person, Plan, Profile, Role, Source
from billradar.checks import Evidence, Kind, _add_months, _q, check_assistance, check_e1, episodes, has_discount, windows
from billradar.ledger import Book, Step
from billradar.policies import source

needs_text = pytest.mark.skipif(not all(source.is_cached(p) for p in source.SOURCES),
                                reason="run scripts/fetch_policies.py first")
MEMORIAL = "memorial-2026-05"
BAPTIST = "baptist-2026-09"
HOSPITAL = "Seaside Regional Hospital"
OFFICE = "Women First OB/GYN"
ANESTHESIA = "Coastal Anesthesia Group"
D = date(2025, 8, 4)
T = date(2026, 10, 30)
PCT = Decimal("257.6")  # 85% off at Memorial
PAYMENT_RULE = "policy: 12 months after last insurance payment"
SERVICE_RULE = "policy: one year after service"
DAYS_RULE = "policy: days after first bill"
FEDERAL_RULE = "federal: 240 days after first bill"
F1_LAWS = ["federal-501r-5#agb-limit", "federal-501r-6#refund-overpaid", "federal-501r-6#reverse-eca"]
F2_LAWS = ["federal-501r#application-period"]


def paper(doc_id, kind=DocKind.HOSPITAL_STATEMENT, **kw) -> Document:
    kw = {"patient": "PATIENT_1", "provider": HOSPITAL} | kw
    return Document(doc_id=doc_id, source=Source.PAPER, kind=kind, **kw)


def eob(doc_id, *lines, **kw) -> Document:
    return paper(doc_id, DocKind.EOB, provider=kw.pop("provider", "Blue Plan Insurance"), lines=list(lines), **kw)


def L(no, code="99213", share=None, charges="500.00", **kw) -> Line:
    return Line(line_no=no, code=code, charges=charges, patient_responsibility=share, service_date=kw.pop("service_date", D), **kw)


def family(*docs, policy_id=MEMORIAL, today=T, letterhead=HOSPITAL, **profile) -> Case:
    prof = {"household_size": 4, "annual_income": Decimal(85000), "liquid_assets": Decimal(6000), "insured": True,
            "people": [Person(token="PATIENT_1", role=Role.MOTHER), Person(token="PATIENT_2", role=Role.NEWBORN)]} | profile
    return Case(case_id="t", policy_id=policy_id, today=today, profile=Profile(**prof), documents=list(docs), letterhead=letterhead)


def stay(doc_id, service=D, bill_date=None, balance="1000.00", **kw) -> Document:
    return paper(doc_id, account_ref=f"[ACCT_{doc_id[1:]}]", service_from=service, statement_date=bill_date,
                 patient_balance=balance, **kw)


def e1_of(*docs, repeats=frozenset(), **profile):
    case = family(*docs, **profile)
    book = Book(case)
    found, matched = check_e1(case, set(repeats), book)
    return found, matched, book


def help_for(*docs, pol=None, pct=PCT, **profile):
    case = family(*docs, **profile)
    book = Book(case)
    found, notes = check_assistance(case, pol or policy.load(MEMORIAL), pct, book)
    return found, notes, book


def ids(groups):
    return [[b.doc_id for b in g] for g in groups]


def kinds(found):
    return [f.kind for f in found]


# --- _q ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("value,want", [
    ("0.005", "0.01"), ("0.0049", "0.00"), ("-0.005", "-0.01"), ("-0.0049", "-0.00"), ("1.005", "1.01"), ("2.675", "2.68"),
    ("1000000.005", "1000000.01"), ("999999.994", "999999.99"), ("7", "7.00"), ("1E+2", "100.00"), ("0", "0.00"), ("3.10", "3.10"),
])
def test_a_sum_is_rounded_to_cents_half_away_from_zero(value, want):
    assert str(_q(Decimal(value))) == want


def test_rounding_gives_a_decimal_with_exactly_two_places():
    out = _q(Decimal("12"))
    assert isinstance(out, Decimal) and out.as_tuple().exponent == -2


def test_an_endless_sum_cannot_be_rounded_to_cents():
    with pytest.raises(decimal.InvalidOperation):
        _q(Decimal("Infinity"))


# --- _add_months ------------------------------------------------------------------------------

@pytest.mark.parametrize("start,months,want", [
    (date(2025, 9, 2), 12, date(2026, 9, 2)),
    (date(2025, 12, 15), 1, date(2026, 1, 15)),
    (date(2025, 1, 15), -1, date(2024, 12, 15)),
    (date(2025, 5, 30), 0, date(2025, 5, 30)),
    (date(2025, 1, 31), 1, date(2025, 2, 28)),
    (date(2024, 1, 31), 1, date(2024, 2, 29)),
    (date(2024, 2, 29), 12, date(2025, 2, 28)),
    (date(2024, 2, 29), 48, date(2028, 2, 29)),
    (date(2025, 1, 29), 1, date(2025, 2, 28)),
    (date(2024, 11, 30), 3, date(2025, 2, 28)),
    (date(2025, 8, 31), 1, date(2025, 9, 30)),
    (date(2025, 10, 31), -1, date(2025, 9, 30)),
    (date(2025, 3, 31), -1, date(2025, 2, 28)),
    (date(2025, 12, 31), 2, date(2026, 2, 28)),
    (date(2025, 6, 15), 18, date(2026, 12, 15)),
    (date(2025, 6, 15), -18, date(2023, 12, 15)),
])
def test_months_keep_the_day_or_stop_at_the_last_day_of_the_month(start, months, want):
    assert _add_months(start, months) == want


@pytest.mark.parametrize("start,months", [(date(9999, 12, 1), 1), (date(9999, 12, 31), 1), (date(1, 1, 31), -1)])
def test_a_month_past_the_calendar_raises_with_the_date_itself(start, months):
    with pytest.raises(ValueError) as err:
        _add_months(start, months)
    assert err.value.args == (start,)


# --- episodes ---------------------------------------------------------------------------------

def bare(doc_id, day=None, **kw):
    return paper(doc_id, service_from=day, **kw)


def after(n):
    return date.fromordinal(D.toordinal() + n)


def test_no_bills_give_no_stays():
    assert episodes([]) == []


@pytest.mark.parametrize("gap,want", [(0, [["S1", "S2"]]), (6, [["S1", "S2"]]), (7, [["S1", "S2"]]), (8, [["S1"], ["S2"]])])
def test_bills_up_to_a_week_apart_are_one_stay(gap, want):
    assert ids(episodes([bare("S1", D), bare("S2", after(gap))])) == want


def test_a_stay_is_counted_from_its_first_bill_not_from_the_last_one_it_took_in():
    bills = [bare("S1", D), bare("S2", after(5)), bare("S3", after(10)), bare("S4", after(15)), bare("S5", after(17))]
    assert ids(episodes(bills)) == [["S1", "S2"], ["S3", "S4", "S5"]]


def test_bills_are_ordered_by_service_and_equal_dates_keep_their_order():
    bills = [bare("S1", after(30)), bare("S2", D), bare("S3", after(31)), bare("S4", D)]
    assert ids(episodes(bills)) == [["S2", "S4"], ["S1", "S3"]]


def test_bills_with_no_service_date_are_one_last_stay_in_the_order_given():
    bills = [bare("S3"), bare("S1", D), bare("S2")]
    assert ids(episodes(bills)) == [["S1"], ["S3", "S2"]]


def test_only_undated_bills_are_one_stay():
    assert ids(episodes([bare("S2"), bare("S1")])) == [["S2", "S1"]]


def test_the_end_of_a_service_does_not_move_a_bill_to_another_stay():
    bills = [bare("S1", D, service_to=after(30)), bare("S2", after(3))]
    assert ids(episodes(bills)) == [["S1", "S2"]]


def test_stays_hold_the_same_papers_and_leave_the_list_alone():
    bills = [bare("S2", after(30)), bare("S1", D), bare("S3")]
    order = list(bills)
    groups = episodes(bills)
    assert bills == order
    assert groups[0][0] is bills[1] and groups[1][0] is bills[0] and groups[2][0] is bills[2]


# --- has_discount -----------------------------------------------------------------------------

@pytest.mark.parametrize("sheet,line,want", [
    (None, None, False), ("0.00", None, False), (None, "0.00", False), ("0", "0", False), ("-10.00", None, True), ("10.00", None, True),
    (None, "-0.01", True), ("0.00", "5.00", True), (None, None, False),
])
def test_a_discount_is_any_amount_other_than_zero_on_the_sheet_or_a_line(sheet, line, want):
    doc = paper("S1", fa_discount=sheet, lines=[Line(line_no=1), Line(line_no=2, fa_discount=line)])
    assert has_discount(doc) is want


def test_a_sheet_with_no_lines_has_only_its_own_discount():
    assert has_discount(paper("S1")) is False
    assert has_discount(paper("S1", fa_discount="-1.00")) is True


# --- check_e1 ---------------------------------------------------------------------------------

def test_a_bill_line_equal_to_the_insurance_line_is_a_match_with_nothing_to_dispute():
    found, matched, book = e1_of(paper("S1", lines=[L(1, share="100.00")]), eob("S2", L(1, share="100.00")))
    assert found == []
    (m,) = matched
    assert (m.kind, m.title) == (Kind.NM, "Sheet 1 line 1 matches your insurance statement")
    assert m.detail == "Both say $100.00. Nothing to dispute here."
    assert m.evidence == [Evidence(doc_id="S1", line_no=1), Evidence(doc_id="S2", line_no=1)]
    assert list(m.math.items()) == [("bill_patient_responsibility", "100.00"), ("eob_patient_responsibility", "100.00"),
                                    ("difference", "0.00")]
    assert (m.amount, m.severity, m.trace) == (None, None, [])


def test_a_bill_line_below_the_insurance_line_is_a_match_too_and_says_what_the_bill_asks():
    _, (m,), _ = e1_of(paper("D1", lines=[L(1, share="1234.50")]), eob("S2", L(1, share="1300.00")))
    assert m.title == "Sheet 1 line 1 matches your insurance statement"  # only the first letter of the id goes
    assert m.detail == "Both say $1,234.50. Nothing to dispute here."
    assert m.math["difference"] == "-65.50"


def test_an_overcharge_is_the_difference_with_every_number_it_stands_on():
    case = family(paper("S1", patient_balance="2500.00", lines=[L(3, share="2312.40")]), eob("S2", L(7, share="2000.00")))
    book = Book(case)
    (f,), matched = check_e1(case, set(), book)
    assert matched == []
    assert (f.kind, f.amount, f.severity) == (Kind.E1, Decimal("312.40"), None)
    assert f.title == "Bill asks $312.40 more than your insurance says"
    assert f.detail == ("Line 3 on sheet S1 asks $2,312.40. Your insurance statement (S2, line 7) says you owe $2,000.00 "
                        "for the same service.")
    assert f.evidence == [Evidence(doc_id="S1", line_no=3), Evidence(doc_id="S2", line_no=7)]
    assert list(f.math.items()) == [("bill_patient_responsibility", "2312.40"), ("eob_patient_responsibility", "2000.00"),
                                    ("difference", "312.40"), ("counts_toward_total", "312.40")]
    assert f.trace == [
        Step(doc_id="S1", line_no=3, field="patient_responsibility", printed=Decimal("2312.40"), role="the bill asks"),
        Step(doc_id="S2", line_no=7, field="patient_responsibility", printed=Decimal("2000.00"), role="your insurance says")]
    assert book.taken("S1") == Decimal("312.40") and book.left("S1") == Decimal("2187.60")


def test_a_line_with_no_code_is_compared_with_every_line_of_its_claim():
    (f,), _, _ = e1_of(paper("S1", patient_balance="500.00", lines=[L(1, code="", share="500.00", claim_ref="C1")]),
                       eob("S2", L(1, code="0110", share="100.00", claim_ref="C1"), L(2, code="0250", share="50.50", claim_ref="C1")))
    assert f.amount == Decimal("349.50")
    assert "Your insurance statement (S2, lines 1, 2) says you owe $150.50 for the same service." in f.detail
    assert f.evidence == [Evidence(doc_id="S1", line_no=1), Evidence(doc_id="S2", line_no=1), Evidence(doc_id="S2", line_no=2)]
    assert [s.printed for s in f.trace] == [Decimal("500.00"), Decimal("100.00"), Decimal("50.50")]
    assert f.math["eob_patient_responsibility"] == "150.50"


def test_on_a_discounted_bill_only_the_share_left_after_the_discount_counts():
    case = family(paper("S1", patient_balance="676.80", fa_discount="-3835.20", lines=[L(1, share="4512.00")]), eob("S2", L(1, share="4199.60")))
    book = Book(case)
    (f,), _ = check_e1(case, set(), book)
    assert f.title == "Bill asks $312.40 more than your insurance says"  # the title keeps the whole difference
    assert f.amount == Decimal("46.86")  # 312.40 * 676.80 / 4512.00
    assert f.detail.endswith(" for the same service. Your discount already covers part of it, so $46.86 of it is yours.")
    assert list(f.math.items()) == [("bill_patient_responsibility", "4512.00"), ("eob_patient_responsibility", "4199.60"),
                                    ("difference", "312.40"), ("share_left_after_discount", "676.80/4512.00"),
                                    ("counts_toward_total", "46.86")]
    assert f.trace[2:] == [Step(doc_id="S1", field="patient_balance", printed=Decimal("676.80"), role="balance"),
                           Step(doc_id="S1", field="fa_discount", printed=Decimal("-3835.20"), role="discount")]
    assert book.taken("S1") == Decimal("46.86")


def test_a_positive_discount_counts_as_its_size():
    (f,), _, _ = e1_of(paper("S1", patient_balance="600.00", fa_discount="200.00", lines=[L(1, share="300.00")]), eob("S2", L(1, share="200.00")))
    assert f.amount == Decimal("75.00")  # 100.00 * 600 / 800
    assert f.math["share_left_after_discount"] == "600.00/800.00"


def test_a_discount_printed_only_on_a_line_does_not_shrink_the_overcharge():
    (f,), _, _ = e1_of(paper("S1", patient_balance="400.00", lines=[L(1, share="300.00", fa_discount="-50.00")]), eob("S2", L(1, share="200.00")))
    assert f.amount == Decimal("100.00")
    assert "share_left_after_discount" not in f.math and "Your discount" not in f.detail and len(f.trace) == 2


def test_a_discount_with_no_balance_does_not_shrink_the_overcharge():
    (f,), _, _ = e1_of(paper("S1", fa_discount="-50.00", lines=[L(1, share="300.00")]), eob("S2", L(1, share="200.00")))
    assert f.amount == Decimal("100.00")
    assert "share_left_after_discount" not in f.math


def test_a_balance_and_discount_that_cancel_out_leave_the_whole_difference():
    (f,), _, _ = e1_of(paper("S1", patient_balance="-100.00", fa_discount="100.00", lines=[L(1, share="300.00")]), eob("S2", L(1, share="200.00")))
    assert f.amount == Decimal("100.00")
    assert f.math["share_left_after_discount"] == "-100.00/0.00"
    assert "Your discount" not in f.detail and len(f.trace) == 4


def test_a_share_that_rounds_back_to_the_difference_adds_no_sentence():
    (f,), _, _ = e1_of(paper("S1", patient_balance="990.00", fa_discount="-10.00", lines=[L(1, share="100.01")]), eob("S2", L(1, share="100.00")))
    assert f.amount == Decimal("0.01")
    assert f.math["share_left_after_discount"] == "990.00/1000.00"
    assert f.detail.endswith("for the same service.")


def test_a_repeated_line_is_left_to_the_duplicate_finding_and_its_insurance_line_stays_free():
    bill = paper("S1", patient_balance="900.00", lines=[L(1, share="300.00"), L(2, share="300.00")])
    found, matched, _ = e1_of(bill, eob("S2", L(1, share="100.00")), repeats={("S1", 1)})
    assert [f.evidence[0].line_no for f in found] == [2]
    assert matched == []


def test_a_bill_line_with_no_share_is_passed_over():
    found, matched, _ = e1_of(paper("S1", lines=[L(1, share=None), L(2, share="300.00")]), eob("S2", L(1, share="100.00")))
    assert [f.evidence[0].line_no for f in found] == [2]
    assert matched == []


def test_a_bill_line_nothing_on_the_statement_answers_is_passed_over():
    found, matched, book = e1_of(paper("S1", lines=[L(1, share="300.00")]), eob("S2", L(1, code="0110", share="100.00")))
    assert (found, matched) == ([], [])
    assert book.taken("S1") == 0


def test_a_claim_with_a_share_not_read_is_not_compared_and_keeps_its_lines_for_the_next_bill_line():
    bill = paper("S1", patient_balance="900.00",
                 lines=[L(1, code="", share="300.00", claim_ref="C1"), L(2, code="0250", share="80.00", claim_ref="C1")])
    plan = eob("S2", L(1, code="0110", share=None, claim_ref="C1"), L(2, code="0250", share="20.00", claim_ref="C1"))
    (f,), matched, _ = e1_of(bill, plan)
    assert f.evidence == [Evidence(doc_id="S1", line_no=2), Evidence(doc_id="S2", line_no=2)]
    assert f.amount == Decimal("60.00")
    assert matched == []


def test_one_insurance_line_answers_one_bill_line_even_when_it_matched():
    bill = paper("S1", lines=[L(1, share="100.00"), L(2, share="100.00")])
    found, matched, _ = e1_of(bill, eob("S2", L(1, share="100.00")))
    assert found == []
    assert [m.evidence[0].line_no for m in matched] == [1]


def test_one_insurance_line_answers_one_bill_line_across_bills():
    a = paper("S1", account_ref="[ACCT_1]", lines=[L(1, share="300.00")])
    b = paper("S2", account_ref="[ACCT_2]", lines=[L(1, share="300.00")])
    found, _, _ = e1_of(a, b, eob("S3", L(1, share="100.00")))
    assert [f.evidence[0].doc_id for f in found] == ["S1"]


def test_a_second_insurance_line_answers_the_second_bill_line():
    bill = paper("S1", patient_balance="1000.00", lines=[L(1, share="300.00"), L(2, share="300.00")])
    found, matched, _ = e1_of(bill, eob("S2", L(1, share="300.00"), L(2, share="100.00")))
    assert [(f.evidence[0].line_no, f.evidence[1].line_no) for f in found] == [(2, 2)]
    assert [(m.evidence[0].line_no, m.evidence[1].line_no) for m in matched] == [(1, 1)]


def test_findings_follow_the_order_of_the_papers_and_their_lines():
    a = paper("S1", account_ref="[ACCT_1]", patient_balance="900.00", lines=[L(1, "0110", "300.00"), L(2, "0250", "50.00"), L(3, "0450", "300.00")])
    b = paper("S2", account_ref="[ACCT_2]", patient_balance="900.00", lines=[L(1, "0120", "300.00")])
    plan = eob("S3", L(1, "0120", "1.00"), L(2, "0450", "1.00"), L(3, "0250", "50.00"), L(4, "0110", "1.00"))
    found, matched, _ = e1_of(a, b, plan)
    assert [(f.evidence[0].doc_id, f.evidence[0].line_no) for f in found] == [("S1", 1), ("S1", 3), ("S2", 1)]
    assert [(m.evidence[0].doc_id, m.evidence[0].line_no) for m in matched] == [("S1", 2)]


def test_a_reversal_with_no_pair_leaves_an_overcharge_without_a_confirmed_sum():
    plan = eob("S2", L(1, share="100.00", claim_ref="C1"), L(2, share="-40.00", charges="-777.00", claim_ref="C1"))
    (f,), _, book = e1_of(paper("S1", patient_balance="500.00", lines=[L(1, share="300.00", claim_ref="C1")]), plan)
    assert f.severity == "borderline"
    assert f.math["why_unsure"] == "the insurance statement reverses a line of this claim without saying which one"
    assert f.amount == Decimal("200.00")
    assert book.taken("S1") == 0


def test_an_overcharge_on_a_sheet_read_with_a_doubt_takes_nothing_off():
    (f,), _, book = e1_of(paper("S1", patient_balance="500.00", lines=[L(1, share="300.00")]), eob("S2", L(1, share="100.00"), doubts=["x"]))
    assert f.severity == "borderline"
    assert f.math["why_unsure"] == "S2 could not be read in full: take a new photo of it"
    assert book.taken("S1") == 0


def test_an_overcharge_larger_than_the_debt_stays_without_a_confirmed_sum():
    (f,), _, book = e1_of(paper("S1", patient_balance="150.00", lines=[L(1, share="300.00")]), eob("S2", L(1, share="100.00")))
    assert f.math["why_unsure"] == "it would take off more than the $150.00 your papers still ask for"
    assert (f.severity, f.amount) == ("borderline", Decimal("200.00"))
    assert book.taken("S1") == 0


def test_two_overcharges_on_one_debt_share_what_it_asks():
    bill = paper("S1", patient_balance="250.00", lines=[L(1, "0110", "300.00"), L(2, "0250", "300.00")])
    found, _, book = e1_of(bill, eob("S2", L(1, "0110", "100.00"), L(2, "0250", "100.00")))
    assert [f.severity for f in found] == [None, "borderline"]
    assert book.taken("S1") == Decimal("200.00")


def test_the_book_and_the_case_are_the_only_things_read_and_the_case_stays_as_it_was():
    case = family(paper("S1", patient_balance="500.00", lines=[L(1, share="300.00")]), eob("S2", L(1, share="100.00")))
    before = case.model_dump_json()
    check_e1(case, set(), Book(case))
    assert case.model_dump_json() == before


# --- check_assistance -------------------------------------------------------------------------

def test_a_hospital_bill_with_no_discount_is_f1_with_every_word_and_number():
    found, notes, book = help_for(stay("S1"))
    assert notes == []
    (f,) = found
    assert (f.kind, f.amount, f.severity, f.deadline) == (Kind.F1, Decimal("850.00"), None, None)
    assert f.title == "You likely qualify for financial assistance"
    assert f.detail == ("Household of 4, income $85,000: 257.6% of the poverty guideline. The policy gives 85% off at this level. "
                        "Sheet S1 has no discount yet.")
    assert f.evidence == [Evidence(doc_id="S1", note="no discount")]
    assert f.policy_refs == [f"{MEMORIAL}#scale-mrh", f"{MEMORIAL}#insured-balances"]
    assert list(f.math.items()) == [("balance", "1000.00"), ("minus_overcharge", "0"), ("fpl_pct", "257.6"), ("discount_pct", "85"),
                                    ("saving", "850.00")]
    assert f.trace == [Step(doc_id="S1", field="patient_balance", printed=Decimal("1000.00"), role="what the papers ask")]
    assert book.taken("S1") == Decimal("850.00") and book.left("S1") == Decimal("150.00")


def test_the_discount_is_worked_out_on_what_is_left_of_the_debt():
    case = family(stay("S1"))
    book = Book(case)
    assert book.take("S1", Decimal("100.00")) == ""
    (f,), _ = check_assistance(case, policy.load(MEMORIAL), PCT, book)
    assert f.amount == Decimal("765.00")
    assert (f.math["balance"], f.math["minus_overcharge"], f.math["saving"]) == ("1000.00", "100.00", "765.00")
    assert book.taken("S1") == Decimal("865.00")


def test_a_bill_of_the_same_stay_as_a_discounted_one_is_f3_on_the_baby():
    mom = stay("S1", fa_discount="-500.00")
    baby = stay("S2", service=after(1), balance="400.00", patient="PATIENT_2")
    (f,), _, book = help_for(mom, baby)
    assert (f.kind, f.amount) == (Kind.F3, Decimal("340.00"))
    assert f.title == "Discount on sheet S1, not on the baby's bill"
    assert f.detail == ("Same hospital stay. Financial assistance is on sheet S1, but sheet S2 still asks $400.00. "
                        "At your income level the policy gives 85% off.")
    assert f.evidence == [Evidence(doc_id="S1", note="discount applied"), Evidence(doc_id="S2", note="no discount")]
    assert f.policy_refs == [f"{MEMORIAL}#scale-mrh", f"{MEMORIAL}#insured-balances"]
    assert list(f.math) == ["balance", "minus_overcharge", "fpl_pct", "discount_pct", "saving"]
    assert book.taken("S1") == 0 and book.taken("S2") == Decimal("340.00")


def test_f3_on_a_bill_that_is_not_the_babys_says_this_bill():
    (f,), _, _ = help_for(stay("S1", fa_discount="-500.00"), stay("S2", balance="400.00", patient="PATIENT_3"))
    assert f.title == "Discount on sheet S1, not on this bill"


def test_f3_shows_what_the_sheet_asks_and_counts_what_is_left():
    case = family(stay("S1", fa_discount="-500.00"), stay("S2", balance="400.00", patient="PATIENT_2"))
    book = Book(case)
    book.take("S2", Decimal("100.00"))
    (f,), _ = check_assistance(case, policy.load(MEMORIAL), PCT, book)
    assert "sheet S2 still asks $400.00." in f.detail
    assert f.amount == Decimal("255.00")


def test_f3_names_the_first_discounted_bill_of_the_stay():
    bills = [stay("S1", fa_discount="-5.00"), stay("S2", fa_discount="-5.00", patient="PATIENT_3"), stay("S3", balance="400.00", patient="PATIENT_2")]
    (f,), _, _ = help_for(*bills)
    assert f.evidence[0].doc_id == "S1"


def test_a_stay_with_every_bill_discounted_gives_nothing():
    found, notes, book = help_for(stay("S1", fa_discount="-5.00"), stay("S2", fa_discount="-5.00", patient="PATIENT_2"))
    assert (found, notes) == ([], [])
    assert book.taken("S1") == 0


def test_a_discount_on_another_stay_makes_this_one_f1():
    found, _, _ = help_for(stay("S1", fa_discount="-5.00"), stay("S2", service=after(30), balance="400.00"))
    assert kinds(found) == [Kind.F1]
    assert found[0].evidence == [Evidence(doc_id="S2", note="no discount")]


def test_a_discount_on_any_paper_of_the_debt_counts_for_the_debt():
    old = paper("S1", account_ref="[ACCT_1]", service_from=D, statement_date=date(2025, 9, 1), patient_balance="800.00", fa_discount="-5.00")
    new = paper("S2", account_ref="[ACCT_1]", service_from=D, statement_date=date(2025, 10, 1), patient_balance="800.00")
    assert help_for(old, new)[0] == []


def test_a_line_discount_counts_as_a_discount_on_the_bill():
    found, _, _ = help_for(stay("S1", lines=[Line(line_no=1, fa_discount="-3.00")]), stay("S2", balance="400.00", patient="PATIENT_2"))
    assert kinds(found) == [Kind.F3]


def test_findings_follow_the_stays_oldest_first():
    found, _, _ = help_for(stay("S1", service=after(40)), stay("S2", service=D, balance="400.00"))
    assert [f.evidence[0].doc_id for f in found] == ["S2", "S1"]


def test_every_family_bill_of_one_stay_gets_its_own_finding():
    found, _, book = help_for(stay("S1"), stay("S2", balance="400.00", patient="PATIENT_2"))
    assert kinds(found) == [Kind.F1, Kind.F1]
    assert [f.amount for f in found] == [Decimal("850.00"), Decimal("340.00")]


def test_a_bill_with_nothing_asked_of_the_family_gets_no_finding():
    assert help_for(stay("S1", balance="0.00"))[0] == []


def test_a_bill_all_due_from_insurance_is_a_note_with_nothing_taken():
    found, notes, book = help_for(stay("S1", balance="300.00", due_from_insurance="300.00"))
    assert found == []
    (n,) = notes
    assert (n.kind, n.title) == (Kind.NM, "Sheet S1: waiting for insurance")
    assert n.detail == ("$300.00 is due from insurance, not from you, so nothing comes off it yet. "
                        "If the plan refuses it, ask for the same help on this bill.")
    assert n.evidence == [Evidence(doc_id="S1")]
    assert (n.policy_refs, n.math, n.amount) == ([], {}, None)


def test_a_due_amount_on_a_bill_with_a_balance_is_no_note():
    assert help_for(stay("S1", balance="600.00", due_from_insurance="100.00"))[1] == []


def test_two_statements_of_one_account_wait_for_insurance_once():
    a = paper("S1", account_ref="[ACCT_1]", patient_balance="300.00", due_from_insurance="300.00", statement_date=date(2025, 9, 1))
    b = paper("S2", account_ref="[ACCT_1]", patient_balance="300.00", due_from_insurance="300.00", statement_date=date(2025, 10, 1))
    assert [n.title for n in help_for(a, b)[1]] == ["Sheet S2: waiting for insurance"]


def test_doctors_bills_are_named_in_one_note_sorted_and_once():
    bills = [stay("S1", provider=OFFICE), stay("S2", provider=ANESTHESIA), stay("S3", provider=OFFICE, balance="20.00")]
    found, notes, _ = help_for(*bills)
    assert found == []
    (n,) = notes
    assert n.title == "Doctors' bills are outside the hospital's assistance policy"
    assert n.detail == ("Coastal Anesthesia Group, Women First OB/GYN bill separately. This policy covers the hospital and its own "
                        "doctors only; ask each office whether it has its own help program.")
    assert n.evidence == [Evidence(doc_id="S1"), Evidence(doc_id="S2"), Evidence(doc_id="S3")]
    assert n.policy_refs == [f"{MEMORIAL}#facilities-only"]


def test_the_doctors_note_cites_the_scope_fragment_the_policy_has():
    pol = policy.load(BAPTIST)
    assert help_for(stay("S1", provider=OFFICE), pol=pol, policy_id=BAPTIST)[1][0].policy_refs == [f"{BAPTIST}#facility-only"]
    bare_pol = replace(policy.load(MEMORIAL), fragments={})
    assert help_for(stay("S1", provider=OFFICE), pol=bare_pol)[1][0].policy_refs == []


def test_a_doctors_bill_with_nothing_asked_is_not_in_the_note():
    assert help_for(stay("S1", provider=OFFICE, balance="0.00"))[1] == []


def test_a_policy_for_the_uninsured_answers_an_insured_family_before_the_notes():
    pol = policy.load(BAPTIST)
    bills = [stay("S1"), stay("S2", balance="300.00", due_from_insurance="300.00"), stay("S3", provider=OFFICE)]
    found, notes, book = help_for(*bills, pol=pol, policy_id=BAPTIST)
    assert found == []
    assert [n.title for n in notes] == ["This hospital's policy does not cover what insurance leaves you to pay",
                                        "Sheet S2: waiting for insurance",
                                        "Doctors' bills are outside the hospital's assistance policy"]
    assert notes[0].detail == (f"{pol.hospital}: financial assistance is for uninsured patients. Your copays, deductible and coinsurance "
                               "are not covered by it. Check the bill against your insurance statement instead.")
    assert notes[0].policy_refs == [f"{BAPTIST}#uninsured-only"]
    assert (notes[0].evidence, notes[0].math) == ([], {})
    assert book.taken("S1") == 0


def test_an_uninsured_family_is_helped_by_a_policy_for_the_uninsured():
    found, _, _ = help_for(stay("S1"), pol=policy.load(BAPTIST), pct=Decimal("150.0"), policy_id=BAPTIST, insured=False)
    assert (found[0].kind, found[0].amount) == (Kind.F1, Decimal("1000.00"))
    assert found[0].policy_refs == [f"{BAPTIST}#levels"]


def test_an_uninsured_family_gets_no_reference_to_insured_balances():
    (f,), _, _ = help_for(stay("S1"), insured=False)
    assert f.policy_refs == [f"{MEMORIAL}#scale-mrh"]


def test_a_policy_with_no_such_fragment_gets_no_reference_to_insured_balances():
    pol = policy.load(MEMORIAL)
    pol = replace(pol, fragments={k: v for k, v in pol.fragments.items() if k != "insured-balances"})
    (f,), _, _ = help_for(stay("S1"), pol=pol)
    assert f.policy_refs == [f"{MEMORIAL}#scale-mrh"]


def test_income_above_the_top_tier_is_a_note():
    found, notes, _ = help_for(stay("S1"), pct=Decimal("450.0"))
    assert found == []
    (n,) = notes
    assert n.title == "Your income is above this policy's limit"
    assert n.detail == "Your household income is 450.0% of the federal poverty guideline. This policy helps households up to 400%."
    assert n.policy_refs == [f"{MEMORIAL}#scale-mrh"]
    assert n.math == {"fpl_pct": "450.0"}


@pytest.mark.parametrize("sheet,profile,pct,title", [
    ({}, {}, "450.0", "Your income is above this policy's limit"),
    ({"balance": "300.00"}, {}, "257.6", "Balances are under the $500 minimum"),
    ({}, {"liquid_assets": Decimal("20000")}, "150.0", "Free care needs savings under the policy's limit"),
])
def test_an_answer_that_ends_the_check_comes_before_the_notes(sheet, profile, pct, title):
    bills = [stay("S1", **sheet), stay("S2", balance="250.00", due_from_insurance="250.00"), stay("S3", provider=OFFICE)]
    found, notes, _ = help_for(*bills, pct=Decimal(pct), **profile)
    assert found == []
    assert [n.title for n in notes] == [title, "Sheet S2: waiting for insurance", "Doctors' bills are outside the hospital's assistance policy"]


def test_findings_and_notes_come_back_apart():
    found, notes, _ = help_for(stay("S1"), stay("S2", balance="300.00", due_from_insurance="300.00"), stay("S3", provider=OFFICE))
    assert kinds(found) == [Kind.F1]
    assert [n.title for n in notes] == ["Sheet S2: waiting for insurance", "Doctors' bills are outside the hospital's assistance policy"]


def test_a_policy_with_no_tiers_helps_up_to_zero_percent():
    (n,) = help_for(stay("S1"), pol=replace(policy.load(MEMORIAL), tiers=[]))[1]
    assert n.detail.endswith("This policy helps households up to 0%.")
    assert n.policy_refs == []


def test_savings_at_the_limit_stop_free_care():
    found, notes, _ = help_for(stay("S1"), pct=Decimal("150.0"), liquid_assets=Decimal("10000.00"))
    assert found == []
    (n,) = notes
    assert n.title == "Free care needs savings under the policy's limit"
    assert n.detail == ("Your income fits the 100% level, but this policy also asks for savings under $10,000. "
                        "Ask the hospital how it treats your case.")
    assert n.policy_refs == [f"{MEMORIAL}#liquid-assets"]


def test_savings_under_the_limit_give_free_care_citing_the_limit():
    (f,), _, book = help_for(stay("S1"), pct=Decimal("150.0"), liquid_assets=Decimal("9999.99"))
    assert (f.amount, f.severity) == (Decimal("1000.00"), None)
    assert f.policy_refs == [f"{MEMORIAL}#tier-200", f"{MEMORIAL}#insured-balances", f"{MEMORIAL}#liquid-assets"]
    assert f.detail.endswith("Sheet S1 has no discount yet.")
    assert book.left("S1") == 0


def test_savings_not_known_leave_free_care_without_a_confirmed_sum():
    (f,), _, book = help_for(stay("S1"), pct=Decimal("150.0"), liquid_assets=None)
    assert f.detail.endswith("Sheet S1 has no discount yet. This level also needs savings under $10,000.")
    assert (f.severity, f.amount) == ("borderline", Decimal("1000.00"))
    assert f.math["why_unsure"] == "free care also depends on savings we do not know: This level also needs savings under $10,000."
    assert book.taken("S1") == 0


def test_savings_not_known_are_said_on_f3_too():
    (f,), _, _ = help_for(stay("S1", fa_discount="-5.00"), stay("S2", balance="400.00", patient="PATIENT_2"), pct=Decimal("150.0"), liquid_assets=None)
    assert f.detail.endswith("the policy gives 100% off. This level also needs savings under $10,000.")


def test_a_full_discount_with_no_savings_limit_asks_nothing_about_savings():
    pol = replace(policy.load(MEMORIAL), liquid_assets_limit_for_free_care=None)
    (f,), _, _ = help_for(stay("S1"), pol=pol, pct=Decimal("150.0"), liquid_assets=None)
    assert f.policy_refs == [f"{MEMORIAL}#tier-200", f"{MEMORIAL}#insured-balances"]
    assert f.severity is None


def test_a_lower_tier_says_nothing_about_savings_whatever_they_are():
    (f,), _, _ = help_for(stay("S1"), liquid_assets=Decimal("900000"))
    assert (f.amount, f.severity) == (Decimal("850.00"), None)
    assert f"{MEMORIAL}#liquid-assets" not in f.policy_refs


def test_balances_at_the_minimum_are_a_note():
    found, notes, _ = help_for(stay("S1", balance="300.00"), stay("S2", balance="200.00", patient="PATIENT_2"))
    assert found == []
    (n,) = notes
    assert n.title == "Balances are under the $500 minimum"
    assert n.detail == "All your balances together are $500.00. This policy considers requests of more than $500."
    assert n.policy_refs == [f"{MEMORIAL}#min-request"]
    assert n.math == {"total_balance": "500.00"}


def test_one_cent_over_the_minimum_is_a_request():
    assert kinds(help_for(stay("S1", balance="500.01"))[0]) == [Kind.F1]


def test_the_minimum_looks_at_what_is_left_of_the_debts():
    case = family(stay("S1", balance="700.00"))
    book = Book(case)
    book.take("S1", Decimal("200.00"))
    found, notes = check_assistance(case, policy.load(MEMORIAL), PCT, book)
    assert found == []
    assert notes[0].math == {"total_balance": "500.00"}


def test_a_policy_with_no_minimum_takes_any_balance():
    pol = replace(policy.load(MEMORIAL), min_request_total=None)
    assert help_for(stay("S1", balance="1.00"), pol=pol)[0][0].amount == Decimal("0.85")


def test_what_stays_after_the_discount_is_capped_at_a_share_of_income():
    (f, cap), _, book = help_for(stay("S1", balance="100000.00"))
    assert f.amount == Decimal("85000.00")
    assert (cap.kind, cap.amount) == (Kind.F1, Decimal("6500.00"))
    assert cap.title == "Capped at 10% of your yearly income"
    assert cap.detail == "After the discount you would still owe $15,000.00. The policy caps it at 10% of household income: $8,500.00."
    assert list(cap.math.items()) == [("owed_after_discount", "15000.00"), ("cap", "8500.00")]
    assert cap.policy_refs == [f"{MEMORIAL}#income-cap"]
    assert cap.evidence == [Evidence(doc_id="S1")]
    assert cap.trace == [Step(doc_id="S1", field="patient_balance", printed=Decimal("100000.00"), role="what the papers ask")]
    assert book.left("S1") == Decimal("8500.00")


def test_the_cap_covers_every_hospital_bill_and_comes_off_them_in_turn():
    a, b = stay("S1", balance="60000.00"), stay("S2", service=after(30), balance="40000.00")
    (_, _, cap), _, book = help_for(a, b)
    assert cap.amount == Decimal("6500.00")
    assert cap.evidence == [Evidence(doc_id="S1"), Evidence(doc_id="S2")]
    assert [s.doc_id for s in cap.trace] == ["S1", "S2"]
    assert book.left("S1") == Decimal("2500.00") and book.left("S2") == Decimal("6000.00")


def test_a_discount_that_lands_exactly_on_the_cap_adds_nothing():
    found, _, _ = help_for(stay("S1", balance="56666.67"))  # saving 48166.67, 8500.00 left
    assert kinds(found) == [Kind.F1]


def test_the_cap_needs_its_fragment_a_percent_and_a_discount():
    pol = policy.load(MEMORIAL)
    no_fragment = replace(pol, fragments={k: v for k, v in pol.fragments.items() if k != "income-cap"})
    assert kinds(help_for(stay("S1", balance="100000.00"), pol=no_fragment)[0]) == [Kind.F1]
    assert kinds(help_for(stay("S1", balance="100000.00"), pol=replace(pol, income_cap_pct=None))[0]) == [Kind.F1]
    assert help_for(stay("S1", balance="100000.00", fa_discount="-5.00"))[0] == []


def test_the_cap_counts_sums_that_stayed_unconfirmed():
    (f, cap), _, book = help_for(stay("S1", balance="100000.00", doubts=["x"]))
    assert f.severity == "borderline" and f.amount == Decimal("85000.00")
    assert cap.amount == Decimal("6500.00")
    assert book.taken("S1") == Decimal("6500.00")


def test_a_debt_with_two_answers_is_worked_out_on_its_balance_and_confirmed_by_nothing():
    (f,), _, book = help_for(stay("S1", amount_due_coupon="0.00"))
    assert f.amount == Decimal("850.00")
    assert (f.math["balance"], f.math["minus_overcharge"]) == ("1000.00", "0")
    assert f.severity == "borderline"
    assert f.math["why_unsure"] == "your papers do not give one amount you are asked for"
    assert f.trace == []


def test_a_capped_sum_on_a_debt_with_two_answers_is_not_confirmed():
    (_, cap), _, book = help_for(stay("S1", balance="100000.00", amount_due_coupon="0.00"))
    assert cap.severity == "borderline"
    assert cap.math["why_unsure"] == "your papers do not give one amount you are asked for"
    assert book.taken("S1") == 0


def test_a_bill_on_a_sheet_read_with_a_doubt_takes_nothing_off():
    (f,), _, book = help_for(stay("S1", unreadable=True))
    assert f.math["why_unsure"] == "S1 could not be read in full: take a new photo of it"
    assert book.taken("S1") == 0


def test_the_debt_asked_by_a_coupon_counts_when_the_head_prints_no_balance():
    bill = paper("S1", service_from=D, amount_due_coupon="900.00", patient_balance=None)
    (f,), _, _ = help_for(bill)
    assert f.amount == Decimal("765.00")
    assert f.trace[0].field == "amount_due_coupon"


# --- windows ----------------------------------------------------------------------------------

def windows_of(*docs, pol=None, **kw):
    return windows(family(*docs, **kw), pol or policy.load(MEMORIAL))


def rules(**window):
    return replace(policy.load(MEMORIAL), window=window)


def test_each_rule_gives_a_date_and_the_latest_is_the_deadline():
    bill = stay("S1", bill_date=date(2025, 9, 12), service_to=date(2025, 8, 6), insurance_payment_date=date(2025, 9, 2))
    (w,) = windows_of(bill)
    assert list(w.candidates.items()) == [(SERVICE_RULE, date(2026, 8, 6)), (PAYMENT_RULE, date(2026, 9, 2)), (FEDERAL_RULE, date(2026, 5, 10))]
    assert w.deadline == date(2026, 9, 2)
    assert w.first is not None and w.first.doc_id == "S1"
    assert w.flagged is False
    assert w.paid == (date(2025, 9, 2), "S1")


def test_the_rules_stand_in_a_fixed_order():
    pol = rules(after_first_statement_days=90, after_service_days=365, after_last_insurance_payment_months=6)
    (w,) = windows_of(stay("S1", bill_date=date(2025, 9, 12), insurance_payment_date=date(2025, 9, 2)), pol=pol)
    assert list(w.candidates) == [DAYS_RULE, SERVICE_RULE, PAYMENT_RULE, FEDERAL_RULE]
    assert w.candidates[DAYS_RULE] == date(2025, 12, 11)
    assert w.candidates[PAYMENT_RULE] == date(2026, 3, 2)


def test_equal_dates_keep_both_rules():
    (w,) = windows_of(stay("S1", bill_date=date(2025, 9, 12)), pol=policy.load(BAPTIST))
    assert list(w.candidates.items()) == [(DAYS_RULE, date(2026, 5, 10)), (FEDERAL_RULE, date(2026, 5, 10))]
    assert w.deadline == date(2026, 5, 10)
    assert w.paid is None


def test_a_policy_without_a_rule_leaves_only_the_federal_date():
    (w,) = windows_of(stay("S1", bill_date=date(2025, 9, 12)), pol=rules())
    assert list(w.candidates.items()) == [(FEDERAL_RULE, date(2026, 5, 10))]


def test_the_sheet_marked_first_after_discharge_wins_over_an_earlier_bill():
    a = stay("S1", bill_date=date(2025, 9, 1))
    b = stay("S2", bill_date=date(2025, 10, 1), first_after_discharge=True, patient="PATIENT_2")
    (w,) = windows_of(a, b)
    assert (w.first.doc_id, w.flagged) == ("S2", True)
    assert w.candidates[FEDERAL_RULE] == date(2026, 5, 29)


def test_the_earliest_of_the_marked_sheets_is_the_first_bill():
    a = stay("S1", bill_date=date(2025, 10, 1), first_after_discharge=True)
    b = stay("S2", bill_date=date(2025, 9, 20), first_after_discharge=True, patient="PATIENT_2")
    assert windows_of(a, b)[0].first.doc_id == "S2"


def test_a_marked_sheet_with_no_date_marks_nothing():
    a = stay("S1", first_after_discharge=True)
    b = stay("S2", bill_date=date(2025, 10, 1), patient="PATIENT_2")
    (w,) = windows_of(a, b)
    assert (w.first.doc_id, w.flagged) == ("S2", False)


def test_with_no_mark_the_earliest_bill_is_the_first_and_a_tie_goes_to_the_first_paper():
    a = stay("S1", bill_date=date(2025, 10, 1))
    b = stay("S2", bill_date=date(2025, 9, 20), patient="PATIENT_2")
    c = stay("S3", bill_date=date(2025, 9, 20), patient="PATIENT_3")
    (w,) = windows_of(a, b, c)
    assert (w.first.doc_id, w.flagged) == ("S2", False)


def test_a_stay_with_no_bill_date_counts_from_the_care_and_stands_on_its_first_paper():
    (w,) = windows_of(stay("S1"), stay("S2", patient="PATIENT_2"))
    assert list(w.candidates.items()) == [(SERVICE_RULE, date(2026, 8, 4))]
    assert (w.first.doc_id, w.flagged, w.paid) == ("S1", False, None)


def test_a_stay_with_no_date_at_all_gives_no_window():
    assert windows_of(stay("S1", service=None)) == []
    assert windows_of(stay("S1"), pol=policy.load(BAPTIST)) == []


def test_a_policy_year_lands_on_the_same_day_next_year_even_from_a_leap_day():
    (w,) = windows_of(stay("S1", service=date(2024, 2, 29)))
    assert w.candidates[SERVICE_RULE] == date(2025, 2, 28)


def test_other_periods_after_service_are_counted_in_days():
    (w,) = windows_of(stay("S1", service=date(2024, 2, 29)), pol=rules(after_service_days=300))
    assert w.candidates[SERVICE_RULE] == date(2024, 12, 25)


def test_the_year_after_service_runs_from_the_latest_care_of_the_stay():
    a = stay("S1", service_to=after(2))
    b = stay("S2", service=after(5), patient="PATIENT_2")
    (w,) = windows_of(a, b)
    assert w.candidates[SERVICE_RULE] == date(2026, 8, 9)


def test_the_latest_payment_counts_and_a_tie_goes_to_the_larger_sheet_name():
    a = stay("S1", insurance_payment_date=date(2025, 9, 2))
    b = stay("S2", insurance_payment_date=date(2025, 9, 20), patient="PATIENT_2")
    c = stay("S9", insurance_payment_date=date(2025, 9, 20), patient="PATIENT_3")
    d = stay("S10", insurance_payment_date=date(2025, 9, 20), patient="PATIENT_4")
    (w,) = windows_of(a, b, c, d)
    assert w.paid == (date(2025, 9, 20), "S9")
    assert w.candidates[PAYMENT_RULE] == date(2026, 9, 20)


def test_the_date_of_the_hospitals_insurance_statement_stands_for_the_payment():
    plan = eob("S2", L(1, "0110", "0.00"), statement_date=date(2025, 9, 15))
    (w,) = windows_of(stay("S1"), plan)
    assert w.paid == (date(2025, 9, 15), "S2")
    assert w.candidates[PAYMENT_RULE] == date(2026, 9, 15)


def test_a_paper_with_no_dates_counts_only_when_there_is_one_stay():
    plan = eob("S3", Line(line_no=1, code="0110", charges="900.00"), statement_date=date(2025, 12, 1))
    (w,) = windows_of(stay("S1"), plan)
    assert w.paid == (date(2025, 12, 1), "S3")
    found = windows_of(stay("S1"), stay("S2", service=after(30)), plan)
    assert [w.paid for w in found] == [None, None]


def test_a_stay_already_paid_still_counts_as_a_stay_for_a_paper_with_no_dates():
    plan = eob("S3", Line(line_no=1, code="0110", charges="900.00"), statement_date=date(2025, 12, 1))
    (w,) = windows_of(stay("S1"), stay("S2", service=after(30), balance="0.00"), plan)
    assert w.first.doc_id == "S1" and w.paid is None


@pytest.mark.parametrize("sheet", [{"balance": "0.00"}, {"balance": None}, {"balance": "300.00", "due_from_insurance": "300.00"}, {"balance": "-40.00"}])
def test_a_stay_with_nothing_asked_of_the_family_gives_no_window(sheet):
    assert windows_of(stay("S1", bill_date=date(2025, 9, 12), **sheet)) == []


def test_one_bill_asking_money_opens_the_window_for_its_whole_stay():
    a = stay("S1", bill_date=date(2025, 9, 1), balance="0.00")
    b = stay("S2", bill_date=date(2025, 10, 1), patient="PATIENT_2")
    assert windows_of(a, b)[0].first.doc_id == "S1"


def test_only_hospital_bills_count():
    assert windows_of(stay("S1", provider=OFFICE, bill_date=date(2025, 9, 12))) == []


def test_a_window_is_given_for_each_stay_soonest_first():
    later = stay("S1", service=date(2026, 3, 1))
    sooner = stay("S2", service=date(2025, 8, 1))
    found = windows_of(later, sooner)
    assert [(w.first.doc_id, w.deadline) for w in found] == [("S2", date(2026, 8, 1)), ("S1", date(2027, 3, 1))]


def test_an_older_stay_with_the_later_date_comes_second():
    older = stay("S1", service=date(2025, 1, 10), insurance_payment_date=date(2025, 12, 1))
    newer = stay("S2", service=date(2025, 6, 1))
    found = windows_of(older, newer)
    assert [(w.first.doc_id, w.deadline) for w in found] == [("S2", date(2026, 6, 1)), ("S1", date(2026, 12, 1))]


def test_two_stays_with_the_same_date_keep_their_order():
    a = stay("S1", service=date(2025, 1, 10), insurance_payment_date=date(2025, 6, 1))
    b = stay("S2", service=date(2025, 6, 1))
    assert [w.first.doc_id for w in windows_of(a, b)] == ["S1", "S2"]


def test_a_payment_of_a_later_stay_does_not_move_an_earlier_one():
    first = stay("S1", service=date(2025, 3, 1))
    second = stay("S2", service=date(2025, 9, 1), insurance_payment_date=date(2025, 10, 1))
    plan = eob("S3", L(1, "0110", "0.00", service_date=date(2025, 3, 1)), statement_date=date(2025, 4, 1))
    found = windows_of(first, second, plan)
    assert [(w.first.doc_id, w.paid) for w in found] == [("S1", (date(2025, 4, 1), "S3")), ("S2", (date(2025, 10, 1), "S2"))]


# --- run --------------------------------------------------------------------------------------

def all_found(report):
    return report.findings + report.worth_asking


def by_kind(report, kind):
    return [f for f in all_found(report) if f.kind == kind]


@needs_text
def test_an_empty_pile_is_an_empty_report():
    r = checks.run(family())
    assert (r.case_id, r.policy_id, r.fpl_pct) == ("t", MEMORIAL, Decimal("257.6"))
    assert (r.findings, r.no_money, r.held_back, r.worth_asking, r.not_sent) == ([], [], [], [], [])
    assert str(r.total_may_come_off) == "0.00"
    assert (r.apply_by, r.apply_by_sure) == (None, True)


def test_an_unknown_policy_stops_the_run():
    with pytest.raises(FileNotFoundError):
        checks.run(family(policy_id="no-such-policy"))


@needs_text
def test_every_finding_in_the_report_comes_in_a_fixed_order():
    anesthesia = paper("S1", provider=ANESTHESIA, account_ref="[ACCT_1]", patient_balance="900.00", claim_ref="C9")
    hospital = stay("S2", bill_date=date(2025, 9, 1), balance="1200.00", lines=[L(1, "0110", "300.00"), L(2, "0250", "90.00"), L(3, "0250", "90.00")])
    plan = eob("S3", L(1, "0110", "100.00"), L(2, "01960", "200.00", claim_ref="C9", denial_codes="X17", insurance_paid="0.00"),
               statement_date=date(2025, 8, 20), insurance_payment_date=date(2025, 8, 20))
    r = checks.run(family(anesthesia, hospital, plan, context=["out_of_network", "employer_plan"]))
    assert kinds(r.findings) == [Kind.E1, Kind.E2, Kind.N1, Kind.F1, Kind.F2, Kind.A1]
    assert kinds(r.worth_asking) == [Kind.I1]


@needs_text
def test_a_double_line_comes_off_before_an_overcharge():
    bill = paper("S1", provider=OFFICE, patient_balance="150.00", lines=[L(1, share="100.00"), L(2, share="100.00")])
    r = checks.run(family(bill, eob("S2", L(1, share="40.00"))))
    assert [(f.kind, f.amount) for f in r.findings] == [(Kind.E2, Decimal("100.00"))]
    (e1,) = r.worth_asking
    assert e1.math["why_unsure"] == "it would take off more than the $50.00 your papers still ask for"
    assert e1.math["amount_if_confirmed"] == "60.00"


@needs_text
def test_only_the_second_print_of_a_double_is_kept_from_the_overcharge_check():
    bill = paper("S1", provider=OFFICE, patient_balance="1000.00", lines=[L(1, share="100.00"), L(2, share="100.00"), L(3, share="100.00")])
    r = checks.run(family(bill, eob("S2", L(1, share="40.00"), L(2, share="40.00"))))
    assert [f.amount for f in by_kind(r, Kind.E2)] == [Decimal("100.00"), Decimal("100.00")]
    (e1,) = by_kind(r, Kind.E1)
    assert (e1.evidence[0].line_no, e1.evidence[1].line_no) == (1, 1)


@needs_text
def test_the_same_double_on_a_second_paper_keeps_its_first_print_for_the_overcharge_check():
    lines = [L(1, share="100.00"), L(2, share="100.00")]
    a = paper("S1", provider=OFFICE, account_ref="[ACCT_1]", patient_balance="900.00", lines=lines)
    b = paper("S2", DocKind.ITEMIZED_BILL, provider=OFFICE, account_ref="[ACCT_2]", patient_balance="800.00", lines=lines)
    r = checks.run(family(a, b, eob("S3", L(1, share="40.00"), L(2, share="40.00"))))
    assert len(by_kind(r, Kind.E2)) == 1
    assert [e.evidence[0].doc_id for e in by_kind(r, Kind.E1)] == ["S1", "S2"]


class OnePrice:
    """A hospital's published file with one cash price and one plan rate: made up, the real files are not touched."""
    hospital, url, last_updated_on, version = "Seaside", "https://example.org/file.csv", "2026-05-01", "1"

    def plan_rates(self, payer, plan, code_type, code):
        return [prices.Rate("CPT", code, "Delivery", "inpatient", Decimal("2500.00"), "case rate", 7)] if code_type == "CPT" else []


@needs_text
def test_a_cash_price_comes_off_before_the_discount(monkeypatch):
    price = prices.Price("CPT", "99213", "Visit", "outpatient", Decimal("1000.00"), Decimal("700.00"), 9)
    monkeypatch.setattr(prices, "load", lambda policy_id: OnePrice())
    monkeypatch.setattr(prices, "match", lambda index, code, charge: (price, 1))
    bill = stay("S1", balance="1000.00", lines=[L(1, charges="1000.00")])
    r = checks.run(family(bill, insured=False))
    assert [(f.kind, f.amount) for f in r.findings if f.amount] == [(Kind.C1, Decimal("300.00")), (Kind.F1, Decimal("595.00"))]


@needs_text
def test_what_the_plan_allowed_over_its_rate_comes_off_before_the_discount(monkeypatch):
    monkeypatch.setattr(prices, "load", lambda policy_id: OnePrice())
    plan_line = L(1, "59400", "3000.00", charges="5000.00", adjustment="-2000.00")
    bill = stay("S1", balance="3000.00")
    r = checks.run(family(bill, eob("S2", plan_line, provider=HOSPITAL), plan=Plan(payer="Aetna", plan_name="Qualified Health Plan")))
    assert [(f.kind, f.amount) for f in r.findings if f.amount] == [(Kind.C2, Decimal("500.00")), (Kind.F1, Decimal("2125.00"))]


@needs_text
def test_the_discount_counts_what_is_left_after_a_double_and_an_overcharge():
    bill = stay("S1", balance="1000.00", lines=[L(1, "0110", "300.00"), L(2, "0250", "90.00"), L(3, "0250", "90.00")])
    r = checks.run(family(bill, eob("S2", L(1, "0110", "100.00"))))
    assert [(f.kind, f.amount) for f in r.findings if f.amount] == [
        (Kind.E1, Decimal("200.00")), (Kind.E2, Decimal("90.00")), (Kind.F1, Decimal("603.50"))]  # 85% of 710.00
    assert r.total_may_come_off == Decimal("893.50")


@needs_text
def test_a_credit_on_an_account_that_still_asks_money_has_no_sum():
    old = paper("S1", provider=OFFICE, account_ref="[ACCT_1]", patient_balance="-40.00", statement_date=date(2025, 11, 1))
    new = paper("S2", provider=OFFICE, account_ref="[ACCT_1]", patient_balance="300.00", statement_date=date(2025, 10, 1))
    newest = paper("S3", provider=OFFICE, account_ref="[ACCT_1]", patient_balance="300.00", statement_date=date(2025, 12, 1))
    r = checks.run(family(old, new, newest))
    (e3,) = by_kind(r, Kind.E3)
    assert (e3.amount, e3.severity) == (None, "borderline")
    assert e3.math["why_unsure"] == "this account also asks you for money: ask whether the credit is already taken off"
    assert e3.math["amount_if_confirmed"] == "40.00"
    assert r.total_may_come_off == 0


@needs_text
def test_a_credit_on_an_account_that_asks_nothing_stays_confirmed():
    r = checks.run(family(paper("S1", provider=OFFICE, account_ref="[ACCT_1]", patient_balance="-40.00")))
    (e3,) = r.findings
    assert (e3.kind, e3.amount, e3.severity) == (Kind.E3, Decimal("40.00"), "high")


@needs_text
def test_no_assistance_finding_no_date_to_apply_by():
    r = checks.run(family(stay("S1", bill_date=date(2025, 9, 12), fa_discount="-5.00")))
    assert by_kind(r, Kind.F2) == [] and r.apply_by is None
    r = checks.run(family(stay("S1", bill_date=date(2025, 9, 12)), policy_id=BAPTIST))
    assert by_kind(r, Kind.F2) == [] and r.apply_by is None


@needs_text
def test_an_assistance_finding_with_no_sum_still_brings_the_date():
    r = checks.run(family(stay("S1", bill_date=date(2025, 9, 12)), annual_income=Decimal(30000), liquid_assets=None))
    assert kinds(r.worth_asking) == [Kind.F1, Kind.I1]
    assert kinds(r.findings) == [Kind.F2]
    assert r.apply_by == date(2026, 8, 4)
    assert r.apply_by_sure is True


@needs_text
def test_a_line_with_a_finding_loses_its_nothing_to_dispute_note():
    bill = paper("S1", provider=OFFICE, patient_balance="500.00", lines=[L(1, share="100.00"), L(2, share="100.00"), L(3, "0250", "50.00")])
    plan = eob("S2", L(1, share="100.00"), L(2, "0250", "50.00"))
    r = checks.run(family(bill, plan))
    assert [m.title for m in r.no_money] == ["Doctors' bills are outside the hospital's assistance policy",
                                             "Sheet 1 line 3 matches your insurance statement"]


@needs_text
def test_every_finding_comes_out_with_a_severity_laws_and_plain_words():
    r = checks.run(family(stay("S1", bill_date=date(2025, 9, 12))))
    (f1, f2) = r.findings
    assert (f1.severity, f2.severity) == ("high", "high")
    assert f1.explain == explain.finding("F1") and f2.explain == explain.finding("F2")
    assert f1.laws == F1_LAWS
    assert f2.laws == F2_LAWS


@needs_text
def test_plain_words_a_check_wrote_itself_stay():
    first = paper("S1", provider=OFFICE, account_ref="[ACCT_1]", patient_balance="-40.00", statement_date=date(2025, 9, 1))
    later = paper("S2", provider=OFFICE, account_ref="[ACCT_1]", patient_balance="-40.00", statement_date=date(2025, 8, 1), amount_due_coupon="60.00")
    r = checks.run(family(first, later))
    (e3,) = by_kind(r, Kind.E3)
    assert e3.explain == "The sum this sheet asks for looks like it already took this credit off, so it is not extra money back."


@needs_text
def test_a_law_whose_quote_does_not_verify_leaves_the_finding():
    real = policy.verified
    try:
        policy.verified = lambda ref: ref != "federal-501r-5#agb-limit" and real(ref)
        (f1, _) = checks.run(family(stay("S1", bill_date=date(2025, 9, 12)))).findings
    finally:
        policy.verified = real
    assert "federal-501r-5#agb-limit" not in f1.laws


@needs_text
def test_a_date_resting_on_a_sheet_read_with_a_doubt_is_one_to_check():
    r = checks.run(family(stay("S1", bill_date=date(2025, 9, 12), doubts=["x"])))
    assert kinds(r.findings) == []
    (f2,) = by_kind(r, Kind.F2)
    assert f2.math["why_unsure"] == "S1 could not be read in full: take a new photo of it"
    assert f2.deadline == date(2026, 8, 4)
    assert (r.apply_by, r.apply_by_sure) == (date(2026, 8, 4), False)


@needs_text
def test_an_appeal_date_resting_on_a_doubted_sheet_is_one_to_check():
    plan = eob("S1", L(1, share="80.00", denial_codes="X17", insurance_paid="0.00"), statement_date=date(2025, 9, 1), unreadable=True)
    r = checks.run(family(plan, context=["employer_plan"]))
    (a1,) = by_kind(r, Kind.A1)
    assert a1.severity == "borderline" and a1.deadline == date(2026, 2, 28)
    assert a1.math["why_unsure"] == "S1 could not be read in full: take a new photo of it"


@needs_text
def test_a_finding_with_no_sum_and_no_date_keeps_its_words_on_a_doubted_sheet():
    r = checks.run(family(stay("S1", balance="400.00", doubts=["x"])))  # under the minimum
    (i1,) = by_kind(r, Kind.I1)
    assert "why_unsure" not in i1.math


@needs_text
def test_a_finding_on_a_quote_not_verified_is_held_back_with_the_reason():
    real = policy.verified
    try:
        policy.verified = lambda ref: ref != f"{MEMORIAL}#scale-mrh" and real(ref)
        r = checks.run(family(stay("S1", bill_date=date(2025, 9, 12))))
    finally:
        policy.verified = real
    (f1,) = r.held_back
    assert f1.kind == Kind.F1
    assert f1.detail.endswith(f"Sheet S1 has no discount yet. [held back: unverified {MEMORIAL}#scale-mrh]")
    assert kinds(r.findings) == [Kind.F2]
    assert r.total_may_come_off == 0


@needs_text
def test_every_ref_not_verified_is_named_in_the_order_of_the_finding():
    real = policy.verified
    try:
        policy.verified = lambda ref: not ref.startswith(MEMORIAL) and real(ref)
        r = checks.run(family(stay("S1", bill_date=date(2025, 9, 12))))
    finally:
        policy.verified = real
    assert r.held_back[0].detail.endswith(f"[held back: unverified {MEMORIAL}#scale-mrh, {MEMORIAL}#insured-balances]")


@needs_text
def test_a_held_back_finding_can_be_money_in_doubt_too():
    real = policy.verified
    try:
        policy.verified = lambda ref: ref != f"{MEMORIAL}#scale-mrh" and real(ref)
        r = checks.run(family(stay("S1", doubts=["x"])))
    finally:
        policy.verified = real
    assert r.held_back[0].severity == "borderline"
    assert r.held_back[0].amount == Decimal("850.00")


@needs_text
def test_a_note_on_a_quote_not_verified_is_left_out():
    bill = stay("S1", provider=OFFICE)
    real = policy.verified
    try:
        assert len(checks.run(family(bill)).no_money) == 1  # must light
        policy.verified = lambda ref: ref != f"{MEMORIAL}#facilities-only" and real(ref)
        assert checks.run(family(bill)).no_money == []
    finally:
        policy.verified = real


@needs_text
def test_one_paper_read_twice_counts_once_and_says_so():
    bill = stay("S1", bill_date=date(2025, 9, 12), balance="1000.00")
    r = checks.run(family(bill, bill.model_copy(update={"doc_id": "S2"})))
    assert [f.amount for f in by_kind(r, Kind.F1)] == [Decimal("850.00")]
    (n,) = r.no_money
    assert (n.kind, n.title, n.detail) == (Kind.NM, "S2 is the same paper as S1", "We counted it once.")
    assert n.evidence == [Evidence(doc_id="S1"), Evidence(doc_id="S2", note="same paper")]


@needs_text
def test_the_notes_come_in_order_policy_then_matches_then_same_paper():
    bill = paper("S1", provider=OFFICE, patient_balance="100.00", lines=[L(1, share="100.00")])
    r = checks.run(family(bill, bill.model_copy(update={"doc_id": "S2"}), eob("S3", L(1, share="100.00"))))
    assert [n.title for n in r.no_money] == ["Doctors' bills are outside the hospital's assistance policy",
                                             "Sheet 1 line 1 matches your insurance statement", "S2 is the same paper as S1"]


@needs_text
def test_a_date_after_today_does_not_count():
    r = checks.run(family(stay("S1", bill_date=date(2027, 1, 1)), today=date(2026, 1, 1)))
    (f2,) = by_kind(r, Kind.F2)
    assert f2.deadline == date(2026, 8, 4)  # a year after the care: no first bill to count from
    assert list(f2.math) == [SERVICE_RULE, "why_unsure", "retake"]
    assert (r.apply_by, r.apply_by_sure) == (date(2026, 8, 4), False)


@needs_text
def test_the_percent_uses_the_guideline_year_of_the_policy(monkeypatch):
    monkeypatch.setitem(fpl.GUIDELINES, 2027, {"base": [100000] * 8, "each_extra": 1000})
    assert checks.run(family()).fpl_pct == Decimal("257.6")


@needs_text
def test_a_policy_with_no_guideline_year_uses_the_latest_table(monkeypatch):
    monkeypatch.setitem(fpl.GUIDELINES, 2027, {"base": [100000] * 8, "each_extra": 1000})
    pol = replace(policy.load(MEMORIAL), fpg_year=None)
    monkeypatch.setattr(policy, "load", lambda policy_id: pol)
    assert checks.run(family()).fpl_pct == Decimal("85.0")


@needs_text
def test_a_run_leaves_the_case_as_it_was_and_gives_the_same_report_twice():
    bill = stay("S1", bill_date=date(2027, 12, 1), balance="1000.00", lines=[L(1, "0110", "300.00")])
    case = family(bill, bill.model_copy(update={"doc_id": "S2"}), eob("S3", L(1, "0110", "100.00")))
    before = case.model_dump_json()
    first = checks.run(case)
    assert case.model_dump_json() == before
    assert checks.run(case) == first


@needs_text
def test_a_borderline_sum_stays_out_of_the_total():
    r = checks.run(family(stay("S1"), stay("S2", service=after(30), balance="400.00", doubts=["x"])))
    assert r.total_may_come_off == Decimal("850.00")
    (doubted,) = [f for f in r.worth_asking if f.kind == Kind.F1]
    assert doubted.amount is None
    assert doubted.math["amount_if_confirmed"] == "340.00"


# --- found by the independent review ----------------------------------------------------------

CREDIT_WHY = "this account also asks you for money: ask whether the credit is already taken off"


def credit_and_double(provider, balance="150.00"):
    day = date(2026, 1, 5)
    credit = paper("S1", provider=provider, account_ref="A-77", statement_date=date(2026, 1, 10), patient_balance="-40.00")
    asks = paper("S2", provider=provider, account_ref="A-77", statement_date=date(2026, 2, 10), patient_balance=balance,
                 lines=[L(1, charges="150.00", share="150.00", service_date=day), L(2, charges="150.00", share="150.00", service_date=day)])
    return family(credit, asks, today=date(2026, 3, 2))


@needs_text
@pytest.mark.parametrize("provider,balance", [(OFFICE, "150.00"), (HOSPITAL, "150.00"), (OFFICE, "300.00")])
def test_a_credit_is_a_question_while_the_papers_ask_money_even_when_a_double_took_it_all_off(provider, balance):
    r = checks.run(credit_and_double(provider, balance))
    (e3,) = [f for f in r.worth_asking if f.kind == Kind.E3]
    assert e3.amount is None
    assert e3.math["amount_if_confirmed"] == "40.00" and e3.math["why_unsure"] == CREDIT_WHY
    assert [f.amount for f in r.findings if f.kind == Kind.E2] == [Decimal("150.00")]
    assert r.total_may_come_off == Decimal("150.00")


@needs_text
def test_line_number_zero_is_no_number_so_a_finding_on_it_leaves_the_match_note():
    day = date(2026, 1, 5)
    bill = paper("S1", provider=OFFICE, patient_balance="200.00",
                 lines=[L(0, charges="100.00", share="100.00", service_date=day), L(1, charges="100.00", share="100.00", service_date=day)])
    r = checks.run(family(bill, eob("S2", L(1, charges="100.00", share="100.00", service_date=day))))
    assert "Sheet 1 line 0 matches your insurance statement" in [n.title for n in r.no_money]


def test_a_zero_finding_leaves_the_places_of_what_is_still_owed_to_the_cap():
    mom = stay("S1", balance="100000", fa_discount="-1000")
    baby = stay("S2", service=after(1), balance="100", patient="PATIENT_2", lines=[L(1, share="100"), L(2, share="100")])
    case = family(mom, baby)
    book = Book(case)
    assert book.take("S2", Decimal("100")) == ""  # the double, already off
    found, _ = check_assistance(case, policy.load(MEMORIAL), PCT, book)
    assert [(f.kind, f.amount) for f in found] == [(Kind.F3, Decimal("0.00")), (Kind.F1, Decimal("91500.00"))]
    assert found[1].math["owed_after_discount"] == "100000"
    assert found[1].math["cap"] == "8500.00"
