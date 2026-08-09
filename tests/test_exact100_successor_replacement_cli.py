# pyright: reportPrivateUsage=false

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import legalforecast.cli as cli
import pytest
from legalforecast.ingestion.canonical_json import canonical_json_bytes
from legalforecast.ingestion.mistral_markdown_parser import EXPECTED_PARSER_REVISION
from legalforecast.ingestion.post_selection_terminal_exclusion import (
    RECOVERY_RECEIPT_SCHEMA_VERSION,
    RECOVERY_REQUEST_SCHEMA_VERSION,
    RECOVERY_RUN_CARD_SCHEMA_VERSION,
    REST_OBSERVATION_SCHEMA_VERSION,
    REST_OBSERVATION_TRANSCRIPT_SCHEMA_VERSION,
)
from tests.test_exact100_successor_replacement import (
    _fixture,
    _jsonl,
    _selection_row,
    _write_replay_root,
)


def _bytes(value: object) -> bytes:
    return canonical_json_bytes(
        value, error_type=ValueError, error_message="test serialization failed"
    )


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _stipulated_evidence(
    root: Path,
    *,
    candidate_id: str = "C001",
    source_document: bytes = b"authenticated PDF source",
) -> Path:
    root.mkdir()
    document_id = f"{candidate_id}-motion"
    markdown = b"# [PROPOSED] STIPULATION FOR AND ORDER OF DISMISSAL\n"
    request = {
        "candidate_id": candidate_id,
        "source_document_id": document_id,
        "input_path": f"/authenticated/{candidate_id}/{document_id}.pdf",
        "expected_sha256": _sha(source_document),
        "expected_byte_count": len(source_document),
        "markdown_output_path": f"/authenticated/{candidate_id}/{document_id}.md",
    }
    requests_bytes = _bytes(request)
    record: dict[str, Any] = {
        "candidate_id": candidate_id,
        "source_document_id": document_id,
        "status": "succeeded",
        "input_path": request["input_path"],
        "markdown_path": request["markdown_output_path"],
        "parser_config": {
            "engine": "mistral",
            "parser_revision": EXPECTED_PARSER_REVISION,
            "expected_parser_revision": EXPECTED_PARSER_REVISION,
        },
        "quality_flags": [],
        "source_sha256": _sha(source_document),
        "source_byte_count": len(source_document),
        "extracted_text": {
            "source_document_id": document_id,
            "extraction_method": "mistral_parser_markdown",
            "text_sha256": _sha(markdown),
        },
    }
    manifest_bytes = _bytes(record)
    run_card: dict[str, Any] = {
        "schema_version": "legalforecast.acquisition_run_card.v1",
        "stage": "parse-documents",
        "status": "completed",
        "dry_run": False,
        "execute": True,
        "record_count": 1,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "source_commitments": {
            "requests": {"path": "parse-requests.jsonl", "sha256": _sha(requests_bytes)}
        },
        "output_commitments": {
            "parser_manifest": {
                "path": "mistral-markdown-conversions.jsonl",
                "sha256": _sha(manifest_bytes),
            }
        },
        "parser_execution": {
            "mode": "live_mistral",
            "engine": "mistral",
            "parser_revision": EXPECTED_PARSER_REVISION,
            "fixture_markdown": False,
        },
    }
    files = {
        "parser-requests.jsonl": requests_bytes,
        "parser-record.json": _bytes(record),
        "parser-manifest.json": manifest_bytes,
        "parser-run-card.json": _bytes(run_card),
        "document.md": markdown,
        "document.pdf": source_document,
    }
    for name, payload in files.items():
        (root / name).write_bytes(payload)
    return root


