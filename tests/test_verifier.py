import dataclasses
import json
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from billradar import app as app_module
from billradar import checks, pipeline, verifier, writer
from billradar.checks import Evidence, Kind
from billradar.meta_client import MetaClient
from billradar.policies import source
from tests.test_writer import case

needs_text = pytest.mark.skipif(not all(source.is_cached(p) for p in source.SOURCES),
                                reason="run scripts/fetch_policies.py first")


def run_all(c):
    """The report of a case and the letters written from it."""
    report = checks.run(c)
    return report, writer.all_letters(c, report)


@needs_text
def test_clean_case_passes_the_checker():
    c = case()
    report, letters = run_all(c)
    assert (len(report.findings), len(letters)) == (3, 4)
    v = verifier.verify(c, report, letters)
    assert v.ok, v.issues
    assert v.checked == len(report.findings) + len(letters)


@needs_text
def test_a_wrong_amount_is_caught_and_held_back():
    c = case()
    report, _ = run_all(c)
    f3 = next(f for f in report.findings if f.kind == Kind.F3)
    # the discount worked out from a wrong balance; the right sum is 1054.00
    wrong = report.model_copy(update={"findings": [
        f.model_copy(update={"amount": Decimal("1100.00")}) if f is f3 else f for f in report.findings]})
    errors = [i for i in verifier.check_findings(c, wrong).issues if i.severity == "error"]
    assert [i.subject.split(" on ")[0] for i in errors] == ["F3 #1", "total"]  # the total stopped adding up too
    assert "1100.00" in errors[0].what and "1054.00" in errors[0].what

    shown, _ = pipeline.check_and_hold(c, wrong)
    assert Kind.F3 not in {f.kind for f in shown.findings}
    assert {f.kind for f in shown.findings} == {Kind.E1, Kind.F2}  # the honest findings stay
    held = [f for f in shown.held_back if "held back by the checker" in f.detail]
    assert [f.kind for f in held] == [Kind.F3]


@needs_text
def test_wrong_deadline_is_caught():
    c = case()
    report, _ = run_all(c)
    assert not [i for i in verifier.check_findings(c, report).issues if i.subject.startswith("F2 #1")]
    window = next(f for f in report.findings if f.kind == Kind.F2)
    assert window.deadline == date(2026, 9, 2)
    early = window.model_copy(update={"deadline": window.deadline.replace(day=1)})
    wrong = report.model_copy(update={"findings": [early if f is window else f for f in report.findings]})
    issues = [i for i in verifier.check_findings(c, wrong).issues if i.subject.startswith("F2 #1")]
    assert issues and "2026-09-02" in issues[0].what


@needs_text
def test_evidence_must_exist():
    c = case()
    report, _ = run_all(c)
    assert not any("S9" in i.what for i in verifier.check_findings(c, report).issues)
    first = report.findings[0]
    pointing = first.model_copy(update={"evidence": [*first.evidence, Evidence(doc_id="S9", line_no=3)]})
    v = verifier.check_findings(c, report.model_copy(update={"findings": [pointing, *report.findings[1:]]}))
    assert [i.severity for i in v.issues if "S9" in i.what] == ["error"]


@needs_text
def test_letters_with_made_up_amounts_tokens_or_promises_are_caught():
    c = case()
    report, letters = run_all(c)
    dispute = next(x for x in letters if x.kind == "dispute")
    assert verifier.check_letters(c, report, [dispute]).issues == []  # the honest letter passes
    promise = writer.Paragraph("We promise you will get $9,999.99 back for account [ACCT_1].")
    bad = dataclasses.replace(dispute, paragraphs=[*dispute.paragraphs, promise])
    issues = verifier.check_letters(c, report, [bad]).issues
    assert all(i.subject == "letter dispute" and i.severity == "error" for i in issues)
    said = " | ".join(i.what for i in issues)
    for needle in ("$9,999.99", "token", "we promise"):
        assert needle in said, f"nothing says {needle!r}: {said}"


