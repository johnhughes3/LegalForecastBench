# LegalReasonBench rankings captured November 8, 2026

Source: [LegalReasonBench (micro1)](https://www.micro1.ai/benchmark/legal-reason-bench). This extract preserves the numbers published on micro1's own page, retrieved November 8, 2026. The page's leaderboard widget labels its last update October 26, 2026. Unlike the recovered LAB-AA snapshot, these data were obtained directly from the evaluator.

## Preserved data

- [leaderboard.csv](leaderboard.csv): all nine models in the current leaderboard widget, with displayed mean reward and best-of-three scores in percent. Position preserves the widget's order; equal displayed scores need not be exact ties.
- [original-report.csv](original-report.csv): the eight models in the accompanying report, with unrounded means and 95% bootstrap confidence intervals from the page's embedded chart arrays. These values use a 0-to-1 scale.
- [paired-comparisons.csv](paired-comparisons.csv): all 56 directed comparisons in the report's eight-model table, including shared matching-version matter counts and the 95% intervals stored in the cells' tooltips. Differences use a 0-to-1 scale.
- [source.json](source.json): retrieval information, extraction locations, scoring definition, and scope qualifications.

The widget adds Kimi K3.1 Pro at 36.4%; the report and its confidence intervals still cover the original eight models. Neither captured list includes a Luna model. The source uses an asterisk for Gemini 4 Argon because it answered revised versions of 17 of the 50 matters. The pairwise table limits each comparison to matters where both models answered matching task versions. Do not substitute a difference between full-leaderboard means for a matching-version paired estimate.

## Score gaps and the rubric audit

The original report's unrounded means yield the following descriptive differences:

| Comparison | Difference in percentage points |
| --- | ---: |
| Gemini 4 Argon to Claude Fable 5.1 | 0.2469 |
| Gemini 4 Argon to Claude Opus 5.5 | 4.3405 |
| Muse Spark 1.3 to GPT-6 Astra, spanning the four-model middle group | 0.9668 |
| Gemini 4 Argon to GPT-6 Sol, highest to lowest | 18.8863 |

The displayed means are rounded, so subtracting 50.8 minus 50.6 gives 0.2 points rather than the 0.2469-point difference in the embedded unrounded values. The preserved files distinguish those precisions.

micro1's separate matching-version comparison estimates Argon minus Fable at 0.9 percentage points across 33 matters, with a 95% interval of -2.6 to +4.6 points. Its interval includes zero. These are the evaluator's published estimates; we did not rerun its bootstrap or obtain the underlying matter-level scores.

Our human audit estimates at least 45 defective criteria among 179 public litigation criteria (25.1%, one-sided 95% lower bound), with a point estimate of 53 (29.6%). It covers 11 assignments across four matters at public dataset revision `1bfa904c8f255925baf2610c0f86aa7c05d94ed9`. The leaderboard covers the full 50-matter benchmark, and the page does not map each leaderboard run to that public revision.

The defect shares count criteria equally. The leaderboard averages weighted rewards that include negative penalties over three runs per matter and then over matters. Consequently, 25.1% defective criteria is not an estimated 25.1-point score error, and it cannot be subtracted from a model's score or used to establish a ranking reversal. The supported comparison is that published rankings have narrow margins while the audited public subset contains substantive rubric defects. Measuring the effect on those rankings would require the corresponding criteria, weights, model answers, and corrected grades.

The sampled criteria and grades are recorded in the [human-review worksheet](https://github.com/johnhughes3/LegalForecastBench/blob/ec36a9c9/docs/legalreasonbench-audit/litigation/human-review/worksheet.md); the paper's [generated analysis](https://github.com/johnhughes3/LegalForecastBench/blob/ec36a9c9/docs/papers/lab-audit/analysis/lrb_review.py) checks the reported defect counts against that worksheet.

## Citation and preservation

Suggested citation: micro1. *LegalReasonBench: published leaderboard and paired comparisons*. Leaderboard widget labeled October 26, 2026; retrieved November 8, 2026. Available at https://www.micro1.ai/benchmark/legal-reason-bench. Cite a commit-pinned link to this directory alongside the original source to identify the retained numerical extract. The report's eight-model analysis and the widget's nine-model update are preserved separately.

These files are static website assets under `/data/lab-audit/legalreasonbench-2026-11-08/` after deployment. Committing the files does not publish the website. Retain this dated copy; store any later correction or update separately. The results remain attributable to micro1; this extract does not imply endorsement or assign a new license to the original results.
