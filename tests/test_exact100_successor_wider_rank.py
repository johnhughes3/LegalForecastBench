# pyright: reportPrivateUsage=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
from __future__ import annotations

import hashlib
from typing import Any

import pytest
from legalforecast.ingestion.canonical_json import canonical_json_bytes
from legalforecast.ingestion.exact100_successor_wider_rank import (
    SEMANTIC_REPAIR_SCHEMA_VERSION,
    Exact100SuccessorWiderRankError,
    VerifiedExact100SuccessorWiderRank,
    _mint_verified_exact100_successor_wider_rank,
    require_verified_exact100_successor_wider_rank,
)


def _sha(row: dict[str, Any]) -> str:
    return hashlib.sha256(
        canonical_json_bytes(row, error_type=ValueError, error_message="invalid")
    ).hexdigest()


def _fixture() -> dict[str, Any]:
    selected_ids = [f"s{index:03d}" for index in range(100)]
    excluded_ids = [f"x{index:03d}" for index in range(53)]
    final: list[dict[str, Any]] = [
        {"candidate_id": f"courtlistener-docket-{cid}", "accepted": True}
        for cid in (*selected_ids, *excluded_ids)
    ]
    identities = [
        {
            "snapshot_candidate_id": row["candidate_id"],
            "canonical_candidate_id": row["candidate_id"].removeprefix(
                "courtlistener-docket-"
            ),
            "snapshot_row_sha256": _sha(row),
        }
        for row in final
    ]
    exact = [{"candidate_id": cid} for cid in selected_ids]
    exclusions = [
        {"candidate_id": cid, "reason": "operative_complaint_not_found"}
        for cid in excluded_ids
    ]
    materialized = [
        {
            "candidate_id": cid,
            "missing_required_document_count": 1,
            "projected_paid_cost_usd": "0.00",
            "exclusion_reasons": [],
        }
        for cid in excluded_ids
    ]

    downloads: list[dict[str, Any]] = []
    clearances: list[dict[str, Any]] = []
    restrictions: list[dict[str, Any]] = []
    repairs: list[dict[str, Any]] = []
    for candidate_id in ("x010", "x001"):
        for suffix, role in (
            ("bundle", "other"),
            ("opening", "motion_to_dismiss_notice"),
            ("opposition", "opposition"),
            ("decision", "decision"),
        ):
            document = {
                "candidate_id": candidate_id,
                "source_document_id": f"{candidate_id}-{suffix}",
                "document_role": role,
                "docket_entry_number": 1,
                "sha256": ("a" if candidate_id == "x001" else "b") * 64,
                "byte_count": 100,
                "free_or_purchased": "free",
            }
            downloads.append(document)
            clearances.append(
                {
                    "candidate_id": candidate_id,
                    "source_document_id": document["source_document_id"],
                    "status": "cleared",
                    "restriction_status": "public",
                    "sha256": document["sha256"],
                    "byte_count": document["byte_count"],
                    "free_or_purchased": "free",
                }
            )
            restrictions.append(
                {
                    "candidate_id": candidate_id,
                    "source_document_id": document["source_document_id"],
                    "restriction_status": "public",
                }
            )
            derived = {
                "bundle": (
                    "embedded_operative_amended_complaint",
                    "amended_complaint",
                ),
                "opening": (
                    "combined_mtd_memorandum",
                    "motion_to_dismiss_memorandum",
                ),
            }.get(suffix)
            if derived is not None:
                repairs.append(
                    {
                        "schema_version": SEMANTIC_REPAIR_SCHEMA_VERSION,
                        "candidate_id": candidate_id,
                        "source_document_id": document["source_document_id"],
                        "docket_entry_number": 1,
                        "original_document_role": role,
                        "derived_document_role": derived[1],
                        "repair_kind": derived[0],
                        "source_sha256": document["sha256"],
                        "source_byte_count": 100,
                        "source_metadata_sha256": "sha256:" + _sha(document),
                        "evidence_cues": [{"cue": "exact cue", "page_number": 1}],
                    }
                )

    return {
        "final153_rows": final,
        "exact100_rows": exact,
        "exclusion_rows": exclusions,
        "materialized_selection_rows": materialized,
        "case_relevance_rows": [
            {"candidate_id": candidate_id} for candidate_id in ("x001", "x010")
        ],
        "download_manifest_rows": downloads,
        "disclosure_rows": clearances,
        "restriction_rows": restrictions,
        "core_filter_rows": [
            {"candidate_id": candidate_id} for candidate_id in ("x001", "x010")
        ],
        "identity_mapping_rows": identities,
        "semantic_repair_rows": repairs,
        "source_commitments": {"final153": "b" * 64, "repairs": "c" * 64},
    }


