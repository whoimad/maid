# Plan 020: Select and freeze the 15-company universes (tech, banks) and add a yfinance price layer

> **Executor instructions**: Follow this plan step by step. Run every verification command and confirm the expected
> result before moving to the next step. If anything in the "STOP conditions" section occurs, stop and report — do
> not improvise. When done, update the status row for this plan in `plans/README.md` — unless a reviewer dispatched
> you and told you they maintain the index.
>
> **Drift check (run first)**: `test -f src/maid/sec.py && test -f src/maid/xbrl.py && test -f docs/architecture/data.md && echo ok`
> → `ok` (plans 018 and 019 are done). Then `git diff --stat 66b0316 -- pyproject.toml` → only changes made by
> plans 018/019 (expected: none). Otherwise STOP.

## Status

- **Priority**: P1
- **Effort**: L
- **Risk**: MED (yfinance is an unofficial scraper; a one-time scan of a few thousand SEC requests)
- **Depends on**: plans/018-real-data-spec-and-decision-date.md, plans/019-sec-xbrl-quant-ingest.md
- **Category**: direction (new capability)
- **Planned at**: commit `66b0316` (branch `integration/prototype`), 2026-11-02

## Why this matters

MAID ranks a fixed set of companies per sector. The owner decided on **15 per sector**, for **tech** then **banks**.
They are chosen by a rule, not by hand: the 15 largest by market cap on the decision date (**2025-03-31**) within a
sector defined by SEC SIC codes. The list is computed once, frozen, and **committed** at
`data/universe/tech.csv` and `data/universe/banks.csv`. These are the only committed data files. Every download
stays local (owner rule).

The same price layer later feeds the backtest: total return over the evaluation window **2025-04-01 to 2026-03-31**.
That window is already in the past on the planning date, so the data exists.

## Current state

- `docs/architecture/data.md` (plan 018) has the spec. The rules this plan implements, restated:
  - Tech SIC: 3570–3579, 3661–3663, 3670–3679, 7370–7379. Banks SIC: 6021, 6022.
  - Eligibility: exchange NYSE or Nasdaq; a 10-K filed on or before the decision date that also reports the prior
    year (i.e. `maid.xbrl.latest_10k` succeeds and `maid.xbrl.prior_period_end` succeeds for revenue).
    For **banks** use these revenue tags instead of `xbrl.REVENUE`: `["Revenues", "InterestAndDividendIncomeOperating"]`.
  - Market cap = sum of `dei:EntityCommonStockSharesOutstanding` values in the latest filing (`max filed`, any
    form) filed on or before the decision date × split-corrected close on the decision date.
- `src/maid/sec.py` (plan 019): `SecClient(cache, user_agent, fetch)` with `.companyfacts(cik)`, `.submissions(cik)`,
  `.tickers()`, all cached on disk under `data/cache/sec/`; `ticker_to_cik(tickers_json, ticker)`; `cik10(cik)`.
  `_get_json` rate-limits to ≤ 8 requests/s and requires `SEC_USER_AGENT`.
- `src/maid/xbrl.py` (plan 019): pure functions `latest_10k(facts, date) -> (accn, filed, period_end)`,
  `annual_value(facts, tags, accn, period_end)`, `prior_period_end(facts, tags, accn, period_end)`,
  `tech_criteria(facts, date)`, constants `REVENUE`, `TAGS`. Check the live signatures; if they differ from these,
  STOP.
- `src/maid/cache.py`: `DiskCache(root).get_or_compute(key, fn)` caches JSON; `DiskCache.key(*parts)`.
- `pyproject.toml` optional extras today: `dev = ["pytest>=8", "ruff>=0.6"]`, `gui = ["streamlit>=1.39"]`.
  CI (`.github/workflows/ci.yml`) installs `.[dev,gui]` and runs `ruff check .` and `pytest -q`.
- Conventions: pure logic separate from I/O (exemplar: `src/maid/matrix.py`); tests offline, plain `assert`;
  one-line docstrings; scripts follow `scripts/weight_stability.py`.

### API shapes used

- `company_tickers_exchange.json`: `{"fields": ["cik","name","ticker","exchange"], "data": [[320193,"Apple Inc.","AAPL","Nasdaq"], ...]}`.
  One CIK can appear on several rows (share classes, e.g. GOOGL and GOOG). Exchange values include `"Nasdaq"`,
  `"NYSE"`, `"OTC"`, `"CBOE"` and others.
