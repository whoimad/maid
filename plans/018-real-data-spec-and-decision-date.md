# Plan 018: Write the real-data spec (D17) and move the decision date to 2025-03-31

> **Executor instructions**: Follow this plan step by step. Run every verification command and confirm the expected
> result before moving to the next step. If anything in the "STOP conditions" section occurs, stop and report — do
> not improvise. When done, update the status row for this plan in `plans/README.md` — unless a reviewer dispatched
> you and told you they maintain the index.
>
> **Drift check (run first)**: `git diff --stat 66b0316 -- docs/ CLAUDE.md README.md .gitignore .env.example src/maid/config.py src/maid/graph.py`
> must print nothing. If it prints changes, compare the touched files against the excerpts below; if they no longer
> match, STOP.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: LOW (docs, one config default, one report string, `.gitignore`)
- **Depends on**: none
- **Category**: docs / direction
- **Planned at**: commit `66b0316` (branch `integration/prototype`), 2026-11-02

## Why this matters

MAID ranks companies with a deterministic MCDM engine. LLM agents only score text. The pipeline currently runs on
synthetic data, and the next step is real data: SEC EDGAR (10-K filings and XBRL numbers) and yfinance (prices).
Before anyone writes ingest code, the docs must fix a look-ahead contradiction and set the rules the code will
implement.

**The contradiction.** `docs/SCOPE.md` §3 sets the decision date to 2024-12-31 *and* says agents read "FY2024 10-K
filings". A 10-K is filed 1–3 months after the fiscal year ends. Alphabet's FY2024 ends 2024-12-31, and its 10-K was
filed in early February 2025, after that decision date. The owner decided (2026-11-02) to move the decision date to
**2025-03-31**. By then every large US company has filed its 10-K for the latest fiscal year, since large
accelerated filers must file within 60 days. The evaluation window becomes **2025-04-01 to 2026-03-31**.

The owner also decided:
- **15 companies per sector** (was "10–15" or "~12"). There are two sectors: tech first, then banks.
- The **universe list is committed** to git, but **every downloaded or derived data file stays local** (gitignored,
  never pushed).
- Fiscal year ends are **not hard-coded** per company. They are derived from the filing data by a general rule.

This plan only writes docs and changes a default. Plans 019 (SEC ingest) and 020 (universe and prices) implement it.

## Current state

Files and the exact text to change:

- `docs/SCOPE.md` lines 14–18 (§3):
  ```
  ## 3. Time frame (look-ahead control)
  - Decision date: **2024-12-31**. Agents see only information available on or before this date
    (FY2024 10-K filings, prices up to the date).
  - Evaluation window: calendar 2025.
  ```
  Line 26: `- Phase 1: US **technology** sector, 10–15 companies. Phase 2: US **banks**, 10–15 companies.`
  Line 28: `- Selection rule: N largest by market cap within the sector at 2024-12-31, list frozen and committed.`
  Line 44: `- Backtest: Spearman correlation of ranks with 2025 total return and a risk-adjusted measure.`
  Line 45: `  Reported as correlation, not "accuracy"; with 10–15 names it is noisy.`
- `docs/architecture/decisions.md` line 15: `## D3. Decision date 2024-12-31, backtest on 2025, anonymized company names`
  and the body below it (lines 16–19). The last decision is D16 (line 87). The format is in line 3: "Format:
  decision, alternatives, why, cost."
- `docs/architecture/overview.md` lines 11 (Ingest row), 13 (Config row: `DECISION_DATE` (default 2024-12-31)),
  19 (`| Backtest vs 2025 | none | planned |`), and the time-boundary diagram at lines 96–112:
  ```
      D1[FY2024 10-K filings]
      D2[Prices up to 2024-12-31]
    end
    X((Decision date<br/>2024-12-31))
    subgraph after[" Evaluation only "]
      E1[2025 returns]
  ```
  Line 90: `    O --> E[Backtest vs 2025 returns]`.
