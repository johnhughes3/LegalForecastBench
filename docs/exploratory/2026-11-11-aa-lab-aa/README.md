# November 11, 2026: AA and LAB-AA exploratory comparison

This directory reproduces only the numerical claims in the November 11 public response: the GPT-4.1 comparison, two AA correlation comparisons, Brier references, and cohort counts. The associated posts and timestamps are preserved in the pull request description. No other exploratory comparisons are included.

## Reproduce

From the repository root:

```bash
uv run --locked --with scipy==1.18.1 python docs/exploratory/2026-11-11-aa-lab-aa/reproduce.py --check
```

Omit `--check` to print the calculated JSON; redirect stdout to `results.json` to regenerate that file. The command reads only the adjacent saved inputs. Once dependencies are installed, the calculation works offline and makes no model calls. NumPy 2.5.4 comes from the repository's `uv.lock`; SciPy is pinned in the command without adding a runtime dependency to the benchmark.

## Saved evidence

- [inputs.csv](inputs.csv): the 21 ranked LFB micro-Brier scores and GPT-4.1 reference, plus only the AA variants and LAB-AA scores used in the cited correlations. Blank external-score cells mean the model is outside that comparison; they are not zeros.
- [cohort.json](cohort.json): 91 cases, 387 prediction units per model, and 285 dismissed units, used to reproduce the sample size and retrospectively fitted constant reference.
- [reproduce.py](reproduce.py): the arithmetic and fixed-seed permutation calculation.
- [results.json](results.json): generated output with more precision than the public response.

LFB inputs were copied from Table 1, the reference-baseline paragraph, and Appendix A of the [working-paper source at commit 06f9cfa11a637532dcb4976d62f3ed0c1e03a94f](https://github.com/johnhughes3/LegalForecastBench/blob/06f9cfa11a637532dcb4976d62f3ed0c1e03a94f/docs/papers/legalforecastbench/LegalForecastBench-paper.tex). This script recomputes comparisons from published aggregate scores; it does not rerun models or rescore unit-level predictions.

AA and LAB-AA inputs were captured on November 11, 2026 from the public data served by the [AA model comparison page](https://artificialanalysis.ai/models/claude-fable-5-1) and [Harvey LAB-AA leaderboard](https://artificialanalysis.ai/evaluations/harvey-lab-aa). The fields retained are `intelligenceIndex` (AA Intelligence Index v5.0.1) and `harveyLab` (LAB-AA v1.1 hallucination-gated all-pass rate, represented as a proportion). The CSV retains AA slugs so each configuration can be located at `https://artificialanalysis.ai/models/<slug>`. These live pages may change; the saved numeric extracts preserve the inputs actually used.

## The two matching rules

The **10-model comparison** selects rows with `aa_same_effort_score`: the stated reasoning effort matches LFB's high setting. It correlates AA's score with negative micro-Brier, so positive correlation means agreement about better performance. Its Spearman coefficient is 0.563636363636, reported as **+0.56**. The two-sided permutation p-value is 0.096979030210, reported as **0.10**.

The **12-model comparison** selects rows with `aa_shared_model_score` and `lab_aa_gated_all_pass`. It matches model identities across all three sources, allowing LFB's reasoning effort to differ. AA's Intelligence Index and LAB-AA scores use the same AA configuration slug. Where multiple LAB-AA efforts exist, the highest available effort is selected, not the highest observed LAB score. The coefficients are **0.405594405594 for LFB** and **0.090909090909 for LAB-AA**, reported as **0.41** and **0.09**. The 10- and 12-model sets are not nested. Product names and effort labels are matching evidence, not proof of identical API snapshots or harnesses.

The p-value reproduces the original 100,000 random permutations, in batches of 1,000, using NumPy's default generator with seed 20261111 and the CSV row order. Each permutation randomly pairs the fixed rank vectors; the test counts absolute correlations at least as large as observed and uses `(extreme + 1) / (100000 + 1)`. Average ranks handle ties. This is an exploratory, unadjusted model-level diagnostic: models are not an independent random sample, and task-level score uncertainty is not propagated. A larger point estimate does not establish a statistically significant difference between correlations.

## Other cited numbers

GPT-4.1's micro-Brier is **0.60513** versus **0.18345** for Gemini 3.1 Pro Preview, the worst-performing ranked model; the response rounds these to **0.605** and **0.183**. The constant 50% forecast has Brier **0.25**. The retrospectively fitted constant has Brier `(285/387) × (1 − 285/387) = 0.194098912325`, reported as **0.19410**. All **21 ranked models** beat both Brier references; GPT-4.1 beats neither. The **387 predictions per model** come from **91 cases**, not 387 independent cases. No human-baseline result is supplied or inferred by this calculation.
