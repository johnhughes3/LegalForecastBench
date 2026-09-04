#!/usr/bin/env bash
set -euo pipefail

if [[ "$#" -ne 3 ]]; then
  echo "usage: reconcile-s3-object.sh <bucket> <source> <key>" >&2
  exit 2
fi

bucket="$1"
source="$2"
key="$3"
[[ -f "$source" && ! -L "$source" ]] || {
  echo "refusing non-regular S3 source: ${source}" >&2
  exit 1
}

expected_sha256="$(sha256sum "$source" | awk '{print $1}')"
expected_size="$(stat -c '%s' "$source")"
expected_metadata="$(jq -cn --arg digest "$expected_sha256" '{sha256: $digest}')"
state_dir="$(mktemp -d)"
trap 'rm -rf "$state_dir"' EXIT

reconcile_existing() {
  local head_json="$state_dir/head.json"
  local head_error="$state_dir/head.error"
  if ! aws s3api head-object \
    --bucket "$bucket" \
    --key "$key" \
    --output json >"$head_json" 2>"$head_error"; then
    if grep -Eq '(^|[^0-9])404([^0-9]|$)|Not Found|NoSuchKey' "$head_error"; then
      return 1
    fi
    cat "$head_error" >&2
    echo "refusing S3 reconciliation after head-object failure: ${key}" >&2
    exit 1
  fi
  local actual_size actual_metadata
  actual_size="$(jq -r '.ContentLength // empty' "$head_json")"
  actual_metadata="$(jq -cS '.Metadata // {}' "$head_json")"
  if [[ "$actual_size" == "$expected_size" && "$actual_metadata" == "$expected_metadata" ]]; then
    echo "reused existing immutable S3 object: ${key}"
    return 0
  fi
  echo "refusing S3 object mismatch for immutable key: ${key}" >&2
  echo "expected size=${expected_size} metadata=${expected_metadata}; got size=${actual_size} metadata=${actual_metadata}" >&2
  exit 1
}

if reconcile_existing; then
  exit 0
fi

put_error="$state_dir/put.error"
if aws s3api put-object \
  --bucket "$bucket" \
  --key "$key" \
  --body "$source" \
  --metadata "sha256=${expected_sha256}" \
  --if-none-match '*' >"$state_dir/put.json" 2>"$put_error"; then
  echo "created immutable S3 object: ${key}"
  exit 0
fi

# A concurrent writer or a network failure may have happened after the first
# HEAD. Reconcile once more; only an exact object can turn the failed PUT into
# a successful idempotent retry. Any other error or byte/metadata drift fails
# closed.
if reconcile_existing; then
  exit 0
fi
cat "$put_error" >&2
echo "refusing S3 publication after put-object failure: ${key}" >&2
exit 1
