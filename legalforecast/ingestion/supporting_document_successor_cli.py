"""Bounded executor for the ECF-14 exact-100 supporting-document successor.

This is intentionally a one-document executor.  It replays the existing v2
successor and raw-docket plan before opening the public source, writes only to
a no-follow output tree, and leaves the legacy materializer run-card shape
untouched.  The output is a new target root, not an augmentation of v2.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from legalforecast.contracts import (
    DISCLOSURE_CLEARANCE_V1,
    SUPPORTING_DOCUMENT_RESTRICTION_EVIDENCE_V1,
)
from legalforecast.ingestion.canonical_json import canonical_json_bytes
from legalforecast.ingestion.disclosure_clearance import scan_disclosure_document
from legalforecast.ingestion.free_document_downloader import (
    FreeDocumentDownloadError,
    FreeDocumentFetch,
    FreeDocumentSource,
    UrlLibFreeDocumentSource,
)
from legalforecast.ingestion.free_support_memorandum_recovery import (
    FreeSupportMemorandumRecoveryError,
    FreeSupportMemorandumRecoveryPlan,
    verify_free_support_memorandum_recovery_plan,
)
from legalforecast.ingestion.supporting_document_successor import (
    SCHEMA_VERSION,
    SUPPORT_CANDIDATE_ID,
    SUPPORT_DOCKET_ENTRY_NUMBER,
    SUPPORT_DOCUMENT_ID,
    SUPPORT_DOCUMENT_ROLE,
    SUPPORT_SOURCE_URL,
    build_supporting_document_successor,
)


class SupportingDocumentSuccessorCliError(ValueError):
    """Raised when the bounded successor cannot be safely published."""


V2ProjectionVerifier = Callable[[Path], Mapping[str, object]]

_OUTPUTS = {
    "selection": "target-cohort-selection.jsonl",
    "relevance": "case-relevance.jsonl",
    "manifest": "document-downloads-merged.jsonl",
    "clearance": "disclosure-clearance.jsonl",
    "restriction": "restriction-evidence.jsonl",
    "core_filter": "core-filter-results.jsonl",
    "supplemental_manifest": "supplemental-free-source/document-downloads.jsonl",
    "supplemental_clearance": "supplemental-free-source/disclosure-clearance.jsonl",
    "state": "run-cards/project-exact100-supporting-document-successor.json",
}
_SUPPLEMENTAL_DOCUMENT = (
    "supplemental-free-source/documents/73327542/courtlistener_public/"
    "entry-14_73327542-entry-14-motion-to-dismiss-memorandum.pdf"
)
_PROMOTED_CANDIDATE_ID = "72309378"


def add_parser(
    subparsers: Any, *, handler: Callable[[argparse.Namespace], int]
) -> None:
    parser = subparsers.add_parser(
        "project-exact100-supporting-document-successor",
        help="Create the one-document, versioned ECF-14 exact-100 successor.",
        description=(
            "Replays an authenticated exact-100 v2 root and raw-docket recovery "
            "plan, then retrieves only the fixed public ECF-14 PDF.  No paid, "
            "Pacer, model, evaluation, freeze, or dispatch authority is exposed."
        ),
    )
    parser.add_argument("--v2-root", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--bridge-descriptor", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    parser.set_defaults(handler=handler)


def run(args: argparse.Namespace) -> int:
    verifier = cast(V2ProjectionVerifier | None, getattr(args, "_verify_v2", None))
    if verifier is None:
        raise SupportingDocumentSuccessorCliError(
            "supporting-document successor requires exact100 v2 replay authority"
        )
    return _run(
        v2_root=cast(Path, args.v2_root),
        plan_path=cast(Path, args.plan),
        bridge_descriptor=cast(Path, args.bridge_descriptor),
        output_root=cast(Path, args.output_root),
        resume=bool(args.resume),
        verifier=verifier,
        source=None,
    )


def verify_supporting_document_successor_projection(
    target_root: Path, *, verifier: V2ProjectionVerifier
) -> Mapping[str, object]:
    """Reauthenticate a completed successor for ordinary materialization.

    The successor's own card names exactly its v2 root, persisted plan, and
    bridge.  Those paths are inputs to reauthentication, never caller-selected
    source authority.
    """

    root_fd = _open_directory_fd(target_root, create=False)
    try:
        state_bytes = _read_relative_regular(
            target_root, Path(_OUTPUTS["state"]), root_fd=root_fd
        )
        state = _object(state_bytes, "supporting-document successor run card")
        paths = state.get("input_paths")
        if not isinstance(paths, list):
            raise SupportingDocumentSuccessorCliError("successor inputs are malformed")
        inputs = cast(list[object], paths)
        if len(inputs) != 3 or not all(
            isinstance(value, str) and value for value in inputs
        ):
            raise SupportingDocumentSuccessorCliError("successor inputs are malformed")
        v2_root, plan_path, bridge_descriptor = (
            Path(cast(str, value)) for value in inputs
        )
        projection = _verified_v2(v2_root, verifier)
        plan_bytes = _read_regular(plan_path, "support memorandum plan")
        plan = _verified_plan(plan_bytes, bridge_descriptor)
        payloads = _verify_completed_output(
            output_root=target_root,
            projection=projection,
            plan=plan,
            plan_bytes=plan_bytes,
            v2_root=v2_root,
            plan_path=plan_path,
            bridge_descriptor=bridge_descriptor,
            root_fd=root_fd,
        )
        manifest = _jsonl(payloads["manifest"], "supporting-document merged manifest")
        clearance = _jsonl(payloads["clearance"], "supporting-document clearance")
        _require_output_identity(target_root, root_fd)
        return {
            "run_card": state,
            "run_card_path": target_root / _OUTPUTS["state"],
            "run_card_bytes": state_bytes,
            "summary": state,
            "summary_path": target_root / _OUTPUTS["state"],
            "selection_path": target_root / _OUTPUTS["selection"],
            "selection_bytes": payloads["selection"],
            "selection_records": _jsonl(
                payloads["selection"], "supporting-document selection"
            ),
            "case_relevance": _jsonl(
                payloads["relevance"], "supporting-document relevance"
            ),
            "free_manifest": tuple(
                row for row in manifest if row.get("free_or_purchased") == "free"
            ),
            "free_manifest_path": target_root / _OUTPUTS["manifest"],
            "purchased_manifest": tuple(
                row for row in manifest if row.get("free_or_purchased") == "purchased"
            ),
            "free_clearance": tuple(
                row for row in clearance if row.get("free_or_purchased") == "free"
            ),
            "purchased_clearance": tuple(
                row for row in clearance if row.get("free_or_purchased") == "purchased"
            ),
            "restriction_records": _jsonl(
                payloads["restriction"], "supporting-document restriction evidence"
            ),
            "restriction_path": target_root / _OUTPUTS["restriction"],
            "selected_document_keys": {_record_key(row) for row in manifest},
            "supplemental_document_root": target_root
            / "supplemental-free-source/documents",
            "supplemental_manifest": _jsonl(
                payloads["supplemental_manifest"],
                "supporting-document supplemental manifest",
            ),
            "supplemental_clearance": _jsonl(
                payloads["supplemental_clearance"],
                "supporting-document supplemental clearance",
            ),
            "base_v2_projection": projection,
            "verified_artifact_bytes": {
                str((target_root / relative).absolute()): payloads[name]
                for name, relative in _OUTPUTS.items()
            },
        }
    finally:
        os.close(root_fd)


def _run_with_test_dependencies(  # pyright: ignore[reportUnusedFunction]
    *,
    v2_root: Path,
    plan_path: Path,
    bridge_descriptor: Path,
    output_root: Path,
    verifier: V2ProjectionVerifier,
    source: FreeDocumentSource,
    resume: bool = True,
) -> int:
    return _run(
        v2_root=v2_root,
        plan_path=plan_path,
        bridge_descriptor=bridge_descriptor,
        output_root=output_root,
        resume=resume,
        verifier=verifier,
        source=source,
    )


def _run(
    *,
    v2_root: Path,
    plan_path: Path,
    bridge_descriptor: Path,
    output_root: Path,
    resume: bool,
    verifier: V2ProjectionVerifier,
    source: FreeDocumentSource | None,
) -> int:
    # All authority replays and no-follow output checks precede source creation
    # or a network call.
    projection = _verified_v2(v2_root, verifier)
    plan_bytes = _read_regular(plan_path, "support memorandum plan")
    plan = _verified_plan(plan_bytes, bridge_descriptor)
    _require_disjoint_output(output_root, (v2_root, plan_path, bridge_descriptor))
    root_fd = _open_output_root_fd(output_root)
    try:
        _require_output_identity(output_root, root_fd)
        existing = tuple(os.scandir(f"/proc/self/fd/{root_fd}"))
    finally:
        os.close(root_fd)
    if existing:
        if not resume:
            raise SupportingDocumentSuccessorCliError(
                "supporting-document successor already exists and resume is disabled"
            )
        root_fd = _open_directory_fd(output_root, create=False)
        try:
            _verify_completed_output(
                output_root=output_root,
                projection=projection,
                plan=plan,
                plan_bytes=plan_bytes,
                v2_root=v2_root,
                plan_path=plan_path,
                bridge_descriptor=bridge_descriptor,
                root_fd=root_fd,
            )
            _require_output_identity(output_root, root_fd)
        finally:
            os.close(root_fd)
        _print_result(output_root, resumed=True)
        return 0

    promoted_records, promoted_clearance, promoted_documents = _supplemental_promoted(
        projection
    )
    root_fd = _open_output_root_fd(output_root)
    try:
        _require_output_identity(output_root, root_fd)
        if plan.record.get("source_url") != SUPPORT_SOURCE_URL:
            raise SupportingDocumentSuccessorCliError("support memorandum URL differs")
        document_source = source or UrlLibFreeDocumentSource(
            final_url_validator=_require_exact_final_url
        )
        try:
            fetched = document_source.fetch(SUPPORT_SOURCE_URL)
        except FreeDocumentDownloadError as exc:
            raise SupportingDocumentSuccessorCliError(
                f"support memorandum download failed: {exc}"
            ) from exc
        addition, clearance, restriction, document = _addition_records(
            plan=plan,
            base_selection=cast(bytes, projection["selection_bytes"]),
            fetched=fetched,
        )
        projection = _require_inputs_unchanged(
            v2_root=v2_root,
            verifier=verifier,
            initial_projection=projection,
            plan_path=plan_path,
            bridge_descriptor=bridge_descriptor,
            initial_plan_bytes=plan_bytes,
            initial_plan=plan,
        )
        successor = build_supporting_document_successor(
            base_projection=projection,
            addition=addition,
            addition_clearance=clearance,
            addition_restriction=restriction,
        )
        supplemental_manifest = (*promoted_records, addition)
        supplemental_clearance = (*promoted_clearance, clearance)
        payloads = {
            "selection": successor.selection_bytes,
            "relevance": successor.case_relevance_bytes,
            "manifest": successor.free_manifest_bytes
            + _jsonl_bytes(
                cast(tuple[Mapping[str, Any], ...], projection["purchased_manifest"])
            ),
            "clearance": successor.free_clearance_bytes
            + _jsonl_bytes(
                cast(tuple[Mapping[str, Any], ...], projection["purchased_clearance"])
            ),
            "restriction": successor.restriction_bytes,
            "core_filter": successor.core_filter_bytes,
            "supplemental_manifest": _jsonl_bytes(supplemental_manifest),
            "supplemental_clearance": _jsonl_bytes(supplemental_clearance),
            "document": document,
        }
        document_payloads = {
            record["local_path"]: payload for record, payload in promoted_documents
        }
        document_payloads[cast(str, addition["local_path"])] = document
        state = _state(
            v2_root=v2_root,
            plan_path=plan_path,
            bridge_descriptor=bridge_descriptor,
            plan_bytes=plan_bytes,
            payloads={
                **payloads,
                **{
                    f"supplemental_document:{path}": value
                    for path, value in document_payloads.items()
                },
            },
            output_root=output_root,
            selected_case_count=sum(
                row.get("selected") is True
                for row in cast(
                    tuple[Mapping[str, Any], ...], projection["selection_records"]
                )
            ),
        )
        payloads["state"] = _bytes(state)
        for name, payload in payloads.items():
            relative = _SUPPLEMENTAL_DOCUMENT if name == "document" else _OUTPUTS[name]
            _write_immutable_at(root_fd, Path(relative), payload)
        for local_path, payload in document_payloads.items():
            if local_path == cast(str, addition["local_path"]):
                continue
            _write_immutable_at(
                root_fd,
                Path("supplemental-free-source/documents") / Path(local_path),
                payload,
            )
        _require_output_identity(output_root, root_fd)
        projection = _require_inputs_unchanged(
            v2_root=v2_root,
            verifier=verifier,
            initial_projection=projection,
            plan_path=plan_path,
            bridge_descriptor=bridge_descriptor,
            initial_plan_bytes=plan_bytes,
            initial_plan=plan,
        )
        _verify_completed_output(
            output_root=output_root,
            projection=projection,
            plan=plan,
            plan_bytes=plan_bytes,
            v2_root=v2_root,
            plan_path=plan_path,
            bridge_descriptor=bridge_descriptor,
            root_fd=root_fd,
        )
        os.fsync(root_fd)
    finally:
        os.close(root_fd)
    _print_result(output_root, resumed=False)
    return 0


def _verified_v2(v2_root: Path, verifier: V2ProjectionVerifier) -> Mapping[str, object]:
    try:
        value = verifier(v2_root)
    except (OSError, ValueError) as exc:
        raise SupportingDocumentSuccessorCliError(
            "supporting-document successor v2 root is not authenticated"
        ) from exc
    required = {
        "selection_records",
        "selection_path",
        "selection_bytes",
        "case_relevance",
        "free_manifest",
        "purchased_manifest",
        "purchased_clearance",
        "free_clearance",
        "restriction_records",
        "verified_artifact_bytes",
    }
    if not required <= set(value):
        raise SupportingDocumentSuccessorCliError("v2 replay lacks projection surfaces")
    selection_path = value["selection_path"]
    selection_bytes = value["selection_bytes"]
    raw_selection = value["selection_records"]
    if not isinstance(raw_selection, Sequence) or isinstance(
        raw_selection, (str, bytes)
    ):
        raise SupportingDocumentSuccessorCliError("v2 selection is malformed")
    selection_records = tuple(cast(Sequence[object], raw_selection))
    candidate_ids = tuple(
        cast(Mapping[str, object], record).get("candidate_id")
        for record in selection_records
        if isinstance(record, Mapping)
    )
    if (
        len(selection_records) != 100
        or len(candidate_ids) != 100
        or len(set(candidate_ids)) != 100
        or any(
            cast(Mapping[str, object], record).get("selected") is not True
            for record in selection_records
            if isinstance(record, Mapping)
        )
        or SUPPORT_CANDIDATE_ID not in candidate_ids
        or _PROMOTED_CANDIDATE_ID not in candidate_ids
    ):
        raise SupportingDocumentSuccessorCliError(
            "v2 successor does not contain the exact 100 selected candidates"
        )
    if (
        not isinstance(selection_path, Path)
        or selection_path.absolute() != (v2_root / _OUTPUTS["selection"]).absolute()
        or not isinstance(selection_bytes, bytes)
        or _read_regular(selection_path, "v2 selection") != selection_bytes
    ):
        raise SupportingDocumentSuccessorCliError("v2 selection changed during replay")
    return value


def _require_inputs_unchanged(
    *,
    v2_root: Path,
    verifier: V2ProjectionVerifier,
    initial_projection: Mapping[str, object],
    plan_path: Path,
    bridge_descriptor: Path,
    initial_plan_bytes: bytes,
    initial_plan: FreeSupportMemorandumRecoveryPlan,
) -> Mapping[str, object]:
    """Reauthenticate all immutable authority at each publication boundary."""

    replayed = _verified_v2(v2_root, verifier)
    if replayed.get("verified_artifact_bytes") != initial_projection.get(
        "verified_artifact_bytes"
    ):
        raise SupportingDocumentSuccessorCliError(
            "exact100 v2 authority changed during successor publication"
        )
    current_plan_bytes = _read_regular(plan_path, "support memorandum plan")
    if current_plan_bytes != initial_plan_bytes:
        raise SupportingDocumentSuccessorCliError(
            "support memorandum plan changed during successor publication"
        )
    current_plan = _verified_plan(current_plan_bytes, bridge_descriptor)
    if current_plan.record_bytes != initial_plan.record_bytes:
        raise SupportingDocumentSuccessorCliError(
            "support memorandum bridge changed during successor publication"
        )
    return replayed


def _verified_plan(payload: bytes, bridge: Path) -> FreeSupportMemorandumRecoveryPlan:
    try:
        plan = verify_free_support_memorandum_recovery_plan(
            persisted_plan_bytes=payload, bridge_descriptor_path=bridge
        )
    except (FreeSupportMemorandumRecoveryError, OSError, ValueError) as exc:
        raise SupportingDocumentSuccessorCliError(
            "support memorandum plan is not authenticated"
        ) from exc
    if (
        plan.record.get("candidate_id") != SUPPORT_CANDIDATE_ID
        or plan.record.get("source_document_id") != SUPPORT_DOCUMENT_ID
        or plan.record.get("supporting_entry_number") != SUPPORT_DOCKET_ENTRY_NUMBER
        or plan.record.get("document_role") != SUPPORT_DOCUMENT_ROLE
        or plan.record.get("source_url") != SUPPORT_SOURCE_URL
    ):
        raise SupportingDocumentSuccessorCliError(
            "support memorandum plan is outside authority"
        )
    return plan


def _addition_records(
    *,
    plan: FreeSupportMemorandumRecoveryPlan,
    base_selection: bytes,
    fetched: FreeDocumentFetch,
) -> tuple[dict[str, object], dict[str, object], dict[str, object], bytes]:
    if not fetched.content:
        raise SupportingDocumentSuccessorCliError(
            "support memorandum download is empty"
        )
    digest = hashlib.sha256(fetched.content).hexdigest()
    local_path = _SUPPLEMENTAL_DOCUMENT.removeprefix(
        "supplemental-free-source/documents/"
    )
    addition: dict[str, object] = {
        "candidate_id": SUPPORT_CANDIDATE_ID,
        "source_provider": "courtlistener_public",
        "source_document_id": SUPPORT_DOCUMENT_ID,
        "docket_entry_number": SUPPORT_DOCKET_ENTRY_NUMBER,
        "document_role": SUPPORT_DOCUMENT_ROLE,
        "source_url": SUPPORT_SOURCE_URL,
        "local_path": local_path,
        "sha256": digest,
        "byte_count": len(fetched.content),
        "free_or_purchased": "free",
        "retry_count": fetched.retry_count,
        "rate_limited": fetched.rate_limited,
        "reused_existing": False,
    }
    scan = scan_disclosure_document(fetched.content)
    if scan.automated_markers or scan.coverage_status != "complete":
        raise SupportingDocumentSuccessorCliError("support memorandum is not cleared")
    clearance: dict[str, object] = {
        "schema_version": str(DISCLOSURE_CLEARANCE_V1),
        "candidate_id": SUPPORT_CANDIDATE_ID,
        "source_document_id": SUPPORT_DOCUMENT_ID,
        "document_role": SUPPORT_DOCUMENT_ROLE,
        "docket_entry_number": SUPPORT_DOCKET_ENTRY_NUMBER,
        "source_url": SUPPORT_SOURCE_URL,
        "local_path": local_path,
        "sha256": digest,
        "byte_count": len(fetched.content),
        "status": "cleared",
        "automated_markers": list(scan.automated_markers),
        "restriction_status": "public",
        "restriction_evidence": ["courtlistener_public_download_record_checked"],
        "reviewer_id": None,
        "controlled_store_provenance": SUPPORT_SOURCE_URL,
        "reviewed_at": None,
        "free_or_purchased": "free",
        "clearance_basis": "affirmative_public_provenance",
        "routing_plan_sha256": _sha(
            base_selection + plan.record_bytes + _bytes(addition)
        ),
    }
    restriction: dict[str, object] = {
        "schema_version": str(SUPPORTING_DOCUMENT_RESTRICTION_EVIDENCE_V1),
        "candidate_id": SUPPORT_CANDIDATE_ID,
        "source_document_id": SUPPORT_DOCUMENT_ID,
        "document_role": SUPPORT_DOCUMENT_ROLE,
        "docket_entry_number": SUPPORT_DOCKET_ENTRY_NUMBER,
        "source_url": SUPPORT_SOURCE_URL,
        "local_path": local_path,
        "sha256": digest,
        "byte_count": len(fetched.content),
        "free_or_purchased": "free",
        "is_available": True,
        "is_private": False,
        "is_sealed": False,
        "redaction_or_seal_status": "public",
        "restriction_status": "public",
        "restriction_evidence": ["courtlistener_public_download_record_checked"],
    }
    return addition, clearance, restriction, fetched.content


def _supplemental_promoted(
    projection: Mapping[str, object],
) -> tuple[
    tuple[Mapping[str, Any], ...],
    tuple[Mapping[str, Any], ...],
    tuple[tuple[Mapping[str, Any], bytes], ...],
]:
    """Copy exactly the five v2-promoted free documents into the second source."""

    run_card = projection.get("run_card")
    if not isinstance(run_card, Mapping):
        raise SupportingDocumentSuccessorCliError("v2 projection lacks run card")
    paths = cast(Mapping[str, object], run_card).get("input_paths")
    if not isinstance(paths, list):
        raise SupportingDocumentSuccessorCliError("v2 projection lacks exact inputs")
    input_paths = cast(list[object], paths)
    if len(input_paths) != 7 or not all(
        isinstance(value, str) and value for value in input_paths
    ):
        raise SupportingDocumentSuccessorCliError("v2 projection lacks exact inputs")
    historical_root = Path(cast(str, input_paths[6]))
    document_root = historical_root / "documents"
    raw_manifest = _jsonl(
        _read_relative_regular(historical_root, Path("free-document-downloads.jsonl")),
        "historical free manifest",
    )
    expected = tuple(
        cast(Mapping[str, Any], record)
        for record in cast(tuple[object, ...], projection["free_manifest"])
        if cast(Mapping[str, object], record).get("candidate_id")
        == _PROMOTED_CANDIDATE_ID
    )
    if len(expected) != 5:
        raise SupportingDocumentSuccessorCliError(
            "v2 projection does not retain exactly five promoted free documents"
        )
    source_by_key = {
        _record_key(record): record
        for record in raw_manifest
        if record.get("free_or_purchased") == "free"
    }
    clearance_by_key = {
        _record_key(cast(Mapping[str, Any], record))
        for record in cast(tuple[object, ...], projection["free_clearance"])
    }
    records: list[Mapping[str, Any]] = []
    clearances: list[Mapping[str, Any]] = []
    documents: list[tuple[Mapping[str, Any], bytes]] = []
    source_clearance = {
        _record_key(cast(Mapping[str, Any], record)): cast(Mapping[str, Any], record)
        for record in cast(tuple[object, ...], projection["free_clearance"])
    }
    for record in expected:
        key = _record_key(record)
        source = source_by_key.get(key)
        if source is None or any(
            source.get(field) != record.get(field)
            for field in ("free_or_purchased", "local_path", "sha256", "byte_count")
        ):
            raise SupportingDocumentSuccessorCliError(
                "promoted free source differs from authenticated v2 projection"
            )
        clearance = source_clearance.get(key)
        if clearance is None or key not in clearance_by_key:
            raise SupportingDocumentSuccessorCliError(
                "promoted free source lacks clearance"
            )
        local_path = record.get("local_path")
        if not isinstance(local_path, str):
            raise SupportingDocumentSuccessorCliError(
                "promoted free source path is invalid"
            )
        payload = _read_relative_regular(document_root, _safe_relative(local_path))
        if len(payload) != record.get("byte_count") or hashlib.sha256(
            payload
        ).hexdigest() != record.get("sha256"):
            raise SupportingDocumentSuccessorCliError(
                "promoted free source bytes differ"
            )
        records.append(record)
        clearances.append(clearance)
        documents.append((record, payload))
    return tuple(records), tuple(clearances), tuple(documents)


def _record_key(record: Mapping[str, Any]) -> tuple[str, str]:
    candidate_id = record.get("candidate_id")
    document_id = record.get("source_document_id")
    if not isinstance(candidate_id, str) or not isinstance(document_id, str):
        raise SupportingDocumentSuccessorCliError("document identity is invalid")
    return candidate_id, document_id


def _safe_relative(value: str) -> Path:
    relative = Path(value)
    if relative.is_absolute() or any(
        part in {"", ".", ".."} for part in relative.parts
    ):
        raise SupportingDocumentSuccessorCliError("document path is invalid")
    return relative


def _state(
    *,
    v2_root: Path,
    plan_path: Path,
    bridge_descriptor: Path,
    plan_bytes: bytes,
    payloads: Mapping[str, bytes],
    output_root: Path,
    selected_case_count: int,
) -> dict[str, object]:
    output_paths = {
        **{
            name: str((output_root / path).absolute())
            for name, path in _OUTPUTS.items()
        },
        "document": str((output_root / _SUPPLEMENTAL_DOCUMENT).absolute()),
    }
    output_paths.update(
        {
            name: str(
                (
                    output_root
                    / "supplemental-free-source/documents"
                    / name.removeprefix("supplemental_document:")
                ).absolute()
            )
            for name in payloads
            if name.startswith("supplemental_document:")
        }
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "stage": "project-exact100-supporting-document-successor",
        "status": "completed",
        "dry_run": False,
        "execute": True,
        "selected_case_count": selected_case_count,
        "added_document": {
            "candidate_id": SUPPORT_CANDIDATE_ID,
            "source_document_id": SUPPORT_DOCUMENT_ID,
            "docket_entry_number": SUPPORT_DOCKET_ENTRY_NUMBER,
            "document_role": SUPPORT_DOCUMENT_ROLE,
            "source_url": SUPPORT_SOURCE_URL,
        },
        "input_paths": [
            str(v2_root.absolute()),
            str(plan_path.absolute()),
            str(bridge_descriptor.absolute()),
        ],
        "input_commitments": {
            "v2_selection_sha256": _sha(
                _read_regular(v2_root / _OUTPUTS["selection"], "v2 selection")
            ),
            "plan_sha256": _sha(plan_bytes),
            "bridge_sha256": _sha(
                _read_regular(bridge_descriptor, "raw-docket bridge")
            ),
        },
        "output_paths": output_paths,
        "output_commitments": {
            name: _sha(payload) for name, payload in payloads.items()
        },
        "paid_activity_executed": False,
        "pacer_activity_executed": False,
        "recap_fetch_activity_executed": False,
        "provider_activity_executed": True,
        "evaluation_permitted": False,
        "freeze_permitted": False,
        "dispatch_permitted": False,
    }


def _verify_completed_output(
    *,
    output_root: Path,
    projection: Mapping[str, object],
    plan: FreeSupportMemorandumRecoveryPlan,
    plan_bytes: bytes,
    v2_root: Path,
    plan_path: Path,
    bridge_descriptor: Path,
    root_fd: int | None = None,
) -> dict[str, bytes]:
    payloads = {
        name: _read_relative_regular(output_root, Path(path), root_fd=root_fd)
        for name, path in _OUTPUTS.items()
    }
    document = _read_relative_regular(
        output_root, Path(_SUPPLEMENTAL_DOCUMENT), root_fd=root_fd
    )
    state = _object(payloads["state"], "supporting-document successor run card")
    if (
        state.get("schema_version") != SCHEMA_VERSION
        or state.get("status") != "completed"
    ):
        raise SupportingDocumentSuccessorCliError(
            "supporting-document successor is partial"
        )
    if state.get("input_paths") != [
        str(v2_root.absolute()),
        str(plan_path.absolute()),
        str(bridge_descriptor.absolute()),
    ]:
        raise SupportingDocumentSuccessorCliError(
            "supporting-document successor inputs differ"
        )
    supplemental_manifest = _jsonl(
        payloads["supplemental_manifest"], "supplemental manifest"
    )
    supplemental_clearance = _jsonl(
        payloads["supplemental_clearance"], "supplemental clearance"
    )
    if len(supplemental_manifest) != 6 or len(supplemental_clearance) != 6:
        raise SupportingDocumentSuccessorCliError(
            "supplemental source does not contain six documents"
        )
    addition_rows = [
        row
        for row in supplemental_manifest
        if _record_key(row) == (SUPPORT_CANDIDATE_ID, SUPPORT_DOCUMENT_ID)
    ]
    clearance_rows = [
        row
        for row in supplemental_clearance
        if _record_key(row) == (SUPPORT_CANDIDATE_ID, SUPPORT_DOCUMENT_ID)
    ]
    if len(addition_rows) != 1 or len(clearance_rows) != 1:
        raise SupportingDocumentSuccessorCliError(
            "supplemental ECF-14 identity differs"
        )
    addition = addition_rows[0]
    clearance = clearance_rows[0]
    restriction = next(
        row
        for row in _jsonl(payloads["restriction"], "restriction evidence")
        if _record_key(row) == (SUPPORT_CANDIDATE_ID, SUPPORT_DOCUMENT_ID)
    )
    if addition.get("sha256") != hashlib.sha256(document).hexdigest() or addition.get(
        "byte_count"
    ) != len(document):
        raise SupportingDocumentSuccessorCliError("support memorandum bytes differ")
    scan = scan_disclosure_document(document)
    if (
        scan.automated_markers
        or scan.coverage_status != "complete"
        or clearance.get("status") != "cleared"
        or clearance.get("automated_markers") != list(scan.automated_markers)
    ):
        raise SupportingDocumentSuccessorCliError(
            "support memorandum is not cleared on replay"
        )
    promoted_records, promoted_clearance, promoted_documents = _supplemental_promoted(
        projection
    )
    if (
        tuple(supplemental_manifest[:-1]) != promoted_records
        or tuple(supplemental_clearance[:-1]) != promoted_clearance
    ):
        raise SupportingDocumentSuccessorCliError(
            "supplemental promoted documents differ"
        )
    for record, expected_document in promoted_documents:
        local_path = record.get("local_path")
        if (
            not isinstance(local_path, str)
            or _read_relative_regular(
                output_root,
                Path("supplemental-free-source/documents") / _safe_relative(local_path),
                root_fd=root_fd,
            )
            != expected_document
        ):
            raise SupportingDocumentSuccessorCliError(
                "supplemental promoted bytes differ"
            )
    successor = build_supporting_document_successor(
        base_projection=projection,
        addition=addition,
        addition_clearance=clearance,
        addition_restriction=restriction,
    )
    expected = {
        "selection": successor.selection_bytes,
        "relevance": successor.case_relevance_bytes,
        "manifest": successor.free_manifest_bytes
        + _jsonl_bytes(
            cast(tuple[Mapping[str, Any], ...], projection["purchased_manifest"])
        ),
        "clearance": successor.free_clearance_bytes
        + _jsonl_bytes(
            cast(tuple[Mapping[str, Any], ...], projection["purchased_clearance"])
        ),
        "restriction": successor.restriction_bytes,
        "core_filter": successor.core_filter_bytes,
        "supplemental_manifest": _jsonl_bytes(tuple(supplemental_manifest)),
        "supplemental_clearance": _jsonl_bytes(tuple(supplemental_clearance)),
        "document": document,
    }
    document_payloads = {
        cast(str, addition["local_path"]): document,
        **{
            cast(str, record["local_path"]): payload
            for record, payload in promoted_documents
        },
    }
    if any(payloads[name] != expected[name] for name in _OUTPUTS if name != "state"):
        raise SupportingDocumentSuccessorCliError(
            "supporting-document successor differs from replay"
        )
    expected_state = _state(
        v2_root=v2_root,
        plan_path=plan_path,
        bridge_descriptor=bridge_descriptor,
        plan_bytes=plan_bytes,
        payloads={
            **expected,
            **{
                f"supplemental_document:{path}": value
                for path, value in document_payloads.items()
            },
        },
        output_root=output_root,
        selected_case_count=sum(
            row.get("selected") is True
            for row in cast(
                tuple[Mapping[str, Any], ...], projection["selection_records"]
            )
        ),
    )
    if payloads["state"] != _bytes(expected_state):
        raise SupportingDocumentSuccessorCliError(
            "supporting-document successor run card differs from replay"
        )
    return payloads


def _require_exact_final_url(url: str) -> None:
    if url != SUPPORT_SOURCE_URL:
        raise SupportingDocumentSuccessorCliError(
            "support memorandum redirect differs from canonical URL"
        )


def _read_regular(path: Path, label: str) -> bytes:
    parent: int | None = None
    try:
        parent = _open_directory_fd(path.parent, create=False)
        descriptor = os.open(
            path.name,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=parent,
        )
    except (OSError, SupportingDocumentSuccessorCliError) as exc:
        if parent is not None:
            os.close(parent)
        raise SupportingDocumentSuccessorCliError(
            f"{label} is not a safe regular file"
        ) from exc
    os.close(parent)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise SupportingDocumentSuccessorCliError(
                f"{label} is not a singly linked regular file"
            )
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
        payload = b"".join(chunks)
        after = os.fstat(descriptor)
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ):
            raise SupportingDocumentSuccessorCliError(f"{label} changed while reading")
        return payload
    finally:
        os.close(descriptor)


def _read_relative_regular(
    root: Path, relative: Path, *, root_fd: int | None = None
) -> bytes:
    """Read one input using no-follow descriptors for every component."""

    relative = _safe_relative(relative.as_posix())
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    try:
        descriptor = (
            os.dup(root_fd)
            if root_fd is not None
            else _open_directory_fd(root, create=False)
        )
    except OSError as exc:
        raise SupportingDocumentSuccessorCliError(
            "input directory is not safe"
        ) from exc
    try:
        for component in relative.parts[:-1]:
            child = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        handle = os.open(
            relative.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=descriptor
        )
        try:
            before = os.fstat(handle)
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
                raise SupportingDocumentSuccessorCliError(
                    "input document is not a singly linked regular file"
                )
            chunks: list[bytes] = []
            while chunk := os.read(handle, 1024 * 1024):
                chunks.append(chunk)
            payload = b"".join(chunks)
            after = os.fstat(handle)
            if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
            ):
                raise SupportingDocumentSuccessorCliError(
                    "input document changed while reading"
                )
            return payload
        finally:
            os.close(handle)
    except OSError as exc:
        raise SupportingDocumentSuccessorCliError("input document is not safe") from exc
    finally:
        os.close(descriptor)


def _require_disjoint_output(output: Path, inputs: tuple[Path, ...]) -> None:
    output_abs = Path(os.path.abspath(output))
    for value in inputs:
        input_abs = Path(os.path.abspath(value))
        if (
            output_abs == input_abs
            or output_abs in input_abs.parents
            or input_abs in output_abs.parents
        ):
            raise SupportingDocumentSuccessorCliError("output overlaps immutable input")


def _open_directory_fd(root: Path, *, create: bool) -> int:
    absolute = Path(os.path.abspath(root))
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    descriptor = os.open(absolute.anchor, flags)
    try:
        for component in absolute.parts[1:]:
            try:
                child = os.open(component, flags, dir_fd=descriptor)
            except FileNotFoundError:
                if not create:
                    raise SupportingDocumentSuccessorCliError(
                        "directory could not be opened without symlinks"
                    ) from None
                try:
                    os.mkdir(component, 0o700, dir_fd=descriptor)
                    child = os.open(component, flags, dir_fd=descriptor)
                except OSError as exc:
                    raise SupportingDocumentSuccessorCliError(
                        "output root could not be opened without symlinks"
                    ) from exc
            except OSError as exc:
                raise SupportingDocumentSuccessorCliError(
                    "output root could not be opened without symlinks"
                ) from exc
            os.close(descriptor)
            descriptor = child
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor


def _open_output_root_fd(root: Path) -> int:
    return _open_directory_fd(root, create=True)


def _require_output_identity(root: Path, descriptor: int) -> None:
    current = _open_output_root_fd(root)
    try:
        if (os.fstat(current).st_dev, os.fstat(current).st_ino) != (
            os.fstat(descriptor).st_dev,
            os.fstat(descriptor).st_ino,
        ):
            raise SupportingDocumentSuccessorCliError(
                "output root changed during publication"
            )
    finally:
        os.close(current)


def _write_immutable_at(root_fd: int, relative: Path, payload: bytes) -> None:
    if relative.is_absolute() or any(
        part in {"", ".", ".."} for part in relative.parts
    ):
        raise SupportingDocumentSuccessorCliError("invalid output path")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    parent = os.dup(root_fd)
    try:
        for component in relative.parts[:-1]:
            try:
                child = os.open(component, flags, dir_fd=parent)
            except FileNotFoundError:
                os.mkdir(component, 0o700, dir_fd=parent)
                child = os.open(component, flags, dir_fd=parent)
            os.close(parent)
            parent = child
        handle = os.open(
            relative.name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
            0o600,
            dir_fd=parent,
        )
        try:
            with os.fdopen(handle, "wb", closefd=True) as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.fsync(parent)
        except BaseException:
            try:
                os.unlink(relative.name, dir_fd=parent)
            except FileNotFoundError:
                # Another cleanup path already removed the partial leaf.
                pass
            raise
    except FileExistsError as exc:
        raise SupportingDocumentSuccessorCliError(
            f"immutable output already exists: {relative}"
        ) from exc
    finally:
        os.close(parent)


def _object(payload: bytes, label: str) -> dict[str, object]:
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SupportingDocumentSuccessorCliError(
            f"{label} is not canonical JSON"
        ) from exc
    if not isinstance(value, dict) or _bytes(cast(dict[str, object], value)) != payload:
        raise SupportingDocumentSuccessorCliError(f"{label} is not canonical JSON")
    return cast(dict[str, object], value)


def _jsonl_bytes(records: tuple[Mapping[str, Any], ...]) -> bytes:
    return b"".join(_bytes(dict(record)) for record in records)


def _jsonl(payload: bytes, label: str) -> tuple[dict[str, Any], ...]:
    try:
        rows = tuple(_object(line + b"\n", label) for line in payload.splitlines())
    except SupportingDocumentSuccessorCliError:
        raise
    if not rows or _jsonl_bytes(rows) != payload:
        raise SupportingDocumentSuccessorCliError(f"{label} is not canonical JSONL")
    return tuple(cast(dict[str, Any], row) for row in rows)


def _bytes(value: object) -> bytes:
    return canonical_json_bytes(
        value,
        error_type=SupportingDocumentSuccessorCliError,
        error_message="supporting-document successor serialization failed",
    )


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _print_result(output_root: Path, *, resumed: bool) -> None:
    print(
        json.dumps(
            {
                "output_root": str(output_root.absolute()),
                "resumed": resumed,
                "paid_activity_executed": False,
                "pacer_activity_executed": False,
                "recap_fetch_activity_executed": False,
                "provider_activity_executed": not resumed,
            },
            sort_keys=True,
        )
    )
