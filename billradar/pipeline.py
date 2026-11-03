"""Photos and PDFs in, a checked case out, in two steps.

First the family's computer finds the sheets and closes everything personal on them; only a blurred copy of the table
leaves. Then, with the person's yes, the closed sheets go to the reading model, the answers are checked, the report is
held back where a checker disagrees, and the run is written to disk for the screens."""

from __future__ import annotations

import json
import os
import re
import shutil
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from billradar import (checks, open_reader, pdfpages, people, providers, reader, receipt, reconcile_read, redact, sam,
                       table_rows, verifier, writer)
from billradar import highlight, local_reader, policy_finder, video as clips
from billradar.policies import source as policy_source
from billradar.case import Case, DocKind, Profile
from billradar.meta_client import MetaAPIError, MetaClient


@dataclass
class CaseRun:
    case: Case
    report: checks.Report
    sheets: list[sam.Sheet]
    overlays: list[bytes]  # one numbered overlay per table photo, JPEG
    sent_views: list[bytes] = field(default_factory=list)  # private mode: the covered photo, as the models got it
    problems: list[str] = field(default_factory=list)
    timings: dict[str, float] = field(default_factory=dict)
    replayed: bool = True
    verdict: verifier.Verdict | None = None
    redacted: bool = False
    receipt: dict | None = None  # model, seconds and cost per step (billradar.receipt)
    provider: str = "meta"  # which models answered (providers.py)
    file_previews: dict[str, bytes] = field(default_factory=dict)  # D1 -> page 1 of that PDF as JPEG, shown on this device
    originals: dict = field(default_factory=dict)  # private mode: S1 -> the sheet cut from the photo as taken, for the screen
    found_policy: dict | None = None  # BILLRADAR_POLICY_FINDER=1: the hospital's own policy, via Tavily (policy_finder)
    unreadable: list[str] = field(default_factory=list)  # sheets to photograph again


def _jpeg(img) -> bytes:
    return redact.as_sent(img)  # the gate looks at the sheet in this same form


class RealDataGate(RuntimeError):
    pass


class Unsendable(RealDataGate):
    """Not a leak: a sheet too soft for the device to read. A person may read what OCR cannot, so the leak check proves
    nothing on it. It stays on the device and the family takes a new photo."""


@dataclass
class Prepared:
    """What the family's computer holds once the papers are closed, before anything readable leaves. `finish` takes it from here."""
    profile: Profile
    sheets: list[sam.Sheet]  # closed, in sheet order; nothing withheld
    pages: list  # PDF pages: (D1.1, closed image)
    files: list[tuple[str, bytes]]  # PDFs that go as they are (fictional, not private)
    vault: redact.Vault | None
    originals: dict  # S1 -> the sheet as photographed; stays here
    soft: list  # (what the sheet finder got, the sheets cut from that photo), for the view of what left
    overlays: list[bytes]
    previews: dict[str, bytes]
    problems: list[str]
    timings: dict[str, float]
    lost: dict[str, list[str]]  # numbers a cover could not give back: those sheets give no confirmed sum
    withheld: list[str]  # the gate would not let it out: not sent, the family takes a new photo
    unseen_money: list[str]  # withheld, and it prints sums or cannot be read here: nothing on it was counted
    replayed: bool = True
    calls: list = field(default_factory=list)  # model calls made so far: the sheet finder's
    printed_money: dict[str, bool] = field(default_factory=dict)  # sheet -> it prints a sum
    request: dict = field(default_factory=dict)  # what the person asked with: policy_id, letterhead, fictional

    @property
    def to_send(self) -> list[str]:
        return [s.doc_id for s in self.sheets] + [pid for pid, _ in self.pages]


def run(client: MetaClient, photos: list[bytes], files: list[tuple[str, bytes]], profile: Profile,
        policy_id: str, letterhead: str = "", today: date | None = None, case_id: str = "case",
        fictional: bool = False, private: bool = False, video: bytes | None = None) -> CaseRun:
    """The whole path with nobody in between: sample piles, tests, measurements."""
    return finish(client, prepare(client, photos, files, profile, fictional, private, video), None, policy_id, letterhead,
                  today, case_id)


def prepare(client: MetaClient, photos: list[bytes], files: list[tuple[str, bytes]], profile: Profile, fictional: bool = False,
            private: bool = False, video: bytes | None = None) -> Prepared:
    """Find the sheets and close them, here. Only the blurred copy has left when this returns."""
    try:
        return _prepare(client, photos, files, profile, fictional, private, video)
    except local_reader.NotAvailable as exc:  # no local model, nothing leaves
        raise RealDataGate(f"papers are read on this computer first, and that step cannot run: {exc}") from exc


def finish(client: MetaClient, prepared: Prepared, approved: set[str] | None, policy_id: str, letterhead: str = "",
           today: date | None = None, case_id: str = "case") -> CaseRun:
    """Send what the person let go, read it, check it. `approved` names the sheets and pages; None sends all of them."""
    try:
        return _finish(client, prepared, approved, policy_id, letterhead, today, case_id)
    except local_reader.NotAvailable as exc:
        raise RealDataGate(f"papers are read on this computer first, and that step cannot run: {exc}") from exc


PREPARED = "prepared"


