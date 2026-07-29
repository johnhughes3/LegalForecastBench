from __future__ import annotations

from copy import deepcopy

import pytest
from legalforecast.ingestion.mistral_markdown_parser import EXPECTED_PARSER_REVISION
from legalforecast.ingestion.packet_role_adjudication import (
    AuthenticatedPacketRoleEvidence,
    PacketRoleAdjudicationError,
    PacketRoleDisposition,
    build_packet_role_adjudication_record,
    packet_role_adjudication_record_sha256,
    verify_packet_role_adjudications,
)

_HASHES = tuple(f"{value:064x}" for value in range(1, 8))


def test_verified_accepted_record_is_deterministic_and_generic() -> None:
    first = _evidence(candidate_id="courtlistener-docket-123", docket_id="123")
    second = _evidence(
        candidate_id="courtlistener-docket-987",
        docket_id="987",
        document_key="987-entry-12-motion-to-dismiss-notice",
    )
    records = (
        _record(second),
        _record(first),
    )

    forward = verify_packet_role_adjudications(records, (first, second))
    reverse = verify_packet_role_adjudications(
        tuple(reversed(records)),
        (second, first),
    )

    assert forward.commitment_sha256 == reverse.commitment_sha256
    assert forward.records == reverse.records
    assert (
        forward.accepted_combined_mtd_memorandum(
            candidate_id=first.candidate_id,
            docket_id=first.docket_id,
            document_key=first.document_key,
        )
        is not None
    )
    assert (
        forward.accepted_combined_mtd_memorandum(
            candidate_id=second.candidate_id,
            docket_id=second.docket_id,
            document_key=second.document_key,
        )
        is not None
    )


@pytest.mark.parametrize(
    "field",
    (
        "source_pdf_sha256",
        "parser_manifest_sha256",
        "parser_run_card_sha256",
        "parser_record_sha256",
        "evidence_text_sha256",
    ),
)
def test_hash_mismatch_fails_closed(field: str) -> None:
    evidence = _evidence()
    record = _record(evidence)
    record[field] = "f" * 64
    _rehash(record)

    with pytest.raises(PacketRoleAdjudicationError, match=f"{field} mismatch"):
        verify_packet_role_adjudications((record,), (evidence,))


def test_unknown_disposition_fails_closed() -> None:
    evidence = _evidence()
    record = _record(evidence)
    record["disposition"] = "accept_any_motion"
    _rehash(record)

    with pytest.raises(PacketRoleAdjudicationError, match="unknown disposition"):
        verify_packet_role_adjudications((record,), (evidence,))


@pytest.mark.parametrize(
    ("failure_kind", "match"),
    (
        ("ambiguous", "ambiguous"),
        ("restriction_status", "restricted"),
        ("restriction_marker", "restricted"),
    ),
)
def test_accepted_ambiguous_or_restricted_material_fails_closed(
    failure_kind: str,
    match: str,
) -> None:
    if failure_kind == "ambiguous":
        evidence = _evidence(ambiguous=True)
    elif failure_kind == "restriction_status":
        evidence = _evidence(restriction_status="sealed")
    else:
        evidence = _evidence(restriction_markers=("field_issealed",))

    with pytest.raises(PacketRoleAdjudicationError, match=match):
        verify_packet_role_adjudications((_record(evidence),), (evidence,))


def test_rejected_ambiguous_material_is_verified_but_never_accepted() -> None:
    evidence = _evidence(ambiguous=True)
    verified = verify_packet_role_adjudications(
        (_record(evidence, disposition=PacketRoleDisposition.REJECT),),
        (evidence,),
    )

    assert (
        verified.accepted_combined_mtd_memorandum(
            candidate_id=evidence.candidate_id,
            docket_id=evidence.docket_id,
            document_key=evidence.document_key,
        )
        is None
    )


def test_duplicate_and_conflicting_records_fail_closed() -> None:
    evidence = _evidence()
    accepted = _record(evidence)
    rejected = _record(evidence, disposition=PacketRoleDisposition.REJECT)

    with pytest.raises(PacketRoleAdjudicationError, match="duplicate or conflicting"):
        verify_packet_role_adjudications((accepted, deepcopy(accepted)), (evidence,))
    with pytest.raises(PacketRoleAdjudicationError, match="duplicate or conflicting"):
        verify_packet_role_adjudications((accepted, rejected), (evidence,))


def test_record_self_hash_is_verified() -> None:
    evidence = _evidence()
    record = _record(evidence)
    record["notes"] = "changed after adjudication"

    with pytest.raises(PacketRoleAdjudicationError, match="record_sha256 mismatch"):
        verify_packet_role_adjudications((record,), (evidence,))


def _evidence(
    *,
    candidate_id: str = "courtlistener-docket-123",
    docket_id: str = "123",
    document_key: str = "123-entry-5-motion-to-dismiss-notice",
    ambiguous: bool = False,
    restriction_status: str = "public",
    restriction_markers: tuple[str, ...] = (),
) -> AuthenticatedPacketRoleEvidence:
    return AuthenticatedPacketRoleEvidence(
        candidate_id=candidate_id,
        docket_id=docket_id,
        document_key=document_key,
        source_pdf_sha256=_HASHES[0],
        source_byte_count=1234,
        parser_revision=EXPECTED_PARSER_REVISION,
        parser_manifest_sha256=_HASHES[1],
        parser_run_card_sha256=_HASHES[2],
        parser_record_sha256=_HASHES[3],
        evidence_kind="excerpt",
        evidence_text_sha256=_HASHES[4],
        ambiguous=ambiguous,
        restriction_status=restriction_status,
        restriction_markers=restriction_markers,
    )


def _record(
    evidence: AuthenticatedPacketRoleEvidence,
    *,
    disposition: PacketRoleDisposition = (
        PacketRoleDisposition.ACCEPT_COMBINED_MTD_MEMORANDUM
    ),
) -> dict[str, object]:
    return build_packet_role_adjudication_record(
        evidence,
        adjudicator="John Hughes",
        disposition=disposition,
        notes="The same pre-decision PDF contains substantive points and authorities.",
    )


def _rehash(record: dict[str, object]) -> None:
    body = {key: value for key, value in record.items() if key != "record_sha256"}
    record["record_sha256"] = packet_role_adjudication_record_sha256(body)
