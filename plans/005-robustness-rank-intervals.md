# Plan 005: The MCDM engine reports rank intervals and rank acceptability under bootstrap and Monte Carlo weight perturbation

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat c094993..HEAD -- src/maid/mcdm tests/test_robustness.py docs/architecture/robustness.md docs/architecture/overview.md`
> Plans 003 and 004 legitimately change `weights.py`/`ranking.py` (a `normalization` parameter on
> `entropy_weights`; input checks `_check_matrix` / `_check_weights`). That drift is expected. Any other change
> to the excerpts below is a STOP condition.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: LOW (new module, nothing existing changes behavior)
- **Depends on**: plans/004-mcdm-input-validation-and-review-overrides.md (soft: land after it so the rankers already validate weights)
- **Category**: direction (build the next pipeline block, scoped as library + design doc; no graph wiring)
- **Planned at**: commit `c094993`, 2026-11-02

## Why this matters

With ~12 companies, the data-driven weights are noisy. The repo's own spike (#6) found that sample weights vs reference
weights change rankings substantially: Kendall tau 0.62–0.89 at n=12. The project therefore committed to reporting
**rank intervals instead of point ranks**:

- `docs/SCOPE.md` §5.6: "Sensitivity and robustness analysis: bootstrap and Monte Carlo weight perturbation, reporting
  rank intervals (SMAA-style) instead of only point ranks."
- `docs/architecture/decisions.md` D5: "Report rank intervals, not just a rank. Why: with 12 alternatives and noisy
  weights, a single rank overstates certainty."
- `docs/research/weight-stability-results.md`, "Consequences for the design": "Keep the bootstrap / Monte Carlo weight
  perturbation and rank intervals already in the scope."

This block can be built and fully unit-tested now. It is pure numpy, needs no data or LLM, and the graph's `robustness`
node is waiting for it. This plan builds the library function and documents it; wiring it into the graph comes later,
once real matrices exist.

## Current state

- `src/maid/mcdm/` today:
  - `weights.py`: `equal_weights(X)`, `entropy_weights(X, normalization="minmax")` (the parameter exists if plan 003 landed),
    `critic_weights(X)`. Each returns a 1-D array of length m summing to 1. `X` has shape `(n_alternatives, m_criteria)`, all benefit-type.
  - `ranking.py`: `saw(X, w)`, `topsis(X, w)`. Each returns a score per alternative, **higher = better**.
  - `__init__.py`:
    ```python
    from maid.mcdm.ranking import saw, topsis
    from maid.mcdm.weights import critic_weights, entropy_weights, equal_weights

    __all__ = ["saw", "topsis", "critic_weights", "entropy_weights", "equal_weights"]
    ```
- `src/maid/graph.py` has a stub `def robustness(state) -> dict: return {}`. **Leave it alone** (out of scope).
- `scipy` is already a runtime dependency (`pyproject.toml`); `scipy.stats.rankdata` is available.
- Exemplar style: `src/maid/mcdm/weights.py`, with a short module docstring, one-line function docstrings, numpy only, no I/O.
  Exemplar tests: `tests/test_mcdm.py` (plain functions, seeded `np.random.default_rng(<int>)`, plain `assert`).
- Doc style: `docs/architecture/mcdm.md` (a "Block:" title, a responsibility line, a mermaid flowchart, a method table,
  "Why these choices", "Known limitations"). Match it.

## Design (decided here; implement exactly this)

Two separate sources of uncertainty, reported separately (not mixed):

1. **Bootstrap (weight-estimation noise).** Resample the *rows* of `X` with replacement, recompute weights with the
   given `weight_fn` on the resample, then **rank the original `X`** with those weights. This isolates "what if we had
   observed a slightly different set of companies", matching the spike design.
2. **Dirichlet perturbation (weight-choice uncertainty).** Draw weight vectors `w' ~ Dirichlet(concentration * w)` around
   the point weights `w`, and rank `X` with each. `E[w'] = w`; `Var(w'_j) = w_j (1 - w_j) / (concentration + 1)`.
   Zero weights are floored to `1e-6` before multiplying (Dirichlet parameters must be > 0).

Ranks: `1 = best`, computed as `scipy.stats.rankdata(-scores, method="min").astype(int)` (ties share the better rank).

Result type:

```python
@dataclass(frozen=True)
class RankIntervals:
    point: np.ndarray          # (n,) rank under the point weights
    median: np.ndarray         # (n,) median rank over draws
    lo: np.ndarray             # (n,) 5th percentile rank (best plausible)
    hi: np.ndarray             # (n,) 95th percentile rank (worst plausible)
    acceptability: np.ndarray  # (n, n): [i, r-1] = share of draws in which alternative i got rank r (SMAA rank acceptability)
    n_draws: int
```

Percentiles use `np.percentile(..., method="lower")` for `lo` and `method="higher"` for `hi`, so the bounds are always
ranks that actually occurred. `median` uses `np.median` (it may be x.5).

