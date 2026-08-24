"""Focused authority checks for the additive Stage B manifest runner."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from legalforecast.evals import stageb_manifest_runner as runner
from legalforecast.evals.inspect_task import SolverResponse
from legalforecast.labeling import AmendmentClass, UnitResolution, llm_pipeline
from legalforecast.labeling.label_outcomes import OutcomeCitation, OutcomeLabel
from legalforecast.labeling.llm_pipeline import (
    STAGE_B_FROZEN_UNIT_EXCLUSION_ADJUDICATION_V1,
    _require_frozen_unit_adjudication,
)


def _comment(comment_id: str, text: str, *, author: str = "owner") -> dict[str, str]:
    return {"id": comment_id, "author": author, "text": text}


def _beads_comments(
    spend_comments: Sequence[dict[str, str]],
    terminal_comments: Sequence[dict[str, str]],
) -> Callable[..., SimpleNamespace]:
    comments_by_bead = {
        runner.BEAD_ID: spend_comments,
        runner.TERMINAL_APPROVAL_BEAD_ID: terminal_comments,
    }

    def fake_run(args: Sequence[str], **_: object) -> SimpleNamespace:
        bead_id = args[2]
        return SimpleNamespace(stdout=json.dumps(comments_by_bead[bead_id]))

    return fake_run


def _contextual_fixture(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[str, str, str]:
    comment_text = "synthetic owner approval for the contextual fixture"
    candidate_id = "synthetic-contextual-candidate"
    missing_description = "synthetic missing-unit description"
    for constant_name, value in (
        ("CONTEXTUAL_OWNER_APPROVAL_TEXT_SHA256", comment_text),
        ("CONTEXTUAL_OWNER_APPROVAL_CANDIDATE_SHA256", candidate_id),
        ("CONTEXTUAL_OWNER_APPROVAL_MISSING_UNIT_SHA256", missing_description),
    ):
        monkeypatch.setattr(
            runner,
            constant_name,
            str(
                runner.ARTIFACT_PREFIXED_SHA256_V1.commit(
                    value,
                    domain=runner._ADJ_SCHEMA,  # pyright: ignore[reportPrivateUsage]
                ).digest
            ),
        )
    return comment_text, candidate_id, missing_description


def test_owner_approval_ids_require_exact_real_comments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(runner.OWNER_AUTHOR_ENV, "owner")
    spend = _comment("spend-id", runner.SPEND_APPROVAL, author="owner")
    terminal = _comment("terminal-id", runner.TERMINAL_PACKET_APPROVAL, author="owner")
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        _beads_comments([spend], [terminal]),
    )

    assert set(
        runner._owner_approval_ids()  # pyright: ignore[reportPrivateUsage]
    ) == {"spend-id", "terminal-id"}


def test_owner_approval_ids_reject_near_match_terminal_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(runner.OWNER_AUTHOR_ENV, "owner")
    spend = _comment("spend-id", runner.SPEND_APPROVAL, author="owner")
    near_match = _comment(
        "near-match",
        "stage51-terminal-units: approved - packet "
        "8617ee835c3578042a1081f484d6520de187c5da8367e1e6a71228262266dcca",
        author="owner",
    )
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        _beads_comments([spend], [near_match]),
    )

    with pytest.raises(
        runner.StageBManifestError, match="terminal-unit packet approval"
    ):
        runner._owner_approval_ids()  # pyright: ignore[reportPrivateUsage]


def test_owner_approval_ids_reject_terminal_comment_on_spend_bead(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(runner.OWNER_AUTHOR_ENV, "owner")
    spend = _comment("spend-id", runner.SPEND_APPROVAL, author="owner")
    terminal = _comment("terminal-id", runner.TERMINAL_PACKET_APPROVAL, author="owner")
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        _beads_comments([spend, terminal], []),
    )

    with pytest.raises(
        runner.StageBManifestError, match="terminal-unit packet approval"
    ):
        runner._owner_approval_ids()  # pyright: ignore[reportPrivateUsage]


def test_contextual_owner_approval_binds_candidate_specific_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    comment_text, candidate_id, missing_description = _contextual_fixture(monkeypatch)
    monkeypatch.setenv(runner.OWNER_AUTHOR_ENV, "owner")
    comment = _comment(
        runner.CONTEXTUAL_OWNER_APPROVAL_COMMENT_ID,
        comment_text,
        author="owner",
    )
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        _beads_comments([comment], []),
    )
    ruling = {
        "action": "exclude_missing_unit_only",
        "candidate_id": candidate_id,
        "case_id": candidate_id,
        "frozen_unit_ids": ["unit-1", "unit-2", "unit-3", "unit-4"],
        "missing_unit_descriptions": [missing_description],
    }

    digest = runner._owner_comment_ruling_sha256(  # pyright: ignore[reportPrivateUsage]
        runner.CONTEXTUAL_OWNER_APPROVAL_COMMENT_ID,
        expected_ruling=ruling,
    )

    assert digest == str(
        runner.ARTIFACT_PREFIXED_SHA256_V1.commit(
            comment_text,
            domain=runner._ADJ_SCHEMA,  # pyright: ignore[reportPrivateUsage]
        ).digest
    )


@pytest.mark.parametrize(
    "ruling_update",
    [
        {"candidate_id": "other-contextual-candidate"},
        {"frozen_unit_ids": ["unit-1", "unit-2", "unit-3"]},
        {"missing_unit_descriptions": ["different claim"]},
    ],
)
def test_contextual_owner_approval_rejects_unbound_scope(
    monkeypatch: pytest.MonkeyPatch,
    ruling_update: dict[str, Any],
) -> None:
    comment_text, candidate_id, missing_description = _contextual_fixture(monkeypatch)
    monkeypatch.setenv(runner.OWNER_AUTHOR_ENV, "owner")
    comment = _comment(
        runner.CONTEXTUAL_OWNER_APPROVAL_COMMENT_ID,
        comment_text,
        author="owner",
    )
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        _beads_comments([comment], []),
    )
    ruling: dict[str, Any] = {
        "action": "exclude_missing_unit_only",
        "candidate_id": candidate_id,
        "case_id": candidate_id,
        "frozen_unit_ids": ["unit-1", "unit-2", "unit-3", "unit-4"],
        "missing_unit_descriptions": [missing_description],
    }
    ruling.update(ruling_update)

    with pytest.raises(
        runner.StageBManifestError,
        match="not the exact typed ruling",
    ):
        runner._owner_comment_ruling_sha256(  # pyright: ignore[reportPrivateUsage]
            runner.CONTEXTUAL_OWNER_APPROVAL_COMMENT_ID,
            expected_ruling=ruling,
        )


def test_spend_and_terminal_approvals_cannot_authorize_adjudication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(runner.OWNER_AUTHOR_ENV, "owner")
    spend = _comment("spend-id", runner.SPEND_APPROVAL, author="owner")
    terminal = _comment("terminal-id", runner.TERMINAL_PACKET_APPROVAL, author="owner")
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        _beads_comments([spend], [terminal]),
    )

    with pytest.raises(
        runner.StageBManifestError,
        match="not the exact typed ruling",
    ):
        runner._owner_comment_ruling_sha256(  # pyright: ignore[reportPrivateUsage]
            "spend-id",
            expected_ruling={"candidate_id": "synthetic-contextual-candidate"},
        )


def test_additional_attempt_requires_exact_owner_comment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(runner.OWNER_AUTHOR_ENV, "owner")
    approval = _comment(
        runner.ADDITIONAL_ATTEMPT_APPROVAL_COMMENT_ID,
        runner.ADDITIONAL_ATTEMPT_APPROVAL_TEXT,
        author="owner",
    )
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        _beads_comments([approval], []),
    )

    assert (
        runner._additional_attempt_approval_id()  # pyright: ignore[reportPrivateUsage]
        == runner.ADDITIONAL_ATTEMPT_APPROVAL_COMMENT_ID
    )


def test_additional_attempt_permit_binds_prompt_and_journal() -> None:
    entry = cast(
        Any,
        SimpleNamespace(
            registry_key=runner.MODEL_KEYS[1],
            context_limit=1_048_576,
            max_output_tokens=65_536,
            input_token_price=0.5,
            output_token_price=1.0,
            long_context_surcharge=None,
        ),
    )
    scope = runner.provider_prompt_logical_call_scope("exact repair prompt")
    permit = runner._additional_attempt_permit(  # pyright: ignore[reportPrivateUsage]
        candidate_id="candidate-repair-google",
        provider="google",
        account="cycle1-google",
        registry_entry=entry,
        prompt="exact repair prompt",
        journal_path=Path("/tmp/provider-attempts-google.sqlite3"),
        cycle_id="cycle-1-stage-b-manifest",
    )

    assert permit.max_total_attempts == 2
    assert (
        permit.provider_logical_call_scope_sha256
        == hashlib.sha256(scope.encode()).hexdigest()
    )
    llm_pipeline._validate_additional_attempt_permit(  # pyright: ignore[reportPrivateUsage]
        permit,
        prompt="exact repair prompt",
        provider_journal_path=Path("/tmp/provider-attempts-google.sqlite3"),
        provider_logical_call_scope=scope,
    )
    with pytest.raises(llm_pipeline.LlmPipelineError, match="prompt binding differs"):
        llm_pipeline._validate_additional_attempt_permit(  # pyright: ignore[reportPrivateUsage]
            permit,
            prompt="changed prompt",
            provider_journal_path=Path("/tmp/provider-attempts-google.sqlite3"),
            provider_logical_call_scope=scope,
        )


def test_additional_attempt_help_describes_general_candidate_scope() -> None:
    help_text = runner.build_parser().format_help()

    assert "Owner-approved one additional same-model attempt" in help_text
    assert "one selected failed Stage B candidate" in help_text
    assert "72213663" not in help_text


def test_additional_attempt_prompt_uses_exact_journal_evidence() -> None:
    prompt = runner._additional_attempt_prompt(  # pyright: ignore[reportPrivateUsage]
        original_prompt="authenticated prompt",
        evidence=runner.ReconstructionFailureEvidence(
            attempt_ordinal=1,
            raw_response_json='{"response":"exact"}',
            normalized_response_json='{"raw_output":"{\\"bad\\":true}"}',
            failure_type="ValueError",
            failure_message="unknown unit IDs: ['invented']",
        ),
    )

    assert json.loads(prompt) == {
        "instruction": "Return only corrected Stage B schema JSON.",
        "original_authenticated_prompt": "authenticated prompt",
        "original_raw_submission": '{"bad":true}',
        "validation_error": {
            "type": "ValueError",
            "message": "unknown unit IDs: ['invented']",
        },
    }


def _valid_result() -> tuple[dict[str, Any], dict[str, Any]]:
    selection = {"candidate_id": "candidate-1", "case_id": "case-1"}
    frozen_units = ({"unit_id": "unit-1"},)
    decision_commitment = {
        "decision_texts_sha256": "decision",
        "decision_texts_manifest_sha256": "manifest",
        "decision_texts_run_card_sha256": "run-card",
        "decision_text_record_sha256": "record",
        "decision_text_sha256": "sha256:text",
        "decision_text_case_id": "case-1",
        "finalized_prediction_units_sha256": "units",
        "finalized_unit_envelope_sha256": "envelope",
    }
    label = OutcomeLabel(
        unit_id="unit-1",
        unit_resolution=UnitResolution.SURVIVES_IN_MATERIAL_RESPECT,
        fully_dismissed=False,
        amendment_class=AmendmentClass.NOT_FULLY_DISMISSED,
        ambiguous=False,
        label_confidence=0.9,
        supporting_citations=(OutcomeCitation(document_id="decision-1"),),
        first_written_disposition_id="decision-1",
        first_written_disposition_date="2026-08-01",
    ).to_record()
    prompt = "authenticated prompt"
    model_key = "openai:gpt-5.4-mini-2026-03-17"
    model_output = {
        "model_key": model_key,
        "input_tokens": 1,
        "output_tokens": 1,
        "estimated_cost": 0.01,
        "raw_output_sha256": "sha256:raw",
        "finding_count": 0,
        "missing_unit_flag_count": 0,
        "provider_prompt_sha256": "sha256:"
        + hashlib.sha256(prompt.encode()).hexdigest(),
        "metadata": {
            "provider": "openai",
            "model": "gpt-5.4-mini-2026-03-17",
            "model_id": "gpt-5.4-mini-2026-03-17",
            "model_registry_sha256": "registry",
            "provider_sampling_policy": "provider_default",
            "tool_policy": "no_tools",
        },
        "labels": [label],
    }
    audit = {
        "stage": "llm-label-provider-shard",
        "status": "succeeded",
        "candidate_id": "candidate-1",
        "case_id": "case-1",
        "execution_provider": "openai",
        "model_keys": [model_key],
        "frozen_panel_model_keys": list(runner.MODEL_KEYS),
        "model_registry_sha256": "registry",
        "decision_text_commitment": decision_commitment,
        "label_count": 0,
        "unit_count": 1,
        "model_outputs": [model_output],
        "estimated_cost": 0.01,
    }
    result = {
        "schema_version": str(runner.STAGE_B_MANIFEST_PROVIDER_RESULT_V1),
        "status": "succeeded",
        "candidate_id": "candidate-1",
        "case_id": "case-1",
        "provider": "openai",
        "model_key": model_key,
        "model_registry_sha256": "registry",
        "raw_prediction_units_sha256": "raw",
        "raw_candidate_envelope_sha256": "envelope",
        "decision_texts_sha256": "decision",
        "provider_sampling_policy": "provider_default",
        "tools_enabled": False,
        "audit": audit,
    }
    context = {
        "selection": selection,
        "frozen_units": frozen_units,
        "decision_commitment": decision_commitment,
        "prompt": prompt,
    }
    return result, context


def _assert_result_rejected(
    tmp_path: Path,
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    result, context = _valid_result()
    mutate(result)
    path = tmp_path / "result.json"
    path.write_text(json.dumps(result), encoding="utf-8")
    with pytest.raises(runner.StageBManifestError):
        runner._existing_result(  # pyright: ignore[reportPrivateUsage]
            path,
            candidate_id="candidate-1",
            provider="openai",
            model_key="openai:gpt-5.4-mini-2026-03-17",
            raw_sha256="raw",
            raw_candidate_envelope_sha256="envelope",
            decision_sha256="decision",
            registry_sha256="registry",
            selection=context["selection"],
            frozen_units=context["frozen_units"],
            decision_commitment=context["decision_commitment"],
            prompt=context["prompt"],
        )


def test_supporting_evidence_sidecar_is_non_authoritative_and_result_bound(
    tmp_path: Path,
) -> None:
    result_path = tmp_path / "candidate-1.json"
    result_bytes = b'{"status":"succeeded"}\n'
    result_path.write_bytes(result_bytes)
    sidecar_path = runner._supporting_evidence_sidecar_path(  # pyright: ignore[reportPrivateUsage]
        result_path
    )
    sidecar_path.write_text(
        json.dumps(
            {
                "kind": runner.SUPPORTING_EVIDENCE_SIDECAR_KIND,
                "authoritative": False,
                "result_sha256": runner._raw_sha256(result_bytes),  # pyright: ignore[reportPrivateUsage]
                "candidate_id": "candidate-1",
                "provider": "openai",
                "model_key": runner.MODEL_KEYS[0],
                "supporting_evidence_status": "unresolved_advisory",
                "supporting_evidence_affected_unit_ids": ["unit-1"],
            }
        ),
        encoding="utf-8",
    )

    validated = runner._validated_supporting_evidence_sidecar(  # pyright: ignore[reportPrivateUsage]
        result_path=result_path,
        result_bytes=result_bytes,
        candidate_id="candidate-1",
        provider="openai",
        model_key=runner.MODEL_KEYS[0],
        frozen_unit_ids={"unit-1"},
    )
    assert validated is not None
    assert validated["authoritative"] is False
    assert validated["supporting_evidence_affected_unit_ids"] == ["unit-1"]

    with pytest.raises(runner.StageBManifestError, match="result_sha256"):
        runner._validated_supporting_evidence_sidecar(  # pyright: ignore[reportPrivateUsage]
            result_path=result_path,
            result_bytes=b'{"status":"tampered"}\n',
            candidate_id="candidate-1",
            provider="openai",
            model_key=runner.MODEL_KEYS[0],
            frozen_unit_ids={"unit-1"},
        )


def test_existing_result_replays_full_nested_identity(tmp_path: Path) -> None:
    result, context = _valid_result()
    path = tmp_path / "result.json"
    path.write_text(json.dumps(result), encoding="utf-8")
    replayed = runner._existing_result(  # pyright: ignore[reportPrivateUsage]
        path,
        candidate_id="candidate-1",
        provider="openai",
        model_key="openai:gpt-5.4-mini-2026-03-17",
        raw_sha256="raw",
        raw_candidate_envelope_sha256="envelope",
        decision_sha256="decision",
        registry_sha256="registry",
        selection=context["selection"],
        frozen_units=context["frozen_units"],
        decision_commitment=context["decision_commitment"],
        prompt=context["prompt"],
    )
    assert replayed == result


def test_existing_failed_result_is_preserved_for_adjudicated_rerun(
    tmp_path: Path,
) -> None:
    result, context = _valid_result()
    result["status"] = "failed"
    path = tmp_path / "result.json"
    original = json.dumps(result).encode()
    path.write_bytes(original)

    assert (
        runner._existing_result(  # pyright: ignore[reportPrivateUsage]
            path,
            candidate_id="candidate-1",
            provider="openai",
            model_key="openai:gpt-5.4-mini-2026-03-17",
            raw_sha256="raw",
            raw_candidate_envelope_sha256="envelope",
            decision_sha256="decision",
            registry_sha256="registry",
            selection=context["selection"],
            frozen_units=context["frozen_units"],
            decision_commitment=context["decision_commitment"],
            prompt=context["prompt"],
            frozen_unit_adjudication={"candidate_id": "candidate-1"},
        )
        is None
    )
    assert not path.exists()
    assert (tmp_path / "result.json.failed").read_bytes() == original


def test_existing_failed_result_without_adjudication_remains_create_only(
    tmp_path: Path,
) -> None:
    result, context = _valid_result()
    result["status"] = "failed"
    path = tmp_path / "result.json"
    path.write_text(json.dumps(result), encoding="utf-8")

    with pytest.raises(
        runner.StageBManifestError, match="requires frozen-unit adjudication"
    ):
        runner._existing_result(  # pyright: ignore[reportPrivateUsage]
            path,
            candidate_id="candidate-1",
            provider="openai",
            model_key="openai:gpt-5.4-mini-2026-03-17",
            raw_sha256="raw",
            raw_candidate_envelope_sha256="envelope",
            decision_sha256="decision",
            registry_sha256="registry",
            selection=context["selection"],
            frozen_units=context["frozen_units"],
            decision_commitment=context["decision_commitment"],
            prompt=context["prompt"],
        )
    assert path.exists()


def test_stage_b_replay_only_never_falls_back_to_live_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    live_calls: list[object] = []

    def fail_live(*args: object, **kwargs: object) -> object:
        live_calls.append((args, kwargs))
        raise AssertionError("provider transport must not be called")

    monkeypatch.setattr(llm_pipeline, "complete_live_prompt", fail_live)
    with pytest.raises(
        llm_pipeline.LlmPipelineError,
        match="provider-free Stage B replay has no retained response",
    ):
        llm_pipeline._llm_label_one_model(  # pyright: ignore[reportPrivateUsage]
            selection={"candidate_id": "candidate-1", "case_id": "case-1"},
            decision_text=cast(Any, SimpleNamespace()),
            decision_text_commitment={},
            frozen_units=(),
            prompt="provider-free replay prompt",
            registry_entry=cast(
                Any,
                SimpleNamespace(provider="openai", registry_key="openai:model"),
            ),
            model_registry_sha256=None,
            transport=None,
            environ=None,
            timeout_seconds=1.0,
            provider_journal_path=None,
            provider_cycle_cap_usd=0.0,
            provider_cycle_id=None,
            provider_cycle_caps_sha256=None,
            provider_spend_authorities=None,
            provider_accounts=None,
            replay_only=True,
        )
    assert live_calls == []


def test_frozen_unit_adjudication_binds_exact_response_and_exclusion() -> None:
    missing_flags = ({"missing_unit_description": "new claim"},)
    exclusion = {
        "candidate_id": "candidate-1",
        "case_id": "case-1",
        "reason": "unit_missing_from_stage_a",
    }
    response = SolverResponse(raw_output='{"unit_findings": []}')
    adjudication = {
        "schema_version": STAGE_B_FROZEN_UNIT_EXCLUSION_ADJUDICATION_V1,
        "candidate_id": "candidate-1",
        "case_id": "case-1",
        "status": "missing_unit_excluded_from_scoring",
        "score_scope": "frozen_units_only",
        "scoreable_unit_ids": ["unit-1"],
        "owner_comment_id": "owner-comment",
        "owner_ruling": {
            "action": "exclude_missing_unit_only",
            "candidate_id": "candidate-1",
            "case_id": "case-1",
            "frozen_unit_ids": ["unit-1"],
            "missing_unit_descriptions": ["new claim"],
        },
        "owner_ruling_sha256": "sha256:owner-ruling",
        "raw_output_sha256": response.raw_output_sha256,
        "frozen_unit_ids": ["unit-1"],
        "missing_unit_flags_sha256": runner.canonical_records_sha256(missing_flags),
        "exclusion_entry_sha256": runner.canonical_sha256(exclusion),
    }
    _require_frozen_unit_adjudication(
        adjudication,
        candidate_id="candidate-1",
        case_id="case-1",
        frozen_unit_ids=("unit-1",),
        missing_flags=missing_flags,
        exclusion_record=exclusion,
        response=response,
        normalized_response_json=None,
    )

    tampered = dict(adjudication, raw_output_sha256="sha256:tampered")
    with pytest.raises(ValueError, match="raw response differs"):
        _require_frozen_unit_adjudication(
            tampered,
            candidate_id="candidate-1",
            case_id="case-1",
            frozen_unit_ids=("unit-1",),
            missing_flags=missing_flags,
            exclusion_record=exclusion,
            response=response,
            normalized_response_json=None,
        )


def test_frozen_unit_adjudication_index_is_create_only(tmp_path: Path) -> None:
    payload = {
        "schema_version": runner.FROZEN_UNIT_ADJUDICATION_INDEX_V1,
        "records": [
            {
                "schema_version": STAGE_B_FROZEN_UNIT_EXCLUSION_ADJUDICATION_V1,
                "candidate_id": "candidate-1",
                "case_id": "case-1",
            }
        ],
    }
    path = tmp_path / "adjudications.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    first, digest = runner._load_frozen_unit_adjudications(path)  # pyright: ignore[reportPrivateUsage]
    second, second_digest = runner._load_frozen_unit_adjudications(path)  # pyright: ignore[reportPrivateUsage]
    assert first == second
    assert digest == second_digest
    assert digest is not None


@pytest.mark.parametrize(
    ("has_reconstruction_failure", "has_validated_response"),
    [(True, False), (False, True)],
)
def test_issuer_reconstructs_retained_response_without_transport(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    has_reconstruction_failure: bool,
    has_validated_response: bool,
) -> None:
    class FakeJournal:
        def __init__(self, account: str) -> None:
            assert account == "cycle1-google"
            self.has_reconstruction_failure = has_reconstruction_failure
            self.has_validated_response = has_validated_response
            self.has_settled_attempt = False

        def __enter__(self) -> FakeJournal:
            return self

        def __exit__(self, *args: object) -> None:
            self.close()

        def close(self) -> None:
            return None

        def record_reconstruction_failure(self, error: Exception) -> None:
            assert isinstance(error, runner.FrozenUnitWorkflowRequiredError)
            self.has_validated_response = False
            self.has_reconstruction_failure = True

        def latest_reconstruction_recovery_evidence(self) -> SimpleNamespace:
            return SimpleNamespace(
                normalized_response_json='{"actual_cost_usd":0.01}',
            )

    decision = SimpleNamespace(text_sha256="sha256:decision")
    missing_flag = SimpleNamespace(
        to_record=lambda _: {"missing_unit_description": "new claim"}
    )
    exclusion = SimpleNamespace(
        to_record=lambda: {
            "candidate_id": "candidate-1",
            "case_id": "case-1",
            "reason": "unit_missing_from_stage_a",
        }
    )
    workflow_error = runner.FrozenUnitWorkflowRequiredError(
        response=SolverResponse(raw_output='{"unit_findings": []}'),
        labeling_result=SimpleNamespace(
            candidate_id="candidate-1",
            case_id="case-1",
            decision_text=decision,
            missing_unit_flags=(missing_flag,),
        ),
        repair_result=SimpleNamespace(
            units=(SimpleNamespace(unit_id="unit-1"),),
            exclusion_entry=exclusion,
        ),
    )
    monkeypatch.setattr(
        runner,
        "_provider_attempt_journal",
        lambda **kwargs: FakeJournal(str(kwargs["account"])),
    )
    monkeypatch.setattr(
        runner,
        "_owner_comment_ruling_sha256",
        lambda _, **__: "sha256:ruling",
    )
    monkeypatch.setattr(
        runner,
        "_prediction_units_by_candidate",
        lambda _: {"candidate-1": (SimpleNamespace(unit_id="unit-1"),)},
    )
    monkeypatch.setattr(
        runner,
        "_verified_stage_b_decisions",
        lambda _: {
            "candidate-1": (decision, {"decision_text_sha256": "sha256:decision"})
        },
    )
    monkeypatch.setattr(runner, "_labeling_prompt", lambda *args, **kwargs: "prompt")
    transport_calls: list[object] = []

    def fake_label(**kwargs: Any) -> object:
        transport_calls.append((kwargs["transport"], kwargs["provider_accounts"]))
        raise workflow_error

    monkeypatch.setattr(runner, "_llm_label_one_model", fake_label)
    artifact = cast(
        Any,
        SimpleNamespace(finalized_unit_envelope_sha256s={"candidate-1": "envelope"}),
    )
    runner._issue_frozen_unit_adjudication(  # pyright: ignore[reportPrivateUsage]
        output_path=tmp_path / "adjudications.json",
        owner_comment_id="owner-comment",
        provider="google",
        output_root=tmp_path / "output",
        artifact=artifact,
        selection_records=({"candidate_id": "candidate-1", "case_id": "case-1"},),
        adapted_records=(),
        registry_entry=cast(
            Any,
            SimpleNamespace(provider="google", registry_key=runner.MODEL_KEYS[1]),
        ),
        registry_sha256="registry",
        raw_sha256="raw",
        decision_sha256="decision",
    )
    assert transport_calls == [(None, {"google": "cycle1-google"})]
    issued = json.loads((tmp_path / "adjudications.json").read_text())
    assert issued["records"][0]["frozen_unit_ids"] == ["unit-1"]


def _tamper_envelope(result: dict[str, Any]) -> None:
    result.update(raw_candidate_envelope_sha256="tampered")


def _tamper_candidate(result: dict[str, Any]) -> None:
    result["audit"].update(candidate_id="other")


def _tamper_sampling(result: dict[str, Any]) -> None:
    result["audit"]["model_outputs"][0]["metadata"].update(
        provider_sampling_policy="custom"
    )


def _tamper_prompt(result: dict[str, Any]) -> None:
    result["audit"]["model_outputs"][0].update(provider_prompt_sha256="sha256:tampered")


def _tamper_labels(result: dict[str, Any]) -> None:
    result["audit"]["model_outputs"][0].update(labels=[])


@pytest.mark.parametrize(
    "mutate",
    [
        _tamper_envelope,
        _tamper_candidate,
        _tamper_sampling,
        _tamper_prompt,
        _tamper_labels,
    ],
)
def test_existing_result_rejects_tampered_nested_receipt(
    tmp_path: Path,
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    _assert_result_rejected(tmp_path, mutate)


def test_provider_environment_requires_one_matching_provider_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    runner._validate_provider_environment("openai")  # pyright: ignore[reportPrivateUsage]
    with pytest.raises(runner.StageBManifestError, match="only GEMINI_API_KEY"):
        monkeypatch.setenv("GEMINI_API_KEY", "google-test")
        runner._validate_provider_environment("google")  # pyright: ignore[reportPrivateUsage]


@pytest.mark.parametrize(
    ("receipt", "message"),
    [
        (None, "provider shard receipt is missing"),
        ({"audit": {"stage": "tampered"}}, "provider shard audit does not match"),
    ],
)
def test_full_merge_rejects_missing_or_tampered_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    receipt: dict[str, Any] | None,
    message: str,
) -> None:
    monkeypatch.setattr(runner, "EXPECTED_CASE_COUNT", 1)
    monkeypatch.setattr(runner, "EXPECTED_UNIT_COUNT", 1)
    provider = "openai"
    entry = cast(
        Any,
        SimpleNamespace(
            provider=provider,
            registry_key=runner.MODEL_KEYS[0],
        ),
    )
    selection = {"candidate_id": "candidate-1", "case_id": "case-1"}
    audit = {
        "stage": "llm-label-provider-shard",
        "status": "succeeded",
        "candidate_id": "candidate-1",
    }
    audit_payload = runner._canonical_jsonl((audit,))  # pyright: ignore[reportPrivateUsage]
    audit_path, card_path = runner._shard_artifact_paths(  # pyright: ignore[reportPrivateUsage]
        tmp_path, provider, None
    )
    audit_path.write_bytes(audit_payload)
    journal_path = runner._provider_attempt_journal_path(  # pyright: ignore[reportPrivateUsage]
        tmp_path, provider
    )
    journal_path.write_bytes(b"provider-free journal")
    card_path.write_text(
        json.dumps(
            {
                "schema_version": str(
                    runner.STAGE_B_MANIFEST_PROVIDER_SHARD_RUN_CARD_V1
                ),
                "stage": "llm-label-provider-shard",
                "status": "completed",
                "dry_run": False,
                "execute": True,
                "paid_activity_requested": True,
                "paid_activity_executed": True,
                "execution_provider": provider,
                "model_keys": list(runner.MODEL_KEYS),
                "executed_model_keys": [runner.MODEL_KEYS[0]],
                "provider_sampling_policy": "provider_default",
                "tools_enabled": False,
                "create_only": True,
                "resumable": True,
                "max_cases": None,
                "case_count": 1,
                "unit_count": 1,
                "owner_comment_ids": ["spend", "terminal"],
                "source_commitments": {
                    "raw_prediction_units": "raw",
                    "selection": runner.CURRENT_SELECTION_SHA256,
                    "legacy_decision_texts": runner.DECISION_TEXTS_SHA256,
                    "decision_texts_current": "decision",
                    "model_registry": "registry",
                    "terminal_packet_approval": runner.TERMINAL_PACKET_APPROVAL,
                },
                "output_commitments": {
                    "audit": runner._raw_sha256(audit_payload),  # pyright: ignore[reportPrivateUsage]
                    "provider_attempt_journal": runner._source_digest(journal_path),  # pyright: ignore[reportPrivateUsage]
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        runner,
        "_prediction_units_by_candidate",
        lambda _: {"candidate-1": (SimpleNamespace(unit_id="unit-1"),)},
    )
    monkeypatch.setattr(
        runner,
        "_verified_stage_b_decisions",
        lambda _: {"candidate-1": (SimpleNamespace(), {})},
    )
    monkeypatch.setattr(runner, "_labeling_prompt", lambda *args, **kwargs: "prompt")
    monkeypatch.setattr(runner, "_existing_result", lambda *args, **kwargs: receipt)

    with pytest.raises(runner.StageBManifestError, match=message):
        runner._validate_full_provider_shard(  # pyright: ignore[reportPrivateUsage]
            output_root=tmp_path,
            provider=provider,
            registry_entry=entry,
            registry_sha256="registry",
            raw_sha256="raw",
            decision_sha256="decision",
            artifact=cast(
                Any,
                SimpleNamespace(
                    finalized_unit_envelope_sha256s={"candidate-1": "candidate-raw"}
                ),
            ),
            selection_records=(selection,),
            adapted_records=(),
            owner_comment_ids=("spend", "terminal"),
        )


def test_merge_writes_and_replays_create_only_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entries = tuple(
        cast(
            Any,
            SimpleNamespace(
                provider=provider,
                registry_key=model_key,
            ),
        )
        for provider, model_key in zip(
            ("openai", "google"), runner.MODEL_KEYS, strict=True
        )
    )
    selection = {"candidate_id": "candidate-1", "case_id": "case-1"}
    shard_audits = {
        provider: (
            {
                "stage": "llm-label-provider-shard",
                "status": "succeeded",
                "candidate_id": "candidate-1",
                "execution_provider": provider,
            },
        )
        for provider in ("openai", "google")
    }

    def fake_validate(
        **kwargs: Any,
    ) -> tuple[tuple[dict[str, Any], ...], dict[str, Any]]:
        provider = kwargs["provider"]
        return shard_audits[provider], {
            "provider": provider,
            "audit_sha256": f"{provider}-audit",
            "run_card_sha256": f"{provider}-card",
            "case_count": 1,
            "unit_count": 1,
        }

    review_queue = {
        "schema_version": "legalforecast.lawyer_review_queue.v1",
        "status": "pending_adjudication",
        "candidate_id": "candidate-1",
        "case_id": "case-1",
        "unit_id": "unit-1",
        "review_id": "review-1",
        "route_reason": "disagreement",
        "packet": {},
    }
    merged = SimpleNamespace(
        records=({"unit_id": "unit-1", "label": "survives"},),
        audit_records=(
            {
                "stage": "llm-label",
                "status": "adjudication_pending",
                "candidate_id": "candidate-1",
                "lawyer_review_queue": [review_queue],
            },
        ),
    )
    monkeypatch.setattr(runner, "_validate_full_provider_shard", fake_validate)
    monkeypatch.setattr(
        runner,
        "_prediction_units_by_candidate",
        lambda _: {"candidate-1": (SimpleNamespace(unit_id="unit-1"),)},
    )
    monkeypatch.setattr(runner, "merge_llm_label_provider_shards", lambda **_: merged)

    kwargs = {
        "output_root": tmp_path,
        "artifact": cast(Any, SimpleNamespace()),
        "selection_records": (selection,),
        "adapted_records": (),
        "registry_entries": entries,
        "owner_comment_ids": ("spend", "terminal"),
        "registry_sha256": "registry",
        "raw_sha256": "raw",
        "decision_sha256": "decision",
    }
    first = runner._merge_provider_shards(**kwargs)  # pyright: ignore[reportPrivateUsage]
    first_bytes = {
        name: (tmp_path / name).read_bytes()
        for name in (
            "labels.jsonl",
            "llm-label-audit.jsonl",
            "lawyer-review-queue.jsonl",
            "llm-label-merge-run-card.json",
        )
    }
    second = runner._merge_provider_shards(**kwargs)  # pyright: ignore[reportPrivateUsage]
    second_bytes = {name: (tmp_path / name).read_bytes() for name in first_bytes}

    assert first == second
    assert first_bytes == second_bytes
    assert json.loads(first_bytes["llm-label-merge-run-card.json"])["label_count"] == 1
    assert first_bytes["lawyer-review-queue.jsonl"].count(b"review-1") == 1


def test_full_provider_shard_authenticates_complete_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, context = _valid_result()
    audit = cast(dict[str, Any], result["audit"])
    audit_payload = runner._canonical_jsonl((audit,))  # pyright: ignore[reportPrivateUsage]
    audit_path, card_path = runner._shard_artifact_paths(  # pyright: ignore[reportPrivateUsage]
        tmp_path, "openai", None
    )
    audit_path.write_bytes(audit_payload)
    journal_path = runner._provider_attempt_journal_path(  # pyright: ignore[reportPrivateUsage]
        tmp_path, "openai"
    )
    journal_path.write_bytes(b"provider-free journal")
    result_path = runner._result_path(  # pyright: ignore[reportPrivateUsage]
        tmp_path, "openai", "candidate-1"
    )
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(result), encoding="utf-8")
    card_path.write_text(
        json.dumps(
            {
                "schema_version": str(
                    runner.STAGE_B_MANIFEST_PROVIDER_SHARD_RUN_CARD_V1
                ),
                "stage": "llm-label-provider-shard",
                "status": "completed",
                "dry_run": False,
                "execute": True,
                "paid_activity_requested": True,
                "paid_activity_executed": True,
                "execution_provider": "openai",
                "model_keys": list(runner.MODEL_KEYS),
                "executed_model_keys": [runner.MODEL_KEYS[0]],
                "provider_sampling_policy": "provider_default",
                "tools_enabled": False,
                "create_only": True,
                "resumable": True,
                "max_cases": None,
                "case_count": 1,
                "unit_count": 1,
                "owner_comment_ids": ["spend", "terminal"],
                "source_commitments": {
                    "raw_prediction_units": "raw",
                    "selection": runner.CURRENT_SELECTION_SHA256,
                    "legacy_decision_texts": runner.DECISION_TEXTS_SHA256,
                    "decision_texts_current": "decision",
                    "model_registry": "registry",
                    "terminal_packet_approval": runner.TERMINAL_PACKET_APPROVAL,
                },
                "output_commitments": {
                    "audit": runner._raw_sha256(audit_payload),  # pyright: ignore[reportPrivateUsage]
                    "provider_attempt_journal": runner._source_digest(journal_path),  # pyright: ignore[reportPrivateUsage]
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(runner, "EXPECTED_CASE_COUNT", 1)
    monkeypatch.setattr(runner, "EXPECTED_UNIT_COUNT", 1)
    monkeypatch.setattr(
        runner,
        "_prediction_units_by_candidate",
        lambda _: {"candidate-1": context["frozen_units"]},
    )
    monkeypatch.setattr(
        runner,
        "_verified_stage_b_decisions",
        lambda _: {
            "candidate-1": ("authenticated decision", context["decision_commitment"])
        },
    )
    monkeypatch.setattr(
        runner, "_labeling_prompt", lambda *args, **kwargs: context["prompt"]
    )

    audits, shard = runner._validate_full_provider_shard(  # pyright: ignore[reportPrivateUsage]
        output_root=tmp_path,
        provider="openai",
        registry_entry=cast(
            Any,
            SimpleNamespace(provider="openai", registry_key=runner.MODEL_KEYS[0]),
        ),
        registry_sha256="registry",
        raw_sha256="raw",
        decision_sha256="decision",
        artifact=cast(
            Any,
            SimpleNamespace(
                finalized_unit_envelope_sha256s={"candidate-1": "envelope"}
            ),
        ),
        selection_records=(context["selection"],),
        adapted_records=(),
        owner_comment_ids=("spend", "terminal"),
    )

    assert audits == (audit,)
    assert shard["provider"] == "openai"
    assert shard["case_count"] == 1
    assert shard["unit_count"] == 1
    assert shard["provider_attempt_journal"] == runner._source_digest(  # pyright: ignore[reportPrivateUsage]
        journal_path
    )
    original_card = json.loads(card_path.read_text(encoding="utf-8"))
    extra_owner_card = dict(original_card)
    extra_owner_card["owner_comment_ids"] = [
        "spend",
        "terminal",
        "unexpected-extra-approval",
    ]
    card_path.write_text(json.dumps(extra_owner_card), encoding="utf-8")
    with pytest.raises(
        runner.StageBManifestError, match="provider shard run card field differs"
    ):
        runner._validate_full_provider_shard(  # pyright: ignore[reportPrivateUsage]
            output_root=tmp_path,
            provider="openai",
            registry_entry=cast(
                Any,
                SimpleNamespace(provider="openai", registry_key=runner.MODEL_KEYS[0]),
            ),
            registry_sha256="registry",
            raw_sha256="raw",
            decision_sha256="decision",
            artifact=cast(
                Any,
                SimpleNamespace(
                    finalized_unit_envelope_sha256s={"candidate-1": "envelope"}
                ),
            ),
            selection_records=(context["selection"],),
            adapted_records=(),
            owner_comment_ids=("spend", "terminal"),
        )

    card_path.write_text(json.dumps(original_card), encoding="utf-8")
    tampered_card = json.loads(card_path.read_text(encoding="utf-8"))
    tampered_card["output_commitments"]["provider_attempt_journal"] = "tampered"
    card_path.write_text(json.dumps(tampered_card), encoding="utf-8")
    with pytest.raises(
        runner.StageBManifestError, match="attempt journal commitment differs"
    ):
        runner._validate_full_provider_shard(  # pyright: ignore[reportPrivateUsage]
            output_root=tmp_path,
            provider="openai",
            registry_entry=cast(
                Any,
                SimpleNamespace(provider="openai", registry_key=runner.MODEL_KEYS[0]),
            ),
            registry_sha256="registry",
            raw_sha256="raw",
            decision_sha256="decision",
            artifact=cast(
                Any,
                SimpleNamespace(
                    finalized_unit_envelope_sha256s={"candidate-1": "envelope"}
                ),
            ),
            selection_records=(context["selection"],),
            adapted_records=(),
            owner_comment_ids=("spend", "terminal"),
        )


def test_retry_provider_shard_authenticates_its_extra_approval_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, context = _valid_result()
    candidate_id = "candidate-repair-google"
    context["selection"]["candidate_id"] = candidate_id
    result["candidate_id"] = candidate_id
    cast(dict[str, Any], result["audit"])["candidate_id"] = candidate_id
    evidence = runner.ReconstructionFailureEvidence(
        attempt_ordinal=1,
        raw_response_json='{"response":"exact"}',
        normalized_response_json='{"raw_output":"{\\"bad\\":true}"}',
        failure_type="ValueError",
        failure_message="unknown unit IDs: ['invented']",
    )
    repair_prompt = runner._additional_attempt_prompt(  # pyright: ignore[reportPrivateUsage]
        original_prompt=context["prompt"], evidence=evidence
    )
    cast(dict[str, Any], cast(dict[str, Any], result["audit"])["model_outputs"][0])[
        "provider_prompt_sha256"
    ] = "sha256:" + hashlib.sha256(repair_prompt.encode()).hexdigest()
    audit_payload = runner._canonical_jsonl(  # pyright: ignore[reportPrivateUsage]
        (cast(dict[str, Any], result["audit"]),)
    )
    audit_path, card_path = runner._shard_artifact_paths(  # pyright: ignore[reportPrivateUsage]
        tmp_path, "openai", None
    )
    audit_path.write_bytes(audit_payload)
    journal_path = runner._provider_attempt_journal_path(  # pyright: ignore[reportPrivateUsage]
        tmp_path, "openai"
    )
    journal_path.write_bytes(b"provider-free journal")
    retry_path = runner._additional_attempt_result_path(  # pyright: ignore[reportPrivateUsage]
        tmp_path, "openai", candidate_id
    )
    retry_path.parent.mkdir(parents=True, exist_ok=True)
    retry_path.write_text(json.dumps(result), encoding="utf-8")
    monkeypatch.setattr(
        runner,
        "_additional_attempt_approval_id",
        lambda: runner.ADDITIONAL_ATTEMPT_APPROVAL_COMMENT_ID,
    )
    card_path.write_text(
        json.dumps(
            {
                "schema_version": str(
                    runner.STAGE_B_MANIFEST_PROVIDER_SHARD_RUN_CARD_V1
                ),
                "stage": "llm-label-provider-shard",
                "status": "completed",
                "dry_run": False,
                "execute": True,
                "paid_activity_requested": True,
                "paid_activity_executed": True,
                "execution_provider": "openai",
                "model_keys": list(runner.MODEL_KEYS),
                "executed_model_keys": [runner.MODEL_KEYS[0]],
                "provider_sampling_policy": "provider_default",
                "tools_enabled": False,
                "create_only": True,
                "resumable": True,
                "max_cases": None,
                "case_count": 1,
                "unit_count": 1,
                "owner_comment_ids": [
                    "spend",
                    "terminal",
                    runner.ADDITIONAL_ATTEMPT_APPROVAL_COMMENT_ID,
                ],
                "source_commitments": {
                    "raw_prediction_units": "raw",
                    "selection": runner.CURRENT_SELECTION_SHA256,
                    "legacy_decision_texts": runner.DECISION_TEXTS_SHA256,
                    "decision_texts_current": "decision",
                    "model_registry": "registry",
                    "terminal_packet_approval": runner.TERMINAL_PACKET_APPROVAL,
                },
                "output_commitments": {
                    "audit": runner._raw_sha256(audit_payload),  # pyright: ignore[reportPrivateUsage]
                    "provider_attempt_journal": runner._source_digest(journal_path),  # pyright: ignore[reportPrivateUsage]
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(runner, "EXPECTED_CASE_COUNT", 1)
    monkeypatch.setattr(runner, "EXPECTED_UNIT_COUNT", 1)
    monkeypatch.setattr(
        runner,
        "_prediction_units_by_candidate",
        lambda _: {candidate_id: context["frozen_units"]},
    )
    monkeypatch.setattr(
        runner,
        "_verified_stage_b_decisions",
        lambda _: {
            candidate_id: ("authenticated decision", context["decision_commitment"])
        },
    )
    monkeypatch.setattr(
        runner, "_labeling_prompt", lambda *args, **kwargs: context["prompt"]
    )
    monkeypatch.setattr(
        runner, "_reconstruction_failure_evidence", lambda **_: evidence
    )

    audits, _ = runner._validate_full_provider_shard(  # pyright: ignore[reportPrivateUsage]
        output_root=tmp_path,
        provider="openai",
        registry_entry=cast(
            Any,
            SimpleNamespace(provider="openai", registry_key=runner.MODEL_KEYS[0]),
        ),
        registry_sha256="registry",
        raw_sha256="raw",
        decision_sha256="decision",
        artifact=cast(
            Any,
            SimpleNamespace(finalized_unit_envelope_sha256s={candidate_id: "envelope"}),
        ),
        selection_records=(context["selection"],),
        adapted_records=(),
        owner_comment_ids=("spend", "terminal"),
    )
    model_output = cast(dict[str, Any], audits[0]["model_outputs"][0])
    assert model_output["provider_prompt_scope"] == "repair"
    assert model_output["original_provider_prompt_sha256"] == (
        "sha256:" + hashlib.sha256(context["prompt"].encode()).hexdigest()
    )

    card = json.loads(card_path.read_text(encoding="utf-8"))
    card["owner_comment_ids"].append("unexpected-extra-approval")
    card_path.write_text(json.dumps(card), encoding="utf-8")
    with pytest.raises(
        runner.StageBManifestError, match="provider shard run card field differs"
    ):
        runner._validate_full_provider_shard(  # pyright: ignore[reportPrivateUsage]
            output_root=tmp_path,
            provider="openai",
            registry_entry=cast(
                Any,
                SimpleNamespace(provider="openai", registry_key=runner.MODEL_KEYS[0]),
            ),
            registry_sha256="registry",
            raw_sha256="raw",
            decision_sha256="decision",
            artifact=cast(
                Any,
                SimpleNamespace(
                    finalized_unit_envelope_sha256s={candidate_id: "envelope"}
                ),
            ),
            selection_records=(context["selection"],),
            adapted_records=(),
            owner_comment_ids=("spend", "terminal"),
        )


def test_full_provider_shard_rejects_adjudication_hash_not_bound_to_journal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, context = _valid_result()
    audit = cast(dict[str, Any], result["audit"])
    raw_output = '{"unit_findings": []}'
    normalized_response_json = json.dumps(
        {"raw_output": raw_output}, sort_keys=True, separators=(",", ":")
    )
    missing_flags = [{"missing_unit_description": "new claim"}]
    exclusion = {
        "candidate_id": "candidate-1",
        "case_id": "case-1",
        "reason": "unit_missing_from_stage_a",
    }
    adjudication = {
        "schema_version": STAGE_B_FROZEN_UNIT_EXCLUSION_ADJUDICATION_V1,
        "candidate_id": "candidate-1",
        "case_id": "case-1",
        "status": "missing_unit_excluded_from_scoring",
        "score_scope": "frozen_units_only",
        "scoreable_unit_ids": ["unit-1"],
        "owner_comment_id": "owner-comment",
        "owner_ruling": {
            "action": "exclude_missing_unit_only",
            "candidate_id": "candidate-1",
            "case_id": "case-1",
            "frozen_unit_ids": ["unit-1"],
            "missing_unit_descriptions": ["new claim"],
        },
        "owner_ruling_sha256": "sha256:ruling",
        "raw_output_sha256": "sha256:tampered",
        "normalized_response_sha256": str(
            runner.ARTIFACT_PREFIXED_SHA256_V1.commit(
                normalized_response_json,
                domain=STAGE_B_FROZEN_UNIT_EXCLUSION_ADJUDICATION_V1,
            ).digest
        ),
        "frozen_unit_ids": ["unit-1"],
        "missing_unit_flags_sha256": runner.canonical_records_sha256(missing_flags),
        "exclusion_entry_sha256": runner.canonical_sha256(exclusion),
    }
    audit.update(
        {
            "missing_unit_flags": missing_flags,
            "frozen_unit_workflow": {
                "is_scored": False,
                "score_scope": "frozen_units_only",
                "scoreable_unit_ids": ["unit-1"],
                "exclusion": exclusion,
            },
            "frozen_unit_adjudication": adjudication,
        }
    )
    cast(dict[str, Any], audit["model_outputs"])[0]["raw_output_sha256"] = (
        "sha256:tampered"
    )
    audit_payload = runner._canonical_jsonl((audit,))  # pyright: ignore[reportPrivateUsage]
    audit_path, card_path = runner._shard_artifact_paths(  # pyright: ignore[reportPrivateUsage]
        tmp_path, "openai", None
    )
    audit_path.write_bytes(audit_payload)
    journal_path = runner._provider_attempt_journal_path(  # pyright: ignore[reportPrivateUsage]
        tmp_path, "openai"
    )
    journal_path.write_bytes(b"provider-free journal")
    card_path.write_text(
        json.dumps(
            {
                "schema_version": str(
                    runner.STAGE_B_MANIFEST_PROVIDER_SHARD_RUN_CARD_V1
                ),
                "stage": "llm-label-provider-shard",
                "status": "completed",
                "dry_run": False,
                "execute": True,
                "paid_activity_requested": True,
                "paid_activity_executed": True,
                "execution_provider": "openai",
                "model_keys": list(runner.MODEL_KEYS),
                "executed_model_keys": [runner.MODEL_KEYS[0]],
                "provider_sampling_policy": "provider_default",
                "tools_enabled": False,
                "create_only": True,
                "resumable": True,
                "max_cases": None,
                "case_count": 1,
                "unit_count": 1,
                "owner_comment_ids": ["spend", "terminal"],
                "source_commitments": {
                    "raw_prediction_units": "raw",
                    "selection": runner.CURRENT_SELECTION_SHA256,
                    "legacy_decision_texts": runner.DECISION_TEXTS_SHA256,
                    "decision_texts_current": "decision",
                    "model_registry": "registry",
                    "terminal_packet_approval": runner.TERMINAL_PACKET_APPROVAL,
                },
                "output_commitments": {
                    "audit": runner._raw_sha256(audit_payload),  # pyright: ignore[reportPrivateUsage]
                    "provider_attempt_journal": runner._source_digest(journal_path),  # pyright: ignore[reportPrivateUsage]
                },
            }
        ),
        encoding="utf-8",
    )
    result_path = runner._result_path(  # pyright: ignore[reportPrivateUsage]
        tmp_path, "openai", "candidate-1"
    )
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(result), encoding="utf-8")
    monkeypatch.setattr(runner, "EXPECTED_CASE_COUNT", 1)
    monkeypatch.setattr(runner, "EXPECTED_UNIT_COUNT", 1)
    monkeypatch.setattr(
        runner,
        "_prediction_units_by_candidate",
        lambda _: {"candidate-1": context["frozen_units"]},
    )
    monkeypatch.setattr(
        runner,
        "_verified_stage_b_decisions",
        lambda _: {
            "candidate-1": ("authenticated decision", context["decision_commitment"])
        },
    )
    monkeypatch.setattr(
        runner, "_labeling_prompt", lambda *args, **kwargs: context["prompt"]
    )
    monkeypatch.setattr(
        runner, "_validate_frozen_unit_adjudication", lambda *args, **kwargs: None
    )

    class FakeJournal:
        def __enter__(self) -> FakeJournal:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def latest_reconstruction_recovery_evidence(self) -> SimpleNamespace:
            return SimpleNamespace(normalized_response_json=normalized_response_json)

    monkeypatch.setattr(runner, "_provider_attempt_journal", lambda **_: FakeJournal())

    with pytest.raises(
        runner.StageBManifestError,
        match="raw output differs from authenticated provider journal",
    ):
        runner._validate_full_provider_shard(  # pyright: ignore[reportPrivateUsage]
            output_root=tmp_path,
            provider="openai",
            registry_entry=cast(
                Any,
                SimpleNamespace(provider="openai", registry_key=runner.MODEL_KEYS[0]),
            ),
            registry_sha256="registry",
            raw_sha256="raw",
            decision_sha256="decision",
            artifact=cast(
                Any,
                SimpleNamespace(
                    finalized_unit_envelope_sha256s={"candidate-1": "envelope"}
                ),
            ),
            selection_records=(context["selection"],),
            adapted_records=(),
            owner_comment_ids=("spend", "terminal"),
            frozen_unit_adjudications={"candidate-1": adjudication},
        )


def test_execute_provider_is_resumable_without_provider_calls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, context = _valid_result()
    output_root = tmp_path / "output"
    output_root.mkdir()
    runner._provider_attempt_journal_path(  # pyright: ignore[reportPrivateUsage]
        output_root, "openai"
    ).write_bytes(b"provider-free journal")
    artifact = cast(
        Any,
        SimpleNamespace(finalized_unit_envelope_sha256s={"candidate-1": "envelope"}),
    )
    entry = cast(
        Any,
        SimpleNamespace(provider="openai", registry_key=runner.MODEL_KEYS[0]),
    )
    monkeypatch.setattr(runner, "_validate_provider_environment", lambda _: None)
    monkeypatch.setattr(
        runner,
        "_prediction_units_by_candidate",
        lambda _: {"candidate-1": context["frozen_units"]},
    )
    monkeypatch.setattr(
        runner,
        "_verified_stage_b_decisions",
        lambda _: {
            "candidate-1": ("authenticated decision", context["decision_commitment"])
        },
    )
    monkeypatch.setattr(
        runner, "_labeling_prompt", lambda *args, **kwargs: context["prompt"]
    )
    monkeypatch.setattr(runner, "_owner_approval_ids", lambda: ("spend", "terminal"))
    provider_calls: list[dict[str, Any]] = []

    def fake_label(**kwargs: Any) -> tuple[list[Any], Any, int, int, str]:
        provider_calls.append(kwargs)
        return (
            [],
            SimpleNamespace(
                input_tokens=1,
                output_tokens=1,
                estimated_cost=0.01,
                raw_output_sha256="sha256:raw",
                metadata={"provider": "openai"},
            ),
            0,
            0,
            "sha256:" + hashlib.sha256(context["prompt"].encode()).hexdigest(),
        )

    monkeypatch.setattr(runner, "_llm_label_one_model", fake_label)

    def replay_existing(path: Path, **_: Any) -> dict[str, Any] | None:
        if not path.exists():
            return None
        return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))

    monkeypatch.setattr(runner, "_existing_result", replay_existing)
    kwargs = {
        "provider": "openai",
        "output_root": output_root,
        "raw_path": tmp_path / "raw.jsonl",
        "decision_texts_path": tmp_path / "decision.jsonl",
        "artifact": artifact,
        "selection_records": (context["selection"],),
        "adapted_records": (),
        "registry_entry": entry,
        "registry_sha256": "registry",
        "raw_sha256": "raw",
        "decision_sha256": "decision",
        "max_cases": None,
    }

    first = runner._execute_provider(**kwargs)  # pyright: ignore[reportPrivateUsage]
    second = runner._execute_provider(**kwargs)  # pyright: ignore[reportPrivateUsage]

    assert len(first) == len(second) == 1
    assert len(provider_calls) == 1
    assert (output_root / "openai-provider-shard-audit.jsonl").is_file()
    assert (output_root / "openai-provider-shard-run-card.json").is_file()


def test_execute_provider_replay_skips_provider_credentials(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, context = _valid_result()
    output_root = tmp_path / "output"
    output_root.mkdir()
    runner._provider_attempt_journal_path(  # pyright: ignore[reportPrivateUsage]
        output_root, "openai"
    ).write_bytes(b"provider-free journal")
    artifact = cast(
        Any,
        SimpleNamespace(finalized_unit_envelope_sha256s={"candidate-1": "envelope"}),
    )
    entry = cast(
        Any,
        SimpleNamespace(provider="openai", registry_key=runner.MODEL_KEYS[0]),
    )
    adjudication = {"candidate_id": "candidate-1", "provider": "openai"}
    monkeypatch.setattr(
        runner,
        "_validate_provider_environment",
        lambda _: pytest.fail("provider credentials must not be validated on replay"),
    )
    monkeypatch.setattr(
        runner, "_validate_frozen_unit_adjudication", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        runner,
        "_prediction_units_by_candidate",
        lambda _: {"candidate-1": context["frozen_units"]},
    )
    monkeypatch.setattr(
        runner,
        "_verified_stage_b_decisions",
        lambda _: {
            "candidate-1": ("authenticated decision", context["decision_commitment"])
        },
    )
    monkeypatch.setattr(
        runner, "_labeling_prompt", lambda *args, **kwargs: context["prompt"]
    )
    monkeypatch.setattr(runner, "_owner_approval_ids", lambda: ("spend", "terminal"))
    monkeypatch.setattr(runner, "_existing_result", lambda *args, **kwargs: None)

    def fake_label(**kwargs: Any) -> tuple[list[Any], Any, int, int, str]:
        assert kwargs["replay_only"] is True
        audit = cast(dict[str, Any], kwargs["frozen_unit_workflow_audit"])
        audit.update(
            {
                "frozen_unit_adjudication": adjudication,
                "frozen_unit_workflow": {
                    "is_scored": False,
                    "score_scope": "frozen_units_only",
                    "scoreable_unit_ids": ["unit-1"],
                },
            }
        )
        return (
            [],
            SimpleNamespace(
                input_tokens=1,
                output_tokens=1,
                estimated_cost=0.0,
                raw_output_sha256="sha256:raw",
                metadata={"provider": "openai"},
            ),
            0,
            1,
            "sha256:" + hashlib.sha256(context["prompt"].encode()).hexdigest(),
        )

    monkeypatch.setattr(runner, "_llm_label_one_model", fake_label)
    records = runner._execute_provider(  # pyright: ignore[reportPrivateUsage]
        provider="openai",
        output_root=output_root,
        raw_path=tmp_path / "raw.jsonl",
        decision_texts_path=tmp_path / "decision.jsonl",
        artifact=artifact,
        selection_records=(context["selection"],),
        adapted_records=(),
        registry_entry=entry,
        registry_sha256="registry",
        raw_sha256="raw",
        decision_sha256="decision",
        max_cases=None,
        frozen_unit_adjudications={"candidate-1": adjudication},
        frozen_unit_adjudications_sha256="sha256:adjudications",
    )
    assert len(records) == 1


def test_execute_provider_recovers_retained_failure_without_provider_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A corrected local normalizer may settle a failed response create-only."""

    _, context = _valid_result()
    output_root = tmp_path / "output"
    failure_path = output_root / "results/google/candidate-1.json"
    failure_path.parent.mkdir(parents=True)
    failure_payload = {
        "schema_version": str(runner.STAGE_B_MANIFEST_PROVIDER_RESULT_V1),
        "status": "failed",
        "candidate_id": "candidate-1",
        "case_id": "case-1",
        "provider": "google",
        "model_key": runner.MODEL_KEYS[1],
        "model_registry_sha256": "registry",
        "raw_prediction_units_sha256": "raw",
        "raw_candidate_envelope_sha256": "envelope",
        "decision_texts_sha256": "decision",
        "provider_sampling_policy": "provider_default",
        "tools_enabled": False,
        "error_type": runner.ADDITIONAL_ATTEMPT_FAILURE_TYPE,
        "error_message": runner.ADDITIONAL_ATTEMPT_FAILURE_MESSAGE,
    }
    original_failure = json.dumps(failure_payload, sort_keys=True).encode()
    failure_path.write_bytes(original_failure)
    journal_path = runner._provider_attempt_journal_path(  # pyright: ignore[reportPrivateUsage]
        output_root, "google"
    )
    journal_path.write_bytes(b"retained reconstruction-failed journal")

    class FakeJournal:
        has_reconstruction_failure = True
        has_validated_response = False
        has_settled_attempt = False

        def __enter__(self) -> FakeJournal:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def close(self) -> None:
            return None

        def latest_reconstruction_recovery_evidence(
            self,
        ) -> runner.ReconstructionFailureEvidence:
            return runner.ReconstructionFailureEvidence(
                attempt_ordinal=1,
                raw_response_json='{"response":"exact"}',
                normalized_response_json='{"raw_output":"{}"}',
                failure_type="LlmPipelineError",
                failure_message=runner.ADDITIONAL_ATTEMPT_FAILURE_MESSAGE,
            )

    monkeypatch.setattr(runner, "_provider_attempt_journal", lambda **_: FakeJournal())
    monkeypatch.setattr(
        runner,
        "_validate_provider_environment",
        lambda _: pytest.fail("provider credentials must not be checked"),
    )
    monkeypatch.setattr(
        runner,
        "_prediction_units_by_candidate",
        lambda _: {"candidate-1": context["frozen_units"]},
    )
    monkeypatch.setattr(
        runner,
        "_verified_stage_b_decisions",
        lambda _: {
            "candidate-1": ("authenticated decision", context["decision_commitment"])
        },
    )
    monkeypatch.setattr(
        runner, "_labeling_prompt", lambda *args, **kwargs: context["prompt"]
    )
    captured: dict[str, Any] = {}

    def fake_label(**kwargs: Any) -> tuple[list[Any], Any, int, int, str]:
        captured.update(kwargs)
        return (
            [],
            SimpleNamespace(
                input_tokens=123,
                output_tokens=456,
                estimated_cost=0.0,
                raw_output_sha256="sha256:retained",
                metadata={"provider": "google"},
            ),
            0,
            0,
            "sha256:" + hashlib.sha256(context["prompt"].encode()).hexdigest(),
        )

    monkeypatch.setattr(runner, "_llm_label_one_model", fake_label)

    records = runner._execute_provider(  # pyright: ignore[reportPrivateUsage]
        provider="google",
        output_root=output_root,
        raw_path=tmp_path / "raw.jsonl",
        decision_texts_path=tmp_path / "decision.jsonl",
        artifact=cast(
            Any,
            SimpleNamespace(
                finalized_unit_envelope_sha256s={"candidate-1": "envelope"}
            ),
        ),
        selection_records=(context["selection"],),
        adapted_records=(),
        registry_entry=cast(
            Any,
            SimpleNamespace(provider="google", registry_key=runner.MODEL_KEYS[1]),
        ),
        registry_sha256="registry",
        raw_sha256="raw",
        decision_sha256="decision",
        max_cases=None,
    )

    assert len(records) == 1
    assert captured["replay_only"] is True
    assert failure_path.read_bytes() == original_failure
    recovered_path = output_root / "results/google/candidate-1.recovered.json"
    recovered = json.loads(recovered_path.read_text(encoding="utf-8"))
    assert recovered["status"] == "succeeded"


