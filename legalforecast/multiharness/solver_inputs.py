"""Private, content-addressed solver inputs for live multi-harness rows."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Self, cast

from legalforecast._json_io import read_json_object, write_json_object
from legalforecast.multiharness.materialization import (
    TaskArtifactProjection,
    TaskMaterializationLayout,
    TaskMaterializationManifest,
    materialize_task,
)
from legalforecast.multiharness.spec import ArtifactRecord, CanonicalTask
from legalforecast.multiharness.validation import (
    require_schema_version,
    require_sequence,
    require_str,
    validate_safe_relative_path,
    validate_sha256,
    validate_unique_ids,
)

SOLVER_INPUT_PAYLOAD_SCHEMA_VERSION = (
    "legalforecast.multiharness.solver_input_payload.v1"
)
SOLVER_INPUT_INDEX_SCHEMA_VERSION = "legalforecast.multiharness.solver_input_index.v1"
SOLVER_INPUT_LAYOUT_ID = "legalforecast.solver_input.v1"
SOLVER_INPUT_EXECUTION_MANIFEST_SCHEMA_VERSION = (
    "legalforecast.multiharness.solver_input_execution_manifest.v1"
)
SOLVER_INPUT_ENTRY_PATH = "prompt.txt"
SOLVER_INPUT_INDEX_NAME = "solver-input-index.json"
_SOURCE_PACKET_PATH = "source/model-packet.json"


class SolverInputError(ValueError):
    """Raised when private solver input cannot be authenticated."""


@dataclass(frozen=True, slots=True)
class SolverInputPayload:
    """Complete solver-visible LFB input, kept outside public task records."""

    task: CanonicalTask
    prompt: str = field(repr=False)
    source_packet: Mapping[str, Any] = field(repr=False)

    def __post_init__(self) -> None:
        if not self.prompt.strip():
            raise ValueError("prompt must be non-empty")
        if not self.source_packet:
            raise ValueError("source_packet must not be empty")


@dataclass(frozen=True, slots=True)
class SolverInputFile:
    """One authenticated file in a private solver-input tree."""

    source_path: str
    destination_path: str
    media_type: str
    sha256: str
    size_bytes: int
    solver_visible: bool

    def __post_init__(self) -> None:
        validate_safe_relative_path(self.source_path, "source_path")
        validate_safe_relative_path(self.destination_path, "destination_path")
        if not self.media_type.strip():
            raise ValueError("media_type must be non-empty")
        validate_sha256(self.sha256, "sha256")
        if type(self.size_bytes) is not int or self.size_bytes <= 0:
            raise ValueError("size_bytes must be a positive integer")
        if type(self.solver_visible) is not bool:
            raise ValueError("solver_visible must be a boolean")

    def to_record(self) -> dict[str, str | int]:
        return {
            "source_path": self.source_path,
            "destination_path": self.destination_path,
            "media_type": self.media_type,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "solver_visible": self.solver_visible,
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        if set(record) != {
            "source_path",
            "destination_path",
            "media_type",
            "sha256",
            "size_bytes",
            "solver_visible",
        }:
            raise SolverInputError("solver input file has unexpected fields")
        size_bytes = record.get("size_bytes")
        if type(size_bytes) is not int:
            raise SolverInputError("solver input file size_bytes is invalid")
        solver_visible = record.get("solver_visible")
        if type(solver_visible) is not bool:
            raise SolverInputError("solver input file solver_visible is invalid")
        return cls(
            source_path=require_str(record, "source_path"),
            destination_path=require_str(record, "destination_path"),
            media_type=require_str(record, "media_type"),
            sha256=require_str(record, "sha256"),
            size_bytes=size_bytes,
            solver_visible=solver_visible,
        )


@dataclass(frozen=True, slots=True)
class SolverInputEntry:
    """Content-addressed private input tree for one canonical task."""

    task_id: str
    task_sha256: str
    prompt_sha256: str
    entrypoint_path: str
    files: tuple[SolverInputFile, ...]
    tree_sha256: str

    def __post_init__(self) -> None:
        if not self.task_id.strip():
            raise ValueError("task_id must be non-empty")
        validate_sha256(self.task_sha256, "task_sha256")
        validate_sha256(self.prompt_sha256, "prompt_sha256")
        validate_safe_relative_path(self.entrypoint_path, "entrypoint_path")
        if not self.files:
            raise ValueError("files must not be empty")
        validate_unique_ids(
            (item.destination_path for item in self.files),
            "solver input destination paths",
        )
        validate_unique_ids(
            (item.source_path for item in self.files),
            "solver input source paths",
        )
        casefolded = tuple(item.destination_path.casefold() for item in self.files)
        validate_unique_ids(casefolded, "case-folded solver input paths")
        visible_files = tuple(item for item in self.files if item.solver_visible)
        if self.entrypoint_path not in {
            item.destination_path for item in visible_files
        }:
            raise SolverInputError("solver input entrypoint is not in the file tree")
        files_by_path = {item.destination_path: item for item in self.files}
        if set(files_by_path) != {SOLVER_INPUT_ENTRY_PATH, _SOURCE_PACKET_PATH}:
            raise SolverInputError("solver input entry has an unexpected file layout")
        prompt_file = files_by_path[SOLVER_INPUT_ENTRY_PATH]
        source_file = files_by_path[_SOURCE_PACKET_PATH]
        if not prompt_file.solver_visible or source_file.solver_visible:
            raise SolverInputError("solver input file visibility is invalid")
        if _normalized_sha256(prompt_file.sha256) != _normalized_sha256(
            self.prompt_sha256
        ):
            raise SolverInputError("solver prompt sha256 does not match task metadata")
        if _normalized_sha256(source_file.sha256) != _normalized_sha256(
            self.task_sha256
        ):
            raise SolverInputError("source packet sha256 does not match task")
        validate_sha256(self.tree_sha256, "tree_sha256")
        if self.tree_sha256 != _tree_sha256(self.files):
            raise SolverInputError("solver input tree sha256 does not match files")

    def to_record(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_sha256": self.task_sha256,
            "prompt_sha256": self.prompt_sha256,
            "entrypoint_path": self.entrypoint_path,
            "files": [item.to_record() for item in self.files],
            "tree_sha256": self.tree_sha256,
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        if set(record) != {
            "task_id",
            "task_sha256",
            "prompt_sha256",
            "entrypoint_path",
            "files",
            "tree_sha256",
        }:
            raise SolverInputError("solver input entry has unexpected fields")
        files: list[SolverInputFile] = []
        for value in require_sequence(record, "files"):
            if not isinstance(value, Mapping):
                raise SolverInputError("solver input files must be objects")
            files.append(SolverInputFile.from_record(cast(Mapping[str, Any], value)))
        return cls(
            task_id=require_str(record, "task_id"),
            task_sha256=require_str(record, "task_sha256"),
            prompt_sha256=require_str(record, "prompt_sha256"),
            entrypoint_path=require_str(record, "entrypoint_path"),
            files=tuple(files),
            tree_sha256=require_str(record, "tree_sha256"),
        )


@dataclass(frozen=True, slots=True)
class SolverInputIndex:
    """Private manifest binding a task index to all solver-visible trees."""

    task_index_sha256: str
    entries: tuple[SolverInputEntry, ...]
    index_sha256: str

    def __post_init__(self) -> None:
        validate_sha256(self.task_index_sha256, "task_index_sha256")
        if not self.entries:
            raise ValueError("entries must not be empty")
        validate_unique_ids(
            (entry.task_id for entry in self.entries),
            "solver input task IDs",
        )
        validate_sha256(self.index_sha256, "index_sha256")
        if self.index_sha256 != _record_sha256(self.content_record()):
            raise SolverInputError("solver input index sha256 does not match content")

    def content_record(self) -> dict[str, Any]:
        return {
            "schema_version": SOLVER_INPUT_INDEX_SCHEMA_VERSION,
            "task_index_sha256": self.task_index_sha256,
            "entries": [entry.to_record() for entry in self.entries],
        }

    def to_record(self) -> dict[str, Any]:
        return {**self.content_record(), "index_sha256": self.index_sha256}

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        if set(record) != {
            "schema_version",
            "task_index_sha256",
            "entries",
            "index_sha256",
        }:
            raise SolverInputError("solver input index has unexpected fields")
        require_schema_version(record, SOLVER_INPUT_INDEX_SCHEMA_VERSION)
        entries: list[SolverInputEntry] = []
        for value in require_sequence(record, "entries"):
            if not isinstance(value, Mapping):
                raise SolverInputError("solver input index entries must be objects")
            entries.append(SolverInputEntry.from_record(cast(Mapping[str, Any], value)))
        return cls(
            task_index_sha256=require_str(record, "task_index_sha256"),
            entries=tuple(entries),
            index_sha256=require_str(record, "index_sha256"),
        )


@dataclass(frozen=True, slots=True)
class SolverInputStore:
    """Host-only source root and authenticated solver-input index."""

    root: Path = field(repr=False)
    index: SolverInputIndex

    @classmethod
    def load(cls, root: Path) -> Self:
        """Load a private store without exposing its path in public records."""

        _validate_private_store_path(root, expect_directory=True)
        index_path = root / SOLVER_INPUT_INDEX_NAME
        _validate_private_store_path(index_path, expect_directory=False)
        record = read_json_object(
            index_path,
            error_factory=SolverInputError,
            missing_message=lambda _path: "solver input index does not exist",
            non_object_message=lambda _path: "solver input index must be an object",
        )
        return cls(root=root, index=SolverInputIndex.from_record(record))

    def entry_for(self, task: CanonicalTask) -> SolverInputEntry:
        """Return the exact entry bound to a canonical task."""

        matches = tuple(
            entry for entry in self.index.entries if entry.task_id == task.task_id
        )
        if len(matches) != 1:
            raise SolverInputError("solver input task entry is missing or duplicated")
        entry = matches[0]
        if entry.task_sha256 != task.task_sha256:
            raise SolverInputError("solver input task sha256 does not match")
        return entry

    def materialize(
        self,
        task: CanonicalTask,
        *,
        destination_root: Path,
    ) -> tuple[SolverInputEntry, TaskMaterializationManifest]:
        """Materialize and seal one authenticated private input tree."""

        entry = self.entry_for(task)
        visible_files = tuple(item for item in entry.files if item.solver_visible)
        artifacts = tuple(
            ArtifactRecord(
                artifact_id=f"solver_input:{index}",
                path=item.source_path,
                sha256=item.sha256,
                media_type=item.media_type,
                public=False,
                size_bytes=item.size_bytes,
            )
            for index, item in enumerate(visible_files)
        )
        materialization_task = replace(task, artifacts=artifacts)
        manifest = materialize_task(
            materialization_task,
            source_root=self.root,
            destination_root=destination_root,
            layout=TaskMaterializationLayout(
                layout_id=SOLVER_INPUT_LAYOUT_ID,
                solver_artifacts=tuple(
                    TaskArtifactProjection(
                        artifact_id=artifact.artifact_id,
                        destination_path=visible_files[index].destination_path,
                    )
                    for index, artifact in enumerate(artifacts)
                ),
            ),
        )
        _seal_materialized_tree(destination_root)
        files_by_artifact_id = {
            artifact.artifact_id: visible_files[index]
            for index, artifact in enumerate(artifacts)
        }
        observed = tuple(
            SolverInputFile(
                source_path=files_by_artifact_id[item.artifact_id].source_path,
                destination_path=item.destination_path,
                media_type=files_by_artifact_id[item.artifact_id].media_type,
                sha256=f"sha256:{item.sha256}",
                size_bytes=item.size_bytes,
                solver_visible=True,
            )
            for item in manifest.entries
        )
        if _tree_sha256(observed) != entry.tree_sha256:
            raise SolverInputError("materialized solver input tree does not match")
        return entry, manifest


def write_solver_input_store(
    *,
    destination_root: Path,
    task_index_sha256: str,
    payloads: tuple[SolverInputPayload, ...],
) -> SolverInputStore:
    """Write one fresh private store and return its authenticated view."""

    validate_sha256(task_index_sha256, "task_index_sha256")
    if not payloads:
        raise SolverInputError("solver input payloads must not be empty")
    validate_unique_ids(
        (payload.task.task_id for payload in payloads),
        "solver input task IDs",
    )
    try:
        destination_root.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        raise SolverInputError("solver input destination must be fresh") from exc
    entries: list[SolverInputEntry] = []
    for payload in sorted(payloads, key=lambda item: item.task.task_id):
        task_root = f"tasks/{hashlib.sha256(payload.task.task_id.encode()).hexdigest()}"
        prompt_sha256 = payload.task.metadata.get("prompt_sha256")
        if not isinstance(prompt_sha256, str):
            raise SolverInputError("task metadata prompt_sha256 is required")
        file_payloads = (
            (
                SOLVER_INPUT_ENTRY_PATH,
                "text/plain",
                payload.prompt.encode("utf-8"),
                True,
            ),
            (
                _SOURCE_PACKET_PATH,
                "application/json",
                _canonical_bytes(dict(payload.source_packet), trailing_newline=False),
                False,
            ),
        )
        files: list[SolverInputFile] = []
        for relative_name, media_type, encoded, solver_visible in file_payloads:
            source_path = f"{task_root}/{relative_name}"
            path = destination_root / source_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(encoded)
            path.chmod(0o400)
            files.append(
                SolverInputFile(
                    source_path=source_path,
                    destination_path=relative_name,
                    media_type=media_type,
                    sha256=_bytes_sha256(encoded),
                    size_bytes=len(encoded),
                    solver_visible=solver_visible,
                )
            )
        canonical_files = tuple(sorted(files, key=lambda item: item.destination_path))
        entries.append(
            SolverInputEntry(
                task_id=payload.task.task_id,
                task_sha256=payload.task.task_sha256,
                prompt_sha256=prompt_sha256,
                entrypoint_path=SOLVER_INPUT_ENTRY_PATH,
                files=canonical_files,
                tree_sha256=_tree_sha256(canonical_files),
            )
        )
    content = {
        "schema_version": SOLVER_INPUT_INDEX_SCHEMA_VERSION,
        "task_index_sha256": task_index_sha256,
        "entries": [entry.to_record() for entry in entries],
    }
    index = SolverInputIndex(
        task_index_sha256=task_index_sha256,
        entries=tuple(entries),
        index_sha256=_record_sha256(content),
    )
    write_json_object(destination_root / SOLVER_INPUT_INDEX_NAME, index.to_record())
    (destination_root / SOLVER_INPUT_INDEX_NAME).chmod(0o600)
    directories = tuple(path for path in destination_root.rglob("*") if path.is_dir())
    for directory in (destination_root, *directories):
        directory.chmod(0o700)
    return SolverInputStore(root=destination_root, index=index)


def _tree_sha256(files: tuple[SolverInputFile, ...]) -> str:
    return _record_sha256(
        {
            "schema_version": SOLVER_INPUT_PAYLOAD_SCHEMA_VERSION,
            "files": [
                {
                    "destination_path": item.destination_path,
                    "media_type": item.media_type,
                    "sha256": item.sha256,
                    "size_bytes": item.size_bytes,
                }
                for item in sorted(
                    (file for file in files if file.solver_visible),
                    key=lambda value: value.destination_path,
                )
            ],
        }
    )


def _seal_materialized_tree(root: Path) -> None:
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        path.chmod(0o500 if path.is_dir() else 0o400, follow_symlinks=False)
    root.chmod(0o500, follow_symlinks=False)


def _canonical_bytes(
    record: dict[str, Any],
    *,
    trailing_newline: bool = True,
) -> bytes:
    suffix = "\n" if trailing_newline else ""
    return (
        json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + suffix
    ).encode("utf-8")


def _record_sha256(record: dict[str, Any]) -> str:
    return _bytes_sha256(_canonical_bytes(record))


def _bytes_sha256(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def _normalized_sha256(value: str) -> str:
    return value.removeprefix("sha256:")


def _validate_private_store_path(path: Path, *, expect_directory: bool) -> None:
    try:
        path_stat = path.lstat()
    except OSError as exc:
        raise SolverInputError("solver input store is unavailable") from exc
    expected_type = stat.S_ISDIR if expect_directory else stat.S_ISREG
    if path.is_symlink() or not expected_type(path_stat.st_mode):
        raise SolverInputError("solver input store path is unsafe")
    if path_stat.st_uid != os.geteuid() or stat.S_IMODE(path_stat.st_mode) & 0o077:
        raise SolverInputError("solver input store permissions are not private")
