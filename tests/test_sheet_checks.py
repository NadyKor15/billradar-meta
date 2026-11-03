"""The five paper-only classes, each on a small SYNTHETIC case one case per pattern."""

from datetime import date
from decimal import Decimal

import pytest

from billradar import checks, sheet_checks
from billradar.case import Case, DocKind, Document, Line, Person, Profile, Role, Source
from billradar.checks import Kind
from billradar.policies import source

needs_text = pytest.mark.skipif(not all(source.is_cached(p) for p in source.SOURCES),
                                reason="run scripts/fetch_policies.py first")
D = date(2025, 8, 4)


def make(*docs: Document, policy_id: str = "memorial-2026-05", income: str = "85000") -> Case:
    people = [Person(token="PATIENT_1", role=Role.MOTHER), Person(token="PATIENT_2", role=Role.NEWBORN)]
    profile = Profile(household_size=4, annual_income=Decimal(income), liquid_assets=Decimal(6000), insured=True, people=people)
    return Case(case_id="t", policy_id=policy_id, today=date(2026, 10, 26), profile=profile, documents=list(docs))


def line(n, code, charges, resp, **kw) -> Line:
    """A line on day D; amounts are strings, a negative responsibility is a credit printed in brackets."""
    return Line(line_no=n, service_date=kw.pop("service_date", D), code=code, charges=Decimal(charges),
                patient_responsibility=None if resp is None else Decimal(resp), **kw)


def doc(doc_id, kind, patient="PATIENT_1", **kw) -> Document:
    return Document(doc_id=doc_id, source=Source.PAPER, kind=kind, patient=patient, **kw)


def kinds(findings):
    return [f.kind for f in findings]


def twin_lines():
    return [line(1, "01960", "2200.00", "550.00"), line(2, "01960", "2200.00", "550.00")]


def test_duplicate_anesthesia_line_counted_once_across_bill_and_eob():
    bill = doc("S1", DocKind.HOSPITAL_STATEMENT, provider="Sample Anesthesia Group", patient_balance=Decimal("1100"),
               lines=twin_lines())
    eob = doc("S2", DocKind.EOB, lines=twin_lines())
    found = sheet_checks.duplicates(make(bill, eob))
    assert kinds(found) == [Kind.E2]
    assert found[0].amount == Decimal("550.00")  # asked once for the second line, not on the bill and again on the EOB
    assert {e.doc_id for e in found[0].evidence} == {"S1", "S2"}


def test_same_code_on_different_days_is_not_a_duplicate():
    other_day = date(2025, 8, 5)
    visits = doc("S1", DocKind.HOSPITAL_STATEMENT, lines=[line(1, "99213", "300.00", "60.00"),
                                                           line(2, "99213", "300.00", "60.00", service_date=other_day)])
    assert sheet_checks.duplicates(make(visits)) == []
    same_day = doc("S1", DocKind.HOSPITAL_STATEMENT, lines=[line(1, "99213", "300.00", "60.00"), line(2, "99213", "300.00", "60.00")])
    assert kinds(sheet_checks.duplicates(make(same_day))) == [Kind.E2]  # must differ


def test_credit_in_parentheses_is_money_back():
    bill = doc("S1", DocKind.HOSPITAL_STATEMENT, provider="Sample OB Group", patient_balance=Decimal("410.00"),
               lines=[line(1, "59409", "4200.00", "435.00"),
                      line(2, "76801", "0.00", "-25.00", description="Copay overpaid")])
    found = sheet_checks.credits(make(bill))
    assert kinds(found) == [Kind.E3]
    assert found[0].amount == Decimal("25.00")
    assert "Copay overpaid" in found[0].detail


def test_negative_balance_is_a_credit():
    bill = doc("S1", DocKind.HOSPITAL_STATEMENT, patient_balance=Decimal("-40.00"))
    found = sheet_checks.credits(make(bill))
    assert kinds(found) == [Kind.E3]
    assert found[0].amount == Decimal("40.00")


