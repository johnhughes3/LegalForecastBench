#!/usr/bin/env bash
# Rebuild each paper in the pinned TeX Live container and compare it with the
# committed PDF, so a push does not wait for CI to report a stale PDF.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: bash docs/papers/check-pdfs.sh [--all]

For each paper directory under docs/papers/ that has a *-paper.tex, build it
with `build.sh --paper NAME --container` and require the result to be
byte-identical to the committed PDF listed below. The Paper workflow runs the
same comparison in CI.

As a pre-push hook (see .pre-commit-config.yaml), only papers whose files
changed between PRE_COMMIT_FROM_REF and PRE_COMMIT_TO_REF are built; a change
to the shared tooling in docs/papers/ builds every paper. Without those
variables, or with --all, every paper is built.

The build reads the working tree, so commit or stash unrelated edits first.
Without Docker the check prints a warning and passes; CI still enforces it.

  --all      Build every paper regardless of what changed.
  --help     Show this help.
EOF
}

# Paper directory name -> the committed PDF it must match. Paper 1 is served
# by the website; the LAB audit PDF is not published there yet. (A case
# statement rather than an associative array keeps macOS's bash 3.2 working.)
committed_pdf() {
  case "$1" in
    legalforecastbench) echo site/public/paper/legalforecastbench-working.pdf ;;
    lab-audit) echo docs/papers/lab-audit/LAB-audit-paper.pdf ;;
  esac
}

all=false
while (( $# )); do
  case "$1" in
    --all) all=true ;;
    --help|-h) usage; exit 0 ;;
    *) printf 'Unknown argument: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

tools_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "$tools_dir/../.." && pwd)
cd "$repo_root"

if ! command -v docker >/dev/null 2>&1; then
  printf 'warning: docker is not available; skipping the paper PDF check (CI still runs it).\n' >&2
  exit 0
fi

changed=""
if ! "$all" && [[ -n "${PRE_COMMIT_FROM_REF:-}" && -n "${PRE_COMMIT_TO_REF:-}" ]]; then
  # A ref git cannot compare (a new branch's all-zero base) builds everything.
  changed=$(git diff --name-only "$PRE_COMMIT_FROM_REF" "$PRE_COMMIT_TO_REF" 2>/dev/null) \
    || all=true
else
  all=true
fi

# True when a paper must be built for this push.
needs_build() {
  local name=$1 pdf=$2 path
  "$all" && return 0
  while IFS= read -r path; do
    case "$path" in
      "docs/papers/$name/"*|"$pdf") return 0 ;;
      # Shared tooling (build.sh, the TeX image) affects every paper.
      docs/papers/*/*) ;;
      docs/papers/*) return 0 ;;
    esac
  done <<< "$changed"
  return 1
}

status=0
for manuscript in docs/papers/*/*-paper.tex; do
  [[ -f "$manuscript" ]] || continue
  dir=$(dirname "$manuscript")
  name=$(basename "$dir")
  pdf=$(committed_pdf "$name")
  if [[ -z "$pdf" ]]; then
    printf 'No committed PDF is listed for docs/papers/%s; add it to committed_pdf in %s.\n' \
      "$name" "docs/papers/check-pdfs.sh" >&2
    status=1
    continue
  fi
  needs_build "$name" "$pdf" || continue
  printf 'Building %s ...\n' "$name" >&2
  if ! bash docs/papers/build.sh --paper "$name" --container >/dev/null; then
    printf 'The %s paper did not build; run bash docs/papers/build.sh --paper %s --container.\n' \
      "$name" "$name" >&2
    status=1
    continue
  fi
  built="$dir/build/$(basename "${manuscript%.tex}").pdf"
  if ! cmp -s "$built" "$pdf"; then
    printf 'The %s PDF is stale. Commit the fresh build:\n  cp -f %s %s\n' \
      "$name" "$built" "$pdf" >&2
    status=1
  fi
done
exit "$status"
