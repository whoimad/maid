"""Stub qualitative scorer: a deterministic stand-in for the LLM scorer. It scores; it never ranks."""
import zlib

import numpy as np

from maid.demo_data import template_sentence
from maid.state import CriterionScore


class StubScorer:
    """Deterministic stand-in for the LLM scorer: latent score + seeded noise, evidence quoted from the filing."""

    def __init__(self, latent: dict[str, dict[str, int]], noise: float = 1.0, seed: int = 0):
        self.latent, self.noise, self.seed = latent, noise, seed

    def score(self, company: str, criterion: str, filing: str, k: int) -> list[CriterionScore]:
        """Return k noisy samples for one company and criterion."""
        base = self.latent[company][criterion]
        evidence = template_sentence(criterion, base)
        tag = zlib.crc32(f"{company}|{criterion}".encode())
        out = []
        for i in range(k):
            rng = np.random.default_rng([self.seed, i, tag])
            s = int(np.clip(round(base + rng.normal(0, self.noise)), 1, 9))
            out.append(CriterionScore(company=company, criterion=criterion, score=s, evidence=evidence))
        return out


def aggregate(samples: list[CriterionScore]) -> tuple[CriterionScore, float]:
    """Median score (half rounds up) with the first sample's evidence, plus the sample std as noise."""
    vals = np.array([s.score for s in samples], dtype=float)
    med = int(np.floor(np.median(vals) + 0.5))
    return samples[0].model_copy(update={"score": med}), float(vals.std())


def evidence_is_quoted(score: CriterionScore, filing: str) -> bool:
    """Programmatic citation check: the evidence must appear verbatim in the filing."""
    return score.evidence in filing
