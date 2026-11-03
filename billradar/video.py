"""SAM 3.1 on a video of the table: the clip stays here, a soft copy goes out, every sheet is cut from the clip.

Flow:
  clip (stays local) -> small, blurred, silent copy with no metadata, checked by OCR -> SAM 3.1 "sheet of paper"
  -> one track per sheet, kept across frames -> the frames where each sheet is whole and largest
  -> those frames from the clip itself -> cut and straightened exactly like a photo, the sharpest one kept.

`input_video` takes a whole clip and nothing less, so the copy is the only way to use tracking without sending the
clip. Sheets found here go through the same covering, leak gate and reading as sheets from photos (pipeline.run).

One request follows 16 objects at most in all (the docs say per frame; three live clips stopped at 16 with 6-8 in any
frame, and sheets further on were never picked up), and the edges of the next row use up places. So a clip goes out in
overlapping pieces, each with its own 16 places; a sheet seen in two pieces is one sheet (one_paper_once).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
from meta_sam_parser import (
    CompletedOutcome,
    SegmentationMaskRecord,
    decode_mask_to_raster,
    video_segmentation_format,
)
from PIL import Image, ImageDraw

from billradar import redact, sam
from billradar.meta_client import MAX_VIDEO_FRAMES, VIDEO_FPS, MetaClient, data_url

MAX_BYTES = 1 << 30  # a phone clip of about a minute in 4K
MAX_SECONDS = MAX_VIDEO_FRAMES // VIDEO_FPS
MAX_SENT = 50_000_000  # the API's limit for a video inside a request; the copy never goes to file storage
SOFT_SIDE = 900  # as redact.sam_copy: enough to see the sheets' edges, not to read them
SPOT_CHECKS = 3  # frames of the copy read on this computer before it may leave
TRIES = 4
EDGE = 0.004  # a box this close to the frame's edge may be cut off by it
PAPER = 1.29  # height over width of a sheet, until the clip's own whole sheets say otherwise
EDGE_CUT = 0.02  # less than this short of a sheet's shape, against one edge: the sheet is all there (a live clip: -3 %, cut 7 %)
MIN_SEEN = 3  # frames; less than that is a flicker
WINDOW = 180  # frames in one request: three live clips needed at least 221 to use up the 16 places
OVERLAP = 40  # a sheet at the join stands whole in one piece or the other
PICK = 3  # frames of each track looked at in full size
LOOK_SIDE = 1280  # one pass over the whole clip at this size finds the frames where the camera stood still
SAME_PAPER = 0.7  # share of numbers two cuts have in common when they are one sheet seen twice
SAME_LOOK = 0.8  # likeness of two cuts: one sheet 0.885 and 0.952, two different sheets 0.694 at most (live clip)
SHARED = 0.4  # of the shorter list of numbers, for two cuts that look alike: one sheet read twice 0.5, two pages of a form 0
MIN_NUMBERS = 5
FFMPEG_SECONDS = 300
FRAME = re.compile(r"<(\d+)f>")
BOX = re.compile(r"(\d+)<\|box;x1=(\d+);y1=(\d+);x2=(\d+);y2=(\d+);w=\d+;h=\d+(?:;c=([\d.]+))?\|>")
WORD = re.compile(r"[A-Za-z0-9]{5,}")
NUMBER = re.compile(r"\d[\d,./-]*\d")


class VideoError(ValueError):
    """Said to the family as it is: why this video cannot be used."""


@dataclass
class Clip:
    path: Path
    size: tuple[int, int]  # width, height as displayed, after the rotation flag
    seconds: float


@dataclass
class Seen:
    frame: int  # in the copy as a whole
    box: tuple[float, float, float, float]  # left, top, right, bottom in the clip's pixels
    confidence: float | None = None
    mask: SegmentationMaskRecord | None = None
    sharp: float = 0.0  # inside the box, from the pass over the clip
    piece: int = 0  # which piece of the clip it was seen in


@dataclass
class Found:
    result: sam.SheetsResult
    soft: Image.Image  # one frame of the copy, for "what left this device"
    strip: Image.Image  # the frame each sheet came from, outlined and numbered
    frames_sent: int = 0
    blur: float = 0.0


def _run(cmd: list[str]) -> str:
    try:
        done = subprocess.run(cmd, capture_output=True, text=True, timeout=FFMPEG_SECONDS)
    except FileNotFoundError as exc:
        raise VideoError("this device has no ffmpeg, so it cannot open a video") from exc
    except subprocess.TimeoutExpired as exc:
        raise VideoError("the video took too long to open") from exc
    if done.returncode:
        raise VideoError("this file could not be opened as a video")
    return done.stdout


def probe(path: Path) -> Clip:
    out = json.loads(_run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                           "stream=width,height:stream_side_data=rotation:stream_tags=rotate:format=duration",
                           "-of", "json", str(path)]) or "{}")
    streams = out.get("streams") or []
    if not streams:
        raise VideoError("this file has no video in it")
    s = streams[0]
    turn = int(float((s.get("tags") or {}).get("rotate", 0) or 0))
    for side in s.get("side_data_list") or []:
        turn = int(float(side.get("rotation", turn) or 0))
    w, h = int(s["width"]), int(s["height"])
    seconds = float((out.get("format") or {}).get("duration") or 0)
    if seconds > MAX_SECONDS:
        raise VideoError(f"this video runs {seconds:.0f} seconds; keep it under {MAX_SECONDS}")
    return Clip(path, (h, w) if abs(turn) % 180 == 90 else (w, h), seconds)


def _soft_size(size: tuple[int, int]) -> tuple[int, int]:
    k = min(1.0, SOFT_SIDE / max(size))
    return tuple(max(2, int(v * k) // 2 * 2) for v in size)  # the codec wants even sides


def _encode(clip: Clip, sigma: float, out: Path) -> None:
    w, h = _soft_size(clip.size)
    _run(["ffmpeg", "-v", "error", "-y", "-i", str(clip.path), "-map", "0:v:0", "-an", "-sn", "-dn",
          "-map_metadata", "-1", "-map_chapters", "-1",
          "-vf", f"fps={VIDEO_FPS},scale={w}:{h}:flags=lanczos,gblur=sigma={sigma:.1f},format=yuv420p",
          "-c:v", "libx264", "-preset", "veryfast", "-crf", "30", "-threads", "4", "-movflags", "+faststart",
          "-fflags", "+bitexact", "-flags:v", "+bitexact", str(out)])


def frames_at(path: Path, numbers: list[int]) -> dict[int, Image.Image]:
    """Frames by their number in the copy's timing, read from `path`: the same moments in the clip and in the copy."""
    if not numbers:
        return {}
    wanted = sorted(set(numbers))
    picked = "+".join(f"eq(n\\,{n})" for n in wanted)
    with tempfile.TemporaryDirectory(prefix="billradar-frames-") as tmp:
        _run(["ffmpeg", "-v", "error", "-y", "-i", str(path), "-vf", f"fps={VIDEO_FPS},select='{picked}'",
              "-fps_mode", "passthrough", "-compression_level", "1", f"{tmp}/f%05d.png"])
        files = sorted(Path(tmp).glob("f*.png"))
        return {n: Image.open(f).convert("RGB") for n, f in zip(wanted, files)}


