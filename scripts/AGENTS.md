# Scripts

Utility scripts for release and reconstruction tasks that are useful from a
checkout but do not belong in the installed `legalforecast` CLI.

## Current Scripts

- `release_check.py`: runs the full v0.1 alpha release gate: locked sync, formatting, linting, type checking, scoped public-API docstring coverage, the supported four-worker pytest suite, CLI smokes, fixture E2E, multi-harness no-network smokes, package build, package hashes, and installed wheel/sdist smokes.

  ```bash
  uv run scripts/release_check.py
  ```

  Use `--dry-run` to print the planned checks without executing them.

- `dev-check-recovery-vertical-slice.sh`: runs the provider-free Cycle 1 recovery developer check. No arguments run the full focused regression and public-capsule check; `--quick --manifest <path>` runs only the real-lineage preflight while iterating, and `--require-real-lineage` prevents fixture-only success before merge. Use `--json` for a stable summary on stdout; child diagnostics are written to stderr.

  ```bash
  scripts/dev-check-recovery-vertical-slice.sh --quick --manifest <cycle-preflight-manifest.json>
  scripts/dev-check-recovery-vertical-slice.sh --manifest <cycle-preflight-manifest.json> --require-real-lineage
  ```

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

- `smoke_infisical_systemd_exit_status.py`: runs a provider-free user-systemd
  smoke proving that the acquisition Infisical launcher preserves both status 0
  and a deliberate status 23 even when a fake sandbox wrapper masks the child.

  ```bash
  uv run scripts/smoke_infisical_systemd_exit_status.py \
    --output tmp/infisical-systemd-smoke-receipt.json
  ```

- `validate_flatten_local_luna.py`: validates the provider-free integrity
  summaries in local Luna result envelopes and emits the unchanged nested run
  records as `legalforecast score` JSONL input. It never creates outcome labels
  and refuses to overwrite an existing output.

  ```bash
  uv run python scripts/validate_flatten_local_luna.py \
    --results-dir <private-local-luna-results> \
    --output <private-runs.jsonl> \
    --expected-count 200 \
    --expected-registry-sha256 <registry-sha256>
  ```

  The compatibility escape hatch is identity-scoped and fail-closed by
  default. Use `--derive-missing-output-statuses-for CASE:ABLATION` only for a
  specifically audited legacy envelope whose unchanged run record permits
  deterministic re-derivation; it writes a separate output and never repairs
  the source envelope.

- `run_cycle1_gemini.py`: runs the supplementary Cycle 1 Gemini 3.7 Flash
  configuration through the shared authenticated local runner. Dry runs are
  provider-free; paid runs must be wrapped with
  `legalforecast.labeling.provider_environment --provider google` so only
  `GEMINI_API_KEY` enters the child.

  ```bash
  uv run python scripts/run_cycle1_gemini.py --help
  uv run python -m legalforecast.labeling.provider_environment --provider google -- \
    uv run python scripts/run_cycle1_gemini.py <run arguments>
  ```

- `validate_flatten_local.py`: generic provider-free validator for local model
  envelopes. It authenticates the expected model, registry, prompt commitments,
  and response/status summaries before emitting score-compatible JSONL. The
  Luna-specific validator remains available for backward compatibility.

  ```bash
  uv run python scripts/validate_flatten_local.py \
    --results-dir <private-results> --output <private-runs.jsonl> \
    --expected-count 200 --model-key google:gemini-3.7-flash \
    --expected-registry-sha256 <supplementary-registry-sha256> \
    --expected-prompt-commitments <frozen-run-record.json>
  ```

- `official_infra_contract.py`: fail-closed contract helper used by the protected infrastructure workflow to resolve reviewed import IDs, verify exact remote-state bindings, and reject destructive or unreviewed Terraform plans. Raw protected import IDs are accepted only through the workflow environment and are never printed.

  ```bash
  scripts/official_infra_contract.py --help
  scripts/official_infra_contract.py resolve-import --help
  scripts/official_infra_contract.py state-binding --help
  scripts/official_infra_contract.py validate-plan --help
  ```

- `probe_claude_code_native_containment.py`: pending, host-specific zero-provider-spend characterization of Claude Code's native loop inside a whole-process systemd `DynamicUser` boundary. The outer probe requires independent source review, an exact approved source digest, and the documented sudo-gate stdout capture; it is not a portable contributor command and no successful receipt is currently claimed. See [the containment feasibility record](../docs/adapters/claude-code-native-containment.md).
