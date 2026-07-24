# Codex CLI Native-Containment Feasibility

Decision: the installed Codex CLI `0.144.5` does **not** qualify as `codex-cli-clean-native` on this host. The pinned binary's native local tool loop works against a deterministic loopback Responses API stub, but the requested native sandbox and a whole-process outer boundary are not enforceable in the current execution environment. The retained, deliberately narrower profile is `codex-cli-local-stub-native-loop-only`; it is characterization evidence, not a runnable benchmark treatment.

Decision reviewed: 2026-07-17.

## Scope and method

The probe consumes zero benchmark-task bytes, sends zero provider requests, uses no provider credential, and makes no scored model call. A deterministic HTTP server bound to loopback returns scripted Responses API tool calls to the real installed Codex executable. This preserves Codex's own request construction, event loop, tool dispatch, process launch, output handling, and native delegation advertisement without substituting an MCP agent loop or spending provider tokens.

The probe first requests `workspace-write`, `never` approval behavior through the noninteractive default, an ephemeral thread, strict configuration, isolated `HOME` and `CODEX_HOME`, ignored user configuration, ignored execution rules, no task MCP servers, and live web search disabled. It then disables apps/connectors, browser/computer use, hooks, image generation, memories, plugins, remote control, and network-proxy features. Native multi-agent support remains enabled so the capability inventory can record whether delegation is present.

The real native-sandbox attempt fails before a command can enter the sandbox. The probe therefore repeats the scripted tool sequence under `danger-full-access` solely as a diagnostic fallback. That fallback is intentionally incapable of satisfying the containment claim: its positive tool results prove native-loop mechanics only, while its hostile canaries identify the missing boundaries.

## Pinned executable and capability identity

| Field | Recorded value |
| --- | --- |
| Resolved executable | `codex-x86_64-unknown-linux-musl` |
| Version | `codex-cli 0.144.5` |
| SHA-256 | `058d616bde049c0648b72d53a22a54bf428eeb3f10e76cb4d6d4d4f81b764600` |
| Requested native sandbox | `workspace-write` |
| Native sandbox implementation observed | bubblewrap |
| Native sandbox result | rejected: `bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted` |
| Model route | deterministic loopback Responses API stub, model label `gpt-5.1` |
| Provider requests | `0` |
| Benchmark-task bytes | `0` |

The committed JSON fixture contains the complete observed CLI subcommand list, every `codex exec` long flag, all 92 feature rows reported by `codex features list`, the exact runtime overrides, and the full native request tool inventory. The binary/source relationship was checked against OpenAI's [`rust-v0.144.5` tag](https://github.com/openai/codex/tree/rust-v0.144.5); the local binary and its own help/feature output remain the authority for this host.

The local model request advertised `exec_command`, `write_stdin`, `multi_agent_v1`, `request_user_input`, `update_plan`, and `view_image`. No foreign MCP tool name appeared. `multi_agent_v1` proves native delegation is present in the installed request surface, but the no-spend characterization deliberately does not launch a subagent because that would require another model response and is not needed to identify the containment blocker.

The native diagnostic loop passed shell execution, filesystem read, filesystem write, text search, edit, and final-output probes. The installed build exposes editing through `exec_command`, rather than a separate `apply_patch` tool, so the scripted edit uses that advertised native shell surface. The final output is `/workspace/deliverable.txt`, exact content `FINAL NATIVE_BOUNDARY_OK\n`, SHA-256 `85d05425d3c82e24da44a918148bec75a776609c56f3a2fa0484a0984ee1a100`.

## Disabled stock capabilities and deliberate deviations

The candidate profile deliberately disables live web search; apps and connectors; browser and computer use; hooks; image generation; memories; plugins; remote control; and the experimental network proxy. It also uses an empty isolated `CODEX_HOME`, no MCP configuration, `--ignore-user-config`, `--ignore-rules`, `--ephemeral`, and no project instruction file. These are disclosed treatment controls, so literal “out of the box” wording is forbidden even if a later host proves containment.

The deterministic loopback provider is a probe instrument, not the treatment provider. A future real run must replace it with one of the supported authentication profiles in [Provider Runtime Baseline Adapters](provider-baselines.md), repeat the exact executable and capability checks, and retain the same native Codex loop. An MCP-mediated planner or foreign tool server cannot be substituted and still use the clean-native identity.

## Canary results and outer-boundary gaps

