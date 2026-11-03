"""The voice helper on the site: speak, and the app sets the chips or answers about the case. Everything said goes to
Meta to become text, so a live call needs a yes on the screen, a fictional case, and stays limited per address. Audio
is never kept. Every answer here is SYNTHETIC: no model was called."""

import json
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from billradar import app as app_module
from billradar import ask, checks, meta_client as mc, pipeline, voice
from billradar.checks import Finding, Kind
from tests.test_writer import case

WAV = b"RIFF" + b"\0" * 4 + b"WAVE" + b"\0" * 200


class Fake:
    """Live or not, this answers the two calls of a voice turn."""

    def __init__(self, text="I had surgery and they sent my bill to collections", chips=("planned_surgery", "in_collections", "no_such_chip")):
        self.text, self.chips, self.asked = text, chips, []

    def asr(self, request, audio):
        return {"transcript": self.text, "audioDurationMs": 4000}

    def events(self, body):
        self.asked.append(body)
        return [{"type": "response.output_text.delta", "delta": json.dumps({"chips": list(self.chips)})},
                {"type": "response.completed", "response": {"id": "r", "usage": {}}}]


class LiveClient(mc.MetaClient):
    live = True


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "RUNS", tmp_path)
    monkeypatch.setattr(app_module, "_live_hits", type(app_module._live_hits)(app_module._live_hits.default_factory))
    return TestClient(app_module.app)


def use(monkeypatch, cls=mc.MetaClient, fake=None):
    monkeypatch.setattr(app_module.providers, "make_client", lambda: cls(transport=fake or Fake(), record_to=None, journal=None))


def saved_case(tmp_path, demo=True) -> str:
    c = case(case_id="c1")
    c.demo = demo
    report = checks.run(c)
    run = pipeline.CaseRun(c, report, [], [])
    pipeline.save(run, tmp_path / "c1")
    return "c1"


def test_speaking_sets_the_chips_and_only_known_ones(client, monkeypatch):
    fake = Fake()
    use(monkeypatch, fake=fake)
    r = client.post("/voice/intake?lang=en&consent=1", content=WAV)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["transcript"].startswith("I had surgery") and d["chips"] == ["planned_surgery", "in_collections"]
    assert d["language"] == "en" and d["replayed"] is True
    assert fake.asked[0]["model"] == "muse-spark-1.3" and fake.asked[0]["store"] is False


def test_nothing_goes_out_live_without_a_yes(client, monkeypatch):
    use(monkeypatch, LiveClient)
    r = client.post("/voice/intake?lang=en", content=WAV)
    assert r.status_code == 400 and "consent" in r.json()["error"].lower()


def test_russian_is_refused_with_the_reason(client, monkeypatch):
    use(monkeypatch)
    r = client.post("/voice/intake?lang=ru&consent=1", content=WAV)
    assert r.status_code == 400 and "English or Spanish" in r.json()["error"]


def test_no_model_says_so(client, monkeypatch):
    class Missing(Fake):
        def asr(self, request, audio):
            raise mc.ReplayMissing("no recording")

    use(monkeypatch, fake=Missing())
    r = client.post("/voice/intake?lang=en&consent=1", content=WAV)
    assert r.status_code == 503 and "error" in r.json()


def test_a_long_recording_is_refused_before_it_goes_anywhere(client, monkeypatch):
    fake = Fake()
    use(monkeypatch, fake=fake)
    r = client.post("/voice/intake?lang=en&consent=1", content=WAV + b"\0" * (6 * 1024 * 1024))
    assert r.status_code == 413 and fake.asked == []


def test_a_public_link_keeps_live_voice_off_unless_switched_on(client, monkeypatch):
    use(monkeypatch, LiveClient)
    monkeypatch.setenv("BILLRADAR_PUBLIC", "1")
    assert client.post("/voice/intake?lang=en&consent=1", content=WAV).status_code == 503
    monkeypatch.setenv("BILLRADAR_PUBLIC_VOICE", "1")
    assert client.post("/voice/intake?lang=en&consent=1", content=WAV).status_code == 200


