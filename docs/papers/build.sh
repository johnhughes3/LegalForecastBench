#!/usr/bin/env bash
# Compile the standalone working paper; keep generated files out of the source tree.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: bash docs/papers/build.sh [--paper NAME] [--container] [--release]

Build docs/papers/NAME/*-paper.tex with latexmk and pdfLaTeX. The PDF and logs
are written to docs/papers/NAME/build/. Undefined citations/references are errors.

  --paper NAME Paper directory under docs/papers (default: legalforecastbench).
  --container  Use the pinned TeX Live image (Docker, linux/amd64).
  --release    Refuse unresolved draft, citation, number, or TODO annotations.
  --help       Show this help.

Without --container, latexmk and a TeX Live installation must be on PATH.
The native document editor can also compile the standalone .tex directly.
EOF
}

container=false
release=false
paper=legalforecastbench
while (( $# )); do
  case "$1" in
    --paper) paper=${2:?--paper needs a name}; shift ;;
    --container) container=true ;;
    --release) release=true ;;
    --help|-h) usage; exit 0 ;;
    *) printf 'Unknown argument: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

tools_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "$tools_dir/../.." && pwd)
paper_dir="$tools_dir/$paper"
manuscripts=("$paper_dir"/*-paper.tex)
if [[ ! -f "${manuscripts[0]}" || ${#manuscripts[@]} -ne 1 ]]; then
  printf 'Expected exactly one *-paper.tex in %s\n' "$paper_dir" >&2
  exit 2
fi
manuscript=$(basename "${manuscripts[0]}")
output_dir="$paper_dir/build"
mkdir -p "$output_dir"

if "$release" && grep -nE -e '^[[:space:]]*%[[:space:]]*TODO([[:space:]:]|$)' -e '\\(draft|checkcite|checknum|todo)(\[[^]]*\])?\{' \
  "$paper_dir/$manuscript"; then
  printf 'Resolve the draft annotations above before publishing a paper version.\n' >&2
  exit 1
fi

# Date the PDF from the manuscript's \date line, not from a git commit. A squash
# merge creates a new commit, and dating from that commit would change the PDF
# bytes after the pull request had already compiled them. Uncommitted drafts are
# previews of the working tree.
if [[ -z "${SOURCE_DATE_EPOCH:-}" ]]; then
  SOURCE_DATE_EPOCH=$(python3 - "$paper_dir/$manuscript" <<'PY'
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

text = Path(sys.argv[1]).read_text(encoding="utf-8")
dated = re.search(r"\\date\{([^}]*)\}", text)
if dated is None:
    raise SystemExit("The manuscript needs a \\date{Month D, YYYY} line.")
found = re.search(
    r"(January|February|March|April|May|June|July|August|September|"
    r"October|November|December)\s+(\d{1,2}),\s+(\d{4})",
    dated.group(1),
)
if found is None:
    raise SystemExit(
        "Could not read a month, day, and year from the manuscript date: "
        + dated.group(1)
    )
when = datetime.strptime(
    f"{found.group(1)} {int(found.group(2))} {found.group(3)}",
    "%B %d %Y",
).replace(tzinfo=timezone.utc)
print(int(when.timestamp()))
PY
)
fi
export SOURCE_DATE_EPOCH
if [[ -z "${SOURCE_DATE_EPOCH}" ]]; then
  printf 'Could not date the PDF from the manuscript \\date line.\n' >&2
  exit 1
fi
export FORCE_SOURCE_DATE=1

# ghcr sometimes leaves one texlive-full layer in "Waiting" until the job
# clock expires. Stop a stalled pull and try again before compiling.
pull_pinned_texlive_image() {
  local image=$1
  local attempt=1
  local attempts=${PAPER_IMAGE_PULL_ATTEMPTS:-2}
  local pull_timeout=${PAPER_IMAGE_PULL_TIMEOUT_SECONDS:-120}
  local backoff=${PAPER_IMAGE_PULL_BACKOFF_SECONDS:-5}
  if ! command -v timeout >/dev/null 2>&1; then
    printf 'timeout is required to pull the pinned TeX Live image.\n' >&2
    return 1
  fi
  while (( attempt <= attempts )); do
    if timeout --foreground "$pull_timeout" \
      docker pull --platform linux/amd64 "$image"; then
      return 0
    fi
    if (( attempt == attempts )); then
      printf 'Could not pull the pinned TeX Live image after %s attempts.\n' \
        "$attempts" >&2
      return 1
    fi
    printf 'Pinned TeX Live image pull attempt %s did not finish; retrying.\n' \
      "$attempt" >&2
    if (( backoff > 0 )); then
      sleep "$backoff"
    fi
    attempt=$((attempt + 1))
  done
}

if "$container"; then
  image=$(cat "$tools_dir/texlive-image.txt")
  pull_pinned_texlive_image "$image"
  options=(--paper "$paper")
  if "$release"; then options+=(--release); fi
  # Rootless Docker maps container root to the invoking user, so the host
  # user's own uid would land on an unwritable subordinate uid instead.
  user="$(id -u):$(id -g)"
  if docker info --format '{{.SecurityOptions}}' 2>/dev/null | grep -q rootless; then
    user=0:0
  fi
  exec docker run --rm --platform linux/amd64 --network none \
    --user "$user" \
    --env SOURCE_DATE_EPOCH --env FORCE_SOURCE_DATE --env HOME=/tmp \
    --volume "$repo_root:/paper:ro" \
    --volume "$output_dir:/paper/docs/papers/$paper/build" \
    --workdir /paper "$image" bash docs/papers/build.sh "${options[@]}"
fi

cd "$paper_dir"
latexmk -norc -pdf -Werror -interaction=nonstopmode -halt-on-error \
  -file-line-error -no-shell-escape -outdir="$output_dir" \
  "$manuscript"
printf '\nBuilt %s/%s\n' "$output_dir" "${manuscript%.tex}.pdf"