| Canary or control | Result | Interpretation |
| --- | --- | --- |
| Ambient config marker | absent | Isolated `CODEX_HOME` prevented loading the planted config. |
| Ambient MCP marker | absent | The isolated MCP list was empty and no MCP tool appeared in the request. |
| Ambient project instructions marker | absent | The disposable workspace had no inherited project instructions. |
| Ambient execution-rules marker | absent | `--ignore-rules` and the isolated home excluded the planted rule. |
| Ambient skill marker | absent | The planted host skill did not enter the request. |
| Credential-child inheritance | **failed** | Despite `shell_environment_policy.inherit="none"`, child commands received `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, and `AWS_SECRET_ACCESS_KEY` canary names from the parent. No real credential value was used. |
| Host-auth canary | **visible** | The diagnostic fallback could read a planted auth-shaped file outside the workspace. |
| Host-home canary | **visible** | The diagnostic fallback had no whole-process filesystem boundary. |
| Host-repository canary | **visible** | The diagnostic fallback had no whole-process filesystem boundary. |
| Evaluator-private canary | **visible** | The diagnostic fallback did not preserve the solver/evaluator trust split. |
| External-network canary | **reachable** | The diagnostic fallback had no enforced egress boundary. |
| Background descendant | not observed after Codex exit | The non-daemonizing scripted `sleep` did not survive the diagnostic process exit. This does not establish cleanup of descendants that create another session or process group; stronger host-owned containment is tracked in [issue #267](https://github.com/johnhughes3/LegalForecastBench/issues/267). |

The credential result is especially important: the committed fixture records child environment variable names only, never values. The requested setting and observed inheritance are both preserved so later runtime work can reproduce and fix the discrepancy instead of assuming that a configuration declaration enforced the boundary.

The current host also cannot use a user transient systemd root as a replacement outer boundary: user-level mount namespacing exits `226/NAMESPACE`, while `PrivateNetwork=yes` can be silently ignored when the user manager lacks namespace privilege. The probe treats those journal diagnostics as supporting detail rather than a stable receipt surface: it normalizes exit 226 to `failure_class = namespace-setup-failed`, records one conservative nonzero-preflight warning, and records the absent distinct network namespace. This avoids a transient-unit collection race changing the fixture without weakening the fail-closed decision.

That systemd invocation is a capability preflight, not a wrapper around the Codex parent. The receipt therefore records `kind = none-applied-to-codex-parent` and `whole_process_boundary_applied = false` unconditionally for this characterization. Even a future successful preflight or native child-sandbox result cannot authorize the stronger claim until the actual Codex parent runs inside an independently attested whole-process boundary; regression tests freeze this distinction.

## Claim decision

The `codex-cli-clean-native` claim is rejected on four independent blockers: the native `workspace-write` sandbox is unavailable; no whole-process filesystem boundary denies host and evaluator-private bytes; no whole-process network boundary denies external egress; and credential canaries reach child commands despite the requested environment policy. The exact failure is the evidence-gated outcome required by this feasibility bead, not permission to weaken or bypass the sandbox.

The only supported statement from this artifact is: “The pinned Codex CLI 0.144.5 native local tool loop and output contract worked against a deterministic loopback model stub with ambient configuration excluded; this host did not establish native or whole-process containment.” It does not establish a publishable score, a contributor-grade boundary, provider-auth safety, independent reproducibility, or a successful Tier-0 Codex treatment.

Any later attempt to use `codex-cli-clean-native` must fail before task materialization or provider contact unless all of the following are true: the expected executable hash matches; the native sandbox starts and remains the selected tool executor; a disposable whole-process boundary denies host home, host repository, evaluator-private bytes, and general network; child credential canaries are absent; no foreign MCP primary loop appears; all native tool/output probes pass; and an independent security review approves the evidence.

## Reproduction

Run the focused committed contract without contacting a provider:

```bash
uv run pytest -q tests/test_codex_native_containment.py
```

Re-run the live local-stub characterization for the exact installed binary:

```bash
scripts/probe_codex_native_containment.py \
  --expected-sha256 058d616bde049c0648b72d53a22a54bf428eeb3f10e76cb4d6d4d4f81b764600 \
  --output tmp/codex-native-containment-0.144.5.json

CODEX_NATIVE_CONTAINMENT_PROBE_RESULT=tmp/codex-native-containment-0.144.5.json \
  uv run pytest -q tests/test_codex_native_containment.py
```

The live replay is exact-host evidence. A changed executable hash, version, request tool inventory, feature inventory, canary result, sandbox result, or output causes review rather than silent fixture refresh.
