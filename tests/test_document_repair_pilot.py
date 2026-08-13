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
    build_missing_document_acquisition_plan,
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
    return build_missing_document_acquisition_plan(
        manifest_bytes=manifest,
        approved_manifest_sha256=hashlib.sha256(manifest).hexdigest(),
        approved_maximum_usd="453.00",
    )


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
