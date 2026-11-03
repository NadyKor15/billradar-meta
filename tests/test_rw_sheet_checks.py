"""Current behaviour of the paper-only checks, past what test_sheet_checks and test_money_ceiling pin.

Titles, details, evidence and math go into the review request as they stand, so these tests compare whole findings and
the order of the math keys, not fragments.
"""
from datetime import date
from decimal import Decimal

import pytest

from billradar import sheet_checks
from billradar.case import Case, DocKind, Document, Line, Person, Profile, Role, Source
from billradar.checks import Evidence, Finding, Kind
from billradar.ledger import Step

DAY = date(2025, 8, 4)
NEXT_DAY = date(2025, 8, 5)
TODAY = date(2026, 3, 16)
OFFICE = "Little Harbor Pediatrics"
INSIDE = "The sum this sheet asks for looks like it already took this credit off, so it is not extra money back."


def make(*docs: Document, letterhead: str = "") -> Case:
    profile = Profile(household_size=3, annual_income=Decimal("58000"),
                      people=[Person(token="PATIENT_1", role=Role.MOTHER), Person(token="PATIENT_2", role=Role.NEWBORN),
                              Person(token="PATIENT_3", role=Role.PATIENT)])
    return Case(case_id="t", policy_id="memorial-2026-05", letterhead=letterhead, today=TODAY, profile=profile, documents=list(docs))


def amount(text: str | None) -> Decimal | None:
    return None if text is None else Decimal(text)


def line(no: int, code: str = "", charges: str | None = None, share: str | None = None, when: date | None = DAY, **kw) -> Line:
    return Line(line_no=no, code=code, charges=amount(charges), patient_responsibility=amount(share), service_date=when, **kw)


def doc(doc_id: str, kind: DocKind = DocKind.HOSPITAL_STATEMENT, patient: str = "PATIENT_1", **kw) -> Document:
    kw.setdefault("source", Source.PAPER)
    for name in ("patient_balance", "amount_due_coupon", "due_from_insurance", "insurance_paid"):
        if isinstance(kw.get(name), str):
            kw[name] = Decimal(kw[name])
    return Document(doc_id=doc_id, kind=kind, patient=patient, **kw)


def eob(doc_id: str, **kw) -> Document:
    return doc(doc_id, DocKind.EOB, **kw)


def where(finding: Finding) -> list[tuple]:
    return [(e.doc_id, e.line_no, e.note) for e in finding.evidence]


# --- duplicates -------------------------------------------------------------------------------

def test_a_double_line_gives_every_field_of_the_finding():
    bill = doc("S7", lines=[line(1, "01960", "2200.00", "550.00"), line(2, "01960", "2200.00", "412.50")])
    found = sheet_checks.duplicates(make(bill))
    assert found == [Finding(
        kind=Kind.E2, title="Same service billed twice on sheet 7",
        detail=("Lines 1 and 2 are the same code 01960 on Aug 4, 2025 for $2,200.00 each. "
                "You are asked to pay $412.50 for the second one."),
        amount=Decimal("412.50"),
        evidence=[Evidence(doc_id="S7", line_no=1), Evidence(doc_id="S7", line_no=2)],
        trace=[Step(doc_id="S7", line_no=2, field="patient_responsibility", printed=Decimal("412.50"),
                    role="asked for the second one")],
        math={"code": "01960", "service_date": "2025-08-04", "charges": "2200.00",
              "second_patient_responsibility": "412.50"})]
    assert list(found[0].math) == ["code", "service_date", "charges", "second_patient_responsibility"]


@pytest.mark.parametrize("second_share", [None, "0.00", "-5.00"])
def test_a_second_line_that_asks_nothing_gives_a_double_with_no_sum(second_share):
    bill = doc("S2", lines=[line(1, "99213", "150.00", "30.00"), line(2, "99213", "150.00", second_share)])
    (f,) = sheet_checks.duplicates(make(bill))
    assert f.amount is None and f.trace == []
    assert f.detail == "Lines 1 and 2 are the same code 99213 on Aug 4, 2025 for $150.00 each."
    assert f.math["second_patient_responsibility"] == "0"


def test_the_text_of_a_double_keeps_the_day_without_a_leading_zero_and_the_digit_after_the_first_letter():
    bill = doc("D12", lines=[line(4, "A", "1234567.50", None, date(2025, 12, 1)), line(9, "A", "1234567.50", None, date(2025, 12, 1))])
    (f,) = sheet_checks.duplicates(make(bill))
    assert f.title == "Same service billed twice on sheet 12"
    assert f.detail == "Lines 4 and 9 are the same code A on Dec 1, 2025 for $1,234,567.50 each."


def test_a_charge_keeps_its_own_printed_form_in_math():
    bill = doc("S1", lines=[line(1, "A", "1100", None), line(2, "A", "1100.00", None)])
    (f,) = sheet_checks.duplicates(make(bill))  # Decimal("1100") == Decimal("1100.00"): one charge, the second line is shown
    assert f.math["charges"] == "1100.00"
    assert sheet_checks.duplicates(make(doc("S1", lines=[line(1, "A", "1100", None), line(2, "A", "1100", None)])))[0].math["charges"] == "1100"


def test_a_free_line_printed_twice_is_a_double_too():
    (f,) = sheet_checks.duplicates(make(doc("S1", lines=[line(1, "A", "0.00", None), line(2, "A", "0.00", None)])))
    assert f.detail == "Lines 1 and 2 are the same code A on Aug 4, 2025 for $0.00 each."


def test_code_case_does_not_separate_lines_and_the_second_line_prints_the_code():
    (f,) = sheet_checks.duplicates(make(doc("S1", lines=[line(1, "j1100", "10.00", None), line(2, "J1100", "10.00", None)])))
    assert f.math["code"] == "J1100" and "same code J1100 on" in f.detail
    (f,) = sheet_checks.duplicates(make(doc("S1", lines=[line(1, "J1100", "10.00", None), line(2, "j1100", "10.00", None)])))
    assert f.math["code"] == "j1100"


def test_spaces_around_a_code_keep_lines_apart():
    assert sheet_checks.duplicates(make(doc("S1", lines=[line(1, "01960", "10.00", None), line(2, "01960 ", "10.00", None)]))) == []


@pytest.mark.parametrize("second", [line(2, "", "10.00", None), line(2, "A", None, None), line(2, "A", "10.01", None), line(2, "B", "10.00", None),
                                    line(2, "A", "10.00", None, NEXT_DAY)])
def test_a_line_that_differs_or_lacks_a_code_or_a_charge_is_no_double(second):
    assert sheet_checks.duplicates(make(doc("S1", lines=[line(1, "A", "10.00", None), second]))) == []


