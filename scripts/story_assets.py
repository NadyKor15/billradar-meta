"""What the home page story shows from the recorded Meta run of the example (fictional pack), never typed by hand:

  python scripts/story_assets.py

Replays the example run exactly as the app does (no key, no spend) and writes to billradar/web/static/story/:
  table.webp  the table photo with the most sheets, made smaller
  found.json  the boxes SAM 3.1 put around its sheets, and the recording they came from;
              the people and the first sheet in the request Muse Wonder got for its review, cut verbatim,
              and the name of that recording (its name is the hash of the request, so a different request
              would not have found it)."""
import io
import json
import sys
from pathlib import Path

from PIL import Image

from billradar import example, sam
from billradar.meta_client import ReplayTransport

OUT = Path(__file__).resolve().parents[1] / "billradar" / "web" / "static" / "story"
EXCERPT_DOC = '"people": ['  # mother and baby with empty names, then the first sheet: only tokens left the device
EXCERPT_LEN = 470

found, asked = [], []
_find, _events = sam.find_sheets, ReplayTransport.events


def spy_find(client, photo, *a, **k):
    res = _find(client, photo, *a, **k)
    found.append((photo, res))
    return res


def spy_events(self, body):
    asked.append((self.path(body), body))
    return _events(self, body)


sam.find_sheets, ReplayTransport.events = spy_find, spy_events
example.run_recorded(example.PACK, example.EXAMPLE_ID)

photo, res = max(found, key=lambda f: len(f[1].sheets))
finds = [a for a in asked if a[1]["model"].startswith("sam")]
find_path, find_body = finds[[id(f[1]) for f in found].index(id(res))]
img = sam.load_photo(photo).convert("RGB")
w, h = img.size
img.resize((round(900 * w / h), 900), Image.LANCZOS).save(OUT / "table.webp", "WEBP", quality=80, method=6)

reviews = [a for a in asked if a[1]["model"].startswith("muse-wonder")]
if not reviews:
    sys.exit("no Muse Wonder request in this run: the review is not recorded")
review_path, body = reviews[0]
text = next(p["text"] for m in body["input"] if m["role"] == "user" for p in m["content"] if p.get("text"))
start = text.index(EXCERPT_DOC)
excerpt = text[start:start + EXCERPT_LEN]
excerpt = excerpt[:excerpt.rindex(", ")] + ", …"

(OUT / "found.json").write_text(json.dumps({
    "photo": {"width": w, "height": h},
    "boxes": [{"sheet": s.doc_id, "box": list(s.box)} for s in res.sheets],
    "find_model": find_body["model"],
    "find_recording": find_path.name,
    "sent": {"model": body["model"], "recording": review_path.name, "excerpt": excerpt},
}, indent=1) + "\n")
print(f"{len(res.sheets)} boxes on a {w}x{h} photo ({find_path.name}); excerpt {len(excerpt)} chars from {review_path.name}")
