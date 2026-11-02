# Plan 004: MCDM functions reject invalid input loudly, and the human-review step records validated overrides

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat c094993..HEAD -- src/maid/mcdm src/maid/state.py src/maid/graph.py tests/test_mcdm.py tests/test_scaffold.py tests/test_review.py`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition. (Plan 003 legitimately changes
> `entropy_weights` and `tests/test_mcdm.py`; that drift is expected — keep its changes.)

## Status

- **Priority**: P2
- **Effort**: S
- **Risk**: LOW
- **Depends on**: plans/003-entropy-normalization-variant.md (same files; land 003 first to avoid conflicts)
- **Category**: bug / tech-debt
- **Planned at**: commit `c094993`, 2026-11-02

## Why this matters

Two parts of the pipeline will soon receive real data, and both currently fail silently:

1. **MCDM inputs.** With one alternative, `entropy_weights` divides by `log(1) = 0` and gets NaN. The `d.sum() > _EPS`
   check is then False, so it **silently returns equal weights**. NaN or inf values in `X` (common when a ratio is
   missing in XBRL), a 1-D `X`, or a weight vector of the wrong length are never checked: they produce NaN scores or
   numpy broadcasting errors far from the cause. Real data arrives with the ingest step; the engine should refuse bad input at its boundary.
2. **Human-review overrides.** The architecture says: "H-->>G: resume(overrides + reasons)" and "Overrides are logged
   with a reason; they can later be used to measure where the LLM disagrees with the human" (`docs/architecture/overview.md` §4).
   Today `human_review` discards the resume value, and `PipelineState` has no field for overrides. Defining the
   contract now (score 1–9, mandatory reason, must refer to an existing score) keeps the later scorer and MCDM wiring honest.
3. **Checkpoint serialization.** LangGraph's checkpointer (installed `langgraph-checkpoint` 4.3.1) already logs
   "Deserializing unregistered type maid.state.CriterionScore from checkpoint. This will be blocked in a future version"
   for the Pydantic models in state. Once LangGraph enforces that, resuming after the interrupt will break. This plan
   registers the state models explicitly.

## Current state

- `src/maid/mcdm/weights.py` — functions `_minmax(X)`, `equal_weights(X)`, `entropy_weights(X, ...)`, `critic_weights(X)`;
  module constant `_EPS = 1e-12`. `entropy_weights` ends with
  `return d / d.sum() if d.sum() > _EPS else equal_weights(X)`; `critic_weights` ends with
  `return c / c.sum() if c.sum() > _EPS else equal_weights(X)`. Keep those fallbacks: they handle the legitimate
  "all criteria constant" case.
- `src/maid/mcdm/ranking.py` (entire file):
  ```python
  """Ranking methods. Return a score per alternative (higher = better)."""
  import numpy as np

  from maid.mcdm.weights import _minmax


  def saw(X: np.ndarray, w: np.ndarray) -> np.ndarray:
      """Simple Additive Weighting on min-max normalized values."""
      return _minmax(X) @ w


  def topsis(X: np.ndarray, w: np.ndarray) -> np.ndarray:
      """TOPSIS: relative closeness to the ideal solution (vector normalization)."""
      norm = np.sqrt((X**2).sum(axis=0))
      ...
  ```
- `src/maid/state.py` (entire file):
  ```python
  """Shared graph state. LLM-produced values always carry evidence; MCDM is deterministic."""
  from typing import TypedDict

  from pydantic import BaseModel, Field


  class CriterionScore(BaseModel):
      company: str  # anonymized label, e.g. "Company A"
      criterion: str
      score: int = Field(ge=1, le=9)
      evidence: str  # quote that must appear in the source filing


  class PipelineState(TypedDict, total=False):
      companies: list[str]
      quantitative: dict[str, dict[str, float]]  # company -> criterion -> value
      qualitative: list[CriterionScore]
      weights: dict[str, float]
      ranking: list[str]
      report: str
  ```
- `src/maid/graph.py` — relevant parts:
  ```python
  from langgraph.checkpoint.memory import MemorySaver
  ...
  def score_qualitative(state: PipelineState) -> dict:
      return {"qualitative": []}


  def human_review(state: PipelineState) -> dict:
      # Pauses the graph; resume with Command(resume=...) carrying overrides.
      interrupt({"qualitative": state.get("qualitative", [])})
      return {}
  ...
      return g.compile(checkpointer=MemorySaver())
  ```
- `tests/test_scaffold.py::test_graph_pauses_at_human_review_then_finishes` resumes with `Command(resume="ok")`.
  You will change that to the new payload format.
- Verified API (installed version): `from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer`;
  `JsonPlusSerializer(allowed_msgpack_modules=[("maid.state", "CriterionScore")])` removes the warning for that type;
  `MemorySaver(serde=...)` accepts it. Env var `LANGGRAPH_STRICT_MSGPACK=true` makes unregistered types get blocked now.
- Conventions: one-line docstrings, `ValueError` with a short message for bad input, pydantic v2 `Field(...)` constraints,
  tests with plain `assert` and `pytest.raises`.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Tests | `pytest -q` | all pass |
| Strict checkpoint mode | `LANGGRAPH_STRICT_MSGPACK=true pytest -q tests/test_scaffold.py tests/test_review.py` | all pass |
| Lint (if 001 done) | `ruff check .` | `All checks passed!` |

## Scope

**In scope**:
- `src/maid/mcdm/weights.py` (add `_check_matrix`; call it at the top of `entropy_weights`, `critic_weights`, `equal_weights`)
- `src/maid/mcdm/ranking.py` (add weight check; call it in `saw`, `topsis`)
- `src/maid/state.py`, `src/maid/graph.py`
- `tests/test_mcdm.py` (add tests), `tests/test_review.py` (create), `tests/test_scaffold.py` (only the resume payload)

**Out of scope**:
- Applying overrides to scores in the `mcdm` node. The `mcdm` node is still a stub; wiring comes with the scorer issue.
- Persisting overrides to disk, or a CLI for reviewing them.
- Any change to the math of the weighting/ranking functions for valid input. Outputs for valid input must be identical.
- `scripts/weight_stability.py`: it only passes valid input.

## Git workflow

- Base: the branch where plan 003 landed (or `main` once merged).
- Branch: `fix/mcdm-validation-overrides`. Commits e.g. `fix(mcdm): validate decision matrix and weights`,
  `feat: human-review override schema`. Do NOT push or open a PR unless instructed.

## Steps

### Step 1: Validate the decision matrix

In `weights.py`, add:

```python
def _check_matrix(X: np.ndarray) -> None:
    if X.ndim != 2 or X.shape[0] < 2 or X.shape[1] < 1:
        raise ValueError(f"X must be 2-D with >= 2 alternatives and >= 1 criterion, got shape {X.shape}")
    if not np.isfinite(X).all():
        raise ValueError("X contains NaN or inf; impute or drop missing criteria before weighting")
