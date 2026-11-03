"""Every defect the independent review of 31.10 reproduced, as a class. SYNTHETIC cases, numbers worked out by hand.
Income 85,000 for 4 is 257.6% of the guideline, 85% off at Memorial; 60,000 for 3 is 90% off."""

from datetime import date
from decimal import Decimal

import pytest
import requests
from PIL import Image, ImageDraw, ImageFilter

from billradar import local_reader
from billradar import checks, days, finding_text, ledger, meta_client as mc, open_reader, pdfpages, pipeline, reader
from billradar import reconcile_read, redact, table_rows, view, writer
from billradar.case import Case, DocKind, Document, Line, Person, Profile, Role, Source
from billradar.checks import Finding, Kind
from billradar.policies import source
from billradar.table_rows import Row

needs_text = pytest.mark.skipif(not all(source.is_cached(p) for p in source.SOURCES),
                                reason="run scripts/fetch_policies.py first")
HOSPITAL = "Seaside Regional Hospital"
OFFICE = "Women First OB/GYN"
ANESTHESIA = "Coastal Anesthesia Group"
D = date(2026, 3, 1)
T = date(2026, 10, 31)


def make(*docs, income="85000", size=4, insured=True, context=(), today=T, liquid="6000") -> Case:
    prof = Profile(household_size=size, annual_income=Decimal(income), insured=insured, context=list(context),
                   liquid_assets=Decimal(liquid), people=[Person(token="PATIENT_1", role=Role.MOTHER)])
    return Case(case_id="t", policy_id="memorial-2026-05", today=today, profile=prof, documents=list(docs), letterhead=HOSPITAL)


def L(n, code, charges, share, **kw) -> Line:
    return Line(line_no=n, service_date=kw.pop("service_date", D), code=code, charges=Decimal(charges),
                patient_responsibility=Decimal(share) if share is not None else None, **kw)


def paper(doc_id, kind=DocKind.HOSPITAL_STATEMENT, provider=HOSPITAL, **kw) -> Document:
    for k in ("patient_balance", "amount_due_coupon"):
        if isinstance(kw.get(k), str):
            kw[k] = Decimal(kw[k])
    return Document(doc_id=doc_id, source=Source.PAPER, kind=kind, patient=kw.pop("patient", "PATIENT_1"), provider=provider, **kw)


def eob(doc_id, *lines, **kw) -> Document:
    return paper(doc_id, DocKind.EOB, provider=kw.pop("provider", "Plan"), lines=list(lines), **kw)


def sums(report, kind) -> list:
    return [f.amount for f in report.findings if f.kind == kind]


def asked(report, kind) -> list:
    return [f for f in report.worth_asking if f.kind == kind]


def checked(case: Case) -> checks.Report:
    return pipeline.check_and_hold(case, checks.run(case))[0]


# --- 1, 2: No Surprises ----------------------------------------------------------------------

@needs_text
def test_1_a_doubled_line_is_not_counted_again_in_the_no_surprises_difference():
    bill = paper("S1", provider=ANESTHESIA, patient_balance="400.00", claim_ref="C1",
                 lines=[L(1, "00840", "1000.00", "200.00", claim_ref="C1"), L(2, "00840", "1000.00", "200.00", claim_ref="C1")])
    report = checked(make(bill, eob("S2", L(1, "00840", "1000.00", "200.00", claim_ref="C1")), context=["out_of_network"]))
    assert report.total_may_come_off == Decimal("200.00")
    assert sums(report, Kind.E2) == [Decimal("200.00")] and sums(report, Kind.N1) == []


@needs_text
def test_2_a_claim_with_no_statement_is_not_an_overcharge():
    bill = paper("S1", provider=ANESTHESIA, patient_balance="1000.00",
                 lines=[L(1, "00840", "1000.00", "400.00", claim_ref="C1"), L(2, "01960", "1000.00", "600.00", claim_ref="C2")])
    report = checked(make(bill, eob("S2", L(1, "00840", "1000.00", "400.00", claim_ref="C1")), context=["out_of_network"]))
    assert sums(report, Kind.N1) == [] and asked(report, Kind.N1) and report.total_may_come_off == 0


@needs_text
def test_1b_the_checker_counts_what_came_off_before_the_no_surprises_difference():
    bill = paper("S1", provider=ANESTHESIA, patient_balance="1000.00", claim_ref="C1",
                 lines=[L(1, "00840", "1000.00", "100.00", claim_ref="C1"), L(2, "00840", "1000.00", "100.00", claim_ref="C1")])
    case = make(bill, eob("S2", L(1, "00840", "1000.00", "100.00", claim_ref="C1")), context=["out_of_network"])
    assert not [f for f in checked(case).held_back]  # E2 100 + N1 900 - 100 = 800: both paths agree


# --- 3, 6: what makes one debt ---------------------------------------------------------------

@needs_text
@pytest.mark.parametrize("a,b", [("A-12", "A12"), ("[ACCT_1]", "[ACCT 1]"), ("ab123", "AB123")])
def test_3_one_account_printed_two_ways_is_one_debt(a, b):
    stay = dict(service_from=D, service_to=D)
    case = make(paper("S1", account_ref=a, patient_balance="3000.00", statement_date=date(2026, 3, 20), **stay),
                paper("S2", account_ref=b, patient_balance="2800.00", statement_date=date(2026, 4, 1), **stay),
                income="60000", size=3, insured=False)
    report = checked(case)
    assert report.total_may_come_off == Decimal("2520.00")  # 90% of the newest balance, once


@needs_text
def test_3b_an_itemized_bill_that_adds_up_to_the_statement_is_the_same_debt():
    stay = dict(service_from=D, service_to=D)
    case = make(paper("S1", account_ref="G-77", patient_balance="3000.00", amount_due_coupon="3000.00", statement_date=date(2026, 4, 1), **stay),
                paper("S2", DocKind.ITEMIZED_BILL, account_ref="A-12", statement_date=date(2026, 4, 1),
                      lines=[L(1, "0110", "2000.00", "1000.00"), L(2, "0250", "4000.00", "2000.00")], **stay),
                income="60000", size=3, insured=False)
    assert checked(case).total_may_come_off == Decimal("2700.00")


@needs_text
def test_6_two_stays_with_the_same_balance_are_two_debts():
    case = make(paper("S1", account_ref="A-1", patient_balance="800.00", statement_date=date(2026, 3, 1),
                      service_from=date(2026, 2, 1), service_to=date(2026, 2, 1)),
                paper("S2", account_ref="A-2", patient_balance="800.00", statement_date=date(2026, 8, 1),
                      service_from=date(2026, 7, 1), service_to=date(2026, 7, 1)),
                income="60000", size=3, insured=False)
    assert len(ledger.Book(case).debts) == 2
    assert checked(case).total_may_come_off == Decimal("1440.00")  # 90% of each


# each layer alone: what the checks say before the checker looks, and what the checker says when the checks are wrong

def two_ways_case() -> Case:
    stay_ = dict(service_from=D, service_to=D)
    return make(paper("S1", account_ref="A-12", patient_balance="3000.00", statement_date=date(2026, 3, 20), **stay_),
                paper("S2", account_ref="A12", patient_balance="2800.00", statement_date=date(2026, 4, 1), **stay_),
                income="60000", size=3, insured=False)


