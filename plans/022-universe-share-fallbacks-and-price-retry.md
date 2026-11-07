# Plan 022: Fix universe selection: share-count fallbacks for multi-class companies, price retries, loud failures

> **Executor instructions**: Follow this plan step by step. Run every verification command and confirm the expected
> result before moving to the next step. If anything in the "STOP conditions" section occurs, stop and report — do
> not improvise. When done, update the status row for this plan in `plans/README.md` — unless a reviewer dispatched
> you and told you they maintain the index.
>
> **Drift check (run first)**: `git diff --stat 328de0f -- src/maid/universe.py src/maid/prices.py src/maid/xbrl.py scripts/select_universe.py tests/`
> must print nothing.

## Status

- **Priority**: P1 (the frozen universe is wrong without it)
- **Effort**: S
- **Risk**: LOW
- **Depends on**: plans 020, 021 (DONE)
- **Category**: bug
- **Planned at**: commit `328de0f` (branch `integration/prototype`), 2026-11-02

## Why this matters

`scripts/select_universe.py tech` picks the 15 largest tech companies by market cap on 2025-03-31. A real run
returned a list **without NVIDIA, Alphabet and Meta**, three of the five largest US tech companies. That breaks the
plan-020 sanity check. Root causes, verified against the real cached SEC data:

1. **Multi-class companies have no `dei:EntityCommonStockSharesOutstanding` in companyfacts.** Alphabet (CIK 1652044)
   and Meta (CIK 1326801) report cover-page shares per share class (an XBRL dimension). The companyfacts API drops
   dimensional facts, so their `dei` block only has `EntityPublicFloat`. The SEC `frames` pre-screen misses them for
   the same reason, so they never reach the top 40, and `universe.shares_outstanding` would raise anyway. The data
   that *is* present:
   - Alphabet: `us-gaap:CommonStockSharesOutstanding`, end 2024-12-31, val 12,211,000,000 (all classes), 10-K filed
     2025-02-05.
   - Meta: no `CommonStockSharesOutstanding` either. It has `us-gaap:WeightedAverageNumberOfSharesOutstandingBasic`,
     2024-01-01→2024-12-31, val 2,534,000,000, 10-K filed 2025-01-30.
2. **Yahoo price lookups have no retry.** NVIDIA's pre-screen price failed with `curl: (6) Could not resolve host:
   query2.finance.yahoo.com`. The script printed a warning and silently dropped NVIDIA. "No data" for a delisted
   ticker is a legitimate skip. A *network* error must be retried and, if it persists, must abort the run.

Also: Adobe (CIK 796343) tags R&D as `ResearchAndDevelopmentExpenseSoftwareExcludingAcquiredInProcessCost`. Add it
to the R&D fallback list so `tech_criteria` works for Adobe.

## Current state

`src/maid/universe.py` (verbatim):
```python
def shares_outstanding(facts: dict, date: str) -> tuple[float, str]:
    """Sum of cover-page shares in the latest filing on or before date, and its accession."""
    try:
        rows = facts["facts"]["dei"]["EntityCommonStockSharesOutstanding"]["units"]["shares"]
    except KeyError:
        rows = []
    rows = [r for r in rows if r["filed"] <= date]
    if not rows:
        raise ValueError(f"no shares outstanding filed on or before {date}: {facts.get('entityName')}")
    filed = max(r["filed"] for r in rows)
    accn = max(r["accn"] for r in rows if r["filed"] == filed)
    uniq = {(r["end"], r["val"]) for r in rows if r["filed"] == filed and r["accn"] == accn}
    return float(sum(v for _, v in uniq)), accn
```

`scripts/select_universe.py`, pre-screen (verbatim):
```python
def frame_shares(client: SecClient, period: str) -> dict[int, float]:
    """Sum of cover-page shares per CIK from a dei frame."""
    out: dict[int, float] = {}
    for r in client.frame("dei", "EntityCommonStockSharesOutstanding", "shares", period)["data"]:
        out[int(r["cik"])] = out.get(int(r["cik"]), 0.0) + float(r["val"])
    return out
...
        shares = frame_shares(client, "CY2025Q1I")
        for cik, v in frame_shares(client, "CY2024Q4I").items():
            shares.setdefault(cik, v)
        est = []
        for cik in in_sec:
            if cik not in shares:
                continue
            try:
                est.append((shares[cik] * market_price_on(cands[cik][0], a.date)["close"], cik))
            except Exception as e:  # yfinance raises many types
                print(f"warning: no price for {cands[cik][0]}: {e}", file=sys.stderr)