def test_three_equal_lines_on_a_sheet_give_two_doubles_each_against_the_first_line():
    found = sheet_checks.duplicates(make(doc("S1", lines=[line(1, "A", "10.00", "1.00"), line(2, "A", "10.00", "2.00"), line(3, "A", "10.00", "3.00")])))
    assert [where(f) for f in found] == [[("S1", 1, ""), ("S1", 2, "")], [("S1", 1, ""), ("S1", 3, "")]]
    assert [f.amount for f in found] == [Decimal("2.00"), Decimal("3.00")]


def test_a_later_paper_joins_the_last_double_of_that_service():
    bill = doc("S1", lines=[line(1, "A", "10.00", "1.00"), line(2, "A", "10.00", "2.00"), line(3, "A", "10.00", "3.00")])
    statement = eob("S2", lines=[line(1, "A", "10.00", "4.00"), line(2, "A", "10.00", "4.00")])
    first, second = sheet_checks.duplicates(make(bill, statement))
    assert len(first.evidence) == 2 and len(second.evidence) == 4


def test_two_different_doubles_on_a_sheet_follow_the_order_of_the_lines():
    found = sheet_checks.duplicates(make(doc("S1", lines=[
        line(1, "B", "10.00", None), line(2, "A", "20.00", None), line(3, "A", "20.00", None), line(4, "B", "10.00", None)])))
    assert [f.math["code"] for f in found] == ["A", "B"]


def test_a_claim_the_plan_took_back_is_not_a_double():
    took_back = doc("S1", lines=[line(1, "A", "100.00", "20.00"), line(2, "A", "-100.00", "-20.00"), line(3, "A", "100.00", "20.00")])
    assert sheet_checks.duplicates(make(took_back)) == []
    both_stand = doc("S1", lines=[line(1, "A", "100.00", "20.00"), line(3, "A", "100.00", "20.00")])
    assert len(sheet_checks.duplicates(make(both_stand))) == 1  # must differ: without the reversal it is a double


def test_a_reversal_with_nothing_to_cancel_is_not_a_line_at_all():
    lonely = doc("S1", lines=[line(1, "A", "-100.00", None), line(2, "A", "-100.00", None)])
    assert sheet_checks.duplicates(make(lonely)) == []


@pytest.mark.parametrize("kind", [DocKind.ITEMIZED_BILL, DocKind.FA_LETTER, DocKind.PAYMENT_RECEIPT, DocKind.OTHER, DocKind.EOB])
def test_every_kind_of_paper_is_checked_for_doubles(kind):
    assert len(sheet_checks.duplicates(make(doc("S1", kind, lines=[line(1, "A", "10.00", None), line(2, "A", "10.00", None)])))) == 1


def test_the_same_double_on_the_insurance_statement_joins_the_bill_even_when_the_statement_lies_first():
    bill = doc("S1", lines=[line(3, "01960", "2200.00", "550.00"), line(4, "01960", "2200.00", "550.00")])
    statement = eob("S2", lines=[line(7, "01960", "2200.00", "500.00"), line(8, "01960", "2200.00", "500.00")])
    (f,) = sheet_checks.duplicates(make(statement, bill))
    assert where(f) == [("S1", 3, ""), ("S1", 4, ""), ("S2", 7, "also twice here"), ("S2", 8, "")]
    assert f.amount == Decimal("550.00") and "amount_from" not in f.math and len(f.trace) == 1
    assert f.detail.endswith("You are asked to pay $550.00 for the second one.")


def test_an_insurance_statement_gives_the_sum_a_bill_did_not_print():
    bill = doc("S1", lines=[line(1, "01960", "2200.00", None), line(2, "01960", "2200.00", None)])
    statement = eob("S2", lines=[line(5, "01960", "2200.00", "100.00"), line(6, "01960", "2200.00", "550.00")])
    (f,) = sheet_checks.duplicates(make(bill, statement))
    assert f.amount == Decimal("550.00")
    assert f.detail == ("Lines 1 and 2 are the same code 01960 on Aug 4, 2025 for $2,200.00 each. "
                        "Your insurance statement shows $550.00 for the second one.")
    assert f.trace == [Step(doc_id="S2", line_no=6, field="patient_responsibility", printed=Decimal("550.00"),
                            role="your insurance shows for the second one")]
    assert f.math == {"code": "01960", "service_date": "2025-08-04", "charges": "2200.00",
                      "second_patient_responsibility": "550.00", "amount_from": "S2"}
    assert list(f.math)[-1] == "amount_from"


def test_the_first_paper_with_a_share_gives_the_sum_and_later_papers_only_add_evidence():
    bill = doc("S1", lines=[line(1, "A", "10.00", None), line(2, "A", "10.00", None)])
    first = eob("S2", lines=[line(1, "A", "10.00", None), line(2, "A", "10.00", "3.00")])
    second = eob("S3", lines=[line(1, "A", "10.00", None), line(2, "A", "10.00", "4.00")])
    (f,) = sheet_checks.duplicates(make(bill, first, second))
    assert f.amount == Decimal("3.00") and f.math["amount_from"] == "S2" and len(f.evidence) == 6 and len(f.trace) == 1


def test_a_second_bill_joins_the_first_one_and_its_sum_is_still_worded_as_the_insurance_statement():
    bill = doc("S1", lines=[line(1, "A", "10.00", None), line(2, "A", "10.00", None)])
    copy = doc("S2", DocKind.ITEMIZED_BILL, lines=[line(3, "A", "10.00", None), line(4, "A", "10.00", "2.00")])
    (f,) = sheet_checks.duplicates(make(bill, copy))
    assert where(f)[2:] == [("S2", 3, "also twice here"), ("S2", 4, "")]
    assert f.detail.endswith(" Your insurance statement shows $2.00 for the second one.")


@pytest.mark.parametrize("share", [None, "0.00", "-1.00"])
def test_a_later_paper_without_a_share_leaves_the_double_without_a_sum(share):
    bill = doc("S1", lines=[line(1, "A", "10.00", None), line(2, "A", "10.00", None)])
    statement = eob("S2", lines=[line(1, "A", "10.00", None), line(2, "A", "10.00", share)])
    (f,) = sheet_checks.duplicates(make(bill, statement))
    assert f.amount is None and len(f.evidence) == 4 and f.trace == [] and "amount_from" not in f.math


def test_a_later_paper_with_another_charge_joins_by_date_and_code():
    bill = doc("S1", lines=[line(1, "A", "10.00", None), line(2, "A", "10.00", None)])
    statement = eob("S2", lines=[line(1, "A", "99.00", None), line(2, "A", "99.00", None)])
    assert len(sheet_checks.duplicates(make(bill, statement))) == 1