def save_prepared(prep: Prepared, out: Path) -> None:
    """Everything `finish` needs, as files next to the case: the person may answer tomorrow, after a restart. Pixels stay exact (PNG):
    what leaves is what the person saw and what was checked. Sheets as photographed stay on this computer."""
    if prep.vault is None:
        raise RealDataGate("only private mode waits for a person")
    d = out / PREPARED
    d.mkdir(parents=True, exist_ok=True)
    for name in ("sheets", "originals", "pages", "soft"):
        (d / name).mkdir(exist_ok=True)

    def png(img, folder: str, name: str) -> dict:
        img.save(d / folder / f"{name}.png")
        return redact.reading_of(img)

    state = {"profile": json.loads(prep.profile.model_dump_json()), "vault": prep.vault.dump(), "problems": prep.problems, "timings": prep.timings,
             "lost": prep.lost, "withheld": prep.withheld, "unseen_money": prep.unseen_money, "replayed": prep.replayed, "calls": prep.calls,
             "printed_money": prep.printed_money, "request": prep.request,
             "sheets": [{"doc_id": s.doc_id, "box": list(s.box), "confidence": s.confidence, "corners": s.corners, "straightened": s.straightened,
                         "reading": png(s.image, "sheets", s.doc_id)} for s in prep.sheets],
             "pages": [{"doc_id": pid, "reading": png(img, "pages", pid)} for pid, img in prep.pages],
             "originals": {sid: png(img, "originals", sid) for sid, img in prep.originals.items()},
             "soft": [{"file": f"{i}.png", "cut": [s.doc_id for s in cut]} for i, (_, cut) in enumerate(prep.soft)]}
    for i, (img, _) in enumerate(prep.soft):
        img.save(d / "soft" / f"{i}.png")
    for i, raw in enumerate(prep.overlays):
        (d / f"overlay-{i}.jpg").write_bytes(raw)
    for doc_id, raw in prep.previews.items():
        (d / f"preview-{doc_id}.jpg").write_bytes(raw)
    (d / "state.json").write_text(json.dumps(state))


def load_prepared(out: Path) -> Prepared:
    from PIL import Image

    d = out / PREPARED
    state = json.loads((d / "state.json").read_text())

    def image(folder: str, name: str, reading: dict | None = None):
        with Image.open(d / folder / f"{name}.png") as f:
            img = f.convert("RGB")
        if reading is not None:
            redact.restore(img, reading["lines"], reading["h"], reading["turn"])
        return img

    sheets = [sam.Sheet(x["doc_id"], tuple(x["box"]), x["confidence"], [tuple(c) for c in x["corners"]] if x["corners"] else None,
                        image("sheets", x["doc_id"], x["reading"]), x["straightened"]) for x in state["sheets"]]
    by_id = {s.doc_id: s for s in sheets}
    soft = []
    for x in state["soft"]:
        with Image.open(d / "soft" / x["file"]) as f:
            soft.append((f.convert("RGB"), [by_id[sid] for sid in x["cut"] if sid in by_id]))
    overlays = [p.read_bytes() for p in sorted(d.glob("overlay-*.jpg"), key=lambda p: int(p.stem.split("-")[1]))]
    previews = {p.stem.split("-", 1)[1]: p.read_bytes() for p in d.glob("preview-*.jpg")}
    return Prepared(Profile.model_validate(state["profile"]), sheets, [(x["doc_id"], image("pages", x["doc_id"], x["reading"])) for x in state["pages"]],
                    [], redact.Vault.load(state["vault"]), {sid: image("originals", sid, r) for sid, r in state["originals"].items()},
                    soft, overlays, previews, state["problems"], state["timings"], state["lost"], state["withheld"], state["unseen_money"],
                    state["replayed"], state["calls"], state["printed_money"], state["request"])


def drop_prepared(out: Path) -> None:
    """The case went out or was given up: nothing of it waits on the disk any more."""
    shutil.rmtree(out / PREPARED, ignore_errors=True)


