# Real data: sources, time rule, universe, criteria

This page is the spec that the ingest code (`src/maid/sec.py`, `src/maid/xbrl.py`, `src/maid/universe.py`, `src/maid/prices.py`) implements. Status: SEC quantitative extraction implemented (`xbrl.py`, `sec.py`, `scripts/fetch_sec.py`), universe selection (`universe.py`, `scripts/select_universe.py`) and the price layer (`prices.py`) implemented; not wired into the graph yet.

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

- Known side effects of SIC: Amazon (5961) and Tesla (3711) are not tech. Visa and Mastercard (7389) are not tech. Goldman Sachs and Morgan Stanley (6211, broker-dealers) are not banks. Alphabet and Meta (7370) are tech.
- Eligibility: listed on NYSE or Nasdaq; files 10-K (foreign 20-F filers are excluded); has a 10-K filed on or before the decision date that also reports the prior fiscal year (needed for revenue growth).
- Ranking: market cap on the decision date = shares outstanding (XBRL `dei:EntityCommonStockSharesOutstanding`, summed over share classes, from the latest filing filed on or before the decision date) x closing price on the decision date (yfinance, split-corrected). Multi-class companies use one class's price: an approximation.
- The list is frozen and committed at `data/universe/<sector>.csv`. It is the only committed file under `data/`.
- Known limitation (kept from SCOPE section 4): selecting the largest names adds mild survivorship and winner bias.

### Frozen universes

Not yet selected: run `python scripts/select_universe.py tech --write` and `... banks --write` with SEC_USER_AGENT set.

## Quantitative criteria (tech)

All are benefit-type (higher is better). The tag lists are fallbacks: the first tag that has a matching fact wins, and the tag used is recorded.

| Criterion | Formula | XBRL tags (us-gaap, in fallback order) |
|---|---|---|
| `revenue_growth` | Rev(FY) / Rev(FY-1) - 1 | Revenue: `RevenueFromContractWithCustomerExcludingAssessedTax`, `Revenues`, `SalesRevenueNet` |
| `operating_margin` | OperatingIncome / Rev | `OperatingIncomeLoss` |
| `fcf_margin` | (OperatingCashFlow - Capex) / Rev | `NetCashProvidedByUsedInOperatingActivities`; capex: `PaymentsToAcquirePropertyPlantAndEquipment`, `PaymentsToAcquireProductiveAssets` |
| `rd_intensity` | R&D / Rev | `ResearchAndDevelopmentExpense`, `ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost` |

- Annual fact = duration between 350 and 380 days (52/53-week years) with `end` equal to the 10-K's fiscal period end. FY-1 = the same tags, same 10-K accession, `end` 350-380 days earlier.
- If no tag matches, ingest fails loudly with the company, criterion and tags tried. It never fills in zero.

## Quantitative criteria (banks)

Status: OPEN. SCOPE lists CET1, NIM, efficiency ratio and NPL ratio. CET1 and NPL are not reliably tagged in us-gaap XBRL, so the bank criteria need their own spike before coding.

## Local-only data

Downloads and derived files live under `data/cache/` and `data/raw/` (both gitignored) and are never committed or pushed (owner rule). Only `data/universe/*.csv` is committed. Tests use small hand-made JSON fixtures under `tests/fixtures/`, never real downloads, and never touch the network.
