# Plan 013: A walkthrough tells a newcomer, in order, what to run, what to read and where each idea lives in the code

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: these must exist: `src/maid/demo.py`, `app/streamlit_app.py`, `src/maid/gui_data.py`,
> `docs/architecture/graph.md`, `docs/architecture/uncertainty.md`, and `grep -c "^## D" docs/architecture/decisions.md` → 15.
> If any is missing, STOP.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW (one new doc + README links)
- **Depends on**: plans 007, 008, 009, 011, 012
- **Category**: docs
- **Planned at**: commit `6750b35` (integration/prototype), 2026-11-02

## Why this matters

The owner asked for "a walkthrough on how to navigate the project to understand it". The repo now has a runnable
demo, a GUI, architecture docs, decisions and research notes, but no path through them. This plan writes
`docs/WALKTHROUGH.md`: a guided tour in reading order, each stop naming the exact file (and function) to open, what to
look for, and one question to check understanding. It contains no new claims: every statement points to a file.

## Current state

Read these before writing (all exist at this point): `README.md`, `CLAUDE.md`, `docs/SCOPE.md`,
`docs/architecture/overview.md`, `graph.md`, `mcdm.md`, `robustness.md`, `uncertainty.md`, `decisions.md`,
`docs/research/README.md`, `docs/research/weight-stability-results.md`, `src/maid/state.py`, `src/maid/graph.py`,
`src/maid/demo.py`, `src/maid/demo_data.py`, `src/maid/scoring.py`, `src/maid/matrix.py`, `src/maid/mcdm/weights.py`,
`src/maid/mcdm/ranking.py`, `src/maid/mcdm/robustness.py`, `src/maid/gui_data.py`, `app/streamlit_app.py`,
`scripts/weight_stability.py`, `tests/`, `plans/README.md`.

## Scope

**In scope**: `docs/WALKTHROUGH.md` (create); `README.md` (one line linking it, near the top).
**Out of scope**: all other files. Report inconsistencies you find; do not fix them.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Demo | `python -m maid.demo` | report prints |
| Tests | `pytest -q` | all pass (includes the doc link test) |
| Lint | `ruff check .` | `All checks passed!` |

## Git workflow

Branch `docs/walkthrough`. Commit `docs: add project walkthrough`, ending with
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. No push/PR unless instructed.

## Steps

### Step 1: Write `docs/WALKTHROUGH.md`

Structure (use relative links for every file mentioned; use `path:line` only where the line is stable, e.g. a
function definition you verified with `grep -n`):

1. `# Walkthrough: how to understand MAID in about two hours` + a table of the stops with estimated minutes.
2. `## Stop 0 — Run it first (10 min)`: setup commands from README; `python -m maid.demo`; `streamlit run app/streamlit_app.py`;
   what to click in each GUI tab (one line per tab, matching the tab names in `app/streamlit_app.py`).
3. `## Stop 1 — The question and the one rule (10 min)`: `docs/SCOPE.md` §1–3; overview "The one idea"; D1.
4. `## Stop 2 — The architecture (15 min)`: overview status table and C4 diagrams; how to read each diagram type.
5. `## Stop 3 — The LangGraph pipeline (20 min)`: `graph.md`; then open `src/maid/state.py` (state keys),
   `src/maid/graph.py` (`build_graph`, each node), and trace one run: which node writes which key. Explain
   interrupt/resume using `src/maid/demo.py` `run_demo` (how it resumes) and `tests/test_review.py`.
6. `## Stop 4 — Where scores come from (15 min)`: `demo_data.py` (synthetic, latent scores), `scoring.py`
   (`StubScorer`, K samples, median, evidence check), what the real DeepSeek scorer will replace; D9, D14.
7. `## Stop 5 — The MCDM engine (25 min)`: `mcdm.md`; `weights.py` (entropy, CRITIC, equal), `ranking.py` (SAW,
   TOPSIS); `matrix.py` (`build_matrix`, `apply_overrides`); D4, D8, D10, D11; GUI "Weights" and "Ranking" tabs.
8. `## Stop 6 — Noise and robustness (20 min)`: `uncertainty.md`; spike #6 (`scripts/weight_stability.py`,
   `weight-stability-results.md`); `robustness.py` and `robustness.md`; D5, D12, D13; GUI "Robustness" tab:
   change `concentration` and watch intervals widen/narrow.
9. `## Stop 7 — How it is built and tested (10 min)`: `CLAUDE.md` rules; `tests/` (one line per test file: what it
   protects); CI workflow; `plans/` (how the improve-skill plans drove the work).
10. `## Stop 8 — Explaining it (10 min)`: point to `docs/INTERVIEW.md` if it exists (else say "see decisions.md").
11. `## Map: concept → file` — table: concept | where in code | where explained (≈ 15 rows: anonymization,
    decision date, evidence quote, K samples, human override, decision matrix X, entropy, CRITIC, SAW, TOPSIS,
    Kendall tau, bootstrap, Dirichlet, rank acceptability, checkpointer, cache key).
12. `## Check yourself` — 8 questions with a one-line answer each and a link (e.g. "Why can't the scorer change the
    ranking?").

### Step 2: Link from README

Add near the top of `README.md`: `New here? Follow [docs/WALKTHROUGH.md](docs/WALKTHROUGH.md).`

**Verify**: `pytest -q && ruff check .` → pass; `grep -c "^## Stop" docs/WALKTHROUGH.md` → 9.

## Done criteria

- [ ] `docs/WALKTHROUGH.md` with 9 "Stop" sections, a concept map and check-yourself questions
- [ ] Every file path mentioned exists (the link test covers Markdown links; also run `grep -o "src/maid/[a-z_/]*\.py" docs/WALKTHROUGH.md | sort -u | xargs ls` → no "No such file")
- [ ] `pytest -q`, `ruff check .` pass; only the two in-scope files changed

## STOP conditions

- A claim you want to write is not in any listed file → write `TODO(owner)` instead and report it.
- GUI tab names in `app/streamlit_app.py` differ from plan 012 → use the real names (that is not a STOP), mention it.

## Maintenance notes

- Update the walkthrough whenever a stop's file is renamed or a demo/stub becomes real.
