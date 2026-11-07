# Plan 021: Parallel SEC downloads (8 at a time, still ≤ 8 requests/s) with retry on network errors

> **Executor instructions**: Follow this plan step by step. Run every verification command and confirm the expected
> result before moving to the next step. If anything in the "STOP conditions" section occurs, stop and report — do
> not improvise. When done, update the status row for this plan in `plans/README.md` — unless a reviewer dispatched
> you and told you they maintain the index.
>
> **Drift check (run first)**: `git diff --stat 138373d -- src/maid/sec.py scripts/select_universe.py tests/test_sec.py`
> must print nothing. Otherwise compare against the excerpts below; on a mismatch, STOP.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW (same requests, issued concurrently; the rate cap is unchanged)
- **Depends on**: plans/020-universe-and-prices.md (DONE)
- **Category**: perf
- **Planned at**: commit `138373d` (branch `integration/prototype`), 2026-11-02

## Why this matters

`scripts/select_universe.py` looks up the SEC industry (SIC) code of every NYSE/Nasdaq company: 6,041 sequential
downloads of `https://data.sec.gov/submissions/CIK##########.json`. Each takes about 1 second round trip, so the scan
takes about 1.5 hours, although the SEC allows 10 requests/s. Downloading 8 at a time while keeping the global cap
at 8 requests/s cuts that to about 13 minutes. The owner's bandwidth is about 20 MB/s, and these files are about
0.5–1 MB each.

There is a second problem. A transient network error (seen in a real run: `<urlopen error [Errno -3] Temporary
failure in name resolution>`) makes the script skip that company, which silently drops it from the candidate pool.
A short retry fixes most of these.

Results are cached per company in `data/cache/sic/` (gitignored). A new run reuses everything already cached.

## Current state

`src/maid/sec.py` (top of file, verbatim):
```python
MIN_INTERVAL = 0.125  # seconds between network requests (SEC allows 10/s)
_last = [0.0]


def _get_json(url: str, user_agent: str) -> dict:
    """GET a JSON URL with the SEC User-Agent, rate-limited."""
    if not user_agent.strip():
        raise ValueError("SEC_USER_AGENT is not set (SEC requires a contact, e.g. 'MAID research you@example.com')")
    wait = MIN_INTERVAL - (time.monotonic() - _last[0])
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(url, headers={"User-Agent": user_agent, "Accept-Encoding": "identity"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    finally:
        _last[0] = time.monotonic()
```
This limiter is not thread-safe. It also spaces requests by end time to start time, which forces them to run
sequentially.

`scripts/select_universe.py`, the SIC scan loop inside `main()` (verbatim):
```python
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
```
`DiskCache.get_or_compute` (`src/maid/cache.py`) writes `<key>.json` atomically through a temp file named
`<key>.<pid>.tmp`. Distinct keys never collide, so threads that write different CIKs are safe.

Conventions: one-line docstrings, compact code, tests offline with plain `assert` (`tests/test_sec.py` has an autouse
fixture that makes `urllib.request.urlopen` raise).

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Setup | `python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev,gui]"` | exit 0 |
| Tests | `pytest -q` | all pass |
| Lint | `ruff check .` | `All checks passed!` |

## Scope

**In scope:** `src/maid/sec.py`, `scripts/select_universe.py`, `tests/test_sec.py`.
**Out of scope:** everything else, including `universe.py`, `xbrl.py` and `prices.py`. Do not run the script against
the network: the reviewer does that.

## Git workflow

Branch `perf/parallel-sec`. Commit `perf(ingest): parallel SEC downloads with a shared rate limit and retry`, ending
with the line `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Do not push.

## Steps

### Step 1: Thread-safe start-time limiter and retry in `sec.py`

Replace `_last` and `_get_json` with:
```python
MIN_INTERVAL = 0.125  # seconds between request starts, shared by all threads (SEC allows 10/s)
RETRIES = 3
_lock = threading.Lock()
_next = [0.0]


def _slot() -> None:
    """Block until this thread may start a request (global cap of 1 / MIN_INTERVAL starts per second)."""
    with _lock:
        now = time.monotonic()
        start = max(now, _next[0])
        _next[0] = start + MIN_INTERVAL
    if start > now:
        time.sleep(start - now)


