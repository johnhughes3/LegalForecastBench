"""Fail-closed authenticated execution for Gemini disclosure review."""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from weakref import WeakKeyDictionary

from legalforecast.evals.live_model_solver import (
    LiveModelTransport,
    complete_live_prompt,
)
from legalforecast.evals.model_registry import ModelRegistry, ModelRegistryEntry
from legalforecast.evals.provider_spend_attempt_handler import (
    CompositeProviderAttemptHandler,
    ProviderSpendAttemptHandler,
    conservative_reservation_microusd,
)
from legalforecast.evals.provider_spend_control import (
    FrozenAttemptPolicy,
    ProviderSpendKey,
    SqliteProviderSpendAuthority,
)
from legalforecast.ingestion.disclosure_model_review import (
    DisclosureModelReviewDecision,
    build_marker_page_prompt,
    build_model_review_batch_prompt,
    build_public_model_review_decision,
    validate_model_review_batch_response,
)
from legalforecast.ingestion.provenance_clearance import (
    validate_exception_review_worksheet_v3,
)
from legalforecast.labeling.provider_journal import (
    ProviderAttemptJournal,
    ProviderCallIdentity,
    load_provider_cycle_caps_bytes,
)

AUTHORITY_SCHEMA_VERSION = "legalforecast.disclosure_model_review_authority.v2"
PRIVATE_RECORDS_SCHEMA_VERSION = (
    "legalforecast.disclosure_model_review_authority_private.v1"
)
REVIEWER_REGISTRY_SHA256 = (
    "f577faab344745d9dcffc4bc0662901e7f511a2a0e0fa58c2e611fe348846e03"
)
EVALUATED_REGISTRY_SHA256 = (
    "960c4783826e365d01229fd0199b1c767144ad2275de1c4cfe981f25f4159f2e"
)
PROVIDER_CYCLE_CAPS_SHA256 = (
    "71a0919b7e23a1b0dab7bca7233c9036f2e678f35760f78f98b4f2c37330eb74"
)
_ROOT = Path(__file__).resolve().parents[2]
_REVIEWER_REGISTRY = (
    _ROOT / "model_registries/cycle-1-disclosure-reviewer-2026-07-27.json"
)
_EVALUATED_REGISTRY = _ROOT / "model_registries/cycle-1-2026-06-30.json"
_PROVIDER_CYCLE_CAPS = (
    _ROOT / "model_registries/cycle-1-target-100-provider-caps-base-2026-07-28.json"
)
_STAGE = "disclosure-exception-review-v3"
_REVIEWER_KEY = "google:gemini-3.5-flash"
_ACCOUNT = "default"
_MAX_ATTEMPTS = 2
_FAILURE_WINDOW_SECONDS = 3600


class DisclosureModelReviewAuthorityError(ValueError):
    """Raised when authenticated review authority cannot be proven exactly."""


@dataclass(frozen=True, slots=True)
class _FrozenInputs:
    routing_plan_bytes: bytes
    worksheet_bytes: bytes
    documents: tuple[tuple[tuple[str, str], bytes], ...]


@dataclass(frozen=True, slots=True)
class _CapabilityState:
    inputs: _FrozenInputs
    frozen_source_root: Path | None
    provider_journal_path: Path
    provider_spend_authority_path: Path
    local_attempt_ordinal: int
    journal_attempt_ordinal: int
    authority_attempt_ordinal: int
    public_bytes: bytes
    private_bytes: bytes


