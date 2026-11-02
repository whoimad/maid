# Spike #6: entropy vs CRITIC weight stability at small n

Reproduce: `python scripts/weight_stability.py` (seed 42). **Synthetic data only**: this shows the
mechanism under one generator, not how real companies behave.

## Method
Per trial: random correlated criteria (m=7), a 5000-row synthetic population gives "reference" weights.
Draw n alternatives, recompute weights from the sample only, then compare:
- **TV**: total-variation distance between sample and reference weights (0 = identical, 1 = disjoint).
- **tau**: Kendall tau between rankings of the same sample using sample vs reference weights
  (1 = identical order). This isolates the effect of weight noise on the ranking.
300 trials per n. Two regimes: Gaussian criteria, and log-normal (skewed, closer to financial ratios).
Entropy is computed with min-max pre-normalization unless marked *sum-entropy* (textbook column-sum normalization, positive data only, so log-normal regime only).

## Results
### Gaussian criteria

| n | entropy TV | CRITIC TV | entropy→TOPSIS tau | entropy→SAW tau | CRITIC→TOPSIS tau | CRITIC→SAW tau |
|---|---|---|---|---|---|---|
| 8 | 0.140 | 0.061 | 0.629 | 0.791 | 0.698 | 0.875 |
| 12 | 0.137 | 0.056 | 0.622 | 0.777 | 0.738 | 0.886 |
| 20 | 0.131 | 0.052 | 0.633 | 0.804 | 0.766 | 0.898 |
| 50 | 0.125 | 0.046 | 0.643 | 0.804 | 0.810 | 0.915 |
| 200 | 0.109 | 0.038 | 0.683 | 0.831 | 0.843 | 0.932 |

### Log-normal (skewed) criteria

| n | entropy TV | CRITIC TV | entropy→TOPSIS tau | entropy→SAW tau | CRITIC→TOPSIS tau | CRITIC→SAW tau | sum-entropy TV | sum-entropy→TOPSIS tau | sum-entropy→SAW tau |
|---|---|---|---|---|---|---|---|---|---|
| 8 | 0.133 | 0.093 | 0.785 | 0.800 | 0.737 | 0.836 | 0.186 | 0.749 | 0.747 |
| 12 | 0.128 | 0.090 | 0.771 | 0.814 | 0.778 | 0.853 | 0.158 | 0.740 | 0.779 |
| 20 | 0.107 | 0.092 | 0.801 | 0.856 | 0.789 | 0.865 | 0.124 | 0.786 | 0.841 |
| 50 | 0.082 | 0.092 | 0.835 | 0.889 | 0.797 | 0.869 | 0.087 | 0.837 | 0.888 |
| 200 | 0.050 | 0.097 | 0.895 | 0.932 | 0.796 | 0.870 | 0.046 | 0.905 | 0.939 |

## What the numbers say (and don't)
1. **At n=12 weight noise changes rankings noticeably**: tau ranges roughly 0.62 to 0.89 depending on
   the weighting/ranking pair. Weights should not be treated as exact.
2. **CRITIC was closer to its reference than min-max entropy at n=12 in both regimes** (TV 0.056 vs 0.137
   Gaussian; 0.090 vs 0.128 skewed).
3. **Under skew, CRITIC stops improving** (TV about 0.09 from n=8 to n=200) while min-max entropy keeps
   improving (0.133 to 0.050). Hypothesis, not tested: Pearson correlation inside CRITIC is outlier-sensitive.
4. **SAW rankings were more stable than TOPSIS** under the same weight noise in this setup.
5. **Weights barely converge as n grows** (e.g. min-max entropy TV 0.140 at n=8, 0.109 at n=200, Gaussian).
   Untested hypothesis: part of this is not sampling noise but min-max normalization depending on
   sample extremes, so a sample's weights differ systematically from the population's.
6. **Sum-entropy vs min-max entropy (log-normal only)**: TV at n=12 is 0.158 (sum) vs 0.128 (min-max), and at
   n=200 it is 0.046 vs 0.050; tau at n=12 is 0.740/0.779 (sum, TOPSIS/SAW) vs 0.771/0.814 (min-max), and at
   n=200 0.905/0.939 vs 0.895/0.932. Sum-entropy TV falls from 0.158 to 0.046, min-max from 0.128 to 0.050, but
   sum-entropy starts higher and ends about the same, so hypothesis 5 is not supported in this run. The
   Gaussian regime, where hypothesis 5 was first noted, cannot be tested because sum-entropy needs positive data.

## Limits
Reference weights come from the same estimator on a big sample, not a ground truth. Real criteria
are neither Gaussian nor log-normal. One generator, one seed.

## Consequences for the design
- Keep the bootstrap / Monte Carlo weight perturbation and rank intervals already in the scope.
- Keep equal weights and SAW as baselines.
- Run both entropy and CRITIC and report where they disagree.
- Follow-up: test hypothesis 5 (normalization effect) before claiming anything about it.
