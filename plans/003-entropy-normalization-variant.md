# Plan 003: Entropy weighting offers the textbook (sum-normalized) variant, and the spike/docs say which variant produced which result

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat c094993..HEAD -- src/maid/mcdm tests/test_mcdm.py scripts/weight_stability.py docs/architecture/mcdm.md docs/architecture/decisions.md docs/research/weight-stability-results.md`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED (touches a core method and research conclusions; the default behavior must NOT change in this plan)
- **Depends on**: plans/001-ci-lint-claude-md.md (soft)
- **Category**: bug (methodology)
- **Planned at**: commit `c094993`, 2026-11-02

## Why this matters

`entropy_weights` min-max-normalizes each criterion to [0, 1] **before** computing Shannon entropy. That is one
variant found in the literature, but the textbook entropy weight method normalizes raw positive values by
column sum (`p_ij = x_ij / Σ_i x_ij`). The two variants can disagree completely. On the repo's own test matrix
`[[1,1],[1,2],[1,3],[1,4],[2,5]]` (columns `[1,1,1,1,2]` and `[1,2,3,4,5]`):

- current min-max variant → weights **[0.830, 0.170]** (the single-outlier column dominates)
- sum-normalized variant → weights **[0.289, 0.711]** (the evenly spread column dominates)

The test `test_entropy_rewards_concentration_not_spread` and the table in `docs/architecture/mcdm.md` describe the
first behavior as a "known property" of entropy. It is a property of the **min-max variant**: min-max maps the
smallest value to ~0, so one outlier makes the column look maximally concentrated. The spike #6 conclusions
("entropy noisier than CRITIC", hypothesis 5 "weights barely converge … min-max normalization") were all produced
with this variant. Design decision D4 relies on them.

This plan does **not** pick a winner. It makes the variant explicit, adds the textbook variant, reruns the spike with
both, and corrects the docs so the research write-up is accurate. Choosing the default is left to the maintainer.

## Current state

- `src/maid/mcdm/weights.py` (relevant part):
  ```python
  """Objective (data-driven) criterion weighting. All criteria are assumed benefit-type
  (higher is better); flip cost criteria before calling. Input: matrix X, shape (n_alternatives, m_criteria)."""
  import numpy as np

  _EPS = 1e-12


  def _minmax(X: np.ndarray) -> np.ndarray:
      lo, hi = X.min(axis=0), X.max(axis=0)
      return (X - lo) / np.where(hi - lo < _EPS, 1.0, hi - lo)
  ...
  def entropy_weights(X: np.ndarray) -> np.ndarray:
      """Shannon-entropy weights: criteria whose values vary more across alternatives get more weight."""
      n = X.shape[0]
      P = _minmax(X) + _EPS  # shift to strictly positive so ln() is defined
      P = P / P.sum(axis=0)
      e = -(P * np.log(P)).sum(axis=0) / np.log(n)
      d = 1.0 - e
      return d / d.sum() if d.sum() > _EPS else equal_weights(X)
  ```
- `src/maid/mcdm/__init__.py` exports `saw, topsis, critic_weights, entropy_weights, equal_weights`.
- `tests/test_mcdm.py:18-21`:
  ```python
  def test_entropy_rewards_concentration_not_spread():
      # Known property: one outlier value (low entropy) outweighs an evenly spread criterion.
      X = np.column_stack([[1, 1, 1, 1, 2], [1, 2, 3, 4, 5]]).astype(float)
      assert entropy_weights(X)[0] > entropy_weights(X)[1]
  ```
  `tests/test_mcdm.py:13-15` checks a constant column gets ~0 weight — must hold for both variants.
- `scripts/weight_stability.py` — spike #6 simulation. Runs in ~12 s. Key facts:
  - `population(rng, skewed)` returns Gaussian data (contains **negative** values, min ≈ −8.7) when
    `skewed=False`, and log-normal (strictly positive) data when `skewed=True`. The `+ 1e-9` with the comment
    "keep positive for TOPSIS vector norm" does NOT make Gaussian data positive. (TOPSIS still works, because
    vector normalization is just a positive per-column scale factor. Fix only the comment.)
  - It prints two markdown tables (Gaussian, log-normal) with columns
    `n | entropy TV | CRITIC TV | entropy→TOPSIS tau | entropy→SAW tau | CRITIC→TOPSIS tau | CRITIC→SAW tau`.
  - Seeded: `rng = np.random.default_rng(42)` in `run()`.
- `docs/research/weight-stability-results.md` contains those tables plus a "What the numbers say" list (items 1–5)
  and "Consequences for the design".
- `docs/architecture/mcdm.md` weighting table, Entropy row, Weakness column says:
  "Rewards concentration, so a single outlier can dominate (test `test_entropy_rewards_concentration_not_spread`).
  Noisier than CRITIC at n=12 in our simulation".
- `docs/architecture/decisions.md` D4: "**Cost:** noisy weights at n~12 (see spike #6) and no expert knowledge."
- Conventions: pure numpy functions, `X` shape `(n, m)`, one-line docstrings, tests with plain `assert` and
  seeded `np.random.default_rng(<int>)`.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Tests | `pytest -q` | all pass |
| MCDM tests | `pytest -q tests/test_mcdm.py` | all pass |
| Spike | `python scripts/weight_stability.py > $TMPDIR/spike.md` | exit 0, ~12–30 s |
| Lint (if 001 done) | `ruff check .` | `All checks passed!` |

## Scope

**In scope**:
- `src/maid/mcdm/weights.py` (`entropy_weights` only)
- `tests/test_mcdm.py`
- `scripts/weight_stability.py`
- `docs/research/weight-stability-results.md`
- `docs/architecture/mcdm.md` (Entropy row + "Known limitations")
- `docs/architecture/decisions.md` (D4 only: append one sentence)

**Out of scope**:
- `critic_weights`, `_minmax`, `ranking.py` — CRITIC conventionally uses min-max; leave it.
- Changing the **default** of `entropy_weights`. Its default output for existing calls must be bit-identical.
- Any interpretation beyond what the new numbers show. Don't declare one variant "correct".

## Git workflow

- Base: `feat/weight-stability-spike` if not merged into `main`, else `main`.
- Branch: `fix/entropy-variant`. Commits e.g. `feat(mcdm): add sum-normalized entropy variant`, `docs: rerun spike #6 with both entropy variants`. Body: `Refs #6`.
- Do NOT push or open a PR unless instructed.

