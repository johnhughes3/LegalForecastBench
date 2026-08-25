# Multi-Harness Adapter Spec

The multi-harness package is an additive community benchmark layer under `legalforecast/multiharness/`. It does not replace official LegalForecastBench evaluation or official publication. Official results remain controlled by protected workflows and official aggregation; community harness results use separate schemas, separate registry files, and non-official public copy.

## Core Records

Canonical records live in `legalforecast.multiharness.spec`.

- `CanonicalTask`: one task projected into a common contract. Current families are `legalforecast_mtd`, `harvey_lab`, and `contract_only`; current scoring modes are `lfb_brier`, `lab_native`, and `contract_only`.
- `TaskIndex`: ordered task collection with `index_sha256` and `selection_namespace`.
- `TaskSelection`: deterministic selectors for family, task ID, case ID, candidate ID, ablation, LAB module, practice area, tags, seed, and limit.
- `AdapterManifest`: public adapter identity and command metadata.
- `AdapterCapabilities`: declared task families, scoring modes, sandbox-policy support, and a capabilities hash. The hash commits to semantic capability inputs and must be stable across equivalent checkouts; absolute roots, launcher paths, workspaces, and other machine-local paths belong only in private probe artifacts. The Harvey LAB bridge derives its public-safe identity from the checkout's Git subtree plus its exact dirty/untracked overlay and a path-normalized digest of the launcher argv and file bytes. It rechecks that identity immediately before execution, writes the path-bearing probe only under `private-logs/`, and materializes only task bytes whose size and SHA-256 match the indexed artifacts.
- `SandboxPolicy`: host-owned execution policy recorded for every row. Plan-only runs record the policy without claiming containment. Live-tool runs enforce a network-disabled, read-only, non-root container while provider egress and allowlisted credentials remain confined to the host adapter.
- `RunRequest` and `RunResult`: canonical per-row request/result records.
- `RunManifest`: deterministic run-level provenance for the scheduled task, adapter, model, selection, and sandbox matrix.
- `ConformanceReport`: fixture-only adapter conformance result.
- `CommunitySubmission` and `CommunityAggregate`: reviewed community metadata and generated comparison bundles. Community package files use the versioned schemas in `legalforecast.multiharness.community`.

All public records are scanned by multi-harness validation for secret-like fields, provider account IDs, and removed legacy publication-classification fields or values.

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

For the supported public/private boundary, index an already-issued immutable `forecast-release.v1` instead of reconstructing the legacy packet JSONL:

```bash
uv run legalforecast release issue-synthetic \
  --output-dir tmp/release-fixture

uv run legalforecast multiharness tasks index \
  --suite lfb \
  --forecast-release tmp/release-fixture/forecast-release.json \
  --artifact-root tmp/release-fixture \
  --solver-input-root tmp/private-release-inputs \
  --output tmp/multiharness/release-index.json
```

This command loads only the outcome-blinded forecast side. It authenticates every release artifact, projects one `CanonicalTask` per prediction unit, keeps prompt and packet bytes out of public task metadata, and writes the exact packet bytes plus the strict-UTF-8 prompt to a fresh private solver-input store. The private packet remains construction evidence and is not mounted into the solver; the solver receives only the exact committed prompt.

Release-backed rows use the existing `RunRequest`, `RunResult`, and LFB scoring projection. Every successful row emits `legalforecast.multiharness.release_harness_receipt.v1`, including a `should_score` commitment, so excluded units retain execution evidence without becoming scoring inputs. Only rows whose authenticated release unit has `should_score: true` emit public and private LFB scoring projections. The receipt binds release/unit and packet/prompt identity, adapter ID/version, neutral or native track, model key, tool policy and count, network policy, resource/time limits, a private-transcript commitment, the forecast-output commitment, and the prose-free normalized parser result. The private transcript semantically binds the exact request, packet, prompt, and forecast-output digests in addition to its own byte digest. Community packaging reconstructs both the receipt aggregate and the scoreable LFB aggregate from durable row request, result, transcript, forecast, and projection evidence, compares each run aggregate exactly, and packages the reconstructed snapshot rather than rereading mutable aggregate files. `treatment_id` includes the track and adapter identity, so neutral and native results cannot collapse into one scoring identity. Adding another adapter implements the solver-input-aware adapter seam and returns the standard private forecast artifact; it does not change `forecast-release.v1`.

