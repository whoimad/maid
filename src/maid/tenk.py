"""10-K text: HTML to plain text, Item 1 / 1A / 7 extraction, name anonymization (pure, no I/O)."""
import re
import unicodedata
from html.parser import HTMLParser

SECTIONS = {"1": ("1", ("1a", "1b", "1c", "2")), "1a": ("1a", ("1b", "1c", "2")), "7": ("7", ("7a", "8"))}
TITLES = {"1": r"business", "1a": r"risk\s+factors", "1b": r"unresolved", "1c": r"cybersecurity",
          "2": r"properties", "7": r"management", "7a": r"quantitative", "8": r"financial\s+statements"}
EXTRACTOR_VERSION = "2"  # bump when extraction rules change (cache keys and reports carry it)
SKIP = {"script", "style", "ix:header"}
BLOCK = {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6", "table", "td"}
SUFFIXES = r"(?:inc|incorporated|corp|corporation|co|company|ltd|limited|plc|llc|l\.p|n\.v|s\.a)"
GENERIC = {"companies", "company", "holdings", "holding", "group", "foods", "food", "brands", "international",
           "corporation", "inc", "co", "products", "beverages", "beverage", "industries", "enterprises"}
RESIDUAL_SKIP = {"general", "national", "american", "united", "pride", "snack", "dwight", "church"}
MDNA_HEAD = re.compile(r"^[ \t]*management[’']s\s+discussion\s+and\s+analysis\s+of\s+financial\s+condition", re.I | re.M)
MDNA_END = re.compile(r"^[ \t]*(?:report\s+of\s+independent\s+registered|consolidated\s+statements?\s+of\s+"
                      r"(?:earnings|income|operations))", re.I | re.M)
MIN_WORDS = 1000
CRITERIA_TEXT = {"strategy_clarity": "1", "pricing_power": "7_ops", "capital_allocation": "7_liq"}
BUDGET_TOKENS = 24000
LIQ_HEAD = re.compile(r"liquidity\s+and\s+(?:capital\s+resources|financial\s+condition)|liquidity,\s+capital\s+"
                      r"resources|financial\s+(?:condition|position)\s+and\s+liquidity|capital\s+resources\s+and\s+"
                      r"liquidity|liquidity\s+and\s+capital", re.I)
ACCENTS = {"e": "eéèêë", "a": "aáàâä", "o": "oóòôö", "i": "iíìîï", "u": "uúùûü", "c": "cç", "n": "nñ"}


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in SKIP:
            self.skip += 1
        elif tag in BLOCK:
            self.out.append("\n")

    def handle_startendtag(self, tag, attrs):
        if tag in BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag in BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def html_to_text(html: str) -> str:
    """Plain text with block-level line breaks; hidden inline-XBRL header, scripts and styles dropped."""
    p = _Text()
    p.feed(html)
    p.close()
    t = "".join(p.out).replace("\xa0", " ")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"[ \t]*\n[ \t\n]*\n[ \t\n]*", "\n\n", t)
    return t


def _num(item: str) -> str:
    """Item number pattern; sub-items also match "1.A" and "1. A"."""
    return rf"{item[:-1]}\.?\s*{item[-1]}" if item[-1].isalpha() else re.escape(item)


def heading(item: str) -> re.Pattern:
    """Pattern for a line-initial "Item N. Title" heading."""
    return re.compile(rf"^[ \t]*item\s*{_num(item)}(?![0-9a-z])\s*[\.:\-—–]?\s*{TITLES[item]}", re.I | re.M)


def find_section(text: str, item: str, ends: tuple[str, ...]) -> str:
    """Longest span from an Item heading to the next end heading (skips the table of contents)."""
    best = ""
    end_ms = [m.start() for e in ends for m in heading(e).finditer(text)]
    for m in heading(item).finditer(text):
        stop = min((s for s in end_ms if s > m.start()), default=None)
        if stop is not None and stop - m.start() > len(best):
            best = text[m.start():stop]
    return re.sub(r"\s+", " ", best).strip()


def extract_sections(html: str) -> dict[str, str]:
    """{"1", "1a", "7"} section text (whitespace collapsed) from a 10-K HTML document."""
    text = html_to_text(html)
    return {k: find_section(text, item, ends) for k, (item, ends) in SECTIONS.items()}


def find_mdna(html: str) -> str:
    """MD&A from a document that is not a 10-K body (e.g. an annual-report exhibit): longest span head -> end."""
    text = html_to_text(html)
    best = ""
    ends = [m.start() for m in MDNA_END.finditer(text)]
    for m in MDNA_HEAD.finditer(text):
        stop = min((e for e in ends if e > m.start()), default=None)
        if stop is not None and stop - m.start() > len(best):
            best = text[m.start():stop]
    return re.sub(r"\s+", " ", best).strip()


