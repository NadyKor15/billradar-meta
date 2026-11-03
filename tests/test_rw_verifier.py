"""Current behaviour of billradar/verifier.py, past what test_verifier, test_prices and test_money_ceiling pin.

Every case here is made up. The policies and their quotes are the real files, read only. Nothing goes to a model: the
review tests use an in-memory client. Issues are compared whole and in order: the order is what the screen shows.
"""

import decimal
import json
from datetime import date, datetime, timezone
from decimal import ROUND_DOWN, Decimal
from pathlib import Path

import pytest

from billradar import checks, fpl, meta_client, policy, prices, verifier, writer
from billradar.case import Case, DocKind, Document, Line, LocalDetails, Person, Plan, Profile, Role, Source
from billradar.checks import Evidence, Finding, Kind, Report
from billradar.ledger import Step
from billradar.meta_client import MetaAPIError
from billradar.verifier import Issue, Verdict
from billradar.writer import Letter, Paragraph

FIXTURE = Path(__file__).parent / "fixtures" / "cases" / "anna-birth.json"
MEMORIAL = "memorial-2026-05"
BAPTIST = "baptist-2026-09"
TODAY = date(2026, 6, 15)
RECOMPUTE = "amount could not be recomputed independently"


def money(text):
    return None if text is None else Decimal(text)


def text(value):
    assert isinstance(value, Decimal)
    return str(value)


def row(no=1, **fields):
    return Line(line_no=no, **fields)


def paper(doc_id, *lines, kind=DocKind.HOSPITAL_STATEMENT, **fields):
    return Document(doc_id=doc_id, source=Source.PAPER, kind=kind, lines=list(lines), **fields)


def eob(doc_id, *lines, **fields):
    return paper(doc_id, *lines, kind=DocKind.EOB, **fields)


def family(*papers, income="50000", size=4, policy_id=MEMORIAL, today=TODAY, letterhead="", plan=None):
    profile = Profile(household_size=size, annual_income=Decimal(income), plan=plan)
    return Case(case_id="t", policy_id=policy_id, today=today, letterhead=letterhead, profile=profile,
                documents=list(papers))


def anna():
    return Case.model_validate(json.loads(FIXTURE.read_text()))


def private_anna():
    c = anna()
    c.profile.people = [Person(token="PATIENT_1", role=Role.MOTHER, name="Anna Sample", birth_date="03/14/1994",
                               relationship="Self", employer="Sample Bakery LLC"),
                        Person(token="PATIENT_2", role=Role.NEWBORN, name="Baby Sample", birth_date="08/04/2025",
                               relationship="Daughter")]
    c.profile.local = LocalDetails(street="100 Example Street", city="Hollywood", state="FL", zip="33021",
                                   phone="(555) 010-0000", checking=Decimal("2400"),
                                   tokens={"ACCT_1": "LDH-000123", "ACCT_2": "LDH-000124"})
    return c


def at(doc_id, line_no=None, note=""):
    return Evidence(doc_id=doc_id, line_no=line_no, note=note)


def finding(kind, *evidence, amount=None, deadline=None, math=None, trace=None, refs=()):
    return Finding(kind=kind, title=f"{kind.value} title", detail=f"{kind.value} detail", amount=money(amount),
                   deadline=deadline, evidence=list(evidence), math=math or {}, trace=trace or [],
                   policy_refs=list(refs))


def printed(doc_id, line_no, field, value):
    return Step(doc_id=doc_id, line_no=line_no, field=field, printed=Decimal(value))


def report(*findings, total=None):
    if total is None:
        total = sum((f.amount for f in findings if f.amount is not None), Decimal(0))
    return Report(case_id="t", policy_id=MEMORIAL, fpl_pct=Decimal("151.5"), findings=list(findings), no_money=[],
                  held_back=[], total_may_come_off=Decimal(total), apply_by=None)


def issues(verdict):
    return [(i.subject, i.severity, i.what) for i in verdict.issues]


def check(case, *findings, total=None):
    return issues(verifier.check_findings(case, report(*findings, total=total)))


def letter(*paragraphs, kind="dispute", dropped=()):
    return Letter(kind=kind, button="b", to="t", subject="s", paragraphs=list(paragraphs), dropped=list(dropped))


def said(*paragraphs, case=None, rep=None, **fields):
    case = case or family()
    rep = rep or report()
    return issues(verifier.check_letters(case, rep, [letter(*paragraphs, **fields)]))


def windowed(monkeypatch, window, fpg_year=2026, tiers=()):
    """A made-up policy with this application window, in place of whatever the case names."""
    made_up = policy.Policy("made-up", "Hospital", "Policy", "https://example.org/p.pdf", {}, fpg_year=fpg_year,
                            tiers=list(tiers), window=window)
    monkeypatch.setattr(policy, "load", lambda policy_id: made_up)
    return made_up


# --- Verdict.errors_for --------------------------------------------------------------------------

def test_errors_for_keeps_only_the_errors_of_that_exact_subject_in_their_order():
    first, second = Issue("F1 #1", "error", "first"), Issue("F1 #1", "error", "second")
    v = Verdict(issues=[first, Issue("F1 #1", "doubt", "d"), Issue("F1 #1", "note", "n"), Issue("F1 #2", "error", "x"),
                        Issue("F1 #1 on D1", "error", "longer name"), second])
    assert v.errors_for("F1 #1") == [first, second]


def test_errors_for_a_subject_without_errors_is_an_empty_list():
    assert Verdict(issues=[Issue("F1 #1", "doubt", "d")]).errors_for("F1 #1") == []
    assert Verdict().errors_for("") == []


# --- _q ------------------------------------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    ("1.005", "1.01"), ("-1.005", "-1.01"), ("2.675", "2.68"), ("0.125", "0.13"), ("0.135", "0.14"), ("0.004", "0.00"),
    ("0.005", "0.01"), ("-0.004", "-0.00"), ("1", "1.00"), ("1E+3", "1000.00"), ("999999.995", "1000000.00"),
    ("0", "0.00"), ("-0", "-0.00"), ("46.8560", "46.86"),
])
def test_q_rounds_half_a_cent_away_from_zero_and_always_prints_two_places(value, expected):
    assert text(verifier._q(Decimal(value))) == expected


def test_q_does_not_follow_the_rounding_of_the_decimal_context():
    with decimal.localcontext(rounding=ROUND_DOWN):
        assert text(verifier._q(Decimal("0.125"))) == "0.13"


@pytest.mark.parametrize("value", [Decimal("Infinity"), Decimal("1E+30")])
def test_q_refuses_a_value_with_no_cents_form(value):
    with pytest.raises(decimal.InvalidOperation):
        verifier._q(value)


@pytest.mark.parametrize("value", [1, 1.5, None, "1.00"])
def test_q_takes_only_a_decimal(value):
    with pytest.raises(AttributeError):
        verifier._q(value)


# --- _add_months ---------------------------------------------------------------------------------

@pytest.mark.parametrize("start,months,expected", [
    (date(2025, 9, 2), 12, date(2026, 9, 2)), (date(2025, 1, 31), 1, date(2025, 2, 28)),
    (date(2024, 1, 31), 1, date(2024, 2, 29)), (date(2023, 12, 31), 2, date(2024, 2, 29)),
    (date(2024, 2, 29), 12, date(2025, 2, 28)), (date(2024, 2, 29), 48, date(2028, 2, 29)),
    (date(2025, 3, 31), -1, date(2025, 2, 28)), (date(2025, 1, 15), -1, date(2024, 12, 15)),
    (date(2025, 1, 15), -13, date(2023, 12, 15)), (date(2025, 8, 31), 1, date(2025, 9, 30)),
    (date(2025, 12, 31), 1, date(2026, 1, 31)), (date(2025, 6, 30), 0, date(2025, 6, 30)),
    (date(1900, 1, 31), 1, date(1900, 2, 28)), (date(2000, 1, 31), 1, date(2000, 2, 29)),
    (date(2100, 1, 31), 1, date(2100, 2, 28)), (date(9999, 11, 30), 1, date(9999, 12, 30)),
    (date(1, 2, 1), -1, date(1, 1, 1)),
])
def test_add_months_keeps_the_day_or_takes_the_last_day_of_a_shorter_month(start, months, expected):
    assert verifier._add_months(start, months) == expected


def test_add_months_gives_back_what_it_was_given_with_its_time():
    moment = datetime(2025, 1, 31, 8, 30, tzinfo=timezone.utc)
    assert verifier._add_months(moment, 1) == datetime(2025, 2, 28, 8, 30, tzinfo=timezone.utc)
    assert type(verifier._add_months(date(2025, 1, 31), 1)) is date


@pytest.mark.parametrize("start,months", [(date(9999, 12, 31), 1), (date(1, 1, 1), -1)])
def test_add_months_past_the_calendar_is_a_value_error(start, months):
    with pytest.raises(ValueError):
        verifier._add_months(start, months)


@pytest.mark.parametrize("start,months,error", [(date(2025, 1, 1), 1.0, TypeError), (None, 1, AttributeError)])
def test_add_months_takes_a_date_and_a_whole_number(start, months, error):
    with pytest.raises(error):
        verifier._add_months(start, months)


# --- _line ---------------------------------------------------------------------------------------

def test_line_finds_the_paper_and_its_line():
    wanted = row(2, code="B")
    c = family(paper("S1", row(1, code="A"), wanted))
    doc, line = verifier._line(c, "S1", 2)
    assert doc is c.documents[0] and line is c.documents[0].lines[1] and line.code == "B"


def test_line_of_a_paper_not_in_the_case_is_nothing_at_all():
    assert verifier._line(family(paper("S1")), "S9", 1) == (None, None)
    assert verifier._line(family(paper("S1")), "S9", None) == (None, None)


def test_line_without_a_number_means_the_paper_itself():
    c = family(paper("S1", row(1)))
    doc, line = verifier._line(c, "S1", None)
    assert doc is c.documents[0] and line is None


def test_line_that_is_not_on_the_paper_keeps_the_paper():
    c = family(paper("S1", row(1)))
    doc, line = verifier._line(c, "S1", 7)
    assert doc is c.documents[0] and line is None


def test_line_zero_is_a_number_and_a_repeated_number_gives_the_first_line():
    c = family(paper("S1", row(0, code="zero"), row(4, code="first"), row(4, code="second")))
    assert verifier._line(c, "S1", 0)[1].code == "zero"
    assert verifier._line(c, "S1", 4)[1].code == "first"


