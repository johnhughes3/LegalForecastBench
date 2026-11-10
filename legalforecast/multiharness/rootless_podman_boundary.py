"""Rootless Podman outer filesystem boundary for native Codex.

The native Codex sandbox creates its own user namespace and procfs.  Applying
Landlock to the parent first blocks bubblewrap's future ``uid_map`` writes, so
the community Codex solver instead starts inside a rootless OCI mount namespace.
Codex keeps its native named filesystem policy inside that boundary.
"""

from __future__ import annotations

import os
import stat
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from legalforecast.multiharness.container_harness.images import (
    resolve_rootless_backend,
)
from legalforecast.multiharness.spec import POSIX_PROCESS_GROUP_CONTAINMENT
from legalforecast.multiharness.validation import validate_public_record

ROOTLESS_PODMAN_FILESYSTEM_SCOPE: Final = "rootless_podman_mounts.v1"
CONTRIBUTOR_ROOTLESS_PODMAN_BOUNDARY: Final = (
    "contributor_rootless_podman_whole_process.v1"
)
_TMPFS: Final = "/tmp:rw,nosuid,nodev,mode=1777"
_SYSTEM_TARGETS: Final = (Path("/usr"), Path("/bin"), Path("/lib"), Path("/lib64"))
_CA_CERTIFICATE: Final = Path("/etc/ssl/certs/ca-certificates.crt")
_CONTAINER_PATH: Final = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
_ZERO_CAPABILITIES: Final = "0000000000000000"
_ENTRYPOINT = (
    'test "$(/usr/bin/id -u)" = "$1" || exit 125; shift; '
    "seen=0; while read -r key value rest; do "
    'case "$key" in CapEff:|CapPrm:|CapBnd:) '
    f'test "$value" = "{_ZERO_CAPABILITIES}" || exit 125; '
    "seen=$((seen + 1));; esac; done < /proc/self/status; "
    'test "$seen" = 3 || exit 125; '
    'exec "$@"'
)


class RootlessPodmanBoundaryError(RuntimeError):
    """Raised when the rootless Podman boundary cannot be established safely."""


@dataclass(frozen=True, slots=True)
class _MountIdentity:
    source: Path
    target: Path
    mode: str
    device: int
    inode: int
    file_type: int


