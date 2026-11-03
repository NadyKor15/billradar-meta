"""Web app for BillRadar: case screens, letters, calendar files, forms and the live helpers, served with FastAPI."""

from __future__ import annotations

import asyncio
import contextlib
import functools
import hashlib
import json
import os
import re
import queue
import secrets
import threading
import time
import wave
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import date, datetime, timezone
from decimal import ROUND_DOWN, Decimal
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

from billradar import links, meta_client
from billradar import days, policy_finder
from billradar import (agent_entry, appeal, ask, bill_picture, call_assist, callprep, checks, context, example, forms, history, i18n, laws,
                       pipeline, plans, policy, portal_job, providers, report_pdf, view, voice, web_answer, writer)
from billradar.case import Case, Person, Profile, Role
from billradar.receipt import STEP as RECEIPT_STEP
from billradar import highlight, pdfpages
from billradar import video as clips
from billradar.meta_client import MetaAPIError, MetaClient, ReplayMissing, ReplayTransport, SpendCapReached, SpendLedger, asr_cost

WEB = Path(__file__).parent / "web"
RUNS = Path(__file__).resolve().parents[1] / "runs"
VOICE_SAMPLES = Path(__file__).parent / "voice_samples"
MAX_VOICE_BYTES = 5 * 1024 * 1024  # about two minutes of 16 kHz speech
LIMIT_TEXT = "Live runs are limited per hour here. The example case shows the whole path."
_live_hits: dict[str, deque] = defaultdict(deque)

# Entry for AI agents (MCP, A2A): mounted last, so every route below wins; its lifespan runs exactly once.
agent = agent_entry.app()


@asynccontextmanager
async def lifespan(_app):
    async with agent.app.router.lifespan_context(agent.app):
        yield


app = FastAPI(title="BillRadar", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=WEB / "static"), name="static")
templates = Jinja2Templates(directory=WEB / "templates")
templates.env.filters["quotes"] = lambda t: view.mark_quotes(t)
templates.env.filters["letter_name"] = lambda k: view.letter_name(k)


@app.exception_handler(SpendCapReached)
async def _spend_cap(_request: Request, _exc: SpendCapReached):
    return JSONResponse({"error": "The live budget of this demo is used up. The example case still works."}, status_code=503)


def _allow_live(request: Request) -> bool:
    """A live model run costs money: at most BILLRADAR_LIVE_PER_HOUR per address (unset or 0: no limit).
    Replays are free and never limited. Behind a proxy (BILLRADAR_TRUST_PROXY=1) the address is X-Forwarded-For."""
    limit = int(os.environ.get("BILLRADAR_LIVE_PER_HOUR", "0") or 0)
    if not limit:
        return True
    ip = request.client.host if request.client else "?"
    if os.environ.get("BILLRADAR_TRUST_PROXY") == "1" and request.headers.get("x-forwarded-for"):
        ip = request.headers["x-forwarded-for"].split(",")[0].strip()
    now, q = time.monotonic(), _live_hits[ip]
    while q and now - q[0] > 3600:
        q.popleft()
    if len(q) >= limit:
        return False
    q.append(now)
    return True


SAMPLE_CASES = {example.EXAMPLE_ID, example.PRIVATE_ID}  # the recorded question and note were made for the first example


def _sample_client() -> MetaClient:
    return MetaClient(transport=ReplayTransport(), record_to=None, journal=None)


@functools.lru_cache(maxsize=16)
def _sample_answers(case_id: str) -> bool:
    """The recorded question is offered only where its words and its answer are both on the recording. No model is called."""
    wav = VOICE_SAMPLES / "ask.wav"
    if case_id not in SAMPLE_CASES or not wav.exists():
        return False
    _, case, report = _load(case_id)
    client = _sample_client()
    try:
        heard = voice.transcribe(client, case, wav.read_bytes(), "en")
        return not ask.answer(client, case, report, heard.text[:500]).refused
    except ReplayMissing:
        return False


@functools.lru_cache(maxsize=16)
def _sample_note_ready(case_id: str, to: str) -> bool:
    """The recorded note after a call, offered only where its words and what was read from them are on the recording."""
    wav = VOICE_SAMPLES / "note.wav"
    if case_id not in SAMPLE_CASES or not wav.exists():
        return False
    _, case, report = _load(case_id)
    client = _sample_client()
    try:
        heard = voice.transcribe(client, case, wav.read_bytes(), "en")
        return bool(voice.read_note(client, case, heard, who=callprep.build(case, report, to).who).paragraph(case, "en"))
    except (ReplayMissing, ValueError, MetaAPIError):
        return False


def voice_context(case_id: str | None = None) -> dict:
    """What the voice helper can do on this page. On a public link a stranger's voice goes to Meta only when the
    owner switched that on (BILLRADAR_PUBLIC_VOICE=1); a recorded sample is offered where it works from start to end."""
    live = bool(providers.make_client().live) and (not history.public() or os.environ.get("BILLRADAR_PUBLIC_VOICE") == "1")
    sample = lambda name: f"/voice/sample/{name}.wav" if (VOICE_SAMPLES / f"{name}.wav").exists() else None  # noqa: E731
    return {"live": live, "langs": voice.LANGUAGES, "sample_intake": sample("intake"),
            "sample_ask": sample("ask") if case_id and _sample_answers(case_id) else None,
            "sample_call": sample("call")}


def _run_dir(case_id: str) -> Path:
    if case_id in example.READ_ONLY:
        example.ensure(RUNS)
    d = history.run_dir(RUNS, case_id)
    if d is None:
        raise HTTPException(404)
    return d


def _meta(d: Path) -> dict:
    return json.loads((d / "problems.json").read_text()) if (d / "problems.json").exists() else {}


def _sent(case_id: str) -> list[str]:
    """What left the device, as the models got it. Only runs in private mode have it."""
    d = history.run_dir(RUNS, case_id)
    return [f"/cases/{case_id}/overlay/{p.name}" for p in sorted(d.glob("sent-*.jpg"))] if d else []


STATIC = os.environ.get("BILLRADAR_STATIC") == "1"
CSS_V = hashlib.sha256((WEB / "static" / "app.css").read_bytes()).hexdigest()[:10]  # a new stylesheet gets a new address


def asset(path: str) -> str:
    """/static/brand/x.png -> /static/brand/x.png?v=<hash>: a changed picture gets a new address (no stale cache)."""
    p = WEB / path.lstrip("/")
    return f"{path}?v={hashlib.sha256(p.read_bytes()).hexdigest()[:10]}" if p.exists() else path


templates.env.globals["asset"] = asset
templates.env.globals["repo_tree"] = links.tree()  # the repo link on every page, from one constant
templates.env.globals["repo_blob"] = links.blob
REPO_URL = links.tree()


def _page(request: Request, name: str, **ctx):
    ctx.setdefault("nav", "")
    ctx.setdefault("mdl", providers.labels())
    ctx.setdefault("public", history.public())
    ctx.setdefault("voice", voice_context(ctx.get("case_id")))
    ctx.setdefault("static", STATIC)  # a read-only copy of the example pages (scripts/export_static.py)
    ctx.setdefault("css_v", CSS_V)
    status_code = ctx.pop("status_code", 200)
    return templates.TemplateResponse(request, name, ctx, status_code=status_code)


