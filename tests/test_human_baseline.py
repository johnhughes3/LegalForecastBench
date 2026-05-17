from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from legalforecast.evals.human_baseline import (
    CaseComplexityStratum,
    HumanForecast,
    HumanForecastPacket,
    score_human_baseline,
)
from legalforecast.evals.packet_builder import PacketText, build_model_packet
from legalforecast.ingestion.provenance import (
    CasePacketSchema,
    DocumentRole,
    SourceDocumentProvenance,
    sha256_text,
)
from legalforecast.labeling import (
    AmendmentClass,
    OutcomeCitation,
    OutcomeLabel,
    ReviewerExpertise,
)
from legalforecast.unitization.schemas import (
    ChallengeScope,
    PredictionUnit,
    SourceCitation,
)


def test_human_packet_uses_same_units_and_no_external_research_default() -> None:
    from legalforecast.evals.inspect_task import build_inspect_samples

    sample = build_inspect_samples((_model_packet(),), use_docket_tool=False)[0]

    packet = HumanForecastPacket.from_inspect_sample(sample, time_limit_minutes=30)
    record = packet.to_record()

    assert packet.unit_ids == ("unit-1", "unit-2")
    assert packet.external_research_allowed is False
    assert packet.time_limit_minutes == 30
    assert "0 to 1" in packet.instructions
    assert record["prompt_sha256"] == sample.to_record()["prompt_sha256"]
    json.dumps(record)


def test_score_human_baseline_reports_expertise_and_complexity() -> None:
    forecasts = (
        _forecast(
            reviewer_id="student-1",
            expertise=ReviewerExpertise.LAW_STUDENT,
            unit_id="unit-1",
            probability=0.65,
            complexity=CaseComplexityStratum.SIMPLE,
            minutes=12,
            confidence=0.7,
        ),
        _forecast(
            reviewer_id="senior-1",
            expertise=ReviewerExpertise.SENIOR_LITIGATOR,
            unit_id="unit-2",
            probability=0.25,
            complexity=CaseComplexityStratum.COMPLEX,
            minutes=18,
            confidence=0.9,
        ),
    )

    summary = score_human_baseline(
        forecasts,
        {
            "unit-1": _label("unit-1", dismissed=True),
            "unit-2": _label("unit-2", dismissed=False),
        },
        model_probabilities_by_unit_id={"unit-1": 0.75, "unit-2": 0.55},
    )
    record = summary.to_record()

    expected_brier = ((0.65 - 1) ** 2 + 0.25**2) / 2
    assert summary.overall.unit_count == 2
    assert summary.overall.reviewer_count == 2
    assert abs(summary.overall.mean_brier - expected_brier) < 1e-12
    assert summary.overall.mean_minutes_spent == 15
    assert summary.overall.mean_confidence == 0.8
    assert summary.overall.mean_absolute_model_delta is not None
    assert abs(summary.overall.mean_absolute_model_delta - 0.2) < 1e-12
    assert [slice_.slice_id for slice_ in summary.by_expertise] == [
        "law_student",
        "senior_litigator",
    ]
    assert [slice_.slice_id for slice_ in summary.by_complexity] == [
        "simple",
        "complex",
    ]
    assert record["unit_scores"][0]["reviewer_expertise"] == "law_student"


def test_human_baseline_rejects_external_research_without_permission() -> None:
    forecast = _forecast(
        reviewer_id="senior-1",
        expertise=ReviewerExpertise.SENIOR_LITIGATOR,
        unit_id="unit-1",
        probability=0.65,
        external_research_used=True,
    )

    with pytest.raises(ValueError, match="external research"):
        score_human_baseline(
            (forecast,),
            {"unit-1": _label("unit-1", dismissed=True)},
        )

    allowed = score_human_baseline(
        (forecast,),
        {"unit-1": _label("unit-1", dismissed=True)},
        external_research_allowed=True,
    )
    assert allowed.overall.unit_count == 1


def test_human_baseline_rejects_duplicate_reviewer_unit_forecasts() -> None:
    forecast = _forecast(
        reviewer_id="senior-1",
        expertise=ReviewerExpertise.SENIOR_LITIGATOR,
        unit_id="unit-1",
        probability=0.65,
    )

    with pytest.raises(ValueError, match="duplicate"):
        score_human_baseline(
            (forecast, forecast),
            {"unit-1": _label("unit-1", dismissed=True)},
        )


def _forecast(
    *,
    reviewer_id: str,
    expertise: ReviewerExpertise,
    unit_id: str,
    probability: float,
    complexity: CaseComplexityStratum = CaseComplexityStratum.SIMPLE,
    minutes: float = 10,
    confidence: float = 0.8,
    external_research_used: bool = False,
) -> HumanForecast:
    return HumanForecast(
        packet_id="packet-1",
        case_id="case-1",
        unit_id=unit_id,
        reviewer_id=reviewer_id,
        reviewer_expertise=expertise,
        probability_fully_dismissed=probability,
        confidence=confidence,
        minutes_spent=minutes,
        complexity_stratum=complexity,
        notes="Human forecast rationale.",
        external_research_used=external_research_used,
    )


def _label(unit_id: str, *, dismissed: bool) -> OutcomeLabel:
    return OutcomeLabel(
        unit_id=unit_id,
        fully_dismissed=dismissed,
        amendment_class=(
            AmendmentClass.DISMISSED_WITHOUT_EXPRESS_AMENDMENT_OPPORTUNITY
            if dismissed
            else AmendmentClass.NOT_FULLY_DISMISSED
        ),
        ambiguous=False,
        label_confidence=0.95,
        supporting_citations=(OutcomeCitation(document_id="decision-1", page=1),),
        first_written_disposition_id="decision-1",
        first_written_disposition_date="2026-05-18",
    )


def _model_packet():
    return build_model_packet(
        case_packet=CasePacketSchema(
            candidate_id="cand-1",
            case_id="case-1",
            court="S.D.N.Y.",
            docket_number="1:26-cv-1",
            generated_at=datetime(2026, 5, 14, tzinfo=UTC),
            documents=(
                _document("complaint", DocumentRole.COMPLAINT, 1),
                _document("mtd-memo", DocumentRole.MTD_MEMORANDUM, 34),
            ),
        ),
        prediction_units=(_unit("unit-1", "I"), _unit("unit-2", "II")),
        texts=(
            PacketText(source_document_id="complaint", text="complaint text"),
            PacketText(source_document_id="mtd-memo", text="motion text"),
        ),
    )


def _document(
    document_id: str,
    role: DocumentRole,
    docket_entry_number: int,
) -> SourceDocumentProvenance:
    return SourceDocumentProvenance(
        source_provider="case.dev",
        source_case_id="case-dev-1",
        source_document_id=document_id,
        court="S.D.N.Y.",
        docket_number="1:26-cv-1",
        document_role=role,
        retrieved_at=datetime(2026, 5, 14, tzinfo=UTC),
        source_url_or_reference=f"case.dev://{document_id}",
        sha256=sha256_text(f"{document_id} source"),
        is_predecision_material=True,
        is_mounted_for_model=True,
        docket_entry_number=docket_entry_number,
        packet_section="filings",
    )


def _unit(unit_id: str, count: str) -> PredictionUnit:
    return PredictionUnit(
        unit_id=unit_id,
        count=count,
        claim_name="Section 10(b)",
        defendant_group="Issuer",
        challenged_by_motion=True,
        challenge_scope=ChallengeScope.ENTIRE_CLAIM,
        unit_confidence=0.95,
        source_citations=(SourceCitation(document_id="complaint", page=1),),
    )
