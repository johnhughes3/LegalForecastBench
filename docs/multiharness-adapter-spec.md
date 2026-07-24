# Multi-Harness Adapter Spec

The multi-harness package is an additive community benchmark layer under `legalforecast/multiharness/`. It does not replace official LegalForecastBench evaluation or official publication. Official results remain controlled by protected workflows and official aggregation; community harness results use separate schemas, separate registry files, and non-official public copy.

## Core Records

Canonical records live in `legalforecast.multiharness.spec`.

- `CanonicalTask`: one task projected into a common contract. Current families are `legalforecast_mtd`, `harvey_lab`, and `contract_only`; current scoring modes are `lfb_brier`, `lab_native`, and `contract_only`.
- `TaskIndex`: ordered task collection with `index_sha256` and `selection_namespace`.
- `TaskSelection`: deterministic selectors for family, task ID, case ID, candidate ID, ablation, LAB module, practice area, tags, seed, and limit.
- `AdapterManifest`: public adapter identity and command metadata.
- `AdapterCapabilities`: declared task families, scoring modes, sandbox-policy support, and a capabilities hash. The hash commits to semantic capability inputs and must be stable across equivalent checkouts; absolute roots, launcher paths, workspaces, and other machine-local paths belong only in private probe artifacts. The Harvey LAB bridge derives its public-safe identity from the checkout's Git subtree plus its exact dirty/untracked overlay and a path-normalized digest of the launcher argv and file bytes. It rechecks that identity immediately before execution, writes the path-bearing probe only under `private-logs/`, and materializes only task bytes whose size and SHA-256 match the indexed artifacts.
- `SandboxPolicy`: host-owned execution policy recorded for every row. The planned tool container uses no network; live tool-container enforcement remains unimplemented, and provider egress, when allowed, is a host-adapter assumption.
- `RunRequest` and `RunResult`: canonical per-row request/result records.
- `RunManifest`: deterministic run-level provenance for the scheduled task, adapter, model, selection, and sandbox matrix.
- `ConformanceReport`: fixture-only adapter conformance result.
- `CommunitySubmission` and `CommunityAggregate`: reviewed community metadata and generated comparison bundles. Community package files use the versioned schemas in `legalforecast.multiharness.community`.

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
- The OpenClaw fixture bridge is documented in `docs/adapters/openclaw.md` and can be checked with `uv run legalforecast multiharness conformance --adapter-manifest examples/adapters/openclaw/adapter-manifest.json --output-dir tmp/openclaw-conformance`.
- The OpenAI Responses and Claude Agent SDK fixture baselines are documented in `docs/adapters/provider-baselines.md` and can be checked with the manifests under `examples/adapters/openai-responses/` and `examples/adapters/claude-agent-sdk/`.

## Command Adapter Protocol

Community adapters can be ordinary command-line programs. The host never invokes adapters through `shell=True`; commands are argv arrays from `AdapterManifest.command`.

Command-adapter and Harvey LAB subprocesses receive an environment allowlist, not the caller's full host environment. The `run` phase receives only provider variables named by `SandboxPolicy.allowed_provider_env_vars`, plus `PATH`, `LC_CTYPE`, and private per-workspace `HOME`/XDG directories. Capability probes receive only those runtime essentials because they must not require provider credentials. The caller's normal home directory is therefore unavailable through ordinary home/config credential discovery; live adapters must use explicitly allowed environment variables until a separate file-credential policy exists. Declared variables must be set and nonempty, and their exact values are rejected from public result/error records. Because provider-variable grants are currently run-wide rather than row-scoped, credentialed runs require `provider_egress_host_only` and exactly one adapter/model pair; use separate runs for additional pairs.

The host starts each command adapter in a new POSIX session and performs best-effort cleanup by signaling the adapter leader's original process group. A descendant that calls `setsid()`, changes process group, or otherwise daemonizes can leave that group and retain the run environment after group cleanup. The private receipt status `process_group_cleanup_requested` and fields `termination_requested` and `forced_kill` describe signals delivered to the original group; they do not prove that every descendant stopped. Conformance output and these receipts are therefore not whole-process containment evidence. Stronger host-owned containment is tracked in [issue #267](https://github.com/johnhughes3/LegalForecastBench/issues/267); any profile that requires whole-process containment must fail closed until that boundary is implemented and attested.

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

`capabilities` writes a valid `AdapterCapabilities` JSON object. The conformance suite currently requires `supports_sandbox_policy: true`, because every fixture request includes a host-owned `SandboxPolicy`.

`run` reads a `RunRequest`, writes a `RunResult`, and keeps stdout/stderr/private logs out of public summaries. Each result public summary must echo the received `sandbox_policy_id` so reviewers can verify which host policy was recorded for the row. Public artifacts must use safe relative paths and SHA-256 hashes.

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

Live tool-container execution remains open. The current adapter protocol defines host-side `capabilities` and `run` commands, but it does not define a tool command or RPC that the host can execute inside the planned container and connect back to the adapter. Launching an unrelated image entrypoint would not create a meaningful execution boundary, so the runner continues to record `sandbox.plan.json` without claiming that adapter/tool work ran there.

If a provider CLI or subscription is used, the adapter must record the auth mode and terms assumption in its public-safe metadata. Do not put API keys, account IDs, refresh tokens, raw transcripts, private logs, sealed material, or source documents in public artifacts.

## Troubleshooting

- `adapter capabilities ID does not match manifest`: the adapter wrote capabilities for a different `adapter_id` or version.
- `run result request_id does not match request`: the adapter did not echo the exact request row.
- `result record passed public-safety validation` failure: remove secret-like fields, provider account IDs, deprecated tier labels, or unsafe public artifact paths.
- LAB bridge reports missing `--lab-root` or `--output-dir`: the supplied LAB command does not expose the root/output controls this bridge needs. Use a fixture command or update the command manifest until the real LAB CLI supports those flags.
- `LAB root must be a tracked path in a readable Git checkout`: use a Git checkout whose selected LAB root exists at `HEAD`; untracked standalone directories are intentionally rejected because they cannot provide a cheap, stable publication identity.
- `LAB capabilities changed after run planning`: the LAB source overlay, launcher, or semantic command arguments changed after the manifest was created. Start a new run so its compatibility hash describes the bytes that will execute.
- Container backend unavailable: the runner currently records a plan without checking or invoking the backend. Do not treat that plan as container-execution evidence; live tool-container enforcement still needs a tool command or RPC contract.
