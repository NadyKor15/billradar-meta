"""The printed pieces of a sheet, found with plain image processing and laid out for reading.

A model given a whole table loses track of which text stands where, and its own coordinates are invented. So OpenCV
finds every piece of print, each piece is cut out, and the cuts go down one image in a numbered column. What the model
reads next to a number belongs to that piece's exact pixels.
"""

from __future__ import annotations

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROW_H = 34  # height of a cut on the list
GAP = 10
NUMBER_W = 76
PAGE_W = 1400
PAGE_ROWS = 34  # more rows shrink past what the model reads well
TALL = 3.2  # of the type height: taller is not one line of print
DENSE_ROWS = 0.45  # of the densest row


def ink_mask(img: Image.Image) -> np.ndarray:
    """Print: dark on light, and light on a dark bar. The window is wider than a stroke and narrower than a bar, so a bar
    itself does not count as ink."""
    g = np.asarray(img.convert("L"), dtype=np.uint8)
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (max(15, g.shape[1] // 50) | 1,) * 2)
    bg = cv2.medianBlur(g, 41)
    dark = cv2.morphologyEx(g, cv2.MORPH_BLACKHAT, k)
    light = cv2.morphologyEx(g, cv2.MORPH_TOPHAT, k)
    return np.where(bg >= 128, dark > 38, light > 38).astype(np.uint8)


def row_height(ink: np.ndarray) -> int:
    n, _, st, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    hs = [st[i, cv2.CC_STAT_HEIGHT] for i in range(1, n) if 7 <= st[i, cv2.CC_STAT_HEIGHT] <= 40 and st[i, cv2.CC_STAT_AREA] >= 12]
    return max(8, int(np.median(hs))) if hs else 14


def without_rules(ink: np.ndarray, h: int) -> np.ndarray:
    long_h = cv2.morphologyEx(ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (max(80, 8 * h), 1)))
    long_v = cv2.morphologyEx(ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(60, 6 * h))))
    text = ink.copy()
    text[(long_h | long_v) > 0] = 0
    return text


def text_mask(img: Image.Image) -> np.ndarray:
    ink = ink_mask(img)
    return without_rules(ink, row_height(ink))


def _bands(block: np.ndarray, share: float = 0.04) -> list[tuple[int, int]]:
    """A tall piece of print (a frame glued lines together) cut into lines at its empty rows."""
    prof = block.sum(axis=1)
    on = prof > max(2, share * prof.max())
    out, start = [], None
    for i, v in enumerate(list(on) + [False]):
        if v and start is None:
            start = i
        elif not v and start is not None:
            if i - start >= 3:
                out.append((start, i - start))
            start = None
    return out


def _segments(ink: np.ndarray) -> tuple[list[tuple[int, int, int, int]], int]:
    """Letters join into words and phrases along a line; lines of a table do not join each other."""
    h = row_height(ink)
    text = without_rules(ink, h)  # table rules would glue the lines
    joined = cv2.morphologyEx(text, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (max(9, int(1.6 * h)), 1)))
    n, _, st, _ = cv2.connectedComponentsWithStats(joined, connectivity=8)
    width = ink.shape[1]
    out = []
    for i in range(1, n):
        x, y, w, ht, _ = st[i]
        if w < 1.3 * h or w > 0.97 * width:
            continue
        found = _bands(joined[y:y + ht, x:x + w]) if ht > 1.8 * h else [(0, ht)]
        if any(bh > TALL * h for _, bh in found):  # the wedge at a dark bar's end joins its text: the dense rows are the line
            found = _bands(joined[y:y + ht, x:x + w], DENSE_ROWS)
        for by, bh in found:
            if bh < 0.7 * h or bh > TALL * h:
                continue
            crop = text[y + by:y + by + bh, x:x + w]
            cols = np.where(crop.sum(axis=0) > 0)[0]
            if len(cols) == 0:
                continue
            x0, x1 = x + int(cols.min()), x + int(cols.max()) + 1
            if float(crop[:, int(cols.min()):int(cols.max()) + 1].mean()) < 0.10:  # remains of a frame. Dense stays: bold print merges
                continue
            out.append((int(x0), int(y + by), int(x1), int(y + by + bh)))
    return sorted(out, key=lambda b: (b[1], b[0])), h


def _rows(segs: list, h: int) -> list[dict]:
    rows: list[dict] = []
    for b in segs:
        cy = (b[1] + b[3]) / 2
        for r in rows:
            if abs(r["cy"] - cy) <= 0.6 * h:
                r["segs"].append(b)
                r["cy"] = (r["cy"] * (len(r["segs"]) - 1) + cy) / len(r["segs"])
                break
        else:
            rows.append({"cy": cy, "segs": [b]})
    rows.sort(key=lambda r: r["cy"])
    return rows


def pieces(img: Image.Image) -> tuple[dict[int, tuple[int, int, int, int]], int]:
    """The pieces in reading order: down the sheet, along each row. Number -> box in the sheet's pixels."""
    segs, h = _segments(ink_mask(img))
    ordered = [b for r in _rows(segs, h) for b in sorted(r["segs"])]
    return {i: b for i, b in enumerate(ordered, start=1)}, h


def lists(img: Image.Image, boxes: dict[int, tuple], font_path: str, row_h: int = ROW_H, per: int = PAGE_ROWS) -> list[Image.Image]:
    """The numbered lists of cuts, one image per `per` pieces."""
    font = ImageFont.truetype(font_path, 24)
    out, keys = [], sorted(boxes)
    for start in range(0, len(keys), per):
        part = keys[start:start + per]
        page = Image.new("RGB", (PAGE_W, len(part) * (row_h + GAP) + GAP), (255, 255, 255))
        draw = ImageDraw.Draw(page)
        y = GAP
        for k in part:
            b = boxes[k]
            crop = img.crop((max(0, b[0] - 4), max(0, b[1] - 4), min(img.width, b[2] + 4), min(img.height, b[3] + 4)))
            scale = min(row_h / crop.height, (PAGE_W - NUMBER_W - 10) / crop.width)
            crop = crop.resize((max(1, int(crop.width * scale)), max(1, int(crop.height * scale))), Image.Resampling.LANCZOS)
            draw.text((6, y + 2), str(k), fill=(170, 0, 0), font=font)
            page.paste(crop, (NUMBER_W, y))
            draw.line((0, y + row_h + GAP // 2, PAGE_W, y + row_h + GAP // 2), fill=(225, 225, 225))
            y += row_h + GAP
        out.append(page)
    return out
