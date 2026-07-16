from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import legalforecast.labeling.llm_pipeline as llm_pipeline
import pytest
from legalforecast import cli
from legalforecast.cli import (
    CommandError,
    _require_complete_registry_panel,
    _require_exact_model_disjoint_judges,
    _require_explicit_unique_model_keys,
    main,
)
from legalforecast.evals.inspect_task import SolverResponse
from legalforecast.evals.model_registry import load_model_registry
from legalforecast.ingestion.mistral_markdown_parser import EXPECTED_PARSER_REVISION
from legalforecast.labeling.provider_journal import (
    ProviderAttemptJournal,
    ProviderCallIdentity,
)
from legalforecast.unitization import ChallengeScope, PredictionUnit, SourceCitation
from legalforecast.unitization.review import apply_unitization_reviews
from pytest import MonkeyPatch, raises

JsonRecord = dict[str, Any]


def _stub_downstream_decision_artifact(
    monkeypatch: MonkeyPatch,
    decision_texts_path: Path,
    *,
    replace_after_verification: bool = False,
) -> list[str]:
    monkeypatch.setattr(cli, "require_finalized_envelopes", lambda records: records)
    authenticated_records = tuple(_read_jsonl(decision_texts_path))

    class _Artifact:
        records = authenticated_records

        def verify_stage_b_audit_commitments(self, records: object) -> None:
            del records

    def verify(**kwargs: object) -> _Artifact:
        del kwargs
        if replace_after_verification:
            _write_jsonl(
                decision_texts_path,
                [
                    {
                        "document_id": "decision",
                        "entered_date": "2026-05-18",
                        "text": "The authenticated decision was replaced.",
                    }
                ],
            )
        return _Artifact()

    monkeypatch.setattr(cli, "verify_decision_text_artifact", verify)
    return [
        "--selection",
        str(decision_texts_path),
        "--parser-manifest",
        str(decision_texts_path),
        "--prediction-units",
        str(decision_texts_path),
        "--decision-texts-manifest",
        str(decision_texts_path),
        "--decision-texts-run-card",
        str(decision_texts_path),
        "--markdown-root",
        str(decision_texts_path.parent),
    ]


def _provider_caps_path(root: Path) -> Path:
    path = root / "provider-cycle-caps.json"
    if not path.exists():
        _write_json(
            path,
            {
                "schema_version": "legalforecast.provider_cycle_caps.v1",
                "cycle_id": "test-cycle",
                "providers": [
                    {
                        "provider": "openai",
                        "cycle_reservation_cap_usd": "10.00",
                        "external_spend_limit_usd": "20.00",
                        "external_limit_scope": "test account",
                        "external_limit_source": "test fixture",
                        "verified_at": "2026-07-12T16:00:00Z",
                    }
                ],
            },
        )
    return path


def _evaluated_registry_path(root: Path) -> Path:
    path = root / "evaluated-registry.json"
    if not path.exists():
        record = _registry_record()
        record["model_id"] = "gpt-evaluated"
        record["model_version_or_snapshot"] = "gpt-evaluated-2026-06-30"
        _write_json(path, [record])
    return path


def _stub_authenticated_stage_a_lineage(
    monkeypatch: MonkeyPatch,
    *,
    selection_path: Path,
    parser_path: Path,
    markdown_root: Path,
    registry_path: Path,
    caps_path: Path,
    provider_journal_path: Path,
) -> list[str]:
    fixture_lineage_paths = {
        name: selection_path.parent / f"fixture-{name.replace('_', '-')}.json"
        for name in (
            "selection_run_card",
            "download_manifest",
            "disclosure_clearance",
            "materialization_run_card",
            "parse_requests",
            "parser_run_card",
        )
    }
    for path in fixture_lineage_paths.values():
        _write_json(path, {})
    entry, registry_sha256 = cli._registry_entry_for_key(
        registry_path, "openai:gpt-test"
    )
    caps = cli.load_provider_cycle_caps(caps_path)
    markdown_tree = {
        path.relative_to(markdown_root).as_posix(): {
            "path": str(path.resolve()),
            "sha256": cli._path_sha256(path),
            "byte_count": path.stat().st_size,
        }
        for path in sorted(markdown_root.rglob("*.md"))
    }
    lineage = cli._StageAUnitizationLineage(
        selection_records=tuple(_read_jsonl(selection_path)),
        parser_records=tuple(_read_jsonl(parser_path)),
        registry_entry=entry,
        registry_sha256=registry_sha256,
        provider_caps=caps,
        provider_caps_sha256=cli._path_sha256(caps_path),
        provider_journal_path=provider_journal_path,
        document_root=markdown_root,
        markdown_root=markdown_root,
        cohort_cycle_id=caps.cycle_id,
        input_paths=(
            selection_path,
            parser_path,
            markdown_root,
            registry_path,
            caps_path,
            provider_journal_path,
        ),
        input_commitments={
            "selection": cli._stage_a_file_commitment(selection_path),
            **{
                name: cli._stage_a_file_commitment(path)
                for name, path in fixture_lineage_paths.items()
            },
            "parser_manifest": cli._stage_a_file_commitment(parser_path),
            "model_registry": cli._stage_a_file_commitment(registry_path),
            "provider_cycle_caps": cli._stage_a_file_commitment(caps_path),
            "document_tree": {},
            "markdown_tree": markdown_tree,
        },
        markdown_tree=markdown_tree,
    )
    monkeypatch.setattr(
        cli,
        "_verify_stage_a_unitization_lineage",
        lambda *args, **kwargs: lineage,
    )
    return ["--provider-journal", str(provider_journal_path)]


def _stub_authenticated_finalized_provider_chain(
    monkeypatch: MonkeyPatch,
    *,
    selection_path: Path,
    parser_path: Path,
    markdown_root: Path,
    registry_path: Path,
    caps_path: Path,
    provider_journal_path: Path,
    finalized_units_path: Path,
) -> list[str]:
    entry = load_model_registry(registry_path).entries[0]
    caps = cli.load_provider_cycle_caps(caps_path)
    registry_sha = cli._path_sha256(registry_path).removeprefix("sha256:")
    if not provider_journal_path.exists():
        ProviderAttemptJournal(
            provider_journal_path,
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
            provider_cycle_caps_sha256=cli._path_sha256(caps_path),
        ).close()
    unit_card = finalized_units_path.parent / "fixture-unitization-run-card.json"
    structural_card = (
        finalized_units_path.parent / "fixture-structural-review-run-card.json"
    )
    apply_card = finalized_units_path.parent / "fixture-apply-run-card.json"
    review_queue = finalized_units_path.parent / "fixture-review-queue.jsonl"
    for path in (unit_card, structural_card, apply_card):
        _write_json(path, {})
    _write_jsonl(review_queue, [])
    lineage = cli._StageAUnitizationLineage(
        selection_records=tuple(_read_jsonl(selection_path)),
        parser_records=tuple(_read_jsonl(parser_path)),
        registry_entry=entry,
        registry_sha256=registry_sha,
        provider_caps=caps,
        provider_caps_sha256=cli._path_sha256(caps_path),
        provider_journal_path=provider_journal_path,
        document_root=markdown_root,
        markdown_root=markdown_root,
        cohort_cycle_id=caps.cycle_id,
        input_paths=(),
        input_commitments={},
        markdown_tree={},
    )
    monkeypatch.setattr(
        cli,
        "_verify_finalized_stage_a_provider_chain",
        lambda *args, **kwargs: (lineage, unit_card, review_queue),
    )
    monkeypatch.setattr(cli, "_verify_stage_a_review_run_card", lambda *a, **k: None)
    return [
        "--llm-unitization-run-card",
        str(unit_card),
        "--llm-review-stage-a-run-card",
        str(structural_card),
        "--unitization-review-run-card",
        str(apply_card),
        "--provider-journal",
        str(provider_journal_path),
    ]


def _settle_fixture_unitization_attempt(
    response: SolverResponse, kwargs: Mapping[str, Any]
) -> SolverResponse:
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


def test_llm_label_requires_iso_first_written_disposition_date() -> None:
    selection = _selection_record()
    del selection["decision_date"]
    with raises(
        llm_pipeline.LlmPipelineError,
        match="missing the first written MTD disposition",
    ):
        llm_pipeline._decision_date(selection)

    selection["decision_date"] = "docket-entry-16"
    with raises(llm_pipeline.LlmPipelineError, match="must be an ISO date"):
        llm_pipeline._decision_date(selection)


def test_stage_b_judges_must_be_exact_model_disjoint_from_evaluated_registry(
    tmp_path: Path,
) -> None:
    registry_path = tmp_path / "registry.json"
    _write_json(registry_path, [_registry_record()])
    [judge] = load_model_registry(registry_path).entries

    with raises(CommandError, match="not exact-model disjoint"):
        _require_exact_model_disjoint_judges(
            [judge], evaluated_model_registry_path=registry_path
        )


@pytest.mark.parametrize("keys", [("   ",), ("openai:gpt-test", "openai:gpt-test")])
def test_stage_b_judge_keys_must_be_explicit_and_unique(keys: tuple[str, ...]) -> None:
    with raises(CommandError):
        _require_explicit_unique_model_keys(keys)


def test_stage_b_must_select_complete_dedicated_judge_registry(
    tmp_path: Path,
) -> None:
    registry_path = tmp_path / "registry.json"
    first = _registry_record()
    second = {**first, "model_id": "gpt-b", "model_version_or_snapshot": "gpt-b"}
    _write_json(registry_path, [first, second])
    [selected, _] = load_model_registry(registry_path).entries

    with raises(CommandError, match="every judge"):
        _require_complete_registry_panel([selected], model_registry_path=registry_path)


