"""Which printed line may leave this computer. A pure function: no model, no image.

Everything is closed by default. A line opens only when its shape belongs to an allowed class: a sum, a date
under a listed label or on a service line, a service code on a service line, the description of a service, a
column label, a sentence of ordinary words, the name of an organization. Ordinary words are not enough: a name
or an address made of dictionary words has none of these shapes, so it stays closed.

The value after a person's or a number's label (Patient:, Guarantor:, Member ID:, Claim #:, To:) is always closed.
The label stays: the reader needs to see what stood there.
"""

from __future__ import annotations

import gzip
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

LISTS = Path(__file__).parent / "wordlists"


def _words(name: str) -> set[str]:
    return {w for w in (LISTS / name).read_text(encoding="utf-8").split() if w}


def english() -> set[str]:
    with gzip.open(LISTS / "english.txt.gz", "rt", encoding="utf-8") as f:
        return {w for w in f.read().split() if w}


NAMES = _words("first_names.txt") | _words("surnames.txt") | {
    "grace", "rose", "mark", "bill", "hope", "faith", "joy", "may", "june", "april", "august", "dawn", "summer", "autumn", "amber", "ruby",
    "pearl", "violet", "lily", "iris", "ivy", "holly", "hazel", "jasmine", "olive", "penny", "sandy", "wade", "drew", "dale", "dean", "earl",
    "frank", "gene", "hank", "herb", "jack", "jean", "jewel", "lance", "miles", "nick", "norm", "pat", "pete", "ray", "reed", "rich", "rob",
    "rod", "sue", "ted", "victor", "will", "woody", "hill", "park", "oak", "lane", "street",
}

FUNCTION = set("a about after all also an and any are as at be been before but by can could do does each for from has have if in into is it its may "
               "more most must no not of on one only or our out over per please should so some than that the their them then there these they this "
               "those to under until up upon us was we were what when where which who why will with within without would you your".split())

_LABEL_WORDS = set(
    "accepted account accounts action address adjusted adjustment adjustments administrator agreement allowable allowed amount amounts annual appeal "
    "appeals applied applies apply approved assignment assistance authorization available balance balances benefit benefits billed billing "
    "breakdown calendar call care carrier cash category center change changes charge charged charges check checks claim claims clinic code "
    "codes coinsurance collected collection collections company complete condition confirmation contact contract contractual copay copayment "
    "copays cost costs coverage covered credit credits current customer date dated dates day days decision deductible denied denial department "
    "description detach detail details determination diagnosis difference disallowed discount discounts dispute document documents due "
    "duplicate effective electronic eligible emergency enclosed encounter estimate estimated exceeds exclusion expenses expired explanation "
    "facility family federal fee fees file final financial following form forms group guarantee help home hospital hospitalization hours "
    "identification important inc included includes incorrect indicate individual information initial inpatient inquiry instructions insurance "
    "insurer interest invoice issued item items itemized language late later level liability lifetime limit limits line lines list "
    "location mail maximum medical member members message method minimum mode month monthly months name net network new next non notes notice "
    "number numbers office online open option options order original other outpatient outstanding overpayment owe owed owes page paid "
    "participant partial past patient pay payable payer payment payments payor payee pending percent period phone physician plan plans "
    "please pocket policy portion post posted preauthorization preferred premium prescription previous price primary prior "
    "procedure procedures process processed processing professional program provider providers purposes qty quantity questions rate rates "
    "reason reasons receipt receive received record records reduction reference referral refund regarding regional reimbursement related "
    "remark remarks remit remittance rendered reply request requested required requirements responsibility responsible result results retain "
    "return reverse review revenue right rights rx save schedule scheduled secondary section secure self send sent service services "
    "share sign signature size sponsor standard state statement status submit submitted subscriber subtotal summary support tax taxes "
    "telephone terms thank through time today total totals treatment type types unit units unpaid update usual value verify visit visits "
    "waived website withheld write written year years".split())
_GENERAL = set(
    "able access accept account additional address advance agree allow already always amount another answer appear appears apply arrange ask "
    "automatic avoid back bank based because become begin being below best between both box bring business card cards carefully case cause "
    "certain charge choose clinical collect come commercial communication complaint concerning confidential consider continue contracted "
    "correct cover create debit deliver determine different directly discuss do done during each early either else end ensure enter even "
    "every example except explain extended fair find first free full further general get give given go good grievance guide have helpful "
    "here hold how however id immediate immediately include including instead issue keep kind know law laws legal less letter like limited "
    "long look made mailing make making many mean means meet might need needed needs never new no note now obtain offer official once "
    "online ongoing opportunity outside own part parties party payable pays people perform personal place possible prepared present "
    "print prompt protect provide provided providing public purpose put quality read ready really reasonable recently regular remain "
    "remaining reminder report represent resolve respond response review rule rules same scan second see select separate serve set "
    "several show similar since social specific subject such suite sure take tell thanks time timely told tomorrow too transaction true "
    "try understand unable unless use used using usually very view want way ways well while wish work would yes".split())
_ADD_BACK = set(
    "and arm back bed blood body bone brain breast care chest clot cord day delivery ear eye face female fetus fetuses fetal foot full "
    "hand head heart heel high hip iv kidney knee lab labor leg level limited liver long low lung male nerve newborn nose nurse or pain "
    "pap pelvis post pre red room semi short skin spine stay supply test tests tissue visit vaginal wrist white x xray pat ice pack tray perineal perineum "
    "episiotomy amniotic oxytocin placenta uterus cervix tab syringe".split())
