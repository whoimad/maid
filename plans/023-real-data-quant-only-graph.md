# Plan 023: The graph runs on real SEC data (tech, quantitative only, no LLM) with `source="sec"`

> **Executor instructions**: Follow this plan step by step. Run every verification command and confirm the expected
> result before moving to the next step. If anything in the "STOP conditions" section occurs, stop and report — do
> not improvise. When done, update the status row for this plan in `plans/README.md`, unless a reviewer dispatched
> you and told you they maintain the index.
>
> **Drift check (run first)**: `git diff --stat 1bb3b67..HEAD -- src/maid/graph.py src/maid/demo.py src/maid/state.py src/maid/xbrl.py src/maid/sec.py tests/test_demo.py docs/architecture/graph.md docs/architecture/data.md docs/architecture/overview.md CLAUDE.md`
> If any in-scope file changed since this plan was written, compare the "Current state" excerpts against the live
> code before proceeding; on a mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: LOW (new code path behind a setting; the default `source="demo"` must behave exactly as today)
- **Depends on**: plans 019–022 (all DONE), D18 (net margin, commit `42c3383`)
- **Category**: direction
- **Planned at**: commit `1bb3b67` on branch `integration/prototype`, 2026-11-02

## Why this matters

MAID (Multi-Agent Investment Decision-making) ranks companies with a deterministic MCDM engine (Multi-Criteria
Decision Making: entropy/CRITIC weights, TOPSIS/SAW ranking). Today the LangGraph pipeline only runs on a synthetic demo
dataset. The SEC/XBRL extraction (`src/maid/xbrl.py`, `src/maid/sec.py`) and the frozen 15-company tech universe
(`data/universe/tech.csv`) exist but are not connected to the graph. This plan adds `settings["source"] = "sec"`:
ingest reads the frozen universe, gets the four point-in-time quantitative criteria for each company from SEC XBRL,
anonymizes tickers to "Company A".."Company O", and the graph runs with **quantitative criteria only and no LLM**.
That gives the first real ranking, and it is also the "quant-only" ablation baseline from `docs/SCOPE.md` §6, which
later LLM runs are compared against.

## Current state

Files and roles:
- `src/maid/graph.py`: LangGraph pipeline. Nodes `ingest -> score_qualitative -> human_review -> mcdm -> robustness -> report`.
- `src/maid/demo.py`: CLI runner `python -m maid.demo`; `run_demo(settings, overrides)` runs the graph and auto-resumes the review interrupt.
- `src/maid/xbrl.py`: pure point-in-time extraction. `tech_criteria(facts, decision_date)` returns
  `{"accn", "filed", "period_end", "values": {criterion: float}, "tags": {...}}`. `TECH_CRITERIA = ["revenue_growth", "net_margin", "fcf_margin", "rd_intensity"]`.
- `src/maid/sec.py`: `SecClient()` with `.companyfacts(cik) -> dict`, cached on disk under `data/cache/sec` (cache hits need no network and no User-Agent).
- `src/maid/config.py`: `get_settings().decision_date` (default `"2025-03-31"`, from env `DECISION_DATE`).
- `data/universe/tech.csv`: committed. Header:
  `rank,ticker,cik,name,sic,market_cap_usd,shares,shares_accn,close,price_date,decision_date,shares_source`
  (15 rows; `name` may contain commas inside quotes, so read it with `csv.DictReader`, never `split(",")`).
- `src/maid/demo_data.py`: `QUANT_CRITERIA` has the **same names** as `xbrl.TECH_CRITERIA`; `QUAL_CRITERIA = ["strategy_clarity", "risk_disclosure"]`.

`src/maid/graph.py:14-15` and `:37-55` (today):

