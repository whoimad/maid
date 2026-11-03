# Plan 014: Validate pipeline settings at ingest and make the evidence check a real error

> **Executor instructions**: Follow this plan step by step. Run every verification command and confirm the expected
> result before moving to the next step. If anything in the "STOP conditions" section occurs, stop and report — do
> not improvise. When done, update the status row for this plan in `plans/README.md` — unless a reviewer dispatched
> you and told you they maintain the index.
>
> **Drift check (run first)**: `git diff --stat 73d9bb1 -- src/maid/graph.py tests/test_demo.py` must print nothing.
> If it prints changes, compare against the excerpts below; if they no longer match, STOP.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW (validation added at the start of the graph; the happy path is unchanged)
- **Depends on**: plans/011-demo-pipeline-end-to-end.md (DONE)
- **Category**: correctness
- **Planned at**: commit `73d9bb1` (branch `integration/prototype`), 2026-11-02

## Why this matters

MAID is a LangGraph pipeline: `ingest -> score_qualitative -> human_review (interrupt) -> mcdm -> robustness -> report`.
`src/maid/demo.py` `run_demo(settings, overrides)` runs it and auto-resumes the human review. A Streamlit GUI
(plan 012) and a CLI pass user `settings` into it. Today:

1. An unknown `weighting` is only rejected in `mcdm`, **after** scoring and the human review. In the GUI the user
   reviews scores and only then gets an error.
2. Unknown keys are silently ignored: `{"weigthing": "equal"}` runs with CRITIC and nobody notices.
3. `k=0` crashes with `IndexError` inside `aggregate` (`samples[0]`); negative `n_draws` or `concentration <= 0`
   fail deep inside numpy with confusing messages.
4. Duplicate company labels (`companies=["Company A", "Company A"]`) give a matrix with duplicate rows, and
   `report()` uses `cs.index(c)`, so its table is wrong.
5. The evidence check (a project rule: every LLM score must quote the filing verbatim) is a bare `assert`, which
   Python removes under `python -O`. A project rule must not depend on interpreter flags.

## Current state (verbatim excerpts, `src/maid/graph.py` at `73d9bb1`)

```python
DEFAULT_SETTINGS = {"k": 5, "weighting": "critic", "seed": 0, "n_draws": 500, "concentration": 100.0}
WEIGHT_FNS = {"entropy": entropy_weights, "critic": critic_weights, "equal": equal_weights}


def _settings(state: PipelineState) -> dict:
    return {**DEFAULT_SETTINGS, **state.get("settings", {})}


def ingest(state: PipelineState) -> dict:
    """Load the synthetic demo dataset (real SEC/yfinance ingest is planned)."""
    settings = _settings(state)
    ds = demo_dataset(seed=settings["seed"])
    companies = state.get("companies") or ds.companies
    unknown = [c for c in companies if c not in ds.companies]
    if unknown:
        raise ValueError(f"unknown companies: {unknown}")
    return {
```

In `score_qualitative`:

```python
            score, std = aggregate(drawn)
            assert evidence_is_quoted(score, state["filings"][c]), f"evidence not in filing: {c}, {crit}"
```

In `mcdm`:

```python
    settings = _settings(state)
    if settings["weighting"] not in WEIGHT_FNS:
        raise ValueError(f"unknown weighting: {settings['weighting']!r}")
```

The existing test `tests/test_demo.py::test_weighting_choice_is_respected` does
`with pytest.raises(ValueError): run_demo({"weighting": "nope"})`. It must still pass (now the error is raised earlier).

## Conventions to match

- Short module docstrings, one-line function docstrings, compact code. Do not reformat existing code.
- Errors are `ValueError` with a message naming the bad value, e.g. `raise ValueError(f"unknown companies: {unknown}")`.
- Tests: plain `assert`, `pytest.raises`, no network. Exemplar from `tests/test_demo.py`:

```python
def test_weighting_choice_is_respected():
    w = run_demo({"weighting": "equal"})["weights"]
    assert np.allclose(list(w.values()), 1 / 6)
    with pytest.raises(ValueError):
        run_demo({"weighting": "nope"})
```

## Design (decided)

Add to `src/maid/graph.py`, directly below `_settings`:

```python
def validate_settings(settings: dict) -> dict:
    """Merge with defaults and reject unknown keys or out-of-range values (ValueError)."""
```

Rules (merged = `{**DEFAULT_SETTINGS, **settings}`):
- keys not in `DEFAULT_SETTINGS` → `ValueError(f"unknown settings: {sorted(extra)}")`
- `weighting` not in `WEIGHT_FNS` → `ValueError(f"unknown weighting: {w!r}")`
- `k`, `seed`, `n_draws` must be `int` (and not `bool`); `k >= 1`, `n_draws >= 1`, `seed >= 0`
- `concentration` must be an `int` or `float` (not `bool`), finite and `> 0`
- Returns the merged dict.

