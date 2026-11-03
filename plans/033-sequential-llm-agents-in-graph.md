# Plan 033: Three LLM criterion agents as sequential, cache-resumable graph nodes on real staples 10-Ks

> **Executor instructions**: Follow this plan step by step. Run every verification command and confirm the expected
> result before moving to the next step. If anything in the "STOP conditions" section occurs, stop and report — do
> not improvise. The reviewer maintains `plans/README.md`; do not edit it.
>
> **Drift check (run first)**: `git diff --stat <BASE>..HEAD -- src/maid/graph.py src/maid/state.py src/maid/demo.py src/maid/gui_data.py src/maid/llm.py src/maid/real_data.py tests/test_real_data.py tests/test_gui_data.py docs/architecture/graph.md`
> where `<BASE>` is the commit the reviewer told you to reset to. Expected: no output.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED (changes the graph shape; demo path must stay identical)
- **Depends on**: plan 031 (LLM scorer), plan 032 (local only, D21; prompt v2)
- **Category**: direction
- **Planned at**: commit `65bd00b` on `integration/prototype` (plan 032 merged), 2026-11-03

## Why this matters

MAID: LLM agents **score** qualitative criteria from 10-K text; a deterministic MCDM engine computes weights and
ranks. **LLMs never rank.** Decision D21 (owner, final): local models only, and one 7B model fills the 8 GB GPU, so
the agents are **conceptually multi-agent but run as sequential jobs**: the pricing-power agent scores every company,
then the strategy-clarity agent, then the capital-allocation agent. This plan makes that visible in the LangGraph
pipeline as three explicit agent nodes chained one after another, on the real consumer-staples universe
(`source="sec"`, `sector="staples"`). Every LLM reply is cached on disk (`LLMScorer`), so a job that is interrupted
(crash, laptop sleep) resumes where it stopped when the run is started again. The human review interrupt then sees
all scores at once, and the MCDM engine ranks.

## Current state

- `src/maid/graph.py` (read it fully first). Relevant parts:
  - `DEFAULT_SETTINGS = {"source": "demo", "sector": "tech", "k": 5, "weighting": "critic", "seed": 0, "n_draws": 500, "concentration": 100.0}`
    and `validate_settings(settings)` (rejects unknown keys, checks values).
  - `ingest(state)`: for `source == "sec"` it calls `load_sec(get_settings().decision_date, settings["sector"])` and
    sets `filings = {c: "" for c in tickers}`, `criteria = list(SECTORS[sector][1])` (4 quantitative criteria).
  - `score_qualitative(state)`: for `source == "sec"` returns empty `qualitative`, `score_samples`, `score_noise`;
    for the demo it runs `StubScorer` over `QUAL_CRITERIA` (`["strategy_clarity", "risk_disclosure"]`).
  - `human_review(state)`: skips the interrupt when `qualitative` is empty.
  - `report(state)`: for `sec` the header says "quantitative only" and the last line says "this run has no LLM
    scores".
  - `build_graph()`: nodes `ingest → score_qualitative → human_review → mcdm → robustness → report`, compiled with
    `MemorySaver`.
- `src/maid/llm.py` (plans 031/032): `LLMScorer(client, model, cache, temperature=0.7, max_attempts=3, seed=0,
  max_tokens=400)`, `.score(company, criterion, filing, k) -> list[CriterionScore]` (raises `ScoringError` when fewer
  than ceil(k/2) valid samples; `ContextTruncated` when the server cut the prompt), `.log` (list of dicts with
  `ok`, `prompt_tokens`, `completion_tokens`, `model`, ...), `quote_in_text(quote, text)`, `make_client(settings)`
  (local servers only).
- `src/maid/real_data.py`: `load_filings(decision_date, sector) -> (label -> ticker, label -> {"1","1a","7"}
  anonymized text, label -> info)`. `src/maid/tenk.py`: `criterion_text(sections, criterion)["text"]`.
- `src/maid/scoring.py`: `aggregate(samples) -> (median CriterionScore, std)`.
- `src/maid/rubrics.py`: `RUBRICS` has keys `pricing_power`, `strategy_clarity`, `capital_allocation`;
  `PROMPT_VERSION`.
