#!/usr/bin/env bash
# Refuse a manifest-run stage record that names any object outside its own prefix.
#
# Manifest-run objects are written create-once and no role holds a delete grant,
# so a single object placed under the wrong prefix is unrecoverable. This runs
# twice: once on the dry-run plan, before anything is written, which is the
# load-bearing use; and once on the record of what was actually written, because
# those are separate invocations and only the second describes the real writes.
#
# One script rather than two inline copies: a fence that drifts between its
# pre-write and post-write forms is worse than no fence, because the pre-write
# pass would license writes the post-write pass would then accept.
set -euo pipefail

record="${1:?usage: assert-manifest-run-lane.sh <record.json> <prefix> <results-bucket> <packet-bucket>}"
expected_prefix="${2:?expected prefix is required}"
results_bucket="${3:?results bucket is required}"
packet_bucket="${4:?packet bucket is required}"

if ! jq -e \
  --arg prefix "${expected_prefix}" \
  --arg results "${results_bucket}" \
  --arg packets "${packet_bucket}" '
    (.objects | length) > 0 and
    (.prefix == $prefix) and
    all(.objects[];
      (.bucket == $results and (.key | startswith($prefix + "/"))) or
      (.bucket == $packets and (.key | startswith("model-packets/")))
    )
  ' "${record}" >/dev/null; then
  echo "Stage record ${record} names an object outside ${expected_prefix}; refusing." >&2
  exit 1
fi

# Belt and braces on the segment that keeps the two lanes apart: a supplementary
# prefix always contains it, and an object that lost it would land in the shared
# official prefix that already backs dispatched shards.
if ! jq -e \
  'all(.objects[];
     (.key | startswith("model-packets/")) or (.key | contains("/supplementary/")))
  ' "${record}" >/dev/null; then
  echo "Stage record ${record} names a results-bucket key outside the supplementary segment; refusing." >&2
  exit 1
fi