def test_selects_first_complete_candidate_and_carries_full_ledger() -> None:
    result = _mint_verified_exact100_successor_wider_rank(**_fixture())

    assert require_verified_exact100_successor_wider_rank(result) is result
    assert len(result.ordered_ledger) == 53
    assert [row["candidate_id"] for row in result.ordered_ledger[:2]] == [
        "x001",
        "x010",
    ]
    assert result.selected_candidate_id == "x001"
    assert result.selected_evidence.download_manifest[0]["candidate_id"] == "x001"
    assert sum(row["selected_for_promotion"] for row in result.ordered_ledger) == 1


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda f: f["exact100_rows"].append({"candidate_id": "s000"}), "duplicate"),
        (lambda f: f["exclusion_rows"].pop(), "153 final"),
        (lambda f: f["identity_mapping_rows"].pop(), "cover every final"),
        (lambda f: f["final153_rows"][0].update({"accepted": False}), "hash mismatch"),
        (
            lambda f: f["semantic_repair_rows"][0].update(
                {"source_metadata_sha256": "sha256:" + "d" * 64}
            ),
            "source binding mismatch",
        ),
    ],
)
def test_fails_closed_on_partition_mapping_and_tamper(
    mutation: Any, message: str
) -> None:
    fixture = _fixture()
    mutation(fixture)
    with pytest.raises(Exact100SuccessorWiderRankError, match=message):
        _mint_verified_exact100_successor_wider_rank(**fixture)


def test_rejects_incomplete_repair_and_absent_eligible_candidate() -> None:
    fixture = _fixture()
    fixture["download_manifest_rows"] = [
        row
        for row in fixture["download_manifest_rows"]
        if row["source_document_id"] != "x010-opening"
    ]
    with pytest.raises(Exact100SuccessorWiderRankError, match="absent or duplicate"):
        _mint_verified_exact100_successor_wider_rank(**fixture)

    fixture = _fixture()
    fixture["semantic_repair_rows"] = []
    with pytest.raises(Exact100SuccessorWiderRankError, match="no fully eligible"):
        _mint_verified_exact100_successor_wider_rank(**fixture)


def test_rechecks_integrity_and_refuses_public_construction() -> None:
    forged = VerifiedExact100SuccessorWiderRank()
    with pytest.raises(Exact100SuccessorWiderRankError, match="not minted"):
        require_verified_exact100_successor_wider_rank(forged)

    result = _mint_verified_exact100_successor_wider_rank(**_fixture())
    result.selected_selection_row["candidate_id"] = "tampered"
    with pytest.raises(Exact100SuccessorWiderRankError, match="changed"):
        require_verified_exact100_successor_wider_rank(result)


def test_rejects_nonfinite_ranking_cost() -> None:
    fixture = _fixture()
    fixture["materialized_selection_rows"][2]["projected_paid_cost_usd"] = "NaN"
    with pytest.raises(Exact100SuccessorWiderRankError, match="invalid projected"):
        _mint_verified_exact100_successor_wider_rank(**fixture)
