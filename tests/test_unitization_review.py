from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from legalforecast import cli
from legalforecast.cli import main
from legalforecast.unitization.review import (
    ADJUDICATION_SCHEMA_VERSION,
    FINALIZED_SCHEMA_VERSION,
    LEGACY_FINALIZED_SCHEMA_VERSION,
    UnitizationReviewError,
    V4FinalizedCitationDocument,
    apply_unitization_reviews,
    canonical_records_sha256,
    canonical_sha256,
    require_finalized_envelopes,
    validate_v4_finalized_unit_citations,
    verify_finalized_prediction_units,
)


def test_apply_unitization_reviews_supports_every_consuming_disposition() -> None:
    """Cover the dispositions that consume a source unit.

    ADD consumes none, emits the v3 successor schema for the whole output, and
    is covered in tests/test_unitization_add_adjudication.py; keeping it out of
    this case preserves the v2/v1 schema-selection assertions below.
    """

    raw = [
        _candidate("accept", [_unit("a")]),
        _candidate("amend", [_unit("a")]),
        _candidate("split", [_unit("a")]),
        _candidate("merge", [_unit("a"), _unit("b")]),
        _candidate("drop", [_unit("a"), _unit("b")]),
        _candidate("exclude", [_unit("a")]),
    ]
    queue = [
        _review("accept", "a"),
        _review("amend", "a"),
        _review("split", "a"),
        _review("merge", "a"),
        _review("merge", "b"),
        _review("drop", "a"),
        _review("exclude", "a"),
    ]
    adjudications = [
        _adjudication("accept", "ACCEPT", ["a"]),
        _adjudication("amend", "AMEND", ["a"], [_unit("a-amended")]),
        _adjudication("split", "SPLIT", ["a"], [_unit("a-1"), _unit("a-2")]),
        _adjudication("merge", "MERGE", ["a", "b"], [_unit("ab")]),
        _adjudication("drop", "DROP", ["a"]),
        _adjudication(
            "exclude",
            "CANDIDATE-EXCLUSION",
            ["a"],
            exclusion_reason="stage_a_boundary_unresolvable",
        ),
    ]

    result = apply_unitization_reviews(
        prediction_unit_records=raw,
        review_records=queue,
        adjudication_records=adjudications,
    )

    by_candidate = {record["candidate_id"]: record for record in result}
    assert {unit["unit_id"] for unit in by_candidate["split"]["prediction_units"]} == {
        "a-1",
        "a-2",
    }
    assert [unit["unit_id"] for unit in by_candidate["merge"]["prediction_units"]] == [
        "ab"
    ]
    assert [unit["unit_id"] for unit in by_candidate["drop"]["prediction_units"]] == [
        "b"
    ]
    assert by_candidate["exclude"]["status"] == "candidate_excluded"
    assert by_candidate["exclude"]["prediction_units"] == []
    assert all(
        record["schema_version"] == FINALIZED_SCHEMA_VERSION for record in result
    )
    verify_finalized_prediction_units(result, raw, adjudications, queue)


def test_v4_finalized_citations_reconstruct_from_candidate_predecision_text() -> None:
    finalized = _v4_finalized_candidate()

    validate_v4_finalized_unit_citations(
        [finalized],
        source_documents_by_candidate={"cand": _v4_citation_documents()},
    )


