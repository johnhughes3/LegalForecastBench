from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from legalforecast.evals.inspect_ai_adapter import (
    InspectAIAdapterFactories,
    InspectAIShimTask,
    build_headline_inspect_ai_task,
    score_output_contract,
)
from legalforecast.evals.inspect_task import RunExecutionBackend, build_inspect_samples
from legalforecast.evals.packet_builder import PacketText, build_model_packet
from legalforecast.ingestion.provenance import (
    CasePacketSchema,
    DocumentRole,
    SourceDocumentProvenance,
    sha256_text,
)
from legalforecast.unitization.schemas import (
    ChallengeScope,
    PredictionUnit,
    SourceCitation,
)


def test_inspect_ai_adapter_builds_dependency_free_shim_task() -> None:
    samples = build_inspect_samples((_model_packet(),), run_label="full_packet")

    build = build_headline_inspect_ai_task(samples, force_shim=True)

    assert build.execution_backend is RunExecutionBackend.INSPECT_AI_SHIM
    assert build.dependency_available is False
    assert build.sample_count == 1
    assert build.run_metadata()["execution_backend"] == "inspect_ai_shim"
    assert "without importing Inspect" in build.dependency_boundary
    assert isinstance(build.task, InspectAIShimTask)

    task = build.task
    sample = task.dataset[0]
    valid_output = json.dumps(
        {
            "case_assessment": "Fixture assessment.",
            "predictions": [
                {
                    "unit_id": "count_i_issuer",
                    "probability_fully_dismissed": 0.42,
                }
            ],
        }
    )
    score = task.scorer.score_output(valid_output, sample.target)
    invalid_score = task.scorer.score_output("not json", sample.target)

    assert sample.id == "cand-1"
    assert sample.metadata["run_label"] == "full_packet"
    assert sample.metadata["execution_backend"] == "inspect_ai_shim"
    assert score.value == "C"
    assert score.valid is True
    assert invalid_score.value == "I"
    assert invalid_score.metadata["parser_status"] == "invalid_json"


def test_inspect_ai_adapter_uses_injected_real_factories() -> None:
    samples = build_inspect_samples((_model_packet(),), run_label="full_packet")

    build = build_headline_inspect_ai_task(
        samples,
        factories=InspectAIAdapterFactories(
            task_factory=_FakeTask,
            sample_factory=_FakeSample,
            solver_factory=_FakeSolver,
            scorer_factory=_FakeScorer,
            dependency_name="inspect_ai",
        ),
    )

    assert build.execution_backend is RunExecutionBackend.INSPECT_AI
    assert build.dependency_available is True
    assert build.dependency_name == "inspect_ai"
    assert build.run_metadata()["execution_backend"] == "inspect_ai"
    assert isinstance(build.task, _FakeTask)
    assert isinstance(build.inspect_samples[0], _FakeSample)
    assert build.to_record()["sample_count"] == 1


def test_contract_scorer_rejects_invalid_targets_without_throwing() -> None:
    score = score_output_contract('{"predictions":[]}', '{"required_unit_ids":[]}')

    assert score.value == "I"
    assert score.valid is False
    assert score.metadata["parser_status"] == "invalid_target"


@dataclass(frozen=True, slots=True)
class _FakeSample:
    id: str
    input: str
    target: str
    metadata: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class _FakeSolver:
    solver_name: str = "fake-generate"


@dataclass(frozen=True, slots=True)
class _FakeScorer:
    scorer_name: str = "fake-contract-scorer"


@dataclass(frozen=True, slots=True)
class _FakeTask:
    dataset: Sequence[object]
    solver: object
    scorer: object
    sandbox: str | None


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
        prediction_units=(_unit(),),
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


def _unit() -> PredictionUnit:
    return PredictionUnit(
        unit_id="count_i_issuer",
        count="I",
        claim_name="Section 10(b)",
        defendant_group="Issuer",
        challenged_by_motion=True,
        challenge_scope=ChallengeScope.ENTIRE_CLAIM,
        unit_confidence=0.95,
        source_citations=(SourceCitation(document_id="complaint", page=1),),
    )