- `src/maid/gui_data.py`: `DEFAULT_STATUSES = {"ingest": "demo", "score_qualitative": "demo", "human_review": "real", "mcdm": "real", "robustness": "real", "report": "real"}`;
  `pipeline_dot` draws every node of `build_graph()`.
- `src/maid/demo.py`: `run_demo(settings, overrides)` invokes the graph and auto-resumes the review; `main()` maps
  CLI flags to settings (`--source`, `--sector`, `--weighting`, `--k`, `--seed`, `--n-draws`, `--concentration`,
  `--overrides`, `--json`).
- Tests: `tests/test_real_data.py` has `_patch(monkeypatch)` (fakes `graph.load_sec` with 3 tech companies) and an
  autouse `no_network` fixture; `tests/test_demo.py` covers the demo graph. Exemplar test style: those two files.
- Conventions: compact code, one-line docstrings, line length 110, no network in tests, plain `assert`.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Tests | `env PYTHONPATH=src /home/imad/maid/.venv/bin/python -m pytest -q` | all pass |
| Lint | `/home/imad/maid/.venv/bin/ruff check .` | `All checks passed!` |
| Demo unchanged | `env PYTHONPATH=src /home/imad/maid/.venv/bin/python -m maid.demo > /tmp/claude-1000/demo_after.txt` | same output as before your change (Step 0) |

Run each command on its own.

## Steps

### Step 0: baseline

Run the "Demo unchanged" command once **before** any change, writing to `/tmp/claude-1000/demo_before.txt` instead.

### Step 1: settings

- Add `"scorer": "auto"` and `"limit": 0` to `DEFAULT_SETTINGS`.
- `validate_settings`: `scorer` must be `"auto"` or `"llm"`; `"llm"` requires `source == "sec"` and
  `sector == "staples"` (ValueError naming the rule otherwise). `limit` must be an int ≥ 0 (add it to the existing
  int loop with low 0). `limit = N > 0` means: use only the first N companies in label order; 0 means all.
- Tests (`tests/test_real_data.py`): `scorer="llm"` with `source="demo"` raises; with `source="sec", sector="tech"`
  raises; `scorer="gpt"` raises; `limit=-1` raises.

### Step 2: ingest

In `ingest`, for `source == "sec"`:
- After the existing `load_sec` call, apply `limit`: when `settings["limit"] > 0` and `state.get("companies")` is
  empty, `companies = sorted(available)[:limit]`.
- When `settings["scorer"] == "llm"`: `_, texts, _ = load_filings(get_settings().decision_date, settings["sector"])`
  (import `load_filings` from `maid.real_data` at module top, like `load_sec`, so tests can monkeypatch
  `graph.load_filings`), then build `criterion_texts = {f"{c}|{k}": criterion_text(texts[c], k)["text"] for c in
  companies for k in LLM_CRITERIA}` and append `LLM_CRITERIA` to `criteria`. Return `criterion_texts` (empty dict
  otherwise).
- Define at module level: `LLM_CRITERIA = ["pricing_power", "strategy_clarity", "capital_allocation"]  # agent order (D21: sequential)`.
- `state.py`: add to `PipelineState`:
  `criterion_texts: dict[str, str]  # "company|criterion" -> anonymized 10-K slice the agent reads (source="sec", scorer="llm")`
  and `agent_runs: dict[str, dict]  # criterion -> {"model", "prompt_version", "calls", "failed_attempts", "prompt_tokens", "completion_tokens", "seconds"}`.

### Step 3: the agent nodes

```python
def make_agent(criterion: str):
    """Graph node for one LLM criterion agent: scores every company for its criterion, one call at a time."""
    def agent(state: PipelineState) -> dict:
        settings = _settings(state)
        if settings["scorer"] != "llm":
            return {}
        ...
    agent.__name__ = f"agent_{criterion}"
    return agent
```

Body when `scorer == "llm"`:
1. `cfg = get_settings()`; `scorer = LLMScorer(make_client(cfg), cfg.model, DiskCache(cfg.cache_dir / "llm"),
   seed=settings["seed"])`; `t0 = time.perf_counter()`.
2. `qualitative = list(state.get("qualitative", []))`, `samples = dict(state.get("score_samples", {}))`,
   `noise = dict(state.get("score_noise", {}))` (copies: this agent **adds** to what earlier agents produced; there
   is no reducer because nodes run strictly one after another).
