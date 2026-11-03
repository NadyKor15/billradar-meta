"""What the sealed run n1-n3 (03.11.2026) showed the checks and the covering missed. SYNTHETIC values; the n2 case is
the reading of a fictional pack, kept as it was read."""

from datetime import date
from decimal import Decimal
from functools import partial
from pathlib import Path
from types import SimpleNamespace

import pytest

from billradar import checks, ledger, redact, sheet_checks
from billradar.case import Case, Document, DocKind, Line, Profile, Source

N2 = Path(__file__).parent / "fixtures" / "sealed-cases" / "n2-case.json"
Doc = partial(Document, source=Source.PAPER)


def hospital(letterhead: str, provider: str) -> bool:
    return checks.is_hospital_bill(SimpleNamespace(letterhead=letterhead), SimpleNamespace(provider=provider))


def test_memorial_regional_is_the_hospital_of_its_own_policy():
    assert hospital("Memorial Regional Hospital", "Memorial Regional Hospital")
    assert hospital("Memorial Regional Hospital", "MEMORIAL HEALTHCARE SYSTEM")


def test_other_hospitals_and_doctors_stay_apart():
    assert not hospital("Memorial Regional Hospital", "Baptist Hospital of Miami")
    assert not hospital("Memorial Regional Hospital", "Seaside Regional Hospital")
    assert not hospital("Seaside Regional Hospital", "Memorial Regional Hospital")
    assert hospital("Seaside Regional Hospital", "Seaside Regional Hospital (IP) 300")
    assert not hospital("Memorial Regional Hospital", "Causeway Emergency Physicians")


def _line(no, code, charge, day=date(2026, 2, 17)):
    return Line(line_no=no, service_date=day, code=code, charges=Decimal(charge))


def _pages(insured: bool, second_account: str = "[ACCT_1]") -> Case:
    a = Doc(doc_id="S2", kind=DocKind.ITEMIZED_BILL, provider="Memorial Regional Hospital", account_ref="[ACCT_1]",
            lines=[_line(1, "99285", "3184.00"), _line(5, "71046", "486.00")])
    b = Doc(doc_id="S3", kind=DocKind.ITEMIZED_BILL, provider="Memorial Regional Hospital", account_ref=second_account,
            lines=[_line(1, "94640", "856.00", date(2026, 2, 18)), _line(9, "71046", "486.00")])
    return Case(case_id="t", letterhead="Memorial Regional Hospital", policy_id="memorial-2026-05", today=date(2026, 10, 20),
                profile=Profile(household_size=3, annual_income=61500, insured=insured), documents=[a, b])


def test_a_late_charge_posted_again_on_the_next_page_is_one_double():
    found = [f for f in sheet_checks.duplicates(_pages(insured=False)) if f.kind == checks.Kind.E2]
    assert len(found) == 1 and found[0].amount == Decimal("486.00")  # no insurance: the second charge is asked in full
    assert [(e.doc_id, e.line_no) for e in found[0].evidence] == [("S2", 5), ("S3", 9)]


def test_with_insurance_and_no_share_printed_the_page_double_has_no_sum():
    found = [f for f in sheet_checks.duplicates(_pages(insured=True)) if f.kind == checks.Kind.E2]
    assert len(found) == 1 and found[0].amount is None


def test_two_accounts_are_not_one_bill():
    assert not [f for f in sheet_checks.duplicates(_pages(insured=False, second_account="[ACCT_2]")) if f.kind == checks.Kind.E2]


def test_the_n2_reading_gives_the_double_and_the_assistance_once_with_the_right_sum():
    case = Case.model_validate_json(N2.read_text())
    report = checks.split_borderline(checks.run(case))
    got = sorted((f.kind.value, str(f.amount)) for f in report.findings)
    assert got == [("E2", "486.00"), ("F1", "10378.89")]  # 90% of the balance without the double, once for the account


@pytest.mark.parametrize("text, value", [
    ("03/20/2026 Payment by card ending 4471, thank you (520.00)", "4471"),
    ("06/02/26 REFUND OF OVERPAYMENT, check no. 20418 35.00", "20418"),
    ("We sent $10,496.00 to Memorial Regional Hospital on 05/27/2026 (EFT 00884127).", "00884127"),
    ("You work at Gulfline Freight Forwarding LLC and", "Gulfline Freight Forwarding LLC"),
    ("Mr. Nwosu works at Seawall Marine Supply Inc.", "Seawall Marine Supply Inc."),
    ("Group Gulfline Freight Forwarding LLC", "Gulfline Freight Forwarding LLC"),
    ("PRICE-NWOSU, ADAEZE 01/22/1990 Acct", "01/22/1990"),
    ("Patient DOB: 03/14/2026", "03/14/2026"),
])
def test_the_values_the_sealed_packs_left_open_are_closed(text, value):
    spans = redact._spans(text, redact.Vault())
    assert value in {text[a:b] for a, b, _ in spans}


