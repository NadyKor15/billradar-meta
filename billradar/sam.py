"""Find the sheets of paper in one photo of a table.

SAM 3.1 gets a shrunken copy of the photo and is asked for every "sheet of paper". Its boxes and masks are mapped back to
original pixels, thinned out by plain geometry (too small, wrong shape, duplicates), numbered in reading order, and each
sheet is straightened from the full-size original using the corners of its mask. The model finds the sheets; the code
does the geometry. The original photo never leaves the machine, only the small copy does.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field

import cv2
import numpy as np
from meta_sam_parser import (
    CompletedOutcome,
    SegmentationBoxRecord,
    SegmentationMaskRecord,
    decode_mask_to_raster,
    image_segmentation_format,
)
from PIL import Image, ImageOps

from billradar.meta_client import MetaClient, data_url

PHRASE = "sheet of paper"
SAM_MAX_SIDE = 1600  # the copy sent to SAM; sheets are cut from the original
MIN_AREA_FRACTION = 0.012
ASPECT_RANGE = (0.33, 3.0)
NMS_IOU = 0.5
SHEET_COLORS = [(232, 106, 90), (214, 164, 72), (52, 160, 150), (139, 104, 196), (74, 136, 214), (232, 110, 150)]


@dataclass
class Detection:
    object_id: str
    box: tuple[float, float, float, float]  # left, top, right, bottom in ORIGINAL pixels, half-open
    confidence: float | None
    mask: np.ndarray | None = None  # uint8 0/1, size of the box in original pixels

    @property
    def area(self) -> float:
        left, top, right, bottom = self.box
        return float(max(0, right - left)) * float(max(0, bottom - top))


@dataclass
class Sheet:
    doc_id: str  # S1, S2 ... in reading order; the number painted on screen
    box: tuple[int, int, int, int]
    confidence: float | None
    corners: list[tuple[int, int]] | None  # 4 corners in original pixels when the mask gave them
    image: Image.Image  # straightened (or box-cropped) sheet from the full-size original
    straightened: bool


@dataclass
class SheetsResult:
    sheets: list[Sheet]
    dropped: list[str] = field(default_factory=list)  # why each detection was not kept
    phrase: str = PHRASE
    sent_size: tuple[int, int] = (0, 0)
    original_size: tuple[int, int] = (0, 0)
    seconds: float = 0.0
    replayed: bool = True


def load_photo(raw: bytes) -> Image.Image:
    # Phones store rotation in EXIF; every pixel measure must come after it is applied.
    return ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert("RGB")


def to_jpeg(img: Image.Image, max_side: int | None = None, quality: int = 88) -> bytes:
    if max_side and max(img.size) > max_side:
        img = img.copy()  # thumbnail works in place
        img.thumbnail((max_side, max_side), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def request_body(jpeg: bytes, phrase: str = PHRASE) -> dict:
    return {
        "model": "sam-3.1",
        "input": [{
            "type": "message",
            "role": "user",
            "content": [
                {"type": "input_text", "text": phrase},
                {"type": "input_image", "image_url": data_url(jpeg, "image/jpeg")},
            ],
        }],
        "stream": True,
        "metadata": {"mask_encoding": "one_bit", "include_confidence": "true"},
    }


def parse(text: str, scale: tuple[float, float] = (1.0, 1.0)) -> tuple[list[Detection], list[str]]:
    sx, sy = scale
    parser = image_segmentation_format().create_parser()
    if text:
        parser.push(text)
    result = parser.finish(CompletedOutcome()).result

    # One table per kind of record, keyed by object id: a dict keeps the place of an id's first record
    # and the value of its last.
    by_kind: dict[type, dict[str, object]] = {SegmentationBoxRecord: {}, SegmentationMaskRecord: {}}
    for rec in result.records:
        for kind, table in by_kind.items():
            if isinstance(rec, kind):
                table[rec.object_id] = rec

    # Pass 1: the boxes alone, in the original's pixels.
    found = [Detection(oid, (rec.left * sx, rec.top * sy, rec.right * sx, rec.bottom * sy), rec.confidence)
             for oid, rec in by_kind[SegmentationBoxRecord].items()]

    # Pass 2: masks onto the boxes; a bad one leaves its box and a note behind.
    failures = []
    for det in found:
        rec = by_kind[SegmentationMaskRecord].get(det.object_id)
        if rec is None:
            continue
        try:
            raster = np.frombuffer(decode_mask_to_raster(rec.mask), dtype=np.uint8).reshape(rec.mask.height, rec.mask.width)
            size = (max(1, round(det.box[2] - det.box[0])), max(1, round(det.box[3] - det.box[1])))
            det.mask = cv2.resize(raster, size, interpolation=cv2.INTER_NEAREST)
        except Exception as exc:  # noqa: BLE001 - a bad mask still leaves a usable box
            det.mask = None
            failures.append(f"mask {det.object_id} not decoded: {exc}")

    diagnostics = [f"{d.severity}: {d.code} {d.message}" for d in result.diagnostics]
    return found, diagnostics + failures


def _iou(a, b) -> float:
    inter = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union != 0 else 0.0


def clean(dets: list[Detection], size: tuple[int, int]) -> tuple[list[Detection], list[str]]:
    width, height = size
    photo_area = width * height
    kept: list[Detection] = []
    reasons: list[str] = []
    # Most confident first, then biggest; sorted() is stable, so full ties keep input order.
    for d in sorted(dets, key=lambda d: (-(d.confidence or 0), -d.area)):
        w = d.box[2] - d.box[0]
        h = d.box[3] - d.box[1]
        ratio = h / w if w else 0.0
        if d.area < MIN_AREA_FRACTION * photo_area:
            reasons.append(f"object {d.object_id}: too small ({d.area / photo_area:.1%} of photo)")
        elif not ASPECT_RANGE[0] <= ratio <= ASPECT_RANGE[1]:
            reasons.append(f"object {d.object_id}: not sheet-shaped (h/w {ratio:.2f})")
        elif any(_iou(d.box, k.box) > NMS_IOU for k in kept):
            reasons.append(f"object {d.object_id}: duplicate of a kept sheet")
        else:
            kept.append(d)
    return kept, reasons


def reading_order(dets: list[Detection]) -> list[Detection]:
    if not dets:
        return []
    centres = [(d.box[1] + d.box[3]) / 2 for d in dets]
    heights = sorted(d.box[3] - d.box[1] for d in dets)
    tolerance = heights[len(heights) // 2] / 2

    # Pass 1: give every detection a row number, walking down the page. Only the last row is ever joined.
    top_down = sorted(range(len(dets)), key=centres.__getitem__)
    row_of: dict[int, int] = {}
    totals: list[float] = []
    counts: list[int] = []
    for i in top_down:
        if counts and abs(centres[i] - totals[-1] / counts[-1]) <= tolerance:
            totals[-1] += centres[i]
            counts[-1] += 1
        else:
            totals.append(centres[i])
            counts.append(1)
        row_of[i] = len(counts) - 1

    # Pass 2: one stable sort by (row, left); ties keep the order of entry into the row.
    return [dets[i] for i in sorted(top_down, key=lambda i: (row_of[i], dets[i].box[0]))]


def _order_corners(pts: np.ndarray) -> np.ndarray:
    total = pts.sum(axis=1)
    diff = pts[:, 1] - pts[:, 0]  # y - x
    return np.array([pts[total.argmin()], pts[diff.argmin()], pts[total.argmax()], pts[diff.argmax()]], dtype=np.float32)


def corners_from_mask(det: Detection) -> np.ndarray | None:
    mask = det.mask
    if mask is None or not mask.any():
        return None
    contours, _ = cv2.findContours(np.asarray(mask, dtype=np.uint8) * np.uint8(255), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    biggest = max(contours, key=cv2.contourArea)
    if cv2.contourArea(biggest) < 0.25 * mask.size:  # under a quarter of the box: the mask is not to be trusted
        return None
    approx = cv2.approxPolyDP(biggest, 0.02 * cv2.arcLength(biggest, True), True)
    if len(approx) == 4:
        pts = approx.reshape(4, 2)
    else:
        pts = cv2.boxPoints(cv2.minAreaRect(biggest))
    return _order_corners(pts.astype(np.float32) + np.array([det.box[0], det.box[1]], dtype=np.float32))


def straighten(original: np.ndarray, corners: np.ndarray) -> np.ndarray:
    tl, tr, br, bl = corners
    width = int(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl)))
    height = int(max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr)))
    target = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(corners, target)
    return cv2.warpPerspective(original, matrix, (width, height))


def find_sheets(client: MetaClient, photo: bytes, phrase: str = PHRASE, max_side: int = SAM_MAX_SIDE,
                send: Image.Image | None = None, crop_from: Image.Image | None = None) -> SheetsResult:
    original = crop_from if crop_from is not None else load_photo(photo)
    jpeg, sent_size, scale = _outgoing_copy(original, send, max_side)

    reply = client.respond(request_body(jpeg, phrase), label=f"sam:{phrase}")
    found, notes = parse(reply.text, scale)
    kept, reasons = clean(found, original.size)
    sheets = _cut_sheets(reading_order(kept), original)
    return SheetsResult(sheets, reasons + notes, phrase, sent_size, original.size, reply.seconds, reply.replayed)


def _outgoing_copy(original: Image.Image, send: Image.Image | None, max_side: int):
    """The JPEG that leaves the machine, its size as measured on those bytes, and the per-axis factor back to the original."""
    jpeg = to_jpeg(original, max_side) if send is None else to_jpeg(send)
    with Image.open(io.BytesIO(jpeg)) as sent:
        width, height = sent.size
    return jpeg, (width, height), (original.width / width, original.height / height)


def _cut_sheets(ordered: list[Detection], original: Image.Image) -> list[Sheet]:
    """One Sheet per detection, numbered from 1: straightened when the mask gave corners, else a plain crop."""
    pixels = np.asarray(original)
    sheets = []
    for number, det in enumerate(ordered, start=1):
        box = tuple(int(v) for v in det.box)
        corners = corners_from_mask(det)
        if corners is None:
            sheets.append(Sheet(f"S{number}", box, det.confidence, None, original.crop(box), False))
        else:
            flat = Image.fromarray(straighten(pixels, corners))
            sheets.append(Sheet(f"S{number}", box, det.confidence, [(int(x), int(y)) for x, y in corners], flat, True))
    return sheets


def overlay(photo: bytes, result: SheetsResult, max_side: int = 1400) -> Image.Image:
    img = load_photo(photo)
    w, h = img.size
    k = min(1.0, max_side / max(w, h))
    canvas = np.array(img)  # a writable copy
    if k < 1.0:
        canvas = cv2.resize(canvas, (int(w * k), int(h * k)))

    thickness = max(2, int(6 * k))
    radius = max(14, int(34 * k))
    for n, sheet in enumerate(result.sheets):
        color = SHEET_COLORS[n % len(SHEET_COLORS)]
        if sheet.corners is not None and len(sheet.corners):
            outline = np.asarray(sheet.corners, dtype=np.float64)
        else:
            left, top, right, bottom = sheet.box
            outline = np.array([[left, top], [right, top], [right, bottom], [left, bottom]], dtype=np.float64)
        outline = (outline * k).astype(np.int32)
        cv2.polylines(canvas, [outline.reshape(-1, 1, 2)], True, color, thickness, cv2.LINE_AA)

        x, y = int(outline[0][0]), int(outline[0][1])
        cv2.circle(canvas, (x, y), radius, color, -1, cv2.LINE_AA)
        label = sheet.doc_id[1:]  # S12 -> 12
        font_scale = radius / 22
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_DUPLEX, font_scale, 2)
        cv2.putText(canvas, label, (int(x - tw / 2), int(y + th / 2)), cv2.FONT_HERSHEY_DUPLEX, font_scale,
                    (255, 255, 255), 2, cv2.LINE_AA)
    return Image.fromarray(canvas)
