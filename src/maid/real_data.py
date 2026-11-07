"""Real-data inputs for the graph: frozen universe (tech or staples) -> anonymized labels -> point-in-time SEC criteria."""
import csv
from pathlib import Path

from maid.xbrl import STAPLES_CRITERIA, TECH_CRITERIA, staples_criteria, tech_criteria

SECTORS = {"tech": (Path("data/universe/tech.csv"), TECH_CRITERIA, tech_criteria),
           "staples": (Path("data/universe/staples.csv"), STAPLES_CRITERIA, staples_criteria)}
UNIVERSE = SECTORS["tech"][0]


def read_universe(path=UNIVERSE) -> list[dict]:
    """Rows of a frozen universe CSV."""
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def anonymize(tickers: list[str]) -> dict[str, str]:
    """Label -> ticker; labels "Company 001", "Company 002", ... in alphabetical ticker order (no size information)."""
    if len(set(tickers)) != len(tickers) or len(tickers) > 999:
        raise ValueError(f"need up to 999 distinct tickers: {tickers}")
    return {f"Company {i:03d}": t for i, t in enumerate(sorted(tickers), 1)}


def sec_quantitative(rows: list[dict], companyfacts, decision_date: str, sector: str = "tech") -> tuple[dict, dict, dict]:
    """(label -> ticker, label -> criterion -> value, label -> {accn, filed, period_end}); companyfacts(cik) -> facts."""
    if sector not in SECTORS:
        raise ValueError(f"unknown sector: {sector!r}")
    _, criteria, criteria_fn = SECTORS[sector]
    if bad := [r["ticker"] for r in rows if r["decision_date"] != decision_date]:
        raise ValueError(f"universe frozen for another decision date than {decision_date}: {bad}")
    labels = anonymize([r["ticker"] for r in rows])
    by_ticker = {r["ticker"]: r for r in rows}
    quant, meta = {}, {}
    for label, t in labels.items():
        r = criteria_fn(companyfacts(int(by_ticker[t]["cik"])), decision_date)
        quant[label] = {k: r["values"][k] for k in criteria}
        meta[label] = {k: r[k] for k in ("accn", "filed", "period_end")}
    return labels, quant, meta


def load_sec(decision_date: str, sector: str = "tech", client=None) -> tuple[dict, dict, dict]:
    """sec_quantitative on the frozen universe of a sector with the cached SEC client."""
    from maid.sec import SecClient

    if sector not in SECTORS:
        raise ValueError(f"unknown sector: {sector!r}")
    return sec_quantitative(read_universe(SECTORS[sector][0]), (client or SecClient()).companyfacts, decision_date, sector)


def read_aliases(path=Path("data/universe/aliases.csv")) -> dict[str, list[str]]:
    """ticker -> extra name forms that the registrant name rules cannot derive."""
    out: dict[str, list[str]] = {}
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            out.setdefault(r["ticker"], []).append(r["alias"])
    return out


def company_filing(client, cik, accn: str, ticker: str, label: str, aliases=()) -> tuple[dict, dict]:
    """({"1", "1a", "7"} anonymized text, {"replacements", "mdna_source", "residual"}) for one company's 10-K."""
    import re

    from maid import tenk

    sections = tenk.extract_sections(client.filing_html(cik, accn))
    sub = client.submissions(cik)
    names = [sub["name"]] + [f["name"] for f in sub.get("formerNames", [])]
    source = "body"
    if len(sections["7"].split()) < tenk.MIN_WORDS:
        r = sub["filings"]["recent"]
        primary = r["primaryDocument"][r["accessionNumber"].index(accn)]
        docs = [d for d in client.filing_documents(cik, accn)
                if d["name"] != primary and not re.match(r"R\d+\.htm$", d["name"])]
        for d in sorted(docs, key=lambda d: -d["size"])[:3]:
            mdna = tenk.find_mdna(client.document_html(cik, accn, d["name"]))
            if len(mdna.split()) >= tenk.MIN_WORDS:
                sections["7"], source = mdna, f"exhibit:{d['name']}"
                break
    out, total = {}, 0
    for k, text in sections.items():
        out[k], n = tenk.anonymize_text(text, names, ticker, label, aliases)
        total += n
    residual = tenk.residual_mentions(" ".join(out.values()), names, aliases)
    return out, {"replacements": total, "mdna_source": source, "residual": residual}


def load_filings(decision_date: str, sector: str = "tech", client=None) -> tuple[dict, dict, dict]:
    """(label -> ticker, label -> {"1", "1a", "7"} anonymized text, label -> {accn, replacements, mdna_source, residual}) for the 10-K in use."""
    from maid.sec import SecClient

    client = client or SecClient()
    labels, _, meta = load_sec(decision_date, sector, client)
    ciks = {r["ticker"]: int(r["cik"]) for r in read_universe(SECTORS[sector][0])}
    aliases = read_aliases()
    texts, info = {}, {}
    for label, ticker in labels.items():
        accn = meta[label]["accn"]
        texts[label], i = company_filing(client, ciks[ticker], accn, ticker, label, aliases.get(ticker, ()))
        info[label] = {"accn": accn, **i}
    return labels, texts, info
