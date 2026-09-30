#!/usr/bin/env bash
# Copy the compiled manuscript onto the path the website serves.
# A local run only copies. GitHub Actions must not push the result: main rejects
# a commit that does not already have the Python quality gates check.
set -euo pipefail

paper_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "$paper_dir/../.." && pwd)
rel=site/public/papers/legalforecastbench-working.pdf
built="$paper_dir/build/LegalForecastBench-paper.pdf"
dest="$repo_root/$rel"

if [[ ! -f "$built" ]]; then
  printf 'Missing compiled PDF: %s\nRun bash docs/paper/build.sh first.\n' "$built" >&2
  exit 1
fi

mkdir -p "$(dirname "$dest")"
if [[ -f "$dest" ]] && cmp -s "$built" "$dest"; then
  printf 'UNCHANGED\n'
  exit 0
fi

cp -f "$built" "$dest"
if [[ "${CI:-}" != "true" ]]; then
  printf 'Copied %s\nCommit it with the manuscript change.\n' "$rel" >&2
  exit 0
fi

git -C "$repo_root" add -- "$rel"
if git -C "$repo_root" diff --cached --quiet -- "$rel"; then
  printf 'UNCHANGED\n'
  exit 0
fi

git -C "$repo_root" \
  -c user.name='github-actions[bot]' \
  -c user.email='41898282+github-actions[bot]@users.noreply.github.com' \
  -c commit.gpgsign=false \
  commit -q -m "chore(paper): update the working paper PDF from the manuscript" -- "$rel"
printf 'UPDATED\n'