Public API in `src/maid/mcdm/robustness.py`:

```python
def ranks(scores: np.ndarray) -> np.ndarray: ...
def dirichlet_weights(w: np.ndarray, n_draws: int, concentration: float, rng: np.random.Generator) -> np.ndarray: ...   # (n_draws, m)
def bootstrap_weights(X: np.ndarray, weight_fn, n_draws: int, rng: np.random.Generator) -> np.ndarray: ...             # (n_draws, m)
def rank_intervals(X: np.ndarray, weight_draws: np.ndarray, rank_fn, point_w: np.ndarray) -> RankIntervals: ...
def robust_ranking(X, weight_fn, rank_fn, n_draws: int = 1000, concentration: float = 100.0, seed: int = 0) -> dict[str, RankIntervals]:
    """Returns {"bootstrap": ..., "dirichlet": ...}; point weights = weight_fn(X)."""
```

`robust_ranking` creates one `rng = np.random.default_rng(seed)`, computes bootstrap draws first and Dirichlet draws
second (the order fixes reproducibility). Default `concentration=100` gives a weight standard deviation of about 0.035
when m=7 and w=1/7 (≈25% relative). This is a placeholder for the maintainer to calibrate (see Open questions); state that in its docstring.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| New tests | `pytest -q tests/test_robustness.py` | all pass |
| All tests | `pytest -q` | all pass |
| Lint (if 001 done) | `ruff check .` | `All checks passed!` |

## Scope

**In scope**:
- `src/maid/mcdm/robustness.py` (create)
- `src/maid/mcdm/__init__.py` (export `robust_ranking`, `rank_intervals`, `RankIntervals`)
- `tests/test_robustness.py` (create)
- `docs/architecture/robustness.md` (create)
- `docs/architecture/overview.md`: only the "Blocks" list at the bottom (add one line)

**Out of scope**:
- `src/maid/graph.py`: no wiring into the `robustness` node yet.
- `weights.py`, `ranking.py`: do not modify. If you think you need to, see STOP conditions.
- Compound bootstrap+Dirichlet sampling, PROMETHEE/VIKOR, plotting, report formatting.

## Git workflow

- Base: the branch where plan 004 landed (or `main` once merged).
- Branch: `feat/robustness`. Commit e.g. `feat(mcdm): rank intervals via bootstrap and Dirichlet weight perturbation`.
- Do NOT push or open a PR unless instructed.

## Steps

### Step 1: Write the tests first

Create `tests/test_robustness.py` with these tests (all use `topsis` and/or `saw` with `critic_weights` or `entropy_weights`):

1. `test_ranks_one_is_best_and_ties_share_rank`: `ranks(np.array([0.2, 0.9, 0.9, 0.1]))` equals `[3, 1, 1, 4]`.
2. `test_dirichlet_draws_are_valid_and_centered`: `w = np.array([0.5, 0.3, 0.2, 0.0])`, 5000 draws, concentration 100,
   `rng = np.random.default_rng(0)` → shape `(5000, 4)`, all `>= 0`, rows sum to 1 (`np.allclose`), column means within
   `0.01` of `w`.
3. `test_bootstrap_draws_shape_and_sum`: `X = np.random.default_rng(1).random((12, 5))`, 200 draws with `critic_weights`
   → shape `(200, 5)`, rows sum to 1.
4. `test_dominant_alternative_is_always_first`: `X = np.array([[9, 9, 9], [5, 5, 5], [1, 1, 1]], float)`; for both sources
   from `robust_ranking(X, equal_weights, topsis, n_draws=300)`: `acceptability[0, 0] == 1.0` and `lo[0] == hi[0] == 1`.
   (`equal_weights` ignores the data, so degenerate resamples such as three identical rows cannot break this test.)
5. `test_acceptability_rows_sum_to_one`: random `X` (seed 2, shape `(10, 6)`), both sources → `np.allclose(acc.sum(axis=1), 1)`.
6. `test_bounds_are_ordered`: same input → `(lo <= median).all() and (median <= hi).all()`, and every value in `[1, n]`.
7. `test_point_rank_matches_direct_ranking`: `point == ranks(topsis(X, critic_weights(X)))`.
8. `test_huge_concentration_collapses_interval`: `X = np.random.default_rng(0).random((8, 4))`,
   `rank_intervals(X, dirichlet_weights(w, 200, 1e10, rng), topsis, w)` with `w = critic_weights(X)` → `lo == hi == point` for all alternatives.
9. `test_reproducible_with_seed`: two calls of `robust_ranking(X, critic_weights, saw, n_draws=200, seed=7)` give identical
   `acceptability` arrays for both sources; `seed=8` gives a different bootstrap `acceptability` (assert `not np.array_equal`).

**Verify**: `pytest -q tests/test_robustness.py` → fails with `ImportError`/`ModuleNotFoundError` (module not created yet).

### Step 2: Implement `robustness.py`

