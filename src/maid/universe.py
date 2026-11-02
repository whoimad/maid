"""Universe rule (docs/architecture/data.md): SIC sector, NYSE/Nasdaq, 10-K filer, top 15 by market cap."""
from maid import xbrl

SECTORS = {
    "tech": [(3570, 3579), (3661, 3663), (3670, 3679), (7370, 7379)],
    "banks": [(6021, 6021), (6022, 6022)],
}
REVENUE_TAGS = {"tech": None, "banks": ["Revenues", "InterestAndDividendIncomeOperating"]}  # None -> xbrl.REVENUE
EXCHANGES = {"NYSE", "Nasdaq"}
N = 15


def in_sector(sic: str, sector: str) -> bool:
    """True if the SIC code falls in the sector's ranges."""
    try:
        n = int(sic)
    except (TypeError, ValueError):
        return False
    return any(lo <= n <= hi for lo, hi in SECTORS[sector])


def listed(tickers_json: dict) -> dict[int, list[str]]:
    """CIK -> tickers listed on NYSE or Nasdaq, in file order."""
    f = tickers_json["fields"]
    ic, it, ie = f.index("cik"), f.index("ticker"), f.index("exchange")
    out: dict[int, list[str]] = {}
    for row in tickers_json["data"]:
        if row[ie] in EXCHANGES:
            out.setdefault(int(row[ic]), []).append(row[it])
    return out


def shares_outstanding(facts: dict, date: str) -> tuple[float, str]:
    """Sum of cover-page shares in the latest filing on or before date, and its accession."""
    try:
        rows = facts["facts"]["dei"]["EntityCommonStockSharesOutstanding"]["units"]["shares"]
    except KeyError:
        rows = []
    rows = [r for r in rows if r["filed"] <= date]
    if not rows:
        raise ValueError(f"no shares outstanding filed on or before {date}: {facts.get('entityName')}")
    filed = max(r["filed"] for r in rows)
    accn = max(r["accn"] for r in rows if r["filed"] == filed)
    uniq = {(r["end"], r["val"]) for r in rows if r["filed"] == filed and r["accn"] == accn}
    return float(sum(v for _, v in uniq)), accn


def eligible_annual(facts: dict, date: str, sector: str) -> bool:
    """True if a 10-K on or before date and its prior-year period both exist for the sector's revenue tags."""
    tags = REVENUE_TAGS[sector] or xbrl.REVENUE
    try:
        accn, _, end = xbrl.latest_10k(facts, date, tags)
        xbrl.prior_period_end(facts, tags, accn, end)
    except ValueError:
        return False
    return True


def top_n(rows: list[dict], n: int = N) -> list[dict]:
    """Top n rows by market_cap descending, ties by cik ascending."""
    return sorted(rows, key=lambda r: (-r["market_cap"], r["cik"]))[:n]