def itemized_case() -> Case:
    stay_ = dict(service_from=D, service_to=D)
    return make(paper("S1", account_ref="G-77", patient_balance="3000.00", amount_due_coupon="3000.00", statement_date=date(2026, 4, 1), **stay_),
                paper("S2", DocKind.ITEMIZED_BILL, account_ref="A-12", statement_date=date(2026, 4, 1),
                      lines=[L(1, "0110", "2000.00", "1000.00"), L(2, "0250", "4000.00", "2000.00")], **stay_),
                income="60000", size=3, insured=False)


@needs_text
def test_2_the_checks_alone_give_no_sum_for_a_claim_with_no_statement():
    bill = paper("S1", provider=ANESTHESIA, patient_balance="1000.00",
                 lines=[L(1, "00840", "1000.00", "400.00", claim_ref="C1"), L(2, "01960", "1000.00", "600.00", claim_ref="C2")])
    report = checks.run(make(bill, eob("S2", L(1, "00840", "1000.00", "400.00", claim_ref="C1")), context=["out_of_network"]))
    assert sums(report, Kind.N1) == [] and report.total_may_come_off == 0


@needs_text
def test_3_the_checks_alone_join_an_itemized_bill_to_its_statement():
    assert checks.run(itemized_case()).total_may_come_off == Decimal("2700.00")


@needs_text
def test_3_the_checker_stops_one_account_counted_as_two(monkeypatch):
    monkeypatch.setattr(ledger, "account_key", str.strip)
    monkeypatch.setattr(checks, "account_key", str.strip)
    case = two_ways_case()
    wrong = checks.run(case)
    assert wrong.total_may_come_off == Decimal("5220.00")  # must light: without the key the checks do count it twice
    assert pipeline.check_and_hold(case, wrong)[0].total_may_come_off <= Decimal("2800.00")


@needs_text
def test_3_the_checker_stops_an_itemized_bill_counted_as_a_second_debt(monkeypatch):
    monkeypatch.setattr(ledger, "_adds_up_to", lambda *a: False)
    case = itemized_case()
    wrong = checks.run(case)
    assert wrong.total_may_come_off == Decimal("5400.00")  # must light
    assert pipeline.check_and_hold(case, wrong)[0].total_may_come_off <= Decimal("3000.00")


@needs_text
def test_4_the_checks_alone_give_no_sum_for_a_credit_next_to_a_coupon():
    report = checks.run(make(paper("S1", provider=OFFICE, patient_balance="-50.00", amount_due_coupon="200.00")))
    assert sums(report, Kind.E3) == [] and report.total_may_come_off == 0


# --- 4: credits ------------------------------------------------------------------------------

@needs_text
def test_4_a_credit_next_to_a_coupon_on_the_same_sheet_is_not_money_back():
    report = checked(make(paper("S1", provider=OFFICE, patient_balance="-50.00", amount_due_coupon="200.00")))
    assert sums(report, Kind.E3) == [] and asked(report, Kind.E3) and report.total_may_come_off == 0


@needs_text
def test_4_a_credit_on_an_old_statement_is_gone_when_a_newer_one_asks_money():
    case = make(paper("S1", provider=OFFICE, account_ref="A", patient_balance="-50.00", statement_date=date(2026, 2, 1)),
                paper("S2", provider=OFFICE, account_ref="A", patient_balance="100.00", statement_date=date(2026, 6, 1)))
    assert checked(case).total_may_come_off == 0


@needs_text
def test_4_a_newer_credit_stands():  # must light
    case = make(paper("S1", provider=OFFICE, account_ref="A", patient_balance="100.00", statement_date=date(2026, 2, 1)),
                paper("S2", provider=OFFICE, account_ref="A", patient_balance="-50.00", statement_date=date(2026, 6, 1)))
    assert sums(checked(case), Kind.E3) == [Decimal("50.00")]


@needs_text
def test_4_the_checker_stops_a_credit_the_papers_contradict_on_its_own_path():
    case = make(paper("S1", provider=OFFICE, account_ref="A", patient_balance="-50.00", statement_date=date(2026, 2, 1)))
    report = checks.run(case)
    later = case.model_copy(deep=True)
    later.documents.append(paper("S2", provider=OFFICE, account_ref="A", patient_balance="100.00", statement_date=date(2026, 6, 1)))
    assert pipeline.check_and_hold(later, report)[0].total_may_come_off == 0


# --- 5: a doubted finding leaves nothing on the book -----------------------------------------

@needs_text
def test_5_a_doubted_overcharge_takes_nothing_off_the_discount():
    case = make(paper("S1", patient_balance="3000.00", amount_due_coupon="3000.00", statement_date=date(2026, 3, 20),
                      service_from=D, service_to=D, lines=[L(1, "99213", "900.00", "300.00", claim_ref="C1")]),
                eob("S2", L(1, "99213", "900.00", "100.00", claim_ref="C1"), doubts=["S2: a number is cut"]))
    report = checked(case)
    assert not report.held_back
    assert sums(report, Kind.F1) == [Decimal("2550.00")]  # 85% of the whole 3,000: the doubted $200 came off nothing


# --- 7-11: the window ------------------------------------------------------------------------

def stay(doc_id, service, bill_date, balance, **kw) -> Document:
    return paper(doc_id, account_ref=f"[ACCT_{doc_id[1:]}]", statement_date=bill_date, service_from=service, service_to=service,
                 patient_balance=balance, **kw)


@needs_text
def test_7_a_paper_with_no_dates_does_not_join_the_open_stay_when_there_were_two():
    a = date(2026, 1, 5)
    b = date(2026, 6, 5)
    case = make(stay("S1", a, date(2026, 2, 1), "0.00"), stay("S2", b, date(2026, 7, 1), "900.00"),
                eob("S3", L(1, "0450", "500.00", "0.00", service_date=b), statement_date=date(2026, 7, 10)),
                eob("S4", L(1, "0450", "500.00", "0.00", service_date=None), statement_date=date(2026, 10, 20)))
    report = checks.run(case)
    f2 = next(f for f in report.findings + report.worth_asking if f.kind == Kind.F2)
    assert f2.deadline == date(2027, 7, 10)  # 12 months after S3; S4 could belong to either stay
    assert f2.severity == "borderline" and "S4" in f2.math["why_unsure"]


@needs_text
def test_8_a_first_bill_whose_date_was_misread_leaves_no_confirmed_date():
    first = paper("S1", account_ref="A", first_after_discharge=True, service_from=date(2026, 1, 1), service_to=date(2026, 1, 1),
                  statement_date=date(2026, 12, 5), patient_balance="900.00")
    second = paper("S2", account_ref="B", service_from=date(2026, 1, 1), service_to=date(2026, 1, 1),
                   statement_date=date(2026, 10, 1), patient_balance="700.00")
    report = checks.run(checks.plausible_dates(make(first, second)))
    assert not [f for f in report.findings if f.kind == Kind.F2]


@needs_text
def test_9_a_reopened_case_moves_to_the_stay_whose_window_is_open():
    case = make(stay("S1", date(2026, 1, 5), date(2026, 2, 1), "800.00"), stay("S2", date(2026, 6, 5), date(2026, 7, 1), "900.00"),
                today=date(2026, 12, 30))
    report = checks.run(case)
    assert report.apply_by == date(2027, 1, 5)
    later = case.model_copy(update={"today": date(2027, 1, 10)})
    fresh = checks.window_today(later, report)
    assert fresh.apply_by == date(2027, 6, 5)
    assert next(f for f in fresh.findings if f.kind == Kind.F2).deadline == date(2027, 6, 5)
    assert "applying before June 5, 2027" in " ".join(p.text for p in writer.application(later, fresh).paragraphs)


