"""Provider-free scope tests for the five-case repair pilot."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from decimal import Decimal

import pytest
from legalforecast.ingestion.document_repair_pilot import (
    DocumentRepairPilotError,
    build_document_repair_pilot,
)
from legalforecast.ingestion.missing_document_successor import (
    MissingDocumentSuccessorError,
    build_missing_document_acquisition_plan,
    verify_repair_plan_approval,
)


def _manifest_bytes(*records: Mapping[str, object]) -> bytes:
    return b"".join(
        json.dumps(record, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        for record in records
    )


def _row(candidate_id: str, costs: tuple[int, ...]) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "recommendation": "repair",
        "cost_usd": float(sum(costs)),
        "missing_docs": [
            {
                "entry": index,
                "role": "reply",
                "cost_usd": float(cost),
                "free_document_count": int(cost == 0),
                "pacer_only_document_count": int(cost != 0),
                "evidence": "synthetic pilot fixture",
                "source": "pass1",
                "opinion_derived": False,
            }
            for index, cost in enumerate(costs, start=1)
        ],
        "byte_mismatches": [],
        "current_selection": [],
        "required_entries": [],
        "extra_selected": [],
    }


def _plan(manifest: bytes):  # type: ignore[no-untyped-def]
    rows = [json.loads(line) for line in manifest.splitlines()]
    return build_missing_document_acquisition_plan(
        manifest_bytes=manifest,
        approval=verify_repair_plan_approval(manifest, _approval(rows, manifest)),
    )


def _approval(rows: list[dict[str, object]], manifest: bytes) -> dict[str, object]:
    return {
        "schema_version": "legalforecast.repair_manifest_approval.v2",
        "decision": "approve",
        "manifest_sha256": hashlib.sha256(manifest).hexdigest(),
        "maximum_cost_usd": "453.00",
        "max_per_document_usd": "3.00",
        "candidate_count": len(rows),
        "repair_count": sum(row["recommendation"] == "repair" for row in rows),
        "keep_count": sum(row["recommendation"] == "keep" for row in rows),
        "replace_count": sum(row["recommendation"] == "replace" for row in rows),
        "missing_slot_count": sum(len(row["missing_docs"]) for row in rows),
    }


def test_pilot_is_bound_to_full_plan_and_exact_five_case_scope() -> None:
    manifest = _manifest_bytes(
        _row("a", (3, 0)),
        _row("b", (3,)),
        _row("c", (0,)),
        _row("d", (3, 3)),
        _row("e", (3,)),
        _row("outside", (3,)),
    )
    plan = _plan(manifest)

    pilot = build_document_repair_pilot(
        full_plan=plan,
        candidate_ids=("a", "b", "c", "d", "e"),
        pilot_maximum_usd="15.00",
    )

    assert pilot.full_plan_sha256 == plan.plan_sha256
    assert pilot.manifest_sha256 == plan.manifest_sha256
    assert pilot.candidate_ids == ("a", "b", "c", "d", "e")
    assert {item.candidate_id for item in pilot.items} == set(pilot.candidate_ids)
    assert pilot.projected_paid_cost_usd == Decimal("15.00")
    assert [item.acquisition_method for item in pilot.items][:2] == [
        "courtlistener_free",
        "courtlistener_free",
    ]
    assert pilot.paid_activity_requested is False
    assert pilot.paid_activity_executed is False
    assert pilot.provider_activity_requested is False
    assert pilot.provider_activity_executed is False


@pytest.mark.parametrize(
    ("candidate_ids", "maximum", "message"),
    (
        (("a", "b", "c", "d"), "15.00", "exactly five"),
        (("a", "b", "c", "d", "missing"), "15.00", "outside the full plan"),
        (("a", "b", "c", "d", "e"), "12.00", "pilot maximum"),
    ),
)
def test_pilot_refuses_wrong_scope_or_cap(
    candidate_ids: tuple[str, ...], maximum: str, message: str
) -> None:
    manifest = _manifest_bytes(
        _row("a", (3,)),
        _row("b", (3,)),
        _row("c", (3,)),
        _row("d", (3,)),
        _row("e", (3,)),
    )

    with pytest.raises(DocumentRepairPilotError, match=message):
        build_document_repair_pilot(
            full_plan=_plan(manifest),
            candidate_ids=candidate_ids,
            pilot_maximum_usd=maximum,
        )


def test_pilot_admits_keep_candidate_from_approved_manifest() -> None:
    manifest = _manifest_bytes(
        _row("a", (3,)),
        _row("b", (3,)),
        _row("c", (0,)),
        _row("d", (3,)),
        {
            "candidate_id": "kept",
            "recommendation": "keep",
            "cost_usd": 0.0,
            "missing_docs": [],
            "byte_mismatches": [],
            "current_selection": [],
            "required_entries": [],
            "extra_selected": [],
        },
        _row("outside", (3,)),
    )
    plan = _plan(manifest)

    pilot = build_document_repair_pilot(
        full_plan=plan,
        candidate_ids=("a", "b", "c", "d", "kept"),
        pilot_maximum_usd="9.00",
        approved_manifest_bytes=manifest,
    )

    assert pilot.candidate_ids == ("a", "b", "c", "d", "kept")
    assert {item.candidate_id for item in pilot.items} == {"a", "b", "c", "d"}
    assert pilot.projected_paid_cost_usd == Decimal("9.00")


def test_keep_admission_does_not_split_authenticated_jsonl_on_cr() -> None:
    keep_row = {
        "candidate_id": "kept",
        "recommendation": "keep",
        "cost_usd": 0.0,
        "missing_docs": [],
        "byte_mismatches": [],
        "current_selection": [],
        "required_entries": [],
        "extra_selected": [],
    }
    smuggled = {**keep_row, "candidate_id": "smuggled"}
    poisoned = (
        _manifest_bytes(
            _row("a", (3,)),
            _row("b", (3,)),
            _row("c", (3,)),
            _row("d", (3,)),
        )
        + json.dumps(keep_row, sort_keys=True, separators=(",", ":")).encode()
        + b"\r"
        + json.dumps(smuggled, sort_keys=True, separators=(",", ":")).encode()
        + b"\n"
    )
    plan = _plan(poisoned)

    with pytest.raises(DocumentRepairPilotError, match="invalid JSONL"):
        build_document_repair_pilot(
            full_plan=plan,
            candidate_ids=("a", "b", "c", "d", "smuggled"),
            pilot_maximum_usd="12.00",
            approved_manifest_bytes=poisoned,
        )


def test_pilot_rejects_keep_candidate_without_approved_manifest() -> None:
    manifest = _manifest_bytes(
        _row("a", (3,)),
        _row("b", (3,)),
        _row("c", (3,)),
        _row("d", (3,)),
        {
            "candidate_id": "kept",
            "recommendation": "keep",
            "cost_usd": 0.0,
            "missing_docs": [],
            "byte_mismatches": [],
            "current_selection": [],
            "required_entries": [],
            "extra_selected": [],
        },
    )
    with pytest.raises(DocumentRepairPilotError, match="outside the full plan"):
        build_document_repair_pilot(
            full_plan=_plan(manifest),
            candidate_ids=("a", "b", "c", "d", "kept"),
            pilot_maximum_usd="12.00",
        )


def test_pilot_rejects_keep_candidate_when_manifest_digest_differs() -> None:
    manifest = _manifest_bytes(
        _row("a", (3,)),
        _row("b", (3,)),
        _row("c", (3,)),
        _row("d", (3,)),
        {
            "candidate_id": "kept",
            "recommendation": "keep",
            "cost_usd": 0.0,
            "missing_docs": [],
            "byte_mismatches": [],
            "current_selection": [],
            "required_entries": [],
            "extra_selected": [],
        },
    )
    other = _manifest_bytes(_row("a", (3,)))
    with pytest.raises(DocumentRepairPilotError, match="approved manifest digest"):
        build_document_repair_pilot(
            full_plan=_plan(manifest),
            candidate_ids=("a", "b", "c", "d", "kept"),
            pilot_maximum_usd="12.00",
            approved_manifest_bytes=other,
        )


def test_pilot_rejects_keep_candidate_with_repair_obligations() -> None:
    manifest = _manifest_bytes(
        _row("a", (3,)),
        _row("b", (3,)),
        _row("c", (3,)),
        _row("d", (3,)),
        {
            "candidate_id": "kept",
            "recommendation": "keep",
            "cost_usd": 3.0,
            "missing_docs": [
                {
                    "entry": 1,
                    "role": "reply",
                    "cost_usd": 3.0,
                    "free_document_count": 0,
                    "pacer_only_document_count": 1,
                    "evidence": "synthetic pilot fixture",
                    "source": "pass1",
                    "opinion_derived": False,
                }
            ],
            "byte_mismatches": [],
            "current_selection": [],
            "required_entries": [],
            "extra_selected": [],
        },
    )
    with pytest.raises(MissingDocumentSuccessorError, match="keep"):
        _plan(manifest)


def test_pilot_rejects_tampered_full_plan() -> None:
    manifest = _manifest_bytes(*(_row(value, (3,)) for value in "abcde"))
    plan = _plan(manifest)
    object.__setattr__(plan, "plan_sha256", "0" * 64)

    with pytest.raises(DocumentRepairPilotError, match="full plan"):
        build_document_repair_pilot(
            full_plan=plan,
            candidate_ids=tuple("abcde"),
            pilot_maximum_usd="15.00",
        )
