# Real data: sources, time rule, universe, criteria

This page is the spec that the ingest code (`src/maid/sec.py`, `src/maid/xbrl.py`, `src/maid/universe.py`, `src/maid/prices.py`) implements. Status: SEC quantitative extraction implemented (`xbrl.py`, `sec.py`, `scripts/fetch_sec.py`), universe selection (`universe.py`, `scripts/select_universe.py`) and the price layer (`prices.py`) implemented; the consumer-staples universe (floor rule, plan 025) is built and frozen with no returns looked at; wired into the graph for tech and staples via settings["source"] = "sec" and settings["sector"] (src/maid/real_data.py; quantitative only, labels "Company 001".. in ticker order).

## Sources

| Source | Used for | Access |
|---|---|---|
| SEC EDGAR `companyfacts` API (`https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json`) | XBRL numbers for quantitative criteria, shares outstanding | free; a `User-Agent` header with a contact email is required; at most 10 requests/s |
| SEC EDGAR `submissions` API (`https://data.sec.gov/submissions/CIK##########.json`) | company name, SIC code, fiscal year end, filing list | same |
| SEC `company_tickers_exchange.json` (`https://www.sec.gov/files/company_tickers_exchange.json`) | ticker to CIK, exchange | same |
| SEC EDGAR filing documents | 10-K text for the qualitative scorer (later plan) | same |
| yfinance | prices on the decision date (universe selection) and total returns in the evaluation window (backtest) | unofficial Yahoo scraper; can break or rate-limit; personal research use |

## Time rule (look-ahead control)

- Decision date **2025-03-31** (env `DECISION_DATE`). Evaluation window **2025-04-01 to 2026-03-31**.
- Rule: "For each company, use the most recent **10-K** (not 10-K/A) whose **filing date is on or before the decision date**. Use only XBRL facts that were filed on or before the decision date, and take the values reported in that 10-K."
- Why the filing date and not the fiscal year: a 10-K appears 1-3 months after its fiscal year ends. Example (fiscal year ends from SEC `fiscalYearEnd`; filing dates are approximate):

| Company | Fiscal year end | Latest 10-K on 2025-03-31 covers the year ending |
|---|---|---|
| Microsoft | June 30 | 2024-06-30 |
| Apple | late September | 2024-09-28 |
| Alphabet | December 31 | 2024-12-31 (filed early Feb 2025) |
| NVIDIA | late January | 2025-01-26 (filed late Feb 2025) |

- Known limitation: period ends differ by up to about 9 months across companies. Every company is measured on its latest full fiscal year that was public on the decision date.
- Fiscal year ends are never hard-coded. The code derives the period from the facts (`end`, `filed`, `form` fields).
- Restatements: `companyfacts` also contains values re-reported in later filings. The `filed <= decision date` filter plus "values from that 10-K" excludes them.

## Universe

- 15 companies per sector. Tech first, banks second.
- Sector by SEC SIC code (free and deterministic; GICS is not free):

| Sector | SIC codes |
|---|---|
| Tech | 3570-3579 (computer equipment), 3661-3663 (communications equipment), 3670-3679 (semiconductors and electronic components), 7370-7379 (software and IT services) |
| Banks | 6021 (national commercial banks), 6022 (state commercial banks) |
| Staples | 2000-2099 (food and beverages), 2100-2199 (tobacco), 2840-2844 (household and personal products), 5411 (grocery stores) |

