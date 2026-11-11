#!/usr/bin/env bash
# Compile the standalone working paper; keep generated files out of the source tree.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: bash docs/papers/build.sh [--paper NAME] [--container] [--release]

Build docs/papers/NAME/*-paper.tex with latexmk and pdfLaTeX. The PDF and logs
are written to docs/papers/NAME/build/. Undefined citations/references are errors.

  --paper NAME Paper directory under docs/papers (default: legalforecastbench).
  --container  Use the pinned TeX Live image (Docker, linux/amd64). Set
               PAPER_BUILD_SSH_HOST (or write an SSH host alias to
               ${XDG_CONFIG_HOME:-~/.config}/legalforecastbench/paper-build-host)
               to offload container builds over SSH; set PAPER_BUILD_SSH_HOST=none
               to force local Docker.
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

if [[ ! "$paper" =~ ^[A-Za-z0-9._-]+$ || "$paper" == *..* ]]; then
  printf 'Invalid paper directory name: %s\n' "$paper" >&2
  exit 2
fi

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
  SOURCE_DATE_EPOCH=$(python3 - "$paper_dir/$manuscript" <<'PYEOF'
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
PYEOF
)
fi
export SOURCE_DATE_EPOCH
if [[ -z "${SOURCE_DATE_EPOCH}" ]]; then
  printf 'Could not date the PDF from the manuscript \\date line.\n' >&2
  exit 1
fi
export FORCE_SOURCE_DATE=1

resolve_remote_build_host() {
  local host="${PAPER_BUILD_SSH_HOST:-}"
  if [[ -z "${PAPER_BUILD_SSH_HOST+x}" ]]; then
    local config_root="${XDG_CONFIG_HOME:-${HOME:-}/.config}"
    local host_file="$config_root/legalforecastbench/paper-build-host"
    if [[ -n "${config_root}" && -f "$host_file" ]]; then
      IFS= read -r host < "$host_file" || true
      host="${host#"${host%%[![:space:]]*}"}"
      host="${host%"${host##*[![:space:]]}"}"
    fi
  fi
  if [[ "$host" == "none" ]]; then
    host=""
  fi
  printf '%s\n' "$host"
}

build_remote_container() {
  local remote_host=$1
  if ! command -v ssh >/dev/null 2>&1; then
    printf 'ssh is required to build on %s.\n' "$remote_host" >&2
    return 69
  fi

  local input_tar output_tar rc=0
  local -a tar_flags=()
  input_tar=$(mktemp)
  output_tar=$(mktemp)

  if tar --version 2>/dev/null | grep -qi bsdtar; then
    tar_flags+=(--no-xattrs --no-mac-metadata)
  fi
  COPYFILE_DISABLE=1 tar "${tar_flags[@]+${tar_flags[@]}}" -cf "$input_tar" -C "$repo_root" \
    --exclude="docs/papers/$paper/build" \
    --exclude="docs/papers/$paper/.texpadtmp" \
    --exclude="docs/papers/$paper/temp" \
    --exclude=".DS_Store" \
    docs/papers/build.sh \
    docs/papers/texlive-image.txt \
    "docs/papers/$paper"

  local remote_script remote_b64
  remote_script=$(cat <<'REMOTE_EOF'
set -euo pipefail
exec 3>&1 1>&2

remote_paper=$1
remote_epoch=$2
remote_release=$3

if [[ -z "${DOCKER_HOST:-}" && -S "/run/user/$(id -u)/docker.sock" ]]; then
  export DOCKER_HOST="unix:///run/user/$(id -u)/docker.sock"
fi

if ! command -v docker >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
  printf 'Docker is not available on remote container build host.\n' >&2
  exit 69
fi

cache_root="${XDG_CACHE_HOME:-$HOME/.cache}/lfb-paper-build"
mkdir -p "$cache_root"
workdir=$(mktemp -d "$cache_root/run.XXXXXX")
trap 'rm -rf "$workdir"' EXIT

tar -xf - -C "$workdir"
remote_args=(--paper "$remote_paper" --container)
if [[ "$remote_release" == true ]]; then
  remote_args+=(--release)
fi
if ! PAPER_BUILD_SSH_HOST=none SOURCE_DATE_EPOCH="$remote_epoch" \
  bash "$workdir/docs/papers/build.sh" "${remote_args[@]}" >"$workdir/compile.out"; then
  cat "$workdir/compile.out" >&2
  exit 1
fi

tar -cf - -C "$workdir/docs/papers/$remote_paper/build" . >&3
REMOTE_EOF
)
  remote_b64=$(printf '%s\n' "$remote_script" | base64 | tr -d '\r\n')

  ssh -o BatchMode=yes -o ConnectTimeout="${PAPER_SSH_CONNECT_TIMEOUT:-5}" \
    "$remote_host" \
    "bash -c \"\$(printf '%s' '$remote_b64' | base64 -d)\" _ '$paper' '$SOURCE_DATE_EPOCH' '$release'" \
    < "$input_tar" > "$output_tar" || rc=$?

  rm -f "$input_tar"
  if (( rc == 255 || rc == 69 )); then
    rm -f "$output_tar"
    printf 'Could not reach container build host %s over SSH (or Docker is unavailable there).\n' \
      "$remote_host" >&2
    return 69
  fi
  if (( rc != 0 )); then
    rm -f "$output_tar"
    return "$rc"
  fi

  mkdir -p "$output_dir"
  tar -xf "$output_tar" -C "$output_dir"
  rm -f "$output_tar"
  printf '\nBuilt %s/%s (via %s)\n' "$output_dir" "${manuscript%.tex}.pdf" "$remote_host"
}

# The pinned image is about 1.8GB. A 120s cap kills a healthy slow pull on
# CI, and ghcr can also leave a layer in "Waiting". Stop a stalled pull and
# try again before compiling.
pull_pinned_texlive_image() {
  local image=$1
  local attempt=1
  local attempts=${PAPER_IMAGE_PULL_ATTEMPTS:-3}
  local pull_timeout=${PAPER_IMAGE_PULL_TIMEOUT_SECONDS:-300}
  local backoff=${PAPER_IMAGE_PULL_BACKOFF_SECONDS:-10}
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
  remote_host=$(resolve_remote_build_host)
  if [[ -n "$remote_host" ]]; then
    build_remote_container "$remote_host"
    exit 0
  fi

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