3. For each company `c` in `state["companies"]` (in order): `text = state["criterion_texts"][f"{c}|{criterion}"]`;
   `drawn = scorer.score(c, criterion, text, settings["k"])`; `score, std = aggregate(drawn)`; if not
   `quote_in_text(score.evidence, text)` raise `ValueError(f"evidence not in 10-K text: {c}, {criterion}")`; append
   `score`; `samples[f"{c}|{criterion}"] = [s.score for s in drawn]`; `noise[...] = std`. Log progress with
   `logging.getLogger("maid.agents").info("%s %d/%d %s", criterion, i, n, c)`.
   `ScoringError` and `ContextTruncated` propagate (the run stops; re-running reuses every cached reply).
4. Return `{"qualitative": qualitative, "score_samples": samples, "score_noise": noise, "agent_runs":
   {**state.get("agent_runs", {}), criterion: {"model": sorted({r["model"] for r in scorer.log}),
   "prompt_version": PROMPT_VERSION, "calls": len(scorer.log), "failed_attempts": sum(not r["ok"] for r in
   scorer.log), "prompt_tokens": sum(r["prompt_tokens"] for r in scorer.log), "completion_tokens": sum(...),
   "seconds": round(time.perf_counter() - t0, 1)}}}`.

`score_qualitative` (the demo stub node) stays exactly as it is, except its `sec` branch must not wipe agent results:
it already runs **before** the agents, so keep the order below and leave its body unchanged.

`build_graph`: nodes in this order, with linear edges:
`ingest → score_qualitative → agent_pricing_power → agent_strategy_clarity → agent_capital_allocation → human_review → mcdm → robustness → report`.
Build the agent nodes with a loop over `LLM_CRITERIA` (`g.add_node(f"agent_{k}", make_agent(k))`) and the edges from
a list of node names, so the order is defined once.

### Step 4: report

In `report`, when `st["scorer"] == "llm"`:
- header line: `# MAID report: real data ({sector}, quantitative + local LLM scores)` and the blockquote:
  `> **Real data**: SEC XBRL and 10-K text, point-in-time on {date}; LLM scores from a local model, agents run one
  after another (D21). Local only: do not commit.`
- drop the "No LLM scores in this run" line;
- add a section after the ranking: `## Agents (sequential jobs, D21)` with a table
  `| Agent | Model | Prompt version | Calls | Failed attempts | Prompt tokens | Minutes |`, one row per entry of
  `state["agent_runs"]` in `LLM_CRITERIA` order (minutes = seconds / 60, 1 decimal);
- last line: `LLMs never rank: scores come from local LLM agents run one after another (D21); ranks come from the MCDM engine.`
The demo and quant-only reports must stay byte-identical (Step 0 check; the quant-only tests check their text).
Also add `scorer={st['scorer']}, limit={st['limit']}` to the Settings line **only** when `scorer == "llm"` (so the
demo output is unchanged).

### Step 5: CLI and GUI

- `demo.py` `main`: add `--scorer` (choices `auto`, `llm`) and `--limit` (int), passed into settings like the others.
  Update the module docstring to `"""Run the whole pipeline: python -m maid.demo [--source sec] [--sector staples --scorer llm --limit 10]."""`.
- `gui_data.py` `DEFAULT_STATUSES`: add `"agent_pricing_power": "stub", "agent_strategy_clarity": "stub",
  "agent_capital_allocation": "stub"` (on demo data these nodes do nothing). The GUI itself is unchanged.

### Step 6: tests (`tests/test_real_data.py`, no network)

Write a staples fixture: monkeypatch `graph.load_sec` with `lambda d, sector="tech": sec_quantitative(ROWS, fake_facts,
d, "staples")` (check `sec_quantitative`'s signature in `real_data.py` and the existing `test_graph_sec_staples` for
how staples is faked; copy that), `graph.load_filings` with a lambda returning `(labels, texts, {})` where every
company's `texts[c] = {"1": "We aim to grow margins 2% by 2026.", "1a": "", "7": "<an MD&A with a sentence per
criterion>"}` (keep it short; `criterion_text` must work on it), and `graph.make_client` with a lambda returning a
FakeClient (copy the class from `tests/test_llm.py`) whose replies quote a sentence from the right slice. Set
`MAID_CACHE_DIR` to `tmp_path` with `monkeypatch.setenv`. **Hint:** the reply must quote text from the slice that the
criterion reads (`strategy_clarity` reads `"1"`; the two others read `"7"`); a FakeClient that picks the reply by
looking for a marker in the user message is the simplest way.

