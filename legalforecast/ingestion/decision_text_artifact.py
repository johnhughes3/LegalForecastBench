"""Build hash-bound first-written-disposition text artifacts for label audit."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, cast

from legalforecast.ingestion.mistral_markdown_parser import EXPECTED_PARSER_REVISION

SCHEMA_VERSION = "legalforecast.decision_text.v1"
MANIFEST_SCHEMA_VERSION = "legalforecast.decision_text_manifest.v1"
CYCLE_1_ELIGIBILITY_ANCHOR = date(2026, 6, 30)
_PUBLIC_STATUSES = frozenset({"public", "redacted"})
_OUTCOME_ROLES = frozenset({"decision", "order"})

JsonRecord = dict[str, Any]
DocumentKey = tuple[str, str]


class DecisionTextArtifactError(ValueError):
    """Raised when decision text provenance cannot be proven exactly."""


@dataclass(frozen=True, slots=True)
class VerifiedDecisionTextArtifact:
    """Authenticated Stage B evidence and its immutable commitments."""

    records: tuple[Mapping[str, Any], ...]
    decision_texts_sha256: str
    manifest_sha256: str
    run_card_sha256: str
    finalized_prediction_units_sha256: str
    finalized_unit_envelope_sha256s: Mapping[str, str]
    input_commitments: Mapping[str, str]

    def record_commitment(self, record: Mapping[str, Any]) -> str:
        """Return the canonical commitment for one authenticated record."""

        return _canonical_sha256(record)

    def stage_b_commitments(self) -> Mapping[str, Mapping[str, str]]:
        """Return the exact per-candidate commitments emitted by Stage B."""

        commitments: dict[str, Mapping[str, str]] = {}
        for record in self.records:
            candidate_id = _required_str(record, "candidate_id")
            text = _required_str(record, "text")
            text_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
            commitments[candidate_id] = {
                "decision_texts_sha256": self.decision_texts_sha256,
                "decision_texts_manifest_sha256": self.manifest_sha256,
                "decision_texts_run_card_sha256": self.run_card_sha256,
                "decision_text_record_sha256": self.record_commitment(record),
                "decision_text_sha256": "sha256:" + text_sha256,
                "decision_text_case_id": _required_str(record, "case_id"),
                "finalized_prediction_units_sha256": (
                    self.finalized_prediction_units_sha256
                ),
                "finalized_unit_envelope_sha256": (
                    self.finalized_unit_envelope_sha256s[candidate_id]
                ),
            }
        return commitments

    def verify_stage_b_audit_commitments(
        self, audit_records: Sequence[Mapping[str, Any]]
    ) -> None:
        """Require every Stage B audit row to bind this exact artifact."""

        expected = self.stage_b_commitments()
        actual: dict[str, Mapping[str, Any]] = {}
        for record in audit_records:
            if record.get("stage") != "llm-label":
                continue
            candidate_id = _required_str(record, "candidate_id")
            if candidate_id in actual:
                raise DecisionTextArtifactError(
                    f"duplicate Stage B label audit candidate: {candidate_id}"
                )
            actual[candidate_id] = _mapping(
                record.get("decision_text_commitment"),
                f"Stage B decision_text_commitment for {candidate_id}",
            )
        if set(actual) != set(expected):
            raise DecisionTextArtifactError(
                "Stage B decision-text commitment coverage mismatch"
            )
        for candidate_id, commitment in actual.items():
            if dict(commitment) != dict(expected[candidate_id]):
                raise DecisionTextArtifactError(
                    f"Stage B decision-text commitment mismatch: {candidate_id}"
                )


def verify_decision_text_artifact(
    *,
    decision_texts_path: Path,
    manifest_path: Path,
    run_card_path: Path,
    selections: Sequence[Mapping[str, Any]],
    selection_path: Path,
    parser_records: Sequence[Mapping[str, Any]],
    parser_manifest_path: Path,
    finalized_unit_records: Sequence[Mapping[str, Any]],
    finalized_units_path: Path,
    markdown_root: Path,
) -> VerifiedDecisionTextArtifact:
    """Authenticate all Stage B text before any provider call is possible."""

    decision_payload = _read_regular_file(decision_texts_path, "decision texts")
    manifest_payload = _read_regular_file(manifest_path, "decision text manifest")
    run_card_payload = _read_regular_file(run_card_path, "decision text run card")
    selection_payload = _read_regular_file(selection_path, "selection")
    parser_payload = _read_regular_file(parser_manifest_path, "parser manifest")
    finalized_units_payload = _read_regular_file(
        finalized_units_path, "finalized prediction units"
    )
    records = _jsonl_records(decision_payload, label="decision texts")
    manifest = _json_object(manifest_payload, label="decision text manifest")
    run_card = _json_object(run_card_payload, label="decision text run card")
    authenticated_selections = _jsonl_records(selection_payload, label="selection")
    authenticated_parser_records = _jsonl_records(
        parser_payload, label="parser manifest"
    )
    authenticated_finalized_units = _jsonl_records(
        finalized_units_payload, label="finalized prediction units"
    )
    if tuple(dict(record) for record in selections) != tuple(
        dict(record) for record in authenticated_selections
    ):
        raise DecisionTextArtifactError(
            "loaded selection differs from authenticated bytes"
        )
    if tuple(dict(record) for record in parser_records) != tuple(
        dict(record) for record in authenticated_parser_records
    ):
        raise DecisionTextArtifactError(
            "loaded parser manifest differs from authenticated bytes"
        )
    if tuple(dict(record) for record in finalized_unit_records) != tuple(
        dict(record) for record in authenticated_finalized_units
    ):
        raise DecisionTextArtifactError(
            "loaded finalized prediction units differ from authenticated bytes"
        )
    selection_index = _selection_index(authenticated_selections)
    parser_index = _document_index(authenticated_parser_records, label="parser")

    selected_candidates = set(selection_index)
    finalized_index: dict[str, Mapping[str, Any]] = {}
    finalized_envelope_sha256s: dict[str, str] = {}
    for record in authenticated_finalized_units:
        candidate_id = _required_str(record, "candidate_id")
        if candidate_id in finalized_index:
            raise DecisionTextArtifactError(
                "finalized prediction units contain duplicate candidate envelopes"
            )
        finalized_index[candidate_id] = record
        finalized_envelope_sha256s[candidate_id] = _canonical_sha256(record)
    finalized_candidates = set(finalized_index)
    if finalized_candidates != selected_candidates:
        raise DecisionTextArtifactError(
            "decision text, selection, and finalized-unit candidate coverage differ"
        )
    for candidate_id, selection in selection_index.items():
        _validate_finalized_unit_envelope(
            finalized_index[candidate_id],
            expected_case_id=_required_str(selection, "case_id"),
        )

    decision_sha256 = _payload_sha256(decision_payload)
    manifest_sha256 = _payload_sha256(manifest_payload)
    run_card_sha256 = _payload_sha256(run_card_payload)
    _validate_manifest(
        manifest,
        records=records,
        decision_texts_sha256=decision_sha256,
    )
    _validate_run_card(
        run_card,
        manifest=manifest,
        decision_texts_sha256=decision_sha256,
        manifest_sha256=manifest_sha256,
        record_count=len(records),
    )

    manifest_commitments = _input_commitments(
        cast(
            Mapping[str, object],
            _mapping(manifest.get("input_commitments"), "input_commitments"),
        )
    )
    if _normalize_sha256(manifest_commitments["selection_sha256"]) != _normalize_sha256(
        _payload_sha256(selection_payload)
    ):
        raise DecisionTextArtifactError("selection commitment mismatch")
    if _normalize_sha256(
        manifest_commitments["parser_manifest_sha256"]
    ) != _normalize_sha256(_payload_sha256(parser_payload)):
        raise DecisionTextArtifactError("parser manifest commitment mismatch")

    root = markdown_root.expanduser().resolve()
    indexed_records: dict[str, Mapping[str, Any]] = {}
    seen_documents: set[str] = set()
    for record in records:
        candidate_id = _required_str(record, "candidate_id")
        if candidate_id in indexed_records:
            raise DecisionTextArtifactError(
                f"duplicate decision text candidate: {candidate_id}"
            )
        if candidate_id not in selection_index:
            raise DecisionTextArtifactError(
                f"extra decision text candidate: {candidate_id}"
            )
        _validate_verified_record(
            record,
            selection=selection_index[candidate_id],
            parser_index=parser_index,
            markdown_root=root,
            manifest_commitments=manifest_commitments,
            seen_documents=seen_documents,
        )
        indexed_records[candidate_id] = record
    if set(indexed_records) != selected_candidates:
        raise DecisionTextArtifactError(
            "decision text, selection, and finalized-unit candidate coverage differ"
        )

    return VerifiedDecisionTextArtifact(
        records=tuple(records),
        decision_texts_sha256=decision_sha256,
        manifest_sha256=manifest_sha256,
        run_card_sha256=run_card_sha256,
        finalized_prediction_units_sha256=_payload_sha256(finalized_units_payload),
        finalized_unit_envelope_sha256s=finalized_envelope_sha256s,
        input_commitments=dict(manifest_commitments),
    )


def build_decision_text_records(
    *,
    selections: Sequence[Mapping[str, Any]],
    download_manifest: Sequence[Mapping[str, Any]],
    clearance_records: Sequence[Mapping[str, Any]],
    restriction_records: Sequence[Mapping[str, Any]],
    parser_records: Sequence[Mapping[str, Any]],
    markdown_root: Path,
    input_commitments: Mapping[str, str],
) -> tuple[JsonRecord, ...]:
    """Return one strictly reconciled first-disposition text row per candidate."""

    return _build_decision_text_records(
        selections=selections,
        download_manifest=download_manifest,
        clearance_records=clearance_records,
        restriction_records=restriction_records,
        parser_records=parser_records,
        markdown_root=markdown_root,
        input_commitments=input_commitments,
        parser_provenance="live_mistral",
    )


def build_fixture_rehearsal_decision_text_records(
    *,
    selections: Sequence[Mapping[str, Any]],
    download_manifest: Sequence[Mapping[str, Any]],
    clearance_records: Sequence[Mapping[str, Any]],
    restriction_records: Sequence[Mapping[str, Any]],
    parser_records: Sequence[Mapping[str, Any]],
    markdown_root: Path,
    input_commitments: Mapping[str, str],
) -> tuple[JsonRecord, ...]:
    """Build decision text only from explicit fixture-Markdown provenance.

    The returned rows are intentionally ineligible for
    :func:`verify_decision_text_artifact` and therefore cannot enter an official
    labeling, readiness, freeze, evaluation, or dispatch path.
    """

    return _build_decision_text_records(
        selections=selections,
        download_manifest=download_manifest,
        clearance_records=clearance_records,
        restriction_records=restriction_records,
        parser_records=parser_records,
        markdown_root=markdown_root,
        input_commitments=input_commitments,
        parser_provenance="fixture_markdown",
    )


def _build_decision_text_records(
    *,
    selections: Sequence[Mapping[str, Any]],
    download_manifest: Sequence[Mapping[str, Any]],
    clearance_records: Sequence[Mapping[str, Any]],
    restriction_records: Sequence[Mapping[str, Any]],
    parser_records: Sequence[Mapping[str, Any]],
    markdown_root: Path,
    input_commitments: Mapping[str, str],
    parser_provenance: str,
) -> tuple[JsonRecord, ...]:
    if parser_provenance not in {"live_mistral", "fixture_markdown"}:
        raise DecisionTextArtifactError("unsupported parser provenance")

    selection_index = _selection_index(selections)
    manifest_index = _document_index(download_manifest, label="download manifest")
    clearance_index = _document_index(clearance_records, label="clearance")
    restriction_index = _document_index(restriction_records, label="restriction")
    parser_index = _document_index(parser_records, label="parser")
    acquired_keys = set(manifest_index)
    if not acquired_keys:
        raise DecisionTextArtifactError("download manifest is empty")
    if not (
        acquired_keys
        == set(clearance_index)
        == set(restriction_index)
        == set(parser_index)
    ):
        raise DecisionTextArtifactError(
            "document key coverage mismatch across download, clearance, "
            "restriction, and parser artifacts"
        )
    acquired_candidates = {candidate_id for candidate_id, _ in acquired_keys}
    if set(selection_index) != acquired_candidates:
        raise DecisionTextArtifactError(
            "selection and acquired document candidates differ"
        )

    normalized_commitments = _input_commitments(input_commitments)
    root = markdown_root.expanduser().resolve()
    output: list[JsonRecord] = []
    seen_document_ids: set[str] = set()
    for candidate_id in sorted(selection_index):
        selection = selection_index[candidate_id]
        decision_document = _first_disposition_document(selection)
        source_document_id = _required_str(decision_document, "source_document_id")
        if source_document_id in seen_document_ids:
            raise DecisionTextArtifactError(
                f"decision document_id is not globally unique: {source_document_id}"
            )
        seen_document_ids.add(source_document_id)
        key = (candidate_id, source_document_id)
        try:
            manifest = manifest_index[key]
            clearance = clearance_index[key]
            restriction = restriction_index[key]
            parser = parser_index[key]
        except KeyError as exc:
            raise DecisionTextArtifactError(
                "first written disposition is absent from authenticated acquired "
                f"artifacts: {candidate_id}/{source_document_id}"
            ) from exc
        _validate_document_binding(
            key=key,
            selection_document=decision_document,
            manifest=manifest,
            clearance=clearance,
            restriction=restriction,
            parser=parser,
            parser_provenance=parser_provenance,
        )
        text, text_sha256 = _read_parser_markdown(parser, markdown_root=root, key=key)
        entered_date = _decision_date(selection, candidate_id=candidate_id)
        parser_config = _mapping(parser.get("parser_config"), "parser_config")
        extracted_text = _mapping(parser.get("extracted_text"), "extracted_text")
        output.append(
            {
                "schema_version": SCHEMA_VERSION,
                "candidate_id": candidate_id,
                "case_id": _required_str(selection, "case_id"),
                "document_id": source_document_id,
                "entered_date": entered_date,
                "text": text,
                "is_first_written_disposition": True,
                "contains_target_outcome": True,
                "model_visible": False,
                "document_role": _required_str(decision_document, "document_role"),
                "docket_entry_number": _required_int(
                    decision_document, "docket_entry_number"
                ),
                "source_sha256": _required_sha256(manifest, "sha256"),
                "source_byte_count": _required_nonnegative_int(manifest, "byte_count"),
                "text_sha256": text_sha256,
                "markdown_sha256": text_sha256,
                "extraction_method": _required_str(extracted_text, "extraction_method"),
                "parser_revision": (
                    _required_str(parser_config, "parser_revision")
                    if parser_provenance == "live_mistral"
                    else "fixture_markdown"
                ),
                **(
                    {"parser_provenance": "fixture_markdown"}
                    if parser_provenance == "fixture_markdown"
                    else {}
                ),
                "clearance": {
                    "status": "cleared",
                    "restriction_status": _required_str(
                        clearance, "restriction_status"
                    ),
                    "reviewer_id": _required_str(clearance, "reviewer_id"),
                    "controlled_store_provenance": _required_str(
                        clearance, "controlled_store_provenance"
                    ),
                    "reviewed_at": _required_str(clearance, "reviewed_at"),
                },
                "input_commitments": dict(normalized_commitments),
            }
        )
    if len(output) != len(selection_index):
        raise DecisionTextArtifactError(
            "decision text count does not reconcile selected candidate count"
        )
    return tuple(output)


def _validate_manifest(
    manifest: Mapping[str, Any],
    *,
    records: Sequence[Mapping[str, Any]],
    decision_texts_sha256: str,
) -> None:
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise DecisionTextArtifactError(
            "unsupported decision text manifest schema_version"
        )
    if manifest.get("eligibility_anchor") != CYCLE_1_ELIGIBILITY_ANCHOR.isoformat():
        raise DecisionTextArtifactError(
            "decision text manifest eligibility anchor drift"
        )
    if manifest.get("record_count") != len(records):
        raise DecisionTextArtifactError("decision text manifest record count mismatch")
    if manifest.get("decision_texts_sha256") != decision_texts_sha256:
        raise DecisionTextArtifactError("decision text artifact hash mismatch")
    candidate_ids = [_required_str(record, "candidate_id") for record in records]
    if manifest.get("candidate_ids_sha256") != _canonical_sha256(candidate_ids):
        raise DecisionTextArtifactError("decision text candidate commitment mismatch")
    if manifest.get("outcome_material_model_visible") is not False:
        raise DecisionTextArtifactError(
            "decision text manifest marks outcome material model-visible"
        )
    if (
        manifest.get("paid_activity_requested") is not False
        or manifest.get("paid_activity_executed") is not False
    ):
        raise DecisionTextArtifactError(
            "decision text manifest has invalid paid-activity provenance"
        )


def _validate_run_card(
    run_card: Mapping[str, Any],
    *,
    manifest: Mapping[str, Any],
    decision_texts_sha256: str,
    manifest_sha256: str,
    record_count: int,
) -> None:
    if run_card.get("schema_version") != "legalforecast.acquisition_run_card.v1":
        raise DecisionTextArtifactError("unsupported decision text run-card schema")
    if (
        run_card.get("stage") != "build-decision-texts"
        or run_card.get("status") != "completed"
        or run_card.get("execute") is not True
        or run_card.get("dry_run") is not False
    ):
        raise DecisionTextArtifactError(
            "decision text run card is not a completed executed build"
        )
    if run_card.get("record_count") != record_count:
        raise DecisionTextArtifactError("decision text run-card count mismatch")
    if run_card.get("eligibility_anchor") != CYCLE_1_ELIGIBILITY_ANCHOR.isoformat():
        raise DecisionTextArtifactError(
            "decision text run-card eligibility anchor drift"
        )
    if run_card.get("decision_texts_sha256") != decision_texts_sha256:
        raise DecisionTextArtifactError("decision text run-card artifact hash mismatch")
    if run_card.get("decision_texts_manifest_sha256") != manifest_sha256:
        raise DecisionTextArtifactError("decision text run-card manifest hash mismatch")
    if (
        run_card.get("paid_activity_requested") is not False
        or run_card.get("paid_activity_executed") is not False
    ):
        raise DecisionTextArtifactError(
            "decision text run card has invalid paid-activity provenance"
        )
    run_commitments = _input_commitments(
        cast(
            Mapping[str, object],
            _mapping(run_card.get("input_commitments"), "input_commitments"),
        )
    )
    manifest_commitments = _input_commitments(
        cast(
            Mapping[str, object],
            _mapping(manifest.get("input_commitments"), "input_commitments"),
        )
    )
    if run_commitments != manifest_commitments:
        raise DecisionTextArtifactError(
            "decision text run-card input commitments mismatch"
        )


def _validate_verified_record(
    record: Mapping[str, Any],
    *,
    selection: Mapping[str, Any],
    parser_index: Mapping[DocumentKey, Mapping[str, Any]],
    markdown_root: Path,
    manifest_commitments: Mapping[str, str],
    seen_documents: set[str],
) -> None:
    candidate_id = _required_str(record, "candidate_id")
    if record.get("schema_version") != SCHEMA_VERSION:
        raise DecisionTextArtifactError(
            f"unsupported decision text schema: {candidate_id}"
        )
    if _required_str(record, "case_id") != _required_str(selection, "case_id"):
        raise DecisionTextArtifactError(f"decision text case mismatch: {candidate_id}")
    selected_document = _first_disposition_document(selection)
    document_id = _required_str(record, "document_id")
    if document_id in seen_documents:
        raise DecisionTextArtifactError(
            f"decision document_id is not globally unique: {document_id}"
        )
    seen_documents.add(document_id)
    if document_id != _required_str(selected_document, "source_document_id"):
        raise DecisionTextArtifactError(
            f"decision text document mismatch: {candidate_id}"
        )
    if _required_str(record, "entered_date") != _decision_date(
        selection, candidate_id=candidate_id
    ):
        raise DecisionTextArtifactError(f"decision text date mismatch: {candidate_id}")
    if record.get("is_first_written_disposition") is not True:
        raise DecisionTextArtifactError(
            f"decision text is not the first written disposition: {candidate_id}"
        )
    if record.get("contains_target_outcome") is not True:
        raise DecisionTextArtifactError(
            f"decision text is not outcome-bearing: {candidate_id}"
        )
    if record.get("model_visible") is not False:
        raise DecisionTextArtifactError(
            f"decision text is marked model-visible: {candidate_id}"
        )
    if _required_str(record, "document_role") != _required_str(
        selected_document, "document_role"
    ):
        raise DecisionTextArtifactError(f"decision text role mismatch: {candidate_id}")
    if _required_int(record, "docket_entry_number") != _required_int(
        selected_document, "docket_entry_number"
    ):
        raise DecisionTextArtifactError(
            f"decision text docket-entry mismatch: {candidate_id}"
        )
    text = _required_str(record, "text")
    text_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if _required_sha256(record, "text_sha256") != text_sha256:
        raise DecisionTextArtifactError(f"decision text hash mismatch: {candidate_id}")
    if _required_sha256(record, "markdown_sha256") != text_sha256:
        raise DecisionTextArtifactError(
            f"decision Markdown commitment mismatch: {candidate_id}"
        )
    record_commitments = _input_commitments(
        cast(
            Mapping[str, object],
            _mapping(record.get("input_commitments"), "input_commitments"),
        )
    )
    if record_commitments != manifest_commitments:
        raise DecisionTextArtifactError(
            f"decision text input commitments mismatch: {candidate_id}"
        )
    clearance = _mapping(record.get("clearance"), "clearance")
    if clearance.get("status") != "cleared":
        raise DecisionTextArtifactError(
            f"decision text lacks authenticated clearance: {candidate_id}"
        )
    if _required_str(clearance, "restriction_status").lower() not in _PUBLIC_STATUSES:
        raise DecisionTextArtifactError(
            f"decision text is sealed/private/restricted: {candidate_id}"
        )
    if not _required_str(clearance, "controlled_store_provenance").startswith(
        "private-store://"
    ):
        raise DecisionTextArtifactError(
            f"decision text clearance lacks controlled-store provenance: {candidate_id}"
        )
    _required_str(clearance, "reviewer_id")
    _required_str(clearance, "reviewed_at")

    key = (candidate_id, document_id)
    try:
        parser = parser_index[key]
    except KeyError as exc:
        raise DecisionTextArtifactError(
            f"decision text parser lineage missing: {candidate_id}/{document_id}"
        ) from exc
    if parser.get("status") != "succeeded":
        raise DecisionTextArtifactError(f"parser record did not succeed: {key}")
    if _required_sha256(record, "source_sha256") != _required_sha256(
        parser, "source_sha256"
    ):
        raise DecisionTextArtifactError(f"decision source hash mismatch: {key}")
    if _required_nonnegative_int(
        record, "source_byte_count"
    ) != _required_nonnegative_int(parser, "source_byte_count"):
        raise DecisionTextArtifactError(f"decision source byte-count mismatch: {key}")
    quality_flags = parser.get("quality_flags")
    if not isinstance(quality_flags, Sequence) or isinstance(
        quality_flags, (str, bytes)
    ):
        raise DecisionTextArtifactError(f"parser quality_flags must be a list: {key}")
    if quality_flags:
        raise DecisionTextArtifactError(
            f"decision parser record has quality flags: {key}"
        )
    parser_config = _mapping(parser.get("parser_config"), "parser_config")
    if (
        parser_config.get("engine") != "mistral"
        or parser_config.get("parser_revision") != EXPECTED_PARSER_REVISION
        or parser_config.get("expected_parser_revision") != EXPECTED_PARSER_REVISION
        or parser_config.get("fixture_markdown") is True
    ):
        raise DecisionTextArtifactError(
            f"parser revision is not the pinned live Mistral revision: {key}"
        )
    extracted = _mapping(parser.get("extracted_text"), "extracted_text")
    if extracted.get("extraction_method") != "mistral_parser_markdown":
        raise DecisionTextArtifactError(f"unexpected extraction method: {key}")
    if _required_str(extracted, "source_document_id") != document_id:
        raise DecisionTextArtifactError(f"extracted text identity mismatch: {key}")
    if _required_str(record, "extraction_method") != _required_str(
        extracted, "extraction_method"
    ):
        raise DecisionTextArtifactError(f"extraction method mismatch: {key}")
    if _required_str(record, "parser_revision") != EXPECTED_PARSER_REVISION:
        raise DecisionTextArtifactError(f"decision text parser revision drift: {key}")
    parser_text, parser_text_sha256 = _read_parser_markdown(
        parser, markdown_root=markdown_root, key=key
    )
    if parser_text_sha256 != text_sha256 or parser_text != text:
        raise DecisionTextArtifactError(
            f"decision text differs from pinned parser output: {key}"
        )


def _validate_finalized_unit_envelope(
    record: Mapping[str, Any], *, expected_case_id: str
) -> None:
    candidate_id = _required_str(record, "candidate_id")
    if record.get("schema_version") != "legalforecast.finalized_prediction_units.v1":
        raise DecisionTextArtifactError(
            f"unsupported finalized prediction-units schema: {candidate_id}"
        )
    if _required_str(record, "case_id") != expected_case_id:
        raise DecisionTextArtifactError(
            f"finalized prediction-units case mismatch: {candidate_id}"
        )
    _required_sha256(record, "raw_prediction_units_sha256")
    _required_sha256(record, "unitization_review_queue_sha256")
    units = _mapping_sequence(record.get("prediction_units"), "prediction_units")
    status = record.get("status")
    if status == "candidate_excluded":
        if units:
            raise DecisionTextArtifactError(
                f"invalid finalized candidate-exclusion envelope: {candidate_id}"
            )
        exclusion = _mapping(record.get("exclusion"), "exclusion")
        _required_str(exclusion, "reason")
        _required_str(exclusion, "adjudication_id")
        _required_sha256(exclusion, "adjudication_sha256")
        return
    if status != "finalized" or not units or record.get("exclusion") is not None:
        raise DecisionTextArtifactError(
            f"invalid finalized prediction-units envelope: {candidate_id}"
        )
    seen_unit_ids: set[str] = set()
    for unit in units:
        unit_id = _required_str(unit, "unit_id")
        if unit_id in seen_unit_ids:
            raise DecisionTextArtifactError(
                f"duplicate finalized unit_id: {candidate_id}/{unit_id}"
            )
        seen_unit_ids.add(unit_id)
        source_hashes = _required_nonempty_strings(unit, "source_unit_sha256s")
        if any(not _valid_sha256(value) for value in source_hashes):
            raise DecisionTextArtifactError(
                f"invalid finalized source-unit hash: {candidate_id}/{unit_id}"
            )
        adjudication_id = _required_str(unit, "adjudication_id")
        disposition = _required_str(unit, "disposition")
        if adjudication_id.startswith("automatic:"):
            base_unit = {
                key: value
                for key, value in unit.items()
                if key
                not in {
                    "source_unit_sha256s",
                    "adjudication_id",
                    "adjudication_sha256",
                    "disposition",
                }
            }
            expected_source_sha256 = _unitization_sha256(base_unit)
            if (
                len(source_hashes) != 1
                or source_hashes[0] != expected_source_sha256
                or adjudication_id != f"automatic:{expected_source_sha256}"
                or unit.get("adjudication_sha256") is not None
                or disposition != "ACCEPT"
            ):
                raise DecisionTextArtifactError(
                    "invalid automatic finalized-unit provenance: "
                    f"{candidate_id}/{unit_id}"
                )
        else:
            _required_sha256(unit, "adjudication_sha256")


def _unitization_sha256(record: Mapping[str, Any]) -> str:
    payload = json.dumps(
        dict(record), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _read_regular_file(path: Path, label: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise DecisionTextArtifactError(f"{label} is not a regular file: {path}")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise DecisionTextArtifactError(f"cannot read {label}: {path}") from exc


def _jsonl_records(payload: bytes, *, label: str) -> tuple[Mapping[str, Any], ...]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DecisionTextArtifactError(f"{label} is not UTF-8") from exc
    if not text or not text.endswith("\n"):
        raise DecisionTextArtifactError(f"{label} must be newline-terminated JSONL")
    output: list[Mapping[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            raise DecisionTextArtifactError(
                f"{label} contains a blank row at line {line_number}"
            )
        loaded = _parse_json(line, label=f"{label}:{line_number}")
        output.append(_mapping(loaded, label))
    if not output:
        raise DecisionTextArtifactError(f"{label} is empty")
    return tuple(output)


def _json_object(payload: bytes, *, label: str) -> Mapping[str, Any]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DecisionTextArtifactError(f"{label} is not UTF-8") from exc
    return _mapping(_parse_json(text, label=label), label)


def _parse_json(text: str, *, label: str) -> object:
    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        output: dict[str, object] = {}
        for key, value in pairs:
            if key in output:
                raise DecisionTextArtifactError(
                    f"{label} contains duplicate JSON key {key!r}"
                )
            output[key] = value
        return output

    try:
        return json.loads(text, object_pairs_hook=reject_duplicates)
    except json.JSONDecodeError as exc:
        raise DecisionTextArtifactError(f"{label} is invalid JSON") from exc


def _payload_sha256(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return _payload_sha256(payload)


def _normalize_sha256(value: str) -> str:
    if not _valid_sha256(value):
        raise DecisionTextArtifactError("invalid SHA-256 commitment")
    return value.removeprefix("sha256:")


def _selection_index(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    if not records:
        raise DecisionTextArtifactError("selection is empty")
    output: dict[str, Mapping[str, Any]] = {}
    for record in records:
        candidate_id = _required_str(record, "candidate_id")
        if candidate_id in output:
            raise DecisionTextArtifactError(
                f"duplicate selected candidate: {candidate_id}"
            )
        if record.get("selected") is not True:
            raise DecisionTextArtifactError(
                f"selection row is not selected: {candidate_id}"
            )
        output[candidate_id] = record
    return output


def _document_index(
    records: Sequence[Mapping[str, Any]], *, label: str
) -> dict[DocumentKey, Mapping[str, Any]]:
    output: dict[DocumentKey, Mapping[str, Any]] = {}
    for record in records:
        key = (
            _required_str(record, "candidate_id"),
            _required_str(record, "source_document_id"),
        )
        if key in output:
            raise DecisionTextArtifactError(f"duplicate {label} document: {key}")
        output[key] = record
    return output


def _first_disposition_document(
    selection: Mapping[str, Any],
) -> Mapping[str, Any]:
    candidate_id = _required_str(selection, "candidate_id")
    decision_entries = _required_int_sequence(selection, "decision_entry_numbers")
    if not decision_entries:
        raise DecisionTextArtifactError(
            f"decision_entry_numbers is empty: {candidate_id}"
        )
    first_entry = min(decision_entries)
    documents = _mapping_sequence(selection.get("documents"), "documents")
    qualifying: list[Mapping[str, Any]] = []
    for document in documents:
        if _required_str(document, "candidate_id") != candidate_id:
            raise DecisionTextArtifactError(
                f"selection document candidate lineage mismatch: {candidate_id}"
            )
        role = _required_str(document, "document_role")
        if role not in _OUTCOME_ROLES:
            continue
        if _required_int(document, "docket_entry_number") != first_entry:
            continue
        if document.get("contains_target_outcome") is not True:
            raise DecisionTextArtifactError(
                "first disposition document must be explicitly outcome-bearing: "
                f"{candidate_id}/{_required_str(document, 'source_document_id')}"
            )
        if document.get("model_visible") is not False:
            raise DecisionTextArtifactError(
                "first disposition document must not be model-visible: "
                f"{candidate_id}/{_required_str(document, 'source_document_id')}"
            )
        _require_public_document(
            document,
            key=(candidate_id, _required_str(document, "source_document_id")),
            require_explicit_status=False,
        )
        qualifying.append(document)
    if not qualifying:
        raise DecisionTextArtifactError(
            f"first written disposition document missing: {candidate_id}"
        )
    if len(qualifying) != 1:
        raise DecisionTextArtifactError(
            f"ambiguous first written disposition: {candidate_id} entry {first_entry}"
        )
    return qualifying[0]


def _validate_document_binding(
    *,
    key: DocumentKey,
    selection_document: Mapping[str, Any],
    manifest: Mapping[str, Any],
    clearance: Mapping[str, Any],
    restriction: Mapping[str, Any],
    parser: Mapping[str, Any],
    parser_provenance: str,
) -> None:
    if clearance.get("schema_version") != "legalforecast.disclosure_clearance.v1":
        raise DecisionTextArtifactError(f"unsupported clearance schema: {key}")
    if clearance.get("status") != "cleared":
        raise DecisionTextArtifactError(f"decision document lacks clearance: {key}")
    _require_public_document(selection_document, key=key, require_explicit_status=False)
    _require_public_document(clearance, key=key)
    _require_public_document(restriction, key=key)
    for field in ("reviewer_id", "controlled_store_provenance", "reviewed_at"):
        _required_str(clearance, field)
    if not _required_str(clearance, "controlled_store_provenance").startswith(
        "private-store://"
    ):
        raise DecisionTextArtifactError(
            f"clearance lacks controlled-store provenance: {key}"
        )
    _required_nonempty_strings(clearance, "restriction_evidence")
    _required_nonempty_strings(restriction, "restriction_evidence")
    manifest_sha = _required_sha256(manifest, "sha256")
    clearance_sha = _required_sha256(clearance, "sha256")
    parser_sha = _required_sha256(parser, "source_sha256")
    if manifest_sha != clearance_sha or manifest_sha != parser_sha:
        raise DecisionTextArtifactError(f"source hash mismatch: {key}")
    manifest_bytes = _required_nonnegative_int(manifest, "byte_count")
    if manifest_bytes != _required_nonnegative_int(
        clearance, "byte_count"
    ) or manifest_bytes != _required_nonnegative_int(parser, "source_byte_count"):
        raise DecisionTextArtifactError(f"source byte-count mismatch: {key}")
    if manifest.get("free_or_purchased") not in {"free", "purchased"}:
        raise DecisionTextArtifactError(f"invalid acquisition phase: {key}")
    if clearance.get("free_or_purchased") != manifest.get("free_or_purchased"):
        raise DecisionTextArtifactError(f"acquisition phase mismatch: {key}")
    if parser.get("status") != "succeeded":
        raise DecisionTextArtifactError(f"parser record did not succeed: {key}")
    quality_flags = parser.get("quality_flags")
    if not isinstance(quality_flags, Sequence) or isinstance(
        quality_flags, (str, bytes)
    ):
        raise DecisionTextArtifactError(f"parser quality_flags must be a list: {key}")
    if quality_flags:
        raise DecisionTextArtifactError(
            f"decision parser record has quality flags: {key}"
        )
    parser_config = _mapping(parser.get("parser_config"), "parser_config")
    if parser_provenance == "live_mistral":
        if (
            parser_config.get("engine") != "mistral"
            or parser_config.get("parser_revision") != EXPECTED_PARSER_REVISION
            or parser_config.get("expected_parser_revision") != EXPECTED_PARSER_REVISION
            or parser_config.get("fixture_markdown") is True
        ):
            raise DecisionTextArtifactError(
                f"parser revision is not the pinned Mistral revision: {key}"
            )
        expected_extraction_method = "mistral_parser_markdown"
    else:
        if parser_config.get("engine") != "fixture_markdown" or set(parser_config) != {
            "engine",
            "fixture_markdown_dir",
        }:
            raise DecisionTextArtifactError(
                f"parser record is not explicit fixture Markdown: {key}"
            )
        expected_extraction_method = "fixture_markdown"
    extracted_text = _mapping(parser.get("extracted_text"), "extracted_text")
    if extracted_text.get("source_document_id") != key[1]:
        raise DecisionTextArtifactError(f"extracted text identity mismatch: {key}")
    if extracted_text.get("extraction_method") != expected_extraction_method:
        raise DecisionTextArtifactError(f"unexpected extraction method: {key}")
    _required_sha256(extracted_text, "text_sha256")


def _read_parser_markdown(
    parser: Mapping[str, Any], *, markdown_root: Path, key: DocumentKey
) -> tuple[str, str]:
    configured_path = Path(_required_str(parser, "markdown_path"))
    source_path = (
        configured_path
        if configured_path.is_absolute()
        else markdown_root / configured_path
    )
    if ".." in source_path.parts:
        raise DecisionTextArtifactError(
            f"parser markdown path escapes markdown root: {key}"
        )
    try:
        source_path.relative_to(markdown_root)
    except ValueError as exc:
        raise DecisionTextArtifactError(
            f"parser markdown path escapes markdown root: {key}"
        ) from exc
    path_component = source_path
    while path_component != markdown_root:
        if path_component.is_symlink():
            raise DecisionTextArtifactError(
                f"parser markdown path contains a symlink: {key}"
            )
        path_component = path_component.parent
    resolved = source_path.resolve()
    try:
        resolved.relative_to(markdown_root)
    except ValueError as exc:
        raise DecisionTextArtifactError(
            f"parser markdown path escapes markdown root: {key}"
        ) from exc
    if not resolved.is_file():
        raise DecisionTextArtifactError(f"markdown file missing: {resolved}")
    try:
        text = resolved.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise DecisionTextArtifactError(
            f"cannot read decision markdown: {key}"
        ) from exc
    if not text.strip():
        raise DecisionTextArtifactError(f"decision markdown is empty: {key}")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    extracted = _mapping(parser.get("extracted_text"), "extracted_text")
    if digest != _required_sha256(extracted, "text_sha256"):
        raise DecisionTextArtifactError(f"extracted text hash mismatch: {key}")
    return text, digest


def _decision_date(selection: Mapping[str, Any], *, candidate_id: str) -> str:
    value = _required_str(selection, "decision_date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise DecisionTextArtifactError(
            f"decision_date must be YYYY-MM-DD: {candidate_id}"
        ) from exc
    if parsed < CYCLE_1_ELIGIBILITY_ANCHOR:
        raise DecisionTextArtifactError(
            f"decision is before eligibility anchor: {candidate_id}/{value}"
        )
    return parsed.isoformat()


def _require_public_document(
    record: Mapping[str, Any],
    *,
    key: DocumentKey,
    require_explicit_status: bool = True,
) -> None:
    statuses: list[str] = []
    for field in ("restriction_status", "redaction_or_seal_status", "seal_status"):
        value = record.get(field)
        if value is not None:
            if not isinstance(value, str) or not value.strip():
                raise DecisionTextArtifactError(f"invalid public status: {key}")
            statuses.append(value.strip().lower())
    for field in ("is_sealed", "is_private"):
        value = record.get(field)
        if value is not None and type(value) is not bool:
            raise DecisionTextArtifactError(
                f"decision document has malformed {field} flag: {key}"
            )
        if value is True:
            raise DecisionTextArtifactError(
                f"decision document is sealed/private/restricted: {key}"
            )
    if (require_explicit_status and not statuses) or any(
        status not in _PUBLIC_STATUSES for status in statuses
    ):
        raise DecisionTextArtifactError(
            f"decision document is sealed/private/restricted: {key}"
        )


def _input_commitments(commitments: Mapping[str, object]) -> dict[str, str]:
    expected = {
        "selection_sha256",
        "download_manifest_sha256",
        "disclosure_clearance_sha256",
        "clearance_run_card_sha256",
        "restriction_evidence_sha256",
        "parser_manifest_sha256",
        "parser_run_card_sha256",
        "selection_run_card_sha256",
    }
    if set(commitments) != expected:
        raise DecisionTextArtifactError(
            "decision text input commitments are incomplete"
        )
    output: dict[str, str] = {}
    for name in sorted(expected):
        value = commitments[name]
        if not isinstance(value, str) or not _valid_sha256(value):
            raise DecisionTextArtifactError(f"invalid input commitment: {name}")
        output[name] = value
    return output


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise DecisionTextArtifactError(f"{label} must be an object")
    return cast(Mapping[str, Any], value)


def _mapping_sequence(value: object, label: str) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise DecisionTextArtifactError(f"{label} must be a list")
    output: list[Mapping[str, Any]] = []
    for item in cast(Sequence[object], value):
        output.append(_mapping(item, label))
    return tuple(output)


def _required_str(record: Mapping[str, Any], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise DecisionTextArtifactError(f"{field} must be a non-empty string")
    return value


def _required_int(record: Mapping[str, Any], field: str) -> int:
    value = record.get(field)
    if type(value) is not int:
        raise DecisionTextArtifactError(f"{field} must be an integer")
    return value


def _required_nonnegative_int(record: Mapping[str, Any], field: str) -> int:
    value = _required_int(record, field)
    if value < 0:
        raise DecisionTextArtifactError(f"{field} must be nonnegative")
    return value


def _required_int_sequence(record: Mapping[str, Any], field: str) -> tuple[int, ...]:
    value = record.get(field)
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise DecisionTextArtifactError(f"{field} must be a list")
    output: list[int] = []
    for item in cast(Sequence[object], value):
        if type(item) is not int:
            raise DecisionTextArtifactError(f"{field} must contain integers")
        output.append(item)
    if len(output) != len(set(output)):
        raise DecisionTextArtifactError(f"{field} contains duplicates")
    return tuple(output)


def _required_nonempty_strings(
    record: Mapping[str, Any], field: str
) -> tuple[str, ...]:
    value = record.get(field)
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise DecisionTextArtifactError(f"{field} must be a list")
    output = tuple(cast(Sequence[object], value))
    if not output or not all(isinstance(item, str) and item.strip() for item in output):
        raise DecisionTextArtifactError(f"{field} must contain non-empty strings")
    return cast(tuple[str, ...], output)


def _required_sha256(record: Mapping[str, Any], field: str) -> str:
    value = _required_str(record, field)
    if not _valid_sha256(value):
        raise DecisionTextArtifactError(f"{field} must be a SHA-256 digest")
    return value.removeprefix("sha256:")


def _valid_sha256(value: object) -> bool:
    if not isinstance(value, str):
        return False
    digest = value.removeprefix("sha256:")
    return len(digest) == 64 and all(
        character in "0123456789abcdef" for character in digest
    )
