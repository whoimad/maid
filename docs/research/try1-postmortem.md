# MAID try #1: post-mortem

*Written 2026-11-06, after the tech and staples backtests and the LLM pilot. Try #1 = everything in this repo up to this note.*

Short version: the try failed, mostly because it tried to predict next-year returns. One correction: "returns can't
be predicted at all" is a bit too strong. Some weak cross-sectional effects (value, quality, momentum) do exist. But
they are small and unstable, and they only show up across thousands of company-years. Our test design could never
have detected them.

## The systematic errors, most fundamental first

### 1. We asked the wrong question, and our own docs said so
Memo §5 already lists the reason the test would fail: public 10-K figures for heavily followed companies are already
in the price. D15 says we can't train a predictor on about 12 companies. We then made "rank vs. next-year return" the
main test anyway. Two things outside the project agree:
- Welch & Goyal (2008) found that none of the standard predictors beat the historical mean out of sample.
- SPIVA scorecards show that roughly 85–90% of professional active managers trail their index over 10–15 years.

Expecting four ratios plus a 7B model to beat that was never a fair hypothesis to test.

### 2. The test could not have succeeded even if the idea was right
- **Too few companies.** With n=15 we had a 9% chance of detecting a modest effect (rho 0.2). With n=60 it was about
  31%.
- **One draw.** We tested a single 12-month window, and it started the day before the April 2025 tariff shock. Tech
  was in the middle of an AI rally that moved stocks from −34% to +98%.

We spent the effort making one draw clean (pre-registration, point-in-time data) when the bigger problem was that one
draw can't answer the question.

### 3. We used MCDM without a decision-maker
MCDM exists to turn a decision-maker's stated preferences into a ranking. We removed the preferences on purpose (D4:
no AHP, data-driven weights only). CRITIC and entropy weight a criterion by how much it varies across companies, not
by how much it matters. That's how R&D intensity got 42% of the weight. Without a preference model, TOPSIS just
produces an arbitrary index, and judging an arbitrary index on returns doesn't tell you anything about MCDM.

### 4. The LLM criteria measure how the report is written, not how the company is doing
"Strategy clarity" and "pricing power" judged from 10-K prose mostly score legal boilerplate and how well the report
is written. The pilot showed it:
- 19 of 26 valid cells scored exactly 7.
- 99 of 228 attempts were invalid.
- One score of 8 for pricing power quoted a gross-margin *decrease*.

That clustering around 7 is a documented behaviour of LLM judges (central tendency bias), not just a bug in our
prompt. There's a deeper problem too: we had no ground truth for these scores. Nothing told us whether a 7 was right,
so the only check left was the noisy return test.

### 5. We built the system before testing the idea
That's 144 commits and 33 plans: LangGraph, three kinds of rank intervals, a seven-tab GUI, sequential agents, and a
demo plan for a professor. All of it was built before any single criterion was shown to carry signal. The engineering
got ahead of the question.

