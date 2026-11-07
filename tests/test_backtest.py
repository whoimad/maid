"""Tests for the backtest (offline)."""
import inspect
import urllib.request

import pytest

import maid.graph
from maid import graph
from maid.backtest import WINDOW, backtest, rank_vs_return, window_return
from maid.prices import total_return

TECH_CRITERIA = ["revenue_growth", "net_margin", "fcf_margin", "rd_intensity"]


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("network in tests")

    monkeypatch.setattr(urllib.request, "urlopen", boom)


def _fake(decision_date=None, sector="tech"):
    labels = {"Company A": "AAA", "Company B": "BBB", "Company C": "CCC", "Company D": "DDD"}
    vals = [[0.30, 0.25, 0.30, 0.20], [0.10, 0.10, 0.12, 0.08], [0.20, 0.18, 0.20, 0.15], [0.05, 0.02, 0.05, 0.03]]
    quant = {c: dict(zip(TECH_CRITERIA, v, strict=True)) for c, v in zip(labels, vals, strict=True)}
    return labels, quant, {}


def test_perfect_agreement():
    r = rank_vs_return([1, 2, 3, 4, 5], [0.1, 0.2, 0.3, 0.4, 0.5])
    assert r["kendall_tau"] == pytest.approx(1)
    assert r["kendall_p"] == pytest.approx(1 / 60)
    assert r["spearman_rho"] == pytest.approx(1)


def test_reversed_is_negative():
    assert rank_vs_return([1, 2, 3, 4, 5], [0.5, 0.4, 0.3, 0.2, 0.1])["kendall_tau"] == pytest.approx(-1)


def test_known_swap():
    r = rank_vs_return([1, 2, 3, 4, 5], [1, 2, 3, 5, 4])
    assert r["kendall_tau"] == pytest.approx(0.8)
    assert r["kendall_p"] == pytest.approx(0.08333, abs=1e-4)


def test_bad_inputs_raise():
    with pytest.raises(ValueError):
        rank_vs_return([1, 2, 3], [1, 2])
    with pytest.raises(ValueError):
        rank_vs_return([1, 2], [1, 2])
    with pytest.raises(ValueError):
        rank_vs_return([1, 2, float("nan")], [1, 2, 3])


def test_backtest_runs_graph_with_given_returns(monkeypatch):
    monkeypatch.setattr(graph, "load_sec", _fake)
    returns = {"AAA": 0.4, "CCC": 0.3, "BBB": 0.2, "DDD": 0.1}
    res = backtest("equal", returns, n_draws=10)
    assert [r["ticker"] for r in res["rows"]] == ["AAA", "CCC", "BBB", "DDD"]
    assert res["kendall_tau"] == pytest.approx(1)
    assert res["n"] == 4


def test_backtest_missing_return_raises(monkeypatch):
    monkeypatch.setattr(graph, "load_sec", _fake)
    with pytest.raises(ValueError, match="DDD"):
        backtest("equal", {"AAA": 0.4, "CCC": 0.3, "BBB": 0.2}, n_draws=10)


def test_backtest_no_outcome_left_out(monkeypatch):
    monkeypatch.setattr(graph, "load_sec", _fake)
    res = backtest("equal", {"AAA": 0.4, "CCC": 0.3, "BBB": 0.2}, n_draws=10, no_outcome=["DDD"])
    assert res["n"] == 3
    assert "DDD" not in [r["ticker"] for r in res["rows"]]
    assert res["no_outcome"] == ["DDD"]
    assert res["kendall_tau"] == pytest.approx(1)


def test_backtest_no_outcome_unknown_raises(monkeypatch):
    monkeypatch.setattr(graph, "load_sec", _fake)
    with pytest.raises(ValueError, match="ZZZ"):
        backtest("equal", {"AAA": 0.4, "CCC": 0.3, "BBB": 0.2, "DDD": 0.1}, n_draws=10, no_outcome=["ZZZ"])


def test_backtest_no_outcome_with_return_raises(monkeypatch):
    monkeypatch.setattr(graph, "load_sec", _fake)
    with pytest.raises(ValueError, match="DDD"):
        backtest("equal", {"AAA": 0.4, "CCC": 0.3, "BBB": 0.2, "DDD": 0.1}, n_draws=10, no_outcome=["DDD"])


def test_graph_never_reads_prices():
    src = inspect.getsource(maid.graph)
    assert "maid.prices" not in src
    assert "fetch_series" not in src


def test_window_return_normal():
    adj = {"2025-03-31": 100.0, "2026-03-31": 120.0}
    w = window_return(adj, *WINDOW)
    assert w == {"return": pytest.approx(0.2), "last_day": "2026-03-31", "delisted": False}
    assert w["return"] == total_return(adj, *WINDOW)


def test_window_return_delisted():
    adj = {"2025-03-31": 100.0, "2025-12-10": 90.0, "2025-12-12": 95.0}
    w = window_return(adj, *WINDOW)
    assert w == {"return": pytest.approx(-0.05), "last_day": "2025-12-12", "delisted": True}


def test_window_return_no_data_raises():
    with pytest.raises(ValueError):
        window_return({"2025-03-31": 100.0}, *WINDOW)
