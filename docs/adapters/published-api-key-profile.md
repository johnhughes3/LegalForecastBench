# Published API-key profile (`published-api-key`)

This is the portable provider-billed local-CLI profile (`LegalForecastBench-dm0g.4.2.13`). A run declares it by name. The harness fetches only the environment-variable names listed on that adapter's local CLI manifest, through `infisical-agent-sandbox`, and never from the operator shell.

`fixture-none` never reads this folder. `contributor-subscription` is a different folder and is out of scope here.

## Infisical layout (exact)

| Field | Value |
| --- | --- |
| Wrapper | `infisical-agent-sandbox` (the bare `infisical` CLI is unlinked and must not be used) |
| Path | `/agents/sandbox/legalforecastbench/labeling` |
| Canonical `--env` | `dev` |
| Also allowed `--env` | `staging`, `sandbox` |
| Refused `--env` | `prod` |
| Projected secret names | `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` |

This profile **reuses the existing labeling stage view**. It does not use, and must not duplicate keys into, `/agents/sandbox/legalforecastbench/harness-runtime/published-api-key`.

The labeling inventory is exactly `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, and `GEMINI_API_KEY`. `GEMINI_API_KEY` stays in that folder for labeling and is never projected into a Claude Code or Codex CLI child. Secret *names* in Infisical must match those environment-variable names exactly. Adapters project a subset:

| Adapter | Manifest | Projected name |
| --- | --- | --- |
| Claude Code (`claude-code-clean-native`) | `examples/adapters/claude-code/local-cli-adapter-manifest.json` | `ANTHROPIC_API_KEY` |
| Codex CLI (`codex-cli-offline`) | `examples/adapters/codex-cli/local-cli-manifest.json` | `OPENAI_API_KEY` |

An adapter that does not name a key never receives it. Extra names the wrapper returns beyond the adapter's projected set are refused.

## Operator source (human only)

Agents must not write secret values. The keys already live on the labeling path. If a named key is empty, populate it in Infisical as the human operator:

1. Path: `/agents/sandbox/legalforecastbench/labeling`
2. Environment: `dev`
3. Keys this profile reads (names only):
   - `ANTHROPIC_API_KEY` — Claude Code live smoke / provider-billed runs
   - `OPENAI_API_KEY` — Codex CLI live smoke / provider-billed runs

Do not copy those values into a second Infisical folder, the host environment, `auth.json`, or the repo.

## Fail-closed behavior

- Missing, empty, or 404 path: no spawn, no spend, no host-environment fallback.
- Wrapper identity other than `infisical-agent-sandbox`: refused.
- Projected value equal to the same name in the parent shell: refused (no ambient fallback).
- Extra names returned by the wrapper: refused.
- Public receipts, task bytes, and packages record only `auth_profile: published-api-key`. They never record the Infisical path, account, or key material.

## Offline vs live

Offline and CI runs use `fixture-none` (zero credentials) or inject a test double. A live preflight or haiku-tier smoke is opt-in (`LFB_LIVE_SMOKE=1`) and still uses this path through the wrapper with `--env dev`.
