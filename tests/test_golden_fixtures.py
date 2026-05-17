from __future__ import annotations

import json

import pytest
from legalforecast.testing import (
    REQUIRED_PIPELINE_LOG_FIELDS,
    FixtureEdgeCase,
    get_golden_case,
    golden_case_ids,
    iter_golden_cases,
    pipeline_log_context,
)


def test_golden_corpus_covers_required_edge_cases() -> None:
    covered = {case.edge_case for case in iter_golden_cases()}

    assert covered == set(FixtureEdgeCase)


def test_golden_cases_have_stable_unique_hashes() -> None:
    hashes = {case.source_hash for case in iter_golden_cases()}

    assert len(hashes) == len(golden_case_ids())
    assert all(source_hash.startswith("sha256:") for source_hash in hashes)


def test_golden_case_records_are_json_serializable() -> None:
    record = get_golden_case("fixture_mixed_disposition").to_record()

    encoded = json.dumps(record, sort_keys=True)
    assert "fixture_mixed_disposition" in encoded
    assert record["edge_case"] == FixtureEdgeCase.MIXED_DISPOSITION.value


def test_pipeline_log_context_contains_all_required_fields() -> None:
    case = get_golden_case("fixture_false_positive_dismissal")

    context = pipeline_log_context(
        case,
        stage="eligibility",
        decision="exclude",
        exclusion_reason=case.expected_exclusion_reason,
        elapsed_ms=17,
        request_count=2,
        estimated_cost=0.03,
    )

    assert set(REQUIRED_PIPELINE_LOG_FIELDS) <= context.keys()
    assert context["case_id"] == "fixture_false_positive_dismissal"
    assert context["candidate_id"] == "cand_fixture_false_positive_dismissal"
    assert context["decision"] == "exclude"
    assert context["exclusion_reason"] == "not_motion_to_dismiss"
    assert context["elapsed_ms"] == 17
    assert context["request_count"] == 2
    assert context["estimated_cost"] == 0.03


def test_pipeline_log_context_rejects_negative_accounting_values() -> None:
    case = get_golden_case("fixture_clean_grant")

    with pytest.raises(ValueError, match="estimated_cost"):
        pipeline_log_context(
            case,
            stage="model_execution",
            decision="predict",
            estimated_cost=-0.01,
        )


def test_false_positive_fixture_is_not_a_motion_to_dismiss_candidate() -> None:
    case = get_golden_case("fixture_false_positive_dismissal")

    assert "dismissal" in case.docket_entries[0].text.lower()
    assert case.expected_exclusion_reason == "not_motion_to_dismiss"


def test_malformed_model_fixture_preserves_invalid_output() -> None:
    case = get_golden_case("fixture_malformed_model_output")

    assert case.malformed_model_output is not None
    with pytest.raises(json.JSONDecodeError):
        json.loads(case.malformed_model_output)