def test_a_later_paper_on_another_day_is_a_finding_of_its_own():
    bill = doc("S1", lines=[line(1, "A", "10.00", None), line(2, "A", "10.00", None)])
    statement = eob("S2", lines=[line(1, "A", "10.00", None, NEXT_DAY), line(2, "A", "10.00", None, NEXT_DAY)])
    found = sheet_checks.duplicates(make(bill, statement))
    assert [(f.title, f.math["service_date"]) for f in found] == [("Same service billed twice on sheet 1", "2025-08-04"),
                                                                  ("Same service billed twice on sheet 2", "2025-08-05")]


def test_an_undated_insurance_statement_joins_a_double_of_the_same_code_and_charge():
    bill = doc("S1", lines=[line(1, "a", "10.00", None), line(2, "a", "10.00", None)])
    statement = eob("S2", lines=[line(5, "A", "10.00", "3.00", None), line(6, "A", "10.00", "3.00", None)])
    (f,) = sheet_checks.duplicates(make(bill, statement))
    assert where(f)[2:] == [("S2", 5, "also twice here"), ("S2", 6, "")] and f.amount == Decimal("3.00")


def test_an_undated_insurance_statement_joins_the_last_double_of_that_code_and_charge():
    bill = doc("S1", lines=[line(1, "A", "10.00", None), line(2, "A", "10.00", None), line(3, "A", "10.00", None)])
    statement = eob("S2", lines=[line(5, "A", "10.00", None, None), line(6, "A", "10.00", None, None)])
    first, second = sheet_checks.duplicates(make(bill, statement))
    assert len(first.evidence) == 2 and len(second.evidence) == 4


def test_three_equal_lines_on_a_later_paper_join_twice_each_pair_against_its_first_line():
    bill = doc("S1", lines=[line(1, "A", "10.00", None), line(2, "A", "10.00", None)])
    statement = eob("S2", lines=[line(5, "A", "10.00", None), line(6, "A", "10.00", None), line(7, "A", "10.00", None)])
    (f,) = sheet_checks.duplicates(make(bill, statement))
    assert where(f)[2:] == [("S2", 5, "also twice here"), ("S2", 6, ""), ("S2", 5, "also twice here"), ("S2", 7, "")]


def test_an_undated_insurance_statement_with_another_charge_joins_nothing_and_says_nothing():
    bill = doc("S1", lines=[line(1, "A", "10.00", None), line(2, "A", "10.00", None)])
    statement = eob("S2", lines=[line(5, "A", "11.00", "3.00", None), line(6, "A", "11.00", "3.00", None)])
    (f,) = sheet_checks.duplicates(make(bill, statement))
    assert len(f.evidence) == 2


def test_an_undated_insurance_statement_alone_does_not_make_a_double():
    assert sheet_checks.duplicates(make(eob("S1", lines=[line(1, "A", "10.00", "3.00", None), line(2, "A", "10.00", "3.00", None)]))) == []


def test_a_line_on_an_insurance_statement_does_not_borrow_a_date():
    statement = eob("S1", lines=[line(1, "A", "10.00", None), line(2, "A", "10.00", None, None)])
    assert sheet_checks.duplicates(make(statement)) == []


def test_an_undated_pair_after_a_dated_double_on_the_same_insurance_statement_raises_type_error():
    statement = eob("S1", lines=[line(1, "A", "10.00", None), line(2, "A", "10.00", None),
                                 line(3, "A", "10.00", None, None), line(4, "A", "10.00", None, None)])
    with pytest.raises(TypeError):
        sheet_checks.duplicates(make(statement))


def test_a_line_on_any_other_paper_read_without_a_date_borrows_the_one_date_of_its_twin():
    bill = doc("S1", DocKind.OTHER, lines=[line(1, "j1", "10.00", None), line(2, "J1", "10.00", "7.00", None)])
    (f,) = sheet_checks.duplicates(make(bill))
    assert f.math["service_date"] == "2025-08-04" and f.amount == Decimal("7.00") and "on Aug 4, 2025" in f.detail
    assert bill.lines[1].service_date is None


def test_a_line_read_without_a_date_borrows_nothing_when_its_twins_have_two_dates():
    bill = doc("S1", lines=[line(1, "A", "10.00", None), line(2, "A", "10.00", None, NEXT_DAY), line(3, "A", "10.00", None, None)])
    assert sheet_checks.duplicates(make(bill)) == []


def test_two_lines_without_a_date_and_without_a_twin_are_passed_over_on_a_bill():
    assert sheet_checks.duplicates(make(doc("S1", lines=[line(1, "A", "10.00", None, None), line(2, "A", "10.00", None, None)]))) == []


def test_a_line_without_a_code_lends_no_date():
    bill = doc("S1", lines=[line(1, "", "10.00", None), line(2, "A", "10.00", None, None), line(3, "A", "10.00", None, None)])
    assert sheet_checks.duplicates(make(bill)) == []


# --- credits ----------------------------------------------------------------------------------

def test_a_balance_below_zero_gives_every_field_of_the_finding():
    found = sheet_checks.credits(make(doc("S1", patient_balance="-1040.00")))
    assert found == [Finding(
        kind=Kind.E3, title="You have a $1,040.00 credit on sheet 1",
        detail="The balance is in your favor. Ask for a refund instead of leaving it on the account.",
        amount=Decimal("1040.00"), evidence=[Evidence(doc_id="S1")],
        trace=[Step(doc_id="S1", field="patient_balance", printed=Decimal("-1040.00"), role="balance in your favor")],
        math={"patient_balance": "-1040.00"})]


def test_a_later_sum_on_the_same_account_turns_the_credit_into_a_check():
    credit = doc("S3", account_ref="[ACCT_1]", patient_balance="-40.00")
    asks = doc("S4", DocKind.OTHER, account_ref="[ACCT 1]", amount_due_coupon="1100.00")
    found = sheet_checks.credits(make(credit, asks))
    assert found == [Finding(
        kind=Kind.E3, severity="borderline", title="Check the $40.00 credit stays taken off",
        detail=("Sheet 3 shows a $40.00 credit. Sheet 4 of the same account asks $1,100.00, which looks to include it "
                "already. Check that it stays there; it is not counted as money back."),
        evidence=[Evidence(doc_id="S3"), Evidence(doc_id="S4")],
        trace=[Step(doc_id="S3", field="patient_balance", printed=Decimal("-40.00"), role="balance in your favor")],
        explain=INSIDE, math={"patient_balance": "-40.00", "applied_on": "S4"})]
    assert list(found[0].math) == ["patient_balance", "applied_on"]


def test_the_first_paper_of_the_account_that_asks_a_sum_is_named():
    credit = doc("S1", account_ref="A-1", patient_balance="-40.00")
    (f,) = sheet_checks.credits(make(doc("S9", account_ref="A1", amount_due_coupon="0.00"), doc("S8", account_ref="A1", amount_due_coupon="5.00"),
                                     credit, doc("S7", account_ref="A1", amount_due_coupon="6.00")))
    assert f.math["applied_on"] == "S8"