_ABBR = set(
    "adj amt anes appt aso asst bal bcbs ben chg chgs cob coins cpt cr deduct descr desc dept drg dx eob eobs est exp fap fsa hcpcs hipaa "
    "hmo hosp hsa icd init ip lab ltd mo mod npi ob oop op ot pcp pmt pmts ppo pt pts rev rx sim svc svcs tx ucr us vag yr yrs ytd "
    "gyn ob/gyn ins cplx deliv co bill commercial medicare medicaid clinician holder admit admission admitting discharge dt px dollars consulting ordering "
    "hospitalists hospitalist neonatology neonatologist cardiology pulmonary specialist nuc imaging "
    "antepartum postpartum perinatal prenatal neonatal ultrasound sonogram obstetric obstetrical obstetrics gynecology epidural anesthesiology anesthesiologist "
    "cesarean nicu pediatrician newborn mammogram electrocardiogram echocardiogram laparoscopic endoscopy colonoscopy immunization vaccination vaccine".split())
# Billing words that are also surnames: a label needs another word beside them that is not.
AMBIGUOUS = (_LABEL_WORDS | _ABBR) & NAMES
LABELS = _LABEL_WORDS | _ABBR
MEDICAL = ((_words("service_words.txt") | _ADD_BACK) - (NAMES - _ADD_BACK)) | LABELS
GENERAL = _GENERAL
_BACK = set("bill bills do go no new back good best case card part place read see law laws long look means free fair way true ready early box".split())
WIDE = (english() - NAMES) | MEDICAL | GENERAL | _BACK

# Phrases with words from the list of names: they open only whole.
PHRASES = {re.sub(r"\s+", " ", p) for p in (
    "this is not a bill", "bill date", "billing date", "bill amount", "this is a bill", "page", "price", "unit price", "cash price",
    "amount billed", "pay this amount", "please pay", "please pay by", "pay online", "payment options", "upon receipt", "make checks payable to",
    "statement", "explanation of benefits", "retain for tax purposes", "customer service", "return service requested", "important message",
    "participant information", "claim totals", "claim total", "dates of service", "date of service", "description of service", "service code",
    "reason code", "total charge", "total charges", "total payment amount", "your responsibility", "scan to pay", "by mail:", "use coupon above",
    "family of companies", "please detach and return above with your payment",
)}
SAMPLE = re.compile(r"(?i)^sample\s*-\s*fictional test document\b.*$")

MONEY = re.compile(r"^[(\-–]*\$?[\-–]?\d[\d,]*\.\d{2}[)\-–]*$")
NUM_DATE = re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4}-?$|^\d{4}-\d{2}-\d{2}$")
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
MONTH_DATE = re.compile(r"(?i)\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}\b")
SERVICE_CODE = re.compile(r"^(?:\d{5}|[A-Z]\d{4}|0\d{3}|\d{4}[A-Z])$")
ICD = re.compile(r"^[A-Z]\d{2}(?:\.\d{1,4}[A-Z]?)?$")
CHARGE_NO = re.compile(r"^\d{6,10}$")
CHARGE_LINE = re.compile(r"^\W*\d{1,2}/\d{1,2}/\d{2,4}\s+0\d{3}\s+\d{6,10}\s")  # date, revenue code, charge number: a drug or a service follows
SHORT = re.compile(r"^(?:[A-Z]{1,3}\d{1,2}|[A-Z]{2,3}|[A-Z]{2}-\d{1,3}|\d{1,3}%|\d{1,3}\+?)$")
DOSE = re.compile(r"(?i)^\d+(?:\.\d+)?(?:mg|ml|mcg|gm?|l|%|u|meq|cm|mm|hr|hrs|min|units?)$")
PAGE = re.compile(r"(?i)^(?:page\s*)?\d{1,3}\s*(?:of|/)\s*\d{1,3}$")
STREET = (r"st|street|ave|avenue|rd|road|dr|drive|ln|lane|blvd|boulevard|way|ct|court|cir|circle|pl|place|ter|terrace|trl|trail|pkwy|parkway|hwy|"
          r"highway|pike|loop|run|sq|square|plaza|pt|point")
ADDRESS = [re.compile(rf"(?i)\b\d{{1,6}}\s+[\w .'-]*\b(?:{STREET})\b"),  # 12 Oak Street
           re.compile(r"(?i)^\W*(?:apt|apartment|unit|suite|ste|bldg|building|p\.?\s*o\.?\s*box|box)\b\.?\s*#?\s*\w*\W*$"),
           re.compile(r"\b[A-Z]{2},?\s+\d{5}(?:-\d{4})?\b"),  # FL 33067
           re.compile(rf"(?i)^\W*[\w'.-]+(?:\s+[\w'.-]+){{0,2}}\s+(?:{STREET})\W*$")]  # Oak Street
ORG = set("hospital hospitals hosp health healthcare medical center centre clinic clinics pediatrics pediatric physicians associates anesthesia radiology "
          "pathology laboratory laboratories labs insurance assurance pharmacy care llc inc pllc corp corporation company companies foundation physician services "
          "system ob/gyn obgyn gynecology obstetrics emergency urgent surgical surgery imaging dental".split())