@needs_text
def test_10_a_stay_still_owed_with_no_bill_date_leaves_no_confirmed_date():
    undated = paper("S1", account_ref="A", service_from=date(2026, 1, 10), service_to=date(2026, 1, 10), patient_balance="800.00")
    case = make(undated, stay("S2", date(2026, 9, 1), date(2026, 9, 20), "500.00"))
    report = checks.run(case)
    assert not [f for f in report.findings if f.kind == Kind.F2]
    f2 = next(f for f in report.worth_asking if f.kind == Kind.F2)
    assert f2.deadline == date(2027, 1, 10) and "S1" in f2.math["why_unsure"]  # a year after the care, the earliest we know


@needs_text
def test_11_the_checker_agrees_on_a_hospital_named_another_way():
    bill = paper("S1", provider="Regional Seaside Hospital", account_ref="A", service_from=date(2026, 1, 1), service_to=date(2026, 1, 1),
                 statement_date=date(2026, 1, 20), patient_balance="900.00", insurance_payment_date=date(2026, 6, 30))
    assert not checked(make(bill)).held_back


@needs_text
def test_11_the_checker_keeps_bills_with_no_service_date_together():
    a = paper("S1", account_ref="A", statement_date=date(2026, 1, 20), patient_balance="900.00")
    b = paper("S2", account_ref="B", statement_date=date(2026, 3, 20), patient_balance="700.00")
    assert not checked(make(a, b)).held_back


def test_9_a_family_case_opened_later_shows_the_date_still_open(tmp_path, monkeypatch):
    from billradar import app
    case = make(stay("S1", date(2026, 1, 5), date(2026, 2, 1), "800.00"), stay("S2", date(2026, 6, 5), date(2026, 7, 1), "900.00"),
                today=date(2026, 12, 30))
    (tmp_path / "case.json").write_text(case.model_dump_json())
    (tmp_path / "report.json").write_text(checks.run(case).model_dump_json())
    monkeypatch.setattr(app, "_run_dir", lambda _: tmp_path)
    monkeypatch.setattr(app, "_today", lambda *_: date(2027, 1, 10))
    assert app._load("t")[2].apply_by == date(2027, 6, 5)


@needs_text
def test_10_the_sheet_with_no_bill_date_goes_back_for_a_new_photo():
    undated = paper("S1", account_ref="A", service_from=date(2026, 1, 10), service_to=date(2026, 1, 10), patient_balance="800.00")
    report = checks.run(make(undated, stay("S2", date(2026, 9, 1), date(2026, 9, 20), "500.00")))
    assert pipeline.unreadable_sheets([undated], report=report) == ["S1"]


# --- 12, 13: every surface says it --------------------------------------------------------------

def report_with_date(when: date) -> checks.Report:
    return checks.Report(case_id="t", policy_id="memorial-2026-05", fpl_pct=Decimal(200), findings=[], no_money=[], held_back=[],
                         total_may_come_off=Decimal(0), apply_by=when)


def test_12_the_subline_does_not_tell_the_family_to_apply_by_a_day_gone_by():
    line = view.build(make(), report_with_date(date(2026, 9, 1)), [], True).subline
    assert "apply by" not in line and "Sep 1, 2026" in line and "passed" in line


@pytest.mark.parametrize("kind,word", [(Kind.F2, "apply"), (Kind.A1, "appeal")])
def test_13_the_english_pdf_says_a_day_has_gone_by(kind, word):
    f = Finding(kind=kind, title="Apply by Sep 1, 2026", detail="d", deadline=date(2026, 9, 1))
    assert finding_text.text(f, make(), "en")[0] == f"The last day to {word} was Sep 1, 2026"


def test_13_an_appeal_gone_by_is_said_in_the_translations_too():
    f = Finding(kind=Kind.A1, title="Appeal the denial by Sep 1, 2026", detail="d", deadline=date(2026, 9, 1))
    assert "прошёл" in finding_text.text(f, make(), "ru")[0] and "pasó" in finding_text.text(f, make(), "es")[0]


# --- 14: a year is a year ----------------------------------------------------------------------

@needs_text
def test_14_one_year_after_service_crosses_a_leap_day():
    case = make(stay("S1", date(2027, 6, 5), date(2027, 6, 20), "900.00"), today=date(2027, 8, 1))
    report = checked(case)
    assert report.apply_by == date(2028, 6, 5) and not report.held_back


# --- 15-19: reading ----------------------------------------------------------------------------

def docs_of(*raw) -> list:
    expected = {r["doc_id"]: Source.PAPER for r in raw}
    return reader.to_documents({"documents": list(raw)}, expected)[0]


def raw_doc(**kw) -> dict:
    return {"doc_id": "S1", "kind": "hospital_statement", "patient_balance": "$50.00", "lines": []} | kw


class Script:
    live = False

    def __init__(self, *answers):
        self.answers, self.labels = list(answers), []

    def respond(self, body, label=""):
        import json
        from types import SimpleNamespace
        self.labels.append(label)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return SimpleNamespace(text=json.dumps({"documents": answer}), usage={}, seconds=0.1, replayed=True)


def settle(client, first, printed=None):
    problems = []
    return reconcile_read.reconcile(client, first, [("S1", b"x")], printed or {}, problems), problems


def test_15_reads_that_differ_on_a_date_of_service_are_not_settled():
    out, _ = settle(Script([raw_doc(service_from="2025-03-01")], [raw_doc(service_from="2024-03-01")]),
                    docs_of(raw_doc(service_from="2026-03-01")))
    assert out[0].doubts


def test_15_reads_that_differ_on_a_line_date_are_not_settled():
    line = {"line_no": 1, "code": "99213", "charges": "$10.00", "service_date": "2026-03-01"}
    other = line | {"service_date": "2025-03-09"}
    out, _ = settle(Script([raw_doc(lines=[other])], [raw_doc(lines=[other | {"service_date": "2024-01-01"}])]),
                    docs_of(raw_doc(lines=[line])))
    assert out[0].doubts


def test_15_reads_that_differ_on_the_kind_of_paper_are_not_settled():
    out, _ = settle(Script([raw_doc(kind="eob")], [raw_doc(kind="itemized_bill")]), docs_of(raw_doc()))
    assert out[0].doubts


def test_16_a_lone_third_read_does_not_replace_the_first():
    out, _ = settle(Script([], [raw_doc(patient_balance="$5,000.00")]), docs_of(raw_doc(patient_balance="$500.00")))
    assert out[0].patient_balance == Decimal("500.00") and out[0].doubts


def test_16_a_third_read_that_agrees_settles_it():  # must light
    out, _ = settle(Script([], [raw_doc(patient_balance="$500.00")]), docs_of(raw_doc(patient_balance="$500.00")))
    assert out[0].doubts == []