```python
DEFAULT_SETTINGS = {"k": 5, "weighting": "critic", "seed": 0, "n_draws": 500, "concentration": 100.0}
WEIGHT_FNS = {"entropy": entropy_weights, "critic": critic_weights, "equal": equal_weights}
...
def ingest(state: PipelineState) -> dict:
    """Load the synthetic demo dataset (real SEC/yfinance ingest is planned)."""
    settings = _settings(state)
    ds = demo_dataset(seed=settings["seed"])
    companies = state.get("companies") or ds.companies
    unknown = [c for c in companies if c not in ds.companies]
    if unknown:
        raise ValueError(f"unknown companies: {unknown}")
    if len(set(companies)) != len(companies):
        raise ValueError(f"duplicate companies: {companies}")
    return {
        "companies": list(companies),
        "quantitative": {c: ds.quantitative[c] for c in companies},
        "filings": {c: ds.filings[c] for c in companies},
        "criteria": QUANT_CRITERIA + QUAL_CRITERIA,
        "settings": settings,
    }
```

`score_qualitative` (graph.py:58-73) builds a `StubScorer` from the demo dataset and loops over `QUAL_CRITERIA`.
`human_review` (graph.py:92-95) always calls `interrupt(...)`. `report` (graph.py:131-160) starts with
`"# MAID demo report"` and the line `"> **Synthetic demo data**: invented companies, not real ones. Decision date 2025-03-31."`
and ends with `"LLMs never rank: scores come from the (stub) scorer, ranks from the MCDM engine."`.

`robust_ranking(..., cell_samples={})` (empty dict, as `score_cells` returns when there are no LLM scores) still
returns a `"score_noise"` entry with zero-width intervals. This was checked on the real cached data: it works, and
`report` can keep reading `rb["score_noise"]`.

Advisor's scratch run on the real cached data (2026-11-02, labels sorted by ticker, CRITIC weights) gave
weights about `[0.17, 0.22, 0.19, 0.42]` and TOPSIS top 5 `NVDA, META, AVGO, NOW, QCOM`. Use it as a sanity reference
in Step 6, not as a test.

Conventions (from `CLAUDE.md`): short module docstrings, one-line function docstrings, compact code, do not reformat
existing code. Tests in `tests/test_<area>.py`, plain `assert`, **no network in tests**. Rules: LLMs never rank;
company names anonymized as "Company A", ...; downloaded or derived real data stays local (only `data/universe/*.csv`
is committed).

Exemplar test with a fixture and an offline guard: `tests/test_sec.py:1-30` (the `no_network` autouse fixture that
monkeypatches `urllib.request.urlopen`). Copy that fixture into the new test file.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Activate | `source .venv/bin/activate` | — |
| Tests | `pytest -q` | all pass (baseline at `1bb3b67`: `100 passed, 1 skipped`) |
| One file | `pytest -q tests/test_real_data.py` | all pass |
| Lint | `ruff check .` | `All checks passed!` |
| Demo still works | `python -m maid.demo \| head -3` | first line `# MAID demo report` |

## Scope

**In scope** (the only files you may modify or create):
- `src/maid/real_data.py` (create)
- `src/maid/graph.py`
- `src/maid/state.py` (one new state key)
- `src/maid/demo.py` (one new CLI flag)
- `tests/test_real_data.py` (create)
- `docs/architecture/graph.md`, `docs/architecture/data.md`, `docs/architecture/overview.md`, `CLAUDE.md` (status lines only)
- `plans/README.md` (status row)

**Out of scope** (do NOT touch):
- `src/maid/xbrl.py`, `src/maid/sec.py`, `src/maid/universe.py`, `src/maid/prices.py`: already reviewed; use them as they are.
- `src/maid/mcdm/`: the engine is pure and finished for this purpose.
- `app/streamlit_app.py`, `src/maid/gui_data.py`: the GUI stays on demo data (a later plan).
- `data/universe/*.csv`: frozen; never rewrite them.
- Banks: the bank criteria are OPEN (no spike yet). `source="sec"` means the tech universe only.
- Prices and backtest: a separate later plan.
- Never commit anything under `data/` and never commit a real-data report or JSON.

