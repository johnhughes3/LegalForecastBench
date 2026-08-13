# Multi-harness identity keys

Status: contract foundation for `LegalForecastBench-dm0g.4.1.4`.

Community submissions and official runs share one identity layer. Local CLI `RunSpec` and `ExecutionReceipt` types in `legalforecast.multiharness.local_cli_contracts` remain the execution records from PR #685. This note does not add a second type family.

## Records

| Record | What it binds | When it exists |
| --- | --- | --- |
| `TaskIdentity` | Task id, family, scoring mode, suite version, and task bytes (`task_sha256`) | Always |
| `SolverIdentity` | Provider, requested model, settings digest, and served model | Always. `served_model` may be JSON `null` when unresolved |
| `RunIdentity` | Task key, solver key, runtime policy, config, temporal block, order, and repeat index | Always |
| `MatchedHarnessIdentity` | Task key, resolved served model/provider/settings, evaluator/judge, temporal block, outer envelope, order, and repeats | Only when the served model is resolved |
| `SystemBundleLabel` | Adapter id/version, requested model, and family | Always, including when the served model is unresolved |

Keys are `sha256:`-prefixed digests of artifact-canonical JSON (key-sorted, compact UTF-8, trailing newline) under `ARTIFACT_PREFIXED_SHA256_V1`. Each record's `schema_version` is part of the hashed payload. Unknown fields and refused aliases (`task_hash`, `servedModel`, `clean_native`, `mcp`) fail closed.

## Matched-harness versus treatment

A matched-harness key holds task bytes, served model, provider, settings, evaluator/judge, temporal block, outer envelope, order, and repeats fixed. Frozen harness-intrinsic prompt, context management, loop, tool API, and tool implementation may vary as treatment and are not mixed into the key. `clean-native` and `mcp-mediated` are distinct `outer_envelope` values; aliases are refused.

Unresolved served-model sentinels (`unknown`, `unresolved`, `*`, empty, `none`) are rejected as strings. Use JSON `null` on `SolverIdentity`. That unresolved solver still yields a system-bundle label; it cannot yield a matched-harness key.

## Resume

`validate_resume_binding` refuses a resume whose task identity, `config_sha256`, or `runtime_policy_sha256` differs from the prior run. Slot fields (`order`, `repeat_index`) may change; crossing task bytes, config, or runtime policy may not.

## Execution receipts

`ExecutionReceipt.to_public_record()` may carry `task_identity_key`, `solver_identity_key`, and `run_identity_key` together, or omit all three. Partial sets are rejected. `validate_public_execution_receipt` names any missing required public field on a receipt fixture.