def _prepare(client: MetaClient, photos: list[bytes], files: list[tuple[str, bytes]], profile: Profile, fictional: bool,
             private: bool, video: bytes | None) -> Prepared:
    # Two refusals before anything is read, closed or sent.
    if client.live and not fictional:
        raise RealDataGate("live model calls are allowed only on fictional packs (mark the pack fictional)")
    if video is not None and not private:
        raise RealDataGate("a video goes through private mode only")
    calls_before = len(getattr(client, "calls", []))
    find_sheets = providers.sheet_finder(client)
    vault = _vault(profile) if private else None
    problems: list[str] = []
    timings: dict[str, float] = {}
    replayed = True
    unreadable_files: set[int] = set()
    if private:  # the files' own text first: what is typed in them is closed on the photos as well
        for i, (name, raw) in enumerate(files, start=1):
            try:
                pdfpages.learn(vault, raw)
            except pdfpages.RenderError as exc:
                unreadable_files.add(i)
                problems.append(_file_not_sent(name, exc))
    groups: list[tuple[object, list[sam.Sheet]]] = []  # (what the finder was sent, the sheets cut from it)
    overlays: list[bytes] = []
    originals: dict = {}
    taken = 0

    def learned(cut: list[sam.Sheet]) -> None:
        # Sheet by sheet, before the next photo: what is printed here is checked on the copy of that photo as well,
        # and with no local model the second photo never leaves.
        for s in cut:
            originals[s.doc_id] = s.image
            redact.learn(s.image, vault)

    for photo in photos:
        if private:
            as_taken = sam.load_photo(photo)
            to_sam = redact.sam_copy(as_taken, secrets=vault.secrets)
            found = find_sheets(client, photo, send=to_sam, crop_from=as_taken)
        else:
            to_sam = None
            found = find_sheets(client, photo)
        cut = _numbered(found.sheets, taken)
        taken += len(cut)
        timings["sam"] = timings.get("sam", 0.0) + found.seconds
        replayed = replayed and found.replayed
        problems += _finder_notes(found)
        overlays.append(_jpeg(sam.overlay(photo, sam.SheetsResult(cut))))
        groups.append((to_sam, cut))
        if private:
            learned(cut)
    if video is not None:  # one more source
        seen = clips.find_sheets(client, video, vault.secrets)
        cut = _numbered(seen.result.sheets, taken)
        taken += len(cut)
        timings["sam"] = timings.get("sam", 0.0) + seen.result.seconds
        replayed = replayed and seen.result.replayed
        problems += _finder_notes(seen.result)
        overlays.append(_jpeg(seen.strip))
        groups.append((seen.soft, cut))
        learned(cut)
    lost: dict[str, list[str]] = {}
    sheets: list[sam.Sheet] = []
    pages: list = []
    soft: list = []
    printed_money: dict[str, bool] = {}
    withheld: list[str] = []
    unseen_money: list[str] = []
    if not private:
        sheets = [s for _, cut in groups for s in cut]
    else:
        def hold(doc_id: str, as_taken, why: RealDataGate) -> None:
            problems.append(str(why))
            withheld.append(doc_id)
            if isinstance(why, Unsendable) or _prints_money(as_taken):
                unseen_money.append(doc_id)

        def page_gate(closed, page_id: str, as_printed):
            try:
                return _checked(as_printed, closed, page_id, vault, lost)
            except RealDataGate as why:
                hold(page_id, as_printed, why)
                return None

        for to_sam, cut in groups:  # every sheet is learned by now: a number labelled on sheet 10 is closed on 9
            kept: list[sam.Sheet] = []
            for s in cut:
                try:
                    closed = _checked(s.image, redact.redact(s.image, vault).image, s.doc_id, vault, lost)
                except RealDataGate as why:
                    hold(s.doc_id, s.image, why)
                    continue
                kept.append(_sheet_as(s, image=closed))
            soft.append((to_sam, kept))
            sheets += kept
        for i, (name, raw) in enumerate(files, start=1):
            if i in unreadable_files:
                continue
            try:
                pages += pdfpages.cover(raw, f"D{i}", vault, page_gate)
            except pdfpages.RenderError as exc:
                problems.append(_file_not_sent(name, exc))
        printed_money = {sid: _prints_money(img) for sid, img in originals.items()}
    return Prepared(profile, sheets, pages, [] if private else list(files), vault, originals, soft, overlays,
                    _previews(files), problems, timings, lost, withheld, unseen_money, replayed,
                    list(getattr(client, "calls", [])[calls_before:]), printed_money)


def _file_not_sent(name: str, why: Exception) -> str:
    return f"private mode: {name} not sent: {why}"


def _finder_notes(result) -> list[str]:
    """What the sheet finder left out, as lines for the person."""
    return [f"SAM: {d}" for d in result.dropped]


def _sheet_as(s: sam.Sheet, doc_id: str | None = None, image=None) -> sam.Sheet:
    """The same sheet under another number, or with another picture."""
    return sam.Sheet(doc_id or s.doc_id, s.box, s.confidence, s.corners, s.image if image is None else image, s.straightened)


def _numbered(found: list[sam.Sheet], taken: int) -> list[sam.Sheet]:
    """A finder numbers each source from S1; the case numbers them through all sources ("S1" -> "S4" after three sheets)."""
    return [_sheet_as(s, f"S{taken + int(s.doc_id[1:])}") for s in found]


def _checked(original, covered, doc_id: str, vault: redact.Vault, lost: dict[str, list[str]]):
    """The gate a closed picture passes before it may leave. Raises RealDataGate (Unsendable too) and says kinds, never values."""
    _readable(original, doc_id)
    _no_leaks(covered, vault, doc_id)
    return _numbers_kept(original, covered, doc_id, lost)


def _printed_rows(prep: Prepared, sheets: list[sam.Sheet], pages: list) -> dict[str, list]:
    """What this device reads on the papers: the rows of each sheet as photographed, and for each PDF the rows of all
    its pages together (the file's id and each of its page ids hold the same rows)."""
    sources = prep.originals or {s.doc_id: s.image for s in sheets}
    printed = {sid: table_rows.rows(redact.ocr(img)) for sid, img in sources.items()}
    by_file: dict[str, list] = {}
    for page_id, img in pages:
        by_file.setdefault(page_id.split(".")[0], []).extend(table_rows.rows(redact.ocr(img)))
    for page_id, _ in pages:
        printed[page_id] = by_file[page_id.split(".")[0]]
    return printed | by_file


