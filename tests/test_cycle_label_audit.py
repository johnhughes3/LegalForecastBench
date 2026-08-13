from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from legalforecast import cli
from legalforecast.cli import main
from legalforecast.contracts.schemas import CYCLE_GROUPED_LABEL_AUDIT_PACKET_V1
from legalforecast.labeling import llm_pipeline
from legalforecast.labeling.cycle_label_audit import (
    CycleLabelAuditError,
    case_grouped_label_audit_packet_metrics,
    evaluate_cycle_label_audit,
    plan_cycle_label_audit,
    render_case_grouped_label_audit_packet,
)
from legalforecast.protocol.policy_artifacts import generate_labeling_policy

JUDGE_REGISTRY = Path("model_registries/cycle-1-stage-b-judges-2026-07-12.json")


def test_cycle_plan_samples_all_observed_resolution_strata_and_is_non_circular() -> (
    None
):
    audits = [
        _audit("cand-grant", "fully_dismissed", True),
        _audit("cand-deny", "survives_in_material_respect", False),
        _audit("cand-partial", "partial_dismissal_only", False),
    ]
    policy = _policy()
    plan, augmented, queue = plan_cycle_label_audit(
        label_audit_records=audits,
        selection_records=[_selection(candidate) for candidate in _candidates()],
        finalized_prediction_unit_records=[
            _units(candidate) for candidate in _candidates()
        ],
        decision_text_records=[
            {"document_id": f"decision-{candidate}", "text": "The order resolves it."}
            for candidate in _candidates()
        ],
        policy_record=policy,
    )

    assert plan["population_count"] == 3
    assert plan["sample_count"] == 3
    assert {row["stratum"] for row in plan["sampled_units"]} == {
        "unanimous_grant",
        "unanimous_deny",
        "partial",
    }
    assert len(queue) == 3
    assert all(row["packet"]["blind_reliability_study"] for row in queue)
    assert all("ensemble" not in row["packet"] for row in queue)
    seed = plan["seed_sha256"]

    adjudications = {
        row["review_id"]: _adjudication(row, matching=True)
        for row in plan["sampled_units"]
    }
    gates = evaluate_cycle_label_audit(
        plan=plan,
        label_audit_records=augmented,
        adjudications_by_review_id=adjudications,
        policy_record=policy,
    )
    assert all(gate["status"] == "passed" for gate in gates)
    assert plan["seed_sha256"] == seed


def test_cycle_gate_fails_closed_on_per_stratum_error() -> None:
    audits = [
        _audit("cand-grant", "fully_dismissed", True),
        _audit("cand-deny", "survives_in_material_respect", False),
        _audit("cand-partial", "partial_dismissal_only", False),
    ]
    policy = _policy()
    plan, augmented, _ = plan_cycle_label_audit(
        label_audit_records=audits,
        selection_records=[_selection(candidate) for candidate in _candidates()],
        finalized_prediction_unit_records=[
            _units(candidate) for candidate in _candidates()
        ],
        decision_text_records=[
            {"document_id": f"decision-{candidate}", "text": "The order resolves it."}
            for candidate in _candidates()
        ],
        policy_record=policy,
    )
    adjudications = {
        row["review_id"]: _adjudication(row, matching=row["stratum"] != "partial")
        for row in plan["sampled_units"]
    }

    with pytest.raises(CycleLabelAuditError, match="failed closed"):
        evaluate_cycle_label_audit(
            plan=plan,
            label_audit_records=augmented,
            adjudications_by_review_id=adjudications,
            policy_record=policy,
        )


