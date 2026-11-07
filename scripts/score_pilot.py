"""Score the first N companies of a universe with the LLM scorer (K samples) and write a local review table.

Usage: python scripts/score_pilot.py [--sector staples] [--n 10] [--k 5] [--out data/pilot]
Needs SEC_USER_AGENT (cached 10-Ks) and a local LLM server (LLM_* settings, default Ollama on localhost). Writes only under --out.
"""
import argparse
import json
import sys
from pathlib import Path

from maid.cache import DiskCache
from maid.config import get_settings
from maid.llm import ContextTruncated, LLMScorer, ScoringError, make_client
from maid.real_data import SECTORS, load_filings
from maid.rubrics import PROMPT_VERSION
from maid.scoring import aggregate
from maid.tenk import EXTRACTOR_VERSION, criterion_text

CRITERIA = ("pricing_power", "strategy_clarity", "capital_allocation")
COLS = ("label", "ticker", "criterion", "median", "std", "valid/k", "failed attempts", "prompt tokens", "source",
        "truncated", "quote")


def main() -> int:
    """Run the pilot; returns the process exit code."""
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--sector", choices=sorted(SECTORS), default="staples")
    p.add_argument("--n", type=int, default=10)
    p.add_argument("--k", type=int, default=5)
    p.add_argument("--out", default="data/pilot")
    p.add_argument("--temperature", type=float, default=0.7)
    a = p.parse_args()
    settings = get_settings()
    labels, texts, _ = load_filings(settings.decision_date, a.sector)
    scorer = LLMScorer(make_client(settings), settings.model, DiskCache(settings.cache_dir / "llm"),
                       temperature=a.temperature)
    rows, ok, failed = [], 0, 0
    for c in sorted(labels)[:a.n]:
        for crit in CRITERIA:
            ct = criterion_text(texts[c], crit)
            n0 = len(scorer.log)
            try:
                samples = scorer.score(c, crit, ct["text"], a.k)
            except ScoringError as e:
                failed += 1
                recs = scorer.log[n0:]
                rows.append((c, labels[c], crit, f"ERROR: {e}", "", f"{sum(r['ok'] for r in recs)}/{a.k}", sum(not r["ok"] for r in recs),
                             sum(r["prompt_tokens"] for r in recs), ct["source"], ct["truncated"], ""))
                continue
            except ContextTruncated as e:
                print(f"context truncated: {e}", file=sys.stderr)
                return 2
            ok += 1
            recs = scorer.log[n0:]
            med, std = aggregate(samples)
            quote = samples[0].evidence.replace("|", "/")[:300]
            rows.append((c, labels[c], crit, med.score, f"{std:.2f}", f"{len(samples)}/{a.k}",
                         sum(not r["ok"] for r in recs), sum(r["prompt_tokens"] for r in recs), ct["source"],
                         ct["truncated"], quote))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    seen = sorted({r["model"] for r in scorer.log})
    pt = sum(r["prompt_tokens"] for r in scorer.log)
    cpt = sum(r["completion_tokens"] for r in scorer.log)
    lines = [f"sector={a.sector} n={a.n} k={a.k} temperature={a.temperature} prompt_version={PROMPT_VERSION} "
             f"extractor_version={EXTRACTOR_VERSION} model={settings.model} reply_models={seen}", "",
             "| " + " | ".join(COLS) + " |", "|" + "---|" * len(COLS)]
    lines += ["| " + " | ".join(str(x) for x in r) + " |" for r in rows]
    lines += ["", f"total prompt tokens: {pt}", f"total completion tokens: {cpt}"]
    (out / "pilot.md").write_text("\n".join(lines) + "\n")
    (out / "pilot_log.jsonl").write_text("".join(json.dumps(r) + "\n" for r in scorer.log))
    print(f"cells ok: {ok}, failed: {failed}, tokens: {pt + cpt}, output: {out / 'pilot.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
