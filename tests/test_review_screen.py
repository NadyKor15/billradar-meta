"""The screen where a person looks at every covered sheet: what the routes let go, and what they keep."""

import json
import re
from datetime import date

import pytest
from fastapi.testclient import TestClient

from billradar import app as app_module, history, pipeline
from billradar.case import Profile
from tests.test_review_step import PACK, Spy, client as spy_client, meta, photos

CASE = "c0123456789"


_closed: list = []


@pytest.fixture
def prepared_files(tmp_path_factory):
    """The sample pile closed once, on disk: a person may come back to it after a restart. Built inside a test, where the
    recorded local reader is in place."""
    if not _closed:
        out = tmp_path_factory.mktemp("prepared")
        spy = Spy()
        prep = pipeline.prepare(spy_client(spy), photos(spy), [], Profile.model_validate(meta()["profile"]), fictional=True, private=True)
        prep.request = {"policy_id": meta()["policy_id"], "letterhead": meta().get("letterhead", ""), "fictional": True, "today": meta()["today"]}
        pipeline.save_prepared(prep, out)
        _closed.append(out / pipeline.PREPARED)
    return _closed[0]


@pytest.fixture
def web(prepared_files, tmp_path, monkeypatch):
    import shutil

    d = tmp_path / CASE
    d.mkdir()
    shutil.copytree(prepared_files, d / pipeline.PREPARED)
    history.issue_token(d)
    spy = Spy()
    monkeypatch.setattr(app_module, "RUNS", tmp_path)
    monkeypatch.setattr(app_module.providers, "make_client", lambda: spy_client(spy))
    c = TestClient(app_module.app)
    c.spy, c.d = spy, d
    return c


def sheet_ids(c) -> list[str]:
    return re.findall(r'name="([SD][\d.]+)" value="send"', c.get(f"/cases/{CASE}/review").text)


def test_the_screen_says_what_the_decision_says(web):
    html = web.get(f"/cases/{CASE}/review").text.replace("&#39;", "'")
    assert "Check every covered sheet before it leaves" in html
    assert "Your family's names, IDs, addresses, phone numbers and account numbers are covered on this computer." in html
    assert "Doctors and hospitals stay visible because the checks and letters need them." in html
    assert "Before you press Send, only a heavily blurred copy with no readable text goes to Meta's SAM 3.1, to find the sheets." in html
    assert "The sheets themselves go only when you press Send." in html
    assert "nobody can read" not in html.lower() and "date" not in html.split("<form", 1)[1].split("</section>")[0].lower()
    assert f"Send {len(sheet_ids(web))} sheets to the models" in html


def test_nothing_goes_to_the_reader_before_the_button(web):
    assert sheet_ids(web)
    assert web.spy.models == []


def test_a_sheet_kept_here_does_not_leave(web):
    ids = sheet_ids(web)
    kept = ids[2]
    form = dict.fromkeys(ids, "send") | {kept: "keep"}
    closed = (web.d / pipeline.PREPARED / "sheets" / f"{kept}.png")
    assert web.post(f"/cases/{CASE}/send", data=form, follow_redirects=False).headers["location"] == f"/cases/{CASE}"
    assert not closed.exists()  # the step is over and nothing of it waits on the disk
    report = json.loads((web.d / "report.json").read_text())
    assert kept in report["not_sent"] and not set(ids) - {kept} & set(report["not_sent"])


def test_the_case_says_who_kept_the_sheet_and_shows_it(web):
    ids = sheet_ids(web)
    kept = ids[-1]
    web.post(f"/cases/{CASE}/send", data=dict.fromkeys(ids, "send") | {kept: "keep"})
    html = web.get(f"/cases/{CASE}").text
    assert f"You kept sheet {kept[1:]} here." in html and "We could not make sure" not in html
    assert web.get(f"/cases/{CASE}/sheet/{kept}.jpg").status_code == 200


def test_an_empty_form_sends_nothing_readable(web):
    ids = sheet_ids(web)
    web.post(f"/cases/{CASE}/send", data={})
    assert set(json.loads((web.d / "report.json").read_text())["not_sent"]) == set(ids)


def test_a_sheet_the_screen_never_offered_is_not_sent(web):
    state = json.loads((web.d / pipeline.PREPARED / "state.json").read_text())
    state["withheld"].append("S99")
    (web.d / pipeline.PREPARED / "state.json").write_text(json.dumps(state))
    html = web.get(f"/cases/{CASE}/review").text
    assert "Not sent" in html and "Take a new photo" in html and 'name="S99"' not in html


