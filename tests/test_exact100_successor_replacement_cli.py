# pyright: reportPrivateUsage=false

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import legalforecast.cli as cli
import pytest
from legalforecast.ingestion import exact100_successor_replacement_cli as successor_cli
from legalforecast.ingestion.canonical_json import canonical_json_bytes
from legalforecast.ingestion.mistral_markdown_parser import EXPECTED_PARSER_REVISION
from legalforecast.ingestion.post_selection_terminal_exclusion import (
    RECOVERY_RECEIPT_SCHEMA_VERSION,
    RECOVERY_REQUEST_SCHEMA_VERSION,
    RECOVERY_RUN_CARD_SCHEMA_VERSION,
    REST_OBSERVATION_SCHEMA_VERSION,
    REST_OBSERVATION_TRANSCRIPT_SCHEMA_VERSION,
    VerifiedTerminalExclusionEvidence,
    _mint_terminal_recovery_evidence_from_producer,
)
from tests.test_exact100_successor_replacement import (
    _fixture,
    _jsonl,
    _selection_row,
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


def _rewrite_recovery_response_self_consistently(
    root: Path, *, response_bytes: bytes
) -> None:
    """Rewrite every caller-owned commitment around a fabricated response."""

    transcript_path = (
        root / successor_cli._RECOVERY_FILES["rest_observation_transcript"]
    )
    transcript = json.loads(transcript_path.read_bytes())
    transcript["response_sha256"] = _sha(response_bytes)
    transcript_bytes = _bytes(transcript)
    transcript_path.write_bytes(transcript_bytes)

    observation_path = root / successor_cli._RECOVERY_FILES["rest_observation"]
    observation = json.loads(observation_path.read_bytes())
    observation["transcript_sha256"] = _sha(transcript_bytes)
    observation_bytes = _bytes(observation)
    observation_path.write_bytes(observation_bytes)

    receipt_path = root / successor_cli._RECOVERY_FILES["receipt"]
    receipt = json.loads(receipt_path.read_bytes())
    receipt["rest_observation_sha256"] = _sha(observation_bytes)
    receipt["rest_observation_transcript_sha256"] = _sha(transcript_bytes)
    receipt_bytes = _bytes(receipt)
    receipt_path.write_bytes(receipt_bytes)

    response_path = root / successor_cli._RECOVERY_FILES["rest_observation_response"]
    response_path.write_bytes(response_bytes)
    run_card_path = root / successor_cli._RECOVERY_FILES["run_card"]
    run_card = json.loads(run_card_path.read_bytes())
    run_card["output_commitments"] = {
        "receipt": _sha(receipt_bytes),
        "rest_observation": _sha(observation_bytes),
        "rest_observation_transcript": _sha(transcript_bytes),
        "rest_observation_response": _sha(response_bytes),
    }
    run_card_path.write_bytes(_bytes(run_card))


@pytest.fixture(autouse=True)
def _fresh_terminal_recovery_test_seam(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Replace only the private live-observation dependency in offline tests."""

    calls = 0

    def replay(
        *, selection_bytes: bytes, plan_bytes: bytes
    ) -> VerifiedTerminalExclusionEvidence:
        nonlocal calls
        calls += 1
        record = json.loads(plan_bytes)["records"][0]
        root = _recovery_evidence(
            tmp_path / f"fresh-live-recovery-{calls}",
            candidate_id=str(record["candidate_id"]),
        )
        payloads = {
            name: (root / filename).read_bytes()
            for name, filename in successor_cli._RECOVERY_FILES.items()
        }
        return _mint_terminal_recovery_evidence_from_producer(
            selection_bytes=selection_bytes,
            request=json.loads(payloads["request"]),
            request_bytes=payloads["request"],
            receipt=json.loads(payloads["receipt"]),
            receipt_bytes=payloads["receipt"],
            run_card=json.loads(payloads["run_card"]),
            run_card_bytes=payloads["run_card"],
            rest_observation=json.loads(payloads["rest_observation"]),
            rest_observation_bytes=payloads["rest_observation"],
            rest_observation_transcript_bytes=payloads["rest_observation_transcript"],
            rest_observation_response_bytes=payloads["rest_observation_response"],
        )

    monkeypatch.setattr(cli, "execute_terminal_recovery_for_successor", replay)


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
    inputs = _fixture()
    return inputs["predecessor"], inputs["promotion_pool"]


def _write_legacy_hash_consistent_forgery(
    root: Path,
    *,
    predecessor_config: dict[str, Any],
    predecessor_output_bytes: dict[str, bytes],
    reserve: list[dict[str, Any]],
    reserve_selection: list[dict[str, Any]],
    reserve_artifacts: dict[str, list[dict[str, Any]]],
) -> None:
    """Write the retired self-authenticating predecessor shape for rejection."""

    root.joinpath("predecessor-config.json").write_bytes(_bytes(predecessor_config))
    for name, payload in predecessor_output_bytes.items():
        root.joinpath(f"predecessor-{name}").write_bytes(payload)
    promotion_bytes = {
        "ranked_reserve": _jsonl(reserve),
        "source_selection": _jsonl(reserve_selection),
        **{name: _jsonl(rows) for name, rows in reserve_artifacts.items()},
    }
    commitments = {name: _sha(payload) for name, payload in promotion_bytes.items()}
    authority = {
        "provider_activity_permitted": False,
        "paid_activity_permitted": False,
        "evaluation_authorized": False,
        "freeze_authorized": False,
        "dispatch_authorized": False,
    }
    producer_config = {
        "schema_version": (
            "legalforecast.exact100_successor_replacement_inputs_config.v1"
        ),
        "status": "completed",
        "source_commitments": commitments,
        **authority,
    }
    producer_config_bytes = _bytes(producer_config)
    producer_run_card = {
        "schema_version": (
            "legalforecast.exact100_successor_replacement_inputs_run_card.v1"
        ),
        "stage": "replay-exact100-successor-replacement-inputs",
        "status": "completed",
        "config_sha256": _sha(producer_config_bytes),
        "source_commitments": commitments,
        "provider_activity_requested": False,
        "provider_activity_executed": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "evaluation_authorized": False,
        "freeze_authorized": False,
        "dispatch_authorized": False,
    }
    producer_run_card_bytes = _bytes(producer_run_card)
    producer_root = {
        "schema_version": "legalforecast.exact100_successor_replacement_inputs_root.v1",
        "producer_config_sha256": _sha(producer_config_bytes),
        "producer_run_card_sha256": _sha(producer_run_card_bytes),
        "source_commitments": commitments,
        **authority,
    }
    root.joinpath("promotion-producer-config.json").write_bytes(producer_config_bytes)
    root.joinpath("promotion-producer-run-card.json").write_bytes(
        producer_run_card_bytes
    )
    root.joinpath("promotion-producer-root.json").write_bytes(_bytes(producer_root))
    for name, payload in promotion_bytes.items():
        file_name = {
            "ranked_reserve": "ranked-reserve.jsonl",
            "source_selection": "source-selection.jsonl",
            "case_relevance": "case-relevance.jsonl",
            "download_manifest": "document-downloads-merged.jsonl",
            "disclosure_clearance": "disclosure-clearance.jsonl",
            "restriction_evidence": "restriction-evidence.jsonl",
            "core_filter_results": "core-filter-results.jsonl",
        }[name]
        root.joinpath(f"promotion-{file_name}").write_bytes(payload)


def test_successor_cli_replays_sealed_input_and_materializer_projection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = tmp_path / "sealed-inputs"
    inputs.mkdir()
    _fixture()
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


def test_saved_recovery_root_alone_cannot_mint_successor_authority(
    tmp_path: Path,
) -> None:
    evidence = _recovery_evidence(tmp_path / "saved-recovery")
    args = SimpleNamespace(
        predecessor_root=tmp_path / "predecessor",
        stipulated_evidence_root=[],
        recovery_evidence_root=[evidence],
        output_root=tmp_path / "successor",
        _replay_inputs=_test_only_replay,
    )

    with pytest.raises(
        successor_cli.Exact100SuccessorReplacementCliError,
        match="requires fresh producer replay",
    ):
        successor_cli.run(args)


def test_successor_rejects_self_consistent_fabricated_recovery_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = tmp_path / "sealed-inputs"
    inputs.mkdir()
    _fixture()
    evidence = _recovery_evidence(tmp_path / "fabricated-recovery")
    _rewrite_recovery_response_self_consistently(
        evidence, response_bytes=_bytes({"detail": "fabricated terminal response"})
    )
    output = tmp_path / "successor"
    monkeypatch.setattr(cli, "_replay_exact100_successor_inputs", _test_only_replay)

    assert cli.main(_command(predecessor=inputs, evidence=evidence, output=output)) == 2
    assert not output.exists()


def test_successor_rejects_saved_404_after_fresh_nonterminal_observation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = tmp_path / "sealed-inputs"
    inputs.mkdir()
    _fixture()
    evidence = _recovery_evidence(tmp_path / "saved-404")
    output = tmp_path / "successor"
    monkeypatch.setattr(cli, "_replay_exact100_successor_inputs", _test_only_replay)

    def reject_nonterminal(**_kwargs: object) -> VerifiedTerminalExclusionEvidence:
        raise ValueError("fresh CourtListener observation returned a public document")

    monkeypatch.setattr(
        cli, "execute_terminal_recovery_for_successor", reject_nonterminal
    )

    assert cli.main(_command(predecessor=inputs, evidence=evidence, output=output)) == 2
    assert not output.exists()


def test_successor_materializer_rejects_tampered_immutable_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = tmp_path / "sealed-inputs"
    inputs.mkdir()
    _fixture()
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


def test_successor_state_rejects_invalid_input_path_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = tmp_path / "sealed-inputs"
    inputs.mkdir()
    _fixture()
    evidence = _recovery_evidence(tmp_path / "recovery")
    output = tmp_path / "successor"
    monkeypatch.setattr(cli, "_replay_exact100_successor_inputs", _test_only_replay)
    assert cli.main(_command(predecessor=inputs, evidence=evidence, output=output)) == 0

    state_path = output / "run-cards/project-target-cohort.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["input_paths"][0] = 1
    with pytest.raises(
        successor_cli.Exact100SuccessorReplacementCliError,
        match="invalid completed exact100 successor run card",
    ):
        successor_cli._verify_state(
            state, target_root=output, expected_target_count=100
        )

    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["recovery_evidence_root_count"] = 2
    with pytest.raises(
        successor_cli.Exact100SuccessorReplacementCliError,
        match="invalid completed exact100 successor run card",
    ):
        successor_cli._verify_state(
            state, target_root=output, expected_target_count=100
        )


def test_successor_overlap_resolves_symlinked_paths(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    alias = tmp_path / "input-alias"
    alias.symlink_to(input_root, target_is_directory=True)

    assert successor_cli._overlaps(alias / "output", input_root)


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
    _fixture()
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
    inputs = _fixture()
    _write_legacy_hash_consistent_forgery(
        fabricated,
        predecessor_config=inputs["predecessor"].projection,
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
    _fixture()
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
    fixture = _fixture()
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
    predecessor_summary_path.write_bytes(_bytes(fixture["predecessor"].projection))
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
            "summary": fixture["predecessor"].projection,
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
        original_root / "core-filter-results.jsonl": _jsonl(
            fixture["reserve_artifacts"]["core_filter_results"]
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
            "authenticated_input_paths": {
                "selection": original_inputs[0],
                "case_relevance": original_inputs[1],
                "download_manifest": original_inputs[2],
                "disclosure_clearance": original_inputs[3],
                "restriction_evidence": original_inputs[5],
                "snapshot_manifest": original_inputs[8],
            },
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

    original_payloads[original_root / "core-filter-results.jsonl"] = b"{}\n"
    with pytest.raises(cli.CommandError, match="core-filter results do not reproduce"):
        cli._replay_exact100_successor_inputs(predecessor_root)

    del predecessor_snapshots[
        os.path.abspath(predecessor_root / "core-filter-results.jsonl")
    ]
    with pytest.raises(
        cli.CommandError,
        match="authenticated projection lacks exact100 predecessor output",
    ):
        cli._replay_exact100_successor_inputs(predecessor_root)