def _words(img: Image.Image) -> set[str]:
    return {w.lower() for w in WORD.findall(redact.read_back(img))}


def _numbers(img: Image.Image) -> set[str]:
    return {n for ln in redact.ocr(img) for n in NUMBER.findall(ln.text)}  # the sheet's own reading: it is needed anyway


def _count_frames(path: Path) -> int:
    seconds = float(json.loads(_run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json",
                                     str(path)]) or "{}").get("format", {}).get("duration") or 0)
    return max(1, int(seconds * VIDEO_FPS))


def still_readable(copy: Path, clip: Clip, secrets: list[redact.Secret]) -> bool:
    """True when anything on the papers can be read on the copy: a family value, or a word OCR also reads in the clip.
    Blur makes OCR invent words; a word found in both is one it really read."""
    total = _count_frames(copy)
    spots = sorted({round(i * (total - 1) / max(1, SPOT_CHECKS - 1)) for i in range(SPOT_CHECKS)})
    soft, sharp = frames_at(copy, spots), frames_at(clip.path, spots)
    for n, img in soft.items():
        if secrets and redact.leaks(img, secrets):
            return True
        if n in sharp and _words(img) & _words(sharp[n]):
            return True
    return False


def soft_copy(clip: Clip, secrets: list[redact.Secret], tmp: Path) -> tuple[bytes, float]:
    """What SAM gets. It is blurred more until the check reads nothing; if it never stops, nothing is sent."""
    sigma = SOFT_SIDE / 150
    for attempt in range(TRIES):
        out = tmp / f"soft-{attempt}.mp4"
        _encode(clip, sigma, out)
        if not still_readable(out, clip, secrets):
            raw = out.read_bytes()
            if len(raw) > MAX_SENT:
                raise VideoError("this video is too long to send; keep it under a minute")
            return raw, sigma
        sigma *= 1.6
    raise VideoError("could not make this video unreadable for SAM; it was not sent")