def _finish(client: MetaClient, prep: Prepared, approved: set[str] | None, policy_id: str, letterhead: str, today: date | None,
            case_id: str) -> CaseRun:
    policy_source.require(policy_id)
    calls_before = len(getattr(client, "calls", []))
    goes = (lambda doc_id: True) if approved is None else (lambda doc_id: doc_id in approved)
    sheets = [s for s in prep.sheets if goes(s.doc_id)]
    pages = [(pid, img) for pid, img in prep.pages if goes(pid)]
    problems = list(prep.problems)
    withheld = list(prep.withheld)
    unseen_money = list(prep.unseen_money)
    kept = [s.doc_id for s in prep.sheets if not goes(s.doc_id)] + [pid for pid, _ in prep.pages if not goes(pid)]
    for doc_id in kept:
        problems.append(f"{doc_id}: kept on this computer by the person")
    withheld += kept
    unseen_money += [doc_id for doc_id in kept if prep.printed_money.get(doc_id, True)]
    profile = prep.profile
    if prep.vault is not None:  # tokens back to values for the letters and forms made here; no model gets them
        profile = profile.model_copy(deep=True)
        for secret in prep.vault.secrets:
            profile.local.tokens.setdefault(secret.token.strip("[]"), secret.value)
    models = providers.models(client)
    sent_views = [_jpeg(_what_was_sent(to_sam, [s for s in cut if goes(s.doc_id)], models)) for to_sam, cut in prep.soft]
    if pages:
        sent_views.append(_jpeg(pdfpages.sent_view(pages, _short(models["read"]))))
    digital = [(f"D{i}", name, raw) for i, (name, raw) in enumerate(prep.files, start=1)]
    going = [(s.doc_id, _jpeg(s.image)) for s in sheets] + [(pid, _jpeg(img)) for pid, img in pages]
    read = reader.read_case(client, going, digital)
    problems += [f"reader: {p}" for p in read.problems]
    docs = read.documents
    second = second_read_on(client)
    printed: dict[str, list] = {}
    if second:  # the device counts the printed numbers itself and settles what the two reads dispute
        printed = _printed_rows(prep, sheets, pages)
        docs = reconcile_read.reconcile(client, docs, going, printed, problems, digital, second=open_reader.second_reader())
    soft_files = {w.split(".")[0] for w in withheld if "." in w}
    for d in docs:
        if d.doc_id in prep.lost:
            d.doubts.append(f"{d.doc_id}: {', '.join(prep.lost[d.doc_id])} sits under a family value's cover: take a new photo")
        if d.doc_id.split(".")[0] in soft_files:
            d.doubts.append(f"{d.doc_id}: a page of this file was too soft to send")
    docs = _second_look(client, docs, sheets, problems)
    docs = _office_from_coupon(docs, sheets, letterhead, problems)
    docs = pdfpages.merge_pages(docs)
    docs = people.link(docs, profile)
    docs = checks.one_office_per_account(docs, letterhead)
    docs = _visit_dates(docs, sheets, problems)
    case = checks.plausible_dates(Case(case_id=case_id, letterhead=letterhead, policy_id=policy_id,
                                       today=today or date.today(), profile=profile, documents=docs))
    report = checks.run(case)
    if second:
        report = device_confirms(case, report, printed)
    report = sheets_not_sent(report, withheld, unseen_money, kept)
    report = pages_maybe_unread(case, report, withheld)
    report, verdict = check_and_hold(case, report, client)
    cost = receipt.build(prep.calls + list(getattr(client, "calls", [])[calls_before:]))
    return CaseRun(case, report, sheets, prep.overlays, sent_views, problems, prep.timings | {"spark": read.seconds},
                   prep.replayed and read.replayed, verdict, redacted=prep.vault is not None, receipt=cost,
                   provider=getattr(client, "provider", "meta"), file_previews=prep.previews, originals=prep.originals,
                   found_policy=policy_finder.for_case(case, client),
                   unreadable=unreadable_sheets(case.documents, [s.doc_id for s in sheets] + withheld, report))


def _prints_money(page) -> bool:
    return any(row.amounts for row in table_rows.rows(redact.ocr(page)))


def _paper(doc_id: str) -> str:
    return f"{'sheet' if doc_id.startswith('S') else 'file'} {doc_id[1:].split('.')[0]}"


def sheets_not_sent(report: checks.Report, withheld: list[str], unseen_money: list[str], kept: list[str] = ()) -> checks.Report:
    """What stayed on the device was not read, so no sum comes from it. It may still hold a payment or a charge that moves
    a sum or a date worked out from the other papers: while it is unread none of them is confirmed. A sheet with no
    sums on it changes nothing, and it is still asked for again."""
    if not withheld:
        return report
    if unseen_money:
        retake = ", ".join(dict.fromkeys(_paper(d) for d in unseen_money if d not in kept))
        chosen = ", ".join(dict.fromkeys(_paper(d) for d in unseen_money if d in kept))
        why = "; ".join(x for x in (f"{retake} was not sent, and what it prints could change this: take a new photo of it" if retake else "",
                                    f"{chosen} stayed on your computer by your choice, and what it prints could change this" if chosen else "") if x)
        for f in report.findings:
            if f.amount is not None or f.kind == checks.Kind.F2:
                checks.doubt(f, why)
        report = checks.split_borderline(report)
    return report.model_copy(update={"not_sent": list(dict.fromkeys(withheld))})


def pages_maybe_unread(case: Case, report: checks.Report, withheld: list[str] = ()) -> checks.Report:
    """BillRadar does not guess: a page is called missing only when no sheet that could be it went unread. An unread sheet
    could be it when nothing on it says otherwise: same office or none read, a document of the same kind or none read,
    the same page count and a missing page number, or no page mark read. A sheet kept back was not read at all. Nor is a
    page called missing when the page mark is on a sheet not read in full."""
    from billradar import ledger, sheet_checks
    changed = False
    for f in report.findings:
        if f.kind != checks.Kind.P1:
            continue
        ids = {e.doc_id for e in f.evidence}
        run = [d for d in case.documents if d.doc_id in ids]
        mine = {d.doc_id for d in run}
        missing = {int(x) for x in f.math.get("missing", "").split(",") if x}
        total = int(f.math.get("page_count") or 0)
        maybe = [d.doc_id for d in case.documents if d.doc_id not in mine and (d.unreadable or d.doubts)
                 and all(ledger._same_office(d, r) for r in run if r.kind != DocKind.EOB) and sheet_checks._fits(run, d)
                 and (d.page_count in (None, total)) and (d.page_no is None or d.page_no in missing)]
        maybe += [w for w in withheld if w not in mine and w not in maybe]
        maybe += [d.doc_id for d in run if d.unreadable or d.doubts]  # the page mark itself rests on a sheet not read in full
        if maybe:
            checks.doubt(f, f"{', '.join(_paper(x) for x in maybe)} could not be read, and it may be the missing page: check it")
            changed = True
    return checks.split_borderline(report) if changed else report