def test_a_recorded_sample_plays_back_on_a_live_public_copy_and_reaches_no_model(client, monkeypatch):
    class Reaches(Fake):
        def asr(self, request, audio):
            raise AssertionError("a recorded sample went to the model")

    use(monkeypatch, LiveClient, Reaches())
    monkeypatch.setenv("BILLRADAR_PUBLIC", "1")
    sample = (app_module.VOICE_SAMPLES / "intake.wav").read_bytes()
    r = client.post("/voice/intake?lang=en&consent=1", content=sample)
    assert r.status_code == 200 and r.json()["replayed"] and r.json()["chips"]
    assert client.post("/voice/intake?lang=en&consent=1", content=WAV).status_code == 503  # a person's voice stays off


def test_a_voice_note_on_a_public_copy_stays_off_and_a_live_one_needs_a_yes(client, tmp_path, monkeypatch):
    saved_case(tmp_path)
    use(monkeypatch, LiveClient)
    assert client.post("/cases/c1/call/hospital/note?lang=en", content=WAV).status_code == 400  # no yes on the screen
    monkeypatch.setenv("BILLRADAR_PUBLIC", "1")
    assert client.post("/cases/c1/call/hospital/note?lang=en&consent=1", content=WAV).status_code == 503
    assert client.post("/cases/c1/call/hospital/note?lang=en&consent=1", content=WAV + b"\0" * (6 * 1024 * 1024)).status_code == 413


def test_the_sample_note_is_offered_only_where_it_is_recorded(client, tmp_path, monkeypatch):
    saved_case(tmp_path)
    assert 'id="note-sample"' not in client.get("/cases/c1/call/hospital").text  # her own case has no recording
    monkeypatch.setattr(app_module, "_sample_note_ready", lambda *_: True)
    page = client.get("/cases/c1/call/hospital").text
    assert 'id="note-sample"' in page and "/voice/sample/note.wav" in page


def test_the_sample_question_is_offered_only_where_it_answers(client, tmp_path, monkeypatch):
    c = saved_case(tmp_path)
    assert "vox-sample" not in client.get(f"/cases/{c}").text  # her own case has no recording
    monkeypatch.setattr(app_module, "_sample_answers", lambda _: True)
    assert "vox-sample" in client.get(f"/cases/{c}").text


def test_a_sample_without_a_recorded_answer_is_not_offered(tmp_path, monkeypatch):
    app_module._sample_answers.cache_clear()
    monkeypatch.setattr(app_module, "_load", lambda _: (None, case(), checks.run(case())))
    monkeypatch.setattr(app_module, "_sample_client", lambda: mc.MetaClient(transport=mc.ReplayTransport(tmp_path), record_to=None, journal=None))
    assert not app_module._sample_answers("example")
    assert not app_module._sample_answers("somebody-else")
    assert not app_module._sample_answers("example-appeal") and not app_module._sample_note_ready("example-appeal", "insurer")
    app_module._sample_answers.cache_clear()


def test_a_sheet_at_the_start_of_a_sentence_takes_a_capital():
    said = "sheet 1 and sheet 2 list two lines. sheet 1 shows $5. See file 3! file 3 is short."
    assert app_module._sentences_start_big(said) == "Sheet 1 and sheet 2 list two lines. Sheet 1 shows $5. See file 3! File 3 is short."


def test_a_sum_in_an_answer_has_its_dollar_sign_and_nothing_else_does():
    said = "Sheet 10 lists it twice at 4944 each. The paper asks 393.64, and $196.82 may come off; 1,399.71 too."
    assert app_module._money_reads_as_money(said) == ("Sheet 10 lists it twice at $4,944 each. The paper asks $393.64, "
                                                     "and $196.82 may come off; $1,399.71 too.")
    same = "Fla. Stat. 395.301(1)(e), 26 CFR 1.501(r)-5, 212.3% on 2025-02-11, 90.00% off, 2 sheets each."
    assert app_module._money_reads_as_money(same) == same


