# Publication Governance

Status: public result-label and publication-surface contract, effective 2026-07-16 · trimmed 2026-08-30 to the boundaries the project actually keeps.

The machine-readable source of truth is [`publication-governance.json`](publication-governance.json). Downstream report, leaderboard, README, writeup, community-site, and preprint work must use that contract rather than restating the roadmap from memory.

## Fixed boundaries

Official LegalForecast-MTD results and Community Harness Comparisons are different products. They use separate result paths, score meanings, and public identities. No surface may rank LegalForecast-MTD Brier scores against Harvey LAB rubric scores or combine the tracks into an overall winner.

No paid community run begins before its specification is committed; a schedule target never substitutes for it. Provider purchases and budget consent for corpus construction are not shipped from this repository at all; they belong to the companion private corpus repository, per the Corpus Spending Boundary in [AGENTS.md](/.agents/AGENTS.md).

Required non-affiliation text:

> LegalForecastBench is an independent project. Harvey AI, Harvey LAB, and LegalQuants are not sponsors, partners, or endorsers of this work.

Repository and publication credits do not imply review, approval, sponsorship, partnership, or endorsement.

## Required labels

Every published result carries the exact label its track and evidence basis calls for, copied verbatim onto the public surface and onto every README or preprint link to it. The three labels are frozen in the JSON contract, which is authoritative wherever this summary is shorter — in particular for each label's `forbidden_claims` list.

**Official LegalForecast-MTD Cycle 1 result** — the official track. It reports the frozen model identities, micro-Brier results, clustered uncertainty, coverage, accounting, baseline context, and limitations, and it may compare frozen Cycle 1 model configurations on the shared cohort. It may not claim absolute legal intelligence, infer capability gains across cycles with different case mixes, rank official Brier scores against Harvey LAB rubric scores, imply affiliation, or combine official and community rows into an overall winner. A post-anchor official row carries this same label plus an arm qualifier: **Official LegalForecast-MTD Cycle 1 result (post-anchor)**.

**Reproducible community result — contributor-grade, non-official** — a contributor-run community result. It may report observed score, coverage, efficiency, and failure results for its declared tasks and treatment identities. It may not call itself official, imply affiliation, claim harness causality, or name an overall cross-suite winner.

**Preliminary — one task pair, operator-run, not independently reproducible** — a single operator-run task pair. When the complete compatibility key matches, it may report only the observed paired difference for the pinned task and run; when it does not match, publish separately labeled system-bundle observations. It may not claim `estimated harness effect`, `performs better`, a population-average effect, general superiority, contributor safety, or independent reproducibility, and it does not close issue #49.

## Pre-anchor and post-anchor results

Every published result belongs to one of two arms, decided mechanically by comparing the model's first documented external deployment against the cycle's corpus anchor — the earliest decision date the cycle scores. A model released on or before the anchor is **pre-anchor**; one released after it is **post-anchor**. Per the owner directive of 2026-09-03 (bead `legalforecastbench-wjuo`), both arms are official, viable benchmark results. Pre-anchor is the gold standard, because only it supports the claim that every scored decision postdates the model. Post-anchor is reportable and first class alongside it, so a model released after the corpus was frozen is scored and published rather than withheld until a contamination-resistant corpus exists for it.

The arm is a tracked property of a result, not a permission to publish. What it governs is what may be claimed. A pre-anchor row may claim contamination resistance on this corpus; a post-anchor row may not, and no surface may present, cite, or link a post-anchor row as a contamination-resistant or pre-anchor result. That separation is fail-closed in both directions and is the one property this classification must never lose.

Keeping the arms distinct is what makes the comparison possible. A post-anchor model runs the identical pipeline, prompts, packets, and scoring protocol; it is aggregated separately and merged into the published surface at render time, appearing after the pre-anchor rows, ranked within its own arm, and marked with a dagger. The headline and overall best-model figure remain the best pre-anchor row. Delta-vs-best is versus the best model in the same arm, never across arms. On the Hugging Face distribution surface it occupies its own config and split. When the same model has a score in both arms, the paired delta between them is drift, and drift is a headline result of this benchmark: a large drift says contamination moves that model's score a great deal, a near-zero drift says it barely does, and both are publishable findings. This is not the four-tier result classification the project declined to adopt; it is two tracked arms, and neither is a tier below the other.

Contamination resistance is not being retired or downgraded by any of this. Acquiring fresh cases over time so a versioned benchmark keeps a contamination-resistant arm remains the goal; the anchor date exists to say which arm a case and a result belong to, and to say which cases to acquire next.

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
