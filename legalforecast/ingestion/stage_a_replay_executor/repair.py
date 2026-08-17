"""Independent document-repair receipt replay for Stage A preflight."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

from legalforecast.ingestion.candidate_scoped_stage_a_replay import (
    CandidatePacketInput,
)
from legalforecast.ingestion.stage_a_replay_executor.spec import (
    ReplaySpec,
    StageAReplayExecutorError,
)


def verify_repair_receipt(record: Mapping[str, object]) -> dict[str, object]:
    """Rebuild the repair plan/execution before accepting the receipt pin."""

    from legalforecast.ingestion.document_repair_executor import (
        build_full_document_repair_execution,
        replay_docket_snapshot_authority,
        replay_document_repair_receipt,
    )
    from legalforecast.ingestion.missing_document_successor import (
        build_missing_document_acquisition_plan,
        verify_repair_plan_approval,
    )

    manifest_path = _path(record, "manifest_path")
    approval_path = _path(record, "approval_path")
    snapshot_manifest_path = _path(record, "snapshot_manifest_path")
    source_lineage_path = _path(record, "source_lineage_path")
    snapshots_root = _path(record, "snapshots_root")
    execution_path = _path(record, "execution_path")
    receipt_path = _path(record, "receipt_path")
    acquired_documents_path = _path(record, "acquired_documents_path")
    acquired_documents_sha256 = _digest(record, "acquired_documents_sha256")
    acquired_documents = _verify_acquired_documents(
        acquired_documents_path,
        expected_sha256=acquired_documents_sha256,
    )

    manifest_bytes = _read_regular(manifest_path, "document repair manifest")
    approval = verify_repair_plan_approval(
        manifest_bytes,
        _json_object(
            _read_regular(approval_path, "repair approval"), "repair approval"
        ),
    )
    full_plan = build_missing_document_acquisition_plan(
        manifest_bytes=manifest_bytes,
        approval=approval,
    )
    snapshot_manifest_bytes = _read_regular(
        snapshot_manifest_path, "docket snapshot manifest"
    )
    source_lineage_bytes = _read_regular(source_lineage_path, "repair source lineage")
    source_lineage_sha256 = _digest(record, "source_lineage_sha256")
    snapshot_authority = replay_docket_snapshot_authority(
        manifest_bytes=snapshot_manifest_bytes,
        source_lineage_bytes=source_lineage_bytes,
        expected_source_lineage_sha256=source_lineage_sha256,
    )
    snapshot_bytes = {
        candidate_id: _read_regular(
            _snapshot_path(snapshots_root, candidate_id),
            f"docket snapshot {candidate_id}",
        )
        for candidate_id in snapshot_authority.candidate_sha256
    }
    execution_bytes = _read_regular(execution_path, "document repair execution")
    execution_raw_sha256 = hashlib.sha256(execution_bytes).hexdigest()
    if execution_raw_sha256 != _digest(record, "execution_artifact_sha256"):
        raise StageAReplayExecutorError(
            "document repair execution artifact pin differs"
        )
    execution_record = _json_object(execution_bytes, "document repair execution")
    execution = build_full_document_repair_execution(
        full_plan=full_plan,
        docket_snapshot_bytes=snapshot_bytes,
        docket_snapshot_sha256=dict(snapshot_authority.candidate_sha256),
        snapshot_authority=snapshot_authority,
        schema_version=_text(execution_record, "schema_version"),
    )
    if execution.to_record() != dict(execution_record):
        raise StageAReplayExecutorError(
            "document repair execution does not reproduce from verifier inputs"
        )

    receipt_bytes = _read_regular(receipt_path, "document repair receipt")
    receipt_raw_sha256 = hashlib.sha256(receipt_bytes).hexdigest()
    if receipt_raw_sha256 != _digest(record, "receipt_artifact_sha256"):
        raise StageAReplayExecutorError("document repair receipt artifact pin differs")
    replayed = replay_document_repair_receipt(
        full_plan=full_plan,
        execution=execution,
        receipt_record=_json_object(receipt_bytes, "document repair receipt"),
        expected_receipt_sha256=_digest(record, "expected_receipt_sha256"),
    )
    manifest_candidate_ids = tuple(
        dict.fromkeys(item.candidate_id for item in full_plan.items)
    )
    execution_candidate_ids = tuple(
        dict.fromkeys(operation.candidate_id for operation in execution.operations)
    )
    receipt_candidate_ids = tuple(
        dict.fromkeys(_text(row, "candidate_id") for row in replayed.operation_ledger)
    )
    included_rows = [
        row for row in replayed.operation_ledger if row.get("disposition") == "included"
    ]
    included_keys = [
        (
            _text(row, "candidate_id"),
            _text(row, "recap_document_id"),
            _text(row, "document_role"),
        )
        for row in included_rows
    ]
    if len(set(included_keys)) != len(included_keys):
        raise StageAReplayExecutorError(
            "document repair receipt contains duplicate included operations"
        )
    if set(included_keys) != set(acquired_documents):
        raise StageAReplayExecutorError(
            "acquired document identities differ from included repair operations"
        )
    included_operations = [
        {
            "candidate_id": candidate_id,
            "source_document_id": source_document_id,
            "document_role": document_role,
            "sha256": acquired_documents[key][0],
            "byte_count": acquired_documents[key][1],
        }
        for key in included_keys
        for candidate_id, source_document_id, document_role in (key,)
    ]
    nonincluded_operations = [
        {
            "candidate_id": _text(row, "candidate_id"),
            "source_document_id": _text(row, "recap_document_id"),
            "document_role": _text(row, "document_role"),
            "disposition": _text(row, "disposition"),
        }
        for row in replayed.operation_ledger
        if row.get("disposition") != "included"
    ]
    return {
        "manifest_path": str(manifest_path),
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "source_lineage_sha256": source_lineage_sha256,
        "execution_path": str(execution_path),
        "execution_sha256": execution.execution_sha256,
        "execution_artifact_sha256": execution_raw_sha256,
        "receipt_path": str(receipt_path),
        "receipt_sha256": replayed.receipt_sha256,
        "receipt_artifact_sha256": receipt_raw_sha256,
        "acquired_documents_path": str(acquired_documents_path),
        "acquired_documents_sha256": acquired_documents_sha256,
        "manifest_candidate_ids": list(manifest_candidate_ids),
        "execution_candidate_ids": list(execution_candidate_ids),
        "receipt_candidate_ids": list(receipt_candidate_ids),
        "included_operations": included_operations,
        "nonincluded_operations": nonincluded_operations,
    }


def verify_repair_scope(
    spec: ReplaySpec,
    evidence: Mapping[str, object],
    successor_packets: Sequence[CandidatePacketInput],
) -> None:
    """Bind authorized candidates and included repairs to successor packets."""

    authorized = set(spec.candidate_ids)
    for field in (
        "manifest_candidate_ids",
        "execution_candidate_ids",
        "receipt_candidate_ids",
    ):
        value = evidence.get(field)
        if not isinstance(value, list):
            raise StageAReplayExecutorError(
                f"verified repair receipt {field} is invalid"
            )
        raw_items = cast(list[object], value)
        if not all(isinstance(item, str) and item for item in raw_items):
            raise StageAReplayExecutorError(
                f"verified repair receipt {field} is invalid"
            )
        candidate_scope = {cast(str, item) for item in raw_items}
        if not authorized.issubset(candidate_scope):
            raise StageAReplayExecutorError(
                "signed replay candidates fall outside verified repair receipt scope"
            )
    packet_documents = {
        packet.candidate_id: {
            (
                document.source_document_id,
                document.document_role,
                document.sha256,
                document.byte_count,
            )
            for document in packet.documents
        }
        for packet in successor_packets
    }
    included = evidence.get("included_operations")
    if not isinstance(included, list):
        raise StageAReplayExecutorError(
            "verified repair receipt included operations are invalid"
        )
    authorized_with_inclusion: set[str] = set()
    for raw in cast(list[object], included):
        if not isinstance(raw, Mapping):
            raise StageAReplayExecutorError(
                "verified repair receipt included operation is invalid"
            )
        operation = cast(Mapping[str, object], raw)
        candidate_id = _text(operation, "candidate_id")
        source_document_id = _text(operation, "source_document_id")
        document_role = _text(operation, "document_role")
        sha256 = _digest(operation, "sha256")
        byte_count = _byte_count(operation, "byte_count")
        if candidate_id not in authorized:
            continue
        authorized_with_inclusion.add(candidate_id)
        if (
            source_document_id,
            document_role,
            sha256,
            byte_count,
        ) not in packet_documents.get(candidate_id, set()):
            raise StageAReplayExecutorError(
                "included repair document differs from authenticated successor packet: "
                f"{candidate_id}/{source_document_id}/{document_role}"
            )
    if authorized_with_inclusion != authorized:
        raise StageAReplayExecutorError(
            "signed replay candidate lacks an included terminal repair operation"
        )
    nonincluded = evidence.get("nonincluded_operations")
    if not isinstance(nonincluded, list):
        raise StageAReplayExecutorError(
            "verified repair receipt nonincluded operations are invalid"
        )
    for raw in cast(list[object], nonincluded):
        if not isinstance(raw, Mapping):
            raise StageAReplayExecutorError(
                "verified repair receipt nonincluded operation is invalid"
            )
        operation = cast(Mapping[str, object], raw)
        if _text(operation, "candidate_id") in authorized:
            raise StageAReplayExecutorError(
                "signed replay candidate has a nonincluded repair operation: "
                f"{_text(operation, 'disposition')}"
            )


def _verify_acquired_documents(
    path: Path,
    *,
    expected_sha256: str,
) -> dict[tuple[str, str, str], tuple[str, int]]:
    """Verify every acquired-document record and its exact referenced bytes."""

    payload = _read_regular(path, "acquired documents")
    if hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise StageAReplayExecutorError("acquired documents artifact pin differs")
    try:
        loaded: object = json.loads(payload)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise StageAReplayExecutorError(
            "acquired documents artifact is not valid JSON"
        ) from exc
    if not isinstance(loaded, list):
        raise StageAReplayExecutorError("acquired documents artifact must be an array")
    verified: dict[tuple[str, str, str], tuple[str, int]] = {}
    for raw in cast(list[object], loaded):
        if not isinstance(raw, Mapping):
            raise StageAReplayExecutorError("acquired document record is invalid")
        record = cast(Mapping[str, object], raw)
        key = (
            _text(record, "candidate_id"),
            _text(record, "source_document_id"),
            _text(record, "document_role"),
        )
        if key in verified:
            raise StageAReplayExecutorError(
                "acquired documents artifact contains a duplicate document"
            )
        document_path = Path(_text(record, "path"))
        if (
            not document_path.is_absolute()
            or ".." in document_path.parts
            or document_path.resolve() != document_path
        ):
            raise StageAReplayExecutorError(
                f"acquired document path is not absolute and canonical: {document_path}"
            )
        expected_digest = _digest(record, "sha256")
        expected_bytes = _byte_count(record, "byte_count")
        document = _read_regular(document_path, "acquired document")
        if (
            hashlib.sha256(document).hexdigest() != expected_digest
            or len(document) != expected_bytes
        ):
            raise StageAReplayExecutorError(
                "acquired document bytes differ from their committed identity: "
                f"{key[0]}/{key[1]}/{key[2]}"
            )
        verified[key] = (expected_digest, expected_bytes)
    return verified


def _snapshot_path(root: Path, candidate_id: str) -> Path:
    if (
        not candidate_id
        or candidate_id in {".", ".."}
        or "/" in candidate_id
        or "\\" in candidate_id
    ):
        raise StageAReplayExecutorError("docket snapshot candidate_id is unsafe")
    path = root / f"{candidate_id}.json"
    if path.parent != root:
        raise StageAReplayExecutorError("docket snapshot escapes its verified root")
    return path


def _json_object(payload: bytes, label: str) -> Mapping[str, object]:
    try:
        loaded: object = json.loads(payload)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise StageAReplayExecutorError(f"{label} is not valid JSON") from exc
    if not isinstance(loaded, Mapping):
        raise StageAReplayExecutorError(f"{label} must be an object")
    return cast(Mapping[str, object], loaded)


def _read_regular(path: Path, label: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise StageAReplayExecutorError(f"{label} is not a regular file: {path}")
    return path.read_bytes()


def _path(record: Mapping[str, object], field: str) -> Path:
    return Path(_text(record, field))


def _text(record: Mapping[str, object], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise StageAReplayExecutorError(f"{field} must be non-empty text")
    return value


def _digest(record: Mapping[str, object], field: str) -> str:
    value = _text(record, field).removeprefix("sha256:")
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise StageAReplayExecutorError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _byte_count(record: Mapping[str, object], field: str) -> int:
    value = record.get(field)
    if type(value) is not int or value < 0:
        raise StageAReplayExecutorError(f"{field} must be a nonnegative integer")
    return value
