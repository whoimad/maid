# MCDM noise at small n (~12 alternatives, ~6-8 criteria)

Status: desk research, 2026-11-02. Web search returned abstracts/metadata mostly; full texts were
NOT read. Each claim is tagged [V] (seen in a search result/abstract), [S] (secondary source only),
or UNVERIFIED (from background knowledge, no source checked). Nothing here replaces simulation on
our own data.

## 1. Key findings

### Objective weighting (entropy, CRITIC, SD, MEREC)
- CRITIC weights by contrast intensity (std. dev.) and conflict (pairwise correlation) of criteria;
  uses only the decision matrix. [V, S1] Entropy weights criteria more when values vary more across
  alternatives. [V, S2 summary]
- Entropy was reported as more weight-sensitive than CRITIC in two case studies: a 16-dataset
  engineering study (entropy weights more sensitive to the data modifications tested; SAW less
  sensitive than other rankers) [V, S2] and one ARAS customer-prioritisation case
  (75% vs 57% sensitivity, as reported by search summary) [S, S3-URL listed under S2 search; exact
  paper UNVERIFIED]. Both are single-case/applied; they do not establish a general rule.
- No source found that directly tests entropy vs CRITIC as a function of sample size. The claim
  "weights are noisy at n~12" is therefore UNVERIFIED in the literature; it is plausible because
  all three methods estimate dispersion/correlation from n rows (a 6-8 criteria correlation matrix
  from 12 points is very noisy -- statistical reasoning, UNVERIFIED as MCDM-specific citation).
  Our own bootstrap (resample alternatives) is the right test; this is also an open item in SCOPE.md.
- Entropy hypersensitivity to the matrix and redistribution of weight among correlated criteria is
  argued in a critique found via search [S, S2-search; specific paper not identified -> UNVERIFIED].
- MEREC: weights from change in overall performance when each criterion is removed; original paper
  validated on illustrative example, comparison with other objective methods, and a simulation on
  normal data. [V, S4] Independent small-n critiques not found.
- Structural point (own reasoning, UNVERIFIED as citation): entropy and SD weights reward criteria
  with spread, so a criterion with one outlier company can dominate; CRITIC also penalises
  correlated criteria, which matters when several tech ratios are collinear.

### Ranking methods
- Normalization changes rankings. A TOPSIS/VIKOR reanalysis reports mean Spearman between rankings
  under weight changes of 0.969 (logarithmic), 0.942 (vector), 0.958 (linear) normalisation [V, S5];
  that is a single paper's data, treat as indicative. Another paper shows TOPSIS vector vs min-max
  normalisation flips some close alternatives [V, S6 search summary]. A Baltic J. Modern Computing
  study compared normalisations with Kendall tau [S, S7]; findings not read.
- Rank reversal (adding/removing an alternative reorders others): documented for PROMETHEE I/II;
  Verly & De Smet (2013) estimate frequency on artificial data and give avoidance conditions [V, S8];
  Dejaegere & De Smet (2022) report reversals only occur between alternatives with close net flows,
  and propose a stricter indifference threshold [V, S9]. A 2024 Omega paper studies how preference
  function parameters affect PROMETHEE II reversal [V, S10 title only; details UNVERIFIED].
- TOPSIS and VIKOR reversal under added/removed alternatives, and VIKOR's compromise (v, DQ) rule
  producing sets of "compromise" alternatives rather than a strict order: UNVERIFIED here (I know
  of Opricovic & Tzeng 2004 EJOR and Garcia-Cascales & Lamata 2012 but did not check them).
- SAW with max/min-max normalization is generally the most stable and most correlated with other
  methods in comparative studies: Mulliner et al. 2016 (Omega) compare WSM, WPM, AHP, TOPSIS,
  COPRAS on 10 alternatives x 20 criteria and report WSM-TOPSIS correlation ~0.86, WSM-COPRAS ~0.94,
  WPM an outlier (~0.18) [V, S11; numbers from accepted-manuscript tables, check vs published].
