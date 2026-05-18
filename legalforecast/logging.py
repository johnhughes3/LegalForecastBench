"""Structured logging helpers for benchmark pipeline stages."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any, TextIO

PIPELINE_LOG_FIELDS = (
    "case_id",
    "source_hash",
    "stage",
    "decision",
    "exclusion_reason",
    "duration_ms",
    "cost_usd",
    "request_count",
)


@dataclass(frozen=True, slots=True)
class PipelineLogContext:
    """Shared context fields for case-pipeline logs and test failures."""

    case_id: str | None = None
    source_hash: str | None = None
    stage: str | None = None
    decision: str | None = None
    exclusion_reason: str | None = None
    duration_ms: int | None = None
    cost_usd: float | None = None
    request_count: int | None = None

    def as_extra(self) -> dict[str, object]:
        return {key: value for key, value in asdict(self).items() if value is not None}


def pipeline_log_extra(
    *,
    case_id: str | None = None,
    source_hash: str | None = None,
    stage: str | None = None,
    decision: str | None = None,
    exclusion_reason: str | None = None,
    duration_ms: int | None = None,
    cost_usd: float | None = None,
    request_count: int | None = None,
) -> dict[str, object]:
    """Return a logging ``extra`` mapping using the project pipeline fields."""

    return PipelineLogContext(
        case_id=case_id,
        source_hash=source_hash,
        stage=stage,
        decision=decision,
        exclusion_reason=exclusion_reason,
        duration_ms=duration_ms,
        cost_usd=cost_usd,
        request_count=request_count,
    ).as_extra()


class JsonFormatter(logging.Formatter):
    """Render log records as compact JSON with pipeline context fields."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field_name in PIPELINE_LOG_FIELDS:
            value = getattr(record, field_name, None)
            if value is not None:
                payload[field_name] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, sort_keys=True, allow_nan=False)


def configure_logging(
    *,
    level: int | str = logging.INFO,
    stream: TextIO | None = None,
    force: bool = True,
) -> None:
    """Configure root logging for local CLI runs and tests."""

    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=level, handlers=[handler], force=force)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def context_from_mapping(values: Mapping[str, Any]) -> PipelineLogContext:
    """Build context from a loose mapping, keeping only known pipeline fields."""

    known_values = {
        field_name: values[field_name]
        for field_name in PIPELINE_LOG_FIELDS
        if field_name in values
    }
    return PipelineLogContext(**known_values)
