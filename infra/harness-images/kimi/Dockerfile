# Kimi Code, tools-on, for the multiharness lane.
#
# This image answers "does the harness beat the bare API?", so the CLI keeps its
# own local tools (Bash/Read/Write/Edit/Grep/Agent).  What it must NOT keep is
# any path to the outcomes: the run is executed by
# legalforecast.multiharness.container_harness behind an allowlist CONNECT
# proxy, and Kimi's two retrieval tools are redirected off the provider host by
# the ENV block below (see the "web tools" note -- this harness has no flag).
#
# Build (rootless Docker only; never sudo, never the docker group):
#   docker build -t lfb-harness/kimi:0.36.0 \
#     -f infra/harness-images/kimi/Dockerfile \
#     infra/harness-images/kimi
#   docker image inspect --format '{{.Id}}' lfb-harness/kimi:0.36.0
# The Id is the sha256: value that goes in the manifest's
# executable.container_image_digest.  It is a local content id, so every host
# that rebuilds re-mints it; that is the point of pinning the digest rather
# than the tag.
FROM node:22-bookworm-slim@sha256:83f487e0a63425e5b4d146fb5e5be574bcbe1b7b843d3ebafdd95eaf7767a7e5

# ca-certificates TLS-terminates against the provider through the proxy; curl is
# the run's own blocked-host probe; python3 runs the single-file allowlist proxy
# as a sidecar from this same image, so one image means one digest to pin.
#
# ripgrep is not optional here.  Kimi's Grep tool resolves `rg` and, when it
# finds none, downloads a pinned ripgrep 15.0.0 archive from its own CDN -- a
# host the egress allowlist refuses, which would silently degrade a *local*
# tool this lane exists to measure.  Installing the distro build puts `rg` on
# PATH before that download is ever attempted.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates curl python3 ripgrep \
 && rm -rf /var/lib/apt/lists/*

# Pinned by exact version.  The npm wrapper bakes the platform binary into the
# image at build time, so nothing is fetched at run time -- which matters,
# because at run time the only reachable host is the provider's.
ARG KIMI_CODE_VERSION=0.36.0
RUN npm install -g --no-fund --no-audit \
      "@moonshot-ai/kimi-code@${KIMI_CODE_VERSION}" \
 && npm cache clean --force \
 && kimi --version

# WEB TOOLS OFF -- READ THIS BEFORE CHANGING IT.
#
# Kimi's WebSearch and FetchURL are backed by two Moonshot services whose
# default base URLs sit on the SAME HOST as the model API (.../coding/v1/search
# and .../coding/v1/fetch).  A host-level egress allowlist therefore cannot
# separate them from the completion traffic it has to allow, and Kimi 0.36.0
# exposes no --tools / --disallowed-tools flag in print mode: the only
# reachable lever is the service base URL itself.
#
# Pointing both at a reserved-by-RFC-2606 .invalid host is a fail-closed
# redirect that is also *recorded*: the container's only route out is the
# CONNECT proxy, so an attempted retrieval lands in the run's egress evidence
# as a refused host rather than disappearing inside allowed provider traffic.
# Loopback would be the wrong choice -- NO_PROXY covers it, so the refusal
# would never reach the proxy log.
#
# Precedence is verified against the CLI's bundled source, not assumed, because
# a staged config.toml carries [services.moonshot_search] / [services.
# moonshot_fetch] blocks naming the real endpoints: withServiceEnv() checks the
# env base URL FIRST and, when it is set, returns a fresh service entry built
# from the environment alone -- the configured endpoint, its API key and its
# OAuth reference are all discarded.  Env wins unconditionally, so the redirect
# survives credential staging.
#
# What this does NOT do is unregister the tools: the model still sees WebSearch
# and FetchURL and may call them.  That is why the redirect target has to be a
# host the proxy refuses -- the call fails at the fence and the attempt is
# counted (parser_kimi.KimiStreamResult.web_tools_invoked) instead of being
# indistinguishable from allowed provider traffic.
#
# These forecasts are about real federal cases whose outcomes are one search
# away, so this is an integrity control, not a tidiness one.
ENV KIMI_WEB_SEARCH_BASE_URL=https://web-tools-disabled.invalid/ \
    KIMI_WEB_FETCH_BASE_URL=https://web-tools-disabled.invalid/

# The update preflight runs in print mode too, and on one branch it exits 0
# with empty stdout -- which a naive parser reads as an empty successful
# answer -- and on another it replaces the binary mid-benchmark, invalidating
# the pinned image.  Both spellings are honoured; set both.
#
# KIMI_DISABLE_TELEMETRY is set but does NOT fully take: the 2026-08-31 live
# containerized run still attempted one CONNECT to the telemetry endpoint with
# this set to 1, which the allowlist proxy refused and recorded.  It stays here
# because it costs nothing and suppresses the collector's other paths; the fence
# is what actually stops the traffic, and the refusal in the egress evidence is
# how a run shows it.
ENV KIMI_CODE_NO_AUTO_UPDATE=1 \
    KIMI_CLI_NO_AUTO_UPDATE=1 \
    KIMI_DISABLE_TELEMETRY=1

# Deliberately NOT set: KIMI_CODE_HOME.  It relocates the whole state directory
# *including* the credential store, so pointing it anywhere but $HOME would
# hide the login the run stages into the container HOME.

# NO `USER` LINE, DELIBERATELY.  Under rootless Docker -- the only sanctioned
# backend here -- the host operator is mapped to container uid 0, so "root" in
# this image is an unprivileged host account with every capability dropped.  A
# non-root USER would instead map to a subuid that does not own the run's
# bind-mounted HOME, and the CLI could not read the 0600 login that
# stage_credential_home() writes.  A rootful-Docker deployment must revisit
# this and pass --user explicitly.
WORKDIR /workspace

# Kimi has no working-directory flag: the process cwd *is* the workspace, and
# the container plan sets --workdir /workspace.  The plan also runs
# `docker run <image> <manifest argv...>` with no --entrypoint of its own, so
# the CLI has to BE the entrypoint.  The egress sidecar overrides this with
# --entrypoint python3.
ENTRYPOINT ["kimi"]