Implement the Design section exactly. Notes:
- `bootstrap_weights`: `idx = rng.integers(0, n, size=n)` per draw; `weight_fn(X[idx])`.
- `rank_intervals`: `R = np.stack([ranks(rank_fn(X, w)) for w in weight_draws])` → shape `(n_draws, n)`;
  `acceptability[i, r-1] = (R[:, i] == r).mean()`, computed with a loop over `r in 1..n` or `np.apply_along_axis`; clarity over cleverness.
- `point_w` is used only for `point`.
- Module docstring: 2 lines naming the two sources and the rank convention (1 = best).

**Verify**: `pytest -q tests/test_robustness.py` → 9 passed.

### Step 3: Export and smoke-run

Add the three names to `src/maid/mcdm/__init__.py` imports and `__all__`.

**Verify**:
`python -c "import numpy as np; from maid.mcdm import robust_ranking, critic_weights, topsis; X=np.random.default_rng(0).random((12,7)); r=robust_ranking(X, critic_weights, topsis); print({k: (v.lo.tolist(), v.hi.tolist()) for k,v in r.items()})"`
→ prints a dict with keys `bootstrap` and `dirichlet`; each `lo`/`hi` list has 12 integers in 1..12. Runs in well under 10 s.
Then `pytest -q` → all pass.

### Step 4: Document the block

Create `docs/architecture/robustness.md` in the style of `docs/architecture/mcdm.md`:
- Title `# Block: Robustness (src/maid/mcdm/robustness.py)`, a responsibility line.
- Mermaid flowchart: `X` + `weight_fn` → bootstrap resamples → weight draws → rank original X; point w → Dirichlet draws → rank X; both → `RankIntervals`.
- Table of the two sources: what uncertainty each represents, its parameter (`n_draws`, `concentration`), and its caveat.
  Bootstrap with n≈12 understates uncertainty because it only resamples companies already observed. Dirichlet's spread is set by hand.
- How to read the output: `lo`–`hi` is a 90% rank interval; `acceptability[i, 0]` is "share of draws where i is ranked first".
- **Open questions** (copy verbatim):
  - Calibrate `concentration`: pick it so Dirichlet weight spread matches the bootstrap spread observed on the real matrix (or the spike's TV at n=12), instead of the placeholder 100.
  - Should the report combine both sources (e.g. Dirichlet around each bootstrap draw), or show them side by side?
  - Report format: rank intervals per company plus rank-1 acceptability; decide the threshold under which two companies are called "not distinguishable".
- "Known limitations": synthetic-only tests; min-max-based rankers make ranks depend on sample extremes; nothing here addresses LLM score noise (that comes from the K repeated runs).

Add to the "Blocks" list in `docs/architecture/overview.md`:
`- [robustness.md](robustness.md): rank intervals via bootstrap and weight perturbation (library implemented, not yet wired into the graph)`

**Verify**: `test -f docs/architecture/robustness.md && grep -c "Open questions" docs/architecture/robustness.md` → `1`.

## Test plan

Nine tests in `tests/test_robustness.py` (Step 1), modeled after `tests/test_mcdm.py`. They cover the rank convention and
ties, valid Dirichlet draws, valid bootstrap draws, a dominance sanity check, probability invariants, bound ordering, the
point rank, interval collapse at zero noise, and seeding.

## Done criteria

- [ ] `pytest -q tests/test_robustness.py` → 9 passed; `pytest -q` → all pass
- [ ] Step 3 smoke command prints both keys with valid rank lists
- [ ] `git diff --stat -- src/maid/mcdm/weights.py src/maid/mcdm/ranking.py src/maid/graph.py` → empty
- [ ] `docs/architecture/robustness.md` exists with an "Open questions" section; overview Blocks list links it
- [ ] `ruff check .` passes (if 001 landed)
- [ ] `plans/README.md` status row updated

## STOP conditions

- Test 4 fails because a weight function raises on a degenerate bootstrap resample (e.g. all rows identical) → report;
  do not add special cases in `weights.py`.
- Test 8 does not collapse even at `1e10` → likely exact score ties in `topsis`; report the tied indices rather than changing the test data.
- You find yourself wanting to change `topsis`/`saw` signatures or add a `rank_fn` adapter in `ranking.py` → stop.
- Runtime of the Step 3 smoke command exceeds 30 s → report; do not vectorize speculatively.

## Maintenance notes

- Wiring into `graph.py`'s `robustness` node needs the real decision matrix, criterion names, and company labels in
  `PipelineState`. That is a separate issue once ingest exists. `RankIntervals` holds arrays indexed by row order, so the
  caller must keep the row → company mapping.
- If plan 003's default entropy variant changes, nothing here changes. `weight_fn` is injected (use `functools.partial(entropy_weights, normalization="sum")`).
- Reviewers: check that bootstrap ranks the **original** `X` (not the resample) and that `lo`/`hi` are actual observed ranks.
