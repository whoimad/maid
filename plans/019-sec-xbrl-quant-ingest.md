# Plan 019: Fetch SEC XBRL facts (cached, local-only) and compute point-in-time tech criteria

> **Executor instructions**: Follow this plan step by step. Run every verification command and confirm the expected
> result before moving to the next step. If anything in the "STOP conditions" section occurs, stop and report — do
> not improvise. When done, update the status row for this plan in `plans/README.md` — unless a reviewer dispatched
> you and told you they maintain the index.
>
> **Drift check (run first)**: `git diff --stat 66b0316 -- src/maid/config.py src/maid/cache.py pyproject.toml tests/`
> must print nothing except the one-line `config.py` default change from plan 018. Also run
> `test -f docs/architecture/data.md && echo ok`, which must print `ok` (plan 018 must be done). Otherwise STOP.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED (external API shapes; the look-ahead rule must be exactly right)
- **Depends on**: plans/018-real-data-spec-and-decision-date.md
- **Category**: direction (new capability)
- **Planned at**: commit `66b0316` (branch `integration/prototype`), 2026-11-02

## Why this matters

MAID ranks companies with a deterministic MCDM engine on a decision matrix `X` (companies × criteria). Today the
quantitative columns come from a synthetic dataset (`src/maid/demo_data.py`). This plan adds real numbers from SEC
EDGAR's XBRL "companyfacts" API for the four tech criteria. The hard part is **look-ahead control**: the decision
date is 2025-03-31, and the code must use only facts that were *filed* on or before it, taken from the company's
latest 10-K filed by then. One fact filed later, such as a restatement, silently leaks the future into a backtest.
The code is split so that this rule is pure and fully tested offline. The network layer is thin.

The graph is NOT changed here. Wiring real data into `ingest()` is a later plan.

## Current state

- `docs/architecture/data.md` (from plan 018) is the spec. Its "Time rule" and "Quantitative criteria (tech)"
  sections are restated below so you do not need to interpret them.
- `src/maid/cache.py`: `DiskCache(root)`, with `DiskCache.key(*parts) -> str` (sha256 of JSON) and
  `get_or_compute(key, fn)`. It returns cached JSON from `root/<key>.json` or calls `fn()`, writes the result
  atomically and returns it. Values must be JSON-serializable.
- `src/maid/config.py` (excerpt; plan 018 changed only the date default):
  ```python
  @dataclass(frozen=True)
  class Settings:
      api_key: str = field(default_factory=lambda: os.getenv("DEEPSEEK_API_KEY", ""), repr=False)
      base_url: str = field(
          default_factory=lambda: os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
      )
      model: str = field(default_factory=lambda: os.getenv("DEEPSEEK_MODEL", "deepseek-flash"))
      decision_date: str = field(default_factory=lambda: os.getenv("DECISION_DATE", "2025-03-31"))
      cache_dir: Path = field(default_factory=lambda: Path(os.getenv("MAID_CACHE_DIR", "data/cache")))
  ```
- `.gitignore` (after 018) ignores `data/*` except `data/universe/`. The cache is local-only. **Owner rule: never
  commit downloaded data.** Test fixtures are small, hand-written and synthetic.
- Conventions (CLAUDE.md): short module docstrings, one-line function docstrings, compact code; tests in
  `tests/test_<area>.py` with plain `assert`; **no network access in tests**; never print API keys. Exemplar for
  style: `src/maid/matrix.py` (pure helpers, one-line docstrings, `ValueError` naming the missing cell).
- `pyproject.toml` dependencies: langgraph, openai, pydantic, python-dotenv, numpy, scipy. **Do not add an HTTP
  library**. Use the standard library `urllib.request`.

### SEC API shapes (what the code parses)

`https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json` (the CIK is zero-padded to 10 digits):
```json
{"cik": 320193, "entityName": "Apple Inc.",
 "facts": {
   "dei": {"EntityCommonStockSharesOutstanding": {"units": {"shares": [
       {"end": "2024-10-18", "val": 15115823000, "accn": "0000320193-24-000123", "fy": 2024, "fp": "FY",
        "form": "10-K", "filed": "2024-11-01"}]}}},
   "us-gaap": {"RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [
       {"start": "2023-10-01", "end": "2024-09-28", "val": 391035000000, "accn": "0000320193-24-000123",
        "fy": 2024, "fp": "FY", "form": "10-K", "filed": "2024-11-01", "frame": "CY2024"}]}}}}}
```
Duration facts have `start` and `end`; instant facts have only `end`. One 10-K (one `accn`) reports the current and
prior years, and also quarterly figures. The same fact appears again under later accessions, possibly with a
restated value.

