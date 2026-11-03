"""A sheet the gate will not let out stays on the device and the case goes on. No sum comes from it, and while it may
hold a sum, none is confirmed: zero wrong sums counts for more than a finding kept. SYNTHETIC cases only."""

from datetime import date
from decimal import Decimal

import pytest

from billradar import checks, example, pipeline, report_pdf, writer
from billradar.checks import Finding, Kind, Report


def run_with_gate_refusing(monkeypatch, sheet="S2", money=True):
    real = pipeline._no_leaks

    def gate(img, vault, doc_id):
        if doc_id == sheet:
            raise pipeline.RealDataGate(f"sheet {doc_id}: 1 private value(s) still readable after covering (ADDR); not sending")
        return real(img, vault, doc_id)
    monkeypatch.setattr(pipeline, "_no_leaks", gate)
    monkeypatch.setattr(pipeline, "_prints_money", lambda page: money)
    return example.run_demo_synthetic("t")


def test_the_baseline_case_has_a_confirmed_sum():  # must light
    run = example.run_demo_synthetic("t")
    assert run.report.total_may_come_off > 0 and not run.report.not_sent


def test_the_case_goes_on_without_the_sheet(monkeypatch):
    run = run_with_gate_refusing(monkeypatch)
    assert "S2" not in [s.doc_id for s in run.sheets] and len(run.sheets) >= 2
    assert run.report.not_sent == ["S2"] and "S2" in run.unreadable


def test_a_sheet_that_may_hold_a_sum_leaves_no_confirmed_sum(monkeypatch):
    run = run_with_gate_refusing(monkeypatch)
    assert run.report.total_may_come_off == 0
    assert not [f for f in run.report.findings if f.amount is not None]
    doubted = [f for f in run.report.worth_asking if "was not sent" in f.math.get("why_unsure", "")]
    assert doubted and all(f.amount is None for f in doubted)


def test_a_sheet_with_no_sums_on_it_changes_no_sum_but_is_still_asked_for(monkeypatch):  # must differ
    run = run_with_gate_refusing(monkeypatch, money=False)
    assert run.report.total_may_come_off > 0 and run.report.not_sent == ["S2"] and "S2" in run.unreadable


def test_the_reason_names_a_kind_never_a_value(monkeypatch):
    run = run_with_gate_refusing(monkeypatch)
    said = [p for p in run.problems if "S2" in p and "still readable" in p]
    assert said and "(ADDR)" in said[0]


def test_every_letter_says_it_was_written_without_a_paper(monkeypatch):
    run = run_with_gate_refusing(monkeypatch)
    letters = writer.all_letters(run.case, run.report)
    assert letters and all(any("may change" in p.text for p in x.paragraphs) for x in letters)


def test_with_every_sheet_sent_no_letter_says_so():  # must differ
    run = example.run_demo_synthetic("t")
    assert not [p for x in writer.all_letters(run.case, run.report) for p in x.paragraphs if "may change once" in p.text]


@pytest.mark.parametrize("lang", ["en", "ru", "es"])
def test_the_report_says_it_in_the_familys_language(monkeypatch, lang):
    run = run_with_gate_refusing(monkeypatch)
    run.case.demo = True
    assert report_pdf.build(run.case, run.report, lang=lang)[:4] == b"%PDF"


def test_the_deadline_is_a_date_to_check_too():
    f2 = Finding(kind=Kind.F2, title="Apply by", detail="d", deadline=date(2026, 4, 1))
    money = Finding(kind=Kind.F1, title="t", detail="d", amount=Decimal("100.00"))
    rep = Report(case_id="c", policy_id="p", fpl_pct=Decimal(100), findings=[f2, money], no_money=[], held_back=[], total_may_come_off=Decimal("100.00"), apply_by=date(2026, 4, 1))
    out = pipeline.sheets_not_sent(rep, ["S3"], ["S3"])
    assert out.findings == [] and out.total_may_come_off == 0 and out.apply_by == date(2026, 4, 1) and not out.apply_by_sure


def test_nothing_withheld_changes_nothing():
    rep = Report(case_id="c", policy_id="p", fpl_pct=Decimal(100), findings=[], no_money=[], held_back=[], total_may_come_off=Decimal(0), apply_by=None)
    assert pipeline.sheets_not_sent(rep, [], []) is rep


def test_the_screen_says_what_happened(monkeypatch):
    from pathlib import Path
    html = (Path(checks.__file__).parent / "web" / "templates" / "case.html").read_text()
    assert "was not sent." in html and "not_sent" in html
