"""Select the 15 largest companies of a sector (tech, banks) or all above a market-cap floor (staples) on the decision date.

Needs SEC_USER_AGENT; local only. Usage: python scripts/select_universe.py {tech,banks,staples} [--date 2025-03-31] [--write] [--out-dir DIR]
"""
import argparse
import csv
import sys
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from maid import sec
from maid.cache import DiskCache
from maid.config import get_settings
from maid.prices import PriceNetworkError, market_price_on
from maid.sec import SecClient, cik10
from maid.universe import (
    MIN_CAP,
    SECTORS,
    above_floor,
    eligible_annual,
    in_sector,
    listed,
    listed_on_cover,
    pick_ticker,
    public_float,
    shares_outstanding,
    top_n,
)
from maid.xbrl import latest_10k, staples_criteria

PRESCREEN = 40
WORKERS = 8
COLS = ["rank", "ticker", "cik", "name", "sic", "market_cap_usd", "shares", "shares_accn", "close", "price_date", "decision_date", "shares_source"]
EXCL_COLS = ["cik", "name", "sic", "ticker", "public_float_usd", "reason", "decision_date"]
ASSET_FRAMES = ["CY2024Q1I", "CY2024Q2I", "CY2024Q3I", "CY2024Q4I"]

FRAMES = [("dei", "EntityCommonStockSharesOutstanding", "CY2025Q1I"), ("dei", "EntityCommonStockSharesOutstanding", "CY2024Q4I"),
          ("us-gaap", "CommonStockSharesOutstanding", "CY2024Q4I"),
          ("us-gaap", "WeightedAverageNumberOfSharesOutstandingBasic", "CY2024")]


def frame_shares(client: SecClient, taxonomy: str, tag: str, period: str) -> dict[int, float]:
    """Sum of shares per CIK from a frame."""
    out: dict[int, float] = {}
    for r in client.frame(taxonomy, tag, "shares", period)["data"]:
        out[int(r["cik"])] = out.get(int(r["cik"]), 0.0) + float(r["val"])
    return out


def sic_info(client: SecClient, sic_cache: DiskCache, cik: int) -> dict:
    """{"sic", "name"} for a CIK from SEC submissions (cached on disk)."""
    def get():
        s = sec._get_json(f"https://data.sec.gov/submissions/CIK{cik10(cik)}.json", client.user_agent)
        return {"sic": s.get("sic", ""), "name": s.get("name", "")}
    return sic_cache.get_or_compute(DiskCache.key("sic", cik), get)


