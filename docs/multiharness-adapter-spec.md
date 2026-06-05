# Multi-Harness Adapter Spec

The multi-harness package is an additive community benchmark layer under `legalforecast/multiharness/`. It does not replace official LegalForecastBench evaluation or official publication. Official results remain controlled by protected workflows and official aggregation; community harness results use separate schemas, separate registry files, and non-official public copy.

## Core Records

Canonical records live in `legalforecast.multiharness.spec`.

- `CanonicalTask`: one task projected into a common contract. Current families are `legalforecast_mtd`, `harvey_lab`, and `contract_only`; current scoring modes are `lfb_brier`, `lab_native`, and `contract_only`.
- `TaskIndex`: ordered task collection with `index_sha256` and `selection_namespace`.
- `TaskSelection`: deterministic selectors for family, task ID, case ID, candidate ID, ablation, LAB module, practice area, tags, seed, and limit.
- `AdapterManifest`: public adapter identity and command metadata.
- `AdapterCapabilities`: declared task families, scoring modes, sandbox-policy support, and a capabilities hash.
- `SandboxPolicy`: host-owned execution policy recorded for every row. The tool container network is disabled; provider egress, when allowed, is only a recorded host-adapter assumption.
- `RunRequest` and `RunResult`: canonical per-row request/result records.
- `ConformanceReport`: fixture-only adapter conformance result.

All public records are scanned by multi-harness validation for secret-like fields, provider account IDs, deprecated result-tier fields, and banned values such as `verified-community`, `community-unverified`, and `alpha-non-canonical`.

## Task Index Examples

Index a Harvey LAB checkout and select one corporate module shard:

```bash
uv run legalforecast multiharness tasks index \
  --suite harvey-lab \
  --lab-root "$HARVEY_LAB_ROOT" \
  --output tmp/multiharness/lab-index.json

uv run legalforecast multiharness tasks select \
  --index tmp/multiharness/lab-index.json \
  --module corporate \
  --limit 1 \
  --seed demo \
  --output tmp/multiharness/lab-selection.json
```

Index a LegalForecastBench packet subset:

```bash
uv run legalforecast multiharness tasks index \
  --suite lfb \
  --input tmp/fixture-run/packets.jsonl \
  --output tmp/multiharness/lfb-index.json

uv run legalforecast multiharness tasks select \
  --index tmp/multiharness/lfb-index.json \
  --family legalforecast_mtd \
  --limit 1 \
  --seed demo \
  --output tmp/multiharness/lfb-selection.json
```

The LAB examples require a user-supplied LAB checkout. Harvey LAB is a separate Harvey AI project and task corpus; credit and license language for any public-facing use must remain explicit, and final branding is subject to John Hughes/Legal Quants approval.

## First-Class Adapter Examples

The first-class adapter examples live under `examples/adapters/`.

- The LQ.AI fixture bridge is documented in `docs/adapters/lq-ai.md` and can be checked with `uv run legalforecast multiharness conformance --adapter-manifest examples/adapters/lq-ai/adapter-manifest.json --output-dir tmp/lq-ai-conformance`.
- The Hermes Agent fixture bridge is documented in `docs/adapters/hermes-agent.md` and can be checked with `uv run legalforecast multiharness conformance --adapter-manifest examples/adapters/hermes-agent/adapter-manifest.json --output-dir tmp/hermes-agent-conformance`.

## Command Adapter Protocol

Community adapters can be ordinary command-line programs. The host never invokes adapters through `shell=True`; commands are argv arrays from `AdapterManifest.command`.

Minimal manifest:

```json
{
  "schema_version": "legalforecast.multiharness.adapter_manifest.v1",
  "adapter_id": "example-cli",
  "display_name": "Example CLI Adapter",
  "adapter_version": "0.1.0",
  "command": ["uv", "run", "python", "examples/example_adapter.py"],
  "contributors": [
    {"role": "adapter_author", "name": "Example Team", "identifiers": {}}
  ]
}
```

The command must support two phases:

```bash
example-adapter capabilities --output adapter-capabilities.json
example-adapter run --request request.json --output result.json --workspace row-workspace
```

`capabilities` writes a valid `AdapterCapabilities` JSON object. `run` reads a `RunRequest`, writes a `RunResult`, and keeps stdout/stderr/private logs out of public summaries. Public artifacts must use safe relative paths and SHA-256 hashes.

Inspect and run conformance:

```bash
uv run legalforecast multiharness adapters inspect \
  --adapter-manifest adapter-manifest.json \
  --output-dir tmp/multiharness/inspect

uv run legalforecast multiharness conformance \
  --adapter-manifest adapter-manifest.json \
  --output-dir tmp/multiharness/conformance
```

The conformance suite is fixture-only by default. It must not require provider credentials, Docker, Podman, network access, or a real LAB checkout.

## Running A Matrix

Dry-run a selected matrix without invoking adapters or containers:

```bash
uv run legalforecast multiharness run \
  --task-index tmp/multiharness/lab-index.json \
  --selection tmp/multiharness/lab-selection.json \
  --adapter-manifest adapter-manifest.json \
  --model-key provider:model-id \
  --output-dir tmp/multiharness/run \
  --dry-run
```

Run the matrix:

```bash
uv run legalforecast multiharness run \
  --task-index tmp/multiharness/lab-index.json \
  --selection tmp/multiharness/lab-selection.json \
  --adapter-manifest adapter-manifest.json \
  --model-key provider:model-id \
  --sandbox-policy-id demo-sandbox \
  --sandbox-backend docker \
  --sandbox-image python:3.12-slim \
  --output-dir tmp/multiharness/run
```

If a provider CLI or subscription is used, the adapter must record the auth mode and terms assumption in its public-safe metadata. Do not put API keys, account IDs, refresh tokens, raw transcripts, private logs, sealed material, or source documents in public artifacts.

## Troubleshooting

- `adapter capabilities ID does not match manifest`: the adapter wrote capabilities for a different `adapter_id` or version.
- `run result request_id does not match request`: the adapter did not echo the exact request row.
- `result record passed public-safety validation` failure: remove secret-like fields, provider account IDs, deprecated tier labels, or unsafe public artifact paths.
- LAB bridge reports missing `--lab-root` or `--output-dir`: the supplied LAB command does not expose the root/output controls this bridge needs. Use a fixture command or update the command manifest until the real LAB CLI supports those flags.
- Container backend unavailable: current CI coverage is fixture-only. Live tool-container enforcement is host-owned and should be tested separately before a real public run.
