# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownLambdaType=false
# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false
# pyright: reportPrivateUsage=false

from __future__ import annotations

import hashlib
from typing import Any

import pytest
from legalforecast.ingestion.canonical_json import canonical_json_bytes
from legalforecast.ingestion.mistral_markdown_parser import EXPECTED_PARSER_REVISION
from legalforecast.ingestion.post_selection_terminal_exclusion import (
    EXCLUSION_SCHEMA_VERSION,
    RECOVERY_RECEIPT_SCHEMA_VERSION,
    RECOVERY_REQUEST_SCHEMA_VERSION,
    RECOVERY_RUN_CARD_SCHEMA_VERSION,
    REST_OBSERVATION_SCHEMA_VERSION,
    REST_OBSERVATION_TRANSCRIPT_SCHEMA_VERSION,
    PostSelectionTerminalExclusionError,
    VerifiedPostSelectionTerminalExclusions,
    VerifiedTerminalExclusionEvidence,
    _verify_stipulated_target_evidence_for_test,
    require_verified_post_selection_terminal_exclusions,
    require_verified_terminal_exclusion_evidence,
    verify_post_selection_terminal_exclusions,
    verify_terminal_recovery_evidence,
)


def _bytes(value: object) -> bytes:
    return canonical_json_bytes(
        value, error_type=ValueError, error_message="test serialization failed"
    )


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _selection() -> tuple[list[dict[str, Any]], bytes]:
    records = [
        {
            "candidate_id": f"C{number:03d}",
            "identity_resolution": {"courtlistener_docket_id": str(1000 + number)},
            "documents": [
                {
                    "source_document_id": f"D{number:03d}",
                    "document_role": "motion_to_dismiss_memorandum",
                    "courtlistener_docket_entry_id": str(2000 + number),
                }
            ],
        }
        for number in range(1, 101)
    ]
    return records, b"".join(_bytes(record) for record in records)


def _stipulated_inputs(markdown: bytes | None = None) -> dict[str, Any]:
    _, selection_bytes = _selection()
    source_document_bytes = b"%PDF authenticated source bytes"
    markdown = markdown or b"# [PROPOSED] STIPULATION FOR AND ORDER OF DISMISSAL\n"
    parser_request = {
        "candidate_id": "C001",
        "source_document_id": "D001",
        "input_path": "/authenticated/C001/D001.pdf",
        "expected_sha256": _sha(source_document_bytes),
        "expected_byte_count": len(source_document_bytes),
        "markdown_output_path": "/authenticated/C001/D001.md",
    }
    parser_requests_bytes = _bytes(parser_request)
    parser_record = {
        "candidate_id": "C001",
        "source_document_id": "D001",
        "status": "succeeded",
        "input_path": parser_request["input_path"],
        "markdown_path": parser_request["markdown_output_path"],
        "parser_config": {
            "engine": "mistral",
            "parser_revision": EXPECTED_PARSER_REVISION,
            "expected_parser_revision": EXPECTED_PARSER_REVISION,
        },
        "quality_flags": [],
        "source_sha256": _sha(source_document_bytes),
        "source_byte_count": len(source_document_bytes),
        "extracted_text": {
            "source_document_id": "D001",
            "extraction_method": "mistral_parser_markdown",
            "text_sha256": _sha(markdown),
        },
    }
    parser_manifest_bytes = _bytes(parser_record)
    parser_run_card = {
        "schema_version": "legalforecast.acquisition_run_card.v1",
        "stage": "parse-documents",
        "status": "completed",
        "dry_run": False,
        "execute": True,
        "record_count": 1,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "source_commitments": {
            "requests": {
                "path": "parse-requests.jsonl",
                "sha256": _sha(parser_requests_bytes),
            }
        },
        "output_commitments": {
            "parser_manifest": {
                "path": "mistral-markdown-conversions.jsonl",
                "sha256": _sha(parser_manifest_bytes),
            }
        },
        "parser_execution": {
            "mode": "live_mistral",
            "engine": "mistral",
            "parser_revision": EXPECTED_PARSER_REVISION,
            "fixture_markdown": False,
        },
    }
    return {
        "selection_bytes": selection_bytes,
        "authenticated_download_manifest_bytes": _bytes(
            {
                "candidate_id": "C001",
                "source_document_id": "D001",
                "sha256": _sha(source_document_bytes),
                "byte_count": len(source_document_bytes),
            }
        ),
        "candidate_id": "C001",
        "source_document_id": "D001",
        "parser_record": parser_record,
        "parser_requests_bytes": parser_requests_bytes,
        "parser_manifest_bytes": parser_manifest_bytes,
        "parser_run_card_bytes": _bytes(parser_run_card),
        "markdown_bytes": markdown,
        "source_document_bytes": source_document_bytes,
    }