@needs_text
def test_wonder_review_is_read_only_and_never_sees_names():
    c = case()
    report, letters = run_all(c)
    body = verifier.review_body(c, report, letters)
    assert body["model"] == "muse-wonder-1.0" and body["store"] is False
    sent = json.dumps(body)
    for private in ("Anna Sample", "100 Example Street", "LDH-000123"):
        assert private not in sent

    answer = {"items": [
        {"subject": "F3 #1", "verdict": "confirmed", "reason": "matches sheet 2"},
        {"subject": "letter dispute", "verdict": "problem", "reason": "line 2 says 2,887.50"}]}

    class Fake:  # SYNTHETIC transport: the same answer to any request
        def events(self, request):
            text = json.dumps(answer)
            return [{"type": "response.output_text.delta", "delta": text},
                    {"type": "response.completed", "response": {"id": "r", "usage": {}}}]

    v = verifier.model_review(MetaClient(transport=Fake(), record_to=None, journal=None), c, report, letters,
                              verifier.Verdict())
    assert v.model_notes == answer["items"]
    assert len(v.issues) == 1 and v.issues[0].severity == "note"  # a "problem" is a note, no finding is removed
    assert v.issues[0].subject == "letter dispute" and "line 2 says 2,887.50" in v.issues[0].what
    assert v.ok


def _saved_case(tmp_path, monkeypatch, today):
    """A saved case opened on the day `today`: the app reads the case on that day, so the clock is fixed here."""
    c = case()
    run = tmp_path / "r1"
    run.mkdir()
    (run / "case.json").write_text(c.model_dump_json())
    (run / "report.json").write_text(checks.run(c).model_dump_json())
    monkeypatch.setattr(app_module, "RUNS", tmp_path)
    monkeypatch.setattr(app_module, "_today", lambda case_id, loaded: today)
    return TestClient(app_module.app)


@needs_text
def test_reminder_calendar_file(tmp_path, monkeypatch):
    res = _saved_case(tmp_path, monkeypatch, date(2026, 6, 15)).get("/cases/r1/reminder.ics")
    assert res.headers["content-type"].startswith("text/calendar")
    assert "DTSTART;VALUE=DATE:20260902" in res.text and "TRIGGER:-P7D" in res.text


@needs_text
def test_a_comma_in_the_reminder_title_is_escaped_for_the_calendar(tmp_path, monkeypatch):
    client = _saved_case(tmp_path, monkeypatch, date(2026, 6, 15))
    monkeypatch.setattr(app_module, "_apply_title", lambda _: "Last day to apply, check it with the hospital")
    assert "SUMMARY:Last day to apply\\, check it with the hospital" in client.get("/cases/r1/reminder.ics").text


@needs_text
def test_no_reminder_for_a_date_gone_by(tmp_path, monkeypatch):
    assert _saved_case(tmp_path, monkeypatch, date(2026, 9, 3)).get("/cases/r1/reminder.ics").status_code == 404


# --- confidence (Я11) -------------------------------------------------------------------------

@needs_text
def test_every_shown_finding_gets_a_confidence_and_clean_ones_are_sure():
    c = case()
    r, _ = pipeline.check_and_hold(c, checks.run(c))
    assert r.findings and all(f.confidence is not None for f in r.findings + r.worth_asking)
    assert all(f.severity == "high" and f.confidence >= verifier.CONFIRMED for f in r.findings)


@needs_text
def test_a_model_objection_makes_a_finding_borderline_without_its_sum():
    c = case()
    r = checks.run(c)
    v = verifier.verify(c, r, writer.all_letters(c, r))
    names = verifier.subjects(r)
    target = next(f for f in r.findings if f.amount)
    v.model_notes = [{"subject": names[id(target)], "verdict": "problem", "reason": "line 2 is a different service"}]
    graded = verifier.grade(c, r, v, names)
    moved = next(f for f in graded.worth_asking if f.kind == target.kind and "amount_if_confirmed" in f.math)
    assert moved.severity == "borderline" and moved.amount is None and moved.confidence == 0.6
    assert moved.math["amount_if_confirmed"] == str(target.amount) and "Muse Wonder" in moved.math["why_unsure"]
    assert graded.total_may_come_off == r.total_may_come_off - target.amount
    # must differ: the same finding confirmed by the model stays with its sum
    v.model_notes = [{"subject": names[id(target)], "verdict": "confirmed", "reason": "ok"}]
    kept = next(f for f in verifier.grade(c, r, v, names).findings if f.title == target.title)
    assert kept.amount == target.amount and kept.confidence == 1.0


