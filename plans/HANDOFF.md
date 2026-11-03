# Session handoff (2026-11-03, evening)

Start here. Then read, in this order:
1. `plans/README.md`: status of every plan, and the "Batch 9" notes (LLM scores: owner decisions, Ollama facts).
2. `plans/030-tenk-text-v2.md`: the plan under review right now.
3. `docs/architecture/data.md`, subsection "10-K text for the qualitative scorer".
4. `notes/MEMO.md` (local only): the owner's memo. Updated this session (sections 8–10).

Workflow: the `/improve` skill. The advisor writes plans in `plans/`, executor subagents (sonnet) implement them in
worktrees, and the advisor reviews and merges into the local branch `integration/prototype`. **Push only when the
owner says so.**

## Git state

- `integration/prototype` = `2a3f72c`, **pushed** on 2026-11-03 at the owner's request (PR #16 head = `2a3f72c`).
  CI was `in_progress` when last checked. Check `gh run list --branch integration/prototype --limit 1`.
- Tests on `2a3f72c`: 158 passed, 1 skipped; ruff clean.
- **Plan 030 is waiting for review completion:** branch `feat/tenk-text-v2` at `030c82d`, worktree
  `/home/imad/maid/.claude/worktrees/agent-a2e8d30bb59c1ac06`. Executor report: COMPLETE, 182 passed, 1 skipped, ruff
  clean, only in-scope files. Its two test changes are fine: the core variant ("ALTRIA") changes two old assertions.
  - **Done:** the advisor read the `tenk.py` diff, and it matches the plan.
  - **Not done:** the real-data check. The owner interrupted it. Run it from the worktree with the shared cache:

    ```bash
    W=/home/imad/maid/.claude/worktrees/agent-a2e8d30bb59c1ac06
    cd $W && MAID_CACHE_DIR=/home/imad/maid/data/cache PYTHONPATH=$W/src \
      /home/imad/maid/.venv/bin/python -W ignore scripts/fetch_filings.py --sector staples
    ```

    Check:
    - CLX has `mdna_source = exhibit:clx-20240630_d2.htm` (about 13k words) and a non-empty Item 1A.
    - The `residual` column is 0 or close to it for the 10 weak companies (ACI CELH CHD CLX EL HRL JJSF MKC PPC SJM).
    - How many companies have no split (`n`) and how many are truncated: the expectation was 7 and 1.
    - **Core variants that are common English words.** For example, if "Post Holdings" is in the universe, its core
      variant "Post" would also replace "post-retirement". Print `name_variants` for all 61 and look at any variant of
      6 characters or fewer. If one is a common word, the fix is a small follow-up: a stop-list or a minimum length for
      core variants, plus a test. Do not patch by hand.
  - Then merge (`git merge --no-ff feat/tenk-text-v2`), run the gates, remove the worktree, and set the 030 row to DONE
    in `plans/README.md`.

## Owner decisions this session (do not re-ask)

1. Kenvue (KVUE, delisted, no Yahoo history): option (b). It stays ranked, has no outcome, n = 60. The dated deviation
   is in `data.md`.
2. LLM criteria for staples: **pricing power, strategy clarity, capital allocation**. Each is scored 1–9 with a verbatim
   quote, and all are benefit-type.
3. **Pilot first:** 10 companies (the first 10 labels, a fixed rule), K = 5. The owner reviews them before all 61 run.
4. **Local model via Ollama** (OpenAI-compatible API) for development and as the older-cutoff leakage comparison.
   **DeepSeek** for the main run. Record this as D20 (it extends D14).
5. Push approved once (done). Ask again before the next push.
6. Communication: the owner's network is fine. Don't blame "waiting for the API"; mention the network only if a call
   actually fails because of it.

## What was done this session

- 027: `--no-outcome` in the backtest. Merged `99ea26d`.
- **Staples backtest run:** primary CRITIC Kendall tau −0.096 (p = 0.28, n = 60). Entropy +0.044, equal −0.043. A null
  result. The approximate 95% CI for tau is −0.27..+0.08, which argues against rho ≳ 0.13. The per-company table is
  local only, in `notes/scratch/staples_backtest.txt`.
- 028: write-up `docs/research/backtest-staples-results.md`. Merged `b6bb576`.
- 029: 10-K text ingest (`src/maid/tenk.py`, `SecClient.filing_html`, `real_data.load_filings`,
  `scripts/fetch_filings.py`). Revised once for hyphenated names. Merged `20a063a`. The real fetch found:
  - 60 ok;
  - CLX: MD&A by reference, and "Item 1.A." headings;
  - 10 weakly anonymized companies;
  - MD&A median about 15.5k tokens, max about 64k (PEP);
  - KO's URL `www.coca-colacompany.com` survives (a recognition cue).
- 030 written and executed (see above).
- `notes/MEMO.md` updated: universe outcome, Kenvue, the result, next steps.

## Next: plan 031, the LLM scorer (not written yet)

