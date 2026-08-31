# Antigravity CLI (agy), tools-on, for the multiharness lane.
#
# This image answers "does the harness beat the bare API?", so the CLI keeps its
# own local tools (its bash/read/write/grep_search suite).  What it must NOT
# keep is any path to the outcomes: the run is executed by
# legalforecast.multiharness.container_harness behind an allowlist CONNECT
# proxy, and the run's egress evidence records what was refused.  See
# examples/adapters/agy-native/ for the argv, and read the WEB RETRIEVAL note
# at the bottom of this file before publishing an agy row.
#
# Staging the binary (one manual step, unlike the npm-installed harnesses):
# agy 1.1.22 ships as a single self-contained Go ELF executable rather than
# through a package registry, so the build context has to be handed the exact
# binary rather than a version string:
#   cp "$(command -v agy)" infra/harness-images/agy/agy
# The staged copy is gitignored -- it is a 208 MB third-party binary and must
# never land in this public repository.
#
# Build (rootless Docker only; never sudo, never the docker group):
#   docker build -t lfb-harness/agy:1.1.22 \
#     -f infra/harness-images/agy/Dockerfile \
#     infra/harness-images/agy
#   docker image inspect --format '{{.Id}}' lfb-harness/agy:1.1.22
# The Id is the sha256: value that goes in the manifest's
# executable.container_image_digest.  It is a local content id, so every host
# that rebuilds re-mints it; that is the point of pinning the digest rather
# than the tag.
FROM debian:bookworm-slim@sha256:88200866dfff7ea7f5cbcb6ec7c8a701889efe6fe859fe64d6990e4b07ea4171

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

# Pinned by content, not by version string: the staged binary is rejected
# unless its bytes hash to the executable characterised on 2026-08-31, and the
# CLI is then asked its own version so a hash that was updated without the
# binary (or the reverse) fails the build rather than the benchmark.
ARG AGY_VERSION=1.1.22
ARG AGY_SHA256=2822292f90deea4556938a8728fe4ed02a1d66d1525cf75fa07a171e36a38c25
COPY agy /usr/local/bin/agy
RUN printf '%s  %s\n' "${AGY_SHA256}" /usr/local/bin/agy | sha256sum -c - \
 && chmod 0755 /usr/local/bin/agy \
 && test "$(agy --version)" = "${AGY_VERSION}"

# NO autoupdater/telemetry ENV BLOCK, because agy 1.1.22 has no kill switch
# for either: its declared AGY_* variables are cosmetic (logo, LaTeX, escape
# sequences), DO_NOT_TRACK is not read, and telemetry is a settings.json key
# that the run's throwaway HOME does not carry.  Both clients will therefore
# attempt their own hosts, the egress proxy will refuse them, and the refusals
# will appear in the run's journal -- expected noise, not a failed run.

# NO `USER` LINE, DELIBERATELY.  Under rootless Docker -- the only sanctioned
# backend here -- the host operator is mapped to container uid 0, so "root" in
# this image is an unprivileged host account with every capability dropped.  A
# non-root USER would instead map to a subuid that does not own the run's
# bind-mounted HOME, and the CLI could not read the 0600 login that
# stage_credential_home() writes.  A rootful-Docker deployment must revisit
# this and pass --user explicitly.
WORKDIR /workspace

# The container plan runs `docker run <image> <manifest argv...>` with no
# --entrypoint of its own, so the CLI has to BE the entrypoint.  The egress
# sidecar overrides this with --entrypoint python3.
ENTRYPOINT ["agy"]

# EGRESS, MEASURED.  The first containerized run (2026-08-31, one attempt) did
# not reach the model: agy's startup eligibility check fetches the signed-in
# operator's Google profile picture from lh3.googleusercontent.com, the
# provider-only allowlist refused that host, and agy exited 1 with
# status ERROR before its first turn.  Reaching a first turn therefore costs
# either that host on the allowlist -- a general user-content CDN, which is a
# real widening of the fence and a lane decision, not a config tweak -- or an
# upstream way to skip the check.  Hosts agy did reach, and which a run needs:
# oauth2.googleapis.com, www.googleapis.com, daily-cloudcode-pa.googleapis.com.
# Hosts it tried and were correctly refused with no ill effect:
# antigravity-unleash.goog (feature flags) and the playwright.azureedge.net
# browser-download CDNs.
#
# WEB RETRIEVAL, THE OPEN GAP.  Claude Code closes the provider-executed web
# tools with --disallowedTools WebSearch WebFetch.  agy 1.1.22 exposes no
# equivalent: `agy --help` lists no tool-selection, tool-denial or
# web-search flag, and its JSON envelope reports neither a tool inventory nor
# any tool call, so a run cannot even show after the fact which tools it had.
# Client-side retrieval is refused by the egress allowlist and journaled; a
# provider-side Gemini grounding call would run on Google's infrastructure,
# downstream of every rule here, and is UNVERIFIED either way.  Do not publish
# an agy forecast row until that is settled upstream or by live
# characterisation.
