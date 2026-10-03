#!/usr/bin/env bash
# Build the selected source; optionally refresh its saved predictions offline.
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$root"
case_ids=()
if [[ -n "${WITHDRAWN_CASE_IDS:-}" ]]; then
  read -r -a case_ids <<< "${WITHDRAWN_CASE_IDS//$'\n'/ }"
  for case_id in "${case_ids[@]}"; do
    [[ "$case_id" =~ ^[A-Za-z0-9][A-Za-z0-9_-]*$ ]] || {
      echo 'Withdrawal case IDs must contain only letters, digits, underscores or hyphens' >&2
      exit 1
    }
  done
  (( ${#case_ids[@]} > 0 )) || { echo 'No withdrawal case IDs supplied' >&2; exit 1; }
fi
pnpm site:build
if (( ${#case_ids[@]} > 0 )); then
  fixture="$(mktemp -d)"
  trap 'rm -rf "$fixture"' EXIT
  arguments=()
  for case_id in "${case_ids[@]}"; do
    arguments+=(--withdrawn-case "$case_id")
  done
  uv run legalforecast site refresh --input-dir site/dist/data --output-dir "$fixture/refreshed" "${arguments[@]}"
  LFB_SITE_DATA_DIR="$fixture/refreshed" pnpm site:build
fi
