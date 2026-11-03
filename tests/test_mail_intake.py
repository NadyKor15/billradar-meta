"""Bills by forwarded email (Я25). Every message here is SYNTHETIC: built in the test from the fictional sample
pack's PDFs, with made-up people and example.com addresses. The model's reading comes from that pack's
generator, so this checks the plumbing, not the models."""

import base64
import io
import json
import re
import shutil
import subprocess
import time
from email.message import EmailMessage
from pathlib import Path

import httpx
import pytest
from pypdf import PdfReader

from billradar import agent_api, agent_entry, mail_intake, providers
from billradar.meta_client import MetaClient

PACK = Path(__file__).resolve().parents[1] / "eval" / "packs" / "work" / "brs1-birth-all-errors"
PDFS = ["01-hospital-statement.pdf", "02-hospital-itemized-mother.pdf", "03-hospital-itemized-newborn.pdf"]
FAMILY = "maria.sample@example.com"
SECRET = "s" * 40
BASE = "https://billradar.example"


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(agent_api, "RUNS", tmp_path / "agents")
    monkeypatch.setattr(agent_api, "INTAKE_INDEX", tmp_path / "agents" / "intake-index.json")
    monkeypatch.setenv("BILLRADAR_AGENT_KEYS", "k" * 32)
    monkeypatch.setenv(mail_intake.DOMAIN_ENV, "bills.example.org")
    monkeypatch.setenv(mail_intake.SECRET_ENV, SECRET)
    monkeypatch.delenv(mail_intake.PATH_ENV, raising=False)


def message(pdfs=PDFS, extra=None, message_id="<m1@example.com>", sender=f"Maria Sample <{FAMILY}>") -> bytes:
    m = EmailMessage()
    m["From"] = sender
    m["To"] = "intake+0123456789abcdef@bills.example.org"
    m["Subject"] = "Fwd: Your statement from Seaside Regional Hospital (SAMPLE)"
    m["Date"] = "Tue, 27 Oct 2026 09:00:00 -0400"
    m["Message-ID"] = message_id
    m.set_content("---------- Forwarded message ---------\nFrom: Billing <billing@seaside-regional.example>\n"
                  "Dear Maria Sample, your statement is attached. Please pay by the date on it.\n")
    for name in pdfs:
        m.add_attachment((PACK / name).read_bytes(), maintype="application", subtype="pdf", filename=name)
    for name, data, (mt, st) in extra or []:
        m.add_attachment(data, maintype=mt, subtype=st, filename=name)
    return m.as_bytes()


class PackReader:
    """Answers Spark with the pack generator's reading of D1..D3, page by page; the email's own page is 'other'."""

    def __init__(self):
        self.reading = {d["doc_id"]: d for d in json.loads((PACK / "answers" / "reading.json").read_text())["documents"]}
        self.bodies = []

    def events(self, body):
        self.bodies.append(body)
        ids = re.search(r"Documents in this case: ([^.]+(?:\.[0-9]+)?(?:, [^,.]+(?:\.[0-9]+)?)*)\. Images",
                        body["input"][1]["content"][0]["text"]).group(1).split(", ")
        docs = []
        for pid in ids:
            base, _, page = pid.partition(".")
            src = self.reading.get(base)
            if src and page in ("", "1"):
                docs.append(dict(src, doc_id=pid))
            else:
                docs.append({k: ("" if isinstance(v, str) else v) for k, v in next(iter(self.reading.values())).items()}
                            | {"doc_id": pid, "kind": "other", "lines": [], "first_after_discharge": False,
                               "page_no": 0, "page_count": 0})
        return [{"type": "response.output_text.delta", "delta": json.dumps({"documents": docs})},
                {"type": "response.completed", "response": {"id": "resp_SYNTHETIC", "usage": {}}}]


def fake_client():
    return MetaClient(transport=PackReader(), record_to=None, journal=None)


def email_case(senders=(FAMILY,)):
    r = agent_api.start_email_case(fictional=True, household_size=3, annual_income="58000",
                                   letterhead="Seaside Regional Hospital", senders=list(senders))
    return r, agent_api.RUNS / r["case_id"]


# --- reading a message ----------------------------------------------------------------------------

