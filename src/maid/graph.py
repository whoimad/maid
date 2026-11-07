"""LangGraph pipeline matching docs/SCOPE.md section 5. Runs on a synthetic demo dataset with a stub scorer."""
import logging
import time

import numpy as np
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from maid.cache import DiskCache
from maid.config import get_settings
from maid.demo_data import QUAL_CRITERIA, QUANT_CRITERIA, demo_dataset
from maid.llm import LLMScorer, make_client, quote_in_text
from maid.matrix import apply_overrides, build_matrix, kendall_tau
from maid.mcdm import critic_weights, entropy_weights, equal_weights, robust_ranking, saw, topsis
from maid.real_data import SECTORS, load_filings, load_sec
from maid.rubrics import PROMPT_VERSION
from maid.scoring import StubScorer, aggregate, evidence_is_quoted
from maid.state import CHECKPOINT_TYPES, CriterionScore, PipelineState, ScoreOverride
from maid.tenk import criterion_text

DEFAULT_SETTINGS = {"source": "demo", "sector": "tech", "k": 5, "weighting": "critic", "seed": 0, "n_draws": 500, "concentration": 100.0,
                    "scorer": "auto", "limit": 0}
LLM_CRITERIA = ["pricing_power", "strategy_clarity", "capital_allocation"]  # agent order (D21: sequential)
WEIGHT_FNS = {"entropy": entropy_weights, "critic": critic_weights, "equal": equal_weights}


def validate_settings(settings: dict) -> dict:
    """Merge with defaults and reject unknown keys or out-of-range values (ValueError)."""
    merged = {**DEFAULT_SETTINGS, **settings}
    if extra := set(merged) - set(DEFAULT_SETTINGS):
        raise ValueError(f"unknown settings: {sorted(extra)}")
    if merged["weighting"] not in WEIGHT_FNS:
        raise ValueError(f"unknown weighting: {merged['weighting']!r}")
    if merged["source"] not in ("demo", "sec"):
        raise ValueError(f"unknown source: {merged['source']!r}")
    if merged["sector"] not in ("tech", "staples"):
        raise ValueError(f"unknown sector: {merged['sector']!r}")
    if merged["scorer"] not in ("auto", "llm"):
        raise ValueError(f"unknown scorer: {merged['scorer']!r}")
    if merged["scorer"] == "llm" and (merged["source"], merged["sector"]) != ("sec", "staples"):
        raise ValueError('scorer="llm" requires source="sec" and sector="staples"')
    for key, low in (("k", 1), ("seed", 0), ("n_draws", 1), ("limit", 0)):
        v = merged[key]
        if not isinstance(v, int) or isinstance(v, bool) or v < low:
            raise ValueError(f"{key} must be an int >= {low}: {v!r}")
    c = merged["concentration"]
    if not isinstance(c, (int, float)) or isinstance(c, bool) or not np.isfinite(c) or c <= 0:
        raise ValueError(f"concentration must be a finite number > 0: {c!r}")
    return merged


def _settings(state: PipelineState) -> dict:
    return validate_settings(state.get("settings", {}))


def ingest(state: PipelineState) -> dict:
    """Load inputs: the synthetic demo dataset, or (source="sec") the frozen tech universe from SEC XBRL, quant only."""
    settings = _settings(state)
    if settings["source"] == "sec":
        tickers, quant, _ = load_sec(get_settings().decision_date, settings["sector"])
        available, filings, criteria = list(tickers), {c: "" for c in tickers}, list(SECTORS[settings["sector"]][1])
    else:
        ds = demo_dataset(seed=settings["seed"])
        tickers, quant, filings = {}, ds.quantitative, ds.filings
        available, criteria = ds.companies, QUANT_CRITERIA + QUAL_CRITERIA
    companies = state.get("companies") or available
    if settings["source"] == "sec" and settings["limit"] > 0 and not state.get("companies"):
        companies = sorted(available)[:settings["limit"]]
    unknown = [c for c in companies if c not in available]
    if unknown:
        raise ValueError(f"unknown companies: {unknown}")
    if len(set(companies)) != len(companies):
        raise ValueError(f"duplicate companies: {companies}")
    criterion_texts = {}
    if settings["source"] == "sec" and settings["scorer"] == "llm":
        _, texts, _ = load_filings(get_settings().decision_date, settings["sector"])
        criterion_texts = {f"{c}|{k}": criterion_text(texts[c], k)["text"] for c in companies for k in LLM_CRITERIA}
        criteria = criteria + LLM_CRITERIA
    return {
        "criterion_texts": criterion_texts,
        "companies": list(companies),
        "quantitative": {c: quant[c] for c in companies},
        "filings": {c: filings[c] for c in companies},
        "tickers": {c: tickers[c] for c in companies if c in tickers},
        "criteria": criteria,
        "settings": settings,
    }


