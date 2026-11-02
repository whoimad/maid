# Research notes: LLM agents, MCDM, look-ahead bias, reliable scoring

Date: 2026-11-02. Method: web search + fetch of arXiv abstracts/docs only. Full texts were NOT read;
claims come from abstracts/search summaries. Anything not seen directly is marked UNVERIFIED.
Numbers (returns, Sharpe) deliberately omitted because I did not verify them.

## 1. LLM / multi-agent systems for investment and MCDM

- TradingAgents (Xiao, Sun, Luo, Wang; 2024, arXiv 2412.20138): simulated trading firm of role agents
  (fundamental, sentiment, technical analysts; bull/bear researchers who debate; risk team; trader).
  Reports backtest gains over baselines [S1]. Architecture: role-specialised analysts -> debate -> decision.
  The LLM makes the final trade call, which is exactly what MAID avoids.
- FinMem (Yu et al.? author list UNVERIFIED; 2023, arXiv 2311.13743): single trading agent with a profiling
  module, layered memory ranked by recency/relevance/importance, and a decision module [S2]. Architecture
  is memory-centred, not criteria-centred.
- FinAgent (Zhang, Zhao, Xia, ... Bo An; 2024, arXiv 2402.18485): tool-augmented multimodal agent over
  numeric, text and chart data, with reflection; reports beating nine baselines on six datasets [S3].
- Common pattern in all three: LLM directly produces buy/sell/hold. All are evaluated by backtest on
  trading performance, mostly on pre-cutoff periods (contamination risk, see section 2). No source here
  separates "LLM extracts scores" from "deterministic ranker", so MAID's design is a deliberate departure.
- LLM + MCDM (found, none in stock selection):
  - Lu et al. 2024, arXiv 2410.01246: LLM generates criteria and does pairwise comparisons under each
    criterion (AHP-style) for open-ended answer evaluation; skipped criteria-vs-criteria pairwise because
    LLMs gave near-identical importance judgments [S4].
  - arXiv 2604.03742 (2026; authors UNVERIFIED): fuzzy AHP + "DualJudge"; claims AHP-style structured
    judging beats direct scoring for judging LLM outputs [S5].
  - Xue et al., "RankLLM", CCL 2025: TOPSIS used to rank LLMs, i.e. MCDM applied TO LLMs, not by them [S6].
- Gap: I did not find (in a single search round) a paper that uses LLMs to score qualitative criteria for
  equity selection and then ranks with entropy/CRITIC + TOPSIS/PROMETHEE. Absence of evidence only;
  UNVERIFIED that none exists. Do a second targeted search (Google Scholar, "LLM" + "TOPSIS" + "stock") before claiming novelty.

## 2. Look-ahead / contamination bias

- Memorization is real: Lopez-Lira, Tang, Zhu 2025 (arXiv 2504.14765) report LLMs recall exact economic
  and financial values before their cutoff; "respect the date" instructions do not stop it; masking fails
  because models reconstruct entities/dates from minimal context; no recall post-cutoff [S7].
  Caveat: their focus is forecasting of numbers; they note extraction tasks are less affected (from search
  summary, UNVERIFIED in full text).
- Anonymization trades one bias for another: Wu, Yang, Ying, Zhou 2025 (arXiv 2511.15364): anonymized text
  predicted S&P credit downgrades worse; loss mainly from removed numbers/entities, not from bias removal;
  proposes an "anonymization gap" metric needing no outcome data [S8]. Glasserman & Lin 2023 (arXiv
  2309.17322): in-sample anonymized headlines did better (a "distraction effect" of firm knowledge),
  out-of-sample look-ahead was not a concern [S9].
- Detection: Gao, Jiang, Yan 2025/26 (arXiv 2512.23847): "Lookahead Propensity" from a date-only recall
  query; contamination flagged by a positive LAP x forecast interaction; effect vanishes post-cutoff [S10].