def test_cli_v4_finalized_citations_use_authenticated_lineage_snapshot(
    tmp_path: Path,
) -> None:
    markdown_root = tmp_path / "markdown" / "cand"
    markdown_root.mkdir(parents=True)
    (markdown_root / "complaint.md").write_bytes(
        b"Heading\nCount I pleads breach of contract.\nPrayer"
    )
    (markdown_root / "motion.md").write_bytes(
        b"Introduction\nDefendant moves to dismiss Count I.\nArgument"
    )
    unitization_card = tmp_path / "llm-unitize.json"
    unitization_card.write_text(
        json.dumps(
            {"model_execution": {"provider_attempt_namespace": "claim-ontology-v4"}}
        ),
        encoding="utf-8",
    )
    lineage = SimpleNamespace(
        selection_records=(
            {
                "candidate_id": "cand",
                "documents": [
                    {
                        "source_document_id": "complaint",
                        "document_role": "complaint",
                        "model_visible": True,
                        "contains_target_outcome": False,
                    },
                    {
                        "source_document_id": "motion",
                        "document_role": "motion_to_dismiss_memorandum",
                        "model_visible": True,
                        "contains_target_outcome": False,
                    },
                ],
            },
        ),
        parser_records=(
            {
                "candidate_id": "cand",
                "source_document_id": "complaint",
                "status": "succeeded",
                "markdown_path": "cand/complaint.md",
            },
            {
                "candidate_id": "cand",
                "source_document_id": "motion",
                "status": "succeeded",
                "markdown_path": "cand/motion.md",
            },
        ),
        markdown_root=tmp_path / "markdown",
        markdown_bytes={
            "cand/complaint.md": (
                b"Heading\nCount I pleads breach of contract.\nPrayer"
            ),
            "cand/motion.md": (
                b"Introduction\nDefendant moves to dismiss Count I.\nArgument"
            ),
        },
    )

    cli._validate_v4_finalized_stage_a_citations(
        [_v4_finalized_candidate()],
        lineage=lineage,
        llm_unitization_run_card_path=unitization_card,
    )

    tampered = deepcopy(_v4_finalized_candidate())
    tampered["prediction_units"][0]["source_citations"][1]["excerpt"] = (
        "Defendant moves to dismiss a different count."
    )
    with pytest.raises(cli.CommandError, match="authenticated Markdown"):
        cli._validate_v4_finalized_stage_a_citations(
            [tampered],
            lineage=lineage,
            llm_unitization_run_card_path=unitization_card,
        )


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("unknown_finalized_field", "forged", "canonical prediction unit"),
        ("should_score", False, "should_score does not match"),
    ],
)
def test_v4_finalized_citations_reject_unknown_or_computed_field_drift(
    field: str,
    value: object,
    error: str,
) -> None:
    finalized = _v4_finalized_candidate()
    finalized["prediction_units"][0][field] = value

    with pytest.raises(UnitizationReviewError, match=error):
        validate_v4_finalized_unit_citations(
            [finalized],
            source_documents_by_candidate={"cand": _v4_citation_documents()},
        )


def test_v4_finalized_citations_reject_cross_candidate_or_outcome_source() -> None:
    finalized = _v4_finalized_candidate()
    documents = list(_v4_citation_documents())
    documents[0] = V4FinalizedCitationDocument(
        document_id="complaint",
        document_role="complaint",
        markdown="Count I pleads breach of contract.",
        is_predecision_material=False,
        contains_target_outcome=True,
    )

    with pytest.raises(UnitizationReviewError, match="non-predecision"):
        validate_v4_finalized_unit_citations(
            [finalized], source_documents_by_candidate={"cand": documents}
        )

    with pytest.raises(UnitizationReviewError, match="unsupplied candidate document"):
        validate_v4_finalized_unit_citations(
            [finalized],
            source_documents_by_candidate={"other-candidate": documents},
        )


def test_v4_finalized_citations_require_exact_excerpt_and_both_evidence_roles() -> None:
    finalized = _v4_finalized_candidate()
    finalized["prediction_units"][0]["source_citations"][0]["excerpt"] = (
        "Count I pleads a different claim."
    )
    with pytest.raises(UnitizationReviewError, match="exact substring"):
        validate_v4_finalized_unit_citations(
            [finalized],
            source_documents_by_candidate={"cand": _v4_citation_documents()},
        )

    finalized = _v4_finalized_candidate()
    finalized["prediction_units"][0]["source_citations"] = [
        finalized["prediction_units"][0]["source_citations"][0]
    ]
    with pytest.raises(UnitizationReviewError, match="target-MTD"):
        validate_v4_finalized_unit_citations(
            [finalized],
            source_documents_by_candidate={"cand": _v4_citation_documents()},
        )


def test_one_adjudication_consumes_multiple_reviews_for_same_source_unit() -> None:
    raw = [_candidate("cand", [_unit("a")])]
    first = _review("cand", "a")
    second = {**first, "review_id": "cand:a:structural:second"}
    adjudication = _adjudication("cand", "AMEND", ["a"], [_unit("amended")])
    adjudication["review_ids"] = [first["review_id"], second["review_id"]]

    [result] = apply_unitization_reviews(
        prediction_unit_records=raw,
        review_records=[first, second],
        adjudication_records=[adjudication],
    )

    assert [unit["unit_id"] for unit in result["prediction_units"]] == ["amended"]
    assert result["schema_version"] == LEGACY_FINALIZED_SCHEMA_VERSION


