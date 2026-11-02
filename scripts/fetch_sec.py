"""Print point-in-time tech criteria from SEC XBRL for tickers (needs SEC_USER_AGENT; cache is local only).

Usage: python scripts/fetch_sec.py AAPL MSFT [--date 2025-03-31]
"""
import argparse
import sys

from maid.config import get_settings
from maid.sec import SecClient, ticker_to_cik
from maid.xbrl import TECH_CRITERIA, tech_criteria


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("tickers", nargs="+")
    ap.add_argument("--date", default=get_settings().decision_date)
    a = ap.parse_args()
    client, failed = SecClient(), False
    try:
        tj = client.tickers()
        for t in a.tickers:
            try:
                r = tech_criteria(client.companyfacts(ticker_to_cik(tj, t)), a.date)
            except ValueError as e:
                if "SEC_USER_AGENT" in str(e):
                    raise
                print(f"{t}: ERROR {e}")
                failed = True
                continue
            vals = " ".join(f"{k}={r['values'][k]:.3f}" for k in TECH_CRITERIA)
            print(f"{t} period_end={r['period_end']} filed={r['filed']} {vals} tags={r['tags']}")
    except ValueError as e:
        print(f"ERROR {e}", file=sys.stderr)
        return 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