Design worked out, ready to write once 030 is merged:
- **Client:** the `openai` package is already a dependency (`openai>=1.40`; 3.42.1 in the venv). Use one
  OpenAI-compatible client with base URL, model and key from settings. New env vars `LLM_BASE_URL`, `LLM_MODEL`,
  `LLM_API_KEY` fall back to the existing `DEEPSEEK_*` ones (`src/maid/config.py`; `tests/test_config_cache.py`
  reads `DEEPSEEK_MODEL`, so keep that working). Ollama uses `http://localhost:11434/v1`, model e.g. `qwen2.5:7b`, and
  any non-empty key. Log the `model` field of each response (the DeepSeek alias was re-pointed on 2026-10-17; see
  `docs/research/model-cutoff.md`).
- **Request:** `response_format={"type": "json_object"}` (the prompt must contain the word "json"), a per-sample
  `seed`, and a fixed temperature (e.g. 0.7) so K samples vary. Ollama supports `response_format` and `seed`.
- **Output JSON:** `{"score": 1-9, "evidence": "<verbatim quote ≤ 300 chars>", "reasoning": "≤ 60 words"}`. Validate
  with the existing `CriterionScore` (`state.py`: score, evidence; keep it unchanged) and keep the reasoning
  separately. Evidence check: the quote must be a substring of the criterion text after whitespace collapse and
  curly/straight quote normalization.
- **Failures:** up to 3 attempts per sample (attempt index goes into the seed and the cache key). A sample with no
  valid attempt is dropped. If fewer than ceil(K/2) valid samples remain, raise. Report counts.
- **Truncation guard (essential for Ollama):** its default context is 4k tokens on GPUs under 24 GiB, the
  OpenAI-compatible API cannot change it (set `OLLAMA_CONTEXT_LENGTH=32768 ollama serve`, or use a Modelfile
  `PARAMETER num_ctx`), and `ollama ps` shows the allocated context. Raise if the reported `usage.prompt_tokens` is
  below 0.7 × `approx_tokens(prompt)`.
- **Cache key:** `DiskCache.llm_key(model, PROMPT_VERSION, EXTRACTOR_VERSION, criterion, label, sha256(text),
  sample, attempt, temperature)`.
- **Rubrics** (`src/maid/rubrics.py`, with `PROMPT_VERSION`), anchors for 1–3, 4–6 and 7–9:
  - *pricing power:* low means price cuts or promotions to defend volume, costs not passed through, or private-label
    losses; high means price/mix gains with stable or growing volume, and costs explicitly passed through.
  - *strategy clarity:* low means boilerplate with no priorities; high means specific priorities with measurable
    targets and timeframes, tied to resources.
  - *capital allocation:* low means no stated policy, a dividend cut, or opportunistic M&A with no criteria; high
    means explicit ordered priorities, a leverage target, return criteria, and a consistent record.
  - The system prompt says the company is anonymized and asks the model to use only the excerpt, with no outside
    knowledge.
- **Input:** `tenk.criterion_text(sections, criterion)` from plan 030 gives every model the same slice, with a 24k
  budget.
- **Scope of 031:** client, rubrics, `LLMScorer.score(company, criterion, text, k)` with the same shape as
  `StubScorer`, and a pilot script (`scripts/score_pilot.py --sector staples --n 10 --k 5 --out <local dir>`) that
  writes a local Markdown table for the owner to review (score, std, valid samples, failures, tokens, one quote each)
  plus total prompt tokens. Use fake clients in tests, with no network. **Graph wiring is the next plan** (032: a
  `scorer` setting and the `source="sec"` qualitative path). Then 033 leakage probes (recognition and date-only recall,
  local vs DeepSeek; include the KO URL cue) and 034 the pre-registered comparison against the quant-only baseline
  (n = 60). 033 and 034 are fixed before any full run. (`plans/README.md` Batch 9 still says "031 scorer → 032 probes
  → 033 comparison". Update it when 031 is written.)
- Add D20 to `docs/architecture/decisions.md` in 031: Ollama local and DeepSeek main, the same text slice for both,
  and the truncation guard.

## Owner to-dos (remind, don't nag)

- Install Ollama and run `ollama pull qwen2.5:7b`. The laptop has an RTX 2070 Max-Q (8 GB VRAM) and 15 GB RAM, so it
  can run 7–8B models at 4-bit with a 32k context. Start it with `OLLAMA_CONTEXT_LENGTH=32768 ollama serve`.
- Qwen2.5 and Llama 3.1 release dates (2024) are not yet verified from official sources. Check them in 033.

## Practical warnings

- Executor worktrees start from `main`: tell executors to `git reset --hard <integration/prototype SHA>` first.
  Inline the plan via a scratchpad copy, since uncommitted plans aren't in the worktree. The harness often refuses
  `cd ... &&` and `PYTHONPATH=... cmd` in compound commands, so tell executors to run such commands alone.
- Real runs use `/home/imad/maid` as the working directory (relative `data/` paths), or set `MAID_CACHE_DIR`.
- Yahoo rate limits are server-side. Kenvue is gone from Yahoo for good.
- Scratch: `/tmp/claude-1000/-home-imad-maid/41a15b00-9aec-473f-9d86-5e9783a1defc/scratchpad/` (sample 10-K HTML in
  `dl/`, extraction prototypes in `probe/`, primary-document map in `tenk/primary.json`). Temporary.
