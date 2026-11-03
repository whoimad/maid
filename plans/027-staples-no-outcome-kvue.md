# Plan 027: Backtest leaves companies with no price history out of the correlation (Kenvue), with a documented deviation

> **Executor instructions**: Follow this plan step by step. Run every verification command and confirm the expected
> result before moving to the next step. If anything in the "STOP conditions" section occurs, stop and report — do
> not improvise. The reviewer maintains `plans/README.md`; do not edit it.
>
> **Drift check (run first)**: `git diff --stat 02e61a8..HEAD -- src/maid/backtest.py scripts/backtest.py tests/test_backtest.py docs/architecture/data.md`
> If any in-scope file changed since then, compare the "Current state" excerpts against the live code before
> proceeding; on a mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW (default behaviour unchanged; guarded by existing tests)
- **Depends on**: plan 026 (DONE)
- **Category**: direction
- **Planned at**: commit `02e61a8` on branch `integration/prototype`, 2026-11-03

## Why this matters

MAID ranks companies with a deterministic MCDM engine (CRITIC weights, then TOPSIS) on 10-K numbers as of
2025-03-31, then a backtest correlates the TOPSIS score with each company's total return from 2025-03-31 to
2026-03-31 (Kendall tau). The staples test was **pre-registered** in `docs/architecture/data.md` on 61 frozen
companies. One of them, Kenvue (ticker KVUE), now has **no price history on Yahoo** (checked 2026-11-03: KVUE returns
0 rows for the window and a single row dated 2026-10-30 for `period="max"`, while KMB and MSFT returned 259 rows in
the same call; it is probably delisted after Kimberly-Clark's acquisition, not verified). The script therefore exits 1
and the test cannot run.

The owner decided: drop Kenvue from the test with a documented note (n = 60). To change the pre-registration as
little as possible, Kenvue **stays in the frozen universe and in the ranking** (so CRITIC weights and the
"Company 0xx" labels are exactly as pre-registered); it is only left out of the correlation, because it has no
outcome. This is an explicit, named list passed on the command line, never an automatic skip: an empty Yahoo answer
is usually rate limiting, and silently skipping would hide that.

**You write code, tests and doc text only. Never fetch prices or run `scripts/backtest.py` without `--help`. No
network.** The reviewer runs the real backtest afterwards.

## Current state

- `src/maid/backtest.py:39-51` — `backtest()` runs the graph and raises if any ranked ticker has no return:

  ```python
  def backtest(weighting: str, returns: dict[str, float], n_draws: int = 50, sector: str = "tech") -> dict:
      """Run the graph on real data (source="sec") and correlate TOPSIS scores with returns by ticker."""
      from maid.demo import run_demo

      s = run_demo({"source": "sec", "sector": sector, "weighting": weighting, "n_draws": n_draws},
                   thread_id=f"backtest-{sector}-{weighting}")
      tickers = [s["tickers"][c] for c in s["companies"]]
      if missing := [t for t in tickers if t not in returns]:
          raise ValueError(f"no return for {missing}")
      rows = [{"label": c, "ticker": s["tickers"][c], "topsis": s["scores"]["topsis"][s["companies"].index(c)],
               "return": returns[s["tickers"][c]]} for c in s["ranking"]]
      stats = rank_vs_return([x["topsis"] for x in rows], [x["return"] for x in rows])
      return {"weighting": weighting, "weights": s["weights"], "rows": rows, **stats}
  ```

- `scripts/backtest.py` — `main()` builds `tickers` from the graph, fetches each with `fetch_series`, collects
  `failed`, returns 1 if any failed, then for each weighting calls `backtest(w, returns, a.n_draws, a.sector)` and
  prints a table (CRITIC only) and one stats line per weighting. Arguments today:

  ```python
  ap.add_argument("--sector", choices=["tech", "staples"], default="tech")
  ap.add_argument("--n-draws", type=int, default=50)
  ```

  The module docstring starts `Usage (from the repo root): python scripts/backtest.py [--sector tech|staples] [--n-draws 50]`.

- `tests/test_backtest.py` — offline tests. Exemplar to copy (uses the `_fake` loader with tickers AAA, BBB, CCC, DDD):

  ```python
  def test_backtest_missing_return_raises(monkeypatch):
      monkeypatch.setattr(graph, "load_sec", _fake)
      with pytest.raises(ValueError, match="DDD"):
          backtest("equal", {"AAA": 0.4, "CCC": 0.3, "BBB": 0.2}, n_draws=10)
  ```

- `docs/architecture/data.md`, section `### Backtest #2: consumer staples (pre-registered 2026-11-03, before any
  staples return was computed)`. Its first bullet:

  ```
  - Universe: the 61 companies in `data/universe/staples.csv` (plan 025, D19). No company is added or removed; the 19
    in `staples_excluded.csv` stay out.
  ```

  and its last bullet: `- Run: \`python scripts/backtest.py --sector staples\`.`

Conventions (CLAUDE.md): short module docstrings, one-line function docstrings, compact code, do not reformat existing
code, tests use plain `assert`, no network in tests. Lines up to 120 chars (ruff).

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Setup (once) | `git reset --hard 02e61a8` in your clean worktree, then `test -f plans/027-staples-no-outcome-kvue.md` | exit 0 |
| Tests | `PYTHONPATH=$PWD/src /home/imad/maid/.venv/bin/python -m pytest -q` | all pass (143 passed, 1 skipped before your change) |
| Lint | `/home/imad/maid/.venv/bin/ruff check .` | `All checks passed!` |

Your worktree starts from `main`, which lacks this work: run the reset first. Use the main repo's venv with
`PYTHONPATH` pointing at your worktree's `src`.

## Scope

In scope: `src/maid/backtest.py` (`backtest()` only), `scripts/backtest.py`, `tests/test_backtest.py`,
`docs/architecture/data.md` (Backtest #2 section only).

Out of scope — do not touch: `data/universe/*.csv` (frozen; Kenvue must stay in `staples.csv`), `src/maid/real_data.py`,
`src/maid/graph.py`, `src/maid/prices.py`, `window_return`, `rank_vs_return`, `plans/README.md`, anything under
`data/cache/` or `notes/`.

## Git workflow

Branch `fix/backtest-no-outcome`. Two commits, conventional style, body `Refs #16`:
1. `docs(data): staples deviation, Kenvue has no price history` (Step 1 only — the deviation is recorded first).
2. `feat(backtest): --no-outcome keeps a company ranked but out of the correlation` (Steps 2–4).

End each commit message with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Do not push or merge.

## Steps

### Step 1: record the deviation in data.md (commit 1)

In the Backtest #2 section, directly after the "Universe:" bullet, add this bullet (keep the wording):

```
- **Deviation (2026-11-03, decided before any staples return or statistic was seen):** Kenvue (KVUE) has no price
  history on Yahoo any more (0 rows for the window; KMB and MSFT fetched fine in the same call; probably delisted
  after Kimberly-Clark's acquisition, not verified). Kenvue stays in the universe and in the ranking, so the CRITIC
  weights and labels are as pre-registered, but it has no outcome and is left out of the correlation: **n = 60**.
  This is the same "no Yahoo price, no place in the test" rule as the 19 excluded companies, applied after the freeze.
  Owner decision.
```

Change the Run bullet to: `- Run: \`python scripts/backtest.py --sector staples --no-outcome KVUE\`.`

Verify: `grep -c "no-outcome KVUE" docs/architecture/data.md` → `1`; tests pass (the doc link test runs). Commit 1.

### Step 2: `backtest()` accepts `no_outcome`

New signature: `backtest(weighting, returns, n_draws=50, sector="tech", no_outcome=())`. Behaviour:
- The graph still ranks every company (do not change the `run_demo` call).
- `unknown = [t for t in no_outcome if t not in tickers]` → `ValueError(f"no_outcome tickers not in the universe: {unknown}")`.
- `both = [t for t in no_outcome if t in returns]` → `ValueError(f"no_outcome tickers have a return: {both}")`.
- The "missing return" check ignores tickers in `no_outcome`; any other missing ticker still raises as today.
- `rows` keeps only companies with a return (still in ranking order); stats are computed on those rows.
- The result dict gains `"no_outcome": sorted(no_outcome)`.

Update the one-line docstring, e.g. `"""Run the graph on real data and correlate TOPSIS scores with returns; no_outcome tickers are ranked but left out."""`
(≤ 120 chars).

### Step 3: tests

Add to `tests/test_backtest.py`, following the exemplar:
1. `test_backtest_no_outcome_left_out`: returns for AAA, CCC, BBB only, `no_outcome=["DDD"]` →
   `res["n"] == 3`, `"DDD" not in [r["ticker"] for r in res["rows"]]`, `res["no_outcome"] == ["DDD"]`,
   `res["kendall_tau"] == pytest.approx(1)`.
2. `test_backtest_no_outcome_unknown_raises`: `no_outcome=["ZZZ"]` with all four returns → `ValueError` matching `ZZZ`.
3. `test_backtest_no_outcome_with_return_raises`: all four returns and `no_outcome=["DDD"]` → `ValueError` matching `DDD`.

The existing `test_backtest_missing_return_raises` must still pass unchanged.

Verify: `pytest -q tests/test_backtest.py` → all pass.

### Step 4: script flag

In `scripts/backtest.py`:
- `ap.add_argument("--no-outcome", action="append", default=[], metavar="TICKER", help="ranked but left out of the correlation (no price history); see data.md")`
- If any `--no-outcome` ticker is not in `tickers`, print an error to stderr and return 2.
- Skip those tickers in the fetch loop (do not fetch them).
- Before the results, if the list is non-empty, print `no outcome (ranked, left out of the correlation): KVUE` (comma-joined, sorted).
- Pass `no_outcome=a.no_outcome` to `backtest(...)`.
- Update the docstring usage line to `[--sector tech|staples] [--no-outcome TICKER ...] [--n-draws 50]`.

Verify: `PYTHONPATH=$PWD/src /home/imad/maid/.venv/bin/python scripts/backtest.py --help` shows `--no-outcome`
(this makes no network call). Do not run it without `--help`.

### Step 5: full gates, commit 2

Tests: all pass, 146 passed, 1 skipped (143 + 3). Ruff clean. Commit 2.

## Done criteria

- `git log --oneline 02e61a8..HEAD` shows exactly the two commits, docs first.
- `pytest -q` → 146 passed, 1 skipped; `ruff check .` → clean.
- `git diff --stat 02e61a8..HEAD` touches only the four in-scope files.
- `grep -c KVUE data/universe/staples.csv` → `1` (Kenvue still in the universe).
- `scripts/backtest.py --help` lists `--no-outcome`.

## STOP conditions

- The drift check shows changes to an in-scope file and the excerpts do not match.
- Test count before your change is not 143 passed, 1 skipped.
- Any step would need a network call, a change to `data/universe/*.csv`, or a change to the graph or ranking.
- You find another way to compute KVUE's return (another data source): do not add it; report it.

## Maintenance notes

- `--no-outcome` is a deviation tool, not a filter: each use must have a matching dated note in `data.md` written
  before the result is seen. Reviewers should reject any use without one.
- If more companies lose their Yahoo history later, re-running the staples test will fail again; that is intended.
