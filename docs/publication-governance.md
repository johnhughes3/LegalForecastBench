# Publication Governance

Status: frozen for the dual-track launch on 2026-07-16.

The machine-readable source of truth is [`publication-governance.json`](publication-governance.json). Downstream report, leaderboard, README, writeup, community-site, and preprint work must use that contract rather than restating the roadmap from memory.

## Fixed boundaries

Official LegalForecast-MTD results and Community Harness Comparisons are different products. They use separate result paths, score meanings, approval gates, and public identities. No surface may rank LegalForecast-MTD Brier scores against Harvey LAB rubric scores or combine the tracks into an overall winner.

Dates are escalation triggers, not gate waivers. A missed date requires a recorded blocker, revised forecast, and claim consequence. It never authorizes a weaker freeze, audit, privacy, security, or review gate.

No one sends a message to Jamie Tso, LegalQuants, or another external party without John's approval of the exact text. Repository drafting is not send authority. The same rule applies to SSRN or arXiv submission.

No paid community run begins before its Tier-0 specification is committed. A schedule target never substitutes for that pre-spend freeze.

Required non-affiliation text:

> LegalForecastBench is an independent project. Harvey AI, Harvey LAB, and LegalQuants are not sponsors, partners, or endorsers of this work.

Harvey LAB receives ordinary repository, pinned-revision, and license credit. LegalQuants and Jamie Tso receive credit only for public feedback they supplied. Neither form of credit implies review, approval, sponsorship, or partnership.

## Audiences and calls to action

| Audience | What they should see first | Call to action |
| --- | --- | --- |
| Practitioners | The official Cycle 1 report and leaderboard; the short Tier-0 writeup when relevant | Read the human report first, compare score, coverage, cost, tokens, and time, then open the methods and audit evidence before using a result to choose a workflow or model. |
| AI researchers | The methods preprint, official report, and reproducible community site | Inspect the contamination boundary, frozen treatment identities, compatibility key, evaluator separation, uncertainty, and immutable evidence; propose a preregistered replication or extension. |
| LegalQuants | The preliminary Claude writeup, later Codex addendum, and official report | Review the preliminary result and offer pilot-design input before the declared input window closes and before any stratified-pilot score is observed. |
| Contributors | The README contributor path and reproducible community site | Reproduce the pinned fixture path, follow the contributor-grade submission contract, validate the package locally, and submit an evidence-linked pull request. |

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

| Surface | Canonical destination | Track | Tier | Owner | Approval |
| --- | --- | --- | --- | --- | --- |
| Cycle 1 human report | `results/official/cycle-1/README.md` | Official | Official | D0 | Official publication |
| Cycle 1 leaderboard | `results/official/cycle-1/leaderboard.md` | Official | Official | D0 | Official publication |
| Claude Tier-0 writeup | `results/community/harvey-lab/claude-code-tier0.md` | Community | Preliminary | D1 | Tier-0 publication |
| Codex Tier-0 addendum | `results/community/harvey-lab/codex-tier0.md` | Community | Preliminary | D1 | Tier-0 publication |
| Community comparison site | `community/site/index.html` | Community | Reproducible | D1 | Tier-1 community publication |
| README official block | `README.md#official-benchmark-results` | Official | Official | D1 | Official publication |
| README preliminary block | `README.md#preliminary-community-result` | Community | Preliminary | D1 | Tier-0 publication |
| README contributor block | `README.md#reproducible-community-comparisons` | Community | Reproducible | D1 | Tier-1 community publication |
| Methods preprint | `docs/preprint/legalforecast-mtd-cycle-1.md` | Official | Official | D1 | John separately approves submission |

The canonical GitHub URLs are frozen in the JSON contract. README and preprint sections that link results must reproduce each result's tier label next to the link. A community appendix in the official preprint keeps its own preliminary or reproducible label; placement does not promote it to official evidence.

## Owners and approvals

D0 owns the Cycle 1 report and leaderboard shell and later official presentation. D1 owns the harness writeup, README landing page, and preprint draft. D2 owns this governance contract, LegalQuants drafts, and their Beads evidence, but never sends externally. D3 owns quality integration and independent cross-worktree review. John makes final external communication, release, authorship, and submission decisions.

