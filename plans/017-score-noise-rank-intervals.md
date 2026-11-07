# Plan 017: LLM score noise is propagated into a third rank interval (`score_noise`) in the engine, graph, report, GUI and docs

> **Executor instructions**: Follow this plan step by step. Run every verification command and confirm the
> expected result before moving to the next step. If anything in the "STOP conditions" section occurs, stop and
> report; do not improvise. When done, update the status row for this plan in `plans/README.md`, unless a reviewer
> dispatched you and told you they maintain the index.
>
> **Drift check (run first)**:
> `git diff --stat c31034f..HEAD -- src/maid app tests docs/architecture docs/INTERVIEW.md docs/WALKTHROUGH.md`
> must print nothing. If it prints anything, compare the "Current state" excerpts below with the live files; on a
> mismatch, STOP.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: LOW (additive: a new key `score_noise` next to `bootstrap`/`dirichlet`; existing outputs must stay bit-identical)
- **Depends on**: plans 005, 011, 012 (all DONE on `integration/prototype`)
- **Category**: direction (core of the project's noise argument)
- **Planned at**: commit `c31034f` (branch `integration/prototype`), 2026-11-02

## Why this matters

MAID's central claim is that a single leaderboard overstates certainty, so it reports rank intervals. Today the
intervals cover only **weight** uncertainty (bootstrap of companies, Dirichlet around the weights). The **LLM score
noise** is measured (the scorer draws K samples per company x criterion and stores them in state as `score_samples`)
but is thrown away after the median: `docs/architecture/robustness.md` ends with "Nothing here addresses LLM score
noise", and `docs/architecture/uncertainty.md` says "score noise not yet propagated into rank intervals". This plan
propagates it: re-draw the aggregated scores from their own K samples, recompute weights and ranks per draw, and
report a third, separate rank interval. After this, the demo shows how much of each company's rank uncertainty comes
from the scorer itself.

## Design (decided by the planner; implement exactly this)

- **What is resampled**: only LLM-scored cells of X that a human did **not** override. Quantitative cells are fixed.
  Overridden cells are fixed (the human value is treated as exact).
- **How**: per draw and per cell, take a with-replacement resample of size K from that cell's K samples and aggregate
  it with the **same rule the pipeline uses**: median, half rounded up, i.e. `floor(median + 0.5)`
  (see `maid.scoring.aggregate`). This is the nonparametric bootstrap of the aggregated score. Rejected alternatives
  (record them in decision D16, step 6): draw one of the K samples (models a single-sample scorer, overstates the noise
  of a median); a normal around the median with the stored std (needs rounding/clipping, assumes a shape).
- **Weights are recomputed on each perturbed matrix** (`weight_fn(Xd)`), because data-driven weights depend on the
  scores. The point rank is the rank of the original X under `weight_fn(X)` (same as the other two sources).
- **Separate source**: key `"score_noise"` in the result dict, next to `"bootstrap"` and `"dirichlet"`. Not mixed.
- **RNG**: drawn from the same `rng` in `robust_ranking`, **after** the bootstrap and Dirichlet draws, so the existing
  two sources stay bit-identical for a given seed. Cells are visited in `sorted()` key order for reproducibility.
- **Consequence to document**: with K=1 every cell has one sample, so the interval has zero width. That means "no
  information", not "certain".

A scratch prototype of this design on the demo data (seed 0, critic weights, TOPSIS, 500 draws) gave mean interval
widths (hi - lo) of 0.0 at k=1, 1.6 at k=5, 1.4 at k=15, so the k=5 demo shows visible but modest intervals.

## Current state

Files and roles:
- `src/maid/mcdm/robustness.py` (76 lines): pure rank-interval engine. Excerpts:
  ```python
  # line 1-2 (module docstring)
  """Rank intervals from two separate sources: bootstrap (weight-estimation noise) and Dirichlet perturbation (weight choice).
  Ranks use the convention 1 = best; ties share the better rank."""
  ```
  ```python
  # lines 42-58
  def rank_intervals(
      X: np.ndarray, weight_draws: np.ndarray, rank_fn, point_w: np.ndarray
  ) -> RankIntervals:
      """Rank the (original) X under each weight draw and summarize the rank distribution."""
      R = np.stack([ranks(rank_fn(X, w)) for w in weight_draws])  # (n_draws, n)
      n = X.shape[0]
      acceptability = np.empty((n, n))
      for r in range(1, n + 1):
          acceptability[:, r - 1] = (R == r).mean(axis=0)
      return RankIntervals(
          point=ranks(rank_fn(X, point_w)),
          median=np.median(R, axis=0),
          lo=np.percentile(R, 5, axis=0, method="lower"),
          hi=np.percentile(R, 95, axis=0, method="higher"),
          acceptability=acceptability,
          n_draws=len(weight_draws),
      )
  ```
  ```python
  # lines 61-76
  def robust_ranking(
      X, weight_fn, rank_fn, n_draws: int = 1000, concentration: float = 100.0, seed: int = 0
  ) -> dict[str, RankIntervals]:
      """Return {"bootstrap": ..., "dirichlet": ...}; point weights = weight_fn(X).

      The default concentration=100 is a placeholder for the maintainer to calibrate
      (weight sd ~0.035 when m=7, w=1/7); see docs/architecture/robustness.md.
      """
      X = np.asarray(X, dtype=float)
      rng = np.random.default_rng(seed)
      w = weight_fn(X)
      boot = bootstrap_weights(X, weight_fn, n_draws, rng)
      dirich = dirichlet_weights(w, n_draws, concentration, rng)
      return {
          "bootstrap": rank_intervals(X, boot, rank_fn, w),
          "dirichlet": rank_intervals(X, dirich, rank_fn, w),
      }
  ```
- `src/maid/scoring.py:31-35`, the aggregation rule to mirror (do NOT import `maid.scoring` from `maid.mcdm`; the
  engine must stay free of pipeline imports, so the rule is duplicated and a test pins them together):
  ```python
  def aggregate(samples: list[CriterionScore]) -> tuple[CriterionScore, float]:
      """Median score (half rounds up) with the first sample's evidence, plus the sample std as noise."""
      vals = np.array([s.score for s in samples], dtype=float)
      med = int(np.floor(np.median(vals) + 0.5))
  ```
- `src/maid/graph.py`: the pipeline. State key `score_samples` is `{"company|criterion": [K ints]}` (written by
  `score_qualitative`, line 72). `overrides` is a list of `ScoreOverride` (attributes `company`, `criterion`).
  `companies` is the row order of X, `criteria` the column order. Excerpts:
  ```python
  # lines 114-123
  def robustness(state: PipelineState) -> dict:
      """Rank intervals under bootstrap and Dirichlet weight perturbation."""
      settings = _settings(state)
      res = robust_ranking(
          np.array(state["matrix"]), WEIGHT_FNS[settings["weighting"]], topsis,
          n_draws=settings["n_draws"], concentration=settings["concentration"], seed=settings["seed"],
      )
      fields = ("point", "median", "lo", "hi", "acceptability")
      return {"robustness": {src: {f: getattr(r, f).tolist() for f in fields} | {"n_draws": r.n_draws}
                             for src, r in res.items()}}
  ```
  ```python
  # lines 126-142 (report)
      cs, st, rb = state["companies"], state["settings"], state["robustness"]
      top, sw = state["scores"]["topsis"], state["scores"]["saw"]
      bo, di = rb["bootstrap"], rb["dirichlet"]
      ...
          "| Rank | Company | TOPSIS | SAW | Bootstrap 90% rank | Dirichlet 90% rank | P(rank 1) Dirichlet |",
          "|---|---|---|---|---|---|---|",
      ]
      for r, c in enumerate(state["ranking"], 1):
          i = cs.index(c)
          lines.append(f"| {r} | {c} | {top[i]:.3f} | {sw[i]:.3f} | {bo['lo'][i]:.0f}-{bo['hi'][i]:.0f} | "
                       f"{di['lo'][i]:.0f}-{di['hi'][i]:.0f} | {di['acceptability'][i][0]:.2f} |")
  ```
- `src/maid/state.py:38`: `    robustness: dict  # {"bootstrap": {...}, "dirichlet": {...}} with lists`
- `src/maid/gui_data.py:68`: docstring of `interval_rows` says `(bootstrap or dirichlet)`. `interval_rows` and
  `acceptability_rows` are generic over the source key, so their code needs no change.
- `app/streamlit_app.py:134`: `    src = st.radio("Perturbation", ["bootstrap", "dirichlet"], horizontal=True)`
- Tests: `tests/test_robustness.py` (engine), `tests/test_demo.py` (end-to-end), `tests/test_gui_data.py`
  (`for src in ("bootstrap", "dirichlet"):` at line 61), `tests/test_gui_app.py` (Streamlit `AppTest`, skipped when
  streamlit is missing), `tests/test_docs.py` (relative Markdown links must resolve).

Conventions (from `CLAUDE.md`): short module docstrings, one-line function docstrings, compact code; do not reformat
existing code. Decision matrix is `X` with shape `(n, m)`; uppercase matrix names are intentional. Tests use plain
`assert` and seeded `np.random.default_rng(<int>)`; no network. The MCDM engine is pure functions (no LLM, no I/O).
Exemplar for engine style: the existing functions in `src/maid/mcdm/robustness.py`. Exemplar tests:
`tests/test_robustness.py`. Line length 110 (ruff).

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Setup (fresh worktree) | `python3 -m venv .venv && . .venv/bin/activate && pip install -e ".[dev,gui]"` | exit 0 |
| Tests | `pytest -q` | all pass (baseline at c31034f: 59 passed, 1 skipped without streamlit; with `[gui]` installed, 0 skipped) |
| Lint | `ruff check .` | `All checks passed!` |
| Demo | `python -m maid.demo` | prints a Markdown report |

## Scope

**In scope** (the only files you may modify):
- `src/maid/mcdm/robustness.py`
- `src/maid/mcdm/__init__.py` (export the new public function)
- `src/maid/graph.py` (`robustness` node, new helper `score_cells`, `report`)
- `src/maid/state.py` (one comment, line 38)
- `src/maid/gui_data.py` (one docstring, line 68)
- `app/streamlit_app.py` (Robustness tab: radio options and one caption)
- `tests/test_robustness.py`, `tests/test_demo.py`, `tests/test_gui_data.py`, `tests/test_gui_app.py`
- `docs/architecture/robustness.md`, `docs/architecture/uncertainty.md`, `docs/architecture/decisions.md`,
  `docs/architecture/graph.md`, `docs/architecture/overview.md`, `docs/INTERVIEW.md`, `docs/WALKTHROUGH.md`
- `plans/README.md` (status row only, unless told otherwise)

**Out of scope** (do NOT touch):
- `src/maid/scoring.py`: the aggregation rule stays where it is; the engine duplicates it (see Current state).
- `src/maid/mcdm/weights.py`, `src/maid/mcdm/ranking.py`: no change needed (constant columns are already handled).
- `bootstrap_weights`, `dirichlet_weights`, `ranks`, the `RankIntervals` dataclass fields: keep their behavior and
  signatures. Existing bootstrap/Dirichlet results must not change for any seed.
- `DEFAULT_SETTINGS` / `validate_settings`: no new setting (score noise always runs; it reuses `n_draws` and `seed`).
- `docs/img/*.png` screenshots, `docs/research/*`, `docs/SCOPE.md`, `README.md`, `CLAUDE.md`.
- The other plans' files.

## Git workflow

- Branch: `feat/score-noise-intervals`.
- Conventional commits, matching `git log` (e.g. `feat(mcdm): rank intervals from LLM score noise`,
  `feat(graph): wire score-noise intervals into robustness and report`, `docs: score noise as a third source (D16)`).
  Body: `Refs` is not needed (no issue for this plan).
- Do NOT push or open a PR.

## Steps

### Step 1: Engine: factor the summary out of `rank_intervals` (no behavior change)

In `src/maid/mcdm/robustness.py`, add a private helper above `rank_intervals` and make `rank_intervals` use it:

```python
def _summarize(R: np.ndarray, point: np.ndarray) -> RankIntervals:
    """Summarize a (n_draws, n) rank matrix: median, 90% interval and acceptability around the point ranks."""
    n = R.shape[1]
    acceptability = np.empty((n, n))
    for r in range(1, n + 1):
        acceptability[:, r - 1] = (R == r).mean(axis=0)
    return RankIntervals(
        point=point,
        median=np.median(R, axis=0),
        lo=np.percentile(R, 5, axis=0, method="lower"),
        hi=np.percentile(R, 95, axis=0, method="higher"),
        acceptability=acceptability,
        n_draws=R.shape[0],
    )


def rank_intervals(
    X: np.ndarray, weight_draws: np.ndarray, rank_fn, point_w: np.ndarray
) -> RankIntervals:
    """Rank the (original) X under each weight draw and summarize the rank distribution."""
    R = np.stack([ranks(rank_fn(X, w)) for w in weight_draws])  # (n_draws, n)
    return _summarize(R, ranks(rank_fn(X, point_w)))
```

**Verify**: `pytest -q tests/test_robustness.py` → 9 passed (unchanged count).

### Step 2: Engine: score-noise draws and intervals

In the same file, add after `bootstrap_weights` (before `_summarize`):

```python
def median_half_up(values) -> float:
    """Median with halves rounded up; the same rule as maid.scoring.aggregate."""
    return float(np.floor(np.median(values) + 0.5))


def score_noise_matrices(
    X: np.ndarray, cell_samples: dict, n_draws: int, rng: np.random.Generator
) -> np.ndarray:
    """(n_draws, n, m) copies of X; each cell (i, j) in cell_samples becomes the half-up median of a
    with-replacement resample of its K samples (bootstrap of the aggregated score). Other cells stay fixed."""
    n, m = X.shape
    out = np.repeat(X[None, :, :], n_draws, axis=0)
    for (i, j), s in sorted(cell_samples.items()):
        s = np.asarray(s, dtype=float)
        if not (0 <= i < n and 0 <= j < m):
            raise ValueError(f"cell ({i}, {j}) is outside X with shape {X.shape}")
        if s.ndim != 1 or s.size == 0 or not np.isfinite(s).all():
            raise ValueError(f"cell ({i}, {j}) needs a non-empty 1-D list of finite samples")
        idx = rng.integers(0, s.size, size=(n_draws, s.size))
        out[:, i, j] = np.floor(np.median(s[idx], axis=1) + 0.5)
    return out


def score_noise_intervals(
    X: np.ndarray, cell_samples: dict, weight_fn, rank_fn, n_draws: int, rng: np.random.Generator
) -> RankIntervals:
    """Rank each score-noise draw of X with weights recomputed on that draw; point = rank of X under weight_fn(X)."""
    X = np.asarray(X, dtype=float)
    draws = score_noise_matrices(X, cell_samples, n_draws, rng)
    R = np.stack([ranks(rank_fn(Xd, weight_fn(Xd))) for Xd in draws])
    return _summarize(R, ranks(rank_fn(X, weight_fn(X))))
```

Notes: the `np.floor(np.median(...) + 0.5)` inside `score_noise_matrices` is the vectorized form of `median_half_up`;
keep both (the test in step 4 pins `median_half_up` to `maid.scoring.aggregate`, and the test
`test_score_noise_matrices_use_half_up_median` pins the vectorized form). `sorted()` makes the draw order independent
of dict insertion order.

Change `robust_ranking` to accept the samples and add the third source **after** the other two draws:

```python
def robust_ranking(
    X, weight_fn, rank_fn, n_draws: int = 1000, concentration: float = 100.0, seed: int = 0,
    cell_samples: dict | None = None,
) -> dict[str, RankIntervals]:
    """Return {"bootstrap": ..., "dirichlet": ...} plus "score_noise" when cell_samples is given; point weights = weight_fn(X).

    cell_samples maps (row, column) of X to that cell's K sampled scores. The default concentration=100 is a
    placeholder for the maintainer to calibrate (weight sd ~0.035 when m=7, w=1/7); see docs/architecture/robustness.md.
    """
    X = np.asarray(X, dtype=float)
    rng = np.random.default_rng(seed)
    w = weight_fn(X)
    boot = bootstrap_weights(X, weight_fn, n_draws, rng)
    dirich = dirichlet_weights(w, n_draws, concentration, rng)
    out = {
        "bootstrap": rank_intervals(X, boot, rank_fn, w),
        "dirichlet": rank_intervals(X, dirich, rank_fn, w),
    }
    if cell_samples is not None:
        out["score_noise"] = score_noise_intervals(X, cell_samples, weight_fn, rank_fn, n_draws, rng)
    return out
```

(If the first docstring line exceeds 110 characters, ruff ignores E501 per `pyproject.toml`, so that is fine; keep it
on one line.)

Replace the module docstring (lines 1-2) with:

```python
"""Rank intervals from three separate sources: bootstrap (weight-estimation noise), Dirichlet perturbation
(weight choice) and score noise (bootstrap of the K LLM samples per cell). Ranks: 1 = best; ties share the better rank."""
```

In `src/maid/mcdm/__init__.py`, import and export `score_noise_intervals` (add it to the import from
`maid.mcdm.robustness` and to `__all__`).

**Verify**: `pytest -q tests/test_robustness.py && ruff check src` → 9 passed; `All checks passed!`

### Step 3: Graph: pass the samples, hold overrides fixed, extend the report

In `src/maid/graph.py`:

1. Add this helper just above `def robustness`:
   ```python
   def score_cells(state: PipelineState) -> dict[tuple[int, int], list[int]]:
       """K samples per LLM-scored cell of X, keyed (row, column); human-overridden cells are left out (held fixed)."""
       over = {(o.company, o.criterion) for o in state.get("overrides", [])}
       cs, cr = state["companies"], state["criteria"]
       out = {}
       for key, vals in state.get("score_samples", {}).items():
           company, criterion = key.split("|", 1)
           if (company, criterion) not in over:
               out[(cs.index(company), cr.index(criterion))] = vals
       return out
   ```
2. In `robustness`, change the docstring to
   `"""Rank intervals under bootstrap and Dirichlet weight perturbation, and under LLM score noise."""` and add
   `cell_samples=score_cells(state),` as the last keyword argument of the `robust_ranking(...)` call. The dict
   comprehension that converts results to lists already iterates over all keys; leave it.
3. In `report`:
   - `bo, di = rb["bootstrap"], rb["dirichlet"]` → `bo, di, sn = rb["bootstrap"], rb["dirichlet"], rb["score_noise"]`
   - Header row becomes
     `"| Rank | Company | TOPSIS | SAW | Bootstrap 90% rank | Dirichlet 90% rank | Score-noise 90% rank | P(rank 1) Dirichlet |",`
     and the separator `"|---|---|---|---|---|---|---|---|",` (8 columns).
   - Each data row gets `{sn['lo'][i]:.0f}-{sn['hi'][i]:.0f} | ` inserted between the Dirichlet interval and the
     P(rank 1) cell.
   - Directly after the table rows (before `lines += ["", "## Weights", ...]`), add:
     ```python
     lines += ["", "Score-noise intervals re-draw each LLM score from its K samples (median of a resample) and "
               "recompute weights; human-overridden scores are held fixed, and with k=1 the interval has zero width."]
     ```

In `src/maid/state.py` line 38, change the comment to
`# {"bootstrap": {...}, "dirichlet": {...}, "score_noise": {...}} with lists`.

**Verify**: `python -m maid.demo | head -12` → the table header contains `Score-noise 90% rank` and every data row has
8 cells; `pytest -q` → all pass (existing tests unchanged).

### Step 4: Tests

Add to `tests/test_robustness.py` (import `median_half_up`, `score_noise_intervals`, `score_noise_matrices` from
`maid.mcdm.robustness`; import `pytest`, `aggregate` from `maid.scoring` and `CriterionScore` from `maid.state`):

1. `test_median_half_up_matches_pipeline_aggregate`: for each of `[3, 4]`, `[2, 3, 4, 5]`, `[1, 9]`, `[5]`,
   `[1, 2, 2, 9, 9]`, assert `median_half_up(v) == aggregate([CriterionScore(company="Company A", criterion="x",
   score=s, evidence="e") for s in v])[0].score`.
2. `test_score_noise_matrices_touch_only_listed_cells`: `X = np.random.default_rng(3).random((5, 3))`,
   `cells = {(0, 1): [1, 5, 9], (2, 0): [3, 3, 3]}`, `D = score_noise_matrices(X, cells, 200, np.random.default_rng(0))`.
   Assert `D.shape == (200, 5, 3)`; a boolean mask of untouched cells equals X in every draw; `(D[:, 2, 0] == 3).all()`;
   `set(D[:, 0, 1]) <= {1.0, 5.0, 9.0}` and `len(set(D[:, 0, 1])) > 1`.
3. `test_score_noise_matrices_use_half_up_median`: `cells = {(0, 0): [4, 5]}` on any 2x2 X; with 500 draws every value
   is in `{4.0, 5.0}` (resample `[4, 4]` → 4, `[5, 5]` → 5, `[4, 5]` → median 4.5 → 5), and the share of 5.0 is
   about 0.75 (assert `0.65 < share < 0.85`).
4. `test_constant_samples_give_point_intervals`: `X = np.random.default_rng(4).integers(1, 10, (8, 4)).astype(float)`;
   `cells = {(i, j): [X[i, j]] * 5 for i in range(8) for j in (2, 3)}`;
   `ri = score_noise_intervals(X, cells, critic_weights, topsis, 100, np.random.default_rng(0))`; assert
   `np.array_equal(ri.lo, ri.point) and np.array_equal(ri.hi, ri.point)`.
5. `test_score_noise_bounds_and_acceptability`: `X = np.random.default_rng(5).integers(1, 10, (10, 4)).astype(float)`,
   `cells = {(i, 3): [max(1, X[i, 3] - 2), X[i, 3], min(9, X[i, 3] + 2)] for i in range(10)}`; result via
   `robust_ranking(X, critic_weights, topsis, n_draws=200, cell_samples=cells)["score_noise"]`; assert lo <= median <= hi,
   all in 1..10, acceptability rows sum to 1, `ri.point` equals `ranks(topsis(X, critic_weights(X)))`, and at least one
   `hi - lo > 0`.
6. `test_score_noise_does_not_change_other_sources`: same X and cells as test 5; `a = robust_ranking(X, critic_weights,
   saw, n_draws=200, seed=7)`, `b = robust_ranking(..., seed=7, cell_samples=cells)`; assert `"score_noise" not in a`,
   `"score_noise" in b`, and for `k in ("bootstrap", "dirichlet")` the `acceptability`, `lo` and `hi` arrays are equal.
7. `test_score_noise_reproducible_and_order_independent`: same X and cells; reversed dict
   `dict(reversed(list(cells.items())))`; with `seed=7` both give equal `score_noise.acceptability`.
8. `test_score_noise_rejects_bad_cells`: `pytest.raises(ValueError)` for cell `(10, 0)` on a 10x4 X, and for an empty
   sample list `{(0, 0): []}`.

Add to `tests/test_demo.py`:

9. `test_score_noise_intervals_in_demo`: `s = run_demo({"n_draws": 200})`; `r = s["robustness"]["score_noise"]`;
   assert `lo <= hi` for all companies, `any(hi > lo ...)` (verified by the planner: mean width 1.6 at k=5, seed 0),
   and `"Score-noise 90% rank" in s["report"]`.
10. `test_k1_score_noise_has_zero_width`: `r = run_demo({"n_draws": 100, "k": 1})["robustness"]["score_noise"]`;
    assert `r["lo"] == r["point"] and r["hi"] == r["point"]`.
11. `test_score_cells_skip_overrides`: `from maid.graph import score_cells`; run
    `s = run_demo({"n_draws": 50}, [{"company": "Company A", "criterion": "strategy_clarity", "score": 9, "reason": "r"}])`;
    `cells = score_cells(s)`; assert `len(cells) == 19` (10 companies x 2 qualitative criteria, minus 1 overridden),
    `(0, s["criteria"].index("strategy_clarity")) not in cells`, and `(0, s["criteria"].index("risk_disclosure")) in cells`.

In `tests/test_gui_data.py` line 61, change the tuple to `("bootstrap", "dirichlet", "score_noise")`. Add one line to
`test_acceptability_rows` or a new small test asserting `acceptability_rows(state, "score_noise")` is non-empty and
each company's shares sum to 1 (pattern: the existing `test_acceptability_rows`).

**Verify**: `pytest -q` → all pass; new tests: 8 in `test_robustness.py`, 3 in `test_demo.py`. `ruff check .` → clean.

### Step 5: GUI

In `app/streamlit_app.py`, Robustness tab (line 134):
- radio options become `["bootstrap", "dirichlet", "score_noise"]`.
- Directly after the radio line, add a caption that explains the selected source:
  ```python
      st.caption({"bootstrap": "Weight-estimation noise: weights recomputed on resampled companies.",
                  "dirichlet": "Weight-choice uncertainty: weights drawn around the point weights.",
                  "score_noise": "LLM score noise: each score re-drawn from its K samples, weights recomputed; "
                                 "overridden scores held fixed."}[src])
  ```
In `src/maid/gui_data.py` line 68, change `(bootstrap or dirichlet)` to `(bootstrap, dirichlet or score_noise)`.

Add to `tests/test_gui_app.py`:
```python
def test_score_noise_source_renders():
    at = AppTest.from_file("../app/streamlit_app.py", default_timeout=60).run()
    at.radio[0].set_value("score_noise").run()
    assert not at.exception
    assert any("LLM score noise" in c.value for c in at.caption)
```

**Verify**: `pytest -q tests/test_gui_app.py` → 4 passed (needs `pip install -e ".[gui]"`; if streamlit cannot be
installed, report that the file was skipped). Optionally `streamlit run app/streamlit_app.py` and check the tab.

### Step 6: Docs

Make these edits. Keep the surrounding text; match the existing tone (short, factual, no marketing).

1. `docs/architecture/robustness.md`
   - Responsibility line: `under two\nseparate sources of weight uncertainty.` → say "under three separate sources:
     two of weight uncertainty (bootstrap, Dirichlet) and one of LLM score noise".
   - Mermaid: add a third branch, e.g.
     `S[K samples per LLM score] --> SN[Bootstrap median per cell]`, `X --> SN`,
     `SN -->|recompute weights, rank each draw| RI3[RankIntervals: score_noise]`.
   - Heading `## The two sources` → `## The three sources`; add a table row:
     `| Score noise | LLM sampling noise of the aggregated (median-of-K) scores | `n_draws`, K (`settings.k`) | Small K understates the spread; K=1 gives zero width (no information, not certainty); overridden cells are held fixed; cells are resampled independently |`
   - `The two are reported separately, not mixed. In both, the original \`X\` is what gets ranked.` → "The three are
     reported separately, not mixed. Bootstrap and Dirichlet rank the original `X`; score noise ranks each perturbed
     `X` with weights recomputed on it. See D16 in [decisions.md](decisions.md)."
   - Known limitations: replace `Nothing here\naddresses LLM score noise (that comes from the K repeated runs).` with
     "Score noise treats the 1-9 scores as interval data (as the rest of the engine does) and assumes cells are
     independent."
   - Open questions: change "combine both sources" to "combine the sources".
2. `docs/architecture/uncertainty.md`, the "LLM sampling noise" row, Status cell: replace
   `score noise not yet propagated into rank intervals` with
   `built: score-noise rank intervals in the robustness node (bootstrap of the median of K; overrides held fixed; D16)`.
   In the "Why intervals and agreement" list, add one bullet: "Score-noise intervals with small K understate the
   spread, and K=1 gives zero width ([robustness.md](robustness.md), D16)."
3. `docs/architecture/decisions.md`: append at the end of the file:
   ```markdown

   ## D16. LLM score noise: bootstrap the median of the K samples, reported as a third rank interval
   - **Alternatives:** draw one of the K samples per cell; a normal around the median with the stored std; one simulation that mixes score and weight noise.
   - **Why:** the pipeline ranks the median of K, so the noise that matters is the sampling noise of that median; a with-replacement resample of the K samples, aggregated with the same half-up median, is the nonparametric bootstrap of exactly that statistic, stays on the 1-9 integer scale and needs no distribution assumption. Drawing one sample per cell would model a single-sample scorer and overstate the noise; a normal needs rounding and clipping and assumes a shape. Weights are recomputed on each draw because data-driven weights depend on the scores. Kept separate from D13's two sources so the report shows which kind of uncertainty drives an interval. SMAA also allows stochastic criterion values ([mcdm-noise.md](../research/mcdm-noise.md), abstract-only).
   - **Cost:** small K understates the spread and K=1 gives a zero-width interval (no information, not certainty); human-overridden cells are held fixed; quantitative criteria are treated as noise-free; cells are resampled independently.
   - **Status:** implemented and wired into the graph's `robustness` node (demo); K OPEN (D9).
   - **Revisit if:** real LLM samples turn out correlated across criteria of the same company (independent resampling would then understate the noise).
   ```
   Also add `, D16` where the doc lists decision ids, if it has such a list at the top (check with
   `head -5 docs/architecture/decisions.md`; if there is no list, skip).
4. `docs/architecture/graph.md`
   - Node table, `robustness` row: Reads `matrix`, `settings` → `matrix`, `settings`, `score_samples`, `overrides`,
     `companies`, `criteria`.
   - `- \`robustness\`: bootstrap and Dirichlet rank intervals, as lists.` →
     `- \`robustness\`: bootstrap, Dirichlet and score-noise rank intervals, as lists.`
5. `docs/architecture/overview.md` line 17: `(bootstrap + Dirichlet rank intervals)` →
   `(bootstrap, Dirichlet and score-noise rank intervals)`.
6. `docs/INTERVIEW.md` question 7: "There are two sources, reported separately: bootstrap ... placeholder of 100)."
   → three sources: keep the two existing descriptions and add "and score noise (each LLM score re-drawn as the median
   of a resample of its K samples, weights recomputed; overridden scores held fixed)". Add `, D16` next to the D13
   link reference in that answer (e.g. "[D13 and D16](architecture/decisions.md)").