@dataclass(slots=True)
class RootlessPodmanLaunch:
    """Prepared Podman command plus exact mount identities and cleanup state."""

    argv: tuple[str, ...]
    environment: dict[str, str]
    boundary_identity: dict[str, object]
    control_root: Path
    _backend: Path
    _container_name: str
    _rootfs: Path
    _mounts: tuple[_MountIdentity, ...]
    _temporary: tempfile.TemporaryDirectory[str]
    _spawn_attempted: bool = False
    _container_absence_verified: bool = False
    _closed: bool = False

    def revalidate(self) -> None:
        """Re-open every source immediately before spawn and reject replacements."""

        for expected in self._mounts:
            observed = _validated_mount_identity(
                expected.source,
                target=expected.target,
                mode=expected.mode,
            )
            if (
                observed.device,
                observed.inode,
                observed.file_type,
            ) != (
                expected.device,
                expected.inode,
                expected.file_type,
            ):
                raise RootlessPodmanBoundaryError(
                    "Podman mount source changed before launch"
                )

    def mark_spawn_attempted(self) -> None:
        """Record that the retained container name may now identify a workload."""

        self._spawn_attempted = True
        self._container_absence_verified = False

    def require_container_revalidation(self) -> None:
        """Invalidate an absence check made while the Podman client was alive."""

        if self._spawn_attempted:
            self._container_absence_verified = False

    def terminate_container(self) -> None:
        """Stop with zero grace, remove, and verify the exact container is absent."""

        if not self._spawn_attempted or self._container_absence_verified:
            return
        cleanup_error: RootlessPodmanBoundaryError | None = None
        commands = (
            ("stop", "--time=0", "--ignore", self._container_name),
            ("rm", "--force", "--ignore", self._container_name),
        )
        for arguments in commands:
            try:
                completed = subprocess.run(
                    (str(self._backend), *arguments),
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    check=False,
                    timeout=30,
                    env=self.environment,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                cleanup_error = cleanup_error or RootlessPodmanBoundaryError(
                    "rootless Podman container cleanup failed"
                )
                cleanup_error.__cause__ = exc
            else:
                if (
                    completed.returncode != 0
                    or len(completed.stdout) > 65_536
                    or len(completed.stderr) > 65_536
                ):
                    cleanup_error = cleanup_error or RootlessPodmanBoundaryError(
                        "rootless Podman container cleanup failed"
                    )
        try:
            exists = subprocess.run(
                (
                    str(self._backend),
                    "container",
                    "exists",
                    self._container_name,
                ),
                stdin=subprocess.DEVNULL,
                capture_output=True,
                check=False,
                timeout=30,
                env=self.environment,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            cleanup_error = cleanup_error or RootlessPodmanBoundaryError(
                "rootless Podman container removal could not be verified"
            )
            cleanup_error.__cause__ = exc
        else:
            if (
                exists.returncode != 1
                or len(exists.stdout) > 65_536
                or len(exists.stderr) > 65_536
            ):
                cleanup_error = cleanup_error or RootlessPodmanBoundaryError(
                    "rootless Podman container removal could not be verified"
                )
        if cleanup_error is not None:
            raise cleanup_error
        self._container_absence_verified = True

    def close(self) -> None:
        """Remove any surviving container, then delete the private transient rootfs."""

        if self._closed:
            return
        self._closed = True
        cleanup_error: RootlessPodmanBoundaryError | None = None
        try:
            try:
                self.terminate_container()
            except RootlessPodmanBoundaryError as exc:
                cleanup_error = exc
        finally:
            try:
                _restore_rootfs_ownership(
                    self._backend,
                    self._rootfs,
                    self.environment,
                )
            except RootlessPodmanBoundaryError as exc:
                cleanup_error = cleanup_error or exc
            else:
                self._temporary.cleanup()
        if cleanup_error is not None:
            raise cleanup_error


def require_rootless_podman_scope(value: str | None) -> str:
    """Return the exact supported Podman filesystem scope or fail closed."""

    if value != ROOTLESS_PODMAN_FILESYSTEM_SCOPE:
        raise RootlessPodmanBoundaryError(
            f"filesystem_scope must be {ROOTLESS_PODMAN_FILESYSTEM_SCOPE}"
        )
    return value


def system_read_mounts() -> tuple[tuple[Path, Path], ...]:
    """Resolve the four reviewed system roots while retaining fixed targets."""

    mounts: list[tuple[Path, Path]] = []
    for target in _SYSTEM_TARGETS:
        try:
            source = target.resolve(strict=True)
        except OSError as exc:
            raise RootlessPodmanBoundaryError(
                f"required system root is unavailable: {target}"
            ) from exc
        identity = _validated_mount_identity(source, target=target, mode="ro")
        if identity.file_type != stat.S_IFDIR:
            raise RootlessPodmanBoundaryError(
                f"required system root is not a directory: {target}"
            )
        mounts.append((source, target))
    return tuple(mounts)


def prepare_rootless_podman_boundary(
    argv: tuple[str, ...],
    *,
    execution_cwd: Path,
    executable: Path,
    read_paths: Sequence[Path],
    write_paths: Sequence[Path],
    container_environment: Mapping[str, str],
) -> RootlessPodmanLaunch:
    """Build one transient, image-free rootless Podman launch.

    Only reviewed system roots, the exact executable, declared read paths, and
    declared write roots enter the container.  Host ``/proc`` and ``/tmp`` are
    never bound: OCI supplies a distinct procfs and the command receives tmpfs.
    """

    if not argv:
        raise RootlessPodmanBoundaryError("contained command is empty")
    try:
        backend, backend_environment = resolve_rootless_backend("podman")
    except RuntimeError as exc:
        raise RootlessPodmanBoundaryError(
            "rootless Podman backend is unavailable"
        ) from exc

    cwd = _validated_mount_identity(
        execution_cwd,
        target=execution_cwd,
        mode="rw",
    )
    selected_executable = _validated_mount_identity(
        executable,
        target=executable,
        mode="ro",
    )
    if selected_executable.file_type != stat.S_IFREG:
        raise RootlessPodmanBoundaryError(
            "pinned Codex executable mount must be a regular file"
        )
    if Path(argv[0]) != selected_executable.source:
        raise RootlessPodmanBoundaryError(
            "Podman command must start with the exact pinned executable"
        )

    mounts: dict[Path, _MountIdentity] = {}
    for source, target in system_read_mounts():
        identity = _validated_mount_identity(source, target=target, mode="ro")
        mounts[target] = identity
    mounts[selected_executable.target] = selected_executable
    ca_certificate = _validated_mount_identity(
        _CA_CERTIFICATE,
        target=_CA_CERTIFICATE,
        mode="ro",
    )
    if ca_certificate.file_type != stat.S_IFREG:
        raise RootlessPodmanBoundaryError("system CA bundle must be a regular file")
    mounts[ca_certificate.target] = ca_certificate
    fixed_read_only_targets = frozenset(mounts)
    for path in read_paths:
        identity = _validated_mount_identity(path, target=path, mode="ro")
        mounts.setdefault(identity.target, identity)
    for path in (*write_paths, execution_cwd):
        identity = _validated_mount_identity(path, target=path, mode="rw")
        if identity.target in fixed_read_only_targets:
            raise RootlessPodmanBoundaryError(
                "Podman system and executable mounts must remain read-only"
            )
        existing = mounts.get(identity.target)
        if existing is not None and existing.source != identity.source:
            raise RootlessPodmanBoundaryError(
                "Podman mount target has conflicting sources"
            )
        mounts[identity.target] = identity

    auth_value = container_environment.get("CODEX_HOME")
    if auth_value is None:
        raise RootlessPodmanBoundaryError("Podman Codex launch requires CODEX_HOME")
    auth_root = Path(auth_value)
    auth_mount = mounts.get(auth_root)
    if auth_mount is None or auth_mount.mode != "rw":
        raise RootlessPodmanBoundaryError(
            "Podman Codex launch requires the exact auth root as a writable mount"
        )
    workspace_mount = mounts.get(cwd.target)
    if workspace_mount is None or workspace_mount.mode != "rw":
        raise RootlessPodmanBoundaryError(
            "Podman Codex launch requires its exact workspace as a writable mount"
        )
    for mount in mounts.values():
        if mount.target != auth_root and auth_root.is_relative_to(mount.target):
            raise RootlessPodmanBoundaryError(
                "Podman must not bind an ancestor of the Codex auth root"
            )

    temporary = tempfile.TemporaryDirectory(prefix="lfb-podman-boundary-")
    control_root = Path(temporary.name)
    control_root.chmod(0o700)
    rootfs = control_root / "rootfs"
    rootfs.mkdir(mode=0o700)
    cidfile = control_root / "container.cid"
    try:
        for mount in mounts.values():
            _prepare_mount_target(rootfs, mount)
        name = f"lfb-codex-{os.getpid()}-{os.urandom(6).hex()}"
        command: list[str] = [
            str(backend),
            "run",
            "--interactive",
            "--rm",
            "--cidfile",
            str(cidfile),
            "--name",
            name,
            "--read-only",
            "--userns=keep-id",
            "--cap-drop=ALL",
            "--rootfs",
            "--tmpfs",
            _TMPFS,
        ]
        for mount in mounts.values():
            command.extend(("--mount", _mount_argument(mount)))
        command.extend(
            (
                "--workdir",
                str(execution_cwd),
                "--env",
                f"CODEX_HOME={auth_root}",
                "--env",
                f"HOME={execution_cwd}",
                "--env",
                f"PATH={_CONTAINER_PATH}",
                "--env",
                "TMPDIR=/tmp",
                "--env",
                "TERM=dumb",
                "--env",
                "LC_CTYPE=C.UTF-8",
                str(rootfs),
                "/bin/sh",
                "-c",
                _ENTRYPOINT,
                "lfb-codex-exec",
                str(os.getuid()),
                *argv,
            )
        )
        boundary_identity: dict[str, object] = {
            "policy_id": CONTRIBUTOR_ROOTLESS_PODMAN_BOUNDARY,
            "filesystem_scope": ROOTLESS_PODMAN_FILESYSTEM_SCOPE,
            "backend": "podman",
            "host_process_containment": POSIX_PROCESS_GROUP_CONTAINMENT,
            "isolated_environment": True,
            "transcript_redaction": True,
            "root_filesystem": "read_only",
            "network": "rootless_default",
            "user_namespace": "keep-id",
            "cap_drop": ["ALL"],
        }
        validate_public_record(boundary_identity, "contributor boundary identity")
        return RootlessPodmanLaunch(
            argv=tuple(command),
            environment=dict(backend_environment),
            boundary_identity=boundary_identity,
            control_root=control_root,
            _backend=backend,
            _container_name=name,
            _rootfs=rootfs,
            _mounts=tuple(mounts.values()),
            _temporary=temporary,
        )
    except Exception:
        temporary.cleanup()
        raise


def _validated_mount_identity(
    path: Path,
    *,
    target: Path,
    mode: str,
) -> _MountIdentity:
    if mode not in {"ro", "rw"}:
        raise RootlessPodmanBoundaryError("Podman mount mode must be ro or rw")
    source = Path(os.path.abspath(os.fspath(path)))
    destination = Path(os.path.abspath(os.fspath(target)))
    for value in (source, destination):
        encoded = str(value)
        if not value.is_absolute():
            raise RootlessPodmanBoundaryError("Podman mount paths must be absolute")
        if "," in encoded or any(ord(character) < 32 for character in encoded):
            raise RootlessPodmanBoundaryError(
                "Podman path contains unsafe mount-option characters"
            )
    if destination == Path("/"):
        raise RootlessPodmanBoundaryError("Podman must not bind the host root")
    try:
        home = Path.home().resolve(strict=True)
    except OSError:
        home = Path.home()
    if destination == home:
        raise RootlessPodmanBoundaryError("Podman must not bind the host home root")

    descriptor = _open_path_without_symlinks(source)
    try:
        metadata = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    file_type = stat.S_IFMT(metadata.st_mode)
    if file_type not in {stat.S_IFDIR, stat.S_IFREG}:
        raise RootlessPodmanBoundaryError(
            "Podman mount sources must be regular files or directories"
        )
    return _MountIdentity(
        source=source,
        target=destination,
        mode=mode,
        device=metadata.st_dev,
        inode=metadata.st_ino,
        file_type=file_type,
    )


def _open_path_without_symlinks(path: Path) -> int:
    nofollow = getattr(os, "O_NOFOLLOW", None)
    directory = getattr(os, "O_DIRECTORY", None)
    if nofollow is None or directory is None:
        raise RootlessPodmanBoundaryError(
            "safe Podman mount admission requires O_NOFOLLOW and O_DIRECTORY"
        )
    flags = os.O_RDONLY | nofollow | getattr(os, "O_CLOEXEC", 0)
    current = os.open("/", flags | directory)
    try:
        parts = path.parts[1:]
        if not parts:
            raise RootlessPodmanBoundaryError("Podman must not bind the host root")
        for index, part in enumerate(parts):
            component_flags = flags
            if index < len(parts) - 1:
                component_flags |= directory
            try:
                following = os.open(part, component_flags, dir_fd=current)
            except OSError as exc:
                raise RootlessPodmanBoundaryError(
                    "Podman mount source must exist without symlink components"
                ) from exc
            os.close(current)
            current = following
        return current
    except Exception:
        os.close(current)
        raise


def _prepare_mount_target(rootfs: Path, mount: _MountIdentity) -> None:
    relative = mount.target.relative_to(Path("/"))
    target = rootfs / relative
    if mount.file_type == stat.S_IFDIR:
        target.mkdir(mode=0o755, parents=True, exist_ok=True)
        return
    target.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0)
    try:
        descriptor = os.open(target, flags, 0o000)
    except FileExistsError:
        if not target.is_file() or target.is_symlink():
            raise RootlessPodmanBoundaryError(
                "Podman rootfs mount target has conflicting type"
            ) from None
    else:
        os.close(descriptor)


def _mount_argument(mount: _MountIdentity) -> str:
    return f"type=bind,source={mount.source},destination={mount.target}," + (
        "ro=true" if mount.mode == "ro" else "rw=true"
    )


def _restore_rootfs_ownership(
    backend: Path,
    rootfs: Path,
    environment: Mapping[str, str],
) -> None:
    """Map OCI-created subuid files back to the invoking user for deletion."""

    current_uid = os.getuid()
    needs_reset = False
    for directory, names, files in os.walk(rootfs, followlinks=False):
        paths = (
            Path(directory),
            *(Path(directory) / name for name in (*names, *files)),
        )
        if any(path.lstat().st_uid != current_uid for path in paths):
            needs_reset = True
            break
    if not needs_reset:
        return
    try:
        completed = subprocess.run(
            (
                str(backend),
                "unshare",
                "/usr/bin/chown",
                "-hR",
                "0:0",
                str(rootfs),
            ),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            timeout=30,
            env=dict(environment),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RootlessPodmanBoundaryError(
            "rootless Podman rootfs cleanup failed"
        ) from exc
    if (
        completed.returncode != 0
        or len(completed.stdout) > 65_536
        or len(completed.stderr) > 65_536
    ):
        raise RootlessPodmanBoundaryError("rootless Podman rootfs cleanup failed")


__all__ = [
    "CONTRIBUTOR_ROOTLESS_PODMAN_BOUNDARY",
    "ROOTLESS_PODMAN_FILESYSTEM_SCOPE",
    "RootlessPodmanBoundaryError",
    "RootlessPodmanLaunch",
    "prepare_rootless_podman_boundary",
    "require_rootless_podman_scope",
    "system_read_mounts",
]
