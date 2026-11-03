# Plan 007: A LangGraph block doc explains state, nodes, interrupt/resume and the target fan-out, with a diagram the tests keep in sync with the code

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat 258af88..HEAD -- src/maid/graph.py src/maid/state.py docs/architecture/graph.md tests/test_docs.py`
> Expected drift: `tests/test_docs.py` was created by plan 006. Any change to `graph.py` or `state.py` → compare
> against "Current state"; on a mismatch, STOP.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: LOW (docs + one test; no source changes)
- **Depends on**: plans/006-overview-accuracy-and-c4.md (creates `tests/test_docs.py` and the status table)
- **Category**: docs
- **Planned at**: commit `258af88`, 2026-11-02

## Why this matters

LangGraph is the part of the project an interviewer is most likely to probe ("why LangGraph?", "how does the
human-in-the-loop actually work?", "what happens on a crash?"). Today there is no doc for it: the reasoning is
split between a few lines in `docs/architecture/overview.md` and a research note. This plan writes
`docs/architecture/graph.md`: what each node does, what state it reads and writes, how `interrupt`/resume works,
what is a stub, and what the target fan-out design is and why. The diagram of the current graph is checked by a
test against the real compiled graph, so the doc cannot silently drift from the code.

## Current state

`src/maid/graph.py` (full, at 258af88; 61 lines). Key parts:

```python
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

def ingest(state): return {"quantitative": {}}
def score_qualitative(state): return {"qualitative": []}

def parse_overrides(decision, qualitative):
    """Resume payload: {"overrides": [{company, criterion, score, reason}, ...]}; {} or None means no changes."""
    # None -> []; non-dict -> ValueError; each item validated as ScoreOverride;
    # overrides naming a (company, criterion) not in `qualitative` -> ValueError

def human_review(state):
    # Pauses the graph; resume with Command(resume={"overrides": [...]}).
    decision = interrupt({"qualitative": state.get("qualitative", [])})
    return {"overrides": parse_overrides(decision, state.get("qualitative", []))}

def mcdm(state): return {"weights": {}, "ranking": []}
def robustness(state): return {}
def report(state): return {"report": ""}

def build_graph():
    g = StateGraph(PipelineState)
    # nodes: ingest, score_qualitative, human_review, mcdm, robustness, report
    # edges: START->ingest->score_qualitative->human_review->mcdm->robustness->report->END
    serde = JsonPlusSerializer(allowed_msgpack_modules=CHECKPOINT_TYPES)
    return g.compile(checkpointer=MemorySaver(serde=serde))
```

`src/maid/state.py` (full):

```python
class CriterionScore(BaseModel):
    company: str  # anonymized label, e.g. "Company A"
    criterion: str
    score: int = Field(ge=1, le=9)
    evidence: str  # quote that must appear in the source filing

class ScoreOverride(BaseModel):
    """A human correction of one LLM score; the reason is mandatory so disagreements can be analyzed later."""
    company: str; criterion: str; score: int = Field(ge=1, le=9); reason: str = Field(min_length=1)

class PipelineState(TypedDict, total=False):
    companies: list[str]
    quantitative: dict[str, dict[str, float]]  # company -> criterion -> value
    qualitative: list[CriterionScore]
    overrides: list[ScoreOverride]
    weights: dict[str, float]
    ranking: list[str]
    report: str

# Pydantic types stored in graph state; checkpoints must be allowed to restore them.
CHECKPOINT_TYPES = [("maid.state", "CriterionScore"), ("maid.state", "ScoreOverride")]
```

No state key has a reducer (no `Annotated[..., operator.add]`), so each write replaces the key's value.

How the existing test drives the interrupt (`tests/test_scaffold.py`):

```python
graph = build_graph()
cfg = {"configurable": {"thread_id": "t1"}}
result = graph.invoke({"companies": ["Company A"]}, cfg)
assert "__interrupt__" in result
final = graph.invoke(Command(resume={"overrides": []}), cfg)
assert "report" in final
```

LangGraph facts to use (from `docs/research/llm-agents-finance.md` §3, sourced from LangGraph docs; keep the
"per our research note" framing, do not add new claims):
- `Send` objects returned from a conditional edge give map-reduce fan-out; the destinations run in the same superstep (in parallel).
- Each state key has its own reducer; parallel writes to one list key need a reducer such as `Annotated[list, operator.add]` (the note marks this exact snippet UNVERIFIED).
- `interrupt()` pauses; resume with `Command(resume=...)`; the value passed becomes the return value of `interrupt()`.
- On resume, the interrupted node **re-runs from its start**, so anything before `interrupt()` in that node must be idempotent.
- Checkpoints are saved at superstep boundaries. Interrupts inside parallel branches are not documented in what the research read; avoid them.
- Target design (research note §4 item 5): fan out via `Send` per (company, criterion); reduce into a dict keyed by (company, criterion); single `interrupt` in a node after the join; persistent checkpointer; idempotent review node.

Decision D6 (`docs/architecture/decisions.md`): LangGraph chosen over plain Python functions because built-in
checkpointing and `interrupt` give human-in-the-loop cheaply and the graph mirrors the architecture diagram;
cost: a framework dependency for a mostly linear pipeline.

Why `CHECKPOINT_TYPES` exists: the checkpointer serializes state with msgpack; LangGraph's `JsonPlusSerializer`
only restores Pydantic classes listed in `allowed_msgpack_modules` (strict allowlist), so `CriterionScore` and
`ScoreOverride` must be listed or a resumed run cannot rebuild them. (This was added in plan 004 and is
exercised by `tests/test_review.py`.)

Doc style exemplar: `docs/architecture/mcdm.md` (title `# Block: ...`, a **Responsibility:** line, Mermaid
diagram, tables, "Why these choices", "Known limitations").

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Print current graph edges | `python -c "from maid.graph import build_graph; print(sorted((e.source, e.target) for e in build_graph().get_graph().edges))"` | 7 pairs, linear chain |
| Tests | `pytest -q` | all pass |
| Lint | `ruff check .` | `All checks passed!` |

