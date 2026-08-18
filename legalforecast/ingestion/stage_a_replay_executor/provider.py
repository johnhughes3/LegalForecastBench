"""Canonical v5/v4 provider callbacks and authoritative journal accounting."""

from __future__ import annotations

import hashlib
import os
import sqlite3
from collections.abc import Mapping, Sequence
from decimal import Decimal
from importlib import import_module
from pathlib import Path
from typing import Any, Protocol, cast

from legalforecast.contracts import ARTIFACT_CANONICAL_JSON_V1
from legalforecast.evals.model_registry import (
    ModelRegistry,
    ModelRegistryEntry,
    load_model_registry_bytes,
    model_registry_entry_sha256,
)
from legalforecast.ingestion.candidate_scoped_stage_a_replay import (
    CandidateScopedStageARerunRequest,
    StageAStageOutcome,
)
from legalforecast.ingestion.stage_a_replay_executor.journal import (
    terminal_route_available,
    verify_journal,
)
from legalforecast.ingestion.stage_a_replay_executor.lineage import (
    VerifiedReplayLineage,
)
from legalforecast.ingestion.stage_a_replay_executor.spec import (
    REVIEWER_CONFIG_NAMESPACE,
    UNITIZER_CONFIG_NAMESPACE,
    ReplaySpec,
    StageAReplayExecutorError,
)
from legalforecast.labeling import llm_pipeline, unitizer_terminal
from legalforecast.labeling.provider_journal import (
    ProviderCallIdentity,
    ProviderCycleCaps,
    ProviderJournalError,
    load_provider_cycle_caps_bytes,
    maximum_call_cost_usd,
    open_provider_journal_snapshot,
    provider_prompt_logical_call_scope,
    public_account_alias,
    verify_provider_journal_identity,
)

# Load terminal-review code before the executor captures its runtime Git identity.
import_module("legalforecast.unitization.unitizer_terminal_review")


class _StageABatchResult(Protocol):
    @property
    def audit_records(self) -> Sequence[Mapping[str, object]]: ...

    @property
    def records(self) -> Sequence[Mapping[str, object]]: ...


