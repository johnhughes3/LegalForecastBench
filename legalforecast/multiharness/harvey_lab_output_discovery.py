"""Safe Harvey LAB solver-output discovery.

Walk only the declared sandbox output directory. Never follow links, never
execute content, never score extras. A solver write outside the sandbox is a
finding, not a score.
"""

from __future__ import annotations

import errno
import hashlib
import os
import shutil
import stat
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Literal

from legalforecast.contracts.schemas import HARVEY_LAB_OUTPUT_DISCOVERY_V2
from legalforecast.multiharness.deliverables import (
    DeliverableArtifactProjection,
    DeliverableLimits,
    DeliverableManifest,
    DeliverableValidationError,
    seal_deliverable,
)
from legalforecast.multiharness.harvey_lab.contract import (
    HarveyLabOutputSelectionError,
    selected_output_paths,
)
from legalforecast.multiharness.harvey_lab_projection import HarveyLabProjectedTask
from legalforecast.multiharness.validation import validate_sha256

HARVEY_LAB_OUTPUT_DISCOVERY_SCHEMA_VERSION = str(HARVEY_LAB_OUTPUT_DISCOVERY_V2)
HARVEY_LAB_DOCX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
_ARCHIVE_SUFFIXES = (
    ".7z",
    ".gz",
    ".rar",
    ".tar",
    ".tar.gz",
    ".tgz",
    ".zip",
)
_ZIP_MAGIC = b"PK\x03\x04"


class HarveyLabOutputErrorCode(StrEnum):
    """Typed bounded failures for one discovery attempt."""

    MISSING_DELIVERABLE = "missing_deliverable"
    DUPLICATE_BASENAME = "duplicate_basename"
    OVERSIZED = "oversized"
    PATH_TRAVERSAL = "path_traversal"
    SYMLINK = "symlink"
    ARCHIVE = "archive"
    UNEXPECTED_TYPE = "unexpected_type"
    SANDBOX_ESCAPE = "sandbox_escape"
    MATERIAL_OVERLAP = "material_overlap"
    LAYOUT = "layout"


class HarveyLabOutputDiscoveryError(ValueError):
    """Solver output could not be discovered without scoring unsafe bytes."""

    def __init__(self, message: str, *, code: HarveyLabOutputErrorCode) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class HarveyLabOutputLimits:
    """Bounds applied while walking the solver output directory."""

    max_files: int = 32
    max_file_bytes: int = 10 * 1024 * 1024
    max_total_bytes: int = 20 * 1024 * 1024
    max_directories: int = 32
    max_depth: int = 8

    def __post_init__(self) -> None:
        for field_name, value in (
            ("max_files", self.max_files),
            ("max_file_bytes", self.max_file_bytes),
            ("max_total_bytes", self.max_total_bytes),
            ("max_directories", self.max_directories),
            ("max_depth", self.max_depth),
        ):
            if type(value) is not int or value <= 0:
                raise ValueError(f"{field_name} must be a positive integer")


@dataclass(frozen=True, slots=True)
class HarveyLabQuarantinedFile:
    """An unrecognized extra that was copied out of the scored set."""

    source_relative: str
    quarantine_relative: str
    sha256: str
    size_bytes: int

    def to_record(self) -> dict[str, str | int]:
        return {
            "source_relative": self.source_relative,
            "quarantine_relative": self.quarantine_relative,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True, slots=True)
class HarveyLabOutputDiscoveryResult:
    """Sealed expected deliverable plus unscored quarantined extras."""

    task_id: str
    layout: str
    expected_deliverables: tuple[str, ...]
    sealed: DeliverableManifest
    quarantined: tuple[HarveyLabQuarantinedFile, ...]
    schema_version: str = HARVEY_LAB_OUTPUT_DISCOVERY_SCHEMA_VERSION

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "task_id": self.task_id,
            "layout": self.layout,
            "expected_deliverables": list(self.expected_deliverables),
            "sealed": self.sealed.to_record(),
            "quarantined": [item.to_record() for item in self.quarantined],
        }

    @property
    def expected_deliverable(self) -> str:
        """Compatibility accessor for single-file result consumers."""

        if len(self.expected_deliverables) != 1:
            raise HarveyLabOutputDiscoveryError(
                "result does not declare exactly one expected deliverable",
                code=HarveyLabOutputErrorCode.LAYOUT,
            )
        return self.expected_deliverables[0]


