"""Backend and image preflight for containerized harness runs.

Everything here is a thin, reusing layer over
:mod:`legalforecast.multiharness.host_environment` and
:mod:`legalforecast.multiharness.sandbox`.  The one thing it adds is reading
back the image ID that actually ran, which the run record needs and which no
existing helper returns.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Final

from legalforecast.multiharness.host_environment import (
    HostEnvironmentError,
    build_container_backend_environment,
    require_local_pinned_container_image,
    require_rootless_container_daemon,
)
from legalforecast.multiharness.sandbox import (
    SUPPORTED_CONTAINER_BACKENDS,
    validate_container_backend_path,
)

DIGEST_PINNED_IMAGE: Final[re.Pattern[str]] = re.compile(
    r"(?:[^@\s]+@)?sha256:[0-9a-f]{64}\Z"
)
_IMAGE_ID = re.compile(r"sha256:[0-9a-f]{64}\Z")


class ContainerImageError(RuntimeError):
    """Raised when the backend or a pinned image is not usable for a run."""


def require_digest_pinned_image(image: str, field_name: str) -> str:
    """Fail unless the image reference is pinned by sha256 digest or image ID.

    A tag is not an identity: ``harness:latest`` can be rebuilt under the same
    name between two rows of the same sweep, which would make the harness-vs-API
    delta a comparison of two different programs.
    """

    if DIGEST_PINNED_IMAGE.fullmatch(image) is None:
        raise ContainerImageError(
            f"{field_name} must be digest-pinned (name@sha256:... or sha256:...), "
            f"got {image!r}"
        )
    return image


def resolve_rootless_backend(backend: str) -> tuple[Path, dict[str, str]]:
    """Resolve a local rootless Docker/Podman backend and its value-free env.

    The socket is discovered from ``DOCKER_HOST``/``XDG_RUNTIME_DIR`` by
    :func:`build_container_backend_environment`, which also refuses a socket
    that is not an operator-owned Unix socket beneath the runtime directory.
    No path or uid is hardcoded here.
    """

    if backend not in SUPPORTED_CONTAINER_BACKENDS:
        formatted = ", ".join(sorted(SUPPORTED_CONTAINER_BACKENDS))
        raise ContainerImageError(f"backend must be one of: {formatted}")
    resolved = shutil.which(backend)
    if resolved is None:
        raise ContainerImageError(f"container backend is not available: {backend}")
    try:
        backend_path = validate_container_backend_path(Path(resolved))
        environment = build_container_backend_environment()
        require_rootless_container_daemon(backend_path, backend, environment)
    except (HostEnvironmentError, ValueError) as exc:
        raise ContainerImageError(str(exc)) from exc
    return backend_path, environment


def resolve_local_image_id(
    backend_path: Path,
    image: str,
    environment: Mapping[str, str],
) -> str:
    """Return the local image ID for a pinned reference that already exists.

    The pinned reference is validated first, then the ID is read back so the run
    record names the bytes that actually ran rather than the string we asked for.
    """

    try:
        require_local_pinned_container_image(backend_path, image, environment)
    except HostEnvironmentError as exc:
        raise ContainerImageError(
            f"pinned image is not present locally (pull it first): {image}"
        ) from exc
    completed = _backend_output(
        (str(backend_path), "image", "inspect", "--format", "{{.Id}}", image),
        environment,
    )
    if _IMAGE_ID.fullmatch(completed) is None:
        raise ContainerImageError(f"image inspect returned an invalid ID for {image}")
    return completed


def _backend_output(argv: tuple[str, ...], environment: Mapping[str, str]) -> str:
    try:
        completed = subprocess.run(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=30,
            check=False,
            env=dict(environment),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ContainerImageError(
            f"container backend command failed: {argv[1:]}"
        ) from exc
    if completed.returncode != 0 or len(completed.stdout) > 4096:
        raise ContainerImageError(f"container backend command failed: {argv[1:]}")
    try:
        return completed.stdout.decode("ascii").strip()
    except UnicodeDecodeError as exc:
        raise ContainerImageError(
            "container backend returned non-ASCII output"
        ) from exc