- `docs/architecture/uncertainty.md` lines 11, 42, 48 mention 2024-12-31, "2025 backtest", "2025 returns" and n=12.
- `docs/INTERVIEW.md` lines 14, 49–50, 77 mention 2024-12-31 and 2025.
- `docs/WALKTHROUGH.md` lines 77 and 233 mention 2024-12-31.
- `CLAUDE.md` line 33: `- Decision date is 2024-12-31: agents see only information available on or before it. Company names`
- `.env.example` line 5 sets `DECISION_DATE` to the old date.
- `src/maid/config.py:18`: `decision_date: str = field(default_factory=lambda: os.getenv("DECISION_DATE", "2024-12-31"))`
- `src/maid/graph.py:147` (inside `report()`):
  `"> **Synthetic demo data**: invented companies, not real ones. Decision date 2024-12-31.", "",`
- `.gitignore` currently has the line `data/cache/` (plus `.venv/`, `__pycache__/`, `*.egg-info/`, `.env`,
  `.pytest_cache/`, `.claude/worktrees/`).
- `docs/research/*.md` and `plans/*.md` also mention 2024-12-31. **Do not edit them**: research notes and plans are
  dated records.

Conventions: short, plain sentences; tables for comparisons; relative Markdown links. `tests/test_docs.py` fails if
any relative link in `docs/**.md` or `README.md` does not resolve.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Setup | `python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev,gui]"` | exit 0 |
| Tests | `pytest -q` | all pass |
| Lint | `ruff check .` | `All checks passed!` |
| Old date left | `grep -rn "2024-12-31" docs/SCOPE.md docs/architecture docs/INTERVIEW.md docs/WALKTHROUGH.md CLAUDE.md .env.example src/` | only lines that explicitly describe the *old* date as history (see Step 6) |

## Scope

**In scope:**
- `docs/architecture/data.md` (create)
- `docs/architecture/decisions.md`, `docs/architecture/overview.md`, `docs/architecture/uncertainty.md`
- `docs/SCOPE.md`, `docs/INTERVIEW.md`, `docs/WALKTHROUGH.md`
- `CLAUDE.md`, `.env.example`, `.gitignore`
- `src/maid/config.py` (one default string), `src/maid/graph.py` (one report string)

**Out of scope:**
- `.env`: the owner's local secrets file. Never open, print or edit it. (The owner must update their own
  `DECISION_DATE` there. Say so in your final report.)
- `docs/research/**` and `plans/**` except the status row in `plans/README.md`.
- Any ingest code. Plans 019 and 020 write it.

## Git workflow

- Branch: `docs/real-data-spec` from the current `integration/prototype` HEAD.
- Conventional commits, e.g. `docs: real-data spec and decision date 2025-03-31 (D17)`. The repo style is visible in
  `git log --oneline -5` (`docs(plans): mark 017 done`, `feat(mcdm): rank intervals from LLM score noise`).
- Do NOT push or open a PR.

## Steps

### Step 1: Create `docs/architecture/data.md`

Write it with these sections, in this order. Use the content given here; you may tighten the wording, but do not
change any rule, number or tag name.

1. `# Real data: sources, time rule, universe, criteria`. One intro line: this page is the spec that the ingest code
   (`src/maid/sec.py`, `src/maid/xbrl.py`, `src/maid/universe.py`, `src/maid/prices.py`) implements. Status: planned.
2. `## Sources`: a table.
   | Source | Used for | Access |
   |---|---|---|
   | SEC EDGAR `companyfacts` API (`https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json`) | XBRL numbers for quantitative criteria, shares outstanding | free; a `User-Agent` header with a contact email is required; at most 10 requests/s |
   | SEC EDGAR `submissions` API (`https://data.sec.gov/submissions/CIK##########.json`) | company name, SIC code, fiscal year end, filing list | same |
   | SEC `company_tickers_exchange.json` (`https://www.sec.gov/files/company_tickers_exchange.json`) | ticker → CIK, exchange | same |
   | SEC EDGAR filing documents | 10-K text for the qualitative scorer (later plan) | same |
   | yfinance | prices on the decision date (universe selection) and total returns in the evaluation window (backtest) | unofficial Yahoo scraper; can break or rate-limit; personal research use |
