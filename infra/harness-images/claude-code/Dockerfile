# Claude Code, tools-on, for the multiharness lane.
#
# This image answers "does the harness beat the bare API?", so the CLI keeps its
# own local tools (Bash/Read/Write/Edit/Task).  What it must NOT keep is any
# path to the outcomes: the run is executed by
# legalforecast.multiharness.container_harness behind an allowlist CONNECT
# proxy, and the provider-executed web tools are turned off by argv in the
# adapter manifest (see examples/adapters/claude-code-native/).
#
# Build (rootless Docker only; never sudo, never the docker group):
#   docker build -t lfb-harness/claude-code:2.1.251 \
#     -f infra/harness-images/claude-code/Dockerfile \
#     infra/harness-images/claude-code
#   docker image inspect --format '{{.Id}}' lfb-harness/claude-code:2.1.251
# The Id is the sha256: value that goes in the manifest's
# executable.container_image_digest.  It is a local content id, so every host
# that rebuilds re-mints it; that is the point of pinning the digest rather
# than the tag.
FROM node:22-bookworm-slim@sha256:83f487e0a63425e5b4d146fb5e5be574bcbe1b7b843d3ebafdd95eaf7767a7e5

# ca-certificates is required to TLS-terminate against the provider through the
# proxy; curl is the run's own blocked-host probe, so the container can show
# that general egress is refused rather than merely assert it.  python3 is here
# because container_harness runs its single-file allowlist proxy as a sidecar
# from this same image, and the sidecar entrypoint is `python3` -- one image
# means one digest to pin instead of two.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates curl python3 \
 && rm -rf /var/lib/apt/lists/*

# Pinned by exact version.  The npm wrapper's postinstall resolves the
# platform's optionalDependency and bakes the native binary into the image, so
# nothing is downloaded at run time -- which matters, because at run time the
# only reachable hosts are the provider's.
ARG CLAUDE_CODE_VERSION=2.1.251
RUN npm install -g --no-fund --no-audit \
      "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}" \
 && npm cache clean --force \
 && claude --version

# Nothing here needs the network except the provider, and every one of these
# would be a silent refusal in the egress evidence rather than a useful signal.
ENV CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 \
    DISABLE_AUTOUPDATER=1 \
    DISABLE_TELEMETRY=1 \
    DISABLE_ERROR_REPORTING=1 \
    DISABLE_BUG_COMMAND=1 \
    CLAUDE_CODE_DISABLE_TERMINAL_TITLE=1

# --permission-mode bypassPermissions is refused under uid 0 unless the CLI can
# see that the operator put it in a sandbox on purpose
# (isRootOutsideDeliberateSandbox: uid 0 and IS_SANDBOX unset and no
# CLAUDE_CODE_BUBBLEWRAP).  It IS in one: no capabilities, no-new-privileges, a
# read-only rootfs, and a network with no route off the host.
ENV IS_SANDBOX=1

# NO `USER` LINE, DELIBERATELY.  Under rootless Docker -- the only sanctioned
# backend here -- the host operator is mapped to container uid 0, so "root" in
# this image is an unprivileged host account with every capability dropped.  A
# non-root USER would instead map to a subuid that does not own the run's
# bind-mounted HOME, and the CLI could not read the 0600 login that
# stage_credential_home() writes.  A rootful-Docker deployment must revisit
# this and pass --user explicitly.
WORKDIR /workspace

# The container plan runs `docker run <image> <manifest argv...>` with no
# --entrypoint of its own, so the CLI has to BE the entrypoint.  Without this
# the base image's node entrypoint would receive `-p <prompt> ...` and run the
# wrong program.  The egress sidecar overrides this with --entrypoint python3.
ENTRYPOINT ["claude"]
