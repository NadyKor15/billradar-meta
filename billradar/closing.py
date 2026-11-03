"""Closing a sheet: everything printed goes, except the lines open_lines opened.

Outside the open pieces the sheet becomes smooth background; only table rules stay, because they are not text and the
reader needs the grid. A faint line up the margin does not survive this, read or not. A family's value that was read
gets its token in its place, the same token on every sheet.
"""

from __future__ import annotations

import re
from collections import Counter

import cv2
import numpy as np
from PIL import Image, ImageDraw

from billradar import redact, sheet_pieces
from billradar.open_lines import Tag, Verdict

PAPER = (250, 250, 248)
SMOOTH = 31  # wider than any stroke of body type
MARGIN = 3  # around an open piece: tails of letters stay
TOKEN_GRAY = (120, 120, 120)
TOKEN_LIGHT = (235, 235, 235)  # on a dark bar
DARK_BAR = 110


def known_of(vault: redact.Vault) -> set[str]:
    """The family's values as the rules look for them; a name also word by word."""
    return {redact.compact(s.value) for s in vault.secrets} | {redact.compact(w) for s in vault.secrets if s.kind == "PATIENT"
                                                                for w in s.value.split() if len(w) >= 3}


def token_of(text: str, kind: str, vault: redact.Vault) -> str:
    if kind and not re.search(r"\d|\b[A-Z]", text):  # "sibility", a cut read: closed, and no value of the family
        return ""
    if kind and re.search(r"\w", text):  # a value after a label: whole, not by the surname
        return vault.token_for_label(kind, text.strip(" ,:;#.")).token
    spans = redact._spans(text, vault, False)
    if not spans:
        return ""
    # A family shares a surname: the given name says who. CASTILLO, ADRIAN is the baby, not the mother.
    people = {sec.token: sec.value.split() for (k, _), sec in vault.seeded.items() if k == "PATIENT" and "," not in sec.value}
    named = {tok for tok, words in people.items() if words and re.search(rf"(?i)\b{re.escape(words[0])}\b", text)}
    if len(named) == 1:
        return named.pop()
    return max(spans, key=lambda x: x[1] - x[0])[2].token


def _flat(rgb: np.ndarray, box: tuple) -> None:
    """A solid fill in the colour around it, on paper and on a dark bar: no pieces of letters, no blots on the rules."""
    height, width = rgb.shape[:2]
    x0, y0, x1, y1 = max(0, box[0]), max(0, box[1]), min(width, box[2]), min(height, box[3])
    if x1 <= x0 or y1 <= y0:
        return
    ring = np.concatenate([rgb[max(0, y0 - 3):y0, x0:x1].reshape(-1, 3), rgb[y1:min(height, y1 + 3), x0:x1].reshape(-1, 3),
                           rgb[y0:y1, max(0, x0 - 3):x0].reshape(-1, 3), rgb[y0:y1, x1:min(width, x1 + 3)].reshape(-1, 3)])
    rgb[y0:y1, x0:x1] = np.median(ring, axis=0) if len(ring) else PAPER


def _ink_end(x1: int, y0: int, y1: int, text: np.ndarray, h: int, stop: int) -> int:
    """A box can end inside a word: follow the ink of the line up to an empty stretch or the next open piece."""
    has = text[y0:y1 + 1].sum(axis=0) > 0
    limit, gap, x = int(1.1 * h), 0, x1
    while x + 1 < min(text.shape[1], stop) and gap <= limit:
        x += 1
        if has[x]:
            x1, gap = x, 0
        else:
            gap += 1
    return x1


def _word_runs(box: tuple, text: np.ndarray, h: int, n: int) -> list[tuple[int, int]] | None:
    """The words in a box, from the ink: n runs at the widest gaps, or None when the ink does not give n words. Counting
    characters misses by one or two; a border here stands in a real gap, so it neither shows a letter nor cuts a sum."""
    if n == 0:
        return None
    x0, y0, x1, y1 = box
    cols = text[y0:y1 + 1, x0:x1 + 1].sum(axis=0) > 0
    for gap in range(int(1.5 * h), 1, -1):
        runs, start, last, empty = [], None, 0, 0
        for i, on in enumerate(cols):
            if on:
                start = i if start is None else start
                last, empty = i, 0
            elif start is not None:
                empty += 1
                if empty >= gap:
                    runs.append((x0 + start, x0 + last))
                    start = None
        if start is not None:
            runs.append((x0 + start, x0 + last))
        if len(runs) == n:
            return runs
        if len(runs) > n:
            return None
    return None