def test_drop_cannot_remove_every_unit_from_retained_candidate() -> None:
    with pytest.raises(UnitizationReviewError, match="must retain at least one unit"):
        apply_unitization_reviews(
            prediction_unit_records=[_candidate("cand", [_unit("a")])],
            review_records=[_review("cand", "a")],
            adjudication_records=[_adjudication("cand", "DROP", ["a"])],
        )


def test_drop_must_consume_exactly_one_distinct_source_unit() -> None:
    with pytest.raises(UnitizationReviewError, match="exactly one unit"):
        apply_unitization_reviews(
            prediction_unit_records=[
                _candidate("cand", [_unit("a"), _unit("b"), _unit("c")])
            ],
            review_records=[_review("cand", "a"), _review("cand", "b")],
            adjudication_records=[_adjudication("cand", "DROP", ["a", "b"])],
        )


def test_drop_requires_explicit_source_unit_ids() -> None:
    raw = [_candidate("cand", [_unit("a"), _unit("b")])]
    queue = [_review("cand", "a")]
    adjudication = _adjudication("cand", "DROP", ["a"])
    adjudication.pop("source_unit_ids")

    with pytest.raises(UnitizationReviewError, match="requires explicit"):
        apply_unitization_reviews(
            prediction_unit_records=raw,
            review_records=queue,
            adjudication_records=[adjudication],
        )


@pytest.mark.parametrize("disposition", ["ACCEPT", "AMEND", "SPLIT"])
def test_single_source_dispositions_cannot_implicitly_merge(
    disposition: str,
) -> None:
    finalized_units = {
        "ACCEPT": [],
        "AMEND": [_unit("replacement")],
        "SPLIT": [_unit("first"), _unit("second")],
    }[disposition]

    with pytest.raises(UnitizationReviewError, match="must consume exactly one unit"):
        apply_unitization_reviews(
            prediction_unit_records=[_candidate("cand", [_unit("a"), _unit("b")])],
            review_records=[_review("cand", "a"), _review("cand", "b")],
            adjudication_records=[
                _adjudication("cand", disposition, ["a", "b"], finalized_units)
            ],
        )


def test_finalized_chain_rejects_removed_drop_provenance() -> None:
    raw = [_candidate("cand", [_unit("a"), _unit("b")])]
    queue = [_review("cand", "a")]
    adjudications = [_adjudication("cand", "DROP", ["a"])]
    finalized = apply_unitization_reviews(
        prediction_unit_records=raw,
        review_records=queue,
        adjudication_records=adjudications,
    )
    broken = deepcopy(finalized[0])
    broken["dropped_units"] = []

    with pytest.raises(UnitizationReviewError, match="does not consume adjudications"):
        verify_finalized_prediction_units([broken], raw, adjudications, queue)


def test_finalized_chain_rejects_drop_bound_to_wrong_or_retained_unit() -> None:
    raw = [_candidate("cand", [_unit("a"), _unit("b")])]
    queue = [_review("cand", "a")]
    adjudications = [_adjudication("cand", "DROP", ["a"])]
    finalized = apply_unitization_reviews(
        prediction_unit_records=raw,
        review_records=queue,
        adjudication_records=adjudications,
    )
    wrong = deepcopy(finalized[0])
    wrong["dropped_units"][0]["unit_id"] = "b"
    wrong["dropped_units"][0]["source_unit_sha256"] = canonical_sha256(_unit("b"))

    with pytest.raises(UnitizationReviewError, match="remains in finalized"):
        verify_finalized_prediction_units([wrong], raw, adjudications, queue)