- `submissions` top level: `"sic"` (string, may be `""`), `"name"`, `"tickers"`.
- `frames` API: `https://data.sec.gov/api/xbrl/frames/dei/EntityCommonStockSharesOutstanding/shares/CY2025Q1I.json`
  → `{"data": [{"cik": 320193, "entityName": ..., "end": "...", "val": ..., "accn": ...}, ...]}`. Use it **only as a
  pre-screen**. Frames hold the latest-filed value per company, which is not point-in-time.
- yfinance: `yf.Ticker(t).history(start=..., end=..., auto_adjust=False)` returns a DataFrame indexed by date with
  `Close` (split-adjusted, **not** dividend-adjusted) and `Adj Close` (split- and dividend-adjusted).
  `yf.Ticker(t).splits` is a Series of split ratios indexed by date. `yf.download([...], start, end, auto_adjust=False,
  group_by="ticker")` fetches many tickers at once.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Setup | `pip install -e ".[dev,gui,data]"` (after Step 1) | exit 0 |
| Tests | `pytest -q` | all pass |
| Lint | `ruff check .` | `All checks passed!` |
| Selection (network, slow first time) | `python scripts/select_universe.py tech --write` | prints 15 rows, writes `data/universe/tech.csv` |

## Scope

**In scope:**
- `pyproject.toml`: add extra `data = ["yfinance>=0.2.40"]`.
- `src/maid/prices.py` (create), `src/maid/universe.py` (create), `src/maid/sec.py` (add one method `frame(...)`).
- `scripts/select_universe.py` (create).
- `data/universe/tech.csv`, `data/universe/banks.csv` (generated by the script, committed).
- `tests/test_prices.py`, `tests/test_universe.py` (create).
- `docs/architecture/data.md`: status line, and a "Frozen universes" subsection listing both tables' tickers.
- `CLAUDE.md`, `README.md` Layout lists: one line each for the new modules.

**Out of scope:**
- `graph.py`, the MCDM engine, `state.py`, `xbrl.py` (except STOP conditions).
- The backtest itself: ranking-vs-return correlation is a later plan. Only the `total_return` function is added here.
- Anonymization labels (ticker → "Company A"): a later plan.
- `.env`: never open or print it.

## Git workflow

- Branch: `feat/universe-prices` from `integration/prototype` after 019 is merged into it.
- Conventional commits, e.g. `feat(ingest): yfinance price layer`, `feat(ingest): freeze tech and bank universes`.
  The universe CSVs get their own commit, `data: freeze tech and bank universes at 2025-03-31`.
- Do NOT push or open a PR.

## Steps

### Step 1: Optional dependency

Add `data = ["yfinance>=0.2.40"]` under `[project.optional-dependencies]`. Do **not** add it to CI. `prices.py`
imports `yfinance` only inside its fetch functions, so tests and CI never need it.

**Verify**: `pip install -e ".[dev,gui,data]"` → exit 0; `python -c "import yfinance"` → no error.

### Step 2: `src/maid/prices.py`

Docstring: `"""Prices via yfinance (cached on disk, local only). Pure helpers work on {date: value} dicts."""`

Pure functions (no pandas, no yfinance):
- `def close_on(closes: dict[str, float], date: str) -> tuple[str, float]`: the last `(day, close)` with
  `day <= date`, looking back at most 7 calendar days (weekends, holidays). Raise `ValueError` if there is none.
- `def split_factor_after(splits: dict[str, float], date: str) -> float`: the product of ratios for split days
  strictly after `date` (1.0 if none). The unadjusted close on `date` = split-adjusted close × this factor.
- `def total_return(adj_closes: dict[str, float], start: str, end: str) -> float`: `close_on(adj, end) / close_before(adj, start) - 1`.
  `close_before` is the last adjusted close strictly before `start` (also ≤ 7 days back). Use `Adj Close` so
  dividends count.

Fetch functions (import yfinance inside; cache with `DiskCache(get_settings().cache_dir / "prices")`, key
`DiskCache.key("yf", ticker, field, start, end)`):
- `def fetch_series(ticker, start, end, field="Close") -> dict[str, float]`: `history(start, end, auto_adjust=False)[field]`,
  as `{"YYYY-MM-DD": float}`. Raise `ValueError` if empty.
- `def fetch_splits(ticker) -> dict[str, float]`: `{date: ratio}` from `.splits`. Cache it under a key that includes
  today's date: splits can be added later, and the result must be stable within one selection run.
- `def market_price_on(ticker, date) -> dict`: `{"date": day, "close_adj": c, "split_factor": f, "close": c * f}`,
  fetching the window `[date − 10 days, date + 1 day)`.