The LAB examples require a user-supplied LAB checkout. Harvey LAB is a separate Harvey AI project and task corpus; credit and license language for any public-facing use must remain explicit, and final branding is subject to John Hughes/Legal Quants approval.

## First-Class Adapter Examples

The first-class adapter examples live under `examples/adapters/`.

- The LQ.AI fixture bridge is documented in `docs/adapters/lq-ai.md` and can be checked with `uv run legalforecast multiharness conformance --adapter-manifest examples/adapters/lq-ai/adapter-manifest.json --output-dir tmp/lq-ai-conformance`.
- The Hermes Agent fixture bridge is documented in `docs/adapters/hermes-agent.md` and can be checked with `uv run legalforecast multiharness conformance --adapter-manifest examples/adapters/hermes-agent/adapter-manifest.json --output-dir tmp/hermes-agent-conformance`.
- The OpenClaw fixture bridge is documented in `docs/adapters/openclaw.md` and can be checked with `uv run legalforecast multiharness conformance --adapter-manifest examples/adapters/openclaw/adapter-manifest.json --output-dir tmp/openclaw-conformance`.
- The real OpenAI Responses and Claude Agent SDK community baselines are documented in `docs/adapters/provider-baselines.md`. Both adapters support `legalforecast_mtd` with `lfb_brier`, advertise the v1 tool protocol, and keep their ordinary `run` paths credential-free and conformance-only; live provider execution uses `run-with-tools`. Their manifests live under `examples/adapters/openai-responses/` and `examples/adapters/claude-agent-sdk/`, while separate fixture manifests preserve the historical no-network examples.

## Command Adapter Protocol

Community adapters can be ordinary command-line programs. The host never invokes adapters through `shell=True`; commands are argv arrays from `AdapterManifest.command`.

Command-adapter and Harvey LAB subprocesses receive an environment allowlist, not the caller's full host environment. The `run` phase receives only provider variables named by `SandboxPolicy.allowed_provider_env_vars`, plus `PATH`, `LC_CTYPE`, and private per-workspace `HOME`/XDG directories. Capability probes receive only those runtime essentials because they must not require provider credentials. The caller's normal home directory is therefore unavailable through ordinary home/config credential discovery; live adapters must use explicitly allowed environment variables until a separate file-credential policy exists. Declared variables must be set and nonempty, and their exact values are rejected from public result/error records. Because provider-variable grants are currently run-wide rather than row-scoped, credentialed runs require `provider_egress_host_only` and exactly one adapter/model pair; use separate runs for additional pairs.

`SandboxPolicy.host_process_containment` selects one of two explicit lifecycle boundaries. `posix_process_group.v1` retains the compatibility behavior: the host starts the adapter in a new POSIX session and performs best-effort cleanup of the leader's original process group, but a descendant that calls `setsid()` can escape. `linux_systemd_scope_cgroup_v2.v1` requires Linux, unified cgroup v2, a working systemd user manager, pidfd support, and writable `cgroup.kill`; it never downgrades to process-group cleanup. Before resolving provider values, the host exercises a provider-free transient scope. The real adapter then starts behind a peer-credentialed control socket, and the host releases it only after binding the exact gate PID and nonce to the scope's `InvocationID`, `ControlGroup`, pidfd, and open cgroup descriptors. Provider values cross that private socket only after attestation, so they do not appear in `systemd-run` arguments, unit properties, or its initial environment.

For the stronger mode, cleanup sends graceful signals through pidfds read from the retained cgroup, uses the retained `cgroup.kill` descriptor if processes remain, and accepts completion only after the retained `cgroup.events` reports `populated 0` or the kernel removes the now-empty cgroup. The v2 private execution receipt records the requested mode, establishment result, systemd identity, whether cleanup was requested, TERM/KILL activity, the terminal cleanup outcome (`not_required`, `succeeded`, `denied`, or `incomplete`), and the observed population state. A successful adapter result is rejected whenever descendant cleanup was required or cleanup was not positively completed.