def _authenticate_state(
    *,
    routing_plan: Mapping[str, object],
    routing_plan_bytes: bytes,
    worksheet: Mapping[str, object],
    worksheet_bytes: bytes,
    document_bytes_by_key: Mapping[tuple[str, str], bytes],
    provider_journal_path: str | Path,
    provider_spend_authority_path: str | Path,
    source_root: str | Path | None = None,
    transport: LiveModelTransport | None = None,
    environ: Mapping[str, str] | None = None,
    timeout_seconds: float = 120.0,
    retry_backoff_seconds: float = 2.0,
) -> _CapabilityState:
    """Execute or cross-store-adopt one frozen Gemini review."""

    frozen_source_root = None if source_root is None else Path(source_root).resolve()
    reviewer, evaluated_registry_sha256, caps, caps_sha256 = _frozen_authorities(
        source_root=frozen_source_root
    )
    inputs, documents = _validate_inputs(
        routing_plan=routing_plan,
        routing_plan_bytes=routing_plan_bytes,
        worksheet=worksheet,
        worksheet_bytes=worksheet_bytes,
        document_bytes_by_key=document_bytes_by_key,
    )
    prompts = tuple(
        build_marker_page_prompt(
            document, document_bytes=document_bytes_by_key[_key(document)]
        )
        for document in documents
    )
    batch_prompt = build_model_review_batch_prompt(prompts, reviewer=reviewer)
    context = _execution_context(
        routing_plan_bytes=routing_plan_bytes,
        worksheet_bytes=worksheet_bytes,
        batch_prompt_text=batch_prompt.prompt_text,
        reviewer=reviewer,
        caps=caps,
        provider_journal_path=Path(provider_journal_path),
        provider_spend_authority_path=Path(provider_spend_authority_path),
    )
    journal, authority, handler = context.open()
    try:
        response = complete_live_prompt(
            reviewer,
            batch_prompt.prompt_text,
            model_registry_sha256=REVIEWER_REGISTRY_SHA256,
            transport=transport,
            environ=environ,
            timeout_seconds=timeout_seconds,
            max_attempts=_MAX_ATTEMPTS,
            retry_backoff_seconds=retry_backoff_seconds,
            attempt_handler=handler,
        )
        local_ordinal = max(response.request_count, 1)
        journal_ordinal = journal.durable_attempt_ordinal(local_ordinal)
        authority_ordinal = journal.authority_attempt_ordinal(local_ordinal)
        raw_response, normalized = _readback_journal(
            journal, journal_attempt_ordinal=journal_ordinal
        )
        _verify_normalized(
            raw_response,
            normalized,
            raw_output=response.raw_output,
            served_model_version=_metadata_text(
                response.metadata, "served_model_version"
            ),
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            actual_cost_usd=response.estimated_cost,
        )
        decisions, private_records = _validate_semantic(
            response.raw_output,
            batch_prompt=batch_prompt,
            reviewer=reviewer,
        )
        public_record = _public_record(
            cycle_id=caps.cycle_id,
            routing_plan_sha256=_sha256(routing_plan_bytes),
            worksheet_sha256=_sha256(worksheet_bytes),
            evaluated_registry_sha256=evaluated_registry_sha256,
            provider_cycle_caps_sha256=caps_sha256,
            provider_envelope_sha256=_sha256(
                _canonical_bytes(raw_response, newline=False)
            ),
            served_model_version=_metadata_text(
                response.metadata, "served_model_version"
            ),
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            actual_cost_usd=response.estimated_cost,
            journal_attempt_ordinal=journal_ordinal,
            authority_attempt_ordinal=authority_ordinal,
            decisions=decisions,
        )
        if journal.has_validated_response:
            journal.commit_reconstruction(
                {
                    "schema_version": PRIVATE_RECORDS_SCHEMA_VERSION,
                    "public_record_sha256": _sha256(_canonical_bytes(public_record)),
                    "private_records_sha256": _sha256(
                        _canonical_bytes(list(private_records))
                    ),
                }
            )
    except BaseException as exc:
        if journal.has_validated_response:
            journal.record_reconstruction_failure(
                exc if isinstance(exc, Exception) else RuntimeError(type(exc).__name__)
            )
        raise
    finally:
        journal.close()
        authority.close()

    return _CapabilityState(
        inputs=inputs,
        frozen_source_root=frozen_source_root,
        provider_journal_path=Path(provider_journal_path).resolve(),
        provider_spend_authority_path=Path(provider_spend_authority_path).resolve(),
        local_attempt_ordinal=local_ordinal,
        journal_attempt_ordinal=journal_ordinal,
        authority_attempt_ordinal=authority_ordinal,
        public_bytes=_canonical_bytes(public_record),
        private_bytes=_canonical_bytes(list(private_records)),
    )