def device_confirms(case: Case, report: checks.Report, printed: dict[str, list]) -> checks.Report:
    """The last word on a confirmed sum. Two reads can agree on a wrong number, so every number a sum stands on must be
    read by this device, on that paper, where the paper prints it. What it cannot find goes to "check it", without a sum."""
    for f in report.findings:
        if f.amount is None:
            continue
        unseen = [s for s in f.trace if not table_rows.confirms(case.doc(s.doc_id), s, printed.get(s.doc_id, []))]
        if unseen or not f.trace:
            where = ", ".join(sorted({s.doc_id for s in unseen}))
            checks.doubt(f, f"{where or 'the papers'}: this device could not find the same number there: take a new photo of it")
    return checks.split_borderline(report)


def unreadable_sheets(docs: list, sent: list[str] = (), report: checks.Report | None = None) -> list[str]:
    """Sheets to photograph again: the reader could not read them, read text that is no amount, or left them out; a bill
    whose date the application window needs."""
    have = {d.doc_id for d in docs}
    out = [d.doc_id for d in docs if d.unreadable or d.doubts] + [s for s in sent if s not in have]
    for f in (report.findings + report.worth_asking) if report else ():
        out += [x for x in f.math.get("retake", "").split(",") if x and x not in out]
    return out


@dataclass
class Covered:
    name: str  # "table-1.jpg", "01-statement.pdf page 2"
    image: object  # PIL image, covered
    blocked: str = ""  # why it would not be sent: the kinds of what is still readable, never the values


def cover_only(photos: list[tuple[str, bytes]], files: list[tuple[str, bytes]], profile: Profile) -> list[Covered]:
    """Private mode's covering alone, on this device, with no model call: every photo whole and every PDF page,
    covered and run through the same leak gate the sheets pass before they are sent. For a person to look at
    their own papers covered before trusting the app with them (`billradar cover`)."""
    vault = _vault(profile)
    out: list[Covered] = []
    for name, raw in files:  # the files' own text first, as in run(): their values are covered on the photos too
        try:
            pdfpages.learn(vault, raw)
        except pdfpages.RenderError as exc:
            out.append(Covered(name, None, f"not read: {exc}"))
    images = [(name, sam.load_photo(raw)) for name, raw in photos]
    for name, raw in files:
        try:
            images += [(f"{name} page {k}", page) for k, page in enumerate(pdfpages.render(raw), start=1)]
        except pdfpages.RenderError:
            continue  # already reported above
    for _, img in images:  # every value on every paper first, as run() learns every cut sheet before checking one
        redact.learn(img, vault)
    out += [_gated(name, redact.redact(img, vault).image, vault, img) for name, img in images]
    return out


def _gated(name: str, img, vault: redact.Vault, page) -> Covered:
    try:
        _readable(page, name)
        return Covered(name, _no_leaks(img, vault, name))
    except Unsendable:
        return Covered(name, img, "too soft to read: take a new photo")
    except RealDataGate:
        left = redact.leaks(img, vault.secrets, vault.units, vault.name_words)
        return Covered(name, img, ", ".join(sorted({s.kind for s in left})) or "still readable")


SERVICE_CODE = re.compile(r"(?<![\d.,$])(\d{5}|0\d{3})(?![\d.,])")
MONEY_ON_ROW = re.compile(r"\$\s?\d")
BALANCE_WORDS = re.compile(r"(?i)balance|amount due|you owe|total due|please pay")
SECOND_LOOKS = 4  # at most this many sheets are read again alone, per case


def _rows(lines) -> list[str]:
    """OCR boxes joined into printed rows, left to right ("01960" + "$4,944.00" + "$196.82")."""
    rows: list[list] = []
    for line in sorted(lines, key=lambda l: (float(l.box[:, 1].min()), float(l.box[:, 0].min()))):
        row = next((r for r in rows if redact._same_row(r[0], line)), None)
        (row.append(line) if row is not None else rows.append([line]))
    return [" ".join(l.text for l in sorted(r, key=lambda l: float(l.box[:, 0].min()))) for r in rows]


def _missed(doc, lines) -> str:
    """What the device sees on a sheet that its reading left out, in words; "" when nothing."""
    from collections import Counter
    rows = _rows(lines)
    seen = Counter(c for row in rows if MONEY_ON_ROW.search(row) for c in set(SERVICE_CODE.findall(row)))
    read = Counter(ln.code.strip() for ln in doc.lines if ln.code)
    short = [f"{code} {n} times, read {read.get(code, 0)}" for code, n in seen.items() if n > read.get(code, 0)
             and (read.get(code, 0) or n >= 2)]
    if short:
        return "the sheet prints " + "; ".join(short)
    if doc.kind == DocKind.EOB:  # the share is printed on the code's row and the reading left it out on every line
        shared = {c for row in rows if len(MONEY_ON_ROW.findall(row)) >= 2 for c in set(SERVICE_CODE.findall(row))}
        lost = sorted(c for c in shared if read.get(c) and all(
            ln.patient_responsibility is None for ln in doc.lines if ln.code.strip() == c))
        if lost:
            return "the sheet prints your share for " + ", ".join(lost) + ", the reading has none"
    if doc.patient_balance is None and doc.amount_due_coupon is None and any(
            BALANCE_WORDS.search(row) and MONEY_ON_ROW.search(row) for row in rows):
        return "the sheet prints a balance, the reading has none"
    return ""


