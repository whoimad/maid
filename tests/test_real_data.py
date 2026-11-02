"""Real-data path: anonymization, SEC criteria, graph with source="sec" (no network)."""
import copy
import json
import urllib.request
from pathlib import Path

import pytest

from maid import graph
from maid.demo import run_demo
from maid.graph import build_graph, validate_settings
from maid.real_data import anonymize, read_universe, sec_quantitative
from maid.xbrl import TECH_CRITERIA

F = json.loads((Path(__file__).parent / "fixtures/sec/companyfacts_example.json").read_text())


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("network in tests")

    monkeypatch.setattr(urllib.request, "urlopen", boom)


def fake_facts(cik):
    """The example fixture with per-company scaled values, so the matrix columns are not all constant."""
    f = copy.deepcopy(F)
    g = f["facts"]["us-gaap"]
    for tag, mult in [("NetIncomeLoss", 1 + 0.2 * cik), ("ResearchAndDevelopmentExpense", 1 + 0.1 * cik),
                      ("NetCashProvidedByUsedInOperatingActivities", 1 + 0.15 * cik)]:
        for x in g[tag]["units"]["USD"]:
            x["val"] *= mult
    for x in g["RevenueFromContractWithCustomerExcludingAssessedTax"]["units"]["USD"]:
        if x["end"] < "2024-06-30":
            x["val"] *= 1 - 0.05 * cik
    return f


ROWS = [{"ticker": t, "cik": str(i), "decision_date": "2025-03-31"} for i, t in [(1, "MSFT"), (2, "AAPL"), (3, "NVDA")]]


def _patch(monkeypatch):
    monkeypatch.setattr(graph, "load_sec", lambda d: sec_quantitative(ROWS, fake_facts, d))


def test_anonymize_sorts_by_ticker():
    assert anonymize(["MSFT", "AAPL"]) == {"Company A": "AAPL", "Company B": "MSFT"}
    with pytest.raises(ValueError):
        anonymize(["AAPL", "AAPL"])


def test_sec_quantitative_labels_and_values():
    labels, quant, meta = sec_quantitative(ROWS, fake_facts, "2025-03-31")
    assert labels == {"Company A": "AAPL", "Company B": "MSFT", "Company C": "NVDA"}
    assert all(set(q) == set(TECH_CRITERIA) for q in quant.values())
    assert meta["Company A"]["filed"] <= "2025-03-31"


def test_sec_quantitative_rejects_other_decision_date():
    rows = [{**ROWS[0], "decision_date": "2024-12-31"}]
    with pytest.raises(ValueError, match="decision date"):
        sec_quantitative(rows, fake_facts, "2025-03-31")


def test_read_universe_real_file():
    rows = read_universe()
    assert len(rows) == 15 and len({r["ticker"] for r in rows}) == 15
    assert all(r["decision_date"] == "2025-03-31" for r in rows)


def test_graph_sec_source_quant_only(monkeypatch):
    _patch(monkeypatch)
    s = run_demo({"source": "sec", "n_draws": 50})
    assert s["criteria"] == TECH_CRITERIA and s["qualitative"] == [] and s["overrides"] == []
    assert len(s["ranking"]) == 3 and set(s["tickers"].values()) == {"AAPL", "MSFT", "NVDA"}
    assert "Real data" in s["report"] and "Company A (AAPL)" in s["report"]
    sn = s["robustness"]["score_noise"]
    assert all(lo == hi for lo, hi in zip(sn["lo"], sn["hi"], strict=True))


def test_graph_sec_runs_without_interrupt(monkeypatch):
    _patch(monkeypatch)
    r = build_graph().invoke({"settings": {"source": "sec", "n_draws": 20}}, {"configurable": {"thread_id": "t"}})
    assert "__interrupt__" not in r and "report" in r


def test_unknown_source_rejected():
    with pytest.raises(ValueError, match="source"):
        validate_settings({"source": "banks"})


def test_no_ticker_in_scores_or_criteria(monkeypatch):
    _patch(monkeypatch)
    s = run_demo({"source": "sec", "n_draws": 20})
    tickers = set(s["tickers"].values())
    text = " ".join(s["criteria"] + s["companies"] + list(s["filings"].values()))
    assert not any(t in text for t in tickers)
