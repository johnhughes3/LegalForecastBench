# Local CLI adapter manifest v1

`legalforecast.multiharness.local_cli_adapter_manifest.v1` describes a local agentic CLI (Claude Code, Codex CLI, or a future peer) to the existing multi-harness solver surface.

It does not replace frozen `legalforecast.multiharness.adapter_manifest.v1`. That record remains the public command-adapter identity (`capabilities` / `run` / `run-with-tools`). This schema is the generic description of the **target CLI**: executable identity, headless invocation, auth-profile name, containment, timeout/retry, transcript capture, usage mapping, and task/deliverable projection.

B3 adapter cores load this manifest and implement `HarnessAdapter` and `HarnessSolver`. They must not add provider-specific branches to `legalforecast/cli.py`. Future CLIs register by shipping a new instance of this schema, not by editing a central switch.

The schema is closed. Unknown fields, unknown capability tokens, unknown auth-profile names, and host paths are rejected. Public records must not contain credentials, account identifiers, or local filesystem paths.

## Exact artifact

```json
{
  "schema_version": "legalforecast.multiharness.local_cli_adapter_manifest.v1",
  "manifest_id": "claude-code-clean-native",
  "display_name": "Claude Code clean-native local CLI",
  "adapter_kind": "local_cli",
  "executable": {
    "basename": "claude",
    "version": "2.1.229 (Claude Code)",
    "sha256": "<64-char lowercase hex>",
    "distribution_kind": "standalone-cli"
  },
  "capabilities": ["headless_print", "json_output"],
  "capability_digest": "sha256:<64-char lowercase hex>",
  "invocation": {
    "headless_mode": "print_flag",
    "argv_template": ["-p", "{prompt}", "--output-format", "json", "--model", "{model}"],
    "output_format": "json",
    "schema_enforcement": "json_schema_flag",
    "prompt_delivery": "argv_placeholder",
    "working_directory_flag": "--add-dir",
    "model_flag": "--model"
  },
  "auth_profile_name": "fixture_none",
  "containment": {
    "host_process_containment": "posix_process_group.v1",
    "network_policy": "provider_egress_host_only",
    "isolated_host_environment": true,
    "session_persistence": "forbidden",
    "setting_sources": [],
    "strict_mcp_config": true
  },
  "timeout_retry": {
    "timeout_seconds": 120,
    "max_attempts": 1,
    "retry_backoff_seconds": 2,
    "retryable_exit_codes": []
  },
  "transcript_capture": {
    "points": ["stdout", "stderr", "private_execution_log"],
    "public_raw_transcript": false
  },
  "usage_reporting": {
    "input_tokens_field": "usage.input_tokens",
    "output_tokens_field": "usage.output_tokens",
    "cache_read_tokens_field": "usage.cache_read_input_tokens",
    "cache_write_tokens_field": "usage.cache_creation_input_tokens",
    "cost_usd_field": "total_cost_usd",
    "cost_basis": "provider_reported",
    "solver_response_fields": ["input_tokens", "output_tokens", "estimated_cost", "request_count"]
  },
  "task_projection": {
    "prompt_source": "solver_input_prompt",
    "deliverable_source": "structured_stdout",
    "deliverable_relative_path": null
  },
  "harness_binding": {
    "adapter_id": "claude-code-clean-native",
    "adapter_version": "1.0.0",
    "supported_families": ["legalforecast_mtd"],
    "supported_scoring_modes": ["lfb_brier"],
    "tool_protocol_version": null,
    "implements_harness_adapter": true,
    "implements_harness_solver": true,
    "harness_adapter_contract": "legalforecast.multiharness.adapters.HarnessAdapter",
    "harness_solver_contract": "legalforecast.evals.inspect_task.HarnessSolver",
    "solver_response_contract": "legalforecast.evals.inspect_task.SolverResponse",
    "solver_kind": "inspect_ai"
  }
}
```

`capability_digest` is SHA-256 over the canonical JSON of every field except `schema_version`, `manifest_id`, `display_name`, `adapter_kind`, `executable`, and `capability_digest` itself. Executable identity can therefore change without silently rewriting the capability contract, and the opposite drift is also visible.

