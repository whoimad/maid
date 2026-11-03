# Plan 026: Run the graph and the backtest on the staples universe (code + pre-registration; no real run)

> **Executor instructions**: Follow this plan step by step. Run every verification command and confirm the expected
> result before moving to the next step. If anything in the "STOP conditions" section occurs, stop and report — do
> not improvise. When done, update the status row for this plan in `plans/README.md`, unless a reviewer dispatched
> you and told you they maintain the index.
>
> **Drift check (run first)**: `git diff --stat <BASE>..HEAD -- src/maid/real_data.py src/maid/graph.py src/maid/demo.py src/maid/backtest.py scripts/backtest.py tests/test_real_data.py tests/test_backtest.py docs/architecture/data.md`
> (`<BASE>` is the commit the reviewer gives you.) If any in-scope file changed since then, compare the "Current
> state" excerpts against the live code before proceeding; on a mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: LOW (tech results must stay identical except for the label text; guarded by tests)
- **Depends on**: plan 025 (DONE: `data/universe/staples.csv`, 61 companies; `xbrl.staples_criteria`)
- **Category**: direction
- **Planned at**: commit `4bf145c` on branch `integration/prototype`, 2026-11-03

## Why this matters

MAID ranks companies with a deterministic MCDM engine (CRITIC weights, then TOPSIS) on point-in-time 10-K numbers
as of the decision date 2025-03-31. The first backtest (15 tech companies) found nothing, with almost no power. Plan
025 froze a larger universe: 61 US consumer-staples companies (market cap ≥ $1bn), with four criteria
`revenue_growth, net_margin, fcf_margin, roa`. This plan makes the graph and the backtest run on that universe, and
writes the test into `docs/architecture/data.md` **before** anyone runs it (pre-registration: the test is fixed
before the result is seen, so it can't be tuned to the data). **You write code, tests and the pre-registration
text only. You never fetch or compute a return after 2025-03-31; the reviewer runs the real backtest afterwards.**

## Current state

- `src/maid/real_data.py` (42 lines): tech only.

  ```python
  # src/maid/real_data.py:5-41
  from maid.xbrl import TECH_CRITERIA, tech_criteria
  UNIVERSE = Path("data/universe/tech.csv")

  def anonymize(tickers: list[str]) -> dict[str, str]:
      """Label -> ticker; labels "Company A", "Company B", ... in alphabetical ticker order (no size information)."""
      if len(set(tickers)) != len(tickers) or len(tickers) > 26:
          raise ValueError(f"need up to 26 distinct tickers: {tickers}")
      return {f"Company {chr(65 + i)}": t for i, t in enumerate(sorted(tickers))}

  def sec_quantitative(rows: list[dict], companyfacts, decision_date: str) -> tuple[dict, dict, dict]:
      ...
      for label, t in labels.items():
          r = tech_criteria(companyfacts(int(by_ticker[t]["cik"])), decision_date)
          quant[label] = {k: r["values"][k] for k in TECH_CRITERIA}
          meta[label] = {k: r[k] for k in ("accn", "filed", "period_end")}
      return labels, quant, meta

  def load_sec(decision_date: str, path=UNIVERSE, client=None) -> tuple[dict, dict, dict]:
      from maid.sec import SecClient
      return sec_quantitative(read_universe(path), (client or SecClient()).companyfacts, decision_date)
  ```

- `src/maid/xbrl.py` already has `STAPLES_CRITERIA = ["revenue_growth", "net_margin", "fcf_margin", "roa"]` and
  `staples_criteria(facts, decision_date)` (same return shape as `tech_criteria`).
- `src/maid/graph.py`:
  - line 17: `DEFAULT_SETTINGS = {"source": "demo", "k": 5, "weighting": "critic", "seed": 0, "n_draws": 500, "concentration": 100.0}`
  - `validate_settings` (lines 21-37) rejects unknown keys and checks `source in ("demo", "sec")`.
  - `ingest` (lines 44-49): `if settings["source"] == "sec": tickers, quant, _ = load_sec(get_settings().decision_date); available, filings, criteria = list(tickers), {c: "" for c in tickers}, list(TECH_CRITERIA)`.
  - `report` (around line 162): heading `"# MAID report: real data (tech, quantitative only)"` and `"4 quantitative criteria, no LLM scores. Local only: do not commit."`.
  - `graph.py` imports `load_sec` by name (`from maid.real_data import load_sec`); tests monkeypatch `graph.load_sec`.
- `src/maid/demo.py` `main()`: argparse with `--source {demo,sec}`, `--weighting`, `--k`, `--seed`, `--n-draws`,
  `--concentration`; builds `given = {...}` and drops `None` values.
- `src/maid/backtest.py`: `WINDOW = ("2025-04-01", "2026-03-31")`, `WEIGHTINGS = ["critic", "entropy", "equal"]`,
  `rank_vs_return(scores, returns)`, `backtest(weighting, returns, n_draws=50)` which calls
  `run_demo({"source": "sec", "weighting": weighting, "n_draws": n_draws}, thread_id=f"backtest-{weighting}")`.
- `scripts/backtest.py`: gets tickers via `run_demo({"source": "sec", "n_draws": 1}, ...)`, computes
  `total_return(fetch_series(t, "2025-03-20", "2026-04-01", "Adj Close"), *WINDOW)` per ticker, exits 1 if any
  ticker fails, prints the CRITIC table and one stats line per weighting, then the hard-coded line
  `"n=15: |rho| > ~0.51 needed for two-sided p < 0.05. ..."`.
- `src/maid/prices.py`: `close_on(closes, date) -> (day, close)` returns the last close with `day <= date`, at most 7
  calendar days back, else `ValueError`. `total_return(adj, start, end) = close_on(adj, end)[1] / last close strictly before start - 1`.
- Tests: `tests/test_real_data.py` (patches `graph.load_sec` with `lambda d: sec_quantitative(ROWS, fake_facts, d)`;
  expects labels `"Company A": "AAPL"` etc. and `"Company A (AAPL)"` in the report), `tests/test_backtest.py`
  (patches `graph.load_sec` with `_fake(decision_date=None)`; has `test_graph_never_reads_prices`, which must keep
  passing).

Conventions (`CLAUDE.md`): short module docstrings, one-line function docstrings, compact code, do not reformat
existing code; tests use plain `assert`, no network. Conventional commits with `Refs plan 026` in the body.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Venv | `source /home/imad/maid/.venv/bin/activate` | — |
| Tests | `PYTHONPATH=<worktree>/src pytest -q` (inside the worktree) | all pass, 1 skipped |
| Lint | `ruff check .` | `All checks passed!` |
| Smoke run (no prices) | `cd /home/imad/maid && PYTHONPATH=<worktree>/src python -m maid.demo --source sec --sector staples --n-draws 20` | prints a report with 61 rows |

Real runs use `/home/imad/maid` as the working directory (SEC cache and `.env` are there; the universe CSV path is
relative, so also confirm `/home/imad/maid/data/universe/staples.csv` exists). Never print `.env`.

## Scope

**In scope:** `src/maid/real_data.py`, `src/maid/graph.py`, `src/maid/demo.py`, `src/maid/backtest.py`,
`scripts/backtest.py`, `tests/test_real_data.py`, `tests/test_backtest.py`, `docs/architecture/data.md`, `CLAUDE.md`
(layout lines for `real_data.py` and `scripts/backtest.py` only).

**Out of scope:** `src/maid/prices.py`, `src/maid/xbrl.py`, `src/maid/universe.py`, `scripts/select_universe.py`,
everything under `data/`, `app/` (the GUI stays on demo data), `src/maid/mcdm/`, `notes/`,
`docs/research/` (the reviewer writes the result note).

**Forbidden:** running `scripts/backtest.py` against the network, calling `fetch_series` / `total_return` for any
real ticker, or printing any price after 2025-03-31.

## Git workflow

- Worktree setup: `git reset --hard <BASE>` (given by the reviewer), check `test -f plans/026-staples-backtest.md`,
  then `git checkout -b feat/staples-backtest`.
- **Step 1 (pre-registration) is its own commit and must come first**: `docs(data): pre-register the staples backtest`.
- Then code commits, e.g. `feat(real-data): sector setting and numeric labels`. Do not push.

## Steps

### Step 1: Pre-register the test in `docs/architecture/data.md` (first commit)

Under the existing `## Backtest` section, after the "First result" bullet, add this subsection **verbatim**:

```markdown
### Backtest #2: consumer staples (pre-registered 2026-11-03, before any staples return was computed)

- Universe: the 61 companies in `data/universe/staples.csv` (plan 025, D19). No company is added or removed; the 19
  in `staples_excluded.csv` stay out.
- Inputs: `revenue_growth`, `net_margin`, `fcf_margin`, `roa` from the latest 10-K filed on or before 2025-03-31;
  quantitative only, no LLM.
- Ranking: CRITIC weights, then TOPSIS (graph defaults).
- Outcome: total return with dividends reinvested (Yahoo `Adj Close`) from the 2025-03-31 close to the 2026-03-31
  close. A company that stops trading inside the window gets its return up to its last close and 0% after that
  (cash earns nothing).
- **Primary test:** Kendall tau between TOPSIS score and total return, two-sided, alpha = 0.05.
- Secondary: Spearman rho. Sensitivity only: entropy and equal weights (not extra chances to find an effect).
- Power (seeded simulation, bivariate normal, n = 61, 2000 trials): about 12% for a true correlation of 0.1, 32%
  for 0.2, 60% for 0.3. A null result is likely even if a modest signal exists, and will be reported as such.
- The result is written up whatever it is, with summary statistics only (per-company returns stay local).
- Run: `python scripts/backtest.py --sector staples`.
```

**Verify**: `pytest -q tests/test_docs.py` passes; `git log -1 --stat` shows only `docs/architecture/data.md`.

### Step 2: Sector setting and numeric labels (`src/maid/real_data.py`)

1. Replace `UNIVERSE` with
   ```python
   SECTORS = {"tech": (Path("data/universe/tech.csv"), TECH_CRITERIA, tech_criteria),
              "staples": (Path("data/universe/staples.csv"), STAPLES_CRITERIA, staples_criteria)}
   ```
   Keep `UNIVERSE = SECTORS["tech"][0]` as an alias so `read_universe()` still defaults to tech.
2. `anonymize(tickers)`: labels `f"Company {i:03d}"` starting at `001`, in alphabetical ticker order; raise
   `ValueError` on duplicates or more than 999 tickers. Update the docstring ("Company 001", ...). One rule for every
   real-data sector, tech included (so tech labels change from "Company A" to "Company 001"; values and ranks don't).
3. `sec_quantitative(rows, companyfacts, decision_date, sector="tech")`: use the sector's criteria function and list.
4. `load_sec(decision_date, sector="tech", client=None)`: reads `SECTORS[sector][0]`. Unknown sector → `ValueError`.
5. Update the module docstring (no longer "tech only").

**Verify**: `python -c "from maid.real_data import anonymize; print(anonymize(['B','A']))"` → `{'Company 001': 'A', 'Company 002': 'B'}`.

### Step 3: Graph and CLI (`src/maid/graph.py`, `src/maid/demo.py`)

1. Add `"sector": "tech"` to `DEFAULT_SETTINGS`. In `validate_settings` reject a sector not in `("tech", "staples")`
   with `ValueError(f"unknown sector: ...")`. (Demo source ignores it.)
2. `ingest`: `tickers, quant, _ = load_sec(get_settings().decision_date, settings["sector"])` and
   `criteria = list(SECTORS[settings["sector"]][1])` (import `SECTORS` from `maid.real_data`). Remove the now-unused
   `TECH_CRITERIA` import only if ruff says it is unused.
3. `report`: heading `f"# MAID report: real data ({st['sector']}, quantitative only)"`; keep the rest.
4. `demo.py`: add `--sector {tech,staples}` and include it in `given`.

**Verify**: the smoke run from the commands table prints a report whose heading says `staples`, with a ranking table
of 61 rows (`grep -c "^| [0-9]" ` on the output gives 61 + the weights rows; just check the Rank column reaches 61)
and four weights `revenue_growth, net_margin, fcf_margin, roa` summing to 1. If any company fails with a
`ValueError` from `staples_criteria`, STOP.

### Step 4: Backtest (`src/maid/backtest.py`, `scripts/backtest.py`)

1. `backtest(weighting, returns, n_draws=50, sector="tech")`: pass `"sector": sector` into the `run_demo` settings
   and use `thread_id=f"backtest-{sector}-{weighting}"`.
2. Add a pure `window_return(adj_closes: dict[str, float], start: str, end: str) -> dict`:
   - base = `prices.close_on(adj_closes, <start minus 1 day>)` (last close strictly before `start`; `ValueError` if
     none within 7 days, as today);
   - if `prices.close_on(adj_closes, end)` succeeds → `{"return": c_end / base - 1, "last_day": day_end, "delisted": False}`;
   - else, if there are closes on or after `start`: use the latest one → `{"return": c_last / base - 1,
     "last_day": that day, "delisted": True}` (the 0% cash after it adds nothing);
   - else raise `ValueError` (no data in the window).
   For a series that ends normally, `window_return(...)["return"]` must equal `prices.total_return(...)` exactly.
3. `scripts/backtest.py`: add `--sector {tech,staples}` (default `tech`); pass it to `run_demo` (ticker list) and
   `backtest`; replace `total_return(...)` with `window_return(...)`; collect the delisted ones and print
   `delisted inside the window: TICKER (last close YYYY-MM-DD), ...` (or `none`). Replace the hard-coded `n=15` line
   with `f"n={n}. Only the CRITIC Kendall tau is the pre-registered primary test (data.md); entropy and equal are sensitivity."`.
   Keep the "exit 1 if any ticker has no price" behaviour: an **empty** series still means Yahoo trouble, not a delisting.
   Update the usage docstring.

**Verify**: `python scripts/backtest.py --help` lists `--sector`. Do NOT run it without `--help`.

### Step 5: Tests

`tests/test_real_data.py`:
- Update label expectations to `"Company 001"`, `"Company 002"`, ... and `"Company 001 (AAPL)"` in the report.
- Patched `load_sec` lambdas must accept the sector: `lambda d, sector="tech": sec_quantitative(ROWS, fake_facts, d, sector)`.
- `test_anonymize_numeric_many`: 30 tickers → labels `Company 001`..`Company 030`, alphabetical.
- `test_sec_quantitative_staples`: `fake_facts` plus an instant `Assets` row per company (copy the pattern from
  `tests/test_xbrl.py::_with_assets`: `{"end": "2024-12-31", "val": 4000, "accn": "A-2025", "form": "10-K",
  "filed": "2025-02-10"}`); `sec_quantitative(ROWS, facts_with_assets, "2025-03-31", "staples")` gives criteria keys
  `== set(STAPLES_CRITERIA)`.
- `test_graph_sec_staples`: patch `graph.load_sec` to return the staples result; `run_demo({"source": "sec",
  "sector": "staples", "n_draws": 20})` → `criteria == STAPLES_CRITERIA`, `"staples" in report`.
- `test_unknown_sector_rejected`: `validate_settings({"sector": "banks"})` raises matching `sector`.
- `test_read_staples_universe_real_file`: `read_universe(SECTORS["staples"][0])` has 61 rows, 61 distinct tickers,
  all `decision_date == "2025-03-31"`.

`tests/test_backtest.py`:
- `_fake` must accept `(decision_date=None, sector="tech")`.
- `test_window_return_normal`: series with closes on 2025-03-31 (100) and 2026-03-31 (120) → return 0.2,
  `delisted False`, equal to `total_return`.
- `test_window_return_delisted`: closes 2025-03-31 (100), 2025-12-10 (90), last 2025-12-12 (95) → 
  return -0.05, `last_day "2025-12-12"`, `delisted True`.
- `test_window_return_no_data_raises`: only a close before the window → `ValueError`.
- Keep `test_graph_never_reads_prices` passing unchanged.

**Verify**: `pytest -q` all pass; `ruff check .` clean.

### Step 6: Docs

- `docs/architecture/data.md` status line: "wired into the graph for tech and staples via `settings["source"] = "sec"`
  and `settings["sector"]`; labels "Company 001".. in ticker order".
- `CLAUDE.md` Layout: `src/maid/real_data.py: frozen universe (tech or staples) -> anonymized labels -> SEC criteria`;
  `scripts/backtest.py: run the backtest on a real universe (--sector tech|staples; prints only)`.

**Verify**: `pytest -q tests/test_docs.py` passes.

## Done criteria

- [ ] First commit on the branch touches only `docs/architecture/data.md` and contains the pre-registration text
- [ ] `pytest -q` passes; `ruff check .` clean
- [ ] Smoke run (`--source sec --sector staples`) ranks 61 companies with the four staples criteria
- [ ] `python -m maid.demo --source sec --n-draws 20` (tech) still ranks 15, top 5 by ticker unchanged from before
      your change (run it once at the start on `<BASE>` and save the output to compare: same tickers in the same
      order, labels differ)
- [ ] `git diff <BASE> --stat` lists only in-scope files
- [ ] No price after 2025-03-31 was fetched or printed (state this in the report)

## STOP conditions

- Any of the 61 staples companies fails in `staples_criteria` during the smoke run.
- The tech ranking order (by ticker) differs before/after.
- You think you need to run the real backtest or fetch prices to finish a step.

## Maintenance notes

- Labels are now numeric for every real-data run; anything that parses "Company A" for real data must change.
- The pre-registration text is a record: later changes to the method go in a new subsection, never edit it.
- The reviewer runs `python scripts/backtest.py --sector staples`, writes
  `docs/research/backtest-staples-results.md` (summary stats only) and updates the owner's local memo.