`https://data.sec.gov/submissions/CIK0000320193.json` top-level fields used: `name`, `sic` (string, e.g. `"3571"`),
`fiscalYearEnd` (e.g. `"0928"`), `tickers` (list).

SEC fair-access rules: every request carries a `User-Agent` header with a contact (env `SEC_USER_AGENT`, added to
`.env.example` by plan 018), and makes at most 10 requests per second.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Setup | `python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev,gui]"` | exit 0 |
| Tests | `pytest -q` | all pass |
| Focused tests | `pytest -q tests/test_xbrl.py tests/test_sec.py` | all pass |
| Lint | `ruff check .` | `All checks passed!` |

## Scope

**In scope:**
- `src/maid/xbrl.py` (create): pure functions, no I/O.
- `src/maid/sec.py` (create): HTTP fetch, rate limit, cache.
- `src/maid/config.py`: add one field `sec_user_agent`.
- `scripts/fetch_sec.py` (create): CLI that prints criteria for tickers.
- `tests/test_xbrl.py`, `tests/test_sec.py`, `tests/fixtures/sec/*.json` (create).
- `docs/architecture/data.md`: change the status line only, and fix a tag list if Step 6 proves it wrong.
- `CLAUDE.md` and `README.md` "Layout" lists: add one line each for `xbrl.py`, `sec.py`.

**Out of scope:**
- `src/maid/graph.py`, `demo_data.py`, `state.py`, `src/maid/mcdm/`: real data is not wired in yet.
- 10-K text download and parsing (a later plan).
- Universe selection and yfinance (plan 020).
- Bank criteria (OPEN in data.md).
- `.env`: never open or print it.

## Git workflow

- Branch: `feat/sec-xbrl-ingest` from `integration/prototype` after plan 018 is merged into it.
- Conventional commits, e.g. `feat(ingest): point-in-time XBRL tech criteria`.
- Do NOT push or open a PR.

## Steps

### Step 1: `src/maid/xbrl.py`, the pure point-in-time logic

Module docstring: `"""Point-in-time XBRL extraction: only facts filed on or before the decision date (see docs/architecture/data.md)."""`

Constants:
```python
REVENUE = ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"]
TAGS = {
    "revenue": REVENUE,
    "operating_income": ["OperatingIncomeLoss"],
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
    "rd": ["ResearchAndDevelopmentExpense", "ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost"],
}
TECH_CRITERIA = ["revenue_growth", "operating_margin", "fcf_margin", "rd_intensity"]  # same names as demo_data.QUANT_CRITERIA
```

Functions (dates are ISO strings `YYYY-MM-DD`, so string comparison is date comparison; use `datetime.date.fromisoformat`
for day differences):

1. `def _usd(facts, tag) -> list[dict]`: returns `facts["facts"].get("us-gaap", {}).get(tag, {}).get("units", {}).get("USD", [])`.
2. `def _days(start, end) -> int`: the number of days from `start` to `end`.
3. `def latest_10k(facts, decision_date) -> tuple[str, str, str]`: returns `(accn, filed, period_end)` of the latest 10-K
   filed on or before `decision_date`.
   - Candidates: every fact in any `REVENUE` tag with `form == "10-K"` (exactly; `"10-K/A"` excluded),
     `filed <= decision_date`, and a `start` with `_days(start, end)` in `[350, 380]`.
   - Pick the max `filed`. Among facts with that `filed` and its `accn`, `period_end` = max `end`.
   - If there are no candidates, raise `ValueError(f"no 10-K revenue filed on or before {decision_date}: {facts.get('entityName')}")`.
