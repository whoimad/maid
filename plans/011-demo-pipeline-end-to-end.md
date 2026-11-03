# Plan 011: `python -m maid.demo` runs the whole LangGraph pipeline end to end on a synthetic dataset, with a stub scorer, real MCDM, robustness and a report

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git log --oneline -1` and `git diff --stat faa325b..HEAD -- src/maid tests`.
> Expected drift: `tests/test_docs.py` (plans 006/007). If `src/maid/graph.py` or `src/maid/state.py` differ from
> "Current state" below, STOP.

## Status

- **Priority**: P1
- **Effort**: L
- **Risk**: MED (changes graph node bodies and state; human-review behaviour must not change)
- **Depends on**: plans 006 and 007 merged (docs this plan updates must exist: `docs/architecture/overview.md` status table, `docs/architecture/graph.md`)
- **Category**: direction (working prototype)
- **Planned at**: commit `faa325b`, 2026-11-02

## Why this matters

Every graph node except `human_review` is a stub, so the project cannot be run or shown. The owner needs a working
prototype to learn from, demo in interviews and visualize in a GUI (plan 012). Real ingest (SEC EDGAR) and the real
LLM scorer (DeepSeek) need criteria definitions, API keys and money, so this plan builds the **same pipeline on a
synthetic demo dataset** with a **deterministic stub scorer** that behaves like a noisy LLM (K samples, evidence
quotes). The MCDM, robustness and human-review parts are the real code. The project rule "LLMs never rank" holds:
the scorer only produces 1–9 scores with evidence; weights and ranks come from `maid.mcdm`.

## Current state

- `src/maid/graph.py`: nodes `ingest`, `score_qualitative`, `human_review`, `mcdm`, `robustness`, `report`, linear
  edges START→ingest→score_qualitative→human_review→mcdm→robustness→report→END, compiled with
  `MemorySaver(serde=JsonPlusSerializer(allowed_msgpack_modules=CHECKPOINT_TYPES))`. Stubs return
  `{"quantitative": {}}`, `{"qualitative": []}`, `{"weights": {}, "ranking": []}`, `{}`, `{"report": ""}`.
  `human_review` (keep unchanged):
  ```python
  def human_review(state: PipelineState) -> dict:
      # Pauses the graph; resume with Command(resume={"overrides": [...]}).
      decision = interrupt({"qualitative": state.get("qualitative", [])})
      return {"overrides": parse_overrides(decision, state.get("qualitative", []))}
  ```
- `src/maid/state.py`: `CriterionScore(company, criterion, score: int 1..9, evidence)`,
  `ScoreOverride(company, criterion, score, reason min_length=1)`, `PipelineState(TypedDict, total=False)` with keys
  companies, quantitative (company→criterion→float), qualitative (list[CriterionScore]), overrides, weights
  (dict[str, float]), ranking (list[str]), report (str); `CHECKPOINT_TYPES` lists the two Pydantic models.
- `src/maid/mcdm/`: `equal_weights(X)`, `entropy_weights(X, normalization="minmax")`, `critic_weights(X)` → 1-D weights
  summing to 1; `saw(X, w)`, `topsis(X, w)` → score per row, higher = better; `robust_ranking(X, weight_fn, rank_fn,
  n_draws=1000, concentration=100.0, seed=0)` → `{"bootstrap": RankIntervals, "dirichlet": RankIntervals}` with numpy
  fields `point, median, lo, hi` (n,), `acceptability` (n, n), `n_draws`; `ranks(scores)` in `maid.mcdm.robustness`
  (1 = best). All inputs `X` shape (n_alternatives, m_criteria), all benefit-type.
- `src/maid/cache.py` `DiskCache` exists; not needed here (no API calls).
- Tests: `tests/test_scaffold.py::test_graph_pauses_at_human_review_then_finishes` invokes the graph with
  `{"companies": ["Company A"]}` and expects `__interrupt__`, then resumes with `Command(resume={"overrides": []})` and
  expects `"report" in final`. `tests/test_review.py` tests `parse_overrides` and a checkpoint round trip.
  Style: plain functions, plain `assert`, seeded `np.random.default_rng(<int>)`, no network.
- Conventions (CLAUDE.md): short module docstrings, one-line function docstrings, compact code, do not reformat
  existing code; matrix named `X`; company names anonymized "Company A", ...; decision date 2024-12-31.

## Design (decided; implement this)

### New module `src/maid/demo_data.py` (pure, no I/O)

```python
QUANT_CRITERIA = ["revenue_growth", "operating_margin", "fcf_margin", "rd_intensity"]   # all benefit-type
QUAL_CRITERIA = ["strategy_clarity", "risk_disclosure"]                               # LLM-scored, 1-9

