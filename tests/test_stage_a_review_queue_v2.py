"""The candidate-aware review-queue projection keeps v1 intact and honest."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from legalforecast import cli
from legalforecast.cli import CommandError
from legalforecast.labeling import llm_pipeline
from legalforecast.unitization.review_queue import (
    MIXED_VALIDATOR_CODE,
    TERMINAL_ROUTE_REASON,
    UNCLASSIFIED_VALIDATOR_CODE,
    ReviewAction,
    ReviewQueueError,
    ReviewReasonClass,
    ReviewSubject,
    classify_structural_validator_failure,
    review_queue_v2_records,
    review_queue_v2_sidecar_path,
    review_reason_code,
    safe_parsed_structural_flags,
    verify_review_queue_v2_coverage,
)

JsonRecord = dict[str, Any]
V1 = "legalforecast.unitization_review_queue.v1"
V2 = "legalforecast.unitization_review_queue.v2"
ESCALATION_SHA = "e" * 64


def _sha256(payload: str) -> str:
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _construction_row(unit_id: str, *, reason: str = "low_confidence") -> JsonRecord:
    return {
        "schema_version": V1,
        "status": "pending_adjudication",
        "candidate_id": "cand-1",
        "case_id": "case-1",
        "unit_id": unit_id,
        "review_id": f"cand-1:{unit_id}:stage-a-review",
        "route_reason": reason,
        "review_item": {
            "unit_id": unit_id,
            "reason": reason,
            "notes": "Stage A unit requires blinded pre-decision review.",
        },
    }


def _failed_attempt(
    ordinal: int,
    *,
    failure_message: str,
    failure_type: str = "LlmResponseValidationError",
    normalized_body: str = '{"structural_flags": []}',
) -> JsonRecord:
    return {
        "attempt_ordinal": ordinal,
        "raw_response_sha256": _sha256(f"raw-{ordinal}"),
        "normalized_response_sha256": _sha256(normalized_body),
        "failure_type": failure_type,
        "failure_message": failure_message,
    }


def _terminal_row(
    unit_id: str,
    *,
    attempts: tuple[JsonRecord, ...] | None = None,
    escalation_sha256: str = ESCALATION_SHA,
) -> JsonRecord:
    failed_attempts = list(
        attempts
        if attempts is not None
        else (
            _failed_attempt(
                1,
                failure_message=(
                    "affected_unit_ids must uniquely reference existing frozen units"
                ),
            ),
            _failed_attempt(
                2,
                failure_message=(
                    "affected_unit_ids must uniquely reference existing frozen units"
                ),
            ),
        )
    )
    return {
        "schema_version": V1,
        "status": "pending_adjudication",
        "candidate_id": "cand-1",
        "case_id": "case-1",
        "unit_id": unit_id,
        "review_id": f"cand-1:{unit_id}:structural-terminal:{escalation_sha256[:16]}",
        "route_reason": TERMINAL_ROUTE_REASON,
        "review_item": {
            "unit_id": unit_id,
            "reason": TERMINAL_ROUTE_REASON,
            "notes": "The structural reviewer exhausted all reconstruction attempts.",
            "frozen_unit": {"unit_id": unit_id},
            "reviewer_prompt": "prompt",
            "reviewer_prompt_sha256": "b" * 64,
            "predecision_source_commitments": [{"source_document_id": "complaint"}],
            "failed_attempts": failed_attempts,
        },
        "terminal_escalation_sha256": escalation_sha256,
        "raw_prediction_units_sha256": "c" * 64,
        "reviewer_model_key": "google:reviewer",
        "model_registry_sha256": "d" * 64,
    }


def test_v2_separates_subject_reason_and_authoritative_actions() -> None:
    """The four things a v1 route_reason conflates become four fields."""

    (item,) = review_queue_v2_records((_construction_row("unit-1"),))

    assert item["schema_version"] == V2
    assert item["review_subject"] == ReviewSubject.UNIT.value
    assert item["unit_id"] == "unit-1"
    assert item["reason"] == {
        "code": "low_confidence",
        "class": ReviewReasonClass.SUBSTANTIVE.value,
        "summary": "Stage A produced this unit below the confidence floor.",
    }
    # Allowed actions are authoritative; suggested actions are a separate,
    # explicitly non-authoritative channel and stay empty without evidence.
    assert item["allowed_actions"] == [
        ReviewAction.ACCEPT.value,
        ReviewAction.AMEND.value,
        ReviewAction.SPLIT.value,
        ReviewAction.MERGE.value,
        ReviewAction.DROP.value,
        ReviewAction.CANDIDATE_EXCLUSION.value,
    ]
    assert item["suggested_actions"] == []
    assert "route_reason" not in item
    assert review_reason_code(item) == "low_confidence"
    assert review_reason_code(_construction_row("unit-1")) == "low_confidence"


def test_only_structural_omission_allows_add() -> None:
    """ADD is offered exactly where the frozen adjudication validator allows it."""

    omitted = _construction_row("unit-1", reason="structural_omitted")
    spurious = _construction_row("unit-2", reason="structural_spurious")
    omitted_item, spurious_item = review_queue_v2_records((omitted, spurious))

    assert ReviewAction.ADD.value in omitted_item["allowed_actions"]
    assert ReviewAction.ADD.value not in spurious_item["allowed_actions"]


def test_unsupported_route_reason_fails_closed() -> None:
    """An unknown rationale is never silently given a reason class or actions."""

    with pytest.raises(ReviewQueueError, match="unsupported review queue route_reason"):
        review_queue_v2_records((_construction_row("unit-1", reason="invented"),))


def test_terminal_rows_collapse_into_one_candidate_technical_item() -> None:
    """One failed reviewer run is one fact, not N findings about N units."""

    v1_records = (
        _terminal_row("unit-1"),
        _terminal_row("unit-2"),
        _terminal_row("unit-3"),
    )
    v2_records = review_queue_v2_records(v1_records)

    assert len(v2_records) == 1
    (item,) = v2_records
    assert item["review_subject"] == ReviewSubject.CANDIDATE.value
    assert "unit_id" not in item
    assert item["reason"]["class"] == ReviewReasonClass.TECHNICAL.value
    assert item["reason"]["code"] == TERMINAL_ROUTE_REASON
    # Cycle 1 has no candidate-level adjudication consumer. Technical options
    # therefore remain outside the authoritative action contract.
    assert item["allowed_actions"] == []
    assert item["affected_unit_ids"] == ["unit-1", "unit-2", "unit-3"]
    assert item["source_review_ids"] == [record["review_id"] for record in v1_records]
    assert item["terminal_evidence_review_ids"] == [
        record["review_id"] for record in v1_records
    ]
    assert item["terminal_escalation_sha256"] == ESCALATION_SHA
    assert item["reviewer_model_key"] == "google:reviewer"

    review_item = item["review_item"]
    assert review_item["validator_code"] == (
        "structural_flag_affected_unit_ids_invalid"
    )
    assert review_item["invalid_field"] == "affected_unit_ids"
    assert [
        commitment["attempt_ordinal"]
        for commitment in review_item["attempt_commitments"]
    ] == [1, 2]
    assert all(
        set(commitment)
        == {
            "attempt_ordinal",
            "raw_response_sha256",
            "normalized_response_sha256",
            "validator_code",
            "invalid_field",
            "failure_type",
            "failure_message",
        }
        for commitment in review_item["attempt_commitments"]
    )
    assert review_item["safe_parsed_flags"] == []
    assert item["suggested_actions"] == []
    verify_review_queue_v2_coverage(v1_records, v2_records)


def test_coalesced_terminal_row_keeps_its_substantive_unit_item() -> None:
    """A unit already under substantive review keeps its own question."""

    coalesced = {
        **_construction_row("unit-1"),
        "terminal_escalation": _terminal_row("unit-1"),
    }
    v1_records = (coalesced, _terminal_row("unit-2"))
    unit_item, candidate_item = review_queue_v2_records(v1_records)

    assert unit_item["reason"]["code"] == "low_confidence"
    assert unit_item["source_review_ids"] == ["cand-1:unit-1:stage-a-review"]
    # The unit is still affected by the failed run, but its review_id belongs to
    # the substantive item — the candidate item absorbs only the standalone row.
    assert candidate_item["affected_unit_ids"] == ["unit-1", "unit-2"]
    assert candidate_item["source_review_ids"] == [v1_records[1]["review_id"]]
    assert candidate_item["terminal_evidence_review_ids"] == [
        record["review_id"] for record in v1_records
    ]
    verify_review_queue_v2_coverage(v1_records, (unit_item, candidate_item))


def test_all_coalesced_terminal_rows_keep_candidate_evidence_visible() -> None:
    """Coverage stays exact once while terminal provenance includes every row."""

    v1_records = tuple(
        {
            **_construction_row(unit_id),
            "terminal_escalation": _terminal_row(unit_id),
        }
        for unit_id in ("unit-1", "unit-2", "unit-3")
    )
    *unit_items, candidate_item = review_queue_v2_records(v1_records)

    assert [item["source_review_ids"] for item in unit_items] == [
        [record["review_id"]] for record in v1_records
    ]
    assert candidate_item["source_review_ids"] == []
    assert candidate_item["terminal_evidence_review_ids"] == [
        record["review_id"] for record in v1_records
    ]
    # The supported producer -> merge -> projection path keeps every frozen
    # cohort unit in the terminal group; suggestions never narrow this fact.
    assert candidate_item["affected_unit_ids"] == ["unit-1", "unit-2", "unit-3"]
    verify_review_queue_v2_coverage(v1_records, (*unit_items, candidate_item))


def test_conflicting_terminal_escalations_fail_closed() -> None:
    """Two reviewer runs never merge into one item behind a lawyer's back."""

    v1_records = (
        _terminal_row("unit-1"),
        _terminal_row("unit-2", escalation_sha256="f" * 64),
    )
    with pytest.raises(ReviewQueueError, match="conflicting terminal escalations"):
        review_queue_v2_records(v1_records)


