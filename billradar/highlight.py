"""A finding shown on its paper: the line that holds the sum, marked on the sheet as photographed.

It starts from a real finding and nowhere else. The finding's trace names the sheet, the line and the printed value; this
device finds that row on the sheet and the value in it. A row the device cannot find, or a sum not printed in it, gets no
mark: a mark in the wrong place would say more than the finding does.

SAM 3.1 gets a box around the row on the covered sheet, the one that already went out, and its mask has to agree that
the row is there. The band on the sheet is the row itself, not the mask: a mask follows the ink, so on a real sheet it can
stop halfway along the line, before the sum. `by` says who stands behind a mark.
"""

from __future__ import annotations

import io
import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np
from meta_sam_parser import FramePrompt, PromptBox, PromptObject, build_object_prompt
from PIL import Image, ImageDraw

from billradar import redact, sam, table_rows
from billradar.case import Case, Document
from billradar.checks import Finding, Report
from billradar.meta_client import MetaAPIError, MetaClient, SpendCapReached, data_url

SHEET_ID = "S"  # a file's page has no photo to mark
PAD = 6  # pixels round the row
MIN_OVERLAP = 0.5  # of the row, inside the mask's box
MAX_GROWTH = 2.5  # a mask much larger than the row took the page with it
BAND = (250, 196, 60)
log = logging.getLogger(__name__)


@dataclass
class Mark:
    index: int  # the finding's place in findings + worth_asking
    kind: str
    doc_id: str
    line_no: int | None
    value: str
    box: tuple[int, int, int, int]  # the row, on the sheet
    outline: list[tuple[int, int]]  # the mask's outline, empty when SAM gave none we can trust
    by: str  # "SAM 3.1", or "this device" when only the row is known


PRINTED = "printed.json"  # what each sheet says, kept next to the sheets on this computer


def rows_with_boxes(lines: list) -> list[tuple[table_rows.Row, tuple[int, int, int, int]]]:
    """table_rows.rows(), each row with where it stands."""
    rows = table_rows.rows(lines)
    boxes = []
    for group in table_rows.groups(lines):
        pts = np.concatenate([x.box for x in group])
        (x0, y0), (x1, y1) = pts.min(axis=0), pts.max(axis=0)
        boxes.append((int(x0), int(y0), int(x1), int(y1)))
    return list(zip(rows, boxes))


def find_row(doc: Document, step, printed: list[tuple[table_rows.Row, tuple]]) -> tuple | None:
    """The row that prints the step's value: under the line's own code when it has one. The same reading of the page as
    the last word on a sum (table_rows.confirms), so what is marked is what confirmed it."""
    value = abs(step.printed)
    rows = [r for r, _ in printed]
    line = next((ln for ln in doc.lines if ln.line_no == step.line_no), None) if step.line_no is not None else None
    code = line.code.strip() if line is not None and line.code else ""
    starts = [i for i, r in enumerate(rows) if code in r.codes] if code else list(range(len(rows)))
    if code:
        same = [ln.line_no for ln in doc.lines if ln.code and ln.code.strip() == code]
        if len(same) == len(starts) and step.line_no in same:
            starts = [starts[same.index(step.line_no)]]
    for i in starts:
        for j in range(i, min(i + (6 if code else 1), len(rows))):
            if value in rows[j].amounts:
                return printed[j][1]
    return None


def request_body(jpeg: bytes, size: tuple[int, int], box: tuple[int, int, int, int]) -> dict:
    """Ask SAM 3.1 for the object inside one box of an already covered sheet."""
    ask = build_object_prompt(size=size, objects=[PromptObject(id=1, prompts=[FramePrompt(frame=0, box=PromptBox(*box))])])
    parts = [{"type": "input_text", "text": ask}, {"type": "input_image", "image_url": data_url(jpeg, "image/jpeg")}]
    return {"model": "sam-3.1", "input": [{"type": "message", "role": "user", "content": parts}], "stream": True,
            "metadata": {"mask_encoding": "one_bit", "include_confidence": "true"}}


