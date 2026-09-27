# Documentation Index

This index covers the current public contracts, operator guides, and reproducible research context for LegalForecastBench. The official-run runbook and reproduction guide are checked against the CLI by automated tests. Corrections are welcome as issues or pull requests.

## Start Here

| If you want to… | Read |
| --- | --- |
| Understand what the benchmark measures and how | [METHODS.md](METHODS.md) |
| Reproduce or audit a published result | [reproduce-or-audit.md](reproduce-or-audit.md) |
| Know what may and may not be claimed publicly | [publication-governance.md](publication-governance.md) |
| Operate a protected official cycle | [official-run-runbook.md](official-run-runbook.md) |
| Submit a community harness comparison | [community-contributor-guide.md](community-contributor-guide.md), then [multiharness-adapter-spec.md](multiharness/adapter-spec.md) and [community-submissions.md](community-submissions.md) |

## Official Benchmark

- [METHODS.md](METHODS.md): eval-card-grade methods — construct, frozen inputs, leakage controls, metrics, inference, related work, human-baseline status, limitations, and withdrawal policy.
- [Contamination-tier reporting](contamination-tier-reporting.md): the mechanical rule that distinguishes contamination-resistant scores from preliminary (non-contamination-resistant) scores — both official, viable results — and the paired drift metric between them.
- [official-run-runbook.md](official-run-runbook.md): the public release boundary — immutable inputs, protected forecast/fan-in workflows, strict scoring, reporting, and hold conditions.
- [reproduce-or-audit.md](reproduce-or-audit.md): credential-free reproduction of public arithmetic and the deeper audit workflow.
- [Website data contract](site-data.md): public score exports, generated TypeScript types, frontend integration, and withdrawal behavior.
- [Publication governance](publication-governance.md): current track-separation, arm, reporting, and non-affiliation rules.
- [Hugging Face benchmark publication](hugging-face-publication.md): manually gated access, immutable dataset revisions, native leaderboard registration, and short-lived automated publication.

- [Jev one-shot condition](jev-mode.md): unchanged prediction units with full text or persisted Luna document summaries.

## Research References

- [AI-generated Harvey LAB litigation audit](harvey-lab-audit/litigation-dispute-resolution/README.md): unverified, human-steered reference analysis of rubric and grading drift, with model provenance and reports for 52 tasks. Inclusion is not verification; findings verified for public discussion will be described separately on the public-facing site.

<details>
<summary>Audit report file index (AI-generated and unverified)</summary>

