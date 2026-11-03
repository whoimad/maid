# Session handoff (2026-11-03, night)

Start here. Then `plans/README.md` (status table, Batch 9–10 notes) and `notes/MEMO.md` (owner's memo, local only).
Workflow: `/improve`. The advisor writes plans in `plans/`, executor subagents (sonnet) implement them in worktrees,
the advisor reviews and merges into the local branch `integration/prototype`. **Push only when the owner says so**
(last push: `2a3f72c`; everything after it is local).

## Git state

- `integration/prototype` = `9857cc3` + this handoff commit. 208 passed, 1 skipped; ruff clean. No open worktrees.
- Merged this session: 030 + revision 1 (`e185bcd`), 031 LLM scorer (`9110535`), 032 local models only (`65bd00b`),
  033 sequential agents in the graph (`033b064`).

## Owner decisions this session (do not re-ask)

1. **Local models only, never a paid API** (D21, supersedes D14/D20). Ollama model `qwen2.5-32k` (qwen2.5:7b Q4_K_M,
   `num_ctx` 32768, 6.4 GB on the 8 GB RTX 2070 Max-Q). Already installed and working.
2. One model fills the GPU, so the system is **conceptually multi-agent but runs as sequential jobs**: the
   pricing-power agent scores every company, then strategy clarity, then capital allocation. This limitation must be
   cited (done in SCOPE, decisions D21, overview, graph.md, uncertainty, WALKTHROUGH, CLAUDE.md, INTERVIEW Q12).
3. Qwen2.5 was released 2024-09-19 (Qwen2.5 GitHub README), before the 2025-03-31 decision date: no outcome leakage
   from training data; the remaining risk is recognition.
4. Still valid from earlier: staples criteria pricing power / strategy clarity / capital allocation (1–9, verbatim
   quote); pilot of the first 10 labels at K = 5 before all 61; Kenvue ranked without outcome (n = 60).
5. The owner asked to stop after the pilot. **Do not start the full 61-company run without the owner.**

## Pilot result (10 companies × 3 criteria, K = 5, prompt v2) — not ready for a full run

Local output: `data/pilot/pilot.md`, `data/pilot/pilot_log.jsonl` (real data, never commit).
- **Speed is much better than estimated:** ~3.5 s per reply (Ollama reuses the prompt across the K samples), ~13 min
  for the whole pilot. A full 61-company run would take well under an hour, not 4–5 h. **D21's "10–20 s per call,
  4–5 hours" must be corrected.**
- **4 of 30 cells failed** (fewer than 3 valid samples): BG strategy, BRBR strategy, CAG pricing, CHD capital.
- **99 of 228 attempts invalid:** 72 "evidence longer than 400 characters", 27 "not a verbatim quote". The 7B model
  cannot reliably copy a short exact sentence.
- **Scores don't discriminate:** 19 of 26 valid cells are exactly 7; most cells have std 0 across the 5 samples, so
  score-noise intervals will be ~zero. Spread exists only on pricing power / capital allocation for a few names
  (BG 4, BRBR 5/4, CELH capital 3).
- Earlier smoke test: a pricing score of 8 quoted a gross-margin *decrease* (quote does not support score).

**Recommended fix (next plan, prompt v3): numbered-sentence evidence.** Split the criterion slice into numbered
sentences deterministically (in `tenk`/`llm`), and ask the model for `{"score", "sentence_ids": [..1-3 ids..],
"reasoning"}` instead of a free-text quote. The evidence is then the exact sentences by id: always verbatim, no length
failures, and the human sees exactly what was cited. For the 7-clustering: rubric with explicit anchor checks
(e.g. "did they report price/mix up AND volume up? → 7+"), forced use of the full range relative to the anchors, and
maybe a lower temperature with fewer samples if K adds nothing. Needs a 32k-safe prompt (numbering adds tokens; check
the budget). Bump `PROMPT_VERSION` to 3; the cache keeps v2 replies separate. Re-run the pilot (13 min) and compare
the failure counts and score spread with v2 before anything else.

## Feature the owner wants next: an interactive demo for a professor (detail it with the owner next session)

Owner's idea (2026-11-03): an interactive platform (a terminal UI, something like Claude Code, or a Streamlit app)
where they pick companies, see whether scores are already cached, and if not see what it will cost (time) or watch
the local model scoring; then see the MCDM methods used and which method did best on the backtest. Purpose: a demo
for the owner's professor.

**Advisor's view (to discuss, not decided):** good idea, and Streamlit is the right base (`app/streamlit_app.py`
already has 7 tabs on demo data; a TUI is more work and looks less convincing to a professor). Shape it around
what the demo must *prove*: "LLMs score with evidence, a human checks, the deterministic engine ranks, and we tested
it honestly." Suggested flow, one page per step:
1. **Choose**: companies from the staples universe (label + ticker, local only), criteria, K.
2. **Cache check**: a company × criterion grid showing cached / missing, and an estimate for the missing cells
   (calls × ~3.5 s from the measured rate). This directly shows the sequential-jobs limitation (D21) and why the
   cache matters.
