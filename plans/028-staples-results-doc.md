# Plan 028: Write up backtest #2 (consumer staples): a null result, summary statistics only

> **Executor instructions**: Follow this plan step by step. Run every verification command and confirm the expected
> result before moving to the next step. If anything in the "STOP conditions" section occurs, stop and report — do
> not improvise. The reviewer maintains `plans/README.md`; do not edit it.
>
> **Drift check (run first)**: `git diff --stat 99ea26d..HEAD -- docs/research/ docs/architecture/data.md`
> → no output expected.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW (docs only)
- **Depends on**: plan 027 (DONE, merged `99ea26d`)
- **Category**: docs
- **Planned at**: commit `99ea26d` on branch `integration/prototype`, 2026-11-03

## Why this matters

The staples backtest was pre-registered in `docs/architecture/data.md`, which promises: "The result is written up
whatever it is, with summary statistics only (per-company returns stay local)." The reviewer ran it on 2026-11-03.
This plan records the result. All numbers below come from the reviewer's run; **copy them exactly, do not recompute,
and never add per-company returns, tickers or names** (owner rule: price-derived per-company data stays local).

## Current state

- `docs/research/backtest-quant-only-results.md`: backtest #1 (tech). The new file follows the same shape.
- `docs/research/README.md` ends with:

  ```
  Results of our own runs (not desk research):
  - `weight-stability-results.md`: spike #6, entropy vs CRITIC weight stability (synthetic)
  - `backtest-quant-only-results.md`: backtest #1, quant-only ranking vs 12-month return: null result, power analysis, next options
  ```

- `docs/architecture/data.md`, last bullet of `### Backtest #2: consumer staples (...)`:

  ```
  - Run: `python scripts/backtest.py --sector staples --no-outcome KVUE`.
  ```

- `tests/test_docs.py::test_relative_markdown_links_resolve` checks that every relative Markdown link resolves.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Setup | `git reset --hard 99ea26d` in your clean worktree; `git log --oneline -1` | shows `99ea26d` |
| Tests | `PYTHONPATH=$PWD/src /home/imad/maid/.venv/bin/python -m pytest -q` | 146 passed, 1 skipped |
| Lint | `/home/imad/maid/.venv/bin/ruff check .` | `All checks passed!` |

## Scope