def test_eob_negatives_are_reversals_not_credits():
    eob = doc("S1", DocKind.EOB, lines=[line(1, "0110", "-5000.00", "-500.00", denial_codes="X42")])
    assert sheet_checks.credits(make(eob)) == []


def test_zero_balance_but_pay_this_amount():
    bill = doc("S1", DocKind.HOSPITAL_STATEMENT, patient_balance=Decimal("0.00"), amount_due_coupon=Decimal("1385.00"))
    found = sheet_checks.two_amounts(make(bill))
    assert kinds(found) == [Kind.E4]
    assert "$0.00" in found[0].detail
    assert "$1,385.00" in found[0].detail
    assert found[0].amount is None  # no money is promised: the sheet only disagrees with itself


def test_newborn_codes_under_mothers_id():
    eob = doc("S1", DocKind.EOB, member_ref="[MEMBER_1]", lines=[
        line(1, "99460", "1800.00", "1800.00", denial_codes="X17"),
        line(2, "99462", "900.00", "900.00", denial_codes="X17"),
        line(3, "59409", "5000.00", "300.00"),
    ])
    found = sheet_checks.baby_under_mother(make(eob))
    assert kinds(found) == [Kind.B1]
    assert found[0].math["codes"] == "99460, 99462"
    assert found[0].math["denied_lines"] == "2"
    assert found[0].math["denied_total"] == "2700.00"  # the two denied newborn lines, not the delivery
    assert "[MEMBER_1]" in found[0].detail


def test_newborn_codes_under_babys_id_are_fine():
    eob = doc("S1", DocKind.EOB, patient="PATIENT_2", lines=[line(1, "0170", "1200.00", "0.00")])
    assert sheet_checks.baby_under_mother(make(eob)) == []


def test_missing_pages_of_one_statement():
    pages = [doc(doc_id, DocKind.EOB, provider="Sample Health Plan", claim_ref="CL-9", page_no=page, page_count=5)
             for doc_id, page in (("S1", 2), ("S2", 3), ("S3", 5))]
    found = sheet_checks.missing_pages(make(*pages))
    assert kinds(found) == [Kind.P1]
    assert found[0].math["missing"] == "1,4"
    assert found[0].title == "Pages 1, 4 of 5 are missing"


@needs_text
def test_duplicate_extra_is_not_discounted_again():
    bill = doc("S1", DocKind.HOSPITAL_STATEMENT, patient_balance=Decimal("1100.00"), statement_date=date(2025, 8, 11),
               service_from=D, service_to=D, lines=twin_lines())
    r = checks.run(make(bill))  # 257.6% of the guideline: the 85% tier
    (e2,) = [f for f in r.findings if f.kind == Kind.E2]
    assert e2.amount == Decimal("550.00")
    (f1,) = [f for f in r.findings if f.kind == Kind.F1 and "fpl_pct" in f.math]
    assert f1.amount == Decimal("467.50")  # 85% of 1100 - 550
    assert r.total_may_come_off == Decimal("1017.50")


@needs_text
def test_statement_and_itemized_bill_of_one_account_count_once():
    # Shaped like the first look-alike pack: hospital statement and itemized bill, same account, no assistance.
    stmt = Document(doc_id="D1", source=Source.PDF, kind=DocKind.HOSPITAL_STATEMENT, patient="PATIENT_1",
                    account_ref="[ACCT_1]", patient_balance=Decimal("5040.00"), statement_date=date(2025, 9, 12),
                    service_from=date(2025, 8, 4), service_to=date(2025, 8, 6))
    itemized = stmt.model_copy(update={"doc_id": "D2", "kind": DocKind.ITEMIZED_BILL, "statement_date": date(2025, 8, 20)})
    r = checks.run(make(stmt, itemized, income="57500").model_copy(
        update={"profile": make(stmt, income="57500").profile.model_copy(update={"household_size": 3})}))
    f1 = [f for f in r.findings if f.kind == Kind.F1]
    assert len(f1) == 1 and f1[0].evidence[0].doc_id == "D1"
    assert f1[0].amount == Decimal("4536.00")  # 90% at 210.5% of the guideline for 3, counted once


