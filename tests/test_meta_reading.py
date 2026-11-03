"""What the first live run on Muse Spark showed (fictional pack, 2026-10-30): the fixes that came from it."""

from datetime import date
from decimal import Decimal

from billradar import checks, evaluation as ev, pipeline, reader
from billradar.checks import Finding, Kind
from tests.test_writer import case


def f2(severity=None):
    return Finding(kind=Kind.F2, title="Apply by Apr 01, 2026", detail="d", deadline=date(2026, 4, 1), severity=severity)


def base():
    return checks.run(case())


def test_a_deadline_marked_worth_checking_is_still_the_day_to_apply_by():
    """A date the reviewer doubts goes under "worth asking"; the family still needs it, in the calendar too."""
    r = base().model_copy(update={"findings": [f2("borderline")], "worth_asking": []})
    split = checks.split_borderline(r)
    assert split.apply_by == date(2026, 4, 1) and split.worth_asking[0].kind == Kind.F2


def test_a_sure_deadline_wins_over_a_doubted_one():
    r = base().model_copy(update={"findings": [f2()], "worth_asking": [
        Finding(kind=Kind.F2, title="Apply by Jan 01, 2026", detail="d", deadline=date(2026, 1, 1))]})
    assert checks.split_borderline(r).apply_by == date(2026, 4, 1)


def test_the_measurement_counts_a_date_shown_for_checking():
    r = base().model_copy(update={"findings": [], "worth_asking": [f2(), Finding(
        kind=Kind.F1, title="t", detail="d", math={"amount_if_confirmed": "10"})]})
    assert [(p.cls, p.deadline) for p in ev.from_report(r)] == [("F2", date(2026, 4, 1))]


def test_a_doubted_amount_is_not_counted_as_found():
    r = base().model_copy(update={"findings": [], "worth_asking": [Finding(kind=Kind.E1, title="t", detail="d", amount=Decimal(5))]})
    assert ev.from_report(r) == []


def test_the_reader_is_told_who_a_bill_is_from():
    assert "the organization that sends the bill" in reader.INSTRUCTIONS
    assert "not the place where a service was given" in reader.INSTRUCTIONS


def test_the_reader_keeps_the_balance_and_the_coupon_apart():
    assert "Never take it from the payment coupon" in reader.INSTRUCTIONS
    assert "belongs to the document as a whole, never to a line" in reader.INSTRUCTIONS  # S10
    assert 'take the last one. A printed "$0.00" is a real value' in reader.INSTRUCTIONS  # S12, S13


def _waiting(c, doc):
    """The bill prints: amount due from insurance = the whole balance; amount due from patient: blank."""
    return c.model_copy(deep=True, update={"documents": [
        d.model_copy(update={"due_from_insurance": d.patient_balance}) if d.doc_id == doc else d for d in c.documents]})


def test_a_balance_waiting_for_insurance_is_not_money_off():
    """Found on the first live pack: 90% of a baby's bill the hospital was asking the insurer for, not the family."""
    c = case()
    bills = checks.hospital_bills(c)
    target = bills[0].doc_id
    before = checks.run(c)
    after = checks.run(_waiting(c, target))
    assert any(e.doc_id == target for f in before.findings if f.amount for e in f.evidence)
    assert not any(e.doc_id == target for f in after.findings if f.amount for e in f.evidence)
    assert after.total_may_come_off < before.total_may_come_off


def test_the_family_is_told_what_is_waiting_for_insurance():
    c = case()
    target = checks.hospital_bills(c)[0].doc_id
    note = next(n for n in checks.run(_waiting(c, target)).no_money if "waiting for insurance" in n.title.lower())
    assert note.evidence[0].doc_id == target and "ask for the same help" in note.detail


def test_a_bill_the_family_owes_is_untouched():
    c = case()
    assert checks.run(c).total_may_come_off == checks.run(c.model_copy(deep=True)).total_may_come_off


def test_a_credit_already_inside_the_coupon_is_not_money_back():
    """20.00 - 40.00 + 26.72 + 712.31 = 719.03: the coupon has already taken it off."""
    from billradar.case import Line
    c = case()
    bill = c.bills()[0]
    lines = [Line(line_no=1, description="Copay paid twice", patient_responsibility=Decimal("-40.00")),
             Line(line_no=2, description="Visit", patient_responsibility=Decimal("759.03"))]
    c = c.model_copy(deep=True, update={"documents": [
        d.model_copy(update={"lines": lines, "amount_due_coupon": Decimal("719.03")}) if d.doc_id == bill.doc_id else d
        for d in c.documents]})
    r = checks.run(c)
    assert not [f for f in r.findings if f.kind == Kind.E3 and f.amount]
    credit = next(f for f in r.worth_asking if f.kind == Kind.E3)
    assert credit.amount is None and "taken off" in credit.title