def require_harvey_lab_sandbox_hosts(
    *,
    sandbox_root: Path,
    output_root: Path,
) -> Path:
    """Fail closed before a solver spawns unless the LAB host layout is safe.

    Discovery already refuses a bad layout after the run, but by then the
    solver has already written somewhere. This is the same containment rule
    applied pre-spawn: ``sandbox_root`` and ``output_root`` must be real
    directories, neither may be a symlink, and ``output_root`` must resolve
    strictly inside ``sandbox_root`` (never equal to it). The resolved output
    directory is returned so callers hand the solver the checked path rather
    than the caller-supplied spelling.
    """

    sandbox_path = (
        sandbox_root if sandbox_root.is_absolute() else Path.cwd() / sandbox_root
    )
    output_path = output_root if output_root.is_absolute() else Path.cwd() / output_root
    _ensure_directory(sandbox_path, "sandbox_root")
    resolved_sandbox = sandbox_path.resolve(strict=True)
    _reject_uncontained_output(output_path, resolved_sandbox)
    _ensure_directory(output_path, "output_root")
    resolved_output = output_path.resolve(strict=True)
    _reject_uncontained_output(resolved_output, resolved_sandbox)
    return resolved_output


def _reject_uncontained_output(output_path: Path, resolved_sandbox: Path) -> None:
    """Refuse an output path that does not resolve strictly inside the sandbox.

    ``resolve(strict=False)`` is used for the not-yet-created case so a path
    whose parents escape the sandbox is rejected before ``mkdir`` would create
    directories outside it.
    """

    resolved_output = output_path.resolve(strict=False)
    if resolved_output == resolved_sandbox or not resolved_output.is_relative_to(
        resolved_sandbox
    ):
        raise HarveyLabOutputDiscoveryError(
            "output_root must be a real directory strictly inside sandbox_root",
            code=HarveyLabOutputErrorCode.LAYOUT,
        )


def discover_harvey_lab_outputs(
    *,
    sandbox_root: Path,
    output_root: Path,
    quarantine_root: Path,
    sealed_root: Path,
    task: HarveyLabProjectedTask,
    task_sha256: str,
    run_sha256: str,
    config_sha256: str,
    layout: Literal["native", "external"] = "native",
    limits: HarveyLabOutputLimits | None = None,
    escape_watch_roots: Sequence[Path] = (),
    evaluator_private_root: Path | None = None,
    projection_root: Path | None = None,
) -> HarveyLabOutputDiscoveryResult:
    """Find the expected deliverable and quarantine unrecognized extras.

    ``output_root`` must sit inside ``sandbox_root``. Quarantine and sealed
    trees must be disjoint from the sandbox, the projection, and evaluator-
    private material. Extra files are copied to ``quarantine_root`` and are
    never passed to the sealer. Writes observed outside the sandbox are a
    sandbox-escape finding, not a score.
    """

    applied = limits or HarveyLabOutputLimits()
    task_digest = _canonical_digest(task_sha256, "task_sha256")
    run_digest = _canonical_digest(run_sha256, "run_sha256")
    config_digest = _canonical_digest(config_sha256, "config_sha256")
    if task_digest != _canonical_digest(task.task_sha256, "task_sha256"):
        raise HarveyLabOutputDiscoveryError(
            "task_sha256 does not match the selected projected task",
            code=HarveyLabOutputErrorCode.LAYOUT,
        )
    sandbox_path = (
        sandbox_root if sandbox_root.is_absolute() else Path.cwd() / sandbox_root
    )
    output_path = output_root if output_root.is_absolute() else Path.cwd() / output_root
    if sandbox_path.is_symlink() or output_path.is_symlink():
        raise HarveyLabOutputDiscoveryError(
            "sandbox_root and output_root must not be symlinks",
            code=HarveyLabOutputErrorCode.SYMLINK,
        )
    sandbox_fd = _open_directory(sandbox_path, "sandbox_root")
    try:
        try:
            sandbox = Path(os.readlink(f"/proc/self/fd/{sandbox_fd}"))
        except OSError as exc:
            raise HarveyLabOutputDiscoveryError(
                "sandbox_root must be a real directory",
                code=HarveyLabOutputErrorCode.LAYOUT,
            ) from exc
        try:
            output_relative = output_path.resolve(strict=True).relative_to(sandbox)
        except (OSError, ValueError) as exc:
            raise HarveyLabOutputDiscoveryError(
                "output_root must be inside sandbox_root",
                code=HarveyLabOutputErrorCode.LAYOUT,
            ) from exc
        if not output_relative.parts:
            raise HarveyLabOutputDiscoveryError(
                "output_root must be inside sandbox_root",
                code=HarveyLabOutputErrorCode.LAYOUT,
            )
        disjoint_roots = [sandbox, quarantine_root, sealed_root]
        if evaluator_private_root is not None:
            private = (
                evaluator_private_root
                if evaluator_private_root.is_absolute()
                else (Path.cwd() / evaluator_private_root)
            )
            disjoint_roots.append(private.resolve(strict=False))
            if _is_inside(sandbox / output_relative, disjoint_roots[-1]):
                raise HarveyLabOutputDiscoveryError(
                    "solver output must not share a directory with "
                    "evaluator-private material",
                    code=HarveyLabOutputErrorCode.MATERIAL_OVERLAP,
                )
        if projection_root is not None:
            projection = (
                projection_root
                if projection_root.is_absolute()
                else (Path.cwd() / projection_root)
            )
            disjoint_roots.append(projection.resolve(strict=False))
        _require_disjoint(disjoint_roots)
        _reject_escape_watch(escape_watch_roots, sandbox)

        for basename in task.expected_deliverables:
            if "/" in basename or basename in {".", ""}:
                raise HarveyLabOutputDiscoveryError(
                    "expected_deliverables must be basenames inside output/",
                    code=HarveyLabOutputErrorCode.LAYOUT,
                )

        output_fd = _open_nested_directory_from_fd(
            sandbox_fd, output_relative.as_posix()
        )
        try:
            return _discover_from_output_fd(
                output_fd,
                sandbox=sandbox,
                quarantine_root=quarantine_root,
                sealed_root=sealed_root,
                task=task,
                task_sha256=task_digest,
                run_sha256=run_digest,
                config_sha256=config_digest,
                layout=layout,
                limits=applied,
            )
        finally:
            os.close(output_fd)
    finally:
        os.close(sandbox_fd)


