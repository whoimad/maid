"""10-K text: HTML to plain text, Item 1 / 1A / 7 extraction, name anonymization (pure, no I/O)."""
import re
from html.parser import HTMLParser

SECTIONS = {"1": ("1", ("1a", "1b", "1c", "2")), "1a": ("1a", ("1b", "1c", "2")), "7": ("7", ("7a", "8"))}
TITLES = {"1": r"business", "1a": r"risk\s+factors", "1b": r"unresolved", "1c": r"cybersecurity",
          "2": r"properties", "7": r"management", "7a": r"quantitative", "8": r"financial\s+statements"}
EXTRACTOR_VERSION = "1"  # bump when extraction rules change (cache keys and reports carry it)
SKIP = {"script", "style", "ix:header"}
BLOCK = {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6", "table", "td"}
SUFFIXES = r"(?:inc|incorporated|corp|corporation|co|company|ltd|limited|plc|llc|l\.p|n\.v|s\.a)"


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


def heading(item: str) -> re.Pattern:
    """Pattern for a line-initial "Item N. Title" heading."""
    return re.compile(rf"^[ \t]*item\s*{item}(?![0-9a-z])\s*[\.:\-—–]?\s*{TITLES[item]}", re.I | re.M)


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


def name_variants(names: list[str]) -> list[str]:
    """Registrant names without leading "The" and trailing legal suffixes, unique, longest first."""
    out = set()
    for n in names:
        n = re.sub(r"^the\s+", "", n.strip(), flags=re.I)
        while True:
            m = re.sub(rf"[\s,.;]+{SUFFIXES}[\s,]*\.?\s*$", "", n, flags=re.I)
            m = re.sub(r"[\s,.;]+$", "", m)
            if m == n:
                break
            n = m
        if len(n) >= 4:
            out.add(n)
    return sorted(out, key=lambda v: (-len(v), v))


def anonymize_text(text: str, names: list[str], ticker: str, label: str) -> tuple[str, int]:
    """Replace whole-word registrant names (case-insensitive) and the ticker (case-sensitive) with label."""
    count = 0
    guard = r"(?<![A-Za-z0-9]){}(?![A-Za-z0-9])"
    sep = r"[\s\-‐‑–]+"
    pats = [re.compile(guard.format(sep.join(map(re.escape, re.split(sep, v)))), re.I) for v in name_variants(names)]
    if len(ticker) >= 2:
        pats.append(re.compile(guard.format(re.escape(ticker))))
    for p in pats:
        text, n = p.subn(label, text)
        count += n
    return text, count


def approx_tokens(text: str) -> int:
    """Rough token count (4 characters per token)."""
    return (len(text) + 3) // 4
