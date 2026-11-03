"""SEC client: caching, User-Agent guard, ticker lookup (no network)."""
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from maid import sec
from maid.cache import DiskCache
from maid.sec import SecClient, _get_json, _get_text, ticker_to_cik


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


COVER = (Path(__file__).parent / "fixtures/sec/cover_two_classes.xml").read_text()


def _cover_client(tmp_path, names, urls, texts):
    def fj(url, ua):
        urls.append(url)
        return {"directory": {"item": [{"name": n} for n in names]}}

    def ft(url, ua):
        texts.append(url)
        return COVER

    return SecClient(cache=DiskCache(tmp_path), user_agent="t t@example.com", fetch=fj, fetch_text=ft)


def test_cover_cached(tmp_path):
    urls, texts = [], []
    c = _cover_client(tmp_path, ["a_htm.xml", "a_cal.xml"], urls, texts)
    r = c.cover(24545, "0000024545-25-000007")
    assert c.cover(24545, "0000024545-25-000007") == r
    assert len(texts) == 1 and texts[0].endswith("/a_htm.xml")
    assert r["accn"] == "0000024545-25-000007" and r["shares"] == 192721011.0
    assert "/Archives/edgar/data/24545/000002454525000007/index.json" in urls[0]


def test_cover_needs_single_instance(tmp_path):
    c = _cover_client(tmp_path, ["a_cal.xml"], [], [])
    with pytest.raises(ValueError, match="single inline XBRL"):
        c.cover(1, "0000000001-25-000001")


def test_get_text_user_agent_required():
    with pytest.raises(ValueError, match="SEC_USER_AGENT"):
        _get_text("https://example.invalid", "  ")


class _Resp:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return b'{"ok": 1}'


def test_rate_limit_shared_across_threads(no_network, monkeypatch):
    monkeypatch.setattr(sec, "MIN_INTERVAL", 0.02)
    sec._next[0] = 0.0
    starts, out = [], []

    def fake(req, timeout=0):
        starts.append(time.monotonic())
        return _Resp()

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    ts = [threading.Thread(target=lambda: [out.append(_get_json("http://x", "t t@e.com")) for _ in range(2)]) for _ in range(5)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert out == [{"ok": 1}] * 10
    starts.sort()
    assert all(b - a >= 0.018 for a, b in zip(starts, starts[1:], strict=False))


def test_retry_then_success(no_network, monkeypatch):
    calls = []

    def fake(req, timeout=0):
        calls.append(1)
        if len(calls) == 1:
            raise urllib.error.URLError("dns")
        return _Resp()

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    monkeypatch.setattr(time, "sleep", lambda s: None)
    assert _get_json("http://x", "t t@e.com") == {"ok": 1}
    assert len(calls) == 2


def test_404_not_retried(no_network, monkeypatch):
    calls = []

    def fake(req, timeout=0):
        calls.append(1)
        raise urllib.error.HTTPError("http://x", 404, "nf", None, None)

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    with pytest.raises(urllib.error.HTTPError):
        _get_json("http://x", "t t@e.com")
    assert len(calls) == 1


def _sub(form="10-K"):
    return {"filings": {"recent": {"accessionNumber": ["0000000001-25-000001"], "form": [form],
                                   "filingDate": ["2025-02-01"], "primaryDocument": ["acme-20241231.htm"]}}}


def test_filing_html_cached(tmp_path):
    urls = []

    def fake_text(url, ua):
        urls.append(url)
        return "<html></html>"

    c = SecClient(cache=DiskCache(tmp_path), user_agent="t t@example.com", fetch=lambda u, ua: _sub(), fetch_text=fake_text)
    assert c.filing_html(5, "0000000001-25-000001") == "<html></html>"
    assert c.filing_html(5, "0000000001-25-000001") == "<html></html>"
    assert len(urls) == 1 and urls[0].endswith("/5/000000000125000001/acme-20241231.htm")


def test_filing_html_unknown_accn_raises(tmp_path):
    c = SecClient(cache=DiskCache(tmp_path), user_agent="t t@example.com", fetch=lambda u, ua: _sub())
    with pytest.raises(ValueError, match="not in recent"):
        c.filing_html(5, "0000000009-25-000009")


def test_filing_html_wrong_form_raises(tmp_path):
    c = SecClient(cache=DiskCache(tmp_path), user_agent="t t@example.com", fetch=lambda u, ua: _sub("10-Q"))
    with pytest.raises(ValueError, match="10-Q"):
        c.filing_html(5, "0000000001-25-000001")


def test_filing_documents_cached_and_filtered(tmp_path):
    calls = []

    def fake(url, ua):
        calls.append(url)
        return {"directory": {"item": [{"name": "a.htm", "size": "1200"}, {"name": "b.htm", "size": ""},
                                       {"name": "x.xml", "size": "5"}, {"name": "c.htm"}]}}

    c = SecClient(cache=DiskCache(tmp_path), user_agent="t t@example.com", fetch=fake)
    want = [{"name": "a.htm", "size": 1200}, {"name": "b.htm", "size": 0}, {"name": "c.htm", "size": 0}]
    assert c.filing_documents(5, "0000000001-25-000001") == want
    assert c.filing_documents(5, "0000000001-25-000001") == want
    assert len(calls) == 1 and calls[0].endswith("/5/000000000125000001/index.json")


def test_document_html_cached_per_name(tmp_path):
    urls = []

    def fake_text(url, ua):
        urls.append(url)
        return f"<html>{url[-6:]}</html>"

    c = SecClient(cache=DiskCache(tmp_path), user_agent="t t@example.com", fetch_text=fake_text)
    assert c.document_html(5, "0000000001-25-000001", "d2.htm") == "<html>d2.htm</html>"
    assert c.document_html(5, "0000000001-25-000001", "d2.htm") == "<html>d2.htm</html>"
    assert c.document_html(5, "0000000001-25-000001", "d3.htm") == "<html>d3.htm</html>"
    assert len(urls) == 2 and urls[0].endswith("/5/000000000125000001/d2.htm")