@app.exception_handler(StarletteHTTPException)
async def not_found_page(request: Request, exc: StarletteHTTPException):
    """A person who opens a wrong address gets a page with the header and a way back; everything else stays JSON."""
    if exc.status_code == 404 and "text/html" in request.headers.get("accept", ""):
        return _page(request, "not_found.html", status_code=404)
    return await http_exception_handler(request, exc)


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    example.ensure(RUNS)
    sheets = [f"/cases/{example.EXAMPLE_ID}/sheet/{s}.jpg" for s in ("S4", "S1", "S12")]
    d, case, report = _load(example.EXAMPLE_ID)
    letter = next((x for x in writer.all_letters(case, report) if x.kind == "itemized"), None)
    story = view.story(case, report, letter, [f"/cases/{example.EXAMPLE_ID}/sheet/S{i}.jpg" for i in (1, 2, 4, 5, 8)])  # the five fullest sheets
    found = WEB / "static" / "story" / "found.json"  # scripts/story_assets.py
    if found.exists():
        story["found"] = view.story_found(json.loads(found.read_text()), lambda s: f"/cases/{example.EXAMPLE_ID}/sheet/{s}.jpg")
    receipt = d / "receipt.json"
    if receipt.exists():
        r = json.loads(receipt.read_text())
        story["receipt"] = {"calls": len(r["rows"]), "usd": round(r["total_usd"], 3), "rows": r["rows"]}
    return _page(request, "home.html", nav="home", sheets=sheets, steps=view.steps_static(), story=story)


def _upload_page(request: Request, status: int = 200, error: str = "", chosen: list[str] | None = None):
    rules = {c.id: context.rules_on([c.id]) for c in context.CHIPS}
    r = _page(request, "upload.html", nav="upload", error=error, live=providers.make_client().live, chips=context.CHIPS,
              chosen=context.valid(chosen or []), rules=rules,
              policies=[policy.load(p) for p in policy.available() if policy.load(p).tiers])
    r.status_code = status
    return r


@app.get("/upload", response_class=HTMLResponse)
def upload(request: Request, ctx: list[str] = Query(default=[], alias="context")):
    return _upload_page(request, chosen=ctx)


@app.get("/how", response_class=HTMLResponse)
def how(request: Request):
    example.ensure(RUNS)
    ex = f"/cases/{example.EXAMPLE_ID}"
    art = {"photo": f"{ex}/overlay/overlay-1.jpg", "sheets": [f"{ex}/sheet/S1.jpg", f"{ex}/sheet/S2.jpg"],
           "check": f"{ex}/sheet/S10.jpg", "covered": f"/cases/{example.PRIVATE_ID}/sheet/S4.jpg"}
    return _page(request, "how.html", nav="how", models=view.model_status(), art=art)


# The journal's own values, as written, under the step name the receipt uses. Anything else in a line stays out, so no
# body, header or key can reach this page. A "sent" line and its answer are one call, matched on the request's hash.
CALL_FIELDS = ("at", "event", "status", "label", "model", "live", "seconds", "response_id", "answer_start", "usage", "usd")


def _calls() -> list[dict]:
    """Every model call in the journal, oldest first. Only on this machine: a public copy has no such page."""
    if history.public() or STATIC:
        raise HTTPException(404)
    path = meta_client.JOURNAL
    rows: list[dict] = []
    waiting: dict[str, dict] = {}
    for line in path.read_text().splitlines() if path.exists() else []:
        r = json.loads(line) if line.strip() else {}
        if not r.get("model"):
            continue
        row = waiting.pop(r.get("key"), None) if r.get("event") != "sent" else None
        if row is None:
            row = {}
            rows.append(row)
        row.update({k: r[k] for k in CALL_FIELDS if k in r})
        row["step"] = RECEIPT_STEP.get(r.get("label", ""), r.get("label", ""))
        row["state"] = r.get("status") or ("sent" if r.get("event") == "sent" else "answered")
        if r.get("event") == "sent":  # written only when a request really leaves (meta_client._going_out)
            row["live"] = True
            waiting[r.get("key")] = row
    return rows


@app.get("/calls", response_class=HTMLResponse)
def calls_page(request: Request, all: int = 0):
    return _page(request, "calls.html", start=0 if all else len(_calls()))


@app.get("/calls.json")
def calls_json(after: int = 0):
    rows = _calls()
    return {"seen": len(rows), "rows": rows[max(after, 0):]}


@app.get("/privacy", response_class=HTMLResponse)
def privacy(request: Request):
    return _page(request, "privacy.html", nav="")


@app.get("/safe", response_class=HTMLResponse)
def safe(request: Request, case: str = ""):
    example.ensure(RUNS)
    own = history.run_dir(RUNS, case) if case else None
    sent = (_sent(case) if own else []) or _sent(example.PRIVATE_ID)
    deletable = bool(own) and history.may_delete(own, request.cookies.get(history.cookie_name(case)))
    pair_case = case if own and _sent(case) else example.PRIVATE_ID
    d = history.run_dir(RUNS, pair_case)
    pair = (f"/cases/{pair_case}/sheet/S1.jpg", f"/cases/{pair_case}/sent-sheet/S1.jpg") \
        if d and (d / "sent-sheets" / "S1.jpg").exists() else None
    return _page(request, "safe.html", nav="safe", sent=sent, sent_is_example=not (own and _sent(case)),
                 case_id=case if own else "", deletable=deletable, pair=pair)


@app.get("/agents", response_class=HTMLResponse)
def for_agents(request: Request):
    public = os.environ.get("BILLRADAR_PUBLIC_URL", "").rstrip("/")  # behind a proxy the request sees the inside address
    base = public or ("http://127.0.0.1:8000" if STATIC else str(request.base_url).rstrip("/"))  # the read-only copy has no server
    return _page(request, "agents.html", nav="agents", base=base, packs=sorted(
        p.name for p in (example.ROOT / "eval" / "packs" / "work").iterdir() if (p / "profile.json").exists()))


@app.get("/cases", response_class=HTMLResponse)
def all_cases(request: Request, deleted: str = ""):
    rows = [] if history.public() else history.list_runs(RUNS)
    waiting = [] if history.public() else history.list_waiting(RUNS)
    return _page(request, "cases.html", nav="cases", rows=rows, waiting=waiting, deleted=deleted)


@app.get("/cases/{case_id}/summary.json")
def case_summary(case_id: str):
    return history.summary(_run_dir(case_id)).to_dict()


@app.post("/cases/{case_id}/delete")
def delete_case(request: Request, case_id: str):
    d = history.waiting_dir(RUNS, case_id) or _run_dir(case_id)
    if not history.delete(RUNS, case_id, request.cookies.get(history.cookie_name(case_id))):
        raise HTTPException(403, "this case can only be deleted from the browser that made it")
    r = RedirectResponse(f"/cases?deleted={d.name}", status_code=303)
    r.delete_cookie(history.cookie_name(case_id), path=f"/cases/{case_id}")
    return r


def _upload_family(mother_name: str, baby_name: str) -> list[Person]:
    """The mother always; the baby only when a name was given. Tokens are what the models see in their place."""
    named = [("PATIENT_1", Role.MOTHER, mother_name), ("PATIENT_2", Role.NEWBORN, baby_name)]
    return [Person(token=token, role=role, name=name) for n, (token, role, name) in enumerate(named) if n == 0 or name]


