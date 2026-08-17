"""Shared validation primitives for the non-authoritative replay spec."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, cast

from legalforecast.contracts import ARTIFACT_CANONICAL_JSON_V1

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class StageAReplayExecutorError(ValueError):
    """Raised when executor authority or persisted evidence is invalid."""


class ReplaySpendCeilingError(StageAReplayExecutorError):
    """Raised when a provider invocation reaches signed spend authority."""

    def __init__(self, message: str, *, candidate_id: str | None = None) -> None:
        super().__init__(message)
        self.candidate_id = candidate_id


def validate_authorization(
    authorization: Mapping[str, object],
    candidate_ids: tuple[str, ...],
    *,
    now: datetime | None,
) -> Path:
    required = {
        "request_artifact_path",
        "request_artifact_sha256",
        "approval_text",
        "approval_sha256",
        "signature",
        "expires_at",
        "candidate_ids",
        "estimated_cost_usd",
        "hard_ceiling_usd",
    }
    if set(authorization) != required:
        raise StageAReplayExecutorError("signed authorization fields differ")
    request_path = path_value(authorization, "request_artifact_path")
    request_payload = read_regular(request_path, "authorization request artifact")
    request_sha256 = digest(authorization, "request_artifact_sha256")
    if hashlib.sha256(request_payload).hexdigest() != request_sha256:
        raise StageAReplayExecutorError(
            "authorization request artifact differs from its SHA-256 pin"
        )
    approval = text_value(authorization, "approval_text")
    if hashlib.sha256(approval.encode("utf-8")).hexdigest() != digest(
        authorization, "approval_sha256"
    ):
        raise StageAReplayExecutorError("signed authorization approval digest differs")
    signature = text_value(authorization, "signature")
    if signature not in {"John Hughes", "synthetic:true"}:
        raise StageAReplayExecutorError("signed authorization identity is unsupported")
    expiry_text = text_value(authorization, "expires_at")
    try:
        expiry = datetime.fromisoformat(expiry_text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise StageAReplayExecutorError(
            "signed authorization expiry is invalid"
        ) from exc
    if expiry.tzinfo is None:
        raise StageAReplayExecutorError(
            "signed authorization expiry must include timezone"
        )
    if (now or datetime.now(UTC)) >= expiry.astimezone(UTC):
        raise StageAReplayExecutorError("signed authorization has expired")
    if candidate_ids_value(authorization.get("candidate_ids"), "authorization") != (
        candidate_ids
    ):
        raise StageAReplayExecutorError("signed authorization candidate set differs")
    estimated = decimal_value(authorization, "estimated_cost_usd")
    hard_ceiling = decimal_value(authorization, "hard_ceiling_usd")
    if estimated > hard_ceiling:
        raise StageAReplayExecutorError(
            "signed authorization estimate exceeds its hard ceiling"
        )
    approval_tokens = (
        *candidate_ids,
        f"USD {estimated:.2f}",
        f"USD {hard_ceiling:.2f}",
    )
    if signature != "synthetic:true" and any(
        token not in approval for token in approval_tokens
    ):
        raise StageAReplayExecutorError(
            "signed authorization text does not bind candidates and spend ceilings"
        )
    return request_path


def validate_spend(
    spend: Mapping[str, object],
    authorization: Mapping[str, object],
    candidate_ids: tuple[str, ...],
) -> tuple[Decimal, dict[str, Decimal], dict[str, Decimal]]:
    if set(spend) != {
        "aggregate_ceiling_usd",
        "per_candidate_ceiling_usd",
        "invocation_reservations_usd",
    }:
        raise StageAReplayExecutorError("spend descriptor fields differ")
    aggregate = decimal_value(spend, "aggregate_ceiling_usd")
    if aggregate != decimal_value(authorization, "hard_ceiling_usd"):
        raise StageAReplayExecutorError(
            "spend aggregate ceiling differs from signed authorization hard ceiling"
        )
    per_raw = mapping_value(spend, "per_candidate_ceiling_usd")
    if set(per_raw) != set(candidate_ids):
        raise StageAReplayExecutorError(
            "spend per_candidate_ceiling_usd must cover exactly the candidate set"
        )
    per = {
        candidate: parse_decimal(per_raw[candidate], candidate)
        for candidate in candidate_ids
    }
    if any(value > aggregate for value in per.values()):
        raise StageAReplayExecutorError(
            "a per-candidate ceiling exceeds the aggregate ceiling"
        )
    reservations_raw = mapping_value(spend, "invocation_reservations_usd")
    if set(reservations_raw) != {"unitizer", "reviewer"}:
        raise StageAReplayExecutorError(
            "invocation reservations must name unitizer and reviewer"
        )
    reservations = {
        stage: parse_decimal(reservations_raw[stage], stage)
        for stage in ("unitizer", "reviewer")
    }
    return aggregate, per, reservations


def candidate_ids_value(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise StageAReplayExecutorError(
            f"{label} candidate_ids must be a non-empty array"
        )
    result: list[str] = []
    for item in cast(list[object], value):
        if not isinstance(item, str) or not item.strip():
            raise StageAReplayExecutorError(
                f"{label} candidate_id must be non-empty text"
            )
        if item in result:
            raise StageAReplayExecutorError(f"{label} repeats candidate {item}")
        result.append(item)
    return tuple(result)


def read_regular(path: Path, label: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise StageAReplayExecutorError(f"{label} is not a regular file: {path}")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise StageAReplayExecutorError(f"cannot read {label}: {path}") from exc


def parse_strict_jsonl(payload: bytes) -> tuple[Mapping[str, Any], ...]:
    """Decode non-empty object rows with an exact trailing newline."""

    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise StageAReplayExecutorError("Stage A JSONL is not UTF-8") from exc
    if not text.endswith("\n"):
        raise StageAReplayExecutorError("Stage A JSONL lacks its trailing newline")
    lines = text[:-1].split("\n")
    if any(not line for line in lines):
        raise StageAReplayExecutorError("Stage A JSONL contains a blank row")
    records: list[Mapping[str, Any]] = []
    for line in lines:
        value = json.loads(line)
        if not isinstance(value, Mapping):
            raise StageAReplayExecutorError("Stage A JSONL row is not an object")
        records.append(cast(Mapping[str, Any], value))
    if not records:
        raise StageAReplayExecutorError("Stage A JSONL is empty")
    return tuple(records)


def path_value(record: Mapping[str, object], field: str) -> Path:
    value = text_value(record, field)
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts or path.resolve() != path:
        raise StageAReplayExecutorError(f"{field} must be an absolute canonical path")
    return path


def optional_path(record: Mapping[str, object], field: str) -> Path | None:
    return None if record.get(field) is None else path_value(record, field)


def mapping_value(record: Mapping[str, object], field: str) -> Mapping[str, object]:
    value = record.get(field)
    if not isinstance(value, Mapping):
        raise StageAReplayExecutorError(f"{field} must be an object")
    return cast(Mapping[str, object], value)


def text_value(record: Mapping[str, object], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise StageAReplayExecutorError(f"{field} must be non-empty text")
    return value


def digest(record: Mapping[str, object], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise StageAReplayExecutorError(f"{field} must be a lowercase SHA-256 digest")
    return value


def decimal_value(record: Mapping[str, object], field: str) -> Decimal:
    return parse_decimal(record.get(field), field)


def parse_decimal(value: object, field: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise StageAReplayExecutorError(f"{field} must be a non-negative decimal")
    try:
        parsed = Decimal(str(value))
    except InvalidOperation as exc:
        raise StageAReplayExecutorError(
            f"{field} must be a non-negative decimal"
        ) from exc
    if not parsed.is_finite() or parsed < 0:
        raise StageAReplayExecutorError(f"{field} must be a non-negative decimal")
    return parsed


def canonical(value: object) -> bytes:
    return ARTIFACT_CANONICAL_JSON_V1.encode(value)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