class CanonicalProviderRuntime:
    """Verified model registry, caps, callbacks, and prompt identities."""

    def __init__(self, spec: ReplaySpec, lineage: VerifiedReplayLineage) -> None:
        if spec.synthetic_fixture:
            raise StageAReplayExecutorError(
                "synthetic replay specs cannot bind production provider callbacks"
            )
        self.spec = spec
        self.lineage = lineage
        provider = _mapping(spec.record, "provider")
        registry_path = Path(_text(provider, "model_registry_path"))
        caps_path = Path(_text(provider, "provider_cycle_caps_path"))
        registry_payload = _read_regular(registry_path, "model registry")
        caps_payload = _read_regular(caps_path, "provider cycle caps")
        if hashlib.sha256(registry_payload).hexdigest() != spec.model_registry_sha256:
            raise StageAReplayExecutorError(
                "model registry hash differs from replay-spec"
            )
        if hashlib.sha256(caps_payload).hexdigest() != spec.provider_caps_sha256:
            raise StageAReplayExecutorError(
                "provider cycle caps hash differs from replay-spec"
            )
        try:
            self.registry = load_model_registry_bytes(registry_payload)
            self.caps = load_provider_cycle_caps_bytes(caps_payload, source=caps_path)
        except (ProviderJournalError, ValueError) as exc:
            raise StageAReplayExecutorError(str(exc)) from exc
        if self.caps.cycle_id != spec.cycle_id:
            raise StageAReplayExecutorError("provider cycle caps cycle_id differs")
        self.unitizer_entry = _registry_entry(self.registry, spec.model_ids["unitizer"])
        self.reviewer_entry = _registry_entry(self.registry, spec.model_ids["reviewer"])
        configuration = _mapping(spec.record, "configuration")
        for stage, entry in (
            ("unitizer", self.unitizer_entry),
            ("reviewer", self.reviewer_entry),
        ):
            expected_entry = _digest(
                _mapping(configuration, stage), "model_entry_sha256"
            )
            if model_registry_entry_sha256(entry) != expected_entry:
                raise StageAReplayExecutorError(
                    f"{stage} model entry differs from replay-spec"
                )
        accounts = _mapping(provider, "provider_accounts")
        self.accounts = _validated_provider_accounts(
            accounts,
            (self.unitizer_entry, self.reviewer_entry),
            self.caps,
            spec,
        )
        self.provider_caps_usd = {
            name: self.caps.cap_usd(name) for name in self.caps.providers
        }
        for stage, entry in (
            ("unitizer", self.unitizer_entry),
            ("reviewer", self.reviewer_entry),
        ):
            maximum = Decimal(
                str(
                    maximum_call_cost_usd(
                        context_limit=entry.context_limit,
                        max_output_tokens=entry.max_output_tokens,
                        input_token_price=entry.input_token_price,
                        output_token_price=entry.output_token_price,
                    )
                )
            )
            if spec.invocation_reservations_usd[stage] < maximum:
                raise StageAReplayExecutorError(
                    f"{stage} reservation is below the pinned model maximum cost"
                )
        verify_journal(spec)

    def call_identity(
        self,
        request: CandidateScopedStageARerunRequest,
        *,
        stage: str,
        unitize: StageAStageOutcome | None,
    ) -> tuple[ProviderCallIdentity, ModelRegistryEntry, str, str]:
        if stage == "unitizer":
            entry = self.unitizer_entry
            namespace = UNITIZER_CONFIG_NAMESPACE
            [prompt_record] = llm_pipeline.stage_a_unitization_prompt_records(
                selection_records=(request.packet.selection_record,),
                parser_records=self.lineage.successor_parser_records,
                markdown_root=self.lineage.successor_markdown_root,
                markdown_bytes=self.lineage.successor_markdown_bytes,
                provider_attempt_namespace=namespace,
            )
        elif stage == "reviewer" and unitize is not None:
            entry = self.reviewer_entry
            namespace = REVIEWER_CONFIG_NAMESPACE
            [prompt_record] = llm_pipeline.stage_a_structural_review_prompt_records(
                selection_records=(request.packet.selection_record,),
                parser_records=self.lineage.successor_parser_records,
                prediction_unit_records=unitize.records,
                markdown_root=self.lineage.successor_markdown_root,
                provider_attempt_namespace=namespace,
            )
        else:
            raise StageAReplayExecutorError("invalid Stage A provider stage")
        prompt = _text(prompt_record, "prompt")
        account = self.accounts[entry.provider.lower()]
        identity = ProviderCallIdentity(
            stage=_base_stage(stage),
            candidate_id=request.candidate_id,
            model_key=entry.registry_key,
            prompt=prompt,
            model_registry_sha256=self.spec.model_registry_sha256,
            account=account,
            prompt_contract=namespace,
            logical_call_scope=provider_prompt_logical_call_scope(prompt),
        )
        provider_stage = llm_pipeline.stage_a_provider_attempt_stage(
            _base_stage(stage), namespace
        )
        return identity, entry, account, provider_stage

    def unitizer(
        self, request: CandidateScopedStageARerunRequest
    ) -> StageAStageOutcome:
        identity, entry, account, _provider_stage = self.call_identity(
            request, stage="unitizer", unitize=None
        )
        exhausted = terminal_route_available(
            self.spec.provider_journal_path,
            identity=identity,
            provider=entry.provider,
            account=account,
            stage="unitizer",
        )
        if exhausted:
            return self._unitizer_terminal(request)
        try:
            result = llm_pipeline.llm_unitize_cases(
                selection_records=(request.packet.selection_record,),
                parser_records=self.lineage.successor_parser_records,
                markdown_root=self.lineage.successor_markdown_root,
                markdown_bytes=self.lineage.successor_markdown_bytes,
                registry_entry=entry,
                model_registry_sha256=self.spec.model_registry_sha256,
                provider_journal_path=self.spec.provider_journal_path,
                provider_cycle_caps_usd=self.provider_caps_usd,
                provider_cycle_id=self.spec.cycle_id,
                provider_cycle_caps_sha256=self.spec.provider_caps_sha256,
                provider_accounts={entry.provider.lower(): account},
                provider_attempt_namespace=UNITIZER_CONFIG_NAMESPACE,
                provider_logical_call_scope=identity.logical_call_scope,
            )
        except Exception:
            if not terminal_route_available(
                self.spec.provider_journal_path,
                identity=identity,
                provider=entry.provider,
                account=account,
                stage="unitizer",
            ):
                raise
            return self._unitizer_terminal(request)
        return _outcome(request, result)

    def reviewer(
        self,
        request: CandidateScopedStageARerunRequest,
        unitize: StageAStageOutcome,
    ) -> StageAStageOutcome:
        identity, entry, account, _provider_stage = self.call_identity(
            request, stage="reviewer", unitize=unitize
        )
        if terminal_route_available(
            self.spec.provider_journal_path,
            identity=identity,
            provider=entry.provider,
            account=account,
            stage="reviewer",
        ):
            return self._reviewer_terminal(request, unitize)
        try:
            result = llm_pipeline.llm_review_stage_a_units(
                selection_records=(request.packet.selection_record,),
                parser_records=self.lineage.successor_parser_records,
                prediction_unit_records=unitize.records,
                markdown_root=self.lineage.successor_markdown_root,
                registry_entry=entry,
                model_registry_sha256=self.spec.model_registry_sha256,
                provider_journal_path=self.spec.provider_journal_path,
                provider_cycle_caps_usd=self.provider_caps_usd,
                provider_cycle_id=self.spec.cycle_id,
                provider_cycle_caps_sha256=self.spec.provider_caps_sha256,
                provider_accounts={entry.provider.lower(): account},
                provider_attempt_namespace=REVIEWER_CONFIG_NAMESPACE,
                provider_logical_call_scope=identity.logical_call_scope,
            )
        except Exception:
            if not terminal_route_available(
                self.spec.provider_journal_path,
                identity=identity,
                provider=entry.provider,
                account=account,
                stage="reviewer",
            ):
                raise
            return self._reviewer_terminal(request, unitize)
        return _outcome(request, result)

    def _unitizer_terminal(
        self, request: CandidateScopedStageARerunRequest
    ) -> StageAStageOutcome:
        entry = self.unitizer_entry
        account = self.accounts[entry.provider.lower()]
        identity, _entry, _account, _provider_stage = self.call_identity(
            request, stage="unitizer", unitize=None
        )
        escalation = unitizer_terminal.build_llm_stage_a_unitizer_terminal_escalation(
            selection_record=request.packet.selection_record,
            parser_records=self.lineage.successor_parser_records,
            markdown_root=self.lineage.successor_markdown_root,
            markdown_bytes=self.lineage.successor_markdown_bytes,
            registry_entry=entry,
            model_registry_sha256=self.spec.model_registry_sha256,
            provider_journal_path=self.spec.provider_journal_path,
            provider_cycle_cap_usd=self.caps.cap_usd(entry.provider),
            provider_cycle_id=self.spec.cycle_id,
            provider_cycle_caps_sha256=self.spec.provider_caps_sha256,
            provider_account=account,
            provider_attempt_namespace=UNITIZER_CONFIG_NAMESPACE,
            provider_logical_call_scope=identity.logical_call_scope,
        )
        commitment = self._terminal_commitment(
            request.candidate_id, "unitizer", escalation.to_record()
        )
        result = llm_pipeline.llm_unitize_cases(
            selection_records=(request.packet.selection_record,),
            parser_records=self.lineage.successor_parser_records,
            markdown_root=self.lineage.successor_markdown_root,
            markdown_bytes=self.lineage.successor_markdown_bytes,
            registry_entry=entry,
            model_registry_sha256=self.spec.model_registry_sha256,
            provider_journal_path=self.spec.provider_journal_path,
            provider_cycle_caps_usd=self.provider_caps_usd,
            provider_cycle_id=self.spec.cycle_id,
            provider_cycle_caps_sha256=self.spec.provider_caps_sha256,
            provider_accounts={entry.provider.lower(): account},
            terminal_escalations={request.candidate_id: (escalation, commitment)},
            provider_attempt_namespace=UNITIZER_CONFIG_NAMESPACE,
            provider_logical_call_scope=identity.logical_call_scope,
        )
        return _outcome(request, result)

    def _reviewer_terminal(
        self,
        request: CandidateScopedStageARerunRequest,
        unitize: StageAStageOutcome,
    ) -> StageAStageOutcome:
        entry = self.reviewer_entry
        account = self.accounts[entry.provider.lower()]
        identity, _entry, _account, _provider_stage = self.call_identity(
            request, stage="reviewer", unitize=unitize
        )
        escalation = (
            llm_pipeline.build_llm_stage_a_structural_review_terminal_escalation(
                selection_record=request.packet.selection_record,
                parser_records=self.lineage.successor_parser_records,
                prediction_unit_records=unitize.records,
                markdown_root=self.lineage.successor_markdown_root,
                markdown_bytes=self.lineage.successor_markdown_bytes,
                registry_entry=entry,
                model_registry_sha256=self.spec.model_registry_sha256,
                provider_journal_path=self.spec.provider_journal_path,
                provider_cycle_cap_usd=self.caps.cap_usd(entry.provider),
                provider_cycle_id=self.spec.cycle_id,
                provider_cycle_caps_sha256=self.spec.provider_caps_sha256,
                provider_account=account,
                provider_attempt_namespace=REVIEWER_CONFIG_NAMESPACE,
                provider_logical_call_scope=identity.logical_call_scope,
            )
        )
        commitment = self._terminal_commitment(
            request.candidate_id, "reviewer", escalation.to_record()
        )
        result = llm_pipeline.llm_review_stage_a_units(
            selection_records=(request.packet.selection_record,),
            parser_records=self.lineage.successor_parser_records,
            prediction_unit_records=unitize.records,
            markdown_root=self.lineage.successor_markdown_root,
            registry_entry=entry,
            model_registry_sha256=self.spec.model_registry_sha256,
            provider_journal_path=self.spec.provider_journal_path,
            provider_cycle_caps_usd=self.provider_caps_usd,
            provider_cycle_id=self.spec.cycle_id,
            provider_cycle_caps_sha256=self.spec.provider_caps_sha256,
            provider_accounts={entry.provider.lower(): account},
            terminal_escalations={request.candidate_id: (escalation, commitment)},
            provider_attempt_namespace=REVIEWER_CONFIG_NAMESPACE,
            provider_logical_call_scope=identity.logical_call_scope,
        )
        return _outcome(request, result)

    def _terminal_commitment(
        self, candidate_id: str, stage: str, record: Mapping[str, object]
    ) -> dict[str, object]:
        root = self.spec.output_paths["terminal_evidence_root"]
        root.mkdir(parents=True, exist_ok=True)
        path = root / f"{candidate_id}-{stage}-terminal-escalation.json"
        payload = ARTIFACT_CANONICAL_JSON_V1.encode(record)
        temporary = path.with_name(f".{path.name}.tmp")
        temporary.write_bytes(payload)
        os.replace(temporary, path)
        return {"path": str(path), "sha256": hashlib.sha256(payload).hexdigest()}


