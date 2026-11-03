"""What the family reads says one thing, about their own papers, and shows no sum we do not stand behind.

Items of the strict read of the site, the display lens of the money audit
(S1-S3, S6, S7, R4) and the lens items that had not been checked. All cases are SYNTHETIC."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from billradar import app as app_module
from billradar import appeal, callprep, checks, explain, laws, report_pdf, verifier, view, writer
from billradar.case import Case, DocKind, Document, Line, Person, Profile, Role, Source
from billradar.checks import Evidence, Finding, Kind
from billradar.policies import source
from tests import test_appeal

needs_text = pytest.mark.skipif(not all(source.is_cached(p) for p in source.SOURCES), reason="run scripts/fetch_policies.py first")
HOSPITAL = "Seaside Regional Hospital"
OFFICE = "Women First OB/GYN"
D = date(2025, 8, 4)


def make(*docs: Document, income="85000", liquid: str | None = "6000", size=4, today=date(2026, 3, 1), people=None) -> Case:
    prof = Profile(household_size=size, annual_income=Decimal(income), insured=True,
                   liquid_assets=Decimal(liquid) if liquid is not None else None,
                   people=people or [Person(token="PATIENT_1", role=Role.MOTHER, name="Anna Sample"),
                                     Person(token="PATIENT_2", role=Role.NEWBORN, name="Leo Sample")])
    return Case(case_id="t", policy_id="memorial-2026-05", today=today, profile=prof, documents=list(docs), letterhead=HOSPITAL)


def L(n, code, charges, share, **kw) -> Line:
    return Line(line_no=n, service_date=kw.pop("service_date", D), code=code, charges=Decimal(charges),
                patient_responsibility=Decimal(share) if share is not None else None, **kw)


def paper(doc_id, kind=DocKind.HOSPITAL_STATEMENT, patient="PATIENT_1", provider=HOSPITAL, **kw) -> Document:
    for k in ("patient_balance", "amount_due_coupon", "due_from_insurance", "fa_discount", "insurance_paid"):
        if isinstance(kw.get(k), str):
            kw[k] = Decimal(kw[k])
    return Document(doc_id=doc_id, source=Source.PAPER, kind=kind, patient=patient, provider=provider, **kw)


def text_of(letter: writer.Letter) -> str:
    return " ".join(p.text for p in letter.paragraphs)


# --- 30: the same line is not "dispute it" and "nothing to dispute" ---------------------------

@needs_text
def test_a_line_with_a_finding_is_never_said_to_be_nothing_to_dispute():
    case = test_appeal.case()
    report = checks.run(case)
    flagged = {(e.doc_id, e.line_no) for f in report.findings + report.worth_asking for e in f.evidence if e.line_no}
    assert flagged  # must light: the sample case has an appeal on a line
    for note in report.no_money:
        assert not ({(e.doc_id, e.line_no) for e in note.evidence if e.line_no} & flagged), note.title


@needs_text
def test_a_clean_line_still_says_it_matches():  # must light for the test above
    bill = paper("S1", provider=OFFICE, patient_balance="100.00", lines=[L(1, "99213", "500.00", "100.00", claim_ref="C1")])
    plan = paper("S2", DocKind.EOB, provider="Plan", lines=[L(1, "99213", "500.00", "100.00", claim_ref="C1")])
    assert any("matches your insurance statement" in f.title for f in checks.run(make(bill, plan)).no_money)


# --- 31: an address is not a name -------------------------------------------------------------

@needs_text
def test_the_appeal_greeting_has_no_address():
    case = test_appeal.case()
    letter = writer.appeal_letters(case)[0]
    assert writer.greeting(letter) == "Dear Sample Health Plan appeals team,"
    assert "PO Box" in writer.plain_text(letter, case)  # must light: the address stays where an address goes


@pytest.mark.parametrize("to,want", [
    ("Patient Financial Services, Seaside Regional Hospital", "Dear Patient Financial Services team,"),
    ("Billing office, Women First OB/GYN", "Dear Women First OB/GYN billing team,"),
])
def test_other_greetings_stay_as_they_are(to, want):
    assert writer.greeting(writer.Letter(kind="x", button="b", to=to, subject="s", paragraphs=[])) == want


# --- 32: the rules line names this case, and only where the rules apply ----------------------

def demo(case: Case) -> Case:
    return case.model_copy(update={"demo": True})


@needs_text
def test_the_rules_line_names_the_hospital_of_this_case():
    case = demo(test_appeal.case())
    hospital_letter = writer.all_letters(case, checks.run(case))[0]
    line = writer.demo_rules(case, hospital_letter)
    assert "Seaside" not in line and case.letterhead in line


@needs_text
def test_an_appeal_to_the_plan_carries_no_hospital_rules_line():
    case = demo(test_appeal.case())
    assert writer.demo_rules(case, writer.appeal_letters(case)[0]) == ""


def test_the_pdf_note_names_the_hospital_of_this_case():
    assert "Lakeview" in report_pdf.policy_note(make().model_copy(update={"letterhead": "Lakeview Demo Hospital"}), "en")
    for lang in ("ru", "es"):
        assert "Seaside" not in report_pdf.policy_note(make().model_copy(update={"letterhead": "Lakeview"}), lang)


# --- 33: an appeal attaches what the family has, and speaks the plan's language ---------------

@needs_text
def test_an_appeal_attaches_an_itemized_bill_only_when_there_is_one():
    case = test_appeal.case()
    assert not any(d.kind == DocKind.ITEMIZED_BILL for d in case.documents)
    letter = writer.appeal_letters(case)[0]
    assert not any("temized" in a for a in letter.attachments)


@needs_text
def test_an_appeal_with_an_itemized_bill_attaches_it():
    case = test_appeal.case()
    case.documents.append(paper("S9", DocKind.ITEMIZED_BILL, provider=case.letterhead))
    assert any("temized" in a for a in writer.appeal_letters(case)[0].attachments)


@needs_text
def test_a_letter_to_the_plan_does_not_name_our_sheet_numbers():
    letter = writer.appeal_letters(test_appeal.case())[0]
    assert "sheet S" not in " ".join(letter.attachments) + text_of(letter)
    assert "October 15, 2026" in " ".join(letter.attachments)


# --- 6: a plain line that agrees with its finding ---------------------------------------------

@needs_text
def test_a_credit_already_inside_the_coupon_is_not_called_money_back():
    bill = paper("S1", provider=OFFICE, account_ref="[A]", amount_due_coupon="60.00", patient_balance="60.00",
                 lines=[L(1, "99213", "150.00", "100.00"), L(2, "99214", "90.00", "-40.00")])
    (f,) = [x for x in checks.run(make(bill)).worth_asking if x.kind == Kind.E3]
    assert "come back" not in f.explain and "not extra money" in f.explain
    case = make(bill)
    row = view.row(f, case, case.policy_id, {})
    assert row.caption == "Check it stays taken off"


@pytest.mark.parametrize("kind", [Kind.E1, Kind.E2, Kind.E3, Kind.N1, Kind.C1, Kind.C2, Kind.F1, Kind.F3])
def test_no_doubted_finding_is_told_to_ask_for_the_itemized_bill(kind):
    case = make(paper("S1"))
    f = Finding(kind=kind, title="t", detail="d", severity="borderline", evidence=[Evidence(doc_id="S1")])
    assert view.row(f, case, case.policy_id, {}).caption != "Ask for the itemized bill"


# --- 1: we answer for what BillRadar does with a voice, not for what the model's owner keeps --

def test_the_voice_note_promises_only_what_billradar_does():
    said = {p.name: p.read_text(encoding="utf-8") for p in (Path(app_module.__file__).parent / "web" / "templates").glob("*.html")}
    assert all("BillRadar doesn't keep the audio" in said[n] for n in ("_voice_card.html", "_story.html"))
    assert not [n for n, text in said.items() if "isn't stored" in text]


# --- 7, 38: one date on the page --------------------------------------------------------------

def test_an_example_lives_on_its_own_day():
    case = make(today=date(2026, 3, 16))
    assert app_module.case_day(case, "2026-10-31T02:00:00+00:00", True) == "Mar 16, 2026"
    assert app_module.case_day(case, "2026-10-31T02:00:00+00:00", False) == "Oct 31, 2026"  # must light


# --- 16: each date names its sheet ------------------------------------------------------------

@needs_text
def test_the_window_says_which_payment_it_counts_from():
    bill = paper("S1", patient_balance="2000.00", statement_date=date(2025, 9, 1), service_from=D, service_to=D, account_ref="[A]")
    plan = paper("S2", DocKind.EOB, statement_date=date(2026, 2, 1),
                 lines=[Line(line_no=1, service_date=D, code="0110", charges=Decimal(900), patient_responsibility=Decimal(0))])
    case = make(bill, plan)
    f2 = next(f for f in checks.run(case).worth_asking if f.kind == Kind.F2)  # the plan's statement stands in for the payment
    assert "sheet 2" in view.short(f2, case, case.policy_id) and "Feb 1, 2026" in view.short(f2, case, case.policy_id)


# --- 17: the law's number is the one that says it ---------------------------------------------

def test_the_appeal_card_cites_both_rules():
    card = next(p for p in laws.registry()["protections"] if p["id"] == "appeal-180-days")
    assert "(h)(3)(i)" in card["cite"] and "(i)(2)(iii)(A)" in card["cite"]


# --- 41, 42: the call sheet -------------------------------------------------------------------

@needs_text
def test_one_account_number_is_one_row():
    stmt = paper("D1", account_ref="5057388214", patient_balance="900.00", statement_date=D, service_from=D)
    item = paper("D2", DocKind.ITEMIZED_BILL, account_ref="5057388214", patient_balance="900.00", statement_date=D, service_from=D)
    case = make(stmt, item)
    numbers = callprep.build(case, checks.run(case), "hospital").numbers
    assert [n.value for n in numbers].count("5057388214") == 1


@needs_text
def test_the_call_opens_with_the_same_days_as_the_case_header():
    a = paper("S1", patient_balance="900.00", statement_date=date(2025, 3, 1), service_from=date(2025, 2, 11), service_to=date(2025, 2, 13))
    b = paper("S2", provider=OFFICE, patient_balance="90.00", statement_date=date(2025, 4, 1), service_from=date(2025, 3, 11))
    case = make(a, b)
    say = callprep.build(case, checks.run(case), "hospital").say_first
    assert "from Feb 11, 2025 to Feb 13, 2025" in say
    assert view.service_span(case) == "Feb 11–13, 2025"  # the hospital's stay, not a doctor's later visit


# --- S1: the PDF headline ---------------------------------------------------------------------

def report_of(total: str) -> checks.Report:
    return checks.Report(case_id="t", policy_id="memorial-2026-05", fpl_pct=Decimal(200), findings=[], no_money=[],
                         held_back=[], total_may_come_off=Decimal(total), apply_by=None)


@pytest.mark.parametrize("total,lang,want", [
    ("2004.30", "en", "$2,004"), ("2004.30", "es", "$2,004"), ("2004.30", "ru", "2\xa0004\xa0$"),
    ("1000.00", "en", "$1,000"), ("10005.00", "en", "$10,005"), ("1100.00", "en", "$1,100"),
    ("0.40", "en", "$0.40"),      # under a dollar: the sum itself, never "$0"
])
def test_the_pdf_headline_keeps_every_digit(total, lang, want):
    assert want in report_pdf.headline(report_of(total), lang)


def test_the_screen_headline_for_less_than_a_dollar():
    assert "$0.40" in view.build(make(), report_of("0.40"), [], True).headline
    assert view.up_to(Decimal("2004.30")) == "$2,004"


# --- S2: a doubted finding shows no sum in its words ------------------------------------------

def over_debt_case() -> Case:
    bill = paper("S1", provider=OFFICE, patient_balance="100.00",
                 lines=[L(1, "99213", "500.00", "90.00", claim_ref="C1"), L(2, "85025", "400.00", "90.00", claim_ref="C2")])
    plan = paper("S2", DocKind.EOB, provider="Plan", lines=[L(1, "99213", "500.00", "10.00", claim_ref="C1"),
                                                            L(2, "85025", "400.00", "10.00", claim_ref="C2")])
    return make(bill, plan)


@needs_text
def test_a_doubted_sum_leaves_the_title_and_the_detail():
    (f,) = [x for x in checks.run(over_debt_case()).worth_asking if x.kind == Kind.E1]
    assert "$" not in f.title and "$" not in f.detail
    assert f.math["amount_if_confirmed"] == "80.00"  # kept for the case data, not for the family's eyes


@needs_text
def test_a_finding_the_checker_doubts_loses_its_sum_too():
    case = over_debt_case()
    report = checks.run(case)
    v = verifier.Verdict(issues=[verifier.Issue(verifier.subject(report.findings[0], 1), "doubt", "line not read")])
    graded = verifier.grade(case, report, v)
    assert all("$" not in f.title for f in graded.worth_asking if f.kind == Kind.E1)


# --- S3: free care needs savings we may not know ----------------------------------------------

def free_care(liquid) -> Case:
    bill = paper("S1", patient_balance="4512.00", statement_date=date(2025, 9, 1), service_from=D, service_to=D, account_ref="[A]")
    return make(bill, income="30000", size=4, liquid=liquid)


@needs_text
def test_free_care_with_savings_unknown_has_no_sum():
    report = checks.run(free_care(None))
    assert report.total_may_come_off == 0
    (f,) = [x for x in report.worth_asking if x.kind == Kind.F1]
    assert "savings" in f.detail and "savings" in f.math["why_unsure"]


@needs_text
def test_free_care_with_savings_known_stands():  # must light
    assert checks.run(free_care("2000")).total_may_come_off == Decimal("4512.00")


# --- S6: a letter for every sum ---------------------------------------------------------------

@needs_text
def test_the_discount_letter_covers_every_account_without_it():
    stay = dict(statement_date=date(2025, 9, 1), service_from=D, service_to=D)
    mom = paper("S1", patient_balance="1000.00", fa_discount="500.00", account_ref="[A]", **stay)
    baby = paper("S2", patient="PATIENT_2", patient_balance="2000.00", account_ref="[B]", **stay)
    nicu = paper("S3", patient="PATIENT_2", patient_balance="3000.00", account_ref="[C]", **stay)
    case = make(mom, baby, nicu)
    report = checks.run(case)
    assert len([f for f in report.findings if f.kind == Kind.F3]) == 2
    text = text_of(writer.apply_discount(case, report))
    assert "$2,000.00" in text and "$3,000.00" in text


# --- S7: the fix for a baby's claim is not an appeal ------------------------------------------

@needs_text
def test_a_claim_that_belongs_under_the_baby_is_not_listed_as_an_appeal():
    case = test_appeal.case()
    assert [d.line_nos for d in appeal.denials(case)] == [[1]]  # must light: an ordinary denial is an appeal
    eob = next(d for d in case.documents if d.kind == DocKind.EOB)
    eob.lines[0].code = "99460"  # newborn care on mom's statement, denied: the fix is a corrected claim
    assert appeal.denials(case) == []


# --- R4: the sheet list and the "We checked every sheet" line ---------------------------------

def test_the_headline_does_not_claim_every_sheet_when_one_was_not_read():
    screen = view.build(make(), report_of("0"), [], True, unreadable=["S5"])
    assert "every sheet" not in screen.headline and "S5"[1:] in screen.headline


# --- the display lens, items that had not been checked ----------------------------------------

@needs_text
def test_lens7_the_discount_card_does_not_print_the_policy_tier_as_the_sheets_number():
    stay = dict(statement_date=date(2025, 9, 1), service_from=D, service_to=D)
    case = make(paper("S1", patient_balance="4000.00", fa_discount="1000.00", account_ref="[A]", **stay),
                paper("S2", patient="PATIENT_2", patient_balance="2000.00", account_ref="[B]", **stay))
    f3 = next(f for f in checks.run(case).findings if f.kind == Kind.F3)
    line = view.short(f3, case, case.policy_id)
    assert "85% off on sheet 1" not in line and "sheet 1" in line and "sheet 2" in line


@needs_text
def test_lens8_a_sum_that_differs_from_the_title_says_why():
    bill = paper("S1", provider=OFFICE, patient_balance="1500.00", fa_discount="500.00",
                 lines=[L(1, "99213", "900.00", "500.00", claim_ref="C1", fa_discount=Decimal("100.00"))])
    plan = paper("S2", DocKind.EOB, provider="Plan", lines=[L(1, "99213", "900.00", "300.00", claim_ref="C1")])
    case = make(bill, plan)
    e1 = next(f for f in checks.run(case).findings if f.kind == Kind.E1)
    assert e1.amount == Decimal("150.00")
    assert "$150 of it is yours" in view.short(e1, case, case.policy_id)


@needs_text
def test_lens8_the_discount_card_quotes_what_the_sheet_asks():
    stay = dict(statement_date=date(2025, 9, 1), service_from=D, service_to=D)
    case = make(paper("S1", patient_balance="4000.00", fa_discount="1000.00", account_ref="[A]", **stay),
                paper("S2", patient="PATIENT_2", patient_balance="2000.00", account_ref="[B]", **stay,
                      lines=[L(1, "01960", "900.00", "300.00"), L(2, "01960", "900.00", "300.00")]))
    f3 = next(f for f in checks.run(case).findings if f.kind == Kind.F3)
    assert "sheet S2 still asks $2,000.00" in f3.detail


@needs_text
def test_lens9_a_share_read_from_the_bill_is_not_credited_to_the_insurance_statement():
    bill = paper("S1", provider=OFFICE, patient_balance="150.00", lines=[L(1, "99213", "400.00", "75.00"), L(2, "99213", "400.00", "75.00")])
    case = make(bill)
    report = checks.run(case)
    text = text_of(writer.dispute(case, report)[0] if isinstance(writer.dispute(case, report), list) else writer.dispute(case, report))
    assert "as my insurance statement shows" not in text and "$75.00" in text


@needs_text
def test_lens12_the_paper_list_does_not_show_what_is_due_from_insurance_as_owed():
    d = paper("D3", patient="PATIENT_2", patient_balance="1341.23", due_from_insurance="1341.23")
    label = view.doc_label(make(d), d)
    assert "$1,341.23 due from insurance" in label


@needs_text
def test_lens13_each_office_gets_its_own_dispute_letter():
    hospital = paper("S3", account_ref="[A]", patient_balance="500.00", lines=[L(1, "0110", "900.00", "100.00"), L(2, "0110", "900.00", "100.00")])
    office = paper("S10", provider=OFFICE, account_ref="[B]", patient_balance="300.00", lines=[L(1, "99213", "400.00", "90.00"), L(2, "99213", "400.00", "90.00")])
    case = make(hospital, office)
    letters = [x for x in writer.all_letters(case, checks.run(case)) if x.kind.startswith("dispute")]
    assert len(letters) == 2 and len({x.kind for x in letters}) == 2
    assert {("Hospital" in x.to or "Patient Financial" in x.to, OFFICE in x.to) for x in letters} == {(True, False), (False, True)}


def test_lens14_a_negative_insurance_payment_reads_as_a_credit():
    text = explain.line(L(1, "0110", "900.00", None, insurance_paid=Decimal("-120.00")))
    assert "$-120" not in text and "$120.00" in text and "credit" in text.lower()


def test_lens12_a_family_who_owes_gets_the_balance_as_before():  # must light
    d = paper("S1", patient_balance="500.00")
    assert "$500" in view.doc_label(make(d), d)


# --- how a sum was worked out: built from its trace -------------------------------------------

@needs_text
def test_a_sum_on_the_screen_says_where_it_comes_from():
    bill = paper("S1", provider=OFFICE, patient_balance="200.00", lines=[L(1, "99213", "500.00", "100.00", claim_ref="C1")])
    plan = paper("S2", DocKind.EOB, provider="Plan", lines=[L(1, "99213", "500.00", "40.00", claim_ref="C1")])
    case = make(bill, plan)
    row = view.row(next(f for f in checks.run(case).findings if f.kind == Kind.E1), case, case.policy_id, {})
    assert row.how == ["Sheet 1, line 1: the bill asks $100.00", "Sheet 2, line 1: your insurance says $40.00"]


def test_a_finding_without_a_sum_shows_no_working():
    case = make(paper("S1"))
    f = Finding(kind=Kind.I1, title="t", detail="d", evidence=[Evidence(doc_id="S1")])
    assert view.row(f, case, case.policy_id, {}).how == []


@needs_text
def test_the_acceptance_table_gives_a_row_for_every_sum(tmp_path):
    from scripts import money_table
    bill = paper("S1", provider=OFFICE, patient_balance="200.00", lines=[L(1, "99213", "500.00", "100.00", claim_ref="C1")])
    plan = paper("S2", DocKind.EOB, provider="Plan", lines=[L(1, "99213", "500.00", "40.00", claim_ref="C1")])
    case = make(bill, plan)
    report = checks.run(case)
    table = money_table.table(report)
    assert "| E1 | $60.00 | S1 line 1 patient_responsibility 100.00: the bill asks" in table
    assert table.count("\n") >= 2 + len([f for f in report.findings if f.amount])


# --- what the site needs from the check, and a label that is not a name --------------------------

def test_the_second_models_verdicts_are_counted_for_the_screen():
    from billradar import pipeline
    v = verifier.Verdict(checked=4, model_notes=[{"verdict": x} for x in ("confirmed", "confirmed", "problem", "cannot_tell")])
    assert pipeline._checker(v)["review"] == {"confirmed": 2, "problem": 1, "cannot_tell": 1}


def test_a_claim_with_nobody_named_says_no_name_rather_than_the_word_patient():
    plan = paper("S7", DocKind.EOB, service_from=D, lines=[Line(line_no=1, service_date=D, code="59410", claim_ref="C-1",
                                                               charges=Decimal(900), patient_responsibility=Decimal(0))])
    plan.patient = "UNKNOWN_9"
    case = make(paper("S1", patient_balance="900.00", statement_date=D, service_from=D, account_ref="A-1"), plan)
    labels = [n.label for n in callprep.build(case, checks.run(case), "hospital").numbers]
    assert not [x for x in labels if " patient " in f" {x} "]


@pytest.mark.parametrize(("lang", "word"), [("ru", "ждём страховую"), ("es", "a la espera del seguro")])
def test_a_bill_waiting_for_insurance_is_told_in_the_familys_language(lang, word):
    from billradar import finding_text
    note = Finding(kind=Kind.NM, title="Sheet D3: waiting for insurance", detail="$1,490.25 is due from insurance, not from you, so "
                   "nothing comes off it yet.", evidence=[Evidence(doc_id="D3")])
    title, detail = finding_text.text(note, make(), lang)
    assert word in title and title.split(":")[0].endswith(" 3") and "1" in detail and "due from insurance" not in detail


def test_an_answer_about_a_questioned_sum_is_told_to_give_both_numbers():
    from billradar import ask, qa_cite
    for text in (ask.INSTRUCTIONS, qa_cite.INSTRUCTIONS):
        assert "what may come off" in text and "finally owes" in text
