"""Provider-free projection of five cases from a full approved repair plan."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import cast

from legalforecast.contracts import (
    ARTIFACT_RAW_SHA256_V1,
    EXACT100_DOCUMENT_REPAIR_PILOT_V2,
    EXACT100_MISSING_DOCUMENT_ACQUISITION_PLAN_V2,
)
from legalforecast.ingestion.missing_document_successor import (
    MissingDocumentAcquisitionItem,
    MissingDocumentAcquisitionPlan,
)

SCHEMA_VERSION = str(EXACT100_DOCUMENT_REPAIR_PILOT_V2)
PILOT_CASE_COUNT = 5


class DocumentRepairPilotError(ValueError):
    """Raised when a five-case pilot is outside its approved full plan."""


@dataclass(frozen=True, slots=True)
class DocumentRepairPilot:
    """Exact five-case scope for a later authenticated executor."""

    full_plan_sha256: str
    manifest_sha256: str
    candidate_ids: tuple[str, ...]
    pilot_maximum_usd: Decimal
    items: tuple[MissingDocumentAcquisitionItem, ...]
    pilot_sha256: str
    provider_activity_requested: bool = False
    provider_activity_executed: bool = False
    paid_activity_requested: bool = False
    paid_activity_executed: bool = False

    @property
    def projected_paid_cost_usd(self) -> Decimal:
        return sum((item.projected_cost_usd for item in self.items), Decimal("0.00"))

    def content_record(self) -> dict[str, object]:
        return {
            "schema_version": SCHEMA_VERSION,
            "full_plan_sha256": self.full_plan_sha256,
            "manifest_sha256": self.manifest_sha256,
            "candidate_ids": list(self.candidate_ids),
            "pilot_maximum_usd": _money(self.pilot_maximum_usd),
            "projected_paid_cost_usd": _money(self.projected_paid_cost_usd),
            "items": [item.to_record() for item in self.items],
            "provider_activity_requested": self.provider_activity_requested,
            "provider_activity_executed": self.provider_activity_executed,
            "paid_activity_requested": self.paid_activity_requested,
            "paid_activity_executed": self.paid_activity_executed,
        }

    def to_record(self) -> dict[str, object]:
        return {**self.content_record(), "pilot_sha256": self.pilot_sha256}


def build_document_repair_pilot(
    *,
    full_plan: MissingDocumentAcquisitionPlan,
    candidate_ids: tuple[str, ...],
    pilot_maximum_usd: Decimal | str,
    approved_manifest_bytes: bytes | None = None,
) -> DocumentRepairPilot:
    """Project five candidate IDs without changing the approved manifest."""

    _require_untampered_full_plan(full_plan)
    if len(candidate_ids) != PILOT_CASE_COUNT or len(set(candidate_ids)) != len(
        candidate_ids
    ):
        raise DocumentRepairPilotError("pilot requires exactly five unique candidates")
    if any(not candidate_id.strip() for candidate_id in candidate_ids):
        raise DocumentRepairPilotError("pilot candidate ID must be nonempty")
    maximum = _positive_money(pilot_maximum_usd, "pilot maximum")
    plan_candidates = {item.candidate_id for item in full_plan.items}
    outside = set(candidate_ids) - plan_candidates
    if outside:
        keep_ids = _keep_candidate_ids(
            approved_manifest_bytes, full_plan.manifest_sha256
        )
        if not outside <= keep_ids:
            raise DocumentRepairPilotError("pilot candidate is outside the full plan")
    selected = set(candidate_ids)
    items = tuple(item for item in full_plan.items if item.candidate_id in selected)
    projected = sum((item.projected_cost_usd for item in items), Decimal("0.00"))
    if projected > maximum:
        raise DocumentRepairPilotError("pilot projected cost exceeds pilot maximum")
    provisional = DocumentRepairPilot(
        full_plan_sha256=full_plan.plan_sha256,
        manifest_sha256=full_plan.manifest_sha256,
        candidate_ids=candidate_ids,
        pilot_maximum_usd=maximum,
        items=items,
        pilot_sha256="",
    )
    return DocumentRepairPilot(
        full_plan_sha256=provisional.full_plan_sha256,
        manifest_sha256=provisional.manifest_sha256,
        candidate_ids=provisional.candidate_ids,
        pilot_maximum_usd=provisional.pilot_maximum_usd,
        items=provisional.items,
        pilot_sha256=str(
            ARTIFACT_RAW_SHA256_V1.commit(
                provisional.content_record(), domain=EXACT100_DOCUMENT_REPAIR_PILOT_V2
            ).digest
        ),
    )


def _keep_candidate_ids(
    manifest_bytes: bytes | None, expected_manifest_sha256: str
) -> frozenset[str]:
    """Admit keep rows from the exact approved sidecar, not a subset manifest."""

    if manifest_bytes is None:
        return frozenset()
    digest = hashlib.sha256(manifest_bytes).hexdigest()
    if digest != expected_manifest_sha256:
        raise DocumentRepairPilotError(
            "approved manifest digest differs from the full plan"
        )
    if not manifest_bytes.endswith(b"\n"):
        raise DocumentRepairPilotError("approved manifest is invalid JSONL")
    keep: set[str] = set()
    # Producer JSONL is LF-terminated. Split only on b"\n" so CR/VT/FF/NEL
    # cannot invent extra keep rows from the same authenticated bytes.
    for line in manifest_bytes.split(b"\n")[:-1]:
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError as exc:
            raise DocumentRepairPilotError(
                "approved manifest is invalid JSONL"
            ) from exc
        if not isinstance(parsed, dict):
            raise DocumentRepairPilotError("approved manifest row is invalid")
        record = cast(Mapping[str, object], parsed)
        candidate_id = record.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id.strip():
            raise DocumentRepairPilotError("approved manifest candidate ID is invalid")
        if record.get("recommendation") != "keep":
            continue
        missing = record.get("missing_docs")
        if missing in (None, []):
            keep.add(candidate_id)
            continue
        raise DocumentRepairPilotError("keep row contains repair obligations")
    return frozenset(keep)


def _require_untampered_full_plan(plan: MissingDocumentAcquisitionPlan) -> None:
    if type(plan) is not MissingDocumentAcquisitionPlan:
        raise DocumentRepairPilotError("full plan is not verified")
    digest = str(
        ARTIFACT_RAW_SHA256_V1.commit(
            plan.content_record(),
            domain=EXACT100_MISSING_DOCUMENT_ACQUISITION_PLAN_V2,
        ).digest
    )
    if digest != plan.plan_sha256:
        raise DocumentRepairPilotError("full plan changed after approval")


def _positive_money(value: Decimal | str, label: str) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise DocumentRepairPilotError(f"{label} is invalid") from exc
    if (
        not amount.is_finite()
        or amount <= 0
        or amount != amount.quantize(Decimal("0.01"))
    ):
        raise DocumentRepairPilotError(f"{label} is invalid")
    return amount


def _money(value: Decimal) -> str:
    return f"{value:.2f}"