## Steps

### Step 1: Add the `normalization` parameter

Change the signature to
`def entropy_weights(X: np.ndarray, normalization: str = "minmax") -> np.ndarray:` and implement:

- `"minmax"`: the current code path, unchanged.
- `"sum"`: require `np.all(X > 0)`, else `raise ValueError("sum-normalized entropy needs strictly positive values")`;
  then `P = X / X.sum(axis=0)` and the same entropy/divergence/normalize lines. (Values are positive, so no `_EPS` shift is needed.)
- anything else: `raise ValueError(f"unknown normalization: {normalization!r}")`.

Update the docstring to one or two lines that name both variants and say min-max is "sensitive to the sample min/max".

**Verify**: `python -c "import numpy as np; from maid.mcdm import entropy_weights as e; X=np.column_stack([[1,1,1,1,2],[1,2,3,4,5]]).astype(float); print(e(X).round(3), e(X,'sum').round(3))"`
→ `[0.83 0.17] [0.289 0.711]`

### Step 2: Fix the tests so they state the variant

In `tests/test_mcdm.py`:
- Rename `test_entropy_rewards_concentration_not_spread` → `test_minmax_entropy_rewards_single_outlier` and change the comment to:
  `# Min-max variant: the outlier is mapped to 1 and the rest to ~0, so the column looks maximally concentrated.`
- Add `test_sum_entropy_prefers_spread_on_same_data`: same `X`; assert `entropy_weights(X, "sum")[1] > entropy_weights(X, "sum")[0]`
  and `np.allclose(entropy_weights(X, "sum"), [0.289, 0.711], atol=1e-3)`.
- Add `test_sum_entropy_rejects_nonpositive`: `pytest.raises(ValueError)` for a matrix containing a `0.0`.
- Add `test_entropy_unknown_normalization_raises`.
- Extend `test_weights_sum_to_one_and_nonnegative` to also call `entropy_weights(X, "sum")` (its `X` is `rng.random`, positive except with probability ~0; if it ever contains 0, add `+ 0.01`).
- Extend `test_entropy_gives_zero_weight_to_constant_criterion` to check the `"sum"` variant too.

**Verify**: `pytest -q tests/test_mcdm.py` → all pass (5 original tests, one renamed, plus 3 new ones).

### Step 3: Save the baseline spike output, then extend the script

First, before editing: `python scripts/weight_stability.py > $TMPDIR/spike_before.md`.

Then in `scripts/weight_stability.py`:
- Fix the comment on `return X + 1e-9` to: `# tiny offset; Gaussian data still has negative values (fine for TOPSIS/SAW, not for sum-entropy)`.
- In `run(skewed)`, additionally compute the sum-normalized entropy **only when `skewed` is True** (Gaussian data is
  not positive): `true_s = entropy_weights(P, "sum")`, `s = entropy_weights(S, "sum")`, collecting `sum_tv`,
  `sum_topsis`, `sum_saw` the same way as `ent_*`.
