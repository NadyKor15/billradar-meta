"""Measurement runner: scores the simple prompt, the strong prompt and the full pipeline against sealed answer keys."""

from __future__ import annotations

import io
import json
import os
import statistics
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from billradar import evaluation as ev  # noqa: E402
from billradar import pipeline, providers, reader  # noqa: E402
from billradar.case import Profile  # noqa: E402
from billradar.meta_client import MetaClient  # noqa: E402

PACKS = ROOT / "eval" / "packs"
LEDGER = ROOT / "eval" / "SEALED.txt"


PATHS = ("Simple prompt", "Strong prompt", "BillRadar")


def jpeg(img) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)
    return buf.getvalue()


def _pack_inputs(pack: Path) -> tuple[list[bytes], list[tuple[str, bytes]]]:
    entries = sorted(pack.iterdir())
    photos = [p.read_bytes() for p in entries if p.suffix.lower() in (".jpg", ".jpeg", ".png")]
    pdfs = [(p.name, p.read_bytes()) for p in entries if p.suffix.lower() == ".pdf"]
    return photos, pdfs


class _Meter:
    """Cost and wall time of one path: client calls made and monotonic seconds between enter and exit."""

    def __init__(self, client):
        self.client = client
        self.usd = 0.0
        self.seconds = 0.0

    def __enter__(self):
        self._from = len(self.client.calls)
        self._began = time.monotonic()
        return self

    def __exit__(self, *_exc):
        self.seconds = time.monotonic() - self._began
        self.usd = spent(self.client, self._from)
        return False


def _ask_each(client, parts, build, label: str) -> list[str]:
    texts = []
    for sheets, files in parts:
        texts.append(client.respond(build(sheets, files), label=label).text)
    return texts


def _join_answers(texts: list[str]) -> str:
    if len(texts) < 2:
        return "".join(texts)
    total = len(texts)
    return "\n\n".join("[answer %d of %d]\n%s" % (n, total, t) for n, t in enumerate(texts, 1))


def _household(profile: Profile, meta: dict) -> dict:
    assets = profile.liquid_assets
    return {"size": profile.household_size, "yearly_income": str(profile.annual_income),
            "savings": str(assets) if assets is not None else "", "insured": profile.insured, "today": meta["today"]}


def _score_simple(client, parts, key, out: Path) -> ev.Score:
    answer = _join_answers(_ask_each(client, parts, ev.simple_body, "eval:simple"))
    (out / "simple.txt").write_text(answer)
    verdict = client.respond(ev.judge_body(answer, key), label="eval:judge").text
    (out / "judge.json").write_text(verdict)
    preds, extra = ev.from_judge(verdict, key)
    return ev.score(key, preds, extra)


def _score_strong(client, parts, key, policy_id: str, household: dict, out: Path) -> ev.Score:
    def build(sheets, files):
        return ev.strong_body(sheets, files, policy_id, household)

    merged = []
    for text in _ask_each(client, parts, build, "eval:strong"):
        merged += json.loads(text).get("findings", [])
    blob = json.dumps({"findings": merged})
    (out / "strong.json").write_text(blob)
    return ev.score(key, ev.from_strong(blob))