def _full_variants(names: list[str]) -> list[str]:
    """Registrant names without "The", state tags and trailing legal suffixes or "&" (4+ characters)."""
    out = []
    for n in names:
        n = re.sub(r"^the\s+", "", n.strip(), flags=re.I)
        n = re.sub(r"/[A-Z]{2,}/", " ", n)
        n = re.sub(r"[\s,.;&]+$", "", n)
        while True:
            m = re.sub(rf"[\s,.;]+{SUFFIXES}[\s,]*\.?\s*$", "", n, flags=re.I)
            m = re.sub(r"[\s,.;&]+$", "", m)
            if m == n:
                break
            n = m
        if len(n) >= 4:
            out.append(n)
    return out


def _core(full: str) -> str:
    """Full variant minus trailing generic words ("" when nothing is dropped or the result is too short)."""
    words = full.split()
    while len(words) > 1 and words[-1].lower().strip(",.") in GENERIC:
        words.pop()
    core = " ".join(words)
    return core if core != full and len(core) >= 4 else ""


def name_variants(names: list[str], aliases=()) -> list[str]:
    """Full and core registrant-name variants plus aliases, unique, longest first."""
    out = set(aliases)
    for full in _full_variants(names):
        out.add(full)
        if core := _core(full):
            out.add(core)
    return sorted(out, key=lambda v: (-len(v), v))


def _word_pat(word: str) -> str:
    """Regex for one word: accent-insensitive, optional apostrophe before a final s."""
    base = unicodedata.normalize("NFD", word)
    base = "".join(c for c in base if not unicodedata.combining(c))
    parts = []
    for i, c in enumerate(base):
        cl = c.lower()
        p = f"[{ACCENTS[cl]}]" if cl in ACCENTS else re.escape(c)
        parts.append("['’]?" + p if cl == "s" and i == len(base) - 1 and i > 0 else p)
    return "".join(parts)


def _variant_pat(variant: str) -> str:
    """Regex for a name variant: flexible separators, "&" or "and", accents, apostrophes."""
    sep = r"[\s\-‐‑–.]+"
    chunks = [sep.join(_word_pat(w) for w in re.split(sep, c) if w) for c in re.split(r"\s*&\s*", variant)]
    return r"\s*(?:&|and)\s*".join(chunks)


def anonymize_text(text: str, names: list[str], ticker: str, label: str, aliases=()) -> tuple[str, int]:
    """Replace whole-word registrant names (case-insensitive) and the ticker (case-sensitive) with label."""
    count = 0
    guard = r"(?<![A-Za-z0-9]){}(?![A-Za-z0-9])"
    pats = [re.compile(guard.format(_variant_pat(v)), re.I) for v in name_variants(names, aliases)]
    if len(ticker) >= 2:
        pats.append(re.compile(guard.format(re.escape(ticker))))
    for p in pats:
        text, n = p.subn(label, text)
        count += n
    return text, count


def residual_mentions(text: str, names: list[str], aliases=()) -> int:
    """Count whole-word mentions of distinctive name words (4+ letters) left in text (reporting only)."""
    words = set()
    for v in _full_variants(names) + list(aliases):
        for w in re.findall(r"[^\W\d_]{4,}", v):
            if w.lower() not in GENERIC | RESIDUAL_SKIP:
                words.add(w)
    guard = r"(?<![A-Za-z0-9]){}(?![A-Za-z0-9])"
    return sum(len(re.findall(guard.format(_word_pat(w)), text, re.I)) for w in words)


def approx_tokens(text: str) -> int:
    """Rough token count (4 characters per token)."""
    return (len(text) + 3) // 4


def split_mdna(mdna: str) -> tuple[str, str, bool]:
    """(operations part, liquidity part, split found): split at the first liquidity heading after 20% of the text."""
    for m in LIQ_HEAD.finditer(mdna):
        if m.start() > 0.2 * len(mdna):
            return mdna[:m.start()], mdna[m.start():], True
    return mdna, mdna, False


def clip(text: str, budget: int = BUDGET_TOKENS, tail: bool = False) -> tuple[str, bool]:
    """Keep at most budget tokens (approx_tokens), cut at a sentence boundary; tail=True keeps the end."""
    if approx_tokens(text) <= budget:
        return text, False
    if tail:
        kept = text[-budget * 4:]
        i = kept.find(". ")
        return (kept[i + 2:] if i >= 0 else kept), True
    kept = text[:budget * 4]
    i = kept.rfind(". ")
    return (kept[:i + 1] if i >= 0 else kept), True


def criterion_text(sections: dict, criterion: str, budget: int = BUDGET_TOKENS) -> dict:
    """{"text", "source", "truncated", "split_found", "tokens"} for one criterion (same input for every model)."""
    ops, liq, found = split_mdna(sections["7"])
    if criterion == "strategy_clarity":
        src, text, tail = "1", sections["1"], False
    elif criterion == "pricing_power":
        src, text, tail = "7_ops", ops, False
    elif criterion == "capital_allocation":
        src, text, tail = ("7_liq", liq, False) if found else ("7_tail", liq, True)
    else:
        raise ValueError(f"unknown criterion: {criterion!r}")
    out, cut = clip(text, budget, tail)
    return {"text": out, "source": src, "truncated": cut, "split_found": found, "tokens": approx_tokens(out)}
