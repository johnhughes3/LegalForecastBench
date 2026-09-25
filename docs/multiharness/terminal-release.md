# Claude Code terminal release run

`legalforecast multiharness release-run` evaluates one outcome-blinded forecast release with the real headless Claude Code CLI. It gives Claude Code a read-only prompt and the permitted case documents, collects one forecast envelope per case, and scores every selected prediction unit. The result directory contains `scores.json`, per-case run records, container packages, and private transcripts. Failed or invalid attempts stay in the denominator under the stated failure policy; the report includes both micro-Brier and equal-case Brier.

The public command uses a provider-free fixture endpoint. Build the pinned CLI image from the repository root, then use its image ID with an issued synthetic release and an Anthropic-compatible local fixture:

```bash
docker build --pull=false -f infra/claude-code-runtime/Containerfile -t lfb-claude-code:local .
docker image inspect --format '{{.Id}}' lfb-claude-code:local
uv run legalforecast release issue-synthetic --output-dir run-inputs
docker network create lfb-local-fixture
docker run -d --name lfb-local-fixture-server --network lfb-local-fixture \
  --network-alias fixture-upstream --read-only --cap-drop ALL \
  --security-opt no-new-privileges:true \
  --mount "type=bind,src=$PWD/tests/fixtures/claude_code/release_fixture_server.py,dst=/opt/fixture.py,readonly" \
  --entrypoint /usr/bin/python3 lfb-claude-code:local /opt/fixture.py
uv run legalforecast multiharness release-run \
  --forecast-release run-inputs/forecast-release.json \
  --labels-release run-inputs/labels-release.json \
  --artifact-root run-inputs \
  --output-dir run-results \
  --model-key anthropic:claude-opus-5-5 \
  --image sha256:REPLACE_WITH_BUILT_IMAGE_ID \
  --fixture-base-url http://fixture-upstream:8081/v1 \
  --fixture-egress-network lfb-local-fixture
```

The fixture server runs under the `fixture-upstream` alias. After inspecting the result, remove the fixture container and network with `docker rm -f lfb-local-fixture-server` and `docker network rm lfb-local-fixture`. The outer container runner places the harness and model gateway on a per-run internal network. Only the fixed CONNECT relay joins the fixture network; the harness has no direct external route. The gateway rejects provider-side web and remote tools, while the image's managed Claude policy disables `WebSearch`, `WebFetch`, and MCP tools even if the agent invokes the vendor binary directly. Local Bash tools remain available for case work.

The repository's opt-in rootless smoke runs the complete scored path against a local fixture without a provider key:

```bash
LFB_TERMINAL_RELEASE_E2E_IMAGE=sha256:REPLACE_WITH_BUILT_IMAGE_ID \
  uv run pytest -q tests/test_terminal_release_container_e2e.py
```

These fixture results demonstrate execution and scoring behavior. They are not model forecasts or benchmark results. Paid runs require the protected workflow's credential and spend authority and remain subject to the existing spending and publication boundaries.
