"""Plan docket-history refreshes for authenticated opinion-backed gaps.

This module is deliberately provider-free.  It consumes exclusion records that
an upstream verifier has already classified and authenticated, and produces a
budget projection only.  It cannot make a candidate packet-eligible, identify
documents to purchase, acknowledge fees, or execute a refresh.
"""

from __future__ import annotations

import hashlib
import json
import re
import urllib.parse
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, cast

OPINION_DOCKET_GAP_REASON = "opinion_backed_docket_history_incomplete"
OPINION_DOCKET_GAP_PLAN_SCHEMA_VERSION = "legalforecast.opinion_docket_gap_plan.v1"
VALIDATED_PUBLIC_OPINION_SCHEMA_VERSION = "legalforecast.validated_public_opinion.v1"

_CANDIDATE_PREFIX = "courtlistener-docket-"
_SHA256 = re.compile(r"[0-9a-f]{64}")


class OpinionDocketGapPlanningError(ValueError):
    """Raised when an asserted opinion-backed docket gap is contradictory."""


@dataclass(frozen=True, slots=True)
class OpinionDocketGapPlanItem:
    """One non-executable reservation for a docket-history-only refresh."""

    candidate_id: str
    docket_id: str
    decision_date: str
    courtlistener_cluster_id: str
    courtlistener_opinion_id: str
    public_decision_url: str
    opinion_plain_text_sha256: str
    disposition_excerpt_sha256: str
    opinion_disposition_evidence_sha256: str
    eligibility_anchor: str
    decision_window_end: str | None
    reservation_usd: str

    def to_record(self) -> dict[str, object]:
        """Return the narrow public planning record."""

        return {
            "candidate_id": self.candidate_id,
            "docket_id": self.docket_id,
            "decision_date": self.decision_date,
            "courtlistener_cluster_id": self.courtlistener_cluster_id,
            "courtlistener_opinion_id": self.courtlistener_opinion_id,
            "public_decision_url": self.public_decision_url,
            "opinion_plain_text_sha256": self.opinion_plain_text_sha256,
            "disposition_excerpt_sha256": self.disposition_excerpt_sha256,
            "opinion_disposition_evidence_sha256": (
                self.opinion_disposition_evidence_sha256
            ),
            "eligibility_anchor": self.eligibility_anchor,
            "decision_window_end": self.decision_window_end,
            "refresh_scope": "docket_history_only",
            "reservation_usd": self.reservation_usd,
            "packet_eligible": False,
        }


@dataclass(frozen=True, slots=True)
class OpinionDocketGapPlan:
    """Deterministic, non-executable projection for verified docket gaps."""

    source_manifest_sha256: str
    source_cycle_hash: str
    source_batch_id: str
    source_batch_digest: str
    source_exclusions_sha256: str
    cost_per_docket_usd: str
    items: tuple[OpinionDocketGapPlanItem, ...]

    @property
    def candidate_count(self) -> int:
        """Return the number of retained refresh candidates."""

        return len(self.items)

    @property
    def total_projected_cost_usd(self) -> str:
        """Return the exact sum of per-docket reservations."""

        total = Decimal(self.cost_per_docket_usd) * self.candidate_count
        return _money(total)

    def _content_record(self) -> dict[str, object]:
        return {
            "schema_version": OPINION_DOCKET_GAP_PLAN_SCHEMA_VERSION,
            "source_manifest_sha256": self.source_manifest_sha256,
            "source_cycle_hash": self.source_cycle_hash,
            "source_batch_id": self.source_batch_id,
            "source_batch_digest": self.source_batch_digest,
            "source_exclusions_sha256": self.source_exclusions_sha256,
            "cost_per_docket_usd": self.cost_per_docket_usd,
            "candidate_count": self.candidate_count,
            "total_projected_cost_usd": self.total_projected_cost_usd,
            "packet_eligible": False,
            "paid_activity_requested": False,
            "paid_activity_executed": False,
            "items": [item.to_record() for item in self.items],
        }

    @property
    def plan_sha256(self) -> str:
        """Commit to the complete deterministic plan content."""

        return _record_sha256(self._content_record())

    def to_record(self) -> dict[str, object]:
        """Return the complete plan with its self-verifiable commitment."""

        return {**self._content_record(), "plan_sha256": self.plan_sha256}


