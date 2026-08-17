"""Read-only spend snapshots for the canonical Stage A provider journal."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Protocol

from legalforecast.contracts import ARTIFACT_CANONICAL_JSON_V1
from legalforecast.evals.model_registry import ModelRegistryEntry
from legalforecast.ingestion.candidate_scoped_stage_a_replay import (
    CandidateScopedStageARerunRequest,
    StageAStageOutcome,
)
from legalforecast.ingestion.stage_a_replay_executor.spec import (
    ReplaySpec,
    StageAReplayExecutorError,
)
from legalforecast.labeling.provider_journal import (
    ProviderCallIdentity,
    ProviderJournalError,
    open_provider_journal_snapshot,
    provider_prompt_logical_call_scope,
    verify_provider_journal_identity,
)


class ProviderRuntime(Protocol):
    spec: ReplaySpec

    def call_identity(
        self,
        request: CandidateScopedStageARerunRequest,
        *,
        stage: str,
        unitize: StageAStageOutcome | None,
    ) -> tuple[ProviderCallIdentity, ModelRegistryEntry, str, str]: ...


@dataclass(frozen=True, slots=True)
class StageSpendSnapshot:
    """Exact logical-call spend before one executor callback."""

    logical_call_key: str
    provider_stage: str
    candidate_id: str
    stage: str
    model_key: str
    provider: str
    account: str
    prompt: str
    prompt_sha256: str
    committed_usd: Decimal
    attempt_count: int
    maximum_new_attempts: int
    logical_call_scope: str | None = None


@dataclass(frozen=True, slots=True)
class StageSpend:
    """Authoritative incremental spend and terminal journal evidence."""

    actual_usd: Decimal
    attempt_count: int
    new_attempt_count: int
    logical_call_key: str
    provider_stage: str
    prompt_sha256: str
    attempts: tuple[Mapping[str, object], ...]


class JournalSpendMeter:
    """Measure only rows matching the exact callback prompt and model identity."""

    def __init__(self, runtime: ProviderRuntime) -> None:
        self.runtime = runtime

    def before(
        self,
        request: CandidateScopedStageARerunRequest,
        *,
        stage: str,
        unitize: StageAStageOutcome | None,
    ) -> StageSpendSnapshot:
        identity, entry, account, provider_stage = self.runtime.call_identity(
            request, stage=stage, unitize=unitize
        )
        committed, rows = journal_rows(
            self.runtime.spec.provider_journal_path,
            identity=identity,
            provider=entry.provider,
            account=account,
        )
        return StageSpendSnapshot(
            logical_call_key=identity.logical_call_key,
            provider_stage=provider_stage,
            candidate_id=request.candidate_id,
            stage=stage,
            model_key=entry.registry_key,
            provider=entry.provider,
            account=account,
            prompt=identity.prompt,
            prompt_sha256=identity.prompt_sha256,
            committed_usd=committed,
            attempt_count=len(rows),
            maximum_new_attempts=_maximum_new_attempts(rows, stage=stage),
            logical_call_scope=identity.logical_call_scope,
        )

    def after(self, before: StageSpendSnapshot) -> StageSpend:
        logical_call_scope = None
        if before.logical_call_scope is not None:
            logical_call_scope = provider_prompt_logical_call_scope(before.prompt)
            if before.logical_call_scope != logical_call_scope:
                raise StageAReplayExecutorError(
                    "provider logical-call scope differs from the exact prompt"
                )
        identity = ProviderCallIdentity(
            stage=_base_stage(before.stage),
            candidate_id=before.candidate_id,
            model_key=before.model_key,
            prompt=before.prompt,
            model_registry_sha256=self.runtime.spec.model_registry_sha256,
            account=before.account,
            prompt_contract=_namespace(before.stage),
            logical_call_scope=logical_call_scope,
        )
        committed, rows = journal_rows(
            self.runtime.spec.provider_journal_path,
            identity=identity,
            provider=before.provider,
            account=before.account,
        )
        if identity.logical_call_key != before.logical_call_key:
            raise StageAReplayExecutorError("provider logical-call identity changed")
        delta = committed - before.committed_usd
        if delta < 0:
            raise StageAReplayExecutorError("provider journal spend moved backwards")
        new_attempt_count = len(rows) - before.attempt_count
        if new_attempt_count < 0:
            raise StageAReplayExecutorError(
                "provider journal attempt count moved backwards"
            )
        return StageSpend(
            actual_usd=delta,
            attempt_count=len(rows),
            new_attempt_count=new_attempt_count,
            logical_call_key=before.logical_call_key,
            provider_stage=before.provider_stage,
            prompt_sha256=before.prompt_sha256,
            attempts=rows,
        )


def terminal_route_available(
    path: Path,
    *,
    identity: ProviderCallIdentity,
    provider: str,
    account: str,
    stage: str,
) -> bool:
    """Recognize only the frozen unitizer/reviewer terminal retry routes."""

    _committed, rows = journal_rows(
        path, identity=identity, provider=provider, account=account
    )
    return _terminal_route_from_rows(rows, stage=stage)


def _terminal_route_from_rows(
    rows: tuple[Mapping[str, object], ...], *, stage: str
) -> bool:
    if len(rows) > 3:
        raise StageAReplayExecutorError(
            f"{stage} provider journal contains a forbidden fourth attempt"
        )
    failures = [row for row in rows if row["status"] == "reconstruction_failed"]
    if stage == "unitizer":
        return len(rows) == 3 and len(failures) == 3
    if stage != "reviewer":
        raise StageAReplayExecutorError("invalid terminal-route stage")
    if len(rows) == 3 and len(failures) == 3:
        return True
    if len(rows) != 2 or len(failures) != 2:
        return False
    first, second = failures
    return all(
        first.get(field) == second.get(field) and bool(first.get(field))
        for field in (
            "normalized_response_sha256",
            "failure_type",
            "failure_message",
        )
    )


def _maximum_new_attempts(rows: tuple[Mapping[str, object], ...], *, stage: str) -> int:
    if _terminal_route_from_rows(rows, stage=stage):
        return 0
    if any(row["status"] == "reconstruction_failed" for row in rows):
        if len(rows) < 3:
            return 3 - len(rows)
        raise StageAReplayExecutorError(
            f"{stage} provider journal exhausted without a valid terminal route"
        )
    return 3


def journal_rows(
    path: Path,
    *,
    identity: ProviderCallIdentity,
    provider: str,
    account: str,
) -> tuple[Decimal, tuple[Mapping[str, object], ...]]:
    snapshot = open_provider_journal_snapshot(path)
    try:
        rows = snapshot.execute(
            """
            SELECT logical_call_key, attempt_ordinal, stage, candidate_id,
                   model_key, provider, account, prompt_sha256, prompt_text,
                   model_registry_sha256, reservation_usd, actual_cost_usd,
                   status, failure_type, failure_message,
                   normalized_response_json
            FROM provider_attempts
            WHERE logical_call_key = ? AND stage = ? AND candidate_id = ?
              AND model_key = ? AND provider = ? AND account = ?
              AND prompt_sha256 = ? AND prompt_text = ?
              AND model_registry_sha256 = ?
            ORDER BY attempt_ordinal
            """,
            (
                identity.logical_call_key,
                identity.stage,
                identity.candidate_id,
                identity.model_key,
                provider,
                account,
                identity.prompt_sha256,
                identity.prompt,
                identity.model_registry_sha256,
            ),
        ).fetchall()
    finally:
        snapshot.close()
    evidence: list[Mapping[str, object]] = []
    total = Decimal("0")
    for row in rows:
        actual = row["actual_cost_usd"]
        reservation = Decimal(str(row["reservation_usd"]))
        committed = Decimal(str(actual)) if actual is not None else reservation
        total += committed
        item: dict[str, object] = {
            "logical_call_key": str(row["logical_call_key"]),
            "attempt_ordinal": int(row["attempt_ordinal"]),
            "stage": str(row["stage"]),
            "candidate_id": str(row["candidate_id"]),
            "model_key": str(row["model_key"]),
            "provider": str(row["provider"]),
            "account": str(row["account"]),
            "prompt_sha256": str(row["prompt_sha256"]),
            "model_registry_sha256": str(row["model_registry_sha256"]),
            "reservation_usd": format(reservation, "f"),
            "actual_cost_usd": None
            if actual is None
            else format(Decimal(str(actual)), "f"),
            "status": str(row["status"]),
            "failure_type": row["failure_type"],
            "failure_message": row["failure_message"],
        }
        normalized = row["normalized_response_json"]
        item["normalized_response_sha256"] = (
            None
            if normalized is None
            else hashlib.sha256(str(normalized).encode()).hexdigest()
        )
        item["attempt_record_sha256"] = hashlib.sha256(
            ARTIFACT_CANONICAL_JSON_V1.encode(item)
        ).hexdigest()
        evidence.append(item)
    return total, tuple(evidence)


def verify_journal(spec: ReplaySpec) -> None:
    snapshot = None
    try:
        snapshot = open_provider_journal_snapshot(spec.provider_journal_path)
        verify_provider_journal_identity(
            spec.provider_journal_path,
            cycle_id=spec.cycle_id,
            provider_cycle_caps_sha256=spec.provider_caps_sha256,
            snapshot=snapshot,
        )
    except ProviderJournalError as exc:
        raise StageAReplayExecutorError(str(exc)) from exc
    finally:
        if snapshot is not None:
            snapshot.close()


def _base_stage(stage: str) -> str:
    return "llm-unitize" if stage == "unitizer" else "llm-review-stage-a"


def _namespace(stage: str) -> str:
    return "claim-ontology-v5" if stage == "unitizer" else "claim-ontology-v4"
