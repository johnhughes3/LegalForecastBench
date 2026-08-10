"""Read-only Stage A adjudication preflight worklist and matrix.

This module rehearses ``apply_unitization_reviews`` over proposed
adjudications without writing any artifact.  Authentication is delegated
entirely to the frozen applicator and verifier — this module adds no gate,
relaxes no invariant, and derives every worklist fact from the applicator's
own validated output so the preflight can never disagree with apply.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from legalforecast.contracts.schemas import (
    UNITIZATION_ADJUDICATION_PREFLIGHT_REPORT_V1,
)
from legalforecast.unitization.review import (
    UnitizationDisposition,
    _adjudication_review_ids,  # pyright: ignore[reportPrivateUsage]
    apply_unitization_reviews,
    canonical_records_sha256,
    canonical_sha256,
    verify_finalized_prediction_units,
)
from legalforecast.unitization.schemas import ChallengeScope, DefendantGrouping

JsonRecord = dict[str, Any]

ADJUDICATION_PREFLIGHT_REPORT_SCHEMA_VERSION = str(
    UNITIZATION_ADJUDICATION_PREFLIGHT_REPORT_V1
)
_AUTOMATIC_ADJUDICATION_PREFIX = "automatic:"


class AdjudicationPreflightError(ValueError):
    """Raised when a provided finalized artifact diverges from recomputation."""


@dataclass(frozen=True, slots=True)
class AdjudicationPreflightResult:
    """Preflight report plus the recomputed finalized records it summarizes.

    The recomputed records are returned so a caller can run downstream
    checks that apply also runs (for example v4 citation validation)
    without invoking the applicator a second time.
    """

    report: JsonRecord
    recomputed_finalized_records: tuple[JsonRecord, ...]


def build_adjudication_preflight_report(
    *,
    prediction_unit_records: Sequence[Mapping[str, Any]],
    review_records: Sequence[Mapping[str, Any]],
    adjudication_records: Sequence[Mapping[str, Any]],
    finalized_records: Sequence[Mapping[str, Any]] | None = None,
    input_commitments: Mapping[str, Mapping[str, Any]],
) -> AdjudicationPreflightResult:
    """Authenticate proposed adjudications and build the private worklist.

    Raises ``UnitizationReviewError`` exactly where apply would, and
    ``AdjudicationPreflightError`` when an optional finalized artifact does
    not equal the recomputation.
    """

    raw_records = tuple(dict(record) for record in prediction_unit_records)
    reviews = tuple(dict(record) for record in review_records)
    adjudications = tuple(dict(record) for record in adjudication_records)
    recomputed = apply_unitization_reviews(
        prediction_unit_records=raw_records,
        review_records=reviews,
        adjudication_records=adjudications,
    )
    finalized_artifact: JsonRecord | None = None
    if finalized_records is not None:
        provided = tuple(dict(record) for record in finalized_records)
        # Verify the provided artifact independently of the recomputation so
        # a broken artifact is reported as its own hash-chain failure, not as
        # a bare mismatch against the proposal.
        verify_finalized_prediction_units(provided, raw_records, adjudications, reviews)
        provided_sha256 = canonical_records_sha256(provided)
        recomputed_sha256 = canonical_records_sha256(recomputed)
        if provided_sha256 != recomputed_sha256:
            raise AdjudicationPreflightError(
                "finalized artifact does not match the adjudication "
                f"recomputation: {provided_sha256} != {recomputed_sha256}"
            )
        finalized_artifact = {
            "canonical_records_sha256": provided_sha256,
            "matches_recomputation": True,
        }

    reviews_by_id = {str(review["review_id"]): review for review in reviews}
    finalized_by_candidate = {
        str(record["candidate_id"]): record for record in recomputed
    }
    candidates: list[JsonRecord] = []
    for raw_record in sorted(
        raw_records, key=lambda record: str(record["candidate_id"])
    ):
        candidate_id = str(raw_record["candidate_id"])
        candidates.append(
            _candidate_report(
                candidate_id=candidate_id,
                raw_record=raw_record,
                finalized_record=finalized_by_candidate[candidate_id],
                reviews_by_id=reviews_by_id,
                adjudications=adjudications,
            )
        )

    report: JsonRecord = {
        "schema_version": ADJUDICATION_PREFLIGHT_REPORT_SCHEMA_VERSION,
        "provider_free": True,
        "read_only": True,
        "creates_adjudications": False,
        "input_commitments": {
            label: dict(commitment)
            for label, commitment in sorted(input_commitments.items())
        },
        "totals": _totals(
            candidates,
            review_count=len(reviews),
            adjudication_count=len(adjudications),
        ),
        "candidates": candidates,
        "finalized_artifact": finalized_artifact,
    }
    return AdjudicationPreflightResult(
        report=report, recomputed_finalized_records=recomputed
    )


def _candidate_report(
    *,
    candidate_id: str,
    raw_record: Mapping[str, Any],
    finalized_record: Mapping[str, Any],
    reviews_by_id: Mapping[str, Mapping[str, Any]],
    adjudications: Sequence[Mapping[str, Any]],
) -> JsonRecord:
    raw_units = [dict(unit) for unit in raw_record["prediction_units"]]
    raw_hash_to_unit_id = {
        canonical_sha256(unit): str(unit["unit_id"]) for unit in raw_units
    }
    status = str(finalized_record["status"])
    excluded = status == "candidate_excluded"
    final_units = [dict(unit) for unit in finalized_record["prediction_units"]]
    dropped_rows = [dict(row) for row in finalized_record.get("dropped_units", ())]
    added_rows = [dict(row) for row in finalized_record.get("added_units", ())]

    before = _side_summary(raw_units)
    after = _side_summary(final_units)
    automatic_accept_unit_ids = sorted(
        str(unit["unit_id"])
        for unit in final_units
        if str(unit["adjudication_id"]).startswith(_AUTOMATIC_ADJUDICATION_PREFIX)
    )
    worklist = _worklist(
        candidate_id=candidate_id,
        raw_hash_to_unit_id=raw_hash_to_unit_id,
        raw_unit_ids=[str(unit["unit_id"]) for unit in raw_units],
        finalized_record=finalized_record,
        final_units=final_units,
        dropped_rows=dropped_rows,
        added_rows=added_rows,
        reviews_by_id=reviews_by_id,
        adjudications=adjudications,
    )
    return {
        "candidate_id": candidate_id,
        "case_id": str(raw_record["case_id"]),
        "status": status,
        "before_unit_count": len(raw_units),
        "after_unit_count": len(final_units),
        "added_unit_ids": sorted(str(row["unit_id"]) for row in added_rows),
        "dropped_unit_ids": sorted(str(row["unit_id"]) for row in dropped_rows),
        "automatic_accept_unit_ids": automatic_accept_unit_ids,
        "unclear_unit_ids_before": before["unclear_unit_ids"],
        "unclear_unit_ids_after": after["unclear_unit_ids"],
        "nonmovant_unit_ids_before": before["nonmovant_unit_ids"],
        "nonmovant_unit_ids_after": after["nonmovant_unit_ids"],
        "nonconforming_unit_ids_before": before["nonconforming_unit_ids"],
        "nonconforming_unit_ids_after": after["nonconforming_unit_ids"],
        "duplicate_claim_defendant_keys_before": before["duplicate_keys"],
        "duplicate_claim_defendant_keys_after": after["duplicate_keys"],
        "excluded": excluded,
        "worklist": worklist,
        "matrix": _matrix(raw_units, final_units),
    }


def _worklist(
    *,
    candidate_id: str,
    raw_hash_to_unit_id: Mapping[str, str],
    raw_unit_ids: Sequence[str],
    finalized_record: Mapping[str, Any],
    final_units: Sequence[Mapping[str, Any]],
    dropped_rows: Sequence[Mapping[str, Any]],
    added_rows: Sequence[Mapping[str, Any]],
    reviews_by_id: Mapping[str, Mapping[str, Any]],
    adjudications: Sequence[Mapping[str, Any]],
) -> list[JsonRecord]:
    """Group the candidate's reviews by the adjudication that resolves them.

    Source and emitted units come from the applicator's validated
    provenance (source hashes mapped back through the raw units, dropped
    and added ledgers, and the exclusion object) rather than from a second
    reading of the adjudication rows, so the worklist cannot drift from
    what apply actually did.
    """

    emitted_by_adjudication: dict[str, list[str]] = {}
    sources_by_adjudication: dict[str, list[str]] = {}
    for unit in final_units:
        adjudication_id = str(unit["adjudication_id"])
        if adjudication_id.startswith(_AUTOMATIC_ADJUDICATION_PREFIX):
            continue
        unit_id = str(unit["unit_id"])
        emitted_by_adjudication.setdefault(adjudication_id, []).append(unit_id)
        source_ids = [
            raw_hash_to_unit_id[source_sha256]
            for source_sha256 in unit.get("source_unit_sha256s", ())
            if source_sha256 in raw_hash_to_unit_id
        ]
        existing = sources_by_adjudication.setdefault(adjudication_id, [])
        for source_id in source_ids:
            if source_id not in existing:
                existing.append(source_id)
    for dropped_row in dropped_rows:
        sources_by_adjudication.setdefault(
            str(dropped_row["adjudication_id"]), []
        ).append(str(dropped_row["unit_id"]))
    exclusion = finalized_record.get("exclusion")
    if isinstance(exclusion, Mapping):
        # CANDIDATE-EXCLUSION consumes every raw unit; the exclusion object
        # only names the adjudication, so the sources are the whole side.
        exclusion_record = cast(Mapping[str, Any], exclusion)
        sources_by_adjudication.setdefault(
            str(exclusion_record["adjudication_id"]), list(raw_unit_ids)
        )
    added_by_adjudication = {
        str(row["adjudication_id"]): str(row["unit_id"]) for row in added_rows
    }

    rows: list[JsonRecord] = []
    for adjudication in adjudications:
        if str(adjudication["candidate_id"]) != candidate_id:
            continue
        adjudication_id = str(adjudication["adjudication_id"])
        review_ids = list(_adjudication_review_ids(adjudication))
        reviewed_unit_ids: list[str] = []
        route_reasons: set[str] = set()
        for review_id in review_ids:
            review = reviews_by_id[review_id]
            # Apply only validates unit_id on reviews consumed by unit-level
            # dispositions; an ADD-consumed omission row names a neighbour
            # unit and may in principle omit the field, so read defensively.
            reviewed_unit_id = review.get("unit_id")
            if (
                isinstance(reviewed_unit_id, str)
                and reviewed_unit_id.strip()
                and reviewed_unit_id not in reviewed_unit_ids
            ):
                reviewed_unit_ids.append(reviewed_unit_id)
            route_reason = review.get("route_reason")
            if isinstance(route_reason, str) and route_reason.strip():
                route_reasons.add(route_reason)
        disposition = str(adjudication["disposition"]).upper()
        row: JsonRecord = {
            "adjudication_id": adjudication_id,
            "disposition": disposition,
            "adjudicator_id": str(adjudication["adjudicator_id"]),
            "review_ids": review_ids,
            "reviewed_unit_ids": reviewed_unit_ids,
            "route_reasons": sorted(route_reasons),
            "source_unit_ids": sources_by_adjudication.get(adjudication_id, []),
            "emitted_unit_ids": sorted(
                emitted_by_adjudication.get(adjudication_id, [])
            ),
        }
        if disposition == UnitizationDisposition.DROP.value:
            row["drop_reason"] = str(adjudication["drop_reason"])
        if disposition == UnitizationDisposition.CANDIDATE_EXCLUSION.value:
            row["exclusion_reason"] = str(adjudication["exclusion_reason"])
        if disposition == UnitizationDisposition.ADD.value:
            added_unit_id = added_by_adjudication[adjudication_id]
            row["emitted_unit_ids"] = [added_unit_id]
            for unit in final_units:
                if str(unit["unit_id"]) == added_unit_id:
                    row["structural_flag_sha256"] = str(unit["structural_flag_sha256"])
                    break
        rows.append(row)
    rows.sort(key=lambda row: str(row["adjudication_id"]))
    return rows


def _side_summary(units: Sequence[Mapping[str, Any]]) -> JsonRecord:
    unclear: list[str] = []
    nonmovant: list[str] = []
    nonconforming: list[str] = []
    by_key: dict[tuple[str, str], list[str]] = {}
    for unit in units:
        unit_id = str(unit["unit_id"])
        classified = _classify_unit(unit)
        if classified is None:
            nonconforming.append(unit_id)
            continue
        if classified["challenge_scope"] == ChallengeScope.UNCLEAR.value:
            unclear.append(unit_id)
        if classified["challenged_by_motion"] is False:
            nonmovant.append(unit_id)
        key = (classified["claim_name"], classified["defendant_group"])
        by_key.setdefault(key, []).append(unit_id)
    duplicate_keys = [
        {
            "claim_name": claim_name,
            "defendant_group": defendant_group,
            "unit_ids": sorted(unit_ids),
        }
        for (claim_name, defendant_group), unit_ids in sorted(by_key.items())
        if len(unit_ids) > 1
    ]
    return {
        "unclear_unit_ids": sorted(unclear),
        "nonmovant_unit_ids": sorted(nonmovant),
        "nonconforming_unit_ids": sorted(nonconforming),
        "duplicate_keys": duplicate_keys,
    }


def _matrix(
    raw_units: Sequence[Mapping[str, Any]],
    final_units: Sequence[Mapping[str, Any]],
) -> list[JsonRecord]:
    """Claim-defendant matrix over conforming units, before and after.

    The v4 ontology folds movant capacity into ``defendant_group``, so the
    matrix key is (claim_name, defendant_group); nonconforming units are
    listed separately by the side summaries instead of being forced into a
    fabricated cell.
    """

    before_by_key: dict[tuple[str, str], list[JsonRecord]] = {}
    after_by_key: dict[tuple[str, str], list[JsonRecord]] = {}
    for unit in raw_units:
        classified = _classify_unit(unit)
        if classified is None:
            continue
        before_by_key.setdefault(_matrix_key(classified), []).append(
            _matrix_unit(unit, classified)
        )
    for unit in final_units:
        classified = _classify_unit(unit)
        if classified is None:
            continue
        entry = _matrix_unit(unit, classified)
        entry["disposition"] = _unit_disposition(unit)
        after_by_key.setdefault(_matrix_key(classified), []).append(entry)
    return [
        {
            "claim_name": claim_name,
            "defendant_group": defendant_group,
            "before_units": sorted(
                before_by_key.get((claim_name, defendant_group), []),
                key=_entry_unit_id,
            ),
            "after_units": sorted(
                after_by_key.get((claim_name, defendant_group), []),
                key=_entry_unit_id,
            ),
        }
        for claim_name, defendant_group in sorted(
            set(before_by_key) | set(after_by_key)
        )
    ]


def _matrix_key(classified: Mapping[str, Any]) -> tuple[str, str]:
    return (str(classified["claim_name"]), str(classified["defendant_group"]))


def _entry_unit_id(entry: Mapping[str, Any]) -> str:
    return str(entry["unit_id"])


def _matrix_unit(unit: Mapping[str, Any], classified: Mapping[str, Any]) -> JsonRecord:
    return {
        "unit_id": str(unit["unit_id"]),
        "challenge_scope": classified["challenge_scope"],
        "challenged_by_motion": classified["challenged_by_motion"],
        "grouping": classified["grouping"],
        "should_score": classified["should_score"],
    }


def _unit_disposition(unit: Mapping[str, Any]) -> str:
    adjudication_id = str(unit["adjudication_id"])
    if adjudication_id.startswith(_AUTOMATIC_ADJUDICATION_PREFIX):
        return "automatic-accept"
    return str(unit["disposition"])


def _classify_unit(unit: Mapping[str, Any]) -> JsonRecord | None:
    """Return matrix fields, or None for a non-canonical unit shape.

    Apply deliberately accepts AMEND/SPLIT/MERGE outputs without imposing
    the canonical prediction-unit shape, so the preflight observes rather
    than gates: a unit missing well-formed matrix fields is reported as
    nonconforming instead of failing the run.
    """

    claim_name = unit.get("claim_name")
    defendant_group = unit.get("defendant_group")
    challenge_scope = unit.get("challenge_scope")
    challenged_by_motion = unit.get("challenged_by_motion")
    grouping = unit.get("grouping", DefendantGrouping.INDIVIDUAL.value)
    if not isinstance(claim_name, str) or not claim_name.strip():
        return None
    if not isinstance(defendant_group, str) or not defendant_group.strip():
        return None
    if not isinstance(challenge_scope, str) or challenge_scope not in {
        scope.value for scope in ChallengeScope
    }:
        return None
    if not isinstance(challenged_by_motion, bool):
        return None
    if not isinstance(grouping, str) or grouping not in {
        value.value for value in DefendantGrouping
    }:
        return None
    return {
        "claim_name": claim_name,
        "defendant_group": defendant_group,
        "challenge_scope": challenge_scope,
        "challenged_by_motion": challenged_by_motion,
        "grouping": grouping,
        "should_score": (
            challenged_by_motion and challenge_scope != ChallengeScope.UNCLEAR.value
        ),
    }


def _totals(
    candidates: Sequence[Mapping[str, Any]],
    *,
    review_count: int,
    adjudication_count: int,
) -> JsonRecord:
    def total(field: str) -> int:
        return sum(len(candidate[field]) for candidate in candidates)

    return {
        "candidate_count": len(candidates),
        "review_count": review_count,
        "adjudication_count": adjudication_count,
        "excluded_candidate_count": sum(
            1 for candidate in candidates if candidate["excluded"]
        ),
        "before_unit_count": sum(
            int(candidate["before_unit_count"]) for candidate in candidates
        ),
        "after_unit_count": sum(
            int(candidate["after_unit_count"]) for candidate in candidates
        ),
        "added_unit_count": total("added_unit_ids"),
        "dropped_unit_count": total("dropped_unit_ids"),
        "unclear_unit_count_before": total("unclear_unit_ids_before"),
        "unclear_unit_count_after": total("unclear_unit_ids_after"),
        "nonmovant_unit_count_before": total("nonmovant_unit_ids_before"),
        "nonmovant_unit_count_after": total("nonmovant_unit_ids_after"),
        "nonconforming_unit_count_before": total("nonconforming_unit_ids_before"),
        "nonconforming_unit_count_after": total("nonconforming_unit_ids_after"),
        "duplicate_claim_defendant_key_count_before": total(
            "duplicate_claim_defendant_keys_before"
        ),
        "duplicate_claim_defendant_key_count_after": total(
            "duplicate_claim_defendant_keys_after"
        ),
    }
