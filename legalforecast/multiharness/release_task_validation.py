"""Validation of selected outcome-blinded release task metadata."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from legalforecast.contracts import FORECAST_RELEASE_V1
from legalforecast.release.models import ForecastRelease


def validate_selected_release_task_metadata(
    task: Any,
    *,
    required_unit_ids: tuple[str, ...],
    units_by_id: Mapping[str, Any],
    forecast_release: ForecastRelease,
) -> None:
    """Bind selected task metadata to the exact forecast release contract."""

    metadata = task.metadata
    expected_schema = str(FORECAST_RELEASE_V1)
    if metadata.get("release_schema_version") != expected_schema:
        raise ValueError("selected release task schema does not match forecast")
    if metadata.get("release_id") != forecast_release.release_id:
        raise ValueError("selected release task release_id does not match forecast")
    if metadata.get("forecast_release_digest") != forecast_release.release_digest:
        raise ValueError(
            "selected release task forecast_release_digest does not match forecast"
        )

    raw_unit_ids = metadata.get("unit_ids")
    if raw_unit_ids is not None:
        if not isinstance(raw_unit_ids, list | tuple):
            raise ValueError(
                "selected release task unit_ids do not match required units"
            )
        unit_ids = cast(list[Any] | tuple[Any, ...], raw_unit_ids)
        if tuple(unit_ids) != (*required_unit_ids,):
            raise ValueError(
                "selected release task unit_ids do not match required units"
            )
    expected_scoreable = tuple(
        unit_id for unit_id in required_unit_ids if units_by_id[unit_id].should_score
    )
    raw_scoreable = metadata.get("scoreable_unit_ids")
    if raw_scoreable is not None:
        if not isinstance(raw_scoreable, list | tuple):
            raise ValueError(
                "selected release task scoreable_unit_ids do not match forecast"
            )
        scoreable_ids = cast(list[Any] | tuple[Any, ...], raw_scoreable)
        if tuple(scoreable_ids) != (*expected_scoreable,):
            raise ValueError(
                "selected release task scoreable_unit_ids do not match forecast"
            )
    should_score = metadata.get("should_score")
    if not isinstance(should_score, bool) or should_score != bool(expected_scoreable):
        raise ValueError("selected release task should_score does not match forecast")

    raw_unit_id = metadata.get("unit_id")
    if raw_unit_id is not None and (
        not isinstance(raw_unit_id, str)
        or len(required_unit_ids) != 1
        or raw_unit_id != required_unit_ids[0]
    ):
        raise ValueError("selected release task unit_id does not match required units")

    raw_unit_metadata = metadata.get("unit_metadata")
    if raw_unit_metadata is None:
        return
    if not isinstance(raw_unit_metadata, list):
        raise ValueError("selected release task unit_metadata does not match units")
    unit_metadata = cast(list[Any], raw_unit_metadata)
    if len(unit_metadata) != len(required_unit_ids):
        raise ValueError("selected release task unit_metadata does not match units")
    records_by_id: dict[str, Mapping[str, Any]] = {}
    for raw_record in unit_metadata:
        if not isinstance(raw_record, Mapping):
            raise ValueError("selected release task unit_metadata is invalid")
        record = cast(Mapping[str, Any], raw_record)
        unit_id = record.get("unit_id")
        if not isinstance(unit_id, str) or unit_id in records_by_id:
            raise ValueError("selected release task unit_metadata has invalid IDs")
        records_by_id[unit_id] = record
    if tuple(records_by_id) != required_unit_ids:
        raise ValueError("selected release task unit_metadata IDs do not match units")
    for unit_id in required_unit_ids:
        value = records_by_id[unit_id].get("should_score")
        if value is not units_by_id[unit_id].should_score:
            raise ValueError(
                "selected release task unit_metadata should_score does not match"
            )