def test_finalized_chain_rejects_duplicate_drop_rows() -> None:
    raw = [_candidate("cand", [_unit("a"), _unit("b")])]
    queue = [_review("cand", "a")]
    adjudications = [_adjudication("cand", "DROP", ["a"])]
    finalized = apply_unitization_reviews(
        prediction_unit_records=raw,
        review_records=queue,
        adjudication_records=adjudications,
    )
    broken = deepcopy(finalized[0])
    broken["dropped_units"].append(deepcopy(broken["dropped_units"][0]))

    with pytest.raises(UnitizationReviewError, match="duplicate dropped unit"):
        verify_finalized_prediction_units([broken], raw, adjudications, queue)


@pytest.mark.parametrize(
    "schema_version", [LEGACY_FINALIZED_SCHEMA_VERSION, FINALIZED_SCHEMA_VERSION]
)
def test_finalized_chain_rejects_drop_adjudication_bound_to_retained_unit(
    schema_version: str,
) -> None:
    raw = [_candidate("cand", [_unit("a"), _unit("b")])]
    queue = [_review("cand", "a")]
    adjudications = [_adjudication("cand", "DROP", ["a"])]
    finalized = apply_unitization_reviews(
        prediction_unit_records=raw,
        review_records=queue,
        adjudication_records=adjudications,
    )
    broken = deepcopy(finalized[0])
    broken["schema_version"] = schema_version
    broken["dropped_units"] = []
    if schema_version == LEGACY_FINALIZED_SCHEMA_VERSION:
        broken.pop("dropped_units")
    drop = adjudications[0]
    broken["prediction_units"].append(
        {
            **_unit("a"),
            "source_unit_sha256s": [canonical_sha256(_unit("a"))],
            "adjudication_id": drop["adjudication_id"],
            "adjudication_sha256": canonical_sha256(drop),
            "disposition": "DROP",
        }
    )

    with pytest.raises(
        UnitizationReviewError,
        match=r"broken adjudication hash link|schema does not match",
    ):
        verify_finalized_prediction_units([broken], raw, adjudications, queue)


def test_candidate_exclusion_rejects_dropped_unit_rows() -> None:
    record = {
        "schema_version": FINALIZED_SCHEMA_VERSION,
        "status": "candidate_excluded",
        "candidate_id": "cand",
        "case_id": "case-cand",
        "unitization_review_queue_sha256": "a" * 64,
        "prediction_units": [],
        "dropped_units": [
            {
                "unit_id": "a",
                "source_unit_sha256": "b" * 64,
                "adjudication_id": "adj-drop",
                "adjudication_sha256": "c" * 64,
                "disposition": "DROP",
            }
        ],
        "exclusion": {"reason": "unresolvable"},
    }

    with pytest.raises(UnitizationReviewError, match="candidate-exclusion"):
        require_finalized_envelopes([record])


def test_lightweight_envelope_rejects_duplicate_drop_rows() -> None:
    dropped = {
        "unit_id": "a",
        "source_unit_sha256": "b" * 64,
        "adjudication_id": "adj-drop",
        "adjudication_sha256": "c" * 64,
        "disposition": "DROP",
    }
    record = {
        "schema_version": FINALIZED_SCHEMA_VERSION,
        "status": "finalized",
        "candidate_id": "cand",
        "case_id": "case-cand",
        "unitization_review_queue_sha256": "a" * 64,
        "prediction_units": [
            {
                **_unit("b"),
                "source_unit_sha256s": ["d" * 64],
                "adjudication_id": "automatic:" + "d" * 64,
                "adjudication_sha256": None,
                "disposition": "ACCEPT",
            }
        ],
        "dropped_units": [dropped, deepcopy(dropped)],
        "exclusion": None,
    }

    with pytest.raises(UnitizationReviewError, match="duplicate dropped unit"):
        require_finalized_envelopes([record])


def test_finalized_chain_rejects_raw_bypass_and_hash_mutation() -> None:
    raw = [_candidate("amend", [_unit("a")])]
    adjudications = [_adjudication("amend", "AMEND", ["a"], [_unit("a-amended")])]
    queue = [_review("amend", "a")]
    finalized = apply_unitization_reviews(
        prediction_unit_records=raw,
        review_records=queue,
        adjudication_records=adjudications,
    )
    broken = deepcopy(finalized[0])
    broken["prediction_units"][0]["source_unit_sha256s"] = ["0" * 64]

    with pytest.raises(UnitizationReviewError, match="broken source-unit hash link"):
        verify_finalized_prediction_units([broken], raw, adjudications, queue)
    with pytest.raises(UnitizationReviewError, match="raw or unsupported"):
        verify_finalized_prediction_units(raw, raw, adjudications, queue)


