"""Real-data inputs for the graph: frozen universe -> anonymized labels -> point-in-time SEC criteria (tech only)."""
import csv
from pathlib import Path

from maid.xbrl import TECH_CRITERIA, tech_criteria

UNIVERSE = Path("data/universe/tech.csv")


def read_universe(path=UNIVERSE) -> list[dict]:
    """Rows of a frozen universe CSV."""
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def anonymize(tickers: list[str]) -> dict[str, str]:
    """Label -> ticker; labels "Company A", "Company B", ... in alphabetical ticker order (no size information)."""
    if len(set(tickers)) != len(tickers) or len(tickers) > 26:
        raise ValueError(f"need up to 26 distinct tickers: {tickers}")
    return {f"Company {chr(65 + i)}": t for i, t in enumerate(sorted(tickers))}


def sec_quantitative(rows: list[dict], companyfacts, decision_date: str) -> tuple[dict, dict, dict]:
    """(label -> ticker, label -> criterion -> value, label -> {accn, filed, period_end}); companyfacts(cik) -> facts."""
    if bad := [r["ticker"] for r in rows if r["decision_date"] != decision_date]:
        raise ValueError(f"universe frozen for another decision date than {decision_date}: {bad}")
    labels = anonymize([r["ticker"] for r in rows])
    by_ticker = {r["ticker"]: r for r in rows}
    quant, meta = {}, {}
    for label, t in labels.items():
        r = tech_criteria(companyfacts(int(by_ticker[t]["cik"])), decision_date)
        quant[label] = {k: r["values"][k] for k in TECH_CRITERIA}
        meta[label] = {k: r[k] for k in ("accn", "filed", "period_end")}
    return labels, quant, meta


def load_sec(decision_date: str, path=UNIVERSE, client=None) -> tuple[dict, dict, dict]:
    """sec_quantitative on the frozen tech universe with the cached SEC client."""
    from maid.sec import SecClient

    return sec_quantitative(read_universe(path), (client or SecClient()).companyfacts, decision_date)
