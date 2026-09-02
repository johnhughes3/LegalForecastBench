# Codex CLI, tools-on, for the multiharness lane.
#
# This image answers "does the harness beat the bare API?", so the CLI keeps
# its own tools (shell, apply_patch, file edits, subagents).  Codex ships its
# OWN inner sandbox -- Landlock/seccomp on Linux -- and its help text says
# --dangerously-bypass-approvals-and-sandbox is "intended solely for running in
# environments that are externally sandboxed".  This container IS that
# environment: no capabilities, no-new-privileges, a read-only rootfs, and an
# --internal network whose only door is the allowlist CONNECT proxy in
# legalforecast.multiharness.container_harness.  Leaving the inner sandbox on
# would instead measure a doubly-jailed agent that cannot use its own tools.
#
# The provider-executed web tool is a separate problem the container cannot
# solve, because it runs on the provider's infrastructure: it is turned off by
# argv in the adapter manifest (see examples/adapters/codex-cli-native/).
#
# Build (rootless Docker only; never sudo, never the docker group):
#   docker build -t lfb-harness/codex-cli:0.151.0 \
#     -f infra/harness-images/codex-cli/Dockerfile \
#     infra/harness-images/codex-cli
#   docker image inspect --format '{{.Id}}' lfb-harness/codex-cli:0.151.0
# The Id is the sha256: value that goes in the manifest's
# executable.container_image_digest.  It is a local content id, so every host
# that rebuilds re-mints it; that is the point of pinning the digest rather
# than the tag.
FROM node:22-bookworm-slim@sha256:83f487e0a63425e5b4d146fb5e5be574bcbe1b7b843d3ebafdd95eaf7767a7e5

# ca-certificates TLS-terminates against the provider through the proxy; curl
# is the run's own blocked-host probe, so a run can SHOW that general egress is
# refused rather than assert it; python3 is here because container_harness runs
# its single-file allowlist proxy as a sidecar from this same image, so one
# image means one digest to pin instead of two.  git is here because Codex is a
# coding agent whose apply_patch and ghost-snapshot paths shell out to it --
# --skip-git-repo-check silences only the startup check, not those.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates curl git python3 \
 && rm -rf /var/lib/apt/lists/*

# Pinned by exact version.  The npm wrapper's postinstall resolves the
# platform's optionalDependency (@openai/codex-linux-x64) and bakes the native
# binary into the image, so nothing is downloaded at run time -- which matters,
# because at run time the only reachable hosts are the provider's.
ARG CODEX_CLI_VERSION=0.151.0
RUN npm install -g --no-fund --no-audit \
      "@openai/codex@${CODEX_CLI_VERSION}" \
 && npm cache clean --force \
 && codex --version

# NO `USER` LINE, DELIBERATELY.  Under rootless Docker -- the only sanctioned
# backend here -- the host operator is mapped to container uid 0, so "root" in
# this image is an unprivileged host account with every capability dropped.  A
# non-root USER would instead map to a subuid that does not own the run's
# bind-mounted HOME, and the CLI could not read the 0600 auth.json that
# stage_credential_home() writes.  A rootful-Docker deployment must revisit
# this and pass --user explicitly.
#
# CODEX_HOME is deliberately NOT set: it defaults to $HOME/.codex, and the run
# plan points HOME at a fresh throwaway directory holding only the staged
# login.  That default is also the fix for this CLI's worst contamination
# problem -- $CODEX_HOME/AGENTS.md is injected into every run as a user
# message, and on a developer host that is tens of kilobytes of personal
# operator instructions.  A clean HOME has no AGENTS.md at all.
WORKDIR /workspace

# The container plan runs `docker run <image> <manifest argv...>` with no
# --entrypoint of its own, so the CLI has to BE the entrypoint.  Without this
# the base image's node entrypoint would receive `exec --json ...` and run the
# wrong program.  The egress sidecar overrides this with --entrypoint python3.
ENTRYPOINT ["codex"]
