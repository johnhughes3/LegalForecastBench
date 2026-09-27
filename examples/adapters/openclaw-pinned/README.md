# Pinned OpenClaw community bridge

This source-checkout adapter runs one LegalForecastBench forecast through OpenClaw's managed `agent exec` entrypoint. The upstream runtime owns model calls and the agent loop. The adapter supplies one tool, `lfb_read_task`, which reads the host-staged solver prompt through LegalForecastBench's existing container protocol. It supports `legalforecast_mtd` with `lfb_brier` scoring and `openai:<model>` model keys.

The runtime is pinned to [OpenClaw v2026.9.6](https://github.com/openclaw/openclaw/releases/tag/v2026.9.6), commit `eb377ac59e6c9fd6c7705028034812becf00271b`. Its separate pnpm lockfile pins the distribution and dependency graph. Before each run, the adapter checks the installed package version and distribution build revision and refuses a mismatch or missing installation. These checks identify an installed distribution; they do not attest a hostile machine.

## Install and check

Use Node 24.16+ within major 24, or Node 26.1+, plus pnpm. From the repository root:

```sh
pnpm --dir examples/adapters/openclaw-pinned install --frozen-lockfile
uv run python -m legalforecast.multiharness.openclaw_cli --help
uv run pytest tests/test_multiharness_openclaw.py -q
LEGALFORECAST_OPENCLAW_E2E=1 uv run pytest tests/test_multiharness_openclaw.py -q
```

The isolated package disables dependency lifecycle scripts; the distributed CLI, built-in OpenAI runtime, and adapter tool do not require them. It does not install a gateway service, register interactive logins, or modify an existing OpenClaw profile. Runtime tests are opt-in because installing OpenClaw is a substantial optional dependency.

The ordinary `run` phase is a credential-free conformance fixture. It accepts only the conformance task marker and reports `offline_protocol_fixture: true` and zero provider requests. The historical `../openclaw/adapter-manifest.json` remains explicitly a fixture; use this directory's manifest for the pinned bridge.

## Execute a contributor run

Use this `adapter-manifest.json` through the existing [command adapter and live tool runner](../../../docs/multiharness/adapter-spec.md). Select `run-with-tools`, an `openai:<model>` model key, and a sandbox policy with exactly `OPENAI_API_KEY` in `allowed_provider_env_vars` and `provider-egress-host-only` networking. The caller supplies the normal locked task, nonempty unique `required_unit_ids`, staged `prompt.txt`, and the digest-pinned host tool image. The tool container retains the runner's existing network, filesystem, and credential isolation. Invoke live tool execution through the host runner, not by feeding arbitrary stdin to the adapter CLI.

Each run uses fresh private OpenClaw home, state, config, and working directories. It pins the built-in `openclaw` runtime, disables configured model fallbacks and Code Mode, loads only the OpenAI provider and this adapter's tool plugin, and removes the minimal profile's session and gateway tools. Native shell, filesystem, browser, network, and messaging tools are unavailable. The provider key stays in the host runtime; the tool plugin can request only one fixed solver-prompt read and cannot choose a path or command. Ambient credentials, endpoint overrides, proxies, and `NODE_OPTIONS` are excluded by the shared host environment builder. No persistent gateway runs.

The adapter rejects failed or timed-out turns, served-model drift, missing or repeated solver-prompt reads, and invalid/defaulted predictions. Canonical result metadata records runtime, commit, model, authentication category, and tool policy. Forecast text and runtime stdout/stderr remain private under `private-logs`; temporary config and session state are removed when execution exits. Do not publish those private logs or an OpenClaw state directory.

The outer command adapter owns process containment and timeout cleanup. OpenClaw receives a bounded native timeout as well. A contributor-funded credentialed smoke requires a separately approved model and spending ceiling. This implementation has not established live provider availability, runtime spend accounting, benchmark quality, or full issue #46 completion.

## What the tests prove

Default tests cover public adapter conformance, result normalization, mismatched version/commit rejection, and the actual Node plugin exchanging a solver-prompt read with the Python host protocol bridge. Opt-in installed-runtime tests validate the config, load the plugin through pinned OpenClaw, and run the real upstream agent loop against a local provider double. The local server is an offline test fixture: it does not establish live provider access or forecast quality. None of these tests is the contributor-funded credentialed smoke required by issue #46.
