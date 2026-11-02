# Plan 015: Refresh built-vs-planned status in overview.md and uncertainty.md after the demo pipeline

> **Executor instructions**: Follow this plan step by step. Run every verification command and confirm the expected
> result before moving to the next step. If anything in the "STOP conditions" section occurs, stop and report — do
> not improvise. When done, update the status row for this plan in `plans/README.md` — unless a reviewer dispatched
> you and told you they maintain the index.
>
> **Drift check (run first)**: `git diff --stat 73d9bb1 -- docs/architecture/overview.md docs/architecture/uncertainty.md`
> must print nothing; otherwise compare with the excerpts below and STOP if they no longer match.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW (docs only)
- **Depends on**: plans/011-demo-pipeline-end-to-end.md (DONE)
- **Category**: docs
- **Planned at**: commit `73d9bb1` (branch `integration/prototype`), 2026-11-02

## Why this matters

The owner uses these docs to explain the project in interviews. Plan 011 built a working demo pipeline
(`python -m maid.demo`), but two docs still say those parts are "planned". Saying in an interview that something is
not built when it is (or the reverse) costs credibility. The status tables are the docs' main promise.

## What is built today (facts; verify each with the command shown)

| Fact | Check |
|---|---|
| A stub scorer draws K samples per company x criterion, aggregates by median (half rounds up) and stores the sample std | `grep -n "def aggregate\|class StubScorer" src/maid/scoring.py` |
| The graph stores samples and noise in state (`score_samples`, `score_noise`) | `grep -n "score_samples\|score_noise" src/maid/graph.py` |
| The evidence substring check runs on every aggregated score (`evidence_is_quoted`) | `grep -n "evidence_is_quoted" src/maid/graph.py` |
| Overrides are applied to scores before the matrix is built (`apply_overrides` in `mcdm` node) | `grep -n "apply_overrides" src/maid/graph.py` |
| A method-agreement metric exists: Kendall tau TOPSIS vs SAW, in state as `method_agreement` and in the report | `grep -n "kendall_tau" src/maid/graph.py` |
| The `mcdm` and `robustness` graph nodes are real (not stubs): weights, TOPSIS/SAW, bootstrap + Dirichlet rank intervals | `grep -n "def mcdm\|def robustness" src/maid/graph.py` |
| Still NOT built: real LLM (DeepSeek) scorer, real SEC/yfinance ingest, LangGraph `Send` fan-out, persistent checkpointer, entropy-vs-CRITIC agreement metric, backtest, look-ahead probe | `grep -rn "Send\|Sqlite\|deepseek" src/maid/graph.py` → no `Send`/`Sqlite` |

## Current state (verbatim excerpts to change)

`docs/architecture/overview.md` line 84 (system flow diagram):
```
    I -->|filing text, names anonymized| S["Qualitative scorer agents<br/>one per company x criterion, K samples (planned)"]
```
`docs/architecture/overview.md` lines 133-134:
```
checkpointer (e.g. SQLite) and is planned. Today the graph is linear (no fan-out yet). Overrides are
validated with a mandatory reason; applying them to the scores is not built yet.
```
`docs/architecture/uncertainty.md` table rows (status column is the 5th column):
- Row "LLM sampling noise": status `planned (scorer agents not built)`
- Row "LLM error / unsupported evidence": status `human checkpoint and override validation built; applying overrides, the substring check and the scorers are planned`
- Row "Weight estimation noise": status `library (bootstrap in `robust_ranking`; weights built, graph nodes are stubs)`
- Row "Method choice (weighting x ranker)": status ``entropy_weights`, `critic_weights`, `equal_weights`, `topsis`, `saw` built (library); agreement report planned``

## Required changes (decided wording; small deviations in phrasing are fine, facts are not)

1. overview.md line 84: label becomes `"Qualitative scorer agents<br/>one per company x criterion, K samples (stub today)"`.
   Keep the quotes (Mermaid needs them because of the parentheses).
2. overview.md lines 133-134: replace the last sentence with
   `Overrides are validated with a mandatory reason and applied to the scores in the mcdm node before the decision matrix is built.`
   Keep "Today the graph is linear (no fan-out yet)."
3. uncertainty.md statuses:
   - LLM sampling noise → `demo: stub scorer draws K samples, median aggregate, std stored in score_noise; real LLM scorer planned; score noise not yet propagated into rank intervals`
   - LLM error / unsupported evidence → `demo: substring check on every score, human checkpoint, overrides applied with reason; real LLM scorer planned`
   - Weight estimation noise → `built: bootstrap rank intervals in the robustness graph node`
   - Weight choice → `built: Dirichlet rank intervals in the robustness graph node; concentration uncalibrated` (current status is `library`)
   - Method choice → `built: Kendall tau TOPSIS vs SAW in the mcdm node and report; entropy vs CRITIC comparison planned`
4. Do not change any other row, column, or section. Search both files for any other sentence that says one of the
   built items in the facts table is planned/not built; if you find one, fix it the same way and list it in your report.

## Scope

**In scope**: `docs/architecture/overview.md`, `docs/architecture/uncertainty.md`.
**Out of scope**: everything else (code, other docs, README, plans other than the index row).

## Commands

| Purpose | Command | Expected |
|---|---|---|
| Setup (fresh worktree) | `python3 -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"` | exit 0 |
| Docs tests (link check + graph diagram check) | `pytest -q tests/test_docs.py` | 2 passed |
| All tests | `pytest -q` | all pass |
| Lint | `ruff check .` | `All checks passed!` |

## Steps

1. Run every check in the facts table; if any fact is false, STOP.
2. Make changes 1-3. **Verify**: `grep -n "not built yet\|scorer agents not built\|graph nodes are stubs\|agreement report planned" docs/architecture/overview.md docs/architecture/uncertainty.md` → no match.
3. Do change 4. **Verify**: `pytest -q` → all pass; `ruff check .` → pass.
4. Commit on branch `docs/status-after-demo`: `docs(architecture): mark demo-built parts in overview and uncertainty`,
   body `Refs plan 015`, ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. No push.

## Done criteria

- [ ] The grep in step 2 prints nothing
- [ ] `pytest -q` all pass; `ruff check .` passes
- [ ] `git diff --stat 73d9bb1..HEAD` lists only the two in-scope files

## STOP conditions

- A fact in the facts table is false on the current code.
- The uncertainty table has a different set of rows than listed above.

## Maintenance notes

- When the real scorer, fan-out or score-noise propagation lands, update these same status cells.
