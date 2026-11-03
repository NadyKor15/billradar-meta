"""When the papers do not answer: the hospital's own site and official law pages, quoted word for word.

The ladder, for a question about a case and for what the office says during a call:
  1. the case: an answer with a checked quote (ask.answer);
  2. the web, two searches and each gets the question it is good at: about this hospital, a Tavily search only on the
     hospital's site and official pages; about a law or insurance in general, Meta's web_search, whose results code
     filters by host because the request cannot name domains. Nothing from one: the other. The model picks one of the
     sentences code found; it never writes one. Code compares the quote with the page's own text. The quote is shown
     with its page and the label "from the web, check it", and it never reaches an amount or a finding;
  3. nothing found: "not in your case", and a phrase to say.

What leaves the device for step 2 is the question without anything personal: clean_question takes out what the
family typed in, covered tokens, digits, and anything that looks like money or a date.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from urllib.parse import urlparse

from billradar import ask, i18n
from billradar.case import Case
from billradar.checks import Report
from billradar.meta_client import MetaAPIError, MetaClient, search_calls
from billradar.policies import source
from billradar.policy_finder import _key
from billradar.tavily_client import TavilyClient, TavilyError

MODEL = "muse-spark-1.3"
LABEL = "from the web, check it"
NOT_IN_CASE = "That's not in your case."
ASK_IN_WRITING = "Could you send me that in writing, please?"
MIN_WORDS = 3
MAX_CANDIDATES = 24
OFFICIAL = ("cms.gov", "hhs.gov", "healthcare.gov", "dol.gov", "irs.gov", "ecfr.gov", "federalregister.gov",
            "flsenate.gov")
TITLES = {"dr", "doctor", "mr", "mrs", "ms", "miss", "nurse"}
SPEECH_WORDS = {"said", "says", "told", "asked", "wrote", "called", "sent"}
BILLING_WORDS = {"No", "Surprises", "Act", "Medicaid", "Medicare", "Florida", "COBRA", "ACA", "ERISA", "EOB", "ER", "ICU", "I"}
OPENING_WORDS = set("can could what what's whats why how when where who does do did is are was were our my the they we i "
                    "should will would may if has have this that there a an in on for at to you your it its".split())
_TOKEN = re.compile(r"\[[^\]]*\]|\b[A-Z]{2,}_\d+\b")
_HAS_DIGIT = re.compile(r"\S*\d\S*")
_WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*")
PICK_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["pick"],
               "properties": {"pick": {"type": "string"}}}
PICK_INSTRUCTIONS = """You pick one sentence that answers a question about a hospital bill or insurance. You get the question and numbered sentences from the hospital's own site and official pages.
Return in "pick" the id of the one sentence that directly answers the question, or "none" if no sentence does. Never write a sentence yourself. You do not give medical advice: for a health question, return "none"."""


@dataclass
class WebAnswer:
    quote: str
    url: str
    title: str
    label: str = LABEL
    seconds: float = 0.0  # the search and the pick together


def clean_question(question: str, case: Case) -> str:
    """The question with nothing personal left: the only text that goes to the search."""
    text = i18n.mask(question, i18n.private_values(case))
    text = _HAS_DIGIT.sub(" ", _TOKEN.sub(" ", text))
    family = {w.lower() for v in i18n.private_values(case) for w in _WORD.findall(v)}
    kept, after_title = [], 0
    for i, word in enumerate(_WORD.findall(text)):
        low = word.lower()
        if low in TITLES:
            after_title = 2  # "dr smith", "doctor jane smith": speech gives names in small letters
            continue
        if after_title and low not in OPENING_WORDS and low not in SPEECH_WORDS:
            after_title -= 1
            continue
        after_title = 0
        if low in family:
            continue
        if word[0].isupper() and word not in BILLING_WORDS and (i or word.lower() not in OPENING_WORDS):
            continue  # a name anyone can say: a capitalised word stays here unless it is a word of billing
        kept.append(word)
    return " ".join(kept)[:200]


def domains(case: Case) -> list[str]:
    """The hospital's own site, from the policy the case is checked against, and official law pages."""
    src = source.SOURCES.get(case.policy_id)
    host = (urlparse(src.url).hostname or "").removeprefix("www.") if src else ""
    return ([host] if host else []) + list(OFFICIAL)


def _allowed(url: str, allowed: list[str]) -> bool:
    parts = urlparse(url)
    host = (parts.hostname or "").removeprefix("www.")
    return parts.scheme == "https" and any(host == d or host.endswith("." + d) for d in allowed)


def _sentences(text: str) -> list[str]:
    out = []
    for raw in re.split(r"(?<=[.;:?!])\s+|\n+", text or ""):
        s = raw.strip(" \t#*>-|")
        if 40 <= len(s) <= 400 and re.search(r"[a-z]", s):
            out.append(s)
    return out


