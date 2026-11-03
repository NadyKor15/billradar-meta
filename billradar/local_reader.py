"""Muse Glimmer on this computer: it reads the sheets before anything leaves.

Muse Glimmer is one of Meta's open-weight models. It runs here through llama.cpp, so the family's papers are read on the
family's own computer. Its first job is to read every printed piece of a sheet; what may leave is decided from that
reading by rules (open_lines). Its second job is to read the covered sheet back as a whole, as a check.

The weights are about 20 GB and need about 32 GB of free memory: see the README. Without them the private path stops with
`NotAvailable` and nothing is sent. The sample piles do not need them: what the model answered on them is kept in
tests/fixtures/recordings/glimmer, by what was asked and what the image shows.
"""

from __future__ import annotations

import atexit
import base64
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

from PIL import Image

from billradar import sheet_pieces

WEIGHTS = "Muse-Glimmer-30B-KQuant-17GB-Q4_K_M.gguf"
VISION = "mmproj-Muse-Glimmer-30B-Q4_K_M.gguf"
DRAFT = "dflash-Muse-Glimmer-30B-Q4_K_M.gguf"
FONT = str(Path(__file__).parent / "fonts" / "NotoSans-Bold.ttf")
RECORDINGS = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "recordings" / "glimmer"
RECORD_TO = "BILLRADAR_GLIMMER_RECORD"  # a folder: answers are written there too
START_SECONDS = 300
ANSWER_SECONDS = 900
JPEG_QUALITY = 92
LIST = ("This image is a numbered list. Each row has a red number on the left and a small piece cut from a printed document on the right. "
        "Copy the printed text of each row exactly as printed, every number, code and punctuation mark. Do not complete cut words and do not guess. "
        "If a row shows no text, leave it empty. Output only one line per row: <number>|<text>")
WHOLE = ("Transcribe every line of printed text on this image, from top to bottom, exactly as printed, including every number, "
         "code and punctuation mark, and any text printed sideways along the edges. Do not skip table rows. Output only the text, "
         "one printed line per output line.")
WHOLE_AGAIN = WHOLE + " Take it line by line and do not repeat a line."
TURN = ("Look at the printed text on this page. Which way must the page be turned clockwise so the text reads upright? "
        "Answer with one number only: 0, 90, 180 or 270.")
ROW = re.compile(r"\s*(\d+)\s*\|(.*)$")
WORD_OR_NUMBER = re.compile(r"[A-Za-z0-9]")
AGAIN_ROW_H = 60
AGAIN_PER_LIST = 14


class NotAvailable(RuntimeError):
    """The local model cannot run here. Nothing goes out without it."""


def _dir() -> Path:
    return Path(os.environ.get("BILLRADAR_GLIMMER_DIR") or Path.home() / "Models" / "Muse-Glimmer-30B-GGUF")


def _exe() -> str | None:
    return os.environ.get("BILLRADAR_LLAMA_SERVER") or shutil.which("llama-server")


def available() -> bool:
    return bool(_exe()) and all((_dir() / f).is_file() for f in (WEIGHTS, VISION, DRAFT))


