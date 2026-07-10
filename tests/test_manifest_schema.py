from __future__ import annotations

import json
from datetime import UTC, date, datetime

import pytest
from legalforecast.ingestion import (
    AvailabilityStatus,
    DocumentRole,
    SourceDocumentProvenance,
    sha256_text,
)
from legalforecast.protocol import (
    MANIFEST_SCHEMA_VERSION,
    CandidateManifestRecord,
    ManifestDocumentReference,
    ManifestExclusionStatus,
    build_candidate_manifest_record,
    hash_payload,
    hash_records,
)
from legalforecast.selection import (
    ContaminationMetadata,
    ModelRunMetadata,
    SeriesCaseTiming,
    TrainingCutoffStatus,
)
from legalforecast.selection.case_mix_diagnostics import (
    CaseMixCandidate,
    DocumentCompleteness,
)
from legalforecast.selection.exclusion_ledger import (
    ExclusionLedgerEntry,
    ExclusionReason,
    ExclusionStage,
)


def test_manifest_record_serializes_required_fields_for_jsonl_and_consumers() -> None:
    manifest = _manifest_record()
    record = manifest.to_record()
    packet = manifest.to_packet_build_fields()

    assert record["manifest_schema_version"] == MANIFEST_SCHEMA_VERSION
    assert record["candidate_id"] == "cand-1"
    assert record["source_document_ids"] == ["doc-complaint", "doc-decision"]
    assert record["document_hashes"]["doc-complaint"] == sha256_text("complaint")
    assert record["unit_hash"] == hash_records((_unit_record(),))
    assert record["label_hash"] == hash_records((_label_record(),))
    assert record["eligibility_status"] == "eligible"
    assert record["exclusion_status"] == "included"
    assert packet["model_packet_document_ids"] == ["doc-complaint"]
    assert json.loads(manifest.to_jsonl_line())["candidate_id"] == "cand-1"


def test_manifest_record_has_no_preregistration_projection() -> None:
    assert not hasattr(_manifest_record(), "to_preregistration_fields")


def test_manifest_hashes_are_deterministic_for_mapping_order() -> None:
    left = hash_payload({"b": 2, "a": {"y": 1, "x": 0}})
    right = hash_payload({"a": {"x": 0, "y": 1}, "b": 2})

    assert left == right
    assert (
        _manifest_record().manifest_record_hash
        == _manifest_record().manifest_record_hash
    )


def test_manifest_validation_rejects_missing_fields_and_bad_hashes() -> None:
    with pytest.raises(ValueError, match="at least one document"):
        _manifest_record(documents=())

    with pytest.raises(ValueError, match="unit_hash"):
        _manifest_record(unit_hash="not-a-hash")

    with pytest.raises(ValueError, match="case_mix_fields"):
        CandidateManifestRecord(
            protocol_version="cycle-2026-05",
            candidate_id="cand-1",
            case_id="case-1",
            court="S.D.N.Y.",
            docket_number="1:26-cv-00001",
            decision_date=date(2026, 5, 14),
            source_case_id="case-dev-1",
            documents=(
                ManifestDocumentReference.from_provenance(_document("doc-complaint")),
            ),
            unit_hash=hash_records((_unit_record(),)),
            label_hash=hash_records((_label_record(),)),
            eligibility_status=_contamination().eligibility_status,
            exclusion_status=ManifestExclusionStatus.INCLUDED,
            contamination_metadata=_contamination().to_manifest_record(),
            case_mix_fields={"district": "S.D.N.Y."},
        )


def test_excluded_manifest_records_keep_primary_exclusion_reason() -> None:
    manifest = build_candidate_manifest_record(
        protocol_version="cycle-2026-05",
        candidate_id="cand-1",
        case_id="case-1",
        court="S.D.N.Y.",
        docket_number="1:26-cv-00001",
        decision_date=date(2026, 5, 14),
        source_case_id="case-dev-1",
        documents=(_document("doc-complaint"),),
        unit_records=(_unit_record(),),
        label_records=(_label_record(),),
        contamination_metadata=_contamination(),
        case_mix_candidate=_case_mix(included=False),
        exclusion_entry=ExclusionLedgerEntry(
            candidate_id="cand-1",
            case_id="case-1",
            stage=ExclusionStage.RETRIEVAL,
            reason=ExclusionReason.MISSING_CORE_FILING.value,
            source_entry_ids=("entry-12",),
            source_document_ids=("doc-motion",),
            notes="Missing target motion.",
        ),
    )

    record = manifest.to_record()

    assert record["exclusion_status"] == "excluded"
    assert record["exclusion_reason"] == "missing_core_filing"


