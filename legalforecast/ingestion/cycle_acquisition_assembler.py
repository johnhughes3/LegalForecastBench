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

ASSEMBLY_SCHEMA = "legalforecast.cycle_acquisition_assembly.v1"

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
        "firecrawl_provider_blocker",
    }
)
_COURTLISTENER_NAMESPACED_ID = re.compile(r"courtlistener-docket-(\d+)\Z")


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
    output_root: Path,
    copy_documents: bool,
) -> CycleAssembly:
    """Validate, reconcile, and optionally publish immutable acquisition batches."""

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

    for ordinal, root in enumerate(roots, start=1):
        screened_records = _read_first_jsonl(
            root, ("screened-cases.jsonl", "courtlistener-screened-cases.jsonl")
        )
        screening_exclusion_records = _read_jsonl_union(
            root,
            (
                "exclusions.jsonl",
                "discovery-exclusions.jsonl",
                "courtlistener-discovery-exclusions.jsonl",
            ),
        )
        downstream_exclusion_records = _read_jsonl_union(
            root,
            (
                "public-packet-exclusions.jsonl",
                "pacer-gap-bridge-exclusions.jsonl",
            ),
        )
        exclusion_records = [
            *screening_exclusion_records,
            *downstream_exclusion_records,
        ]
        summary = _read_optional_json(root / "summary.json")
        _validate_discovery_counts(
            root,
            summary=summary,
            screened_count=len(screened_records),
            exclusion_count=len(screening_exclusion_records),
        )
        _apply_discovery_batch(current, screened_records, exclusion_records)
        _merge_latest(
            selections,
            _read_first_jsonl(
                root,
                (
                    "public-packet-selection-reconciled.jsonl",
                    "public-packet-selection.jsonl",
                ),
            ),
            artifact="selection",
        )
        _merge_latest(
            paid_gaps,
            _read_first_jsonl(root, ("public-packet-paid-gaps.jsonl",)),
            artifact="paid-gap",
        )
        batch_relevance = _read_first_jsonl(root, ("case-relevance.jsonl",))
        _reject_duplicate_ids(batch_relevance, artifact="case-relevance")
        _merge_latest(relevance, batch_relevance, artifact="case-relevance")
        _merge_latest(
            filters,
            _read_first_jsonl(root, ("core-filter-results.jsonl",)),
            artifact="core-filter-result",
        )
        batch_manifest = _read_first_jsonl(
            root,
            (
                "document-downloads-merged.jsonl",
                "free-document-downloads.jsonl",
            ),
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
    for key in ("candidate_id", "case_id", "docket_id"):
        value = record.get(key)
        if isinstance(value, str) and (
            match := _COURTLISTENER_NAMESPACED_ID.fullmatch(value.strip())
        ):
            aliases.add(match.group(1))
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
    if (
        isinstance(reasons, Sequence)
        and not isinstance(reasons, str)
        and reasons
        and isinstance(reasons[0], str)
        and reasons[0].strip()
    ):
        return reasons[0].strip().lower()
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
