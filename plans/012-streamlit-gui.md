# Plan 012: A Streamlit GUI runs the demo pipeline and visualizes data, scores, human overrides, weights, rankings and rank intervals

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `python -c "from maid.demo import run_demo; s = run_demo(); print(sorted(s))"` must
> list at least: companies, criteria, filings, matrix, method_agreement, overrides, qualitative, quantitative, ranking,
> report, robustness, score_noise, score_samples, scores, settings, weights. If `maid.demo` is missing or keys differ,
> STOP (plan 011 not merged or changed).

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: LOW (new optional extra + new files; pipeline untouched)
- **Depends on**: plans/011-demo-pipeline-end-to-end.md
- **Category**: direction (GUI)
- **Planned at**: commit `6750b35` (integration/prototype), 2026-11-02; designed against plan 011's API

## Why this matters

The project is for learning and explaining. Numbers in a terminal report hide the story; a small GUI makes it visible:
what goes in (decision matrix, LLM-style scores with evidence and sampling noise), the human checkpoint (edit a score
with a reason and see the ranking change), how weighting methods disagree, and why the project reports rank
intervals instead of a single rank. The GUI must stay thin: all data shaping lives in a pure, tested module; the GUI
only calls `run_demo` and plots.

## Current state (from plan 011; verify with the drift check)

- `maid.demo.run_demo(settings: dict | None = None, overrides: list[dict] | None = None, thread_id: str = "demo") -> dict`
  runs the LangGraph pipeline on synthetic data and auto-resumes the human review with `overrides`
  (`[{"company", "criterion", "score", "reason"}]`).
- `maid.graph.DEFAULT_SETTINGS = {"k": 5, "weighting": "critic", "seed": 0, "n_draws": 500, "concentration": 100.0}`.
- Final state keys (all JSON-friendly): `companies` (list[str], row order), `criteria` (list[str], column order),
  `quantitative`, `filings` (company → text), `qualitative` (list of `CriterionScore` Pydantic objects: company,
  criterion, score, evidence), `score_samples` / `score_noise` (keyed `"company|criterion"`), `overrides`
  (list of `ScoreOverride`), `matrix` (list of rows), `weights` (criterion → float), `scores`
  (`{"topsis": [...], "saw": [...]}` in company order), `ranking` (company labels best first),
  `method_agreement` (`{"kendall_tau_topsis_saw": float}`), `robustness` (`{"bootstrap": {...}, "dirichlet": {...}}`,
  each with lists `point, median, lo, hi` (per company) and `acceptability` (n × n; `[i][r-1]` = share of draws where
  company i got rank r)), `report` (Markdown).
- `maid.mcdm`: `equal_weights(X)`, `entropy_weights(X)`, `critic_weights(X)` (numpy arrays).
- `maid.graph.build_graph().get_graph().edges` → objects with `.source` / `.target`.
- `maid.demo_data.QUANT_CRITERIA`, `QUAL_CRITERIA`.
- `pyproject.toml` optional deps: `dev = ["pytest>=8", "ruff>=0.6"]`. CI (`.github/workflows/ci.yml`) runs
  `pip install -e ".[dev]"`, `ruff check .`, `pytest -q` on Python 3.11 and 3.13.
- Conventions: short module docstrings, one-line function docstrings, compact code; tests plain `assert`, no network.

## Design (decided)

1. `pyproject.toml`: add optional extra `gui = ["streamlit>=1.39"]` (Streamlit brings pandas and Altair).
2. `src/maid/gui_data.py` — pure functions, **no streamlit import**, return plain lists of dicts (rows) or strings:
   - `pipeline_dot(statuses: dict[str, str]) -> str` — Graphviz DOT of `build_graph()` edges, left to right; node
     fill by status (`"real"` green-ish, `"demo"` amber, `"stub"` grey). Default statuses: ingest demo,
     score_qualitative demo, human_review real, mcdm real, robustness real, report real.
   - `matrix_rows(state) -> list[dict]` — one row per company: `{"company": ..., <criterion>: value, ...}`.
   - `score_rows(state) -> list[dict]` — per company × qual criterion: score, samples (as "3, 5, 4, 5, 5"), noise (std),
     evidence, overridden (bool).
   - `weight_rows(state) -> list[dict]` — long form `{"method", "criterion", "weight"}` for entropy, critic and equal,
     each computed from `np.array(state["matrix"])`, plus `"used"` marking the method in `settings["weighting"]`.
   - `ranking_rows(state) -> list[dict]` — per company: rank (TOPSIS), company, topsis, saw, saw_rank.
   - `interval_rows(state, source) -> list[dict]` — per company: company, point, median, lo, hi; sorted by point.
   - `acceptability_rows(state, source) -> list[dict]` — long form company, rank, share (skip zeros).