## Field catalog

### Identity

- `manifest_id`: stable adapter id; must equal `harness_binding.adapter_id`.
- `adapter_kind`: fixed to `local_cli`.
- `executable.basename`: pathless command name (`claude`, `codex`). Absolute paths and directory separators are rejected so public records cannot leak host layout.
- `executable.sha256`: unprefixed lowercase SHA-256 of the executable bytes.
- `executable.distribution_kind`: `standalone-cli`, `homebrew-cask`, `sdk-bundled`, or `fixture`.

### Capabilities

Closed tokens: `headless_print`, `json_output`, `stream_json_output`, `json_schema_enforcement`, `tool_allowlist`, `empty_tools`, `no_session_persistence`, `isolated_setting_sources`, `strict_mcp_config`, `max_budget_usd`, `permission_mode`, `model_selection`, `working_directory_isolation`. Unknown tokens fail closed.

### Invocation

`argv_template` is an argv array, not a shell string. The only placeholders are `{prompt}`, `{model}`, `{workspace}`, and `{output_schema_path}`. Empty strings are allowed so a CLI can pass `--tools ""`.

- `headless_mode`: `print_flag` (Claude Code `-p`) or `exec_subcommand` (Codex `exec`).
- `output_format`: `json`, `stream_json`, or `text`.
- `schema_enforcement`: `none`, `json_schema_flag`, or `output_schema_file`. Any mode other than `none` requires `{output_schema_path}`.
- `prompt_delivery`: `argv_placeholder` or `stdin`. The placeholder mode requires `{prompt}`.

### Authentication

`auth_profile_name` is a name reference only. Profile semantics, credential projection, and no-fallback policy belong to `LegalForecastBench-dm0g.4.2.5`. The vocabulary this schema accepts is:

- `fixture_none`
- `explicit_api_key`
- `local_cli_subscription`

Do not store account identifiers, token paths, or secret field names on this record.

### Containment, timeout, transcripts, usage

- `containment.host_process_containment` reuses the existing sandbox modes `posix_process_group.v1` and `linux_systemd_scope_cgroup_v2.v1`.
- `containment.network_policy` reuses `none` and `provider_egress_host_only`.
- `setting_sources` is a subset of `user`, `project`, `local`. Empty means load none.
- `timeout_retry.max_attempts` defaults to `1` in the shipped fixtures. A value greater than 1 requires `retryable_exit_codes`, because retrying a whole agent session is not a silent HTTP retry.
- `transcript_capture.public_raw_transcript` must be `false`. Capture points are `stdout`, `stderr`, `private_execution_log`, and `session_transcript`.
- `usage_reporting` maps dotted CLI-envelope paths onto existing `SolverResponse` fields. `input_tokens` and `output_tokens` are required members of `solver_response_fields`.

### Task and harness binding

- `task_projection.prompt_source` is fixed to `solver_input_prompt` (the private `prompt.txt` from `legalforecast.multiharness.solver_inputs`).
- `deliverable_source` is `structured_stdout` or `workspace_relative_file` (the latter requires a safe relative path).
- `harness_binding` names the existing `HarnessAdapter`, `HarnessSolver`, and `SolverResponse` contracts. `solver_kind` must be one of the existing `SolverKind` values (`offline_mock`, `configured_model_stub`, `inspect_ai`). This schema does not add a parallel solver kind.
- `to_adapter_manifest()` / `to_adapter_capabilities()` emit the frozen v1 records so `CommandAdapter.prepare` can keep using them. The wrapper `command` is the executable basename; B3 supplies the Python entry point that reads this manifest and renders `argv_template`.

## Fixtures

- `tests/fixtures/local_cli_adapters/claude-code.json` — first real instance, dogfooding the Claude Code 2.1.229 characterization.
- `tests/fixtures/local_cli_adapters/codex-cli.json` — Codex CLI 0.146.0 interface pin, same schema, no Claude-specific fields.

Validate with:

```bash
uv run pytest tests/test_local_cli_adapter_manifest.py -q
```