@dataclass(frozen=True)
class DemoDataset:
    companies: list[str]                       # "Company A".."Company J"
    quantitative: dict[str, dict[str, float]]  # company -> criterion -> value
    filings: dict[str, str]                    # company -> synthetic 10-K excerpt (one sentence per QUAL criterion + filler)
    latent: dict[str, dict[str, int]]          # company -> qual criterion -> hidden "true" score 1-9 (for the stub scorer only)

def demo_dataset(n: int = 10, seed: int = 0) -> DemoDataset: ...
```
- `rng = np.random.default_rng(seed)`. Quantitative values: revenue_growth ~ N(0.10, 0.08), operating_margin ~
  N(0.18, 0.08), fcf_margin ~ N(0.15, 0.07), rd_intensity ~ U(0.03, 0.25); round to 3 decimals. Latent qual scores:
  integers in 2..8 from rng.
- Filing text per company: built from templates; for each qualitative criterion one sentence chosen by its latent
  score band (low 1–3 / mid 4–6 / high 7–9), e.g. strategy_clarity high: "Management set out three measurable
  priorities for 2025 and reported progress against each one." Write 3 bands × 2 criteria = 6 template sentences
  plus 2 filler sentences. The company label must not appear in the text (anonymization).
- Module docstring must say: synthetic data, not real companies; used for the demo and tests only.

### New module `src/maid/scoring.py`

```python
class StubScorer:
    """Deterministic stand-in for the LLM scorer: latent score + seeded noise, evidence quoted from the filing."""
    def __init__(self, latent: dict[str, dict[str, int]], noise: float = 1.0, seed: int = 0): ...
    def score(self, company: str, criterion: str, filing: str, k: int) -> list[CriterionScore]: ...
```
- For sample i in range(k): `score = clip(round(latent + rng_normal(0, noise)), 1, 9)` where the rng is seeded from
  `(seed, company, criterion, i)` via `np.random.default_rng([seed, i, zlib.crc32(f"{company}|{criterion}".encode())])`
  so results are reproducible and independent of call order.
- Evidence: the sentence in `filing` written for that criterion (find it by the template text; it must be an exact
  substring of `filing`).
- `aggregate(samples: list[CriterionScore]) -> tuple[CriterionScore, float]`: median score (rounded half up to int),
  evidence from the first sample, plus the sample standard deviation (ddof=0) as the noise measure.
- `evidence_is_quoted(score: CriterionScore, filing: str) -> bool`: `score.evidence in filing` (the programmatic
  citation check from the project research).

### New pure module `src/maid/matrix.py`

```python
def apply_overrides(scores: list[CriterionScore], overrides: list[ScoreOverride]) -> list[CriterionScore]: ...
def build_matrix(companies, quantitative, qualitative, criteria) -> np.ndarray: ...   # (n, m), rows follow `companies`
def kendall_tau(a_scores, b_scores) -> float: ...                                       # scipy.stats.kendalltau on scores
```
- `apply_overrides`: returns new list where each (company, criterion) with an override takes the override's score;
  evidence becomes `f"{orig.evidence} [human override: {o.reason}]"`. Does not mutate input.
- `build_matrix`: quantitative values from `quantitative[c][crit]` for quant criteria, `float(score)` from
  `qualitative` for qual criteria; raise `ValueError` naming the missing (company, criterion) if any cell is missing.

### State additions (`src/maid/state.py`), all JSON-friendly (lists/dicts/floats, no numpy)

```python
class PipelineState(TypedDict, total=False):
    # existing keys unchanged, plus:
    criteria: list[str]                         # column order of X
    filings: dict[str, str]
    score_samples: dict[str, list[int]]         # "company|criterion" -> K sampled scores
    score_noise: dict[str, float]               # "company|criterion" -> std of the K samples
    settings: dict                              # {"k": 5, "weighting": "critic", "seed": 0, "n_draws": 500, "concentration": 100.0}
    matrix: list[list[float]]                   # X after overrides
    scores: dict[str, list[float]]              # {"topsis": [...], "saw": [...]} per company, in `companies` order
    method_agreement: dict[str, float]          # {"kendall_tau_topsis_saw": ...}
    robustness: dict                            # {"bootstrap": {...}, "dirichlet": {...}} with lists: point, median, lo, hi, acceptability
