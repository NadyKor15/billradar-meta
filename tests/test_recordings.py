"""What a recording keeps: enough to replay, and not the model's encrypted reasoning."""

import json
from pathlib import Path

import pytest

from billradar import meta_client as mc

RECORDINGS = Path(__file__).parent / "fixtures" / "recordings"


class Live:
    live = True

    def events(self, body):
        return [{"type": "response.output_text.delta", "delta": "{}"},
                {"type": "response.completed", "response": {"id": "r1", "usage": {}, "output": [
                    {"type": "reasoning", "encrypted_content": "abc", "summary": []},
                    {"type": "message", "content": []}]}}]


def test_no_recording_holds_encrypted_reasoning():
    files = [p for p in RECORDINGS.iterdir() if p.is_file()]
    assert len(files) > 50 and not [p.name for p in files if b"encrypted_content" in p.read_bytes()]


def test_a_new_recording_drops_it_and_keeps_the_rest(tmp_path):
    body = {"model": "muse-spark-1.3", "store": False, "input": []}
    client = mc.MetaClient(transport=Live(), record_to=tmp_path, journal=None)
    assert client.respond(body).text == "{}"
    saved = (tmp_path / mc.recording_name(body)).read_text()
    assert "encrypted_content" not in saved
    last = json.loads(saved.splitlines()[-1])
    assert [o["type"] for o in last["response"]["output"]] == ["reasoning", "message"]  # must light: only the field went


class Stream:
    status_code = 200
    headers: dict = {}
    text = ""

    def __init__(self, *events):
        self.lines = [f"data: {json.dumps(e)}".encode() for e in events]

    def iter_lines(self):
        return iter(self.lines)


DONE = {"type": "response.completed", "response": {"id": "r2", "usage": {}, "output": []}}
FAILED = {"type": "error", "code": "server_error", "message": "The model failed to generate a response."}
BODY = {"model": "muse-spark-1.3", "store": False, "input": []}


def transport(tmp_path, monkeypatch, answers):
    monkeypatch.setattr(mc.time, "sleep", lambda _: None)
    monkeypatch.setattr(mc.requests, "post", lambda *a, **k: answers.pop(0))
    return mc.LiveTransport("k", attempts=2, ledger=mc.SpendLedger(tmp_path / "spend.jsonl", cap=5))


def test_a_model_that_failed_mid_answer_is_asked_again_and_both_tries_are_counted(tmp_path, monkeypatch):
    t = transport(tmp_path, monkeypatch, [Stream(FAILED), Stream(DONE)])
    assert t.events(BODY)[-1]["type"] == "response.completed"
    notes = [json.loads(ln)["note"] for ln in (tmp_path / "spend.jsonl").read_text().splitlines()]
    assert notes[:2] == ["reserve muse-spark-1.3", "reserve muse-spark-1.3 again"]


def test_when_it_fails_again_the_error_reaches_the_caller(tmp_path, monkeypatch):
    t = transport(tmp_path, monkeypatch, [Stream(FAILED), Stream(FAILED)])
    with pytest.raises(mc.MetaAPIError, match="server_error"):
        mc.collect(t.events(BODY))


def test_a_stream_cut_without_an_error_is_not_asked_again(tmp_path, monkeypatch):
    answers = [Stream({"type": "response.output_text.delta", "delta": "x"}), Stream(DONE)]
    t = transport(tmp_path, monkeypatch, answers)
    with pytest.raises(mc.MetaAPIError, match="without a final event"):
        mc.collect(t.events(BODY))
    assert len(answers) == 1  # must differ: nothing says the model failed, and it may have worked


class Watching:
    """A live transport that looks at the journal at the moment the request leaves."""
    live = True

    def __init__(self, journal):
        self.journal, self.seen = journal, None

    def events(self, body):
        self.seen = self.journal.read_text().splitlines() if self.journal.exists() else []
        return [{"type": "response.output_text.delta", "delta": "{}"},
                {"type": "response.completed", "response": {"id": "r3", "usage": {}, "output": []}}]


PRIVATE = "SYNTHETIC name Daniela, member 39132817396"
ASKED = {"model": "muse-spark-1.3", "store": False, "input": [{"role": "user", "content": [
    {"type": "input_text", "text": PRIVATE}, {"type": "input_image", "image_url": "data:image/jpeg;base64,QUJD"}]}]}


def test_the_journal_says_a_request_left_before_any_answer_and_holds_no_content(tmp_path):
    journal = tmp_path / "requests.jsonl"
    t = Watching(journal)
    client = mc.MetaClient(transport=t, record_to=None, journal=journal)
    sent = json.dumps(ASKED)
    result = client.respond(ASKED, label="spark:read")
    assert json.dumps(ASKED) == sent and result.text == "{}"  # the request and the answer are what they were
    assert len(t.seen) == 1  # already there while the request is out
    line = json.loads(t.seen[0])
    assert set(line) == {"at", "event", "live", "label", "model", "key", "images", "files"} and line["event"] == "sent"
    assert line["key"] == mc.request_key(ASKED) and line["images"] == 1
    lines = journal.read_text().splitlines()
    answered = json.loads(lines[1])
    assert len(lines) == 2 and answered["key"] == line["key"] and answered["event"] == "answered"  # the call's own line follows
    text = journal.read_text()
    assert PRIVATE not in text and "QUJD" not in text and "Authorization" not in text
    assert len(client.calls) == 1  # the receipt counts one call, as before


def test_a_replay_writes_no_line_about_a_request_that_never_left(tmp_path):
    journal = tmp_path / "requests.jsonl"

    class Replay(Watching):
        live = False

    client = mc.MetaClient(transport=Replay(journal), record_to=None, journal=journal)
    client.respond(ASKED, label="spark:read")
    assert [json.loads(ln).get("event") for ln in journal.read_text().splitlines()] == ["answered"]  # must differ from the live run


def test_a_recorded_answer_used_twice_is_counted_once():
    from billradar import receipt
    call = {"label": "spark:read", "model": "muse-spark-1.3", "response_id": "r1", "usd": 0.03, "usage": {}}
    other = {**call, "response_id": "r2", "usd": 0.01}
    built = receipt.build([call, {**call, "label": "spark:read-3"}, other])
    assert len(built["rows"]) == 2 and built["total_usd"] == 0.04
    assert receipt.build([call, other])["total_usd"] == 0.04  # must differ: two answers stay two


def test_a_case_being_checked_leaves_the_server_answering(monkeypatch, tmp_path):
    """The live screen reads /calls while a case runs: the run must not hold the event loop."""
    import asyncio
    import threading
    import httpx
    from billradar import app as app_module, highlight, pipeline, policy, providers
    done = threading.Event()
    order = []

    def slow_run(*a, **k):
        done.wait(5)
        order.append("run ended")
        raise pipeline.RealDataGate("stop here")

    monkeypatch.setattr(pipeline, "prepare", slow_run)
    monkeypatch.setattr(providers, "make_client", lambda: type("C", (), {"live": False})())
    monkeypatch.setattr(app_module, "RUNS", tmp_path)
    form = {"policy_id": next(iter(policy.available())), "household_size": "3", "annual_income": "50000"}

    async def both():
        transport = httpx.ASGITransport(app=app_module.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            case = asyncio.create_task(c.post("/cases", data=form, files={"photos": ("a.jpg", b"x", "image/jpeg")}))
            await asyncio.sleep(0.2)
            r = await c.get("/privacy", headers={"accept": "text/html"})
            order.append("page answered")
            done.set()
            await case
            return r

    assert asyncio.run(both()).status_code == 200
    assert order == ["page answered", "run ended"]