@dataclass(frozen=True, slots=True)
class _ExecutionContext:
    journal_path: Path
    authority_path: Path
    journal_identity: ProviderCallIdentity
    spend_key: ProviderSpendKey
    cycle_id: str
    cap_usd: float
    cap_microusd: int
    reservation_microusd: int
    authority_identity_sha256: str

    def open(
        self,
    ) -> tuple[
        ProviderAttemptJournal,
        SqliteProviderSpendAuthority,
        CompositeProviderAttemptHandler,
    ]:
        journal = ProviderAttemptJournal(
            self.journal_path,
            identity=self.journal_identity,
            provider="google",
            reservation_usd=self.reservation_microusd / 1_000_000,
            cycle_cap_usd=self.cap_usd,
            cycle_id=self.cycle_id,
            provider_cycle_caps_sha256=PROVIDER_CYCLE_CAPS_SHA256,
        )
        try:
            authority = SqliteProviderSpendAuthority(
                self.authority_path,
                authority_identity_sha256=self.authority_identity_sha256,
                cycle_id=self.cycle_id,
                provider="google",
                account=_ACCOUNT,
                cap_microusd=self.cap_microusd,
                policy=FrozenAttemptPolicy(
                    reservation_ledger_sha256=PROVIDER_CYCLE_CAPS_SHA256,
                    max_billable_attempts=_MAX_ATTEMPTS,
                    failure_threshold=_MAX_ATTEMPTS,
                    failure_window_seconds=_FAILURE_WINDOW_SECONDS,
                ),
            )
        except BaseException:
            journal.close()
            raise
        spend_handler = ProviderSpendAttemptHandler(
            authority=authority,
            key=self.spend_key,
            reservation_microusd=self.reservation_microusd,
        )
        return (
            journal,
            authority,
            CompositeProviderAttemptHandler(journal, spend_handler),
        )


def _execution_context(
    *,
    routing_plan_bytes: bytes,
    worksheet_bytes: bytes,
    batch_prompt_text: str,
    reviewer: ModelRegistryEntry,
    caps: Any,
    provider_journal_path: Path,
    provider_spend_authority_path: Path,
) -> _ExecutionContext:
    logical_id = _logical_call_id(routing_plan_bytes, worksheet_bytes)
    reservation = conservative_reservation_microusd(
        context_limit=reviewer.context_limit,
        max_output_tokens=reviewer.max_output_tokens,
        input_token_price=reviewer.input_token_price,
        output_token_price=reviewer.output_token_price,
    )
    authority_identity = _sha256(
        _canonical_bytes(
            {
                "caps_sha256": PROVIDER_CYCLE_CAPS_SHA256,
                "cycle_id": caps.cycle_id,
                "max_attempts": _MAX_ATTEMPTS,
                "reviewer_registry_sha256": REVIEWER_REGISTRY_SHA256,
                "stage": _STAGE,
            }
        )
    )
    spend_key = ProviderSpendKey(
        cycle_id=caps.cycle_id,
        provider="google",
        account=_ACCOUNT,
        stage=_STAGE,
        model_key=reviewer.registry_key,
        case_id=logical_id,
        ablation="disclosure-review",
        repeat_index=1,
    )
    return _ExecutionContext(
        journal_path=provider_journal_path,
        authority_path=provider_spend_authority_path,
        journal_identity=ProviderCallIdentity(
            stage=_STAGE,
            candidate_id=logical_id,
            model_key=reviewer.registry_key,
            prompt=batch_prompt_text,
            model_registry_sha256=REVIEWER_REGISTRY_SHA256,
            account=_ACCOUNT,
        ),
        spend_key=spend_key,
        cycle_id=caps.cycle_id,
        cap_usd=caps.cap_usd("google"),
        cap_microusd=caps.cap_microusd("google"),
        reservation_microusd=reservation,
        authority_identity_sha256=authority_identity,
    )