def _stipulated_evidence() -> VerifiedTerminalExclusionEvidence:
    return _verify_stipulated_target_evidence_for_test(**_stipulated_inputs())


def _recovery_fixture() -> dict[str, Any]:
    _, selection_bytes = _selection()
    response_bytes = b'{"detail":"Not found."}'
    request = {
        "schema_version": RECOVERY_REQUEST_SCHEMA_VERSION,
        "candidate_id": "C002",
        "source_document_id": "D002",
        "document_role": "motion_to_dismiss_memorandum",
        "courtlistener_docket_id": "1002",
        "courtlistener_docket_entry_id": "2002",
        "recovery_mode": "courtlistener_rest_noncharging_only",
        "paid_permitted": False,
        "pacer_permitted": False,
        "recap_fetch_permitted": False,
        "selection_sha256": _sha(selection_bytes),
    }
    request_bytes = _bytes(request)
    transcript = {
        "schema_version": REST_OBSERVATION_TRANSCRIPT_SCHEMA_VERSION,
        "candidate_id": "C002",
        "source_document_id": "D002",
        "document_role": "motion_to_dismiss_memorandum",
        "courtlistener_docket_id": "1002",
        "courtlistener_docket_entry_id": "2002",
        "request_method": "GET",
        "request_path": "/api/rest/v4/recap-documents/D002/",
        "status_code": 404,
        "response_sha256": _sha(response_bytes),
        "terminal_status": "unavailable",
        "terminal": True,
    }
    transcript_bytes = _bytes(transcript)
    observation = {
        "schema_version": REST_OBSERVATION_SCHEMA_VERSION,
        "candidate_id": "C002",
        "source_document_id": "D002",
        "document_role": "motion_to_dismiss_memorandum",
        "courtlistener_docket_id": "1002",
        "courtlistener_docket_entry_id": "2002",
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
        "candidate_id": "C002",
        "source_document_id": "D002",
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
            "selection": _sha(selection_bytes),
        },
        "output_commitments": {
            "receipt": _sha(receipt_bytes),
            "rest_observation": _sha(observation_bytes),
            "rest_observation_transcript": _sha(transcript_bytes),
            "rest_observation_response": _sha(response_bytes),
        },
    }
    return {
        "selection_bytes": selection_bytes,
        "request": request,
        "request_bytes": request_bytes,
        "receipt": receipt,
        "receipt_bytes": receipt_bytes,
        "run_card": run_card,
        "run_card_bytes": _bytes(run_card),
        "rest_observation": observation,
        "rest_observation_bytes": observation_bytes,
        "rest_observation_transcript_bytes": transcript_bytes,
        "rest_observation_response_bytes": response_bytes,
    }