PAYABLE_TO = re.compile(r"(?i)make\s*checks?\s*payable\s*to\s*:?\s*(.*)")


def _payee(lines) -> str:
    """'MAKE CHECK PAYABLE TO : 300_Women First OB/GYN Care, LLC' -> the office the bill is from, read on this
    device; "" when the payee is printed apart from the words or not at all."""
    rows = _rows(lines)
    for i, row in enumerate(rows):
        m = PAYABLE_TO.search(row)
        if not m or re.search(r"(?i)mail\s*to", m.group(0)):
            continue
        raw = m.group(1)
        if not re.search(r"[A-Za-z]{3}", raw) and i + 1 < len(rows):  # the name printed on the line under the heading
            raw = redact.GLUED_TOKEN.sub(" ", rows[i + 1])
        if re.search(r"[A-Za-z]{3}", raw):
            name = re.sub(r"^[0-9O]{2,4}[_\s]+", "", raw.strip(" :"))  # "300_" is the office's billing code
            name = re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", name)  # OCR ran the words together
            return re.sub(r"\s*,\s*", ", ", name)
    return ""


OFFICE_WORDS = re.compile(r"(?i)\b(?:LLC|P\.?A|M\.?D|Inc|Group|Pediatrics|Physicians?|Associates|Clinic)\b")


def _office_name(lines) -> str:
    """A bill the reader left without a name: the office printed on it ("Little Harbor Pediatrics - PA"), the first
    line with an office's word and no digits."""
    for row in _rows(lines):
        name = redact.GLUED_TOKEN.sub(" ", row).strip(" -:")
        words = re.findall(r"[A-Za-z]{2,}", name)
        if OFFICE_WORDS.search(name) and not re.search(r"\d", name) and 2 <= len(words) <= 6:
            return re.sub(r"\s*-\s*", " - ", name)
    return ""


def _office_from_coupon(docs: list, sheets: list, letterhead: str, problems: list[str]) -> list:
    """A doctor's statement that names the hospital as the place of service ("Seaside Regional Hospital (IP)")
    while its coupon says whom to pay: the bill is from the payee."""
    from billradar.checks import _name_words
    if not letterhead:
        return docs
    home = _name_words(letterhead)
    images = {s.doc_id: s.image for s in sheets}
    out = []
    for d in docs:
        if d.kind != DocKind.EOB and d.doc_id in images and (not d.provider or home & _name_words(d.provider)):
            lines = redact.ocr(images[d.doc_id])
            payee = _payee(lines) or (_office_name(lines) if not d.provider else "")
            if payee and _name_words(payee) and not (home & _name_words(payee)):
                problems.append(f"{d.doc_id}: billed by {payee} (the coupon's payee, read on this device), not "
                                f"{d.provider or 'an unnamed office'}")
                d = d.model_copy(update={"provider": payee})
        out.append(d)
    return out


def _second_look(client, docs: list, sheets: list, problems: list[str]) -> list:
    """The reader's answer checked against the sheet on this device (OCR of the very image it got): a line read
    once that is printed twice, or a balance it left out. Such a sheet is read again on its own and the new
    reading is kept when it no longer misses it. Never more than SECOND_LOOKS sheets."""
    by_id = {d.doc_id: i for i, d in enumerate(docs)}
    looks = 0
    for s in sheets:
        if s.doc_id not in by_id or looks >= SECOND_LOOKS:
            continue
        lines = redact.ocr(s.image)
        why = _missed(docs[by_id[s.doc_id]], lines)
        if not why:
            continue
        looks += 1
        try:
            again = reader.read_case(client, [(s.doc_id, _jpeg(s.image))], [])
        except MetaAPIError as exc:
            problems.append(f"{s.doc_id}: {why}; reading it again did not run: {exc}")
            docs[by_id[s.doc_id]].doubts.append(f"{s.doc_id}: {why}")
            continue
        new = next((d for d in again.documents if d.doc_id == s.doc_id), None)
        if new is not None and not _missed(new, lines):  # what the reads could not settle stays on the sheet
            docs[by_id[s.doc_id]] = new.model_copy(update={"doubts": docs[by_id[s.doc_id]].doubts + new.doubts})
            problems.append(f"{s.doc_id}: read again on its own: {why}")
        else:
            problems.append(f"{s.doc_id}: {why}; reading it again on its own did not fix it")
    return docs


VISIT_RX = re.compile(r"(?i)(?:visit|date of service|service date)\s*(?:on|:)?\s*([A-Z][a-z]{2,8}\.? \d{1,2}, \d{4}|\d{1,2}/\d{1,2}/\d{4})")


VISIT_WORDS = re.compile(r"(?i)visit\s*on|date of service|service date")


