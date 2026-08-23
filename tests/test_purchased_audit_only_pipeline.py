from __future__ import annotations

import hashlib
import json
import sqlite3
from argparse import Namespace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, NoReturn, cast

import legalforecast.labeling.llm_pipeline as llm_pipeline
import pytest
from legalforecast import cli
from legalforecast.cli import main
from legalforecast.evals.inspect_task import SolverResponse
from legalforecast.evals.provider_spend_control import AttemptLease, ProviderSpendKey
from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPacerPurchaseAttempt,
    CaseDevPacerPurchaseStatus,
)
from legalforecast.ingestion.free_document_downloader import FixtureFreeDocumentSource
from legalforecast.ingestion.mistral_markdown_parser import EXPECTED_PARSER_REVISION
from legalforecast.ingestion.packet_input_planner import plan_packet_build_inputs
from legalforecast.ingestion.provenance import DocumentRole
from legalforecast.ingestion.purchased_document_recovery import (
    PurchasedDocumentRecoveryRequest,
    purchased_document_download_manifest_records,
    recover_purchased_documents,
)
from legalforecast.labeling.provider_journal import (
    ProviderAttemptJournal,
    ProviderCallIdentity,
    ProviderJournalError,
)
from legalforecast.labeling.unitizer_terminal import (
    LlmStageAUnitizerTerminalEscalation,
)
from legalforecast.unitization.review import apply_unitization_reviews
from legalforecast.unitization.unitizer_terminal_review import (
    build_unitizer_terminal_review_queue_record,
)

JsonRecord = dict[str, Any]
ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "model_registries/cycle-1-2026-06-30.json"


def test_unitizer_terminal_baton_skips_provider_and_emits_empty_raw_envelope(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    markdown_root = tmp_path / "markdown"
    parser_records: list[JsonRecord] = []
    for document_id, text in (
        ("complaint", "Count I asserts a claim."),
        ("mtd", "Defendant moves to dismiss Count I."),
    ):
        path = markdown_root / "cand-1" / f"{document_id}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        parser_records.append(
            {
                "candidate_id": "cand-1",
                "source_document_id": document_id,
                "status": "succeeded",
                "markdown_path": f"cand-1/{document_id}.md",
            }
        )
    documents = llm_pipeline._predecision_documents(
        _selection(),
        parser_by_key=llm_pipeline._parser_records_by_candidate_and_document(
            parser_records
        ),
        markdown_root=markdown_root,
        provider_attempt_namespace="claim-ontology-v5",
    )
    prompt = llm_pipeline._unitization_prompt(
        _selection(), documents, provider_attempt_namespace="claim-ontology-v5"
    )
    escalation = LlmStageAUnitizerTerminalEscalation(
        candidate_id="cand-1",
        case_id="case-1",
        unitizer_model_key="openai:gpt-test",
        model_registry_sha256="b" * 64,
        provider_attempt_namespace="claim-ontology-v5",
        prompt=prompt,
        prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),
        predecision_source_commitments=tuple(
            {
                "source_document_id": document.source_document_id,
                "document_role": document.document_role.value,
                "docket_entry_number": document.docket_entry_number,
                "description": document.description,
                "markdown_sha256": "sha256:"
                + hashlib.sha256(document.markdown.encode()).hexdigest(),
            }
            for document in documents
        ),
        failed_attempts=tuple(
            {
                "attempt_ordinal": ordinal,
                "raw_response_sha256": "sha256:" + str(ordinal) * 64,
                "normalized_response_sha256": "sha256:" + chr(96 + ordinal) * 64,
                "failure_type": "ValueError",
                "failure_message": f"failed {ordinal}",
            }
            for ordinal in (1, 2, 3)
        ),
    )
    monkeypatch.setattr(
        llm_pipeline,
        "complete_live_prompt",
        lambda *args, **kwargs: pytest.fail("terminal candidate reached provider"),
    )

    result = llm_pipeline.llm_unitize_cases(
        selection_records=(_selection(),),
        parser_records=parser_records,
        markdown_root=markdown_root,
        registry_entry=llm_pipeline.ModelRegistryEntry.from_record(_registry_record()),
        model_registry_sha256="b" * 64,
        provider_attempt_namespace="claim-ontology-v5",
        terminal_escalations={
            "cand-1": (
                escalation,
                {"path": "/receipts/cand-1.json", "sha256": "sha256:" + "d" * 64},
            )
        },
    )

    assert result.records == (
        {"candidate_id": "cand-1", "case_id": "case-1", "prediction_units": []},
    )
    [audit] = result.audit_records
    assert audit["status"] == "terminal_escalation"
    assert audit["terminal_escalation"] == escalation.to_record()
    assert audit["terminal_escalation_receipt"] == {
        "path": "/receipts/cand-1.json",
        "sha256": "sha256:" + "d" * 64,
    }
    assert result.terminal_review_queue_records == (
        build_unitizer_terminal_review_queue_record(escalation.to_record()),
    )
    assert (
        "terminal_escalation_receipt" not in (result.terminal_review_queue_records[0])
    )


def test_structural_reviewer_preserves_unitizer_terminal_without_provider(
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(
        llm_pipeline,
        "complete_live_prompt",
        lambda *args, **kwargs: pytest.fail("terminal baton reached reviewer provider"),
    )

    result = llm_pipeline.llm_review_stage_a_units(
        selection_records=(_selection(),),
        parser_records=(),
        prediction_unit_records=(
            {"candidate_id": "cand-1", "case_id": "case-1", "prediction_units": []},
        ),
        markdown_root="/unused",
        registry_entry=llm_pipeline.ModelRegistryEntry.from_record(_registry_record()),
        model_registry_sha256="b" * 64,
        unitizer_terminal_candidates=("cand-1",),
        provider_attempt_namespace="claim-ontology-v4",
    )

    assert result.records == ()
    assert result.terminal_review_queue_records == ()
    assert result.audit_records == (
        {
            "stage": "llm-review-stage-a",
            "status": "unitizer_terminal_preserved",
            "candidate_id": "cand-1",
            "case_id": "case-1",
            "model_key": "openai:gpt-test",
            "model_registry_sha256": "b" * 64,
            "raw_prediction_units_sha256": llm_pipeline.canonical_sha256(
                {
                    "candidate_id": "cand-1",
                    "case_id": "case-1",
                    "prediction_units": [],
                }
            ),
            "structural_flags_sha256": llm_pipeline.canonical_records_sha256(()),
            "flag_count": 0,
        },
    )


def test_structural_reviewer_rejects_conflicting_terminal_evidence() -> None:
    with pytest.raises(
        llm_pipeline.LlmPipelineError,
        match="both unitizer and structural-review terminal evidence",
    ):
        llm_pipeline.llm_review_stage_a_units(
            selection_records=(_selection(),),
            parser_records=(),
            prediction_unit_records=(
                {"candidate_id": "cand-1", "case_id": "case-1", "prediction_units": []},
            ),
            markdown_root="/unused",
            registry_entry=llm_pipeline.ModelRegistryEntry.from_record(
                _registry_record()
            ),
            model_registry_sha256="b" * 64,
            terminal_escalations={"cand-1": cast(Any, (object(), {}))},
            unitizer_terminal_candidates=("cand-1",),
            provider_attempt_namespace="claim-ontology-v4",
        )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("stage", "llm-unitize"),
        ("status", "passed"),
        ("candidate_id", "other"),
        ("case_id", "other-case"),
        ("model_key", "openai:other"),
        ("model_registry_sha256", "c" * 64),
        ("raw_prediction_units_sha256", "d" * 64),
        ("structural_flags_sha256", "e" * 64),
        ("flag_count", 1),
        ("provider_prompt_sha256", "f" * 64),
    ),
)
def test_unitizer_terminal_preserved_audit_is_closed_and_exact(
    field: str, value: object
) -> None:
    raw = {"candidate_id": "cand-1", "case_id": "case-1", "prediction_units": []}
    expected = llm_pipeline.unitizer_terminal_preserved_audit_record(
        candidate_id="cand-1",
        case_id="case-1",
        reviewer_model_key="openai:gpt-test",
        model_registry_sha256="b" * 64,
        raw_prediction_units=raw,
    )
    mutated = {**expected, field: value}

    with pytest.raises(llm_pipeline.LlmPipelineError, match="exact unitizer terminal"):
        llm_pipeline.validate_unitizer_terminal_preserved_audit_record(
            mutated,
            candidate_id="cand-1",
            case_id="case-1",
            reviewer_model_key="openai:gpt-test",
            model_registry_sha256="b" * 64,
            raw_prediction_units=raw,
        )


def test_unitizer_terminal_preserved_audit_rejects_nonempty_raw_envelope() -> None:
    with pytest.raises(
        llm_pipeline.LlmPipelineError,
        match="exact empty raw envelope",
    ):
        llm_pipeline.unitizer_terminal_preserved_audit_record(
            candidate_id="cand-1",
            case_id="case-1",
            reviewer_model_key="openai:gpt-test",
            model_registry_sha256="b" * 64,
            raw_prediction_units={
                "candidate_id": "cand-1",
                "case_id": "case-1",
                "prediction_units": [{"unit_id": "invented"}],
            },
        )


class _FakeSpendAuthority:
    def __init__(self, **kwargs: object) -> None:
        del kwargs

    def authorize_attempt(
        self,
        key: ProviderSpendKey,
        *,
        reservation_microusd: int,
    ) -> AttemptLease:
        return AttemptLease(
            attempt_id="b" * 64,
            authority_identity_sha256="a" * 64,
            logical_call_key=key.logical_call_key,
            attempt_ordinal=1,
            reservation_microusd=reservation_microusd,
        )

    def record_response(self, lease: AttemptLease, **kwargs: object) -> None:
        del lease, kwargs

    def record_failure(self, lease: AttemptLease, **kwargs: object) -> None:
        del lease, kwargs

    def reconcile_ambiguous(self, lease: AttemptLease, **kwargs: object) -> None:
        del lease, kwargs

    def snapshot(self) -> object:
        raise AssertionError("snapshot is not used by this fixture")


def test_live_stage_a_requires_successor_namespace_before_journal_or_transport(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """A missing namespace cannot mint a fresh call under the legacy identity."""

    journal_path = tmp_path / "provider-attempts.sqlite3"
    markdown_root = tmp_path / "markdown"
    parser_records: list[JsonRecord] = []
    for document_id, text in (
        ("complaint", "Count I alleges a Section 10(b) claim."),
        ("mtd", "Defendant moves to dismiss Count I."),
    ):
        path = markdown_root / "cand-1" / f"{document_id}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        parser_records.append(
            {
                "candidate_id": "cand-1",
                "source_document_id": document_id,
                "status": "succeeded",
                "markdown_path": f"cand-1/{document_id}.md",
            }
        )
    monkeypatch.setattr(
        llm_pipeline,
        "complete_live_prompt",
        lambda *args, **kwargs: pytest.fail("provider transport must not be reached"),
    )

    with pytest.raises(
        llm_pipeline.LlmPipelineError,
        match="requires the closed successor provider-attempt namespace",
    ):
        llm_pipeline.llm_unitize_cases(
            selection_records=(_selection(),),
            parser_records=parser_records,
            markdown_root=markdown_root,
            registry_entry=llm_pipeline.ModelRegistryEntry.from_record(
                _registry_record()
            ),
            model_registry_sha256="b" * 64,
            provider_journal_path=journal_path,
            provider_cycle_id="cycle-1",
            provider_cycle_caps_sha256="sha256:" + "c" * 64,
        )

    with sqlite3.connect(journal_path) as connection:
        row_count = connection.execute(
            "SELECT COUNT(*) FROM provider_attempts"
        ).fetchone()
    assert row_count == (0,)


def test_structural_review_rejects_unitizer_only_v5_before_prompt_or_journal(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    registry_entry = llm_pipeline.ModelRegistryEntry.from_record(_registry_record())

    def unexpected_prompt(**_kwargs: Any) -> NoReturn:
        pytest.fail("structural prompt construction must not run")

    def unexpected_completion(*_args: Any, **_kwargs: Any) -> NoReturn:
        pytest.fail("provider transport must not run")

    monkeypatch.setattr(
        llm_pipeline,
        "stage_a_structural_review_prompt_records",
        unexpected_prompt,
    )
    monkeypatch.setattr(
        llm_pipeline,
        "complete_live_prompt",
        unexpected_completion,
    )

    with pytest.raises(
        llm_pipeline.LlmPipelineError,
        match=r"claim-ontology-v5.*llm-review-stage-a",
    ):
        llm_pipeline.llm_review_stage_a_units(
            selection_records=(),
            parser_records=(),
            prediction_unit_records=(),
            markdown_root=tmp_path,
            registry_entry=registry_entry,
            model_registry_sha256="b" * 64,
            provider_journal_path=tmp_path / "provider-attempts.sqlite3",
            provider_cycle_cap_usd=100.0,
            provider_cycle_id="cycle-1",
            provider_cycle_caps_sha256="sha256:" + "c" * 64,
            provider_attempt_namespace="claim-ontology-v5",
        )
    assert not (tmp_path / "provider-attempts.sqlite3").exists()

    with pytest.raises(
        llm_pipeline.LlmPipelineError,
        match=r"claim-ontology-v5.*llm-review-stage-a",
    ):
        llm_pipeline.recover_llm_stage_a_structural_review_reconstruction(
            selection_record={},
            parser_records=(),
            prediction_unit_records=(),
            markdown_root=tmp_path,
            markdown_bytes=None,
            registry_entry=registry_entry,
            model_registry_sha256="b" * 64,
            provider_journal_path=tmp_path / "provider-attempts.sqlite3",
            provider_cycle_cap_usd=100.0,
            provider_cycle_id="cycle-1",
            provider_cycle_caps_sha256="sha256:" + "c" * 64,
            provider_account="default",
            provider_attempt_namespace="claim-ontology-v5",
        )

    with pytest.raises(
        llm_pipeline.LlmPipelineError,
        match=r"claim-ontology-v5.*llm-review-stage-a",
    ):
        llm_pipeline.build_llm_stage_a_structural_review_terminal_escalation(
            selection_record={},
            parser_records=(),
            prediction_unit_records=(),
            markdown_root=tmp_path,
            markdown_bytes=None,
            registry_entry=registry_entry,
            model_registry_sha256="b" * 64,
            provider_journal_path=tmp_path / "provider-attempts.sqlite3",
            provider_cycle_cap_usd=100.0,
            provider_cycle_id="cycle-1",
            provider_cycle_caps_sha256="sha256:" + "c" * 64,
            provider_account="default",
            provider_attempt_namespace="claim-ontology-v5",
        )
    assert not (tmp_path / "provider-attempts.sqlite3").exists()


@pytest.mark.parametrize(
    "provider_attempt_namespace",
    ("claim-ontology-v2", "claim-ontology-v3", "claim-ontology-v4"),
)
def test_google_structural_review_passes_frozen_response_schema(
    tmp_path: Path,
    monkeypatch: Any,
    provider_attempt_namespace: str,
) -> None:
    markdown_root = tmp_path / "markdown"
    parser_records: list[JsonRecord] = []
    for document_id, text in (
        ("complaint", "Count I alleges a Section 10(b) claim."),
        ("mtd", "Defendant moves to dismiss Count I."),
    ):
        path = markdown_root / "cand-1" / f"{document_id}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        parser_records.append(
            {
                "candidate_id": "cand-1",
                "source_document_id": document_id,
                "status": "succeeded",
                "markdown_path": f"cand-1/{document_id}.md",
            }
        )
    response = SolverResponse(
        raw_output='{"structural_flags":[]}',
        input_tokens=11,
        output_tokens=6,
        estimated_cost=0.02,
    )
    captured: dict[str, object] = {}

    def completion(*_args: Any, **kwargs: Any) -> SolverResponse:
        captured["response_json_schema"] = kwargs["response_json_schema"]
        handler = kwargs["attempt_handler"]
        handler.run_attempt(1, lambda: {"fixture": "google-response"})
        handler.settle_attempt(
            1,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            actual_cost_usd=response.estimated_cost,
            raw_output=response.raw_output,
        )
        return response

    monkeypatch.setattr(llm_pipeline, "complete_live_prompt", completion)
    registry = _registry_record()
    registry.update(
        {
            "provider": "google",
            "model_id": "gemini-test",
            "display_name": "Gemini Test",
            "model_version_or_snapshot": "gemini-test-2026-06-26",
        }
    )
    result = llm_pipeline.llm_review_stage_a_units(
        selection_records=(_selection(),),
        parser_records=parser_records,
        prediction_unit_records=(_prediction_units(),),
        markdown_root=markdown_root,
        registry_entry=llm_pipeline.ModelRegistryEntry.from_record(registry),
        model_registry_sha256="b" * 64,
        provider_journal_path=tmp_path / "provider-attempts.sqlite3",
        provider_cycle_cap_usd=100.0,
        provider_cycle_id="cycle-1",
        provider_cycle_caps_sha256="sha256:" + "c" * 64,
        provider_attempt_namespace=provider_attempt_namespace,
    )

    assert result.records == ()
    if provider_attempt_namespace == "claim-ontology-v2":
        assert captured["response_json_schema"] is None
        return
    schema = cast(dict[str, Any], captured["response_json_schema"])
    flag_item = schema["properties"]["structural_flags"]["items"]
    assert flag_item["properties"]["affected_unit_ids"]["items"]["enum"] == ["unit-1"]
    if provider_attempt_namespace == "claim-ontology-v3":
        assert flag_item["properties"]["source_document_ids"]["items"]["enum"] == [
            "complaint",
            "mtd",
        ]
    else:
        evidence_item = flag_item["properties"]["evidence_spans"]["items"]
        assert evidence_item["properties"]["source_document_id"]["enum"] == [
            "complaint",
            "mtd",
        ]
        assert "citation_excerpt" not in flag_item["properties"]


