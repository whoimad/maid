"""LangGraph skeleton matching docs/SCOPE.md section 5. Nodes are stubs for now."""
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from maid.state import PipelineState


def ingest(state: PipelineState) -> dict:
    return {"quantitative": {}}


def score_qualitative(state: PipelineState) -> dict:
    return {"qualitative": []}


def human_review(state: PipelineState) -> dict:
    # Pauses the graph; resume with Command(resume=...) carrying overrides.
    interrupt({"qualitative": state.get("qualitative", [])})
    return {}


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
    return g.compile(checkpointer=MemorySaver())
