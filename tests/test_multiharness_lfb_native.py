from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from legalforecast.evals.accounting import accounting_records_from_harness_records
from legalforecast.evals.inspect_task import OfflineMockSolver
from legalforecast.evals.output_parser import parse_model_output
from legalforecast.evals.packet_builder import PacketText, build_model_packet
from legalforecast.evals.scorers import ScoringCase, score_cases
from legalforecast.ingestion.provenance import (
    CasePacketSchema,
    DocumentRole,
    SourceDocumentProvenance,
    sha256_text,
)
from legalforecast.labeling import AmendmentClass, OutcomeCitation, OutcomeLabel
from legalforecast.multiharness.lfb_native import (
    LfbNativeAdapter,
    LfbNativeAdapterError,
)
from legalforecast.multiharness.sandbox import sandbox_policy
from legalforecast.multiharness.spec import RunRequest
from legalforecast.multiharness.task_loaders import LfbTaskLoader
from legalforecast.unitization.schemas import (
    ChallengeScope,
    PredictionUnit,
    SourceCitation,
)

EVALUATION_TIMESTAMP = datetime(2026, 5, 14, 20, 0, tzinfo=UTC)


def test_lfb_native_fixture_projection_parses_accounts_and_scores(
    tmp_path: Path,
) -> None:
    packet = _model_packet()
    adapter = LfbNativeAdapter()
    request = _run_request(adapter, packet, model_key="fixture-model")
    solver = OfflineMockSolver(
        solver_id="offline-fixture",
        raw_output=_raw_output(probability=0.8),
        input_tokens=11,
        output_tokens=7,
        estimated_cost=0.025,
    )

    run = adapter.run_fixture_packet(
        request=request,
        packet=packet,
        solver=solver,
        workspace=tmp_path / "workspace",
        latency_ms=123.5,
    )

    assert run.inspect_run.case_count == 1
    projected = run.projected_results[0]
    record = dict(projected.inspect_record)
    assert record["sample_id"] == "cand-1"
    assert record["candidate_id"] == "cand-1"
    assert record["case_id"] == "case-1"
    assert record["related_family_id"] == "related-family-1"
    assert record["mdl_family_id"] == "mdl-family-1"
    assert record["solver_id"] == "offline-fixture"
    assert record["solver_kind"] == "offline_mock"
    assert record["run_label"] == "full_packet"
    assert record["ablation"] == "full_packet"
    assert record["raw_output_sha256"] == _sha256_text(record["raw_output"])
    assert record["required_unit_ids"] == ["count_i_issuer"]
    assert record["request_count"] == 1
    assert record["input_tokens"] == 11
    assert record["prompt_tokens"] == 11
    assert record["output_tokens"] == 7
    assert record["completion_tokens"] == 7
    assert record["estimated_total_tokens"] == 18
    assert record["total_tokens"] == 18
    assert record["estimated_cost"] == 0.025
    assert record["execution_backend"] == "local_fixture"
    assert record["latency_ms"] == 123.5
    assert record["adapter_id"] == "lfb-native"
    assert record["model_key"] == "fixture-model"
    assert record["community_model_id"] == "lfb-native:fixture-model"
    assert record["model_id"] == "lfb-native:fixture-model"
    assert record["metadata"]["community_model_id"] == "lfb-native:fixture-model"
    assert record["metadata"]["adapter_version"] == adapter.manifest.adapter_version
    assert "raw_output" not in projected.result.public_summary
    assert record["raw_output"] not in json.dumps(
        projected.result.to_record(),
        sort_keys=True,
    )

    parsed = parse_model_output(
        record["raw_output"],
        required_unit_ids=tuple(record["required_unit_ids"]),
    )
    accounting = accounting_records_from_harness_records(
        (record,),
        evaluation_timestamp=EVALUATION_TIMESTAMP,
    )
    assert accounting[0].provider == "lfb-native"
    assert accounting[0].model_id == "lfb-native:fixture-model"
    assert accounting[0].latency_ms == 123.5
    summary = score_cases(
        (
            ScoringCase(
                case_id=record["case_id"],
                candidate_id=record["candidate_id"],
                related_family_id=record["related_family_id"],
                mdl_family_id=record["mdl_family_id"],
                model_id=record["model_id"],
                parsed_output=parsed,
                outcome_labels=(_label("count_i_issuer", dismissed=True),),
            ),
        ),
        base_rate=0.5,
    )
    assert summary.model_id == "lfb-native:fixture-model"
    assert summary.case_count == 1
    assert summary.unit_count == 1


def test_lfb_native_direct_run_is_fixture_only(tmp_path: Path) -> None:
    packet = _model_packet()
    adapter = LfbNativeAdapter()

    with pytest.raises(LfbNativeAdapterError, match="fixture-only"):
        adapter.run(_run_request(adapter, packet, model_key="fixture-model"), tmp_path)


def _run_request(
    adapter: LfbNativeAdapter,
    packet: Any,
    *,
    model_key: str,
) -> RunRequest:
    task = LfbTaskLoader(suite_version="fixture-suite").task_from_record(
        packet.to_record()
    )
    request_record: dict[str, object] = {
        "task": task.to_record(),
        "adapter": adapter.manifest.to_record(),
        "model_key": model_key,
    }
    return RunRequest(
        request_id=f"{task.task_id}:{model_key}",
        task=task,
        adapter=adapter.manifest,
        model_key=model_key,
        sandbox_policy=sandbox_policy(
            policy_id="fixture",
            backend="docker",
            image="python:3.12-slim",
            mounts=(),
            timeout_seconds=30,
        ),
        request_sha256=_record_sha256(request_record),
    )


def _model_packet() -> Any:
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
                _document(
                    "decision",
                    DocumentRole.DECISION,
                    50,
                    mounted=False,
                    predecision=False,
                    outcome=True,
                ),
            ),
        ),
        prediction_units=(_unit(),),
        texts=(
            PacketText(source_document_id="complaint", text="complaint text"),
            PacketText(source_document_id="mtd-memo", text="motion text"),
        ),
        metadata={"judge": "Judge Example"},
        related_family_id="related-family-1",
        mdl_family_id="mdl-family-1",
    )


def _document(
    document_id: str,
    role: DocumentRole,
    docket_entry_number: int,
    *,
    mounted: bool = True,
    predecision: bool = True,
    outcome: bool = False,
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
        is_predecision_material=predecision,
        is_mounted_for_model=mounted,
        docket_entry_number=docket_entry_number,
        contains_target_outcome=outcome,
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


def _raw_output(*, probability: float) -> str:
    return json.dumps(
        {
            "case_assessment": "The count is likely dismissed.",
            "predictions": [
                {
                    "unit_id": "count_i_issuer",
                    "probability_fully_dismissed": probability,
                }
            ],
        },
        sort_keys=True,
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
        label_confidence=0.97,
        supporting_citations=(OutcomeCitation(document_id="decision-1", page=1),),
        first_written_disposition_id="decision-1",
        first_written_disposition_date="2026-05-18",
    )


def _sha256_text(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("value must be a string")
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def _record_sha256(record: dict[str, object]) -> str:
    encoded = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"
