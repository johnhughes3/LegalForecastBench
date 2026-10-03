#!/usr/bin/env bash
# Provider-free integration: build original shape, withdraw one fictional case,
# then check rendered pages and every downloadable file against backend output.
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$root"
fixture="$(mktemp -d)"
trap 'rm -rf "$fixture"' EXIT
pnpm site:build
uv run python site/scripts/generate-withdrawal-fixture.py "$fixture/source"
uv run legalforecast site refresh --input-dir "$fixture/source" --output-dir "$fixture/refreshed" --withdrawn-case synthetic-case-b --replicates 100
LFB_SITE_DATA_DIR="$fixture/refreshed" pnpm site:build
uv run python scripts/reproduce_summary_comparisons.py "$fixture/refreshed/summary-comparison" "$fixture/reproduced" --expected-case-count 1 --expected-scored-unit-count 2 --expected-forecast-unit-count 2
uv run python site/scripts/verify-withdrawal-build.py "$fixture/refreshed" "$fixture/reproduced"