@pytest.mark.parametrize("text", [
    "Date of service 02/17/2026 Statement date 07/08/2026 Pay by 08/05/2026",
    "04/09/26 0302 86900 BLOOD TYPING ABO 96.50",
    "Group Name: Harborlight Health Next",  # the plan's own name: no legal suffix, not an employer
    "Insurance paid -$1,574.58",
])
def test_dates_of_care_sums_and_the_plan_stay(text):
    spans = redact._spans(text, redact.Vault())
    kinds = {s.kind for _, _, s in spans}
    assert not kinds & {"DOB", "ACCT"}, kinds
    assert all("$" not in text[a:b] for a, b, s in spans if s.kind != "GROUP" or "Harborlight" not in text[a:b])


def test_the_sums_on_a_line_with_a_payment_number_stay():
    text = "We sent $10,496.00 to Memorial Regional Hospital on 05/27/2026 (EFT 00884127)."
    covered = {text[a:b] for a, b, _ in redact._spans(text, redact.Vault())}
    assert "$10,496.00" not in covered and "05/27/2026" not in covered


def test_income_on_a_letter_is_not_covered_yet():
    """Covering it made the leak check hold the whole letter (sealed run 03.11). Until a sum can be covered, it stays."""
    text = "household income for the year is $92,400.00."
    assert "$92,400.00" not in {text[a:b] for a, b, _ in redact._spans(text, redact.Vault())}


def test_the_tail_of_an_id_is_not_a_family_value():
    """"02" as a value of the family matches every date: the leak check held every sheet of n3 back (03.11)."""
    text = "above since birth. His ID ends in -02."
    assert "-02" not in {text[a:b] for a, b, _ in redact._spans(text, redact.Vault())}


def test_a_page_double_without_insurance_names_the_charge_not_a_share():
    f = next(f for f in sheet_checks.duplicates(_pages(insured=False)) if f.kind == checks.Kind.E2)
    assert f.math["second_patient_responsibility"] == "0" and f.math["second_charge_asked_in_full"] == "486.00"


N3 = Path(__file__).parent / "fixtures" / "sealed-cases" / "n3-case.json"


def _p1(report):
    return [f for f in report.findings if f.kind == checks.Kind.P1], [f for f in report.worth_asking if f.kind == checks.Kind.P1]


def test_a_page_is_not_called_missing_while_a_sheet_that_could_be_it_is_unread():
    """n3 has no error: page 2 of the itemized bill lay upside down (S7), page 1 of the insurance statement was read with
    doubts (S6). Sure: 3 false "page missing" (03.11). Now each goes to "worth checking" and names the sheet."""
    from billradar import pipeline
    case = Case.model_validate_json(N3.read_text())
    before = checks.run(case)
    assert len(_p1(before)[0]) == 3
    sure, ask = _p1(pipeline.pages_maybe_unread(case, before, []))
    assert sure == [] and len(ask) == 3 and all("may be the missing page" in f.math["why_unsure"] or "could not be read" in f.math["why_unsure"] for f in ask)


def test_a_sheet_kept_back_may_be_the_missing_page():
    from billradar import pipeline
    case = Case.model_validate_json(N3.read_text())
    for d in case.documents:
        d.unreadable, d.doubts = False, []
    report = checks.run(case)
    sure = _p1(report)[0]
    if not sure:
        return
    left, _ = _p1(pipeline.pages_maybe_unread(case, report.model_copy(deep=True), ["S99"]))
    assert left == []
    kept, _ = _p1(pipeline.pages_maybe_unread(case, report.model_copy(deep=True), []))
    assert len(kept) == len(sure)  # nothing unread, nothing kept back: the page stays missing


def test_an_unread_sheet_of_another_office_with_its_own_page_mark_leaves_the_missing_page_sure():
    from billradar import pipeline
    case = Case.model_validate_json(N3.read_text())
    for d in case.documents:
        d.unreadable, d.doubts = False, []
    report = checks.run(case)
    sure = _p1(report)[0]
    if not sure:
        return
    other = next(d for d in case.documents if d.provider and all(d.doc_id != e.doc_id for f in sure for e in f.evidence)
                 and d.kind not in (DocKind.EOB,) and d.provider not in {x.provider for f in sure for e in f.evidence for x in case.documents if x.doc_id == e.doc_id})
    other.doubts, other.page_no, other.page_count = ["read twice, two answers"], 1, 1
    left, _ = _p1(pipeline.pages_maybe_unread(case, report.model_copy(deep=True), []))
    assert len(left) == len(sure)
    # nothing known of it but a page number no statement is missing: it is not that page either
    other.provider, other.page_no, other.page_count = "", 9, None
    other.kind = next(x.kind for x in case.documents if x.doc_id == sure[0].evidence[0].doc_id)
    left, _ = _p1(pipeline.pages_maybe_unread(case, report.model_copy(deep=True), []))
    assert len(left) == len(sure)
    other.page_no = None  # no page mark read: it may be any page
    left, _ = _p1(pipeline.pages_maybe_unread(case, report.model_copy(deep=True), []))
    assert len(left) < len(sure)
