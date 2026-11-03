"""Help during a live phone call with the billing office or the insurer.

The family's phone audio streams to Muse Voice Transcribe over
wss://api.meta.ai/v1/asr/realtime (dev.meta.ai/docs/api-reference/voice/realtime.md), in DIARIZATION
mode so each turn carries a speaker label. When the other side finishes a turn, Muse Spark only picks
which prepared answer from the call cheat sheet fits; every answer there was already built in code
from a verified quote, so nothing new is claimed during the call. What the other side says about a
name, a reference number or a promise is captured in their own words.

Rules held in code:
  - consent first: the consent phrase is said and the family presses "They agreed" before the stream
    can open (in Florida every party to a call must agree to recording, F.S. 934.03);
  - only a fictional, synthetic call goes to the live model until the owner says otherwise;
  - audio is never stored; the transcript lives in this object's memory and is gone on close().
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from billradar import i18n
from billradar.callprep import CallSheet
from billradar.case import Case
from billradar.meta_client import RECORDINGS, MetaAPIError, MetaClient, ReplayMissing
from billradar.pipeline import RealDataGate

REALTIME_URL = "wss://api.meta.ai/v1/asr/realtime"  # dev.meta.ai/docs/api-reference/voice/realtime.md
ASR_MODEL = "muse-voice-transcribe-1.0"
NOT_HEARD = "We could not work out that turn. Keep going, and ask for it in writing."
SPARK = "muse-spark-1.3"
RATE = 16_000
FRAME_BYTES = RATE * 2 * 80 // 1000  # 80 ms of 16-bit mono PCM

CONSENT = {
    "en": "Before we start: I'm using an app to take notes of this call. Is it OK with you if this call "
          "is transcribed?",
    "es": "Antes de empezar: uso una aplicación para tomar notas de esta llamada. ¿Está de acuerdo en que "
          "se transcriba la llamada?",
}


# A turn worth looking up: they state a rule, a limit or a refusal. Small talk is not searched.
RULE_TALK = re.compile(r"(?i)\b(?:days?|months?|deadline|policy|law|rule|required|must|cannot|can't|won't|only|"
                       r"eligible|qualify|denied|collections?|appeal|apply)\b")


class ConsentRequired(RuntimeError):
    pass


def handshake(api_key: str, language: str, keywords: list[str]) -> dict:
    """The first text frame, as documented (RealtimeHandshakeRequest)."""
    from billradar.voice import LANGUAGES
    h = {"authorization": {"accessToken": f"Bearer {api_key}"}, "audioEncoding": "PCM_16KHZ",
         "model": ASR_MODEL, "mode": "DIARIZATION", "emitAudioProgress": False,
         "languageBias": [LANGUAGES[language]]}
    if keywords:
        h["keywords"] = keywords
    return h


def _key(hs: dict, audio_digest: str) -> str:
    public = {k: v for k, v in hs.items() if k != "authorization"}  # the key never reaches a file name or log
    return hashlib.sha256((json.dumps(public, sort_keys=True) + audio_digest).encode()).hexdigest()[:20]


class LiveRealtime:
    """The WebSocket session. Audio frames go out paced at real time; events come back as they arrive."""

    def __init__(self, api_key: str, url: str = REALTIME_URL, record_to: Path | None = RECORDINGS):
        self.api_key, self.url, self.record_to = api_key, url, record_to

    def events(self, hs: dict, frames: Iterable[bytes]) -> Iterator[dict]:
        """Yields server events; afterwards records them (events only: no audio, no key) for replay."""
        sent = hashlib.sha256()
        got: list[dict] = []

        def counted(src: Iterable[bytes]) -> Iterator[bytes]:
            for chunk in src:
                sent.update(chunk)  # a running hash; the audio itself is not kept
                yield chunk

        for ev in self._stream(hs, counted(frames)):
            got.append(ev)
            yield ev
        if self.record_to:
            self.record_to.mkdir(parents=True, exist_ok=True)
            out = self.record_to / f"{ASR_MODEL}-realtime-{_key(hs, sent.hexdigest())}.jsonl"
            out.write_text("".join(json.dumps(e) + "\n" for e in got))

    def _stream(self, hs: dict, frames: Iterable[bytes]) -> Iterator[dict]:
        from websockets.sync.client import connect  # optional dependency, live runs only
        with connect(self.url, open_timeout=30) as ws:
            ws.send(json.dumps(hs))
            ack = json.loads(ws.recv(timeout=15))
            if "sessionId" not in ack:
                raise MetaAPIError(f"realtime handshake failed: {str(ack)[:200]}")

            def send() -> None:
                for chunk in frames:
                    ws.send(chunk)
                    time.sleep(0.08)
                ws.send(json.dumps({"type": "endStream"}))

            sender = threading.Thread(target=send, daemon=True)
            sender.start()
            for message in ws:  # ends when the server closes (1000 on success)
                if isinstance(message, bytes):
                    continue
                yield json.loads(message)
            sender.join(timeout=5)


class ReplayRealtime:
    """Recorded server events (no audio, no key), keyed like the other recordings."""

    def __init__(self, directory: Path = RECORDINGS):
        self.directory = directory

    def path(self, hs: dict, audio_digest: str) -> Path:
        return self.directory / f"{ASR_MODEL}-realtime-{_key(hs, audio_digest)}.jsonl"

    def events(self, hs: dict, frames: Iterable[bytes]) -> Iterator[dict]:
        h = hashlib.sha256()
        for chunk in frames:
            h.update(chunk)
        digest = h.hexdigest()
        p = self.path(hs, digest)
        if not p.exists():
            raise ReplayMissing(f"no recording {p.name}; run once live to record it")
        for line in p.read_text().splitlines():
            if line.strip():
                yield json.loads(line)


@dataclass
class Turn:
    turn_id: int
    speaker: str  # the model's label ("A", "B"), session-scoped, not an identity
    who: str  # "you", "them" or "?"
    text: str


@dataclass
class Update:
    kind: str  # "partial", "turn", "suggestion", "captured", "error", "closed"
    data: dict = field(default_factory=dict)


ROUTE_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["side", "answer", "rep_name", "reference", "promise"],
    "properties": {
        "side": {"type": "string", "enum": ["office", "caller", "unclear"]},
        "answer": {"type": "string"},
        "rep_name": {"type": "object", "additionalProperties": False, "required": ["value", "quote"],
                     "properties": {"value": {"type": "string"}, "quote": {"type": "string"}}},
        "reference": {"type": "object", "additionalProperties": False, "required": ["value", "quote"],
                      "properties": {"value": {"type": "string"}, "quote": {"type": "string"}}},
        "promise": {"type": "string"},
    },
}
ROUTE_INSTRUCTIONS = """You help a parent during a phone call with a hospital billing office or an insurance company. You never give medical advice and you never write new advice.

