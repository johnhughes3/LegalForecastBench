# Publication Governance

Status: public result-label and publication-surface contract, effective 2026-07-16 · trimmed 2026-08-30 to the boundaries the project actually keeps.

The machine-readable source of truth is [`publication-governance.json`](publication-governance.json). Downstream report, leaderboard, README, writeup, community-site, and preprint work must use that contract rather than restating the roadmap from memory.

## Fixed boundaries

Official LegalForecast-MTD results and Community Harness Comparisons are different products. They use separate result paths, score meanings, and public identities. No surface may rank LegalForecast-MTD Brier scores against Harvey LAB rubric scores or combine the tracks into an overall winner.

No paid community run begins before its specification is committed; a schedule target never substitutes for it. What may be spent, and how the owner's approval is recorded, is governed by the Spending guardrails in [AGENTS.md](/.agents/AGENTS.md).

Required non-affiliation text:

> LegalForecastBench is an independent project. Harvey AI, Harvey LAB, and LegalQuants are not sponsors, partners, or endorsers of this work.

Repository and publication credits do not imply review, approval, sponsorship, partnership, or endorsement.

## Required labels

Every published result carries the exact label its track and evidence basis calls for, copied verbatim onto the public surface and onto every README or preprint link to it. The three labels are frozen in the JSON contract, which is authoritative wherever this summary is shorter — in particular for each label's `forbidden_claims` list.

**Official LegalForecast-MTD Cycle 1 result** — the official track. It reports the frozen model identities, micro-Brier results, clustered uncertainty, coverage, accounting, baseline context, and limitations, and it may compare frozen Cycle 1 model configurations on the shared cohort. It may not claim absolute legal intelligence, infer capability gains across cycles with different case mixes, rank official Brier scores against Harvey LAB rubric scores, imply affiliation, or combine official and community rows into an overall winner.

**Reproducible community result — contributor-grade, non-official** — a contributor-run community result. It may report observed score, coverage, efficiency, and failure results for its declared tasks and treatment identities. It may not call itself official, imply affiliation, claim harness causality, or name an overall cross-suite winner.

**Preliminary — one task pair, operator-run, not independently reproducible** — a single operator-run task pair. When the complete compatibility key matches, it may report only the observed paired difference for the pinned task and run; when it does not match, publish separately labeled system-bundle observations. It may not claim `estimated harness effect`, `performs better`, a population-average effect, general superiority, contributor safety, or independent reproducibility, and it does not close issue #49.

## Supplementary presentation on official surfaces

A model released after the cycle's corpus decision window closed runs through the official pipeline but publishes as supplementary, not official. It is aggregated separately and merged into the official surface only at render time, so it never enters the official set or any official set-equality gate.

Supplementary rows appear beside official rows on the official surface, after them and ordered by model id, marked with a dagger and the standard supplementary caveat. They are never ranked: no rank position, no best-model claim, no delta-vs-best interval. On the Hugging Face distribution surface they occupy their own config and split. A supplementary row may not be presented, cited, or linked as an official LegalForecastBench result, and its presence on an official surface does not promote it.

This is not the four-tier result classification the project declined to adopt. It is a two-value presentation flag, `official` or `supplementary_post_anchor`, derived mechanically from a release date against the corpus anchor, plus one fail-closed gate that refuses a post-anchor model inside an official bundle.

## Canonical public surfaces

| Surface | Canonical destination | Track | Label |
| --- | --- | --- | --- |
| Cycle 1 human report | `results/official/cycle-1/README.md` | Official | Official |
| Cycle 1 leaderboard | `results/official/cycle-1/leaderboard.md` | Official | Official |
| Claude Tier-0 writeup | `results/community/harvey-lab/claude-code-tier0.md` | Community | Preliminary |
| Codex Tier-0 addendum | `results/community/harvey-lab/codex-tier0.md` | Community | Preliminary |
| Community comparison site | `community/site/index.html` | Community | Reproducible |
| README official block | `README.md#official-benchmark-results` | Official | Official |
| README preliminary block | `README.md#preliminary-community-result` | Community | Preliminary |
| README contributor block | `README.md#reproducible-community-comparisons` | Community | Reproducible |
| Methods preprint | `docs/preprint/legalforecast-mtd-cycle-1.md` | Official | Official |

The canonical GitHub URLs are frozen in the JSON contract. README and preprint sections that link results must reproduce each result's label next to the link. A community appendix in the official preprint keeps its own preliminary or reproducible label; placement does not promote it to official evidence.