**Verify**: `python -c "import maid.prices"` works **without** yfinance installed. Check with
`python -c "import sys; sys.modules['yfinance']=None; import maid.prices; print('ok')"` → `ok`.

### Step 3: `tests/test_prices.py` (offline)

1. `close_on({"2025-03-28": 10.0, "2025-03-31": 11.0}, "2025-03-31") == ("2025-03-31", 11.0)`; with
   `"2025-04-01"` → same row; with `"2025-03-30"` (Sunday) → `("2025-03-28", 10.0)`.
2. `close_on({"2025-03-01": 1.0}, "2025-03-31")` raises `ValueError` (more than 7 days back).
3. `split_factor_after({"2024-06-10": 10.0, "2025-06-01": 2.0, "2026-01-05": 3.0}, "2025-03-31") == 6.0`.
4. `total_return({"2025-03-31": 100.0, "2026-03-31": 120.0}, "2025-04-01", "2026-03-31") == pytest.approx(0.2)`.

**Verify**: `pytest -q tests/test_prices.py` → 4 passed.

### Step 4: `SecClient.frame` in `src/maid/sec.py`

```python
    def frame(self, taxonomy: str, tag: str, unit: str, period: str) -> dict:
        return self._cached(f"https://data.sec.gov/api/xbrl/frames/{taxonomy}/{tag}/{unit}/{period}.json")
```
**Verify**: `pytest -q tests/test_sec.py` → all pass.

### Step 5: `src/maid/universe.py`, pure selection logic

Docstring: `"""Universe rule (docs/architecture/data.md): SIC sector, NYSE/Nasdaq, 10-K filer, top 15 by market cap."""`

```python
SECTORS = {
    "tech": [(3570, 3579), (3661, 3663), (3670, 3679), (7370, 7379)],
    "banks": [(6021, 6021), (6022, 6022)],
}
REVENUE_TAGS = {"tech": None, "banks": ["Revenues", "InterestAndDividendIncomeOperating"]}  # None -> xbrl.REVENUE
EXCHANGES = {"NYSE", "Nasdaq"}
N = 15
```
Functions:
- `def in_sector(sic: str, sector: str) -> bool`: `False` for `""` or non-numeric values.
- `def listed(tickers_json) -> dict[int, list[str]]`: CIK → tickers on NYSE/Nasdaq, in file order.
- `def shares_outstanding(facts, date) -> tuple[float, str]`: from `facts["facts"]["dei"]["EntityCommonStockSharesOutstanding"]["units"]["shares"]`,
  the facts with `filed <= date`. Take the max `filed`, then (tie-break) the max `accn`. Return
  `(sum of val over all facts with that accn and filed, accn)`. The sum covers share classes; if the same `end` and
  `val` appear twice, count it once. Raise `ValueError` if there are none.
- `def eligible_annual(facts, date, sector) -> bool`: `True` if `xbrl.latest_10k` and `xbrl.prior_period_end` both
  succeed with the sector's revenue tags. Catch `ValueError` → `False`. If `latest_10k` only works with
  `xbrl.REVENUE`, add an optional `tags` parameter to `latest_10k` in `xbrl.py` (defaulting to `REVENUE`) with a
  test. This is the only allowed `xbrl.py` change.
- `def top_n(rows: list[dict], n=N) -> list[dict]`: sort by `market_cap` descending, then `cik` ascending; return the
  first n.

### Step 6: `tests/test_universe.py` (offline, hand-written dicts)

1. `in_sector("3674", "tech")`, `in_sector("7372", "tech")`, `not in_sector("5961", "tech")`, `in_sector("6021", "banks")`,
   `not in_sector("6211", "banks")`, `not in_sector("", "tech")`.
2. `listed(...)` drops OTC rows and keeps both GOOGL and GOOG under one CIK.
3. `shares_outstanding`: two classes in one filing are summed; a later filing after the date is ignored; a duplicate
   fact is counted once.
4. `top_n` ordering and tie-break.

**Verify**: `pytest -q tests/test_universe.py` → all pass.

### Step 7: `scripts/select_universe.py`

`python scripts/select_universe.py {tech,banks} [--date D] [--write]`. Steps inside the script:
1. `tj = client.tickers()`; `cands = listed(tj)`.
2. SIC scan: for each CIK, get `sic` via
   `DiskCache(cache_dir / "sic").get_or_compute(DiskCache.key("sic", cik), lambda: {"sic": s["sic"], "name": s["name"]})`
   where `s = sec._get_json(f"https://data.sec.gov/submissions/CIK{cik10(cik)}.json", client.user_agent)`.
   Do **not** use `client.submissions` here: it would cache thousands of large submissions files. This way only the
   slim dict is cached. Print progress
   every 250 CIKs. Keep the CIKs that are `in_sector`.
