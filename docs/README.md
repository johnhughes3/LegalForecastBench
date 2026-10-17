# Documentation Index

This index covers the current public documentation for LegalForecastBench. The reproduction guide is checked against the CLI by automated tests. Corrections are welcome as issues or pull requests.

## Start Here

| If you want to… | Read |
| --- | --- |
| Understand what the benchmark measures and how | [METHODS.md](METHODS.md) |
| Reproduce or audit a published result | [reproduce-or-audit.md](reproduce-or-audit.md) |
| Know what may and may not be claimed publicly | [publication-governance.md](publication-governance.md) |
| Read the working papers | [papers/README.md](papers/README.md) |

## Official Benchmark

- [Methods](METHODS.md): construct, frozen inputs, leakage controls, model eligibility, metrics, inference, related work, limitations, and withdrawal policy.
- [Reproduce or audit](reproduce-or-audit.md): validating a published release, recomputing scores and reports, verifying public arithmetic, the audit checklist, and how official runs are produced.
- [Publication governance](publication-governance.md): track separation, eligibility, reporting, and non-affiliation rules.
- [Model release dates](MODEL_RELEASE_DATES.md): model identities, release dates, and provider-reported cutoffs behind the Cycle 1 comparisons.
- [Jev one-shot condition](jev-mode.md): the separately reported summary experiment, with unchanged prediction units and full text or persisted document summaries.
- [Website data contract](site-data.md): public score exports, frontend integration, hosting, and case withdrawals.
- [Hugging Face benchmark publication](hugging-face-publication.md): gated access, immutable dataset revisions, and leaderboard registration.

## Corpus Handoff Boundary

Corpus construction, private source bytes, selection, unitization, and quality control are owned by the companion LegalForecastCorpus repository. This public repository receives only immutable, outcome-blinded release inputs.

- [Release inputs](release-inputs.md): the forecast release, the separately controlled labels release, and what each contains.

## Research

- [Working papers and PDF builds](papers/README.md): the LegalForecastBench and Harvey LAB audit manuscripts, public numerical inputs, and build and publication instructions.
- [Paper figure reproduction](papers/legalforecastbench/figures/README.md): regenerate the manuscript CSVs and TikZ result figures from public inputs.
- [Paper clustering analysis](papers/legalforecastbench/analysis/README.md): reproduce within-case dependence estimates.
- [Rationale review export](rationale-audit.md): prepare private, model-blinded rationales from saved forecasts for qualitative lawyer review.
- [AI-generated Harvey LAB litigation audits](harvey-lab-audit/litigation-dispute-resolution/README.md): unverified, human-steered analysis of rubric and grading drift by GPT-6 Sol and Claude Opus 5.5 across 52 tasks, with its own file index. Inclusion is not verification.
- [AI-generated LegalReasonBench litigation audit](legalreasonbench-audit/litigation/README.md): a pinned audit of the public sample's litigation assignments using the Harvey rubric-defect taxonomy. Findings are unverified AI judgments, with source extractions and reproducible counts.

## Community Multi-Harness (planned)

- [Multi-harness overview](multiharness/README.md): a planned, non-official community track for comparing agent harnesses. It is not yet operational; its contracts, adapter specs, and contributor guides are indexed there.
