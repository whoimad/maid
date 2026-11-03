"""Real-data path: anonymization, SEC criteria, graph with source="sec" (no network)."""
import copy
import json
import urllib.request
from pathlib import Path

import pytest

from maid import graph
from maid.demo import run_demo
from maid.graph import build_graph, validate_settings
from maid.real_data import SECTORS, anonymize, read_universe, sec_quantitative
from maid.xbrl import STAPLES_CRITERIA, TECH_CRITERIA

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
    monkeypatch.setattr(graph, "load_sec", lambda d, sector="tech": sec_quantitative(ROWS, fake_facts, d, sector))


def test_anonymize_sorts_by_ticker():
    assert anonymize(["MSFT", "AAPL"]) == {"Company 001": "AAPL", "Company 002": "MSFT"}
    with pytest.raises(ValueError):
        anonymize(["AAPL", "AAPL"])


def test_sec_quantitative_labels_and_values():
    labels, quant, meta = sec_quantitative(ROWS, fake_facts, "2025-03-31")
    assert labels == {"Company 001": "AAPL", "Company 002": "MSFT", "Company 003": "NVDA"}
    assert all(set(q) == set(TECH_CRITERIA) for q in quant.values())
    assert meta["Company 001"]["filed"] <= "2025-03-31"


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
    assert "Real data" in s["report"] and "Company 001 (AAPL)" in s["report"]
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


def test_anonymize_numeric_many():
    tickers = [f"T{i:02d}" for i in range(30)][::-1]
    labels = anonymize(tickers)
    assert list(labels) == [f"Company {i:03d}" for i in range(1, 31)]
    assert list(labels.values()) == sorted(tickers)


def _facts_with_assets(cik):
    f = fake_facts(cik)
    row = {"end": "2024-12-31", "val": 4000, "accn": "A-2025", "form": "10-K", "filed": "2025-02-10"}
    f["facts"]["us-gaap"]["Assets"] = {"units": {"USD": [row]}}
    return f


def test_sec_quantitative_staples():
    _, quant, _ = sec_quantitative(ROWS, _facts_with_assets, "2025-03-31", "staples")
    assert all(set(q) == set(STAPLES_CRITERIA) for q in quant.values())


def test_graph_sec_staples(monkeypatch):
    monkeypatch.setattr(graph, "load_sec", lambda d, sector="tech": sec_quantitative(ROWS, _facts_with_assets, d, sector))
    s = run_demo({"source": "sec", "sector": "staples", "n_draws": 20})
    assert s["criteria"] == STAPLES_CRITERIA and "staples" in s["report"]


def test_unknown_sector_rejected():
    with pytest.raises(ValueError, match="sector"):
        validate_settings({"sector": "banks"})


def test_read_staples_universe_real_file():
    rows = read_universe(SECTORS["staples"][0])
    assert len(rows) == 61 and len({r["ticker"] for r in rows}) == 61
    assert all(r["decision_date"] == "2025-03-31" for r in rows)


def test_load_filings_anonymizes(monkeypatch):
    from maid import real_data

    html = (Path(__file__).parent / "fixtures/tenk/mini_10k.htm").read_text()
    rows = [{"ticker": "ACME", "cik": "5", "decision_date": "2025-03-31"},
            {"ticker": "ZZZZ", "cik": "6", "decision_date": "2025-03-31"}]
    labels = anonymize(["ACME", "ZZZZ"])
    meta = {lab: {"accn": f"A-{lab[-1]}"} for lab in labels}

    class Client:
        def submissions(self, cik):
            return {"name": "ACME FOODS, Inc.", "formerNames": [], "filings": {"recent": {
                "accessionNumber": ["A-1", "A-2"], "primaryDocument": ["a.htm", "a.htm"]}}}

        def filing_html(self, cik, accn):
            return html

        def filing_documents(self, cik, accn):
            return []

    monkeypatch.setattr(real_data, "load_sec", lambda d, sector="tech", client=None: (labels, {}, meta))
    monkeypatch.setattr(real_data, "read_universe", lambda path=None: rows)
    got_labels, texts, info = real_data.load_filings("2025-03-31", "tech", Client())
    assert got_labels == labels
    assert "Company 001 sells cereal" in texts["Company 001"]["1"]
    assert "ACME" not in texts["Company 001"]["1"]
    assert info["Company 001"]["replacements"] > 0 and info["Company 001"]["accn"] == "A-1"


def test_company_filing_mdna_by_reference():
    from maid import real_data

    fx = Path(__file__).parent / "fixtures/tenk"
    docs = {"byref_10k.htm": (fx / "byref_10k.htm").read_text(), "byref_d2.htm": (fx / "byref_d2.htm").read_text()}

    class Client:
        def submissions(self, cik):
            return {"name": "BLEACHCO CO /DE/", "formerNames": [], "filings": {"recent": {
                "accessionNumber": ["B-1"], "primaryDocument": ["byref_10k.htm"]}}}

        def filing_html(self, cik, accn):
            return docs["byref_10k.htm"]

        def filing_documents(self, cik, accn):
            return [{"name": "byref_10k.htm", "size": 9}, {"name": "R2.htm", "size": 99},
                    {"name": "byref_d2.htm", "size": 5}]

        def document_html(self, cik, accn, name):
            assert name == "byref_d2.htm"
            return docs[name]

    out, info = real_data.company_filing(Client(), 5, "B-1", "BLCH", "Company 001")
    assert info["mdna_source"] == "exhibit:byref_d2.htm"
    assert len(out["7"].split()) >= 1000
    assert out["1a"] and "Resin costs" in out["1a"]
    assert "BleachCo" not in out["1"] and info["residual"] == 0


