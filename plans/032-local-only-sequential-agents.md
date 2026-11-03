# Plan 032: Local models only, agents run as sequential jobs (D21); prompt v2 quote length; docs state the limitation

> **Executor instructions**: Follow this plan step by step. Run every verification command and confirm the expected
> result before moving to the next step. If anything in the "STOP conditions" section occurs, stop and report — do
> not improvise. The reviewer maintains `plans/README.md`; do not edit it.
>
> **Drift check (run first)**: `git diff --stat <BASE>..HEAD -- src docs README.md CLAUDE.md .env.example scripts tests`
> where `<BASE>` is the commit the reviewer told you to reset to. Expected: no output.

## Status

- **Priority**: P1
- **Effort**: M (mostly docs; small code change)
- **Risk**: LOW
- **Depends on**: plan 031 (merged)
- **Category**: direction / docs
- **Planned at**: commit `c3a8a25` on branch `integration/prototype`, 2026-11-03

## Why this matters

MAID (Multi-Agent Investment Decision-making): LLM agents **score** qualitative criteria of companies from their 10-K
text, and a deterministic MCDM engine computes weights and ranks. **LLMs never rank.**

Owner decision (2026-11-03, final): **no paid API, local models only.** One 7B model (Qwen2.5 7B, 4-bit, 32k
context, served by Ollama) already fills the laptop GPU (RTX 2070 Max-Q, 8 GB; the loaded model takes 6.4 GB). So
the agents cannot run in parallel. The architecture stays **conceptually multi-agent** (each criterion agent has its
own prompt, rubric, input slice and output contract), but the agents run **as sequential jobs**: one agent finishes
all its companies, then the next starts. This limitation must be stated clearly everywhere the docs promise parallel
fan-out or the DeepSeek API.

Measured (2026-11-03 smoke test, 1 company, K = 1, local model): about 10–20 s per call; 4 of 6 attempts were
rejected because the model quoted more than the allowed 300 characters. So this plan also relaxes the quote rule
(prompt version 2).

A useful consequence for the docs: Qwen2.5 was released on **2024-09-19** (Qwen2.5 GitHub README:
"2024.09.19: We released the Qwen2.5 series", https://github.com/QwenLM/Qwen2.5). That is before the decision date
2025-03-31, so the model's training data cannot contain anything from the evaluation window (2025-04-01 to
2026-03-31). The remaining look-ahead-style risk is **recognition**: the model may identify an anonymized company from
older knowledge.

## Current state

- `src/maid/config.py`, LLM fields (from plan 031):

```python
    api_key: str = field(
        default_factory=lambda: os.getenv("LLM_API_KEY") or os.getenv("DEEPSEEK_API_KEY", ""), repr=False
    )
    base_url: str = field(
        default_factory=lambda: os.getenv("LLM_BASE_URL")
        or os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    )
    model: str = field(
        default_factory=lambda: os.getenv("LLM_MODEL") or os.getenv("DEEPSEEK_MODEL", "deepseek-flash")
    )
```

- `tests/test_config_cache.py`: `test_settings_read_env_at_call_time` (sets `DEEPSEEK_MODEL`, has a
  `monkeypatch.delenv("LLM_MODEL", raising=False)` line) and two plan-031 tests about `LLM_MODEL` vs `DEEPSEEK_MODEL`
  fallback. Read the file to find them.
- `src/maid/llm.py` (end of file):

```python
def make_client(settings) -> OpenAI:
    """OpenAI client for the configured endpoint; a key is required unless the server is local."""
    local = settings.base_url.startswith(("http://localhost", "http://127.0.0.1"))
    if not settings.api_key and not local:
        raise ValueError("no LLM API key: set LLM_API_KEY or DEEPSEEK_API_KEY")
    return OpenAI(base_url=settings.base_url, api_key=settings.api_key or "none", timeout=600)
```

  and in `parse_reply`: `if len(normalize(ev)) > 300: raise ValueError("evidence longer than 300 characters")`.
  `tests/test_llm.py::test_make_client` tests the key rule.
- `src/maid/rubrics.py`: `PROMPT_VERSION = "1"`; `SYSTEM` contains the sentence
  `"Score one criterion as an integer from 1 to 9 using the rubric. Quote, word for word, one passage of at most "`
  `"300 characters from the excerpt that best supports the score. "`.
