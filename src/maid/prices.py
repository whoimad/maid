"""Prices via yfinance (cached on disk, local only). Pure helpers work on {date: value} dicts."""
from datetime import date as _date
from datetime import datetime, timedelta

from maid.cache import DiskCache
from maid.config import get_settings

LOOKBACK_DAYS = 7


def _d(s: str) -> _date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def _last_before(closes: dict[str, float], date: str, inclusive: bool) -> tuple[str, float]:
    lo = (_d(date) - timedelta(days=LOOKBACK_DAYS)).isoformat()
    days = [d for d in closes if lo <= d and (d <= date if inclusive else d < date)]
    if not days:
        raise ValueError(f"no close within {LOOKBACK_DAYS} days {'on or ' if inclusive else ''}before {date}")
    day = max(days)
    return day, closes[day]


def close_on(closes: dict[str, float], date: str) -> tuple[str, float]:
    """Last (day, close) with day <= date, at most 7 calendar days back."""
    return _last_before(closes, date, True)


def split_factor_after(splits: dict[str, float], date: str) -> float:
    """Product of split ratios for split days strictly after date."""
    f = 1.0
    for d, r in splits.items():
        if d > date:
            f *= r
    return f


def total_return(adj_closes: dict[str, float], start: str, end: str) -> float:
    """Total return from the last adjusted close before start to the close on or before end."""
    return close_on(adj_closes, end)[1] / _last_before(adj_closes, start, False)[1] - 1


def _cache() -> DiskCache:
    return DiskCache(get_settings().cache_dir / "prices")


def fetch_series(ticker: str, start: str, end: str, field: str = "Close") -> dict[str, float]:
    """Daily {date: value} for a field over [start, end), cached."""
    def go():
        import yfinance as yf
        h = yf.Ticker(ticker).history(start=start, end=end, auto_adjust=False)
        if h.empty:
            raise ValueError(f"no price data for {ticker} {start}..{end}")
        return {i.strftime("%Y-%m-%d"): float(v) for i, v in h[field].items()}
    return _cache().get_or_compute(DiskCache.key("yf", ticker, field, start, end), go)


def fetch_splits(ticker: str) -> dict[str, float]:
    """{date: ratio} split history, cached per day so one run is stable."""
    def go():
        import yfinance as yf
        return {i.strftime("%Y-%m-%d"): float(v) for i, v in yf.Ticker(ticker).splits.items()}
    return _cache().get_or_compute(DiskCache.key("yf", ticker, "splits", _date.today().isoformat()), go)


def market_price_on(ticker: str, date: str) -> dict:
    """Unadjusted close on or before date: split-adjusted close times later splits."""
    start = (_d(date) - timedelta(days=10)).isoformat()
    end = (_d(date) + timedelta(days=1)).isoformat()
    day, c = close_on(fetch_series(ticker, start, end, "Close"), date)
    f = split_factor_after(fetch_splits(ticker), date)
    return {"date": day, "close_adj": c, "split_factor": f, "close": c * f}