- **Audit overview:** [README](harvey-lab-audit/litigation-dispute-resolution/README.md) · [index](harvey-lab-audit/litigation-dispute-resolution/index.md) · [initial-grade-observations](harvey-lab-audit/litigation-dispute-resolution/initial-grade-observations.md)
- **batch-1:** [summary](harvey-lab-audit/litigation-dispute-resolution/batch-1/summary.md)
- **batch-1/analyze-counterparty-motion-to-dismiss:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-1/analyze-counterparty-motion-to-dismiss/README.md) · [audit](harvey-lab-audit/litigation-dispute-resolution/batch-1/analyze-counterparty-motion-to-dismiss/audit.md)
- **batch-1/build-litigation-case-timeline:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-1/build-litigation-case-timeline/README.md) · [audit](harvey-lab-audit/litigation-dispute-resolution/batch-1/build-litigation-case-timeline/audit.md)
- **batch-1/draft-conflict-check-memorandum:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-1/draft-conflict-check-memorandum/README.md) · [audit](harvey-lab-audit/litigation-dispute-resolution/batch-1/draft-conflict-check-memorandum/audit.md)
- **batch-1/draft-interrogatories:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-1/draft-interrogatories/README.md) · [audit](harvey-lab-audit/litigation-dispute-resolution/batch-1/draft-interrogatories/audit.md)
- **batch-1/draft-motion-in-limine-to-exclude-expert-testimony-and-prejudicial-evidence:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-1/draft-motion-in-limine-to-exclude-expert-testimony-and-prejudicial-evidence/README.md) · [audit](harvey-lab-audit/litigation-dispute-resolution/batch-1/draft-motion-in-limine-to-exclude-expert-testimony-and-prejudicial-evidence/audit.md)
- **batch-1/draft-requests-for-production:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-1/draft-requests-for-production/README.md) · [audit](harvey-lab-audit/litigation-dispute-resolution/batch-1/draft-requests-for-production/audit.md)
- **batch-1/extract-key-terms-from-counterparty-complaint:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-1/extract-key-terms-from-counterparty-complaint/README.md) · [audit](harvey-lab-audit/litigation-dispute-resolution/batch-1/extract-key-terms-from-counterparty-complaint/audit.md)
- **batch-1/identify-issues-in-counterparty-interrogatories:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-1/identify-issues-in-counterparty-interrogatories/README.md) · [audit](harvey-lab-audit/litigation-dispute-resolution/batch-1/identify-issues-in-counterparty-interrogatories/audit.md)
- **batch-1/review-litigation-invoice-against-outside-counsel-billing-guidelines:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-1/review-litigation-invoice-against-outside-counsel-billing-guidelines/README.md) · [audit](harvey-lab-audit/litigation-dispute-resolution/batch-1/review-litigation-invoice-against-outside-counsel-billing-guidelines/audit.md)
- **batch-2:** [summary](harvey-lab-audit/litigation-dispute-resolution/batch-2/summary.md)
- **batch-2/analyze-counterparty-requests-for-production-for-objectionable-and-overbroad-discovery-demands:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-2/analyze-counterparty-requests-for-production-for-objectionable-and-overbroad-discovery-demands/README.md) · [findings](harvey-lab-audit/litigation-dispute-resolution/batch-2/analyze-counterparty-requests-for-production-for-objectionable-and-overbroad-discovery-demands/findings.md)
- **batch-2/categorize-document-production-set-by-relevance-and-privilege:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-2/categorize-document-production-set-by-relevance-and-privilege/README.md) · [findings](harvey-lab-audit/litigation-dispute-resolution/batch-2/categorize-document-production-set-by-relevance-and-privilege/findings.md)
- **batch-2/draft-counterclaim-against-plaintiff-for-breach-of-joint-development-agreement:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-2/draft-counterclaim-against-plaintiff-for-breach-of-joint-development-agreement/README.md) · [findings](harvey-lab-audit/litigation-dispute-resolution/batch-2/draft-counterclaim-against-plaintiff-for-breach-of-joint-development-agreement/findings.md)
- **batch-2/draft-jury-instructions:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-2/draft-jury-instructions/README.md) · [findings](harvey-lab-audit/litigation-dispute-resolution/batch-2/draft-jury-instructions/findings.md)
- **batch-2/draft-motion-to-compel-discovery-responses:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-2/draft-motion-to-compel-discovery-responses/README.md) · [findings](harvey-lab-audit/litigation-dispute-resolution/batch-2/draft-motion-to-compel-discovery-responses/findings.md)
- **batch-2/draft-responses-to-interrogatories:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-2/draft-responses-to-interrogatories/README.md) · [findings](harvey-lab-audit/litigation-dispute-resolution/batch-2/draft-responses-to-interrogatories/findings.md)
- **batch-2/extract-privileged-communications-from-production-set:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-2/extract-privileged-communications-from-production-set/README.md) · [findings](harvey-lab-audit/litigation-dispute-resolution/batch-2/extract-privileged-communications-from-production-set/findings.md)
- **batch-2/identify-issues-in-matter-budget-proposal:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-2/identify-issues-in-matter-budget-proposal/README.md) · [findings](harvey-lab-audit/litigation-dispute-resolution/batch-2/identify-issues-in-matter-budget-proposal/findings.md)
- **batch-2/review-outside-counsel-engagement-letter-for-problematic-terms:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-2/review-outside-counsel-engagement-letter-for-problematic-terms/README.md) · [findings](harvey-lab-audit/litigation-dispute-resolution/batch-2/review-outside-counsel-engagement-letter-for-problematic-terms/findings.md)
- **batch-3:** [summary](harvey-lab-audit/litigation-dispute-resolution/batch-3/summary.md)
- **batch-3/analyze-counterpartys-motion-for-summary-judgment:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-3/analyze-counterpartys-motion-for-summary-judgment/README.md) · [audit](harvey-lab-audit/litigation-dispute-resolution/batch-3/analyze-counterpartys-motion-for-summary-judgment/audit.md)
- **batch-3/compare-document-production-against-discovery-requests:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-3/compare-document-production-against-discovery-requests/README.md) · [audit](harvey-lab-audit/litigation-dispute-resolution/batch-3/compare-document-production-against-discovery-requests/audit.md)
- **batch-3/draft-defective-industrial-equipment-product-liability:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-3/draft-defective-industrial-equipment-product-liability/README.md) · [audit](harvey-lab-audit/litigation-dispute-resolution/batch-3/draft-defective-industrial-equipment-product-liability/audit.md)
- **batch-3/draft-litigation-discovery-responses:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-3/draft-litigation-discovery-responses/README.md) · [audit](harvey-lab-audit/litigation-dispute-resolution/batch-3/draft-litigation-discovery-responses/audit.md)
- **batch-3/draft-motion-to-dismiss-brief:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-3/draft-motion-to-dismiss-brief/README.md) · [audit](harvey-lab-audit/litigation-dispute-resolution/batch-3/draft-motion-to-dismiss-brief/audit.md)
- **batch-3/draft-responses-to-requests-for-production:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-3/draft-responses-to-requests-for-production/README.md) · [audit](harvey-lab-audit/litigation-dispute-resolution/batch-3/draft-responses-to-requests-for-production/audit.md)
- **batch-3/extract-scope-terms-from-matter-plan:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-3/extract-scope-terms-from-matter-plan/README.md) · [audit](harvey-lab-audit/litigation-dispute-resolution/batch-3/extract-scope-terms-from-matter-plan/audit.md)
- **batch-3/research-corporate-veil-piercing-standards-across-target-jurisdictions:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-3/research-corporate-veil-piercing-standards-across-target-jurisdictions/README.md) · [audit](harvey-lab-audit/litigation-dispute-resolution/batch-3/research-corporate-veil-piercing-standards-across-target-jurisdictions/audit.md)
- **batch-3/review-privilege-log-clawback-review:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-3/review-privilege-log-clawback-review/README.md) · [audit](harvey-lab-audit/litigation-dispute-resolution/batch-3/review-privilege-log-clawback-review/audit.md)
- **batch-4:** [grade-audit](harvey-lab-audit/litigation-dispute-resolution/batch-4/grade-audit.md) · [summary](harvey-lab-audit/litigation-dispute-resolution/batch-4/summary.md)
- **batch-4/assess-litigation-hold-scope-for-custodian-identification:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-4/assess-litigation-hold-scope-for-custodian-identification/README.md) · [findings](harvey-lab-audit/litigation-dispute-resolution/batch-4/assess-litigation-hold-scope-for-custodian-identification/findings.md)
- **batch-4/draft-answer-to-breach-of-contract-complaint:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-4/draft-answer-to-breach-of-contract-complaint/README.md) · [findings](harvey-lab-audit/litigation-dispute-resolution/batch-4/draft-answer-to-breach-of-contract-complaint/findings.md)
- **batch-4/draft-deposition-outline:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-4/draft-deposition-outline/README.md) · [findings](harvey-lab-audit/litigation-dispute-resolution/batch-4/draft-deposition-outline/findings.md)
- **batch-4/draft-litigation-hold-notice-for-new-product-liability-matter:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-4/draft-litigation-hold-notice-for-new-product-liability-matter/README.md) · [findings](harvey-lab-audit/litigation-dispute-resolution/batch-4/draft-litigation-hold-notice-for-new-product-liability-matter/findings.md)
- **batch-4/draft-opposition-to-motion-for-summary-judgment:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-4/draft-opposition-to-motion-for-summary-judgment/README.md) · [findings](harvey-lab-audit/litigation-dispute-resolution/batch-4/draft-opposition-to-motion-for-summary-judgment/findings.md)
- **batch-4/draft-witness-examination-outline:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-4/draft-witness-examination-outline/README.md) · [findings](harvey-lab-audit/litigation-dispute-resolution/batch-4/draft-witness-examination-outline/findings.md)
- **batch-4/identify-excessive-or-duplicative-research-charges-in-litigation-invoice:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-4/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/README.md) · [findings](harvey-lab-audit/litigation-dispute-resolution/batch-4/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/findings.md)
- **batch-4/research-ucc-warranty-disclaimer-requirements-for-new-product-launch:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-4/research-ucc-warranty-disclaimer-requirements-for-new-product-launch/README.md) · [findings](harvey-lab-audit/litigation-dispute-resolution/batch-4/research-ucc-warranty-disclaimer-requirements-for-new-product-launch/findings.md)
- **batch-4/verify-disbursement-charges-against-billing-guidelines:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-4/verify-disbursement-charges-against-billing-guidelines/README.md) · [findings](harvey-lab-audit/litigation-dispute-resolution/batch-4/verify-disbursement-charges-against-billing-guidelines/findings.md)
- **batch-5:** [summary](harvey-lab-audit/litigation-dispute-resolution/batch-5/summary.md)
- **batch-5/assess-reasonableness-of-staffing-levels-on-litigation-invoice:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-5/assess-reasonableness-of-staffing-levels-on-litigation-invoice/README.md) · [audit](harvey-lab-audit/litigation-dispute-resolution/batch-5/assess-reasonableness-of-staffing-levels-on-litigation-invoice/audit.md)
- **batch-5/draft-case-assessment-memorandum:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-5/draft-case-assessment-memorandum/README.md) · [audit](harvey-lab-audit/litigation-dispute-resolution/batch-5/draft-case-assessment-memorandum/audit.md)
- **batch-5/draft-discovery-plan-memorandum:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-5/draft-discovery-plan-memorandum/README.md) · [audit](harvey-lab-audit/litigation-dispute-resolution/batch-5/draft-discovery-plan-memorandum/audit.md)
- **batch-5/draft-motion-for-preliminary-injunction:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-5/draft-motion-for-preliminary-injunction/README.md) · [audit](harvey-lab-audit/litigation-dispute-resolution/batch-5/draft-motion-for-preliminary-injunction/audit.md)
- **batch-5/draft-opposition-to-motion-to-dismiss:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-5/draft-opposition-to-motion-to-dismiss/README.md) · [audit](harvey-lab-audit/litigation-dispute-resolution/batch-5/draft-opposition-to-motion-to-dismiss/audit.md)
- **batch-5/extract-key-admissions-from-deposition-transcript:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-5/extract-key-admissions-from-deposition-transcript/README.md) · [audit](harvey-lab-audit/litigation-dispute-resolution/batch-5/extract-key-admissions-from-deposition-transcript/audit.md)
- **batch-5/identify-government-subpoena-issues:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-5/identify-government-subpoena-issues/README.md) · [audit](harvey-lab-audit/litigation-dispute-resolution/batch-5/identify-government-subpoena-issues/audit.md)
- **batch-5/review-counterpartys-proposed-jury-instructions:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-5/review-counterpartys-proposed-jury-instructions/README.md) · [audit](harvey-lab-audit/litigation-dispute-resolution/batch-5/review-counterpartys-proposed-jury-instructions/audit.md)
- **batch-6:** [summary](harvey-lab-audit/litigation-dispute-resolution/batch-6/summary.md)
- **batch-6/assess-settlement-value-range:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-6/assess-settlement-value-range/README.md) · [findings](harvey-lab-audit/litigation-dispute-resolution/batch-6/assess-settlement-value-range/findings.md) · [summary](harvey-lab-audit/litigation-dispute-resolution/batch-6/assess-settlement-value-range/summary.md)
- **batch-6/draft-complaint:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-6/draft-complaint/README.md) · [findings](harvey-lab-audit/litigation-dispute-resolution/batch-6/draft-complaint/findings.md) · [summary](harvey-lab-audit/litigation-dispute-resolution/batch-6/draft-complaint/summary.md)
- **batch-6/draft-federal-complaint-drafting:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-6/draft-federal-complaint-drafting/README.md) · [findings](harvey-lab-audit/litigation-dispute-resolution/batch-6/draft-federal-complaint-drafting/findings.md) · [summary](harvey-lab-audit/litigation-dispute-resolution/batch-6/draft-federal-complaint-drafting/summary.md)
- **batch-6/draft-motion-for-summary-judgment:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-6/draft-motion-for-summary-judgment/README.md) · [findings](harvey-lab-audit/litigation-dispute-resolution/batch-6/draft-motion-for-summary-judgment/findings.md) · [summary](harvey-lab-audit/litigation-dispute-resolution/batch-6/draft-motion-for-summary-judgment/summary.md)
- **batch-6/draft-pretrial-statement:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-6/draft-pretrial-statement/README.md) · [findings](harvey-lab-audit/litigation-dispute-resolution/batch-6/draft-pretrial-statement/findings.md) · [summary](harvey-lab-audit/litigation-dispute-resolution/batch-6/draft-pretrial-statement/summary.md)
- **batch-6/extract-key-obligations-from-litigation-hold-and-document-preservation-notice:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-6/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/README.md) · [findings](harvey-lab-audit/litigation-dispute-resolution/batch-6/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/findings.md) · [summary](harvey-lab-audit/litigation-dispute-resolution/batch-6/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/summary.md)
- **batch-6/identify-issues-in-counterparty-complaint:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-6/identify-issues-in-counterparty-complaint/README.md) · [findings](harvey-lab-audit/litigation-dispute-resolution/batch-6/identify-issues-in-counterparty-complaint/findings.md) · [summary](harvey-lab-audit/litigation-dispute-resolution/batch-6/identify-issues-in-counterparty-complaint/summary.md)
- **batch-6/review-document-production-set-for-attorney:** [README](harvey-lab-audit/litigation-dispute-resolution/batch-6/review-document-production-set-for-attorney/README.md) · [findings](harvey-lab-audit/litigation-dispute-resolution/batch-6/review-document-production-set-for-attorney/findings.md) · [summary](harvey-lab-audit/litigation-dispute-resolution/batch-6/review-document-production-set-for-attorney/summary.md)
- **grade-motion:** [coverage](harvey-lab-audit/litigation-dispute-resolution/grade-motion/coverage.md) · [findings](harvey-lab-audit/litigation-dispute-resolution/grade-motion/findings.md) · [summary](harvey-lab-audit/litigation-dispute-resolution/grade-motion/summary.md)

