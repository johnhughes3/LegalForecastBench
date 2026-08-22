"""Flat owner-signed corpus manifest: schema, digest, and fail-closed loading.

One manifest names every case, every document under it, and the exact bytes on
disk behind each document.  The corpus digest over that manifest is the single
value the owner signs, so every byte the forecast run reads is either inline in
the manifest or bound to it by a recorded SHA-256.

The role partition below is enumerated positively on both halves.  A role that
is in neither set is a hard error rather than a silent default: a new
``DocumentRole`` member must be classified by name before any manifest can
admit or exclude it.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, cast

from legalforecast._hashing import is_lowercase_sha256
from legalforecast.contracts.commitments import MANIFEST_RAW_SHA256_V1
from legalforecast.contracts.schemas import OWNER_SIGNED_CORPUS_MANIFEST_V1
from legalforecast.evals.corpus_manifest.coercion import (
    CorpusManifestError,
    document_role,
    mapping,
    optional_int,
    optional_int_sequence,
    optional_str,
    optional_str_sequence,
    require_digest,
    require_non_empty,
    required_bool,
    required_str,
)
from legalforecast.ingestion.provenance import DocumentRole

MANIFEST_DIGEST_FIELD: Final[str] = "manifest_sha256"

# Positively enumerated, both halves.  ``_require_total_role_partition`` below
# fails closed if the two sets stop covering DocumentRole exactly once.
MODEL_VISIBLE_DOCUMENT_ROLES: Final[frozenset[DocumentRole]] = frozenset(
    {
        DocumentRole.COMPLAINT,
        DocumentRole.AMENDED_COMPLAINT,
        DocumentRole.COUNTERCLAIM,
        DocumentRole.CROSSCLAIM,
        DocumentRole.THIRD_PARTY_COMPLAINT,
        DocumentRole.INTERPLEADER_COMPLAINT,
        DocumentRole.OTHER_CLAIM_BEARING,
        DocumentRole.MTD_NOTICE,
        DocumentRole.MTD_MEMORANDUM,
        DocumentRole.OPPOSITION,
        DocumentRole.REPLY,
        DocumentRole.SURREPLY,
        DocumentRole.SUPPLEMENTAL_BRIEF,
        DocumentRole.DOCKET_HISTORY,
    }
)
AUDIT_ONLY_DOCUMENT_ROLES: Final[frozenset[DocumentRole]] = frozenset(
    {
        DocumentRole.ORDER,
        DocumentRole.DECISION,
        DocumentRole.EXCLUSION_NOTE,
        DocumentRole.OTHER,
    }
)

# The roles a case must carry among its model-visible documents.  These mirror
# ``legalforecast.ingestion.model_packet_assembly``'s required-document check;
# ``tests/test_owner_signed_corpus_manifest.py`` asserts the two stay equal so
# the duplication cannot drift silently.
REQUIRED_CLAIM_BEARING_ROLES: Final[frozenset[DocumentRole]] = frozenset(
    {
        DocumentRole.COMPLAINT,
        DocumentRole.AMENDED_COMPLAINT,
        DocumentRole.COUNTERCLAIM,
        DocumentRole.CROSSCLAIM,
        DocumentRole.THIRD_PARTY_COMPLAINT,
        DocumentRole.INTERPLEADER_COMPLAINT,
        DocumentRole.OTHER_CLAIM_BEARING,
    }
)
REQUIRED_TARGET_MOTION_ROLES: Final[frozenset[DocumentRole]] = frozenset(
    {
        DocumentRole.MTD_NOTICE,
        DocumentRole.MTD_MEMORANDUM,
    }
)


def _require_total_role_partition() -> None:
    """Fail closed unless the two role halves partition ``DocumentRole``."""

    overlap = MODEL_VISIBLE_DOCUMENT_ROLES & AUDIT_ONLY_DOCUMENT_ROLES
    if overlap:
        raise CorpusManifestError(
            "document roles classified both model-visible and audit-only: "
            + ", ".join(sorted(role.value for role in overlap))
        )
    unclassified = set(DocumentRole) - (
        MODEL_VISIBLE_DOCUMENT_ROLES | AUDIT_ONLY_DOCUMENT_ROLES
    )
    if unclassified:
        raise CorpusManifestError(
            "document roles are classified in neither half of the manifest "
            "visibility partition: "
            + ", ".join(sorted(role.value for role in unclassified))
        )


_require_total_role_partition()


@dataclass(frozen=True, slots=True)
class ManifestDocument:
    """One document, bound to the exact bytes standing behind it on disk."""

    source_document_id: str
    document_role: DocumentRole
    model_visible: bool
    pdf_path: str
    pdf_sha256: str
    source_url: str
    markdown_path: str | None = None
    markdown_sha256: str | None = None
    docket_entry_number: int | None = None
    byte_role_verdict: str | None = None
    validation_basis: str | None = None

    def __post_init__(self) -> None:
        require_non_empty(self.source_document_id, "source_document_id")
        require_non_empty(self.pdf_path, "pdf_path")
        require_non_empty(self.source_url, "source_url")
        require_digest(self.pdf_sha256, "pdf_sha256")
        if self.model_visible:
            if self.document_role not in MODEL_VISIBLE_DOCUMENT_ROLES:
                raise CorpusManifestError(
                    f"{self.source_document_id}: role "
                    f"{self.document_role.value} may never be model-visible"
                )
            if not self.markdown_path or not self.markdown_sha256:
                raise CorpusManifestError(
                    f"{self.source_document_id}: model-visible documents require "
                    "markdown_path and markdown_sha256"
                )
        if self.markdown_sha256 is not None:
            require_digest(self.markdown_sha256, "markdown_sha256")
        if self.docket_entry_number is not None and self.docket_entry_number <= 0:
            raise CorpusManifestError("docket_entry_number must be positive")

    def to_record(self) -> dict[str, Any]:
        """Return the flat, key-stable manifest row for this document."""

        return {
            "byte_role_verdict": self.byte_role_verdict,
            "docket_entry_number": self.docket_entry_number,
            "document_role": self.document_role.value,
            "markdown_path": self.markdown_path,
            "markdown_sha256": self.markdown_sha256,
            "model_visible": self.model_visible,
            "pdf_path": self.pdf_path,
            "pdf_sha256": self.pdf_sha256,
            "source_document_id": self.source_document_id,
            "source_url": self.source_url,
            "validation_basis": self.validation_basis,
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> ManifestDocument:
        """Rebuild one document row, rejecting unknown roles."""

        return cls(
            source_document_id=required_str(record, "source_document_id"),
            document_role=document_role(record),
            model_visible=required_bool(record, "model_visible"),
            pdf_path=required_str(record, "pdf_path"),
            pdf_sha256=required_str(record, "pdf_sha256"),
            source_url=required_str(record, "source_url"),
            markdown_path=optional_str(record, "markdown_path"),
            markdown_sha256=optional_str(record, "markdown_sha256"),
            docket_entry_number=optional_int(record, "docket_entry_number"),
            byte_role_verdict=optional_str(record, "byte_role_verdict"),
            validation_basis=optional_str(record, "validation_basis"),
        )


@dataclass(frozen=True, slots=True)
class ManifestCase:
    """One case and every document the corpus holds under it."""

    candidate_id: str
    case_id: str
    court: str
    docket_number: str
    documents: tuple[ManifestDocument, ...]
    decision_date: str | None = None
    target_motion_entry_numbers: tuple[int, ...] = ()
    # Audit-only documents the corpus names but holds no parsed bytes for.
    # They are recorded rather than dropped: the forecast never reads them, so
    # they do not block a run, but a later labeling or reconciliation pass must
    # be able to see that this manifest does not stand behind them.
    unresolved_audit_only_document_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_non_empty(self.candidate_id, "candidate_id")
        require_non_empty(self.case_id, "case_id")
        require_non_empty(self.court, "court")
        require_non_empty(self.docket_number, "docket_number")
        if not self.documents:
            raise CorpusManifestError(f"{self.candidate_id}: no documents")
        seen: set[str] = set()
        for document in self.documents:
            if document.source_document_id in seen:
                raise CorpusManifestError(
                    f"{self.candidate_id}: duplicate document "
                    f"{document.source_document_id}"
                )
            seen.add(document.source_document_id)

    @property
    def model_visible_documents(self) -> tuple[ManifestDocument, ...]:
        """Return only the documents this manifest permits a model to read."""

        return tuple(document for document in self.documents if document.model_visible)

    def to_record(self) -> dict[str, Any]:
        """Return the flat, key-stable manifest row for this case."""

        return {
            "candidate_id": self.candidate_id,
            "case_id": self.case_id,
            "court": self.court,
            "decision_date": self.decision_date,
            "docket_number": self.docket_number,
            "documents": [document.to_record() for document in self.documents],
            "target_motion_entry_numbers": list(self.target_motion_entry_numbers),
            "unresolved_audit_only_document_ids": list(
                self.unresolved_audit_only_document_ids
            ),
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> ManifestCase:
        """Rebuild one case row and every document beneath it."""

        raw_documents = record.get("documents")
        if not isinstance(raw_documents, Sequence) or isinstance(
            raw_documents, (str, bytes)
        ):
            raise CorpusManifestError("case documents must be a list")
        documents = cast("Sequence[object]", raw_documents)
        return cls(
            candidate_id=required_str(record, "candidate_id"),
            case_id=required_str(record, "case_id"),
            court=required_str(record, "court"),
            docket_number=required_str(record, "docket_number"),
            documents=tuple(
                ManifestDocument.from_record(mapping(document))
                for document in documents
            ),
            decision_date=optional_str(record, "decision_date"),
            target_motion_entry_numbers=tuple(
                optional_int_sequence(record, "target_motion_entry_numbers")
            ),
            unresolved_audit_only_document_ids=optional_str_sequence(
                record, "unresolved_audit_only_document_ids"
            ),
        )


@dataclass(frozen=True, slots=True)
class BoundSource:
    """An input file bound to the manifest by path and content digest."""

    path: str
    sha256: str

    def __post_init__(self) -> None:
        require_non_empty(self.path, "path")
        require_digest(self.sha256, "sha256")

    def to_record(self) -> dict[str, Any]:
        """Return the flat record for this bound source."""

        return {"path": self.path, "sha256": self.sha256}

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> BoundSource:
        """Rebuild one bound source, requiring both halves."""

        return cls(
            path=required_str(record, "path"),
            sha256=required_str(record, "sha256"),
        )


@dataclass(frozen=True, slots=True)
class CorpusManifest:
    """The whole frozen corpus: cases, documents, and their bound inputs."""

    cycle_id: str
    generated_at: str
    selection_source: BoundSource
    prediction_units_source: BoundSource
    cases: tuple[ManifestCase, ...]

    def __post_init__(self) -> None:
        require_non_empty(self.cycle_id, "cycle_id")
        require_non_empty(self.generated_at, "generated_at")
        if not self.cases:
            raise CorpusManifestError("manifest must contain at least one case")
        seen: set[str] = set()
        for case in self.cases:
            if case.candidate_id in seen:
                raise CorpusManifestError(f"duplicate case {case.candidate_id}")
            seen.add(case.candidate_id)

    def to_record(self) -> dict[str, Any]:
        """Return the manifest payload the corpus digest is computed over."""

        return {
            "cases": [case.to_record() for case in self.cases],
            "cycle_id": self.cycle_id,
            "generated_at": self.generated_at,
            "prediction_units_source": self.prediction_units_source.to_record(),
            "schema_version": str(OWNER_SIGNED_CORPUS_MANIFEST_V1),
            "selection_source": self.selection_source.to_record(),
        }

    def digest(self) -> str:
        """Return the corpus digest the owner signs."""

        return manifest_digest(self.to_record())

    def to_signed_record(self) -> dict[str, Any]:
        """Return the manifest payload with its own digest embedded."""

        record = self.to_record()
        record[MANIFEST_DIGEST_FIELD] = manifest_digest(record)
        return record

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> CorpusManifest:
        """Rebuild a manifest from its record, rejecting a wrong schema id."""

        schema_version = required_str(record, "schema_version")
        if schema_version != str(OWNER_SIGNED_CORPUS_MANIFEST_V1):
            raise CorpusManifestError(
                f"unexpected manifest schema_version: {schema_version}"
            )
        raw_cases = record.get("cases")
        if not isinstance(raw_cases, Sequence) or isinstance(raw_cases, (str, bytes)):
            raise CorpusManifestError("manifest cases must be a list")
        cases = cast("Sequence[object]", raw_cases)
        return cls(
            cycle_id=required_str(record, "cycle_id"),
            generated_at=required_str(record, "generated_at"),
            selection_source=BoundSource.from_record(
                mapping(record.get("selection_source"))
            ),
            prediction_units_source=BoundSource.from_record(
                mapping(record.get("prediction_units_source"))
            ),
            cases=tuple(ManifestCase.from_record(mapping(case)) for case in cases),
        )


def manifest_digest(record: Mapping[str, Any]) -> str:
    """Return the corpus digest over *record*, excluding any embedded digest.

    The digest is taken through the frozen manifest commitment profile so this
    instrument commits bytes the same way every other Cycle 1 manifest does.
    """

    payload = {
        key: value for key, value in record.items() if key != MANIFEST_DIGEST_FIELD
    }
    commitment = MANIFEST_RAW_SHA256_V1.commit(
        payload,
        domain=OWNER_SIGNED_CORPUS_MANIFEST_V1,
    )
    return str(commitment.digest)


def load_signed_manifest(path: Path, *, expected_digest: str) -> CorpusManifest:
    """Load a manifest and refuse unless it matches *expected_digest* exactly.

    Both the digest embedded in the file and the digest the operator names on
    the command line must agree with the digest recomputed from the bytes, so
    neither a re-signed file nor a stale command line can be used alone.
    """

    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise CorpusManifestError(f"manifest not found: {path}") from exc
    return load_signed_manifest_bytes(payload, expected_digest=expected_digest)


def load_signed_manifest_bytes(
    payload: bytes, *, expected_digest: str
) -> CorpusManifest:
    """Load and authenticate one caller-captured manifest byte snapshot."""

    if not is_lowercase_sha256(expected_digest):
        raise CorpusManifestError(
            "expected manifest digest must be 64 lowercase hexadecimal characters"
        )
    try:
        value: object = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusManifestError("manifest must be valid UTF-8 JSON") from exc
    if not isinstance(value, Mapping):
        raise CorpusManifestError("manifest must be a JSON object")
    record = dict(cast(Mapping[str, Any], value))
    embedded = record.get(MANIFEST_DIGEST_FIELD)
    if not isinstance(embedded, str) or not is_lowercase_sha256(embedded):
        raise CorpusManifestError(
            f"manifest is missing a valid {MANIFEST_DIGEST_FIELD}"
        )
    recomputed = manifest_digest(record)
    if recomputed != embedded:
        raise CorpusManifestError(
            "manifest bytes do not match the digest embedded in the manifest"
        )
    if recomputed != expected_digest:
        raise CorpusManifestError(
            "manifest digest does not match the expected digest supplied by the "
            "operator; the signed manifest and the named digest disagree"
        )
    return CorpusManifest.from_record(record)
