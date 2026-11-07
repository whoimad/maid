"""Universe selection logic on hand-written dicts (offline)."""
import pytest

from maid.universe import (
    COVER_SOURCE,
    above_floor,
    in_sector,
    listed,
    listed_on_cover,
    pick_ticker,
    public_float,
    shares_outstanding,
    top_n,
)


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
    assert shares_outstanding(f, "2025-03-31") == (150.0, "A2", "EntityCommonStockSharesOutstanding")
    with pytest.raises(ValueError):
        shares_outstanding(f, "2020-01-01")


def _f(tag, rows, tax="us-gaap"):
    return {"facts": {tax: {tag: {"units": {"shares": rows}}}}}


def test_shares_cover_page_ignores_later_filings():
    rows = [_row("2025-02-01", 100, "2025-02-10", "A2"), _row("2025-05-01", 999, "2025-05-10", "A3")]
    assert shares_outstanding(_f("EntityCommonStockSharesOutstanding", rows, "dei"), "2025-03-31")[0] == 100.0


def test_shares_us_gaap_latest_end_not_summed():
    rows = [_row("2023-12-31", 100, "2025-02-05", "A1"), _row("2024-12-31", 120, "2025-02-05", "A1"),
            _row("2025-12-31", 999, "2026-02-05", "A2")]
    assert shares_outstanding(_f("CommonStockSharesOutstanding", rows), "2025-03-31") == (120.0, "A1", "CommonStockSharesOutstanding")


def test_shares_weighted_average_longest_duration():
    tag = "WeightedAverageNumberOfSharesOutstandingBasic"
    rows = [{**_row("2024-12-31", 90, "2025-01-30", "A1"), "start": "2024-10-01"},
            {**_row("2024-12-31", 95, "2025-01-30", "A1"), "start": "2024-01-01"},
            {**_row("2025-06-30", 999, "2025-07-30", "A2"), "start": "2025-01-01"}]
    assert shares_outstanding(_f(tag, rows), "2025-03-31") == (95.0, "A1", tag)
    with pytest.raises(ValueError):
        shares_outstanding(_f(tag, rows), "2020-01-01")


def test_top_n():
    rows = [{"cik": 3, "market_cap": 5}, {"cik": 2, "market_cap": 5}, {"cik": 1, "market_cap": 9}, {"cik": 4, "market_cap": 1}]
    assert [r["cik"] for r in top_n(rows, 3)] == [1, 2, 3]


def test_in_sector_staples():
    assert all(in_sector(s, "staples") for s in ("2086", "2111", "2844", "5411"))
    assert not any(in_sector(s, "staples") for s in ("5331", "2670", "5140"))


def test_shares_skip_zero():
    f = {"facts": {"dei": {"EntityCommonStockSharesOutstanding": {"units": {"shares": [_row("2010-01-01", 0, "2025-02-10", "A2")]}}},
                   "us-gaap": {"CommonStockSharesOutstanding": {"units": {"shares": [_row("2024-12-31", 120, "2025-02-10", "A2")]}}}}}
    assert shares_outstanding(f, "2025-03-31") == (120.0, "A2", "CommonStockSharesOutstanding")


def test_shares_skip_stale():
    stale = _row("2022-12-31", 500, "2023-01-10", "A0")
    f = {"facts": {"dei": {"EntityCommonStockSharesOutstanding": {"units": {"shares": [stale]}}},
                   "us-gaap": {"CommonStockSharesOutstanding": {"units": {"shares": [_row("2024-12-31", 120, "2025-02-05", "A2")]}}}}}
    assert shares_outstanding(f, "2025-03-31")[0] == 120.0
    with pytest.raises(ValueError):
        shares_outstanding(_f("EntityCommonStockSharesOutstanding", [stale], "dei"), "2025-03-31")


def test_shares_cover_fallback():
    cover = {"accn": "X", "shares": 355864471.0, "symbols": []}
    assert shares_outstanding({"facts": {}}, "2025-03-31", cover) == (355864471.0, "X", COVER_SOURCE)
    with pytest.raises(ValueError):
        shares_outstanding({"facts": {}}, "2025-03-31", {**cover, "shares": None})


def test_listed_on_cover():
    assert listed_on_cover({"symbols": [["TAP 32", "NYSE"]]}) and listed_on_cover({"symbols": [["X", "nasdaq"]]})
    assert not listed_on_cover({"symbols": [["X", "NYSEAMER"], ["Y", ""]]}) and not listed_on_cover({"symbols": []})


def test_pick_ticker():
    today = {1: ["AAA", "AAB"], 9: ["K"]}
    assert pick_ticker(1, {"symbols": []}, today) == "AAA"
    assert pick_ticker(2, {"symbols": [["TAP 32", "NYSE"], ["KK", "NYSE"]]}, today) == "KK"
    assert pick_ticker(2, {"symbols": [["X.A", "NASDAQ"]]}, today) == "X-A"
    with pytest.raises(ValueError, match="reused"):
        pick_ticker(2, {"symbols": [["K", "NYSE"]]}, today)
    with pytest.raises(ValueError):
        pick_ticker(2, {"symbols": [["K", "NYSEAMER"]]}, today)


def test_public_float():
    f = {"facts": {"dei": {"EntityPublicFloat": {"units": {"USD": [
        {"end": "2023-06-30", "val": 5, "filed": "2024-02-01"}, {"end": "2024-06-30", "val": 7, "filed": "2025-02-01"},
        {"end": "2025-06-30", "val": 9, "filed": "2026-02-01"}]}}}}}
    assert public_float(f, "2025-03-31") == 7.0
    assert public_float({"facts": {}}, "2025-03-31") is None


def test_above_floor():
    rows = [{"cik": 3, "market_cap": 1e9}, {"cik": 2, "market_cap": 1e9}, {"cik": 1, "market_cap": 5e9}, {"cik": 4, "market_cap": 9e8}]
    assert [r["cik"] for r in above_floor(rows, 1e9)] == [1, 2, 3]