def test_line_with_a_repeated_paper_id_reads_the_first_paper():
    c = family(paper("S1", row(1, code="first")), paper("S1", row(1, code="second")))
    assert verifier._line(c, "S1", 1)[1].code == "first"


# --- _expect_e1 ----------------------------------------------------------------------------------

def e1_case(bill_share="2887.50", eob_share="2575.10", **bill):
    return family(paper("S1", row(2, patient_responsibility=money(bill_share)), **bill),
                  eob("S4", row(2, patient_responsibility=money(eob_share))))


E1_LINES = (at("S1", 2), at("S4", 2))


@pytest.mark.parametrize("bill,expected", [
    ({}, "312.40"),
    ({"fa_discount": Decimal("0"), "patient_balance": Decimal("676.80")}, "312.40"),
    ({"fa_discount": Decimal("-3835.20")}, "312.40"),
    ({"fa_discount": Decimal("-3835.20"), "patient_balance": Decimal("676.80")}, "46.86"),
    ({"fa_discount": Decimal("3835.20"), "patient_balance": Decimal("676.80")}, "46.86"),
    ({"fa_discount": Decimal("-100.00"), "patient_balance": Decimal("0.00")}, "0.00"),
])
def test_expect_e1_counts_the_difference_and_only_the_share_left_after_a_discount(bill, expected):
    assert text(verifier._expect_e1(e1_case(**bill), finding(Kind.E1, *E1_LINES))) == expected


@pytest.mark.parametrize("balance,discount,difference,expected", [
    ("1", "-27", "0.14", "0.00"), ("1", "-37", "0.19", "0.00"), ("3", "-25", "0.14", "0.01"), ("3", "-25", "0.42", "0.04"),
    ("3", "-25", "0.70", "0.07"), ("1", "-1", "0.01", "0.01"),
])
def test_expect_e1_takes_the_share_first_so_an_inexact_share_decides_half_a_cent(balance, discount, difference, expected):
    c = e1_case(difference, "0.00", fa_discount=Decimal(discount), patient_balance=Decimal(balance))
    assert text(verifier._expect_e1(c, finding(Kind.E1, *E1_LINES))) == expected


def test_expect_e1_adds_up_every_insurance_line():
    c = family(paper("S1", row(1, patient_responsibility=Decimal("300.00"))),
               eob("S4", row(1, patient_responsibility=Decimal("100.10"))),
               eob("S5", row(1, patient_responsibility=Decimal("50.20"))))
    assert text(verifier._expect_e1(c, finding(Kind.E1, at("S1", 1), at("S4", 1), at("S5", 1)))) == "149.70"


def test_expect_e1_can_be_negative_and_keeps_its_sign():
    assert text(verifier._expect_e1(e1_case("10.00", "12.50"), finding(Kind.E1, *E1_LINES))) == "-2.50"


def test_expect_e1_rounds_half_a_cent_up_only_after_the_share():
    c = e1_case("10.01", "10.00", fa_discount=Decimal("-100.00"), patient_balance=Decimal("100.00"))
    assert text(verifier._expect_e1(c, finding(Kind.E1, *E1_LINES))) == "0.01"


@pytest.mark.parametrize("evidence", [
    (at("S9", 2), at("S4", 2)), (at("S1", 7), at("S4", 2)), (at("S1"), at("S4", 2)), (at("S1", 2),),
    (at("S1", 2), at("S9", 2)), (at("S1", 2), at("S4", 7)), (at("S1", 2), at("S4")),
    (at("S1", 2), at("S4", 2), at("S4", 7)),
])
def test_expect_e1_has_no_answer_when_a_line_is_missing(evidence):
    assert verifier._expect_e1(e1_case(), finding(Kind.E1, *evidence)) is None


@pytest.mark.parametrize("bill_share,eob_share", [(None, "1.00"), ("1.00", None)])
def test_expect_e1_has_no_answer_when_a_line_prints_no_share(bill_share, eob_share):
    assert verifier._expect_e1(e1_case(bill_share, eob_share), finding(Kind.E1, *E1_LINES)) is None


def test_expect_e1_needs_at_least_one_evidence_line():
    with pytest.raises(IndexError):
        verifier._expect_e1(e1_case(), finding(Kind.E1))


def test_expect_e1_a_balance_that_cancels_the_discount_divides_by_zero():
    c = e1_case(fa_discount=Decimal("-10.00"), patient_balance=Decimal("-10.00"))
    with pytest.raises(decimal.DivisionByZero):
        verifier._expect_e1(c, finding(Kind.E1, *E1_LINES))


# --- _tier_pct -----------------------------------------------------------------------------------

@pytest.mark.parametrize("income,size,expected", [
    ("0", 4, "100"), ("33000", 4, "100"), ("66000", 4, "100"), ("66310.20", 4, "100"), ("66316.80", 4, "90"),
    ("82500", 4, "90"), ("85000", 4, "85"), ("99000", 4, "85"), ("115500", 4, "83"), ("132000", 4, "83"),
    ("132313", 4, "83"), ("61400", 9, "100"), ("15960", 1, "100"),
])
def test_tier_pct_reads_the_policy_table_at_the_income_rounded_to_a_tenth_then_cut_to_a_whole_percent(income, size, expected):
    assert text(verifier._tier_pct(family(income=income, size=size))) == expected


@pytest.mark.parametrize("income,size", [("132314", 4), ("132330", 4), ("1000000", 1)])
def test_tier_pct_above_the_last_tier_is_nothing(income, size):
    assert verifier._tier_pct(family(income=income, size=size)) is None


def test_tier_pct_reads_the_table_of_the_policy_the_case_names():
    tiers = policy.load(BAPTIST).tiers
    assert text(verifier._tier_pct(family(income="1", policy_id=BAPTIST))) == str(tiers[0].discount_pct)


def test_tier_pct_of_a_policy_without_a_table_is_nothing():
    assert verifier._tier_pct(family(policy_id="fl-395-301")) is None


def test_tier_pct_takes_the_first_tier_that_fits_even_out_of_order(monkeypatch):
    windowed(monkeypatch, {}, tiers=[policy.Tier(300, 20, "a"), policy.Tier(100, 90, "b")])
    assert text(verifier._tier_pct(family(income="33000"))) == "20"


def test_tier_pct_uses_the_policy_guideline_year_and_else_the_latest(monkeypatch):
    monkeypatch.setitem(fpl.GUIDELINES, 2030, {"base": [1000] * 8, "each_extra": 1})
    tiers = [policy.Tier(200, 50, "a"), policy.Tier(100000, 10, "b")]
    windowed(monkeypatch, {}, fpg_year=2026, tiers=tiers)
    assert text(verifier._tier_pct(family(income="33000"))) == "50"
    windowed(monkeypatch, {}, fpg_year=None, tiers=tiers)  # must differ: the latest year is 2030 here
    assert text(verifier._tier_pct(family(income="33000"))) == "10"


def test_tier_pct_of_an_unknown_policy_or_an_empty_household_is_an_error():
    with pytest.raises(FileNotFoundError):
        verifier._tier_pct(family(policy_id="no-such-policy"))
    c = family()
    c.profile.household_size = 0
    with pytest.raises(ValueError):
        verifier._tier_pct(c)


# --- _expect_deadline ----------------------------------------------------------------------------

def owed(doc_id, statement=None, start=None, end=None, balance="100.00", **fields):
    return paper(doc_id, statement_date=statement, service_from=start, service_to=end, patient_balance=money(balance),
                 **fields)


def test_expect_deadline_of_the_demo_case_is_a_year_after_the_last_insurance_payment():
    assert verifier._expect_deadline(anna()) == date(2026, 9, 2)


def test_expect_deadline_without_bills_or_without_a_debt_is_nothing():
    assert verifier._expect_deadline(family()) is None
    assert verifier._expect_deadline(family(owed("S1", date(2025, 1, 1), balance="0.00"))) is None
    assert verifier._expect_deadline(family(owed("S1", date(2025, 1, 1), balance=None))) is None
    assert verifier._expect_deadline(family(eob("S4", statement_date=date(2025, 1, 1)))) is None


def test_expect_deadline_needs_a_statement_date_on_a_paper_of_the_stay():
    assert verifier._expect_deadline(family(owed("S1", None, date(2025, 1, 1)))) is None


def test_expect_deadline_balance_owed_by_the_insurer_is_not_a_debt_of_the_family():
    bill = owed("S1", date(2025, 2, 1), date(2025, 1, 1), due_from_insurance=Decimal("100.00"))
    assert verifier._expect_deadline(family(bill, policy_id=BAPTIST)) is None


def test_expect_deadline_counts_240_days_from_the_first_statement_when_the_policy_says_no_more():
    c = family(owed("S1", date(2025, 3, 10), date(2025, 1, 1)), owed("S2", date(2025, 2, 1), date(2025, 1, 2)),
               policy_id=BAPTIST)
    assert verifier._expect_deadline(c) == date(2025, 9, 29)


def test_expect_deadline_starts_from_the_first_bill_after_discharge_when_one_is_marked():
    c = family(owed("S1", date(2025, 1, 5), date(2025, 1, 1)),
               owed("S2", date(2025, 3, 1), date(2025, 1, 2), first_after_discharge=True),
               owed("S3", date(2025, 2, 1), date(2025, 1, 3), first_after_discharge=True), policy_id=BAPTIST)
    assert verifier._expect_deadline(c) == date(2025, 9, 29)  # 240 days from 2025-02-01


def test_expect_deadline_a_marked_bill_without_a_date_does_not_take_over():
    c = family(owed("S1", date(2025, 1, 5), date(2025, 1, 1)),
               owed("S2", None, date(2025, 1, 2), first_after_discharge=True), policy_id=BAPTIST)
    assert verifier._expect_deadline(c) == date(2025, 9, 2)


def test_expect_deadline_takes_the_latest_of_what_the_window_allows(monkeypatch):
    bill = owed("S1", date(2025, 1, 1), date(2024, 12, 1), date(2024, 12, 5))
    windowed(monkeypatch, {})
    assert verifier._expect_deadline(family(bill)) == date(2025, 8, 29)  # only the federal 240 days
    windowed(monkeypatch, {"after_first_statement_days": 100})
    assert verifier._expect_deadline(family(bill)) == date(2025, 8, 29)
    windowed(monkeypatch, {"after_first_statement_days": 300})
    assert verifier._expect_deadline(family(bill)) == date(2025, 10, 28)
    windowed(monkeypatch, {"after_service_days": 400})
    assert verifier._expect_deadline(family(bill)) == date(2026, 1, 9)  # 400 days from the last day of service


