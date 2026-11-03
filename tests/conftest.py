"""Tests never start Muse Glimmer. What a test drew with PIL is what the sheet says: one piece per text call. A sample pile's sheet reads
as the model read it (tests/fixtures/recordings/glimmer). Anything else, such as a sheet cut out of a drawn photo, reads as empty, and an
empty piece stays closed."""

import pytest
from PIL import ImageDraw

from billradar import local_reader, redact, sheet_pieces

DRAWN: list[tuple] = []  # (image, [(text, box), ...]) of the running test


def _printed_on(img) -> list[tuple[str, tuple]] | None:
    rgb = img.convert("RGB")
    for source, items in DRAWN:
        if source.size == rgb.size and source.convert("RGB").tobytes() == rgb.tobytes():
            return items
    return None


READ_PIECES, TRANSCRIBE = local_reader.read_pieces, local_reader.transcribe


def _no_server(prompt, jpeg):
    raise local_reader.NotAvailable("tests never start the model")


def _read_pieces(img):
    items = _printed_on(img)
    if items is not None:
        return [(text, box) for text, box in items], sheet_pieces.pieces(img)[1]
    try:
        return READ_PIECES(img)
    except local_reader.NotAvailable:
        boxes, h = sheet_pieces.pieces(img)
        return [("", tuple(int(v) for v in b)) for _, b in sorted(boxes.items())], h


def _transcribe(img, again=False):
    stored = local_reader.RECORDINGS / local_reader.recording_name(local_reader.WHOLE_AGAIN if again else local_reader.WHOLE, img)
    if stored.is_file():
        return stored.read_text()
    hit = redact._reads.get(redact._key(img))
    if hit:
        return "\n".join(ln.text for ln in hit.lines)
    items = _printed_on(img)
    if items is not None:
        return "\n".join(text for text, _ in items)
    try:
        return TRANSCRIBE(img, again)
    except local_reader.NotAvailable:
        return ""


@pytest.fixture(autouse=True)
def no_model_in_tests(request, monkeypatch):
    if request.node.get_closest_marker("glimmer"):
        yield
        return
    DRAWN.clear()
    redact._reads.clear()
    redact._read_backs.clear()
    real_text = ImageDraw.ImageDraw.text

    def text(self, xy, content, *a, **k):
        real_text(self, xy, content, *a, **k)
        try:
            box = tuple(int(v) for v in self.textbbox(xy, content, font=k.get("font") or self.getfont(), anchor=k.get("anchor")))
        except (TypeError, ValueError):
            return
        for source, items in DRAWN:
            if source is self._image:
                items.append((content, box))
                return
        DRAWN.append((self._image, [(content, box)]))

    monkeypatch.setattr(ImageDraw.ImageDraw, "text", text)
    monkeypatch.setattr(local_reader._server, "ask", _no_server)
    monkeypatch.setattr(local_reader, "read_pieces", _read_pieces)
    monkeypatch.setattr(local_reader, "transcribe", _transcribe)
    monkeypatch.setattr(local_reader, "turn_of", lambda img: 0)
    yield
