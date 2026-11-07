# Plan 008: One doc lists every source of noise, how it is measured or mitigated, and what is built, with the argument for why point rankings are not trusted

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat 258af88..HEAD -- docs/research/weight-stability-results.md docs/research/mcdm-noise.md docs/SCOPE.md docs/architecture/uncertainty.md`
> Expect no changes. If any of the source docs changed, re-check every number you copy from them; if one differs
> from this plan, use the doc's value and say so in your report.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: LOW (one new doc)
- **Depends on**: PR #13 merged (`docs/architecture/robustness.md` exists); plan 006 (`tests/test_docs.py` link test)
- **Category**: docs
- **Planned at**: commit `258af88`, 2026-11-02

## Why this matters

The project's core argument is about noise: with about 12 companies, LLM-made scores and data-driven weights, a
single ranking overstates certainty. That argument is currently spread over five files (`SCOPE.md`,
`decisions.md` D4/D5, `weight-stability-results.md`, `mcdm-noise.md`, `robustness.md`). The project owner must
explain it to interviewers. This plan writes `docs/architecture/uncertainty.md`: a single "uncertainty budget"
that names each noise source, where it enters the pipeline, how it is measured or reduced, and whether that is
built, plus the short argument and the key numbers.

## Current state — the facts to use (copy, do not invent)

Every number and claim below comes from the file named. In the doc, link each to its source.
Claims marked [abstract-only] come from `docs/research/`, whose README says the notes were made from abstracts;
keep that caveat in the doc.

From `docs/research/weight-stability-results.md` (spike #6; synthetic data only; seed 42; m=7 criteria; 300 trials):
- At n=12, Kendall tau between rankings with sample weights vs reference weights ranges roughly 0.62 to 0.89
  depending on the weighting/ranking pair.
- Gaussian regime, n=12: entropy TV 0.137, CRITIC TV 0.056; tau entropy→TOPSIS 0.622, entropy→SAW 0.777,
  CRITIC→TOPSIS 0.738, CRITIC→SAW 0.886.
- SAW rankings were more stable than TOPSIS under the same weight noise in this setup.
- Under skew (log-normal), CRITIC stops improving with n (TV ≈ 0.09 from n=8 to n=200).
- Limits: reference weights are the same estimator on a big sample, not a ground truth; one generator, one seed.

From `docs/research/mcdm-noise.md` §2 [abstract-only]:
- Item 7: "with n=12 a Spearman vs 2025 returns needs |rho| > ~0.58 for p<0.05 (two-sided, approx., verify with
  scipy)". The planner verified the t-approximation: `t = stats.t.ppf(0.975, 10); t / sqrt(10 + t*t)` = 0.576.
- Item 8: quantify how much rank variance comes from weights vs ranker vs normalization vs LLM score noise;
  do not conclude "method X is best" from one sector-year.
- Ranking-methods section: the ranking method matters much less for the top and bottom of the list than for the
  middle, where scores are tied within noise.

From `docs/SCOPE.md`: §3 decision date 2024-12-31, anonymized names, DeepSeek cutoff unpublished and likely later;
§4 universe = N largest by market cap (mild survivorship/winner bias, documented, not fixed); §5.3 one scorer per
criterion, rubric, score 1–9 + cited evidence, repeated K times; §6 LLM stability = score variance across K runs;
backtest reported as correlation, not accuracy; Kendall tau primary for ranking comparison.

From `docs/research/llm-agents-finance.md` §4 [abstract-only]: K≥5 samples at nonzero temperature, aggregate by
median/mean and store variance; reject scores whose evidence quote is not a substring of the filing text;
anonymization is necessary but insufficient.

From `docs/architecture/robustness.md` / `src/maid/mcdm/robustness.py` (PR #13): two weight-uncertainty sources
reported separately: bootstrap (resample companies, recompute weights, rank original X) and Dirichlet perturbation
around the point weights (`concentration`, placeholder 100, uncalibrated). Output: 90% rank interval (`lo`–`hi`)
and rank acceptability (share of draws at each rank).

From `docs/architecture/mcdm.md`: min-max normalization depends on sample extremes, so adding/removing a company
can change weights and ranks; default entropy variant (min-max vs sum) undecided.

Status facts: scorer agents, human-override application, method-agreement report, backtest and look-ahead probe
are NOT built; `entropy_weights`, `critic_weights`, `equal_weights`, `topsis`, `saw` and `robust_ranking` ARE built
(library); the human checkpoint interrupt and override validation ARE built.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Tests | `pytest -q` | all pass |
| Lint | `ruff check .` | `All checks passed!` |

## Scope

**In scope**: `docs/architecture/uncertainty.md` (create); `docs/architecture/overview.md` (one Blocks line).
**Out of scope**: all code; all other docs (do not edit the research notes, even if you spot inconsistencies — list them in your report).

## Git workflow

Branch `docs/uncertainty`. Commit e.g. `docs(architecture): add uncertainty budget`, ending with
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. No push/PR unless instructed.

## Steps

### Step 1: Write the doc

`docs/architecture/uncertainty.md`, sections in order:

1. `# Uncertainty budget: where noise enters and what we do about it` + one-line purpose.
2. `## The argument in five sentences` — (1) n≈12 companies; (2) LLM scores are sampled, weights are estimated
   from those 12 rows, and several method choices are defensible; (3) spike #6 shows weight noise alone moves
   rankings (tau ≈ 0.62–0.89 at n=12, synthetic); (4) so the system reports rank intervals and method agreement,
   never a single leaderboard; (5) the 2025 backtest is a sanity check, not proof (|rho| must exceed ~0.58 at n=12).