- Takeaway: the ranking method matters much less for the *top and bottom* of the list than for the
  middle where scores are tied within noise (consistent with S9's near-ties finding).

### Weighting x ranking interaction
- Little direct literature found. S2 reports SAW coupled with entropy or CRITIC less sensitive than
  other rankers [V]. Otherwise: UNVERIFIED. Expectation (own reasoning): interaction is largest when
  weights are very unequal (entropy often concentrates weight), since TOPSIS/VIKOR/PROMETHEE then
  behave like a single-criterion ranking and differ mainly in normalisation. Test empirically with a
  full factorial: weights {equal, entropy, CRITIC, SD, MEREC} x rankers x normalisations, then a
  variance decomposition of rank (ANOVA-style) -- this is our own design, not from a source.

### Robustness / sensitivity practice
- SMAA (Lahdelma, Hokkanen, Salminen 1998) explores the weight space by simulation and returns
  acceptability indices, central weight vectors, confidence factors; SMAA-2 (Lahdelma & Salminen
  2001) analyses all ranks (rank acceptability indices). [V, S12] Survey: Tervonen & Figueira 2008.
  [V, S12]
- Monte Carlo weight perturbation (e.g. Dirichlet or +/-x% noise around the base weights, rerun
  ranking, report rank intervals and top-k frequencies) is standard practice and is SMAA's idea
  restricted to a neighbourhood. A specific canonical reference for the Dirichlet variant: not
  found -> UNVERIFIED. Weight stability intervals for PROMETHEE and TOPSIS: Genc (2014) [V, S6].
- For data noise (our K repeated LLM scores) the analogue is to propagate score draws through the
  pipeline (SMAA also allows stochastic criteria values [V, S12 via Wikipedia summary]).

### Comparing rankings
- Spearman rho and Kendall tau are the common choices (used in S5, S7). Kendall is a pair-counting
  measure, easier to interpret ("share of concordant pairs"); Spearman penalises big displacements
  more. At n=12 both have wide sampling error: a rho of 0.5 is only borderline significant
  (statistical fact, UNVERIFIED as citation; compute exact permutation p-values instead).
- Rank-biased overlap (Webber, Moffat & Zobel 2010, ACM TOIS) handles indefinite/non-conjoint lists,
  top-weighted with persistence parameter p, supports ties and bounds (base/extrapolated). [V, S13]
  It is designed for truncated search-result lists; for full, complete rankings of 12 items it is
  mainly useful as a top-weighted alternative (our judgement).

## 2. Practical recommendation for this project
1. Report weights with uncertainty: bootstrap the 12 alternatives (and the K LLM repeats) and show
   weight intervals for entropy and CRITIC; add SD (cheap) and optionally MEREC. Treat weights whose
   interval spans most of [0, 2/m] as "not identified".
2. Always include equal weights as a baseline and as a shrinkage option: w = a*w_obj + (1-a)*equal
   (a=0.5 as a reported sensitivity row). Our suggestion; not from a cited source.
3. Fix normalization per method, then vary it as a sensitivity factor (vector, min-max, and
   optionally log) rather than treating it as a free choice. Cite S5/S6 as motivation only.
4. Rankers: SAW (baseline), TOPSIS, PROMETHEE II (not VIKOR first: its output is a compromise set,
   not a clean rank). Run each on the full set and on leave-one-out subsets to measure reversal.
5. Robustness layer: Monte Carlo weight perturbation + SMAA-2-style rank acceptability (a ~50-line
   NumPy routine: sample weights, compute ranks, tabulate rank-by-company matrix). Report each
   company as a rank interval / top-3 frequency, not a point rank. Treat close-score pairs as ties
   (cf. S9).
6. Comparison metrics: Kendall tau (primary), Spearman (secondary, as SCOPE.md says), RBO with
   p~0.8-0.9 for top-weighted agreement. Use permutation tests / bootstrap CIs given n=12.
7. Backtest framing: with n=12 a Spearman vs 2025 returns needs |rho| > ~0.58 for p<0.05 (two-sided,
   approx., verify with scipy); say so in the report.
8. Do not draw "method X is best" conclusions from one sector-year; quantify instead how much of
   rank variance comes from weights vs ranker vs normalization vs LLM score noise.

## 3. Sources (checked = abstract/search summary only unless noted)
- S1 Diakoulaki, Mavrotas, Papayannakis (1995). Determining objective weights in multiple criteria
  problems: the CRITIC method. Computers & Operations Research 22, 763-770.
  doi:10.1016/0305-0548(94)00059-H ; repo record https://dspace.lib.ntua.gr/xmlui/handle/123456789/11492
- S2 Sensitivity Assessment of Multi-Criteria Decision-Making Methods in Chemical Engineering
  Optimization Applications (arXiv 2024; authors not captured). https://arxiv.org/pdf/2403.11569
- S3 Entropy-ARAS vs CRITIC-ARAS customer prioritisation (Indonesian journal; title/authors not
  captured) https://ejournal.undip.ac.id/index.php/jmasif/article/view/73143 -- UNVERIFIED match.
- S4 Keshavarz-Ghorabaee et al. (2021). Determination of Objective Weights Using a New Method Based
  on the Removal Effects of Criteria (MEREC). Symmetry 13(4), 525. doi:10.3390/sym13040525 (title
  from memory, UNVERIFIED wording). https://etalpykla.vilniustech.lt/handle/123456789/151967
- S5 A VIKOR and TOPSIS focused reanalysis of the MADM methods based on logarithmic normalization
  (arXiv 2020; authors not captured). https://arxiv.org/pdf/2006.08150
- S6 Genc (2014). Sensitivity analysis on PROMETHEE and TOPSIS weights. Int. J. Multicriteria
  Decision Making (per search; first name/vol UNVERIFIED). https://www.inderscience.com/filter.php?aid=65359
- S7 Simanaviciene et al., TOPSIS/COPRAS normalization comparison, Baltic J. Modern Computing 10(2).
  https://www.bjmc.lu.lv/fileadmin/user_upload/lu_portal/projekti/bjmc/Contents/10_2_01_Simanaviciene.pdf
  (author list/title UNVERIFIED; content not read)
- S8 Verly & De Smet (2013). Some results about rank reversal instances in the PROMETHEE methods.
  Int. J. Multicriteria Decision Making 3(4), 325-345. https://ideas.repec.org/a/ids/ijmcdm/v3y2013i4p325-345.html
- S9 Dejaegere & De Smet (2022). A new threshold for the detection of possible rank reversal
  occurrences in PROMETHEE II rankings. Int. J. Multicriteria Decision Making 9(1), 1-16.
  https://ideas.repec.org/a/ids/ijmcdm/v9y2022i1p1-16.html
- S10 Omega 128 (2024) article on PROMETHEE II rank reversal (title/authors not captured).
  https://ideas.repec.org/a/eee/jomega/v128y2024ics0305048324000823.html
- S11 Mulliner, Malys, Maliene (2016). Comparative analysis of MCDM methods for the assessment of
  sustainable housing affordability. Omega 59(B), 146-156. doi:10.1016/j.omega.2015.05.013
  https://researchonline.ljmu.ac.uk/id/eprint/2777/
- S12 Lahdelma, Hokkanen, Salminen (1998). SMAA - Stochastic multiobjective acceptability analysis.
  EJOR 106(1), 137-143. https://sal.aalto.fi/publications/abstracts/plah98.html ;
  Lahdelma & Salminen (2001). SMAA-2. Operations Research. https://sal.aalto.fi/publications/abstracts/plah01.html ;
  Tervonen & Figueira (2008). A survey on SMAA methods. J. Multi-Crit. Decis. Anal. 15, 1-14.
  doi:10.1002/mcda.407 (cited via Wikipedia summary: https://en.wikipedia.org/wiki/Stochastic_multicriteria_acceptability_analysis)
- S13 Webber, Moffat, Zobel (2010). A Similarity Measure for Indefinite Rankings. ACM TOIS.
  https://people.eng.unimelb.edu.au/ammoffat/abstracts/wmz10acmtois.html

Mentioned but NOT checked (background memory only): Opricovic & Tzeng (2004, EJOR, VIKOR vs TOPSIS);
Garcia-Cascales & Lamata (2012, TOPSIS rank reversal); Wang & Triantaphyllou (2008, ranking
irregularities in ELECTRE/PROMETHEE; search returned nothing); Vafaei et al. (2016, normalisation).