Then:
- `_settings(state)` returns `validate_settings(state.get("settings", {}))`. Every node already calls `_settings`, so
  `ingest` (the first node) now fails fast.
- In `ingest`, after the unknown-companies check, reject duplicates:
  `if len(set(companies)) != len(companies): raise ValueError(f"duplicate companies: {companies}")`.
- In `score_qualitative`, replace the `assert` with
  `if not evidence_is_quoted(...): raise ValueError(f"evidence not in filing: {c}, {crit}")`.
- Leave the check in `mcdm` as is (harmless; it now never fires). Do not remove it.

## Scope

**In scope**: `src/maid/graph.py`, `tests/test_demo.py` (add tests only).

**Out of scope**: `src/maid/demo.py`, `state.py`, `scoring.py`, `matrix.py`, `demo_data.py`, `src/maid/mcdm/*`,
all docs. `DEFAULT_SETTINGS` keys and values must not change.

## Commands

| Purpose | Command | Expected |
|---|---|---|
| Setup (fresh worktree) | `python3 -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"` | exit 0 |
| Tests | `pytest -q` | all pass (48 before this plan) |
| Lint | `ruff check .` | `All checks passed!` |

## Steps

### Step 1: Tests first
Append to `tests/test_demo.py`:
- `test_validate_settings_rejects_bad_values`: for each of `{"weigthing": "equal"}`, `{"k": 0}`, `{"k": 2.5}`,
  `{"k": True}`, `{"n_draws": 0}`, `{"seed": -1}`, `{"concentration": 0}`, `{"concentration": float("inf")}`,
  `{"weighting": "nope"}`: `with pytest.raises(ValueError): validate_settings(bad)`. Also
  `assert validate_settings({}) == DEFAULT_SETTINGS` and `validate_settings({"k": 3})["k"] == 3`.
- `test_bad_settings_fail_before_human_review`: build the graph with `build_graph()`, invoke
  `graph.invoke({"settings": {"k": 0}}, {"configurable": {"thread_id": "t"}})` inside `pytest.raises(ValueError)`,
  then `assert graph.get_state({"configurable": {"thread_id": "t"}}).values.get("qualitative") is None`
  (nothing was scored).
- `test_duplicate_companies_rejected`: `pytest.raises(ValueError)` on
  `build_graph().invoke({"companies": ["Company A", "Company A"]}, {"configurable": {"thread_id": "d"}})`.
- `test_evidence_check_raises_not_asserts`: monkeypatch `maid.graph.evidence_is_quoted` to `lambda s, f: False`,
  then `pytest.raises(ValueError)` on `run_demo()`. (Use `monkeypatch.setattr("maid.graph.evidence_is_quoted", ...)`.
  An `AssertionError` would not satisfy `pytest.raises(ValueError)`, so this test fails before step 2.)

Imports to add: `from maid.graph import DEFAULT_SETTINGS, build_graph, validate_settings`.

**Verify**: `pytest -q tests/test_demo.py` → fails (ImportError on `validate_settings`).

### Step 2: Implement
Edit `src/maid/graph.py` per the Design section.
**Verify**: `pytest -q` → all pass; `ruff check .` → `All checks passed!`;
`grep -n "assert " src/maid/graph.py` → no match.

### Step 3: Commit
Branch `fix/settings-validation`. Commit `fix(graph): validate settings at ingest and raise on uncited evidence`,
body `Refs plan 014`, ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. No push.

## Done criteria

- [ ] `pytest -q` → all pass, at least 52 tests
- [ ] `ruff check .` → `All checks passed!`
- [ ] `grep -n "assert " src/maid/graph.py` → no match
- [ ] `python -c "from maid.demo import run_demo; print(run_demo()['ranking'][:3])"` prints the same list before and after
- [ ] `git diff --stat 73d9bb1..HEAD` lists only `src/maid/graph.py` and `tests/test_demo.py`

## STOP conditions

- The ranking from `run_demo()` changes after the edit (the happy path must be unchanged).
- Making a test pass seems to require editing an out-of-scope file.
- LangGraph wraps exceptions from nodes so that `pytest.raises(ValueError)` does not catch them → STOP and report the
  actual exception type.

## Maintenance notes

- New settings keys must be added to `DEFAULT_SETTINGS` and given a rule in `validate_settings`, or they will be
  rejected as unknown. This is intended.
- The GUI (plan 012) can call `validate_settings` to show errors before running.
