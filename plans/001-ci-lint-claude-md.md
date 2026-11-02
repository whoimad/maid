# Plan 001: Every PR is gated by CI (pytest + ruff), and agents have a CLAUDE.md

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat c094993..HEAD -- pyproject.toml README.md .github CLAUDE.md src tests scripts`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: dx
- **Planned at**: commit `c094993`, 2026-11-02

## Why this matters

MAID is built issue-by-issue, mostly by AI agents, via small PRs into `main`. Today nothing checks a PR:
there is no CI and no linter, so a PR that breaks the test suite can be merged without anyone noticing. There
is also no `CLAUDE.md`, so every agent session re-discovers the commands, layout and project rules
(e.g. "LLMs never rank"). This plan adds a one-command verification baseline that every later plan relies on.

## Current state

- Repo: Python package `maid` in `src/maid/`, tests in `tests/`, one research script in `scripts/`.
- `pyproject.toml` (full dev section today):
  ```toml
  [project.optional-dependencies]
  dev = ["pytest>=8"]

  [tool.pytest.ini_options]
  testpaths = ["tests"]
  ```
  `requires-python = ">=3.11"`. Local venv runs Python 3.13.
- No `.github/` directory exists. No `CLAUDE.md` / `AGENTS.md` exists. Ruff is not installed.
- Test suite today: `pytest -q` → `7 passed`.
- `README.md` "Layout" section is stale — it lists only graph/state/cache/config:
  ```markdown
  ## Layout
  - `src/maid/graph.py`: LangGraph pipeline skeleton (stub nodes, human-review interrupt)
  - `src/maid/state.py`: shared state and score schema
  - `src/maid/cache.py`: on-disk cache for API/data calls
  - `src/maid/config.py`: settings from environment
  ```
  Missing: `src/maid/mcdm/` (weights.py, ranking.py), `scripts/weight_stability.py`, `docs/architecture/`.
- Code style conventions (match them; do not reformat): short module docstrings, one-line function
  docstrings, numpy matrices named `X` with shape `(n_alternatives, m_criteria)` (uppercase single-letter
  matrix names are intentional — do NOT enable pep8-naming `N` rules), compact code, no type-checker yet.
- Project rules that belong in CLAUDE.md (quote them; they come from `docs/SCOPE.md` and `docs/architecture/decisions.md`):
  - "**LLMs never rank.** Agents extract and score; a deterministic MCDM engine computes weights and ranks.
    Every LLM score carries cited evidence and is reviewable by the human." (SCOPE §2)
  - Decision date 2024-12-31; agents see only information available on or before it; company names
    anonymized ("Company A", …) in scoring prompts. (SCOPE §3)
  - "Workflow: issue per component, branch per issue, small PRs into `main`, conventional commits." (SCOPE §8)
  - D7: "Cache everything on disk … cache keys must include model and prompt version."
  - MCDM engine (`src/maid/mcdm/`): "Pure functions, no LLM, no I/O. Everything is unit tested." All criteria
    must be benefit-type (higher is better). (docs/architecture/mcdm.md)
  - Research notes in `docs/research/` were made from abstracts only; claims marked UNVERIFIED must be checked
    before relying on them.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Activate venv | `source .venv/bin/activate` (create with `python3 -m venv .venv` if absent) | prompt shows venv |
| Install | `pip install -e ".[dev]"` | exit 0 |
| Tests | `pytest -q` | `7 passed` (before this plan) |
| Lint | `ruff check .` | `All checks passed!` |

## Scope

**In scope** (the only files you should modify/create):
- `pyproject.toml` (dev deps + `[tool.ruff]` section only)
- `.github/workflows/ci.yml` (create)
- `CLAUDE.md` (create)
- `README.md` (Layout section only)
- Files under `src/`, `tests/`, `scripts/` **only** for changes produced by `ruff check --fix` (import sorting / trivial autofixes)

**Out of scope**:
- Any manual logic change in `src/`, `tests/`, `scripts/`. Lint findings that need a manual fix → see STOP conditions.
- Adding a formatter (`ruff format`), mypy, or pre-commit — deliberately deferred; reformatting the whole repo
  would create a noisy diff.
- `docs/` content.

## Git workflow

- Base: `feat/weight-stability-spike` if it is not yet merged into `main` (check: `git branch --merged main | grep weight-stability`); otherwise `main`.
- Branch: `chore/ci-lint` (repo uses `feat/…`, `docs/…` prefixes).
- Conventional commits, e.g. `chore: add CI workflow and ruff lint`. Repo style example from `git log`:
  `feat: MCDM engine, weight-stability spike, architecture docs`.
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Add ruff to dev deps and configure it

In `pyproject.toml`, change the dev extra to `dev = ["pytest>=8", "ruff>=0.6"]` and append:

```toml
[tool.ruff]
line-length = 110
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]
ignore = ["E501", "E741"]  # long table/f-string lines in scripts; single-letter math names are intentional
```

**Verify**: `pip install -e ".[dev]" && ruff --version` → prints a version, exit 0.

### Step 2: Make the repo lint-clean using autofix only

Run `ruff check .` and read the output. Then `ruff check . --fix`. Then `ruff check .` again.

**Verify**: `ruff check .` → `All checks passed!` and `pytest -q` → `7 passed`.
Review `git diff -- src tests scripts`: every hunk must be an import reorder or equally trivial autofix.

### Step 3: Add the CI workflow

Create `.github/workflows/ci.yml`:

```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: pip
      - run: pip install -e ".[dev]"
      - run: ruff check .
      - run: pytest -q