This boundary owns ordinary forked, daemonized, and `setsid()` descendants; it is not a separate UID, filesystem sandbox, network sandbox, or defense against an actively malicious same-UID process asking the user manager to create a sibling unit. `Delegate=no` prevents delegated child cgroups, but the stronger same-UID threat model remains the responsibility of the separate Codex and Claude native-containment tracks. Unsupported hosts and unavailable primitives fail before the adapter executable or provider environment is released.

### Harvey LAB composition preflight

Both clean-native Harvey LAB compositions run the same host check before the solver starts: `output_root` must be a real, non-symlink directory that resolves strictly inside `sandbox_root`, never equal to it. Output discovery enforces the identical rule after the run, but only the pre-spawn check keeps a bad layout from launching a solver at all — a path outside the sandbox is refused before any directory is created for it, so the run never begins. The check lives in `require_harvey_lab_sandbox_hosts` alongside the post-run rule rather than being reimplemented per adapter, and it raises the same `HarveyLabOutputDiscoveryError` codes (`layout`, `symlink`).

A LAB run is scored only when its solver receipt is a clean success served by the requested model. Because a LAB task returns a deliverable rather than a forecast envelope, the Claude LAB path classifies its receipt with `classify_claude_completion_execution` — the shared adapter-core taxonomy without the forecast parser — so `cancelled` is reported as a lifecycle abort rather than a crash, and a served-model mismatch is `identity_drift` even when the CLI exits zero. The Codex LAB path uses `classify_codex_execution` for the same purpose. Neither path invents a LAB-local failure vocabulary.

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

The command must support two ordinary phases:

```bash
example-adapter capabilities --output adapter-capabilities.json
example-adapter run --request request.json --output result.json --workspace row-workspace
```

`capabilities` writes a valid `AdapterCapabilities` JSON object. The conformance suite currently requires `supports_sandbox_policy: true`, because every fixture request includes a host-owned `SandboxPolicy`.

`run` reads a `RunRequest`, writes a `RunResult`, and keeps stdout/stderr/private logs out of public summaries. Each result public summary must echo the received `sandbox_policy_id` so reviewers can verify which host policy was recorded for the row. Public artifacts must use safe relative paths and SHA-256 hashes.

An adapter that advertises `tool_protocol_version: legalforecast.multiharness.tool_request.v1` must also support `run-with-tools --request ... --output ... --workspace ...`. During that phase, stdout is reserved for one bounded `ToolRequest` JSON line at a time and stdin is reserved for the matching host-written `ToolResponse` line. Diagnostics belong on stderr. Unknown protocol versions, malformed frames, duplicate request IDs, mismatched responses, and adapters that advertise the protocol without implementing the phase fail before a result is accepted.

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
  --host-process-containment linux_systemd_scope_cgroup_v2.v1 \
  --output-dir tmp/multiharness/run
```

That command is plan-only: it records `sandbox.plan.json` but does not claim that adapter tools ran in the container.

Live tool execution is explicit:

```bash
uv run legalforecast multiharness run \
  --task-index tmp/multiharness/lab-index.json \
  --selection tmp/multiharness/lab-selection.json \
  --adapter-manifest adapter-manifest.json \
  --model-key provider:model-id \
  --sandbox-policy-id live-tool-sandbox \
  --sandbox-backend podman \
  --sandbox-image 'example/tool-worker@sha256:<64-lowercase-hex-digest>' \
  --allow-provider-egress \
  --provider-env-var OPENAI_API_KEY \
  --live-tool-container \
  --output-dir tmp/multiharness/run