def _rebind_recovery_transcript(
    inputs: dict[str, Any], transcript_bytes: bytes, *, record_count: int
) -> None:
    inputs["rest_observation_transcript_bytes"] = transcript_bytes
    inputs["rest_observation"]["transcript_sha256"] = _sha(transcript_bytes)
    inputs["rest_observation"]["transcript_record_count"] = record_count
    inputs["rest_observation_bytes"] = _bytes(inputs["rest_observation"])
    inputs["receipt"]["rest_observation_sha256"] = _sha(
        inputs["rest_observation_bytes"]
    )
    inputs["receipt"]["rest_observation_transcript_sha256"] = _sha(transcript_bytes)
    inputs["receipt_bytes"] = _bytes(inputs["receipt"])
    inputs["run_card"]["output_commitments"]["receipt"] = _sha(inputs["receipt_bytes"])
    inputs["run_card"]["output_commitments"]["rest_observation"] = _sha(
        inputs["rest_observation_bytes"]
    )
    inputs["run_card"]["output_commitments"]["rest_observation_transcript"] = _sha(
        transcript_bytes
    )
    inputs["run_card_bytes"] = _bytes(inputs["run_card"])


def test_stipulated_target_evidence_replays_complete_live_mistral_chain() -> None:
    evidence = _stipulated_evidence()
    _, selection_bytes = _selection()
    authority = verify_post_selection_terminal_exclusions(
        selection_bytes=selection_bytes, evidence=[evidence]
    )

    require_verified_terminal_exclusion_evidence(evidence)
    require_verified_post_selection_terminal_exclusions(authority)
    assert authority.candidate_ids == ("C001",)
    assert authority.records[0]["schema_version"] == EXCLUSION_SCHEMA_VERSION
    assert authority.records[0]["reason"] == "stipulated_ineligible"
    assert authority.records[0]["evidence_commitments"]["parser_requests"].startswith(
        "sha256:"
    )


@pytest.mark.parametrize(
    ("target", "mutation", "message"),
    [
        ("parser_requests_bytes", lambda value: value + b"\n", "blank line"),
        ("parser_manifest_bytes", lambda value: value + b"\n", "blank line"),
        (
            "parser_run_card_bytes",
            lambda value: value.replace(b"live_mistral", b"fixture_markdown"),
            "live-Mistral",
        ),
        (
            "source_document_bytes",
            lambda value: value + b"tampered",
            "authenticated predecessor download",
        ),
        ("markdown_bytes", lambda value: value + b"tampered", "Markdown differs"),
    ],
)
def test_stipulated_target_evidence_rejects_tampered_replay_artifacts(
    target: str, mutation: Any, message: str
) -> None:
    inputs = _stipulated_inputs()
    inputs[target] = mutation(inputs[target])

    with pytest.raises(PostSelectionTerminalExclusionError, match=message):
        _verify_stipulated_target_evidence_for_test(**inputs)


def test_stipulated_target_evidence_rejects_nonproof() -> None:
    inputs = _stipulated_inputs(
        b"# Memorandum in Support of Motion to Dismiss\nNo dismissal occurred.\n"
    )
    with pytest.raises(PostSelectionTerminalExclusionError, match="does not prove"):
        _verify_stipulated_target_evidence_for_test(**inputs)


def test_terminal_recovery_evidence_requires_closed_authenticated_transcript() -> None:
    inputs = _recovery_fixture()
    evidence = verify_terminal_recovery_evidence(**inputs)
    authority = verify_post_selection_terminal_exclusions(
        selection_bytes=inputs["selection_bytes"], evidence=[evidence]
    )

    assert authority.candidate_ids == ("C002",)
    assert authority.records[0]["reason"] == "terminal_missing_core_document"
    assert "rest_observation_transcript" in authority.records[0]["evidence_commitments"]


def test_terminal_recovery_evidence_rejects_empty_transcript_with_rebuilt_hashes() -> (
    None
):
    inputs = _recovery_fixture()
    _rebind_recovery_transcript(inputs, b"", record_count=0)

    with pytest.raises(PostSelectionTerminalExclusionError, match="closed exact match"):
        verify_terminal_recovery_evidence(**inputs)


