"""Bills by email: the family forwards a hospital's or an insurer's email to the case's own address, and
BillRadar adds it to the case and checks everything again. No photo needed.

Three ways in, one function underneath (`ingest`):
  - forwarded mail: Cloudflare Email Routing -> a small Worker (workers/email-intake) -> POST of the raw
    message to INTAKE_PATH, signed with HMAC-SHA256 (agent_entry.py checks it);
  - a saved .eml dropped on the case screen;
  - an AI agent's `ingest_email` tool.

What is taken: PDF and image attachments (also inside a forwarded message), and the email's own text,
which becomes a one-page PDF so it is read like any other paper. Everything else is dropped with a note.
The case then runs in private mode: names, numbers and addresses are covered on the device before any
page goes to a model (pdfpages, redact). Email addresses and the senders' names are masked in the text
before it is even drawn. The raw message is not kept.

Who may add mail: a forwarded message must come from an address the family listed when the address was
issued; a dropped .eml comes from the person on the case screen. Only fictional cases get an address for
now. Each Message-ID is taken once.
"""

from __future__ import annotations

import email
import email.policy
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import time
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import getaddresses, parseaddr
from pathlib import Path

DOMAIN_ENV, PATH_ENV, LOCAL_ENV, SECRET_ENV = ("BILLRADAR_INTAKE_DOMAIN", "BILLRADAR_INTAKE_PATH",
                                               "BILLRADAR_INTAKE_LOCAL", "BILLRADAR_INTAKE_SECRET")
MAX_MESSAGE = 25 * 1024 * 1024  # Cloudflare rejects larger inbound mail anyway
MAX_ATTACHMENTS = 10
MAX_ATTACHMENT = 10 * 1024 * 1024
MAX_SKEW = 300  # seconds between the Worker's timestamp and ours
TAKE = {"application/pdf": "pdf", "image/jpeg": "jpg", "image/png": "png"}
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def intake_domain() -> str:
    return os.environ.get(DOMAIN_ENV, "")


def intake_path() -> str:
    return os.environ.get(PATH_ENV, "/intake/email")


def intake_local() -> str:
    return os.environ.get(LOCAL_ENV, "intake")


class IntakeError(ValueError):
    pass


# --- reading one message ------------------------------------------------------------------------

@dataclass
class Parsed:
    message_id: str
    from_addr: str
    from_name: str
    subject: str
    date: str
    body: str
    files: list[tuple[str, str, bytes]] = field(default_factory=list)  # (name, kind pdf|jpg|png, bytes)
    dropped: list[str] = field(default_factory=list)
    names: list[str] = field(default_factory=list)  # display names in the headers, to mask


def parse(raw: bytes) -> Parsed:
    if len(raw) > MAX_MESSAGE:
        raise IntakeError("message is larger than 25 MB")
    msg: EmailMessage = email.message_from_bytes(raw, policy=email.policy.default)
    name, addr = parseaddr(str(msg.get("From", "")))
    names = _names(msg)
    p = Parsed(message_id=str(msg.get("Message-ID", "")).strip(), from_addr=addr.lower(), from_name=name,
               subject=str(msg.get("Subject", "")), date=str(msg.get("Date", "")), body="", names=names)
    bodies: list[str] = []
    _walk(msg, p, bodies)
    p.body = "\n\n".join(b.strip() for b in bodies if b.strip())
    if not p.message_id:
        p.message_id = "<sha256:" + hashlib.sha256(raw).hexdigest()[:24] + ">"
    return p


def _names(msg) -> list[str]:
    # one header at a time: since Python 3.12 a strict parse of a list with an empty entry returns nothing
    out = []
    for h in ("From", "To", "Cc", "Reply-To", "Sender"):
        for value in msg.get_all(h, []) or []:
            out += [n for n, _ in getaddresses([str(value)]) if n]
    return out


def _parts(msg):
    """Every leaf part, also inside a forwarded message attached whole (message/rfc822)."""
    ctype = msg.get_content_type()
    if ctype == "message/rfc822":
        payload = msg.get_payload()
        for inner in payload if isinstance(payload, list) else [payload]:
            yield ("message", inner)
            yield from _parts(inner)
    elif msg.is_multipart():
        for part in msg.get_payload():
            yield from _parts(part)
    else:
        yield ("leaf", msg)


