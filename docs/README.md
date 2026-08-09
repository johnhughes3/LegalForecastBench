# Documentation Index

The technical documentation in this folder is drafted and maintained with substantial assistance from AI systems working under the direction of John J. Hughes, III, and is reviewed on a best-effort basis. Where possible, accuracy is enforced mechanically: the official-run runbook and reproduction guide are checked against the actual CLI by automated tests. Corrections are welcome as issues or pull requests.

## Start Here

| If you want to… | Read |
| --- | --- |
| Understand what the benchmark measures and how | [METHODS.md](METHODS.md) |
| Reproduce or audit a published result | [reproduce-or-audit.md](reproduce-or-audit.md) |
| Know what may and may not be claimed publicly | [publication-governance.md](publication-governance.md) |
| Operate a protected official cycle | [official-run-runbook.md](official-run-runbook.md) |
| Submit a community harness comparison | [multiharness-adapter-spec.md](multiharness-adapter-spec.md), then [community-submissions.md](community-submissions.md) |

## Official Benchmark

- [METHODS.md](METHODS.md): eval-card-grade methods — construct, frozen inputs, leakage controls, metrics, inference, related work, human-baseline status, limitations, and withdrawal policy.
- [labeling-protocol.md](labeling-protocol.md): the unit-resolution and edge-case codebook used to label frozen prediction units.
- [official-run-runbook.md](official-run-runbook.md): operator checklist for protected official cycles — freeze, dispatch, recovery, aggregation, and site rendering.
- [reproduce-or-audit.md](reproduce-or-audit.md): credential-free reproduction of public arithmetic and the deeper audit workflow.
- [Publication governance](publication-governance.md): public evidence tiers, forbidden claims, canonical result destinations, track-separation rules, and non-affiliation language.

## Acquisition Operations

- [Ingestion module map](ingestion-module-map.md): concern-oriented ownership and entry points for every module in the intentionally shallow `legalforecast.ingestion` package.
- [Acquisition systemd launcher](acquisition-systemd-launcher.md): fail-closed Infisical child-status propagation, downstream receipt requirements, and the provider-free transient-unit smoke.
- [Cycle 1 Target-100 direct prerequisites](cycle-1-target-100-direct-prerequisites.md): the authority and protected-workflow steps that cannot be represented as ordinary coordinator stages.
- [Cycle 1 v4 ranked-reserve materialization](cycle-1-target-100-v4-ranked-reserve-materialization.md): materializing already-approved v4 ranked-reserve authority without rerunning selection or contacting a provider.
- [Cycle 1 v4 ranked-reserve continuation](cycle-1-target-100-v4-ranked-reserve-replacement.md): replacing a candidate only on terminal nonretryable exclusion evidence, consuming the reserve in frozen order under the unchanged cap.
- [Cycle 1 target-100 recovery disclosure continuation](cycle-1-target-100-recovery-disclosure.md): keeping recovered CourtListener material quarantined until public provenance is authenticated and every PDF is scanned.
- [Cycle 1 exact-100 cohort-policy provenance](cohort-policy-cycle-1-target-100-2026-07-25-provenance.md): value-by-value record of why each committed cohort-policy value is authorized or mechanically derived.
- [Cycle 1 change control](cycle-1-change-control.md): the change-control rules adopted for the remainder of Cycle 1, through the final gate.
- [Cycle 1 Stage A v4 correctness migration](cycle-1-stage-a-v4-correctness-migration.md): the required citation-integrity, ontology, successor-cohort, and replay path before Cycle 1 Stage B.
- [Commitment contracts](commitment-contracts.md): named canonical-byte, digest-representation, and schema-domain APIs for new code without migrating Cycle 1 artifacts.

## Community Multi-Harness (non-official)

The multi-harness layer is a separate, non-official track. Its results never rank alongside official results.

- [multiharness-adapter-spec.md](multiharness-adapter-spec.md): the community adapter contract.
- [community-submissions.md](community-submissions.md): submission packaging, attestations, credits, funding policy, and PR intake.
- [multiharness-deliverable-contract.md](multiharness-deliverable-contract.md): the harness-independent sealed boundary between a solver run and later evaluation.
- [multiharness-evaluation-contract.md](multiharness-evaluation-contract.md): `EvaluationSpec` precommitments for deliverables, evaluator identity, judge settings, and runtime policy.
- [multiharness-score-contract.md](multiharness-score-contract.md): the pinned score contract — deliberately a strict Harvey LAB specialization, not generic metric arithmetic.
- [multiharness-artifact-compatibility.md](multiharness-artifact-compatibility.md): the frozen compatibility baseline for community artifact readers and writers.

### Adapter tracks