def run_pack(client: MetaClient, pack: Path, out: Path) -> dict[str, ev.Score]:
    meta = json.loads((pack / "profile.json").read_text())
    key = ev.Key.model_validate_json((pack / "key.json").read_text())
    photos, pdfs = _pack_inputs(pack)
    profile = Profile.model_validate(meta["profile"])
    out.mkdir(parents=True, exist_ok=True)

    with _Meter(client) as full:
        run = pipeline.run(client, photos, pdfs, profile, meta["policy_id"], meta.get("letterhead", ""),
                           date.fromisoformat(meta["today"]), pack.name,
                           fictional=bool(meta.get("fictional", False)), private=True)
        pipeline.save(run, out / "billradar")
        full_score = ev.score(key, ev.from_report(run.report))
    unproven = len([f for f in run.report.findings if f.amount is not None and not (f.evidence or f.policy_refs)])

    uncovered = [(s.doc_id, jpeg(run.originals.get(s.doc_id, s.image))) for s in run.sheets]
    attachments = [("D%d" % n, name, data) for n, (name, data) in enumerate(pdfs, 1)]
    parts = reader.batches(uncovered, attachments, getattr(client, "max_images", None))

    with _Meter(client) as simple:
        simple_score = _score_simple(client, parts, key, out)
    with _Meter(client) as strong:
        strong_score = _score_strong(client, parts, key, meta["policy_id"], _household(profile, meta), out)

    meters = {"BillRadar": full, "Simple prompt": simple, "Strong prompt": strong}
    summary = {"pack": pack.name,
               "usd": {n: round(m.usd, 6) for n, m in meters.items()},
               "seconds": {n: round(m.seconds, 1) for n, m in meters.items()},
               "unproven_amounts": unproven,
               "total_may_come_off": str(run.report.total_may_come_off)}
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    return {"Simple prompt": simple_score, "Strong prompt": strong_score, "BillRadar": full_score}


def spent(client, first: int) -> float:
    return sum(c.get("usd", 0.0) for c in client.calls[first:])


def headline(summaries: list[dict], total: dict[str, ev.Score]) -> dict:
    """The numbers the video and the README quote, each from this run's own files."""
    paths = list(total)
    return {"paths": ev.numbers(total), "packs": len(summaries),
            "usd": {p: round(sum(s["usd"][p] for s in summaries), 4) for p in paths},
            "median_seconds": {p: statistics.median(s["seconds"][p] for s in summaries) for p in paths},
            "unproven_amounts": sum(s["unproven_amounts"] for s in summaries),
            "money_found": str(sum(float(s["total_may_come_off"]) for s in summaries))}


def _packs_with_keys(split: str) -> list[Path]:
    return [p for p in sorted((PACKS / split).iterdir()) if (p / "key.json").is_file()]


def _markdown(split: str, count: int, stamp: str, client, table: str) -> str:
    mode = "live" if client.live else "REPLAYED (not a measurement)"
    models = ", ".join("%s %s" % pair for pair in providers.models(client).items())
    return "# %s: %d packs, %s, %s, models: %s\n\n%s\n" % (split, count, stamp, mode, models, table)


def _seal_split(split: str) -> int:
    for line in ev.seal(sorted((PACKS / split).glob("*/key.json")), LEDGER):
        print(line)
    return 0


def _measure(client, packs: list[Path], base: Path) -> tuple[dict[str, ev.Score], list[dict]]:
    """Run every pack under `base`; sum the scores per path and collect each pack's summary."""
    total = {name: ev.Score() for name in PATHS}
    summaries = []
    for pack in packs:
        folder = base / pack.name
        for name, score in run_pack(client, pack, folder).items():
            total[name].add(score)
        summaries.append(json.loads((folder / "summary.json").read_text()))
    return total, summaries


def _unsealed(packs: list[Path]) -> list[str]:
    return [p.name for p in packs if not ev.check_seal(p / "key.json", LEDGER)]


def _run_split(split: str) -> int:
    packs = _packs_with_keys(split)
    loose = _unsealed(packs) if split == "holdout" else []
    if loose:
        print("refusing: keys not sealed or changed since sealing: %s" % (loose,))
        return 1
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%MZ") + "-" + providers.name()
    results = ROOT / "eval" / "results" / stamp
    client = providers.make_client()
    os.environ.setdefault(pipeline.WONDER_REVIEW, "1")
    total, summaries = _measure(client, packs, results / split)
    numbers = headline(summaries, total)
    report = _markdown(split, len(packs), stamp, client, ev.table(total))
    results.mkdir(parents=True, exist_ok=True)
    for name, content in ((split + "-numbers.json", json.dumps(numbers, indent=2)), (split + ".md", report)):
        (results / name).write_text(content)
    print(report)
    return 0


def main(argv: list[str]) -> int:
    first, *rest = argv or ["work"]
    return _seal_split(rest[0]) if first == "seal" else _run_split(first)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
