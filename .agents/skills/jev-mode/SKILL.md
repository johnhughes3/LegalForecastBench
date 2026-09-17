---
name: jev-mode
description: Inspect context fit, prepare reusable Luna document summaries, and run the distinct one-shot Jev official benchmark condition.
---

Use `legalforecast jev inspect` on the original locked manifest and blinded forecast release before choosing a representation. The full JSON request budget is 64,000 bytes, not tokens; TypeSafe does not publish an exact tokenizer. Enforce that limit on the complete case request; per-document summary allowances are planning targets. Do not truncate documents or change the frozen prediction units to make them fit.

`legalforecast jev prepare` stores one Luna summary per original selected document. Retain both its JSON cache and SQLite spend ledger on resume. Official preparation uses `prepare-jev-summaries.yaml`, and official inference uses `run-benchmark.yaml`; the normal protected-provider boundaries apply. `legalforecast jev registry --summaries ... --output ...` freezes the completed cache identity into the Jev registry. Inference adds `--jev-summaries` to the ordinary `run execute` command.

Report the condition as Jev with Luna summaries, one shot. Keep summary preparation costs visible separately and include them in total pipeline cost. Jev's native Boolean probabilities map directly to the original fully-dismissed event; never substitute confidence scores or a generated explanation. The implementation uses the pinned Vercel evaluation SDK under `integrations/jev`, with SDK retries disabled.

Jev's workflow matrix stops queued cells after a failure. Diagnose the saved SDK message, HTTP status, and generation ID before retrying; the error class alone is insufficient. Use the normal `run resume --github-run RUN_ID --ref main --max-parallel 1` recovery path for a serial retry with the original summary cache and budget identity. Preserve ambiguous charges. Do not regenerate summaries to retry inference.

See [the method and reproduction guide](../../../docs/jev-mode.md) for commands, interpretation, and context-fit evidence.
