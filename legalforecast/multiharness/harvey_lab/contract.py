"""Shared task and deliverable validation for the pinned Harvey LAB bridge."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import cast
from xml.parsers import expat

from openpyxl.utils.cell import coordinate_to_tuple, range_boundaries

from legalforecast.multiharness.deliverables import DeliverableManifest


class HarveyLabContractError(ValueError):
    """A task or produced-output declaration is malformed."""


class HarveyLabUnsupportedOutputError(HarveyLabContractError):
    """A task declares an output kind the bridge cannot carry."""


class HarveyLabOutputSelectionError(HarveyLabContractError):
    """Produced output paths do not satisfy the task declaration."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


_XLSX_NAMESPACE_SEPARATOR = "|"
_SPREADSHEET_NAMESPACE = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def preflight_xlsx_package(
    payload: bytes,
    *,
    max_members: int,
    max_part_bytes: int,
    max_package_bytes: int,
    max_cell_slots: int,
) -> None:
    """Bound expansion and validate worksheet dimensions before openpyxl."""

    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            members = archive.infolist()
            if len(members) > max_members:
                raise HarveyLabContractError(
                    "deliverable contains too many package members"
                )
            names = [member.filename for member in members]
            if len(set(names)) != len(names):
                raise HarveyLabContractError(
                    "deliverable has duplicate package members"
                )
            declared_total = 0
            for member in members:
                if member.file_size > max_part_bytes:
                    raise HarveyLabContractError(
                        "deliverable package part is too large"
                    )
                declared_total += member.file_size
                if declared_total > max_package_bytes:
                    raise HarveyLabContractError("deliverable package is too large")

            streamed_total = 0
            worksheet_parts = 0
            worksheet_slots = 0
            for member in members:
                if member.is_dir():
                    continue
                part = bytearray()
                part_size = 0
                keep = _is_worksheet_part(member.filename)
                with archive.open(member) as handle:
                    while chunk := handle.read(64 * 1024):
                        part_size += len(chunk)
                        streamed_total += len(chunk)
                        if part_size > max_part_bytes:
                            raise HarveyLabContractError(
                                "deliverable package part is too large"
                            )
                        if streamed_total > max_package_bytes:
                            raise HarveyLabContractError(
                                "deliverable package is too large"
                            )
                        if keep:
                            part.extend(chunk)
                if keep:
                    worksheet_parts += 1
                    worksheet_slots += _validate_worksheet_dimension(
                        bytes(part), max_cell_slots=max_cell_slots - worksheet_slots
                    )
            if worksheet_parts == 0:
                raise HarveyLabContractError(
                    "deliverable contains no SpreadsheetML worksheet parts"
                )
    except HarveyLabContractError:
        raise
    except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
        raise HarveyLabContractError(
            "deliverable is not a readable SpreadsheetML package"
        ) from exc


def _is_worksheet_part(name: str) -> bool:
    path = PurePosixPath(name)
    return (
        len(path.parts) == 3
        and path.parts[:2] == ("xl", "worksheets")
        and path.suffix == ".xml"
    )