def _discover_from_output_fd(
    output_fd: int,
    *,
    sandbox: Path,
    quarantine_root: Path,
    sealed_root: Path,
    task: HarveyLabProjectedTask,
    task_sha256: str,
    run_sha256: str,
    config_sha256: str,
    layout: Literal["native", "external"],
    limits: HarveyLabOutputLimits,
) -> HarveyLabOutputDiscoveryResult:
    entries = _walk_from_fd(output_fd, limits=limits)
    try:
        selected_paths = selected_output_paths(
            [item.relative for item in entries], task.expected_deliverables
        )
    except HarveyLabOutputSelectionError as exc:
        raise HarveyLabOutputDiscoveryError(
            str(exc), code=HarveyLabOutputErrorCode(exc.code)
        ) from exc
    by_path = {item.relative: item for item in entries}
    selected = [by_path[path] for path in selected_paths]
    for expected in selected:
        _require_expected_docx(expected, limits=limits)
        _require_zip_magic(output_fd, expected)

    selected_set = set(selected_paths)
    extras = [item for item in entries if item.relative not in selected_set]
    quarantined = _quarantine_extras(
        extras,
        output_fd=output_fd,
        quarantine_root=quarantine_root,
        limits=limits,
    )

    _ensure_directory(quarantine_root.parent, "quarantine parent")
    try:
        staging_root = Path(
            tempfile.mkdtemp(
                prefix="lfb-lab-discovery-staging-",
                dir=str(quarantine_root.parent),
            )
        )
    except OSError as exc:
        raise HarveyLabOutputDiscoveryError(
            "could not create discovery staging directory",
            code=HarveyLabOutputErrorCode.LAYOUT,
        ) from exc
    try:
        if _is_inside(staging_root, sandbox):
            raise HarveyLabOutputDiscoveryError(
                "discovery staging must not share a directory with the sandbox",
                code=HarveyLabOutputErrorCode.MATERIAL_OVERLAP,
            )
        for expected in selected:
            _copy_regular_file_from_fd(
                output_fd,
                expected.relative,
                destination_root=staging_root,
                destination_relative=expected.relative,
                expected_stat=expected.file_stat,
                expected_digest=expected.sha256,
                max_bytes=limits.max_file_bytes,
            )
        try:
            sealed = seal_deliverable(
                source_root=staging_root,
                sealed_root=sealed_root,
                task_sha256=task_sha256,
                run_sha256=run_sha256,
                config_sha256=config_sha256,
                artifacts=tuple(
                    DeliverableArtifactProjection(
                        artifact_id=f"lab-deliverable:{expected.relative}",
                        source_path=expected.relative,
                        path=expected.relative,
                        media_type=HARVEY_LAB_DOCX_MEDIA_TYPE,
                        max_size_bytes=limits.max_file_bytes,
                    )
                    for expected in selected
                ),
                limits=DeliverableLimits(
                    max_files=len(selected),
                    max_file_bytes=limits.max_file_bytes,
                    max_total_bytes=limits.max_total_bytes,
                ),
            )
        except DeliverableValidationError as exc:
            raise HarveyLabOutputDiscoveryError(
                str(exc),
                code=HarveyLabOutputErrorCode.UNEXPECTED_TYPE,
            ) from exc
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)

    return HarveyLabOutputDiscoveryResult(
        task_id=task.task_id,
        layout=layout,
        expected_deliverables=task.expected_deliverables,
        sealed=sealed,
        quarantined=tuple(quarantined),
    )


