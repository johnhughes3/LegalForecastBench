# Claude Code runtime image

This image is the exact image producer for the containerized Claude Code adapter. Build it from the repository root with the digest-pinned command below, then pass the resulting image digest to the adapter. The runtime never pulls or builds an image while a benchmark row is running.

```bash
docker build --pull=false -f infra/claude-code-runtime/Containerfile -t lfb-claude-code:2.1.282 .
docker image inspect lfb-claude-code:2.1.282 --format '{{.Id}} {{json .RepoDigests}}'
```

The image pins Claude Code `2.1.282`, carries Python 3, bubblewrap, and socat for Claude's Linux sandbox, and keeps the vendor executable under `/opt/legalforecast/libexec/claude`. The container harness bind-mounts its current CLI fence over `/opt/legalforecast/bin/claude` and removes the vendor directory from `PATH`. The vendor executable remains directly executable by the container user at its absolute `libexec` path; this generic wrapper therefore is not, by itself, an immutable binary boundary.

The adapter passes `--restricted --tools Bash`, disables `WebSearch` and `WebFetch`, excludes user/project settings, and supplies a strict empty domain allowlist. Its production preflight runs the exact rootless, non-privileged bubblewrap namespace operation; a failed preflight refuses before credentials or a model request. That probe is deliberately reported as namespace capability evidence, not as proof that a child cannot inspect a parent environment or proxy. The published-api-key profile therefore remains a typed refusal until a credential broker and complete child-boundary probe are available. On hosts where rootless Docker does not permit bubblewrap's nested namespace setup, the adapter preserves that refusal and does not retry unsandboxed or with weaker nested isolation.

The image producer is provider-free. It does not contain an API key, call a model, or publish an image. The current adapter refuses `published-api-key` before credential resolution because the required credential broker and complete child-boundary probe are not available; fixture runs receive no provider credential.