def test_expect_deadline_365_days_after_service_is_a_calendar_year_not_365_days(monkeypatch):
    bill = owed("S1", date(2023, 1, 1), date(2023, 2, 20), date(2023, 3, 1))
    windowed(monkeypatch, {"after_service_days": 365})
    assert verifier._expect_deadline(family(bill)) == date(2024, 3, 1)
    windowed(monkeypatch, {"after_service_days": 366})  # must differ: any other number stays days
    assert verifier._expect_deadline(family(bill)) == date(2024, 3, 1)
    windowed(monkeypatch, {"after_service_days": 364})
    assert verifier._expect_deadline(family(bill)) == date(2024, 2, 28)


def test_expect_deadline_service_end_falls_back_to_the_start_and_takes_the_latest_of_the_stay(monkeypatch):
    windowed(monkeypatch, {"after_service_days": 365})
    c = family(owed("S1", date(2025, 1, 1), date(2024, 12, 1)), owed("S2", date(2025, 1, 2), date(2024, 12, 3)))
    assert verifier._expect_deadline(c) == date(2025, 12, 3)


def test_expect_deadline_counts_months_from_the_last_payment_of_the_stay(monkeypatch):
    windowed(monkeypatch, {"after_last_insurance_payment_months": 12})
    bill = owed("S1", date(2025, 1, 1), date(2024, 12, 1), insurance_payment_date=date(2025, 1, 20))
    claim = eob("S4", row(1, service_date=date(2024, 12, 1), code="0112"), provider="Plan",
                insurance_payment_date=date(2025, 3, 15))
    assert verifier._expect_deadline(family(bill, claim)) == date(2026, 3, 15)


def test_expect_deadline_an_undated_insurance_statement_counts_only_when_the_case_has_one_stay(monkeypatch):
    windowed(monkeypatch, {"after_last_insurance_payment_months": 12})
    bill = owed("S1", date(2025, 1, 1), date(2024, 12, 1))
    claim = eob("S4", row(1, code="0112"), insurance_payment_date=date(2025, 3, 15))
    assert verifier._expect_deadline(family(bill, claim)) == date(2026, 3, 15)
    paid = owed("S2", date(2025, 6, 1), date(2025, 5, 1), balance="0.00")  # a second stay, nothing owed on it
    assert verifier._expect_deadline(family(bill, paid, claim)) == date(2025, 8, 29)


def test_expect_deadline_a_stay_is_a_week_from_its_first_bill(monkeypatch):
    windowed(monkeypatch, {})
    day = date(2025, 1, 1)
    later = date(2025, 9, 15)  # past the first statement's 240 days, before the second's
    # 7 days apart: one stay, so only the first statement of the two counts
    together = family(owed("S1", date(2025, 2, 1), day), owed("S2", date(2025, 1, 10), date(2025, 1, 8)), today=later)
    assert verifier._expect_deadline(together) == date(2025, 9, 7)
    # must differ: 8 days apart makes two stays, and the stay of the later statement is still open
    apart = family(owed("S1", date(2025, 2, 1), day), owed("S2", date(2025, 1, 10), date(2025, 1, 9)), today=later)
    assert verifier._expect_deadline(apart) == date(2025, 9, 29)
    # 5 days from the second bill but 9 from the first: a new stay with its own statement
    chain = family(owed("S1", date(2025, 1, 3), day), owed("S2", date(2025, 2, 1), date(2025, 1, 5), balance="0.00"),
                   owed("S3", date(2025, 3, 1), date(2025, 1, 10)), today=later)
    assert verifier._expect_deadline(chain) == date(2025, 10, 27)


def test_expect_deadline_the_paper_with_no_debt_still_dates_its_stay(monkeypatch):
    windowed(monkeypatch, {})
    c = family(owed("S1", date(2025, 1, 3), date(2025, 1, 1), balance="0.00"), owed("S2", date(2025, 3, 1), date(2025, 1, 2)))
    assert verifier._expect_deadline(c) == date(2025, 8, 31)


def test_expect_deadline_undated_bills_make_one_stay_of_their_own(monkeypatch):
    windowed(monkeypatch, {"after_service_days": 30})
    c = family(owed("S1", date(2025, 1, 1), None, date(2025, 11, 20)), owed("S2", date(2025, 3, 1), None), today=TODAY)
    assert verifier._expect_deadline(c) == date(2025, 12, 20)


def test_expect_deadline_takes_the_earliest_date_still_open_then_the_latest_gone(monkeypatch):
    windowed(monkeypatch, {})
    first = owed("S1", date(2025, 1, 1), date(2025, 1, 1))  # 2025-08-29
    second = owed("S2", date(2025, 6, 1), date(2025, 5, 1))  # 2026-01-27
    assert verifier._expect_deadline(family(first, second, today=date(2025, 1, 1))) == date(2025, 8, 29)
    assert verifier._expect_deadline(family(first, second, today=date(2025, 8, 29))) == date(2025, 8, 29)
    assert verifier._expect_deadline(family(first, second, today=date(2025, 8, 30))) == date(2026, 1, 27)
    assert verifier._expect_deadline(family(first, second, today=date(2026, 1, 28))) == date(2026, 1, 27)


def test_expect_deadline_a_doctors_group_bill_does_not_count(monkeypatch):
    windowed(monkeypatch, {})
    doctor = owed("S1", date(2025, 1, 1), date(2025, 1, 1), provider="Women First OBGYN")
    hospital = owed("S2", date(2025, 3, 1), date(2025, 1, 2), provider="Seaside Regional Hospital")
    assert verifier._expect_deadline(family(doctor, hospital, letterhead="Seaside Regional Hospital")) == date(2025, 10, 27)


def test_expect_deadline_of_an_unknown_policy_is_an_error_even_with_no_bills():
    with pytest.raises(FileNotFoundError):
        verifier._expect_deadline(family(policy_id="no-such-policy"))


# --- check_findings: shape and order -------------------------------------------------------------

def test_check_findings_on_nothing_is_a_clean_new_verdict():
    v = verifier.check_findings(family(), report())
    assert (v.issues, v.checked, v.model_notes, v.checker, v.ok) == ([], 0, [], "Muse Wonder", True)


def test_check_findings_counts_every_finding_and_numbers_each_kind_on_its_own():
    c = family(paper("S1"), paper("S2"))
    v = verifier.check_findings(c, report(finding(Kind.E4, at("S1")), finding(Kind.P1), finding(Kind.E4, at("S2"))))
    assert v.checked == 3 and v.ok


def test_check_findings_names_the_paper_in_the_subject():
    assert check(family(paper("S1")), finding(Kind.E4, at("S1"), amount="1.00"), finding(Kind.E4, amount="2.00")) == [
        ("E4 #1 on S1", "doubt", "no trace to what the sheets print"), ("E4 #1 on S1", "note", RECOMPUTE),
        ("E4 #2", "doubt", "no trace to what the sheets print"), ("E4 #2", "note", RECOMPUTE)]


def test_check_findings_says_when_evidence_points_nowhere():
    c = family(paper("S1", row(1)))
    assert check(c, finding(Kind.E4, at("S9", 3), at("S1", 9), at("S1", 1), at("S1"))) == [
        ("E4 #1 on S9", "error", "points to S9, which is not in the case"),
        ("E4 #1 on S9", "error", "points to line 9 of S1, which does not exist")]


def test_check_findings_a_sum_needs_a_trace_that_the_sheets_print():
    c = family(paper("S1", row(1, charges=Decimal("5.00")), patient_balance=Decimal("7.00")))
    good = [printed("S1", 1, "charges", "5.00"), printed("S1", None, "patient_balance", "7.00")]
    assert check(c, finding(Kind.E4, at("S1"), amount="1.00", trace=good)) == [("E4 #1 on S1", "note", RECOMPUTE)]
    bad_line = [printed("S1", 1, "charges", "9.99")]
    assert check(c, finding(Kind.E4, at("S1"), amount="1.00", trace=bad_line))[0] == (
        "E4 #1 on S1", "doubt", "line 1 of S1 does not print 9.99")
    bad_paper = [printed("S1", None, "patient_balance", "9.99")]
    assert check(c, finding(Kind.E4, at("S1"), amount="1.00", trace=bad_paper))[0] == (
        "E4 #1 on S1", "doubt", "S1 does not print 9.99")


def test_check_findings_a_finding_without_a_sum_needs_no_trace():
    assert check(family(paper("S1")), finding(Kind.E4, at("S1"))) == []


def test_check_findings_a_capped_sum_with_no_second_path_is_not_a_note():
    trace = [printed("S1", None, "patient_balance", "7.00")]
    c = family(paper("S1", patient_balance=Decimal("7.00")))
    assert check(c, finding(Kind.E4, at("S1"), amount="1.00", trace=trace, math={"cap": "1.00"})) == []


def test_check_findings_a_quote_must_be_on_its_page(monkeypatch):
    ref = f"{MEMORIAL}#window"
    c = family(paper("S1"))
    assert check(c, finding(Kind.E4, at("S1"), refs=[ref])) == []
    monkeypatch.setattr(policy, "verified", lambda r: False)
    assert check(c, finding(Kind.E4, at("S1"), refs=[ref, f"{MEMORIAL}#tier-200"])) == [
        ("E4 #1 on S1", "error", f"quote {ref} is not on its page"),
        ("E4 #1 on S1", "error", f"quote {MEMORIAL}#tier-200 is not on its page")]


def test_check_findings_issues_of_one_finding_come_in_a_fixed_order_and_the_total_comes_last(monkeypatch):
    monkeypatch.setattr(policy, "verified", lambda r: False)
    c = family(paper("S1", row(1, patient_responsibility=Decimal("-5.00")), patient_balance=Decimal("3.00")))
    f = finding(Kind.E3, at("S1", 1), at("S9"), amount="9.00", refs=["x#y"])
    other = finding(Kind.E1, at("S1", 1), at("S1", 1), amount="1.00", trace=[printed("S1", 1, "patient_responsibility", "-5.00")])
    third = finding(Kind.E1, at("S1", 1), at("S1", 1), amount="1.00", trace=[printed("S1", 1, "patient_responsibility", "-5.00")])
    assert check(c, f, other, third, total="99.00") == [
        ("E3 #1 on S1", "doubt", "no trace to what the sheets print"),
        ("E3 #1 on S1", "error", "points to S9, which is not in the case"),
        ("E3 #1 on S1", "error", "quote x#y is not on its page"),
        ("E3 #1 on S1", "doubt", "the papers of this account still ask for money"),
        ("E3 #1 on S1", "error", "amount 9.00 but recomputed from the sheets: 5.00"),
        ("E1 #1 on S1", "error", "amount 1.00 but recomputed from the sheets: 0.00"),
        ("E1 #2 on S1", "error", "amount 1.00 but recomputed from the sheets: 0.00"),
        ("E1 #2 on S1", "doubt", "line 1 of S1 is counted more than once"),
        ("total", "error", "total 99.00 but findings add up to 11.00")]


