"""Tests for the pure GUI data helpers (no streamlit)."""
import numpy as np
import pytest

from maid.demo import run_demo
from maid.graph import build_graph
from maid.gui_data import (
    acceptability_rows,
    interval_rows,
    matrix_rows,
    pipeline_dot,
    ranking_rows,
    score_rows,
    weight_rows,
)

OVERRIDE = {"company": "Company A", "criterion": "strategy_clarity", "score": 9, "reason": "test"}


@pytest.fixture(scope="module")
def state():
    return run_demo({"n_draws": 100}, [OVERRIDE])


def test_pipeline_dot_has_nodes_and_direction():
    dot = pipeline_dot()
    assert "rankdir=LR" in dot
    for n in build_graph().get_graph().nodes:
        assert n in dot
    assert pipeline_dot({"mcdm": "stub"}) != dot


def test_matrix_rows(state):
    rows = matrix_rows(state)
    assert len(rows) == 10 and set(rows[0]) == {"company", *state["criteria"]}


def test_score_rows_flags_override(state):
    rows = score_rows(state)
    assert len(rows) == 20
    hit = [r for r in rows if r["overridden"]]
    assert len(hit) == 1 and hit[0]["company"] == "Company A" and hit[0]["criterion"] == "strategy_clarity"
    assert isinstance(rows[0]["samples"], str) and rows[0]["evidence"]


def test_weight_rows_sum_to_one(state):
    rows = weight_rows(state)
    for m in ("entropy", "critic", "equal"):
        assert abs(sum(r["weight"] for r in rows if r["method"] == m) - 1) < 1e-9
    assert {r["method"] for r in rows if r["used"]} == {state["settings"]["weighting"]}


def test_ranking_rows(state):
    rows = ranking_rows(state)
    assert [r["company"] for r in rows] == state["ranking"]
    assert [r["rank"] for r in rows] == list(range(1, 11))
    assert sorted(r["saw_rank"] for r in rows) == list(range(1, 11))


def test_interval_rows_sorted(state):
    for src in ("bootstrap", "dirichlet"):
        rows = interval_rows(state, src)
        pts = [r["point"] for r in rows]
        assert pts == sorted(pts) and all(r["lo"] <= r["hi"] for r in rows)


def test_acceptability_rows(state):
    rows = acceptability_rows(state, "dirichlet")
    assert all(r["share"] > 0 for r in rows)
    assert abs(sum(r["share"] for r in rows if r["company"] == "Company A") - 1) < 1e-9
    assert np.isclose(sum(r["share"] for r in rows), 10)
