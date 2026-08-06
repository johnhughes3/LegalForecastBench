"""Tests for provider-free planning of opinion-backed docket-history gaps."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path

import pytest
from legalforecast.ingestion.opinion_docket_gap_planner import (
    OpinionDocketGapPlanningError,
    _record_sha256,
    plan_opinion_docket_gaps,
    validate_opinion_docket_gap_paths,
)

_LINEAGE = {
    "source_manifest_sha256": "d" * 64,
    "source_cycle_hash": "e" * 64,
    "source_batch_id": "cycle1-opinion-gap-source-v1",
    "source_batch_digest": "f" * 64,
    "source_exclusions_sha256": "1" * 64,
}


def test_path_validation_accepts_new_outputs_without_walking_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()

    def fail_if_walked(_path: Path, _pattern: str) -> object:
        raise AssertionError("new planner outputs do not require a snapshot walk")

    monkeypatch.setattr(Path, "rglob", fail_if_walked)

    validate_opinion_docket_gap_paths(
        snapshot_path=snapshot,
        writable_paths=(tmp_path / "plan.jsonl", tmp_path / "summary.json"),
    )


@pytest.mark.parametrize("error_type", (OSError, RuntimeError))
def test_path_validation_translates_snapshot_resolution_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    error_type: type[Exception],
) -> None:
    snapshot = tmp_path / "snapshot"
    outputs = (tmp_path / "plan.jsonl", tmp_path / "summary.json")
    original_resolve = Path.resolve

    def resolve(path: Path, *, strict: bool = False) -> Path:
        if path == snapshot:
            raise error_type("platform-specific resolution failure")
        return original_resolve(path, strict=strict)

    monkeypatch.setattr(Path, "resolve", resolve)

    with pytest.raises(OpinionDocketGapPlanningError) as exc_info:
        validate_opinion_docket_gap_paths(
            snapshot_path=snapshot,
            writable_paths=outputs,
        )

    assert str(exc_info.value) == (
        f"cannot resolve immutable screening snapshot path: {snapshot}"
    )


@pytest.mark.parametrize("error_type", (OSError, RuntimeError))
@pytest.mark.parametrize("failing_index", range(4))
def test_path_validation_translates_each_output_resolution_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    error_type: type[Exception],
    failing_index: int,
) -> None:
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    outputs = tuple(tmp_path / f"output-{index}.json" for index in range(4))
    failing_output = outputs[failing_index]
    original_resolve = Path.resolve

    def resolve(path: Path, *, strict: bool = False) -> Path:
        if path == failing_output:
            raise error_type("platform-specific resolution failure")
        return original_resolve(path, strict=strict)

    monkeypatch.setattr(Path, "resolve", resolve)

    with pytest.raises(OpinionDocketGapPlanningError) as exc_info:
        validate_opinion_docket_gap_paths(
            snapshot_path=snapshot,
            writable_paths=outputs,
        )

    assert str(exc_info.value) == (
        f"cannot resolve plan-opinion-docket-gaps output path: {failing_output}"
    )


def test_path_validation_rejects_snapshot_writes_and_duplicate_outputs(
    tmp_path: Path,
) -> None:
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    nested = snapshot / "nested" / "plan.jsonl"

    with pytest.raises(
        OpinionDocketGapPlanningError,
        match="output must be outside the immutable snapshot",
    ):
        validate_opinion_docket_gap_paths(
            snapshot_path=snapshot,
            writable_paths=(nested,),
        )

    shared = tmp_path / "shared.json"
    with pytest.raises(
        OpinionDocketGapPlanningError,
        match="outputs must be distinct",
    ):
        validate_opinion_docket_gap_paths(
            snapshot_path=snapshot,
            writable_paths=(shared, shared),
        )


def test_path_validation_rejects_hard_linked_outputs(tmp_path: Path) -> None:
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    plan = tmp_path / "plan.jsonl"
    summary = tmp_path / "summary.json"
    plan.write_text("{}\n", encoding="utf-8")
    summary.hardlink_to(plan)

    with pytest.raises(
        OpinionDocketGapPlanningError,
        match="outputs hard-link the same file",
    ):
        validate_opinion_docket_gap_paths(
            snapshot_path=snapshot,
            writable_paths=(plan, summary),
        )


def test_path_validation_rejects_output_aliasing_snapshot_evidence(
    tmp_path: Path,
) -> None:
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    evidence = snapshot / "manifest.json"
    evidence.write_text("{}\n", encoding="utf-8")
    output = tmp_path / "plan.jsonl"
    output.hardlink_to(evidence)

    with pytest.raises(
        OpinionDocketGapPlanningError,
        match="output aliases immutable snapshot evidence",
    ):
        validate_opinion_docket_gap_paths(
            snapshot_path=snapshot,
            writable_paths=(output,),
        )


def _gap(candidate_id: str = "courtlistener-docket-71878956") -> dict[str, object]:
    docket_id = candidate_id.removeprefix("courtlistener-docket-")
    return {
        "candidate_id": candidate_id,
        "docket_id": docket_id,
        "reason_code": "opinion_backed_docket_history_incomplete",
        "reason": "opinion_backed_docket_history_incomplete",
        "primary_exclusion_reason": "opinion_backed_docket_history_incomplete",
        "paid_gap_candidate": True,
        "packet_eligible": False,
        "planning_status": "docket_history_recovery_required",
        "opinion_source_binding_verified": True,
        "source_batch_complete_saturated": True,
        "target_motion_linkage_proven": False,
        "earliest_written_disposition_proven": False,
        "eligibility_anchor": "2026-06-30",
        "decision_window_end": "2026-07-15",
        "reconstruction_proof": {
            "docket_id": docket_id,
            "entry_count": 0,
            "cursor_exhausted": True,
            "complete": True,
        },
        "opinion_disposition_evidence": {
            "schema_version": "legalforecast.validated_public_opinion.v1",
            "source_opinion_docket_id": "71234567",
            "cluster_id": "10927691",
            "opinion_id": "11395231",
            "opinion_date": "2026-07-14",
            "public_pdf_url": (
                "https://storage.courtlistener.com/pdf/2026/07/14/example.pdf"
            ),
            "plain_text_sha256": "a" * 64,
            "disposition_excerpt": "The motion to dismiss is denied.",
            "cluster_response_sha256": "b" * 64,
            "opinion_response_sha256": "c" * 64,
        },
    }


def test_planner_selects_only_exact_gap_records_deterministically() -> None:
    later = _gap("courtlistener-docket-9")
    earlier = _gap("courtlistener-docket-10")
    unrelated = {
        "candidate_id": "courtlistener-docket-1",
        "reason": "strict_clean_screen_failed",
    }

    plan = plan_opinion_docket_gaps(
        (later, unrelated, earlier),
        cost_per_docket_usd="3.05",
        **_LINEAGE,
    )

    assert [item.candidate_id for item in plan.items] == [
        "courtlistener-docket-9",
        "courtlistener-docket-10",
    ]
    assert plan.candidate_count == 2
    assert plan.total_projected_cost_usd == "6.10"
    assert plan.to_record()["packet_eligible"] is False
    assert plan.to_record()["paid_activity_requested"] is False
    assert plan.to_record()["paid_activity_executed"] is False
    assert plan.plan_sha256 == plan.to_record()["plan_sha256"]
    assert plan.to_record()["source_manifest_sha256"] == "d" * 64
    assert plan.to_record()["source_exclusions_sha256"] == "1" * 64

    encoded = json.dumps(plan.to_record(), sort_keys=True)
    for forbidden in (
        "document_id",
        "document_ids",
        "source_document_id",
        "acknowledge_pacer_fees",
        "purchase",
    ):
        assert forbidden not in encoded


def test_planner_accepts_sparse_but_nonempty_exhausted_reconstruction() -> None:
    record = _gap()
    proof = record["reconstruction_proof"]
    assert isinstance(proof, dict)
    proof["entry_count"] = 37

    plan = plan_opinion_docket_gaps((record,), cost_per_docket_usd="3.05", **_LINEAGE)

    assert plan.candidate_count == 1


def test_planner_ignores_nonmatching_reason_code() -> None:
    record = _gap()
    record["reason_code"] = "strict_clean_screen_failed"

    plan = plan_opinion_docket_gaps((record,), cost_per_docket_usd="3.05", **_LINEAGE)

    assert plan.items == ()


def test_plan_item_commits_only_public_decision_and_docket_refresh_identity() -> None:
    source = _gap()
    [item] = plan_opinion_docket_gaps(
        (source,), cost_per_docket_usd=Decimal("3.05"), **_LINEAGE
    ).items
    opinion_evidence = source["opinion_disposition_evidence"]
    assert isinstance(opinion_evidence, dict)
    opinion_evidence_sha256 = hashlib.sha256(
        json.dumps(
            opinion_evidence,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode()
    ).hexdigest()

    assert item.to_record() == {
        "candidate_id": "courtlistener-docket-71878956",
        "docket_id": "71878956",
        "decision_date": "2026-07-14",
        "courtlistener_cluster_id": "10927691",
        "courtlistener_opinion_id": "11395231",
        "public_decision_url": (
            "https://storage.courtlistener.com/pdf/2026/07/14/example.pdf"
        ),
        "opinion_plain_text_sha256": "a" * 64,
        "disposition_excerpt_sha256": (
            "946fba1973823c0bf7a8cc94113f7c6c5d12f73ee6b6424553c7073def2cd51c"
        ),
        "opinion_disposition_evidence_sha256": opinion_evidence_sha256,
        "eligibility_anchor": "2026-06-30",
        "decision_window_end": "2026-07-15",
        "refresh_scope": "docket_history_only",
        "reservation_usd": "3.05",
        "packet_eligible": False,
    }


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("packet_eligible", True),
        ("paid_gap_candidate", False),
        ("planning_status", "ready"),
        ("opinion_source_binding_verified", False),
        ("source_batch_complete_saturated", False),
        ("target_motion_linkage_proven", True),
        ("earliest_written_disposition_proven", True),
        ("reason", "strict_clean_screen_failed"),
        ("primary_exclusion_reason", "strict_clean_screen_failed"),
    ),
)
def test_matching_gap_fails_closed_when_boundary_flags_drift(
    field: str,
    value: object,
) -> None:
    record = _gap()
    record[field] = value

    with pytest.raises(OpinionDocketGapPlanningError, match=field):
        plan_opinion_docket_gaps((record,), cost_per_docket_usd="3.05", **_LINEAGE)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("schema_version", "unsupported", "schema_version"),
        ("source_opinion_docket_id", "0", "source_opinion_docket_id"),
        (
            "public_pdf_url",
            "https://storage.courtlistener.com/pdf\\..\\decision.pdf",
            "public_pdf_url",
        ),
    ),
)
def test_matching_gap_requires_validated_public_opinion_evidence(
    field: str,
    value: object,
    message: str,
) -> None:
    record = _gap()
    evidence = record["opinion_disposition_evidence"]
    assert isinstance(evidence, dict)
    evidence[field] = value

    with pytest.raises(OpinionDocketGapPlanningError, match=message):
        plan_opinion_docket_gaps((record,), cost_per_docket_usd="3.05", **_LINEAGE)


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ("candidate_identity", "candidate_id"),
        ("reconstruction_identity", "reconstruction"),
        ("opinion_identity", "source_opinion_docket_id"),
        ("invalid_entry_count", "entry_count"),
        ("unsafe_url", "public_pdf_url"),
    ),
)
def test_matching_gap_rejects_identity_or_public_evidence_drift(
    mutation: str,
    message: str,
) -> None:
    record = _gap()
    if mutation == "candidate_identity":
        record["candidate_id"] = "courtlistener-docket-999"
    elif mutation == "reconstruction_identity":
        proof = record["reconstruction_proof"]
        assert isinstance(proof, dict)
        proof["docket_id"] = "999"
    elif mutation == "opinion_identity":
        evidence = record["opinion_disposition_evidence"]
        assert isinstance(evidence, dict)
        evidence["source_opinion_docket_id"] = "invalid"
    elif mutation == "invalid_entry_count":
        proof = record["reconstruction_proof"]
        assert isinstance(proof, dict)
        proof["entry_count"] = -1
    else:
        evidence = record["opinion_disposition_evidence"]
        assert isinstance(evidence, dict)
        evidence["public_pdf_url"] = "https://evil.example/decision.pdf"

    with pytest.raises(OpinionDocketGapPlanningError, match=message):
        plan_opinion_docket_gaps((record,), cost_per_docket_usd="3.05", **_LINEAGE)


def test_planner_rejects_duplicate_candidate_and_invalid_cost() -> None:
    with pytest.raises(OpinionDocketGapPlanningError, match="duplicate candidate"):
        plan_opinion_docket_gaps(
            (_gap(), _gap()), cost_per_docket_usd="3.05", **_LINEAGE
        )
    for value in ("0", "-1", "NaN", "3.001"):
        with pytest.raises(OpinionDocketGapPlanningError, match="cost_per_docket_usd"):
            plan_opinion_docket_gaps((_gap(),), cost_per_docket_usd=value, **_LINEAGE)


def test_plan_commitment_rejects_nonfinite_numbers() -> None:
    with pytest.raises(ValueError, match="Out of range float values"):
        _record_sha256({"unexpected": float("nan")})


def test_planner_rejects_noncanonical_candidate_identity() -> None:
    record = _gap()
    record["candidate_id"] = " courtlistener-docket-71878956 "

    with pytest.raises(OpinionDocketGapPlanningError, match="candidate_id"):
        plan_opinion_docket_gaps((record,), cost_per_docket_usd="3.05", **_LINEAGE)


def test_planner_rejects_noncanonical_numeric_identity() -> None:
    record = _gap()
    proof = record["reconstruction_proof"]
    assert isinstance(proof, dict)
    proof["docket_id"] = " 71878956 "

    with pytest.raises(OpinionDocketGapPlanningError, match="docket_id"):
        plan_opinion_docket_gaps((record,), cost_per_docket_usd="3.05", **_LINEAGE)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("source_manifest_sha256", "invalid"),
        ("source_cycle_hash", "A" * 64),
        ("source_batch_id", " source "),
        ("source_batch_digest", "0" * 63),
        ("source_exclusions_sha256", ""),
    ),
)
def test_planner_rejects_invalid_source_lineage(field: str, value: str) -> None:
    lineage = {**_LINEAGE, field: value}

    with pytest.raises(OpinionDocketGapPlanningError, match=field):
        plan_opinion_docket_gaps(
            (_gap(),),
            cost_per_docket_usd="3.05",
            **lineage,
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("eligibility_anchor", "2026-07-15", "eligibility_anchor"),
        ("decision_window_end", "2026-07-13", "decision_window_end"),
        ("eligibility_anchor", "not-a-date", "eligibility_anchor"),
        ("decision_window_end", "not-a-date", "decision_window_end"),
    ),
)
def test_planner_reproves_frozen_decision_window(
    field: str,
    value: object,
    message: str,
) -> None:
    record = _gap()
    record[field] = value

    with pytest.raises(OpinionDocketGapPlanningError, match=message):
        plan_opinion_docket_gaps((record,), cost_per_docket_usd="3.05", **_LINEAGE)