def test_cycle_gate_reconstructs_plan_from_policy_and_rejects_rehashed_tampering() -> (
    None
):
    policy = _policy()
    plan, augmented, _ = _fixture_plan(policy)
    tampered = json.loads(json.dumps(plan))
    tampered["sampling_policy"]["max_llm_error_rate"] = 1.0
    unhashed = dict(tampered)
    del unhashed["plan_sha256"]
    tampered["plan_sha256"] = hashlib.sha256(
        json.dumps(unhashed, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    adjudications = {
        row["review_id"]: _adjudication(row, matching=True)
        for row in plan["sampled_units"]
    }

    with pytest.raises(CycleLabelAuditError, match="pinned policy and corpus"):
        evaluate_cycle_label_audit(
            plan=tampered,
            label_audit_records=augmented,
            adjudications_by_review_id=adjudications,
            policy_record=policy,
        )


def test_cycle_gate_rejects_wrong_adjudication_identity() -> None:
    policy = _policy()
    plan, augmented, _ = _fixture_plan(policy)
    adjudications = {
        row["review_id"]: _adjudication(row, matching=True)
        for row in plan["sampled_units"]
    }
    first_review_id = str(plan["sampled_units"][0]["review_id"])
    adjudications[first_review_id]["candidate_id"] = "wrong-candidate"

    with pytest.raises(CycleLabelAuditError, match="candidate identity mismatch"):
        evaluate_cycle_label_audit(
            plan=plan,
            label_audit_records=augmented,
            adjudications_by_review_id=adjudications,
            policy_record=policy,
        )


def test_cycle_gate_rejects_single_reviewer_as_null_disagreement_rate() -> None:
    policy = _policy()
    plan, augmented, _ = _fixture_plan(policy)
    adjudications = {
        row["review_id"]: _adjudication(row, matching=True)
        for row in plan["sampled_units"]
    }
    first_review_id = str(plan["sampled_units"][0]["review_id"])
    adjudications[first_review_id]["reviewer_responses"] = adjudications[
        first_review_id
    ]["reviewer_responses"][:1]

    with pytest.raises(CycleLabelAuditError, match="at least two independent"):
        evaluate_cycle_label_audit(
            plan=plan,
            label_audit_records=augmented,
            adjudications_by_review_id=adjudications,
            policy_record=policy,
        )


def test_audit_adjudication_cannot_rewrite_label_or_change_drawn_sample() -> None:
    candidate = "cand-partial"
    policy = _policy()
    audit = _audit(candidate, "partial_dismissal_only", False)
    kwargs = {
        "label_audit_records": [audit],
        "selection_records": [_selection(candidate)],
        "finalized_prediction_unit_records": [_units(candidate)],
        "decision_text_records": [
            {
                "document_id": f"decision-{candidate}",
                "text": "The order resolves it.",
            }
        ],
        "policy_record": policy,
    }
    plan, augmented, _ = plan_cycle_label_audit(**kwargs)
    sample = plan["sampled_units"][0]
    auto_label = audit["ensemble"]["decisions"][0]["unanimous_label"]
    changed_adjudication = _adjudication(sample, matching=False)

    resumed = llm_pipeline.apply_adjudicated_reviews(
        label_records=[auto_label],
        adjudication_records=[changed_adjudication],
        decision_texts={
            f"decision-{candidate}": llm_pipeline.StageBDecisionText(
                document_id=f"decision-{candidate}",
                entered_date="2026-07-01",
                text="The order resolves it.",
            )
        },
        label_audit_records=(),
    )
    replanned, _, _ = plan_cycle_label_audit(
        **{**kwargs, "label_audit_records": augmented}
    )

    assert resumed.records[0]["unit_resolution"] == "partial_dismissal_only"
    assert replanned["seed_sha256"] == plan["seed_sha256"]
    assert replanned["sampled_units"] == plan["sampled_units"]


def test_cycle_plan_rejects_empty_auto_label_population() -> None:
    with pytest.raises(CycleLabelAuditError, match="population is empty"):
        plan_cycle_label_audit(
            label_audit_records=[],
            selection_records=[],
            finalized_prediction_unit_records=[],
            decision_text_records=[],
            policy_record=_policy(),
        )


def test_case_grouped_packet_deduplicates_disposition_without_mutating_queue() -> None:
    _, _, queue = _fixture_plan(_policy())
    first = next(row for row in queue if row["candidate_id"] == "cand-grant")
    second = json.loads(json.dumps(first))
    second["unit_id"] = "unit-cand-grant-second"
    second["review_id"] = "cand-grant:unit-cand-grant-second:label-audit"
    second["packet"]["unit_id"] = second["unit_id"]
    second["packet"]["review_id"] = second["review_id"]
    second["packet"]["materials"][0]["material_id"] = (
        "unit-cand-grant-second:frozen-unit"
    )
    second["packet"]["materials"][0]["text"] = '{"claim_name":"Count II"}'
    second["packet"]["materials"][1]["material_id"] = (
        "unit-cand-grant-second:first-written-disposition"
    )
    queue = (*reversed(queue), second)
    queue_before = json.dumps(queue, sort_keys=True, separators=(",", ":"))

    packet = render_case_grouped_label_audit_packet(queue)

    assert json.dumps(queue, sort_keys=True, separators=(",", ":")) == queue_before
    assert [case["case_id"] for case in packet["cases"]] == [
        "case-cand-deny",
        "case-cand-grant",
        "case-cand-partial",
    ]
    grant_case = packet["cases"][1]
    assert grant_case["candidate_id"] == "cand-grant"
    assert grant_case["disposition_evidence"]["text"] == "The order resolves it."
    assert (
        grant_case["disposition_evidence"]["material_id"]
        == "case-cand-grant:first-written-disposition"
    )
    assert [item["review_id"] for item in grant_case["review_items"]] == [
        "cand-grant:unit-cand-grant-second:label-audit",
        "cand-grant:unit-cand-grant:label-audit",
    ]
    assert all(
        all(material["kind"] != "decision_excerpt" for material in item["materials"])
        for item in grant_case["review_items"]
    )


def test_case_grouped_packet_rejects_duplicate_review_ids() -> None:
    _, _, queue = _fixture_plan(_policy())
    duplicate = json.loads(json.dumps(queue[0]))

    with pytest.raises(
        CycleLabelAuditError,
        match=f"unique review ids: {duplicate['case_id']}",
    ):
        render_case_grouped_label_audit_packet((queue[0], duplicate))


def test_case_grouped_packet_schema_has_versioned_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, queue = _fixture_plan(_policy())

    packet = render_case_grouped_label_audit_packet(queue)
    schema_version = str(CYCLE_GROUPED_LABEL_AUDIT_PACKET_V1)
    monkeypatch.chdir(tmp_path)
    contract = (
        Path(__file__).resolve().parents[1]
        / "docs"
        / "schemas"
        / "case-grouped-label-audit-packet-v1.md"
    ).read_text(encoding="utf-8")

    assert packet["schema_version"] == schema_version
    assert f"`{schema_version}`" in contract


def test_case_grouped_packet_rejects_cross_case_disposition_leakage() -> None:
    _, _, queue = _fixture_plan(_policy())
    leaked = json.loads(json.dumps(queue[0]))
    leaked["case_id"] = queue[1]["case_id"]
    leaked["candidate_id"] = queue[1]["candidate_id"]
    leaked["packet"]["candidate_id"] = queue[1]["candidate_id"]

    with pytest.raises(CycleLabelAuditError, match="conflicting disposition evidence"):
        render_case_grouped_label_audit_packet((queue[1], leaked))


def test_case_grouped_packet_rejects_multiple_candidates_for_a_case() -> None:
    _, _, queue = _fixture_plan(_policy())
    other_candidate = json.loads(json.dumps(queue[0]))
    other_candidate["case_id"] = queue[1]["case_id"]
    other_candidate["candidate_id"] = "cand-other"
    other_candidate["packet"]["candidate_id"] = "cand-other"

    with pytest.raises(CycleLabelAuditError, match="one candidate per case"):
        render_case_grouped_label_audit_packet((queue[1], other_candidate))


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("blind_reliability_study", None),
        ("blind_reliability_study", "true"),
        ("review_reason", None),
        ("review_reason", False),
    ],
)
def test_case_grouped_packet_rejects_missing_or_invalid_required_item_fields(
    field: str,
    invalid_value: object,
) -> None:
    _, _, queue = _fixture_plan(_policy())
    malformed = json.loads(json.dumps(queue[0]))
    packet = malformed["packet"]
    if invalid_value is None:
        packet.pop(field)
    else:
        packet[field] = invalid_value

    with pytest.raises(CycleLabelAuditError, match=field):
        render_case_grouped_label_audit_packet((malformed,))


