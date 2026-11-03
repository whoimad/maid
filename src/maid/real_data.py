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
