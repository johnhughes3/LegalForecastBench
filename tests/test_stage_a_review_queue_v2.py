"""The candidate-aware review-queue projection keeps v1 intact and honest."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from threading import Event, Thread
from typing import Any

import pytest
from legalforecast import cli
from legalforecast.cli import CommandError
from legalforecast.labeling import llm_pipeline
from legalforecast.unitization import review_queue_generation as generation_module
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
from legalforecast.unitization.review_queue_generation import (
    read_review_queue_generation,
    review_queue_generation_id,
    review_queue_generation_manifest_path,
    review_queue_generation_root,
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
    original_write = cli.write_review_queue_file_durably
    failed_sidecar_write = False

    def fail_sidecar_write(
        path: Path,
        payload: bytes,
        *,
        parent_anchor: generation_module.ReviewQueueParentAnchor | None = None,
        verify_parent_path: bool = True,
    ) -> None:
        nonlocal failed_sidecar_write
        if path == sidecar_path and not failed_sidecar_write:
            failed_sidecar_write = True
            raise OSError("sidecar storage unavailable")
        original_write(
            path,
            payload,
            parent_anchor=parent_anchor,
            verify_parent_path=verify_parent_path,
        )

    monkeypatch.setattr(cli, "write_review_queue_file_durably", fail_sidecar_write)

    with pytest.raises(CommandError, match="cannot publish the Stage A review queue"):
        cli.publish_stage_a_review_queue(queue_path, (_construction_row("unit-1"),))

    assert queue_path.read_bytes() == b"prior-v1\\n"
    assert sidecar_path.read_bytes() == b"prior-v2\\n"


def test_generation_publish_failure_rolls_back_the_entire_queue_pair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed generation commit cannot leave canonical files ahead of its manifest."""

    queue_path = tmp_path / "unitization-review-queue-reviewed.jsonl"
    sidecar_path = review_queue_v2_sidecar_path(queue_path)
    queue_path.write_bytes(b"prior-v1\\n")
    sidecar_path.write_bytes(b"prior-v2\\n")

    def fail_generation(*_: object, **__: object) -> None:
        raise OSError("generation storage unavailable")

    monkeypatch.setattr(cli, "publish_review_queue_generation", fail_generation)

    with pytest.raises(
        CommandError, match="cannot publish the Stage A review queue generation"
    ):
        cli.publish_stage_a_review_queue(queue_path, (_construction_row("unit-1"),))

    assert queue_path.read_bytes() == b"prior-v1\\n"
    assert sidecar_path.read_bytes() == b"prior-v2\\n"


def test_generation_failure_durably_restores_canonical_pair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pre-commit failure restores both canonical files with durable writes."""

    queue_path = tmp_path / "unitization-review-queue-reviewed.jsonl"
    sidecar_path = review_queue_v2_sidecar_path(queue_path)
    queue_path.write_bytes(b"prior-v1\\n")
    sidecar_path.write_bytes(b"prior-v2\\n")
    writes: list[tuple[Path, bytes]] = []
    original_write = cli.write_review_queue_file_durably

    def record_write(
        path: Path,
        payload: bytes,
        *,
        parent_anchor: generation_module.ReviewQueueParentAnchor | None = None,
        verify_parent_path: bool = True,
    ) -> None:
        writes.append((path, payload))
        original_write(
            path,
            payload,
            parent_anchor=parent_anchor,
            verify_parent_path=verify_parent_path,
        )

    monkeypatch.setattr(cli, "write_review_queue_file_durably", record_write)

    def fail_generation(*_: object, **__: object) -> None:
        raise OSError("generation storage unavailable")

    monkeypatch.setattr(cli, "publish_review_queue_generation", fail_generation)

    with pytest.raises(
        CommandError, match="cannot publish the Stage A review queue generation"
    ):
        cli.publish_stage_a_review_queue(queue_path, (_construction_row("unit-1"),))

    assert [path for path, _ in writes] == [
        queue_path,
        sidecar_path,
        queue_path,
        sidecar_path,
    ]
    assert [payload for _, payload in writes][-2:] == [
        b"prior-v1\\n",
        b"prior-v2\\n",
    ]
    assert queue_path.read_bytes() == b"prior-v1\\n"
    assert sidecar_path.read_bytes() == b"prior-v2\\n"


def test_failed_publisher_cannot_rollback_a_newer_committed_generation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The queue lock serializes commit and rollback across publishers."""

    queue_path = tmp_path / "unitization-review-queue-reviewed.jsonl"
    cli.publish_stage_a_review_queue(queue_path, (_construction_row("prior"),))
    original_publish = cli.publish_review_queue_generation
    first_at_generation = Event()
    allow_first_failure = Event()
    second_done = Event()
    outcomes: dict[str, Exception | None] = {}

    def controlled_publish(
        path: Path,
        *,
        v1_bytes: bytes,
        v2_bytes: bytes,
        parent_anchor: generation_module.ReviewQueueParentAnchor | None = None,
    ) -> object:
        if b'"unit-a"' in v1_bytes:
            first_at_generation.set()
            assert allow_first_failure.wait(timeout=5)
            raise OSError("first generation unavailable")
        return original_publish(
            path,
            v1_bytes=v1_bytes,
            v2_bytes=v2_bytes,
            parent_anchor=parent_anchor,
        )

    monkeypatch.setattr(cli, "publish_review_queue_generation", controlled_publish)

    def publish(name: str, unit_id: str) -> None:
        try:
            cli.publish_stage_a_review_queue(queue_path, (_construction_row(unit_id),))
        except Exception as exc:  # captured for assertions in the parent thread
            outcomes[name] = exc
        else:
            outcomes[name] = None
        finally:
            if name == "second":
                second_done.set()

    first = Thread(target=publish, args=("first", "unit-a"))
    second = Thread(target=publish, args=("second", "unit-b"))
    first.start()
    assert first_at_generation.wait(timeout=5)
    second.start()
    assert not second_done.wait(timeout=0.1)
    allow_first_failure.set()
    first.join(timeout=5)
    second.join(timeout=5)

    assert not first.is_alive()
    assert not second.is_alive()
    assert isinstance(outcomes["first"], CommandError)
    assert outcomes["second"] is None
    generation = read_review_queue_generation(queue_path)
    assert generation.v1_bytes == queue_path.read_bytes()
    assert generation.v2_bytes == review_queue_v2_sidecar_path(queue_path).read_bytes()
    assert b'"unit-b"' in generation.v1_bytes


