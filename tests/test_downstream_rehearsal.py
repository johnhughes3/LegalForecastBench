from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import urllib.request
from collections.abc import Callable
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, NoReturn, cast

import legalforecast.cli as cli_module
import pytest
from legalforecast.cli import main
from legalforecast.evals.model_registry import load_model_registry
from legalforecast.ingestion.decision_text_artifact import (
    DecisionTextArtifactError,
    VerifiedDecisionTextArtifact,
    build_fixture_rehearsal_decision_text_records,
    verify_decision_text_artifact,
)
from legalforecast.ingestion.downstream_rehearsal import (
    REHEARSAL_PROVENANCE,
    RESPONSE_FIXTURE_SCHEMA_VERSION,
    DeterministicModelFixtureTransport,
    DownstreamRehearsalError,
    fixture_provider_environ,
    load_deterministic_response_fixtures,
    run_fixture_stage_a,
    select_response_fixtures,
)
from legalforecast.labeling.llm_pipeline import (
    llm_unitize_cases,
    stage_a_structural_review_prompt_records,
    stage_a_unitization_prompt_records,
    stage_b_labeling_prompt_records,
)
from legalforecast.unitization.review import canonical_sha256

JsonRecord = dict[str, Any]
ROOT = Path(__file__).resolve().parents[1]
REHEARSAL_STAGE_COMMANDS = (
    "rehearsal-build-decision-texts",
    "rehearsal-stage-a-unitize",
    "rehearsal-stage-a-review",
    "rehearsal-stage-a-apply",
    "rehearsal-stage-b-label",
    "rehearsal-stage-b-apply",
    "rehearsal-plan-packet-inputs",
    "rehearsal-build-packets",
)


def test_response_fixture_writer_canonicalizes_prompt_digest_prefix() -> None:
    entry = SimpleNamespace(
        registry_key="openai:fixture-model",
        model_version_or_snapshot="fixture-model-v1",
    )
    digest = "a" * 64

    bare = _response_row(
        stage="llm-unitize",
        candidate_id="cand-1",
        entry=entry,
        prompt_sha256=digest,
        raw_output={"unit_seeds": []},
    )
    prefixed = _response_row(
        stage="llm-unitize",
        candidate_id="cand-1",
        entry=entry,
        prompt_sha256=f"sha256:{digest}",
        raw_output={"unit_seeds": []},
    )

    assert bare["prompt_sha256"] == f"sha256:{digest}"
    assert prefixed["prompt_sha256"] == f"sha256:{digest}"