- Staples side effects of SIC (accepted, no name added or removed by hand): Walmart, Costco, Target, Dollar General (5331), Sysco (5140) and Kimberly-Clark (2670) are out; Ecolab is in.
- Known side effects of SIC: Amazon (5961) and Tesla (3711) are not tech. Visa and Mastercard (7389) are not tech. Goldman Sachs and Morgan Stanley (6211, broker-dealers) are not banks. Alphabet and Meta (7370) are tech.
- Eligibility: listed on NYSE or Nasdaq; files 10-K (foreign 20-F filers are excluded); has a 10-K filed on or before the decision date that also reports the prior fiscal year (needed for revenue growth).
- Ranking: market cap on the decision date = shares outstanding from the latest filing filed on or before the decision date: cover page (`dei:EntityCommonStockSharesOutstanding`, summed over classes), else `us-gaap:CommonStockSharesOutstanding`, else `us-gaap:WeightedAverageNumberOfSharesOutstandingBasic` (multi-class filers such as Alphabet and Meta only appear through the fallbacks, because the SEC API omits per-class cover facts). The source used is recorded in the CSV x closing price on the decision date (yfinance, split-corrected). Multi-class companies use one class's price: an approximation.
- The list is frozen and committed at `data/universe/<sector>.csv`. It is the only committed file under `data/`.
- Known limitation (kept from SCOPE section 4): selecting the largest names adds mild survivorship and winner bias.
- Share-count rule (all sectors): a source is skipped if its latest value is zero or its latest filing was filed more than 456 days (about 15 months) before the date; the next source is tried. A fourth source is the cover-page `dei:EntityCommonStockSharesOutstanding` read from the 10-K's own inline XBRL instance (`<name>_htm.xml` found via the filing `index.json`), summed over share classes; the CSV `shares_source` records `10-K cover (instance)` when it is used. Order: companyfacts dei, then `CommonStockSharesOutstanding`, then the weighted average, then the 10-K cover. TAP, EL, MKC, HRL, SAM, TR and UTZ end up on the weighted average (a period average, accepted as an approximation: TAP is 208.8M vs 192.7M on its cover; moving the cover earlier would reorder the frozen banks list). This fixes companyfacts gaps (for example Molson Coors, whose only dei value is 0 from 2010).

### Staples (floor rule)

- Every staples company with a market cap of at least $1bn on the decision date. No fixed N and no pre-screen.
- Candidates (survivorship): every company that reported us-gaap `Assets` in 2024 (SEC frames `CY2024Q1I` to `CY2024Q4I`), not today's ticker list, so companies delisted after the decision date are still seen.
- Eligibility: a 10-K filed on or before the decision date, and an exchange listing (`NYSE` or `NASDAQ`) on that 10-K's cover (`dei:SecurityExchangeName`). Ticker: today's ticker if the CIK is still listed, else the first NYSE/Nasdaq cover symbol without whitespace, `.` turned into `-`. A ticker that today belongs to another CIK is rejected (reused ticker).
- Delisted companies are included if Yahoo has a price for them; otherwise they are listed in `data/universe/staples_excluded.csv` with the reason (`no Yahoo price`, `criteria`, `shares`, `ticker` or `cover`) and the public float as a size hint. A listed company whose price lookup fails stops the run instead of being dropped.
- The excluded file is part of the pre-registration record: later plans must not re-add excluded companies.

### Frozen universes

Selected by `scripts/select_universe.py <sector> --write` on 2025-03-31 market caps, ranked by market cap:

| Sector | Companies |
|---|---|
| Tech | AAPL, MSFT, NVDA, GOOGL, META, AVGO, ORCL, CRM, CSCO, IBM, PLTR, INTU, QCOM, AMD, NOW |
| Banks | JPM, BAC, WFC, C, PNC, COF, USB, BNY, TFC, MTB, FCNCA, FITB, STT, HBAN, RF |
| Staples | floor rule, see `data/universe/staples.csv` (selected) and `data/universe/staples_excluded.csv` (excluded with reason) |

- 15th place in tech is close: NOW 164.0bn vs TXN 163.6bn and ADBE 163.5bn. Small share-count or price differences could swap it; the rule is applied as written.

## Quantitative criteria (tech)

All are benefit-type (higher is better). The tag lists are fallbacks: the first tag that has a matching fact wins, and the tag used is recorded.

| Criterion | Formula | XBRL tags (us-gaap, in fallback order) |
|---|---|---|
| `revenue_growth` | Rev(FY) / Rev(FY-1) - 1 | Revenue: `RevenueFromContractWithCustomerExcludingAssessedTax`, `Revenues`, `SalesRevenueNet` |
| `net_margin` | NetIncome / Rev | `NetIncomeLoss` (the only income tag all 15 tech companies report: IBM has no `OperatingIncomeLoss`, Oracle no pre-tax income tag) |
| `fcf_margin` | (OperatingCashFlow - Capex) / Rev | `NetCashProvidedByUsedInOperatingActivities`; capex: `PaymentsToAcquirePropertyPlantAndEquipment`, `PaymentsToAcquireProductiveAssets` |
| `rd_intensity` | R&D / Rev | `ResearchAndDevelopmentExpense`, `ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost`, `ResearchAndDevelopmentExpenseSoftwareExcludingAcquiredInProcessCost` |

- Annual fact = duration between 350 and 380 days (52/53-week years) with `end` equal to the 10-K's fiscal period end. FY-1 = the same tags, same 10-K accession, `end` 350-380 days earlier.
- If no tag matches, ingest fails loudly with the company, criterion and tags tried. It never fills in zero.

