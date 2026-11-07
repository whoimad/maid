# Plan 031: LLM scorer: OpenAI-compatible client, rubrics, K cached samples with quote check and truncation guard, pilot script

> **Executor instructions**: Follow this plan step by step. Run every verification command and confirm the expected
> result before moving to the next step. If anything in the "STOP conditions" section occurs, stop and report — do
> not improvise. The reviewer maintains `plans/README.md`; do not edit it.
>
> **Drift check (run first)**: `git diff --stat <BASE>..HEAD -- src/maid/config.py src/maid/cache.py src/maid/state.py src/maid/scoring.py src/maid/tenk.py .env.example docs/architecture/decisions.md CLAUDE.md`
> where `<BASE>` is `e185bcd`. Expected: no output.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: LOW (new modules; one additive config change; no network in tests; the graph is not touched)
- **Depends on**: plan 030 (10-K text v2, provides `tenk.criterion_text` and `tenk.EXTRACTOR_VERSION`)
- **Category**: direction
- **Planned at**: commit `e185bcd` on branch `integration/prototype` (plan 030 merged), 2026-11-03

## Why this matters

MAID (Multi-Agent Investment Decision-making) has LLM agents **score** qualitative criteria and a deterministic MCDM
engine compute weights and ranks. **LLMs never rank.** Every LLM score is an integer 1–9 with a verbatim quote from the
source text as evidence, and is reviewable by a human. So far only a deterministic stub scorer exists
(`src/maid/scoring.py`). This plan builds the real scorer for three criteria on consumer-staples 10-Ks (pricing power,
strategy clarity, capital allocation) and a pilot script that scores the first 10 companies at K = 5 so the owner can
read the results before anything else runs. The graph is **not** wired here (next plan).

Owner decisions (fixed, do not change): one OpenAI-compatible client; a local model via **Ollama** for development and
as an older-cutoff comparison, **DeepSeek** for the main run; both models get the **same** text slice
(`tenk.criterion_text`). Ollama's default context is 4k tokens on GPUs under 24 GiB and its OpenAI-compatible API
cannot change it, so a long prompt would be **silently truncated**. The scorer must detect that and refuse.

## Current state

- `src/maid/config.py` (whole file):

```python
"""Settings loaded from environment (.env). See .env.example."""
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    api_key: str = field(default_factory=lambda: os.getenv("DEEPSEEK_API_KEY", ""), repr=False)
    base_url: str = field(
        default_factory=lambda: os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    )
    model: str = field(default_factory=lambda: os.getenv("DEEPSEEK_MODEL", "deepseek-flash"))
    decision_date: str = field(default_factory=lambda: os.getenv("DECISION_DATE", "2025-03-31"))
    cache_dir: Path = field(default_factory=lambda: Path(os.getenv("MAID_CACHE_DIR", "data/cache")))
    sec_user_agent: str = field(default_factory=lambda: os.getenv("SEC_USER_AGENT", ""))


def get_settings() -> Settings:
    return Settings()
```

  `tests/test_config_cache.py::test_settings_read_env_at_call_time` sets `DEEPSEEK_MODEL` and expects
  `get_settings().model` to follow it. That must keep passing.

- `src/maid/cache.py`: `DiskCache(root)`, `DiskCache.llm_key(model, prompt_version, *parts) -> str` (sha256 of the
  JSON of all parts), `cache.get_or_compute(key, fn)`: returns the cached JSON value, else calls `fn()`, writes the
  result atomically and returns it. **If `fn()` raises, nothing is written.** The plan relies on that.
- `src/maid/state.py`: keep unchanged.

```python
class CriterionScore(BaseModel):
    company: str  # anonymized label, e.g. "Company A"
    criterion: str
    score: int = Field(ge=1, le=9)
    evidence: str  # quote that must appear in the source filing
```

- `src/maid/scoring.py`: `StubScorer.score(self, company, criterion, filing, k) -> list[CriterionScore]` and
  `aggregate(samples) -> (median CriterionScore, std)`. The new scorer has the **same `score` signature** so the next
  plan can swap it in. Do not modify `scoring.py`.
