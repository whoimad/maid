# Plan 016: No doc line contradicts the demo pipeline (robustness wired, overrides applied, full state keys, current layout)

> **Executor instructions**: Follow this plan step by step. Run every verification command and confirm the
> expected result. If a STOP condition occurs, stop and report. When done, update the status row in
> `plans/README.md` unless a reviewer told you they maintain the index.
>
> **Drift check (run first)**: run the four `grep` commands in "Current state"; each must print the quoted line.
> If one prints nothing, that line was already fixed — skip it and say so.

## Status

- **Priority**: P1 · **Effort**: S · **Risk**: LOW (docs only) · **Category**: docs
- **Depends on**: plans 011–015 merged (they are, on `integration/prototype`)
- **Planned at**: `integration/prototype` after merging c551cea, 2026-11-02

## Why this matters

The demo pipeline (plan 011) wired every graph node, but a few doc lines written earlier still say the opposite.
A reader (or interviewer) who runs `python -m maid.demo` and then reads "not yet wired" loses trust in all the docs.

## Current state (facts verified by the planner)

Code facts: `src/maid/graph.py` node `robustness` calls `robust_ranking(...)` and stores lists in state;
node `mcdm` calls `apply_overrides(...)` before `build_matrix(...)`; the graph is still linear (no `Send` fan-out);
the checkpointer is still `MemorySaver`. `src/maid/state.py` `PipelineState` keys: companies, quantitative,
qualitative, overrides, weights, ranking, report, criteria, filings, score_samples, score_noise, settings, matrix,
scores, method_agreement, robustness (check with `grep -n ":" src/maid/state.py`).

Stale lines:
1. `grep -n "Library only: not yet wired" docs/architecture/robustness.md` (line ~4).
2. `grep -n "not yet wired into the graph" docs/architecture/overview.md` (Blocks list, robustness line).
3. `grep -n "applying them to the scores is not built yet" docs/architecture/overview.md` (section 4 paragraph).
4. `grep -n "ingest and scoring are stubs today" docs/architecture/overview.md` (C4 level-1 caption).
5. `docs/architecture/graph.md`, "Nodes and state": the `PipelineState` key bullet list has only the first 7 keys.
6. `CLAUDE.md` "## Layout": first bullet says `graph.py` is a "LangGraph pipeline skeleton (stub nodes, human-review
   interrupt)"; no bullets for `demo.py`, `demo_data.py`, `scoring.py`, `matrix.py`, `gui_data.py`, `app/`.

## Scope

**In scope**: `docs/architecture/robustness.md`, `docs/architecture/overview.md`, `docs/architecture/graph.md`,
`CLAUDE.md` (Layout section only). **Out of scope**: all code, all other docs, CLAUDE.md sections other than Layout.

## Steps

### Step 1: Fix lines 1–4
1. robustness.md: replace the "Library only: not yet wired into the graph's `robustness` node." sentence with
   "Wired into the graph's `robustness` node, which runs it on the demo decision matrix (see [graph.md](graph.md))."
   Also remove "Not yet wired into the graph's `robustness` node." from its Known limitations if present.
2. overview.md Blocks: robustness line ends with "(implemented and wired into the graph)".
3. overview.md section 4: replace "Overrides are validated with a mandatory reason; applying them to the scores is
   not built yet." with "Overrides are validated with a mandatory reason and applied to the scores in the `mcdm` node
   before the decision matrix is built." Keep the sentences about MemorySaver and "no fan-out yet" (still true).
4. overview.md C4 caption: replace "ingest and scoring are stubs today" with "today ingest loads a synthetic demo
   dataset and scoring uses a stub scorer".
**Verify**: the four greps print nothing.

### Step 2: graph.md state keys
Extend the `PipelineState` key bullet list with the 9 missing keys, one line each, wording from `state.py` comments
(e.g. `criteria`: column order of X; `settings`: k, weighting, seed, n_draws, concentration; `matrix`: X after
overrides; `scores`: TOPSIS and SAW per company; `method_agreement`: Kendall tau TOPSIS vs SAW; `robustness`:
bootstrap and Dirichlet rank intervals as lists).
**Verify**: `grep -c "^- \`" docs/architecture/graph.md` increases by 9.

### Step 3: CLAUDE.md Layout
Change the graph.py bullet to "LangGraph pipeline: demo run end to end (synthetic data, stub scorer, human-review
interrupt)" and add one bullet each for `src/maid/demo.py` (`python -m maid.demo`), `demo_data.py` (synthetic
dataset), `scoring.py` (stub scorer, evidence check), `matrix.py` (overrides → decision matrix), `gui_data.py`
(pure GUI data helpers), `app/streamlit_app.py` (Streamlit GUI). Match the existing bullet style. Change nothing
else in CLAUDE.md.

### Step 4: Verify
`pytest -q` (all pass, doc link test included) and `ruff check .`.

## Done criteria
- [ ] The four greps from Current state print nothing
- [ ] graph.md lists all 16 state keys; CLAUDE.md Layout lists the 6 new modules
- [ ] `pytest -q`, `ruff check .` pass; only the 4 in-scope files changed

## STOP conditions
- A code fact above is false (e.g. `robustness` node does not call `robust_ranking`) → STOP.

## Maintenance notes
- When the real scorer/ingest or the `Send` fan-out land, re-run the same greps for "stub", "demo", "planned".
