"""Backtest: MCDM scores on the decision date vs total return in the evaluation window (see docs/architecture/data.md)."""
import numpy as np
from scipy.stats import kendalltau, spearmanr

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


def backtest(weighting: str, returns: dict[str, float], n_draws: int = 50) -> dict:
    """Run the graph on real data (source="sec") and correlate TOPSIS scores with returns by ticker."""
    from maid.demo import run_demo

    s = run_demo({"source": "sec", "weighting": weighting, "n_draws": n_draws}, thread_id=f"backtest-{weighting}")
    tickers = [s["tickers"][c] for c in s["companies"]]
    if missing := [t for t in tickers if t not in returns]:
        raise ValueError(f"no return for {missing}")
    rows = [{"label": c, "ticker": s["tickers"][c], "topsis": s["scores"]["topsis"][s["companies"].index(c)],
             "return": returns[s["tickers"][c]]} for c in s["ranking"]]
    stats = rank_vs_return([x["topsis"] for x in rows], [x["return"] for x in rows])
    return {"weighting": weighting, "weights": s["weights"], "rows": rows, **stats}