```

Call `_check_matrix(X)` as the first line of `equal_weights`, `entropy_weights`, `critic_weights`. Do **not** call it inside
`_minmax` (it's also used by `saw` and on large arrays in the spike; one check per public call is enough).

**Verify**: `pytest -q tests/test_mcdm.py` → all existing tests still pass.

### Step 2: Validate weights in the rankers

In `ranking.py`, import `_check_matrix` alongside `_minmax`, and add:

```python
def _check_weights(X: np.ndarray, w: np.ndarray) -> None:
    _check_matrix(X)
    if w.shape != (X.shape[1],):
        raise ValueError(f"w must have shape ({X.shape[1]},), got {w.shape}")
    if not np.isfinite(w).all() or (w < 0).any() or not np.isclose(w.sum(), 1.0, atol=1e-6):
        raise ValueError("w must be finite, non-negative and sum to 1")
```

Call it first in `saw` and `topsis`.

**Verify**: `pytest -q` → all pass; `python scripts/weight_stability.py > /dev/null` exits 0 (the spike still runs, ~12 s).

### Step 3: Tests for validation

Append to `tests/test_mcdm.py` (add `import pytest` at the top):
- `test_single_alternative_is_rejected`: `entropy_weights`, `critic_weights` each raise `ValueError` on `np.ones((1, 3))`.
- `test_nan_in_matrix_is_rejected`: a 3×2 matrix with one `np.nan` → `ValueError` from `entropy_weights`.
- `test_one_dimensional_matrix_is_rejected`: `np.arange(5.0)` → `ValueError` from `critic_weights`.
- `test_rankers_reject_bad_weights`: for `saw` and `topsis` with a valid 3×3 `X`: wrong length `np.full(2, .5)`,
  negative `np.array([1.5, -0.25, -0.25])`, not summing to 1 `np.full(3, 0.5)` → each raises `ValueError`.
- `test_all_constant_matrix_still_falls_back_to_equal_weights`: `np.ones((4, 3))` → both weight functions return `np.full(3, 1/3)` (this case is legitimate and must not raise).

**Verify**: `pytest -q tests/test_mcdm.py` → all pass.

### Step 4: Override schema in state

In `state.py`, add after `CriterionScore`:

```python
class ScoreOverride(BaseModel):
    """A human correction of one LLM score; the reason is mandatory so disagreements can be analyzed later."""
    company: str
    criterion: str
    score: int = Field(ge=1, le=9)
    reason: str = Field(min_length=1)
