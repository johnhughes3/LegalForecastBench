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

The standalone caller consumes those prepared directories rather than projecting the upstream checkout again:

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

The command requires the production configuration before it resolves credentials or launches the solver. It uses the descriptor's single approved ceiling and DynamoDB journal for both the solver gateway and every criterion-level judge request, requires pinned solver and gateway images, uses a distinct evaluator execution service, and refuses fixture provenance as a reportable baseline. A fixture run can still return a diagnostic score through the source join, but its result is explicitly `execution_mode=fixture` and has no `baseline_score_value`.

## Execution status

The callable source join is `run_claude_code_clean_native_harvey_lab`; the installed operator entry point above calls it directly. The operator-run result retains the projection, sealed output, evaluator spec, canonical raw verdicts, usage, and cost evidence without fabricating the unprovisioned historical receipt key.

The command is source-complete, but a paid run remains blocked on the protected descriptor/workflow integration. After the provider-preserving genericization in PR #1384 lands, the minimal follow-up is:

1. Admit the existing `claude-code-harvey-lab` harness identity in the protected descriptor CLI.
2. Derive the descriptor's existing run/authority identity fields from the authenticated Harvey LAB projection and v1.1.0 source pin, instead of calling the forecast-release input loader or populating `forecast_release_digest`.
3. Have the protected workflow create that descriptor from the prepared LAB inputs and invoke `harvey-lab run-clean-native` with the already pinned solver image, gateway image, locked model registry, approved ceiling, and existing authority environment.

This needs no new authority schema or approval format. Until that adapter exists, `prepare-clean-native` and evaluator-wrapper installation above are the exact credential-free commands runnable today; there is no legitimate paid descriptor to pass to `run-clean-native`. Do not reuse a forecast descriptor, an old dollar approval, the native-thin sandbox, or a host container socket, and do not dispatch a model merely to test this source path.

Any eventual one-task result must remain labeled `Preliminary — one task pair, operator-run, not independently reproducible.` until a real protected solver and separate evaluator execution has completed and its artifacts have been inspected.
