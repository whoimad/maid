"""Pure data shaping for the Streamlit GUI: plain rows (list of dicts) and strings, no streamlit import."""
import numpy as np

from maid.graph import build_graph
from maid.mcdm import critic_weights, entropy_weights, equal_weights

DEFAULT_STATUSES = {
    "ingest": "demo", "score_qualitative": "demo", "human_review": "real",
    "mcdm": "real", "robustness": "real", "report": "real",
    "agent_pricing_power": "stub", "agent_strategy_clarity": "stub", "agent_capital_allocation": "stub",
}
FILL = {"real": "#b7e4c7", "demo": "#ffe8a3", "stub": "#d9d9d9"}


def pipeline_dot(statuses: dict[str, str] | None = None) -> str:
    """Graphviz DOT of the pipeline graph, left to right, nodes filled by status (real/demo/stub)."""
    st = {**DEFAULT_STATUSES, **(statuses or {})}
    g = build_graph().get_graph()
    lines = ["digraph maid {", "  rankdir=LR;", '  node [shape=box, style="rounded,filled"];']
    for n in g.nodes:
        fill = FILL.get(st.get(n), "#ffffff")
        lines.append(f'  "{n}" [fillcolor="{fill}"];')
    lines += [f'  "{e.source}" -> "{e.target}";' for e in g.edges]
    return "\n".join(lines + ["}"])


def matrix_rows(state) -> list[dict]:
    """One row per company with every criterion value (after overrides)."""
    return [{"company": c, **dict(zip(state["criteria"], row, strict=True))}
            for c, row in zip(state["companies"], state["matrix"], strict=True)]


def score_rows(state) -> list[dict]:
    """One row per company x qualitative criterion: score, K samples, noise, evidence, overridden flag."""
    over = {(o.company, o.criterion) for o in state.get("overrides", [])}
    rows = []
    for s in state["qualitative"]:
        key = f"{s.company}|{s.criterion}"
        rows.append({
            "company": s.company, "criterion": s.criterion, "score": s.score,
            "samples": ", ".join(map(str, state["score_samples"][key])),
            "noise": round(state["score_noise"][key], 3), "evidence": s.evidence,
            "overridden": (s.company, s.criterion) in over,
        })
    return rows


def weight_rows(state) -> list[dict]:
    """Long-form weights for entropy, CRITIC and equal, computed from the matrix; `used` marks the chosen one."""
    X = np.array(state["matrix"])
    used = state["settings"]["weighting"]
    rows = []
    for m, fn in [("entropy", entropy_weights), ("critic", critic_weights), ("equal", equal_weights)]:
        rows += [{"method": m, "criterion": c, "weight": float(w), "used": m == used}
                 for c, w in zip(state["criteria"], fn(X), strict=True)]
    return rows


def ranking_rows(state) -> list[dict]:
    """Per company in TOPSIS order: rank, TOPSIS and SAW scores, SAW rank."""
    cs, top, sw = state["companies"], state["scores"]["topsis"], state["scores"]["saw"]
    saw_order = np.argsort(-np.array(sw), kind="stable")
    saw_rank = {int(i): r for r, i in enumerate(saw_order, 1)}
    return [{"rank": r, "company": c, "topsis": top[cs.index(c)], "saw": sw[cs.index(c)],
             "saw_rank": saw_rank[cs.index(c)]} for r, c in enumerate(state["ranking"], 1)]


def interval_rows(state, source: str) -> list[dict]:
    """Per company point rank, median and 90% interval for `source` (bootstrap, dirichlet or score_noise), sorted by point."""
    r = state["robustness"][source]
    rows = [{"company": c, "point": r["point"][i], "median": r["median"][i], "lo": r["lo"][i], "hi": r["hi"][i]}
            for i, c in enumerate(state["companies"])]
    return sorted(rows, key=lambda x: x["point"])


def acceptability_rows(state, source: str) -> list[dict]:
    """Long-form share of draws in which each company got each rank (zeros skipped)."""
    acc = state["robustness"][source]["acceptability"]
    return [{"company": c, "rank": j + 1, "share": v}
            for c, row in zip(state["companies"], acc, strict=True) for j, v in enumerate(row) if v > 0]
