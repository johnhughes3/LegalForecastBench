# Documentation

This directory is the public reference set for the pre-data alpha. The root
`README.md` is the quickstart; this file is only the map. Generated reports,
smoke-test transcripts, and release-gate notes belong in `tmp/`, CI logs, or
issues, not in the public docs tree.

## Canonical Sources

| Topic | Canonical doc |
| --- | --- |
| Benchmark task, unitization, scoring, validity, and leakage controls | [Methodology](methodology.md) |
| Cycle-level data scope, exclusions, metadata, labels, and reconstruction | [Data Card](data_card.md) |
| Live-data blocker, no-paid defaults, Case.dev/CourtListener/PACER boundaries, and acquisition commands | [Acquisition](acquisition.md) |
| Private packet bucket prefixes, manifests, access roles, hashes, and takedown state | [Private Storage Layout](private_storage_layout.md) |
| Local acquisition-to-object-store staging and verification | [Private Store Export](private_store_export.md) |
| Protected GitHub environment, OIDC packet-reader identity, and revocation | [Official Evaluation Environment](official_eval_environment.md) |
| Per-case artifact validation, publication bundle, and private-debug split | [Official Aggregation](official_aggregation.md) |
| Sealing-order takedown, withdrawal ledger, public errata, and future-run exclusion | [Withdrawal Workflow](withdrawal_workflow.md) |
| Official, verified-community, community-unverified, and alpha-non-canonical result handling | [Result Tiers](result_tiers.md) |
| Intended use, public-record handling, leakage, judge/party metadata, human review, and takedowns | [Ethics and Legal-Risk Note](ethics.md) |

## Protocol And Template Artifacts

- [Preregistration](preregistration.md): process and freeze order.
- [Preregistration Template](preregistration_template.md): human-readable cycle draft.
- [Outcome Rules Appendix](outcome_rules_appendix.md): edge-case outcome-label rules.
- [Run Card Template](run_card_template.md): human guide to run-card JSON.
- [Run Card Schema](run_card_schema.json): machine-readable run-card contract.
- [Model Card Template](model_card_template.md): public model/run disclosure template.

## Release Notes And Planning Appendices

- [v0.1 alpha release notes](v0.1_alpha_release_notes.md)
- [Target model release dates](target_model_release_dates.md)

The repository does not yet publish public cases, labels, model scores, or an
official leaderboard. The current release is for reviewing the benchmark
machinery and methodology before live packet acquisition succeeds.