def _substantive_replay(state: _CapabilityState) -> None:
    reviewer, evaluated_sha, caps, caps_sha = _frozen_authorities(
        source_root=state.frozen_source_root
    )
    plan = _json_object(state.inputs.routing_plan_bytes, "routing plan")
    worksheet = _json_object(state.inputs.worksheet_bytes, "worksheet")
    document_map = dict(state.inputs.documents)
    _, documents = _validate_inputs(
        routing_plan=plan,
        routing_plan_bytes=state.inputs.routing_plan_bytes,
        worksheet=worksheet,
        worksheet_bytes=state.inputs.worksheet_bytes,
        document_bytes_by_key=document_map,
    )
    prompts = tuple(
        build_marker_page_prompt(document, document_bytes=document_map[_key(document)])
        for document in documents
    )
    batch_prompt = build_model_review_batch_prompt(prompts, reviewer=reviewer)
    context = _execution_context(
        routing_plan_bytes=state.inputs.routing_plan_bytes,
        worksheet_bytes=state.inputs.worksheet_bytes,
        batch_prompt_text=batch_prompt.prompt_text,
        reviewer=reviewer,
        caps=caps,
        provider_journal_path=state.provider_journal_path,
        provider_spend_authority_path=state.provider_spend_authority_path,
    )
    journal, authority, _ = context.open()
    try:
        journal.adopt_attempt(
            state.local_attempt_ordinal,
            durable_attempt_ordinal=state.journal_attempt_ordinal,
        )
        raw, normalized = _readback_journal(
            journal, journal_attempt_ordinal=state.journal_attempt_ordinal
        )
        raw_output = _required_text(normalized, "raw_output")
        input_tokens = _integer(normalized.get("input_tokens"), "input_tokens")
        output_tokens = _integer(normalized.get("output_tokens"), "output_tokens")
        actual_cost = _number(normalized.get("actual_cost_usd"), "actual_cost_usd")
        served_version = _required_text(raw, "modelVersion")
        _verify_normalized(
            raw,
            normalized,
            raw_output=raw_output,
            served_model_version=served_version,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            actual_cost_usd=actual_cost,
        )
        lease = authority.adopt_attempt(
            context.spend_key,
            attempt_ordinal=state.authority_attempt_ordinal,
        )
        authority.record_response(
            lease,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            actual_microusd=math.ceil(actual_cost * 1_000_000),
            response_sha256=_sha256(raw_output.encode()),
        )
        decisions, private_records = _validate_semantic(
            raw_output, batch_prompt=batch_prompt, reviewer=reviewer
        )
        public = _public_record(
            cycle_id=caps.cycle_id,
            routing_plan_sha256=_sha256(state.inputs.routing_plan_bytes),
            worksheet_sha256=_sha256(state.inputs.worksheet_bytes),
            evaluated_registry_sha256=evaluated_sha,
            provider_cycle_caps_sha256=caps_sha,
            provider_envelope_sha256=_sha256(_canonical_bytes(raw, newline=False)),
            served_model_version=served_version,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            actual_cost_usd=actual_cost,
            journal_attempt_ordinal=state.journal_attempt_ordinal,
            authority_attempt_ordinal=state.authority_attempt_ordinal,
            decisions=decisions,
        )
        if (
            _canonical_bytes(public) != state.public_bytes
            or _canonical_bytes(list(private_records)) != state.private_bytes
        ):
            raise DisclosureModelReviewAuthorityError(
                "capability projections differ from substantive authority replay"
            )
    finally:
        journal.close()
        authority.close()