3. `app/streamlit_app.py` — thin UI:
   - Sidebar: weighting (entropy/critic/equal), K samples (1–15), seed, n_draws (100–2000), concentration (10–1000, log
     slider is fine as a select_slider of [10, 30, 100, 300, 1000]). A short "Synthetic demo data — not real companies"
     warning.
   - Cache: `@st.cache_data` on a wrapper `run(settings_json: str, overrides_json: str) -> dict` that calls `run_demo`
     and converts Pydantic objects with `model_dump()`. Overrides live in `st.session_state["overrides"]`.
   - Tabs, in order:
     1. **Pipeline**: `st.graphviz_chart(pipeline_dot(...))` + 4 bullet lines on what each stage does + legend
        (real / demo / stub) + "LLMs never rank" sentence.
     2. **Inputs**: decision matrix table (`matrix_rows`), the filing text of a company chosen in a selectbox.
     3. **Scores & review**: `score_rows` table (score, K samples, noise, evidence); a form to add an override
        (company, criterion, score 1–9, reason required) that appends to session state and reruns; list of active
        overrides with a "clear overrides" button. Show validation errors from the pipeline with `st.error`.
     4. **Weights**: grouped bar chart (Altair) of `weight_rows` — entropy vs CRITIC vs equal per criterion; note
        that the methods disagree and why that matters (link `docs/architecture/uncertainty.md` by path text).
     5. **Ranking**: `ranking_rows` table; Kendall tau TOPSIS vs SAW as `st.metric`; scatter TOPSIS rank vs SAW rank.
     6. **Robustness**: radio bootstrap / dirichlet; Altair rank-interval chart (rule from lo to hi, point at
        `point`, y = company sorted by point, x = rank with 1 on the left); heatmap of `acceptability_rows`;
        one sentence on how to read a 90% interval.
     7. **Report**: `st.markdown(state["report"])`.
4. `tests/test_gui_data.py` (runs in CI without streamlit): one test per helper (shapes, sorting, weights sum to 1
   per method, `pipeline_dot` contains every graph node name and `rankdir=LR`, override marks `overridden=True`).
5. `tests/test_gui_app.py`: `pytest.importorskip("streamlit")`; `AppTest.from_file("app/streamlit_app.py", default_timeout=60).run()`;
   assert `not at.exception`. Model on the import-skip pattern; no network.
6. CI: change install line to `pip install -e ".[dev,gui]"` so the app smoke test runs in CI.
7. README: "Run the GUI" section: `pip install -e ".[gui]"` then `streamlit run app/streamlit_app.py`.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Install GUI extra | `pip install -e ".[dev,gui]"` | exit 0 (network needed once) |
| Tests | `pytest -q` | all pass |
| Lint | `ruff check .` | `All checks passed!` |
| GUI smoke (headless) | `timeout 25 streamlit run app/streamlit_app.py --server.headless true --server.port 8599` then `curl -s localhost:8599/_stcore/health` from another shell | `ok` |

## Scope

**In scope**: `pyproject.toml` (gui extra only), `src/maid/gui_data.py`, `app/streamlit_app.py`,
`tests/test_gui_data.py`, `tests/test_gui_app.py`, `.github/workflows/ci.yml` (install line only), `README.md`
("Run the GUI" section only).

**Out of scope**: `src/maid/graph.py`, `state.py`, `demo.py`, `scoring.py`, `matrix.py`, `demo_data.py`,
`src/maid/mcdm/*` — if the GUI needs data the state does not have, compute it in `gui_data.py` from state; if that is
impossible, STOP.

## Git workflow

Branch `feat/gui`. Commits e.g. `feat(gui): pure data helpers for the demo GUI`, `feat(gui): streamlit app`,
`ci: install gui extra`, each ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. No push/PR
unless instructed.

## Steps

### Step 1: Extra + helper tests first
Add the `gui` extra; write `tests/test_gui_data.py`.
**Verify**: `pytest -q tests/test_gui_data.py` → import error (module missing).

### Step 2: `gui_data.py`
**Verify**: `pytest -q tests/test_gui_data.py` → all pass; `ruff check .` passes.

### Step 3: `app/streamlit_app.py` + app smoke test
**Verify**: `pytest -q tests/test_gui_app.py` → 1 passed (not skipped, since the gui extra is installed);
headless run + health check → `ok`.

### Step 4: CI + README
**Verify**: `pytest -q && ruff check .` → pass.

## Done criteria

- [ ] `pytest -q` → all pass; `tests/test_gui_app.py` passed (not skipped) locally with the gui extra
- [ ] `ruff check .` → `All checks passed!`
- [ ] `grep -n "import streamlit" src/maid/gui_data.py` → no match
- [ ] Headless health check prints `ok`
- [ ] Only in-scope files changed (`git diff --stat <base>..HEAD`)

## STOP conditions

- Drift check fails (plan 011 API differs).
- `pip install` of streamlit fails (no network) → STOP and report; do not vendor anything.
- `AppTest` reports an exception you cannot fix within in-scope files.
- The GUI would need to call an LLM or network → STOP.

## Maintenance notes

- When the real scorer/ingest exist, add a data-source switch in the sidebar; keep `gui_data.py` pure.
- Reviewers: the GUI must not compute rankings itself except via `maid.mcdm` (weights comparison) or state values.
