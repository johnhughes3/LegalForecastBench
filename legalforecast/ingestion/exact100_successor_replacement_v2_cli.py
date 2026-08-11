"""Closed CLI adapter for exact-100 successor replacement v2."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, cast

from legalforecast.ingestion.canonical_json import canonical_json_bytes
from legalforecast.ingestion.cohort_document_materializer import (
    CohortDocumentMaterializationError,
    require_materializer_artifact,
)
from legalforecast.ingestion.exact100_successor_replacement_v2 import (
    CONFIG_SCHEMA_VERSION,
    STATE_SCHEMA_VERSION,
    Exact100SuccessorReplacementV2,
    VerifiedExact100V2Base,
    project_exact100_successor_replacement_v2,
)
from legalforecast.ingestion.exact100_successor_semantic_repair import (
    VerifiedExact100SuccessorSemanticRepairs,
)
from legalforecast.ingestion.exact100_successor_wider_rank import (
    VerifiedExact100SuccessorWiderRank,
)
from legalforecast.ingestion.post_selection_terminal_exclusion import (
    VerifiedPostSelectionTerminalExclusions,
)

_OUTPUT_NAMES = {
    "selection": "target-cohort-selection.jsonl",
    "config": "target-cohort-projection.json",
    "state": "run-cards/project-target-cohort.json",
    "case_relevance": "case-relevance.jsonl",
    "download_manifest": "document-downloads-merged.jsonl",
    "clearance": "disclosure-clearance.jsonl",
    "restriction": "restriction-evidence.jsonl",
    "core_filter": "core-filter-results.jsonl",
    "terminal_exclusions": "successor-terminal-exclusions.jsonl",
    "semantic_repairs": "successor-semantic-repairs.jsonl",
    "wider_rank": "successor-wider-rank-ledger.jsonl",
    "promotions": "successor-promotions.jsonl",
}


class Exact100SuccessorReplacementV2CliError(ValueError):
    """Raised when the closed v2 replay cannot be reproduced."""


V2InputReplay = Callable[
    [argparse.Namespace],
    tuple[
        VerifiedExact100V2Base,
        VerifiedPostSelectionTerminalExclusions,
        VerifiedExact100SuccessorSemanticRepairs,
        VerifiedExact100SuccessorWiderRank,
    ],
]


def add_parser(
    subparsers: Any, *, handler: Callable[[argparse.Namespace], int]
) -> None:
    parser = subparsers.add_parser(
        "project-exact100-successor-replacement-v2",
        help="Replay the complete exact-100 and wider horizon into a v2 successor.",
        description=(
            "Provider-free v2 exact-100 successor replay. The terminal candidate, "
            "semantic repairs, wider ordering, and promotion are derived from "
            "authenticated roots; no candidate, provider, retrieval, paid, model, "
            "evaluation, freeze, or dispatch switch is exposed."
        ),
    )
    parser.add_argument("--predecessor-root", type=Path, required=True)
    parser.add_argument("--complete-materialization-root", type=Path, required=True)
    parser.add_argument("--stipulated-evidence-root", type=Path, required=True)
    parser.add_argument("--final153-snapshot", type=Path, required=True)
    parser.add_argument("--wider-plan-root", type=Path, required=True)
    parser.add_argument("--wider-exclusion-root", type=Path, required=True)
    parser.add_argument("--historical-packet-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    parser.set_defaults(handler=handler)


def run(args: argparse.Namespace) -> int:
    replay = cast(V2InputReplay | None, getattr(args, "_replay_v2_inputs", None))
    if replay is None:
        raise Exact100SuccessorReplacementV2CliError(
            "v2 successor requires authenticated integration replay"
        )
    output_root = cast(Path, args.output_root)
    _validate_output_root(output_root)
    input_roots = tuple(
        cast(Path, getattr(args, field_name))
        for field_name in (
            "predecessor_root",
            "complete_materialization_root",
            "stipulated_evidence_root",
            "final153_snapshot",
            "wider_plan_root",
            "wider_exclusion_root",
            "historical_packet_root",
        )
    )
    if any(_overlaps(output_root, root) for root in input_roots):
        raise Exact100SuccessorReplacementV2CliError(
            "v2 successor output overlaps authenticated input evidence"
        )
    first = _project(replay(args))
    second = _project(replay(args))
    first_payloads = _result_payloads(first)
    if first_payloads != _result_payloads(second):
        raise Exact100SuccessorReplacementV2CliError(
            "v2 authenticated inputs changed during replay"
        )
    config_bytes = first.config_bytes
    state = {
        **first.state,
        "stage": "project-exact100-successor-replacement-v2",
        "dry_run": False,
        "execute": True,
        "record_count": len(first.selection),
        "input_paths": [str(path.absolute()) for path in input_roots],
        "output_paths": [
            str((output_root / relative).absolute())
            for relative in _OUTPUT_NAMES.values()
        ],
        "output_commitments": {
            **cast(Mapping[str, str], first.config["output_commitments"]),
            _OUTPUT_NAMES["config"]: _sha(config_bytes),
        },
    }
    payloads = {**first_payloads, "state": _bytes(state)}
    output_root_fd = _open_output_root_fd(output_root)
    try:
        for name, payload in payloads.items():
            _write_immutable_at(
                output_root_fd,
                Path(_OUTPUT_NAMES[name]),
                payload,
                resume=args.resume,
            )
        if any(
            _read_immutable_relative(output_root_fd, Path(_OUTPUT_NAMES[name]))
            != payload
            for name, payload in payloads.items()
        ):
            raise Exact100SuccessorReplacementV2CliError(
                "v2 successor output changed during publication"
            )
        os.fsync(output_root_fd)
        _require_output_root_path_identity(output_root, output_root_fd)
    finally:
        os.close(output_root_fd)
    _validate_output_root(output_root)
    print(
        json.dumps(
            {
                "schema_version": STATE_SCHEMA_VERSION,
                "status": "completed",
                "selected_case_count": len(first.selection),
                "terminal_candidate_ids": first.state["terminal_candidate_ids"],
                "promoted_candidate_ids": first.state["promoted_candidate_ids"],
                "output_root": str(output_root.absolute()),
            },
            sort_keys=True,
        )
    )
    return 0


def verify_exact100_successor_replacement_v2_projection(
    target_root: Path, *, replay: V2InputReplay, args: argparse.Namespace
) -> dict[str, Any]:
    """Replay a completed v2 root before downstream materialization authority."""

    actual = {name: _read(target_root / path) for name, path in _OUTPUT_NAMES.items()}
    config = _object(actual["config"], target_root / _OUTPUT_NAMES["config"])
    state = _object(actual["state"], target_root / _OUTPUT_NAMES["state"])
    if (
        config.get("schema_version") != CONFIG_SCHEMA_VERSION
        or state.get("schema_version") != STATE_SCHEMA_VERSION
        or state.get("status") != "completed"
    ):
        raise Exact100SuccessorReplacementV2CliError(
            "completed v2 successor has invalid schema or status"
        )
    replayed = _project(replay(args))
    expected = _result_payloads(replayed)
    if any(actual[name] != payload for name, payload in expected.items()):
        raise Exact100SuccessorReplacementV2CliError(
            "completed v2 successor differs from authenticated replay"
        )
    expected_state = {
        **replayed.state,
        "stage": "project-exact100-successor-replacement-v2",
        "dry_run": False,
        "execute": True,
        "record_count": len(replayed.selection),
        "input_paths": [
            str(cast(Path, getattr(args, field_name)).absolute())
            for field_name in (
                "predecessor_root",
                "complete_materialization_root",
                "stipulated_evidence_root",
                "final153_snapshot",
                "wider_plan_root",
                "wider_exclusion_root",
                "historical_packet_root",
            )
        ],
        "output_paths": [
            str((target_root / relative).absolute())
            for relative in _OUTPUT_NAMES.values()
        ],
        "output_commitments": {
            **cast(Mapping[str, str], replayed.config["output_commitments"]),
            _OUTPUT_NAMES["config"]: _sha(replayed.config_bytes),
        },
    }
    if actual["state"] != _bytes(expected_state):
        raise Exact100SuccessorReplacementV2CliError(
            "completed v2 successor run card differs from replay"
        )
    manifest_path = target_root / _OUTPUT_NAMES["download_manifest"]
    manifest = _jsonl(actual["download_manifest"], manifest_path)
    if any(
        row.get("free_or_purchased") not in {"free", "purchased"} for row in manifest
    ):
        raise Exact100SuccessorReplacementV2CliError(
            "completed v2 successor manifest has invalid phase"
        )
    return {
        "run_card": state,
        "run_card_bytes": actual["state"],
        "summary": config,
        "summary_path": target_root / _OUTPUT_NAMES["config"],
        "run_card_path": target_root / _OUTPUT_NAMES["state"],
        "selection_path": target_root / _OUTPUT_NAMES["selection"],
        "selection_bytes": actual["selection"],
        "selection_records": _jsonl(
            actual["selection"], target_root / _OUTPUT_NAMES["selection"]
        ),
        "free_manifest_path": manifest_path,
        "free_manifest": tuple(
            row for row in manifest if row.get("free_or_purchased") == "free"
        ),
        "purchased_manifest": tuple(
            row for row in manifest if row.get("free_or_purchased") == "purchased"
        ),
        "case_relevance": _jsonl(
            actual["case_relevance"], target_root / _OUTPUT_NAMES["case_relevance"]
        ),
        "free_clearance": tuple(
            row
            for row in _jsonl(
                actual["clearance"], target_root / _OUTPUT_NAMES["clearance"]
            )
            if row.get("free_or_purchased") == "free"
        ),
        "purchased_clearance": tuple(
            row
            for row in _jsonl(
                actual["clearance"], target_root / _OUTPUT_NAMES["clearance"]
            )
            if row.get("free_or_purchased") == "purchased"
        ),
        "restriction_path": target_root / _OUTPUT_NAMES["restriction"],
        "restriction_records": _jsonl(
            actual["restriction"], target_root / _OUTPUT_NAMES["restriction"]
        ),
        "selected_document_keys": {
            (cast(str, row["candidate_id"]), cast(str, row["source_document_id"]))
            for row in manifest
        },
        "verified_artifact_bytes": {
            str((target_root / path).absolute()): actual[name]
            for name, path in _OUTPUT_NAMES.items()
        },
    }


def _project(
    inputs: tuple[
        VerifiedExact100V2Base,
        VerifiedPostSelectionTerminalExclusions,
        VerifiedExact100SuccessorSemanticRepairs,
        VerifiedExact100SuccessorWiderRank,
    ],
) -> Exact100SuccessorReplacementV2:
    base, terminal, repairs, wider = inputs
    return project_exact100_successor_replacement_v2(
        base=base,
        terminal_exclusions=terminal,
        semantic_repairs=repairs,
        wider_rank=wider,
    )


def _result_payloads(result: Exact100SuccessorReplacementV2) -> dict[str, bytes]:
    return {
        "selection": result.selection_bytes,
        "config": result.config_bytes,
        "case_relevance": result.case_relevance_bytes,
        "download_manifest": result.download_manifest_bytes,
        "clearance": result.disclosure_clearance_bytes,
        "restriction": result.restriction_evidence_bytes,
        "core_filter": result.core_filter_results_bytes,
        "terminal_exclusions": result.terminal_exclusions_bytes,
        "semantic_repairs": result.semantic_repairs_bytes,
        "wider_rank": result.wider_rank_ledger_bytes,
        "promotions": result.promotions_bytes,
    }


def _validate_output_root(root: Path) -> None:
    if not root.exists():
        return
    if root.is_symlink() or not root.is_dir():
        raise Exact100SuccessorReplacementV2CliError(
            "v2 successor output root must be a regular directory"
        )
    expected_files = set(_OUTPUT_NAMES.values())
    expected_directories = {"run-cards"}
    files: set[str] = set()
    directories: set[str] = set()
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise Exact100SuccessorReplacementV2CliError(
                "v2 successor output contains a non-regular path"
            )
        (files if path.is_file() else directories).add(relative)
    if files - expected_files or directories - expected_directories:
        raise Exact100SuccessorReplacementV2CliError(
            "v2 successor output root contains unexpected paths"
        )


def _open_output_root_fd(root: Path, *, create: bool = True) -> int:
    absolute = Path(os.path.abspath(root))
    nofollow = getattr(os, "O_NOFOLLOW", None)
    directory = getattr(os, "O_DIRECTORY", None)
    if nofollow is None or directory is None:
        raise Exact100SuccessorReplacementV2CliError(
            "immutable v2 successor writes require no-follow directory support"
        )
    flags = os.O_RDONLY | directory | nofollow | getattr(os, "O_CLOEXEC", 0)
    descriptor = os.open(absolute.anchor, flags)
    try:
        for component in absolute.parts[1:]:
            try:
                child = os.open(component, flags, dir_fd=descriptor)
            except FileNotFoundError:
                if not create:
                    raise Exact100SuccessorReplacementV2CliError(
                        "v2 successor output root disappeared during publication"
                    ) from None
                try:
                    os.mkdir(component, 0o700, dir_fd=descriptor)
                except FileExistsError:
                    pass
                except OSError as exc:
                    raise Exact100SuccessorReplacementV2CliError(
                        "v2 successor output root could not be created"
                    ) from exc
                try:
                    child = os.open(component, flags, dir_fd=descriptor)
                except OSError as exc:
                    raise Exact100SuccessorReplacementV2CliError(
                        "v2 successor output root could not be opened without symlinks"
                    ) from exc
            except OSError as exc:
                raise Exact100SuccessorReplacementV2CliError(
                    "v2 successor output root could not be opened without symlinks"
                ) from exc
            os.close(descriptor)
            descriptor = child
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor


def _require_output_root_path_identity(root: Path, root_fd: int) -> None:
    current_fd = _open_output_root_fd(root, create=False)
    try:
        expected = os.fstat(root_fd)
        current = os.fstat(current_fd)
        if (expected.st_dev, expected.st_ino) != (current.st_dev, current.st_ino):
            raise Exact100SuccessorReplacementV2CliError(
                "v2 successor output root changed during publication"
            )
    finally:
        os.close(current_fd)


def _open_output_parent_fd(root_fd: int, relative_parent: Path) -> int:
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    directory = getattr(os, "O_DIRECTORY", 0)
    flags = os.O_RDONLY | directory | nofollow | getattr(os, "O_CLOEXEC", 0)
    descriptor = os.dup(root_fd)
    try:
        for component in relative_parent.parts:
            if component in {"", ".", ".."}:
                raise Exact100SuccessorReplacementV2CliError(
                    "invalid relative v2 successor output path"
                )
            try:
                child = os.open(component, flags, dir_fd=descriptor)
            except FileNotFoundError:
                try:
                    os.mkdir(component, 0o700, dir_fd=descriptor)
                except FileExistsError:
                    pass
                except OSError as exc:
                    raise Exact100SuccessorReplacementV2CliError(
                        "v2 successor output path could not be created"
                    ) from exc
                try:
                    child = os.open(component, flags, dir_fd=descriptor)
                except OSError as exc:
                    raise Exact100SuccessorReplacementV2CliError(
                        "v2 successor output path could not be opened without symlinks"
                    ) from exc
            except OSError as exc:
                raise Exact100SuccessorReplacementV2CliError(
                    "v2 successor output path could not be opened without symlinks"
                ) from exc
            os.close(descriptor)
            descriptor = child
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor


def _write_immutable_at(
    root_fd: int, relative: Path, payload: bytes, *, resume: bool
) -> None:
    if relative.is_absolute() or relative.name in {"", ".", ".."}:
        raise Exact100SuccessorReplacementV2CliError(
            "invalid relative v2 successor output path"
        )
    parent_fd = _open_output_parent_fd(root_fd, relative.parent)
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    flags = (
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | nofollow | getattr(os, "O_CLOEXEC", 0)
    )
    try:
        try:
            descriptor = os.open(relative.name, flags, 0o600, dir_fd=parent_fd)
        except FileExistsError:
            existing = _read_immutable_at(parent_fd, relative.name)
            if not resume or existing != payload:
                raise Exact100SuccessorReplacementV2CliError(
                    f"immutable v2 successor output differs: {relative}"
                ) from None
            return
        try:
            with os.fdopen(descriptor, "wb", closefd=True) as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.fsync(parent_fd)
        except BaseException:
            try:
                os.unlink(relative.name, dir_fd=parent_fd)
            except FileNotFoundError:
                # Cleanup is best-effort if another actor removed the partial file.
                pass
            raise
    finally:
        os.close(parent_fd)


def _read_immutable_at(parent_fd: int, name: str) -> bytes:
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(
        name,
        os.O_RDONLY
        | nofollow
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NONBLOCK", 0),
        dir_fd=parent_fd,
    )
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise Exact100SuccessorReplacementV2CliError(
                "immutable v2 successor output is not a singly linked file"
            )
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            return stream.read()
    finally:
        os.close(descriptor)


def _read_immutable_relative(root_fd: int, relative: Path) -> bytes:
    parent_fd = _open_output_parent_fd(root_fd, relative.parent)
    try:
        return _read_immutable_at(parent_fd, relative.name)
    finally:
        os.close(parent_fd)


def _overlaps(first: Path, second: Path) -> bool:
    left, right = first.absolute(), second.absolute()
    return left == right or left in right.parents or right in left.parents


def _read(path: Path) -> bytes:
    try:
        return require_materializer_artifact(
            path, label="immutable v2 successor artifact"
        )
    except CohortDocumentMaterializationError as exc:
        raise Exact100SuccessorReplacementV2CliError(str(exc)) from exc


def _object(payload: bytes, path: Path) -> dict[str, Any]:
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Exact100SuccessorReplacementV2CliError(f"{path} is not JSON") from exc
    if not isinstance(value, dict):
        raise Exact100SuccessorReplacementV2CliError(f"{path} is not canonical JSON")
    record = cast(dict[str, Any], value)
    if _bytes(record) != payload:
        raise Exact100SuccessorReplacementV2CliError(f"{path} is not canonical JSON")
    return record


def _jsonl(payload: bytes, path: Path) -> tuple[dict[str, Any], ...]:
    rows = tuple(_object(line + b"\n", path) for line in payload.splitlines())
    if not rows or _result_jsonl(rows) != payload:
        raise Exact100SuccessorReplacementV2CliError(f"{path} is not canonical JSONL")
    return rows


def _result_jsonl(rows: tuple[dict[str, Any], ...]) -> bytes:
    return b"".join(_bytes(row) for row in rows)


def _bytes(value: object) -> bytes:
    return canonical_json_bytes(
        value,
        error_type=Exact100SuccessorReplacementV2CliError,
        error_message="v2 successor serialization failed",
    )


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()