- `src/maid/tenk.py` (from plan 030): `criterion_text(sections, criterion) -> {"text", "source", "truncated",
  "split_found", "tokens"}`, `approx_tokens(text) = (len(text) + 3) // 4`, `EXTRACTOR_VERSION = "2"`.
- `src/maid/real_data.py`: `load_filings(decision_date, sector="tech", client=None) -> (label -> ticker,
  label -> {"1", "1a", "7"} anonymized text, label -> info)`. Staples labels are `"Company 001"`..`"Company 061"`.
  It needs `SEC_USER_AGENT` and network (cached on disk after the first run).
- The `openai` package (`openai>=1.40` in `pyproject.toml`; 3.42.1 installed) is already a dependency. Use
  `from openai import OpenAI`; `client.chat.completions.create(model=..., messages=..., temperature=..., seed=...,
  response_format={"type": "json_object"}, max_tokens=...)`. A response has `.choices[0].message.content`,
  `.usage.prompt_tokens`, `.usage.completion_tokens` and `.model`.
- Conventions (CLAUDE.md): short module docstrings, one-line function docstrings, compact code, line length 110.
  Tests in `tests/test_<area>.py`, plain `assert`, **no network**. Never print API keys. Cache keys must include model
  and prompt version (decision D7). Exemplar for style: `src/maid/scoring.py`, `tests/test_tenk.py`.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Tests | `/home/imad/maid/.venv/bin/python -m pytest -q` (from your worktree root) | all pass |
| Lint | `/home/imad/maid/.venv/bin/ruff check .` | `All checks passed!` |
| Script help | `/home/imad/maid/.venv/bin/python scripts/score_pilot.py --help` | usage text, exit 0 |

If `python -c "import maid; print(maid.__file__)"` does not point into your worktree, prefix commands with
`env PYTHONPATH=src`. Run each command on its own (no `cd ... &&` chains).

## Steps

### Step 1: settings with `LLM_*` overrides

In `config.py`, make the three LLM fields read `LLM_*` first and fall back to `DEEPSEEK_*`:

```python
    api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY") or os.getenv("DEEPSEEK_API_KEY", ""),
                         repr=False)
    base_url: str = field(default_factory=lambda: os.getenv("LLM_BASE_URL")
                          or os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"))
    model: str = field(default_factory=lambda: os.getenv("LLM_MODEL") or os.getenv("DEEPSEEK_MODEL", "deepseek-flash"))
```

Append to `.env.example`:

```
# Optional: any OpenAI-compatible server overrides the DEEPSEEK_* values, e.g. a local Ollama model
# LLM_BASE_URL=http://localhost:11434/v1
# LLM_MODEL=maid-qwen7b-32k
# LLM_API_KEY=ollama
```

Tests (`tests/test_config_cache.py`): `LLM_MODEL` set → it wins over `DEEPSEEK_MODEL`; `LLM_MODEL` deleted
(`monkeypatch.delenv("LLM_MODEL", raising=False)`) → `DEEPSEEK_MODEL` is used. Add `monkeypatch.delenv("LLM_MODEL",
raising=False)` at the top of the existing `test_settings_read_env_at_call_time`, so a developer's own `.env` cannot
break it. That is the only change to that test.

Verify: `pytest -q tests/test_config_cache.py` passes.

### Step 2: `src/maid/rubrics.py`