def _visit_date_in(text: str):
    """'[PATIENT_1]'svisitonFebruary11,2025' -> 2025-02-11 (OCR runs the words together)."""
    from datetime import datetime
    t = re.sub(r",\s*", ", ", re.sub(r"([A-Za-z])(\d)", r"\1 \2", text))
    out = set()
    for m in VISIT_RX.finditer(t):
        for fmt in ("%B %d, %Y", "%b %d, %Y", "%b. %d, %Y", "%m/%d/%Y"):
            try:
                out.add(datetime.strptime(m.group(1), fmt).date())
                break
            except ValueError:
                continue
    return out


def _visit_dates(docs: list, sheets: list, problems: list[str]) -> list:
    """A bill that prints one visit in its heading ("Daniela's visit on February 11, 2025") and lines without a
    date of their own: the lines get that date. Read on this device by OCR from the very image the reader got,
    never guessed; with two visit dates on the sheet nothing is filled."""
    images = {s.doc_id: s.image for s in sheets}
    out = []
    for d in docs:
        undated = [ln for ln in d.lines if not ln.service_date and ln.code]
        if not undated or d.doc_id not in images or any(ln.service_date for ln in d.lines) or d.service_from:
            out.append(d)
            continue
        found, said = set(), 0
        for line in redact.ocr(images[d.doc_id]):
            found |= _visit_date_in(line.text)
            said += len(VISIT_WORDS.findall(line.text))
        if said != 1 or len(found) != 1:  # one visit printed and read whole, or no date at all
            out.append(d)
            continue
        day = found.pop()
        problems.append(f"{d.doc_id}: date of service {day.isoformat()} from the sheet's heading, read on this device")
        out.append(d.model_copy(update={"lines": [ln.model_copy(update={"service_date": day}) if ln in undated else ln
                                                  for ln in d.lines]}))
    return out


def _cut(photo, sheet):
    """The same sheet, same corners, from another copy of the photo (the covering does not move pixels)."""
    import numpy as np
    from PIL import Image
    if sheet.corners:
        return Image.fromarray(sam.straighten(np.array(photo), np.array(sheet.corners, dtype=np.float32)))
    return photo.crop(tuple(int(v) for v in sheet.box))


def _previews(files: list[tuple[str, bytes]]) -> dict[str, bytes]:
    """Page 1 of each PDF, small, for the documents column. Rendered here and never sent; a file that does not
    render just gets no picture."""
    out = {}
    for i, (_, raw) in enumerate(files, start=1):
        if not raw.startswith(b"%PDF"):
            continue
        try:
            page = pdfpages.render(raw, dpi=50)[0]
        except (pdfpages.RenderError, IndexError):
            continue
        page.thumbnail((420, 560))
        out[f"D{i}"] = _jpeg(page.convert("RGB"))
    return out