@dataclass(frozen=True, slots=True)
class _OutputEntry:
    relative: str
    file_stat: os.stat_result
    kind: str
    sha256: bytes


@dataclass
class _WalkState:
    entries: list[_OutputEntry]
    total_bytes: int = 0
    directory_count: int = 0


def _walk_from_fd(
    output_fd: int,
    *,
    limits: HarveyLabOutputLimits,
) -> list[_OutputEntry]:
    state = _WalkState(entries=[])
    _scan_output(
        output_fd,
        prefix="",
        limits=limits,
        state=state,
    )
    state.entries.sort(key=lambda item: item.relative)
    return state.entries


def _scan_output(
    directory_fd: int,
    *,
    prefix: str,
    limits: HarveyLabOutputLimits,
    state: _WalkState,
) -> None:
    try:
        iterator = os.scandir(directory_fd)
    except OSError as exc:
        raise HarveyLabOutputDiscoveryError(
            "could not enumerate solver output",
            code=HarveyLabOutputErrorCode.LAYOUT,
        ) from exc
    with iterator:
        for entry in iterator:
            relative = f"{prefix}/{entry.name}" if prefix else entry.name
            _reject_path_name(entry.name, relative)
            try:
                entry_stat = entry.stat(follow_symlinks=False)
            except OSError as exc:
                raise HarveyLabOutputDiscoveryError(
                    f"output changed during discovery: {relative}",
                    code=HarveyLabOutputErrorCode.LAYOUT,
                ) from exc
            if stat.S_ISLNK(entry_stat.st_mode):
                raise HarveyLabOutputDiscoveryError(
                    f"solver output contains a symlink: {relative}",
                    code=HarveyLabOutputErrorCode.SYMLINK,
                )
            if stat.S_ISDIR(entry_stat.st_mode):
                depth = relative.count("/") + 1
                if depth > limits.max_depth:
                    raise HarveyLabOutputDiscoveryError(
                        "solver output exceeds the directory-depth limit",
                        code=HarveyLabOutputErrorCode.OVERSIZED,
                    )
                state.directory_count += 1
                if state.directory_count > limits.max_directories:
                    raise HarveyLabOutputDiscoveryError(
                        "solver output exceeds the directory-count limit",
                        code=HarveyLabOutputErrorCode.OVERSIZED,
                    )
                child_fd = _open_child_directory(directory_fd, entry.name)
                try:
                    _scan_output(
                        child_fd,
                        prefix=relative,
                        limits=limits,
                        state=state,
                    )
                finally:
                    os.close(child_fd)
                continue
            if not stat.S_ISREG(entry_stat.st_mode):
                raise HarveyLabOutputDiscoveryError(
                    f"solver output contains a non-file: {relative}",
                    code=HarveyLabOutputErrorCode.UNEXPECTED_TYPE,
                )
            if entry_stat.st_nlink != 1:
                raise HarveyLabOutputDiscoveryError(
                    f"solver output contains a hard link: {relative}",
                    code=HarveyLabOutputErrorCode.UNEXPECTED_TYPE,
                )
            if len(state.entries) >= limits.max_files:
                raise HarveyLabOutputDiscoveryError(
                    "solver output exceeds the file-count limit",
                    code=HarveyLabOutputErrorCode.OVERSIZED,
                )
            if entry_stat.st_size > limits.max_file_bytes:
                raise HarveyLabOutputDiscoveryError(
                    f"solver output exceeds the byte limit: {relative}",
                    code=HarveyLabOutputErrorCode.OVERSIZED,
                )
            next_total = state.total_bytes + entry_stat.st_size
            if next_total > limits.max_total_bytes:
                raise HarveyLabOutputDiscoveryError(
                    "solver output exceeds the total byte limit",
                    code=HarveyLabOutputErrorCode.OVERSIZED,
                )
            state.total_bytes = next_total
            kind = _classify_regular(relative, entry_stat)
            try:
                file_fd = os.open(entry.name, _file_flags(), dir_fd=directory_fd)
            except OSError as exc:
                raise HarveyLabOutputDiscoveryError(
                    f"output changed during discovery: {relative}",
                    code=HarveyLabOutputErrorCode.LAYOUT,
                ) from exc
            try:
                hashed_stat = os.fstat(file_fd)
                if not stat.S_ISREG(hashed_stat.st_mode) or _file_identity_changed(
                    entry_stat, hashed_stat
                ):
                    raise HarveyLabOutputDiscoveryError(
                        f"output changed during discovery: {relative}",
                        code=HarveyLabOutputErrorCode.LAYOUT,
                    )
                content_sha256 = _sha256_fd(file_fd, max_bytes=entry_stat.st_size)
                hashed_after = os.fstat(file_fd)
                if _file_identity_changed(entry_stat, hashed_after):
                    raise HarveyLabOutputDiscoveryError(
                        f"output changed during discovery: {relative}",
                        code=HarveyLabOutputErrorCode.LAYOUT,
                    )
            finally:
                os.close(file_fd)
            state.entries.append(
                _OutputEntry(relative, entry_stat, kind, content_sha256)
            )


