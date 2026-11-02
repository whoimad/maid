"""Backtest the quant-only real ranking: TOPSIS score on 2025-03-31 vs total return 2025-04-01..2026-03-31.

Usage (from the repo root): python scripts/backtest.py [--n-draws 50]
Needs the SEC cache (or SEC_USER_AGENT) and network for yfinance; prices are cached under data/cache (local only).
Prints only; writes nothing. Primary test: CRITIC weights, Kendall tau. Entropy and equal weights are sensitivity.
"""
import argparse
import sys

from maid.backtest import WEIGHTINGS, WINDOW, backtest
from maid.demo import run_demo
from maid.prices import fetch_series, total_return


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-draws", type=int, default=50)
    a = ap.parse_args()
    tickers = sorted(run_demo({"source": "sec", "n_draws": 1}, thread_id="tickers")["tickers"].values())
    returns, failed = {}, []
    for t in tickers:
        try:
            returns[t] = total_return(fetch_series(t, "2025-03-20", "2026-04-01", "Adj Close"), *WINDOW)
        except Exception as e:  # yfinance: empty frame under rate limiting, network errors
            print(f"{t}: ERROR {e}")
            failed.append(t)
    if failed:
        print(f"{len(failed)} tickers without prices (Yahoo often returns empty data when rate limiting). "
              "Re-run later; successful downloads are cached.", file=sys.stderr)
        return 1
    for w in WEIGHTINGS:
        res = backtest(w, returns, a.n_draws)
        if w == "critic":
            print("| Rank | Company | Ticker | TOPSIS | Total return |\n|---|---|---|---|---|")
            for i, x in enumerate(res["rows"], 1):
                print(f"| {i} | {x['label']} | {x['ticker']} | {x['topsis']:.3f} | {x['return']:+.1%} |")
        print(f"{w:8s} n={res['n']} kendall_tau={res['kendall_tau']:+.3f} (p={res['kendall_p']:.3f})  "
              f"spearman_rho={res['spearman_rho']:+.3f} (p={res['spearman_p']:.3f})"
              + ("  <- primary" if w == "critic" else ""))
    print("n=15: |rho| > ~0.51 needed for two-sided p < 0.05. "
          "Three weightings tested; only critic is the pre-registered primary test.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
