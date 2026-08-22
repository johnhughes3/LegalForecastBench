# pyright: reportUnusedFunction=false
"""Shared contracts and byte-validation helpers for manifest unitization."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from legalforecast.ingestion.provenance import DocumentRole
from legalforecast.unitization.schemas import prediction_unit_from_record

JsonRecord = dict[str, Any]

_UNITS_SPEND_APPROVAL = (
    "units: approved — ceiling USD 5.00 extends to the sixth fresh case"
)
_R2_UNITS_SPEND_APPROVAL = (
    "units: approved — ceiling USD 5.00 extends to the fifth fresh case"
)
_CYCLE1_FRESH_CANDIDATE_IDS = frozenset(
    {"69437817", "69617129", "70142291", "71203930", "71929529", "72288139"}
)
_R2_FRESH_CANDIDATE_IDS = frozenset(
    {"69437817", "69617129", "70142291", "71203930", "71929529"}
)
_CYCLE1_REPROCESSED_CANDIDATE_IDS = frozenset({"72288139"})
_LABELING_MODEL_KEY = "anthropic:claude-sonnet-4-6"
_LABELING_MODEL_REGISTRY_SHA256 = (
    "e24b0a235936de4b0870fd6b688fabbd4901ccd3a8378a826c4a287a26c1aba0"
)
_PROVIDER_CAPS_SHA256 = (
    "71a0919b7e23a1b0dab7bca7233c9036f2e678f35760f78f98b4f2c37330eb74"
)
_R2_AUTHORITY_MODE = "stage51-r2-proposal-v1"
_FINALIZED_V1_AUTHORITY_MODE = "finalized-v1"
_R2_PACKET_CANDIDATE_IDS = (
    "73183894",
    "70754103",
    "71212565",
    "71194192",
    "72288139",
)
_R2_FILES = {
    "selection": "selection-proposal.jsonl",
    "overlay": "prediction-units-overlay.jsonl",
    "packet": "stage51-terminal-units-owner-packet.json",
    "validation": "validation-report.json",
    "semantic_diff": "semantic-diff.json",
    "inventory": "byte-inventory.json",
    "checksums": "sha256sums.txt",
    "integration_proposal": "integration-proposal.json",
}
_CLAIM_BEARING_ROLES = frozenset(
    {
        DocumentRole.COMPLAINT,
        DocumentRole.AMENDED_COMPLAINT,
        DocumentRole.COUNTERCLAIM,
        DocumentRole.CROSSCLAIM,
        DocumentRole.THIRD_PARTY_COMPLAINT,
        DocumentRole.INTERPLEADER_COMPLAINT,
        DocumentRole.OTHER_CLAIM_BEARING,
    }
)
_TARGET_MOTION_ROLES = frozenset({DocumentRole.MTD_NOTICE, DocumentRole.MTD_MEMORANDUM})


class ManifestUnitizerInputError(ValueError):
    """Raised when a document-store unitizer input cannot be authenticated."""


class ManifestUnitizerCommandError(ValueError):
    """Raised when manifest-mode execution inputs or outputs are invalid."""


@dataclass(frozen=True, slots=True)
class PreparedManifestUnitizerInputs:
    """Exact prompt inputs assembled from a selection and parser stores."""

    selection_records: tuple[JsonRecord, ...]
    parser_records: tuple[JsonRecord, ...]
    markdown_root: Path
    markdown_bytes: Mapping[str, bytes]
    selection_sha256: str
    verdict_source_sha256: tuple[str, ...]
    document_commitments: Mapping[str, Mapping[str, str]]


@dataclass(frozen=True, slots=True)
class AuthenticatedFinalizedOverlay:
    """Provider-free finalized units retained from the authenticated overlay."""

    retained_records: tuple[JsonRecord, ...]
    fresh_selection_records: tuple[JsonRecord, ...]
    overlay_sha256: str
    integration_manifest_sha256: str
    fresh_candidate_ids: tuple[str, ...]
    reprocessed_records: tuple[JsonRecord, ...] = ()
    reprocessed_candidate_ids: tuple[str, ...] = ()
    authority_mode: str = _FINALIZED_V1_AUTHORITY_MODE
    authority_input_commitments: tuple[JsonRecord, ...] = ()
    expected_fresh_records: tuple[JsonRecord, ...] = ()
    expected_fresh_audits: tuple[JsonRecord, ...] = ()


def _records_by_candidate(
    records: Sequence[JsonRecord], *, label: str
) -> dict[str, JsonRecord]:
    by_candidate: dict[str, JsonRecord] = {}
    for record in records:
        candidate_id = _command_required_string(record, "candidate_id")
        if candidate_id in by_candidate:
            raise ManifestUnitizerCommandError(
                f"{label} repeats candidate {candidate_id}"
            )
        by_candidate[candidate_id] = dict(record)
    return by_candidate


def _packet_replacement_units(payload: bytes) -> dict[str, list[JsonRecord]]:
    try:
        raw = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ManifestUnitizerCommandError(
            "approved replacement packet is invalid JSON"
        ) from exc
    if not isinstance(raw, Mapping):
        raise ManifestUnitizerCommandError(
            "approved replacement packet lacks candidates"
        )
    raw_mapping = cast(Mapping[str, object], raw)
    raw_candidates = raw_mapping.get("candidates")
    if not isinstance(raw_candidates, list):
        raise ManifestUnitizerCommandError(
            "approved replacement packet lacks candidates"
        )
    result: dict[str, list[JsonRecord]] = {}
    for raw_candidate in cast(list[object], raw_candidates):
        if not isinstance(raw_candidate, Mapping):
            raise ManifestUnitizerCommandError(
                "approved replacement packet has an invalid candidate"
            )
        candidate = cast(Mapping[str, Any], raw_candidate)
        candidate_id = _command_required_string(candidate, "candidate_id")
        raw_units = candidate.get("prediction_units")
        if candidate_id in result or not isinstance(raw_units, list) or not raw_units:
            raise ManifestUnitizerCommandError(
                "approved replacement packet has invalid prediction units"
            )
        units: list[JsonRecord] = []
        for raw_unit in cast(list[object], raw_units):
            if not isinstance(raw_unit, Mapping):
                raise ManifestUnitizerCommandError(
                    "approved replacement packet has an invalid prediction unit"
                )
            unit = dict(cast(Mapping[str, Any], raw_unit))
            prediction_unit_from_record(unit)
            units.append(unit)
        result[candidate_id] = units
    return result


def _validate_retained_record(
    record: Mapping[str, Any],
    *,
    selection: Mapping[str, Any],
    prepared: PreparedManifestUnitizerInputs,
) -> None:
    candidate_id = _command_required_string(record, "candidate_id")
    selection_documents = selection.get("documents")
    if not isinstance(selection_documents, list):
        raise ManifestUnitizerCommandError(
            f"{candidate_id}: selection documents must be a list"
        )
    parser_by_document = {
        str(parser["source_document_id"]): parser
        for parser in prepared.parser_records
        if parser.get("candidate_id") == candidate_id
    }
    documents: dict[str, tuple[DocumentRole, int | None, str]] = {}
    for raw_document in cast(list[object], selection_documents):
        if not isinstance(raw_document, Mapping):
            raise ManifestUnitizerCommandError(
                f"{candidate_id}: malformed selection document"
            )
        document = cast(Mapping[str, Any], raw_document)
        if document.get("model_visible") is not True:
            continue
        # Older selected rows omit this redundant flag. Their closed role and
        # certified byte-role verdict are the authority; an explicit non-true
        # value is still refused.
        if (
            "is_predecision_material" in document
            and document.get("is_predecision_material") is not True
        ):
            raise ManifestUnitizerCommandError(
                f"{candidate_id}: model-visible document is not explicitly predecision"
            )
        if document.get("contains_target_outcome") is not False:
            raise ManifestUnitizerCommandError(
                f"{candidate_id}: model-visible document is not explicitly outcome-free"
            )
        document_id = _command_required_string(document, "source_document_id")
        try:
            role = DocumentRole(_command_required_string(document, "document_role"))
            parser = parser_by_document[document_id]
            relative = _command_required_string(parser, "markdown_path")
            markdown = prepared.markdown_bytes[relative].decode("utf-8")
        except (KeyError, UnicodeDecodeError, ValueError) as exc:
            raise ManifestUnitizerCommandError(
                f"{candidate_id}/{document_id}: citation source cannot be authenticated"
            ) from exc
        entry = document.get("docket_entry_number")
        if entry is not None and (type(entry) is not int or entry <= 0):
            raise ManifestUnitizerCommandError(
                f"{candidate_id}/{document_id}: invalid docket entry"
            )
        documents[document_id] = (role, entry, markdown)

    units = cast(list[object], record["prediction_units"])
    for raw_unit in units:
        try:
            unit = prediction_unit_from_record(raw_unit)
        except (TypeError, ValueError) as exc:
            raise ManifestUnitizerCommandError(
                f"{candidate_id}: finalized prediction unit is invalid: {exc}"
            ) from exc
        if (
            not isinstance(raw_unit, Mapping)
            or dict(cast(Mapping[str, Any], raw_unit)) != unit.to_record()
        ):
            raise ManifestUnitizerCommandError(
                f"{candidate_id}/{unit.unit_id}: finalized unit is not canonical"
            )
        if not unit.should_score:
            raise ManifestUnitizerCommandError(
                f"{candidate_id}/{unit.unit_id}: retained unit is not scorable"
            )
        cited_roles: set[DocumentRole] = set()
        for citation in unit.source_citations:
            source = documents.get(citation.document_id)
            if source is None:
                raise ManifestUnitizerCommandError(
                    f"{candidate_id}/{unit.unit_id}: citation document is not supplied"
                )
            role, entry, markdown = source
            excerpt = citation.excerpt
            if excerpt is None or not excerpt.strip() or len(excerpt.splitlines()) > 12:
                raise ManifestUnitizerCommandError(
                    f"{candidate_id}/{unit.unit_id}: citation excerpt is invalid"
                )
            span_pages = _citation_span_pages(markdown, excerpt)
            if not span_pages or citation.page not in span_pages:
                raise ManifestUnitizerCommandError(
                    f"{candidate_id}/{unit.unit_id}: citation span or page changed"
                )
            if citation.docket_entry_number != entry or citation.paragraph is not None:
                raise ManifestUnitizerCommandError(
                    f"{candidate_id}/{unit.unit_id}: citation attribution changed"
                )
            cited_roles.add(role)
        if not cited_roles.intersection(_CLAIM_BEARING_ROLES):
            raise ManifestUnitizerCommandError(
                f"{candidate_id}/{unit.unit_id}: no claim-bearing citation"
            )
        if not cited_roles.intersection(_TARGET_MOTION_ROLES):
            raise ManifestUnitizerCommandError(
                f"{candidate_id}/{unit.unit_id}: no target-motion citation"
            )


def _citation_span_pages(markdown: str, excerpt: str) -> set[int | None]:
    lines = markdown.splitlines(keepends=True)
    pages: set[int | None] = set()
    for start_index in range(len(lines)):
        for end_index in range(start_index + 1, min(len(lines), start_index + 12) + 1):
            selected = lines[start_index:end_index]
            reconstructed_with_ending = "".join(selected)
            reconstructed_without_ending = "".join(
                (*selected[:-1], _without_line_ending(selected[-1]))
            )
            if excerpt in (reconstructed_with_ending, reconstructed_without_ending):
                pages.add(_nearest_page(lines, start_index))
    return pages


def _without_line_ending(line: str) -> str:
    return re.sub(r"(?:\r\n|[\n\r\v\f\x1c-\x1e\x85\u2028\u2029])$", "", line)


def _nearest_page(lines: Sequence[str], start_index: int) -> int | None:
    for line in reversed(lines[: start_index + 1]):
        match = re.fullmatch(
            r"\s*(?:#{1,6}\s+)?Page\s+(\d+)(?:\s+of\s+\d+)?\s*", line, re.I
        )
        if match is not None:
            return int(match.group(1))
    return None


def _manifest_digest(manifest: Mapping[str, Any], field: str) -> str:
    value = manifest.get(field)
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ManifestUnitizerCommandError(f"integration manifest has invalid {field}")
    return value


def _normalized_approval(value: str) -> str:
    return " ".join(value.split())


def _read_regular_input(path: Path, label: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ManifestUnitizerCommandError(f"{label} is not a regular file: {path}")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise ManifestUnitizerCommandError(f"{label} is unreadable: {path}") from exc


def _jsonl_records_from_bytes(
    payload: bytes,
    *,
    label: str,
    error_factory: type[ValueError],
) -> tuple[JsonRecord, ...]:
    records: list[JsonRecord] = []
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise error_factory(f"{label} is not UTF-8") from exc
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise error_factory(f"{label} line {line_number} is invalid JSON") from exc
        if not isinstance(raw, dict):
            raise error_factory(f"{label} line {line_number} is not an object")
        records.append(cast(JsonRecord, raw))
    return tuple(records)


def _command_required_string(record: Mapping[str, Any], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ManifestUnitizerCommandError(f"record is missing non-empty {field}")
    return value