7. `docs/WALKTHROUGH.md`
   - Line ~39: `bootstrap and Dirichlet 90% rank intervals` → `bootstrap, Dirichlet and score-noise 90% rank intervals`.
   - Line ~59: `choose bootstrap or Dirichlet;` → `choose bootstrap, Dirichlet or score noise;`.
   - The numbered list near line 183 that describes `robustness.py`: add a sub-bullet
     `- \`score_noise_intervals\` re-draws each LLM score from its K samples and ranks each perturbed \`X\` with weights recomputed (LLM score noise).`
     and change `- \`robust_ranking\` runs both and returns them separately.` to
     `- \`robust_ranking\` runs all three (score noise only when samples are passed) and returns them separately.`
   - Decisions line `D13 (two separate perturbations).` → `D13 (two separate weight perturbations), D16 (score noise).`
   - Question 6 near line 259: "Why are the bootstrap and Dirichlet intervals reported separately?" → "Why are the
     bootstrap, Dirichlet and score-noise intervals reported separately?" (keep the answer; add D16 next to D13).

**Verify**:
- `grep -rn "two sources\|two separate sources\|not yet propagated\|Nothing here" docs/architecture docs/INTERVIEW.md src/maid/mcdm/robustness.py` → no output.
- `grep -c "D16" docs/architecture/decisions.md` → at least 1.
- `pytest -q tests/test_docs.py` → 2 passed (links resolve, graph diagram still matches).

