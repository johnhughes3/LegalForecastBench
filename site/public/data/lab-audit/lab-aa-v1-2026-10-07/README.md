# Harvey LAB-AA v1.0: October 7, 2026 snapshot

This numerical extract preserves the historical comparison cited in *Rules, Standards, and Rubrics: What Two Legal AI Benchmarks Reward*. Artificial Analysis produced the benchmark results. We recovered this copy from [Village LLM Atlas's downloadable data](https://atlas.village.dev/data.json) on November 8, 2026.

## Files and source

- [configurations.json](configurations.json): all 60 configuration scores that Atlas labels “Harvey LAB-AA v1.0 criterion pass rate (Artificial Analysis snapshot 2026-10-07),” with model names, identifiers, and source links.
- [models.csv](models.csv): 43 distinct models, ordered by each model's highest-scoring configuration in that extract. These ranks are our calculation, not a transcription of AA's displayed leaderboard ranks. Different reasoning settings of the same model count once; different model releases count separately.
- [Original AA leaderboard](https://artificialanalysis.ai/evaluations/harvey-lab-aa): now displays v1.1 results.
- [October 7 archived AA page identified by Atlas](https://web.archive.org/web/20261007050139/https://artificialanalysis.ai/evaluations/harvey-lab-aa).

The archived AA page could not be retrieved during recovery. This is a preserved extract of Atlas's copy, not an official AA export or an independently verified copy of the archived page. The snapshot date and archive URL are Atlas's source metadata. Atlas also retains one v1.0 entry for Muse Spark 1.1 from an August snapshot; it is excluded here to avoid combining dates. No GPT-6 Luna score appears in this October 7 extract.

## Reproducing the comparison

Sort the configuration records by descending `criterion_pass_rate_percent`, then keep the first record for each `model_slug`. GPT-5.6 Luna (max) is 17th of 43 distinct models at 87.899840787379%; Muse Spark 1.3 (xhigh) leads at 95.484151107251%. Their difference is 7.584310319872 percentage points, rounded to 7.58 in the paper. Luna is 32nd of 60 when each configuration is counted separately.

The values are criterion pass rates, not task all-pass rates. These results concern AA's private, cross-practice-area evaluation. The paper's rubric-defect estimate concerns public litigation tasks; the populations differ. AA's [October 8 v1.1 announcement](https://artificialanalysis.ai/articles/harvey-lab-aa-v1-1) explains that the dataset and grading changed and that v1.1 results are not directly comparable to v1.0.

## Citation and preservation

Credit Artificial Analysis as the evaluator and Village LLM Atlas as the recovery source. Identify the October 7, 2026 snapshot, the November 8, 2026 retrieval date, and the criterion-pass metric. Cite a commit-pinned GitHub link to this directory for the retained data and ranking calculation. The paper's bibliography contains that fixed link. Retaining this extract does not assert ownership of the original results or change their applicable terms.

This directory is also a static website asset: after deployment, the files are available under `/data/lab-audit/lab-aa-v1-2026-10-07/`. A repository commit does not itself publish the website. Keep this dated extract fixed; preserve any later correction separately and explain the difference.