## Git workflow

- Branch: `feat/real-data-graph` from `integration/prototype` at `1bb3b67` or later.
- Conventional commits, e.g. `feat(graph): source="sec" runs on the frozen tech universe, quant only`. Body: `Refs` the plan.
- Do NOT push, do NOT open a PR.

## Steps

### Step 1: Create `src/maid/real_data.py`

Contents (match this shape; keep it compact):

```python
"""Real-data inputs for the graph: frozen universe -> anonymized labels -> point-in-time SEC criteria (tech only)."""
import csv
from pathlib import Path

from maid.xbrl import TECH_CRITERIA, tech_criteria

UNIVERSE = Path("data/universe/tech.csv")


def read_universe(path=UNIVERSE) -> list[dict]:
    """Rows of a frozen universe CSV."""
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def anonymize(tickers: list[str]) -> dict[str, str]:
    """Label -> ticker; labels "Company A", "Company B", ... in alphabetical ticker order (no size information)."""
    if len(set(tickers)) != len(tickers) or len(tickers) > 26:
        raise ValueError(f"need up to 26 distinct tickers: {tickers}")
    return {f"Company {chr(65 + i)}": t for i, t in enumerate(sorted(tickers))}


def sec_quantitative(rows: list[dict], companyfacts, decision_date: str) -> tuple[dict, dict, dict]:
    """(label -> ticker, label -> criterion -> value, label -> {accn, filed, period_end}); companyfacts(cik) -> facts."""
    if bad := [r["ticker"] for r in rows if r["decision_date"] != decision_date]:
        raise ValueError(f"universe frozen for another decision date than {decision_date}: {bad}")
    labels = anonymize([r["ticker"] for r in rows])
    by_ticker = {r["ticker"]: r for r in rows}
    quant, meta = {}, {}
    for label, t in labels.items():
        r = tech_criteria(companyfacts(int(by_ticker[t]["cik"])), decision_date)
        quant[label] = {k: r["values"][k] for k in TECH_CRITERIA}
        meta[label] = {k: r[k] for k in ("accn", "filed", "period_end")}
    return labels, quant, meta


def load_sec(decision_date: str, path=UNIVERSE, client=None) -> tuple[dict, dict, dict]:
    """sec_quantitative on the frozen tech universe with the cached SEC client."""
    from maid.sec import SecClient

    return sec_quantitative(read_universe(path), (client or SecClient()).companyfacts, decision_date)
```