def test_each_promise_in_the_note_ends_its_own_sentence():
    words = [("they will hold the account for 30 days", "they will hold the account for 30 days"), ("send it by mail.", "send it by mail.")]
    note = voice.CallNote("Seaside", "Morgan", "48213", words)
    assert note.paragraph(case(), "en").text.endswith("I was told: “they will hold the account for 30 days.” I was told: “send it by mail.”")


def test_a_review_with_nothing_to_note_still_counts_as_reviewed():
    from billradar import view
    meta = {"checker": {"checked": 10, "issues": [], "review": {"confirmed": 9, "cannot_tell": 1}}}
    assert view._reviewed(meta)
    assert view._review_line(meta, "Muse Wonder") == "Muse Wonder reviewed 10 items: 9 confirmed, 0 flagged, 1 it could not check from the papers"
    assert not view._reviewed({"checker": {"checked": 10, "issues": []}})  # must light: no second look, no line


def test_a_file_that_could_not_be_read_is_called_a_file(client, tmp_path):
    c = case(case_id="c1")
    pipeline.save(pipeline.CaseRun(c, checks.run(c), [], [], unreadable=["S3", "D2"]), tmp_path / "c1")
    page = client.get("/cases/c1").text
    assert "Sheet 3 could not be read." in page and "Take a new photo." in page
    assert "File 2 could not be read." in page and "Add this file again." in page and "Sheet 2 could not" not in page


def test_the_sample_button_speaks_english_whatever_is_picked():
    js = (app_module.VOICE_SAMPLES.parent / "web/static/assist.js").read_text()
    assert '.blob(), "en")' in js


def test_live_runs_are_limited_per_address(client, monkeypatch):
    use(monkeypatch, LiveClient)
    monkeypatch.setenv("BILLRADAR_LIVE_PER_HOUR", "1")
    assert client.post("/voice/intake?lang=en&consent=1", content=WAV).status_code == 200
    assert client.post("/voice/intake?lang=en&consent=1", content=WAV).status_code == 429


def test_the_spend_cap_answers_in_words(client, monkeypatch):
    class Capped(Fake):
        def asr(self, request, audio):
            raise mc.SpendCapReached("cap")

    use(monkeypatch, fake=Capped())
    r = TestClient(app_module.app, raise_server_exceptions=False).post("/voice/intake?lang=en&consent=1", content=WAV)
    assert r.status_code == 503 and "example" in r.json()["error"]


def test_a_spoken_question_gets_the_same_answer_as_a_typed_one(client, tmp_path, monkeypatch):
    saved_case(tmp_path)
    use(monkeypatch, fake=Fake(text="Why is the baby's bill so high?"))
    asked = []
    from billradar import web_answer
    monkeypatch.setattr(web_answer, "ladder", lambda c, cs, r, q: asked.append(q) or ask.Answer("Because of this line.", replayed=True))
    r = client.post("/cases/c1/ask/voice?lang=en&consent=1", content=WAV)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["transcript"] == "Why is the baby's bill so high?" and d["text"] == "Because of this line."
    assert asked == ["Why is the baby's bill so high?"] and d["citations"] == []


def test_a_spoken_question_about_a_real_case_stays_here(client, tmp_path, monkeypatch):
    saved_case(tmp_path, demo=False)
    use(monkeypatch, LiveClient)
    r = client.post("/cases/c1/ask/voice?lang=en&consent=1", content=WAV)
    assert r.status_code == 400 and "fictional" in r.json()["error"]


def test_a_question_says_which_step_answered(client, tmp_path, monkeypatch):
    from billradar import web_answer
    saved_case(tmp_path)
    use(monkeypatch)
    web = web_answer.WebAnswer("You can apply for 240 days.", "https://www.mhs.net/fa", "Financial assistance", seconds=1.5)
    monkeypatch.setattr(web_answer, "ladder", lambda *a: ask.Answer(web.quote, source="web", web=web))
    d = client.post("/cases/c1/ask", json={"question": "how long can I apply?"}).json()
    assert d["source"] == "web" and d["web"]["url"] == "https://www.mhs.net/fa"
    assert d["web"]["label"] == "from the web, check it" and d["citations"] == []
    monkeypatch.setattr(web_answer, "ladder", lambda *a: ask.Answer(web_answer.NOT_IN_CASE, refused=True, reason="no_citation",
                                                                    source="none", say=web_answer.ASK_IN_WRITING))
    d = client.post("/cases/c1/ask", json={"question": "how long can I apply?"}).json()
    assert d["source"] == "none" and "in writing" in d["say"] and d["web"] is None