def test_publication_lock_rejects_parent_swap_while_waiting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The transaction stays bound to the parent used to select its lock."""

    queue_parent = tmp_path / "queue-parent"
    queue_parent.mkdir()
    queue_path = queue_parent / "unitization-review-queue-reviewed.jsonl"
    displaced_parent = tmp_path / "displaced-parent"
    original_flock = cli.fcntl.flock
    swapped = False

    def swap_parent_on_lock(descriptor: int, operation: int) -> None:
        nonlocal swapped
        original_flock(descriptor, operation)
        if operation == cli.fcntl.LOCK_EX and not swapped:
            swapped = True
            queue_parent.rename(displaced_parent)
            queue_parent.mkdir()

    monkeypatch.setattr(cli.fcntl, "flock", swap_parent_on_lock)

    with pytest.raises(CommandError, match="directory changed while acquiring"):
        cli.publish_stage_a_review_queue(queue_path, (_construction_row("unit-a"),))

    assert swapped
    assert list(queue_parent.iterdir()) == []
    assert not (displaced_parent / queue_path.name).exists()


def test_publication_reports_parent_anchor_failure_as_command_error(
    tmp_path: Path,
) -> None:
    """An unsafe queue parent follows the normal CLI error boundary."""

    queue_parent = tmp_path / "queue-parent"
    queue_parent.symlink_to(tmp_path / "missing-parent", target_is_directory=True)
    queue_path = queue_parent / "unitization-review-queue-reviewed.jsonl"

    with pytest.raises(CommandError, match="cannot anchor"):
        cli.publish_stage_a_review_queue(queue_path, (_construction_row("unit-a"),))


def test_publication_lock_is_shared_by_aliases_to_one_parent(tmp_path: Path) -> None:
    """The directory-inode lock is shared across path and temp namespaces."""

    queue_parent = tmp_path / "queue-parent"
    queue_parent.mkdir()
    first_alias = tmp_path / "first-alias"
    second_alias = tmp_path / "second-alias"
    first_alias.symlink_to(queue_parent, target_is_directory=True)
    second_alias.symlink_to(queue_parent, target_is_directory=True)
    first_path = first_alias / "unitization-review-queue-reviewed.jsonl"
    second_path = second_alias / "unitization-review-queue-reviewed.jsonl"
    first_anchor = cli._acquire_review_queue_publication_lock(first_path)
    second_acquired = Event()

    def acquire_second() -> None:
        second_anchor = cli._acquire_review_queue_publication_lock(second_path)
        try:
            second_acquired.set()
        finally:
            cli._release_review_queue_publication_lock(second_anchor)

    second = Thread(target=acquire_second)
    second.start()
    assert not second_acquired.wait(timeout=0.1)
    cli._release_review_queue_publication_lock(first_anchor)
    second.join(timeout=5)

    assert not second.is_alive()
    assert second_acquired.is_set()


def test_publication_rejects_symlink_parent_retargeted_after_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every transaction operation remains bound to the caller's parent alias."""

    original_parent = tmp_path / "original-parent"
    replacement_parent = tmp_path / "replacement-parent"
    original_parent.mkdir()
    replacement_parent.mkdir()
    queue_alias = tmp_path / "queue-alias"
    queue_alias.symlink_to(original_parent, target_is_directory=True)
    queue_path = queue_alias / "unitization-review-queue-reviewed.jsonl"
    original_acquire = cli._acquire_review_queue_publication_lock

    def retarget_after_lock(
        path: Path,
    ) -> generation_module.ReviewQueueParentAnchor:
        result = original_acquire(path)
        queue_alias.unlink()
        queue_alias.symlink_to(replacement_parent, target_is_directory=True)
        return result

    monkeypatch.setattr(
        cli, "_acquire_review_queue_publication_lock", retarget_after_lock
    )

    with pytest.raises(CommandError, match="cannot snapshot"):
        cli.publish_stage_a_review_queue(queue_path, (_construction_row("unit-a"),))

    assert list(original_parent.iterdir()) == []
    assert list(replacement_parent.iterdir()) == []