```python
"""Scoring prompts: one rubric per qualitative criterion (1-9, quoted evidence). Bump PROMPT_VERSION on any change."""

PROMPT_VERSION = "1"
SYSTEM = (
    "You are a careful equity analyst. The company is anonymized as {label}; other names may also be replaced. "
    "Use only the excerpt below, never outside knowledge, and do not try to identify the company. "
    "Score one criterion as an integer from 1 to 9 using the rubric. Quote, word for word, one passage of at most "
    "300 characters from the excerpt that best supports the score. "
    'Answer with a json object only: {{"score": <1-9>, "evidence": "<verbatim quote>", "reasoning": "<at most 60 words>"}}.'
)
RUBRICS = {
    "pricing_power": (
        "Pricing power: can the company raise prices or improve mix without losing volume, and pass cost inflation "
        "through? 1-3: price cuts or heavy promotion to defend volume, input costs not passed through, share lost to "
        "private label or competitors. 4-6: mixed; some pricing gains offset by volume declines or margin pressure. "
        "7-9: price/mix gains with stable or growing volume, costs explicitly passed through, margins held or expanded."
    ),
    "strategy_clarity": (
        "Strategy clarity: does management state specific priorities and how it will reach them? 1-3: boilerplate, no "
        "identifiable priorities. 4-6: priorities named but vague, no targets or timeframes. 7-9: specific priorities "
        "with measurable targets and timeframes, tied to resources or investments."
    ),
    "capital_allocation": (
        "Capital allocation: is there a clear, disciplined policy for using cash? 1-3: no stated policy, a dividend "
        "cut, or acquisitions with no stated criteria. 4-6: a policy is described but without order or targets. 7-9: "
        "explicit ordered priorities (for example reinvestment, dividend, buybacks, M&A), a leverage target, return "
        "criteria, and a consistent record."
    ),
}


def build_messages(criterion: str, label: str, text: str) -> list[dict]:
    """Chat messages for one score: system prompt with the rubric, then the excerpt."""
    if criterion not in RUBRICS:
        raise ValueError(f"unknown criterion: {criterion!r}")
    system = SYSTEM.format(label=label) + "\n\nRubric. " + RUBRICS[criterion]
    return [{"role": "system", "content": system}, {"role": "user", "content": f"Excerpt from the 10-K of {label}:\n\n{text}"}]
```

Copy the strings exactly (the reviewer has checked them). Wrap lines to ≤ 110 characters if ruff complains, without
changing the text. Note the doubled braces `{{ }}` in `SYSTEM` (it goes through `str.format`).

Tests (`tests/test_llm.py`): for each of the three criteria, `build_messages(c, "Company 007", "Some text.")` has two
messages, the system one contains `"json"`, `"Company 007"` and the criterion's rubric, and the user one ends with
`"Some text."`; an unknown criterion raises `ValueError`.

### Step 3: `src/maid/llm.py`

```python
"""LLM scorer: K sampled 1-9 scores per company and criterion, each with a verified verbatim quote. It never ranks."""
import hashlib
import json
import math

from maid.cache import DiskCache
from maid.rubrics import PROMPT_VERSION, build_messages
from maid.state import CriterionScore
from maid.tenk import EXTRACTOR_VERSION, approx_tokens

QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", " ": " "})
MIN_PROMPT_RATIO = 0.7  # reported prompt tokens below this share of the estimate means the server truncated


class ScoringError(RuntimeError):
    """Too few valid samples for one company and criterion."""


class ContextTruncated(RuntimeError):
    """The server read fewer prompt tokens than were sent (for example Ollama's 4k default context)."""


def normalize(s: str) -> str:
    """Collapse whitespace and map curly quotes, dashes and non-breaking spaces to plain ASCII."""
    return " ".join(s.translate(QUOTES).split())


def quote_in_text(quote: str, text: str) -> bool:
    """True when the normalized quote is a non-empty substring of the normalized text."""
    q = normalize(quote)
    return bool(q) and q in normalize(text)


def parse_reply(content: str, text: str) -> tuple[int, str, str]:
    """(score, evidence, reasoning) from a JSON reply; ValueError when invalid or the quote is not in text."""
```

`parse_reply` rules, each failing case raises `ValueError` with a short reason:
- `json.loads(content)` must give a dict (strip a leading/trailing ```` ``` ````/```` ```json ```` fence first);
- `score` must be an `int` (a `bool` is not allowed; an integral float like `7.0` is accepted as 7) with 1 ≤ score ≤ 9;
- `evidence` must be a non-empty `str` of at most 300 characters after `normalize`, and `quote_in_text(evidence, text)`;
- `reasoning` is optional; a non-`str` becomes `""`; keep at most 600 characters.

```python
class LLMScorer:
    """Scores with any OpenAI-compatible client; every reply is cached on disk and logged in self.log."""

    def __init__(self, client, model: str, cache: DiskCache, temperature: float = 0.7, max_attempts: int = 3,
                 seed: int = 0, max_tokens: int = 400):
        ...
        self.log: list[dict] = []

    def score(self, company: str, criterion: str, filing: str, k: int) -> list[CriterionScore]:
        """Return the valid samples among k (up to max_attempts tries each); ScoringError if fewer than ceil(k/2)."""
```

