"""Universe selection logic on hand-written dicts (offline)."""
import pytest

from maid.universe import in_sector, listed, shares_outstanding, top_n


def test_in_sector():
    assert in_sector("3674", "tech") and in_sector("7372", "tech") and in_sector("6021", "banks")
    assert not in_sector("5961", "tech") and not in_sector("6211", "banks")
    assert not in_sector("", "tech") and not in_sector("abc", "tech")


def test_listed():
    tj = {"fields": ["cik", "name", "ticker", "exchange"], "data": [
        [1, "A", "GOOGL", "Nasdaq"], [1, "A", "GOOG", "Nasdaq"], [2, "B", "BBB", "OTC"], [3, "C", "CCC", "NYSE"]]}
    assert listed(tj) == {1: ["GOOGL", "GOOG"], 3: ["CCC"]}


def _row(end, val, filed, accn):
    return {"end": end, "val": val, "filed": filed, "accn": accn}


def test_shares_outstanding():
    rows = [_row("2025-02-01", 100, "2025-02-10", "A2"), _row("2025-02-01", 50, "2025-02-10", "A2"),
            _row("2025-02-01", 100, "2025-02-10", "A2"),  # duplicate counted once
            _row("2024-02-01", 90, "2024-02-10", "A1"), _row("2025-05-01", 999, "2025-05-10", "A3")]
    f = {"facts": {"dei": {"EntityCommonStockSharesOutstanding": {"units": {"shares": rows}}}}}
    assert shares_outstanding(f, "2025-03-31") == (150.0, "A2")
    with pytest.raises(ValueError):
        shares_outstanding(f, "2020-01-01")


def test_top_n():
    rows = [{"cik": 3, "market_cap": 5}, {"cik": 2, "market_cap": 5}, {"cik": 1, "market_cap": 9}, {"cik": 4, "market_cap": 1}]
    assert [r["cik"] for r in top_n(rows, 3)] == [1, 2, 3]
