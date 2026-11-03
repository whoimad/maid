"""Universe rule (docs/architecture/data.md): SIC sector, NYSE/Nasdaq, 10-K filer, top 15 by market cap."""
from datetime import date as _date
from datetime import timedelta

from maid import xbrl

SECTORS = {
    "tech": [(3570, 3579), (3661, 3663), (3670, 3679), (7370, 7379)],
    "banks": [(6021, 6021), (6022, 6022)],
    "staples": [(2000, 2099), (2100, 2199), (2840, 2844), (5411, 5411)],
}
REVENUE_TAGS = {"tech": None, "banks": ["Revenues", "InterestAndDividendIncomeOperating"],
                "staples": None}  # None -> xbrl.REVENUE
EXCHANGES = {"NYSE", "Nasdaq"}
N = 15
MIN_CAP = {"staples": 1e9}  # sectors selected by a market-cap floor instead of a fixed N
STALE_DAYS = 456  # a share count filed more than ~15 months before the date is not trusted
COVER_EXCHANGES = {"NYSE", "NASDAQ"}  # dei:SecurityExchangeName values that count
COVER_SOURCE = "10-K cover (instance)"


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


SHARE_SOURCES = [  # (taxonomy, tag), tried in order; the first with data filed on or before the date wins
    ("dei", "EntityCommonStockSharesOutstanding"),   # cover page; missing for multi-class filers in companyfacts
    ("us-gaap", "CommonStockSharesOutstanding"),     # balance sheet, all classes
    ("us-gaap", "WeightedAverageNumberOfSharesOutstandingBasic"),  # last resort: period average
]


def _duration(r: dict) -> int:
    """Days between start and end; instant facts count as 0."""
    return (_date.fromisoformat(r["end"]) - _date.fromisoformat(r["start"])).days if "start" in r else 0


def shares_outstanding(facts: dict, date: str, cover: dict | None = None) -> tuple[float, str, str]:
    """Shares in the latest filing on or before date, its accession and the source tag (skips zero or stale sources)."""
    oldest = (_date.fromisoformat(date) - timedelta(days=STALE_DAYS)).isoformat()
    for tax, tag in SHARE_SOURCES:
        rows = facts["facts"].get(tax, {}).get(tag, {}).get("units", {}).get("shares", [])
        rows = [r for r in rows if r["filed"] <= date]
        if not rows:
            continue
        filed = max(r["filed"] for r in rows)
        accn = max(r["accn"] for r in rows if r["filed"] == filed)
        rows = [r for r in rows if r["filed"] == filed and r["accn"] == accn]
        if tax == "dei":
            val = float(sum(v for _, v in {(r["end"], r["val"]) for r in rows}))
        else:
            last = max(r["end"] for r in rows)
            val = float(max((r for r in rows if r["end"] == last), key=_duration)["val"])
        if val == 0 or filed < oldest:
            continue
        return val, accn, tag
    if cover and cover.get("shares") and cover["shares"] > 0:
        return float(cover["shares"]), cover["accn"], COVER_SOURCE
    raise ValueError(f"no shares outstanding filed on or before {date}: {facts.get('entityName')}")


def listed_on_cover(cover: dict) -> bool:
    """True if the 10-K cover names a NYSE or Nasdaq listing."""
    return any(x.upper() in COVER_EXCHANGES for _, x in cover["symbols"])


def pick_ticker(cik: int, cover: dict, listed_today: dict[int, list[str]]) -> str:
    """Today's ticker if listed, else the first NYSE/Nasdaq cover symbol (Yahoo style), guarding against reused tickers."""
    if cik in listed_today:
        return listed_today[cik][0]
    for sym, ex in cover["symbols"]:
        if ex.upper() in COVER_EXCHANGES and sym and not any(c.isspace() for c in sym):
            t = sym.replace(".", "-")
            other = next((c for c, ts in listed_today.items() if t in ts), None)
            if other is not None:
                raise ValueError(f"ticker {t} reused by CIK {other}")
            return t
    raise ValueError("no NYSE/Nasdaq symbol on 10-K cover")


def public_float(facts: dict, date: str) -> float | None:
    """Latest dei:EntityPublicFloat (USD) filed on or before date, or None."""
    rows = [r for r in facts["facts"].get("dei", {}).get("EntityPublicFloat", {}).get("units", {}).get("USD", [])
            if r["filed"] <= date]
    return float(max(rows, key=lambda r: (r["filed"], r["end"]))["val"]) if rows else None


def above_floor(rows: list[dict], min_cap: float) -> list[dict]:
    """Rows with market_cap >= min_cap, by market cap descending, ties by cik."""
    return top_n([r for r in rows if r["market_cap"] >= min_cap], len(rows))


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
