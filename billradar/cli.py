"""Command line for BillRadar: check a saved case, run a bill pack end to end, or preview what would be covered."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from billradar import checks, pipeline, providers
from billradar.case import Case, Profile
from billradar.meta_client import MetaClient


def _print_report(r: checks.Report) -> None:
    rows = ["{}: income {}% of the poverty guideline, policy {}".format(r.case_id, r.fpl_pct, r.policy_id)]
    for f in r.findings:
        price = "" if f.amount is None else " ${:,.2f}".format(f.amount)
        rows += ["  [%s] %s%s" % (f.kind, f.title, price), " " * 8 + f.detail]
    rows += ["  [no money] " + f.title for f in r.no_money]
    rows += ["  [held back] " + f.title for f in r.held_back]
    rows.append("  total that may come off: ${:,.2f}; apply by: {}".format(r.total_may_come_off, r.apply_by or "-"))
    print(*rows, sep="\n")


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="billradar")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check").add_argument("case_json", type=Path)
    run = sub.add_parser("run")
    run.add_argument("pack", type=Path)
    run.add_argument("--out", type=Path, default=None)
    cover = sub.add_parser("cover")
    cover.add_argument("pack", type=Path)
    cover.add_argument("--out", type=Path, required=True)
    return ap


def _pack_media(pack: Path) -> tuple[list[bytes], list[tuple[str, bytes]]]:
    """Photos (raw bytes) and PDFs (name, bytes) of a pack folder, each in path order."""
    photos: list[bytes] = []
    pdfs: list[tuple[str, bytes]] = []
    for item in sorted(pack.iterdir()):
        ext = item.suffix.lower()
        if ext == ".pdf":
            pdfs.append((item.name, item.read_bytes()))
        elif ext in {".jpg", ".jpeg", ".png"}:
            photos.append(item.read_bytes())
    return photos, pdfs


def _day(text) -> date | None:
    return date.fromisoformat(text) if isinstance(text, str) and text else None


def _check_case(args: argparse.Namespace) -> int:
    _print_report(checks.run(Case.model_validate_json(args.case_json.read_text())))
    return 0


def _run_pack(args: argparse.Namespace) -> int:
    meta = json.loads((args.pack / "profile.json").read_text())
    photos, pdfs = _pack_media(args.pack)
    client = providers.make_client()
    mode = "LIVE" if client.live else "replay"
    print("mode: %s; %d photo(s), %d file(s)" % (mode, len(photos), len(pdfs)))
    profile = Profile.model_validate(meta["profile"])
    outcome = pipeline.run(client, photos, pdfs, profile, meta["policy_id"], meta.get("letterhead", ""),
                           _day(meta.get("today")), case_id=args.pack.name,
                           fictional=bool(meta.get("fictional")))
    target = args.out if args.out is not None else Path("runs") / args.pack.name
    pipeline.save(outcome, target)
    print(*["  ! " + p for p in outcome.problems], sep="\n", end="\n" if outcome.problems else "")
    _print_report(outcome.report)
    print("saved to", target)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    handlers = {
        "check": _check_case,
        "run": _run_pack,
        "cover": lambda a: _cover(a.pack, a.out),
    }
    return handlers[args.cmd](args)


def _cover(pack: Path, out: Path) -> int:
    """Names of what was written and whether it would be sent; never a covered value."""
    meta = json.loads((pack / "profile.json").read_text())
    photos = [(p.name, p.read_bytes()) for p in sorted(pack.iterdir()) if p.suffix.lower() in {".jpg", ".jpeg", ".png"}]
    files = [(p.name, p.read_bytes()) for p in sorted(pack.iterdir()) if p.suffix.lower() == ".pdf"]
    out.mkdir(parents=True, exist_ok=True)
    held = 0
    for n, c in enumerate(pipeline.cover_only(photos, files, Profile.model_validate(meta["profile"])), start=1):
        if c.image is not None:
            c.image.save(out / f"{n:02d}-covered.jpg", quality=90)
        held += bool(c.blocked)
        print(f"{n:02d}-covered.jpg  {c.name}: {'HELD BACK, still readable: ' + c.blocked if c.blocked else 'ok to send'}")
    print(f"{held} of {n} would be held back; look at every page in {out} before trusting it")
    return 1 if held else 0


if __name__ == "__main__":
    sys.exit(main())
