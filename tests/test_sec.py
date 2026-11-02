"""SEC client: caching, User-Agent guard, ticker lookup (no network)."""
import urllib.request

import pytest

from maid.cache import DiskCache
from maid.sec import SecClient, _get_json, ticker_to_cik


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("network in tests")

    monkeypatch.setattr(urllib.request, "urlopen", boom)


def test_companyfacts_cached(tmp_path):
    calls = []

    def fake(url, ua):
        calls.append(url)
        return {"ok": 1}

    c = SecClient(cache=DiskCache(tmp_path), user_agent="t t@example.com", fetch=fake)
    assert c.companyfacts(320193) == {"ok": 1}
    assert c.companyfacts(320193) == {"ok": 1}
    assert len(calls) == 1
    assert "CIK0000320193" in calls[0]


def test_user_agent_required():
    with pytest.raises(ValueError, match="SEC_USER_AGENT"):
        _get_json("https://example.invalid", "  ")


def test_ticker_to_cik():
    tj = {"fields": ["cik", "name", "ticker", "exchange"], "data": [[320193, "Apple Inc.", "AAPL", "Nasdaq"]]}
    assert ticker_to_cik(tj, "aapl") == 320193
    with pytest.raises(ValueError):
        ticker_to_cik(tj, "ZZZZ")
