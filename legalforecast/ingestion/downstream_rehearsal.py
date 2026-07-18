"""Deterministic, provider-free model-response fixtures for downstream rehearsal.

This module intentionally does not provide production provenance.  It adapts
hash-bound response fixtures to the same local response parsing and schema
validation used by live Stage A and Stage B calls while making any network
access impossible.
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.parse
import urllib.request
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from legalforecast.evals.live_model_solver import LiveModelTransport
from legalforecast.evals.model_registry import ModelRegistryEntry
from legalforecast.ingestion.decision_text_artifact import (
    VerifiedDecisionTextArtifact,
)
from legalforecast.ingestion.disclosure_review_bundle import (
    ReviewBundleError,
    read_unique_regular_file,
)
from legalforecast.labeling.llm_pipeline import (
    LlmBatchResult,
    lawyer_review_queue_records,
    llm_label_cases,
    llm_review_stage_a_units,
    llm_unitize_cases,
    merge_structural_flags_into_review_queue,
    unitization_review_queue_records,
)
from legalforecast.unitization.review import apply_unitization_reviews

RESPONSE_FIXTURE_SCHEMA_VERSION = (
    "legalforecast.deterministic_model_response_fixture.v1"
)
REHEARSAL_SCHEMA_VERSION = "legalforecast.downstream_rehearsal.v1"
REHEARSAL_PROVENANCE = {
    "schema_version": REHEARSAL_SCHEMA_VERSION,
    "provenance_class": "fixture_only",
    "official_eligible": False,
    "authorizes_freeze": False,
    "authorizes_evaluation": False,
    "authorizes_dispatch": False,
}
_SUPPORTED_STAGES = frozenset({"llm-unitize", "llm-review-stage-a", "llm-label"})
_SUPPORTED_PROVIDERS = frozenset({"openai", "anthropic", "google", "gemini"})

JsonRecord = dict[str, Any]


class DownstreamRehearsalError(ValueError):
    """Raised when deterministic fixture lineage cannot be authenticated."""


@dataclass(frozen=True, slots=True)
class DeterministicModelResponseFixture:
    """One exact prompt-bound response used instead of a provider call."""

    stage: str
    candidate_id: str
    model_key: str
    prompt_sha256: str
    raw_output: str
    served_model_version: str
    input_tokens: int
    output_tokens: int
    fixture_sha256: str

    def __post_init__(self) -> None:
        if self.stage not in _SUPPORTED_STAGES:
            raise DownstreamRehearsalError(
                f"unsupported response-fixture stage: {self.stage}"
            )
        for field_name, value in (
            ("candidate_id", self.candidate_id),
            ("model_key", self.model_key),
            ("raw_output", self.raw_output),
            ("served_model_version", self.served_model_version),
        ):
            if not value.strip():
                raise DownstreamRehearsalError(
                    f"response fixture {field_name} is required"
                )
        _require_prefixed_sha256(self.prompt_sha256, "prompt_sha256")
        _require_prefixed_sha256(self.fixture_sha256, "fixture_sha256")
        if self.input_tokens < 0 or self.output_tokens < 0:
            raise DownstreamRehearsalError(
                "response fixture token counts cannot be negative"
            )
        try:
            parsed: object = json.loads(self.raw_output)
        except json.JSONDecodeError as exc:
            raise DownstreamRehearsalError(
                "response fixture raw_output must be valid JSON"
            ) from exc
        if not isinstance(parsed, Mapping):
            raise DownstreamRehearsalError(
                "response fixture raw_output must be a JSON object"
            )

    @property
    def key(self) -> tuple[str, str, str]:
        """Return the exact stage/candidate/model identity."""

        return self.stage, self.candidate_id, self.model_key


@dataclass(frozen=True, slots=True)
class DeterministicFixtureTrace:
    """Evidence that one local request consumed its exact response fixture."""

    stage: str
    candidate_id: str
    model_key: str
    prompt_sha256: str
    raw_output_sha256: str
    fixture_sha256: str
    input_tokens: int
    output_tokens: int

    def to_record(self) -> JsonRecord:
        """Return stable audit provenance for a rehearsal run card."""

        return {
            **REHEARSAL_PROVENANCE,
            "stage": self.stage,
            "candidate_id": self.candidate_id,
            "model_key": self.model_key,
            "prompt_sha256": self.prompt_sha256,
            "raw_output_sha256": self.raw_output_sha256,
            "fixture_sha256": self.fixture_sha256,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "estimated_cost_usd": "0.00",
            "provider_call_executed": False,
        }


@dataclass(frozen=True, slots=True)
class FixtureStageAResult:
    """Validated Stage A artifacts produced without a provider journal."""

    raw_prediction_units: tuple[JsonRecord, ...]
    unitization_audit: tuple[JsonRecord, ...]
    original_review_queue: tuple[JsonRecord, ...]
    structural_flags: tuple[JsonRecord, ...]
    structural_review_audit: tuple[JsonRecord, ...]
    merged_review_queue: tuple[JsonRecord, ...]
    finalized_prediction_units: tuple[JsonRecord, ...]
    traces: tuple[DeterministicFixtureTrace, ...]


@dataclass(frozen=True, slots=True)
class FixtureStageBResult:
    """Validated Stage B artifacts produced without a provider journal."""

    labels: tuple[JsonRecord, ...]
    labeling_audit: tuple[JsonRecord, ...]
    lawyer_review_queue: tuple[JsonRecord, ...]
    traces: tuple[DeterministicFixtureTrace, ...]


@dataclass(frozen=True, slots=True)
class FixtureUnitizationResult:
    raw_prediction_units: tuple[JsonRecord, ...]
    unitization_audit: tuple[JsonRecord, ...]
    original_review_queue: tuple[JsonRecord, ...]
    traces: tuple[DeterministicFixtureTrace, ...]


@dataclass(frozen=True, slots=True)
class FixtureStructuralReviewResult:
    structural_flags: tuple[JsonRecord, ...]
    structural_review_audit: tuple[JsonRecord, ...]
    merged_review_queue: tuple[JsonRecord, ...]
    traces: tuple[DeterministicFixtureTrace, ...]


@dataclass(frozen=True, slots=True)
class LoadedDeterministicResponseFixtures:
    """Exact response-fixture bytes and parsed records consumed from them."""

    path: Path
    fixtures: tuple[DeterministicModelResponseFixture, ...]
    sha256: str
    byte_count: int

    def require_unchanged(self) -> None:
        """Reject mutation or path substitution after the fixtures were loaded."""

        try:
            payload = read_unique_regular_file(self.path)
        except (OSError, ReviewBundleError) as exc:
            raise DownstreamRehearsalError(
                f"cannot reread response fixture: {self.path}"
            ) from exc
        if len(payload) != self.byte_count or _bytes_sha256(payload) != self.sha256:
            raise DownstreamRehearsalError(
                "deterministic response fixture changed after it was loaded"
            )


class DeterministicModelFixtureTransport(LiveModelTransport):
    """FIFO provider adapter that can only return authenticated local fixtures."""

    def __init__(
        self,
        fixtures: Sequence[DeterministicModelResponseFixture],
        *,
        provider_by_model_key: Mapping[str, str],
        requested_model_by_model_key: Mapping[str, str],
    ) -> None:
        if not fixtures:
            raise DownstreamRehearsalError(
                "deterministic response transport requires at least one fixture"
            )
        self._fixtures = tuple(fixtures)
        self._provider_by_model_key = {
            model_key: provider.strip().lower()
            for model_key, provider in provider_by_model_key.items()
        }
        self._requested_model_by_model_key = dict(requested_model_by_model_key)
        self._next_index = 0
        self._traces: list[DeterministicFixtureTrace] = []

    @property
    def traces(self) -> tuple[DeterministicFixtureTrace, ...]:
        """Return fixture-consumption evidence in provider-call order."""

        return tuple(self._traces)

    @property
    def request_count(self) -> int:
        """Return the number of local fixture requests consumed."""

        return self._next_index

    def __call__(
        self,
        request: urllib.request.Request,
        timeout_seconds: float,
    ) -> Mapping[str, object]:
        del timeout_seconds
        if self._next_index >= len(self._fixtures):
            raise DownstreamRehearsalError(
                "model stage attempted more calls than the response fixture"
            )
        fixture = self._fixtures[self._next_index]
        provider = self._provider_by_model_key.get(fixture.model_key)
        if provider not in _SUPPORTED_PROVIDERS:
            raise DownstreamRehearsalError(
                f"unsupported response-fixture provider for {fixture.model_key}"
            )
        prompt, requested_model = _request_prompt_and_model(request, provider=provider)
        prompt_sha256 = "sha256:" + hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        if prompt_sha256 != fixture.prompt_sha256:
            raise DownstreamRehearsalError(
                "response fixture prompt commitment mismatch for "
                f"{fixture.stage}/{fixture.candidate_id}/{fixture.model_key}"
            )
        expected_requested_model = self._requested_model_by_model_key.get(
            fixture.model_key
        )
        if expected_requested_model is None:
            raise DownstreamRehearsalError(
                f"missing requested-model commitment for {fixture.model_key}"
            )
        if not _same_model_version(requested_model, expected_requested_model):
            raise DownstreamRehearsalError(
                "response fixture request model differs from the frozen registry for "
                f"{fixture.model_key}"
            )
        self._next_index += 1
        self._traces.append(
            DeterministicFixtureTrace(
                stage=fixture.stage,
                candidate_id=fixture.candidate_id,
                model_key=fixture.model_key,
                prompt_sha256=prompt_sha256,
                raw_output_sha256="sha256:"
                + hashlib.sha256(fixture.raw_output.encode("utf-8")).hexdigest(),
                fixture_sha256=fixture.fixture_sha256,
                input_tokens=fixture.input_tokens,
                output_tokens=fixture.output_tokens,
            )
        )
        return _provider_payload(fixture, provider=provider)

    def require_exhausted(self) -> None:
        """Fail if any committed response fixture was silently unused."""

        if self._next_index != len(self._fixtures):
            remaining = self._fixtures[self._next_index :]
            sample = ", ".join("/".join(item.key) for item in remaining[:3])
            raise DownstreamRehearsalError(
                "unused deterministic response fixtures remain: " + sample
            )


def load_deterministic_response_fixtures(
    path: str | Path,
) -> tuple[DeterministicModelResponseFixture, ...]:
    """Load one immutable JSONL fixture file with exact identity coverage."""

    return load_deterministic_response_fixture_bundle(path).fixtures


def load_deterministic_response_fixture_bundle(
    path: str | Path,
) -> LoadedDeterministicResponseFixtures:
    """Load fixtures and retain the exact whole-file commitment consumed."""

    source = Path(os.path.abspath(os.fspath(path)))
    try:
        payload = read_unique_regular_file(source)
    except (OSError, ReviewBundleError) as exc:
        raise DownstreamRehearsalError(
            f"cannot read response fixture: {source}"
        ) from exc
    records: list[DeterministicModelResponseFixture] = []
    seen: set[tuple[str, str, str]] = set()
    for line_number, raw_line in enumerate(payload.splitlines(), start=1):
        if not raw_line.strip():
            continue
        try:
            raw: object = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise DownstreamRehearsalError(
                f"invalid response fixture JSON on line {line_number}"
            ) from exc
        if not isinstance(raw, Mapping):
            raise DownstreamRehearsalError(
                f"response fixture line {line_number} must be an object"
            )
        record = cast(Mapping[str, object], raw)
        expected_keys = {
            "schema_version",
            "stage",
            "candidate_id",
            "model_key",
            "prompt_sha256",
            "raw_output",
            "served_model_version",
            "input_tokens",
            "output_tokens",
        }
        if set(record) != expected_keys:
            raise DownstreamRehearsalError(
                f"response fixture line {line_number} has unexpected fields"
            )
        if record.get("schema_version") != RESPONSE_FIXTURE_SCHEMA_VERSION:
            raise DownstreamRehearsalError(
                f"unsupported response fixture schema on line {line_number}"
            )
        fixture = DeterministicModelResponseFixture(
            stage=_required_str(record, "stage"),
            candidate_id=_required_str(record, "candidate_id"),
            model_key=_required_str(record, "model_key"),
            prompt_sha256=_required_str(record, "prompt_sha256"),
            raw_output=_required_str(record, "raw_output"),
            served_model_version=_required_str(record, "served_model_version"),
            input_tokens=_required_nonnegative_int(record, "input_tokens"),
            output_tokens=_required_nonnegative_int(record, "output_tokens"),
            fixture_sha256="sha256:" + hashlib.sha256(raw_line).hexdigest(),
        )
        if fixture.key in seen:
            raise DownstreamRehearsalError(
                "duplicate deterministic response fixture identity: "
                + "/".join(fixture.key)
            )
        seen.add(fixture.key)
        records.append(fixture)
    if not records:
        raise DownstreamRehearsalError("response fixture file is empty")
    return LoadedDeterministicResponseFixtures(
        path=source,
        fixtures=tuple(records),
        sha256=_bytes_sha256(payload),
        byte_count=len(payload),
    )


def select_response_fixtures(
    fixtures: Iterable[DeterministicModelResponseFixture],
    *,
    stage: str,
    candidate_ids: Sequence[str],
    model_keys: Sequence[str],
) -> tuple[DeterministicModelResponseFixture, ...]:
    """Require exact candidate/model coverage and return provider-call order."""

    if stage not in _SUPPORTED_STAGES:
        raise DownstreamRehearsalError(f"unsupported response-fixture stage: {stage}")
    if not candidate_ids or len(candidate_ids) != len(set(candidate_ids)):
        raise DownstreamRehearsalError(
            "response-fixture candidate identities must be non-empty and unique"
        )
    if not model_keys or len(model_keys) != len(set(model_keys)):
        raise DownstreamRehearsalError(
            "response-fixture model identities must be non-empty and unique"
        )
    indexed: dict[tuple[str, str, str], DeterministicModelResponseFixture] = {}
    for fixture in fixtures:
        if fixture.stage != stage:
            continue
        if fixture.key in indexed:
            raise DownstreamRehearsalError(
                "duplicate deterministic response fixture identity: "
                + "/".join(fixture.key)
            )
        indexed[fixture.key] = fixture
    expected = {
        (stage, candidate_id, model_key)
        for candidate_id in candidate_ids
        for model_key in model_keys
    }
    if set(indexed) != expected:
        missing = sorted(expected - set(indexed))
        extra = sorted(set(indexed) - expected)
        raise DownstreamRehearsalError(
            "deterministic response fixture coverage mismatch; "
            f"missing={missing[:3]}, extra={extra[:3]}"
        )
    return tuple(
        indexed[(stage, candidate_id, model_key)]
        for candidate_id in candidate_ids
        for model_key in model_keys
    )


def fixture_provider_environ() -> Mapping[str, str]:
    """Return in-memory placeholders used only to build local HTTP requests."""

    return {
        "OPENAI_API_KEY": "fixture-only-not-a-provider-key",
        "ANTHROPIC_API_KEY": "fixture-only-not-a-provider-key",
        "GEMINI_API_KEY": "fixture-only-not-a-provider-key",
    }


def rehearsal_provenance(
    *, response_fixtures: LoadedDeterministicResponseFixtures
) -> JsonRecord:
    """Return explicit non-production provenance bound to fixture bytes."""

    return {
        **REHEARSAL_PROVENANCE,
        "response_fixture": {
            "path": str(response_fixtures.path),
            "sha256": response_fixtures.sha256,
            "byte_count": response_fixtures.byte_count,
        },
        "provider_journal_created": False,
        "provider_billing_usd": "0.00",
    }


def run_fixture_stage_a(
    *,
    selection_records: Sequence[Mapping[str, Any]],
    parser_records: Sequence[Mapping[str, Any]],
    markdown_root: Path,
    unitizer_entry: ModelRegistryEntry,
    unitizer_registry_sha256: str,
    reviewer_entry: ModelRegistryEntry,
    reviewer_registry_sha256: str,
    fixtures: Sequence[DeterministicModelResponseFixture],
) -> FixtureStageAResult:
    """Run unitization, structural review, and empty-queue apply locally."""

    unitized = run_fixture_unitization(
        selection_records=selection_records,
        parser_records=parser_records,
        markdown_root=markdown_root,
        unitizer_entry=unitizer_entry,
        unitizer_registry_sha256=unitizer_registry_sha256,
        fixtures=fixtures,
    )
    reviewed = run_fixture_structural_review(
        selection_records=selection_records,
        parser_records=parser_records,
        prediction_unit_records=unitized.raw_prediction_units,
        original_review_queue=unitized.original_review_queue,
        markdown_root=markdown_root,
        reviewer_entry=reviewer_entry,
        reviewer_registry_sha256=reviewer_registry_sha256,
        fixtures=fixtures,
    )
    finalized = apply_fixture_unitization_review(
        prediction_unit_records=unitized.raw_prediction_units,
        review_records=reviewed.merged_review_queue,
    )
    return FixtureStageAResult(
        raw_prediction_units=unitized.raw_prediction_units,
        unitization_audit=unitized.unitization_audit,
        original_review_queue=unitized.original_review_queue,
        structural_flags=reviewed.structural_flags,
        structural_review_audit=reviewed.structural_review_audit,
        merged_review_queue=reviewed.merged_review_queue,
        finalized_prediction_units=finalized,
        traces=(*unitized.traces, *reviewed.traces),
    )


def run_fixture_unitization(
    *,
    selection_records: Sequence[Mapping[str, Any]],
    parser_records: Sequence[Mapping[str, Any]],
    markdown_root: Path,
    unitizer_entry: ModelRegistryEntry,
    unitizer_registry_sha256: str,
    fixtures: Sequence[DeterministicModelResponseFixture],
) -> FixtureUnitizationResult:
    """Run only fixture Stage A unitization through the live validator."""

    candidate_ids = tuple(
        _required_str(row, "candidate_id") for row in selection_records
    )
    unitizer_transport = _stage_transport(
        fixtures,
        stage="llm-unitize",
        candidate_ids=candidate_ids,
        entries=(unitizer_entry,),
    )
    unitized = llm_unitize_cases(
        selection_records=selection_records,
        parser_records=parser_records,
        markdown_root=markdown_root,
        registry_entry=unitizer_entry,
        model_registry_sha256=unitizer_registry_sha256,
        transport=unitizer_transport,
        environ=fixture_provider_environ(),
        provider_journal_path=None,
    )
    unitizer_transport.require_exhausted()
    raw_units = tuple(dict(row) for row in unitized.records)
    original_queue = tuple(
        dict(row) for row in unitization_review_queue_records(unitized.audit_records)
    )
    return FixtureUnitizationResult(
        raw_prediction_units=raw_units,
        unitization_audit=_fixture_audit_rows(unitized),
        original_review_queue=original_queue,
        traces=unitizer_transport.traces,
    )


def run_fixture_structural_review(
    *,
    selection_records: Sequence[Mapping[str, Any]],
    parser_records: Sequence[Mapping[str, Any]],
    prediction_unit_records: Sequence[Mapping[str, Any]],
    original_review_queue: Sequence[Mapping[str, Any]],
    markdown_root: Path,
    reviewer_entry: ModelRegistryEntry,
    reviewer_registry_sha256: str,
    fixtures: Sequence[DeterministicModelResponseFixture],
) -> FixtureStructuralReviewResult:
    """Run only fixture Stage A structural review through the live validator."""

    candidate_ids = tuple(
        _required_str(row, "candidate_id") for row in selection_records
    )
    reviewer_transport = _stage_transport(
        fixtures,
        stage="llm-review-stage-a",
        candidate_ids=candidate_ids,
        entries=(reviewer_entry,),
    )
    reviewed = llm_review_stage_a_units(
        selection_records=selection_records,
        parser_records=parser_records,
        prediction_unit_records=prediction_unit_records,
        markdown_root=markdown_root,
        registry_entry=reviewer_entry,
        model_registry_sha256=reviewer_registry_sha256,
        transport=reviewer_transport,
        environ=fixture_provider_environ(),
        provider_journal_path=None,
    )
    reviewer_transport.require_exhausted()
    structural_flags = tuple(dict(row) for row in reviewed.records)
    merged_queue = tuple(
        dict(row)
        for row in merge_structural_flags_into_review_queue(
            original_review_queue, structural_flags
        )
    )
    return FixtureStructuralReviewResult(
        structural_flags=structural_flags,
        structural_review_audit=_fixture_audit_rows(reviewed),
        merged_review_queue=merged_queue,
        traces=reviewer_transport.traces,
    )


def apply_fixture_unitization_review(
    *,
    prediction_unit_records: Sequence[Mapping[str, Any]],
    review_records: Sequence[Mapping[str, Any]],
) -> tuple[JsonRecord, ...]:
    """Apply only an empty fixture Stage A queue using the live apply function."""

    merged_queue = tuple(dict(row) for row in review_records)
    if merged_queue:
        raise DownstreamRehearsalError(
            "fixture Stage A routed units to John; provide corrected deterministic "
            "fixtures instead of self-adjudicating the queue"
        )
    finalized = apply_unitization_reviews(
        prediction_unit_records=prediction_unit_records,
        review_records=merged_queue,
        adjudication_records=(),
    )
    return tuple(dict(row) for row in finalized)


def run_fixture_stage_b(
    *,
    selection_records: Sequence[Mapping[str, Any]],
    finalized_prediction_units: Sequence[Mapping[str, Any]],
    decision_text_artifact: VerifiedDecisionTextArtifact,
    judge_entries: Sequence[ModelRegistryEntry],
    judge_registry_sha256: str,
    fixtures: Sequence[DeterministicModelResponseFixture],
    apply_review: bool = True,
) -> FixtureStageBResult:
    """Run the live Stage B validators through local deterministic responses."""

    candidate_ids = tuple(
        _required_str(row, "candidate_id") for row in selection_records
    )
    transport = _stage_transport(
        fixtures,
        stage="llm-label",
        candidate_ids=candidate_ids,
        entries=judge_entries,
    )
    labeled = llm_label_cases(
        selection_records=selection_records,
        prediction_unit_records=finalized_prediction_units,
        decision_text_artifact=decision_text_artifact,
        registry_entries=judge_entries,
        model_registry_sha256=judge_registry_sha256,
        transport=transport,
        environ=fixture_provider_environ(),
        provider_journal_path=None,
    )
    transport.require_exhausted()
    queue = tuple(
        dict(row) for row in lawyer_review_queue_records(labeled.audit_records)
    )
    if apply_review:
        apply_fixture_label_review(review_records=queue)
    return FixtureStageBResult(
        labels=tuple(dict(row) for row in labeled.records),
        labeling_audit=_fixture_audit_rows(labeled),
        lawyer_review_queue=queue,
        traces=transport.traces,
    )


def apply_fixture_label_review(*, review_records: Sequence[Mapping[str, Any]]) -> None:
    """Apply only an empty fixture Stage B queue without self-adjudication."""

    queue = tuple(review_records)
    if queue:
        raise DownstreamRehearsalError(
            "fixture Stage B routed labels to John; provide unanimous, unambiguous "
            "deterministic fixtures instead of self-adjudicating the queue"
        )


def _stage_transport(
    fixtures: Sequence[DeterministicModelResponseFixture],
    *,
    stage: str,
    candidate_ids: Sequence[str],
    entries: Sequence[ModelRegistryEntry],
) -> DeterministicModelFixtureTransport:
    model_keys = tuple(entry.registry_key for entry in entries)
    selected = select_response_fixtures(
        fixtures,
        stage=stage,
        candidate_ids=candidate_ids,
        model_keys=model_keys,
    )
    return DeterministicModelFixtureTransport(
        selected,
        provider_by_model_key={entry.registry_key: entry.provider for entry in entries},
        requested_model_by_model_key={
            entry.registry_key: entry.model_id for entry in entries
        },
    )


def _fixture_audit_rows(result: LlmBatchResult) -> tuple[JsonRecord, ...]:
    return tuple(
        {
            **dict(row),
            **REHEARSAL_PROVENANCE,
            "fixture_response": True,
            "provider_call_executed": False,
            "provider_billing_usd": "0.00",
        }
        for row in result.audit_records
    )


def _request_prompt_and_model(
    request: urllib.request.Request,
    *,
    provider: str,
) -> tuple[str, str]:
    if request.data is None:
        raise DownstreamRehearsalError("fixture model request has no JSON body")
    try:
        if not isinstance(request.data, (bytes, bytearray)):
            raise DownstreamRehearsalError(
                "fixture model request body must be buffered bytes"
            )
        request_payload = bytes(request.data)
        value: object = json.loads(request_payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DownstreamRehearsalError(
            "fixture model request body is not valid JSON"
        ) from exc
    if not isinstance(value, Mapping):
        raise DownstreamRehearsalError("fixture model request body must be an object")
    payload = cast(Mapping[str, object], value)
    if provider == "openai":
        prompt = _required_str(payload, "input")
        model = _required_str(payload, "model")
    elif provider == "anthropic":
        model = _required_str(payload, "model")
        messages = _required_sequence(payload, "messages")
        if len(messages) != 1 or not isinstance(messages[0], Mapping):
            raise DownstreamRehearsalError(
                "fixture Anthropic request must contain one user message"
            )
        prompt = _required_str(cast(Mapping[str, object], messages[0]), "content")
    else:
        model = urllib.parse.unquote(
            request.full_url.split("/models/", 1)[-1].split(":", 1)[0]
        )
        contents = _required_sequence(payload, "contents")
        if len(contents) != 1 or not isinstance(contents[0], Mapping):
            raise DownstreamRehearsalError(
                "fixture Gemini request must contain one content item"
            )
        parts = _required_sequence(cast(Mapping[str, object], contents[0]), "parts")
        if len(parts) != 1 or not isinstance(parts[0], Mapping):
            raise DownstreamRehearsalError(
                "fixture Gemini request must contain one text part"
            )
        prompt = _required_str(cast(Mapping[str, object], parts[0]), "text")
    return prompt, model


def _provider_payload(
    fixture: DeterministicModelResponseFixture,
    *,
    provider: str,
) -> Mapping[str, object]:
    if provider == "openai":
        return {
            "model": fixture.served_model_version,
            "output_text": fixture.raw_output,
            "usage": {
                "input_tokens": fixture.input_tokens,
                "output_tokens": fixture.output_tokens,
            },
        }
    if provider == "anthropic":
        return {
            "model": fixture.served_model_version,
            "content": [{"type": "text", "text": fixture.raw_output}],
            "usage": {
                "input_tokens": fixture.input_tokens,
                "output_tokens": fixture.output_tokens,
            },
        }
    return {
        "modelVersion": fixture.served_model_version,
        "candidates": [{"content": {"parts": [{"text": fixture.raw_output}]}}],
        "usageMetadata": {
            "promptTokenCount": fixture.input_tokens,
            "candidatesTokenCount": fixture.output_tokens,
        },
    }


def _same_model_version(left: str, right: str) -> bool:
    def normalized(value: str) -> str:
        text = value.strip().lower()
        if text.startswith("models/"):
            text = text.removeprefix("models/")
        return text

    return normalized(left) == normalized(right)


def _required_str(record: Mapping[str, object], field_name: str) -> str:
    value = record.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise DownstreamRehearsalError(f"response fixture {field_name} is required")
    return value


def _required_nonnegative_int(record: Mapping[str, object], field_name: str) -> int:
    value = record.get(field_name)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise DownstreamRehearsalError(
            f"response fixture {field_name} must be a nonnegative integer"
        )
    return value


def _required_sequence(
    record: Mapping[str, object], field_name: str
) -> Sequence[object]:
    value = record.get(field_name)
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise DownstreamRehearsalError(
            f"fixture model request {field_name} must be a list"
        )
    return cast(Sequence[object], value)


def _require_prefixed_sha256(value: str, field_name: str) -> None:
    if len(value) != 71 or not value.startswith("sha256:"):
        raise DownstreamRehearsalError(
            f"response fixture {field_name} must be a sha256: digest"
        )
    try:
        int(value.removeprefix("sha256:"), 16)
    except ValueError as exc:
        raise DownstreamRehearsalError(
            f"response fixture {field_name} must be a sha256: digest"
        ) from exc


def _bytes_sha256(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()
