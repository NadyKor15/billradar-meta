"""Keep names, IDs, addresses and account numbers on this computer: nothing leaves before they are closed.

Muse Glimmer, on this computer, reads every printed piece of a sheet (local_reader). A rule then decides what may leave:
a line opens only when its shape belongs to an allowed class (open_lines), and everything else is closed (closing).
This module keeps what the sheets of one case share: the family's values, one token each, the same on every sheet
("[ACCT_1]"), so the model can still link a bill to its insurance statement by token. Printed machine codes (the postal IMb
under an address, DataMatrix, QR, 1D bars) carry the same numbers for a scanner, so they are covered whole ("[CODE]").

`leaks()` reads the covered sheet back as a whole and looks for the family's values, mailing lines and machine codes on
it. The pipeline refuses to send an image with a leak.
"""

from __future__ import annotations

import hashlib
import io
import re
import threading
import unicodedata
from collections import Counter, OrderedDict
from dataclasses import dataclass, field
from functools import cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from billradar import local_reader, open_lines, sheet_pieces

LABELS: list[tuple[str, list[str]]] = [  # longest first inside each kind; order of kinds matters for "name"
    # a personal code to see or pay the bill online: "your personal statement code - PxvEVrdx"
    ("ACCESS", ["statement code", "access code", "activation code", "online code", "web code", "user id", "login id"]),
    ("SSN", ["social security number", "social security", "ssn"]),
    ("STMT", ["statement number", "statement no", "statement #", "stmt #", "stmt"]),
    ("DOB", ["date of birth", "birth date", "dob"]),
    ("MEMBER", ["member id", "member #", "member number", "subscriber id", "subscriber #", "policy number",
                "policy #", "group number", "group #", "medical record number", "medical record", "mrn", "mr number",
                "mr #", "id #", "id number"]),
    ("ACCT", ["account number", "account no", "account #", "acct #", "acct no", "guarantor number", "guarantor no",
              "guarantor id", "guarantor #", "account", "acct"]),
    ("GROUP", ["group name", "employer name", "employer"]),  # before PATIENT: "Group Name: X" is not a person
    ("CLAIM", ["claim number", "claim #", "claim no", "claim id", "claim"]),
    ("PATIENT", ["patient name", "patient", "guarantor", "subscriber", "member name", "member", "name"]),
    ("ADDR", ["address", "street"]),
    ("PHONE", ["telephone", "phone", "tel"]),
]
LEGAL = r"(?:LLC|L\.L\.C\.|Inc\.?|Corp\.?|Corporation|Co\.|Company|Ltd\.?)"
PATTERNS = [
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("PHONE", re.compile(r"\(?\b\d{3}\)?[\s.-]?\d{3}-\d{4}\b")),
    # values with no label of their own; where a pattern has a group, only the group is closed and its words stay
    ("ACCT", re.compile(r"(?i)\b(?:card|visa|mastercard|amex|discover|debit)\b[^\n\d]{0,24}?\b(?:ending|ends)\s*(?:in|with)?"
                        r"\s*[*x#.\s]*(\d{4})\b")),  # "Payment by card ending 4471"
    ("ACCT", re.compile(r"(?i)\bche(?:ck|que)\s*(?:no\.?|number|num\.?|#)\s*:?\s*(\d{3,})")),  # "check no. 20418"
    ("ACCT", re.compile(r"\bEFT\s*(?:no\.?|number|#|trace)?\s*:?\s*([A-Z0-9-]*\d[A-Z0-9-]{4,})")),  # "(EFT 00884127)"
    # NOT the tail of an ID ("His ID ends in -02"): two digits as a family value match every date, so the leak check held
    # every sheet back (sealed check 03.11, n3)
    ("DOB", re.compile(r"(?i)\b(?:d\.o\.b\.?|dob|date of birth|birth\s*date|born)\s*:?\s*"
                       r"((?:0?[1-9]|1[0-2])[/-](?:0?[1-9]|[12]\d|3[01])[/-](?:19|20)?\d{2})\b")),
    ("DOB", re.compile(r"(?<![\d/])((?:0?[1-9]|1[0-2])/(?:0?[1-9]|[12]\d|3[01])/(?:19\d{2}|200\d|201[0-4]))(?![\d/])")),  # no bill is that old
    ("GROUP", re.compile(r"\b(?:[Ww]ork(?:s|ed)?|[Ee]mployed)\s+(?:at|for|by)\s+((?:[A-Z][\w&'.-]*,?\s+){1,5}" + LEGAL + r")")),
    ("GROUP", re.compile(r"\b(?:Group|Employer)(?:\s+[Nn]ame)?\s*:?\s+((?:[A-Z][\w&'.-]*,?\s+){1,5}" + LEGAL + r")")),
    # NOT income: a sum with commas cannot be covered as a family value yet, so the leak check would hold the whole letter
    # back (sealed run 03.11: n1 S6, n2 S9); README says income on an assistance letter stays printed
]


def _pattern_span(m: re.Match) -> tuple[int, int]:
    return m.span(1) if m.re.groups else m.span()
# Printed mailing and scan lines carry no label but identify the letter and often the account:
#   "H2PX375M007494" (letters and digits in five runs or more), "449325560190000000DANIELA..." (a payment
#   scan line), "HLNX-H2PX375M-007494-001OF001" (four groups or more, 8 digits or more); see _mail_spans.
#   A service code with its words ("99222INITHOSPCARE") or a PO box has two runs and stays.
MAIL_WORD = re.compile(r"(?<![\w/-])[A-Z0-9]{10,}(?![\w/-])")
MAIL_GROUPS = re.compile(r"(?<![\w/#-])[A-Z0-9#]+(?:\s?-\s?[A-Z0-9#]+){2,}(?![\w/#-])")
# A residential line with its unit, for addresses the family did not type in: "9349 SEAGRAPE LN # 717", "12 Oak St Apt 4B".
# "Suite" is left out: that is how offices print theirs.
STREET_UNIT = re.compile(r"(?i)\b\d{1,6}\s*[a-z][a-z .]*?(?:ln|lane|st|street|ave|avenue|rd|road|dr|drive|way|blvd|"
                         r"ct|court|pl|place|cir|circle|ter|terrace|pkwy|hwy|trl)\.?\s*(?:apt|apartment|unit|#)\.?\s*#?\s*"
                         r"[a-z0-9-]{1,6}\b")