def test_parse_takes_pdfs_and_text_and_drops_the_rest():
    raw = message(extra=[("notes.zip", b"PK\x03\x04", ("application", "zip")),
                         ("fake.pdf", b"not a pdf", ("application", "pdf"))])
    p = mail_intake.parse(raw)
    assert [n for n, _, _ in p.files] == PDFS and p.from_addr == FAMILY and "Maria Sample" in p.names
    assert "statement is attached" in p.body
    assert any("notes.zip" in d for d in p.dropped) and any("fake.pdf" in d and "not a PDF" in d for d in p.dropped)


def test_forwarded_message_attached_whole_is_read_inside():
    inner = mail_intake.parse(message())
    outer = EmailMessage()
    outer["From"] = f"Maria Sample <{FAMILY}>"
    outer["Subject"] = "Fwd"
    outer.set_content("see attached")
    # a mail client attaches the message itself (message/rfc822 may not be base64-encoded, RFC 2046 5.2.1)
    import email as _email, email.policy as _policy
    outer.add_attachment(_email.message_from_bytes(message(), policy=_policy.default))
    p = mail_intake.parse(outer.as_bytes())
    assert [n for n, _, _ in p.files] == [n for n, _, _ in inner.files]


def test_email_page_hides_addresses_and_names_must_light():
    p = mail_intake.parse(message())
    assert "Maria Sample" in p.body and "billing@seaside-regional.example" in p.body  # visible before
    page = PdfReader(io.BytesIO(mail_intake.body_pdf(p))).pages[0].extract_text()
    assert "Maria" not in page and "@" not in page and "statement is attached" in page
    assert "[name]" in page and "[email]" in page


# --- addresses, signatures ----------------------------------------------------------------------

def test_address_only_for_fictional_cases_started_for_email():
    r, d = email_case()
    assert r["address"] == f"intake+{r['token']}@bills.example.org" and r["senders"] == [FAMILY]
    assert mail_intake.token_from(r["address"]) == r["token"]
    sample = agent_api.analyze_case(sample_pack="brs1-birth-all-errors", fictional=True)
    with pytest.raises(mail_intake.IntakeError, match="not started for email"):
        mail_intake.open_address(agent_api.RUNS / sample["case_id"], [FAMILY], agent_api.INTAKE_INDEX)
    with pytest.raises(agent_api.AgentError, match="only fictional"):
        agent_api.start_email_case(fictional=False, household_size=3, annual_income="1")


def test_no_domain_means_no_address(monkeypatch):
    monkeypatch.delenv(mail_intake.DOMAIN_ENV)
    r, _ = email_case()
    assert r["address"] is None and ".eml" in r["note"]


def test_signature_must_be_right_and_fresh():
    raw, now = b"Subject: x\r\n\r\nhi", time.time()
    ts = str(int(now))
    import hashlib, hmac
    sig = hmac.new(SECRET.encode(), ts.encode() + b"." + raw, hashlib.sha256).hexdigest()
    assert mail_intake.verify_signature(raw, ts, sig, SECRET, now)
    assert not mail_intake.verify_signature(raw + b"!", ts, sig, SECRET, now)
    assert not mail_intake.verify_signature(raw, ts, sig, SECRET, now + 600)  # replayed later
    assert not mail_intake.verify_signature(raw, ts, sig, "", now)


@pytest.mark.skipif(not shutil.which("node"), reason="node is needed to run the Worker")
def test_worker_signs_what_the_app_checks(tmp_path):
    """The Worker's own code runs in node with a fake message and a fake fetch; Python checks its signature."""
    script = tmp_path / "run.mjs"
    worker = Path(__file__).resolve().parents[1] / "workers" / "email-intake" / "worker.js"
    script.write_text(f"""
import w from {json.dumps(worker.as_uri())};
const raw = new TextEncoder().encode("Subject: test\\r\\n\\r\\nSAMPLE body");
let sent = null, rejected = null;
globalThis.fetch = async (url, init) => {{ sent = {{url, headers: init.headers, body: Buffer.from(init.body).toString("base64")}}; return {{status: 202}}; }};
const msg = {{from: "{FAMILY}", to: "intake+0123456789abcdef@bills.example.org", rawSize: raw.byteLength,
  raw: new Blob([raw]).stream(), setReject: (r) => {{ rejected = r; }}}};
await w.email(msg, {{INTAKE_URL: "{BASE}/intake/email", INTAKE_SECRET: "{SECRET}"}});
console.log(JSON.stringify({{sent, rejected}}));
""")
    out = json.loads(subprocess.run(["node", str(script)], capture_output=True, text=True, check=True).stdout)
    h, body = out["sent"]["headers"], base64.b64decode(out["sent"]["body"])
    assert out["rejected"] is None and h["X-BillRadar-From"] == FAMILY and out["sent"]["url"].endswith("/intake/email")
    assert mail_intake.verify_signature(body, h["X-BillRadar-Timestamp"], h["X-BillRadar-Signature"], SECRET)