def _upload_refusal(exc: Exception) -> tuple[int, str]:
    """Status and words for a run that stopped for a reason the family can act on."""
    if isinstance(exc, ReplayMissing):
        return 503, ("Checking new papers starts when the model calls are switched on. "
                     "Until then, the example case shows the whole path with sample papers.")
    if isinstance(exc, pipeline.RealDataGate):
        return 400, f"Not sent: {exc}."
    return 400, str(exc)


def _owned_redirect(case_id: str, token: str) -> RedirectResponse:
    """To the sheets of the new case, with the one-year cookie that says this browser made it."""
    reply = RedirectResponse(f"/cases/{case_id}/review", status_code=303)
    reply.set_cookie(history.cookie_name(case_id), token, path=f"/cases/{case_id}", httponly=True, samesite="strict",
                     secure=history.public(), max_age=60 * 60 * 24 * 365)
    return reply


async def _upload_bytes(upload: UploadFile | None) -> bytes | None:
    """An upload's content, or None for a form field that carried no file."""
    return await upload.read() if upload is not None and upload.filename else None


@app.post("/cases")
async def create_case(
    request: Request,
    photos: list[UploadFile] = File(default=[]),
    files: list[UploadFile] = File(default=[]),
    video: UploadFile | None = File(None),
    policy_id: str = Form(...),
    letterhead: str = Form(""),
    household_size: int = Form(...),
    annual_income: Decimal = Form(...),
    liquid_assets: Decimal | None = Form(None),
    insured: bool = Form(False),
    fictional: bool = Form(False),
    mother_name: str = Form(""),
    baby_name: str = Form(""),
    ctx: list[str] = Form(default=[], alias="context"),
):
    if history.public():  # nothing is read or started on the public copy
        raise HTTPException(403, "Uploading papers is off on this public copy. See the example case.")
    if policy_id not in policy.available():
        raise HTTPException(400, "unknown policy")
    profile = Profile(household_size=household_size, annual_income=annual_income, liquid_assets=liquid_assets,
                      insured=insured, people=_upload_family(mother_name, baby_name), context=context.valid(ctx))
    table_photos = [raw for raw in [await _upload_bytes(f) for f in photos] if raw is not None]
    pdfs = [(f.filename, raw) for f, raw in [(f, await _upload_bytes(f)) for f in files] if raw is not None]
    clip = await _upload_bytes(video)
    case_id = "c" + secrets.token_hex(5)
    client = providers.make_client()
    if client.live and not _allow_live(request):
        return _upload_page(request, 429, LIMIT_TEXT)
    try:  # private mode is not a choice of the form; the work runs in a thread so the page keeps answering
        prep = await asyncio.to_thread(pipeline.prepare, client, table_photos, pdfs, profile, fictional=fictional, private=True, video=clip)
    except (clips.VideoError, ReplayMissing, pipeline.RealDataGate) as refused:
        return _upload_page(request, *_upload_refusal(refused))
    prep.request = {"policy_id": policy_id, "letterhead": letterhead, "fictional": fictional, "today": date.today().isoformat()}
    folder = RUNS / case_id
    await asyncio.to_thread(pipeline.save_prepared, prep, folder)
    return _owned_redirect(case_id, history.issue_token(folder))


def _waiting(request: Request, case_id: str) -> Path:
    """The sheets of a case nobody has sent yet: as closely held as the case itself."""
    d = history.waiting_dir(RUNS, case_id)
    if d is None or not history.may_delete(d, request.cookies.get(history.cookie_name(case_id))):
        raise HTTPException(404)
    return d


def _sheet_card(doc_id: str, state: dict, kind: str) -> dict:
    n = doc_id[1:].split(".")
    label = f"Sheet {n[0]}" if doc_id[0] == "S" else f"File {n[0]}" + (f", page {n[1]}" if len(n) > 1 else "")
    return {"id": doc_id, "label": label, "kind": kind, "lost": bool(state["lost"].get(doc_id)), "original": doc_id in state["originals"]}


def _review_page(request: Request, case_id: str, d: Path, status_code: int = 200, error: str = ""):
    state = json.loads((d / pipeline.PREPARED / "state.json").read_text())
    cards = [_sheet_card(x["doc_id"], state, "send") for x in state["sheets"] + state["pages"]] + [_sheet_card(i, state, "not_sent") for i in state["withheld"]]
    cards.sort(key=lambda c: (c["id"][0] == "D", [int(x) for x in c["id"][1:].split(".")]))
    return _page(request, "review.html", nav="cases", case_id=case_id, cards=cards, to_send=sum(c["kind"] == "send" for c in cards),
                 not_sent=sum(c["kind"] == "not_sent" for c in cards), soft=[x["file"] for x in state["soft"]], pdf_pages=bool(state["pages"]),
                 second_look=pipeline.review_on(providers.make_client()), no_dock=True, error=error, status_code=status_code)


KEPT = "kept.json"  # sheets the person chose to keep here
REVIEW_IMAGES = {"sheet": (r"[SD]\d{1,3}(\.\d{1,3})?\.png", ("sheets", "pages")), "original": (r"S\d{1,3}\.png", ("originals",)), "blurred": (r"\d{1,3}\.png", ("soft",))}


@app.get("/cases/{case_id}/review/{what}/{name}")
def review_image(request: Request, case_id: str, what: str, name: str):
    """What only this computer shows: the sheets as closed and as photographed. Never kept by a browser cache."""
    if what not in REVIEW_IMAGES or not re.fullmatch(REVIEW_IMAGES[what][0], name):
        raise HTTPException(404)
    d = _waiting(request, case_id)
    for folder in REVIEW_IMAGES[what][1]:
        p = d / pipeline.PREPARED / folder / name
        if p.exists():
            return FileResponse(p, media_type="image/png", headers={"Cache-Control": "no-store"})
    raise HTTPException(404)


@app.get("/cases/{case_id}/review", response_class=HTMLResponse)
def review_screen(request: Request, case_id: str):
    done = history.run_dir(RUNS, case_id)
    if done is not None:  # sent already: a second look at this address lands on the case
        pipeline.drop_prepared(done)
        return RedirectResponse(f"/cases/{case_id}", status_code=303)
    return _review_page(request, case_id, _waiting(request, case_id))


def _stayed_here(prep: pipeline.Prepared, kept: set[str], d: Path) -> None:
    """The case page shows the sheets that did not leave as well, and says who decided that."""
    for sid, img in prep.originals.items():
        if not (d / "sheets" / f"{sid}.jpg").exists():
            pdfpages.to_paper(img).save(d / "sheets" / f"{sid}.jpg", quality=88)
    (d / KEPT).write_text(json.dumps(sorted(kept)))


_sending: set[str] = set()  # one press at a time: a second one would pay for the same reading twice


