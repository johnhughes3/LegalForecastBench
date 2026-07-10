# Scripts

Utility scripts for release and reconstruction tasks that are useful from a
checkout but do not belong in the installed `legalforecast` CLI.

## Current Scripts

- `release_check.py`: runs the full v0.1 alpha release gate: locked sync, formatting, linting, type checking, scoped public-API docstring coverage, tests, CLI smokes, fixture E2E, multi-harness no-network smokes, package build, package hashes, and installed wheel/sdist smokes.

  ```bash
  uv run scripts/release_check.py
  ```

  Use `--dry-run` to print the planned checks without executing them.

- `build_release_bundle.py`: copies fixture E2E artifacts, selected
  release metadata, and optional package artifacts into an alpha release bundle.

  ```bash
  uv run scripts/build_release_bundle.py \
    --fixture-output-dir tmp/release-check/fixture-run \
    --dist-dir tmp/release-check/dist \
    --output-dir tmp/release-bundle
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
  Use `--verify-packet-render-dir tmp/rebuilt-packets` to verify packet and prompt
  renders against the hashes published by the private-store exporter.

- `legalforecast.publication.run_input_manifest`: records late-bound locked-label
  hashes after packet export and before an official matrix fans out. It emits a
  new manifest, preserves the packet inputs, and refuses to replace a different
  existing labels commitment.

  ```bash
  uv run python -m legalforecast.publication.run_input_manifest freeze-labels \
    --manifest tmp/cycle.run-inputs.json \
    --labels tmp/cycle.labels.jsonl \
    --output tmp/cycle.run-inputs.frozen.json
  ```

- `validate_local_assume_access.py`: runs a non-mutating local Granted/AWS S3
  smoke test without printing bucket names or account IDs. Profile and bucket
  values come from the private runbook or local vault, not from this repository.

  ```bash
  export LFB_LOCAL_S3_ASSUME_PROFILE=<from-private-runbook>
  export LFB_PACKET_BUCKET=<from-private-vault>
  export LFB_RESULTS_BUCKET=<from-private-vault>
  uv run scripts/validate_local_assume_access.py
  ```