def test_check_findings_a_wrong_total_is_an_error_named_total():
    c = family(paper("S1"))
    assert check(c, total="5.00") == [("total", "error", "total 5.00 but findings add up to 0.00")]


@pytest.mark.parametrize("total", ["0", "0.00", "0.0"])
def test_check_findings_compares_the_total_by_value(total):
    assert check(family(), total=total) == []


def test_check_findings_rounds_the_sum_of_the_findings_before_it_compares():
    c = family(paper("S1", patient_balance=Decimal("1.00")))
    trace = [printed("S1", None, "patient_balance", "1.00")]
    assert check(c, finding(Kind.E4, at("S1"), amount="1.005", trace=trace, math={"cap": ""}), total="1.01") == []


def test_check_findings_leaves_the_case_and_the_report_as_they_were():
    c = anna()
    r = checks.run(c)
    before = c.model_dump_json() + r.model_dump_json()
    verifier.check_findings(c, r)
    assert c.model_dump_json() + r.model_dump_json() == before


# --- check_findings: E1 and E2 -------------------------------------------------------------------

def e1_family():
    return family(paper("S1", row(2, patient_responsibility=Decimal("2887.50")), patient_balance=Decimal("5000.00")),
                  eob("S4", row(2, patient_responsibility=Decimal("2575.10"))))


TRACED = [printed("S1", 2, "patient_responsibility", "2887.50")]


def test_check_findings_e1_with_the_right_sum_is_clean():
    assert check(e1_family(), finding(Kind.E1, *E1_LINES, amount="312.40", trace=TRACED)) == []


def test_check_findings_e1_with_a_wrong_sum_is_an_error_with_both_numbers():
    assert check(e1_family(), finding(Kind.E1, *E1_LINES, amount="300.00", trace=TRACED)) == [
        ("E1 #1 on S1", "error", "amount 300.00 but recomputed from the sheets: 312.40")]


def test_check_findings_e1_that_cannot_be_recomputed_is_a_note_not_an_error():
    assert check(e1_family(), finding(Kind.E1, at("S1", 2), amount="300.00", trace=TRACED)) == [
        ("E1 #1 on S1", "note", RECOMPUTE)]


def test_check_findings_e1_without_a_sum_is_neither_compared_nor_noted():
    assert check(e1_family(), finding(Kind.E1, *E1_LINES)) == []


def test_check_findings_e1_or_e3_without_evidence_stops_with_an_index_error():
    for kind in (Kind.E1, Kind.E3):
        with pytest.raises(IndexError):
            verifier.check_findings(family(), report(finding(kind)))


def test_check_findings_e2_expects_the_first_positive_share_on_every_second_evidence_line():
    c = family(paper("S1", row(1, patient_responsibility=Decimal("40.00")), row(2, patient_responsibility=Decimal("40.00")),
                     patient_balance=Decimal("100.00")),
               paper("S2", row(1, patient_responsibility=Decimal("0.00")), row(2),
                     row(3, patient_responsibility=Decimal("-1.00")), row(4, patient_responsibility=Decimal("70.00")),
                     row(5, patient_responsibility=Decimal("9.00"))))
    trace = [printed("S1", 1, "patient_responsibility", "40.00")]
    evidence = (at("S1", 1), at("S2", 1), at("S1", 2), at("S2", 2), at("S2", 5), at("S2", 3), at("S2", 5), at("S2", 4),
                at("S2", 5), at("S2", 5))
    assert check(c, finding(Kind.E2, *evidence, amount="70.00", trace=trace)) == []
    assert ("E2 #1 on S1", "error", "amount 9.00 but recomputed from the sheets: 70.00") in check(
        c, finding(Kind.E2, *evidence, amount="9.00", trace=trace))


def test_check_findings_e2_with_no_positive_share_is_a_note():
    c = family(paper("S1", row(1, patient_responsibility=Decimal("0.00")), patient_balance=Decimal("100.00")))
    trace = [printed("S1", None, "patient_balance", "100.00")]
    assert check(c, finding(Kind.E2, at("S1", 1), at("S1", 1), amount="5.00", trace=trace)) == [
        ("E2 #1 on S1", "note", RECOMPUTE)]
    assert check(c, finding(Kind.E2, amount="5.00", trace=trace)) == [
        ("E2 #1", "note", RECOMPUTE), ("E2 #1", "doubt", "no bill in the papers asks for this")]


# --- check_findings: E3 --------------------------------------------------------------------------

E3_TRACE = [printed("S1", None, "patient_balance", "-40.00")]


def e3_family(**fields):
    return family(paper("S1", row(1, patient_responsibility=Decimal("-25.00")), row(2),
                        patient_balance=Decimal("-40.00"), **fields))


def test_check_findings_e3_on_a_line_expects_the_size_of_that_line():
    assert check(e3_family(), finding(Kind.E3, at("S1", 1), amount="25.00", trace=E3_TRACE)) == []
    assert check(e3_family(), finding(Kind.E3, at("S1", 1), amount="24.00", trace=E3_TRACE)) == [
        ("E3 #1 on S1", "error", "amount 24.00 but recomputed from the sheets: 25.00")]


def test_check_findings_e3_on_a_paper_expects_the_size_of_its_balance():
    assert check(e3_family(), finding(Kind.E3, at("S1"), amount="40.00", trace=E3_TRACE)) == []


def test_check_findings_e3_on_a_line_with_no_share_does_not_fall_back_to_the_balance():
    assert check(e3_family(), finding(Kind.E3, at("S1", 2), amount="40.00", trace=E3_TRACE)) == [
        ("E3 #1 on S1", "note", RECOMPUTE)]


def test_check_findings_e3_on_a_line_that_is_not_there_falls_back_to_the_balance():
    assert check(e3_family(), finding(Kind.E3, at("S1", 7), amount="40.00", trace=E3_TRACE)) == [
        ("E3 #1 on S1", "error", "points to line 7 of S1, which does not exist")]


def test_check_findings_e3_on_a_missing_paper_is_a_note_after_the_error():
    assert check(e3_family(), finding(Kind.E3, at("S9"), amount="40.00", trace=E3_TRACE)) == [
        ("E3 #1 on S9", "error", "points to S9, which is not in the case"), ("E3 #1 on S9", "note", RECOMPUTE)]


def test_check_findings_e3_doubts_a_credit_on_an_account_that_still_asks_for_money():
    c = family(paper("S1", row(1, patient_responsibility=Decimal("-25.00")), patient_balance=Decimal("100.00")))
    trace = [printed("S1", 1, "patient_responsibility", "-25.00")]
    assert check(c, finding(Kind.E3, at("S1", 1), amount="25.00", trace=trace)) == [
        ("E3 #1 on S1", "doubt", "the papers of this account still ask for money")]
    assert check(c, finding(Kind.E3, at("S1", 1))) == []  # no sum, nothing to doubt


def test_check_findings_e3_on_a_paper_that_is_no_bill_asks_for_nothing():
    c = family(eob("S4", row(1, patient_responsibility=Decimal("-25.00")), patient_balance=Decimal("100.00")))
    trace = [printed("S4", 1, "patient_responsibility", "-25.00")]
    assert check(c, finding(Kind.E3, at("S4", 1), amount="25.00", trace=trace)) == []


# --- check_findings: F1, F3 ----------------------------------------------------------------------

def discount_family(income="85000", balance="1240.00"):
    return family(paper("S2", patient_balance=money(balance), account_ref="A-2"),
                  paper("S1", row(2, patient_responsibility=Decimal("100.00")), patient_balance=Decimal("500.00"),
                        account_ref="A-1"), income=income)


NO_DISCOUNT = at("S2", note="no discount")
S2_TRACE = [printed("S2", None, "patient_balance", "1240.00")]


def test_check_findings_a_discount_is_recomputed_from_the_income_and_the_bill():
    good = finding(Kind.F3, NO_DISCOUNT, amount="1054.00", math={"fpl_pct": "1"}, trace=S2_TRACE)
    assert check(discount_family(), good) == []
    wrong = finding(Kind.F1, NO_DISCOUNT, amount="1000.00", math={"fpl_pct": "1"}, trace=S2_TRACE)
    assert check(discount_family(), wrong) == [
        ("F1 #1 on S2", "error", "amount 1000.00 but recomputed from the sheets: 1054.00")]


def test_check_findings_a_discount_is_taken_after_the_debts_that_come_off_the_same_bill():
    c = family(paper("S2", row(1, patient_responsibility=Decimal("1240.00")), patient_balance=Decimal("1240.00")),
               eob("S4", row(1, patient_responsibility=Decimal("1000.00"))), income="85000")
    over = finding(Kind.E1, at("S2", 1), at("S4", 1), amount="240.00", trace=[printed("S2", 1, "patient_responsibility", "1240.00")])
    discount = finding(Kind.F3, NO_DISCOUNT, amount="850.00", math={"fpl_pct": "1"}, trace=S2_TRACE)
    assert check(c, over, discount) == []


@pytest.mark.parametrize("math,evidence,expected", [
    ({"fpl_pct": "1"}, (at("S2"),), [("F1 #1 on S2", "note", RECOMPUTE)]),
    ({"fpl_pct": "1", "cap": "1"}, (at("S2"),), []),
    ({}, (NO_DISCOUNT,), [("F1 #1 on S2", "note", RECOMPUTE)]),
])
def test_check_findings_a_discount_with_no_second_path_is_a_note(math, evidence, expected):
    assert check(discount_family(), finding(Kind.F1, *evidence, amount="10.00", math=math, trace=S2_TRACE)) == expected


def test_check_findings_a_discount_above_every_tier_has_no_second_path():
    f = finding(Kind.F1, NO_DISCOUNT, amount="10.00", math={"fpl_pct": "1"}, trace=S2_TRACE)
    assert check(discount_family(income="900000"), f) == [("F1 #1 on S2", "note", RECOMPUTE)]


