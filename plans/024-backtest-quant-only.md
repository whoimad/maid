# Plan 024: Backtest the quant-only real ranking against 12-month total return

> **Executor instructions**: Follow this plan step by step. Run every verification command and confirm the expected
> result before moving to the next step. If anything in the "STOP conditions" section occurs, stop and report — do
> not improvise. When done, update the status row for this plan in `plans/README.md`, unless a reviewer dispatched
> you and told you they maintain the index.
>
> **Drift check (run first)**: `git diff --stat 497afb0..HEAD -- src/maid/graph.py src/maid/demo.py src/maid/prices.py src/maid/real_data.py docs/architecture/data.md CLAUDE.md`
> If any in-scope or referenced file changed since this plan was written, compare the "Current state" excerpts against
> the live code before proceeding; on a mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW (new module and script; no existing behaviour changes)
- **Depends on**: plan 023 (DONE: `python -m maid.demo --source sec` ranks the real tech universe)
- **Category**: direction
- **Planned at**: commit `497afb0` on branch `integration/prototype`, 2026-11-02

## Why this matters

MAID ranks 15 real tech companies with a deterministic MCDM engine (CRITIC/entropy/equal weights, then TOPSIS) using
only point-in-time data from 10-Ks filed on or before the decision date 2025-03-31. `docs/SCOPE.md` says the ranking is
then checked with a **backtest**: does the rank go with the total return over the evaluation window
**2025-04-01 to 2026-03-31**? The project has to hold up in interviews: no cherry-picking and no look-ahead. So the
test is fixed *before* the result is seen (one primary test, the others labelled as sensitivity). Post-decision
prices are read **only** by the backtest, never by the graph. With n = 15, only a strong association can be told
apart from chance: |Spearman rho| must exceed about 0.51 for two-sided p < 0.05. A null result is an acceptable and
honest outcome. This run is the quant-only baseline that later LLM-scored runs are compared against.

## Current state

- `src/maid/demo.py`: `run_demo(settings, overrides=None, thread_id="demo") -> dict` runs the graph and returns the
  final state. With `settings={"source": "sec", ...}` the state has:
  - `companies`: labels `"Company A"`..`"Company O"`
  - `tickers`: label -> ticker
  - `scores["topsis"]`: a list in `companies` order
  - `ranking`: labels, best first
  - `weights`: criterion -> weight

  It reads `data/universe/tech.csv` and the SEC cache under `data/cache/sec` by relative path, so run it from the
  repo root.
- `src/maid/graph.py`: `load_sec` is imported at module level (`from maid.real_data import load_sec`), and tests
  replace it with `monkeypatch.setattr(graph, "load_sec", ...)`. `load_sec(decision_date)` returns
  `(labels: dict[label, ticker], quant: dict[label, dict[criterion, float]], meta: dict)`. The criteria are
  `["revenue_growth", "net_margin", "fcf_margin", "rd_intensity"]`. **`graph.py` does not import `maid.prices`**, and
  it must stay that way.
- `src/maid/prices.py` (do not modify):

```python
def total_return(adj_closes: dict[str, float], start: str, end: str) -> float:
    """Total return from the last adjusted close before start to the close on or before end."""
    return close_on(adj_closes, end)[1] / _last_before(adj_closes, start, False)[1] - 1
...
def fetch_series(ticker: str, start: str, end: str, field: str = "Close") -> dict[str, float]:
    """Daily {date: value} for a field over [start, end), cached."""
```

  `fetch_series` caches successes only, under `data/cache/prices` (gitignored). With `start="2025-04-01"`,
  `total_return` buys at the last close **before** 2025-04-01, which is the 2025-03-31 close (decision date). It needs
  a close within 7 days before that, so fetch from `"2025-03-20"`. `end` is exclusive, so fetch to `"2026-04-01"`.
  Use the field `"Adj Close"` (dividends reinvested; yfinance returns it with `auto_adjust=False`).
