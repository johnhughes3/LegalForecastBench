from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast

import legalforecast.cli as cli_module
import pytest
from legalforecast.cli import build_parser, main
from legalforecast.ingestion.canonical_json import canonical_json_value_bytes
from legalforecast.ingestion.decision_text_artifact import (
    DecisionTextArtifactError,
    _require_deferred_docket_public_proof,
    _validate_finalized_unit_envelope,
    build_decision_text_records,
    verify_decision_text_artifact,
)
from legalforecast.ingestion.embedded_text_layer_repair import (
    EMBEDDED_TEXT_LAYER_REPAIR_ENGINE,
    EMBEDDED_TEXT_LAYER_REPAIR_METHOD,
    EMBEDDED_TEXT_LAYER_REPAIR_REVISION,
)
from legalforecast.ingestion.mistral_markdown_parser import EXPECTED_PARSER_REVISION
from legalforecast.protocol.policy_artifacts import generate_labeling_policy
from legalforecast.unitization.review import (
    STRUCTURAL_ADD_ADJUDICATION_SCHEMA_VERSION,
    apply_unitization_reviews,
    canonical_sha256,
)

JsonRecord = dict[str, Any]


def _structural_add_prediction_unit(unit_id: str) -> JsonRecord:
    return {
        "unit_id": unit_id,
        "count": "I",
        "claim_name": f"Claim {unit_id}",
        "defendant_group": "Defendant",
        "challenged_by_motion": True,
        "challenge_scope": "entire_claim",
        "unit_confidence": 0.9,
        "source_citations": [
            {
                "document_id": "decision",
                "docket_entry_number": None,
                "page": 1,
                "paragraph": None,
                "excerpt": None,
            }
        ],
        "grouping": "individual",
        "grouping_rationale": None,
        "separable_subclaim": None,
        "uncertainty_notes": None,
        "should_score": True,
    }


def _structural_add_finalized_envelope() -> JsonRecord:
    raw = {
        "candidate_id": "cand-1",
        "case_id": "case-1",
        "prediction_units": [_structural_add_prediction_unit("unit-1")],
    }
    review = {
        "schema_version": "legalforecast.unitization_review_queue.v1",
        "status": "pending_adjudication",
        "candidate_id": "cand-1",
        "case_id": "case-1",
        "unit_id": "unit-1",
        "review_id": "cand-1:unit-1:stage-a-review",
        "route_reason": "structural_omitted",
        "review_item": {
            "unit_id": "unit-1",
            "reason": "structural_omitted",
            "notes": "A structural omission requires adjudication.",
            "source_document_ids": ["decision"],
        },
        "structural_flag_sha256": canonical_sha256({"flag": "flag-1"}),
        "raw_prediction_units_sha256": canonical_sha256(raw),
    }
    adjudication = {
        "schema_version": STRUCTURAL_ADD_ADJUDICATION_SCHEMA_VERSION,
        "adjudication_id": "adj-cand-1-add",
        "candidate_id": "cand-1",
        "case_id": "case-1",
        "review_ids": [review["review_id"]],
        "disposition": "ADD",
        "finalized_units": [_structural_add_prediction_unit("unit-2")],
        "adjudicator_id": "lawyer-1",
        "adjudication_notes": "Add the omitted unit.",
    }
    [finalized] = apply_unitization_reviews(
        prediction_unit_records=[raw],
        review_records=[review],
        adjudication_records=[adjudication],
    )
    return finalized


def test_decision_text_authenticates_v3_added_unit_without_source_hash() -> None:
    finalized = _structural_add_finalized_envelope()
    added = next(
        unit for unit in finalized["prediction_units"] if unit["disposition"] == "ADD"
    )
    assert added["source_unit_sha256s"] == []
    _validate_finalized_unit_envelope(finalized, expected_case_id="case-1")


def test_decision_text_rejects_empty_source_hashes_for_ordinary_schema() -> None:
    raw = {
        "candidate_id": "cand-1",
        "case_id": "case-1",
        "prediction_units": [_structural_add_prediction_unit("unit-1")],
    }
    [finalized] = apply_unitization_reviews(
        prediction_unit_records=[raw], review_records=(), adjudication_records=()
    )
    unit = finalized["prediction_units"][0]
    unit["source_unit_sha256s"] = []

    with pytest.raises(
        DecisionTextArtifactError, match="invalid finalized prediction-units envelope"
    ):
        _validate_finalized_unit_envelope(finalized, expected_case_id="case-1")