## Test plan

New tests (listed in step 4 and 5): 8 engine tests in `tests/test_robustness.py`, 3 pipeline tests in
`tests/test_demo.py`, a source tuple change plus one assertion in `tests/test_gui_data.py`, 1 `AppTest` in
`tests/test_gui_app.py`. Pattern: `tests/test_robustness.py` (plain functions, seeded RNGs, plain asserts). The key
regression guard is test 6: adding score noise must not change the bootstrap or Dirichlet results for a given seed.

## Done criteria

- [ ] `pytest -q` exits 0; with `[gui]` installed it reports 0 skipped and at least 72 passed (59 + 1 previously skipped
      GUI file now running its tests + the new ones; exact count may differ by the GUI file's test count, that's fine).
- [ ] `ruff check .` → `All checks passed!`
- [ ] `python -m maid.demo | grep -c "Score-noise 90% rank"` → `1`
- [ ] `python -c "from maid.demo import run_demo; s=run_demo({'n_draws':100}); print(sorted(s['robustness']))"` →
      `['bootstrap', 'dirichlet', 'score_noise']`
- [ ] `grep -rn "not yet propagated" docs` → no output
- [ ] `git diff --name-only c31034f..HEAD` lists only in-scope files.
- [ ] `plans/README.md` row for 017 updated (unless the reviewer maintains it).