def test_pages_say_what_voice_can_do(client, monkeypatch):
    use(monkeypatch, LiveClient)
    assert app_module.voice_context()["live"] is True
    assert app_module.voice_context()["langs"] == voice.LANGUAGES
    use(monkeypatch)
    assert app_module.voice_context()["live"] is False


def test_all_the_dates_of_a_case_in_one_calendar_file(client, tmp_path, monkeypatch):
    saved_case(tmp_path)
    monkeypatch.setattr(app_module, "_today", lambda case_id, c: c.today)  # opened on the case's own day
    r = client.get("/cases/c1/deadlines.ics")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/calendar")
    text = r.text
    assert text.startswith("BEGIN:VCALENDAR") and text.count("BEGIN:VEVENT") >= 1
    assert "TRIGGER:-P7D" in text and "\r\n" in text


def test_a_case_with_no_dates_gets_an_empty_calendar_not_an_error(client, tmp_path, monkeypatch):
    saved_case(tmp_path)
    monkeypatch.setattr(app_module, "case_dates", lambda *a: [])
    r = client.get("/cases/c1/deadlines.ics")
    assert r.status_code == 200 and "BEGIN:VEVENT" not in r.text


def test_finding_deadlines_are_on_the_list():
    c = case()
    report = checks.run(c)
    report.findings.append(Finding(kind=Kind.N1, title="Send the insurance details", detail="d", amount=Decimal(0),
                                   deadline=date(2026, 8, 1)))
    assert (date(2026, 8, 1), "Send the insurance details") in app_module.case_dates(c, report)


def _note_app(client, tmp_path, monkeypatch):
    saved_case(tmp_path)
    use(monkeypatch)
    monkeypatch.setattr(app_module.callprep, "build", lambda c, r, to: type("Sheet", (), {"who": "Seaside billing"})())
    monkeypatch.setattr(voice, "transcribe", lambda *a: voice.Transcript("I spoke with Maria, reference 4471", "en", 1000, True))
    monkeypatch.setattr(voice, "read_note", lambda *a, **k: voice.CallNote(who="Seaside billing", rep_name="Maria", reference="4471",
                                                                           promises=[("We will call back", "We will call back")]))


def test_a_note_after_a_call_is_kept_with_the_case(client, tmp_path, monkeypatch):
    _note_app(client, tmp_path, monkeypatch)
    assert client.get("/cases/c1/notes").json() == []
    r = client.post("/cases/c1/call/hospital/note?lang=en", content=WAV)
    assert r.status_code == 200 and r.json()["rep_name"] == "Maria"
    notes = client.get("/cases/c1/notes").json()
    assert len(notes) == 1
    assert notes[0]["to"] == "hospital" and notes[0]["reference"] == "4471" and "Maria" in notes[0]["paragraph"]
    assert notes[0]["at"] and "transcript" not in notes[0]  # what was said stays out of the file; the paragraph is hers


def test_no_audio_is_kept_with_a_note(client, tmp_path, monkeypatch):
    _note_app(client, tmp_path, monkeypatch)
    client.post("/cases/c1/call/hospital/note?lang=en", content=WAV)
    assert not [p for p in (tmp_path / "c1").rglob("*") if p.suffix in {".wav", ".webm", ".pcm"}]


def test_an_example_note_is_shown_but_not_saved(client, tmp_path, monkeypatch):
    _note_app(client, tmp_path, monkeypatch)
    monkeypatch.setattr(app_module.example, "READ_ONLY", {"c1"})
    monkeypatch.setattr(app_module.example, "ensure", lambda runs: None)  # the real example takes minutes to build
    assert client.post("/cases/c1/call/hospital/note?lang=en", content=WAV).status_code == 200
    assert client.get("/cases/c1/notes").json() == []
