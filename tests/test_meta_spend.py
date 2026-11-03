"""The Meta Model API has no spend limit that stops anything (a Spend Limit only sends an email), and past the free
credits the card pays. So every live call is priced from its usage, a worst case is reserved before it goes out, and
a call that would pass the cap never leaves. Every answer here is SYNTHETIC: no model was called."""

import json

import pytest

from billradar import meta_client as mc


class FakeHTTP:
    """Stands in for requests.post on the live transport."""

    def __init__(self, status=200, lines=(), headers=None, payload=None):
        self.status_code, self.lines, self.headers, self.payload = status, list(lines), headers or {}, payload
        self.text = "synthetic error"

    def iter_lines(self):
        return iter(self.lines)

    def json(self):
        return self.payload


USAGE = {"input_tokens": 10000, "input_tokens_details": {"cached_tokens": 4000},
         "output_tokens": 2000, "output_tokens_details": {"reasoning_tokens": 1500}}
SPARK_USD = (6000 * 1.25 + 4000 * 0.15 + 2000 * 4.25) / 1e6


def sse(usage=USAGE) -> list[bytes]:
    done = {"type": "response.completed", "response": {"id": "resp_SYNTHETIC", "usage": usage}}
    return [b"data: " + json.dumps({"type": "response.output_text.delta", "delta": "{}"}).encode(),
            b"data: " + json.dumps(done).encode(), b"data: [DONE]"]


def body(model="muse-spark-1.3", max_out=1000, text="hello") -> dict:
    return {"model": model, "store": False, "stream": True, "max_output_tokens": max_out,
            "input": [{"role": "user", "content": [{"type": "input_text", "text": text}]}]}


@pytest.fixture
def ledger(tmp_path):
    return mc.SpendLedger(tmp_path / "spend.jsonl", cap=1.0)


def live(ledger, tmp_path):
    return mc.MetaClient(transport=mc.LiveTransport("k-synthetic", ledger=ledger), record_to=None, journal=tmp_path / "j.jsonl")


def test_a_token_call_costs_what_the_price_list_says():
    """Cached input at its own rate; reasoning is already inside output_tokens (quickstart: 258 of which 241)."""
    assert mc.cost_of("muse-spark-1.3", USAGE) == pytest.approx(SPARK_USD)
    assert mc.cost_of("muse-wonder-1.0", USAGE) == pytest.approx((6000 * 4 + 4000 * 0.2 + 2000 * 20) / 1e6)


def test_flat_priced_calls():
    assert mc.flat_cost("sam-3.1") == pytest.approx(0.0025)
    assert mc.flat_cost("muse-image-1.0") == pytest.approx(0.01)
    assert mc.asr_cost(3_600_000) == pytest.approx(0.18)


def test_the_ledger_ends_on_the_real_cost_and_the_call_is_journaled(ledger, tmp_path, monkeypatch):
    monkeypatch.setattr(mc.requests, "post", lambda *a, **k: FakeHTTP(lines=sse()))
    c = live(ledger, tmp_path)
    res = c.respond(body(), label="spark:read")
    assert res.text == "{}"
    assert ledger.spent() == pytest.approx(SPARK_USD)
    entry = json.loads((tmp_path / "j.jsonl").read_text().splitlines()[-1])
    assert entry["usd"] == pytest.approx(SPARK_USD, abs=1e-6) and entry["label"] == "spark:read" and entry["live"]
    assert c.calls[-1]["usd"] == entry["usd"] and c.calls[-1]["response_id"] == "resp_SYNTHETIC"


def test_a_call_that_would_pass_the_cap_never_leaves(ledger, tmp_path, monkeypatch):
    sent = []
    monkeypatch.setattr(mc.requests, "post", lambda *a, **k: sent.append(1) or FakeHTTP(lines=sse()))
    with pytest.raises(mc.SpendCapReached):
        live(ledger, tmp_path).respond(body(max_out=400_000), label="spark:read")  # $1.70 of output alone, cap $1
    assert sent == [] and ledger.spent() == 0


def test_the_cap_counts_what_earlier_runs_spent(tmp_path, monkeypatch):
    path = tmp_path / "spend.jsonl"
    mc.SpendLedger(path, cap=1.0).settle(0.999, "an earlier run")
    monkeypatch.setattr(mc.requests, "post", lambda *a, **k: FakeHTTP(lines=sse()))
    with pytest.raises(mc.SpendCapReached):
        live(mc.SpendLedger(path, cap=1.0), tmp_path).respond(body(), label="spark:read")


def test_the_cap_is_not_swallowed_as_a_model_error():
    """Optional steps catch MetaAPIError and go on; the cap has to stop the run."""
    assert not issubclass(mc.SpendCapReached, mc.MetaAPIError)


def test_an_error_is_not_counted(ledger, tmp_path, monkeypatch):
    monkeypatch.setattr(mc.requests, "post", lambda *a, **k: FakeHTTP(status=402))
    with pytest.raises(mc.MetaAPIError, match="HTTP 402"):
        live(ledger, tmp_path).respond(body(), label="spark:read")
    assert ledger.spent() == 0


def test_a_cut_stream_keeps_the_reservation(ledger, tmp_path, monkeypatch):
    """The model may have worked and we cannot see the bill: count the worst case."""
    monkeypatch.setattr(mc.requests, "post", lambda *a, **k: FakeHTTP(lines=sse()[:1]))
    with pytest.raises(mc.MetaAPIError, match="final event"):
        live(ledger, tmp_path).respond(body(), label="spark:read")
    assert ledger.spent() > 0


def test_a_recording_is_free(ledger, tmp_path):
    class Replay(mc.ReplayTransport):
        def events(self, b):
            return [{"type": "response.completed", "response": {"id": "r", "usage": USAGE}}]

    c = mc.MetaClient(transport=Replay(tmp_path), record_to=None, journal=None)
    c.respond(body(), label="spark:read")
    assert ledger.spent() == 0 and c.calls[-1]["live"] is False


def test_transcription_is_priced_by_the_second(ledger, tmp_path, monkeypatch):
    wav = b"RIFF" + b"\0" * 4 + b"WAVE" + b"\0" * 100
    monkeypatch.setattr(mc.requests, "post", lambda *a, **k: FakeHTTP(payload={"transcript": "hi", "audioDurationMs": 120_000}))
    c = live(ledger, tmp_path)
    answer, replayed = c.transcribe({"model": "muse-voice-transcribe-1.0", "audioEncoding": "WAV"}, wav, label="voice:note")
    assert answer["transcript"] == "hi" and replayed is False
    assert ledger.spent() == pytest.approx(0.18 * 120 / 3600)