@pytest.mark.parametrize("replacement", ["other", "duplicate"])
def test_verifier_requires_exact_adjudicated_source_hashes(replacement: str) -> None:
    raw = [_candidate("amend", [_unit("a"), _unit("b")])]
    adjudications = [_adjudication("amend", "AMEND", ["a"], [_unit("a-amended")])]
    queue = [_review("amend", "a")]
    finalized = apply_unitization_reviews(
        prediction_unit_records=raw,
        review_records=queue,
        adjudication_records=adjudications,
    )
    broken = deepcopy(finalized[0])
    source_hashes = broken["prediction_units"][0]["source_unit_sha256s"]
    if replacement == "other":
        source_hashes[:] = [canonical_sha256(_unit("b"))]
    else:
        source_hashes.append(source_hashes[0])

    with pytest.raises(UnitizationReviewError, match="exact adjudicated source hashes"):
        verify_finalized_prediction_units([broken], raw, adjudications, queue)


def test_verifier_binds_automatic_unit_content_to_its_raw_hash() -> None:
    raw = [_candidate("cand", [_unit("a")])]
    [finalized] = apply_unitization_reviews(
        prediction_unit_records=raw,
        review_records=[],
        adjudication_records=[],
    )
    finalized["prediction_units"][0]["claim_name"] = "Substituted claim"

    with pytest.raises(UnitizationReviewError, match="automatic finalization link"):
        verify_finalized_prediction_units([finalized], raw, [], [])


def test_apply_unitization_reviews_requires_complete_queue_drain() -> None:
    with pytest.raises(UnitizationReviewError, match="unresolved reviews"):
        apply_unitization_reviews(
            prediction_unit_records=[_candidate("cand", [_unit("a")])],
            review_records=[_review("cand", "a")],
            adjudication_records=[],
        )


def test_apply_unitization_reviews_rejects_source_review_mismatch() -> None:
    adjudication = _adjudication("cand", "ACCEPT", ["b"])
    adjudication["review_ids"] = ["cand:a:stage-a-review"]

    with pytest.raises(UnitizationReviewError, match="must include reviewed units"):
        apply_unitization_reviews(
            prediction_unit_records=[_candidate("cand", [_unit("a"), _unit("b")])],
            review_records=[_review("cand", "a")],
            adjudication_records=[adjudication],
        )


def test_candidate_exclusion_must_consume_whole_candidate() -> None:
    with pytest.raises(UnitizationReviewError, match="must consume every unit"):
        apply_unitization_reviews(
            prediction_unit_records=[_candidate("cand", [_unit("a"), _unit("b")])],
            review_records=[_review("cand", "a")],
            adjudication_records=[
                _adjudication(
                    "cand",
                    "CANDIDATE-EXCLUSION",
                    ["a"],
                    exclusion_reason="unresolvable",
                )
            ],
        )


def test_candidate_exclusion_can_consume_unqueued_units() -> None:
    raw = [_candidate("cand", [_unit("a"), _unit("b")])]
    queue = [_review("cand", "a")]
    adjudication = _adjudication(
        "cand",
        "CANDIDATE-EXCLUSION",
        ["a"],
        exclusion_reason="unresolvable",
    )
    adjudication["source_unit_ids"] = ["a", "b"]

    [result] = apply_unitization_reviews(
        prediction_unit_records=raw,
        review_records=queue,
        adjudication_records=[adjudication],
    )

    assert result["status"] == "candidate_excluded"
    assert result["prediction_units"] == []


def test_accept_preserves_current_same_id_amendment() -> None:
    raw = [_candidate("cand", [_unit("a")])]
    first = _review("cand", "a")
    second = {**first, "review_id": "cand:a:structural:second"}
    amended = _unit("a")
    amended["claim_name"] = "Amended Claim"
    amend = _adjudication("cand", "AMEND", ["a"], [amended])
    amend["review_ids"] = [first["review_id"]]
    accept = _adjudication("cand", "ACCEPT", ["a"])
    accept["adjudication_id"] = "adj-cand-accept"
    accept["review_ids"] = [second["review_id"]]

    with pytest.raises(UnitizationReviewError, match="coalesce reviews"):
        apply_unitization_reviews(
            prediction_unit_records=raw,
            review_records=[first, second],
            adjudication_records=[amend, accept],
        )