@pytest.mark.parametrize("other", [doc("S2", account_ref="B-7", amount_due_coupon="5.00"), doc("S2", account_ref="A-1", amount_due_coupon="0.00"),
                                   doc("S2", account_ref="A-1", amount_due_coupon="-5.00"), doc("S2", account_ref="A-1")])
def test_a_paper_that_asks_nothing_on_this_account_leaves_the_credit_as_money_back(other):
    (f,) = sheet_checks.credits(make(doc("S1", account_ref="A-1", patient_balance="-40.00"), other))
    assert f.amount == Decimal("40.00") and f.severity is None


def test_a_coupon_on_the_credit_sheet_itself_or_on_a_paper_without_an_account_changes_nothing():
    sheet = doc("S1", patient_balance="-40.00", amount_due_coupon="5.00")
    (f,) = sheet_checks.credits(make(sheet, doc("S2", amount_due_coupon="5.00")))
    assert f.amount == Decimal("40.00") and "applied_on" not in f.math


def test_a_coupon_on_the_credit_sheet_itself_does_not_count_even_with_an_account():
    (f,) = sheet_checks.credits(make(doc("S1", account_ref="A-1", patient_balance="-40.00", amount_due_coupon="5.00")))
    assert f.amount == Decimal("40.00") and "applied_on" not in f.math


def test_one_credit_per_account_and_the_newest_statement_speaks():
    old = doc("S1", account_ref="A-1", statement_date=date(2025, 8, 1), patient_balance="-10.00")
    new = doc("S2", DocKind.ITEMIZED_BILL, account_ref="A1", statement_date=date(2025, 9, 1), patient_balance="-20.00")
    assert [f.amount for f in sheet_checks.credits(make(old, new))] == [Decimal("20.00")]


def test_a_credit_with_no_account_is_counted_sheet_by_sheet_newest_first_and_undated_last():
    undated = doc("S1", patient_balance="-1.00")
    old = doc("S2", statement_date=date(2025, 8, 1), patient_balance="-2.00")
    new = doc("S3", statement_date=date(2025, 9, 1), patient_balance="-3.00")
    twin = doc("S4", statement_date=date(2025, 9, 1), patient_balance="-4.00")
    assert [f.evidence[0].doc_id for f in sheet_checks.credits(make(undated, old, new, twin))] == ["S3", "S4", "S2", "S1"]


def test_a_sheet_passed_over_for_its_account_loses_its_credit_lines_too():
    new = doc("S1", account_ref="A-1", statement_date=date(2025, 9, 1), patient_balance="-20.00")
    old = doc("S2", account_ref="A-1", statement_date=date(2025, 8, 1), patient_balance="-10.00", lines=[line(1, "A", "5.00", "-5.00")])
    assert len(sheet_checks.credits(make(new, old))) == 1


def test_a_balance_below_zero_says_nothing_of_its_own_credit_lines():
    (f,) = sheet_checks.credits(make(doc("S1", patient_balance="-40.00", lines=[line(1, "A", "5.00", "-5.00")])))
    assert f.math == {"patient_balance": "-40.00"}


def test_a_sheet_of_the_account_with_a_positive_balance_still_shows_its_credit_line():
    new = doc("S1", account_ref="A-1", statement_date=date(2025, 9, 1), patient_balance="-20.00")
    old = doc("S2", account_ref="A-1", statement_date=date(2025, 8, 1), patient_balance="10.00", lines=[line(1, "A", "5.00", "-5.00")])
    assert [f.title for f in sheet_checks.credits(make(new, old))] == ["You have a $20.00 credit on sheet 1", "$5.00 you overpaid is still on sheet 2"]


def test_a_credit_line_with_nothing_asked_gives_every_field_of_the_finding():
    found = sheet_checks.credits(make(doc("S1", patient_balance="0.00", lines=[line(2, "76801", "0.00", "-25.00", description="Copay overpaid")])))
    assert found == [Finding(
        kind=Kind.E3, severity="borderline", title="$25.00 you overpaid is still on sheet 1",
        detail=("Line 2 shows a credit of $25.00 (Copay overpaid). Ask the office to refund it or to show it taken off "
                "what you owe."),
        amount=Decimal("25.00"), evidence=[Evidence(doc_id="S1", line_no=2)],
        trace=[Step(doc_id="S1", line_no=2, field="patient_responsibility", printed=Decimal("-25.00"), role="a credit on the line")],
        math={"line_patient_responsibility": "-25.00", "why_unsure": "a credit line may already be inside the balance this sheet asks"})]
    assert list(found[0].math) == ["line_patient_responsibility", "why_unsure"]


def test_a_credit_line_without_words_has_no_brackets():
    (f,) = sheet_checks.credits(make(doc("S1", lines=[line(2, "A", "0.00", "-1234.50")])))
    assert f.detail == "Line 2 shows a credit of $1,234.50. Ask the office to refund it or to show it taken off what you owe."


def test_a_credit_line_on_a_sheet_that_asks_a_sum_is_a_check_with_no_sum():
    found = sheet_checks.credits(make(doc("S1", amount_due_coupon="410.00", lines=[line(2, "76801", "0.00", "-25.00")])))
    assert found == [Finding(
        kind=Kind.E3, severity="borderline", title="Check the $25.00 credit stays taken off",
        detail=("Line 2 of sheet 1 shows a $25.00 credit. Sheet 1 asks $410.00, which looks to include it already. "
                "Check that it stays there; it is not counted as money back."),
        evidence=[Evidence(doc_id="S1", line_no=2), Evidence(doc_id="S1")],
        trace=[Step(doc_id="S1", line_no=2, field="patient_responsibility", printed=Decimal("-25.00"), role="a credit on the line")],
        explain=INSIDE, math={"line_patient_responsibility": "-25.00", "applied_on": "S1"})]
    assert list(found[0].math) == ["line_patient_responsibility", "applied_on"]


def test_the_first_paper_of_the_pile_that_asks_a_sum_is_named_for_a_credit_line():
    other = doc("S5", DocKind.EOB, account_ref="A1", amount_due_coupon="7.00")
    sheet = doc("S6", account_ref="A-1", amount_due_coupon="9.00", lines=[line(1, "A", "0.00", "-2.00")])
    assert sheet_checks.credits(make(other, sheet))[0].math["applied_on"] == "S5"
    assert sheet_checks.credits(make(sheet, other))[0].math["applied_on"] == "S6"


def test_a_paper_with_no_account_says_nothing_about_a_credit_line_elsewhere():
    (f,) = sheet_checks.credits(make(doc("S1", lines=[line(1, "A", "0.00", "-2.00")]), doc("S2", amount_due_coupon="9.00")))
    assert f.amount == Decimal("2.00")