def plan_opinion_docket_gaps(
    exclusion_records: Iterable[Mapping[str, object]],
    *,
    source_manifest_sha256: str,
    source_cycle_hash: str,
    source_batch_id: str,
    source_batch_digest: str,
    source_exclusions_sha256: str,
    cost_per_docket_usd: Decimal | str,
) -> OpinionDocketGapPlan:
    """Project docket-refresh cost for exact opinion-backed gap exclusions.

    Records with any other exclusion reason are outside this planner and are
    ignored.  A record that claims the exact gap reason is validated strictly:
    it must remain packet-ineligible, prove a completely exhausted RECAP entry
    reconstruction that still lacks target-motion linkage and earliest-written-
    disposition proof, and carry validated public opinion disposition evidence
    whose source binding and source saturation were verified upstream.
    """

    normalized_cost = _cost(cost_per_docket_usd)
    items: list[OpinionDocketGapPlanItem] = []
    seen_candidates: set[str] = set()
    for raw_record in exclusion_records:
        record = cast(Mapping[str, Any], raw_record)
        if not _is_exact_gap_reason(record):
            continue
        item = _plan_item(record, normalized_cost)
        if item.candidate_id in seen_candidates:
            raise OpinionDocketGapPlanningError(
                f"duplicate candidate in opinion docket-gap input: {item.candidate_id}"
            )
        seen_candidates.add(item.candidate_id)
        items.append(item)
    items.sort(
        key=lambda item: (
            item.candidate_id.casefold(),
            item.candidate_id,
        )
    )
    return OpinionDocketGapPlan(
        source_manifest_sha256=_sha256(
            source_manifest_sha256, "source_manifest_sha256"
        ),
        source_cycle_hash=_sha256(source_cycle_hash, "source_cycle_hash"),
        source_batch_id=_lineage_text(source_batch_id, "source_batch_id"),
        source_batch_digest=_sha256(source_batch_digest, "source_batch_digest"),
        source_exclusions_sha256=_sha256(
            source_exclusions_sha256, "source_exclusions_sha256"
        ),
        cost_per_docket_usd=_money(normalized_cost),
        items=tuple(items),
    )


def _is_exact_gap_reason(record: Mapping[str, Any]) -> bool:
    return record.get("reason_code") == OPINION_DOCKET_GAP_REASON