4. `def annual_value(facts, tags, accn, period_end) -> dict`: the first tag (in order) with a fact where
   `accn` matches, `form == "10-K"`, `end == period_end`, and `start` present with `_days` in `[350, 380]`.
   Return `{"value": float(val), "tag": tag}`. If that tag has several matching facts with different `val`, raise
   `ValueError` naming the tag. Identical duplicates are fine. If no tag matches, raise
   `ValueError(f"no annual fact for {tags} in {accn} ending {period_end}")`.
5. `def prior_period_end(facts, tags, accn, period_end) -> str`: the `end` of a fact in the same `accn` (first tag in
   order with a match), annual duration, with `_days(end, period_end)` in `[350, 380]`. Raise `ValueError` if none.
6. `def tech_criteria(facts, decision_date) -> dict`: returns
   ```python
   {"accn": ..., "filed": ..., "period_end": ...,
    "values": {"revenue_growth": ..., "operating_margin": ..., "fcf_margin": ..., "rd_intensity": ...},
    "tags": {"revenue": "<tag used>", ...}}
   ```
   Formulas: growth = rev / rev_prev − 1; operating_margin = operating_income / rev; fcf_margin =
   (operating_cash_flow − capex) / rev; rd_intensity = rd / rev. Capex is reported as a positive payment, so subtract
   it. Round nothing. If `rev <= 0` or `rev_prev <= 0`, raise `ValueError`.

There is no network or file access in this module.

**Verify**: `python -c "import maid.xbrl as x; print(x.TECH_CRITERIA)"` → `['revenue_growth', 'operating_margin', 'fcf_margin', 'rd_intensity']`

### Step 2: Hand-written fixtures and `tests/test_xbrl.py`

Create `tests/fixtures/sec/companyfacts_example.json`, a **synthetic** company (`"entityName": "Example Corp"`,
`"cik": 1`). Round numbers. Fiscal year ends 2024-12-31. Include:
- 10-K `accn` `"A-2025"` filed `2025-02-10`: annual facts for FY2024 (`2024-01-01`→`2024-12-31`) and FY2023
  (`2023-01-01`→`2023-12-31`) for `RevenueFromContractWithCustomerExcludingAssessedTax` (1000, 800),
  `OperatingIncomeLoss` (200, …), `NetCashProvidedByUsedInOperatingActivities` (300, …),
  `PaymentsToAcquirePropertyPlantAndEquipment` (50, …), `ResearchAndDevelopmentExpense` (150, …). Also add one
  quarterly fact (`2024-10-01`→`2024-12-31`, val 280) in the same accn for revenue.
- 10-K `accn` `"A-2024"` filed `2024-02-12` for FY2023 and FY2022 (so an earlier decision date picks it).
- A **restatement**: the FY2024 revenue fact again with `val` 1100, `accn` `"A-2026"`, `form` `"10-K"`, `filed`
  `"2026-02-09"`, plus its own FY2025 annual revenue fact so it is a full later 10-K.
- A `"10-K/A"` revenue fact with `filed` `"2025-03-20"`, `accn` `"A-2025-amend"`, for FY2024 with val 999.

Create `tests/fixtures/sec/companyfacts_revenues_tag.json`: the same shape, but revenue only under `Revenues`
and R&D only under `ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost`.

Load fixtures in tests with `json.loads((Path(__file__).parent / "fixtures/sec/<name>.json").read_text())`.

Tests (plain `assert`, `pytest.raises` for errors; pattern: `tests/test_demo.py`):
1. `latest_10k(f, "2025-03-31")` → `("A-2025", "2025-02-10", "2024-12-31")`. The 10-K/A filed 2025-03-20 is ignored.
2. `latest_10k(f, "2024-12-31")` → accn `"A-2024"` (FY2025's 10-K isn't filed yet on that date).
3. Restatement excluded: `tech_criteria(f, "2025-03-31")["values"]["revenue_growth"] == pytest.approx(1000/800 - 1)`, not 1100.
4. Margins: operating 0.2, fcf (300−50)/1000 = 0.25, rd 0.15 (`pytest.approx`).
5. Quarterly facts ignored: the 280 value never changes a result (covered by 3–4; add an explicit
   `annual_value(...)["value"] == 1000`).
6. Tag fallback: on the `revenues_tag` fixture, `tags["revenue"] == "Revenues"` and
   `tags["rd"] == "ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost"`.