def test_a_twin_line_read_without_a_date_still_makes_a_double():
    """S10 prints 01960 $4,944.00 twice; a reading that dates one line and not the other must not lose the double."""
    from datetime import date
    from decimal import Decimal
    from billradar.case import Case, Document, DocKind, Line, Source
    from billradar.sheet_checks import duplicates
    from billradar import example
    import json
    meta = json.loads((example.PACK / "profile.json").read_text())
    from billradar.case import Profile
    def case(second_charge):
        lines = [Line(line_no=1, code="01960", service_date=date(2025, 2, 11), charges=Decimal("4944.00")),
                 Line(line_no=2, code="01960", charges=Decimal(second_charge))]
        doc = Document(doc_id="S10", source=Source.PAPER, kind=DocKind.ITEMIZED_BILL, lines=lines)
        return Case(case_id="t", policy_id=meta["policy_id"], today=date(2026, 3, 16),
                    profile=Profile.model_validate(meta["profile"]), documents=[doc])
    found = duplicates(case("4944.00"))
    assert [f.kind.value for f in found] == ["E2"] and found[0].math["service_date"] == "2025-02-11"
    assert duplicates(case("4945.00")) == []  # must differ: another charge is another line


# --- pages of one statement with other sheets between them, as a video of the table gives them ---

def _page(doc_id, no, count, kind=DocKind.HOSPITAL_STATEMENT, provider="Meridian Physician Services", stmt=None, acct=""):
    return Document(doc_id=doc_id, source=Source.PAPER, kind=kind, page_no=no, page_count=count, provider=provider, statement_date=stmt, account_ref=acct)


def _case(*docs) -> Case:
    return Case(case_id="t", policy_id="memorial-2026-05", today=date(2026, 3, 2), profile=Profile(household_size=2, annual_income=Decimal(1)), documents=list(docs))


def test_a_bills_pages_with_other_sheets_between_them_are_one_bill():
    other = _page("S6", 1, 1, DocKind.EOB, "Harborlight")
    case = _case(_page("S5", 1, 3), other, _page("S7", 2, 3, DocKind.ITEMIZED_BILL), _page("S10", 3, 3))
    assert sheet_checks.missing_pages(case) == []


def test_an_insurance_statements_pages_apart_are_tied_by_their_date():
    d = date(2025, 1, 8)
    case = _case(_page("S6", 1, 2, DocKind.EOB, "COASTLINE", d), _page("S8", 1, 1), _page("S11", 2, 2, DocKind.EOB, "", d))
    assert sheet_checks.missing_pages(case) == []


def test_two_statements_of_other_dates_stay_apart():  # must differ
    case = _case(_page("S1", 1, 2, DocKind.EOB, "A", date(2025, 1, 8)), _page("S2", 1, 1), _page("S3", 2, 2, DocKind.EOB, "B", date(2025, 3, 8)))
    assert [f.title for f in sheet_checks.missing_pages(case)] == ["Page 2 of 2 is missing", "Page 1 of 2 is missing"]


def test_a_doctor_on_an_insurance_statement_ties_nothing():  # must differ
    case = _case(_page("S1", 1, 2, DocKind.EOB, "SAME DOCTOR"), _page("S2", 1, 1), _page("S3", 2, 2, DocKind.EOB, "SAME DOCTOR"))
    assert len(sheet_checks.missing_pages(case)) == 2


def test_a_page_really_missing_is_still_said():  # must differ
    case = _case(_page("S5", 1, 3), _page("S6", 1, 1, DocKind.EOB, "X"), _page("S10", 3, 3))
    assert [f.title for f in sheet_checks.missing_pages(case)] == ["Page 2 of 3 is missing"]
