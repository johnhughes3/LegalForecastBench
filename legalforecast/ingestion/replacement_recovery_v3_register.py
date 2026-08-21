"""Authenticated v3 document bridge for replacement-recovery consolidation."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping, MutableMapping, Sequence
from pathlib import Path
from typing import Any, Protocol, cast

from legalforecast.contracts import (
    EXACT100_SUCCESSOR_REPLACEMENT_STATE_V2,
    EXACT100_SUCCESSOR_REPLACEMENT_STATE_V3,
)
from legalforecast.ingestion.supporting_document_successor import (
    SCHEMA_VERSION as SUPPORTING_DOCUMENT_SUCCESSOR_SCHEMA_VERSION,
)

DocumentKey = tuple[str, str]
JsonRecord = dict[str, Any]


class _Register(Protocol):
    def commitment_map(self) -> Mapping[DocumentKey, str]: ...


def consolidation_legacy_target_root(
    target_projection: Mapping[str, object],
) -> Path:
    """Return the legacy target beneath an authenticated v2/v3 projection."""

    projection = target_projection
    run_card = projection.get("run_card")
    if not isinstance(run_card, Mapping):
        raise ValueError("exact100 target projection lacks an authenticated run card")
    card = cast(Mapping[str, object], run_card)
    schema_version = card.get("schema_version")
    if schema_version == str(EXACT100_SUCCESSOR_REPLACEMENT_STATE_V3):
        base = projection.get("base_projection")
        if not isinstance(base, Mapping):
            raise ValueError("exact100 v3 target lacks authenticated anchor projection")
        projection = cast(Mapping[str, object], base)
        run_card = projection.get("run_card")
        if not isinstance(run_card, Mapping) or (
            cast(Mapping[str, object], run_card).get("schema_version")
            != SUPPORTING_DOCUMENT_SUCCESSOR_SCHEMA_VERSION
        ):
            raise ValueError(
                "exact100 v3 target anchor is not a supporting-document successor"
            )
        base_v2 = projection.get("base_v2_projection")
        if not isinstance(base_v2, Mapping):
            raise ValueError("exact100 v3 target anchor lacks authenticated v2 base")
        run_card = cast(Mapping[str, object], base_v2).get("run_card")
        if not isinstance(run_card, Mapping):
            raise ValueError("exact100 v3 target v2 base lacks authenticated run card")
        card = cast(Mapping[str, object], run_card)
        schema_version = card.get("schema_version")
    if schema_version != str(EXACT100_SUCCESSOR_REPLACEMENT_STATE_V2):
        raise ValueError("exact100 target lineage does not terminate at a v2 successor")
    raw_inputs = card.get("input_paths")
    if not isinstance(raw_inputs, Sequence) or isinstance(raw_inputs, (str, bytes)):
        raise ValueError("exact100 v2 target lacks predecessor lineage")
    inputs = cast(Sequence[object], raw_inputs)
    if not inputs or not isinstance(inputs[0], str) or not inputs[0]:
        raise ValueError("exact100 v2 predecessor root is invalid")
    return Path(inputs[0]).absolute()


def verified_register_commitments(
    payload: bytes,
    *,
    canonical_operation_keys: set[DocumentKey],
    verify: Callable[[bytes], _Register],
) -> dict[DocumentKey, str]:
    """Verify the ratified register and reject canonical-ledger overlap."""

    commitments = dict(verify(payload).commitment_map())
    overlap = canonical_operation_keys & set(commitments)
    if overlap:
        raise ValueError(
            "external billing register overlaps canonical ledger coverage: "
            f"{sorted(overlap)[0]}"
        )
    return commitments


def merge_authenticated_v3_register_gap(
    *,
    target_root: Path,
    target_projection: Mapping[str, object],
    register_commitments: Mapping[DocumentKey, str],
    required_purchased_keys: set[DocumentKey],
    manifest_by_key: MutableMapping[DocumentKey, JsonRecord],
    clearance_by_key: MutableMapping[DocumentKey, JsonRecord],
    restriction_by_key: MutableMapping[DocumentKey, list[JsonRecord]],
    document_bytes: MutableMapping[str, bytes],
) -> None:
    """Fill a historical-index gap only from authenticated v3 projection bytes."""

    register_backed = required_purchased_keys & set(register_commitments)
    missing_manifest = register_backed - set(manifest_by_key)
    missing_clearance = register_backed - set(clearance_by_key)
    if missing_manifest != missing_clearance:
        raise ValueError(
            "authenticated v3 target register coverage is partially populated"
        )
    if not missing_manifest:
        return
    manifests = _index(
        target_projection.get("purchased_manifest"),
        label="authenticated v3 target purchased manifest",
    )
    clearances = _index(
        target_projection.get("purchased_clearance"),
        label="authenticated v3 target purchased clearance",
    )
    raw_documents = target_projection.get("verified_document_bytes")
    if not isinstance(raw_documents, Mapping):
        raise ValueError("authenticated v3 target lacks verified document bytes")
    verified_documents = cast(Mapping[str, object], raw_documents)
    for key in sorted(missing_manifest):
        manifest = manifests.get(key)
        clearance = clearances.get(key)
        if manifest is None or clearance is None:
            raise ValueError(
                f"authenticated v3 target lacks register-backed document: {key}"
            )
        if (
            manifest.get("free_or_purchased") != "purchased"
            or clearance.get("free_or_purchased") != "purchased"
            or clearance.get("status") != "cleared"
        ):
            raise ValueError(
                "authenticated v3 target register-backed document is not cleared: "
                f"{key}"
            )
        sha256 = _text(manifest, "sha256")
        byte_count = _integer(manifest, "byte_count")
        if (
            clearance.get("sha256") != sha256
            or clearance.get("byte_count") != byte_count
            or register_commitments[key] != sha256
        ):
            raise ValueError(
                f"authenticated v3 target register-backed metadata differs: {key}"
            )
        relative = Path(_text(manifest, "local_path"))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("authenticated v3 target local_path is unsafe")
        source_path = (
            target_root / "owner-adjudicated-source" / "documents" / relative
        ).absolute()
        payload = verified_documents.get(str(source_path))
        if (
            not isinstance(payload, bytes)
            or hashlib.sha256(payload).hexdigest() != sha256
            or len(payload) != byte_count
        ):
            raise ValueError(f"authenticated v3 target document bytes differ: {key}")
        consolidated = f"sha256/{sha256[:2]}/{sha256}.pdf"
        existing = document_bytes.get(consolidated)
        if existing is not None and existing != payload:
            raise ValueError("replacement recovery document hash collision")
        document_bytes[consolidated] = payload
        manifest_by_key[key] = {**manifest, "local_path": consolidated}
        clearance_by_key[key] = {**clearance, "local_path": consolidated}
    raw_restrictions = target_projection.get("restriction_records")
    if not isinstance(raw_restrictions, Sequence) or isinstance(
        raw_restrictions, (str, bytes)
    ):
        raise ValueError("authenticated v3 target lacks restriction records")
    for raw_record in cast(Sequence[object], raw_restrictions):
        if not isinstance(raw_record, Mapping):
            raise ValueError("authenticated v3 target restriction record is invalid")
        record = dict(cast(Mapping[str, Any], raw_record))
        key = _key(record)
        if key in missing_manifest:
            restriction_by_key[key].append(record)


def _index(raw_records: object, *, label: str) -> dict[DocumentKey, JsonRecord]:
    if not isinstance(raw_records, Sequence) or isinstance(raw_records, (str, bytes)):
        raise ValueError(f"{label} is not a list")
    result: dict[DocumentKey, JsonRecord] = {}
    for raw_record in cast(Sequence[object], raw_records):
        if not isinstance(raw_record, Mapping):
            raise ValueError(f"{label} contains a non-object")
        record = dict(cast(Mapping[str, Any], raw_record))
        key = _key(record)
        if key in result:
            raise ValueError(f"{label} repeats {key}")
        result[key] = record
    return result


def _key(record: Mapping[str, object]) -> DocumentKey:
    return (_text(record, "candidate_id"), _text(record, "source_document_id"))


def _text(record: Mapping[str, object], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"authenticated v3 target {field} is invalid")
    return value


def _integer(record: Mapping[str, object], field: str) -> int:
    value = record.get(field)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"authenticated v3 target {field} is invalid")
    return value
