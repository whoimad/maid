# Session handoff (2026-11-03)

Start here. Then read, in this order:
1. `notes/MEMO.md` (local only, not on GitHub): the owner's high-level project memo. **Not yet updated for 025/026.**
2. `plans/README.md`: status of every plan.
3. `docs/architecture/data.md`: the real-data spec, including the staples universe and (after 026) the
   pre-registered staples test.

Workflow: the `/improve` skill. The advisor writes plans in `plans/`, executor subagents implement them in
worktrees, and the advisor reviews and merges into the local branch `integration/prototype`. Push only when the
owner says so.

## Git state

- Local `integration/prototype` at `4b51ec6`. GitHub has `5b3b5e7`. **Not pushed:** plan 025, the 025 merge
  (`4bf145c`), plan 026. Ask before pushing (the push updates PR #16).
- Tests: 135 passed, 1 skipped; ruff clean.
- **Plan 026 executor was still running when this was written**: branch `feat/staples-backtest`, worktree under
  `.claude/worktrees/agent-*`, based on `4b51ec6`. If the session died, check `git worktree list` and
  `git log 4b51ec6..feat/staples-backtest`. Review it against the plan's done criteria before merging. If it's
  half done, re-dispatch from the plan rather than patching by hand.

## Owner decisions (do not re-ask)

Earlier sessions: decision date 2025-03-31; evaluation window 2025-04-01..2026-03-31; latest 10-K filed on or before
the date; universe by rule only; real data stays local (only `data/universe/*.csv` committed); net margin for
everyone (D18); tech null result documented as a process result; staples sector by SIC (food/bev 2000–2099, tobacco
2100–2199, household 2840–2844, grocery 5411); $1bn floor; ROA as the fourth staples criterion; one set of fallback
tags for everyone; share-count fix; survivorship rule (delisted included only if Yahoo has prices); test fixed
before the run.

This session (2026-11-03):
1. **Accept losing Kellanova.** One rule for everyone. No deal-price exceptions for takeover targets.
2. **Share-source order stays as decided:** companyfacts dei → `CommonStockSharesOutstanding` → weighted average →
   10-K cover. Seven staples (TAP, EL, MKC, HRL, SAM, TR, UTZ) use the weighted average (TAP 208.8M vs 192.7M on
   the cover). Moving the cover earlier would reorder the frozen banks list (FCNCA 11th → 13th). This was the
   advisor's call in review, under the "one rule" principle. Recorded in `data.md`.
3. **Three more fallback tags, appended last** (advisor's call in review, same principle as the owner's decision on
   fallback tags): capex `PaymentsToAcquireOtherPropertyPlantAndEquipment`, `PaymentsToAcquireOtherProductiveAssets`;
   operating cash flow `NetCashProvidedByUsedInOperatingActivitiesContinuingOperations`. They rescued Smithfield and
   Primo Brands. Tech values were checked and are unchanged.

## What was done

- **Plan 025 DONE**, merged `4bf145c`. Staples universe frozen:
  - `data/universe/staples.csv`: **61 companies**. All 16 sanity names are in. WMT, COST, UL and BTI are out.
  - `data/universe/staples_excluded.csv`: 19 companies. 13 have no Yahoo price (Kellanova, TreeHouse, WK Kellogg,
    SunOpta, Olaplex, Vector, Duckhorn, Primo Water, ...). 6 are small companies with criteria gaps.
  - Near the floor: NGVC at $0.92bn (out). The smallest selected company is $1.05bn.
  - Counts: 6928 candidates (2024 Assets frames), 163 in sector, 57 ineligible, 19 excluded, 87 priced, 26 below the
    floor, 61 selected.
  - Re-running tech and banks with the new code gives identical lists, and the tech criteria values are identical.
  - D19 is in `decisions.md`.
- Yahoo checked live: **no history** for delisted K, THS, KLG, STKL, OLPX.
- **Plan 026 written** (`plans/026-staples-backtest.md`) and dispatched. It covers:
  - a `sector` setting (tech/staples);
  - numeric labels "Company 001.." for all real data;
  - a delisted-aware `window_return`;
  - `--sector` in `scripts/backtest.py`;
  - the pre-registration text added to `data.md` as its **first commit**.
- Power at n = 61 (seeded simulation, 2000 trials): 12% / 32% / 60% for rho 0.1 / 0.2 / 0.3.

## Next

1. Review and merge plan 026: re-run its done criteria, check the pre-registration commit comes first, read the
   tests.
2. **The advisor runs the real backtest** (the executor is forbidden to):
   `cd /home/imad/maid && python scripts/backtest.py --sector staples`. If Yahoo rate-limits, wait and rerun
   (successes are cached; test with GIS first).
3. Write `docs/research/backtest-staples-results.md` (summary stats only, same shape as
   `backtest-quant-only-results.md`). Report the primary CRITIC Kendall tau first, whatever it is.
4. Update `notes/MEMO.md` (local) with the 025 outcome, the excluded list, and the backtest result (per-company
   returns may go there; never commit them).
5. Ask the owner before pushing.

Later options (not planned): LLM scores from 10-K text with memorization controls; bank criteria spike; medical
devices as a backup sector.

## Practical warnings

- Yahoo rate-limits often (it throttled for about 40 minutes on 2026-11-03). Empty data looks like "no price data".
- Executor worktrees start from `main`: tell them to `git reset --hard <integration/prototype SHA>` first. The venv
  is in the main repo, so use `PYTHONPATH=<worktree>/src`. Real runs use `/home/imad/maid` as the working directory.
  Scripts that write must take an output dir (e.g. `select_universe.py --out-dir`), so they don't write into the
  main tree.
- Keep executor tasks small. Network-heavy real runs are better done by the advisor after review. The 025 executor
  used about 140k tokens, mostly on waits and logs.
- Scratch from 025's executor: `/tmp/claude-1000/plan025/` (tech before/after outputs, run logs). It's temporary.
