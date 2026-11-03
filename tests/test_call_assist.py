"""Help during a live call (pack A, Я19). The call is SYNTHETIC: server events are written in the documented
DIARIZATION shape (dev.meta.ai/docs/speech-to-text.md, "Label speakers with diarization"; handshake and URL
from dev.meta.ai/docs/api-reference/voice/realtime.md, saved 2026-10-27), and Spark's answers come from a fake.
No audio exists here: a few bytes of silence stand in for the stream."""

import json

import pytest

from billradar import call_assist, callprep, checks
from billradar.meta_client import MetaClient, ReplayMissing
from billradar.pipeline import RealDataGate
from tests import test_writer

PCM = b"\x00\x00" * 1600  # 0.1 s of silence


def turn(n, label, text):
    return [{"type": "speechStart", "turnId": n, "audioProcessedMs": n * 1000},
            {"type": "transcript", "transcript": text[:12], "final": False, "audioProcessedMs": n * 1000 + 200},
            {"type": "speaker", "label": label, "audioProcessedMs": n * 1000 + 300},
            {"type": "speechEnd", "turnId": n, "audioProcessedMs": n * 1000 + 600},
            {"type": "speechComplete", "turnId": n, "transcript": text, "audioProcessedMs": n * 1000 + 600}]


# The stream opens only after "They agreed", so the consent itself is never in it.
CALL = (turn(1, "A", "Thank you for calling Lakeview Demo Hospital billing. This is Morgan.")
        + turn(2, "B", "Hi, I'm calling about the bills for Anna Sample. I think there may be a duplicate charge.")
        + turn(3, "A", "The discount is only for uninsured patients.")
        + turn(4, "B", "Your policy says insured patients can apply too.")
        + turn(5, "A", "Your reference number is 48213. We will review the account within 10 business days."))


class SpyRealtime:
    def __init__(self, events):
        self.evs, self.calls = events, []

    def events(self, hs, frames):
        self.calls.append(hs)
        list(frames)
        yield from self.evs


class FakeSpark:
    """Picks an answer by what was said; records every request body."""

    def __init__(self, sheet, overrides=None):
        self.sheet, self.overrides, self.bodies = sheet, overrides or {}, []

    def events(self, body):
        self.bodies.append(body)
        said = body["input"][1]["content"][0]["text"].split("This turn:\n", 1)[1]
        office = any(w in said for w in ("Thank you for calling", "uninsured", "reference number"))
        ans = {"side": "office" if office else "caller", "answer": "none", "rep_name": {"value": "", "quote": ""},
               "reference": {"value": "", "quote": ""}, "promise": ""}
        if "This is Morgan" in said:
            ans["rep_name"] = {"value": "Morgan", "quote": "This is Morgan."}
        if "uninsured" in said:
            n = next(i for i, o in enumerate(self.sheet.objections, 1) if "uninsured" in o.they_say)
            ans["answer"] = str(n)
        if "48213" in said:
            ans["reference"] = {"value": "48213", "quote": "Your reference number is 48213."}
            ans["promise"] = "We will review the account within 10 business days."
        for k, v in self.overrides.items():
            if k in said:
                ans.update(v)
        return [{"type": "response.output_text.delta", "delta": json.dumps(ans)},
                {"type": "response.completed", "response": {"id": "resp_SYNTHETIC", "usage": {}}}]


def session(overrides=None, events=CALL, journal=None):
    c = test_writer.case(demo=True)
    sheet = callprep.build(c, checks.run(c), "hospital")
    rt = SpyRealtime(events)
    spark = FakeSpark(sheet, overrides)
    s = call_assist.CallSession(rt, MetaClient(transport=spark, record_to=None, journal=None), c, sheet,
                                journal=journal)
    return s, rt, spark, sheet


# --- consent -------------------------------------------------------------------------------------

def test_no_stream_without_consent():
    s, rt, spark, _ = session()
    with pytest.raises(call_assist.ConsentRequired):
        list(s.run(call_assist.pcm_frames(PCM)))
    assert rt.calls == [] and spark.bodies == []  # nothing was opened, nothing was sent


def test_consent_phrase_in_english_and_spanish_only():
    s, *_ = session()
    assert "transcribed" in s.consent_phrase
    c = test_writer.case(demo=True)
    sheet = callprep.build(c, checks.run(c))
    assert "transcriba" in call_assist.CallSession(None, None, c, sheet, "es").consent_phrase
    with pytest.raises(ValueError, match="no 'ru'"):
        call_assist.CallSession(None, None, c, sheet, "ru")


def test_live_call_only_for_a_fictional_case():
    c = test_writer.case()  # not marked fictional
    sheet = callprep.build(c, checks.run(c))
    s = call_assist.CallSession(call_assist.LiveRealtime("not-a-key", record_to=None), None, c, sheet)
    s.they_agreed()
    with pytest.raises(RealDataGate):
        list(s.run(call_assist.pcm_frames(PCM)))


# --- during the call -----------------------------------------------------------------------------

