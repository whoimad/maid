"""Select the 15 largest companies of a sector by market cap on the decision date (needs SEC_USER_AGENT; local only).

Usage: python scripts/select_universe.py {tech,banks} [--date 2025-03-31] [--write]
"""
import argparse
import csv
import sys
from pathlib import Path

from maid import sec
from maid.cache import DiskCache
from maid.config import get_settings
from maid.prices import market_price_on
from maid.sec import SecClient, cik10
from maid.universe import SECTORS, eligible_annual, in_sector, listed, shares_outstanding, top_n

PRESCREEN = 40
COLS = ["rank", "ticker", "cik", "name", "sic", "market_cap_usd", "shares", "shares_accn", "close", "price_date", "decision_date"]


def frame_shares(client: SecClient, period: str) -> dict[int, float]:
    """Sum of cover-page shares per CIK from a dei frame."""
    out: dict[int, float] = {}
    for r in client.frame("dei", "EntityCommonStockSharesOutstanding", "shares", period)["data"]:
        out[int(r["cik"])] = out.get(int(r["cik"]), 0.0) + float(r["val"])
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("sector", choices=sorted(SECTORS))
    ap.add_argument("--date", default=get_settings().decision_date)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    client, cache_dir = SecClient(), get_settings().cache_dir
    try:
        cands = listed(client.tickers())
        sic_cache = DiskCache(cache_dir / "sic")
        in_sec: dict[int, dict] = {}
        for i, cik in enumerate(cands, 1):
            def get(cik=cik):
                s = sec._get_json(f"https://data.sec.gov/submissions/CIK{cik10(cik)}.json", client.user_agent)
                return {"sic": s.get("sic", ""), "name": s.get("name", "")}
            try:
                info = sic_cache.get_or_compute(DiskCache.key("sic", cik), get)
            except ValueError as e:
                if "SEC_USER_AGENT" in str(e):
                    raise
                print(f"warning: submissions failed for CIK {cik}: {e}", file=sys.stderr)
                continue
            except OSError as e:
                print(f"warning: submissions failed for CIK {cik}: {e}", file=sys.stderr)
                continue
            if in_sector(info["sic"], a.sector):
                in_sec[cik] = info
            if i % 250 == 0:
                print(f"SIC scan {i}/{len(cands)}, {len(in_sec)} in sector", file=sys.stderr)

        shares = frame_shares(client, "CY2025Q1I")
        for cik, v in frame_shares(client, "CY2024Q4I").items():
            shares.setdefault(cik, v)
        est = []
        for cik in in_sec:
            if cik not in shares:
                continue
            try:
                est.append((shares[cik] * market_price_on(cands[cik][0], a.date)["close"], cik))
            except Exception as e:  # yfinance raises many types
                print(f"warning: no price for {cands[cik][0]}: {e}", file=sys.stderr)
        top = [cik for _, cik in sorted(est, key=lambda x: (-x[0], x[1]))[:PRESCREEN]]

        rows, price_fail = [], 0
        for cik in top:
            facts = client.companyfacts(cik)
            if not eligible_annual(facts, a.date, a.sector):
                continue
            try:
                n_sh, accn = shares_outstanding(facts, a.date)
                p = market_price_on(cands[cik][0], a.date)
            except ValueError as e:
                if "SEC_USER_AGENT" in str(e):
                    raise
                print(f"warning: {cands[cik][0]}: {e}", file=sys.stderr)
                price_fail += 1
                continue
            except Exception as e:
                print(f"warning: {cands[cik][0]}: {e}", file=sys.stderr)
                price_fail += 1
                continue
            rows.append({"cik": cik, "ticker": cands[cik][0], "name": in_sec[cik]["name"], "sic": in_sec[cik]["sic"],
                         "market_cap": n_sh * p["close"], "shares": n_sh, "accn": accn, "close": p["close"],
                         "price_date": p["date"]})
        if top and price_fail / len(top) > 0.25:
            print(f"ERROR: {price_fail}/{len(top)} candidates failed price/share lookup; yfinance may be broken", file=sys.stderr)
            return 1
        sel = top_n(rows)
        if len(sel) < 15:
            print(f"ERROR: only {len(sel)} eligible companies in {a.sector}", file=sys.stderr)
            return 1
    except ValueError as e:
        print(f"ERROR {e}", file=sys.stderr)
        return 1

    for i, r in enumerate(sel, 1):
        print(f"{i:>2} {r['ticker']:<6} {r['name'][:32]:<32} {r['sic']} {r['market_cap'] / 1e9:>9.1f}bn {r['accn']} {r['price_date']}")
    if a.write:
        out = Path("data/universe") / f"{a.sector}.csv"
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(COLS)
            for i, r in enumerate(sel, 1):
                w.writerow([i, r["ticker"], r["cik"], r["name"], r["sic"], round(r["market_cap"]), r["shares"], r["accn"],
                            r["close"], r["price_date"], a.date])
        print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