def floor_main(a, client: SecClient) -> int:
    """Staples: every sector company with a 10-K and market cap >= floor; nothing is dropped without a bucket."""
    err = lambda *x: print(*x, file=sys.stderr)  # noqa: E731
    try:
        listed_today = listed(client.tickers())
        sic_cache = DiskCache(get_settings().cache_dir / "sic")
        cands = sorted({int(r["cik"]) for p in ASSET_FRAMES for r in client.frame("us-gaap", "Assets", "USD", p)["data"]})
        err(f"candidates (reported Assets in 2024): {len(cands)}")
        info: dict[int, dict] = {}
        failed: list[int] = []
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futs = {ex.submit(sic_info, client, sic_cache, cik): cik for cik in cands}
            for n, f in enumerate(as_completed(futs), 1):
                try:
                    info[futs[f]] = f.result()
                except (ValueError, OSError) as e:
                    if isinstance(e, ValueError) and "SEC_USER_AGENT" in str(e):
                        ex.shutdown(wait=False, cancel_futures=True)
                        raise
                    failed.append(futs[f])
                if n % 500 == 0:
                    err(f"SIC scan {n}/{len(cands)}")
        if failed:
            err(f"ERROR: submissions failed for CIKs {sorted(failed)}; rerun resumes from cache")
            return 1
        sector = sorted(c for c in cands if in_sector(info[c]["sic"], a.sector))
        err(f"in sector: {len(sector)}")
        ineligible, excluded, priced = 0, [], []
        for cik in sector:
            name, sic = info[cik]["name"], info[cik]["sic"]
            facts = ticker = None
            try:
                facts = client.companyfacts(cik)
            except urllib.error.HTTPError as e:
                if e.code != 404:
                    raise
            if facts is None:
                ineligible += 1
                continue

            def drop(reason, ticker=None, cik=cik, name=name, sic=sic, facts=facts):
                excluded.append({"cik": cik, "name": name, "sic": sic, "ticker": ticker or "",
                                 "public_float_usd": public_float(facts, a.date), "reason": reason})

            try:
                accn = latest_10k(facts, a.date)[0]
            except ValueError:
                ineligible += 1
                continue
            try:
                cover = client.cover(cik, accn)
            except ValueError as e:
                if "SEC_USER_AGENT" in str(e):
                    raise
                drop(f"cover: {e}")
                continue
            if not listed_on_cover(cover):
                ineligible += 1
                continue
            try:
                staples_criteria(facts, a.date)
            except ValueError as e:
                drop(f"criteria: {e}")
                continue
            try:
                n_sh, sh_accn, src = shares_outstanding(facts, a.date, cover)
            except ValueError as e:
                drop(f"shares: {e}")
                continue
            try:
                ticker = pick_ticker(cik, cover, listed_today)
            except ValueError as e:
                drop(f"ticker: {e}")
                continue
            try:
                p = market_price_on(ticker, a.date)
            except PriceNetworkError as e:
                err(f"ERROR price lookup failed after retries: {e}")
                return 1
            except ValueError as e:
                if cik in listed_today:
                    err(f"ERROR price lookup failed for listed {ticker}: {e}")
                    return 1
                drop(f"no Yahoo price: {e}", ticker)
                continue
            priced.append({"cik": cik, "ticker": ticker, "name": name, "sic": sic, "market_cap": n_sh * p["close"],
                           "shares": n_sh, "accn": sh_accn, "close": p["close"], "price_date": p["date"], "source": src})
    except ValueError as e:
        err(f"ERROR {e}")
        return 1
    sel = above_floor(priced, MIN_CAP[a.sector])
    for r in sorted(priced, key=lambda r: -r["market_cap"]):
        if 0.9e9 <= r["market_cap"] < MIN_CAP[a.sector]:
            print(f"near floor: {r['ticker']} {r['market_cap'] / 1e9:.2f}bn {r['source']}", file=sys.stderr)
    for i, r in enumerate(sel, 1):
        print(f"{i:>2} {r['ticker']:<6} {r['name'][:32]:<32} {r['sic']} {r['market_cap'] / 1e9:>9.1f}bn {r['accn']} {r['price_date']} {r['source']}")
    print(f"candidates {len(cands)}, in sector {len(sector)}, ineligible {ineligible}, excluded {len(excluded)}, "
          f"priced {len(priced)}, below floor {len(priced) - len(sel)}, selected {len(sel)}")
    if a.write:
        out = Path(a.out_dir)
        out.mkdir(parents=True, exist_ok=True)
        with (out / f"{a.sector}.csv").open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(COLS)
            for i, r in enumerate(sel, 1):
                w.writerow([i, r["ticker"], r["cik"], r["name"], r["sic"], round(r["market_cap"]), r["shares"], r["accn"],
                            r["close"], r["price_date"], a.date, r["source"]])
        excluded.sort(key=lambda r: (r["public_float_usd"] is None, -(r["public_float_usd"] or 0), r["cik"]))
        with (out / f"{a.sector}_excluded.csv").open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(EXCL_COLS)
            for r in excluded:
                pf = "" if r["public_float_usd"] is None else round(r["public_float_usd"])
                w.writerow([r["cik"], r["name"], r["sic"], r["ticker"], pf, r["reason"], a.date])
        print(f"wrote {out / (a.sector + '.csv')} and {out / (a.sector + '_excluded.csv')}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("sector", choices=sorted(SECTORS))
    ap.add_argument("--date", default=get_settings().decision_date)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--out-dir", default="data/universe")
    a = ap.parse_args()
    client, cache_dir = SecClient(), get_settings().cache_dir
    if a.sector in MIN_CAP:
        return floor_main(a, client)
    try:
        cands = listed(client.tickers())
        sic_cache = DiskCache(cache_dir / "sic")
        in_sec: dict[int, dict] = {}

        done = failed = 0
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futs = {ex.submit(sic_info, client, sic_cache, cik): cik for cik in cands}
            for f in as_completed(futs):
                cik = futs[f]
                done += 1
                try:
                    info = f.result()
                except (ValueError, OSError) as e:
                    if isinstance(e, ValueError) and "SEC_USER_AGENT" in str(e):
                        ex.shutdown(wait=False, cancel_futures=True)
                        raise
                    print(f"warning: submissions failed for CIK {cik}: {e}", file=sys.stderr)
                    failed += 1
                    continue
                if in_sector(info["sic"], a.sector):
                    in_sec[cik] = info
                if done % 250 == 0:
                    print(f"SIC scan {done}/{len(cands)}, {len(in_sec)} in sector", file=sys.stderr)
        in_sec = {cik: in_sec[cik] for cik in cands if cik in in_sec}
        print(f"SIC scan done: {len(in_sec)} in sector, {failed} failed", file=sys.stderr)

        shares: dict[int, float] = {}
        for tax, tag, period in FRAMES:
            try:
                fs = frame_shares(client, tax, tag, period)
            except urllib.error.HTTPError as e:
                if e.code != 404:
                    raise
                print(f"warning: frame {tax}:{tag} {period} not found", file=sys.stderr)
                continue
            for cik, v in fs.items():
                shares.setdefault(cik, v)
        est = []
        for cik in in_sec:
            if cik not in shares:
                continue
            try:
                est.append((shares[cik] * market_price_on(cands[cik][0], a.date)["close"], cik))
            except PriceNetworkError as e:
                print(f"ERROR price lookup failed after retries: {e}", file=sys.stderr)
                return 1
            except ValueError as e:
                if "SEC_USER_AGENT" in str(e):
                    raise
                print(f"warning: no price for {cands[cik][0]}: {e}", file=sys.stderr)
        n_with = sum(1 for c in in_sec if c in shares)
        print(f"pre-screen: {len(in_sec)} in sector, {n_with} with shares, {len(est)} priced", file=sys.stderr)
        top = [cik for _, cik in sorted(est, key=lambda x: (-x[0], x[1]))[:PRESCREEN]]

        rows, price_fail = [], 0
        for cik in top:
            facts = client.companyfacts(cik)
            if not eligible_annual(facts, a.date, a.sector):
                continue
            try:
                n_sh, accn, src = shares_outstanding(facts, a.date)
                p = market_price_on(cands[cik][0], a.date)
            except PriceNetworkError as e:
                print(f"ERROR price lookup failed after retries: {e}", file=sys.stderr)
                return 1
            except ValueError as e:
                if "SEC_USER_AGENT" in str(e):
                    raise
                print(f"warning: {cands[cik][0]}: {e}", file=sys.stderr)
                price_fail += 1
                continue
            rows.append({"cik": cik, "ticker": cands[cik][0], "name": in_sec[cik]["name"], "sic": in_sec[cik]["sic"],
                         "market_cap": n_sh * p["close"], "shares": n_sh, "accn": accn, "close": p["close"],
                         "price_date": p["date"], "source": src})
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
        out = Path(a.out_dir) / f"{a.sector}.csv"
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(COLS)
            for i, r in enumerate(sel, 1):
                w.writerow([i, r["ticker"], r["cik"], r["name"], r["sic"], round(r["market_cap"]), r["shares"], r["accn"],
                            r["close"], r["price_date"], a.date, r["source"]])
        print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