Why each rule: the decision-date check stops a universe frozen for one date being used with another (look-ahead
guard). Sorting by ticker before labelling means "Company A" does not mean "largest company". `tech_criteria` raises
`ValueError` on any missing tag; let it propagate, never fill in zeros (`docs/architecture/data.md`: "It never fills
in zero").

**Verify**: `python -c "from maid.real_data import anonymize; print(anonymize(['MSFT','AAPL']))"` →
`{'Company A': 'AAPL', 'Company B': 'MSFT'}`

### Step 2: Add the `source` setting and the `tickers` state key

In `src/maid/graph.py`:
- `DEFAULT_SETTINGS` gets `"source": "demo"` (add it as the first key).
- In `validate_settings`, after the `weighting` check, add:
  `if merged["source"] not in ("demo", "sec"): raise ValueError(f"unknown source: {merged['source']!r}")`.

In `src/maid/state.py`, add to `PipelineState` (after `filings`):
`tickers: dict[str, str]  # label -> ticker for source="sec"; local only, never put into prompts`
and change the `settings` comment to list `"source"` too.

**Verify**: `pytest -q` → still `100 passed, 1 skipped` (nothing else changed yet).

### Step 3: `ingest` branches on the source

Rewrite `ingest` in `src/maid/graph.py` so the demo branch behaves exactly as today and the sec branch uses
`load_sec`. Import at the top: `from maid.config import get_settings` and `from maid.real_data import load_sec`, and
`from maid.xbrl import TECH_CRITERIA`. Target shape:

```python
def ingest(state: PipelineState) -> dict:
    """Load inputs: the synthetic demo dataset, or (source="sec") the frozen tech universe from SEC XBRL, quant only."""
    settings = _settings(state)
    if settings["source"] == "sec":
        tickers, quant, _ = load_sec(get_settings().decision_date)
        available, filings, criteria = list(tickers), {c: "" for c in tickers}, list(TECH_CRITERIA)
    else:
        ds = demo_dataset(seed=settings["seed"])
        tickers, quant, filings = {}, ds.quantitative, ds.filings
        available, criteria = ds.companies, QUANT_CRITERIA + QUAL_CRITERIA
    companies = state.get("companies") or available
    unknown = [c for c in companies if c not in available]
    if unknown:
        raise ValueError(f"unknown companies: {unknown}")
    if len(set(companies)) != len(companies):
        raise ValueError(f"duplicate companies: {companies}")
    return {
        "companies": list(companies),
        "quantitative": {c: quant[c] for c in companies},
        "filings": {c: filings[c] for c in companies},
        "tickers": {c: tickers[c] for c in companies if c in tickers},
        "criteria": criteria,
        "settings": settings,
    }
```

Call `load_sec` through the module-level name `load_sec` (imported into `graph.py`) so tests can monkeypatch
`maid.graph.load_sec`.

**Verify**: `pytest -q` → `100 passed, 1 skipped`.

### Step 4: No LLM scores and no review pause when there is nothing to score

- `score_qualitative`: at the top, after `settings = _settings(state)`, add
  `if settings["source"] == "sec": return {"qualitative": [], "score_samples": {}, "score_noise": {}}`
  with a one-line comment: `# quant-only baseline (SCOPE section 6): no LLM scorer on real data yet`.
- `human_review`: if `state.get("qualitative")` is empty, return `{"overrides": []}` **without** calling `interrupt`
  (there is nothing for the human to review). Keep the existing comment line.

The `mcdm` and `robustness` nodes need no change: `build_matrix` takes only the criteria listed in `state["criteria"]`,
and `robust_ranking` with `cell_samples={}` gives zero-width score-noise intervals.

**Verify**: `pytest -q` → `100 passed, 1 skipped`.

### Step 5: Report says which data it ran on

In `report` (`src/maid/graph.py`):
- If `st["source"] == "sec"`: title `"# MAID report: real data (tech, quantitative only)"`, then the line
  `"> **Real data**: SEC XBRL, point-in-time on the decision date {get_settings().decision_date}; 4 quantitative criteria, no LLM scores. Local only: do not commit."`.
  Otherwise keep today's two lines unchanged (the demo test asserts `"Synthetic demo data"`).
- Add `source=...` as the first item of the `Settings:` line.
- In the ranking table, when `state.get("tickers")` is non-empty, write the company cell as `f"{c} ({tickers[c]})"`.
  The report is for the human; tickers stay out of prompts only.
- Replace the last line with: demo → unchanged; sec → `"LLMs never rank: this run has no LLM scores; ranks come from the MCDM engine."`
- After the score-noise sentence, when source is sec, add: `"No LLM scores in this run, so score-noise intervals have zero width."`

**Verify**: `python -m maid.demo | head -3` → line 1 `# MAID demo report`, line 3 starts `> **Synthetic demo data**`.

### Step 6: CLI flag and one real run

In `src/maid/demo.py` add `p.add_argument("--source", choices=["demo", "sec"])` and include `"source": a.source` in
`given`. Update the module docstring to: `"""Run the whole pipeline: python -m maid.demo [--source sec]."""`.
Add to the `--json` help text: `"(with --source sec, write it under data/: real data stays local)"`.

Real run (only if `.env` has `SEC_USER_AGENT` or the SEC cache under `data/cache/sec` is already filled; never
print the `.env` contents):

`python -m maid.demo --source sec --n-draws 200 | head -25`

Expected: the title line `# MAID report: real data (tech, quantitative only)`; 15 ranking rows, `Company A (AAPL)`
through `Company O (...)`; 4 weights summing to 1; NVIDIA near the top (advisor scratch run: CRITIC top 5
`NVDA, META, AVGO, NOW, QCOM`). If there's no network and no cache, skip the real run and say so in the report.

**Verify**: `git status --short` shows no file under `data/`.

### Step 7: Tests in `tests/test_real_data.py`

Copy the `no_network` autouse fixture from `tests/test_sec.py`. Build fake company facts from the existing fixture
(this helper was checked: it gives three different, valid rows):

```python
F = json.loads((Path(__file__).parent / "fixtures/sec/companyfacts_example.json").read_text())


def fake_facts(cik):
    """The example fixture with per-company scaled values, so the matrix columns are not all constant."""
    f = copy.deepcopy(F)
    g = f["facts"]["us-gaap"]
    for tag, mult in [("NetIncomeLoss", 1 + 0.2 * cik), ("ResearchAndDevelopmentExpense", 1 + 0.1 * cik),
                      ("NetCashProvidedByUsedInOperatingActivities", 1 + 0.15 * cik)]:
        for x in g[tag]["units"]["USD"]:
            x["val"] *= mult
    for x in g["RevenueFromContractWithCustomerExcludingAssessedTax"]["units"]["USD"]:
        if x["end"] < "2024-06-30":
            x["val"] *= 1 - 0.05 * cik
    return f


ROWS = [{"ticker": t, "cik": str(i), "decision_date": "2025-03-31"} for i, t in [(1, "MSFT"), (2, "AAPL"), (3, "NVDA")]]
```

Tests (plain `assert`):
1. `test_anonymize_sorts_by_ticker`: `anonymize(["MSFT", "AAPL"]) == {"Company A": "AAPL", "Company B": "MSFT"}`; duplicates raise `ValueError`.
2. `test_sec_quantitative_labels_and_values`: `sec_quantitative(ROWS, fake_facts, "2025-03-31")`: labels map to AAPL, MSFT, NVDA; every label has the 4 `TECH_CRITERIA` keys; `meta["Company A"]["filed"] <= "2025-03-31"`.
3. `test_sec_quantitative_rejects_other_decision_date`: a row with `decision_date` `"2024-12-31"` → `ValueError` matching `"decision date"`.
4. `test_read_universe_real_file`: `read_universe()` on the committed `data/universe/tech.csv` gives 15 rows with distinct tickers and every `decision_date == "2025-03-31"` (reads a committed file, no network).
5. `test_graph_sec_source_quant_only(monkeypatch)`: `monkeypatch.setattr(graph, "load_sec", lambda d: sec_quantitative(ROWS, fake_facts, d))`; `s = run_demo({"source": "sec", "n_draws": 50})`; assert `s["criteria"] == TECH_CRITERIA`, `s["qualitative"] == []`, `s["overrides"] == []`, `len(s["ranking"]) == 3`, `set(s["tickers"].values()) == {"AAPL", "MSFT", "NVDA"}`, `"Real data" in s["report"]` and `"Company A (AAPL)" in s["report"]`, and the score-noise `lo == hi` for every company.
6. `test_graph_sec_runs_without_interrupt(monkeypatch)`: same monkeypatch; `build_graph().invoke({"settings": {"source": "sec", "n_draws": 20}}, {"configurable": {"thread_id": "t"}})` result has no `"__interrupt__"` key and has `"report"`.
7. `test_unknown_source_rejected`: `validate_settings({"source": "banks"})` raises `ValueError` matching `"source"`.
8. `test_no_ticker_in_scores_or_criteria(monkeypatch)`: after the sec run, no ticker string appears in `s["criteria"]`, `s["companies"]` or `s["filings"]` values (guards the anonymization rule).

**Verify**: `pytest -q tests/test_real_data.py` → `8 passed`; `pytest -q` → `108 passed, 1 skipped`; `ruff check .` → `All checks passed!`

### Step 8: Status docs (one line each, no new claims)

- `docs/architecture/graph.md:26` `ingest` row Status: `demo implemented (synthetic dataset); real SEC tech universe with source="sec" (quantitative only, no LLM)`. In the `PipelineState` keys list add `tickers`: label -> ticker for real data, local only, never in prompts.
- `docs/architecture/data.md:3`: replace `not wired into the graph yet.` with `wired into the graph for tech via settings["source"] = "sec" (src/maid/real_data.py; quantitative only, labels "Company A".. in ticker order).`
- `docs/architecture/overview.md:11` Status cell: `demo implemented; real SEC tech ingest with source="sec" (quantitative only); prices/backtest planned; spec: [data.md](data.md)`.
- `CLAUDE.md` Layout: add `- \`src/maid/real_data.py\`: frozen universe -> anonymized labels -> SEC criteria for the graph` after the `prices.py` line.

**Verify**: `pytest -q tests/test_docs.py` → all pass.

## Test plan

Eight new tests in `tests/test_real_data.py` (listed in Step 7), offline, based on the existing fixture
`tests/fixtures/sec/companyfacts_example.json`. They cover the anonymization order, the decision-date guard, the
committed universe file, the quant-only graph end to end, no interrupt when there is nothing to review, and no
tickers leaking into labels or filings. Existing tests in `tests/test_demo.py` and `tests/test_review.py` guard that
the demo path is unchanged.

## Done criteria

- [ ] `pytest -q` → `108 passed, 1 skipped` (or baseline + 8)
- [ ] `ruff check .` → `All checks passed!`
- [ ] `python -m maid.demo | head -1` → `# MAID demo report`
- [ ] `grep -n '"source": "demo"' src/maid/graph.py` → one match in `DEFAULT_SETTINGS`
- [ ] `git status --short` lists only in-scope files; nothing under `data/`
- [ ] Step 6 real run done (paste the first 25 lines into the report back) or explicitly reported as skipped
- [ ] `plans/README.md` row 023 updated

## STOP conditions

- `report`, `ingest`, `score_qualitative` or `human_review` don't match the excerpts above.
- An existing test in `tests/test_demo.py`, `tests/test_review.py` or `tests/test_gui_*.py` fails after your change,
  and the only fix seems to be changing that test. The demo path must not change.
- In the real run, any of the 15 tickers raises in `tech_criteria`. Expected: none. All 15 passed on 2026-11-02
  after D18. Report the ticker and message; do not add fallbacks.
- `robust_ranking` raises on `cell_samples={}`. Report it; do not change `src/maid/mcdm/`.
- You feel the need to add a bank path or prices. Out of scope.

## Maintenance notes

- The `tickers` key is the only place the label -> ticker map lives. When the real LLM scorer arrives, its prompts
  must be built from `companies` and anonymized filing text only. A reviewer should check that `tickers` never reaches
  a prompt.
- Labels follow alphabetical ticker order, so adding or removing a company relabels others. That's fine while the
  universe is frozen.
- `filings` is `""` per company on real data until the 10-K text plan, and the GUI's filing tab would show blanks.
  The GUI stays on demo data for now.
- Next plans that build on this: backtest (`prices.total_return` over 2025-04-01..2026-03-31, Spearman/Kendall of rank
  vs return, |rho| > ~0.51 for p < 0.05 at n=15), then 10-K text, then the DeepSeek scorer.
- `kendall_tau` returns NaN if a score vector is constant (rejected-for-now in `plans/README.md`); with real data
  TOPSIS and SAW scores are not constant (scratch run tau ~0.85), so it stays deferred.
