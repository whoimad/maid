# Model knowledge cutoff research (issue #2, SCOPE.md section 3)

Researched 2026-11-02. Decision date to beat: 2024-12-31. Anything without a URL or marked UNVERIFIED is not established.

## 1. Current DeepSeek API models
Source: https://api-docs.deepseek.com/quick_start/pricing (fetched 2026-11-02; summarized by a fetch tool, re-check the page before relying on exact prices).

| | deepseek-flash | deepseek-v4-pro |
|---|---|---|
| Version | DeepSeek-V4.1-Flash-1017 | DeepSeek-V4-Pro-0813 |
| Context / max output | 1M / 384K | 1M / 384K |
| JSON output | Yes | Yes |
| Function calling | Yes | Yes |
| Input, cache miss, $/1M (off-peak / peak) | 0.15 / 0.30 | 0.66 / 1.32 |
| Input, cache hit, $/1M | 0.003 / 0.006 | 0.022 / 0.044 |
| Output $/1M | 0.60 / 1.20 | 1.98 / 3.96 |

- Peak is 01:00-04:00 and 06:00-10:00 UTC, Mon-Fri; off-peak is half price (same page).
- Release history (https://api-docs.deepseek.com/updates): V3.2 aliases (`deepseek-chat`, `deepseek-reasoner`) from 2025-12-01; V4-Pro GA 2026-08-13; V4.1-Flash 2026-09-10; Flash-1017 replaced it 2026-10-17.
- Older API models (V3, R1, V3.1, V3.2) are NOT listed as current. The legacy names were scheduled for discontinuation on 2026-07-24 (same updates page).

## 2. Official knowledge cutoffs
- Neither the pricing page nor the updates page states any knowledge cutoff for any model (both URLs above).
- The Hugging Face card for DeepSeek-V3-0324 states no cutoff either (https://huggingface.co/deepseek-ai/DeepSeek-V3-0324). It does list the V3 tech report as published 2024-12-27 and the weights as MIT-licensed.
- Official cutoffs for the current V4/V4.1 models: UNVERIFIED (not published as far as I could find).
- Third-party aggregators list V3 and R1 at about 2024-07-31, V3.1 as either Aug 2024 or 2025-03-31 (sources conflict), and V3.2 as none. Search result, unofficial: e.g. https://www.datalearner.com/en/ai-models/pretrained-models/deepseek-v-3_1 and https://thegtmdirectory.com/models/compare/deepseek-deepseek__deepseek-v3.2-vs-deepseek-deepseek__deepseek-chat-v3.1. Treat all as UNVERIFIED.

**Is any currently served DeepSeek API model's cutoff <= 2024-12-31? UNVERIFIED, and probably no.** The models were released in 2026, and nothing documents a cutoff. Assume the current V4 models have seen 2025 data.

## 3. Reliability of stated cutoffs
- Cheng et al., "Dated Data" (COLM 2024) found that effective cutoffs, measured by perplexity probing, often differ from reported cutoffs, usually by being earlier, because of CommonCrawl temporal bias and dedup issues. https://arxiv.org/abs/2403.12958. I saw no DeepSeek-specific results in the summary I read.
- Look-ahead bias is a documented problem for LLM backtests. FinCAD (2026) reports memorized in-sample returns, and a suppression method cut them by up to 67%. https://arxiv.org/abs/2605.24564 (via search summary; not read in full).
- DatedGPT (2026) trains models with strict yearly cutoffs, 2013-2024, for this purpose, but only at 1.3B parameters. https://arxiv.org/abs/2603.11838
- Net: a stated cutoff is a weak guarantee, and even the true cutoff does not rule out contamination of dated facts. Anonymizing companies helps only partly, because financial figures can still identify a company.

## 4. Older-cutoff alternatives
- DeepSeek-V3-0324 weights are public under MIT (HF link above). The model is listed on OpenRouter with `tools` and `response_format` parameters accepted (https://openrouter.ai/deepseek/deepseek-chat-v3-0324). Current price, context and uptime: UNVERIFIED (the page fetch did not show them).
- Qwen2.5-72B-Instruct is listed on OpenRouter with tools and `response_format` (https://openrouter.ai/qwen/qwen-2.5-72b-instruct). Price, context and its cutoff: UNVERIFIED. I did not confirm Qwen2.5's cutoff from an official source. Qwen2.5 was released in 2024, but I have not verified the date.
- OpenRouter's catalogue fetch did not return usable data (UNVERIFIED), so availability on cheap APIs on 2026-11-02 must be checked live (https://openrouter.ai/models).
- Self-hosting open weights is the only option with a guaranteed fixed model version. Its cost is GPU hours, and I did not price it.
- Option not researched: DatedGPT-style small models with a 2024 cutoff. They are likely too weak for 10-K analysis.

## 5. Recommendation
1. Do not claim the DeepSeek V4 models satisfy the 2024-12-31 cutoff. Record in `docs/MODEL.md` that the cutoff is "not published, UNVERIFIED, likely later than the decision date", and list look-ahead as a known limitation (this is what SCOPE section 3 already prescribes).
2. For the primary run, use `deepseek-flash`. It is cheapest, supports JSON and tool calls, and has a 1M context. Pin the dated model version in config and log it per run, since the alias is re-pointed (it moved on 2026-10-17).
3. If a defensible cutoff matters, run an ablation with an older open-weight model (DeepSeek-V3-0324 or Qwen2.5) via OpenRouter, after verifying its price, availability and cutoff. Compare results to bound the leakage effect.
4. Add a cheap probe to the pipeline: ask the model about known post-2024-12-31 events and about the anonymized companies' 2025 results, and record the answers as evidence.
