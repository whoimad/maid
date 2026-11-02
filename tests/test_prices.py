"""Pure price helpers (offline)."""
import pytest

from maid.prices import close_on, split_factor_after, total_return


def test_close_on():
    c = {"2025-03-28": 10.0, "2025-03-31": 11.0}
    assert close_on(c, "2025-03-31") == ("2025-03-31", 11.0)
    assert close_on(c, "2025-04-01") == ("2025-03-31", 11.0)
    assert close_on(c, "2025-03-30") == ("2025-03-28", 10.0)


def test_close_on_too_old():
    with pytest.raises(ValueError):
        close_on({"2025-03-01": 1.0}, "2025-03-31")


def test_split_factor_after():
    assert split_factor_after({"2024-06-10": 10.0, "2025-06-01": 2.0, "2026-01-05": 3.0}, "2025-03-31") == 6.0


def test_total_return():
    assert total_return({"2025-03-31": 100.0, "2026-03-31": 120.0}, "2025-04-01", "2026-03-31") == pytest.approx(0.2)


def _fake_yf(monkeypatch, tmp_path, history):
    import sys
    import types

    import maid.prices as prices
    monkeypatch.setenv("MAID_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(prices.time, "sleep", lambda s: None)
    monkeypatch.setitem(sys.modules, "yfinance", types.SimpleNamespace(Ticker=lambda t: types.SimpleNamespace(history=history)))
    return prices


def test_fetch_series_retries_then_succeeds(monkeypatch, tmp_path):
    pd = pytest.importorskip("pandas")
    calls = []

    def history(**kw):
        calls.append(1)
        if len(calls) < 3:
            raise OSError("Could not resolve host")
        return pd.DataFrame({"Close": [1.0]}, index=pd.to_datetime(["2025-03-31"]))
    prices = _fake_yf(monkeypatch, tmp_path, history)
    assert prices.fetch_series("XXX", "2025-03-25", "2025-04-01") == {"2025-03-31": 1.0}
    assert len(calls) == 3


def test_fetch_series_network_error(monkeypatch, tmp_path):
    def history(**kw):
        raise OSError("Could not resolve host")
    prices = _fake_yf(monkeypatch, tmp_path, history)
    with pytest.raises(prices.PriceNetworkError):
        prices.fetch_series("XXX", "2025-03-25", "2025-04-01")


def test_fetch_series_empty_is_no_data(monkeypatch, tmp_path):
    pd = pytest.importorskip("pandas")
    prices = _fake_yf(monkeypatch, tmp_path, lambda **kw: pd.DataFrame({"Close": []}))
    with pytest.raises(ValueError, match="no price data"):
        prices.fetch_series("XXX", "2025-03-25", "2025-04-01")
