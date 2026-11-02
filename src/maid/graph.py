"""LangGraph pipeline matching docs/SCOPE.md section 5. Runs on a synthetic demo dataset with a stub scorer."""
import numpy as np
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from maid.demo_data import QUAL_CRITERIA, QUANT_CRITERIA, demo_dataset
from maid.matrix import apply_overrides, build_matrix, kendall_tau
from maid.mcdm import critic_weights, entropy_weights, equal_weights, robust_ranking, saw, topsis
from maid.scoring import StubScorer, aggregate, evidence_is_quoted
from maid.state import CHECKPOINT_TYPES, CriterionScore, PipelineState, ScoreOverride

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
        "companies": list(companies),
        "quantitative": {c: ds.quantitative[c] for c in companies},
        "filings": {c: ds.filings[c] for c in companies},
        "criteria": QUANT_CRITERIA + QUAL_CRITERIA,
        "settings": settings,
    }


def score_qualitative(state: PipelineState) -> dict:
    """Score each company and qualitative criterion with the stub scorer (K samples, median, evidence check)."""
    settings = _settings(state)
    scorer = StubScorer(demo_dataset(seed=settings["seed"]).latent, seed=settings["seed"])
    qualitative, samples, noise = [], {}, {}
    for c in state["companies"]:
        for crit in QUAL_CRITERIA:
            drawn = scorer.score(c, crit, state["filings"][c], settings["k"])
            score, std = aggregate(drawn)
            assert evidence_is_quoted(score, state["filings"][c]), f"evidence not in filing: {c}, {crit}"
            qualitative.append(score)
            samples[f"{c}|{crit}"] = [s.score for s in drawn]
            noise[f"{c}|{crit}"] = std
    return {"qualitative": qualitative, "score_samples": samples, "score_noise": noise}


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
    """Apply overrides, build X, compute weights (entropy/CRITIC/equal), TOPSIS and SAW scores, the ranking."""
    settings = _settings(state)
    if settings["weighting"] not in WEIGHT_FNS:
        raise ValueError(f"unknown weighting: {settings['weighting']!r}")
    qualitative = apply_overrides(state["qualitative"], state.get("overrides", []))
    X = build_matrix(state["companies"], state["quantitative"], qualitative, state["criteria"])
    w = WEIGHT_FNS[settings["weighting"]](X)
    t, s = topsis(X, w), saw(X, w)
    order = np.argsort(-t, kind="stable")
    return {
        "matrix": X.tolist(),
        "weights": dict(zip(state["criteria"], map(float, w), strict=True)),
        "scores": {"topsis": t.tolist(), "saw": s.tolist()},
        "ranking": [state["companies"][i] for i in order],
        "method_agreement": {"kendall_tau_topsis_saw": kendall_tau(t, s)},
    }


def robustness(state: PipelineState) -> dict:
    """Rank intervals under bootstrap and Dirichlet weight perturbation."""
    settings = _settings(state)
    res = robust_ranking(
        np.array(state["matrix"]), WEIGHT_FNS[settings["weighting"]], topsis,
        n_draws=settings["n_draws"], concentration=settings["concentration"], seed=settings["seed"],
    )
    fields = ("point", "median", "lo", "hi", "acceptability")
    return {"robustness": {src: {f: getattr(r, f).tolist() for f in fields} | {"n_draws": r.n_draws}
                           for src, r in res.items()}}


def report(state: PipelineState) -> dict:
    """Markdown report built from state only."""
    cs, st, rb = state["companies"], state["settings"], state["robustness"]
    top, sw = state["scores"]["topsis"], state["scores"]["saw"]
    bo, di = rb["bootstrap"], rb["dirichlet"]
    tau = state["method_agreement"]["kendall_tau_topsis_saw"]
    lines = [
        "# MAID demo report", "",
        "> **Synthetic demo data**: invented companies, not real ones. Decision date 2024-12-31.", "",
        f"Settings: weighting={st['weighting']}, k={st['k']}, seed={st['seed']}, "
        f"n_draws={st['n_draws']}, concentration={st['concentration']}", "",
        "## Ranking (by TOPSIS)", "",
        "| Rank | Company | TOPSIS | SAW | Bootstrap 90% rank | Dirichlet 90% rank | P(rank 1) Dirichlet |",
        "|---|---|---|---|---|---|---|",
    ]
    for r, c in enumerate(state["ranking"], 1):
        i = cs.index(c)
        lines.append(f"| {r} | {c} | {top[i]:.3f} | {sw[i]:.3f} | {bo['lo'][i]:.0f}-{bo['hi'][i]:.0f} | "
                     f"{di['lo'][i]:.0f}-{di['hi'][i]:.0f} | {di['acceptability'][i][0]:.2f} |")
    lines += ["", "## Weights", "", "| Criterion | Weight |", "|---|---|"]
    lines += [f"| {k} | {v:.3f} |" for k, v in state["weights"].items()]
    lines += ["", f"Method agreement (Kendall tau, TOPSIS vs SAW): {tau:.3f}", "", "## Human overrides", ""]
    lines += [f"- {o.company} / {o.criterion} -> {o.score}: {o.reason}" for o in state.get("overrides", [])] or ["none"]
    lines += ["", "LLMs never rank: scores come from the (stub) scorer, ranks from the MCDM engine.", ""]
    return {"report": "\n".join(lines)}


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
