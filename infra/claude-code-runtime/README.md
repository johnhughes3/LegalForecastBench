# Claude Code runtime image

This image is the exact image producer for the containerized Claude Code adapter. Build it from the repository root with the digest-pinned command below, then pass the resulting image digest to the adapter. The runtime never pulls or builds an image while a benchmark row is running.

```bash
docker build --pull=false -f infra/claude-code-runtime/Containerfile -t lfb-claude-code:2.1.282 .
docker image inspect lfb-claude-code:2.1.282 --format '{{.Id}} {{json .RepoDigests}}'
```

The image pins Claude Code `2.1.282`, carries Python 3, bubblewrap, and socat for Claude's Linux sandbox, and keeps the vendor executable under `/opt/legalforecast/libexec/claude`. The container harness bind-mounts its current CLI fence over `/opt/legalforecast/bin/claude` and removes the vendor directory from `PATH`.

The image also installs a root-owned, mode `0444` `/etc/claude-code/managed-settings.json`. Claude Code reads this file as a managed policy even when an agent invokes the absolute vendor path, so `WebSearch`, `WebFetch`, and user/project MCP tools remain denied; bypass permissions and sideload flags are disabled. The policy also keeps sandboxed subprocesses from inheriting provider credential variables and gives sandboxed networking an empty strict allowlist. The optional built-image E2E test invokes `/opt/legalforecast/libexec/claude` directly with a dummy key and `--tools WebSearch` over `--network none`; the initial stream event must report no tools.

The native adapter passes `--restricted --tools Bash`, excludes user/project settings, and supplies a strict empty domain allowlist. Its production preflight runs the exact rootless, non-privileged bubblewrap namespace operation; a failed preflight refuses before credentials or a model request. That probe is deliberately reported as namespace capability evidence, not as proof that a child cannot inspect a parent environment or proxy. On hosts where rootless Docker does not permit bubblewrap's nested namespace setup, native mode preserves that refusal and does not retry unsandboxed or with weaker nested isolation.

The explicit `outer-container-only` mode uses the fixed internal origin `http://lfb-model-gateway:8080` (Claude appends `/v1/messages`). For each run the harness starts a bounded Python gateway and allowlisted CONNECT relay on the per-run `--internal` network, then connects only the relay to the selected egress network. The gateway policy contains one model, one upstream origin, one ingress host, and the fixed internal relay origin; its upstream key and per-run capability are supplied as environment values only to the gateway launch subprocess, never through an env file or Docker argv. The harness receives only the capability-shaped key required by Claude's CLI, never the upstream key, and has no generic proxy variables or direct external network attachment. Fixture runs use a dummy upstream key and the caller's fixture network. The protected terminal workflow derives a paid descriptor from the locked blinded inputs and frozen registry, then launches the pinned gateway image under the existing spend authority. This source path has provider-free fixture validation; it has not yet produced a paid forecast.

The image producer is provider-free. It does not contain an API key, call a model, or publish an image. Native mode refuses a paid run when nested sandbox preflight fails. The public outer-mode command remains usable without credentials through `fixture-none`. Fixture runs receive no provider credential, and their dummy value is not a usable provider key.
