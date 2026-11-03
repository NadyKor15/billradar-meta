"""The first live calls, smallest first, on fictional papers only. Run with a key and BILLRADAR_LIVE=1.

python scripts/live_smoke.py models                     # the models this key sees (free)
python scripts/live_smoke.py count                      # free token count; prints headers about limits or billing
python scripts/live_smoke.py photo <pack> [photo-name]  # one photo of a pack through the whole pipeline, private mode
python scripts/live_smoke.py dry <pack> [photo-name]    # the same with the pack's synthetic answers: no model, no key
python scripts/live_smoke.py pack <pack>                # the whole pack, private mode, scored against its key
python scripts/live_smoke.py web                        # the questions below through step 2 of the answer ladder
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from billradar import evaluation as ev  # noqa: E402
from billradar import example, pipeline, providers  # noqa: E402
from billradar.case import Profile  # noqa: E402
from billradar.meta_client import API_URL, MetaClient, SpendLedger  # noqa: E402

MODELS_URL = API_URL.replace("/responses", "/models")
COUNT_URL = API_URL + "/input_tokens"
WORTH_PRINTING = re.compile(r"(?i)credit|billing|balance|limit|usage|plan|remaining")


def headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {os.environ['MODEL_API_KEY']}", "Content-Type": "application/json"}


def models() -> int:
    r = requests.get(MODELS_URL, headers=headers(), timeout=30)
    print("HTTP", r.status_code)
    r.raise_for_status()
    print(sorted(m["id"] for m in r.json().get("data", [])))
    return 0


def count() -> int:
    body = {"model": "muse-spark-1.3", "input": [{"role": "user", "content": [{"type": "input_text", "text": "hello"}]}]}
    r = requests.post(COUNT_URL, headers=headers(), json=body, timeout=30)
    print("HTTP", r.status_code, r.text[:200])
    print({k: v for k, v in r.headers.items() if WORTH_PRINTING.search(k)})
    return 0 if r.ok else 1


def photo(pack: Path, name: str | None, dry: bool = False) -> int:
    meta = json.loads((pack / "profile.json").read_text())
    if not meta.get("fictional"):
        print("refusing: this pack is not marked fictional")
        return 1
    photos = sorted(p for p in pack.glob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    chosen = next(p for p in photos if p.name == name) if name else photos[0]
    client = providers.make_client()
    if dry:
        answers = example.PackAnswers(pack)
        answers.photos = [chosen]
        client = MetaClient(transport=answers, record_to=None, journal=None)
    print("live:", client.live, "| photo:", chosen.name, "| spent before: $%.4f" % SpendLedger().spent())
    run = pipeline.run(client, [chosen.read_bytes()], [], Profile.model_validate(meta["profile"]), meta["policy_id"],
                       meta.get("letterhead", ""), date.fromisoformat(meta["today"]), f"smoke-{pack.name}",
                       fictional=True, private=True)
    out = ROOT / "runs" / f"smoke-{pack.name}"
    pipeline.save(run, out)
    print("sheets:", [s.doc_id for s in run.sheets], "| redacted:", run.redacted, "| problems:", run.problems)
    print("documents:", [(d.doc_id, d.kind.value, len(d.lines)) for d in run.case.documents])
    print("findings:", [(f.kind.value, str(f.amount)) for f in run.report.findings])
    for c in client.calls:
        print(c["label"], c["model"], "s", c.get("seconds"), "usd", c.get("usd"), json.dumps(c.get("usage")))
    print("spent after: $%.4f" % SpendLedger().spent(), "| saved to", out)
    return 0


def whole_pack(pack: Path) -> int:
    meta = json.loads((pack / "profile.json").read_text())
    if not meta.get("fictional"):
        print("refusing: this pack is not marked fictional")
        return 1
    photos = [p.read_bytes() for p in sorted(pack.glob("*")) if p.suffix.lower() in {".jpg", ".jpeg", ".png"}]
    pdfs = [(p.name, p.read_bytes()) for p in sorted(pack.glob("*.pdf"))]
    client = providers.make_client()
    print("live:", client.live, "| photos:", len(photos), "| files:", len(pdfs), "| spent before: $%.4f" % SpendLedger().spent())
    started = time.monotonic()
    run = pipeline.run(client, photos, pdfs, Profile.model_validate(meta["profile"]), meta["policy_id"],
                       meta.get("letterhead", ""), date.fromisoformat(meta["today"]), pack.name, fictional=True, private=True)
    out = ROOT / "runs" / f"live-{pack.name}"
    pipeline.save(run, out)
    print("seconds:", round(time.monotonic() - started, 1), "| sheets:", len(run.sheets), "| problems:")
    for p in run.problems:
        print("  !", p)
    print("findings:", [(f.kind.value, str(f.amount), [e.doc_id for e in f.evidence]) for f in run.report.findings])
    print("worth asking:", [(f.kind.value, f.title[:60]) for f in run.report.worth_asking])
    print("held back:", [(f.kind.value, f.detail[-120:]) for f in run.report.held_back])
    print("total:", run.report.total_may_come_off, "apply_by:", run.report.apply_by)
    key = ev.Key.model_validate_json((pack / "key.json").read_text())
    print(ev.table({"BillRadar": ev.score(key, ev.from_report(run.report))}))
    for c in client.calls:
        print(c["label"], c["model"], "s", c.get("seconds"), "usd", c.get("usd"))
    print("spent after: $%.4f" % SpendLedger().spent(), "| saved to", out)
    return 0


WEB_QUESTIONS = ["Can Anna Sample at 100 Example Street get help with bill LDH-000123 for $1,234.56 before March 14?",
                 "What's the deadline to apply for financial assistance at Memorial?",
                 "They say my account went to collections on 04/01/2026, can they do that?",
                 "Does the No Surprises Act cover the anesthesiologist for my baby's birth?",
                 "Our income is $58,000 and we are 3 people, Baby Sample is on my plan, member LDH-000124",
                 "The lady on the phone said I have 30 days to appeal, is that right?",
                 "Why did they charge Anna twice?"]


def web() -> int:
    from billradar import tavily_client, web_answer
    from tests.test_writer import case
    client, tavily, c = providers.make_client(), tavily_client.TavilyClient(), case()
    print("live:", client.live, tavily.live, "| domains:", web_answer.domains(c))
    for q in WEB_QUESTIONS:
        started = time.monotonic()
        found = web_answer.find(client, tavily, c, q)
        print(f"OUT: {web_answer.clean_question(q, c)}\n  {time.monotonic() - started:.1f} s ->",
              f"{found.quote!r} | {found.url}" if found else "nothing")
    print("spent after: $%.4f" % SpendLedger().spent())
    return 0


def main(argv: list[str]) -> int:
    if argv[:1] == ["models"]:
        return models()
    if argv[:1] == ["count"]:
        return count()
    if argv[:1] == ["web"]:
        return web()
    if argv[:1] == ["pack"]:
        return whole_pack(Path(argv[1]))
    if argv[:1] in (["photo"], ["dry"]):
        return photo(Path(argv[1]), argv[2] if len(argv) > 2 else None, dry=argv[0] == "dry")
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