def test_terminal_item_requires_attempt_evidence() -> None:
    """A terminal item with no recorded attempt cannot be classified honestly."""

    with pytest.raises(ReviewQueueError, match="records no failed attempt"):
        review_queue_v2_records((_terminal_row("unit-1", attempts=()),))


@pytest.mark.parametrize(
    ("failure_type", "failure_message", "expected"),
    (
        (
            "LlmResponseValidationError",
            "structural reviewer may not rewrite units",
            ("structural_flag_rewrite_forbidden", "structural_flags"),
        ),
        (
            "LlmResponseValidationError",
            "unsupported structural flag_type: invented",
            ("structural_flag_type_unsupported", "flag_type"),
        ),
        (
            "LlmResponseValidationError",
            "citation line range may not exceed 12 lines",
            ("structural_evidence_span_line_range_too_long", "evidence_spans"),
        ),
        (
            "LlmPipelineError",
            "structural_flags must be a sequence",
            (UNCLASSIFIED_VALIDATOR_CODE, None),
        ),
    ),
)
def test_validator_classification_is_deterministic(
    failure_type: str, failure_message: str, expected: tuple[str, str | None]
) -> None:
    """Known validator failures get a stable code; unknown ones say so."""

    assert (
        classify_structural_validator_failure(
            failure_type=failure_type, failure_message=failure_message
        )
        == expected
    )


