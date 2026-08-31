# Grok CLI (xAI "Grok Build"), tools-on, for the multiharness lane.
#
# This image answers "does the harness beat the bare API?", so the CLI keeps
# its own local tools (run_terminal_cmd/read_file/grep/subagents).  What it
# must NOT keep is any path to the outcomes: the run is executed by
# legalforecast.multiharness.container_harness behind an allowlist CONNECT
# proxy, and xAI's server-executed web search is turned off by argv in the
# adapter manifest (see examples/adapters/grok-native/).
#
# Build (rootless Docker only; never sudo, never the docker group):
#   docker build -t lfb-harness/grok:1.0.13 \
#     -f infra/harness-images/grok/Dockerfile \
#     infra/harness-images/grok
#   docker image inspect --format '{{.Id}}' lfb-harness/grok:1.0.13
# The Id is the sha256: value that goes in the manifest's
# executable.container_image_digest.  It is a local content id, so every host
# that rebuilds re-mints it; that is the point of pinning the digest rather
# than the tag.
FROM node:22-bookworm-slim@sha256:83f487e0a63425e5b4d146fb5e5be574bcbe1b7b843d3ebafdd95eaf7767a7e5

# ca-certificates is required to TLS-terminate against xAI through the proxy;
# curl is the run's own blocked-host probe, so the container can show that
# general egress is refused rather than merely assert it.  python3 is here
# because container_harness runs its single-file allowlist proxy as a sidecar
# from this same image, and the sidecar entrypoint is `python3` -- one image
# means one digest to pin instead of two.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates curl python3 \
 && rm -rf /var/lib/apt/lists/*

# Pinned by exact version, and installed as the bare binary rather than
# through the npm trampoline.  xAI's npm package ships the CLI brotli-
# compressed inside a per-platform optional dependency and leaves a JS shim on
# the PATH; that shim decompresses 166 MB into $GROK_HOME/bin on FIRST RUN,
# which here would mean every run -- HOME is a fresh throwaway directory per
# row -- and would fail outright the moment that HOME is not writable.  The
# build-time `grok --version` does not catch it, because the shim answers
# --version itself; `grok --help` in a clean container is what exposed it.
#
# So the payload is decompressed at build time, checked against the SHA-256 of
# the binary that the 2026-08-31 harness characterization actually described,
# and installed at /usr/local/bin/grok.  The check is the point: it makes the
# image byte-identical to the characterized CLI instead of merely
# same-versioned, and it fails the build if npm ever serves different bytes
# under the same version.  The npm package is removed in the same layer so the
# shim cannot shadow the real binary and the 46 MB archive does not ship.
ARG GROK_CLI_VERSION=1.0.13
ARG GROK_CLI_SHA256=edf79521581bb5e6b95abef848491a6a742e860da3e237ebe86a280d30dce4c1
RUN npm install -g --no-fund --no-audit --ignore-scripts \
      "@xai-official/grok@${GROK_CLI_VERSION}" \
 && node -e "const z=require('zlib'),f=require('fs');\
const d=process.argv[1];\
f.writeFileSync('/tmp/grok.bin', z.brotliDecompressSync(f.readFileSync(d)));" \
      "/usr/local/lib/node_modules/@xai-official/grok/node_modules/@xai-official/grok-linux-x64/bin/grok.br" \
 && echo "${GROK_CLI_SHA256}  /tmp/grok.bin" | sha256sum -c - \
 && npm uninstall -g --no-fund --no-audit @xai-official/grok \
 && npm cache clean --force \
 && install -m 0755 /tmp/grok.bin /usr/local/bin/grok \
 && rm -f /tmp/grok.bin \
 && grok --version

# Contamination fence, and it is not optional here.  Run in an empty directory
# on the characterization host, `grok inspect --json` reported the operator's
# global ~/.claude/CLAUDE.md as an active projectInstruction plus a large set
# of user skills: grok reads Claude's and Cursor's surfaces by default, so a
# bare run silently injects another vendor's instructions into the system
# prompt and destroys run-to-run comparability across harnesses.  The clean
# container HOME already has none of those files; these turn the reader off at
# the source so a future credential-staging change cannot re-open it.
ENV GROK_CLAUDE_RULES_ENABLED=0 \
    GROK_CLAUDE_SKILLS_ENABLED=0 \
    GROK_CLAUDE_AGENTS_ENABLED=0 \
    GROK_CLAUDE_MCPS_ENABLED=0 \
    GROK_CLAUDE_HOOKS_ENABLED=0 \
    GROK_CURSOR_RULES_ENABLED=0 \
    GROK_CURSOR_SKILLS_ENABLED=0 \
    GROK_CURSOR_AGENTS_ENABLED=0 \
    GROK_CURSOR_MCPS_ENABLED=0 \
    GROK_CURSOR_HOOKS_ENABLED=0

# The updater and the changelog fetch would be silent refusals in the egress
# evidence rather than useful signals, and cross-session memory could carry
# state between benchmark cases.  GROK_MEMORY and GROK_DISABLE_AUTOUPDATER are
# also set as child environment by the subscription lane; setting them in the
# image covers the fixture-none profile, which projects no child environment
# at all.
ENV GROK_DISABLE_AUTOUPDATER=1 \
    GROK_MEMORY=0 \
    GROK_CHANGELOG_OFFLINE=1

# GROK_HOME is deliberately NOT set.  It relocates the whole grok state
# directory including auth.json, and the run's login is staged at
# $HOME/.grok/auth.json by stage_credential_home(); overriding it here would
# point the CLI at an empty directory and fail the run as "not signed in".

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
ENTRYPOINT ["grok"]
