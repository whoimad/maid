"""Pure helpers between scores and the decision matrix X."""
import numpy as np
from scipy.stats import kendalltau

from maid.state import CriterionScore, ScoreOverride


def apply_overrides(scores: list[CriterionScore], overrides: list[ScoreOverride]) -> list[CriterionScore]:
    """Return new scores with human overrides applied; the reason is appended to the evidence."""
    by_key = {(o.company, o.criterion): o for o in overrides}
    out = []
    for s in scores:
        o = by_key.get((s.company, s.criterion))
        out.append(s if o is None else s.model_copy(
            update={"score": o.score, "evidence": f"{s.evidence} [human override: {o.reason}]"}))
    return out


def build_matrix(companies, quantitative, qualitative, criteria) -> np.ndarray:
    """Decision matrix X (n companies, m criteria); raises ValueError naming a missing cell."""
    qual = {(s.company, s.criterion): float(s.score) for s in qualitative}
    X = np.empty((len(companies), len(criteria)))
    for i, c in enumerate(companies):
        for j, k in enumerate(criteria):
            v = quantitative.get(c, {}).get(k, qual.get((c, k)))
            if v is None:
                raise ValueError(f"missing value for ({c}, {k})")
            X[i, j] = v
    return X


def kendall_tau(a_scores, b_scores) -> float:
    """Kendall rank correlation between two score vectors."""
    return float(kendalltau(a_scores, b_scores)[0])
