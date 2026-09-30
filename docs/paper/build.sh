#!/usr/bin/env bash
# Compile the standalone working paper; keep generated files out of the source tree.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: bash docs/paper/build.sh [--container] [--release]

Build LegalForecastBench-paper.tex with latexmk and pdfLaTeX. The PDF and logs
are written to docs/paper/build/. Undefined citations/references are errors.

  --container  Use the pinned TeX Live image (Docker, linux/amd64).
  --release    Refuse unresolved draft, citation, number, or TODO annotations.
  --help       Show this help.

Without --container, latexmk and a TeX Live installation must be on PATH.
The native document editor can also compile the standalone .tex directly.
EOF
}

container=false
release=false
for argument in "$@"; do
  case "$argument" in
    --container) container=true ;;
    --release) release=true ;;
    --help|-h) usage; exit 0 ;;
    *) printf 'Unknown argument: %s\n' "$argument" >&2; usage >&2; exit 2 ;;
  esac
done

paper_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "$paper_dir/../.." && pwd)
output_dir="$paper_dir/build"
mkdir -p "$output_dir"

if "$release" && grep -nE -e '^[[:space:]]*%[[:space:]]*TODO([[:space:]:]|$)' -e '\\(draft|checkcite|checknum|todo)(\[[^]]*\])?\{' \
  "$paper_dir/LegalForecastBench-paper.tex"; then
  printf 'Resolve the draft annotations above before publishing a paper version.\n' >&2
  exit 1
fi

# Date the PDF from the last change under docs/paper. A later commit that only
# replaces the website copy must not change the metadata, or each publication
# would compile a different file. Uncommitted drafts are previews of the working tree.
export SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH:-$(git -C "$repo_root" log -1 --format=%ct -- docs/paper)}
if [[ -z "${SOURCE_DATE_EPOCH}" ]]; then
  printf 'Could not date the PDF from the docs/paper git history.\n' >&2
  exit 1
fi
export FORCE_SOURCE_DATE=1

if "$container"; then
  image=$(cat "$paper_dir/texlive-image.txt")
  options=()
  if "$release"; then options+=(--release); fi
  exec docker run --rm --platform linux/amd64 --network none \
    --user "$(id -u):$(id -g)" \
    --env SOURCE_DATE_EPOCH --env FORCE_SOURCE_DATE --env HOME=/tmp \
    --volume "$repo_root:/paper:ro" \
    --volume "$output_dir:/paper/docs/paper/build" \
    --workdir /paper "$image" bash docs/paper/build.sh "${options[@]}"
fi

cd "$paper_dir"
latexmk -norc -pdf -Werror -interaction=nonstopmode -halt-on-error \
  -file-line-error -no-shell-escape -outdir="$output_dir" \
  LegalForecastBench-paper.tex
printf '\nBuilt %s/LegalForecastBench-paper.pdf\n' "$output_dir"
