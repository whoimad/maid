"""Shared graph state. LLM-produced values always carry evidence; MCDM is deterministic."""
from typing import TypedDict

from pydantic import BaseModel, Field


class CriterionScore(BaseModel):
    company: str  # anonymized label, e.g. "Company A"
    criterion: str
    score: int = Field(ge=1, le=9)
    evidence: str  # quote that must appear in the source filing


class PipelineState(TypedDict, total=False):
    companies: list[str]
    quantitative: dict[str, dict[str, float]]  # company -> criterion -> value
    qualitative: list[CriterionScore]
    weights: dict[str, float]
    ranking: list[str]
    report: str