def _outcome(
    request: CandidateScopedStageARerunRequest, result: _StageABatchResult
) -> StageAStageOutcome:
    audit_records = result.audit_records
    if len(audit_records) != 1:
        raise StageAReplayExecutorError(
            "Stage A provider callback returned ambiguous audit rows"
        )
    audit = audit_records[0]
    provider_status = str(audit.get("status", ""))
    if provider_status == "terminal_escalation":
        status = "terminal_escalation"
    elif provider_status in {
        "succeeded",
        "adjudication_pending",
        "passed",
        "flags_pending",
    }:
        status = "settled"
    else:
        raise StageAReplayExecutorError(
            f"Stage A provider callback returned unknown status {provider_status!r}"
        )
    return StageAStageOutcome(
        candidate_id=request.candidate_id,
        records=tuple(result.records),
        audit={**audit, "provider_status": provider_status, "status": status},
        status=cast(Any, status),
        request_sha256=request.request_sha256,
    )


def _registry_entry(registry: ModelRegistry, key: str) -> ModelRegistryEntry:
    try:
        provider, model_id = key.split(":", 1)
        return registry.get(provider, model_id)
    except (ValueError, KeyError) as exc:
        raise StageAReplayExecutorError(
            f"model id is absent from pinned registry: {key}"
        ) from exc


