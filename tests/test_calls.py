"""/calls: the journal as written, on this machine only. Every line here is SYNTHETIC: no model was called."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from billradar import app as app_module, meta_client

LINE = {"at": "2026-11-02T03:00:00+00:00", "label": "spark:read", "model": "muse-spark-1.3", "key": "abc", "live": True,
        "response_id": "resp_1", "seconds": 12.34, "usage": {"input_tokens": 7}, "usd": 0.123456}


@pytest.fixture
def client(tmp_path, monkeypatch):
    journal = tmp_path / "requests.jsonl"
    monkeypatch.setattr(meta_client, "JOURNAL", journal)
    monkeypatch.delenv("BILLRADAR_PUBLIC", raising=False)
    journal.write_text(json.dumps(LINE) + "\n")
    return TestClient(app_module.app), journal


def test_the_log_gives_the_values_as_written(client):
    c, _ = client
    assert c.get("/calls", headers={"accept": "text/html"}).status_code == 200
    r = c.get("/calls.json").json()["rows"][0]
    assert (r["response_id"], r["model"], r["seconds"], r["usd"], r["live"], r["step"]) == \
        ("resp_1", "muse-spark-1.3", 12.34, 0.123456, True, "Read every sheet")
    assert "key" not in r


def test_a_sent_call_and_its_answer_are_one_line(client):
    c, journal = client
    sent = {"at": "t", "event": "sent", "label": "spark:read", "model": "muse-spark-1.3", "key": "k2"}
    journal.write_text(json.dumps(sent) + "\n")
    row = c.get("/calls.json").json()["rows"][0]
    assert row["state"] == "sent" and row["live"] is True  # the line is written only when a request really leaves
    with journal.open("a") as f:
        f.write(json.dumps({"at": "t2", "label": "spark:read", "model": "muse-spark-1.3", "key": "k2", "live": True, "response_id": "resp_2", "seconds": 1.5}) + "\n")
    got = c.get("/calls.json").json()
    assert got["seen"] == 1 and got["rows"][0]["state"] == "answered" and got["rows"][0]["response_id"] == "resp_2"


def test_the_page_starts_from_now_and_all_shows_the_history(client):
    c, _ = client
    assert 'data-start="1"' in c.get("/calls", headers={"accept": "text/html"}).text
    assert 'data-start="0"' in c.get("/calls?all=1", headers={"accept": "text/html"}).text


def test_new_lines_come_after_what_was_seen(client):
    c, journal = client
    assert c.get("/calls.json").json()["seen"] == 1
    with journal.open("a") as f:
        f.write(json.dumps(LINE | {"response_id": "resp_2", "live": False}) + "\n")
    got = c.get("/calls.json?after=1").json()
    assert got["seen"] == 2 and [r["response_id"] for r in got["rows"]] == ["resp_2"]
    assert got["rows"][0]["live"] is False


def test_nothing_outside_the_list_of_fields_reaches_the_page(client):
    c, journal = client
    journal.write_text(json.dumps(LINE | {"authorization": "Bearer SECRET-X", "body": "SECRET-Y", "headers": {"x": "SECRET-Z"}}) + "\n")
    assert "SECRET" not in c.get("/calls", headers={"accept": "text/html"}).text
    assert "SECRET" not in c.get("/calls.json").text


def test_a_line_without_a_model_is_left_out(client):
    c, journal = client
    journal.write_text(json.dumps({"at": "x", "label": "tavily", "provider": "tavily"}) + "\n")
    assert c.get("/calls.json").json() == {"seen": 0, "rows": []}


def test_a_public_copy_has_no_such_page(client, monkeypatch):
    c, _ = client
    monkeypatch.setenv("BILLRADAR_PUBLIC", "1")
    assert c.get("/calls", headers={"accept": "text/html"}).status_code == 404
    assert c.get("/calls.json").status_code == 404


def test_no_page_links_to_it(client):
    c, _ = client
    for address in ("/how", "/agents", "/upload", "/privacy"):
        assert 'href="/calls' not in c.get(address, headers={"accept": "text/html"}).text


def test_the_wait_on_upload_is_honest_and_a_refusal_gives_the_page_back():
    page = TestClient(app_module.app).get("/upload", headers={"accept": "text/html"}).text
    assert "Covering your papers on this computer. This takes a few minutes." in page
    assert "%" not in page.split('id="upload-busy"')[1].split("</p>")[0]
    script = page.split("The check runs on the server")[1]
    assert "refuse(" in script and "idle()" in script and "pageshow" in script
    assert 'typeof words === "string"' in script  # a refusal with a list of fields must not print [object Object]
    assert TestClient(app_module.app).post("/cases", data={}).status_code == 422


def test_an_example_reads_as_a_recording_with_plain_step_names(tmp_path):
    (tmp_path / "example-video").mkdir()
    (tmp_path / "example-video" / "receipt.json").write_text(json.dumps({"rows": [{"step": "sam:video:sheet of paper"}], "replayed": False}))
    (tmp_path / "c1").mkdir()
    (tmp_path / "c1" / "receipt.json").write_text(json.dumps({"rows": [{"step": "spark:read"}], "replayed": False}))
    video = app_module._receipt(tmp_path / "example-video")
    assert video["replayed"] is True and video["rows"][0]["step"] == "Follow sheets through the video"
    assert app_module._receipt(tmp_path / "c1")["replayed"] is False  # must light: a real run stays as it is


def test_a_letter_holds_no_note_to_the_family():
    from billradar import writer
    assert "sign before" not in (Path(writer.__file__).read_text())