@pytest.mark.parametrize("words,counted", [
    ("Payment received", False), ("PAYMENT", False), ("Payments", False), ("- payment", False), ("Patient payment", False),
    ("Paid", False), ("paid in full", False), ("Thank you", False), ("We got the payment received today", False),
    ("Patient card payment", True), ("Overpayment refund", True), ("Copay overpaid", True), ("Prepaid", True), ("", True)])
def test_payment_lines_are_not_credits(words, counted):
    found = sheet_checks.credits(make(doc("S1", lines=[line(1, "A", "0.00", "-2.00", description=words)])))
    assert bool(found) is counted


def test_a_positive_or_zero_or_unread_share_is_not_a_credit():
    assert sheet_checks.credits(make(doc("S1", lines=[line(1, "A", "1.00", "1.00"), line(2, "B", "1.00", "0.00"), line(3, "C", "1.00", None)]))) == []


def test_a_credit_line_printed_on_two_statements_of_one_account_counts_once():
    a = doc("S1", account_ref="A-1", statement_date=date(2025, 9, 1), lines=[line(1, "A", "0.00", "-2.00")])
    b = doc("S2", account_ref="A1", statement_date=date(2025, 8, 1), lines=[line(7, "A", "9.00", "-2.00")])
    assert [where(f) for f in sheet_checks.credits(make(b, a))] == [[("S1", 1, "")]]


def test_the_same_credit_line_twice_on_one_sheet_counts_once():
    assert len(sheet_checks.credits(make(doc("S1", lines=[line(1, "A", "0.00", "-2.00"), line(2, "A", "0.00", "-2.00")])))) == 1


@pytest.mark.parametrize("second", [line(1, "B", "0.00", "-2.00"), line(1, "a", "0.00", "-2.00"), line(1, "A", "0.00", "-2.00", NEXT_DAY), line(1, "A", "0.00", "-3.00")])
def test_credit_lines_differ_by_code_as_printed_date_and_sum(second):
    assert len(sheet_checks.credits(make(doc("S1", lines=[line(1, "A", "0.00", "-2.00"), second])))) == 2


def test_credit_lines_of_sheets_without_an_account_are_each_counted():
    a, b = doc("S1", lines=[line(1, "A", "0.00", "-2.00")]), doc("S2", lines=[line(1, "A", "0.00", "-2.00")])
    assert len(sheet_checks.credits(make(a, b))) == 2


def test_a_reversal_on_a_bill_is_read_as_a_credit_line():
    assert sheet_checks.credits(make(doc("S1", lines=[line(1, "A", "-100.00", "-20.00")])))[0].amount == Decimal("20.00")


def test_the_lines_of_a_sheet_keep_their_order():
    found = sheet_checks.credits(make(doc("S1", lines=[line(5, "B", "0.00", "-2.00"), line(2, "A", "0.00", "-1.00")])))
    assert [e.line_no for f in found for e in f.evidence] == [5, 2]


# --- two_amounts ------------------------------------------------------------------------------

def test_two_amounts_gives_every_field_of_the_finding():
    found = sheet_checks.two_amounts(make(doc("S4", patient_balance="0.00", amount_due_coupon="1385.00")))
    assert found == [Finding(
        kind=Kind.E4, title="Sheet 4 asks two different amounts",
        detail="It says your balance is $0.00 and also asks you to pay $1,385.00. Do not pay until the office explains which one is right.",
        evidence=[Evidence(doc_id="S4")], math={"patient_balance": "0.00", "amount_due_coupon": "1385.00"})]
    assert list(found[0].math) == ["patient_balance", "amount_due_coupon"]


@pytest.mark.parametrize("balance,coupon,sentence", [
    ("1385.00", "0.00", "It says your balance is $1,385.00 and also asks you to pay $0.00."),
    ("0", "12.50", "It says your balance is $0.00 and also asks you to pay $12.50."),
    ("-40.00", "0.00", "It says your balance is $-40.00 and also asks you to pay $0.00."),
    ("0.00", "-40.00", "It says your balance is $0.00 and also asks you to pay $-40.00.")])
def test_one_zero_against_one_sum_is_the_error_in_either_direction(balance, coupon, sentence):
    (f,) = sheet_checks.two_amounts(make(doc("S1", patient_balance=balance, amount_due_coupon=coupon)))
    assert f.detail.startswith(sentence)
    assert f.math == {"patient_balance": balance, "amount_due_coupon": coupon}


@pytest.mark.parametrize("balance,coupon", [("10.00", "20.00"), ("20.00", "20.00"), ("0.00", "0"), ("-5.00", "5.00"), (None, "5.00"), ("0.00", None), (None, None)])
def test_two_sums_or_two_zeros_or_a_missing_one_are_no_error(balance, coupon):
    assert sheet_checks.two_amounts(make(doc("S1", patient_balance=balance, amount_due_coupon=coupon))) == []


@pytest.mark.parametrize("kind", list(DocKind))
def test_every_kind_of_paper_is_read_for_two_amounts(kind):
    assert len(sheet_checks.two_amounts(make(doc("S1", kind, patient_balance="0.00", amount_due_coupon="1.00")))) == 1


def test_two_amounts_keeps_the_order_of_the_pile():
    docs = [doc(i, patient_balance="0.00", amount_due_coupon="1.00") for i in ("S9", "S2", "D1")]
    assert [f.title for f in sheet_checks.two_amounts(make(*docs))] == [
        "Sheet 9 asks two different amounts", "Sheet 2 asks two different amounts", "Sheet 1 asks two different amounts"]


# --- baby_not_matched -------------------------------------------------------------------------

def baby_letter(doc_id="S8", kind=DocKind.OTHER, provider=OFFICE, statement_date=date(2025, 7, 6), balance="27.00", **kw) -> Document:
    return doc(doc_id, kind, patient="PATIENT_2", provider=provider, statement_date=statement_date, patient_balance=balance, **kw)


def test_an_old_letter_for_the_baby_gives_every_field_of_the_finding():
    found = sheet_checks.baby_not_matched(make(baby_letter(balance="1027.50")))
    assert found == [Finding(
        kind=Kind.B2, title=f"Send the baby's insurance details to {OFFICE}",
        detail=(f"Sheet 8 from {OFFICE}, dated Jul 6, 2025, asks $1,027.50 for the baby's care, and no insurance statement "
                "in your papers covers the baby. It is 253 days old, so send the baby's insurance details now."),
        evidence=[Evidence(doc_id="S8")],
        math={"patient_balance": "1027.50", "statement_date": "2025-07-06", "days_since": "253"})]
    assert list(found[0].math) == ["patient_balance", "statement_date", "days_since"]


