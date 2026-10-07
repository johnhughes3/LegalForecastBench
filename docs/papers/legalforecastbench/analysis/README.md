# Within-case clustering

This analysis measures association among claim–defendant units sharing a case. It uses the public unit-level exports named in `site/src/data/significance/inputs.json`; no private court records or model calls are required. All included models must have the same case/unit identities and labels. Models without public unit-level exports are reported as unavailable rather than reconstructed from aggregate scores.

## Regenerate and check

From the repository root:

```bash
uv run --frozen python docs/papers/legalforecastbench/analysis/clustering.py --write-manuscript --manuscript docs/papers/legalforecastbench/LegalForecastBench-paper.tex
uv run --frozen python docs/papers/legalforecastbench/analysis/clustering.py --check --manuscript docs/papers/legalforecastbench/LegalForecastBench-paper.tex
```

The first command writes [results.json](results.json), [summary.tex](summary.tex), and the paragraph between the manuscript's `BEGIN GENERATED CLUSTERING` and `END GENERATED CLUSTERING` comments. The rest of the manuscript is untouched. The second recomputes the analysis and fails if those results or the marked paragraph are stale; the Paper workflow runs it before compiling the PDF. A changed dataset therefore requires regenerating and reviewing the results alongside the source change.

That paragraph is generated so the quoted counts and intervals stay tied to the public unit exports. Its wording lives in `render_summary`. Change the wording there, then regenerate. Editing the marked paragraph in the manuscript alone makes the check fail. Pair-agreement counts remain in `results.json` when the paragraph does not quote them.

Use `--inputs` for another cohort manifest, `--output-dir` for another destination, and `--seed`, `--bootstrap`, or `--permutations` to change the resampling configuration. The manifest's `models` maps model identifiers to unit-export paths relative to the manifest. Each JSONL row needs `case_id`, `unit_id`, binary `outcome`, and finite `probability_fully_dismissed` between zero and one. Run `--help` for the complete interface. The defaults are seed 20260930, 20,000 whole-case bootstrap draws, and 20,000 label permutations; NumPy is pinned by the repository lockfile.

## Estimator and interpretation

We use the one-way ANOVA method-of-moments intraclass correlation coefficient (ICC), corrected for unequal case sizes. Let case c contain n_c units, N be the total number of units, and C the number of cases. With between-case and within-case mean squares MS_B and MS_W, define:

```text
n_0 = [N - sum_c(n_c^2)/N] / (C - 1)
ICC = (MS_B - MS_W) / [MS_B + (n_0 - 1) MS_W]
```

The outcome estimate is on the observed 0/1 scale, not a latent logistic scale. It summarizes within-case association under a common-correlation variance-components interpretation; legal units need not have identical dependence in every case. Negative estimates are retained rather than clipped. Constant responses and other undefined estimates are reported explicitly, not converted to zero.

Percentile 95% intervals resample entire cases, retaining all units and recomputing case-size corrections on each draw. The intervals assume cases are independent sampling clusters. Model-specific intervals are pointwise, not adjusted for simultaneous comparisons, and do not establish a model ranking. The same case draws are used across model metrics.

The one-sided outcome permutation test shuffles labels into fixed case-size slots while preserving the dismissal count. Its null is exchangeability of outcome labels across case assignments; it does not control for legal subject matter or other covariates. The Monte Carlo p-value is (exceedances + 1)/(permutations + 1), never zero. This diagnostic does not establish independence among related cases or multidistrict-litigation families.

Within- and between-case pair agreement are descriptive proportions. Larger cases contribute more within-case pairs. Overlapping pairs are not independent observations, so their counts must not be used as sample sizes in an ordinary two-proportion test. The output also reports an equal-case within-case agreement sensitivity.

For each available model, the script computes separate ICCs for signed errors p-y and Brier losses (p-y)^2. A comparison of two models should instead use paired loss differences and resample whole cases (or the coarser related-case family when known); this script's univariate ICCs do not replace the benchmark's paired comparison analysis.

## Sources

- Tak K. Mak, [Analysing Intraclass Correlation for Dichotomous Variables](https://doi.org/10.2307/2347309), *Applied Statistics* 37(3):344–352 (1988), supports the observed-scale variance-component approach to binary responses.
- A. Colin Cameron and Douglas L. Miller, [A Practitioner's Guide to Cluster-Robust Inference](https://doi.org/10.3368/jhr.50.2.317), *Journal of Human Resources* 50(2):317–372 (2015), explains why inference must respect within-cluster dependence.