def test_unclassified_failure_preserves_the_exact_message() -> None:
    """Classification never costs a reviewer the original failure text."""

    message = "some validator nobody has enumerated yet"
    v1_records = (
        _terminal_row(
            "unit-1",
            attempts=(
                _failed_attempt(1, failure_message=message, failure_type="ValueError"),
            ),
        ),
    )
    (item,) = review_queue_v2_records(v1_records)

    assert item["review_item"]["validator_code"] == UNCLASSIFIED_VALIDATOR_CODE
    assert item["review_item"]["invalid_field"] is None
    (commitment,) = item["review_item"]["attempt_commitments"]
    assert commitment["failure_message"] == message
    assert commitment["failure_type"] == "ValueError"


def test_mixed_validator_failures_refuse_to_name_one_code() -> None:
    """Attempts that failed different validators are reported as mixed."""

    v1_records = (
        _terminal_row(
            "unit-1",
            attempts=(
                _failed_attempt(
                    1, failure_message="structural reviewer may not rewrite units"
                ),
                _failed_attempt(2, failure_message="citation line range is empty"),
            ),
        ),
    )
    (item,) = review_queue_v2_records(v1_records)

    assert item["review_item"]["validator_code"] == MIXED_VALIDATOR_CODE
    assert item["review_item"]["invalid_field"] is None
    assert [
        commitment["validator_code"]
        for commitment in item["review_item"]["attempt_commitments"]
    ] == [
        "structural_flag_rewrite_forbidden",
        "structural_evidence_span_line_range_empty",
    ]