def test_acquisition_llm_unitize_and_label_validate_registry_outputs(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    output_root = tmp_path / "acquisition"
    markdown_root = output_root / "markdown"
    _write_markdown(markdown_root / "cand-1" / "complaint.md", "Count I: 10(b).")
    _write_markdown(
        markdown_root / "cand-1" / "mtd.md",
        "Defendants move to dismiss Count I under Rule 12(b)(6).",
    )
    _write_markdown(
        markdown_root / "cand-1" / "decision.md",
        "The motion to dismiss Count I is granted without leave to amend.",
    )
    selection_path = tmp_path / "selection.jsonl"
    parser_path = tmp_path / "parser.jsonl"
    registry_path = tmp_path / "registry.json"
    _write_jsonl(selection_path, [_selection_record()])
    _write_jsonl(
        parser_path,
        [
            _parser_record("complaint", "complaint.md"),
            _parser_record("mtd", "mtd.md"),
            _parser_record("decision", "decision.md"),
        ],
    )
    _write_json(registry_path, [_registry_record()])
    stage_b_args = _write_authenticated_stage_b_inputs(
        root=tmp_path / "stage-b",
        selection_path=selection_path,
        parser_path=parser_path,
        markdown_root=markdown_root,
    )
    caps_path = _provider_caps_path(tmp_path)
    stage_a_args = _stub_authenticated_stage_a_lineage(
        monkeypatch,
        selection_path=selection_path,
        parser_path=parser_path,
        markdown_root=markdown_root,
        registry_path=registry_path,
        caps_path=caps_path,
        provider_journal_path=output_root / "provider-attempts.sqlite3",
    )

    provider_calls = 0

    def journaled_completion(*args: Any, **kwargs: Any) -> SolverResponse:
        nonlocal provider_calls
        provider_calls += 1
        response = _fake_completion(*args, **kwargs)
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

    monkeypatch.setattr(llm_pipeline, "complete_live_prompt", journaled_completion)

    assert (
        main(
            [
                "acquisition",
                "llm-unitize",
                "--selection",
                str(selection_path),
                "--parser-manifest",
                str(parser_path),
                "--output-root",
                str(output_root),
                "--model-registry",
                str(registry_path),
                "--model-key",
                "openai:gpt-test",
                "--provider-cycle-caps",
                str(caps_path),
                *stage_a_args,
                "--execute",
            ]
        )
        == 0
    )

    units = _read_jsonl(output_root / "prediction-units.jsonl")
    assert units[0]["candidate_id"] == "cand-1"
    assert units[0]["prediction_units"][0]["unit_id"] == "unit-1"
    unit_audit = _read_jsonl(output_root / "llm-unitization-audit.jsonl")[0]
    assert unit_audit["model_key"] == "openai:gpt-test"
    assert unit_audit["status"] == "adjudication_pending"
    assert unit_audit["human_verified"] is False
    assert unit_audit["estimated_cost"] > 0
    unitization_queue = _read_jsonl(output_root / "unitization-review-queue.jsonl")
    assert unitization_queue == [
        {
            "candidate_id": "cand-1",
            "case_id": "case-1",
            "review_id": "cand-1:unit-1:stage-a-review",
            "review_item": {
                "notes": "Stage A unit requires blinded pre-decision review.",
                "reason": "low_confidence",
                "source_document_ids": ["complaint", "mtd"],
                "unit_id": "unit-1",
            },
            "route_reason": "low_confidence",
            "schema_version": "legalforecast.unitization_review_queue.v1",
            "status": "pending_adjudication",
            "unit_id": "unit-1",
        }
    ]
    unitization_card = output_root / "run-cards" / "llm-unitize.json"
    provider_journal = output_root / "provider-attempts.sqlite3"
    review_root = tmp_path / "structural-review-output"
    review_args = [
        "acquisition",
        "llm-review-stage-a",
        "--selection",
        str(selection_path),
        "--parser-manifest",
        str(parser_path),
        "--markdown-root",
        str(markdown_root),
        "--prediction-units",
        str(output_root / "prediction-units.jsonl"),
        "--llm-unitization-run-card",
        str(unitization_card),
        "--unitization-review-queue",
        str(output_root / "unitization-review-queue.jsonl"),
        "--model-registry",
        str(registry_path),
        "--model-key",
        "openai:gpt-test",
        "--provider-cycle-caps",
        str(caps_path),
        "--provider-journal",
        str(provider_journal),
        "--output-root",
        str(review_root),
        "--execute",
    ]
    assert main(review_args) == 0
    assert provider_calls == 2

    bad_journal_args = list(review_args)
    bad_journal_args[bad_journal_args.index(str(provider_journal))] = str(
        tmp_path / "different-output-root" / "provider-attempts.sqlite3"
    )
    bad_journal_args[bad_journal_args.index(str(review_root))] = str(
        tmp_path / "different-output-root"
    )
    assert main(bad_journal_args) == 2
    assert provider_calls == 2

    mutated_caps = tmp_path / "mutated-provider-caps.json"
    mutated_caps.write_text(caps_path.read_text() + "\n", encoding="utf-8")
    mutated_caps_args = list(review_args)
    mutated_caps_args[mutated_caps_args.index(str(caps_path))] = str(mutated_caps)
    mutated_caps_args[mutated_caps_args.index(str(review_root))] = str(
        tmp_path / "mutated-caps-output"
    )
    assert main(mutated_caps_args) == 2
    assert provider_calls == 2

    wrong_cycle_caps = tmp_path / "wrong-cycle-provider-caps.json"
    wrong_cycle_payload = json.loads(caps_path.read_text())
    wrong_cycle_payload["cycle_id"] = "different-cycle"
    _write_json(wrong_cycle_caps, wrong_cycle_payload)
    wrong_cycle_args = list(review_args)
    wrong_cycle_args[wrong_cycle_args.index(str(caps_path))] = str(wrong_cycle_caps)
    wrong_cycle_args[wrong_cycle_args.index(str(review_root))] = str(
        tmp_path / "wrong-cycle-output"
    )
    assert main(wrong_cycle_args) == 2
    assert provider_calls == 2

    adjudications_path = tmp_path / "unitization-adjudications.jsonl"
    _write_jsonl(
        adjudications_path,
        [
            {
                "schema_version": "legalforecast.unitization_adjudication.v1",
                "adjudication_id": "adj-cand-1",
                "candidate_id": "cand-1",
                "case_id": "case-1",
                "review_ids": ["cand-1:unit-1:stage-a-review"],
                "source_unit_ids": ["unit-1"],
                "disposition": "ACCEPT",
                "finalized_units": [],
                "adjudicator_id": "john-hughes",
                "adjudication_notes": "Accepted after blinded review.",
            }
        ],
    )
    apply_root = tmp_path / "apply-review-output"
    assert (
        main(
            [
                "acquisition",
                "apply-unitization-review",
                "--prediction-units",
                str(output_root / "prediction-units.jsonl"),
                "--llm-unitization-run-card",
                str(unitization_card),
                "--unitization-review-queue",
                str(review_root / "unitization-review-queue-reviewed.jsonl"),
                "--adjudications",
                str(adjudications_path),
                "--output-root",
                str(apply_root),
                "--execute",
            ]
        )
        == 0
    )
    finalized_units_path = apply_root / "finalized-prediction-units.jsonl"
    provider_chain_args = [
        "--llm-unitization-run-card",
        str(unitization_card),
        "--llm-review-stage-a-run-card",
        str(review_root / "run-cards" / "llm-review-stage-a.json"),
        "--unitization-review-run-card",
        str(apply_root / "run-cards" / "apply-unitization-review.json"),
        "--provider-journal",
        str(provider_journal),
    ]

    assert (
        main(
            [
                "acquisition",
                "llm-label",
                "--selection",
                str(selection_path),
                "--parser-manifest",
                str(parser_path),
                "--prediction-units",
                str(finalized_units_path),
                *stage_b_args,
                "--output-root",
                str(output_root),
                "--model-registry",
                str(registry_path),
                "--evaluated-model-registry",
                str(_evaluated_registry_path(tmp_path)),
                "--model-key",
                "openai:gpt-test",
                "--provider-cycle-caps",
                str(_provider_caps_path(tmp_path)),
                *provider_chain_args,
                "--execute",
            ]
        )
        == 0
    )
    assert provider_calls == 3

    bad_label_chain_args = list(provider_chain_args)
    bad_label_chain_args[bad_label_chain_args.index(str(provider_journal))] = str(
        tmp_path / "label-different-root" / "provider-attempts.sqlite3"
    )
    assert (
        main(
            [
                "acquisition",
                "llm-label",
                "--selection",
                str(selection_path),
                "--parser-manifest",
                str(parser_path),
                "--prediction-units",
                str(finalized_units_path),
                *stage_b_args,
                "--output-root",
                str(tmp_path / "label-different-root"),
                "--model-registry",
                str(registry_path),
                "--evaluated-model-registry",
                str(_evaluated_registry_path(tmp_path)),
                "--model-key",
                "openai:gpt-test",
                "--provider-cycle-caps",
                str(caps_path),
                *bad_label_chain_args,
                "--execute",
            ]
        )
        == 2
    )
    assert provider_calls == 3

    labels = _read_jsonl(output_root / "labels.jsonl")
    assert labels[0]["unit_id"] == "unit-1"
    assert labels[0]["fully_dismissed"] is True
    assert labels[0]["first_written_disposition_date"] == "2026-06-30"
    label_audit = _read_jsonl(output_root / "llm-label-audit.jsonl")[0]
    assert label_audit["consensus_policy"] == "unanimous"
    assert label_audit["status"] == "succeeded"
    assert label_audit["human_verified"] is False
    assert label_audit["model_outputs"][0]["model_key"] == "openai:gpt-test"
    commitments = label_audit["decision_text_commitment"]
    assert commitments["decision_texts_sha256"] == _sha256_path(
        tmp_path / "stage-b" / "decision-texts.jsonl"
    )
    assert commitments["finalized_prediction_units_sha256"] == _sha256_path(
        finalized_units_path
    )
    assert commitments["finalized_unit_envelope_sha256"].startswith("sha256:")
    prompt_sha256 = label_audit["model_outputs"][0]["provider_prompt_sha256"]
    with sqlite3.connect(output_root / "provider-attempts.sqlite3") as connection:
        prompt_text, journal_prompt_sha256, reconstructed = connection.execute(
            "SELECT prompt_text, prompt_sha256, reconstructed_result_json "
            "FROM provider_attempts WHERE stage = 'llm-label'"
        ).fetchone()
    prompt = json.loads(prompt_text)
    assert prompt["decision_text"]["commitment"] == commitments
    assert prompt["decision_text"]["text"] == (
        "The motion to dismiss Count I is granted without leave to amend."
    )
    assert prompt_sha256 == "sha256:" + journal_prompt_sha256
    assert json.loads(reconstructed)["decision_text_commitment"] == commitments
    label_run_card = json.loads(
        (output_root / "run-cards" / "llm-label.json").read_text()
    )
    structural_run_card = json.loads(
        (review_root / "run-cards" / "llm-review-stage-a.json").read_text()
    )
    for card, stage in (
        (structural_run_card, "llm-review-stage-a"),
        (label_run_card, "llm-label"),
    ):
        assert card["provider_chain"] == {
            "schema_version": "legalforecast.provider_attempt_journal.v2",
            "cycle_id": "test-cycle",
            "provider_cycle_caps_sha256": _sha256_path(caps_path),
            "provider_journal": str(provider_journal.resolve()),
            "stage_attempts": {
                "stage": stage,
                "call_count": 1,
                "attempt_count": 1,
                "attempts_sha256": card["provider_chain"]["stage_attempts"][
                    "attempts_sha256"
                ],
            },
        }
        assert card["provider_chain"]["stage_attempts"]["attempts_sha256"].startswith(
            "sha256:"
        )
    assert label_run_card["stage_a_lineage"]["llm_review_stage_a_run_card"] == (
        cli._stage_a_file_commitment(
            review_root / "run-cards" / "llm-review-stage-a.json"
        )
    )
    assert label_run_card["decision_text_commitments"] == {
        "decision_texts_sha256": commitments["decision_texts_sha256"],
        "decision_texts_manifest_sha256": commitments["decision_texts_manifest_sha256"],
        "decision_texts_run_card_sha256": commitments["decision_texts_run_card_sha256"],
        "finalized_prediction_units_sha256": commitments[
            "finalized_prediction_units_sha256"
        ],
    }
    assert label_audit["label_audit_gate"]["status"] == "awaiting_cycle_level_plan"
    assert _read_jsonl(output_root / "lawyer-review-queue.jsonl") == []


def test_executed_llm_unitize_requires_authenticated_lineage_before_provider(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    selection_path = tmp_path / "selection.jsonl"
    parser_path = tmp_path / "parser.jsonl"
    registry_path = tmp_path / "registry.json"
    _write_jsonl(selection_path, [_selection_record()])
    _write_jsonl(parser_path, [_parser_record("complaint", "complaint.md")])
    _write_json(registry_path, [_registry_record()])
    provider_calls = 0

    def forbidden_provider_call(*args: Any, **kwargs: Any) -> SolverResponse:
        nonlocal provider_calls
        provider_calls += 1
        raise AssertionError("provider must not be called")

    monkeypatch.setattr(llm_pipeline, "complete_live_prompt", forbidden_provider_call)
    assert (
        main(
            [
                "acquisition",
                "llm-unitize",
                "--selection",
                str(selection_path),
                "--parser-manifest",
                str(parser_path),
                "--model-registry",
                str(registry_path),
                "--model-key",
                "openai:gpt-test",
                "--provider-cycle-caps",
                str(_provider_caps_path(tmp_path)),
                "--provider-journal",
                str(tmp_path / "shared-provider-attempts.sqlite3"),
                "--output-root",
                str(tmp_path / "out"),
                "--execute",
            ]
        )
        == 2
    )
    assert provider_calls == 0
    assert "authenticated Stage A lineage requires" in capsys.readouterr().err


def test_acquisition_llm_label_persists_lawyer_review_queue_with_partial_success(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    output_root = tmp_path / "acquisition"
    markdown_root = output_root / "markdown"
    _write_markdown(
        markdown_root / "cand-1" / "decision.md",
        "Count I is dismissed. Count II is dismissed.",
    )
    selection_path = tmp_path / "selection.jsonl"
    parser_path = tmp_path / "parser.jsonl"
    units_path = tmp_path / "prediction-units.jsonl"
    registry_path = tmp_path / "registry.json"
    _write_jsonl(selection_path, [_selection_record()])
    _write_jsonl(parser_path, [_parser_record("decision", "decision.md")])
    _write_jsonl(
        units_path,
        [
            {
                "candidate_id": "cand-1",
                "case_id": "case-1",
                "prediction_units": [
                    _prediction_unit_record("unit-auto", "Count I"),
                    _prediction_unit_record("unit-review", "Count II"),
                ],
            }
        ],
    )
    _write_json(
        registry_path,
        [
            _registry_record(model_id="gpt-a", display_name="GPT A"),
            _registry_record(model_id="gpt-b", display_name="GPT B"),
            _registry_record(model_id="gpt-c", display_name="GPT C"),
        ],
    )

    def partial_review_completion(*args: Any, **kwargs: Any) -> SolverResponse:
        entry = args[0]
        response = SolverResponse(
            raw_output=json.dumps(
                {
                    "unit_findings": [
                        {
                            "unit_id": "unit-auto",
                            "resolution": "fully_dismissed",
                            "amendment_signal": "express_denial_of_leave",
                            "supporting_excerpt": "Count I is dismissed.",
                            "labeler_confidence": 0.93,
                        },
                        {
                            "unit_id": "unit-review",
                            "resolution": "fully_dismissed",
                            "amendment_signal": "express_denial_of_leave",
                            "supporting_excerpt": "Count II is dismissed.",
                            "labeler_confidence": 0.7,
                        },
                    ],
                    "missing_unit_flags": [],
                }
            ),
            input_tokens=100,
            output_tokens=50,
            estimated_cost=0.01,
            metadata={"provider": "openai", "model_id": entry.model_id},
        )
        return _settle_fixture_unitization_attempt(response, kwargs)

    monkeypatch.setattr(llm_pipeline, "complete_live_prompt", partial_review_completion)
    _rewrite_as_finalized(units_path)
    stage_b_args = _write_authenticated_stage_b_inputs(
        root=tmp_path / "stage-b",
        selection_path=selection_path,
        parser_path=parser_path,
        markdown_root=markdown_root,
    )
    caps_path = _provider_caps_path(tmp_path)
    provider_chain_args = _stub_authenticated_finalized_provider_chain(
        monkeypatch,
        selection_path=selection_path,
        parser_path=parser_path,
        markdown_root=markdown_root,
        registry_path=registry_path,
        caps_path=caps_path,
        provider_journal_path=output_root / "provider-attempts.sqlite3",
        finalized_units_path=units_path,
    )

    assert (
        main(
            [
                "acquisition",
                "llm-label",
                "--selection",
                str(selection_path),
                "--parser-manifest",
                str(parser_path),
                "--prediction-units",
                str(units_path),
                *stage_b_args,
                "--output-root",
                str(output_root),
                "--model-registry",
                str(registry_path),
                "--evaluated-model-registry",
                str(_evaluated_registry_path(tmp_path)),
                "--model-key",
                "openai:gpt-a",
                "--model-key",
                "openai:gpt-b",
                "--model-key",
                "openai:gpt-c",
                "--provider-cycle-caps",
                str(caps_path),
                *provider_chain_args,
                "--execute",
            ]
        )
        == 0
    )

    labels = _read_jsonl(output_root / "labels.jsonl")
    assert [label["unit_id"] for label in labels] == ["unit-auto"]
    audit = _read_jsonl(output_root / "llm-label-audit.jsonl")[0]
    assert audit["status"] == "adjudication_pending"
    assert audit["human_verified"] is False
    assert audit["pending_adjudication_unit_ids"] == ["unit-review"]
    assert audit["pending_adjudication_count"] == 1
    assert audit["label_count"] == 1
    assert audit["unit_count"] == 2
    assert audit["label_audit_gate"]["status"] == "awaiting_cycle_level_plan"

    queue = _read_jsonl(output_root / "lawyer-review-queue.jsonl")
    assert len(queue) == 1
    queue_by_unit = {record["unit_id"]: record for record in queue}
    assert queue_by_unit["unit-review"]["status"] == "pending_adjudication"
    assert queue_by_unit["unit-review"]["case_id"] == "case-1"
    assert queue_by_unit["unit-review"]["route_reason"] == "low_confidence"
    assert queue_by_unit["unit-review"]["packet"]["review_reason"] == ("low_confidence")
    assert "unit-auto" not in queue_by_unit


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("artifact_date", "decision text date mismatch"),
        ("restricted", "sealed/private/restricted"),
        ("duplicate", "duplicate decision text candidate"),
        ("fixture_parser", "pinned live Mistral revision"),
        ("source_sha", "decision source hash mismatch"),
        ("source_bytes", "decision source byte-count mismatch"),
        ("quality_flags", "decision parser record has quality flags"),
        ("finalized_case", "finalized prediction-units case mismatch"),
        ("finalized_provenance", "automatic finalized-unit provenance"),
        ("markdown_drift", "extracted text hash mismatch"),
        ("manifest_drift", "manifest eligibility anchor drift"),
    ],
)
def test_llm_label_rejects_unauthenticated_decision_text_before_provider_call(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    mutation: str,
    message: str,
) -> None:
    output_root = tmp_path / "acquisition"
    markdown_root = output_root / "markdown"
    decision_path = markdown_root / "cand-1" / "decision.md"
    _write_markdown(decision_path, "Count I is dismissed.")
    selection_path = tmp_path / "selection.jsonl"
    parser_path = tmp_path / "parser.jsonl"
    units_path = tmp_path / "prediction-units.jsonl"
    registry_path = tmp_path / "registry.json"
    _write_jsonl(selection_path, [_selection_record()])
    _write_jsonl(parser_path, [_parser_record("decision", "decision.md")])
    _write_jsonl(
        units_path,
        [
            {
                "candidate_id": "cand-1",
                "case_id": "case-1",
                "prediction_units": [_prediction_unit_record("unit-1", "Count I")],
            }
        ],
    )
    _rewrite_as_finalized(units_path)
    _write_json(registry_path, [_registry_record()])
    stage_root = tmp_path / "stage-b"
    stage_b_args = _write_authenticated_stage_b_inputs(
        root=stage_root,
        selection_path=selection_path,
        parser_path=parser_path,
        markdown_root=markdown_root,
    )
    decision_texts_path = stage_root / "decision-texts.jsonl"
    manifest_path = stage_root / "decision-texts-manifest.json"
    if mutation == "artifact_date":
        rows = _read_jsonl(decision_texts_path)
        rows[0]["entered_date"] = "2026-07-01"
        _write_jsonl(decision_texts_path, rows)
        _reseal_stage_b_bundle(stage_root, selection_path, parser_path)
    elif mutation == "restricted":
        rows = _read_jsonl(decision_texts_path)
        rows[0]["clearance"]["restriction_status"] = "sealed"
        _write_jsonl(decision_texts_path, rows)
        _reseal_stage_b_bundle(stage_root, selection_path, parser_path)
    elif mutation == "duplicate":
        rows = _read_jsonl(decision_texts_path)
        rows.append(dict(rows[0]))
        _write_jsonl(decision_texts_path, rows)
        _reseal_stage_b_bundle(stage_root, selection_path, parser_path)
    elif mutation == "fixture_parser":
        rows = _read_jsonl(parser_path)
        rows[0]["parser_config"]["fixture_markdown"] = True
        _write_jsonl(parser_path, rows)
        _reseal_stage_b_bundle(stage_root, selection_path, parser_path)
    elif mutation == "source_sha":
        rows = _read_jsonl(parser_path)
        rows[0]["source_sha256"] = "2" * 64
        _write_jsonl(parser_path, rows)
        _reseal_stage_b_bundle(stage_root, selection_path, parser_path)
    elif mutation == "source_bytes":
        rows = _read_jsonl(parser_path)
        rows[0]["source_byte_count"] = 43
        _write_jsonl(parser_path, rows)
        _reseal_stage_b_bundle(stage_root, selection_path, parser_path)
    elif mutation == "quality_flags":
        rows = _read_jsonl(parser_path)
        rows[0]["quality_flags"] = ["manual_review_required"]
        _write_jsonl(parser_path, rows)
        _reseal_stage_b_bundle(stage_root, selection_path, parser_path)
    elif mutation == "finalized_case":
        rows = _read_jsonl(units_path)
        rows[0]["case_id"] = "wrong-case"
        _write_jsonl(units_path, rows)
    elif mutation == "finalized_provenance":
        rows = _read_jsonl(units_path)
        rows[0]["prediction_units"][0]["source_unit_sha256s"] = ["3" * 64]
        _write_jsonl(units_path, rows)
    elif mutation == "markdown_drift":
        decision_path.write_text("Count I survives.", encoding="utf-8")
    elif mutation == "manifest_drift":
        manifest = json.loads(manifest_path.read_text())
        manifest["eligibility_anchor"] = "2026-07-01"
        _write_json(manifest_path, manifest)
    else:  # pragma: no cover - parametrization is exhaustive
        raise AssertionError(mutation)

    provider_calls = 0

    def forbidden_provider_call(*args: Any, **kwargs: Any) -> SolverResponse:
        nonlocal provider_calls
        provider_calls += 1
        raise AssertionError("provider must not be called")

    monkeypatch.setattr(llm_pipeline, "complete_live_prompt", forbidden_provider_call)
    assert (
        main(
            [
                "acquisition",
                "llm-label",
                "--selection",
                str(selection_path),
                "--parser-manifest",
                str(parser_path),
                "--prediction-units",
                str(units_path),
                *stage_b_args,
                "--output-root",
                str(output_root),
                "--model-registry",
                str(registry_path),
                "--evaluated-model-registry",
                str(_evaluated_registry_path(tmp_path)),
                "--model-key",
                "openai:gpt-test",
                "--provider-cycle-caps",
                str(_provider_caps_path(tmp_path)),
                "--execute",
            ]
        )
        == 2
    )
    assert message in capsys.readouterr().err
    assert provider_calls == 0
    assert not (output_root / "provider-attempts.sqlite3").exists()
    assert not (output_root / "labels.jsonl").exists()


def test_acquisition_apply_lawyer_review_uses_verified_bytes_after_source_replacement(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    output_root = tmp_path / "acquisition"
    labels_path = tmp_path / "labels.jsonl"
    adjudications_path = tmp_path / "adjudications.jsonl"
    decision_texts_path = _write_decision_texts(tmp_path / "decision-texts.jsonl")
    decision_artifact_args = _stub_downstream_decision_artifact(
        monkeypatch,
        decision_texts_path,
        replace_after_verification=True,
    )
    llm_label_audit_path = tmp_path / "llm-label-audit.jsonl"
    auto_label = _label_record(
        "unit-auto",
        dismissed=False,
        excerpt="Count I survives.",
    )
    adjudicated_label = _label_record(
        "unit-review",
        dismissed=True,
        excerpt="Count II is dismissed.",
    )
    _write_jsonl(labels_path, [auto_label])
    _write_jsonl(
        llm_label_audit_path,
        [
            _llm_label_audit_record(
                auto_label=auto_label,
                review_label=adjudicated_label,
            )
        ],
    )
    _write_jsonl(
        adjudications_path,
        [
            _adjudication_record(
                "cand-1:unit-auto:label-audit",
                "unit-auto",
                auto_label,
            ),
            _adjudication_record(
                "cand-1:unit-review:lawyer-adjudication",
                "unit-review",
                adjudicated_label,
            ),
        ],
    )

    assert (
        main(
            [
                "acquisition",
                "apply-lawyer-review",
                "--labels",
                str(labels_path),
                "--adjudications",
                str(adjudications_path),
                "--decision-texts",
                str(decision_texts_path),
                *decision_artifact_args,
                "--llm-label-audit",
                str(llm_label_audit_path),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )

    labels_by_unit = {
        record["unit_id"]: record
        for record in _read_jsonl(output_root / "labels-adjudicated.jsonl")
    }
    assert sorted(labels_by_unit) == ["unit-auto", "unit-review"]
    assert labels_by_unit["unit-review"]["fully_dismissed"] is True

    audit_records = _read_jsonl(output_root / "lawyer-review-resume-audit.jsonl")
    audit = audit_records[0]
    assert audit["stage"] == "lawyer-review-resume"
    assert audit["status"] == "succeeded"
    assert audit["human_verified"] is True
    assert audit["adjudicated_review"]["disagreement_state"] == "single_reviewer"
    gate = next(
        record for record in audit_records if record["stage"] == "label-audit-gate"
    )
    assert gate["status"] == "passed"
    assert gate["audited_label_error_rate"] == 0.0
    assert gate["sample_unit_ids"] == ["unit-auto"]
    assert gate["label_audit_gate"]["audit_summary"]["passes_acceptance"] is True


def test_apply_adjudicated_reviews_rejects_nonverbatim_excerpt() -> None:
    # A lawyer-adjudicated label whose citation excerpt is not present verbatim in
    # the first written disposition must be rejected, exactly like an LLM Stage B
    # finding excerpt, so no published label ships an uncheckable citation.
    adjudicated_label = _label_record(
        "unit-review",
        dismissed=True,
        excerpt="Count II is dismissed.",
    )
    adjudication = _adjudication_record(
        "cand-1:unit-review:lawyer-adjudication",
        "unit-review",
        adjudicated_label,
    )
    decision_texts = {
        "decision": llm_pipeline.StageBDecisionText(
            document_id="decision",
            entered_date="2026-05-18",
            text="The Court denies the motion in full. No count was dismissed.",
        )
    }

    with raises(ValueError, match="must appear verbatim"):
        llm_pipeline.apply_adjudicated_reviews(
            label_records=[adjudicated_label],
            adjudication_records=[adjudication],
            decision_texts=decision_texts,
        )


def test_apply_adjudicated_reviews_rejects_label_without_excerpt() -> None:
    adjudicated_label = _label_record(
        "unit-review",
        dismissed=True,
        excerpt=None,
    )
    adjudication = _adjudication_record(
        "cand-1:unit-review:lawyer-adjudication",
        "unit-review",
        adjudicated_label,
    )
    decision_texts = {
        "decision": llm_pipeline.StageBDecisionText(
            document_id="decision",
            entered_date="2026-05-18",
            text="Count II is dismissed.",
        )
    }

    with raises(ValueError, match="at least one non-empty supporting excerpt"):
        llm_pipeline.apply_adjudicated_reviews(
            label_records=[adjudicated_label],
            adjudication_records=[adjudication],
            decision_texts=decision_texts,
        )


def test_apply_adjudicated_reviews_rejects_uncited_document() -> None:
    # Fail-closed: an adjudicated citation whose document has no decision text to
    # verify against is an error, not a silent skip.
    adjudicated_label = _label_record(
        "unit-review",
        dismissed=True,
        excerpt="Count II is dismissed.",
    )
    adjudication = _adjudication_record(
        "cand-1:unit-review:lawyer-adjudication",
        "unit-review",
        adjudicated_label,
    )

    with raises(ValueError, match="no decision text"):
        llm_pipeline.apply_adjudicated_reviews(
            label_records=[adjudicated_label],
            adjudication_records=[adjudication],
            decision_texts={},
        )


def test_acquisition_apply_lawyer_review_fails_without_audited_auto_label(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    output_root = tmp_path / "acquisition"
    labels_path = tmp_path / "labels.jsonl"
    adjudications_path = tmp_path / "adjudications.jsonl"
    decision_texts_path = _write_decision_texts(tmp_path / "decision-texts.jsonl")
    decision_artifact_args = _stub_downstream_decision_artifact(
        monkeypatch, decision_texts_path
    )
    llm_label_audit_path = tmp_path / "llm-label-audit.jsonl"
    auto_label = _label_record(
        "unit-auto",
        dismissed=False,
        excerpt="Count I survives.",
    )
    review_label = _label_record(
        "unit-review",
        dismissed=True,
        excerpt="Count II is dismissed.",
    )
    _write_jsonl(labels_path, [auto_label])
    _write_jsonl(
        llm_label_audit_path,
        [_llm_label_audit_record(auto_label=auto_label, review_label=review_label)],
    )
    _write_jsonl(
        adjudications_path,
        [
            _adjudication_record(
                "cand-1:unit-review:lawyer-adjudication",
                "unit-review",
                review_label,
            )
        ],
    )

    assert (
        main(
            [
                "acquisition",
                "apply-lawyer-review",
                "--labels",
                str(labels_path),
                "--adjudications",
                str(adjudications_path),
                "--decision-texts",
                str(decision_texts_path),
                *decision_artifact_args,
                "--llm-label-audit",
                str(llm_label_audit_path),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 2
    )

    assert not (output_root / "labels-adjudicated.jsonl").exists()


def test_acquisition_apply_lawyer_review_fails_closed_on_audit_error(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    output_root = tmp_path / "acquisition"
    labels_path = tmp_path / "labels.jsonl"
    adjudications_path = tmp_path / "adjudications.jsonl"
    decision_texts_path = _write_decision_texts(tmp_path / "decision-texts.jsonl")
    decision_artifact_args = _stub_downstream_decision_artifact(
        monkeypatch, decision_texts_path
    )
    llm_label_audit_path = tmp_path / "llm-label-audit.jsonl"
    auto_label = _label_record(
        "unit-auto",
        dismissed=False,
        excerpt="Count I survives.",
    )
    conflicting_audit_label = _label_record(
        "unit-auto",
        dismissed=True,
        excerpt="Count I is dismissed.",
    )
    review_label = _label_record(
        "unit-review",
        dismissed=True,
        excerpt="Count II is dismissed.",
    )
    _write_jsonl(labels_path, [auto_label])
    _write_jsonl(
        llm_label_audit_path,
        [_llm_label_audit_record(auto_label=auto_label, review_label=review_label)],
    )
    _write_jsonl(
        adjudications_path,
        [
            _adjudication_record(
                "cand-1:unit-auto:label-audit",
                "unit-auto",
                conflicting_audit_label,
            ),
            _adjudication_record(
                "cand-1:unit-review:lawyer-adjudication",
                "unit-review",
                review_label,
            ),
        ],
    )

    assert (
        main(
            [
                "acquisition",
                "apply-lawyer-review",
                "--labels",
                str(labels_path),
                "--adjudications",
                str(adjudications_path),
                "--decision-texts",
                str(decision_texts_path),
                *decision_artifact_args,
                "--llm-label-audit",
                str(llm_label_audit_path),
                "--human-blind-disagreement-rate",
                "0.05",
                "--audit-sample-size",
                "1",
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 2
    )

    assert not (output_root / "labels-adjudicated.jsonl").exists()


def test_acquisition_llm_unitize_accepts_singleton_string_list_fields(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    output_root = tmp_path / "acquisition"
    markdown_root = output_root / "markdown"
    _write_markdown(markdown_root / "cand-1" / "complaint.md", "Count I: 10(b).")
    _write_markdown(
        markdown_root / "cand-1" / "mtd.md",
        "Defendants move to dismiss Count I under Rule 12(b)(6).",
    )
    selection_path = tmp_path / "selection.jsonl"
    parser_path = tmp_path / "parser.jsonl"
    registry_path = tmp_path / "registry.json"
    _write_jsonl(selection_path, [_selection_record()])
    _write_jsonl(
        parser_path,
        [
            _parser_record("complaint", "complaint.md"),
            _parser_record("mtd", "mtd.md"),
            _parser_record("decision", "decision.md"),
        ],
    )
    _write_json(registry_path, [_registry_record()])
    caps_path = _provider_caps_path(tmp_path)
    stage_a_args = _stub_authenticated_stage_a_lineage(
        monkeypatch,
        selection_path=selection_path,
        parser_path=parser_path,
        markdown_root=markdown_root,
        registry_path=registry_path,
        caps_path=caps_path,
        provider_journal_path=output_root / "provider-attempts.sqlite3",
    )

    def fake_completion(*args: Any, **kwargs: Any) -> SolverResponse:
        response = SolverResponse(
            raw_output=json.dumps(
                {
                    "unit_seeds": [
                        {
                            "unit_id": "unit-1",
                            "count": "Count I",
                            "claim_name": "Section 10(b)",
                            "defendant_names": "Issuer",
                            "source_document_ids": "mtd",
                            "challenged_by_motion": True,
                            "challenge_scope": "entire_claim",
                            "unit_confidence": 0.92,
                            "grouping": "individual",
                            "citation_excerpt": "dismiss Count I",
                        }
                    ]
                }
            ),
            input_tokens=100,
            output_tokens=50,
            estimated_cost=0.01,
            metadata={"provider": "openai", "model_id": "gpt-test"},
        )
        return _settle_fixture_unitization_attempt(response, kwargs)

    monkeypatch.setattr(llm_pipeline, "complete_live_prompt", fake_completion)

    assert (
        main(
            [
                "acquisition",
                "llm-unitize",
                "--selection",
                str(selection_path),
                "--parser-manifest",
                str(parser_path),
                "--output-root",
                str(output_root),
                "--model-registry",
                str(registry_path),
                "--model-key",
                "openai:gpt-test",
                "--provider-cycle-caps",
                str(caps_path),
                *stage_a_args,
                "--execute",
            ]
        )
        == 0
    )

    unit = _read_jsonl(output_root / "prediction-units.jsonl")[0]["prediction_units"][0]
    assert unit["source_citations"][0]["document_id"] == "mtd"
    assert unit["defendant_group"] == "Issuer"


def test_acquisition_llm_unitize_accepts_top_level_seed_array(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    output_root = tmp_path / "acquisition"
    markdown_root = output_root / "markdown"
    _write_markdown(markdown_root / "cand-1" / "complaint.md", "Count I: 10(b).")
    _write_markdown(
        markdown_root / "cand-1" / "mtd.md",
        "Defendants move to dismiss Count I under Rule 12(b)(6).",
    )
    selection_path = tmp_path / "selection.jsonl"
    parser_path = tmp_path / "parser.jsonl"
    registry_path = tmp_path / "registry.json"
    _write_jsonl(selection_path, [_selection_record()])
    _write_jsonl(
        parser_path,
        [
            _parser_record("complaint", "complaint.md"),
            _parser_record("mtd", "mtd.md"),
        ],
    )
    _write_json(registry_path, [_registry_record()])
    caps_path = _provider_caps_path(tmp_path)
    stage_a_args = _stub_authenticated_stage_a_lineage(
        monkeypatch,
        selection_path=selection_path,
        parser_path=parser_path,
        markdown_root=markdown_root,
        registry_path=registry_path,
        caps_path=caps_path,
        provider_journal_path=output_root / "provider-attempts.sqlite3",
    )

    def fake_completion(*args: Any, **kwargs: Any) -> SolverResponse:
        response = SolverResponse(
            raw_output=json.dumps(
                [
                    {
                        "unit_id": "unit-1",
                        "count": "Count I",
                        "claim_name": "Section 10(b)",
                        "defendant_names": ["Issuer"],
                        "source_document_ids": ["mtd"],
                        "challenged_by_motion": True,
                        "challenge_scope": "entire_claim",
                        "unit_confidence": 0.92,
                        "grouping": "individual",
                        "citation_excerpt": "dismiss Count I",
                    }
                ]
            ),
            input_tokens=100,
            output_tokens=50,
            estimated_cost=0.01,
            metadata={"provider": "openai", "model_id": "gpt-test"},
        )
        return _settle_fixture_unitization_attempt(response, kwargs)

    monkeypatch.setattr(llm_pipeline, "complete_live_prompt", fake_completion)

    assert (
        main(
            [
                "acquisition",
                "llm-unitize",
                "--selection",
                str(selection_path),
                "--parser-manifest",
                str(parser_path),
                "--output-root",
                str(output_root),
                "--model-registry",
                str(registry_path),
                "--model-key",
                "openai:gpt-test",
                "--provider-cycle-caps",
                str(caps_path),
                *stage_a_args,
                "--execute",
            ]
        )
        == 0
    )

    unit = _read_jsonl(output_root / "prediction-units.jsonl")[0]["prediction_units"][0]
    assert unit["unit_id"] == "unit-1"


def test_acquisition_llm_unitize_rejects_missing_required_unit_fields(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    output_root = tmp_path / "acquisition"
    markdown_root = output_root / "markdown"
    _write_markdown(markdown_root / "cand-1" / "complaint.md", "Count I: 10(b).")
    _write_markdown(
        markdown_root / "cand-1" / "mtd.md",
        "Defendants move to dismiss Count I under Rule 12(b)(6).",
    )
    selection_path = tmp_path / "selection.jsonl"
    parser_path = tmp_path / "parser.jsonl"
    registry_path = tmp_path / "registry.json"
    _write_jsonl(selection_path, [_selection_record()])
    _write_jsonl(
        parser_path,
        [
            _parser_record("complaint", "complaint.md"),
            _parser_record("mtd", "mtd.md"),
        ],
    )
    _write_json(registry_path, [_registry_record()])
    caps_path = _provider_caps_path(tmp_path)
    stage_a_args = _stub_authenticated_stage_a_lineage(
        monkeypatch,
        selection_path=selection_path,
        parser_path=parser_path,
        markdown_root=markdown_root,
        registry_path=registry_path,
        caps_path=caps_path,
        provider_journal_path=output_root / "provider-attempts.sqlite3",
    )

    def incomplete_completion(*args: Any, **kwargs: Any) -> SolverResponse:
        response = SolverResponse(
            raw_output=json.dumps(
                {
                    "unit_seeds": [
                        {
                            "unit_id": "unit-1",
                            "count": "Count I",
                            "claim_name": "Section 10(b)",
                            "defendant_names": ["Issuer"],
                            "source_document_ids": ["mtd"],
                            "unit_confidence": 0.92,
                            "grouping": "individual",
                            "citation_excerpt": "dismiss Count I",
                        }
                    ]
                }
            ),
            input_tokens=100,
            output_tokens=50,
            estimated_cost=0.01,
            metadata={"provider": "openai", "model_id": "gpt-test"},
        )
        return _settle_fixture_unitization_attempt(response, kwargs)

    monkeypatch.setattr(llm_pipeline, "complete_live_prompt", incomplete_completion)

    assert (
        main(
            [
                "acquisition",
                "llm-unitize",
                "--selection",
                str(selection_path),
                "--parser-manifest",
                str(parser_path),
                "--output-root",
                str(output_root),
                "--model-registry",
                str(registry_path),
                "--model-key",
                "openai:gpt-test",
                "--continue-on-error",
                "--provider-cycle-caps",
                str(caps_path),
                *stage_a_args,
                "--execute",
            ]
        )
        == 0
    )

    assert _read_jsonl(output_root / "prediction-units.jsonl") == []
    audit = _read_jsonl(output_root / "llm-unitization-audit.jsonl")[0]
    assert audit["status"] == "failed"
    assert "challenged_by_motion" in audit["error_message"]
    assert audit["exclusion_ledger_entries"][0]["stage"] == "labeling"


def test_acquisition_llm_unitize_accepts_first_balanced_json_object(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    output_root = tmp_path / "acquisition"
    markdown_root = output_root / "markdown"
    _write_markdown(markdown_root / "cand-1" / "complaint.md", "Count I: 10(b).")
    _write_markdown(
        markdown_root / "cand-1" / "mtd.md",
        "Defendants move to dismiss Count I under Rule 12(b)(6).",
    )
    selection_path = tmp_path / "selection.jsonl"
    parser_path = tmp_path / "parser.jsonl"
    registry_path = tmp_path / "registry.json"
    _write_jsonl(selection_path, [_selection_record()])
    _write_jsonl(
        parser_path,
        [
            _parser_record("complaint", "complaint.md"),
            _parser_record("mtd", "mtd.md"),
        ],
    )
    _write_json(registry_path, [_registry_record()])
    caps_path = _provider_caps_path(tmp_path)
    stage_a_args = _stub_authenticated_stage_a_lineage(
        monkeypatch,
        selection_path=selection_path,
        parser_path=parser_path,
        markdown_root=markdown_root,
        registry_path=registry_path,
        caps_path=caps_path,
        provider_journal_path=output_root / "provider-attempts.sqlite3",
    )

    payload = {
        "unit_seeds": [
            {
                "unit_id": "unit-1",
                "count": "Count I",
                "claim_name": "Section 10(b)",
                "defendant_names": ["Issuer"],
                "source_document_ids": ["mtd"],
                "challenged_by_motion": True,
                "challenge_scope": "entire_claim",
                "unit_confidence": 0.92,
                "grouping": "individual",
                "citation_excerpt": "dismiss Count I",
            }
        ]
    }

    def fake_completion(*args: Any, **kwargs: Any) -> SolverResponse:
        response = SolverResponse(
            raw_output=f'{json.dumps(payload)}\n{{"debug": true}}',
            input_tokens=100,
            output_tokens=50,
            estimated_cost=0.01,
            metadata={"provider": "openai", "model_id": "gpt-test"},
        )
        return _settle_fixture_unitization_attempt(response, kwargs)

    monkeypatch.setattr(llm_pipeline, "complete_live_prompt", fake_completion)

    assert (
        main(
            [
                "acquisition",
                "llm-unitize",
                "--selection",
                str(selection_path),
                "--parser-manifest",
                str(parser_path),
                "--output-root",
                str(output_root),
                "--model-registry",
                str(registry_path),
                "--model-key",
                "openai:gpt-test",
                "--provider-cycle-caps",
                str(caps_path),
                *stage_a_args,
                "--execute",
            ]
        )
        == 0
    )

    unit = _read_jsonl(output_root / "prediction-units.jsonl")[0]["prediction_units"][0]
    assert unit["unit_id"] == "unit-1"


def test_llm_label_excerpt_coercion_uses_verbatim_near_match() -> None:
    decision_text = (
        "Defendants' Motion as to Claim One is GRANTED, and the Claim is "
        "DISMISSED WITH LEAVE TO AMEND."
    )

    coerce_excerpt = cast(Any, llm_pipeline)._coerced_excerpt
    excerpt = coerce_excerpt(
        decision_text,
        "Defendants Motion as to Claim One is granted and the claim is dismissed "
        "with leave to amend.",
    )

    assert excerpt == decision_text


def test_labeling_prompt_explains_not_addressed_resolution() -> None:
    prompt = json.loads(
        cast(Any, llm_pipeline)._labeling_prompt(
            _selection_record(),
            llm_pipeline.StageBDecisionText(
                document_id="decision",
                entered_date="2026-05-18",
                text="The motion is granted as to Count I.",
            ),
            (_prediction_unit(),),
            decision_text_commitment={
                "decision_texts_sha256": "sha256:" + "a" * 64,
            },
        )
    )

    rules = "\n".join(prompt["rules"])

    assert "not_addressed_by_this_disposition" in rules
    assert "amendment_signal not_applicable" in rules
    assert "do not infer an outcome from silence" in rules


def test_labeling_failure_ledger_uses_specific_reason_codes() -> None:
    response = SolverResponse(
        raw_output='{"unit_findings": "bad"}',
        input_tokens=1,
        output_tokens=1,
        estimated_cost=0.01,
    )
    cases = [
        (
            llm_pipeline.LlmResponseValidationError(
                "unit_findings must be a list",
                response=response,
            ),
            "parse_error",
        ),
        (
            llm_pipeline.LlmPipelineError(
                "LLM labels require lawyer adjudication for units: ['unit-1']"
            ),
            "adjudication_pending",
        ),
        (
            llm_pipeline.LlmPipelineError("LLM judges were not unanimous for unit-1"),
            "judge_disagreement",
        ),
        (
            llm_pipeline.LlmPipelineError(
                "LLM-only labels include ambiguous units: ['unit-1']"
            ),
            "ambiguous",
        ),
    ]

    entries_for = cast(Any, llm_pipeline)._labeling_exclusion_entries

    for error, reason in cases:
        [entry] = entries_for(_selection_record(), error)
        assert entry["primary_exclusion_reason"] == reason
        assert entry["reason"] == reason


def test_acquisition_llm_unitize_failure_audit_keeps_model_accounting(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    output_root = tmp_path / "acquisition"
    markdown_root = output_root / "markdown"
    _write_markdown(markdown_root / "cand-1" / "complaint.md", "Count I: 10(b).")
    _write_markdown(
        markdown_root / "cand-1" / "mtd.md",
        "Defendants move to dismiss Count I under Rule 12(b)(6).",
    )
    selection_path = tmp_path / "selection.jsonl"
    parser_path = tmp_path / "parser.jsonl"
    registry_path = tmp_path / "registry.json"
    _write_jsonl(selection_path, [_selection_record()])
    _write_jsonl(
        parser_path,
        [
            _parser_record("complaint", "complaint.md"),
            _parser_record("mtd", "mtd.md"),
        ],
    )
    _write_json(registry_path, [_registry_record()])
    caps_path = _provider_caps_path(tmp_path)
    stage_a_args = _stub_authenticated_stage_a_lineage(
        monkeypatch,
        selection_path=selection_path,
        parser_path=parser_path,
        markdown_root=markdown_root,
        registry_path=registry_path,
        caps_path=caps_path,
        provider_journal_path=output_root / "provider-attempts.sqlite3",
    )

    def invalid_completion(*args: Any, **kwargs: Any) -> SolverResponse:
        response = SolverResponse(
            raw_output=json.dumps(
                {
                    "unit_seeds": [
                        {
                            "unit_id": "unit-1",
                            "count": "Count I",
                            "claim_name": "Section 10(b)",
                            "defendant_names": ["Issuer"],
                            "source_document_ids": {"document_id": "mtd"},
                            "challenged_by_motion": True,
                            "challenge_scope": "entire_claim",
                            "unit_confidence": 0.92,
                            "grouping": "individual",
                            "citation_excerpt": "dismiss Count I",
                        }
                    ]
                }
            ),
            input_tokens=123,
            output_tokens=45,
            estimated_cost=0.12,
            metadata={"provider": "openai", "model_id": "gpt-test"},
        )
        return _settle_fixture_unitization_attempt(response, kwargs)

    monkeypatch.setattr(llm_pipeline, "complete_live_prompt", invalid_completion)

    assert (
        main(
            [
                "acquisition",
                "llm-unitize",
                "--selection",
                str(selection_path),
                "--parser-manifest",
                str(parser_path),
                "--output-root",
                str(output_root),
                "--model-registry",
                str(registry_path),
                "--model-key",
                "openai:gpt-test",
                "--continue-on-error",
                "--provider-cycle-caps",
                str(caps_path),
                *stage_a_args,
                "--execute",
            ]
        )
        == 0
    )

    assert _read_jsonl(output_root / "prediction-units.jsonl") == []
    audit = _read_jsonl(output_root / "llm-unitization-audit.jsonl")[0]
    assert audit["status"] == "failed"
    assert audit["estimated_cost"] == 0.12
    assert audit["input_tokens"] == 123
    assert audit["output_tokens"] == 45
    assert str(audit["raw_output_sha256"]).startswith("sha256:")
    assert audit["metadata"]["model_id"] == "gpt-test"


def test_acquisition_llm_label_failure_audit_keeps_model_accounting(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    output_root = tmp_path / "acquisition"
    markdown_root = output_root / "markdown"
    _write_markdown(markdown_root / "cand-1" / "decision.md", "Count I is dismissed.")
    selection_path = tmp_path / "selection.jsonl"
    parser_path = tmp_path / "parser.jsonl"
    units_path = tmp_path / "prediction-units.jsonl"
    registry_path = tmp_path / "registry.json"
    _write_jsonl(selection_path, [_selection_record()])
    _write_jsonl(parser_path, [_parser_record("decision", "decision.md")])
    _write_jsonl(
        units_path,
        [
            {
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
                        "source_citations": [{"document_id": "mtd"}],
                        "grouping": "individual",
                        "grouping_rationale": None,
                        "separable_subclaim": None,
                        "uncertainty_notes": None,
                    }
                ],
            }
        ],
    )
    _write_json(registry_path, [_registry_record()])

    def invalid_label_completion(*args: Any, **kwargs: Any) -> SolverResponse:
        return SolverResponse(
            raw_output=json.dumps(
                {
                    "unit_findings": [
                        {
                            "unit_id": "unit-1",
                            "resolution": "fully_dismissed",
                            "amendment_signal": "express_denial_of_leave",
                            "supporting_excerpt": "The motion is granted.",
                            "labeler_confidence": 0.91,
                        }
                    ],
                    "missing_unit_flags": [],
                }
            ),
            input_tokens=234,
            output_tokens=56,
            estimated_cost=0.23,
            metadata={"provider": "openai", "model_id": "gpt-test"},
        )

    monkeypatch.setattr(llm_pipeline, "complete_live_prompt", invalid_label_completion)
    _rewrite_as_finalized(units_path)
    stage_b_args = _write_authenticated_stage_b_inputs(
        root=tmp_path / "stage-b",
        selection_path=selection_path,
        parser_path=parser_path,
        markdown_root=markdown_root,
    )
    caps_path = _provider_caps_path(tmp_path)
    provider_chain_args = _stub_authenticated_finalized_provider_chain(
        monkeypatch,
        selection_path=selection_path,
        parser_path=parser_path,
        markdown_root=markdown_root,
        registry_path=registry_path,
        caps_path=caps_path,
        provider_journal_path=output_root / "provider-attempts.sqlite3",
        finalized_units_path=units_path,
    )

    assert (
        main(
            [
                "acquisition",
                "llm-label",
                "--selection",
                str(selection_path),
                "--parser-manifest",
                str(parser_path),
                "--prediction-units",
                str(units_path),
                *stage_b_args,
                "--output-root",
                str(output_root),
                "--model-registry",
                str(registry_path),
                "--model-key",
                "openai:gpt-test",
                "--continue-on-error",
                "--evaluated-model-registry",
                str(_evaluated_registry_path(tmp_path)),
                "--provider-cycle-caps",
                str(caps_path),
                *provider_chain_args,
                "--execute",
            ]
        )
        == 0
    )

    assert _read_jsonl(output_root / "labels.jsonl") == []
    audit = _read_jsonl(output_root / "llm-label-audit.jsonl")[0]
    assert audit["status"] == "failed"
    assert audit["estimated_cost"] == 0.23
    assert audit["input_tokens"] == 234
    assert audit["output_tokens"] == 56
    assert str(audit["raw_output_sha256"]).startswith("sha256:")
    assert audit["metadata"]["model_id"] == "gpt-test"


def test_acquisition_llm_label_missing_unit_flags_gate_frozen_unit_workflow(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    output_root = tmp_path / "acquisition"
    markdown_root = output_root / "markdown"
    _write_markdown(
        markdown_root / "cand-1" / "decision.md",
        "Count I is dismissed. The court also dismisses Count II.",
    )
    selection_path = tmp_path / "selection.jsonl"
    parser_path = tmp_path / "parser.jsonl"
    units_path = tmp_path / "prediction-units.jsonl"
    registry_path = tmp_path / "registry.json"
    _write_jsonl(selection_path, [_selection_record()])
    _write_jsonl(parser_path, [_parser_record("decision", "decision.md")])
    _write_jsonl(
        units_path,
        [
            {
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
                        "source_citations": [{"document_id": "mtd"}],
                        "grouping": "individual",
                        "grouping_rationale": None,
                        "separable_subclaim": None,
                        "uncertainty_notes": None,
                    }
                ],
            }
        ],
    )
    _write_json(registry_path, [_registry_record()])

    def missing_unit_completion(*args: Any, **kwargs: Any) -> SolverResponse:
        return SolverResponse(
            raw_output=json.dumps(
                {
                    "unit_findings": [
                        {
                            "unit_id": "unit-1",
                            "resolution": "fully_dismissed",
                            "amendment_signal": "express_denial_of_leave",
                            "supporting_excerpt": "Count I is dismissed.",
                            "labeler_confidence": 0.91,
                        }
                    ],
                    "missing_unit_flags": [
                        {
                            "missing_unit_description": (
                                "Decision resolved Count II, which was absent from "
                                "frozen Stage A units."
                            ),
                            "supporting_excerpt": (
                                "The court also dismisses Count II."
                            ),
                        }
                    ],
                }
            ),
            input_tokens=345,
            output_tokens=67,
            estimated_cost=0.34,
            metadata={"provider": "openai", "model_id": "gpt-test"},
        )

    monkeypatch.setattr(llm_pipeline, "complete_live_prompt", missing_unit_completion)
    _rewrite_as_finalized(units_path)
    stage_b_args = _write_authenticated_stage_b_inputs(
        root=tmp_path / "stage-b",
        selection_path=selection_path,
        parser_path=parser_path,
        markdown_root=markdown_root,
    )
    caps_path = _provider_caps_path(tmp_path)
    provider_chain_args = _stub_authenticated_finalized_provider_chain(
        monkeypatch,
        selection_path=selection_path,
        parser_path=parser_path,
        markdown_root=markdown_root,
        registry_path=registry_path,
        caps_path=caps_path,
        provider_journal_path=output_root / "provider-attempts.sqlite3",
        finalized_units_path=units_path,
    )

    assert (
        main(
            [
                "acquisition",
                "llm-label",
                "--selection",
                str(selection_path),
                "--parser-manifest",
                str(parser_path),
                "--prediction-units",
                str(units_path),
                *stage_b_args,
                "--output-root",
                str(output_root),
                "--model-registry",
                str(registry_path),
                "--model-key",
                "openai:gpt-test",
                "--continue-on-error",
                "--evaluated-model-registry",
                str(_evaluated_registry_path(tmp_path)),
                "--provider-cycle-caps",
                str(caps_path),
                *provider_chain_args,
                "--execute",
            ]
        )
        == 0
    )

    assert _read_jsonl(output_root / "labels.jsonl") == []
    audit = _read_jsonl(output_root / "llm-label-audit.jsonl")[0]
    assert audit["status"] == "failed"
    assert audit["error_type"] == "FrozenUnitWorkflowRequiredError"
    assert audit["requires_frozen_unit_workflow"] is True
    assert audit["missing_unit_flag_count"] == 1
    assert audit["frozen_unit_excluded_count"] == 1
    assert audit["frozen_unit_repaired_count"] == 0
    assert audit["frozen_unit_workflow"]["frozen_unit_status"] == "excluded"
    assert audit["estimated_cost"] == 0.34
    [entry] = audit["exclusion_ledger_entries"]
    assert entry["stage"] == "unitization"
    assert entry["primary_exclusion_reason"] == "unit_missing_from_stage_a"


def _fake_completion(*args: Any, **kwargs: Any) -> SolverResponse:
    prompt = cast(str, args[1])
    if "Construct frozen Stage A" in prompt:
        raw_output = {
            "unit_seeds": [
                {
                    "unit_id": "unit-1",
                    "count": "Count I",
                    "claim_name": "Section 10(b)",
                    "defendant_names": ["Issuer"],
                    "source_document_ids": ["complaint", "mtd"],
                    "challenged_by_motion": True,
                    "challenge_scope": "entire_claim",
                    "unit_confidence": 0.42,
                    "grouping": "individual",
                    "citation_excerpt": "Count I: 10(b).",
                }
            ]
        }
    elif "Create Stage B outcome labels" in prompt:
        raw_output = {
            "unit_findings": [
                {
                    "unit_id": "unit-1",
                    "resolution": "fully_dismissed",
                    "amendment_signal": "express_denial_of_leave",
                    "supporting_excerpt": (
                        "motion to dismiss Count I is granted without leave"
                    ),
                    "labeler_confidence": 0.91,
                    "notes": "The court dismissed the only challenged claim.",
                }
            ],
            "missing_unit_flags": [],
        }
    elif "Review frozen Stage A units" in prompt:
        raw_output = {"structural_flags": []}
    else:
        raise AssertionError("unexpected prompt")
    return SolverResponse(
        raw_output=json.dumps(raw_output),
        input_tokens=100,
        output_tokens=50,
        estimated_cost=0.01,
        metadata={"provider": "openai", "model_id": "gpt-test"},
    )


def _selection_record() -> JsonRecord:
    return {
        "candidate_id": "cand-1",
        "case_id": "case-1",
        "decision_date": "2026-06-30",
        "case_name": "Example v. Issuer",
        "court": "S.D.N.Y.",
        "docket_number": "1:26-cv-1",
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
        "is_sealed": False,
        "is_private": False,
        "restriction_status": "public",
    }


def _prediction_unit() -> PredictionUnit:
    return PredictionUnit(
        unit_id="unit-1",
        count="Count I",
        claim_name="Section 10(b)",
        defendant_group="Issuer",
        challenged_by_motion=True,
        challenge_scope=ChallengeScope.ENTIRE_CLAIM,
        unit_confidence=0.9,
        source_citations=(
            SourceCitation(
                document_id="mtd",
                docket_entry_number=5,
                excerpt="Defendants move to dismiss Count I.",
            ),
        ),
    )


def _prediction_unit_record(unit_id: str, count: str) -> JsonRecord:
    return {
        "unit_id": unit_id,
        "count": count,
        "claim_name": "Section 10(b)",
        "defendant_group": "Issuer",
        "challenged_by_motion": True,
        "challenge_scope": "entire_claim",
        "unit_confidence": 0.9,
        "source_citations": [{"document_id": "mtd"}],
        "grouping": "individual",
        "grouping_rationale": None,
        "separable_subclaim": None,
        "uncertainty_notes": None,
    }


def _parser_record(source_document_id: str, filename: str) -> JsonRecord:
    return {
        "candidate_id": "cand-1",
        "source_document_id": source_document_id,
        "status": "succeeded",
        "markdown_path": f"cand-1/{filename}",
    }


def _registry_record(
    *,
    model_id: str = "gpt-test",
    display_name: str | None = None,
) -> JsonRecord:
    return {
        "provider": "openai",
        "model_id": model_id,
        "display_name": display_name or "GPT Test",
        "model_version_or_snapshot": model_id,
        "release_timestamp": "2026-05-18T00:00:00Z",
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
        "pricing_source": "fixture",
        "input_token_price": 1.0,
        "output_token_price": 2.0,
        "known_cutoff_publicity_caveats": [],
    }


def test_resume_and_lawyer_deserialization_preserve_false_label_resolution() -> None:
    labels = []
    for resolution in ("partial_dismissal_only", "survives_in_material_respect"):
        label = _label_record("unit-1", dismissed=False, excerpt="Count I survives.")
        label["unit_resolution"] = resolution
        labels.append(label)

    reconstructed_votes = [
        llm_pipeline._ensemble_label_vote(
            {
                "model_id": f"judge-{index}",
                "unit_id": "unit-1",
                "label": label,
                "confidence": 0.9,
                "rationale": "Fixture.",
                "raw_response_id": f"response-{index}",
            }
        )
        for index, label in enumerate(labels)
    ]
    reconstructed_responses = [
        llm_pipeline._lawyer_review_response(
            {
                "review_id": "review-1",
                "reviewer_id": f"lawyer-{index}",
                "reviewer_expertise": "senior_litigator",
                "proposed_label": label,
                "confidence": 0.9,
                "minutes_spent": 10.0,
                "notes": "Fixture.",
            }
        )
        for index, label in enumerate(labels)
    ]

    assert {
        vote.label.canonical_unit_resolution.value for vote in reconstructed_votes
    } == {"partial_dismissal_only", "survives_in_material_respect"}
    assert {
        response.proposed_label.canonical_unit_resolution.value
        for response in reconstructed_responses
    } == {"partial_dismissal_only", "survives_in_material_respect"}


def _label_record(
    unit_id: str,
    *,
    dismissed: bool,
    excerpt: str | None,
) -> JsonRecord:
    return {
        "unit_id": unit_id,
        "unit_resolution": (
            "fully_dismissed" if dismissed else "survives_in_material_respect"
        ),
        "fully_dismissed": dismissed,
        "primary_outcome": 1 if dismissed else 0,
        "amendment_class": (
            "dismissed_with_express_denial_of_leave"
            if dismissed
            else "not_fully_dismissed"
        ),
        "amendment_target_applicable": dismissed,
        "conditional_amendment_target": False if dismissed else None,
        "ambiguous": False,
        "label_confidence": 0.97,
        "supporting_citations": [
            {
                "document_id": "decision",
                "page": None,
                "paragraph": None,
                "excerpt": excerpt,
            }
        ],
        "first_written_disposition_id": "decision",
        "first_written_disposition_date": "2026-05-18",
        "first_written_disposition_locked": True,
        "later_procedural_changes": [],
        "notes": None,
    }


def _adjudication_record(
    review_id: str,
    unit_id: str,
    label: JsonRecord,
) -> JsonRecord:
    return {
        "review_id": review_id,
        "candidate_id": "cand-1",
        "unit_id": unit_id,
        "reviewer_responses": [
            {
                "review_id": review_id,
                "reviewer_id": "reviewer-a",
                "reviewer_expertise": "senior_litigator",
                "proposed_label": label,
                "confidence": 0.96,
                "minutes_spent": 12.5,
                "notes": "Checked against the first written disposition.",
            }
        ],
        "adjudicated_label": label,
        "adjudicator_id": "john-hughes",
        "adjudication_notes": "Accepted the reviewer label.",
    }


def _llm_label_audit_record(
    *,
    auto_label: JsonRecord,
    review_label: JsonRecord,
) -> JsonRecord:
    return {
        "stage": "llm-label",
        "status": "adjudication_pending",
        "candidate_id": "cand-1",
        "case_id": "case-1",
        "ensemble": {
            "high_confidence_threshold": 0.85,
            "required_model_count": 3,
            "unit_count": 2,
            "auto_label_count": 1,
            "lawyer_adjudicated_share": 0.5,
            "ambiguous_unit_count": 0,
            "ambiguous_exclusion_count": 0,
            "decisions": [
                _ensemble_decision_record(
                    unit_id="unit-auto",
                    status="auto_label",
                    route_reason="unanimous_high_confidence",
                    label=auto_label,
                    confidence=0.93,
                    unanimous_label=auto_label,
                ),
                _ensemble_decision_record(
                    unit_id="unit-review",
                    status="lawyer_adjudication",
                    route_reason="low_confidence",
                    label=review_label,
                    confidence=0.7,
                    unanimous_label=None,
                ),
            ],
        },
    }


def _ensemble_decision_record(
    *,
    unit_id: str,
    status: str,
    route_reason: str,
    label: JsonRecord,
    confidence: float,
    unanimous_label: JsonRecord | None,
) -> JsonRecord:
    votes = [
        _ensemble_vote_record(f"openai:gpt-{suffix}", unit_id, label, confidence)
        for suffix in ("a", "b", "c")
    ]
    return {
        "unit_id": unit_id,
        "status": status,
        "route_reason": route_reason,
        "model_ids": [vote["model_id"] for vote in votes],
        "mean_confidence": confidence,
        "min_confidence": confidence,
        "unanimous_label": unanimous_label,
        "votes": votes,
    }


def _ensemble_vote_record(
    model_id: str,
    unit_id: str,
    label: JsonRecord,
    confidence: float,
) -> JsonRecord:
    return {
        "model_id": model_id,
        "unit_id": unit_id,
        "confidence": confidence,
        "rationale": "Fixture label rationale.",
        "raw_response_id": f"sha256:{model_id}:{unit_id}",
        "label": label,
        "signature": [
            label["fully_dismissed"],
            label["amendment_class"],
            label["ambiguous"],
            label["primary_outcome"],
            label["conditional_amendment_target"],
        ],
    }


def _write_markdown(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_authenticated_stage_b_inputs(
    *,
    root: Path,
    selection_path: Path,
    parser_path: Path,
    markdown_root: Path,
) -> list[str]:
    selection = _read_jsonl(selection_path)
    parser_rows = _read_jsonl(parser_path)
    [decision_document] = [
        document
        for document in selection[0]["documents"]
        if document["source_document_id"] == "decision"
    ]
    [decision_parser] = [
        record for record in parser_rows if record["source_document_id"] == "decision"
    ]
    markdown_path = markdown_root / decision_parser["markdown_path"]
    text = markdown_path.read_text(encoding="utf-8")
    text_sha256 = hashlib.sha256(text.encode()).hexdigest()
    decision_parser.update(
        {
            "source_sha256": "a" * 64,
            "source_byte_count": 42,
            "quality_flags": [],
            "parser_config": {
                "engine": "mistral",
                "parser_revision": EXPECTED_PARSER_REVISION,
                "expected_parser_revision": EXPECTED_PARSER_REVISION,
                "fixture_markdown": False,
            },
            "extracted_text": {
                "source_document_id": "decision",
                "extraction_method": "mistral_parser_markdown",
                "text_sha256": text_sha256,
            },
        }
    )
    _write_jsonl(parser_path, parser_rows)
    commitments = {
        "clearance_run_card_sha256": "sha256:" + "b" * 64,
        "disclosure_clearance_sha256": "sha256:" + "c" * 64,
        "download_manifest_sha256": "sha256:" + "d" * 64,
        "parser_manifest_sha256": _sha256_path(parser_path),
        "parser_run_card_sha256": "sha256:" + "e" * 64,
        "restriction_evidence_sha256": "sha256:" + "f" * 64,
        "selection_sha256": _sha256_path(selection_path),
        "selection_run_card_sha256": "sha256:" + "1" * 64,
    }
    record = {
        "schema_version": "legalforecast.decision_text.v1",
        "candidate_id": "cand-1",
        "case_id": "case-1",
        "document_id": "decision",
        "entered_date": "2026-06-30",
        "text": text,
        "is_first_written_disposition": True,
        "contains_target_outcome": True,
        "model_visible": False,
        "document_role": decision_document["document_role"],
        "docket_entry_number": decision_document["docket_entry_number"],
        "source_sha256": "a" * 64,
        "source_byte_count": 42,
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
        "decision_texts_sha256": _sha256_path(decision_texts),
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
            "decision_texts_sha256": _sha256_path(decision_texts),
            "decision_texts_manifest_sha256": _sha256_path(manifest_path),
            "input_commitments": commitments,
            "paid_activity_requested": False,
            "paid_activity_executed": False,
            "input_paths": [],
            "output_paths": [str(decision_texts), str(manifest_path)],
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


def _sha256_path(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _reseal_stage_b_bundle(
    root: Path,
    selection_path: Path,
    parser_path: Path,
) -> None:
    decision_texts_path = root / "decision-texts.jsonl"
    manifest_path = root / "decision-texts-manifest.json"
    run_card_path = root / "build-decision-texts.json"
    rows = _read_jsonl(decision_texts_path)
    manifest = json.loads(manifest_path.read_text())
    run_card = json.loads(run_card_path.read_text())
    commitments = dict(rows[0]["input_commitments"])
    commitments["selection_sha256"] = _sha256_path(selection_path)
    commitments["parser_manifest_sha256"] = _sha256_path(parser_path)
    for row in rows:
        row["input_commitments"] = commitments
    _write_jsonl(decision_texts_path, rows)
    manifest.update(
        {
            "record_count": len(rows),
            "candidate_ids_sha256": _canonical_sha256(
                [row["candidate_id"] for row in rows]
            ),
            "decision_texts_sha256": _sha256_path(decision_texts_path),
            "input_commitments": commitments,
        }
    )
    _write_json(manifest_path, manifest)
    run_card.update(
        {
            "record_count": len(rows),
            "decision_texts_sha256": _sha256_path(decision_texts_path),
            "decision_texts_manifest_sha256": _sha256_path(manifest_path),
            "input_commitments": commitments,
        }
    )
    _write_json(run_card_path, run_card)


_DECISION_TEXT = (
    "The Court rules as follows. Count I survives. Count I is dismissed. "
    "Count II is dismissed."
)


def _write_decision_texts(path: Path, *, text: str = _DECISION_TEXT) -> Path:
    _write_jsonl(
        path,
        [
            {
                "document_id": "decision",
                "entered_date": "2026-05-18",
                "text": text,
                "is_first_written_disposition": True,
            }
        ],
    )
    return path


def _write_jsonl(path: Path, records: list[JsonRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(f"{json.dumps(record, sort_keys=True)}\n" for record in records),
        encoding="utf-8",
    )


def _write_json(path: Path, record: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")


def _rewrite_as_finalized(path: Path) -> None:
    finalized = apply_unitization_reviews(
        prediction_unit_records=_read_jsonl(path),
        review_records=(),
        adjudication_records=(),
    )
    _write_jsonl(path, list(finalized))


def _read_jsonl(path: Path) -> list[JsonRecord]:
    return [
        cast(JsonRecord, json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
