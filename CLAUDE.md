# MAID: agent guide

MAID (Multi-Agent Investment Decision-making): LLM agents score qualitative company information;
a deterministic MCDM engine computes weights and ranks. Exploratory prototype. See `docs/SCOPE.md`.

## Commands
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q                          # tests
ruff check .                       # lint (CI runs both)
python scripts/weight_stability.py # spike #6 simulation
```

## Layout
- `src/maid/graph.py`: LangGraph pipeline skeleton (stub nodes, human-review interrupt)
- `src/maid/state.py`: shared state and score schema
- `src/maid/cache.py`: on-disk cache for API/data calls
- `src/maid/config.py`: settings from environment
- `src/maid/mcdm/`: MCDM engine: weights (entropy, CRITIC, equal) and ranking (TOPSIS, SAW)
- `scripts/weight_stability.py`: spike #6 simulation (see `docs/research/weight-stability-results.md`)
- `docs/architecture/`: architecture overview, per-block docs, design decisions

## Rules (non-negotiable)
- **LLMs never rank.** Agents extract and score; a deterministic MCDM engine computes weights and
  ranks. Every LLM score carries cited evidence and is reviewable by the human. (SCOPE section 2)
- Decision date is 2024-12-31: agents see only information available on or before it. Company names
  are anonymized ("Company A", ...) in scoring prompts. (SCOPE section 3)
- The MCDM engine (`src/maid/mcdm/`) is pure functions: no LLM, no I/O, everything unit tested.
  All criteria must be benefit-type (higher is better).
- Cache everything on disk (D7); cache keys must include model and prompt version.
- Never commit `.env`, and never print API keys.

## Conventions
- Decision matrix is `X` with shape `(n_alternatives, m_criteria)`; uppercase matrix names are intentional.
- Short module docstrings, one-line function docstrings, compact code. Do not reformat existing code.
- Tests live in `tests/test_<area>.py`, use plain `assert` and seeded `np.random.default_rng(<int>)`.
  No network access in tests.

## Workflow
- Issue per component, branch per issue (`feat/`, `fix/`, `chore/`, `docs/`), small PRs into `main`.
- Conventional commits; put `Refs #N` / `Closes #N` in the body.
- CI (pytest + ruff) must be green before merge.

## Docs to read before changing X
- `docs/architecture/decisions.md` (D1-D7) before changing any design.
- `docs/architecture/mcdm.md` before touching `src/maid/mcdm/`.
- `docs/research/README.md`: research notes were made from abstracts only; check claims marked
  UNVERIFIED before relying on them.
