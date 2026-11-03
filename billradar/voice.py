"""After the call: the family's voice note becomes a paragraph of the letter.

1. Muse Voice Transcribe turns the WAV note into text. It knows 25 languages; English and Spanish
   are among them, Russian is not (dev.meta.ai/docs/speech-to-text.md), so the note is recorded
   in English or Spanish.
2. Muse Spark picks out who they spoke with, the reference number and what was promised, each with
   the exact words from the transcript. Code keeps only what is really in the transcript.
3. The paragraph quotes those words. A Spanish note keeps the Spanish words, with the family's
   translation next to them, and a translation may not carry a number the words do not.

The voice note goes to Meta's cloud, so a live call is allowed only on a fictional case,
the same gate as the papers.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from billradar import context
from billradar.case import Case
from billradar.meta_client import MetaClient
from billradar.pipeline import RealDataGate
from billradar.writer import Letter, Paragraph

ASR_MODEL = "muse-voice-transcribe-1.0"  # dev.meta.ai/docs/api-reference/voice/transcribe.md
SPARK = "muse-spark-1.3"
LANGUAGES = {"en": "English", "es": "Spanish"}


class LanguageNotSupported(ValueError):
    pass


@dataclass
class Transcript:
    text: str
    language: str  # the language the family picked: "en" or "es"
    duration_ms: int | None = None
    replayed: bool = True


def transcribe_request(language: str, keywords: list[str]) -> dict:
    if language not in LANGUAGES:
        raise LanguageNotSupported(
            f"voice notes can be in {', '.join(LANGUAGES.values())}; Muse Voice Transcribe has no {language!r}")
    req = {"model": ASR_MODEL, "audioEncoding": "WAV", "mode": "PUSH_TO_TALK", "languageBias": [LANGUAGES[language]]}
    if keywords:
        req["keywords"] = keywords
    return req


KEYWORD_MAX = 30  # the model refuses a longer one: "ASR keyword 4 exceeds the maximum length of 30 characters" (HTTP 400)


def _fit(word: str) -> str:
    """As many whole words of a long name as the model takes."""
    kept = ""
    for part in word.split():
        if len(kept) + len(part) + 1 > KEYWORD_MAX:
            break
        kept = f"{kept} {part}".strip()
    return kept or word[:KEYWORD_MAX]


def keywords(case: Case) -> list[str]:
    """Words the model might mishear: who was called, and the words of billing. Never a family name."""
    words = [case.letterhead] + [d.provider for d in case.eobs()]
    words += ["itemized bill", "financial assistance", "appeal", "prior authorization", "reference number"]
    return list(dict.fromkeys(_fit(w) for w in words if w))


def transcribe(client: MetaClient, case: Case, wav: bytes, language: str = "en") -> Transcript:
    if client.live and not case.demo:
        raise RealDataGate("live transcription is allowed only for a fictional case")
    answer, replayed = client.transcribe(transcribe_request(language, keywords(case)), wav, label="voice:note")
    return Transcript(answer.get("transcript", "").strip(), language, answer.get("audioDurationMs"), replayed)


# --- the voice helper on the site: speak, and the chips are set ------------------------------

def transcribe_audio(client: MetaClient, wav: bytes, language: str = "en", label: str = "voice:intake") -> Transcript:
    """No case yet, so the words to listen for are the words of billing."""
    request = transcribe_request(language, ["itemized bill", "financial assistance", "collections", "emergency room"])
    answer, replayed = client.transcribe(request, wav, label=label)
    return Transcript(answer.get("transcript", "").strip(), language, answer.get("audioDurationMs"), replayed)


CHIPS_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["chips"],
    "properties": {"chips": {"type": "array", "items": {"type": "string", "enum": [c.id for c in context.CHIPS]}}},
}
CHIPS_INSTRUCTIONS = """A family tells a helper for hospital bills what happened, in their own words. You do not give medical advice.

Pick every chip the words clearly say; pick none when they say nothing that fits. The chips, as id: meaning:
""" + "\n".join(f"{c.id}: {c.label}" for c in context.CHIPS)


def chips_body(transcript: Transcript) -> dict:
    return {
        "model": SPARK, "store": False, "stream": True, "reasoning": {"effort": "low"}, "max_output_tokens": 1000,
        "text": {"format": {"type": "json_schema", "name": "billradar_chips", "schema": CHIPS_SCHEMA, "strict": True}},
        "input": [{"role": "developer", "content": [{"type": "input_text", "text": CHIPS_INSTRUCTIONS}]},
                  {"role": "user", "content": [{"type": "input_text", "text": transcript.text}]}],
    }


def pick_chips(client: MetaClient, transcript: Transcript) -> list[str]:
    res = client.respond(chips_body(transcript), label="spark:voice-chips")
    return context.valid(json.loads(res.text).get("chips", []))


# --- what was said, in the transcript's own words -------------------------------------------

_q = {"type": "string"}
NOTE_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["rep_name", "reference", "promises"],
    "properties": {
        "rep_name": {"type": "object", "additionalProperties": False, "required": ["value", "quote"],
                     "properties": {"value": _q, "quote": _q}},
        "reference": {"type": "object", "additionalProperties": False, "required": ["value", "quote"],
                      "properties": {"value": _q, "quote": _q}},
        "promises": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["quote", "english"],
            "properties": {"quote": _q, "english": _q}}},
    },
}

NOTE_INSTRUCTIONS = """You read a short voice note a parent recorded after a phone call with a hospital billing office or an insurance company. You help with bills and insurance only; you never give medical advice.

