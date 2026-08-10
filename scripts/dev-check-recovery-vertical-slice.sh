#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

exec uv run --project "$repo_root" python \
  "$repo_root/scripts/dev_check_recovery_vertical_slice.py" "$@"
