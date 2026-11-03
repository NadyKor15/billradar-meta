"""A sheet a test draws, and what it says: the test knows the text, so no model is needed to read it."""

from functools import cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from billradar import redact
from billradar.open_lines import Tag

FONT_DIRS = ["/System/Library/Fonts/Supplemental", "/Library/Fonts", "/usr/share/fonts/truetype/dejavu"]
PRODUCT_FONT = Path(redact.__file__).parent / "fonts" / "NotoSans-Bold.ttf"  # one file, always bold


@cache
def font(size: int, bold: bool = False):
    """Arial where the machine has it, else the product's own font; any of them fits the longest private line."""
    name = "Arial Bold.ttf" if bold else "Arial.ttf"
    for folder in FONT_DIRS:
        try:
            return ImageFont.truetype(str(Path(folder) / name), size)
        except OSError:
            continue  # not installed here: the next folder
    return ImageFont.truetype(str(PRODUCT_FONT), size)


def sheet(lines: list[str], width: int = 1275) -> Image.Image:
    """One printed line per row, each known as a piece of the sheet."""
    img = Image.new("RGB", (width, 160 + 90 * len(lines)), "white")
    draw = ImageDraw.Draw(img)
    tags = []
    for i, (text, f, y) in enumerate([("LAKEVIEW DEMO HOSPITAL - SAMPLE", font(36, True), 60)] + [(t, font(28), 150 + 90 * k) for k, t in enumerate(lines)], start=1):
        draw.text((90, y), text, font=f, fill="black")
        tags.append(Tag(i, text, tuple(int(v) for v in draw.textbbox((90, y), text, font=f))))
    redact.remember(img, tags, 28)
    return img
