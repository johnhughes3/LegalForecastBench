from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from typing import Any

import pytest
from legalforecast.ingestion.canonical_json import canonical_json_bytes
from legalforecast.ingestion.exact100_successor_replacement import (
    RESULT_SCHEMA_VERSION,
    Exact100SuccessorReplacementError,
    VerifiedExact100TerminalAuthority,
    issue_verified_terminal_authority_for_testing,
    project_exact100_successor_replacement,
    verify_exact100_successor_replacement_result,
)


def _jsonl(rows: Sequence[Mapping[str, object]]) -> bytes:
    return b"".join(
        canonical_json_bytes(
            row,
            error_type=ValueError,
            error_message="test serialization failed",
        )
        for row in rows
    )


def _fixture() -> dict[str, Any]:
    selected = [
        {"candidate_id": f"C{number:03d}", "case_name": f"Case {number:03d}"}
        for number in range(1, 101)
    ]
    reserves = [
        {"candidate_id": f"R{number}", "case_name": f"Reserve {number}"}
        for number in range(1, 5)
    ]
    source_rows = [*selected, *reserves]
    selected_rows = deepcopy(selected)
    ranked_reserves = [
        {"candidate_id": reserve["candidate_id"], "reserve_rank": rank}
        for rank, reserve in enumerate(reserves, start=1)
    ]
    terminal_rows = [
        {"candidate_id": "C002", "reason": "terminal"},
        {"candidate_id": "C004", "reason": "terminal"},
    ]
    source_rows_bytes = _jsonl(source_rows)
    selected_rows_bytes = _jsonl(selected_rows)
    ranked_reserve_rows_bytes = _jsonl(ranked_reserves)
    terminal_exclusions_bytes = _jsonl(terminal_rows)
    authority = issue_verified_terminal_authority_for_testing(
        source_rows_bytes=source_rows_bytes,
        selected_rows_bytes=selected_rows_bytes,
        ranked_reserve_rows_bytes=ranked_reserve_rows_bytes,
        terminal_exclusions_bytes=terminal_exclusions_bytes,
    )
    return {
        "source_rows": source_rows,
        "selected_rows": selected_rows,
        "ranked_reserves": ranked_reserves,
        "terminal_rows": terminal_rows,
        "source_rows_bytes": source_rows_bytes,
        "selected_rows_bytes": selected_rows_bytes,
        "ranked_reserve_rows_bytes": ranked_reserve_rows_bytes,
        "terminal_exclusions_bytes": terminal_exclusions_bytes,
        "authority": authority,
    }


def _project(inputs: dict[str, Any]):
    return project_exact100_successor_replacement(
        terminal_authority=inputs["authority"],
        source_rows_bytes=inputs["source_rows_bytes"],
        selected_rows_bytes=inputs["selected_rows_bytes"],
        ranked_reserve_rows_bytes=inputs["ranked_reserve_rows_bytes"],
    )


def test_projection_derives_terminal_count_and_promotes_first_ranked_reserves() -> None:
    result = _project(_fixture())

    assert result.result["schema_version"] == RESULT_SCHEMA_VERSION
    assert result.result["terminal_exclusion_count"] == 2
    assert result.result["promoted_candidate_ids"] == ["R1", "R2"]
    assert [row["candidate_id"] for row in result.promoted_reserves] == ["R1", "R2"]
    successor_ids = [row["candidate_id"] for row in result.successor_selection]
    assert len(successor_ids) == 100
    assert "C002" not in successor_ids
    assert "C004" not in successor_ids
    assert successor_ids[-2:] == ["R1", "R2"]
    verify_exact100_successor_replacement_result(result.result)

    for flag in (
        "provider_activity_requested",
        "provider_activity_executed",
        "provider_activity_permitted",
        "paid_activity_requested",
        "paid_activity_executed",
        "paid_activity_permitted",
        "evaluation_authorized",
        "freeze_authorized",
        "dispatch_authorized",
    ):
        assert result.result[flag] is False


def test_projection_rejects_source_row_mutation_after_authority_issuance() -> None:
    inputs = _fixture()
    source_rows = deepcopy(inputs["source_rows"])
    source_rows[0]["case_name"] = "Mutated source row"
    inputs["source_rows_bytes"] = _jsonl(source_rows)

    with pytest.raises(
        Exact100SuccessorReplacementError,
        match="source rows differ from verified terminal authority",
    ):
        _project(inputs)