def test_safe_parsed_flags_authenticate_bytes_before_parsing() -> None:
    """Bytes that do not match their commitment never reach the JSON decoder."""

    body = json.dumps({"structural_flags": []})
    with pytest.raises(ReviewQueueError, match="does not match its commitment"):
        safe_parsed_structural_flags(
            body, expected_sha256=_sha256("different"), frozen_unit_ids=("unit-1",)
        )


def test_safe_parsed_flags_keep_only_individually_wellformed_flags() -> None:
    """A rejected response can still hold flags worth showing as suggestions."""

    body = json.dumps(
        {
            "structural_flags": [
                {
                    "flag_type": "spurious",
                    "affected_unit_ids": ["unit-1"],
                    "explanation": "Names a dismissal ground, not a claim.",
                },
                {
                    "flag_type": "spurious",
                    "affected_unit_ids": ["unit-9"],
                    "explanation": "References a unit that does not exist.",
                },
                {
                    "flag_type": "invented",
                    "affected_unit_ids": ["unit-1"],
                    "explanation": "Unsupported flag type.",
                },
                {
                    "flag_type": "omitted",
                    "affected_unit_ids": ["unit-1", "unit-1"],
                    "explanation": "Duplicate unit references.",
                },
                {"flag_type": "combined", "affected_unit_ids": ["unit-1"]},
            ]
        }
    )
    flags = safe_parsed_structural_flags(
        body, expected_sha256=_sha256(body), frozen_unit_ids=("unit-1", "unit-2")
    )

    assert flags == (
        {
            "flag_type": "spurious",
            "affected_unit_ids": ["unit-1"],
            "explanation": "Names a dismissal ground, not a claim.",
        },
    )


def test_safe_parsed_flags_tolerate_unparseable_bodies() -> None:
    """An unparseable authenticated body yields nothing rather than an error."""

    body = "not json at all"
    assert (
        safe_parsed_structural_flags(
            body, expected_sha256=_sha256(body), frozen_unit_ids=("unit-1",)
        )
        == ()
    )