def test_17_a_look_at_one_sheet_keeps_its_doubts():
    class Client:
        def respond(self, body, label=""):
            import json
            from types import SimpleNamespace
            line = {"line_no": 1, "code": "99213", "charges": "$400.00"}
            raw = {"doc_id": "S1", "kind": "hospital_statement", "lines": [line, line | {"line_no": 2}]}
            return SimpleNamespace(text=json.dumps({"documents": [raw]}), usage={}, seconds=0, replayed=True)

    img = Image.new("RGB", (900, 260), "white")
    d = ImageDraw.Draw(img)
    for i in (0, 1):
        d.text((80, 60 + 70 * i), "99213 Office visit $400.00", fill="black", font=redact._font(30))
    doc = docs_of(raw_doc(lines=[{"line_no": 1, "code": "99213", "charges": "$400.00"}]))[0]
    doc.doubts.append("S1: the reads disagree")
    sheet = type("Sheet", (), {"doc_id": "S1", "image": img})()
    out = pipeline._second_look(Client(), [doc], [sheet], [])
    assert out[0].doubts == ["S1: the reads disagree"]


def test_18_a_balance_row_keeps_its_sign():
    assert table_rows.last_balance([Row("Account Balance (812.40)", {Decimal("812.40")}, set())]) == Decimal("-812.40")


@pytest.mark.parametrize("text", ["Late fee if balance not paid $35.00", "Insurance balance pending $1,200.00",
                                  "If your balance is not paid by March 1 $25.00"])
def test_18_rows_that_only_mention_a_balance_are_not_the_balance(text):
    assert table_rows.last_balance([Row(text, {Decimal("1.00")}, set())]) is None


def test_18_a_balance_read_only_by_the_device_gives_no_confirmed_sum():
    last = Row("Your Balance Due $812.40", {Decimal("812.40")}, set())
    out, _ = settle(Script([raw_doc(patient_balance="")]), docs_of(raw_doc(patient_balance="")), {"S1": [last]})
    assert out[0].patient_balance == Decimal("812.40") and out[0].device_balance
    (debt,) = ledger.Book(make(out[0])).debts
    assert debt.asked is None


def test_18_a_device_balance_next_to_a_coupon_leaves_the_coupon_standing():
    doc = paper("S1", patient_balance="0.00", amount_due_coupon="719.03", device_balance=True)
    assert ledger.Book(make(doc)).debts[0].asked is None  # two answers: E4


def test_19_a_second_read_that_fails_leaves_the_sheet_doubted_and_the_case_alive():
    out, problems = settle(Script(mc.MetaAPIError("down"), mc.MetaAPIError("down")), docs_of(raw_doc()))
    assert out[0].doubts and any("down" in p for p in problems)


def test_19_a_model_answer_of_the_wrong_shape_is_an_api_error():
    class Odd:
        live = False

        def respond(self, body, label=""):
            from types import SimpleNamespace
            return SimpleNamespace(text='{"documents": [{"doc_id": "S1", "kind": "invoice"}]}', usage={}, seconds=0, replayed=False)

    with pytest.raises(mc.MetaAPIError):
        reader.read_case(Odd(), [("S1", b"x")], [])


def test_19_a_timeout_on_the_open_model_is_an_api_error_and_gives_its_reservation_back(tmp_path):
    def boom(*a, **k):
        raise requests.ReadTimeout("slow")

    t = open_reader.BasetenTransport("KEY", post=boom, ledger=mc.SpendLedger(tmp_path / "s.jsonl", cap=1.0))
    body = reader.request_body([("S1", b"\xff\xd8")], [], model=open_reader.MODEL)
    with pytest.raises(mc.MetaAPIError):
        t.events(body)
    assert t.ledger.spent() == pytest.approx(0)


# --- 21: pages ---------------------------------------------------------------------------------

def test_20_a_number_larger_than_the_charge_leaves_the_line_and_no_doubt_on_the_sheet():
    doc = docs_of(raw_doc(lines=[{"line_no": 1, "code": "99213", "charges": "$100.00", "adjustment": "$900.00",
                                  "patient_responsibility": "$50.00"}]))[0]
    assert doc.lines[0].adjustment is None and doc.lines[0].patient_responsibility is None
    assert doc.doubts == []  # one subtotal read into a line would otherwise send a good sheet back for a new photo


def test_21_a_printed_zero_on_a_later_page_is_a_value():
    pages = [Document(doc_id="D1.1", source=Source.PAPER, kind=DocKind.HOSPITAL_STATEMENT, patient_balance=Decimal("125.00")),
             Document(doc_id="D1.2", source=Source.PAPER, kind=DocKind.OTHER, patient_balance=Decimal("0.00"))]
    merged = pdfpages.merge_pages(pages)[0]
    assert merged.patient_balance == Decimal("0.00") and merged.doubts


def test_21_pages_that_agree_leave_no_doubt():
    pages = [Document(doc_id=f"D1.{i}", source=Source.PAPER, kind=DocKind.HOSPITAL_STATEMENT, patient_balance=Decimal("125.00"))
             for i in (1, 2)]
    assert pdfpages.merge_pages(pages)[0].doubts == []


# --- 22-26: private values ---------------------------------------------------------------------

def test_22_an_accented_name_on_the_profile_is_found_printed_without_accents():
    vault = redact.Vault(seed={("PATIENT", "María Pérez"): "[PATIENT_1]"})
    assert redact._spans("Insured: MARIA PEREZ", vault, False)
    assert redact.compact("María") == redact.compact("MARIA")


def small_sheet(text_lines) -> Image.Image:
    img = Image.new("RGB", (900, 120 + 70 * len(text_lines)), "white")
    d = ImageDraw.Draw(img)
    for i, t in enumerate(text_lines):
        d.text((60, 50 + 70 * i), t, fill="black", font=redact._font(34))
    return img


def test_23_a_sheet_upside_down_is_read_and_closed_upright(monkeypatch):
    sheet = small_sheet(["Anna Sample came in for the visit today", "Visit charged today by the office", "Thank you very much"])
    upside = sheet.rotate(180, expand=True)
    monkeypatch.setattr(local_reader, "turn_of", lambda img: 180)
    vault = redact.Vault(seed={("PATIENT", "Anna Sample"): "[PATIENT_1]"})
    covered = redact.redact(upside, vault).image
    assert redact._reading(upside).turn == 180
    assert "ANNA" not in " ".join(ln.text.upper() for ln in redact.ocr(covered))


def blurred() -> Image.Image:
    sheet = small_sheet(["Patient: Anna Sample", "Account: LDH-000123", "Member ID: XQZ123456789", "Balance due $676.80",
                         "Thank you for your payment"])
    return sheet.filter(ImageFilter.GaussianBlur(radius=4))


def test_25_a_soft_sheet_the_device_cannot_read_is_not_sent():
    with pytest.raises(pipeline.Unsendable):
        pipeline._no_leaks(blurred(), redact.Vault(), "S1")


def test_25_a_clean_sheet_passes_the_same_check():  # must light
    sheet = small_sheet(["Statement of services", "Balance due $676.80", "Thank you for your payment"])
    assert pipeline._no_leaks(sheet, redact.Vault(), "S1") is sheet


def test_25_a_blank_back_of_a_page_is_sent_as_it_is():
    blank = Image.new("RGB", (800, 1000), "white")
    assert pipeline._no_leaks(blank, redact.Vault(), "S1") is blank