```

No secrets are needed: no test calls the network or the DeepSeek API. Do not add `DEEPSEEK_API_KEY` to the workflow.

**Verify**: `python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ci.yml'))" 2>/dev/null || python -c "print(open('.github/workflows/ci.yml').read()[:20])"` → no exception (PyYAML may be absent; the fallback just confirms the file exists). Visually confirm 2-space indentation.

### Step 4: Write CLAUDE.md

Create `CLAUDE.md` (aim for 40–70 lines) with these sections, filled from "Current state" above:
1. **What this is** — 2 lines: MAID, LLM agents score qualitative info, deterministic MCDM ranks; exploratory prototype; see `docs/SCOPE.md`.
2. **Commands** — setup, `pytest -q`, `ruff check .`, `python scripts/weight_stability.py`.
3. **Layout** — one line per module/dir (same list as the README update in Step 5).
4. **Rules (non-negotiable)** — the quoted project rules: LLMs never rank; decision date & anonymization; MCDM is pure/no I/O/unit-tested, benefit-type criteria only; cache keys include model+prompt version; never commit `.env` or print API keys.
5. **Conventions** — matrix `X` shape `(n, m)`, short docstrings, tests as `tests/test_<area>.py` with plain `assert` and seeded `np.random.default_rng(<int>)`, no network in tests.
6. **Workflow** — issue per component, branch per issue (`feat/`, `fix/`, `chore/`, `docs/`), conventional commits with `Refs #N` / `Closes #N` in the body, small PRs into `main`, CI must be green.
7. **Docs to read before changing X** — `docs/architecture/decisions.md` (D1–D7) before changing design; `docs/architecture/mcdm.md` before touching `src/maid/mcdm/`; `docs/research/README.md` caveat about unverified claims.

**Verify**: `test -f CLAUDE.md && grep -c "LLMs never rank" CLAUDE.md` → `1` (or more).

### Step 5: Fix the README Layout section

Replace the Layout list with:

```markdown
## Layout
- `src/maid/graph.py`: LangGraph pipeline skeleton (stub nodes, human-review interrupt)
- `src/maid/state.py`: shared state and score schema
- `src/maid/cache.py`: on-disk cache for API/data calls
- `src/maid/config.py`: settings from environment
- `src/maid/mcdm/`: MCDM engine: weights (entropy, CRITIC, equal) and ranking (TOPSIS, SAW)
- `scripts/weight_stability.py`: spike #6 simulation (see `docs/research/weight-stability-results.md`)
- `docs/architecture/`: architecture overview, per-block docs, design decisions
```

Also add `ruff check .` after `pytest` in the Setup code block.

**Verify**: `grep -n "mcdm" README.md` → at least one match in the Layout section.

## Test plan

No new tests (this plan adds verification infrastructure, not behavior). The existing 7 tests must still pass,
and must pass under CI on Python 3.11 and 3.13.

## Done criteria

- [ ] `ruff check .` → `All checks passed!`
- [ ] `pytest -q` → `7 passed`
- [ ] `.github/workflows/ci.yml` exists and runs `ruff check .` and `pytest -q` on a 3.11/3.13 matrix
- [ ] `CLAUDE.md` exists and contains "LLMs never rank"
- [ ] `git diff --stat` shows changes only in in-scope files; diffs in `src/ tests/ scripts/` are autofix-only
- [ ] `plans/README.md` status row updated

## STOP conditions

- `ruff check .` after `--fix` still reports **more than 5** findings, or any finding requires a logic change → stop and list them.
- `pytest` fails after the autofix → revert the autofix (`git checkout -- src tests scripts`) and report.
- `pip install` cannot reach PyPI → stop; do not vendor or pin around it.

## Maintenance notes

- If a later plan adds a formatter or type checker, add it as a separate CI step, not merged into the lint step.
- Reviewers: confirm `CLAUDE.md` rules match `docs/SCOPE.md`; if SCOPE changes, CLAUDE.md must follow.
- Deferred: pre-commit hooks, coverage reporting, `ruff format`.
