"""Rebuildable discovery index for authenticated acquisition-cycle lineages."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from legalforecast.ingestion.canonical_json import canonical_json_value_bytes
from legalforecast.ingestion.cycle_manifest_template import (
    authenticate_stage_outputs,
    reject_stale_stage_head,
)
from legalforecast.ingestion.cycle_orchestrator import (
    COMMAND_BOUNDARIES,
    COMMAND_RUN_CARD_STAGES,
    AcquisitionBoundary,
    BoundaryPermissions,
    CycleOrchestratorError,
    load_cycle_config,
    run_acquisition_cycle,
)
from legalforecast.ingestion.disclosure_review_bundle import (
    ReviewBundleError,
    canonical_json_bytes,
    read_unique_regular_file,
)

INDEX_SCHEMA_VERSION = "legalforecast.cycle_lineage_index.v1"
STATUS_SCHEMA_VERSION = "legalforecast.cycle_lineage_status.v1"
INDEX_ENVIRONMENT_VARIABLE = "LEGALFORECAST_CYCLE_LINEAGE_INDEX"

_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_INDEX_FIELDS = {"schema_version", "entries", "stage_heads"}
_ENTRY_FIELDS = {
    "cycle_id",
    "config_path",
    "state_root",
    "config_sha256",
    "code_commit",
    "supersedes_config_sha256",
    "root_identity_sha256",
}
_STAGE_HEAD_FIELDS = {
    "cycle_id",
    "command",
    "stage",
    "run_card_path",
    "run_card_sha256",
    "root_identity_sha256",
    "code_commit",
    "supersedes_root_identity_sha256",
}
_APPROVAL_RUN_CARD_SCHEMAS = {
    "legalforecast.purchase_approval_run_card.v1",
    "legalforecast.replacement_purchase_approval_run_card.v1",
    "legalforecast.replacement_purchase_approval_run_card.v2",
}
_APPROVAL_BODY_FIELDS = {
    "stage",
    "status",
    "decision",
    "request_sha256",
    "checkpoint_sha256",
    "reviewer_id",
    "recorded_at_utc",
    "provider_activity_requested",
    "provider_activity_executed",
    "pacer_fee_acknowledged",
    "paid_activity_requested",
    "paid_activity_executed",
}


class CycleLineageIndexError(ValueError):
    """Raised when advisory lineage discovery cannot produce one verified head."""


def register_cycle_lineage(
    *,
    index_path: Path,
    config_path: Path,
    state_root: Path,
    code_commit: str,
    supersedes_config_sha256: str | None = None,
) -> dict[str, object]:
    """Verify and atomically register one candidate lineage.

    The index only locates candidates. Every registration and lookup replays the
    acquisition coordinator's receipt authentication; the index grants no
    purchase, evaluation, freeze, dispatch, or publication authority.
    """

    commit = _require_digest(code_commit, "code commit", pattern=_SHA40)
    config = _verified_config_path(config_path)
    state = _verified_state_root(state_root)
    try:
        status = _cycle_status(config, state)
    except CycleOrchestratorError as exc:
        raise CycleLineageIndexError(str(exc)) from exc
    config_sha256 = _required_string(status, "config_sha256")
    cycle_id = _required_string(status, "cycle_id")
    supersedes = (
        None
        if supersedes_config_sha256 is None
        else _require_digest(
            supersedes_config_sha256,
            "superseded config SHA-256",
            pattern=_SHA256,
        )
    )
    entries, stage_heads = _load_index(index_path, missing_ok=True)
    if supersedes == config_sha256:
        raise CycleLineageIndexError("a lineage cannot supersede itself")
    if supersedes is not None:
        predecessors = [
            entry for entry in entries if entry["config_sha256"] == supersedes
        ]
        if len(predecessors) != 1:
            raise CycleLineageIndexError(
                "superseded config SHA-256 must identify one registered lineage"
            )
        if predecessors[0]["cycle_id"] != cycle_id:
            raise CycleLineageIndexError("a lineage may supersede only the same cycle")

    provisional_entry: dict[str, object] = {
        "cycle_id": cycle_id,
        "config_path": str(config),
        "state_root": str(state),
        "config_sha256": config_sha256,
        "code_commit": commit,
        "supersedes_config_sha256": supersedes,
        "root_identity_sha256": "",
    }
    projection = _lineage_status(
        provisional_entry,
        status,
        config_path=config,
        state_root=state,
    )
    entry = {
        **provisional_entry,
        "root_identity_sha256": projection["root_identity_sha256"],
    }
    same_config = [item for item in entries if item["config_sha256"] == config_sha256]
    if same_config:
        if len(same_config) != 1 or same_config[0] != entry:
            raise CycleLineageIndexError(
                "registered config SHA-256 has conflicting lineage metadata"
            )
        return _registration_result(entry, status)

    entries.append(entry)
    _validate_supersession_graph(entries)
    _publish_index(index_path, entries, stage_heads)
    return _registration_result(entry, status)


def register_cycle_stage_head(
    *,
    index_path: Path,
    cycle_id: str,
    command: str,
    run_card_path: Path,
    code_commit: str,
    supersedes_root_identity_sha256: str | None = None,
) -> dict[str, object]:
    """Register one directly executed, completed stage as a discoverable head."""

    if command not in COMMAND_BOUNDARIES:
        raise CycleLineageIndexError("stage command is not coordinator-reviewed")
    commit = _require_digest(code_commit, "code commit", pattern=_SHA40)
    card_path = _verified_config_path(run_card_path, label="stage-head run card")
    card, card_sha256, commitments = _authenticate_standalone_card(card_path, command)
    stage = _required_string(card, "stage")
    root_identity = hashlib.sha256(
        canonical_json_bytes(
            {
                "cycle_id": cycle_id,
                "command": command,
                "stage": stage,
                "run_card_sha256": card_sha256,
                "output_commitments": commitments,
            }
        )
    ).hexdigest()
    predecessor = (
        None
        if supersedes_root_identity_sha256 is None
        else _require_digest(
            supersedes_root_identity_sha256,
            "superseded root identity SHA-256",
            pattern=_SHA256,
        )
    )
    if predecessor == root_identity:
        raise CycleLineageIndexError("a stage head cannot supersede itself")
    entries, heads = _load_index(index_path, missing_ok=True)
    same_cycle_heads = [head for head in heads if head["cycle_id"] == cycle_id]
    known_roots = {
        cast(str, item["root_identity_sha256"])
        for item in [*entries, *same_cycle_heads]
    }
    if predecessor is not None and predecessor not in known_roots:
        raise CycleLineageIndexError(
            "superseded root identity must identify a registered lineage"
        )
    same_cycle_entries = [entry for entry in entries if entry["cycle_id"] == cycle_id]
    if (same_cycle_heads or same_cycle_entries) and predecessor is None:
        raise CycleLineageIndexError(
            "a later stage head must identify the root it supersedes"
        )
    head: dict[str, object] = {
        "cycle_id": cycle_id,
        "command": command,
        "stage": stage,
        "run_card_path": str(card_path),
        "run_card_sha256": card_sha256,
        "root_identity_sha256": root_identity,
        "code_commit": commit,
        "supersedes_root_identity_sha256": predecessor,
    }
    identical = [
        item for item in heads if item["root_identity_sha256"] == root_identity
    ]
    if identical:
        if len(identical) != 1 or identical[0] != head:
            raise CycleLineageIndexError("stage-head identity has conflicting metadata")
        return _stage_head_registration_result(head, commitments)
    heads.append(head)
    _validate_stage_heads(entries, heads)
    _publish_index(index_path, entries, heads)
    return _stage_head_registration_result(head, commitments)


def locate_cycle_lineage(
    *,
    index_path: Path,
    cycle_id: str | None = None,
) -> dict[str, object]:
    """Locate and re-authenticate the unique active lineage for one cycle."""

    entries, stage_heads = _load_index(index_path, missing_ok=False)
    if cycle_id is None:
        cycle_ids = sorted(
            {cast(str, item["cycle_id"]) for item in [*entries, *stage_heads]}
        )
        if len(cycle_ids) != 1:
            raise CycleLineageIndexError(
                "lineage index contains multiple cycles; pass --cycle-id"
            )
        cycle_id = cycle_ids[0]
    candidates = [entry for entry in entries if entry["cycle_id"] == cycle_id]
    candidate_heads = [head for head in stage_heads if head["cycle_id"] == cycle_id]
    if not candidates and not candidate_heads:
        raise CycleLineageIndexError(f"cycle is not registered: {cycle_id}")
    by_config = {cast(str, entry["config_sha256"]): entry for entry in candidates}
    superseded_roots = {
        cast(
            str,
            by_config[cast(str, entry["supersedes_config_sha256"])][
                "root_identity_sha256"
            ],
        )
        for entry in candidates
        if entry["supersedes_config_sha256"] is not None
    }
    superseded_roots.update(
        cast(str, head["supersedes_root_identity_sha256"])
        for head in candidate_heads
        if head["supersedes_root_identity_sha256"] is not None
    )
    active = [
        item
        for item in [*candidates, *candidate_heads]
        if item["root_identity_sha256"] not in superseded_roots
    ]
    if len(active) != 1:
        raise CycleLineageIndexError(
            f"cycle has ambiguous active lineages: {cycle_id} ({len(active)} found)"
        )
    entry = active[0]
    if "run_card_path" in entry:
        try:
            reject_stale_stage_head(_required_string(entry, "run_card_path"))
        except ValueError as exc:
            raise CycleLineageIndexError(str(exc)) from exc
        return _standalone_lineage_status(
            entry,
            config_entries=candidates,
            stage_heads=candidate_heads,
        )
    config_path = _verified_config_path(Path(cast(str, entry["config_path"])))
    state_root = _verified_state_root(Path(cast(str, entry["state_root"])))
    try:
        status = _cycle_status(config_path, state_root)
    except CycleOrchestratorError as exc:
        raise CycleLineageIndexError(str(exc)) from exc
    if status.get("config_sha256") != entry["config_sha256"]:
        raise CycleLineageIndexError("registered cycle config bytes changed")
    return _lineage_status(
        entry, status, config_path=config_path, state_root=state_root
    )


def _cycle_status(config_path: Path, state_root: Path) -> dict[str, object]:
    return run_acquisition_cycle(
        config_path=config_path,
        state_root=state_root,
        execute=False,
        permissions=BoundaryPermissions(),
        executor=lambda _command, _arguments: (_ for _ in ()).throw(
            AssertionError("status-only lineage discovery executed a stage")
        ),
    )


def _lineage_status(
    entry: Mapping[str, object],
    status: Mapping[str, object],
    *,
    config_path: Path,
    state_root: Path,
) -> dict[str, object]:
    config = load_cycle_config(config_path)
    stage_records = cast(list[object], status["stages"])
    completed: list[tuple[int, Mapping[str, object], Mapping[str, object]]] = []
    receipt_hashes: list[dict[str, object]] = []
    human_decisions: list[dict[str, object]] = []
    for index, (stage, raw_stage_status) in enumerate(
        zip(config.stages, stage_records, strict=True)
    ):
        if not isinstance(raw_stage_status, Mapping):
            raise CycleLineageIndexError("cycle status contains an invalid stage")
        stage_status = cast(Mapping[str, object], raw_stage_status)
        receipt: Mapping[str, object] | None = None
        if stage_status.get("status") == "completed":
            receipt = _verified_receipt_projection(
                state_root=state_root,
                index=index,
                stage_id=stage.stage_id,
                expected_sha256=_required_string(stage_status, "receipt_sha256"),
            )
            completed.append((index, stage_status, receipt))
            receipt_hashes.append(
                {
                    "stage": stage.stage_id,
                    "sha256": _required_string(stage_status, "receipt_sha256"),
                }
            )
        if stage.boundary is AcquisitionBoundary.HUMAN:
            if receipt is not None:
                human_decisions.append(
                    {
                        "stage": stage.stage_id,
                        "status": "recorded",
                        "verification": "VERIFIED",
                        "card_sha256": _required_string(receipt, "run_card_sha256"),
                    }
                )
            else:
                human_decisions.append(
                    _unreceipted_human_status(stage.stage_id, stage.run_card)
                )

    if completed:
        _, head_stage, head_receipt = completed[-1]
        stage_name = _required_string(head_stage, "id")
        stage_status_name = "completed"
        card: dict[str, object] | None = {
            "stage": _required_string(head_receipt, "run_card_stage"),
            "sha256": _required_string(head_receipt, "run_card_sha256"),
        }
        artifact_hashes = _public_artifact_hashes(head_receipt)
    else:
        next_stage = status.get("next_stage")
        if not isinstance(next_stage, Mapping):
            raise CycleLineageIndexError("unstarted cycle lacks a next stage")
        stage_name = _required_string(cast(Mapping[str, object], next_stage), "id")
        stage_status_name = _required_string(
            cast(Mapping[str, object], next_stage), "status"
        )
        card = None
        artifact_hashes = []

    root_identity = hashlib.sha256(
        canonical_json_bytes(
            {
                "config_sha256": entry["config_sha256"],
                "receipts": receipt_hashes,
            }
        )
    ).hexdigest()
    return {
        "schema_version": STATUS_SCHEMA_VERSION,
        "cycle_id": entry["cycle_id"],
        "verification": "VERIFIED",
        "stage": stage_name,
        "stage_status": stage_status_name,
        "root_identity_sha256": root_identity,
        "config_sha256": entry["config_sha256"],
        "code_commit": entry["code_commit"],
        "supersedes_config_sha256": entry["supersedes_config_sha256"],
        "card": card,
        "artifact_hashes": artifact_hashes,
        "human_decisions": human_decisions,
        "authority": {
            "purchase": False,
            "evaluation": False,
            "freeze": False,
            "dispatch": False,
            "publication": False,
        },
    }


def _unreceipted_human_status(stage_id: str, run_card_path: Path) -> dict[str, object]:
    result: dict[str, object] = {
        "stage": stage_id,
        "status": "pending",
        "verification": "NOT_RECORDED",
        "card_sha256": None,
    }
    if not run_card_path.exists() and not run_card_path.is_symlink():
        return result
    try:
        payload = read_unique_regular_file(run_card_path)
        raw = json.loads(payload)
    except (OSError, ReviewBundleError, UnicodeError, json.JSONDecodeError):
        result["status"] = "candidate_corrupt"
        result["verification"] = "UNVERIFIED"
        return result
    raw_record = cast(Mapping[str, object], raw) if isinstance(raw, Mapping) else None
    if raw_record is not None and raw_record.get("status") == "completed":
        result["status"] = "recorded_unreceipted"
        result["verification"] = "UNVERIFIED"
        result["card_sha256"] = hashlib.sha256(payload).hexdigest()
    return result


def _authenticate_standalone_card(
    path: Path, command: str
) -> tuple[Mapping[str, object], str, list[dict[str, object]]]:
    try:
        payload = read_unique_regular_file(path)
        raw = json.loads(payload)
    except (OSError, ReviewBundleError, UnicodeError, json.JSONDecodeError) as exc:
        raise CycleLineageIndexError(
            "stage-head run card is unsafe or invalid"
        ) from exc
    if not isinstance(raw, Mapping):
        raise CycleLineageIndexError("stage-head run card must be a JSON object")
    outer = cast(Mapping[str, object], raw)
    body = outer.get("run_card")
    if isinstance(body, Mapping):
        card = cast(Mapping[str, object], body)
        if (
            set(outer) != {"schema_version", "run_card", "run_card_sha256"}
            or outer.get("schema_version") not in _APPROVAL_RUN_CARD_SCHEMAS
            or set(card) != _APPROVAL_BODY_FIELDS
            or card.get("decision") != "approve"
            or card.get("provider_activity_requested") is not False
            or card.get("provider_activity_executed") is not False
            or card.get("pacer_fee_acknowledged") is not False
            or card.get("paid_activity_requested") is not False
            or card.get("paid_activity_executed") is not False
        ):
            raise CycleLineageIndexError(
                "nested decision run card is not an activity-free approval"
            )
        if (
            outer.get("run_card_sha256")
            != hashlib.sha256(
                canonical_json_value_bytes(
                    card,
                    error_type=CycleLineageIndexError,
                    error_message="nested decision run card is not canonicalizable",
                )
            ).hexdigest()
        ):
            raise CycleLineageIndexError("nested decision run-card hash differs")
        card_view: Mapping[str, object] = {
            **card,
            "schema_version": outer.get("schema_version"),
            "dry_run": False,
            "execute": True,
            "resume": True,
            "output_paths": [],
        }
    else:
        card_view = outer
    expected_stage = COMMAND_RUN_CARD_STAGES.get(command, command)
    schema = card_view.get("schema_version")
    if (
        not isinstance(schema, str)
        or not schema.startswith("legalforecast.")
        or card_view.get("stage") != expected_stage
        or card_view.get("status") != "completed"
        or card_view.get("dry_run") is not False
        or card_view.get("execute") is not True
        or not isinstance(card_view.get("resume"), bool)
        or not isinstance(card_view.get("paid_activity_executed"), bool)
    ):
        raise CycleLineageIndexError(
            "stage-head run card is not an executed completion"
        )
    raw_paths = card_view.get("output_paths")
    try:
        commitments = authenticate_stage_outputs(card_view, raw_paths)
    except ValueError as exc:
        raise CycleLineageIndexError(str(exc)) from exc
    return card_view, hashlib.sha256(payload).hexdigest(), commitments


def _standalone_lineage_status(
    head: Mapping[str, object],
    *,
    config_entries: list[dict[str, object]],
    stage_heads: list[dict[str, object]],
) -> dict[str, object]:
    _card, card_sha256, commitments = _authenticate_stage_head_entry(head)

    decisions: dict[str, dict[str, object]] = {}
    entries_by_root = {
        cast(str, entry["root_identity_sha256"]): entry for entry in config_entries
    }
    heads_by_root = {
        cast(str, item["root_identity_sha256"]): item for item in stage_heads
    }
    cursor: Mapping[str, object] | None = head
    while cursor is not None:
        if "command" in cursor:
            cursor_command = _required_string(cursor, "command")
            cursor_card, cursor_card_sha256, _ = _authenticate_stage_head_entry(cursor)
            if COMMAND_BOUNDARIES[cursor_command] is AcquisitionBoundary.HUMAN:
                cursor_stage = _required_string(cursor_card, "stage")
                decisions[cursor_stage] = {
                    "stage": cursor_stage,
                    "status": "recorded",
                    "verification": "VERIFIED",
                    "card_sha256": cursor_card_sha256,
                }
            predecessor = cursor.get("supersedes_root_identity_sha256")
        else:
            config_path = _verified_config_path(
                Path(_required_string(cursor, "config_path"))
            )
            state_root = _verified_state_root(
                Path(_required_string(cursor, "state_root"))
            )
            try:
                config_status = _cycle_status(config_path, state_root)
            except CycleOrchestratorError as exc:
                raise CycleLineageIndexError(str(exc)) from exc
            projection = _lineage_status(
                cursor,
                config_status,
                config_path=config_path,
                state_root=state_root,
            )
            for raw_decision in cast(list[object], projection["human_decisions"]):
                decision = cast(dict[str, object], raw_decision)
                decisions[cast(str, decision["stage"])] = decision
            predecessor_config = cursor.get("supersedes_config_sha256")
            if predecessor_config is None:
                predecessor = None
            else:
                predecessor_entry = next(
                    (
                        item
                        for item in config_entries
                        if item["config_sha256"] == predecessor_config
                    ),
                    None,
                )
                predecessor = (
                    None
                    if predecessor_entry is None
                    else predecessor_entry["root_identity_sha256"]
                )
        if predecessor is None:
            cursor = None
        else:
            predecessor_text = cast(str, predecessor)
            cursor = heads_by_root.get(predecessor_text) or entries_by_root.get(
                predecessor_text
            )

    return {
        "schema_version": STATUS_SCHEMA_VERSION,
        "cycle_id": head["cycle_id"],
        "verification": "VERIFIED",
        "stage": head["stage"],
        "stage_status": "completed",
        "root_identity_sha256": head["root_identity_sha256"],
        "config_sha256": None,
        "code_commit": head["code_commit"],
        "supersedes_config_sha256": None,
        "supersedes_root_identity_sha256": head["supersedes_root_identity_sha256"],
        "card": {"stage": head["stage"], "sha256": card_sha256},
        "artifact_hashes": _public_commitment_list(commitments),
        "human_decisions": [decisions[key] for key in sorted(decisions)],
        "authority": {
            "purchase": False,
            "evaluation": False,
            "freeze": False,
            "dispatch": False,
            "publication": False,
        },
    }


def _authenticate_stage_head_entry(
    head: Mapping[str, object],
) -> tuple[Mapping[str, object], str, list[dict[str, object]]]:
    command = _required_string(head, "command")
    card, card_sha256, commitments = _authenticate_standalone_card(
        _verified_config_path(
            Path(_required_string(head, "run_card_path")),
            label="stage-head run card",
        ),
        command,
    )
    expected_identity = hashlib.sha256(
        canonical_json_bytes(
            {
                "cycle_id": head["cycle_id"],
                "command": command,
                "stage": card["stage"],
                "run_card_sha256": card_sha256,
                "output_commitments": commitments,
            }
        )
    ).hexdigest()
    if (
        card_sha256 != head["run_card_sha256"]
        or card["stage"] != head["stage"]
        or expected_identity != head["root_identity_sha256"]
    ):
        raise CycleLineageIndexError("registered stage-head evidence changed")
    return card, card_sha256, commitments


def _verified_receipt_projection(
    *,
    state_root: Path,
    index: int,
    stage_id: str,
    expected_sha256: str,
) -> Mapping[str, object]:
    path = state_root / "receipts" / f"{index:04d}-{stage_id}.json"
    try:
        payload = read_unique_regular_file(path)
        raw = json.loads(payload)
    except (OSError, ReviewBundleError, UnicodeError, json.JSONDecodeError) as exc:
        raise CycleLineageIndexError(
            f"stage receipt is unavailable: {stage_id}"
        ) from exc
    if hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise CycleLineageIndexError(f"stage receipt changed during lookup: {stage_id}")
    if not isinstance(raw, Mapping):
        raise CycleLineageIndexError(f"stage receipt is invalid: {stage_id}")
    return cast(Mapping[str, object], raw)


def _public_artifact_hashes(receipt: Mapping[str, object]) -> list[dict[str, object]]:
    raw = receipt.get("output_commitments")
    if not isinstance(raw, list):
        raise CycleLineageIndexError("stage receipt lacks output commitments")
    return _public_commitment_list(cast(list[object], raw))


def _public_commitment_list(
    commitments: list[object] | list[dict[str, object]],
) -> list[dict[str, object]]:
    public: list[dict[str, object]] = []
    for item in commitments:
        if not isinstance(item, Mapping):
            raise CycleLineageIndexError("stage receipt output commitment is invalid")
        record = cast(Mapping[str, object], item)
        kind = _required_string(record, "kind")
        projection: dict[str, object] = {"kind": kind}
        for field in (
            "sha256",
            "tree_sha256",
            "byte_count",
            "entry_count",
            "file_count",
        ):
            if field in record:
                projection[field] = record[field]
        public.append(projection)
    return public


def _registration_result(
    entry: Mapping[str, object], status: Mapping[str, object]
) -> dict[str, object]:
    return {
        "schema_version": INDEX_SCHEMA_VERSION,
        "cycle_id": entry["cycle_id"],
        "config_sha256": entry["config_sha256"],
        "code_commit": entry["code_commit"],
        "supersedes_config_sha256": entry["supersedes_config_sha256"],
        "root_identity_sha256": entry["root_identity_sha256"],
        "completed_stage_count": status["completed_stage_count"],
        "stage_count": status["stage_count"],
    }


def _stage_head_registration_result(
    head: Mapping[str, object], commitments: list[dict[str, object]]
) -> dict[str, object]:
    return {
        "schema_version": INDEX_SCHEMA_VERSION,
        "cycle_id": head["cycle_id"],
        "stage": head["stage"],
        "run_card_sha256": head["run_card_sha256"],
        "root_identity_sha256": head["root_identity_sha256"],
        "code_commit": head["code_commit"],
        "supersedes_root_identity_sha256": head["supersedes_root_identity_sha256"],
        "artifact_hashes": _public_commitment_list(commitments),
    }


def _load_index(
    index_path: Path, *, missing_ok: bool
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    path = _normalized_absolute(index_path, "lineage index")
    if not path.exists() and not path.is_symlink():
        if missing_ok:
            return [], []
        raise CycleLineageIndexError(
            "lineage index does not exist; run register-cycle-lineage to rebuild it"
        )
    try:
        payload = read_unique_regular_file(path)
        raw = json.loads(payload)
    except (OSError, ReviewBundleError) as exc:
        raise CycleLineageIndexError(
            "lineage index is not a safe regular file"
        ) from exc
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CycleLineageIndexError("lineage index must be valid UTF-8 JSON") from exc
    if not isinstance(raw, Mapping):
        raise CycleLineageIndexError("lineage index must be a JSON object")
    record = cast(Mapping[str, object], raw)
    if (
        set(record) != _INDEX_FIELDS
        or record.get("schema_version") != INDEX_SCHEMA_VERSION
    ):
        raise CycleLineageIndexError("lineage index fields or schema differ")
    if canonical_json_bytes(record) != payload:
        raise CycleLineageIndexError("lineage index must use canonical JSON bytes")
    raw_entries = record.get("entries")
    if not isinstance(raw_entries, list):
        raise CycleLineageIndexError("lineage index entries must be a JSON list")
    entries: list[dict[str, object]] = []
    for raw_entry in cast(list[object], raw_entries):
        if not isinstance(raw_entry, Mapping):
            raise CycleLineageIndexError("lineage index entry fields differ")
        typed_entry = cast(Mapping[str, object], raw_entry)
        if set(typed_entry) != _ENTRY_FIELDS:
            raise CycleLineageIndexError("lineage index entry fields differ")
        entry = dict(typed_entry)
        _validate_entry(entry)
        entries.append(entry)
    _validate_supersession_graph(entries)
    raw_heads = record.get("stage_heads")
    if not isinstance(raw_heads, list):
        raise CycleLineageIndexError("lineage stage_heads must be a JSON list")
    heads: list[dict[str, object]] = []
    for raw_head in cast(list[object], raw_heads):
        if not isinstance(raw_head, Mapping):
            raise CycleLineageIndexError("lineage stage-head fields differ")
        typed_head = cast(Mapping[str, object], raw_head)
        if set(typed_head) != _STAGE_HEAD_FIELDS:
            raise CycleLineageIndexError("lineage stage-head fields differ")
        head = dict(typed_head)
        _validate_stage_head(head)
        heads.append(head)
    _validate_stage_heads(entries, heads)
    return entries, heads


def _validate_entry(entry: Mapping[str, object]) -> None:
    _required_string(entry, "cycle_id")
    _require_digest(
        _required_string(entry, "config_sha256"), "config SHA-256", pattern=_SHA256
    )
    _require_digest(
        _required_string(entry, "code_commit"), "code commit", pattern=_SHA40
    )
    _require_digest(
        _required_string(entry, "root_identity_sha256"),
        "root identity SHA-256",
        pattern=_SHA256,
    )
    _normalized_absolute(Path(_required_string(entry, "config_path")), "config path")
    _normalized_absolute(Path(_required_string(entry, "state_root")), "state root")
    supersedes = entry.get("supersedes_config_sha256")
    if supersedes is not None:
        if not isinstance(supersedes, str):
            raise CycleLineageIndexError(
                "superseded config SHA-256 must be text or null"
            )
        _require_digest(supersedes, "superseded config SHA-256", pattern=_SHA256)


def _validate_stage_head(head: Mapping[str, object]) -> None:
    _required_string(head, "cycle_id")
    command = _required_string(head, "command")
    if command not in COMMAND_BOUNDARIES:
        raise CycleLineageIndexError("stage-head command is unsupported")
    if _required_string(head, "stage") != COMMAND_RUN_CARD_STAGES.get(command, command):
        raise CycleLineageIndexError("stage-head command and card stage differ")
    _normalized_absolute(
        Path(_required_string(head, "run_card_path")), "stage-head run card"
    )
    for field, label, pattern in (
        ("run_card_sha256", "run-card SHA-256", _SHA256),
        ("root_identity_sha256", "root identity SHA-256", _SHA256),
        ("code_commit", "code commit", _SHA40),
    ):
        _require_digest(_required_string(head, field), label, pattern=pattern)
    predecessor = head.get("supersedes_root_identity_sha256")
    if predecessor is not None:
        if not isinstance(predecessor, str):
            raise CycleLineageIndexError(
                "superseded root identity SHA-256 must be text or null"
            )
        _require_digest(
            predecessor, "superseded root identity SHA-256", pattern=_SHA256
        )


def _validate_stage_heads(
    entries: list[dict[str, object]], heads: list[dict[str, object]]
) -> None:
    all_items = [*entries, *heads]
    identities = [cast(str, item["root_identity_sha256"]) for item in all_items]
    if len(identities) != len(set(identities)):
        raise CycleLineageIndexError("lineage index repeats a root identity")
    by_identity = {cast(str, item["root_identity_sha256"]): item for item in all_items}
    for head in heads:
        predecessor = head["supersedes_root_identity_sha256"]
        if predecessor is None:
            continue
        if predecessor not in by_identity:
            raise CycleLineageIndexError("stage head references a missing predecessor")
        if by_identity[cast(str, predecessor)]["cycle_id"] != head["cycle_id"]:
            raise CycleLineageIndexError("stage head crosses cycle IDs")
    for head in heads:
        seen: set[str] = set()
        cursor: Mapping[str, object] | None = head
        while cursor is not None and "command" in cursor:
            identity = cast(str, cursor["root_identity_sha256"])
            if identity in seen:
                raise CycleLineageIndexError("stage-head supersession contains a cycle")
            seen.add(identity)
            predecessor = cursor["supersedes_root_identity_sha256"]
            cursor = (
                None if predecessor is None else by_identity.get(cast(str, predecessor))
            )


def _validate_supersession_graph(entries: list[dict[str, object]]) -> None:
    identities = [cast(str, entry["config_sha256"]) for entry in entries]
    if len(identities) != len(set(identities)):
        raise CycleLineageIndexError("lineage index repeats a config SHA-256")
    by_identity = {cast(str, entry["config_sha256"]): entry for entry in entries}
    for entry in entries:
        predecessor = entry["supersedes_config_sha256"]
        if predecessor is None:
            continue
        if predecessor not in by_identity:
            raise CycleLineageIndexError(
                "lineage index references a missing predecessor"
            )
        if by_identity[cast(str, predecessor)]["cycle_id"] != entry["cycle_id"]:
            raise CycleLineageIndexError("lineage index crosses cycle IDs")
    for identity in identities:
        seen: set[str] = set()
        cursor: str | None = identity
        while cursor is not None:
            if cursor in seen:
                raise CycleLineageIndexError(
                    "lineage index supersession contains a cycle"
                )
            seen.add(cursor)
            predecessor = by_identity[cursor]["supersedes_config_sha256"]
            cursor = cast(str | None, predecessor)


def _publish_index(
    index_path: Path,
    entries: list[dict[str, object]],
    stage_heads: list[dict[str, object]],
) -> None:
    path = _normalized_absolute(index_path, "lineage index")
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    try:
        resolved_parent = parent.resolve(strict=True)
    except OSError as exc:  # pragma: no cover - mkdir above normally resolves this
        raise CycleLineageIndexError("lineage index parent is unavailable") from exc
    if resolved_parent != parent:
        raise CycleLineageIndexError("lineage index parent must not contain symlinks")
    payload = canonical_json_bytes(
        {
            "schema_version": INDEX_SCHEMA_VERSION,
            "entries": sorted(
                entries, key=lambda item: cast(str, item["config_sha256"])
            ),
            "stage_heads": sorted(
                stage_heads,
                key=lambda item: cast(str, item["root_identity_sha256"]),
            ),
        }
    )
    if path.exists() or path.is_symlink():
        try:
            current = read_unique_regular_file(path)
        except (OSError, ReviewBundleError) as exc:
            raise CycleLineageIndexError(
                "lineage index is not a safe regular file"
            ) from exc
        if current == payload:
            return
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary.exists():
            temporary.unlink()


def _verified_config_path(path: Path, *, label: str = "cycle config") -> Path:
    normalized = _normalized_absolute(path, label)
    try:
        resolved = normalized.resolve(strict=True)
    except OSError as exc:
        raise CycleLineageIndexError(f"{label} does not exist") from exc
    if resolved != normalized or not resolved.is_file():
        raise CycleLineageIndexError(f"{label} must be a regular path without symlinks")
    return resolved


def _verified_state_root(path: Path) -> Path:
    normalized = _normalized_absolute(path, "state root")
    try:
        resolved = normalized.resolve(strict=True)
    except OSError as exc:
        raise CycleLineageIndexError("state root does not exist") from exc
    if resolved != normalized or not resolved.is_dir():
        raise CycleLineageIndexError("state root must be a directory without symlinks")
    return resolved


def _normalized_absolute(path: Path, label: str) -> Path:
    if not path.is_absolute() or path != Path(os.path.abspath(path)):
        raise CycleLineageIndexError(f"{label} must be an absolute normalized path")
    return path


def _required_string(record: Mapping[str, object], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value:
        raise CycleLineageIndexError(f"{field} must be non-empty text")
    return value


def _require_digest(value: str, label: str, *, pattern: re.Pattern[str]) -> str:
    if not pattern.fullmatch(value):
        raise CycleLineageIndexError(f"{label} has an invalid digest")
    return value