- [lq-ai.md](adapters/lq-ai.md): LegalQuants LQ.AI fixture track.
- [hermes-agent.md](adapters/hermes-agent.md): Hermes CLI/batch/API/library fixture track.
- [openclaw.md](adapters/openclaw.md): OpenClaw harness/plugin fixture track.
- [provider-baselines.md](adapters/provider-baselines.md): provider/runtime reference points and the publication terms they rest on.
- [harvey-lab-pinned-evaluator-seam.md](adapters/harvey-lab-pinned-evaluator-seam.md): the pinned upstream evaluator boundary the deliverable, evaluation, and score contracts rely on.
- [codex-cli-characterization.md](adapters/codex-cli-characterization.md): pinned offline interface characterization of the installed Codex CLI; not activated for benchmark execution.
- [codex-native-containment.md](adapters/codex-native-containment.md): why the pinned Codex CLI does not qualify as clean-native containment on this host.
- [claude-code-native-containment.md](adapters/claude-code-native-containment.md): pending zero-provider-spend containment characterization; no successful capture or fixture is claimed.

## Preprint

- [preprint/README.md](preprint/README.md): the pre-results preprint package and its approval boundary.
- [preprint/legalforecast-mtd-cycle-1.md](preprint/legalforecast-mtd-cycle-1.md): the Cycle 1 methods draft, which claims no result.

## Schema Reference

Artifact and policy contracts consumed by the CLI. Where a schema is versioned, the highest version is current unless the document says otherwise; superseded versions are retained because existing artifacts remain verifiable against them.

**Cycle configuration**

- [acquisition-cycle-config-v1.md](schemas/acquisition-cycle-config-v1.md): the immutable operator plan consumed by `acquisition run-cycle`.
- [acquisition-cycle-template-v1.md](schemas/acquisition-cycle-template-v1.md): how `acquisition render-cycle-config` turns a path-parameterized template into that immutable config.
- [cycle-lineage-index-v1.md](schemas/cycle-lineage-index-v1.md): rebuildable, machine-local discovery of the uniquely current receipt-backed cycle lineage and human-decision state.

**Discovery and screening**

- [courtlistener-discovery-snapshot-v1.md](schemas/courtlistener-discovery-snapshot-v1.md): hash-bound provider-page transcripts and provider-free saturated snapshot materialization.
- [courtlistener-recap-fetch-broker-v1.md](schemas/courtlistener-recap-fetch-broker-v1.md): why raw PACER credentials never reach this repository, and the broker identity policy that replaces them.
- [firecrawl-screening-implementation-v1.md](schemas/firecrawl-screening-implementation-v1.md): the Firecrawl-specific screening, replay, and promotion path.
- [frozen-batch-firecrawl-observation-v1.md](schemas/frozen-batch-firecrawl-observation-v1.md): the frozen-batch Firecrawl observation run record.
- [opinion-recap-resolution-v1.md](schemas/opinion-recap-resolution-v1.md): resumable strict identity mapping from opinion leads to RECAP docket identities.
- [opinion-docket-gap-plan-v1.md](schemas/opinion-docket-gap-plan-v1.md): projecting the cost of refreshing authoritative docket coverage.
- [target-public-gap-refresh-v1.md](schemas/target-public-gap-refresh-v1.md): the public-recovery overlay for an authenticated target-cohort projection.
- [target-raw-docket-auxiliary-provenance-v1.md](schemas/target-raw-docket-auxiliary-provenance-v1.md): provider-free bridge from a frozen raw-docket manifest to receipt-verified selected recovery pages.

**Cohort selection**

- [cohort-policy-v1.md](schemas/cohort-policy-v1.md): the Cycle 1 acquisition precommitment schema.
- [target-cohort-preparation-v1.md](schemas/target-cohort-preparation-v1.md): the generic provider-safe preparation driver for a saturated acquisition snapshot.
- [retained-cohort-extension-v1.md](schemas/retained-cohort-extension-v1.md): the noncharging bridge from an executed 100-case root to a combined 150-case cohort.
- [accepted-attempt-map-v1.md](schemas/accepted-attempt-map-v1.md): a committed post-execution selection amendment that does not modify the frozen inputs.
- [zero-cost-successor-v1.md](schemas/zero-cost-successor-v1.md): provider-free authentication of the 99-case ranked-reserve precursor plus the first fully cleared candidate in the frozen zero-cost order.
- [exact100-reserve-extension-v1.md](schemas/exact100-reserve-extension-v1.md): provider-free derivation of additional reserve capacity for an authenticated exact-100 successor whose frozen reserve cannot cover fresh disclosure quarantines.

**Spend authority and purchase**

