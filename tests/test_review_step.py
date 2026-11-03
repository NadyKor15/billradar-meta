"""The person's step between closing and sending: prepare, a look at the closed sheets, finish. Sample pile, scripted answers."""
import base64
import hashlib
import io
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from PIL import Image

from billradar import checks, pipeline, redact
from billradar.case import Profile
from billradar.example import PackAnswers
from billradar.meta_client import MetaClient
from billradar.policies import source

PACK = Path(__file__).resolve().parents[1] / "eval" / "packs" / "work" / "brs1-birth-all-errors"


class Spy:
    def __init__(self):
        self.answers = PackAnswers(PACK)
        self.models: list[str] = []
        self.images: list[bytes] = []
        self.bodies: list[str] = []

    def events(self, body: dict) -> list[dict]:
        self.models.append(body["model"])
        self.bodies.append(hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest())
        for item in body["input"]:
            for part in item.get("content", []) if isinstance(item.get("content"), list) else []:
                if part.get("type") == "input_image":
                    self.images.append(base64.b64decode(part["image_url"].split(",", 1)[1]))
        return self.answers.events(body)


def client(spy: Spy) -> MetaClient:
    return MetaClient(transport=spy, record_to=None, journal=None)


def meta() -> dict:
    return json.loads((PACK / "profile.json").read_text())


def photos(spy: Spy) -> list[bytes]:
    return [p.read_bytes() for p in spy.answers.photos[:3]]


def prepared(spy: Spy) -> pipeline.Prepared:
    return pipeline.prepare(client(spy), photos(spy), [], Profile.model_validate(meta()["profile"]),
                            fictional=True, private=True)


def finished(spy: Spy, prep: pipeline.Prepared, approved=None) -> pipeline.CaseRun:
    m = meta()
    return pipeline.finish(client(spy), prep, approved, m["policy_id"], m.get("letterhead", ""), date.fromisoformat(m["today"]), PACK.name)


def test_before_the_button_only_the_sheet_finder_is_called():
    spy = Spy()
    prepared(spy)
    assert set(spy.models) == {"sam-3.1"}


def test_a_kept_sheet_does_not_leave():
    spy = Spy()
    prep = prepared(spy)
    kept = prep.sheets[1]
    gone = pipeline._jpeg(kept.image)
    finished(spy, prep, {s.doc_id for s in prep.sheets} - {kept.doc_id})
    assert gone not in spy.images
    assert pipeline._jpeg(prep.sheets[0].image) in spy.images  # must light: the others left


def test_a_kept_sheet_is_a_sheet_that_was_not_sent():
    spy = Spy()
    prep = prepared(spy)
    kept = prep.sheets[1].doc_id
    run = finished(spy, prep, {s.doc_id for s in prep.sheets} - {kept})
    assert kept in run.report.not_sent
    assert any(kept in p and "kept on this computer" in p for p in run.problems)


def test_nothing_approved_sends_nothing_readable():
    spy = Spy()
    prep = prepared(spy)
    finished(spy, prep, set())
    assert all(pipeline._jpeg(s.image) not in spy.images for s in prep.sheets)


def test_run_asks_the_same_as_prepare_and_finish():
    one, two = Spy(), Spy()
    m = meta()
    pipeline.run(client(one), photos(one), [], Profile.model_validate(m["profile"]), m["policy_id"], m.get("letterhead", ""),
                 date.fromisoformat(m["today"]), PACK.name, fictional=True, private=True)
    finished(two, prepared(two))
    assert one.bodies == two.bodies


def test_the_step_survives_a_restart(tmp_path):
    spy = Spy()
    prep = prepared(spy)
    prep.request = {"policy_id": "memorial-2026-05"}
    direct = finished(Spy(), prepared(Spy()))
    pipeline.save_prepared(prep, tmp_path)
    redact._reads.clear()
    redact._read_backs.clear()
    back = pipeline.load_prepared(tmp_path)
    assert back.request == prep.request
    assert [s.doc_id for s in back.sheets] == [s.doc_id for s in prep.sheets]
    assert back.vault.secrets == prep.vault.secrets
    assert all(a.image.tobytes() == b.image.tobytes() for a, b in zip(prep.sheets, back.sheets))  # what was checked is what leaves
    run = finished(Spy(), back)
    assert run.report.total_may_come_off == direct.report.total_may_come_off
    assert run.case.profile.local.tokens == direct.case.profile.local.tokens


def test_nothing_stays_after_the_case_is_done(tmp_path):
    prep = prepared(Spy())
    pipeline.save_prepared(prep, tmp_path)
    assert (tmp_path / pipeline.PREPARED / "state.json").exists()
    pipeline.drop_prepared(tmp_path)
    assert not (tmp_path / pipeline.PREPARED).exists()


def test_only_private_mode_waits_for_a_person(tmp_path):
    spy = Spy()
    prep = pipeline.prepare(client(spy), photos(spy), [], Profile.model_validate(meta()["profile"]), fictional=True)
    with pytest.raises(pipeline.RealDataGate):
        pipeline.save_prepared(prep, tmp_path)


def test_a_kept_sheet_is_not_asked_for_again(monkeypatch):
    spy = Spy()
    prep = prepared(spy)
    kept = prep.sheets[1].doc_id
    prep.printed_money[kept] = True
    run = finished(spy, prep, {s.doc_id for s in prep.sheets} - {kept})
    said = [f.math.get("why_unsure", "") for f in run.report.findings + run.report.worth_asking]
    assert not any(f"sheet {kept[1:]} " in s and "new photo" in s for s in said)


def test_a_sheet_kept_by_choice_says_so_and_a_withheld_one_asks_for_a_photo():
    finding = checks.Finding(kind=checks.Kind.E1, title="x", detail="y", amount=Decimal("5.00"))
    report = checks.Report(case_id="c", policy_id="p", fpl_pct=Decimal(100), findings=[finding], no_money=[], held_back=[], total_may_come_off=Decimal("5.00"),
                           apply_by=None, apply_by_sure=False)
    out = pipeline.sheets_not_sent(report, ["S1", "S2"], ["S1", "S2"], ["S2"])
    text = json.dumps(out.model_dump(mode="json"))
    assert "sheet 1 was not sent" in text and "take a new photo" in text
    assert "sheet 2 stayed on your computer by your choice" in text
    assert out.not_sent == ["S1", "S2"]


def test_a_case_without_the_policy_text_stops_and_says_what_to_do(monkeypatch, tmp_path):
    spy = Spy()
    prep = prepared(spy)
    monkeypatch.setattr(source, "CACHE", tmp_path)
    with pytest.raises(source.PolicyMissing, match="fetch_policies"):  # its findings would be held back with no word said
        finished(spy, prep)