def _walk(msg: EmailMessage, p: Parsed, bodies: list[str]) -> None:
    for what, part in _parts(msg):
        if what == "message":
            p.names += _names(part)
            continue
        ctype = part.get_content_type()
        disp = part.get_content_disposition()
        name = part.get_filename() or ""
        if ctype in TAKE and (disp == "attachment" or name or ctype != "text/plain"):
            data = part.get_payload(decode=True) or b""
            if len(p.files) >= MAX_ATTACHMENTS:
                p.dropped.append(f"{name or ctype}: more than {MAX_ATTACHMENTS} attachments")
            elif len(data) > MAX_ATTACHMENT:
                p.dropped.append(f"{name or ctype}: larger than {MAX_ATTACHMENT // (1024 * 1024)} MB")
            elif ctype == "application/pdf" and not data.startswith(b"%PDF"):
                p.dropped.append(f"{name or ctype}: not a PDF inside")
            else:
                p.files.append((_safe_name(name, TAKE[ctype], len(p.files) + 1), TAKE[ctype], data))
            continue
        if ctype == "text/plain" and disp != "attachment":
            bodies.append(part.get_content())
        elif ctype == "text/html" and disp != "attachment" and not any(b for b in bodies):
            bodies.append(_html_text(part.get_content()))
        elif disp == "attachment" or name:
            p.dropped.append(f"{name or ctype}: {ctype} is not read (PDF, JPEG and PNG are)")


def _safe_name(name: str, ext: str, n: int) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(name).stem)[:40].strip("-.") or f"attachment-{n}"
    return f"{stem}.{ext}"


def _html_text(html: str) -> str:
    html = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>", "\n", html)
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"[ \t]+", " ", re.sub(r"&nbsp;", " ", text))


def masked(text: str, names: list[str]) -> str:
    """Email addresses and the people named in the headers never reach the drawn page."""
    text = EMAIL_RE.sub("[email]", text)
    for n in sorted({n.strip() for n in names if len(n.strip()) > 2}, key=len, reverse=True):
        text = re.sub(re.escape(n), "[name]", text, flags=re.I)
    return text


def body_pdf(p: Parsed, extra_names: list[str] = ()) -> bytes:
    """The email's own words as a page, so the reader treats it like any other paper."""
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    from xml.sax.saxutils import escape

    from billradar.report_pdf import _fonts
    _fonts()
    names = list(p.names) + list(extra_names)
    st = ParagraphStyle("b", fontName="Noto", fontSize=10, leading=14)
    head = ParagraphStyle("h", parent=st, fontName="Noto-Bold")
    story = [Paragraph(escape(masked(f"Email received: {p.subject}", names)), head),
             Paragraph(escape(masked(f"Date: {p.date}", names)), st), Spacer(1, 10)]
    for para in masked(p.body, names).split("\n"):
        story.append(Paragraph(escape(para) or "&nbsp;", st))
    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=LETTER, invariant=1, title="Email").build(story)
    return buf.getvalue()


# --- addresses and who may write ------------------------------------------------------------------

def _state(run_dir: Path) -> dict:
    p = run_dir / "intake.json"
    return (json.loads(p.read_text()) if p.exists()
            else {"mail_case": False, "token": "", "senders": [], "messages": [], "files": []})


def start_case(run_dir: Path, case) -> None:
    """A case that is built from forwarded mail only: no papers yet, the family's numbers and policy."""
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "case.json").write_text(case.model_dump_json())
    _save_state(run_dir, {"mail_case": True, "token": "", "senders": [], "messages": [], "files": []})


def _save_state(run_dir: Path, st: dict) -> None:
    (run_dir / "intake.json").write_text(json.dumps(st, indent=1))