- In `table(rows)`, when the rows include `sum_tv`, append three columns: `sum-entropy TV | sum-entropy→TOPSIS tau | sum-entropy→SAW tau`.
  For the Gaussian table, leave them out (do not print fake numbers).
- Do not change `M, POP, TRIALS, NS`, the seed, or the order of existing `rng` calls (the sum-variant needs no extra
  random draws, so the existing columns must reproduce exactly).

**Verify**: `python scripts/weight_stability.py > $TMPDIR/spike_after.md` exits 0, and the existing columns match the
baseline: for each table row, the first 7 cells in `spike_after.md` are identical to `spike_before.md`
(check with `diff <(cut -d'|' -f1-8 $TMPDIR/spike_before.md) <(cut -d'|' -f1-8 $TMPDIR/spike_after.md)` → no output).

### Step 4: Update the results doc with what the numbers actually show

In `docs/research/weight-stability-results.md`:
- In "Method", add one line: "Entropy is computed with min-max pre-normalization unless marked *sum-entropy*
  (textbook column-sum normalization, positive data only, so log-normal regime only)."
- Replace the log-normal table with the new one (extra columns). Leave the Gaussian table unchanged.
- Add item 6 under "What the numbers say": compare sum-entropy TV and tau with min-max entropy at n=12 and n=200, using the
  printed numbers, in 2–3 sentences. State plainly whether hypothesis 5 (weights barely converge because of min-max)
  gets support: if sum-entropy TV falls clearly faster with n than min-max entropy TV, say "consistent with hypothesis 5";
  otherwise say "not supported in this run". Do not go beyond that.
- Edit item 2/3 wording so "entropy" reads "min-max entropy".

**Verify**: `grep -c "sum-entropy" docs/research/weight-stability-results.md` → ≥ 3.

### Step 5: Correct the architecture docs

- `docs/architecture/mcdm.md`, Entropy row, Weakness column: replace the first sentence with
  "With min-max pre-normalization (current default) a single outlier can dominate (test `test_minmax_entropy_rewards_single_outlier`);
  the textbook sum-normalized variant (`normalization="sum"`, positive data only) does not do this."
  Keep the "Noisier than CRITIC at n=12" clause but prefix it with "min-max variant:".
- In "Known limitations", add: "Default entropy variant is not yet decided (min-max vs sum); see spike #6 results."
- `docs/architecture/decisions.md` D4: append "Entropy variant (min-max vs column-sum) is an open sub-decision; spike #6 compares them."

**Verify**: `grep -n "normalization=\"sum\"" docs/architecture/mcdm.md` → 1 match; `pytest -q` → all pass.

## Test plan

New/changed tests are listed in Step 2. Pattern: the existing functions in `tests/test_mcdm.py`. The regression this
plan protects against: the default (`minmax`) output changing — `test_minmax_entropy_rewards_single_outlier` plus the
unchanged-columns diff in Step 3 cover it.

## Done criteria

- [ ] `pytest -q` → all pass; `tests/test_mcdm.py` has 8 tests
- [ ] `python -c "...see Step 1..."` prints `[0.83 0.17] [0.289 0.711]`
- [ ] Step 3 column diff is empty (existing spike numbers unchanged)
- [ ] `grep -rn "rewards_concentration_not_spread" .` (excluding `plans/`) → no matches
- [ ] `ruff check .` passes (if plan 001 landed)
- [ ] Only in-scope files changed (`git status`)
- [ ] `plans/README.md` status row updated

## STOP conditions

- The Step 1 verify prints anything other than `[0.83 0.17] [0.289 0.711]` → the code drifted; stop.
- The Step 3 column diff is non-empty → you changed the random stream or existing logic; revert and stop if you can't find why.
- The log-normal sample `S` turns out to contain a non-positive value (sum-variant raises inside the script) → stop and report; do not clip values.
- You feel the need to change the default variant or rewrite research conclusions beyond item 6 → stop; that is the maintainer's call.

## Maintenance notes

- Once the maintainer picks a default, change it in one place (`entropy_weights` signature) and update tests 1-for-1; the
  robustness module (plan 005) takes a weight function as a parameter, so it is unaffected.
- Sum-entropy is not translation-invariant: shifting data to make it positive changes weights. If real criteria can be
  zero or negative (e.g. net margin), the sum variant needs an explicit, documented transformation — not an ad-hoc shift.
- Reviewers: check that the Gaussian table is byte-identical to before and that item 6 claims only what the numbers show.
