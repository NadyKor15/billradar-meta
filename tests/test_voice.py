"""Voice note after the call (pack A, Я8). All model answers here are SYNTHETIC, written in the documented
formats: TranscribeResponse (dev.meta.ai/docs/api-reference/voice/schemas.md) and Responses SSE events.
Model id "muse-voice-transcribe-1.0" and POST /v1/asr/transcribe are copied from
dev.meta.ai/docs/api-reference/voice/transcribe.md (saved 2026-10-27)."""

import io
import json
import wave

import pytest

from billradar import meta_client, voice, writer
from billradar.meta_client import LiveTransport, MetaAPIError, MetaClient, ReplayTransport
from billradar.pipeline import RealDataGate
from tests import test_appeal

ES_NOTE = ("Hablé con Morgan en facturación. El número de referencia es 48213. "
           "Me dijeron que van a revisar la cuenta en diez días hábiles.")


def wav(seconds: float = 0.5, rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(seconds * rate))
    return buf.getvalue()


def replay_client(tmp_path, transcript: str, audio: bytes, language: str = "es") -> MetaClient:
    c = test_appeal.case()
    req = voice.transcribe_request(language, voice.keywords(c))
    rec = ReplayTransport(tmp_path)
    rec.asr_path(req, audio).write_text(json.dumps(
        {"sessionId": "SYNTHETIC", "transcript": transcript, "audioDurationMs": 9000, "turns": []}))
    return MetaClient(transport=rec, record_to=None, journal=tmp_path / "journal.jsonl")


class FakeSpark:
    def __init__(self, answer: dict):
        self.answer = answer
        self.bodies = []

    def events(self, body):
        self.bodies.append(body)
        return [{"type": "response.output_text.delta", "delta": json.dumps(self.answer)},
                {"type": "response.completed", "response": {"id": "resp_SYNTHETIC", "usage": {}}}]


def spark(answer: dict) -> tuple[MetaClient, FakeSpark]:
    fake = FakeSpark(answer)
    return MetaClient(transport=fake, record_to=None, journal=None), fake


# --- transcription -------------------------------------------------------------------------

def test_request_follows_the_documented_shape():
    req = voice.transcribe_request("es", ["Lakeview Demo Hospital"])
    assert req == {"model": "muse-voice-transcribe-1.0", "audioEncoding": "WAV", "mode": "PUSH_TO_TALK",
                   "languageBias": ["Spanish"], "keywords": ["Lakeview Demo Hospital"]}


def test_russian_is_refused_with_a_reason():
    with pytest.raises(voice.LanguageNotSupported, match="no 'ru'"):
        voice.transcribe_request("ru", [])


def test_keywords_never_carry_a_family_name():
    c = test_appeal.case()
    words = " ".join(voice.keywords(c))
    assert "Lakeview Demo Hospital" in words and "Sample Health Plan" in words
    assert "Maria" not in words and "Leo" not in words and "SHP-000" not in words


def test_only_wav_goes_out():
    client = MetaClient(transport=ReplayTransport(), record_to=None, journal=None)
    with pytest.raises(MetaAPIError, match="WAV"):
        client.transcribe(voice.transcribe_request("en", []), b"\x1aE\xdf\xa3webm-bytes")


def test_transcript_from_a_recording_and_journal_without_audio(tmp_path):
    audio = wav()
    client = replay_client(tmp_path, ES_NOTE, audio)
    t = voice.transcribe(client, test_appeal.case(), audio, "es")
    assert t.text == ES_NOTE and t.replayed and t.duration_ms == 9000
    entry = json.loads((tmp_path / "journal.jsonl").read_text())
    assert entry["model"] == "muse-voice-transcribe-1.0" and entry["audio_bytes"] == len(audio)
    assert "transcript" not in entry and ES_NOTE not in json.dumps(entry)


def test_missing_recording_is_an_error_not_a_guess(tmp_path):
    client = MetaClient(transport=ReplayTransport(tmp_path), record_to=None, journal=None)
    with pytest.raises(meta_client.ReplayMissing):
        voice.transcribe(client, test_appeal.case(), wav(), "en")


