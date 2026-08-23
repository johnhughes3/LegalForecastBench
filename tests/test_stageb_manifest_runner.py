"""Focused authority checks for the additive Stage B manifest runner."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from legalforecast.evals import stageb_manifest_runner as runner
from legalforecast.labeling import AmendmentClass, UnitResolution
from legalforecast.labeling.label_outcomes import OutcomeCitation, OutcomeLabel


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