def test_terminal_recovery_evidence_rejects_two_transcript_rows() -> None:
    inputs = _recovery_fixture()
    original = inputs["rest_observation_transcript_bytes"]
    _rebind_recovery_transcript(inputs, original + original, record_count=2)

    with pytest.raises(PostSelectionTerminalExclusionError, match="closed exact match"):
        verify_terminal_recovery_evidence(**inputs)


def test_terminal_recovery_evidence_rejects_changed_response_sidecar() -> None:
    inputs = _recovery_fixture()
    inputs["rest_observation_response_bytes"] += b"!"
    inputs["run_card"]["output_commitments"]["rest_observation_response"] = _sha(
        inputs["rest_observation_response_bytes"]
    )
    inputs["run_card_bytes"] = _bytes(inputs["run_card"])

    with pytest.raises(PostSelectionTerminalExclusionError, match="not closed"):
        verify_terminal_recovery_evidence(**inputs)


@pytest.mark.parametrize(
    ("target", "field", "value", "message"),
    [
        ("request", "courtlistener_docket_entry_id", "wrong", "closed noncharging"),
        ("receipt", "retryable", True, "terminal noncharging"),
        ("receipt", "paid_activity_executed", True, "terminal noncharging"),
        ("rest_observation", "transcript_record_count", 2, "REST observation"),
    ],
)
def test_terminal_recovery_evidence_rejects_unbound_or_self_asserted_records(
    target: str, field: str, value: object, message: str
) -> None:
    inputs = _recovery_fixture()
    inputs[target][field] = value
    inputs[f"{target}_bytes"] = _bytes(inputs[target])
    if target == "request":
        inputs["receipt"]["request_sha256"] = _sha(inputs["request_bytes"])
        inputs["rest_observation"]["request_sha256"] = _sha(inputs["request_bytes"])
        inputs["rest_observation_bytes"] = _bytes(inputs["rest_observation"])
        inputs["receipt"]["rest_observation_sha256"] = _sha(
            inputs["rest_observation_bytes"]
        )
    if target in {"request", "receipt", "rest_observation"}:
        inputs["receipt"]["rest_observation_sha256"] = _sha(
            inputs["rest_observation_bytes"]
        )
        inputs["receipt_bytes"] = _bytes(inputs["receipt"])
        inputs["run_card"]["input_commitments"]["request"] = _sha(
            inputs["request_bytes"]
        )
        inputs["run_card"]["output_commitments"]["receipt"] = _sha(
            inputs["receipt_bytes"]
        )
        inputs["run_card"]["output_commitments"]["rest_observation"] = _sha(
            inputs["rest_observation_bytes"]
        )
        inputs["run_card_bytes"] = _bytes(inputs["run_card"])

    with pytest.raises(PostSelectionTerminalExclusionError, match=message):
        verify_terminal_recovery_evidence(**inputs)


def test_terminal_authority_rejects_caller_constructed_or_changed_objects() -> None:
    fake_evidence = object.__new__(VerifiedTerminalExclusionEvidence)
    with pytest.raises(PostSelectionTerminalExclusionError, match="verified replay"):
        require_verified_terminal_exclusion_evidence(fake_evidence)

    fake_authority = object.__new__(VerifiedPostSelectionTerminalExclusions)
    with pytest.raises(PostSelectionTerminalExclusionError, match="verified replay"):
        require_verified_post_selection_terminal_exclusions(fake_authority)

    evidence = _stipulated_evidence()
    _, selection_bytes = _selection()
    authority = verify_post_selection_terminal_exclusions(
        selection_bytes=selection_bytes, evidence=[evidence]
    )
    object.__setattr__(authority, "records_bytes", authority.records_bytes + b"\n")
    with pytest.raises(PostSelectionTerminalExclusionError, match="verified replay"):
        require_verified_post_selection_terminal_exclusions(authority)
