# Codex CLI Interface Characterization

Decision: the installed `codex-cli 0.146.0` interface is pinned for offline adapter work, but it is not activated for benchmark execution.

This characterization invokes only the installed binary's version, help, feature-list, and help-only argument-parser surfaces.
The probe argv requests no model/provider call, benchmark-task path, or authentication path, and the child environment inherits no provider credential variable.
The probe does not enforce network isolation or trace the binary's system calls, so it makes no categorical claim that the executable performed zero external behavior internally.

## Exact installed identity

| Field | Value |
| --- | --- |
| Distribution | Homebrew cask `codex` `0.146.0` |
| Executable | `codex-x86_64-unknown-linux-musl` |
| Executable mode | `0755` |
| Version output | `codex-cli 0.146.0` |
| SHA-256 | `2e863156ed35ecc5253b1e2f907a9143077b9f7cb51942070c61996471ff6e04` |
| Requested future model pin | `gpt-5.1` |

The safe parser probe supplies `exec`, `--json`, `--ephemeral`, `--model gpt-5.1`, an isolated working directory through `--cd`, `--sandbox read-only`, `--strict-config`, `--ignore-user-config`, and `--ignore-rules`, followed by `--help`.
This records that the exact binary accepted the required help-only command-line surface; the probe supplied no task prompt.
It does not prove JSONL event semantics, model resolution, sandbox enforcement, or model-advertised tool behavior.

The isolated `features list` surface reports enabled stable rows for `shell_tool`, `unified_exec`, and `multi_agent`, along with the recorded stock feature rows in the fixture.
These rows are CLI configuration declarations, not evidence that a model request received or exercised those tools.
The native tool inventory therefore remains unobserved for this binary.

## Identity and activation boundary

This artifact belongs to the future `codex-cli-clean-native` profile.
It is distinct from the OpenAI Responses adapter: no Responses API adapter, task MCP server, or foreign MCP primary loop is used or characterized here.

Activation remains blocked on two exact-hash observations that require a separately approved model request:

- The resolved model must equal the requested `gpt-5.1` pin.
- The native model-advertised tool inventory must be recorded and reviewed.

The newer binary/interface pin does not supersede the provider-free native-loop and containment findings recorded for Codex CLI 0.144.5.
Those findings remain historical evidence for their exact executable hash; they cannot be silently transferred to 0.146.0.

## Drift probe

The committed fixture stores only public executable identity and sanitized interface data.
It contains no local path, account, credential, auth-store, configuration value, task content, or raw transcript.
In check mode, the expected fixture is loaded before the source executable can run.
The probe verifies the source basename, mode, and hash, copies those exact bytes into the isolated probe root, verifies the staged copy, executes only that staged file through an exact command-shape allowlist, and verifies its mode and hash again after all commands.
Version, distribution, executable mode/hash, help interface, feature interface, sandbox modes, or requested-model changes fail closed.

Run the fixture tests on any host:

```bash
uv run pytest -q tests/test_codex_cli_characterization.py
```

On the characterized host, compare the installed executable to the exact fixture with no provider credential inherited and no provider/model call requested:

```bash
uv run python scripts/probe_codex_cli_interface.py \
  --expected-model gpt-5.1 \
  --check tests/fixtures/codex_cli_characterization/codex-cli-interface-0.146.0.json
```

Review a changed sanitized observation explicitly rather than refreshing the fixture automatically:

```bash
uv run python scripts/probe_codex_cli_interface.py \
  --expected-model gpt-5.1 \
  --print-observation
```