def _classify_regular(relative: str, file_stat: os.stat_result) -> str:
    name = PurePosixPath(relative).name
    lowered = name.casefold()
    if any(lowered.endswith(suffix) for suffix in _ARCHIVE_SUFFIXES) and not (
        lowered.endswith(".docx")
    ):
        return "archive"
    if file_stat.st_mode & 0o111:
        return "unexpected_type"
    return "regular"


def _require_expected_docx(
    entry: _OutputEntry,
    *,
    limits: HarveyLabOutputLimits,
) -> None:
    if entry.kind != "regular":
        raise HarveyLabOutputDiscoveryError(
            f"expected deliverable has type {entry.kind}",
            code=_code_for_kind(entry.kind),
        )
    if entry.file_stat.st_size > limits.max_file_bytes:
        raise HarveyLabOutputDiscoveryError(
            "expected deliverable exceeds the byte limit",
            code=HarveyLabOutputErrorCode.OVERSIZED,
        )
    if not PurePosixPath(entry.relative).name.endswith(".docx"):
        raise HarveyLabOutputDiscoveryError(
            "expected deliverable must be a .docx file",
            code=HarveyLabOutputErrorCode.UNEXPECTED_TYPE,
        )


def _require_zip_magic(output_fd: int, entry: _OutputEntry) -> None:
    file_fd = _open_relative_from_fd(output_fd, entry.relative, _file_flags())
    try:
        header = os.read(file_fd, 4)
        opened = os.fstat(file_fd)
        if _file_identity_changed(entry.file_stat, opened):
            raise HarveyLabOutputDiscoveryError(
                f"output changed while copying: {entry.relative}",
                code=HarveyLabOutputErrorCode.LAYOUT,
            )
    finally:
        os.close(file_fd)
    if header != _ZIP_MAGIC:
        raise HarveyLabOutputDiscoveryError(
            "expected deliverable is not a DOCX/ZIP container",
            code=HarveyLabOutputErrorCode.UNEXPECTED_TYPE,
        )


def _quarantine_extras(
    extras: Sequence[_OutputEntry],
    *,
    output_fd: int,
    quarantine_root: Path,
    limits: HarveyLabOutputLimits,
) -> list[HarveyLabQuarantinedFile]:
    quarantined: list[HarveyLabQuarantinedFile] = []
    if not extras:
        _clear_directory(quarantine_root)
        return quarantined
    _reset_directory(quarantine_root)
    for extra in extras:
        if extra.kind == "archive":
            raise HarveyLabOutputDiscoveryError(
                f"solver output contains an archive: {extra.relative}",
                code=HarveyLabOutputErrorCode.ARCHIVE,
            )
        if extra.kind != "regular":
            raise HarveyLabOutputDiscoveryError(
                f"solver output contains an unexpected type: {extra.relative}",
                code=_code_for_kind(extra.kind),
            )
        if extra.file_stat.st_size > limits.max_file_bytes:
            raise HarveyLabOutputDiscoveryError(
                f"extra output exceeds the byte limit: {extra.relative}",
                code=HarveyLabOutputErrorCode.OVERSIZED,
            )
        digest, size_bytes = _copy_regular_file_from_fd(
            output_fd,
            extra.relative,
            destination_root=quarantine_root,
            destination_relative=extra.relative,
            expected_stat=extra.file_stat,
            expected_digest=extra.sha256,
            max_bytes=limits.max_file_bytes,
        )
        quarantined.append(
            HarveyLabQuarantinedFile(
                source_relative=extra.relative,
                quarantine_relative=extra.relative,
                sha256=digest,
                size_bytes=size_bytes,
            )
        )
    return quarantined


