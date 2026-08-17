# Local CLI adapter manifest v1

`legalforecast.multiharness.local_cli_adapter_manifest.v1` describes a local agentic CLI (Claude Code, Codex CLI, or a future peer) to the existing multi-harness solver surface.

It does not replace frozen `legalforecast.multiharness.adapter_manifest.v1`. That record remains the public command-adapter identity (`capabilities` / `run` / `run-with-tools`). This schema is the generic description of the **target CLI**: executable identity, headless invocation, auth-profile name, containment, timeout/retry, transcript capture, usage mapping, and task/deliverable projection.

B3 adapter cores load this manifest and implement `HarnessAdapter` and `HarnessSolver`. They must not add provider-specific branches to `legalforecast/cli.py`. Future CLIs register by shipping a new instance of this schema, not by editing a central switch.

The schema is closed. Unknown fields, unknown capability tokens, unknown auth-profile names, and host paths are rejected. Public records must not contain credentials, account identifiers, or local filesystem paths.

## Exact artifact

The fenced example is the committed Claude Code instance (`tests/fixtures/local_cli_adapters/claude-code.json`). Tests parse every `json` fence in this document through the typed model and require re-serialization equality.

```json
{
  "adapter_kind": "local_cli",
  "auth_environment_variables": [
    {
      "names": [
        "CLAUDE_CODE_OAUTH_TOKEN"
      ],
      "profile": "contributor-subscription"
    },
    {
      "names": [],
      "profile": "fixture-none"
    },
    {
      "names": [
        "ANTHROPIC_API_KEY"
      ],
      "profile": "published-api-key"
    }
  ],
  "auth_profile_name": "fixture-none",
  "capabilities": [
    "empty_tools",
    "headless_print",
    "isolated_setting_sources",
    "json_output",
    "json_schema_enforcement",
    "max_budget_usd",
    "model_selection",
    "no_session_persistence",
    "permission_mode",
    "strict_mcp_config",
    "tool_allowlist",
    "working_directory_isolation"
  ],
  "capability_digest": "sha256:589dcb30806b1f204f3f6c7e7a9d071a7f7400e9ac91eec07220843b0516ba2a",
  "containment": {
    "host_process_containment": "posix_process_group.v1",
    "isolated_host_environment": true,
    "network_policy": "provider_egress_host_only",
    "session_persistence": "forbidden",
    "setting_sources": [],
    "strict_mcp_config": true
  },
  "display_name": "Claude Code clean-native local CLI",
  "executable": {
    "basename": "claude",
    "distribution_kind": "standalone-cli",
    "sha256": "55d281096f57d411ebbdd94dbf5e9ff3accb7c05713e37348c2c11d4b83bf9d9",
    "version": "2.1.233 (Claude Code)"
  },
  "harness_binding": {
    "adapter_id": "claude-code-clean-native",
    "adapter_version": "1.0.0",
    "harness_adapter_contract": "legalforecast.multiharness.adapters.HarnessAdapter",
    "harness_solver_contract": "legalforecast.evals.inspect_task.HarnessSolver",
    "implements_harness_adapter": true,
    "implements_harness_solver": true,
    "solver_kind": "inspect_ai",
    "solver_response_contract": "legalforecast.evals.inspect_task.SolverResponse",
    "supported_families": [
      "legalforecast_mtd"
    ],
    "supported_scoring_modes": [
      "lfb_brier"
    ],
    "tool_protocol_version": null
  },
  "invocation": {
    "argv_template": [
      "-p",
      "{prompt}",
      "--output-format",
      "json",
      "--json-schema",
      "{output_schema}",
      "--tools",
      "",
      "--strict-mcp-config",
      "--no-session-persistence",
      "--setting-sources",
      "",
      "--model",
      "{model}",
      "--add-dir",
      "{workspace}"
    ],
    "headless_mode": "print_flag",
    "model_flag": "--model",
    "output_format": "json",
    "prompt_delivery": "argv_placeholder",
    "schema_enforcement": "json_schema_flag",
    "working_directory_flag": "--add-dir"
  },
  "manifest_id": "claude-code-clean-native",
  "schema_version": "legalforecast.multiharness.local_cli_adapter_manifest.v1",
  "supported_auth_profiles": [
    "contributor-subscription",
    "fixture-none",
    "published-api-key"
  ],
  "task_projection": {
    "deliverable_event_type": null,
    "deliverable_field": "result",
    "deliverable_item_type": null,
    "deliverable_relative_path": null,
    "deliverable_source": "structured_stdout",
    "prompt_source": "solver_input_prompt"
  },
  "timeout_retry": {
    "max_attempts": 1,
    "retry_backoff_seconds": 2,
    "retryable_exit_codes": [],
    "timeout_seconds": 120
  },
  "transcript_capture": {
    "points": [
      "private_execution_log",
      "stderr",
      "stdout"
    ],
    "public_raw_transcript": false
  },
  "usage_reporting": {
    "cache_read_tokens_field": "usage.cache_read_input_tokens",
    "cache_write_tokens_field": "usage.cache_creation_input_tokens",
    "cost_basis": "provider_reported",
    "cost_usd_field": "total_cost_usd",
    "input_tokens_field": "usage.input_tokens",
    "output_tokens_field": "usage.output_tokens",
    "solver_response_fields": [
      "estimated_cost",
      "input_tokens",
      "output_tokens",
      "request_count"
    ]
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

`argv_template` is an argv array, not a shell string. The only placeholders are `{prompt}`, `{model}`, `{workspace}`, `{output_schema}`, and `{output_schema_path}`. Empty strings are allowed so a CLI can pass `--tools ""`. Literal tokens must not contain `/`, `\`, or `~`.

- `headless_mode`: `print_flag` (Claude Code `-p`) or `exec_subcommand` (Codex `exec`).
- `output_format`: `json` (one JSON document on stdout), `stream_json` (JSONL), or `text`. `json` requires the `json_output` capability; `stream_json` requires `stream_json_output`. For `stream_json`, `usage_reporting` dotted paths are evaluated against the terminal JSON object in that stream, not against concatenated stdout.
- `schema_enforcement`: `none`, `json_schema_flag`, or `output_schema_file`. `json_schema_flag` requires `{output_schema}` (inline JSON, as Claude Code `--json-schema` takes a schema value). `output_schema_file` requires `{output_schema_path}` (Codex `--output-schema` takes a file). The two placeholders are mutually exclusive. `none` rejects both `{output_schema}` and `{output_schema_path}` so `render_argv` cannot demand schema material the mode says to omit.
- `prompt_delivery`: `argv_placeholder` or `stdin`. The placeholder mode requires `{prompt}`. `stdin` forbids `{prompt}` so the prompt is not duplicated onto argv.
- A non-null `working_directory_flag` or `model_flag` must appear as an exact token in `argv_template` (in addition to requiring `{workspace}` / `{model}`).

### Authentication

`auth_profile_name` is a name reference only. Profile semantics, credential projection, and no-fallback policy belong to `LegalForecastBench-dm0g.4.2.5`. The vocabulary this schema accepts is:

- `fixture-none`
- `published-api-key`
- `contributor-subscription`

`supported_auth_profiles` lists the subset this adapter instance may use. `auth_profile_name` must be one of those names and is the profile the fixture itself is bound to. `auth_environment_variables` is an array of `{profile, names}` objects mapping each supported profile to the public environment-variable *names* B3 may project; values and Infisical paths stay with `LegalForecastBench-dm0g.4.2.5` / `LegalForecastBench-dm0g.4.2.13`. The published-api-key Infisical layout is documented in `docs/adapters/published-api-key-profile.md`. `fixture-none` must map to an empty list. Profile IDs are record values, not object keys, so `published-api-key` does not trip the public-record secret-key scanner.

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
- `structured_stdout` requires `deliverable_field`, a dotted path into the JSON object that holds the answer. The projector accepts a non-empty string or a JSON object (serialized with sorted keys, indent 2, and a trailing newline, matching Claude `result` encoding). For `output_format: stream_json` it also requires `deliverable_event_type` (and may set `deliverable_item_type` to distinguish events that share a type, such as Codex `item.completed` / `agent_message`). For `output_format: json` the event selectors must be null. `workspace_relative_file` forbids the event/field selectors.
- `project_structured_stdout_deliverable()` is the generic projector: wrappers must not hard-code Codex event names.
- `harness_binding` names the existing `HarnessAdapter`, `HarnessSolver`, and `SolverResponse` contracts. `solver_kind` must be one of the existing `SolverKind` values (`offline_mock`, `configured_model_stub`, `inspect_ai`). This schema does not add a parallel solver kind.
- `to_adapter_manifest(command=...)` emits frozen `adapter_manifest.v1` for the **B3 in-process wrapper**, never for `CommandAdapter.prepare` against `claude` or `codex`. `command` is the wrapper identity (a Python entry point). The helper rejects the target CLI basename so the existing command-adapter protocol (`capabilities --output ...`) is not aimed at the vendor binary. `to_adapter_capabilities()` emits the v1 capability advertisement keyed by this schema's `capability_digest`. B3 implements `HarnessAdapter` / `HarnessSolver` by reading this manifest and rendering `argv_template`.

## Closed field inventory

The following tables are the anti-drift inventory. Tests parse the `field` column of each `###` heading and require set equality with the typed model's dataclass fields. Adding or renaming a field without updating both sides fails closed.

