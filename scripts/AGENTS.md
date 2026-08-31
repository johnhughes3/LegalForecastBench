# Scripts

Utility scripts for release, infrastructure, and adapter tasks that are useful
from a checkout but do not belong in the installed `legalforecast` CLI.

## Current Scripts

- `release_check.py`: runs the full v0.1 alpha release gate: locked sync, formatting, linting, type checking, scoped public-API docstring coverage, the supported four-worker pytest suite, CLI smokes, fixture E2E, multi-harness no-network smokes, package build, package hashes, and installed wheel/sdist smokes.

  ```bash
  uv run scripts/release_check.py
  ```

  Use `--dry-run` to print the planned checks without executing them.

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

- `official_infra_contract.py`: fail-closed contract helper used by the protected infrastructure workflow to resolve reviewed import IDs, verify exact remote-state bindings, and reject destructive or unreviewed Terraform plans. Raw protected import IDs are accepted only through the workflow environment and are never printed.

  ```bash
  scripts/official_infra_contract.py --help
  scripts/official_infra_contract.py resolve-import --help
  scripts/official_infra_contract.py state-binding --help
  scripts/official_infra_contract.py validate-plan --help
  ```

- `probe_claude_code_native_containment.py`: pending, host-specific zero-provider-spend characterization of Claude Code's native loop inside a whole-process systemd `DynamicUser` boundary. The outer probe requires independent source review, an exact approved source digest, and the documented sudo-gate stdout capture; it is not a portable contributor command and no successful receipt is currently claimed. See [the containment feasibility record](../docs/adapters/claude-code-native-containment.md).
