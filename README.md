# MAID: Multi-Agent Investment Decision-making

LLM agents turn qualitative company information into scores; a deterministic MCDM engine
computes weights and rankings. Exploratory prototype. See `docs/SCOPE.md` and `docs/research/`.

## Setup
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # add DEEPSEEK_API_KEY
pytest
ruff check .
```

## Layout
- `src/maid/graph.py`: LangGraph pipeline skeleton (stub nodes, human-review interrupt)
- `src/maid/state.py`: shared state and score schema
- `src/maid/cache.py`: on-disk cache for API/data calls
- `src/maid/config.py`: settings from environment
- `src/maid/mcdm/`: MCDM engine: weights (entropy, CRITIC, equal) and ranking (TOPSIS, SAW)
- `scripts/weight_stability.py`: spike #6 simulation (see `docs/research/weight-stability-results.md`)
- `docs/architecture/`: architecture overview, per-block docs, design decisions