@pytest.mark.parametrize("sent,days,ending", [
    (date(2026, 2, 13), "31", "It is 31 days old, so send the baby's insurance details now."),
    (date(2026, 2, 14), "30", "Send the baby's insurance details before it becomes yours to pay."),
    (TODAY, "0", "Send the baby's insurance details before it becomes yours to pay."),
    (date(2026, 3, 21), "-5", "Send the baby's insurance details before it becomes yours to pay.")])
def test_the_ending_changes_after_thirty_days(sent, days, ending):
    (f,) = sheet_checks.baby_not_matched(make(baby_letter(statement_date=sent)))
    assert f.detail.endswith("covers the baby. " + ending) and f.math["days_since"] == days


@pytest.mark.parametrize("kind", [DocKind.OTHER, DocKind.FA_LETTER, DocKind.PAYMENT_RECEIPT])
def test_any_other_paper_for_the_baby_counts_even_from_the_hospital(kind):
    assert len(sheet_checks.baby_not_matched(make(baby_letter(kind=kind, provider="Seaside Hospital"), letterhead="Seaside Hospital"))) == 1


@pytest.mark.parametrize("kind", [DocKind.EOB, DocKind.ITEMIZED_BILL])
def test_an_itemized_bill_or_an_insurance_statement_never_counts(kind):
    assert sheet_checks.baby_not_matched(make(baby_letter(kind=kind), letterhead="Seaside Hospital")) == []


def test_a_statement_counts_only_from_an_office_that_is_not_the_hospital():
    statement = baby_letter(kind=DocKind.HOSPITAL_STATEMENT)
    assert len(sheet_checks.baby_not_matched(make(statement, letterhead="Seaside Hospital"))) == 1
    assert sheet_checks.baby_not_matched(make(statement, letterhead="Little Harbor Hospital")) == []
    assert sheet_checks.baby_not_matched(make(statement)) == []  # no name on the sheets: everything is the hospital's


@pytest.mark.parametrize("change", [{"balance": "0.00"}, {"balance": "-5.00"}, {"balance": None}, {"statement_date": None}, {"provider": ""},
                                    {"due_from_insurance": "27.00"}])
def test_a_letter_that_asks_the_family_nothing_or_lacks_a_date_or_an_office_is_left_out(change):
    assert sheet_checks.baby_not_matched(make(baby_letter(**change))) == []


def test_a_balance_partly_due_from_insurance_is_still_said_whole():
    (f,) = sheet_checks.baby_not_matched(make(baby_letter(balance="27.00", due_from_insurance="10.00")))
    assert f.math["patient_balance"] == "27.00"


def test_any_insurance_statement_for_the_baby_stops_the_check_for_every_paper():
    statement = eob("S9", patient="PATIENT_2")
    assert sheet_checks.baby_not_matched(make(baby_letter(), statement)) == []
    assert len(sheet_checks.baby_not_matched(make(baby_letter(), eob("S9")))) == 1  # must differ: mom's statement covers nobody else


def test_only_the_babys_papers_count_and_the_order_of_the_pile_stays():
    moms = doc("S1", DocKind.OTHER, provider=OFFICE, statement_date=date(2025, 7, 6), patient_balance="5.00")
    found = sheet_checks.baby_not_matched(make(baby_letter("S9"), moms, baby_letter("S3")))
    assert [f.evidence[0].doc_id for f in found] == ["S9", "S3"]


# --- baby_under_mother ------------------------------------------------------------------------

END = "Ask the insurer and the provider to bill it under the baby, or add the baby to the plan, before the balance moves to you."


def mom_statement(**kw) -> Document:
    return eob("S1", member_ref="[MEMBER_1]", lines=[line(1, "99460", "1800.00", "1800.00", denial_codes="X17"),
                                                     line(2, "99462", "900.00", "900.00", denial_codes="X17"),
                                                     line(3, "59409", "5000.00", "300.00")], **kw)


def test_newborn_codes_under_mom_give_every_field_of_the_finding():
    found = sheet_checks.baby_under_mother(make(mom_statement()))
    assert found == [Finding(
        kind=Kind.B1, title="Baby's care is billed under mom's insurance",
        detail=f"Sheet 1 lists newborn care (99460, 99462) for mom (member [MEMBER_1]). 2 lines for $2,700.00 were denied (reason X17). {END}",
        evidence=[Evidence(doc_id="S1", line_no=1, note="X17"), Evidence(doc_id="S1", line_no=2, note="X17")],
        math={"codes": "99460, 99462", "denied_lines": "2", "denied_total": "2700.00"})]
    assert list(found[0].math) == ["codes", "denied_lines", "denied_total"]


def test_one_denied_line_is_said_in_the_singular_and_keeps_the_plural_verb():
    sheet = doc("S2", lines=[line(1, "0171", "120.00", None, denial_codes="A27")])
    (f,) = sheet_checks.baby_under_mother(make(sheet))
    assert f.detail == f"Sheet 2 lists newborn care (0171) for mom. 1 line for $120.00 were denied (reason A27). {END}"


def test_a_line_denied_with_the_same_reason_belongs_to_the_babys_stay_in_the_order_of_the_sheet():
    sheet = eob("S1", lines=[line(1, "0120", "300.00", None, denial_codes=" A27 "), line(2, "99460", "100.00", None, denial_codes="A27"),
                             line(3, "0250", "50.00", None, denial_codes="B1"), line(4, "0450", "9.00", None)])
    (f,) = sheet_checks.baby_under_mother(make(sheet))
    assert where(f) == [("S1", 1, " A27 "), ("S1", 2, "A27")]
    assert f.math == {"codes": "99460", "denied_lines": "2", "denied_total": "400.00"}


def test_a_newborn_line_the_plan_paid_nothing_on_counts_as_denied_with_no_reason():
    sheet = eob("S1", lines=[line(1, "99460", "100.00", None, insurance_paid=Decimal("0.00"))])
    (f,) = sheet_checks.baby_under_mother(make(sheet))
    assert f.detail == f"Sheet 1 lists newborn care (99460) for mom. 1 line for $100.00 were denied. {END}"
    assert where(f) == [("S1", 1, "")] and f.math["denied_total"] == "100.00"


@pytest.mark.parametrize("newborn", [line(1, "99460", "100.00", None, insurance_paid=Decimal("5.00")), line(1, "99460", "100.00", None),
                                     line(1, "99460", "0.00", None, insurance_paid=Decimal(0)), line(1, "99460", None, None, insurance_paid=Decimal(0))])
def test_a_newborn_line_paid_or_unread_or_free_is_listed_but_not_denied(newborn):
    (f,) = sheet_checks.baby_under_mother(make(eob("S1", lines=[newborn])))
    assert f.detail == f"Sheet 1 lists newborn care (99460) for mom. {END}"
    assert where(f) == [("S1", 1, "")]
    assert f.math == {"codes": "99460", "denied_lines": "0", "denied_total": "0"}


