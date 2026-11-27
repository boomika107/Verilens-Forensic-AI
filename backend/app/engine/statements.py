"""Deterministic statement/claim extraction. No external services. Never judges honesty."""
import re
from datetime import date

MONTHS = {m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"])}
_AP = r"a\.?m\.?|p\.?m\.?"
_TIME_RE = re.compile(
    rf"\b(?:(?P<h>[01]?\d|2[0-3])[:.](?P<m>[0-5]\d)\s*(?P<ap>{_AP})?"
    rf"|(?P<h2>1[0-2]|0?[1-9])\s*(?P<ap2>{_AP})"
    rf"|(?P<h3>1[0-2]|0?[1-9])\s*o['’]?clock(?:\s*(?P<ap3>{_AP}|in the (?:morning|evening|night|afternoon)))?)", re.I)
_ISO_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_DMY_DATE = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b")
_MON = "|".join(MONTHS)
_TEXT_DATE = re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MON})(?:,?\s+(\d{{4}}))?\b", re.I)
_TEXT_DATE2 = re.compile(rf"\b({_MON})\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,?\s+(\d{{4}}))?\b", re.I)
_LOC_RE = re.compile(
    r"\b(?:at|in|near|outside|inside)\s+(?:the\s+|my\s+|his\s+|her\s+|a\s+)?"
    r"([A-Za-z][A-Za-z'\-]*(?:\s+[A-Za-z][A-Za-z'\-]*){0,2}?)"
    r"(?=\s*(?:,|\.|;|\band\b|\bwhen\b|\bwith\b|\bat\b|\bon\b|\bafter\b|\bbefore\b|\buntil\b|$))", re.I)
_NOT_LOC = {"time", "night", "morning", "evening", "pm", "am", "least", "first", "once", "all", "that", "this"}
_NAME_RE = re.compile(r"\b([A-Z][a-z]{2,})\b")
_STOP = {"The", "And", "But", "Then", "When", "Where", "That", "This", "They", "She", "His", "Her",
         "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday", *[m.title() for m in MONTHS]}
_OBJECTS = ["car", "bus", "motorcycle", "bike", "bag", "phone", "knife", "key", "keys", "laptop", "van", "truck", "door"]


def parse_time(text):
    """First explicit time as 'HH:MM' (24h) or None. Bare 12h times without am/pm are kept as written."""
    m = _TIME_RE.search(text)
    if not m:
        return None
    h = int(m.group("h") or m.group("h2") or m.group("h3"))
    mi = m.group("m") or "00"
    ap = (m.group("ap") or m.group("ap2") or m.group("ap3") or "").lower().replace(".", "")
    if ap.startswith("p") or ap in ("in the evening", "in the night", "in the afternoon"):
        h = h + 12 if h < 12 else h
    elif ap.startswith("a") or ap == "in the morning":
        h = 0 if h == 12 else h
    return f"{h:02d}:{mi}"


def parse_date(text):
    m = _ISO_DATE.search(text)
    if m:
        return m.group(0)
    m = _DMY_DATE.search(text)
    if m:
        d, mo, y = map(int, m.groups())
        try:
            return date(y, mo, d).isoformat()
        except ValueError:
            return None
    m = _TEXT_DATE.search(text)
    if m and m.group(3):
        try:
            return date(int(m.group(3)), MONTHS[m.group(2).lower()], int(m.group(1))).isoformat()
        except ValueError:
            return None
    m = _TEXT_DATE2.search(text)
    if m and m.group(3):
        try:
            return date(int(m.group(3)), MONTHS[m.group(1).lower()], int(m.group(2))).isoformat()
        except ValueError:
            return None
    return None


def parse_location(text):
    for m in _LOC_RE.finditer(text):
        loc = m.group(1).strip()
        if loc.lower() not in _NOT_LOC and not _TIME_RE.fullmatch(loc):
            return loc.lower()
    return None


def extract_claim(text, speaker=None, source_ref=None):
    text = text.strip()
    low = text.lower()
    return {
        "speaker_reference": speaker,
        "event_description": text,
        "claimed_location": parse_location(text),
        "claimed_date": parse_date(text),
        "claimed_time": parse_time(text),
        "people": sorted({n for n in _NAME_RE.findall(text) if n not in _STOP}),
        "objects": sorted({o for o in _OBJECTS if re.search(rf"\b{o}\b", low)}),
        "source_reference": source_ref,
        "extraction_method": "rule-based",
    }


def split_statement(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if len(s.strip()) > 3]


def extract_events_from_text(text, source_ref=""):
    """Only sentences with an explicit time/date become candidate events; nothing is invented."""
    out = []
    for s in split_statement(text):
        t, d = parse_time(s), parse_date(s)
        if t or d:
            out.append({"description": s[:500], "date": d, "time": t,
                        "location": parse_location(s), "source_ref": source_ref})
    return out