def _candidates(question: str, pages: list[dict]) -> list[tuple[str, dict]]:
    """Sentences that share words with the question, most shared first."""
    wanted = {w.lower() for w in _WORD.findall(question) if len(w) > 3}
    scored = []
    for page in pages:
        for s in _sentences(page.get("raw_content") or page.get("content") or ""):
            hits = len(wanted & {w.lower() for w in _WORD.findall(s)})
            if hits:
                scored.append((-hits, len(scored), s, page))
    return [(s, page) for _, _, s, page in sorted(scored, key=lambda x: x[:2])[:MAX_CANDIDATES]]


def pick_body(question: str, sentences: list[str]) -> dict:
    listing = "\n".join(f"W{i}. {s}" for i, s in enumerate(sentences, start=1))
    return {"model": MODEL, "store": False, "stream": True, "reasoning": {"effort": "low"}, "max_output_tokens": 600,
            "text": {"format": {"type": "json_schema", "name": "billradar_pick", "schema": PICK_SCHEMA, "strict": True}},
            "input": [{"role": "developer", "content": [{"type": "input_text", "text": PICK_INSTRUCTIONS}]},
                      {"role": "user", "content": [{"type": "input_text", "text": f"Question: {question}\n\n{listing}"}]}]}


ABOUT_THE_HOSPITAL = re.compile(r"(?i)\b(?:hospital|billing office|financial assistance|charity care|assistance policy|"
                                r"payment plan|itemized)\b")
SEARCH_INSTRUCTIONS = ("Search the web for an official answer to this question about a medical bill or health insurance. "
                       "Prefer government pages.")


def _tavily_pages(client, tavily: TavilyClient, cleaned: str, allowed: list[str]) -> list[dict]:
    res = tavily.search({"query": cleaned, "search_depth": "basic", "include_domains": allowed, "include_raw_content": True,
                         "max_results": 3}, label="web:search")
    return res.get("results") or []


def search_body(cleaned: str) -> dict:
    """Only the cleaned question goes in: Meta's search forms its own queries from this input."""
    return {"model": MODEL, "store": False, "stream": True, "reasoning": {"effort": "low"}, "max_output_tokens": 800,
            "max_tool_calls": 2, "tools": [{"type": "web_search"}], "include": ["web_search_call.results"],
            "input": [{"role": "developer", "content": [{"type": "input_text", "text": SEARCH_INSTRUCTIONS}]},
                      {"role": "user", "content": [{"type": "input_text", "text": cleaned}]}]}


def _meta_pages(client: MetaClient, tavily, cleaned: str, allowed: list[str]) -> list[dict]:
    res = client.respond(search_body(cleaned), label="spark:web-search")
    return [{"url": r.get("url", ""), "title": r.get("title", ""), "content": r.get("snippet", "")}
            for call in search_calls(res.events) for r in call.get("results") or []]


def _quote(client: MetaClient, cleaned: str, pages: list[dict]) -> tuple[str, dict] | None:
    found = _candidates(cleaned, pages)
    if not found:
        return None
    raw = json.loads(client.respond(pick_body(cleaned, [s for s, _ in found]), label="spark:web-pick").text)
    pick = str(raw.get("pick", "")).strip()
    if not re.fullmatch(r"W\d+", pick) or not 1 <= int(pick[1:]) <= len(found):
        return None
    quote, page = found[int(pick[1:]) - 1]
    if _key(quote) not in _key(page.get("raw_content") or page.get("content") or ""):
        return None  # code compares the quote with the page's own text, always
    return quote, page


def find(client: MetaClient, tavily: TavilyClient, case: Case, question: str) -> WebAnswer | None:
    cleaned = clean_question(question, case)
    if len(cleaned.split()) < MIN_WORDS:
        return None
    started = time.monotonic()
    allowed = domains(case)
    order = [_tavily_pages, _meta_pages] if ABOUT_THE_HOSPITAL.search(cleaned) else [_meta_pages, _tavily_pages]
    for search in order:
        try:
            pages = [r for r in search(client, tavily, cleaned, allowed) if _allowed(r.get("url", ""), allowed)]
            hit = _quote(client, cleaned, pages)
        except (TavilyError, MetaAPIError):
            continue  # one search down: the other still has a turn
        if hit:
            quote, page = hit
            return WebAnswer(quote, page["url"], page.get("title", ""), seconds=round(time.monotonic() - started, 2))
    return None


def ladder(client: MetaClient, case: Case, report: Report, question: str, tavily: TavilyClient | None = None) -> ask.Answer:
    a = ask.answer(client, case, report, question)
    if not a.refused or a.reason != "no_citation":
        return a
    try:
        web = find(client, tavily or TavilyClient(), case, question)
    except (TavilyError, MetaAPIError, ValueError):
        web = None  # a failed search ends the same way as an empty one
    if web:
        return ask.Answer(web.quote, replayed=a.replayed, source="web", web=web)
    return ask.Answer(NOT_IN_CASE, refused=True, reason="no_citation", replayed=a.replayed, source="none", say=ASK_IN_WRITING)
