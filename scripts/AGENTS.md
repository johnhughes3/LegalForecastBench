# Scripts

Utility scripts for release, infrastructure, and adapter tasks that are useful
from a checkout but do not belong in the installed `legalforecast` CLI.

## Current Scripts

- `release_check.py`: runs the full v0.1 alpha release gate: locked sync, formatting, linting, type checking, scoped public-API docstring coverage, the supported four-worker pytest suite, CLI smokes, fixture E2E, multi-harness no-network smokes, package build, package hashes, and installed wheel/sdist smokes.

  ```bash
  uv run scripts/release_check.py
  ```

  Use `--dry-run` to print the planned checks without executing them.

- `release_smoke.py`: prepares the deterministic fixture manifest and combines
  authenticated public receipt JSON into the JSONL input consumed by the strict
  score/report release path.

  ```bash
  uv run python scripts/release_smoke.py --help
  ```

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

- `recover_managed_transcript.py`: validates one provider-recorded successful
  managed SDK transcript against the frozen ledger cell and model registry, then
  restores its response payload for the normal provider-free replay path. It
  never opens provider transport.

  ```bash
  uv run scripts/recover_managed_transcript.py --help
  ```