Behaviour of `score` (implement exactly):
1. `messages = build_messages(criterion, company, filing)`; `digest = sha256(json.dumps(messages).encode()).hexdigest()`.
2. For `sample` in `range(k)`, for `attempt` in `range(max_attempts)`:
   - `seed = self.seed + 1000 * sample + attempt`;
   - `key = DiskCache.llm_key(self.model, PROMPT_VERSION, EXTRACTOR_VERSION, criterion, company, digest, sample,
     attempt, self.temperature)`;
   - `reply = self.cache.get_or_compute(key, lambda: self._call(messages, seed))` (bind `seed` correctly, e.g. a
     default argument);
   - try `parse_reply(reply["content"], filing)`. On success append a `CriterionScore(company=..., criterion=...,
     score=..., evidence=<the evidence string as returned>)`, log, and stop trying this sample. On `ValueError` log
     the reason and try the next attempt.
   - each log record: `{"company", "criterion", "sample", "attempt", "ok": bool, "error": str | None,
     "model": reply["model"], "prompt_tokens", "completion_tokens", "score": int | None, "reasoning": str}`.
3. A sample with no valid attempt is dropped. If `len(valid) < math.ceil(k / 2)`, raise `ScoringError` with company,
   criterion and the counts. Otherwise return the valid samples (sample order).

`_call(messages, seed) -> dict` (the only place that talks to the network):

```python
        r = self.client.chat.completions.create(model=self.model, messages=messages, temperature=self.temperature,
                                                seed=seed, max_tokens=self.max_tokens,
                                                response_format={"type": "json_object"})
        usage = getattr(r, "usage", None)
        sent = approx_tokens("".join(m["content"] for m in messages))
        if usage is None or usage.prompt_tokens < MIN_PROMPT_RATIO * sent:
            raise ContextTruncated(f"server read {getattr(usage, 'prompt_tokens', None)} prompt tokens, sent ~{sent}; "
                                   "raise the context size (Ollama: Modelfile PARAMETER num_ctx 32768)")
        return {"content": r.choices[0].message.content or "", "model": r.model,
                "prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens}
```

Because `_call` raises inside `get_or_compute`, a truncated reply is **never cached**. `ContextTruncated` and network
errors propagate out of `score` unchanged (they are not retried as attempts).

`make_client(settings) -> OpenAI`: `OpenAI(base_url=settings.base_url, api_key=settings.api_key or "none",
timeout=600)`. Raise `ValueError("no LLM API key: set LLM_API_KEY or DEEPSEEK_API_KEY")` when `settings.api_key`
is empty **and** `settings.base_url` does not start with `http://localhost` or `http://127.0.0.1`. Never put the
key in any message or log.

Tests (`tests/test_llm.py`, no network). Use a fake client:

```python
from types import SimpleNamespace as NS

class FakeClient:
    """Returns queued reply contents; records every create() call."""
    def __init__(self, contents, prompt_tokens=None, model="fake-1"):
        self.contents, self.calls, self.pt, self.model = list(contents), [], prompt_tokens, model
        self.chat = NS(completions=NS(create=self.create))

    def create(self, **kw):
        self.calls.append(kw)
        sent = sum(len(m["content"]) for m in kw["messages"]) // 4
        return NS(choices=[NS(message=NS(content=self.contents.pop(0)))], model=self.model,
                  usage=NS(prompt_tokens=self.pt if self.pt is not None else sent, completion_tokens=20))
```

with `TEXT = "We raised prices 5% while volume grew 2%. Costs were passed through to customers."` and
`ok = json.dumps({"score": 8, "evidence": "We raised prices 5% while volume grew 2%.", "reasoning": "r"})`. Write at
least these tests:
1. k = 3 valid replies → 3 `CriterionScore` with score 8; 3 calls; seeds `0, 1000, 2000`; every call has
   `response_format == {"type": "json_object"}`; `scorer.log` has 3 records with `ok` true and `model == "fake-1"`.