In scope: create `docs/research/backtest-staples-results.md`; one line in `docs/research/README.md`; one bullet in
`docs/architecture/data.md` (Backtest #2 section). Nothing else. No code, no network, no scripts.

## Git workflow

Branch `docs/staples-results`. One commit: `docs(research): backtest #2 staples null result`, body `Refs #16`, ending
with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Do not push or merge.

## Steps

### Step 1: create `docs/research/backtest-staples-results.md` with exactly this content

````markdown
# Backtest #2: the quant-only ranking does not predict 12-month returns in consumer staples (a null result)

Reproduce: `python scripts/backtest.py --sector staples --no-outcome KVUE` (needs the local SEC cache and yfinance).
Plans 025–027 built it, and it was run on 2026-11-03. The test was pre-registered in
[data.md](../architecture/data.md) before any staples return was computed. This note gives only summary statistics;
the per-company table is derived from price data, so it stays local (owner rule).

## Question and design (fixed before the result was seen)

Backtest #1 (15 tech companies, [backtest-quant-only-results.md](backtest-quant-only-results.md)) found nothing but
had almost no power. This test asks the same question, SCOPE §1 (c): is the MCDM ranking informative about
subsequent performance? It uses a larger universe and **no LLM**.

- **Companies:** 61 US consumer-staples companies chosen by rule (D19): SIC food and beverages, tobacco, household
  products and grocery, market cap of at least $1bn on 2025-03-31. 19 companies were excluded before the run (no
  Yahoo price, or criteria gaps).
- **Deviation, decided before any return was seen:** Kenvue has no price history on Yahoo any more. It stays in the
  ranking (weights and labels as pre-registered) but has no outcome, so the test uses **n = 60**.
- **Inputs:** revenue growth, net margin, FCF margin and ROA from the latest 10-K filed on or before 2025-03-31.
- **Ranking:** CRITIC weights, then TOPSIS (graph defaults). CRITIC weights: revenue growth 0.31, FCF margin 0.26,
  ROA 0.24, net margin 0.19.
- **Outcome:** total return with dividends reinvested, from the 2025-03-31 close to the 2026-03-31 close. No company
  stopped trading inside the window.
- **Primary test:** Kendall tau between TOPSIS score and return, two-sided, alpha = 0.05. Spearman rho is secondary;
  entropy and equal weights are sensitivity checks only.

## Result

| Weighting | Kendall tau | p | Spearman rho | p |
|---|---|---|---|---|
| **CRITIC (primary)** | −0.096 | 0.28 | −0.136 | 0.30 |
| Entropy | +0.044 | 0.62 | +0.043 | 0.75 |
| Equal | −0.043 | 0.63 | −0.069 | 0.60 |

No association. The primary estimate is slightly negative and not significant; the sensitivity checks do not even
agree on the sign.

Descriptive only (not part of the pre-registered test): it was a weak year for the sector. The median company
returned −15% and the mean −8%. Mean return by quarter of the CRITIC ranking, best-ranked first: −11%, −14%, −21%,
+12% (medians −13%, −16%, −24%, +4%). The lowest-ranked quarter did best, which matches the slightly negative tau.
A split chosen after seeing the data is not evidence; it is reported only so that nothing is hidden.

## What this does and does not show

**This test says more than backtest #1.** At n = 60, an approximate 95% interval for the primary Kendall tau is
−0.27 to +0.08 (normal approximation, ignoring ties). Under a bivariate-normal model, tau = +0.08 corresponds to a
correlation of about 0.13. So the data argue against a positive link of the size the power analysis cared about
(0.2 to 0.3), not merely fail to find one. Pre-registered power was 12%, 32% and 60% for true correlations of 0.1, 0.2
and 0.3.

**Still one period and one sector.** One 12-month window is one draw of the market regime. In this window the whole
sector fell, and moves common to all staples dominate a single cross-section.

**What a null here is consistent with.** The four ratios come from a 10-K that was public on the decision date, so
the market already knew them. Little predictive power was the prior expectation, and two sectors now agree with it.
It does not show the pipeline is broken: the same run reproduces the pre-registered ranking.

## What it means for the project

The quant-only ranking stays as the baseline. Any LLM-scored ranking is compared against it, inside an evaluation
fixed before its run, with leakage controls (the scoring model may know what happened after 2025-03-31; see
[llm-agents-finance.md](llm-agents-finance.md), abstract-only, UNVERIFIED). Options that need no new returns, such
as stability (rank intervals, D13 and D16) and agreement between LLM scores and human review, remain the parts of the
research question this project can answer well.
````

Verify: `test -f docs/research/backtest-staples-results.md && grep -c "−0.096" docs/research/backtest-staples-results.md` → `2` or more is fine, at least `1`.

### Step 2: research index

Append after the `backtest-quant-only-results.md` line in `docs/research/README.md`:

```
- `backtest-staples-results.md`: backtest #2, 60 consumer-staples companies, pre-registered: null result (primary Kendall tau −0.10, p = 0.28)
```

### Step 3: data.md

After the Run bullet of the Backtest #2 section (the line containing `--no-outcome KVUE`), add:

```
- Result (2026-11-03): no association (primary Kendall tau −0.10, p = 0.28, n = 60). See [backtest-staples-results.md](../research/backtest-staples-results.md).
```

### Step 4: gates and commit

Tests 146 passed, 1 skipped (the link test covers the new links). Ruff clean. `git diff --stat 99ea26d..HEAD` shows
exactly the three files. Commit.

## Done criteria

- One commit on `docs/staples-results`, three files changed (one new).
- `pytest -q` → 146 passed, 1 skipped; `ruff check .` clean.
- `grep -E "KVUE|Kenvue" docs/research/backtest-staples-results.md` shows only Kenvue in the deviation bullet (no
  other company names or tickers anywhere in the new file).

## STOP conditions

- The drift check shows changes.
- The link test fails and the fix would need edits outside the three files.
- You are tempted to add, recompute or "correct" any number: stop and report instead.

## Maintenance notes

- If the staples backtest is ever re-run with different inputs, this file describes the 2026-11-03 run only; add a
  new dated section rather than overwriting the numbers.