@app.post("/cases/{case_id}/send")
async def send_sheets(request: Request, case_id: str):
    """Only what the person let go, by name: a sheet with no answer in the form stays here."""
    if history.run_dir(RUNS, case_id) is not None:
        return RedirectResponse(f"/cases/{case_id}", status_code=303)
    d = _waiting(request, case_id)
    form = await request.form()
    if case_id in _sending:
        return _review_page(request, case_id, d, 409, "These sheets are being read already.")
    _sending.add(case_id)
    try:
        client = providers.make_client()
        prep = await asyncio.to_thread(pipeline.load_prepared, d)
        r = prep.request
        if client.live and not r["fictional"]:  # the same gate as before the sheets were closed
            return _review_page(request, case_id, d, 400, "Not sent: live model calls are allowed only on fictional papers.")
        if client.live and not _allow_live(request):
            return _review_page(request, case_id, d, 429, LIMIT_TEXT)
        approved = {doc_id for doc_id in prep.to_send if form.get(doc_id) == "send"}
        try:
            result = await asyncio.to_thread(pipeline.finish, client, prep, approved, r["policy_id"], r["letterhead"],
                                             date.fromisoformat(r["today"]), case_id)
        except ReplayMissing:
            return _review_page(request, case_id, d, 503, "Checking new papers starts when the model calls are switched on. Your sheets stay here.")
        except pipeline.RealDataGate as e:
            return _review_page(request, case_id, d, 400, f"Not sent: {e}.")
        result.case.demo = r["fictional"]
        await asyncio.to_thread(pipeline.save, result, d)
        await asyncio.to_thread(_stayed_here, prep, set(prep.to_send) - approved, d)
        await asyncio.to_thread(highlight.attach, client, result, d)
        pipeline.drop_prepared(d)
    finally:
        _sending.discard(case_id)
    return RedirectResponse(f"/cases/{case_id}", status_code=303)


def _sent_sheets(case_id: str) -> list[str]:
    """Private mode: each sheet as the model got it, covered, in sheet order."""
    d = history.run_dir(RUNS, case_id)
    files = sorted((d / "sent-sheets").glob("S*.jpg"), key=lambda p: int(p.stem[1:])) if d else []
    return [f"/cases/{case_id}/sent-sheet/{p.name}" for p in files]


def _receipt(d: Path) -> dict | None:
    p = d / "receipt.json"
    if not p.exists():
        return None
    r = json.loads(p.read_text())
    for row in r["rows"]:
        row["step"] = RECEIPT_STEP.get(row["step"], row["step"])
    r["replayed"] = r.get("replayed") or d.name in example.READ_ONLY  # an example is a recording, however it was made
    return r


def _load(case_id: str) -> tuple[Path, Case, checks.Report]:
    d = _run_dir(case_id)
    case = Case.model_validate_json((d / "case.json").read_text())
    report = checks.Report.model_validate_json((d / "report.json").read_text())
    case = case.model_copy(update={"today": _today(case_id, case)})
    return d, case, checks.window_today(case, report)


FORM_FOR_POLICY = {"memorial-2026-05": forms.fill_memorial}


def _picture_ready(case: Case, report: checks.Report) -> bool:
    """The bill picture is asked for only where it can come: from the model, or from its recording."""
    return case.demo and (providers.make_client().live or ReplayTransport().image_path(bill_picture.request(case, report)).exists())


def _case_page(request: Request, case_id: str, is_example: bool = False):
    d, case, report = _load(case_id)
    meta = _meta(d)
    overlays = [f"/cases/{case_id}/overlay/{p.name}" for p in sorted(d.glob("overlay-*.jpg"))]
    sheet_ids = sorted((p.stem for p in (d / "sheets").glob("S*.jpg")), key=lambda x: int(x[1:]))
    screen = view.build(case, report, overlays, meta.get("replayed", True), unreadable=meta.get("unreadable", []))
    sent = _sent(case_id)
    sent_from_example = False
    if case_id == example.EXAMPLE_ID:  # the same pack in private mode: the photos as they leave the device
        sent, sent_from_example = _sent(example.PRIVATE_ID), True
    return _page(
        request, "case.html", nav="cases", s=screen, case=case, case_id=case_id, report=report,
        board=view.board(case, report, meta, {m.index: f"/cases/{case_id}/marked/{m.index}.jpg" for m in highlight.load(d)}),
        steps=view.steps(case, meta, len(sheet_ids)),
        span=view.service_span(case), sheets=sheet_ids, letters=writer.all_letters(case, report),
        appeals=writer.appeal_letters(case), calls=callprep.all_sheets(case, report), langs=i18n.LANGS,
        laws=laws.for_case(case), chips=[context.chip(c) for c in context.valid(case.profile.context)],
        fap_policy_by=max((f.deadline for f in report.findings + report.worth_asking if f.kind.value == "F2" and f.deadline),
                          default=None),  # the hospital's own last day to apply, beside the federal minimum
        has_form=case.policy_id in FORM_FOR_POLICY, checker=meta.get("checker"), held=len(report.held_back),
        unreadable=meta.get("unreadable", []), not_sent=report.not_sent,
        doubted={d.doc_id for d in case.documents if d.doubts and not d.unreadable}, kept=json.loads((d / KEPT).read_text()) if (d / KEPT).exists() else [], deadlines_ics=f"/cases/{case_id}/deadlines.ics", picture=f"/cases/{case_id}/picture.png" if _picture_ready(case, report) else None,
        redaction=meta.get("redacted", False), sent=sent, sent_from_example=sent_from_example,
        receipt=_receipt(d), receipt_rows=view.receipt_rows(_receipt(d)),
        previews={p.stem for p in (d / "files").glob("D*.jpg")}, sent_sheets=_sent_sheets(
            example.PRIVATE_ID if sent_from_example else case_id),
        example=is_example, created=history.summary(d).created,
        created_on=case_day(case, history.summary(d).created, is_example),
        as_of=case.today,  # one date on the page: an example's own day, or the day it is opened
        amount=view.up_to(report.total_may_come_off),
        deletable=history.may_delete(d, request.cookies.get(history.cookie_name(case_id))),
        **_policy_block(d, case_id, is_example))


def case_day(case: Case, created: str, is_example: bool) -> str:
    """The date in the case history: an example lives on its own day, whatever day its files were written."""
    return (case.today if is_example else datetime.fromisoformat(created)).strftime("%b %-d, %Y")


def _policy_block(d: Path, case_id: str, is_example: bool) -> dict:
    """The case's policy_finder result (policy-finder.json), and where its "yes / type the site" forms post."""
    p = d / "policy-finder.json"
    found = json.loads(p.read_text()) if p.exists() and policy_finder.enabled() else None  # flag off: screen as before
    form = f"/cases/{case_id}/policy-finder" if found and not STATIC and not is_example else ""
    return {"found_policy": found, "pf_form": form}


@app.post("/cases/{case_id}/policy-finder")
def find_policy_for_case(request: Request, case_id: str, website: str = Form(""), place: str = Form(""),
                         state: str = Form(""), confirmed: str = Form("")):
    """The family answers "Is this your hospital?" or types the site / city or ZIP / state from the bill."""
    if not policy_finder.enabled() or case_id in example.READ_ONLY:
        raise HTTPException(404)
    d = _run_dir(case_id)
    origin = request.headers.get("origin")
    if origin and urlsplit(origin).netloc != request.url.netloc:  # a form posted from another site
        raise HTTPException(403)
    if not history.may_delete(d, request.cookies.get(history.cookie_name(case_id))):
        raise HTTPException(403)
    p = d / "policy-finder.json"
    old = json.loads(p.read_text()) if p.exists() else {}
    _, case, _ = _load(case_id)
    hint = policy_finder.hint_for(case) or policy_finder.Hint(name=old.get("hospital", ""))
    if not hint.name:
        raise HTTPException(400, "the bills name no hospital")
    place = " ".join(place.split())
    hint.website = website.strip()
    if place and place[0].isdigit():  # a ZIP replaces the city saved before, and the other way round
        hint.zip, hint.city = place, ""
    elif place:
        hint.city, hint.zip = place, ""
    else:
        hint.city, hint.zip = old.get("city", ""), old.get("zip", "")
    hint.state = state.strip() or old.get("state", "")
    try:
        hint = hint.clean()
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    found = policy_finder.find(hint, confirmed=confirmed == "1" and bool(hint.website)).to_dict()
    p.write_text(json.dumps(found, indent=2))
    return RedirectResponse(f"/cases/{case_id}#policy", status_code=303)