def test_parent_retarget_after_first_write_rolls_back_original_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rollback uses the retained parent descriptor after the alias moves."""

    original_parent = tmp_path / "original-parent"
    replacement_parent = tmp_path / "replacement-parent"
    original_parent.mkdir()
    replacement_parent.mkdir()
    queue_alias = tmp_path / "queue-alias"
    queue_alias.symlink_to(original_parent, target_is_directory=True)
    queue_path = queue_alias / "unitization-review-queue-reviewed.jsonl"
    sidecar_path = review_queue_v2_sidecar_path(queue_path)
    original_queue = original_parent / queue_path.name
    original_sidecar = original_parent / sidecar_path.name
    original_queue.write_bytes(b"prior-v1\n")
    original_sidecar.write_bytes(b"prior-v2\n")
    original_write = cli.write_review_queue_file_durably
    retargeted = False

    def retarget_after_first_write(
        path: Path,
        payload: bytes,
        *,
        parent_anchor: generation_module.ReviewQueueParentAnchor | None = None,
        verify_parent_path: bool = True,
    ) -> None:
        nonlocal retargeted
        original_write(
            path,
            payload,
            parent_anchor=parent_anchor,
            verify_parent_path=verify_parent_path,
        )
        if path == queue_path and verify_parent_path and not retargeted:
            retargeted = True
            queue_alias.unlink()
            queue_alias.symlink_to(replacement_parent, target_is_directory=True)

    monkeypatch.setattr(
        cli, "write_review_queue_file_durably", retarget_after_first_write
    )

    with pytest.raises(CommandError, match="cannot publish"):
        cli.publish_stage_a_review_queue(queue_path, (_construction_row("unit-a"),))

    assert retargeted
    assert original_queue.read_bytes() == b"prior-v1\n"
    assert original_sidecar.read_bytes() == b"prior-v2\n"
    assert list(replacement_parent.iterdir()) == []


def test_durable_queue_write_replaces_inode_and_fsyncs_file_and_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Canonical publication is atomic and persists bytes plus its directory entry."""

    path = tmp_path / "queue.jsonl"
    path.write_bytes(b"prior\\n")
    prior_inode = path.stat().st_ino
    fsynced_modes: list[int] = []
    original_fsync = generation_module.os.fsync

    def record_fsync(descriptor: int) -> None:
        fsynced_modes.append(os.fstat(descriptor).st_mode)
        original_fsync(descriptor)

    monkeypatch.setattr(generation_module.os, "fsync", record_fsync)
    generation_module.write_review_queue_file_durably(path, b"current\\n")

    assert path.read_bytes() == b"current\\n"
    assert path.stat().st_ino != prior_inode
    assert any(stat.S_ISREG(mode) for mode in fsynced_modes)
    assert any(stat.S_ISDIR(mode) for mode in fsynced_modes)