```
`SecClient.frame(taxonomy, tag, unit, period)` exists. `frame_shares` hard-codes the `dei` taxonomy and tag.

`src/maid/prices.py` `fetch_series` (verbatim):
```python
def fetch_series(ticker: str, start: str, end: str, field: str = "Close") -> dict[str, float]:
    """Daily {date: value} for a field over [start, end), cached."""
    def go():
        import yfinance as yf
        h = yf.Ticker(ticker).history(start=start, end=end, auto_adjust=False)
        if h.empty:
            raise ValueError(f"no price data for {ticker} {start}..{end}")
        return {i.strftime("%Y-%m-%d"): float(v) for i, v in h[field].items()}
    return _cache().get_or_compute(DiskCache.key("yf", ticker, field, start, end), go)
```
Note: yfinance often does **not** raise on network errors. It logs the error and returns an empty frame, so a DNS
failure can look like "no data". `fetch_splits` has the same shape.

`src/maid/xbrl.py`:
`"rd": ["ResearchAndDevelopmentExpense", "ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost"],`

Conventions: one-line docstrings, compact code, offline tests with plain `assert` and hand-written dicts
(pattern: `tests/test_universe.py`).

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Setup | `python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev,gui,data]"` | exit 0 |
| Tests | `pytest -q` | all pass |
| Lint | `ruff check .` | `All checks passed!` |

## Scope

**In scope:** `src/maid/universe.py`, `src/maid/prices.py`, `src/maid/xbrl.py` (one list entry),
`scripts/select_universe.py`, `tests/test_universe.py`, `tests/test_prices.py`, `tests/test_xbrl.py` (optional, one
test), `docs/architecture/data.md` (Universe "Ranking" bullet and the R&D tag row).
**Out of scope:** `sec.py`, `graph.py`, the MCDM engine, `data/universe/*.csv` (do not create or commit them; the
reviewer runs the selection). No network in tests; do not run the script against the network.

## Git workflow

Branch `fix/universe-shares`. Commit `fix(ingest): share-count fallbacks for multi-class companies; price retries`,
ending with:
```
Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_019fo6ZZzo3v3VNbkgpdRYGM
```
Do not push.

## Steps

### Step 1: Share-count fallback chain in `universe.py`

Add:
```python
SHARE_SOURCES = [  # (taxonomy, tag), tried in order; the first with data filed on or before the date wins
    ("dei", "EntityCommonStockSharesOutstanding"),   # cover page; missing for multi-class filers in companyfacts
    ("us-gaap", "CommonStockSharesOutstanding"),     # balance sheet, all classes
    ("us-gaap", "WeightedAverageNumberOfSharesOutstandingBasic"),  # last resort: period average
]
```
Change `shares_outstanding(facts, date)` to return `(shares, accn, source_tag)`:
- For each source in order: `rows = facts["facts"].get(tax, {}).get(tag, {}).get("units", {}).get("shares", [])`,
  filtered to `filed <= date`. If empty, try the next source.
- Take the latest `filed`, tie-break by max `accn`. Keep the rows of that filing.
- For `dei`: sum the unique `(end, val)` as today (share classes).
- For the two us-gaap tags: keep the rows with the max `end`. If they still have several values (e.g. a quarter and
  a year-to-date period ending the same day), take the value of the row with the **longest duration** (`end − start`;
  instant facts have no `start`, so treat them as duration 0). Do **not** sum.
- Return `(float(value), accn, tag)`.
- If no source has data, raise the same `ValueError` as today.

Update the one caller in `scripts/select_universe.py` (`n_sh, accn = shares_outstanding(...)`) to unpack three values,
and add a `shares_source` column at the end of `COLS` and of each written CSV row.

### Step 2: Pre-screen covers multi-class companies

In `scripts/select_universe.py`, generalize `frame_shares(client, taxonomy, tag, period)` and build the pre-screen
share map from, in order, keeping the first value found per CIK (`setdefault`):
1. `("dei", "EntityCommonStockSharesOutstanding", "CY2025Q1I")`
2. `("dei", "EntityCommonStockSharesOutstanding", "CY2024Q4I")`
3. `("us-gaap", "CommonStockSharesOutstanding", "CY2024Q4I")`
4. `("us-gaap", "WeightedAverageNumberOfSharesOutstandingBasic", "CY2024")`

`CY2024` is an annual duration frame. Frames 3 and 4 hold one row per company (no class sum needed, but `frame_shares`
summing is harmless). If a frame request raises `urllib.error.HTTPError` with code 404, print a warning and skip that
frame. Any other error propagates.