def request_body(mp4: bytes, phrase: str = sam.PHRASE) -> dict:
    """Ask SAM 3.1 to follow `phrase` through a clip. The clip is the soft, silent copy, never the family's own file."""
    parts = [{"type": "input_text", "text": phrase}, {"type": "input_video", "video_url": data_url(mp4, "video/mp4")}]
    return {"model": "sam-3.1", "input": [{"type": "message", "role": "user", "content": parts}], "stream": True,
            "metadata": {"mask_encoding": "one_bit", "include_confidence": "true"}}


def _frame_of(rec) -> int:
    return int(getattr(rec.frame, "frame_index", rec.frame) or 0)


def parse(text: str, scale: tuple[float, float] = (1.0, 1.0), start: int = 0, piece: int = 0) -> tuple[dict[str, list[Seen]], list[str]]:
    """SAM's lines -> one list of sightings per object, in the clip's pixels and frames. Only the boxes: a clip has hundreds
    of frames, and a mask is needed for just a few of them (`with_masks`). `start`: where this piece begins in the copy."""
    sx, sy = scale
    tracks: dict[str, list[Seen]] = {}
    for line in text.splitlines():
        if not (m := FRAME.match(line.strip())):
            continue
        for oid, x1, y1, x2, y2, c in BOX.findall(line):
            tracks.setdefault(f"{piece}.{oid}", []).append(Seen(
                int(m.group(1)) + start, (int(x1) * sx, int(y1) * sy, (int(x2) + 1) * sx, (int(y2) + 1) * sy),
                float(c) if c else None, piece=piece))
    return tracks, []


def with_masks(text: str, wanted: list[tuple[str, Seen]], start: int = 0) -> list[str]:
    """Meta's parser reads the frames that were chosen, of one piece; their sightings get their masks."""
    frames = {s.frame - start for _, s in wanted}
    lines = [ln for ln in text.splitlines() if (m := FRAME.match(ln.strip())) and int(m.group(1)) in frames]
    parser = video_segmentation_format().create_parser()
    parser.push("\n".join(lines) + "\n")
    result = parser.finish(CompletedOutcome()).result
    masks = {(r.object_id, _frame_of(r)): r for r in result.records if isinstance(r, SegmentationMaskRecord)}
    for oid, s in wanted:
        s.mask = masks.get((oid.split(".", 1)[-1], s.frame - start))
    return [f"{d.severity}: {d.code} {d.message}" for d in result.diagnostics]


def pieces(total: int) -> list[tuple[int, int]]:
    """(first frame, how many) of each request. The last one runs to the end rather than leave a stump."""
    step = WINDOW - OVERLAP
    starts = list(range(0, max(1, total - OVERLAP), step))
    if len(starts) > 1 and total - starts[-1] < OVERLAP * 2:
        starts.pop()
    return [(s, (starts[i + 1] + OVERLAP if i + 1 < len(starts) else total) - s) for i, s in enumerate(starts)]