def _what_was_sent(to_sam, sheets: list[sam.Sheet], models: dict[str, str] | None = None, per_row: int = 3):
    """One picture of everything that left for one photo: the blurred table SAM got, then each sheet as the reader got it."""
    from PIL import Image, ImageDraw
    models = models or {"sheets": "SAM 3.1", "read": "Muse Spark"}
    captions = [f"to {_short(models['sheets'])}, blurred"] + [f"to {_short(models['read'])}: sheet {s.doc_id[1:]}" for s in sheets]
    pictures = [to_sam] + [pdfpages.to_paper(s.image) for s in sheets]
    across, down = 640 + 28, 520 + 40 + 28  # one cell with its gap: a picture, its caption above
    canvas = Image.new("RGB", (per_row * across + 28, ((len(pictures) + per_row - 1) // per_row) * down + 28), pdfpages.CREAM)
    pen, face = ImageDraw.Draw(canvas), redact._font(26)
    for n, (caption, picture) in enumerate(zip(captions, pictures)):
        x, y = 28 + n % per_row * across, 28 + n // per_row * down
        pen.text((x, y), caption, fill=(30, 42, 46), font=face)
        tile = picture.copy()  # the originals stay as they are
        tile.thumbnail((640, 520))
        pdfpages.paste_paper(canvas, tile, x, y + 40)
    return canvas


def _short(model: str) -> str:
    """Screen label of a model id: sam-3.1 -> SAM 3.1, muse-spark-1.3 -> Muse Spark."""
    return {"sam-3.1": "SAM 3.1", "muse-spark-1.3": "Muse Spark"}.get(model, model.split("/")[-1])


def _vault(profile: Profile) -> redact.Vault:
    """The case's one vault: what the family typed (never to leave) and the people's tokens, fixed up front."""
    home = profile.local

    def kind_of(key: str) -> str:  # "ACCT_1" is an account, "MEMBER_7" a member id, "P3" is its own kind
        return "ACCT" if key.startswith("ACCT") else key.partition("_")[0]

    typed = [("ADDR", home.street), ("PHONE", home.phone),
             *(("ADDR", line) for line in redact.city_line(home.city, home.state, home.zip)),
             *((kind_of(key), value) for key, value in home.tokens.items())]
    named = {("PATIENT", p.name): "[" + p.token + "]" for p in profile.people if p.name}
    return redact.Vault(known=[pair for pair in typed if pair[1] != ""], seed=named)


def _numbers_kept(original, covered, doc_id: str, lost: dict[str, list[str]]):
    """A sum that closing took: the sheet still goes, and gives no confirmed sum."""
    if gone := redact.amounts_gone(original, covered):
        lost.setdefault(doc_id, []).extend(gone)
    return covered


def _readable(img, doc_id: str) -> None:
    if redact.too_soft(img):
        raise Unsendable(f"sheet {doc_id}: too soft for this device to read, so nothing proves it is covered; not sending")


def _no_leaks(img, vault: redact.Vault, doc_id: str):
    """Every sheet is read back on this computer before it may leave."""
    _readable(img, doc_id)
    left = redact.leaks(img, vault.secrets, vault.units, vault.name_words)
    if left:
        kinds = ", ".join(sorted({s.kind for s in left}))
        raise RealDataGate(f"sheet {doc_id}: {len(left)} private value(s) still readable after covering ({kinds}); not sending")
    return img


SECOND_READ = "BILLRADAR_SECOND_READ"


def second_read_on(client) -> bool:
    """Every live case is read twice. "0" switches that off; a replay has it only when its run was recorded with it ("1")."""
    flag = os.environ.get(SECOND_READ, "")
    return flag == "1" or (client.live and flag != "0")


WONDER_REVIEW = "BILLRADAR_WONDER_REVIEW"


def review_on(client) -> bool:
    """Muse Wonder reads every live case before it is shown. "0" switches that off; a replay has it only when the run
    it replays was recorded with it ("1")."""
    flag = os.environ.get(WONDER_REVIEW, "")
    return flag == "1" or (client.live and flag != "0")


def check_and_hold(case: Case, report: checks.Report, client: MetaClient | None = None
                   ) -> tuple[checks.Report, verifier.Verdict]:
    """The last stop before the screen. A checker that only reads goes over the findings and the letters; a finding it
    rejects is not shown (it goes to `held_back`), the others get a confidence. Amounts and titles are never changed."""
    letters = writer.all_letters(case, report)  # from the report as it came in
    verdict = _second_opinion(client, case, report, letters, verifier.verify(case, report, letters))
    names = verifier.subjects(report)  # numbered over every finding, so holding one back moves no other's number
    objections = {id(f): verdict.errors_for(names[id(f)]) for f in report.findings}
    kept = report.model_copy(update=dict(
        findings=[f for f in report.findings if not objections[id(f)]],
        held_back=[*report.held_back, *(_held(f, objections[id(f)]) for f in report.findings if objections[id(f)])]))
    return verifier.grade(case, kept, verdict, names), verdict


def _second_opinion(client, case: Case, report: checks.Report, letters: list, verdict: verifier.Verdict) -> verifier.Verdict:
    """The model's own read of the findings, added as notes. When it cannot run, the code's verdict stands and says so."""
    if client is None or not review_on(client):
        return verdict
    try:
        return verifier.model_review(client, case, report, letters, verdict)
    except MetaAPIError as exc:
        verdict.issues.append(verifier.Issue("model review", "note", f"{verifier.checker_name(client)} review did not run: {exc}"))
        return verdict


def _held(finding: checks.Finding, objections: list) -> checks.Finding:
    """The finding as kept back: nothing but its text changes, and the text says why."""
    why = "; ".join(o.what for o in objections)
    return finding.model_copy(update={"detail": f"{finding.detail} [held back by the checker: {why}]"})


def _checker(v: verifier.Verdict) -> dict:
    """`review`: how the second model's own verdicts add up, for the screen ("7 confirmed, 1 flagged, 2 could not check")."""
    return {"checked": v.checked, "ok": v.ok, "issues": [i.__dict__ for i in v.issues],
            "review": dict(Counter(str(i.get("verdict")) for i in v.model_notes))}


def save(run_: CaseRun, out: Path) -> None:
    """Write a run where the screens, the history, the marks, the letters and the voice read it. Old files stay."""
    import io

    def paper(img) -> bytes:
        buf = io.BytesIO()
        pdfpages.to_paper(img).convert("RGB").save(buf, format="JPEG", quality=88)
        return buf.getvalue()

    def text(value: str) -> bytes:
        return value.encode("utf-8")

    checker = None if run_.verdict is None else _checker(run_.verdict)
    summary = {"problems": run_.problems, "timings": run_.timings, "replayed": run_.replayed, "redacted": run_.redacted,
               "provider": run_.provider, "unreadable": run_.unreadable, "checker": checker}
    written: dict[str, bytes] = {"case.json": text(run_.case.model_dump_json(indent=2)),
                                 "report.json": text(run_.report.model_dump_json(indent=2)),
                                 "problems.json": text(json.dumps(summary, indent=2))}
    written |= {name: text(json.dumps(extra, indent=2))
                for name, extra in (("receipt.json", run_.receipt), ("policy-finder.json", run_.found_policy)) if extra}
    written |= {f"overlay-{i}.jpg": raw for i, raw in enumerate(run_.overlays, start=1)}
    written |= {f"sent-{i}.jpg": raw for i, raw in enumerate(run_.sent_views, start=1)}
    written |= {f"files/{doc_id}.jpg": raw for doc_id, raw in run_.file_previews.items()}
    # the screen shows a sheet as photographed (in private mode that picture never left); a sent sheet is the closed one
    written |= {f"sheets/{s.doc_id}.jpg": paper(run_.originals.get(s.doc_id, s.image)) for s in run_.sheets}
    if run_.originals:
        written["sheets/" + highlight.PRINTED] = text(json.dumps({sid: redact.stored_lines(img) for sid, img in run_.originals.items()}))
        written |= {f"sent-sheets/{s.doc_id}.jpg": paper(s.image) for s in run_.sheets}
        (out / "sent-sheets").mkdir(parents=True, exist_ok=True)
    (out / "sheets").mkdir(parents=True, exist_ok=True)
    for name, raw in written.items():
        (out / name).parent.mkdir(parents=True, exist_ok=True)
        (out / name).write_bytes(raw)
