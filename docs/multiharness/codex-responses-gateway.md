# Codex Responses gateway

LegalForecastBench can place native Codex behind a bounded local gateway that speaks the OpenAI Responses protocol. The gateway is a protocol proxy only: the pinned Codex runtime owns the agent loop, native tools, retries, and sandbox.

The official Codex `codex-responses-api-proxy` confirms the supported wire seam: Codex uses a custom `model_providers.<name>` entry with `wire_api = "responses"`, the proxy accepts only `POST /v1/responses`, and the provider key is held by the privileged proxy. That proxy is not the LFB paid gateway because its upstream is configurable and it has no LFB run-capability, reservation, or durable settlement contract.

The existing protected descriptor issuer now has a real OpenAI/Codex mode. Given the same locked run inputs, approved ceiling, and protected authority environment used by the other paid terminal harnesses, the exact producer is:

```bash
uv run python -m legalforecast.multiharness.paid_gateway_descriptor \
  --manifest /protected/run-manifest.json \
  --forecast /protected/forecast-release.json \
  --artifact-root /protected/release \
  --model-registry /protected/model-registry.json \
  --model-key openai:MODEL_ID \
  --ceiling-microusd APPROVED_CEILING \
  --account APPROVED_ACCOUNT \
  --harness codex \
  --output /protected/codex-paid-gateway.json
```

The command performs no AWS or provider request. It derives `provider=openai` from the locked model key, binds that provider into the existing authority and reservation-ledger identities, and refuses Anthropic models in `--harness codex` mode. The gateway consumes that produced descriptor directly:

```bash
uv run python -m legalforecast.multiharness.container_harness.model_gateway_responses_server \
  --paid-config /protected/codex-paid-gateway.json \
  --model-registry /protected/model-registry.json \
  --server-info /protected/server-info.json
```

The protected workflow must project `LFB_RESPONSES_UPSTREAM_API_KEY` only into this gateway process, and must provide `LFB_RESPONSES_CAPABILITY_TOKEN` and `LFB_RESPONSES_REQUEST_ID`. Secret values are never command-line arguments. The gateway binds only to loopback, fixes its upstream to `https://api.openai.com/v1/responses`, permits only `openai:<model>` keys from the paid descriptor, rejects `CONNECT`, and rejects client-supplied provider credentials.

After the server writes its loopback port, the parent runner supplies Codex's supported custom-provider arguments. No new agent loop or controller is involved:

```toml
[model_providers.lfb-openai]
name = "LegalForecastBench OpenAI Responses gateway"
base_url = "http://127.0.0.1:<gateway-port>/v1"
env_key = "LFB_RESPONSES_CAPABILITY_TOKEN"
wire_api = "responses"
```

The corresponding native invocation uses `-c 'model_provider="lfb-openai"'` and the provider table above, with `LFB_RESPONSES_CAPABILITY_TOKEN` projected only to Codex. The checked-in 0.147 manifest remains authoritative; a different installed Codex version is diagnostic only until its manifest pin is deliberately updated and validated.

The gateway forwards accepted request and response bodies unchanged. Requests must set `store=false`, use the one service tier represented by the frozen registry price source, and may advertise Codex's local `function`, `custom`, and nested `namespace` tool definitions. Hosted web search, file search, MCP, computer tools, and structured remote input URLs are refused before reservation or upstream transport. Client `OpenAI-Organization` and `OpenAI-Project` headers are not trusted or forwarded.

For streaming responses the gateway retains the bounded SSE bytes and requires exactly one terminal event. Only `response.completed` is returned as HTTP success. `response.failed` and `response.incomplete` settle valid reported usage but return a sanitized gateway error; duplicate, conflicting, malformed, or transport-truncated terminal evidence remains unknown and retains the conservative reservation. Cache reads and cache writes are separately parsed from `input_tokens_details`, their sum cannot exceed total input, and an omitted dimension remains unknown rather than becoming zero.

The credential-free native-loop regression can be run when the exact manifest-pinned binary is available:

```bash
LEGALFORECAST_CODEX_0147_BIN=/path/to/pinned/codex \
  uv run pytest tests/test_container_model_gateway_responses_codex.py -q
```

That test starts the real Codex subprocess with an empty isolated home, sends its native function-tool request through the loopback gateway, returns a local tool call, observes Codex's tool result in the second model turn, and finishes without an OpenAI login, provider credential, or paid request.

The implementation is source- and protocol-tested only. The protected parent still must launch the sidecar and Codex together, project the approved host-only OpenAI key and per-run capability, inspect the existing ceiling journal, and run the separately approved live smoke. The loopback native test is not provider readiness or live-spend proof.
