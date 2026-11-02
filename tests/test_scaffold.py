from langgraph.types import Command

from maid.cache import DiskCache
from maid.graph import build_graph


def test_cache_computes_once(tmp_path):
    cache = DiskCache(tmp_path)
    calls = []
    key = cache.key("a", 1)
    for _ in range(2):
        cache.get_or_compute(key, lambda: calls.append(1) or {"x": 1})
    assert len(calls) == 1


def test_graph_pauses_at_human_review_then_finishes():
    graph = build_graph()
    cfg = {"configurable": {"thread_id": "t1"}}
    result = graph.invoke({"companies": ["Company A"]}, cfg)
    assert "__interrupt__" in result
    final = graph.invoke(Command(resume="ok"), cfg)
    assert "report" in final