- `.env.example` has `DEEPSEEK_API_KEY=`, `DEEPSEEK_BASE_URL=...`, `DEEPSEEK_MODEL=deepseek-flash` lines and a
  commented `LLM_*` block.
- Docs that mention DeepSeek or parallel fan-out (all are changed in Step 4): `docs/architecture/decisions.md` (D3,
  D14, D20), `docs/SCOPE.md` §3, §8, §9, `docs/architecture/graph.md` ("Target design: parallel scoring with Send",
  "Why LangGraph", "Known limitations"), `docs/architecture/overview.md` (status table rows Config and Qualitative
  scorer agents, the two C4 diagrams, the section 4 sequence diagram and the paragraph under it),
  `docs/INTERVIEW.md` (status paragraph, container diagram, Q2, Q8), `docs/architecture/uncertainty.md` (look-ahead
  row), `docs/WALKTHROUGH.md` (Stop 3 item 7, Stop 4 items 3–4), `README.md` (setup comment),
  `docs/research/model-cutoff.md` (top).
- Conventions (CLAUDE.md): compact code, one-line docstrings, line length 110, plain-`assert` tests, no network in
  tests, never print API keys. Docs style: short sentences, plain English, no marketing words. `tests/test_docs.py`
  checks relative links in docs.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Tests | `env PYTHONPATH=src /home/imad/maid/.venv/bin/python -m pytest -q` | all pass |
| Lint | `/home/imad/maid/.venv/bin/ruff check .` | `All checks passed!` |
| Grep | `grep -rn -i "deepseek" README.md CLAUDE.md .env.example src scripts docs/architecture/overview.md docs/architecture/graph.md docs/architecture/uncertainty.md docs/WALKTHROUGH.md` | see Step 5 |

Run each command on its own (no `cd ... &&` chains).

## Steps

### Step 1: config defaults are local; no DeepSeek names in code

`config.py` LLM fields become:

```python
    api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", "ollama"), repr=False)
    base_url: str = field(default_factory=lambda: os.getenv("LLM_BASE_URL", "http://localhost:11434/v1"))
    model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "qwen2.5-32k"))
```