def _frozen_authorities(
    *, source_root: Path | None = None
) -> tuple[ModelRegistryEntry, str, Any, str]:
    reviewer_path, evaluated_path, caps_path = _frozen_paths(source_root)
    reviewer_bytes = _read_frozen(reviewer_path, REVIEWER_REGISTRY_SHA256)
    evaluated_bytes = _read_frozen(evaluated_path, EVALUATED_REGISTRY_SHA256)
    caps_bytes = _read_frozen(caps_path, PROVIDER_CYCLE_CAPS_SHA256)
    reviewer_registry = _registry(reviewer_bytes, "reviewer registry")
    evaluated = _registry(evaluated_bytes, "evaluated registry")
    if len(reviewer_registry.entries) != 1:
        raise DisclosureModelReviewAuthorityError("reviewer registry is not singular")
    reviewer = reviewer_registry.entries[0]
    if (
        reviewer.registry_key != _REVIEWER_KEY
        or reviewer.model_version_or_snapshot != "gemini-3.5-flash"
        or not reviewer.network_disabled
        or not reviewer.search_disabled
        or reviewer.tool_policy.value != "no_tools"
    ):
        raise DisclosureModelReviewAuthorityError("frozen reviewer policy differs")
    if (
        reviewer.provider in {entry.provider for entry in evaluated.entries}
        or reviewer.model_id in {entry.model_id for entry in evaluated.entries}
        or reviewer.registry_key in {entry.registry_key for entry in evaluated.entries}
    ):
        raise DisclosureModelReviewAuthorityError(
            "reviewer is not provider, model, and registry-key disjoint"
        )
    caps = load_provider_cycle_caps_bytes(caps_bytes, source=caps_path)
    return reviewer, EVALUATED_REGISTRY_SHA256, caps, PROVIDER_CYCLE_CAPS_SHA256


def _frozen_paths(source_root: Path | None) -> tuple[Path, Path, Path]:
    if source_root is None:
        return _REVIEWER_REGISTRY, _EVALUATED_REGISTRY, _PROVIDER_CYCLE_CAPS
    root = source_root.resolve()
    return (
        root / "model_registries/cycle-1-disclosure-reviewer-2026-07-27.json",
        root / "model_registries/cycle-1-2026-06-30.json",
        root / "model_registries/cycle-1-target-100-provider-caps-base-2026-07-28.json",
    )


def _validate_inputs(
    *,
    routing_plan: Mapping[str, object],
    routing_plan_bytes: bytes,
    worksheet: Mapping[str, object],
    worksheet_bytes: bytes,
    document_bytes_by_key: Mapping[tuple[str, str], bytes],
) -> tuple[_FrozenInputs, list[Mapping[str, object]]]:
    try:
        documents = validate_exception_review_worksheet_v3(
            worksheet,
            routing_plan=routing_plan,
            routing_plan_bytes=routing_plan_bytes,
            worksheet_bytes=worksheet_bytes,
        )
    except ValueError as exc:
        raise DisclosureModelReviewAuthorityError(str(exc)) from exc
    expected = tuple(_key(document) for document in documents)
    if not documents or set(document_bytes_by_key) != set(expected):
        raise DisclosureModelReviewAuthorityError(
            "authenticated source-byte coverage differs from worksheet"
        )
    inputs = _FrozenInputs(
        routing_plan_bytes=bytes(routing_plan_bytes),
        worksheet_bytes=bytes(worksheet_bytes),
        documents=tuple((key, bytes(document_bytes_by_key[key])) for key in expected),
    )
    return inputs, documents


def _validate_semantic(
    raw_output: str,
    *,
    batch_prompt: Any,
    reviewer: ModelRegistryEntry,
) -> tuple[tuple[DisclosureModelReviewDecision, ...], tuple[dict[str, object], ...]]:
    semantic = _json_object(raw_output.encode(), "provider semantic output")
    if raw_output.encode() != _canonical_bytes(semantic):
        raise DisclosureModelReviewAuthorityError(
            "provider semantic output is not exact canonical JSON"
        )
    reviews = validate_model_review_batch_response(
        semantic,
        response_bytes=raw_output.encode(),
        batch_prompt=batch_prompt,
        reviewer=reviewer,
    )
    return (
        tuple(
            build_public_model_review_decision(review, reviewer=reviewer)
            for review in reviews
        ),
        tuple(review.to_private_record() for review in reviews),
    )