def _validated_provider_accounts(
    accounts: Mapping[str, object],
    entries: Sequence[ModelRegistryEntry],
    caps: ProviderCycleCaps,
    spec: ReplaySpec,
) -> dict[str, str]:
    used_providers = {entry.provider.lower() for entry in entries}
    if set(accounts) != used_providers:
        raise StageAReplayExecutorError(
            "provider accounts must exactly cover frozen model providers"
        )
    validated: dict[str, str] = {}
    for provider_name in sorted(used_providers):
        alias = _text(accounts, provider_name)
        canonical_alias = _canonical_provider_account(caps, spec, provider_name)
        if alias != canonical_alias:
            raise StageAReplayExecutorError(
                f"provider account alias differs from pinned caps: {provider_name}"
            )
        validated[provider_name] = alias
    return validated


def _canonical_provider_account(
    caps: ProviderCycleCaps, spec: ReplaySpec, provider_name: str
) -> str:
    """Resolve the canonical account alias this replay's caps digest commits to.

    A caps artifact that carries the alias answers directly.  A *legacy base*
    caps artifact cannot: ``provider_cycle_caps_materializer`` requires the
    base artifact to omit accounts, so a replay pinned to one has no alias to
    compare against even though it is fully authenticated.  Refusing there
    would make the pin and the account check jointly unsatisfiable.

    The alias is still authenticated in that case, one artifact further along:
    the pinned journal's immutable identity row commits to this replay's cycle
    id *and* to the exact caps digest the spec pins, so the aliases its attempt
    rows carry belong to the same artifact the digest check already
    authenticated.  Nothing about that digest binding is relaxed here — this
    only reads an alias the caps artifact itself never carried, and the
    request must still match it exactly.
    """

    cap = caps.providers.get(provider_name)
    if cap is None:
        raise StageAReplayExecutorError(
            f"provider cycle caps artifact has no entry for {provider_name!r}"
        )
    if cap.account is not None:
        return cap.account
    return _journal_committed_account(spec, provider_name)