## Scope

**In scope**: `docs/architecture/graph.md` (create), `tests/test_docs.py` (add one test),
`docs/architecture/overview.md` (add one line to the "Blocks" list only).

**Out of scope**: everything in `src/` (do NOT implement `Send`, reducers or a SQLite checkpointer; this plan
only documents them as planned), other docs.

## Git workflow

Branch `docs/graph-block` from `main` (after plan 006 is merged). Commit e.g.
`docs(architecture): add LangGraph block doc with code-checked diagram`, ending with
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Do NOT push or open a PR unless instructed.

## Steps

### Step 1: Write the sync test first

In `tests/test_docs.py` add `test_graph_doc_diagram_matches_code`:
- Read `docs/architecture/graph.md`; find the line `<!-- current-graph: kept in sync with build_graph() by tests/test_docs.py -->`;
  take the first ```` ```mermaid ```` block after it.
- Parse edges from lines matching `^\s*(\w+)\s*-->\s*(\w+)\s*;?\s*$` (plain arrows only, no labels).
- Assert the set equals `{(e.source, e.target) for e in build_graph().get_graph().edges}`.
Node ids in the doc must therefore be the code names, including `__start__` and `__end__`.

**Verify**: `pytest -q tests/test_docs.py` → the new test fails (file missing). The link test still passes.

### Step 2: Write `docs/architecture/graph.md`

Sections, in order:
1. `# Block: Pipeline orchestration (src/maid/graph.py, src/maid/state.py)` and a **Responsibility:** line
   (wire the steps, carry shared state, pause for human review, resume).
2. `## Current graph` — the marker comment from Step 1, then a `flowchart LR` Mermaid block with exactly the 7
   edges as `a --> b` lines using code names. Under it: one sentence "Linear; every node except `human_review`
   is a stub today (see the status table in overview.md)."
3. `## Nodes and state` — table: Node | Reads | Writes | Status. Fill from `graph.py` above
   (e.g. `human_review` reads `qualitative`, writes `overrides`, implemented). Then a short list of the
   `PipelineState` keys with one line each, and the two Pydantic models (why `evidence` and `reason` are mandatory:
   every LLM score must be auditable; every override must be explainable).
4. `## Human-in-the-loop: interrupt and resume` — a Mermaid `sequenceDiagram` with participants Caller, Graph,
   human_review node, Checkpointer: invoke → nodes run → `interrupt(payload)` → checkpoint saved → caller gets
   `__interrupt__` → caller sends `Command(resume={"overrides": [...]})` → node **re-runs from its start**,
   `interrupt()` now returns the payload → `parse_overrides` validates → graph continues to `mcdm`.
   Then bullets: the resume payload format; validation rules of `parse_overrides`; why the node must be idempotent;
   why `CHECKPOINT_TYPES` exists (text from Current state).
5. `## Checkpointer: MemorySaver today, persistent later` — what MemorySaver gives (pause/resume inside one
   process, keyed by `thread_id`) and does not (a restart loses the paused run). Planned: a persistent checkpointer
   such as SQLite. Mark as planned.
6. `## Target design: parallel scoring with Send` — a Mermaid flowchart: `ingest` → conditional edge returning one
   `Send("score_one", {company, criterion})` per pair → many `score_one` boxes → join (reducer merges results into
   one dict keyed by (company, criterion)) → `human_review` (single interrupt, after the join) → `mcdm`.
   Label the whole section **planned, not implemented**. Explain in 3–5 bullets why: parallel LLM calls; each
   branch independently cached and retried; the reducer is needed because without one parallel writes to the same
   key conflict; interrupt after the join so the human reviews all scores once (interrupts inside parallel
   branches are not documented). Attribute these to `docs/research/llm-agents-finance.md`.
7. `## Why LangGraph (and not plain functions)` — restate D6 with its cost in 3–4 lines and link
   `[decisions.md](decisions.md)`. Add the honest counterpoint: for today's linear pipeline, plain functions would
   be simpler; LangGraph pays off with the interrupt, checkpointing and the planned fan-out.
8. `## Known limitations` — MemorySaver only; overrides validated but not applied; no fan-out; nodes are stubs.

**Verify**: `pytest -q tests/test_docs.py` → 2 passed.

### Step 3: Link it

Add `- [graph.md](graph.md): LangGraph pipeline, state, interrupt/resume (skeleton implemented, nodes mostly stubs)`
to the Blocks list in `docs/architecture/overview.md`, directly above the `mcdm.md` line.

**Verify**: `pytest -q && ruff check .` → all pass, `All checks passed!`

## Done criteria

- [ ] `pytest -q` passes, including `test_graph_doc_diagram_matches_code` and the link test
- [ ] `ruff check .` → `All checks passed!`
- [ ] `grep -c "planned" docs/architecture/graph.md` → ≥ 2
- [ ] `grep -c '```mermaid' docs/architecture/graph.md` → 3
- [ ] `git diff --stat main -- src` → empty
- [ ] `plans/README.md` row updated

## STOP conditions

- The printed graph edges are not the 7-edge linear chain → the code changed; STOP.
- You feel the need to change `graph.py`/`state.py` to make the doc or test work → STOP.
- `tests/test_docs.py` does not exist (plan 006 not merged) → STOP.

## Maintenance notes

- When the fan-out is built, the sync test will fail until the "Current graph" diagram is updated: that is the
  point. Move content from "Target design" into "Current graph" then.
- Reviewers: check that nothing in "Target design" is described as working today.