3. `## Time rule (look-ahead control)`. Content:
   - Decision date **2025-03-31** (env `DECISION_DATE`). Evaluation window **2025-04-01 to 2026-03-31**.
   - Rule, verbatim: "For each company, use the most recent **10-K** (not 10-K/A) whose **filing date is on or before
     the decision date**. Use only XBRL facts that were filed on or before the decision date, and take the
     values reported in that 10-K."
   - Why the filing date and not the fiscal year: a 10-K appears 1–3 months after its fiscal year ends. Example
     table (fiscal year ends from SEC `fiscalYearEnd`; filing dates are approximate):
     | Company | Fiscal year end | Latest 10-K on 2025-03-31 covers the year ending |
     |---|---|---|
     | Microsoft | June 30 | 2024-06-30 |
     | Apple | late September | 2024-09-28 |
     | Alphabet | December 31 | 2024-12-31 (filed early Feb 2025) |
     | NVIDIA | late January | 2025-01-26 (filed late Feb 2025) |
   - Consequence, stated as a known limitation: period ends differ by up to about 9 months across companies. Every
     company is measured on its latest full fiscal year that was public on the decision date.
   - Fiscal year ends are never hard-coded. The code derives the period from the facts (`end`, `filed`, `form`
     fields).
   - Restatements: `companyfacts` also contains values re-reported in later filings. The `filed <= decision date`
     filter plus "values from that 10-K" excludes them.
4. `## Universe`. Content:
   - 15 companies per sector. Tech first, banks second.
   - Sector by SEC SIC code (free and deterministic; GICS is not free):
     | Sector | SIC codes |
     |---|---|
     | Tech | 3570–3579 (computer equipment), 3661–3663 (communications equipment), 3670–3679 (semiconductors and electronic components), 7370–7379 (software and IT services) |
     | Banks | 6021 (national commercial banks), 6022 (state commercial banks) |
   - Known side effects of SIC: Amazon (5961) and Tesla (3711) are not tech. Visa and Mastercard (7389) are not
     tech. Goldman Sachs and Morgan Stanley (6211, broker-dealers) are not banks. Alphabet and Meta (7370) are tech.
   - Eligibility: listed on NYSE or Nasdaq; files 10-K (foreign 20-F filers are excluded); has a 10-K filed on or
     before the decision date that also reports the prior fiscal year (needed for revenue growth).
   - Ranking: market cap on the decision date = shares outstanding (XBRL `dei:EntityCommonStockSharesOutstanding`,
     summed over share classes, from the latest filing filed on or before the decision date) × closing price on the
     decision date (yfinance, split-corrected). Multi-class companies use one class's price: an approximation.
   - The list is frozen and committed at `data/universe/<sector>.csv`. It is the only committed file under `data/`.
   - Known limitation (keep from SCOPE §4): selecting the largest names adds mild survivorship and winner bias.
5. `## Quantitative criteria (tech)`: a table. All are benefit-type (higher is better). The tag lists are
   fallbacks: the first tag that has a matching fact wins, and the tag used is recorded.
   | Criterion | Formula | XBRL tags (us-gaap, in fallback order) |
   |---|---|---|
   | `revenue_growth` | Rev(FY) / Rev(FY−1) − 1 | Revenue: `RevenueFromContractWithCustomerExcludingAssessedTax`, `Revenues`, `SalesRevenueNet` |
   | `operating_margin` | OperatingIncome / Rev | `OperatingIncomeLoss` |
   | `fcf_margin` | (OperatingCashFlow − Capex) / Rev | `NetCashProvidedByUsedInOperatingActivities`; capex: `PaymentsToAcquirePropertyPlantAndEquipment`, `PaymentsToAcquireProductiveAssets` |
   | `rd_intensity` | R&D / Rev | `ResearchAndDevelopmentExpense`, `ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost` |
   - Annual fact = duration between 350 and 380 days (52/53-week years) with `end` equal to the 10-K's fiscal
     period end. FY−1 = the same tags, same 10-K accession, `end` 350–380 days earlier.
   - If no tag matches, ingest fails loudly with the company, criterion and tags tried. It never fills in zero.
6. `## Quantitative criteria (banks)`: status OPEN. SCOPE lists CET1, NIM, efficiency ratio and NPL ratio. CET1 and
   NPL are not reliably tagged in us-gaap XBRL, so the bank criteria need their own spike before coding.