def _journal_committed_account(spec: ReplaySpec, provider_name: str) -> str:
    """Read one provider's single committed alias from the pinned journal."""

    snapshot: sqlite3.Connection | None = None
    try:
        snapshot = open_provider_journal_snapshot(spec.provider_journal_path)
        verify_provider_journal_identity(
            spec.provider_journal_path,
            cycle_id=spec.cycle_id,
            provider_cycle_caps_sha256=spec.provider_caps_sha256,
            snapshot=snapshot,
        )
        rows = snapshot.execute(
            "SELECT DISTINCT account FROM provider_attempts WHERE provider = ?",
            (provider_name,),
        ).fetchall()
    except (ProviderJournalError, sqlite3.Error, ValueError) as exc:
        raise StageAReplayExecutorError(str(exc)) from exc
    finally:
        if snapshot is not None:
            snapshot.close()
    aliases = sorted({row[0] for row in rows})
    if len(aliases) != 1:
        raise StageAReplayExecutorError(
            "pinned provider journal does not commit exactly one account alias "
            f"for {provider_name!r}"
        )
    try:
        return public_account_alias(aliases[0])
    except ProviderJournalError as exc:
        raise StageAReplayExecutorError(str(exc)) from exc


def _read_regular(path: Path, label: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise StageAReplayExecutorError(f"{label} is not a regular file: {path}")
    return path.read_bytes()


def _base_stage(stage: str) -> str:
    return "llm-unitize" if stage == "unitizer" else "llm-review-stage-a"


def _mapping(record: Mapping[str, object], field: str) -> Mapping[str, object]:
    value = record.get(field)
    if not isinstance(value, Mapping):
        raise StageAReplayExecutorError(f"{field} must be an object")
    return cast(Mapping[str, object], value)


def _text(record: Mapping[str, object], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value:
        raise StageAReplayExecutorError(f"{field} must be non-empty text")
    return value


def _digest(record: Mapping[str, object], field: str) -> str:
    value = _text(record, field)
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise StageAReplayExecutorError(f"{field} must be a lowercase SHA-256")
    return value