You get one turn of the call, and a numbered list of prepared answers (each with what the office might say). Return:
- side: "office" if the billing office or insurer said this turn, "caller" if the parent said it, "unclear" if you cannot tell.
- answer: the number of the prepared answer that fits what the office just said, or "none" (always "none" for the caller).
- rep_name: the name the other side gave for themselves, with the exact words that contain it; empty strings if none.
- reference: a reference, ticket or confirmation number they said, with the exact words; empty strings if none.
- promise: the exact words of anything they said they will do (for example review, call back, send a bill), or "".
Copy words exactly as transcribed."""


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


class CallSession:
    def __init__(self, rt, spark: MetaClient, case: Case, sheet: CallSheet, language: str = "en",
                 live: bool = False, journal: Path | None = None, tavily=None):
        if language not in CONSENT:
            raise ValueError(f"live help works in {', '.join(CONSENT)}; Muse Voice Transcribe has no {language!r}")
        self.rt, self.spark, self.case, self.sheet, self.language = rt, spark, case, sheet, language
        self.live = live or isinstance(rt, LiveRealtime)
        self.journal = journal
        self.tavily = tavily  # the ladder's web step; None: straight to the phrase to say
        self.consent_at: str | None = None
        self.turns: list[Turn] = []
        self.captured: dict[str, str] = {}
        self.promises: list[str] = []
        self._sides: dict[str, str] = {}  # speaker label -> "you" / "them", fixed once known
        self.closed = False

    # --- consent ------------------------------------------------------------------------------
    @property
    def consent_phrase(self) -> str:
        return CONSENT[self.language]

    def they_agreed(self) -> None:
        """The family pressed "They agreed" after saying the consent phrase."""
        self.consent_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _gate(self) -> None:
        if self.closed:
            raise ConsentRequired("this call is closed")
        if not self.consent_at:
            raise ConsentRequired("say the consent phrase and press 'They agreed' before the call is transcribed")
        if self.live and not self.case.demo:
            raise RealDataGate("live call help runs only on a fictional, synthetic call for now")

    # --- the stream -----------------------------------------------------------------------------
    def run(self, frames: Iterable[bytes], api_key: str = "") -> Iterator[Update]:
        self._gate()
        from billradar.voice import keywords
        hs = handshake(api_key, self.language, keywords(self.case))
        speakers: dict[int, str] = {}
        current: int | None = None
        partial = ""
        for ev in self.rt.events(hs, frames):
            t = ev.get("type")
            if t == "speechStart":
                current, partial = ev.get("turnId"), ""
            elif t == "transcript":
                partial = ev.get("transcript", "")
                yield Update("partial", {"text": partial})
            elif t == "speaker" and current is not None:
                speakers[current] = ev.get("label", "")
            elif t == "speechComplete":
                turn = self._turn(ev.get("turnId"), speakers.get(ev.get("turnId"), ""), ev.get("transcript", ""))
                if turn.who != "you":
                    yield from self._help(turn)
                yield Update("turn", turn.__dict__.copy())
            elif t == "error":
                yield Update("error", {"message": ev.get("message", "")})
        self._log()
        yield Update("closed", {"turns": len(self.turns)})

    def this_is_me(self, label: str) -> None:
        """The family taps "That's me" on a turn: its label is theirs, the other labels are the office."""
        self._sides = {label: "you"}
        for t in self.turns:
            t.who = self._who(t.speaker)

    def _who(self, label: str) -> str:
        if not label:
            return "?"
        if label in self._sides:
            return self._sides[label]
        return "them" if "you" in self._sides.values() else "?"

    def _learn(self, label: str, side: str) -> None:
        """The first clear side seen for a label fixes it (the transcript cannot hear the consent, which
        was given before the stream opened)."""
        if label and label not in self._sides and side in ("office", "caller"):
            self._sides[label] = "them" if side == "office" else "you"
            for t in self.turns:
                t.who = self._who(t.speaker)

    def _turn(self, turn_id: int, label: str, text: str) -> Turn:
        turn = Turn(turn_id, label, self._who(label), text)
        self.turns.append(turn)
        return turn

    def _help(self, turn: Turn) -> Iterator[Update]:
        from billradar.web_answer import ASK_IN_WRITING
        options = self.sheet.objections
        if not options:
            return
        values = i18n.private_values(self.case)
        listing = "\n".join(f"{i}. They might say: {o.they_say}" for i, o in enumerate(options, 1))
        body = {"model": SPARK, "store": False, "stream": True, "reasoning": {"effort": "low"},
                "max_output_tokens": 2000,  # 800 ran out on the first live call: the reasoning counts in it
                "text": {"format": {"type": "json_schema", "name": "billradar_call_turn", "schema": ROUTE_SCHEMA,
                                    "strict": True}},
                "input": [{"role": "developer", "content": [{"type": "input_text", "text": ROUTE_INSTRUCTIONS}]},
                          {"role": "user", "content": [{"type": "input_text", "text":
                              f"Prepared answers:\n{listing}\n\nThis turn:\n"
                              f"{i18n.mask(turn.text, values)}"}]}]}
        if self.spark.live and not self.case.demo:
            raise RealDataGate("live model calls are allowed only for a fictional case")
        try:
            raw = json.loads(self.spark.respond(body, label="spark:call-turn").text)
        except (MetaAPIError, ValueError):  # one turn lost, not the call: say what to do and listen on
            yield Update("no_answer", {"text": NOT_HEARD, "say": ASK_IN_WRITING, "turn_id": turn.turn_id})
            return
        self._learn(turn.speaker, raw.get("side", "unclear"))
        turn.who = self._who(turn.speaker)
        if turn.who == "you" or (turn.who == "?" and raw.get("side") != "office"):
            return
        pick = (raw.get("answer") or "").strip()
        if pick.isdigit() and 1 <= int(pick) <= len(options):
            o = options[int(pick) - 1]
            yield Update("suggestion", {"they_say": o.they_say, "say": o.answer, "refs": o.refs,
                                        "turn_id": turn.turn_id})
        elif RULE_TALK.search(turn.text):
            yield from self._ladder(turn)
        heard = _norm(turn.text)
        for key in ("rep_name", "reference"):
            item = raw.get(key) or {}
            value, quote = (item.get("value") or "").strip(), (item.get("quote") or "").strip()
            if value and quote and _norm(quote) in heard and _norm(value) in _norm(quote):
                self.captured[key] = value
                yield Update("captured", {"field": key, "value": value, "words": quote})
        promise = (raw.get("promise") or "").strip()
        if promise and _norm(promise) in heard:
            self.promises.append(promise)
            yield Update("captured", {"field": "promise", "value": promise, "words": promise})

    def _ladder(self, turn: Turn) -> Iterator[Update]:
        """They state a rule and nothing prepared fits: the web, quoted word for word, or a phrase to say. Never invented."""
        from billradar import web_answer
        found = None
        if self.tavily is not None:
            try:
                found = web_answer.find(self.spark, self.tavily, self.case, turn.text)
            except (web_answer.TavilyError, MetaAPIError, ValueError):
                found = None  # a failed search ends the same way as an empty one
        if found:
            yield Update("web", {"quote": found.quote, "url": found.url, "title": found.title, "label": found.label,
                                 "seconds": found.seconds, "turn_id": turn.turn_id})
        else:
            yield Update("no_answer", {"text": web_answer.NOT_IN_CASE, "say": web_answer.ASK_IN_WRITING,
                                       "turn_id": turn.turn_id})

    # --- after the call --------------------------------------------------------------------------
    def note(self):
        """What was captured, as the voice-note helper's CallNote: it becomes a paragraph of a letter."""
        from billradar.voice import CallNote
        return CallNote(who=self.sheet.who, rep_name=self.captured.get("rep_name", ""),
                        reference=self.captured.get("reference", ""), promises=[(p, p) for p in self.promises],
                        replayed=not self.live)

    def close(self) -> None:
        """End of the case's call: the transcript leaves memory. Audio was never kept."""
        self.turns.clear()
        self.captured.clear()
        self.promises.clear()
        self.closed = True

    def _log(self) -> None:
        if not self.journal:
            return
        entry = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "label": "voice:live-call",
                 "model": ASR_MODEL, "live": self.live, "turns": len(self.turns), "consent_at": self.consent_at}
        self.journal.parent.mkdir(parents=True, exist_ok=True)
        with self.journal.open("a") as f:
            f.write(json.dumps(entry) + "\n")


def pcm_frames(pcm: bytes) -> Iterator[bytes]:
    for i in range(0, len(pcm), FRAME_BYTES):
        yield pcm[i:i + FRAME_BYTES]
