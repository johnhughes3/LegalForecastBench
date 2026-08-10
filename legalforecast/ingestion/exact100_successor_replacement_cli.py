"""Closed CLI and materializer adapter for exact-100 successor replacement."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any, cast

from legalforecast.contracts import EXACT100_ZERO_COST_RECOVERY_PLAN_V1
from legalforecast.ingestion.canonical_json import canonical_json_bytes
from legalforecast.ingestion.exact100_successor_replacement import (
    CONFIG_SCHEMA_VERSION,
    STATE_SCHEMA_VERSION,
    VerifiedExact100Predecessor,
    VerifiedSuccessorPromotionPool,
    project_exact100_successor_replacement,
)
from legalforecast.ingestion.post_selection_terminal_exclusion import (
    VerifiedTerminalExclusionEvidence,
    authorize_persisted_terminal_recovery_evidence,
    verify_post_selection_terminal_exclusions,
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
    "promotions": "successor-promotions.jsonl",
}
_RECOVERY_FILES = {
    "request": "recovery-request.json",
    "receipt": "recovery-receipt.json",
    "run_card": "recovery-run-card.json",
    "rest_observation": "rest-observation.json",
    "rest_observation_transcript": "rest-observation-transcript.jsonl",
    "rest_observation_response": "rest-observation-response.bin",
}
_STIPULATED_AUDIT_FILES = {
    "audit": "target-document-eligibility-audit.jsonl",
    "run_card": "run-cards/audit-stage-a-target-eligibility.json",
}


class Exact100SuccessorReplacementCliError(ValueError):
    """Raised when the CLI root cannot reproduce a closed successor."""


SuccessorInputReplay = Callable[
    [Path], tuple[VerifiedExact100Predecessor, VerifiedSuccessorPromotionPool]
]
TerminalRecoveryReplay = Callable[[bytes, bytes], VerifiedTerminalExclusionEvidence]
StipulatedEligibilityReplay = Callable[[Path, bytes], VerifiedTerminalExclusionEvidence]


def add_parser(
    subparsers: Any, *, handler: Callable[[argparse.Namespace], int]
) -> None:
    parser = subparsers.add_parser(
        "project-exact100-successor-replacement",
        help="Replay sealed inputs and terminal evidence into an exact-100 successor.",
        description=(
            "Provider-free exact-100 successor projection. Candidate removals and "
            "promotions are derived from sealed evidence roots; it exposes no "
            "provider, retrieval, paid, evaluation, freeze, or dispatch action."
        ),
    )
    parser.add_argument("--predecessor-root", type=Path, required=True)
    parser.add_argument(
        "--stipulated-evidence-root", type=Path, action="append", default=[]
    )
    parser.add_argument(
        "--recovery-evidence-root", type=Path, action="append", default=[]
    )
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    parser.set_defaults(handler=handler)


def run(args: argparse.Namespace) -> int:
    predecessor_root = cast(Path, args.predecessor_root)
    replay_inputs = cast(
        SuccessorInputReplay | None, getattr(args, "_replay_inputs", None)
    )
    if replay_inputs is None:
        raise Exact100SuccessorReplacementCliError(
            "exact100 successor inputs require authenticated predecessor replay"
        )
    stipulated_roots = tuple(cast(list[Path], args.stipulated_evidence_root))
    recovery_roots = tuple(cast(list[Path], args.recovery_evidence_root))
    stipulated_replay = cast(
        StipulatedEligibilityReplay | None,
        getattr(args, "_replay_stipulated_eligibility", None),
    )
    if stipulated_roots and stipulated_replay is None:
        raise Exact100SuccessorReplacementCliError(
            "exact100 successor stipulated exclusions require authenticated "
            "eligibility-audit replay"
        )
    recovery_replay = cast(
        TerminalRecoveryReplay | None, getattr(args, "_replay_terminal_recovery", None)
    )
    if recovery_roots and recovery_replay is None:
        raise Exact100SuccessorReplacementCliError(
            "exact100 successor recovery requires fresh producer replay"
        )
    output_root = cast(Path, args.output_root)
    _validate_output_root(output_root)
    result, payloads = _build(
        predecessor_root=predecessor_root,
        replay_inputs=replay_inputs,
        recovery_replay=recovery_replay,
        stipulated_replay=stipulated_replay,
        stipulated_roots=stipulated_roots,
        recovery_roots=recovery_roots,
        output_root=output_root,
    )
    for name, payload in payloads.items():
        _write_immutable(output_root / _OUTPUT_NAMES[name], payload, resume=args.resume)
    print(
        json.dumps(
            {
                "output_root": str(output_root),
                "selected_case_count": len(result.selection),
                "terminal_exclusion_count": len(result.terminal_exclusions),
                "promoted_candidate_ids": result.config["promoted_candidate_ids"],
                "provider_activity_requested": False,
                "paid_activity_requested": False,
                "paid_activity_executed": False,
                "evaluation_authorized": False,
                "freeze_authorized": False,
                "dispatch_authorized": False,
            },
            sort_keys=True,
        )
    )
    return 0


def verify_materializer_projection(
    *,
    target_root: Path,
    free_clearance_path: Path,
    expected_target_count: int,
    replay_inputs: SuccessorInputReplay,
    recovery_replay: TerminalRecoveryReplay | None,
    stipulated_replay: StipulatedEligibilityReplay | None,
) -> dict[str, object]:
    """Replay the saved command and return the normal materializer projection."""

    _validate_output_root(target_root)
    state_path = target_root / _OUTPUT_NAMES["state"]
    state_bytes = _read(state_path)
    state = _object(state_bytes, state_path)
    _verify_state(
        state, target_root=target_root, expected_target_count=expected_target_count
    )
    inputs = tuple(Path(value) for value in cast(list[str], state["input_paths"]))
    stipulated_count = cast(int, state["stipulated_evidence_root_count"])
    recovery_count = cast(int, state["recovery_evidence_root_count"])
    predecessor_root = inputs[0]
    stipulated_roots = inputs[1 : 1 + stipulated_count]
    recovery_roots = inputs[
        1 + stipulated_count : 1 + stipulated_count + recovery_count
    ]
    with redirect_stdout(StringIO()):
        _result, expected = _build(
            predecessor_root=predecessor_root,
            replay_inputs=replay_inputs,
            recovery_replay=recovery_replay,
            stipulated_replay=stipulated_replay,
            stipulated_roots=stipulated_roots,
            recovery_roots=recovery_roots,
            output_root=target_root,
        )
    actual = {
        name: _read(target_root / relative) for name, relative in _OUTPUT_NAMES.items()
    }
    if actual != expected:
        raise Exact100SuccessorReplacementCliError(
            "exact100 successor output changed after replay"
        )
    config = _object(actual["config"], target_root / _OUTPUT_NAMES["config"])
    _verify_config(
        config,
        state=state,
        payloads=actual,
        expected_target_count=expected_target_count,
    )
    if (
        free_clearance_path.absolute()
        != (target_root / _OUTPUT_NAMES["clearance"]).absolute()
    ):
        raise Exact100SuccessorReplacementCliError(
            "free clearance must be the exact successor projection output"
        )
    selection = _jsonl(actual["selection"], target_root / _OUTPUT_NAMES["selection"])
    if len(selection) != expected_target_count:
        raise Exact100SuccessorReplacementCliError(
            "exact100 successor selection count differs"
        )
    selected_document_keys = _selected_document_keys(selection)
    manifest = _jsonl(
        actual["download_manifest"], target_root / _OUTPUT_NAMES["download_manifest"]
    )
    if any(_key(row) not in selected_document_keys for row in manifest):
        raise Exact100SuccessorReplacementCliError(
            "successor manifest is outside selection"
        )
    if any(
        row.get("free_or_purchased") not in {"free", "purchased"} for row in manifest
    ):
        raise Exact100SuccessorReplacementCliError(
            "successor manifest has invalid phase"
        )
    return {
        "run_card": state,
        "run_card_bytes": state_bytes,
        "summary": config,
        "summary_path": target_root / _OUTPUT_NAMES["config"],
        "run_card_path": state_path,
        "selection_path": target_root / _OUTPUT_NAMES["selection"],
        "selection_records": selection,
        "free_manifest_path": target_root / _OUTPUT_NAMES["download_manifest"],
        "free_manifest": tuple(
            row for row in manifest if row.get("free_or_purchased") == "free"
        ),
        "purchased_manifest": tuple(
            row for row in manifest if row.get("free_or_purchased") == "purchased"
        ),
        "free_clearance": _jsonl(
            actual["clearance"], target_root / _OUTPUT_NAMES["clearance"]
        ),
        "restriction_path": target_root / _OUTPUT_NAMES["restriction"],
        "restriction_records": _jsonl(
            actual["restriction"], target_root / _OUTPUT_NAMES["restriction"]
        ),
        "selected_document_keys": selected_document_keys,
        "verified_artifact_bytes": {
            str((target_root / relative).absolute()): payload
            for name, relative in _OUTPUT_NAMES.items()
            for payload in (actual[name],)
        },
    }


def _build(
    *,
    predecessor_root: Path,
    replay_inputs: SuccessorInputReplay,
    recovery_replay: TerminalRecoveryReplay | None,
    stipulated_replay: StipulatedEligibilityReplay | None,
    stipulated_roots: Sequence[Path],
    recovery_roots: Sequence[Path],
    output_root: Path,
) -> tuple[Any, dict[str, bytes]]:
    if not stipulated_roots and not recovery_roots:
        raise Exact100SuccessorReplacementCliError(
            "at least one terminal evidence root is required"
        )
    if _overlaps(output_root, predecessor_root) or any(
        _overlaps(output_root, root) for root in (*stipulated_roots, *recovery_roots)
    ):
        raise Exact100SuccessorReplacementCliError(
            "successor output overlaps authenticated input evidence"
        )
    predecessor, promotion_pool = replay_inputs(predecessor_root)
    snapshots: dict[Path, bytes] = {}
    evidence = [
        _recovery(
            root,
            predecessor.selection_bytes,
            snapshots,
            recovery_replay=recovery_replay,
        )
        for root in recovery_roots
    ]
    evidence.extend(
        _stipulated(
            root,
            predecessor.selection_bytes,
            snapshots,
            stipulated_replay=stipulated_replay,
        )
        for root in stipulated_roots
    )
    terminals = verify_post_selection_terminal_exclusions(
        selection_bytes=predecessor.selection_bytes, evidence=evidence
    )
    result = project_exact100_successor_replacement(
        predecessor=predecessor,
        terminal_exclusions=terminals,
        promotion_pool=promotion_pool,
    )
    _check_snapshots(snapshots)
    # A second sealed-root replay closes the TOCTOU interval around the mint.
    second_predecessor, second_promotion_pool = replay_inputs(predecessor_root)
    second_evidence = [
        *(
            _recovery(
                root,
                second_predecessor.selection_bytes,
                snapshots,
                recovery_replay=recovery_replay,
            )
            for root in recovery_roots
        ),
        *(
            _stipulated(
                root,
                second_predecessor.selection_bytes,
                snapshots,
                stipulated_replay=stipulated_replay,
            )
            for root in stipulated_roots
        ),
    ]
    second_terminals = verify_post_selection_terminal_exclusions(
        selection_bytes=second_predecessor.selection_bytes, evidence=second_evidence
    )
    if terminals.records_bytes != second_terminals.records_bytes:
        raise Exact100SuccessorReplacementCliError(
            "terminal exclusion evidence changed during replay"
        )
    second_result = project_exact100_successor_replacement(
        predecessor=second_predecessor,
        terminal_exclusions=second_terminals,
        promotion_pool=second_promotion_pool,
    )
    if _result_payloads(result) != _result_payloads(second_result):
        raise Exact100SuccessorReplacementCliError(
            "sealed successor inputs changed during replay"
        )
    _check_snapshots(snapshots)
    config_bytes = result.config_bytes
    state = {
        **result.state,
        "stage": "project-exact100-successor-replacement",
        "dry_run": False,
        "execute": True,
        "record_count": len(result.selection),
        "input_paths": [
            str(path.absolute())
            for path in (predecessor_root, *stipulated_roots, *recovery_roots)
        ],
        "stipulated_evidence_root_count": len(stipulated_roots),
        "recovery_evidence_root_count": len(recovery_roots),
        "output_paths": [
            str((output_root / relative).absolute())
            for relative in _OUTPUT_NAMES.values()
        ],
        "output_commitments": {
            **cast(Mapping[str, str], result.config["output_commitments"]),
            "target-cohort-projection.json": _sha(config_bytes),
        },
    }
    return result, {
        "selection": result.selection_bytes,
        "config": config_bytes,
        "case_relevance": result.case_relevance_bytes,
        "download_manifest": result.download_manifest_bytes,
        "clearance": result.disclosure_clearance_bytes,
        "restriction": result.restriction_evidence_bytes,
        "core_filter": result.core_filter_results_bytes,
        "terminal_exclusions": result.terminal_exclusions_bytes,
        "promotions": result.promotions_bytes,
        "state": _bytes(state),
    }


def _recovery(
    root: Path,
    selection: bytes,
    snapshots: dict[Path, bytes],
    *,
    recovery_replay: TerminalRecoveryReplay | None,
) -> VerifiedTerminalExclusionEvidence:
    if recovery_replay is None:
        raise Exact100SuccessorReplacementCliError(
            "exact100 successor recovery requires fresh producer replay"
        )
    payloads = _root_payloads(root, _RECOVERY_FILES, snapshots)
    request = _object(payloads["request"], root / _RECOVERY_FILES["request"])
    candidate_id = request.get("candidate_id")
    source_document_id = request.get("source_document_id")
    if not isinstance(candidate_id, str) or not isinstance(source_document_id, str):
        raise Exact100SuccessorReplacementCliError(
            "persisted recovery request lacks the fixed candidate and document"
        )
    plan_bytes = _bytes(
        {
            "schema_version": str(EXACT100_ZERO_COST_RECOVERY_PLAN_V1),
            "selection_sha256": _sha(selection),
            "records": [
                {
                    "candidate_id": candidate_id,
                    "source_document_id": source_document_id,
                }
            ],
        }
    )
    try:
        live_evidence = recovery_replay(selection, plan_bytes)
    except ValueError as exc:
        raise Exact100SuccessorReplacementCliError(
            "fresh terminal recovery replay did not authorize the persisted root"
        ) from exc
    return authorize_persisted_terminal_recovery_evidence(
        live_evidence=live_evidence,
        selection_bytes=selection,
        request=request,
        request_bytes=payloads["request"],
        receipt=_object(payloads["receipt"], root / _RECOVERY_FILES["receipt"]),
        receipt_bytes=payloads["receipt"],
        run_card=_object(payloads["run_card"], root / _RECOVERY_FILES["run_card"]),
        run_card_bytes=payloads["run_card"],
        rest_observation=_object(
            payloads["rest_observation"], root / _RECOVERY_FILES["rest_observation"]
        ),
        rest_observation_bytes=payloads["rest_observation"],
        rest_observation_transcript_bytes=payloads["rest_observation_transcript"],
        rest_observation_response_bytes=payloads["rest_observation_response"],
    )


def _stipulated(
    root: Path,
    selection: bytes,
    snapshots: dict[Path, bytes],
    *,
    stipulated_replay: StipulatedEligibilityReplay | None,
) -> VerifiedTerminalExclusionEvidence:
    """Mint one stipulated exclusion only from an authenticated audit replay."""

    if stipulated_replay is None:
        raise Exact100SuccessorReplacementCliError(
            "exact100 successor stipulated exclusions require authenticated "
            "eligibility-audit replay"
        )
    _root_payloads(root, _STIPULATED_AUDIT_FILES, snapshots)
    try:
        return stipulated_replay(root, selection)
    except ValueError as exc:
        raise Exact100SuccessorReplacementCliError(
            "authenticated stipulated eligibility replay did not authorize the "
            "persisted root"
        ) from exc


def _root_payloads(
    root: Path, names: Mapping[str, str], snapshots: dict[Path, bytes]
) -> dict[str, bytes]:
    payloads = {name: _read(root / filename) for name, filename in names.items()}
    for name, payload in payloads.items():
        path = root / names[name]
        previous = snapshots.setdefault(path, payload)
        if previous != payload:
            raise Exact100SuccessorReplacementCliError(
                "persisted terminal evidence changed during replay"
            )
    return payloads


def _verify_state(
    state: Mapping[str, Any], *, target_root: Path, expected_target_count: int
) -> None:
    required = {
        "schema_version",
        "status",
        "target_case_count",
        "predecessor_case_count",
        "retained_case_count",
        "terminal_exclusion_count",
        "promotion_count",
        "selected_case_count",
        "terminal_candidate_ids",
        "promoted_candidate_ids",
        "config_sha256",
        "provider_activity_requested",
        "provider_activity_executed",
        "paid_activity_requested",
        "paid_activity_executed",
        "evaluation_authorized",
        "freeze_authorized",
        "dispatch_authorized",
        "stage",
        "dry_run",
        "execute",
        "record_count",
        "input_paths",
        "stipulated_evidence_root_count",
        "recovery_evidence_root_count",
        "output_paths",
        "output_commitments",
    }
    expected_paths = {
        str((target_root / relative).absolute()) for relative in _OUTPUT_NAMES.values()
    }
    if (
        set(state) != required
        or state.get("schema_version") != STATE_SCHEMA_VERSION
        or state.get("status") != "completed"
        or state.get("stage") != "project-exact100-successor-replacement"
        or state.get("target_case_count") != expected_target_count
        or state.get("selected_case_count") != expected_target_count
        or state.get("record_count") != expected_target_count
        or state.get("dry_run") is not False
        or state.get("execute") is not True
        or any(
            state.get(name) is not False
            for name in (
                "provider_activity_requested",
                "provider_activity_executed",
                "paid_activity_requested",
                "paid_activity_executed",
                "evaluation_authorized",
                "freeze_authorized",
                "dispatch_authorized",
            )
        )
        or not isinstance(state.get("input_paths"), list)
        or any(
            not isinstance(value, str) or not value
            for value in cast(list[object], state["input_paths"])
        )
        or type(state.get("stipulated_evidence_root_count")) is not int
        or cast(int, state["stipulated_evidence_root_count"]) < 0
        or type(state.get("recovery_evidence_root_count")) is not int
        or cast(int, state["recovery_evidence_root_count"]) < 0
        or len(cast(list[object], state["input_paths"]))
        != 1
        + cast(int, state["stipulated_evidence_root_count"])
        + cast(int, state["recovery_evidence_root_count"])
        or not isinstance(state.get("output_paths"), list)
        or any(
            not isinstance(value, str) or not value
            for value in cast(list[object], state["output_paths"])
        )
        or set(cast(list[str], state["output_paths"])) != expected_paths
    ):
        raise Exact100SuccessorReplacementCliError(
            "invalid completed exact100 successor run card"
        )


def _verify_config(
    config: Mapping[str, Any],
    *,
    state: Mapping[str, Any],
    payloads: Mapping[str, bytes],
    expected_target_count: int,
) -> None:
    required = {
        "schema_version",
        "target_case_count",
        "predecessor_schema_version",
        "terminal_exclusion_count",
        "promoted_candidate_ids",
        "source_commitments",
        "output_commitments",
        "provider_activity_permitted",
        "paid_activity_permitted",
        "evaluation_authorized",
        "freeze_authorized",
        "dispatch_authorized",
    }
    commitments = config.get("output_commitments")
    expected_commitments = {
        _OUTPUT_NAMES[name]: _sha(payloads[name])
        for name in (
            "selection",
            "case_relevance",
            "download_manifest",
            "clearance",
            "restriction",
            "core_filter",
            "terminal_exclusions",
            "promotions",
        )
    }
    state_commitments = state.get("output_commitments")
    expected_state_commitments = {
        **expected_commitments,
        _OUTPUT_NAMES["config"]: _sha(payloads["config"]),
    }
    commitment_records = cast(Mapping[str, object], commitments)
    state_commitment_records = cast(Mapping[str, object], state_commitments)
    if (
        set(config) != required
        or config.get("schema_version") != CONFIG_SCHEMA_VERSION
        or config.get("target_case_count") != expected_target_count
        or config.get("terminal_exclusion_count")
        != state.get("terminal_exclusion_count")
        or config.get("promoted_candidate_ids") != state.get("promoted_candidate_ids")
        or any(
            config.get(name) is not False
            for name in (
                "provider_activity_permitted",
                "paid_activity_permitted",
                "evaluation_authorized",
                "freeze_authorized",
                "dispatch_authorized",
            )
        )
        or not isinstance(commitments, Mapping)
        or dict(commitment_records) != expected_commitments
        or state.get("config_sha256") != _sha(payloads["config"])
        or not isinstance(state_commitments, Mapping)
        or dict(state_commitment_records) != expected_state_commitments
    ):
        raise Exact100SuccessorReplacementCliError("invalid exact100 successor config")


def _result_payloads(result: Any) -> dict[str, bytes]:
    """Return the deterministic closed projection surface used for TOCTOU checks."""

    return {
        "selection": result.selection_bytes,
        "config": result.config_bytes,
        "case_relevance": result.case_relevance_bytes,
        "download_manifest": result.download_manifest_bytes,
        "clearance": result.disclosure_clearance_bytes,
        "restriction": result.restriction_evidence_bytes,
        "core_filter": result.core_filter_results_bytes,
        "terminal_exclusions": result.terminal_exclusions_bytes,
        "promotions": result.promotions_bytes,
    }


def _selected_document_keys(rows: Sequence[Mapping[str, Any]]) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    candidates: set[str] = set()
    for row in rows:
        candidate = _text(row, "candidate_id")
        if candidate in candidates or not isinstance(row.get("documents"), list):
            raise Exact100SuccessorReplacementCliError("successor selection is invalid")
        candidates.add(candidate)
        for raw in cast(list[object], row["documents"]):
            if not isinstance(raw, Mapping):
                raise Exact100SuccessorReplacementCliError(
                    "successor document is invalid"
                )
            key = (candidate, _text(cast(Mapping[str, Any], raw), "source_document_id"))
            if key in keys:
                raise Exact100SuccessorReplacementCliError(
                    "successor selection document repeats"
                )
            keys.add(key)
    return keys


def _key(row: Mapping[str, Any]) -> tuple[str, str]:
    return (_text(row, "candidate_id"), _text(row, "source_document_id"))


def _text(row: Mapping[str, Any], field: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value:
        raise Exact100SuccessorReplacementCliError(f"record lacks {field}")
    return value


def _bytes(value: object) -> bytes:
    return canonical_json_bytes(
        value,
        error_type=Exact100SuccessorReplacementCliError,
        error_message="successor serialization failed",
    )


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _object(payload: bytes, path: Path) -> dict[str, Any]:
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Exact100SuccessorReplacementCliError(f"{path} is not JSON") from exc
    if not isinstance(value, dict):
        raise Exact100SuccessorReplacementCliError(f"{path} is not canonical JSON")
    record = cast(dict[str, Any], value)
    if _bytes(record) != payload:
        raise Exact100SuccessorReplacementCliError(f"{path} is not canonical JSON")
    return record


def _jsonl(payload: bytes, path: Path) -> tuple[dict[str, Any], ...]:
    rows = tuple(_object(line + b"\n", path) for line in payload.splitlines())
    if (
        not rows
        or b"\n".join(_bytes(row).rstrip(b"\n") for row in rows) + b"\n" != payload
    ):
        raise Exact100SuccessorReplacementCliError(f"{path} is not canonical JSONL")
    return rows


def _read(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise Exact100SuccessorReplacementCliError(
            f"missing regular evidence file: {path}"
        )
    return path.read_bytes()


def _check_snapshots(snapshots: Mapping[Path, bytes]) -> None:
    if any(_read(path) != payload for path, payload in snapshots.items()):
        raise Exact100SuccessorReplacementCliError(
            "terminal evidence changed during replay"
        )


def _write_immutable(path: Path, payload: bytes, *, resume: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if not resume or _read(path) != payload:
            raise Exact100SuccessorReplacementCliError(
                f"immutable successor output differs: {path}"
            )
        return
    path.write_bytes(payload)


def _validate_output_root(root: Path) -> None:
    """Keep replay output closed so stray files cannot alter materializer inputs."""

    if not root.exists():
        return
    if root.is_symlink() or not root.is_dir():
        raise Exact100SuccessorReplacementCliError(
            "successor output root must be a regular directory"
        )
    expected_files = set(_OUTPUT_NAMES.values())
    expected_directories = {"run-cards"}
    files: set[str] = set()
    directories: set[str] = set()
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise Exact100SuccessorReplacementCliError(
                "successor output contains a non-regular path"
            )
        if path.is_file():
            files.add(relative)
        else:
            directories.add(relative)
    if files - expected_files or directories - expected_directories:
        raise Exact100SuccessorReplacementCliError(
            "successor output root contains unexpected paths"
        )


def _overlaps(left: Path, right: Path) -> bool:
    a, b = left.resolve(), right.resolve()
    return a == b or a in b.parents or b in a.parents