def test_check_findings_a_cap_does_not_stop_a_recomputed_discount_from_being_compared():
    f = finding(Kind.F1, NO_DISCOUNT, amount="1000.00", math={"fpl_pct": "1", "cap": "1"}, trace=S2_TRACE)
    assert check(discount_family(), f) == [("F1 #1 on S2", "error", "amount 1000.00 but recomputed from the sheets: 1054.00")]


# --- check_findings: F2 --------------------------------------------------------------------------

def test_check_findings_f2_compares_the_deadline_and_says_both_dates():
    c = anna()
    right = finding(Kind.F2, at("S3"), deadline=date(2026, 9, 2))
    assert check(c, right) == []
    assert check(c, finding(Kind.F2, at("S3"), deadline=date(2026, 9, 1))) == [
        ("F2 #1 on S3", "error", "deadline 2026-09-01 but the sheets and policy give 2026-09-02")]


def test_check_findings_f2_without_a_date_against_nothing_is_clean_and_against_a_date_is_an_error():
    assert check(family(), finding(Kind.F2)) == []
    assert check(anna(), finding(Kind.F2)) == [("F2 #1", "error", "deadline None but the sheets and policy give 2026-09-02")]
    assert check(family(), finding(Kind.F2, deadline=date(2026, 9, 1))) == [
        ("F2 #1", "error", "deadline 2026-09-01 but the sheets and policy give None")]


def test_check_findings_f2_never_notes_its_sum():
    trace = [printed("S1", None, "patient_balance", "1.00")]
    c = family(paper("S1", patient_balance=Decimal("1.00")))
    assert check(c, finding(Kind.F2, at("S1"), amount="1.00", trace=trace)) == []


# --- check_findings: C1 and C2 -------------------------------------------------------------------

def price_index(*rates, gross="1000", cash="400"):
    listed = prices.Price("CPT", "99285", "ER visit", "outpatient", Decimal(gross), Decimal(cash), 7)
    plan_rates = {}
    for code_type, code, dollar in rates:
        plan_rates.setdefault(f"{code_type}:{code}", []).append(
            prices.Rate(code_type, code, "stay", "inpatient", Decimal(dollar), "case rate", 3))
    return prices.Index(MEMORIAL, "Hospital", "https://example.org/f", "2026-05-27", "3", {"CPT:99285": [listed]},
                        {prices.plan_key("Aetna", "Silver"): plan_rates})


def priced(monkeypatch, index):
    monkeypatch.setattr(prices, "load", lambda policy_id: index)


def c1_family(charges="1000.00", share="1000.00", code="99285"):
    return family(paper("S1", row(1, code=code, charges=money(charges), patient_responsibility=money(share)),
                        patient_balance=Decimal("5000.00")))


C1_TRACE = [printed("S1", None, "patient_balance", "5000.00")]


def test_check_findings_c1_recomputes_the_saving_from_the_hospital_file(monkeypatch):
    priced(monkeypatch, price_index())
    assert check(c1_family(), finding(Kind.C1, at("S1", 1), amount="600.00", trace=C1_TRACE)) == []
    assert check(c1_family(), finding(Kind.C1, at("S1", 1), amount="500.00", trace=C1_TRACE)) == [
        ("C1 #1 on S1", "error", "amount 500.00 but recomputed from the sheets: 600.00")]


def test_check_findings_c1_counts_units_and_stops_at_what_the_line_still_asks(monkeypatch):
    priced(monkeypatch, price_index())
    assert check(c1_family("2000.00", "2000.00"), finding(Kind.C1, at("S1", 1), amount="1200.00", trace=C1_TRACE)) == []
    assert check(c1_family("2000.00", "300.00"), finding(Kind.C1, at("S1", 1), amount="300.00", trace=C1_TRACE)) == []
    assert check(c1_family("2000.00", None), finding(Kind.C1, at("S1", 1), amount="1200.00", trace=C1_TRACE)) == []
    assert check(c1_family("1000.00", None), finding(Kind.C1, at("S1", 1), amount="600.00", trace=C1_TRACE)) == []


def test_check_findings_c1_a_share_of_zero_is_the_ceiling_not_a_missing_value(monkeypatch):
    priced(monkeypatch, price_index())
    assert check(c1_family("1000.00", "0.00"), finding(Kind.C1, at("S1", 1), amount="600.00", trace=C1_TRACE)) == [
        ("C1 #1 on S1", "error", "amount 600.00 but recomputed from the sheets: 0.00")]


@pytest.mark.parametrize("charges,code", [("0.00", "99285"), (None, "99285"), ("1000.00", "11111"), ("777.00", "99285")])
def test_check_findings_c1_with_no_single_price_is_a_note(monkeypatch, charges, code):
    priced(monkeypatch, price_index())
    f = finding(Kind.C1, at("S1", 1), amount="600.00", trace=C1_TRACE)
    assert check(c1_family(charges, "1000.00", code), f) == [("C1 #1 on S1", "note", RECOMPUTE)]


def test_check_findings_c1_without_a_price_file_is_a_note(monkeypatch):
    priced(monkeypatch, None)
    assert check(c1_family(), finding(Kind.C1, at("S1", 1), amount="600.00", trace=C1_TRACE)) == [
        ("C1 #1 on S1", "note", RECOMPUTE)]


def test_check_findings_c1_without_a_sum_or_evidence_does_not_open_the_price_file(monkeypatch):
    def refuse(policy_id):
        raise AssertionError("the price file was opened")
    monkeypatch.setattr(prices, "load", refuse)
    assert check(c1_family(), finding(Kind.C1, at("S1", 1))) == []
    assert check(c1_family(), finding(Kind.C1, amount="600.00", trace=C1_TRACE)) == [
        ("C1 #1", "note", RECOMPUTE), ("C1 #1", "doubt", "no bill in the papers asks for this")]


def test_check_findings_c1_on_a_line_that_is_not_there_is_an_error_and_a_note(monkeypatch):
    priced(monkeypatch, price_index())
    assert check(c1_family(), finding(Kind.C1, at("S1", 7), amount="600.00", trace=C1_TRACE)) == [
        ("C1 #1 on S1", "error", "points to line 7 of S1, which does not exist"), ("C1 #1 on S1", "note", RECOMPUTE)]


SILVER = Plan(payer="Aetna", plan_name="Silver")


def c2_family(code="DRG 807", charges="8000.00", adjustment="-1900.00", share="1900.00", plan=SILVER):
    return family(paper("S1", row(1, code=code, charges=money(charges), adjustment=money(adjustment),
                                  patient_responsibility=money(share)), patient_balance=Decimal("5000.00")), plan=plan)


@pytest.mark.parametrize("code", ["DRG 807", "drg807", "DRG#807", "DRG # 807", " MS-DRG 807 ", "MSDRG807", "ms-drg #807"])
def test_check_findings_c2_reads_every_way_a_case_rate_code_is_printed(monkeypatch, code):
    priced(monkeypatch, price_index(("MS-DRG", "807", "5100.00")))
    assert check(c2_family(code), finding(Kind.C2, at("S1", 1), amount="1000.00", trace=C1_TRACE)) == []


def test_check_findings_c2_a_plain_code_takes_its_type_from_the_finding(monkeypatch):
    priced(monkeypatch, price_index(("CPT", "59400", "5100.00")))
    f = finding(Kind.C2, at("S1", 1), amount="1000.00", trace=C1_TRACE, math={"code_type": "CPT"})
    assert check(c2_family(" 59400 "), f) == []
    untyped = finding(Kind.C2, at("S1", 1), amount="1000.00", trace=C1_TRACE)
    assert check(c2_family(" 59400 "), untyped) == [("C2 #1 on S1", "note", RECOMPUTE)]


def test_check_findings_c2_expects_what_the_plan_allowed_over_its_rate_up_to_the_family_share(monkeypatch):
    priced(monkeypatch, price_index(("MS-DRG", "807", "5100.00")))
    assert check(c2_family(share="700.00"), finding(Kind.C2, at("S1", 1), amount="1000.00", trace=C1_TRACE)) == [
        ("C2 #1 on S1", "error", "amount 1000.00 but recomputed from the sheets: 700.00")]
    assert check(c2_family(adjustment="1900.00"), finding(Kind.C2, at("S1", 1), amount="1000.00", trace=C1_TRACE)) == []


@pytest.mark.parametrize("share", [None, "0.00"])
def test_check_findings_c2_a_missing_or_zero_share_gives_a_plain_zero(monkeypatch, share):
    priced(monkeypatch, price_index(("MS-DRG", "807", "5100.00")))
    assert check(c2_family(share=share), finding(Kind.C2, at("S1", 1), amount="1000.00", trace=C1_TRACE)) == [
        ("C2 #1 on S1", "error", "amount 1000.00 but recomputed from the sheets: 0")]


def test_check_findings_c2_a_rate_above_what_was_allowed_stays_negative(monkeypatch):
    priced(monkeypatch, price_index(("MS-DRG", "807", "7000.00")))
    assert check(c2_family(), finding(Kind.C2, at("S1", 1), amount="1000.00", trace=C1_TRACE)) == [
        ("C2 #1 on S1", "error", "amount 1000.00 but recomputed from the sheets: -900.00")]


def test_check_findings_c2_one_rate_listed_twice_is_one_rate_and_two_rates_are_no_answer(monkeypatch):
    f = finding(Kind.C2, at("S1", 1), amount="1000.00", trace=C1_TRACE)
    priced(monkeypatch, price_index(("MS-DRG", "807", "5100.00"), ("MS-DRG", "807", "5100.0")))
    assert check(c2_family(), f) == []
    priced(monkeypatch, price_index(("MS-DRG", "807", "5100.00"), ("MS-DRG", "807", "5200.00")))
    assert check(c2_family(), f) == [("C2 #1 on S1", "note", RECOMPUTE)]


@pytest.mark.parametrize("fields", [{"plan": None}, {"charges": None}, {"adjustment": None}])
def test_check_findings_c2_with_something_missing_is_a_note(monkeypatch, fields):
    priced(monkeypatch, price_index(("MS-DRG", "807", "5100.00")))
    f = finding(Kind.C2, at("S1", 1), amount="1000.00", trace=C1_TRACE)
    assert check(c2_family(**fields), f) == [("C2 #1 on S1", "note", RECOMPUTE)]


