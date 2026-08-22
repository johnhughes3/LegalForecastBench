# pyright: reportPrivateUsage=false
# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownMemberType=false
# pyright: reportUnusedVariable=false
# pyright: reportUnknownVariableType=false

from __future__ import annotations

import hashlib
from typing import Any

import pytest
from legalforecast.ingestion.canonical_json import canonical_json_bytes
from legalforecast.ingestion.exact100_successor_replacement import (
    CONFIG_SCHEMA_VERSION,
    PREDECESSOR_COVERAGE_SCHEMA_V1,
    PREDECESSOR_COVERAGE_SCHEMA_V2,
    STATE_SCHEMA_VERSION,
    Exact100SuccessorReplacementError,
    VerifiedExact100Predecessor,
    VerifiedSuccessorPromotionPool,
    _mint_verified_exact100_predecessor,
    _mint_verified_successor_promotion_pool,
    project_exact100_successor_replacement,
    require_verified_exact100_predecessor,
    require_verified_successor_promotion_pool,
    verify_exact100_predecessor,
    verify_successor_promotion_pool,
)
from legalforecast.ingestion.mistral_markdown_parser import EXPECTED_PARSER_REVISION
from legalforecast.ingestion.post_selection_terminal_exclusion import (
    _verify_stipulated_target_evidence_for_test,
    verify_post_selection_terminal_exclusions,
)


def _bytes(value: object) -> bytes:
    return canonical_json_bytes(
        value, error_type=ValueError, error_message="test serialization failed"
    )


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _selection_row(candidate_id: str) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "case_id": candidate_id,
        "identity_resolution": {"courtlistener_docket_id": f"docket-{candidate_id}"},
        "documents": [
            {
                "source_document_id": f"{candidate_id}-motion",
                "document_role": "motion_to_dismiss_memorandum",
                "courtlistener_docket_entry_id": f"entry-{candidate_id}",
            }
        ],
    }


def _jsonl(records: list[dict[str, Any]]) -> bytes:
    return b"".join(_bytes(record) for record in records)


def _candidate_artifacts(
    candidate_ids: list[str], *, incomplete: set[str] | None = None
) -> dict[str, list[dict[str, Any]]]:
    incomplete = incomplete or set()
    relevance: list[dict[str, Any]] = []
    manifest: list[dict[str, Any]] = []
    clearance: list[dict[str, Any]] = []
    restrictions: list[dict[str, Any]] = []
    core: list[dict[str, Any]] = []
    for candidate_id in candidate_ids:
        document_id = f"{candidate_id}-motion"
        relevance.append(
            {
                "candidate_id": candidate_id,
                "documents": [{"source_document_id": document_id}],
            }
        )
        manifest.append(
            {
                "candidate_id": candidate_id,
                "source_document_id": document_id,
                "sha256": hashlib.sha256(b"authenticated PDF source").hexdigest(),
                "byte_count": len(b"authenticated PDF source"),
                "availability_status": "available",
                "requires_paid_recovery": False,
                "free_or_purchased": "free",
            }
        )
        clearance.append(
            {
                "candidate_id": candidate_id,
                "source_document_id": document_id,
                "status": "cleared",
            }
        )
        restrictions.append(
            {
                "candidate_id": candidate_id,
                "source_document_id": document_id,
                "restriction_status": "public",
                "restriction_markers": [],
            }
        )
        core.append(
            {
                "candidate_id": candidate_id,
                "missing_core_document_count": (1 if candidate_id in incomplete else 0),
                "core_documents_complete": candidate_id not in incomplete,
            }
        )
    return {
        "case_relevance": relevance,
        "download_manifest": manifest,
        "disclosure_clearance": clearance,
        "restriction_evidence": restrictions,
        "core_filter_results": core,
    }