class Wire:
    """The model on the wire: says what it was sent and reads one line of a balance for every paper."""

    live = False

    def __init__(self):
        self.asked = []

    def events(self, body):
        import json
        said = [p["text"] for m in body["input"] if isinstance(m["content"], list) for p in m["content"] if p["type"] == "input_text"]
        ids = [t.split()[1].rstrip(":") for t in said if t.startswith("Sheet ")]
        self.asked += ids
        text = json.dumps({"documents": [raw_doc(doc_id=i) for i in ids]})
        return [{"type": "response.output_text.delta", "delta": text},
                {"type": "response.completed", "response": {"id": "", "usage": {}}}]


CLEAR = ["Statement of services", "Balance due $676.80", "Thank you for your payment"]


def go(wire, photos=(), files=()):
    client = mc.MetaClient(transport=wire, record_to=None, journal=None)
    prof = Profile(household_size=4, annual_income=Decimal("85000"), insured=True, people=[Person(token="PATIENT_1", role=Role.MOTHER)])
    return pipeline.run(client, list(photos), list(files), prof, "memorial-2026-05", HOSPITAL, T, "t", fictional=True, private=True)


def test_25_a_soft_sheet_is_kept_here_and_comes_back_for_a_new_photo(monkeypatch):
    from io import BytesIO

    from billradar import sam
    raw = BytesIO()
    small_sheet(CLEAR).save(raw, "JPEG")
    box = (0, 0, 900, 300)
    found = sam.SheetsResult([sam.Sheet("S1", box, None, None, small_sheet(CLEAR), False), sam.Sheet("S2", box, None, None, blurred(), False)])
    monkeypatch.setattr(pipeline.providers, "sheet_finder", lambda _: lambda *a, **k: found)
    wire = Wire()
    run = go(wire, photos=[raw.getvalue()])
    assert "S1" in wire.asked and "S2" not in wire.asked
    assert run.unreadable == ["S2"]


def test_sheets_are_cut_from_the_photo_as_taken_and_covered_on_the_sheet(monkeypatch):
    """A whole photo is read at a quarter of its size: three tight address lines become one line of noise, and a cover put
    there leaves pieces the sheet pass cannot match. So the covers that leave the device are made on the cut sheet."""
    from io import BytesIO

    from billradar import sam
    sheet = small_sheet(["Patient: Anna Sample", "Balance due $676.80", "Thank you for your payment"])
    raw = BytesIO()
    sheet.save(raw, "PNG")
    seen = {}

    def finder(client, photo, send=None, crop_from=None):
        seen["cut_from"] = crop_from
        return sam.SheetsResult([sam.Sheet("S1", (0, 0) + crop_from.size, None, None, crop_from.copy(), False)])

    monkeypatch.setattr(pipeline.providers, "sheet_finder", lambda _: finder)
    wire = Wire()
    client = mc.MetaClient(transport=wire, record_to=None, journal=None)
    prof = Profile(household_size=4, annual_income=Decimal("85000"), insured=True,
                   people=[Person(token="PATIENT_1", role=Role.MOTHER, name="Anna Sample")])
    run = pipeline.run(client, [raw.getvalue()], [], prof, "memorial-2026-05", HOSPITAL, T, "t", fictional=True, private=True)
    assert seen["cut_from"].tobytes() == sam.load_photo(raw.getvalue()).tobytes()
    assert "ANNA" not in " ".join(ln.text.upper() for ln in redact.ocr(run.sheets[0].image))
    assert run.originals["S1"].tobytes() == seen["cut_from"].tobytes()


def test_25_a_soft_page_leaves_its_file_with_no_sum(monkeypatch):
    monkeypatch.setattr(pdfpages, "learn", lambda *a: 0)
    monkeypatch.setattr(pdfpages, "render", lambda _: [small_sheet(CLEAR), blurred()])
    wire = Wire()
    run = go(wire, files=[("a.pdf", b"x")])
    assert "D1.1" in wire.asked and "D1.2" not in wire.asked
    assert "D1.2" in run.unreadable
    assert any("too soft" in x for d in run.case.documents for x in d.doubts)


def test_26_an_account_number_printed_like_an_amount_is_covered_and_seen():
    secret = redact.Secret("ACCT", "123456", "[ACCT_1]")
    vault = redact.Vault(known=[("ACCT", "123456")])
    assert redact._spans("Ref 1234.56 Office visit", vault, False)
    assert redact.leaks(small_sheet(["Ref 1234.56 Office visit"]), [secret]) == [secret]


def test_days_passed_title_is_one_function():
    assert days.passed_title("F2", date(2026, 9, 1), T) == "The last day to apply was Sep 1, 2026"
    assert days.passed_title("F2", date(2026, 12, 1), T) == ""
    assert days.passed_title("E1", date(2026, 9, 1), T) == ""


def test_the_call_sheet_shows_whose_rules_only_for_the_hospital(monkeypatch):
    from fastapi.testclient import TestClient

    from billradar import app, callprep
    case = make(paper("S1", patient_balance="900.00"), income="60000", size=3, insured=False).model_copy(update={"demo": True})
    report = checks.run(case)
    monkeypatch.setattr(app, "_load", lambda _: (None, case, report))
    monkeypatch.setattr(callprep, "build", lambda *a: _Sheet())
    monkeypatch.setattr(callprep, "all_sheets", lambda *a: [])
    seen = {}
    monkeypatch.setattr(app, "_page", lambda request, name, **kw: seen.update(kw) or "")
    c = TestClient(app.app)  # no `with`: the agents' entry starts once per process
    c.get("/cases/x/call/hospital")
    assert "Memorial Regional Hospital" in seen["demo_rules"]
    c.get("/cases/x/call/insurer")
    assert seen["demo_rules"] == ""


class _Sheet:
    objections = ()


# --- what the family reads (build-5 review) -------------------------------------------------------

@pytest.mark.parametrize("said,shown", [("Line 1 on sheet S1 asks more", "Line 1 on sheet 1 asks more"),
                                        ("Your insurance statement S2, line 3", "Your insurance statement on sheet 2, line 3"),
                                        ("Sheet D1: waiting for insurance", "File 1: waiting for insurance"),
                                        ("(S2, lines 1, 2)", "(sheet 2, lines 1, 2)"),
                                        ("S4 could not be read in full", "Sheet 4 could not be read in full"),
                                        ("code 99213 on S10", "code 99213 on sheet 10")])
def test_a_paper_is_named_the_way_the_screen_numbers_it(said, shown):
    from billradar import i18n
    assert i18n.plain(said, make()) == shown


def test_a_code_that_looks_like_a_paper_id_stays():
    from billradar import i18n
    assert i18n.plain("Code S0630 and code D1-2 stay", make()) == "Code S0630 and code D1-2 stay"


@needs_text
def test_the_application_quotes_the_familys_row_not_the_whole_table():
    case = make(paper("S1", patient_balance="3000.00", statement_date=date(2026, 3, 20), service_from=D, service_to=D),
                income="85000", size=4, insured=False)
    letter = writer.application(case, checks.run(case))
    quotes = [s["quote"] for s in writer.sources(letter)]
    assert "251% - 300% of FPG 85% Discount" in quotes
    assert not any("BALANCES DUE" in q for q in quotes)


