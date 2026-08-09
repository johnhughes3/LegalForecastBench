#!/usr/bin/env bash
set -u

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root" || exit 1

failed=0
run_check() {
  label="$1"
  shift
  echo "CHECK $label"
  if "$@"; then
    echo "RESULT PASS $label"
  else
    echo "RESULT FAIL $label"
    failed=1
  fi
}

run_check focused-tests uv run pytest tests/test_cycle_preflight.py -q
run_check capsule-rehearsal uv run pytest tests/test_successor_ledger_rehearsal.py -q
run_check public-capsule-preflight uv run python -m legalforecast.ingestion.cycle_preflight \
  --manifest tests/fixtures/cycle-preflight/manifest.json --format text

if [[ -n "${LEGALFORECAST_CYCLE_PREFLIGHT_MANIFEST:-}" ]]; then
  run_check real-lineage-preflight uv run python -m legalforecast.ingestion.cycle_preflight \
    --manifest "$LEGALFORECAST_CYCLE_PREFLIGHT_MANIFEST" --format text
else
  echo "RESULT NOT_EVALUATED real-lineage-preflight reason=manifest-not-configured"
fi

if [[ "$failed" -eq 0 ]]; then
  echo "DEV_CHECK_VERDICT PASS"
else
  echo "DEV_CHECK_VERDICT FAIL"
fi
exit "$failed"
