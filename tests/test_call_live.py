"""The phone call helper in the app: a WebSocket from the browser, the ladder when nothing prepared fits. Consent comes
first, the case must be fictional, a live call is limited and paid for in the ledger, and audio is never kept.
The call is SYNTHETIC: no model was called and no audio exists, a few bytes of silence stand in for the stream."""

import json

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from billradar import app as app_module
from billradar import call_assist, callprep, checks, meta_client as mc, pipeline, web_answer
from tests import test_call_assist as tca
from tests.test_writer import case

PCM = b"\x00\x00" * 640  # 40 ms of silence


def saved(tmp_path, demo=True):
    c = case(case_id="c1")
    c.demo = demo
    pipeline.save(pipeline.CaseRun(c, checks.run(c), [], []), tmp_path / "c1")
    return c


class Rt:
    """Stands in for the realtime stream: takes the frames, gives the recorded turns of a synthetic call."""

    last = None

    def __init__(self, *a, **k):
        Rt.last = self
        self.frames = []

    def events(self, hs, frames):
        self.frames = list(frames)
        yield from tca.CALL


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "RUNS", tmp_path)
    monkeypatch.setattr(app_module, "_live_hits", type(app_module._live_hits)(app_module._live_hits.default_factory))
    Rt.last = None
    c = saved(tmp_path)
    sheet = callprep.build(c, checks.run(c), "hospital")
    spark = mc.MetaClient(transport=tca.FakeSpark(sheet), record_to=None, journal=None)
    monkeypatch.setattr(app_module.providers, "make_client", lambda: spark)
    monkeypatch.setattr(app_module, "_sample_client", lambda: spark)
    monkeypatch.setattr(app_module, "_realtime", lambda client: Rt())
    return TestClient(app_module.app)


def play(ws):
    ws.send_json({"type": "start", "lang": "en", "consent": True})
    assert ws.receive_json()["kind"] == "started"
    ws.send_bytes(PCM)
    ws.send_bytes(PCM)
    ws.send_json({"type": "stop"})
    out = []
    while True:
        m = ws.receive_json()
        out.append(m)
        if m["kind"] in ("closed", "error"):
            return out


def test_a_call_runs_from_consent_to_suggestions(client):
    with client.websocket_connect("/cases/c1/call/hospital/live") as ws:
        got = play(ws)
    kinds = [m["kind"] for m in got]
    assert "suggestion" in kinds and kinds[-1] == "closed"
    assert any(m["kind"] == "captured" and m["data"]["value"] == "48213" for m in got)
    refs = next(m for m in got if m["kind"] == "suggestion")["data"]["refs"]
    assert refs and all(set(r) == {"label", "quote"} and r["label"] for r in refs)  # for the screen, not raw ids
    assert Rt.last.frames == [PCM, PCM]  # the browser's frames reached the stream, in order


def test_no_consent_no_stream(client):
    with client.websocket_connect("/cases/c1/call/hospital/live") as ws:
        ws.send_json({"type": "start", "lang": "en", "consent": False})
        m = ws.receive_json()
    assert m["kind"] == "error" and "agreed" in m["data"]["message"]
    assert Rt.last is None or Rt.last.frames == []


def test_russian_is_refused_with_the_reason(client):
    with client.websocket_connect("/cases/c1/call/hospital/live") as ws:
        ws.send_json({"type": "start", "lang": "ru", "consent": True})
        assert ws.receive_json()["kind"] == "error"