def test_check_findings_c2_with_charges_of_zero_is_still_computed(monkeypatch):
    priced(monkeypatch, price_index(("MS-DRG", "807", "100.00")))
    f = finding(Kind.C2, at("S1", 1), amount="1000.00", trace=C1_TRACE)
    assert check(c2_family(charges="0.00"), f) == [
        ("C2 #1 on S1", "error", "amount 1000.00 but recomputed from the sheets: -2000.00")]


def test_check_findings_c2_without_a_price_file_is_a_note(monkeypatch):
    priced(monkeypatch, None)
    assert check(c2_family(), finding(Kind.C2, at("S1", 1), amount="1000.00", trace=C1_TRACE)) == [
        ("C2 #1 on S1", "note", RECOMPUTE)]


# --- check_findings: N1 --------------------------------------------------------------------------

def n1_family(claim="C-1", line_claim="C-1", balance="500.00", eob_claim="C-1", share="200.00"):
    return family(paper("S1", row(1, claim_ref=line_claim, patient_responsibility=Decimal("500.00")),
                        patient_balance=money(balance), claim_ref=claim),
                  eob("S4", row(1, claim_ref=eob_claim, patient_responsibility=money(share)),
                      row(2, claim_ref="C-9", patient_responsibility=Decimal("50.00"))))


N1_TRACE = [printed("S1", None, "patient_balance", "500.00")]
N1_LINES = (at("S1"), at("S4", 1))


def test_check_findings_n1_expects_the_bill_less_what_the_plan_says_the_family_owes():
    assert check(n1_family(), finding(Kind.N1, *N1_LINES, amount="300.00", trace=N1_TRACE)) == []
    assert check(n1_family(), finding(Kind.N1, *N1_LINES, amount="1.00", trace=N1_TRACE)) == [
        ("N1 #1 on S1", "error", "amount 1.00 but recomputed from the sheets: 300.00")]


def test_check_findings_n1_adds_up_every_share_it_points_to():
    f = finding(Kind.N1, at("S1"), at("S4", 1), at("S4", 2), amount="250.00", trace=N1_TRACE)
    assert check(n1_family(), f) == []


def test_check_findings_n1_comes_after_e1_and_e2_on_the_same_bill_and_not_after_others():
    c = n1_family()
    line = (at("S1", 1), at("S4", 1))
    trace = [printed("S1", 1, "patient_responsibility", "500.00")]
    over = finding(Kind.E1, *line, amount="300.00", trace=trace)
    assert check(c, over, finding(Kind.N1, *N1_LINES, amount="0.00", trace=N1_TRACE)) == []
    credit = finding(Kind.E4, at("S1"), amount="100.00", trace=N1_TRACE)
    assert check(c, credit, finding(Kind.N1, *N1_LINES, amount="300.00", trace=N1_TRACE)) == [
        ("E4 #1 on S1", "note", RECOMPUTE)]


def test_check_findings_n1_with_no_share_to_compare_is_a_note():
    f = finding(Kind.N1, at("S1"), at("S4", 7), amount="300.00", trace=N1_TRACE)
    assert check(n1_family(claim="", line_claim=""), f) == [
        ("N1 #1 on S1", "error", "points to line 7 of S4, which does not exist"), ("N1 #1 on S1", "note", RECOMPUTE)]


def test_check_findings_n1_with_a_share_of_zero_still_compares():
    assert check(n1_family(share="0.00"), finding(Kind.N1, *N1_LINES, amount="500.00", trace=N1_TRACE)) == []


def test_check_findings_n1_doubts_a_claim_no_insurance_statement_answers_on_the_paper_or_a_line():
    doubt = ("N1 #1 on S1", "doubt", "a claim on this bill has no insurance statement in the papers")
    f = finding(Kind.N1, *N1_LINES, amount="300.00", trace=N1_TRACE)
    assert check(n1_family(claim="C-2"), f) == [doubt]
    assert check(n1_family(line_claim="C-3"), f) == [doubt]
    assert check(n1_family(claim="", line_claim=""), f) == []


def test_check_findings_n1_doubt_comes_even_without_a_sum_and_before_the_comparison():
    doubt = ("N1 #1 on S1", "doubt", "a claim on this bill has no insurance statement in the papers")
    assert check(n1_family(claim="C-2"), finding(Kind.N1, *N1_LINES)) == [doubt]
    assert check(n1_family(claim="C-2"), finding(Kind.N1, *N1_LINES, amount="1.00", trace=N1_TRACE)) == [
        doubt, ("N1 #1 on S1", "error", "amount 1.00 but recomputed from the sheets: 300.00")]


def test_check_findings_n1_on_a_paper_not_in_the_case_says_so_and_has_no_second_path():
    assert check(n1_family(), finding(Kind.N1, at("S9"), at("S4", 1), amount="1.00", trace=N1_TRACE)) == [
        ("N1 #1 on S9", "error", "points to S9, which is not in the case"), ("N1 #1 on S9", "note", RECOMPUTE),
        ("N1 #1 on S9", "doubt", "no bill in the papers asks for this")]


def test_check_findings_n1_without_evidence_is_a_note():
    f = finding(Kind.N1, amount="1.00", trace=N1_TRACE)
    assert check(n1_family(), f) == [("N1 #1", "note", RECOMPUTE), ("N1 #1", "doubt", "no bill in the papers asks for this")]


# --- check_letters -------------------------------------------------------------------------------

def test_check_letters_returns_a_new_verdict_or_adds_to_the_one_it_is_given():
    existing = Verdict(issues=[Issue("x", "note", "kept")], checked=5)
    assert verifier.check_letters(family(), report(), [letter(Paragraph("clean"))], existing) is existing
    assert existing.checked == 6 and issues(existing) == [("x", "note", "kept")]
    fresh = verifier.check_letters(family(), report(), [letter(Paragraph("a")), letter(Paragraph("b"))])
    assert fresh.checked == 2 and fresh.issues == []


def test_check_letters_with_no_letters_changes_nothing():
    v = verifier.check_letters(family(), report(), [])
    assert (v.checked, v.issues) == (0, [])


def test_check_letters_names_each_letter_by_its_kind():
    v = verifier.check_letters(family(), report(), [letter(Paragraph("$1.00"), kind="itemized"),
                                                    letter(Paragraph("$2.00"), kind="apply-discount")])
    assert issues(v) == [("letter itemized", "error", "$1.00 does not come from the case"),
                         ("letter apply-discount", "error", "$2.00 does not come from the case")]


def test_check_letters_knows_every_quoted_number_of_the_case_and_the_report():
    c = family(income="85000")
    rep = report(finding(Kind.E4, math={"made up": "1234.5", "1500.25": "key", "negative": "-40"}))
    assert said(Paragraph("$85,000.00 and $85000.00 and $1,234.50 and $1,500.25 and $40.00 and $0.00"), case=c, rep=rep) == []


def test_check_letters_does_not_know_a_number_printed_without_quotes():
    c = family(paper("S1", row(77)), size=4)
    assert said(Paragraph("$4.00 and $77.00"), case=c) == [
        ("letter dispute", "error", "$4.00 does not come from the case"),
        ("letter dispute", "error", "$77.00 does not come from the case")]


def test_check_letters_a_long_run_of_digits_is_a_scan_line_not_money():
    c = family(paper("S1", account_ref="123456789012"), paper("S2", account_ref="1234567890123"))
    assert said(Paragraph("$123,456,789,012.00 and $1,234,567,890,123.00"), case=c) == [
        ("letter dispute", "error", "$1,234,567,890,123.00 does not come from the case")]


def test_check_letters_a_number_inside_a_longer_text_is_not_known():
    c = family(paper("S1", account_ref="A-100"))
    assert said(Paragraph("$100.00"), case=c) == [("letter dispute", "error", "$100.00 does not come from the case")]


def test_check_letters_rounds_known_numbers_half_to_even_to_the_cent():
    rep = report(finding(Kind.E4, math={"a": "2.665", "b": "2.675"}))
    assert said(Paragraph("$2.66 $2.68"), rep=rep) == []
    assert said(Paragraph("$2.67"), rep=rep) == [("letter dispute", "error", "$2.67 does not come from the case")]


def test_check_letters_reads_only_dollar_amounts_with_cents():
    assert said(Paragraph("$12 and 12.00 and $ 12.00 and $.50")) == []


@pytest.mark.parametrize("printed_amount", ["$,944.00", "$,100.00", "$,999.99", "$,,5.25", "$,.50"])
def test_check_letters_catches_an_amount_whose_first_digit_was_lost_and_leaves_a_comma_first(printed_amount):
    # "$4,944.00" with its first digit gone: the checker must still read it as an amount and keep it as printed
    v = verifier.check_letters(family(), report(), [letter(Paragraph(f"We owe {printed_amount} today."))])
    assert v.ok is False
    assert issues(v) == [("letter dispute", "error", f"{printed_amount} does not come from the case")]


def test_check_letters_the_whole_amount_is_clean_and_only_the_damaged_one_is_reported():
    c = family(income="4944")
    assert said(Paragraph("$4,944.00 and $,944.00"), case=c) == [
        ("letter dispute", "error", "$,944.00 does not come from the case")]


def test_check_letters_reports_an_amount_each_time_it_appears_as_printed():
    assert said(Paragraph("$1,234.50 and $1,234.50"), Paragraph("$1234.50")) == [
        ("letter dispute", "error", "$1,234.50 does not come from the case"),
        ("letter dispute", "error", "$1,234.50 does not come from the case"),
        ("letter dispute", "error", "$1234.50 does not come from the case")]


def test_check_letters_takes_the_first_two_decimals_of_a_longer_amount():
    assert said(Paragraph("$7.009")) == [("letter dispute", "error", "$7.00 does not come from the case")]


def test_check_letters_reads_a_quote_reference_from_every_paragraph(monkeypatch):
    monkeypatch.setattr(policy, "verified", lambda r: r != "a#1")
    assert said(Paragraph("x", ["a#1", "b#2"]), Paragraph("y", ["a#1"])) == [
        ("letter dispute", "error", "quote a#1 is not on its page"), ("letter dispute", "error", "quote a#1 is not on its page")]


@pytest.mark.parametrize("words", ["[ACCT_1]", "[PATIENT_12]", "[MEMBER_0]", "two [ACCT_1] and [ACCT_2]"])
def test_check_letters_says_once_that_a_token_was_left_in(words):
    assert said(Paragraph(words)) == [("letter dispute", "error", "a token is left in the letter instead of the real value")]