@app.get("/policy-finder", response_class=HTMLResponse)
def policy_finder_page(request: Request):
    return _page(request, "policy_finder.html", nav="how", **_recorded_policy_run())


@functools.cache
def _recorded_policy_run() -> dict:
    return policy_finder.replay_run()


@app.get("/cases/{case_id}", response_class=HTMLResponse)
def case_screen(request: Request, case_id: str):
    if history.waiting_dir(RUNS, case_id) is not None:
        return RedirectResponse(f"/cases/{case_id}/review", status_code=303)
    return _case_page(request, case_id, is_example=case_id in example.READ_ONLY)


@app.get("/example", response_class=HTMLResponse)
def example_case(request: Request):
    return _case_page(request, example.EXAMPLE_ID, is_example=True)


@app.get("/cases/{case_id}/sent-sheet/{name}")
def sent_sheet(case_id: str, name: str):
    if not re.fullmatch(r"S\d{1,3}\.jpg", name):
        raise HTTPException(404)
    p = _run_dir(case_id) / "sent-sheets" / name
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p, media_type="image/jpeg")


@app.get("/cases/{case_id}/file/{name}")
def file_preview(case_id: str, name: str):
    if not re.fullmatch(r"D\d{1,3}\.jpg", name):
        raise HTTPException(404)
    p = _run_dir(case_id) / "files" / name
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p, media_type="image/jpeg")


@app.get("/cases/{case_id}/sheet/{name}")
def sheet(case_id: str, name: str):
    if not re.fullmatch(r"S\d{1,3}\.jpg", name):
        raise HTTPException(404)
    p = _run_dir(case_id) / "sheets" / name
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p)


@app.get("/cases/{case_id}/marked/{name}")
def marked_sheet(case_id: str, name: str):
    if not re.fullmatch(r"\d{1,3}\.jpg", name):
        raise HTTPException(404)
    p = _run_dir(case_id) / "marked" / name
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p)


def _apply_title(report: checks.Report) -> str:
    return "Last day to apply for hospital financial assistance" + ("" if report.apply_by_sure else f", {days.CHECK_DATE}")


def case_dates(case: Case, report: checks.Report) -> list[tuple[date, str]]:
    """Every date the family has to act by, from the checked report."""
    dates = [(report.apply_by, _apply_title(report))] if report.apply_by else []
    dates += [(f.deadline, f.title) for f in report.findings + report.worth_asking if f.deadline and f.deadline != report.apply_by]
    return sorted(dict.fromkeys(x for x in dates if not days.passed(x[0], case.today)))  # a reminder for a day gone by helps no one


@app.get("/cases/{case_id}/deadlines.ics")
def deadlines(case_id: str):
    """All the dates of the case in one calendar file, one tap from the case screen."""
    d, case, report = _load(case_id)
    tracker = _tracker(d, case, report, _today(case_id, case))
    dates = case_dates(case, report) + [(it.appeal_by, f"Last day to appeal: {it.title}") for it in tracker.items.values()
                                        if it.appeal_by and not it.sent_on and not days.passed(it.appeal_by, case.today)]
    return Response(appeal.dates_ics(case_id, sorted(dict.fromkeys(dates)), sample=bool(case.demo)), media_type="text/calendar",
                    headers={"Content-Disposition": f'attachment; filename="{case_id}-dates.ics"'})


@app.get("/cases/{case_id}/picture.png")
def picture(case_id: str, lang: str = "en"):
    """The bill in one picture: Muse Image draws the scene, code writes the numbers."""
    d, case, report = _load(case_id)
    if lang not in i18n.LANGS:
        raise HTTPException(400, "language")
    saved = d / f"picture-{lang}.png"
    if saved.exists():
        return FileResponse(saved, media_type="image/png")
    try:
        raw = bill_picture.render(providers.make_client(), case, report, lang)
    except ReplayMissing:
        raise HTTPException(404, "no picture recorded for this case") from None
    except pipeline.RealDataGate as e:
        raise HTTPException(400, str(e)) from None
    saved.write_bytes(raw)
    return Response(raw, media_type="image/png")


@app.get("/cases/{case_id}/reminder.ics")
def reminder(case_id: str):
    """Calendar file for the last day to apply, with alarms 30 and 7 days ahead."""
    _, case, report = _load(case_id)
    due = report.apply_by
    if due is None or days.passed(due, case.today):
        raise HTTPException(404, "no application deadline ahead in this case")
    stamp = case.today.strftime("%Y%m%d") + "T000000Z"
    title = appeal._ics_text(_apply_title(report))
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//BillRadar//EN",
        "BEGIN:VEVENT",
        f"UID:{case_id}-apply-by@billradar",
        f"DTSTAMP:{stamp}",
        f"DTSTART;VALUE=DATE:{due:%Y%m%d}",
        f"SUMMARY:{title}",
        f"DESCRIPTION:BillRadar case {case_id}. Apply by this day. You review and sign every letter.",
    ]
    for ahead in (30, 7):
        lines += ["BEGIN:VALARM", f"TRIGGER:-P{ahead}D", "ACTION:DISPLAY",
                  f"DESCRIPTION:{ahead} days left to apply", "END:VALARM"]
    lines += ["END:VEVENT", "END:VCALENDAR", ""]
    return Response("\r\n".join(lines), media_type="text/calendar",
                    headers={"Content-Disposition": f'attachment; filename="{case_id}-apply-by.ics"'})


def _letters(case: Case, report: checks.Report) -> list[writer.Letter]:
    return writer.all_letters(case, report) + writer.appeal_letters(case)


def _lang(lang: str) -> str:
    if lang not in i18n.LANGS:
        raise HTTPException(400, f"language must be one of {sorted(i18n.LANGS)}")
    return lang


NOT_LIVE = "The translation appears when the model is switched on. Below is the English letter, the one that is sent."


def _letter(case_id: str, kind: str, lang: str):
    loaded = _load(case_id)
    by_kind = {}
    for candidate in _letters(loaded[1], loaded[2]):
        by_kind.setdefault(candidate.kind, candidate)
    if kind not in by_kind:
        raise HTTPException(404)
    chosen = by_kind[kind]
    if _lang(lang) != "en":
        try:
            translated = i18n.letter(providers.make_client(), loaded[1], chosen, lang)
        except (ReplayMissing, pipeline.RealDataGate):
            return (*loaded, chosen, None, NOT_LIVE)
        return (*loaded, chosen, translated, translated.note)
    return (*loaded, chosen, None, "")


@app.get("/cases/{case_id}/letters/{kind}", response_class=HTMLResponse)
def letter(request: Request, case_id: str, kind: str, lang: str = "en"):
    _, case, report, found, tr, note = _letter(case_id, kind, lang)
    chips = [list({c.label: c for c in (view.source_chip(r) for r in dict.fromkeys(p.refs))}.values())
             for p in found.paragraphs]  # two quotes from one statute: one chip
    return _page(request, "letter.html", nav="cases", l=found, case=case, case_id=case_id,
                 sources=writer.sources(found), signature=writer.signature(case), today=case.today,
                 letters=_letters(case, report), chips=chips, apply_by=report.apply_by, apply_sure=report.apply_by_sure, lang=lang,
                 langs=i18n.LANGS, tr=tr, note=note, appeal=view.appeal_panel(case, found),
                 calls=callprep.all_sheets(case, report),
                 greeting=writer.greeting(found),
                 demo_rules=writer.demo_rules(case, found))


