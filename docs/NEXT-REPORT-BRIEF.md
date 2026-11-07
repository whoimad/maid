# Brief: report for the next step (written for Claude on claude.ai)

You are picking up the MAID project in the browser. This repo is **try #1**: an experiment that tested one assumption
and found it wrong. Your job is to write **a simple report, in French**, that sets up what to do next. Do not write
code.

Repo: https://github.com/whoimad/maid, branch **`integration/prototype`** (`main` is behind and does not have this
brief or the post-mortem).

## 1. Read first (in this order)
1. `docs/research/try1-postmortem.md`: the conclusion of try #1. **Start here; it is the most important file.**
2. `docs/SCOPE.md`: the original research question and constraints.
3. `docs/research/backtest-quant-only-results.md` and `docs/research/backtest-staples-results.md`: the two null
   results (tech n=15, Kendall tau +0.05; staples n=60, tau −0.10, p=0.28).
4. `docs/architecture/decisions.md`: decisions D1–D21 and why they were made. D4, D9, D15 and D21 matter most.
5. `docs/research/README.md` and the notes it lists: earlier desk research. **Warning:** it was made from abstracts
   only; treat every claim there as unverified until you check the original.
6. Optional: `docs/WALKTHROUGH.md`, `docs/architecture/overview.md` for how the pipeline works.

## 2. What we learned (summary of the post-mortem)
- Predicting which company will have the best return next year from public 10-K ratios and LLM scores was the wrong
  question. Markets already price public figures; professionals mostly fail at it; our tests had little power
  (n=15, then n=60) and only one 12-month window.
- MCDM was used without a decision-maker: data-driven weights (CRITIC, entropy) measure dispersion, not importance.
- The local 7B LLM gave 1–9 opinion scores that clustered at 7 and had no ground truth to check them against.
- We built a lot of infrastructure before testing whether any criterion carried signal.
- Worth keeping: LLMs never rank; point-in-time data; anonymized names; tests written down before running them;
  honest reporting of null results.
- Leading idea for try #2: use MCDM to assess **risk** (volatility, drawdown, distress), which is far more
  predictable than returns, and test whether 10-K information adds anything **beyond trailing volatility**. The
  post-mortem explains this baseline in detail.

## 3. The report to write (in French)
Keep it simple and readable: about 5–8 pages of Markdown, plain French, short sections, no jargon without a one-line
explanation.

Structure:
1. **La question.** Start with the research question for try #2. Restate try #1's question in one paragraph, say
   why it was wrong, then propose the new question. Do not just copy the post-mortem's suggestion: weigh it against
   the alternatives in section 4 below and recommend one, with reasons.
2. **État de l'art.** What the literature actually establishes. Cover at least the topics in section 5. For each:
   what is known, the key references, and what it means for our question.
3. **Ce que l'essai n°1 nous a appris.** The mistakes and what we keep, linked to the repo files as evidence.
4. **Proposition pour l'essai n°2.** The question, the outcome measure (defined before any data is looked at), the
   baseline to beat, the companies, what the LLM does (fact extraction, not opinions), how MCDM weights are set,
   and how the test is judged (including a power estimate, or what is needed to compute one).
5. **Risques et questions ouvertes.** What could make try #2 fail too, and what the owner must decide.
6. **Références.** Every source with a link.

## 4. Candidate questions to weigh
- **A. Risk beyond the baseline:** does information extracted from 10-K text add to a ratio-only model in ranking
  companies by next-year downside risk, beyond trailing volatility?
- **B. Decision support, no market outcome:** can a local LLM extract checkable risk facts from 10-Ks (customer
  concentration, going-concern language, refinancing needs, ...) accurately enough, measured against human labels,
  for a transparent MCDM risk screen?
- **C. Something else** you find better supported by the literature. Say why.

## 5. State-of-the-art topics (starting points, verify each one)
- Return predictability and market efficiency: Welch & Goyal (2008); SPIVA scorecards; the "factor zoo" and
  replication problems (e.g. Harvey, Liu & Zhu 2016).
- Volatility forecasting and persistence: GARCH, HAR models; how strong trailing volatility is as a predictor.
- Distress and default prediction: Altman Z-score (1968), Ohlson (1980), Campbell, Hilscher & Szilagyi (2008).
- 10-K text and risk: Kogan et al. (2009, MD&A text predicts volatility); Loughran & McDonald (financial word
  lists); Cohen, Malloy & Nguyen ("Lazy Prices", 10-K changes).
- LLMs in finance: Lopez-Lira & Tang (ChatGPT and stock returns); Glasserman & Lin (look-ahead bias and
  anonymization); what small local models can and cannot do.
- LLM-as-judge reliability: central tendency, calibration against human labels; extraction vs scoring.
- MCDM for risk and credit assessment: TOPSIS and related methods in credit risk; subjective (AHP) vs objective
  (CRITIC, entropy) weights, and when each is appropriate.

## 6. How to research
- Use research mode / sub-agents and search widely; we want **accurate** information, not plausible-sounding text.
- Prefer primary sources: the paper itself, the journal page, the official report. Give a link for every claim.
- If you could only read an abstract or a summary, say so next to the claim. If you cannot verify something, mark it
  **NON VÉRIFIÉ** instead of guessing. Never invent numbers, authors or years.
- Keep separate: what the literature establishes, what our own experiment found (cite the repo file), and your own
  opinion.

## 7. Constraints that still hold (do not propose breaking them)
- **LLMs never rank.** They extract (and maybe score) with cited evidence; a deterministic MCDM engine ranks.
- **Local models only.** No paid API. One local model (Ollama, ~7B, 8 GB GPU), so agents run one after another.
- **No look-ahead.** A fixed decision date; only information public on or before it. Company names anonymized in
  prompts.
- Downloaded SEC / price data stays local; the report must not contain per-company returns.
- This is research and learning, not investment advice.

## 8. Tone
The owner sees try #1 as a normal step: an assumption tested and found wrong. The report should read the same way:
honest about the failure, without drama, and focused on a better question.