def _recovery_evidence(root: Path, *, candidate_id: str = "C001") -> Path:
    root.mkdir()
    document_id = f"{candidate_id}-motion"
    docket_id = f"docket-{candidate_id}"
    docket_entry_id = f"entry-{candidate_id}"
    response = b'{"detail":"Not found."}'
    request = {
        "schema_version": RECOVERY_REQUEST_SCHEMA_VERSION,
        "candidate_id": candidate_id,
        "source_document_id": document_id,
        "document_role": "motion_to_dismiss_memorandum",
        "courtlistener_docket_id": docket_id,
        "courtlistener_docket_entry_id": docket_entry_id,
        "recovery_mode": "courtlistener_rest_noncharging_only",
        "paid_permitted": False,
        "pacer_permitted": False,
        "recap_fetch_permitted": False,
        "selection_sha256": "deferred",
    }
    # The sealed predecessor binds the selection at replay time.  Populate the
    # request below once the fixture's deterministic selection is available.
    selection = b"".join(
        _bytes(_selection_row(f"C{number:03d}")) for number in range(1, 101)
    )
    request["selection_sha256"] = _sha(selection)
    request_bytes = _bytes(request)
    transcript = {
        "schema_version": REST_OBSERVATION_TRANSCRIPT_SCHEMA_VERSION,
        "candidate_id": candidate_id,
        "source_document_id": document_id,
        "document_role": "motion_to_dismiss_memorandum",
        "courtlistener_docket_id": docket_id,
        "courtlistener_docket_entry_id": docket_entry_id,
        "request_method": "GET",
        "request_path": f"/api/rest/v4/recap-documents/{document_id}/",
        "status_code": 404,
        "response_sha256": _sha(response),
        "terminal_status": "unavailable",
        "terminal": True,
    }
    transcript_bytes = _bytes(transcript)
    observation = {
        "schema_version": REST_OBSERVATION_SCHEMA_VERSION,
        "candidate_id": candidate_id,
        "source_document_id": document_id,
        "document_role": "motion_to_dismiss_memorandum",
        "courtlistener_docket_id": docket_id,
        "courtlistener_docket_entry_id": docket_entry_id,
        "request_sha256": _sha(request_bytes),
        "terminal_status": "unavailable",
        "completed": True,
        "retryable": False,
        "recovered": False,
        "transcript_sha256": _sha(transcript_bytes),
        "transcript_record_count": 1,
    }
    observation_bytes = _bytes(observation)
    receipt = {
        "schema_version": RECOVERY_RECEIPT_SCHEMA_VERSION,
        "candidate_id": candidate_id,
        "source_document_id": document_id,
        "document_role": "motion_to_dismiss_memorandum",
        "recovery_mode": "courtlistener_rest_noncharging_only",
        "terminal_status": "unavailable",
        "completed": True,
        "retryable": False,
        "recovered": False,
        "paid_activity_executed": False,
        "pacer_activity_executed": False,
        "recap_fetch_activity_executed": False,
        "fee_acknowledged": False,
        "request_sha256": _sha(request_bytes),
        "rest_observation_sha256": _sha(observation_bytes),
        "rest_observation_transcript_sha256": _sha(transcript_bytes),
    }
    receipt_bytes = _bytes(receipt)
    run_card = {
        "schema_version": RECOVERY_RUN_CARD_SCHEMA_VERSION,
        "stage": "recover-exact100-target-document-zero-cost",
        "status": "completed",
        "dry_run": False,
        "execute": True,
        "record_count": 1,
        "provider_activity_requested": True,
        "provider_activity_executed": True,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "pacer_activity_executed": False,
        "recap_fetch_activity_executed": False,
        "fee_acknowledged": False,
        "input_commitments": {
            "request": _sha(request_bytes),
            "selection": _sha(selection),
        },
        "output_commitments": {
            "receipt": _sha(receipt_bytes),
            "rest_observation": _sha(observation_bytes),
            "rest_observation_transcript": _sha(transcript_bytes),
            "rest_observation_response": _sha(response),
        },
    }
    for name, payload in {
        "recovery-request.json": request_bytes,
        "recovery-receipt.json": receipt_bytes,
        "recovery-run-card.json": _bytes(run_card),
        "rest-observation.json": observation_bytes,
        "rest-observation-transcript.jsonl": transcript_bytes,
        "rest-observation-response.bin": response,
    }.items():
        (root / name).write_bytes(payload)
    return root


def _command(
    *, predecessor: Path, evidence: Path, output: Path, stipulated: bool = False
) -> list[str]:
    return [
        "acquisition",
        "project-exact100-successor-replacement",
        "--predecessor-root",
        str(predecessor),
        "--stipulated-evidence-root" if stipulated else "--recovery-evidence-root",
        str(evidence),
        "--output-root",
        str(output),
    ]


