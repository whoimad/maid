# Session handoff (2026-11-02, end of day)

Start here. Then read, in this order:
1. `notes/MEMO.md` (local only, not on GitHub): the owner's high-level project memo. It has the full story and the
   per-company tech results.
2. `plans/README.md`: status of every plan.
3. `docs/architecture/data.md`: the real-data spec.

Workflow: the `/improve` skill. The advisor writes plans in `plans/`, executor subagents implement them in
worktrees, and the advisor reviews and merges into the local branch `integration/prototype`. Push only when the
owner says so.

## Git state

- Local `integration/prototype` is ahead of GitHub (`9d7def1`). The result note
  `docs/research/backtest-quant-only-results.md` and this handoff are **not pushed yet**. Ask before pushing. The
  push updates PR #16.
- PR #16 (`integration/prototype` -> `main`) is open and green. The owner merges it.
- No stale worktrees. Tests: 115 passed, 1 skipped; ruff clean.

## Owner decisions (do not re-ask)

Earlier sessions:
- **Decision date** 2025-03-31. **Evaluation window** 2025-04-01 to 2026-03-31.
- **Point-in-time rule:** use the latest 10-K filed on or before the decision date.
- **Universe:** picked by a rule only, never by hand or by an LLM.
- **Data:** real data stays local. Only `data/universe/*.csv` is committed.

This session:
1. **Net margin replaces operating margin** for everyone (D18). IBM has no operating income in XBRL, and the owner
   wanted the simplest rule with no per-company exceptions.
2. **The tech result is documented as a process result, not hidden.**
   - Result: quant-only, 15 companies, primary CRITIC + Kendall tau = +0.05 (p = 0.85).
   - Committed note: `docs/research/backtest-quant-only-results.md` (summary stats only; per-company returns stay
     local).
   - Why it was a weak test: power at n = 15 is tiny (9% for rho = 0.2), it is one AI-driven year, and CRITIC weights
     measure dispersion, not relevance.
3. **Next sector: consumer staples** (the owner thinks tech is too volatile). Defined by SEC SIC code:
   - food and beverages 2000–2099
   - tobacco 2100–2199
   - household and personal products 2840–2844
   - grocery stores 5411

   Known side effects, accepted as written:
   - Out: Walmart, Costco, Target, Dollar General (5331), Sysco (5140), Kimberly-Clark (2670).
   - In: Ecolab.

   Rejected sectors: energy (driven by geopolitics), utilities (regulated, move with interest rates), pharma
   (biotechs, policy shocks). Medical devices is the backup sector.
4. **One set of fallback tags for everyone.** Earlier tags still win where present, so the tech numbers do not
   change:
   - revenue: add `RevenueFromContractWithCustomerIncludingAssessedTax` last in `xbrl.REVENUE` (fixes Kraft Heinz,
     Smucker, Lamb Weston);
   - net income: `["NetIncomeLoss", "ProfitLoss"]` (fixes Monster, Estée Lauder, Zevia).
5. **Size floor: market cap of at least $1bn** on 2025-03-31. Expect about 55 companies (about 58 with the
   delisted ones).
6. **Fourth staples criterion: return on assets** = net income / total assets, where total assets is the instant
   fact `Assets` at the 10-K period end. It replaces `rd_intensity`, which most staples don't report. Gross margin
   and asset turnover were rejected because they mostly reflect the business model. So the staples criteria are
   `revenue_growth, net_margin, fcf_margin, roa`.
7. **Share-count fix**, one rule for everyone, in `universe.shares_outstanding`:
   - skip a source whose latest value is zero or was filed more than about 15 months before the date, and try the
     next source;
   - add a fourth source: the cover-page `dei:EntityCommonStockSharesOutstanding` read from the 10-K's own XBRL
     instance document (with class dimensions, summed over classes).

   Why: Molson Coors gets a zero share count from 2010. Tyson and Constellation (two share classes) have no
   usable share count in companyfacts at all. The frozen tech and bank top-15 lists were checked and are not
   affected: every company the bug hits there is far below #15 (largest is Shopify at about $124bn vs #15 at
   $164bn).