def cut_piece(copy: Path, start: int, count: int, out: Path) -> bytes:
    _run(["ffmpeg", "-v", "error", "-y", "-i", str(copy), "-an", "-map_metadata", "-1",
          "-vf", f"select='between(n,{start},{start + count - 1})',setpts=N/{VIDEO_FPS}/TB",
          "-c:v", "libx264", "-preset", "veryfast", "-crf", "30", "-threads", "4", "-r", str(VIDEO_FPS), "-movflags", "+faststart",
          "-fflags", "+bitexact", "-flags:v", "+bitexact", str(out)])
    return out.read_bytes()


def sharpness_in_boxes(clip: Clip, chosen: list[tuple[str, list[Seen]]]) -> None:
    """One pass over the clip at a small size: how sharp each sheet is in each frame it stands whole in. A moving camera
    smears a sheet in most frames; the frames to look at closely are those where it stood still, not the largest."""
    by_frame: dict[int, list[Seen]] = {}
    for _, seen in chosen:
        for s in seen:
            by_frame.setdefault(s.frame, []).append(s)
    if not by_frame:
        return
    k = LOOK_SIDE / max(clip.size)
    w, h = (max(2, int(v * k) // 2 * 2) for v in clip.size)
    proc = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(clip.path), "-vf", f"fps={VIDEO_FPS},scale={w}:{h},format=gray",
                             "-f", "rawvideo", "-"], stdout=subprocess.PIPE)
    n = 0
    with proc.stdout:
        while (raw := proc.stdout.read(w * h)) and len(raw) == w * h:
            for s in by_frame.get(n, ()):
                gray = np.frombuffer(raw, dtype=np.uint8).reshape(h, w)
                l, t, r, b = (int(v * x) for v, x in zip((k, k, k, k), s.box))
                patch = gray[max(0, t):b, max(0, l):r]
                s.sharp = float(cv2.Laplacian(patch, cv2.CV_64F).var()) if patch.size else 0.0
            n += 1
    proc.wait(timeout=FFMPEG_SECONDS)


def _inside(box: tuple, size: tuple[int, int]) -> bool:
    l, t, r, b = box
    w, h = size
    m = EDGE * max(size)
    return l > m and t > m and r < w - m and b < h - m


def _whole(box: tuple, size: tuple[int, int], paper: float = PAPER) -> bool:
    """Clear of the frame's edges, or against one of them and still the full shape of a sheet."""
    if _inside(box, size):
        return True
    l, t, r, b = box
    W, H = size
    m = EDGE * max(size)
    side, end = l <= m or r >= W - m, t <= m or b >= H - m
    if (l <= m and r >= W - m) or (t <= m and b >= H - m) or (side and end):
        return False
    w, h = r - l, b - t
    short = 1 - w / max(1.0, h / paper) if side else 1 - h / max(1.0, w * paper)
    return w > 0 and h > 0 and short <= EDGE_CUT


