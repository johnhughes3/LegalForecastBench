"""Apply blinded Stage A review decisions and verify finalized unit artifacts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from enum import StrEnum
from typing import Any, cast

JsonRecord = dict[str, Any]
FINALIZED_SCHEMA_VERSION = "legalforecast.finalized_prediction_units.v1"
ADJUDICATION_SCHEMA_VERSION = "legalforecast.unitization_adjudication.v1"


class UnitizationReviewError(ValueError):
    """Raised when Stage A review artifacts do not form a complete hash chain."""


class UnitizationDisposition(StrEnum):
    """Supported reviewer actions for Stage A prediction units."""

    ACCEPT = "ACCEPT"
    AMEND = "AMEND"
    SPLIT = "SPLIT"
    MERGE = "MERGE"
    CANDIDATE_EXCLUSION = "CANDIDATE-EXCLUSION"


def canonical_sha256(record: Mapping[str, Any]) -> str:
    """Hash a JSON object using the repository's canonical compact encoding."""

    payload = json.dumps(
        dict(record), sort_keys=True, separators=(",", ":"), ensure_ascii=False
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
    expected_review_ids = set(reviews_by_id)
    resolved_review_ids: set[str] = set()
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
            source_unit_ids = _string_sequence(
                adjudication.get("source_unit_ids"), "source_unit_ids"
            ) or tuple(
                _required_str(candidate_reviews[review_id], "unit_id")
                for review_id in review_ids
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

        unresolved = set(candidate_reviews) - resolved_review_ids
        if unresolved:
            raise UnitizationReviewError(
                f"candidate {candidate_id} has unresolved reviews: {sorted(unresolved)}"
            )
        finalized = [
            {**_base_unit(unit), **provenance[unit_id]}
            for unit_id, unit in sorted(current.items())
        ]
        output.append(
            {
                "schema_version": FINALIZED_SCHEMA_VERSION,
                "status": "candidate_excluded" if excluded else "finalized",
                "candidate_id": candidate_id,
                "case_id": case_id,
                "raw_prediction_units_sha256": canonical_sha256(raw_record),
                "prediction_units": finalized,
                "exclusion": exclusion,
            }
        )

    missing_candidates = {
        _required_str(review, "candidate_id") for review in reviews_by_id.values()
    } - set(raw_by_candidate)
    if missing_candidates:
        raise UnitizationReviewError(
            "reviews reference candidates with no raw units: "
            f"{sorted(missing_candidates)}"
        )
    unconsumed_adjudications = (
        set(adjudications_by_id)
        - {
            provenance["adjudication_id"]
            for record in output
            for provenance in _record_sequence(
                record.get("prediction_units"), "prediction_units"
            )
            if isinstance(provenance.get("adjudication_id"), str)
            and not cast(str, provenance["adjudication_id"]).startswith("automatic:")
        }
        - {
            cast(str, exclusion["adjudication_id"])
            for record in output
            if isinstance((exclusion := record.get("exclusion")), Mapping)
        }
    )
    if unconsumed_adjudications:
        raise UnitizationReviewError(
            f"adjudications were not consumed: {sorted(unconsumed_adjudications)}"
        )
    if resolved_review_ids != expected_review_ids:
        raise UnitizationReviewError("unitization review queue was not fully drained")
    verify_finalized_prediction_units(output, raw_by_candidate.values(), adjudications)
    return tuple(output)


def verify_finalized_prediction_units(
    finalized_records: Iterable[Mapping[str, Any]],
    raw_records: Iterable[Mapping[str, Any]],
    adjudication_records: Iterable[Mapping[str, Any]],
) -> None:
    """Fail closed unless finalized records reproduce their complete hash chain."""

    raw_by_candidate = _unique_by_candidate(raw_records, "raw units")
    adjudications = _unique_by_id(
        adjudication_records, "adjudication_id", "adjudication"
    )
    finalized_by_candidate = _unique_by_candidate(finalized_records, "finalized units")
    if set(finalized_by_candidate) != set(raw_by_candidate):
        raise UnitizationReviewError("finalized candidates do not match raw candidates")
    for candidate_id, record in finalized_by_candidate.items():
        if record.get("schema_version") != FINALIZED_SCHEMA_VERSION:
            raise UnitizationReviewError("raw or unsupported prediction-units artifact")
        raw = raw_by_candidate[candidate_id]
        if record.get("raw_prediction_units_sha256") != canonical_sha256(raw):
            raise UnitizationReviewError(f"broken raw-unit hash link: {candidate_id}")
        raw_hashes = {
            canonical_sha256(unit)
            for unit in _record_sequence(
                raw.get("prediction_units"), "prediction_units"
            )
        }
        for unit in _record_sequence(
            record.get("prediction_units"), "prediction_units"
        ):
            source_hashes = set(
                _string_sequence(unit.get("source_unit_sha256s"), "source_unit_sha256s")
            )
            if not source_hashes or not source_hashes.issubset(raw_hashes):
                raise UnitizationReviewError(
                    f"broken source-unit hash link: {_required_str(unit, 'unit_id')}"
                )
            adjudication_id = _required_str(unit, "adjudication_id")
            if adjudication_id.startswith("automatic:"):
                expected = f"automatic:{next(iter(source_hashes))}"
                if adjudication_id != expected or unit.get("disposition") != "ACCEPT":
                    raise UnitizationReviewError("invalid automatic finalization link")
            else:
                adjudication = adjudications.get(adjudication_id)
                if adjudication is None or unit.get(
                    "adjudication_sha256"
                ) != canonical_sha256(adjudication):
                    raise UnitizationReviewError(
                        f"broken adjudication hash link: {adjudication_id}"
                    )


def require_finalized_envelopes(
    records: Iterable[Mapping[str, Any]],
) -> tuple[JsonRecord, ...]:
    """Reject raw or malformed units at a downstream Stage A boundary."""

    materialized = tuple(dict(record) for record in records)
    _unique_by_candidate(materialized, "finalized units")
    for record in materialized:
        if record.get("schema_version") != FINALIZED_SCHEMA_VERSION:
            raise UnitizationReviewError("raw or unsupported prediction-units artifact")
        status = record.get("status")
        units = _record_sequence(record.get("prediction_units"), "prediction_units")
        if status == "candidate_excluded":
            if units or not isinstance(record.get("exclusion"), Mapping):
                raise UnitizationReviewError("invalid candidate-exclusion envelope")
            continue
        if status != "finalized" or not units:
            raise UnitizationReviewError("finalized candidate must contain units")
        for unit in units:
            _required_str(unit, "adjudication_id")
            _required_str(unit, "disposition")
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
        UnitizationDisposition.CANDIDATE_EXCLUSION: 0,
    }
    if disposition in expected and len(finalized_units) != expected[disposition]:
        raise UnitizationReviewError(f"invalid {disposition.value} output count")
    if disposition is UnitizationDisposition.SPLIT and len(finalized_units) < 2:
        raise UnitizationReviewError("SPLIT must emit at least two units")
    if disposition is UnitizationDisposition.MERGE and len(source_unit_ids) < 2:
        raise UnitizationReviewError("MERGE must consume at least two units")


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
