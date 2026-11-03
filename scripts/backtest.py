"""Backtest the quant-only real ranking: TOPSIS score on 2025-03-31 vs total return 2025-04-01..2026-03-31.

Usage (from the repo root): python scripts/backtest.py [--sector tech|staples] [--no-outcome TICKER ...] [--n-draws 50]
Needs the SEC cache (or SEC_USER_AGENT) and network for yfinance; prices are cached under data/cache (local only).
Prints only; writes nothing. Primary test: CRITIC weights, Kendall tau. Entropy and equal weights are sensitivity.
A company that stops trading inside the window keeps its return to the last close (then cash, 0%).
"""
import argparse
import sys

from maid.backtest import WEIGHTINGS, WINDOW, backtest, window_return
from maid.demo import run_demo
from maid.prices import fetch_series


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sector", choices=["tech", "staples"], default="tech")
    ap.add_argument("--n-draws", type=int, default=50)
    ap.add_argument("--no-outcome", action="append", default=[], metavar="TICKER",
                    help="ranked but left out of the correlation (no price history); see data.md")
    a = ap.parse_args()
    tickers = sorted(run_demo({"source": "sec", "sector": a.sector, "n_draws": 1}, thread_id="tickers")["tickers"].values())
    if unknown := [t for t in a.no_outcome if t not in tickers]:
        print(f"--no-outcome tickers not in the universe: {unknown}", file=sys.stderr)
        return 2
    returns, failed, delisted = {}, [], []
    for t in tickers:
        if t in a.no_outcome:
            continue
        try:
            series = fetch_series(t, "2025-03-20", "2026-04-01", "Adj Close")
            if not series:
                raise ValueError("empty price series")
            w = window_return(series, *WINDOW)
            returns[t] = w["return"]
            if w["delisted"]:
                delisted.append(f"{t} (last close {w['last_day']})")
        except Exception as e:  # yfinance: empty frame under rate limiting, network errors
            print(f"{t}: ERROR {e}")
            failed.append(t)
    if failed:
        print(f"{len(failed)} tickers without prices (Yahoo often returns empty data when rate limiting). "
              "Re-run later; successful downloads are cached.", file=sys.stderr)
        return 1
    if a.no_outcome:
        print("no outcome (ranked, left out of the correlation): " + ", ".join(sorted(a.no_outcome)))
    print("delisted inside the window: " + (", ".join(delisted) or "none"))
    for w in WEIGHTINGS:
        res = backtest(w, returns, a.n_draws, a.sector, no_outcome=a.no_outcome)
        if w == "critic":
            print("| Rank | Company | Ticker | TOPSIS | Total return |\n|---|---|---|---|---|")
            for i, x in enumerate(res["rows"], 1):
                print(f"| {i} | {x['label']} | {x['ticker']} | {x['topsis']:.3f} | {x['return']:+.1%} |")
        print(f"{w:8s} n={res['n']} kendall_tau={res['kendall_tau']:+.3f} (p={res['kendall_p']:.3f})  "
              f"spearman_rho={res['spearman_rho']:+.3f} (p={res['spearman_p']:.3f})"
              + ("  <- primary" if w == "critic" else ""))
    print(f"n={len(returns)}. Only the CRITIC Kendall tau is the pre-registered primary test (data.md); "
          "entropy and equal are sensitivity.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