@needs_text
def test_unknown_savings_lower_confidence_on_free_care():
    c = case()
    r = checks.run(c)
    v = verifier.verify(c, r, writer.all_letters(c, r))
    f = r.findings[0].model_copy(update={"kind": Kind.F1, "policy_refs": ["memorial-2026-05#liquid-assets"]})
    c.profile.liquid_assets = None
    conf, why = verifier.confidence(c, f, "F1 #9", v)
    assert conf == 0.8 and "savings" in why[0]


@needs_text
def test_muse_wonder_review_runs_only_with_the_flag(monkeypatch):
    c = case()
    r = checks.run(c)
    target = next(f for f in r.findings if f.amount)
    name = verifier.subjects(r)[id(target)]

    class Wonder:  # SYNTHETIC answer in the recorded shape
        calls = 0

        def events(self, body):
            Wonder.calls += 1
            assert body["model"] == "muse-wonder-1.0" and body["store"] is False
            text = json.dumps({"items": [{"subject": name, "verdict": "problem", "reason": "different service"}]})
            return [{"type": "response.output_text.delta", "delta": text},
                    {"type": "response.completed", "response": {"id": "resp_SYNTHETIC", "usage": {}}}]

    client = MetaClient(transport=Wonder(), record_to=None, journal=None)
    monkeypatch.delenv(pipeline.WONDER_REVIEW, raising=False)
    shown, _ = pipeline.check_and_hold(c, r, client)
    assert Wonder.calls == 0 and any(f.title == target.title for f in shown.findings)
    monkeypatch.setenv(pipeline.WONDER_REVIEW, "1")
    shown, verdict = pipeline.check_and_hold(c, checks.run(c), client)
    assert Wonder.calls == 1 and verdict.model_notes
    moved = next(f for f in shown.worth_asking if f.kind == target.kind and "amount_if_confirmed" in f.math)
    assert moved.amount is None and "Muse Wonder" in moved.math["why_unsure"]


@needs_text
def test_a_failed_wonder_review_keeps_the_code_result_and_says_so(monkeypatch):
    from billradar.meta_client import MetaAPIError
    c = case()

    class Down:
        def events(self, body):
            raise MetaAPIError("HTTP 503: SYNTHETIC outage")

    monkeypatch.setenv(pipeline.WONDER_REVIEW, "1")
    shown, verdict = pipeline.check_and_hold(c, checks.run(c), MetaClient(transport=Down(), record_to=None, journal=None))
    plain, _ = pipeline.check_and_hold(c, checks.run(c))
    assert [f.title for f in shown.findings] == [f.title for f in plain.findings]
    assert any(i.subject == "model review" and i.what.startswith("Muse Wonder review did not run")
               and i.severity == "note" for i in verdict.issues)


def test_the_review_note_names_the_model_that_really_ran():
    assert verifier.checker_name(MetaClient(transport=object(), record_to=None, journal=None)) == "Muse Wonder"


def test_a_second_read_that_calls_a_present_paper_missing_is_overruled_by_code():
    """The second read once wrote "References sheet S10 which does not exist in case documents" while S10 was in the very
    case it got: code checks that claim, the finding keeps its confidence, and the note says why."""
    import json
    from billradar import example, pipeline, verifier, writer
    run = example.run_recorded(example.PACK, example.EXAMPLE_ID)
    case, report = run.case, run.report
    assert "S10" in {d.doc_id for d in case.documents}

    class Client:
        model = "muse-wonder-1.0"
        def respond(self, body, label=""):
            items = [{"subject": "E2 #1 on S10", "verdict": "problem",
                      "reason": "References sheet S10 which does not exist in case documents."},
                     {"subject": "F1 #1 on D1", "verdict": "problem", "reason": "D1 balance differs from the math."}]
            return type("R", (), {"text": json.dumps({"items": items}), "usage": {}, "seconds": 0.0, "replayed": True})()

    v = verifier.model_review(Client(), case, report, writer.all_letters(case, report), verifier.verify(case, report, []))
    by = {i["subject"]: i for i in v.model_notes}
    assert by["E2 #1 on S10"]["verdict"] == "overruled" and "S10 is in the case" in by["E2 #1 on S10"]["code_check"]
    assert by["F1 #1 on D1"]["verdict"] == "problem"  # must differ: a claim code cannot check stays the model's