def _manifest_record(
    *,
    documents: tuple[ManifestDocumentReference, ...] | None = None,
    unit_hash: str | None = None,
) -> CandidateManifestRecord:
    return CandidateManifestRecord(
        protocol_version="cycle-2026-05",
        candidate_id="cand-1",
        case_id="case-1",
        court="S.D.N.Y.",
        docket_number="1:26-cv-00001",
        decision_date=date(2026, 5, 14),
        source_case_id="case-dev-1",
        documents=documents
        if documents is not None
        else (
            ManifestDocumentReference.from_provenance(_document("doc-complaint")),
            ManifestDocumentReference.from_provenance(
                _document("doc-decision", role=DocumentRole.DECISION, mounted=False)
            ),
        ),
        unit_hash=unit_hash or hash_records((_unit_record(),)),
        label_hash=hash_records((_label_record(),)),
        eligibility_status=_contamination().eligibility_status,
        exclusion_status=ManifestExclusionStatus.INCLUDED,
        contamination_metadata=_contamination().to_manifest_record(),
        case_mix_fields=_case_mix().to_record(),
        related_family_id="family-1",
    )


def _document(
    source_document_id: str,
    *,
    role: DocumentRole = DocumentRole.COMPLAINT,
    mounted: bool = True,
) -> SourceDocumentProvenance:
    text = "complaint" if mounted else "decision"
    return SourceDocumentProvenance(
        source_provider="case.dev",
        source_case_id="case-dev-1",
        source_document_id=source_document_id,
        court="S.D.N.Y.",
        docket_number="1:26-cv-00001",
        document_role=role,
        retrieved_at=datetime(2026, 5, 14, 12, 0, tzinfo=UTC),
        source_url_or_reference=f"case.dev/{source_document_id}",
        sha256=sha256_text(text),
        is_predecision_material=mounted,
        is_mounted_for_model=mounted,
        availability_status=AvailabilityStatus.AVAILABLE,
        contains_target_outcome=not mounted,
    )


def _unit_record() -> dict[str, object]:
    return {"unit_id": "unit-1", "claim_name": "Section 10(b)"}


def _label_record() -> dict[str, object]:
    return {"unit_id": "unit-1", "fully_dismissed": True}


def _contamination() -> ContaminationMetadata:
    return ContaminationMetadata(
        case_timing=SeriesCaseTiming(
            series_release_timestamp=datetime(2026, 5, 13, 12, 0, tzinfo=UTC),
            decision_entered_at=datetime(2026, 5, 14, 12, 0, tzinfo=UTC),
        ),
        model_run=ModelRunMetadata(
            provider="example",
            model_name="frontier-model",
            model_version_or_snapshot="2026-05-14",
            evaluation_timestamp=datetime(2026, 5, 15, 12, 0, tzinfo=UTC),
            network_disabled=True,
            search_disabled=True,
            provider_training_cutoff_status=TrainingCutoffStatus.KNOWN,
            provider_training_cutoff=date(2026, 4, 1),
        ),
    )


def _case_mix(*, included: bool = True) -> CaseMixCandidate:
    return CaseMixCandidate(
        candidate_id="cand-1",
        case_id="case-1",
        district="S.D.N.Y.",
        circuit="2d",
        nos_code="850",
        nos_macro_category="securities",
        represented_party_status="all_represented",
        government_party_status="no_government_party",
        mdl_flag=False,
        public_company_flag=True,
        claim_count=1,
        defendant_count=1,
        defendant_group_count=1,
        prediction_unit_count=1 if included else 0,
        document_completeness=DocumentCompleteness.COMPLETE,
        motion_available=True,
        opposition_available=True,
        reply_available=False,
        fallback_used=False,
        included_in_benchmark=included,
        related_family_id="family-1",
        exclusion_reason=(
            ExclusionReason.MISSING_CORE_FILING.value if not included else None
        ),
    )