```
`ranking` becomes the company labels sorted by TOPSIS score (best first). Keep `weights` as `dict[criterion, float]`.

### Node bodies (`src/maid/graph.py`)

- `ingest`: `ds = demo_dataset(seed=settings.get("seed", 0))` where `settings = {**DEFAULT_SETTINGS, **state.get("settings", {})}`;
  returns companies, quantitative, filings, criteria (`QUANT_CRITERIA + QUAL_CRITERIA`), settings. If
  `state["companies"]` is given, keep only those companies that exist in the dataset (an unknown name → ValueError).
- `score_qualitative`: needs the latent scores; re-create `demo_dataset(seed)` (deterministic) to build a
  `StubScorer`. For each company × qual criterion: `k` samples → `aggregate` → one `CriterionScore` into
  `qualitative`, the samples into `score_samples`, the std into `score_noise`. Assert `evidence_is_quoted` for each.
- `human_review`: unchanged.
- `mcdm`: `apply_overrides` → `build_matrix` → weights by `settings["weighting"]` in {"entropy", "critic", "equal"}
  (unknown → ValueError) → `topsis` and `saw` scores → `ranking` (by TOPSIS) → `method_agreement` Kendall tau
  between the two score vectors. Store `matrix`, `weights` (criterion → float), `scores`, `ranking`, `method_agreement`.
- `robustness`: `robust_ranking(np.array(matrix), weight_fn, topsis, n_draws, concentration, seed)`, converted to
  lists (`.tolist()`), plus `n_draws`.
- `report`: Markdown string: title, "Synthetic demo data" warning, settings line, ranking table (rank, company,
  TOPSIS, SAW, 90% interval bootstrap `lo–hi`, dirichlet `lo–hi`, P(rank 1) dirichlet), weights table, method
  agreement line, a list of overrides with reasons (or "none"), and the caveat "LLMs never rank: scores come from the
  (stub) scorer, ranks from the MCDM engine."
- `DEFAULT_SETTINGS = {"k": 5, "weighting": "critic", "seed": 0, "n_draws": 500, "concentration": 100.0}` in `graph.py`.
- Graph edges and compile call: unchanged (the 7-edge linear chain must stay; plan 007's doc test checks it).

### New entry point `src/maid/demo.py`

```python
def run_demo(settings: dict | None = None, overrides: list[dict] | None = None, thread_id: str = "demo") -> dict:
    """Run the graph, auto-resume the human review with `overrides`, return the final state."""
def main() -> None:  # argparse: --weighting, --k, --seed, --n-draws, --concentration, --overrides PATH (JSON list), --json PATH
```
`main` prints the report; `--json PATH` writes the final state as JSON (convert Pydantic models with
`model_dump()`). Runs with `python -m maid.demo`. No network, no API key.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Setup | `python3 -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"` (or use an existing venv) | exit 0 |
| Tests | `pytest -q` | all pass |
| Lint | `ruff check .` | `All checks passed!` |
| Demo | `python -m maid.demo` | prints a Markdown report with 10 ranked companies |

## Scope

**In scope**: create `src/maid/demo_data.py`, `src/maid/scoring.py`, `src/maid/matrix.py`, `src/maid/demo.py`,
`tests/test_demo.py`; modify `src/maid/graph.py` (node bodies + `DEFAULT_SETTINGS` + imports only),
`src/maid/state.py` (add keys only), `tests/test_scaffold.py` (only if the existing graph test must pass
`"settings"`; prefer leaving it unchanged), `docs/architecture/overview.md` (status table rows only),
`docs/architecture/graph.md` (node table + "Known limitations" only), `README.md` (add a "Run the demo" block).

**Out of scope**: `src/maid/mcdm/*` (use, do not change), `src/maid/cache.py`, `src/maid/config.py`, edges of
the graph, any real network/API code, GUI (plan 012).

## Git workflow

Branch `feat/demo-pipeline`. Conventional commits (e.g. `feat: demo dataset and stub scorer`,
`feat(graph): wire demo pipeline end to end`, `docs: mark demo nodes implemented`), each ending with
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Do NOT push or open a PR unless instructed.

## Steps

### Step 1: Tests first (`tests/test_demo.py`)

