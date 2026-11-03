"""Scoring prompts: one rubric per qualitative criterion (1-9, quoted evidence). Bump PROMPT_VERSION on any change."""

PROMPT_VERSION = "1"
SYSTEM = (
    "You are a careful equity analyst. The company is anonymized as {label}; other names may also be replaced. "
    "Use only the excerpt below, never outside knowledge, and do not try to identify the company. "
    "Score one criterion as an integer from 1 to 9 using the rubric. Quote, word for word, one passage of at most "
    "300 characters from the excerpt that best supports the score. "
    'Answer with a json object only: {{"score": <1-9>, "evidence": "<verbatim quote>", '
    '"reasoning": "<at most 60 words>"}}.'
)
RUBRICS = {
    "pricing_power": (
        "Pricing power: can the company raise prices or improve mix without losing volume, and pass cost inflation "
        "through? 1-3: price cuts or heavy promotion to defend volume, input costs not passed through, share lost to "
        "private label or competitors. 4-6: mixed; some pricing gains offset by volume declines or margin pressure. "
        "7-9: price/mix gains with stable or growing volume, costs explicitly passed through, margins held or expanded."
    ),
    "strategy_clarity": (
        "Strategy clarity: does management state specific priorities and how it will reach them? 1-3: boilerplate, no "
        "identifiable priorities. 4-6: priorities named but vague, no targets or timeframes. 7-9: specific priorities "
        "with measurable targets and timeframes, tied to resources or investments."
    ),
    "capital_allocation": (
        "Capital allocation: is there a clear, disciplined policy for using cash? 1-3: no stated policy, a dividend "
        "cut, or acquisitions with no stated criteria. 4-6: a policy is described but without order or targets. 7-9: "
        "explicit ordered priorities (for example reinvestment, dividend, buybacks, M&A), a leverage target, return "
        "criteria, and a consistent record."
    ),
}


def build_messages(criterion: str, label: str, text: str) -> list[dict]:
    """Chat messages for one score: system prompt with the rubric, then the excerpt."""
    if criterion not in RUBRICS:
        raise ValueError(f"unknown criterion: {criterion!r}")
    system = SYSTEM.format(label=label) + "\n\nRubric. " + RUBRICS[criterion]
    user = f"Excerpt from the 10-K of {label}:\n\n{text}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