@app.get("/cases/{case_id}/letters/{kind}/text")
def letter_text(case_id: str, kind: str, lang: str = "en"):
    _, case, _, found, tr, _ = _letter(case_id, kind, lang)
    text = i18n.plain_text(tr) if tr else writer.plain_text(found, case)
    return Response(text, media_type="text/plain; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{case_id}-{kind}-{lang}.txt"'})


@app.get("/cases/{case_id}/letters/{kind}/pdf")
def letter_pdf(case_id: str, kind: str, lang: str = "en"):
    _, case, _, found, tr, _ = _letter(case_id, kind, lang)
    return Response(report_pdf.letter_pdf(case, found, tr), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{case_id}-{kind}.pdf"'})


@app.get("/cases/{case_id}/report.pdf")
def report_as_pdf(case_id: str, lang: str = "en"):
    d, case, report = _load(case_id)
    pdf = report_pdf.build(case, report, lang=_lang(lang), replayed=_meta(d).get("replayed", True))
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{case_id}-report-{lang}.pdf"'})


@app.get("/cases/{case_id}/call/{to}", response_class=HTMLResponse)
def call_sheet(request: Request, case_id: str, to: str):
    d, case, report = _load(case_id)
    if to not in ("hospital", "insurer"):
        raise HTTPException(404)
    sheet = callprep.build(case, report, to)
    if sheet is None:
        raise HTTPException(404, "nothing to call about here")
    answers = [[view.source_chip(r) for r in dict.fromkeys(o.refs)] for o in sheet.objections]
    return _page(request, "call.html", nav="cases", case=case, case_id=case_id, sheet=sheet, answers=answers,
                 sheets=callprep.all_sheets(case, report), voice_langs=voice.LANGUAGES, span=view.service_span(case),
                 example=case_id in example.READ_ONLY, sample_note="/voice/sample/note.wav" if _sample_note_ready(case_id, to) else None,
                 demo_rules=writer.demo_rules(case) if to == "hospital" else "")  # the insurer's call rests on the plan


@app.post("/cases/{case_id}/call/{to}/note")
async def call_note(case_id: str, to: str, request: Request, lang: str = "en", consent: int = 0):
    """Her voice note after the call -> who she spoke with, the reference number, what was promised -> a paragraph."""
    d, case, report = _load(case_id)
    sheet = callprep.build(case, report, to) if to in ("hospital", "insurer") else None
    if sheet is None:
        raise HTTPException(404)
    wav = await request.body()
    client = _voice_client(wav)
    refused = _voice_refused(request, client, lang, consent, wav)
    if refused:
        return refused
    try:
        tx = voice.transcribe(client, case, wav, lang)
        note = voice.read_note(client, case, tx, who=sheet.who)
    except ReplayMissing:
        return JSONResponse({"error": "Voice notes start when the model is switched on."}, status_code=503)
    except pipeline.RealDataGate as e:
        return JSONResponse({"error": f"Not sent: {e}."}, status_code=400)
    except (ValueError, MetaAPIError) as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    para = note.paragraph(case, lang)
    if case_id not in example.READ_ONLY:
        _save_note(d, to, note, para.text if para else "")
    return {"transcript": tx.text, "replayed": tx.replayed and note.replayed, "rep_name": note.rep_name,
            "reference": note.reference, "promises": [{"words": w, "english": e} for w, e in note.promises],
            "paragraph": para.text if para else ""}


def _notes(d: Path) -> list[dict]:
    p = d / "notes.json"
    return json.loads(p.read_text()) if p.exists() else []


def _save_note(d: Path, to: str, note: voice.CallNote, paragraph: str) -> None:
    """What she keeps from a call: who, the reference, the promise, the paragraph. Never the audio or the transcript."""
    notes = _notes(d) + [{"to": to, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "rep_name": note.rep_name,
                          "reference": note.reference, "promises": [w for w, _ in note.promises], "paragraph": paragraph}]
    (d / "notes.json").write_text(json.dumps(notes, indent=2))


MAX_CALL_BYTES = 32_000 * 60 * 15  # 15 minutes of 16 kHz, 16-bit mono; the stream closes there
SAMPLE_PACE_S = 0.9  # the sample call's answers appear one by one, as they would during a call


def _sample_pcm() -> bytes:
    with wave.open(str(VOICE_SAMPLES / "call.wav")) as f:
        return f.readframes(f.getnframes())


def _realtime(client):
    return call_assist.LiveRealtime(os.environ.get("MODEL_API_KEY", "")) if client.live else call_assist.ReplayRealtime()


def _search_client(client):
    from billradar.tavily_client import TavilyClient
    return TavilyClient() if client.live else None


def _charge_call(ledger: SpendLedger, pcm_bytes: int) -> None:
    ledger.settle(asr_cost(pcm_bytes // 32), "settle muse-voice-transcribe-1.0 realtime")


@app.get("/cases/{case_id}/call/{to}/consent")
def call_consent(case_id: str, to: str, lang: str = "en"):
    """The phrase she says before the call is transcribed, in the language of the call."""
    _load(case_id)
    if lang not in call_assist.CONSENT:
        raise HTTPException(400, "live help works in English or Spanish")
    return {"phrase": call_assist.CONSENT[lang], "language": lang}


@app.websocket("/cases/{case_id}/call/{to}/live")
async def live_call(ws: WebSocket, case_id: str, to: str):
    """The call, live. The browser sends {"type": "start", "lang", "consent"}, then 16 kHz 16-bit mono PCM as binary
    frames, then {"type": "stop"}. The server answers with {"kind", "data"}: started, partial, turn, suggestion,
    captured, web, no_answer, error, closed. Nothing of the call is kept: the note she saves afterwards is her own."""
    await ws.accept()
    try:
        _, case, report = _load(case_id)
        sheet = callprep.build(case, report, to) if to in ("hospital", "insurer") else None
    except HTTPException:
        sheet = None
    if sheet is None:
        await ws.close(code=4404)
        return
    start = await ws.receive_json()
    client, lang = providers.make_client(), start.get("lang", "en")
    sample = bool(start.get("sample"))
    if sample:  # the recorded synthetic call: nothing leaves, nothing is paid for
        client = _sample_client()

    async def refuse(message: str) -> None:
        await ws.send_json({"kind": "error", "data": {"message": message}})
        await ws.close()

    if lang not in call_assist.CONSENT:
        return await refuse("Live help works in English or Spanish.")
    if client.live and history.public() and os.environ.get("BILLRADAR_PUBLIC_VOICE") != "1":
        return await refuse("Live voice is off on this public copy.")
    if client.live and not case.demo:
        return await refuse("Live call help runs only on a fictional case for now.")
    if not sample and not start.get("consent"):
        return await refuse("Say the consent phrase and press \"They agreed\" first.")
    session = call_assist.CallSession(_realtime(client), client, case, sheet, lang, tavily=_search_client(client))
    session.they_agreed()
    ledger = SpendLedger()
    if client.live:
        ledger.reserve(asr_cost(MAX_CALL_BYTES // 32), "reserve muse-voice-transcribe-1.0 realtime")
    frames: queue.Queue = queue.Queue()
    if sample:
        for chunk in call_assist.pcm_frames(_sample_pcm()):
            frames.put(chunk)
        frames.put(None)
    out: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()
    sent = 0

    def work() -> None:
        try:
            for u in session.run(iter(frames.get, None), os.environ.get("MODEL_API_KEY", "")):
                if u.kind == "suggestion":  # for the screen: what the source is called and what it says
                    chips = [view.source_chip(r) for r in u.data["refs"]]
                    u.data["refs"] = [{"label": c.label, "quote": c.title} for c in chips]
                loop.call_soon_threadsafe(out.put_nowait, {"kind": u.kind, "data": u.data})
                if sample and u.kind != "partial":
                    time.sleep(SAMPLE_PACE_S)
        except (ReplayMissing, MetaAPIError, pipeline.RealDataGate, call_assist.ConsentRequired) as e:
            loop.call_soon_threadsafe(out.put_nowait, {"kind": "error", "data": {"message": str(e)}})
        finally:
            loop.call_soon_threadsafe(out.put_nowait, None)

    await ws.send_json({"kind": "started", "data": {"phrase": session.consent_phrase, "sample": sample}})
    threading.Thread(target=work, daemon=True).start()

    async def feed() -> None:
        nonlocal sent
        try:
            while True:
                m = await ws.receive()
                if m.get("bytes") and sent < MAX_CALL_BYTES:
                    sent += len(m["bytes"])
                    frames.put(m["bytes"])
                elif m.get("type") == "websocket.disconnect" or (m.get("text") and json.loads(m["text"]).get("type") == "stop"):
                    break
        except (WebSocketDisconnect, RuntimeError):
            pass
        frames.put(None)

    feeding = asyncio.create_task(feed())
    try:
        while (update := await out.get()) is not None:
            await ws.send_json(update)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        feeding.cancel()
        session.close()
        if client.live:
            ledger.settle(-asr_cost(MAX_CALL_BYTES // 32), "release muse-voice-transcribe-1.0 realtime")
            _charge_call(ledger, sent)
    with contextlib.suppress(WebSocketDisconnect, RuntimeError):  # the caller may have left first
        await ws.close()


@app.get("/cases/{case_id}/notes")
def case_notes(case_id: str):
    return _notes(_run_dir(case_id))


def _today(case_id: str, case: Case) -> date:
    return case.today if case_id in example.READ_ONLY else date.today()


def _tracker(d: Path, case: Case, report: checks.Report, today: date) -> appeal.Tracker:
    tr = appeal.Tracker.load(d)
    for letter_ in _letters(case, report):
        tr.prepare(case, letter_, today)
    return tr


def _owner_only(request: Request, d: Path) -> None:
    if not history.may_delete(d, request.cookies.get(history.cookie_name(d.name))):
        raise HTTPException(403, "only the browser that made this case can change it; the examples are read-only")


@app.post("/cases/{case_id}/ask")
async def ask_case(case_id: str, request: Request):
    """A question about this case; answered only with checked quotes from her sheets or the policy."""
    _, case, report = _load(case_id)
    q = ((await request.json()).get("question") or "").strip()[:500]
    if not q:
        raise HTTPException(400, "empty question")
    return _answer(case, report, q)


def _voice_client(wav: bytes):
    """A recorded sample plays back on every copy and spends nothing; only a person's own voice reaches the model."""
    client = providers.make_client()
    recorded = client.live and getattr(client, "provider", "meta") == "meta" and any(p.read_bytes() == wav for p in VOICE_SAMPLES.glob("*.wav"))
    return _sample_client() if recorded else client


def _voice_refused(request: Request, client, lang: str, consent: int, wav: bytes) -> JSONResponse | None:
    """Why this recording does not go out, or None. Everything said goes to Meta to become text."""
    if lang not in voice.LANGUAGES:
        return JSONResponse({"error": "Voice works in English or Spanish."}, status_code=400)
    if len(wav) > MAX_VOICE_BYTES:
        return JSONResponse({"error": "That recording is too long. Keep it under two minutes."}, status_code=413)
    if not client.live:
        return None  # a recorded sample: nothing leaves
    if history.public() and os.environ.get("BILLRADAR_PUBLIC_VOICE") != "1":
        return JSONResponse({"error": "Live voice is off on this public copy. Try the recorded sample."}, status_code=503)
    if consent != 1:
        return JSONResponse({"error": "Your voice goes to Meta to become text: consent comes first."}, status_code=400)
    if not _allow_live(request):
        return JSONResponse({"error": LIMIT_TEXT}, status_code=429)
    return None


@app.post("/voice/intake")
async def voice_intake(request: Request, lang: str = "en", consent: int = 0):
    """She says what happened; Muse Voice Transcribe writes it, Muse Spark sets the chips. Nothing is kept."""
    wav = await request.body()
    client = _voice_client(wav)
    refused = _voice_refused(request, client, lang, consent, wav)
    if refused:
        return refused
    try:
        tx = voice.transcribe_audio(client, wav, lang)
        chips = voice.pick_chips(client, tx)
    except ReplayMissing:
        return JSONResponse({"error": "Voice starts when the model is switched on."}, status_code=503)
    except (ValueError, MetaAPIError) as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    return {"transcript": tx.text, "chips": chips, "language": lang, "replayed": tx.replayed}


@app.get("/voice/sample/{name}.wav")
def voice_sample(name: str):
    if name not in ("intake", "ask", "call", "note") or not (VOICE_SAMPLES / f"{name}.wav").exists():
        raise HTTPException(404)
    return FileResponse(VOICE_SAMPLES / f"{name}.wav", media_type="audio/wav")


@app.post("/cases/{case_id}/ask/voice")
async def ask_case_by_voice(case_id: str, request: Request, lang: str = "en", consent: int = 0):
    """The same answer as a typed question, plus what she said."""
    _, case, report = _load(case_id)
    wav = await request.body()
    client = _voice_client(wav)
    refused = _voice_refused(request, client, lang, consent, wav)
    if refused:
        return refused
    try:
        tx = voice.transcribe(client, case, wav, lang)
    except ReplayMissing:
        return JSONResponse({"error": "Voice starts when the model is switched on."}, status_code=503)
    except pipeline.RealDataGate as e:
        return JSONResponse({"error": f"Not sent: {e}."}, status_code=400)
    except (ValueError, MetaAPIError) as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    answered = _answer(case, report, tx.text[:500], client)
    return answered if isinstance(answered, JSONResponse) else {**answered, "transcript": tx.text}


def _money_reads_as_money(text: str) -> str:
    """The model can quote a sum as the sheet's bare number: on the screen a sum has its dollar sign."""
    text = re.sub(r"(?<![\d$.,/-])(\d{1,3}(?:,\d{3})+|\d+)\.(\d{2})(?![\d%])", lambda m: f"${int(m[1].replace(',', '')):,}.{m[2]}", text)
    return re.sub(r"(?<![\d$.,/-])(\d{3,})(?= each\b)", lambda m: f"${int(m[1]):,}", text)


def _sentences_start_big(text: str) -> str:
    """Sheet names come out of tokens in lower case: "sheet 1" can land at the start of a sentence."""
    return re.sub(r"(^|[.!?]\s+)(sheet|file)\b", lambda m: m.group(1) + m.group(2).capitalize(), text)


def _answer(case: Case, report: checks.Report, q: str, client=None):
    try:
        a = web_answer.ladder(client or providers.make_client(), case, report, q)
    except ReplayMissing:
        a = ask.Answer("No answer yet: the model is not connected.", refused=True, reason="no_model")
    except pipeline.RealDataGate as e:
        return JSONResponse({"error": f"Not sent: {e}."}, status_code=400)
    cites = []
    for c in a.citations:
        if c.source == "sheet":
            doc = c.ref.split("#", 1)[0]
            cites.append({"kind": "sheet", "label": f"{'Sheet' if doc.startswith('S') else 'File'} {doc[1:]}", "quote": c.quote})
        else:
            chip = view.source_chip(c.ref)
            cites.append({"kind": "policy", "label": chip.label, "quote": c.quote, "url": c.url})
    return {"text": _money_reads_as_money(_sentences_start_big(i18n.plain(a.text, case))), "refused": a.refused, "reason": a.reason, "citations": cites, "replayed": a.replayed,
            "source": a.source, "say": a.say, "web": asdict(a.web) if a.web else None}


@app.get("/cases/{case_id}/appeals", response_class=HTMLResponse)
def appeals(request: Request, case_id: str, key: str = "", msg: str = ""):
    d, case, report = _load(case_id)
    today = _today(case_id, case)
    tr = _tracker(d, case, report, today)
    rows = [tr.status_on(k, today) | {"to": it.to, "reply": it.reply, "appeal_by_on": it.appeal_by,
                                       "sent_on": it.sent_on} for k, it in tr.items.items()]
    rows.sort(key=lambda r: (not r["key"].startswith("appeal-"), r["key"]))
    current = next((r for r in rows if r["key"] == key), rows[0] if rows else None)
    has_dates = any(it.sent_on or it.decide_by or (it.appeal_by and not it.sent_on) for it in tr.items.values())
    return _page(request, "appeals.html", nav="cases", case=case, case_id=case_id, rows=rows, current=current,
                 has_dates=has_dates,
                 steps=appeal.STATUSES, msg=msg, today=today,
                 can_change=history.may_delete(d, request.cookies.get(history.cookie_name(case_id))))


@app.post("/cases/{case_id}/appeals/{key}/sent")
def appeal_sent(request: Request, case_id: str, key: str, on: date = Form(...), confirmation: str = Form("")):
    d, case, report = _load(case_id)
    _owner_only(request, d)
    tr = _tracker(d, case, report, _today(case_id, case))
    if key not in tr.items:
        raise HTTPException(404)
    tr.mark_sent(case, key, on, confirmation.strip()[:80])
    tr.save(d)
    return RedirectResponse(f"/cases/{case_id}/appeals?key={key}", status_code=303)


@app.post("/cases/{case_id}/appeals/{key}/agent", status_code=202)
def appeal_agent_fill(case_id: str, key: str):
    """Muse Spark fills the insurer's form on the demo copy and stops before Submit."""
    d, case, _ = _load(case_id)
    client = providers.make_client()
    if client.live and history.public():  # a public copy plays the recorded run: no browser opens for a stranger
        client = _sample_client()
    if not client.live and not (portal_job.RECORDED / "run.json").exists():
        return JSONResponse({"error": "The agent starts when the model is switched on."}, status_code=503)
    try:
        return portal_job.fill(client, d, case, key)
    except KeyError:
        raise HTTPException(404, "no such appeal in this case") from None
    except pipeline.RealDataGate as e:
        return JSONResponse({"error": f"Not sent: {e}."}, status_code=400)


@app.get("/cases/{case_id}/appeals/{key}/agent")
def appeal_agent_status(case_id: str, key: str):
    """state: none, filling, ready, sending, sent, failed. shots: how many screenshots, /agent/shot/<n>.png."""
    d, _, _ = _load(case_id)
    return portal_job.status(d, key)


@app.get("/cases/{case_id}/appeals/{key}/agent/shot/{n}.png")
def appeal_agent_shot(case_id: str, key: str, n: int):
    p = _run_dir(case_id) / "agent" / f"{n}.png"
    if not p.is_file():
        raise HTTPException(404)
    return FileResponse(p, media_type="image/png")


@app.post("/cases/{case_id}/appeals/{key}/agent/send")
def appeal_agent_send(case_id: str, key: str):
    """Only this press lets the agent press Submit, once."""
    d, case, report = _load(case_id)
    today = _today(case_id, case)
    tr = _tracker(d, case, report, today)
    try:
        return portal_job.send(providers.make_client(), d, case, key, today, tr)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=409)


@app.post("/cases/{case_id}/appeals/{key}/reply")
async def appeal_reply(request: Request, case_id: str, key: str, photo: UploadFile = File(...)):
    d, case, report = _load(case_id)
    _owner_only(request, d)
    tr = _tracker(d, case, report, _today(case_id, case))
    if key not in tr.items:
        raise HTTPException(404)
    plan_id = next((x.plan_id for x in appeal.denials(case) if appeal.letter_kind(x) == key), None)
    try:
        reply = appeal.read_reply(providers.make_client(), case, await photo.read(), plans.load(plan_id) if plan_id else None)
    except ReplayMissing:
        return RedirectResponse(f"/cases/{case_id}/appeals?key={key}&msg=not-live", status_code=303)
    except pipeline.RealDataGate:
        return RedirectResponse(f"/cases/{case_id}/appeals?key={key}&msg=gate", status_code=303)
    tr.record_reply(key, reply, _today(case_id, case))
    tr.save(d)
    return RedirectResponse(f"/cases/{case_id}/appeals?key={key}", status_code=303)


@app.get("/cases/{case_id}/appeals.ics")
def appeals_ics(case_id: str):
    d, case, report = _load(case_id)
    tr = _tracker(d, case, report, _today(case_id, case))
    return Response(appeal.reminders_ics(tr, case_id), media_type="text/calendar",
                    headers={"Content-Disposition": f'attachment; filename="{case_id}-reminders.ics"'})


@app.get("/cases/{case_id}/form.pdf")
def form_pdf(case_id: str):
    case = _load(case_id)[1]
    if case.policy_id not in FORM_FOR_POLICY:
        raise HTTPException(404, "no form for this policy yet")
    filled = FORM_FOR_POLICY[case.policy_id](case)
    disposition = 'inline; filename="%s-financial-assistance-form.pdf"' % case_id
    return Response(content=filled.pdf, media_type="application/pdf", headers={"Content-Disposition": disposition})


@app.get("/cases/{case_id}/overlay/{name}")
def overlay(case_id: str, name: str):
    if not re.fullmatch(r"(overlay|sent)-\d+\.jpg", name):
        raise HTTPException(404)
    return FileResponse(_run_dir(case_id) / name)


@app.get("/cases/{case_id}/report.json")
def report_json(case_id: str):
    return FileResponse(_run_dir(case_id) / "report.json")


class _PersonGetsAPage:
    """The agent entry sits at the root, so an unknown address lands there: a person in a browser still gets our page."""
    OWN = ("/mcp", "/a2a", "/.well-known/", "/agents/healthz")

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if (scope["type"] == "http" and scope["method"] == "GET" and not scope["path"].startswith(self.OWN)
                and b"text/html" in dict(scope["headers"]).get(b"accept", b"")):
            await _page(Request(scope, receive), "not_found.html", status_code=404)(scope, receive, send)
            return
        await self.inner(scope, receive, send)


app.mount("/", _PersonGetsAPage(agent))  # last: /mcp, /a2a, /.well-known/agent-card.json, /agents/healthz
