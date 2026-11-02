"""SEC EDGAR fetches: User-Agent required, <= 8 requests/s, every response cached on disk (local only)."""
import json
import time
import urllib.request

from maid.cache import DiskCache
from maid.config import get_settings

MIN_INTERVAL = 0.125  # seconds between network requests (SEC allows 10/s)
_last = [0.0]


def _get_json(url: str, user_agent: str) -> dict:
    """GET a JSON URL with the SEC User-Agent, rate-limited."""
    if not user_agent.strip():
        raise ValueError("SEC_USER_AGENT is not set (SEC requires a contact, e.g. 'MAID research you@example.com')")
    wait = MIN_INTERVAL - (time.monotonic() - _last[0])
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(url, headers={"User-Agent": user_agent, "Accept-Encoding": "identity"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    finally:
        _last[0] = time.monotonic()


def cik10(cik) -> str:
    """Zero-padded 10-digit CIK."""
    return f"{int(cik):010d}"


class SecClient:
    """Cached SEC JSON endpoints."""

    def __init__(self, cache: DiskCache | None = None, user_agent: str | None = None, fetch=_get_json):
        s = get_settings()
        self.cache = cache or DiskCache(s.cache_dir / "sec")
        self.user_agent = s.sec_user_agent if user_agent is None else user_agent
        self.fetch = fetch

    def _cached(self, url: str) -> dict:
        # Never expires on purpose: companyfacts only grows and the filed <= decision_date filter makes old and new copies agree.
        return self.cache.get_or_compute(DiskCache.key("sec", url), lambda: self.fetch(url, self.user_agent))

    def companyfacts(self, cik) -> dict:
        """XBRL companyfacts for a CIK."""
        return self._cached(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10(cik)}.json")

    def submissions(self, cik) -> dict:
        """Filing submissions metadata for a CIK."""
        return self._cached(f"https://data.sec.gov/submissions/CIK{cik10(cik)}.json")

    def tickers(self) -> dict:
        """Ticker/CIK table."""
        return self._cached("https://www.sec.gov/files/company_tickers_exchange.json")


def ticker_to_cik(tickers_json: dict, ticker: str) -> int:
    """CIK for a ticker from company_tickers_exchange.json ({"fields": [...], "data": [[cik, name, ticker, exchange], ...]})."""
    fields = tickers_json["fields"]
    ic, it = fields.index("cik"), fields.index("ticker")
    for row in tickers_json["data"]:
        if str(row[it]).upper() == ticker.upper():
            return int(row[ic])
    raise ValueError(f"unknown ticker: {ticker}")
