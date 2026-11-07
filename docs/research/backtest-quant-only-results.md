# Backtest #1: the quant-only ranking does not predict 12-month returns (a null result)

Reproduce: `python scripts/backtest.py` (needs the local SEC cache and yfinance). Plans 023 and 024 built it, and it
was run on 2026-11-02. This note gives only the summary statistics; the per-company table is derived from price
data, so it stays local (owner rule). Rerun the script to see it.

## Question and design (fixed before the result was seen)

SCOPE §1 asks whether the MCDM ranking is (a) stable, (b) robust to method and weight choice, and (c) informative
about subsequent performance. This backtest is the first test of (c), with **no LLM involved**. It is the
quant-only baseline.

- **Companies:** 15 US tech companies. Chosen by a fixed rule, not by hand: SIC codes in the tech sector, listed on
  NYSE or Nasdaq, files a 10-K, then the top 15 by market cap on 2025-03-31 ([data.md](../architecture/data.md),
  D17).
- **Inputs:** four point-in-time criteria from the latest 10-K filed on or before 2025-03-31: revenue growth, net
  margin (D18), FCF margin, R&D intensity.
- **Ranking:** CRITIC weights, then TOPSIS (the graph defaults).
- **Outcome:** total return with dividends reinvested, from the 2025-03-31 close to the 2026-03-31 close.
- **Primary test:** Kendall tau between TOPSIS score and return, two-sided (D12). Spearman rho is secondary.
  Entropy and equal weights are sensitivity checks only.
- **Look-ahead guard:** only the backtest reads post-decision prices. A test checks that the graph never imports
  the price module.

## Result

| Weighting | Kendall tau | p | Spearman rho | p |
|---|---|---|---|---|
| **CRITIC (primary)** | +0.048 | 0.85 | +0.061 | 0.83 |
| Entropy | +0.086 | 0.70 | +0.139 | 0.62 |
| Equal | +0.067 | 0.77 | +0.082 | 0.77 |

No association. All three weightings give the same answer, so the null result does not depend on the weighting
scheme. The best performers of the year are spread across the whole ranking. One example: the 7th- and 10th-ranked
companies had two of the three highest returns.

## What this does and does not show

**The test was too weak to show much either way.** A seeded simulation drew bivariate-normal samples at n = 15 and
ran a Kendall test at alpha = 0.05 (4000 trials per row):

| True correlation | Chance the test detects it |
|---|---|
| 0.1 | 6% |
| 0.2 | 9% |
| 0.3 | 15% |
| 0.5 | 42% |

So "no significant correlation" is the expected outcome even if the ranking carried a real, modest signal. The
result rules out only a strong effect. It cannot tell "no signal" from "small signal".

**One period is one draw.** This is a single 12-month window in one sector. Returns in that window were driven by
themes such as AI-related demand, which shift the whole cross-section together. A different year could give a
different sign. One cross-section can't separate the method from the market regime.

**Data-driven weights measure the matrix, not relevance.** CRITIC gave R&D intensity the largest weight (about
0.42) because that column varies most and correlates least with the others. CRITIC and entropy reward
*information in the matrix*, not *predictive relevance*. That is a property of the method (D4), not a bug. But it
means "objective weights" should not be read as "weights that matter for returns". Equal weights gave the same null
result, so this is not the whole explanation.

**The metric is not the problem.** Kendall/Spearman asks exactly "does a higher rank go with a higher return?",
which is what (c) means. Switching metrics after seeing the result would be a forking path. Any new metric must be
fixed before its own run. See the options below.

**Prior expectation.** Ratios from a 10-K that is already public on the decision date are known to the market. For
the largest, most-followed companies, little predictive power is expected. A null here is consistent with that and
is not evidence that the pipeline is broken.

## Options for the next evaluation (decide and fix before running)

1. **More observations: repeat the same rule at several decision dates.** For example, every 31 March from about
   2015 to 2025, which gives about 10 cross-sections × 15 companies. Average the per-year Kendall tau and test it
   across years. Rough power at about 150 observations: 23% for rho = 0.1 and 69% for rho = 0.2 (Fisher
   approximation, assuming independent observations). This tests the *method* instead of one year. Cost: universe
   selection and XBRL extraction per date (the code is already date-parameterized), plus more price data.
2. **Outcomes that match what the criteria claim.** A quality-style ranking is more plausibly linked to lower risk
   (volatility, drawdown) or to future fundamentals (next-year revenue growth and margins from the next 10-K) than
   to raw return. Future fundamentals are much less noisy than prices. Excess return over the sector average removes
   the common market move.
3. **Focus on (a) and (b), which need no returns.** These are stability under resampling and noise, already measured
   by the rank intervals (D13, D16), and agreement between LLM scores and human review. These parts of the research
   question can be answered well at n = 15.

## Would LLM scores do better?

Possibly, but this design could not show it, and a "win" would be suspect:
- **Power:** the same n = 15, one-period test has the same low power. An LLM run that also gives a null tells us
  little.
- **Look-ahead leakage:** the scoring model was very likely trained on text written after 2025-03-31. It may "know"
  which companies did well in 2025. Anonymization reduces this but cannot exclude it (D3). Prior work reports that
  LLMs can recall economic data from their training period (Lopez-Lira, Tang, Zhu 2025; see
  [llm-agents-finance.md](llm-agents-finance.md), abstract-only, UNVERIFIED). So a better LLM result needs leakage
  controls first: recall probes, and an older-cutoff model as an ablation.
- **What LLMs plausibly add:** information that is not in the four ratios, for example strategy, risk disclosure
  and competitive position from the 10-K text. That is information the market also had, so the prior is still a
  small effect.

Conclusion for the project: compare LLM-scored rankings against this baseline, but only inside an evaluation with
enough power (option 1) and leakage controls. The quant-only baseline stays as the reference.