def test_read_aliases_real_file():
    from maid.real_data import read_aliases

    a = read_aliases()
    assert a["PG"] == ["P&G", "Procter & Gamble"] and a["EL"] == ["Estée Lauder", "Lauder"] and len(a) == 16


# --- LLM criterion agents (plan 033) ---
from types import SimpleNamespace as NS  # noqa: E402

from maid.graph import LLM_CRITERIA  # noqa: E402
from maid.rubrics import RUBRICS  # noqa: E402

LABELS = {"Company 001": "AAPL", "Company 002": "MSFT", "Company 003": "NVDA"}
MDNA = ("We raised prices 4% in fiscal 2024 and volume held steady. "
        "We repurchased shares worth 500 million and paid dividends. " * 3)
QUOTES = {"strategy_clarity": "We aim to grow margins 2% by 2026.", "pricing_power": "We raised prices 4% in fiscal 2024",
          "capital_allocation": "We repurchased shares worth 500 million"}


class AgentClient:
    """Replies with a quote from the slice the criterion reads (found via the rubric in the system message)."""

    def __init__(self, empty=False):
        self.calls, self.empty = [], empty
        self.chat = NS(completions=NS(create=self.create))

    def create(self, **kw):
        assert not self.empty, "unexpected LLM call"
        self.calls.append(kw)
        sys_msg, user = kw["messages"][0]["content"], kw["messages"][1]["content"]
        crit = next(c for c in RUBRICS if RUBRICS[c] in sys_msg)
        score = 3 + len(self.calls) % 5
        body = json.dumps({"score": score, "evidence": QUOTES[crit], "reasoning": "r"})
        return NS(choices=[NS(message=NS(content=body))], model="fake-1",
                  usage=NS(prompt_tokens=(len(sys_msg) + len(user)) // 4, completion_tokens=20))


def _llm_patch(monkeypatch, tmp_path, client):
    monkeypatch.setenv("MAID_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(graph, "load_sec", lambda d, sector="tech": sec_quantitative(ROWS, _facts_with_assets, d, sector))
    texts = {c: {"1": QUOTES["strategy_clarity"] + " Our products are sold worldwide.", "1a": "", "7": MDNA} for c in LABELS}
    monkeypatch.setattr(graph, "load_filings", lambda d, sector="tech": (LABELS, texts, {}))
    monkeypatch.setattr(graph, "make_client", lambda cfg: client)


LLM = {"source": "sec", "sector": "staples", "scorer": "llm", "k": 2, "n_draws": 20}


def test_scorer_validation():
    for bad in ({"scorer": "llm"}, {"scorer": "llm", "source": "sec", "sector": "tech"}, {"scorer": "gpt"}, {"limit": -1}):
        with pytest.raises(ValueError):
            validate_settings(bad)
    assert validate_settings(LLM)["limit"] == 0


def test_graph_has_agent_nodes_in_order():
    order = list(build_graph().get_graph().nodes)
    got = [n for n in order if n.startswith("agent_")]
    assert got == [f"agent_{k}" for k in LLM_CRITERIA]
    assert order.index("score_qualitative") < order.index(got[0]) and order.index(got[-1]) < order.index("human_review")


def test_agents_run_sequentially_and_report(monkeypatch, tmp_path):
    fc = AgentClient()
    _llm_patch(monkeypatch, tmp_path, fc)
    g, cfg = build_graph(), {"configurable": {"thread_id": "t"}}
    assert "__interrupt__" in g.invoke({"settings": LLM}, cfg)
    crits = [next(c for c in RUBRICS if RUBRICS[c] in kw["messages"][0]["content"]) for kw in fc.calls]
    assert crits == [c for c in LLM_CRITERIA for _ in range(6)]
    s = run_demo(LLM, thread_id="t2")
    assert len(s["qualitative"]) == 9 and s["criteria"] == STAPLES_CRITERIA + LLM_CRITERIA
    assert list(s["agent_runs"]) == LLM_CRITERIA
    assert "## Agents (sequential jobs, D21)" in s["report"] and "run one after another" in s["report"]
    assert "scorer=llm, limit=0" in s["report"] and "No LLM scores" not in s["report"]


def test_resume_from_cache(monkeypatch, tmp_path):
    _llm_patch(monkeypatch, tmp_path, AgentClient())
    first = run_demo(LLM)
    monkeypatch.setattr(graph, "make_client", lambda cfg: AgentClient(empty=True))
    second = run_demo(LLM, thread_id="again")
    assert second["ranking"] == first["ranking"] and second["agent_runs"]["pricing_power"]["calls"] == 6


def test_limit_two(monkeypatch, tmp_path):
    _llm_patch(monkeypatch, tmp_path, AgentClient())
    s = run_demo({**LLM, "limit": 2})
    assert s["companies"] == ["Company 001", "Company 002"] and len(s["qualitative"]) == 6


def test_no_ticker_in_prompts(monkeypatch, tmp_path):
    fc = AgentClient()
    _llm_patch(monkeypatch, tmp_path, fc)
    run_demo(LLM)
    assert fc.calls and not any(t in m["content"] for kw in fc.calls for m in kw["messages"] for t in LABELS.values())


def test_demo_unchanged_by_agents():
    s = run_demo({"n_draws": 50})
    assert "## Agents" not in s["report"] and not s.get("agent_runs")
