# pyright: reportPrivateUsage=false
# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownMemberType=false
# pyright: reportUnusedVariable=false
# pyright: reportUnknownVariableType=false

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest
from legalforecast.ingestion.canonical_json import canonical_json_bytes
from legalforecast.ingestion.exact100_successor_replacement import (
    CONFIG_SCHEMA_VERSION,
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
    verify_post_selection_terminal_exclusions,
    verify_stipulated_target_evidence,
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
        "documents": [
            {
                "source_document_id": f"{candidate_id}-motion",
                "document_role": "motion_to_dismiss_memorandum",
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
        relevance.append({"candidate_id": candidate_id, "documents": [document_id]})
        manifest.append(
            {
                "candidate_id": candidate_id,
                "source_document_id": document_id,
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


def _fixture(tmp_path: Path) -> dict[str, Any]:
    selected_ids = [f"C{number:03d}" for number in range(1, 101)]
    selection = [_selection_row(candidate_id) for candidate_id in selected_ids]
    selection_bytes = b"".join(_bytes(record) for record in selection)
    predecessor_artifacts = _candidate_artifacts(selected_ids)
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
        source_document = b"authenticated PDF source"
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
            verify_stipulated_target_evidence(
                selection_bytes=selection_bytes,
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
    return locals()


def _write_replay_root(
    root: Path,
    *,
    predecessor_config: dict[str, Any],
    predecessor_output_bytes: dict[str, bytes],
    reserve: list[dict[str, Any]],
    reserve_selection: list[dict[str, Any]],
    reserve_artifacts: dict[str, list[dict[str, Any]]],
) -> None:
    root.joinpath("predecessor-config.json").write_bytes(_bytes(predecessor_config))
    for name, payload in predecessor_output_bytes.items():
        root.joinpath(f"predecessor-{name}").write_bytes(payload)
    promotion_bytes = {
        "ranked_reserve": _jsonl(reserve),
        "source_selection": _jsonl(reserve_selection),
        **{name: _jsonl(rows) for name, rows in reserve_artifacts.items()},
    }
    commitments = {name: _sha(payload) for name, payload in promotion_bytes.items()}
    authority = {
        "provider_activity_permitted": False,
        "paid_activity_permitted": False,
        "evaluation_authorized": False,
        "freeze_authorized": False,
        "dispatch_authorized": False,
    }
    producer_config = {
        "schema_version": (
            "legalforecast.exact100_successor_replacement_inputs_config.v1"
        ),
        "status": "completed",
        "source_commitments": commitments,
        **authority,
    }
    producer_config_bytes = _bytes(producer_config)
    producer_run_card = {
        "schema_version": (
            "legalforecast.exact100_successor_replacement_inputs_run_card.v1"
        ),
        "stage": "replay-exact100-successor-replacement-inputs",
        "status": "completed",
        "config_sha256": _sha(producer_config_bytes),
        "source_commitments": commitments,
        "provider_activity_requested": False,
        "provider_activity_executed": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "evaluation_authorized": False,
        "freeze_authorized": False,
        "dispatch_authorized": False,
    }
    producer_run_card_bytes = _bytes(producer_run_card)
    producer_root = {
        "schema_version": (
            "legalforecast.exact100_successor_replacement_inputs_root.v1"
        ),
        "producer_config_sha256": _sha(producer_config_bytes),
        "producer_run_card_sha256": _sha(producer_run_card_bytes),
        "source_commitments": commitments,
        **authority,
    }
    root.joinpath("promotion-producer-config.json").write_bytes(producer_config_bytes)
    root.joinpath("promotion-producer-run-card.json").write_bytes(
        producer_run_card_bytes
    )
    root.joinpath("promotion-producer-root.json").write_bytes(_bytes(producer_root))
    for name, payload in promotion_bytes.items():
        file_name = {
            "ranked_reserve": "ranked-reserve.jsonl",
            "source_selection": "source-selection.jsonl",
            "case_relevance": "case-relevance.jsonl",
            "download_manifest": "document-downloads-merged.jsonl",
            "disclosure_clearance": "disclosure-clearance.jsonl",
            "restriction_evidence": "restriction-evidence.jsonl",
            "core_filter_results": "core-filter-results.jsonl",
        }[name]
        root.joinpath(f"promotion-{file_name}").write_bytes(payload)


def test_replacement_preserves_rows_and_promotes_first_clean_reserves(
    tmp_path: Path,
) -> None:
    inputs = _fixture(tmp_path)

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


def test_replacement_fails_closed_when_clean_reserves_are_insufficient(
    tmp_path: Path,
) -> None:
    inputs = _fixture(tmp_path)
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
    tmp_path: Path, artifact_name: str, expected_reason: str
) -> None:
    inputs = _fixture(tmp_path)
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


def test_replacement_rejects_terminal_selection_substitution(tmp_path: Path) -> None:
    inputs = _fixture(tmp_path)
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


def test_source_commitments_are_derived_from_the_replayed_bytes(tmp_path: Path) -> None:
    inputs = _fixture(tmp_path)

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


def test_replacement_rejects_pool_artifact_edited_after_replay(tmp_path: Path) -> None:
    """An edit invisible to the eligibility rules must still fail the commitment."""

    inputs = _fixture(tmp_path)
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


def test_replacement_rejects_promotion_root_edited_after_replay(
    tmp_path: Path,
) -> None:
    inputs = _fixture(tmp_path)
    object.__setattr__(inputs["promotion_pool"], "producer_root_bytes", b"tampered")

    with pytest.raises(Exact100SuccessorReplacementError, match="artifacts changed"):
        project_exact100_successor_replacement(
            predecessor=inputs["predecessor"],
            terminal_exclusions=inputs["terminals"],
            promotion_pool=inputs["promotion_pool"],
        )


def test_replacement_rejects_predecessor_artifact_edited_after_replay(
    tmp_path: Path,
) -> None:
    inputs = _fixture(tmp_path)
    inputs["predecessor"].case_relevance[0]["documents"] = ["tampered"]

    with pytest.raises(Exact100SuccessorReplacementError, match="producer replay"):
        project_exact100_successor_replacement(
            predecessor=inputs["predecessor"],
            terminal_exclusions=inputs["terminals"],
            promotion_pool=inputs["promotion_pool"],
        )