Return:
- rep_name: the name of the person they spoke with. value = the name; quote = the exact words from the note that contain it. Empty strings if the note does not say.
- reference: the reference or ticket number for the call. value = the number as said; quote = the exact words that contain it. Empty strings if not said.
- promises: what the office said it would do or what it told the parent, one item each. quote = the exact words from the note, copied character for character. english = the same words in plain English (the same text if the note is in English). Never add a number, a date or a promise that is not in the quote.
Copy quotes exactly as they appear in the note. Do not fix spelling. Do not summarize inside a quote."""


def note_body(transcript: Transcript, who: str) -> dict:
    return {
        "model": SPARK, "store": False, "stream": True, "reasoning": {"effort": "low"}, "max_output_tokens": 2000,
        "text": {"format": {"type": "json_schema", "name": "billradar_call_note", "schema": NOTE_SCHEMA,
                            "strict": True}},
        "input": [
            {"role": "developer", "content": [{"type": "input_text", "text": NOTE_INSTRUCTIONS}]},
            {"role": "user", "content": [{"type": "input_text",
                                          "text": f"The call was with: {who}\nVoice note ({LANGUAGES[transcript.language]}):\n"
                                                  f"{transcript.text}"}]},
        ],
    }


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("’", "'").replace("“", '"').replace("”", '"')).strip().lower()


def _digits(s: str) -> list[str]:
    return re.findall(r"\d+", s.replace(",", ""))


@dataclass
class CallNote:
    who: str
    rep_name: str = ""
    reference: str = ""
    promises: list[tuple[str, str]] = field(default_factory=list)  # (exact words, English)
    dropped: list[str] = field(default_factory=list)
    replayed: bool = True

    def paragraph(self, case: Case, language: str) -> Paragraph | None:
        if not (self.rep_name or self.reference or self.promises):
            return None
        head = f"On {case.today:%B %-d, %Y} I called {self.who}"
        if self.rep_name:
            head += f" and spoke with {self.rep_name}"
        if self.reference:
            head += f" (reference number {self.reference})"
        parts = [head + "."]
        for words, english in self.promises:
            said = words.rstrip(" .") + "."  # each promise ends its own sentence, however the model cut it
            if language == "en" or _norm(words) == _norm(english):
                parts.append(f"I was told: “{said}”")
            else:
                parts.append(f"I was told: “{said}” (my translation: “{english.rstrip(' .')}.”)")
        return Paragraph(" ".join(parts))


def read_note(client: MetaClient, case: Case, transcript: Transcript, who: str) -> CallNote:
    """Spark proposes; code keeps only words that are really in the transcript."""
    if client.live and not case.demo:
        raise RealDataGate("live model calls are allowed only for a fictional case")
    res = client.respond(note_body(transcript, who), label="spark:call-note")
    raw = json.loads(res.text)
    text = _norm(transcript.text)
    note = CallNote(who=who, replayed=res.replayed)
    for key in ("rep_name", "reference"):
        item = raw.get(key) or {}
        value, quote = (item.get("value") or "").strip(), (item.get("quote") or "").strip()
        if not value:
            continue
        if quote and _norm(quote) in text and _norm(value) in _norm(quote):
            setattr(note, key, value)
        else:
            note.dropped.append(f"{key} {value!r}: not in the note's own words")
    for p in raw.get("promises", []):
        words, english = (p.get("quote") or "").strip(), (p.get("english") or "").strip()
        if not words or _norm(words) not in text:
            note.dropped.append(f"promise {words[:50]!r}: not in the note's own words")
        elif not set(_digits(english)) <= set(_digits(words)):
            note.dropped.append(f"promise {words[:50]!r}: translation carries a number the words do not")
        else:
            note.promises.append((words, english or words))
    return note


def with_call_note(letter: Letter, paragraph: Paragraph) -> Letter:
    """The same letter with the call paragraph just before the closing line."""
    paras = list(letter.paragraphs)
    at = len(paras) - 1 if paras and not paras[-1].refs and "Thank you" in paras[-1].text else len(paras)
    paras.insert(at, paragraph)
    return Letter(**{**letter.__dict__, "paragraphs": paras})