def _copy_regular_file_from_fd(
    source_root_fd: int,
    source_relative: str,
    *,
    destination_root: Path,
    destination_relative: str,
    expected_stat: os.stat_result,
    expected_digest: bytes,
    max_bytes: int,
) -> tuple[str, int]:
    source_fd = _open_relative_from_fd(source_root_fd, source_relative, _file_flags())
    try:
        opened = os.fstat(source_fd)
        if _file_identity_changed(expected_stat, opened):
            raise HarveyLabOutputDiscoveryError(
                f"output changed while copying: {source_relative}",
                code=HarveyLabOutputErrorCode.LAYOUT,
            )
        if opened.st_size > max_bytes:
            raise HarveyLabOutputDiscoveryError(
                f"output exceeds the byte limit: {source_relative}",
                code=HarveyLabOutputErrorCode.OVERSIZED,
            )
        destination_fd = _create_relative_file(destination_root, destination_relative)
        digest = hashlib.sha256()
        size_bytes = 0
        try:
            with os.fdopen(os.dup(source_fd), "rb") as source_handle:
                with os.fdopen(
                    destination_fd, "wb", closefd=False
                ) as destination_handle:
                    while True:
                        chunk = source_handle.read(1024 * 1024)
                        if not chunk:
                            break
                        size_bytes += len(chunk)
                        if size_bytes > max_bytes:
                            raise HarveyLabOutputDiscoveryError(
                                f"output exceeds the byte limit: {source_relative}",
                                code=HarveyLabOutputErrorCode.OVERSIZED,
                            )
                        digest.update(chunk)
                        destination_handle.write(chunk)
            final = os.fstat(source_fd)
            if _file_identity_changed(
                expected_stat, final, copied_bytes=size_bytes
            ) or _file_identity_changed(opened, final, copied_bytes=size_bytes):
                raise HarveyLabOutputDiscoveryError(
                    f"output changed while copying: {source_relative}",
                    code=HarveyLabOutputErrorCode.LAYOUT,
                )
            destination_stat = os.fstat(destination_fd)
            if destination_stat.st_size != size_bytes:
                raise HarveyLabOutputDiscoveryError(
                    f"output changed while copying: {source_relative}",
                    code=HarveyLabOutputErrorCode.LAYOUT,
                )
            copied = digest.digest()
            if (
                copied != expected_digest
                or _sha256_fd(source_fd, max_bytes=size_bytes) != copied
            ):
                raise HarveyLabOutputDiscoveryError(
                    f"output changed while copying: {source_relative}",
                    code=HarveyLabOutputErrorCode.LAYOUT,
                )
            return "sha256:" + digest.hexdigest(), size_bytes
        except HarveyLabOutputDiscoveryError:
            _unlink_relative(destination_root, destination_relative)
            raise
        finally:
            os.close(destination_fd)
    finally:
        os.close(source_fd)


def _reject_path_name(name: str, relative: str) -> None:
    if name in {".", ".."} or "\x00" in name:
        raise HarveyLabOutputDiscoveryError(
            f"solver output path is unsafe: {relative}",
            code=HarveyLabOutputErrorCode.PATH_TRAVERSAL,
        )
    if name.startswith("."):
        raise HarveyLabOutputDiscoveryError(
            f"solver output contains a hidden path: {relative}",
            code=HarveyLabOutputErrorCode.UNEXPECTED_TYPE,
        )


def _reject_escape_watch(
    watch_roots: Sequence[Path],
    sandbox: Path,
) -> None:
    for raw in watch_roots:
        watch = raw if raw.is_absolute() else Path.cwd() / raw
        if watch.is_symlink():
            raise HarveyLabOutputDiscoveryError(
                "escape watch root must not be a symlink",
                code=HarveyLabOutputErrorCode.SYMLINK,
            )
        if not watch.exists():
            continue
        if not watch.is_dir():
            raise HarveyLabOutputDiscoveryError(
                "escape watch root must be a real directory",
                code=HarveyLabOutputErrorCode.LAYOUT,
            )
        resolved = watch.resolve(strict=True)
        if _is_inside(resolved, sandbox) or _is_inside(sandbox, resolved):
            raise HarveyLabOutputDiscoveryError(
                "escape watch root must be disjoint from the sandbox",
                code=HarveyLabOutputErrorCode.LAYOUT,
            )
        watch_fd = _open_directory(watch, "escape watch root")
        try:
            with os.scandir(watch_fd) as iterator:
                if any(True for _ in iterator):
                    raise HarveyLabOutputDiscoveryError(
                        "solver wrote outside its sandbox",
                        code=HarveyLabOutputErrorCode.SANDBOX_ESCAPE,
                    )
        finally:
            os.close(watch_fd)