def paper_shape(tracks: dict[str, list[Seen]], size: tuple[int, int]) -> float:
    shapes = sorted((s.box[3] - s.box[1]) / max(1.0, s.box[2] - s.box[0]) for seen in tracks.values() for s in seen if _inside(s.box, size))
    usable = [x for x in shapes if sam.ASPECT_RANGE[0] <= x <= sam.ASPECT_RANGE[1]]
    return usable[len(usable) // 2] if len(usable) >= 5 else PAPER


def _area(s: Seen) -> float:
    return max(0.0, s.box[2] - s.box[0]) * max(0.0, s.box[3] - s.box[1])


def choose(tracks: dict[str, list[Seen]], size: tuple[int, int]) -> tuple[list[tuple[str, list[Seen]]], list[str]]:
    """For each sheet, in the order they first appear: the frames where it stands whole."""
    kept, dropped = [], []
    w, h = size
    paper = paper_shape(tracks, size)
    for oid, seen in sorted(tracks.items(), key=lambda kv: min(s.frame for s in kv[1])):
        if len(seen) < MIN_SEEN:
            dropped.append(f"object {oid}: seen for {len(seen)} frames only")
            continue
        whole = [s for s in seen if _whole(s.box, size, paper)]
        if not whole:
            dropped.append(f"object {oid}: never whole in the frame")
            continue
        shaped = [s for s in whole if sam.ASPECT_RANGE[0] <= (s.box[3] - s.box[1]) / max(1.0, s.box[2] - s.box[0])
                  <= sam.ASPECT_RANGE[1] and _area(s) >= sam.MIN_AREA_FRACTION * w * h]
        if not shaped:
            dropped.append(f"object {oid}: not sheet-shaped")
            continue
        kept.append((oid, shaped))
    return kept, dropped


def _detection(oid: str, s: Seen) -> sam.Detection:
    mask = None
    if s.mask is not None:
        try:
            raster = np.frombuffer(decode_mask_to_raster(s.mask.mask), dtype=np.uint8)
            raster = raster.reshape(s.mask.mask.height, s.mask.mask.width)
            size = (max(1, round(s.box[2] - s.box[0])), max(1, round(s.box[3] - s.box[1])))
            mask = cv2.resize(raster, size, interpolation=cv2.INTER_NEAREST)
        except Exception:  # noqa: BLE001 - a bad mask still leaves a usable box, as on photos
            mask = None
    return sam.Detection(oid, s.box, s.confidence, mask)


def _sharpness(img: Image.Image) -> float:
    gray = cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2GRAY)
    k = 1000 / max(gray.shape)
    return float(cv2.Laplacian(cv2.resize(gray, None, fx=k, fy=k, interpolation=cv2.INTER_AREA), cv2.CV_64F).var())


@dataclass
class Cut:
    oid: str
    seen: Seen
    corners: np.ndarray | None
    image: Image.Image
    sharp: float
    frame: Image.Image = field(repr=False, default=None)


def cut_best(oid: str, seen: list[Seen], frames: dict[int, Image.Image]) -> Cut | None:
    cuts = []
    for s in seen:
        if s.frame not in frames:
            continue
        corners = sam.corners_from_mask(_detection(oid, s))
        arr = np.asarray(frames[s.frame])
        img = Image.fromarray(sam.straighten(arr, corners)) if corners is not None else frames[s.frame].crop(
            tuple(int(v) for v in s.box))
        cuts.append(Cut(oid, s, corners, img, _sharpness(img), frames[s.frame]))
    return max(cuts, key=lambda c: c.sharp, default=None)


def _look(img: Image.Image) -> np.ndarray:
    g = cv2.resize(np.asarray(img.convert("L"), dtype=np.float32), (96, 128), interpolation=cv2.INTER_AREA)
    return ((g - g.mean()) / (g.std() + 1e-6)).ravel()


def one_paper_once(cuts: list[Cut]) -> tuple[list[Cut], list[str]]:
    """A sheet that left the frame and came back is a new object to SAM. Two pages of one form share nearly all their
    words, so they are told apart by their numbers; a merged pair would lose a sheet with no word said. A smeared cut
    has no numbers to compare: then the look of the page decides, against a sheet that reads. Numbers read a little
    differently on two views of one sheet: the look decides too, as long as enough of them are shared."""
    marks = [_numbers(c.image) for c in cuts]
    looks = [_look(c.image) for c in cuts]

    def one(i: int, j: int) -> bool:
        alike = float(looks[i] @ looks[j]) / looks[i].size >= SAME_LOOK
        if len(marks[i]) >= MIN_NUMBERS and len(marks[j]) >= MIN_NUMBERS:
            both = len(marks[i] & marks[j])
            return both / len(marks[i] | marks[j]) >= SAME_PAPER or (alike and both / min(len(marks[i]), len(marks[j])) >= SHARED)
        return alike and bool(marks[i] or marks[j]) and cuts[i].sharp != cuts[j].sharp

    keep: list[int] = []
    dropped = []
    for i in range(len(cuts)):
        same = next((j for j in keep if one(i, j)), None)
        if same is None:
            keep.append(i)
            continue
        if cuts[i].sharp > cuts[same].sharp:  # the place in the order stays, the sharper image wins
            cuts[same], marks[same], looks[same] = cuts[i], marks[i], looks[i]
        dropped.append(f"object {cuts[i].oid}: the same sheet as an earlier one")
    return [cuts[i] for i in keep], dropped