- Point-in-time models: He, Lv, Manela, Wu 2025 (arXiv 2502.21206) ChronoBERT/ChronoGPT trained only on
  data available at each date; bias appears modest for news-based return prediction [S11].
  Look-Ahead-Bench (Benhenda 2026, arXiv 2601.13770) compares Llama 3.1 and DeepSeek 3.2 with PiT-Inference
  models and reports significant look-ahead bias in the standard LLMs via alpha decay [S12]
  (that benchmark's own independence is UNVERIFIED: PiT-Inference is a compared product).
- Another entity-swapping approach: Greve & Sablica 2025 (arXiv 2505.21128), replacing names with other
  names; authors admit some semantic distortion [S13].

## 3. Reliable LLM scoring and LangGraph

Scoring (all from abstracts/summaries; effect sizes UNVERIFIED):
- Yamauchi et al. 2025 (arXiv 2506.13639): clear evaluation criteria matter most; sampling-based decoding
  tracks humans better than greedy; averaging multiple scores worked best; CoT adds little with clear
  criteria [S14].
- Judge Reliability Harness (arXiv 2603.05399, 2026; authors UNVERIFIED): test suites for invariance to
  paraphrase/format, repeated-sampling stability, ordinal calibration; warns small human-agreement checks
  give limited assurance [S15].
- RULERS (arXiv 2601.08654) and Autorubric (arXiv 2603.00077): locked evidence anchors, calibration
  mapping, multi-judge ensembles [S16, S17]. Authors UNVERIFIED. G-Eval (original paper) not retrieved.
- LangGraph docs [S18]: `Send` objects returned from conditional edges give map-reduce fan-out (node name
  + per-branch state); fan-out destinations run in the same superstep, i.e. parallel; each state key has
  its own reducer (so parallel writes to a list need an `Annotated[list, operator.add]` style reducer;
  that exact snippet is from my background knowledge, UNVERIFIED here). `interrupt()` pauses; resume via
  `Command(resume=...)`, payload returned by `interrupt()`; node re-runs from its start on resume, so
  pre-interrupt side effects must be idempotent; checkpoints saved at superstep boundaries [S18, S19].
  Interrupt placed inside parallel branches: not documented in what I read; avoid it.

## 4. Implications for MAID design

1. Keep "LLMs never rank": supported by the lack of any verified evidence that direct LLM trade calls are
   free of memorization; it also separates what we can audit (scores) from what is deterministic.
2. Anonymization is necessary-but-insufficient [S7] and costly [S8]. Do not strip numbers: feed anonymized
   names but keep financial figures (quantitative criteria come from XBRL anyway). Expect residual leakage
   from distinctive facts (segment names, product lines); scrub product/brand names in qualitative text
   where feasible and say the rest remains a limitation.
3. Check DeepSeek cutoff vs 2024-12-31 (open item). Likely later; then 2025 backtest is partly contaminated
   in principle. Run a cheap LAP-style probe [S10] (ask the model date-only recall of FY2025 outcomes for
   anonymized and named firms) and report it. Consider a small-model/early-cutoff robustness run.
   Measure the anonymization gap [S8] by scoring a few firms both ways.
4. Scoring protocol: one rubric per criterion with anchored levels, JSON schema output (score, quote, source
   section), K>=5 samples at nonzero temperature, aggregate by median/mean and store variance [S14, S15];
   reject scores whose evidence quote is not a substring of the supplied filing text (cheap programmatic
   citation check). Test paraphrase/order invariance on a few prompts [S15]. Calibrate against the human
   overrides collected at the checkpoint.
5. LangGraph: fan out via `Send` (company x criterion), reduce into a dict keyed (company, criterion);
   place a single `interrupt` in a node AFTER the join, never inside parallel branches; use a persistent
   checkpointer; keep the review node idempotent [S18, S19].
6. Cite honestly in the report: backtest on ~12 names with a possibly contaminated model is a plumbing
   test, not evidence of predictive skill.

## Sources
- S1 Xiao, Sun, Luo, Wang (2024), TradingAgents: Multi-Agents LLM Financial Trading Framework. https://arxiv.org/abs/2412.20138
- S2 FinMem: A Performance-Enhanced LLM Trading Agent with Layered Memory and Character Design (2023). https://arxiv.org/abs/2311.13743
- S3 Zhang et al. (2024), A Multimodal Foundation Agent for Financial Trading. https://arxiv.org/abs/2402.18485
- S4 Lu et al. (2024), AHP-Powered LLM Reasoning for Multi-Criteria Evaluation of Open-Ended Responses. https://arxiv.org/abs/2410.01246
- S5 Structured Multi-Criteria Evaluation of LLMs with Fuzzy AHP and DualJudge (2026). https://arxiv.org/abs/2604.03742
- S6 Xue et al. (2025), RankLLM, CCL. https://preview.aclanthology.org/new-sigs/2025.ccl-1.62/
- S7 Lopez-Lira, Tang, Zhu (2025), The Memorization Problem: Can We Trust LLMs' Economic Forecasts? https://arxiv.org/abs/2504.14765
- S8 Wu, Yang, Ying, Zhou (2025), Anonymization and Information Loss. https://arxiv.org/abs/2511.15364
- S9 Glasserman, Lin (2023), Assessing Look-Ahead Bias in Stock Return Predictions Generated By GPT Sentiment Analysis. https://arxiv.org/abs/2309.17322
- S10 Gao, Jiang, Yan (2025), Detecting Lookahead Bias in LLM Forecasts. https://arxiv.org/abs/2512.23847
- S11 He, Lv, Manela, Wu (2025), Chronologically Consistent Large Language Models. https://arxiv.org/abs/2502.21206
- S12 Benhenda (2026), Look-Ahead-Bench. https://arxiv.org/abs/2601.13770
- S13 Greve, Sablica (2025), Named Entity Swapping for Metadata Anonymization in a Text Corpus. https://arxiv.org/abs/2505.21128
- S14 Yamauchi et al. (2025), An Empirical Study of LLM-as-a-Judge. https://arxiv.org/abs/2506.13639
- S15 Judge Reliability Harness (2026). https://arxiv.org/abs/2603.05399
- S16 RULERS (2026). https://arxiv.org/abs/2601.08654
- S17 Autorubric (2026). https://arxiv.org/abs/2603.00077
- S18 LangGraph Graph API docs. https://docs.langchain.com/oss/python/langgraph/graph-api
- S19 LangGraph human-in-the-loop docs. https://docs.langchain.com/oss/python/langgraph/human-in-the-loop

Not retrieved (do not cite without checking): Lopez-Lira & Tang "Can ChatGPT Forecast Stock Price Movements?"
(arXiv 2304.07619, ID only from a citation); Sarkar & Vafa on lookahead bias in pretrained LMs (not found).
