#!/usr/bin/env bash

set -euo pipefail

readonly docker_repository_key="https://download.docker.com/linux/ubuntu/gpg"
readonly docker_repository="https://download.docker.com/linux/ubuntu"
readonly startup_timeout_seconds=45

fail() {
  printf 'rootless Docker setup failed: %s\n' "$*" >&2
  exit 1
}

is_rootless_docker() {
  docker info --format '{{json .SecurityOptions}}' 2>/dev/null | grep -q 'rootless'
}

persist_backend_environment() {
  local runtime_directory="$1"
  local docker_host="$2"

  {
    printf 'XDG_RUNTIME_DIR=%s\n' "${runtime_directory}"
    printf 'DOCKER_HOST=%s\n' "${docker_host}"
    printf 'LFB_CONTAINER_BACKEND=docker\n'
  } >>"${GITHUB_ENV}"
}

has_subordinate_ids() {
  local database="$1"
  local username uid
  username="$(id -un)"
  uid="$(id -u)"
  awk -F: -v username="${username}" -v uid="${uid}" \
    '($1 == username || $1 == uid) && $3 >= 65536 { found = 1 } END { exit !found }' \
    "${database}"
}

install_rootless_dependencies() {
  if command -v dockerd-rootless.sh >/dev/null \
    && command -v rootlesskit >/dev/null \
    && command -v slirp4netns >/dev/null \
    && command -v newuidmap >/dev/null \
    && command -v newgidmap >/dev/null; then
    return
  fi

  command -v sudo >/dev/null || fail "sudo is required to install rootless Docker dependencies"
  command -v dpkg >/dev/null || fail "dpkg is required to identify the runner architecture"
  command -v dpkg-query >/dev/null || fail "docker-ce must be installed from a Debian package"

  local apt_root architecture codename docker_version
  apt_root="${RUNNER_TEMP}/lfb-rootless-docker-apt"
  mkdir -p "${apt_root}"
  if ! grep -RqsF "${docker_repository}" \
    /etc/apt/sources.list /etc/apt/sources.list.d 2>/dev/null; then
    command -v curl >/dev/null \
      || fail "curl is required to configure the Docker package repository"
    command -v gpg >/dev/null \
      || fail "gpg is required to configure the Docker package repository"
    curl -fsSL "${docker_repository_key}" -o "${apt_root}/docker.asc"
    gpg --batch --yes --dearmor --output "${apt_root}/docker.gpg" \
      "${apt_root}/docker.asc"
    sudo install -d -m 0755 /etc/apt/keyrings
    sudo install -m 0644 "${apt_root}/docker.gpg" \
      /etc/apt/keyrings/lfb-docker-rootless.gpg

    architecture="$(dpkg --print-architecture)"
    # VERSION_CODENAME is the Ubuntu runner contract.
    # shellcheck disable=SC1091
    source /etc/os-release
    codename="${VERSION_CODENAME:-}"
    [[ -n "${codename}" ]] || fail "Ubuntu release codename is unavailable"
    printf 'deb [arch=%s signed-by=/etc/apt/keyrings/lfb-docker-rootless.gpg] %s %s stable\n' \
      "${architecture}" "${docker_repository}" "${codename}" \
      | sudo tee /etc/apt/sources.list.d/lfb-docker-rootless.list >/dev/null
  fi

  docker_version="$(dpkg-query -W -f='${Version}' docker-ce 2>/dev/null)"
  [[ -n "${docker_version}" ]] || fail "docker-ce package version is unavailable"
  sudo apt-get update -qq
  sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    "docker-ce-rootless-extras=${docker_version}" uidmap slirp4netns

  command -v dockerd-rootless.sh >/dev/null || fail "dockerd-rootless.sh was not installed"
  command -v rootlesskit >/dev/null || fail "rootlesskit was not installed"
  command -v slirp4netns >/dev/null || fail "slirp4netns was not installed"
  command -v newuidmap >/dev/null || fail "newuidmap was not installed"
  command -v newgidmap >/dev/null || fail "newgidmap was not installed"
}

main() {
  [[ "$(id -u)" != "0" ]] || fail "the daemon must run as the unprivileged workflow user"
  [[ -n "${RUNNER_TEMP:-}" && "${RUNNER_TEMP}" = /* ]] \
    || fail "RUNNER_TEMP must be an absolute runner-owned directory"
  [[ -n "${GITHUB_ENV:-}" ]] || fail "GITHUB_ENV is required"

  if [[ -n "${DOCKER_HOST:-}" && -n "${XDG_RUNTIME_DIR:-}" ]] \
    && is_rootless_docker; then
    persist_backend_environment "${XDG_RUNTIME_DIR}" "${DOCKER_HOST}"
    return
  fi

  install_rootless_dependencies
  has_subordinate_ids /etc/subuid \
    || fail "the workflow user needs at least 65536 subordinate UIDs"
  has_subordinate_ids /etc/subgid \
    || fail "the workflow user needs at least 65536 subordinate GIDs"

  local state_root runtime_directory docker_host daemon_log daemon_pid deadline
  # Containerd's Unix socket limit is 104 bytes, so keep this runner-owned
  # suffix short even when RUNNER_TEMP itself is nested.
  state_root="${RUNNER_TEMP}/lfb-dkr"
  runtime_directory="${state_root}/run"
  docker_host="unix://${runtime_directory}/docker.sock"
  daemon_log="${state_root}/daemon.log"
  [[ ! -L "${state_root}" ]] || fail "rootless Docker state must not be a symlink"
  mkdir -p "${runtime_directory}" "${state_root}/data" "${state_root}/exec"
  chmod 0700 "${state_root}" "${runtime_directory}" "${state_root}/data" \
    "${state_root}/exec"
  rm -f "${runtime_directory}/docker.sock" "${state_root}/docker.pid"

  export XDG_RUNTIME_DIR="${runtime_directory}"
  export DOCKER_HOST="${docker_host}"
  env -i \
    HOME="${HOME}" \
    PATH="${PATH}" \
    XDG_RUNTIME_DIR="${runtime_directory}" \
    DOCKERD_ROOTLESS_ROOTLESSKIT_NET=slirp4netns \
    dockerd-rootless.sh \
    --host="${docker_host}" \
    --exec-opt native.cgroupdriver=cgroupfs \
    --data-root="${state_root}/data" \
    --exec-root="${state_root}/exec" \
    --pidfile="${state_root}/docker.pid" \
    >"${daemon_log}" 2>&1 &
  daemon_pid="$!"
  printf '%s\n' "${daemon_pid}" >"${state_root}/daemon-launcher.pid"

  deadline=$((SECONDS + startup_timeout_seconds))
  until is_rootless_docker; do
    if ! kill -0 "${daemon_pid}" 2>/dev/null; then
      tail -n 80 "${daemon_log}" >&2 || true
      fail "rootless Docker daemon exited during startup"
    fi
    if ((SECONDS >= deadline)); then
      kill "${daemon_pid}" 2>/dev/null || true
      tail -n 80 "${daemon_log}" >&2 || true
      fail "rootless Docker daemon did not become ready within ${startup_timeout_seconds} seconds"
    fi
    sleep 1
  done

  persist_backend_environment "${runtime_directory}" "${docker_host}"
}

main "$@"