7. A missing tag raises: delete `OperatingIncomeLoss` from a copy of the fixture, and `pytest.raises(ValueError, match="OperatingIncomeLoss")`.
8. No 10-K before the date: `pytest.raises(ValueError)` for `latest_10k(f, "2020-01-01")`.

**Verify**: `pytest -q tests/test_xbrl.py` → 8 passed.

### Step 3: `sec_user_agent` setting

In `src/maid/config.py` add, after `cache_dir`:
```python
    sec_user_agent: str = field(default_factory=lambda: os.getenv("SEC_USER_AGENT", ""))
```
**Verify**: `pytest -q tests/test_config_cache.py` → all pass.

### Step 4: `src/maid/sec.py`, the thin network layer

Module docstring: `"""SEC EDGAR fetches: User-Agent required, <= 8 requests/s, every response cached on disk (local only)."""`

```python
import json, time, urllib.request
from maid.cache import DiskCache
from maid.config import get_settings

MIN_INTERVAL = 0.125  # seconds between network requests (SEC allows 10/s)
_last = [0.0]

def _get_json(url: str, user_agent: str) -> dict:
    """GET a JSON URL with the SEC User-Agent, rate-limited."""
    if not user_agent.strip():
        raise ValueError("SEC_USER_AGENT is not set (SEC requires a contact, e.g. 'MAID research you@example.com')")
    wait = MIN_INTERVAL - (time.monotonic() - _last[0])
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(url, headers={"User-Agent": user_agent, "Accept-Encoding": "identity"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    finally:
        _last[0] = time.monotonic()

def cik10(cik) -> str:
    """Zero-padded 10-digit CIK."""
    return f"{int(cik):010d}"

class SecClient:
    """Cached SEC JSON endpoints."""
    def __init__(self, cache: DiskCache | None = None, user_agent: str | None = None, fetch=_get_json):
        s = get_settings()
        self.cache = cache or DiskCache(s.cache_dir / "sec")
        self.user_agent = s.sec_user_agent if user_agent is None else user_agent
        self.fetch = fetch

    def _cached(self, url: str) -> dict:
        return self.cache.get_or_compute(DiskCache.key("sec", url), lambda: self.fetch(url, self.user_agent))

    def companyfacts(self, cik) -> dict:
        return self._cached(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10(cik)}.json")

    def submissions(self, cik) -> dict:
        return self._cached(f"https://data.sec.gov/submissions/CIK{cik10(cik)}.json")

    def tickers(self) -> dict:
        return self._cached("https://www.sec.gov/files/company_tickers_exchange.json")

def ticker_to_cik(tickers_json: dict, ticker: str) -> int:
    """CIK for a ticker from company_tickers_exchange.json ({"fields": [...], "data": [[cik, name, ticker, exchange], ...]})."""
```
Implement `ticker_to_cik` by finding the column indices in `fields` (`"cik"`, `"ticker"`), matching case-insensitively,
and raising `ValueError(f"unknown ticker: {ticker}")` if there is no match.

Never log or print the User-Agent value. It contains the owner's email.

The cache never expires, and that is intended: `companyfacts` only grows, and the `filed <= decision_date` filter
makes old and new copies give the same result. Write this as a one-line comment on `_cached`.

**Verify**: `python -c "from maid.sec import cik10; print(cik10(320193))"` → `0000320193`

### Step 5: `tests/test_sec.py` (no network)

1. `SecClient(cache=DiskCache(tmp_path), user_agent="t t@example.com", fetch=fake)`, where `fake` counts calls and
   returns `{"ok": 1}`. Call `companyfacts(320193)` twice → result `{"ok": 1}`, `fake` called once, and the URL
   passed contains `CIK0000320193`.
2. `_get_json("https://example.invalid", "  ")` raises `ValueError` matching `SEC_USER_AGENT`. The check happens before
   any network call.
3. `ticker_to_cik({"fields": ["cik","name","ticker","exchange"], "data": [[320193,"Apple Inc.","AAPL","Nasdaq"]]}, "aapl") == 320193`;
   an unknown ticker raises `ValueError`.
4. Guard: a test that monkeypatches `urllib.request.urlopen` to raise `AssertionError("network in tests")` and runs
   tests 1–3 logic. Simpler: put an autouse fixture in `tests/test_sec.py` that does this for the whole module.

