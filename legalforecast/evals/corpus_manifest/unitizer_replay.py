# pyright: reportPrivateUsage=false, reportUnusedFunction=false
"""Query-only adoption of authenticated historical Stage A responses."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from legalforecast.evals.live_model_solver import (
    LiveModelSolverError,
    validate_provider_response_fields,
)
from legalforecast.evals.model_registry import ModelRegistryEntry
from legalforecast.labeling.llm_pipeline import (
    LlmBatchResult,
    LlmPipelineError,
    reconstruct_stage_a_unitization_response,
    stage_a_unitization_prompt_records,
    unitization_review_queue_records_from_items,
)
from legalforecast.labeling.provider_journal import (
    open_provider_journal_snapshot,
    verify_provider_journal_identity,
)

from .unitizer_shared import JsonRecord, ManifestUnitizerCommandError


def _verify_reconstructed_audits(
    actual: Sequence[JsonRecord], *, expected: Sequence[JsonRecord]
) -> None:
    if len(actual) != len(expected):
        raise ManifestUnitizerCommandError(
            "provider-free reconstruction audit count differs from fresh-five evidence"
        )
    fields = (
        "candidate_id",
        "case_id",
        "status",
        "model_key",
        "provider_prompt_sha256",
        "input_tokens",
        "output_tokens",
        "estimated_cost",
        "raw_output_sha256",
        "unit_count",
        "scorable_unit_count",
        "review_items",
        "unitization_review_queue",
    )
    for actual_row, expected_row in zip(actual, expected, strict=True):
        for field in fields:
            if actual_row.get(field) != expected_row.get(field):
                raise ManifestUnitizerCommandError(
                    f"{actual_row.get('candidate_id')}: reconstructed audit differs "
                    f"from fresh-five evidence at {field}"
                )


def _adopt_authenticated_unitization_replays(
    *,
    selection_records: Sequence[JsonRecord],
    parser_records: Sequence[JsonRecord],
    markdown_root: Path,
    markdown_bytes: Mapping[str, bytes],
    registry_entry: ModelRegistryEntry,
    model_registry_sha256: str,
    provider_journal_path: Path,
    provider_cycle_id: str,
    provider_cycle_caps_sha256: str,
    provider_account: str,
    provider_attempt_namespace: str,
) -> LlmBatchResult:
    """Adopt exact settled pre-authority responses without opening a writer.

    This is intentionally a narrow bridge for the five current prompts whose
    canonical journal rows already settled before shared authority ordinals
    existed.  It never inserts or updates a journal/authority row.  A missing
    exact prompt match is a structural halt, so the changed-material 72288139
    row cannot accidentally trigger a new provider call.
    """

    prompt_records = stage_a_unitization_prompt_records(
        selection_records=selection_records,
        parser_records=parser_records,
        markdown_root=markdown_root,
        markdown_bytes=markdown_bytes,
        provider_attempt_namespace=provider_attempt_namespace,
    )
    prompt_by_candidate = {
        str(record["candidate_id"]): record for record in prompt_records
    }
    snapshot = open_provider_journal_snapshot(provider_journal_path)
    try:
        verify_provider_journal_identity(
            provider_journal_path,
            cycle_id=provider_cycle_id,
            provider_cycle_caps_sha256=provider_cycle_caps_sha256,
            snapshot=snapshot,
        )
        adopted: list[tuple[JsonRecord, sqlite3.Row, str]] = []
        missing: list[str] = []
        for selection in selection_records:
            candidate_id = str(selection["candidate_id"])
            prompt_record = prompt_by_candidate[candidate_id]
            prompt_sha256 = str(prompt_record["prompt_sha256"]).removeprefix("sha256:")
            rows = snapshot.execute(
                """
                SELECT * FROM provider_attempts
                WHERE stage = 'llm-unitize'
                  AND candidate_id = ?
                  AND model_key = ?
                  AND provider = ?
                  AND account = ?
                  AND prompt_sha256 = ?
                  AND model_registry_sha256 IN (?, ?)
                  AND status = 'settled'
                ORDER BY attempt_ordinal
                """,
                (
                    candidate_id,
                    registry_entry.registry_key,
                    registry_entry.provider,
                    provider_account,
                    prompt_sha256,
                    model_registry_sha256,
                    "sha256:" + model_registry_sha256,
                ),
            ).fetchall()
            if len(rows) != 1 or rows[0]["authority_attempt_ordinal"] is not None:
                missing.append(candidate_id)
                continue
            prompt = str(prompt_record["prompt"])
            if rows[0]["prompt_text"] != prompt:
                missing.append(candidate_id)
                continue
            adopted.append((selection, rows[0], prompt))
        if missing:
            raise ManifestUnitizerCommandError(
                "provider-free adoption structural halt: no exact settled "
                "pre-authority response exists for "
                + ", ".join(sorted(missing))
                + "; no provider call was attempted"
            )

        records: list[JsonRecord] = []
        audits: list[JsonRecord] = []
        for selection, row, _prompt in adopted:
            normalized_json = row["normalized_response_json"]
            raw_response_json = row["raw_response_json"]
            if not isinstance(normalized_json, str) or not isinstance(
                raw_response_json, str
            ):
                raise ManifestUnitizerCommandError(
                    f"{selection['candidate_id']}: settled journal row lacks "
                    "complete response evidence"
                )
            try:
                normalized = json.loads(normalized_json)
                raw_response = json.loads(raw_response_json)
            except json.JSONDecodeError as exc:
                raise ManifestUnitizerCommandError(
                    f"{selection['candidate_id']}: settled journal response is "
                    "not valid JSON"
                ) from exc
            if not isinstance(normalized, Mapping) or not isinstance(
                raw_response, Mapping
            ):
                raise ManifestUnitizerCommandError(
                    f"{selection['candidate_id']}: settled journal response "
                    "must be JSON objects"
                )
            normalized = cast(Mapping[str, object], normalized)
            raw_response = cast(Mapping[str, object], raw_response)
            try:
                response_fields = validate_provider_response_fields(
                    registry_entry, raw_response
                )
            except (LiveModelSolverError, ValueError) as exc:
                raise ManifestUnitizerCommandError(
                    f"{selection['candidate_id']}: raw provider response is "
                    f"invalid: {exc}"
                ) from exc
            try:
                input_tokens = int(cast(Any, normalized.get("input_tokens", -1)))
                output_tokens = int(cast(Any, normalized.get("output_tokens", -1)))
                estimated_cost = float(
                    cast(Any, normalized.get("actual_cost_usd", -1.0))
                )
            except (TypeError, ValueError) as exc:
                raise ManifestUnitizerCommandError(
                    f"{selection['candidate_id']}: settled journal accounting "
                    "is malformed"
                ) from exc
            if (
                input_tokens != int(row["input_tokens"])
                or output_tokens != int(row["output_tokens"])
                or estimated_cost != float(row["actual_cost_usd"])
                or response_fields.input_tokens != input_tokens
                or response_fields.output_tokens != output_tokens
            ):
                raise ManifestUnitizerCommandError(
                    f"{selection['candidate_id']}: settled journal accounting "
                    "does not match its normalized response"
                )
            raw_output = normalized.get("raw_output")
            if not isinstance(raw_output, str) or not raw_output:
                raise ManifestUnitizerCommandError(
                    f"{selection['candidate_id']}: settled journal lacks raw output"
                )
            expected_cost = (
                input_tokens * float(registry_entry.input_token_price)
                + output_tokens * float(registry_entry.output_token_price)
            ) / 1_000_000
            if (
                response_fields.raw_output != raw_output
                or abs(estimated_cost - expected_cost) > 1e-12
            ):
                raise ManifestUnitizerCommandError(
                    f"{selection['candidate_id']}: raw response and frozen accounting "
                    "do not match normalized journal evidence"
                )
            try:
                result = reconstruct_stage_a_unitization_response(
                    selection_record=selection,
                    parser_records=parser_records,
                    markdown_root=markdown_root,
                    markdown_bytes=markdown_bytes,
                    raw_output=raw_output,
                    model_key=registry_entry.registry_key,
                    provider_attempt_namespace=provider_attempt_namespace,
                )
            except (LlmPipelineError, ValueError) as exc:
                raise ManifestUnitizerCommandError(
                    f"{selection['candidate_id']}: authenticated journal replay "
                    f"failed current-input reconstruction: {exc}"
                ) from exc
            case_id = str(selection["case_id"])
            review_queue = unitization_review_queue_records_from_items(
                candidate_id=str(selection["candidate_id"]),
                case_id=case_id,
                review_items=(item.to_record() for item in result.review_items),
            )
            records.append(
                {
                    "candidate_id": str(selection["candidate_id"]),
                    "case_id": case_id,
                    "prediction_units": [unit.to_record() for unit in result.units],
                }
            )
            audits.append(
                {
                    "stage": "llm-unitize",
                    "status": "adjudication_pending" if review_queue else "succeeded",
                    "candidate_id": str(selection["candidate_id"]),
                    "case_id": case_id,
                    "model_key": registry_entry.registry_key,
                    "model_registry_sha256": "sha256:" + model_registry_sha256,
                    "provider_prompt_sha256": str(
                        "sha256:"
                        + hashlib.sha256(str(_prompt).encode("utf-8")).hexdigest()
                    ),
                    "provider_called": False,
                    "provider_replay_adopted": True,
                    "historical_provider_attempt_ordinal": int(row["attempt_ordinal"]),
                    "human_verified": False,
                    "unit_count": len(result.units),
                    "scorable_unit_count": sum(
                        unit.should_score for unit in result.units
                    ),
                    "review_items": [item.to_record() for item in result.review_items],
                    "unitization_review_queue": [
                        dict(record) for record in review_queue
                    ],
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "estimated_cost": estimated_cost,
                    "raw_output_sha256": "sha256:"
                    + hashlib.sha256(raw_output.encode()).hexdigest(),
                    "metadata": {
                        "provider_response_sha256": hashlib.sha256(
                            raw_response_json.encode()
                        ).hexdigest(),
                        "normalized_response_sha256": hashlib.sha256(
                            normalized_json.encode()
                        ).hexdigest(),
                        "provider_attempt_count": "0",
                    },
                }
            )
        return LlmBatchResult(records=tuple(records), audit_records=tuple(audits))
    finally:
        snapshot.close()
