---
name: jev-mode
description: Inspect context fit, prepare reusable Luna document summaries, and run the distinct one-shot Jev official benchmark condition.
---

Use `legalforecast jev inspect` on the original locked manifest and blinded forecast release before choosing a representation. The full JSON request budget is 64,000 bytes, not tokens; TypeSafe does not publish an exact tokenizer. Enforce that limit on the complete case request; per-document summary allowances are planning targets. Do not truncate documents or change the frozen prediction units to make them fit.

`legalforecast jev prepare` stores one Luna summary per original selected document. Retain both its JSON cache and SQLite spend ledger on resume. Official preparation uses `prepare-jev-summaries.yaml`, and official inference uses `run-benchmark.yaml`; the normal protected-provider boundaries apply. `legalforecast jev registry --summaries ... --output ...` freezes the completed cache identity into the Jev registry. Inference adds `--jev-summaries` to the ordinary `run execute` command.

Report the condition as Jev with Luna summaries, one shot. Keep summary preparation costs visible separately and include them in total pipeline cost. Jev's native Boolean probabilities map directly to the original fully-dismissed event; never substitute confidence scores or a generated explanation. The default route uses the pinned TypeSafe Python SDK and `typesafe:jev-1.13.0`, authenticated with `TYPESAFE_API_KEY`, with SDK retries disabled. Historical Gateway registries remain supported with `--provider vercel_ai_gateway`. To issue a direct registry from an already complete hosted summary cache, set `registry_only=true` and supply the prior cache run and artifact IDs to `prepare-jev-summaries.yaml`; this skips all summary model calls. Switching providers creates a new registry and run identity; do not resume a Gateway run as TypeSafe.

Jev's workflow matrix stops queued cells after a failure. Diagnose the saved SDK message, HTTP status, and generation ID before retrying; the error class alone is insufficient. Use the normal `run resume --github-run RUN_ID --ref main --max-parallel 1` recovery path for a serial retry with the original summary cache and budget identity. Preserve ambiguous charges. Do not regenerate summaries to retry inference.

See [the method and reproduction guide](../../../docs/jev-mode.md) for commands, interpretation, and context-fit evidence.
