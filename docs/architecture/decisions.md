# Design decisions and trade-offs

Format: decision, alternatives, why, cost. Written so each can be defended in an interview. Status: OPEN marks decisions not yet made.

## D1. LLMs score, MCDM ranks
- **Alternatives:** LLM picks the best stocks directly (as in TradingAgents / FinMem style systems per our desk research, abstracts only); LLM does everything including weights.
- **Why:** an auditable, reproducible ranking and a clear place to measure bias and noise.
- **Cost:** the LLM's judgment is reduced to 1-9 scores, losing nuance; the rubric design carries a lot of weight.

## D2. Single sector per run, sector-specific criteria
- **Alternatives:** rank tech and banks together.
- **Why:** ratios do not mean the same thing across sectors (bank leverage vs tech cash flow).
- **Cost:** two criteria sets to design; no cross-sector comparison.

## D3. Decision date 2024-12-31, backtest on 2025, anonymized company names
- **Alternatives:** only trust a model with an earlier cutoff; no look-ahead control.
- **Why:** gives a real out-of-sample test. DeepSeek publishes no cutoff, so it is likely later than the decision date; we cannot rely on the model's ignorance.
- **Mitigation:** anonymize names, keep numbers, probe for recalled post-date facts, ablate with an older open-weight model.
- **Cost:** anonymization may reduce scoring quality; the leak cannot be fully excluded and is stated as a limitation.