PERSON = r"patient|member|subscriber|insured|guarantor|policy\s*holder|responsible\s+party|beneficiary|addressee|recipient"
NO = r"(?:num(?:ber)?\.?|no\.?|#|id)"
LABEL = re.compile(
    r"(?<![A-Za-z])(?:"
    rf"(?P<ACCT>(?:patient\s+)?(?:account|acct)\.?(?:\s*{NO})?|mrn|medical\s+record(?:\s*{NO})?|encounter(?:\s*{NO})?|visit\s*{NO}|invoice\s*{NO}?|"
    rf"ref(?:erence)?\s*{NO}|statement\s+code|access\s+code|confirmation\s*{NO}?|ssn|social\s+security(?:\s*{NO})?)"
    rf"|(?P<MEMBER>(?:member|subscriber|insured|policy(?:holder)?|certificate|guarantor)\s*{NO}|id\s*{NO}?)"
    rf"|(?P<CLAIM>claim\s*{NO}?)"
    rf"|(?P<GROUP>group(?:\s+(?:name|num(?:ber)?\.?|no\.?|#))?)"
    rf"|(?P<PATIENT>(?:{PERSON})(?:\s+name)?|account\s+holder|name|date\s+of\s+birth|birth\s*date|dob|born|attn\.?|attention|bill\s+to|ship\s+to|sold\s+to|mail\s+to|to|from)"
    r"|(?P<ADDR>(?:mailing\s+)?address|addr)"
    r"|(?P<PHONE>phone|telephone|tel|fax|cell|mobile)"
    r"|(?P<MAIL>e-?mail)"
    r"|(?P<OPEN>(?:(?:rendering\s+|billing\s+|attending\s+|referring\s+|performing\s+|admitting\s+|consulting\s+|ordering\s+)?(?:provider|physician|doctor|surgeon|facility|hospital|clinician|location)(?:\s+name)?"
    r"|make\s+checks?\s+payable\s+to|payable\s+to|billing\s+phone)(?=\s*[:#]))"
    r")(?=\s*[:#])", re.I)
WHOLE = re.compile(rf"(?i)^\W*(?:(?:{PERSON})(?:\s+name)?|(?:patient\s+)?(?:account|acct)\.?(?:\s*{NO})?|claim\s*{NO}?|name|dob|birth\s*date|date\s+of\s+birth|address|group\s*{NO}?|(?:member|subscriber)\s*{NO}|to|from)\W*$")
STRONG = re.compile(rf"(?i)^(?:{PERSON}|to|from|attn\.?|attention|bill\s+to|ship\s+to|sold\s+to|mail\s+to|dob)\b\s+(?=\S)")
SAFE = re.compile(
    r"(?i)\b(?:patient\s+(?:responsibility|resp|balance|copay|co-?pay|pays?|owes?|portion|share|payments?|deductible|coinsurance|co-?insurance|amount|costs?|"
    r"liability|due|information)|member\s+(?:services?|responsibility|pays?|owes?|portal|balance|costs?|share|information)|"
    r"claims?\s+(?:totals?|summary|details?|status|information|payment|charges?)|group\s+(?:health|plan|policy|insurance)|"
    r"from\s+(?:the|your|our|this|hospital|insurance|plan)|to\s+(?:the|your|our|this|pay|avoid|make|appeal|request|provider))\b")
HEADER_ID = re.compile(rf"(?i)\b(?:{PERSON}|account|acct|claim|group|dob|birth|ssn|id|mrn|policy)\b")
# The labels that open a date. Any other label, however ordinary (Effective Date, Renewal Date), does not.
DATE_OK = re.compile(r"(?i)\b(?:dates?\s+of\s+service|service\s+dates?|date\s+of\s+(?:admission|discharge)|admission(?:\s+date)?|admit(?:\s+date)?|discharged?(?:\s+date)?|"
                     r"statement\s+date|bill(?:ing)?\s+date|print(?:ed)?\s+(?:on|date)|date\s+(?:processed|received|paid)|due\s+date|payment\s+due|(?:please\s+)?pay\s+by|due\s+by|"
                     r"appeal\s+(?:by|deadline|date)|file\s+by|visit\s+on)\b|(?:^|\W)date(?=\s*[:#]|\s*$)|^\W*dates?\W*$")
DATE_WORD = re.compile(r"(?i)\b(?:dates?|dated|deadline|renewal|effective|expires?|expiration|issued|since|born|birth)\b")
BIRTH = re.compile(r"(?i)\b(?:d\.?\s?[o0]\.?\s?b\.?|birth\s*-?\s*date|birthday|date\s+[o0][fl]\s+\w{3,6}|born|birth\s*[:#])(?=\W|$)")
BARE_DATE = re.compile(r"(?i)^\W*dates?\W*$|^\W*date\s*[:#]")  # the bare label: once a sheet, at its head, and beside a person only as _bare_date_ok allows
PERSON_NEAR = re.compile(rf"(?i)\b(?:{PERSON}|name|address|addr)\b")
HEAD_OF_SHEET = 0.35
SIDE_MARGIN = 0.03
LEAN = 0.04  # steepest slope taken for a tilted line of print
WEB = re.compile(r"(?i)https?:|www\.|\w\.\w+\.\w|\w@\w")  # a site or a mail address is no service
SERVICE_DATE = re.compile(r"(?i)\b(?:dates?\s+of\s+service|service\s+dates?|dos|visit\s+on)\b")
CODE_HEADER = re.compile(r"(?i)\b(?:code|codes|cpt|hcpcs|procedure|rev|revenue)\b")
# Labels of numbers and contacts: their value is closed however the label is spelled, misreadings included.
FUZZY = {"dob": "PATIENT", "birthdate": "PATIENT", "birthday": "PATIENT", "ssn": "ACCT", "account": "ACCT", "acct": "ACCT", "acc": "ACCT", "mrn": "ACCT", "policy": "MEMBER",
         "group": "GROUP", "grp": "GROUP", "phone": "PHONE", "telephone": "PHONE", "tel": "PHONE", "fax": "PHONE", "cell": "PHONE", "mobile": "PHONE",
         "email": "MAIL", "address": "ADDR", "addr": "ADDR"}