Tier-0 publication requires a specification that predates spend, a reviewed machine package, independent privacy and claims scans, and John's release approval. Reproducible community publication additionally requires contributor-grade acceptance, trusted score verification, package validation, a clean rebuild, and independent review. Official publication requires completion of `LegalForecastBench-5qd6.41`, an independent artifact and claims audit, protected publication, and John's release approval.

## Controlled communications

The immediate LegalQuants draft may describe the intended native-tools design only as pending feasibility. It makes no unpublished result claim, invites input before pilot selection freezes and before pilot scores exist, and includes the required non-affiliation text.

The result follow-up may link only a validated publication. It reproduces the publication's exact tier label, states the one-task scope when applicable, and keeps the pilot-input deadline explicit. Both drafts remain unsent until John approves the exact text.

The preprint may be drafted and packaged in the repository. John separately approves authorship, destination, final text, and submission.

## Calendar

| Deliverable or decision | Target | Hard escalation | Required action if missed |
| --- | --- | --- | --- |
| Claims governance freeze | 2026-07-18 | — | Record the blocker before public-surface work proceeds. |
| First LegalQuants send/decline decision | 2026-07-18 | — | Record John's send, decline, or defer decision; never send without approval or block engineering on it. |
| Model-universe cut | 2026-07-20 | — | Move later candidates to Cycle 2 unless John records a new pre-freeze decision. |
| Reviewed Claude Tier-0 package | 2026-07-21 | 2026-07-23 | Escalate the exact blocker; publish only verified, preliminary plumbing evidence if no matched result exists. |
| Claude writeup and README link | Within 24 hours of validated publication; projected 2026-07-22 | — | Record why the post-validation window was missed and assign a corrective owner/date. |
| Codex Tier-0 follow-on | 2026-07-23 | 2026-07-25 | Continue Claude publication and Tier-1 freeze without waiting for Codex. |
| Official source reconciliation | 2026-07-24 | — | Record the source shortfall, revised forecast, and exact-100 impact. |
| Contributor-grade Claude checkpoint | 2026-07-31 | — | Keep Tier 0 preliminary and record the failing contributor gate. |
| First trusted issue-49 row | 2026-08-07 | — | Do not close issue #49 or relabel Tier-0 evidence. |
| Official exact-100 packet readiness | 2026-08-07 | — | Record the immutable-gate shortfall without changing the cohort rule. |
| Official one-provider smoke | 2026-08-11 | — | Record the failure; do not dispatch the official matrix. |
| LegalQuants pilot-input window closes | 2026-08-12 | — | Close as feedback received, no response, or John-declined-send. |
| Official dispatch | 2026-08-13 | — | Record the blocking gate; do not alter the cohort, registry, or approvals. |
| Audited official publication | 2026-08-17 | — | Keep surfaces private or unreleased until the failing audit/publication gate passes. |
| Official README link | Within 24 hours of audited publication; projected 2026-08-18 | — | Record the missed link window and assign an immediate fix. |
| Prespecified pilot publication | 2026-08-21 | — | Record the pilot failure; do not generalize from Tier 0 instead. |
| Preprint draft | Within seven days of the official report; projected 2026-08-24 | — | Record the drafting blocker without substituting unreviewed claims. |
| Cycle relevance reapproval | 2026-08-27 | — | John must continue, reanchor and reproject, or defer Cycle 1. |
| SSRN package | Within fourteen days of the official report; projected 2026-08-31 | — | Record the packaging blocker; submission still requires John's approval. |

## Consumer checklist

Before publishing or linking a result:

1. Select the evidence tier from the JSON contract. Do not invent an intermediate label.
2. Copy the exact required label onto the public surface and every README or preprint link to it.
3. Satisfy the tier's evidence list and the surface-specific disclosures.
4. Apply the global separation, non-affiliation, score-meaning, and no-overall-winner rules.
5. Obtain the named approval. A date, merged draft, or available URL is not approval.
6. If a target date was missed, record the blocker and revised forecast without weakening any gate.

## Consistency record

The retained roadmap and live GitHub issue #196 were checked on 2026-07-16. Both use the exact Tier-0 label, preserve the native Claude treatment, require the matched compatibility key before reporting an observed paired difference, reserve generalized causal or superiority language for a prespecified pilot with supported uncertainty, keep issue #49 open, and separate official from community work.