7. `## Local-only data`: downloads and derived files live under `data/cache/` and `data/raw/` (both gitignored) and
   are never committed or pushed (owner rule). Only `data/universe/*.csv` is committed. Tests use small hand-made
   JSON fixtures under `tests/fixtures/`, never real downloads, and never touch the network.

**Verify**: `test -f docs/architecture/data.md && grep -c "2025-03-31" docs/architecture/data.md` → a number ≥ 2.

### Step 2: Add D17 and update D3 in `docs/architecture/decisions.md`

- Change the D3 heading to `## D3. Decision date 2025-03-31, backtest 2025-04-01 to 2026-03-31, anonymized company names`.
  In its **Why** bullet, replace "the decision date" wording only if it names 2024-12-31. Add one line at the end of
  D3: `- **Changed 2026-11-02:** was 2024-12-31; moved by D17.`
- Append after D16:
  ```
  ## D17. Real data: point-in-time 10-K rule, decision date 2025-03-31, SIC sectors, 15 names
  - **Alternatives:** keep 2024-12-31 and use the latest 10-K filed by then (mixes FY2023 and FY2024 reports);
    hard-code each company's fiscal year end; GICS sectors; a hand-picked company list (owner rejected it as
    cherry-picking); letting an LLM pick the companies (not reproducible, and a selection is a ranking, which D1
    reserves for deterministic code).
  - **Why:** a 10-K is public 1-3 months after its fiscal year ends, so on 2024-12-31 December year-end companies
    had not filed FY2024. On 2025-03-31 every company's latest full year is public. A filing-date rule works for
    any company without per-company code. SIC codes are free and deterministic. The details are in [data.md](data.md).
  - **Cost:** fiscal period ends still differ by up to ~9 months across companies; the model has seen even more
    post-decision text (already assumed, D3/D14); SIC puts Alphabet and Meta in tech but not Amazon or Visa.
  - **Revisit if:** the bank sector needs a different date, or SIC yields an implausible universe.
  ```

**Verify**: `grep -c "^## D17" docs/architecture/decisions.md` → `1`; `grep -n "^## D3" docs/architecture/decisions.md` → contains `2025-03-31`.

### Step 3: Update `docs/SCOPE.md`

- §3: decision date **2025-03-31**; "(latest 10-K filed on or before the date, prices up to the date; see
  `architecture/data.md`)"; evaluation window "2025-04-01 to 2026-03-31".
- Line 26: `10–15 companies` → `15 companies` (both phases).
- Line 28: `at 2024-12-31` → `at the decision date (SIC-defined sector; see architecture/data.md)`.
- Line 44: `2025 total return` → `total return over the evaluation window`. Line 45: `10–15 names` → `15 names`.
- In §9 change the open question `Final criteria list for tech ...` by appending ` (quantitative part: see architecture/data.md)`.

Write the references as plain text, not Markdown links. SCOPE.md has no links today.

**Verify**: `grep -n "2024-12-31\|10–15\|calendar 2025" docs/SCOPE.md` → no output.

### Step 4: Update overview, uncertainty, INTERVIEW, WALKTHROUGH, CLAUDE.md

- `overview.md`: in the Ingest row add `spec: [data.md](data.md)`. In the Config row change `(default 2024-12-31)` to
  `(default 2025-03-31)`. Change `Backtest vs 2025` to `Backtest (2025-04 to 2026-03)` in the table row and in the
  diagram node at line 90. In the time-boundary diagram use
  `D1[Latest 10-K filed by 2025-03-31]`, `D2[Prices up to 2025-03-31]`, `X((Decision date<br/>2025-03-31))`,
  `E1[Returns 2025-04-01 to 2026-03-31]`. Add `data.md` to the "## Blocks" list with a one-line description.
- `uncertainty.md` line 42: `post-2024-12-31` → `post-2025-03-31`, `Decision date 2024-12-31` → `Decision date 2025-03-31`.
  Lines 11 and 48: `2025 backtest` / `2025 returns` → `backtest` / `evaluation-window returns`. Keep the n=12
  threshold statements as they are, and add after line 11's sentence: ` At n=15 the threshold is about 0.51.`
  (Check it: t = r·sqrt(n−2)/sqrt(1−r²) with n=15, two-sided p<0.05, t_crit(13) ≈ 2.160 gives r ≈ 0.514.)
