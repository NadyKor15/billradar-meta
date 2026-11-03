"""Download the public policy sources and the blank form into the local cache (nothing here is committed)."""

from __future__ import annotations

import sys

import requests

from billradar.policies.source import CACHE, FORMS, SOURCES, form_path, page_texts, pdf_path, sha256

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) BillRadar policy fetch"}


_MARKERS = {"ecfr": b"<?xml", "html": b"<"}


def _fetch(url: str, marker: bytes, strip: bool):
    """The response, and whether it is a 200 whose body opens with the marker."""
    resp = requests.get(url, headers=HEADERS, timeout=60)
    body = resp.content.lstrip() if strip else resp.content
    return resp, resp.status_code == 200 and body.startswith(marker)


def _fetch_policy(policy_id: str) -> bool:
    src = SOURCES[policy_id]
    resp, good = _fetch(src.url, _MARKERS.get(src.kind, b"%PDF"), True)
    if not good:
        print("FAIL %s: HTTP %s, %s" % (policy_id, resp.status_code, resp.headers.get("content-type")))
        return False
    pdf_path(policy_id).write_bytes(resp.content)
    pages = page_texts(policy_id)
    print("ok   %s: %d bytes, %d pages, sha256 %s" % (policy_id, len(resp.content), len(pages), sha256(policy_id)[:16]))
    return True


def _fetch_form(form_id: str) -> bool:
    title, url = FORMS[form_id]
    resp, good = _fetch(url, b"%PDF", False)
    if not good:
        print("FAIL %s: HTTP %s" % (form_id, resp.status_code))
        return False
    dest = form_path(form_id)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(resp.content)
    print("ok   %s: %d bytes (%s)" % (form_id, len(resp.content), title))
    return True


def main() -> int:
    CACHE.mkdir(parents=True, exist_ok=True)
    outcomes = [_fetch_policy(pid) for pid in SOURCES]
    outcomes += [_fetch_form(fid) for fid in FORMS]
    failures = outcomes.count(False)
    print("errors: %d" % failures)
    return int(failures > 0)


if __name__ == "__main__":
    sys.exit(main())