2. First reply `"not json"`, then valid, for k = 1 → 1 score; 2 calls with seeds `0` and `1`; the first log record
   has `ok` false.
3. A quote not in the text, a score of 10, a score of `true`, and an empty evidence each make `parse_reply` raise
   `ValueError`; `"7.0"`-style integral float (`{"score": 7.0, ...}`) is accepted.
4. Curly vs straight quotes and extra whitespace: `quote_in_text("We ’raised’  prices", "We 'raised' prices now")`
   is true.
5. k = 4, max_attempts = 1, replies: 1 valid and 3 invalid → `ScoringError` (1 < 2); 2 valid and 2 invalid → 2
   scores returned.
6. Truncation: `FakeClient([ok], prompt_tokens=5)` with a long text (e.g. `TEXT * 200`) → `ContextTruncated`, and
   the cache directory (`tmp_path`) holds no `*.json` file.
7. Cache: score once with a fresh `DiskCache(tmp_path)`, then a second `LLMScorer` with a `FakeClient([])` (empty
   queue) and the same cache returns the same scores with 0 calls. Changing `temperature` makes the second scorer
   call the client again.
8. `make_client` with an empty key and a non-local base URL raises `ValueError`; with `http://localhost:11434/v1`
   it returns an object without raising (no request is made by construction). Build the settings with
   `dataclasses.replace(get_settings(), api_key="", base_url=...)`.

Verify: `pytest -q tests/test_llm.py` passes; `ruff check .` clean.

### Step 4: `scripts/score_pilot.py`

```
"""Score the first N companies of a universe with the LLM scorer (K samples) and write a local review table.

Usage: python scripts/score_pilot.py [--sector staples] [--n 10] [--k 5] [--out data/pilot]
Needs SEC_USER_AGENT (cached 10-Ks) and an LLM endpoint (LLM_* or DEEPSEEK_* settings). Writes only under --out.
"""
```

- Arguments: `--sector` (choices `sorted(SECTORS)`, default `staples`), `--n` (default 10), `--k` (default 5),
  `--out` (default `data/pilot`; `data/` is gitignored), `--temperature` (default 0.7).
- `labels, texts, _ = load_filings(settings.decision_date, a.sector)`; the companies are `sorted(labels)[:a.n]` (a
  fixed rule: the first N labels).
- `scorer = LLMScorer(make_client(settings), settings.model, DiskCache(settings.cache_dir / "llm"),
  temperature=a.temperature)`.
- For each company and each of `("pricing_power", "strategy_clarity", "capital_allocation")`:
  `ct = criterion_text(texts[c], crit)`; `samples = scorer.score(c, crit, ct["text"], a.k)`; then
  `med, std = aggregate(samples)` (from `maid.scoring`). Catch `ScoringError` per cell (record it, continue); let
  `ContextTruncated` stop the script with exit code 2 and a one-line message on stderr.
- Write `<out>/pilot.md`: a header line with sector, n, k, temperature, `PROMPT_VERSION`, `EXTRACTOR_VERSION`, the
  configured model and the set of `model` values seen in replies; then one Markdown table row per cell:
  `| label | ticker | criterion | median | std | valid/k | failed attempts | prompt tokens | source | truncated | quote |`
  (quote: the **first valid sample's** evidence, `|` replaced by `/`, cut to 300 chars;
  `ERROR: <reason>` in the median column for a `ScoringError`). Last lines: total prompt tokens and total
  completion tokens over `scorer.log`.
- Write `<out>/pilot_log.jsonl`: one JSON line per `scorer.log` record.
- Print to stdout only a short summary (cells ok, cells failed, total tokens, output path). Never print the API key.
- The ticker column is for the owner's local review only; tickers never go into a prompt (`build_messages` only gets
  the label).

Verify: `python scripts/score_pilot.py --help` prints the usage and exits 0. **Do not run it without `--help`**
(network and a model are needed; the reviewer runs it).

### Step 5: docs

- `docs/architecture/decisions.md`: append, in the format of the existing entries (look at D14 and D19):