def test_the_reason_is_the_whole_printed_field_and_several_are_sorted():
    sheet = eob("S1", lines=[line(1, "99462", "1.00", None, denial_codes="X42"), line(2, "99460", "2.00", None, denial_codes="X05, X17")])
    (f,) = sheet_checks.baby_under_mother(make(sheet))
    assert "2 lines for $3.00 were denied (reason X05, X17, X42). " in f.detail


def test_a_reason_is_compared_without_the_spaces_around_it():
    sheet = eob("S1", lines=[line(1, "99460", "1.00", None, denial_codes=" A27 "), line(2, "0120", "2.00", None, denial_codes="A27")])
    (f,) = sheet_checks.baby_under_mother(make(sheet))
    assert "2 lines for $3.00 were denied (reason A27). " in f.detail and where(f) == [("S1", 1, " A27 "), ("S1", 2, "A27")]


def test_a_denied_line_with_no_charge_adds_nothing_to_the_sum():
    sheet = eob("S1", lines=[line(1, "99460", None, None, denial_codes="A"), line(2, "0120", "10.00", None, denial_codes="A")])
    (f,) = sheet_checks.baby_under_mother(make(sheet))
    assert f.math["denied_lines"] == "2" and f.math["denied_total"] == "10.00"


def test_denied_lines_all_without_a_charge_add_up_to_a_plain_zero():
    (f,) = sheet_checks.baby_under_mother(make(eob("S1", lines=[line(1, "99460", None, None, denial_codes="A")])))
    assert f.math == {"codes": "99460", "denied_lines": "1", "denied_total": "0"} and "1 line for $0.00 were denied" in f.detail


def test_codes_are_shown_as_printed_once_each_and_sorted():
    sheet = eob("S1", lines=[line(1, " 0171 ", "1.00", None), line(2, "99477", "1.00", None), line(3, "0171", "1.00", None), line(4, "99477", "1.00", None),
                             line(5, "171", "1.00", None), line(6, "99461", "1.00", None)])
    (f,) = sheet_checks.baby_under_mother(make(sheet))
    assert f.math["codes"] == " 0171 , 0171, 171, 99461, 99477"


@pytest.mark.parametrize("patient", ["PATIENT_2", "PATIENT_3", "PATIENT 1", "", "PATIENT_9"])
def test_only_a_sheet_of_the_mother_counts(patient):
    assert sheet_checks.baby_under_mother(make(eob("S1", patient=patient, lines=[line(1, "99460", "1.00", None)]))) == []


@pytest.mark.parametrize("kind", list(DocKind))
def test_a_sheet_of_any_kind_counts(kind):
    assert len(sheet_checks.baby_under_mother(make(doc("S1", kind, lines=[line(1, "99460", "1.00", None)])))) == 1


def test_a_sheet_of_the_mother_without_newborn_codes_is_left_out_and_each_sheet_gives_its_own_finding():
    sheets = [doc("S3", lines=[line(1, "99460", "1.00", None)]), doc("S4", lines=[line(1, "59409", "1.00", None)]), doc("S5", lines=[line(1, "0170", "1.00", None)])]
    assert [f.evidence[0].doc_id for f in sheet_checks.baby_under_mother(make(*sheets))] == ["S3", "S5"]


def baby_bill(doc_id="S2", balance="27.00", paid="-120.00", **kw) -> Document:
    return doc(doc_id, patient="PATIENT_2", patient_balance=balance, insurance_paid=paid, **kw)


def test_a_payment_on_the_babys_bill_with_no_statement_behind_it_is_said():
    (f,) = sheet_checks.baby_under_mother(make(mom_statement(), baby_bill()))
    assert f.detail.endswith(f"{END} The hospital already bills the baby's account (sheet 2) $27.00 and shows an insurance credit of "
                             "$120.00 that no insurance statement in your papers explains: ask for the statement behind it.")
    assert where(f)[-1] == ("S2", None, "baby's bill") and len(f.evidence) == 3
    assert f.math == {"codes": "99460, 99462", "denied_lines": "2", "denied_total": "2700.00", "baby_bill": "S2",
                      "baby_insurance_credit": "120.00", "baby_balance": "27.00"}
    assert list(f.math) == ["codes", "denied_lines", "denied_total", "baby_bill", "baby_insurance_credit", "baby_balance"]


def test_a_digital_bill_is_called_a_file():
    (f,) = sheet_checks.baby_under_mother(make(mom_statement(), baby_bill("D3")))
    assert "the baby's account (file 3) $27.00 and shows" in f.detail


def test_a_balance_all_due_from_insurance_is_said_as_that():
    (f,) = sheet_checks.baby_under_mother(make(mom_statement(), baby_bill(balance="1490.25", due_from_insurance="1490.25")))
    assert "the baby's account (sheet 2) $1,490.25 due from insurance and shows" in f.detail
    assert f.math["baby_balance"] == "1490.25" and f.math["baby_waiting"] == "yes"
    assert list(f.math)[-2:] == ["baby_balance", "baby_waiting"]


def test_a_zero_balance_with_a_sum_asked_from_insurance_is_waiting_too():
    (f,) = sheet_checks.baby_under_mother(make(mom_statement(), baby_bill(balance="0.00", due_from_insurance="500.00")))
    assert "$0.00 due from insurance and shows" in f.detail
    assert f.math["baby_balance"] == "0.00" and f.math["baby_waiting"] == "yes"


def test_a_balance_and_a_sum_from_insurance_both_zero_are_not_waiting_and_lose_the_cents_in_math():
    (f,) = sheet_checks.baby_under_mother(make(mom_statement(), baby_bill(balance="0.00", due_from_insurance="0.00")))
    assert "the baby's account (sheet 2) $0.00 and shows" in f.detail
    assert f.math["baby_balance"] == "0" and "baby_waiting" not in f.math


def test_a_balance_partly_from_insurance_is_said_as_a_plain_sum():
    (f,) = sheet_checks.baby_under_mother(make(mom_statement(), baby_bill(balance="100.00", due_from_insurance="40.00")))
    assert "the baby's account (sheet 2) $100.00 and shows" in f.detail
    assert f.math["baby_balance"] == "100.00" and "baby_waiting" not in f.math


def test_a_balance_not_read_leaves_the_sum_out():
    (f,) = sheet_checks.baby_under_mother(make(mom_statement(), baby_bill(balance=None)))
    assert "the baby's account (sheet 2) and shows an insurance credit of $120.00" in f.detail
    assert "baby_balance" not in f.math and "baby_waiting" not in f.math and f.math["baby_insurance_credit"] == "120.00"