def _outline(det: sam.Detection) -> list[tuple[int, int]]:
    if det.mask is None or not det.mask.any():
        return []
    contours, _ = cv2.findContours((det.mask * 255).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    c = max(contours, key=cv2.contourArea)
    pts = cv2.approxPolyDP(c, 1.5, True).reshape(-1, 2) + np.array([det.box[0], det.box[1]])
    return [(int(x), int(y)) for x, y in pts]


def _trusted(det: sam.Detection, row: tuple) -> bool:
    l, t, r, b = det.box
    x0, y0, x1, y1 = row
    area = max(1, (x1 - x0) * (y1 - y0))
    over = max(0.0, min(r, x1) - max(l, x0)) * max(0.0, min(b, y1) - max(t, y0))
    painted = float(det.mask.sum()) if det.mask is not None else det.area  # its box can span the rows next to it
    return over >= MIN_OVERLAP * area and painted <= MAX_GROWTH * area


def mark_for(client: MetaClient, index: int, f: Finding, doc: Document, sheet: Image.Image, sent: bytes,
             lines: list | None = None) -> Mark | None:
    """One finding on one sheet. `sheet` as photographed, `sent` the covered JPEG the models already have, `lines` what the
    sheet says when that is stored with the case: a saved sheet is not read again."""
    steps = [s for s in f.trace if s.doc_id == doc.doc_id]
    printed = rows_with_boxes(redact.ocr(sheet) if lines is None else lines)
    for step in steps:
        row = find_row(doc, step, printed)
        if row is None:
            continue
        size = Image.open(io.BytesIO(sent)).size
        k = (size[0] / sheet.width, size[1] / sheet.height)
        box = (max(0, int(row[0] * k[0]) - PAD), max(0, int(row[1] * k[1]) - PAD),
               min(size[0], int(row[2] * k[0]) + PAD), min(size[1], int(row[3] * k[1]) + PAD))
        res = client.respond(request_body(sent, size, box), label="sam:highlight")
        dets, _ = sam.parse(res.text, (1 / k[0], 1 / k[1]))
        det = next((d for d in dets if _trusted(d, row)), None)
        return Mark(index, f.kind.value, doc.doc_id, step.line_no, str(step.printed), row, _outline(det) if det else [],
                    "SAM 3.1" if det else "this device")
    return None


def marks(client: MetaClient, case: Case, report: Report, sheets: Path, sent: Path) -> list[Mark]:
    """Every finding with a sum on a sheet. Findings about a file, or with no sum, have no line to point at."""
    out = []
    stored = sheets / PRINTED
    printed = json.loads(stored.read_text()) if stored.exists() else {}
    for i, f in enumerate(report.findings + report.worth_asking):
        for doc_id in dict.fromkeys(s.doc_id for s in f.trace if s.doc_id.startswith(SHEET_ID)):
            photo, covered = sheets / f"{doc_id}.jpg", sent / f"{doc_id}.jpg"
            if not (photo.exists() and covered.exists()):
                continue
            lines = redact.lines_from(printed[doc_id]) if doc_id in printed else None
            m = mark_for(client, i, f, case.doc(doc_id), Image.open(photo).convert("RGB"), covered.read_bytes(), lines)
            if m is not None:
                out.append(m)
                break
    return out


def save(found: list[Mark], d: Path) -> None:
    (d / "highlights.json").write_text(json.dumps([asdict(m) for m in found], indent=2))


def load(d: Path) -> list[Mark]:
    p = d / "highlights.json"
    return [Mark(**{**x, "box": tuple(x["box"]), "outline": [tuple(q) for q in x["outline"]]}) for x in json.loads(p.read_text())] if p.exists() else []


def render(sheet: Image.Image, m: Mark) -> Image.Image:
    """The sheet with its line marked. The band runs the whole row and sits under the print, so the sum stays readable."""
    base = sheet.convert("RGB")
    layer = np.zeros((base.height, base.width, 1), dtype=np.float32)
    layer[max(0, m.box[1]):m.box[3], max(0, m.box[0]):m.box[2]] = 1.0
    gray = np.asarray(base.convert("L"), dtype=np.float32)
    a = layer * (gray[..., None] > 110)  # paper, not ink
    arr = np.asarray(base, dtype=np.float32)
    out = arr * (1 - 0.55 * a) + np.array(BAND, dtype=np.float32) * 0.55 * a
    img = Image.fromarray(out.clip(0, 255).astype(np.uint8))
    ImageDraw.Draw(img).rectangle((m.box[0] - 4, m.box[1] - 4, m.box[2] + 4, m.box[3] + 4), outline=(190, 120, 0), width=3)
    return img


def attach(client, run, d: Path) -> None:
    """Marks for a saved case, next to it. A mark is an extra: when it fails, the case stands without it."""
    try:
        found = marks(client, run.case, run.report, d / "sheets", d / "sent-sheets")
    except (MetaAPIError, SpendCapReached) as exc:
        log.warning("no marks for case %s: %s", d.name, exc)
        return
    if not found:
        return
    save(found, d)
    (d / "marked").mkdir(exist_ok=True)
    for m in found:
        render(Image.open(d / "sheets" / f"{m.doc_id}.jpg"), m).save(d / "marked" / f"{m.index}.jpg", quality=88)


__all__ = ["Mark", "marks", "mark_for", "find_row", "rows_with_boxes", "render", "save", "load", "attach"]