```
## D20. Scorer models: a local Ollama model for development and the older-cutoff check, DeepSeek for the main run
- **Alternatives:** DeepSeek only; a hosted older model; different text per model (each model's full context).
- **Why:** a local model costs nothing while prompts and rubrics are developed, and an open-weight model released
  before the 2025-03-31 decision date gives the older-cutoff comparison (D3, D14). One OpenAI-compatible client serves
  both (`LLM_*` settings fall back to `DEEPSEEK_*`). Both models read the same per-criterion slice of the 10-K
  (`tenk.criterion_text`, 24k-token budget), so differences come from the model, not the input.
- **Cost:** a 7–8B model at 4-bit is weaker than DeepSeek, so disagreement mixes capability with leakage; Ollama's
  default 4k context would silently truncate prompts, so the scorer refuses any reply whose reported prompt tokens are
  below 70% of the estimate (`ContextTruncated`) and such replies are never cached.
- **Status:** decided 2026-11-03 (extends D14). Pilot: 10 companies, K = 5, reviewed by the owner before all 61 run.
```

- `CLAUDE.md` "Layout": add three lines after the `scoring.py` line, matching the existing style:
  `- \`src/maid/llm.py\`: LLM scorer (OpenAI-compatible, cached K samples, quote check, truncation guard)`,
  `- \`src/maid/rubrics.py\`: scoring prompts and rubrics (PROMPT_VERSION)`, and after the `fetch_filings.py` line
  `- \`scripts/score_pilot.py\`: score the first N companies with the LLM scorer; writes a local review table`.

Verify: `pytest -q tests/test_docs.py` passes.

### Step 6: gates and commit

Full `pytest -q` passes; `ruff check .` clean. Commit (conventional commit, e.g. `feat(llm): OpenAI-compatible scorer
with rubrics, quote check, truncation guard and pilot script`, body `Refs plan 031`, ending with the line
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`).

## Done criteria

- `pytest -q`: all pass, at least 14 new tests; `ruff check .` clean.
- `git diff --stat <BASE>..HEAD` lists only: `src/maid/config.py`, `src/maid/llm.py`, `src/maid/rubrics.py`,
  `scripts/score_pilot.py`, `tests/test_llm.py`, `tests/test_config_cache.py`, `.env.example`,
  `docs/architecture/decisions.md`, `CLAUDE.md`.
- `grep -n "LLMs never rank\|never ranks" src/maid/llm.py` → at least one hit (the module docstring).
- `grep -rn "api_key" scripts/score_pilot.py` → no `print` of it.

## Out of scope (do not touch)

- `src/maid/graph.py`, `src/maid/scoring.py`, `src/maid/state.py`, `src/maid/tenk.py`, `src/maid/real_data.py`, the
  GUI, the MCDM engine. Wiring the scorer into the graph is the next plan.
- Any network call in tests; running the pilot; adding dependencies.

## STOP conditions

- Drift check shows changes.
- `openai` is not importable, or `chat.completions.create` has no `seed` / `response_format` parameter.
- An existing test fails and the cause is not the one-line `delenv` addition in Step 1.
- Any step needs a file outside the done-criteria list.

## Maintenance notes

- Any change to `SYSTEM`, `RUBRICS` or `build_messages` must bump `PROMPT_VERSION` (the message digest in the cache key
  also changes, so stale replies are never reused even if someone forgets).
- The graph's citation check (`scoring.evidence_is_quoted`) is an exact substring test. When the next plan wires this
  scorer in, it must use `llm.quote_in_text` instead, or valid quotes with curly apostrophes fail review.
- The DeepSeek `deepseek-flash` alias is re-pointed from time to time (it moved on 2026-10-17); `pilot.md` records the
  `model` field of every reply so runs stay attributable.
- Local Ollama setup (owner): `ollama pull qwen2.5:7b`, then a Modelfile with `FROM qwen2.5:7b` and
  `PARAMETER num_ctx 32768`, `ollama create maid-qwen7b-32k -f Modelfile`, and set `LLM_BASE_URL=http://localhost:11434/v1`,
  `LLM_MODEL=maid-qwen7b-32k`, `LLM_API_KEY=ollama`. `ollama ps` shows the allocated context.