## STOP conditions

Stop and report (do not improvise) if:
- The drift check shows changes and the excerpts above no longer match.
- Test 6 fails (the bootstrap/Dirichlet results change when `cell_samples` is passed): the RNG order is wrong; do not
  "fix" it by changing the expected values.
- Test 1 fails (`median_half_up` disagrees with `maid.scoring.aggregate`): the pipeline rule changed; report which
  input differs.
- `test_score_noise_intervals_in_demo` finds every interval has zero width at k=5 (the planner measured a mean width of
  1.6); report the widths instead of loosening the assertion.
- A full `python -m maid.demo` run takes more than 30 seconds (the planner expects a few seconds; 500 extra weight
  computations on a 10x6 matrix).
- Any change seems to require editing `src/maid/scoring.py`, `weights.py`, `ranking.py` or the settings schema.

## Maintenance notes

- When the real LLM scorer replaces the stub, `score_samples` must keep its shape (`"company|criterion"` -> list of K
  ints); `score_cells` depends on it and on `companies` / `criteria` being the row/column order of X.
- If the aggregation rule in `maid.scoring.aggregate` changes (e.g. to the mean), update `median_half_up` and the
  vectorized line in `score_noise_matrices` together; `test_median_half_up_matches_pipeline_aggregate` will fail first.
- Reviewers: check that `robust_ranking` draws score noise after bootstrap and Dirichlet (bit-identical old results),
  that overridden cells are excluded in `score_cells`, and that weights are recomputed per draw (not `w` reused).
- Deferred: a nested simulation that combines weight and score noise; calibrating K (D9); correlated noise across
  criteria of one company.
