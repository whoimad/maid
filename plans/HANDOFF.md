# Session handoff: real data (2026-11-02)

For the next session. Read this first, then `plans/README.md` (status of every plan) and `docs/architecture/data.md`
(the real-data spec).

## Goal

Move MAID from synthetic demo data to **real data**: SEC EDGAR (10-K filings, XBRL numbers) and yfinance (prices).
The owner wants the project to be defensible in interviews: no cherry-picking and no look-ahead, and the rules live
in code, not in anyone's judgment. Workflow: the `/improve` skill. The advisor writes plans in `plans/`, executor
subagents implement them in worktrees, and the advisor reviews and merges into the local branch
`integration/prototype`. Nothing is pushed; the owner merges to GitHub.

## Owner decisions made this session (do not re-ask)

- **Decision date 2025-03-31**, not 2024-12-31. On 2024-12-31, December year-end companies had not filed their FY2024
  10-K. The evaluation window is **2025-04-01 to 2026-03-31**. Recorded as D17 in `docs/architecture/decisions.md`
  (D3 updated).
- **Rule:** use the latest 10-K (not 10-K/A) **filed** on or before the decision date, and only XBRL facts filed by
  then. Fiscal year ends are never hard-coded.
- **15 companies per sector**, tech and banks. The companies are **picked by a deterministic rule, not by a person
  or an LLM**: SEC SIC code in the sector, NYSE/Nasdaq, files 10-K, top 15 by market cap on the decision date.
  The owner explicitly rejected hand-picking as cherry-picking.
- Sectors by SIC: tech 3570–3579, 3661–3663, 3670–3679, 7370–7379; banks 6021, 6022.
- **Downloaded data stays local** (gitignored: `data/*` except `data/universe/`). Only `data/universe/*.csv` is
  committed. Also saved in memory (`real-data-local-only`).
- The owner's `.env` exists (gitignored) with `SEC_USER_AGENT` (their contact email) and `DECISION_DATE=2025-03-31`.
  Never print it.

## What was done

| Plan | Result |
|---|---|
| 018 | Spec `docs/architecture/data.md`, D17, decision-date change across docs/config, `.gitignore` rule |
| 019 | `src/maid/xbrl.py` (pure point-in-time extraction), `src/maid/sec.py` (cached SEC client), `scripts/fetch_sec.py` |
| 020 | `src/maid/prices.py` (yfinance, optional extra `data`), `src/maid/universe.py`, `scripts/select_universe.py` |
| 021 | Parallel SEC downloads (8 workers, shared ≤ 8 req/s cap) and retry. The scan went from ~1.5 h to minutes |
| 022 | Fix: share-count fallbacks for multi-class companies (Alphabet and Meta were missing), Yahoo retries (NVIDIA was dropped by a DNS error), Adobe R&D tag |

Real runs (with the owner's `.env`):
- `fetch_sec.py` on 15 tech tickers: 13 OK, numbers sensible (NVDA growth 114%, AAPL 2%). Adobe has since been fixed
  by 022. **IBM still fails** (see below).
- **Frozen universes, committed** (`c72ac31`, `e0e7dda`):
  - Tech: AAPL, MSFT, NVDA, GOOGL, META, AVGO, ORCL, CRM, CSCO, IBM, PLTR, INTU, QCOM, AMD, NOW.
    15th place is close: NOW 164.0bn vs TXN 163.6bn and ADBE 163.5bn.
  - Banks: JPM, BAC, WFC, C, PNC, COF, USB, BNY, TFC, MTB, FCNCA, FITB, STT, HBAN, RF.
  - Both passed their sanity checks (giants in; AMZN/TSLA/V/MA and GS/MS out).
- Tests: 100 pass (1 skipped), ruff clean (on `integration/prototype`, HEAD `e0e7dda` + this file).

## Failing or unfinished

**Update (same day):** items 1, 2 and 4 are done (D18). Owner said "keep it as simple as possible": `operating_margin`
became `net_margin` (`NetIncomeLoss`, the only income tag all 15 report). data.md frozen tables filled. `fetch_sec.py`
on all 15 tech tickers: 15 OK. Plan 023 (DONE, merged `b998797`): `python -m maid.demo --source sec` ranks the
real tech universe, quant only (108 tests). Next: backtest.

1. **IBM has no `OperatingIncomeLoss` in XBRL.** `tech_criteria` raises for IBM, so the `operating_margin` cell is
   missing. **This is an owner decision**: use a different income measure for everyone, a per-company fallback
   (document it), or drop IBM and take #16 (which breaks the rule). Ask; do not decide silently.
2. **`docs/architecture/data.md` "Frozen universes"** still says "Not yet selected". It needs the two tables and the
   close 15th place noted.
3. **Bank criteria are OPEN.** CET1 and NPL are not reliably in us-gaap XBRL; NIM and the efficiency ratio may be
   computable. A spike is needed before any bank ingest. The bank revenue tags used for eligibility
   (`Revenues`, `InterestAndDividendIncomeOperating`) worked for selection but were never checked as criteria.
4. **`fetch_sec.py` has not been re-run on the final 15 tech tickers** since plan 022 (expect only IBM to fail).
5. Mistakes made this session, worth avoiding next time:
   - I underestimated the SEC scan time (said ~20 min; the sequential version needed ~1.5 h).
   - Plan 020 missed multi-class share counts and yfinance network errors. Both were caught by the sanity check, not
     by tests. For real-data plans, always include a named-company sanity list.
6. Stale agent worktrees pile up under `.claude/worktrees/`; clean up if the owner agrees.

## Planned next (not yet written as plans)

In rough order:
1. **Small docs/IBM plan**: fill in data.md frozen tables, plus the IBM decision once the owner makes it.
2. **Wire real data into the graph**: `ingest()` with `settings["source"] in {"demo", "sec"}`; read
   `data/universe/tech.csv`; anonymize tickers to "Company A..O" (the map stays out of prompts); quantitative-only run
   first (no LLM), which is also the SCOPE §6 quant-only ablation baseline. Watch `kendall_tau` NaN on constant
   columns (noted as rejected-for-now in `plans/README.md`).
3. **Backtest**: `prices.total_return` over 2025-04-01 to 2026-03-31; Spearman/Kendall of rank vs return; at n=15 |rho|
   must exceed about 0.51 for p<0.05.
4. **10-K text**: download the filing document, extract Items 1, 1A and 7, anonymize (names and products), and a
   whitespace-normalized evidence check (the current `evidence_is_quoted` is an exact substring match).
5. **Real DeepSeek scorer** (`deepseek-flash`, pinned version, cache keys with model and prompt version per D7).
   Cost estimate about $1–2 per sector.
6. **Bank criteria spike.**

## Useful commands

```bash
source .venv/bin/activate
pytest -q && ruff check .
python scripts/fetch_sec.py AAPL MSFT NVDA            # point-in-time tech criteria (needs .env)
python scripts/select_universe.py tech                # re-check selection (SIC cache in data/cache/sic; fast)
```
