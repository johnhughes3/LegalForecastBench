"""Additive Cycle 1 Stage B runner for the authenticated manifest input pair.

The historical ``llm-unitize`` run-card is unavailable for the current Stage51
proposal.  This module is intentionally a narrow adapter: it authenticates the
owner-pinned raw unit bytes, derives an in-memory finalized-shaped view only for
the existing Stage B validators, and then delegates prompt construction,
response validation, and provider journaling to ``llm_pipeline``.  It never
changes the legacy acquisition command or publishes a finalized Stage-A
artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from legalforecast.evals.model_registry import (
    ModelRegistryEntry,
    load_model_registry,
)
from legalforecast.evals.provider_spend_control import (
    FrozenAttemptPolicy,
    ProviderSpendAuthority,
    SqliteProviderSpendAuthority,
)
from legalforecast.ingestion.decision_text_artifact import (
    VerifiedDecisionTextArtifact,
)
from legalforecast.labeling.llm_pipeline import (
    _labeling_prompt,  # pyright: ignore[reportPrivateUsage]
    _llm_label_one_model,  # pyright: ignore[reportPrivateUsage]
    _prediction_units_by_candidate,  # pyright: ignore[reportPrivateUsage]
    _required_str,  # pyright: ignore[reportPrivateUsage]
    _verified_stage_b_decisions,  # pyright: ignore[reportPrivateUsage]
)
from legalforecast.unitization.review import canonical_records_sha256, canonical_sha256

JsonRecord = dict[str, Any]

RAW_UNITS_SHA256 = "9bfe41369e50f1dd110ca1d214a9413c6afa60b2f655175e2463796c3d06502a"
DECISION_TEXTS_SHA256 = (
    "01fc5d325b45677ce1f67db1eb1b958ebc9af53d75a7bb496c95b387525a44d7"
)
CURRENT_SELECTION_SHA256 = (
    "ff94024b60fd976edace2bcea0ffc28923651fd0ae36859e6b654e526730dfee"
)
STAGE_B_REGISTRY_SHA256 = (
    "5243b74bfdb2d3accc1a301f7c997b9520abc8586bbf944e22f67e2b263106a2"
)
SPEND_APPROVAL = (
    "I approve up to USD 300 of provider spend for the Cycle 1 Stage B label run, "
    "estimated USD 15, across GPT-5.4 mini and Gemini 3.5 Flash."
)
BEAD_ID = "legalforecastbench-3ak.38.18"
TERMINAL_APPROVAL_BEAD_ID = "legalforecastbench-3ak.38"
TERMINAL_PACKET_APPROVAL = (
    "stage51-terminal-units: approved — packet "
    "8617ee835c3578042a1081f484d6520de187c5da8367e1e6a71228262266dcca"
)
OWNER_CAP_USD = 300.0
EXPECTED_CASE_COUNT = 100
EXPECTED_UNIT_COUNT = 425
MODEL_KEYS = (
    "openai:gpt-5.4-mini-2026-03-17",
    "google:gemini-3.5-flash",
)
PROVIDER_CAP_USD = {"openai": 80.0, "google": 220.0}


class StageBManifestError(ValueError):
    """Raised when the owner-pinned manifest inputs are not exact."""


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _read_regular(path: Path, label: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise StageBManifestError(f"{label} must be a regular non-symlink file: {path}")
    return path.read_bytes()


def _jsonl(payload: bytes, label: str) -> tuple[JsonRecord, ...]:
    records: list[JsonRecord] = []
    for line_number, line in enumerate(payload.splitlines(), 1):
        if not line.strip():
            continue
        try:
            value: object = json.loads(line)
        except json.JSONDecodeError as exc:
            raise StageBManifestError(
                f"{label} has invalid JSON at line {line_number}"
            ) from exc
        if not isinstance(value, Mapping):
            raise StageBManifestError(f"{label} line {line_number} is not an object")
        records.append(dict(cast(Mapping[str, object], value)))
    return tuple(records)


def _json_object(payload: bytes, label: str) -> Mapping[str, object]:
    try:
        value: object = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise StageBManifestError(f"{label} is not valid JSON") from exc
    if not isinstance(value, Mapping):
        raise StageBManifestError(f"{label} is not a JSON object")
    return cast(Mapping[str, object], value)


def _canonical_jsonl(records: Iterable[Mapping[str, object]]) -> bytes:
    return b"".join(
        json.dumps(
            dict(record), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        + b"\n"
        for record in records
    )


def _write_create_only(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        existing = _read_regular(path, f"create-only output {path}")
        if existing != payload:
            raise StageBManifestError(f"create-only output differs: {path}")
        return
    with path.open("xb") as stream:
        stream.write(payload)


def _owner_approval_ids() -> tuple[str, ...]:
    """Return exact owner comment IDs for spend and the terminal packet."""

    def comments(bead_id: str) -> list[Mapping[str, object]]:
        try:
            completed = subprocess.run(
                ["bd", "comments", bead_id, "--json"],
                check=True,
                capture_output=True,
                text=True,
            )
            value: object = json.loads(completed.stdout)
        except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
            raise StageBManifestError(
                f"could not read owner approval from Beads: {bead_id}"
            ) from exc
        if not isinstance(value, list):
            raise StageBManifestError(
                f"Beads comments response is not an array: {bead_id}"
            )
        return [
            cast(Mapping[str, object], raw)
            for raw in cast(list[object], value)
            if isinstance(raw, Mapping)
        ]

    spend_comments = comments(BEAD_ID)
    terminal_comments = comments(TERMINAL_APPROVAL_BEAD_ID)
    spend_ids: list[str] = []
    terminal_ids: list[str] = []
    for comment in spend_comments:
        if comment.get("author") != "John Hughes":
            continue
        text = comment.get("text")
        comment_id = comment.get("id")
        if not isinstance(text, str) or not isinstance(comment_id, str):
            continue
        if text == SPEND_APPROVAL:
            spend_ids.append(comment_id)
    for comment in terminal_comments:
        if comment.get("author") != "John Hughes":
            continue
        text = comment.get("text")
        comment_id = comment.get("id")
        if text == TERMINAL_PACKET_APPROVAL and isinstance(comment_id, str):
            terminal_ids.append(comment_id)
    if not spend_ids:
        raise StageBManifestError("exact USD 300 Stage B owner approval is missing")
    if not terminal_ids:
        raise StageBManifestError("terminal-unit packet approval is missing")
    return tuple(sorted(set((*spend_ids, *terminal_ids))))


def _manifest_units(raw_records: Sequence[Mapping[str, Any]]) -> tuple[JsonRecord, ...]:
    """Derive a local validation view without claiming Stage-A finalization."""

    envelopes: list[JsonRecord] = []
    for raw in raw_records:
        candidate_id = _required_str(raw, "candidate_id")
        case_id = _required_str(raw, "case_id")
        units_value = raw.get("prediction_units")
        if not isinstance(units_value, Sequence) or isinstance(
            units_value, (str, bytes)
        ):
            raise StageBManifestError(
                f"raw units missing prediction_units: {candidate_id}"
            )
        units: list[JsonRecord] = []
        for unit_value in cast(Sequence[object], units_value):
            if not isinstance(unit_value, Mapping):
                raise StageBManifestError(f"raw unit is not an object: {candidate_id}")
            unit = dict(cast(Mapping[str, Any], unit_value))
            unit_id = _required_str(unit, "unit_id")
            digest = canonical_sha256(unit)
            unit.update(
                {
                    "source_unit_sha256s": [digest],
                    "adjudication_id": f"automatic:{digest}",
                    "adjudication_sha256": None,
                    "disposition": "ACCEPT",
                }
            )
            if unit.get("unit_id") != unit_id:
                raise StageBManifestError(
                    "unit identity changed while adapting raw units"
                )
            units.append(unit)
        if not units:
            raise StageBManifestError(f"raw units envelope is empty: {candidate_id}")
        envelopes.append(
            {
                "schema_version": "legalforecast.finalized_prediction_units.v1",
                "status": "finalized",
                "candidate_id": candidate_id,
                "case_id": case_id,
                "raw_prediction_units_sha256": canonical_sha256(raw),
                "unitization_review_queue_sha256": canonical_records_sha256(()),
                "prediction_units": units,
                "exclusion": None,
            }
        )
    return tuple(envelopes)


def _validate_raw_inputs(raw_path: Path) -> tuple[JsonRecord, ...]:
    raw_bytes = _read_regular(raw_path, "raw prediction units")
    if _sha256(raw_bytes) != RAW_UNITS_SHA256:
        raise StageBManifestError(
            "raw prediction-units bytes differ from owner commitment"
        )
    records = _jsonl(raw_bytes, "raw prediction units")
    if len(records) != EXPECTED_CASE_COUNT:
        raise StageBManifestError(
            f"expected {EXPECTED_CASE_COUNT} raw cases, got {len(records)}"
        )
    candidate_ids = [_required_str(record, "candidate_id") for record in records]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise StageBManifestError(
            "raw prediction units contain duplicate candidate IDs"
        )
    unit_count = sum(
        len(cast(Sequence[object], record["prediction_units"])) for record in records
    )
    if unit_count != EXPECTED_UNIT_COUNT:
        raise StageBManifestError(
            f"expected {EXPECTED_UNIT_COUNT} raw units, got {unit_count}"
        )
    return records


def _validate_registry(registry_path: Path) -> tuple[ModelRegistryEntry, ...]:
    registry_bytes = _read_regular(registry_path, "Stage B model registry")
    if _sha256(registry_bytes) != STAGE_B_REGISTRY_SHA256:
        raise StageBManifestError("Stage B registry bytes differ from owner commitment")
    registry = load_model_registry(registry_path)
    by_key = {entry.registry_key: entry for entry in registry.entries}
    if set(by_key) != set(MODEL_KEYS):
        raise StageBManifestError(
            "registry must contain exactly the two approved Stage B model keys"
        )
    for entry in by_key.values():
        if (
            not entry.network_disabled
            or not entry.search_disabled
            or entry.tool_policy.value != "no_tools"
        ):
            raise StageBManifestError(
                f"unsafe Stage B registry policy: {entry.registry_key}"
            )
    return tuple(by_key[key] for key in MODEL_KEYS)


def _current_decision_record(
    *,
    selection: Mapping[str, Any],
    decision_store_root: Path,
    input_commitments: Mapping[str, str],
) -> JsonRecord:
    candidate_id = _required_str(selection, "candidate_id")
    case_id = _required_str(selection, "case_id")
    outcome_documents: list[Mapping[str, Any]] = []
    for value in cast(Sequence[object], selection.get("documents")):
        if not isinstance(value, Mapping):
            continue
        document_value = cast(Mapping[str, Any], value)
        if (
            document_value.get("contains_target_outcome") is True
            and document_value.get("model_visible") is False
            and document_value.get("document_role") in {"decision", "order"}
        ):
            outcome_documents.append(document_value)
    if len(outcome_documents) != 1:
        raise StageBManifestError(
            f"expected exactly one outcome document: {candidate_id}"
        )
    document = outcome_documents[0]
    source_document_id = _required_str(document, "source_document_id")
    metadata_path = decision_store_root / f"{source_document_id}.metadata.json"
    markdown_path = decision_store_root / f"{source_document_id}.md"
    metadata = _json_object(
        _read_regular(metadata_path, "decision metadata"), "decision metadata"
    )
    markdown = _read_regular(markdown_path, "decision markdown")
    if (
        metadata.get("candidate_id") != candidate_id
        or metadata.get("source_document_id") != source_document_id
        or metadata.get("status") != "succeeded"
    ):
        raise StageBManifestError(
            f"decision metadata identity differs: {candidate_id}/{source_document_id}"
        )
    extracted = metadata.get("extracted_text")
    if not isinstance(extracted, Mapping):
        raise StageBManifestError(
            f"decision metadata lacks extracted_text: {candidate_id}"
        )
    extracted_record = cast(Mapping[str, object], extracted)
    markdown_sha256 = _sha256(markdown)
    if extracted_record.get("text_sha256") != markdown_sha256:
        raise StageBManifestError(f"decision markdown hash differs: {candidate_id}")
    source_path_value = metadata.get("input_path")
    source_sha256 = metadata.get("source_sha256")
    if not isinstance(source_path_value, str) or not isinstance(source_sha256, str):
        raise StageBManifestError(
            f"decision metadata lacks source binding: {candidate_id}"
        )
    source_path = Path(source_path_value)
    source_bytes = _read_regular(source_path, "decision source PDF")
    if _sha256(source_bytes) != source_sha256:
        raise StageBManifestError(f"decision source PDF hash differs: {candidate_id}")
    try:
        text = markdown.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise StageBManifestError(
            f"decision markdown is not UTF-8: {candidate_id}"
        ) from exc
    docket_entry = document.get("docket_entry_number")
    if not isinstance(docket_entry, int):
        raise StageBManifestError(f"decision docket entry is missing: {candidate_id}")
    entered_date = selection.get("decision_date")
    if not isinstance(entered_date, str) or not entered_date:
        raise StageBManifestError(f"decision date is missing: {candidate_id}")
    return {
        "schema_version": "legalforecast.decision_text.v1",
        "candidate_id": candidate_id,
        "case_id": case_id,
        "document_id": f"{candidate_id}-entry-{docket_entry}-decision",
        "source_document_id": source_document_id,
        "document_role": document.get("document_role"),
        "docket_entry_number": docket_entry,
        "entered_date": entered_date,
        "is_first_written_disposition": True,
        "contains_target_outcome": True,
        "model_visible": False,
        "extraction_method": extracted_record.get("extraction_method"),
        "parser_revision": cast(
            Mapping[str, object], metadata.get("parser_config", {})
        ).get("parser_revision"),
        "source_byte_count": len(source_bytes),
        "source_sha256": source_sha256,
        "markdown_sha256": markdown_sha256,
        "text_sha256": markdown_sha256,
        "text": text,
        "input_commitments": dict(input_commitments),
    }


def _verified_inputs(
    *,
    raw_path: Path,
    decision_texts_path: Path,
    selection_path: Path,
    decision_store_root: Path,
    adapted_path: Path,
    raw_records: Sequence[Mapping[str, Any]],
) -> tuple[
    VerifiedDecisionTextArtifact, tuple[JsonRecord, ...], tuple[JsonRecord, ...]
]:
    decision_bytes = _read_regular(decision_texts_path, "decision texts")
    if _sha256(decision_bytes) != DECISION_TEXTS_SHA256:
        raise StageBManifestError("decision-text bytes differ from owner commitment")
    legacy_decisions = _jsonl(decision_bytes, "decision texts")
    if len(legacy_decisions) != EXPECTED_CASE_COUNT:
        raise StageBManifestError("decision-text count is not exactly 100")
    selection_bytes = _read_regular(selection_path, "selection")
    if _sha256(selection_bytes) != CURRENT_SELECTION_SHA256:
        raise StageBManifestError(
            "selection bytes differ from current Stage51 commitment"
        )
    selection_records = _jsonl(selection_bytes, "selection")
    adapted_records = _manifest_units(raw_records)
    adapted_bytes = _canonical_jsonl(adapted_records)
    _write_create_only(adapted_path, adapted_bytes)
    selected_by_id = {
        _required_str(record, "candidate_id"): record for record in selection_records
    }
    if len(selected_by_id) != EXPECTED_CASE_COUNT or set(selected_by_id) != {
        _required_str(record, "candidate_id") for record in raw_records
    }:
        raise StageBManifestError("selection and raw-unit candidate coverage differ")
    legacy_by_id = {
        _required_str(record, "candidate_id"): record for record in legacy_decisions
    }
    shared_commitments = {
        "legacy_decision_texts_sha256": DECISION_TEXTS_SHA256,
        "raw_prediction_units_sha256": RAW_UNITS_SHA256,
        "selection_sha256": CURRENT_SELECTION_SHA256,
    }
    decisions: list[JsonRecord] = []
    for candidate_id, selection in selected_by_id.items():
        legacy = legacy_by_id.get(candidate_id)
        if legacy is None:
            record = _current_decision_record(
                selection=selection,
                decision_store_root=decision_store_root,
                input_commitments=shared_commitments,
            )
        else:
            record = dict(legacy)
            if record.get("case_id") != selection.get("case_id") or record.get(
                "entered_date"
            ) != selection.get("decision_date"):
                raise StageBManifestError(
                    "retained decision text differs from current selection: "
                    f"{candidate_id}"
                )
            record["input_commitments"] = dict(shared_commitments)
        normalized_text = _required_str(record, "text")
        record["text"] = normalized_text
        record["text_sha256"] = _sha256(normalized_text.encode("utf-8"))
        decisions.append(record)
    decision_payload = _canonical_jsonl(decisions)
    current_decision_path = adapted_path.parent / "decision-texts-current.jsonl"
    _write_create_only(current_decision_path, decision_payload)
    manifest = {
        "schema_version": "legalforecast.stage_b_manifest_decision_texts.v1",
        **shared_commitments,
        "record_count": len(decisions),
        "decision_texts_sha256": _sha256(decision_payload),
        "record_sha256s": {
            _required_str(record, "candidate_id"): canonical_sha256(record)
            for record in decisions
        },
    }
    manifest_payload = (
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    manifest_path = adapted_path.parent / "decision-texts-current-manifest.json"
    _write_create_only(manifest_path, manifest_payload)
    run_card = {
        "schema_version": "legalforecast.stage_b_manifest_decision_texts_run.v1",
        "status": "completed",
        "paid_activity_executed": False,
        "manifest_sha256": _sha256(manifest_payload),
        "decision_texts_sha256": _sha256(decision_payload),
    }
    run_card_payload = (
        json.dumps(run_card, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    run_card_path = adapted_path.parent / "decision-texts-current-run-card.json"
    _write_create_only(run_card_path, run_card_payload)
    artifact = VerifiedDecisionTextArtifact(
        records=tuple(decisions),
        decision_texts_sha256=_sha256(decision_payload),
        manifest_sha256=_sha256(manifest_payload),
        run_card_sha256=_sha256(run_card_payload),
        finalized_prediction_units_sha256=RAW_UNITS_SHA256,
        finalized_unit_envelope_sha256s={
            _required_str(record, "candidate_id"): canonical_sha256(raw)
            for record, raw in zip(adapted_records, raw_records, strict=True)
        },
        input_commitments=shared_commitments,
    )
    _verified_stage_b_decisions(artifact)
    return artifact, selection_records, adapted_records


def _source_digest(path: Path) -> str:
    return _sha256(_read_regular(path, str(path)))


def _result_path(output_root: Path, provider: str, candidate_id: str) -> Path:
    safe_candidate = "".join(
        character
        for character in candidate_id
        if character.isalnum() or character in "-_"
    )
    if safe_candidate != candidate_id or not safe_candidate:
        raise StageBManifestError(
            f"unsafe candidate ID for output path: {candidate_id}"
        )
    return output_root / "results" / provider / f"{safe_candidate}.json"


def _existing_result(
    path: Path,
    *,
    candidate_id: str,
    provider: str,
    model_key: str,
    raw_sha256: str,
    decision_sha256: str,
    registry_sha256: str,
) -> JsonRecord | None:
    if not path.exists():
        return None
    value = _json_object(
        _read_regular(path, f"existing result {path}"), f"existing result {path}"
    )
    expected = {
        "schema_version": "legalforecast.stage_b_manifest_provider_result.v1",
        "candidate_id": candidate_id,
        "provider": provider,
        "model_key": model_key,
        "raw_prediction_units_sha256": raw_sha256,
        "decision_texts_sha256": decision_sha256,
        "model_registry_sha256": registry_sha256,
        "status": "succeeded",
    }
    for key, expected_value in expected.items():
        if value.get(key) != expected_value:
            raise StageBManifestError(f"existing result identity differs: {path}")
    return dict(cast(Mapping[str, Any], value))


def _authority_identity(
    *, raw_sha256: str, decision_sha256: str, registry_sha256: str, provider: str
) -> str:
    payload = json.dumps(
        {
            "bead": BEAD_ID,
            "decision_texts_sha256": decision_sha256,
            "owner_cap_usd": OWNER_CAP_USD,
            "provider": provider,
            "raw_prediction_units_sha256": raw_sha256,
            "registry_sha256": registry_sha256,
            "spend_approval": SPEND_APPROVAL,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return _sha256(payload)


def _execute_provider(
    *,
    provider: str,
    output_root: Path,
    raw_path: Path,
    decision_texts_path: Path,
    artifact: VerifiedDecisionTextArtifact,
    selection_records: Sequence[Mapping[str, Any]],
    adapted_records: Sequence[Mapping[str, Any]],
    registry_entry: ModelRegistryEntry,
    registry_sha256: str,
    raw_sha256: str,
    decision_sha256: str,
    max_cases: int | None,
) -> tuple[JsonRecord, ...]:
    del raw_path, decision_texts_path
    if provider not in PROVIDER_CAP_USD:
        raise StageBManifestError(f"unsupported execution provider: {provider}")
    units_by_candidate = _prediction_units_by_candidate(adapted_records)
    decisions_by_candidate = _verified_stage_b_decisions(artifact)
    selections_by_candidate = {
        _required_str(selection, "candidate_id"): selection
        for selection in selection_records
    }
    if set(selections_by_candidate) != set(units_by_candidate) or set(
        selections_by_candidate
    ) != set(decisions_by_candidate):
        raise StageBManifestError(
            "selection, adapted units, and decision texts do not cover the same "
            "candidates"
        )
    candidate_ids = list(selections_by_candidate)
    if max_cases is not None:
        if max_cases <= 0:
            raise StageBManifestError("max_cases must be positive")
        candidate_ids = candidate_ids[:max_cases]
    journal_path = output_root / "provider-attempts.sqlite3"
    authority_path = output_root / f"spend-authority-{provider}.sqlite3"
    account = f"cycle1-{provider}"
    authority = SqliteProviderSpendAuthority(
        authority_path,
        authority_identity_sha256=_authority_identity(
            raw_sha256=raw_sha256,
            decision_sha256=decision_sha256,
            registry_sha256=registry_sha256,
            provider=provider,
        ),
        cycle_id="cycle-1-stage-b-manifest",
        provider=provider,
        account=account,
        cap_microusd=int(PROVIDER_CAP_USD[provider] * 1_000_000),
        policy=FrozenAttemptPolicy(
            reservation_ledger_sha256=_authority_identity(
                raw_sha256=raw_sha256,
                decision_sha256=decision_sha256,
                registry_sha256=registry_sha256,
                provider=provider,
            ),
            max_billable_attempts=1,
            failure_threshold=5,
            failure_window_seconds=86_400,
        ),
    )
    records: list[JsonRecord] = []
    try:
        for candidate_id in candidate_ids:
            selection = selections_by_candidate[candidate_id]
            result_path = _result_path(output_root, provider, candidate_id)
            prior = _existing_result(
                result_path,
                candidate_id=candidate_id,
                provider=provider,
                model_key=registry_entry.registry_key,
                raw_sha256=raw_sha256,
                decision_sha256=decision_sha256,
                registry_sha256=registry_sha256,
            )
            if prior is not None:
                records.append(cast(JsonRecord, prior["audit"]))
                continue
            frozen_units = tuple(units_by_candidate[candidate_id])
            decision_text, commitment = decisions_by_candidate[candidate_id]
            prompt = _labeling_prompt(
                selection,
                decision_text,
                frozen_units,
                decision_text_commitment=commitment,
            )
            authorities: Mapping[str, ProviderSpendAuthority] = {provider: authority}
            accounts = {provider: account}
            try:
                labels, response, finding_count, missing_count, prompt_sha256 = (
                    _llm_label_one_model(
                        selection=selection,
                        decision_text=decision_text,
                        decision_text_commitment=commitment,
                        frozen_units=frozen_units,
                        prompt=prompt,
                        registry_entry=registry_entry,
                        model_registry_sha256=registry_sha256,
                        transport=None,
                        environ=None,
                        timeout_seconds=120.0,
                        max_provider_attempts=1,
                        provider_journal_path=journal_path,
                        provider_cycle_cap_usd=PROVIDER_CAP_USD[provider],
                        provider_cycle_id="cycle-1-stage-b-manifest",
                        provider_cycle_caps_sha256=_authority_identity(
                            raw_sha256=raw_sha256,
                            decision_sha256=decision_sha256,
                            registry_sha256=registry_sha256,
                            provider=provider,
                        ),
                        provider_spend_authorities=authorities,
                        provider_accounts=accounts,
                    )
                )
            except Exception as exc:
                failure = {
                    "schema_version": (
                        "legalforecast.stage_b_manifest_provider_result.v1"
                    ),
                    "status": "failed",
                    "candidate_id": candidate_id,
                    "case_id": _required_str(selection, "case_id"),
                    "provider": provider,
                    "model_key": registry_entry.registry_key,
                    "model_registry_sha256": registry_sha256,
                    "raw_prediction_units_sha256": raw_sha256,
                    "raw_candidate_envelope_sha256": (
                        artifact.finalized_unit_envelope_sha256s[candidate_id]
                    ),
                    "decision_texts_sha256": decision_sha256,
                    "provider_sampling_policy": "provider_default",
                    "tools_enabled": False,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                }
                _write_create_only(
                    result_path,
                    (
                        json.dumps(
                            failure,
                            ensure_ascii=False,
                            sort_keys=True,
                            indent=2,
                        )
                        + "\n"
                    ).encode(),
                )
                raise
            model_output = {
                "model_key": registry_entry.registry_key,
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "estimated_cost": response.estimated_cost,
                "raw_output_sha256": response.raw_output_sha256,
                "finding_count": finding_count,
                "missing_unit_flag_count": missing_count,
                "provider_prompt_sha256": prompt_sha256,
                "metadata": dict(response.metadata or {}),
                "labels": [label.to_record() for label in labels],
            }
            audit: JsonRecord = {
                "stage": "llm-label-provider-shard",
                "status": "succeeded",
                "candidate_id": candidate_id,
                "case_id": _required_str(selection, "case_id"),
                "execution_provider": provider,
                "model_keys": [registry_entry.registry_key],
                "frozen_panel_model_keys": list(MODEL_KEYS),
                "model_registry_sha256": registry_sha256,
                "decision_text_commitment": commitment,
                "label_count": 0,
                "unit_count": len(frozen_units),
                "model_outputs": [model_output],
                "estimated_cost": response.estimated_cost,
            }
            result = {
                "schema_version": "legalforecast.stage_b_manifest_provider_result.v1",
                "status": "succeeded",
                "candidate_id": candidate_id,
                "case_id": _required_str(selection, "case_id"),
                "provider": provider,
                "model_key": registry_entry.registry_key,
                "model_registry_sha256": registry_sha256,
                "raw_prediction_units_sha256": raw_sha256,
                "raw_candidate_envelope_sha256": (
                    artifact.finalized_unit_envelope_sha256s[candidate_id]
                ),
                "decision_texts_sha256": decision_sha256,
                "provider_sampling_policy": "provider_default",
                "tools_enabled": False,
                "audit": audit,
            }
            _write_create_only(
                result_path,
                (
                    json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2)
                    + "\n"
                ).encode(),
            )
            records.append(audit)
    finally:
        authority.close()
    return tuple(records)


def run(args: argparse.Namespace) -> int:
    raw_path = Path(args.raw_prediction_units).resolve()
    decision_texts_path = Path(args.decision_texts).resolve()
    selection_path = Path(args.selection).resolve()
    decision_store_root = Path(args.decision_store_root).resolve()
    registry_path = Path(args.model_registry).resolve()
    output_root = Path(args.output_root).resolve()
    owner_comment_ids = _owner_approval_ids()
    raw_records = _validate_raw_inputs(raw_path)
    registry_entries = _validate_registry(registry_path)
    registry_sha256 = _source_digest(registry_path)
    raw_sha256 = _source_digest(raw_path)
    legacy_decision_sha256 = _source_digest(decision_texts_path)
    adapted_path = output_root / "stageb-manifest-input-adapter.jsonl"
    artifact, selection_records, adapted_records = _verified_inputs(
        raw_path=raw_path,
        decision_texts_path=decision_texts_path,
        selection_path=selection_path,
        decision_store_root=decision_store_root,
        adapted_path=adapted_path,
        raw_records=raw_records,
    )
    if registry_sha256 != STAGE_B_REGISTRY_SHA256 or raw_sha256 != RAW_UNITS_SHA256:
        raise StageBManifestError("authenticated source commitment changed")
    if legacy_decision_sha256 != DECISION_TEXTS_SHA256:
        raise StageBManifestError("legacy decision-text commitment changed")
    decision_sha256 = artifact.decision_texts_sha256
    provider = args.provider
    if not args.execute:
        plan = {
            "schema_version": "legalforecast.stage_b_manifest_plan.v1",
            "execute": False,
            "owner_bead": BEAD_ID,
            "owner_comment_ids": list(owner_comment_ids),
            "owner_cap_usd": OWNER_CAP_USD,
            "estimated_cost_usd": 15.0,
            "raw_prediction_units_sha256": raw_sha256,
            "raw_case_count": len(raw_records),
            "raw_unit_count": sum(
                len(cast(Sequence[object], record["prediction_units"]))
                for record in raw_records
            ),
            "decision_texts_sha256": decision_sha256,
            "model_registry_sha256": registry_sha256,
            "model_keys": list(MODEL_KEYS),
            "provider": provider,
            "provider_sampling_policy": "provider_default",
            "tools_enabled": False,
            "create_only": True,
            "resume": True,
            "legacy_llm_unitize_path": "untouched",
            "decision_text_verified": True,
        }
        payload = (
            json.dumps(plan, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        ).encode()
        _write_create_only(output_root / "dry-run-plan.json", payload)
        print(json.dumps(plan, sort_keys=True))
        return 0
    if provider is None:
        raise StageBManifestError("--execute requires exactly one --provider shard")
    entry = next(
        (item for item in registry_entries if item.provider.lower() == provider), None
    )
    if entry is None:
        raise StageBManifestError(
            f"provider is not in the approved registry: {provider}"
        )
    audits = _execute_provider(
        provider=provider,
        output_root=output_root,
        raw_path=raw_path,
        decision_texts_path=decision_texts_path,
        artifact=artifact,
        selection_records=selection_records,
        adapted_records=adapted_records,
        registry_entry=entry,
        registry_sha256=registry_sha256,
        raw_sha256=raw_sha256,
        decision_sha256=decision_sha256,
        max_cases=args.max_cases,
    )
    print(
        json.dumps(
            {
                "provider": provider,
                "succeeded": len(audits),
                "output_root": str(output_root),
            },
            sort_keys=True,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-prediction-units", required=True, type=Path)
    parser.add_argument("--selection", required=True, type=Path)
    parser.add_argument("--decision-texts", required=True, type=Path)
    parser.add_argument("--decision-store-root", required=True, type=Path)
    parser.add_argument("--model-registry", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--provider", choices=("openai", "google"))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--max-cases", type=int)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return run(build_parser().parse_args(argv))
    except StageBManifestError as exc:
        raise SystemExit(f"stageb-manifest: {exc}") from exc


if __name__ == "__main__":
    main()
