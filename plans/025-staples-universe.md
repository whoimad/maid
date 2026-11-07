# Plan 025: Build and freeze the consumer-staples universe (no returns)

> **Executor instructions**: Follow this plan step by step. Run every verification command and confirm the expected
> result before moving to the next step. If anything in the "STOP conditions" section occurs, stop and report — do
> not improvise. When done, update the status row for this plan in `plans/README.md`, unless a reviewer dispatched
> you and told you they maintain the index.
>
> **Drift check (run first)**: `git diff --stat 5b3b5e7..HEAD -- src/maid/universe.py src/maid/xbrl.py src/maid/sec.py scripts/select_universe.py tests/test_universe.py tests/test_xbrl.py tests/test_sec.py docs/architecture/data.md docs/architecture/decisions.md`
> If any in-scope file changed since this plan was written, compare the "Current state" excerpts against the live
> code before proceeding; on a mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: L
- **Risk**: MED (changes `shares_outstanding` and the XBRL tag lists, which the frozen tech universe also uses;
  guarded by a before/after regression check)
- **Depends on**: plans 019–024 (DONE)
- **Category**: direction
- **Planned at**: commit `5b3b5e7` on branch `integration/prototype`, 2026-11-03

## Why this matters

MAID ranks companies with a deterministic MCDM engine. The first real backtest (15 tech companies) found nothing
(Kendall tau +0.05, p = 0.85), and with n = 15 it had almost no power. The owner chose **consumer staples** with a
larger universe: every staples company with a market cap of at least **$1bn** on the decision date **2025-03-31**
(about 55 companies). This plan builds and freezes that list. It must be built **by a rule only**, before any
returns are looked at, so the later backtest (plan 026) is pre-registered. **This plan never computes or prints a
return after 2025-03-31.** Two known data bugs must be fixed on the way: wrong or missing share counts
(Molson Coors gets 0 shares from a 2010 filing; Tyson and Constellation have no usable count in companyfacts), and
survivorship (today's SEC ticker list leaves out companies delisted after 2025-03-31, such as Kellanova).

## Owner decisions (fixed; do not change or re-ask)

1. Sector by SEC SIC code: food and beverages 2000–2099, tobacco 2100–2199, household and personal products
   2840–2844, grocery stores 5411. Accepted side effects: Walmart, Costco, Target, Dollar General (5331), Sysco (5140),
   Kimberly-Clark (2670) are out; Ecolab is in. No names are added or removed by hand.
2. Size floor: market cap ≥ $1bn on 2025-03-31 (shares × close). No fixed N, no pre-screen.
3. Fallback tags for everyone, appended **last** so the tech numbers cannot change: revenue gets
   `RevenueFromContractWithCustomerIncludingAssessedTax` last in `xbrl.REVENUE`; net income becomes
   `["NetIncomeLoss", "ProfitLoss"]`.
4. Staples criteria: `revenue_growth, net_margin, fcf_margin, roa`. `roa` = net income / total assets, where total
   assets is the **instant** us-gaap fact `Assets` with the same 10-K accession and `end` equal to the 10-K period
   end. (It replaces `rd_intensity`, which most staples don't report.)
5. Share count, one rule for everyone: skip a source whose latest value is zero, or whose latest filing was filed
   more than about 15 months (456 days) before the date, and try the next source. Add a fourth source: the
   cover-page `dei:EntityCommonStockSharesOutstanding` read from the 10-K's own XBRL instance document, summed over
   share classes.
6. Survivorship: candidates come from every company that reported us-gaap `Assets` for 2024 (SEC frames
   `CY2024Q1I..CY2024Q4I`), not from today's ticker list. A delisted company is included if Yahoo has a price for it;
   otherwise it is listed as **excluded, with the reason**. Guard against reused tickers.
7. Real downloaded data stays local. Only `data/universe/*.csv` is committed.

## Facts the advisor checked on 2026-11-03 (live, do not re-derive)

- Yahoo has **no** price history for the delisted staples tickers K (Kellanova), THS (TreeHouse), KLG (WK Kellogg),
  STKL (SunOpta), OLPX (Olaplex), while GIS returned 257 days in the same call (so it was not rate limiting). Under
  decision 6 they are expected in the excluded file with reason "no Yahoo price".
- The 10-K instance document exists for inline-XBRL filings at
  `https://www.sec.gov/Archives/edgar/data/<cik>/<accession without dashes>/<name>_htm.xml`. The filing index is JSON
  at `.../<accession without dashes>/index.json` with `directory.item[].name`. Example cover values:
  - Tyson (CIK 100493), accn `0000100493-24-000119`: `EntityCommonStockSharesOutstanding` 285855466 (context c-4) and
    70009005 (c-5); `TradingSymbol` TSN, `SecurityExchangeName` NYSE (both context c-1).
  - Constellation (CIK 16918), accn `0000016918-24-000054`: 182952680 and 23661; one symbol, STZ / NYSE.
  - Molson Coors (CIK 24545), accn `0000024545-25-000007`: 2563034 and 190157977; symbols TAP.A/NYSE (c-3),
    TAP/NYSE (c-4), "TAP 32"/NYSE (c-5, a note, not a stock). companyfacts only has dei shares of 0 from 2010.
- `dei:SecurityExchangeName` is an enumeration: `NYSE`, `NASDAQ`, `NYSEAMER`, `NYSEArca`, ... Only `NYSE` and
  `NASDAQ` count.

## Current state

Files (all read at `5b3b5e7`):

- `src/maid/universe.py` (78 lines, pure): `SECTORS`, `REVENUE_TAGS`, `EXCHANGES`, `N = 15`, `in_sector`, `listed`,
  `SHARE_SOURCES`, `shares_outstanding`, `eligible_annual`, `top_n`. Current share logic:

  ```python
  # src/maid/universe.py:47-62
  def shares_outstanding(facts: dict, date: str) -> tuple[float, str, str]:
      """Shares in the latest filing on or before date, its accession and the source tag."""
      for tax, tag in SHARE_SOURCES:
          rows = facts["facts"].get(tax, {}).get(tag, {}).get("units", {}).get("shares", [])
          rows = [r for r in rows if r["filed"] <= date]
          if not rows:
              continue
          filed = max(r["filed"] for r in rows)
          accn = max(r["accn"] for r in rows if r["filed"] == filed)
          rows = [r for r in rows if r["filed"] == filed and r["accn"] == accn]
          if tax == "dei":
              return float(sum(v for _, v in {(r["end"], r["val"]) for r in rows})), accn, tag
          last = max(r["end"] for r in rows)
          best = max((r for r in rows if r["end"] == last), key=_duration)
          return float(best["val"]), accn, tag
      raise ValueError(f"no shares outstanding filed on or before {date}: {facts.get('entityName')}")
  ```

- `src/maid/xbrl.py` (78 lines, pure): `REVENUE`, `TAGS`, `TECH_CRITERIA`, `_usd`, `_days`, `_annual`, `latest_10k`,
  `annual_value`, `prior_period_end`, `tech_criteria`. Excerpt:

  ```python
  # src/maid/xbrl.py:4-13
  REVENUE = ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"]
  TAGS = {
      "revenue": REVENUE,
      "net_income": ["NetIncomeLoss"],
      "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
      "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
      "rd": [...],
  }
  TECH_CRITERIA = ["revenue_growth", "net_margin", "fcf_margin", "rd_intensity"]

  # src/maid/xbrl.py:65-78
  def tech_criteria(facts, decision_date) -> dict:
      """Four tech criteria from the latest 10-K filed on or before decision_date."""
      accn, filed, end = latest_10k(facts, decision_date)
      got = {k: annual_value(facts, t, accn, end) for k, t in TAGS.items()}
      rt = [got["revenue"]["tag"]]
      prev = annual_value(facts, rt, accn, prior_period_end(facts, rt, accn, end))
      rev, rev0 = got["revenue"]["value"], prev["value"]
      if rev <= 0 or rev0 <= 0:
          raise ValueError(f"non-positive revenue in {accn}: {facts.get('entityName')}")
      v = {k: x["value"] for k, x in got.items()}
      return {"accn": accn, "filed": filed, "period_end": end,
              "values": {"revenue_growth": rev / rev0 - 1, "net_margin": v["net_income"] / rev,
                         "fcf_margin": (v["operating_cash_flow"] - v["capex"]) / rev, "rd_intensity": v["rd"] / rev},
              "tags": {k: x["tag"] for k, x in got.items()}}
  ```

- `src/maid/sec.py` (88 lines): `_get_json(url, user_agent)` (rate limited via `_slot()`, retries 429/5xx and network
  errors, raises `ValueError` containing `SEC_USER_AGENT` if the agent is blank), `cik10`, `SecClient` with
  `_cached(url)`, `companyfacts`, `submissions`, `frame`, `tickers`; `SecClient.__init__(cache=None, user_agent=None,
  fetch=_get_json)`. The fetcher is injectable so tests never touch the network (see `tests/test_sec.py:21-31`).
- `scripts/select_universe.py` (152 lines): the tech/banks pipeline. Starts from `listed(client.tickers())` (today's
  list), SIC from submissions cached in `DiskCache(cache_dir / "sic")` (key `DiskCache.key("sic", cik)`, value
  `{"sic", "name"}`), estimates caps from share **frames**, keeps the top `PRESCREEN = 40`, then
  `eligible_annual` + `shares_outstanding` + `market_price_on`, then `top_n` (15), writes
  `data/universe/<sector>.csv` (relative to the working directory) with `COLS`. Two silent drops that must **not**
  exist in the staples path: `PRESCREEN = 40` and `if cik not in shares: continue`.
- `src/maid/prices.py`: `market_price_on(ticker, date) -> {"date", "close_adj", "split_factor", "close"}`; raises
  `ValueError` when Yahoo returns no data and `PriceNetworkError` after repeated exceptions. Results are cached on disk.
- `src/maid/real_data.py` reads `data/universe/tech.csv` with `csv.DictReader` (columns `ticker`, `cik`,
  `decision_date`). Do **not** change it in this plan (plan 026 wires staples into the graph).
- Frozen lists that must not change: `data/universe/tech.csv` (AAPL, MSFT, NVDA, GOOGL, META, AVGO, ORCL, CRM, CSCO,
  IBM, PLTR, INTU, QCOM, AMD, NOW) and `data/universe/banks.csv` (JPM, BAC, WFC, C, PNC, COF, USB, BNY, TFC, MTB,
  FCNCA, FITB, STT, HBAN, RF).

Conventions (from `CLAUDE.md`): short module docstrings, one-line function docstrings, compact code, do not reformat
existing code. Tests in `tests/test_<area>.py` with plain `assert`, no network (see the `no_network` fixture in
`tests/test_sec.py:14-19`). Conventional commits with `Refs`/`Closes` in the body. Line length: follow ruff's config
in `pyproject.toml` (`ruff check .` must pass).

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Venv | `source /home/imad/maid/.venv/bin/activate` | prompt shows venv |
| Tests | `PYTHONPATH=<worktree>/src pytest -q` (run inside the worktree) | `N passed, 1 skipped`, N ≥ 115 |
| Lint | `ruff check .` (inside the worktree) | `All checks passed!` |
| Real runs | `cd /home/imad/maid && PYTHONPATH=<worktree>/src python <worktree>/scripts/...` | see steps |

Real runs must use `/home/imad/maid` as the working directory: the disk cache (`data/cache/`) and `.env` (with
`SEC_USER_AGENT`) live there. **Never print `.env` or the user agent.** Never write files into `/home/imad/maid`
other than the cache (that is why Step 5 adds `--out-dir`).

## Scope

**In scope:**
- `src/maid/xbrl.py`, `src/maid/universe.py`, `src/maid/sec.py`
- `scripts/select_universe.py`
- `tests/test_xbrl.py`, `tests/test_universe.py`, `tests/test_sec.py`, `tests/fixtures/sec/cover_two_classes.xml` (create)
- `data/universe/staples.csv`, `data/universe/staples_excluded.csv` (create, from the real run)
- `docs/architecture/data.md`, `docs/architecture/decisions.md` (add D19), `CLAUDE.md` (one layout line)
- `plans/README.md` (status row only)

**Out of scope (do not touch):**
- `data/universe/tech.csv`, `data/universe/banks.csv`: frozen; they must be byte-identical at the end.
- `src/maid/real_data.py`, `src/maid/graph.py`, `src/maid/backtest.py`, `scripts/backtest.py`: plan 026.
- `src/maid/prices.py`, `src/maid/cache.py`, `src/maid/mcdm/`.
- The tech/banks path of `scripts/select_universe.py` (PRESCREEN, today's-ticker candidates): leave it as is.
- `notes/` (local owner memo; the advisor updates it).
- Anything that prints or computes a return after 2025-03-31. Don't call `total_return` or fetch prices after
  2025-04-01.

## Git workflow

- Worktree setup: `git reset --hard 5b3b5e7` first (worktrees start from `main`, which lacks this plan), then
  `test -f plans/025-staples-universe.md` must succeed.
- Branch `feat/staples-universe`. Conventional commits, e.g. `feat(universe): cover-page share count fallback`,
  body `Refs plan 025`. One commit per step is fine.
- Do not push, do not open a PR, do not merge.

## Steps

### Step 0: Record the tech baseline (before any code change)

From `/home/imad/maid`, with `PYTHONPATH=<worktree>/src` at commit `5b3b5e7`:

```bash
python <worktree>/scripts/fetch_sec.py AAPL MSFT NVDA GOOGL META AVGO ORCL CRM CSCO IBM PLTR INTU QCOM AMD NOW > <scratch>/tech_before.txt
```

**Verify**: exit 0, 15 lines, no `ERROR`. (`<scratch>` = any directory outside both repos, e.g. `/tmp/claude-1000/plan025`.)

### Step 1: XBRL fallbacks and `staples_criteria` (`src/maid/xbrl.py`)

1. Append `"RevenueFromContractWithCustomerIncludingAssessedTax"` as the **last** element of `REVENUE`.
2. Change `TAGS["net_income"]` to `["NetIncomeLoss", "ProfitLoss"]`.
3. Add `STAPLES_CRITERIA = ["revenue_growth", "net_margin", "fcf_margin", "roa"]`.
4. Add `instant_value(facts, tags, accn, period_end) -> dict`: like `annual_value`, but matches facts **without**
   `"start"` (instant), same `accn`, `form == "10-K"`, `end == period_end`; conflicting values raise `ValueError`;
   no match raises `ValueError` naming the tags.
5. Refactor so tech and staples share one body, without changing tech output. Target shape:

   ```python
   def _criteria(facts, decision_date, keys) -> tuple[dict, dict]:
       """(header with accn/filed/period_end/tags, values) for the duration tags in keys, plus revenue growth."""
       accn, filed, end = latest_10k(facts, decision_date)
       got = {k: annual_value(facts, TAGS[k], accn, end) for k in keys}
       # ... prior-year revenue and non-positive revenue check exactly as in tech_criteria today ...
       v = {k: x["value"] for k, x in got.items()}
       vals = {"revenue_growth": rev / rev0 - 1, "net_margin": v["net_income"] / rev,
               "fcf_margin": (v["operating_cash_flow"] - v["capex"]) / rev}
       return {"accn": accn, "filed": filed, "period_end": end, "tags": {k: x["tag"] for k, x in got.items()}}, {**vals, "_v": v}
   ```

   (The exact helper signature is up to you; the requirement is: `tech_criteria` returns exactly the same dict as
   before, including its `tags` keys `revenue, net_income, operating_cash_flow, capex, rd` and `values` keys in
   `TECH_CRITERIA`.)
6. Add `staples_criteria(facts, decision_date) -> dict`: same return shape as `tech_criteria`; `values` keys are
   `STAPLES_CRITERIA`; `roa = net_income / assets` with `assets = instant_value(facts, ["Assets"], accn, end)`;
   `tags` has keys `revenue, net_income, operating_cash_flow, capex, assets`. Raise `ValueError` if assets ≤ 0.
   Staples never reads the R&D tags.

**Verify**: `pytest -q tests/test_xbrl.py` → all existing tests pass (they must not be edited in this step).

### Step 2: Cover-page parser (`src/maid/xbrl.py`) and fetcher (`src/maid/sec.py`)

1. In `xbrl.py` add `parse_cover(xml_text: str) -> dict` using `xml.etree.ElementTree.fromstring`. Walk all elements;
   an element counts if its namespace URI contains `xbrl.sec.gov/dei` and its local name (after `}`) is one of
   `EntityCommonStockSharesOutstanding`, `TradingSymbol`, `SecurityExchangeName`. Read `contextRef` and the stripped
   text. Return
   `{"shares": float | None, "symbols": [[symbol, exchange], ...]}` where `shares` is the sum over **distinct**
   `(contextRef, value)` pairs of `EntityCommonStockSharesOutstanding` (None if there are none), and `symbols` lists
   each `TradingSymbol` in document order paired with the `SecurityExchangeName` of the same `contextRef` (`""` if
   none).
2. In `sec.py` split `_get_json` into a byte fetcher plus JSON decode: add `_get_text(url, user_agent) -> str` that
   shares the same User-Agent guard, `_slot()` rate limit and retry loop (refactor into one private `_get_bytes`;
   `_get_json` keeps its name and behaviour). Add a `fetch_text=_get_text` parameter to `SecClient.__init__`
   (stored as `self.fetch_text`).
3. Add `SecClient.cover(cik, accn) -> dict`: cached via `self.cache.get_or_compute(DiskCache.key("sec-cover", cik, accn), ...)`.
   Inside: fetch `https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn.replace('-', '')}/index.json` with
   `self.fetch`, pick the names in `directory.item[].name` ending in `_htm.xml`; if there is not exactly one, raise
   `ValueError(f"no single inline XBRL instance in {accn}: {names}")`; fetch it with `self.fetch_text` and return
   `{"accn": accn, **parse_cover(text)}`.
4. Create `tests/fixtures/sec/cover_two_classes.xml`: a minimal hand-written instance with namespace
   `xmlns:dei="http://xbrl.sec.gov/dei/2024"`, root `<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance">`,
   containing: `TradingSymbol` TAP.A + `SecurityExchangeName` NYSE in context c-3; TAP + NYSE in c-4; "TAP 32" + NYSE
   in c-5; `EntityCommonStockSharesOutstanding` 2563034 (c-7) and 190157977 (c-8), with the c-8 element repeated
   once (duplicate must be counted once). (These are Molson Coors' public cover values.)

**Verify**: Step 2 tests (see Test plan) pass: `pytest -q tests/test_xbrl.py tests/test_sec.py`.

### Step 3: Universe rule (`src/maid/universe.py`)

1. `SECTORS["staples"] = [(2000, 2099), (2100, 2199), (2840, 2844), (5411, 5411)]`; `REVENUE_TAGS["staples"] = None`.
2. `MIN_CAP = {"staples": 1e9}`; `STALE_DAYS = 456`; `COVER_EXCHANGES = {"NYSE", "NASDAQ"}`;
   `COVER_SOURCE = "10-K cover (instance)"`.
3. `shares_outstanding(facts, date, cover=None)`: for each of the three existing sources, compute the candidate value
   exactly as today, then **skip** the source (continue to the next) if the value is 0 or if its `filed` is earlier
   than `date - STALE_DAYS` days. After the three sources, if `cover` is given and `cover["shares"]` is a positive
   number, return `(float(cover["shares"]), cover["accn"], COVER_SOURCE)`. Otherwise raise the same `ValueError` as
   today. The existing tests in `tests/test_universe.py` must pass unchanged.
4. `listed_on_cover(cover) -> bool`: True if any `symbols` exchange (upper-cased) is in `COVER_EXCHANGES`.
5. `pick_ticker(cik, cover, listed_today) -> str` (`listed_today` is the output of `listed(...)`):
   - if `cik in listed_today`: return `listed_today[cik][0]` (same as tech);
   - else take the first symbol whose exchange is in `COVER_EXCHANGES` and which contains no whitespace; none →
     `ValueError("no NYSE/Nasdaq symbol on 10-K cover")`; normalise `.` to `-` (Yahoo style, e.g. `TAP.A` → `TAP-A`);
     if that normalised symbol is in `listed_today` under another CIK → `ValueError(f"ticker {s} reused by CIK {other}")`;
     else return it.
6. `public_float(facts, date) -> float | None`: the `val` of the latest-filed `dei:EntityPublicFloat` USD fact with
   `filed <= date` (None if absent). Only used to show the size of excluded companies.
7. `above_floor(rows, min_cap) -> list[dict]`: rows with `market_cap >= min_cap`, sorted by market cap descending,
   ties by cik ascending (reuse `top_n(rows, len(rows))`).

**Verify**: `pytest -q tests/test_universe.py` → all pass (old + new).

### Step 4: Regression check on tech and banks (no `--write`)

From `/home/imad/maid` with `PYTHONPATH=<worktree>/src`:

```bash
python <worktree>/scripts/fetch_sec.py AAPL MSFT NVDA GOOGL META AVGO ORCL CRM CSCO IBM PLTR INTU QCOM AMD NOW > <scratch>/tech_after.txt
diff <scratch>/tech_before.txt <scratch>/tech_after.txt
python <worktree>/scripts/select_universe.py tech  2> <scratch>/tech_sel.err | tee <scratch>/tech_sel.txt
python <worktree>/scripts/select_universe.py banks 2> <scratch>/banks_sel.err | tee <scratch>/banks_sel.txt
```

**Verify**: `diff` prints nothing. The selection tables list the same 15 tickers in the same order as
`data/universe/tech.csv` and `data/universe/banks.csv` (compare the ticker column). If Yahoo rate-limits (errors
mentioning price lookups), wait 10 minutes and rerun; successes are cached.

### Step 5: Staples pipeline in `scripts/select_universe.py`

Add `--out-dir` (default `data/universe`) used by both paths when `--write` is given. Then, at the top of `main()`
after parsing: `if a.sector in MIN_CAP: return floor_main(a, client)`; leave the tech/banks code below unchanged.
Move the inline `scan` closure into a module-level helper `sic_info(client, sic_cache, cik) -> dict` and use it in
both paths (same cache key and value as today, so the existing cache is reused).

`floor_main(a, client) -> int`, in this order, printing progress and counts to stderr:

1. Candidates: union of `int(r["cik"])` over `client.frame("us-gaap", "Assets", "USD", p)["data"]` for
   `p in ("CY2024Q1I", "CY2024Q2I", "CY2024Q3I", "CY2024Q4I")`. Print the count.
2. SIC for every candidate with `sic_info` in a `ThreadPoolExecutor(WORKERS)`. If any lookup fails (other than the
   `SEC_USER_AGENT` error, which aborts), print the failed CIKs and **return 1** (rerun resumes from cache). Keep
   `in_sector(sic, a.sector)`.
3. For each sector CIK (sorted by cik), assign it to exactly one bucket:
   - **ineligible** (counted only): `latest_10k(facts, a.date)` raises (no 10-K by the date), or the cover is not
     listed (`listed_on_cover` False);
   - **excluded** (written with reason, see below): `staples_criteria` raises (reason `criteria: <message>`),
     `shares_outstanding(facts, a.date, cover)` raises (`shares: ...`), `pick_ticker` raises (`ticker: ...`),
     `market_price_on` raises `ValueError` **for a CIK not in today's ticker list** (`no Yahoo price: ...`), or
     `client.cover` raises `ValueError` (`cover: ...`);
   - **priced**: everything succeeded; row has the same fields as the tech rows (`cik, ticker, name, sic,
     market_cap, shares, accn, close, price_date, source`).

   The cover is fetched with `client.cover(cik, accn)` where `accn` is from `latest_10k`. A `ValueError` from
   `market_price_on` for a CIK that **is** in today's ticker list is treated as Yahoo trouble: print it and
   **return 1** (never silently drop a listed company). `PriceNetworkError` → return 1.
4. `sel = above_floor(priced, MIN_CAP[a.sector])`. Print a table like the tech path (rank, ticker, name, sic, cap in
   bn, accn, price date, source) and the counts: candidates, in sector, ineligible, excluded, priced, below floor,
   selected.
5. With `--write`: write `<out-dir>/staples.csv` with the existing `COLS` (rank 1..n by cap) and
   `<out-dir>/staples_excluded.csv` with columns
   `cik, name, sic, ticker, public_float_usd, reason, decision_date` (ticker empty if unknown, `public_float_usd`
   from `public_float(facts, a.date)` rounded to an int or empty), sorted by public float descending (empty last),
   then cik.

Do **not** compute any return. Do not change `COLS`.

**Verify**: `ruff check .` clean; `pytest -q` all pass; `python scripts/select_universe.py --help` lists `staples`
and `--out-dir`.

### Step 6: Real run and sanity checks

From `/home/imad/maid` (it may take 20–40 minutes the first time: thousands of cached-or-new submissions requests at
8/s; run it in the background or with a long timeout):

```bash
PYTHONPATH=<worktree>/src python <worktree>/scripts/select_universe.py staples --write --out-dir <worktree>/data/universe 2> <scratch>/staples.err | tee <scratch>/staples.txt
```

**Verify** (all must hold, otherwise STOP):
- exit 0; `<worktree>/data/universe/staples.csv` has between 45 and 70 data rows.
- Must be **in** `staples.csv` (by ticker): PG, KO, PM, PEP, MO, MDLZ, CL, KHC, GIS, HSY, TSN, STZ, TAP, MNST, EL, KR.
- Must **not** be in it: WMT, COST, UL, BTI, and no Publix (it is not exchange-listed).
- `staples_excluded.csv` lists Kellanova (CIK 55067) with a `no Yahoo price` reason (Yahoo has no K history).
- TAP's `shares` is about 192.7 million (cover source or a non-zero balance-sheet source), not 0; TSN's and STZ's
  shares are positive.
- `git -C <worktree> status --short data/universe` shows only the two new staples files.

### Step 7: Docs

- `docs/architecture/data.md`:
  - Status line: mention the staples universe.
  - Sector table: add the staples row with the four SIC ranges, and the accepted side effects (decision 1).
  - Universe section: a "Staples (floor rule)" subsection: candidates from 2024 Assets frames (survivorship), ≥ $1bn
    floor, exchange and ticker from the 10-K cover, the reused-ticker guard, the delisted rule (decision 6), the
    excluded file, and the share-count rule (decision 5, applies to all sectors).
  - Frozen universes table: add a staples row with the count and a pointer to `data/universe/staples.csv` (do not
    list 55 tickers inline) and to `staples_excluded.csv`.
  - New section "Quantitative criteria (staples)": the same table format as tech, rows `revenue_growth`,
    `net_margin`, `fcf_margin`, `roa` (`Assets`, instant, same accession and period end). Note the two new
    fallback tags and that they are appended last so tech values are unchanged.
- `docs/architecture/decisions.md`: add `## D19. Staples universe: SIC ranges, $1bn floor, survivorship-safe
  candidates, ROA` in the D17/D18 format (Alternatives / Why / Cost / Revisit if). Alternatives: energy, utilities,
  pharma (rejected in decision record: geopolitics, rate-driven, policy shocks), medical devices (backup), fixed N,
  gross margin and asset turnover instead of ROA (business-model driven). Cost: power only ~31% at rho 0.2 with
  n ≈ 55; delisted names without Yahoo history are excluded, so some survivorship remains.
- `CLAUDE.md` Layout: change the `scripts/select_universe.py` line to "select the tech/bank top 15 or the staples
  floor universe".

**Verify**: `pytest -q tests/test_docs.py` passes (relative links valid); `ruff check .` clean.

## Test plan

Offline only; follow the style of `tests/test_universe.py` (hand-written dicts) and `tests/test_xbrl.py`
(fixtures under `tests/fixtures/sec/`).

`tests/test_xbrl.py`:
- `test_revenue_including_tax_fallback`: deepcopy `F`, rename the `RevenueFromContractWithCustomerExcludingAssessedTax`
  key to `RevenueFromContractWithCustomerIncludingAssessedTax`; `tech_criteria(...)["tags"]["revenue"]` is the new tag
  and revenue growth is still `1000/800 - 1`.
- `test_profit_loss_fallback`: rename `NetIncomeLoss` to `ProfitLoss`; net margin still 0.2, tag `ProfitLoss`.
- `test_staples_criteria_roa`: deepcopy `F`, add `us-gaap.Assets.units.USD` rows: `{"end": "2024-12-31", "val": 4000,
  "accn": "A-2025", "form": "10-K", "filed": "2025-02-10"}` plus a decoy with `"start"` and a decoy from `A-2026`;
  `staples_criteria(f, "2025-03-31")["values"]` == `{revenue_growth: 0.25, net_margin: 0.2, fcf_margin: 0.25,
  roa: 0.05}` (use `pytest.approx`), and `"rd"` not in `tags`.
- `test_staples_criteria_missing_assets_raises` (match `"Assets"`).
- `test_tech_criteria_unchanged`: assert the full `tech_criteria(F, "2025-03-31")` dict equals a literal written
  from the current output (run it once on the base commit to get the literal).
- `test_parse_cover`: on `cover_two_classes.xml`: shares == 192721011.0; symbols ==
  `[["TAP.A", "NYSE"], ["TAP", "NYSE"], ["TAP 32", "NYSE"]]`. Plus a no-shares string → `shares is None`.

`tests/test_universe.py`:
- `in_sector("2086", "staples")`, `"2111"`, `"2844"`, `"5411"` True; `"5331"`, `"2670"`, `"5140"` False.
- `test_shares_skip_zero`: dei rows with value 0 + `CommonStockSharesOutstanding` 120 filed recently → 120 from
  the us-gaap tag.
- `test_shares_skip_stale`: dei filed `2023-01-10` (more than 456 days before `2025-03-31`) + us-gaap filed
  `2025-02-05` → us-gaap wins; and with only the stale source and no cover → `ValueError`.
- `test_shares_cover_fallback`: empty facts + `cover={"accn": "X", "shares": 355864471.0, "symbols": []}` →
  `(355864471.0, "X", COVER_SOURCE)`; cover with `shares=None` → `ValueError`.
- `test_pick_ticker`: listed today → first listed ticker; delisted with symbols
  `[["TAP 32", "NYSE"], ["K", "NYSE"]]` → `"K"`; `[["X.A", "NASDAQ"]]` → `"X-A"`; `[["K", "NYSE"]]` with `"K"` listed
  under another CIK → `ValueError` matching `reused`; `[["K", "NYSEAMER"]]` → `ValueError`.
- `test_listed_on_cover`, `test_public_float` (latest filed ≤ date wins; later filing ignored; absent → None),
  `test_above_floor` (boundary `== 1e9` kept, ordering by cap then cik).

`tests/test_sec.py`:
- `test_cover_cached`: `SecClient(cache=DiskCache(tmp_path), user_agent="t t@example.com", fetch=fake_json,
  fetch_text=fake_text)` where `fake_json` returns `{"directory": {"item": [{"name": "a_htm.xml"}, {"name":
  "a_cal.xml"}]}}` and `fake_text` returns the fixture text; two calls → one `fake_text` call; result has `accn` and
  the parsed shares; the index URL contains `/Archives/edgar/data/24545/000002454525000007/index.json`.
- `test_cover_needs_single_instance`: index without `_htm.xml` → `ValueError`.
- `test_get_text_user_agent_required` (blank agent → `ValueError` matching `SEC_USER_AGENT`).

Final: `pytest -q` → all pass (≥ 115 + new tests), 1 skipped; `ruff check .` clean.

## Done criteria

- [ ] `pytest -q` passes; `ruff check .` prints `All checks passed!`
- [ ] `diff tech_before.txt tech_after.txt` empty; tech and banks selections reproduce the frozen 15 tickers in order
- [ ] `git diff 5b3b5e7 -- data/universe/tech.csv data/universe/banks.csv` is empty
- [ ] `data/universe/staples.csv` (45–70 rows) and `data/universe/staples_excluded.csv` exist and pass Step 6 checks
- [ ] `grep -rn "total_return\|2026-03-31" scripts/select_universe.py src/maid/universe.py` prints nothing
- [ ] `docs/architecture/data.md` has the staples sector, universe and criteria sections; `decisions.md` has D19
- [ ] Report to the reviewer: the counts line from Step 6, the selected count, the excluded list (name + reason), and
      which companies use `COVER_SOURCE`

## STOP conditions

- Step 4: any tech value differs, or the tech/banks top 15 differs in members or order. Report the diff; do not
  "fix" the tag lists or the share rule to make it pass.
- Step 6: any must-in company is missing, any must-out company is present, or the row count is outside 45–70.
  Report the counts and the relevant stderr lines.
- More than 10 companies currently in today's ticker list fail the price lookup repeatedly over three reruns spaced
  10+ minutes apart.
- A SIC lookup fails for the same CIK on three reruns.
- Any 10-K instance index for a must-in company has zero or several `_htm.xml` files.
- You find yourself needing to compute or look at a return after 2025-03-31.

## Maintenance notes

- `shares_outstanding` now has a staleness rule used by every sector; a future re-freeze of tech or banks will use
  it too. Step 4 shows it does not change today's lists.
- `staples_excluded.csv` is part of the pre-registration record: plan 026 must not re-add excluded companies.
- Plan 026 will need `real_data.py` to read `staples.csv`, `staples_criteria`, and numeric labels (`Company 001`),
  because the staples universe has more than 26 companies.
- Reviewers: check that no code path silently `continue`s past a staples candidate without putting it in a bucket.
