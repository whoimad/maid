# Block: Robustness (`src/maid/mcdm/robustness.py`)

**Responsibility:** report rank intervals and rank acceptability instead of point ranks, under three separate sources:
two of weight uncertainty (bootstrap, Dirichlet) and one of LLM score noise. Pure numpy, no LLM, no I/O. Wired into
the graph's `robustness` node, which runs it on the demo decision matrix (see [graph.md](graph.md)).

```mermaid
flowchart LR
    X[Decision matrix X] --> B[Bootstrap resamples of rows]
    F[weight_fn] --> B
    B --> BW[Weight draws]
    BW -->|rank original X| RI1[RankIntervals: bootstrap]
    X --> P[Point weights w = weight_fn X]
    P --> D[Dirichlet draws around w]
    D -->|rank original X| RI2[RankIntervals: dirichlet]
    X --> RI1
    X --> RI2
    S[K samples per LLM score] --> SN[Bootstrap median per cell]
    X --> SN
    SN -->|recompute weights, rank each draw| RI3[RankIntervals: score_noise]
```

## The three sources

| Source | Uncertainty it represents | Parameter | Caveat |
|---|---|---|---|
| Bootstrap | Weight-estimation noise: "what if we had observed a slightly different set of companies" | `n_draws` | With n around 12 it understates uncertainty, because it only resamples companies already observed |
| Dirichlet | Weight-choice uncertainty around the point weights (`E[w'] = w`, `Var(w'_j) = w_j(1-w_j)/(concentration+1)`) | `n_draws`, `concentration` (placeholder 100) | Spread is set by hand; zero weights are floored to 1e-6 |
| Score noise | LLM sampling noise of the aggregated (median-of-K) scores | `n_draws`, K (`settings.k`) | Small K understates the spread; K=1 gives zero width (no information, not certainty); overridden cells are held fixed; cells are resampled independently |

The three are reported separately, not mixed. Bootstrap and Dirichlet rank the original `X`; score noise ranks each perturbed
`X` with weights recomputed on it. See D16 in [decisions.md](decisions.md).

## How to read the output
- Ranks: 1 = best; ties share the better rank.
- `lo`-`hi` is a 90% rank interval (5th to 95th percentile, always ranks that actually occurred).
- `acceptability[i, 0]` is the share of draws in which alternative `i` is ranked first;
  `acceptability[i, r-1]` is the share where it gets rank `r`.
- `point` is the rank under the point weights. Arrays are indexed by row order of `X`.

## Open questions
- Calibrate `concentration`: pick it so Dirichlet weight spread matches the bootstrap spread observed on the real matrix (or the spike's TV at n=12), instead of the placeholder 100.
- Should the report combine the sources (e.g. Dirichlet around each bootstrap draw), or show them side by side?
- Report format: rank intervals per company plus rank-1 acceptability; decide the threshold under which two companies are called "not distinguishable".

## Known limitations
Tests are synthetic only. Min-max-based rankers make ranks depend on sample extremes. Score noise treats the 1-9 scores as interval data (as the rest of the engine does) and assumes cells are
independent.
