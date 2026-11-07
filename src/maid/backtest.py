"""Backtest: MCDM scores on the decision date vs total return in the evaluation window (see docs/architecture/data.md)."""
from datetime import date, timedelta

import numpy as np
from scipy.stats import kendalltau, spearmanr

from maid.prices import close_on

WINDOW = ("2025-04-01", "2026-03-31")  # evaluation window (D3/D17); buy at the 2025-03-31 close
WEIGHTINGS = ["critic", "entropy", "equal"]  # critic (the graph default) is the primary test; others are sensitivity


def rank_vs_return(scores, returns) -> dict:
    """Kendall tau (primary, D12) and Spearman rho of scores vs returns, two-sided p-values."""
    s, r = np.asarray(scores, dtype=float), np.asarray(returns, dtype=float)
    if s.shape != r.shape or s.ndim != 1 or len(s) < 3:
        raise ValueError(f"need two equal-length 1-D vectors with n >= 3, got {s.shape} and {r.shape}")
    if not (np.isfinite(s).all() and np.isfinite(r).all()):
        raise ValueError("scores and returns must be finite")
    k, sp = kendalltau(s, r), spearmanr(s, r)
    return {"n": len(s), "kendall_tau": float(k.statistic), "kendall_p": float(k.pvalue),
            "spearman_rho": float(sp.statistic), "spearman_p": float(sp.pvalue)}


def window_return(adj_closes: dict[str, float], start: str, end: str) -> dict:
    """Return over the window; a stock that stops trading inside it keeps its return to the last close (then cash, 0%)."""
    base = close_on(adj_closes, (date.fromisoformat(start) - timedelta(days=1)).isoformat())[1]
    try:
        day, c = close_on(adj_closes, end)
        return {"return": c / base - 1, "last_day": day, "delisted": False}
    except ValueError:
        inside = [d for d in adj_closes if start <= d <= end]
        if not inside:
            raise ValueError(f"no closes in the window {start}..{end}") from None
        day = max(inside)
        return {"return": adj_closes[day] / base - 1, "last_day": day, "delisted": True}


def backtest(weighting: str, returns: dict[str, float], n_draws: int = 50, sector: str = "tech",
             no_outcome=()) -> dict:
    """Run the graph on real data and correlate TOPSIS scores with returns; no_outcome tickers are ranked but left out."""
    from maid.demo import run_demo

    s = run_demo({"source": "sec", "sector": sector, "weighting": weighting, "n_draws": n_draws},
                 thread_id=f"backtest-{sector}-{weighting}")
    tickers = [s["tickers"][c] for c in s["companies"]]
    if unknown := [t for t in no_outcome if t not in tickers]:
        raise ValueError(f"no_outcome tickers not in the universe: {unknown}")
    if both := [t for t in no_outcome if t in returns]:
        raise ValueError(f"no_outcome tickers have a return: {both}")
    if missing := [t for t in tickers if t not in returns and t not in no_outcome]:
        raise ValueError(f"no return for {missing}")
    rows = [{"label": c, "ticker": s["tickers"][c], "topsis": s["scores"]["topsis"][s["companies"].index(c)],
             "return": returns[s["tickers"][c]]} for c in s["ranking"] if s["tickers"][c] not in no_outcome]
    stats = rank_vs_return([x["topsis"] for x in rows], [x["return"] for x in rows])
    return {"weighting": weighting, "weights": s["weights"], "rows": rows, "no_outcome": sorted(no_outcome), **stats}