@pytest.mark.parametrize("words", ["[ACCT_]", "[acct_1]", "ACCT_1", "[OTHER_1]", "[ACCT_1a]"])
def test_check_letters_leaves_what_only_looks_like_a_token(words):
    assert said(Paragraph(words)) == []


@pytest.mark.parametrize("words,shown", [
    ("The DIAGNOSIS was wrong", "diagnos"), ("a treatment plan", "treatment plan"), ("this is medical advice", "medical advice"),
    ("You Should Take this", "you should take"), ("we will send it", "we will send"), ("I guarantee", "guarantee"),
    ("we promise it", "we promise"), ("you will get it", "you will get"), ("a lawsuit", "lawsuit"), ("we sue them", "sue"),
    ("this issue stays", "sue"), ("tissue paper", "sue"),
])
def test_check_letters_flags_risky_wording_by_a_plain_lowercase_search(words, shown):
    assert said(Paragraph(words)) == [("letter dispute", "error", f"wording '{shown}' sounds like advice or a promise")]


def test_check_letters_a_word_at_the_very_end_is_not_the_one_with_a_space():
    assert said(Paragraph("we may sue")) == []


def test_check_letters_paragraphs_are_read_joined_by_one_space():
    assert said(Paragraph("we may sue"), Paragraph("them")) == [
        ("letter dispute", "error", "wording 'sue' sounds like advice or a promise")]
    assert said(Paragraph("[ACCT_"), Paragraph("1]")) == []


def test_check_letters_flags_each_risky_word_once_in_the_order_of_the_list():
    assert said(Paragraph("we promise and guarantee, we promise")) == [
        ("letter dispute", "error", "wording 'guarantee' sounds like advice or a promise"),
        ("letter dispute", "error", "wording 'we promise' sounds like advice or a promise")]


def test_check_letters_a_dropped_paragraph_is_a_note_with_the_count():
    assert said(Paragraph("clean"), dropped=["a", "b"]) == [("letter dispute", "note", "2 paragraph(s) left out: quote not verified")]


def test_check_letters_issues_of_a_letter_come_in_a_fixed_order(monkeypatch):
    monkeypatch.setattr(policy, "verified", lambda r: False)
    assert said(Paragraph("we promise [ACCT_1] $3.00", ["a#1"]), dropped=["x"]) == [
        ("letter dispute", "error", "$3.00 does not come from the case"),
        ("letter dispute", "error", "quote a#1 is not on its page"),
        ("letter dispute", "error", "a token is left in the letter instead of the real value"),
        ("letter dispute", "error", "wording 'we promise' sounds like advice or a promise"),
        ("letter dispute", "note", "1 paragraph(s) left out: quote not verified")]


# --- verify --------------------------------------------------------------------------------------

def test_verify_is_the_findings_first_then_the_letters_in_one_verdict():
    c = family(paper("S1"))
    v = verifier.verify(c, report(finding(Kind.E4, at("S9"))), [letter(Paragraph("$1.00"))])
    assert v.checked == 2 and v.ok is False
    assert issues(v) == [("E4 #1 on S9", "error", "points to S9, which is not in the case"),
                         ("letter dispute", "error", "$1.00 does not come from the case")]


def test_verify_of_the_demo_case_is_clean():
    c = anna()
    r = checks.run(c)
    letters = writer.all_letters(c, r)
    v = verifier.verify(c, r, letters)
    assert (v.ok, v.issues, v.checked) == (True, [], 3 + 4)


# --- REVIEW_SCHEMA -------------------------------------------------------------------------------

def test_review_schema_is_the_strict_shape_the_model_answers_in():
    assert json.dumps(verifier.REVIEW_SCHEMA) == (
        '{"type": "object", "additionalProperties": false, "required": ["items"], "properties": {"items": '
        '{"type": "array", "items": {"type": "object", "additionalProperties": false, '
        '"required": ["subject", "verdict", "reason"], "properties": {"subject": {"type": "string"}, '
        '"verdict": {"type": "string", "enum": ["confirmed", "problem", "cannot_tell"]}, "reason": {"type": "string"}}}}}}')


# --- redacted ------------------------------------------------------------------------------------

def private_case():
    c = family(paper("S1", patient="PATIENT_1", account_ref="[ACCT_1]"), plan=SILVER, letterhead="Hospital")
    c.profile.people = [Person(token="PATIENT_1", role=Role.MOTHER, name="Anna Sample", birth_date="03/14/1994",
                               relationship="Self", employer="Sample Bakery LLC")]
    c.profile.local = LocalDetails(street="100 Example Street", phone="(555) 010-0000", checking=Decimal("2400"),
                                   tokens={"ACCT_1": "LDH-000123"})
    c.profile.context = ["er_visit"]
    c.profile.liquid_assets = Decimal("6000")
    return c


def test_redacted_clears_names_birth_dates_employers_and_all_local_details():
    clean = verifier.redacted(private_case())
    person = clean.profile.people[0]
    assert (person.name, person.birth_date, person.employer) == ("", "", "")
    assert clean.profile.local == LocalDetails()


def test_redacted_keeps_everything_else():
    c = private_case()
    clean = verifier.redacted(c)
    person = clean.profile.people[0]
    assert (person.token, person.role, person.relationship) == ("PATIENT_1", Role.MOTHER, "Self")
    p = clean.profile
    assert (p.household_size, p.annual_income, p.liquid_assets, p.insured, p.context, p.plan) == (
        4, Decimal("50000"), Decimal("6000"), True, ["er_visit"], SILVER)
    assert (clean.case_id, clean.policy_id, clean.today, clean.letterhead) == (c.case_id, c.policy_id, c.today, c.letterhead)
    assert clean.documents is c.documents and type(clean) is Case


def test_redacted_does_not_touch_the_case_it_is_given():
    c = private_case()
    before = c.model_dump_json()
    clean = verifier.redacted(c)
    assert c.model_dump_json() == before and c.profile.people[0].name == "Anna Sample"
    assert clean is not c and clean.profile is not c.profile and clean.profile.people is not c.profile.people


def test_redacted_does_not_run_the_checks_of_the_model():
    c = private_case()
    c.profile.household_size = 0  # as tests and repairs may set it
    assert verifier.redacted(c).profile.household_size == 0


def test_redacted_with_nobody_is_an_empty_list():
    assert verifier.redacted(family()).profile.people == []


# --- review_body ---------------------------------------------------------------------------------

def body_case():
    c = family(paper("S1", row(1, code="59409", patient_responsibility=Decimal("10.00")), patient="PATIENT_1",
                     patient_balance=Decimal("10.00")), letterhead="Hospital", today=date(2026, 6, 15))
    c.profile.people = [Person(token="PATIENT_1", role=Role.MOTHER, name="Anna Sample", birth_date="03/14/1994")]
    c.profile.local = LocalDetails(street="100 Example Street", tokens={"ACCT_1": "LDH-000123"})
    return c


def body_report():
    ref = f"{MEMORIAL}#tier-200"
    first = finding(Kind.E1, at("S1", 1, "the bill"), amount="1.50", deadline=date(2026, 9, 2), refs=[ref],
                    math={"zeta": "1", "why_unsure": "kept out", "alpha": "2"})
    return report(first, finding(Kind.E1), finding(Kind.F2, at("S1")), total="1.50")


def payload_of(body):
    return body["input"][1]["content"][0]["text"]


def test_review_body_is_the_exact_request_for_muse_wonder():
    body = verifier.review_body(body_case(), body_report(), [])
    payload = body["input"][1]["content"][0].pop("text")
    assert body == {
        "model": "muse-wonder-1.0", "store": False, "stream": True, "reasoning": {"effort": "medium"},
        "max_output_tokens": 19000,
        "text": {"format": {"type": "json_schema", "name": "billradar_review", "schema": verifier.REVIEW_SCHEMA, "strict": True}},
        "input": [{"role": "developer", "content": [{"type": "input_text", "text": verifier.REVIEW_INSTRUCTIONS}]},
                  {"role": "user", "content": [{"type": "input_text"}]}]}
    assert list(body) == ["model", "store", "stream", "reasoning", "max_output_tokens", "text", "input"]
    assert isinstance(payload, str)


def test_review_body_payload_is_exact_to_the_byte_key_order_included():
    c = body_case()
    pol = policy.load(MEMORIAL)
    quote = pol.fragment("tier-200")
    table = [{"up_to_percent_of_guideline": t.max_fpl_pct, "discount_percent": t.discount_pct,
              "quote": f"{MEMORIAL}#{t.fragment}"} for t in pol.tiers]
    expected = {
        "case": {
            "letterhead": "Hospital", "policy_id": MEMORIAL, "today": "2026-06-15", "demo": False,
            "profile": {
                "household_size": 4, "annual_income": "50000", "liquid_assets": None, "insured": True,
                "people": [{"token": "PATIENT_1", "role": "mother", "name": "", "birth_date": "", "relationship": "",
                            "employer": ""}],
                "context": [], "plan": None},
            "documents": json.loads(c.model_dump_json())["documents"]},
        "reference": {
            "federal_poverty_guideline": {
                "year": 2026, "household_size": 4, "amount": "33000",
                "source": "HHS poverty guidelines 2026, 48 contiguous states and DC, 91 FR 1797 (January 15, 2026)",
                "annual_income": "50000", "percent_of_guideline": "151.5"},
            "policy_discount_table": table},
        "findings": [
            {"subject": "E1 #1 on S1", "title": "E1 title", "detail": "E1 detail", "amount": "1.50",
             "deadline": "2026-09-02", "evidence": [{"doc_id": "S1", "line_no": 1, "note": "the bill"}],
             "math": {"zeta": "1", "alpha": "2"},
             "quotes": [{"ref": f"{MEMORIAL}#tier-200", "page": quote.page, "text": quote.quote}]},
            {"subject": "E1 #2", "title": "E1 title", "detail": "E1 detail", "amount": None, "deadline": None,
             "evidence": [], "math": {}, "quotes": []},
            {"subject": "F2 #1 on S1", "title": "F2 title", "detail": "F2 detail", "amount": None, "deadline": None,
             "evidence": [{"doc_id": "S1", "line_no": None, "note": ""}], "math": {}, "quotes": []}],
        "letters": []}
    assert payload_of(verifier.review_body(c, body_report(), [])) == json.dumps(expected)