def _validate_worksheet_dimension(payload: bytes, *, max_cell_slots: int) -> int:
    """Refuse worksheet metadata that could make read-only parsing truncate."""

    dimension: tuple[int, int, int, int] | None = None
    dimension_slots = 0
    cell_count = 0
    min_row: int | None = None
    max_row = 0
    min_column: int | None = None
    max_column = 0
    parser = expat.ParserCreate(namespace_separator=_XLSX_NAMESPACE_SEPARATOR)
    parser.StartDoctypeDeclHandler = _refuse_xlsx_doctype
    parser.EntityDeclHandler = _refuse_xlsx_entity
    parser.ExternalEntityRefHandler = _refuse_xlsx_external_entity
    prefix = f"{_SPREADSHEET_NAMESPACE}{_XLSX_NAMESPACE_SEPARATOR}"

    def start(name: str, attributes: dict[str, str]) -> None:
        nonlocal dimension, dimension_slots
        nonlocal cell_count, min_row, max_row, min_column, max_column
        if name == f"{prefix}dimension":
            if dimension is not None or "ref" not in attributes:
                raise HarveyLabContractError(
                    "deliverable worksheet has invalid dimension metadata"
                )
            try:
                bounds = range_boundaries(attributes["ref"])
            except (TypeError, ValueError) as exc:
                raise HarveyLabContractError(
                    "deliverable worksheet has invalid dimension metadata"
                ) from exc
            if not all(isinstance(value, int) for value in bounds):
                raise HarveyLabContractError(
                    "deliverable worksheet has invalid dimension metadata"
                )
            min_col_bound = cast(int, bounds[0])
            min_row_bound = cast(int, bounds[1])
            max_col_bound = cast(int, bounds[2])
            max_row_bound = cast(int, bounds[3])
            dimension = (
                min_col_bound,
                min_row_bound,
                max_col_bound,
                max_row_bound,
            )
            dimension_slots = (max_col_bound - min_col_bound + 1) * (
                max_row_bound - min_row_bound + 1
            )
            if dimension_slots > max_cell_slots:
                raise HarveyLabContractError("deliverable contains too many cell slots")
        elif name == f"{prefix}c":
            reference = attributes.get("r")
            if reference is None:
                raise HarveyLabContractError(
                    "deliverable worksheet cell has no coordinate"
                )
            try:
                row, column = coordinate_to_tuple(reference)
            except (TypeError, ValueError) as exc:
                raise HarveyLabContractError(
                    "deliverable worksheet cell has an invalid coordinate"
                ) from exc
            cell_count += 1
            if cell_count > max_cell_slots:
                raise HarveyLabContractError("deliverable contains too many cell slots")
            min_row = row if min_row is None else min(min_row, row)
            max_row = max(max_row, row)
            min_column = column if min_column is None else min(min_column, column)
            max_column = max(max_column, column)

    parser.StartElementHandler = start
    try:
        parser.Parse(payload, True)
    except expat.ExpatError as exc:
        raise HarveyLabContractError(
            "deliverable worksheet part is not well-formed XML"
        ) from exc
    if cell_count:
        if dimension is None or min_row is None or min_column is None:
            raise HarveyLabContractError(
                "deliverable worksheet omits populated dimension metadata"
            )
        min_col_bound, min_row_bound, max_col_bound, max_row_bound = dimension
        if (
            min_column < min_col_bound
            or min_row < min_row_bound
            or max_column > max_col_bound
            or max_row > max_row_bound
        ):
            raise HarveyLabContractError(
                "deliverable worksheet dimension under-reports populated cells"
            )
    return dimension_slots


def _refuse_xlsx_doctype(*_args: object, **_kwargs: object) -> None:
    raise HarveyLabContractError("deliverable worksheet part declares a DTD")


def _refuse_xlsx_entity(*_args: object, **_kwargs: object) -> None:
    raise HarveyLabContractError("deliverable worksheet part declares an entity")


def _refuse_xlsx_external_entity(*_args: object, **_kwargs: object) -> int:
    raise HarveyLabContractError("deliverable worksheet uses an external entity")


def expected_supported_deliverables(record: Mapping[str, object]) -> tuple[str, ...]:
    """Return sorted declared OOXML basenames; empty means score all outputs."""

    for field_name in (
        "expected_deliverable",
        "expected_output",
        "output_file",
        "deliverable",
        "output",
    ):
        value = record.get(field_name)
        if isinstance(value, str) and value.strip():
            return (_supported_basename(Path(value).name),)
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
        basenames.append(_supported_basename(Path(value).name))
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


def _supported_basename(basename: str) -> str:
    if not basename.endswith((".docx", ".xlsx")):
        raise HarveyLabUnsupportedOutputError(
            f"deliverable {basename} is not a supported deliverable; "
            "this projection carries .docx and .xlsx outputs only"
        )
    return basename
