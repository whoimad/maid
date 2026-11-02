"""SEC EDGAR fetches: User-Agent required, <= 8 requests/s, every response cached on disk (local only)."""
import json
import threading
import time
import urllib.error
import urllib.request

from maid.cache import DiskCache
from maid.config import get_settings

MIN_INTERVAL = 0.125  # seconds between request starts, shared by all threads (SEC allows 10/s)
RETRIES = 3
_lock = threading.Lock()
_next = [0.0]


def _slot() -> None:
    """Block until this thread may start a request (global cap of 1 / MIN_INTERVAL starts per second)."""
    with _lock:
        now = time.monotonic()
        start = max(now, _next[0])
        _next[0] = start + MIN_INTERVAL
    if start > now:
        time.sleep(start - now)


def _get_json(url: str, user_agent: str) -> dict:
    """GET a JSON URL with the SEC User-Agent; rate-limited across threads; retries transient network errors."""
    if not user_agent.strip():
        raise ValueError("SEC_USER_AGENT is not set (SEC requires a contact, e.g. 'MAID research you@example.com')")
    req = urllib.request.Request(url, headers={"User-Agent": user_agent, "Accept-Encoding": "identity"})
    for attempt in range(RETRIES):
        _slot()
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or attempt == RETRIES - 1:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt == RETRIES - 1:
                raise
        time.sleep(2 ** attempt)


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

    def frame(self, taxonomy: str, tag: str, unit: str, period: str) -> dict:
        """XBRL frame: one value per company for a tag and period."""
        return self._cached(f"https://data.sec.gov/api/xbrl/frames/{taxonomy}/{tag}/{unit}/{period}.json")

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
