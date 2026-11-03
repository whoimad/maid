# Session handoff (2026-11-03, late evening)

Start here, then `plans/README.md` (status + Batch 9 notes) and `notes/MEMO.md` (local only).
Workflow: `/improve`; executors (sonnet) in worktrees, advisor reviews and merges into local `integration/prototype`.
**Push only when the owner says so** (last push: `2a3f72c`; everything after it is local).

## Git state

- `integration/prototype` = this commit (after `9110535`); 201 passed, 1 skipped; ruff clean. No open worktrees.
- Done this session: 030 revision 1 (common-word cores Post/Corn/National, dotless SA → Bunge, 15 aliases; real fetch:
  61 ok, distinctive leftovers 0; merged `e185bcd`) and 031 LLM scorer (`src/maid/llm.py`, `src/maid/rubrics.py`,
  `scripts/score_pilot.py`, D20; merged `9110535`).

## Next step: the pilot (needs the owner)

Ollama 0.40.14 runs as a systemd service with no models and the default 4k context. Owner to-do:

```bash
ollama pull qwen2.5:7b
printf 'FROM qwen2.5:7b\nPARAMETER num_ctx 32768\n' > Modelfile
ollama create maid-qwen7b-32k -f Modelfile
# .env: LLM_BASE_URL=http://localhost:11434/v1  LLM_MODEL=maid-qwen7b-32k  LLM_API_KEY=ollama
```

Then the advisor runs (from `/home/imad/maid`): `.venv/bin/python scripts/score_pilot.py --sector staples --n 10 --k 5`
→ `data/pilot/pilot.md` (local). Check: no `ContextTruncated` (the guard works if `ollama ps` shows 32768), failed
attempts per cell, whether quotes support the scores, score spread across the 10 companies (all 5–6 means the rubric
does not discriminate). Owner reviews the table before anything else; rubric changes bump `PROMPT_VERSION`.
Cost estimate: 10 × 3 × 5 = 150 calls, ~1.5–2M prompt tokens (slow locally at 32k context on 8 GB: expect minutes per
call for the 24k-token slices; consider `--k 1` first as a smoke test).

## Then (not written yet)

- 032 graph wiring: `scorer` setting, `source="sec"` qualitative path, use `llm.quote_in_text` in the review check
  (`scoring.evidence_is_quoted` is exact-substring and would reject curly-apostrophe quotes).
- 033 leakage probes (recognition incl. KO URL, COKE "Coca-Cola", BF-B "Brown" cues; date-only recall; local vs
  DeepSeek; verify Qwen2.5 / Llama 3.1 release dates from official sources).
- 034 pre-registered comparison vs the quant-only baseline (n = 60). 033 and 034 fixed before any full run.

## Owner decisions (do not re-ask)

See the previous handoff items, all still valid: Kenvue ranked without outcome (n = 60); criteria pricing power,
strategy clarity, capital allocation (1–9, verbatim quote); pilot of the first 10 labels at K = 5; Ollama local +
DeepSeek main (D20); ask before each push; don't blame the network unless a call fails.

## Practical warnings

- Executor worktrees start from `main`: tell them to `git reset --hard <integration SHA>` and run tests with
  `env PYTHONPATH=src` (the venv's editable install points at the main checkout).
- Real runs use `/home/imad/maid` as working directory or set `MAID_CACHE_DIR=/home/imad/maid/data/cache`.
- `fetch_filings.py` rows: the label is two fields ("Company 001"), so replacements = field 9, residual = field 10.
