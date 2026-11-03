"""Meta Model API client for BillRadar.

Answers come from one of two places: a live POST to api.meta.ai (only when a key and
BILLRADAR_LIVE=1 are set; every live answer is saved to disk and its worst-case cost is
reserved in the spend book first) or a replay of those saved files (a missing file is an
error, never a stand-in). Each call also leaves a content-free line in the local journal.
"""

from __future__ import annotations

import base64
import fcntl
import hashlib
import json
import os
import random
import re
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import requests

API_URL = "https://api.meta.ai/v1/responses"
# Muse Voice Transcribe: one recording per request, WAV only, up to 10 minutes and 32 MB
# (dev.meta.ai/docs/api-reference/voice/transcribe.md).
ASR_URL = "https://api.meta.ai/v1/asr/transcribe"
ASR_MODELS = {"muse-voice-transcribe-1.0"}
# Muse Image: one flat price per image (dev.meta.ai/docs/api-reference/images/create-image.md).
IMAGE_URL = "https://api.meta.ai/v1/images/generations"
IMAGE_MODELS = {"muse-image-1.0"}
ROOT = Path(__file__).resolve().parents[1]
RECORDINGS = ROOT / "tests" / "fixtures" / "recordings"
JOURNAL = ROOT / "runs" / "requests.jsonl"
SPEND = ROOT / "runs" / "meta-spend.jsonl"

ALLOWED_MODELS = {"sam-3.1", "muse-spark-1.3", "muse-wonder-1.0", "meta-models/muse-spark-open-1026"}
RETRY_STATUS = {429, 500, 503}

# dev.meta.ai/docs/pricing-rate-limits, Standard mode, USD. (input, cached input, output) per 1M tokens;
# reasoning is already inside output_tokens (docs/quickstart: output_tokens 258, of which reasoning_tokens 241).
PRICES = {"muse-spark-1.3": (1.25, 0.15, 4.25), "muse-wonder-1.0": (4.00, 0.20, 20.00),
          "meta-models/muse-spark-open-1026": (1.25, 0.15, 4.25)}  # the open weights on Baseten, its published price
FLAT = {"sam-3.1": 2.50 / 1000, "muse-image-1.0": 0.01}  # per request here: one image each
VIDEO_FPS = 10  # the rate of the copy sent to SAM (billradar.video)
MAX_VIDEO_FRAMES = 900  # 90 seconds of it
SEARCH_USD = 2.50 / 1000  # one web_search call, on top of the tokens
ASR_PER_HOUR = 0.18
IMAGE_TOKENS_GUESS = 3000  # per image, for the reservation only
FILE_TOKENS_GUESS = 30000  # per file, for the reservation only


class MetaAPIError(RuntimeError):
    pass


class ReplayMissing(MetaAPIError):
    pass


class SpendCapReached(RuntimeError):
    """Not a MetaAPIError: optional steps catch that and go on; the cap has to stop the run."""


def cost_of(model: str, usage: dict) -> float:
    p_in, p_cached, p_out = PRICES[model]
    total = usage.get("input_tokens", 0)
    cached = (usage.get("input_tokens_details") or {}).get("cached_tokens", 0)
    return ((total - cached) * p_in + cached * p_cached + usage.get("output_tokens", 0) * p_out) / 1e6


def flat_cost(model: str) -> float:
    return FLAT[model]


def asr_cost(duration_ms: int) -> float:
    return ASR_PER_HOUR * (duration_ms or 0) / 3_600_000


def call_cost(model: str, usage: dict) -> float:
    return cost_of(model, usage) if model in PRICES else FLAT.get(model, 0.0)


def video_cost(frames: int) -> float:
    """SAM on video: $0.20 per 1,000 frames, each request billed for at least 50."""
    return 0.20 / 1000 * max(50, frames)


def _is_video(body: dict) -> bool:
    return any(isinstance(item.get("content"), list) and any(p.get("type") == "input_video" for p in item["content"])
               for item in body.get("input", []) if isinstance(item, dict))


def _frames_answered(events: list[dict]) -> int:
    text = "".join(e.get("delta", "") for e in events if e.get("type") == "response.output_text.delta")
    return len(set(re.findall(r"<(\d+)f>", text)))


def search_calls(events: list[dict]) -> list[dict]:
    """The web_search_call items of a finished answer."""
    final = next((e for e in events if e.get("type") == "response.completed"), {})
    return [item for item in (final.get("response") or {}).get("output") or [] if item.get("type") == "web_search_call"]


