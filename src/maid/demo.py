"""Run the whole pipeline: python -m maid.demo [--source sec] [--sector staples --scorer llm --limit 10]."""
import argparse
import json

from langgraph.types import Command

from maid.graph import build_graph
from maid.state import CriterionScore, ScoreOverride


def run_demo(settings: dict | None = None, overrides: list[dict] | None = None, thread_id: str = "demo") -> dict:
    """Run the graph, auto-resume the human review with `overrides`, return the final state."""
    graph = build_graph()
    cfg = {"configurable": {"thread_id": thread_id}}
    result = graph.invoke({"settings": settings or {}}, cfg)
    if "__interrupt__" in result:
        graph.invoke(Command(resume={"overrides": overrides or []}), cfg)
    return graph.get_state(cfg).values


def _jsonable(o):
    """Convert Pydantic models in state to plain dicts for JSON output."""
    if isinstance(o, (CriterionScore, ScoreOverride)):
        return o.model_dump()
    raise TypeError(f"not JSON serializable: {type(o)}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", choices=["demo", "sec"])
    p.add_argument("--sector", choices=["tech", "staples"])
    p.add_argument("--weighting", choices=["entropy", "critic", "equal"])
    p.add_argument("--k", type=int)
    p.add_argument("--seed", type=int)
    p.add_argument("--n-draws", type=int)
    p.add_argument("--concentration", type=float)
    p.add_argument("--scorer", choices=["auto", "llm"])
    p.add_argument("--limit", type=int)
    p.add_argument("--overrides", help="path to a JSON list of {company, criterion, score, reason}")
    p.add_argument("--json", help="write the final state as JSON to this path (with --source sec, write it under data/: real data stays local)")
    a = p.parse_args()
    given = {"source": a.source, "sector": a.sector,"weighting": a.weighting, "k": a.k, "seed": a.seed, "n_draws": a.n_draws, "concentration": a.concentration,
             "scorer": a.scorer, "limit": a.limit}
    settings = {k: v for k, v in given.items() if v is not None}
    overrides = None
    if a.overrides:
        with open(a.overrides) as f:
            overrides = json.load(f)
    state = run_demo(settings, overrides)
    print(state["report"])
    if a.json:
        with open(a.json, "w") as f:
            json.dump(state, f, default=_jsonable, indent=2)


if __name__ == "__main__":
    main()