def test_reconstruction_prestate_isolates_legacy_and_successor_rows() -> None:
    """Equal ordinals in the shared journal remain contract-disjoint."""

    prompt = "same provider prompt"
    registry_sha = "a" * 64
    common: JsonRecord = {
        "stage": "llm-unitize",
        "candidate_id": "cand-1",
        "model_key": "anthropic:model",
        "attempt_ordinal": 1,
        "status": "settled",
        "failure_type": "ValueError",
        "reconstructed_result_json": '{"candidate_id":"cand-1"}',
        "prompt_text": prompt,
        "model_registry_sha256": registry_sha,
    }
    legacy = {
        **common,
        "logical_call_key": ProviderCallIdentity(
            stage="llm-unitize",
            candidate_id="cand-1",
            model_key="anthropic:model",
            prompt=prompt,
            model_registry_sha256=registry_sha,
        ).logical_call_key,
    }
    successor = {
        **common,
        "logical_call_key": ProviderCallIdentity(
            stage="llm-unitize",
            candidate_id="cand-1",
            model_key="anthropic:model",
            prompt=prompt,
            model_registry_sha256=registry_sha,
            prompt_contract="claim-ontology-v2",
        ).logical_call_key,
    }

    expected_legacy = dict(legacy)
    expected_legacy["status"] = "reconstruction_failed"
    expected_legacy["reconstructed_result_json"] = None
    assert cli._pre_reconstruction_provider_state_sha256(
        (legacy, successor),
        stage="llm-unitize",
        candidate_id="cand-1",
        model_key="anthropic:model",
        attempt_ordinal=1,
    ) == cli._canonical_json_sha256((expected_legacy, successor))

    expected_successor = dict(successor)
    expected_successor["status"] = "reconstruction_failed"
    expected_successor["reconstructed_result_json"] = None
    assert cli._pre_reconstruction_provider_state_sha256(
        (legacy, successor),
        stage="llm-unitize",
        candidate_id="cand-1",
        model_key="anthropic:model",
        attempt_ordinal=1,
        provider_attempt_namespace="claim-ontology-v2",
    ) == cli._canonical_json_sha256((legacy, expected_successor))


