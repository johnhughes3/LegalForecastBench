from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from legalforecast import cli
from legalforecast.cli import build_parser, main
from legalforecast.ingestion.mistral_markdown_parser import EXPECTED_PARSER_REVISION
from legalforecast.protocol.policy_artifacts import generate_labeling_policy
from legalforecast.unitization.review import apply_unitization_reviews

JsonRecord = dict[str, Any]


@pytest.mark.parametrize(
    "command",
    ("plan-label-audit", "apply-lawyer-review", "finalize-corpus"),
)
def test_downstream_commands_require_authenticated_decision_text_bundle(
    command: str,
) -> None:
    parser = build_parser()
    acquisition = next(
        action
        for action in parser._actions
        if getattr(action, "dest", None) == "command"
    ).choices["acquisition"]
    subcommands = next(
        action
        for action in acquisition._actions
        if getattr(action, "dest", None) == "acquisition_command"
    ).choices
    option_actions = {
        option: action
        for action in subcommands[command]._actions
        for option in action.option_strings
    }

    for option in (
        "--decision-texts",
        "--decision-texts-manifest",
        "--decision-texts-run-card",
        "--selection",
        "--parser-manifest",
        "--prediction-units",
        "--markdown-root",
    ):
        assert option in option_actions
        assert option_actions[option].required is True


def test_build_decision_texts_emits_consumer_compatible_hash_bound_rows(
    tmp_path: Path,
) -> None:
    inputs = _write_inputs(tmp_path)
    output = tmp_path / "output"

    assert main(_command(inputs, output)) == 0

    records = _read_jsonl(output / "decision-texts.jsonl")
    assert len(records) == 1
    record = records[0]
    assert record["schema_version"] == "legalforecast.decision_text.v1"
    assert record["candidate_id"] == "cand-1"
    assert record["case_id"] == "case-1"
    assert record["document_id"] == "decision"
    assert record["entered_date"] == "2026-06-30"
    assert record["text"] == "# Decision\n\nThe motion is granted.\n"
    assert record["is_first_written_disposition"] is True
    assert record["contains_target_outcome"] is True
    assert record["model_visible"] is False
    assert (
        record["text_sha256"]
        == hashlib.sha256(record["text"].encode("utf-8")).hexdigest()
    )
    assert record["source_sha256"] == inputs["source_sha256"]
    assert record["input_commitments"] == {
        "clearance_run_card_sha256": _sha256(inputs["clearance_run_card"]),
        "disclosure_clearance_sha256": _sha256(inputs["clearance"]),
        "download_manifest_sha256": _sha256(inputs["download_manifest"]),
        "parser_manifest_sha256": _sha256(inputs["parser_manifest"]),
        "parser_run_card_sha256": _sha256(inputs["parser_run_card"]),
        "restriction_evidence_sha256": _sha256(inputs["restriction_evidence"]),
        "selection_sha256": _sha256(inputs["selection"]),
        "selection_run_card_sha256": _sha256(inputs["selection_run_card"]),
    }

    # Downstream consumers construct Stage B text only from verified records.
    loaded = cli._decision_texts_from_records(records)
    assert loaded["decision"].text == record["text"]

    manifest = json.loads(
        (output / "decision-texts-manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["record_count"] == 1
    assert manifest["eligibility_anchor"] == "2026-06-30"
    assert manifest["decision_texts_sha256"] == _sha256(output / "decision-texts.jsonl")
    run_card = json.loads(
        (output / "run-cards" / "build-decision-texts.json").read_text(encoding="utf-8")
    )
    assert run_card["decision_texts_manifest_sha256"] == _sha256(
        output / "decision-texts-manifest.json"
    )
    assert run_card["paid_activity_requested"] is False
    assert run_card["paid_activity_executed"] is False


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("before_anchor", "before eligibility anchor"),
        ("model_visible", "must not be model-visible"),
        ("not_outcome_bearing", "must be explicitly outcome-bearing"),
        ("sealed", "sealed/private/restricted"),
        ("malformed_sealed", "malformed is_sealed flag"),
        ("malformed_private_restriction", "malformed is_private flag"),
        ("uncleared", "decision document lacks clearance"),
        ("missing_disposition", "first written disposition document missing"),
        ("ambiguous", "ambiguous first written disposition"),
        ("missing_markdown", "markdown file missing"),
        ("path_traversal", "markdown path escapes markdown root"),
        ("symlink_markdown", "markdown path contains a symlink"),
        ("text_hash_mismatch", "extracted text hash mismatch"),
        ("source_hash_mismatch", "source hash mismatch"),
        ("failed_parser", "parser record did not succeed"),
        ("unpinned_parser", "parser revision is not the pinned Mistral revision"),
        ("fixture_parser_card", "pinned live Mistral parser execution"),
        (
            "clearance_hash_drift",
            "clear-disclosures disclosure_clearance commitment mismatch",
        ),
        ("clearance_coverage", "document key coverage mismatch"),
        ("selection_coverage", "selection and acquired document candidates differ"),
        ("duplicate_document_id", "decision document_id is not globally unique"),
    ],
)
def test_build_decision_texts_fails_closed(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    mutation: str,
    message: str,
) -> None:
    inputs = _write_inputs(tmp_path, mutation=mutation)

    assert main(_command(inputs, tmp_path / "output")) == 2
    assert message in capsys.readouterr().err
    assert not (tmp_path / "output" / "decision-texts.jsonl").exists()