def test_a_finding_does_not_say_itself_twice():
    f = Finding(kind=Kind.E2, title="t", detail="d", amount=Decimal("5.00"), explain="The same service appears twice, same day and same price.",
                evidence=[checks.Evidence(doc_id="S1", line_no=1), checks.Evidence(doc_id="S1", line_no=2)],
                math={"code": "01960", "service_date": "2026-03-01", "charges": "5.00"})
    assert view.row(f, make(), "memorial-2026-05", {}).explain == ""


def test_one_office_is_spelled_one_way():
    a = docs_of(raw_doc(provider="Little Harbor Pediatrics \u2013 PA"))[0]
    b = docs_of(raw_doc(provider="Little Harbor Pediatrics - PA"))[0]
    assert a.provider == b.provider


def info_icon_sheet() -> Image.Image:
    """Type the size of a bill's, so the icon counts as a square: a ring of 18 pixels with an "i", as printed by "Additional information"."""
    img = Image.new("RGB", (900, 260), "white")
    d = ImageDraw.Draw(img)
    for i, t in enumerate(["Additional information about this bill", "Your plan decides how much you owe for this visit",
                           "The balance may be due to your deductible today", "This bill is the portion you owe for care"]):
        d.text((60, 40 + 34 * i), t, fill="black", font=redact._font(16))
    d.ellipse((30, 40, 48, 58), outline=(30, 30, 30), width=2)
    d.rectangle((38, 44, 40, 46), fill=(30, 30, 30))
    d.rectangle((38, 48, 40, 54), fill=(30, 30, 30))
    return img


def test_a_round_info_icon_is_not_a_machine_code():
    assert redact.codes(info_icon_sheet()) == []


def test_a_small_square_with_filled_corners_is_still_a_code():  # must light
    import numpy as np
    patch = np.zeros((18, 18), dtype=bool)
    patch[:, :3] = patch[-3:, :] = True
    assert redact._inked_corners(patch)
    ring = np.zeros((18, 18), dtype=bool)
    ring[4:14, 8:10] = True
    assert not redact._inked_corners(ring)


def test_a_mail_line_is_covered_whole():
    import numpy as np
    sheet = small_sheet(["H2PX312M008497 HLNX", "Statement of your account", "Balance due $676.80"])
    line = next(ln for ln in redact.ocr(sheet) if "HLNX" in ln.text)
    x0, y0, x1, y1 = (int(v) for v in (*line.box.min(axis=0), *line.box.max(axis=0)))
    covered = redact.redact(sheet, redact.Vault()).image
    tail = covered.crop((x0 + int(0.8 * (x1 - x0)), y0, x1, y1))  # where the last word was printed
    assert np.asarray(tail.convert("L")).min() > 200
    assert "676.80" in " ".join(ln.text for ln in redact.ocr(covered))


def test_an_amount_on_a_mail_line_stays():  # must light
    sheet = small_sheet(["H2PX312M008497 Balance $676.80", "Statement of your account", "Thank you for your payment"])
    covered = redact.redact(sheet, redact.Vault()).image
    read = " ".join(ln.text for ln in redact.ocr(covered))
    assert "H2PX" not in read and "676.80" in read


def test_a_code_only_the_jpeg_shows_is_a_code(monkeypatch):
    """What leaves the device is a JPEG. A small DataMatrix (a fictional sheet's margin) sits just under the threshold on the
    sheet and over it once compressed, so the gate has to look at it as it will be sent."""
    from pathlib import Path
    fixture = Image.open(Path(__file__).parent / "fixtures" / "small-datamatrix.png").convert("RGB")
    monkeypatch.setattr(redact, "_text_height", lambda *a: 18.9)
    assert redact.codes(fixture, [])


def test_a_code_found_twice_is_listed_once(monkeypatch):
    from pathlib import Path
    fixture = Image.open(Path(__file__).parent / "fixtures" / "small-datamatrix.png").convert("RGB")
    monkeypatch.setattr(redact, "_text_height", lambda *a: 18.9)
    assert len(redact.codes(fixture, [])) == 1


# --- what the first live read showed (31.10): real answers of Muse Spark on a fictional pack ---------

def test_a_line_dated_as_a_span_takes_its_first_day_and_no_doubt():
    doc = docs_of(raw_doc(kind="eob", lines=[{"line_no": 1, "code": "0112", "charges": "$10.00",
                                              "service_date": "02/11/2025-02/13/2025"}]))[0]
    assert doc.lines[0].service_date == date(2025, 2, 11) and doc.doubts == []


def test_a_date_that_is_no_date_is_still_a_doubt():  # must light
    doc = docs_of(raw_doc(lines=[{"line_no": 1, "code": "0112", "charges": "$10.00", "service_date": "02/11/2025-soon"}]))[0]
    assert doc.lines[0].service_date is None and doc.doubts


def test_a_lone_dollar_sign_is_an_empty_field():
    assert docs_of(raw_doc(due_from_insurance="$"))[0].doubts == []


def printed_row(text: str, *amounts: str) -> Row:
    return Row(text, {Decimal(a) for a in amounts}, set())


def test_what_one_read_left_out_and_the_sheet_prints_is_taken():
    first = docs_of(raw_doc(amount_due_coupon=""))
    out, _ = settle(Script([raw_doc(amount_due_coupon="$393.64")]), first, {"S1": [printed_row("PAY THIS AMOUNT $393.64", "393.64")]})
    assert out[0].amount_due_coupon == Decimal("393.64") and out[0].doubts == []


def test_what_one_read_left_out_and_the_sheet_does_not_print_stays_open():  # must light
    first = docs_of(raw_doc(amount_due_coupon=""))
    out, _ = settle(Script([raw_doc(amount_due_coupon="$393.64")], [raw_doc(amount_due_coupon="$1.00")]), first, {"S1": []})
    assert out[0].doubts


def test_a_total_one_read_left_out_is_no_reason_to_doubt_a_sheet():
    out, _ = settle(Script([raw_doc(insurance_paid="-$1,574.58")]), docs_of(raw_doc()))
    assert out[0].doubts == []


def test_two_totals_that_differ_are_still_a_disagreement():  # must light
    out, _ = settle(Script([raw_doc(insurance_paid="-$1,574.58")], [raw_doc(insurance_paid="-$2.00")]), docs_of(raw_doc(insurance_paid="-$1.00")))
    assert out[0].doubts


def test_a_page_read_as_other_fits_any_kind():
    out, _ = settle(Script([raw_doc(kind="other")]), docs_of(raw_doc()))
    assert out[0].doubts == []


def test_a_balance_on_an_insurance_statement_asks_nothing():
    out, _ = settle(Script([raw_doc(kind="eob", patient_balance="$739.03")]), docs_of(raw_doc(kind="eob", patient_balance="")))
    assert out[0].doubts == []


def test_a_line_the_device_sees_stands_though_a_part_has_no_field():
    """$332.00 = paid $85.57 + adjusted $196.43 + copay collected $90.00 - $40.00 back: no field holds the copay."""
    line = {"line_no": 1, "code": "76815", "charges": "$332.00", "insurance_paid": "$85.57", "adjustment": "$196.43",
            "patient_responsibility": "$40.00"}
    rows = [Row("76815 OB US $332.00", {Decimal("332.00")}, {"76815"}), printed_row("Insurance Payment $85.57", "85.57"),
            printed_row("Insurance Adjustment $196.43", "196.43"), printed_row("Your Balance Due On These Services ($40.00)", "40.00")]
    out, _ = settle(Script([raw_doc(lines=[line])]), docs_of(raw_doc(lines=[line])), {"S1": rows})
    assert out[0].doubts == []


