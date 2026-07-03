from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from legalforecast.evals.inspect_task import (
    ConfiguredModelStubSolver,
    HarnessRequest,
    SolverKind,
    SolverResponse,
    build_inspect_samples,
    render_model_prompt,
    run_inspect_fixture,
)
from legalforecast.evals.model_registry import ModelRegistryEntry
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

DECISION_SECRET = "SECRET_DECISION_TEXT: motion granted in full"
LABEL_SECRET = "SECRET_LABEL: count_i_issuer fully_dismissed=true"


def test_model_prompt_omits_decision_label_and_post_decision_sources() -> None:
    packet = _sandbox_packet()

    prompt = render_model_prompt(packet)
    payload = json.loads(prompt)

    assert [document["source_document_id"] for document in payload["documents"]] == [
        "complaint",
        "mtd-memo",
    ]
    assert DECISION_SECRET not in prompt
    assert LABEL_SECRET not in prompt
    assert '"source_document_id": "decision"' not in prompt
    assert "labels-jsonl" not in prompt
    assert "post_decision" not in prompt


def test_adversarial_solver_gets_denials_without_forbidden_content() -> None:
    samples = build_inspect_samples((_sandbox_packet(),), max_tool_calls=5)

    run = run_inspect_fixture(samples, (_AdversarialDocketProbeSolver(),))
    record = run.to_records()[0]
    serialized = json.dumps(record, sort_keys=True)
    denied_logs = [log for log in record["tool_call_logs"] if log["status"] == "denied"]

    assert denied_logs
    assert {log["entry_number"] for log in denied_logs} == {50, 99}
    assert all(log["denial_reason"] == "entry_not_found" for log in denied_logs)
    assert DECISION_SECRET not in serialized
    assert LABEL_SECRET not in serialized
    assert "Motion granted" not in serialized
    assert "fully_dismissed=true" not in serialized


def test_configured_stub_rejects_search_enabled_runs() -> None:
    record = _registry_record()
    record["search_disabled"] = False

    with pytest.raises(ValueError, match="search_disabled"):
        ConfiguredModelStubSolver(
            registry_entry=ModelRegistryEntry.from_record(record),
            stub_raw_output='{"predictions":[]}',
        )


@dataclass(frozen=True, slots=True)
class _AdversarialDocketProbeSolver:
    solver_id: str = "adversarial-docket-probe"

    @property
    def solver_kind(self) -> SolverKind:
        return SolverKind.OFFLINE_MOCK

    def solve(self, request: HarnessRequest) -> SolverResponse:
        listed = request.docket_tool.list_available_docket_entries()
        allowed = request.docket_tool.read_docket_entry(34)
        post_decision = request.docket_tool.read_docket_entry(50)
        missing = request.docket_tool.read_docket_entry(99)
        return SolverResponse(
            raw_output=json.dumps(
                {
                    "available": listed.to_record(),
                    "allowed": allowed.to_record(),
                    "post_decision_probe": post_decision.to_record(),
                    "missing_probe": missing.to_record(),
                },
                sort_keys=True,
            ),
            metadata={"solver_mode": "adversarial_fixture"},
        )


def _sandbox_packet():
    return build_model_packet(
        case_packet=CasePacketSchema(
            candidate_id="cand-sandbox",
            case_id="case-sandbox",
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
                    packet_section="post_decision",
                ),
                _document(
                    "labels-jsonl",
                    DocumentRole.EXCLUSION_NOTE,
                    51,
                    mounted=False,
                    predecision=False,
                    outcome=True,
                    packet_section="labels",
                ),
            ),
        ),
        prediction_units=(_unit(),),
        texts=(
            PacketText(source_document_id="complaint", text="complaint text"),
            PacketText(source_document_id="mtd-memo", text="motion text"),
            PacketText(source_document_id="decision", text=DECISION_SECRET),
            PacketText(source_document_id="labels-jsonl", text=LABEL_SECRET),
        ),
        metadata={"judge": "Judge Example", "nos_macro_category": "securities"},
    )


def _document(
    document_id: str,
    role: DocumentRole,
    docket_entry_number: int,
    *,
    mounted: bool = True,
    predecision: bool = True,
    outcome: bool = False,
    packet_section: str = "filings",
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
        packet_section=packet_section,
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


def _registry_record() -> dict[str, object]:
    return {
        "provider": "example-provider",
        "model_id": "example-model",
        "display_name": "Example Model",
        "model_version_or_snapshot": "2026-05-14",
        "release_timestamp": "2026-05-14T09:00:00Z",
        "release_timestamp_source": "fixture release note",
        "provider_training_cutoff_status": "known",
        "provider_training_cutoff": "2026-04-01",
        "temperature": 0,
        "top_p": 1,
        "max_output_tokens": 4096,
        "network_disabled": True,
        "search_disabled": True,
        "tool_policy": "controlled_docket_tool_only",
        "context_limit": 200000,
        "pricing_source": "provider-price-sheet-2026-05-14",
        "input_token_price": 0.25,
        "output_token_price": 1.0,
        "known_cutoff_publicity_caveats": [],
    }