8. **Survivorship fix.** Build candidates from companies that filed for 2024, not from today's ticker list. The
   ticker file only lists currently traded tickers. The SEC frames `us-gaap/Assets/USD/CY2024Q1I..Q4I` give every
   filer.
   - Found: Kellanova (about $28bn), TreeHouse (about $2–3bn) and WK Kellogg (about $1.7bn) were listed on
     2025-03-31 but have been delisted since. SunOpta and Olaplex are borderline around $1bn.
   - Rule: include a delisted company if a price history exists. Its return runs to the last trading day, with zero
     return on the cash after. Otherwise list it as excluded, with the reason.
   - Guard against reused tickers ("K").
9. **Test fixed before the run** (pre-registration), unchanged from tech:
   - primary: CRITIC weights, TOPSIS score vs total return, Kendall tau, two-sided;
   - secondary: Spearman;
   - sensitivity: entropy and equal weights.

   Power at n ≈ 55: about 31% for rho = 0.2 and about 61% for rho = 0.3. Say so in the write-up.

## Next: write two plans (the owner asked for a split)

**Plan 025: build and freeze the staples universe. No returns are computed or looked at.**
- `universe.py`:
  - `SECTORS["staples"]` with the SIC ranges above;
  - the share-count fix (decision 7);
  - a size floor option instead of a fixed N for staples (`MIN_CAP = 1e9`).
- `xbrl.py`: the revenue and net-income fallbacks (decision 4), plus a pure `staples_criteria(facts, date)` with ROA.
  The instant `Assets` fact must match the 10-K accession and period end.
- `scripts/select_universe.py`:
  - candidates from the 2024 Assets frames, not from today's ticker list;
  - the exchange on the decision date from the 10-K cover (`dei:SecurityExchangeName`) or from submissions;
  - the ticker from the 10-K cover (`dei:TradingSymbol`).

  Remember: `PRESCREEN = 40` and the silent `if cik not in shares: continue` both drop companies. Neither is
  acceptable for a floor-based universe.
- Named-company sanity list:
  - must be in: PG, KO, PM, PEP, MO, MDLZ, CL, KHC, GIS, HSY, TSN, STZ, TAP, MNST, EL, KR, Kellanova;
  - must be out: WMT, COST, Publix, Unilever/BAT (20-F filers).
- Real runs need `SEC_USER_AGENT` (already in `.env`, never print it) and Yahoo for the 2025-03-31 prices.
- Freeze to `data/universe/staples.csv`.
- Tests: offline fixtures, as for tech.
- Re-run `scripts/fetch_sec.py` on the 15 tech tickers to show the tech numbers are unchanged.

**Plan 026: staples backtest**, after 025 is frozen and reviewed:
- `source="sec"` gets a sector option (staples criteria, staples universe).
- Labels: "Company A..Z" breaks above 26, so switch to "Company 001"-style labels.
- `scripts/backtest.py` for staples, with the delisted rule.
- Primary test as in decision 9, written into `data.md` **before** the run.
- Update `notes/MEMO.md` with the result. Commit only summary stats (as for tech).

## Practical warnings

- **Yahoo rate limits often.** It then returns empty data for valid tickers, which looks like "no price data".
  - Test with a live ticker (GIS) before concluding a ticker is delisted.
  - Successes are cached; re-run later.
  - Stooq is not usable: it blocks automated downloads.
- Whether Yahoo still has history for delisted K / THS / KLG / STKL / OLPX was **not confirmed**: it was rate
  limiting at the time. Check this first in plan 025 or 026. If Yahoo has no history, the delisted rule says
  "excluded, with reason".
- Executors' worktrees start from `main`. Tell them to `git reset --hard <integration/prototype SHA>` first. The venv
  is in the main repo: use `PYTHONPATH=<worktree>/src`. Real runs must use `/home/imad/maid` as the working
  directory (for the data cache).
- The advisor's scratch scripts (coverage check, caps, survivorship count, scratch backtest) are saved locally in
  `notes/scratch/`. They show working code for frames, the staples SIC filter, tag coverage and the delisted search.

## Useful commands

```bash
source .venv/bin/activate
pytest -q && ruff check .
python -m maid.demo --source sec          # real tech ranking, quant only
python scripts/backtest.py                # tech backtest (needs Yahoo)
python notes/scratch/staples_caps.py      # staples coverage + caps estimate (local scratch)
python notes/scratch/survivors.py         # delisted staples count (local scratch)
```