def test_deterministic_response_fixture_transport_is_prompt_bound_and_exhaustive(
    tmp_path: Path,
) -> None:
    prompt = "fixture prompt"
    fixture_path = tmp_path / "responses.jsonl"
    fixture_path.write_text(
        json.dumps(
            {
                "schema_version": RESPONSE_FIXTURE_SCHEMA_VERSION,
                "stage": "llm-unitize",
                "candidate_id": "cand-1",
                "model_key": "openai:fixture-model",
                "prompt_sha256": _sha256_text(prompt),
                "raw_output": json.dumps({"unit_seeds": []}),
                "served_model_version": "fixture-model-v1",
                "input_tokens": 0,
                "output_tokens": 0,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    fixtures = load_deterministic_response_fixtures(fixture_path)
    selected = select_response_fixtures(
        fixtures,
        stage="llm-unitize",
        candidate_ids=("cand-1",),
        model_keys=("openai:fixture-model",),
    )
    transport = DeterministicModelFixtureTransport(
        selected,
        provider_by_model_key={"openai:fixture-model": "openai"},
        requested_model_by_model_key={"openai:fixture-model": "fixture-model-v1"},
    )
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps({"model": "fixture-model-v1", "input": prompt}).encode(),
        method="POST",
    )

    payload = transport(request, 120.0)

    assert payload["output_text"] == json.dumps({"unit_seeds": []})
    assert payload["usage"] == {"input_tokens": 0, "output_tokens": 0}
    assert transport.request_count == 1
    [trace] = transport.traces
    assert trace.prompt_sha256 == _sha256_text(prompt)
    assert trace.model_key == "openai:fixture-model"
    assert trace.to_record()["provider_call_executed"] is False
    assert trace.to_record()["official_eligible"] is False
    transport.require_exhausted()


def test_deterministic_response_fixture_transport_rejects_prompt_drift(
    tmp_path: Path,
) -> None:
    fixture_path = tmp_path / "responses.jsonl"
    fixture_path.write_text(
        json.dumps(
            {
                "schema_version": RESPONSE_FIXTURE_SCHEMA_VERSION,
                "stage": "llm-unitize",
                "candidate_id": "cand-1",
                "model_key": "openai:fixture-model",
                "prompt_sha256": _sha256_text("expected"),
                "raw_output": json.dumps({"unit_seeds": []}),
                "served_model_version": "fixture-model-v1",
                "input_tokens": 0,
                "output_tokens": 0,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    transport = DeterministicModelFixtureTransport(
        load_deterministic_response_fixtures(fixture_path),
        provider_by_model_key={"openai:fixture-model": "openai"},
        requested_model_by_model_key={"openai:fixture-model": "fixture-model-v1"},
    )
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps({"model": "fixture-model-v1", "input": "substituted"}).encode(),
        method="POST",
    )

    with pytest.raises(DownstreamRehearsalError, match="prompt commitment mismatch"):
        transport(request, 120.0)
    assert transport.request_count == 0


def test_deterministic_response_fixture_requires_exact_coverage(
    tmp_path: Path,
) -> None:
    fixture_path = tmp_path / "responses.jsonl"
    fixture_path.write_text(
        json.dumps(
            {
                "schema_version": RESPONSE_FIXTURE_SCHEMA_VERSION,
                "stage": "llm-label",
                "candidate_id": "cand-1",
                "model_key": "openai:judge",
                "prompt_sha256": _sha256_text("prompt"),
                "raw_output": json.dumps({"unit_findings": []}),
                "served_model_version": "judge-v1",
                "input_tokens": 0,
                "output_tokens": 0,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(DownstreamRehearsalError, match="coverage mismatch"):
        select_response_fixtures(
            load_deterministic_response_fixtures(fixture_path),
            stage="llm-label",
            candidate_ids=("cand-1", "cand-2"),
            model_keys=("openai:judge",),
        )


def test_deterministic_response_fixture_rejects_symlink(tmp_path: Path) -> None:
    target = tmp_path / "responses-target.jsonl"
    target.write_text("{}\n", encoding="utf-8")
    link = tmp_path / "responses.jsonl"
    link.symlink_to(target)

    with pytest.raises(DownstreamRehearsalError, match="cannot read response fixture"):
        load_deterministic_response_fixtures(link)


def test_fixture_provider_environment_is_in_memory_and_explicit() -> None:
    assert fixture_provider_environ() == {
        "OPENAI_API_KEY": "fixture-only-not-a-provider-key",
        "ANTHROPIC_API_KEY": "fixture-only-not-a-provider-key",
        "GEMINI_API_KEY": "fixture-only-not-a-provider-key",
    }


def test_exact_100_provider_free_downstream_rehearsal(
    tmp_path: Path,
    authenticated_downstream_fixture: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        _reject_network,
    )
    fixture = _write_exact_cohort_fixture(
        tmp_path,
        count=100,
        authenticated_downstream_fixture=authenticated_downstream_fixture,
    )
    output_root = fixture["output_root"]
    command = _rehearsal_command(fixture, target_count=100)

    assert main(command) == 0
    final_root = tmp_path / "rehearsal-finalized"
    assert (
        main(
            _finalize_rehearsal_command(
                fixture,
                target_count=100,
                output_root=final_root,
            )
        )
        == 0
    )

    summary = json.loads(
        (output_root / "rehearsal-final-summary.json").read_text(encoding="utf-8")
    )
    assert summary["status"] == "completed_fixture_only"
    assert summary["official_eligible"] is False
    assert summary["authorizes_freeze"] is False
    assert summary["authorizes_evaluation"] is False
    assert summary["authorizes_dispatch"] is False
    assert summary["selected_case_count"] == 100
    assert summary["finalized_case_count"] == 100
    assert summary["decision_text_count"] == 100
    assert summary["packet_case_count"] == 100
    assert summary["prediction_unit_count"] == 100
    assert summary["label_count"] == 100
    assert summary["provider_journal_created"] is False
    assert summary["provider_billing_usd"] == "0.00"
    assert summary["packet_outcome_material_excluded"] is True
    assert summary["pending_stage_a_review_count"] == 0
    assert summary["pending_stage_b_review_count"] == 0
    assert summary["provider_fixture_call_count"] == 300
    assert len(summary["fixture_traces"]) == 300
    assert all(
        trace["provider_call_executed"] is False and trace["official_eligible"] is False
        for trace in summary["fixture_traces"]
    )
    for path_text, digest in summary["output_commitments"].items():
        assert _sha256_path(Path(path_text)) == digest
    assert not (output_root / "provider-attempts.sqlite3").exists()
    corpus = json.loads(
        (final_root / "fixture-rehearsal-corpus.json").read_text(encoding="utf-8")
    )
    assert corpus["schema_version"] == "legalforecast.fixture_rehearsal_corpus.v1"
    assert corpus["clean_case_count"] == 100
    assert corpus["official_eligible"] is False
    assert corpus["authorizes_freeze"] is False
    assert corpus["authorizes_evaluation"] is False
    assert corpus["authorizes_dispatch"] is False
    packets = _read_jsonl(output_root / "rehearsal-packets.jsonl")
    assert len(packets) == 100
    assert all(
        not {
            document["source_document_id"] for document in packet["documents"]
        }.intersection(
            {f"cand-{index:03d}-decision-{index:03d}" for index in range(100)}
        )
        for packet in packets
    )
    assert all(packet["excluded_document_ids"] for packet in packets)
    decision_text_by_id = {
        row["document_id"]: row["text"]
        for row in _read_jsonl(output_root / "rehearsal-decision-texts.jsonl")
    }
    for label in _read_jsonl(output_root / "rehearsal-labels.jsonl"):
        [citation] = label["supporting_citations"]
        assert citation["excerpt"] in decision_text_by_id[citation["document_id"]]
    with pytest.raises(
        DecisionTextArtifactError,
        match="unsupported decision text manifest schema_version",
    ):
        verify_decision_text_artifact(
            decision_texts_path=output_root / "rehearsal-decision-texts.jsonl",
            manifest_path=output_root / "rehearsal-decision-texts-manifest.json",
            run_card_path=(
                output_root / "run-cards/rehearsal-build-decision-texts.json"
            ),
            selections=_read_jsonl(fixture["selection"]),
            selection_path=fixture["selection"],
            parser_records=_read_jsonl(fixture["parser_manifest"]),
            parser_manifest_path=fixture["parser_manifest"],
            finalized_unit_records=_read_jsonl(
                output_root / "rehearsal-finalized-prediction-units.jsonl"
            ),
            finalized_units_path=(
                output_root / "rehearsal-finalized-prediction-units.jsonl"
            ),
            markdown_root=fixture["markdown_root"],
        )


def test_exact_100_public_fixture_chain_reaches_fixture_only_finalization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(urllib.request, "urlopen", _reject_network)
    fixture = _write_canonical_exact_100_chain(tmp_path, monkeypatch=monkeypatch)

    for command_name in REHEARSAL_STAGE_COMMANDS:
        command = _rehearsal_command(fixture, target_count=100)
        command[1] = command_name
        assert main(command) == 0
    final_root = tmp_path / "canonical-finalized-rehearsal"
    assert (
        main(
            _finalize_rehearsal_command(
                fixture,
                target_count=100,
                output_root=final_root,
            )
        )
        == 0
    )

    purchase_card = json.loads(fixture["purchase_card"].read_text())
    assert purchase_card["paid_activity_requested"] is False
    assert purchase_card["paid_activity_executed"] is False
    expected_stage_cards = {
        "preparation_card": "prepare-target-cohort",
        "free_clearance_card": "clear-disclosures",
        "selection_card": "project-target-cohort",
        "ledger_card": "init-purchase-ledger",
        "purchase_card": "purchase-missing-recap-fetch",
        "recovery_card": "recover-purchased",
        "purchased_clearance_card": "clear-disclosures",
        "materialization_card": "materialize-cohort-documents",
        "parse_plan_card": "plan-parse-documents",
        "parser_card": "parse-documents",
    }
    for key, expected_stage in expected_stage_cards.items():
        card = json.loads(fixture[key].read_text())
        assert card["stage"] == expected_stage
        assert card["status"] == "completed"
        assert card["execute"] is True
    prior_card: Path | None = None
    for stage_name in REHEARSAL_STAGE_COMMANDS:
        stage_card = fixture["output_root"] / "run-cards" / f"{stage_name}.json"
        card = json.loads(stage_card.read_text())
        assert card["schema_version"] == "legalforecast.fixture_stage_run_card.v1"
        assert card["prior_stage"] == (prior_card.stem if prior_card else None)
        assert card["prior_stage_card_sha256"] == (
            _sha256_path(prior_card) if prior_card else None
        )
        assert card["provider_journal_created"] is False
        assert card["provider_billing_usd"] == "0.00"
        output_paths = {Path(path) for path in card["output_commitments"]}
        sidecars = {
            Path(str(path).removesuffix(".fixture-artifact.json"))
            for path in output_paths
            if str(path).endswith(".fixture-artifact.json")
        }
        assert (
            output_paths
            - {
                path
                for path in output_paths
                if str(path).endswith(".fixture-artifact.json")
            }
            == sidecars
        )
        prior_card = stage_card
    corpus = json.loads(
        (final_root / "fixture-rehearsal-corpus.json").read_text(encoding="utf-8")
    )
    assert corpus["clean_case_count"] == 100
    assert corpus["official_eligible"] is False
    assert corpus["provider_journal_created"] is False
    assert corpus["provider_billing_usd"] == "0.00"


@pytest.mark.parametrize(
    ("pending_stage", "expected_message"),
    [
        ("llm-review-stage-a", "routed units to John"),
        ("llm-label", "routed labels to John"),
    ],
)
def test_rehearsal_refuses_to_self_adjudicate_pending_review_queues(
    tmp_path: Path,
    authenticated_downstream_fixture: Any,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    pending_stage: str,
    expected_message: str,
) -> None:
    monkeypatch.setattr(urllib.request, "urlopen", _reject_network)
    fixture = _write_exact_cohort_fixture(
        tmp_path,
        count=1,
        authenticated_downstream_fixture=authenticated_downstream_fixture,
    )
    responses = _read_jsonl(fixture["responses"])
    pending = next(row for row in responses if row["stage"] == pending_stage)
    raw_output = json.loads(pending["raw_output"])
    if pending_stage == "llm-review-stage-a":
        raw_output["structural_flags"] = [
            {
                "flag_type": "combined",
                "affected_unit_ids": ["unit-000"],
                "source_document_ids": ["mtd-000"],
                "explanation": "Fixture routes this structural question to John.",
                "citation_excerpt": "Issuer 0 moves to dismiss Count I.",
            }
        ]
    else:
        raw_output["unit_findings"][0]["labeler_confidence"] = 0.10
    pending["raw_output"] = json.dumps(raw_output, sort_keys=True)
    _write_jsonl(fixture["responses"], responses)

    assert main(_rehearsal_command(fixture, target_count=1)) == 2

    assert expected_message in capsys.readouterr().err
    assert not (fixture["output_root"] / "rehearsal-final-summary.json").exists()
    assert not (fixture["output_root"] / "provider-attempts.sqlite3").exists()


def test_rehearsal_rejects_selection_digest_under_wrong_output_path(
    tmp_path: Path,
    authenticated_downstream_fixture: Any,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(urllib.request, "urlopen", _reject_network)
    fixture = _write_exact_cohort_fixture(
        tmp_path,
        count=1,
        authenticated_downstream_fixture=authenticated_downstream_fixture,
    )
    selection_card = json.loads(fixture["selection_card"].read_text())
    selection_digest = selection_card["output_commitments"].pop(
        str(fixture["selection"].resolve())
    )
    selection_card["output_commitments"][str(tmp_path / "wrong-output.jsonl")] = (
        selection_digest
    )
    _write_json(fixture["selection_card"], selection_card)

    assert main(_rehearsal_command(fixture, target_count=1)) == 2

    assert "invalid exact target-cohort selection run card" in capsys.readouterr().err
    assert not (fixture["output_root"] / "rehearsal-final-summary.json").exists()


def test_rehearsal_rejects_response_fixture_mutation_after_consumption(
    tmp_path: Path,
    authenticated_downstream_fixture: Any,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(urllib.request, "urlopen", _reject_network)
    fixture = _write_exact_cohort_fixture(
        tmp_path,
        count=1,
        authenticated_downstream_fixture=authenticated_downstream_fixture,
    )
    run_stage_b = cli_module.run_fixture_stage_b

    def mutate_after_stage_b(*args: Any, **kwargs: Any) -> Any:
        result = run_stage_b(*args, **kwargs)
        fixture["responses"].write_bytes(fixture["responses"].read_bytes() + b"\n")
        return result

    monkeypatch.setattr(cli_module, "run_fixture_stage_b", mutate_after_stage_b)

    assert main(_rehearsal_command(fixture, target_count=1)) == 2

    assert "changed during stage execution" in capsys.readouterr().err
    assert not (fixture["output_root"] / "rehearsal-final-summary.json").exists()


@pytest.mark.parametrize("input_key", ("selection", "markdown_root"))
def test_rehearsal_rejects_file_or_directory_input_mutation_during_stage(
    tmp_path: Path,
    authenticated_downstream_fixture: Any,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    input_key: str,
) -> None:
    monkeypatch.setattr(urllib.request, "urlopen", _reject_network)
    fixture = _write_exact_cohort_fixture(
        tmp_path,
        count=1,
        authenticated_downstream_fixture=authenticated_downstream_fixture,
    )
    run_stage_b = cli_module.run_fixture_stage_b

    def mutate_input_after_stage_b(*args: Any, **kwargs: Any) -> Any:
        result = run_stage_b(*args, **kwargs)
        path = fixture[input_key]
        if path.is_dir():
            (path / "late-mutation.md").write_text("changed", encoding="utf-8")
        else:
            path.write_bytes(path.read_bytes() + b"\n")
        return result

    monkeypatch.setattr(cli_module, "run_fixture_stage_b", mutate_input_after_stage_b)

    assert main(_rehearsal_command(fixture, target_count=1)) == 2
    assert "changed during stage execution" in capsys.readouterr().err
    assert not (fixture["output_root"] / "rehearsal-final-summary.json").exists()


def test_fixture_finalizer_rejects_decision_mounted_even_when_listed_excluded(
    tmp_path: Path,
    authenticated_downstream_fixture: Any,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(urllib.request, "urlopen", _reject_network)
    fixture = _write_exact_cohort_fixture(
        tmp_path,
        count=1,
        authenticated_downstream_fixture=authenticated_downstream_fixture,
    )
    assert main(_rehearsal_command(fixture, target_count=1)) == 0
    rehearsal_root = fixture["output_root"]
    packets_path = rehearsal_root / "rehearsal-packets.jsonl"
    [packet] = _read_jsonl(packets_path)
    [decision] = _read_jsonl(rehearsal_root / "rehearsal-decision-texts.jsonl")
    mounted_decision = dict(packet["documents"][0])
    mounted_decision["source_document_id"] = decision["document_id"]
    packet["documents"].append(mounted_decision)
    _write_jsonl(packets_path, [packet])
    _recommit_fixture_stage_output(
        rehearsal_root,
        artifact_path=packets_path,
        stage="rehearsal-build-packets",
    )

    assert (
        main(
            _finalize_rehearsal_command(
                fixture,
                target_count=1,
                output_root=tmp_path / "mounted-decision-finalize",
            )
        )
        == 2
    )
    assert "outcome material in a packet" in capsys.readouterr().err


@pytest.mark.parametrize(
    "relative_path",
    (
        "rehearsal-llm-unitize-audit.jsonl",
        "rehearsal-unitization-review-queue.jsonl",
        "rehearsal-stage-a-structural-flags.jsonl",
        "rehearsal-stage-a-review-audit.jsonl",
        "rehearsal-unitization-review-final.jsonl",
        "rehearsal-decision-texts-manifest.json",
        "rehearsal-decision-texts-run-card.json",
        "rehearsal-llm-label-audit.jsonl",
        "rehearsal-lawyer-review-queue.jsonl",
        "rehearsal-label-apply-audit.jsonl",
        "rehearsal-packet-build-input.jsonl",
        "rehearsal-packet-audit.jsonl",
        "rehearsal-packet-audit.jsonl.fixture-artifact.json",
        "run-cards/rehearsal-stage-a-review.json",
    ),
)
def test_fixture_finalizer_rehashes_every_committed_stage_output(
    tmp_path: Path,
    authenticated_downstream_fixture: Any,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    relative_path: str,
) -> None:
    monkeypatch.setattr(urllib.request, "urlopen", _reject_network)
    fixture = _write_exact_cohort_fixture(
        tmp_path,
        count=1,
        authenticated_downstream_fixture=authenticated_downstream_fixture,
    )
    assert main(_rehearsal_command(fixture, target_count=1)) == 0
    artifact = fixture["output_root"] / relative_path
    artifact.write_bytes(artifact.read_bytes() + b"\n")

    assert (
        main(
            _finalize_rehearsal_command(
                fixture,
                target_count=1,
                output_root=tmp_path / "tampered-finalize",
            )
        )
        == 2
    )
    assert "output commitment changed" in capsys.readouterr().err


@pytest.mark.parametrize("field", ("artifact_byte_count", "record_count"))
def test_fixture_finalizer_rejects_false_sidecar_counts_after_recommitment(
    tmp_path: Path,
    authenticated_downstream_fixture: Any,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    field: str,
) -> None:
    monkeypatch.setattr(urllib.request, "urlopen", _reject_network)
    fixture = _write_exact_cohort_fixture(
        tmp_path,
        count=1,
        authenticated_downstream_fixture=authenticated_downstream_fixture,
    )
    assert main(_rehearsal_command(fixture, target_count=1)) == 0
    rehearsal_root = fixture["output_root"]
    artifact = rehearsal_root / "rehearsal-packet-audit.jsonl"
    sidecar_path = Path(str(artifact) + ".fixture-artifact.json")
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    sidecar[field] = int(sidecar[field]) + 1
    _write_json(sidecar_path, sidecar)
    _recommit_fixture_metadata_output(
        rehearsal_root,
        metadata_path=sidecar_path,
        stage="rehearsal-build-packets",
    )

    assert (
        main(
            _finalize_rehearsal_command(
                fixture,
                target_count=1,
                output_root=tmp_path / f"false-{field}-finalize",
            )
        )
        == 2
    )
    assert "invalid fixture artifact sidecar" in capsys.readouterr().err


@pytest.mark.parametrize("mutation", ("delete", "symlink"))
def test_fixture_finalizer_rejects_missing_or_symlinked_committed_output(
    tmp_path: Path,
    authenticated_downstream_fixture: Any,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    mutation: str,
) -> None:
    monkeypatch.setattr(urllib.request, "urlopen", _reject_network)
    fixture = _write_exact_cohort_fixture(
        tmp_path,
        count=1,
        authenticated_downstream_fixture=authenticated_downstream_fixture,
    )
    assert main(_rehearsal_command(fixture, target_count=1)) == 0
    artifact = fixture["output_root"] / "rehearsal-packet-audit.jsonl"
    backup = tmp_path / "packet-audit-backup.jsonl"
    artifact.rename(backup)
    if mutation == "symlink":
        artifact.symlink_to(backup)

    assert (
        main(
            _finalize_rehearsal_command(
                fixture,
                target_count=1,
                output_root=tmp_path / f"{mutation}-finalize",
            )
        )
        == 2
    )
    assert "missing or unsafe" in capsys.readouterr().err


def test_official_finalize_corpus_rejects_rehearsal_provenance(
    tmp_path: Path,
    authenticated_downstream_fixture: Any,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(urllib.request, "urlopen", _reject_network)
    fixture = _write_exact_cohort_fixture(
        tmp_path,
        count=1,
        authenticated_downstream_fixture=authenticated_downstream_fixture,
    )
    assert main(_rehearsal_command(fixture, target_count=1)) == 0

    assert main(_official_finalize_rejection_command(fixture, tmp_path=tmp_path)) == 2

    assert (
        "official finalize-corpus rejects fixture-only rehearsal provenance"
        in capsys.readouterr().err
    )


def _rehearsal_command(fixture: dict[str, Path], *, target_count: int) -> list[str]:
    return [
        "acquisition",
        "rehearse-downstream",
        "--output-root",
        str(fixture["output_root"]),
        "--selection",
        str(fixture["selection"]),
        "--selection-run-card",
        str(fixture["selection_card"]),
        "--download-manifest",
        str(fixture["manifest"]),
        "--disclosure-clearance",
        str(fixture["clearance"]),
        "--restriction-evidence",
        str(fixture["restrictions"]),
        "--materialization-run-card",
        str(fixture["materialization_card"]),
        "--parse-plan-run-card",
        str(fixture["parse_plan_card"]),
        "--parse-requests",
        str(fixture["parse_requests"]),
        "--parser-manifest",
        str(fixture["parser_manifest"]),
        "--parser-run-card",
        str(fixture["parser_card"]),
        "--document-root",
        str(fixture["document_root"]),
        "--markdown-root",
        str(fixture["markdown_root"]),
        "--raw-html-dir",
        str(fixture["raw_html_root"]),
        "--unitizer-model-registry",
        str(fixture["unitizer_registry"]),
        "--unitizer-model-key",
        "openai:fixture-unitizer",
        "--reviewer-model-registry",
        str(fixture["reviewer_registry"]),
        "--reviewer-model-key",
        "google:fixture-reviewer",
        "--judge-model-registry",
        str(fixture["judge_registry"]),
        "--judge-model-key",
        "anthropic:fixture-judge",
        "--evaluated-model-registry",
        str(fixture["evaluated_registry"]),
        "--response-fixtures",
        str(fixture["responses"]),
        "--target-case-count",
        str(target_count),
        "--generated-at",
        "2026-07-17T00:00:00Z",
        "--execute",
        "--no-resume",
    ]


def _finalize_rehearsal_command(
    fixture: dict[str, Path], *, target_count: int, output_root: Path
) -> list[str]:
    rehearsal_root = fixture["output_root"]
    return [
        "acquisition",
        "finalize-rehearsal-corpus",
        "--output-root",
        str(output_root),
        "--rehearsal-summary",
        str(rehearsal_root / "rehearsal-final-summary.json"),
        "--rehearsal-run-card",
        str(rehearsal_root / "run-cards/rehearse-downstream.json"),
        "--selection",
        str(fixture["selection"]),
        "--prediction-units",
        str(rehearsal_root / "rehearsal-finalized-prediction-units.jsonl"),
        "--decision-texts",
        str(rehearsal_root / "rehearsal-decision-texts.jsonl"),
        "--labels",
        str(rehearsal_root / "rehearsal-labels.jsonl"),
        "--packets",
        str(rehearsal_root / "rehearsal-packets.jsonl"),
        "--target-case-count",
        str(target_count),
        "--execute",
    ]


def _official_finalize_rejection_command(
    fixture: dict[str, Path], *, tmp_path: Path
) -> list[str]:
    rehearsal_root = fixture["output_root"]
    placeholder = rehearsal_root / "rehearsal-final-summary.json"
    empty_root = tmp_path / "official-finalize-placeholder-root"
    empty_root.mkdir(exist_ok=True)
    required_paths = {
        "--selection": fixture["selection"],
        "--parser-manifest": fixture["parser_manifest"],
        "--parser-run-card": fixture["parser_card"],
        "--decision-texts": rehearsal_root / "rehearsal-decision-texts.jsonl",
        "--decision-texts-manifest": (
            rehearsal_root / "rehearsal-decision-texts-manifest.json"
        ),
        "--decision-texts-run-card": (
            rehearsal_root / "run-cards/rehearsal-build-decision-texts.json"
        ),
        "--disclosure-clearance": fixture["clearance"],
        "--markdown-root": fixture["markdown_root"],
        "--raw-html-dir": fixture["raw_html_root"],
        "--raw-artifacts-manifest": placeholder,
        "--raw-prediction-units": (
            rehearsal_root / "rehearsal-raw-prediction-units.jsonl"
        ),
        "--prediction-units": (
            rehearsal_root / "rehearsal-finalized-prediction-units.jsonl"
        ),
        "--llm-unitization-audit": (
            rehearsal_root / "rehearsal-llm-unitize-audit.jsonl"
        ),
        "--llm-unitize-run-card": placeholder,
        "--llm-unitize-provider-journal": placeholder,
        "--original-unitization-review-queue": (
            rehearsal_root / "rehearsal-unitization-review-queue.jsonl"
        ),
        "--stage-a-structural-flags": (
            rehearsal_root / "rehearsal-stage-a-structural-flags.jsonl"
        ),
        "--stage-a-structural-review-audit": (
            rehearsal_root / "rehearsal-stage-a-review-audit.jsonl"
        ),
        "--stage-a-review-run-card": placeholder,
        "--stage-a-review-provider-journal": placeholder,
        "--stage-a-review-model-registry": fixture["reviewer_registry"],
        "--unitization-review-queue": (
            rehearsal_root / "rehearsal-unitization-review-final.jsonl"
        ),
        "--unitization-review-adjudications": (
            rehearsal_root / "rehearsal-unitization-review-final.jsonl"
        ),
        "--parse-plan-run-card": fixture["parse_plan_card"],
        "--labels": rehearsal_root / "rehearsal-labels.jsonl",
        "--llm-label-audit": rehearsal_root / "rehearsal-llm-label-audit.jsonl",
        "--stage-b-judge-registry": fixture["judge_registry"],
        "--labeling-policy": placeholder,
        "--lawyer-review-queue": (
            rehearsal_root / "rehearsal-lawyer-review-queue.jsonl"
        ),
        "--lawyer-review-audit": (rehearsal_root / "rehearsal-label-apply-audit.jsonl"),
        "--packet-build-input": (rehearsal_root / "rehearsal-packet-build-input.jsonl"),
        "--packets": rehearsal_root / "rehearsal-packets.jsonl",
        "--model-registry": fixture["evaluated_registry"],
        "--screened-cases": placeholder,
        "--discovery-summary": placeholder,
        "--discovery-exclusions": placeholder,
        "--screening-snapshot-manifest": placeholder,
        "--screening-cycle-store": placeholder,
        "--target-cohort-preparation-root": empty_root,
    }
    command = [
        "acquisition",
        "finalize-corpus",
        "--output-root",
        str(tmp_path / "official-finalize-rejected"),
        "--stage-a-review-model-key",
        "google:fixture-reviewer",
        "--expected-model-registry-sha256",
        "0" * 64,
    ]
    for option, path in required_paths.items():
        command.extend((option, str(path)))
    return command


def _write_canonical_exact_100_chain(
    tmp_path: Path, *, monkeypatch: pytest.MonkeyPatch
) -> dict[str, Path]:
    helpers = cast(Any, _target_100_helpers())
    fixture_setup = cast(
        Callable[[pytest.MonkeyPatch], None],
        helpers._allow_cryptographic_service_identity_in_fixtures.__wrapped__,
    )
    fixture_setup(monkeypatch)
    preparation = tmp_path / "canonical-preparation"
    snapshot, cycle_hash, fixture_documents, courtlistener_fixture = (
        helpers._target_100_fixture(tmp_path / "canonical-fixture", case_count=100)
    )
    assert (
        main(
            [
                "acquisition",
                "prepare-target-cohort",
                "--output-root",
                str(preparation),
                "--snapshot",
                str(snapshot),
                "--expected-cycle-hash",
                str(cycle_hash),
                "--target-case-count",
                "100",
                "--fixture-documents",
                str(fixture_documents),
                "--courtlistener-fixture",
                str(courtlistener_fixture),
                "--use-embedded-entries",
                "--execute",
            ]
        )
        == 0
    )
    free_manifest = preparation / "03c-merged-downloads/document-downloads-merged.jsonl"
    free_restrictions = preparation / "06-clearance-inputs/restriction-evidence.jsonl"
    free_review = helpers._write_authenticated_reviews(
        tmp_path / "canonical-free-review",
        manifest_path=free_manifest,
        document_root=preparation / "documents/free",
        review_requests_path=(
            preparation / "06-clearance-inputs/disclosure-review-requests.jsonl"
        ),
        restriction_evidence_path=free_restrictions,
        store_uri="private-store://fixture/exact-100-free",
    )
    free_clearance_root = tmp_path / "canonical-free-clearance"
    assert (
        main(
            [
                "acquisition",
                "clear-disclosures",
                "--download-manifest",
                str(free_manifest),
                "--review-requests",
                str(free_review.requests),
                "--document-root",
                str(preparation / "documents/free"),
                "--review-worksheet",
                str(free_review.worksheet),
                "--reviews",
                str(free_review.reviews),
                "--review-receipt",
                str(free_review.receipt),
                "--reviewer-policy",
                str(free_review.policy),
                "--cohort-policy",
                str(free_review.cohort_policy),
                "--restriction-evidence",
                str(free_restrictions),
                "--output-root",
                str(free_clearance_root),
                "--execute",
            ]
        )
        == 0
    )
    projection = tmp_path / "canonical-projection"
    assert (
        main(
            [
                "acquisition",
                "project-target-cohort",
                "--output-root",
                str(projection),
                "--selection",
                str(
                    preparation
                    / "03-gap-bridge/public-packet-selection-reconciled.jsonl"
                ),
                "--case-relevance",
                str(preparation / "03-gap-bridge/case-relevance.jsonl"),
                "--download-manifest",
                str(free_manifest),
                "--disclosure-clearance",
                str(free_clearance_root / "disclosure-clearance.jsonl"),
                "--clearance-run-card",
                str(free_clearance_root / "run-cards/clear-disclosures.json"),
                "--restriction-evidence",
                str(free_restrictions),
                "--preparation-summary",
                str(preparation / "target-cohort-preparation-summary.json"),
                "--preparation-config",
                str(preparation / "target-cohort-config.json"),
                "--snapshot-manifest",
                str(snapshot / "manifest.json"),
                "--target-case-count",
                "100",
                "--execute",
            ]
        )
        == 0
    )
    selection = projection / "target-cohort-selection.jsonl"
    budget_plan = projection / "missing-core-budget-plan.json"
    purchase_policy_root = tmp_path / "canonical-purchase-policy"
    purchase_policy_root.mkdir()
    _, cohort_policy, purchase_ledger = helpers._purchase_policies(purchase_policy_root)
    cohort = json.loads(cohort_policy.read_text(encoding="utf-8"))
    purchase_decisions = purchase_policy_root / "purchase-policy-decisions.json"
    _write_json(
        purchase_decisions,
        {
            "cycle_id": "cycle-1",
            "cohort_policy_sha256": cohort["policy_sha256"],
            "canonical_ledger_path": str(purchase_ledger.resolve()),
            "hard_cap_usd": "2250.00",
            "opening_committed_spend_usd": "0.00",
            "opening_case_committed_spend_usd": {},
            "max_per_case_usd": "73.20",
            "per_document_reservation_usd": "3.05",
            "fee_schedule": {
                "source_citation": (
                    "https://www.courtlistener.com/help/coverage/recap/"
                ),
                "verified_at_utc": "2026-07-14T00:00:00Z",
                "includes_pacer_fees": True,
                "includes_service_fees": True,
                "includes_rounding": True,
            },
        },
    )
    purchase_policy = purchase_policy_root / "purchase-policy-cli.json"
    assert (
        main(
            [
                "acquisition",
                "generate-purchase-policy",
                "--decisions",
                str(purchase_decisions),
                "--output",
                str(purchase_policy),
                "--cohort-policy",
                str(cohort_policy),
            ]
        )
        == 0
    )
    broker_policy = tmp_path / "canonical-recap-fetch-broker-policy.json"
    assert (
        main(
            [
                "acquisition",
                "generate-recap-fetch-broker-policy",
                "--purchase-policy",
                str(purchase_policy),
                "--cohort-policy",
                str(cohort_policy),
                "--budget-plan",
                str(budget_plan),
                "--selection",
                str(selection),
                "--output",
                str(broker_policy),
            ]
        )
        == 0
    )
    allowed_document_ids = [
        str(record["recap_document"])
        for record in json.loads(broker_policy.read_text())["allowed_documents"]
    ]
    purchase_fixture_root = tmp_path / "canonical-purchase-fixtures"
    purchase_fixture_root.mkdir()
    courtlistener_purchase_fixture, broker_fixture = helpers._purchase_fixtures(
        purchase_fixture_root, allowed_document_ids
    )
    ledger_root = tmp_path / "canonical-ledger-init"
    assert (
        main(
            [
                "acquisition",
                "init-purchase-ledger",
                "--purchase-policy",
                str(purchase_policy),
                "--cohort-policy",
                str(cohort_policy),
                "--purchase-ledger",
                str(purchase_ledger),
                "--output-root",
                str(ledger_root),
                "--execute",
            ]
        )
        == 0
    )

    def reject_live_transport(*args: object, **kwargs: object) -> NoReturn:
        del args, kwargs
        raise AssertionError("fixture purchase constructed a production transport")

    monkeypatch.setattr(cli_module, "UrlLibRecapFetchTransport", reject_live_transport)
    monkeypatch.setattr(
        cli_module, "SignedRecapFetchPurchaseBroker", reject_live_transport
    )
    purchase_root = tmp_path / "canonical-offline-purchase"
    assert (
        main(
            [
                "acquisition",
                "purchase-missing-recap-fetch",
                "--output-root",
                str(purchase_root),
                "--budget-plan",
                str(budget_plan),
                "--selection",
                str(selection),
                "--purchase-policy",
                str(purchase_policy),
                "--cohort-policy",
                str(cohort_policy),
                "--purchase-ledger",
                str(purchase_ledger),
                "--courtlistener-fixture",
                str(courtlistener_purchase_fixture),
                "--purchase-broker-fixture",
                str(broker_fixture),
                "--execute",
                "--acknowledge-pacer-fees",
            ]
        )
        == 0
    )
    purchase_result = purchase_root / "courtlistener-recap-fetch-purchases.json"
    purchase_attempts = json.loads(purchase_result.read_text())["attempts"]
    purchased_fixture = tmp_path / "canonical-purchased-pdfs.json"
    purchased_fixture.write_text(
        json.dumps(
            {
                str(attempt["download_url"]): helpers._fixture_pdf_text(
                    "Defendant moves to dismiss Count I."
                )
                for attempt in purchase_attempts
            }
        ),
        encoding="utf-8",
    )
    recovery = tmp_path / "canonical-recovery"
    assert (
        main(
            [
                "acquisition",
                "recover-purchased",
                "--purchase-result",
                str(purchase_result),
                "--selection",
                str(selection),
                "--output-root",
                str(recovery),
                "--fixture-documents",
                str(purchased_fixture),
                "--execute",
            ]
        )
        == 0
    )
    purchased_manifest = recovery / "purchased-document-downloads.jsonl"
    purchased_restrictions = tmp_path / "canonical-purchased-restrictions.jsonl"
    _write_jsonl(
        purchased_restrictions,
        [
            {
                "candidate_id": row["candidate_id"],
                "source_document_id": row["source_document_id"],
                "restriction_status": "public",
                "restriction_evidence": ["courtlistener_recap_fetch_public_fixture"],
                "is_sealed": False,
                "is_private": False,
            }
            for row in _read_jsonl(purchased_manifest)
        ],
    )
    purchased_review = helpers._write_authenticated_reviews(
        tmp_path / "canonical-purchased-review",
        manifest_path=purchased_manifest,
        document_root=recovery / "documents/purchased",
        restriction_evidence_path=purchased_restrictions,
        store_uri="private-store://fixture/exact-100-purchased",
    )
    purchased_clearance_root = tmp_path / "canonical-purchased-clearance"
    assert (
        main(
            [
                "acquisition",
                "clear-disclosures",
                "--download-manifest",
                str(purchased_manifest),
                "--review-requests",
                str(purchased_review.requests),
                "--document-root",
                str(recovery / "documents/purchased"),
                "--review-worksheet",
                str(purchased_review.worksheet),
                "--reviews",
                str(purchased_review.reviews),
                "--review-receipt",
                str(purchased_review.receipt),
                "--reviewer-policy",
                str(purchased_review.policy),
                "--cohort-policy",
                str(purchased_review.cohort_policy),
                "--restriction-evidence",
                str(purchased_restrictions),
                "--output-root",
                str(purchased_clearance_root),
                "--execute",
            ]
        )
        == 0
    )
    materialized = tmp_path / "canonical-materialized"
    assert (
        main(
            [
                "acquisition",
                "materialize-cohort-documents",
                "--output-root",
                str(materialized),
                "--preparation-root",
                str(preparation),
                "--preparation-summary",
                str(preparation / "target-cohort-preparation-summary.json"),
                "--preparation-config",
                str(preparation / "target-cohort-config.json"),
                "--snapshot-manifest",
                str(snapshot / "manifest.json"),
                "--target-cohort-root",
                str(projection),
                "--free-disclosure-clearance",
                str(projection / "disclosure-clearance.jsonl"),
                "--purchased-recovery-root",
                str(recovery),
                "--purchased-disclosure-clearance",
                str(purchased_clearance_root / "disclosure-clearance.jsonl"),
                "--purchased-clearance-run-card",
                str(purchased_clearance_root / "run-cards/clear-disclosures.json"),
                "--purchase-policy",
                str(purchase_policy),
                "--cohort-policy",
                str(cohort_policy),
                "--purchase-ledger",
                str(purchase_ledger),
                "--execute",
            ]
        )
        == 0
    )
    parse_root = tmp_path / "canonical-parse"
    materialization_card = materialized / "run-cards/materialize-cohort-documents.json"
    assert (
        main(
            [
                "acquisition",
                "plan-parse-documents",
                "--output-root",
                str(parse_root),
                "--selection",
                str(selection),
                "--download-manifest",
                str(materialized / "document-downloads-merged.jsonl"),
                "--disclosure-clearance",
                str(materialized / "disclosure-clearance.jsonl"),
                "--materialization-run-card",
                str(materialization_card),
                "--document-root",
                str(materialized / "documents"),
                "--execute",
            ]
        )
        == 0
    )
    fixture_markdown = tmp_path / "canonical-fixture-markdown"
    fixture_markdown.mkdir()
    for selection_record in _read_jsonl(selection):
        for document in selection_record["documents"]:
            document_id = str(document["source_document_id"])
            role = str(document["document_role"])
            if document.get("contains_target_outcome") is True:
                text = (
                    "The motion to dismiss Count I is granted without leave to amend."
                )
            elif "complaint" in role:
                text = "Count I alleges fraud against Defendant."
            else:
                text = "Defendant moves to dismiss Count I."
            (fixture_markdown / f"{document_id}.md").write_text(text, encoding="utf-8")
    assert (
        main(
            [
                "acquisition",
                "parse-documents",
                "--output-root",
                str(parse_root),
                "--selection",
                str(selection),
                "--requests",
                str(parse_root / "parse-document-requests.jsonl"),
                "--disclosure-clearance",
                str(materialized / "disclosure-clearance.jsonl"),
                "--materialization-run-card",
                str(materialization_card),
                "--fixture-markdown-dir",
                str(fixture_markdown),
                "--execute",
            ]
        )
        == 0
    )
    snapshot_raw = _read_jsonl(snapshot / "raw-artifacts.jsonl")
    raw_html_root = Path(str(snapshot_raw[0]["path"])).parent
    output_root = tmp_path / "canonical-rehearsal-output"
    output_root.mkdir()
    paths = {
        "output_root": output_root,
        "document_root": materialized / "documents",
        "markdown_root": parse_root / "markdown",
        "raw_html_root": raw_html_root,
        "selection": selection,
        "selection_card": projection / "run-cards/project-target-cohort.json",
        "manifest": materialized / "document-downloads-merged.jsonl",
        "clearance": materialized / "disclosure-clearance.jsonl",
        "restrictions": materialized / "restriction-evidence.jsonl",
        "materialization_card": materialization_card,
        "parse_plan_card": parse_root / "run-cards/plan-parse-documents.json",
        "parse_requests": parse_root / "parse-document-requests.jsonl",
        "parser_manifest": parse_root / "mistral-markdown-conversions.jsonl",
        "parser_card": parse_root / "run-cards/parse-documents.json",
        "unitizer_registry": tmp_path / "canonical-unitizer-registry.json",
        "reviewer_registry": tmp_path / "canonical-reviewer-registry.json",
        "judge_registry": tmp_path / "canonical-judge-registry.json",
        "evaluated_registry": tmp_path / "canonical-evaluated-registry.json",
        "responses": tmp_path / "canonical-responses.jsonl",
        "preparation_card": preparation / "run-cards/prepare-target-cohort.json",
        "free_clearance_card": (
            free_clearance_root / "run-cards/clear-disclosures.json"
        ),
        "ledger_card": ledger_root / "run-cards/init-purchase-ledger.json",
        "purchase_card": purchase_root / "run-cards/purchase-missing-recap-fetch.json",
        "recovery_card": recovery / "run-cards/recover-purchased.json",
        "purchased_clearance_card": (
            purchased_clearance_root / "run-cards/clear-disclosures.json"
        ),
    }
    _write_generic_response_fixtures(paths)
    return paths


def _write_exact_cohort_fixture(
    tmp_path: Path,
    *,
    count: int,
    authenticated_downstream_fixture: Any,
) -> dict[str, Path]:
    output_root = tmp_path / "rehearsal-output"
    document_root = tmp_path / "documents"
    fixture_markdown_root = tmp_path / "fixture-markdown"
    parse_root = tmp_path / "parse"
    markdown_root = parse_root / "markdown"
    raw_html_root = tmp_path / "raw-html"
    for root in (
        output_root,
        document_root,
        fixture_markdown_root,
        raw_html_root,
    ):
        root.mkdir(parents=True)
    selections: list[JsonRecord] = []
    downloads: list[JsonRecord] = []
    clearances: list[JsonRecord] = []
    restrictions: list[JsonRecord] = []
    for index in range(count):
        candidate_id = f"cand-{index:03d}"
        case_id = f"case-{index:03d}"
        complaint_id = f"complaint-{index:03d}"
        motion_id = f"mtd-{index:03d}"
        decision_id = f"decision-{index:03d}"
        documents = [
            _selection_document(candidate_id, complaint_id, "complaint", 1, True),
            _selection_document(
                candidate_id,
                motion_id,
                "motion_to_dismiss_memorandum",
                5,
                True,
            ),
            _selection_document(
                candidate_id,
                decision_id,
                "decision",
                16,
                False,
                contains_target_outcome=True,
            ),
        ]
        selections.append(
            {
                "candidate_id": candidate_id,
                "case_id": case_id,
                "decision_date": "2026-07-01",
                "case_name": f"Plaintiff {index} v. Issuer {index}",
                "court": "S.D.N.Y.",
                "docket_number": f"1:26-cv-{index + 1:05d}",
                "source_url": f"https://www.courtlistener.com/docket/{index + 1}/",
                "target_motion_entry_numbers": [5],
                "decision_entry_numbers": [16],
                "selected": True,
                "documents": documents,
            }
        )
        text_by_document = {
            complaint_id: f"Count I alleges fraud against Issuer {index}.",
            motion_id: f"Issuer {index} moves to dismiss Count I.",
            decision_id: (
                f"The motion to dismiss Count I against Issuer {index} is granted "
                "without leave to amend."
            ),
        }
        for document in documents:
            document_id = str(document["source_document_id"])
            content = f"%PDF fixture {candidate_id} {document_id}".encode()
            local_path = Path(candidate_id) / f"{document_id}.pdf"
            source_path = document_root / local_path
            source_path.parent.mkdir(parents=True, exist_ok=True)
            source_path.write_bytes(content)
            digest = hashlib.sha256(content).hexdigest()
            downloads.append(
                {
                    "candidate_id": candidate_id,
                    "source_provider": "courtlistener",
                    "source_document_id": document_id,
                    "docket_entry_number": document["docket_entry_number"],
                    "document_role": document["document_role"],
                    "source_url": f"https://storage.courtlistener.com/{document_id}.pdf",
                    "local_path": str(local_path),
                    "sha256": digest,
                    "byte_count": len(content),
                    "free_or_purchased": "free",
                    "retrieved_at": "2026-07-17T00:00:00Z",
                    "retry_count": 0,
                    "rate_limited": False,
                    "reused_existing": False,
                }
            )
            clearance = {
                "schema_version": "legalforecast.disclosure_clearance.v1",
                "candidate_id": candidate_id,
                "source_document_id": document_id,
                "sha256": digest,
                "byte_count": len(content),
                "status": "cleared",
                "restriction_status": "public",
                "restriction_evidence": ["fixture-only public docket"],
                "reviewer_id": "fixture:john",
                "controlled_store_provenance": "private-store://fixture/review",
                "reviewed_at": "2026-07-17T00:00:00Z",
                "free_or_purchased": "free",
            }
            clearances.append(clearance)
            restrictions.append(
                {
                    "candidate_id": candidate_id,
                    "source_document_id": document_id,
                    "restriction_status": "public",
                    "restriction_evidence": ["fixture-only public docket"],
                    "is_sealed": False,
                    "is_private": False,
                }
            )
            markdown = text_by_document[document_id]
            (fixture_markdown_root / f"{document_id}.md").write_text(
                markdown, encoding="utf-8"
            )
        (raw_html_root / f"{candidate_id}.html").write_text(
            _docket_html(index), encoding="utf-8"
        )

    paths = {
        "output_root": output_root,
        "document_root": document_root,
        "markdown_root": markdown_root,
        "raw_html_root": raw_html_root,
        "selection": tmp_path / "selection.jsonl",
        "selection_card": tmp_path / "selection-card.json",
        "manifest": tmp_path / "manifest.jsonl",
        "clearance": tmp_path / "clearance.jsonl",
        "restrictions": tmp_path / "restrictions.jsonl",
        "materialization_card": tmp_path / "materialization-card.json",
        "parse_plan_card": parse_root / "run-cards/plan-parse-documents.json",
        "parse_requests": parse_root / "parse-document-requests.jsonl",
        "parser_manifest": parse_root / "mistral-markdown-conversions.jsonl",
        "parser_card": parse_root / "run-cards/parse-documents.json",
        "unitizer_registry": tmp_path / "unitizer-registry.json",
        "reviewer_registry": tmp_path / "reviewer-registry.json",
        "judge_registry": tmp_path / "judge-registry.json",
        "evaluated_registry": tmp_path / "evaluated-registry.json",
        "responses": tmp_path / "responses.jsonl",
    }
    _write_jsonl(paths["selection"], selections)
    _write_jsonl(paths["manifest"], downloads)
    _write_jsonl(paths["clearance"], clearances)
    _write_jsonl(paths["restrictions"], restrictions)
    paths["materialization_card"] = authenticated_downstream_fixture.materialize(
        manifest=paths["manifest"],
        clearance=paths["clearance"],
        document_root=document_root,
        selection=paths["selection"],
        name="exact-100-rehearsal",
    )
    _write_json(
        paths["selection_card"],
        {
            "stage": "project-target-cohort",
            "status": "completed",
            "execute": True,
            "record_count": count,
            "output_commitments": {
                str(paths["selection"].resolve()): _sha256_path(paths["selection"])
            },
        },
    )
    assert (
        main(
            [
                "acquisition",
                "plan-parse-documents",
                "--output-root",
                str(parse_root),
                "--selection",
                str(paths["selection"]),
                "--download-manifest",
                str(paths["manifest"]),
                "--disclosure-clearance",
                str(paths["clearance"]),
                "--materialization-run-card",
                str(paths["materialization_card"]),
                "--document-root",
                str(document_root),
                "--execute",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "acquisition",
                "parse-documents",
                "--output-root",
                str(parse_root),
                "--selection",
                str(paths["selection"]),
                "--requests",
                str(paths["parse_requests"]),
                "--disclosure-clearance",
                str(paths["clearance"]),
                "--materialization-run-card",
                str(paths["materialization_card"]),
                "--fixture-markdown-dir",
                str(fixture_markdown_root),
                "--execute",
            ]
        )
        == 0
    )
    parser_records = _read_jsonl(paths["parser_manifest"])
    _write_json(
        paths["unitizer_registry"], [_registry_record("openai", "fixture-unitizer")]
    )
    _write_json(
        paths["reviewer_registry"], [_registry_record("google", "fixture-reviewer")]
    )
    _write_json(
        paths["judge_registry"], [_registry_record("anthropic", "fixture-judge")]
    )
    _write_json(
        paths["evaluated_registry"], [_registry_record("openai", "evaluated-model")]
    )

    unitizer = load_model_registry(paths["unitizer_registry"]).entries[0]
    reviewer = load_model_registry(paths["reviewer_registry"]).entries[0]
    unit_fixture_rows: list[JsonRecord] = []
    for prompt in stage_a_unitization_prompt_records(
        selection_records=selections,
        parser_records=parser_records,
        markdown_root=markdown_root,
    ):
        index = int(str(prompt["candidate_id"]).rsplit("-", 1)[-1])
        unit_fixture_rows.append(
            _response_row(
                stage="llm-unitize",
                candidate_id=str(prompt["candidate_id"]),
                entry=unitizer,
                prompt_sha256=str(prompt["prompt_sha256"]),
                raw_output={
                    "unit_seeds": [
                        {
                            "unit_id": f"unit-{index:03d}",
                            "count": "Count I",
                            "claim_name": "Fraud",
                            "defendant_names": [f"Issuer {index}"],
                            "source_document_ids": [
                                f"complaint-{index:03d}",
                                f"mtd-{index:03d}",
                            ],
                            "challenged_by_motion": True,
                            "challenge_scope": "entire_claim",
                            "unit_confidence": 0.99,
                            "grouping": "individual",
                            "grouping_rationale": None,
                            "separable_subclaim": None,
                            "uncertainty_notes": None,
                            "citation_excerpt": (
                                f"Issuer {index} moves to dismiss Count I."
                            ),
                        }
                    ]
                },
            )
        )
    _write_jsonl(paths["responses"], unit_fixture_rows)
    unit_transport = DeterministicModelFixtureTransport(
        load_deterministic_response_fixtures(paths["responses"]),
        provider_by_model_key={unitizer.registry_key: unitizer.provider},
        requested_model_by_model_key={unitizer.registry_key: unitizer.model_id},
    )
    unitized = llm_unitize_cases(
        selection_records=selections,
        parser_records=parser_records,
        markdown_root=markdown_root,
        registry_entry=unitizer,
        transport=unit_transport,
        environ=fixture_provider_environ(),
    )
    review_rows = [
        _response_row(
            stage="llm-review-stage-a",
            candidate_id=str(prompt["candidate_id"]),
            entry=reviewer,
            prompt_sha256="sha256:"
            + str(prompt["prompt_sha256"]).removeprefix("sha256:"),
            raw_output={"structural_flags": []},
        )
        for prompt in stage_a_structural_review_prompt_records(
            selection_records=selections,
            parser_records=parser_records,
            prediction_unit_records=unitized.records,
            markdown_root=markdown_root,
        )
    ]
    _write_jsonl(paths["responses"], [*unit_fixture_rows, *review_rows])
    stage_a = run_fixture_stage_a(
        selection_records=selections,
        parser_records=parser_records,
        markdown_root=markdown_root,
        unitizer_entry=unitizer,
        unitizer_registry_sha256=_sha256_path(paths["unitizer_registry"]),
        reviewer_entry=reviewer,
        reviewer_registry_sha256=_sha256_path(paths["reviewer_registry"]),
        fixtures=load_deterministic_response_fixtures(paths["responses"]),
    )
    commitments = {
        "selection_sha256": _sha256_path(paths["selection"]),
        "selection_run_card_sha256": _sha256_path(paths["selection_card"]),
        "download_manifest_sha256": _sha256_path(paths["manifest"]),
        "disclosure_clearance_sha256": _sha256_path(paths["clearance"]),
        "clearance_run_card_sha256": _sha256_path(paths["materialization_card"]),
        "restriction_evidence_sha256": _sha256_path(paths["restrictions"]),
        "parser_manifest_sha256": _sha256_path(paths["parser_manifest"]),
        "parser_run_card_sha256": _sha256_path(paths["parser_card"]),
    }
    decisions = build_fixture_rehearsal_decision_text_records(
        selections=selections,
        download_manifest=downloads,
        clearance_records=clearances,
        restriction_records=restrictions,
        parser_records=parser_records,
        markdown_root=markdown_root,
        input_commitments=commitments,
    )
    prompt_artifact_root = tmp_path / "prompt-artifacts"
    finalized_path = prompt_artifact_root / "finalized-prediction-units.jsonl"
    decision_path = prompt_artifact_root / "decision-texts.jsonl"
    decision_manifest_path = prompt_artifact_root / "decision-texts-manifest.json"
    decision_card_path = prompt_artifact_root / "build-decision-texts.json"
    _write_jsonl(finalized_path, list(stage_a.finalized_prediction_units))
    _write_jsonl(decision_path, list(decisions))
    candidate_ids = tuple(str(row["candidate_id"]) for row in selections)
    _write_json(
        decision_manifest_path,
        {
            **REHEARSAL_PROVENANCE,
            "schema_version": "legalforecast.fixture_decision_text_manifest.v1",
            "record_count": len(decisions),
            "decision_texts_sha256": _sha256_path(decision_path),
            "candidate_ids_sha256": "sha256:"
            + hashlib.sha256(
                json.dumps(candidate_ids, separators=(",", ":")).encode()
            ).hexdigest(),
            "input_commitments": commitments,
            "outcome_material_model_visible": False,
        },
    )
    _write_json(
        decision_card_path,
        {
            **REHEARSAL_PROVENANCE,
            "schema_version": "legalforecast.fixture_acquisition_run_card.v1",
            "stage": "rehearsal-build-decision-texts",
            "status": "completed",
            "execute": True,
            "record_count": len(decisions),
            "decision_texts_sha256": _sha256_path(decision_path),
            "decision_texts_manifest_sha256": _sha256_path(decision_manifest_path),
            "input_commitments": commitments,
            "provider_call_executed": False,
        },
    )
    artifact = VerifiedDecisionTextArtifact(
        records=decisions,
        decision_texts_sha256=_sha256_path(decision_path),
        manifest_sha256=_sha256_path(decision_manifest_path),
        run_card_sha256=_sha256_path(decision_card_path),
        finalized_prediction_units_sha256=_sha256_path(finalized_path),
        finalized_unit_envelope_sha256s={
            str(row["candidate_id"]): "sha256:" + canonical_sha256(row)
            for row in stage_a.finalized_prediction_units
        },
        input_commitments=commitments,
    )
    judge = load_model_registry(paths["judge_registry"]).entries[0]
    label_rows: list[JsonRecord] = []
    decision_by_candidate = {str(row["candidate_id"]): row for row in decisions}
    unit_by_candidate = {
        str(row["candidate_id"]): row["prediction_units"][0]
        for row in stage_a.finalized_prediction_units
    }
    for prompt in stage_b_labeling_prompt_records(
        selection_records=selections,
        prediction_unit_records=stage_a.finalized_prediction_units,
        decision_text_artifact=artifact,
    ):
        candidate_id = str(prompt["candidate_id"])
        label_rows.append(
            _response_row(
                stage="llm-label",
                candidate_id=candidate_id,
                entry=judge,
                prompt_sha256=str(prompt["prompt_sha256"]),
                raw_output={
                    "unit_findings": [
                        {
                            "unit_id": unit_by_candidate[candidate_id]["unit_id"],
                            "resolution": "fully_dismissed",
                            "amendment_signal": "express_denial_of_leave",
                            "supporting_excerpt": decision_by_candidate[candidate_id][
                                "text"
                            ],
                            "labeler_confidence": 0.99,
                        }
                    ],
                    "missing_unit_flags": [],
                },
            )
        )
    _write_jsonl(paths["responses"], [*unit_fixture_rows, *review_rows, *label_rows])
    return paths


def _write_generic_response_fixtures(paths: dict[str, Path]) -> None:
    selections = _read_jsonl(paths["selection"])
    parser_records = _read_jsonl(paths["parser_manifest"])
    downloads = _read_jsonl(paths["manifest"])
    clearances = _read_jsonl(paths["clearance"])
    restrictions = _read_jsonl(paths["restrictions"])
    markdown_root = paths["markdown_root"]
    _write_json(
        paths["unitizer_registry"], [_registry_record("openai", "fixture-unitizer")]
    )
    _write_json(
        paths["reviewer_registry"], [_registry_record("google", "fixture-reviewer")]
    )
    _write_json(
        paths["judge_registry"], [_registry_record("anthropic", "fixture-judge")]
    )
    _write_json(
        paths["evaluated_registry"], [_registry_record("openai", "evaluated-model")]
    )
    unitizer = load_model_registry(paths["unitizer_registry"]).entries[0]
    reviewer = load_model_registry(paths["reviewer_registry"]).entries[0]
    selection_by_candidate = {
        str(record["candidate_id"]): record for record in selections
    }
    unit_ids = {
        str(record["candidate_id"]): f"unit-{index:03d}"
        for index, record in enumerate(selections)
    }
    unit_fixture_rows: list[JsonRecord] = []
    for prompt in stage_a_unitization_prompt_records(
        selection_records=selections,
        parser_records=parser_records,
        markdown_root=markdown_root,
    ):
        candidate_id = str(prompt["candidate_id"])
        selection = selection_by_candidate[candidate_id]
        visible_documents = [
            document
            for document in selection["documents"]
            if document.get("model_visible") is True
        ]
        complaint = next(
            document
            for document in visible_documents
            if "complaint" in str(document["document_role"])
        )
        motion = next(
            document
            for document in visible_documents
            if "motion_to_dismiss" in str(document["document_role"])
        )
        unit_fixture_rows.append(
            _response_row(
                stage="llm-unitize",
                candidate_id=candidate_id,
                entry=unitizer,
                prompt_sha256=str(prompt["prompt_sha256"]),
                raw_output={
                    "unit_seeds": [
                        {
                            "unit_id": unit_ids[candidate_id],
                            "count": "Count I",
                            "claim_name": "Fraud",
                            "defendant_names": ["Defendant"],
                            "source_document_ids": [
                                str(complaint["source_document_id"]),
                                str(motion["source_document_id"]),
                            ],
                            "challenged_by_motion": True,
                            "challenge_scope": "entire_claim",
                            "unit_confidence": 0.99,
                            "grouping": "individual",
                            "grouping_rationale": None,
                            "separable_subclaim": None,
                            "uncertainty_notes": None,
                            "citation_excerpt": ("Defendant moves to dismiss Count I."),
                        }
                    ]
                },
            )
        )
    _write_jsonl(paths["responses"], unit_fixture_rows)
    unit_transport = DeterministicModelFixtureTransport(
        load_deterministic_response_fixtures(paths["responses"]),
        provider_by_model_key={unitizer.registry_key: unitizer.provider},
        requested_model_by_model_key={unitizer.registry_key: unitizer.model_id},
    )
    unitized = llm_unitize_cases(
        selection_records=selections,
        parser_records=parser_records,
        markdown_root=markdown_root,
        registry_entry=unitizer,
        transport=unit_transport,
        environ=fixture_provider_environ(),
    )
    review_rows = [
        _response_row(
            stage="llm-review-stage-a",
            candidate_id=str(prompt["candidate_id"]),
            entry=reviewer,
            prompt_sha256=str(prompt["prompt_sha256"]),
            raw_output={"structural_flags": []},
        )
        for prompt in stage_a_structural_review_prompt_records(
            selection_records=selections,
            parser_records=parser_records,
            prediction_unit_records=unitized.records,
            markdown_root=markdown_root,
        )
    ]
    _write_jsonl(paths["responses"], [*unit_fixture_rows, *review_rows])
    stage_a = run_fixture_stage_a(
        selection_records=selections,
        parser_records=parser_records,
        markdown_root=markdown_root,
        unitizer_entry=unitizer,
        unitizer_registry_sha256=_sha256_path(paths["unitizer_registry"]),
        reviewer_entry=reviewer,
        reviewer_registry_sha256=_sha256_path(paths["reviewer_registry"]),
        fixtures=load_deterministic_response_fixtures(paths["responses"]),
    )
    commitments = {
        "selection_sha256": _sha256_path(paths["selection"]),
        "selection_run_card_sha256": _sha256_path(paths["selection_card"]),
        "download_manifest_sha256": _sha256_path(paths["manifest"]),
        "disclosure_clearance_sha256": _sha256_path(paths["clearance"]),
        "clearance_run_card_sha256": _sha256_path(paths["materialization_card"]),
        "restriction_evidence_sha256": _sha256_path(paths["restrictions"]),
        "parser_manifest_sha256": _sha256_path(paths["parser_manifest"]),
        "parser_run_card_sha256": _sha256_path(paths["parser_card"]),
    }
    decisions = build_fixture_rehearsal_decision_text_records(
        selections=selections,
        download_manifest=downloads,
        clearance_records=clearances,
        restriction_records=restrictions,
        parser_records=parser_records,
        markdown_root=markdown_root,
        input_commitments=commitments,
    )
    prompt_root = paths["responses"].parent / "canonical-prompt-artifacts"
    finalized_path = prompt_root / "finalized-prediction-units.jsonl"
    decision_path = prompt_root / "decision-texts.jsonl"
    decision_manifest_path = prompt_root / "decision-texts-manifest.json"
    decision_card_path = prompt_root / "build-decision-texts.json"
    _write_jsonl(finalized_path, list(stage_a.finalized_prediction_units))
    _write_jsonl(decision_path, list(decisions))
    candidate_ids = tuple(str(row["candidate_id"]) for row in selections)
    _write_json(
        decision_manifest_path,
        {
            **REHEARSAL_PROVENANCE,
            "schema_version": "legalforecast.fixture_decision_text_manifest.v1",
            "record_count": len(decisions),
            "decision_texts_sha256": _sha256_path(decision_path),
            "candidate_ids_sha256": "sha256:"
            + hashlib.sha256(
                json.dumps(candidate_ids, separators=(",", ":")).encode()
            ).hexdigest(),
            "input_commitments": commitments,
            "outcome_material_model_visible": False,
        },
    )
    _write_json(
        decision_card_path,
        {
            **REHEARSAL_PROVENANCE,
            "schema_version": "legalforecast.fixture_acquisition_run_card.v1",
            "stage": "rehearsal-build-decision-texts",
            "status": "completed",
            "execute": True,
            "record_count": len(decisions),
            "decision_texts_sha256": _sha256_path(decision_path),
            "decision_texts_manifest_sha256": _sha256_path(decision_manifest_path),
            "input_commitments": commitments,
            "provider_call_executed": False,
        },
    )
    artifact = VerifiedDecisionTextArtifact(
        records=decisions,
        decision_texts_sha256=_sha256_path(decision_path),
        manifest_sha256=_sha256_path(decision_manifest_path),
        run_card_sha256=_sha256_path(decision_card_path),
        finalized_prediction_units_sha256=_sha256_path(finalized_path),
        finalized_unit_envelope_sha256s={
            str(row["candidate_id"]): "sha256:" + canonical_sha256(row)
            for row in stage_a.finalized_prediction_units
        },
        input_commitments=commitments,
    )
    judge = load_model_registry(paths["judge_registry"]).entries[0]
    decision_by_candidate = {str(row["candidate_id"]): row for row in decisions}
    label_rows = [
        _response_row(
            stage="llm-label",
            candidate_id=str(prompt["candidate_id"]),
            entry=judge,
            prompt_sha256=str(prompt["prompt_sha256"]),
            raw_output={
                "unit_findings": [
                    {
                        "unit_id": unit_ids[str(prompt["candidate_id"])],
                        "resolution": "fully_dismissed",
                        "amendment_signal": "express_denial_of_leave",
                        "supporting_excerpt": decision_by_candidate[
                            str(prompt["candidate_id"])
                        ]["text"],
                        "labeler_confidence": 0.99,
                    }
                ],
                "missing_unit_flags": [],
            },
        )
        for prompt in stage_b_labeling_prompt_records(
            selection_records=selections,
            prediction_unit_records=stage_a.finalized_prediction_units,
            decision_text_artifact=artifact,
        )
    ]
    _write_jsonl(paths["responses"], [*unit_fixture_rows, *review_rows, *label_rows])


def _target_100_helpers() -> ModuleType:
    module_path = ROOT / "tests/test_target_100_acquisition.py"
    spec = importlib.util.spec_from_file_location(
        "_lfb_target_100_rehearsal_helpers", module_path
    )
    if spec is None or spec.loader is None:
        raise AssertionError("cannot load target-100 fixture helpers")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _selection_document(
    candidate_id: str,
    source_document_id: str,
    role: str,
    entry_number: int,
    model_visible: bool,
    *,
    contains_target_outcome: bool = False,
) -> JsonRecord:
    return {
        "candidate_id": candidate_id,
        "source_document_id": source_document_id,
        "docket_entry_number": entry_number,
        "document_role": role,
        "description": role,
        "model_visible": model_visible,
        "contains_target_outcome": contains_target_outcome,
        "redaction_or_seal_status": "public",
        "restriction_evidence": ["fixture-only public docket"],
    }


def _registry_record(provider: str, model_id: str) -> JsonRecord:
    return {
        "provider": provider,
        "model_id": model_id,
        "display_name": model_id,
        "model_version_or_snapshot": f"{model_id}-2026-07-01",
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
        "input_token_price": 0.0,
        "output_token_price": 0.0,
        "known_cutoff_publicity_caveats": [],
    }


def _response_row(
    *,
    stage: str,
    candidate_id: str,
    entry: Any,
    prompt_sha256: str,
    raw_output: JsonRecord,
) -> JsonRecord:
    return {
        "schema_version": RESPONSE_FIXTURE_SCHEMA_VERSION,
        "stage": stage,
        "candidate_id": candidate_id,
        "model_key": entry.registry_key,
        "prompt_sha256": "sha256:" + prompt_sha256.removeprefix("sha256:"),
        "raw_output": json.dumps(raw_output, sort_keys=True),
        "served_model_version": entry.model_version_or_snapshot,
        "input_tokens": 0,
        "output_tokens": 0,
    }


def _recommit_fixture_stage_output(
    rehearsal_root: Path,
    *,
    artifact_path: Path,
    stage: str,
) -> None:
    sidecar_path = Path(str(artifact_path) + ".fixture-artifact.json")
    sidecar = json.loads(sidecar_path.read_text())
    sidecar["artifact_sha256"] = _sha256_path(artifact_path)
    sidecar["artifact_byte_count"] = artifact_path.stat().st_size
    _write_json(sidecar_path, sidecar)

    stage_card_path = rehearsal_root / "run-cards" / f"{stage}.json"
    stage_card = json.loads(stage_card_path.read_text())
    stage_card["output_commitments"][str(artifact_path.resolve())] = _sha256_path(
        artifact_path
    )
    stage_card["output_commitments"][str(sidecar_path.resolve())] = _sha256_path(
        sidecar_path
    )
    _write_json(stage_card_path, stage_card)

    summary_path = rehearsal_root / "rehearsal-final-summary.json"
    summary = json.loads(summary_path.read_text())
    summary["output_commitments"][str(artifact_path.resolve())] = _sha256_path(
        artifact_path
    )
    summary["output_commitments"][str(sidecar_path.resolve())] = _sha256_path(
        sidecar_path
    )
    summary["output_commitments"][str(stage_card_path.resolve())] = _sha256_path(
        stage_card_path
    )
    _write_json(summary_path, summary)
    run_card_path = rehearsal_root / "run-cards/rehearse-downstream.json"
    run_card = json.loads(run_card_path.read_text())
    run_card["summary_sha256"] = _sha256_path(summary_path)
    _write_json(run_card_path, run_card)


def _recommit_fixture_metadata_output(
    rehearsal_root: Path,
    *,
    metadata_path: Path,
    stage: str,
) -> None:
    stage_card_path = rehearsal_root / "run-cards" / f"{stage}.json"
    stage_card = json.loads(stage_card_path.read_text(encoding="utf-8"))
    stage_card["output_commitments"][str(metadata_path.resolve())] = _sha256_path(
        metadata_path
    )
    _write_json(stage_card_path, stage_card)

    summary_path = rehearsal_root / "rehearsal-final-summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["output_commitments"][str(metadata_path.resolve())] = _sha256_path(
        metadata_path
    )
    summary["output_commitments"][str(stage_card_path.resolve())] = _sha256_path(
        stage_card_path
    )
    _write_json(summary_path, summary)
    run_card_path = rehearsal_root / "run-cards/rehearse-downstream.json"
    run_card = json.loads(run_card_path.read_text(encoding="utf-8"))
    run_card["summary_sha256"] = _sha256_path(summary_path)
    _write_json(run_card_path, run_card)


def _docket_html(index: int) -> str:
    return f"""
    <html><body><div id="docket-entry-table">
      <div class="row odd" id="entry-1">
        <div class="col-xs-1"><p>1</p></div>
        <div class="col-xs-3"><p>Jan 1, 2026</p></div>
        <div class="col-xs-8"><p>COMPLAINT filed by Plaintiff {index}.</p></div>
      </div>
      <div class="row even" id="entry-5">
        <div class="col-xs-1"><p>5</p></div>
        <div class="col-xs-3"><p>Feb 1, 2026</p></div>
        <div class="col-xs-8"><p>MOTION to Dismiss.</p></div>
      </div>
      <div class="row odd" id="entry-16">
        <div class="col-xs-1"><p>16</p></div>
        <div class="col-xs-3"><p>July 1, 2026</p></div>
        <div class="col-xs-8"><p>ORDER granting 5 Motion to Dismiss.</p></div>
      </div>
    </div></body></html>
    """


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, records: list[JsonRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[JsonRecord]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_path(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _reject_network(*args: object, **kwargs: object) -> NoReturn:
    del args, kwargs
    raise AssertionError("provider-free rehearsal attempted network access")
