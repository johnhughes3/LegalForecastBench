"""Fail-closed, provider-free repair of a saved Grok summary overrun."""

from __future__ import annotations

import math
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from legalforecast.contracts import (
    ARTIFACT_CANONICAL_JSON_V1,
    ARTIFACT_RAW_SHA256_V1,
    PUBLIC_RUN_IDENTITY_V1,
    PUBLIC_RUN_RECEIPT_V1,
    RAW_BYTES_RAW_SHA256_V1,
)
from legalforecast.evals.live_model_solver import (
    _estimated_cost,  # pyright: ignore[reportPrivateUsage]
)
from legalforecast.evals.model_registry import (
    ModelRegistryEntry,
    model_registry_entry_sha256,
)
from legalforecast.evals.provider_spend_control import (
    PROVIDER_SPEND_CONTROL_SCHEMA_VERSION,
    ProviderSpendKey,
)
from legalforecast.immutable_io import read_single_link_file
from legalforecast.release import ForecastExecution

from .packets import JEV_REQUEST_BYTE_BUDGET, case_documents
from .summaries import SUMMARY_PROMPT_VERSION, DocumentSummary, SummaryCache

KNOWN_OUTPUT_OVERRUN_POISON = "observed provider cost exceeds frozen reservation"
SUMMARY_REQUEST_OUTPUT_TOKENS = 8192
_GROK = ("vercel_ai_gateway", "spacexai/grok-4.6")
_ACCOUNT, _STAGE, _ABLATION, _REPEAT = "jev-summaries", "document_summary", "none", 1
_RECOVERY_SCHEMA = "legalforecast.jev.summary_recovery.v1"


class SummaryRecoveryError(ValueError):
    """Saved cache and ledger evidence cannot be reconciled safely."""


@dataclass(frozen=True, slots=True)
class SummaryRecoveryResult:
    recovery_id: str
    attempt_id: str
    already_recovered: bool
    cache_sha256: str
    response_sha256: str
    input_tokens: int
    output_tokens: int
    actual_microusd: int
    prior_settled_microusd: int
    settled_microusd: int
    attempt_count: int
    poison_reason: str


