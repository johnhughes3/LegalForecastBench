# Hermes Agent community bridge

The real bridge uses Hermes' managed Python library, `AIAgent.run_conversation`, with the upstream tool registry. It pins release `v2026.9.24`, commit `f97608f178d1ffeca59860195ab7da295f7c8e5f`, package version `0.21.5`. The historical `adapter-manifest.json` remains an explicitly named no-network fixture; use `examples/adapters/hermes-agent/live-manifest.json` for the real bridge.

Install Hermes separately because its supported Python range excludes the benchmark's Python 3.14:

```bash
git clone --branch v2026.9.24 https://github.com/NousResearch/hermes-agent.git hermes-agent
uv sync --project hermes-agent --frozen --no-dev --python 3.13
```

Make a local copy of the live manifest and set `--hermes-checkout` to the absolute path of this clean checkout. Do not place `.env` credentials in the checkout. The adapter requires its exact tag and commit and rejects tracked modifications and untracked source files. The installed runtime must report version `0.21.5`.

Select an `openrouter:<model>` model and grant only the contributor's `OPENROUTER_API_KEY` in the sandbox policy. The command adapter keeps that credential in its host process; the model's sole tool, `read_canonical_task`, sends a `read_text` request over the existing host-owned container protocol. The tool container receives no provider credential. Run through the normal community runner with the host-authenticated solver input and a digest-pinned tool image; bare `run` without the tool channel refuses execution.

Each attempt gets a new private profile, working directory, and session. Memory, profile injection, background review, project context, plugins, and MCP servers are disabled. Hermes tool search is disabled so the model receives exactly the canonical-task tool schema. The bridge checks the exposed tools before inference and reads the host-authenticated prompt once. The model reads that prompt in sequential chunks; acceptance requires complete coverage. Bounded chunks prevent Hermes from spilling large tool output to local files that the model cannot read. Hermes owns the conversation, with 200 iterations and a 180-second runtime budget; the outer command adapter enforces the process and container timeout. These limits are not a dollar-denominated spend cap. Contributor-funded use still requires the normal spending approval.

The final forecast must pass the benchmark's strict parser for the exact required units. Failed, partial, malformed, or mismatched completions are rejected. The full trajectory stays under `private-logs`; public output contains only runtime, auth, model and adapter provenance plus session and trajectory hashes. It never exports the transcript or forecast rationale. A served model is reported only when Hermes supplies it; the requested model is not proof of the provider's actual deployment.

Offline verification:

```bash
uv run pytest tests/test_multiharness_hermes_agent.py -q
LEGALFORECAST_HERMES_CHECKOUT=/path/to/hermes-agent uv run pytest tests/test_multiharness_hermes_agent.py -q
```

The second command additionally executes the pinned upstream managed conversation with SDK response fixtures and network calls blocked. It exercises a real Hermes tool invocation and result path, but neither command proves live provider execution or container isolation. A contributor-funded credentialed smoke and public-package validation remain required before issue #45 can close.

Upstream contracts: [Python library architecture](https://github.com/NousResearch/hermes-agent/blob/f97608f178d1ffeca59860195ab7da295f7c8e5f/website/docs/developer-guide/architecture.md), [tool registry](https://github.com/NousResearch/hermes-agent/blob/f97608f178d1ffeca59860195ab7da295f7c8e5f/website/docs/developer-guide/tools-runtime.md), and [tool-search controls](https://github.com/NousResearch/hermes-agent/blob/f97608f178d1ffeca59860195ab7da295f7c8e5f/website/docs/user-guide/features/tool-search.md).