def close(img: Image.Image, tags: list[Tag], verdicts: dict[int, Verdict], vault: redact.Vault, h: int, kept_sums: Counter | None = None) -> Image.Image:
    original = np.array(img.convert("RGB"), dtype=np.uint8)
    text = sheet_pieces.text_mask(img)
    width = text.shape[1]
    keep = [t.box for t in tags if verdicts[t.n].how == "open"]
    k = max(3, int(.5 * h))
    mask = cv2.dilate(cv2.morphologyEx(text, cv2.MORPH_CLOSE, np.ones((k, k), np.uint8)), np.ones((3, 3), np.uint8))
    for b in keep:
        mask[max(0, b[1] - 2):b[3] + 3, max(0, b[0] - 3):b[2] + 4] = 0
    rgb = cv2.inpaint(original, (mask * 255).astype(np.uint8), 3, cv2.INPAINT_TELEA)
    ink = sheet_pieces.ink_mask(img)
    rules = ink - sheet_pieces.without_rules(ink, h)
    smooth = cv2.medianBlur(rgb, SMOOTH)
    smooth[rules > 0] = rgb[rules > 0]
    rgb = smooth

    def stop_at(x1: int, y0: int, y1: int) -> int:
        return min([u[0] for u in keep if u[1] < y1 and y0 < u[3] and u[0] > x1] + [width])

    marks = []
    for t in tags:  # closed first; open pieces go back on top: a neighbour's box may reach into them, and they were read whole
        if verdicts[t.n].how != "open":
            x0, y0, x1, y1 = t.box
            _flat(rgb, (x0 - 4, y0 - 3, _ink_end(x1, y0, y1, text, h, stop_at(x1, y0, y1)) + 5, y1 + 4))
            marks.append((x0, y0, token_of(t.text, "", vault), y1 - y0))
    for b in keep:
        top, left = max(0, b[1] - MARGIN), max(0, b[0] - MARGIN)
        rgb[top:b[3] + MARGIN + 1, left:b[2] + MARGIN + 1] = original[top:b[3] + MARGIN + 1, left:b[2] + MARGIN + 1]
    sums = Counter()  # the sums that stand on the sheet as printed: their pixels were not touched
    for t in tags:
        v = verdicts[t.n]
        if v.how != "open":
            continue
        if not v.hide:
            sums.update(redact.AMOUNT_READ.findall(t.text))
            continue
        x0, y0, x1, y1 = t.box
        words = list(re.finditer(r"\S+", t.text))  # a dash is ink; a bar read off a table rule is not
        runs = _word_runs(t.box, text, h, len(words))
        if runs is None:
            words = [m for m in words if re.search(r"\w", m.group())]
            runs = _word_runs(t.box, text, h, len(words))
        if runs is None:  # the border is unknown: a sum must not be cut, so the whole piece closes, and the check holds the sheet
            _flat(rgb, (x0 - 4, y0 - 3, _ink_end(x1, y0, y1, text, h, stop_at(x1, y0, y1)) + 5, y1 + 4))
            marks.append((x0, y0, token_of(t.text, "", vault), y1 - y0))
            continue
        shown = list(t.text)
        for a, b, _ in v.hide:
            shown[a:b] = " " * (b - a)
        sums.update(redact.AMOUNT_READ.findall("".join(shown)))
        for a, b, kind in v.hide:
            hit = [runs[i] for i, m in enumerate(words) if m.start() < b and m.end() > a]
            if not hit:
                continue
            left, right = hit[0][0] - 2, hit[-1][1] + 3
            if not any(re.search(r"\w", m.group()) for m in words if m.start() >= b):  # a value to the end of the line, the stars after it, what the box cut off
                right = _ink_end(right, y0, y1, text, h, stop_at(x1, y0, y1)) + 4
            _flat(rgb, (left, y0 - 3, right, y1 + 4))
            marks.append((max(0, left), y0, token_of(t.text[a:b], kind, vault), y1 - y0))
    if kept_sums is not None:
        kept_sums.update(sums)
    out = Image.fromarray(rgb)
    draw = ImageDraw.Draw(out)
    placed: list[tuple[int, int]] = []  # one token per place: two boxes of one line give one mark
    for x0, y0, token, ht in marks:
        if token and not any(abs(y0 - y) < 12 and abs(x0 - x) < 120 for x, y in placed):
            placed.append((x0, y0))
            under = rgb[max(0, y0):y0 + max(ht, 1), max(0, x0):x0 + 40]
            fill = TOKEN_LIGHT if under.size and under.mean() < DARK_BAR else TOKEN_GRAY
            draw.text((x0 + 2, y0), token, fill=fill, font=redact._font(max(11, min(ht, 18))))
    boxes = [redact.Line(np.array([[t.box[0], t.box[1]], [t.box[2], t.box[1]], [t.box[2], t.box[3]], [t.box[0], t.box[3]]], dtype=np.float32), "xxxx", .9)
             for t in tags]
    for b in redact.codes(img, boxes):
        redact._cover_box(draw, b, float(h))
    return out