def test_call_turns_suggestions_and_captured_words():
    s, rt, spark, sheet = session()
    s.they_agreed()
    ups = list(s.run(call_assist.pcm_frames(PCM), api_key="SYNTHETIC-KEY"))
    kinds = [u.kind for u in ups]
    assert kinds.count("turn") == 5 and kinds[-1] == "closed" and "partial" in kinds
    assert [t.who for t in s.turns] == ["them", "you", "them", "you", "them"]
    sug = [u.data for u in ups if u.kind == "suggestion"]
    assert len(sug) == 1 and sug[0]["they_say"] == "The discount is only for uninsured patients."
    insured = next(o for o in sheet.objections if "uninsured" in o.they_say)
    assert sug[0]["say"] == insured.answer and sug[0]["refs"] == insured.refs  # a prepared, verified answer
    assert s.captured == {"rep_name": "Morgan", "reference": "48213"}
    assert s.promises == ["We will review the account within 10 business days."]
    hs = rt.calls[0]
    assert hs["model"] == "muse-voice-transcribe-1.0" and hs["mode"] == "DIARIZATION"
    assert hs["audioEncoding"] == "PCM_16KHZ" and hs["authorization"] == {"accessToken": "Bearer SYNTHETIC-KEY"}
    assert call_assist.REALTIME_URL == "wss://api.meta.ai/v1/asr/realtime"


def test_family_name_never_reaches_the_model():
    s, _, spark, _ = session()
    s.they_agreed()
    list(s.run(call_assist.pcm_frames(PCM)))
    sent = json.dumps([b["input"] for b in spark.bodies], ensure_ascii=False)
    assert "Anna Sample" not in sent and "⟦V" in sent  # the caller's turn went out with the name hidden
    assert all(b["model"] == "muse-spark-1.3" and b["store"] is False for b in spark.bodies)
    assert len(spark.bodies) == 4  # turn 4 is already known to be the caller's and is not sent


def test_that_is_me_fixes_the_sides_by_hand():
    s, *_ = session(overrides={"Thank you": {"side": "unclear"}, "I'm calling": {"side": "unclear"}})
    s.they_agreed()
    ups = s.run(call_assist.pcm_frames(PCM))
    while not s.turns or len(s.turns) < 2:
        next(ups)
    assert s.turns[0].who == "?"
    s.this_is_me("B")
    rest = list(ups)
    assert [t.who for t in s.turns] == ["them", "you", "them", "you", "them"]
    assert any(u.kind == "suggestion" for u in rest)


def test_made_up_answer_or_words_are_dropped():
    s, *_ = session(overrides={"uninsured": {"answer": "99", "rep_name": {"value": "Taylor", "quote": "I am Taylor."},
                                             "promise": "We will waive the bill."},
                               "I'm calling": {"answer": "1"}})
    s.they_agreed()
    ups = list(s.run(call_assist.pcm_frames(PCM)))
    assert not [u for u in ups if u.kind == "suggestion"]
    assert "Taylor" not in s.captured.values() and "We will waive the bill." not in s.promises


def test_after_the_call_the_note_becomes_a_letter_paragraph_and_close_forgets():
    s, *_ = session()
    s.they_agreed()
    list(s.run(call_assist.pcm_frames(PCM)))
    p = s.note().paragraph(s.case, "en").text
    assert "spoke with Morgan (reference number 48213)" in p and "within 10 business days" in p
    s.close()
    assert s.turns == [] and s.captured == {} and s.promises == []
    with pytest.raises(call_assist.ConsentRequired):
        list(s.run(call_assist.pcm_frames(PCM)))


def test_journal_keeps_counts_not_words(tmp_path):
    s, *_ = session(journal=tmp_path / "j.jsonl")
    s.they_agreed()
    list(s.run(call_assist.pcm_frames(PCM)))
    line = (tmp_path / "j.jsonl").read_text()
    assert json.loads(line)["turns"] == 5 and "Morgan" not in line and "uninsured" not in line


# --- recordings --------------------------------------------------------------------------------------

def test_replay_reads_recorded_events_and_the_key_is_not_in_the_name(tmp_path):
    hs = call_assist.handshake("SECRET-KEY-SYNTHETIC", "en", ["Lakeview Demo Hospital"])
    import hashlib
    rec = call_assist.ReplayRealtime(tmp_path)
    p = rec.path(hs, hashlib.sha256(PCM).hexdigest())
    assert "SECRET" not in p.name
    p.write_text("".join(json.dumps(e) + "\n" for e in CALL))
    assert list(rec.events(hs, call_assist.pcm_frames(PCM))) == CALL
    with pytest.raises(ReplayMissing):
        list(rec.events(hs, call_assist.pcm_frames(PCM + b"\x01\x00")))


def test_one_turn_the_model_cannot_answer_does_not_end_the_call():
    """The first live call: one answer ran out of tokens ("response ended with response.incomplete") and took the call down."""
    s, _, spark, _ = session()
    real = spark.events

    def cut(body):
        if "uninsured" in body["input"][1]["content"][0]["text"].split("This turn:\n", 1)[1]:
            return [{"type": "response.incomplete", "response": {"incomplete_details": {"reason": "max_output_tokens"}}}]
        return real(body)

    spark.events = cut
    s.they_agreed()
    ups = list(s.run(call_assist.pcm_frames(PCM), api_key="SYNTHETIC-KEY"))
    kinds = [u.kind for u in ups]
    assert kinds.count("turn") == 5 and kinds[-1] == "closed"  # every turn still came through
    assert s.captured.get("reference") == "48213"  # and the later turns still helped
    assert any(u.kind == "no_answer" for u in ups)  # the person is told to ask in writing, not left with silence


def test_a_turn_has_room_for_its_answer():
    s, _, spark, _ = session()
    s.they_agreed()
    list(s.run(call_assist.pcm_frames(PCM), api_key="SYNTHETIC-KEY"))
    assert spark.bodies[0]["max_output_tokens"] >= 2000