def _readback_journal(
    journal: ProviderAttemptJournal, *, journal_attempt_ordinal: int
) -> tuple[dict[str, object], dict[str, object]]:
    with sqlite3.connect(
        f"file:{journal.path.resolve()}?mode=ro", uri=True
    ) as connection:
        row = connection.execute(
            "SELECT status, raw_response_json, normalized_response_json "
            "FROM provider_attempts WHERE logical_call_key = ? AND attempt_ordinal = ?",
            (journal.identity.logical_call_key, journal_attempt_ordinal),
        ).fetchone()
    if row is None or row[0] not in {"validated_response", "settled"}:
        raise DisclosureModelReviewAuthorityError(
            "provider journal has no adopted validated response"
        )
    return (
        _json_object(cast(str, row[1]).encode(), "raw provider response"),
        _json_object(cast(str, row[2]).encode(), "normalized provider response"),
    )


def _verify_normalized(
    raw: Mapping[str, object],
    normalized: Mapping[str, object],
    *,
    raw_output: str,
    served_model_version: str,
    input_tokens: int,
    output_tokens: int,
    actual_cost_usd: float,
) -> None:
    if raw.get("modelVersion") != served_model_version or (
        normalized.get("raw_output"),
        normalized.get("input_tokens"),
        normalized.get("output_tokens"),
        normalized.get("actual_cost_usd"),
    ) != (raw_output, input_tokens, output_tokens, actual_cost_usd):
        raise DisclosureModelReviewAuthorityError(
            "cross-store provider response readback differs"
        )


def _public_record(
    *,
    cycle_id: str,
    routing_plan_sha256: str,
    worksheet_sha256: str,
    evaluated_registry_sha256: str,
    provider_cycle_caps_sha256: str,
    provider_envelope_sha256: str,
    served_model_version: str,
    input_tokens: int,
    output_tokens: int,
    actual_cost_usd: float,
    journal_attempt_ordinal: int,
    authority_attempt_ordinal: int,
    decisions: tuple[DisclosureModelReviewDecision, ...],
) -> dict[str, object]:
    return {
        "schema_version": AUTHORITY_SCHEMA_VERSION,
        "cycle_id": cycle_id,
        "stage": _STAGE,
        "provider": "google",
        "account": "opaque-provider-account",
        "reviewer_registry_key": _REVIEWER_KEY,
        "routing_plan_sha256": routing_plan_sha256,
        "worksheet_sha256": worksheet_sha256,
        "reviewer_registry_sha256": REVIEWER_REGISTRY_SHA256,
        "evaluated_registry_sha256": evaluated_registry_sha256,
        "provider_cycle_caps_sha256": provider_cycle_caps_sha256,
        "provider_envelope_sha256": provider_envelope_sha256,
        "served_model_version": served_model_version,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "actual_cost_usd": actual_cost_usd,
        "journal_attempt_ordinal": journal_attempt_ordinal,
        "authority_attempt_ordinal": authority_attempt_ordinal,
        "decision_count": len(decisions),
        "decisions": [decision.to_record() for decision in decisions],
    }


def _read_frozen(path: Path, expected_sha256: str) -> bytes:
    data = path.read_bytes()
    if _sha256(data) != expected_sha256:
        raise DisclosureModelReviewAuthorityError(
            f"verifier-owned frozen artifact differs: {path.name}"
        )
    return data


def _registry(data: bytes, label: str) -> ModelRegistry:
    loaded = _json_value(data, label)
    if not isinstance(loaded, list):
        raise DisclosureModelReviewAuthorityError(f"{label} is invalid")
    rows = cast(list[object], loaded)
    if not all(isinstance(row, Mapping) for row in rows):
        raise DisclosureModelReviewAuthorityError(f"{label} is invalid")
    return ModelRegistry.from_records([cast(Mapping[str, Any], row) for row in rows])