class _Server:
    """One llama-server per process, started on first use and stopped at exit."""

    def __init__(self):
        self.proc: subprocess.Popen | None = None
        self.port = int(os.environ.get("BILLRADAR_GLIMMER_PORT", "8093"))
        self.lock = threading.Lock()

    def url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}{path}"

    def _healthy(self) -> bool:
        try:
            with urllib.request.urlopen(self.url("/health"), timeout=5) as r:
                return r.status == 200
        except OSError:
            return False

    def start(self) -> None:
        if self.proc is not None and self.proc.poll() is None:
            return
        if not available():
            raise NotAvailable(f"Muse Glimmer is not set up: weights in {_dir()} and llama-server are needed")
        folder = _dir()
        self.proc = subprocess.Popen(
            [_exe(), "-m", str(folder / WEIGHTS), "--mmproj", str(folder / VISION), "-md", str(folder / DRAFT), "--spec-type", "draft-dflash",
             "--spec-draft-n-max", "4", "--host", "127.0.0.1", "--port", str(self.port), "-ngl", "99", "--ctx-size", "16384",
             "--reasoning-effort", "low", "--jinja"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        atexit.register(self.stop)
        deadline = time.monotonic() + START_SECONDS
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                raise NotAvailable("Muse Glimmer stopped while loading; it needs about 32 GB of free memory")
            if self._healthy():
                return
            time.sleep(2)
        self.stop()
        raise NotAvailable("Muse Glimmer did not start in time")

    def stop(self) -> None:
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()
            self.proc.wait(timeout=30)
        self.proc = None

    def ask(self, prompt: str, jpeg: bytes) -> str:
        with self.lock:  # one model, one sheet at a time
            self.start()
            body = {"messages": [{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()}}]}],
                "temperature": 1.0, "top_p": .95, "top_k": 64, "max_tokens": 7000}
            req = urllib.request.Request(self.url("/v1/chat/completions"), data=json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=ANSWER_SECONDS) as r:
                    return json.load(r)["choices"][0]["message"].get("content") or ""
            except (OSError, ValueError, KeyError, IndexError) as exc:
                raise NotAvailable(f"Muse Glimmer did not answer: {type(exc).__name__}") from exc


_server = _Server()


def recording_name(prompt: str, img: Image.Image) -> str:
    rgb = img.convert("RGB")
    return hashlib.sha256(prompt.encode() + repr(rgb.size).encode() + rgb.tobytes()).hexdigest()[:24] + ".txt"


def _ask(prompt: str, img: Image.Image) -> str:
    """The one place that talks to the model. The same picture and the same question have one answer."""
    name = recording_name(prompt, img)
    stored = RECORDINGS / name
    if stored.is_file():
        return stored.read_text()
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=JPEG_QUALITY)
    answer = _server.ask(prompt, buf.getvalue())
    if folder := os.environ.get(RECORD_TO):
        (Path(folder) / name).write_text(answer)
    return answer


def parse_rows(text: str) -> dict[int, str]:
    rows: dict[int, str] = {}
    for line in text.splitlines():
        if m := ROW.match(line):
            rows[int(m.group(1))] = m.group(2).strip()
    return rows


def read_pieces(img: Image.Image) -> tuple[list[tuple[str, tuple]], int]:
    """Every printed piece of the sheet with its text: [(text, box), ...] and the sheet's type height. A piece the model left
    empty comes back empty and stays closed."""
    boxes, h = sheet_pieces.pieces(img)
    rows: dict[int, str] = {}
    for page in sheet_pieces.lists(img, boxes, FONT):
        rows |= parse_rows(_ask(LIST, page))
    empty = {k: boxes[k] for k in boxes if not WORD_OR_NUMBER.search(rows.get(k, ""))}
    if empty:  # an empty piece is an unread piece: once more, larger and fewer to a page
        for page in sheet_pieces.lists(img, empty, FONT, row_h=AGAIN_ROW_H, per=AGAIN_PER_LIST):
            rows |= {k: v for k, v in parse_rows(_ask(LIST, page)).items() if WORD_OR_NUMBER.search(v)}
    return [(rows.get(k, ""), tuple(int(x) for x in boxes[k])) for k in sorted(boxes)], h


def transcribe(img: Image.Image, again: bool = False) -> str:
    """The whole image read as one: what can be read on it, with no help from the boxes."""
    return _ask(WHOLE_AGAIN if again else WHOLE, img)


def turn_of(img: Image.Image) -> int:
    """Clockwise turn that makes the page upright. 0 when the answer is not one of the four."""
    small = img.convert("RGB").copy()
    small.thumbnail((1000, 1000), Image.Resampling.LANCZOS)
    m = re.search(r"\b(0|90|180|270)\b", _ask(TURN, small))
    return int(m.group(1)) if m else 0
