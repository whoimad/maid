"""Shared graph state. LLM-produced values always carry evidence; MCDM is deterministic."""
from typing import TypedDict

from pydantic import BaseModel, Field


class CriterionScore(BaseModel):
    company: str  # anonymized label, e.g. "Company A"
    criterion: str
    score: int = Field(ge=1, le=9)
    evidence: str  # quote that must appear in the source filing


class ScoreOverride(BaseModel):
    """A human correction of one LLM score; the reason is mandatory so disagreements can be analyzed later."""
    company: str
    criterion: str
    score: int = Field(ge=1, le=9)
    reason: str = Field(min_length=1)


class PipelineState(TypedDict, total=False):
    companies: list[str]
    quantitative: dict[str, dict[str, float]]  # company -> criterion -> value
    qualitative: list[CriterionScore]
    overrides: list[ScoreOverride]
    weights: dict[str, float]
    ranking: list[str]
    report: str
    criteria: list[str]  # column order of X
    filings: dict[str, str]
    tickers: dict[str, str]  # label -> ticker for source="sec"; local only, never put into prompts
    score_samples: dict[str, list[int]]  # "company|criterion" -> K sampled scores
    score_noise: dict[str, float]  # "company|criterion" -> std of the K samples
    settings: dict  # {"source", "k", "weighting", "seed", "n_draws", "concentration"}
    matrix: list[list[float]]  # X after overrides
    scores: dict[str, list[float]]  # {"topsis": [...], "saw": [...]} in `companies` order
    method_agreement: dict[str, float]  # {"kendall_tau_topsis_saw": ...}
    robustness: dict  # {"bootstrap": {...}, "dirichlet": {...}, "score_noise": {...}} with lists


# Pydantic types stored in graph state; checkpoints must be allowed to restore them.
CHECKPOINT_TYPES = [("maid.state", "CriterionScore"), ("maid.state", "ScoreOverride")]
