"""Muse Spark files the appeal from the app: fill, the family looks, the family presses Send. Every run here is
SYNTHETIC: no model and no browser were started."""

import json
import time

import pytest
from fastapi.testclient import TestClient

from billradar import app as app_module
from billradar import appeal, example, meta_client as mc, pipeline, portal_job, submit_agent


class Driver:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def result(phase="fill", **kw):
    r = submit_agent.AgentRun(phase)
    r.stopped_before_submit = phase == "fill"
    r.filled = {"member_id": "[MEMBER_1]"}
    r.screenshots = [b"\x89PNG-one", b"\x89PNG-two"]
    for k, v in kw.items():
        setattr(r, k, v)
    return r


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "RUNS", tmp_path)
    monkeypatch.setattr(portal_job, "_jobs", {})
    monkeypatch.setattr(portal_job, "RECORDED", tmp_path / "no-recording")
    monkeypatch.setattr(portal_job, "make_driver", Driver)
    run = example.run_appeal_example("c1")
    run.case.case_id = "c1"
    pipeline.save(run, tmp_path / "c1")
    (tmp_path / "c1" / app_module.history.OWNER).unlink(missing_ok=True)
    key = appeal.letter_kind(appeal.denials(run.case)[0])
    class Live(mc.MetaClient):
        live = True
    monkeypatch.setattr(app_module.providers, "make_client", lambda: Live(transport=object(), record_to=None, journal=None))
    return TestClient(app_module.app), key, tmp_path / "c1", run.case


def wait(c, key, state):
    for _ in range(100):
        d = c.get(f"/cases/c1/appeals/{key}/agent").json()
        if d["state"] == state:
            return d
        time.sleep(0.02)
    raise AssertionError(d)


def test_the_agent_fills_and_waits_for_the_family(setup, monkeypatch):
    c, key, d, _ = setup
    calls = []
    monkeypatch.setattr(submit_agent, "run", lambda cl, dr, cs, v, phase, confirmed=False: calls.append((phase, confirmed)) or result())
    assert c.post(f"/cases/c1/appeals/{key}/agent").status_code == 202
    got = wait(c, key, "ready")
    assert got["filled"] == {"member_id": "[MEMBER_1]"} and got["shots"] == 2 and calls == [("fill", False)]
    assert c.get(f"/cases/c1/appeals/{key}/agent/shot/1.png").headers["content-type"] == "image/png"
    assert json.loads((d / "agent.json").read_text())["state"] == "ready"


def test_only_the_familys_press_sends_and_it_lands_in_the_tracker(setup, monkeypatch):
    c, key, d, _ = setup
    runs = iter([result(), result("submit", submitted=True, confirmation="SHP-1234", stopped_before_submit=False)])
    calls = []
    monkeypatch.setattr(submit_agent, "run", lambda cl, dr, cs, v, phase, confirmed=False: calls.append((phase, confirmed)) or next(runs))
    c.post(f"/cases/c1/appeals/{key}/agent")
    wait(c, key, "ready")
    r = c.post(f"/cases/c1/appeals/{key}/agent/send")
    assert r.status_code == 200 and r.json()["state"] == "sent" and r.json()["confirmation"] == "SHP-1234"
    assert calls[-1] == ("submit", True)
    tr = appeal.Tracker.load(d)
    assert tr.items[key].status == "sent" and tr.items[key].confirmation == "SHP-1234"


def test_send_before_fill_is_refused(setup):
    c, key, _, _ = setup
    assert c.post(f"/cases/c1/appeals/{key}/agent/send").status_code == 409


def test_a_form_that_does_not_match_cannot_be_sent(setup, monkeypatch):
    c, key, _, _ = setup
    monkeypatch.setattr(submit_agent, "run", lambda *a, **k: result(mismatches=["member_id: asked x, page has y"]))
    c.post(f"/cases/c1/appeals/{key}/agent")
    assert wait(c, key, "failed")["mismatches"]
    assert c.post(f"/cases/c1/appeals/{key}/agent/send").status_code == 409


def test_an_unknown_appeal_is_404(setup):
    c, _, _, _ = setup
    assert c.post("/cases/c1/appeals/nope/agent").status_code == 404


def test_a_recording_is_shown_and_sends_nothing(setup, tmp_path, monkeypatch):
    c, key, d, _ = setup
    rec = tmp_path / "recorded"
    rec.mkdir()
    (rec / "run.json").write_text(json.dumps({"steps": 7, "filled": {"member_id": "[MEMBER_1]"}}))
    (rec / "0.png").write_bytes(b"\x89PNG-rec")
    monkeypatch.setattr(portal_job, "RECORDED", rec)
    monkeypatch.setattr(app_module.providers, "make_client", lambda: mc.MetaClient(transport=object(), record_to=None, journal=None))
    monkeypatch.setattr(submit_agent, "run", lambda *a, **k: pytest.fail("no agent runs on a recording"))
    got = c.post(f"/cases/c1/appeals/{key}/agent").json()
    assert got["state"] == "ready" and got["replayed"] is True and got["steps"] == 7
    sent = c.post(f"/cases/c1/appeals/{key}/agent/send").json()
    assert "nothing was sent" in sent["note"]
    assert appeal.Tracker.load(d).items.get(key) is None or appeal.Tracker.load(d).items[key].status == "prepared"


def test_no_recording_and_no_model_says_so(setup, monkeypatch):
    c, key, _, _ = setup
    monkeypatch.setattr(app_module.providers, "make_client", lambda: mc.MetaClient(transport=object(), record_to=None, journal=None))
    monkeypatch.setattr(portal_job, "make_driver", lambda: pytest.fail("no browser without a model"))
    r = c.post(f"/cases/c1/appeals/{key}/agent")
    assert r.status_code == 503


def test_a_public_copy_never_opens_a_browser(setup, monkeypatch):
    c, key, _, _ = setup
    monkeypatch.setenv("BILLRADAR_PUBLIC", "1")
    assert c.post(f"/cases/c1/appeals/{key}/agent").status_code == 503


def test_a_public_copy_plays_the_recording_even_with_a_model_connected(setup, tmp_path, monkeypatch):
    c, key, _, _ = setup
    rec = tmp_path / "recorded"
    rec.mkdir()
    (rec / "run.json").write_text(json.dumps({"steps": 7, "filled": {"member_id": "[MEMBER_1]"}}))
    (rec / "0.png").write_bytes(b"\x89PNG-rec")
    monkeypatch.setattr(portal_job, "RECORDED", rec)
    monkeypatch.setenv("BILLRADAR_PUBLIC", "1")
    monkeypatch.setattr(portal_job, "make_driver", lambda: pytest.fail("no browser on a public copy"))
    monkeypatch.setattr(submit_agent, "run", lambda *a, **k: pytest.fail("no agent runs on a recording"))
    got = c.post(f"/cases/c1/appeals/{key}/agent")
    assert got.status_code == 202 and got.json()["state"] == "ready" and got.json()["replayed"] is True
    assert "nothing was sent" in c.post(f"/cases/c1/appeals/{key}/agent/send").json()["note"]