## D4. Data-driven weights (entropy, CRITIC), no AHP in v1
- **Alternatives:** AHP with my own pairwise judgments; fixed equal weights.
- **Why:** simplicity and less subjective input. **Cost:** noisy weights at n~12 (see spike #6) and no expert knowledge. Mitigated by perturbation and rank intervals. Entropy variant (min-max vs column-sum) is an open sub-decision; spike #6 compares them.

## D5. Report rank intervals, not just a rank
- **Why:** with 12 alternatives and noisy weights, a single rank overstates certainty.
- **Cost:** harder to read than a leaderboard.

## D6. LangGraph for orchestration
- **Alternatives:** plain Python functions; another agent framework.
- **Why:** built-in checkpointing and `interrupt` give the human-in-the-loop step cheaply, and the graph structure mirrors the architecture diagram.
- **Cost:** a framework dependency for a pipeline that is mostly linear.

## D7. Cache everything on disk
- **Why:** limited budget; filings, prices and LLM calls must never be paid for twice, and caching makes runs reproducible.
- **Cost:** stale cache risk; cache keys must include model and prompt version.

## D8. Rankers: SAW and TOPSIS now; PROMETHEE II next; VIKOR later
- **Alternatives:** VIKOR, PROMETHEE II, ELECTRE, letting the LLM rank (rejected by D1).
- **Why:** SAW is the transparent baseline and was the more stable ranker under weight noise in spike #6 ([weight-stability-results.md](../research/weight-stability-results.md)); comparative studies report SAW/WSM highly correlated with other methods (Mulliner et al. 2016, WSM-TOPSIS ≈ 0.86) [abstract-only, [mcdm-noise.md](../research/mcdm-noise.md)]. TOPSIS adds a distance-to-ideal view. PROMETHEE II before VIKOR because VIKOR's output is a compromise set rather than a strict order (UNVERIFIED in mcdm-noise.md).
- **Cost:** both are compensatory (a high score on one criterion offsets a low one); TOPSIS was less stable under weight noise in spike #6; no outranking method yet.
- **Status:** SAW/TOPSIS decided; second family OPEN.
- **Revisit if:** TOPSIS and SAW disagree on the top 3 on real data.

## D9. LLM scores: integer 1-9 with an evidence quote, K samples aggregated
- **Alternatives:** continuous 0-100; pairwise comparisons by the LLM; yes/no checklists.
- **Why:** anchored ordinal levels are easier to write rubrics for and to review; an odd scale has a neutral midpoint; the schema enforces range and evidence (`src/maid/state.py`: `score: int = Field(ge=1, le=9)`, `evidence: str`). Research suggests averaging several sampled scores tracks humans better than one greedy score (Yamauchi et al. 2025) [abstract-only, [llm-agents-finance.md](../research/llm-agents-finance.md)].
- **Cost:** coarse; MCDM treats an ordinal score as interval data.
- **Status:** K (research suggests ≥5) and the aggregation rule (median vs mean) are OPEN.
- **Revisit if:** score variance across K runs is larger than one scale step for most criteria.

## D10. All criteria benefit-type (higher is better)
- **Alternatives:** support cost-type criteria inside each method.
- **Why:** one code path for every weighting/ranking function, fewer sign bugs; documented in `src/maid/mcdm/weights.py` module docstring ("flip cost criteria before calling").
- **Cost:** how a cost criterion is flipped (negation vs reciprocal) is itself a choice that changes min-max results; it must be recorded per criterion when criteria are defined (issue #3).
- **Status:** decided.

## D11. Normalization: min-max for SAW, CRITIC and entropy (default); vector for TOPSIS
- **Alternatives:** z-score; column-sum (textbook entropy); log.
- **Why:** each is the standard pairing for its method; min-max maps every criterion to [0, 1].
- **Cost:** min-max depends on the sample's extremes, so adding/removing a company can change weights and ranks ([mcdm.md](mcdm.md) Known limitations); normalization choice changes rankings in published reanalyses [abstract-only, [mcdm-noise.md](../research/mcdm-noise.md)].
- **Status:** entropy variant (min-max vs sum) OPEN; spike #6 compares them.

## D12. Kendall tau as the primary ranking-comparison metric; Spearman secondary
- **Alternatives:** Spearman only; rank-biased overlap (RBO, top-weighted).
- **Why:** tau counts agreeing vs disagreeing pairs, which is easy to explain and handles ties; recommended for small n in [mcdm-noise.md](../research/mcdm-noise.md) §2 item 6; SCOPE §6.
- **Cost:** not top-weighted (a swap at rank 1 counts the same as at rank 11); tau values look lower than Spearman for the same data, which can confuse readers.
- **Revisit if:** the report cares mostly about the top 3 (then add RBO).

## D13. Weight uncertainty: bootstrap and Dirichlet perturbation, reported separately
- **Alternatives:** perturb each weight by ±x% and renormalize; uniform weights on the simplex (classic SMAA with no weight information); one combined simulation.
- **Why:** bootstrap measures estimation noise from having only ~12 companies; Dirichlet(concentration × w) stays on the simplex, is centred on the point weights and has one spread parameter. Keeping them separate shows which kind of uncertainty drives a rank interval ([robustness.md](robustness.md)).
- **Cost:** bootstrap understates uncertainty at n≈12 (it only resamples observed companies); `concentration` (placeholder 100) is hand-set.
- **Status:** implemented as a library; calibration OPEN.

## D14. Model: DeepSeek (`deepseek-flash`) for the pipeline
- **Alternatives:** Claude or GPT models; an older open-weight model with an earlier cutoff.
- **Why:** budget (SCOPE §8); cheapest option with JSON output, tool calls and a 1M context ([model-cutoff.md](../research/model-cutoff.md) §5).
- **Cost:** no published knowledge cutoff, likely after the 2024-12-31 decision date (look-ahead risk, D3); the alias was re-pointed on 2026-10-17, so the dated version must be pinned and logged per run (not done yet).
- **Status:** decided for v1; older-model ablation OPEN (SCOPE §9).

## D15. No trained predictive (ML) model
- **Alternatives:** train a regressor/classifier from features to 2025 returns.
- **Why:** ~12 companies per sector-year is not a training set; the research question is whether LLM-made scores give a stable, robust, informative MCDM ranking, not return prediction (SCOPE §1); trading advice is a non-goal (SCOPE §7).
- **Cost:** no learned weighting; the backtest only checks association, and with n=12 only a strong one (|rho| > ~0.58) is distinguishable from chance.
