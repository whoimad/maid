"""Fetch the decision-date 10-K of each universe company, extract Items 1/1A/7, anonymize, and report coverage.

Usage: python scripts/fetch_filings.py [--sector tech|staples] [--date 2025-03-31]
Needs SEC_USER_AGENT; downloads are cached under data/cache (local only). Prints only.
"""
import argparse
import statistics
import sys

from maid.config import get_settings
from maid.real_data import SECTORS, company_filing, load_sec, read_aliases, read_universe
from maid.sec import SecClient
from maid.tenk import BUDGET_TOKENS, EXTRACTOR_VERSION, criterion_text

CRIT = ("strategy_clarity", "pricing_power", "capital_allocation")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sector", default="tech", choices=sorted(SECTORS))
    ap.add_argument("--date", default=get_settings().decision_date)
    a = ap.parse_args()
    client = SecClient()
    try:
        labels, _, meta = load_sec(a.date, a.sector, client)
    except ValueError as e:
        print(f"ERROR {e}", file=sys.stderr)
        return 1
    ciks = {r["ticker"]: int(r["cik"]) for r in read_universe(SECTORS[a.sector][0])}
    aliases = read_aliases()
    counts, failed = {"ok": 0, "SHORT": 0, "EMPTY": 0}, False
    exhibits = no_split = n_trunc = 0
    residuals = []
    for label, ticker in labels.items():  # same per-company loop as real_data.load_filings, but failures do not stop it
        accn = meta[label]["accn"]
        try:
            t, info = company_filing(client, ciks[ticker], accn, ticker, label, aliases.get(ticker, ()))
        except Exception as e:  # noqa: BLE001 - report and continue per company
            if "SEC_USER_AGENT" in str(e):
                print(f"ERROR {e}", file=sys.stderr)
                return 1
            print(f"{label} {ticker} ERROR {e}")
            failed = True
            continue
        w = {k: len(t[k].split()) for k in ("1", "1a", "7")}
        flag = "EMPTY" if not w["1"] or not w["7"] else "SHORT" if w["1"] < 1000 or w["7"] < 1000 else "ok"
        counts[flag] += 1
        c = {k: criterion_text(t, k) for k in CRIT}
        cut = [k for k in CRIT if c[k]["truncated"]]
        split = c["pricing_power"]["split_found"]
        exhibits += info["mdna_source"] != "body"
        no_split += not split
        n_trunc += bool(cut)
        residuals.append(info["residual"])
        print(f"{label} {ticker} {accn} {w['1']} {w['1a']} {w['7']} {info['mdna_source']} {info['replacements']} "
              f"{info['residual']} {c['strategy_clarity']['tokens']} {c['pricing_power']['tokens']} "
              f"{c['capital_allocation']['tokens']} {'y' if split else 'n'} {','.join(cut) or '-'} {flag}")
    print(f"ok={counts['ok']} SHORT={counts['SHORT']} EMPTY={counts['EMPTY']} exhibit_mdna={exhibits} "
          f"no_split={no_split} truncated={n_trunc}"
          + (f" max_residual={max(residuals)} median_residual={int(statistics.median(residuals))}" if residuals else "")
          + f" extractor={EXTRACTOR_VERSION} budget={BUDGET_TOKENS}")
    return 1 if failed or counts["EMPTY"] else 0


if __name__ == "__main__":
    sys.exit(main())
