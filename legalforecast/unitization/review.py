"""Apply blinded Stage A review decisions and verify finalized unit artifacts."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, cast

from legalforecast.contracts.schemas import (
    FINALIZED_PREDICTION_UNITS_V2,
    FINALIZED_PREDICTION_UNITS_V3,
    UNITIZATION_ADJUDICATION_V1,
    UNITIZATION_ADJUDICATION_V2,
)
from legalforecast.unitization.construct_units import StageADocumentRole
from legalforecast.unitization.schemas import prediction_unit_from_record

JsonRecord = dict[str, Any]
LEGACY_FINALIZED_SCHEMA_VERSION = "legalforecast.finalized_prediction_units.v1"
FINALIZED_SCHEMA_VERSION = str(FINALIZED_PREDICTION_UNITS_V2)
STRUCTURAL_ADD_FINALIZED_SCHEMA_VERSION = str(FINALIZED_PREDICTION_UNITS_V3)
# Downstream Stage B authentication (decision-text artifacts) authenticates v1
# and v2 only; adopting the structural-ADD successor there is its own migration,
# so a v3 envelope fails closed at that boundary until it lands.
SUPPORTED_FINALIZED_SCHEMA_VERSIONS = frozenset(
    {LEGACY_FINALIZED_SCHEMA_VERSION, FINALIZED_SCHEMA_VERSION}
)
STAGE_A_FINALIZED_SCHEMA_VERSIONS = SUPPORTED_FINALIZED_SCHEMA_VERSIONS | {
    STRUCTURAL_ADD_FINALIZED_SCHEMA_VERSION
}
DROP_MIGRATION_SCHEMA_VERSIONS = frozenset(
    {FINALIZED_SCHEMA_VERSION, STRUCTURAL_ADD_FINALIZED_SCHEMA_VERSION}
)
ADJUDICATION_SCHEMA_VERSION = str(UNITIZATION_ADJUDICATION_V1)
STRUCTURAL_ADD_ADJUDICATION_SCHEMA_VERSION = str(UNITIZATION_ADJUDICATION_V2)
SUPPORTED_ADJUDICATION_SCHEMA_VERSIONS = frozenset(
    {ADJUDICATION_SCHEMA_VERSION, STRUCTURAL_ADD_ADJUDICATION_SCHEMA_VERSION}
)
STRUCTURAL_OMISSION_ROUTE_REASON = "structural_omitted"
_PROVENANCE_KEYS = frozenset(
    {
        "source_unit_sha256s",
        "adjudication_id",
        "adjudication_sha256",
        "disposition",
        "added_from_review_ids",
        "structural_flag_sha256",
        "raw_prediction_units_sha256",
        "predecision_source_document_ids",
    }
)
_ADDED_UNIT_LEDGER_KEYS = frozenset(
    {
        "unit_id",
        "review_ids",
        "structural_flag_sha256",
        "raw_prediction_units_sha256",
        "adjudication_id",
        "adjudication_sha256",
        "disposition",
    }
)


class UnitizationReviewError(ValueError):
    """Raised when Stage A review artifacts do not form a complete hash chain."""


@dataclass(frozen=True, slots=True)
class V4FinalizedCitationDocument:
    """Verifier-owned predecision text available to a finalized v4 unit."""

    document_id: str
    document_role: str
    markdown: str
    is_predecision_material: bool
    contains_target_outcome: bool
    docket_entry_number: int | None = None

    def __post_init__(self) -> None:
        if type(self.document_id) is not str or not self.document_id.strip():
            raise ValueError("document_id is required")
        if type(self.markdown) is not str:
            raise ValueError("markdown must be text")
        if type(self.is_predecision_material) is not bool:
            raise ValueError("is_predecision_material must be boolean")
        if type(self.contains_target_outcome) is not bool:
            raise ValueError("contains_target_outcome must be boolean")
        if self.docket_entry_number is not None and (
            type(self.docket_entry_number) is not int or self.docket_entry_number <= 0
        ):
            raise ValueError("docket_entry_number must be a positive integer")
        try:
            StageADocumentRole(self.document_role)
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"unsupported Stage A document role: {self.document_role}"
            ) from error


class UnitizationDisposition(StrEnum):
    """Supported reviewer actions for Stage A prediction units."""

    ACCEPT = "ACCEPT"
    ADD = "ADD"
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
    uses_add_migration = any(
        _required_str(adjudication, "disposition").upper()
        == UnitizationDisposition.ADD.value
        for adjudication in adjudications
    )
    if uses_add_migration:
        schema_version = STRUCTURAL_ADD_FINALIZED_SCHEMA_VERSION
    elif uses_drop_migration:
        schema_version = FINALIZED_SCHEMA_VERSION
    else:
        schema_version = LEGACY_FINALIZED_SCHEMA_VERSION
    expected_review_ids = set(reviews_by_id)
    review_queue_sha256 = canonical_records_sha256(reviews)
    resolved_review_ids: set[str] = set()
    consumed_adjudication_ids: set[str] = set()
    output: list[JsonRecord] = []

    for candidate_id, raw_record in raw_by_candidate.items():
        case_id = _required_str(raw_record, "case_id")
        raw_candidate_sha256 = canonical_sha256(raw_record)
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
        added_units: list[JsonRecord] = []
        adjudicated_source_unit_ids: set[str] = set()

        candidate_dispositions = {
            _required_str(adjudication, "disposition").upper()
            for adjudication in candidate_adjudications
        }
        if {
            UnitizationDisposition.ADD.value,
            UnitizationDisposition.CANDIDATE_EXCLUSION.value,
        }.issubset(candidate_dispositions):
            raise UnitizationReviewError(
                "ADD and CANDIDATE-EXCLUSION are incompatible for one candidate"
            )

        for adjudication in candidate_adjudications:
            _validate_adjudication_header(adjudication, case_id=case_id)
            adjudication_id = _required_str(adjudication, "adjudication_id")
            disposition = UnitizationDisposition(
                _required_str(adjudication, "disposition").upper()
            )
            review_ids = _adjudication_review_ids(adjudication)
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
            if disposition is UnitizationDisposition.ADD:
                added_unit, added_provenance = _added_unit_from_adjudication(
                    adjudication,
                    adjudication_id=adjudication_id,
                    review_ids=review_ids,
                    candidate_reviews=candidate_reviews,
                    raw_candidate_sha256=raw_candidate_sha256,
                    known_unit_ids=set(units_by_id) | set(current),
                )
                added_unit_id = _required_str(added_unit, "unit_id")
                current[added_unit_id] = added_unit
                provenance[added_unit_id] = added_provenance
                added_units.append(
                    {
                        "unit_id": added_unit_id,
                        "review_ids": list(review_ids),
                        "structural_flag_sha256": added_provenance[
                            "structural_flag_sha256"
                        ],
                        "raw_prediction_units_sha256": raw_candidate_sha256,
                        "adjudication_id": adjudication_id,
                        "adjudication_sha256": added_provenance["adjudication_sha256"],
                        "disposition": UnitizationDisposition.ADD.value,
                    }
                )
                resolved_review_ids.update(review_ids)
                consumed_adjudication_ids.add(adjudication_id)
                continue
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
            "schema_version": schema_version,
            "status": "candidate_excluded" if excluded else "finalized",
            "candidate_id": candidate_id,
            "case_id": case_id,
            "raw_prediction_units_sha256": raw_candidate_sha256,
            "unitization_review_queue_sha256": review_queue_sha256,
            "prediction_units": finalized,
            "exclusion": exclusion,
        }
        if schema_version in DROP_MIGRATION_SCHEMA_VERSIONS:
            finalized_record["dropped_units"] = dropped_units
        if schema_version == STRUCTURAL_ADD_FINALIZED_SCHEMA_VERSION:
            finalized_record["added_units"] = added_units
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
    dispositions = {
        _required_str(adjudication, "disposition").upper()
        for adjudication in adjudications.values()
    }
    expected_schema_version = (
        STRUCTURAL_ADD_FINALIZED_SCHEMA_VERSION
        if UnitizationDisposition.ADD.value in dispositions
        else FINALIZED_SCHEMA_VERSION
        if UnitizationDisposition.DROP.value in dispositions
        else LEGACY_FINALIZED_SCHEMA_VERSION
    )
    expected_source_hashes_by_adjudication = _verify_adjudication_review_coverage(
        raw_by_candidate=raw_by_candidate,
        reviews=reviews,
        adjudications=adjudications,
    )
    if set(finalized_by_candidate) != set(raw_by_candidate):
        raise UnitizationReviewError("finalized candidates do not match raw candidates")
    verified_adjudication_ids: set[str] = set()
    for candidate_id, record in finalized_by_candidate.items():
        schema_version = record.get("schema_version")
        if schema_version not in STAGE_A_FINALIZED_SCHEMA_VERSIONS:
            raise UnitizationReviewError("raw or unsupported prediction-units artifact")
        if schema_version != expected_schema_version:
            raise UnitizationReviewError(
                "finalized schema does not match the adjudication migration"
            )
        if (
            schema_version in DROP_MIGRATION_SCHEMA_VERSIONS
            and "dropped_units" not in record
        ):
            raise UnitizationReviewError("v2 finalized schema requires dropped_units")
        if (
            schema_version == STRUCTURAL_ADD_FINALIZED_SCHEMA_VERSION
            and "added_units" not in record
        ):
            raise UnitizationReviewError("v3 finalized schema requires added_units")
        raw = raw_by_candidate[candidate_id]
        raw_candidate_sha256 = canonical_sha256(raw)
        if record.get("raw_prediction_units_sha256") != raw_candidate_sha256:
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
        finalized_units_by_id = _unique_by_id(units, "unit_id", "finalized unit_id")
        dropped_units = _record_sequence(
            record.get("dropped_units", ()), "dropped_units"
        )
        added_units = _record_sequence(record.get("added_units", ()), "added_units")
        if schema_version == LEGACY_FINALIZED_SCHEMA_VERSION and (
            "dropped_units" in record or dropped_units
        ):
            raise UnitizationReviewError("legacy finalized schema cannot record drops")
        if schema_version == LEGACY_FINALIZED_SCHEMA_VERSION and (
            "added_units" in record or added_units
        ):
            raise UnitizationReviewError(
                "legacy finalized schema cannot record additions"
            )
        if schema_version == FINALIZED_SCHEMA_VERSION and (
            "added_units" in record or added_units
        ):
            raise UnitizationReviewError("v2 finalized schema cannot record additions")
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
            if units or dropped_units or added_units:
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
        added_by_unit_id = _unique_by_id(added_units, "unit_id", "added unit")
        added_adjudication_ids: set[str] = set()
        finalized_added_units = {
            _required_str(unit, "unit_id"): unit
            for unit in units
            if unit.get("disposition") == UnitizationDisposition.ADD.value
        }
        if set(added_by_unit_id) != set(finalized_added_units):
            if len(finalized_added_units) > 1 and len(finalized_added_units) > len(
                added_by_unit_id
            ):
                raise UnitizationReviewError(
                    "more than one added unit is not authorized by the ADD ledger"
                )
            raise UnitizationReviewError(
                "added_units provenance does not match finalized units"
            )
        for added in added_units:
            _require_added_unit_ledger_shape(added)
            unit_id = _required_str(added, "unit_id")
            adjudication_id = _required_str(added, "adjudication_id")
            unit = finalized_added_units[unit_id]
            if added.get("structural_flag_sha256") != unit.get(
                "structural_flag_sha256"
            ):
                raise UnitizationReviewError(
                    f"broken added-unit evidence link: {unit_id}"
                )
            if added.get("raw_prediction_units_sha256") != raw_candidate_sha256:
                raise UnitizationReviewError(
                    f"broken added-unit ledger link: {unit_id}"
                )
            if added.get("review_ids") != unit.get("added_from_review_ids"):
                raise UnitizationReviewError(
                    f"broken added-unit review link: {unit_id}"
                )
            if (
                adjudication_id != unit.get("adjudication_id")
                or added.get("adjudication_sha256") != unit.get("adjudication_sha256")
                or added.get("disposition") != UnitizationDisposition.ADD.value
            ):
                raise UnitizationReviewError(f"broken added-unit hash link: {unit_id}")
            if adjudication_id in added_adjudication_ids:
                raise UnitizationReviewError(
                    f"more than one added unit uses ADD adjudication: {adjudication_id}"
                )
            added_adjudication_ids.add(adjudication_id)
        for unit in units:
            if unit.get("disposition") == UnitizationDisposition.ADD.value:
                verified_adjudication_ids.add(
                    _verify_added_unit(
                        unit,
                        candidate_id=candidate_id,
                        schema_version=schema_version,
                        raw_candidate_sha256=raw_candidate_sha256,
                        raw_unit_ids=set(raw_units),
                        adjudications=adjudications,
                        reviews=reviews,
                    )
                )
                continue
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
                if (
                    adjudication_id != expected
                    or unit.get("disposition") != "ACCEPT"
                    or canonical_sha256(_base_unit(unit)) != source_hashes[0]
                ):
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
                expected_source_hashes = expected_source_hashes_by_adjudication.get(
                    adjudication_id
                )
                if source_hashes != expected_source_hashes:
                    raise UnitizationReviewError(
                        "finalized unit does not use exact adjudicated source hashes"
                    )
                verified_adjudication_ids.add(adjudication_id)
    if verified_adjudication_ids != set(adjudications):
        raise UnitizationReviewError(
            "finalized artifact does not consume adjudications"
        )


def validate_v4_finalized_unit_citations(
    finalized_records: Iterable[Mapping[str, Any]],
    *,
    source_documents_by_candidate: Mapping[str, Sequence[V4FinalizedCitationDocument]],
) -> None:
    """Replay finalized v4 unit shape and citation evidence from trusted text.

    The caller remains responsible for authenticating the supplied Markdown and
    document roles. This pure verifier prevents finalized/adjudicated units from
    changing the canonical prediction-unit payload, citing another candidate's
    document, or retaining an excerpt that the authenticated source cannot
    reconstruct exactly.
    """

    complaint_roles = {
        StageADocumentRole.COMPLAINT,
        StageADocumentRole.AMENDED_COMPLAINT,
    }
    target_motion_roles = {
        StageADocumentRole.MTD_NOTICE,
        StageADocumentRole.MTD_MEMORANDUM,
    }
    for finalized in finalized_records:
        candidate_id = _required_str(finalized, "candidate_id")
        supplied_documents = source_documents_by_candidate.get(candidate_id, ())
        documents_by_id: dict[str, V4FinalizedCitationDocument] = {}
        for document in supplied_documents:
            if document.document_id in documents_by_id:
                raise UnitizationReviewError(
                    f"duplicate supplied citation document: {candidate_id}:"
                    f"{document.document_id}"
                )
            documents_by_id[document.document_id] = document

        units = _record_sequence(
            finalized.get("prediction_units", ()), "prediction_units"
        )
        for finalized_unit in units:
            unit_id = _required_str(finalized_unit, "unit_id")
            base_unit = _base_unit(finalized_unit)
            try:
                decoded = prediction_unit_from_record(base_unit)
            except (TypeError, ValueError) as error:
                raise UnitizationReviewError(
                    f"{candidate_id}:{unit_id}: invalid finalized v4 prediction "
                    f"unit: {error}"
                ) from error
            if base_unit != decoded.to_record():
                raise UnitizationReviewError(
                    f"{candidate_id}:{unit_id}: finalized v4 unit must equal its "
                    "canonical prediction unit"
                )

            cited_roles: set[StageADocumentRole] = set()
            for citation in decoded.source_citations:
                document = documents_by_id.get(citation.document_id)
                if document is None:
                    raise UnitizationReviewError(
                        f"{candidate_id}:{unit_id}: citation references an "
                        "unsupplied candidate document"
                    )
                if (
                    not document.is_predecision_material
                    or document.contains_target_outcome
                ):
                    raise UnitizationReviewError(
                        f"{candidate_id}:{unit_id}: citation references outcome or "
                        "non-predecision material"
                    )
                excerpt = citation.excerpt
                if excerpt is None or not excerpt.strip():
                    raise UnitizationReviewError(
                        f"{candidate_id}:{unit_id}: v4 citation excerpt is required"
                    )
                if len(excerpt.splitlines()) > 12:
                    raise UnitizationReviewError(
                        f"{candidate_id}:{unit_id}: citation span may contain at "
                        "most 12 lines"
                    )
                span_pages = _v4_citation_span_pages(document.markdown, excerpt)
                if not span_pages:
                    raise UnitizationReviewError(
                        f"{candidate_id}:{unit_id}: citation excerpt is not an "
                        "exact substring forming a bounded contiguous span of its "
                        "authenticated Markdown"
                    )
                if citation.page not in span_pages:
                    raise UnitizationReviewError(
                        f"{candidate_id}:{unit_id}: citation page attribution does "
                        "not match its authenticated Markdown span"
                    )
                if citation.docket_entry_number != document.docket_entry_number:
                    raise UnitizationReviewError(
                        f"{candidate_id}:{unit_id}: citation docket-entry attribution "
                        "does not match its authenticated source document"
                    )
                if citation.paragraph is not None:
                    raise UnitizationReviewError(
                        f"{candidate_id}:{unit_id}: v4 line-span citation cannot "
                        "assert paragraph metadata"
                    )
                cited_roles.add(StageADocumentRole(document.document_role))

            if decoded.should_score and not cited_roles.intersection(complaint_roles):
                raise UnitizationReviewError(
                    f"{candidate_id}:{unit_id}: scorable v4 unit requires complaint "
                    "or amended-complaint evidence"
                )
            if decoded.should_score and not cited_roles.intersection(
                target_motion_roles
            ):
                raise UnitizationReviewError(
                    f"{candidate_id}:{unit_id}: scorable v4 unit requires target-MTD "
                    "notice or memorandum evidence"
                )


def _v4_citation_span_pages(markdown: str, excerpt: str) -> set[int | None]:
    """Return pages where excerpt equals a valid v4 line-selector span."""

    lines = markdown.splitlines(keepends=True)
    matching_pages: set[int | None] = set()
    for start_index in range(len(lines)):
        max_end = min(len(lines), start_index + 12)
        for end_index in range(start_index + 1, max_end + 1):
            selected_lines = lines[start_index:end_index]
            final_line = _without_one_line_ending(selected_lines[-1])
            reconstructed = "".join((*selected_lines[:-1], final_line))
            if reconstructed == excerpt:
                matching_pages.add(_nearest_page_marker(lines, start_index))
    return matching_pages


def _without_one_line_ending(line: str) -> str:
    """Mirror the v4 model-response reconstruction of the final selected line."""

    for line_ending in (
        "\r\n",
        "\n",
        "\r",
        "\v",
        "\f",
        "\x1c",
        "\x1d",
        "\x1e",
        "\x85",
        "\u2028",
        "\u2029",
    ):
        if line.endswith(line_ending):
            return line[: -len(line_ending)]
    return line


def _nearest_page_marker(lines: Sequence[str], start_index: int) -> int | None:
    """Return the v4 page marker at or before a zero-based span start."""

    for line in reversed(lines[: start_index + 1]):
        match = re.fullmatch(
            r"\s*(?:#{1,6}\s+)?Page\s+(\d+)(?:\s+of\s+\d+)?\s*",
            line,
            re.I,
        )
        if match is not None:
            return int(match.group(1))
    return None


def _verify_adjudication_review_coverage(
    *,
    raw_by_candidate: Mapping[str, Mapping[str, Any]],
    reviews: Mapping[str, Mapping[str, Any]],
    adjudications: Mapping[str, Mapping[str, Any]],
) -> dict[str, tuple[str, ...]]:
    """Recheck complete queue/source consumption without trusting the applicator."""

    resolved_review_ids: set[str] = set()
    consumed_source_unit_ids: dict[str, set[str]] = {}
    source_hashes_by_adjudication: dict[str, tuple[str, ...]] = {}
    dispositions_by_candidate: dict[str, set[str]] = {}
    for adjudication in adjudications.values():
        dispositions_by_candidate.setdefault(
            _required_str(adjudication, "candidate_id"), set()
        ).add(_required_str(adjudication, "disposition").upper())
    if any(
        {
            UnitizationDisposition.ADD.value,
            UnitizationDisposition.CANDIDATE_EXCLUSION.value,
        }.issubset(candidate_dispositions)
        for candidate_dispositions in dispositions_by_candidate.values()
    ):
        raise UnitizationReviewError(
            "ADD and CANDIDATE-EXCLUSION are incompatible for one candidate"
        )
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
        if disposition is UnitizationDisposition.ADD:
            if "source_unit_ids" in adjudication:
                raise UnitizationReviewError(
                    f"{adjudication_id}: ADD must omit source_unit_ids"
                )
            finalized_units = _record_sequence(
                adjudication.get("finalized_units", ()), "finalized_units"
            )
            if len(finalized_units) != 1:
                raise UnitizationReviewError(
                    f"{adjudication_id}: invalid ADD output count"
                )
            _canonical_added_unit(finalized_units[0], adjudication_id)
            _authenticated_omission_evidence(
                adjudication_id,
                review_ids=review_ids,
                reviews=reviews,
                raw_candidate_sha256=canonical_sha256(raw_record),
            )
            source_hashes_by_adjudication[adjudication_id] = ()
            resolved_review_ids.update(review_ids)
            continue
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
        raw_units = _unique_units(
            _record_sequence(raw_record.get("prediction_units"), "prediction_units")
        )
        source_hashes_by_adjudication[adjudication_id] = tuple(
            canonical_sha256(raw_units[unit_id]) for unit_id in source_unit_ids
        )
        resolved_review_ids.update(review_ids)
    unresolved = set(reviews) - resolved_review_ids
    if unresolved:
        raise UnitizationReviewError(
            f"finalized artifact leaves unresolved reviews: {sorted(unresolved)}"
        )
    return source_hashes_by_adjudication


def require_finalized_envelopes(
    records: Iterable[Mapping[str, Any]],
) -> tuple[JsonRecord, ...]:
    """Reject raw or malformed units at a downstream Stage A boundary."""

    materialized = tuple(dict(record) for record in records)
    _unique_by_candidate(materialized, "finalized units")
    for record in materialized:
        schema_version = record.get("schema_version")
        if schema_version not in STAGE_A_FINALIZED_SCHEMA_VERSIONS:
            raise UnitizationReviewError("raw or unsupported prediction-units artifact")
        if (
            schema_version == LEGACY_FINALIZED_SCHEMA_VERSION
            and "dropped_units" in record
        ):
            raise UnitizationReviewError("legacy finalized schema cannot record drops")
        if (
            schema_version == LEGACY_FINALIZED_SCHEMA_VERSION
            and "added_units" in record
        ):
            raise UnitizationReviewError(
                "legacy finalized schema cannot record additions"
            )
        _required_str(record, "unitization_review_queue_sha256")
        status = record.get("status")
        units = _record_sequence(record.get("prediction_units"), "prediction_units")
        finalized_units_by_id = _unique_by_id(units, "unit_id", "finalized unit_id")
        dropped_units = _record_sequence(
            record.get("dropped_units", ()), "dropped_units"
        )
        added_units = _record_sequence(record.get("added_units", ()), "added_units")
        if schema_version in DROP_MIGRATION_SCHEMA_VERSIONS:
            if "dropped_units" not in record:
                raise UnitizationReviewError(
                    "v2 finalized schema requires dropped_units"
                )
            finalized_ids = set(finalized_units_by_id)
            dropped_ids = set(_unique_by_id(dropped_units, "unit_id", "dropped unit"))
            if finalized_ids.intersection(dropped_ids):
                raise UnitizationReviewError("dropped unit remains in finalized units")
            for dropped in dropped_units:
                _required_str(dropped, "source_unit_sha256")
                _required_str(dropped, "adjudication_id")
                _required_str(dropped, "adjudication_sha256")
                if dropped.get("disposition") != "DROP":
                    raise UnitizationReviewError("invalid dropped-unit disposition")
        if schema_version == STRUCTURAL_ADD_FINALIZED_SCHEMA_VERSION:
            if "added_units" not in record:
                raise UnitizationReviewError("v3 finalized schema requires added_units")
            _unique_by_id(added_units, "unit_id", "added unit")
            seen_adjudication_ids: set[str] = set()
            for added in added_units:
                _require_added_unit_ledger_shape(added)
                adjudication_id = _required_str(added, "adjudication_id")
                if adjudication_id in seen_adjudication_ids:
                    raise UnitizationReviewError(
                        "more than one added unit uses ADD adjudication"
                    )
                seen_adjudication_ids.add(adjudication_id)
        elif "added_units" in record or added_units:
            raise UnitizationReviewError(
                "only v3 finalized schema can record additions"
            )
        if status == "candidate_excluded":
            if (
                units
                or (schema_version in DROP_MIGRATION_SCHEMA_VERSIONS and dropped_units)
                or added_units
                or not isinstance(record.get("exclusion"), Mapping)
            ):
                raise UnitizationReviewError("invalid candidate-exclusion envelope")
            continue
        if status != "finalized" or not units:
            raise UnitizationReviewError("finalized candidate must contain units")
        if schema_version == STRUCTURAL_ADD_FINALIZED_SCHEMA_VERSION:
            added_by_unit_id = _unique_by_id(added_units, "unit_id", "added unit")
            finalized_added_units = {
                _required_str(unit, "unit_id"): unit
                for unit in finalized_units_by_id.values()
                if unit.get("disposition") == UnitizationDisposition.ADD.value
            }
            if set(added_by_unit_id) != set(finalized_added_units):
                raise UnitizationReviewError(
                    "added_units provenance does not match finalized units"
                )
            for unit_id, added in added_by_unit_id.items():
                unit = finalized_added_units[unit_id]
                if (
                    added.get("review_ids") != unit.get("added_from_review_ids")
                    or added.get("structural_flag_sha256")
                    != unit.get("structural_flag_sha256")
                    or added.get("raw_prediction_units_sha256")
                    != _required_str(record, "raw_prediction_units_sha256")
                    or added.get("adjudication_id") != unit.get("adjudication_id")
                    or added.get("adjudication_sha256")
                    != unit.get("adjudication_sha256")
                ):
                    raise UnitizationReviewError(
                        f"broken added-unit ledger link: {unit_id}"
                    )
        for unit in units:
            _required_str(unit, "adjudication_id")
            disposition = _required_str(unit, "disposition")
            if disposition == UnitizationDisposition.ADD.value:
                _require_added_unit_shape(
                    unit,
                    schema_version=schema_version,
                    raw_candidate_sha256=_required_str(
                        record, "raw_prediction_units_sha256"
                    ),
                )
                continue
            if disposition not in {"ACCEPT", "AMEND", "SPLIT", "MERGE"}:
                raise UnitizationReviewError("invalid finalized-unit disposition")
            if not _string_sequence(
                unit.get("source_unit_sha256s"), "source_unit_sha256s"
            ):
                raise UnitizationReviewError("finalized unit lacks source hash links")
    return materialized


def _adjudication_review_ids(adjudication: Mapping[str, Any]) -> tuple[str, ...]:
    review_ids = _string_sequence(adjudication.get("review_ids"), "review_ids")
    if not review_ids:
        review_ids = (_required_str(adjudication, "review_id"),)
    return review_ids


def _added_unit_from_adjudication(
    adjudication: Mapping[str, Any],
    *,
    adjudication_id: str,
    review_ids: tuple[str, ...],
    candidate_reviews: Mapping[str, Mapping[str, Any]],
    raw_candidate_sha256: str,
    known_unit_ids: set[str],
) -> tuple[JsonRecord, JsonRecord]:
    """Return the unit an ADD adjudication introduces plus its provenance.

    ADD is the only disposition that resolves a review without consuming a
    source unit: a structural omission means the missing unit was never in the
    raw artifact, so deriving it from an unrelated raw unit would both destroy
    that unit and forge a hash link the added unit does not have.
    """

    if "source_unit_ids" in adjudication:
        declared_sources = _string_sequence(
            adjudication.get("source_unit_ids"), "source_unit_ids"
        )
        if declared_sources:
            raise UnitizationReviewError(
                f"{adjudication_id}: ADD must not consume source units"
            )
        raise UnitizationReviewError(
            f"{adjudication_id}: ADD must omit source_unit_ids"
        )
    finalized_units = _record_sequence(
        adjudication.get("finalized_units", ()), "finalized_units"
    )
    if len(finalized_units) != 1:
        raise UnitizationReviewError(f"{adjudication_id}: invalid ADD output count")
    proposed_unit = dict(finalized_units[0])
    unit_id = _required_str(proposed_unit, "unit_id")
    if unit_id in known_unit_ids:
        raise UnitizationReviewError(f"{adjudication_id}: duplicate added unit_id")
    if _PROVENANCE_KEYS.intersection(proposed_unit):
        raise UnitizationReviewError(
            f"{adjudication_id}: ADD unit may not declare its own provenance"
        )
    added_unit = _canonical_added_unit(proposed_unit, adjudication_id)
    flag_sha256, document_ids = _authenticated_omission_evidence(
        adjudication_id,
        review_ids=review_ids,
        reviews=candidate_reviews,
        raw_candidate_sha256=raw_candidate_sha256,
    )
    _require_cited_evidence(added_unit, adjudication_id, document_ids)
    provenance: JsonRecord = {
        "source_unit_sha256s": [],
        "adjudication_id": adjudication_id,
        "adjudication_sha256": canonical_sha256(adjudication),
        "disposition": UnitizationDisposition.ADD.value,
        "added_from_review_ids": list(review_ids),
        "structural_flag_sha256": flag_sha256,
        "raw_prediction_units_sha256": raw_candidate_sha256,
        "predecision_source_document_ids": list(document_ids),
    }
    return added_unit, provenance


def _canonical_added_unit(
    record: Mapping[str, Any], adjudication_id: str
) -> JsonRecord:
    """Return the sole strict, scorable prediction-unit form an ADD may emit."""

    try:
        decoded = prediction_unit_from_record(record)
    except (TypeError, ValueError) as error:
        raise UnitizationReviewError(
            f"{adjudication_id}: invalid canonical prediction unit: {error}"
        ) from error
    canonical = decoded.to_record()
    if dict(record) != canonical:
        raise UnitizationReviewError(
            f"{adjudication_id}: ADD unit must equal its canonical prediction unit"
        )
    if not decoded.should_score:
        raise UnitizationReviewError(
            f"{adjudication_id}: ADD unit must be a scorable motion target"
        )
    return canonical


def _require_added_unit_ledger_shape(record: Mapping[str, Any]) -> None:
    """Require the closed v3 envelope-ledger row shape."""

    if frozenset(record) != _ADDED_UNIT_LEDGER_KEYS:
        raise UnitizationReviewError("invalid added-unit ledger shape")
    _required_str(record, "unit_id")
    _required_str(record, "adjudication_id")
    _required_str(record, "adjudication_sha256")
    _required_str(record, "structural_flag_sha256")
    _required_str(record, "raw_prediction_units_sha256")
    if not _string_sequence(record.get("review_ids"), "review_ids"):
        raise UnitizationReviewError("added unit lacks review links")
    if record.get("disposition") != UnitizationDisposition.ADD.value:
        raise UnitizationReviewError("invalid added-unit disposition")


def _authenticated_omission_evidence(
    adjudication_id: str,
    *,
    review_ids: tuple[str, ...],
    reviews: Mapping[str, Mapping[str, Any]],
    raw_candidate_sha256: str,
) -> tuple[str, tuple[str, ...]]:
    """Return the flag hash and cited documents an ADD may rely on."""

    flag_hashes: set[str] = set()
    documents: set[str] = set()
    for review_id in review_ids:
        review = reviews[review_id]
        if _required_str(review, "route_reason") != STRUCTURAL_OMISSION_ROUTE_REASON:
            raise UnitizationReviewError(
                f"{adjudication_id}: ADD requires an omitted structural review"
            )
        if _required_str(review, "raw_prediction_units_sha256") != raw_candidate_sha256:
            raise UnitizationReviewError(
                f"{adjudication_id}: ADD evidence is bound to another raw candidate"
            )
        flag_hashes.add(_required_str(review, "structural_flag_sha256"))
        review_item = review.get("review_item")
        if not isinstance(review_item, Mapping):
            raise UnitizationReviewError(
                f"{adjudication_id}: ADD review lacks predecision citations"
            )
        cited = _string_sequence(
            cast(Mapping[str, Any], review_item).get("source_document_ids"),
            "source_document_ids",
        )
        if not cited:
            raise UnitizationReviewError(
                f"{adjudication_id}: ADD review lacks predecision citations"
            )
        documents.update(cited)
    if len(flag_hashes) != 1:
        raise UnitizationReviewError(
            f"{adjudication_id}: ADD must consume one structural omission flag"
        )
    return flag_hashes.pop(), tuple(sorted(documents))


def _require_cited_evidence(
    unit: Mapping[str, Any], adjudication_id: str, document_ids: tuple[str, ...]
) -> None:
    """Fail closed unless the added unit cites exactly the flagged documents."""

    cited = _cited_document_ids(unit)
    if not cited:
        raise UnitizationReviewError(
            f"{adjudication_id}: ADD unit lacks predecision citations"
        )
    if cited - set(document_ids):
        raise UnitizationReviewError(
            f"{adjudication_id}: ADD unit cites unauthenticated predecision documents"
        )
    if set(document_ids) - cited:
        raise UnitizationReviewError(
            f"{adjudication_id}: ADD unit does not cite every flagged document"
        )


def _cited_document_ids(unit: Mapping[str, Any]) -> set[str]:
    citations = _record_sequence(unit.get("source_citations", ()), "source_citations")
    return {_required_str(citation, "document_id") for citation in citations}


def _verify_added_unit(
    unit: Mapping[str, Any],
    *,
    candidate_id: str,
    schema_version: object,
    raw_candidate_sha256: str,
    raw_unit_ids: set[str],
    adjudications: Mapping[str, Mapping[str, Any]],
    reviews: Mapping[str, Mapping[str, Any]],
) -> str:
    """Re-derive an added unit's evidence chain and return its adjudication."""

    unit_id = _required_str(unit, "unit_id")
    if schema_version != STRUCTURAL_ADD_FINALIZED_SCHEMA_VERSION:
        raise UnitizationReviewError(f"added unit requires the v3 schema: {unit_id}")
    if unit_id in raw_unit_ids:
        raise UnitizationReviewError(f"added unit shadows a raw unit: {unit_id}")
    if unit.get("source_unit_sha256s") != []:
        raise UnitizationReviewError(
            f"added unit must not derive from raw units: {unit_id}"
        )
    adjudication_id = _required_str(unit, "adjudication_id")
    adjudication = adjudications.get(adjudication_id)
    if (
        adjudication is None
        or adjudication.get("disposition") != UnitizationDisposition.ADD.value
        or adjudication.get("candidate_id") != candidate_id
        or unit.get("adjudication_sha256") != canonical_sha256(adjudication)
    ):
        raise UnitizationReviewError(f"broken added-unit hash link: {unit_id}")
    if _string_sequence(adjudication.get("source_unit_ids"), "source_unit_ids"):
        raise UnitizationReviewError(f"added unit consumes source units: {unit_id}")
    finalized_units = _record_sequence(
        adjudication.get("finalized_units", ()), "finalized_units"
    )
    if len(finalized_units) != 1:
        raise UnitizationReviewError(f"invalid ADD output count: {adjudication_id}")
    expected_unit = _canonical_added_unit(finalized_units[0], adjudication_id)
    if _base_unit(unit) != expected_unit:
        raise UnitizationReviewError(
            f"added unit does not match adjudication output: {unit_id}"
        )
    review_ids = _adjudication_review_ids(adjudication)
    if review_ids != _string_sequence(
        unit.get("added_from_review_ids"), "added_from_review_ids"
    ) or any(
        review_id not in reviews
        or reviews[review_id].get("candidate_id") != candidate_id
        for review_id in review_ids
    ):
        raise UnitizationReviewError(f"broken added-unit review link: {unit_id}")
    flag_sha256, document_ids = _authenticated_omission_evidence(
        adjudication_id,
        review_ids=review_ids,
        reviews=reviews,
        raw_candidate_sha256=raw_candidate_sha256,
    )
    if (
        unit.get("structural_flag_sha256") != flag_sha256
        or unit.get("raw_prediction_units_sha256") != raw_candidate_sha256
        or _string_sequence(
            unit.get("predecision_source_document_ids"),
            "predecision_source_document_ids",
        )
        != document_ids
    ):
        raise UnitizationReviewError(f"broken added-unit evidence link: {unit_id}")
    _require_cited_evidence(unit, adjudication_id, document_ids)
    return adjudication_id