## What was done right and is worth keeping
- The rule that LLMs never rank
- Point-in-time data
- Anonymized company names (Glasserman & Lin found anonymizing headlines actually *improved* GPT's sentiment signal)
- Writing the test down before running it
- Reporting the null results honestly

These are a sound method. The problem was what we pointed it at.

## The risk idea holds up better than return prediction
Risk is much more predictable than returns:
- **Volatility persists.** That's why it can be forecast at all.
- **Distress can be modelled.** Campbell, Hilscher & Szilagyi (2008) predict corporate failure from leverage,
  profitability, cash and volatility. Altman's Z-score is the classic accounting-ratio version.
- **There's a direct precedent for our pipeline.** Kogan et al. (2009) used 10-K MD&A text to predict next-year
  *volatility* rather than returns. Their reasoning is ours: 10-Ks rarely move prices, but they do describe risk.
- **MCDM is already used this way.** TOPSIS is common in credit-risk and distress assessment, where a decision-maker's
  risk preferences are a natural fit.

There are traps to avoid:
- **Trailing volatility is a hard baseline** (explained in detail below).
- **Define "risk" before looking at any data.** Candidates are realized volatility, maximum drawdown, a dividend cut,
  a rating downgrade, or a distress event. Large staples companies almost never fail, so we'd need the volatility or
  drawdown versions.
- **Let the LLM extract facts, not give opinions.** A 7B model is unreliable at "rate pricing power 1–9". It's much
  better at yes/no questions: "Does a customer account for more than 10% of revenue? Is there going-concern language?
  Is debt refinancing due within 12 months?" That removes the clustering around 7 and gives checkable ground truth.
- **Weights should come from a stated risk preference**, set by me or by AHP, not from CRITIC.

## Trailing volatility as the baseline, in detail

**What it means.** Trailing volatility is how much a stock's price moved over the past year: the standard deviation of
its daily returns, annualized. It is known on the decision date with no model at all, just last year's price chart.

**Why it is hard to beat.** Volatility persists. A stock that swung a lot last year usually swings a lot next year,
and a calm stock usually stays calm. The ranking "riskiest to safest" barely changes from year to year, because it
comes from things that don't change fast: the business model, size, leverage and how the stock is owned. In staples,
a large tobacco or beverage company will almost always be calmer than a small, fast-growing energy-drink brand. You
don't need a 10-K, an LLM or TOPSIS to know that. You only need last year's price history.

A market-wide shock, like the April 2025 tariffs, raises everyone's volatility at the same time. Because we rank
companies against each other, a shock like that mostly shifts the level, not the order. So the trailing-volatility
ranking should hold up even in a bad year. That is the opposite of returns, where the order reshuffles every year.
(This is the expected behaviour from the literature. On our 60 companies it still needs to be measured.)

**Why it matters for the test.** Suppose the MCDM risk ranking correlates strongly with next-year volatility, say
Kendall tau 0.5. That looks like a success, but it may not be. Our criteria (leverage, small size, thin margins,
volatile cash flow) are exactly the things that *cause* a stock to be volatile, so they also line up with *last*
year's volatility. The MCDM ranking could just be an indirect, noisier copy of trailing volatility. In that case all
the agents, rubrics and weights add nothing that the price chart didn't already say.

It's like a weather forecast. "Tomorrow will be like today" is right most of the time. A weather model is only
useful if it beats that, especially on the days when the weather changes.

**What the test should be.** The question is not "does our ranking predict risk?", but "does it add anything beyond
trailing volatility?":
1. Baseline: rank by trailing volatility and measure how well it predicts next-year volatility (or drawdown).
2. Ours: the MCDM risk ranking, with and without the LLM criteria.
3. The real test: does our ranking explain the part of next-year risk that trailing volatility misses? For example,
   does it still correlate with next-year volatility after the trailing-volatility effect is removed (partial
   correlation), or does a model with both beat the model with trailing volatility alone?

Where we could plausibly add something is the **changes**: companies whose risk is about to go up or down. A calm
company that just took on a lot of debt, lost its biggest customer, or flagged a refinancing problem in Item 1A will
not show it in its price history yet, but the 10-K says it. That is the gap the LLM extractions could fill.

**Honest caveat.** The extra effect beyond the baseline will be smaller than the raw correlation, so statistical power
becomes a problem again at n≈60. The power calculation must be done for this incremental test before running it.

## Suggested direction for try #2
Ask this: **"Does information extracted from 10-K text add to a ratio-only model in ranking companies by next-year
downside risk, beyond trailing volatility?"**
- It can be tested at n≈60, because risk outcomes vary much less randomly than returns (power still to check for the
  incremental test).
- It has published precedent (Kogan et al. 2009).
- It keeps the principles: LLMs extract, a transparent MCDM ranks, and the test is fixed in advance.

The other honest option is to drop market outcomes entirely and evaluate the system as decision support, by comparing
the LLM's extractions against human-labelled answers. That's a cleaner and smaller research question, but less
exciting.

## Sources
- Kogan et al. 2009, Predicting Risk from Financial Reports with Regression: https://preview.aclanthology.org/teach-a-man-to-fish/N09-1031
- Welch & Goyal, equity premium prediction: https://nber.org/papers/w10483
- SPIVA long-term summary: https://www.etf.com/sections/index-investor-corner/swedroe-spiva-survey-continues-passive-winning-streak
- Indexes outperform active managers long term: https://www.planadviser.com/indexes-outperform-active-managers-over-long-term/
- Glasserman & Lin, look-ahead bias in GPT sentiment: https://arxiv.org/abs/2309.17322
- Campbell, Hilscher & Szilagyi, In Search of Distress Risk: https://econpapers.repec.org/RePEc:bla:jfinan:v:63:y:2008:i:6:p:2899-2939
- Altman Z-score: https://en.wikipedia.org/wiki/Altman_Z-score
- Volatility forecastability: https://investordaily.com.au/analysis/40088-the-art-and-science-of-volatility-prediction
- Volatility clustering and predictability: https://arxiv.org/pdf/2605.19278
- Central tendency bias in LLM raters: https://arxiv.deeppaper.ai/papers/2605.16386v1
- LLM judge calibration: https://mlflow.org/articles/llm-judge-calibration/
- Fuzzy MCDM for credit ratings: https://ideas.repec.org/a/spr/annopr/v353y2025i1d10.1007_s10479-024-06183-2.html
- R-TOPSIS for bank credit risk: https://web1.pmf.ni.ac.rs/filomat-content/2016/30-15/30-15-18.pdf

Caveat: these sources were read through search summaries, not full papers. Read the originals before citing them in
a write-up.