### local_cli_adapter_manifest

| field |
| --- |
| adapter_kind |
| auth_environment_variables |
| auth_profile_name |
| capabilities |
| capability_digest |
| containment |
| display_name |
| executable |
| harness_binding |
| invocation |
| manifest_id |
| schema_version |
| supported_auth_profiles |
| task_projection |
| timeout_retry |
| transcript_capture |
| usage_reporting |

### executable

| field |
| --- |
| basename |
| distribution_kind |
| sha256 |
| version |

### invocation

| field |
| --- |
| argv_template |
| headless_mode |
| model_flag |
| output_format |
| prompt_delivery |
| schema_enforcement |
| working_directory_flag |

### containment

| field |
| --- |
| host_process_containment |
| isolated_host_environment |
| network_policy |
| session_persistence |
| setting_sources |
| strict_mcp_config |

### timeout_retry

| field |
| --- |
| max_attempts |
| retry_backoff_seconds |
| retryable_exit_codes |
| timeout_seconds |

### transcript_capture

| field |
| --- |
| points |
| public_raw_transcript |

### usage_reporting

| field |
| --- |
| cache_read_tokens_field |
| cache_write_tokens_field |
| cost_basis |
| cost_usd_field |
| input_tokens_field |
| output_tokens_field |
| solver_response_fields |

### task_projection

| field |
| --- |
| deliverable_event_type |
| deliverable_field |
| deliverable_item_type |
| deliverable_relative_path |
| deliverable_source |
| prompt_source |

### harness_binding

| field |
| --- |
| adapter_id |
| adapter_version |
| harness_adapter_contract |
| harness_solver_contract |
| implements_harness_adapter |
| implements_harness_solver |
| solver_kind |
| solver_response_contract |
| supported_families |
| supported_scoring_modes |
| tool_protocol_version |

## Fixtures

- `tests/fixtures/local_cli_adapters/claude-code.json` — first real instance, dogfooding the Claude Code 2.1.233 characterization.
- `tests/fixtures/local_cli_adapters/codex-cli.json` — Codex CLI 0.147.0 interface pin, same schema, no Claude-specific fields.

Validate with:

```bash
uv run pytest tests/test_local_cli_adapter_manifest.py -q
```