def test_review_body_never_carries_a_name_or_a_real_account_number():
    c = private_anna()
    text_sent = json.dumps(verifier.review_body(c, checks.run(c), ["any"]))
    for private in ("Anna Sample", "03/14/1994", "100 Example Street", "LDH-000123", "Sample Bakery LLC"):
        assert private not in text_sent
    plain = "".join(p.text for x in writer.all_letters(c, checks.run(c)) for p in x.paragraphs)
    assert "Anna Sample" in plain or "LDH-000123" in plain  # must differ: the letters to the family do carry them


def test_review_body_leaves_out_the_case_id_and_the_local_details_key():
    c = json.loads(payload_of(verifier.review_body(body_case(), body_report(), [])))["case"]
    assert "case_id" not in c and "local" not in c["profile"]


def test_review_body_rebuilds_the_letters_from_the_redacted_case():
    c = private_anna()
    r = checks.run(c)
    built = writer.all_letters(verifier.redacted(c), r)
    sent = json.loads(payload_of(verifier.review_body(c, r, ["only its being there counts"])))["letters"]
    assert sent == [{"subject": f"letter {x.kind}", "text": [p.text for p in x.paragraphs], "quotes": x.refs} for x in built]
    assert len(sent) == 4


def test_review_body_with_no_letters_sends_none_and_does_not_build_them(monkeypatch):
    def refuse(case, report):
        raise AssertionError("letters were built")
    monkeypatch.setattr(writer, "all_letters", refuse)
    assert json.loads(payload_of(verifier.review_body(body_case(), body_report(), [])))["letters"] == []


def test_review_body_sends_only_the_shown_findings():
    r = body_report()
    r.held_back = [finding(Kind.F1)]
    r.no_money = [finding(Kind.NM)]
    r.worth_asking = [finding(Kind.A1)]
    subjects_sent = [f["subject"] for f in json.loads(payload_of(verifier.review_body(body_case(), r, [])))["findings"]]
    assert subjects_sent == ["E1 #1 on S1", "E1 #2", "F2 #1 on S1"]


def test_review_body_prints_a_sum_of_zero_as_a_sum():
    r = report(finding(Kind.E1, amount="0.00"))
    assert json.loads(payload_of(verifier.review_body(body_case(), r, [])))["findings"][0]["amount"] == "0.00"


def test_review_body_takes_the_year_from_the_policy_or_else_the_latest(monkeypatch):
    windowed(monkeypatch, {}, fpg_year=None, tiers=[policy.Tier(100, 50, "a")])
    reference = json.loads(payload_of(verifier.review_body(body_case(), report(), [])))["reference"]
    assert reference["federal_poverty_guideline"]["year"] == 2026
    assert reference["policy_discount_table"] == [
        {"up_to_percent_of_guideline": 100, "discount_percent": 50, "quote": "made-up#a"}]


def test_review_body_a_guideline_year_without_a_source_has_an_empty_source(monkeypatch):
    monkeypatch.setitem(fpl.GUIDELINES, 2030, {"base": [1000] * 8, "each_extra": 1})
    windowed(monkeypatch, {}, fpg_year=2030)
    reference = json.loads(payload_of(verifier.review_body(body_case(), report(), [])))["reference"]
    assert reference["federal_poverty_guideline"]["source"] == "" and reference["federal_poverty_guideline"]["amount"] == "1000"


def test_review_body_of_the_demo_case_keeps_its_request_key():
    c = anna()
    r = checks.run(c)
    assert meta_client.request_key(verifier.review_body(c, r, writer.all_letters(c, r))) == "5e695f52f409b0e25962"


@pytest.mark.parametrize("ref,error", [(MEMORIAL, IndexError), (f"{MEMORIAL}#no-such", KeyError), ("no-such#x", FileNotFoundError), ("no-hash", FileNotFoundError)])
def test_review_body_a_bad_quote_reference_stops_it(ref, error):
    with pytest.raises(error):
        verifier.review_body(body_case(), report(finding(Kind.E1, refs=[ref])), [])


def test_review_body_reads_only_the_second_part_of_a_reference_with_two_hashes():
    good = verifier.review_body(body_case(), report(finding(Kind.E1, refs=[f"{MEMORIAL}#window#extra"])), [])
    assert json.loads(payload_of(good))["findings"][0]["quotes"][0]["ref"] == f"{MEMORIAL}#window#extra"


# --- model_review --------------------------------------------------------------------------------

class Answer:
    """An in-memory stand-in for the client: it remembers the request and gives the text it was told to."""

    def __init__(self, answer):
        self.text = answer if isinstance(answer, str) else json.dumps(answer)
        self.calls = []

    def respond(self, body, label=""):
        self.calls.append((body, label))
        return type("Result", (), {"text": self.text})()


def review(items, case=None, verdict=None):
    client = Answer({"items": items})
    v = verdict or Verdict()
    case = case or family(paper("S10"), paper("D1"))
    return verifier.model_review(client, case, report(), [], v)


def test_model_review_sends_the_review_body_under_its_label_once():
    c, r = body_case(), body_report()
    client = Answer({"items": []})
    verifier.model_review(client, c, r, [], Verdict())
    assert client.calls == [(verifier.review_body(c, r, []), "wonder:review")]


def test_model_review_passes_the_letters_on():
    c = private_anna()
    r = checks.run(c)
    client = Answer({"items": []})
    verifier.model_review(client, c, r, ["any"], Verdict())
    assert client.calls[0][0] == verifier.review_body(c, r, ["any"]) and client.calls[0][0] != verifier.review_body(c, r, [])


def test_model_review_adds_to_the_verdict_it_was_given_and_returns_it():
    v = Verdict(issues=[Issue("x", "error", "kept")], checked=3)
    assert review([{"subject": "F1 #1", "verdict": "problem", "reason": "off"}], verdict=v) is v
    assert v.checked == 3 and issues(v) == [("x", "error", "kept"), ("F1 #1", "note", "Muse Wonder: off")]


def test_model_review_keeps_every_answer_and_turns_only_problems_into_notes():
    items = [{"subject": "A", "verdict": "confirmed", "reason": "S10 does not exist"},
             {"subject": "B", "verdict": "cannot_tell", "reason": "D1 is missing from the case"},
             {"subject": "C", "verdict": "problem", "reason": "wrong sum"}]
    v = review(items)
    assert v.model_notes == items and issues(v) == [("C", "note", "Muse Wonder: wrong sum")]


def test_model_review_overrules_a_problem_that_calls_a_present_paper_missing():
    v = review([{"subject": "E2 #1 on S10", "verdict": "problem", "reason": "Sheet S10 does not exist in the case."}])
    assert v.model_notes == [{"subject": "E2 #1 on S10", "verdict": "overruled", "reason": "Sheet S10 does not exist in the case.",
                              "code_check": "S10 is in the case: the second read was wrong here"}]
    assert issues(v) == [("E2 #1 on S10", "note", "Muse Wonder said S10 does not exist; it does (checked by code)")]


def test_model_review_names_several_present_papers_in_sorted_order():
    reason = "S10 does not exist; D1 is missing from the case"
    v = review([{"subject": "A", "verdict": "problem", "reason": reason}])
    assert v.model_notes[0]["code_check"] == "D1, S10 is in the case: the second read was wrong here"
    assert issues(v) == [("A", "note", "Muse Wonder said D1, S10 does not exist; it does (checked by code)")]


def test_model_review_leaves_a_problem_about_a_paper_that_really_is_absent():
    v = review([{"subject": "A", "verdict": "problem", "reason": "S99 does not exist"}])
    assert v.model_notes[0]["verdict"] == "problem" and "code_check" not in v.model_notes[0]
    assert issues(v) == [("A", "note", "Muse Wonder: S99 does not exist")]


def test_model_review_a_mixed_reason_counts_only_the_present_paper():
    v = review([{"subject": "A", "verdict": "problem", "reason": "S99 does not exist; S10 does not exist"}])
    assert v.model_notes[0]["code_check"] == "S10 is in the case: the second read was wrong here"


def test_model_review_fills_in_a_missing_subject_and_reason():
    v = review([{"verdict": "problem"}, {"verdict": "problem", "reason": "S10 does not exist"}])
    assert issues(v) == [("?", "note", "Muse Wonder: "), ("?", "note", "Muse Wonder said S10 does not exist; it does (checked by code)")]


def test_model_review_an_empty_subject_stays_empty_and_only_a_missing_key_becomes_a_question_mark():
    v = review([{"subject": "", "verdict": "problem", "reason": "the sum is wrong"},
                {"verdict": "problem", "reason": "the sum is wrong"}])
    assert [(i.subject, i.severity, i.what) for i in v.issues] == [
        ("", "note", "Muse Wonder: the sum is wrong"), ("?", "note", "Muse Wonder: the sum is wrong")]


def test_model_review_a_note_without_a_verdict_is_only_kept():
    v = review([{"subject": "A"}, {}])
    assert v.model_notes == [{"subject": "A"}, {}] and v.issues == []


def test_model_review_uses_the_name_of_the_model_that_reviews(monkeypatch):
    monkeypatch.setattr(verifier, "checker_name", lambda client: "Other Model")
    v = review([{"subject": "A", "verdict": "problem", "reason": "off"},
                {"subject": "B", "verdict": "problem", "reason": "S10 does not exist"}])
    assert v.checker == "Other Model"
    assert issues(v) == [("A", "note", "Other Model: off"),
                         ("B", "note", "Other Model said S10 does not exist; it does (checked by code)")]


def test_model_review_with_no_items_key_is_no_notes():
    client = Answer({})
    v = Verdict(model_notes=[{"old": 1}])
    verifier.model_review(client, family(), report(), [], v)
    assert v.model_notes == [] and v.issues == []


def test_model_review_a_broken_answer_is_a_value_error_with_nothing_kept():
    v = Verdict()
    with pytest.raises(json.JSONDecodeError):
        verifier.model_review(Answer("not json"), family(), report(), [], v)
    assert v.model_notes == [] and v.issues == []


def test_model_review_an_answer_that_is_no_object_is_an_attribute_error():
    with pytest.raises(AttributeError):
        verifier.model_review(Answer("[1]"), family(), report(), [], Verdict())


def test_model_review_a_failed_call_passes_through_with_the_checker_already_named(monkeypatch):
    class Down:
        def respond(self, body, label=""):
            raise MetaAPIError("HTTP 503: SYNTHETIC outage")

    monkeypatch.setattr(verifier, "checker_name", lambda client: "Other Model")
    v = Verdict()
    with pytest.raises(MetaAPIError):
        verifier.model_review(Down(), family(), report(), [], v)
    assert v.checker == "Other Model" and v.model_notes == []