def _test_only_replay(root: Path) -> tuple[Any, Any]:
    inputs = _fixture(root)
    return inputs["predecessor"], inputs["promotion_pool"]


def test_successor_cli_replays_sealed_input_and_materializer_projection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = tmp_path / "sealed-inputs"
    inputs.mkdir()
    _fixture(inputs)
    evidence = _recovery_evidence(tmp_path / "recovery")
    output = tmp_path / "successor"

    monkeypatch.setattr(
        cli,
        "_replay_exact100_successor_inputs",
        _test_only_replay,
    )
    assert cli.main(_command(predecessor=inputs, evidence=evidence, output=output)) == 0
    verified = cli.verify_completed_target_cohort_projection_for_purchase_approval(
        output
    )

    selection_records = cast(list[dict[str, object]], verified["selection_records"])
    assert [record["candidate_id"] for record in selection_records][-1] == "R2"
    assert len(selection_records) == 100
    assert (output / "successor-terminal-exclusions.jsonl").is_file()
    assert cli.main(_command(predecessor=inputs, evidence=evidence, output=output)) == 0


def test_successor_materializer_rejects_tampered_immutable_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = tmp_path / "sealed-inputs"
    inputs.mkdir()
    _fixture(inputs)
    evidence = _recovery_evidence(tmp_path / "recovery")
    output = tmp_path / "successor"
    monkeypatch.setattr(
        cli,
        "_replay_exact100_successor_inputs",
        _test_only_replay,
    )
    assert cli.main(_command(predecessor=inputs, evidence=evidence, output=output)) == 0

    output.joinpath("case-relevance.jsonl").write_bytes(b"{}\n")
    with pytest.raises(cli.CommandError, match="output changed after replay"):
        cli.verify_completed_target_cohort_projection_for_purchase_approval(output)


def test_successor_cli_exposes_no_manual_candidate_or_provider_switches(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["acquisition", "project-exact100-successor-replacement", "--help"])
    assert excinfo.value.code == 0
    help_text = capsys.readouterr().out
    assert "--predecessor-root" in help_text
    assert "--inputs-root" not in help_text
    assert "--stipulated-evidence-root" in help_text
    assert "--recovery-evidence-root" in help_text
    for forbidden in ("--candidate-id", "--drop-id", "--replacement-id", "--provider"):
        assert forbidden not in help_text


def test_successor_rejects_unexpected_output_before_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = tmp_path / "sealed-inputs"
    inputs.mkdir()
    _fixture(inputs)
    evidence = _recovery_evidence(tmp_path / "recovery")
    output = tmp_path / "successor"
    output.mkdir()
    output.joinpath("unrelated.txt").write_text("no", encoding="utf-8")

    monkeypatch.setattr(
        cli,
        "_replay_exact100_successor_inputs",
        _test_only_replay,
    )
    assert cli.main(_command(predecessor=inputs, evidence=evidence, output=output)) == 2


def test_successor_cli_rejects_fabricated_hash_consistent_input_root(
    tmp_path: Path,
) -> None:
    fabricated = tmp_path / "fabricated-inputs"
    fabricated.mkdir()
    inputs = _fixture(fabricated)
    _write_replay_root(
        fabricated,
        predecessor_config=inputs["projection"],
        predecessor_output_bytes=inputs["predecessor_output_bytes"],
        reserve=inputs["reserve"],
        reserve_selection=inputs["reserve_selection"],
        reserve_artifacts=inputs["reserve_artifacts"],
    )
    evidence = _recovery_evidence(tmp_path / "recovery")
    output = tmp_path / "successor"

    assert (
        cli.main(_command(predecessor=fabricated, evidence=evidence, output=output))
        == 2
    )
    assert not output.exists()


def test_successor_cli_rejects_self_consistent_invented_stipulated_pdf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = tmp_path / "sealed-inputs"
    inputs.mkdir()
    _fixture(inputs)
    evidence = _stipulated_evidence(
        tmp_path / "invented-stipulated",
        source_document=b"invented PDF bytes with a fabricated dismissal",
    )
    output = tmp_path / "successor"

    monkeypatch.setattr(cli, "_replay_exact100_successor_inputs", _test_only_replay)

    assert (
        cli.main(
            _command(
                predecessor=inputs, evidence=evidence, output=output, stipulated=True
            )
        )
        == 2
    )
    assert not output.exists()


