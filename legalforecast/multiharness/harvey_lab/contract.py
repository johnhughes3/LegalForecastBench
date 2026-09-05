"""Shared task-cardinality rules for the pinned Harvey LAB bridge."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

from legalforecast.multiharness.deliverables import DeliverableManifest


class HarveyLabContractError(ValueError):
    """A task or produced-output declaration is malformed."""


class HarveyLabUnsupportedOutputError(HarveyLabContractError):
    """A task declares an output kind the DOCX bridge cannot carry."""


class HarveyLabOutputSelectionError(HarveyLabContractError):
    """Produced output paths do not satisfy the task declaration."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


def expected_docx_deliverables(record: Mapping[str, object]) -> tuple[str, ...]:
    """Return sorted declared DOCX basenames; empty means score all outputs."""

    for field_name in (
        "expected_deliverable",
        "expected_output",
        "output_file",
        "deliverable",
        "output",
    ):
        value = record.get(field_name)
        if isinstance(value, str) and value.strip():
            return (_docx_basename(Path(value).name),)
    deliverables = record.get("deliverables")
    if deliverables is None:
        return ()
    if not isinstance(deliverables, Mapping):
        raise HarveyLabContractError("task.json deliverables must be an object")
    basenames: list[str] = []
    for key, value in cast(Mapping[str, object], deliverables).items():
        if not isinstance(value, str) or not value.strip():
            raise HarveyLabContractError(
                "task.json deliverables value must be a non-empty string"
            )
        if key != value:
            raise HarveyLabContractError(
                "task.json deliverables key and value disagree; "
                "refusing to guess the deliverable basename"
            )
        basenames.append(_docx_basename(Path(value).name))
    return tuple(sorted(basenames))


def private_criterion_count(task_json: bytes) -> int:
    """Read criterion cardinality from authenticated private task bytes."""

    try:
        decoded = json.loads(task_json)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HarveyLabContractError("task.json must be UTF-8 JSON") from exc
    if not isinstance(decoded, Mapping):
        raise HarveyLabContractError("task.json must be an object")
    criteria = cast(Mapping[str, object], decoded).get("criteria")
    if not isinstance(criteria, list) or not criteria:
        raise HarveyLabContractError("task.json must contain at least one criterion")
    values = cast(list[object], criteria)
    if any(not isinstance(criterion, Mapping) for criterion in values):
        raise HarveyLabContractError("task.json criteria must be objects")
    return len(values)


def validated_deliverable_sources(
    sealed_root: Path,
    manifest: DeliverableManifest,
    expected_basenames: Sequence[str],
) -> tuple[Path, ...]:
    """Resolve sealed artifacts after checking declared paths and byte digests."""

    paths = [artifact.path for artifact in manifest.artifacts]
    if expected_basenames and paths != list(expected_basenames):
        raise HarveyLabContractError(
            "sealed deliverable must contain exactly the expected basenames"
        )
    sources: list[Path] = []
    for artifact in manifest.artifacts:
        source = sealed_root / artifact.path
        try:
            payload = source.read_bytes()
        except OSError as exc:
            raise HarveyLabContractError(
                f"sealed deliverable is unreadable: {artifact.path}"
            ) from exc
        if hashlib.sha256(payload).hexdigest() != artifact.sha256.removeprefix(
            "sha256:"
        ):
            raise HarveyLabContractError(
                f"sealed deliverable hash mismatch: {artifact.path}"
            )
        sources.append(source)
    return tuple(sources)


def selected_output_paths(
    produced_paths: Sequence[str], expected_basenames: Sequence[str]
) -> tuple[str, ...]:
    """Select exact declared outputs, or every bounded output when undeclared."""

    if not expected_basenames:
        if not produced_paths:
            raise HarveyLabOutputSelectionError(
                "solver produced no deliverable", code="missing_deliverable"
            )
        return tuple(produced_paths)
    basenames = Counter(Path(path).name for path in produced_paths)
    selected: list[str] = []
    for expected in expected_basenames:
        if basenames[expected] > 1:
            raise HarveyLabOutputSelectionError(
                f"duplicate expected deliverable basename: {expected}",
                code="duplicate_basename",
            )
        if expected in produced_paths:
            selected.append(expected)
        elif basenames[expected]:
            raise HarveyLabOutputSelectionError(
                "expected deliverable basename appeared at an undeclared path",
                code="layout",
            )
        else:
            raise HarveyLabOutputSelectionError(
                f"missing required deliverable: {expected}",
                code="missing_deliverable",
            )
    return tuple(selected)


def _docx_basename(basename: str) -> str:
    if not basename.endswith(".docx"):
        raise HarveyLabUnsupportedOutputError(
            f"deliverable {basename} is not a .docx; "
            "this projection carries .docx deliverables only"
        )
    return basename
