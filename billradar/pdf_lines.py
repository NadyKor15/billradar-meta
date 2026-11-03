"""The lines of a PDF with their places, from the file's text layer. No model is needed: the text is already exact."""

from __future__ import annotations

import html
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from billradar.open_lines import Tag

WORD = re.compile(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>')


def has_text(pages: list[list[Tag]]) -> bool:
    return any(t.text.strip() for page in pages for t in page)


def lines_of(pdf: bytes, dpi: int) -> list[list[Tag]]:
    """Page -> lines, in the pixels of the page drawn at this dpi. A wide gap on a line splits it into cells, as on a photo."""
    exe = shutil.which("pdftotext")
    if not exe:
        return []
    with tempfile.TemporaryDirectory(prefix="billradar-pdf-") as tmp:
        src, out = Path(tmp) / "in.pdf", Path(tmp) / "out.html"
        src.write_bytes(pdf)
        try:
            subprocess.run([exe, "-bbox-layout", str(src), str(out)], check=True, capture_output=True, timeout=120)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return []  # no text layer to use: the page is read like a photo
        doc = out.read_text(encoding="utf-8", errors="replace")
    scale = dpi / 72
    pages = []
    for page in re.findall(r"<page\b.*?</page>", doc, re.S):
        tags: list[Tag] = []
        for line in re.findall(r"<line\b.*?</line>", page, re.S):
            cell: list = []
            for w in [(float(a), float(b), float(c), float(d), html.unescape(t)) for a, b, c, d, t in WORD.findall(line)] + [None]:
                if cell and (w is None or w[0] - cell[-1][2] > 1.6 * (cell[-1][3] - cell[-1][1])):
                    box = tuple(int(x * scale) for x in (cell[0][0], min(c[1] for c in cell), cell[-1][2], max(c[3] for c in cell)))
                    tags.append(Tag(len(tags) + 1, " ".join(c[4] for c in cell), box))
                    cell = []
                if w is not None:
                    cell.append(w)
        pages.append(tags)
    return pages
