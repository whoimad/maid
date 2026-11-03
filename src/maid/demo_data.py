"""Synthetic demo dataset: invented companies, not real ones; used for the demo and tests only."""
from dataclasses import dataclass

import numpy as np

QUANT_CRITERIA = ["revenue_growth", "net_margin", "fcf_margin", "rd_intensity"]  # all benefit-type
QUAL_CRITERIA = ["strategy_clarity", "risk_disclosure"]  # LLM-scored, 1-9

# criterion -> (low 1-3, mid 4-6, high 7-9) sentences
TEMPLATES = {
    "strategy_clarity": (
        "Management described its strategy only in general terms and gave no targets for 2025.",
        "Management listed several priorities for 2025 and reported partial progress on some of them.",
        "Management set out three measurable priorities for 2025 and reported progress against each one.",
    ),
    "risk_disclosure": (
        "The risk section lists generic risks and does not say how any of them would affect results.",
        "The risk section names the main risks and describes some mitigation steps.",
        "The risk section ranks each material risk, quantifies its exposure and names an owner for mitigation.",
    ),
}
FILLER = (
    "The company operates in several regional markets and employs staff in each of them.",
    "Financial statements were prepared in accordance with generally accepted accounting principles.",
)


@dataclass(frozen=True)
class DemoDataset:
    companies: list[str]
    quantitative: dict[str, dict[str, float]]  # company -> criterion -> value
    filings: dict[str, str]  # company -> synthetic 10-K excerpt
    latent: dict[str, dict[str, int]]  # company -> qual criterion -> hidden "true" score (stub scorer only)


def template_sentence(criterion: str, score: int) -> str:
    """The filing sentence written for a criterion at a latent score."""
    return TEMPLATES[criterion][0 if score <= 3 else 1 if score <= 6 else 2]


def demo_dataset(n: int = 10, seed: int = 0) -> DemoDataset:
    """Build n synthetic companies deterministically from the seed."""
    rng = np.random.default_rng(seed)
    companies = [f"Company {chr(65 + i)}" for i in range(n)]
    quant = {c: {} for c in companies}
    for crit, vals in [
        ("revenue_growth", rng.normal(0.10, 0.08, n)),
        ("net_margin", rng.normal(0.18, 0.08, n)),
        ("fcf_margin", rng.normal(0.15, 0.07, n)),
        ("rd_intensity", rng.uniform(0.03, 0.25, n)),
    ]:
        for c, v in zip(companies, vals, strict=True):
            quant[c][crit] = round(float(v), 3)
    latent = {c: {k: int(rng.integers(2, 9)) for k in QUAL_CRITERIA} for c in companies}
    filings = {
        c: " ".join([FILLER[0]] + [template_sentence(k, latent[c][k]) for k in QUAL_CRITERIA] + [FILLER[1]])
        for c in companies
    }
    return DemoDataset(companies, quant, filings, latent)