def test_safe_flags_become_non_authoritative_suggested_actions() -> None:
    """Suggestions are marked unauthoritative and never widen allowed actions."""

    body = json.dumps(
        {
            "structural_flags": [
                {
                    "flag_type": "spurious",
                    "affected_unit_ids": ["unit-1"],
                    "explanation": "Names a dismissal ground, not a claim.",
                }
            ]
        }
    )
    v1_records = (
        _terminal_row(
            "unit-1",
            attempts=(
                _failed_attempt(
                    1,
                    failure_message="structural reviewer may not rewrite units",
                    normalized_body=body,
                ),
            ),
        ),
    )
    (item,) = review_queue_v2_records(
        v1_records, normalized_responses={("cand-1", 1): body}
    )

    assert item["suggested_actions"] == [
        {
            "authoritative": False,
            "action": ReviewAction.DROP.value,
            "affected_unit_ids": ["unit-1"],
            "rationale": "Names a dismissal ground, not a claim.",
            "source": "rejected_structural_review_response",
        }
    ]
    assert item["review_item"]["safe_parsed_flags"] == [
        {
            "flag_type": "spurious",
            "affected_unit_ids": ["unit-1"],
            "explanation": "Names a dismissal ground, not a claim.",
        }
    ]
    assert ReviewAction.DROP.value not in item["allowed_actions"]


def test_coverage_verifier_rejects_drops_duplicates_and_inventions() -> None:
    """The verifier is independent of the projection it checks."""

    v1_records = (_construction_row("unit-1"), _construction_row("unit-2"))
    v2_records = review_queue_v2_records(v1_records)
    verify_review_queue_v2_coverage(v1_records, v2_records)

    with pytest.raises(ReviewQueueError, match="drops review work"):
        verify_review_queue_v2_coverage(v1_records, v2_records[:1])
    with pytest.raises(ReviewQueueError, match="covers a review twice"):
        verify_review_queue_v2_coverage(v1_records, (*v2_records, v2_records[0]))
    invented = {
        **v2_records[0],
        "review_id": "cand-1:unit-3:stage-a-review",
        "source_review_ids": ["cand-1:unit-3:stage-a-review"],
    }
    with pytest.raises(ReviewQueueError, match="invents review work"):
        verify_review_queue_v2_coverage(v1_records, (*v2_records, invented))


def test_coverage_verifier_rejects_a_dropped_unit() -> None:
    """Collapsing terminal rows may not quietly lose one of the frozen units."""

    v1_records = (_terminal_row("unit-1"), _terminal_row("unit-2"))
    (item,) = review_queue_v2_records(v1_records)
    thinned = {
        **item,
        "affected_unit_ids": ["unit-1"],
    }
    with pytest.raises(ReviewQueueError, match="drops units"):
        verify_review_queue_v2_coverage(v1_records, (thinned,))


def test_coverage_verifier_rejects_an_unknown_review_subject() -> None:
    """A malformed v2 subject is a ReviewQueueError, not a bare ValueError."""

    v1_records = (_construction_row("unit-1"),)
    (item,) = review_queue_v2_records(v1_records)
    malformed = {**item, "review_subject": "not-a-subject"}
    with pytest.raises(
        ReviewQueueError, match="unknown review_subject: not-a-subject"
    ) as caught:
        verify_review_queue_v2_coverage(v1_records, (malformed,))
    assert isinstance(caught.value.__cause__, ValueError)


def test_coverage_verifier_rejects_the_wrong_queue_schema() -> None:
    """Passing a v1 row as a v2 item, or the reverse, fails closed."""

    v1_records = (_construction_row("unit-1"),)
    with pytest.raises(ReviewQueueError, match="v2 record has the wrong schema"):
        verify_review_queue_v2_coverage(v1_records, v1_records)
    v2_records = review_queue_v2_records(v1_records)
    with pytest.raises(ReviewQueueError, match="v1 record has the wrong schema"):
        verify_review_queue_v2_coverage(v2_records, v2_records)


def test_v1_queue_bytes_are_unchanged_by_the_projection() -> None:
    """The authenticated v1 chain is a frozen input, never an output."""

    construction_queue = (_construction_row("unit-1"),)
    terminal_records = (_terminal_row("unit-2"),)
    merged = llm_pipeline.merge_stage_a_review_queue(
        construction_queue, (), terminal_records
    )
    before = json.dumps([dict(record) for record in merged], sort_keys=True)

    v2_records = review_queue_v2_records(merged)
    verify_review_queue_v2_coverage(merged, v2_records)

    assert merged == (*construction_queue, *terminal_records)
    assert json.dumps([dict(record) for record in merged], sort_keys=True) == before


