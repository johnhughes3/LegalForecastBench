# Scripts

Utility scripts for release and reconstruction tasks that are useful from a
checkout but do not belong in the installed `legalforecast` CLI.

## Current Scripts

- `alpha_release_check.py`: runs the full v0.1 alpha release gate.

  ```bash
  uv run scripts/alpha_release_check.py
  ```

  Use `--dry-run` to print the planned checks without executing them.

- `build_alpha_release_bundle.py`: copies fixture E2E artifacts, selected
  release metadata, and optional package artifacts into an alpha release bundle.

  ```bash
  uv run scripts/build_alpha_release_bundle.py \
    --fixture-output-dir tmp/alpha-release-check/fixture-run \
    --dist-dir tmp/alpha-release-check/dist \
    --output-dir tmp/alpha-release-bundle
  ```

- `reconstruct_packets.py`: builds source-handle reconstruction plans from
  manifest JSONL and can verify locally reconstructed documents by SHA-256.

  ```bash
  uv run scripts/reconstruct_packets.py \
    --manifest tmp/cycle-manifest.jsonl \
    --output tmp/reconstruction-plan.json
  ```

  Add `--verify-dir tmp/reconstructed-documents` to write a verification report
  and return nonzero when any reconstructed document is missing or mismatched.

- `validate_local_assume_access.py`: runs a non-mutating local Granted/AWS
  smoke test for the maintainer profile split without printing bucket names or
  account IDs. Profile and bucket values come from the private runbook or local
  vault, not from this repository.

  ```bash
  export LFB_BEDROCK_ASSUME_PROFILE=<from-private-runbook>
  export LFB_LOCAL_S3_ASSUME_PROFILE=<from-private-runbook>
  export LFB_PACKET_BUCKET=<from-private-vault>
  export LFB_RESULTS_BUCKET=<from-private-vault>
  uv run scripts/validate_local_assume_access.py
  ```
