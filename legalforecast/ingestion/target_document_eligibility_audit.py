"""Verifier-owned semantic eligibility audit for Stage A target documents.

The persisted JSONL is an audit surface, not authority by itself.  Only this
module's sealed result, which a higher-level lineage verifier creates from its
already-authenticated selection, parser manifest, and Markdown snapshots, may
be consumed to mint a terminal exclusion.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, cast

from legalforecast.contracts import TARGET_DOCUMENT_ELIGIBILITY_AUDIT_V1
from legalforecast.ingestion.canonical_json import canonical_json_bytes
from legalforecast.ingestion.frozen_replay_model_regime import (
    TARGET_ELIGIBILITY_REGIME_CURRENT,
)
from legalforecast.ingestion.provenance import DocumentRole
from legalforecast.ingestion.target_document_eligibility import (
    TargetDocumentEligibilityError,
    is_stipulated_or_voluntary_target_document,
)

JsonRecord = dict[str, Any]

AUDIT_SCHEMA_VERSION = str(TARGET_DOCUMENT_ELIGIBILITY_AUDIT_V1)
_VERIFICATION_SEAL = object()
_TARGET_ROLES = frozenset(
    {DocumentRole.MTD_NOTICE.value, DocumentRole.MTD_MEMORANDUM.value}
)


class TargetDocumentEligibilityAuditError(ValueError):
    """Raised when a target-document eligibility audit cannot be replayed."""


class TargetDocumentEligibilityStatus(StrEnum):
    """Closed semantic status for one selected target document."""

    ELIGIBLE = "eligible"
    STIPULATED_INELIGIBLE = "stipulated_ineligible"


@dataclass(frozen=True, slots=True, init=False)
class VerifiedTargetDocumentEligibilityAudit:
    """A deterministic audit minted only from verifier-owned input snapshots."""

    records: tuple[JsonRecord, ...]
    records_bytes: bytes
    selection_sha256: str
    input_commitments: Mapping[str, str]
    commitment_sha256: str
    _verification_seal: object = field(repr=False, compare=False)

    @property
    def ineligible_records(self) -> tuple[JsonRecord, ...]:
        """Return the closed semantic failures in selection/document order."""

        return tuple(
            record
            for record in self.records
            if record["status"]
            == TargetDocumentEligibilityStatus.STIPULATED_INELIGIBLE.value
        )


def _mint_verified_target_document_eligibility_audit(  # pyright: ignore[reportUnusedFunction]
    *,
    selection_bytes: bytes,
    parser_manifest_bytes: bytes,
    parser_records: Sequence[Mapping[str, Any]],
    markdown_by_document: Mapping[tuple[str, str], bytes],
    regime: str = TARGET_ELIGIBILITY_REGIME_CURRENT,
) -> VerifiedTargetDocumentEligibilityAudit:
    """Replay the semantic audit from already-authenticated parser snapshots.

    This is deliberately private: byte validation establishes only integrity.
    Production callers must first authenticate the complete materialization and
    parser lineage, then pass those verifier-owned snapshots here.

    ``regime`` names the detector generation that re-derives each verdict.  It
    defaults to today's detector; a caller replaying a frozen audit selects the
    generation contemporaneous with that audit through
    ``frozen_replay_model_regime``, keyed on the parse manifest digest it has
    already authenticated.  The regime never affects whether the replayed
    records must equal the persisted audit bytes -- only which model derives
    them.
    """

    selections = _jsonl_records(selection_bytes, "selection")
    manifest_records = _jsonl_records(parser_manifest_bytes, "parser manifest")
    supplied_parser_records = tuple(dict(record) for record in parser_records)
    if tuple(manifest_records) != supplied_parser_records:
        raise TargetDocumentEligibilityAuditError(
            "parser records differ from authenticated parser manifest"
        )
    parser_by_key = _unique_records_by_key(
        supplied_parser_records, label="parser manifest"
    )
    if set(markdown_by_document) != set(parser_by_key):
        raise TargetDocumentEligibilityAuditError(
            "Markdown snapshots differ from exact parser manifest"
        )
    _verify_markdown_snapshots(parser_by_key, markdown_by_document)

    records: list[JsonRecord] = []
    seen_candidates: set[str] = set()
    for selection in selections:
        candidate_id = _required_text(selection, "candidate_id")
        if candidate_id in seen_candidates:
            raise TargetDocumentEligibilityAuditError(
                f"selection contains duplicate candidate: {candidate_id}"
            )
        seen_candidates.add(candidate_id)
        documents = _mapping_sequence(selection.get("documents"), "selection documents")
        target_document_count = 0
        for document in documents:
            source_document_id = _required_text(document, "source_document_id")
            role = _required_text(document, "document_role")
            if role not in _TARGET_ROLES:
                continue
            target_document_count += 1
            key = (candidate_id, source_document_id)
            if key not in parser_by_key:
                raise TargetDocumentEligibilityAuditError(
                    "selected target document lacks authenticated parser output: "
                    f"{candidate_id}/{source_document_id}"
                )
            markdown_bytes = markdown_by_document[key]
            try:
                markdown = markdown_bytes.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise TargetDocumentEligibilityAuditError(
                    "target-document Markdown is not UTF-8: "
                    f"{candidate_id}/{source_document_id}"
                ) from exc
            try:
                stipulated = is_stipulated_or_voluntary_target_document(
                    candidate_id=candidate_id,
                    source_document_id=source_document_id,
                    document_role=role,
                    markdown=markdown,
                    regime=regime,
                )
            except TargetDocumentEligibilityError as exc:
                raise TargetDocumentEligibilityAuditError(str(exc)) from exc
            status = (
                TargetDocumentEligibilityStatus.STIPULATED_INELIGIBLE
                if stipulated
                else TargetDocumentEligibilityStatus.ELIGIBLE
            )
            records.append(
                {
                    "schema_version": AUDIT_SCHEMA_VERSION,
                    "candidate_id": candidate_id,
                    "source_document_id": source_document_id,
                    "document_role": role,
                    "status": status.value,
                    "markdown_sha256": _sha(markdown_bytes),
                }
            )
        if target_document_count == 0:
            raise TargetDocumentEligibilityAuditError(
                f"selection candidate lacks target-motion document: {candidate_id}"
            )
    if not selections:
        raise TargetDocumentEligibilityAuditError("selection has no candidates")

    records_tuple = tuple(records)
    records_bytes = _jsonl_bytes(records_tuple)
    input_commitments = {
        "selection": _sha(selection_bytes),
        "parser_manifest": _sha(parser_manifest_bytes),
        "markdown_tree": _markdown_tree_sha256(markdown_by_document),
    }
    result = object.__new__(VerifiedTargetDocumentEligibilityAudit)
    object.__setattr__(result, "records", records_tuple)
    object.__setattr__(result, "records_bytes", records_bytes)
    object.__setattr__(result, "selection_sha256", input_commitments["selection"])
    object.__setattr__(result, "input_commitments", input_commitments)
    object.__setattr__(result, "commitment_sha256", _sha(records_bytes))
    object.__setattr__(result, "_verification_seal", _VERIFICATION_SEAL)
    return result


def _replay_verified_target_document_eligibility_audit(  # pyright: ignore[reportUnusedFunction]
    *,
    persisted_audit_bytes: bytes,
    selection_bytes: bytes,
    parser_manifest_bytes: bytes,
    parser_records: Sequence[Mapping[str, Any]],
    markdown_by_document: Mapping[tuple[str, str], bytes],
    regime: str = TARGET_ELIGIBILITY_REGIME_CURRENT,
) -> VerifiedTargetDocumentEligibilityAudit:
    """Reconstruct and require exact equality with a persisted audit JSONL.

    ``regime`` selects which detector generation reconstructs the audit.  Byte
    equality with ``persisted_audit_bytes`` is required under every regime, so a
    preserved detector that derived anything other than the frozen verdicts
    would refuse here exactly as loudly as the current one does.
    """

    audit = _mint_verified_target_document_eligibility_audit(
        selection_bytes=selection_bytes,
        parser_manifest_bytes=parser_manifest_bytes,
        parser_records=parser_records,
        markdown_by_document=markdown_by_document,
        regime=regime,
    )
    if persisted_audit_bytes != audit.records_bytes:
        raise TargetDocumentEligibilityAuditError(
            "target-document eligibility audit differs from authenticated replay"
        )
    return audit


def require_verified_target_document_eligibility_audit(
    audit: VerifiedTargetDocumentEligibilityAudit,
) -> None:
    """Reject an altered or caller-constructed eligibility audit capability."""

    if (
        type(audit) is not VerifiedTargetDocumentEligibilityAudit
        or getattr(audit, "_verification_seal", None) is not _VERIFICATION_SEAL
        or audit.records_bytes != _jsonl_bytes(audit.records)
        or audit.commitment_sha256 != _sha(audit.records_bytes)
        or audit.selection_sha256 != audit.input_commitments.get("selection")
        or set(audit.input_commitments)
        != {"selection", "parser_manifest", "markdown_tree"}
        or any(not _is_sha256(value) for value in audit.input_commitments.values())
    ):
        raise TargetDocumentEligibilityAuditError(
            "target-document eligibility audit was not produced by verified replay"
        )
    _validate_audit_records(audit.records)


def _validate_audit_records(records: Sequence[Mapping[str, Any]]) -> None:
    seen: set[tuple[str, str]] = set()
    for record in records:
        if set(record) != {
            "schema_version",
            "candidate_id",
            "source_document_id",
            "document_role",
            "status",
            "markdown_sha256",
        }:
            raise TargetDocumentEligibilityAuditError(
                "target-document eligibility audit record fields differ"
            )
        candidate_id = _required_text(record, "candidate_id")
        source_document_id = _required_text(record, "source_document_id")
        if (candidate_id, source_document_id) in seen:
            raise TargetDocumentEligibilityAuditError(
                "target-document eligibility audit has duplicate target document"
            )
        seen.add((candidate_id, source_document_id))
        if (
            record.get("schema_version") != AUDIT_SCHEMA_VERSION
            or record.get("document_role") not in _TARGET_ROLES
            or record.get("status")
            not in {status.value for status in TargetDocumentEligibilityStatus}
            or not _is_sha256(record.get("markdown_sha256"))
        ):
            raise TargetDocumentEligibilityAuditError(
                "target-document eligibility audit record is invalid"
            )


def _verify_markdown_snapshots(
    parser_by_key: Mapping[tuple[str, str], Mapping[str, Any]],
    markdown_by_document: Mapping[tuple[str, str], bytes],
) -> None:
    for key, parser_record in parser_by_key.items():
        markdown_bytes = markdown_by_document[key]
        extracted = parser_record.get("extracted_text")
        if not isinstance(extracted, Mapping):
            raise TargetDocumentEligibilityAuditError(
                f"parser record lacks extracted text: {key[0]}/{key[1]}"
            )
        text_sha256 = cast(Mapping[str, object], extracted).get("text_sha256")
        if not _same_sha(text_sha256, _sha(markdown_bytes)):
            raise TargetDocumentEligibilityAuditError(
                f"parser Markdown hash differs: {key[0]}/{key[1]}"
            )


def _unique_records_by_key(
    records: Sequence[Mapping[str, Any]], *, label: str
) -> dict[tuple[str, str], Mapping[str, Any]]:
    by_key: dict[tuple[str, str], Mapping[str, Any]] = {}
    for record in records:
        key = (
            _required_text(record, "candidate_id"),
            _required_text(record, "source_document_id"),
        )
        if key in by_key:
            raise TargetDocumentEligibilityAuditError(
                f"duplicate {label} record: {key[0]}/{key[1]}"
            )
        by_key[key] = record
    return by_key


def _jsonl_records(payload: bytes, label: str) -> tuple[JsonRecord, ...]:
    """Parse the exact authenticated JSONL bytes without renormalizing them.

    Materialization and parser lineages authenticate their original producer
    bytes, which use the repository's stable projection JSONL form rather than
    the compact canonical encoding used for the audit's own output.  Requiring
    canonical input bytes here would make a valid completed lineage impossible
    to audit while adding no integrity property: the exact original bytes are
    already committed in ``input_commitments`` and replayed by the caller.
    """

    if not payload:
        return ()
    lines = payload.splitlines(keepends=True)
    if any(not line.endswith(b"\n") for line in lines) or any(
        line == b"\n" for line in lines
    ):
        raise TargetDocumentEligibilityAuditError(f"{label} is not valid JSONL")
    records: list[JsonRecord] = []
    for line in lines:
        try:
            decoded = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TargetDocumentEligibilityAuditError(
                f"{label} contains invalid JSON"
            ) from exc
        if not isinstance(decoded, dict):
            raise TargetDocumentEligibilityAuditError(f"{label} is not valid JSONL")
        records.append(cast(JsonRecord, decoded))
    return tuple(records)


def _mapping_sequence(value: object, label: str) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise TargetDocumentEligibilityAuditError(f"{label} is not a sequence")
    result: list[Mapping[str, Any]] = []
    for item in cast(Sequence[object], value):
        if not isinstance(item, Mapping):
            raise TargetDocumentEligibilityAuditError(f"{label} contains non-object")
        result.append(cast(Mapping[str, Any], item))
    return tuple(result)


def _required_text(record: Mapping[str, Any], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise TargetDocumentEligibilityAuditError(f"record lacks {field}")
    return value


def _markdown_tree_sha256(markdown_by_document: Mapping[tuple[str, str], bytes]) -> str:
    tree = {
        f"{candidate_id}/{source_document_id}": _sha(payload)
        for (candidate_id, source_document_id), payload in sorted(
            markdown_by_document.items()
        )
    }
    return _sha(_canonical_bytes(tree))


def _jsonl_bytes(records: Sequence[Mapping[str, Any]]) -> bytes:
    return b"".join(_canonical_bytes(dict(record)) for record in records)


def _canonical_bytes(value: object) -> bytes:
    return canonical_json_bytes(
        value,
        error_type=TargetDocumentEligibilityAuditError,
        error_message="target-document eligibility audit serialization failed",
    )


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _same_sha(value: object, expected: str) -> bool:
    return isinstance(value, str) and value.removeprefix(
        "sha256:"
    ) == expected.removeprefix("sha256:")


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"sha256:[0-9a-f]{64}", value))
