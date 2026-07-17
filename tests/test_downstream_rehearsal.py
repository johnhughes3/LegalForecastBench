from __future__ import annotations

import hashlib
import json
import urllib.request
from pathlib import Path
from typing import Any, NoReturn

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
    ]


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
        "prompt_sha256": prompt_sha256,
        "raw_output": json.dumps(raw_output, sort_keys=True),
        "served_model_version": entry.model_version_or_snapshot,
        "input_tokens": 0,
        "output_tokens": 0,
    }


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
