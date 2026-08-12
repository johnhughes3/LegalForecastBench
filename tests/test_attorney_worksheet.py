"""Tests for deterministic attorney worksheet conversion."""

from __future__ import annotations

import csv
import io
import json
from copy import deepcopy
from typing import Any

import pytest
from legalforecast.unitization.attorney_worksheet import (
    AttorneyWorksheetError,
    convert_attorney_worksheet,
)

JsonRecord = dict[str, Any]


def test_converts_grouped_merge_and_terminal_add() -> None:
    packet = _packet()
    rows = _worksheet_rows(packet)
    rows[0].update(_merge_decision())
    rows[1].update(_merge_decision())
    rows[2].update(
        {
            "adjudication_group": "terminal-add",
            "final_disposition": "ADD",
            "adjudication_notes": "Reconstructed from the complaint and motion.",
            "finalized_units_json": json.dumps([_unit("terminal-unit")]),
            "decision_status": "final",
        }
    )

    result = convert_attorney_worksheet(
        packet=packet,
        worksheet_tsv=_tsv(rows),
        adjudicator_id="attorney-1",
    )

    [ordinary] = result.ordinary_adjudications
    assert ordinary["schema_version"] == "legalforecast.unitization_adjudication.v1"
    assert ordinary["disposition"] == "MERGE"
    assert ordinary["review_ids"] == ["review-1", "review-2"]
    assert ordinary["source_unit_ids"] == ["unit-1", "unit-2"]
    assert ordinary["finalized_units"] == [_unit("merged-unit")]
    assert ordinary["adjudication_id"].startswith("attorney:")

    [terminal] = result.terminal_adjudications
    assert terminal["schema_version"] == "legalforecast.unitization_adjudication.v3"
    assert terminal["review_ids"] == ["terminal-review"]
    assert "source_unit_ids" not in terminal
    assert terminal["terminal_escalation_sha256"] == "e" * 64


def test_rejects_immutable_packet_field_tampering() -> None:
    packet = _packet()
    rows = _worksheet_rows(packet)
    rows[0]["candidate_id"] = "another-candidate"

    with pytest.raises(AttorneyWorksheetError, match="immutable candidate_id"):
        convert_attorney_worksheet(
            packet=packet,
            worksheet_tsv=_tsv(rows),
            adjudicator_id="attorney-1",
        )


def test_rejects_pending_decision_before_emitting_any_records() -> None:
    packet = _packet()
    rows = _worksheet_rows(packet)
    rows[0].update(_merge_decision())
    rows[1].update(_merge_decision())

    with pytest.raises(AttorneyWorksheetError, match="decision is not final"):
        convert_attorney_worksheet(
            packet=packet,
            worksheet_tsv=_tsv(rows),
            adjudicator_id="attorney-1",
        )


def test_rejects_ambiguous_ungrouped_merge() -> None:
    packet = _packet()
    rows = _worksheet_rows(packet)
    rows[0].update(_merge_decision() | {"adjudication_group": ""})
    rows[1].update(_merge_decision() | {"adjudication_group": ""})
    rows[2].update(
        {
            "final_disposition": "CANDIDATE-EXCLUSION",
            "adjudication_notes": "Cannot reconstruct defensibly.",
            "drop_or_exclusion_reason": "unresolvable",
            "decision_status": "final",
        }
    )

    with pytest.raises(AttorneyWorksheetError, match="MERGE requires two units"):
        convert_attorney_worksheet(
            packet=packet,
            worksheet_tsv=_tsv(rows),
            adjudicator_id="attorney-1",
        )


def test_rejects_partial_candidate_exclusion_group() -> None:
    packet = _packet()
    rows = _worksheet_rows(packet)
    rows[0].update(
        {
            "adjudication_group": "exclude-candidate",
            "final_disposition": "CANDIDATE-EXCLUSION",
            "adjudication_notes": "Exclude candidate.",
            "drop_or_exclusion_reason": "unresolvable",
            "decision_status": "final",
        }
    )
    rows[1].update(
        {
            "final_disposition": "ACCEPT",
            "adjudication_notes": "Retain this unit.",
            "decision_status": "final",
        }
    )
    rows[2].update(
        {
            "final_disposition": "CANDIDATE-EXCLUSION",
            "adjudication_notes": "Cannot reconstruct defensibly.",
            "drop_or_exclusion_reason": "unresolvable",
            "decision_status": "final",
        }
    )

    with pytest.raises(
        AttorneyWorksheetError, match="candidate exclusion must group every"
    ):
        convert_attorney_worksheet(
            packet=packet,
            worksheet_tsv=_tsv(rows),
            adjudicator_id="attorney-1",
        )


