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
- [GitHub → AWS OIDC trust claims](github-aws-oidc-trust-claims.md): the verified condition-key surface behind the official roles' trust policies.
- [reproduce-or-audit.md](reproduce-or-audit.md): credential-free reproduction of public arithmetic and the deeper audit workflow.
- [Publication governance](publication-governance.md): current track-separation, arm, reporting, and non-affiliation rules.
- [Hugging Face benchmark publication](hugging-face-publication.md): manually gated access, immutable dataset revisions, native leaderboard registration, and short-lived automated publication.

## Release Security

- [PyPI trusted publishing and release environment](security/pypi-trusted-publishing.md): the registered trusted-publisher claim set, the layers that restrict publication to `v*` tags, and the revocation and recovery order.

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

### Adapter tracks

- [provider-baselines.md](adapters/provider-baselines.md): provider/runtime reference points and the publication terms they rest on.
- [published-api-key-profile.md](adapters/published-api-key-profile.md): Infisical layout for the portable `published-api-key` local-CLI profile.
- [Local CLI adapter manifest](schemas/local-cli-adapter-manifest-v1.md): the current generic manifest contract for local agentic CLI adapters.

## Public Release Schema Reference

Only the outcome-blinded forecast release, separately controlled labels release, and public/private release boundary below are active Bench contracts.

- [Public/private release boundary](release-inputs.md): the additive split between outcome-blinded public execution inputs and separately controlled labels.
- [Forecast release v1](release-inputs.md): canonical cases, prediction units, model-visible document indexes, packets, prompts, and byte commitments.
- [Labels release v1](release-inputs.md): separately bound unit outcomes and scoring policy with no forecast-execution API path.

## Model metadata

- [Model release dates](MODEL_RELEASE_DATES.md): model anchor sources and dates.