```

Add `overrides: list[ScoreOverride]` to `PipelineState` (after `qualitative`). Also add, at the end of the module:

```python
# Pydantic types stored in graph state; checkpoints must be allowed to restore them.
CHECKPOINT_TYPES = [("maid.state", "CriterionScore"), ("maid.state", "ScoreOverride")]
```

**Verify**: `python -c "from maid.state import ScoreOverride as S; S(company='Company A', criterion='c', score=5, reason='r')"` → exit 0.

### Step 5: Parse the resume payload in `human_review`

In `graph.py`, add a pure helper and use it:

```python
def parse_overrides(decision, qualitative: list[CriterionScore]) -> list[ScoreOverride]:
    """Resume payload: {"overrides": [{company, criterion, score, reason}, ...]}; {} or None means no changes."""
    if decision is None:
        return []
    if not isinstance(decision, dict):
        raise ValueError("resume payload must be a dict like {'overrides': [...]}")
    overrides = [ScoreOverride.model_validate(o) for o in decision.get("overrides", [])]
    known = {(s.company, s.criterion) for s in qualitative}
    unknown = [(o.company, o.criterion) for o in overrides if (o.company, o.criterion) not in known]
    if unknown:
        raise ValueError(f"overrides refer to scores that do not exist: {unknown}")
    return overrides


def human_review(state: PipelineState) -> dict:
    # Pauses the graph; resume with Command(resume={"overrides": [...]}).
    decision = interrupt({"qualitative": state.get("qualitative", [])})
    return {"overrides": parse_overrides(decision, state.get("qualitative", []))}
```

Import `CriterionScore, ScoreOverride, CHECKPOINT_TYPES` from `maid.state`. Change the compile line to:

```python
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
...
    serde = JsonPlusSerializer(allowed_msgpack_modules=CHECKPOINT_TYPES)
    return g.compile(checkpointer=MemorySaver(serde=serde))
