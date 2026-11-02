"""LangGraph skeleton matching docs/SCOPE.md section 5. Nodes are stubs for now."""
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from maid.state import CHECKPOINT_TYPES, CriterionScore, PipelineState, ScoreOverride


def ingest(state: PipelineState) -> dict:
    return {"quantitative": {}}


def score_qualitative(state: PipelineState) -> dict:
    return {"qualitative": []}


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


def mcdm(state: PipelineState) -> dict:
    return {"weights": {}, "ranking": []}


def robustness(state: PipelineState) -> dict:
    return {}


def report(state: PipelineState) -> dict:
    return {"report": ""}


def build_graph():
    g = StateGraph(PipelineState)
    for name, fn in [
        ("ingest", ingest),
        ("score_qualitative", score_qualitative),
        ("human_review", human_review),
        ("mcdm", mcdm),
        ("robustness", robustness),
        ("report", report),
    ]:
        g.add_node(name, fn)
    g.add_edge(START, "ingest")
    g.add_edge("ingest", "score_qualitative")
    g.add_edge("score_qualitative", "human_review")
    g.add_edge("human_review", "mcdm")
    g.add_edge("mcdm", "robustness")
    g.add_edge("robustness", "report")
    g.add_edge("report", END)
    serde = JsonPlusSerializer(allowed_msgpack_modules=CHECKPOINT_TYPES)
    return g.compile(checkpointer=MemorySaver(serde=serde))