(`qwen2.5-32k` is the owner's Ollama model: `qwen2.5:7b` with `PARAMETER num_ctx 32768`.)

`tests/test_config_cache.py`: change `test_settings_read_env_at_call_time` to set `LLM_MODEL` (values `m-test`,
`m-other`) and delete its `delenv` line; replace the two plan-031 fallback tests with one test: with `LLM_MODEL`,
`LLM_BASE_URL` and `LLM_API_KEY` deleted (`monkeypatch.delenv(..., raising=False)`), `get_settings()` gives
`model == "qwen2.5-32k"` and `base_url == "http://localhost:11434/v1"`. **Note:** `load_dotenv()` runs at import, so a
developer `.env` may set `LLM_*`; the `delenv` calls make the test independent of it.

`.env.example`: remove the three `DEEPSEEK_*` lines and the commented block; add (uncommented):

```
# Local models only (decision D21): any OpenAI-compatible server on this machine, e.g. Ollama
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=qwen2.5-32k
LLM_API_KEY=ollama
```

Keep `DECISION_DATE` and `SEC_USER_AGENT` lines unchanged.

### Step 2: the client refuses non-local servers

Replace `make_client` with:

```python
LOCAL_HOSTS = ("http://localhost", "http://127.0.0.1")


def make_client(settings) -> OpenAI:
    """OpenAI-compatible client for a local server only (D21: no paid API)."""
    if not settings.base_url.startswith(LOCAL_HOSTS):
        raise ValueError(f"local models only (D21): LLM_BASE_URL must start with {' or '.join(LOCAL_HOSTS)}")
    return OpenAI(base_url=settings.base_url, api_key=settings.api_key or "ollama", timeout=600)
```

(`LOCAL_HOSTS` goes with the other module constants at the top.) Update `test_make_client`: a base URL of
`https://api.example.com` raises `ValueError`; `http://localhost:11434/v1` and `http://127.0.0.1:11434/v1` return a
client. Update the `score_pilot.py` docstring line `Needs ... (LLM_* or DEEPSEEK_* settings)` to
`Needs SEC_USER_AGENT (cached 10-Ks) and a local LLM server (LLM_* settings, default Ollama on localhost).`

### Step 3: prompt version 2 (quote length)

- `rubrics.py`: `PROMPT_VERSION = "2"`; in `SYSTEM`, replace `"one passage of at most "` `"300 characters"` with
  `"a single sentence of at most 400 characters"`, so the sentence reads: "Quote, word for word, a single sentence of
  at most 400 characters from the excerpt that best supports the score." Change nothing else in the prompt.
- `llm.py`: add `MAX_QUOTE = 400` next to `MIN_PROMPT_RATIO`; `parse_reply` uses it:
  `if len(normalize(ev)) > MAX_QUOTE: raise ValueError(f"evidence longer than {MAX_QUOTE} characters")`.
- Tests: adjust any test that relied on 300 (search `300` in `tests/test_llm.py`); add one: a 350-character quote that
  is in the text is accepted, a 401-character one is rejected; `"400 characters" in SYSTEM`.

Verify: `pytest -q tests/test_llm.py tests/test_config_cache.py` passes.

### Step 4: docs

Use exactly this wording where given; elsewhere match the surrounding style.

**4a. `docs/architecture/decisions.md`.**
- D3: append a bullet `- **Changed 2026-11-03:** with D21 the scorer is Qwen2.5 7B, released 2024-09-19, before the
  decision date, so its training data cannot contain evaluation-window events. The remaining risk is recognition: the
  model may identify an anonymized company from older knowledge (probed later).`
- D14: change its `- **Status:**` line to `- **Status:** superseded 2026-11-03 by D21 (local models only).`
- D20: change its `- **Status:**` line to `- **Status:** superseded 2026-11-03 by D21 (no DeepSeek main run).`
- Append D21:

```
## D21. Local models only; agents run as sequential jobs
- **Alternatives:** a paid API (DeepSeek) for the main run (D14, D20); parallel requests to the local server
  (Ollama `OLLAMA_NUM_PARALLEL`) or a LangGraph `Send` fan-out per company and criterion.
- **Why:** the owner will not pay for an API for an exploratory project. One local 7B model at 4-bit with a 32k
  context (Qwen2.5 7B via Ollama) already fills the 8 GB laptop GPU (6.4 GB allocated), so parallel requests would
  only queue or run out of memory. Qwen2.5 was released on 2024-09-19 (Qwen2.5 GitHub README), before the 2025-03-31
  decision date, which removes outcome leakage from the model's training data (D3).
- **How it works:** MAID stays conceptually multi-agent: each criterion agent (pricing power, strategy clarity,
  capital allocation) has its own rubric, input slice of the 10-K and output contract (score 1–9 with a verbatim
  quote). The agents run one after another as jobs: one agent scores every company, then the next agent starts. Every
  reply is cached on disk, so an interrupted job resumes where it stopped. The scorer refuses non-local servers.
- **Cost:** no parallelism. Measured on 2026-11-03: about 10–20 s per call, so the 10-company pilot (K = 5) takes
  about an hour and all 61 companies take about 4–5 hours. A 7B model is weaker than a hosted model, so scores are
  noisier and the human review carries more weight. Reported as a limitation of the project.
- **Status:** decided 2026-11-03 by the owner.
```

**4b. `docs/SCOPE.md`.**
- §3: replace the bullet that starts "DeepSeek publishes no knowledge cutoff" (3 lines, through "once its availability
  and cutoff are verified.") with: `- The scorer is a local open-weight model, Qwen2.5 7B, released 2024-09-19, before
  the decision date (decision D21 in architecture/decisions.md). Its training data cannot contain evaluation-window
  events; the remaining risk is that it recognizes an anonymized company from older knowledge.`
- §8: replace `- Budget: Claude Pro plan; DeepSeek API for the pipeline. Cache everything, small test universe first.`
  with `- Budget: no paid API. Local models only (Ollama on an 8 GB laptop GPU), so agents run as sequential jobs,
  not in parallel (D21). Cache everything, small pilot first.`
- §9: change the item `- [ ] Verify the older-model ablation candidate ...` to
  `- [x] Older-model candidate: Qwen2.5 7B (released 2024-09-19) is now the only scorer model (D21)`.

**4c. `docs/architecture/graph.md`.**
- Rename the heading `## Target design: parallel scoring with Send` to `## Not used: parallel scoring with Send`
  and replace its first paragraph (`**Planned, not implemented.** Nothing in this section works today. Per ...`)
  with: `**Dropped 2026-11-03 (D21).** One local 7B model fills the 8 GB GPU, so parallel branches would only queue.
  The criterion agents run as sequential jobs instead. This section is kept to show what parallel scoring would look
  like with a hosted API. Per \`docs/research/llm-agents-finance.md\` (section 4, item 5), that design is:`
  Keep the diagram and the bullets below it unchanged.
- In "Why LangGraph": replace `LangGraph pays off with the
interrupt, the checkpointing and the planned fan-out.` with `LangGraph pays off with the interrupt and the
checkpointing (the parallel fan-out was dropped, D21).`
- In "Known limitations": replace `- No fan-out: scoring is a single node.` with `- Sequential agents (D21): local
  models only, one model on an 8 GB GPU, so criterion agents run one after another, never in parallel.`

**4d. `docs/architecture/overview.md`.**
- Status table, Config row: replace its Code cell with `` `config.py` `Settings`: `LLM_BASE_URL` (default
  `http://localhost:11434/v1`), `LLM_MODEL` (default `qwen2.5-32k`), `LLM_API_KEY`, `DECISION_DATE` (default
  2025-03-31), `MAID_CACHE_DIR` (default `data/cache`), `SEC_USER_AGENT` `` (one cell, no line break).
- Qualitative scorer agents row, Status cell: replace `DeepSeek scorer planned` with `local LLM scorer built
  (\`llm.py\`, Ollama, sequential jobs, D21); not yet wired into the graph`.
- Both C4 diagrams: replace `DS[DeepSeek API]` with `DS[Local LLM<br/>Ollama, Qwen2.5 7B]`; in the context diagram
  change the edge label `scoring prompts, anonymized - planned` to `scoring prompts, anonymized, one at a time`.
  In the sentence under it, replace `sends only anonymized
prompts to the LLM provider` with `sends only anonymized
prompts to a local model on the same machine (no paid API, D21)`.
- Section 4 sequence diagram: replace `G->>S: fan out per company x criterion (planned: Send)` with
  `G->>S: criterion agents run one after another (sequential jobs, D21)`. In the paragraph below, replace
  `The interrupt sits after the join, not inside parallel branches, so the human reviews everything once.` with
  `The interrupt sits after all scoring agents have finished, so the human reviews everything once.` and replace
  `Today the graph is linear (no fan-out yet).` with `The graph is linear by design: no parallel fan-out (D21).`

**4e. `docs/INTERVIEW.md`.**
- Status paragraph: replace `the model's training
cutoff is unpublished and likely later` (whatever the exact line break) with `the scorer is a local Qwen2.5 7B
released before the decision date, so the remaining risk is recognition`, and `real SEC/yfinance ingest, the DeepSeek
scorer, fan-out and the backtest are planned, not built` with `real SEC ingest, the backtests and the local LLM
scorer are built; wiring the scorer into the graph is next; there is no parallel fan-out (D21)`.
- Container diagram: `DS[DeepSeek API]` → `DS[Local LLM<br/>Ollama, Qwen2.5 7B]`.
- Q2: replace the two sentences from `What cannot be prevented: DeepSeek` to `planned, not built.` with: `The scorer
is Qwen2.5 7B, released on 2024-09-19, so its training data predates the decision date and cannot contain
evaluation-window events. What remains is recognition: the model may identify an anonymized company from older
knowledge, which a recognition probe measures.`
- Q8: replace `the planned fan-out (not built)` with `the checkpointing (the parallel fan-out was dropped, D21)` and
  make the sentence read naturally (`... LangGraph pays off with the interrupt and the checkpointing ...`).
- Add a new question at the end of "Likely questions", numbered after the last one:

```
### N. Is it still multi-agent if the agents run one after another?
Yes, conceptually. Each criterion agent has its own rubric, its own slice of the 10-K and its own output contract
(score 1-9 with a verbatim quote), and the human review and the MCDM engine are separate steps. What is missing is
parallel execution: the project uses local models only (no paid API), and one 7B model already fills the 8 GB laptop
GPU, so the agents run as sequential jobs. The cost is time (about 10-20 s per call, hours for a full run), not
design. With a hosted API the same agents could run in parallel (graph.md keeps that design). See
[D21](architecture/decisions.md).
```

**4f. `docs/architecture/uncertainty.md`**, look-ahead row: replace `The model may know post-2025-03-31 text; the
DeepSeek cutoff is unpublished and likely later` with `The scorer (Qwen2.5 7B, released 2024-09-19) predates the
decision date, so outcome leakage from training data is excluded; the model may still recognize a company from
older knowledge (D21)`.

**4g. `docs/WALKTHROUGH.md`.** Stop 3 item 7: `The \`Send\` fan-out section of graph.md is a target design, not
code.` → `The \`Send\` fan-out section of graph.md is a design that was dropped: agents run sequentially (D21).`
Stop 4 item 3: `The real DeepSeek
   scorer is planned, not built.` → `The real scorer (\`llm.py\`, a local model) is built but not yet wired into
   the graph.` Stop 4 item 4: `D14 (model choice, \`deepseek-flash\`)` → `D21 (local models only, sequential
   agents)`.

**4h. `README.md`**: `cp .env.example .env   # add DEEPSEEK_API_KEY` → `cp .env.example .env   # local LLM via
Ollama; no API key needed (D21)`.

**4i. `docs/research/model-cutoff.md`**: insert after the title line a blockquote:
`> Superseded 2026-11-03: MAID uses local models only (decision D21). This note is kept as research history.`

**4j. `CLAUDE.md`** "Rules (non-negotiable)": add a bullet after the "LLMs never rank" bullet:
`- **Local models only (D21).** No paid API. One local model (Ollama) fills the GPU, so agents run as sequential
  jobs, never in parallel; the scorer refuses non-local servers.`

Verify: `pytest -q tests/test_docs.py` passes.

### Step 5: gates and commit

- The Grep command from the table prints **no lines** (DeepSeek may still appear in `decisions.md`, `SCOPE.md`
  history, `INTERVIEW.md` only if inside an unchanged sentence about history, and `docs/research/`).
- Full `pytest -q` passes; `ruff check .` clean.
- Commit: `feat(llm): local models only, sequential agents (D21); prompt v2 quote length` with body `Refs plan 032`
  and the line `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Done criteria

- `pytest -q` all pass; `ruff check .` clean; the Grep prints nothing.
- `grep -n "^## D21" docs/architecture/decisions.md` → one line; `grep -c "superseded 2026-11-03" docs/architecture/decisions.md` → `2`.
- `grep -n 'PROMPT_VERSION = "2"' src/maid/rubrics.py` → one line.
- `git diff --stat <BASE>..HEAD` lists only: `src/maid/config.py`, `src/maid/llm.py`, `src/maid/rubrics.py`,
  `scripts/score_pilot.py`, `tests/test_config_cache.py`, `tests/test_llm.py`, `.env.example`, `README.md`,
  `CLAUDE.md`, `docs/SCOPE.md`, `docs/INTERVIEW.md`, `docs/WALKTHROUGH.md`, `docs/architecture/decisions.md`,
  `docs/architecture/graph.md`, `docs/architecture/overview.md`, `docs/architecture/uncertainty.md`,
  `docs/research/model-cutoff.md`.

## Out of scope

- `src/maid/graph.py` and the GUI (wiring the scorer as sequential criterion agents is the next plan).
- Any other doc text not listed in Step 4, even if stale. `docs/research/llm-agents-finance.md` stays unchanged.
- Never read or print `.env`.

## STOP conditions

- Drift check shows changes.
- A quoted "current" sentence in Step 4 is not found (after allowing for different line breaks): report which one;
  do not rewrite nearby text to compensate.
- An existing test outside `test_config_cache.py` / `test_llm.py` fails.

## Maintenance notes

- Any change to the prompt or the quote limit bumps `PROMPT_VERSION` (cache keys include it and the message digest).
- If a hosted API is ever reconsidered, D21 must be revised first; `make_client` enforces local-only on purpose.
- The run-time numbers in D21 come from one smoke test; update them after the pilot.