ANY_VALUE = {"PATIENT", "ADDR", "MAIL", "PHONE"}  # closed even with no digit in it
_SHAPE = str.maketrans("015", "ols")
NUMBER_WORD = re.compile(r"\s*(?:num(?:ber)?\.?|no\.?|#|id)?\s*[:#]?\s*", re.I)
ACCOUNT_SAFE = re.compile(r"(?i)\b(?:account\s+(?:balance|summary|details?|activity|status|information|may|has|is)|group\s+(?:health|plan|policy|insurance|number$)|"
                          r"policy\s+(?:year|period|limits?|terms?|and)|address\s+(?:is|above|below|change)|phone\s+(?:calls?|number\s+on))\b")


@dataclass
class Tag:
    n: int
    text: str
    box: tuple  # x0, y0, x1, y1


@dataclass
class Verdict:
    how: str  # open | closed
    why: str
    hide: list = field(default_factory=list)  # (start, end, kind) inside an open line


def compact(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _is_known(text: str, known: set[str]) -> bool:
    c = compact(text)
    toks = {compact(t) for t in text.split()}
    return any((k in c) if len(k) >= 4 else (k in toks) for k in known if k)


def _addressy(text: str) -> bool:
    return any(rx.search(text) for rx in ADDRESS)


def _forms(p: str) -> list[str]:
    """The lists hold base forms: reflects, days, covered. A form counts only through its base, so hunters does not pass."""
    p = p.removesuffix("'s").removesuffix("’s")
    out = [p]
    if len(p) > 3 and p.endswith("s"):
        out.append(p[:-1])
    if len(p) > 4 and p[-2:] in ("es", "ed"):
        out += [p[:-2], p[:-1]]
    if len(p) > 5 and p.endswith("ing"):
        out += [p[:-3], p[:-3] + "e"]
    if len(p) > 4 and p.endswith("ies"):
        out.append(p[:-3] + "y")
    return out


def _word_ok(w: str, vocab: set[str]) -> bool:
    w = w.strip(".,:;!?()[]{}\"'*#|…").lower().replace("(s)", "s")
    if not w or w.isdigit() and len(w) <= 3:
        return True
    if w == "ob/gyn":
        return True
    parts = [p for p in re.split(r"[-/&]", w) if p]
    return bool(parts) and all(p in vocab or p in FUNCTION or re.fullmatch(r"\d{1,3}", p) or (p not in NAMES and any(s in vocab for s in _forms(p))) for p in parts)


def _tokens(text: str) -> tuple[list[str], int, int, int]:
    """The words of a line without sums, dates and codes, and how many of each."""
    t, dates = MONTH_DATE.subn(" ", text)
    words, money, codes = [], 0, 0
    after_code = False
    for tok in t.split():
        bare = tok.strip(".,:;|[]")
        code = False
        if MONEY.match(bare):
            money += 1
        elif NUM_DATE.match(bare.strip("()")):
            dates += 1
        elif SERVICE_CODE.match(bare) or ICD.match(bare) or DOSE.match(bare) or (after_code and dates and CHARGE_NO.match(bare)):
            codes += 1  # a charge number stands right after the revenue code: 02/11/2025 0251 025594594 CEFAZOLIN
            code = True
        elif not re.search(r"\w", tok):
            continue
        else:
            words.append(tok)
        after_code = code
    return words, money, dates, codes


def _short(word: str) -> bool:
    w = word.strip(".,:;")
    return bool(SHORT.match(w)) and w.lower() not in NAMES


def _org(text: str) -> bool:
    if _addressy(text) or re.search(r"\d{4,}", text):
        return False
    words = [w.strip(".,()[]-").lower() for w in text.split()]
    return any(w in ORG for w in words) and not any(w in NAMES and w not in ORG and len(words) <= 2 for w in words)


def _labels(text: str):
    masked = SAFE.sub(lambda m: " " * len(m.group()), text)
    found = [(m.start(), m.end(), m.lastgroup) for m in LABEL.finditer(masked)]
    if not found:
        if WHOLE.match(masked):
            return [(0, len(text), "PATIENT")]
        s = STRONG.match(masked)
        if s:
            found = [(0, s.end(), "PATIENT")]
    found += [x for x in _birth_labels(masked) if not any(a <= x[0] < b for a, b, _ in found)]
    found += _loose_labels(text, masked, found)
    return sorted(found)


def _all_but_money(text: str, codes: bool = False) -> list:
    hide, pos = [], 0
    leading = True  # a service code opens a service line; a number after words may be anything
    for m in re.finditer(r"\S+", text):
        bare = m.group().strip(".,:;")
        code = codes and leading and (SERVICE_CODE.match(bare) or NUM_DATE.match(bare))
        if MONEY.match(bare) or code:
            if m.start() > pos:
                hide.append((pos, m.start(), ""))  # not understood: no token, it need not be a person
            pos = m.end()
        else:
            leading = False
    if pos < len(text):
        hide.append((pos, len(text), ""))
    return hide


def _edit(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[-1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _kind_of(word: str) -> str | None:
    w = word.lower().replace(".", "").replace("-", "").translate(_SHAPE)
    if w in FUZZY:
        return FUZZY[w]
    if len(w) < 4 or w in FUNCTION or w in MEDICAL - set(FUZZY):
        return None
    for target, kind in FUZZY.items():
        if len(target) >= 5 and abs(len(w) - len(target)) <= 2 and _edit(w, target) <= (1 if len(target) < 8 else 2):
            return kind
    return None


def _loose_labels(text: str, masked: str, taken: list) -> list:
    """Account 30955, Polcy # 30955, D0B 01/02/1985: a label without a colon or misread."""
    out = []
    plain = ACCOUNT_SAFE.sub(lambda m: " " * len(m.group()), masked)
    for m in re.finditer(r"[A-Za-z0-9][A-Za-z0-9.-]*", plain):
        if any(a <= m.start() < b for a, b, _ in taken):
            continue
        kind = _kind_of(m.group())
        if not kind:
            continue
        sep = NUMBER_WORD.match(text, m.end())
        end = sep.end() if sep else m.end()
        value = text[end:]
        first = value.split()[0] if value.split() else ""
        if not first or MONEY.match(first.strip(".,:;")):
            continue
        if kind in ANY_VALUE or re.search(r"\d", first):
            out.append((m.start(), end, kind))
    return out


def _birth_match(m: re.Match) -> bool:
    """date of <word>, only when the word looks like birth, misread or not. Date of this letter is no birth date."""
    tail = re.match(r"(?i)date\s+[o0][fl]\s+(\w+)", m.group())
    return not tail or _edit(tail.group(1).lower().translate(_SHAPE), "birth") <= 2


def _birth(text: str) -> bool:
    return any(_birth_match(m) for m in BIRTH.finditer(text))


def _birth_labels(text: str) -> list:
    return [(m.start(), m.end(), "PATIENT") for m in BIRTH.finditer(text) if _birth_match(m)]


def _skew(tags: list[Tag], h: float) -> float:
    """A photographed sheet leans: the slope of its print, from pieces that clearly stand on one line."""
    slopes = []
    centers = sorted(((t.box[0] + t.box[2]) / 2, (t.box[1] + t.box[3]) / 2) for t in tags)
    for i, (x, y) in enumerate(centers):
        for x2, y2 in centers[i + 1:]:
            if x2 - x > 5 * h and abs(y2 - y) <= LEAN * (x2 - x):
                slopes.append((y2 - y) / (x2 - x))
    return sorted(slopes)[len(slopes) // 2] if len(slopes) >= 5 else 0.0


def _rows(tags: list[Tag], h: float) -> list[list[Tag]]:
    rows: list[dict] = []
    skew = _skew(tags, h)

    def center(t: Tag) -> float:
        return (t.box[1] + t.box[3]) / 2 - skew * (t.box[0] + t.box[2]) / 2

    for t in sorted(tags, key=center):
        cy = center(t)
        for r in rows:
            if abs(r["cy"] - cy) <= 0.6 * h:
                r["tags"].append(t)
                break
        else:
            rows.append({"cy": cy, "tags": [t]})
    return [r["tags"] for r in rows]


def _has_money(t: Tag) -> bool:
    return _tokens(t.text)[1] > 0


def _data_only(t: Tag) -> bool:
    words, money, dates, codes = _tokens(t.text)
    return not words or all(_short(w) for w in words)


def _header_above(t: Tag, rows: list[list[Tag]], i: int, h: float) -> str:
    """The label above in the same column: data cells are skipped, a table can be long. A label on two lines is joined."""
    found: list[Tag] = []
    for r in reversed(rows[:i]):
        if found and found[-1].box[1] - max(u.box[3] for u in r) > 1.5 * h:
            break
        for u in r:
            if u.box[0] < t.box[2] and t.box[0] < u.box[2] and not _data_only(u):
                found.append(u)
                break
        else:
            if found:
                break
    return " ".join(u.text.strip() for u in reversed(found))


def _nearest(t: Tag, rows: list[list[Tag]], i: int) -> str:
    for r in reversed(rows[:i]):
        for u in r:
            if u.box[0] < t.box[2] and t.box[0] < u.box[2] and not _data_only(u):
                return u.text
    return ""


def _is_id_header(header: str) -> bool:
    return bool(header and (HEADER_ID.search(SAFE.sub(" ", header)) or _birth(header) or _bare_id(Tag(0, header, (0, 0, 0, 0)))))


def _description(t: Tag) -> bool:
    """A service description. One strange word may stand beside two medical ones unless it is a name: Antihuman Globulin Test."""
    words = _tokens(t.text)[0]
    if any(WEB.search(w) for w in words):
        return False
    medical = [w for w in words if _word_ok(w, MEDICAL) and not _short(w)]
    strange = [w for w in words if not _word_ok(w, WIDE) and not _short(w)]
    return bool(medical) and (not strange or len(strange) == 1 and len(medical) >= 2 and strange[0].strip(".,:;").lower() not in NAMES)


def _coded(t: Tag) -> bool:
    """A line that starts with a service code and goes on with service words, even when the box cut its tail: 59410 Delivery and Po."""
    parts = t.text.split()
    if not parts or not SERVICE_CODE.match(parts[0].strip(".,:;")):
        return False
    words = parts[1:]
    return any(_word_ok(w, MEDICAL) and not _short(w) for w in words) and not any(len(w.strip(".,:;")) >= 4 and w.strip(".,:;").lower() in NAMES - MEDICAL for w in words)


def _unknown(t: Tag) -> bool:
    """Something a service line does not hold: a name, an address, a word nobody knows."""
    words = _tokens(t.text)[0]
    return bool(words) and not _description(t) and not _coded(t) and not all(_short(w) for w in words) and not _labels(t.text)


def _prefix_only(text: str) -> list:
    """The allowed start stays; from the first word that is not allowed the line is closed, sums excepted."""
    for m in re.finditer(r"\S+", text):
        w = m.group()
        if not (MONEY.match(w.strip(".,:;")) or SERVICE_CODE.match(w.strip(".,:;")) or _word_ok(w, MEDICAL) or _short(w) or NUM_DATE.match(w.strip("(),.:;"))):
            return _without_money(m.start(), len(text), text, "")
    return []


def _dates(text: str) -> list[date]:
    out = []
    for m in re.finditer(r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b|\b(\d{4})-(\d{2})-(\d{2})\b|\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})\b", text, re.I):
        g = m.groups()
        try:
            if g[0]:
                y = int(g[2])
                out.append(date(2000 + y if y < 50 else 1900 + y if y < 100 else y, int(g[0]), int(g[1])))
            elif g[3]:
                out.append(date(int(g[3]), int(g[4]), int(g[5])))
            else:
                out.append(date(int(g[8]), MONTHS.index(g[6].lower()) + 1, int(g[7])))
        except ValueError:  # 13/45/2025 is no date
            pass
    return out


def _year(text: str) -> list[int]:
    return [d.year for d in _dates(text)]


def _a_year_after(d: date) -> date:
    try:
        return d.replace(year=d.year + 1)
    except ValueError:  # February 29
        return date(d.year + 1, 2, 28)


def _bare_date_ok(text: str, c: dict) -> bool:
    """The bare "Date:". Beside a person it can only be the paper's own date: after every service on the sheet, within a year of the
    last one. A patient's birth date is never later than a service to that patient, so a birth date does not pass."""
    if not c["bare_head"]:
        return False
    if not c["by_person"]:
        return True
    found, services = _dates(text), c["services"]
    if not found or not services:
        return False
    last = max(services)
    return all(last < d <= _a_year_after(last) for d in found)


def _too_old(text: str, usual: float) -> bool:
    """A service is not decades older than the other dates of its sheet. That is what a birth date without a label looks like."""
    return any(y < 2015 or y < usual - 3 for y in _year(text))


def _without_money(a: int, b: int, text: str, kind: str) -> list:
    """The value is closed to the end of the line; a sum on that line stays open."""
    out, pos = [], a
    for m in re.finditer(r"\S+", text[a:b]):
        if MONEY.match(m.group().strip(".,:;")):
            if a + m.start() > pos and re.search(r"\w", text[pos:a + m.start()]):
                out.append((pos, a + m.start(), kind))
            pos = a + m.end()
    if pos < b and re.search(r"\w", text[pos:b]):
        out.append((pos, b, kind))
    return out


def _bare_id(t: Tag) -> bool:
    """A cell that holds only a number's label: Policy #, Account No., MRN. The value beside it is closed."""
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9.-]*", t.text)
    rest = [w for w in words if w.lower().strip(".") not in ("no", "num", "number", "id")]
    return bool(rest) and len(rest) <= 2 and all(_kind_of(w) for w in rest)


def _labelled(text: str, found: list, known: set[str]) -> Verdict:
    hide, kept = [], []
    pos = 0
    for i, (a, b, kind) in enumerate(found):
        end = found[i + 1][0] if i + 1 < len(found) else len(text)
        kept.append(text[pos:b])
        pos = end
        value = text[b:end]
        if not re.search(r"\w", value):
            continue
        if kind == "OPEN" and not _is_known(value, known) and not _addressy(value) and not re.search(r"\d{4,}", re.sub(r"[()\s-]", "", value) if "phone" not in text[a:b].lower() else ""):
            continue
        plain_words = ":" not in text[a:b + 1] and "#" not in text[a:b + 1] and kind != "OPEN" and all(_word_ok(w, WIDE) for w in value.split())
        hide += _without_money(b, end, text, "" if plain_words else "PATIENT" if kind == "OPEN" else kind)  # member record on file: closed, and not a person
    rest = " ".join(kept)
    words, *_ = _tokens(rest)
    bad = [w for w in words if not _word_ok(w, LABELS | {"id", "num", "no", "name", "to", "from", "attn", "attention", "dob", "acct", "ssn", "mrn", "e-mail", "email",
                                                          "addr", "tel", "fax", "cell", "mobile", "phone", "ref", "account", "provider", "physician", "doctor", "surgeon",
                                                          "rendering", "attending", "referring", "performing", "born", "birth", "of", "insured", "guarantor", "addressee",
                                                          "beneficiary", "recipient", "policyholder", "location", "clinician", "holder", "certificate", "encounter", "access", "code", "make", "checks", "check", "payable"})]
    if bad or _is_known(rest, known):
        if _tokens(text)[1]:
            return Verdict("open", "money only", _all_but_money(text))
        return Verdict("closed", "label+other")
    return Verdict("open", "label", hide)


def org_words(tags: list[Tag], verdicts: dict[int, Verdict]) -> set[str]:
    """The words of organizations opened on this sheet: the same letterhead on the next sheet may print them without Hospital or Services."""
    found = {w.strip(".,()-").lower() for t in tags if verdicts[t.n].why == "org" for w in re.split(r"[\s-]+", t.text)}
    return {w for w in found if len(w) >= 4 and w.isalpha() and w not in NAMES}


def decide(tags: list[Tag], h: float, known: set[str], orgs: set[str] = frozenset()) -> dict[int, Verdict]:
    rows = _rows(tags, h)
    years = sorted(y for t in tags for y in _year(t.text))
    usual = years[len(years) // 2] if years else 0
    bottom = max((t.box[3] for t in tags), default=0)
    right = max((t.box[2] for t in tags), default=0)
    facts = []
    services: list[date] = []
    for i, row in enumerate(rows):
        f = {"money_row": any(_has_money(t) for t in row), "birth_row": any(_birth(t.text) for t in row),
             "labels": [lb for t in row for lb in _labels(t.text) if lb[2] != "OPEN" and not _has_money(t)] + [t.n for t in row if _bare_id(t)],
             "unknown": any(_unknown(t) for t in row), "dated": any(_tokens(t.text)[2] for t in row),
             "coded": any(_tokens(t.text)[3] for t in row), "described": any(_description(t) for t in row)}
        f["service_row"] = f["money_row"] and not f["unknown"] and not f["labels"] and (f["coded"] or f["described"]) and (f["dated"] or f["described"])
        f["legend"] = not f["money_row"] and not f["unknown"] and not f["labels"] and not f["dated"] and f["coded"] and f["described"]
        facts.append(f)
        for t in row:  # the sheet's service dates: a service line, or a service label above the column or on the line
            if f["birth_row"] or not _dates(t.text) or _too_old(t.text, usual):
                continue
            if f["service_row"] or SERVICE_DATE.search(t.text) or SERVICE_DATE.search(_header_above(t, rows, i, h)):
                services += _dates(t.text)
    bare_used = False
    out: dict[int, Verdict] = {}
    for i, row in enumerate(rows):
        f = facts[i]
        near = [u for r in rows[max(0, i - 3):i + 4] for u in r]
        by_person = any(PERSON_NEAR.search(SAFE.sub(" ", u.text)) for u in near)
        for t in row:
            header = _header_above(t, rows, i, h)
            ctx = {"money_row": f["money_row"], "service_row": f["service_row"], "legend": f["legend"], "birth_row": f["birth_row"], "label_row": bool(f["labels"]),
                   "usual": usual, "header": header, "services": services, "by_person": by_person, "orgs": orgs,
                   "sideways": _sideways(t, right),
                   "bare_head": not bare_used and t.box[1] <= HEAD_OF_SHEET * bottom,
                   "row_date": next((m.group().strip() for u in row if u is not t and not _birth(u.text) for m in [DATE_OK.search(u.text)] if m), ""),
                   "under_id": _is_id_header(_nearest(t, rows, i))}
            out[t.n] = _one(t, ctx, known)
            bare_used |= out[t.n].why == "date:date"
    return _parts_of_closed(tags, out)


def _parts_of_closed(tags: list[Tag], out: dict[int, Verdict]) -> dict[int, Verdict]:
    """Two boxes over one ink: OpenCV cut "| More" out of "Moreno , Daniela". A piece with words that only repeats a part of the
    closed piece over it closes too, or its pixels would bring the closed ink back. A sum is read whole, so "$683.02" stays
    beside a closed "AMOUNT | $683.0", and the sum check watches the rest."""
    for t in tags:
        part = compact(t.text)
        if out[t.n].how != "open" or not re.search(r"[a-z]{2}", part):
            continue
        for u in tags:
            over = min(t.box[2], u.box[2]) - max(t.box[0], u.box[0]), min(t.box[3], u.box[3]) - max(t.box[1], u.box[1])
            if out[u.n].how != "open" and min(over) > 2 and part in compact(u.text):
                out[t.n] = Verdict("closed", "part of a closed piece")
                break
    return out


def _sideways(t: Tag, right: int) -> bool:
    """Text printed sideways: a box taller than wide, or a piece on the very margin. Mailing lines run so, and a scrap of one
    can look like a code."""
    tall = t.box[3] - t.box[1] > 1.2 * (t.box[2] - t.box[0]) and len(compact(t.text)) >= 2
    return tall or t.box[2] < SIDE_MARGIN * right


def _one(t: Tag, c: dict, known: set[str]) -> Verdict:
    text = t.text.strip()
    if not re.search(r"\w", text):
        return Verdict("closed", "empty")
    if c["sideways"]:
        return Verdict("closed", "sideways")
    letters = compact(text)
    if len(letters) >= 3 and letters.isalpha() and any(letters in k for k in known if len(k) > len(letters)):  # "| More": a box cut through "Moreno"
        return Verdict("closed", "part of a known value")
    low = re.sub(r"\s+", " ", text.lower()).strip(" .:")
    if SAMPLE.match(text):
        return Verdict("open", "stamp")
    found = _labels(text)
    if found:
        return _labelled(text, found, known)
    if _is_known(text, known):
        spans = [m.span() for m in re.finditer(r"[^\s,;:()'’]+", text) if compact(m.group()) in known]
        if spans:  # Daniela's visit on February 11, 2025: the family's value closes, the rest is judged as any line
            rest = list(text)
            for a, b in spans:
                rest[a:b] = " " * (b - a)
            rest = "".join(rest)
            if re.search(r"\w", rest) and not _is_known(rest, known):
                v = _one(Tag(t.n, rest, t.box), c, known)
                if v.how == "open" and not _tokens(rest)[3]:  # a number beside a name is no service code
                    return Verdict("open", v.why, sorted(v.hide + [(a, b, "") for a, b in spans]))  # the value itself gives the token
        return Verdict("open", "money only", _all_but_money(text)) if _tokens(text)[1] else Verdict("closed", "known")
    if low in PHRASES or PAGE.match(text.strip(" .")):
        return Verdict("open", "phrase")
    if _addressy(text):
        return Verdict("closed", "address")
    words, money, dates, codes = _tokens(text)
    if not words and money and not dates and not codes:
        return Verdict("open", "money")
    if dates and _too_old(text, c["usual"]):
        return Verdict("open", "money only", _all_but_money(text)) if money else Verdict("closed", "old date")
    if not words and dates and not money and not codes:  # a date alone
        if c["birth_row"]:
            return Verdict("closed", "date of a person")
        if c["row_date"] and (not BARE_DATE.match(c["row_date"]) or _bare_date_ok(text, c)):  # a label on the row is nearer than the column above
            return Verdict("open", f"date:{c['row_date'].strip(' :#').lower()}")
        if c["under_id"]:
            return Verdict("closed", "date of a person")
        m = DATE_OK.search(c["header"])
        if m and not BARE_DATE.match(c["header"]):
            return Verdict("open", f"date:{m.group().strip().lower()}")
        if c["service_row"]:
            return Verdict("open", "date:service line")
        return Verdict("closed", "date without a label")
    only_short = bool(words) and all(_short(w) for w in words)
    if (not words or only_short) and (codes or only_short) and not money:  # a code alone
        if c["under_id"] or c["label_row"]:
            return Verdict("closed", "code without a line")
        if c["legend"] or c["service_row"] or (c["money_row"] and CODE_HEADER.search(c["header"])):
            return Verdict("open", "code")
        return Verdict("closed", "code without a line")
    if dates and not money and not codes:  # a date with a label on the line
        m = DATE_OK.search(text)
        if m and not _birth(text) and (not BARE_DATE.match(text) or _bare_date_ok(text, c)):
            return Verdict("open", f"date:{m.group().strip(' :#').lower()}")
        if DATE_WORD.search(text):
            return Verdict("closed", "date label not allowed")
    if CHARGE_LINE.match(text) and not c["label_row"] and any(_word_ok(w, MEDICAL) and not _short(w) for w in words):
        return Verdict("open", "service")
    some_medical = any(_word_ok(w, MEDICAL) and not w.strip(".,:;()").isdigit() for w in words)
    if (money or dates or codes) and not c["label_row"] and all(_word_ok(w, WIDE) or _short(w) for w in words) and (some_medical or not words) and (words or codes):
        return Verdict("open", "service")
    if not c["label_row"] and _coded(t) and (c["money_row"] or c["legend"]):
        return Verdict("open", "service", _prefix_only(text))
    if c["legend"] and _description(t):
        return Verdict("open", "service")
    if c["money_row"] and not c["label_row"] and words and (all(_word_ok(w, MEDICAL) or _short(w) for w in words) or c["service_row"] and _description(t)):
        return Verdict("open", "service")
    if not money and not dates and not codes and len(words) <= 6 and all(_word_ok(w, LABELS) for w in words) and any(_word_ok(w, LABELS - AMBIGUOUS) for w in words):
        return Verdict("open", "label")
    if len(words) >= 4 and any(w.strip(".,:;").lower() in FUNCTION for w in words) and all(_word_ok(w, WIDE) or _short(w) for w in words):
        return Verdict("open", "sentence")
    if not money and not dates and _org(text):
        return Verdict("open", "org")
    named = [w.strip(".,()-").lower() for w in re.split(r"[\s-]+", text) if w.strip(".,()-")]
    if named and len(named) <= 4 and not money and not dates and all(w in c["orgs"] or w in ORG for w in named) and any(w in c["orgs"] for w in named):
        return Verdict("open", "org")
    if money or (c["service_row"] and codes):  # a sum and a code beside something not allowed: only they open
        return Verdict("open", "money only", _all_but_money(text, c["service_row"]))
    return Verdict("closed", "no class")
