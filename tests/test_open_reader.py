"""The second read on Muse Spark Open, the open weights, served through Baseten. A different model from the first read,
so the two reads are independent. SYNTHETIC: no request leaves here."""

import json

import pytest

from billradar import meta_client as mc
from billradar import open_reader, reader, reconcile_read
from billradar.case import Source


def body() -> dict:
    return reader.request_body([("S1", b"\xff\xd8jpeg")], [], model=open_reader.MODEL)


class Http:
    """Stands in for requests.post."""

    def __init__(self, answers):
        self.answers, self.calls = list(answers), []

    def __call__(self, url, json=None, headers=None, timeout=None):
        self.calls.append((url, json, headers))
        return self.answers.pop(0)


class Response:
    def __init__(self, status, payload):
        self.status_code, self.payload, self.text = status, payload, str(payload)

    def json(self):
        return self.payload


def good(text="{\"documents\": []}", tokens=(1000, 200)) -> Response:
    return Response(200, {"id": "c1", "choices": [{"message": {"content": text}, "finish_reason": "stop"}],
                          "usage": {"prompt_tokens": tokens[0], "completion_tokens": tokens[1]}})


def transport(tmp_path, http) -> open_reader.BasetenTransport:
    return open_reader.BasetenTransport("KEY", post=http, ledger=mc.SpendLedger(tmp_path / "spend.jsonl", cap=1.0))


def test_the_request_keeps_the_sheet_and_the_schema_and_names_the_open_model(tmp_path):
    http = Http([good()])
    transport(tmp_path, http).events(body())
    url, sent, headers = http.calls[0]
    assert url == "https://inference.baseten.co/v1/chat/completions"
    assert sent["model"] == "meta-models/muse-spark-open-1026"
    assert sent["messages"][0]["role"] == "system" and "BillRadar" in sent["messages"][0]["content"]
    parts = sent["messages"][1]["content"]
    assert any(p["type"] == "image_url" and p["image_url"]["url"].startswith("data:image/jpeg") for p in parts)
    assert sent["response_format"]["json_schema"]["name"] == "billradar_case"
    assert headers["Authorization"] == "Bearer KEY"


def test_the_answer_comes_back_as_the_events_the_client_reads(tmp_path):
    events = transport(tmp_path, Http([good('{"documents": [1]}')])).events(body())
    assert mc.collect(events)[0] == '{"documents": [1]}'
    assert mc.collect(events)[1]["input_tokens"] == 1000 and mc.collect(events)[1]["output_tokens"] == 200


def test_a_refused_schema_is_asked_again_for_plain_json(tmp_path):
    http = Http([Response(400, {"error": "response_format not supported"}), good()])
    transport(tmp_path, http).events(body())
    assert http.calls[1][1]["response_format"] == {"type": "json_object"}


def test_an_error_is_an_error_and_its_reservation_is_released(tmp_path):
    t = transport(tmp_path, Http([Response(500, {"error": "x"})] * 4))
    with pytest.raises(mc.MetaAPIError):
        t.events(body())
    assert t.ledger.spent() == pytest.approx(0)


def test_what_was_spent_is_counted_at_its_price(tmp_path):
    t = transport(tmp_path, Http([good(tokens=(1_000_000, 0))]))
    t.events(body())
    assert t.ledger.spent() == pytest.approx(1.25)


def test_the_spend_cap_stops_the_call(tmp_path):
    http = Http([good()])
    t = open_reader.BasetenTransport("KEY", post=http, ledger=mc.SpendLedger(tmp_path / "s.jsonl", cap=0.0001))
    with pytest.raises(mc.SpendCapReached):
        t.events(body())
    assert http.calls == []


def test_a_file_cannot_go_to_this_read(tmp_path):
    b = reader.request_body([], [("D1", "a.pdf", b"%PDF")], model=open_reader.MODEL)
    with pytest.raises(mc.MetaAPIError):
        transport(tmp_path, Http([])).events(b)


def test_the_client_prices_the_open_model_as_published():
    assert mc.call_cost(open_reader.MODEL, {"input_tokens": 1_000_000, "output_tokens": 0}) == pytest.approx(1.25)


def test_the_open_reader_is_on_only_when_asked_for(monkeypatch):
    monkeypatch.delenv("BILLRADAR_SECOND_READER", raising=False)
    monkeypatch.setenv("BASETEN_API_KEY", "KEY")
    assert open_reader.second_reader() is None


def test_without_the_key_the_open_reader_replays(monkeypatch):
    monkeypatch.setenv("BILLRADAR_SECOND_READER", "open")
    monkeypatch.delenv("BASETEN_API_KEY", raising=False)
    client = open_reader.second_reader()
    assert client.read_model == open_reader.MODEL and client.live is False


def test_with_the_key_and_live_on_the_open_reader_is_live_and_records(monkeypatch):
    monkeypatch.setenv("BILLRADAR_SECOND_READER", "open")
    monkeypatch.setenv("BASETEN_API_KEY", "KEY")
    monkeypatch.setenv("BILLRADAR_LIVE", "1")
    assert open_reader.second_reader().live is True


def test_a_failed_second_read_on_the_open_model_falls_back_to_the_first_model():
    class Down:
        live, read_model = True, open_reader.MODEL

        def respond(self, body, label=""):
            raise mc.MetaAPIError("Baseten down")

    class Spark:
        live, labels = False, []

        def respond(self, body, label=""):
            from types import SimpleNamespace
            self.labels.append(label)
            raw = {"doc_id": "S1", "kind": "eob", "patient_balance": "$50.00", "lines": []}
            return SimpleNamespace(text=json.dumps({"documents": [raw]}), usage={}, seconds=0, replayed=True)

    first = reader.to_documents({"documents": [{"doc_id": "S1", "kind": "eob", "patient_balance": "$50.00", "lines": []}]},
                                {"S1": Source.PAPER})[0]
    problems = []
    spark = Spark()
    out = reconcile_read.reconcile(spark, first, [("S1", b"x")], {}, problems, second=Down())
    assert spark.labels == ["spark:read-2"] and out[0].doubts == []
    assert any("Baseten down" in p for p in problems)