- **Known Yahoo behaviour, seen by the advisor on 2026-11-02:** under rate limiting, yfinance returns an *empty*
  frame for valid tickers (it logs `possibly delisted; no price data found`). `fetch_series` then raises
  `ValueError("no price data for AAPL ...")`. This is not a bug in our code: plain `yf.Ticker('AAPL').history(...)`
  returned 0 rows three times in a row, minutes after returning 259 rows. Handle it in the script (Step 3): catch per
  ticker, report, exit 1, and re-run later. Successes are cached, so a re-run only fetches what is missing.
- scipy (already a runtime dependency) behaves as checked: `kendalltau([1,2,3,4,5],[1,2,3,4,5])` gives statistic 1.0,
  pvalue 0.01667 (exact, two-sided). `kendalltau([1,2,3,4,5],[1,2,3,5,4])` gives 0.8, pvalue 0.08333.
- Decided rules to honour (quote them in docs, do not change them):
  - D12 (`docs/architecture/decisions.md`): "Kendall tau as the primary ranking-comparison metric; Spearman secondary".
  - SCOPE §5: "Backtest: Spearman correlation of ranks with total return over the evaluation window and a
    risk-adjusted measure". The risk-adjusted measure is still an open SCOPE checklist item ("Risk-adjusted metric
    definition for the backtest") and is **deferred** in this plan.
- Conventions (`CLAUDE.md`): short module docstrings, one-line function docstrings, compact code, do not reformat
  existing code. Tests in `tests/test_<area>.py`, plain `assert`, no network in tests. Real data and derived results
  stay local: the script prints to stdout and writes no files. Script pattern to copy: `scripts/fetch_sec.py`
  (argparse, `main() -> int`, `sys.exit(main())`, errors printed per ticker, exit 1 if any failed).

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Activate | `source .venv/bin/activate` | — |
| Tests | `pytest -q` | all pass (baseline at `497afb0`: `108 passed, 1 skipped`) |
| One file | `pytest -q tests/test_backtest.py` | all pass |
| Lint | `ruff check .` | `All checks passed!` |
| Real run | `python scripts/backtest.py` | table + 3 result lines, exit 0 (needs network or a filled price cache) |

## Scope

**In scope** (the only files you may modify or create):
- `src/maid/backtest.py` (create)
- `scripts/backtest.py` (create)
- `tests/test_backtest.py` (create)
- `docs/architecture/data.md` (new section "Backtest")
- `CLAUDE.md` (two Layout lines)
- `plans/README.md` (status row)

**Out of scope** (do NOT touch):
- `src/maid/prices.py`: the empty-frame behaviour is handled in the script, not here.
- `src/maid/graph.py`, `src/maid/demo.py`, `src/maid/real_data.py`, `src/maid/mcdm/`: the ranking must not change.
- A risk-adjusted metric, other sectors (banks), the GUI.
- Anything under `data/`. Never commit backtest output.

## Git workflow

- Branch: `feat/backtest` from `integration/prototype` at `497afb0` or later.
- Conventional commits, e.g. `feat(backtest): rank vs 12-month total return, quant-only baseline`. Body: `Refs plan 024`.
- Do NOT push, do NOT open a PR.

## Steps

### Step 1: Create `src/maid/backtest.py`

```python
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
```

Rules behind this code:
- Correlate the TOPSIS **score**, not the rank number. A higher score means a better rank, so a positive tau means
  "ranked higher, returned more". Kendall and Spearman are rank-based, so score and rank give the same tau and rho
  except for ties.
- `backtest` receives the returns. It never fetches prices itself, so the graph and the decision-date logic never
  see post-decision data.

**Verify**: `python -c "from maid.backtest import rank_vs_return as f; print(f([1,2,3,4,5],[1,2,3,5,4]))"` →
`kendall_tau` about 0.8 and `kendall_p` about 0.0833.

