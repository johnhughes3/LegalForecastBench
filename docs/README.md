# Documentation

This directory is the public reference set for the pre-data alpha. It is kept
short on purpose. Generated reports, smoke-test transcripts, and release-gate
notes belong in `tmp/`, CI logs, or issues, not in the public docs tree.

## Start Here

- [Methodology](methodology.md): task definition, unitization, scoring,
  contamination controls, cadence, and result claims.
- [Data Card](data_card.md): intended data scope, exclusions, metadata,
  labeling, and current acquisition status.
- [Acquisition](acquisition.md): live-data blocker, no-paid defaults,
  Case.dev/CourtListener/PACER boundaries, and production acquisition commands.
- [Private Storage Layout](private_storage_layout.md): private packet bucket
  prefixes, manifest contract, access roles, hash rules, and takedown state.
- [Private Store Export](private_store_export.md): local acquisition-to-object
  store export command, staged object layout, and verification report.
- [Official Evaluation Environment](official_eval_environment.md): protected
  GitHub environment, OIDC packet-reader identity, and revocation steps.
- [Withdrawal Workflow](withdrawal_workflow.md): sealing-order takedown,
  withdrawal ledger, public errata, and future-run exclusion process.
- [Result Tiers](result_tiers.md): official, verified-community,
  community-unverified, and alpha-non-canonical result handling.

## Protocol Artifacts

- [Preregistration](preregistration.md)
- [Preregistration Template](preregistration_template.md)
- [Outcome Rules Appendix](outcome_rules_appendix.md)
- [Run Card Template](run_card_template.md)
- [Run Card Schema](run_card_schema.json)
- [Model Card Template](model_card_template.md)

## Release Notes

- [v0.1 alpha release notes](v0.1_alpha_release_notes.md)
- [Target model release dates](target_model_release_dates.md)

The repository does not yet publish public cases, labels, model scores, or an
official leaderboard. The current release is for reviewing the benchmark
machinery and methodology before live packet acquisition succeeds.