def test_decision_text_rejects_empty_source_hashes_for_v3_non_add() -> None:
    finalized = _structural_add_finalized_envelope()
    added = next(
        unit for unit in finalized["prediction_units"] if unit["disposition"] == "ADD"
    )
    added["disposition"] = "ACCEPT"
    finalized["added_units"] = []

    with pytest.raises(
        DecisionTextArtifactError, match="invalid finalized prediction-units envelope"
    ):
        _validate_finalized_unit_envelope(finalized, expected_case_id="case-1")


@pytest.mark.parametrize("field", ["adjudication_sha256", "structural_flag_sha256"])
def test_decision_text_rejects_non_digest_v3_add_provenance(field: str) -> None:
    finalized = _structural_add_finalized_envelope()
    added = next(
        unit for unit in finalized["prediction_units"] if unit["disposition"] == "ADD"
    )
    ledger = finalized["added_units"][0]
    added[field] = "not-a-digest"
    ledger[field] = "not-a-digest"

    with pytest.raises(
        DecisionTextArtifactError, match=rf"{field} must be a SHA-256 digest"
    ):
        _validate_finalized_unit_envelope(finalized, expected_case_id="case-1")


@pytest.fixture(autouse=True)
def _isolate_materialized_decision_semantics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        cli_module,
        "_preflight_materialization_purchase_runtime",
        lambda _args: None,
    )

    def verify_fixture_materialization(
        **keywords: Any,
    ) -> cli_module._VerifiedMaterializedDownstreamLineage:
        run_card_path = Path(keywords["run_card_path"])
        clearance_path = Path(keywords["clearance_path"])
        card = json.loads(run_card_path.read_text(encoding="utf-8"))
        commitment = card["output_commitments"]["disclosure_clearance"]
        if commitment["sha256"] != _sha256(clearance_path):
            raise cli_module.CommandError(
                "clear-disclosures disclosure_clearance commitment mismatch"
            )
        return cli_module._VerifiedMaterializedDownstreamLineage(
            paths=(run_card_path,),
            artifact_bytes={},
            manifest_records=(),
            clearance_records=(),
            selection_records=(),
            resolved_records=(),
            document_tree={},
        )

    monkeypatch.setattr(
        cli_module,
        "_verify_materialized_downstream_lineage",
        verify_fixture_materialization,
    )


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
        "clearance_run_card_sha256": _sha256(inputs["materialization_run_card"]),
        "disclosure_clearance_sha256": _sha256(inputs["clearance"]),
        "download_manifest_sha256": _sha256(inputs["download_manifest"]),
        "parser_manifest_sha256": _sha256(inputs["parser_manifest"]),
        "parser_run_card_sha256": _sha256(inputs["parser_run_card"]),
        "restriction_evidence_sha256": _sha256(inputs["restriction_evidence"]),
        "selection_sha256": _sha256(inputs["selection"]),
        "selection_run_card_sha256": _sha256(inputs["selection_run_card"]),
    }
    loaded = cli_module._decision_texts_from_records(records)
    assert loaded["decision"].text == record["text"]
    manifest = json.loads(
        (output / "decision-texts-manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["record_count"] == 1
    assert manifest["eligibility_anchor"] == "2026-06-30"
    assert manifest["decision_texts_sha256"] == _sha256(output / "decision-texts.jsonl")
    run_card = json.loads(
        (output / "run-cards/build-decision-texts.json").read_text(encoding="utf-8")
    )
    assert run_card["decision_texts_manifest_sha256"] == _sha256(
        output / "decision-texts-manifest.json"
    )
    assert run_card["paid_activity_requested"] is False
    assert run_card["paid_activity_executed"] is False
    assert str(inputs["materialization_run_card"]) in run_card["input_paths"]


def test_build_decision_texts_accepts_only_replayed_successor_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The decision-text consumer receives successor authority from materialization."""

    inputs = _write_inputs(tmp_path)
    selection_bytes = inputs["selection"].read_bytes()
    selection_records = _read_jsonl(inputs["selection"])
    successor_card = {
        "schema_version": cli_module.ZERO_COST_SUCCESSOR_STATE_SCHEMA,
        "stage": "project-zero-cost-successor",
        "record_count": len(selection_records),
    }
    card_bytes = (json.dumps(successor_card, sort_keys=True) + "\n").encode("utf-8")
    inputs["selection_run_card"].write_bytes(card_bytes)

    # The regular materialization fixture has no verifier-owned successor proof.
    assert main(_command(inputs, tmp_path / "rejected-output")) == 2

    capability = object.__new__(cli_module._VerifiedSuccessorSelectionCard)
    object.__setattr__(capability, "selection_path", inputs["selection"])
    object.__setattr__(capability, "selection_bytes", selection_bytes)
    object.__setattr__(capability, "selection_record_count", len(selection_records))
    object.__setattr__(capability, "run_card_path", inputs["selection_run_card"])
    object.__setattr__(capability, "run_card_bytes", card_bytes)
    object.__setattr__(
        capability, "_token", cli_module._VERIFIED_SUCCESSOR_SELECTION_CARD_TOKEN
    )

    def replayed_materialization(
        **keywords: Any,
    ) -> cli_module._VerifiedMaterializedDownstreamLineage:
        run_card_path = Path(keywords["run_card_path"])
        return cli_module._VerifiedMaterializedDownstreamLineage(
            paths=(run_card_path,),
            artifact_bytes={},
            manifest_records=(),
            clearance_records=(),
            selection_records=(),
            resolved_records=(),
            document_tree={},
            verified_successor_selection_card=capability,
        )

    monkeypatch.setattr(
        cli_module,
        "_verify_materialized_downstream_lineage",
        replayed_materialization,
    )
    assert main(_command(inputs, tmp_path / "output")) == 0


def test_authenticated_docket_decision_builds_without_pdf_or_parser(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selection = {
        "candidate_id": "cand-1",
        "case_id": "case-1",
        "decision_date": "2026-07-01",
        "decision_entry_numbers": [50],
        "selected": True,
        "documents": [
            {
                "candidate_id": "cand-1",
                "source_document_id": "complaint",
                "docket_entry_number": 1,
                "document_role": "complaint",
                "model_visible": True,
                "contains_target_outcome": False,
            },
            {
                "candidate_id": "cand-1",
                "source_document_id": "decision",
                "docket_entry_number": 50,
                "document_role": "decision",
                "model_visible": False,
                "contains_target_outcome": True,
                "redaction_or_seal_status": "unknown",
                "restriction_evidence": ["courtlistener_public_docket"],
            },
        ],
    }
    canary = "OUTCOME_CANARY_GRANTED_WITH_PREJUDICE — naïve"
    source = {
        "candidate_id": "cand-1",
        "case_id": "case-1",
        "unavailable_recap_document_id": "decision",
        "decision_entry_number": 50,
        "entered_date": "2026-07-01",
        "text": canary,
        "text_sha256": hashlib.sha256(canary.encode()).hexdigest(),
        "selection_record_sha256": "sha256:"
        + hashlib.sha256(
            canonical_json_value_bytes(
                selection,
                error_type=ValueError,
                error_message="not canonical",
            )
        ).hexdigest(),
        "restriction_evidence": ["courtlistener_public_docket"],
    }
    verified_source = MappingProxyType(dict(source))
    monkeypatch.setattr(
        "legalforecast.ingestion.docket_decision_text_source."
        "verified_docket_decision_source_records",
        lambda _authority, *, purchase_journal: (verified_source,),
    )
    acquired = [{"candidate_id": "cand-1", "source_document_id": "complaint"}]

    records = build_decision_text_records(
        selections=[selection],
        download_manifest=acquired,
        clearance_records=acquired,
        restriction_records=acquired,
        parser_records=acquired,
        markdown_root=tmp_path,
        input_commitments={
            name: "a" * 64
            for name in (
                "selection_sha256",
                "download_manifest_sha256",
                "disclosure_clearance_sha256",
                "clearance_run_card_sha256",
                "restriction_evidence_sha256",
                "parser_manifest_sha256",
                "parser_run_card_sha256",
                "selection_run_card_sha256",
            )
        },
        docket_decision_authority=cast(Any, object()),
        purchase_journal=cast(Any, object()),
    )

    assert len(records) == 1
    assert records[0]["text"] == canary
    assert records[0]["source_provenance"] == "authenticated_docket_entry_text"
    assert records[0]["model_visible"] is False
    assert records[0]["parser_revision"] == "not_applicable"
    assert (
        records[0]["docket_source_record_sha256"]
        == "sha256:"
        + hashlib.sha256(
            canonical_json_value_bytes(
                source,
                error_type=ValueError,
                error_message="not canonical",
            )
        ).hexdigest()
    )

    source["selection_record_sha256"] = "0" * 64
    with pytest.raises(
        DecisionTextArtifactError,
        match="does not bind the selected restriction",
    ):
        _require_deferred_docket_public_proof(
            selection=selection,
            selection_document=selection["documents"][1],
            docket_source=source,
            key=("cand-1", "decision"),
        )


def test_docket_decision_record_commitment_rejects_nonfinite_values() -> None:
    with pytest.raises(ValueError, match="not canonical"):
        canonical_json_value_bytes(
            {"score": float("nan")},
            error_type=ValueError,
            error_message="not canonical",
        )


def test_docket_decision_replay_accepts_suffixless_materialization_card(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decision_texts = tmp_path / "decisions.jsonl"
    decision_texts.write_text(
        json.dumps({"source_provenance": "authenticated_docket_entry_text"}) + "\n",
        encoding="utf-8",
    )
    markdown_root = tmp_path / "markdown"
    markdown_root.mkdir()
    materialization_card = tmp_path / "materialization-card"
    materialization_card.write_text(
        json.dumps(
            {
                "stage": "materialize-cohort-documents",
                "output_paths": [
                    str(tmp_path / f"output-{index}") for index in range(6)
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    run_card = tmp_path / "decision-card.json"
    run_card.write_text(
        json.dumps(
            {
                "input_paths": [
                    str(decision_texts),
                    str(materialization_card),
                    str(markdown_root),
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    calls: list[str] = []
    verified = cli_module._VerifiedMaterializedDownstreamLineage(
        paths=(materialization_card,),
        artifact_bytes={},
        manifest_records=(),
        clearance_records=(),
        selection_records=(),
        resolved_records=(),
        document_tree={},
    )
    monkeypatch.setattr(
        cli_module,
        "_verify_materialized_downstream_lineage",
        lambda **_kwargs: (calls.append("materialization"), verified)[1],
    )
    sentinel = cast(Any, object())
    monkeypatch.setattr(
        cli_module,
        "verify_decision_text_artifact",
        lambda **_kwargs: (calls.append("decision"), sentinel)[1],
    )

    result = cli_module._verify_decision_text_artifact_with_materialization(
        args=type(
            "Args",
            (),
            {
                "controlled_private_root": None,
                "purchase_ledger_initialization_receipt": None,
            },
        )(),
        decision_texts_path=decision_texts,
        manifest_path=tmp_path / "manifest.json",
        run_card_path=run_card,
        selections=(),
        selection_path=tmp_path / "selection.jsonl",
        parser_records=(),
        parser_manifest_path=tmp_path / "parser.jsonl",
        finalized_unit_records=(),
        finalized_units_path=tmp_path / "units.jsonl",
        markdown_root=markdown_root,
    )

    assert result is sentinel
    assert calls == ["materialization", "decision"]


def test_docket_decision_replay_rejects_missing_materialization_lineage(
    tmp_path: Path,
) -> None:
    decision_texts = tmp_path / "decisions.jsonl"
    decision_texts.write_text(
        json.dumps({"source_provenance": "authenticated_docket_entry_text"}) + "\n",
        encoding="utf-8",
    )
    markdown_root = tmp_path / "markdown"
    markdown_root.mkdir()
    run_card = tmp_path / "decision-card.json"
    run_card.write_text(
        json.dumps({"input_paths": [str(decision_texts), str(markdown_root)]}) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(cli_module.CommandError, match="no materialization lineage"):
        cli_module._verify_decision_text_artifact_with_materialization(
            args=type(
                "Args",
                (),
                {
                    "controlled_private_root": None,
                    "purchase_ledger_initialization_receipt": None,
                },
            )(),
            decision_texts_path=decision_texts,
            manifest_path=tmp_path / "manifest.json",
            run_card_path=run_card,
            selections=(),
            selection_path=tmp_path / "selection.jsonl",
            parser_records=(),
            parser_manifest_path=tmp_path / "parser.jsonl",
            finalized_unit_records=(),
            finalized_units_path=tmp_path / "units.jsonl",
            markdown_root=markdown_root,
        )


def test_downstream_docket_descriptor_rejects_unverified_shapes() -> None:
    with pytest.raises(cli_module.CommandError, match="invalid type"):
        cli_module._downstream_docket_decision_descriptor((Path("card"),))


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("before_anchor", "before eligibility anchor"),
        ("model_visible", "must not be model-visible"),
        ("not_outcome_bearing", "must be explicitly outcome-bearing"),
        ("sealed", "sealed/private/restricted"),
        ("selection_explicitly_restricted", "sealed/private/restricted"),
        ("malformed_sealed", "malformed is_sealed flag"),
        ("selection_malformed_status", "invalid public status"),
        ("selection_unknown_mismatched_evidence", "does not match materialization"),
        (
            "selection_unknown_selection_evidence_mismatch",
            "does not match materialization",
        ),
        ("unknown_clearance_restricted_token", "sealed/private/restricted"),
        ("selection_unknown_uncanonical", "lacks canonical public proof"),
        ("malformed_private_restriction", "malformed is_private flag"),
        (
            "affirmative_public_with_reviewer",
            "automatic clearance unexpectedly has a reviewer",
        ),
        (
            "affirmative_public_wrong_provenance",
            "automatic clearance provenance is not an allowlisted public",
        ),
        (
            "affirmative_public_wrong_phase",
            "automatic clearance provenance is not an allowlisted public",
        ),
        (
            "model_review_missing_reviewer",
            "model-reviewed clearance lacks model authority provenance",
        ),
        (
            "model_review_human_timestamp",
            "model-reviewed clearance has a human review timestamp",
        ),
        (
            "model_review_wrong_provenance",
            "model-reviewed clearance lacks model authority provenance",
        ),
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
        ("clearance_coverage", "manifest and clearance coverage differ"),
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


def test_build_decision_texts_accepts_unknown_selection_with_affirmative_public_proof(
    tmp_path: Path,
) -> None:
    inputs = _write_inputs(tmp_path, mutation="selection_unknown_affirmative")

    assert main(_command(inputs, tmp_path / "output")) == 0


def test_verify_decision_texts_accepts_unknown_affirmative_public_proof(
    tmp_path: Path,
) -> None:
    inputs = _write_inputs(tmp_path, mutation="selection_unknown_affirmative")
    output = tmp_path / "output"
    assert main(_command(inputs, output)) == 0

    finalized_units_path = tmp_path / "finalized-prediction-units.jsonl"
    finalized_units = [
        {
            "schema_version": "legalforecast.finalized_prediction_units.v1",
            "status": "candidate_excluded",
            "candidate_id": "cand-1",
            "case_id": "case-1",
            "raw_prediction_units_sha256": "1" * 64,
            "unitization_review_queue_sha256": "2" * 64,
            "prediction_units": [],
            "exclusion": {
                "reason": "test exclusion",
                "adjudication_id": "test-adjudication",
                "adjudication_sha256": "3" * 64,
            },
        }
    ]
    _write_jsonl(finalized_units_path, finalized_units)

    verified = verify_decision_text_artifact(
        decision_texts_path=output / "decision-texts.jsonl",
        manifest_path=output / "decision-texts-manifest.json",
        run_card_path=output / "run-cards/build-decision-texts.json",
        selections=_read_jsonl(inputs["selection"]),
        selection_path=inputs["selection"],
        parser_records=_read_jsonl(inputs["parser_manifest"]),
        parser_manifest_path=inputs["parser_manifest"],
        finalized_unit_records=finalized_units,
        finalized_units_path=finalized_units_path,
        markdown_root=inputs["markdown_root"],
    )

    assert verified.records[0]["clearance"]["restriction_status"] == "unknown"


def test_build_decision_texts_accepts_unknown_selection_with_recovered_public_proof(
    tmp_path: Path,
) -> None:
    inputs = _write_inputs(tmp_path, mutation="selection_unknown_recovered_public")

    assert main(_command(inputs, tmp_path / "output")) == 0


def test_build_decision_texts_accepts_closed_recovered_public_clearance(
    tmp_path: Path,
) -> None:
    inputs = _write_inputs(tmp_path, mutation="recovered_public")
    output = tmp_path / "output"

    assert main(_command(inputs, output)) == 0
    clearance = _read_jsonl(output / "decision-texts.jsonl")[0]["clearance"]
    assert clearance["clearance_basis"] == "provider_free_recovered_public"
    assert clearance["reviewer_id"] is None
    assert clearance["reviewed_at"] is None
    assert clearance["recovered_public_lineage"]["purchase_operation_sha256"] == (
        "7" * 64
    )


def test_build_decision_texts_accepts_affirmative_public_provenance(
    tmp_path: Path,
) -> None:
    inputs = _write_inputs(tmp_path, mutation="affirmative_public")
    output = tmp_path / "output"

    assert main(_command(inputs, output)) == 0
    clearance = _read_jsonl(output / "decision-texts.jsonl")[0]["clearance"]
    assert clearance == {
        "status": "cleared",
        "restriction_status": "public",
        "restriction_evidence": ["courtlistener_public_download_record_checked"],
        "reviewer_id": None,
        "controlled_store_provenance": (
            "https://storage.courtlistener.com/recap/example/decision.pdf"
        ),
        "reviewed_at": None,
        "free_or_purchased": "free",
        "clearance_basis": "affirmative_public_provenance",
        "routing_plan_sha256": "8" * 64,
    }


def test_build_decision_texts_accepts_authenticated_model_exception_review(
    tmp_path: Path,
) -> None:
    inputs = _write_inputs(tmp_path, mutation="model_exception_review")
    output = tmp_path / "output"

    assert main(_command(inputs, output)) == 0
    clearance = _read_jsonl(output / "decision-texts.jsonl")[0]["clearance"]
    assert clearance["clearance_basis"] == "authenticated_model_exception_review"
    assert clearance["reviewer_id"] == "google:gemini-3.5-flash"
    assert clearance["reviewed_at"] is None


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
        "--materialization-run-card",
        str(inputs["materialization_run_card"]),
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
    materialization_run_card = tmp_path / "materialize-cohort-documents.json"
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
            "materialization_schema_version": (
                "legalforecast.cohort_document_materialization.v1"
            ),
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
            "materialization_schema_version": (
                "legalforecast.cohort_document_materialization.v1"
            ),
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
    elif mutation == "selection_explicitly_restricted":
        decision_document["redaction_or_seal_status"] = "restricted"
    elif mutation == "selection_malformed_status":
        decision_document["redaction_or_seal_status"] = 1
    elif mutation == "malformed_sealed":
        decision_document["is_sealed"] = "true"
    elif mutation == "malformed_private_restriction":
        restriction_rows[0]["is_private"] = 1
    elif mutation == "null_flags":
        decision_document["is_sealed"] = None
        decision_document["is_private"] = None
        restriction_rows[0]["is_sealed"] = None
        restriction_rows[0]["is_private"] = None
    elif mutation in {"recovered_public", "selection_unknown_recovered_public"}:
        evidence = [
            "courtlistener_recap_fetch_fresh_detail_exact_match",
            "courtlistener_recap_fetch_is_available_true",
            "courtlistener_recap_fetch_is_sealed_false",
            "courtlistener_recap_fetch_no_positive_private_marker",
        ]
        manifest_rows[0]["free_or_purchased"] = "purchased"
        clearance_rows[0].update(
            {
                "restriction_evidence": evidence,
                "reviewer_id": None,
                "controlled_store_provenance": (
                    "courtlistener-rest://recap-documents/decision"
                ),
                "reviewed_at": None,
                "free_or_purchased": "purchased",
                "clearance_basis": "provider_free_recovered_public",
                "routing_plan_sha256": "8" * 64,
                "recovered_public_lineage": {
                    "candidate_id": "cand-1",
                    "source_document_id": "decision",
                    "recovery_run_card_sha256": "3" * 64,
                    "recovery_manifest_sha256": "4" * 64,
                    "recovery_restriction_evidence_sha256": "5" * 64,
                    "purchase_state_sha256": "6" * 64,
                    "purchase_operation_sha256": "7" * 64,
                    "purchase_operation_key": ("00000000-0000-4000-8000-000000000000"),
                    "fresh_recap_detail_sha256": "2" * 64,
                },
            }
        )
        restriction_rows[0]["restriction_evidence"] = evidence
        if mutation == "selection_unknown_recovered_public":
            decision_document.update(
                {
                    "redaction_or_seal_status": "unknown",
                }
            )
    elif mutation in {
        "affirmative_public",
        "affirmative_public_with_reviewer",
        "affirmative_public_wrong_provenance",
        "affirmative_public_wrong_phase",
    }:
        clearance_rows[0].update(
            {
                "restriction_evidence": [
                    "courtlistener_public_download_record_checked"
                ],
                "reviewer_id": (
                    "reviewer:unexpected"
                    if mutation == "affirmative_public_with_reviewer"
                    else None
                ),
                "controlled_store_provenance": (
                    "https://example.invalid/decision.pdf"
                    if mutation == "affirmative_public_wrong_provenance"
                    else "https://storage.courtlistener.com/recap/example/decision.pdf"
                ),
                "reviewed_at": None,
                "free_or_purchased": (
                    "purchased"
                    if mutation == "affirmative_public_wrong_phase"
                    else "free"
                ),
                "clearance_basis": "affirmative_public_provenance",
                "routing_plan_sha256": "8" * 64,
            }
        )
        if mutation == "affirmative_public_wrong_phase":
            manifest_rows[0]["free_or_purchased"] = "purchased"
        restriction_rows[0]["restriction_evidence"] = [
            "courtlistener_public_download_record_checked"
        ]
    elif mutation in {
        "selection_unknown_affirmative",
        "selection_unknown_mismatched_evidence",
        "selection_unknown_selection_evidence_mismatch",
        "selection_unknown_uncanonical",
    }:
        evidence = [
            "courtlistener_rest_docket_exact_match",
            "courtlistener_rest_docket_entry_exact_match",
            "courtlistener_rest_recap_document_exact_match",
            "courtlistener_rest_recap_document_is_available_true",
            "courtlistener_rest_recap_document_is_sealed_unknown",
            "courtlistener_rest_public_download_url_allowlisted",
        ]
        decision_document.update(
            {
                "redaction_or_seal_status": "unknown",
                "restriction_evidence": evidence,
            }
        )
        clearance_rows[0].update(
            {
                "restriction_status": "unknown",
                "restriction_evidence": evidence,
                "reviewer_id": None,
                "controlled_store_provenance": (
                    "https://storage.courtlistener.com/recap/example/decision.pdf"
                ),
                "reviewed_at": None,
                "clearance_basis": "affirmative_public_provenance",
                "routing_plan_sha256": "8" * 64,
            }
        )
        restriction_rows[0].update(
            {
                "restriction_status": "unknown",
                "restriction_evidence": evidence,
            }
        )
        if mutation == "selection_unknown_mismatched_evidence":
            restriction_rows[0]["restriction_evidence"] = ["different-proof"]
        elif mutation == "selection_unknown_selection_evidence_mismatch":
            decision_document["restriction_evidence"] = ["different-proof"]
        elif mutation == "selection_unknown_uncanonical":
            clearance_rows[0].pop("clearance_basis")
            clearance_rows[0].pop("routing_plan_sha256")
            clearance_rows[0]["reviewer_id"] = "reviewer:john"
            clearance_rows[0]["controlled_store_provenance"] = (
                "private-store://cycle-1/reviews"
            )
            clearance_rows[0]["reviewed_at"] = "2026-07-15T12:00:00Z"
    elif mutation == "unknown_clearance_restricted_token":
        decision_document["redaction_or_seal_status"] = "unknown"
        clearance_rows[0]["restriction_status"] = "unknown"
        clearance_rows[0]["redaction_or_seal_status"] = "restricted"
        clearance_rows[0].update(
            {
                "restriction_evidence": ["courtlistener_public_docket"],
                "reviewer_id": None,
                "controlled_store_provenance": (
                    "https://storage.courtlistener.com/recap/example/decision.pdf"
                ),
                "reviewed_at": None,
                "clearance_basis": "affirmative_public_provenance",
                "routing_plan_sha256": "8" * 64,
            }
        )
        restriction_rows[0]["restriction_status"] = "unknown"
    elif mutation in {
        "model_exception_review",
        "model_review_missing_reviewer",
        "model_review_human_timestamp",
        "model_review_wrong_provenance",
    }:
        clearance_rows[0].update(
            {
                "restriction_evidence": [
                    "courtlistener_public_download_record_checked"
                ],
                "reviewer_id": (
                    None
                    if mutation == "model_review_missing_reviewer"
                    else "google:gemini-3.5-flash"
                ),
                "controlled_store_provenance": (
                    "private-store://wrong/model-review"
                    if mutation == "model_review_wrong_provenance"
                    else "private-store://disclosure/model-review"
                ),
                "reviewed_at": (
                    "2026-07-15T12:00:00Z"
                    if mutation == "model_review_human_timestamp"
                    else None
                ),
                "free_or_purchased": "free",
                "clearance_basis": "authenticated_model_exception_review",
                "routing_plan_sha256": "8" * 64,
            }
        )
        restriction_rows[0]["restriction_evidence"] = [
            "courtlistener_public_download_record_checked"
        ]
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
    materialization_run_card.write_text(
        json.dumps(
            {
                "output_paths": [
                    str(download_manifest),
                    str(clearance),
                    str(restriction_evidence),
                    str(tmp_path / "materialization-derivations.jsonl"),
                    str(tmp_path / "cohort-document-materialization.json"),
                    str(tmp_path / "documents"),
                ],
                "output_commitments": {
                    "disclosure_clearance": {
                        "sha256": (
                            "sha256:" + "d" * 64
                            if mutation == "clearance_hash_drift"
                            else _sha256(clearance)
                        )
                    }
                },
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    if mutation in {"repaired_parse", "forged_repair", "noop_repair"}:
        # A page-scoped embedded-text-layer repair is the second accepted
        # conversion provenance.  The decision-text path is the one that
        # motivated the repair -- the incident document is a decision -- so it
        # must accept a valid repair record and refuse a forged one.
        repaired_config = {
            "engine": EMBEDDED_TEXT_LAYER_REPAIR_ENGINE,
            "extraction_method": "pypdf_page_text_v2",
            "repair_revision": EMBEDDED_TEXT_LAYER_REPAIR_REVISION,
            "repaired_page_numbers": [1],
            "parsed_page_count": 2,
            "pinned_parser_revision": EXPECTED_PARSER_REVISION,
            "superseded_text_sha256": hashlib.sha256(b"superseded").hexdigest(),
        }
        if mutation == "forged_repair":
            repaired_config["repair_revision"] = "not-a-known-repair"
        if mutation == "noop_repair":
            # The shape is impeccable; the record simply claims to supersede
            # the very bytes it published, i.e. it repaired nothing.  Only a
            # check that sees the real Markdown can tell.
            repaired_config["superseded_text_sha256"] = hashlib.sha256(
                markdown.encode()
            ).hexdigest()
        parser_rows[0]["parser_config"] = repaired_config
        parser_rows[0]["extracted_text"] = {
            "source_document_id": "decision",
            "extraction_method": EMBEDDED_TEXT_LAYER_REPAIR_METHOD,
            "text_sha256": hashlib.sha256(markdown.encode()).hexdigest(),
            "page_count": 2,
            "quality_flags": [],
            "notes": "pages 1 recovered from the PDF's embedded text layer",
        }

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
        "materialization_run_card": materialization_run_card,
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


def test_build_decision_texts_accepts_a_page_repaired_conversion(
    tmp_path: Path,
) -> None:
    """The decision path must accept the second conversion provenance.

    The document that motivated the page repair is a decision whose disposition
    sentence was dropped, so a repaired decision conversion that this path
    refuses would leave the repair inert exactly where it was needed.
    """

    inputs = _write_inputs(tmp_path, mutation="repaired_parse")
    output = tmp_path / "output"

    assert main(_command(inputs, output)) == 0

    rows = [
        json.loads(line)
        for line in (output / "decision-texts.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    assert rows
    assert rows[0]["extraction_method"] == EMBEDDED_TEXT_LAYER_REPAIR_METHOD
    assert rows[0]["parser_revision"] == EXPECTED_PARSER_REVISION


def test_build_decision_texts_refuses_a_forged_page_repair(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    inputs = _write_inputs(tmp_path, mutation="forged_repair")

    assert main(_command(inputs, tmp_path / "output")) == 2
    assert "repair" in capsys.readouterr().err
    assert not (tmp_path / "output" / "decision-texts.jsonl").exists()


def test_verify_decision_text_artifact_accepts_a_page_repaired_conversion(
    tmp_path: Path,
) -> None:
    """The verify path must accept the repair as well as the build path.

    These are two separate provenance checks in this module, and a repair that
    builds but does not verify would fail at Stage B instead of at build time.
    """

    inputs = _write_inputs(tmp_path, mutation="repaired_parse")
    output = tmp_path / "output"
    assert main(_command(inputs, output)) == 0

    finalized_units_path = tmp_path / "finalized-prediction-units.jsonl"
    finalized_units = [
        {
            "schema_version": "legalforecast.finalized_prediction_units.v1",
            "status": "candidate_excluded",
            "candidate_id": "cand-1",
            "case_id": "case-1",
            "raw_prediction_units_sha256": "1" * 64,
            "unitization_review_queue_sha256": "2" * 64,
            "prediction_units": [],
            "exclusion": {
                "reason": "test exclusion",
                "adjudication_id": "test-adjudication",
                "adjudication_sha256": "3" * 64,
            },
        }
    ]
    _write_jsonl(finalized_units_path, finalized_units)

    verified = verify_decision_text_artifact(
        decision_texts_path=output / "decision-texts.jsonl",
        manifest_path=output / "decision-texts-manifest.json",
        run_card_path=output / "run-cards/build-decision-texts.json",
        selections=_read_jsonl(inputs["selection"]),
        selection_path=inputs["selection"],
        parser_records=_read_jsonl(inputs["parser_manifest"]),
        parser_manifest_path=inputs["parser_manifest"],
        finalized_unit_records=finalized_units,
        finalized_units_path=finalized_units_path,
        markdown_root=inputs["markdown_root"],
    )

    assert verified.records[0]["extraction_method"] == EMBEDDED_TEXT_LAYER_REPAIR_METHOD


def test_build_decision_texts_refuses_a_repair_that_changed_nothing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A repair claiming to supersede its own bytes must be refused here too.

    The shape of such a record is impeccable, so only a check given the real
    published Markdown can catch it.  This is the case that proves the
    decision-text path is held to the same standard as the reuse lane rather
    than to a shape-only subset of it.
    """

    inputs = _write_inputs(tmp_path, mutation="noop_repair")

    assert main(_command(inputs, tmp_path / "output")) == 2
    assert "did not change the superseded Markdown" in capsys.readouterr().err
    assert not (tmp_path / "output" / "decision-texts.jsonl").exists()