After the pre-screen, print to stderr: `pre-screen: {len(in_sec)} in sector, {n_with_shares} with shares, {n_priced} priced`.

### Step 3: Price retries and loud network failures in `prices.py`

- Add `class PriceNetworkError(RuntimeError)` and `RETRIES = 3`.
- In `fetch_series` `go()`: try up to `RETRIES` times. On any exception from yfinance, or on an empty frame, wait
  `2 ** attempt` seconds and retry. After the last attempt:
  - If the last attempt raised an exception, raise `PriceNetworkError(f"{ticker}: {e}")`.
  - If the frame was empty every time, raise the existing `ValueError("no price data ...")`. This is the legitimate
    "no data" case.
- Do the same in `fetch_splits` (an empty splits Series is normal: return `{}` with no retry. Only exceptions are
  retried, then `PriceNetworkError`).
- Note: the cache stores only successful results, because `get_or_compute` does not cache exceptions. Keep it that way.

### Step 4: Script treats network failure as fatal

In `scripts/select_universe.py`, pre-screen and exact stage: catch `ValueError` (no data) → warning and skip, as
today. Catch `PriceNetworkError` → print `ERROR price lookup failed after retries: ...` and `return 1`. Remove the
broad `except Exception` clauses. Keep the existing `SEC_USER_AGENT` handling.

### Step 5: Adobe R&D tag

In `src/maid/xbrl.py`, append `"ResearchAndDevelopmentExpenseSoftwareExcludingAcquiredInProcessCost"` as the third
entry of `TAGS["rd"]`. Add the same tag to the R&D row in `docs/architecture/data.md`.

### Step 6: Docs

`docs/architecture/data.md`, Universe "Ranking" bullet: replace the shares source with "shares outstanding from the
latest filing filed on or before the decision date: cover page (`dei:EntityCommonStockSharesOutstanding`, summed over
classes), else `us-gaap:CommonStockSharesOutstanding`, else `us-gaap:WeightedAverageNumberOfSharesOutstandingBasic`
(multi-class filers such as Alphabet and Meta only appear through the fallbacks, because the SEC API omits per-class
cover facts). The source used is recorded in the CSV."

### Step 7: Tests (offline)

`tests/test_universe.py`:
1. `dei` present → `source == "EntityCommonStockSharesOutstanding"`, values summed (update the existing test for the
   3-tuple).
2. No `dei`, `us-gaap:CommonStockSharesOutstanding` with two rows in the latest filing (ends 2023-12-31: 100 and
   2024-12-31: 120) → `(120.0, accn, "CommonStockSharesOutstanding")`.
3. Only `WeightedAverageNumberOfSharesOutstandingBasic` with a quarter (2024-10-01→2024-12-31, 90) and a year
   (2024-01-01→2024-12-31, 95) in the same filing → `95.0` (longest duration).
4. A later-filed row (filed after the date) is ignored in every source.

`tests/test_prices.py`: monkeypatch a fake `yfinance` module into `sys.modules` (`types.SimpleNamespace(Ticker=...)`)
and monkeypatch `time.sleep` to a no-op. Point `MAID_CACHE_DIR` at `tmp_path` with `monkeypatch.setenv`.
5. `history` raises twice, then returns a one-row frame → success. Build the frame with
   `pandas.DataFrame({"Close": [1.0]}, index=pandas.to_datetime(["2025-03-31"]))`. If pandas isn't importable,
   `pytest.importorskip("pandas")`.
6. `history` always raises → `PriceNetworkError`.
7. `history` always returns an empty frame → `ValueError` matching `no price data`.

**Verify**: `pytest -q` → all pass; `ruff check .` → clean.

## Done criteria

- [ ] `pytest -q` and `ruff check .` pass, with ≥ 7 new or updated tests.
- [ ] `grep -n "except Exception" scripts/select_universe.py` → no output.
- [ ] `git diff --name-only 328de0f` lists only in-scope files.
- [ ] No `data/` files are added.

## STOP conditions

- The excerpts don't match the live files.
- A test needs the real network.
- You'd need to change `sec.py` or `cache.py`.

## Maintenance notes

- Weighted-average basic shares differ from point-in-time shares outstanding by buybacks and issuance over the year
  (a few percent for Meta). That's acceptable for picking the top 15, and the CSV records which source was used.
- If a multi-class company's ranking is borderline (near position 15), check its cap by hand and record the result
  in D17.
