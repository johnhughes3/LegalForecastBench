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

# THE WEB-RETRIEVAL FENCE, VERIFIED.  agy 1.1.22 has no tool-denial flag, so
# the fence is a PreToolUse lifecycle hook: agy hands the pending tool call to
# this handler on stdin, and a `{"decision": "deny"}` answer is, in the CLI's
# own embedded hook reference, a hard block of that execution.  The matcher
# covers `search_web`, `read_url_content` and every browser tool, and nothing
# else -- this is the tools-on lane, so bash, file and grep tools stay live.
# See deny_web_tools.py for why a hook rather than the `disabledTools` settings
# key (that key is scoped to one MCP server entry, not to the built-in suite),
# and entrypoint.sh for why the hook config is written at run time.
#
# Proven live on 2026-08-31, in three independent ways: the run's own denial
# journal recorded `search_web`; the model answered "WEB-BLOCKED" while still
# reading its workspace file; and agy's transcript shows the planner issuing
# `search_web` and `view_file` in the same step, with only `view_file`
# producing a result step.  The blocked call leaves a gap in the step index,
# which is what a hard block looks like from the outside.
#
# THE UNFENCED CONTROL, RUN 2026-09-01.  Those runs could not distinguish
# "the fence stopped a search that would have worked" from "the search would
# have failed anyway", because the hook blocks the call before any request is
# made.  Two runs of THIS image -- same prompt, same allowlist, same login --
# settle it, and the control needs no image change: entrypoint.sh only writes
# a hook file that is ABSENT, so pre-seeding $HOME/.gemini/config/hooks.json
# and $HOME/.gemini/antigravity-cli/hooks.json with `{}` runs the committed
# image with no fence loaded.  The test_agy_entrypoint_* cases in
# tests/test_container_harness_egress.py pin that seed-only-if-absent
# property, which is the only thing the control rests on.  The prompt asked
# for the S&P 500 close on 31 August 2026 -- a number in no file in the
# and could not be in any model's weights -- plus a token planted in a
# workspace file, so a run that did nothing is distinguishable from one that
# worked but could not search.
#
#   unfenced: answered CLOSE=7,686.14 SOURCE=apnews.com, which is the real
#             figure; no denial journal was written.
#   fenced:   answered CLOSE=WEB-BLOCKED, and
#             /workspace/.lfb-agy-tool-denials.jsonl recorded `search_web`.
#
# Both arms echoed the planted token, so local tools stayed live in both.  The
# domain agy cited is NOT on the allowlist below and appears in NEITHER arm's
# refusal list -- the two lists are identical -- so the search ran
# provider-side inside the same TLS session as the model call, exactly as
# deny_web_tools.py describes, and no egress rule in this file could have
# reached it.  This hook is therefore the ONLY thing standing between an agy
# run and a live lookup of the outcome it is being scored on.  Removing it, or
# letting agy rename search_web out from under the matcher, silently makes
# every agy row in this lane unpublishable.
COPY deny_web_tools.py /usr/local/bin/lfb-agy-deny-web-tools
COPY hooks-shared-root.json /opt/legalforecast/agy-hooks-shared-root.json
COPY hooks-cli-root.json /opt/legalforecast/agy-hooks-cli-root.json
COPY entrypoint.sh /usr/local/bin/lfb-agy-entrypoint
RUN chmod 0755 /usr/local/bin/lfb-agy-deny-web-tools /usr/local/bin/lfb-agy-entrypoint \
 && chmod 0644 /opt/legalforecast/agy-hooks-shared-root.json \
               /opt/legalforecast/agy-hooks-cli-root.json \
 && python3 -c "import json,sys;[json.load(open(p)) for p in sys.argv[1:]]" \
      /opt/legalforecast/agy-hooks-shared-root.json \
      /opt/legalforecast/agy-hooks-cli-root.json

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
# --entrypoint of its own, so the CLI has to BE the entrypoint -- here, behind
# the wrapper that seeds the fence into the run's HOME and then execs it.  The
# egress sidecar overrides this with --entrypoint python3, so it never runs the
# wrapper.
ENTRYPOINT ["/usr/local/bin/lfb-agy-entrypoint"]

# EGRESS, MEASURED.  The first containerized run (2026-08-31) did not reach the
# model: agy's startup eligibility check fetches the signed-in operator's
# Google profile picture from lh3.googleusercontent.com, the provider-only
# allowlist refused that host, and agy exited 1 with status ERROR before its
# first turn.  Adding that one host fixed it -- the next run exited 0 with
# status SUCCESS.  The host set below is what a run needs; it is an operator
# input (`--allow-host`, `--allow-port`), because the manifest schema carries
# no allowlist field and an allowlist guessed in code fails open rather than
# closed:
#
#   oauth2.googleapis.com              token refresh          (reached)
#   www.googleapis.com                 signed-in profile      (reached)
#   lh3.googleusercontent.com          eligibility check      (reached)
#   daily-cloudcode-pa.googleapis.com  model endpoint         (reached)
#   cloudcode-pa.googleapis.com        model endpoint sibling (not reached)
#
# Pass them as EXACT hosts, with no `--allow-subdomains googleapis.com` rule.
# That rule would also admit aicode.googleapis.com and
# generativelanguage.googleapis.com, both of which this binary carries, and
# dropping it is what turned play.googleapis.com (telemetry) from silent reach
# into a journaled refusal.  lh3.googleusercontent.com is a genuine widening --
# it is a general user-content CDN, not a provider API -- accepted here because
# it serves opaque content-addressed objects and cannot be queried: it is a way
# to fetch a known URL, not a way to look up a case outcome.
#
# Hosts agy tried and which were correctly refused with no ill effect:
# antigravity-unleash.goog (feature flags), play.googleapis.com (telemetry),
# and the three playwright.azureedge.net browser-download CDNs.