def score_qualitative(state: PipelineState) -> dict:
    """Score each company and qualitative criterion with the stub scorer (K samples, median, evidence check)."""
    settings = _settings(state)
    if settings["source"] == "sec":  # quant-only baseline (SCOPE section 6): no LLM scorer on real data yet
        return {"qualitative": [], "score_samples": {}, "score_noise": {}}
    scorer = StubScorer(demo_dataset(seed=settings["seed"]).latent, seed=settings["seed"])
    qualitative, samples, noise = [], {}, {}
    for c in state["companies"]:
        for crit in QUAL_CRITERIA:
            drawn = scorer.score(c, crit, state["filings"][c], settings["k"])
            score, std = aggregate(drawn)
            if not evidence_is_quoted(score, state["filings"][c]):
                raise ValueError(f"evidence not in filing: {c}, {crit}")
            qualitative.append(score)
            samples[f"{c}|{crit}"] = [s.score for s in drawn]
            noise[f"{c}|{crit}"] = std
    return {"qualitative": qualitative, "score_samples": samples, "score_noise": noise}


def make_agent(criterion: str):
    """Graph node for one LLM criterion agent: scores every company for its criterion, one call at a time."""
    def agent(state: PipelineState) -> dict:
        settings = _settings(state)
        if settings["scorer"] != "llm":
            return {}
        cfg = get_settings()
        scorer = LLMScorer(make_client(cfg), cfg.model, DiskCache(cfg.cache_dir / "llm"), seed=settings["seed"])
        t0 = time.perf_counter()
        qualitative = list(state.get("qualitative", []))
        samples, noise = dict(state.get("score_samples", {})), dict(state.get("score_noise", {}))
        n = len(state["companies"])
        for i, c in enumerate(state["companies"], 1):
            text = state["criterion_texts"][f"{c}|{criterion}"]
            drawn = scorer.score(c, criterion, text, settings["k"])
            score, std = aggregate(drawn)
            if not quote_in_text(score.evidence, text):
                raise ValueError(f"evidence not in 10-K text: {c}, {criterion}")
            qualitative.append(score)
            samples[f"{c}|{criterion}"] = [s.score for s in drawn]
            noise[f"{c}|{criterion}"] = std
            logging.getLogger("maid.agents").info("%s %d/%d %s", criterion, i, n, c)
        run = {"model": sorted({r["model"] for r in scorer.log}), "prompt_version": PROMPT_VERSION,
               "calls": len(scorer.log), "failed_attempts": sum(not r["ok"] for r in scorer.log),
               "prompt_tokens": sum(r["prompt_tokens"] for r in scorer.log),
               "completion_tokens": sum(r["completion_tokens"] for r in scorer.log),
               "seconds": round(time.perf_counter() - t0, 1)}
        return {"qualitative": qualitative, "score_samples": samples, "score_noise": noise,
                "agent_runs": {**state.get("agent_runs", {}), criterion: run}}
    agent.__name__ = f"agent_{criterion}"
    return agent


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
    if not state.get("qualitative"):
        return {"overrides": []}
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


def score_cells(state: PipelineState) -> dict[tuple[int, int], list[int]]:
    """K samples per LLM-scored cell of X, keyed (row, column); human-overridden cells are left out (held fixed)."""
    over = {(o.company, o.criterion) for o in state.get("overrides", [])}
    cs, cr = state["companies"], state["criteria"]
    out = {}
    for key, vals in state.get("score_samples", {}).items():
        company, criterion = key.split("|", 1)
        if (company, criterion) not in over:
            out[(cs.index(company), cr.index(criterion))] = vals
    return out


def robustness(state: PipelineState) -> dict:
    """Rank intervals under bootstrap and Dirichlet weight perturbation, and under LLM score noise."""
    settings = _settings(state)
    res = robust_ranking(
        np.array(state["matrix"]), WEIGHT_FNS[settings["weighting"]], topsis,
        n_draws=settings["n_draws"], concentration=settings["concentration"], seed=settings["seed"],
        cell_samples=score_cells(state),
    )
    fields = ("point", "median", "lo", "hi", "acceptability")
    return {"robustness": {src: {f: getattr(r, f).tolist() for f in fields} | {"n_draws": r.n_draws}
                           for src, r in res.items()}}