def test_a_line_that_does_not_add_up_and_is_not_printed_stays_a_doubt():  # must light
    line = {"line_no": 1, "code": "76815", "charges": "$332.00", "insurance_paid": "$85.57", "adjustment": "$196.43",
            "patient_responsibility": "$40.00"}
    out, _ = settle(Script([raw_doc(lines=[line])]), docs_of(raw_doc(lines=[line])), {"S1": []})
    assert out[0].doubts


def test_the_read_with_more_printed_numbers_settles_a_line():
    thin = {"line_no": 1, "code": "99213", "charges": "$240.00"}
    full = thin | {"insurance_paid": "$53.12", "adjustment": "$166.88", "patient_responsibility": "$20.00"}
    rows = [Row("99213 Office Visit $240.00", {Decimal("240.00")}, {"99213"}), printed_row("Insurance Payment $53.12", "53.12"),
            printed_row("Insurance Adjustment $166.88", "166.88"), printed_row("Your Balance Due On These Services $20.00", "20.00")]
    out, _ = settle(Script([raw_doc(lines=[full])]), docs_of(raw_doc(lines=[thin])), {"S1": rows})
    assert out[0].lines[0].patient_responsibility == Decimal("20.00") and out[0].doubts == []


@pytest.mark.parametrize("text", ["Print Date 4/7/2025", "Statement 04/07/2025", "Apr 7, 2025", "04/07/25"])
def test_a_date_one_read_left_out_is_found_however_it_is_printed(text):
    first = docs_of(raw_doc(statement_date=""))
    out, _ = settle(Script([raw_doc(statement_date="2025-04-07")]), first, {"S1": [printed_row(text)]})
    assert out[0].statement_date == date(2025, 4, 7) and out[0].doubts == []


# --- the last layer: a confirmed sum stands only on numbers the device read there itself -------------

def bill_rows(*text_amounts) -> list:
    return [printed_row(t, *a) for t, *a in text_amounts]


def f1_case():
    return make(paper("S1", patient_balance="3000.00", statement_date=date(2026, 3, 20), service_from=D, service_to=D),
                income="60000", size=3, insured=False)


@needs_text
def test_a_sum_on_a_balance_the_device_reads_stands():  # must light
    case = f1_case()
    report = pipeline.device_confirms(case, checks.run(case), {"S1": bill_rows(("Your Balance Due $3,000.00", "3000.00"))})
    assert sums(report, Kind.F1) == [Decimal("2700.00")]


@needs_text
def test_both_reads_agreeing_on_a_balance_the_sheet_does_not_print_confirm_nothing():
    case = f1_case()
    report = pipeline.device_confirms(case, checks.run(case), {"S1": bill_rows(("Your Balance Due $2,000.00", "2000.00"))})
    assert sums(report, Kind.F1) == [] and report.total_may_come_off == 0 and asked(report, Kind.F1)


@needs_text
def test_the_same_number_printed_for_something_else_confirms_nothing():
    case = f1_case()
    rows = bill_rows(("Charges this visit $3,000.00", "3000.00"), ("Your Balance Due $2,000.00", "2000.00"))
    assert pipeline.device_confirms(case, checks.run(case), {"S1": rows}).total_may_come_off == 0


@needs_text
def test_a_sheet_the_device_never_read_confirms_nothing():
    case = f1_case()
    assert pipeline.device_confirms(case, checks.run(case), {}).total_may_come_off == 0


@needs_text
def test_a_sum_read_on_the_wrong_line_confirms_nothing():
    bill = paper("S1", provider=OFFICE, patient_balance="150.00", amount_due_coupon="150.00",
                 lines=[L(1, "99213", "400.00", "50.00"), L(2, "99213", "400.00", "50.00")])
    rows = [Row("99213 Office visit $400.00 $75.00", {Decimal("400.00"), Decimal("75.00")}, {"99213"}),
            Row("99213 Office visit $400.00 $75.00", {Decimal("400.00"), Decimal("75.00")}, {"99213"}),
            printed_row("Balance due $150.00", "150.00")]
    case = make(bill)
    report = pipeline.device_confirms(case, checks.run(case), {"S1": rows})
    assert sums(report, Kind.E2) == [] and report.total_may_come_off == 0


@needs_text
def test_a_double_line_the_device_reads_stands():  # must light
    bill = paper("S1", provider=OFFICE, patient_balance="150.00", amount_due_coupon="150.00",
                 lines=[L(1, "99213", "400.00", "50.00"), L(2, "99213", "400.00", "50.00")])
    rows = [Row("99213 Office visit $400.00 $50.00", {Decimal("400.00"), Decimal("50.00")}, {"99213"}),
            Row("99213 Office visit $400.00 $50.00", {Decimal("400.00"), Decimal("50.00")}, {"99213"}),
            printed_row("Balance due $150.00", "150.00")]
    case = make(bill)
    assert sums(pipeline.device_confirms(case, checks.run(case), {"S1": rows}), Kind.E2) == [Decimal("50.00")]


def test_a_number_printed_for_something_else_settles_nothing():
    first = docs_of(raw_doc(amount_due_coupon=""))
    rows = {"S1": [printed_row("Charges this visit $4,944.00", "4944.00"), printed_row("Balance due $50.00", "50.00")]}
    out, _ = settle(Script([raw_doc(amount_due_coupon="$4,944.00")], [raw_doc(amount_due_coupon="$7.00")]), first, rows)
    assert out[0].amount_due_coupon is None and out[0].doubts


def test_a_page_of_a_file_is_given_no_balance_of_its_own():
    """A file is one paper: the device must not put a balance on each page that prints none."""
    page = docs_of(raw_doc(doc_id="D1.2", patient_balance=""))
    out, _ = settle(Script([raw_doc(doc_id="D1.2", patient_balance="")]), page, {"D1.2": [printed_row("Your Balance Due $812.40", "812.40")]})
    assert out[0].patient_balance is None and not out[0].device_balance


@needs_text
def test_two_reads_forging_one_sum_do_not_reach_the_screen():
    """Two reads out of three say $9,000, the sheet says $3,000: no sum stands on it."""
    first = docs_of(raw_doc(patient_balance="$3,000.00"))
    rows = {"S1": [printed_row("Your Balance Due $3,000.00", "3000.00")]}
    out, _ = settle(Script([raw_doc(patient_balance="$9,000.00")], [raw_doc(patient_balance="$9,000.00")]), first, rows)
    case = make(out[0], income="60000", size=3, insured=False)
    assert checks.run(case).total_may_come_off > 0  # must light: without the device the forged sum goes through
    assert pipeline.device_confirms(case, checks.run(case), rows).total_may_come_off == 0


def test_no_confirmed_sum_stands_on_what_the_plan_paid():
    """The one amount a dollar off the last layer can still pass is a paid column that equals another column of its row.
    No sum may stand on that field: this keeps it so."""
    import inspect
    import re as regex
    source = inspect.getsource(checks) + inspect.getsource(__import__("billradar.sheet_checks", fromlist=["x"]))
    steps = regex.findall(r'line_step\([^,]+,[^,]+,\s*"(\w+)"', source) + regex.findall(r'field="(\w+)"', source)
    named = regex.findall(r'for n in \(([^)]*)\)', source)
    assert steps and "insurance_paid" not in steps and not any("insurance_paid" in n for n in named)