- [corpus-completion-summary-v1.md](schemas/corpus-completion-summary-v1.md): deterministic terminal acquisition, adjudication, case-mix, and canonical purchase-ledger audit.
- [purchase-spend-summary-v1.md](schemas/purchase-spend-summary-v1.md): provider-free immutable accounting that distinguishes committed PACER exposure from provable actual charges.
- [provider-cycle-caps-v1.md](schemas/provider-cycle-caps-v1.md): the immutable pre-labeling commitment for provider and account spend.
- [provider-cycle-caps-successor-v1.md](schemas/provider-cycle-caps-successor-v1.md): provider-free derivation of the authority-enabled caps artifact from immutable legacy caps.
- [case-dev-purchase-policy-v2.md](schemas/case-dev-purchase-policy-v2.md): the sole public derived authority for a new official document-purchase session.
- [case-dev-purchase-policy-v1.md](schemas/case-dev-purchase-policy-v1.md): superseded by v2; retained for fixture and read-only compatibility and cannot mint purchase authority.
- [clearance-replacement-v1.md](schemas/clearance-replacement-v1.md): the frozen canonical order used when a purchased document fails disclosure clearance.
- [resolved-post-recovery-v4.md](schemas/resolved-post-recovery-v4.md): a recovered public document purchased directly through CourtListener RECAP Fetch, with no broker receipt history.
- [recap-fetch-quarantine-recovery-v1.md](schemas/recap-fetch-quarantine-recovery-v1.md): the noncharging exact partition of recoverable purchase material and canonical terminal-unavailable operations.
- [replacement-recovery-source-producer-v1.md](schemas/replacement-recovery-source-producer-v1.md): deterministic provider-free derivation of authenticated initial and successor recovery-source descriptors.

**Disclosure review and clearance**

- [disclosure-review-bundle-v1.md](schemas/disclosure-review-bundle-v1.md): the authenticated exact-byte human-review lineage required before a document enters parsing or labeling.
- [disclosure-model-review-v1.md](schemas/disclosure-model-review-v1.md): the single frozen non-evaluation acquisition reviewer model.
- [provenance-clearance-v3.md](schemas/provenance-clearance-v3.md): current routing contract, additive to v1 and v2; selected with `plan-disclosure-provenance --schema-version v3`.
- [provenance-clearance-v2.md](schemas/provenance-clearance-v2.md): the legacy v2 routing artifacts and run-card shape, preserved when `--schema-version` is omitted.
- [provenance-clearance-v1.md](schemas/provenance-clearance-v1.md): the original provenance-first routing contract, retained for historical artifacts.
- [provenance-public-marker-clearance-v1.md](schemas/provenance-public-marker-clearance-v1.md): policy-bound provider-free clearance for exact recovered-public marker-only rows.
- [provenance-quarantine-clearance-v1.md](schemas/provenance-quarantine-clearance-v1.md): the provider-free terminal alternative to exception review for a v3 routing plan.

**Stage A review and labeling**

- [finalized-prediction-units-v3.md](schemas/finalized-prediction-units-v3.md): the authenticated Stage A successor contract that admits a structurally omitted unit without deriving it from an unrelated raw unit.
- [finalized-prediction-units-v2.md](schemas/finalized-prediction-units-v2.md): the authenticated Stage A successor contract that records reviewed unit drops without rewriting the original unitization artifacts.
- [llm-stage-a-structural-review-terminal-escalation-v1.md](schemas/llm-stage-a-structural-review-terminal-escalation-v1.md): the provider-free, replay-authenticated John-review route after two byte-identical invalid structural-review responses.
- [llm-stage-a-structural-review-terminal-escalation-v2.md](schemas/llm-stage-a-structural-review-terminal-escalation-v2.md): the distinct provider-free John-review route after all three normal structural-review reconstruction attempts fail.

**Evaluation policy**

- [evaluation-policy-artifacts-v1.md](schemas/evaluation-policy-artifacts-v1.md): how decisions made before labeling or acquisition are separated from facts observed later.

## Committed Policy Data

These JSON files in this folder are the committed policy values the docs above describe: `publication-governance.json`, `labeling-policy.json`, `cohort-policy.json`, the dated `cohort-policy-cycle-1-target-100-2026-07-25*.json` decision and provenance records, and `disclosure-public-marker-policy-cycle-1-2026-08-06.json`.

The RECAP Fetch policy records live under [`manifests/recap-fetch-policies/`](../manifests/recap-fetch-policies/). These committed copies are immutable historical, host-bound provenance snapshots, not portable configuration or replay templates, and runtime code does not load them; operators must generate fresh policies for their own environment instead of rewriting the recorded paths.

Within that historical set, `purchase-policy.json` commits the exact approved budget-plan and selection bytes, while `attempt-policy.json` commits the canonical parsed JSON structures derived from those authenticated bytes. Their `budget_plan_sha256` and `selection_sha256` values therefore intentionally differ and must not be rewritten to match; each complete policy body, including its host-bound paths, is protected by its recorded `policy_sha256`.

Historical planning and review documents have been removed from the working tree; they remain available in git history.
