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

For a split execution and scoring handoff, use `release-execute` with the same execution arguments above but omit `--labels-release`. It writes a portable, outcome-blinded run directory without reading labels. Move that directory to the scoring host, then run:

```bash
uv run legalforecast multiharness release-score \
  --run-dir run-results \
  --forecast-release run-inputs/forecast-release.json \
  --labels-release run-inputs/labels-release.json \
  --artifact-root run-inputs
```

The score command reads and validates the saved run package and writes `run-results/scores.json`; it does not launch Claude Code or contact a model provider. Keep the labels release outside the forecast worker and its container mounts. A failed forecast row remains in the scored unit denominator, while an incomplete package cannot claim a complete headline result.

The repository's opt-in rootless smoke runs the complete scored path against a local fixture without a provider key:

```bash
LFB_TERMINAL_RELEASE_E2E_IMAGE=sha256:REPLACE_WITH_BUILT_IMAGE_ID \
  uv run pytest -q tests/test_terminal_release_container_e2e.py
```

These fixture results demonstrate execution and scoring behavior. They are not model forecasts or benchmark results. Paid runs require the protected workflow's credential and spend authority and remain subject to the existing spending and publication boundaries.

The protected `run-benchmark.yaml` workflow accepts `execution_mode: claude-code-terminal`. Its terminal job reuses the locked outcome-blinded inputs, builds digest-pinned CLI and gateway images, and writes an `official-terminal-forecast-results-<run-id>-attempt-<attempt>` artifact. That artifact contains the scoreless run package and the exact blinded inputs. The terminal job has no labels and does not publish scores. It uses the existing run ceiling and protected provider authority; a local fixture run does not authorize a paid dispatch.

After that workflow attempt completes, `score-terminal-release.yaml` can score its exact artifact ID in the protected fan-in environment. The dispatch supplies the source run ID and attempt, artifact ID, locked manifest, forecast and artifact locations, labels location, and model key. The score workflow compares the package's preserved blinded inputs with the locked inputs, reads labels only inside fan-in, and uploads a score artifact. It can retain partial failure scores, but an incomplete run cannot report a complete benchmark result. This path does not publish a benchmark release; publication remains a separate decision and workflow.