# --- what Muse Wonder caught on the live run (01.11): words the papers do not carry ---------------------

def baby_papers(**kw):
    mom = eob("S1", L(1, "0170", "100.00", "0.00", denial_codes="A27", insurance_paid=Decimal("0")), patient="PATIENT_1")
    baby = paper("D3", patient="PATIENT_2", patient_balance="1490.25", due_from_insurance=Decimal("1490.25"),
                 insurance_paid=Decimal("-4946.75"), **kw)
    prof = Profile(household_size=3, annual_income=Decimal("58000"), insured=True,
                   people=[Person(token="PATIENT_1", role=Role.MOTHER), Person(token="PATIENT_2", role=Role.NEWBORN)])
    return Case(case_id="t", policy_id="memorial-2026-05", today=T, profile=prof, documents=[mom, baby], letterhead=HOSPITAL)


def test_a_balance_waiting_for_insurance_is_said_as_that():
    from billradar import sheet_checks
    case = baby_papers()
    b1 = next(f for f in sheet_checks.baby_under_mother(case) if f.kind == Kind.B1)
    assert "$1,490.25 due from insurance" in b1.detail and "$0.00" not in b1.detail
    assert "страховой" in finding_text.text(b1, case, "ru")[1] and "1" in finding_text.text(b1, case, "ru")[1]


def test_no_finding_guesses_at_a_time_the_papers_do_not_give():
    from billradar import sheet_checks
    bill = paper("S8", provider="Little Harbor Pediatrics", patient="PATIENT_2", patient_balance="27.00", statement_date=date(2025, 7, 6))
    prof = Profile(household_size=3, annual_income=Decimal("58000"), insured=True,
                   people=[Person(token="PATIENT_1", role=Role.MOTHER), Person(token="PATIENT_2", role=Role.NEWBORN)])
    case = Case(case_id="t", policy_id="memorial-2026-05", today=T, profile=prof, documents=[bill], letterhead=HOSPITAL)
    b2 = sheet_checks.baby_not_matched(case)[0]
    for text in (b2.detail, finding_text.text(b2, case, "ru")[1], finding_text.text(b2, case, "es")[1]):
        assert "likely" not in text and "скорее всего" not in text and "probablemente" not in text
    assert "days old" in b2.detail and "now" in b2.detail


def test_the_open_model_gets_no_more_images_than_it_takes(monkeypatch):
    """Baseten answers HTTP 400 "Too many images: 14 (max 8)": the second read goes in groups."""
    monkeypatch.setenv("BILLRADAR_SECOND_READER", "open")
    monkeypatch.delenv("BILLRADAR_LIVE", raising=False)
    client = open_reader.second_reader()
    assert client.max_images == 8
    sheets = [(f"S{i}", b"x") for i in range(1, 15)]
    groups = reader.batches(sheets, [], client.max_images)
    assert [len(g) for g, _ in groups] == [8, 6]


def test_the_open_models_refusal_says_why():
    class Answer:
        status_code = 400
        text = '{"error": {"message": "Too many images: 14 (max 8)"}}'

    t = open_reader.BasetenTransport("KEY", post=lambda *a, **k: Answer(), ledger=mc.SpendLedger(__import__("pathlib").Path("/dev/null"), cap=1.0))
    t.ledger.reserve = t.ledger.settle = lambda *a: None
    with pytest.raises(mc.MetaAPIError, match="Too many images"):
        t.events(reader.request_body([("S1", b"\xff\xd8")], [], model=open_reader.MODEL))


# --- a date no paper prints is a date to check, everywhere it is shown -----------------------------------

def plan_dated_case(printed_payment=None) -> Case:
    """The window is counted from the plan's statement. Printed payment date, or only the statement's own date."""
    bill = paper("S1", account_ref="A", service_from=date(2025, 2, 11), service_to=date(2025, 2, 13), statement_date=date(2025, 4, 5),
                 patient_balance="1555.23", insurance_payment_date=printed_payment)
    statement = eob("S2", L(1, "0112", "100.00", "0.00", service_date=date(2025, 2, 11)), statement_date=date(2025, 4, 1))
    return make(bill, statement, income="58000", size=3, today=date(2026, 3, 2))


@needs_text
def test_a_date_no_paper_prints_leaves_the_deadline_to_check():
    report = checks.run(plan_dated_case())
    f2 = next(f for f in report.worth_asking if f.kind == Kind.F2)
    assert f2.deadline == date(2026, 4, 1) and report.apply_by == date(2026, 4, 1) and report.apply_by_sure is False
    assert "statement" in f2.math["why_unsure"] and "payment date" in f2.math["why_unsure"]
    assert not [f for f in report.findings if f.kind == Kind.F2]


@needs_text
def test_a_printed_payment_date_keeps_the_deadline_confirmed():  # must light
    report = checks.run(plan_dated_case(date(2025, 4, 1)))
    assert next(f for f in report.findings if f.kind == Kind.F2).deadline == date(2026, 4, 1) and report.apply_by_sure is True


@needs_text
def test_the_finding_says_what_the_deadline_counts_from():
    f2 = next(f for f in checks.run(plan_dated_case()).worth_asking if f.kind == Kind.F2)
    assert "12 months after" in f2.detail and "Apr 1, 2025" in f2.detail and "S2" in f2.detail


@needs_text
def test_every_surface_says_the_date_is_to_check():
    from billradar import app, bill_picture, report_pdf
    case = plan_dated_case()
    report = checks.run(case)
    assert "apply by Apr 1, 2026, check it with the hospital" in view.build(case, report, [], True).subline
    assert any("check it with the hospital" in x for x in bill_picture.labels(case, report))
    assert "check it with the hospital" in app.case_dates(case, report)[0][1]
    assert "Check this date with the hospital" in i18n_line(report, case)
    assert report_pdf


def i18n_line(report, case) -> str:
    from billradar import report_pdf
    return report_pdf.apply_line(report, case, "en")


@needs_text
def test_a_confirmed_date_reads_plain_on_every_surface():  # must light
    from billradar import app, bill_picture
    case = plan_dated_case(date(2025, 4, 1))
    report = checks.run(case)
    assert view.build(case, report, [], True).subline.endswith("apply by Apr 1, 2026")
    assert not any("check it" in x for x in bill_picture.labels(case, report))
    assert "check it" not in app.case_dates(case, report)[0][1]


def test_a_model_name_with_a_slash_is_recorded_flat(tmp_path):
    """meta-models/muse-spark-open-1026: the live answer was paid for and lost on writing its recording (01.11)."""
    body = {"model": "meta-models/muse-spark-open-1026", "input": []}
    name = mc.recording_name(body)
    assert "/" not in name and name.startswith("meta-models-muse-spark-open-1026-") and name.endswith(".jsonl")
    assert mc.ReplayTransport(tmp_path).path(body).parent == tmp_path


@needs_text
def test_the_date_line_ends_one_sentence_in_every_language():
    from billradar import report_pdf
    case = plan_dated_case()
    report = checks.run(case)
    for lang in ("en", "ru", "es"):
        assert ".." not in report_pdf.apply_line(report, case, lang)