Tests:
1. `build_graph().get_graph()` node order contains `agent_pricing_power`, `agent_strategy_clarity`,
   `agent_capital_allocation` in this order between `score_qualitative` and `human_review`.
2. Sequential jobs: in an `llm` run with 3 companies and k = 2, the criteria of the FakeClient's calls (read from the
   rubric text in the system message) are all `pricing_power` first, then all `strategy_clarity`, then all
   `capital_allocation`.
3. The run interrupts for review (`"__interrupt__"` in the first invoke result); after `run_demo(...)` the final state
   has 3 × 3 qualitative scores, `criteria` = staples quantitative criteria + `LLM_CRITERIA`, `agent_runs` has 3
   entries, and the report contains `## Agents (sequential jobs, D21)` and `run one after another`.
4. Resume from cache: a second `run_demo` with the same settings and a FakeClient with an empty reply queue makes 0
   calls and gives the same ranking.
5. `limit=2` → 2 companies.
6. No ticker in any prompt: every user message of the FakeClient calls contains no ticker from the fake universe.
7. Demo unchanged: `run_demo({"n_draws": 50})` report has no `## Agents` section, and `agent_runs` is absent or empty.

### Step 7: docs

`docs/architecture/graph.md`: in the node table, add one row per agent node (inputs: `companies`,
`criterion_texts`, `settings`, existing `qualitative`; outputs: `qualitative`, `score_samples`, `score_noise`,
`agent_runs`; status: `built (local LLM, sequential, D21); no-op unless scorer="llm"`), and add a short paragraph
under the table:
`The three criterion agents are separate nodes that run one after another (D21: one local model fills the GPU). Each
adds its scores to what earlier agents produced, so no reducer is needed. Every reply is cached, so an interrupted run
resumes where it stopped.` Update the mermaid diagram of the current graph in graph.md if it lists nodes (add the three
agent nodes in order). Do not touch the "Not used: parallel scoring with Send" section.

### Step 8: gates and commit

Full `pytest -q` passes; `ruff check .` clean; the "Demo unchanged" output equals Step 0's
(`diff /tmp/claude-1000/demo_before.txt /tmp/claude-1000/demo_after.txt` prints nothing). Commit
`feat(graph): three local LLM criterion agents as sequential, cache-resumable nodes (D21)`, body `Refs plan 033`,
line `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Done criteria

- All tests pass (at least 10 new); ruff clean; demo output identical.
- `git diff --stat <BASE>..HEAD` lists only `src/maid/graph.py`, `src/maid/state.py`, `src/maid/demo.py`,
  `src/maid/gui_data.py`, `tests/test_real_data.py`, `docs/architecture/graph.md` (and `tests/test_gui_data.py`
  only if its node test needs the new statuses).

## Out of scope

- `llm.py`, `rubrics.py`, `tenk.py`, `real_data.py`, the MCDM engine, `app/streamlit_app.py`.
- Parallelism of any kind (threads, async, `Send`): forbidden by D21.
- Running a real LLM job.

## STOP conditions

- Drift check shows changes.
- The demo output changes and you cannot make it identical without touching out-of-scope files.
- `human_review`'s interrupt or `run_demo`'s resume does not behave as described with LLM scores.
- `MemorySaver` fails to checkpoint the new state keys (serialization error): report the error.

## Maintenance notes

- A cell with `ScoringError` stops the whole run on purpose (the matrix needs every cell). Fix by changing the prompt
  (bump `PROMPT_VERSION`) or, later, by letting the human fill the cell at review.
- `criterion_texts` for 61 companies is ~15 MB in state; `MemorySaver` keeps it in memory. Fine for one run.
- The pilot script (`scripts/score_pilot.py`) and the graph share the same cache directory (`data/cache/llm`) and
  keys, so pilot replies are reused by the graph run.