### Step 2: Tests in `tests/test_backtest.py`

Copy the `no_network` autouse fixture from `tests/test_sec.py:14-19`. Tests (plain `assert`, `pytest.approx`):
1. `test_perfect_agreement`: `rank_vs_return([1,2,3,4,5], [0.1,0.2,0.3,0.4,0.5])` gives `kendall_tau == approx(1)`,
   `kendall_p == approx(1/60)` (exact two-sided for n=5: 2/120), and `spearman_rho == approx(1)`.
2. `test_reversed_is_negative`: reversed returns give `kendall_tau == approx(-1)`.
3. `test_known_swap`: `rank_vs_return([1,2,3,4,5],[1,2,3,5,4])` gives tau `approx(0.8)`, p `approx(0.08333, abs=1e-4)`.
4. `test_bad_inputs_raise`: length mismatch, n=2, and a NaN each raise `ValueError`.
5. `test_backtest_runs_graph_with_given_returns(monkeypatch)`: `monkeypatch.setattr(graph, "load_sec", fake)`
   (`from maid import graph`). `fake` ignores its argument and returns a hand-built 4-company input:

   ```python
   labels = {"Company A": "AAA", "Company B": "BBB", "Company C": "CCC", "Company D": "DDD"}
   vals = [[0.30, 0.25, 0.30, 0.20], [0.10, 0.10, 0.12, 0.08], [0.20, 0.18, 0.20, 0.15], [0.05, 0.02, 0.05, 0.03]]
   quant = {c: dict(zip(TECH_CRITERIA, v)) for c, v in zip(labels, vals)}
   return labels, quant, {}
   ```

   Here A dominates C, C dominates B, and B dominates D, so the TOPSIS order is A, C, B, D under any weights. With
   `returns = {"AAA": 0.4, "CCC": 0.3, "BBB": 0.2, "DDD": 0.1}`, `backtest("equal", returns, n_draws=10)` gives
   `[r["ticker"] for r in res["rows"]] == ["AAA", "CCC", "BBB", "DDD"]`, `res["kendall_tau"] == approx(1)` and
   `res["n"] == 4`.
6. `test_backtest_missing_return_raises(monkeypatch)`: same fake, returns without `"DDD"`, raises `ValueError`
   matching `"DDD"`.
7. `test_graph_never_reads_prices`: `import inspect, maid.graph`; `assert "maid.prices" not in inspect.getsource(maid.graph)`
   and `"fetch_series" not in inspect.getsource(maid.graph)` (look-ahead guard: post-decision prices stay out of the
   graph).

**Verify**: `pytest -q tests/test_backtest.py` → `7 passed`; `pytest -q` → `115 passed, 1 skipped`; `ruff check .` → `All checks passed!`

### Step 3: Create `scripts/backtest.py`

Shape (follow `scripts/fetch_sec.py`):

```python
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
    ...
```

After the price loop, for each `w in WEIGHTINGS` call `backtest(w, returns, a.n_draws)`. Print:
- For `critic` only: a Markdown table `| Rank | Company | Ticker | TOPSIS | Total return |`, with the return as a
  percentage (`f"{x:+.1%}"`).
- For every weighting, one line:
  `f"{w:8s} n={n} kendall_tau={tau:+.3f} (p={kp:.3f})  spearman_rho={rho:+.3f} (p={sp:.3f})"`, with
  `  <- primary` appended for critic.
- A closing line: `"n=15: |rho| > ~0.51 needed for two-sided p < 0.05. Three weightings tested; only critic is the pre-registered primary test."`

Return 0.

**Verify**: `python scripts/backtest.py --help` → usage text, exit 0.

### Step 4: Real run

Run `python scripts/backtest.py` from the repo root. Never print `.env` contents.
- If it exits 1 because of price errors, wait about 10 minutes and re-run, up to 3 runs in total. Each run only
  re-fetches the tickers that are still missing.
