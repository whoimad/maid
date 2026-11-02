# Design decisions and trade-offs

Format: decision, alternatives, why, cost. Written so each can be defended in an interview.

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
- **Why:** simplicity and less subjective input. **Cost:** noisy weights at n~12 (see spike #6) and no expert knowledge. Mitigated by perturbation and rank intervals.

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
