#!/usr/bin/env bash
# Provider-free integration: build original shape, withdraw one fictional case,
# then check rendered pages and every downloadable file against backend output.
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$root"
fixture="$(mktemp -d)"
persistent="$root/site/refreshed-data"
restore_selection() {
  rm -rf "$persistent"
  if [[ -e "$fixture/previous-selection" ]]; then
    mv -f "$fixture/previous-selection" "$persistent"
  fi
  rm -rf "$fixture"
}
if [[ -e "$persistent" ]]; then
  mv -f "$persistent" "$fixture/previous-selection"
fi
trap restore_selection EXIT
LFB_SITE_DATA_DIR= pnpm site:build
uv run python site/scripts/generate-withdrawal-fixture.py "$fixture/source"
uv run legalforecast site refresh --input-dir "$fixture/source" --output-dir "$fixture/refreshed" --withdrawn-case synthetic-case-b --replicates 100
LFB_SITE_DATA_DIR="$fixture/refreshed" pnpm site:build
uv run python scripts/reproduce_summary_comparisons.py "$fixture/refreshed/summary-comparison" "$fixture/reproduced" --expected-case-count 1 --expected-scored-unit-count 2 --expected-forecast-unit-count 2
uv run python site/scripts/verify-withdrawal-build.py "$fixture/refreshed" "$fixture/reproduced"

# The normal Vercel command picks up a committed generated tree without env changes.
cp -rf "$fixture/refreshed" "$persistent"
env -u LFB_SITE_DATA_DIR pnpm site:build
uv run python site/scripts/verify-withdrawal-build.py "$fixture/refreshed" "$fixture/reproduced"
rm -rf "$persistent"
# Exercise the exact producer used by the protected publisher, without publishing.
WITHDRAWN_CASE_IDS=synthetic-case-b LFB_SITE_DATA_DIR="$fixture/source" bash site/scripts/build-selected-data.sh
uv run python site/scripts/verify-withdrawal-build.py "$fixture/refreshed" "$fixture/reproduced" --producer
