"""Verify human packet-role adjudications against authenticated parser evidence."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import cast

from legalforecast._hashing import is_lowercase_sha256
from legalforecast.ingestion.mistral_markdown_parser import EXPECTED_PARSER_REVISION

PACKET_ROLE_ADJUDICATION_SCHEMA = "legalforecast.packet_role_adjudication.v1"
_EVIDENCE_KINDS = frozenset({"title", "excerpt"})
_NON_RESTRICTED_STATUSES = frozenset({"public", "redacted"})
_RECORD_FIELDS = frozenset(
    {
        "schema_version",
        "candidate_id",
        "docket_id",
        "document_key",
        "source_pdf_sha256",
        "source_byte_count",
        "parser_revision",
        "parser_manifest_sha256",
        "parser_run_card_sha256",
        "parser_record_sha256",
        "evidence_kind",
        "evidence_text_sha256",
        "adjudicator",
        "disposition",
        "ambiguous",
        "restriction_status",
        "restriction_markers",
        "notes",
        "record_sha256",
    }
)

PacketRoleIdentity = tuple[str, str, str]


class PacketRoleAdjudicationError(ValueError):
    """Raised when packet-role authority cannot be verified exactly."""


class PacketRoleDisposition(StrEnum):
    """Supported owner dispositions for one source document."""

    ACCEPT_COMBINED_MTD_MEMORANDUM = "accept_combined_mtd_memorandum"
    REJECT = "reject"


@dataclass(frozen=True, slots=True)
class AuthenticatedPacketRoleEvidence:
    """Preverified source and parser commitments supplied to adjudication replay.

    The caller is responsible for authenticating the parser manifest and run card.
    Replay independently binds the adjudication to those exact authenticated bytes.
    """

    candidate_id: str
    docket_id: str
    document_key: str
    source_pdf_sha256: str
    source_byte_count: int
    parser_revision: str
    parser_manifest_sha256: str
    parser_run_card_sha256: str
    parser_record_sha256: str
    evidence_kind: str
    evidence_text_sha256: str
    ambiguous: bool
    restriction_status: str
    restriction_markers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("candidate_id", "docket_id", "document_key"):
            _require_text(getattr(self, field_name), field_name)
        for field_name in (
            "source_pdf_sha256",
            "parser_manifest_sha256",
            "parser_run_card_sha256",
            "parser_record_sha256",
            "evidence_text_sha256",
        ):
            _require_sha256(getattr(self, field_name), field_name)
        if self.source_byte_count <= 0:
            raise PacketRoleAdjudicationError("source_byte_count must be positive")
        if self.parser_revision != EXPECTED_PARSER_REVISION:
            raise PacketRoleAdjudicationError(
                "parser_revision is not the pinned Mistral revision"
            )
        if self.evidence_kind not in _EVIDENCE_KINDS:
            raise PacketRoleAdjudicationError("evidence_kind must be title or excerpt")
        _require_text(self.restriction_status, "restriction_status")
        for marker in self.restriction_markers:
            _require_text(marker, "restriction_markers")

    @property
    def identity(self) -> PacketRoleIdentity:
        return (self.candidate_id, self.docket_id, self.document_key)


@dataclass(frozen=True, slots=True)
class VerifiedPacketRoleAdjudication:
    """One adjudication whose commitments match authenticated evidence."""

    candidate_id: str
    docket_id: str
    document_key: str
    source_pdf_sha256: str
    source_byte_count: int
    parser_revision: str
    parser_manifest_sha256: str
    parser_run_card_sha256: str
    parser_record_sha256: str
    evidence_kind: str
    evidence_text_sha256: str
    adjudicator: str
    disposition: PacketRoleDisposition
    ambiguous: bool
    restriction_status: str
    restriction_markers: tuple[str, ...]
    notes: str
    record_sha256: str

    @property
    def identity(self) -> PacketRoleIdentity:
        return (self.candidate_id, self.docket_id, self.document_key)

    @property
    def accepted(self) -> bool:
        return self.disposition is PacketRoleDisposition.ACCEPT_COMBINED_MTD_MEMORANDUM

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": PACKET_ROLE_ADJUDICATION_SCHEMA,
            "candidate_id": self.candidate_id,
            "docket_id": self.docket_id,
            "document_key": self.document_key,
            "source_pdf_sha256": self.source_pdf_sha256,
            "source_byte_count": self.source_byte_count,
            "parser_revision": self.parser_revision,
            "parser_manifest_sha256": self.parser_manifest_sha256,
            "parser_run_card_sha256": self.parser_run_card_sha256,
            "parser_record_sha256": self.parser_record_sha256,
            "evidence_kind": self.evidence_kind,
            "evidence_text_sha256": self.evidence_text_sha256,
            "adjudicator": self.adjudicator,
            "disposition": self.disposition.value,
            "ambiguous": self.ambiguous,
            "restriction_status": self.restriction_status,
            "restriction_markers": list(self.restriction_markers),
            "notes": self.notes,
            "record_sha256": self.record_sha256,
        }


@dataclass(frozen=True, slots=True)
class VerifiedPacketRoleAdjudications:
    """Deterministic lookup produced only after exact evidence replay."""

    records: tuple[VerifiedPacketRoleAdjudication, ...]
    commitment_sha256: str

    def accepted_combined_mtd_memorandum(
        self,
        *,
        candidate_id: str,
        docket_id: str,
        document_key: str,
    ) -> VerifiedPacketRoleAdjudication | None:
        identity = (candidate_id, docket_id, document_key)
        return next(
            (
                record
                for record in self.records
                if record.identity == identity and record.accepted
            ),
            None,
        )


def build_packet_role_adjudication_record(
    evidence: AuthenticatedPacketRoleEvidence,
    *,
    adjudicator: str,
    disposition: PacketRoleDisposition | str,
    notes: str,
) -> dict[str, object]:
    """Build deterministic review bytes bound to authenticated evidence."""

    _require_text(adjudicator, "adjudicator")
    _require_text(notes, "notes")
    try:
        normalized_disposition = PacketRoleDisposition(disposition)
    except ValueError as exc:
        raise PacketRoleAdjudicationError(
            f"unknown disposition: {disposition!r}"
        ) from exc
    body: dict[str, object] = {
        "schema_version": PACKET_ROLE_ADJUDICATION_SCHEMA,
        "candidate_id": evidence.candidate_id,
        "docket_id": evidence.docket_id,
        "document_key": evidence.document_key,
        "source_pdf_sha256": evidence.source_pdf_sha256,
        "source_byte_count": evidence.source_byte_count,
        "parser_revision": evidence.parser_revision,
        "parser_manifest_sha256": evidence.parser_manifest_sha256,
        "parser_run_card_sha256": evidence.parser_run_card_sha256,
        "parser_record_sha256": evidence.parser_record_sha256,
        "evidence_kind": evidence.evidence_kind,
        "evidence_text_sha256": evidence.evidence_text_sha256,
        "adjudicator": adjudicator,
        "disposition": normalized_disposition.value,
        "ambiguous": evidence.ambiguous,
        "restriction_status": evidence.restriction_status,
        "restriction_markers": list(evidence.restriction_markers),
        "notes": notes,
    }
    return {
        **body,
        "record_sha256": packet_role_adjudication_record_sha256(body),
    }


def packet_role_adjudication_record_sha256(record: Mapping[str, object]) -> str:
    """Return the canonical self-commitment for an unhashed adjudication body."""

    return hashlib.sha256(_canonical_json_bytes(dict(record))).hexdigest()


def verify_packet_role_adjudications(
    records: Sequence[Mapping[str, object]],
    authenticated_evidence: Sequence[AuthenticatedPacketRoleEvidence],
) -> VerifiedPacketRoleAdjudications:
    """Replay role adjudications against exact authenticated source evidence."""

    evidence_index: dict[PacketRoleIdentity, AuthenticatedPacketRoleEvidence] = {}
    for evidence in authenticated_evidence:
        if evidence.identity in evidence_index:
            raise PacketRoleAdjudicationError(
                f"duplicate authenticated evidence: {evidence.identity}"
            )
        evidence_index[evidence.identity] = evidence

    verified: list[VerifiedPacketRoleAdjudication] = []
    seen: set[PacketRoleIdentity] = set()
    for raw_record in records:
        record = dict(raw_record)
        if frozenset(record) != _RECORD_FIELDS:
            raise PacketRoleAdjudicationError(
                "packet-role adjudication fields do not match the v1 schema"
            )
        if record.get("schema_version") != PACKET_ROLE_ADJUDICATION_SCHEMA:
            raise PacketRoleAdjudicationError(
                "unsupported packet-role adjudication schema"
            )
        body = {key: value for key, value in record.items() if key != "record_sha256"}
        expected_record_sha256 = packet_role_adjudication_record_sha256(body)
        if record.get("record_sha256") != expected_record_sha256:
            raise PacketRoleAdjudicationError("record_sha256 mismatch")

        identity = (
            _required_text(record, "candidate_id"),
            _required_text(record, "docket_id"),
            _required_text(record, "document_key"),
        )
        if identity in seen:
            raise PacketRoleAdjudicationError(
                f"duplicate or conflicting adjudication record: {identity}"
            )
        seen.add(identity)
        evidence = evidence_index.get(identity)
        if evidence is None:
            raise PacketRoleAdjudicationError(
                f"adjudication lacks authenticated evidence: {identity}"
            )

        _require_exact_commitments(record, evidence)
        disposition_text = _required_text(record, "disposition")
        try:
            disposition = PacketRoleDisposition(disposition_text)
        except ValueError as exc:
            raise PacketRoleAdjudicationError(
                f"unknown disposition: {disposition_text!r}"
            ) from exc
        adjudicator = _required_text(record, "adjudicator")
        notes = _required_text(record, "notes")
        if record.get("ambiguous") is not evidence.ambiguous:
            raise PacketRoleAdjudicationError("ambiguous mismatch")
        restriction_status = _required_text(record, "restriction_status")
        markers = _required_text_sequence(record, "restriction_markers")
        if restriction_status != evidence.restriction_status:
            raise PacketRoleAdjudicationError("restriction_status mismatch")
        if markers != evidence.restriction_markers:
            raise PacketRoleAdjudicationError("restriction_markers mismatch")
        if disposition is PacketRoleDisposition.ACCEPT_COMBINED_MTD_MEMORANDUM:
            if evidence.ambiguous:
                raise PacketRoleAdjudicationError(
                    "ambiguous evidence cannot authorize packet-role promotion"
                )
            if (
                evidence.restriction_status not in _NON_RESTRICTED_STATUSES
                or evidence.restriction_markers
            ):
                raise PacketRoleAdjudicationError(
                    "restricted material cannot authorize packet-role promotion"
                )

        verified.append(
            VerifiedPacketRoleAdjudication(
                candidate_id=identity[0],
                docket_id=identity[1],
                document_key=identity[2],
                source_pdf_sha256=evidence.source_pdf_sha256,
                source_byte_count=evidence.source_byte_count,
                parser_revision=evidence.parser_revision,
                parser_manifest_sha256=evidence.parser_manifest_sha256,
                parser_run_card_sha256=evidence.parser_run_card_sha256,
                parser_record_sha256=evidence.parser_record_sha256,
                evidence_kind=evidence.evidence_kind,
                evidence_text_sha256=evidence.evidence_text_sha256,
                adjudicator=adjudicator,
                disposition=disposition,
                ambiguous=evidence.ambiguous,
                restriction_status=evidence.restriction_status,
                restriction_markers=evidence.restriction_markers,
                notes=notes,
                record_sha256=expected_record_sha256,
            )
        )

    ordered = tuple(sorted(verified, key=lambda item: item.identity))
    commitment = hashlib.sha256(
        _canonical_json_bytes([record.to_record() for record in ordered])
    ).hexdigest()
    return VerifiedPacketRoleAdjudications(
        records=ordered,
        commitment_sha256=commitment,
    )


def _require_exact_commitments(
    record: Mapping[str, object],
    evidence: AuthenticatedPacketRoleEvidence,
) -> None:
    expected: dict[str, object] = {
        "source_pdf_sha256": evidence.source_pdf_sha256,
        "source_byte_count": evidence.source_byte_count,
        "parser_revision": evidence.parser_revision,
        "parser_manifest_sha256": evidence.parser_manifest_sha256,
        "parser_run_card_sha256": evidence.parser_run_card_sha256,
        "parser_record_sha256": evidence.parser_record_sha256,
        "evidence_kind": evidence.evidence_kind,
        "evidence_text_sha256": evidence.evidence_text_sha256,
    }
    for field_name, expected_value in expected.items():
        if record.get(field_name) != expected_value:
            raise PacketRoleAdjudicationError(f"{field_name} mismatch")


def _required_text(record: Mapping[str, object], field_name: str) -> str:
    value = record.get(field_name)
    if not isinstance(value, str):
        raise PacketRoleAdjudicationError(f"{field_name} must be a string")
    _require_text(value, field_name)
    return value


def _required_text_sequence(
    record: Mapping[str, object], field_name: str
) -> tuple[str, ...]:
    value = record.get(field_name)
    if not isinstance(value, list):
        raise PacketRoleAdjudicationError(f"{field_name} must be a list")
    output: list[str] = []
    for item in cast(list[object], value):
        if not isinstance(item, str):
            raise PacketRoleAdjudicationError(f"{field_name} entries must be strings")
        _require_text(item, field_name)
        output.append(item)
    return tuple(output)


def _require_text(value: str, field_name: str) -> None:
    if not value or value != value.strip():
        raise PacketRoleAdjudicationError(
            f"{field_name} must be non-empty without surrounding whitespace"
        )


def _require_sha256(value: str, field_name: str) -> None:
    if not is_lowercase_sha256(value):
        raise PacketRoleAdjudicationError(
            f"{field_name} must be a lowercase SHA-256 digest"
        )


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


__all__ = [
    "PACKET_ROLE_ADJUDICATION_SCHEMA",
    "AuthenticatedPacketRoleEvidence",
    "PacketRoleAdjudicationError",
    "PacketRoleDisposition",
    "VerifiedPacketRoleAdjudication",
    "VerifiedPacketRoleAdjudications",
    "build_packet_role_adjudication_record",
    "packet_role_adjudication_record_sha256",
    "verify_packet_role_adjudications",
]
