# Plan 006: The architecture overview says what is built vs planned, has no false claims, and opens with C4 context and container diagrams

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat 258af88..HEAD -- docs/architecture/overview.md tests/test_docs.py src/maid/graph.py`
> Expected drift: PR #13 (robustness) adds one line to the "Blocks" list of `overview.md`. Anything else
> changed in these files → compare against "Current state" below; on a mismatch, STOP.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW (docs + one doc-link test)
- **Depends on**: PR #13 (`feat/robustness`) merged into `main`. Check: `test -f docs/architecture/robustness.md` → exit 0. If it fails, STOP.
- **Category**: docs
- **Planned at**: commit `258af88`, 2026-11-02

## Why this matters

The project is a learning project the owner must explain to interviewers. `docs/architecture/overview.md` currently
describes the *target* system as if it already works. Two sentences are false against the code: it says the
checkpointer "can resume across restarts" (the code uses `MemorySaver`, which lives in process memory and is lost
when the process exits), and it shows scorer agents "fan out (one per criterion)" (the real graph is a straight line
of six stub nodes, and the project's own research recommends fanning out per *company × criterion*). An interviewer
who opens `src/maid/graph.py` will see the mismatch. After this plan, the overview marks every block as implemented,
library-only, stub or planned, and opens with the two standard architecture diagrams (C4 model levels 1 and 2).

## Current state

Repo: Python 3.11+, package `maid` in `src/maid/`. Docs are Markdown with Mermaid diagrams (rendered by GitHub).

`docs/architecture/overview.md` (92–93 lines). Relevant excerpts (line numbers at 258af88):

```
1  # Architecture overview
3  Goal: rank companies on mixed quantitative and qualitative criteria **without letting an LLM make the
4  ranking decision**. Diagrams are Mermaid and render on GitHub. Per-block detail lives in the other
5  files in this folder; the reasoning behind each choice is in [decisions.md](decisions.md).
...
19 ## 2. System flow
...
26     I -->|filing text, names anonymized| S[Qualitative scorer agents<br/>one per criterion, K samples]
...
58 ## 4. Human-in-the-loop (LangGraph interrupt)
...
64     G->>S: fan out (one per criterion)
...
72 The interrupt sits after the join, not inside parallel branches, so the human reviews everything once
73 and the checkpointer can resume across restarts. Overrides are logged with a reason; they can later be
74 used to measure where the LLM disagrees with the human.
...
90 ## Blocks
91 - [mcdm.md](mcdm.md): weights and ranking (implemented)
92 - [robustness.md](robustness.md): ...   (added by PR #13)
93 - Ingest, scorer agents, human checkpoint, robustness, report: documented as each is built
```

Facts about what exists (verified by the planner; use these, do not invent others):

| Block | Code | Status |
|---|---|---|
| Ingest (SEC EDGAR, yfinance) | `graph.py` `ingest()` returns `{"quantitative": {}}` | stub |
| Disk cache | `src/maid/cache.py` `DiskCache` (sha256 keys; `llm_key(model, prompt_version, ...)`) | implemented, not yet used by any node |
| Config | `src/maid/config.py` `Settings`: `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, `DEEPSEEK_MODEL` (default `deepseek-flash`), `DECISION_DATE` (default 2024-12-31), `MAID_CACHE_DIR` (default `data/cache`) | implemented |
| Qualitative scorer agents | `graph.py` `score_qualitative()` returns `{"qualitative": []}`; schema `CriterionScore` in `state.py` (score int 1–9 + evidence quote) | stub (schema implemented) |
| Human checkpoint | `graph.py` `human_review()` calls `interrupt(...)`; `parse_overrides()` validates resume payload (`ScoreOverride`, reason mandatory, unknown company/criterion rejected) | implemented; overrides are validated but not yet applied to scores |
| MCDM engine | `src/maid/mcdm/weights.py`, `ranking.py` (entropy, CRITIC, equal; TOPSIS, SAW) | library implemented; graph node `mcdm()` is a stub |
| Robustness | `src/maid/mcdm/robustness.py` (bootstrap + Dirichlet rank intervals) | library implemented; graph node `robustness()` is a stub |
| Report | `graph.py` `report()` returns `{"report": ""}` | stub |
| Backtest vs 2025 | — | planned |
| Checkpointer | `build_graph()` compiles with `MemorySaver` (in-process memory) | implemented; does NOT survive a process restart |

The actual compiled graph edges (from `build_graph().get_graph().edges`):
`__start__→ingest→score_qualitative→human_review→mcdm→robustness→report→__end__` (linear, no parallel branches).

The project research note `docs/research/llm-agents-finance.md` §4 item 5 recommends: "fan out via `Send`
(company x criterion), reduce into a dict keyed (company, criterion); place a single `interrupt` in a node AFTER
the join, never inside parallel branches; use a persistent checkpointer; keep the review node idempotent."

External systems (from `docs/SCOPE.md` §5, §8 and `config.py`): SEC EDGAR (10-K text + XBRL facts), yfinance
(prices), DeepSeek API (LLM). The human user is the analyst (the project owner) who reviews scores.

Doc style exemplar: `docs/architecture/mcdm.md`: short sections, Mermaid `flowchart LR`, tables, plain sentences.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Setup (once) | `python3 -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"` | exit 0 |
| Tests | `pytest -q` | all pass |
| Lint | `ruff check .` | `All checks passed!` |

## Scope

**In scope**: `docs/architecture/overview.md`, `tests/test_docs.py` (create).

**Out of scope**: all of `src/` (do not "fix" the code to match the doc; the doc must describe the code),
`docs/architecture/decisions.md`, `mcdm.md`, `robustness.md`, `docs/research/`, `README.md`.

## Git workflow

- Branch `docs/overview-status` from up-to-date `main`. Conventional commits, e.g.
  `docs(architecture): mark built vs planned in overview, add C4 diagrams`. Repo examples:
  `docs: rerun spike #6 with both entropy variants`, `fix(mcdm): validate decision matrix and weights`.
- End the commit message with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Do NOT push or open a PR unless instructed.

## Steps

### Step 1: Doc link test (write first)

Create `tests/test_docs.py` with one test, `test_relative_markdown_links_resolve`: for every `*.md` under `docs/`
plus `README.md`, find links with regex `\]\(([^)]+)\)`; skip targets starting with `http`, `#` or `mailto:`;
strip any `#anchor` suffix; assert `(md_file.parent / target).exists()`. Collect all broken links and assert the
list is empty (so the failure message lists them). Use `pathlib`, resolve paths from
`Path(__file__).resolve().parents[1]`. Plain `assert`, no network. One-line docstring at module top.

**Verify**: `pytest -q tests/test_docs.py` → 1 passed.

### Step 2: Add a status section and a diagram-types note

Directly after the intro paragraph (before "## 1."), add `## Status: what is built today` containing the
Block/Code/Status table from "Current state" above (you may shorten the Code column, keep every row and every
status word exactly: stub / implemented / library implemented / planned). Below it, one sentence:
"Diagrams in sections 2–4 show the target design; the table above is the source of truth for what runs today."

Then add a short `### Diagram types used here` list:
- C4 model, level 1 (System context) and level 2 (Containers): what the system is and what it talks to.
- Flowchart (data flow): how data moves through the pipeline.
- Sequence diagram: the order of calls in the human-in-the-loop step.
- Design decisions are written as lightweight ADRs (Architecture Decision Records) in `decisions.md`.

**Verify**: `grep -c "Status: what is built today" docs/architecture/overview.md` → `1`

### Step 3: Add C4 level 1 and level 2 diagrams

Add a section `## 0. System context and containers (C4)` right after the status section. Use Mermaid
`flowchart` (not Mermaid's experimental `C4Context` syntax). Two diagrams:

Level 1 (context): nodes `Analyst (human reviewer)`, `MAID` (one box), `SEC EDGAR`, `yfinance`, `DeepSeek API`.
Edges: Analyst → MAID "reviews/overrides scores, reads report"; MAID → SEC EDGAR "10-K text, XBRL facts";
MAID → yfinance "prices up to decision date"; MAID → DeepSeek API "scoring prompts (anonymized)".

Level 2 (containers), inside a `subgraph MAID`: `LangGraph pipeline (graph.py, state.py)`,
`MCDM engine (mcdm/: pure functions)`, `Disk cache (cache.py, data/cache)`, `Checkpointer (MemorySaver, in-memory)`,
`Config (.env via config.py)`. Edges: pipeline → MCDM engine "decision matrix X"; pipeline → disk cache "all API calls";
pipeline → checkpointer "state at each step / interrupt"; config → pipeline. Externals as in level 1, connected
to the pipeline (via cache for SEC/yfinance/DeepSeek). Add the label "(planned)" to nodes/edges whose block is a
stub or planned in the status table (ingest-related externals, DeepSeek).

Under each diagram, 1–2 sentences on what it shows.

**Verify**: `grep -c '```mermaid' docs/architecture/overview.md` → previous count + 2 (count before editing with the same command and record it).

### Step 4: Fix the two false claims

- Line ~26 node label: change `one per criterion, K samples` to `one per company x criterion, K samples (planned)`.
- Line ~64 sequence step: change `fan out (one per criterion)` to `fan out per company x criterion (planned: Send)`.
- Lines ~72–74: replace the sentence about restarts with:
  "The interrupt sits after the join, not inside parallel branches, so the human reviews everything once.
  Today the graph uses `MemorySaver`, which keeps checkpoints in process memory: a paused run survives
  within one Python process, but a restart loses it. Resuming across restarts needs a persistent
  checkpointer (e.g. SQLite) and is planned. Today the graph is linear (no fan-out yet). Overrides are
  validated with a mandatory reason; applying them to the scores is not built yet."

**Verify**: `grep -c "resume across restarts" docs/architecture/overview.md` → `0`;
`grep -c "MemorySaver" docs/architecture/overview.md` → at least `2`.

### Step 5: Blocks list

Change the last Blocks line to: `- Ingest, scorer agents, human checkpoint, report: documented as each is built`
(remove the word "robustness", which now has its own line). Do not touch the other Blocks lines.

**Verify**: `pytest -q && ruff check .` → all pass, `All checks passed!`

## Done criteria

- [ ] `pytest -q` passes, including `tests/test_docs.py::test_relative_markdown_links_resolve`
- [ ] `ruff check .` → `All checks passed!`
- [ ] `grep -c "resume across restarts" docs/architecture/overview.md` → 0
- [ ] `grep -c "Status: what is built today" docs/architecture/overview.md` → 1
- [ ] `grep -c "C4" docs/architecture/overview.md` → ≥ 2
- [ ] `git diff --stat main -- src` → empty; only the two in-scope files changed
- [ ] `plans/README.md` row updated

## STOP conditions

- `docs/architecture/robustness.md` does not exist (PR #13 not merged).
- The link test finds broken links in files you are not allowed to edit → report the list; do not fix them.
- `graph.py` no longer uses `MemorySaver` or is no longer linear (someone built the fan-out) → the facts table is stale; STOP.

## Maintenance notes

- Whenever a stub becomes real, update the status table in the same PR. Reviewers: check every status word against the code.
- Plan 007 adds `docs/architecture/graph.md` with a code-checked diagram of the LangGraph pipeline and extends `tests/test_docs.py`.