def test_the_second_press_lands_on_the_case(web):
    ids = sheet_ids(web)
    web.post(f"/cases/{CASE}/send", data=dict.fromkeys(ids, "send"))
    calls = len(web.spy.models)
    r = web.post(f"/cases/{CASE}/send", data=dict.fromkeys(ids, "send"), follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == f"/cases/{CASE}" and len(web.spy.models) == calls
    assert web.get(f"/cases/{CASE}/review", follow_redirects=False).headers["location"] == f"/cases/{CASE}"


def test_a_press_while_reading_is_refused(web):
    app_module._sending.add(CASE)
    try:
        r = web.post(f"/cases/{CASE}/send", data=dict.fromkeys(sheet_ids(web), "send"))
    finally:
        app_module._sending.discard(CASE)
    assert r.status_code == 409 and web.spy.models == []


def test_the_case_address_leads_to_the_screen_until_it_is_sent(web):
    assert web.get(f"/cases/{CASE}", follow_redirects=False).headers["location"] == f"/cases/{CASE}/review"


def test_the_list_of_cases_shows_what_waits(web):
    assert f"/cases/{CASE}/review" in web.get("/cases").text


def test_images_answer_and_are_not_cached(web):
    sid = sheet_ids(web)[0]
    for what, name in (("sheet", f"{sid}.png"), ("original", f"{sid}.png"), ("blurred", "0.png")):
        r = web.get(f"/cases/{CASE}/review/{what}/{name}")
        assert r.status_code == 200 and r.headers["content-type"] == "image/png" and r.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("what,name", [("sheet", "state.json"), ("sheet", "..%2Fstate.json"), ("vault", "S1.png"), ("original", "D1.1.png"), ("blurred", "S1.png")])
def test_only_the_images_are_served(web, what, name):
    assert web.get(f"/cases/{CASE}/review/{what}/{name}").status_code == 404


def test_someone_elses_case_does_not_open(web, monkeypatch):
    assert web.get("/cases/cffffffffff/review").status_code == 404
    monkeypatch.setenv("BILLRADAR_PUBLIC", "1")
    sid = "S1"
    assert web.get(f"/cases/{CASE}/review").status_code == 404
    assert web.get(f"/cases/{CASE}/review/sheet/{sid}.png").status_code == 404
    assert web.post(f"/cases/{CASE}/send", data={sid: "send"}).status_code == 404
    assert web.spy.models == []


def test_the_owner_on_a_public_copy_keeps_the_way_in(web, monkeypatch):
    monkeypatch.setenv("BILLRADAR_PUBLIC", "1")
    token = "t" * 20
    (web.d / history.OWNER).write_text(json.dumps({"token_sha256": history._hash(token), "created": "2026-11-02T00:00:00+00:00"}))
    web.cookies.set(history.cookie_name(CASE), token, path=f"/cases/{CASE}")
    assert web.get(f"/cases/{CASE}/review").status_code == 200


def test_a_restart_changes_nothing(web):
    """Everything is in files: another process reads the same screen and sends the same sheets."""
    first = web.get(f"/cases/{CASE}/review").text
    app_module._sending.clear()
    assert web.get(f"/cases/{CASE}/review").text == first
    assert web.post(f"/cases/{CASE}/send", data=dict.fromkeys(sheet_ids(web), "send"), follow_redirects=False).status_code == 303


def test_real_papers_do_not_go_to_a_live_model_from_this_screen(web, monkeypatch):
    state = json.loads((web.d / pipeline.PREPARED / "state.json").read_text())
    state["request"]["fictional"] = False
    (web.d / pipeline.PREPARED / "state.json").write_text(json.dumps(state))
    monkeypatch.setattr(app_module.providers, "make_client", lambda: type("Live", (), {"live": True})())
    r = web.post(f"/cases/{CASE}/send", data={"S1": "send"})
    assert r.status_code == 400 and web.spy.models == []


def test_the_live_limit_holds_on_the_second_step(web, monkeypatch):
    ids = sheet_ids(web)
    monkeypatch.setattr(app_module.providers, "make_client", lambda: type("Live", (), {"live": True})())
    monkeypatch.setattr(app_module, "_allow_live", lambda request: False)
    r = web.post(f"/cases/{CASE}/send", data=dict.fromkeys(ids, "send"))
    assert r.status_code == 429 and web.spy.models == []


@pytest.mark.parametrize("page", ["/safe", "/privacy"])
def test_the_public_pages_say_the_same(web, page):
    html = web.get(page).text.replace("&#39;", "'")
    assert "our family's names, IDs, addresses, phone numbers and account numbers are covered on this computer." in html
    assert "Doctors and hospitals stay visible because the checks and letters need them" in html
    assert "Before you press Send, only a heavily blurred copy with no readable text goes to Meta's SAM 3.1, to find the sheets." in html
    assert "The sheets themselves go only when you press Send" in html and "nobody can read" not in html.lower()


def test_deleting_takes_everything(web):
    assert web.post(f"/cases/{CASE}/delete", follow_redirects=False).headers["location"] == f"/cases?deleted={CASE}"
    assert not web.d.exists()


def test_the_pack_stays_what_the_test_needs():
    assert PACK.exists() and date.fromisoformat(meta()["today"])