def test_verifier_rejects_unresolved_same_source_review() -> None:
    raw = [_candidate("cand", [_unit("a")])]
    first = _review("cand", "a")
    second = {**first, "review_id": "cand:a:structural:second"}
    adjudication = _adjudication("cand", "ACCEPT", ["a"])
    adjudication["review_ids"] = [second["review_id"]]
    finalized = apply_unitization_reviews(
        prediction_unit_records=raw,
        review_records=[second],
        adjudication_records=[adjudication],
    )
    forged = deepcopy(finalized[0])
    forged["unitization_review_queue_sha256"] = canonical_records_sha256(
        [first, second]
    )

    with pytest.raises(UnitizationReviewError, match="unresolved reviews"):
        verify_finalized_prediction_units(
            [forged], raw, [adjudication], [first, second]
        )


def test_verifier_rejects_two_adjudications_of_same_raw_source() -> None:
    raw = [_candidate("cand", [_unit("a")])]
    first = _review("cand", "a")
    second = {**first, "review_id": "cand:a:structural:second"}
    first_replacement = _unit("first")
    second_replacement = _unit("second")
    first_adjudication = _adjudication("cand", "AMEND", ["a"], [first_replacement])
    first_adjudication["review_ids"] = [first["review_id"]]
    second_adjudication = _adjudication("cand", "AMEND", ["a"], [second_replacement])
    second_adjudication["adjudication_id"] = "adj-cand-second"
    second_adjudication["review_ids"] = [second["review_id"]]
    [first_finalized] = apply_unitization_reviews(
        prediction_unit_records=raw,
        review_records=[first],
        adjudication_records=[first_adjudication],
    )
    [second_finalized] = apply_unitization_reviews(
        prediction_unit_records=raw,
        review_records=[second],
        adjudication_records=[second_adjudication],
    )
    forged = deepcopy(first_finalized)
    forged["prediction_units"].extend(second_finalized["prediction_units"])
    forged["unitization_review_queue_sha256"] = canonical_records_sha256(
        [first, second]
    )

    with pytest.raises(UnitizationReviewError, match="more than once"):
        verify_finalized_prediction_units(
            [forged],
            raw,
            [first_adjudication, second_adjudication],
            [first, second],
        )


def test_finalized_chain_rejects_multiple_automatic_source_hashes() -> None:
    raw = [_candidate("cand", [_unit("a"), _unit("b")])]
    finalized = apply_unitization_reviews(
        prediction_unit_records=raw,
        review_records=[],
        adjudication_records=[],
    )
    broken = deepcopy(finalized[0])
    broken["prediction_units"][0]["source_unit_sha256s"].append(
        broken["prediction_units"][1]["source_unit_sha256s"][0]
    )

    with pytest.raises(UnitizationReviewError, match="automatic finalization link"):
        verify_finalized_prediction_units([broken], raw, [], [])


def test_finalized_chain_verifies_candidate_exclusion_adjudication() -> None:
    raw = [_candidate("cand", [_unit("a")])]
    adjudications = [
        _adjudication(
            "cand",
            "CANDIDATE-EXCLUSION",
            ["a"],
            exclusion_reason="unresolvable",
        )
    ]
    queue = [_review("cand", "a")]
    finalized = apply_unitization_reviews(
        prediction_unit_records=raw,
        review_records=queue,
        adjudication_records=adjudications,
    )
    broken = deepcopy(finalized[0])
    broken["exclusion"]["adjudication_sha256"] = "0" * 64

    with pytest.raises(UnitizationReviewError, match="broken exclusion hash link"):
        verify_finalized_prediction_units([broken], raw, adjudications, queue)