@pytest.mark.parametrize("paid", ["0.00", "120.00", None])
def test_a_baby_bill_without_a_credit_from_insurance_is_not_named(paid):
    (f,) = sheet_checks.baby_under_mother(make(mom_statement(), baby_bill(paid=paid)))
    assert list(f.math) == ["codes", "denied_lines", "denied_total"] and "baby's account" not in f.detail


def test_only_a_bill_of_the_baby_is_named_and_the_first_in_the_pile():
    other = doc("S2", DocKind.OTHER, patient="PATIENT_2", insurance_paid="-1.00")
    moms = doc("S3", insurance_paid="-2.00")
    second = baby_bill("S4", paid="-3.00")
    third = baby_bill("S5", paid="-4.00")
    (f,) = sheet_checks.baby_under_mother(make(mom_statement(), other, moms, second, third))
    assert f.math["baby_bill"] == "S4" and f.math["baby_insurance_credit"] == "3.00"


def test_a_statement_for_the_baby_explains_the_credit():
    (f,) = sheet_checks.baby_under_mother(make(mom_statement(), baby_bill(), eob("S9", patient="PATIENT_2")))
    assert list(f.math) == ["codes", "denied_lines", "denied_total"] and "baby's account" not in f.detail and len(f.evidence) == 2


def test_a_mother_with_no_denied_lines_still_gets_the_babys_bill_named():
    (f,) = sheet_checks.baby_under_mother(make(eob("S1", lines=[line(1, "99460", "1.00", None)]), baby_bill()))
    assert where(f) == [("S1", 1, ""), ("S2", None, "baby's bill")]
    assert f.detail.startswith(f"Sheet 1 lists newborn care (99460) for mom. {END} The hospital already bills")


# --- missing_pages ----------------------------------------------------------------------------

def page(doc_id: str, no: int, count: int, kind: DocKind = DocKind.HOSPITAL_STATEMENT, provider: str = "", **kw) -> Document:
    return doc(doc_id, kind, page_no=no, page_count=count, provider=provider, **kw)


def test_one_missing_page_gives_every_field_of_the_finding():
    found = sheet_checks.missing_pages(make(page("S2", 1, 3, provider="Sample OB Group"), page("S3", 3, 3)))
    assert found == [Finding(
        kind=Kind.P1, title="Page 2 of 3 is missing",
        detail="This statement from Sample OB Group has 3 pages; we have 2. Totals may be on a missing page. Find or ask for pages 2.",
        evidence=[Evidence(doc_id="S2", note="page 1 of 3"), Evidence(doc_id="S3", note="page 3 of 3")],
        math={"page_count": "3", "missing": "2"})]
    assert list(found[0].math) == ["page_count", "missing"]


def test_several_missing_pages_are_listed_in_the_plural():
    (f,) = sheet_checks.missing_pages(make(page("S1", 3, 6)))
    assert f.title == "Pages 1, 2, 4, 5, 6 of 6 are missing"
    assert f.detail == "This statement has 6 pages; we have 1. Totals may be on a missing page. Find or ask for pages 1, 2, 4, 5, 6."
    assert f.math == {"page_count": "6", "missing": "1,2,4,5,6"}


def test_an_insurance_statement_is_named_and_its_printed_office_is_left_out():
    (f,) = sheet_checks.missing_pages(make(page("S1", 1, 2, DocKind.EOB, provider="Coastline Health Plan")))
    assert f.detail.startswith("This insurance statement has 2 pages; we have 1.")


def test_a_loose_sheet_among_insurance_pages_gives_the_office():
    found = sheet_checks.missing_pages(make(page("S1", 1, 3, DocKind.EOB, provider="Coastline"), page("S2", 2, 3, DocKind.OTHER, provider="Bay Office")))
    assert found[0].detail.startswith("This insurance statement from Bay Office has 3 pages; we have 2.")


def test_an_insurance_page_after_a_loose_sheet_still_makes_it_an_insurance_statement():
    (f,) = sheet_checks.missing_pages(make(page("S1", 1, 3, DocKind.OTHER, provider="Bay Office"), page("S2", 2, 3, DocKind.EOB, provider="Coastline")))
    assert f.detail.startswith("This insurance statement from Bay Office has 3 pages; we have 2.")


def test_the_first_sheet_that_names_an_office_gives_it():
    (f,) = sheet_checks.missing_pages(make(page("S1", 1, 4), page("S2", 2, 4, DocKind.ITEMIZED_BILL, provider="First"), page("S3", 3, 4, provider="Second")))
    assert f.detail.startswith("This statement from First has 4 pages; we have 3.")


def test_a_page_number_past_the_page_count_is_counted_as_had_but_not_as_expected():
    (f,) = sheet_checks.missing_pages(make(page("S1", 2, 3), page("S2", 5, 3)))
    assert f.math["missing"] == "1,3" and "we have 2." in f.detail
    assert [e.note for e in f.evidence] == ["page 2 of 3", "page 5 of 3"]


def test_every_page_there_says_nothing_and_a_digital_file_or_a_single_sheet_is_not_a_run():
    assert sheet_checks.missing_pages(make(page("S1", 1, 2), page("S2", 2, 2))) == []
    assert sheet_checks.missing_pages(make(page("D1", 1, 4, source=Source.PDF))) == []
    assert sheet_checks.missing_pages(make(page("S1", 1, 1), doc("S2"))) == []


def test_each_broken_statement_gives_its_own_finding_in_reading_order():
    found = sheet_checks.missing_pages(make(page("S10", 2, 2, provider="B"), page("S2", 1, 3, provider="A")))
    assert [f.title for f in found] == ["Pages 2, 3 of 3 are missing", "Page 1 of 2 is missing"]
    assert [f.evidence[0].doc_id for f in found] == ["S2", "S10"]


# --- all of them ------------------------------------------------------------------------------

def test_no_check_changes_the_papers_it_reads():
    papers = [doc("S1", patient_balance="-40.00", account_ref="A-1", lines=[line(1, "A", "10.00", None), line(2, "A", "10.00", "1.00", None)]),
              eob("S2", member_ref="[MEMBER_1]", lines=[line(1, "99460", "10.00", "1.00", denial_codes="A"), line(2, "99460", "10.00", "1.00", denial_codes="A")]),
              baby_bill("S3"), baby_letter("S4"), page("S5", 1, 2), doc("S6", patient_balance="0.00", amount_due_coupon="5.00", account_ref="A-1")]
    case = make(*papers, letterhead="Seaside Hospital")
    before = case.model_dump_json()
    found = (sheet_checks.duplicates(case) + sheet_checks.credits(case) + sheet_checks.two_amounts(case) + sheet_checks.baby_under_mother(case)
             + sheet_checks.baby_not_matched(case) + sheet_checks.missing_pages(case))
    assert case.model_dump_json() == before
    assert {f.kind for f in found} == {Kind.E2, Kind.E3, Kind.E4, Kind.B1, Kind.B2, Kind.P1}