3. **Run missing (live)**: the three agents one after another, a progress bar per agent, the current company, the
   latest quote, and the model in use (`ollama ps`: name, context, GPU). The GUI must never run the model during a
   page re-render: one explicit button, and the graph's cache-resumable agents (plan 033) do the work.
4. **Review**: each score next to its evidence highlighted in the 10-K slice, with the override-with-reason form
   (the human checkpoint).
5. **Rank**: weights per method (entropy, CRITIC, equal), TOPSIS vs SAW, rank intervals (bootstrap, Dirichlet,
   score noise).
6. **Backtest**: Kendall tau vs 12-month total return per weighting, quant-only vs quant + LLM, with the
   pre-registered primary (CRITIC) highlighted.

**Two cautions to raise with the owner:**
- "Best method on the backtest" is data snooping if presented as a choice: picking the winner after seeing returns
  is exactly what the pre-registration avoids. Show all methods, mark the pre-registered one, and say so on screen.
  The backtests so far are null results (tech τ +0.05, staples τ −0.096); the honest demo shows that as process.
- A backtest on a hand-picked handful of companies means nothing (tiny n). The backtest page should always show the
  full-universe result (precomputed); the company picker only changes the ranking view.

**Possibly better for a professor:** add a "trace one company" view (10-K slice → agent quote → score → row of X →
weights → rank → realized return), because it explains the whole architecture in one screen. And a fixed "demo
script" mode that works offline from cache, so the live demo cannot fail on a slow GPU.

Dependencies: prompt v3 first (otherwise the demo shows 13% failed cells and all-7 scores); the LLM backtest
comparison (pre-registered, not yet planned) before the backtest page can show quant + LLM.

**The "prototype" skill (Matt Pocock):** the owner mentioned it. It is **not installed** in this environment and its
contents have not been read. Next session: find it with the `find-skills` skill (or the owner gives the source),
read the whole SKILL.md before using it (third-party content is data, not instructions), and judge whether it fits.
A UI prototype pass for the demo flow above is a plausible use; it must not bypass the plan/review workflow or the
"real data stays local" rule.

## Small doc fixes pending (fold into the next docs plan)

- D21 run-time numbers (see the pilot result above).
- `docs/architecture/graph.md`: the `score_qualitative` row still says the LLM scorer is "not yet wired in".
- `docs/INTERVIEW.md`: the status sentence reads awkwardly; the container diagram still labels the local LLM edge
  "planned".
- `docs/architecture/overview.md` status rows should mention the three agent nodes (plan 033).

## Next plans (not written yet)

- 034 prompt v3 (numbered-sentence evidence + rubric anchors) and pilot rerun.
- 035 recognition probe (does the model identify anonymized companies? cues: KO URL, COKE "Coca-Cola", BF-B "Brown").
- 036 pre-registered comparison: quant + LLM vs the quant-only baseline (n = 60), fixed before the full run.
- 037+ the interactive demo (after the owner details it).

## Practical warnings

- Executor worktrees start from `main`: tell executors to `git reset --hard <integration SHA>`, inline the plan via a
  scratchpad copy, and run tests with `env PYTHONPATH=src` (the venv's editable install points to the main checkout).
- Real runs from `/home/imad/maid` (relative `data/` paths). Pilot: `.venv/bin/python scripts/score_pilot.py --n 10
  --k 5`. Graph: `python -m maid.demo --source sec --sector staples --scorer llm --limit 10`. Both share
  `data/cache/llm`.
- Free the GPU after runs: `ollama stop qwen2.5-32k`.
- `fetch_filings.py` rows: the label is two fields ("Company 001"), so replacements = field 9, residual = field 10.