def test_generation_reader_rejects_fifo_without_blocking(tmp_path: Path) -> None:
    """A FIFO member is rejected promptly instead of waiting for a writer."""

    queue_path = tmp_path / "unitization-review-queue-reviewed.jsonl"
    cli.publish_stage_a_review_queue(queue_path, (_construction_row("unit-1"),))
    generation = read_review_queue_generation(queue_path)
    generation.v1_path.unlink()
    os.mkfifo(generation.v1_path)
    code = (
        "from pathlib import Path; "
        "from legalforecast.unitization.review_queue_generation import "
        "read_review_queue_generation; "
        "read_review_queue_generation(Path(__import__('sys').argv[1]))"
    )

    completed = subprocess.run(
        [sys.executable, "-c", code, str(queue_path)],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert completed.returncode != 0
    assert "regular file with one link" in completed.stderr


def test_manifest_post_commit_fsync_failure_keeps_the_new_canonical_pair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A post-rename durability error cannot roll canonical files backward."""

    queue_path = tmp_path / "unitization-review-queue-reviewed.jsonl"
    sidecar_path = review_queue_v2_sidecar_path(queue_path)
    queue_path.write_bytes(b"prior-v1\\n")
    sidecar_path.write_bytes(b"prior-v2\\n")
    original_fsync = generation_module._fsync_directory_descriptor
    queue_directory_identity = (
        queue_path.parent.stat().st_dev,
        queue_path.parent.stat().st_ino,
    )
    queue_directory_fsyncs = 0

    def fail_final_manifest_fsync(descriptor: int) -> None:
        nonlocal queue_directory_fsyncs
        metadata = os.fstat(descriptor)
        if (metadata.st_dev, metadata.st_ino) == queue_directory_identity:
            queue_directory_fsyncs += 1
            if queue_directory_fsyncs == 4:
                raise OSError("manifest directory unavailable")
        original_fsync(descriptor)

    monkeypatch.setattr(
        generation_module,
        "_fsync_directory_descriptor",
        fail_final_manifest_fsync,
    )

    with pytest.raises(CommandError, match="after the manifest commit"):
        cli.publish_stage_a_review_queue(queue_path, (_construction_row("unit-1"),))

    generation = read_review_queue_generation(queue_path)
    assert queue_path.read_bytes() == generation.v1_bytes
    assert sidecar_path.read_bytes() == generation.v2_bytes
    assert generation.v1_bytes != b"prior-v1\\n"
    assert generation.v2_bytes != b"prior-v2\\n"


def test_first_queue_write_failure_rolls_back_the_entire_queue_pair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A partial v1 overwrite is restored before v2 publication can begin."""

    queue_path = tmp_path / "unitization-review-queue-reviewed.jsonl"
    sidecar_path = review_queue_v2_sidecar_path(queue_path)
    queue_path.write_bytes(b"prior-v1\\n")
    sidecar_path.write_bytes(b"prior-v2\\n")
    original_write = cli.write_review_queue_file_durably
    failed_queue_write = False

    def partially_overwrite_then_fail(
        path: Path,
        payload: bytes,
        *,
        parent_anchor: generation_module.ReviewQueueParentAnchor | None = None,
        verify_parent_path: bool = True,
    ) -> None:
        nonlocal failed_queue_write
        if path == queue_path and not failed_queue_write:
            failed_queue_write = True
            original_write(
                path,
                b"partial-v1",
                parent_anchor=parent_anchor,
                verify_parent_path=verify_parent_path,
            )
            raise OSError("queue storage unavailable")
        original_write(
            path,
            payload,
            parent_anchor=parent_anchor,
            verify_parent_path=verify_parent_path,
        )

    monkeypatch.setattr(
        cli, "write_review_queue_file_durably", partially_overwrite_then_fail
    )

    with pytest.raises(CommandError, match="cannot publish the Stage A review queue"):
        cli.publish_stage_a_review_queue(queue_path, (_construction_row("unit-1"),))

    assert queue_path.read_bytes() == b"prior-v1\\n"
    assert sidecar_path.read_bytes() == b"prior-v2\\n"


def test_publication_records_a_digest_bound_paired_generation(tmp_path: Path) -> None:
    """The manifest names both members and binds their exact bytes."""

    queue_path = tmp_path / "unitization-review-queue-reviewed.jsonl"
    cli.publish_stage_a_review_queue(queue_path, (_construction_row("unit-1"),))

    generation = read_review_queue_generation(queue_path)
    sidecar_path = review_queue_v2_sidecar_path(queue_path)
    assert generation.v1_bytes == queue_path.read_bytes()
    assert generation.v2_bytes == sidecar_path.read_bytes()
    assert generation.generation_id == review_queue_generation_id(
        generation.v1_bytes, generation.v2_bytes
    )
    assert generation.v1_path.parent == generation.v2_path.parent
    assert (
        generation.v1_path.parent
        == review_queue_generation_root(queue_path) / generation.generation_id
    )
    manifest = json.loads(
        review_queue_generation_manifest_path(queue_path).read_bytes()
    )
    assert manifest["generation_id"] == generation.generation_id
    assert set(manifest["members"]) == {"v1", "v2"}
    assert manifest["members"]["v1"]["byte_count"] == len(generation.v1_bytes)


def test_generation_pair_survives_a_torn_canonical_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A crash between the two canonical writes cannot tear the pair readers see.

    This is the window issue #617 describes: a forced termination after the v1
    write but before the v2 write leaves a fresh v1 beside a stale sidecar.  A
    reader that resolves the pair through the manifest still sees the previous
    generation whole, because the manifest rename never happened.
    """

    queue_path = tmp_path / "unitization-review-queue-reviewed.jsonl"
    cli.publish_stage_a_review_queue(queue_path, (_construction_row("unit-1"),))
    first = read_review_queue_generation(queue_path)

    original_write = cli.write_review_queue_file_durably
    sidecar_path = review_queue_v2_sidecar_path(queue_path)

    class _ForcedTermination(BaseException):
        """Stands in for a signal that no except-OSError handler can catch."""

    def terminate_before_sidecar(
        path: Path,
        payload: bytes,
        *,
        parent_anchor: generation_module.ReviewQueueParentAnchor | None = None,
        verify_parent_path: bool = True,
    ) -> None:
        if path == sidecar_path:
            raise _ForcedTermination
        original_write(
            path,
            payload,
            parent_anchor=parent_anchor,
            verify_parent_path=verify_parent_path,
        )

    monkeypatch.setattr(
        cli, "write_review_queue_file_durably", terminate_before_sidecar
    )
    with pytest.raises(_ForcedTermination):
        cli.publish_stage_a_review_queue(
            queue_path, (_construction_row("unit-1"), _construction_row("unit-2"))
        )
    monkeypatch.undo()

    # The canonical pair is exactly the torn state the issue describes.
    assert queue_path.read_bytes() != first.v1_bytes
    assert sidecar_path.read_bytes() == first.v2_bytes

    # The generation reference is still whole and still self-consistent.
    recovered = read_review_queue_generation(queue_path)
    assert recovered == first
    verify_review_queue_v2_coverage(
        [json.loads(line) for line in recovered.v1_bytes.splitlines()],
        [json.loads(line) for line in recovered.v2_bytes.splitlines()],
    )


def test_publication_advances_the_generation_only_after_both_writes(
    tmp_path: Path,
) -> None:
    queue_path = tmp_path / "unitization-review-queue-reviewed.jsonl"
    cli.publish_stage_a_review_queue(queue_path, (_construction_row("unit-1"),))
    first = read_review_queue_generation(queue_path)
    cli.publish_stage_a_review_queue(
        queue_path, (_construction_row("unit-1"), _construction_row("unit-2"))
    )
    second = read_review_queue_generation(queue_path)

    assert second.generation_id != first.generation_id
    # Prior generations stay immutable and readable at their own addresses.
    assert first.v1_path.read_bytes() == first.v1_bytes
    assert first.v2_path.read_bytes() == first.v2_bytes


def test_republishing_identical_records_reuses_one_generation(
    tmp_path: Path,
) -> None:
    queue_path = tmp_path / "unitization-review-queue-reviewed.jsonl"
    cli.publish_stage_a_review_queue(queue_path, (_construction_row("unit-1"),))
    first = read_review_queue_generation(queue_path)
    cli.publish_stage_a_review_queue(queue_path, (_construction_row("unit-1"),))

    assert read_review_queue_generation(queue_path) == first
    assert [
        path.name for path in sorted(review_queue_generation_root(queue_path).iterdir())
    ] == [first.generation_id]


def test_generation_reader_rejects_a_member_changed_after_publication(
    tmp_path: Path,
) -> None:
    queue_path = tmp_path / "unitization-review-queue-reviewed.jsonl"
    cli.publish_stage_a_review_queue(queue_path, (_construction_row("unit-1"),))
    generation = read_review_queue_generation(queue_path)
    generation.v2_path.write_bytes(b'{"tampered": true}\n')

    with pytest.raises(ReviewQueueError, match="changed after publication"):
        read_review_queue_generation(queue_path)


def test_generation_reader_rejects_a_member_path_outside_the_manifest(
    tmp_path: Path,
) -> None:
    queue_path = tmp_path / "unitization-review-queue-reviewed.jsonl"
    cli.publish_stage_a_review_queue(queue_path, (_construction_row("unit-1"),))
    manifest_path = review_queue_generation_manifest_path(queue_path)
    manifest = json.loads(manifest_path.read_bytes())
    manifest["members"]["v2"]["path"] = "../elsewhere/queue-v2.jsonl"
    manifest_path.write_bytes(json.dumps(manifest, sort_keys=True).encode())

    with pytest.raises(ReviewQueueError, match="escapes the manifest"):
        read_review_queue_generation(queue_path)


def test_generation_reader_rejects_a_member_reached_through_a_symlink(
    tmp_path: Path,
) -> None:
    """A member that leaves the manifest's directory is rejected, not read.

    Digest and byte-count agreement is not containment: an escaping member can
    carry exactly the recorded bytes.  Rejecting only a literal ``..`` would
    miss this, because the escape happens when the name is opened rather than
    when it is spelled.
    """

    queue_directory = tmp_path / "queue"
    queue_directory.mkdir()
    queue_path = queue_directory / "unitization-review-queue-reviewed.jsonl"
    cli.publish_stage_a_review_queue(queue_path, (_construction_row("unit-1"),))
    generation = read_review_queue_generation(queue_path)

    outside = tmp_path / "elsewhere"
    outside.mkdir()
    foreign_member = outside / "queue-v2.jsonl"
    foreign_member.write_bytes(generation.v2_bytes)
    generation.v2_path.unlink()
    generation.v2_path.symlink_to(foreign_member)

    with pytest.raises(ReviewQueueError, match="escapes the manifest"):
        read_review_queue_generation(queue_path)


def test_generation_publisher_rejects_an_existing_member_symlink(
    tmp_path: Path,
) -> None:
    """Publishing cannot bless a symlink that its own reader rejects."""

    queue_path = tmp_path / "unitization-review-queue-reviewed.jsonl"
    cli.publish_stage_a_review_queue(queue_path, (_construction_row("unit-1"),))
    generation = read_review_queue_generation(queue_path)
    outside = tmp_path / "outside-v1.jsonl"
    outside.write_bytes(generation.v1_bytes)
    generation.v1_path.unlink()
    generation.v1_path.symlink_to(outside)

    with pytest.raises(ReviewQueueError, match="member is a symlink"):
        generation_module.publish_review_queue_generation(
            queue_path,
            v1_bytes=generation.v1_bytes,
            v2_bytes=generation.v2_bytes,
        )


def test_generation_publisher_and_reader_reject_member_hard_links(
    tmp_path: Path,
) -> None:
    """Immutable generation members must be regular files with one link."""

    queue_path = tmp_path / "unitization-review-queue-reviewed.jsonl"
    cli.publish_stage_a_review_queue(queue_path, (_construction_row("unit-1"),))
    generation = read_review_queue_generation(queue_path)
    outside = tmp_path / "outside-v1.jsonl"
    outside.hardlink_to(generation.v1_path)

    with pytest.raises(ReviewQueueError, match="one link"):
        generation_module.publish_review_queue_generation(
            queue_path,
            v1_bytes=generation.v1_bytes,
            v2_bytes=generation.v2_bytes,
        )
    with pytest.raises(ReviewQueueError, match="one link"):
        read_review_queue_generation(queue_path)


def test_generation_reader_rejects_an_ancestor_symlink_swap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A queue-directory swap cannot redirect an already-validated member path."""

    queue_directory = tmp_path / "queue"
    queue_directory.mkdir()
    queue_path = queue_directory / "unitization-review-queue-reviewed.jsonl"
    cli.publish_stage_a_review_queue(queue_path, (_construction_row("unit-1"),))
    external = tmp_path / "external"
    shutil.copytree(queue_directory, external)
    real_queue_directory = tmp_path / "queue-real"

    original_resolve = generation_module._resolve_member_path
    swapped = False

    def swap_after_resolve(
        relative: str, *, manifest_path: Path, generation_id: str
    ) -> Path:
        nonlocal swapped
        resolved = original_resolve(
            relative, manifest_path=manifest_path, generation_id=generation_id
        )
        if not swapped:
            swapped = True
            queue_directory.rename(real_queue_directory)
            queue_directory.symlink_to(external, target_is_directory=True)
        return resolved

    monkeypatch.setattr(generation_module, "_resolve_member_path", swap_after_resolve)

    with pytest.raises(ReviewQueueError, match="generation tree changed"):
        read_review_queue_generation(queue_path)


def test_generation_reader_rejects_an_ancestor_real_directory_swap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A renamed generations root cannot redirect an anchored reader."""

    queue_path = tmp_path / "unitization-review-queue-reviewed.jsonl"
    cli.publish_stage_a_review_queue(queue_path, (_construction_row("unit-1"),))
    generations_root = review_queue_generation_root(queue_path)
    foreign_root = tmp_path / "foreign-generations"
    shutil.copytree(generations_root, foreign_root)
    original_resolve = generation_module._resolve_member_path
    swapped = False

    def swap_after_resolve(
        relative: str, *, manifest_path: Path, generation_id: str
    ) -> Path:
        nonlocal swapped
        resolved = original_resolve(
            relative, manifest_path=manifest_path, generation_id=generation_id
        )
        if not swapped:
            swapped = True
            generations_root.rename(tmp_path / "generations-real")
            foreign_root.rename(generations_root)
        return resolved

    monkeypatch.setattr(generation_module, "_resolve_member_path", swap_after_resolve)

    with pytest.raises(ReviewQueueError, match="generation tree changed"):
        read_review_queue_generation(queue_path)


def test_generation_publisher_rejects_a_generation_root_swap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Publication cannot commit a manifest after its root entry is replaced."""

    queue_path = tmp_path / "unitization-review-queue-reviewed.jsonl"
    generations_root = review_queue_generation_root(queue_path)
    generations_root.mkdir()
    foreign_root = tmp_path / "foreign-generations"
    foreign_root.mkdir()
    original_write = generation_module._write_immutable_member
    swapped = False

    def swap_before_write(*args: object, **kwargs: object) -> None:
        nonlocal swapped
        if not swapped:
            swapped = True
            generations_root.rename(tmp_path / "generations-real")
            generations_root.symlink_to(foreign_root, target_is_directory=True)
        original_write(*args, **kwargs)

    monkeypatch.setattr(generation_module, "_write_immutable_member", swap_before_write)

    with pytest.raises(ReviewQueueError, match="generation tree changed"):
        generation_module.publish_review_queue_generation(
            queue_path, v1_bytes=b"v1\\n", v2_bytes=b"v2\\n"
        )


def test_generation_publisher_rejects_a_real_generation_root_swap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A real-directory replacement cannot redirect generation publication."""

    queue_path = tmp_path / "unitization-review-queue-reviewed.jsonl"
    generations_root = review_queue_generation_root(queue_path)
    generations_root.mkdir()
    foreign_root = tmp_path / "foreign-generations"
    foreign_root.mkdir()
    original_write = generation_module._write_immutable_member
    swapped = False

    def swap_before_write(*args: object, **kwargs: object) -> None:
        nonlocal swapped
        if not swapped:
            swapped = True
            generations_root.rename(tmp_path / "generations-real")
            foreign_root.rename(generations_root)
        original_write(*args, **kwargs)

    monkeypatch.setattr(generation_module, "_write_immutable_member", swap_before_write)

    with pytest.raises(ReviewQueueError, match="generation tree changed"):
        generation_module.publish_review_queue_generation(
            queue_path, v1_bytes=b"v1\\n", v2_bytes=b"v2\\n"
        )


def test_generation_member_install_never_replaces_a_racing_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A destination created after preflight is rejected without replacement."""

    member_path = tmp_path / "member.jsonl"
    directory_descriptor = os.open(
        tmp_path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    )
    original_atomic_write = generation_module._atomic_write_at

    def race_destination_into_place(*args: object, **kwargs: object) -> None:
        member_path.write_bytes(b"racing-bytes\\n")
        original_atomic_write(*args, **kwargs)

    monkeypatch.setattr(
        generation_module, "_atomic_write_at", race_destination_into_place
    )
    try:
        with pytest.raises(ReviewQueueError, match="not immutable"):
            generation_module._write_immutable_member(
                directory_descriptor,
                member_path.name,
                member_path,
                b"intended-bytes\\n",
            )
    finally:
        os.close(directory_descriptor)

    assert member_path.read_bytes() == b"racing-bytes\\n"


def test_generation_member_install_never_exposes_a_hardlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Atomic no-replace rename keeps the installed inode singly linked."""

    member_path = tmp_path / "member.jsonl"
    directory_descriptor = os.open(
        tmp_path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    )

    def reject_hardlink(*_: object, **__: object) -> None:
        raise AssertionError("immutable installation must not use a hard link")

    monkeypatch.setattr(generation_module.os, "link", reject_hardlink)
    try:
        generation_module._write_immutable_member(
            directory_descriptor,
            member_path.name,
            member_path,
            b"intended-bytes\\n",
        )
    finally:
        os.close(directory_descriptor)

    assert member_path.read_bytes() == b"intended-bytes\\n"
    assert member_path.stat().st_nlink == 1


def test_generation_member_install_uses_darwin_atomic_noreplace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Darwin uses its descriptor-relative exclusive rename primitive."""

    observed: list[tuple[int, bytes, int, bytes, int]] = []

    def renameatx_np(
        source_descriptor: int,
        source_name: bytes,
        destination_descriptor: int,
        destination_name: bytes,
        flags: int,
    ) -> int:
        observed.append(
            (
                source_descriptor,
                source_name,
                destination_descriptor,
                destination_name,
                flags,
            )
        )
        return 0

    class DarwinLibc:
        def __init__(self) -> None:
            self.renameatx_np = renameatx_np

    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(
        generation_module.ctypes,
        "CDLL",
        lambda *_args, **_kwargs: DarwinLibc(),
    )

    generation_module._rename_noreplace_at(
        11, "source.tmp", 12, "member.jsonl", tmp_path / "member.jsonl"
    )

    assert observed == [(11, b"source.tmp", 12, b"member.jsonl", 0x00000004)]


def test_generation_pair_supports_a_legitimate_symlinked_parent(
    tmp_path: Path,
) -> None:
    """A symlinked queue parent is resolved once and remains a legal location."""

    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(real_parent, target_is_directory=True)
    queue_path = linked_parent / "unitization-review-queue-reviewed.jsonl"

    generation_module.publish_review_queue_generation(
        queue_path, v1_bytes=b"v1\\n", v2_bytes=b"v2\\n"
    )

    generation = read_review_queue_generation(queue_path)
    assert generation.v1_bytes == b"v1\\n"
    assert generation.v2_bytes == b"v2\\n"
    assert generation.v1_path.parent.parent.parent == real_parent


@pytest.mark.parametrize("missing_flag", ["O_NOFOLLOW", "O_DIRECTORY"])
def test_generation_reader_fails_closed_without_required_open_flags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, missing_flag: str
) -> None:
    """Safe generation reads refuse platforms without required dirfd flags."""

    queue_path = tmp_path / "unitization-review-queue-reviewed.jsonl"
    generation_module.publish_review_queue_generation(
        queue_path, v1_bytes=b"v1\\n", v2_bytes=b"v2\\n"
    )
    monkeypatch.delattr(generation_module.os, missing_flag, raising=False)

    with pytest.raises(ReviewQueueError, match="requires O_NOFOLLOW and O_DIRECTORY"):
        read_review_queue_generation(queue_path)


