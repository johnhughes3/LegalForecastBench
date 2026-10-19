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

The prepare command verifies the clean commit and tree, selects only `employment-labor/identify-issues-in-counterparty-motion-brief`, and separates solver-visible files from the private rubric. It performs no model or evaluator request. The clean-native composer stages the selected solver files below the mounted workspace and passes `/workspace/task` to Claude, so it never relies on a host-only `--add-dir` path. The task overlay is read-only inside the outer container; generated deliverables remain writable under `/workspace/output`.

## Execution status

The callable source join is `run_claude_code_clean_native_harvey_lab`. It accepts the protected outer-container Claude adapter, a distinct host evaluator execution service, the existing production evaluator runner, and its per-criterion spend boundary. The operator-run result retains exact projection, sealed-output, evaluator-spec, raw-score, usage, and cost evidence without fabricating the unprovisioned historical receipt key.

There is not yet a protected workflow caller for this standalone LAB harness. The current paid gateway descriptor is issued only from locked forecast-release inputs and recognizes the forecast terminal, Hermes, and OpenClaw harness identities. A real run therefore still needs one narrow protected integration: issue a LAB-specific descriptor against the already approved ceiling and journal, then call this source join with the pinned solver and gateway image digests. Do not reuse an old dollar approval, route through the native-thin sandbox, expose a host container socket, or dispatch a model merely to test this source path.

Any eventual one-task result must remain labeled `Preliminary — one task pair, operator-run, not independently reproducible.` until a real protected solver and separate evaluator execution has completed and its artifacts have been inspected.