def test_an_unknown_case_is_closed(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/cases/nope/call/hospital/live") as ws:
            ws.receive_json()


def test_a_live_call_is_only_for_a_fictional_case(client, tmp_path, monkeypatch):
    saved(tmp_path, demo=False)
    class Live(mc.MetaClient):
        live = True
    monkeypatch.setattr(app_module.providers, "make_client", lambda: Live(transport=tca.FakeSpark(None), record_to=None, journal=None))
    with client.websocket_connect("/cases/c1/call/hospital/live") as ws:
        ws.send_json({"type": "start", "lang": "en", "consent": True})
        m = ws.receive_json()
    assert m["kind"] == "error" and "fictional" in m["data"]["message"]


def test_a_public_link_keeps_the_live_call_off(client, monkeypatch):
    class Live(mc.MetaClient):
        live = True
    monkeypatch.setattr(app_module.providers, "make_client", lambda: Live(transport=tca.FakeSpark(None), record_to=None, journal=None))
    monkeypatch.setenv("BILLRADAR_PUBLIC", "1")
    with client.websocket_connect("/cases/c1/call/hospital/live") as ws:
        ws.send_json({"type": "start", "lang": "en", "consent": True})
        assert ws.receive_json()["kind"] == "error"


def test_a_live_call_goes_in_the_ledger(tmp_path):
    ledger = mc.SpendLedger(tmp_path / "s.jsonl", cap=1.0)
    app_module._charge_call(ledger, 2 * 32000 * 60)  # two minutes of 16 kHz, 16-bit mono
    assert ledger.spent() == pytest.approx(0.18 * 2 / 60)


def test_nothing_of_the_call_stays_on_disk(client, tmp_path):
    before = {p for p in tmp_path.rglob("*")}
    with client.websocket_connect("/cases/c1/call/hospital/live") as ws:
        play(ws)
    assert {p for p in tmp_path.rglob("*")} == before


# --- the ladder during a call ---------------------------------------------------------------------

def session_with(tavily, events, spark_over=None):
    c = case(demo=True)
    sheet = callprep.build(c, checks.run(c), "hospital")
    spark = mc.MetaClient(transport=tca.FakeSpark(sheet, spark_over), record_to=None, journal=None)
    s = call_assist.CallSession(tca.SpyRealtime(events), spark, c, sheet, tavily=tavily)
    s.they_agreed()
    return s


STATEMENT = "You only have thirty days to apply for financial assistance."


def rule_turn():
    return tca.turn(1, "A", STATEMENT)


def spark_says_office():
    return {"thirty days": {"side": "office", "answer": "none"}}


class Tavily:
    def __init__(self, answer=None):
        self.answer = answer
        self.asked = []

    def search(self, body, label=""):
        self.asked.append(body)
        return {"results": self.answer or []}


def test_a_rule_they_state_with_no_prepared_answer_goes_to_the_web(monkeypatch):
    found = web_answer.WebAnswer("You can apply within 240 days.", "https://www.mhs.net/fa", "Assistance", seconds=1.0)
    monkeypatch.setattr(web_answer, "find", lambda *a: found)
    out = list(session_with(Tavily(), rule_turn(), spark_says_office()).run([PCM]))
    web = next(u for u in out if u.kind == "web")
    assert web.data["quote"] == found.quote and web.data["url"] == found.url and web.data["label"] == web_answer.LABEL


def test_nothing_found_ends_with_a_phrase_to_say(monkeypatch):
    monkeypatch.setattr(web_answer, "find", lambda *a: None)
    out = list(session_with(Tavily(), rule_turn(), spark_says_office()).run([PCM]))
    assert next(u for u in out if u.kind == "no_answer").data["say"] == web_answer.ASK_IN_WRITING


def test_small_talk_is_not_searched(monkeypatch):
    calls = []
    monkeypatch.setattr(web_answer, "find", lambda *a: calls.append(a))
    list(session_with(Tavily(), tca.turn(1, "A", "Thank you for calling, how are you today?"), {"Thank you": {"side": "office", "answer": "none"}}).run([PCM]))
    assert calls == []


def test_no_search_client_no_web_step(monkeypatch):
    calls = []
    monkeypatch.setattr(web_answer, "find", lambda *a: calls.append(a))
    out = list(session_with(None, rule_turn(), spark_says_office()).run([PCM]))
    assert calls == [] and any(u.kind == "no_answer" for u in out)


def test_the_consent_phrase_is_offered_to_the_screen(client):
    r = client.get("/cases/c1/call/hospital/consent?lang=es")
    assert r.status_code == 200 and "transcriba" in json.dumps(r.json(), ensure_ascii=False)


# --- the sample call: for a judge with no phone at hand --------------------------------------------

def test_the_sample_call_plays_without_a_microphone_and_without_consent(client, monkeypatch):
    monkeypatch.setattr(app_module, "_sample_pcm", lambda: PCM * 3)
    monkeypatch.setattr(app_module, "SAMPLE_PACE_S", 0)
    with client.websocket_connect("/cases/c1/call/hospital/live") as ws:
        ws.send_json({"type": "start", "sample": True, "lang": "en"})
        got = []
        while True:
            m = ws.receive_json()
            got.append(m)
            if m["kind"] in ("closed", "error"):
                break
    assert got[0]["kind"] == "started" and got[0]["data"]["sample"] is True
    assert got[-1]["kind"] == "closed" and Rt.last.frames  # the sample's frames, none from a browser


def test_the_sample_call_is_on_the_page_context(client, monkeypatch, tmp_path):
    (tmp_path / "call.wav").write_bytes(b"RIFF")
    monkeypatch.setattr(app_module, "VOICE_SAMPLES", tmp_path)
    assert app_module.voice_context()["sample_call"] == "/voice/sample/call.wav"


def test_a_sample_on_a_public_copy_still_plays(client, monkeypatch):
    monkeypatch.setattr(app_module, "_sample_pcm", lambda: PCM)
    monkeypatch.setattr(app_module, "SAMPLE_PACE_S", 0)
    monkeypatch.setenv("BILLRADAR_PUBLIC", "1")
    with client.websocket_connect("/cases/c1/call/hospital/live") as ws:
        ws.send_json({"type": "start", "sample": True, "lang": "en"})
        assert ws.receive_json()["kind"] == "started"