def _plan_item(
    record: Mapping[str, Any],
    cost_per_docket_usd: Decimal,
) -> OpinionDocketGapPlanItem:
    candidate_id = _required_text(record, "candidate_id")
    if not candidate_id.startswith(_CANDIDATE_PREFIX):
        raise OpinionDocketGapPlanningError(
            "candidate_id must use the courtlistener-docket- prefix"
        )
    candidate_docket_id = _positive_identifier(
        candidate_id.removeprefix(_CANDIDATE_PREFIX),
        "candidate_id docket identity",
    )
    docket_id = _positive_identifier(record.get("docket_id"), "docket_id")
    if candidate_docket_id != docket_id:
        raise OpinionDocketGapPlanningError(
            "candidate_id does not match the exclusion docket_id"
        )
    if record.get("packet_eligible") is not False:
        raise OpinionDocketGapPlanningError(
            f"packet_eligible must be false for {candidate_id}"
        )
    if record.get("paid_gap_candidate") is not True:
        raise OpinionDocketGapPlanningError(
            f"paid_gap_candidate must be true for {candidate_id}"
        )
    if record.get("planning_status") != "docket_history_recovery_required":
        raise OpinionDocketGapPlanningError(
            f"planning_status must require docket history recovery for {candidate_id}"
        )
    if record.get("opinion_source_binding_verified") is not True:
        raise OpinionDocketGapPlanningError(
            f"opinion_source_binding_verified must be true for {candidate_id}"
        )
    if record.get("source_batch_complete_saturated") is not True:
        raise OpinionDocketGapPlanningError(
            f"source_batch_complete_saturated must be true for {candidate_id}"
        )
    for optional_reason_field in ("reason", "primary_exclusion_reason"):
        reason_value = record.get(optional_reason_field)
        if reason_value is not None and reason_value != OPINION_DOCKET_GAP_REASON:
            raise OpinionDocketGapPlanningError(
                f"{optional_reason_field} contradicts reason_code for {candidate_id}"
            )

    proof = _required_mapping(record, "reconstruction_proof")
    if _positive_identifier(proof.get("docket_id"), "reconstruction docket_id") != (
        docket_id
    ):
        raise OpinionDocketGapPlanningError(
            "reconstruction docket_id does not match the candidate"
        )
    entry_count = proof.get("entry_count")
    if isinstance(entry_count, bool) or not isinstance(entry_count, int):
        raise OpinionDocketGapPlanningError(
            "reconstruction entry_count must be a nonnegative integer"
        )
    if entry_count < 0:
        raise OpinionDocketGapPlanningError(
            "reconstruction entry_count must be a nonnegative integer"
        )
    if proof.get("cursor_exhausted") is not True or proof.get("complete") is not True:
        raise OpinionDocketGapPlanningError(
            "reconstruction must prove complete cursor exhaustion"
        )
    if record.get("target_motion_linkage_proven") is not False:
        raise OpinionDocketGapPlanningError(
            f"target_motion_linkage_proven must be false for {candidate_id}"
        )
    if record.get("earliest_written_disposition_proven") is not False:
        raise OpinionDocketGapPlanningError(
            f"earliest_written_disposition_proven must be false for {candidate_id}"
        )

    evidence = _required_mapping(record, "opinion_disposition_evidence")
    if evidence.get("schema_version") != VALIDATED_PUBLIC_OPINION_SCHEMA_VERSION:
        raise OpinionDocketGapPlanningError(
            "opinion disposition evidence has an unsupported schema_version"
        )
    _positive_identifier(
        evidence.get("source_opinion_docket_id"),
        "source_opinion_docket_id",
    )
    cluster_id = _positive_identifier(evidence.get("cluster_id"), "cluster_id")
    opinion_id = _positive_identifier(evidence.get("opinion_id"), "opinion_id")
    decision_date = _iso_date(evidence.get("opinion_date"), "opinion_date")
    eligibility_anchor = _iso_date(
        record.get("eligibility_anchor"),
        "eligibility_anchor",
    )
    decision_window_end_value = record.get("decision_window_end")
    decision_window_end = (
        _iso_date(decision_window_end_value, "decision_window_end")
        if decision_window_end_value is not None
        else None
    )
    if decision_date < eligibility_anchor:
        raise OpinionDocketGapPlanningError(
            f"opinion_date predates eligibility_anchor for {candidate_id}"
        )
    if decision_window_end is not None and decision_date > decision_window_end:
        raise OpinionDocketGapPlanningError(
            f"opinion_date exceeds decision_window_end for {candidate_id}"
        )
    public_url = _public_pdf_url(evidence.get("public_pdf_url"))
    plain_text_sha256 = _sha256(evidence.get("plain_text_sha256"), "plain_text_sha256")
    _sha256(evidence.get("cluster_response_sha256"), "cluster_response_sha256")
    _sha256(evidence.get("opinion_response_sha256"), "opinion_response_sha256")
    excerpt = _required_text(evidence, "disposition_excerpt")

    return OpinionDocketGapPlanItem(
        candidate_id=candidate_id,
        docket_id=docket_id,
        decision_date=decision_date,
        courtlistener_cluster_id=cluster_id,
        courtlistener_opinion_id=opinion_id,
        public_decision_url=public_url,
        opinion_plain_text_sha256=plain_text_sha256,
        disposition_excerpt_sha256=hashlib.sha256(excerpt.encode()).hexdigest(),
        opinion_disposition_evidence_sha256=_record_sha256(evidence),
        eligibility_anchor=eligibility_anchor,
        decision_window_end=decision_window_end,
        reservation_usd=_money(cost_per_docket_usd),
    )


