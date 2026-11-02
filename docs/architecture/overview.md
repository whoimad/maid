# Architecture overview

Goal: rank companies on mixed quantitative and qualitative criteria **without letting an LLM make the
ranking decision**. Diagrams are Mermaid and render on GitHub. Per-block detail lives in the other
files in this folder; the reasoning behind each choice is in [decisions.md](decisions.md).

## 1. The one idea to remember
LLMs are good at reading text and bad at being auditable decision makers. MCDM methods are the opposite.
So each does only what it is good at:

| Does | LLM agents | MCDM engine |
|---|---|---|
| Reads filings, extracts evidence | yes | no |
| Converts text to a 1-9 score | yes | no |
| Computes weights | no | yes (entropy, CRITIC) |
| Ranks companies | no | yes (TOPSIS, SAW) |
| Reproducible given the same inputs | no (sampled) | yes |

## 2. System flow

```mermaid
flowchart LR
    A[SEC EDGAR<br/>10-K text + XBRL] --> I[Ingest]
    B[yfinance<br/>prices] --> I
    I -->|ratios from XBRL| Q[Quantitative criteria]
    I -->|filing text, names anonymized| S[Qualitative scorer agents<br/>one per criterion, K samples]
    S --> H{{Human checkpoint<br/>review scores + evidence}}
    H --> M[MCDM engine<br/>weights + ranking]
    Q --> M
    M --> R[Robustness<br/>bootstrap / Monte Carlo]
    R --> O[Report<br/>rank intervals + caveats]
    O --> E[Backtest vs 2025 returns]
```

Quantitative criteria bypass the LLM entirely: numbers come from XBRL, which removes a whole class of
hallucination risk. Only genuinely textual criteria (e.g. strategy quality, risk disclosure) use agents.

## 3. Time boundary (look-ahead control)

```mermaid
flowchart LR
    subgraph before[" Information the system may use "]
      D1[FY2024 10-K filings]
      D2[Prices up to 2024-12-31]
    end
    X((Decision date<br/>2024-12-31))
    subgraph after[" Evaluation only "]
      E1[2025 returns]
    end
    before --> X --> after
```

The pipeline never sees the right-hand side; it is used once, afterwards, to grade the ranking.
Known leak: the LLM itself may have been trained on later text. See decisions D3.

## 4. Human-in-the-loop (LangGraph interrupt)

```mermaid
sequenceDiagram
    participant G as Graph
    participant S as Scorer agents
    participant H as Human
    participant M as MCDM engine
    G->>S: fan out (one per criterion)
    S-->>G: scores + evidence quotes
    G->>H: interrupt(scores) , state saved by checkpointer
    H-->>G: resume(overrides + reasons)
    G->>M: validated scores
    M-->>G: weights, ranking
```

The interrupt sits after the join, not inside parallel branches, so the human reviews everything once
and the checkpointer can resume across restarts. Overrides are logged with a reason; they can later be
used to measure where the LLM disagrees with the human.

## 5. Evaluation

```mermaid
flowchart TB
    R[Ranking from pipeline] --> B1[vs 2025 return / risk-adjusted]
    R --> B2[vs equal-weight and SAW baselines]
    R --> B3[Method agreement<br/>TOPSIS vs SAW, entropy vs CRITIC]
    S[K repeated LLM runs] --> B4[Score stability]
    N[Anonymized vs named prompts] --> B5[Look-ahead probe]
```

With about 12 companies the backtest is noisy; the project reports correlations and intervals, not
"accuracy".

## Blocks
- [mcdm.md](mcdm.md): weights and ranking (implemented)
- Ingest, scorer agents, human checkpoint, robustness, report: documented as each is built