def _require_added_unit_shape(
    unit: Mapping[str, Any],
    *,
    schema_version: object,
    raw_candidate_sha256: str,
) -> None:
    """Reject an added unit whose self-contained bindings are incomplete."""

    unit_id = _required_str(unit, "unit_id")
    if schema_version != STRUCTURAL_ADD_FINALIZED_SCHEMA_VERSION:
        raise UnitizationReviewError(f"added unit requires the v3 schema: {unit_id}")
    if unit.get("source_unit_sha256s") != []:
        raise UnitizationReviewError(
            f"added unit must not derive from raw units: {unit_id}"
        )
    _canonical_added_unit(_base_unit(unit), _required_str(unit, "adjudication_id"))
    _required_str(unit, "adjudication_sha256")
    _required_str(unit, "structural_flag_sha256")
    if not _string_sequence(unit.get("added_from_review_ids"), "added_from_review_ids"):
        raise UnitizationReviewError(f"added unit lacks review links: {unit_id}")
    if _required_str(unit, "raw_prediction_units_sha256") != raw_candidate_sha256:
        raise UnitizationReviewError(
            f"added unit is bound to another raw candidate: {unit_id}"
        )
    document_ids = _string_sequence(
        unit.get("predecision_source_document_ids"),
        "predecision_source_document_ids",
    )
    if not document_ids:
        raise UnitizationReviewError(
            f"added unit lacks predecision citations: {unit_id}"
        )
    _require_cited_evidence(unit, _required_str(unit, "adjudication_id"), document_ids)


def _automatic_provenance(unit: Mapping[str, Any]) -> JsonRecord:
    digest = canonical_sha256(unit)
    return {
        "source_unit_sha256s": [digest],
        "adjudication_id": f"automatic:{digest}",
        "adjudication_sha256": None,
        "disposition": UnitizationDisposition.ACCEPT.value,
    }


def _base_unit(unit: Mapping[str, Any]) -> JsonRecord:
    return {key: value for key, value in unit.items() if key not in _PROVENANCE_KEYS}


def _validate_adjudication_header(record: Mapping[str, Any], *, case_id: str) -> None:
    schema_version = record.get("schema_version")
    if schema_version not in SUPPORTED_ADJUDICATION_SCHEMA_VERSIONS:
        raise UnitizationReviewError("unsupported unitization adjudication schema")
    if (
        _required_str(record, "disposition").upper() == UnitizationDisposition.ADD.value
        and schema_version != STRUCTURAL_ADD_ADJUDICATION_SCHEMA_VERSION
    ):
        raise UnitizationReviewError("ADD requires unitization adjudication schema v2")
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
    if disposition is UnitizationDisposition.ADD:
        if source_unit_ids or len(finalized_units) != 1:
            raise UnitizationReviewError("invalid ADD output count")
        return
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
