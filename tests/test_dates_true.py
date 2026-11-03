"""A date on the screen is the date that binds this family, and a date gone by is said to be gone.

Classes D1..D8, S4, S5 of MONEY-AUDIT-2026-10-31, dates worked out by hand. All cases are SYNTHETIC.
Memorial's window: 365 days after service, 12 months after the last insurance payment; federal: 240 days after the
first bill; the latest of them counts."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from billradar import agent_api
from billradar import app as app_module
from billradar import bill_picture, callprep, checks, days, finding_text, i18n, laws, pipeline, report_pdf, view, writer
from billradar.case import Case, DocKind, Document, Line, Person, Profile, Role, Source
from billradar.checks import Kind
from billradar.policies import source
from tests import test_appeal

needs_text = pytest.mark.skipif(not all(source.is_cached(p) for p in source.SOURCES),
                                reason="run scripts/fetch_policies.py first")
HOSPITAL = "Seaside Regional Hospital"
T = date(2026, 10, 30)


def make(*docs: Document, today=T, context=()) -> Case:
    prof = Profile(household_size=4, annual_income=Decimal(85000), liquid_assets=Decimal(6000), insured=True,
                   context=list(context), people=[Person(token="PATIENT_1", role=Role.MOTHER, name="Anna Sample"),
                                                  Person(token="PATIENT_2", role=Role.NEWBORN)])
    return Case(case_id="t", policy_id="memorial-2026-05", today=today, profile=prof, documents=list(docs), letterhead=HOSPITAL)


def stay(doc_id, service: date, bill_date: date, balance="3000.00", **kw) -> Document:
    return Document(doc_id=doc_id, source=Source.PAPER, kind=DocKind.HOSPITAL_STATEMENT, patient="PATIENT_1", provider=HOSPITAL,
                    account_ref=f"[ACCT_{doc_id[1:]}]", statement_date=bill_date, service_from=service, service_to=service,
                    patient_balance=Decimal(balance), **kw)


def plan_paper(doc_id, service: date, code="0110", provider=HOSPITAL, **kw) -> Document:
    return Document(doc_id=doc_id, source=Source.PAPER, kind=DocKind.EOB, patient="PATIENT_1", provider=provider,
                    lines=[Line(line_no=1, service_date=service, code=code, charges=Decimal(900),
                                patient_responsibility=Decimal(0))], **kw)


def f2(report) -> checks.Finding:
    return next(f for f in report.findings + report.worth_asking if f.kind == Kind.F2)


BIRTH = date(2025, 11, 22)    # +365 = 2026-11-22
LABS = date(2026, 9, 15)      # +365 = 2027-09-15


# --- D1: each stay has its own window --------------------------------------------------------

@needs_text
def test_the_date_is_the_nearest_open_window_not_the_last_visit():
    case = make(stay("S1", BIRTH, date(2026, 3, 1)), stay("S2", LABS, date(2026, 9, 25), "900.00"))
    report = checks.run(case)
    assert f2(report).deadline == date(2026, 11, 22)
    assert f2(report).evidence[0].doc_id == "S1"
    assert "Sep 15, 2027" in f2(report).detail  # the later bill's date is said, not lost
    shown, verdict = pipeline.check_and_hold(case, report)
    assert shown.apply_by == date(2026, 11, 22) and verdict.ok, verdict.issues


@needs_text
def test_a_stay_with_nothing_left_to_pay_gives_no_date():
    report = checks.run(make(stay("S1", BIRTH, date(2026, 3, 1), "0.00"), stay("S2", LABS, date(2026, 9, 25), "900.00")))
    assert f2(report).deadline == date(2027, 9, 15)


@needs_text
def test_a_window_gone_by_gives_way_to_an_open_one():
    report = checks.run(make(stay("S1", date(2024, 1, 10), date(2024, 3, 1)), stay("S2", LABS, date(2026, 9, 25), "900.00")))
    assert f2(report).deadline == date(2027, 9, 15)


@needs_text
def test_when_every_window_has_passed_the_latest_is_shown():
    report = checks.run(make(stay("S1", date(2024, 1, 10), date(2024, 3, 1))))
    assert f2(report).deadline == date(2025, 1, 10)


# --- D2: the hospital's payment for this stay ------------------------------------------------

def paid(when: date, **kw) -> Document:
    return plan_paper("S2", kw.pop("service", BIRTH), insurance_payment_date=when, **kw)


@needs_text
@pytest.mark.parametrize("paper,want", [
    (paid(date(2026, 8, 20)), date(2027, 8, 20)),                                      # the hospital's claim, this stay
    (paid(date(2026, 8, 20), provider="Coastal Anesthesia", code="01960"), BIRTH + timedelta(days=365)),  # a doctor's EOB
    (paid(date(2026, 8, 20), service=date(2026, 5, 3)), BIRTH + timedelta(days=365)),  # the hospital, another stay
])
def test_only_the_hospitals_payment_for_this_stay_moves_the_date(paper, want):
    case = make(stay("S1", BIRTH, date(2026, 3, 1)), paper)
    report = checks.run(case)
    assert f2(report).deadline == want
    assert pipeline.check_and_hold(case, report)[1].ok


# --- D7: a date that cannot be right ---------------------------------------------------------

def test_a_date_after_today_is_dropped_and_said():
    doc = stay("S1", BIRTH, date(2026, 12, 5))
    case = checks.plausible_dates(make(doc))
    assert case.doc("S1").statement_date is None
    assert any("2026-12-05" in x for x in case.doc("S1").doubts)
    assert doc.statement_date == date(2026, 12, 5)  # the reading itself stays as it was


def test_a_line_date_after_today_is_dropped():
    doc = stay("S1", BIRTH, date(2026, 3, 1), lines=[Line(line_no=1, service_date=date(2027, 1, 1), code="99213")])
    assert checks.plausible_dates(make(doc)).doc("S1").lines[0].service_date is None


def test_a_bill_dated_before_its_own_service_is_a_doubt():
    doc = stay("S1", date(2026, 6, 1), date(2026, 3, 1))
    assert checks.plausible_dates(make(doc)).doc("S1").doubts


def test_dates_that_fit_are_left_alone():
    doc = stay("S1", BIRTH, date(2026, 3, 1))
    assert checks.plausible_dates(make(doc)).doc("S1") == doc


@needs_text
def test_a_doubted_date_is_not_a_confirmed_deadline():
    report = checks.run(make(stay("S1", BIRTH, date(2026, 12, 5))))
    assert not [f for f in report.findings if f.kind in (Kind.F1, Kind.F2)]


def test_the_pipeline_asks_for_a_new_photo_of_a_sheet_with_a_date_from_the_future():
    case = checks.plausible_dates(make(stay("S1", BIRTH, date(2026, 12, 5))))
    assert pipeline.unreadable_sheets(case.documents) == ["S1"]


# --- D8: 180 days is for employer plans ------------------------------------------------------

def denied_eob(provider="Atlas Marketplace Plan") -> Document:
    return Document(doc_id="S2", source=Source.PAPER, kind=DocKind.EOB, patient="PATIENT_1", provider=provider,
                    statement_date=date(2026, 8, 15),
                    lines=[Line(line_no=1, service_date=date(2026, 7, 1), code="99213", charges=Decimal(500),
                                insurance_paid=Decimal(0), patient_responsibility=Decimal(500), denial_codes="X17")])


@needs_text
def test_an_appeal_date_is_given_only_for_an_employer_plan():
    a1 = next(f for f in checks.run(make(denied_eob(), context=["employer_plan"])).findings if f.kind == Kind.A1)
    assert a1.deadline == date(2027, 2, 11)  # 2026-08-15 + 180 days


@needs_text
def test_with_the_plan_unknown_there_is_no_appeal_date():
    report = checks.run(make(denied_eob()))
    assert not [f for f in report.findings if f.kind == Kind.A1]
    a1 = next(f for f in report.worth_asking if f.kind == Kind.A1)
    assert a1.deadline is None
    assert "ask your plan" in a1.detail.lower()


def test_the_law_card_gives_no_appeal_date_for_an_unknown_plan():
    cards = {c.id: c for c in laws.for_case(make(denied_eob())).cards}
    assert cards["appeal-180-days"].deadline is None
    cards = {c.id: c for c in laws.for_case(make(denied_eob(), context=["employer_plan"])).cards}
    assert cards["appeal-180-days"].deadline == date(2027, 2, 11)


# --- D3, S4: a date gone by is never said to be open -----------------------------------------

def passed_case() -> Case:
    return make(stay("S1", date(2024, 1, 10), date(2024, 3, 1)))


def open_case() -> Case:
    return make(stay("S1", BIRTH, date(2026, 3, 1)))


@needs_text
def test_the_application_letter_does_not_claim_a_passed_window():
    case = passed_case()
    text = " ".join(p.text for p in writer.application(case, checks.run(case)).paragraphs)
    assert "applying before" not in text
    assert "January 10, 2025" in text and "late" in text


@needs_text
def test_the_application_letter_for_an_open_window_says_before():  # must light
    case = open_case()
    assert "applying before November 22, 2026" in " ".join(p.text for p in writer.application(case, checks.run(case)).paragraphs)


@needs_text
def test_the_call_sheet_does_not_say_there_is_still_time():
    case = passed_case()
    sheet = callprep.build(case, checks.run(case), "hospital")
    answers = " ".join(o.answer for o in sheet.objections)
    assert "I can apply until" not in answers
    assert "January 10, 2025" in answers


@needs_text
def test_the_call_sheet_for_an_open_window_gives_the_date():  # must light
    case = open_case()
    assert "I can apply until November 22, 2026" in " ".join(o.answer for o in callprep.build(case, checks.run(case), "hospital").objections)


def late_appeal() -> Case:
    return test_appeal.case().model_copy(update={"today": date(2028, 1, 1)})


@needs_text
def test_the_appeal_letter_does_not_claim_a_passed_window():
    case = late_appeal()
    text = " ".join(" ".join(p.text for p in x.paragraphs) for x in writer.appeal_letters(case))
    assert text and "sending this appeal before" not in text


@needs_text
def test_the_insurer_call_sheet_does_not_say_there_is_still_time():
    case = late_appeal()
    answers = " ".join(o.answer for o in callprep.build(case, checks.run(case), "insurer").objections)
    assert "I can appeal until" not in answers


# --- D4: one word for "passed" on every surface ----------------------------------------------

def rows(case: Case, report) -> dict:
    return {r.kind: r for r in view.board(case, report, {}).rows}


@needs_text
def test_the_screen_says_the_date_has_passed():
    case = passed_case()
    row = rows(case, checks.run(case))["F2"]
    assert "passed" in row.caption.lower()
    assert not row.title.lower().startswith("apply by")


@needs_text
def test_the_screen_keeps_the_plain_words_for_an_open_date():  # must light
    case = open_case()
    assert rows(case, checks.run(case))["F2"].caption == "Last day to apply"


@needs_text
@pytest.mark.parametrize("lang,word", [("ru", "прошёл"), ("es", "pasó")])
def test_translations_say_it_too(lang, word):
    case = passed_case()
    title, _ = finding_text.text(f2(checks.run(case)), case, lang)
    assert word in title


@needs_text
@pytest.mark.parametrize("lang", ["en", "es", "ru"])
def test_the_pdf_says_it_too(lang):
    from pypdf import PdfReader
    import io
    case = passed_case()
    report = checks.run(case)
    text = " ".join(p.extract_text() for p in PdfReader(io.BytesIO(report_pdf.build(case, report, lang=lang))).pages)
    assert i18n.t("report.apply_by", lang, date=i18n.date_text(report.apply_by, lang)) not in text


@needs_text
def test_the_picture_does_not_offer_a_passed_date():
    case = passed_case()
    assert len(bill_picture.labels(case, checks.run(case))) == 2  # the sum and the letters, no date


@needs_text
def test_the_picture_gives_an_open_date():  # must light
    case = open_case()
    assert len(bill_picture.labels(case, checks.run(case))) == 3


@needs_text
def test_the_calendar_file_has_no_date_gone_by():
    case = passed_case()
    assert app_module.case_dates(case, checks.run(case)) == []


def agent_case(tmp_path, monkeypatch, case: Case):
    monkeypatch.setattr(agent_api, "RUNS", tmp_path)
    d = tmp_path / "a0123456789ab"
    d.mkdir()
    (d / "case.json").write_text(case.model_dump_json())
    (d / "report.json").write_text(checks.run(case).model_dump_json())


@needs_text
def test_agents_get_a_passed_flag(tmp_path, monkeypatch):
    agent_case(tmp_path, monkeypatch, passed_case())
    (row, *_) = agent_api.get_deadlines("a0123456789ab")["deadlines"]
    assert row["passed"] is True


# --- D5, D6: today is the day it is shown, not the day it was read ---------------------------

def saved(tmp_path, monkeypatch, case: Case) -> None:
    monkeypatch.setattr(app_module, "RUNS", tmp_path)
    d = tmp_path / case.case_id
    d.mkdir()
    (d / "case.json").write_text(case.model_dump_json())
    (d / "report.json").write_text(checks.run(case).model_dump_json())
    (d / "problems.json").write_text("{}")


@needs_text
def test_a_saved_case_opens_on_todays_date(tmp_path, monkeypatch):
    saved(tmp_path, monkeypatch, open_case())
    monkeypatch.setattr(app_module, "_today", lambda case_id, case: date(2026, 11, 18))
    assert app_module._load("t")[1].today == date(2026, 11, 18)


@needs_text
def test_a_stored_finding_holds_no_day_count():
    report = checks.run(open_case())
    assert "days left" not in f2(report).detail


@needs_text
def test_days_left_are_counted_when_shown():
    case = open_case()
    report = checks.run(case)
    later = case.model_copy(update={"today": date(2026, 11, 20)})
    assert "2 days left" in rows(later, report)["F2"].full


def test_the_words_for_time_left():
    assert days.left(date(2026, 11, 22), date(2026, 11, 20)) == "2 days left."
    assert days.left(date(2026, 11, 22), date(2026, 11, 21)) == "1 day left."
    assert days.left(date(2026, 11, 22), date(2026, 11, 22)) == "Today is the last day."
    assert "passed" in days.left(date(2026, 11, 22), date(2026, 11, 23))


@needs_text
def test_a_letter_is_dated_the_day_it_is_shown():
    case = open_case()
    letter = writer.application(case, checks.run(case))
    later = case.model_copy(update={"today": date(2026, 11, 20)})
    assert writer.plain_text(letter, later).startswith("November 20, 2026")


# --- S5: the insurer sheet, denial by denial -------------------------------------------------

def two_denials() -> Case:
    base = test_appeal.case()
    (bill, first) = base.documents
    second = first.model_copy(deep=True)
    second.doc_id = "S3"
    second.statement_date = date(2026, 4, 20)
    second.lines = [second.lines[0].model_copy(update={"claim_ref": "CLM-2", "denial_codes": "P31"})]
    return base.model_copy(update={"documents": [bill, second, first]})


@needs_text
def test_the_insurer_sheet_gives_each_denial_its_own_code_and_the_earliest_date_first():
    case = two_denials()
    report = checks.run(case)
    sheet = callprep.build(case, report, "insurer")
    assert "CLM-2" in sheet.say_first and "CLM-7765301" in sheet.say_first
    late = [o for o in sheet.objections if o.they_say == "It's too late to appeal."]
    assert len(late) >= 2
    assert "CLM-2" in late[0].answer  # the denial of April comes first: it runs out first