def test_sidecar_path_sits_beside_the_v1_queue() -> None:
    """The projection is a sidecar, not a replacement for the queue file."""

    queue_path = Path("/tmp/out/unitization-review-queue-reviewed.jsonl")
    assert review_queue_v2_sidecar_path(queue_path) == Path(
        "/tmp/out/unitization-review-queue-reviewed-v2.jsonl"
    )


def test_projection_failure_preserves_the_existing_queue_pair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Projection validation runs before either frozen/public queue is published."""

    queue_path = tmp_path / "unitization-review-queue-reviewed.jsonl"
    sidecar_path = review_queue_v2_sidecar_path(queue_path)
    queue_path.write_bytes(b"prior-v1\\n")
    sidecar_path.write_bytes(b"prior-v2\\n")

    def fail_projection(_: object) -> tuple[JsonRecord, ...]:
        raise ReviewQueueError("projection rejected fixture")

    monkeypatch.setattr(cli, "review_queue_v2_records", fail_projection)

    with pytest.raises(CommandError, match="cannot project the Stage A review queue"):
        cli.publish_stage_a_review_queue(queue_path, (_construction_row("unit-1"),))

    assert queue_path.read_bytes() == b"prior-v1\\n"
    assert sidecar_path.read_bytes() == b"prior-v2\\n"


def test_sidecar_write_failure_rolls_back_the_entire_queue_pair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed v2 write cannot leave a new v1 beside an old sidecar."""

    queue_path = tmp_path / "unitization-review-queue-reviewed.jsonl"
    sidecar_path = review_queue_v2_sidecar_path(queue_path)
    queue_path.write_bytes(b"prior-v1\\n")
    sidecar_path.write_bytes(b"prior-v2\\n")
    original_write_bytes = Path.write_bytes
    failed_sidecar_write = False

    def fail_sidecar_write(path: Path, payload: bytes) -> int:
        nonlocal failed_sidecar_write
        if path == sidecar_path and not failed_sidecar_write:
            failed_sidecar_write = True
            raise OSError("sidecar storage unavailable")
        return original_write_bytes(path, payload)

    monkeypatch.setattr(Path, "write_bytes", fail_sidecar_write)

    with pytest.raises(CommandError, match="cannot publish the Stage A review queue"):
        cli.publish_stage_a_review_queue(queue_path, (_construction_row("unit-1"),))

    assert queue_path.read_bytes() == b"prior-v1\\n"
    assert sidecar_path.read_bytes() == b"prior-v2\\n"


def test_first_queue_write_failure_rolls_back_the_entire_queue_pair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A partial v1 overwrite is restored before v2 publication can begin."""

    queue_path = tmp_path / "unitization-review-queue-reviewed.jsonl"
    sidecar_path = review_queue_v2_sidecar_path(queue_path)
    queue_path.write_bytes(b"prior-v1\\n")
    sidecar_path.write_bytes(b"prior-v2\\n")
    original_write_bytes = Path.write_bytes
    failed_queue_write = False

    def partially_overwrite_then_fail(path: Path, payload: bytes) -> int:
        nonlocal failed_queue_write
        if path == queue_path and not failed_queue_write:
            failed_queue_write = True
            original_write_bytes(path, b"partial-v1")
            raise OSError("queue storage unavailable")
        return original_write_bytes(path, payload)

    monkeypatch.setattr(Path, "write_bytes", partially_overwrite_then_fail)

    with pytest.raises(CommandError, match="cannot publish the Stage A review queue"):
        cli.publish_stage_a_review_queue(queue_path, (_construction_row("unit-1"),))

    assert queue_path.read_bytes() == b"prior-v1\\n"
    assert sidecar_path.read_bytes() == b"prior-v2\\n"
