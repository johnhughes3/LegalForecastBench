# Codex Responses gateway

LegalForecastBench can place native Codex behind a bounded local gateway that speaks the OpenAI Responses protocol. The gateway is a protocol proxy only: the pinned Codex runtime owns the agent loop, native tools, retries, and sandbox.

The official Codex `codex-responses-api-proxy` confirms the supported wire seam: Codex uses a custom `model_providers.<name>` entry with `wire_api = "responses"`, the proxy accepts only `POST /v1/responses`, and the provider key is held by the privileged proxy. That proxy is not the LFB paid gateway because its upstream is configurable and it has no LFB run-capability, reservation, or durable settlement contract.

The LFB entrypoint is:

```bash
uv run python -m legalforecast.multiharness.container_harness.model_gateway_responses_server \
  --paid-config /protected/paid-gateway.json \
  --model-registry /protected/model-registry.json \
  --server-info /protected/server-info.json
```

The protected workflow must project `LFB_RESPONSES_UPSTREAM_API_KEY` only into this gateway process, and must provide `LFB_RESPONSES_CAPABILITY_TOKEN` and `LFB_RESPONSES_REQUEST_ID`. Secret values are never command-line arguments. The gateway binds only to loopback, fixes its upstream to `https://api.openai.com/v1/responses`, permits only `openai:<model>` keys from the paid descriptor, rejects `CONNECT`, and rejects client-supplied provider credentials.

The Codex-side provider configuration is produced by the protected issuer for the selected run and has this shape:

```toml
[model_providers.lfb-openai]
name = "LegalForecastBench OpenAI Responses gateway"
base_url = "http://127.0.0.1:<gateway-port>/v1"
env_key = "LFB_RESPONSES_CAPABILITY_TOKEN"
wire_api = "responses"
```

The gateway forwards request and response bodies unchanged. For a streaming response it retains the bounded SSE bytes, extracts only the terminal `response.completed` usage object required for settlement, and then returns the exact SSE body and content type to Codex. It preserves `input_tokens_details.cached_tokens` and `output_tokens_details.reasoning_tokens` in the raw provider evidence used by the OpenAI charge extractor; missing usage or malformed cache dimensions fail closed and are never treated as zero.

The implementation is source- and protocol-tested only. Wiring the protected benchmark producer, projecting the key, obtaining the approved spend ceiling, and running a real Codex subprocess remain parent-owned acceptance work. Offline HTTP tests are not provider or live-spend proof.