def recover_saved_overrun(
    execution: ForecastExecution,
    *,
    entry: ModelRegistryEntry,
    cache_path: Path,
    ledger_path: Path,
    ceiling_microusd: int,
) -> SummaryRecoveryResult:
    """Settle one cached Grok overrun without a provider call."""
    if (entry.provider, entry.model_id) != _GROK:
        raise SummaryRecoveryError("saved overrun recovery is limited to Grok 4.6")
    if type(ceiling_microusd) is not int or ceiling_microusd <= 0:
        raise SummaryRecoveryError("ceiling_microusd must be a positive integer")
    release = execution.release
    entry_hash = model_registry_entry_sha256(entry)
    authority_id = str(
        ARTIFACT_RAW_SHA256_V1.commit(
            {
                "release": release.release_digest,
                "model": entry_hash,
                "prompt": SUMMARY_PROMPT_VERSION,
                "request_byte_budget": JEV_REQUEST_BYTE_BUDGET,
            },
            domain=PUBLIC_RUN_IDENTITY_V1,
        ).digest
    )
    cache_bytes = read_single_link_file(cache_path, label="summary cache")
    cache_sha = str(
        RAW_BYTES_RAW_SHA256_V1.commit(cache_bytes, domain=PUBLIC_RUN_RECEIPT_V1).digest
    )
    cache = SummaryCache.from_bytes(cache_bytes, release.release_digest)
    records = _records(cache, entry, execution)

    db = sqlite3.connect(ledger_path, timeout=30)
    db.row_factory = sqlite3.Row
    try:
        db.execute("BEGIN IMMEDIATE")
        metadata = db.execute(
            "SELECT * FROM provider_spend_metadata WHERE singleton = 1"
        ).fetchone()
        if metadata is None:
            raise SummaryRecoveryError("summary ledger has no authority metadata")
        _metadata(
            metadata,
            ledger_path,
            authority_id,
            release.release_id,
            entry.provider,
            ceiling_microusd,
        )
        _create_event_table(db)
        events = db.execute(
            "SELECT * FROM jev_summary_recovery_events ORDER BY recovered_at_epoch"
        ).fetchall()
        if len(events) > 1:
            raise SummaryRecoveryError("summary ledger has multiple recovery events")
        event = events[0] if events else None
        attempts = db.execute(
            "SELECT * FROM provider_attempts ORDER BY attempt_ordinal, attempt_id"
        ).fetchall()
        target, saved = _attempts(
            attempts,
            records,
            release.release_id,
            entry,
            str(event["attempt_id"]) if event is not None else None,
        )
        response_sha = _response(saved)
        actual = _cost(saved)
        recovery_id = str(
            ARTIFACT_RAW_SHA256_V1.commit(
                {
                    "attempt_id": str(target["attempt_id"]),
                    "cache_sha256": cache_sha,
                    "input_tokens": saved.input_tokens,
                    "output_tokens": saved.output_tokens,
                    "response_sha256": response_sha,
                },
                domain=PUBLIC_RUN_RECEIPT_V1,
            ).digest
        )
        if event is not None:
            if metadata["authority_poisoned"] != 0:
                raise SummaryRecoveryError("recovery event exists while poisoned")
            _event(
                event,
                recovery_id,
                str(target["attempt_id"]),
                cache_sha,
                saved,
                response_sha,
                actual,
            )
            if str(target["status"]) != "settled":
                raise SummaryRecoveryError("recovery event exists before settlement")
            db.commit()
            prior = _settled_total(attempts)
            return _result(
                recovery_id,
                target,
                saved,
                cache_sha,
                response_sha,
                actual,
                prior - actual,
                prior,
                True,
                len(attempts),
            )

        if metadata["authority_poisoned"] != 1:
            raise SummaryRecoveryError("ledger is not in the known poisoned state")
        if target["status"] != "reserved":
            raise SummaryRecoveryError("saved overrun target is not reserved")
        if saved.output_tokens <= SUMMARY_REQUEST_OUTPUT_TOKENS:
            raise SummaryRecoveryError("saved target is not the known output overrun")
        old_reservation = int(target["reservation_microusd"])
        if actual <= old_reservation:
            raise SummaryRecoveryError("saved target cost does not exceed reservation")
        prior = _settled_total(attempts)
        if prior + actual > ceiling_microusd:
            raise SummaryRecoveryError("recovered summary cost would exceed the cap")
        now = time.time()
        attempt_id = str(target["attempt_id"])
        db.execute(
            """UPDATE provider_attempts SET status='settled', reservation_microusd=?,
               input_tokens=?, output_tokens=?, actual_microusd=?,
               response_sha256=?, completed_at_epoch=?
               WHERE attempt_id=? AND status='reserved'""",
            (
                max(old_reservation, actual),
                saved.input_tokens,
                saved.output_tokens,
                actual,
                response_sha,
                now,
                attempt_id,
            ),
        )
        if db.execute("SELECT changes()").fetchone()[0] != 1:
            raise SummaryRecoveryError("target reservation changed during recovery")
        db.execute(
            """INSERT INTO jev_summary_recovery_events
               (recovery_id,schema_version,attempt_id,cache_sha256,poison_reason,
                reservation_microusd,input_tokens,output_tokens,actual_microusd,
                response_sha256,recovered_at_epoch)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                recovery_id,
                _RECOVERY_SCHEMA,
                attempt_id,
                cache_sha,
                KNOWN_OUTPUT_OVERRUN_POISON,
                old_reservation,
                saved.input_tokens,
                saved.output_tokens,
                actual,
                response_sha,
                now,
            ),
        )
        db.execute(
            "UPDATE provider_spend_metadata SET authority_poisoned=0 "
            "WHERE singleton=1 AND authority_poisoned=1"
        )
        if db.execute("SELECT changes()").fetchone()[0] != 1:
            raise SummaryRecoveryError("ledger poison state changed during recovery")
        db.commit()
        return _result(
            recovery_id,
            target,
            saved,
            cache_sha,
            response_sha,
            actual,
            prior,
            prior + actual,
            False,
            len(attempts),
        )
    except BaseException:
        if db.in_transaction:
            db.rollback()
        raise
    finally:
        db.close()


def _records(
    cache: SummaryCache, entry: ModelRegistryEntry, execution: ForecastExecution
) -> dict[str, DocumentSummary]:
    raw = getattr(cache, "_records", None)
    if not isinstance(raw, dict):
        raise SummaryRecoveryError("summary cache records are unavailable")
    sources: dict[str, str] = {}
    for case in execution.release.cases:
        units = tuple(
            u for u in execution.release.prediction_units if u.case_id == case.case_id
        )
        for doc in case_documents(execution, units):
            sources[_identity(case.case_id, doc.document_id)] = doc.source_sha256
    result: dict[str, DocumentSummary] = {}
    for case_id, docs in cast(dict[str, dict[str, object]], raw).items():
        for document_id, value in docs.items():
            if not isinstance(value, DocumentSummary):
                raise SummaryRecoveryError("summary cache contains an invalid record")
            if (
                value.model != entry.model_id
                or value.prompt_version != SUMMARY_PROMPT_VERSION
            ):
                raise SummaryRecoveryError("summary cache model or prompt differs")
            expected_cost = _estimated_cost(
                entry,
                input_tokens=value.input_tokens,
                output_tokens=value.output_tokens,
            )
            if _cost(value) != math.ceil(expected_cost * 1_000_000):
                raise SummaryRecoveryError("summary cache estimated cost differs")
            key = _identity(case_id, document_id)
            if sources.get(key) != value.source_sha256 or key in result:
                raise SummaryRecoveryError("summary cache source or identity differs")
            result[key] = value
    return result


def _attempts(
    attempts: list[sqlite3.Row],
    records: dict[str, DocumentSummary],
    cycle_id: str,
    entry: ModelRegistryEntry,
    target_id: str | None,
) -> tuple[sqlite3.Row, DocumentSummary]:
    if len(attempts) != len(records):
        raise SummaryRecoveryError("summary cache and ledger counts differ")
    target: tuple[sqlite3.Row, DocumentSummary] | None = None
    seen: set[str] = set()
    reserved = 0
    for row in attempts:
        key = str(row["case_id"])
        summary = records.get(key)
        if summary is None or key in seen:
            raise SummaryRecoveryError("summary cache and ledger identities differ")
        seen.add(key)
        expected = _key(cycle_id, entry, key)
        for field, value in (
            ("logical_call_key", expected.logical_call_key),
            ("cycle_id", cycle_id),
            ("provider", entry.provider),
            ("account", _ACCOUNT),
            ("stage", _STAGE),
            ("model_key", entry.registry_key),
            ("ablation", _ABLATION),
            ("repeat_index", _REPEAT),
        ):
            if row[field] != value:
                raise SummaryRecoveryError(f"summary ledger attempt mismatch: {field}")
        status = str(row["status"])
        if status == "settled":
            if (
                int(row["input_tokens"]) != summary.input_tokens
                or int(row["output_tokens"]) != summary.output_tokens
                or int(row["actual_microusd"]) != _cost(summary)
                or str(row["response_sha256"]) != _response(summary)
            ):
                raise SummaryRecoveryError("settled ledger evidence differs from cache")
        elif status == "reserved":
            reserved += 1
            if target is not None:
                raise SummaryRecoveryError("more than one reserved summary attempt")
            target = (row, summary)
        else:
            raise SummaryRecoveryError(f"unsupported summary attempt state: {status}")
    if seen != set(records) or reserved > 1:
        raise SummaryRecoveryError("summary cache and ledger identities differ")
    if target_id is not None:
        matches = [
            (row, records[str(row["case_id"])])
            for row in attempts
            if str(row["attempt_id"]) == target_id
        ]
        if len(matches) != 1:
            raise SummaryRecoveryError("recovery target attempt is missing")
        target = matches[0]
    if target is None:
        raise SummaryRecoveryError("saved overrun target is missing")
    if target_id is not None and reserved:
        raise SummaryRecoveryError("recovery ledger has an unexpected reservation")
    return target


def _metadata(
    row: sqlite3.Row, path: Path, authority: str, cycle: str, provider: str, cap: int
) -> None:
    expected = (
        ("schema_version", PROVIDER_SPEND_CONTROL_SCHEMA_VERSION),
        ("authority_identity_sha256", authority),
        ("canonical_path", str(path.resolve())),
        ("cycle_id", cycle),
        ("provider", provider),
        ("account", _ACCOUNT),
        ("cap_microusd", cap),
        ("reservation_ledger_sha256", authority),
        ("max_billable_attempts", 1),
        ("failure_threshold", 1),
        ("failure_window_seconds", 86_400),
        ("poison_reason", KNOWN_OUTPUT_OVERRUN_POISON),
    )
    for name, value in expected:
        if row[name] != value:
            raise SummaryRecoveryError(f"summary ledger metadata mismatch: {name}")


def _create_event_table(db: sqlite3.Connection) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS jev_summary_recovery_events(
      recovery_id TEXT PRIMARY KEY, schema_version TEXT NOT NULL,
      attempt_id TEXT NOT NULL UNIQUE, cache_sha256 TEXT NOT NULL,
      poison_reason TEXT NOT NULL, reservation_microusd INTEGER NOT NULL,
      input_tokens INTEGER NOT NULL, output_tokens INTEGER NOT NULL,
      actual_microusd INTEGER NOT NULL, response_sha256 TEXT NOT NULL,
      recovered_at_epoch REAL NOT NULL)""")