def data_url(raw: bytes, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")


def _media_digest(url: str) -> str:
    return "sha256:" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def _strip_media(obj):
    """Copy of obj with every "data:" string swapped for its digest (dicts and lists only)."""
    if isinstance(obj, str):
        return _media_digest(obj) if obj.startswith("data:") else obj
    if isinstance(obj, dict):
        fresh = {}
        for name, inner in obj.items():
            fresh[name] = _strip_media(inner)
        return fresh
    if isinstance(obj, list):
        items = []
        for inner in obj:
            items.append(_strip_media(inner))
        return items
    return obj


def kept(obj):
    """What a recording keeps: the model's encrypted reasoning means nothing to a replay."""
    if isinstance(obj, dict):
        return {k: kept(v) for k, v in obj.items() if k != "encrypted_content"}
    return [kept(v) for v in obj] if isinstance(obj, list) else obj


def recording_name(body: dict) -> str:
    """One flat file: a model id may hold a slash ("meta-models/muse-spark-open-1026")."""
    return f"{body['model'].replace('/', '-')}-{request_key(body)}.jsonl"


def request_key(body: dict) -> str:
    """Name of a request: 20 hex chars of the SHA-256 of its canonical JSON, media replaced by digests.
    The canonical form (sorted keys, tight separators, ASCII) fixes every recording's file name."""
    canonical = json.dumps(_strip_media(body), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:20]


def _count_media(body: dict) -> tuple[int, int, int]:
    """(images, files, characters of image_url / file_data strings) over body["input"]."""
    images = files = chars = 0
    for item in body.get("input", []):
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            kind = part.get("type")
            if kind == "input_image":
                images += 1
            elif kind == "input_file":
                files += 1
            for field_name in ("image_url", "file_data"):
                value = part.get(field_name)
                if isinstance(value, str):
                    chars += len(value)
    return images, files, chars


def worst_case(body: dict) -> float:
    model = body["model"]
    if model not in PRICES:
        return video_cost(MAX_VIDEO_FRAMES) if _is_video(body) else FLAT.get(model, 0.0)
    p_in, _, p_out = PRICES[model]
    chars = 0
    for item in body.get("input", []):
        content = item.get("content")
        for part in content if isinstance(content, list) else [{"text": content or ""}]:
            chars += len(part.get("text") or "")
    images, files, _ = _count_media(body)
    tokens_in = chars / 3 + images * IMAGE_TOKENS_GUESS + files * FILE_TOKENS_GUESS
    return (tokens_in * p_in + body.get("max_output_tokens", 8000) * p_out) / 1e6


class SpendLedger:
    """Append-only reservations and settlements, flock-guarded so parallel runs share one cap."""

    def __init__(self, path: Path = SPEND, cap: float | None = None, daily: float | None = None):
        self.path = path
        self.cap = cap if cap is not None else float(os.environ.get("META_SPEND_CAP_USD", "40"))
        self.daily = daily if daily is not None else float(os.environ.get("BILLRADAR_DAILY_SPEND_USD", "0") or 0)

    def _append(self, usd: float, note: str, check: bool) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a+") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                if check:
                    spent = self._total(f)
                    if spent + usd > self.cap:
                        raise SpendCapReached(f"${usd:.4f} more would pass the ${self.cap:.2f} cap "
                                              f"(${spent:.4f} spent or reserved); raise META_SPEND_CAP_USD on purpose")
                    today = self._total(f, datetime.now(timezone.utc).date().isoformat())
                    if self.daily and today + usd > self.daily:
                        raise SpendCapReached(f"${usd:.4f} more would pass today's ${self.daily:.2f} ceiling (${today:.4f} so far)")
                f.seek(0, os.SEEK_END)
                f.write(json.dumps({"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                    "usd": round(usd, 6), "note": note}) + "\n")
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    @staticmethod
    def _total(f, day: str = "") -> float:
        f.seek(0)
        rows = (json.loads(line) for line in f if line.strip())
        return sum(float(r.get("usd", 0)) for r in rows if r["at"].startswith(day))  # a line with no sum spends nothing

    def spent(self) -> float:
        if not self.path.exists():
            return 0.0
        with self.path.open() as f:
            return self._total(f)

    def reserve(self, usd: float, note: str) -> None:
        self._append(usd, note, check=True)

    def settle(self, usd: float, note: str) -> None:
        self._append(usd, note, check=False)


def check_body(body: dict) -> None:
    """Gate for every Responses request: Standard models only, nothing stored, at most 50 images."""
    model = body.get("model")
    refusal = None
    if model not in ALLOWED_MODELS:
        refusal = f"model {model!r} is not allowed (Standard models only: {sorted(ALLOWED_MODELS)})"
    elif model != "sam-3.1" and body.get("store") is not False:  # the flag is not checked for SAM
        refusal = "store must be false: Responses stores answers by default"
    else:
        picture_count = _count_media(body)[0]
        if picture_count > 50:
            refusal = f"{picture_count} images: the API accepts at most 50 per request"
    if refusal is not None:
        raise MetaAPIError(refusal)


def parse_sse(lines: Iterator[bytes]) -> Iterator[dict]:
    """Lazily turn SSE lines into events; stops at [DONE], skips everything but "data:" lines."""
    for raw in lines:
        text = str(raw, "utf-8", "replace") if isinstance(raw, bytes) else raw
        lead, marker, rest = text.partition("data:")
        if lead or not marker:
            continue  # a comment, an "event:" line, a blank, or "data:" not at column 0
        rest = rest.strip()
        if rest == "[DONE]":
            break
        yield json.loads(rest)


@dataclass
class Result:
    text: str
    events: list[dict]
    usage: dict = field(default_factory=dict)
    response_id: str = ""
    replayed: bool = False
    seconds: float = 0.0


FINAL_EVENTS = ("response.completed", "response.failed", "response.incomplete")


def collect(events: list[dict]) -> tuple[str, dict, str]:
    """(text, usage, response id) of a finished stream; a cut-off or failed stream is an error."""
    # An error event anywhere beats a later "completed".
    for event in events:
        if event.get("type") == "error":
            raise MetaAPIError(f"stream error {event.get('code')}: {event.get('message')}")
    endings = [event for event in events if event.get("type") in FINAL_EVENTS]
    if not endings:
        raise MetaAPIError("stream ended without a final event (partial output)")
    last = endings[-1]
    body = last.get("response") or {}
    if last["type"] != "response.completed":
        # Only the reason goes into the message: it may reach the screen.
        details = body.get("incomplete_details") or {}
        failure = body.get("error") or {}
        reason = details.get("reason") or failure.get("message") or "no reason given"
        raise MetaAPIError(f"response ended with {last['type']}: {reason}")
    deltas = (event.get("delta") or "" for event in events if event.get("type") == "response.output_text.delta")
    return "".join(deltas), body.get("usage", {}), body.get("id", "")


def asr_key(request: dict, audio: bytes) -> str:
    canon = json.dumps(request, sort_keys=True, separators=(",", ":")) + hashlib.sha256(audio).hexdigest()
    return hashlib.sha256(canon.encode()).hexdigest()[:20]


def check_asr(request: dict, audio: bytes) -> None:
    if request.get("model") not in ASR_MODELS:
        raise MetaAPIError(f"model {request.get('model')!r} is not a transcription model ({sorted(ASR_MODELS)})")
    if request.get("audioEncoding") != "WAV" or audio[:4] != b"RIFF" or audio[8:12] != b"WAVE":
        raise MetaAPIError("transcription takes a WAV recording (RIFF/WAVE, mono PCM 16 or 24 kHz)")
    if len(audio) > 32 * 1024 * 1024:
        raise MetaAPIError("recording is over 32 MB")


class LiveTransport:
    def __init__(self, api_key: str, attempts: int = 4, timeout: float = 300.0, ledger: SpendLedger | None = None):
        self.api_key = api_key
        self.attempts = attempts
        self.timeout = timeout
        self.ledger = ledger if ledger is not None else SpendLedger()

    def _pause(self, delay: float, response=None) -> None:
        """Sleep before a retry: the server's Retry-After if it sent one, else the current delay, plus jitter."""
        wait = delay
        if response is not None:
            hint = response.headers.get("Retry-After")
            if hint:
                wait = float(hint)
        time.sleep(wait + random.uniform(0, 0.25))

    def _price(self, body: dict, events: list[dict], final: dict) -> float:
        response = final.get("response") or {}
        if _is_video(body):
            base = video_cost(_frames_answered(events))
        else:
            base = call_cost(body["model"], response.get("usage") or {})
        return base + SEARCH_USD * len(search_calls([final]))

    def _post_retrying(self, url: str, model: str, reserve: float, retryable: set[int], **kwargs):
        """POST until a 200; retryable statuses are retried while attempts last, anything else
        gives the reservation back and raises."""
        delay = 0.75
        for attempt in range(self.attempts):
            r = requests.post(url, timeout=self.timeout, **kwargs)
            if r.status_code == 200:
                return r
            if r.status_code in retryable and attempt + 1 < self.attempts:
                self._pause(delay, r)
                delay *= 2
                continue
            self.ledger.settle(-reserve, f"release {model} HTTP {r.status_code}")
            raise MetaAPIError(f"HTTP {r.status_code}: {r.text[:500]}")
        raise MetaAPIError("retries exhausted")

    def events(self, body: dict) -> list[dict]:
        model = body["model"]
        reserve = worst_case(body)
        self.ledger.reserve(reserve, f"reserve {model}")
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json",
                   "Accept": "text/event-stream"}
        delay = 0.75
        for attempt in range(self.attempts):
            can_retry = attempt + 1 < self.attempts
            r = requests.post(API_URL, json=body, stream=True, timeout=self.timeout, headers=headers)
            if r.status_code == 200:
                events = list(parse_sse(r.iter_lines()))
                final = next((e for e in reversed(events) if e.get("type") in FINAL_EVENTS), None)
                if final is not None:
                    self.ledger.settle(self._price(body, events, final) - reserve, f"settle {model}")
                    return events
                # Cut off: the reservation stays, the model may have run and be billed.
                crashed = any(e.get("type") == "error" and e.get("code") == "server_error" for e in events)
                if not (crashed and can_retry):
                    return events
                self._pause(delay)
                delay *= 2
                self.ledger.reserve(reserve, f"reserve {model} again")
                continue
            if r.status_code in RETRY_STATUS and can_retry:
                self._pause(delay, r)
                delay *= 2
                continue
            self.ledger.settle(-reserve, f"release {model} HTTP {r.status_code}")
            raise MetaAPIError(f"HTTP {r.status_code}: {r.text[:500]}")
        raise MetaAPIError("retries exhausted")

    def asr(self, request: dict, audio: bytes) -> dict:
        model = request["model"]
        reserve = asr_cost(len(audio) // 16)  # milliseconds; twice the worst case for 16-bit mono 16 kHz
        self.ledger.reserve(reserve, f"reserve {model}")
        r = self._post_retrying(
            ASR_URL, model, reserve, RETRY_STATUS - {503},
            headers={"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"},
            files={"request": (None, json.dumps(request), "application/json"),
                   "audio": ("note.wav", audio, "audio/wav")})
        answer = r.json()
        self.ledger.settle(asr_cost(answer.get("audioDurationMs")) - reserve, f"settle {model}")
        return answer


    def image(self, request: dict) -> dict:
        model = request["model"]
        reserve = flat_cost(model)  # the flat price is the price: nothing to settle afterwards
        self.ledger.reserve(reserve, f"reserve {model}")
        r = self._post_retrying(
            IMAGE_URL, model, reserve, RETRY_STATUS,
            json=request,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"})
        return r.json()


class ReplayTransport:
    def __init__(self, directory: Path = RECORDINGS):
        self.directory = directory

    def _read(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise ReplayMissing(f"no recording {path.name}; run once with BILLRADAR_LIVE=1 to record it") from None

    def path(self, body: dict) -> Path:
        return self.directory / recording_name(body)

    def events(self, body: dict) -> list[dict]:
        text = self._read(self.path(body))
        return [json.loads(line) for line in text.split("\n") if line.strip()]

    def asr_path(self, request: dict, audio: bytes) -> Path:
        return self.directory / f"{request['model']}-{asr_key(request, audio)}.json"

    def asr(self, request: dict, audio: bytes) -> dict:
        return json.loads(self._read(self.asr_path(request, audio)))


    def image_path(self, request: dict) -> Path:
        return self.directory / f"{request['model']}-{request_key(request)}.json"

    def image(self, request: dict) -> dict:
        return json.loads(self._read(self.image_path(request)))


class MetaClient:
    provider = "meta"

    def __init__(self, transport=None, record_to: Path | None = RECORDINGS, journal: Path | None = JOURNAL):
        self.transport = transport if transport is not None else self._default_transport()
        self.record_to = record_to
        self.journal = journal
        self.calls: list[dict] = []

    @staticmethod
    def _stamped(**fields) -> dict:
        """A journal row: the UTC time first, then the fields in the order given."""
        return {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **fields}

    @staticmethod
    def _timed(call, *args):
        """(result of call(*args), wall seconds rounded to 2 places)."""
        started = time.monotonic()
        result = call(*args)
        return result, round(time.monotonic() - started, 2)

    def _record(self, name: str, render) -> None:
        """Save a live answer as record_to/name. render() builds the file text, so a replay never pays for it."""
        if not (self.live and self.record_to):
            return
        self.record_to.mkdir(parents=True, exist_ok=True)
        scratch = self.record_to / f".{name}.{os.getpid()}.tmp"
        scratch.write_text(render(), encoding="utf-8")
        scratch.replace(self.record_to / name)

    def _conclude(self, body: dict, label: str, events: list[dict], seconds: float) -> Result:
        """Parse a finished stream (an error leaves only the "sent" row), journal it, wrap it."""
        text, usage, response_id = collect(events)
        self._log(body, label, usage, seconds, response_id, len(search_calls(events)))
        return Result(text, events, usage, response_id, not self.live, seconds)

    @staticmethod
    def _default_transport():
        key = os.environ.get("MODEL_API_KEY", "")
        if key and os.environ.get("BILLRADAR_LIVE") == "1":
            return LiveTransport(key)
        return ReplayTransport()

    @property
    def live(self) -> bool:
        return isinstance(self.transport, LiveTransport) or bool(getattr(self.transport, "live", False))

    def respond(self, body: dict, label: str = "") -> Result:
        check_body(body)  # a refused body leaves no trace anywhere
        counts = _count_media(body)
        self._going_out(label, body["model"], request_key(body), images=counts[0], files=counts[1])
        events, seconds = self._timed(self.transport.events, body)
        # Saved before parsing, so a cut-off or failed stream is on disk too.
        self._record(recording_name(body), lambda: "".join(json.dumps(kept(ev)) + "\n" for ev in events))
        return self._conclude(body, label, events, seconds)

    def transcribe(self, request: dict, audio: bytes, label: str = "") -> tuple[dict, bool]:
        check_asr(request, audio)
        model = request["model"]
        key = asr_key(request, audio)
        self._going_out(label, model, key, audio_bytes=len(audio))
        answer, seconds = self._timed(self.transport.asr, request, audio)
        self._record(f"{model}-{key}.json", lambda: json.dumps(answer))
        millis = answer.get("audioDurationMs")
        self._write(self._stamped(label=label, model=model, key=key, live=self.live, audio_bytes=len(audio),
                                  audio_ms=millis, seconds=seconds, usd=round(asr_cost(millis), 6)))
        return answer, not self.live

    def image(self, request: dict, label: str = "") -> tuple[bytes, bool]:
        model = request.get("model")
        if model not in IMAGE_MODELS:
            raise MetaAPIError(f"model {model!r} is not an image model ({sorted(IMAGE_MODELS)})")
        if (request.get("n"), request.get("response_format")) != (1, "b64_json"):
            raise MetaAPIError("one image at a time, returned as b64_json")
        key = request_key(request)
        self._going_out(label, model, key)
        answer, seconds = self._timed(self.transport.image, request)
        self._record(f"{model}-{key}.json", lambda: json.dumps(answer))
        self._write(self._stamped(label=label, model=model, key=key, live=self.live,
                                  seconds=seconds, usd=flat_cost(model)))
        # Decoded only now: a malformed answer fails after it was saved.
        return base64.b64decode(answer["data"][0]["b64_json"]), not self.live

    def _log(self, body: dict, label: str, usage: dict, seconds: float, response_id: str = "", searches: int = 0) -> None:
        model = body["model"]
        pics, docs, chars = _count_media(body)
        price = round(call_cost(model, usage) + SEARCH_USD * searches, 6)  # replays are priced too; "live" tells them apart
        self._write(self._stamped(
            event="answered", status="completed", label=label, model=model, key=request_key(body),
            live=self.live, response_id=response_id, images=pics, files=docs, payload_chars=chars,
            seconds=seconds, usage=usage, searches=searches, usd=price))

    def _going_out(self, label: str, model: str, key: str, **counts) -> None:
        """One line the moment a live request leaves, before any answer: names and counts only, never its content.
        The call's own line comes after it, with the same key. Nothing is written on a replay: nothing left."""
        if self.live and self.journal:
            self.journal.parent.mkdir(parents=True, exist_ok=True)
            with self.journal.open("a") as f:
                f.write(json.dumps({"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "event": "sent",
                                    "live": True, "label": label, "model": model, "key": key, **counts}) + "\n")

    def _write(self, entry: dict) -> None:
        self.calls.append(entry)  # the very dict, kept before anything touches the disk
        if not self.journal:
            return
        self.journal.parent.mkdir(parents=True, exist_ok=True)
        # One O_APPEND write per row, so parallel runs never interleave inside a line.
        fd = os.open(self.journal, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o666)
        try:
            os.write(fd, (json.dumps(entry) + "\n").encode("utf-8"))
        finally:
            os.close(fd)