def test_projection_accepts_an_authenticated_empty_terminal_set() -> None:
    inputs = _fixture()
    inputs["terminal_exclusions_bytes"] = b""
    inputs["authority"] = issue_verified_terminal_authority_for_testing(
        source_rows_bytes=inputs["source_rows_bytes"],
        selected_rows_bytes=inputs["selected_rows_bytes"],
        ranked_reserve_rows_bytes=inputs["ranked_reserve_rows_bytes"],
        terminal_exclusions_bytes=b"",
    )

    result = _project(inputs)

    assert result.result["terminal_exclusion_count"] == 0
    assert result.result["promoted_candidate_ids"] == []
    assert result.successor_selection_bytes == inputs["selected_rows_bytes"]


def _append_duplicate_terminal(inputs: dict[str, Any]) -> None:
    inputs["terminal_rows"].append({"candidate_id": "C002", "reason": "duplicate"})


def _append_unselected_terminal(inputs: dict[str, Any]) -> None:
    inputs["terminal_rows"].append({"candidate_id": "R1", "reason": "unselected"})


def _skip_reserve_rank(inputs: dict[str, Any]) -> None:
    inputs["ranked_reserves"][1] = {"candidate_id": "R2", "reserve_rank": 3}


def _append_duplicate_reserve(inputs: dict[str, Any]) -> None:
    inputs["ranked_reserves"].append({"candidate_id": "R1", "reserve_rank": 5})


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (
            _append_duplicate_terminal,
            "terminal exclusions contain duplicate candidates",
        ),
        (
            _append_unselected_terminal,
            "terminal exclusion is not selected",
        ),
        (
            _skip_reserve_rank,
            "skipped or duplicate reserve ranks",
        ),
        (
            _append_duplicate_reserve,
            "ranked reserve rows contain duplicate candidates",
        ),
    ],
)
def test_test_authority_issuer_rejects_invalid_terminal_or_ranking_contract(
    change: Callable[[dict[str, Any]], None], message: str
) -> None:
    inputs = _fixture()
    change(inputs)

    with pytest.raises(Exact100SuccessorReplacementError, match=message):
        issue_verified_terminal_authority_for_testing(
            source_rows_bytes=inputs["source_rows_bytes"],
            selected_rows_bytes=inputs["selected_rows_bytes"],
            ranked_reserve_rows_bytes=_jsonl(inputs["ranked_reserves"]),
            terminal_exclusions_bytes=_jsonl(inputs["terminal_rows"]),
        )


def test_test_authority_issuer_rejects_exact_count_and_source_uniqueness_errors() -> (
    None
):
    inputs = _fixture()
    selected_rows = deepcopy(inputs["selected_rows"])
    selected_rows.pop()
    with pytest.raises(Exact100SuccessorReplacementError, match="exactly 100"):
        issue_verified_terminal_authority_for_testing(
            source_rows_bytes=inputs["source_rows_bytes"],
            selected_rows_bytes=_jsonl(selected_rows),
            ranked_reserve_rows_bytes=inputs["ranked_reserve_rows_bytes"],
            terminal_exclusions_bytes=inputs["terminal_exclusions_bytes"],
        )

    source_rows = deepcopy(inputs["source_rows"])
    source_rows.append(deepcopy(source_rows[0]))
    with pytest.raises(Exact100SuccessorReplacementError, match="duplicate candidates"):
        issue_verified_terminal_authority_for_testing(
            source_rows_bytes=_jsonl(source_rows),
            selected_rows_bytes=inputs["selected_rows_bytes"],
            ranked_reserve_rows_bytes=inputs["ranked_reserve_rows_bytes"],
            terminal_exclusions_bytes=inputs["terminal_exclusions_bytes"],
        )


def test_authority_is_opaque_and_result_digest_is_fail_closed() -> None:
    with pytest.raises(TypeError, match="issued only"):
        VerifiedExact100TerminalAuthority()

    result = _project(_fixture())
    tampered = dict(result.result)
    tampered["dispatch_authorized"] = True
    with pytest.raises(
        Exact100SuccessorReplacementError, match="grants unavailable authority"
    ):
        verify_exact100_successor_replacement_result(tampered)
