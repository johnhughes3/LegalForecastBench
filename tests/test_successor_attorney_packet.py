"""Tests for the provider-free Stage A successor attorney packet."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import pytest
from legalforecast.ingestion.successor_attorney_packet import (
    AttorneyPacketError,
    build_successor_attorney_packet,
)

JsonRecord = dict[str, Any]


def _jsonl(records: list[JsonRecord]) -> bytes:
    return b"".join(
        json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
        + b"\n"
        for record in records
    )


def _bundle(
    review_id: str,
    candidate_id: str = "candidate-1",
    *,
    terminal: bool = False,
) -> JsonRecord:
    bundle: JsonRecord = {
        "schema_version": "legalforecast.unitization_review_bundle.v1",
        "review_id": review_id,
        "candidate_id": candidate_id,
        "case_id": "case-1",
        "route_reason": "low_confidence",
        "review_item": {"unit_id": "unit-1"},
        "raw_prediction_units": {"prediction_units": []},
        "cited_predecision_markdown": [],
    }
    if terminal:
        bundle["route_reason"] = "structural_reviewer_terminal_reconstruction_failure"
    return bundle


def _unit_v2(review_id: str, candidate_id: str = "candidate-1") -> JsonRecord:
    return {
        "schema_version": "legalforecast.unitization_review_queue.v2",
        "review_id": review_id,
        "review_subject": "unit",
        "candidate_id": candidate_id,
        "case_id": "case-1",
        "unit_id": "unit-1",
        "reason": {
            "code": "low_confidence",
            "class": "substantive",
            "summary": "Stage A produced this unit below the confidence floor.",
        },
        "allowed_actions": [
            "ACCEPT",
            "AMEND",
            "SPLIT",
            "MERGE",
            "DROP",
            "CANDIDATE-EXCLUSION",
        ],
        "suggested_actions": [],
        "source_review_ids": [review_id],
    }


def _terminal_v2(review_id: str, candidate_id: str = "candidate-1") -> JsonRecord:
    digest = "e" * 64
    return {
        "schema_version": "legalforecast.unitization_review_queue.v2",
        "review_id": f"{candidate_id}:structural-terminal:{digest[:16]}",
        "review_subject": "candidate",
        "candidate_id": candidate_id,
        "case_id": "case-1",
        "reason": {
            "code": "structural_reviewer_terminal_reconstruction_failure",
            "class": "technical",
            "summary": (
                "Structural review never produced an accepted flag: every "
                "reconstruction attempt failed local validation. No unit was "
                "adjudicated and no flag was accepted."
            ),
        },
        "allowed_actions": [],
        "suggested_actions": [],
        "affected_unit_ids": ["unit-1"],
        "source_review_ids": [review_id],
        "terminal_evidence_review_ids": [review_id],
        "terminal_escalation_sha256": digest,
        "review_item": {
            "attempt_commitments": [
                {
                    "attempt_ordinal": 1,
                    "raw_response_sha256": "sha256:" + "a" * 64,
                    "normalized_response_sha256": "sha256:" + "b" * 64,
                    "validator_code": "unclassified",
                    "invalid_field": None,
                    "failure_type": "ValueError",
                    "failure_message": "unable to reconstruct structural flags",
                }
            ],
        },
    }


def test_packet_commits_exact_bytes_and_keeps_v1_authoritative() -> None:
    bundle_payload = _jsonl([_bundle("review-1"), _bundle("review-2", terminal=True)])
    queue_payload = _jsonl([_unit_v2("review-1"), _terminal_v2("review-2")])

    packet = build_successor_attorney_packet(bundle_payload, queue_payload)

    manifest = packet.manifest
    assert manifest["schema_version"] == (
        "legalforecast.successor_attorney_packet_manifest.v1"
    )
    assert manifest["authoritative_v1_bundle"] == {
        "schema_version": "legalforecast.unitization_review_bundle.v1",
        "byte_count": len(bundle_payload),
        "sha256": hashlib.sha256(bundle_payload).hexdigest(),
        "review_count": 2,
    }
    assert manifest["observational_v2_review_queue"] == {
        "schema_version": "legalforecast.unitization_review_queue.v2",
        "byte_count": len(queue_payload),
        "sha256": hashlib.sha256(queue_payload).hexdigest(),
        "record_count": 2,
    }
    assert manifest["review_id_coverage"] == {
        "authoritative_v1_review_count": 2,
        "observational_v2_source_review_count": 2,
        "exactly_once": True,
    }

    [candidate] = packet.attorney_view["candidates"]
    assert candidate["authoritative_v1"]["review_ids"] == ["review-1", "review-2"]
    assert candidate["observational_v2"]["unit_items"] == [_unit_v2("review-1")]
    assert candidate["observational_v2"]["terminal_technical_item"] == _terminal_v2(
        "review-2"
    )
    assert "candidate_actions" not in candidate["observational_v2"]


def test_packet_rejects_missing_or_duplicate_v1_coverage() -> None:
    bundle_payload = _jsonl([_bundle("review-1"), _bundle("review-2")])

    with pytest.raises(AttorneyPacketError, match="does not cover every v1 review_id"):
        build_successor_attorney_packet(bundle_payload, _jsonl([_unit_v2("review-1")]))

    with pytest.raises(
        AttorneyPacketError, match="covers a v1 review_id more than once"
    ):
        build_successor_attorney_packet(
            bundle_payload,
            _jsonl([_unit_v2("review-1"), _unit_v2("review-1")]),
        )


def test_packet_rejects_candidate_actions_and_duplicate_terminal_items() -> None:
    bundle_payload = _jsonl([_bundle("review-1"), _bundle("review-2")])
    terminal = _terminal_v2("review-1")
    terminal["allowed_actions"] = ["EXCLUDE-CANDIDATE"]
    with pytest.raises(
        AttorneyPacketError, match="must not advertise candidate actions"
    ):
        build_successor_attorney_packet(
            bundle_payload, _jsonl([terminal, _unit_v2("review-2")])
        )


def test_packet_rejects_duplicate_json_keys_and_byte_tampering() -> None:
    duplicate_key = (
        b'{"schema_version":"legalforecast.unitization_review_bundle.v1",'
        b'"schema_version":"legalforecast.unitization_review_bundle.v1"}\n'
    )
    with pytest.raises(AttorneyPacketError, match="duplicate key"):
        build_successor_attorney_packet(duplicate_key, _jsonl([_unit_v2("review-1")]))

    bundle = _jsonl([_bundle("review-1")])
    packet = build_successor_attorney_packet(bundle, _jsonl([_unit_v2("review-1")]))
    assert (
        packet.manifest["authoritative_v1_bundle"]["sha256"]
        != hashlib.sha256(bundle + b" ").hexdigest()
    )

    with pytest.raises(AttorneyPacketError, match="not JSON"):
        build_successor_attorney_packet(b"{not-json}\n", _jsonl([_unit_v2("review-1")]))

    wrong_schema = _unit_v2("review-1")
    wrong_schema["schema_version"] = "legalforecast.invented.v1"
    with pytest.raises(AttorneyPacketError, match="unsupported schema"):
        build_successor_attorney_packet(bundle, _jsonl([wrong_schema]))


def test_packet_rejects_cross_candidate_and_unit_lineage_swaps() -> None:
    bundles = _jsonl([_bundle("review-1"), _bundle("review-2", "candidate-2")])
    swapped = _unit_v2("review-1", "candidate-2")
    with pytest.raises(AttorneyPacketError, match="crosses v1 candidate or case"):
        build_successor_attorney_packet(
            bundles, _jsonl([swapped, _unit_v2("review-2", "candidate-2")])
        )

    cross_case = _unit_v2("review-1")
    cross_case["case_id"] = "case-2"
    with pytest.raises(AttorneyPacketError, match="crosses v1 candidate or case"):
        build_successor_attorney_packet(
            _jsonl([_bundle("review-1")]), _jsonl([cross_case])
        )

    wrong_unit = _unit_v2("review-1")
    wrong_unit["unit_id"] = "other-unit"
    with pytest.raises(AttorneyPacketError, match="unit_id differs"):
        build_successor_attorney_packet(
            _jsonl([_bundle("review-1")]), _jsonl([wrong_unit])
        )


def test_packet_rejects_tampered_unit_projection_fields() -> None:
    bundle = _jsonl([_bundle("review-1")])

    for field, value, error in (
        ("reason", {"code": "invented", "class": "substantive"}, "reason differs"),
        ("allowed_actions", ["DROP"], "allowed_actions differ"),
        (
            "suggested_actions",
            [{"authoritative": True, "action": "DROP"}],
            "must not advertise suggestions",
        ),
    ):
        tampered = _unit_v2("review-1")
        tampered[field] = value
        with pytest.raises(AttorneyPacketError, match=error):
            build_successor_attorney_packet(bundle, _jsonl([tampered]))


def test_packet_rejects_terminal_attempts_without_producer_commitments() -> None:
    bundle = _jsonl([_bundle("review-1")])

    for field, value, error in (
        ("raw_response_sha256", "not-a-digest", "raw_response_sha256 is not"),
        (
            "normalized_response_sha256",
            "sha256:" + "A" * 64,
            "normalized_response_sha256 is not",
        ),
        ("validator_code", "invented", "validator_code is invalid"),
        ("invalid_field", "invented", "invalid_field is invalid"),
        ("attempt_ordinal", True, "ordinal is invalid"),
    ):
        terminal = _terminal_v2("review-1")
        terminal["review_item"]["attempt_commitments"][0][field] = value
        with pytest.raises(AttorneyPacketError, match=error):
            build_successor_attorney_packet(bundle, _jsonl([terminal]))

    terminal = _terminal_v2("review-1")
    terminal["review_item"]["attempt_commitments"][0].pop("failure_message")
    with pytest.raises(AttorneyPacketError, match="field set"):
        build_successor_attorney_packet(bundle, _jsonl([terminal]))


def test_packet_rejects_terminal_evidence_mismatch_and_is_deterministic() -> None:
    bundles = _jsonl([_bundle("review-1", terminal=True), _bundle("review-2")])
    terminal = _terminal_v2("review-1")
    terminal["terminal_evidence_review_ids"] = ["review-2"]
    with pytest.raises(
        AttorneyPacketError, match="source IDs must be terminal evidence"
    ):
        build_successor_attorney_packet(
            bundles, _jsonl([terminal, _unit_v2("review-2")])
        )

    deterministic_bundles = _jsonl([_bundle("review-1"), _bundle("review-2")])
    queue = _jsonl([_unit_v2("review-1"), _unit_v2("review-2")])
    first = build_successor_attorney_packet(deterministic_bundles, queue)
    second = build_successor_attorney_packet(deterministic_bundles, queue)
    assert first == second

    with pytest.raises(
        AttorneyPacketError, match="more than one terminal technical item"
    ):
        build_successor_attorney_packet(
            _jsonl(
                [
                    _bundle("review-1", terminal=True),
                    _bundle("review-2", terminal=True),
                ]
            ),
            _jsonl([_terminal_v2("review-1"), _terminal_v2("review-2")]),
        )


def test_terminal_evidence_rederives_exact_units_and_accepts_safe_suggestions() -> None:
    bundle = _jsonl([_bundle("review-1")])
    terminal = _terminal_v2("review-1")
    terminal["affected_unit_ids"] = ["unit-1", "invented"]
    with pytest.raises(AttorneyPacketError, match="affected_unit_ids differ"):
        build_successor_attorney_packet(bundle, _jsonl([terminal]))

    terminal = _terminal_v2("review-1")
    terminal["suggested_actions"] = [
        {
            "authoritative": False,
            "action": "DROP",
            "affected_unit_ids": ["unit-1"],
            "rationale": "Visible only as a safe parsed flag.",
            "source": "rejected_structural_review_response",
        }
    ]
    packet = build_successor_attorney_packet(bundle, _jsonl([terminal]))
    assert (
        packet.attorney_view["candidates"][0]["observational_v2"][
            "terminal_technical_item"
        ]["suggested_actions"]
        == terminal["suggested_actions"]
    )

    terminal["suggested_actions"][0]["authoritative"] = True
    with pytest.raises(AttorneyPacketError, match="non-authoritative"):
        build_successor_attorney_packet(bundle, _jsonl([terminal]))


def test_terminal_evidence_accepts_standalone_and_coalesced_v1_bundle_rows() -> None:
    coalesced = _jsonl([_bundle("review-1")])
    assert build_successor_attorney_packet(
        coalesced, _jsonl([_terminal_v2("review-1")])
    )

    standalone = _jsonl([_bundle("review-1", terminal=True)])
    assert build_successor_attorney_packet(
        standalone, _jsonl([_terminal_v2("review-1")])
    )


def test_terminal_suggestions_reject_nonproducer_shape() -> None:
    bundle = _jsonl([_bundle("review-1")])
    terminal = _terminal_v2("review-1")
    suggestion = {
        "authoritative": False,
        "action": "DROP",
        "affected_unit_ids": ["unit-1"],
        "rationale": "Visible only as a safe parsed flag.",
        "source": "rejected_structural_review_response",
    }
    terminal["suggested_actions"] = [suggestion]

    for field, value, error in (
        ("action", "INVENTED", "action is unsupported"),
        ("source", "invented", "source is unsupported"),
        ("affected_unit_ids", ["invented"], "out-of-cohort"),
        ("affected_unit_ids", ["unit-1", "unit-1"], "lacks affected units"),
    ):
        malformed = _terminal_v2("review-1")
        malformed_suggestion = dict(suggestion)
        malformed_suggestion[field] = value
        malformed["suggested_actions"] = [malformed_suggestion]
        with pytest.raises(AttorneyPacketError, match=error):
            build_successor_attorney_packet(bundle, _jsonl([malformed]))

    malformed = _terminal_v2("review-1")
    malformed["suggested_actions"] = [{**suggestion, "extra": "not producer output"}]
    with pytest.raises(AttorneyPacketError, match="field set"):
        build_successor_attorney_packet(bundle, _jsonl([malformed]))