def test_production_replay_derives_both_capabilities_from_verified_snapshots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _fixture(tmp_path)
    predecessor_root = tmp_path / "predecessor"
    predecessor_root.mkdir()
    predecessor_state_path = predecessor_root / "run-cards/project-target-cohort.json"
    predecessor_state_path.parent.mkdir()
    original_root = tmp_path / "original"
    original_root.mkdir()
    predecessor_state = {
        "schema_version": cli.ZERO_COST_SUCCESSOR_STATE_SCHEMA,
        "selected_case_count": 100,
        "input_paths": [
            str(original_root),
            *[str(tmp_path / f"unused-{i}") for i in range(14)],
        ],
    }
    predecessor_state_path.write_bytes(_bytes(predecessor_state))
    predecessor_summary_path = predecessor_root / "target-cohort-projection.json"
    predecessor_summary_path.write_bytes(_bytes(fixture["projection"]))
    predecessor_selection_path = predecessor_root / "target-cohort-selection.jsonl"
    predecessor_selection_path.write_bytes(fixture["selection_bytes"])
    predecessor_snapshots = {
        os.path.abspath(predecessor_state_path): predecessor_state_path.read_bytes(),
        os.path.abspath(
            predecessor_summary_path
        ): predecessor_summary_path.read_bytes(),
        **{
            os.path.abspath(predecessor_root / name): payload
            for name, payload in fixture["predecessor_output_bytes"].items()
        },
    }
    monkeypatch.setattr(
        cli,
        "_verify_zero_cost_successor_projection",
        lambda **_kwargs: {
            "run_card": predecessor_state,
            "run_card_path": predecessor_state_path,
            "summary": fixture["projection"],
            "summary_path": predecessor_summary_path,
            "selection_path": predecessor_selection_path,
            "verified_artifact_bytes": predecessor_snapshots,
        },
    )

    original_inputs = tuple(original_root / f"input-{index}" for index in range(9))
    original_summary_path = original_root / "target-cohort-projection.json"
    original_run_card_path = original_root / "run-cards/project-target-cohort.json"
    original_run_card = {"input_paths": [str(path) for path in original_inputs]}
    original_payloads = {
        original_inputs[0]: _jsonl(fixture["reserve_selection"]),
        original_inputs[1]: _jsonl(fixture["reserve_artifacts"]["case_relevance"]),
        original_inputs[2]: _jsonl(fixture["reserve_artifacts"]["download_manifest"]),
        original_inputs[3]: _jsonl(
            fixture["reserve_artifacts"]["disclosure_clearance"]
        ),
        original_inputs[4]: b"{}\n",
        original_inputs[5]: _jsonl(
            fixture["reserve_artifacts"]["restriction_evidence"]
        ),
        original_inputs[6]: b"{}\n",
        original_inputs[7]: b"{}\n",
        original_inputs[8]: b"{}\n",
        original_root / "target-cohort-ranked-reserve.jsonl": _jsonl(
            fixture["reserve"]
        ),
        original_summary_path: b"{}\n",
        original_run_card_path: _bytes(original_run_card),
    }
    monkeypatch.setattr(
        cli,
        "verify_completed_target_cohort_projection_for_purchase_approval",
        lambda _root: {
            "run_card": original_run_card,
            "run_card_path": original_run_card_path,
            "summary_path": original_summary_path,
            "verified_artifact_bytes": {
                os.path.abspath(path): payload
                for path, payload in original_payloads.items()
            },
        },
    )
    monkeypatch.setattr(
        cli,
        "filter_core_documents",
        lambda _records: tuple(
            SimpleNamespace(to_record=lambda row=row: row)
            for row in fixture["reserve_artifacts"]["core_filter_results"]
        ),
    )

    predecessor, promotion_pool = cli._replay_exact100_successor_inputs(
        predecessor_root
    )

    assert len(predecessor.selection) == 100
    assert promotion_pool.promotable_candidate_ids == ("R2", "R3")