def test_generation_reader_rejects_a_member_from_a_different_generation(
    tmp_path: Path,
) -> None:
    """A valid digest in a sibling generation cannot be relabeled as current."""

    queue_path = tmp_path / "unitization-review-queue-reviewed.jsonl"
    cli.publish_stage_a_review_queue(queue_path, (_construction_row("unit-1"),))
    first = read_review_queue_generation(queue_path)
    cli.publish_stage_a_review_queue(
        queue_path, (_construction_row("unit-1"), _construction_row("unit-2"))
    )
    manifest_path = review_queue_generation_manifest_path(queue_path)
    manifest = json.loads(manifest_path.read_bytes())
    manifest["members"]["v2"]["path"] = first.v2_path.relative_to(
        manifest_path.parent
    ).as_posix()
    manifest_path.write_bytes(json.dumps(manifest, sort_keys=True).encode())

    with pytest.raises(ReviewQueueError, match="immutable generation"):
        read_review_queue_generation(queue_path)


def test_generation_reader_rejects_an_unknown_manifest_schema(
    tmp_path: Path,
) -> None:
    queue_path = tmp_path / "unitization-review-queue-reviewed.jsonl"
    cli.publish_stage_a_review_queue(queue_path, (_construction_row("unit-1"),))
    manifest_path = review_queue_generation_manifest_path(queue_path)
    manifest = json.loads(manifest_path.read_bytes())
    manifest["schema_version"] = "legalforecast.unitization_review_queue_generation.v2"
    manifest_path.write_bytes(json.dumps(manifest, sort_keys=True).encode())

    with pytest.raises(ReviewQueueError, match="manifest schema differs"):
        read_review_queue_generation(queue_path)


def test_generation_reader_rejects_a_manifest_that_names_a_foreign_pair(
    tmp_path: Path,
) -> None:
    """A rewritten generation_id cannot relabel bytes it does not address."""

    queue_path = tmp_path / "unitization-review-queue-reviewed.jsonl"
    cli.publish_stage_a_review_queue(queue_path, (_construction_row("unit-1"),))
    manifest_path = review_queue_generation_manifest_path(queue_path)
    manifest = json.loads(manifest_path.read_bytes())
    manifest["generation_id"] = "f" * 64
    manifest_path.write_bytes(json.dumps(manifest, sort_keys=True).encode())

    with pytest.raises(ReviewQueueError, match="does not bind its own member bytes"):
        read_review_queue_generation(queue_path)