def test_finalized_chain_requires_exclusion_to_consume_unqueued_units() -> None:
    raw = [_candidate("cand", [_unit("a"), _unit("b")])]
    queue = [_review("cand", "a")]
    adjudication = _adjudication(
        "cand",
        "CANDIDATE-EXCLUSION",
        ["a"],
        exclusion_reason="unresolvable",
    )
    adjudication["source_unit_ids"] = ["a", "b"]
    finalized = apply_unitization_reviews(
        prediction_unit_records=raw,
        review_records=queue,
        adjudication_records=[adjudication],
    )
    broken_adjudication = deepcopy(adjudication)
    broken_adjudication["source_unit_ids"] = ["a"]
    broken_finalized = deepcopy(finalized[0])
    broken_finalized["exclusion"]["adjudication_sha256"] = canonical_sha256(
        broken_adjudication
    )

    with pytest.raises(UnitizationReviewError, match="complete provenance"):
        verify_finalized_prediction_units(
            [broken_finalized], raw, [broken_adjudication], queue
        )


def test_apply_unitization_review_cli_writes_finalized_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw_path = tmp_path / "raw.jsonl"
    queue_path = tmp_path / "queue.jsonl"
    adjudications_path = tmp_path / "adjudications.jsonl"
    output_root = tmp_path / "out"
    unitization_run_card = tmp_path / "llm-unitize.json"
    structural_run_card = tmp_path / "llm-review-stage-a.json"
    provider_caps = tmp_path / "provider-caps.json"
    provider_journal = tmp_path / "provider-attempts.sqlite3"
    _write_jsonl(raw_path, [_candidate("cand", [_unit("a")])])
    _write_jsonl(queue_path, [_review("cand", "a")])
    _write_jsonl(adjudications_path, [_adjudication("cand", "ACCEPT", ["a"])])
    unitization_run_card.write_text("{}\n", encoding="utf-8")
    structural_run_card.write_text("{}\n", encoding="utf-8")
    provider_caps.write_text("{}\n", encoding="utf-8")
    provider_journal.write_bytes(b"fixture")
    monkeypatch.setattr(
        cli,
        "_verified_shared_provider_chain",
        lambda *args, **kwargs: (object(), unitization_run_card),
    )
    monkeypatch.setattr(
        cli, "_verify_stage_a_review_run_card", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(cli, "_require_stage_a_lineage_unchanged", lambda lineage: None)

    assert (
        main(
            [
                "acquisition",
                "apply-unitization-review",
                "--prediction-units",
                str(raw_path),
                "--llm-unitization-run-card",
                str(unitization_run_card),
                "--llm-review-stage-a-run-card",
                str(structural_run_card),
                "--provider-cycle-caps",
                str(provider_caps),
                "--provider-journal",
                str(provider_journal),
                "--unitization-review-queue",
                str(queue_path),
                "--adjudications",
                str(adjudications_path),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )
    record = json.loads(
        (output_root / "finalized-prediction-units.jsonl")
        .read_text(encoding="utf-8")
        .strip()
    )
    assert record["schema_version"] == LEGACY_FINALIZED_SCHEMA_VERSION
    assert record["prediction_units"][0]["adjudication_id"] == "adj-cand"

    finalized_path = output_root / "finalized-prediction-units.jsonl"
    run_card_path = output_root / "run-cards" / "apply-unitization-review.json"
    lineage = SimpleNamespace(
        input_commitments={
            "provider_cycle_caps": cli._stage_a_file_commitment(provider_caps)
        },
        provider_caps_sha256=cli._path_sha256(provider_caps),
        provider_journal_path=provider_journal,
    )
    monkeypatch.setattr(
        cli,
        "_verify_stage_a_unitization_run_card",
        lambda *args, **kwargs: lineage,
    )
    cli._verify_unitization_review_run_card(
        run_card_path,
        llm_unitization_run_card_path=unitization_run_card,
        llm_review_stage_a_run_card_path=structural_run_card,
        raw_prediction_units_path=raw_path,
        original_review_queue_path=None,
        review_queue_path=queue_path,
        adjudications_path=adjudications_path,
        provider_cycle_caps_path=provider_caps,
        provider_journal_path=provider_journal,
        finalized_path=finalized_path,
    )
    substituted = json.loads(finalized_path.read_text().strip())
    substituted["prediction_units"][0]["claim_name"] = "Substituted claim"
    _write_jsonl(finalized_path, [substituted])
    card = json.loads(run_card_path.read_text())
    card["output_commitments"]["finalized_prediction_units"] = (
        cli._stage_a_file_commitment(finalized_path)
    )
    run_card_path.write_text(json.dumps(card) + "\n", encoding="utf-8")
    with pytest.raises(cli.CommandError, match="do not replay"):
        cli._verify_unitization_review_run_card(
            run_card_path,
            llm_unitization_run_card_path=unitization_run_card,
            llm_review_stage_a_run_card_path=structural_run_card,
            raw_prediction_units_path=raw_path,
            original_review_queue_path=None,
            review_queue_path=queue_path,
            adjudications_path=adjudications_path,
            provider_cycle_caps_path=provider_caps,
            provider_journal_path=provider_journal,
            finalized_path=finalized_path,
        )


def _candidate(candidate_id: str, units: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "case_id": f"case-{candidate_id}",
        "prediction_units": units,
    }


def _review(candidate_id: str, unit_id: str) -> dict[str, Any]:
    return {
        "schema_version": "legalforecast.unitization_review_queue.v1",
        "status": "pending_adjudication",
        "candidate_id": candidate_id,
        "case_id": f"case-{candidate_id}",
        "unit_id": unit_id,
        "review_id": f"{candidate_id}:{unit_id}:stage-a-review",
        "route_reason": "fixture",
    }


def _adjudication(
    candidate_id: str,
    disposition: str,
    source_unit_ids: list[str],
    finalized_units: list[dict[str, Any]] | None = None,
    *,
    exclusion_reason: str | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "schema_version": ADJUDICATION_SCHEMA_VERSION,
        "adjudication_id": f"adj-{candidate_id}",
        "candidate_id": candidate_id,
        "case_id": f"case-{candidate_id}",
        "review_ids": [
            f"{candidate_id}:{unit_id}:stage-a-review" for unit_id in source_unit_ids
        ],
        "source_unit_ids": source_unit_ids,
        "disposition": disposition,
        "finalized_units": finalized_units or [],
        "adjudicator_id": "lawyer-1",
        "adjudication_notes": "Reviewed against blinded predecision materials.",
    }
    if exclusion_reason is not None:
        record["exclusion_reason"] = exclusion_reason
    if disposition == "DROP":
        record["drop_reason"] = "spurious_nonunit"
    return record


def _unit(unit_id: str) -> dict[str, Any]:
    return {
        "unit_id": unit_id,
        "count": "I",
        "claim_name": f"Claim {unit_id}",
        "defendant_group": "Defendant",
        "challenged_by_motion": True,
        "challenge_scope": "entire_claim",
        "unit_confidence": 0.9,
        "source_citations": [{"document_id": "complaint", "page": 1}],
        "grouping": "individual",
        "grouping_rationale": None,
        "separable_subclaim": None,
        "uncertainty_notes": None,
        "should_score": True,
    }


def _v4_finalized_candidate() -> dict[str, Any]:
    unit = _unit("unit-1")
    unit["source_citations"] = [
        {
            "document_id": "complaint",
            "docket_entry_number": 1,
            "page": 1,
            "paragraph": None,
            "excerpt": "Count I pleads breach of contract.",
        },
        {
            "document_id": "motion",
            "docket_entry_number": 5,
            "page": 2,
            "paragraph": None,
            "excerpt": "Defendant moves to dismiss Count I.",
        },
    ]
    unit.update(
        {
            "source_unit_sha256s": ["a" * 64],
            "adjudication_id": "automatic:" + "a" * 64,
            "adjudication_sha256": None,
            "disposition": "ACCEPT",
        }
    )
    return {"candidate_id": "cand", "prediction_units": [unit]}


def _v4_citation_documents() -> tuple[V4FinalizedCitationDocument, ...]:
    return (
        V4FinalizedCitationDocument(
            document_id="complaint",
            document_role="complaint",
            markdown="Heading\nCount I pleads breach of contract.\nPrayer",
            is_predecision_material=True,
            contains_target_outcome=False,
        ),
        V4FinalizedCitationDocument(
            document_id="motion",
            document_role="motion_to_dismiss_memorandum",
            markdown="Introduction\nDefendant moves to dismiss Count I.\nArgument",
            is_predecision_material=True,
            contains_target_outcome=False,
        ),
    )


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
