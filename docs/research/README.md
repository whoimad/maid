# Research notes

Desk research produced by AI subagents on 2026-11-02.

**Caveat: the agents read abstracts, search summaries and documentation pages, not the full papers.**
Claims are only as reliable as those snippets. Items marked UNVERIFIED have no checked source.
Before relying on a claim in the final write-up, read the original source and verify it.

- `mcdm-noise.md`: stability of weighting and ranking methods at small n (issue #6)
- `model-cutoff.md`: DeepSeek models, pricing, knowledge cutoffs (issue #2)
- `llm-agents-finance.md`: prior work, look-ahead bias, LLM scoring practice, LangGraph patterns

Results of our own runs (not desk research):
- `weight-stability-results.md`: spike #6, entropy vs CRITIC weight stability (synthetic)
- `backtest-quant-only-results.md`: backtest #1, quant-only ranking vs 12-month return: null result, power analysis, next options
- `backtest-staples-results.md`: backtest #2, 60 consumer-staples companies, pre-registered: null result (primary Kendall tau −0.10, p = 0.28)