- If prices still fail after 3 runs, report the run as **skipped because Yahoo is rate limiting** and paste the error
  lines. This is not a failure of the plan.
- On success, paste the full output into your report. Do not interpret the result beyond the printed numbers.

**Verify**: `git status --short` lists no file under `data/`.

### Step 5: Docs

In `docs/architecture/data.md`, add a section `## Backtest` just before `## Local-only data`. Keep it short:
- Rule: the TOPSIS score from the graph on real data (decision date 2025-03-31, quantitative criteria only) against
  each company's total return from the 2025-03-31 close to the 2026-03-31 close (yfinance `Adj Close`, dividends
  reinvested).
- Primary test, fixed before the result was seen: CRITIC weights (the graph default), Kendall tau, two-sided (D12).
  Spearman rho is secondary. Entropy and equal weights are sensitivity checks, not extra chances to find an effect.
- n = 15: only |rho| > ~0.51 is distinguishable from chance at p < 0.05.
- The risk-adjusted measure (SCOPE §5) is not defined yet and is deferred.
- Look-ahead guard: only `src/maid/backtest.py` and `scripts/backtest.py` read post-decision prices. The graph never
  imports `maid.prices` (tested).
- Run: `python scripts/backtest.py`. Output is printed only and stays local.

Do **not** write the backtest result itself into the docs: it is derived real data and stays local.

In `CLAUDE.md` Layout, add after the `real_data.py` line:
- ``- `src/maid/backtest.py`: rank vs total return (Kendall/Spearman), quant-only baseline``
- ``- `scripts/backtest.py`: run the backtest on the real tech universe (prints only)``

**Verify**: `pytest -q tests/test_docs.py` → all pass; `pytest -q` → `115 passed, 1 skipped`.

## Test plan

Seven offline tests in `tests/test_backtest.py` (listed in Step 2). They cover:
- correlation values and the exact p-value against known small cases;
- input validation;
- the full graph-to-backtest path with a hand-built dominance example, so the expected order holds under any weights;
- a missing return;
- the look-ahead guard (the graph never reads prices).

Structural pattern: `tests/test_real_data.py` (monkeypatching `graph.load_sec`).

## Done criteria

- [ ] `pytest -q` → `115 passed, 1 skipped` (baseline + 7)
- [ ] `ruff check .` → `All checks passed!`
- [ ] `python scripts/backtest.py --help` exits 0
- [ ] `grep -n "maid.prices" src/maid/graph.py` → no match
- [ ] `git status --short` lists only in-scope files; nothing under `data/`
- [ ] Step 4 real run output pasted, or reported as skipped with the Yahoo error lines

## STOP conditions

- `run_demo`'s output no longer has `tickers` or `scores["topsis"]` (the plan 023 contract changed).
- Test 5 does not give the order AAA, CCC, BBB, DDD. Report the actual order; do not change the test data to fit.
- The real run fails for a reason other than Yahoo returning no data or a network error. Examples: a `tech_criteria`
  error, or a return outside -100% to +1000%. Report it.
- You feel the need to change `prices.py`, the graph or the ranking to get a result. Out of scope.

## Maintenance notes

- When LLM-scored criteria are added, re-run the same script unchanged. The quant-only output from this plan is the
  baseline to compare against, so keep it in local notes. The primary test stays CRITIC + Kendall tau unless a
  decision record changes it **before** the new result is seen.
- `scripts/backtest.py` builds the graph 4 times: once for the ticker list and once per weighting. It's cheap, since
  everything comes from cache.
- Deferred: risk-adjusted measure (SCOPE open item); a permutation test (scipy's exact Kendall p is already
  permutation-exact without ties); a bank backtest (bank criteria are still OPEN).
- If Yahoo rate limiting gets worse, the clean fix is in `prices.fetch_series`: treat an empty frame for a known-listed
  ticker as retryable with a longer backoff. That's a separate small plan.