3. `## Where noise enters` — Mermaid `flowchart LR` of the pipeline (Ingest → Scorer agents → Human checkpoint →
   Weights → Ranking → Report → Backtest) with a dashed edge (`-.->`) from a noise node into each stage:
   look-ahead leakage → Scorer agents; LLM sampling → Scorer agents; selection bias → Ingest;
   weight estimation → Weights; weight choice → Weights; normalization → Weights and Ranking;
   method choice → Ranking; small-n → Backtest.
4. `## The budget` — table with columns: Source | What it is | Where | How measured / reduced | Status | Source doc.
   One row each, in this order: LLM sampling noise; LLM error / unsupported evidence; look-ahead leakage;
   selection bias; weight estimation noise; weight choice; normalization choice; method choice (weighting × ranker);
   small-n backtest. Status values: built / library / planned / documented only. Use only the facts above.
5. `## Key numbers` — a short table of the spike #6 n=12 Gaussian row (TV and the four tau values) and the 0.58
   threshold, each with its source link and the "synthetic" caveat.
6. `## Why intervals and agreement, not a better single method` — 3–5 bullets: no method is known best at n=12;
   disagreement between methods is itself information (`mcdm.md` "Why these choices": "disagreement between them is itself a robustness signal");
   ranks in the middle are least reliable; bootstrap understates uncertainty with n≈12 because it only resamples
   observed companies; Dirichlet spread is hand-set.
7. `## Open questions` — calibrate `concentration`; K and aggregation rule for LLM samples; how to combine sources
   in the report; the threshold for calling two companies "not distinguishable".

Link every source with relative links (`../research/weight-stability-results.md`, `robustness.md`, `mcdm.md`,
`decisions.md`, `../SCOPE.md`).

**Verify**: `pytest -q tests/test_docs.py` → all pass (links resolve).

### Step 2: Link it

Add `- [uncertainty.md](uncertainty.md): every noise source, how it is measured, what is built` to the Blocks
list in `docs/architecture/overview.md`, after the robustness line.

**Verify**: `pytest -q && ruff check .` → pass.

## Done criteria

- [ ] `docs/architecture/uncertainty.md` exists; `grep -c "| " docs/architecture/uncertainty.md` → ≥ 12 (tables present)
- [ ] `grep -c "0.58" docs/architecture/uncertainty.md` → ≥ 1; `grep -ci "synthetic" docs/architecture/uncertainty.md` → ≥ 1
- [ ] `pytest -q` passes (link test included); `ruff check .` passes
- [ ] Only the two in-scope files changed
- [ ] `plans/README.md` row updated

## STOP conditions

- A number in a source doc differs from this plan and you cannot tell which is right → STOP and report both.
- `tests/test_docs.py` or `docs/architecture/robustness.md` is missing → STOP (dependencies not merged).

## Maintenance notes

- When the scorer, backtest or method-agreement report is built, flip its Status cell in the same PR.
- Reviewers: every number must trace to a linked source; no new claims.
