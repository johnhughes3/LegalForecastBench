# Claude Code CLI Interface Characterization

Decision: the installed standalone `claude` 2.1.231 interface is pinned for offline adapter work. It is not activated for benchmark execution.

This characterization invokes only the installed binary's version, help, and help-only print-mode parser surfaces, plus one credential-free `claude -p` call that failed closed before a provider request. The probe argv requests no benchmark-task path. The child environment inherits no provider credential variable. The probe does not enforce network isolation or trace system calls, so it makes no categorical claim that the executable performed zero external behavior internally.

Issue `#196` recorded earlier 2.1.210 / 2.1.211 observations. The SDK-bundled community baseline remains pinned at Claude Code **2.1.220** (`legalforecast.multiharness.claude_agent_sdk`). This document amends the **standalone CLI** pin to the currently installed 2.1.231 bytes (superseding the 2.1.229 observation on this lane). Those identities must not be silently transferred.

## Exact installed identity

| Field | Value |
| --- | --- |
| Distribution | standalone Claude Code CLI |
| Public executable name | `claude` |
| Executable mode | `0755` |
| Version output | `2.1.231 (Claude Code)` |
| SHA-256 | `47a01daebf794f6c86c13d1875ad6e5be0627029ad8600731161f24018ecde5b` |
| Requested future model pin | `claude-haiku-4-5` |

The public record stores the PATH command name `claude`, not a host-specific versions-directory filename.

The safe parser probe supplies `-p`, `--output-format json`, `--json-schema`, `--tools ""`, `--strict-mcp-config`, `--no-session-persistence`, `--setting-sources ""`, and `--model claude-haiku-4-5`, followed by `--help`. This records that the exact binary accepted the required help-only command-line surface. It does not prove JSON envelope semantics, model resolution, tool enforcement, or network containment.

Required print-mode flags present on this binary: `--print`, `--output-format`, `--json-schema`, `--tools`, `--strict-mcp-config`, `--no-session-persistence`, `--setting-sources`, `--model`. Output-format choices are `text`, `json`, and `stream-json`.

## Identity and activation boundary

This artifact belongs to the future `claude-code-clean-native` profile. It is distinct from the Claude Agent SDK adapter: no SDK session, task MCP server, or `claude --bare` primary loop is used or characterized here. Help text documents that `--bare` skips OAuth/keychain reads and restricts Anthropic auth to `ANTHROPIC_API_KEY` or `apiKeyHelper`; the clean-native treatment therefore does not use `--bare`.

Activation remains blocked on two exact-hash observations that require a separately approved model request:

- The resolved model must equal the requested `claude-haiku-4-5` pin.
- The native model-advertised tool inventory must be recorded and reviewed.

The local CLI adapter manifest instance for this binary is `tests/fixtures/local_cli_adapters/claude-code.json` (`legalforecast.multiharness.local_cli_adapter_manifest.v1`).

## Credential-free print envelope (no provider spend)

With an isolated empty `HOME`, no inherited credential variables, `--no-session-persistence`, empty `--setting-sources`, empty `--tools`, `--output-format json`, `--json-schema`, `--model claude-haiku-4-5`, and `--max-budget-usd 0.05`, `claude -p` exited `1` and wrote a JSON object on stdout. Observed public-safe facts:

- `type` is `result`, `is_error` is true, `terminal_reason` is `api_error`.
- `result` is the login prompt `Not logged in · Please run /login`.
- `total_cost_usd` is `0`, `duration_api_ms` is `0`, token counters are `0`.
- Envelope keys include `usage.input_tokens`, `usage.output_tokens`, `usage.cache_read_input_tokens`, `usage.cache_creation_input_tokens`, and `total_cost_usd`, which is why the v1 manifest maps those paths onto `SolverResponse`.
- `session_id` and `uuid` are present; they are not published here.
- Isolated `HOME` after `--help` contained no files. The failed print still wrote `.claude.json` and a backup under isolated `HOME`, so `--no-session-persistence` does not mean zero config side effects.
- No haiku/provider spend occurred. A successful cheap print still requires an explicit auth profile from `LegalForecastBench-dm0g.4.2.5` (`published-api-key` or `contributor-subscription`); `fixture-none` stops before spend.

Network behavior under outer containment flags was not traced. `duration_api_ms: 0` on this auth-closed call is not a containment proof.

## Verification live print (envelope paths only)

Lane B1 verification later invoked two haiku-tier `claude -p` calls with `--output-format json` against this same binary. Those calls are not adapter activation. Public-safe facts that matched the v1 manifest mapping:

- `type` is `result`, `is_error` is false, `terminal_reason` is `completed`.
- Envelope still includes `usage.input_tokens`, `usage.output_tokens`, `usage.cache_read_input_tokens`, `usage.cache_creation_input_tokens`, and `total_cost_usd`.
- `session_id` and `uuid` remain present and unpublished.
- Spend for those two calls is recorded on `LegalForecastBench-dm0g.4.4.3`, not in this document.

Activation remains blocked for benchmark execution.

## Drift probe

The committed fixture stores only public executable identity and sanitized interface data. It contains no local path, account, credential, auth-store, configuration value, task content, or raw transcript. In check mode, the expected fixture is loaded before the source executable can run. Version, distribution, executable mode/hash, help interface, required print flags, or requested-model changes fail closed.

Run the fixture tests on any host:

```bash
uv run pytest -q tests/test_claude_code_cli_characterization.py tests/test_local_cli_adapter_manifest.py
```

On the characterized host, compare the installed executable to the exact fixture with no provider credential inherited and no provider/model call requested:

```bash
uv run python scripts/probe_claude_code_cli_interface.py \
  --expected-model claude-haiku-4-5 \
  --check tests/fixtures/claude_code_cli_characterization/claude-code-cli-interface-2.1.231.json
```

Review a changed sanitized observation explicitly rather than refreshing the fixture automatically:

```bash
uv run python scripts/probe_claude_code_cli_interface.py \
  --expected-model claude-haiku-4-5 \
  --print-observation
```

## `--json-schema` grammar

Help text on this binary is `--json-schema <schema>` — a JSON Schema value, not a file path. The safe parser probe therefore passes inline JSON (`{"type":"object"}`). The frozen local-CLI argv_template uses `{output_schema}` (inline) and must not use `{output_schema_path}`.

A credential-free print that supplied a filesystem path as the flag value was rejected as invalid JSON. The auth-closed envelope fixture records that observation. Do not switch the freeze to a path token without a new characterization of this exact 2.1.231 binary.

## `--tools` argv encoding

Help text on this binary is `--tools <tools...>`. The frozen local-CLI `argv_template` reserves **exactly one argv value slot** after `--tools`. The offline core fills that slot with the empty string (`--tools ""`).

Clean-native does not keep the empty-string pin when tools are enabled. It fills the **same single slot** with a comma-joined allowlist token, not a shell string and not repeated argv words:

| Encoding | Argv after `--tools` | Status |
| --- | --- | --- |
| Offline core (empty) | `""` (one token) | frozen template default |
| Clean-native (enabled) | `Read,Glob` (one token) | required non-empty encoding |
| Rejected | `Read` `Glob` (two words) | would consume the next flag |
| Rejected | `'Read,Glob'` as a shell string | argv is never a shell |

The exact example token is `Read,Glob`. The clean-native Harvey LAB allowlist on this pin is `Read,Glob,Grep,Bash,Write,Edit` — still one comma-joined token. Web tools are not in that allowlist. Adapter helper: `encode_claude_code_tools_argv_token`. Do not change the frozen template into `{tools}` interpolation; the capability digest is bound to the empty-slot template.