def test_coalesces_duplicate_reviews_for_one_source_unit() -> None:
    packet = _packet()
    ordinary = packet["candidates"][0]
    duplicate = deepcopy(ordinary["observational_v2"]["unit_items"][0])
    duplicate["review_id"] = "review-1-structural"
    duplicate["source_review_ids"] = ["review-1-structural"]
    ordinary["observational_v2"]["unit_items"].append(duplicate)
    ordinary["authoritative_v1"]["bundle_records"].append(
        {
            "review_id": "review-1-structural",
            "raw_prediction_units": deepcopy(
                ordinary["authoritative_v1"]["bundle_records"][0][
                    "raw_prediction_units"
                ]
            ),
        }
    )
    rows = _worksheet_rows(packet)
    for row in rows:
        if row["unit_id"] == "unit-1":
            row.update(
                {
                    "adjudication_group": "drop-unit-1",
                    "final_disposition": "DROP",
                    "adjudication_notes": "This is not a prediction unit.",
                    "drop_or_exclusion_reason": "remedy_only",
                    "decision_status": "final",
                }
            )
        elif row["unit_id"] == "unit-2":
            row.update(
                {
                    "final_disposition": "ACCEPT",
                    "adjudication_notes": "Retain this unit.",
                    "decision_status": "final",
                }
            )
        else:
            row.update(
                {
                    "final_disposition": "CANDIDATE-EXCLUSION",
                    "adjudication_notes": "Cannot reconstruct defensibly.",
                    "drop_or_exclusion_reason": "unresolvable",
                    "decision_status": "final",
                }
            )

    result = convert_attorney_worksheet(
        packet=packet,
        worksheet_tsv=_tsv(rows),
        adjudicator_id="attorney-1",
    )

    dropped = next(
        record
        for record in result.ordinary_adjudications
        if record["disposition"] == "DROP"
    )
    assert dropped["source_unit_ids"] == ["unit-1"]
    assert dropped["review_ids"] == ["review-1", "review-1-structural"]


def _merge_decision() -> dict[str, str]:
    return {
        "adjudication_group": "merge-one-two",
        "final_disposition": "MERGE",
        "adjudication_notes": "These are nonindependent theories.",
        "finalized_units_json": json.dumps([_unit("merged-unit")]),
        "decision_status": "final",
    }


def _worksheet_rows(packet: JsonRecord) -> list[dict[str, str]]:
    ordinary = packet["candidates"][0]
    terminal = packet["candidates"][1]
    rows: list[dict[str, str]] = []
    for item in ordinary["observational_v2"]["unit_items"]:
        rows.append(
            _base_row(
                surface="ordinary",
                candidate_id="candidate-1",
                case_id="case-1",
                review_ids=item["source_review_ids"],
                unit_id=item["unit_id"],
                reason_code=item["reason"]["code"],
                allowed_actions=item["allowed_actions"],
                terminal_digest="",
            )
        )
    queue = terminal["unitizer_terminal"]["queue_record"]
    rows.append(
        _base_row(
            surface="unitizer_terminal",
            candidate_id="candidate-terminal",
            case_id="case-terminal",
            review_ids=[queue["review_id"]],
            unit_id="",
            reason_code=queue["reason"]["code"],
            allowed_actions=queue["allowed_actions"],
            terminal_digest=queue["terminal_escalation_sha256"],
        )
    )
    return rows


def _base_row(
    *,
    surface: str,
    candidate_id: str,
    case_id: str,
    review_ids: list[str],
    unit_id: str,
    reason_code: str,
    allowed_actions: list[str],
    terminal_digest: str,
) -> dict[str, str]:
    return {
        "surface": surface,
        "candidate_id": candidate_id,
        "case_id": case_id,
        "review_ids_json": json.dumps(review_ids, separators=(",", ":")),
        "unit_id": unit_id,
        "reason_code": reason_code,
        "allowed_actions": "|".join(allowed_actions),
        "terminal_escalation_sha256": terminal_digest,
        "adjudication_group": "",
        "final_disposition": "",
        "adjudication_notes": "",
        "drop_or_exclusion_reason": "",
        "finalized_units_json": "",
        "decision_status": "pending",
    }


def _tsv(rows: list[dict[str, str]]) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(rows[0]), delimiter="\t")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def _packet() -> JsonRecord:
    unit_items = [
        _unit_item("review-1", "unit-1"),
        _unit_item("review-2", "unit-2"),
    ]
    raw = {"prediction_units": [_unit("unit-1"), _unit("unit-2")]}
    bundles = [
        {"review_id": item["review_id"], "raw_prediction_units": deepcopy(raw)}
        for item in unit_items
    ]
    return {
        "schema_version": "legalforecast.successor_attorney_packet_view.v2",
        "candidates": [
            {
                "candidate_id": "candidate-1",
                "case_id": "case-1",
                "authoritative_v1": {"bundle_records": bundles},
                "observational_v2": {"unit_items": unit_items},
            },
            {
                "candidate_id": "candidate-terminal",
                "case_id": "case-terminal",
                "unitizer_terminal": {
                    "queue_record": {
                        "review_id": "terminal-review",
                        "reason": {"code": "unitizer_terminal_reconstruction_failure"},
                        "allowed_actions": ["ADD", "CANDIDATE-EXCLUSION"],
                        "terminal_escalation_sha256": "e" * 64,
                    }
                },
            },
        ],
    }


def _unit_item(review_id: str, unit_id: str) -> JsonRecord:
    return {
        "review_id": review_id,
        "source_review_ids": [review_id],
        "unit_id": unit_id,
        "reason": {"code": "structural_mis_split"},
        "allowed_actions": [
            "ACCEPT",
            "AMEND",
            "SPLIT",
            "MERGE",
            "DROP",
            "CANDIDATE-EXCLUSION",
        ],
    }


def _unit(unit_id: str) -> JsonRecord:
    return {
        "unit_id": unit_id,
        "claim_name": "Example claim",
        "defendant_group": "Example defendant",
        "defendants": ["Example defendant"],
        "defendant_grouping": "individual",
        "capacity": "entity",
        "claim_category": "other",
        "claim_authority": "Example law",
        "count_label": "Count I",
        "challenge_scope": "entire_claim",
        "challenged_portion": None,
        "separable_subclaim": None,
        "should_score": True,
        "do_not_score_reason": None,
        "confidence": "high",
        "source_citations": [
            {
                "source_document_id": "complaint",
                "document_role": "complaint",
                "page": 1,
                "line_start": 1,
                "line_end": 1,
                "excerpt": "Count I",
            }
        ],
    }
