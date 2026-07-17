# Publication Governance

Status: public result-label and publication-surface contract, effective 2026-07-16.

The machine-readable source of truth is [`publication-governance.json`](publication-governance.json). Downstream report, leaderboard, README, writeup, community-site, and preprint work must use that contract rather than restating the roadmap from memory.

## Fixed boundaries

Official LegalForecast-MTD results and Community Harness Comparisons are different products. They use separate result paths, score meanings, approval gates, and public identities. No surface may rank LegalForecast-MTD Brier scores against Harvey LAB rubric scores or combine the tracks into an overall winner.

No paid community run begins before its Tier-0 specification is committed. A schedule target never substitutes for that pre-spend freeze.

Required non-affiliation text:

> LegalForecastBench is an independent project. Harvey AI, Harvey LAB, and LegalQuants are not sponsors, partners, or endorsers of this work.

Repository and publication credits do not imply review, approval, sponsorship, partnership, or endorsement.

## Evidence and claim tiers

### Preliminary

Required label: **Preliminary — one task pair, operator-run, not independently reproducible**

This tier requires a pre-spend frozen specification, hash-identical solver-visible bytes, physical solver/evaluator separation, sealed deliverables, complete attempt retention, independent privacy and claims scans, and peer reporting of score, coverage, cost basis, token dimensions, wall-clock, attempts, retries, and failures.

When the complete compatibility key matches, the surface may report only the observed paired difference for the pinned task and run. When it does not match, publish separately labeled system-bundle observations. This tier may not claim `estimated harness effect`, `performs better`, population-average effect, general superiority, contributor safety, or independent reproducibility. It does not close issue #49.

### Reproducible community

Required label: **Reproducible community result — contributor-grade, non-official**

This tier requires contributor-grade containment and canaries, fail-closed auth and execution identities, trusted score verification, hostile package validation, a clean-checkout site rebuild, pinned contributor documentation, and immutable submission evidence.

It may report observed score, coverage, efficiency, and failure results for the declared tasks and treatment identities. Pilot estimates require a specification frozen before pilot scores and supported uncertainty. It may not call itself official, imply affiliation, claim harness causality without the matched key and prespecified pilot, or name an overall cross-suite winner.

### Official

Required label: **Official LegalForecast-MTD Cycle 1 result**

This tier requires the exact-100 freeze, dispatch, authenticated receipts, fan-in, aggregate, protected publication, and independent audit gates. It reports the frozen model identities, micro-Brier results, clustered uncertainty, coverage, accounting, baseline context, and limitations.

It may compare frozen Cycle 1 model configurations on the shared cohort. It may not claim absolute legal intelligence, infer capability gains across cycles with different case mixes, rank official Brier scores against Harvey LAB rubric scores, imply affiliation, or combine official and community rows into an overall winner.

## Canonical public surfaces

| Surface | Canonical destination | Track | Tier |
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

The canonical GitHub URLs are frozen in the JSON contract. README and preprint sections that link results must reproduce each result's tier label next to the link. A community appendix in the official preprint keeps its own preliminary or reproducible label; placement does not promote it to official evidence.

## Consumer checklist

Before publishing or linking a result:

1. Select the evidence tier from the JSON contract. Do not invent an intermediate label.
2. Copy the exact required label onto the public surface and every README or preprint link to it.
3. Satisfy the tier's evidence list and the surface-specific disclosures.
4. Apply the global separation, non-affiliation, score-meaning, and no-overall-winner rules.
5. Complete the evidence, review, and release gates required for the selected tier and surface.