def test_live_voice_only_for_a_fictional_case():
    c = test_appeal.case()
    c.demo = False
    live = MetaClient(transport=LiveTransport("not-a-key"), record_to=None, journal=None)
    with pytest.raises(RealDataGate):
        voice.transcribe(live, c, wav(), "en")
    with pytest.raises(RealDataGate):
        voice.read_note(live, c, voice.Transcript(ES_NOTE, "es"), "Lakeview Demo Hospital")


# --- what was said -------------------------------------------------------------------------

GOOD = {"rep_name": {"value": "Morgan", "quote": "Hablé con Morgan en facturación."},
        "reference": {"value": "48213", "quote": "El número de referencia es 48213."},
        "promises": [{"quote": "van a revisar la cuenta en diez días hábiles",
                      "english": "they will review the account within ten business days"}]}


def test_note_keeps_the_transcripts_own_words():
    client, fake = spark(GOOD)
    c = test_appeal.case()
    note = voice.read_note(client, c, voice.Transcript(ES_NOTE, "es"), "Lakeview Demo Hospital")
    assert (note.rep_name, note.reference, len(note.promises), note.dropped) == ("Morgan", "48213", 1, [])
    body = fake.bodies[0]
    assert body["model"] == "muse-spark-1.3" and body["store"] is False
    p = note.paragraph(c, "es").text
    assert p.startswith("On October 27, 2026 I called Lakeview Demo Hospital and spoke with Morgan "
                        "(reference number 48213).")
    assert "“van a revisar la cuenta en diez días hábiles.”" in p and "my translation" in p


def test_words_not_in_the_note_are_dropped():
    bad = {"rep_name": {"value": "Taylor", "quote": "I spoke with Taylor."},
           "reference": {"value": "99999", "quote": "El número de referencia es 48213."},
           "promises": [{"quote": "they will waive the whole bill", "english": "they will waive the whole bill"},
                        {"quote": "van a revisar la cuenta en diez días hábiles",
                         "english": "they will review the account within 10 business days and refund $500"}]}
    client, _ = spark(bad)
    note = voice.read_note(client, test_appeal.case(), voice.Transcript(ES_NOTE, "es"), "Lakeview Demo Hospital")
    assert note.rep_name == "" and note.reference == "" and note.promises == []
    assert len(note.dropped) == 4
    assert note.paragraph(test_appeal.case(), "es") is None


def test_english_note_has_no_translation_line():
    en = "I talked to Morgan. Reference number 48213. They said they will send the itemized bill this week."
    client, _ = spark({"rep_name": {"value": "Morgan", "quote": "I talked to Morgan."},
                       "reference": {"value": "", "quote": ""},
                       "promises": [{"quote": "they will send the itemized bill this week",
                                     "english": "they will send the itemized bill this week"}]})
    note = voice.read_note(client, test_appeal.case(), voice.Transcript(en, "en"), "Lakeview Demo Hospital")
    p = note.paragraph(test_appeal.case(), "en").text
    assert "my translation" not in p and "reference number" not in p


def test_call_paragraph_goes_before_the_closing_line():
    c = test_appeal.case()
    [letter] = writer.appeal_letters(c)
    client, _ = spark(GOOD)
    para = voice.read_note(client, c, voice.Transcript(ES_NOTE, "es"), "Sample Health Plan").paragraph(c, "es")
    out = voice.with_call_note(letter, para)
    assert out.paragraphs[-2] is para and out.paragraphs[-1].text.startswith("Please send your decision")
    assert len(out.paragraphs) == len(letter.paragraphs) + 1 and out.kind == letter.kind
    assert letter.paragraphs[-2] is not para  # the original letter is unchanged


def test_no_keyword_is_longer_than_the_model_takes():
    """Meta answers HTTP 400 past 30 characters ("ASR keyword 4 exceeds the maximum length of 30 characters")."""
    c = test_appeal.case()
    c = c.model_copy(update={"letterhead": "Cradleview-Obstetrix Medical Group of the Greater Riverton Area"})
    words = voice.keywords(c)
    assert words and all(len(w) <= voice.KEYWORD_MAX for w in words) and voice.KEYWORD_MAX == 30
    assert words[0].startswith("Cradleview-Obstetrix")  # whole words, not cut in the middle of one