def _fixture() -> dict[str, Any]:
    selected_ids = [f"C{number:03d}" for number in range(1, 101)]
    selection = [_selection_row(candidate_id) for candidate_id in selected_ids]
    selection_bytes = b"".join(_bytes(record) for record in selection)
    predecessor_artifacts = _candidate_artifacts(selected_ids)
    stipulated_source_document = b"authenticated PDF source"
    for candidate_id in ("C001", "C002"):
        manifest = next(
            row
            for row in predecessor_artifacts["download_manifest"]
            if row["candidate_id"] == candidate_id
        )
        manifest.update(
            {
                "sha256": _sha(stipulated_source_document),
                "byte_count": len(stipulated_source_document),
            }
        )
    predecessor_output_bytes = {
        "target-cohort-selection.jsonl": selection_bytes,
        "case-relevance.jsonl": _jsonl(predecessor_artifacts["case_relevance"]),
        "document-downloads-merged.jsonl": _jsonl(
            predecessor_artifacts["download_manifest"]
        ),
        "free-document-downloads.jsonl": b"",
        "purchased-document-downloads.jsonl": b"",
        "disclosure-clearance.jsonl": _jsonl(
            predecessor_artifacts["disclosure_clearance"]
        ),
        "restriction-evidence.jsonl": _jsonl(
            predecessor_artifacts["restriction_evidence"]
        ),
        "core-filter-results.jsonl": _jsonl(
            predecessor_artifacts["core_filter_results"]
        ),
        "missing-core-budget-plan.json": _bytes({"status": "not-needed"}),
        "target-cohort-exclusions.jsonl": b"",
        "target-cohort-ranked-reserve.jsonl": b"",
    }
    projection = {
        "schema_version": "legalforecast.zero_cost_successor_config.v1",
        "target_case_count": 100,
        "output_commitments": {
            name: _sha(payload) for name, payload in predecessor_output_bytes.items()
        },
        "provider_activity_permitted": False,
        "paid_activity_permitted": False,
        "evaluation_authorized": False,
        "freeze_authorized": False,
        "dispatch_authorized": False,
    }
    evidence = []
    for candidate_id in ("C001", "C002"):
        document_id = f"{candidate_id}-motion"
        markdown = b"# [PROPOSED] STIPULATION FOR AND ORDER OF DISMISSAL\n"
        source_document = stipulated_source_document
        parser_request = {
            "candidate_id": candidate_id,
            "source_document_id": document_id,
            "input_path": f"/authenticated/{candidate_id}/{document_id}.pdf",
            "expected_sha256": _sha(source_document),
            "expected_byte_count": len(source_document),
            "markdown_output_path": f"/authenticated/{candidate_id}/{document_id}.md",
        }
        parser_requests_bytes = _bytes(parser_request)
        parser_record = {
            "candidate_id": candidate_id,
            "source_document_id": document_id,
            "status": "succeeded",
            "input_path": parser_request["input_path"],
            "markdown_path": parser_request["markdown_output_path"],
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
        evidence.append(
            _verify_stipulated_target_evidence_for_test(
                selection_bytes=selection_bytes,
                authenticated_download_manifest_bytes=predecessor_output_bytes[
                    "document-downloads-merged.jsonl"
                ],
                candidate_id=candidate_id,
                source_document_id=document_id,
                parser_record=parser_record,
                parser_requests_bytes=parser_requests_bytes,
                parser_manifest_bytes=parser_manifest_bytes,
                parser_run_card_bytes=_bytes(parser_run_card),
                markdown_bytes=markdown,
                source_document_bytes=source_document,
            )
        )
    terminals = verify_post_selection_terminal_exclusions(
        selection_bytes=selection_bytes, evidence=evidence
    )

    reserve_ids = ["R1", "R2", "R3"]
    reserve_selection = [_selection_row(candidate_id) for candidate_id in reserve_ids]
    reserve_artifacts = _candidate_artifacts(reserve_ids, incomplete={"R1"})
    reserve = [
        {
            "candidate_id": candidate_id,
            "reserve_rank": rank,
            "ranking_key": [rank, "0.00", candidate_id],
        }
        for rank, candidate_id in enumerate(reserve_ids, start=1)
    ]
    predecessor = _mint_verified_exact100_predecessor(
        projection=projection,
        projection_bytes=_bytes(projection),
        selection_bytes=selection_bytes,
        case_relevance_bytes=predecessor_output_bytes["case-relevance.jsonl"],
        download_manifest_bytes=predecessor_output_bytes[
            "document-downloads-merged.jsonl"
        ],
        disclosure_clearance_bytes=predecessor_output_bytes[
            "disclosure-clearance.jsonl"
        ],
        restriction_evidence_bytes=predecessor_output_bytes[
            "restriction-evidence.jsonl"
        ],
        core_filter_results_bytes=predecessor_output_bytes["core-filter-results.jsonl"],
        all_output_bytes=predecessor_output_bytes,
    )
    promotion_pool = _mint_verified_successor_promotion_pool(
        ranked_reserve_bytes=_jsonl(reserve),
        source_selection_bytes=_jsonl(reserve_selection),
        case_relevance_bytes=_jsonl(reserve_artifacts["case_relevance"]),
        download_manifest_bytes=_jsonl(reserve_artifacts["download_manifest"]),
        disclosure_clearance_bytes=_jsonl(reserve_artifacts["disclosure_clearance"]),
        restriction_evidence_bytes=_jsonl(reserve_artifacts["restriction_evidence"]),
        core_filter_results_bytes=_jsonl(reserve_artifacts["core_filter_results"]),
        producer_config_bytes=b"test-only authenticated producer config",
        producer_run_card_bytes=b"test-only authenticated producer run card",
        producer_root_bytes=b"test-only authenticated producer root",
    )
    return {
        "selection": selection,
        "selection_bytes": selection_bytes,
        "predecessor_artifacts": predecessor_artifacts,
        "predecessor_output_bytes": predecessor_output_bytes,
        "terminals": terminals,
        "reserve": reserve,
        "reserve_selection": reserve_selection,
        "reserve_artifacts": reserve_artifacts,
        "predecessor": predecessor,
        "promotion_pool": promotion_pool,
    }


def test_replacement_preserves_rows_and_promotes_first_clean_reserves() -> None:
    inputs = _fixture()

    result = project_exact100_successor_replacement(
        predecessor=inputs["predecessor"],
        terminal_exclusions=inputs["terminals"],
        promotion_pool=inputs["promotion_pool"],
    )

    assert len(result.selection) == 100
    assert [row["candidate_id"] for row in result.selection[-2:]] == ["R2", "R3"]
    assert [row["candidate_id"] for row in result.selection[:2]] == ["C003", "C004"]
    assert result.selection[:-2] == tuple(inputs["selection"][2:])
    assert [row["reserve_rank"] for row in result.promotions] == [2, 3]
    assert inputs["promotion_pool"].nonpromotable == (
        {
            "candidate_id": "R1",
            "reserve_rank": 1,
            "reason": "core_documents_incomplete",
        },
    )
    assert result.config["schema_version"] == CONFIG_SCHEMA_VERSION
    assert result.state["schema_version"] == STATE_SCHEMA_VERSION
    assert result.state["retained_case_count"] == 98
    assert result.state["terminal_candidate_ids"] == ["C001", "C002"]
    assert result.state["promoted_candidate_ids"] == ["R2", "R3"]
    assert result.config["provider_activity_permitted"] is False
    assert result.config["paid_activity_permitted"] is False
    assert result.state["provider_activity_executed"] is False
    assert result.state["evaluation_authorized"] is False
    assert result.state["freeze_authorized"] is False
    assert result.state["dispatch_authorized"] is False


def test_replacement_orders_promoted_artifacts_by_frozen_reserve_rank() -> None:
    inputs = _fixture()
    reserve_artifacts = {
        name: list(reversed(rows)) for name, rows in inputs["reserve_artifacts"].items()
    }
    pool = _mint_verified_successor_promotion_pool(
        ranked_reserve_bytes=_jsonl(inputs["reserve"]),
        source_selection_bytes=_jsonl(list(reversed(inputs["reserve_selection"]))),
        case_relevance_bytes=_jsonl(reserve_artifacts["case_relevance"]),
        download_manifest_bytes=_jsonl(reserve_artifacts["download_manifest"]),
        disclosure_clearance_bytes=_jsonl(reserve_artifacts["disclosure_clearance"]),
        restriction_evidence_bytes=_jsonl(reserve_artifacts["restriction_evidence"]),
        core_filter_results_bytes=_jsonl(reserve_artifacts["core_filter_results"]),
        producer_config_bytes=b"test-only authenticated producer config",
        producer_run_card_bytes=b"test-only authenticated producer run card",
        producer_root_bytes=b"test-only authenticated producer root",
    )

    result = project_exact100_successor_replacement(
        predecessor=inputs["predecessor"],
        terminal_exclusions=inputs["terminals"],
        promotion_pool=pool,
    )

    assert [row["candidate_id"] for row in result.selection[-2:]] == ["R2", "R3"]
    for artifact in (
        result.case_relevance,
        result.download_manifest,
        result.disclosure_clearance,
        result.restriction_evidence,
        result.core_filter_results,
    ):
        assert [row["candidate_id"] for row in artifact[-2:]] == ["R2", "R3"]


def test_replacement_fails_closed_when_clean_reserves_are_insufficient() -> None:
    inputs = _fixture()
    pool = inputs["promotion_pool"]
    object.__setattr__(
        pool, "core_filter_results", tuple(pool.core_filter_results[:-1])
    )

    with pytest.raises(Exact100SuccessorReplacementError, match="eligibility changed"):
        project_exact100_successor_replacement(
            predecessor=inputs["predecessor"],
            terminal_exclusions=inputs["terminals"],
            promotion_pool=pool,
        )


@pytest.mark.parametrize(
    ("artifact_name", "expected_reason"),
    [
        ("download_manifest", "download_manifest_incomplete"),
        ("disclosure_clearance", "disclosure_clearance_incomplete"),
        ("restriction_evidence", "restriction_evidence_incomplete"),
    ],
)
def test_promotion_pool_rejects_duplicate_document_artifact_rows(
    artifact_name: str, expected_reason: str
) -> None:
    inputs = _fixture()
    artifacts = {name: list(rows) for name, rows in inputs["reserve_artifacts"].items()}
    duplicate = next(
        row for row in artifacts[artifact_name] if row["candidate_id"] == "R2"
    )
    artifacts[artifact_name].append(dict(duplicate))

    pool = _mint_verified_successor_promotion_pool(
        ranked_reserve_bytes=_jsonl(inputs["reserve"]),
        source_selection_bytes=_jsonl(inputs["reserve_selection"]),
        case_relevance_bytes=_jsonl(artifacts["case_relevance"]),
        download_manifest_bytes=_jsonl(artifacts["download_manifest"]),
        disclosure_clearance_bytes=_jsonl(artifacts["disclosure_clearance"]),
        restriction_evidence_bytes=_jsonl(artifacts["restriction_evidence"]),
        core_filter_results_bytes=_jsonl(artifacts["core_filter_results"]),
        producer_config_bytes=b"test-only producer config",
        producer_run_card_bytes=b"test-only producer run card",
        producer_root_bytes=b"test-only producer root",
    )

    assert "R2" not in pool.promotable_candidate_ids
    assert {
        "candidate_id": "R2",
        "reserve_rank": 2,
        "reason": expected_reason,
    } in pool.nonpromotable


@pytest.mark.parametrize(
    ("artifact_name", "field_name", "expected_reason"),
    [
        (
            "download_manifest",
            "availability_status",
            "nonzero_cost_or_unavailable_document",
        ),
        ("core_filter_results", "core_documents_complete", "core_documents_incomplete"),
    ],
)
def test_promotion_pool_requires_explicit_availability_and_core_completion(
    artifact_name: str, field_name: str, expected_reason: str
) -> None:
    inputs = _fixture()
    artifacts = {name: list(rows) for name, rows in inputs["reserve_artifacts"].items()}
    row = next(row for row in artifacts[artifact_name] if row["candidate_id"] == "R2")
    if field_name == "availability_status":
        row[field_name] = "unavailable"
    else:
        row.pop(field_name)

    pool = _mint_verified_successor_promotion_pool(
        ranked_reserve_bytes=_jsonl(inputs["reserve"]),
        source_selection_bytes=_jsonl(inputs["reserve_selection"]),
        case_relevance_bytes=_jsonl(artifacts["case_relevance"]),
        download_manifest_bytes=_jsonl(artifacts["download_manifest"]),
        disclosure_clearance_bytes=_jsonl(artifacts["disclosure_clearance"]),
        restriction_evidence_bytes=_jsonl(artifacts["restriction_evidence"]),
        core_filter_results_bytes=_jsonl(artifacts["core_filter_results"]),
        producer_config_bytes=b"test-only producer config",
        producer_run_card_bytes=b"test-only producer run card",
        producer_root_bytes=b"test-only producer root",
    )

    assert "R2" not in pool.promotable_candidate_ids
    assert {
        "candidate_id": "R2",
        "reserve_rank": 2,
        "reason": expected_reason,
    } in pool.nonpromotable


def test_promotion_pool_requires_relevance_documents_to_match_selection() -> None:
    inputs = _fixture()
    artifacts = {name: list(rows) for name, rows in inputs["reserve_artifacts"].items()}
    relevance = next(
        row for row in artifacts["case_relevance"] if row["candidate_id"] == "R2"
    )
    relevance["documents"] = [
        {
            **relevance["documents"][0],
            "source_document_id": "R2-unselected-document",
        }
    ]

    pool = _mint_verified_successor_promotion_pool(
        ranked_reserve_bytes=_jsonl(inputs["reserve"]),
        source_selection_bytes=_jsonl(inputs["reserve_selection"]),
        case_relevance_bytes=_jsonl(artifacts["case_relevance"]),
        download_manifest_bytes=_jsonl(artifacts["download_manifest"]),
        disclosure_clearance_bytes=_jsonl(artifacts["disclosure_clearance"]),
        restriction_evidence_bytes=_jsonl(artifacts["restriction_evidence"]),
        core_filter_results_bytes=_jsonl(artifacts["core_filter_results"]),
        producer_config_bytes=b"test-only producer config",
        producer_run_card_bytes=b"test-only producer run card",
        producer_root_bytes=b"test-only producer root",
    )

    assert "R2" not in pool.promotable_candidate_ids
    assert {
        "candidate_id": "R2",
        "reserve_rank": 2,
        "reason": "case_relevance_incomplete",
    } in pool.nonpromotable


def test_promotion_pool_missing_selected_candidate_is_a_domain_error() -> None:
    inputs = _fixture()
    inputs["promotion_pool"].selection_by_candidate.pop("R2")

    with pytest.raises(
        Exact100SuccessorReplacementError,
        match="absent from authenticated source selection",
    ):
        project_exact100_successor_replacement(
            predecessor=inputs["predecessor"],
            terminal_exclusions=inputs["terminals"],
            promotion_pool=inputs["promotion_pool"],
        )


@pytest.mark.parametrize(
    "coverage_failure", ["missing_candidate", "duplicate_document"]
)
def test_predecessor_mint_requires_exact_selected_artifact_coverage(
    coverage_failure: str,
) -> None:
    inputs = _fixture()
    artifacts = {
        name: list(rows) for name, rows in inputs["predecessor_artifacts"].items()
    }
    if coverage_failure == "missing_candidate":
        artifacts["case_relevance"] = [
            row for row in artifacts["case_relevance"] if row["candidate_id"] != "C003"
        ]
        error = "case relevance does not exactly cover selected candidates"
    else:
        duplicate = next(
            row
            for row in artifacts["download_manifest"]
            if row["candidate_id"] == "C003"
        )
        artifacts["download_manifest"].append(dict(duplicate))
        error = "download manifest document coverage is incomplete"
    output_bytes = dict(inputs["predecessor_output_bytes"])
    output_bytes["case-relevance.jsonl"] = _jsonl(artifacts["case_relevance"])
    output_bytes["document-downloads-merged.jsonl"] = _jsonl(
        artifacts["download_manifest"]
    )
    projection = dict(inputs["predecessor"].projection)
    projection["output_commitments"] = {
        name: _sha(payload) for name, payload in output_bytes.items()
    }

    with pytest.raises(Exact100SuccessorReplacementError, match=error):
        _mint_verified_exact100_predecessor(
            projection=projection,
            projection_bytes=_bytes(projection),
            selection_bytes=inputs["selection_bytes"],
            case_relevance_bytes=output_bytes["case-relevance.jsonl"],
            download_manifest_bytes=output_bytes["document-downloads-merged.jsonl"],
            disclosure_clearance_bytes=output_bytes["disclosure-clearance.jsonl"],
            restriction_evidence_bytes=output_bytes["restriction-evidence.jsonl"],
            core_filter_results_bytes=output_bytes["core-filter-results.jsonl"],
            all_output_bytes=output_bytes,
        )


def _paid_recovery_gap_payload() -> dict[str, Any]:
    inputs = _fixture()
    selection = [_selection_row(f"C{number:03d}") for number in range(1, 101)]
    gap_id = "C003-unacquired"
    selection[2]["documents"].append(
        {
            "source_document_id": gap_id,
            "document_role": "motion_to_dismiss_memorandum",
            "courtlistener_docket_entry_id": "entry-C003-unacquired",
            "requires_paid_recovery": True,
            "availability_status": "unavailable",
        }
    )
    artifacts = {
        name: [dict(row) for row in rows]
        for name, rows in inputs["predecessor_artifacts"].items()
    }
    relevance = next(
        row for row in artifacts["case_relevance"] if row["candidate_id"] == "C003"
    )
    relevance["documents"] = [
        *list(relevance["documents"]),
        {"source_document_id": gap_id},
    ]
    selection_bytes = _jsonl(selection)
    output_bytes = dict(inputs["predecessor_output_bytes"])
    output_bytes["target-cohort-selection.jsonl"] = selection_bytes
    output_bytes["case-relevance.jsonl"] = _jsonl(artifacts["case_relevance"])
    projection = dict(inputs["predecessor"].projection)
    projection["output_commitments"] = {
        name: _sha(payload) for name, payload in output_bytes.items()
    }
    return {
        "projection": projection,
        "projection_bytes": _bytes(projection),
        "selection_bytes": selection_bytes,
        "output_bytes": output_bytes,
    }


def _mint_from_payload(
    payload: dict[str, Any], *, predecessor_coverage_schema: str
) -> VerifiedExact100Predecessor:
    output_bytes = payload["output_bytes"]
    return _mint_verified_exact100_predecessor(
        projection=payload["projection"],
        projection_bytes=payload["projection_bytes"],
        selection_bytes=payload["selection_bytes"],
        case_relevance_bytes=output_bytes["case-relevance.jsonl"],
        download_manifest_bytes=output_bytes["document-downloads-merged.jsonl"],
        disclosure_clearance_bytes=output_bytes["disclosure-clearance.jsonl"],
        restriction_evidence_bytes=output_bytes["restriction-evidence.jsonl"],
        core_filter_results_bytes=output_bytes["core-filter-results.jsonl"],
        all_output_bytes=output_bytes,
        predecessor_coverage_schema=predecessor_coverage_schema,
    )


def test_v1_predecessor_mint_rejects_paid_recovery_gaps() -> None:
    payload = _paid_recovery_gap_payload()

    with pytest.raises(
        Exact100SuccessorReplacementError,
        match="download manifest document coverage is incomplete",
    ):
        _mint_from_payload(
            payload, predecessor_coverage_schema=PREDECESSOR_COVERAGE_SCHEMA_V1
        )


def test_v2_predecessor_mint_accepts_authenticated_paid_recovery_gaps() -> None:
    payload = _paid_recovery_gap_payload()

    predecessor = _mint_from_payload(
        payload, predecessor_coverage_schema=PREDECESSOR_COVERAGE_SCHEMA_V2
    )

    assert any(
        document.get("source_document_id") == "C003-unacquired"
        for row in predecessor.selection
        if row["candidate_id"] == "C003"
        for document in row["documents"]
    )
    assert not any(
        row.get("source_document_id") == "C003-unacquired"
        for row in predecessor.download_manifest
    )


def test_v1_require_verified_rejects_v2_minted_paid_recovery_gaps() -> None:
    payload = _paid_recovery_gap_payload()
    predecessor = _mint_from_payload(
        payload, predecessor_coverage_schema=PREDECESSOR_COVERAGE_SCHEMA_V2
    )

    with pytest.raises(
        Exact100SuccessorReplacementError,
        match="download manifest document coverage is incomplete",
    ):
        require_verified_exact100_predecessor(predecessor)


def test_replacement_rejects_caller_constructed_authorities() -> None:
    with pytest.raises(Exact100SuccessorReplacementError, match="producer replay"):
        require_verified_exact100_predecessor(
            object.__new__(VerifiedExact100Predecessor)
        )
    with pytest.raises(Exact100SuccessorReplacementError, match="authenticated replay"):
        require_verified_successor_promotion_pool(
            object.__new__(VerifiedSuccessorPromotionPool)
        )
    with pytest.raises(Exact100SuccessorReplacementError, match="disabled"):
        verify_exact100_predecessor()
    with pytest.raises(Exact100SuccessorReplacementError, match="disabled"):
        verify_successor_promotion_pool()


def test_replacement_rejects_terminal_selection_substitution() -> None:
    inputs = _fixture()
    object.__setattr__(
        inputs["terminals"], "selection_sha256", _sha(b"different selection")
    )

    with pytest.raises(
        Exact100SuccessorReplacementError, match="different predecessor"
    ):
        project_exact100_successor_replacement(
            predecessor=inputs["predecessor"],
            terminal_exclusions=inputs["terminals"],
            promotion_pool=inputs["promotion_pool"],
        )


def test_source_commitments_are_derived_from_the_replayed_bytes() -> None:
    inputs = _fixture()

    result = project_exact100_successor_replacement(
        predecessor=inputs["predecessor"],
        terminal_exclusions=inputs["terminals"],
        promotion_pool=inputs["promotion_pool"],
    )

    commitments = result.config["source_commitments"]
    assert commitments["predecessor_selection"] == _sha(inputs["selection_bytes"])
    assert commitments["predecessor_case_relevance"] == _sha(
        _jsonl(inputs["predecessor_artifacts"]["case_relevance"])
    )
    assert commitments["reserve_ranked_reserve"] == _sha(_jsonl(inputs["reserve"]))
    assert commitments["reserve_core_filter_results"] == _sha(
        _jsonl(inputs["reserve_artifacts"]["core_filter_results"])
    )
    assert commitments["terminal_exclusions"] == inputs["terminals"].commitment_sha256
    # No caller-asserted digest survives into the config: every key is one this
    # projector recomputed from bytes a verifier parsed.
    assert set(commitments) == {
        "predecessor_projection",
        "predecessor_selection",
        "predecessor_case_relevance",
        "predecessor_download_manifest",
        "predecessor_disclosure_clearance",
        "predecessor_restriction_evidence",
        "predecessor_core_filter_results",
        "terminal_exclusions",
        "reserve_ranked_reserve",
        "reserve_source_selection",
        "reserve_case_relevance",
        "reserve_download_manifest",
        "reserve_disclosure_clearance",
        "reserve_restriction_evidence",
        "reserve_core_filter_results",
        "reserve_producer_config",
        "reserve_producer_run_card",
        "reserve_producer_root",
    }


def test_replacement_rejects_pool_artifact_edited_after_replay() -> None:
    """An edit invisible to the eligibility rules must still fail the commitment."""

    inputs = _fixture()
    pool = inputs["promotion_pool"]
    # `case_id` is not read by any promotion rule, so eligibility is unchanged;
    # only the derived commitment can catch this.
    pool.selection_by_candidate["R2"]["case_id"] = "tampered"

    with pytest.raises(Exact100SuccessorReplacementError, match="artifacts changed"):
        project_exact100_successor_replacement(
            predecessor=inputs["predecessor"],
            terminal_exclusions=inputs["terminals"],
            promotion_pool=pool,
        )


def test_replacement_rejects_promotion_root_edited_after_replay() -> None:
    inputs = _fixture()
    object.__setattr__(inputs["promotion_pool"], "producer_root_bytes", b"tampered")

    with pytest.raises(Exact100SuccessorReplacementError, match="artifacts changed"):
        project_exact100_successor_replacement(
            predecessor=inputs["predecessor"],
            terminal_exclusions=inputs["terminals"],
            promotion_pool=inputs["promotion_pool"],
        )


def test_replacement_rejects_predecessor_artifact_edited_after_replay() -> None:
    inputs = _fixture()
    inputs["predecessor"].case_relevance[0]["documents"] = ["tampered"]

    with pytest.raises(Exact100SuccessorReplacementError, match="producer replay"):
        project_exact100_successor_replacement(
            predecessor=inputs["predecessor"],
            terminal_exclusions=inputs["terminals"],
            promotion_pool=inputs["promotion_pool"],
        )