def report(state: PipelineState) -> dict:
    """Markdown report built from state only."""
    cs, st, rb = state["companies"], state["settings"], state["robustness"]
    top, sw = state["scores"]["topsis"], state["scores"]["saw"]
    bo, di, sn = rb["bootstrap"], rb["dirichlet"], rb["score_noise"]
    tau = state["method_agreement"]["kendall_tau_topsis_saw"]
    sec, tickers = st["source"] == "sec", state.get("tickers") or {}
    llm = st["scorer"] == "llm"
    head = ([f"# MAID report: real data ({st['sector']}, quantitative + local LLM scores)", "",
             f"> **Real data**: SEC XBRL and 10-K text, point-in-time on {get_settings().decision_date}; LLM scores from a "
             "local model, agents run one after another (D21). Local only: do not commit.", ""] if llm else
            [f"# MAID report: real data ({st['sector']}, quantitative only)", "",
             f"> **Real data**: SEC XBRL, point-in-time on the decision date {get_settings().decision_date}; "
             "4 quantitative criteria, no LLM scores. Local only: do not commit.", ""] if sec else
            ["# MAID demo report", "",
             "> **Synthetic demo data**: invented companies, not real ones. Decision date 2025-03-31.", ""])
    lines = [
        *head,
        f"Settings: source={st['source']}, weighting={st['weighting']}, k={st['k']}, seed={st['seed']}, "
        f"n_draws={st['n_draws']}, concentration={st['concentration']}"
        + (f", scorer={st['scorer']}, limit={st['limit']}" if llm else ""), "",
        "## Ranking (by TOPSIS)", "",
        "| Rank | Company | TOPSIS | SAW | Bootstrap 90% rank | Dirichlet 90% rank | Score-noise 90% rank | P(rank 1) Dirichlet |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r, c in enumerate(state["ranking"], 1):
        i = cs.index(c)
        name = f"{c} ({tickers[c]})" if tickers else c
        lines.append(f"| {r} | {name} | {top[i]:.3f} | {sw[i]:.3f} | {bo['lo'][i]:.0f}-{bo['hi'][i]:.0f} | "
                     f"{di['lo'][i]:.0f}-{di['hi'][i]:.0f} | {sn['lo'][i]:.0f}-{sn['hi'][i]:.0f} | {di['acceptability'][i][0]:.2f} |")
    lines += ["", "Score-noise intervals re-draw each LLM score from its K samples (median of a resample) and "
              "recompute weights; human-overridden scores are held fixed, and with k=1 the interval has zero width."]
    if sec and not llm:
        lines += ["", "No LLM scores in this run, so score-noise intervals have zero width."]
    lines += ["", "## Weights", "", "| Criterion | Weight |", "|---|---|"]
    lines += [f"| {k} | {v:.3f} |" for k, v in state["weights"].items()]
    lines += ["", f"Method agreement (Kendall tau, TOPSIS vs SAW): {tau:.3f}", "", "## Human overrides", ""]
    lines += [f"- {o.company} / {o.criterion} -> {o.score}: {o.reason}" for o in state.get("overrides", [])] or ["none"]
    if llm:
        lines += ["", "## Agents (sequential jobs, D21)", "",
                  "| Agent | Model | Prompt version | Calls | Failed attempts | Prompt tokens | Minutes |",
                  "|---|---|---|---|---|---|---|"]
        for k in LLM_CRITERIA:
            a = state["agent_runs"][k]
            lines.append(f"| {k} | {', '.join(a['model'])} | {a['prompt_version']} | {a['calls']} | {a['failed_attempts']} | "
                         f"{a['prompt_tokens']} | {a['seconds'] / 60:.1f} |")
    lines += ["", "LLMs never rank: scores come from local LLM agents run one after another (D21); ranks come from the MCDM engine."
              if llm else
              "LLMs never rank: this run has no LLM scores; ranks come from the MCDM engine." if sec else
              "LLMs never rank: scores come from the (stub) scorer, ranks from the MCDM engine.", ""]
    return {"report": "\n".join(lines)}


def build_graph():
    g = StateGraph(PipelineState)
    agents = [f"agent_{k}" for k in LLM_CRITERIA]
    order = ["ingest", "score_qualitative", *agents, "human_review", "mcdm", "robustness", "report"]
    fns = {"ingest": ingest, "score_qualitative": score_qualitative, "human_review": human_review, "mcdm": mcdm,
           "robustness": robustness, "report": report}
    for k in LLM_CRITERIA:
        fns[f"agent_{k}"] = make_agent(k)
    for name in order:
        g.add_node(name, fns[name])
    for a, b in zip([START, *order], [*order, END], strict=True):
        g.add_edge(a, b)
    serde = JsonPlusSerializer(allowed_msgpack_modules=CHECKPOINT_TYPES)
    return g.compile(checkpointer=MemorySaver(serde=serde))
