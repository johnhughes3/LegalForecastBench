"""Convert a completed attorney worksheet into Stage A adjudication records."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from legalforecast.ingestion.canonical_json import canonical_json_value_bytes
from legalforecast.unitization.review import (
    ADJUDICATION_SCHEMA_VERSION,
    STRUCTURAL_ADD_ADJUDICATION_SCHEMA_VERSION,
    TERMINAL_UNITIZER_ADJUDICATION_SCHEMA_VERSION,
    UnitizationDisposition,
)
from legalforecast.unitization.schemas import prediction_unit_from_record

JsonRecord = dict[str, Any]

_PACKET_SCHEMA = "legalforecast.successor_attorney_packet_view.v2"
_FINAL_STATUS = "final"
_REQUIRED_COLUMNS = (
    "surface",
    "candidate_id",
    "case_id",
    "review_ids_json",
    "unit_id",
    "reason_code",
    "allowed_actions",
    "terminal_escalation_sha256",
    "adjudication_group",
    "final_disposition",
    "adjudication_notes",
    "drop_or_exclusion_reason",
    "finalized_units_json",
    "decision_status",
)


class AttorneyWorksheetError(ValueError):
    """Raised when a worksheet cannot produce unambiguous adjudications."""


@dataclass(frozen=True, slots=True)
class AttorneyWorksheetResult:
    """Separate ordinary and terminal adjudication streams."""

    ordinary_adjudications: tuple[JsonRecord, ...]
    terminal_adjudications: tuple[JsonRecord, ...]


@dataclass(frozen=True, slots=True)
class _ExpectedRow:
    surface: str
    candidate_id: str
    case_id: str
    review_ids: tuple[str, ...]
    unit_id: str
    reason_code: str
    allowed_actions: tuple[str, ...]
    terminal_escalation_sha256: str
    raw_unit_ids: tuple[str, ...]


def convert_attorney_worksheet(
    *,
    packet: Mapping[str, Any],
    worksheet_tsv: str,
    adjudicator_id: str,
) -> AttorneyWorksheetResult:
    """Authenticate packet-derived TSV fields and emit closed adjudications."""

    if not adjudicator_id.strip():
        raise AttorneyWorksheetError("adjudicator_id is required")
    expected = _expected_rows(packet)
    rows = _read_rows(worksheet_tsv)
    if len(rows) != len(expected):
        raise AttorneyWorksheetError(
            f"worksheet row count mismatch: expected {len(expected)}, got {len(rows)}"
        )

    seen_reviews: set[str] = set()
    grouped: dict[tuple[str, str, str], list[tuple[_ExpectedRow, dict[str, str]]]] = (
        defaultdict(list)
    )
    for line_number, row in enumerate(rows, start=2):
        review_ids = _json_string_list(
            row["review_ids_json"], f"line {line_number} review_ids_json"
        )
        if not review_ids:
            raise AttorneyWorksheetError(
                f"line {line_number}: review_ids_json must not be empty"
            )
        overlap = seen_reviews.intersection(review_ids)
        if overlap:
            raise AttorneyWorksheetError(
                f"line {line_number}: duplicate review coverage: {sorted(overlap)}"
            )
        try:
            expected_row = expected[review_ids]
        except KeyError as error:
            raise AttorneyWorksheetError(
                f"line {line_number}: unknown review_ids_json"
            ) from error
        _authenticate_row(row, expected_row, line_number=line_number)
        seen_reviews.update(review_ids)
        group = row["adjudication_group"].strip() or review_ids[0]
        grouped[(expected_row.surface, expected_row.candidate_id, group)].append(
            (expected_row, row)
        )

    expected_reviews = {review for key in expected for review in key}
    if seen_reviews != expected_reviews:
        raise AttorneyWorksheetError(
            "worksheet does not cover every packet review exactly once"
        )

    ordinary: list[JsonRecord] = []
    terminal: list[JsonRecord] = []
    for group_key in sorted(grouped):
        entries = grouped[group_key]
        record = _adjudication_from_group(entries, adjudicator_id=adjudicator_id)
        if group_key[0] == "unitizer_terminal":
            terminal.append(record)
        else:
            ordinary.append(record)
    _require_complete_candidate_exclusions(ordinary, expected)
    return AttorneyWorksheetResult(tuple(ordinary), tuple(terminal))


def _expected_rows(
    packet: Mapping[str, Any],
) -> dict[tuple[str, ...], _ExpectedRow]:
    if packet.get("schema_version") != _PACKET_SCHEMA:
        raise AttorneyWorksheetError("unsupported successor attorney packet schema")
    candidates = _record_list(packet.get("candidates"), "packet candidates")
    expected: dict[tuple[str, ...], _ExpectedRow] = {}
    for candidate in candidates:
        candidate_id = _required_text(candidate, "candidate_id")
        case_id = _required_text(candidate, "case_id")
        if "unitizer_terminal" in candidate:
            terminal = _record(candidate["unitizer_terminal"], "unitizer_terminal")
            queue = _record(terminal.get("queue_record"), "terminal queue_record")
            review_ids = (_required_text(queue, "review_id"),)
            row = _ExpectedRow(
                surface="unitizer_terminal",
                candidate_id=candidate_id,
                case_id=case_id,
                review_ids=review_ids,
                unit_id="",
                reason_code=_required_text(
                    _record(queue.get("reason"), "terminal reason"), "code"
                ),
                allowed_actions=_string_list(
                    queue.get("allowed_actions"), "terminal allowed_actions"
                ),
                terminal_escalation_sha256=_required_text(
                    queue, "terminal_escalation_sha256"
                ),
                raw_unit_ids=(),
            )
            expected[review_ids] = row
            continue

        authoritative = _record(candidate.get("authoritative_v1"), "authoritative_v1")
        observational = _record(candidate.get("observational_v2"), "observational_v2")
        if observational.get("terminal_technical_item") is not None:
            raise AttorneyWorksheetError(
                "structural terminal technical reviews are not supported by "
                "the worksheet compiler"
            )
        bundles = _record_list(authoritative.get("bundle_records"), "bundle_records")
        raw_unit_ids = _raw_unit_ids(bundles)
        unit_items = _record_list(observational.get("unit_items"), "unit_items")
        for item in unit_items:
            review_ids = _string_list(
                item.get("source_review_ids"), "source_review_ids"
            )
            if not review_ids:
                review_ids = (_required_text(item, "review_id"),)
            reason = _record(item.get("reason"), "ordinary reason")
            row = _ExpectedRow(
                surface="ordinary",
                candidate_id=candidate_id,
                case_id=case_id,
                review_ids=review_ids,
                unit_id=_required_text(item, "unit_id"),
                reason_code=_required_text(reason, "code"),
                allowed_actions=_string_list(
                    item.get("allowed_actions"), "ordinary allowed_actions"
                ),
                terminal_escalation_sha256="",
                raw_unit_ids=raw_unit_ids,
            )
            if review_ids in expected:
                raise AttorneyWorksheetError("packet repeats review coverage")
            expected[review_ids] = row
    return expected


def _read_rows(payload: str) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(payload), delimiter="\t")
    if reader.fieldnames is None:
        raise AttorneyWorksheetError("worksheet lacks a header")
    missing = set(_REQUIRED_COLUMNS) - set(reader.fieldnames)
    if missing:
        raise AttorneyWorksheetError(
            f"worksheet lacks required columns: {sorted(missing)}"
        )
    rows: list[dict[str, str]] = []
    for line_number, raw in enumerate(reader, start=2):
        if None in raw:
            raise AttorneyWorksheetError(f"line {line_number}: too many TSV fields")
        if any(value is None for value in raw.values()):
            raise AttorneyWorksheetError(f"line {line_number}: missing TSV fields")
        rows.append({key: str(value) for key, value in raw.items()})
    return rows


def _authenticate_row(
    row: Mapping[str, str], expected: _ExpectedRow, *, line_number: int
) -> None:
    immutable = {
        "surface": expected.surface,
        "candidate_id": expected.candidate_id,
        "case_id": expected.case_id,
        "unit_id": expected.unit_id,
        "reason_code": expected.reason_code,
        "allowed_actions": "|".join(expected.allowed_actions),
        "terminal_escalation_sha256": expected.terminal_escalation_sha256,
    }
    for field, value in immutable.items():
        if row[field] != value:
            raise AttorneyWorksheetError(
                f"line {line_number}: immutable {field} differs from packet"
            )
    if row["decision_status"].strip().lower() != _FINAL_STATUS:
        raise AttorneyWorksheetError(f"line {line_number}: decision is not final")


def _adjudication_from_group(
    entries: Sequence[tuple[_ExpectedRow, dict[str, str]]], *, adjudicator_id: str
) -> JsonRecord:
    first_expected, first_row = entries[0]
    decision_fields = (
        "final_disposition",
        "adjudication_notes",
        "drop_or_exclusion_reason",
        "finalized_units_json",
        "decision_status",
    )
    if any(
        row[field] != first_row[field]
        for _, row in entries[1:]
        for field in decision_fields
    ):
        raise AttorneyWorksheetError("grouped worksheet rows disagree on decision")
    if any(
        expected.case_id != first_expected.case_id
        or expected.surface != first_expected.surface
        for expected, _ in entries[1:]
    ):
        raise AttorneyWorksheetError("adjudication group crosses case or surface")

    disposition_text = first_row["final_disposition"].strip().upper()
    try:
        disposition = UnitizationDisposition(disposition_text)
    except ValueError as error:
        raise AttorneyWorksheetError(
            f"unsupported disposition: {disposition_text or '<blank>'}"
        ) from error
    if any(
        disposition.value not in expected.allowed_actions for expected, _ in entries
    ):
        raise AttorneyWorksheetError(
            "disposition is not allowed for every grouped review"
        )
    notes = first_row["adjudication_notes"].strip()
    if not notes:
        raise AttorneyWorksheetError("adjudication_notes is required")
    review_ids = tuple(
        review_id for expected, _ in entries for review_id in expected.review_ids
    )
    source_unit_ids = tuple(dict.fromkeys(expected.unit_id for expected, _ in entries))
    finalized_units = _json_record_list(
        first_row["finalized_units_json"], "finalized_units_json"
    )
    reason = first_row["drop_or_exclusion_reason"].strip()

    if first_expected.surface == "unitizer_terminal":
        if len(entries) != 1:
            raise AttorneyWorksheetError("terminal adjudication cannot span rows")
        if disposition not in {
            UnitizationDisposition.ADD,
            UnitizationDisposition.CANDIDATE_EXCLUSION,
        }:
            raise AttorneyWorksheetError("invalid terminal disposition")
        record: JsonRecord = {
            "schema_version": TERMINAL_UNITIZER_ADJUDICATION_SCHEMA_VERSION,
            "candidate_id": first_expected.candidate_id,
            "case_id": first_expected.case_id,
            "review_ids": list(review_ids),
            "terminal_escalation_sha256": first_expected.terminal_escalation_sha256,
            "disposition": disposition.value,
            "finalized_units": finalized_units,
            "adjudicator_id": adjudicator_id,
            "adjudication_notes": notes,
        }
        if disposition is UnitizationDisposition.ADD:
            if not finalized_units or reason:
                raise AttorneyWorksheetError(
                    "terminal ADD requires units and no exclusion reason"
                )
        else:
            if finalized_units or not reason:
                raise AttorneyWorksheetError(
                    "terminal exclusion requires a reason and no units"
                )
            record["exclusion_reason"] = reason
        record["adjudication_id"] = _adjudication_id(record)
        return record

    if disposition is UnitizationDisposition.ADD:
        if len(entries) != 1 or first_expected.reason_code != "structural_omitted":
            raise AttorneyWorksheetError("ordinary ADD requires one omission review")
        if len(finalized_units) != 1 or reason:
            raise AttorneyWorksheetError("ordinary ADD requires exactly one unit")
        schema = STRUCTURAL_ADD_ADJUDICATION_SCHEMA_VERSION
    else:
        schema = ADJUDICATION_SCHEMA_VERSION
        _validate_ordinary_shape(
            disposition,
            source_unit_ids=source_unit_ids,
            finalized_units=finalized_units,
            reason=reason,
        )
    record = {
        "schema_version": schema,
        "candidate_id": first_expected.candidate_id,
        "case_id": first_expected.case_id,
        "review_ids": list(review_ids),
        "disposition": disposition.value,
        "finalized_units": finalized_units,
        "adjudicator_id": adjudicator_id,
        "adjudication_notes": notes,
    }
    if disposition is not UnitizationDisposition.ADD:
        record["source_unit_ids"] = list(source_unit_ids)
    if disposition is UnitizationDisposition.DROP:
        record["drop_reason"] = reason
    elif disposition is UnitizationDisposition.CANDIDATE_EXCLUSION:
        record["source_unit_ids"] = list(first_expected.raw_unit_ids)
        record["exclusion_reason"] = reason
    record["adjudication_id"] = _adjudication_id(record)
    return record


def _validate_ordinary_shape(
    disposition: UnitizationDisposition,
    *,
    source_unit_ids: Sequence[str],
    finalized_units: Sequence[Mapping[str, Any]],
    reason: str,
) -> None:
    if disposition is UnitizationDisposition.MERGE:
        if len(source_unit_ids) < 2 or len(finalized_units) != 1:
            raise AttorneyWorksheetError("MERGE requires two units and one replacement")
    elif disposition is UnitizationDisposition.SPLIT:
        if len(source_unit_ids) != 1 or len(finalized_units) < 2:
            raise AttorneyWorksheetError("SPLIT requires one unit and two replacements")
    elif disposition is UnitizationDisposition.AMEND:
        if len(source_unit_ids) != 1 or len(finalized_units) != 1:
            raise AttorneyWorksheetError("AMEND requires one unit and one replacement")
    elif disposition in {UnitizationDisposition.ACCEPT, UnitizationDisposition.DROP}:
        if len(source_unit_ids) != 1 or finalized_units:
            raise AttorneyWorksheetError(
                f"{disposition.value} requires one unit and no replacements"
            )
    elif disposition is UnitizationDisposition.CANDIDATE_EXCLUSION:
        if finalized_units:
            raise AttorneyWorksheetError("candidate exclusion cannot emit units")
    else:
        raise AttorneyWorksheetError("invalid ordinary disposition")
    if disposition in {
        UnitizationDisposition.DROP,
        UnitizationDisposition.CANDIDATE_EXCLUSION,
    }:
        if not reason:
            raise AttorneyWorksheetError(f"{disposition.value} requires a reason")
    elif reason:
        raise AttorneyWorksheetError(
            f"{disposition.value} cannot declare a drop or exclusion reason"
        )


def _require_complete_candidate_exclusions(
    adjudications: Sequence[Mapping[str, Any]],
    expected: Mapping[tuple[str, ...], _ExpectedRow],
) -> None:
    reviews_by_candidate: dict[str, set[str]] = defaultdict(set)
    for expected_row in expected.values():
        if expected_row.surface == "ordinary":
            reviews_by_candidate[expected_row.candidate_id].update(
                expected_row.review_ids
            )
    for adjudication in adjudications:
        if adjudication["disposition"] != UnitizationDisposition.CANDIDATE_EXCLUSION:
            continue
        candidate_id = str(adjudication["candidate_id"])
        if set(adjudication["review_ids"]) != reviews_by_candidate[candidate_id]:
            raise AttorneyWorksheetError(
                "candidate exclusion must group every candidate review"
            )


def _raw_unit_ids(bundles: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    unit_sets: set[tuple[str, ...]] = set()
    for bundle in bundles:
        raw = _record(bundle.get("raw_prediction_units"), "raw_prediction_units")
        units = _record_list(raw.get("prediction_units"), "prediction_units")
        unit_sets.add(tuple(_required_text(unit, "unit_id") for unit in units))
    if len(unit_sets) != 1:
        raise AttorneyWorksheetError("candidate bundle raw units disagree")
    return next(iter(unit_sets))


def _adjudication_id(record: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(
        canonical_json_value_bytes(
            dict(record),
            error_type=AttorneyWorksheetError,
            error_message="adjudication is not canonical JSON",
        )
    ).hexdigest()
    return f"attorney:{digest}"


def _json_string_list(value: str, label: str) -> tuple[str, ...]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise AttorneyWorksheetError(f"{label} is not valid JSON") from error
    return _string_list(parsed, label)


def _json_record_list(value: str, label: str) -> list[JsonRecord]:
    if not value.strip():
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise AttorneyWorksheetError(f"{label} is not valid JSON") from error
    records = list(_record_list(parsed, label))
    for record in records:
        try:
            canonical = prediction_unit_from_record(record).to_record()
        except ValueError as error:
            raise AttorneyWorksheetError(
                f"{label} contains an invalid prediction unit: {error}"
            ) from error
        if record != canonical:
            raise AttorneyWorksheetError(
                f"{label} prediction unit must equal its canonical record"
            )
    return records


def _record(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise AttorneyWorksheetError(f"{label} must be an object")
    return cast(Mapping[str, Any], value)


def _record_list(value: object, label: str) -> tuple[JsonRecord, ...]:
    if not isinstance(value, list):
        raise AttorneyWorksheetError(f"{label} must be an array of objects")
    items = cast(list[object], value)
    if any(not isinstance(item, Mapping) for item in items):
        raise AttorneyWorksheetError(f"{label} must be an array of objects")
    return tuple(dict(cast(Mapping[str, Any], item)) for item in items)


def _string_list(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise AttorneyWorksheetError(f"{label} must be an array of strings")
    items = cast(list[object], value)
    if any(not isinstance(item, str) or not item.strip() for item in items):
        raise AttorneyWorksheetError(f"{label} must be an array of strings")
    return tuple(cast(str, item) for item in items)


def _required_text(record: Mapping[str, Any], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise AttorneyWorksheetError(f"{field} is required")
    return value
