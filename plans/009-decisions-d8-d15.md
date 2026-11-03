# Plan 009: decisions.md answers the "why X and not Y" questions for rankers, scale, normalization, metrics, perturbation, model and ML

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat 258af88..HEAD -- docs/architecture/decisions.md`
> Expect no changes. If changed, check that D1–D7 still exist and no D8+ exists; otherwise STOP.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: LOW (docs only)
- **Depends on**: PR #13 merged (D13 links `robustness.md`); plan 006 (link test)
- **Category**: docs
- **Planned at**: commit `258af88`, 2026-11-02

## Why this matters

`docs/architecture/decisions.md` is the project's ADR log ("Format: decision, alternatives, why, cost. Written so
each can be defended in an interview."). It has D1–D7 but is missing the choices an interviewer will ask about
most: why TOPSIS and SAW, why a 1–9 scale, why only benefit criteria, which normalization, why Kendall tau, why
Dirichlet perturbation, why DeepSeek, and why not train an ML model. Several of these are still open; recording
them honestly as open is better than leaving them unstated.

## Current state

`docs/architecture/decisions.md` format (exemplar, D4 and D5 verbatim):

```markdown
## D4. Data-driven weights (entropy, CRITIC), no AHP in v1
- **Alternatives:** AHP with my own pairwise judgments; fixed equal weights.
- **Why:** simplicity and less subjective input. **Cost:** noisy weights at n~12 (see spike #6) and no expert knowledge. Mitigated by perturbation and rank intervals. Entropy variant (min-max vs column-sum) is an open sub-decision; spike #6 compares them.

## D5. Report rank intervals, not just a rank
- **Why:** with 12 alternatives and noisy weights, a single rank overstates certainty.
- **Cost:** harder to read than a leaderboard.
```

The file ends after `## D7. Cache everything on disk` (Why + Cost bullets).

## Content to add (decided by the planner; write it, do not change the substance)

Add D8–D15 after D7, same format: `- **Alternatives:**`, `- **Why:**`, `- **Cost:**`, plus two new optional bullets
used in this batch: `- **Status:**` (decided / OPEN) and `- **Revisit if:**`. Keep each decision to 4–7 lines.
Keep `[abstract-only]` markers where given. Use relative links.

**D8. Rankers: SAW and TOPSIS now; PROMETHEE II next; VIKOR later**
- Alternatives: VIKOR, PROMETHEE II, ELECTRE, letting the LLM rank (rejected by D1).
- Why: SAW is the transparent baseline and was the more stable ranker under weight noise in spike #6
  ([weight-stability-results.md](../research/weight-stability-results.md)); comparative studies report SAW/WSM
  highly correlated with other methods (Mulliner et al. 2016, WSM–TOPSIS ≈ 0.86) [abstract-only,
  [mcdm-noise.md](../research/mcdm-noise.md)]. TOPSIS adds a distance-to-ideal view. PROMETHEE II before VIKOR
  because VIKOR's output is a compromise set rather than a strict order (UNVERIFIED in mcdm-noise.md).
- Cost: both are compensatory (a high score on one criterion offsets a low one); TOPSIS was less stable under
  weight noise in spike #6; no outranking method yet. Status: SAW/TOPSIS decided; second family OPEN.
- Revisit if: TOPSIS and SAW disagree on the top 3 on real data.

**D9. LLM scores: integer 1–9 with an evidence quote, K samples aggregated**
- Alternatives: continuous 0–100; pairwise comparisons by the LLM; yes/no checklists.
- Why: anchored ordinal levels are easier to write rubrics for and to review; an odd scale has a neutral midpoint;
  the schema enforces range and evidence (`src/maid/state.py`: `score: int = Field(ge=1, le=9)`, `evidence: str`).
  Research suggests averaging several sampled scores tracks humans better than one greedy score
  (Yamauchi et al. 2025) [abstract-only, [llm-agents-finance.md](../research/llm-agents-finance.md)].
- Cost: coarse; MCDM treats an ordinal score as interval data. Status: K (research suggests ≥5) and the
  aggregation rule (median vs mean) are OPEN.
- Revisit if: score variance across K runs is larger than one scale step for most criteria.

**D10. All criteria benefit-type (higher is better)**
- Alternatives: support cost-type criteria inside each method.
- Why: one code path for every weighting/ranking function, fewer sign bugs; documented in
  `src/maid/mcdm/weights.py` module docstring ("flip cost criteria before calling").
- Cost: how a cost criterion is flipped (negation vs reciprocal) is itself a choice that changes min-max results;
  it must be recorded per criterion when criteria are defined (issue #3). Status: decided.

**D11. Normalization: min-max for SAW, CRITIC and entropy (default); vector for TOPSIS**
- Alternatives: z-score; column-sum (textbook entropy); log.
- Why: each is the standard pairing for its method; min-max maps every criterion to [0, 1].
- Cost: min-max depends on the sample's extremes, so adding/removing a company can change weights and ranks
  ([mcdm.md](mcdm.md) Known limitations); normalization choice changes rankings in published reanalyses
  [abstract-only, mcdm-noise.md]. Status: entropy variant (min-max vs sum) OPEN; spike #6 compares them.

**D12. Kendall tau as the primary ranking-comparison metric; Spearman secondary**
- Alternatives: Spearman only; rank-biased overlap (RBO, top-weighted).
- Why: tau counts agreeing vs disagreeing pairs, which is easy to explain and handles ties; recommended for small n
  in [mcdm-noise.md](../research/mcdm-noise.md) §2 item 6; SCOPE §6.
- Cost: not top-weighted (a swap at rank 1 counts the same as at rank 11); tau values look lower than Spearman
  for the same data, which can confuse readers. Revisit if: the report cares mostly about the top 3 (then add RBO).

**D13. Weight uncertainty: bootstrap and Dirichlet perturbation, reported separately**
- Alternatives: perturb each weight by ±x% and renormalize; uniform weights on the simplex (classic SMAA with no
  weight information); one combined simulation.
- Why: bootstrap measures estimation noise from having only ~12 companies; Dirichlet(concentration × w) stays on
  the simplex, is centred on the point weights and has one spread parameter. Keeping them separate shows which kind
  of uncertainty drives a rank interval ([robustness.md](robustness.md)).
- Cost: bootstrap understates uncertainty at n≈12 (it only resamples observed companies); `concentration`
  (placeholder 100) is hand-set. Status: implemented as a library; calibration OPEN.

**D14. Model: DeepSeek (`deepseek-flash`) for the pipeline**
- Alternatives: Claude or GPT models; an older open-weight model with an earlier cutoff.
- Why: budget (SCOPE §8); cheapest option with JSON output, tool calls and a 1M context
  ([model-cutoff.md](../research/model-cutoff.md) §5).
- Cost: no published knowledge cutoff, likely after the 2024-12-31 decision date (look-ahead risk, D3); the alias
  was re-pointed on 2026-10-17, so the dated version must be pinned and logged per run (not done yet).
  Status: decided for v1; older-model ablation OPEN (SCOPE §9).

**D15. No trained predictive (ML) model**
- Alternatives: train a regressor/classifier from features to 2025 returns.
- Why: ~12 companies per sector-year is not a training set; the research question is whether LLM-made scores give
  a stable, robust, informative MCDM ranking, not return prediction (SCOPE §1); trading advice is a non-goal (SCOPE §7).
- Cost: no learned weighting; the backtest only checks association, and with n=12 only a strong one
  (|rho| > ~0.58) is distinguishable from chance.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Tests | `pytest -q` | all pass |
| Lint | `ruff check .` | `All checks passed!` |

## Scope

**In scope**: `docs/architecture/decisions.md` (append D8–D15; you may add one sentence to the intro saying
"Status: OPEN marks decisions not yet made"). **Out of scope**: editing D1–D7, any other file.

## Git workflow

Branch `docs/decisions-d8-d15`. Commit `docs(architecture): record decisions D8-D15`, ending with
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. No push/PR unless instructed.

## Steps

### Step 1: Append D8–D15

Write them as specified above, in order.

**Verify**: `grep -c "^## D" docs/architecture/decisions.md` → `15`; `grep -c "OPEN" docs/architecture/decisions.md` → ≥ 5.

### Step 2: Check links and lint

**Verify**: `pytest -q && ruff check .` → pass (the link test from plan 006 checks the new relative links).

## Done criteria

- [ ] 15 decision headings; D1–D7 unchanged (`git diff main -- docs/architecture/decisions.md` shows only additions plus at most one intro sentence)
- [ ] `pytest -q` and `ruff check .` pass
- [ ] `plans/README.md` row updated

## STOP conditions

- A cited fact (e.g. `Field(ge=1, le=9)` in `state.py`, the module docstring in `weights.py`, "it moved on 2026-10-17" in `model-cutoff.md` §5) is not found where stated → STOP and report.
- `docs/architecture/robustness.md` missing → STOP.

## Maintenance notes

- When an OPEN item is decided, edit its Status line and add the evidence; do not delete the alternatives.
