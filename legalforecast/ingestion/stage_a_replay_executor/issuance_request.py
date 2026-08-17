"""Operator-supplied input to replay-spec issuance, and its typed accessors.

The issuance request carries only what no authenticated artifact can: which
candidates are authorized, what the ceilings are, where the successor and repair
artifacts live, and where outputs go.  Everything else the executor cross-checks
is derived from the predecessor run cards by :mod:`issuance`.

Keeping the request schema and the shared field readers here leaves the issuer
itself about deriving the descriptor rather than about parsing operator input.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path
from typing import cast

from legalforecast.ingestion.stage_a_replay_executor.contract import (
    StageAReplayExecutorError,
)
from legalforecast.ingestion.stage_a_replay_executor.contract import (
    parse_decimal as _parse_decimal,
)
from legalforecast.ingestion.stage_a_replay_executor.contract import (
    read_regular as _read_regular,
)

ISSUANCE_REQUEST_SCHEMA_VERSION = (
    # contract-ratchet: allow non-authoritative Stage A issuance-request sidecar
    "legalforecast.candidate_scoped_stage_a_issuance_request.v1"
)

REQUEST_FIELDS = frozenset(
    {
        "schema_version",
        "cycle_id",
        "lineage_index_path",
        "active_root_identity_sha256",
        "predecessor",
        "successor",
        "repair_receipt",
        "provider_accounts",
        "candidate_ids",
        "spend",
        "outputs_root",
    }
)
REQUEST_PREDECESSOR_FIELDS = frozenset(
    {
        "unitization_run_card_path",
        "structural_review_run_card_path",
        "finalized_prediction_units_path",
        "adjudications_path",
        "apply_unitization_run_card_path",
        "controlled_private_root",
        "initialization_receipt_path",
    }
)
REQUEST_SUCCESSOR_FIELDS = frozenset(
    {
        "selection_path",
        "selection_run_card_path",
        "download_manifest_path",
        "disclosure_clearance_path",
        "materialization_run_card_path",
        "document_root",
        "parse_requests_path",
        "parser_manifest_path",
        "parser_run_card_path",
        "markdown_root",
        "controlled_private_root",
        "initialization_receipt_path",
    }
)
REQUEST_REPAIR_FIELDS = frozenset(
    {
        "acquired_documents_path",
        "manifest_path",
        "approval_path",
        "snapshot_manifest_path",
        "source_lineage_path",
        "snapshots_root",
        "execution_path",
        "receipt_path",
        "expected_receipt_sha256",
    }
)
REQUEST_SPEND_FIELDS = frozenset(
    {
        "estimated_cost_usd",
        "hard_ceiling_usd",
        "per_candidate_ceiling_usd",
        "invocation_reservations_usd",
    }
)

__all__ = (
    "ISSUANCE_REQUEST_SCHEMA_VERSION",
    "REQUEST_FIELDS",
    "REQUEST_PREDECESSOR_FIELDS",
    "REQUEST_REPAIR_FIELDS",
    "REQUEST_SPEND_FIELDS",
    "REQUEST_SUCCESSOR_FIELDS",
    "decimal_field",
    "digest_field",
    "load_issuance_request",
    "mapping_field",
    "optional_path_text",
    "path_field",
    "request_candidate_ids",
    "text_field",
)


def load_issuance_request(path: str | Path) -> Mapping[str, object]:
    """Read and shape-check the operator-supplied issuance request."""

    source = Path(path).resolve()
    payload = _read_regular(source, "issuance request")
    try:
        loaded: object = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StageAReplayExecutorError("issuance request is not valid JSON") from exc
    if not isinstance(loaded, dict):
        raise StageAReplayExecutorError("issuance request must be a JSON object")
    request = cast(dict[str, object], loaded)
    if set(request) != set(REQUEST_FIELDS):
        raise StageAReplayExecutorError(
            f"issuance request fields differ from {sorted(REQUEST_FIELDS)}"
        )
    if request.get("schema_version") != ISSUANCE_REQUEST_SCHEMA_VERSION:
        raise StageAReplayExecutorError("issuance request schema_version differs")
    for section, fields in (
        ("predecessor", REQUEST_PREDECESSOR_FIELDS),
        ("successor", REQUEST_SUCCESSOR_FIELDS),
        ("repair_receipt", REQUEST_REPAIR_FIELDS),
        ("spend", REQUEST_SPEND_FIELDS),
    ):
        if set(mapping_field(request, section)) != set(fields):
            raise StageAReplayExecutorError(
                f"issuance request {section} fields differ from {sorted(fields)}"
            )
    return request


def request_candidate_ids(request: Mapping[str, object]) -> tuple[str, ...]:
    """Return the authorized candidate set in its operator-declared order."""

    value = request.get("candidate_ids")
    if not isinstance(value, list) or not value:
        raise StageAReplayExecutorError(
            "issuance request candidate_ids must be a non-empty array"
        )
    result: list[str] = []
    for item in cast(list[object], value):
        if not isinstance(item, str) or not item.strip():
            raise StageAReplayExecutorError(
                "issuance request candidate_id must be non-empty text"
            )
        if item in result:
            raise StageAReplayExecutorError(
                f"issuance request repeats candidate {item}"
            )
        result.append(item)
    return tuple(result)


def mapping_field(record: Mapping[str, object], field: str) -> Mapping[str, object]:
    value = record.get(field)
    if not isinstance(value, Mapping):
        raise StageAReplayExecutorError(f"{field} must be an object")
    return cast(Mapping[str, object], value)


def text_field(record: Mapping[str, object], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise StageAReplayExecutorError(f"{field} must be non-empty text")
    return value


def digest_field(record: Mapping[str, object], field: str) -> str:
    value = text_field(record, field).removeprefix("sha256:")
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise StageAReplayExecutorError(f"{field} must be a lowercase SHA-256 digest")
    return value


def decimal_field(record: Mapping[str, object], field: str) -> Decimal:
    return _parse_decimal(record.get(field), field)


def path_field(record: Mapping[str, object], field: str) -> Path:
    value = Path(text_field(record, field))
    if not value.is_absolute() or ".." in value.parts:
        raise StageAReplayExecutorError(f"{field} must be an absolute path")
    return value


def optional_path_text(record: Mapping[str, object], field: str) -> str | None:
    return None if record.get(field) is None else str(path_field(record, field))