def _require_disjoint(roots: Sequence[Path]) -> None:
    normalized = tuple(
        (root if root.is_absolute() else Path.cwd() / root).resolve(strict=False)
        for root in roots
    )
    for index, first in enumerate(normalized):
        for second in normalized[index + 1 :]:
            if (
                first == second
                or first.is_relative_to(second)
                or second.is_relative_to(first)
            ):
                raise HarveyLabOutputDiscoveryError(
                    "solver-visible, sealed, quarantine, and private roots "
                    "must be disjoint",
                    code=HarveyLabOutputErrorCode.MATERIAL_OVERLAP,
                )


def _is_inside(inner: Path, outer: Path) -> bool:
    try:
        inner.resolve(strict=False).relative_to(outer.resolve(strict=False))
    except ValueError:
        return False
    return True


def _ensure_directory(path: Path, field_name: str) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise HarveyLabOutputDiscoveryError(
            f"{field_name} must be a real directory",
            code=HarveyLabOutputErrorCode.LAYOUT,
        ) from exc
    if path.is_symlink():
        raise HarveyLabOutputDiscoveryError(
            f"{field_name} must not be a symlink",
            code=HarveyLabOutputErrorCode.SYMLINK,
        )
    if not path.is_dir():
        raise HarveyLabOutputDiscoveryError(
            f"{field_name} must be a real directory",
            code=HarveyLabOutputErrorCode.LAYOUT,
        )


def _file_identity_changed(
    expected: os.stat_result,
    actual: os.stat_result,
    *,
    copied_bytes: int | None = None,
) -> bool:
    if (
        actual.st_ino != expected.st_ino
        or actual.st_dev != expected.st_dev
        or actual.st_nlink != expected.st_nlink
        or actual.st_size != expected.st_size
        or actual.st_mtime_ns != expected.st_mtime_ns
        or actual.st_ctime_ns != expected.st_ctime_ns
    ):
        return True
    return copied_bytes is not None and actual.st_size != copied_bytes


def _canonical_digest(value: str, field_name: str) -> str:
    canonical = value if value.startswith("sha256:") else f"sha256:{value}"
    validate_sha256(canonical, field_name)
    return canonical


# contract-ratchet: allow non-persisted live-file copy digest
def _sha256_fd(file_fd: int, *, max_bytes: int) -> bytes:
    os.lseek(file_fd, 0, os.SEEK_SET)
    digest = hashlib.sha256()
    seen = 0
    while True:
        chunk = os.read(file_fd, 1024 * 1024)
        if not chunk:
            break
        seen += len(chunk)
        if seen > max_bytes:
            raise HarveyLabOutputDiscoveryError(
                "solver output exceeds the byte limit while hashing",
                code=HarveyLabOutputErrorCode.OVERSIZED,
            )
        digest.update(chunk)
    return digest.digest()