def test_case_grouped_packet_metrics_reduce_multi_unit_disposition_bytes() -> None:
    _, _, queue = _fixture_plan(_policy())
    duplicate = json.loads(
        json.dumps(next(row for row in queue if row["candidate_id"] == "cand-grant"))
    )
    duplicate["unit_id"] = "unit-cand-grant-second"
    duplicate["review_id"] = "cand-grant:unit-cand-grant-second:label-audit"
    duplicate["packet"]["unit_id"] = duplicate["unit_id"]
    duplicate["packet"]["review_id"] = duplicate["review_id"]
    duplicate["packet"]["materials"][0]["material_id"] = (
        "unit-cand-grant-second:frozen-unit"
    )
    duplicate["packet"]["materials"][1]["material_id"] = (
        "unit-cand-grant-second:first-written-disposition"
    )

    metrics = case_grouped_label_audit_packet_metrics(
        (
            next(row for row in queue if row["candidate_id"] == "cand-grant"),
            duplicate,
        )
    )

    assert metrics["source_disposition_count"] == 2
    assert metrics["rendered_disposition_count"] == 1
    assert metrics["packet_byte_reduction"] > 0


def test_plan_label_audit_cli_writes_frozen_plan_and_blind_queue(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = "cand-grant"
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    _write_jsonl(inputs / "audit.jsonl", [_audit(candidate, "fully_dismissed", True)])
    _write_jsonl(inputs / "selection.jsonl", [_selection(candidate)])
    _write_jsonl(inputs / "units.jsonl", [_units(candidate)])
    _write_jsonl(
        inputs / "decisions.jsonl",
        [{"document_id": f"decision-{candidate}", "text": "The order resolves it."}],
    )
    (inputs / "policy.json").write_text(
        json.dumps(_policy(), sort_keys=True), encoding="utf-8"
    )
    _write_jsonl(inputs / "queue.jsonl", [])
    monkeypatch.setattr(cli, "require_finalized_envelopes", lambda records: records)

    class _Artifact:
        records = (
            {
                "candidate_id": candidate,
                "document_id": f"decision-{candidate}",
                "text": "The order resolves it.",
            },
        )

        def verify_stage_b_audit_commitments(self, records: object) -> None:
            del records

    monkeypatch.setattr(
        cli,
        "_verify_decision_text_artifact_with_materialization",
        lambda **kwargs: _Artifact(),
    )
    output = tmp_path / "output"

    assert (
        main(
            [
                "acquisition",
                "plan-label-audit",
                "--output-root",
                str(output),
                "--llm-label-audit",
                str(inputs / "audit.jsonl"),
                "--selection",
                str(inputs / "selection.jsonl"),
                "--prediction-units",
                str(inputs / "units.jsonl"),
                "--parser-manifest",
                str(inputs / "selection.jsonl"),
                "--decision-texts",
                str(inputs / "decisions.jsonl"),
                "--decision-texts-manifest",
                str(inputs / "policy.json"),
                "--decision-texts-run-card",
                str(inputs / "policy.json"),
                "--markdown-root",
                str(inputs),
                "--labeling-policy",
                str(inputs / "policy.json"),
                "--lawyer-review-queue",
                str(inputs / "queue.jsonl"),
                "--execute",
            ]
        )
        == 0
    )
    plan = json.loads((output / "cycle-label-audit-plan.json").read_text())
    assert plan["sample_count"] == 1
    queue = _read_jsonl(output / "lawyer-review-queue-cycle-planned.jsonl")
    assert queue[0]["route_reason"] == "label_audit_sample"
    assert "ensemble" not in queue[0]["packet"]
    packet_path = output / "case-grouped-label-audit-packet.json"
    packet_bytes = packet_path.read_bytes()
    grouped_packet = json.loads(
        packet_bytes.decode("utf-8"),
        parse_constant=lambda value: (_ for _ in ()).throw(
            ValueError(f"non-finite JSON value {value} is not supported")
        ),
    )
    assert packet_bytes == (
        json.dumps(grouped_packet, indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode("utf-8")
    assert grouped_packet["schema_version"].endswith(".v1")
    assert (
        grouped_packet["cases"][0]["review_items"][0]["review_id"]
        == queue[0]["review_id"]
    )
    summary = json.loads((output / "cycle-label-audit-summary.json").read_text())
    assert summary["plan_sha256"] == plan["plan_sha256"]
    assert summary["redacted"] is True
    assert "sampled_units" not in summary
    routing = json.loads((output / "adjudication-routing-summary.json").read_text())
    assert routing["counts_by_reason"] == {"label_audit_sample": 1}
    assert routing["total_routed_count"] == 1


def _candidates() -> tuple[str, ...]:
    return ("cand-grant", "cand-deny", "cand-partial")


def _fixture_plan(
    policy: dict[str, object],
) -> tuple[
    dict[str, object], tuple[dict[str, object], ...], tuple[dict[str, object], ...]
]:
    candidates = _candidates()
    return plan_cycle_label_audit(
        label_audit_records=[
            _audit("cand-grant", "fully_dismissed", True),
            _audit("cand-deny", "survives_in_material_respect", False),
            _audit("cand-partial", "partial_dismissal_only", False),
        ],
        selection_records=[_selection(candidate) for candidate in candidates],
        finalized_prediction_unit_records=[
            _units(candidate) for candidate in candidates
        ],
        decision_text_records=[
            {"document_id": f"decision-{candidate}", "text": "The order resolves it."}
            for candidate in candidates
        ],
        policy_record=policy,
    )


def _policy() -> dict[str, object]:
    return generate_labeling_policy(
        cycle_id="cycle-1",
        judge_registry_path=JUDGE_REGISTRY,
        published_at=datetime(2026, 7, 13, tzinfo=UTC),
        threshold_source="Cycle 1 labeling protocol fixture.",
    )


def _audit(candidate: str, resolution: str, dismissed: bool) -> dict[str, object]:
    label = _label(candidate, resolution, dismissed)
    votes = [
        {
            "model_id": model,
            "unit_id": f"unit-{candidate}",
            "confidence": 0.95,
            "rationale": "fixture",
            "raw_response_id": f"response-{model}",
            "label": label,
            "signature": [],
        }
        for model in ("a", "b", "c")
    ]
    return {
        "stage": "llm-label",
        "status": "succeeded",
        "candidate_id": candidate,
        "case_id": f"case-{candidate}",
        "ensemble": {
            "high_confidence_threshold": 0.85,
            "required_model_count": 3,
            "decisions": [
                {
                    "unit_id": f"unit-{candidate}",
                    "status": "auto_label",
                    "route_reason": "unanimous_high_confidence",
                    "unanimous_label": label,
                    "votes": votes,
                }
            ],
        },
    }


def _label(candidate: str, resolution: str, dismissed: bool) -> dict[str, object]:
    return {
        "unit_id": f"unit-{candidate}",
        "unit_resolution": resolution,
        "fully_dismissed": dismissed,
        "primary_outcome": int(dismissed),
        "amendment_class": (
            "dismissed_without_express_amendment_opportunity"
            if dismissed
            else "not_fully_dismissed"
        ),
        "conditional_amendment_target": False if dismissed else None,
        "ambiguous": False,
        "label_confidence": 0.95,
        "supporting_citations": [
            {
                "document_id": f"decision-{candidate}",
                "excerpt": "The order resolves it.",
            }
        ],
        "first_written_disposition_id": f"decision-{candidate}",
        "first_written_disposition_date": "2026-07-01",
        "first_written_disposition_locked": True,
        "later_procedural_changes": [],
        "notes": None,
    }


def _selection(candidate: str) -> dict[str, object]:
    return {
        "candidate_id": candidate,
        "decision_entry_numbers": [10],
        "documents": [
            {
                "source_document_id": f"decision-{candidate}",
                "document_role": "decision",
                "docket_entry_number": 10,
                "contains_target_outcome": True,
            }
        ],
    }


def _units(candidate: str) -> dict[str, object]:
    return {
        "candidate_id": candidate,
        "status": "finalized",
        "prediction_units": [{"unit_id": f"unit-{candidate}", "claim_name": "Count I"}],
    }


def _adjudication(sample: dict[str, object], *, matching: bool) -> dict[str, object]:
    candidate = str(sample["candidate_id"])
    stratum = str(sample["stratum"])
    dismissed = stratum == "unanimous_grant"
    resolution = {
        "unanimous_grant": "fully_dismissed",
        "unanimous_deny": "survives_in_material_respect",
        "partial": "partial_dismissal_only",
    }[stratum]
    if not matching:
        dismissed = not dismissed
        resolution = "fully_dismissed" if dismissed else "survives_in_material_respect"
    label = _label(candidate, resolution, dismissed)
    responses = [
        {
            "review_id": sample["review_id"],
            "proposed_label": label,
            "reviewer_id": f"lawyer-{index}",
            "reviewer_expertise": "senior_litigator",
            "confidence": 0.9,
            "minutes_spent": 10.0,
            "notes": "Fixture review.",
        }
        for index in (1, 2)
    ]
    return {
        "review_id": sample["review_id"],
        "candidate_id": candidate,
        "unit_id": sample["unit_id"],
        "adjudicated_label": label,
        "adjudicator_id": "senior-adjudicator",
        "adjudication_notes": "Fixture adjudication.",
        "reviewer_responses": responses,
    }


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]
