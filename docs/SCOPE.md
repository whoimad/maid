# MAID: Multi-Agent Investment Decision-making — Scope (v0.1, draft)

Status: exploratory prototype, solo. Goal: a working, fundamentally sound pipeline, not a perfect one.
Lessons carry into a later, cleaner project.

## 1. Research question
Can LLM agents convert qualitative company information into MCDM-ready numeric scores such that a
deterministic MCDM ranking is (a) stable, (b) robust to method/weight choice, and (c) informative
about subsequent performance?

## 2. Core principle
**LLMs never rank.** Agents extract and score; a deterministic MCDM engine computes weights and ranks.
Every LLM score carries cited evidence and is reviewable by the human.

## 3. Time frame (look-ahead control)
- Decision date: **2024-12-31**. Agents see only information available on or before this date
  (FY2024 10-K filings, prices up to the date).
- Evaluation window: calendar 2025.
- Company names are anonymized (Company A, B, …) in scoring prompts to reduce memorized knowledge.
- Open item: verify DeepSeek model knowledge cutoff vs. decision date; record it in `docs/MODEL.md`.
  If the cutoff is later than the decision date, report this as a known limitation.

## 4. Universe
- Phase 1: US **technology** sector, 10–15 companies. Phase 2: US **banks**, 10–15 companies.
  Phases use different criteria sets (sector-specific ratios), same pipeline.
- Selection rule: N largest by market cap within the sector at 2024-12-31, list frozen and committed.
- Known limitation: large-cap selection has mild survivorship/winner bias; documented, not fixed.

## 5. Pipeline (LangGraph)
1. Ingest: SEC EDGAR (10-K text, XBRL facts), prices via yfinance. Cached locally.
2. Quantitative criteria: computed directly from XBRL (no LLM).
3. Qualitative criteria: one scorer agent per criterion, rubric-based, structured output
   (score 1–9 + cited evidence), repeated K times for stability.
4. **Human checkpoint** (`interrupt`): review scores/evidence, override with reason.
5. MCDM engine: weights by **entropy and CRITIC (data-driven only)**; ranking by TOPSIS plus
   one outranking method (PROMETHEE II or VIKOR).
6. Sensitivity and robustness analysis.
7. Report: summary of ranking, evidence, and caveats; human reviews.

## 6. Evaluation
- Backtest: Spearman correlation of ranks with 2025 total return and a risk-adjusted measure.
  Reported as correlation, not "accuracy"; with 10–15 names it is noisy.
- Method agreement: Spearman/Kendall between TOPSIS, PROMETHEE/VIKOR, and weighting schemes.
- LLM stability: score variance across K repeated runs.
- Ablation: quantitative-only vs. quantitative + LLM-derived criteria.
- Baselines: equal-weight ranking; simple single-metric rankings.

## 7. Non-goals
Trading advice, portfolio construction, real-time data, multi-sector joint ranking,
human-set weights (AHP) in this version.

## 8. Constraints
- Budget: Claude Pro plan; DeepSeek API for the pipeline. Cache everything, small test universe first.
- Workflow: issue per component, branch per issue, small PRs into `main`, conventional commits.

## 9. Open questions / spikes
- [ ] DeepSeek model choice and verified knowledge cutoff
- [ ] Final criteria list for tech (quantitative vs. qualitative split) and rubric drafts
- [ ] Criteria list for banks (e.g. CET1, NIM, efficiency ratio, NPL ratio instead of leverage/FCF)
- [ ] Risk-adjusted metric definition for the backtest
- [ ] Entropy vs. CRITIC behavior on only ~12 alternatives (small-sample weight stability)