def test_reconstruction_cli_resumes_settlement_and_rejects_tampered_receipt(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    output_root = tmp_path / "recovery"
    recovery_path = output_root / "receipt.json"
    journal_path = tmp_path / "provider-attempts.sqlite3"
    journal_path.write_bytes(b"journal fixture")
    prompt_text = "fixture unitization prompt"
    model_registry_sha256 = "1" * 64
    failed_row: JsonRecord = {
        "logical_call_key": ProviderCallIdentity(
            stage="llm-unitize",
            candidate_id="cand-1",
            model_key="anthropic:model",
            prompt=prompt_text,
            model_registry_sha256=model_registry_sha256,
        ).logical_call_key,
        "stage": "llm-unitize",
        "candidate_id": "cand-1",
        "model_key": "anthropic:model",
        "attempt_ordinal": 2,
        "status": "reconstruction_failed",
        "failure_type": "ValueError",
        "reconstructed_result_json": None,
        "completed_at": "2026-08-08T12:00:00Z",
        "prompt_text": prompt_text,
        "model_registry_sha256": model_registry_sha256,
    }
    settled_row: JsonRecord = {
        **failed_row,
        "status": "settled",
        "reconstructed_result_json": '{"candidate_id":"cand-1"}',
    }
    rows = [failed_row]

    class _Caps:
        def __init__(self) -> None:
            self.providers = {"anthropic": SimpleNamespace(account=None)}

        @staticmethod
        def cap_usd(provider: str) -> float:
            assert provider.lower() == "anthropic"
            return 200.0

        @staticmethod
        def account(provider: str) -> str:
            raise AssertionError(
                f"legacy local cap for {provider} must retain the default account"
            )

    lineage = SimpleNamespace(
        selection_records=({"candidate_id": "cand-1", "case_id": "case-1"},),
        parser_records=(),
        registry_entry=SimpleNamespace(
            registry_key="anthropic:model",
            provider="Anthropic",
        ),
        registry_sha256="1" * 64,
        provider_caps=_Caps(),
        provider_caps_sha256="2" * 64,
        provider_journal_path=journal_path,
        cohort_cycle_id="cycle-1",
        input_paths=(journal_path,),
        input_commitments={"journal": "3" * 64},
        markdown_root=tmp_path / "markdown",
        markdown_bytes={},
    )
    result = llm_pipeline.LlmUnitizationReconstructionRecovery(
        candidate_id="cand-1",
        case_id="case-1",
        attempt_ordinal=2,
        raw_response_sha256="4" * 64,
        normalized_response_sha256="5" * 64,
        prediction_units=(),
        review_items=(),
    )
    calls = 0

    provider_accounts: list[object] = []

    def recover(**kwargs: object) -> object:
        nonlocal calls
        provider_accounts.append(kwargs["provider_account"])
        calls += 1
        if calls == 1:
            rows[0] = settled_row
            raise llm_pipeline.LlmPipelineError("simulated crash after settlement")
        return result

    monkeypatch.setattr(
        cli, "_verify_stage_a_unitization_lineage", lambda *a, **k: lineage
    )
    monkeypatch.setattr(cli, "_require_stage_a_lineage_unchanged", lambda lineage: None)
    monkeypatch.setattr(cli, "_stage_a_provider_attempt_rows", lambda path: tuple(rows))
    monkeypatch.setattr(cli, "recover_llm_unitization_reconstruction", recover)
    monkeypatch.setattr(cli, "verify_provider_journal_identity", lambda *a, **k: None)
    monkeypatch.setattr(cli, "_write_acquisition_completion", lambda *a, **k: None)
    args = Namespace(
        execute=True,
        output_root=output_root,
        recovery_output=recovery_path,
        resume=True,
        markdown_root=tmp_path / "markdown",
        candidate_id="cand-1",
    )

    with pytest.raises(cli.CommandError, match="simulated crash after settlement"):
        cli._cmd_acquisition_recover_llm_unitize_reconstruction(args)
    assert not recovery_path.exists()

    assert cli._cmd_acquisition_recover_llm_unitize_reconstruction(args) == 0
    receipt = json.loads(recovery_path.read_text(encoding="utf-8"))
    assert receipt[
        "provider_journal_before_state_sha256"
    ] == cli._canonical_json_sha256((failed_row,))
    assert calls == 2

    receipt["provider_journal_before_state_sha256"] = "f" * 64
    recovery_path.write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(cli.CommandError, match="recovery receipt changed"):
        cli._cmd_acquisition_recover_llm_unitize_reconstruction(args)
    assert calls == 3
    assert provider_accounts == ["default", "default", "default"]


def test_reconstruction_cli_rejects_absent_journal_without_creating_it(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    journal_path = tmp_path / "absent-provider-attempts.sqlite3"
    lineage = SimpleNamespace(
        selection_records=({"candidate_id": "cand-1", "case_id": "case-1"},),
        provider_journal_path=journal_path,
        cohort_cycle_id="cycle-1",
        provider_caps_sha256="2" * 64,
    )
    monkeypatch.setattr(
        cli,
        "_verify_stage_a_unitization_lineage",
        lambda *args, **kwargs: lineage,
    )
    monkeypatch.setattr(
        cli,
        "recover_llm_unitization_reconstruction",
        lambda **kwargs: pytest.fail("provider-free recovery must not be entered"),
    )
    args = Namespace(
        execute=True,
        output_root=tmp_path / "output",
        recovery_output=None,
        resume=True,
        markdown_root=tmp_path / "markdown",
        candidate_id="cand-1",
    )

    with pytest.raises(
        cli.CommandError, match="provider journal is not a regular file"
    ):
        cli._cmd_acquisition_recover_llm_unitize_reconstruction(args)
    assert not journal_path.exists()


def test_structural_review_reconstruction_cli_preserves_completed_run_card_on_resume(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    output_root = tmp_path / "recovery"
    recovery_path = output_root / "receipt.json"
    journal_path = tmp_path / "provider-attempts.sqlite3"
    journal_path.write_bytes(b"journal fixture")
    registry_path = tmp_path / "reviewer-registry.json"
    registry_path.write_text("{}\n", encoding="utf-8")
    unitization_card = tmp_path / "unitize.json"
    unitization_card.write_text(
        json.dumps(
            {"model_execution": {"provider_attempt_namespace": "claim-ontology-v2"}}
        ),
        encoding="utf-8",
    )
    prompt_text = "fixture structural-review prompt"
    model_registry_sha256 = "1" * 64
    failed_row: JsonRecord = {
        "logical_call_key": ProviderCallIdentity(
            stage="llm-review-stage-a",
            candidate_id="cand-1",
            model_key="google:reviewer",
            prompt=prompt_text,
            model_registry_sha256=model_registry_sha256,
            prompt_contract="claim-ontology-v2",
        ).logical_call_key,
        "stage": "llm-review-stage-a",
        "candidate_id": "cand-1",
        "model_key": "google:reviewer",
        "attempt_ordinal": 1,
        "status": "reconstruction_failed",
        "failure_type": "LlmResponseValidationError",
        "reconstructed_result_json": None,
        "completed_at": "2026-08-08T12:00:00Z",
        "prompt_text": prompt_text,
        "model_registry_sha256": model_registry_sha256,
    }
    settled_row: JsonRecord = {
        **failed_row,
        "status": "settled",
        "reconstructed_result_json": '{"structural_flags":[]}',
    }
    rows = [failed_row]
    lineage = SimpleNamespace(
        selection_records=({"candidate_id": "cand-1", "case_id": "case-1"},),
        parser_records=(),
        provider_journal_path=journal_path,
        provider_caps=SimpleNamespace(
            cap_usd=lambda provider: 200.0,
            providers={"google": SimpleNamespace(account=None)},
        ),
        provider_caps_sha256="2" * 64,
        cohort_cycle_id="cycle-1",
        input_commitments={"selection": "3" * 64},
        markdown_bytes={},
    )
    registry_entry = SimpleNamespace(registry_key="google:reviewer", provider="google")
    result = llm_pipeline.LlmStageAStructuralReviewReconstructionRecovery(
        candidate_id="cand-1",
        case_id="case-1",
        attempt_ordinal=1,
        raw_response_sha256="4" * 64,
        normalized_response_sha256="5" * 64,
        structural_flags=(),
    )
    calls = 0

    def recover(**kwargs: object) -> object:
        nonlocal calls
        assert kwargs["provider_account"] == "default"
        assert kwargs["provider_attempt_namespace"] == "claim-ontology-v2"
        calls += 1
        rows[0] = settled_row
        return result

    monkeypatch.setattr(
        cli,
        "_verified_shared_provider_chain",
        lambda *args, **kwargs: (lineage, unitization_card),
    )
    monkeypatch.setattr(
        cli,
        "_registry_entry_for_key",
        lambda *args, **kwargs: (registry_entry, "1" * 64),
    )
    monkeypatch.setattr(cli, "_require_stage_a_lineage_unchanged", lambda lineage: None)
    monkeypatch.setattr(
        cli, "_provider_stage_attempt_rows", lambda path, *, stage: tuple(rows)
    )
    monkeypatch.setattr(
        cli, "recover_llm_stage_a_structural_review_reconstruction", recover
    )
    monkeypatch.setattr(cli, "_read_records", lambda path: [])
    monkeypatch.setattr(
        cli, "_stage_a_file_commitment", lambda path: {"path": str(path)}
    )
    args = Namespace(
        execute=True,
        output_root=output_root,
        run_card_output=output_root / "run-card.json",
        log_output=output_root / "completion.jsonl",
        recovery_output=recovery_path,
        resume=True,
        provider_authority_table=None,
        selection=tmp_path / "selection.jsonl",
        parser_manifest=tmp_path / "parser.jsonl",
        prediction_units=tmp_path / "units.jsonl",
        unitization_review_queue=tmp_path / "queue.jsonl",
        markdown_root=tmp_path / "markdown",
        model_registry=registry_path,
        model_key="google:reviewer",
        candidate_id="cand-1",
        provider_cycle_caps=tmp_path / "caps.json",
    )

    assert cli._cmd_acquisition_recover_llm_review_stage_a_reconstruction(args) == 0
    first_receipt = json.loads(recovery_path.read_text(encoding="utf-8"))
    first_run_card = cast(Path, args.run_card_output).read_bytes()
    first_log = cast(Path, args.log_output).read_bytes()
    first_journal = journal_path.read_bytes()
    assert cli._cmd_acquisition_recover_llm_review_stage_a_reconstruction(args) == 0
    assert json.loads(recovery_path.read_text(encoding="utf-8")) == first_receipt
    assert cast(Path, args.run_card_output).read_bytes() == first_run_card
    assert cast(Path, args.log_output).read_bytes() == first_log
    assert journal_path.read_bytes() == first_journal
    assert calls == 2


@pytest.mark.parametrize(
    ("requested_namespace", "expected_namespace"),
    ((None, "claim-ontology-v2"), ("claim-ontology-v3", "claim-ontology-v3")),
)
def test_terminalize_structural_review_cli_writes_provider_free_receipt(
    tmp_path: Path,
    monkeypatch: Any,
    requested_namespace: str | None,
    expected_namespace: str,
) -> None:
    """The terminal route verifies unchanged rows and writes no provider state."""

    output_root = tmp_path / "terminalize"
    receipt_path = output_root / "receipt.json"
    journal_path = tmp_path / "provider-attempts.sqlite3"
    journal_path.write_bytes(b"journal fixture")
    selection_path = tmp_path / "selection.jsonl"
    parser_path = tmp_path / "parser.jsonl"
    units_path = tmp_path / "units.jsonl"
    queue_path = tmp_path / "queue.jsonl"
    unitization_card = tmp_path / "unitize.json"
    unitization_card.write_text(
        json.dumps(
            {"model_execution": {"provider_attempt_namespace": "claim-ontology-v2"}}
        ),
        encoding="utf-8",
    )
    registry_path = tmp_path / "reviewer-registry.json"
    caps_path = tmp_path / "caps.json"
    candidate_id = "72270301"
    selection = {"candidate_id": candidate_id, "case_id": "case-1"}
    lineage = SimpleNamespace(
        selection_records=(selection,),
        parser_records=(),
        provider_journal_path=journal_path,
        provider_caps=SimpleNamespace(
            cap_usd=lambda provider: 200.0,
            providers={"google": SimpleNamespace(account=None)},
        ),
        provider_caps_sha256="2" * 64,
        cohort_cycle_id="cycle-1",
        markdown_bytes={},
    )
    registry_entry = SimpleNamespace(registry_key="google:reviewer", provider="google")
    provider_rows = (
        {
            "stage": "llm-review-stage-a",
            "candidate_id": candidate_id,
            "status": "reconstruction_failed",
        },
    )
    receipt: JsonRecord = {
        "schema_version": str(
            llm_pipeline.LLM_STAGE_A_STRUCTURAL_REVIEW_TERMINAL_ESCALATION_V1
        ),
        "candidate_id": candidate_id,
    }
    completion_calls: list[dict[str, Any]] = []

    monkeypatch.setattr(
        cli,
        "_verified_shared_provider_chain",
        lambda *args, **kwargs: (lineage, unitization_card),
    )
    monkeypatch.setattr(
        cli,
        "_registry_entry_for_key",
        lambda *args, **kwargs: (registry_entry, "1" * 64),
    )
    monkeypatch.setattr(cli, "_require_stage_a_lineage_unchanged", lambda lineage: None)
    monkeypatch.setattr(
        cli,
        "_provider_stage_attempt_rows",
        lambda path, *, stage: provider_rows,
    )

    def terminalize(**kwargs: object) -> object:
        assert kwargs["provider_attempt_namespace"] == expected_namespace
        return SimpleNamespace(to_record=lambda: receipt)

    monkeypatch.setattr(
        cli,
        "build_llm_stage_a_structural_review_terminal_escalation",
        terminalize,
    )
    monkeypatch.setattr(cli, "_read_records", lambda path: [])
    monkeypatch.setattr(
        cli,
        "_write_or_verify_immutable_recovery_completion",
        lambda args, **kwargs: completion_calls.append(kwargs),
    )
    args = Namespace(
        execute=True,
        provider_authority_table=None,
        output_root=output_root,
        terminal_escalation_output=receipt_path,
        resume=False,
        selection=selection_path,
        parser_manifest=parser_path,
        prediction_units=units_path,
        unitization_review_queue=queue_path,
        markdown_root=tmp_path / "markdown",
        model_registry=registry_path,
        model_key="google:reviewer",
        candidate_id=candidate_id,
        provider_cycle_caps=caps_path,
        provider_attempt_namespace=requested_namespace,
    )

    assert cli._cmd_acquisition_terminalize_llm_review_stage_a(args) == 0
    assert json.loads(receipt_path.read_text(encoding="utf-8")) == receipt
    assert completion_calls == [
        {
            "stage": "terminalize-llm-review-stage-a-reconstruction",
            "input_paths": (
                selection_path,
                parser_path,
                units_path,
                queue_path,
                unitization_card,
                registry_path,
                caps_path,
                journal_path,
            ),
            "output_paths": (receipt_path,),
            "extra": {},
        }
    ]


def test_verified_terminal_escalations_rebuilds_the_exact_receipt(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """A later resume accepts only a receipt reconstructed from the journal."""

    candidate_id = "72270301"
    receipt_path = tmp_path / "receipt.json"
    receipt: JsonRecord = {
        "schema_version": str(
            llm_pipeline.LLM_STAGE_A_STRUCTURAL_REVIEW_TERMINAL_ESCALATION_V1
        ),
        "candidate_id": candidate_id,
    }
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    lineage = SimpleNamespace(
        selection_records=({"candidate_id": candidate_id, "case_id": "case-1"},),
        parser_records=(),
        provider_journal_path=tmp_path / "provider-attempts.sqlite3",
        provider_caps=SimpleNamespace(
            cap_usd=lambda provider: 200.0,
            providers={"google": SimpleNamespace(account=None)},
        ),
        provider_caps_sha256="2" * 64,
        cohort_cycle_id="cycle-1",
        markdown_bytes={},
    )
    registry_entry = SimpleNamespace(registry_key="google:reviewer", provider="google")
    monkeypatch.setattr(cli, "_read_records", lambda path: [])
    monkeypatch.setattr(
        cli,
        "build_llm_stage_a_structural_review_terminal_escalation",
        lambda **kwargs: SimpleNamespace(to_record=lambda: receipt),
    )
    monkeypatch.setattr(
        cli,
        "_stage_a_file_commitment",
        lambda path: {"path": str(path), "sha256": "a" * 64},
    )

    verified = cli._verified_stage_a_terminal_escalations(
        receipt_paths=(receipt_path,),
        lineage=lineage,
        prediction_units_path=tmp_path / "units.jsonl",
        markdown_root=tmp_path / "markdown",
        registry_entry=registry_entry,
        registry_sha256="1" * 64,
    )

    escalation, commitment = verified[candidate_id]
    assert escalation.to_record() == receipt
    assert commitment == {"path": str(receipt_path), "sha256": "a" * 64}
    with pytest.raises(
        cli.CommandError, match="duplicate Stage A terminal escalation receipt"
    ):
        cli._verified_stage_a_terminal_escalations(
            receipt_paths=(receipt_path, receipt_path),
            lineage=lineage,
            prediction_units_path=tmp_path / "units.jsonl",
            markdown_root=tmp_path / "markdown",
            registry_entry=registry_entry,
            registry_sha256="1" * 64,
        )
    invalid_schema_path = tmp_path / "invalid-schema-receipt.json"
    invalid_schema_path.write_text(
        json.dumps({**receipt, "schema_version": "invalid"}), encoding="utf-8"
    )
    with pytest.raises(cli.CommandError, match="receipt schema is invalid"):
        cli._verified_stage_a_terminal_escalations(
            receipt_paths=(invalid_schema_path,),
            lineage=lineage,
            prediction_units_path=tmp_path / "units.jsonl",
            markdown_root=tmp_path / "markdown",
            registry_entry=registry_entry,
            registry_sha256="1" * 64,
        )
    monkeypatch.setattr(
        cli,
        "build_llm_stage_a_structural_review_terminal_escalation",
        lambda **kwargs: SimpleNamespace(
            to_record=lambda: {**receipt, "changed": True}
        ),
    )
    with pytest.raises(cli.CommandError, match="receipt changed"):
        cli._verified_stage_a_terminal_escalations(
            receipt_paths=(receipt_path,),
            lineage=lineage,
            prediction_units_path=tmp_path / "units.jsonl",
            markdown_root=tmp_path / "markdown",
            registry_entry=registry_entry,
            registry_sha256="1" * 64,
        )

    exhausted_receipt = {
        "schema_version": str(
            llm_pipeline.LLM_STAGE_A_STRUCTURAL_REVIEW_TERMINAL_ESCALATION_V2
        ),
        "candidate_id": candidate_id,
    }
    exhausted_path = tmp_path / "exhausted-receipt.json"
    exhausted_path.write_text(json.dumps(exhausted_receipt), encoding="utf-8")
    monkeypatch.setattr(
        cli,
        "build_llm_stage_a_structural_review_terminal_escalation",
        lambda **kwargs: SimpleNamespace(to_record=lambda: exhausted_receipt),
    )
    assert (
        cli._verified_stage_a_terminal_escalations(
            receipt_paths=(exhausted_path,),
            lineage=lineage,
            prediction_units_path=tmp_path / "units.jsonl",
            markdown_root=tmp_path / "markdown",
            registry_entry=registry_entry,
            registry_sha256="1" * 64,
        )[candidate_id][0].to_record()
        == exhausted_receipt
    )


def test_terminal_escalation_builder_and_queue_fail_closed_on_invalid_inputs(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Provider-free terminal handling rejects malformed source and queue evidence."""

    registry_entry = llm_pipeline.ModelRegistryEntry.from_record(_registry_record())
    builder_kwargs = {
        "selection_record": _selection(),
        "parser_records": (),
        "markdown_root": tmp_path / "markdown",
        "markdown_bytes": None,
        "registry_entry": registry_entry,
        "model_registry_sha256": "b" * 64,
        "provider_journal_path": tmp_path / "provider-attempts.sqlite3",
        "provider_cycle_cap_usd": 100.0,
        "provider_cycle_id": "cycle-1",
        "provider_cycle_caps_sha256": "sha256:" + "c" * 64,
        "provider_account": "default",
    }
    monkeypatch.setattr(llm_pipeline, "_predecision_documents", lambda *a, **k: ())
    monkeypatch.setattr(
        llm_pipeline, "_stage_a_structural_review_prompt", lambda *a, **k: "prompt"
    )
    for records, message in (
        ((_prediction_units(), _prediction_units()), "duplicate raw Stage A"),
        ((), "no raw Stage A"),
        (({**_prediction_units(), "prediction_units": []},), "no Stage A units"),
    ):
        with pytest.raises(llm_pipeline.LlmPipelineError, match=message):
            llm_pipeline.build_llm_stage_a_structural_review_terminal_escalation(
                **builder_kwargs,
                prediction_unit_records=records,
            )
    monkeypatch.setattr(
        llm_pipeline, "_provider_attempt_journal", lambda **kwargs: None
    )
    with pytest.raises(llm_pipeline.LlmPipelineError, match="requires a journal"):
        llm_pipeline.build_llm_stage_a_structural_review_terminal_escalation(
            **builder_kwargs,
            prediction_unit_records=(_prediction_units(),),
        )

    escalation = SimpleNamespace(
        candidate_id="cand-1",
        case_id="case-1",
        escalation_sha256="a" * 64,
        prompt="prompt",
        prompt_sha256="b" * 64,
        frozen_units=({"unit_id": "unit-1"},),
        predecision_source_commitments=(),
        failed_attempts=(),
        raw_prediction_units_sha256="c" * 64,
        reviewer_model_key="google:reviewer",
        model_registry_sha256="d" * 64,
    )
    with pytest.raises(llm_pipeline.LlmPipelineError, match="receipt commitment"):
        llm_pipeline.structural_review_terminal_escalation_queue_records(
            escalation,
            receipt_commitment={"path": "receipt.json"},
        )
    with pytest.raises(llm_pipeline.LlmPipelineError, match="receipt commitment"):
        llm_pipeline.structural_review_terminal_escalation_audit_record(
            escalation,
            receipt_commitment={"path": "receipt.json"},
        )


def test_terminal_queue_merge_fails_closed_for_conflicting_or_ambiguous_reviews() -> (
    None
):
    """A terminal route never silently chooses between already-pending reviews."""

    terminal = {
        "schema_version": "legalforecast.unitization_review_queue.v1",
        "status": "pending_adjudication",
        "candidate_id": "cand-1",
        "case_id": "case-1",
        "unit_id": "unit-1",
        "review_id": "cand-1:unit-1:structural-terminal:abcdefgh",
    }
    assert llm_pipeline.merge_stage_a_review_queue((), (), (terminal,)) == (terminal,)
    with pytest.raises(llm_pipeline.LlmPipelineError, match="queue conflict"):
        llm_pipeline.merge_stage_a_review_queue(
            ({**terminal, "status": "different"},),
            (),
            (terminal,),
        )
    with pytest.raises(llm_pipeline.LlmPipelineError, match="ambiguous unit reviews"):
        llm_pipeline.merge_stage_a_review_queue(
            (
                {**terminal, "review_id": "review-a"},
                {**terminal, "review_id": "review-b"},
            ),
            (),
            (terminal,),
        )
    with pytest.raises(llm_pipeline.LlmPipelineError, match="queue conflict"):
        llm_pipeline.merge_stage_a_review_queue(
            (
                {
                    **terminal,
                    "review_id": "construction-review",
                    "terminal_escalation": {"different": True},
                },
            ),
            (),
            (terminal,),
        )


@pytest.mark.parametrize("provider_account", ("default", "primary"))
@pytest.mark.parametrize(
    "provider_attempt_namespace", ("claim-ontology-v2", "claim-ontology-v4")
)
def test_unitization_reconstruction_recovers_latest_journal_response_without_provider(
    tmp_path: Path,
    monkeypatch: Any,
    provider_account: str,
    provider_attempt_namespace: str,
) -> None:
    markdown_root = tmp_path / "markdown"
    parser_records: list[JsonRecord] = []
    for document_id, text in (
        ("complaint", "Count I alleges a Section 10(b) claim."),
        ("mtd", "Defendant moves to dismiss Count I."),
    ):
        path = markdown_root / "cand-1" / f"{document_id}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        parser_records.append(
            {
                "candidate_id": "cand-1",
                "source_document_id": document_id,
                "status": "succeeded",
                "markdown_path": f"cand-1/{document_id}.md",
            }
        )
    seed: JsonRecord = {
        "count": "Count I",
        "claim_name": 'Section "10(b)" claim',
        "defendant_names": ["Issuer"],
        "challenged_by_motion": True,
        "unit_confidence": 0.95,
        "grouping": "individual",
    }
    if provider_attempt_namespace == "claim-ontology-v4":
        seed.update(
            {
                "source_citations": [
                    {
                        "source_document_id": "complaint",
                        "start_line": 1,
                        "end_line": 1,
                    },
                    {
                        "source_document_id": "mtd",
                        "start_line": 1,
                        "end_line": 1,
                    },
                ],
                "scope": {"kind": "entire_claim"},
            }
        )
    else:
        seed.update(
            {
                "source_document_ids": ["complaint", "mtd"],
                "challenge_scope": "entire_claim",
                "grouping_rationale": None,
                "separable_subclaim": None,
                "uncertainty_notes": None,
            }
        )
    response = SolverResponse(
        raw_output=json.dumps({"unit_seeds": [seed]}),
        input_tokens=12,
        output_tokens=7,
        estimated_cost=0.03,
    )
    provider_calls = 0

    def malformed_completion(*args: Any, **kwargs: Any) -> SolverResponse:
        del args
        handler = kwargs["attempt_handler"]

        def provider_call() -> JsonRecord:
            nonlocal provider_calls
            provider_calls += 1
            return {"fixture": "provider-response"}

        handler.run_attempt(1, provider_call)
        handler.settle_attempt(
            1,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            actual_cost_usd=response.estimated_cost,
            raw_output=response.raw_output,
        )
        return response

    monkeypatch.setattr(llm_pipeline, "complete_live_prompt", malformed_completion)
    response_parser = cast(Any, llm_pipeline)._json_object_from_response

    def legacy_strict_parser(*args: Any, **kwargs: Any) -> JsonRecord:
        del args, kwargs
        raise llm_pipeline.LlmPipelineError("LLM response JSON object was invalid")

    monkeypatch.setattr(
        llm_pipeline, "_json_object_from_response", legacy_strict_parser
    )
    journal_path = tmp_path / "provider-attempts.sqlite3"
    registry_entry = llm_pipeline.ModelRegistryEntry.from_record(_registry_record())

    with pytest.raises(llm_pipeline.LlmPipelineError, match="JSON object was invalid"):
        llm_pipeline.llm_unitize_cases(
            selection_records=(_selection(),),
            parser_records=parser_records,
            markdown_root=markdown_root,
            registry_entry=registry_entry,
            model_registry_sha256="b" * 64,
            provider_journal_path=journal_path,
            provider_cycle_cap_usd=100.0,
            provider_cycle_id="cycle-1",
            provider_cycle_caps_sha256="sha256:" + "c" * 64,
            provider_accounts={"openai": provider_account},
            provider_attempt_namespace=provider_attempt_namespace,
        )

    monkeypatch.setattr(llm_pipeline, "_json_object_from_response", response_parser)
    # A normal resume, rather than the explicit recovery command, must replay
    # and settle the stored response without reaching this completion's provider
    # callback.
    llm_pipeline.llm_unitize_cases(
        selection_records=(_selection(),),
        parser_records=parser_records,
        markdown_root=markdown_root,
        registry_entry=registry_entry,
        model_registry_sha256="b" * 64,
        provider_journal_path=journal_path,
        provider_cycle_cap_usd=100.0,
        provider_cycle_id="cycle-1",
        provider_cycle_caps_sha256="sha256:" + "c" * 64,
        provider_accounts={"openai": provider_account},
        provider_attempt_namespace=provider_attempt_namespace,
    )
    recovery = llm_pipeline.recover_llm_unitization_reconstruction(
        selection_record=_selection(),
        parser_records=parser_records,
        markdown_root=markdown_root,
        markdown_bytes=None,
        registry_entry=registry_entry,
        model_registry_sha256="b" * 64,
        provider_journal_path=journal_path,
        provider_cycle_cap_usd=100.0,
        provider_cycle_id="cycle-1",
        provider_cycle_caps_sha256="sha256:" + "c" * 64,
        provider_account=provider_account,
        provider_attempt_namespace=provider_attempt_namespace,
    )
    replayed_recovery = llm_pipeline.recover_llm_unitization_reconstruction(
        selection_record=_selection(),
        parser_records=parser_records,
        markdown_root=markdown_root,
        markdown_bytes=None,
        registry_entry=registry_entry,
        model_registry_sha256="b" * 64,
        provider_journal_path=journal_path,
        provider_cycle_cap_usd=100.0,
        provider_cycle_id="cycle-1",
        provider_cycle_caps_sha256="sha256:" + "c" * 64,
        provider_account=provider_account,
        provider_attempt_namespace=provider_attempt_namespace,
    )

    assert provider_calls == 1
    assert replayed_recovery == recovery
    assert recovery.attempt_ordinal == 1
    assert len(recovery.prediction_units) == 1
    assert recovery.prediction_units[0]["claim_name"] == 'Section "10(b)" claim'
    assert recovery.review_items == ()
    with sqlite3.connect(journal_path) as connection:
        assert connection.execute(
            "SELECT status FROM provider_attempts WHERE attempt_ordinal = 1"
        ).fetchone() == ("settled",)
    before_authority_binding = cast(Any, cli)._canonical_json_sha256(
        cast(Any, cli)._stage_a_provider_attempt_rows(journal_path)
    )
    with sqlite3.connect(journal_path) as connection:
        connection.execute(
            "UPDATE provider_attempts SET authority_attempt_ordinal = 7 "
            "WHERE attempt_ordinal = 1"
        )
    after_authority_binding = cast(Any, cli)._canonical_json_sha256(
        cast(Any, cli)._stage_a_provider_attempt_rows(journal_path)
    )
    assert before_authority_binding != after_authority_binding


def test_v5_unitization_resume_replays_settled_retry_after_prior_failure(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """A settled retry wins over a preceding failed response during resume."""

    markdown_root = tmp_path / "markdown"
    parser_records: list[JsonRecord] = []
    for document_id, text in (
        ("complaint", "Count I alleges a Section 10(b) claim."),
        ("mtd", "Defendant moves to dismiss Count I."),
    ):
        path = markdown_root / "cand-1" / f"{document_id}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        parser_records.append(
            {
                "candidate_id": "cand-1",
                "source_document_id": document_id,
                "status": "succeeded",
                "markdown_path": f"cand-1/{document_id}.md",
            }
        )

    def response(*, defendant_names: list[str]) -> SolverResponse:
        return SolverResponse(
            raw_output=json.dumps(
                {
                    "unit_seeds": [
                        {
                            "count": "Count I",
                            "claim_name": "Section 10(b)",
                            "defendant_names": defendant_names,
                            "challenged_by_motion": True,
                            "unit_confidence": 0.95,
                            "grouping": "individual",
                            "grouping_rationale": None,
                            "scope": {"kind": "entire_claim"},
                            "source_citations": [
                                {
                                    "source_document_id": "complaint",
                                    "start_line": 1,
                                    "line_count": 1,
                                },
                                {
                                    "source_document_id": "mtd",
                                    "start_line": 1,
                                    "line_count": 1,
                                },
                            ],
                        }
                    ]
                }
            ),
            input_tokens=12,
            output_tokens=7,
            estimated_cost=0.03,
        )

    responses = iter(
        (
            response(defendant_names=["Issuer", "Other"]),
            response(defendant_names=["Issuer"]),
        )
    )
    provider_calls = 0
    replay_response = response(defendant_names=["Issuer"])

    def completion(*args: Any, **kwargs: Any) -> SolverResponse:
        del args
        handler = kwargs["attempt_handler"]
        live_response: SolverResponse | None = None

        def provider_call() -> JsonRecord:
            nonlocal provider_calls, live_response
            provider_calls += 1
            live_response = next(responses)
            return {"fixture": "provider-response"}

        handler.run_attempt(1, provider_call)
        completed_response = live_response or replay_response
        handler.settle_attempt(
            handler.durable_attempt_ordinal(1),
            input_tokens=completed_response.input_tokens,
            output_tokens=completed_response.output_tokens,
            actual_cost_usd=completed_response.estimated_cost,
            raw_output=completed_response.raw_output,
        )
        return completed_response

    monkeypatch.setattr(llm_pipeline, "complete_live_prompt", completion)
    journal_path = tmp_path / "provider-attempts.sqlite3"
    registry_entry = llm_pipeline.ModelRegistryEntry.from_record(_registry_record())
    kwargs = {
        "selection_records": (_selection(),),
        "parser_records": parser_records,
        "markdown_root": markdown_root,
        "registry_entry": registry_entry,
        "model_registry_sha256": "b" * 64,
        "provider_journal_path": journal_path,
        "provider_cycle_cap_usd": 100.0,
        "provider_cycle_id": "cycle-1",
        "provider_cycle_caps_sha256": "sha256:" + "c" * 64,
        "provider_attempt_namespace": "claim-ontology-v5",
        "continue_on_error": True,
    }

    first = llm_pipeline.llm_unitize_cases(**kwargs)
    assert first.records == ()
    assert first.audit_records[0]["status"] == "failed"
    second = llm_pipeline.llm_unitize_cases(**kwargs)
    assert second.audit_records[0]["status"] == "succeeded"
    assert provider_calls == 2

    resumed = llm_pipeline.llm_unitize_cases(**kwargs)

    assert resumed.audit_records[0]["status"] == "succeeded"
    assert len(resumed.records[0]["prediction_units"]) == 1
    assert provider_calls == 2
    with sqlite3.connect(journal_path) as connection:
        assert connection.execute(
            "SELECT attempt_ordinal, status FROM provider_attempts "
            "ORDER BY attempt_ordinal"
        ).fetchall() == [
            (1, "reconstruction_failed"),
            (2, "settled"),
        ]


def test_malformed_label_response_retries_fresh_bounded_attempts(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    response = SolverResponse(
        raw_output='{"unit_findings":"not-a-list","missing_unit_flags":[]}',
        input_tokens=10,
        output_tokens=5,
        estimated_cost=0.01,
    )
    provider_calls = 0

    def malformed_completion(*args: Any, **kwargs: Any) -> SolverResponse:
        del args
        handler = kwargs["attempt_handler"]

        def provider_call() -> JsonRecord:
            nonlocal provider_calls
            provider_calls += 1
            return {"fixture": "provider-response"}

        handler.run_attempt(1, provider_call)
        handler.settle_attempt(
            1,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            actual_cost_usd=response.estimated_cost,
            raw_output=response.raw_output,
        )
        return response

    monkeypatch.setattr(llm_pipeline, "complete_live_prompt", malformed_completion)
    registry_entry = llm_pipeline.ModelRegistryEntry.from_record(_registry_record())
    unit_record = cast(list[JsonRecord], _prediction_units()["prediction_units"])[0]
    journal_path = tmp_path / "provider-attempts.sqlite3"

    def invoke() -> None:
        cast(Any, llm_pipeline)._llm_label_one_model(
            selection=_selection(),
            decision_text=llm_pipeline.StageBDecisionText(
                document_id="decision",
                entered_date="2026-07-01",
                text="The motion to dismiss Count I is granted without leave to amend.",
            ),
            decision_text_commitment={"decision_texts_sha256": "sha256:" + "a" * 64},
            frozen_units=(cast(Any, llm_pipeline)._prediction_unit(unit_record),),
            prompt="frozen label prompt",
            registry_entry=registry_entry,
            model_registry_sha256="b" * 64,
            transport=None,
            environ=None,
            timeout_seconds=1.0,
            provider_journal_path=journal_path,
            provider_cycle_cap_usd=100.0,
            provider_cycle_id="cycle-1",
            provider_cycle_caps_sha256="sha256:" + "c" * 64,
            provider_spend_authorities=None,
            provider_accounts=None,
        )

    messages = []
    for _ in range(3):
        with pytest.raises(llm_pipeline.LlmResponseValidationError) as exc_info:
            invoke()
        messages.append(str(exc_info.value))

    assert messages == [
        "unit_findings must be a list",
        "unit_findings must be a list",
        "unit_findings must be a list",
    ]
    with pytest.raises(
        ProviderJournalError,
        match="provider reconstruction retry attempt limit is exhausted",
    ):
        invoke()
    assert provider_calls == 3

    with sqlite3.connect(journal_path) as connection:
        rows = connection.execute(
            "SELECT attempt_ordinal, status, actual_cost_usd, failure_type "
            "FROM provider_attempts ORDER BY attempt_ordinal"
        ).fetchall()
    assert rows == [
        (1, "reconstruction_failed", pytest.approx(0.01), "LlmPipelineError"),
        (2, "reconstruction_failed", pytest.approx(0.01), "LlmPipelineError"),
        (3, "reconstruction_failed", pytest.approx(0.01), "LlmPipelineError"),
    ]


@pytest.mark.parametrize("missing_unit", [False, True])
def test_stage_b_resume_recovers_stored_response_before_provider_call(
    tmp_path: Path,
    monkeypatch: Any,
    *,
    missing_unit: bool,
) -> None:
    """A corrected Stage B reconstructor settles the old response locally."""

    decision_text = (
        "The motion to dismiss Count I is granted without leave to amend. "
        "The court also dismisses Count II."
    )
    response = SolverResponse(
        raw_output=json.dumps(
            {
                "unit_findings": [
                    {
                        "unit_id": "unit-1",
                        "resolution": "fully_dismissed",
                        "amendment_signal": "express_denial_of_leave",
                        "supporting_excerpt": (
                            "The motion to dismiss Count I is granted without leave "
                            "to amend."
                        ),
                        "labeler_confidence": 0.95,
                    }
                ],
                "missing_unit_flags": (
                    [
                        {
                            "missing_unit_description": (
                                "Decision resolved Count II, which was absent from "
                                "frozen Stage A units."
                            ),
                            "supporting_excerpt": "The court also dismisses Count II.",
                        }
                    ]
                    if missing_unit
                    else []
                ),
            }
        ),
        input_tokens=10,
        output_tokens=5,
        estimated_cost=0.01,
    )
    provider_calls = 0
    completion_calls = 0

    def completion(*args: Any, **kwargs: Any) -> SolverResponse:
        nonlocal completion_calls
        del args
        completion_calls += 1
        handler = kwargs["attempt_handler"]

        def provider_call() -> JsonRecord:
            nonlocal provider_calls
            provider_calls += 1
            return {"fixture": "provider-response"}

        handler.run_attempt(1, provider_call)
        handler.settle_attempt(
            1,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            actual_cost_usd=response.estimated_cost,
            raw_output=response.raw_output,
        )
        return response

    monkeypatch.setattr(llm_pipeline, "complete_live_prompt", completion)
    journal_path = tmp_path / "provider-attempts.sqlite3"
    registry_entry = llm_pipeline.ModelRegistryEntry.from_record(_registry_record())
    unit = cast(Any, llm_pipeline)._prediction_unit(
        cast(list[JsonRecord], _prediction_units()["prediction_units"])[0]
    )
    kwargs = {
        "selection": _selection(),
        "decision_text": llm_pipeline.StageBDecisionText(
            document_id="decision",
            entered_date="2026-07-01",
            text=decision_text,
        ),
        "decision_text_commitment": {"decision_texts_sha256": "sha256:" + "a" * 64},
        "frozen_units": (unit,),
        "prompt": "frozen label prompt",
        "registry_entry": registry_entry,
        "model_registry_sha256": "b" * 64,
        "transport": None,
        "environ": None,
        "timeout_seconds": 1.0,
        "provider_journal_path": journal_path,
        "provider_cycle_cap_usd": 100.0,
        "provider_cycle_id": "cycle-1",
        "provider_cycle_caps_sha256": "sha256:" + "c" * 64,
        "provider_spend_authorities": None,
        "provider_accounts": None,
    }
    original_labeler = llm_pipeline.label_stage_b_outcomes
    monkeypatch.setattr(
        llm_pipeline,
        "label_stage_b_outcomes",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            llm_pipeline.LlmPipelineError("legacy reconstruction rejection")
        ),
    )
    with pytest.raises(llm_pipeline.LlmResponseValidationError):
        cast(Any, llm_pipeline)._llm_label_one_model(**kwargs)
    monkeypatch.setattr(llm_pipeline, "label_stage_b_outcomes", original_labeler)

    if missing_unit:
        with sqlite3.connect(journal_path) as connection:
            before = connection.execute(
                "SELECT raw_response_json, normalized_response_json, "
                "actual_cost_usd FROM provider_attempts"
            ).fetchone()
            connection.execute(
                "UPDATE provider_attempts SET status = 'validated_response', "
                "failure_type = NULL, failure_message = NULL, completed_at = NULL"
            )
        kwargs["replay_only"] = True
        with pytest.raises(llm_pipeline.FrozenUnitWorkflowRequiredError):
            cast(Any, llm_pipeline)._llm_label_one_model(**kwargs)
        with sqlite3.connect(journal_path) as connection:
            after = connection.execute(
                "SELECT raw_response_json, normalized_response_json, "
                "actual_cost_usd FROM provider_attempts"
            ).fetchone()
        assert after == before
    else:
        labels, *_ = cast(Any, llm_pipeline)._llm_label_one_model(**kwargs)
        assert labels[0].unit_id == "unit-1"

    assert provider_calls == 1
    assert completion_calls == 2
    with sqlite3.connect(journal_path) as connection:
        assert connection.execute(
            "SELECT attempt_ordinal, status FROM provider_attempts"
        ).fetchall() == [(1, "validated_response" if missing_unit else "settled")]


def test_malformed_structural_review_retries_fresh_bounded_attempts(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    markdown_root = tmp_path / "markdown"
    for document_id, text in (
        ("complaint", "Count I alleges a Section 10(b) claim."),
        ("mtd", "Defendant moves to dismiss Count I."),
    ):
        path = markdown_root / "cand-1" / f"{document_id}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    response = SolverResponse(
        raw_output='{"structural_flags":"not-a-list"}',
        input_tokens=11,
        output_tokens=6,
        estimated_cost=0.02,
    )

    provider_calls = 0

    def malformed_completion(*args: Any, **kwargs: Any) -> SolverResponse:
        del args
        handler = kwargs["attempt_handler"]

        def provider_call() -> JsonRecord:
            nonlocal provider_calls
            provider_calls += 1
            return {"fixture": "provider-response"}

        handler.run_attempt(1, provider_call)
        handler.settle_attempt(
            1,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            actual_cost_usd=response.estimated_cost,
            raw_output=response.raw_output,
        )
        return response

    monkeypatch.setattr(llm_pipeline, "complete_live_prompt", malformed_completion)
    journal_path = tmp_path / "provider-attempts.sqlite3"

    def invoke() -> None:
        llm_pipeline.llm_review_stage_a_units(
            selection_records=(_selection(),),
            parser_records=(
                {
                    "candidate_id": "cand-1",
                    "source_document_id": "complaint",
                    "status": "succeeded",
                    "markdown_path": "cand-1/complaint.md",
                },
                {
                    "candidate_id": "cand-1",
                    "source_document_id": "mtd",
                    "status": "succeeded",
                    "markdown_path": "cand-1/mtd.md",
                },
            ),
            prediction_unit_records=(_prediction_units(),),
            markdown_root=markdown_root,
            registry_entry=llm_pipeline.ModelRegistryEntry.from_record(
                _registry_record()
            ),
            model_registry_sha256="b" * 64,
            provider_journal_path=journal_path,
            provider_cycle_cap_usd=100.0,
            provider_cycle_id="cycle-1",
            provider_cycle_caps_sha256="sha256:" + "c" * 64,
            provider_attempt_namespace="claim-ontology-v2",
        )

    for _ in range(3):
        with pytest.raises(llm_pipeline.LlmPipelineError, match="must be a list"):
            invoke()
    with pytest.raises(
        ProviderJournalError,
        match="provider reconstruction retry attempt limit is exhausted",
    ):
        invoke()
    assert provider_calls == 3

    with sqlite3.connect(journal_path) as connection:
        rows = connection.execute(
            "SELECT attempt_ordinal, status, actual_cost_usd, failure_type "
            "FROM provider_attempts ORDER BY attempt_ordinal"
        ).fetchall()
    assert rows == [
        (1, "reconstruction_failed", pytest.approx(0.02), "LlmPipelineError"),
        (2, "reconstruction_failed", pytest.approx(0.02), "LlmPipelineError"),
        (3, "reconstruction_failed", pytest.approx(0.02), "LlmPipelineError"),
    ]


def test_structural_review_recovery_reuses_failed_response_without_provider(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    markdown_root = tmp_path / "markdown"
    parser_records: list[JsonRecord] = []
    for document_id, text in (
        ("complaint", "Count I alleges a Section 10(b) claim."),
        (
            "mtd",
            "Plaintiff\u2019s state law claims against Gage in his individual capacity "
            "are barred.",
        ),
    ):
        path = markdown_root / "cand-1" / f"{document_id}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        parser_records.append(
            {
                "candidate_id": "cand-1",
                "source_document_id": document_id,
                "status": "succeeded",
                "markdown_path": f"cand-1/{document_id}.md",
            }
        )
    response = SolverResponse(
        raw_output=json.dumps(
            {
                "structural_flags": [
                    {
                        "flag_type": "omitted",
                        "affected_unit_ids": ["unit-1"],
                        "source_document_ids": ["mtd"],
                        "explanation": "A separately challenged theory is absent.",
                        "citation_excerpt": (
                            "Plaintiff's state law claims against Gage in his "
                            "individual capacity are barred."
                        ),
                    }
                ]
            }
        ),
        input_tokens=11,
        output_tokens=6,
        estimated_cost=0.02,
    )
    provider_calls = 0

    def completion(*args: Any, **kwargs: Any) -> SolverResponse:
        del args
        handler = kwargs["attempt_handler"]

        def provider_call() -> JsonRecord:
            nonlocal provider_calls
            provider_calls += 1
            return {"fixture": "provider-response"}

        handler.run_attempt(1, provider_call)
        handler.settle_attempt(
            1,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            actual_cost_usd=response.estimated_cost,
            raw_output=response.raw_output,
        )
        return response

    monkeypatch.setattr(llm_pipeline, "complete_live_prompt", completion)
    original_citation_matcher = llm_pipeline._coerced_structural_citation_excerpt
    monkeypatch.setattr(
        llm_pipeline,
        "_coerced_structural_citation_excerpt",
        lambda *args: (_ for _ in ()).throw(
            llm_pipeline.LlmPipelineError("legacy citation rejection")
        ),
    )
    journal_path = tmp_path / "provider-attempts.sqlite3"
    registry_entry = llm_pipeline.ModelRegistryEntry.from_record(_registry_record())
    with pytest.raises(
        llm_pipeline.LlmResponseValidationError, match="does not appear"
    ):
        llm_pipeline.llm_review_stage_a_units(
            selection_records=(_selection(),),
            parser_records=parser_records,
            prediction_unit_records=(_prediction_units(),),
            markdown_root=markdown_root,
            registry_entry=registry_entry,
            model_registry_sha256="b" * 64,
            provider_journal_path=journal_path,
            provider_cycle_cap_usd=100.0,
            provider_cycle_id="cycle-1",
            provider_cycle_caps_sha256="sha256:" + "c" * 64,
            provider_attempt_namespace="claim-ontology-v2",
        )
    monkeypatch.setattr(
        llm_pipeline, "_coerced_structural_citation_excerpt", original_citation_matcher
    )

    def replay_completion(*args: Any, **kwargs: Any) -> SolverResponse:
        del args
        handler = kwargs["attempt_handler"]

        def forbidden_provider_call() -> JsonRecord:
            nonlocal provider_calls
            provider_calls += 1
            return {"fixture": "unexpected-provider-response"}

        handler.run_attempt(1, forbidden_provider_call)
        handler.settle_attempt(
            1,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            actual_cost_usd=response.estimated_cost,
            raw_output=response.raw_output,
        )
        return response

    monkeypatch.setattr(llm_pipeline, "complete_live_prompt", replay_completion)
    llm_pipeline.llm_review_stage_a_units(
        selection_records=(_selection(),),
        parser_records=iter(parser_records),
        prediction_unit_records=(_prediction_units(),),
        markdown_root=markdown_root,
        registry_entry=registry_entry,
        model_registry_sha256="b" * 64,
        provider_journal_path=journal_path,
        provider_cycle_cap_usd=100.0,
        provider_cycle_id="cycle-1",
        provider_cycle_caps_sha256="sha256:" + "c" * 64,
        provider_attempt_namespace="claim-ontology-v2",
    )

    # Resume itself must settle the corrected local reconstruction before the
    # completion wrapper reaches its provider callback.
    recovery = llm_pipeline.recover_llm_stage_a_structural_review_reconstruction(
        selection_record=_selection(),
        parser_records=parser_records,
        prediction_unit_records=(_prediction_units(),),
        markdown_root=markdown_root,
        markdown_bytes=None,
        registry_entry=registry_entry,
        model_registry_sha256="b" * 64,
        provider_journal_path=journal_path,
        provider_cycle_cap_usd=100.0,
        provider_cycle_id="cycle-1",
        provider_cycle_caps_sha256="sha256:" + "c" * 64,
        provider_account="default",
        provider_attempt_namespace="claim-ontology-v2",
    )
    journal_bytes_after_recovery = journal_path.read_bytes()
    replayed_recovery = (
        llm_pipeline.recover_llm_stage_a_structural_review_reconstruction(
            selection_record=_selection(),
            parser_records=parser_records,
            prediction_unit_records=(_prediction_units(),),
            markdown_root=markdown_root,
            markdown_bytes=None,
            registry_entry=registry_entry,
            model_registry_sha256="b" * 64,
            provider_journal_path=journal_path,
            provider_cycle_cap_usd=100.0,
            provider_cycle_id="cycle-1",
            provider_cycle_caps_sha256="sha256:" + "c" * 64,
            provider_account="default",
            provider_attempt_namespace="claim-ontology-v2",
        )
    )

    assert provider_calls == 1
    assert replayed_recovery == recovery
    assert journal_path.read_bytes() == journal_bytes_after_recovery
    assert recovery.structural_flags[0]["citation_excerpt"] == (
        "Plaintiff\u2019s state law claims against Gage in his individual capacity "
        "are barred."
    )
    with sqlite3.connect(journal_path) as connection:
        assert connection.execute(
            "SELECT status, actual_cost_usd FROM provider_attempts "
            "WHERE attempt_ordinal = 1"
        ).fetchone() == ("settled", pytest.approx(0.02))


def test_structural_review_recovery_rejects_missing_stage_a_units(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    registry_entry = llm_pipeline.ModelRegistryEntry.from_record(_registry_record())
    monkeypatch.setattr(llm_pipeline, "_predecision_documents", lambda *a, **k: ())
    with pytest.raises(llm_pipeline.LlmPipelineError, match="no Stage A units"):
        llm_pipeline.recover_llm_stage_a_structural_review_reconstruction(
            selection_record=_selection(),
            parser_records=(),
            prediction_unit_records=({**_prediction_units(), "prediction_units": []},),
            markdown_root=tmp_path / "markdown",
            markdown_bytes=None,
            registry_entry=registry_entry,
            model_registry_sha256="b" * 64,
            provider_journal_path=tmp_path / "provider-attempts.sqlite3",
            provider_cycle_cap_usd=100.0,
            provider_cycle_id="cycle-1",
            provider_cycle_caps_sha256="sha256:" + "c" * 64,
            provider_account="default",
            provider_attempt_namespace="claim-ontology-v2",
        )
    assert not (tmp_path / "provider-attempts.sqlite3").exists()


def test_structural_review_recovery_requires_a_journal(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    registry_entry = llm_pipeline.ModelRegistryEntry.from_record(_registry_record())
    monkeypatch.setattr(llm_pipeline, "_predecision_documents", lambda *a, **k: ())
    monkeypatch.setattr(
        llm_pipeline, "_stage_a_structural_review_prompt", lambda *a, **k: "prompt"
    )
    monkeypatch.setattr(
        llm_pipeline, "_provider_attempt_journal", lambda **kwargs: None
    )
    with pytest.raises(llm_pipeline.LlmPipelineError, match="requires a journal"):
        llm_pipeline.recover_llm_stage_a_structural_review_reconstruction(
            selection_record=_selection(),
            parser_records=(),
            prediction_unit_records=(_prediction_units(),),
            markdown_root=tmp_path / "markdown",
            markdown_bytes=None,
            registry_entry=registry_entry,
            model_registry_sha256="b" * 64,
            provider_journal_path=tmp_path / "provider-attempts.sqlite3",
            provider_cycle_cap_usd=100.0,
            provider_cycle_id="cycle-1",
            provider_cycle_caps_sha256="sha256:" + "c" * 64,
            provider_account="default",
            provider_attempt_namespace="claim-ontology-v2",
        )


def test_structural_review_recovery_rejects_absent_failed_reconstruction(
    tmp_path: Path,
) -> None:
    markdown_root, journal_path, parser_records, registry_entry = (
        _seed_failed_structural_review_journal(tmp_path, record_failure=False)
    )
    with pytest.raises(
        ProviderJournalError,
        match="no failed reconstruction to recover",
    ):
        llm_pipeline.recover_llm_stage_a_structural_review_reconstruction(
            **_structural_review_recovery_kwargs(
                markdown_root=markdown_root,
                journal_path=journal_path,
                parser_records=parser_records,
                registry_entry=registry_entry,
            )
        )
    with sqlite3.connect(journal_path) as connection:
        assert connection.execute(
            "SELECT status FROM provider_attempts WHERE attempt_ordinal = 1"
        ).fetchone() == ("validated_response",)


@pytest.mark.parametrize(
    ("normalized_response_json", "match"),
    (
        ("not-json", "journaled normalized provider response is invalid"),
        ("[1]", "journaled normalized provider response must be an object"),
        (
            '{"input_tokens": 1}',
            "journaled normalized provider response lacks raw_output",
        ),
        (
            '{"raw_output": 12}',
            "journaled normalized provider response lacks raw_output",
        ),
    ),
)
def test_structural_review_recovery_rejects_invalid_journaled_normalized_response(
    tmp_path: Path,
    normalized_response_json: str,
    match: str,
) -> None:
    markdown_root, journal_path, parser_records, registry_entry = (
        _seed_failed_structural_review_journal(tmp_path)
    )
    with sqlite3.connect(journal_path) as connection:
        connection.execute(
            "UPDATE provider_attempts SET normalized_response_json = ? "
            "WHERE attempt_ordinal = 1",
            (normalized_response_json,),
        )
        connection.commit()
    with pytest.raises(llm_pipeline.LlmPipelineError, match=match):
        llm_pipeline.recover_llm_stage_a_structural_review_reconstruction(
            **_structural_review_recovery_kwargs(
                markdown_root=markdown_root,
                journal_path=journal_path,
                parser_records=parser_records,
                registry_entry=registry_entry,
            )
        )
    with sqlite3.connect(journal_path) as connection:
        assert connection.execute(
            "SELECT status, actual_cost_usd FROM provider_attempts "
            "WHERE attempt_ordinal = 1"
        ).fetchone() == ("reconstruction_failed", pytest.approx(0.01))


def test_structural_review_recovery_rejects_non_json_raw_output(tmp_path: Path) -> None:
    markdown_root, journal_path, parser_records, registry_entry = (
        _seed_failed_structural_review_journal(tmp_path, raw_output="not a json object")
    )
    with pytest.raises(
        llm_pipeline.LlmPipelineError,
        match="LLM response did not contain a JSON object",
    ):
        llm_pipeline.recover_llm_stage_a_structural_review_reconstruction(
            **_structural_review_recovery_kwargs(
                markdown_root=markdown_root,
                journal_path=journal_path,
                parser_records=parser_records,
                registry_entry=registry_entry,
            )
        )
    with sqlite3.connect(journal_path) as connection:
        assert connection.execute(
            "SELECT status FROM provider_attempts WHERE attempt_ordinal = 1"
        ).fetchone() == ("reconstruction_failed",)


def test_structural_review_recovery_rejects_still_invalid_structural_flags(
    tmp_path: Path,
) -> None:
    raw_output = json.dumps(
        {
            "structural_flags": [
                {
                    "flag_type": "omitted",
                    "affected_unit_ids": ["unit-1"],
                    "source_document_ids": ["mtd"],
                    "explanation": "A separately challenged theory is absent.",
                    "citation_excerpt": "this excerpt is not in any cited document",
                }
            ]
        }
    )
    markdown_root, journal_path, parser_records, registry_entry = (
        _seed_failed_structural_review_journal(tmp_path, raw_output=raw_output)
    )
    with pytest.raises(
        llm_pipeline.LlmResponseValidationError, match="does not appear"
    ):
        llm_pipeline.recover_llm_stage_a_structural_review_reconstruction(
            **_structural_review_recovery_kwargs(
                markdown_root=markdown_root,
                journal_path=journal_path,
                parser_records=parser_records,
                registry_entry=registry_entry,
            )
        )
    with sqlite3.connect(journal_path) as connection:
        assert connection.execute(
            "SELECT status, actual_cost_usd FROM provider_attempts "
            "WHERE attempt_ordinal = 1"
        ).fetchone() == ("reconstruction_failed", pytest.approx(0.01))


def test_structural_review_terminal_escalation_routes_every_frozen_unit_without_call(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Two identical invalid reviewer responses route John, never a flag."""

    markdown_root = tmp_path / "markdown"
    parser_records: list[JsonRecord] = []
    for document_id, text in (
        ("complaint", "Count I alleges a Section 10(b) claim."),
        ("mtd", "Defendant moves to dismiss Count I."),
    ):
        path = markdown_root / "cand-1" / f"{document_id}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        parser_records.append(
            {
                "candidate_id": "cand-1",
                "source_document_id": document_id,
                "status": "succeeded",
                "markdown_path": f"cand-1/{document_id}.md",
            }
        )
    response = SolverResponse(
        raw_output=json.dumps(
            {
                "structural_flags": [
                    {
                        "flag_type": "omitted",
                        "affected_unit_ids": ["unit-1"],
                        "source_document_ids": ["complaint"],
                        "explanation": "The response tries to flag a missing unit.",
                        "citation_excerpt": "not in the blinded source",
                    }
                ]
            }
        ),
        input_tokens=11,
        output_tokens=6,
        estimated_cost=0.02,
    )
    provider_calls = 0

    def completion(*args: Any, **kwargs: Any) -> SolverResponse:
        del args
        nonlocal provider_calls
        provider_calls += 1
        handler = kwargs["attempt_handler"]
        handler.run_attempt(1, lambda: {"fixture": "identical-invalid-response"})
        handler.settle_attempt(
            1,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            actual_cost_usd=response.estimated_cost,
            raw_output=response.raw_output,
        )
        return response

    monkeypatch.setattr(llm_pipeline, "complete_live_prompt", completion)
    journal_path = tmp_path / "provider-attempts.sqlite3"
    registry_entry = llm_pipeline.ModelRegistryEntry.from_record(_registry_record())
    for _ in range(2):
        with pytest.raises(
            llm_pipeline.LlmResponseValidationError,
            match="citation_excerpt does not appear",
        ):
            llm_pipeline.llm_review_stage_a_units(
                selection_records=(_selection(),),
                parser_records=parser_records,
                prediction_unit_records=(_prediction_units(),),
                markdown_root=markdown_root,
                registry_entry=registry_entry,
                model_registry_sha256="b" * 64,
                provider_journal_path=journal_path,
                provider_cycle_cap_usd=100.0,
                provider_cycle_id="cycle-1",
                provider_cycle_caps_sha256="sha256:" + "c" * 64,
                provider_attempt_namespace="claim-ontology-v2",
            )

    escalation = llm_pipeline.build_llm_stage_a_structural_review_terminal_escalation(
        selection_record=_selection(),
        parser_records=parser_records,
        prediction_unit_records=(_prediction_units(),),
        markdown_root=markdown_root,
        markdown_bytes=None,
        registry_entry=registry_entry,
        model_registry_sha256="b" * 64,
        provider_journal_path=journal_path,
        provider_cycle_cap_usd=100.0,
        provider_cycle_id="cycle-1",
        provider_cycle_caps_sha256="sha256:" + "c" * 64,
        provider_account="default",
        provider_attempt_namespace="claim-ontology-v2",
    )

    assert provider_calls == 2
    assert escalation.provider_attempt_namespace == "claim-ontology-v2"
    assert escalation.to_record()["provider_attempt_namespace"] == "claim-ontology-v2"
    assert [row["attempt_ordinal"] for row in escalation.failed_attempts] == [1, 2]
    assert len(escalation.frozen_units) == 1
    queue = llm_pipeline.structural_review_terminal_escalation_queue_records(escalation)
    assert len(queue) == 1
    assert queue[0]["route_reason"] == (
        "structural_reviewer_terminal_reconstruction_failure"
    )
    assert queue[0]["review_item"]["reviewer_prompt"] == escalation.prompt
    assert queue[0]["review_item"]["frozen_unit"] == escalation.frozen_units[0]
    assert "structural_flags" not in queue[0]
    monkeypatch.setattr(
        llm_pipeline,
        "complete_live_prompt",
        lambda *args, **kwargs: pytest.fail(
            "terminal escalation must not issue a third provider call"
        ),
    )
    receipt_commitment = {
        "path": str(tmp_path / "receipt.json"),
        "sha256": "d" * 64,
    }
    with pytest.raises(
        llm_pipeline.LlmPipelineError,
        match="terminal escalation does not match Stage A input",
    ):
        llm_pipeline.llm_review_stage_a_units(
            selection_records=(_selection(),),
            parser_records=parser_records,
            prediction_unit_records=(_prediction_units(),),
            markdown_root=markdown_root,
            registry_entry=registry_entry,
            model_registry_sha256="b" * 64,
            provider_journal_path=journal_path,
            provider_cycle_cap_usd=100.0,
            provider_cycle_id="cycle-1",
            provider_cycle_caps_sha256="sha256:" + "c" * 64,
            terminal_escalations={
                "cand-1": (
                    escalation,
                    receipt_commitment,
                )
            },
        )
    resumed = llm_pipeline.llm_review_stage_a_units(
        selection_records=(_selection(),),
        parser_records=parser_records,
        prediction_unit_records=(_prediction_units(),),
        markdown_root=markdown_root,
        registry_entry=registry_entry,
        model_registry_sha256="b" * 64,
        provider_journal_path=journal_path,
        provider_cycle_cap_usd=100.0,
        provider_cycle_id="cycle-1",
        provider_cycle_caps_sha256="sha256:" + "c" * 64,
        terminal_escalations={
            "cand-1": (
                escalation,
                receipt_commitment,
            )
        },
        provider_attempt_namespace="claim-ontology-v2",
    )
    assert resumed.records == ()
    assert resumed.audit_records[0]["status"] == "terminal_escalation"
    assert resumed.terminal_review_queue_records == (
        llm_pipeline.structural_review_terminal_escalation_queue_records(
            escalation,
            receipt_commitment=receipt_commitment,
        )
    )
    construction_queue = (
        {
            "schema_version": "legalforecast.unitization_review_queue.v1",
            "status": "pending_adjudication",
            "candidate_id": "cand-1",
            "case_id": "case-1",
            "unit_id": "unit-1",
            "review_id": "cand-1:unit-1:stage-a-review",
            "route_reason": "unclear_claim_or_defendant",
            "review_item": {
                "unit_id": "unit-1",
                "reason": "unclear_claim_or_defendant",
                "notes": "Construction review remains pending.",
            },
        },
    )
    merged_queue = llm_pipeline.merge_stage_a_review_queue(
        construction_queue,
        (),
        resumed.terminal_review_queue_records,
    )
    assert len(merged_queue) == 1
    assert merged_queue[0]["review_id"] == "cand-1:unit-1:stage-a-review"
    assert merged_queue[0]["route_reason"] == "unclear_claim_or_defendant"
    assert (
        merged_queue[0]["terminal_escalation"]
        == (resumed.terminal_review_queue_records[0])
    )
    finalized = apply_unitization_reviews(
        prediction_unit_records=(_prediction_units(),),
        review_records=merged_queue,
        adjudication_records=(
            {
                "schema_version": "legalforecast.unitization_adjudication.v1",
                "adjudication_id": "terminal-escalation-adjudication",
                "candidate_id": "cand-1",
                "case_id": "case-1",
                "review_ids": ["cand-1:unit-1:stage-a-review"],
                "source_unit_ids": ["unit-1"],
                "disposition": "ACCEPT",
                "finalized_units": [],
                "adjudicator_id": "john-hughes",
                "adjudication_notes": "Reviewed blinded Stage A materials.",
            },
        ),
    )
    assert finalized[0]["status"] == "finalized"
    assert finalized[0]["prediction_units"][0]["unit_id"] == "unit-1"
    with sqlite3.connect(journal_path) as connection:
        assert connection.execute(
            "SELECT attempt_ordinal, status, actual_cost_usd FROM provider_attempts "
            "ORDER BY attempt_ordinal"
        ).fetchall() == [
            (1, "reconstruction_failed", pytest.approx(0.02)),
            (2, "reconstruction_failed", pytest.approx(0.02)),
        ]


def test_structural_review_exhausted_terminal_escalation_routes_every_unit_without_call(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Three different failed reconstructions route John and forbid attempt four."""

    markdown_root = tmp_path / "markdown"
    parser_records: list[JsonRecord] = []
    for document_id, text in (
        ("complaint", "Count I alleges a Section 10(b) claim."),
        ("mtd", "Defendant moves to dismiss Count I."),
    ):
        path = markdown_root / "cand-1" / f"{document_id}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        parser_records.append(
            {
                "candidate_id": "cand-1",
                "source_document_id": document_id,
                "status": "succeeded",
                "markdown_path": f"cand-1/{document_id}.md",
            }
        )
    registry_entry = llm_pipeline.ModelRegistryEntry.from_record(_registry_record())
    journal_path = tmp_path / "provider-attempts.sqlite3"
    prompt_record = llm_pipeline.stage_a_structural_review_prompt_records(
        selection_records=(_selection(),),
        parser_records=parser_records,
        prediction_unit_records=(_prediction_units(),),
        markdown_root=markdown_root,
    )[0]
    journal = llm_pipeline._provider_attempt_journal(
        path=journal_path,
        stage="llm-review-stage-a",
        candidate_id="cand-1",
        prompt=prompt_record["prompt"],
        registry_entry=registry_entry,
        account="default",
        model_registry_sha256="b" * 64,
        cycle_cap_usd=100.0,
        cycle_id="cycle-1",
        provider_cycle_caps_sha256="sha256:" + "c" * 64,
        provider_attempt_namespace="claim-ontology-v2",
    )
    assert journal is not None
    with journal:
        for ordinal, (raw_output, error) in enumerate(
            (
                ("first-invalid", ValueError("first validator rejection")),
                ("second-invalid", TypeError("second validator rejection")),
                ("third-invalid", RuntimeError("third validator rejection")),
            ),
            start=1,
        ):
            if ordinal > 1:
                assert (
                    journal.prepare_reconstruction_retry(max_attempts=3) == 4 - ordinal
                )
            journal.run_attempt(1, lambda raw_output=raw_output: {"output": raw_output})
            journal.settle_attempt(
                journal.durable_attempt_ordinal(1),
                input_tokens=10,
                output_tokens=2,
                actual_cost_usd=0.01,
                raw_output=raw_output,
            )
            journal.record_reconstruction_failure(error)
    with sqlite3.connect(journal_path) as connection:
        before_rows = connection.execute(
            "SELECT attempt_ordinal, status, failure_type, failure_message "
            "FROM provider_attempts ORDER BY attempt_ordinal"
        ).fetchall()

    escalation = llm_pipeline.build_llm_stage_a_structural_review_terminal_escalation(
        selection_record=_selection(),
        parser_records=parser_records,
        prediction_unit_records=(_prediction_units(),),
        markdown_root=markdown_root,
        markdown_bytes=None,
        registry_entry=registry_entry,
        model_registry_sha256="b" * 64,
        provider_journal_path=journal_path,
        provider_cycle_cap_usd=100.0,
        provider_cycle_id="cycle-1",
        provider_cycle_caps_sha256="sha256:" + "c" * 64,
        provider_account="default",
        provider_attempt_namespace="claim-ontology-v2",
    )

    assert escalation.to_record()["schema_version"] == str(
        llm_pipeline.LLM_STAGE_A_STRUCTURAL_REVIEW_TERMINAL_ESCALATION_V2
    )
    assert [row["attempt_ordinal"] for row in escalation.failed_attempts] == [1, 2, 3]
    assert [row["failure_type"] for row in escalation.failed_attempts] == [
        "ValueError",
        "TypeError",
        "RuntimeError",
    ]
    assert [row["failure_message"] for row in escalation.failed_attempts] == [
        "first validator rejection",
        "second validator rejection",
        "third validator rejection",
    ]
    assert len({row["raw_response_sha256"] for row in escalation.failed_attempts}) == 3
    monkeypatch.setattr(
        llm_pipeline,
        "complete_live_prompt",
        lambda *args, **kwargs: pytest.fail(
            "exhausted terminal escalation must not issue a fourth provider call"
        ),
    )
    result = llm_pipeline.llm_review_stage_a_units(
        selection_records=(_selection(),),
        parser_records=parser_records,
        prediction_unit_records=(_prediction_units(),),
        markdown_root=markdown_root,
        registry_entry=registry_entry,
        model_registry_sha256="b" * 64,
        provider_journal_path=journal_path,
        provider_cycle_cap_usd=100.0,
        provider_cycle_id="cycle-1",
        provider_cycle_caps_sha256="sha256:" + "c" * 64,
        terminal_escalations={
            "cand-1": (
                escalation,
                {"path": str(tmp_path / "receipt.json"), "sha256": "d" * 64},
            )
        },
        provider_attempt_namespace="claim-ontology-v2",
    )

    assert result.records == ()
    assert result.audit_records[0]["status"] == "terminal_escalation"
    assert result.terminal_review_queue_records[0]["review_item"]["notes"].startswith(
        "The structural reviewer exhausted all three reconstruction attempts."
    )
    with sqlite3.connect(journal_path) as connection:
        after_rows = connection.execute(
            "SELECT attempt_ordinal, status, failure_type, failure_message "
            "FROM provider_attempts ORDER BY attempt_ordinal"
        ).fetchall()
    assert after_rows == before_rows


def test_exhausted_terminal_escalation_builder_rejects_late_v2_receipt(
    tmp_path: Path,
) -> None:
    """The builder fails closed when the first pair already qualified for v1."""

    markdown_root = tmp_path / "markdown"
    parser_records: list[JsonRecord] = []
    for document_id, text in (
        ("complaint", "Count I alleges a Section 10(b) claim."),
        ("mtd", "Defendant moves to dismiss Count I."),
    ):
        path = markdown_root / "cand-1" / f"{document_id}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        parser_records.append(
            {
                "candidate_id": "cand-1",
                "source_document_id": document_id,
                "status": "succeeded",
                "markdown_path": f"cand-1/{document_id}.md",
            }
        )
    registry_entry = llm_pipeline.ModelRegistryEntry.from_record(_registry_record())
    journal_path = tmp_path / "provider-attempts.sqlite3"
    prompt_record = llm_pipeline.stage_a_structural_review_prompt_records(
        selection_records=(_selection(),),
        parser_records=parser_records,
        prediction_unit_records=(_prediction_units(),),
        markdown_root=markdown_root,
    )[0]
    journal = llm_pipeline._provider_attempt_journal(
        path=journal_path,
        stage="llm-review-stage-a",
        candidate_id="cand-1",
        prompt=prompt_record["prompt"],
        registry_entry=registry_entry,
        account="default",
        model_registry_sha256="b" * 64,
        cycle_cap_usd=100.0,
        cycle_id="cycle-1",
        provider_cycle_caps_sha256="sha256:" + "c" * 64,
        provider_attempt_namespace="claim-ontology-v2",
    )
    assert journal is not None
    with journal:
        for ordinal in (1, 2, 3):
            if ordinal > 1:
                assert (
                    journal.prepare_reconstruction_retry(max_attempts=3) == 4 - ordinal
                )
            journal.run_attempt(1, lambda: {"output": "identical-invalid"})
            journal.settle_attempt(
                journal.durable_attempt_ordinal(1),
                input_tokens=10,
                output_tokens=2,
                actual_cost_usd=0.01,
                raw_output="identical-invalid",
            )
            journal.record_reconstruction_failure(ValueError("same rejection"))

    with pytest.raises(
        ProviderJournalError,
        match="third attempt after the early two-identical route qualified",
    ):
        llm_pipeline.build_llm_stage_a_structural_review_terminal_escalation(
            selection_record=_selection(),
            parser_records=parser_records,
            prediction_unit_records=(_prediction_units(),),
            markdown_root=markdown_root,
            markdown_bytes=None,
            registry_entry=registry_entry,
            model_registry_sha256="b" * 64,
            provider_journal_path=journal_path,
            provider_cycle_cap_usd=100.0,
            provider_cycle_id="cycle-1",
            provider_cycle_caps_sha256="sha256:" + "c" * 64,
            provider_account="default",
            provider_attempt_namespace="claim-ontology-v2",
        )


def test_conflicting_unitization_scope_routes_to_blinded_review_without_retry(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    markdown_root = tmp_path / "markdown"
    parser_records: list[JsonRecord] = []
    for document_id, text in (
        ("complaint", "Count I alleges a Section 10(b) claim."),
        ("mtd", "Defendant moves to dismiss Count I."),
    ):
        path = markdown_root / "cand-1" / f"{document_id}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        parser_records.append(
            {
                "candidate_id": "cand-1",
                "source_document_id": document_id,
                "status": "succeeded",
                "markdown_path": f"cand-1/{document_id}.md",
            }
        )
    response = SolverResponse(
        raw_output=json.dumps(
            {
                "unit_seeds": [
                    {
                        "count": "Count I",
                        "claim_name": "Section 10(b)",
                        "defendant_names": ["Issuer"],
                        "source_document_ids": ["complaint", "mtd"],
                        "challenged_by_motion": True,
                        "challenge_scope": "partial_theory_only",
                        "unit_confidence": 0.95,
                        "grouping": "individual",
                        "grouping_rationale": None,
                        "separable_subclaim": "Scienter theory",
                        "uncertainty_notes": "Original model uncertainty.",
                    },
                ]
            }
        ),
        input_tokens=12,
        output_tokens=7,
        estimated_cost=0.03,
    )
    provider_calls = 0

    def invalid_completion(*args: Any, **kwargs: Any) -> SolverResponse:
        del args
        handler = kwargs["attempt_handler"]

        def provider_call() -> JsonRecord:
            nonlocal provider_calls
            provider_calls += 1
            return {"fixture": "provider-response"}

        handler.run_attempt(1, provider_call)
        handler.settle_attempt(
            1,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            actual_cost_usd=response.estimated_cost,
            raw_output=response.raw_output,
        )
        return response

    monkeypatch.setattr(llm_pipeline, "complete_live_prompt", invalid_completion)
    journal_path = tmp_path / "provider-attempts.sqlite3"

    result = llm_pipeline.llm_unitize_cases(
        selection_records=(_selection(),),
        parser_records=parser_records,
        markdown_root=markdown_root,
        registry_entry=llm_pipeline.ModelRegistryEntry.from_record(_registry_record()),
        model_registry_sha256="b" * 64,
        provider_journal_path=journal_path,
        provider_cycle_cap_usd=100.0,
        provider_cycle_id="cycle-1",
        provider_cycle_caps_sha256="sha256:" + "c" * 64,
        provider_attempt_namespace="claim-ontology-v2",
    )
    assert provider_calls == 1
    [record] = result.records
    [unit] = record["prediction_units"]
    assert unit["challenge_scope"] == "unclear"
    assert unit["should_score"] is False
    assert unit["separable_subclaim"] is None
    assert unit["uncertainty_notes"] == (
        "Original model uncertainty. Provider response supplied separable_subclaim for "
        "challenge_scope=partial_theory_only: Scienter theory"
    )
    [audit] = result.audit_records
    assert audit["status"] == "adjudication_pending"
    [review_item] = audit["unitization_review_queue"]
    assert review_item["route_reason"] == "unclear_claim_or_defendant"
    assert review_item["review_item"]["notes"] == unit["uncertainty_notes"]

    with sqlite3.connect(journal_path) as connection:
        rows = connection.execute(
            "SELECT attempt_ordinal, status, actual_cost_usd, failure_type "
            "FROM provider_attempts ORDER BY attempt_ordinal"
        ).fetchall()
    assert rows == [
        (1, "settled", pytest.approx(0.03), None),
    ]


def test_single_defendant_grouped_seed_routes_to_blinded_review_without_retry(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    markdown_root = tmp_path / "markdown"
    parser_records: list[JsonRecord] = []
    for document_id, text in (
        ("complaint", "Counts I-IV assert claims against Meta Platforms, Inc."),
        ("mtd", "Meta raises Section 230 as a threshold defense to all counts."),
    ):
        path = markdown_root / "cand-1" / f"{document_id}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        parser_records.append(
            {
                "candidate_id": "cand-1",
                "source_document_id": document_id,
                "status": "succeeded",
                "markdown_path": f"cand-1/{document_id}.md",
            }
        )
    response = SolverResponse(
        raw_output=json.dumps(
            {
                "unit_seeds": [
                    {
                        "count": "Threshold Defense I",
                        "claim_name": "All Claims — Section 230 Bar",
                        "defendant_names": ["Meta Platforms, Inc."],
                        "source_document_ids": ["complaint", "mtd"],
                        "challenged_by_motion": True,
                        "challenge_scope": "entire_claim",
                        "unit_confidence": 0.92,
                        "grouping": "grouped",
                        "grouping_rationale": (
                            "The defense applies to every count simultaneously."
                        ),
                        "group_label": "Section 230 Threshold Defense (All Counts)",
                        "separable_subclaim": None,
                        "uncertainty_notes": "Original model uncertainty.",
                    },
                    {
                        "count": "Threshold Defense II",
                        "claim_name": "All Claims — SLUSA Bar",
                        "defendant_names": ["Meta Platforms, Inc."],
                        "source_document_ids": ["complaint", "mtd"],
                        "challenged_by_motion": True,
                        "challenge_scope": "partial_theory_only",
                        "unit_confidence": 0.88,
                        "grouping": "grouped",
                        "grouping_rationale": (
                            "The alternative defense applies across all counts."
                        ),
                        "group_label": "SLUSA Threshold Defense (All Counts)",
                        "separable_subclaim": "Purchases of covered securities",
                        "uncertainty_notes": None,
                    },
                    {
                        "count": "Threshold Defense III",
                        "claim_name": "Count IV — State-Law Purchaser Theory",
                        "defendant_names": ["Meta Platforms, Inc."],
                        "source_document_ids": ["complaint", "mtd"],
                        "challenged_by_motion": True,
                        "challenge_scope": "separable_subclaim",
                        "unit_confidence": 0.86,
                        "grouping": "grouped",
                        "grouping_rationale": (
                            "The purchaser theory is pleaded against one defendant."
                        ),
                        "group_label": "Count IV Purchaser Theory",
                        "separable_subclaim": "Purchases made after the notice date",
                        "uncertainty_notes": None,
                    },
                ]
            }
        ),
        input_tokens=12,
        output_tokens=7,
        estimated_cost=0.03,
    )
    provider_calls = 0

    def invalid_completion(*args: Any, **kwargs: Any) -> SolverResponse:
        del args
        handler = kwargs["attempt_handler"]

        def provider_call() -> JsonRecord:
            nonlocal provider_calls
            provider_calls += 1
            return {"fixture": "provider-response"}

        handler.run_attempt(1, provider_call)
        handler.settle_attempt(
            1,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            actual_cost_usd=response.estimated_cost,
            raw_output=response.raw_output,
        )
        return response

    monkeypatch.setattr(llm_pipeline, "complete_live_prompt", invalid_completion)
    journal_path = tmp_path / "provider-attempts.sqlite3"

    result = llm_pipeline.llm_unitize_cases(
        selection_records=(_selection(),),
        parser_records=parser_records,
        markdown_root=markdown_root,
        registry_entry=llm_pipeline.ModelRegistryEntry.from_record(_registry_record()),
        model_registry_sha256="b" * 64,
        provider_journal_path=journal_path,
        provider_cycle_cap_usd=100.0,
        provider_cycle_id="cycle-1",
        provider_cycle_caps_sha256="sha256:" + "c" * 64,
        provider_attempt_namespace="claim-ontology-v2",
    )
    assert provider_calls == 1
    [record] = result.records
    unit, combined_conflict_unit, grouped_subclaim_unit = record["prediction_units"]
    assert unit["grouping"] == "individual"
    assert unit["defendant_group"] == "Meta Platforms, Inc."
    assert unit["grouping_rationale"] is None
    assert unit["challenge_scope"] == "unclear"
    assert unit["should_score"] is False
    assert unit["uncertainty_notes"] == (
        "Original model uncertainty. Provider response marked a single-defendant "
        "seed as grouped; defendant_names=Meta Platforms, Inc.; "
        "challenge_scope=entire_claim; "
        "group_label=Section 230 Threshold Defense (All Counts); "
        "grouping_rationale=The defense applies to every count simultaneously."
    )
    assert combined_conflict_unit["grouping"] == "individual"
    assert combined_conflict_unit["defendant_group"] == "Meta Platforms, Inc."
    assert combined_conflict_unit["grouping_rationale"] is None
    assert combined_conflict_unit["challenge_scope"] == "unclear"
    assert combined_conflict_unit["should_score"] is False
    assert combined_conflict_unit["separable_subclaim"] is None
    assert combined_conflict_unit["uncertainty_notes"] == (
        "Provider response supplied separable_subclaim for "
        "challenge_scope=partial_theory_only: Purchases of covered securities "
        "Provider response marked a single-defendant seed as grouped; "
        "defendant_names=Meta Platforms, Inc.; "
        "challenge_scope=partial_theory_only; "
        "group_label=SLUSA Threshold Defense (All Counts); "
        "grouping_rationale=The alternative defense applies across all counts."
    )
    assert grouped_subclaim_unit["grouping"] == "individual"
    assert grouped_subclaim_unit["defendant_group"] == "Meta Platforms, Inc."
    assert grouped_subclaim_unit["grouping_rationale"] is None
    assert grouped_subclaim_unit["challenge_scope"] == "unclear"
    assert grouped_subclaim_unit["should_score"] is False
    assert grouped_subclaim_unit["separable_subclaim"] is None
    assert grouped_subclaim_unit["uncertainty_notes"] == (
        "Provider response marked a single-defendant seed as grouped; "
        "defendant_names=Meta Platforms, Inc.; "
        "challenge_scope=separable_subclaim; "
        "group_label=Count IV Purchaser Theory; "
        "grouping_rationale=The purchaser theory is pleaded against one defendant.; "
        "separable_subclaim=Purchases made after the notice date"
    )
    [audit] = result.audit_records
    assert audit["status"] == "adjudication_pending"
    review_item, combined_conflict_review_item, grouped_subclaim_review_item = audit[
        "unitization_review_queue"
    ]
    assert review_item["route_reason"] == "unclear_grouping"
    assert review_item["review_item"]["notes"] == unit["uncertainty_notes"]
    assert combined_conflict_review_item["route_reason"] == (
        "unclear_claim_or_defendant"
    )
    assert (
        combined_conflict_review_item["review_item"]["notes"]
        == (combined_conflict_unit["uncertainty_notes"])
    )
    assert grouped_subclaim_review_item["route_reason"] == "unclear_grouping"
    assert (
        grouped_subclaim_review_item["review_item"]["notes"]
        == grouped_subclaim_unit["uncertainty_notes"]
    )

    with sqlite3.connect(journal_path) as connection:
        rows = connection.execute(
            "SELECT attempt_ordinal, status, actual_cost_usd, failure_type "
            "FROM provider_attempts ORDER BY attempt_ordinal"
        ).fetchall()
    assert rows == [
        (1, "settled", pytest.approx(0.03), None),
    ]


def test_paid_audit_only_decision_reaches_stage_b_but_not_model_packet(
    tmp_path: Path,
    monkeypatch: Any,
    authenticated_downstream_fixture: Any,
) -> None:
    output_root = tmp_path / "acquisition"
    document_root = output_root / "documents"
    decision_url = "https://case.dev/download/decision.pdf"
    [recovery] = recover_purchased_documents(
        (
            PurchasedDocumentRecoveryRequest(
                purchase_attempt=CaseDevPacerPurchaseAttempt(
                    candidate_id="cand-1",
                    source_document_id="decision",
                    status=CaseDevPacerPurchaseStatus.PURCHASED,
                    fee_acknowledged=True,
                    pacer_fees={
                        "pacer_fee_usd": "0.00",
                        "service_fee_usd": "3.05",
                        "total_usd": "3.05",
                    },
                    download_url=decision_url,
                ),
                source_case_id="case-1",
                court="S.D.N.Y.",
                docket_number="1:26-cv-00001",
                document_role=DocumentRole.DECISION,
                docket_entry_number=16,
                pre_purchase_evidence={"reason": "first_written_disposition"},
                is_predecision_material=False,
                contains_target_outcome=True,
            ),
        ),
        output_root=document_root,
        source=FixtureFreeDocumentSource({decision_url: b"%PDF paid decision"}),
        retrieved_at=datetime(2026, 7, 2, tzinfo=UTC),
    )
    [decision_download] = purchased_document_download_manifest_records((recovery,))
    assert decision_download["recovery_status"] == "recovered_audit_only"
    assert decision_download["parse_purpose"] == "stage_b_labeling"
    assert decision_download["model_visible"] is False
    assert decision_download["packet_membership"] == "not_mounted"

    free_downloads = [
        _free_download(document_root, "complaint", "complaint", 1),
        _free_download(
            document_root,
            "mtd",
            "motion_to_dismiss_notice",
            5,
        ),
    ]
    downloads = [*free_downloads, decision_download]
    download_manifest = tmp_path / "downloads.jsonl"
    _write_jsonl(download_manifest, downloads)
    clearance = tmp_path / "clearance.jsonl"
    _write_jsonl(
        clearance,
        [
            {
                "candidate_id": row["candidate_id"],
                "source_document_id": row["source_document_id"],
                "sha256": row["sha256"],
                "schema_version": "legalforecast.disclosure_clearance.v1",
                "byte_count": row["byte_count"],
                "status": "cleared",
                "restriction_status": "public",
                "restriction_evidence": ["fixture-public-docket"],
                "reviewer_id": "reviewer:test",
                "controlled_store_provenance": "private-store://fixture/reviews",
                "reviewed_at": "2026-07-12T18:00:00Z",
            }
            for row in downloads
        ],
    )
    parse_materialization_card = authenticated_downstream_fixture.materialize(
        manifest=download_manifest,
        clearance=clearance,
        document_root=document_root,
        name="audit-only-parse",
    )

    assert (
        main(
            [
                "acquisition",
                "plan-parse-documents",
                "--download-manifest",
                str(download_manifest),
                "--disclosure-clearance",
                str(clearance),
                "--document-root",
                str(document_root),
                "--materialization-run-card",
                str(parse_materialization_card),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )
    parse_requests = _read_jsonl(output_root / "parse-document-requests.jsonl")
    assert {record["source_document_id"] for record in parse_requests} == {
        "complaint",
        "mtd",
        "decision",
    }

    fixture_markdown = tmp_path / "fixture-markdown"
    fixture_markdown.mkdir()
    (fixture_markdown / "complaint.md").write_text(
        "Count I alleges a Section 10(b) claim.",
        encoding="utf-8",
    )
    (fixture_markdown / "mtd.md").write_text(
        "Defendant moves to dismiss Count I.",
        encoding="utf-8",
    )
    decision_text = "The motion to dismiss Count I is granted without leave to amend."
    (fixture_markdown / "decision.md").write_text(decision_text, encoding="utf-8")
    assert (
        main(
            [
                "acquisition",
                "parse-documents",
                "--requests",
                str(output_root / "parse-document-requests.jsonl"),
                "--disclosure-clearance",
                str(clearance),
                "--materialization-run-card",
                str(parse_materialization_card),
                "--output-root",
                str(output_root),
                "--fixture-markdown-dir",
                str(fixture_markdown),
                "--execute",
            ]
        )
        == 0
    )
    parser_manifest = output_root / "mistral-markdown-conversions.jsonl"
    conversions = _read_jsonl(parser_manifest)
    assert any(
        record["source_document_id"] == "decision" and record["status"] == "succeeded"
        for record in conversions
    )

    selection = _selection()
    selection_path = tmp_path / "selection.jsonl"
    units = _prediction_units()
    units_path = tmp_path / "prediction-units.jsonl"
    registry_path = tmp_path / "registry.json"
    evaluated_registry_path = tmp_path / "evaluated-registry.json"
    provider_caps_path = tmp_path / "provider-caps.json"
    _write_jsonl(selection_path, [selection])
    finalized_units = apply_unitization_reviews(
        prediction_unit_records=[units],
        review_records=(),
        adjudication_records=(),
    )
    _write_jsonl(units_path, list(finalized_units))
    registry_path.write_text(json.dumps([_registry_record()]), encoding="utf-8")
    evaluated_record = _registry_record()
    evaluated_record["model_id"] = "gpt-evaluated"
    evaluated_record["model_version_or_snapshot"] = "gpt-evaluated-2026-06-30"
    evaluated_registry_path.write_text(json.dumps([evaluated_record]), encoding="utf-8")
    provider_caps_path.write_text(
        json.dumps(
            {
                "schema_version": "legalforecast.provider_cycle_caps.v1",
                "cycle_id": "test-cycle",
                "spend_authority": {
                    "backend": "dynamodb",
                    "resource_identity_sha256": "a" * 64,
                    "ledger_scope_fields": [
                        "cycle_id",
                        "provider",
                        "account",
                    ],
                    "max_billable_attempts": 3,
                    "failure_threshold": 3,
                    "failure_window_seconds": 300,
                },
                "providers": [
                    {
                        "provider": "openai",
                        "account": "primary",
                        "cycle_reservation_cap_usd": "10.00",
                        "external_spend_limit_usd": "20.00",
                        "external_limit_scope": "test account",
                        "external_limit_source": "test fixture",
                        "verified_at": "2026-07-12T16:00:00Z",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    stage_b_args = _write_authenticated_stage_b_inputs(
        root=tmp_path / "stage-b",
        selection_path=selection_path,
        parser_manifest=parser_manifest,
        markdown_root=output_root / "markdown",
        decision_text=decision_text,
    )
    [entry] = cli.load_model_registry(registry_path).entries
    caps = cli.load_provider_cycle_caps(provider_caps_path)
    registry_sha = cli._path_sha256(registry_path).removeprefix("sha256:")
    provider_journal = output_root / "provider-attempts.sqlite3"
    ProviderAttemptJournal(
        provider_journal,
        identity=ProviderCallIdentity(
            stage="fixture-bootstrap",
            candidate_id="fixture",
            model_key=entry.registry_key,
            prompt="fixture",
            model_registry_sha256=registry_sha,
        ),
        provider=entry.provider,
        reservation_usd=0.0,
        cycle_cap_usd=caps.cap_usd(entry.provider),
        cycle_id=caps.cycle_id,
        provider_cycle_caps_sha256=cli._path_sha256(provider_caps_path),
    ).close()
    unit_card = tmp_path / "fixture-unitization-run-card.json"
    structural_card = tmp_path / "fixture-structural-review-run-card.json"
    apply_card = tmp_path / "fixture-apply-run-card.json"
    review_queue = tmp_path / "fixture-review-queue.jsonl"
    for path in (unit_card, structural_card, apply_card):
        path.write_text("{}\n", encoding="utf-8")
    _write_jsonl(review_queue, [])
    parser_records = tuple(_read_jsonl(parser_manifest))
    markdown_tree, markdown_bytes = cli._stage_a_markdown_tree_snapshot(
        parser_records, markdown_root=output_root / "markdown"
    )
    lineage = cli._StageAUnitizationLineage(
        selection_records=(selection,),
        parser_records=parser_records,
        registry_entry=entry,
        registry_sha256=registry_sha,
        provider_caps=caps,
        provider_caps_sha256=cli._path_sha256(provider_caps_path),
        provider_journal_path=provider_journal,
        document_root=document_root,
        markdown_root=output_root / "markdown",
        cohort_cycle_id=caps.cycle_id,
        input_paths=(),
        input_commitments={},
        markdown_tree=markdown_tree,
        file_snapshots={},
        document_tree=cli._materializer_tree_snapshot(document_root),
        markdown_bytes=markdown_bytes,
    )
    monkeypatch.setattr(
        cli,
        "_verify_finalized_stage_a_provider_chain",
        lambda *args, **kwargs: (lineage, unit_card, review_queue),
    )
    monkeypatch.setattr(cli, "_verify_stage_a_review_run_card", lambda *a, **k: None)
    monkeypatch.setattr(cli, "DynamoDbProviderSpendAuthority", _FakeSpendAuthority)
    monkeypatch.setattr(llm_pipeline, "complete_live_prompt", _stage_b_completion)
    assert (
        main(
            [
                "acquisition",
                "llm-label",
                "--selection",
                str(selection_path),
                "--parser-manifest",
                str(parser_manifest),
                "--prediction-units",
                str(units_path),
                *stage_b_args,
                "--model-registry",
                str(registry_path),
                "--evaluated-model-registry",
                str(evaluated_registry_path),
                "--model-key",
                "openai:gpt-test",
                "--provider-cycle-caps",
                str(provider_caps_path),
                "--llm-unitization-run-card",
                str(unit_card),
                "--llm-review-stage-a-run-card",
                str(structural_card),
                "--unitization-review-run-card",
                str(apply_card),
                "--provider-journal",
                str(provider_journal),
                "--provider-authority-table",
                "fixture-provider-authority",
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )
    [label] = _read_jsonl(output_root / "labels.jsonl")
    assert label["supporting_citations"] == [
        {
            "document_id": "decision",
            "excerpt": decision_text,
            "page": None,
            "paragraph": None,
        }
    ]

    raw_html_dir = tmp_path / "raw-html"
    raw_html_dir.mkdir()
    (raw_html_dir / "cand-1.html").write_text(_docket_html(), encoding="utf-8")
    plan = plan_packet_build_inputs(
        selection_records=(selection,),
        download_records=downloads,
        parser_records=conversions,
        prediction_unit_records=finalized_units,
        raw_html_dir=raw_html_dir,
        document_root=document_root,
        markdown_root=output_root / "markdown",
        source_dir=output_root,
        generated_at=datetime(2026, 7, 2, tzinfo=UTC),
    )
    [packet_input] = plan.packet_build_records
    decision_packet_id = "cand-1-decision"
    decision_provenance = next(
        document
        for document in packet_input["documents"]
        if document["source_document_id"] == decision_packet_id
    )
    assert decision_provenance["is_mounted_for_model"] is False
    assert decision_provenance["contains_target_outcome"] is True
    packet_input_path = output_root / "packet-build-input.jsonl"
    _write_jsonl(packet_input_path, [packet_input])
    packet_materialization_card = authenticated_downstream_fixture.materialize(
        manifest=download_manifest,
        clearance=clearance,
        document_root=document_root,
        selection=selection_path,
        name="audit-only-packet",
    )
    packet_planner_card = output_root / "run-cards/plan-packet-inputs.json"
    authenticated_downstream_fixture.write_packet_planner_card(
        packet_planner_card,
        packet_input=packet_input_path,
        selection=selection_path,
        manifest=download_manifest,
        clearance=clearance,
        document_root=document_root,
        materialization_run_card=packet_materialization_card,
    )
    assert (
        main(
            [
                "acquisition",
                "build-packets",
                "--input",
                str(packet_input_path),
                "--packet-input-run-card",
                str(packet_planner_card),
                "--selection",
                str(selection_path),
                "--download-manifest",
                str(download_manifest),
                "--parser-manifest",
                str(selection_path),
                "--parser-run-card",
                str(packet_materialization_card),
                "--parse-plan-run-card",
                str(packet_materialization_card),
                "--disclosure-clearance",
                str(clearance),
                "--raw-prediction-units",
                str(selection_path),
                "--prediction-units",
                str(selection_path),
                "--llm-unitization-audit",
                str(selection_path),
                "--llm-unitize-run-card",
                str(selection_path),
                "--llm-unitize-provider-journal",
                str(selection_path),
                "--original-unitization-review-queue",
                str(selection_path),
                "--stage-a-structural-flags",
                str(selection_path),
                "--stage-a-structural-review-audit",
                str(selection_path),
                "--stage-a-review-run-card",
                str(selection_path),
                "--stage-a-review-provider-journal",
                str(selection_path),
                "--stage-a-review-model-registry",
                str(REGISTRY),
                "--stage-a-review-model-key",
                "fixture:fixture-model",
                "--unitization-review-queue",
                str(selection_path),
                "--unitization-review-adjudications",
                str(selection_path),
                "--apply-unitization-review-run-card",
                str(selection_path),
                "--model-registry",
                str(REGISTRY),
                "--expected-model-registry-sha256",
                hashlib.sha256(REGISTRY.read_bytes()).hexdigest(),
                "--raw-html-dir",
                str(document_root),
                "--raw-artifacts-manifest",
                str(selection_path),
                "--document-root",
                str(document_root),
                "--markdown-root",
                str(document_root),
                "--materialization-run-card",
                str(packet_materialization_card),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )
    [packet] = _read_jsonl(output_root / "packets.jsonl")
    mounted_ids = {document["source_document_id"] for document in packet["documents"]}
    assert decision_packet_id not in mounted_ids
    assert decision_packet_id in packet["excluded_document_ids"]


def _free_download(
    document_root: Path,
    source_document_id: str,
    role: str,
    docket_entry_number: int,
) -> JsonRecord:
    local_path = f"cand-1/courtlistener/{source_document_id}.pdf"
    content = f"%PDF {source_document_id}".encode()
    path = document_root / local_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return {
        "candidate_id": "cand-1",
        "source_provider": "courtlistener",
        "source_document_id": source_document_id,
        "docket_entry_number": docket_entry_number,
        "document_role": role,
        "source_url": f"https://storage.courtlistener.com/{source_document_id}.pdf",
        "local_path": local_path,
        "sha256": hashlib.sha256(content).hexdigest(),
        "byte_count": len(content),
        "free_or_purchased": "free",
        "retry_count": 0,
        "rate_limited": False,
        "reused_existing": False,
    }


def _selection() -> JsonRecord:
    return {
        "candidate_id": "cand-1",
        "case_id": "case-1",
        "decision_date": "2026-07-01",
        "case_name": "Example v. Issuer",
        "court": "S.D.N.Y.",
        "docket_number": "1:26-cv-00001",
        "source_url": "https://www.courtlistener.com/docket/cand-1/",
        "target_motion_entry_numbers": [5],
        "decision_entry_numbers": [16],
        "selected": True,
        "documents": [
            _selection_document("complaint", "complaint", 1, True, False),
            _selection_document("mtd", "motion_to_dismiss_notice", 5, True, False),
            _selection_document("decision", "decision", 16, False, True),
        ],
    }


def _selection_document(
    source_document_id: str,
    role: str,
    docket_entry_number: int,
    model_visible: bool,
    contains_target_outcome: bool,
) -> JsonRecord:
    return {
        "candidate_id": "cand-1",
        "source_document_id": source_document_id,
        "docket_entry_number": docket_entry_number,
        "document_role": role,
        "description": role,
        "model_visible": model_visible,
        "contains_target_outcome": contains_target_outcome,
        "redaction_or_seal_status": "public",
        "restriction_evidence": ["fixture-public-docket"],
    }


def _prediction_units() -> JsonRecord:
    return {
        "candidate_id": "cand-1",
        "case_id": "case-1",
        "prediction_units": [
            {
                "unit_id": "unit-1",
                "count": "Count I",
                "claim_name": "Section 10(b)",
                "defendant_group": "Issuer",
                "challenged_by_motion": True,
                "challenge_scope": "entire_claim",
                "unit_confidence": 0.9,
                "source_citations": [
                    {
                        "document_id": "mtd",
                        "docket_entry_number": 5,
                        "excerpt": "Defendant moves to dismiss Count I.",
                    }
                ],
                "grouping": "individual",
                "grouping_rationale": None,
                "separable_subclaim": None,
                "uncertainty_notes": None,
            }
        ],
    }


def _stage_b_completion(*args: Any, **kwargs: Any) -> SolverResponse:
    prompt = cast(str, args[1])
    assert "Create Stage B outcome labels" in prompt
    response = SolverResponse(
        raw_output=json.dumps(
            {
                "unit_findings": [
                    {
                        "unit_id": "unit-1",
                        "resolution": "fully_dismissed",
                        "amendment_signal": "express_denial_of_leave",
                        "supporting_excerpt": (
                            "The motion to dismiss Count I is granted without leave "
                            "to amend."
                        ),
                        "labeler_confidence": 0.95,
                    }
                ],
                "missing_unit_flags": [],
            }
        ),
        input_tokens=100,
        output_tokens=50,
        estimated_cost=0.01,
        metadata={"provider": "openai", "model_id": "gpt-test"},
    )
    journal = kwargs["attempt_handler"]
    journal.run_attempt(1, lambda: {"fixture": "provider-response"})
    journal.settle_attempt(
        1,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        actual_cost_usd=response.estimated_cost,
        raw_output=response.raw_output,
    )
    return response


def _write_authenticated_stage_b_inputs(
    *,
    root: Path,
    selection_path: Path,
    parser_manifest: Path,
    markdown_root: Path,
    decision_text: str,
) -> list[str]:
    conversions = _read_jsonl(parser_manifest)
    [decision_parser] = [
        record for record in conversions if record["source_document_id"] == "decision"
    ]
    text_sha256 = hashlib.sha256(decision_text.encode()).hexdigest()
    decision_parser["parser_config"] = {
        "engine": "mistral",
        "parser_revision": EXPECTED_PARSER_REVISION,
        "expected_parser_revision": EXPECTED_PARSER_REVISION,
        "fixture_markdown": False,
    }
    decision_parser["extracted_text"] = {
        "source_document_id": "decision",
        "extraction_method": "mistral_parser_markdown",
        "text_sha256": text_sha256,
    }
    _write_jsonl(parser_manifest, conversions)
    commitments = {
        "clearance_run_card_sha256": "sha256:" + "b" * 64,
        "disclosure_clearance_sha256": "sha256:" + "c" * 64,
        "download_manifest_sha256": "sha256:" + "d" * 64,
        "parser_manifest_sha256": _sha256(parser_manifest),
        "parser_run_card_sha256": "sha256:" + "e" * 64,
        "restriction_evidence_sha256": "sha256:" + "f" * 64,
        "selection_sha256": _sha256(selection_path),
        "selection_run_card_sha256": "sha256:" + "1" * 64,
    }
    record = {
        "schema_version": "legalforecast.decision_text.v1",
        "candidate_id": "cand-1",
        "case_id": "case-1",
        "document_id": "decision",
        "entered_date": "2026-07-01",
        "text": decision_text,
        "is_first_written_disposition": True,
        "contains_target_outcome": True,
        "model_visible": False,
        "document_role": "decision",
        "docket_entry_number": 16,
        "source_sha256": decision_parser["source_sha256"],
        "source_byte_count": decision_parser["source_byte_count"],
        "text_sha256": text_sha256,
        "markdown_sha256": text_sha256,
        "extraction_method": "mistral_parser_markdown",
        "parser_revision": EXPECTED_PARSER_REVISION,
        "clearance": {
            "status": "cleared",
            "restriction_status": "public",
            "reviewer_id": "reviewer:test",
            "controlled_store_provenance": "private-store://test/decision",
            "reviewed_at": "2026-07-15T12:00:00Z",
        },
        "input_commitments": commitments,
    }
    decision_texts = root / "decision-texts.jsonl"
    manifest_path = root / "decision-texts-manifest.json"
    run_card_path = root / "build-decision-texts.json"
    _write_jsonl(decision_texts, [record])
    manifest = {
        "schema_version": "legalforecast.decision_text_manifest.v1",
        "eligibility_anchor": "2026-06-30",
        "record_count": 1,
        "candidate_ids_sha256": _canonical_sha256(["cand-1"]),
        "decision_texts_sha256": _sha256(decision_texts),
        "input_commitments": commitments,
        "outcome_material_model_visible": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
    }
    _write_json(manifest_path, manifest)
    _write_json(
        run_card_path,
        {
            "schema_version": "legalforecast.acquisition_run_card.v1",
            "stage": "build-decision-texts",
            "status": "completed",
            "execute": True,
            "dry_run": False,
            "record_count": 1,
            "eligibility_anchor": "2026-06-30",
            "decision_texts_sha256": _sha256(decision_texts),
            "decision_texts_manifest_sha256": _sha256(manifest_path),
            "input_commitments": commitments,
            "paid_activity_requested": False,
            "paid_activity_executed": False,
        },
    )
    return [
        "--decision-texts",
        str(decision_texts),
        "--decision-texts-manifest",
        str(manifest_path),
        "--decision-texts-run-card",
        str(run_card_path),
        "--markdown-root",
        str(markdown_root),
    ]


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _registry_record() -> JsonRecord:
    return {
        "provider": "openai",
        "model_id": "gpt-test",
        "display_name": "GPT Test",
        "model_version_or_snapshot": "gpt-test-2026-06-26",
        "release_timestamp": "2026-06-26T00:00:00Z",
        "release_timestamp_source": "fixture release note",
        "provider_training_cutoff_status": "known",
        "provider_training_cutoff": "2026-06-01",
        "temperature": 0,
        "top_p": 1,
        "max_output_tokens": 4096,
        "network_disabled": True,
        "search_disabled": True,
        "tool_policy": "controlled_docket_tool_only",
        "context_limit": 200000,
        "pricing_source": "fixture",
        "input_token_price": 1.0,
        "output_token_price": 2.0,
        "known_cutoff_publicity_caveats": [],
    }


def _seed_failed_structural_review_journal(
    tmp_path: Path,
    *,
    raw_output: str = "fixture-invalid",
    record_failure: bool = True,
) -> tuple[Path, Path, list[JsonRecord], llm_pipeline.ModelRegistryEntry]:
    markdown_root = tmp_path / "markdown"
    parser_records: list[JsonRecord] = []
    for document_id, text in (
        ("complaint", "Count I alleges a Section 10(b) claim."),
        ("mtd", "Defendant moves to dismiss Count I."),
    ):
        path = markdown_root / "cand-1" / f"{document_id}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        parser_records.append(
            {
                "candidate_id": "cand-1",
                "source_document_id": document_id,
                "status": "succeeded",
                "markdown_path": f"cand-1/{document_id}.md",
            }
        )
    registry_entry = llm_pipeline.ModelRegistryEntry.from_record(_registry_record())
    journal_path = tmp_path / "provider-attempts.sqlite3"
    prompt_record = llm_pipeline.stage_a_structural_review_prompt_records(
        selection_records=(_selection(),),
        parser_records=parser_records,
        prediction_unit_records=(_prediction_units(),),
        markdown_root=markdown_root,
        provider_attempt_namespace="claim-ontology-v2",
    )[0]
    journal = llm_pipeline._provider_attempt_journal(
        path=journal_path,
        stage="llm-review-stage-a",
        candidate_id="cand-1",
        prompt=prompt_record["prompt"],
        registry_entry=registry_entry,
        account="default",
        model_registry_sha256="b" * 64,
        cycle_cap_usd=100.0,
        cycle_id="cycle-1",
        provider_cycle_caps_sha256="sha256:" + "c" * 64,
        provider_attempt_namespace="claim-ontology-v2",
    )
    assert journal is not None
    with journal:
        journal.run_attempt(1, lambda: {"output": raw_output})
        journal.settle_attempt(
            journal.durable_attempt_ordinal(1),
            input_tokens=10,
            output_tokens=2,
            actual_cost_usd=0.01,
            raw_output=raw_output,
        )
        if record_failure:
            journal.record_reconstruction_failure(
                ValueError("fixture reconstruction failure")
            )
    return markdown_root, journal_path, parser_records, registry_entry


def _structural_review_recovery_kwargs(
    *,
    markdown_root: Path,
    journal_path: Path,
    parser_records: list[JsonRecord],
    registry_entry: llm_pipeline.ModelRegistryEntry,
) -> dict[str, Any]:
    return {
        "selection_record": _selection(),
        "parser_records": parser_records,
        "prediction_unit_records": (_prediction_units(),),
        "markdown_root": markdown_root,
        "markdown_bytes": None,
        "registry_entry": registry_entry,
        "model_registry_sha256": "b" * 64,
        "provider_journal_path": journal_path,
        "provider_cycle_cap_usd": 100.0,
        "provider_cycle_id": "cycle-1",
        "provider_cycle_caps_sha256": "sha256:" + "c" * 64,
        "provider_account": "default",
        "provider_attempt_namespace": "claim-ontology-v2",
    }


def _docket_html() -> str:
    return """
    <html><body><div id="docket-entry-table">
      <div class="row odd" id="entry-1">
        <div class="col-xs-1"><p>1</p></div>
        <div class="col-xs-3"><p>Jan 1, 2026</p></div>
        <div class="col-xs-8"><p>COMPLAINT filed by Plaintiff.</p></div>
      </div>
      <div class="row even" id="entry-5">
        <div class="col-xs-1"><p>5</p></div>
        <div class="col-xs-3"><p>Feb 1, 2026</p></div>
        <div class="col-xs-8"><p>MOTION to Dismiss.</p></div>
      </div>
      <div class="row odd" id="entry-16">
        <div class="col-xs-1"><p>16</p></div>
        <div class="col-xs-3"><p>Jul 1, 2026</p></div>
        <div class="col-xs-8"><p>ORDER on Motion to Dismiss.</p></div>
      </div>
    </div></body></html>
    """


def _write_jsonl(path: Path, records: list[JsonRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[JsonRecord]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
