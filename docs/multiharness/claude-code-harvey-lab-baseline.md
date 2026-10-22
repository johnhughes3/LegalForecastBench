# Claude Code clean-native Harvey LAB baseline

This source path composes the managed Claude Code document-tool runtime with the pinned Harvey LAB task and a separately executed evaluator. It is the standalone clean-native treatment for community issue #196, not the blocked native-thin comparison and not an official LegalForecastBench result.

## Produce the exact offline inputs

Clone the public upstream source and check out the recorded v1.1.0 commit:

```bash
git clone https://github.com/harveyai/harvey-labs.git harvey-labs
git -C harvey-labs checkout --detach 1dd81403b2fbb60596f7aea3fcecafad7bf73143
uv run legalforecast harvey-lab prepare-clean-native \
  --source-root harvey-labs \
  --output-dir run-input/projected \
  --evaluator-private-dir run-input/evaluator-private
uv run legalforecast multiharness tier0 install-evaluator-wrapper \
  --bin-dir run-input/bin \
  --scratch-root run-input/wrapper-scratch \
  --output run-input/wrapper-install.json
```

The prepare command verifies the clean commit and tree, selects only `employment-labor/identify-issues-in-counterparty-motion-brief`, and separates solver-visible files from the private rubric. It performs no model or evaluator request. The clean-native composer stages the selected solver files and authenticated `prompt.txt` below the mounted workspace. Claude receives a fixed instruction to read `/workspace/prompt.txt` with Bash, and the run is accepted only when the real stream parser observes the successful read. The task and prompt are read-only inside the outer container; generated deliverables remain writable under `/workspace/output`.

## Protected operator command

The dedicated issuer authenticates the upstream pin, solver projection, and a freshly reproduced copy of the evaluator-private bytes before it emits the existing paid-gateway descriptor shape:

```bash
uv run python -m legalforecast.multiharness.harvey_lab_paid_gateway_descriptor \
  --source-root harvey-labs \
  --projection-dir run-input/projected \
  --evaluator-private-dir run-input/evaluator-private \
  --model-registry path/to/locked-model-registry.json \
  --model-key 'anthropic:<model-id>' \
  --ceiling-microusd '<approved-ceiling>' \
  --account '<account>' \
  --output run-input/harvey-lab-paid-gateway.json
```

The command is valid only inside the configured protected environment. It performs no AWS or provider call, and it does not accept a forecast-release descriptor, approval reference, signing key, or synthetic production identity.

The standalone caller then consumes those prepared directories rather than projecting the upstream checkout again:

```bash
uv run legalforecast harvey-lab run-clean-native \
  --source-root harvey-labs \
  --projection-dir run-input/projected \
  --evaluator-private-dir run-input/evaluator-private \
  --run-dir run-output/claude-code-harvey-lab \
  --evaluator-bin-dir run-input/bin \
  --paid-config run-input/harvey-lab-paid-gateway.json \
  --model-registry path/to/locked-model-registry.json \
  --solver-image 'repository/claude-code@sha256:<digest>' \
  --gateway-image 'repository/model-gateway@sha256:<digest>' \
  --model-key 'anthropic:<model-id>'
```

The command re-authenticates all descriptor-bound LAB inputs before it constructs the DynamoDB authority or resolves credentials. It uses the descriptor's single approved ceiling and DynamoDB journal for both the solver gateway and every criterion-level judge request, requires pinned solver and gateway images, uses a distinct evaluator execution service, and refuses fixture provenance as a reportable baseline. A fixture run can still return a diagnostic score through the source join, but its result is explicitly `execution_mode=fixture` and has no `baseline_score_value`.

The protected producer/consumer is [`.github/workflows/run-harvey-lab-clean-native.yaml`](../../.github/workflows/run-harvey-lab-clean-native.yaml). It checks out an exact main-reachable LegalForecastBench commit and Harvey LAB v1.1.0 commit/tree, builds the repository-pinned solver and gateway images, prepares the projection and evaluator wrapper, issues the native LAB descriptor, and calls the real `run-clean-native` operator. Its uploaded artifact deliberately excludes the authority-bearing descriptor, evaluator-private bytes, evaluator overlays, raw judge attempts, evaluator work directories, and raw solver logs; it retains only the aggregate score summary, public-safe wrapper record, sanitized container package (including cache-usage counts), and sealed solver deliverables.

## Execution status

The callable source join is `run_claude_code_clean_native_harvey_lab`; the installed operator entry point above calls it directly. The source path and protected producer are complete, but no paid workflow has been dispatched from this implementation change. A real baseline therefore still requires an owner-approved ceiling, a compatible locked Anthropic registry entry, configured protected-environment variables and secret, an exact main release SHA, and inspection of the first run's solver transcript cache usage plus shared spend-journal settlement. Do not claim a live baseline from configuration or fixture tests.

This integration adds no new authority schema or approval format. It does not implement the separate Codex clean-native producer requested in #204, and it does not change the native-thin nested-Podman path whose rootless `unshare` failure remains a separate blocker. Do not reuse a forecast descriptor, an old dollar approval, the native-thin sandbox, or a host container socket for either gap.

Any eventual one-task result must remain labeled `Preliminary — one task pair, operator-run, not independently reproducible.` until a real protected solver and separate evaluator execution has completed and its artifacts have been inspected.