def open_address(run_dir: Path, senders: list[str], index: Path) -> dict:
    """Give a fictional case its own address. `senders`: the addresses the family forwards from."""
    from billradar.case import Case
    case = Case.model_validate_json((run_dir / "case.json").read_text())
    if not case.demo:
        raise IntakeError("only fictional cases get an address for now")
    clean = sorted({s.strip().lower() for s in senders if EMAIL_RE.fullmatch(s.strip())})
    if not clean:
        raise IntakeError("list at least one address the family forwards from")
    st = _state(run_dir)
    if not st.get("mail_case"):
        raise IntakeError("this case was not started for email; start one for email first")
    st["token"] = st["token"] or secrets.token_hex(8)
    st["senders"] = clean
    _save_state(run_dir, st)
    idx = json.loads(index.read_text()) if index.exists() else {}
    idx[st["token"]] = str(run_dir)
    index.parent.mkdir(parents=True, exist_ok=True)
    index.write_text(json.dumps(idx))
    domain = intake_domain()
    return {"address": f"{intake_local()}+{st['token']}@{domain}" if domain else None,
            "token": st["token"], "senders": clean,
            "note": None if domain else "email routing is not set up here; drop a saved .eml instead"}


def token_from(recipient: str) -> str:
    local = recipient.split("@", 1)[0].lower()
    m = re.fullmatch(re.escape(intake_local()) + r"\+([0-9a-f]{16})", local)
    return m.group(1) if m else ""


def verify_signature(raw: bytes, timestamp: str, signature: str, secret: str, now: float | None = None) -> bool:
    """HMAC-SHA256 over "<timestamp>." + raw message, hex; the timestamp must be fresh (no replays)."""
    if not secret or not timestamp.isdigit() or not signature:
        return False
    if abs((now or time.time()) - int(timestamp)) > MAX_SKEW:
        return False
    want = hmac.new(secret.encode(), timestamp.encode() + b"." + raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(want, signature.lower())


# --- adding a message to the case -----------------------------------------------------------------

def ingest(run_dir: Path, raw: bytes, client, via: str = "upload", envelope_from: str = "") -> dict:
    """Add one email to the case and run the whole case again in private mode.
    via: "upload" (the person on the case screen, or an agent with the case) or "routing" (forwarded mail)."""
    from billradar import pipeline
    from billradar.case import Case

    case = Case.model_validate_json((run_dir / "case.json").read_text())
    if not case.demo:
        raise IntakeError("only fictional cases take email for now")
    p = parse(raw)
    st = _state(run_dir)
    if not st.get("mail_case"):
        raise IntakeError("this case was not started for email")
    if via == "routing":
        sender = (envelope_from or p.from_addr).lower()
        if sender not in st["senders"]:
            raise IntakeError("this address is not one the family forwards from")
    if p.message_id in st["messages"]:
        return {"added": [], "dropped": p.dropped, "note": "this email was already added", "duplicate": True}
    if not p.files and not p.body.strip():
        raise IntakeError("nothing to read in this email")

    inbox = run_dir / "mail"
    inbox.mkdir(exist_ok=True)
    n = len(st["messages"]) + 1
    added = []
    for name, kind, data in p.files:
        path = inbox / f"{n:02d}-{name}"
        path.write_bytes(data)
        added.append(path.name)
    if p.body.strip():
        names = [x.name for x in case.profile.people if x.name] + [p.from_name]
        path = inbox / f"{n:02d}-email-text.pdf"
        path.write_bytes(body_pdf(p, names))
        added.append(path.name)
    st["messages"].append(p.message_id)
    st["files"] += added
    _save_state(run_dir, st)

    files = [(f, (inbox / f).read_bytes()) for f in st["files"] if f.endswith(".pdf")]
    photos = [(inbox / f).read_bytes() for f in st["files"] if not f.endswith(".pdf")]
    run_ = pipeline.run(client, photos, files, case.profile, case.policy_id, case.letterhead, case.today,
                        case.case_id, fictional=True, private=True)
    run_.case.demo = True
    pipeline.save(run_, run_dir)
    return {"added": added, "dropped": p.dropped, "duplicate": False, "replayed": run_.replayed,
            "total_may_come_off": str(run_.report.total_may_come_off),
            "apply_by": run_.report.apply_by.isoformat() if run_.report.apply_by else None,
            "problems": run_.problems}