```

In `tests/test_scaffold.py`, change only `Command(resume="ok")` → `Command(resume={"overrides": []})`.

**Verify**: `pytest -q` → all pass.

### Step 6: Tests for the review contract

Create `tests/test_review.py`:
- `test_no_payload_means_no_overrides`: `parse_overrides(None, []) == []` and `parse_overrides({}, []) == []`.
- `test_valid_override_is_parsed`: with `qualitative=[CriterionScore(company="Company A", criterion="moat", score=4, evidence="q")]`,
  `parse_overrides({"overrides": [{"company": "Company A", "criterion": "moat", "score": 7, "reason": "underrated"}]}, qualitative)`
  returns one `ScoreOverride` with `score == 7`.
- `test_override_without_reason_is_rejected`: `reason=""` → `pydantic.ValidationError`.
- `test_override_score_out_of_range_is_rejected`: `score=10` → `pydantic.ValidationError`.
- `test_override_for_unknown_score_is_rejected`: criterion not in `qualitative` → `ValueError`.
- `test_non_dict_payload_is_rejected`: `"ok"` → `ValueError`.
- `test_graph_records_overrides_after_resume`: build the graph; invoke with `{"companies": ["Company A"]}` and a thread id;
  resume with `Command(resume={"overrides": []})`; assert `final["overrides"] == []` and `"report" in final`.
  (The stub scorer yields no scores, so a non-empty override would correctly be rejected. Do not change the stub.)
- `test_checkpoint_serde_restores_state_models`: because the graph test above carries only empty lists, it never
  deserializes a model. Test the serializer directly:
  ```python
  serde = JsonPlusSerializer(allowed_msgpack_modules=CHECKPOINT_TYPES)
  state = {"qualitative": [CriterionScore(company="Company A", criterion="moat", score=4, evidence="q")],
           "overrides": [ScoreOverride(company="Company A", criterion="moat", score=7, reason="r")]}
  back = serde.loads_typed(serde.dumps_typed(state))
  assert isinstance(back["qualitative"][0], CriterionScore) and isinstance(back["overrides"][0], ScoreOverride)
  ```
  Under `LANGGRAPH_STRICT_MSGPACK=true` this fails if a type is missing from `CHECKPOINT_TYPES`. To confirm the check
  bites, temporarily drop `ScoreOverride` from the list, run the strict command, and see it fail; then restore it.
  If it does NOT fail with the entry removed, note that in your report (strict mode may be read at import time); keep the test anyway.

**Verify**: `pytest -q` → all pass, and `LANGGRAPH_STRICT_MSGPACK=true pytest -q tests/test_scaffold.py tests/test_review.py` → all pass.

## Test plan

Listed in Steps 3 and 6. Patterns: `tests/test_mcdm.py` (pure functions) and `tests/test_scaffold.py::test_graph_pauses_at_human_review_then_finishes`
(graph invoke/resume with a `thread_id`). Regressions covered: silent equal weights on n=1, NaN propagation,
discarded overrides, unregistered checkpoint types.

## Done criteria

- [ ] `pytest -q` → all pass (existing tests plus 5 in `test_mcdm.py` and 8 in `test_review.py`)
- [ ] `LANGGRAPH_STRICT_MSGPACK=true pytest -q` → all pass
- [ ] `python scripts/weight_stability.py > /dev/null` → exit 0
- [ ] `grep -n "_check_matrix(X)" src/maid/mcdm/weights.py` → 3 matches (one per public function)
- [ ] `grep -n "overrides" src/maid/state.py` → match in `PipelineState`
- [ ] `ruff check .` passes (if 001 landed)
- [ ] Only in-scope files changed; `plans/README.md` status row updated

## STOP conditions

- Any existing MCDM test changes its result after Steps 1–2 (validation must not alter valid-input behavior).
- `JsonPlusSerializer` does not accept `allowed_msgpack_modules`, or `MemorySaver` does not accept `serde=` (a LangGraph
  version change) → stop and report the installed versions (`pip show langgraph langgraph-checkpoint`).
- Strict-mode tests fail for a type not listed in `CHECKPOINT_TYPES` → add it only if it is defined in `maid.state`; otherwise stop.
- The spike script now raises `ValueError` → it is passing invalid input; report which input, don't loosen the checks.

## Maintenance notes

- Every new Pydantic model put into `PipelineState` must be added to `CHECKPOINT_TYPES`; strict-mode CI would catch a
  miss. Consider adding `LANGGRAPH_STRICT_MSGPACK=true` to the CI env (plan 001's workflow) as a follow-up.
- When the real scorer runs K repeated samples per (company, criterion), `CriterionScore` will need a sample index, and
  overrides will target the aggregated score. Revisit `parse_overrides`'s "known" check then.
- The `mcdm` node must apply overrides before building `X`; reviewers of that future PR should check that overridden
  scores (not raw LLM scores) feed the engine, and that the raw ones remain in state for the disagreement analysis.