ZIP4 = re.compile(r"^\s?-\s?\d{4}(?!\d)")
HEADER_KINDS = ("ACCT", "MEMBER", "CLAIM", "ACCESS")
ID_ALONE = re.compile(r"^\W*([A-Za-z0-9][A-Za-z0-9-]{3,})\W*$")
UNIT_ALONE = re.compile(r"(?i)^\W*(?:(?:apt|apartment|unit)\.?\s*)?#?\s*([a-z]?\d{1,5}[a-z]?)\W*$")  # "STE 400" is an office
SEP = re.compile(r"^[\s:#.\-]*")
WORD_KINDS = {"PATIENT", "ADDR", "GROUP"}
# One of our own tokens drawn on the image, as OCR reads it back: "[PATIENT_1]", "L[PATIENT_1]", "[CIAIM81"
TOKEN_RX = re.compile(r"\[\s*[A-Z1Il]{3,8}\s*_?\s*\d+")
# The id itself at the start of a labelled value: "3270189, Provider: ..." -> "3270189"
ID_RX = re.compile(r"[\w/-]+(?:[ -][\w/-]*\d[\w/-]*)*")


def _fold(text: str) -> str:
    """Without accents: a profile says "María", a bill prints "MARIA"."""
    return "".join(ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch))


def compact(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", _fold(text).lower())


GLUED_TOKEN = re.compile(r"\[\s*(?:CODE|MAIL|ADDR|ACCT|PATIENT|MEMBER|CLAIM|PHONE|GROUP|ACCESS|STMT)\s*(?:_\s*\d+)?\s*\]?")
# Up to six letters of junk, up to two marks, then the code, which is no amount: it never runs into a dot, a comma or a slash.
GLUED_TAIL = re.compile(r"[A-Za-z]{0,6}[^\w]{0,2}([A-Za-z0-9-]+)(?![\d./,])")
TOKEN_KINDS = ["PATIENT", "MEMBER", "ACCESS", "CLAIM", "GROUP", "PHONE", "ACCT", "ADDR", "MAIL", "CODE", "STMT"]
_LOOKALIKE = str.maketrans("1L|!0", "IIIIO")


def _token_readback(value: str) -> bool:
    """A value that is one of our tokens as OCR misread it: a kind's name, one letter off, and a digit."""
    if not re.search(r"\d", value):
        return False
    v = re.sub(r"[^A-Z]", "", value.upper().translate(_LOOKALIKE))
    for kind in TOKEN_KINDS:
        k = kind.translate(_LOOKALIKE)
        for i in range(len(v) - len(k) + 1):
            if sum(a != b for a, b in zip(v[i:i + len(k)], k)) <= 1:
                return True
    return False




@dataclass
class Line:
    box: np.ndarray  # 4x2 corners
    text: str
    score: float
    turn: int = 0  # read on the sheet turned: characters do not run left to right across the box


READS_KEPT = 512  # only the lines are kept, not the images
READ_SCORE = 0.95  # Muse Glimmer gives no confidence; a piece it read counts as read
CLEAR_SHARE = 0.3  # below this share of real words the sheet lies turned, and is read again upright
TOKEN_ANY = re.compile(r"\[\s*[A-Z][A-Z0-9_ ]{1,14}\s*\]?")  # our own tokens read back
AMOUNT_READ = re.compile(r"\d[\d,]*\.\d{2}")
_reads: OrderedDict = OrderedDict()
_reads_lock = threading.Lock()


def _plain(text: str) -> str:
    """On these papers a lone accented letter is noise, and an accent is not worth a miss."""
    words = []
    for word in text.split():
        folded = _fold(word)
        if not (len(word) == 1 and folded != word):
            words.append(folded)
    return " ".join(words)






















SOFT = 100.0  # variance of the Laplacian in the cells with print: real sheets 318-1864, the same sheets blurred 3 px 13-55, 6 px 2-5 (03.11.2026)
SOFT_SCALE = 1400  # long side the check looks at: a sheet cut from a 4K frame and a phone photo are measured alike
SOFT_CELL = 48
SOFT_INK = 0.01  # share of dark pixels that makes a cell one with print


def too_soft(img: Image.Image) -> bool:
    """Is the print on the sheet soft? A person may read what the model cannot, so a clean check on a soft image proves nothing.
    Only cells with print count: empty paper says nothing about the ink, and a sharp barcode does not vouch for the words.
    A sharp page, however empty, and a blank page are fine."""
    import cv2
    gray = np.asarray(img.convert("L"))
    if (k := SOFT_SCALE / max(gray.shape)) < 1:
        gray = cv2.resize(gray, None, fx=k, fy=k, interpolation=cv2.INTER_AREA)
    dark = gray.astype(np.float32) < np.median(gray) - 30
    if dark.mean() <= 0.002:
        return False
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    rows = [lap[y:y + SOFT_CELL, x:x + SOFT_CELL].var()
            for y in range(0, gray.shape[0], SOFT_CELL) for x in range(0, gray.shape[1], SOFT_CELL)
            if dark[y:y + SOFT_CELL, x:x + SOFT_CELL].mean() > SOFT_INK]
    return not rows or float(np.percentile(rows, 75)) < SOFT


@dataclass
class Secret:
    kind: str
    value: str
    token: str


@dataclass
class Redaction:
    image: Image.Image
    secrets: list[Secret] = field(default_factory=list)  # every value covered on this image
    covered: int = 0

    @property
    def tokens(self) -> dict[str, str]:
        return {s.token: s.value for s in self.secrets}


STATE_NAMES = dict(pair.split(":") for pair in (
    "AL:Alabama|AK:Alaska|AZ:Arizona|AR:Arkansas|CA:California|CO:Colorado|CT:Connecticut|DE:Delaware|"
    "DC:District of Columbia|FL:Florida|GA:Georgia|HI:Hawaii|ID:Idaho|IL:Illinois|IN:Indiana|IA:Iowa|KS:Kansas|"
    "KY:Kentucky|LA:Louisiana|ME:Maine|MD:Maryland|MA:Massachusetts|MI:Michigan|MN:Minnesota|MS:Mississippi|"
    "MO:Missouri|MT:Montana|NE:Nebraska|NV:Nevada|NH:New Hampshire|NJ:New Jersey|NM:New Mexico|NY:New York|"
    "NC:North Carolina|ND:North Dakota|OH:Ohio|OK:Oklahoma|OR:Oregon|PA:Pennsylvania|RI:Rhode Island|"
    "SC:South Carolina|SD:South Dakota|TN:Tennessee|TX:Texas|UT:Utah|VT:Vermont|VA:Virginia|WA:Washington|"
    "WV:West Virginia|WI:Wisconsin|WY:Wyoming").split("|"))


def city_line(city: str, state: str, zip_code: str) -> list[str]:
    """'Bayside', 'FL', '33067' -> ['Bayside FL 33067', 'Bayside Florida 33067']: the city line as papers print it.
    City and ZIP together only: a bare ZIP would also match digits inside an amount."""
    if not (city.strip() and zip_code.strip()):
        return []
    st = state.strip()
    names = [st] + ([STATE_NAMES[st.upper()]] if st.upper() in STATE_NAMES else [])
    return [f"{city.strip()} {n} {zip_code.strip()}".replace("  ", " ") for n in names]


def name_variants(name: str) -> list[str]:
    """How papers print a person: 'Adrian James Castillo' -> 'Castillo Adrian James', 'Castillo Adrian',
    'Adrian Castillo'. Commas and case do not matter (values are compared letters and digits only)."""
    words = re.findall(r"[A-Za-z'-]+", _fold(name))
    if len(words) < 2:
        return []
    first, last, middle = words[0], words[-1], words[1:-1]
    out = [" ".join([last, first, *middle]), f"{last} {first}"]
    if middle:
        out.append(f"{first} {last}")
    return [v for v in dict.fromkeys(out) if compact(v) != compact(name)]


UNIT_RX = re.compile(r"[\s,]+(?:apt|apartment|unit|suite|ste|#)\.?\s*#?\s*(\w+)\s*$", re.I)
UNIT_WORDS = ["#", "Apt", "Apartment", "Unit", "Ste", "Suite"]


def _street_only(address: str) -> str:
    """'4089 Coral Reef Way Apt 400' -> '4089 Coral Reef Way': papers print the unit as 'Apt', '#' or 'Unit'."""
    return UNIT_RX.sub("", address).strip()


def _with_units(address: str) -> list[str]:
    """'9349 Seagrape Ln Apt 717' -> the same street with the unit as papers print it: '... Ln # 717', '... Ln Unit 717'.
    The street alone is covered too; without these the apartment number would stay readable next to its token."""
    m = UNIT_RX.search(address)
    if not m:
        return []
    street = address[:m.start()].strip()
    return [f"{street} {w} {m.group(1)}" for w in UNIT_WORDS]


def _mail_spans(text: str) -> list[tuple[int, int]]:
    out = []
    for m in MAIL_GROUPS.finditer(text):  # four groups and 8 digits, or three and 12: "292006-143-69524025"
        groups, digits = len(re.split(r"\s?-\s?", m.group())), len(re.sub(r"\D", "", m.group()))
        if (groups >= 4 and digits >= 8) or digits >= 12:
            out.append((m.start(), m.end()))
    for m in MAIL_WORD.finditer(text):
        v = m.group()
        runs, letters = re.findall(r"[A-Z]+|\d+", v), re.findall(r"[A-Z]+", v)
        digits, n_letters = len(re.sub(r"\D", "", v)), sum(map(len, letters))
        # "H2PX375M007494": five runs, letter runs short (a drug name in a merged service line is long);
        # a scan line: 20 digits, or 14 with a name between them. A date run into a revenue and a service code
        # ("20250302030850524HC", 17 digits) is a bill line the checks need.
        name_inside = n_letters >= 5 and re.search(r"\d{6}[A-Z]{5,}\d{6}", v)  # digits, a name, digits again
        if (len(runs) >= 5 and all(len(x) <= 4 for x in letters)) or digits >= 20 or (digits >= 14 and name_inside):
            out.append((m.start(), m.end()))
    return out


def _with_spellings(seed: dict[tuple[str, str], str]) -> dict[tuple[str, str], str]:
    """A person is also printed surname first: those spellings come after every given value, with the same token, and one
    person's spelling wins over a given value that reads the same once compacted."""
    spelled = dict(seed)
    for (kind, value), token in seed.items():
        if kind == "PATIENT":
            for variant in name_variants(value):
                spelled.setdefault((kind, variant), token)
    return spelled


class Vault:
    """Value -> token, shared across all images of one case so the same account gets the same token."""

    def __init__(self, known: list[tuple[str, str]] | None = None, seed: dict[tuple[str, str], str] | None = None):
        seed = dict(seed or {})
        self.by_value: dict[tuple[str, str], Secret] = {}
        self.counts: dict[str, int] = {}
        self.name_words: dict[str, Secret] = {}
        self.units: set[str] = set()
        self.orgs: set[str] = set()
        spelled = _with_spellings(seed)
        for (kind, value), token in spelled.items():
            self.by_value[(kind, compact(value))] = Secret(kind, value, token)
            number = re.sub(r"\D", "", token)
            self.counts[kind] = max(self.counts.get(kind, 0), int(number) if number else 0)
        keys = list(spelled)
        self.seeded = dict(self.by_value)
        for (kind, value) in seed:
            if kind != "PATIENT":
                continue
            words = re.findall(r"[A-Za-z'-]{3,}", _fold(value))
            if len(words) < 2:
                continue
            person = self.by_value[(kind, compact(value))]
            for word in (words[0], words[-1]):
                low = word.lower()
                for form in (low, re.sub(r"([a-z])\1", r"\1", low)):  # OCR drops one letter of a double
                    if len(form) >= 3:
                        self.name_words.setdefault(form, person)
        listed = [tuple(item) for item in (known or [])] + keys
        homes = [value for kind, value in listed if kind == "ADDR"]
        streets = [("ADDR", bare) for home in homes if (bare := _street_only(home)) != home]
        with_units = [("ADDR", form) for home in homes for form in _with_units(home)]
        self.known = [item for item in dict.fromkeys(listed + streets + with_units) if len(compact(item[1])) >= 3]
        self.units = {compact(m.group(1)) for home in homes if (m := UNIT_RX.search(home))}

    def token_for_label(self, kind: str, value: str) -> Secret:
        wanted = compact(value)
        same_person = next((secret for (k, known), secret in self.seeded.items()
                            if kind == k == "PATIENT" and len(known) >= 3 and (known in wanted or wanted in known)), None)
        return self.token(kind, value) if same_person is None else same_person

    def token(self, kind: str, value: str) -> Secret:
        slot = (kind, compact(value))
        if slot in self.by_value:
            return self.by_value[slot]
        self.counts[kind] = self.counts.get(kind, 0) + 1
        made = Secret(kind, value.strip(), f"[{kind}_{self.counts[kind]}]")
        self.by_value[slot] = made
        return made

    def dump(self) -> dict:
        """The vault as plain data, for the time between closing the sheets and sending them. It stays on this computer."""
        return {"by_value": [[k, c, s.kind, s.value, s.token] for (k, c), s in self.by_value.items()], "counts": self.counts,
                "seeded": [[k, c] for k, c in self.seeded], "name_words": {w: [s.kind, s.value, s.token] for w, s in self.name_words.items()},
                "known": [list(x) for x in self.known], "units": sorted(self.units), "orgs": sorted(self.orgs)}

    @classmethod
    def load(cls, data: dict) -> "Vault":
        v = cls()
        v.by_value = {(k, c): Secret(kind, value, token) for k, c, kind, value, token in data["by_value"]}
        v.counts = dict(data["counts"])
        v.seeded = {(k, c): v.by_value[(k, c)] for k, c in data["seeded"]}
        v.name_words = {w: Secret(*s) for w, s in data["name_words"].items()}
        v.known = [tuple(x) for x in data["known"]]
        v.units = set(data["units"])
        v.orgs = set(data["orgs"])
        return v

    @property
    def secrets(self) -> list[Secret]:
        return list(self.by_value.values())


@cache
def _label_rx(label: str) -> re.Pattern:
    """A label as OCR may print it: the spaces inside may be gone, and a letter may not touch it from the right
    (or, for a one-word label, from the left)."""
    words = label.split()
    left = r"(?<![a-z])" if len(words) == 1 else ""
    return re.compile(left + r"\s*".join(re.escape(w) for w in words) + r"(?![a-z])")


def _by_label(text: str, vault: Vault, learn: bool) -> list[tuple[int, int, Secret]]:
    """The value printed after a label ("Account: LDH-000123"). At most one hit per line: the first kind that gives one."""
    low = "".join(ch.lower() if len(ch.lower()) == 1 else ch for ch in text)
    for kind, labels in LABELS:
        for label in labels:
            hit = _label_rx(label).search(low)
            if hit is None:
                continue
            tail = text[hit.end():]
            sep = SEP.match(tail).group()
            start = hit.end() + len(sep)
            value = tail[len(sep):].strip()
            if kind not in WORD_KINDS and (ident := ID_RX.match(value)):
                value = ident.group()
            if TOKEN_RX.search(value) or re.search(r"[\[\]_]", value) or _token_readback(value[:12]):
                break  # that is one of our own tokens read back, not a value: no other label of this kind either
            if len(compact(value)) < 3:
                continue
            digits = len(re.sub(r"\D", "", value))
            if kind in WORD_KINDS:
                if ":" not in sep or (kind == "PATIENT" and not re.search(r"[A-Za-z]{2}", value)):
                    continue  # "Patient responsibility $2,575.10" is a heading
            elif kind == "ACCESS":
                if len(value) < 5 or not (digits or (re.search(r"[a-z]", value) and re.search(r"[A-Z]", value))):
                    continue
            elif not digits or (kind == "PHONE" and digits < 7):
                continue
            if not learn and (kind, compact(value)) not in vault.by_value:
                break  # a reading of what we drew ourselves, not a new value
            end = len(text) if kind in WORD_KINDS else start + len(value)
            return [(start, end, vault.token_for_label(kind, value))]
    return []


def _glued_ids(text: str, vault: Vault) -> list[tuple[int, int, Secret]]:
    """The rest of a machine code that sticks out right after one of our tokens ("[CODE" + "TMT237851G7")."""
    out = []
    for token in GLUED_TOKEN.finditer(text):
        tail = GLUED_TAIL.match(text, token.end())
        if tail and sum(c.isdigit() for c in tail.group(1)) >= ID_DIGITS:
            out.append((tail.start(1), tail.end(1), vault.token("MAIL", tail.group(1))))
    return out


def _known_values(text: str, vault: Vault) -> list[tuple[int, int, Secret]]:
    """Every value the vault knows, found by its letters and digits alone (OCR loses spaces)."""
    where: list[int] = []
    chars: list[str] = []
    for i, ch in enumerate(text):
        for c in _fold(ch).lower():
            if c.isalnum():
                where.append(i)
                chars.append(c)
    hay = "".join(chars)
    amounts = [(m.start(), m.end()) for m in AMOUNT_ON_LINE.finditer(text)]

    def at(pos: int, size: int) -> tuple[int, int]:
        return where[pos], where[pos + size - 1] + 1

    out = []
    for kind, value, secret in _everything_known(vault):
        needle = compact(value)
        if not needle:
            continue
        inside_sums_ok = bool(AMOUNT_ON_LINE.search(value)) or sum(c.isdigit() for c in needle) >= ID_DIGITS
        span = next((s for s in (at(p, len(needle)) for p in _found_at(hay, needle))
                     if inside_sums_ok or not _in_amount(amounts, *s)), None)
        if span is None and needle.isdigit() and len(needle) >= ID_DIGITS and (part := _partial(needle, hay)):
            cut = at(part[0], len(part[1]))  # a digit lost under a cover
            span = None if _in_amount(amounts, *cut) else cut
        if span is None:
            continue
        start, end = span
        if kind == "ADDR" and re.search(r"\d{5}$", value.strip()) and (zip4 := ZIP4.match(text[end:])):
            end += zip4.end()
        out.append((start, end, secret if secret is not None else vault.token(kind, value)))
    return out


def _spans(text: str, vault: Vault, learn: bool = True) -> list[tuple[int, int, Secret]]:
    """What on this line must be closed, and whose it is. Tokens are made as things are found, in the order below:
    the numbers in `[MAIL_1]`, `[ADDR_2]` depend on it."""
    found = _by_label(text, vault, learn)
    for kind, pattern in PATTERNS:
        found += [(*_pattern_span(m), vault.token(kind, text[slice(*_pattern_span(m))])) for m in pattern.finditer(text)]
    found += _glued_ids(text, vault)
    for word, person in vault.name_words.items():
        found += [(m.start(), m.end(), person) for m in _name_word_rx(word).finditer(text)]
    found += [(a, b, vault.token("MAIL", text[a:b])) for a, b in _mail_spans(text)]
    found += [(m.start(), m.end(), vault.token("ADDR", m.group())) for m in STREET_UNIT.finditer(text)]
    return found + _known_values(text, vault)


ID_DIGITS = 6
AMOUNT_ON_LINE = re.compile(r"(?<![\w.,])(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}(?![\d.,]*\d)|\$\s?\d[\d,]*(?:\.\d{2})?")


def _in_amount(amounts: list[tuple[int, int]], start: int, end: int) -> bool:
    return any(start < b and end > a for a, b in amounts)


def _found_at(hay: str, needle: str):
    pos = hay.find(needle)
    while pos >= 0:
        yield pos
        pos = hay.find(needle, pos + 1)


@cache
def _name_word_rx(word: str) -> re.Pattern:
    # OCR runs words together ("Daniela'svisit"): the name ends at a non-letter or where a capital starts the next word
    w = re.escape(word)
    return re.compile(r"(?<![A-Za-z])(?i:" + w + r")(?:['’]?s)?(?![A-Za-z])|(?<![A-Za-z])" + re.escape(word.capitalize())
                      + r"(?:['’]?s)?(?=[A-Z])")


def _partial(needle: str, hay: str) -> tuple[int, str] | None:
    """An all-digit value of 6 digits or more with its first or last digit missing, as a run of digits of its own."""
    if not needle.isdigit() or len(needle) < 6:
        return None
    for part in (needle[:-1], needle[1:]):
        for m in re.finditer(re.escape(part), hay):
            before = hay[m.start() - 1] if m.start() else ""
            after = hay[m.end()] if m.end() < len(hay) else ""
            if not before.isdigit() and not after.isdigit():
                return m.start(), part
    return None


def _everything_known(vault: Vault) -> list[tuple[str, str, Secret | None]]:
    """What the family typed in, plus every value already found next to a label on any sheet:
    an account number labelled on one sheet is covered on the next sheet too, label or not."""
    seen, out = set(), []
    for kind, value in vault.known:
        out.append((kind, value, None))
        seen.add(compact(value))
    for s in vault.secrets:
        v = compact(s.value)
        if len(v) >= 3 and v not in seen and not TOKEN_RX.search(s.value):
            out.append((s.kind, s.value, s))
            seen.add(v)
    return out


def _alnum_map(text: str) -> tuple[list[int], str]:
    idx = [i for i, ch in enumerate(text) if ch.isalnum()]
    return idx, "".join(text[i] for i in idx).lower()






@cache
def _font(size: int):
    candidates = ["/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/Library/Fonts/Arial Bold.ttf",
                  "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
    opened = None
    while candidates and opened is None:
        try:
            opened = ImageFont.truetype(candidates.pop(0), size)
        except OSError:
            pass  # not installed here: the next one
    return ImageFont.load_default() if opened is None else opened




def _text_height(lines: list[Line], img_h: int) -> float:
    hs = [float(np.ptp(line.box[:, 1])) for line in lines if line.score >= 0.6 and len(compact(line.text)) >= 2]
    hs = [h for h in hs if h > 0]
    return float(np.median(hs)) if hs else max(8.0, 0.012 * img_h)


def _ink(img: Image.Image, h: float) -> np.ndarray:
    import cv2
    gray = np.asarray(img.convert("L"))
    block = max(9, int(0.6 * h) | 1)  # about a letter wide: inside a dense code the modules still come apart
    return cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, block, 15)


def _in_text(box: tuple[int, int, int, int], lines: list[Line]) -> bool:
    """Most of the box sits inside a line OCR read as text: a letter, not a code."""
    x0, y0, x1, y1 = box
    area = max(1, (x1 - x0) * (y1 - y0))
    for line in lines:
        if line.score < 0.6 or len(compact(line.text)) < 2:
            continue
        lx0, ly0 = line.box.min(axis=0)
        lx1, ly1 = line.box.max(axis=0)
        w, hh = min(x1, lx1) - max(x0, lx0), min(y1, ly1) - max(y0, ly0)
        if w > 0 and hh > 0 and w * hh >= 0.4 * area:
            return True
    return False


def _bar_runs(ink: np.ndarray, h: float) -> list[tuple[int, int, int, int]]:
    """Rows of thin bars set close together: the postal IMb (four heights), Code 128 and the like.
    Twenty elements or more, five of them tall; a dotted leader line ("Total .....") has no tall ones."""
    import cv2
    n, _, st, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    elems = sorted((int(x), int(y), int(w), int(hh)) for x, y, w, hh, a in st[1:]
                   if w <= max(2.0, 0.3 * h) and 0.12 * h <= hh <= 5 * h and a >= 2)
    runs: list[list[tuple[int, int, int, int]]] = []
    for e in elems:  # each element joins the run it continues; text just above or below keeps its own runs
        for run in runs:
            px, py, pw, ph = run[-1]
            gap = e[0] - (px + pw)
            if -1 <= gap <= max(3.0, 0.45 * h) and min(py + ph, e[1] + e[3]) - max(py, e[1]) >= 1:
                run.append(e)
                break
        else:
            runs.append([e])
    out = []
    for r in runs:
        if len(r) >= 20 and sum(e[3] >= 2 * e[2] and e[3] >= 0.4 * h for e in r) >= 5:
            out.append((min(e[0] for e in r), min(e[1] for e in r), max(e[0] + e[2] for e in r), max(e[1] + e[3] for e in r)))
    return out


def _inked_corners(patch: np.ndarray) -> bool:
    """DataMatrix prints an L along two sides, QR a square in three corners: two corners at least hold ink."""
    k = max(2, min(patch.shape) // 6)
    corners = (patch[:k, :k], patch[:k, -k:], patch[-k:, :k], patch[-k:, -k:])
    return sum(float(c.mean()) >= 0.15 for c in corners) >= 2


def _squares(ink: np.ndarray, h: float, lines: list[Line], rgb: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Dense square patches outside the text: DataMatrix and QR. Ink crosses each row and each column of
    the patch many times and is black; a letter, a ring or icon, a coloured logo or a box around a form field
    is not like that."""
    import cv2
    k = max(2, int(round(0.12 * h)))
    closed = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, np.ones((k, k), np.uint8))
    contours, _ = cv2.findContours(closed, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)  # a code inside a printed box too
    out = []
    for c in contours:
        x, y, w, hh = cv2.boundingRect(c)
        square = 0.7 * h <= w <= 10 * h and 0.75 <= w / max(1, hh) <= 1.33
        block = 0.6 * h <= hh <= 3 * h and w >= 1.8 * hh  # 1D bars printed so fine they run together
        if not (square or block):
            continue
        patch = ink[y:y + hh, x:x + w] > 0
        fill = patch.mean()
        across = np.abs(np.diff(patch.astype(np.int8), axis=1)).sum(axis=1).mean()
        down = np.abs(np.diff(patch.astype(np.int8), axis=0)).sum(axis=0).mean()
        crossings = min(across, down)  # big modules cross fewer times per pixel, but many times in all
        if square and not (0.3 <= fill <= 0.85 and (crossings >= 10 or crossings >= max(3.0, 0.16 * max(w, hh)))):
            continue
        if square and max(w, hh) <= 2 * h and not _inked_corners(patch):
            continue  # a round icon: an "i" in a ring. A code the size of two letters still fills its corners
        # bars run the full height of the code; letters, and words joined by an underline, do not
        if not square and not (0.3 <= fill <= 0.9 and across >= max(8.0, 0.2 * w) and down <= 3
                               and (patch.mean(axis=0) >= 0.85).mean() >= 0.3):
            continue
        px = rgb[y:y + hh, x:x + w][patch].astype(np.int16)
        colour = float((px.max(axis=1) - px.min(axis=1)).mean()) if len(px) else 0.0
        if colour <= 40 and not _in_text((x, y, x + w, y + hh), lines):
            out.append((x, y, x + w, y + hh))
    return out


def _qr(img: Image.Image) -> list[tuple[int, int, int, int]]:
    """QR codes by their three finder squares (opencv), also when a label printed under the code ("SCAN TO PAY")
    joins it into one blob that is no longer square."""
    import cv2
    try:
        ok, pts = cv2.QRCodeDetector().detectMulti(np.asarray(img.convert("L")))
    except cv2.error:
        return []
    if not ok or pts is None:
        return []
    return [(int(q[:, 0].min()), int(q[:, 1].min()), int(q[:, 0].max()) + 1, int(q[:, 1].max()) + 1) for q in pts]


JPEG_QUALITY = 88  # what leaves the device


def as_sent(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=JPEG_QUALITY)
    return buf.getvalue()


def _overlap(a: tuple, b: tuple) -> bool:
    return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])


def codes(img: Image.Image, lines: list[Line] | None = None) -> list[tuple[int, int, int, int]]:
    """Printed machine codes on the image, as boxes (x0, y0, x1, y1). The sheet is looked at as it will be sent too: a
    code just under the threshold on the sheet can stand over it once compressed, and the JPEG is what leaves."""
    lines = ocr(img) if lines is None else lines
    h = _text_height(lines, img.height)

    def printed(image: Image.Image) -> list[tuple[int, int, int, int]]:
        ink = _ink(image, h)
        return _bar_runs(ink, h) + _squares(ink, h, lines, np.asarray(image.convert("RGB")))

    found = printed(img)
    found += [b for b in printed(Image.open(io.BytesIO(as_sent(img)))) if not any(_overlap(b, x) for x in found)]
    return found + _qr(img)


def _cover_box(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], h: float, token: str = "[CODE]") -> None:
    x0, y0, x1, y1 = box
    pad = max(4, int(0.3 * h))
    rect = (max(0, x0 - pad), max(0, y0 - pad), x1 + pad, y1 + pad)
    draw.rectangle(rect, fill=(250, 250, 248))
    size = max(10, int(min(h * 0.6, (rect[3] - rect[1]) * 0.8)))
    draw.text((rect[0] + 2, rect[1] + max(1, (rect[3] - rect[1] - size) // 2)), token, fill=(40, 80, 160), font=_font(size))


def _same_row(a: Line, b: Line) -> bool:
    _, ay0 = a.box.min(axis=0)
    _, ay1 = a.box.max(axis=0)
    _, by0 = b.box.min(axis=0)
    _, by1 = b.box.max(axis=0)
    return min(ay1, by1) - max(ay0, by0) >= 0.5 * min(ay1 - ay0, by1 - by0)




def _header_values(lines: list[Line], vault: Vault, learn: bool) -> list[tuple[Line, Secret]]:
    """A column header with its value in the cell under it: "Patient Account Num" / "4788416", or one column of a
    header row ("Statement Date  Due Date  Guarantor #  Amount Due" / "... 847673833 ..."): the value must sit
    under the label's own words."""
    out = []
    for a in lines:
        idx, flat = _alnum_map(a.text)  # OCR runs header words together: "PatientAccount Num"
        hit = next(((k, flat.find(compact(lb)), len(compact(lb))) for k, labels in LABELS if k in HEADER_KINDS
                    for lb in labels if len(compact(lb)) >= 4 and compact(lb) in flat), None)
        if not hit or len(a.text.split()) > 12:
            continue
        kind, pos, n = hit
        ax0, _ = a.box.min(axis=0)
        ax1, ay1 = a.box.max(axis=0)
        h = max(1.0, float(np.ptp(a.box[:, 1])))
        per_char = (ax1 - ax0) / max(1, len(a.text))
        lx0, lx1 = ax0 + idx[pos] * per_char, ax0 + (idx[pos + n - 1] + 1) * per_char
        if re.search(r"\d", a.text[idx[pos]:]):  # the label has its value on its own line: the line pass covers it
            continue
        for b in lines:
            bx0, by0 = b.box.min(axis=0)
            bx1, _ = b.box.max(axis=0)
            # "Account Number:" with its value further along the same row, in a box of its own
            if b is not a and _same_row(a, b) and 0 <= bx0 - ax1 <= 20 * h and a.text.rstrip().endswith((":", "#")):
                digits = len(re.sub(r"\D", "", b.text))
                if digits >= 5 and not re.search(r"[$/]", b.text) and ID_RX.fullmatch(b.text.strip()) and (
                        learn or (kind, compact(b.text)) in vault.by_value):
                    out.append((b, 0, len(b.text), vault.token(kind, b.text.strip())))
                continue
            if b is a or not (0 <= by0 - ay1 <= 1.5 * h) or min(lx1, bx1) - max(lx0, bx0) <= -3 * per_char:
                continue
            b_char = (bx1 - bx0) / max(1, len(b.text))
            for m in re.finditer(r"\S+", b.text):  # the cell under the label: a whole row may read as one line
                cx0, cx1 = bx0 + m.start() * b_char, bx0 + m.end() * b_char
                value = m.group().strip(".,;:()")
                if min(lx1, cx1) - max(lx0, cx0) <= -2 * per_char or re.search(r"[$/]", value):
                    continue
                if len(re.sub(r"\D", "", value)) < 5 or not ID_ALONE.match(value):
                    continue
                if not learn and (kind, compact(value)) not in vault.by_value:
                    continue
                out.append((b, m.start(), m.end(), vault.token(kind, value)))
    return out


# "77953", "480004 - 440", "4744 500976": digits in one to three groups, five at least, no $, no decimals










UNIT_ANYWHERE = re.compile(r"(?i)(?:apt|apartment|unit|#)\.?\s*#?\s*([a-z]?\d{1,5}[a-z]?)\b")




def _units_left(lines: list[Line], units: set[str], anywhere: bool = False) -> list[Line]:
    """Lines that still print one of the family's apartment numbers: alone ("# 717"), or with anywhere=True also
    after a word or token ("[ADDR_1] # 717", "Apt 717")."""
    out = []
    for line in lines:
        m = UNIT_ALONE.match(line.text)
        hits = [m.group(1)] if m else []
        if anywhere:
            hits += [x.group(1) for x in UNIT_ANYWHERE.finditer(line.text)]
        if any(compact(x) in units for x in hits):
            out.append(line)
    return out








SERVICE_CODE = re.compile(r"(?<![\d.,$/-])(\d{5}|0\d{3})(?![\d.,/-])")














def sam_copy(img: Image.Image, max_side: int = 900, secrets: list[Secret] | None = None,
             tries: int = 4) -> Image.Image:
    """What SAM gets: small and soft, enough to see the sheets' edges, not to read them.
    With `secrets`, the copy is checked by OCR and blurred more until none of them can be read."""
    small = img.convert("RGB").copy()
    small.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    radius = max_side / 150
    for _ in range(tries):
        soft = small.filter(ImageFilter.GaussianBlur(radius=radius))
        if not secrets or not leaks(soft, secrets, edge=False):
            return soft
        radius *= 1.6
    raise RuntimeError("could not make the photo unreadable for SAM; not sending it")


@dataclass
class Reading:
    lines: list[Line]  # on the sheet as it stands upright
    h: int  # type height
    turn: int = 0  # the clockwise turn that made it upright


_read_backs: OrderedDict = OrderedDict()
_untouched: OrderedDict = OrderedDict()  # covered image -> sums whose pixels closing left as printed


def _key(img: Image.Image) -> tuple:
    rgb = img.convert("RGB")
    return rgb.size, hashlib.sha1(rgb.tobytes()).digest()


def _kept(store: OrderedDict, key: tuple, value) -> None:
    with _reads_lock:
        store[key] = value
        while len(store) > READS_KEPT:
            store.popitem(last=False)


def _quad(box: tuple) -> np.ndarray:
    x0, y0, x1, y1 = box
    return np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], dtype=np.float32)


def _lines_of(pairs: list[tuple[str, tuple]]) -> list[Line]:
    return [Line(_quad(box), _plain(TOKEN_ANY.sub(" ", text)), READ_SCORE) for text, box in pairs]


def restore(img: Image.Image, stored: list, h: int, turn: int = 0) -> None:
    """A reading kept with a case comes back: an image that was read needs no model the second time."""
    _kept(_reads, _key(img), Reading(lines_from(stored), h, turn))


def reading_of(img: Image.Image) -> dict:
    r = _reading(img)
    return {"lines": stored_lines(img), "h": r.h, "turn": r.turn}


def lines_from(stored: list) -> list[Line]:
    """Lines kept with a case: [[text, [x0, y0, x1, y1]], ...]."""
    return [Line(_quad(tuple(box)), text, READ_SCORE) for text, box in stored]


def stored_lines(img: Image.Image) -> list:
    return [[ln.text, [int(v) for v in (*ln.box.min(axis=0), *ln.box.max(axis=0))]] for ln in _reading(img).lines]


def _clear_share(lines: list[Line]) -> float:
    """How much of what was read is words. A sheet lying on its side or upside down reads as noise."""
    read = [ln for ln in lines if re.search(r"[A-Za-z]{3}", ln.text)]
    if not read:
        return 0.0
    return sum(open_lines._word_ok(ln.text.split()[0], open_lines.WIDE) for ln in read) / len(read)


def remember(img: Image.Image, tags: list, h: int) -> None:
    """The reading of an image that needs no model: a PDF's text layer, the open pieces of a covered sheet."""
    _kept(_reads, _key(img), Reading(_lines_of([(t.text, t.box) for t in tags]), h))


def _reading(img: Image.Image) -> Reading:
    """Every piece of the image as it stands, once: learning a sheet, closing it and checking it use the same reading."""
    key = _key(img)
    with _reads_lock:
        hit = _reads.get(key)
        if hit is not None:
            _reads.move_to_end(key)
    if hit is not None:
        return hit
    rgb = img.convert("RGB")
    pairs, h = local_reader.read_pieces(rgb)
    lines, turn = _lines_of(pairs), 0
    if _clear_share(lines) < CLEAR_SHARE and (turn := local_reader.turn_of(rgb)):
        pairs, h = local_reader.read_pieces(rgb.rotate(-turn, expand=True))
        lines = _lines_of(pairs)
    hit = Reading(lines, h, turn)
    _kept(_reads, key, hit)
    return hit


def upright(img: Image.Image) -> Image.Image:
    turn = _reading(img).turn
    return img.rotate(-turn, expand=True) if turn else img


def ocr(img: Image.Image) -> list[Line]:
    """The printed lines of an image, with their boxes on the upright sheet."""
    return [Line(ln.box.copy(), ln.text, ln.score) for ln in _reading(img).lines]


def _tags(reading: Reading) -> list:
    return [open_lines.Tag(i, ln.text, tuple(int(v) for v in (*ln.box.min(axis=0), *ln.box.max(axis=0)))) for i, ln in enumerate(reading.lines, start=1)]


def learn_tags(tags: list, h: int, vault: Vault) -> None:
    """The same as learn(), for lines whose text is known already: a PDF's text layer."""
    lines = _lines_of([(t.text, t.box) for t in tags])
    for line in lines:
        _spans(line.text, vault)
    _header_values(lines, vault, True)
    vault.orgs |= open_lines.org_words(tags, open_lines.decide(tags, h, closing.known_of(vault)))


def learn(img: Image.Image, vault: Vault) -> int:
    """Register every labelled value on this image (no drawing). All sheets are learned before any is closed, so a number
    labelled on sheet 10 is closed on sheet 9 as well. Returns how many there were."""
    reading = _reading(img)
    before = len(vault.by_value)
    for line in reading.lines:
        _spans(line.text, vault)
    _header_values(reading.lines, vault, True)
    tags = _tags(reading)
    vault.orgs |= open_lines.org_words(tags, open_lines.decide(tags, reading.h, closing.known_of(vault)))
    return len(vault.by_value) - before


def redact(img: Image.Image, vault: Vault, learn: bool = True) -> Redaction:
    reading = _reading(img)
    if learn:
        globals()["learn"](img, vault)
    tags = _tags(reading)
    verdicts = open_lines.decide(tags, reading.h, closing.known_of(vault), vault.orgs)
    page = img.convert("RGB").rotate(-reading.turn, expand=True) if reading.turn else img.convert("RGB")
    kept_sums: Counter = Counter()
    out = closing.close(page, tags, verdicts, vault, reading.h, kept_sums)
    open_tags = []
    for t in tags:
        v = verdicts[t.n]
        if v.how == "open":  # what is printed on the covered sheet: later steps read this, with no model
            seen = list(t.text)
            for a, b, _ in v.hide:
                seen[a:b] = " " * (b - a)
            open_tags.append(open_lines.Tag(t.n, "".join(seen), t.box))
    remember(out, open_tags, reading.h)
    _kept(_untouched, _key(out), kept_sums)
    closed = sum(v.how != "open" for v in verdicts.values())
    return Redaction(out, vault.secrets, closed)


def read_back(img: Image.Image) -> str:
    """The whole image read as one, once: what can be read on it with no help from the boxes."""
    key = _key(img)
    with _reads_lock:
        hit = _read_backs.get(key)
    if hit is None:
        hit = local_reader.transcribe(img)
        _kept(_read_backs, key, hit)
    return hit


def _still_printed(secret: Secret, rows: list[str], whole: str, without_sums: str) -> bool:
    """Is this family value still readable in the rows the closed image read back as?"""
    flat = compact(secret.value)
    if secret.kind in WORD_KINDS:
        words = [w for w in re.findall(r"[A-Za-z'’-]+", _fold(secret.value)) if len(w) >= 3]
        if len(words) == 1:  # one word of a name: whole words only ("sibility" sits inside "Responsibility")
            rx = _name_word_rx(words[0])
            return any(rx.search(r) for r in rows)
    text = whole if AMOUNT_ON_LINE.search(secret.value) else without_sums
    digits = re.sub(r"\D", "", flat)
    if flat in text or _partial(flat, text) is not None:
        return True
    if len(digits) < ID_DIGITS:
        return False
    # a long number: its digits anywhere in the text (neighbouring rows run together: stricter, on purpose), or in one row
    # of its own, where it may print as a sum
    return digits in re.sub(r"\D", "", text) or any(digits in re.sub(r"\D", "", compact(r)) for r in rows)


def _on_edge(img: Image.Image) -> list[Secret]:
    """Printed machine codes on the image, one Secret each (the sheet's pieces tell the codes where text stands)."""
    boxes, _ = sheet_pieces.pieces(img)
    lines = [Line(_quad(box), "xxxx", READ_SCORE) for box in boxes.values()]
    return [Secret("CODE", f"code at {box[0]},{box[1]}", "[CODE]") for box in codes(img, lines)]


def leaks(img: Image.Image, secrets: list[Secret], units: set[str] | frozenset = frozenset(),
          names: dict[str, Secret] | None = None, edge: bool = True) -> list[Secret]:
    """Read the closed image whole and list what is still on it. Empty means it may leave. Nothing is merged or dropped:
    callers print how many were found."""
    rows = [TOKEN_ANY.sub(" ", _plain(raw)) for raw in read_back(img).splitlines() if raw.strip()]
    whole = " ".join(map(compact, rows))
    without_sums = " ".join(compact(AMOUNT_ON_LINE.sub(" ", r)) for r in rows)
    found = [s for s in secrets if compact(s.value) and _still_printed(s, rows, whole, without_sums)]
    for row in rows:
        found += [Secret("PATIENT", w, "[PATIENT]") for w in (names or ()) if _name_word_rx(w).search(row)]
        found += [Secret("MAIL", row[a:b], "[MAIL]") for a, b in _mail_spans(row)]
        found += [Secret("ADDR", m.group(), "[ADDR]") for m in STREET_UNIT.finditer(row)]
    plain = [Line(_quad((0, 0, 1, 1)), r, READ_SCORE) for r in rows]
    found += [Secret("ADDR", ln.text, "[ADDR]") for ln in _units_left(plain, set(units), anywhere=True)]
    return found + (_on_edge(img) if edge else [])


def amounts_gone(original: Image.Image, covered: Image.Image) -> list[str]:
    """Sums on the sheet that cannot be read on what is about to leave, counted: a sum printed twice may lose one. The clean sheet
    is read whole for this, apart from its pieces: a piece left empty hides its sum from a count made of pieces.
    A whole read can repeat a long column or skip a row, so a difference in number has to hold on a second pair of reads.
    A sum in an open piece went back pixel by pixel: it is there, whatever a whole read skipped.
    A sum that no read finds on the covered sheet holds it at once."""
    def sums(text: str) -> Counter:
        return Counter(AMOUNT_READ.findall(text))

    pieces = sums(" ".join(ln.text for ln in _reading(original).lines))
    want, have = sums(read_back(original)) | pieces, sums(read_back(covered)) | _untouched.get(_key(covered), Counter())
    if not want - have:
        return []
    have |= sums(local_reader.transcribe(covered, again=True))
    want2 = sums(local_reader.transcribe(original, again=True)) | pieces
    gone_whole = Counter({a: n for a, n in want.items() if not have[a]})
    return sorted((((want & want2) | gone_whole) - have).elements())


from billradar import closing  # noqa: E402  closing draws with this module's tokens and fonts