```

The backend and immutable image must already exist locally; before the live adapter run receives provider credentials, live execution verifies that the selected daemon is rootless and that `image inspect` resolves the exact pinned reference locally. Container creation then uses `--pull=never`. The host exposes exactly one read-only input bind, disables container networking, uses a read-only root, provides separate 64 MiB `noexec,nosuid,nodev` tmpfs mounts for `/tmp` and the scoped `/workspace/output`, drops all capabilities, enables no-new-privileges, selects a non-root UID/GID, and enforces PID, memory, CPU, and timeout limits. Output tmpfs bytes disappear with the container; bounded tool responses carry results back to the host. Caller-selected mounts, symlinked or special-file trees, home/root exposure, tag-only images, non-rootless daemons, and incomplete cleanup fail closed.

The adapter remains a host process and receives only the explicitly allowed provider environment variables. The tool container receives no provider variables. Its entrypoint speaks the versioned JSONL tool protocol over stdin/stdout. Each successful row writes a private receipt binding the immutable image, policy, request, staged input tree, ordered exchange hashes, result, exit status, and confirmed cleanup; the public row contains only the receipt SHA-256 commitment. Resume requires the exact successful receipt and all bound artifacts to revalidate.

Tool-container cleanup is separate from host adapter containment. Select `--host-process-containment linux_systemd_scope_cgroup_v2.v1` when the host command adapter must be held in the verified systemd scope/cgroup-v2 boundary described above; the legacy default only cleans the original POSIX process group.

The auditable negative-control worker and its digest-pinned build recipe are checked in under `tests/fixtures/container_runtime_worker/`. Build it explicitly with the same rootless backend used by the test, then resolve the local image ID:

```bash
CONTAINER_BACKEND=docker
E2E_TAG=legalforecast-container-runtime-e2e:local
"$CONTAINER_BACKEND" build \
  --file tests/fixtures/container_runtime_worker/Containerfile \
  --tag "$E2E_TAG" \
  tests/fixtures/container_runtime_worker
E2E_RAW_ID=$("$CONTAINER_BACKEND" image inspect --format '{{.Id}}' "$E2E_TAG")
export LEGALFORECAST_CONTAINER_E2E_IMAGE="sha256:${E2E_RAW_ID#sha256:}"
export LEGALFORECAST_CONTAINER_E2E_BACKEND="$CONTAINER_BACKEND"
export LEGALFORECAST_CONTAINER_E2E=1
uv run pytest -q tests/test_multiharness_container_runtime_e2e.py
```

The explicit build may fetch the Containerfile's digest-pinned base image; the runtime test itself never builds, pulls, publishes, or elevates. While the worker remains live, the host inspects the actual container and independently checks its exact image ID, network mode, read-only root, non-root user, dropped capabilities, no-new-privileges setting, resource limits, input bind, bounded tmpfs mounts, and environment isolation. The worker separately performs network, home, runtime-socket, root-write, tmpfs-write, scoped-output, and background-child probes. The test then requires confirmed cleanup and verifies that the exact container ID no longer exists.

If a provider CLI or subscription is used, the adapter must record the auth mode and terms assumption in its public-safe metadata. Do not put API keys, account IDs, refresh tokens, raw transcripts, private logs, sealed material, or source documents in public artifacts.

## Troubleshooting

- `adapter capabilities ID does not match manifest`: the adapter wrote capabilities for a different `adapter_id` or version.
- `run result request_id does not match request`: the adapter did not echo the exact request row.
- `result record passed public-safety validation` failure: remove secret-like fields, provider account IDs, deprecated tier labels, or unsafe public artifact paths.
- LAB bridge reports missing `--lab-root` or `--output-dir`: the supplied LAB command does not expose the root/output controls this bridge needs. Use a fixture command or update the command manifest until the real LAB CLI supports those flags.
- `LAB root must be a tracked path in a readable Git checkout`: use a Git checkout whose selected LAB root exists at `HEAD`; untracked standalone directories are intentionally rejected because they cannot provide a cheap, stable publication identity.
- `LAB capabilities changed after run planning`: the LAB source overlay, launcher, or semantic command arguments changed after the manifest was created. Start a new run so its compatibility hash describes the bytes that will execute.
- Container backend unavailable: plan-only mode can still record a policy, but `--live-tool-container` requires the selected local daemon to be installed, reachable, and rootless before any adapter run. For rootless Docker, point `DOCKER_HOST` at the operator-owned Unix socket beneath the operator-owned `XDG_RUNTIME_DIR`; remote TCP daemons and rootful daemons are rejected.
- `live container image must be digest-pinned`: use a repository reference with `@sha256:<digest>` or an exact local `sha256:<image-id>`; mutable tags are accepted only for plan-only records.
- `live tool container requires adapter tool protocol`: use an adapter that advertises the exact supported tool protocol and implements `run-with-tools`; ordinary adapters remain plan-only.
