"""Tests for the synthetic demo pipeline: dataset, stub scorer, matrix helpers, end-to-end run."""
import numpy as np
import pytest

from maid import scoring
from maid.demo import run_demo
from maid.demo_data import QUAL_CRITERIA, QUANT_CRITERIA, demo_dataset
from maid.matrix import apply_overrides, build_matrix
from maid.scoring import StubScorer, aggregate, evidence_is_quoted
from maid.state import CriterionScore, ScoreOverride


def test_demo_dataset_is_deterministic_and_anonymized():
    a, b = demo_dataset(seed=0), demo_dataset(seed=0)
    assert a == b
    assert a.companies == [f"Company {c}" for c in "ABCDEFGHIJ"]
    assert not any(c in text for c in a.companies for text in a.filings.values())


def test_stub_scorer_is_reproducible_and_quotes_evidence():
    ds = demo_dataset(seed=0)
    c, crit = ds.companies[0], QUAL_CRITERIA[0]
    s = StubScorer(ds.latent, noise=1.0, seed=3)
    first = s.score(c, crit, ds.filings[c], 5)
    assert first == StubScorer(ds.latent, noise=1.0, seed=3).score(c, crit, ds.filings[c], 5)
    assert all(1 <= x.score <= 9 and evidence_is_quoted(x, ds.filings[c]) for x in first)
    exact = StubScorer(ds.latent, noise=0.0).score(c, crit, ds.filings[c], 4)
    assert {x.score for x in exact} == {ds.latent[c][crit]}


def test_aggregate_takes_median():
    samples = [CriterionScore(company="Company A", criterion="x", score=v, evidence="e") for v in (3, 5, 9)]
    score, std = aggregate(samples)
    assert score.score == 5
    assert std > 0


def test_apply_overrides_replaces_score_and_keeps_reason():
    orig = [CriterionScore(company="Company A", criterion="x", score=3, evidence="quote")]
    out = apply_overrides(orig, [ScoreOverride(company="Company A", criterion="x", score=8, reason="because")])
    assert out[0].score == 8 and "because" in out[0].evidence and "quote" in out[0].evidence
    assert orig[0].score == 3 and orig[0].evidence == "quote"


def test_build_matrix_shape_and_missing_cell():
    ds = demo_dataset(seed=0)
    qual = [CriterionScore(company=c, criterion=k, score=5, evidence="e") for c in ds.companies for k in QUAL_CRITERIA]
    criteria = QUANT_CRITERIA + QUAL_CRITERIA
    X = build_matrix(ds.companies, ds.quantitative, qual, criteria)
    assert X.shape == (10, 6)
    del ds.quantitative["Company C"][QUANT_CRITERIA[0]]
    with pytest.raises(ValueError):
        build_matrix(ds.companies, ds.quantitative, qual, criteria)


def test_run_demo_end_to_end():
    s = run_demo()
    assert len(set(s["ranking"])) == 10
    assert abs(sum(s["weights"].values()) - 1) < 1e-9
    for src in ("bootstrap", "dirichlet"):
        r = s["robustness"][src]
        assert all(lo <= hi for lo, hi in zip(r["lo"], r["hi"], strict=True))
    assert "Synthetic demo data" in s["report"]


def test_override_changes_matrix():
    ov = {"company": "Company A", "criterion": "strategy_clarity", "score": 9, "reason": "test reason"}
    s = run_demo(overrides=[ov])
    i, j = s["companies"].index("Company A"), s["criteria"].index("strategy_clarity")
    assert s["matrix"][i][j] == 9.0
    assert "test reason" in s["report"]


def test_weighting_choice_is_respected():
    w = run_demo({"weighting": "equal"})["weights"]
    assert np.allclose(list(w.values()), 1 / 6)
    with pytest.raises(ValueError):
        run_demo({"weighting": "nope"})


def test_llm_never_ranks():
    assert [n for n in dir(scoring) if "rank" in n.lower()] == []