# --- adding mail to the case -----------------------------------------------------------------------

def test_ingest_reads_the_attachments_in_private_mode_and_skips_a_repeat():
    _, d = email_case()
    out = mail_intake.ingest(d, message(), fake_client(), via="upload")
    assert out["added"] == [f"01-{n}" for n in PDFS] + ["01-email-text.pdf"] and not out["duplicate"]
    case = json.loads((d / "case.json").read_text())
    assert [x["doc_id"] for x in case["documents"]][:3] == ["D1", "D2", "D3"]
    assert json.loads((d / "problems.json").read_text())["redacted"] is True
    assert (d / "sent-1.jpg").exists()  # what left the device: covered pages only
    again = mail_intake.ingest(d, message(), fake_client(), via="upload")
    assert again["duplicate"] and again["added"] == []


def test_forwarded_mail_only_from_listed_senders():
    _, d = email_case()
    with pytest.raises(mail_intake.IntakeError, match="not one the family forwards from"):
        mail_intake.ingest(d, message(sender="Someone <someone@example.net>"), fake_client(), via="routing")


def test_ingest_into_a_case_not_started_for_email_is_refused():
    sample = agent_api.analyze_case(sample_pack="brs1-birth-all-errors", fictional=True)
    with pytest.raises(mail_intake.IntakeError, match="not started for email"):
        mail_intake.ingest(agent_api.RUNS / sample["case_id"], message(), fake_client())


# --- the signed route ---------------------------------------------------------------------------------

def _post(raw, headers, monkeypatch=None):
    import asyncio
    gate = agent_entry.app(public_url=BASE)

    async def go():
        star = gate.app
        async with star.router.lifespan_context(star):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=gate), base_url=BASE) as h:
                return await h.post("/intake/email", content=raw, headers=headers)
    return asyncio.run(go())


def signed(raw, to, sender=FAMILY, secret=SECRET):
    import hashlib, hmac
    ts = str(int(time.time()))
    return {"X-BillRadar-Timestamp": ts, "X-BillRadar-To": to, "X-BillRadar-From": sender,
            "X-BillRadar-Signature": hmac.new(secret.encode(), ts.encode() + b"." + raw, hashlib.sha256).hexdigest()}


def test_route_checks_signature_address_and_sender(monkeypatch):
    r, d = email_case()
    raw = message()
    assert _post(raw, signed(raw, r["address"], secret="x" * 40)).status_code == 401
    assert _post(raw, signed(raw, "intake+ffffffffffffffff@bills.example.org")).status_code == 404
    assert _post(raw, signed(raw, r["address"], sender="someone@example.net")).status_code == 403
    monkeypatch.setattr(providers, "make_client", fake_client)
    ok = _post(raw, signed(raw, r["address"]))
    assert ok.status_code == 202
    assert (d / "mail" / f"01-{PDFS[0]}").exists() and not (d / "intake-error.json").exists()
    monkeypatch.delenv(mail_intake.SECRET_ENV)
    assert _post(raw, signed(raw, r["address"])).status_code == 503  # no secret: closed, not open


# --- for agents ------------------------------------------------------------------------------------------

def test_agent_ingest_needs_a_key_and_then_a_live_model():
    r, _ = email_case()
    eml = base64.b64encode(message()).decode()
    with pytest.raises(agent_api.AgentError, match="API key"):
        agent_api.ingest_email(r["case_id"], eml)
    agent_api.authorized.set(True)
    try:
        with pytest.raises(agent_api.AgentError, match="live model run"):
            agent_api.ingest_email(r["case_id"], eml)
    finally:
        agent_api.authorized.set(False)
