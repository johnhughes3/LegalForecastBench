# Claude Code runtime image

This image is the exact image producer for the containerized Claude Code adapter. Build it from the repository root with the digest-pinned command below, then pass the resulting image digest to the adapter. The runtime never pulls or builds an image while a benchmark row is running.

```bash
docker build --pull=false -f infra/claude-code-runtime/Containerfile -t lfb-claude-code:2.1.282 .
docker image inspect lfb-claude-code:2.1.282 --format '{{.Id}} {{json .RepoDigests}}'
```

The image pins Claude Code `2.1.282`, carries Python 3, bubblewrap, and socat for Claude's Linux sandbox, and keeps the vendor executable under `/opt/legalforecast/libexec/claude`. The container harness bind-mounts its current CLI fence over `/opt/legalforecast/bin/claude` and removes the vendor directory from `PATH`.

The image also installs a root-owned, mode `0444` `/etc/claude-code/managed-settings.json`. Claude Code reads this file as a managed policy even when an agent invokes the absolute vendor path, so `WebSearch`, `WebFetch`, and user/project MCP tools remain denied; bypass permissions and sideload flags are disabled. The policy also keeps sandboxed subprocesses from inheriting provider credential variables and gives sandboxed networking an empty strict allowlist. The optional built-image E2E test invokes `/opt/legalforecast/libexec/claude` directly with a dummy key and `--tools WebSearch` over `--network none`; the initial stream event must report no tools.

The native adapter passes `--restricted --tools Bash`, excludes user/project settings, and supplies a strict empty domain allowlist. Its production preflight runs the exact rootless, non-privileged bubblewrap namespace operation; a failed preflight refuses before credentials or a model request. That probe is deliberately reported as namespace capability evidence, not as proof that a child cannot inspect a parent environment or proxy. On hosts where rootless Docker does not permit bubblewrap's nested namespace setup, native mode preserves that refusal and does not retry unsandboxed or with weaker nested isolation.

The explicit `outer-container-only` fixture mode is constructed with `gateway_base_url="https://..."`. It skips the unavailable nested bubblewrap probe, keeps the harness on the existing per-run internal Docker network, and permits only the gateway host and port through the existing egress sidecar. The gateway must be separately started on or reachable from that run's egress network; this adapter does not create a gateway or a provider route. The container receives only the public fixture dummy key required by Claude's CLI, never a provider credential. This mode remains fixture-only until a credential broker and authoritative paid-run guard are integrated. `fixture_base_url` remains accepted as a compatibility alias for the gateway endpoint.

The image producer is provider-free. It does not contain an API key, call a model, or publish an image. Both native and outer modes refuse `published-api-key` before credential resolution because the required credential broker and complete child-boundary proof are not available. Fixture runs receive no provider credential; the outer mode's dummy value is not a usable provider key and is scoped to the fixture profile.
