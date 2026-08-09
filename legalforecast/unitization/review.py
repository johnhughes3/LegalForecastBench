"""Apply blinded Stage A review decisions and verify finalized unit artifacts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from enum import StrEnum
from typing import Any, cast

from legalforecast.contracts.schemas import FINALIZED_PREDICTION_UNITS_V2

JsonRecord = dict[str, Any]
LEGACY_FINALIZED_SCHEMA_VERSION = "legalforecast.finalized_prediction_units.v1"
FINALIZED_SCHEMA_VERSION = str(FINALIZED_PREDICTION_UNITS_V2)
SUPPORTED_FINALIZED_SCHEMA_VERSIONS = frozenset(
    {LEGACY_FINALIZED_SCHEMA_VERSION, FINALIZED_SCHEMA_VERSION}
)
ADJUDICATION_SCHEMA_VERSION = "legalforecast.unitization_adjudication.v1"


class UnitizationReviewError(ValueError):
    """Raised when Stage A review artifacts do not form a complete hash chain."""


class UnitizationDisposition(StrEnum):
    """Supported reviewer actions for Stage A prediction units."""

    ACCEPT = "ACCEPT"
    AMEND = "AMEND"
    SPLIT = "SPLIT"
    MERGE = "MERGE"
    DROP = "DROP"
    CANDIDATE_EXCLUSION = "CANDIDATE-EXCLUSION"


def canonical_sha256(record: Mapping[str, Any]) -> str:
    """Hash a JSON object using the repository's canonical compact encoding."""

    payload = json.dumps(
        dict(record), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def canonical_records_sha256(records: Iterable[Mapping[str, Any]]) -> str:
    """Hash an ordered JSON-record sequence using canonical compact encoding."""

    payload = json.dumps(
        [dict(record) for record in records],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def apply_unitization_reviews(
    *,
    prediction_unit_records: Iterable[Mapping[str, Any]],
    review_records: Iterable[Mapping[str, Any]],
    adjudication_records: Iterable[Mapping[str, Any]],
) -> tuple[JsonRecord, ...]:
    """Drain the review queue and emit the only units Stage B may consume."""

    raw_records = tuple(prediction_unit_records)
    reviews = tuple(review_records)
    adjudications = tuple(adjudication_records)
    raw_by_candidate = _unique_by_candidate(raw_records, "raw units")
    reviews_by_id = _unique_by_id(reviews, "review_id", "review")
    adjudications_by_id = _unique_by_id(
        adjudications, "adjudication_id", "adjudication"
    )
    uses_drop_migration = any(
        _required_str(adjudication, "disposition").upper()
        == UnitizationDisposition.DROP.value
        for adjudication in adjudications
    )
    expected_review_ids = set(reviews_by_id)
    review_queue_sha256 = canonical_records_sha256(reviews)
    resolved_review_ids: set[str] = set()
    consumed_adjudication_ids: set[str] = set()
    output: list[JsonRecord] = []

    for candidate_id, raw_record in raw_by_candidate.items():
        case_id = _required_str(raw_record, "case_id")
        raw_units = _record_sequence(
            raw_record.get("prediction_units"), "prediction_units"
        )
        units_by_id = _unique_units(raw_units)
        candidate_reviews = {
            review_id: review
            for review_id, review in reviews_by_id.items()
            if _required_str(review, "candidate_id") == candidate_id
        }
        candidate_adjudications = [
            adjudication
            for adjudication in adjudications_by_id.values()
            if _required_str(adjudication, "candidate_id") == candidate_id
        ]
        current = dict(units_by_id)
        provenance: dict[str, JsonRecord] = {
            unit_id: _automatic_provenance(unit)
            for unit_id, unit in units_by_id.items()
        }
        excluded = False
        exclusion: JsonRecord | None = None
        dropped_units: list[JsonRecord] = []
        adjudicated_source_unit_ids: set[str] = set()

        for adjudication in candidate_adjudications:
            _validate_adjudication_header(adjudication, case_id=case_id)
            adjudication_id = _required_str(adjudication, "adjudication_id")
            disposition = UnitizationDisposition(
                _required_str(adjudication, "disposition").upper()
            )
            review_ids = _string_sequence(adjudication.get("review_ids"), "review_ids")
            if not review_ids:
                review_ids = (_required_str(adjudication, "review_id"),)
            if any(review_id not in candidate_reviews for review_id in review_ids):
                raise UnitizationReviewError(
                    f"{adjudication_id}: adjudication references an unknown review"
                )
            overlap = resolved_review_ids.intersection(review_ids)
            if overlap:
                raise UnitizationReviewError(
                    f"reviews adjudicated more than once: {sorted(overlap)}"
                )
            if len(set(review_ids)) != len(review_ids):
                raise UnitizationReviewError(
                    f"{adjudication_id}: duplicate review_ids are not allowed"
                )
            reviewed_unit_ids = tuple(
                _required_str(candidate_reviews[review_id], "unit_id")
                for review_id in review_ids
            )
            reviewed_source_unit_ids = tuple(dict.fromkeys(reviewed_unit_ids))
            explicit_source_unit_ids = _string_sequence(
                adjudication.get("source_unit_ids"), "source_unit_ids"
            )
            source_unit_ids = (
                explicit_source_unit_ids
                if disposition is UnitizationDisposition.CANDIDATE_EXCLUSION
                else reviewed_source_unit_ids
            )
            if (
                disposition
                in {
                    UnitizationDisposition.DROP,
                    UnitizationDisposition.CANDIDATE_EXCLUSION,
                }
                and not explicit_source_unit_ids
            ):
                raise UnitizationReviewError(
                    f"{adjudication_id}: {disposition.value} requires explicit "
                    "source_unit_ids"
                )
            if len(set(explicit_source_unit_ids)) != len(explicit_source_unit_ids):
                raise UnitizationReviewError(
                    f"{adjudication_id}: source_unit_ids must be unique"
                )
            if disposition is UnitizationDisposition.CANDIDATE_EXCLUSION:
                source_ids_match_reviews = set(reviewed_source_unit_ids).issubset(
                    source_unit_ids
                )
            else:
                source_ids_match_reviews = not explicit_source_unit_ids or set(
                    explicit_source_unit_ids
                ) == set(reviewed_source_unit_ids)
            if not source_ids_match_reviews:
                raise UnitizationReviewError(
                    f"{adjudication_id}: source_unit_ids must include reviewed units"
                )
            reused_source_ids = adjudicated_source_unit_ids.intersection(
                source_unit_ids
            )
            if reused_source_ids:
                raise UnitizationReviewError(
                    f"{adjudication_id}: source units were already adjudicated; "
                    f"coalesce reviews for {sorted(reused_source_ids)}"
                )
            if any(unit_id not in current for unit_id in source_unit_ids):
                raise UnitizationReviewError(
                    f"{adjudication_id}: source unit is missing or already consumed"
                )
            source_hashes = tuple(
                canonical_sha256(_base_unit(current[unit_id]))
                for unit_id in source_unit_ids
            )
            finalized_units = _record_sequence(
                adjudication.get("finalized_units", ()), "finalized_units"
            )
            _validate_disposition_shape(
                disposition,
                source_unit_ids=source_unit_ids,
                finalized_units=finalized_units,
            )
            if disposition is UnitizationDisposition.DROP:
                _required_str(adjudication, "drop_reason")
            if disposition is UnitizationDisposition.CANDIDATE_EXCLUSION and (
                set(source_unit_ids) != set(current)
                or set(review_ids) != set(candidate_reviews)
            ):
                raise UnitizationReviewError(
                    "CANDIDATE-EXCLUSION must consume every unit and pending review"
                )
            adjudication_hash = canonical_sha256(adjudication)
            for unit_id in source_unit_ids:
                current.pop(unit_id)
                provenance.pop(unit_id)
            if disposition is UnitizationDisposition.ACCEPT:
                finalized_units = tuple(
                    units_by_id[unit_id] for unit_id in source_unit_ids
                )
            elif disposition is UnitizationDisposition.CANDIDATE_EXCLUSION:
                excluded = True
                exclusion = {
                    "reason": _required_str(adjudication, "exclusion_reason"),
                    "adjudication_id": adjudication_id,
                    "adjudication_sha256": adjudication_hash,
                }
                current.clear()
                provenance.clear()
            elif disposition is UnitizationDisposition.DROP:
                dropped_units.extend(
                    {
                        "unit_id": unit_id,
                        "source_unit_sha256": source_hash,
                        "adjudication_id": adjudication_id,
                        "adjudication_sha256": adjudication_hash,
                        "disposition": disposition.value,
                    }
                    for unit_id, source_hash in zip(
                        source_unit_ids, source_hashes, strict=True
                    )
                )
            for finalized_unit in finalized_units:
                unit_id = _required_str(finalized_unit, "unit_id")
                if unit_id in current:
                    raise UnitizationReviewError(
                        f"duplicate finalized unit_id: {unit_id}"
                    )
                current[unit_id] = dict(finalized_unit)
                provenance[unit_id] = {
                    "source_unit_sha256s": list(source_hashes),
                    "adjudication_id": adjudication_id,
                    "adjudication_sha256": adjudication_hash,
                    "disposition": disposition.value,
                }
            resolved_review_ids.update(review_ids)
            consumed_adjudication_ids.add(adjudication_id)
            adjudicated_source_unit_ids.update(source_unit_ids)

        unresolved = set(candidate_reviews) - resolved_review_ids
        if unresolved:
            raise UnitizationReviewError(
                f"candidate {candidate_id} has unresolved reviews: {sorted(unresolved)}"
            )
        if not excluded and not current:
            raise UnitizationReviewError(
                f"candidate {candidate_id} must retain at least one unit; "
                "use CANDIDATE-EXCLUSION instead"
            )
        finalized = [
            {**_base_unit(unit), **provenance[unit_id]}
            for unit_id, unit in sorted(current.items())
        ]
        finalized_record: JsonRecord = {
            "schema_version": (
                FINALIZED_SCHEMA_VERSION
                if uses_drop_migration
                else LEGACY_FINALIZED_SCHEMA_VERSION
            ),
            "status": "candidate_excluded" if excluded else "finalized",
            "candidate_id": candidate_id,
            "case_id": case_id,
            "raw_prediction_units_sha256": canonical_sha256(raw_record),
            "unitization_review_queue_sha256": review_queue_sha256,
            "prediction_units": finalized,
            "exclusion": exclusion,
        }
        if uses_drop_migration:
            finalized_record["dropped_units"] = dropped_units
        output.append(finalized_record)

    missing_candidates = {
        _required_str(review, "candidate_id") for review in reviews_by_id.values()
    } - set(raw_by_candidate)
    if missing_candidates:
        raise UnitizationReviewError(
            "reviews reference candidates with no raw units: "
            f"{sorted(missing_candidates)}"
        )
    unconsumed_adjudications = set(adjudications_by_id) - consumed_adjudication_ids
    if unconsumed_adjudications:
        raise UnitizationReviewError(
            f"adjudications were not consumed: {sorted(unconsumed_adjudications)}"
        )
    if resolved_review_ids != expected_review_ids:
        raise UnitizationReviewError("unitization review queue was not fully drained")
    verify_finalized_prediction_units(
        output,
        raw_by_candidate.values(),
        adjudications,
        reviews,
    )
    return tuple(output)


def verify_finalized_prediction_units(
    finalized_records: Iterable[Mapping[str, Any]],
    raw_records: Iterable[Mapping[str, Any]],
    adjudication_records: Iterable[Mapping[str, Any]],
    review_records: Iterable[Mapping[str, Any]],
) -> None:
    """Fail closed unless finalized records reproduce their complete hash chain."""

    raw_materialized = tuple(raw_records)
    adjudication_materialized = tuple(adjudication_records)
    review_materialized = tuple(review_records)
    raw_by_candidate = _unique_by_candidate(raw_materialized, "raw units")
    adjudications = _unique_by_id(
        adjudication_materialized, "adjudication_id", "adjudication"
    )
    reviews = _unique_by_id(review_materialized, "review_id", "review")
    finalized_by_candidate = _unique_by_candidate(finalized_records, "finalized units")
    expected_review_queue_sha256 = canonical_records_sha256(review_materialized)
    _verify_adjudication_review_coverage(
        raw_by_candidate=raw_by_candidate,
        reviews=reviews,
        adjudications=adjudications,
    )
    if set(finalized_by_candidate) != set(raw_by_candidate):
        raise UnitizationReviewError("finalized candidates do not match raw candidates")
    verified_adjudication_ids: set[str] = set()
    for candidate_id, record in finalized_by_candidate.items():
        schema_version = record.get("schema_version")
        if schema_version not in SUPPORTED_FINALIZED_SCHEMA_VERSIONS:
            raise UnitizationReviewError("raw or unsupported prediction-units artifact")
        if schema_version == FINALIZED_SCHEMA_VERSION and "dropped_units" not in record:
            raise UnitizationReviewError("v2 finalized schema requires dropped_units")
        raw = raw_by_candidate[candidate_id]
        if record.get("raw_prediction_units_sha256") != canonical_sha256(raw):
            raise UnitizationReviewError(f"broken raw-unit hash link: {candidate_id}")
        if (
            record.get("unitization_review_queue_sha256")
            != expected_review_queue_sha256
        ):
            raise UnitizationReviewError(
                f"broken unitization-review-queue hash link: {candidate_id}"
            )
        raw_units = _unique_units(
            _record_sequence(raw.get("prediction_units"), "prediction_units")
        )
        raw_hashes = {canonical_sha256(unit) for unit in raw_units.values()}
        status = record.get("status")
        _required_str(record, "unitization_review_queue_sha256")
        units = _record_sequence(record.get("prediction_units"), "prediction_units")
        finalized_units_by_id = _unique_units(units)
        dropped_units = _record_sequence(
            record.get("dropped_units", ()), "dropped_units"
        )
        if schema_version == LEGACY_FINALIZED_SCHEMA_VERSION and (
            "dropped_units" in record or dropped_units
        ):
            raise UnitizationReviewError("legacy finalized schema cannot record drops")
        dropped_units_by_id = _unique_by_id(dropped_units, "unit_id", "dropped unit")
        if set(finalized_units_by_id).intersection(dropped_units_by_id):
            raise UnitizationReviewError("dropped unit remains in finalized units")
        dropped_ids_by_adjudication: dict[str, set[str]] = {}
        for dropped in dropped_units:
            unit_id = _required_str(dropped, "unit_id")
            source_hash = _required_str(dropped, "source_unit_sha256")
            adjudication_id = _required_str(dropped, "adjudication_id")
            adjudication = adjudications.get(adjudication_id)
            if (
                unit_id not in raw_units
                or source_hash != canonical_sha256(raw_units[unit_id])
                or adjudication is None
                or adjudication.get("candidate_id") != candidate_id
                or adjudication.get("disposition") != "DROP"
                or not _required_str(adjudication, "drop_reason")
                or dropped.get("disposition") != "DROP"
                or dropped.get("adjudication_sha256") != canonical_sha256(adjudication)
            ):
                raise UnitizationReviewError(
                    f"broken dropped-unit hash link: {unit_id}"
                )
            dropped_ids_by_adjudication.setdefault(adjudication_id, set()).add(unit_id)
            verified_adjudication_ids.add(adjudication_id)
        for adjudication_id, dropped_ids in dropped_ids_by_adjudication.items():
            adjudication = adjudications[adjudication_id]
            source_unit_ids = _string_sequence(
                adjudication.get("source_unit_ids"), "source_unit_ids"
            )
            review_ids = _string_sequence(adjudication.get("review_ids"), "review_ids")
            if not review_ids:
                review_ids = (_required_str(adjudication, "review_id"),)
            reviewed_unit_ids = {
                _required_str(reviews[review_id], "unit_id")
                for review_id in review_ids
                if review_id in reviews
            }
            if (
                len(source_unit_ids) != 1
                or len(review_ids) != len(set(review_ids))
                or any(review_id not in reviews for review_id in review_ids)
                or any(
                    _required_str(reviews[review_id], "candidate_id") != candidate_id
                    for review_id in review_ids
                    if review_id in reviews
                )
                or set(source_unit_ids) != dropped_ids
                or reviewed_unit_ids != dropped_ids
            ):
                raise UnitizationReviewError(
                    f"DROP source units do not match provenance: {adjudication_id}"
                )
        if status == "candidate_excluded":
            if units or dropped_units:
                raise UnitizationReviewError("invalid candidate-exclusion envelope")
            exclusion = record.get("exclusion")
            if not isinstance(exclusion, Mapping):
                raise UnitizationReviewError("invalid candidate-exclusion envelope")
            exclusion = cast(Mapping[str, Any], exclusion)
            _required_str(exclusion, "reason")
            adjudication_id = _required_str(exclusion, "adjudication_id")
            adjudication = adjudications.get(adjudication_id)
            if (
                adjudication is None
                or adjudication.get("candidate_id") != candidate_id
                or adjudication.get("disposition") != "CANDIDATE-EXCLUSION"
                or exclusion.get("adjudication_sha256")
                != canonical_sha256(adjudication)
            ):
                raise UnitizationReviewError(
                    f"broken exclusion hash link: {adjudication_id}"
                )
            source_unit_ids = _string_sequence(
                adjudication.get("source_unit_ids"), "source_unit_ids"
            )
            review_ids = _string_sequence(adjudication.get("review_ids"), "review_ids")
            if not review_ids:
                review_ids = (_required_str(adjudication, "review_id"),)
            candidate_review_ids = {
                review_id
                for review_id, review in reviews.items()
                if _required_str(review, "candidate_id") == candidate_id
            }
            reviewed_unit_ids = {
                _required_str(reviews[review_id], "unit_id")
                for review_id in review_ids
                if review_id in reviews
            }
            if (
                len(source_unit_ids) != len(set(source_unit_ids))
                or set(source_unit_ids) != set(raw_units)
                or len(review_ids) != len(set(review_ids))
                or set(review_ids) != candidate_review_ids
                or not reviewed_unit_ids.issubset(source_unit_ids)
            ):
                raise UnitizationReviewError(
                    f"candidate exclusion does not consume complete provenance: "
                    f"{adjudication_id}"
                )
            verified_adjudication_ids.add(adjudication_id)
            continue
        if status != "finalized" or record.get("exclusion") is not None:
            raise UnitizationReviewError("invalid finalized prediction-units envelope")
        for unit in units:
            source_hashes = _string_sequence(
                unit.get("source_unit_sha256s"), "source_unit_sha256s"
            )
            if not source_hashes or not set(source_hashes).issubset(raw_hashes):
                raise UnitizationReviewError(
                    f"broken source-unit hash link: {_required_str(unit, 'unit_id')}"
                )
            adjudication_id = _required_str(unit, "adjudication_id")
            if adjudication_id.startswith("automatic:"):
                expected = (
                    f"automatic:{source_hashes[0]}" if len(source_hashes) == 1 else None
                )
                if adjudication_id != expected or unit.get("disposition") != "ACCEPT":
                    raise UnitizationReviewError("invalid automatic finalization link")
            else:
                adjudication = adjudications.get(adjudication_id)
                adjudication_disposition = (
                    adjudication.get("disposition")
                    if adjudication is not None
                    else None
                )
                if (
                    adjudication is None
                    or adjudication_disposition
                    not in {"ACCEPT", "AMEND", "SPLIT", "MERGE"}
                    or unit.get("disposition") != adjudication_disposition
                    or unit.get("adjudication_sha256") != canonical_sha256(adjudication)
                ):
                    raise UnitizationReviewError(
                        f"broken adjudication hash link: {adjudication_id}"
                    )
                verified_adjudication_ids.add(adjudication_id)
    if verified_adjudication_ids != set(adjudications):
        raise UnitizationReviewError(
            "finalized artifact does not consume adjudications"
        )


def _verify_adjudication_review_coverage(
    *,
    raw_by_candidate: Mapping[str, Mapping[str, Any]],
    reviews: Mapping[str, Mapping[str, Any]],
    adjudications: Mapping[str, Mapping[str, Any]],
) -> None:
    """Recheck complete queue/source consumption without trusting the applicator."""

    resolved_review_ids: set[str] = set()
    consumed_source_unit_ids: dict[str, set[str]] = {}
    for adjudication_id, adjudication in adjudications.items():
        candidate_id = _required_str(adjudication, "candidate_id")
        raw_record = raw_by_candidate.get(candidate_id)
        if raw_record is None:
            raise UnitizationReviewError(
                f"adjudication references candidate with no raw units: {candidate_id}"
            )
        case_id = _required_str(raw_record, "case_id")
        _validate_adjudication_header(adjudication, case_id=case_id)
        disposition = UnitizationDisposition(
            _required_str(adjudication, "disposition").upper()
        )
        review_ids = _string_sequence(adjudication.get("review_ids"), "review_ids")
        if not review_ids:
            review_ids = (_required_str(adjudication, "review_id"),)
        if len(review_ids) != len(set(review_ids)) or any(
            review_id not in reviews for review_id in review_ids
        ):
            raise UnitizationReviewError(
                f"{adjudication_id}: invalid or duplicate review_ids"
            )
        overlap = resolved_review_ids.intersection(review_ids)
        if overlap:
            raise UnitizationReviewError(
                f"reviews adjudicated more than once: {sorted(overlap)}"
            )
        if any(
            _required_str(reviews[review_id], "candidate_id") != candidate_id
            for review_id in review_ids
        ):
            raise UnitizationReviewError(
                f"{adjudication_id}: review belongs to another candidate"
            )
        reviewed_source_unit_ids = tuple(
            dict.fromkeys(
                _required_str(reviews[review_id], "unit_id") for review_id in review_ids
            )
        )
        explicit_source_unit_ids = _string_sequence(
            adjudication.get("source_unit_ids"), "source_unit_ids"
        )
        if len(explicit_source_unit_ids) != len(set(explicit_source_unit_ids)):
            raise UnitizationReviewError(
                f"{adjudication_id}: source_unit_ids must be unique"
            )
        raw_unit_ids = set(
            _unique_units(
                _record_sequence(raw_record.get("prediction_units"), "prediction_units")
            )
        )
        if disposition is UnitizationDisposition.CANDIDATE_EXCLUSION:
            source_unit_ids = explicit_source_unit_ids
            candidate_review_ids = {
                review_id
                for review_id, review in reviews.items()
                if _required_str(review, "candidate_id") == candidate_id
            }
            if (
                set(source_unit_ids) != raw_unit_ids
                or set(review_ids) != candidate_review_ids
                or not set(reviewed_source_unit_ids).issubset(source_unit_ids)
            ):
                raise UnitizationReviewError(
                    f"candidate exclusion does not consume complete provenance: "
                    f"{adjudication_id}"
                )
        else:
            source_unit_ids = reviewed_source_unit_ids
            if explicit_source_unit_ids and set(explicit_source_unit_ids) != set(
                reviewed_source_unit_ids
            ):
                raise UnitizationReviewError(
                    f"{adjudication_id}: source_unit_ids must include reviewed units"
                )
            if not set(source_unit_ids).issubset(raw_unit_ids):
                raise UnitizationReviewError(
                    f"{adjudication_id}: source unit is not a raw candidate unit"
                )
        already_consumed = consumed_source_unit_ids.setdefault(
            candidate_id, set()
        ).intersection(source_unit_ids)
        if already_consumed:
            raise UnitizationReviewError(
                f"{adjudication_id}: source units were adjudicated more than once: "
                f"{sorted(already_consumed)}"
            )
        consumed_source_unit_ids[candidate_id].update(source_unit_ids)
        finalized_units = _record_sequence(
            adjudication.get("finalized_units", ()), "finalized_units"
        )
        _validate_disposition_shape(
            disposition,
            source_unit_ids=source_unit_ids,
            finalized_units=finalized_units,
        )
        resolved_review_ids.update(review_ids)
    unresolved = set(reviews) - resolved_review_ids
    if unresolved:
        raise UnitizationReviewError(
            f"finalized artifact leaves unresolved reviews: {sorted(unresolved)}"
        )


def require_finalized_envelopes(
    records: Iterable[Mapping[str, Any]],
) -> tuple[JsonRecord, ...]:
    """Reject raw or malformed units at a downstream Stage A boundary."""

    materialized = tuple(dict(record) for record in records)
    _unique_by_candidate(materialized, "finalized units")
    for record in materialized:
        schema_version = record.get("schema_version")
        if schema_version not in SUPPORTED_FINALIZED_SCHEMA_VERSIONS:
            raise UnitizationReviewError("raw or unsupported prediction-units artifact")
        if (
            schema_version == LEGACY_FINALIZED_SCHEMA_VERSION
            and "dropped_units" in record
        ):
            raise UnitizationReviewError("legacy finalized schema cannot record drops")
        _required_str(record, "unitization_review_queue_sha256")
        status = record.get("status")
        units = _record_sequence(record.get("prediction_units"), "prediction_units")
        dropped_units = _record_sequence(
            record.get("dropped_units", ()), "dropped_units"
        )
        if schema_version == FINALIZED_SCHEMA_VERSION:
            if "dropped_units" not in record:
                raise UnitizationReviewError(
                    "v2 finalized schema requires dropped_units"
                )
            finalized_ids = {_required_str(unit, "unit_id") for unit in units}
            dropped_ids = set(_unique_by_id(dropped_units, "unit_id", "dropped unit"))
            if finalized_ids.intersection(dropped_ids):
                raise UnitizationReviewError("dropped unit remains in finalized units")
            for dropped in dropped_units:
                _required_str(dropped, "source_unit_sha256")
                _required_str(dropped, "adjudication_id")
                _required_str(dropped, "adjudication_sha256")
                if dropped.get("disposition") != "DROP":
                    raise UnitizationReviewError("invalid dropped-unit disposition")
        if status == "candidate_excluded":
            if (
                units
                or (schema_version == FINALIZED_SCHEMA_VERSION and dropped_units)
                or not isinstance(record.get("exclusion"), Mapping)
            ):
                raise UnitizationReviewError("invalid candidate-exclusion envelope")
            continue
        if status != "finalized" or not units:
            raise UnitizationReviewError("finalized candidate must contain units")
        for unit in units:
            _required_str(unit, "adjudication_id")
            disposition = _required_str(unit, "disposition")
            if disposition not in {"ACCEPT", "AMEND", "SPLIT", "MERGE"}:
                raise UnitizationReviewError("invalid finalized-unit disposition")
            if not _string_sequence(
                unit.get("source_unit_sha256s"), "source_unit_sha256s"
            ):
                raise UnitizationReviewError("finalized unit lacks source hash links")
    return materialized


def _automatic_provenance(unit: Mapping[str, Any]) -> JsonRecord:
    digest = canonical_sha256(unit)
    return {
        "source_unit_sha256s": [digest],
        "adjudication_id": f"automatic:{digest}",
        "adjudication_sha256": None,
        "disposition": UnitizationDisposition.ACCEPT.value,
    }


def _base_unit(unit: Mapping[str, Any]) -> JsonRecord:
    return {
        key: value
        for key, value in unit.items()
        if key
        not in {
            "source_unit_sha256s",
            "adjudication_id",
            "adjudication_sha256",
            "disposition",
        }
    }


def _validate_adjudication_header(record: Mapping[str, Any], *, case_id: str) -> None:
    if record.get("schema_version") != ADJUDICATION_SCHEMA_VERSION:
        raise UnitizationReviewError("unsupported unitization adjudication schema")
    if _required_str(record, "case_id") != case_id:
        raise UnitizationReviewError("adjudication case_id mismatch")
    _required_str(record, "adjudicator_id")
    _required_str(record, "adjudication_notes")


def _validate_disposition_shape(
    disposition: UnitizationDisposition,
    *,
    source_unit_ids: Sequence[str],
    finalized_units: Sequence[Mapping[str, Any]],
) -> None:
    if not source_unit_ids:
        raise UnitizationReviewError("adjudication must consume source units")
    expected = {
        UnitizationDisposition.ACCEPT: 0,
        UnitizationDisposition.AMEND: 1,
        UnitizationDisposition.MERGE: 1,
        UnitizationDisposition.DROP: 0,
        UnitizationDisposition.CANDIDATE_EXCLUSION: 0,
    }
    if disposition in expected and len(finalized_units) != expected[disposition]:
        raise UnitizationReviewError(f"invalid {disposition.value} output count")
    if disposition is UnitizationDisposition.SPLIT and len(finalized_units) < 2:
        raise UnitizationReviewError("SPLIT must emit at least two units")
    if disposition is UnitizationDisposition.MERGE and len(source_unit_ids) < 2:
        raise UnitizationReviewError("MERGE must consume at least two units")
    if (
        disposition
        in {
            UnitizationDisposition.ACCEPT,
            UnitizationDisposition.AMEND,
            UnitizationDisposition.SPLIT,
            UnitizationDisposition.DROP,
        }
        and len(source_unit_ids) != 1
    ):
        raise UnitizationReviewError(
            f"{disposition.value} must consume exactly one unit"
        )


def _unique_by_candidate(
    records: Iterable[Mapping[str, Any]], label: str
) -> dict[str, Mapping[str, Any]]:
    indexed: dict[str, Mapping[str, Any]] = {}
    for record in records:
        candidate_id = _required_str(record, "candidate_id")
        if candidate_id in indexed:
            raise UnitizationReviewError(f"duplicate {label} candidate: {candidate_id}")
        indexed[candidate_id] = record
    return indexed


def _unique_by_id(
    records: Iterable[Mapping[str, Any]], key: str, label: str
) -> dict[str, Mapping[str, Any]]:
    indexed: dict[str, Mapping[str, Any]] = {}
    for record in records:
        record_id = _required_str(record, key)
        if record_id in indexed:
            raise UnitizationReviewError(f"duplicate {label}: {record_id}")
        indexed[record_id] = record
    return indexed


def _unique_units(records: Sequence[Mapping[str, Any]]) -> dict[str, JsonRecord]:
    units: dict[str, JsonRecord] = {}
    for record in records:
        unit_id = _required_str(record, "unit_id")
        if unit_id in units:
            raise UnitizationReviewError(f"duplicate raw unit_id: {unit_id}")
        units[unit_id] = dict(record)
    return units


def _record_sequence(value: object, field_name: str) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise UnitizationReviewError(f"{field_name} must be a sequence")
    values = cast(Sequence[object], value)
    if not all(isinstance(item, Mapping) for item in values):
        raise UnitizationReviewError(f"{field_name} must contain objects")
    return tuple(cast(Sequence[Mapping[str, Any]], values))


def _string_sequence(value: object, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise UnitizationReviewError(f"{field_name} must be a sequence")
    values = cast(Sequence[object], value)
    result = tuple(item for item in values if isinstance(item, str) and item.strip())
    if len(result) != len(values):
        raise UnitizationReviewError(f"{field_name} must contain nonempty strings")
    return result


def _required_str(record: Mapping[str, Any], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise UnitizationReviewError(f"{key} is required")
    return value