def _cost(value: Decimal | str) -> Decimal:
    try:
        parsed = value if isinstance(value, Decimal) else Decimal(value)
    except (InvalidOperation, ValueError) as error:
        raise OpinionDocketGapPlanningError(
            "cost_per_docket_usd must be a positive two-decimal amount"
        ) from error
    if (
        not parsed.is_finite()
        or parsed <= 0
        or parsed != parsed.quantize(Decimal("0.01"))
    ):
        raise OpinionDocketGapPlanningError(
            "cost_per_docket_usd must be a positive two-decimal amount"
        )
    return parsed


def _money(value: Decimal) -> str:
    return f"{value:.2f}"


def _required_mapping(record: Mapping[str, Any], field_name: str) -> Mapping[str, Any]:
    value = record.get(field_name)
    if not isinstance(value, Mapping):
        raise OpinionDocketGapPlanningError(f"{field_name} must be an object")
    return cast(Mapping[str, Any], value)


def _required_text(record: Mapping[str, Any], field_name: str) -> str:
    value = record.get(field_name)
    if not isinstance(value, str) or not value or value != value.strip():
        raise OpinionDocketGapPlanningError(
            f"{field_name} must be a non-empty canonical string"
        )
    return value


def _positive_identifier(value: object, field_name: str) -> str:
    if isinstance(value, bool):
        raise OpinionDocketGapPlanningError(f"{field_name} must be a positive integer")
    normalized = str(value).strip()
    if not normalized.isdecimal() or normalized.startswith("0") or int(normalized) <= 0:
        raise OpinionDocketGapPlanningError(f"{field_name} must be a positive integer")
    return normalized


def _iso_date(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise OpinionDocketGapPlanningError(f"{field_name} must be an ISO date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise OpinionDocketGapPlanningError(
            f"{field_name} must be an ISO date"
        ) from error
    if parsed.isoformat() != value:
        raise OpinionDocketGapPlanningError(f"{field_name} must be an ISO date")
    return value


def _sha256(value: object, field_name: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise OpinionDocketGapPlanningError(
            f"{field_name} must be a lowercase SHA-256 digest"
        )
    return value


def _lineage_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise OpinionDocketGapPlanningError(
            f"{field_name} must be a canonical non-empty string"
        )
    return value


def _public_pdf_url(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise OpinionDocketGapPlanningError(
            "public_pdf_url must be a CourtListener storage PDF"
        )
    parsed = urllib.parse.urlparse(value)
    decoded_path = urllib.parse.unquote(parsed.path)
    try:
        port = parsed.port
    except ValueError as error:
        raise OpinionDocketGapPlanningError(
            "public_pdf_url must be a CourtListener storage PDF"
        ) from error
    if (
        parsed.scheme != "https"
        or parsed.hostname != "storage.courtlistener.com"
        or "\\" in value
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or parsed.query
        or parsed.fragment
        or parsed.params
        or decoded_path != parsed.path
        or "%" in parsed.path
        or any(character.isspace() or ord(character) < 32 for character in value)
        or any(segment in {"", ".", ".."} for segment in parsed.path.split("/")[1:])
        or not parsed.path.casefold().endswith(".pdf")
    ):
        raise OpinionDocketGapPlanningError(
            "public_pdf_url must be a CourtListener storage PDF"
        )
    return value


def _record_sha256(record: Mapping[str, object]) -> str:
    payload = json.dumps(
        record,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode()
    return hashlib.sha256(payload).hexdigest()
