# MAID: Multi-Agent Investment Decision-making

LLM agents turn qualitative company information into scores; a deterministic MCDM engine
computes weights and rankings. Exploratory prototype. See `docs/SCOPE.md` and `docs/research/`.

New here? Follow [docs/WALKTHROUGH.md](docs/WALKTHROUGH.md).

## Setup
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # add DEEPSEEK_API_KEY
pytest
ruff check .
```

## Run the demo
Runs the whole pipeline on a synthetic dataset with a stub scorer (no network, no API key):
```bash
python -m maid.demo
python -m maid.demo --weighting entropy --json out.json
```

## Run the GUI
```bash
pip install -e ".[gui]"
streamlit run app/streamlit_app.py
```

## Layout
- `src/maid/graph.py`: LangGraph pipeline; runs the demo pipeline end to end (synthetic data, stub scorer), with a human-review interrupt
- `src/maid/demo.py`: runs the graph and auto-resumes the review (`python -m maid.demo`)
- `src/maid/demo_data.py`: deterministic synthetic companies, numbers and filing excerpts
- `src/maid/scoring.py`: stub scorer, K-sample aggregation, evidence check
- `src/maid/matrix.py`: builds the decision matrix, applies overrides, Kendall tau
- `src/maid/gui_data.py`: pure row/DOT helpers that shape pipeline state for the GUI
- `app/streamlit_app.py`: thin Streamlit UI over the demo pipeline
- `src/maid/state.py`: shared state and score schema
- `src/maid/cache.py`: on-disk cache for API/data calls
- `src/maid/config.py`: settings from environment
- `src/maid/mcdm/`: MCDM engine: weights (entropy, CRITIC, equal) and ranking (TOPSIS, SAW)
- `scripts/weight_stability.py`: spike #6 simulation (see `docs/research/weight-stability-results.md`)
- `docs/architecture/`: architecture overview, per-block docs, design decisions