- `INTERVIEW.md` lines 14, 49–50, 77 and `WALKTHROUGH.md` lines 77, 233: replace the old date with 2025-03-31 and
  "2025 returns"/"2025 backtest" with "returns from 2025-04 to 2026-03"/"backtest". Do not add new claims.
- `CLAUDE.md` line 33: `Decision date is 2024-12-31` → `Decision date is 2025-03-31 (D17)`. Add one rule bullet
  under "Rules (non-negotiable)": `- Downloaded/derived real data (SEC, yfinance) stays local: only \`data/universe/*.csv\` is committed.`
  Add to "Docs to read before changing X": `- \`docs/architecture/data.md\` before touching ingest, XBRL or prices.`

**Verify**: `pytest -q tests/test_docs.py` → all pass (links resolve).

### Step 5: Config default, report string, `.env.example`, `.gitignore`

- `src/maid/config.py:18`: change the default `"2024-12-31"` to `"2025-03-31"`. Nothing else.
- `src/maid/graph.py:147`: change `Decision date 2024-12-31.` to `Decision date 2025-03-31.`. Nothing else.
- `.env.example`: set the `DECISION_DATE` value to `2025-03-31`. Add two lines after it:
  ```
  # SEC requires a contact in the User-Agent, e.g. "MAID research you@example.com"
  SEC_USER_AGENT=
  ```
- `.gitignore`: replace the line `data/cache/` with:
  ```
  # real data stays local; only the frozen universe lists are committed
  data/*
  !data/universe/
  ```

**Verify**:
- `pytest -q` → all pass. If a test asserts the old date string, STOP (see STOP conditions).
- `mkdir -p data/raw data/universe && touch data/raw/x.json data/universe/x.csv && git status --porcelain data/` →
  exactly one line, `?? data/universe/`. Then `rm data/raw/x.json data/universe/x.csv && rmdir data/universe data/raw`.
- `ruff check .` → `All checks passed!`

### Step 6: Final sweep

Run `grep -rn "2024-12-31" docs/SCOPE.md docs/architecture docs/INTERVIEW.md docs/WALKTHROUGH.md CLAUDE.md .env.example src/`.
The only allowed hits are lines that describe the old date as history: D3's "Changed" line, D17's Alternatives and
Why bullets, and data.md if it mentions the old date as context. Fix any other hit.

**Verify**: re-run the grep; every remaining hit is one of those lines.

## Test plan

No new tests. `tests/test_docs.py` checks the new links. The `.gitignore` check in Step 5 is manual and its exact
command and output are given there.

## Done criteria

- [ ] `docs/architecture/data.md` exists with the 7 sections of Step 1.
- [ ] `grep -c "^## D17" docs/architecture/decisions.md` → `1`.
- [ ] `grep -n "2024-12-31\|10–15\|calendar 2025" docs/SCOPE.md` → no output.
- [ ] `grep -n '"2025-03-31"' src/maid/config.py` → one hit.
- [ ] `pytest -q` and `ruff check .` pass.
- [ ] The `.gitignore` check in Step 5 prints only `?? data/universe/`.
- [ ] `git diff --name-only 66b0316` lists only in-scope files (plus `plans/README.md`).
- [ ] Final report reminds the owner to set `DECISION_DATE=2025-03-31` and `SEC_USER_AGENT` in their own `.env`.

## STOP conditions

- An excerpt in "Current state" does not match the file.
- A test asserts the literal `2024-12-31` (you would have to edit a test file, which is out of scope).
- You find yourself wanting to edit `.env`, `docs/research/` or old plans.
- The n=15 correlation threshold you compute differs from about 0.51 by more than 0.02.

## Maintenance notes

- Plans 019 (SEC ingest) and 020 (universe and prices) implement `data.md`. If they find a tag or rule that doesn't
  work, update `data.md` in the same PR.
- The bank criteria are OPEN. They need their own spike plan.
- The owner's `.env` overrides the new default. Until they update it, runs still use their old value.