**Verify**: `pytest -q tests/test_sec.py` → all pass; `pytest -q` → all pass.

### Step 6: `scripts/fetch_sec.py` and a real run (network)

Script (argparse): `python scripts/fetch_sec.py AAPL MSFT NVDA GOOGL [--date 2025-03-31]`. `--date` defaults to
`get_settings().decision_date`. For each ticker it resolves the CIK and calls `tech_criteria(client.companyfacts(cik), date)`,
then prints one line per ticker: ticker, `period_end`, `filed`, the four values to 3 decimals, and the tags used. If
a ticker raises `ValueError`, print `ticker: ERROR <message>` and continue. Exit code 1 if any ticker failed.
Style: follow `scripts/weight_stability.py` (module docstring, `main()`, `if __name__ == "__main__":`).

Real run. This needs network and `SEC_USER_AGENT` set in the environment. **Do not create or edit `.env`.** If you
have no network or no `SEC_USER_AGENT`, skip this step, write "Step 6 real run skipped: <reason>" in your report and
continue. The reviewer will run it.
```bash
python scripts/fetch_sec.py AAPL MSFT NVDA GOOGL META AVGO ORCL CRM CSCO ADBE AMD QCOM IBM TXN INTU
```
Expected: every line has a `period_end` before 2025-03-31 and a `filed` on or before 2025-03-31; MSFT `period_end`
`2024-06-30`; NVDA `period_end` in late January 2025; margins between −1 and 1; growth between −0.5 and 2.
If 1–3 tickers fail with "no annual fact", that is a real tag gap. Add the missing tag the company uses (find it in
the cached companyfacts JSON under `data/cache/sec/`) to the fallback list in `xbrl.py` **and** in `data.md`, then
add a fixture test for it. If more than 3 fail, STOP.

**Verify** (after a real run): `git status --porcelain data/` → no output (the cache is ignored).

### Step 7: Docs

- `docs/architecture/data.md`: change the status line to "Status: SEC quantitative extraction implemented
  (`xbrl.py`, `sec.py`, `scripts/fetch_sec.py`); not wired into the graph yet."
- `CLAUDE.md` and `README.md` Layout lists: add
  `- \`src/maid/xbrl.py\`: point-in-time XBRL extraction (pure)` and
  `- \`src/maid/sec.py\`: cached SEC EDGAR client`.

**Verify**: `pytest -q && ruff check .` → all pass.

## Test plan

There are 8 tests in `tests/test_xbrl.py` (Step 2) and 3–4 in `tests/test_sec.py` (Step 5). All are offline and use
hand-written fixtures. The look-ahead tests (2, 3, and the 10-K/A case in 1) are the most important ones. Do not
weaken them to make the code pass.

## Done criteria

- [ ] `pytest -q` passes; `tests/test_xbrl.py` has ≥ 8 tests, `tests/test_sec.py` ≥ 3.
- [ ] `ruff check .` → `All checks passed!`
- [ ] `grep -rn "urlopen\|requests\|httpx" tests/` shows only the monkeypatch guard.
- [ ] `grep -n "print" src/maid/sec.py` → no output.
- [ ] `git status --porcelain data/` → no output.
- [ ] `git diff --name-only` (vs the branch base) lists only in-scope files.
- [ ] The report states whether the Step 6 real run ran, and pastes its output if it did.

## STOP conditions

- The companyfacts JSON shape differs from the "SEC API shapes" section (e.g. no `filed` or `form` field).
- More than 3 of the 15 tickers in Step 6 fail.
- Some company has two different annual values for the same tag in the same accession (the error in Step 1.4 fires
  on real data). Report the company and tag; do not pick one.
- Satisfying a test would require changing `graph.py`, `state.py` or the MCDM engine.
- Any step would write real downloaded data outside `data/` or into `tests/`.

## Maintenance notes

- The next plan wires this into `graph.py` `ingest()` behind a `source` setting (`"demo"` | `"sec"`). Company labels
  must stay anonymized ("Company A") in state; keep the ticker → label map out of scoring prompts.
- A review should check the look-ahead logic in `latest_10k` and `annual_value` line by line against data.md.
- Bank criteria need different tags and are not handled here.
- yfinance is not used here (plan 020).