## Quantitative criteria (staples)

Same conventions as tech (benefit-type, first matching tag wins, annual facts 350-380 days, fail loudly). Revenue, net margin and FCF margin use the tech formulas; R&D is not used.

| Criterion | Formula | XBRL tags (us-gaap, in fallback order) |
|---|---|---|
| `revenue_growth` | Rev(FY) / Rev(FY-1) - 1 | `RevenueFromContractWithCustomerExcludingAssessedTax`, `Revenues`, `SalesRevenueNet`, `RevenueFromContractWithCustomerIncludingAssessedTax` |
| `net_margin` | NetIncome / Rev | `NetIncomeLoss`, `ProfitLoss` |
| `fcf_margin` | (OperatingCashFlow - Capex) / Rev | `NetCashProvidedByUsedInOperatingActivities`, then `NetCashProvidedByUsedInOperatingActivitiesContinuingOperations`; capex: `PaymentsToAcquirePropertyPlantAndEquipment`, `PaymentsToAcquireProductiveAssets`, then `PaymentsToAcquireOtherPropertyPlantAndEquipment`, `PaymentsToAcquireOtherProductiveAssets` |
| `roa` | NetIncome / Assets | `Assets`: instant fact (no `start`), same 10-K accession, `end` equal to the 10-K period end |

- `RevenueFromContractWithCustomerIncludingAssessedTax`, `ProfitLoss`, `NetCashProvidedByUsedInOperatingActivitiesContinuingOperations`, `PaymentsToAcquireOtherPropertyPlantAndEquipment` and `PaymentsToAcquireOtherProductiveAssets` are appended last in their fallback lists, so the tech values are unchanged (checked before and after on all 15 tech companies).
- `roa` replaces `rd_intensity`, which most staples do not report.

## Quantitative criteria (banks)

Status: OPEN. SCOPE lists CET1, NIM, efficiency ratio and NPL ratio. CET1 and NPL are not reliably tagged in us-gaap XBRL, so the bank criteria need their own spike before coding.

## Backtest

- Rule: the TOPSIS score from the graph on real data (decision date 2025-03-31, quantitative criteria only) against each company's total return from the 2025-03-31 close to the 2026-03-31 close (yfinance `Adj Close`, dividends reinvested).
- Primary test, fixed before the result was seen: CRITIC weights (the graph default), Kendall tau, two-sided (D12). Spearman rho is secondary. Entropy and equal weights are sensitivity checks, not extra chances to find an effect.
- n = 15: only |rho| > ~0.51 is distinguishable from chance at p < 0.05.
- The risk-adjusted measure (SCOPE section 5) is not defined yet and is deferred.
- Look-ahead guard: only `src/maid/backtest.py` and `scripts/backtest.py` read post-decision prices. The graph never imports `maid.prices` (tested).
- Run: `python scripts/backtest.py`. Output is printed only and stays local.
- First result (2026-11-02): no association (primary Kendall tau +0.05, p = 0.85), with very low power at n = 15. See [backtest-quant-only-results.md](../research/backtest-quant-only-results.md).

### Backtest #2: consumer staples (pre-registered 2026-11-03, before any staples return was computed)

- Universe: the 61 companies in `data/universe/staples.csv` (plan 025, D19). No company is added or removed; the 19
  in `staples_excluded.csv` stay out.
- **Deviation (2026-11-03, decided before any staples return or statistic was seen):** Kenvue (KVUE) has no price
  history on Yahoo any more (0 rows for the window; KMB and MSFT fetched fine in the same call; probably delisted
  after Kimberly-Clark's acquisition, not verified). Kenvue stays in the universe and in the ranking, so the CRITIC
  weights and labels are as pre-registered, but it has no outcome and is left out of the correlation: **n = 60**.
  This is the same "no Yahoo price, no place in the test" rule as the 19 excluded companies, applied after the freeze.
  Owner decision.
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
- Run: `python scripts/backtest.py --sector staples --no-outcome KVUE`.
- Result (2026-11-03): no association (primary Kendall tau −0.10, p = 0.28, n = 60). See [backtest-staples-results.md](../research/backtest-staples-results.md).

## Local-only data

Downloads and derived files live under `data/cache/` and `data/raw/` (both gitignored) and are never committed or pushed (owner rule). Only `data/universe/*.csv` is committed. Tests use small hand-made JSON fixtures under `tests/fixtures/`, never real downloads, and never touch the network.
