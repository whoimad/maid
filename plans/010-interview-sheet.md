# Plan 010: An interview sheet gives a 2-minute pitch, likely questions with short sourced answers, and an honest "what I'd change"

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: confirm these files exist: `docs/architecture/graph.md`,
> `docs/architecture/uncertainty.md`, `docs/architecture/robustness.md`, and that
> `grep -c "^## D" docs/architecture/decisions.md` → 15. If any is missing, STOP (dependencies not merged).

## Status

- **Priority**: P2
- **Effort**: S
- **Risk**: LOW
- **Depends on**: plans 006, 007, 008, 009 merged; PR #13 merged
- **Category**: docs
- **Planned at**: commit `258af88`, 2026-11-02

## Why this matters

The project exists mainly so its owner can learn and explain it in interviews. The architecture docs are reference
material; this is the one page to read before an interview. It must contain no new claims: every answer is a short
summary of an existing doc, linked.

## Current state

Docs the sheet summarizes (read all of them before writing): `docs/SCOPE.md`, `docs/architecture/overview.md`,
`graph.md`, `mcdm.md`, `robustness.md`, `uncertainty.md`, `decisions.md` (D1–D15),
`docs/research/weight-stability-results.md`.

## Scope

**In scope**: `docs/INTERVIEW.md` (create), `README.md` (add one line linking it, under the first paragraph).
**Out of scope**: every other file. If you find a doc inconsistency, list it in your report; do not fix it.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Tests | `pytest -q` | all pass (includes the doc link test) |
| Lint | `ruff check .` | `All checks passed!` |

## Git workflow

Branch `docs/interview-sheet`. Commit `docs: add interview sheet`, ending with
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. No push/PR unless instructed.

## Steps

### Step 1: Write `docs/INTERVIEW.md`

Sections:

1. `# MAID in an interview`
2. `## 2-minute pitch` — 6–8 sentences, in this order: the problem (rank ~12 companies in one sector on
   quantitative and qualitative criteria); the one idea (LLMs read and score with evidence, a deterministic MCDM
   engine weights and ranks: D1); the pipeline in one sentence (LangGraph: ingest → scorer agents → human review
   interrupt → MCDM → robustness → report); the noise problem (n≈12; spike #6 tau ≈ 0.62–0.89, synthetic) and the
   answer (rank intervals + method agreement); look-ahead control (decision date 2024-12-31, anonymized names,
   known limitation that the model cutoff is unpublished); honest status (MCDM and robustness libraries and the
   review interrupt are built and tested; ingest, scorers and report are stubs).
3. `## One picture` — copy the C4 level-2 (container) Mermaid diagram from `overview.md` verbatim.
4. `## Likely questions` — `###` heading per question, answer ≤ 4 sentences, ending with a link to the source doc
   section. Questions, in order:
   1. Why not let the LLM rank the companies? (D1)
   2. How do you prevent look-ahead bias, and what can't you prevent? (D3, SCOPE §3)
   3. How do you know the LLM scores are any good? (D9, evidence quote, human checkpoint, K samples; say what is not built)
   4. Why entropy and CRITIC instead of AHP or expert weights? (D4)
   5. Why TOPSIS and SAW? (D8)
   6. With 12 companies, can the results mean anything? (uncertainty.md argument, 0.58 threshold)
   7. What is a rank interval and how is it computed? (robustness.md, D13)
   8. Why LangGraph instead of plain Python? (D6, graph.md, including the honest counterpoint)
   9. How does the human-in-the-loop work technically, and what happens if the process crashes mid-review? (graph.md: interrupt/resume, MemorySaver limitation)
   10. How is it tested? (pure-function MCDM engine, seeded unit tests, CI runs pytest + ruff on Python 3.11 and 3.13, doc tests keep diagrams in sync)
   11. Why not train an ML model? (D15)
5. `## What I would do differently` — exactly these points, one line each: use a persistent checkpointer from the
   start; decide the entropy variant and other OPEN decisions earlier, with a spike each; verify research claims
   against full papers, not abstracts (docs/research/README.md caveat); pin the dated model version from day one
   (D14).
6. `## Glossary` — one line each: MCDM, criterion (benefit-type), decision matrix X, entropy weights, CRITIC,
   SAW, TOPSIS, Kendall tau, bootstrap, Dirichlet distribution, rank acceptability, LangGraph node / state / reducer /
   interrupt / checkpointer, C4 model, ADR, look-ahead bias. Definitions must match the docs.

### Step 2: Link from README

Add after the first paragraph of `README.md`: `Preparing to explain the project? Start with [docs/INTERVIEW.md](docs/INTERVIEW.md).`

**Verify**: `pytest -q && ruff check .` → pass; `grep -c "^### " docs/INTERVIEW.md` → 11.

## Done criteria

- [ ] `docs/INTERVIEW.md` exists with 11 question headings; every answer ends with a relative link
- [ ] `pytest -q` (links resolve) and `ruff check .` pass
- [ ] Only `docs/INTERVIEW.md` and `README.md` changed
- [ ] `plans/README.md` row updated

## STOP conditions

- An answer would need a fact not found in the listed docs → leave a `TODO(owner): ...` line instead of inventing; report it.
- Docs contradict each other on a fact you need → report both; do not choose.

## Maintenance notes

- Regenerate or edit this sheet whenever a stub becomes real or an OPEN decision closes.
- Reviewer (the owner): read it aloud once; every sentence should be something you can defend.
