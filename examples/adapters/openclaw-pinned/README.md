# Pinned OpenClaw community bridge

This source-checkout adapter runs one LegalForecastBench forecast through OpenClaw's managed `agent exec` entrypoint. The upstream runtime owns model calls and the agent loop. The adapter supplies one tool, `lfb_read_task`, which pages the host-staged solver prompt through LegalForecastBench's existing container protocol. It supports `legalforecast_mtd` with `lfb_brier` scoring: the contained protected route uses an exact frozen `anthropic:<model>` entry, while the original host tool route uses `openai:<model>`.

The runtime is pinned to [OpenClaw v2026.9.6](https://github.com/openclaw/openclaw/releases/tag/v2026.9.6), commit `eb377ac59e6c9fd6c7705028034812becf00271b`. Its separate pnpm lockfile pins the distribution and dependency graph. Before each run, the adapter checks the installed package version and distribution build revision and refuses a mismatch or missing installation. These checks identify an installed distribution; they do not attest a hostile machine.

## Install and check

Use Node 24.16+ within major 24, or Node 26.1+, plus pnpm. From the repository root:

```sh
pnpm --dir examples/adapters/openclaw-pinned install --frozen-lockfile
uv run python -m legalforecast.multiharness.openclaw_cli --help
uv run pytest tests/test_multiharness_openclaw*.py -q
LEGALFORECAST_OPENCLAW_E2E=1 uv run pytest tests/test_multiharness_openclaw*.py -q
```

The isolated pnpm package disables dependency lifecycle scripts. OpenClaw's launcher completes its own deferred distribution lifecycle on first invocation; the container build performs that step without networking before making the runtime read-only. Installation does not register interactive logins or modify an existing OpenClaw profile. Runtime tests are opt-in because installing OpenClaw is a substantial optional dependency.

The ordinary `run` phase is a credential-free conformance fixture. It accepts only the conformance task marker and reports `offline_protocol_fixture: true` and zero provider requests. The historical `../openclaw/adapter-manifest.json` remains explicitly a fixture; use this directory's manifest for the pinned bridge.

## Contained forecast-release execution

The paid forecast-release route is `legalforecast multiharness release-execute --harness openclaw`. It uses the same outcome-blinded `forecast-release.v1` inputs and separate `release-score` evaluator as the existing terminal route. It does not use LAB, Tier-0, or OpenRouter. The protected `run-benchmark.yaml` workflow selects it with `execution_mode=openclaw`; `terminal_case_id` limits a smoke to one exact case. This is source capability, not authorization to dispatch a paid run.

The route requires digest-pinned OpenClaw and gateway images, `published-api-key` authentication, an exact frozen Anthropic registry entry with explicit high reasoning (currently `anthropic:claude-opus-5-5`), and a descriptor issued with `python -m legalforecast.multiharness.paid_gateway_descriptor --harness openclaw`. The descriptor binds the pinned runtime identity, forecast release, registry/model, and approved ceiling into the existing spend-authority identity. `--max-budget-usd` must equal that ceiling; it is not an OpenClaw dollar flag. The existing gateway reserves a worst-case request charge before forwarding, settles complete provider usage, and retains ambiguous charges. Its 64-request per-case ceiling is an additional request bound, not spending authorization.

OpenClaw runs in the canonical rootless container envelope: read-only runtime and staged inputs, dropped capabilities, no-new-privileges, and an internal-only network. It calls its supported native Anthropic Messages endpoint on the host-owned gateway using a synthetic per-run capability. Only the gateway receives the real provider key and protected spend-authority credentials. The gateway's fixed Anthropic upstream goes through the existing allowlisted relay. The worker cannot select a different endpoint, provider grant, model, task release, runtime, or arbitrary command. OpenClaw still owns every model/tool turn. The fixed worker exposes only `lfb_read_task`, with the same acknowledged paging contract described below.

Build and exercise provider-free containment locally:

```sh
docker build --pull=false -f infra/openclaw-runtime/Containerfile -t lfb-openclaw:issue46-gateway .
LFB_OPENCLAW_CONTAINER_E2E=1 uv run pytest tests/test_multiharness_openclaw_container.py -q
```

The image completes the pinned distribution's deferred lifecycle at build time with networking disabled, before switching to the read-only runtime. The opt-in container test uses a local provider double and sentinel credentials. It is not an authorized paid smoke or live DynamoDB evidence. A real contributor run still needs independently reviewed source, approved bounded provider access, protected authority/evaluator provisioning, settlement evidence, and separate scoring; issue #46 stays open until that run is established.

## Legacy command-adapter tool route

Use this `adapter-manifest.json` through the existing [command adapter and live tool runner](../../../docs/multiharness/adapter-spec.md). Select `run-with-tools`, an `openai:<model>` model key, and a sandbox policy with exactly `OPENAI_API_KEY` in `allowed_provider_env_vars` and `provider_egress_host_only` networking. The caller supplies the normal locked task, nonempty unique `required_unit_ids`, staged `prompt.txt`, and the digest-pinned host tool image. The tool container retains the runner's existing network, filesystem, and credential isolation. Invoke live tool execution through the host runner, not by feeding arbitrary stdin to the adapter CLI.

Each run uses fresh private OpenClaw home, state, config, and working directories. It pins the built-in `openclaw` runtime, disables configured model fallbacks and Code Mode, loads only the OpenAI provider and this adapter's tool plugin, and removes the minimal profile's session and gateway tools. Native shell, filesystem, browser, network, and messaging tools are unavailable. The provider key stays in the host runtime; the tool plugin can request only sequential prompt pages and cannot choose a path or command. The host reads `prompt.txt` once with the production worker's `read` operation, then serves ASCII-escaped pages below pinned OpenClaw's per-tool result cap. Each next-page request must echo the preceding page's trailing receipt, including a final acknowledgement before forecasting can succeed. Worker read limits still apply; oversized inputs fail rather than being silently shortened. Ambient credentials, endpoint overrides, proxies, and `NODE_OPTIONS` are excluded by the shared host environment builder. No persistent gateway runs.

The adapter rejects failed or timed-out turns, served-model drift, missing, repeated, skipped, or unacknowledged prompt pages, and invalid/defaulted predictions. Canonical result metadata records runtime, commit, model, authentication category, tool policy, and completed prompt delivery. Forecast text and runtime stdout/stderr remain private under `private-logs`; temporary config and session state are removed when execution exits. Do not publish those private logs or an OpenClaw state directory.

The outer command adapter owns process containment and timeout cleanup. OpenClaw receives a bounded native timeout as well. This original OpenAI host route is not admitted for paid forecast-release execution: it lacks the protected gateway's spend accounting. Use the contained route above for that source capability. Neither route establishes live provider availability, benchmark quality, or full issue #46 completion by itself.

## What the tests prove

Default tests cover public adapter conformance, result normalization, mismatched version/commit rejection, and the actual Node plugin exchanging prompt pages with the Python host bridge and production worker executor. Opt-in installed-runtime tests run the real upstream loop against local OpenAI and Anthropic provider doubles and verify complete delivery of a 90KB prompt (beginning, middle, and end). The separate container test exercises the real image, gateway and relay, denies a direct external socket and staged-input writes, and confirms no provider credential in the worker. Descriptor/refusal tests and real SQLite reservation/settlement tests establish component behavior; SQLite is not substituted for the protected DynamoDB transport-marker contract. No fixture test establishes live provider availability, protected DynamoDB readiness, forecast quality, or the contributor-funded smoke required by issue #46.