def _get_json(url: str, user_agent: str) -> dict:
    """GET a JSON URL with the SEC User-Agent; rate-limited across threads; retries transient network errors."""
    if not user_agent.strip():
        raise ValueError("SEC_USER_AGENT is not set (SEC requires a contact, e.g. 'MAID research you@example.com')")
    req = urllib.request.Request(url, headers={"User-Agent": user_agent, "Accept-Encoding": "identity"})
    for attempt in range(RETRIES):
        _slot()
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or attempt == RETRIES - 1:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt == RETRIES - 1:
                raise
        time.sleep(2 ** attempt)
```
Add `import threading` and `import urllib.error`. `HTTPError` is a subclass of `URLError`, so keep the `HTTPError`
clause first. A 404 must raise immediately.

**Verify**: `python -c "import maid.sec as s; print(s.MIN_INTERVAL, s.RETRIES)"` → `0.125 3`

### Step 2: Parallel SIC scan in `select_universe.py`

Replace the `for i, cik in enumerate(cands, 1):` loop with a `concurrent.futures.ThreadPoolExecutor(max_workers=8)`
over the CIKs. Each task runs the same `sic_cache.get_or_compute(...)` call and returns `(cik, info_or_None)`.
Collect results with `as_completed`. Rules:
- If the error is a `ValueError` containing `SEC_USER_AGENT`, re-raise it in the main thread. Cancel the remaining
  futures (`ex.shutdown(cancel_futures=True)`), and the script exits 1 through the existing `except ValueError`.
- Any other `ValueError` or `OSError` prints the same `warning: submissions failed for CIK ...` line, and that CIK
  is skipped.
- Print progress every 250 completed: `SIC scan {done}/{len(cands)}, {len(in_sec)} in sector`.
- After the loop, print `SIC scan done: {len(in_sec)} in sector, {failed} failed` to stderr.
- Keep `in_sec` in a deterministic order: after the loop, rebuild it as
  `{cik: in_sec[cik] for cik in cands if cik in in_sec}`.

Add a module constant `WORKERS = 8`. Do not change anything after the SIC scan.

**Verify**: `env -u SEC_USER_AGENT python scripts/select_universe.py tech; echo $?` → an `ERROR SEC_USER_AGENT ...`
line and `1`, with no traceback. (`tickers()` is fetched first, so it fails before the pool starts. That is fine.)

### Step 3: Tests in `tests/test_sec.py` (offline)

Keep the autouse no-network fixture. Add:
1. `test_rate_limit_shared_across_threads`: monkeypatch `sec.MIN_INTERVAL` to `0.02` and reset `sec._next[0] = 0.0`.
   Monkeypatch `urllib.request.urlopen` with a fake that records `time.monotonic()` and returns an object usable as a
   context manager whose `.read()` returns `b'{"ok": 1}'`. Call `_get_json` 10 times from 5 threads. Assert all
   results are `{"ok": 1}` and that consecutive sorted start times differ by ≥ 0.018.
2. `test_retry_then_success`: a fake urlopen raises `urllib.error.URLError("dns")` once, then succeeds. Monkeypatch
   `time.sleep` to a no-op. The result is `{"ok": 1}` after 2 calls.
3. `test_404_not_retried`: a fake raises `urllib.error.HTTPError(url, 404, "nf", None, None)`. `pytest.raises(urllib.error.HTTPError)`,
   and the fake is called exactly once.

These tests set their own `urlopen` fake through `monkeypatch`. The fake must override the autouse guard: request
the guard fixture first, then call `monkeypatch.setattr` again inside the test.

**Verify**: `pytest -q tests/test_sec.py` → all pass; `pytest -q` → all pass; `ruff check .` → clean.

## Done criteria

- [ ] `pytest -q` and `ruff check .` pass.
- [ ] `git diff --name-only 138373d` lists only the 3 in-scope files.
- [ ] `grep -n "max_workers" scripts/select_universe.py` → one hit using `WORKERS`.

## STOP conditions

- The excerpts don't match the live files.
- A test needs real network.
- The change appears to require editing `cache.py` or `universe.py`.

## Maintenance notes

- `MIN_INTERVAL` is the global cap. Never lower it below `0.1` (SEC limit 10/s).
- If the SEC starts returning 403 or 429 under load, reduce `WORKERS`. The cap protects request starts, not bandwidth.
