# Plan 002: Settings read the environment at call time, and the disk cache survives crashes and versions its LLM keys

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat c094993..HEAD -- src/maid/config.py src/maid/cache.py tests/test_scaffold.py tests/test_config_cache.py`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: plans/001-ci-lint-claude-md.md (soft: for `ruff check .`; if 001 is not done, skip the lint commands)
- **Category**: bug
- **Planned at**: commit `c094993`, 2026-11-02

## Why this matters

Two small foundations that the upcoming LLM and ingest code will lean on are subtly wrong:

1. `Settings` field defaults are evaluated **once, when `maid.config` is first imported**, because
   `os.getenv(...)` is a plain dataclass default (a class attribute). `get_settings()` therefore never sees
   environment changes made after import, so tests cannot override settings and a script that sets
   `DEEPSEEK_MODEL` after importing `maid` silently uses the old value. Verified: after import,
   `os.environ["DEEPSEEK_MODEL"]="x"; get_settings().model` still returns `deepseek-flash`.
2. `DiskCache.get_or_compute` writes the JSON file directly. If the process dies mid-write (Ctrl-C during a
   long run is likely), a truncated file remains and `json.loads` raises on **every** later run for that key.
   Separately, design decision D7 states "cache keys must include model and prompt version", but nothing in
   the cache API supports or encourages that, so a prompt change will silently reuse stale paid answers.

## Current state

- `src/maid/config.py` (entire file):
  ```python
  """Settings loaded from environment (.env). See .env.example."""
  import os
  from dataclasses import dataclass
  from pathlib import Path

  from dotenv import load_dotenv

  load_dotenv()


  @dataclass(frozen=True)
  class Settings:
      api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
      base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
      model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-flash")
      decision_date: str = os.getenv("DECISION_DATE", "2024-12-31")
      cache_dir: Path = Path(os.getenv("MAID_CACHE_DIR", "data/cache"))


  def get_settings() -> Settings:
      return Settings()
  ```
- `src/maid/cache.py` (entire file):
  ```python
  """Tiny on-disk JSON cache keyed by a hash, so API/data calls are never paid for twice."""
  import hashlib
  import json
  from pathlib import Path
  from typing import Any, Callable


  class DiskCache:
      def __init__(self, root: Path):
          self.root = Path(root)
          self.root.mkdir(parents=True, exist_ok=True)

      @staticmethod
      def key(*parts: Any) -> str:
          blob = json.dumps(parts, sort_keys=True, default=str).encode()
          return hashlib.sha256(blob).hexdigest()

      def get_or_compute(self, key: str, fn: Callable[[], Any]) -> Any:
          path = self.root / f"{key}.json"
          if path.exists():
              return json.loads(path.read_text())
          value = fn()
          path.write_text(json.dumps(value))
          return value
  ```
- Neither module has callers yet besides `tests/test_scaffold.py`:
  ```python
  def test_cache_computes_once(tmp_path):
      cache = DiskCache(tmp_path)
      calls = []
      key = cache.key("a", 1)
      for _ in range(2):
          cache.get_or_compute(key, lambda: calls.append(1) or {"x": 1})
      assert len(calls) == 1
  ```
  This test must keep passing unchanged.
- Style: tiny modules, one-line docstrings, stdlib only. Tests use pytest's `tmp_path` and `monkeypatch`, plain `assert`.
- `.env` holds a real API key on the developer's machine. Never print, log, or commit its contents.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Install | `pip install -e ".[dev]"` (inside `.venv`) | exit 0 |
| Tests | `pytest -q` | all pass |
| New tests only | `pytest -q tests/test_config_cache.py` | all pass |
| Lint (if plan 001 done) | `ruff check .` | `All checks passed!` |

## Scope

**In scope**:
- `src/maid/config.py`
- `src/maid/cache.py`
- `tests/test_config_cache.py` (create)

**Out of scope**:
- `tests/test_scaffold.py` — must pass unchanged.
- `.env`, `.env.example` — no new variables in this plan.
- Adding cache expiry/TTL, locking, or a cache library — not needed for a single-user prototype.
- Changing the default model name (separate concern; tracked in `docs/research/model-cutoff.md`).

## Git workflow

- Base: `feat/weight-stability-spike` if not yet merged into `main`, else `main`.
- Branch: `fix/config-cache`.
- Commit e.g. `fix: read settings at call time; atomic, versioned disk cache`.
- Do NOT push or open a PR unless instructed.

## Steps

### Step 1: Write failing tests first

Create `tests/test_config_cache.py` with:

1. `test_settings_read_env_at_call_time(monkeypatch)`: `monkeypatch.setenv("DEEPSEEK_MODEL", "m-test")`, then
   `from maid.config import get_settings`; assert `get_settings().model == "m-test"`. Then
   `monkeypatch.setenv("DEEPSEEK_MODEL", "m-other")` and assert `get_settings().model == "m-other"`.
2. `test_settings_cache_dir_is_path(monkeypatch, tmp_path)`: set `MAID_CACHE_DIR` to `str(tmp_path)`; assert
   `get_settings().cache_dir == tmp_path`.
3. `test_corrupt_cache_file_is_recomputed(tmp_path)`: create `DiskCache(tmp_path)`, `k = cache.key("x")`,
   write `(tmp_path / f"{k}.json").write_text('{"trunc')`; call `cache.get_or_compute(k, lambda: {"ok": 1})`;
   assert the result is `{"ok": 1}` and the file now parses to `{"ok": 1}`.
4. `test_interrupted_write_leaves_no_file(tmp_path, monkeypatch)`: simulate a crash halfway through writing.
   Monkeypatch `pathlib.Path.write_text` with a fake that writes only the first half of the text with
   the real method and then raises `KeyboardInterrupt`:
   ```python
   import pathlib
   real = pathlib.Path.write_text
   def half_then_crash(self, data, *a, **kw):
       real(self, data[: len(data) // 2], *a, **kw)
       raise KeyboardInterrupt
   monkeypatch.setattr(pathlib.Path, "write_text", half_then_crash)
   with pytest.raises(KeyboardInterrupt):
       cache.get_or_compute(k, lambda: {"long": "x" * 100})
   monkeypatch.undo()
   ```
   Then assert `list(tmp_path.glob("*.json")) == []` and `list(tmp_path.glob("*.tmp")) == []`, and that a
   second `get_or_compute(k, lambda: {"ok": 1})` returns `{"ok": 1}`.
   (Note: a non-serializable value is NOT a valid test here — today's code already raises before writing.)
5. `test_llm_key_depends_on_model_and_prompt_version()`: assert
   `DiskCache.llm_key("m1", "v1", "p") != DiskCache.llm_key("m2", "v1", "p")`,
   `!= DiskCache.llm_key("m1", "v2", "p")`, and `DiskCache.llm_key("m1", "v1", "p") == DiskCache.llm_key("m1", "v1", "p")`.

**Verify**: `pytest -q tests/test_config_cache.py` → tests 1, 3, 4, 5 FAIL (2 may pass). This confirms the bugs.

### Step 2: Fix `Settings`

Change every field to use `field(default_factory=...)` so `os.getenv` runs at instantiation, e.g.:

```python
from dataclasses import dataclass, field

@dataclass(frozen=True)
class Settings:
    api_key: str = field(default_factory=lambda: os.getenv("DEEPSEEK_API_KEY", ""), repr=False)
    base_url: str = field(default_factory=lambda: os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"))
    ...
    cache_dir: Path = field(default_factory=lambda: Path(os.getenv("MAID_CACHE_DIR", "data/cache")))
```

Note `repr=False` on `api_key` so printing settings never shows the key. Keep `load_dotenv()` at module level
(dotenv does not override variables already set in the environment, so monkeypatched values still win).
Keep `get_settings()` signature.

**Verify**: `pytest -q tests/test_config_cache.py -k settings` → 2 passed.

### Step 3: Make cache writes atomic and tolerate corrupt files

In `get_or_compute`:
- Read: wrap `json.loads(path.read_text())` in `try/except json.JSONDecodeError` → fall through to recompute.
- Write: serialize first (`blob = json.dumps(value)` — if this raises, nothing is written), then write to a temp
  file in the same directory and `os.replace` it onto `path`:
  ```python
  tmp = path.with_suffix(f".{os.getpid()}.tmp")
  try:
      tmp.write_text(blob)
      os.replace(tmp, path)
  finally:
      tmp.unlink(missing_ok=True)  # no-op after a successful replace
  ```
  `finally` (not `except Exception`) is required so the temp file is also removed on `KeyboardInterrupt`.

**Verify**: `pytest -q tests/test_config_cache.py -k "corrupt or interrupted"` → 2 passed.

### Step 4: Add the versioned LLM key helper

Add to `DiskCache`:

```python
@staticmethod
def llm_key(model: str, prompt_version: str, *parts: Any) -> str:
    """Key for LLM calls: model and prompt version are mandatory (design decision D7)."""
    return DiskCache.key("llm", model, prompt_version, *parts)
```

Do not change `key()` behavior (existing cache files must stay valid).

**Verify**: `pytest -q` → all tests pass (7 existing + 5 new = 12).

## Test plan

Covered in Step 1: env read at call time, Path type, corrupt-file recovery, no partial file on failed write,
key sensitivity to model and prompt version. Pattern: model after `tests/test_scaffold.py::test_cache_computes_once`
(plain functions, `tmp_path`).

## Done criteria

- [ ] `pytest -q` → 12 passed (or 7 + the number of new tests, all passing)
- [ ] `grep -n "default_factory" src/maid/config.py` → 5 matches
- [ ] `grep -n "os.replace" src/maid/cache.py` → 1 match
- [ ] `grep -n "def llm_key" src/maid/cache.py` → 1 match
- [ ] `ruff check .` passes (if plan 001 landed)
- [ ] `git status` shows only the 3 in-scope files changed/added
- [ ] `plans/README.md` status row updated

## STOP conditions

- `tests/test_scaffold.py` fails after your change and the fix would require editing that test.
- You find any other module already calling `Settings(...)` with positional args or relying on class-attribute
  access like `Settings.model` (search: `grep -rn "Settings" src tests scripts`). Report instead of adapting.
- Step 1 tests 1/3/4/5 already pass before your fix → the code drifted; stop.

## Maintenance notes

- Future LLM scorer code must use `DiskCache.llm_key(settings.model, PROMPT_VERSION, ...)`; reviewers should reject
  LLM calls cached via plain `key()`. Bump `PROMPT_VERSION` whenever a rubric or prompt changes.
- `model` here is the alias (`deepseek-flash`), which DeepSeek re-points; once the dated model version is pinned
  (see `docs/research/model-cutoff.md` recommendation 2), pass the dated version into `llm_key`.
- Temp-file naming uses the PID; concurrent writers of the same key in one process are not a concern today.