1. `test_demo_dataset_is_deterministic_and_anonymized`: two calls with seed 0 are equal; 10 companies "Company A".."Company J"; no company label appears in any filing.
2. `test_stub_scorer_is_reproducible_and_quotes_evidence`: same args → same scores; every sample in 1..9; `evidence_is_quoted` true; with `noise=0` every sample equals the latent score.
3. `test_aggregate_takes_median`: samples [3, 5, 9] → 5; std > 0.
4. `test_apply_overrides_replaces_score_and_keeps_reason`: score replaced, reason appears in evidence, input list unchanged.
5. `test_build_matrix_shape_and_missing_cell`: shape (n, 6); deleting one quantitative value → `ValueError`.
6. `test_run_demo_end_to_end`: `run_demo()` → `ranking` has 10 unique companies; `weights` sum to 1 (abs 1e-9); every `robustness[src]["lo"][i] <= robustness[src]["hi"][i]`; `"Synthetic demo data"` in `report`.
7. `test_override_changes_matrix`: `run_demo(overrides=[{"company": "Company A", "criterion": "strategy_clarity", "score": 9, "reason": "test"}])` → the matrix cell for Company A / strategy_clarity is 9.0 and the report lists the reason.
8. `test_weighting_choice_is_respected`: `run_demo({"weighting": "equal"})["weights"]` all equal 1/6; unknown weighting → `ValueError`.
9. `test_llm_never_ranks`: `StubScorer` and `scoring` module expose no function whose name contains "rank" (`[n for n in dir(scoring) if "rank" in n.lower()] == []`).

**Verify**: `pytest -q tests/test_demo.py` → fails at import (modules missing).

### Step 2: `demo_data.py`, `scoring.py`, `matrix.py`

**Verify**: `pytest -q tests/test_demo.py -k "dataset or scorer or aggregate or overrides or matrix or never"` → those pass.

### Step 3: State keys and node bodies; `demo.py`

**Verify**: `pytest -q` → all pass (including the unchanged `test_scaffold.py` and `test_review.py`, and plan 007's
`test_graph_doc_diagram_matches_code`); `python -m maid.demo | head -30` → report with a 10-row ranking table;
`time python -m maid.demo > /dev/null` → under 20 s.

### Step 4: Docs

- `docs/architecture/overview.md` status table: Ingest → "demo implemented (synthetic dataset); real SEC/yfinance ingest planned"; Qualitative scorer agents → "stub scorer implemented (deterministic, K samples, evidence check); DeepSeek scorer planned"; Human checkpoint → "implemented; overrides applied in `mcdm`"; MCDM engine → "implemented and wired (node `mcdm`)"; Robustness → "implemented and wired"; Report → "implemented (Markdown)". Leave Backtest and Checkpointer rows unchanged.
- `docs/architecture/graph.md`: update the node table Status column the same way and the Known limitations list (remove "overrides validated but not applied" and "nodes are stubs"; add "ingest and scorer run on synthetic data").
- `README.md`: add a "Run the demo" section with `python -m maid.demo` and `python -m maid.demo --weighting entropy --json out.json`.

**Verify**: `pytest -q && ruff check .` → pass.

## Done criteria

- [ ] `pytest -q` → all pass, 9 new tests in `tests/test_demo.py`
- [ ] `ruff check .` → `All checks passed!`
- [ ] `python -m maid.demo` exits 0 and prints a ranking of 10 companies; runs < 20 s
- [ ] `git diff --stat main -- src/maid/mcdm src/maid/cache.py src/maid/config.py` → empty
- [ ] Graph edges unchanged: `python -c "from maid.graph import build_graph; print(len(build_graph().get_graph().edges))"` → `7`
- [ ] `grep -rn "api_key\|DEEPSEEK_API_KEY" src/maid/demo*.py src/maid/scoring.py` → no matches

## STOP conditions

- The checkpointer refuses to restore a new state value (msgpack allowlist error) → do NOT add numpy types to state; convert to lists. If it still fails with only lists/dicts/Pydantic models, STOP and report the error.
- `test_review.py` or `test_scaffold.py` fails after your change and the fix would change `human_review` or `parse_overrides` → STOP.
- You need to change anything in `src/maid/mcdm/` → STOP.
- A demo run takes > 60 s → STOP; do not vectorize speculatively (report timings per node).

## Maintenance notes

- The real DeepSeek scorer must implement the same `score(company, criterion, filing, k) -> list[CriterionScore]` interface; then `score_qualitative` picks scorer by settings. Real ingest replaces `demo_dataset` behind `ingest`.
- Reviewers: check the scorer cannot see other companies' data or any ranking; check report numbers come from state, not recomputation.
