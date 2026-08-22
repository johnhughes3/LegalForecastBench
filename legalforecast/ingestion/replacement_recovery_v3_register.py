"""Authenticated v3 document bridge for replacement-recovery consolidation."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, MutableMapping, Sequence
from pathlib import Path
from typing import Any, Protocol, cast

from legalforecast.contracts import (
    EXACT100_SUCCESSOR_REPLACEMENT_STATE_V2,
    EXACT100_SUCCESSOR_REPLACEMENT_STATE_V3,
)
from legalforecast.ingestion.disclosure_clearance import (
    PAID_DELIVERY_RESTRICTION_EVIDENCE,
    SCHEMA_VERSION,
)
from legalforecast.ingestion.supporting_document_successor import (
    SCHEMA_VERSION as SUPPORTING_DOCUMENT_SUCCESSOR_SCHEMA_VERSION,
)

DocumentKey = tuple[str, str]
JsonRecord = dict[str, Any]

_LEGACY_PAID_CLEARANCE_FIELDS = frozenset(
    {
        "byte_count",
        "candidate_id",
        "clearance_basis",
        "free_or_purchased",
        "local_path",
        "sha256",
        "source_document_id",
        "status",
    }
)
_PAID_RESTRICTION_FIELDS = frozenset(
    {
        "candidate_id",
        "is_private",
        "is_sealed",
        "restriction_evidence",
        "restriction_status",
        "source_document_id",
    }
)


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


def admit_authenticated_v3_register_clearance_rows(
    *,
    manifest_records: Sequence[Mapping[str, Any]],
    clearance_records: Sequence[Mapping[str, Any]],
    restriction_records: Sequence[Mapping[str, Any]],
    authenticated_clearance_bytes: object,
    authenticated_restriction_bytes: object,
    external_document_commitments: Mapping[DocumentKey, str],
) -> tuple[JsonRecord, ...]:
    """Admit the historical paid-delivery clearance shape for v3 only.

    The v3 consolidation capability authenticates the exact clearance and
    restriction bytes before this helper is called.  We nevertheless compare
    those bytes again at the admission boundary so that callers cannot turn a
    caller-supplied mapping into authority.  Only the register-backed rows
    lacking the canonical schema are enriched, and the enrichment is an
    invocation-local copy; the frozen root-60 artifact is never rewritten.
    """

    if not isinstance(authenticated_clearance_bytes, bytes) or not isinstance(
        authenticated_restriction_bytes, bytes
    ):
        raise ValueError("v3 clearance admission requires authenticated bytes")
    clearance_bytes = authenticated_clearance_bytes
    restriction_bytes = authenticated_restriction_bytes
    if _jsonl_bytes(clearance_records) != clearance_bytes:
        raise ValueError("v3 clearance admission differs from authenticated bytes")
    if _jsonl_bytes(restriction_records) != restriction_bytes:
        raise ValueError("v3 restriction admission differs from authenticated bytes")

    manifest_by_key = _index(
        manifest_records, label="authenticated v3 purchased manifest"
    )
    clearance_by_key = _index(
        clearance_records, label="authenticated v3 purchased clearance"
    )
    restriction_by_key = _index(
        restriction_records, label="authenticated v3 purchased restriction"
    )
    register_keys = set(external_document_commitments)
    if not register_keys <= set(manifest_by_key) or not register_keys <= set(
        clearance_by_key
    ):
        raise ValueError("v3 register commitments lack matching clearance coverage")

    for key, clearance in clearance_by_key.items():
        if "schema_version" not in clearance:
            if key not in register_keys:
                raise ValueError(
                    f"v3 clearance row lacks schema outside register coverage: {key}"
                )
            if frozenset(clearance) != _LEGACY_PAID_CLEARANCE_FIELDS:
                raise ValueError(
                    f"v3 register-backed legacy clearance shape differs: {key}"
                )
            if (
                clearance.get("clearance_basis") != "paid_delivery"
                or clearance.get("free_or_purchased") != "purchased"
                or clearance.get("status") != "cleared"
            ):
                raise ValueError(
                    "v3 register-backed legacy clearance is not paid and cleared: "
                    f"{key}"
                )

            manifest = manifest_by_key[key]
            if (
                any(
                    clearance.get(field) != manifest.get(field)
                    for field in (
                        "candidate_id",
                        "source_document_id",
                        "free_or_purchased",
                        "local_path",
                        "sha256",
                        "byte_count",
                    )
                )
                or manifest.get("free_or_purchased") != "purchased"
            ):
                raise ValueError(
                    f"v3 register-backed clearance differs from manifest: {key}"
                )
            expected_sha256 = external_document_commitments.get(key)
            if (
                not isinstance(expected_sha256, str)
                or clearance.get("sha256") != expected_sha256
            ):
                raise ValueError(
                    f"v3 register-backed clearance differs from register: {key}"
                )

            restriction = restriction_by_key.get(key)
            if restriction is None or (
                frozenset(restriction) != _PAID_RESTRICTION_FIELDS
            ):
                raise ValueError(
                    "v3 register-backed clearance lacks exact restriction evidence: "
                    f"{key}"
                )
            if (
                restriction.get("is_private") is not False
                or restriction.get("is_sealed") is not False
                or restriction.get("restriction_status") != "public"
                or restriction.get("restriction_evidence")
                != list(PAID_DELIVERY_RESTRICTION_EVIDENCE)
            ):
                raise ValueError(
                    "v3 register-backed restriction is not exact public evidence: "
                    f"{key}"
                )

    admitted: list[JsonRecord] = []
    for record in clearance_records:
        row = dict(record)
        if "schema_version" not in row:
            key = _key(row)
            restriction = restriction_by_key[key]
            row.update(
                {
                    "schema_version": SCHEMA_VERSION,
                    "is_private": restriction["is_private"],
                    "is_sealed": restriction["is_sealed"],
                    "restriction_status": restriction["restriction_status"],
                    "restriction_evidence": list(
                        cast(Sequence[str], restriction["restriction_evidence"])
                    ),
                }
            )
        admitted.append(row)
    return tuple(admitted)


def admit_authenticated_v3_register_lineage(
    recovery: Mapping[str, object],
    clearance_lineage: MutableMapping[str, object],
    consolidated_authority: Mapping[str, object] | None,
) -> None:
    """Apply v3-only clearance admission after all raw capability checks."""

    if consolidated_authority is None:
        return
    clearance_lineage["clearance_records"] = (
        admit_authenticated_v3_register_clearance_rows(
            manifest_records=cast(
                Sequence[Mapping[str, Any]], recovery["manifest_records"]
            ),
            clearance_records=cast(
                Sequence[Mapping[str, Any]], clearance_lineage["clearance_records"]
            ),
            restriction_records=cast(
                Sequence[Mapping[str, Any]],
                clearance_lineage["restriction_records"],
            ),
            authenticated_clearance_bytes=consolidated_authority["clearance_bytes"],
            authenticated_restriction_bytes=consolidated_authority["restriction_bytes"],
            external_document_commitments=cast(
                Mapping[DocumentKey, str],
                consolidated_authority["external_document_commitments"],
            ),
        )
    )


def _jsonl_bytes(records: Sequence[Mapping[str, Any]]) -> bytes:
    return "".join(
        f"{json.dumps(dict(record), sort_keys=True, allow_nan=False)}\n"
        for record in records
    ).encode("utf-8")


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
