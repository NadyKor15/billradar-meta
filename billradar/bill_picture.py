"""The bill in one picture, for a parent who does not read English.

Muse Image draws the case as a wordless scene: the pile of letters, the problem found, the money coming back. The
words and numbers on the picture are written here, in the family's language, from the checked report: a generated
image can misspell a figure, so no figure is ever asked of the model. The prompt names no person, no amount, no date.
"""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from PIL.PngImagePlugin import PngInfo

from billradar import days
from billradar.case import Case
from billradar.checks import Kind, Report
from billradar.meta_client import MetaClient
from billradar.pipeline import RealDataGate

MODEL = "muse-image-1.0"
FONTS = Path(__file__).parent / "fonts"
PNG_START = b"\x89PNG\r\n\x1a\n"
LABEL_CHUNKS = (b"iTXt", b"tEXt", b"zTXt", b"caBX")
TEAL, CREAM, GOLD = (14, 94, 94), (251, 247, 236), (201, 150, 40)
ERRORS = {Kind.E1, Kind.E2, Kind.E3, Kind.E4, Kind.N1}
HELP = {Kind.F1, Kind.F3}
MONTHS = {"ru": "января февраля марта апреля мая июня июля августа сентября октября ноября декабря".split(),
          "es": "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split()}
WORDS = {"en": ("May come off your bills: {}", "Last day to apply: {}", "Letters are ready. You read and sign them."),
         "ru": ("Может быть снято со счетов: {}", "Последний день подачи: {}", "Письма готовы. Вы читаете и подписываете сами."),
         "es": ("Se puede quitar de sus cuentas: {}", "Último día para solicitar: {}", "Las cartas están listas. Usted las lee y firma.")}


def _middle(kinds: set[Kind]) -> str:
    parts = []
    if kinds & ERRORS:
        parts.append("a magnifying glass over a sheet of paper where one row glows gold")
    if kinds & HELP:
        parts.append("a hospital building with a heart-shaped shield over its door, an open hand offering a folder")
    if Kind.B1 in kinds:
        parts.append("a small crib next to a paper with a loose link of chain")
    return "; ".join(parts) or "a magnifying glass moving calmly over a tidy sheet of paper"


def prompt(case: Case, report: Report) -> str:
    kinds = {f.kind for f in report.findings}
    return ("A warm, simple illustration in three panels side by side, on a cream background, in soft teal, cream and "
            "gold, flat and friendly, for a family after a hospital stay. "
            "Left panel: a tall pile of envelopes and letters on a kitchen table. "
            f"Middle panel: {_middle(kinds)}. "
            "Right panel: gold coins flowing back into a small house with a warm light in the window. "
            "No text, no numbers, no letters on the papers, no logos, no faces, no people.")


def _day(d, lang: str) -> str:
    if lang in MONTHS:
        month = MONTHS[lang][d.month - 1]
        return f"{d.day} {month} {d.year}" if lang == "ru" else f"{d.day} de {month} de {d.year}"
    return f"{d:%b} {d.day}, {d.year}"


CHECK = {"en": days.CHECK_DATE, "ru": "уточните в больнице", "es": "confírmelo con el hospital"}


def labels(case: Case, report: Report, lang: str = "en") -> list[str]:
    money, apply_by, letters = WORDS.get(lang, WORDS["en"])
    out = [money.format(f"${int(report.total_may_come_off):,}")]
    if report.apply_by and not days.passed(report.apply_by, case.today):
        out.append(apply_by.format(_day(report.apply_by, lang)) + ("" if report.apply_by_sure else f", {CHECK[lang if lang in CHECK else 'en']}"))
    out.append(letters)
    return out


def _provenance(raw: bytes) -> PngInfo:
    """Meta's labels on the picture (its XMP says the image is AI made) go on the picture we build from it."""
    info = PngInfo()
    i = len(PNG_START) if raw.startswith(PNG_START) else len(raw)
    while i < len(raw):
        size, kind = int.from_bytes(raw[i:i + 4], "big"), raw[i + 4:i + 8]
        if kind in LABEL_CHUNKS:
            info.add(kind, raw[i + 8:i + 8 + size])
        i += size + 12
    return info


def _with_labels(raw: bytes, lines: list[str]) -> bytes:
    scene = Image.open(io.BytesIO(raw)).convert("RGB")
    big = ImageFont.truetype(str(FONTS / "NotoSans-Bold.ttf"), max(34, scene.width // 34))
    small = ImageFont.truetype(str(FONTS / "NotoSans-Regular.ttf"), max(26, scene.width // 48))
    gap = big.size // 2
    band = gap * 3 + big.size * 3 // 2 + (len(lines) - 1) * (small.size * 3 // 2)
    out = Image.new("RGB", (scene.width, scene.height + band), CREAM)
    out.paste(scene, (0, 0))
    draw = ImageDraw.Draw(out)
    y = scene.height + gap
    for i, line in enumerate(lines):
        font = big if i == 0 else small
        draw.text((gap * 2, y), line, font=font, fill=TEAL if i == 0 else (40, 50, 54))
        y += font.size * 3 // 2
    draw.rectangle((0, scene.height, scene.width, scene.height + 6), fill=GOLD)
    buf = io.BytesIO()
    out.save(buf, format="PNG", pnginfo=_provenance(raw))
    return buf.getvalue()


def request(case: Case, report: Report) -> dict:
    return {"model": MODEL, "prompt": prompt(case, report), "n": 1, "size": "1536x1024", "output_format": "png",
            "response_format": "b64_json"}


def render(client: MetaClient, case: Case, report: Report, lang: str = "en") -> bytes:
    if client.live and not case.demo:
        raise RealDataGate("the picture is drawn live only for a fictional case")
    raw, _ = client.image(request(case, report), label="image:bill")
    return _with_labels(raw, labels(case, report, lang))

