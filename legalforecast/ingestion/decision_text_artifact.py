"""Build hash-bound first-written-disposition text artifacts for label audit."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
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
                "parser_revision": _required_str(parser_config, "parser_revision"),
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
    if (
        parser_config.get("engine") != "mistral"
        or parser_config.get("parser_revision") != EXPECTED_PARSER_REVISION
        or parser_config.get("expected_parser_revision") != EXPECTED_PARSER_REVISION
    ):
        raise DecisionTextArtifactError(
            f"parser revision is not the pinned Mistral revision: {key}"
        )
    extracted_text = _mapping(parser.get("extracted_text"), "extracted_text")
    if extracted_text.get("source_document_id") != key[1]:
        raise DecisionTextArtifactError(f"extracted text identity mismatch: {key}")
    if extracted_text.get("extraction_method") != "mistral_parser_markdown":
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


def _input_commitments(commitments: Mapping[str, str]) -> dict[str, str]:
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
        if not _valid_sha256(value):
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


def _valid_sha256(value: str) -> bool:
    digest = value.removeprefix("sha256:")
    return len(digest) == 64 and all(
        character in "0123456789abcdef" for character in digest
    )