def test_execute_provider_isolates_sequential_provider_journals(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Provider shards may share an output root but never an attempt journal."""

    _, context = _valid_result()
    output_root = tmp_path / "output"
    output_root.mkdir()
    artifact = cast(
        Any,
        SimpleNamespace(finalized_unit_envelope_sha256s={"candidate-1": "envelope"}),
    )
    monkeypatch.setattr(runner, "_validate_provider_environment", lambda _: None)
    monkeypatch.setattr(
        runner,
        "_prediction_units_by_candidate",
        lambda _: {"candidate-1": context["frozen_units"]},
    )
    monkeypatch.setattr(
        runner,
        "_verified_stage_b_decisions",
        lambda _: {
            "candidate-1": ("authenticated decision", context["decision_commitment"])
        },
    )
    monkeypatch.setattr(
        runner, "_labeling_prompt", lambda *args, **kwargs: context["prompt"]
    )
    monkeypatch.setattr(runner, "_owner_approval_ids", lambda: ("spend", "terminal"))
    monkeypatch.setattr(runner, "_existing_result", lambda *args, **kwargs: None)
    provider_calls: list[tuple[str, Path]] = []

    def fake_label(**kwargs: Any) -> tuple[list[Any], Any, int, int, str]:
        provider = kwargs["registry_entry"].provider
        journal_path = cast(Path, kwargs["provider_journal_path"])
        journal_path.write_bytes(f"{provider} provider-free journal".encode())
        provider_calls.append((provider, journal_path))
        return (
            [],
            SimpleNamespace(
                input_tokens=1,
                output_tokens=1,
                estimated_cost=0.01,
                raw_output_sha256="sha256:raw",
                metadata={"provider": provider},
            ),
            0,
            0,
            "sha256:" + hashlib.sha256(context["prompt"].encode()).hexdigest(),
        )

    monkeypatch.setattr(runner, "_llm_label_one_model", fake_label)

    for provider, model_key in zip(
        ("openai", "google"), runner.MODEL_KEYS, strict=True
    ):
        runner._execute_provider(  # pyright: ignore[reportPrivateUsage]
            provider=provider,
            output_root=output_root,
            raw_path=tmp_path / "raw.jsonl",
            decision_texts_path=tmp_path / "decision.jsonl",
            artifact=artifact,
            selection_records=(context["selection"],),
            adapted_records=(),
            registry_entry=cast(
                Any,
                SimpleNamespace(provider=provider, registry_key=model_key),
            ),
            registry_sha256="registry",
            raw_sha256="raw",
            decision_sha256="decision",
            max_cases=None,
        )

    assert [provider for provider, _ in provider_calls] == ["openai", "google"]
    assert [path.name for _, path in provider_calls] == [
        "provider-attempts-openai.sqlite3",
        "provider-attempts-google.sqlite3",
    ]
    assert not (output_root / "provider-attempts.sqlite3").exists()
    for provider in ("openai", "google"):
        card = json.loads(
            (output_root / f"{provider}-provider-shard-run-card.json").read_text(
                encoding="utf-8"
            )
        )
        journal_path = runner._provider_attempt_journal_path(  # pyright: ignore[reportPrivateUsage]
            output_root, provider
        )
        assert card["output_commitments"]["provider_attempt_journal"] == (
            runner._source_digest(journal_path)  # pyright: ignore[reportPrivateUsage]
        )


def test_execute_provider_records_failure_without_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, context = _valid_result()
    output_root = tmp_path / "output"
    output_root.mkdir()
    artifact = cast(
        Any,
        SimpleNamespace(finalized_unit_envelope_sha256s={"candidate-1": "envelope"}),
    )
    entry = cast(
        Any,
        SimpleNamespace(provider="openai", registry_key=runner.MODEL_KEYS[0]),
    )
    monkeypatch.setattr(runner, "_validate_provider_environment", lambda _: None)
    monkeypatch.setattr(
        runner,
        "_prediction_units_by_candidate",
        lambda _: {"candidate-1": context["frozen_units"]},
    )
    monkeypatch.setattr(
        runner,
        "_verified_stage_b_decisions",
        lambda _: {
            "candidate-1": ("authenticated decision", context["decision_commitment"])
        },
    )
    monkeypatch.setattr(
        runner, "_labeling_prompt", lambda *args, **kwargs: context["prompt"]
    )
    monkeypatch.setattr(runner, "_existing_result", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        runner,
        "_llm_label_one_model",
        lambda **kwargs: (_ for _ in ()).throw(
            RuntimeError("synthetic provider failure")
        ),
    )
    with pytest.raises(RuntimeError, match="synthetic provider failure"):
        runner._execute_provider(  # pyright: ignore[reportPrivateUsage]
            provider="openai",
            output_root=output_root,
            raw_path=tmp_path / "raw.jsonl",
            decision_texts_path=tmp_path / "decision.jsonl",
            artifact=artifact,
            selection_records=(context["selection"],),
            adapted_records=(),
            registry_entry=entry,
            registry_sha256="registry",
            raw_sha256="raw",
            decision_sha256="decision",
            max_cases=1,
        )
    failure = json.loads(
        (output_root / "results/openai/candidate-1.json").read_text(encoding="utf-8")
    )
    assert failure["status"] == "failed"
    assert failure["error_message"] == "synthetic provider failure"


def test_approved_retry_preserves_attempt_one_failure_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, context = _valid_result()
    candidate_id = "candidate-repair-openai"
    context["selection"]["candidate_id"] = candidate_id
    output_root = tmp_path / "output"
    failure_path = output_root / "results/openai" / f"{candidate_id}.json"
    failure_path.parent.mkdir(parents=True)
    failure_payload = {
        "schema_version": str(runner.STAGE_B_MANIFEST_PROVIDER_RESULT_V1),
        "status": "failed",
        "candidate_id": candidate_id,
        "case_id": "case-1",
        "provider": "openai",
        "model_key": runner.MODEL_KEYS[0],
        "model_registry_sha256": "registry",
        "raw_prediction_units_sha256": "raw",
        "raw_candidate_envelope_sha256": "envelope",
        "decision_texts_sha256": "decision",
        "provider_sampling_policy": "provider_default",
        "tools_enabled": False,
        "error_type": "LlmResponseValidationError",
        "error_message": "invalid amendment semantics",
    }
    failure_path.write_text(json.dumps(failure_payload), encoding="utf-8")
    before = failure_path.read_bytes()
    artifact = cast(
        Any,
        SimpleNamespace(finalized_unit_envelope_sha256s={candidate_id: "envelope"}),
    )
    entry = cast(
        Any,
        SimpleNamespace(
            provider="openai",
            registry_key=runner.MODEL_KEYS[0],
            context_limit=400_000,
            max_output_tokens=128_000,
            input_token_price=0.75,
            output_token_price=4.5,
            long_context_surcharge=None,
        ),
    )
    evidence = runner.ReconstructionFailureEvidence(
        attempt_ordinal=1,
        raw_response_json='{"response":"exact"}',
        normalized_response_json='{"raw_output":"{\\"bad\\":true}"}',
        failure_type="ValueError",
        failure_message="invalid amendment semantics",
    )
    monkeypatch.setattr(runner, "_validate_provider_environment", lambda _: None)
    monkeypatch.setattr(
        runner,
        "_prediction_units_by_candidate",
        lambda _: {candidate_id: context["frozen_units"]},
    )
    monkeypatch.setattr(
        runner,
        "_verified_stage_b_decisions",
        lambda _: {
            candidate_id: ("authenticated decision", context["decision_commitment"])
        },
    )
    monkeypatch.setattr(
        runner, "_labeling_prompt", lambda *args, **kwargs: context["prompt"]
    )
    monkeypatch.setattr(runner, "_owner_approval_ids", lambda: ("spend", "terminal"))
    monkeypatch.setattr(
        runner, "_reconstruction_failure_evidence", lambda **_: evidence
    )
    captured: dict[str, Any] = {}

    def fake_label(**kwargs: Any) -> tuple[list[Any], Any, int, int, str]:
        captured.update(kwargs)
        cast(Path, kwargs["provider_journal_path"]).write_bytes(
            b"provider-free journal"
        )
        return (
            [],
            SimpleNamespace(
                input_tokens=1,
                output_tokens=1,
                estimated_cost=0.01,
                raw_output_sha256="sha256:raw",
                metadata={"provider": "openai"},
            ),
            0,
            0,
            "sha256:" + hashlib.sha256(kwargs["prompt"].encode()).hexdigest(),
        )

    monkeypatch.setattr(runner, "_llm_label_one_model", fake_label)
    runner._execute_provider(  # pyright: ignore[reportPrivateUsage]
        provider="openai",
        output_root=output_root,
        raw_path=tmp_path / "raw.jsonl",
        decision_texts_path=tmp_path / "decision.jsonl",
        artifact=artifact,
        selection_records=(context["selection"],),
        adapted_records=(),
        registry_entry=entry,
        registry_sha256="registry",
        raw_sha256="raw",
        decision_sha256="decision",
        max_cases=None,
        additional_attempt_candidate=candidate_id,
        owner_comment_ids=(
            "spend",
            "terminal",
            runner.ADDITIONAL_ATTEMPT_APPROVAL_COMMENT_ID,
        ),
    )

    assert failure_path.read_bytes() == before
    retry_path = output_root / "results/openai" / f"{candidate_id}.attempt-2.json"
    assert retry_path.is_file()
    assert captured["max_provider_attempts"] == 1
    assert captured["registry_entry"] is entry
    assert captured["provider_logical_call_scope"] == (
        runner.provider_prompt_logical_call_scope(captured["prompt"])
    )
    repair_payload = json.loads(captured["prompt"])
    assert repair_payload["original_authenticated_prompt"] == context["prompt"]
    assert repair_payload["original_raw_submission"] == '{"bad":true}'
    assert repair_payload["validation_error"] == {
        "type": "ValueError",
        "message": "invalid amendment semantics",
    }
    run_card = json.loads(
        (output_root / "openai-provider-shard-run-card.json").read_text()
    )
    assert run_card["owner_comment_ids"] == [
        "spend",
        "terminal",
        runner.ADDITIONAL_ATTEMPT_APPROVAL_COMMENT_ID,
    ]

    failed_attempt_two = dict(failure_payload)
    failed_attempt_two["error_message"] = "repair remained invalid"
    retry_path.write_text(json.dumps(failed_attempt_two), encoding="utf-8")
    monkeypatch.setattr(
        runner,
        "_validate_provider_environment",
        lambda _: pytest.fail("terminal repair must stop before credentials"),
    )
    monkeypatch.setattr(
        runner,
        "_llm_label_one_model",
        lambda **_: pytest.fail("terminal repair must not make a third call"),
    )
    with pytest.raises(
        runner.StageBManifestError,
        match="existing failed result requires frozen-unit adjudication",
    ):
        runner._execute_provider(  # pyright: ignore[reportPrivateUsage]
            provider="openai",
            output_root=output_root,
            raw_path=tmp_path / "raw.jsonl",
            decision_texts_path=tmp_path / "decision.jsonl",
            artifact=artifact,
            selection_records=(context["selection"],),
            adapted_records=(),
            registry_entry=entry,
            registry_sha256="registry",
            raw_sha256="raw",
            decision_sha256="decision",
            max_cases=None,
            additional_attempt_candidate=candidate_id,
            owner_comment_ids=(
                "spend",
                "terminal",
                runner.ADDITIONAL_ATTEMPT_APPROVAL_COMMENT_ID,
            ),
        )
    assert failure_path.read_bytes() == before


@pytest.mark.parametrize(
    ("error_type", "error_message"),
    [
        ("TimeoutError", "provider request timed out"),
        ("LlmResponseValidationError", "provider response was not valid JSON"),
        ("LlmResponseValidationError", "supporting excerpt was not authenticated"),
    ],
)
def test_retry_rejects_nonapproved_failure_receipt(
    tmp_path: Path,
    error_type: str,
    error_message: str,
) -> None:
    failure_path = tmp_path / "failed.json"
    failure_path.write_text(
        json.dumps(
            {
                "schema_version": str(runner.STAGE_B_MANIFEST_PROVIDER_RESULT_V1),
                "status": "failed",
                "candidate_id": "candidate-1",
                "case_id": "case-1",
                "provider": "openai",
                "model_key": runner.MODEL_KEYS[0],
                "model_registry_sha256": "registry",
                "raw_prediction_units_sha256": "raw",
                "raw_candidate_envelope_sha256": "envelope",
                "decision_texts_sha256": "decision",
                "provider_sampling_policy": "provider_default",
                "tools_enabled": False,
                "error_type": error_type,
                "error_message": error_message,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        runner.StageBManifestError,
        match="not the approved citation-validation failure",
    ):
        runner._existing_failure_result(  # pyright: ignore[reportPrivateUsage]
            failure_path,
            candidate_id="candidate-1",
            provider="openai",
            model_key=runner.MODEL_KEYS[0],
            raw_sha256="raw",
            raw_candidate_envelope_sha256="envelope",
            decision_sha256="decision",
            registry_sha256="registry",
            selection={"case_id": "case-1"},
        )


def test_run_dispatches_merge_plan_and_execute_modes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    raw_path = tmp_path / "raw.jsonl"
    selection_path = tmp_path / "selection.jsonl"
    decision_path = tmp_path / "decision.jsonl"
    registry_path = tmp_path / "registry.json"
    store_root = tmp_path / "store"
    entries = (
        cast(Any, SimpleNamespace(provider="openai", registry_key="openai:model")),
    )
    artifact = cast(Any, SimpleNamespace(decision_texts_sha256="decision"))
    selection = {"candidate_id": "candidate-1", "case_id": "case-1"}
    monkeypatch.setattr(runner, "_owner_approval_ids", lambda: ("spend", "terminal"))
    monkeypatch.setattr(
        runner,
        "_validate_raw_inputs",
        lambda _: ({"candidate_id": "candidate-1", "prediction_units": [{}]},),
    )
    monkeypatch.setattr(runner, "_validate_registry", lambda _: entries)
    monkeypatch.setattr(
        runner,
        "_source_digest",
        lambda path: (
            runner.RAW_UNITS_SHA256
            if path == raw_path.resolve()
            else runner.STAGE_B_REGISTRY_SHA256
            if path == registry_path.resolve()
            else runner.DECISION_TEXTS_SHA256
        ),
    )
    monkeypatch.setattr(
        runner,
        "_verified_inputs",
        lambda **_: (artifact, (selection,), ()),
    )
    merge_calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        runner,
        "_merge_provider_shards",
        lambda **kwargs: merge_calls.append(kwargs) or {"status": "merged"},
    )
    execute_calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        runner,
        "_execute_provider",
        lambda **kwargs: (
            execute_calls.append(kwargs) or ({"candidate_id": "candidate-1"},)
        ),
    )

    def args(
        output_root: Path, *, merge: bool, execute: bool, provider: str | None
    ) -> Any:
        return SimpleNamespace(
            raw_prediction_units=raw_path,
            selection=selection_path,
            decision_texts=decision_path,
            decision_store_root=store_root,
            model_registry=registry_path,
            output_root=output_root,
            provider=provider,
            execute=execute,
            merge=merge,
            max_cases=1,
        )

    assert (
        runner.run(args(tmp_path / "merge", merge=True, execute=False, provider=None))
        == 0
    )
    assert merge_calls[-1]["owner_comment_ids"] == ("spend", "terminal")
    capsys.readouterr()

    plan_root = tmp_path / "plan"
    assert runner.run(args(plan_root, merge=False, execute=False, provider=None)) == 0
    assert (
        json.loads((plan_root / "dry-run-plan.json").read_text())["estimated_cost_usd"]
        == 15.0
    )
    capsys.readouterr()

    execute_root = tmp_path / "execute"
    assert (
        runner.run(args(execute_root, merge=False, execute=True, provider="openai"))
        == 0
    )
    assert execute_calls[-1]["max_cases"] == 1
    assert capsys.readouterr().out


def test_merge_wraps_consensus_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entries = tuple(
        cast(
            Any,
            SimpleNamespace(provider=provider, registry_key=model_key),
        )
        for provider, model_key in zip(
            ("openai", "google"), runner.MODEL_KEYS, strict=True
        )
    )
    monkeypatch.setattr(
        runner,
        "_validate_full_provider_shard",
        lambda **kwargs: (
            ({"candidate_id": kwargs["provider"]},),
            {"provider": kwargs["provider"]},
        ),
    )
    monkeypatch.setattr(
        runner,
        "merge_llm_label_provider_shards",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("synthetic merge failure")),
    )
    with pytest.raises(runner.StageBManifestError, match="synthetic merge failure"):
        runner._merge_provider_shards(  # pyright: ignore[reportPrivateUsage]
            output_root=tmp_path,
            artifact=cast(Any, SimpleNamespace()),
            selection_records=(),
            adapted_records=(),
            registry_entries=entries,
            owner_comment_ids=(),
            registry_sha256="registry",
            raw_sha256="raw",
            decision_sha256="decision",
        )


def test_verified_inputs_builds_replacement_decision_manifest_provider_free(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selection = {
        "candidate_id": "candidate-1",
        "case_id": "case-1",
        "decision_date": "2026-08-01",
        "documents": [
            {
                "source_document_id": "source-1",
                "contains_target_outcome": True,
                "model_visible": False,
                "document_role": "decision",
            }
        ],
    }
    raw_records = ({"candidate_id": "candidate-1", "case_id": "case-1"},)
    adapted_records = (
        {
            "candidate_id": "candidate-1",
            "case_id": "case-1",
            "prediction_units": [{"unit_id": "unit-1"}],
        },
    )
    monkeypatch.setattr(runner, "EXPECTED_CASE_COUNT", 1)
    monkeypatch.setattr(
        runner,
        "REPLACEMENT_SOURCE_COMMITMENTS",
        {
            "source-1": {
                "metadata_sha256": "metadata",
                "markdown_sha256": "markdown",
                "source_sha256": "source",
            }
        },
    )
    monkeypatch.setattr(
        runner,
        "_read_regular",
        lambda path, label: b"legacy" if label == "decision texts" else b"selection",
    )
    monkeypatch.setattr(
        runner,
        "_raw_sha256",
        lambda payload: (
            runner.DECISION_TEXTS_SHA256
            if payload == b"legacy"
            else runner.CURRENT_SELECTION_SHA256
            if payload == b"selection"
            else "digest-" + str(len(payload))
        ),
    )
    monkeypatch.setattr(
        runner,
        "_jsonl",
        lambda payload, label: (
            (
                {
                    "candidate_id": "legacy-other",
                    "case_id": "other-case",
                    "entered_date": "2026-08-01",
                    "text": "unused legacy text",
                },
            )
            if label == "decision texts"
            else (selection,)
        ),
    )
    monkeypatch.setattr(runner, "_manifest_units", lambda _: adapted_records)
    monkeypatch.setattr(
        runner,
        "_current_decision_record",
        lambda **_: {
            "candidate_id": "candidate-1",
            "case_id": "case-1",
            "entered_date": "2026-08-01",
            "text": "authenticated replacement decision",
        },
    )
    writes: list[Path] = []
    monkeypatch.setattr(
        runner, "_write_create_only", lambda path, payload: writes.append(path)
    )
    monkeypatch.setattr(runner, "_verified_stage_b_decisions", lambda _: {})

    artifact, selected, adapted = runner._verified_inputs(  # pyright: ignore[reportPrivateUsage]
        raw_path=tmp_path / "raw.jsonl",
        decision_texts_path=tmp_path / "decision.jsonl",
        selection_path=tmp_path / "selection.jsonl",
        decision_store_root=tmp_path / "store",
        adapted_path=tmp_path / "adapted.jsonl",
        raw_records=raw_records,
    )

    assert selected == (selection,)
    assert adapted == adapted_records
    assert artifact.records[0]["text"] == "authenticated replacement decision"
    assert artifact.input_commitments["selection_sha256"] == (
        runner.CURRENT_SELECTION_SHA256
    )
    assert {path.name for path in writes} == {
        "adapted.jsonl",
        "decision-texts-current.jsonl",
        "decision-texts-current-manifest.json",
        "decision-texts-current-run-card.json",
    }


def test_manifest_units_adapts_each_authenticated_raw_unit() -> None:
    raw_records = (
        {
            "candidate_id": "candidate-1",
            "case_id": "case-1",
            "prediction_units": [
                {"unit_id": "unit-1", "claim": "first"},
                {"unit_id": "unit-2", "claim": "second"},
            ],
        },
    )

    adapted = runner._manifest_units(raw_records)  # pyright: ignore[reportPrivateUsage]

    assert len(adapted) == 1
    envelope = adapted[0]
    assert envelope["status"] == "finalized"
    assert envelope["candidate_id"] == "candidate-1"
    assert envelope["case_id"] == "case-1"
    assert envelope["exclusion"] is None
    units = cast(list[dict[str, Any]], envelope["prediction_units"])
    assert [unit["unit_id"] for unit in units] == ["unit-1", "unit-2"]
    assert all(unit["disposition"] == "ACCEPT" for unit in units)
    assert all(unit["adjudication_id"].startswith("automatic:") for unit in units)
    assert all(unit["adjudication_sha256"] is None for unit in units)


def test_validate_raw_inputs_accepts_owner_committed_complete_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_payload = runner._canonical_jsonl(  # pyright: ignore[reportPrivateUsage]
        (
            {
                "candidate_id": "candidate-1",
                "case_id": "case-1",
                "prediction_units": [
                    {"unit_id": "unit-1"},
                    {"unit_id": "unit-2"},
                ],
            },
        )
    )
    raw_path = tmp_path / "prediction-units.jsonl"
    raw_path.write_bytes(raw_payload)
    monkeypatch.setattr(runner, "EXPECTED_CASE_COUNT", 1)
    monkeypatch.setattr(runner, "EXPECTED_UNIT_COUNT", 2)
    monkeypatch.setattr(runner, "_raw_sha256", lambda _: runner.RAW_UNITS_SHA256)

    records = runner._validate_raw_inputs(raw_path)  # pyright: ignore[reportPrivateUsage]

    assert records == (
        {
            "candidate_id": "candidate-1",
            "case_id": "case-1",
            "prediction_units": [
                {"unit_id": "unit-1"},
                {"unit_id": "unit-2"},
            ],
        },
    )


def test_validate_registry_accepts_exact_safe_stage_b_entries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry_path = tmp_path / "stage-b-registry.json"
    registry_path.write_bytes(b"owner-committed-registry")
    entries = tuple(
        SimpleNamespace(
            provider=provider,
            registry_key=model_key,
            network_disabled=True,
            search_disabled=True,
            tool_policy=SimpleNamespace(value="no_tools"),
        )
        for provider, model_key in zip(
            ("openai", "google"), runner.MODEL_KEYS, strict=True
        )
    )
    monkeypatch.setattr(runner, "_raw_sha256", lambda _: runner.STAGE_B_REGISTRY_SHA256)
    monkeypatch.setattr(
        runner,
        "load_model_registry",
        lambda _: SimpleNamespace(entries=entries),
    )

    validated = runner._validate_registry(registry_path)  # pyright: ignore[reportPrivateUsage]

    assert validated == entries


def test_current_decision_record_authenticates_replacement_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_document_id = "source-1"
    metadata_bytes = b'{"authenticated":"metadata"}\n'
    markdown_bytes = b"A first-written disposition.\n"
    source_bytes = b"authenticated PDF bytes"
    source_path = tmp_path / "source.pdf"
    source_path.write_bytes(source_bytes)
    store_root = tmp_path / "decision-store"
    store_root.mkdir()
    (store_root / f"{source_document_id}.md").write_bytes(markdown_bytes)
    metadata = {
        "candidate_id": "candidate-1",
        "source_document_id": source_document_id,
        "status": "succeeded",
        "extracted_text": {
            "text_sha256": "markdown",
            "extraction_method": "fixture-parser",
        },
        "input_path": str(source_path),
        "source_sha256": "source",
        "parser_config": {"parser_revision": "fixture-revision"},
    }
    metadata_bytes = json.dumps(metadata).encode("utf-8")
    (store_root / f"{source_document_id}.metadata.json").write_bytes(metadata_bytes)
    selection = {
        "candidate_id": "candidate-1",
        "case_id": "case-1",
        "decision_date": "2026-08-01",
        "documents": [
            {
                "source_document_id": source_document_id,
                "contains_target_outcome": True,
                "model_visible": False,
                "document_role": "decision",
                "docket_entry_number": 42,
            }
        ],
    }
    monkeypatch.setattr(
        runner,
        "REPLACEMENT_SOURCE_COMMITMENTS",
        {
            source_document_id: {
                "metadata_sha256": "metadata",
                "markdown_sha256": "markdown",
                "source_sha256": "source",
            }
        },
    )

    def fake_digest(payload: bytes) -> str:
        return {
            metadata_bytes: "metadata",
            markdown_bytes: "markdown",
            source_bytes: "source",
        }[payload]

    monkeypatch.setattr(runner, "_raw_sha256", fake_digest)

    record = runner._current_decision_record(  # pyright: ignore[reportPrivateUsage]
        selection=selection,
        decision_store_root=store_root,
        input_commitments={"selection_sha256": "selection"},
    )

    assert record == {
        "schema_version": runner.DECISION_TEXT_SCHEMA_VERSION,
        "candidate_id": "candidate-1",
        "case_id": "case-1",
        "document_id": "candidate-1-entry-42-decision",
        "source_document_id": source_document_id,
        "document_role": "decision",
        "docket_entry_number": 42,
        "entered_date": "2026-08-01",
        "is_first_written_disposition": True,
        "contains_target_outcome": True,
        "model_visible": False,
        "extraction_method": "fixture-parser",
        "parser_revision": "fixture-revision",
        "source_byte_count": len(source_bytes),
        "source_sha256": "source",
        "markdown_sha256": "markdown",
        "text_sha256": "markdown",
        "text": markdown_bytes.decode(),
        "input_commitments": {"selection_sha256": "selection"},
    }