def _clear_directory(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
        return
    if path.exists():
        shutil.rmtree(path)


def _reset_directory(path: Path) -> None:
    _clear_directory(path)
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    parent_fd = _open_directory(parent, "destination parent")
    try:
        os.mkdir(path.name, 0o700, dir_fd=parent_fd)
    except OSError as exc:
        raise HarveyLabOutputDiscoveryError(
            "could not create destination directory",
            code=_destination_error_code(exc),
        ) from exc
    finally:
        os.close(parent_fd)


def _directory_flags() -> int:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    return flags


def _file_flags() -> int:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    return flags


def _destination_file_flags() -> int:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    return flags


def _destination_error_code(exc: OSError) -> HarveyLabOutputErrorCode:
    if exc.errno in {errno.ELOOP, errno.ENOTDIR}:
        return HarveyLabOutputErrorCode.SYMLINK
    return HarveyLabOutputErrorCode.LAYOUT


def _open_directory(path: Path, field_name: str) -> int:
    try:
        return os.open(path, _directory_flags())
    except OSError as exc:
        raise HarveyLabOutputDiscoveryError(
            f"{field_name} must be a real directory",
            code=HarveyLabOutputErrorCode.LAYOUT,
        ) from exc


def _open_child_directory(parent_fd: int, name: str) -> int:
    try:
        return os.open(name, _directory_flags(), dir_fd=parent_fd)
    except OSError as exc:
        raise HarveyLabOutputDiscoveryError(
            "solver output directory changed or is a symlink",
            code=HarveyLabOutputErrorCode.SYMLINK,
        ) from exc


def _open_nested_directory_from_fd(root_fd: int, relative: str) -> int:
    posix = PurePosixPath(relative)
    if relative in {"", "."} or posix == PurePosixPath("."):
        return os.dup(root_fd)
    current_fd = os.dup(root_fd)
    try:
        for part in posix.parts:
            if part == ".":
                continue
            _reject_path_name(part, relative)
            next_fd = _open_child_directory(current_fd, part)
            os.close(current_fd)
            current_fd = next_fd
        owned = current_fd
        current_fd = -1
        return owned
    except HarveyLabOutputDiscoveryError:
        raise
    except OSError as exc:
        raise HarveyLabOutputDiscoveryError(
            "output_root must be a real directory",
            code=HarveyLabOutputErrorCode.LAYOUT,
        ) from exc
    finally:
        if current_fd >= 0:
            os.close(current_fd)


def _open_relative_from_fd(root_fd: int, relative: str, flags: int) -> int:
    parts = PurePosixPath(relative).parts
    if not parts:
        raise HarveyLabOutputDiscoveryError(
            f"solver output path is unsafe: {relative}",
            code=HarveyLabOutputErrorCode.PATH_TRAVERSAL,
        )
    current_fd = os.dup(root_fd)
    try:
        for part in parts[:-1]:
            _reject_path_name(part, relative)
            next_fd = _open_child_directory(current_fd, part)
            os.close(current_fd)
            current_fd = next_fd
        _reject_path_name(parts[-1], relative)
        return os.open(parts[-1], flags, dir_fd=current_fd)
    except HarveyLabOutputDiscoveryError:
        raise
    except OSError as exc:
        raise HarveyLabOutputDiscoveryError(
            f"could not open output file: {relative}",
            code=HarveyLabOutputErrorCode.LAYOUT,
        ) from exc
    finally:
        os.close(current_fd)


def _create_relative_file(root: Path, relative: str) -> int:
    root_fd = _open_directory(root, "destination_root")
    current_fd = root_fd
    try:
        parts = PurePosixPath(relative).parts
        if not parts:
            raise HarveyLabOutputDiscoveryError(
                f"destination path is unsafe: {relative}",
                code=HarveyLabOutputErrorCode.PATH_TRAVERSAL,
            )
        for part in parts[:-1]:
            _reject_path_name(part, relative)
            try:
                os.mkdir(part, 0o700, dir_fd=current_fd)
            except FileExistsError:
                pass
            next_fd = _open_child_directory(current_fd, part)
            os.close(current_fd)
            current_fd = next_fd
        _reject_path_name(parts[-1], relative)
        try:
            return os.open(
                parts[-1],
                _destination_file_flags(),
                0o600,
                dir_fd=current_fd,
            )
        except OSError as exc:
            raise HarveyLabOutputDiscoveryError(
                f"could not create destination file: {relative}",
                code=_destination_error_code(exc),
            ) from exc
    except HarveyLabOutputDiscoveryError:
        raise
    except OSError as exc:
        raise HarveyLabOutputDiscoveryError(
            f"could not create destination file: {relative}",
            code=_destination_error_code(exc),
        ) from exc
    finally:
        os.close(current_fd)


def _unlink_relative(root: Path, relative: str) -> None:
    root_fd = _open_directory(root, "destination_root")
    current_fd = root_fd
    try:
        parts = PurePosixPath(relative).parts
        if not parts:
            return
        for part in parts[:-1]:
            next_fd = _open_child_directory(current_fd, part)
            os.close(current_fd)
            current_fd = next_fd
        os.unlink(parts[-1], dir_fd=current_fd)
    except OSError:
        # Best-effort cleanup after a failed destination copy.
        return
    finally:
        os.close(current_fd)


def _code_for_kind(kind: str) -> HarveyLabOutputErrorCode:
    if kind == "archive":
        return HarveyLabOutputErrorCode.ARCHIVE
    if kind == "symlink":
        return HarveyLabOutputErrorCode.SYMLINK
    return HarveyLabOutputErrorCode.UNEXPECTED_TYPE