def test_a_credit_line_on_a_balance_still_owed_is_a_thing_to_check():
    """The balance it adds up to has already taken it off (410 = 435 - 25): only a balance below zero is money back."""
    from billradar.case import Line
    c = case()
    bill = c.bills()[0]
    c = c.model_copy(deep=True, update={"documents": [
        d.model_copy(update={"lines": [Line(line_no=1, description="Overpaid", patient_responsibility=Decimal("-40.00"))],
                             "amount_due_coupon": None}) if d.doc_id == bill.doc_id else d for d in c.documents]})
    r = checks.run(c)
    assert not [f for f in r.findings if f.kind == Kind.E3]
    assert [f for f in r.worth_asking if f.kind == Kind.E3 and f.amount is None]


def test_no_sum_stands_on_a_bill_that_asks_the_family_for_nothing():
    """The whole class: whatever check found it, a sum on such a bill does not reach the total."""
    c = case()
    target = checks.hospital_bills(c)[0].doc_id
    r = checks.run(_waiting(c, target))
    for f in r.findings:
        if f.amount:
            assert target not in {e.doc_id for e in f.evidence}, f.title


def test_the_total_is_what_the_findings_add_up_to():
    r = checks.run(_waiting(case(), checks.hospital_bills(case())[0].doc_id))
    assert r.total_may_come_off == sum((f.amount for f in r.findings if f.amount), Decimal(0))


def test_the_checker_recounts_the_same_base():
    """The read-only checker must agree: it recomputes assistance on what the family is asked for."""
    from billradar import verifier
    c = case()
    target = checks.hospital_bills(c)[0].doc_id
    w = _waiting(c, target)
    assert verifier.verify(w, checks.run(w), []).ok


def test_the_measurement_counts_a_note_shown_without_a_sum():
    r = base().model_copy(update={"findings": [], "worth_asking": [
        Finding(kind=Kind.E3, title="Check the $40.00 credit stays taken off", detail="d")]})
    assert [p.cls for p in ev.from_report(r)] == ["E3"]


def test_the_reader_is_told_to_split_the_balance():
    assert "due_from_insurance" in reader.DOC_SCHEMA["required"]
    assert "AMOUNT DUE FROM INSURANCE" in reader.INSTRUCTIONS.upper()


def test_the_second_read_does_not_depend_on_the_case_id():
    """The example and its private twin are one recorded run."""
    from billradar import meta_client, verifier
    a, b = case(case_id="example"), case(case_id="example-private")
    assert (meta_client.request_key(verifier.review_body(a, checks.run(a), []))
            == meta_client.request_key(verifier.review_body(b, checks.run(b), [])))


def test_every_sealed_pack_loads():
    """Surgery and emergency packs have a patient, not a mother and a baby. Only profiles are read here, never keys."""
    import json
    from pathlib import Path

    from billradar.case import Profile
    packs = sorted((Path(__file__).parents[1] / "eval" / "packs" / "holdout").iterdir())
    assert len(packs) == 6
    for pack in packs:
        meta = json.loads((pack / "profile.json").read_text())
        assert meta["fictional"] is True and Profile.model_validate(meta["profile"]).people


def test_every_key_is_sealed():
    from pathlib import Path
    root = Path(__file__).parents[1] / "eval"
    assert all(ev.check_seal(k, root / "SEALED.txt") for k in (root / "packs" / "holdout").glob("*/key.json"))


def test_the_reader_is_told_to_say_when_a_sheet_cannot_be_read():
    assert "unreadable" in reader.DOC_SCHEMA["required"] and "guess nothing" in reader.INSTRUCTIONS.lower()


def test_a_sheet_the_model_cannot_read_is_named_for_a_new_photo():
    raw = {"doc_id": "S2", "kind": "other", "unreadable": True, "lines": []}
    docs, problems = reader.to_documents({"documents": [raw]}, {"S2": reader.Source.PAPER})
    assert docs[0].unreadable is True
    assert pipeline.unreadable_sheets(docs) == ["S2"]


def test_the_screen_gets_the_sheets_to_take_again(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from billradar import app as app_module
    monkeypatch.setattr(app_module, "RUNS", tmp_path)
    c = case(case_id="c1")
    run = pipeline.CaseRun(c, checks.run(c), [], [], unreadable=["S3"])
    pipeline.save(run, tmp_path / "c1")
    assert app_module._meta(tmp_path / "c1")["unreadable"] == ["S3"]
    assert TestClient(app_module.app).get("/cases/c1").status_code == 200

