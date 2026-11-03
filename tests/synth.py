"""A made-up table photo and the SAM answer for it. Nothing here comes from the real API."""

from __future__ import annotations

import base64
import io

import cv2
import numpy as np
from meta_sam_parser import SegmentationMask, decode_mask_to_raster
from meta_sam_parser._mask_codec import _encode_raster  # test-only
from PIL import Image

WOOD = (120, 84, 52)  # the table: reddish brown, so pale paper stands out from it
PAPER = (246, 244, 238)
INK = (70, 70, 70)
TEXT_ROWS = [0.12 + 0.09 * k for k in range(8)]  # heights of the dark lines on a sheet, 0.12 ... 0.75


def sheet_quad(cx: float, cy: float, w: float, h: float, angle_deg: float) -> np.ndarray:
    """Corners (top-left, top-right, bottom-right, bottom-left) of a w by h sheet turned clockwise on screen around (cx, cy)."""
    corners = np.array([[-w, -h], [w, -h], [w, h], [-w, h]], dtype=np.float64) / 2
    a = np.radians(angle_deg)
    turn = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])
    return (corners @ turn.T + np.array([cx, cy])).astype(np.float32)


def _point(p) -> tuple[int, int]:
    return int(p[0]), int(p[1])


def table_photo(quads: list[np.ndarray], size=(2400, 1800)) -> bytes:
    """JPEG of a wooden table with a pale sheet on each quad, every sheet carrying eight dark lines of "text"."""
    width, height = size
    noise = np.random.default_rng(7).integers(-12, 12, size=(height, width, 3), dtype=np.int16)
    img = np.clip(np.array(WOOD, dtype=np.int16) + noise, 0, 255).astype(np.uint8)
    for quad in quads:
        cv2.fillPoly(img, [quad.astype(np.int32)], PAPER)
        top_left, top_right, _, bottom_left = np.asarray(quad, dtype=np.float64)
        along, down = top_right - top_left, bottom_left - top_left
        for f in TEXT_ROWS:
            start = top_left + f * down
            cv2.line(img, _point(start + 0.10 * along), _point(start + 0.75 * along), INK, 4)
    out = io.BytesIO()
    Image.fromarray(img).save(out, format="JPEG", quality=92)
    return out.getvalue()


def encode_mask(raster: np.ndarray) -> str:
    """The one-bit wire form of a 0/1 raster; decoded again at once, so a wrong encoding fails here."""
    height, width = raster.shape
    payload = _encode_raster(raster.ravel().tolist(), width, height)
    back = decode_mask_to_raster(SegmentationMask(encoding="one_bit", payload=payload, width=width, height=height))
    if not np.array_equal(np.frombuffer(back, dtype=np.uint8).reshape(height, width), raster):
        raise ValueError("mask round trip failed")
    return payload


def record(obj_id: int, quad: np.ndarray, frame: tuple[int, int], mask_scale: float = 0.25, c: float | None = 0.9) -> str:
    """One SAM record for a sheet whose corners are in the pixels of the picture SAM got; box edges inclusive."""
    pts = np.asarray(quad, dtype=np.float64)
    x1, y1 = (int(v) for v in np.floor(pts.min(axis=0)))
    x2, y2 = (int(v) for v in np.ceil(pts.max(axis=0)))
    box_w, box_h = x2 - x1 + 1, y2 - y1 + 1
    mask_w, mask_h = max(4, int(box_w * mask_scale)), max(4, int(box_h * mask_scale))
    raster = np.zeros((mask_h, mask_w), dtype=np.uint8)
    shrunk = (pts - np.array([x1, y1])) * np.array([mask_w / box_w, mask_h / box_h])
    cv2.fillPoly(raster, [shrunk.astype(np.int32)], 1)
    confidence = "" if c is None else f";c={c}"
    return (f"{obj_id}<|box;x1={x1};y1={y1};x2={x2};y2={y2};w={frame[0]};h={frame[1]}{confidence}|>"
            f"<|mask;x=0;y=0;data={mask_h},{mask_w},{encode_mask(raster)}|>")


def sam_events(text: str, completed: bool = True) -> list[dict]:
    """The stream of a SAM answer; completed=False is a stream cut off before its final event."""
    events = [{"type": "response.output_text.delta", "delta": text}] if text else []
    if completed:
        events.append({"type": "response.completed", "response": {"id": "resp_SYNTHETIC", "usage": {"input_tokens": 0}}})
    return events


def sent_size(body: dict) -> tuple[int, int]:
    """Width and height of the picture the product really put in the request (content[0] is the prompt text)."""
    url = body["input"][0]["content"][1]["image_url"]
    with Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1]))) as sent:
        return sent.size


class FakeSAM:
    """Answers like SAM would for quads drawn on the ORIGINAL photo, scaled to what was sent."""

    def __init__(self, quads: list[np.ndarray], original: tuple[int, int], extra: list[str] | None = None,
                 completed: bool = True):
        self.quads = quads
        self.original = original
        self.extra = list(extra or [])  # ready records, already in the pixels of the picture that is sent
        self.completed = completed
        self.bodies: list[dict] = []

    def events(self, body: dict) -> list[dict]:
        self.bodies.append(body)
        frame = sent_size(body)
        scale = np.array([frame[0] / self.original[0], frame[1] / self.original[1]])
        records = [record(10 + 3 * i, quad * scale, frame) for i, quad in enumerate(self.quads)] + self.extra
        return sam_events("<0f>" + ",".join(records) + "\n" if records else "", self.completed)