def _strip(sheets: list[sam.Sheet], cuts: list[Cut], per_row: int = 7, height: int = 420) -> Image.Image:
    tiles = []
    for s, c in zip(sheets, cuts):
        k = height / c.frame.height
        tile = c.frame.resize((max(1, int(c.frame.width * k)), height))
        draw = ImageDraw.Draw(tile)
        if s.corners:
            draw.polygon([(x * k, y * k) for x, y in s.corners], outline=sam.SHEET_COLORS[0], width=3)
        draw.text((10, 8), s.doc_id[1:], fill="white", font=redact._font(30))
        tiles.append(tile)
    if not tiles:
        return Image.new("RGB", (640, 120), "white")
    w = max(t.width for t in tiles)
    rows = (len(tiles) + per_row - 1) // per_row
    canvas = Image.new("RGB", (min(per_row, len(tiles)) * (w + 8) + 8, rows * (height + 8) + 8), "white")
    for i, t in enumerate(tiles):
        r, c = divmod(i, per_row)
        canvas.paste(t, (8 + c * (w + 8), 8 + r * (height + 8)))
    return canvas


def find_sheets(client: MetaClient, raw: bytes, secrets: list[redact.Secret] | None = None,
                phrase: str = sam.PHRASE) -> Found:
    """The clip's bytes never reach `client`: only the soft copy does."""
    if not shutil.which("ffmpeg"):
        raise VideoError("this device has no ffmpeg, so it cannot open a video")
    if len(raw) > MAX_BYTES:
        raise VideoError("this video is over 1 GB; keep it under a minute")
    with tempfile.TemporaryDirectory(prefix="billradar-video-") as name:
        tmp = Path(name)
        src = tmp / "clip"
        src.write_bytes(raw)
        clip = probe(src)
        copy, blur = soft_copy(clip, secrets or [], tmp)
        sent = tmp / "copy.mp4"
        sent.write_bytes(copy)
        total = _count_frames(sent)
        soft = next(iter(frames_at(sent, [total // 2]).values()), Image.new("RGB", _soft_size(clip.size), "white"))
        scale = (clip.size[0] / soft.width, clip.size[1] / soft.height)
        answers, tracks, seconds, replayed = [], {}, 0.0, True
        for i, (start, count) in enumerate(pieces(total)):
            part = copy if count >= total else cut_piece(sent, start, count, tmp / f"piece-{i}.mp4")
            res = client.respond(request_body(part, phrase), label=f"sam:video:{phrase}")
            answers.append((res.text, start))
            seconds, replayed = seconds + res.seconds, replayed and res.replayed
            tracks |= parse(res.text, scale, start, i)[0]
        chosen, dropped = choose(tracks, clip.size)
        sharpness_in_boxes(clip, chosen)
        chosen = [(oid, sorted(seen, key=lambda s: (s.sharp, _area(s)), reverse=True)[:PICK]) for oid, seen in chosen]
        notes = []
        for i, (text, start) in enumerate(answers):
            mine = [(oid, s) for oid, seen in chosen for s in seen if s.piece == i]
            if mine:
                notes += with_masks(text, mine, start)
        frames = frames_at(src, [s.frame for _, seen in chosen for s in seen])
        cuts = [c for oid, seen in chosen if (c := cut_best(oid, seen, frames)) is not None]
        cuts, again = one_paper_once(cuts)
        sheets = [sam.Sheet(doc_id=f"S{i}", box=tuple(int(v) for v in c.seen.box), confidence=c.seen.confidence,
                            corners=[(int(x), int(y)) for x, y in c.corners] if c.corners is not None else None,
                            image=c.image, straightened=c.corners is not None) for i, c in enumerate(cuts, start=1)]
        result = sam.SheetsResult(sheets, dropped + again + notes, phrase, soft.size, clip.size, seconds, replayed)
        return Found(result, soft, _strip(sheets, cuts), frames_sent=total, blur=blur)