def _event(
    row: sqlite3.Row,
    recovery: str,
    attempt: str,
    cache: str,
    summary: DocumentSummary,
    response: str,
    actual: int,
) -> None:
    expected = (
        ("recovery_id", recovery),
        ("schema_version", _RECOVERY_SCHEMA),
        ("attempt_id", attempt),
        ("cache_sha256", cache),
        ("poison_reason", KNOWN_OUTPUT_OVERRUN_POISON),
        ("input_tokens", summary.input_tokens),
        ("output_tokens", summary.output_tokens),
        ("actual_microusd", actual),
        ("response_sha256", response),
    )
    for name, value in expected:
        if row[name] != value:
            raise SummaryRecoveryError(f"saved recovery evidence differs: {name}")
    if not (0 < int(row["reservation_microusd"]) < actual):
        raise SummaryRecoveryError("saved recovery reservation evidence differs")


def _key(cycle: str, entry: ModelRegistryEntry, identity: str) -> ProviderSpendKey:
    return ProviderSpendKey(
        cycle,
        entry.provider,
        _ACCOUNT,
        _STAGE,
        entry.registry_key,
        identity,
        _ABLATION,
        _REPEAT,
    )


def _identity(case: str, document: str) -> str:
    return (
        ARTIFACT_CANONICAL_JSON_V1.encode({"case_id": case, "document_id": document})
        .decode()
        .strip()
    )


def _cost(summary: DocumentSummary) -> int:
    return math.ceil(summary.estimated_cost_usd * 1_000_000)


def _response(summary: DocumentSummary) -> str:
    return str(
        RAW_BYTES_RAW_SHA256_V1.commit(
            summary.text.encode(), domain=PUBLIC_RUN_RECEIPT_V1
        ).digest
    )


def _settled_total(attempts: list[sqlite3.Row]) -> int:
    return sum(
        int(row["actual_microusd"]) for row in attempts if row["status"] == "settled"
    )


def _result(
    recovery: str,
    row: sqlite3.Row,
    summary: DocumentSummary,
    cache: str,
    response: str,
    actual: int,
    prior: int,
    settled: int,
    already: bool,
    count: int,
) -> SummaryRecoveryResult:
    return SummaryRecoveryResult(
        recovery,
        str(row["attempt_id"]),
        already,
        cache,
        response,
        summary.input_tokens,
        summary.output_tokens,
        actual,
        prior,
        settled,
        count,
        KNOWN_OUTPUT_OVERRUN_POISON,
    )