def test_build_decision_texts_resume_rejects_modified_artifact(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    inputs = _write_inputs(tmp_path)
    output = tmp_path / "output"
    command = _command(inputs, output)
    assert main(command) == 0
    (output / "decision-texts.jsonl").write_text("{}\n", encoding="utf-8")

    assert main(command) == 2
    assert "build-decision-texts resume artifact mismatch" in capsys.readouterr().err


def test_build_decision_texts_accepts_unknown_flags_only_with_verified_public_status(
    tmp_path: Path,
) -> None:
    inputs = _write_inputs(tmp_path, mutation="null_flags")

    assert main(_command(inputs, tmp_path / "output")) == 0


def test_build_decision_texts_rejects_selection_modified_after_committed_projection(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    inputs = _write_inputs(tmp_path)
    rows = _read_jsonl(inputs["selection"])
    rows[0]["case_name"] = "Fabricated v. Caption"
    _write_jsonl(inputs["selection"], rows)

    assert main(_command(inputs, tmp_path / "output")) == 2
    assert "target-cohort selection commitment mismatch" in capsys.readouterr().err


def test_build_decision_texts_rejects_rehashed_markdown_and_parser_manifest(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    inputs = _write_inputs(tmp_path)
    forged_text = "# Forged decision\n\nThe motion is denied.\n"
    markdown_path = inputs["markdown_root"] / "cand-1" / "decision.md"
    markdown_path.write_text(forged_text, encoding="utf-8")
    rows = _read_jsonl(inputs["parser_manifest"])
    rows[0]["extracted_text"]["text_sha256"] = hashlib.sha256(
        forged_text.encode("utf-8")
    ).hexdigest()
    _write_jsonl(inputs["parser_manifest"], rows)

    assert main(_command(inputs, tmp_path / "output")) == 2
    assert "parser_manifest commitment mismatch" in capsys.readouterr().err


def test_build_decision_texts_rejects_absolute_markdown_outside_trusted_root(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    inputs = _write_inputs(tmp_path)
    rows = _read_jsonl(inputs["parser_manifest"])
    rows[0]["markdown_path"] = str(tmp_path / "outside.md")
    _write_jsonl(inputs["parser_manifest"], rows)
    _rewrite_parser_run_card_manifest_commitment(inputs)

    assert main(_command(inputs, tmp_path / "output")) == 2
    assert "markdown path escapes markdown root" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("missing_commitment", "decision_text_commitment"),
        ("tampered_decision_text", "decision text artifact hash mismatch"),
    ],
)
def test_plan_label_audit_rejects_legacy_or_tampered_decision_text_input(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    mutation: str,
    message: str,
) -> None:
    inputs = _write_inputs(tmp_path)
    decision_root = tmp_path / "decision-artifact"
    assert main(_command(inputs, decision_root)) == 0
    finalized_units = apply_unitization_reviews(
        prediction_unit_records=[
            {
                "candidate_id": "cand-1",
                "case_id": "case-1",
                "prediction_units": [{"unit_id": "unit-1", "should_score": True}],
            }
        ],
        review_records=(),
        adjudication_records=(),
    )
    units_path = tmp_path / "finalized-units.jsonl"
    _write_jsonl(units_path, list(finalized_units))
    audit_path = tmp_path / "label-audit.jsonl"
    _write_jsonl(
        audit_path,
        [
            {
                "stage": "llm-label",
                "status": "succeeded",
                "candidate_id": "cand-1",
                "case_id": "case-1",
            }
        ],
    )
    if mutation == "tampered_decision_text":
        (decision_root / "decision-texts.jsonl").write_text(
            '{"candidate_id":"cand-1","text":"forged"}\n',
            encoding="utf-8",
        )
    policy_path = tmp_path / "labeling-policy.json"
    policy_path.write_text(
        json.dumps(
            generate_labeling_policy(
                cycle_id="cycle-1",
                judge_registry_path=Path(
                    "model_registries/cycle-1-stage-b-judges-2026-07-12.json"
                ),
                published_at=datetime(2026, 7, 15, tzinfo=UTC),
                threshold_source="Cycle 1 labeling protocol fixture.",
            ),
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    queue_path = tmp_path / "queue.jsonl"
    queue_path.write_text("", encoding="utf-8")

    assert (
        main(
            [
                "acquisition",
                "plan-label-audit",
                "--output-root",
                str(tmp_path / "audit-output"),
                "--llm-label-audit",
                str(audit_path),
                "--selection",
                str(inputs["selection"]),
                "--parser-manifest",
                str(inputs["parser_manifest"]),
                "--prediction-units",
                str(units_path),
                "--decision-texts",
                str(decision_root / "decision-texts.jsonl"),
                "--decision-texts-manifest",
                str(decision_root / "decision-texts-manifest.json"),
                "--decision-texts-run-card",
                str(decision_root / "run-cards" / "build-decision-texts.json"),
                "--markdown-root",
                str(inputs["markdown_root"]),
                "--labeling-policy",
                str(policy_path),
                "--lawyer-review-queue",
                str(queue_path),
                "--execute",
            ]
        )
        == 2
    )
    assert message in capsys.readouterr().err


def _command(inputs: dict[str, Any], output: Path) -> list[str]:
    return [
        "acquisition",
        "build-decision-texts",
        "--output-root",
        str(output),
        "--selection",
        str(inputs["selection"]),
        "--selection-run-card",
        str(inputs["selection_run_card"]),
        "--download-manifest",
        str(inputs["download_manifest"]),
        "--disclosure-clearance",
        str(inputs["clearance"]),
        "--clearance-run-card",
        str(inputs["clearance_run_card"]),
        "--restriction-evidence",
        str(inputs["restriction_evidence"]),
        "--parser-manifest",
        str(inputs["parser_manifest"]),
        "--parser-run-card",
        str(inputs["parser_run_card"]),
        "--markdown-root",
        str(inputs["markdown_root"]),
        "--execute",
    ]


def _write_inputs(tmp_path: Path, *, mutation: str | None = None) -> dict[str, Any]:
    source_sha256 = "a" * 64
    byte_count = 42
    selection = tmp_path / "selection.jsonl"
    download_manifest = tmp_path / "document-downloads-merged.jsonl"
    clearance = tmp_path / "disclosure-clearance.jsonl"
    restriction_evidence = tmp_path / "restriction-evidence.jsonl"
    parser_manifest = tmp_path / "mistral-markdown-conversions.jsonl"
    markdown_root = tmp_path / "markdown"
    clearance_run_card = tmp_path / "clear-disclosures.json"
    selection_run_card = tmp_path / "project-target-cohort.json"
    parser_run_card = tmp_path / "parse-documents.json"
    parse_requests = tmp_path / "parse-document-requests.jsonl"
    markdown = "# Decision\n\nThe motion is granted.\n"
    decision_document: JsonRecord = {
        "candidate_id": "cand-1",
        "source_document_id": "decision",
        "docket_entry_number": 50,
        "document_role": "decision",
        "description": "Order granting motion to dismiss",
        "model_visible": False,
        "contains_target_outcome": True,
        "is_sealed": False,
        "is_private": False,
        "restriction_evidence": ["courtlistener_public_docket"],
    }
    selection_rows: list[JsonRecord] = [
        {
            "candidate_id": "cand-1",
            "case_id": "case-1",
            "case_name": "Example v. Defendant",
            "court": "nysd",
            "docket_number": "1:26-cv-1",
            "decision_date": "2026-06-30",
            "selected": True,
            "decision_entry_numbers": [50],
            "documents": [decision_document],
        }
    ]
    manifest_rows: list[JsonRecord] = [
        {
            "candidate_id": "cand-1",
            "source_document_id": "decision",
            "local_path": "cand-1/decision.pdf",
            "sha256": source_sha256,
            "byte_count": byte_count,
            "free_or_purchased": "free",
        }
    ]
    clearance_rows: list[JsonRecord] = [
        {
            "schema_version": "legalforecast.disclosure_clearance.v1",
            "candidate_id": "cand-1",
            "source_document_id": "decision",
            "local_path": "cand-1/decision.pdf",
            "sha256": source_sha256,
            "byte_count": byte_count,
            "status": "cleared",
            "restriction_status": "public",
            "restriction_evidence": ["courtlistener_public_docket"],
            "reviewer_id": "reviewer:john",
            "controlled_store_provenance": "private-store://cycle-1/reviews",
            "reviewed_at": "2026-07-15T12:00:00Z",
            "free_or_purchased": "free",
        }
    ]
    restriction_rows: list[JsonRecord] = [
        {
            "candidate_id": "cand-1",
            "source_document_id": "decision",
            "restriction_status": "public",
            "restriction_evidence": ["courtlistener_public_docket"],
            "is_sealed": False,
            "is_private": False,
        }
    ]
    parser_rows: list[JsonRecord] = [
        {
            "candidate_id": "cand-1",
            "source_document_id": "decision",
            "status": "succeeded",
            "input_path": "documents/cand-1/decision.pdf",
            "markdown_path": str((markdown_root / "cand-1" / "decision.md").resolve()),
            "metadata_path": "cand-1/decision.metadata.json",
            "parser_config": {
                "engine": "mistral",
                "parser_revision": EXPECTED_PARSER_REVISION,
                "expected_parser_revision": EXPECTED_PARSER_REVISION,
            },
            "quality_flags": [],
            "extracted_text": {
                "source_document_id": "decision",
                "extraction_method": "mistral_parser_markdown",
                "text_sha256": hashlib.sha256(markdown.encode()).hexdigest(),
            },
            "source_sha256": source_sha256,
            "source_byte_count": byte_count,
        }
    ]

    if mutation == "before_anchor":
        selection_rows[0]["decision_date"] = "2026-06-29"
    elif mutation == "model_visible":
        decision_document["model_visible"] = True
    elif mutation == "not_outcome_bearing":
        decision_document["contains_target_outcome"] = False
    elif mutation == "sealed":
        decision_document["is_sealed"] = True
    elif mutation == "malformed_sealed":
        decision_document["is_sealed"] = "true"
    elif mutation == "malformed_private_restriction":
        restriction_rows[0]["is_private"] = 1
    elif mutation == "null_flags":
        decision_document["is_sealed"] = None
        decision_document["is_private"] = None
        restriction_rows[0]["is_sealed"] = None
        restriction_rows[0]["is_private"] = None
    elif mutation == "uncleared":
        clearance_rows[0]["status"] = "quarantined"
    elif mutation == "missing_disposition":
        decision_document["document_role"] = "complaint"
    elif mutation == "ambiguous":
        selection_rows[0]["documents"] = [
            decision_document,
            {**decision_document, "source_document_id": "decision-attachment"},
        ]
        manifest_rows.append(
            {
                **manifest_rows[0],
                "source_document_id": "decision-attachment",
                "local_path": "cand-1/decision-attachment.pdf",
            }
        )
        clearance_rows.append(
            {
                **clearance_rows[0],
                "source_document_id": "decision-attachment",
                "local_path": "cand-1/decision-attachment.pdf",
            }
        )
        restriction_rows.append(
            {**restriction_rows[0], "source_document_id": "decision-attachment"}
        )
        parser_rows.append(
            {
                **parser_rows[0],
                "source_document_id": "decision-attachment",
                "markdown_path": str(
                    (markdown_root / "cand-1" / "decision-attachment.md").resolve()
                ),
                "extracted_text": {
                    **parser_rows[0]["extracted_text"],
                    "source_document_id": "decision-attachment",
                },
            }
        )
    elif mutation == "text_hash_mismatch":
        parser_rows[0]["extracted_text"]["text_sha256"] = "b" * 64
    elif mutation == "source_hash_mismatch":
        parser_rows[0]["source_sha256"] = "b" * 64
    elif mutation == "failed_parser":
        parser_rows[0]["status"] = "failed"
    elif mutation == "unpinned_parser":
        parser_rows[0]["parser_config"]["parser_revision"] = "b" * 40
    elif mutation == "clearance_coverage":
        clearance_rows = []
    elif mutation == "selection_coverage":
        selection_rows.append(
            {
                **selection_rows[0],
                "candidate_id": "cand-2",
                "case_id": "case-2",
                "documents": [
                    {
                        **decision_document,
                        "candidate_id": "cand-2",
                        "source_document_id": "decision-2",
                    }
                ],
            }
        )
    elif mutation == "path_traversal":
        parser_rows[0]["markdown_path"] = "../decision.md"
    elif mutation == "duplicate_document_id":
        selection_rows.append(
            {
                **selection_rows[0],
                "candidate_id": "cand-2",
                "case_id": "case-2",
                "documents": [
                    {
                        **decision_document,
                        "candidate_id": "cand-2",
                    }
                ],
            }
        )
        manifest_rows.append(
            {
                **manifest_rows[0],
                "candidate_id": "cand-2",
                "local_path": "cand-2/decision.pdf",
            }
        )
        clearance_rows.append(
            {
                **clearance_rows[0],
                "candidate_id": "cand-2",
                "local_path": "cand-2/decision.pdf",
            }
        )
        restriction_rows.append({**restriction_rows[0], "candidate_id": "cand-2"})
        parser_rows.append(
            {
                **parser_rows[0],
                "candidate_id": "cand-2",
                "markdown_path": str(
                    (markdown_root / "cand-2" / "decision.md").resolve()
                ),
            }
        )

    _write_jsonl(selection, selection_rows)
    _write_jsonl(download_manifest, manifest_rows)
    _write_jsonl(clearance, clearance_rows)
    _write_jsonl(restriction_evidence, restriction_rows)
    _write_jsonl(parser_manifest, parser_rows)
    _write_jsonl(
        parse_requests,
        [
            {
                "candidate_id": row["candidate_id"],
                "source_document_id": row["source_document_id"],
                "expected_sha256": row["source_sha256"],
                "expected_byte_count": row["source_byte_count"],
            }
            for row in parser_rows
        ],
    )
    markdown_root.joinpath("cand-1").mkdir(parents=True)
    if mutation != "missing_markdown":
        (markdown_root / "cand-1" / "decision.md").write_text(
            markdown, encoding="utf-8"
        )
    if mutation == "symlink_markdown":
        real_markdown = tmp_path / "decision-real.md"
        real_markdown.write_text(markdown, encoding="utf-8")
        (markdown_root / "cand-1" / "decision.md").unlink()
        (markdown_root / "cand-1" / "decision.md").symlink_to(real_markdown)
    if mutation == "duplicate_document_id":
        markdown_root.joinpath("cand-2").mkdir(parents=True)
        (markdown_root / "cand-2" / "decision.md").write_text(
            markdown, encoding="utf-8"
        )
    if mutation == "ambiguous":
        (markdown_root / "cand-1" / "decision-attachment.md").write_text(
            markdown, encoding="utf-8"
        )

    run_card = {
        "schema_version": "legalforecast.acquisition_run_card.v1",
        "stage": "clear-disclosures",
        "status": "completed",
        "dry_run": False,
        "execute": True,
        "paid_activity_executed": False,
        "source_commitments": {
            "download_manifest": {
                "path": str(download_manifest.resolve()),
                "sha256": _sha256(download_manifest),
            },
            "restriction_evidence": {
                "path": str(restriction_evidence.resolve()),
                "sha256": _sha256(restriction_evidence),
            },
            "reviews": {"path": "/private/reviews", "sha256": "sha256:" + "b" * 64},
            "review_receipt": {
                "path": "/private/receipt",
                "sha256": "sha256:" + "c" * 64,
            },
        },
        "output_commitments": {
            "disclosure_clearance": {
                "path": str(clearance.resolve()),
                "sha256": _sha256(clearance),
            }
        },
        "review_authority": {
            "reviewer_id": "reviewer:john",
            "controlled_store_uri": "private-store://cycle-1/reviews",
            "authentication_method": "cloudflare_access_oidc",
            "authenticated_at": "2026-07-15T12:00:00Z",
            "review_artifact_sha256": "sha256:" + "b" * 64,
        },
    }
    if mutation == "clearance_hash_drift":
        run_card["output_commitments"]["disclosure_clearance"]["sha256"] = (
            "sha256:" + "d" * 64
        )
    clearance_run_card.write_text(
        json.dumps(run_card, sort_keys=True) + "\n", encoding="utf-8"
    )
    selection_run_card.write_text(
        json.dumps(
            {
                "schema_version": "legalforecast.acquisition_run_card.v1",
                "stage": "project-target-cohort",
                "status": "completed",
                "dry_run": False,
                "execute": True,
                "record_count": len(selection_rows),
                "paid_activity_executed": False,
                "output_commitments": {str(selection): _sha256(selection)},
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    parser_execution: JsonRecord = {
        "mode": "live_mistral",
        "engine": "mistral",
        "parser_revision": EXPECTED_PARSER_REVISION,
        "parser_root": "/work/Development/tools/parser",
        "fixture_markdown": False,
    }
    if mutation == "fixture_parser_card":
        parser_execution.update(
            mode="fixture_markdown",
            engine="fixture_markdown",
            parser_revision=None,
            fixture_markdown=True,
        )
    parser_run_card.write_text(
        json.dumps(
            {
                "schema_version": "legalforecast.acquisition_run_card.v1",
                "stage": "parse-documents",
                "status": "completed",
                "dry_run": False,
                "execute": True,
                "record_count": len(parser_rows),
                "paid_activity_requested": False,
                "paid_activity_executed": False,
                "source_commitments": {
                    "requests": {
                        "path": str(parse_requests.resolve()),
                        "sha256": _sha256(parse_requests),
                    },
                    "disclosure_clearance": {
                        "path": str(clearance.resolve()),
                        "sha256": _sha256(clearance),
                    },
                },
                "output_commitments": {
                    "parser_manifest": {
                        "path": str(parser_manifest.resolve()),
                        "sha256": _sha256(parser_manifest),
                    }
                },
                "parser_execution": parser_execution,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "selection": selection,
        "selection_run_card": selection_run_card,
        "download_manifest": download_manifest,
        "clearance": clearance,
        "clearance_run_card": clearance_run_card,
        "restriction_evidence": restriction_evidence,
        "parser_manifest": parser_manifest,
        "parser_run_card": parser_run_card,
        "markdown_root": markdown_root,
        "source_sha256": source_sha256,
    }


def _write_jsonl(path: Path, rows: list[JsonRecord]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[JsonRecord]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _rewrite_parser_run_card_manifest_commitment(inputs: dict[str, Any]) -> None:
    path = inputs["parser_run_card"]
    run_card = json.loads(path.read_text(encoding="utf-8"))
    run_card["output_commitments"]["parser_manifest"]["sha256"] = _sha256(
        inputs["parser_manifest"]
    )
    path.write_text(json.dumps(run_card, sort_keys=True) + "\n", encoding="utf-8")