def _key(document: Mapping[str, object]) -> tuple[str, str]:
    return _required_text(document, "candidate_id"), _required_text(
        document, "source_document_id"
    )


def _metadata_text(metadata: Mapping[str, str] | None, field: str) -> str:
    if metadata is None or not metadata.get(field):
        raise DisclosureModelReviewAuthorityError(f"provider metadata lacks {field}")
    return metadata[field]


def _required_text(record: Mapping[str, object], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value:
        raise DisclosureModelReviewAuthorityError(f"{field} must be non-empty")
    return value


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise DisclosureModelReviewAuthorityError(f"{label} must be non-negative")
    return value


def _number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or value < 0:
        raise DisclosureModelReviewAuthorityError(f"{label} must be non-negative")
    return float(value)


def _json_object(data: bytes, label: str) -> dict[str, object]:
    loaded = _json_value(data, label)
    if not isinstance(loaded, dict):
        raise DisclosureModelReviewAuthorityError(f"{label} must be an object")
    return cast(dict[str, object], loaded)


def _json_value(data: bytes, label: str) -> object:
    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in items:
            if key in result:
                raise DisclosureModelReviewAuthorityError(
                    f"{label} contains duplicate JSON key"
                )
            result[key] = value
        return result

    try:
        return json.loads(data.decode(), object_pairs_hook=pairs)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise DisclosureModelReviewAuthorityError(f"{label} is malformed") from exc


def _canonical_bytes(value: object, *, newline: bool = True) -> bytes:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return payload + (b"\n" if newline else b"")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _logical_call_id(routing_plan_bytes: bytes, worksheet_bytes: bytes) -> str:
    """Bind the two frozen inputs without ambiguous concatenation boundaries."""

    return _sha256(
        b"legalforecast.disclosure-review.logical-call.v1\0"
        + bytes.fromhex(_sha256(routing_plan_bytes))
        + bytes.fromhex(_sha256(worksheet_bytes))
    )


def _verifier_owned_capability_boundary() -> tuple[Any, Any, Any]:
    """Close capability construction and state adoption over verifier-only data."""

    class AuthenticatedCapability:
        __slots__ = ("__weakref__",)

    states: WeakKeyDictionary[object, _CapabilityState] = WeakKeyDictionary()

    def consume(capability: object) -> _CapabilityState:
        if type(capability) is not AuthenticatedCapability:
            raise DisclosureModelReviewAuthorityError(
                "authenticated disclosure review requires an opaque capability"
            )
        try:
            return states[capability]
        except KeyError as exc:
            raise DisclosureModelReviewAuthorityError(
                "authenticated disclosure review capability was not verifier-issued"
            ) from exc

    def authenticate(**kwargs: Any) -> object:
        state = _authenticate_state(**kwargs)
        capability = AuthenticatedCapability()
        states[capability] = state
        return capability

    def public_record(capability: object) -> dict[str, object]:
        state = consume(capability)
        _substantive_replay(state)
        return _json_object(state.public_bytes, "public projection")

    def private_records(capability: object) -> tuple[dict[str, object], ...]:
        state = consume(capability)
        _substantive_replay(state)
        loaded = _json_value(state.private_bytes, "private projection")
        if not isinstance(loaded, list):
            raise DisclosureModelReviewAuthorityError("private projection is invalid")
        rows = cast(list[object], loaded)
        if not all(isinstance(row, dict) for row in rows):
            raise DisclosureModelReviewAuthorityError("private projection is invalid")
        return tuple(cast(dict[str, object], row) for row in rows)

    return authenticate, private_records, public_record


(
    authenticate_disclosure_model_review,
    private_disclosure_model_review_records,
    public_disclosure_model_review_record,
) = _verifier_owned_capability_boundary()
del _verifier_owned_capability_boundary


__all__ = [
    "DisclosureModelReviewAuthorityError",
    "authenticate_disclosure_model_review",
    "private_disclosure_model_review_records",
    "public_disclosure_model_review_record",
]
