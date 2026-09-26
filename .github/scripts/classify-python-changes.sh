#!/usr/bin/env bash
# Keep the required Python job successful while omitting work for site-only edits.
set -euo pipefail
run_python=true
if [[ "${EVENT_NAME}" != workflow_dispatch && -n "${BASE_SHA}" ]] && \
  git cat-file -e "${BASE_SHA}^{commit}" 2>/dev/null; then
  changes=$(mktemp)
  trap 'rm -f "$changes"' EXIT
  # Treat renames as removal + addition so moving Python into site cannot skip CI.
  git diff --no-renames --name-only -z "${BASE_SHA}" "${HEAD_SHA}" > "$changes"
  run_python=false
  while IFS= read -r -d '' path; do
    case "$path" in
      site/*) ;;
      *) run_python=true; break ;;
    esac
  done < "$changes"
fi
printf 'run_python=%s\n' "$run_python" >> "$GITHUB_OUTPUT"
