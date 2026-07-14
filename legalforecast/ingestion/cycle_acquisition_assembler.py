"""Content-addressed assembly of immutable acquisition batch roots."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, cast

from legalforecast.ingestion.cycle_acquisition_store import (
    SnapshotVerificationError,
    verify_snapshot,
)

ASSEMBLY_SCHEMA = "legalforecast.cycle_acquisition_assembly.v1"
COMPONENT_PROVENANCE_SCHEMA = "legalforecast.acquisition_component_provenance.v1"
COMPONENT_PROVENANCE_FILENAME = "acquisition-component-provenance.json"
COMPONENT_STAGE_ORDER = {
    "plan": 10,
    "download": 20,
    "bridge": 30,
    "filter": 40,
    "combined": 50,
}
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")

_IMMUTABLE_EXCLUSION_REASONS = frozenset(
    {
        "decision_before_release_anchor",
        "bankruptcy_court",
        "not_federal_district_court",
        "missing_docket_number",
        "placeholder_or_sealed_docket_number",
        "not_civil_cv_docket",
        "criminal_style_caption",
        "non_civil_case",
        "non_civil_metadata",
        "criminal_case",
        "bankruptcy_case",
        "administrative_case",
        "appellate_case",
        "missing_civil_case_metadata",
        "invalid_civil_case_metadata",
    }
)
_TRANSIENT_EXCLUSION_REASONS = frozenset(
    {
        "fetch_error",
        "parse_failure",
        "temporarily_unavailable",
        "courtlistener_docket_unavailable",
        "courtlistener_docket_html_unavailable",
        "case_dev_provider_blocker",
        "case_dev_server_error_retries_exhausted",
        "firecrawl_provider_blocker",
    }
)
_COURTLISTENER_NAMESPACED_ID = re.compile(r"courtlistener-docket-(\d+)\Z")
_SCREENED_ARTIFACTS = (
    "screened-cases.jsonl",
    "courtlistener-screened-cases.jsonl",
)
_SCREENING_EXCLUSION_ARTIFACTS = (
    "exclusions.jsonl",
    "discovery-exclusions.jsonl",
    "courtlistener-discovery-exclusions.jsonl",
)
_DOWNSTREAM_EXCLUSION_ARTIFACTS = (
    "public-packet-exclusions.jsonl",
    "pacer-gap-bridge-exclusions.jsonl",
)
_SELECTION_ARTIFACTS = (
    "public-packet-selection-reconciled.jsonl",
    "public-packet-selection.jsonl",
)
_PAID_GAP_ARTIFACTS = ("public-packet-paid-gaps.jsonl",)
_RELEVANCE_ARTIFACTS = ("case-relevance.jsonl",)
_FILTER_ARTIFACTS = ("core-filter-results.jsonl",)
_MANIFEST_ARTIFACTS = (
    "document-downloads-merged.jsonl",
    "free-document-downloads.jsonl",
)
_DOWNSTREAM_COMPONENT_ARTIFACTS = (
    *_DOWNSTREAM_EXCLUSION_ARTIFACTS,
    *_SELECTION_ARTIFACTS,
    *_PAID_GAP_ARTIFACTS,
    *_RELEVANCE_ARTIFACTS,
    *_FILTER_ARTIFACTS,
    *_MANIFEST_ARTIFACTS,
)


class CycleAssemblyError(ValueError):
    """Raised when a batch cannot safely enter the canonical cycle root."""


@dataclass(frozen=True, slots=True)
class PreparedDocument:
    """A verified source document and its content-addressed destination."""

    source: Path
    destination: Path
    record: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class CycleAssembly:
    """Validated artifacts ready to publish into one cycle root."""

    screened_cases: tuple[Mapping[str, Any], ...]
    discovery_exclusions: tuple[Mapping[str, Any], ...]
    selections: tuple[Mapping[str, Any], ...]
    paid_gaps: tuple[Mapping[str, Any], ...]
    case_relevance: tuple[Mapping[str, Any], ...]
    core_filter_results: tuple[Mapping[str, Any], ...]
    document_manifest: tuple[Mapping[str, Any], ...]
    documents: tuple[PreparedDocument, ...]
    summary: Mapping[str, Any]


def assemble_cycle_acquisition(
    batch_roots: Sequence[Path],
    *,
    expected_cycle_hash: str,
    output_root: Path,
    copy_documents: bool,
) -> CycleAssembly:
    """Validate, reconcile, and optionally publish immutable acquisition batches."""

    if _SHA256.fullmatch(expected_cycle_hash) is None:
        raise CycleAssemblyError("expected cycle hash must be a lowercase SHA-256")
    roots = _validated_batch_roots(batch_roots, output_root=output_root)
    output = output_root.absolute()
    current: dict[str, tuple[str, Mapping[str, Any]]] = {}
    selections: dict[str, Mapping[str, Any]] = {}
    paid_gaps: dict[str, Mapping[str, Any]] = {}
    relevance: dict[str, Mapping[str, Any]] = {}
    filters: dict[str, Mapping[str, Any]] = {}
    manifest: dict[tuple[str, str], Mapping[str, Any]] = {}
    prepared_by_key: dict[tuple[str, str], PreparedDocument] = {}
    batch_provenance: list[dict[str, Any]] = []
    active_screening_snapshot_ordinal: int | None = None
    active_screening_snapshot_root: str | None = None
    downstream_component_ordinal: int | None = None
    active_snapshot_cycle_hash: str | None = None
    active_snapshot_batch_digest: str | None = None
    active_snapshot_manifest_sha256: str | None = None
    predecessor_provenance_sha256: str | None = None
    active_component_stage_rank = 0
    seen_snapshot_batch_digests: set[str] = set()
    seen_snapshot_manifest_sha256s: set[str] = set()

    for ordinal, root in enumerate(roots, start=1):
        input_fingerprint = _root_input_fingerprint(root)
        screened_records = _read_first_jsonl(root, _SCREENED_ARTIFACTS)
        screening_exclusion_records = _read_jsonl_union(
            root,
            _SCREENING_EXCLUSION_ARTIFACTS,
        )
        downstream_exclusion_records = _read_jsonl_union(
            root,
            _DOWNSTREAM_EXCLUSION_ARTIFACTS,
        )
        exclusion_records = [
            *screening_exclusion_records,
            *downstream_exclusion_records,
        ]
        batch_selections = _read_first_jsonl(root, _SELECTION_ARTIFACTS)
        batch_paid_gaps = _read_first_jsonl(root, _PAID_GAP_ARTIFACTS)
        batch_relevance = _read_first_jsonl(root, _RELEVANCE_ARTIFACTS)
        batch_filters = _read_first_jsonl(root, _FILTER_ARTIFACTS)
        batch_manifest = _read_first_jsonl(root, _MANIFEST_ARTIFACTS)
        downstream_record_count = sum(
            len(records)
            for records in (
                downstream_exclusion_records,
                batch_selections,
                batch_paid_gaps,
                batch_relevance,
                batch_filters,
                batch_manifest,
            )
        )
        snapshot_manifest = _verified_snapshot_manifest(
            root,
            expected_cycle_hash=expected_cycle_hash,
        )
        summary = _read_optional_json(root / "summary.json")
        if snapshot_manifest is None and (
            screened_records or screening_exclusion_records or summary is not None
        ):
            raise CycleAssemblyError(
                f"screening root is missing a verified snapshot manifest: {root}"
            )
        has_empty_downstream_component = (
            summary is None
            and not screening_exclusion_records
            and any(
                (root / filename).is_file()
                for filename in _DOWNSTREAM_COMPONENT_ARTIFACTS
            )
        )
        provenance_path = root / COMPONENT_PROVENANCE_FILENAME
        is_downstream_only = snapshot_manifest is None and (
            bool(downstream_record_count)
            or has_empty_downstream_component
            or provenance_path.is_file()
        )
        if is_downstream_only and active_screening_snapshot_ordinal is None:
            raise CycleAssemblyError(
                "downstream-only batch root must immediately follow a non-empty "
                "screening snapshot root or an ordered downstream component tied "
                f"to that snapshot: {root}"
            )
        if snapshot_manifest is not None:
            snapshot_cycle_hash = _required_sha256_field(
                snapshot_manifest, "cycle_hash", artifact="snapshot manifest"
            )
            snapshot_batch_digest = _required_sha256_field(
                snapshot_manifest, "batch_digest", artifact="snapshot manifest"
            )
            snapshot_manifest_sha256 = _hash_file(root / "manifest.json")[0]
            if snapshot_batch_digest in seen_snapshot_batch_digests:
                raise CycleAssemblyError(
                    f"duplicate snapshot batch digest: {snapshot_batch_digest}"
                )
            if snapshot_manifest_sha256 in seen_snapshot_manifest_sha256s:
                raise CycleAssemblyError(
                    f"duplicate snapshot manifest: {snapshot_manifest_sha256}"
                )
            seen_snapshot_batch_digests.add(snapshot_batch_digest)
            seen_snapshot_manifest_sha256s.add(snapshot_manifest_sha256)
            active_snapshot_cycle_hash = snapshot_cycle_hash
            active_snapshot_batch_digest = snapshot_batch_digest
            active_snapshot_manifest_sha256 = snapshot_manifest_sha256
            predecessor_provenance_sha256 = snapshot_manifest_sha256
            active_screening_snapshot_ordinal = ordinal
            active_screening_snapshot_root = root.name
            downstream_component_ordinal = 0
            active_component_stage_rank = 0
        elif is_downstream_only:
            if downstream_component_ordinal is None:  # pragma: no cover - invariant
                raise CycleAssemblyError("missing downstream component ordinal")
            downstream_component_ordinal += 1
        else:
            active_screening_snapshot_ordinal = None
            active_screening_snapshot_root = None
            downstream_component_ordinal = None
            active_snapshot_cycle_hash = None
            active_snapshot_batch_digest = None
            active_snapshot_manifest_sha256 = None
            predecessor_provenance_sha256 = None
            active_component_stage_rank = 0

        has_downstream_component = (
            bool(downstream_record_count)
            or (
                snapshot_manifest is not None
                and any(
                    (root / filename).is_file()
                    for filename in _DOWNSTREAM_COMPONENT_ARTIFACTS
                )
            )
            or has_empty_downstream_component
            or provenance_path.is_file()
        )
        component_provenance_sha256: str | None = None
        if has_downstream_component:
            if snapshot_manifest is not None:
                downstream_component_ordinal = 1
            if (
                active_snapshot_cycle_hash is None
                or active_snapshot_batch_digest is None
                or active_snapshot_manifest_sha256 is None
                or predecessor_provenance_sha256 is None
                or downstream_component_ordinal is None
            ):
                raise CycleAssemblyError(
                    f"downstream component has no verified snapshot binding: {root}"
                )
            (
                component_provenance_sha256,
                active_component_stage_rank,
            ) = _verify_component_provenance(
                root,
                expected_cycle_hash=active_snapshot_cycle_hash,
                expected_batch_digest=active_snapshot_batch_digest,
                expected_snapshot_manifest_sha256=(active_snapshot_manifest_sha256),
                expected_component_ordinal=downstream_component_ordinal,
                expected_predecessor_sha256=predecessor_provenance_sha256,
                previous_stage_rank=active_component_stage_rank,
            )
            predecessor_provenance_sha256 = component_provenance_sha256
        if _root_input_fingerprint(root) != input_fingerprint:
            raise CycleAssemblyError(f"batch root changed during assembly: {root}")
        _validate_discovery_counts(
            root,
            summary=summary,
            screened_count=len(screened_records),
            exclusion_count=len(screening_exclusion_records),
        )
        _apply_discovery_batch(current, screened_records, exclusion_records)
        _merge_latest(
            selections,
            batch_selections,
            artifact="selection",
        )
        _merge_latest(
            paid_gaps,
            batch_paid_gaps,
            artifact="paid-gap",
        )
        _reject_duplicate_ids(batch_relevance, artifact="case-relevance")
        _merge_latest(relevance, batch_relevance, artifact="case-relevance")
        _merge_latest(
            filters,
            batch_filters,
            artifact="core-filter-result",
        )
        for record in batch_manifest:
            prepared = _prepare_document(root, output, record)
            key = _document_key(record)
            prior = manifest.get(key)
            if prior is not None and _required_string(
                prior, "sha256"
            ) != _required_string(record, "sha256"):
                raise CycleAssemblyError(
                    f"conflicting content hashes for document {key[0]}:{key[1]}"
                )
            manifest[key] = prepared.record
            prepared_by_key[key] = prepared
        batch_provenance.append(
            {
                "batch_ordinal": ordinal,
                "batch_root": root.name,
                "screening_snapshot_batch_ordinal": (active_screening_snapshot_ordinal),
                "screening_snapshot_root": active_screening_snapshot_root,
                "downstream_component_ordinal": downstream_component_ordinal,
                "cycle_hash": active_snapshot_cycle_hash,
                "batch_digest": active_snapshot_batch_digest,
                "snapshot_manifest_sha256": active_snapshot_manifest_sha256,
                "component_provenance_sha256": component_provenance_sha256,
                "screened_case_count": len(screened_records),
                "discovery_exclusion_count": len(screening_exclusion_records),
                "downstream_exclusion_count": len(downstream_exclusion_records),
                "document_count": len(batch_manifest),
                "summary_sha256": _optional_file_hash(root / "summary.json"),
                "summary": summary,
            }
        )
    accepted_ids = {
        candidate_id
        for candidate_id, (state, _) in current.items()
        if state == "accepted"
    }
    selections = _retain_candidates(selections, accepted_ids)
    paid_gaps = _retain_candidates(paid_gaps, accepted_ids)
    relevance = _retain_candidates(relevance, accepted_ids)
    filters = _retain_candidates(filters, accepted_ids)
    manifest = {
        key: record for key, record in manifest.items() if key[0] in accepted_ids
    }
    prepared_by_key = {
        key: document
        for key, document in prepared_by_key.items()
        if key[0] in accepted_ids
    }

    missing_relevance = sorted(set(selections) - set(relevance))
    orphan_relevance = sorted(set(relevance) - set(selections))
    if missing_relevance or orphan_relevance:
        raise CycleAssemblyError(
            "every selected candidate must have exactly one relevance record; "
            f"missing={missing_relevance}, orphan={orphan_relevance}"
        )

    screened = tuple(
        record
        for _, record in sorted(current.values(), key=lambda item: _record_id(item[1]))
        if _state_for_record(current, record) == "accepted"
    )
    exclusions = tuple(
        record
        for state, record in sorted(
            current.values(), key=lambda item: _record_id(item[1])
        )
        if state == "excluded"
    )
    documents = tuple(prepared_by_key[key] for key in sorted(prepared_by_key))
    assembled = CycleAssembly(
        screened_cases=screened,
        discovery_exclusions=exclusions,
        selections=_sorted_values(selections),
        paid_gaps=_sorted_values(paid_gaps),
        case_relevance=_sorted_values(relevance),
        core_filter_results=_sorted_values(filters),
        document_manifest=tuple(manifest[key] for key in sorted(manifest)),
        documents=documents,
        summary={
            "schema": ASSEMBLY_SCHEMA,
            "cycle_hash": expected_cycle_hash,
            "batch_count": len(roots),
            "batches": batch_provenance,
            "record_counts": {
                "screened_cases": len(screened),
                "discovery_exclusions": len(exclusions),
                "selections": len(selections),
                "paid_gaps": len(paid_gaps),
                "case_relevance": len(relevance),
                "core_filter_results": len(filters),
                "documents": len(manifest),
            },
        },
    )
    if copy_documents:
        _publish_documents(assembled.documents)
    return assembled


def write_component_provenance(
    root: Path,
    *,
    source_snapshot_manifest: Path,
    component_ordinal: int,
    predecessor_sha256: str,
    component_stage: str,
) -> Path:
    """Commit one downstream root to a verified snapshot and predecessor chain."""

    if component_ordinal < 1:
        raise CycleAssemblyError("component ordinal must be positive")
    if _SHA256.fullmatch(predecessor_sha256) is None:
        raise CycleAssemblyError("predecessor SHA-256 is invalid")
    if component_stage not in COMPONENT_STAGE_ORDER:
        raise CycleAssemblyError(f"invalid component stage: {component_stage}")
    try:
        parsed = cast(object, json.loads(source_snapshot_manifest.read_text()))
    except (OSError, json.JSONDecodeError) as exc:
        raise CycleAssemblyError(f"invalid source snapshot manifest: {exc}") from exc
    if not isinstance(parsed, dict):
        raise CycleAssemblyError("source snapshot manifest must be a JSON object")
    manifest = cast(dict[str, object], parsed)
    cycle_hash = _required_sha256_field(
        manifest, "cycle_hash", artifact="snapshot manifest"
    )
    batch_digest = _required_sha256_field(
        manifest, "batch_digest", artifact="snapshot manifest"
    )
    snapshot_manifest_sha256 = _hash_file(source_snapshot_manifest)[0]
    files = _component_file_commitments(root)
    record = {
        "schema_version": COMPONENT_PROVENANCE_SCHEMA,
        "source_snapshot_cycle_hash": cycle_hash,
        "source_snapshot_batch_digest": batch_digest,
        "source_snapshot_manifest_sha256": snapshot_manifest_sha256,
        "component_ordinal": component_ordinal,
        "component_stage": component_stage,
        "predecessor_sha256": predecessor_sha256,
        "files": files,
    }
    path = root / COMPONENT_PROVENANCE_FILENAME
    payload = (
        json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    try:
        with path.open("xb") as stream:
            stream.write(payload)
    except FileExistsError as exc:
        _require_contained_regular_file(path, root=root)
        if path.read_bytes() != payload:
            raise CycleAssemblyError(
                f"component provenance already exists with different content: {path}"
            ) from exc
    return path


def _verified_snapshot_manifest(
    root: Path, *, expected_cycle_hash: str
) -> Mapping[str, Any] | None:
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        return None
    try:
        return verify_snapshot(
            root,
            expected_cycle_hash=expected_cycle_hash,
            require_complete=True,
            require_saturated=True,
        )
    except SnapshotVerificationError as exc:
        raise CycleAssemblyError(f"invalid screening snapshot {root}: {exc}") from exc


def _verify_component_provenance(
    root: Path,
    *,
    expected_cycle_hash: str,
    expected_batch_digest: str,
    expected_snapshot_manifest_sha256: str,
    expected_component_ordinal: int,
    expected_predecessor_sha256: str,
    previous_stage_rank: int,
) -> tuple[str, int]:
    path = root / COMPONENT_PROVENANCE_FILENAME
    if path.exists():
        _require_contained_regular_file(path, root=root)
    try:
        parsed = cast(object, json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        raise CycleAssemblyError(
            f"missing or invalid downstream component provenance for {root}: {exc}"
        ) from exc
    if not isinstance(parsed, dict):
        raise CycleAssemblyError(f"component provenance must be an object: {root}")
    record = cast(dict[str, object], parsed)
    expected_fields = {
        "schema_version",
        "source_snapshot_cycle_hash",
        "source_snapshot_batch_digest",
        "source_snapshot_manifest_sha256",
        "component_ordinal",
        "component_stage",
        "predecessor_sha256",
        "files",
    }
    if set(record) != expected_fields:
        raise CycleAssemblyError(f"component provenance fields are incomplete: {root}")
    if record.get("schema_version") != COMPONENT_PROVENANCE_SCHEMA:
        raise CycleAssemblyError(f"component provenance schema mismatch: {root}")
    component_stage = record.get("component_stage")
    if not isinstance(component_stage, str) or (
        component_stage not in COMPONENT_STAGE_ORDER
    ):
        raise CycleAssemblyError(f"component provenance stage is invalid: {root}")
    stage_rank = COMPONENT_STAGE_ORDER[component_stage]
    if stage_rank <= previous_stage_rank:
        raise CycleAssemblyError(
            f"component stage order is invalid for {root}: {component_stage}"
        )
    commitments = {
        "source_snapshot_cycle_hash": expected_cycle_hash,
        "source_snapshot_batch_digest": expected_batch_digest,
        "source_snapshot_manifest_sha256": expected_snapshot_manifest_sha256,
        "component_ordinal": expected_component_ordinal,
        "predecessor_sha256": expected_predecessor_sha256,
    }
    for field, expected in commitments.items():
        if record.get(field) != expected:
            raise CycleAssemblyError(
                f"component provenance {field} mismatch for {root}: "
                f"expected {expected}, got {record.get(field)}"
            )
    actual_files = _component_file_commitments(root)
    if record.get("files") != actual_files:
        raise CycleAssemblyError(f"component artifact commitment mismatch: {root}")
    return _hash_file(path)[0], stage_rank


def _component_file_commitments(root: Path) -> dict[str, dict[str, int | str]]:
    commitments: dict[str, dict[str, int | str]] = {}
    for filename in sorted(set(_DOWNSTREAM_COMPONENT_ARTIFACTS)):
        path = root / filename
        if not path.is_file():
            continue
        _require_contained_regular_file(path, root=root)
        sha256, byte_count = _hash_file(path)
        commitments[filename] = {
            "sha256": sha256,
            "byte_count": byte_count,
        }
    return commitments


def _required_sha256_field(
    record: Mapping[str, Any], field: str, *, artifact: str
) -> str:
    value = record.get(field)
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise CycleAssemblyError(f"{artifact} {field} must be a lowercase SHA-256")
    return value


def _root_input_fingerprint(root: Path) -> tuple[tuple[str, str, int], ...]:
    filenames = {
        *_SCREENED_ARTIFACTS,
        *_SCREENING_EXCLUSION_ARTIFACTS,
        *_DOWNSTREAM_COMPONENT_ARTIFACTS,
        "summary.json",
        "manifest.json",
        COMPONENT_PROVENANCE_FILENAME,
    }
    fingerprint: list[tuple[str, str, int]] = []
    for filename in sorted(filenames):
        path = root / filename
        if not path.is_file():
            continue
        sha256, byte_count = _hash_file(path)
        fingerprint.append((filename, sha256, byte_count))
    return tuple(fingerprint)


def _validated_batch_roots(
    batch_roots: Sequence[Path], *, output_root: Path
) -> tuple[Path, ...]:
    if not batch_roots:
        raise CycleAssemblyError("at least one batch root is required")
    output = output_root.absolute()
    roots: list[Path] = []
    seen: set[Path] = set()
    for root_input in batch_roots:
        root = root_input.absolute()
        if not root.is_dir():
            raise CycleAssemblyError(f"batch root is not a directory: {root}")
        _reject_symlink_components(root)
        resolved = root.resolve(strict=True)
        if resolved in seen:
            raise CycleAssemblyError(f"duplicate batch root: {root}")
        output_resolved = output.resolve(strict=False)
        if (
            resolved == output_resolved
            or resolved in output_resolved.parents
            or output_resolved in resolved.parents
        ):
            raise CycleAssemblyError(
                "output root must not contain or equal a batch root"
            )
        seen.add(resolved)
        roots.append(root)
    return tuple(roots)


def _apply_discovery_batch(
    current: dict[str, tuple[str, Mapping[str, Any]]],
    screened: Sequence[Mapping[str, Any]],
    exclusions: Sequence[Mapping[str, Any]],
) -> None:
    _reject_duplicate_ids(screened, artifact="screened")
    _reject_duplicate_ids(exclusions, artifact="discovery-exclusion")
    accepted = {_record_id(record): record for record in screened}
    excluded = {_record_id(record): record for record in exclusions}
    overlap = sorted(set(accepted) & set(excluded))
    if overlap:
        raise CycleAssemblyError(
            f"batch contains candidates in screened and excluded outputs: {overlap}"
        )
    for candidate_id, record in excluded.items():
        reason = _exclusion_reason(record)
        prior = current.get(candidate_id)
        if prior is not None and (
            (prior[0] == "accepted" and reason in _TRANSIENT_EXCLUSION_REASONS)
            or (
                prior[0] == "excluded"
                and _exclusion_reason(prior[1]) in _IMMUTABLE_EXCLUSION_REASONS
                and reason not in _IMMUTABLE_EXCLUSION_REASONS
            )
        ):
            continue
        current[candidate_id] = ("excluded", record)
    for candidate_id, record in accepted.items():
        prior = current.get(candidate_id)
        if prior is not None and prior[0] == "excluded":
            if _exclusion_reason(prior[1]) in _IMMUTABLE_EXCLUSION_REASONS:
                continue
        current[candidate_id] = ("accepted", record)


def _prepare_document(
    batch_root: Path, output_root: Path, record: Mapping[str, Any]
) -> PreparedDocument:
    relative = _safe_relative_path(_required_string(record, "local_path"))
    if relative.parts and relative.parts[0] == "documents":
        relative = PurePosixPath(*relative.parts[1:])
    document_root = batch_root / "documents"
    source = document_root.joinpath(*relative.parts)
    _require_contained_regular_file(source, root=document_root)
    expected_hash = _required_sha256(record)
    actual_hash, byte_count = _hash_file(source)
    if actual_hash != expected_hash:
        raise CycleAssemblyError(
            f"document hash mismatch for {source}: expected {expected_hash}, "
            f"got {actual_hash}"
        )
    committed_bytes = record.get("byte_count")
    if isinstance(committed_bytes, int) and committed_bytes != byte_count:
        raise CycleAssemblyError(
            f"document byte-count mismatch for {source}: "
            f"expected {committed_bytes}, got {byte_count}"
        )
    suffix = source.suffix.lower() or ".bin"
    destination_relative = PurePosixPath(
        "sha256", expected_hash[:2], f"{expected_hash}{suffix}"
    )
    destination = output_root / "documents" / Path(destination_relative)
    _require_safe_destination(
        destination, root=output_root / "documents", expected_hash=expected_hash
    )
    rebased = dict(record)
    rebased["local_path"] = destination_relative.as_posix()
    rebased["sha256"] = expected_hash
    rebased["byte_count"] = byte_count
    return PreparedDocument(source=source, destination=destination, record=rebased)


def _publish_documents(documents: Sequence[PreparedDocument]) -> None:
    for document in documents:
        destination = document.destination
        if destination.exists():
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
        created_temporary = False
        try:
            try:
                with (
                    temporary.open("xb") as target,
                    document.source.open("rb") as source,
                ):
                    created_temporary = True
                    shutil.copyfileobj(source, target)
            except FileExistsError as exc:
                raise CycleAssemblyError(
                    f"temporary publication path already exists: {temporary}"
                ) from exc
            copied_hash, _ = _hash_file(temporary)
            expected = _required_string(document.record, "sha256")
            if copied_hash != expected:
                raise CycleAssemblyError(
                    f"post-copy hash mismatch for {destination}: expected {expected}, "
                    f"got {copied_hash}"
                )
            os.replace(temporary, destination)
        finally:
            if created_temporary:
                temporary.unlink(missing_ok=True)


def _require_safe_destination(
    destination: Path, *, root: Path, expected_hash: str
) -> None:
    resolved_root = root.resolve(strict=False)
    if resolved_root not in destination.resolve(strict=False).parents:
        raise CycleAssemblyError(
            f"destination escapes cycle document root: {destination}"
        )
    if root.exists():
        _reject_symlink_components(root)
    cursor = root
    for part in destination.relative_to(root).parts:
        cursor /= part
        if cursor.is_symlink():
            raise CycleAssemblyError(f"symlink in destination path: {cursor}")
    if destination.exists():
        if not destination.is_file():
            raise CycleAssemblyError(
                f"destination is not a regular file: {destination}"
            )
        actual, _ = _hash_file(destination)
        if actual != expected_hash:
            raise CycleAssemblyError(
                f"content-addressed destination collision at {destination}: "
                f"expected {expected_hash}, got {actual}"
            )


def _require_contained_regular_file(path: Path, *, root: Path) -> None:
    _reject_symlink_components(root)
    cursor = root
    for part in path.relative_to(root).parts:
        cursor /= part
        if cursor.is_symlink():
            raise CycleAssemblyError(f"symlink in source path: {cursor}")
    try:
        source_stat = path.stat(follow_symlinks=False)
    except FileNotFoundError as exc:
        raise CycleAssemblyError(f"manifest document does not exist: {path}") from exc
    if not stat.S_ISREG(source_stat.st_mode):
        raise CycleAssemblyError(f"manifest document is not a regular file: {path}")
    if source_stat.st_nlink != 1:
        raise CycleAssemblyError(
            f"hardlinked source document is forbidden in an immutable batch: {path}"
        )
    resolved_root = root.resolve(strict=True)
    if resolved_root not in path.resolve(strict=True).parents:
        raise CycleAssemblyError(
            f"manifest document escapes batch document root: {path}"
        )


def _reject_symlink_components(path: Path) -> None:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        if current.is_symlink():
            raise CycleAssemblyError(f"symlink in trusted root path: {current}")


def _safe_relative_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise CycleAssemblyError(f"unsafe document local_path: {value!r}")
    return path


def _read_first_jsonl(root: Path, filenames: Sequence[str]) -> list[Mapping[str, Any]]:
    for filename in filenames:
        path = root / filename
        if path.is_file():
            return _read_jsonl(path)
    return []


def _read_jsonl_union(root: Path, filenames: Sequence[str]) -> list[Mapping[str, Any]]:
    records: list[Mapping[str, Any]] = []
    for filename in filenames:
        path = root / filename
        if path.is_file():
            records.extend(_read_jsonl(path))
    return records


def _read_jsonl(path: Path) -> list[Mapping[str, Any]]:
    records: list[Mapping[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise CycleAssemblyError(f"{path}:{line_number} is not a JSON object")
            records.append(
                _canonicalize_courtlistener_identity(cast(dict[str, Any], value))
            )
    return records


def _canonicalize_courtlistener_identity(
    record: Mapping[str, Any],
) -> Mapping[str, Any]:
    aliases: set[str] = set()
    numeric_ids: set[str] = set()
    for key in ("candidate_id", "case_id", "docket_id"):
        value = record.get(key)
        if isinstance(value, str):
            normalized = value.strip()
            if match := _COURTLISTENER_NAMESPACED_ID.fullmatch(normalized):
                aliases.add(match.group(1))
            elif normalized.isdecimal():
                numeric_ids.add(normalized)
    candidate = record.get("candidate")
    nested_docket_id: str | None = None
    if isinstance(candidate, Mapping):
        candidate_record = cast(Mapping[str, Any], candidate)
        value = candidate_record.get("docket_id")
        if isinstance(value, str) and value.strip():
            nested_docket_id = value.strip()
    if not aliases:
        return record
    if len(aliases) != 1:
        raise CycleAssemblyError("CourtListener identity alias conflict")
    canonical = next(iter(aliases))
    if any(value != canonical for value in numeric_ids):
        raise CycleAssemblyError(
            "CourtListener identity alias conflict: "
            f"namespaced={canonical}, numeric_ids={sorted(numeric_ids)}"
        )
    if nested_docket_id is not None and nested_docket_id != canonical:
        raise CycleAssemblyError(
            "CourtListener identity alias conflict: "
            f"namespaced={canonical}, nested_docket_id={nested_docket_id}"
        )
    normalized = dict(record)
    source_candidate_id = record.get("candidate_id")
    if isinstance(source_candidate_id, str) and _COURTLISTENER_NAMESPACED_ID.fullmatch(
        source_candidate_id.strip()
    ):
        normalized["source_candidate_id"] = source_candidate_id.strip()
    for key in ("candidate_id", "case_id", "docket_id"):
        value = record.get(key)
        if isinstance(value, str) and _COURTLISTENER_NAMESPACED_ID.fullmatch(
            value.strip()
        ):
            normalized[key] = canonical
    return normalized


def _read_optional_json(path: Path) -> Mapping[str, Any] | None:
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CycleAssemblyError(f"{path} is not a JSON object")
    return cast(dict[str, Any], value)


def _validate_discovery_counts(
    root: Path,
    *,
    summary: Mapping[str, Any] | None,
    screened_count: int,
    exclusion_count: int,
) -> None:
    if summary is None:
        return
    expected = (
        (("accepted_case_count", "accepted_count"), screened_count),
        (("excluded_case_count", "excluded_count"), exclusion_count),
    )
    for aliases, actual in expected:
        committed_values = [
            (key, summary[key]) for key in aliases if isinstance(summary.get(key), int)
        ]
        for key, committed in committed_values:
            if committed != actual:
                raise CycleAssemblyError(
                    f"discovery count reconciliation failed for {root}: "
                    f"{key}={committed}, actual={actual}"
                )


def _merge_latest(
    target: dict[str, Mapping[str, Any]],
    records: Sequence[Mapping[str, Any]],
    *,
    artifact: str,
) -> None:
    _reject_duplicate_ids(records, artifact=artifact)
    for record in records:
        target[_record_id(record)] = record


def _reject_duplicate_ids(
    records: Sequence[Mapping[str, Any]], *, artifact: str
) -> None:
    counts = Counter(_record_id(record) for record in records)
    duplicates = sorted(key for key, count in counts.items() if count != 1)
    if duplicates:
        raise CycleAssemblyError(
            f"duplicate {artifact} candidate records: {duplicates}"
        )


def _record_id(record: Mapping[str, Any]) -> str:
    for key in ("candidate_id", "case_id", "docket_id"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise CycleAssemblyError(
        "artifact record lacks candidate_id, case_id, or docket_id"
    )


def _document_key(record: Mapping[str, Any]) -> tuple[str, str]:
    return _record_id(record), _required_string(record, "source_document_id")


def _retain_candidates(
    records: Mapping[str, Mapping[str, Any]], candidate_ids: set[str]
) -> dict[str, Mapping[str, Any]]:
    return {
        candidate_id: record
        for candidate_id, record in records.items()
        if candidate_id in candidate_ids
    }


def _required_string(record: Mapping[str, Any], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CycleAssemblyError(f"artifact record requires nonempty {key}")
    return value.strip()


def _required_sha256(record: Mapping[str, Any]) -> str:
    value = _required_string(record, "sha256").lower()
    if len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise CycleAssemblyError(f"invalid sha256 commitment: {value!r}")
    return value


def _exclusion_reason(record: Mapping[str, Any]) -> str:
    for key in (
        "primary_exclusion_reason",
        "reason",
        "reason_code",
        "exclusion_reason",
    ):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    reasons = record.get("exclusion_reasons")
    if isinstance(reasons, Sequence) and not isinstance(reasons, str):
        for reason in cast(Sequence[object], reasons):
            if isinstance(reason, str) and reason.strip():
                return reason.strip().lower()
    raise CycleAssemblyError("discovery exclusion lacks a reason code")


def _state_for_record(
    current: Mapping[str, tuple[str, Mapping[str, Any]]], record: Mapping[str, Any]
) -> str:
    return current[_record_id(record)][0]


def _sorted_values(
    records: Mapping[str, Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ...]:
    return tuple(records[key] for key in sorted(records))


def _hash_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    byte_count = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
            byte_count += len(chunk)
    return digest.hexdigest(), byte_count


def _optional_file_hash(path: Path) -> str | None:
    return _hash_file(path)[0] if path.is_file() else None
