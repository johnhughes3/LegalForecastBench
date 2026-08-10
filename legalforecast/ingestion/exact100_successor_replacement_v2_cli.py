"""Closed CLI adapter for exact-100 successor replacement v2."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, cast

from legalforecast.ingestion.canonical_json import canonical_json_bytes
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
    for name, payload in payloads.items():
        _write_immutable(output_root / _OUTPUT_NAMES[name], payload, resume=args.resume)
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
        "input_paths": state.get("input_paths"),
        "output_paths": state.get("output_paths"),
        "output_commitments": {
            **cast(Mapping[str, str], replayed.config["output_commitments"]),
            _OUTPUT_NAMES["config"]: _sha(replayed.config_bytes),
        },
    }
    if actual["state"] != _bytes(expected_state):
        raise Exact100SuccessorReplacementV2CliError(
            "completed v2 successor run card differs from replay"
        )
    return {
        "run_card": state,
        "run_card_bytes": actual["state"],
        "summary": config,
        "summary_path": target_root / _OUTPUT_NAMES["config"],
        "run_card_path": target_root / _OUTPUT_NAMES["state"],
        "selection_path": target_root / _OUTPUT_NAMES["selection"],
        "selection_records": _jsonl(
            actual["selection"], target_root / _OUTPUT_NAMES["selection"]
        ),
        "free_manifest_path": target_root / _OUTPUT_NAMES["download_manifest"],
        "free_manifest": _jsonl(
            actual["download_manifest"],
            target_root / _OUTPUT_NAMES["download_manifest"],
        ),
        "purchased_manifest": (),
        "free_clearance": _jsonl(
            actual["clearance"], target_root / _OUTPUT_NAMES["clearance"]
        ),
        "restriction_path": target_root / _OUTPUT_NAMES["restriction"],
        "restriction_records": _jsonl(
            actual["restriction"], target_root / _OUTPUT_NAMES["restriction"]
        ),
        "selected_document_keys": {
            (cast(str, row["candidate_id"]), cast(str, row["source_document_id"]))
            for row in _jsonl(
                actual["download_manifest"],
                target_root / _OUTPUT_NAMES["download_manifest"],
            )
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


def _write_immutable(path: Path, payload: bytes, *, resume: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if not resume or _read(path) != payload:
            raise Exact100SuccessorReplacementV2CliError(
                f"immutable v2 successor output differs: {path}"
            )
        return
    path.write_bytes(payload)


def _overlaps(first: Path, second: Path) -> bool:
    left, right = first.absolute(), second.absolute()
    return left == right or left in right.parents or right in left.parents


def _read(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise Exact100SuccessorReplacementV2CliError(
            f"missing regular v2 successor file: {path}"
        )
    return path.read_bytes()


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