3. Pre-screen: `client.frame("dei", "EntityCommonStockSharesOutstanding", "shares", "CY2025Q1I")` → shares per CIK
   (sum the rows per CIK). For CIKs missing from it, try `CY2024Q4I`. For in-sector CIKs, estimate cap = shares ×
   `market_price_on(first ticker, date)["close"]`. Price failures → skip that CIK with a printed warning. Keep the
   top 40 by estimate.
4. Exact: for the top 40, `facts = client.companyfacts(cik)`. Drop the CIK if `not eligible_annual(...)`. Otherwise
   `shares, accn = shares_outstanding(facts, date)`, `p = market_price_on(ticker, date)`, `cap = shares * p["close"]`.
5. `top_n(rows)`. Print a table: rank, ticker, name, SIC, cap in $bn, shares accn, price date.
6. With `--write`, write `data/universe/<sector>.csv` with columns
   `rank,ticker,cik,name,sic,market_cap_usd,shares,shares_accn,close,price_date,decision_date`, sorted by rank.

If the frames endpoint returns 404 or an error for `dei`, STOP and report. Do not fall back to downloading
companyfacts for every candidate without asking.

**Verify (network)**: `python scripts/select_universe.py tech` prints 15 rows. Sanity check: the list contains
AAPL, MSFT, NVDA, GOOGL or GOOG, META, AVGO (all huge, and in tech by SIC). It does **not** contain AMZN, TSLA, V or MA.
If any of the six is missing, STOP (the rule or code is wrong). Then `python scripts/select_universe.py banks` prints
15 rows and contains JPM, BAC, WFC, C (SIC 6021); it does not contain GS or MS.

If you have no network or yfinance can't reach Yahoo: skip Steps 7's verify and 8, report "selection not run:
<reason>", and finish the rest. The reviewer will run it.

### Step 8: Freeze

Run both with `--write`. Commit only `data/universe/tech.csv` and `data/universe/banks.csv`.

**Verify**:
- `git status --porcelain data/` (before commit) → exactly `?? data/universe/` or the two CSV paths; **no** `data/cache` paths.
- `python -c "import csv;print(sum(1 for _ in csv.DictReader(open('data/universe/tech.csv'))))"` → `15`; same for banks.

### Step 9: Docs

`docs/architecture/data.md`: add `### Frozen universes (selected <today's date>)` with two tables
(rank, ticker, name, SIC). Update the status line to mention `universe.py`, `prices.py` and
`scripts/select_universe.py`. Add the new modules to the `CLAUDE.md` and `README.md` Layout lists. Add
`pip install -e ".[data]"` and the two script commands to README under a new `## Real data (local only)` heading,
with a note that `SEC_USER_AGENT` must be set in `.env`.

**Verify**: `pytest -q && ruff check .` → all pass.

## Test plan

`tests/test_prices.py` (4) and `tests/test_universe.py` (≥ 4) use pure functions and hand-written dicts. Nothing
imports yfinance and nothing touches the network. The network steps are verified by the sanity lists in Step 7.

## Done criteria

- [ ] `pytest -q` and `ruff check .` pass on an install **without** the `data` extra (CI parity:
      `pip uninstall -y yfinance && pytest -q`).
- [ ] `data/universe/tech.csv` and `banks.csv` each have 15 rows (or the report explains why selection was not run).
- [ ] `git ls-files data/` lists only `data/universe/*.csv`.
- [ ] `git diff --name-only` vs the branch base lists only in-scope files.

## STOP conditions

- A live signature in `sec.py` or `xbrl.py` differs from "Current state".
- The `dei` frames endpoint fails (Step 7.3).
- Sanity check in Step 7 fails: a named giant is missing, or an excluded name appears.
- More than 25% of the top-40 candidates fail price lookup (yfinance is likely broken or rate-limited).
- Fewer than 15 companies are eligible in a sector.

## Maintenance notes

- The universe is frozen. Re-running the script later may give a different list (SIC changes, new filings, a
  different yfinance split history). Never overwrite the committed CSVs without a decision-log entry.
- Multi-class companies (Alphabet) use one class's price for all classes. That is a documented approximation.
- Next plans: anonymized labels and wiring `source="sec"` into `graph.py` `ingest()`; the backtest using
  `prices.total_return`; the bank criteria spike; 10-K text extraction for the LLM scorer.