</details>

## Corpus Handoff Boundary

Corpus construction, private source bytes, selection, unitization, and quality control are owned by the companion LegalForecastCorpus repository. This public repository receives only immutable, outcome-blinded release inputs through the documented [public/private release boundary](release-inputs.md).

- [Commitment contracts](commitment-contracts.md): named canonical-byte, digest-representation, and schema-domain APIs for retained public release code.

## Community Multi-Harness (non-official)

The multi-harness layer is a separate, non-official track. Its results never rank alongside official results.

- [community-contributor-guide.md](community-contributor-guide.md): install, probe, select, run, interrupt, resume, validate, and package from a dedicated environment.
- [multiharness-adapter-spec.md](multiharness/adapter-spec.md): the community adapter contract.
- [community-submissions.md](community-submissions.md): submission packaging, attestations, credits, funding policy, and PR intake.
- [harness-efficiency-observations.md](harness-efficiency-observations.md): receipt-backed duration, cost, and token accounting published as peer columns.
- [Multiharness contracts](multiharness/contracts.md): the current sealed-deliverable, evaluation, scoring, identity, compatibility, and Harvey LAB source boundaries.
- [multiharness-receipt-authority.md](multiharness/receipt-authority.md): the external Ed25519 evaluator-issuer seam and credential-free executable probe procedure.
- [Claude Code terminal release run](multiharness/terminal-release.md): provider-free reproduction of the rootless CLI, case-document, gateway, and complete-unit scoring path.

### Adapter tracks

- [provider-baselines.md](adapters/provider-baselines.md): provider/runtime reference points and the publication terms they rest on.
- [hermes-agent.md](adapters/hermes-agent.md): pinned Hermes bridge, isolated state, host-owned task tools, and offline verification.
- [Local CLI adapter manifest](schemas/local-cli-adapter-manifest-v1.md): the current generic manifest contract for local agentic CLI adapters.

## Public Release Schema Reference

Only the outcome-blinded forecast release, separately controlled labels release, and public/private release boundary below are active Bench contracts.

- [Public/private release boundary](release-inputs.md): the additive split between outcome-blinded public execution inputs and separately controlled labels.
- [Forecast release v1](release-inputs.md): canonical cases, prediction units, model-visible document indexes, packets, prompts, and byte commitments.
- [Labels release v1](release-inputs.md): separately bound unit outcomes and scoring policy with no forecast-execution API path.

## Model metadata

- [Model release dates](MODEL_RELEASE_DATES.md): model anchor sources and dates.
