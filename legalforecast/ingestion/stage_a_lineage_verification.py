# pyright: reportPrivateUsage=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportUnknownParameterType=false

"""Importable Stage A unitization/parse/review lineage verification helpers."""

from __future__ import annotations

import hashlib
import os
import sqlite3
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, cast

from legalforecast.evals.model_registry import ModelRegistryEntry
from legalforecast.ingestion.parse_quality import assess_parsed_text
from legalforecast.ingestion.readiness_provenance import ReadinessProvenanceError
from legalforecast.labeling.llm_pipeline import (
    STAGE_A_CLAIM_ONTOLOGY_V4_PROMPT_CONTRACT,
    STAGE_A_CLAIM_ONTOLOGY_V5_PROMPT_CONTRACT,
    STAGE_A_PROVIDER_ATTEMPT_CONTRACTS,
    LlmPipelineError,
)
from legalforecast.labeling.provider_journal import (
    PROVIDER_JOURNAL_SCHEMA_VERSION,
    ProviderCallIdentity,
    ProviderCycleCaps,
    ProviderJournalError,
)
from legalforecast.labeling.unitizer_terminal import (
    LlmStageAUnitizerTerminalEscalation,
)
from legalforecast.unitization.review import UnitizationReviewError

JsonRecord = dict[str, Any]


def _cli() -> Any:
    from legalforecast import cli as cli_module

    return cli_module


@dataclass(frozen=True, slots=True)
class StageALineageInputs:
    """Typed CLI inputs for Stage A lineage verification.

    Handlers adapt argparse.Namespace at the facade wrapper boundary.
    """

    selection: Path
    parser_manifest: Path
    model_registry: Path | None = None
    model_key: str | None = None
    selection_run_card: Path | None = None
    download_manifest: Path | None = None
    disclosure_clearance: Path | None = None
    materialization_run_card: Path | None = None
    document_root: Path | None = None
    parse_requests: Path | None = None
    parser_run_card: Path | None = None
    provider_cycle_caps: Path | None = None
    provider_journal: Path | None = None
    controlled_private_root: Path | None = None
    purchase_ledger_initialization_receipt: Path | None = None


VERIFIED_STAGE_A_PARSE_LINEAGE_SEAL = object()


@dataclass(frozen=True, slots=True)
class VerifiedStageAParseLineage:
    """Provider-free authenticated selection, parser, and Markdown lineage."""

    selection_records: tuple[JsonRecord, ...]
    selection_bytes: bytes
    parser_records: tuple[JsonRecord, ...]
    parser_manifest_bytes: bytes
    document_root: Path
    markdown_root: Path
    cohort_cycle_id: str
    input_paths: tuple[Path, ...]
    input_commitments: Mapping[str, object]
    markdown_tree: Mapping[str, object]
    file_snapshots: Mapping[Path, bytes]
    document_tree: Mapping[str, bytes]
    markdown_bytes: Mapping[str, bytes]
    download_records: tuple[JsonRecord, ...] = ()
    verifier_seal: object | None = field(repr=False, compare=False, default=None)


@dataclass(frozen=True, slots=True)
class StageAUnitizationLineage:
    selection_records: tuple[JsonRecord, ...]
    parser_records: tuple[JsonRecord, ...]
    registry_entry: ModelRegistryEntry
    registry_sha256: str
    provider_caps: ProviderCycleCaps
    provider_caps_sha256: str
    provider_journal_path: Path
    document_root: Path
    markdown_root: Path
    cohort_cycle_id: str
    input_paths: tuple[Path, ...]
    input_commitments: Mapping[str, object]
    markdown_tree: Mapping[str, object]
    file_snapshots: Mapping[Path, bytes]
    document_tree: Mapping[str, bytes]
    markdown_bytes: Mapping[str, bytes]
    download_records: tuple[JsonRecord, ...] = ()
    verified_provider_attempt_rows: tuple[JsonRecord, ...] = ()
    unitizer_terminal_escalations: (
        Mapping[str, tuple[LlmStageAUnitizerTerminalEscalation, Mapping[str, Any]]]
        | None
    ) = None


def required_stage_a_lineage_path(path: Path | None, flag: str) -> Path:
    _c = _cli()
    CommandError = _c.CommandError
    if path is None:
        raise CommandError(
            "authenticated Stage A lineage requires " + flag + " with --execute"
        )
    return path


def verify_stage_a_unitization_lineage_uncached(
    inputs: StageALineageInputs,
    *,
    markdown_root: Path,
    parse_lineage: object | None = None,
) -> StageAUnitizationLineage:
    _c = _cli()
    if parse_lineage is None:
        parse_lineage = verify_stage_a_parse_lineage_uncached(
            inputs, markdown_root=markdown_root
        )
    elif (
        not isinstance(parse_lineage, VerifiedStageAParseLineage)
        or parse_lineage.verifier_seal is not VERIFIED_STAGE_A_PARSE_LINEAGE_SEAL
    ):
        raise _c.CommandError("Stage A parse-lineage handoff is not verifier-owned")
    registry_path = inputs.model_registry
    model_key = inputs.model_key
    if registry_path is None or model_key is None:
        raise _c.CommandError(
            "authenticated Stage A unitization lineage requires --model-registry "
            "and --model-key"
        )
    caps_path = required_stage_a_lineage_path(
        inputs.provider_cycle_caps, "--provider-cycle-caps"
    )
    provider_journal_path = required_stage_a_lineage_path(
        inputs.provider_journal, "--provider-journal"
    )
    for path in (registry_path, caps_path):
        if path.is_symlink() or not path.is_file():
            raise _c.CommandError(f"authenticated Stage A input is not a file: {path}")
    if provider_journal_path.exists() and (
        provider_journal_path.is_symlink() or not provider_journal_path.is_file()
    ):
        raise _c.CommandError(
            f"shared provider journal is not a regular file: {provider_journal_path}"
        )
    provider_snapshots = {
        path: _c._read_singly_linked_regular_input(
            path, label="authenticated Stage A input"
        )
        for path in (registry_path, caps_path)
    }
    try:
        provider_caps = _c.load_provider_cycle_caps_bytes(
            provider_snapshots[caps_path], source=caps_path
        )
    except ProviderJournalError as exc:
        raise _c.CommandError(str(exc)) from exc
    if provider_caps.cycle_id != parse_lineage.cohort_cycle_id:
        raise _c.CommandError(
            "provider cycle caps cycle_id differs from authenticated cohort: "
            f"{provider_caps.cycle_id!r} != {parse_lineage.cohort_cycle_id!r}"
        )
    registry_entries, registry_sha256 = _c._registry_entries_for_keys_bytes(
        provider_snapshots[registry_path], (model_key,)
    )
    registry_entry = registry_entries[0]
    provider_caps.cap_usd(registry_entry.provider)
    require_stage_a_parse_lineage_unchanged(parse_lineage)
    _c._require_snapshot_unchanged(
        provider_snapshots, label="authenticated Stage A provider input"
    )
    return StageAUnitizationLineage(
        selection_records=parse_lineage.selection_records,
        parser_records=parse_lineage.parser_records,
        download_records=parse_lineage.download_records,
        registry_entry=registry_entry,
        registry_sha256=registry_sha256,
        provider_caps=provider_caps,
        # contract-ratchet: allow moved CLI replay still hashes the captured caps bytes.
        provider_caps_sha256=hashlib.sha256(provider_snapshots[caps_path]).hexdigest(),
        provider_journal_path=provider_journal_path,
        document_root=parse_lineage.document_root,
        markdown_root=parse_lineage.markdown_root,
        cohort_cycle_id=parse_lineage.cohort_cycle_id,
        input_paths=(
            *parse_lineage.input_paths[:10],
            registry_path,
            caps_path,
            provider_journal_path,
            *parse_lineage.input_paths[10:],
        ),
        input_commitments={
            **parse_lineage.input_commitments,
            "model_registry": stage_a_file_commitment(
                registry_path, payload=provider_snapshots[registry_path]
            ),
            "provider_cycle_caps": stage_a_file_commitment(
                caps_path, payload=provider_snapshots[caps_path]
            ),
        },
        markdown_tree=parse_lineage.markdown_tree,
        file_snapshots={**parse_lineage.file_snapshots, **provider_snapshots},
        document_tree=parse_lineage.document_tree,
        markdown_bytes=parse_lineage.markdown_bytes,
    )


def verify_stage_a_parse_lineage_uncached(
    inputs: StageALineageInputs,
    *,
    markdown_root: Path,
) -> VerifiedStageAParseLineage:
    """Authenticate parser inputs before model registry or journal concerns."""
    _c = _cli()

    selection_path = inputs.selection
    selection_run_card_path = required_stage_a_lineage_path(
        inputs.selection_run_card, "--selection-run-card"
    )
    manifest_path = required_stage_a_lineage_path(
        inputs.download_manifest, "--download-manifest"
    )
    clearance_path = required_stage_a_lineage_path(
        inputs.disclosure_clearance, "--disclosure-clearance"
    )
    materialization_card_path = required_stage_a_lineage_path(
        inputs.materialization_run_card, "--materialization-run-card"
    )
    document_root = required_stage_a_lineage_path(
        inputs.document_root, "--document-root"
    )
    requests_path = required_stage_a_lineage_path(
        inputs.parse_requests, "--parse-requests"
    )
    parser_manifest_path = inputs.parser_manifest
    parser_run_card_path = required_stage_a_lineage_path(
        inputs.parser_run_card, "--parser-run-card"
    )
    regular_files = (
        selection_path,
        selection_run_card_path,
        manifest_path,
        clearance_path,
        materialization_card_path,
        requests_path,
        parser_manifest_path,
        parser_run_card_path,
    )
    for path in regular_files:
        if path.is_symlink() or not path.is_file():
            raise _c.CommandError(f"authenticated Stage A input is not a file: {path}")
    stage_a_file_snapshots = {
        path: _c._read_singly_linked_regular_input(
            path, label="authenticated Stage A input"
        )
        for path in regular_files
    }
    if document_root.is_symlink() or not document_root.is_dir():
        raise _c.CommandError(
            f"authenticated Stage A document root is invalid: {document_root}"
        )
    if markdown_root.is_symlink() or not markdown_root.is_dir():
        raise _c.CommandError(
            f"authenticated Stage A Markdown root is invalid: {markdown_root}"
        )
    parser_records = tuple(
        _c._projection_jsonl_records(
            stage_a_file_snapshots[parser_manifest_path], source=parser_manifest_path
        )
    )
    verified_materialization = _c._verify_materialized_downstream_lineage(
        run_card_path=materialization_card_path,
        manifest_path=manifest_path,
        clearance_path=clearance_path,
        document_root=document_root,
        selection_path=selection_path,
        controlled_private_root=inputs.controlled_private_root,
        initialization_receipt_path=inputs.purchase_ledger_initialization_receipt,
    )
    for path in (
        selection_path,
        manifest_path,
        clearance_path,
        materialization_card_path,
    ):
        if (
            verified_materialization.artifact_bytes[os.path.abspath(path)]
            != stage_a_file_snapshots[path]
        ):
            raise _c.CommandError(f"authenticated Stage A input changed: {path}")
    selection_records = verified_materialization.selection_records
    selection_card_bytes = stage_a_file_snapshots[selection_run_card_path]
    selection_card = _c._projection_json_object(
        selection_card_bytes, source=selection_run_card_path
    )
    selection_bytes = verified_materialization.artifact_bytes[
        os.path.abspath(selection_path)
    ]
    _c._validate_selection_run_card_commitment(
        selection_card,
        selection_path=selection_path,
        selection_bytes=selection_bytes,
        selection_sha256=_c._bytes_sha256(selection_bytes),
        selection_record_count=len(selection_records),
        selection_run_card_path=selection_run_card_path,
        selection_run_card_bytes=selection_card_bytes,
        verified_successor_selection_card=(
            verified_materialization.verified_successor_selection_card
        ),
    )
    materialization_paths = verified_materialization.paths
    markdown_tree, markdown_bytes = _c._stage_a_markdown_tree_snapshot(
        parser_records, markdown_root=markdown_root
    )
    _c._verify_stage_a_parse_lineage(
        selection_path=selection_path,
        manifest_path=manifest_path,
        clearance_path=clearance_path,
        document_root=document_root,
        materialization_paths=materialization_paths,
        requests_path=requests_path,
        parser_manifest_path=parser_manifest_path,
        parser_records=parser_records,
        parser_run_card_path=parser_run_card_path,
        selection_bytes=stage_a_file_snapshots[selection_path],
        requests_bytes=stage_a_file_snapshots[requests_path],
        parser_manifest_bytes=stage_a_file_snapshots[parser_manifest_path],
        parser_run_card_bytes=stage_a_file_snapshots[parser_run_card_path],
        markdown_root=markdown_root,
        download_records=verified_materialization.manifest_records,
        clearance_bytes=verified_materialization.artifact_bytes[
            os.path.abspath(clearance_path)
        ],
        markdown_bytes=markdown_bytes,
    )
    cohort_cycle_id = _c._materialization_cohort_cycle_id(
        materialization_card_path,
        captured_artifact_bytes=verified_materialization.artifact_bytes,
    )
    input_paths = (
        selection_path,
        selection_run_card_path,
        manifest_path,
        clearance_path,
        materialization_card_path,
        document_root,
        requests_path,
        parser_manifest_path,
        parser_run_card_path,
        markdown_root,
        *materialization_paths[1:],
    )
    file_commitments = {
        name: stage_a_file_commitment(path, payload=stage_a_file_snapshots[path])
        for name, path in (
            ("selection", selection_path),
            ("selection_run_card", selection_run_card_path),
            ("download_manifest", manifest_path),
            ("disclosure_clearance", clearance_path),
            ("materialization_run_card", materialization_card_path),
            ("parse_requests", requests_path),
            ("parser_manifest", parser_manifest_path),
            ("parser_run_card", parser_run_card_path),
        )
    }
    _c._require_snapshot_unchanged(
        stage_a_file_snapshots, label="authenticated Stage A input"
    )
    if _c._materializer_tree_snapshot(document_root) != dict(
        verified_materialization.document_tree
    ):
        raise _c.CommandError("authenticated Stage A document tree changed")
    return VerifiedStageAParseLineage(
        selection_records=tuple(dict(record) for record in selection_records),
        selection_bytes=stage_a_file_snapshots[selection_path],
        parser_records=parser_records,
        download_records=tuple(
            dict(record) for record in verified_materialization.manifest_records
        ),
        parser_manifest_bytes=stage_a_file_snapshots[parser_manifest_path],
        document_root=document_root,
        markdown_root=markdown_root,
        cohort_cycle_id=cohort_cycle_id,
        input_paths=input_paths,
        input_commitments={
            **file_commitments,
            "document_tree": {
                path: _c._bytes_sha256(payload)
                for path, payload in verified_materialization.document_tree.items()
            },
            "markdown_tree": dict(markdown_tree),
        },
        markdown_tree=markdown_tree,
        file_snapshots=dict(stage_a_file_snapshots),
        document_tree=dict(verified_materialization.document_tree),
        markdown_bytes=markdown_bytes,
        verifier_seal=VERIFIED_STAGE_A_PARSE_LINEAGE_SEAL,
    )


def require_stage_a_parse_lineage_unchanged(
    lineage: VerifiedStageAParseLineage,
) -> None:
    """Close the parser-lineage TOCTOU interval before a downstream decision."""
    _c = _cli()

    _c._require_snapshot_unchanged(
        lineage.file_snapshots, label="authenticated Stage A parser input"
    )
    if _c._materializer_tree_snapshot(lineage.document_root) != dict(
        lineage.document_tree
    ):
        raise _c.CommandError("authenticated Stage A document tree changed")
    markdown_paths = {
        lineage.markdown_root / relative_path: payload
        for relative_path, payload in lineage.markdown_bytes.items()
    }
    _c._require_snapshot_unchanged(
        markdown_paths, label="authenticated Stage A Markdown"
    )


def stage_a_file_commitment(path: Path, *, payload: bytes | None = None) -> JsonRecord:
    _c = _cli()
    return {
        "path": str(path.resolve()),
        "sha256": _c._bytes_sha256(payload)
        if payload is not None
        else _c._path_sha256(path),
    }


def stage_a_captured_payload(
    path: Path, *, captured_input_bytes: Mapping[str, bytes] | None
) -> bytes | None:
    """Return the caller-authenticated bytes for one path, when it captured it.

    This is a partial overlay, unlike `_captured_or_stable_input`: a caller
    that already authenticated a subset of an artifact chain binds exactly that
    subset, and every other path is still read fresh.  Reusing the captured
    bytes is what stops a verifier from authenticating one byte set while the
    caller commits another, which a re-read cannot detect when an input is
    swapped and restored around the read.
    """
    _c = _cli()

    if captured_input_bytes is None:
        return None
    return captured_input_bytes.get(str(path.resolve()))


def stage_a_captured_records(
    path: Path,
    *,
    label: str,
    captured_input_bytes: Mapping[str, bytes] | None,
) -> list[JsonRecord]:
    """Parse records from caller-authenticated bytes, or read the path fresh.

    Every Stage A artifact a caller captures is JSONL, and the capturing
    command already parses those same bytes with `_c._read_jsonl_payload`, so
    reuse decodes them identically rather than re-reading the path.
    """
    _c = _cli()

    payload = stage_a_captured_payload(path, captured_input_bytes=captured_input_bytes)
    if payload is None:
        return _c._read_records(path)
    try:
        return _c._read_jsonl_payload(payload, label=label)
    except ValueError as exc:
        raise _c.CommandError(str(exc)) from exc


def stage_a_captured_json_object(
    path: Path,
    *,
    label: str,
    captured_input_bytes: Mapping[str, bytes] | None,
) -> JsonRecord:
    """Parse one JSON object from caller-authenticated bytes, or read it fresh."""
    _c = _cli()

    payload = stage_a_captured_payload(path, captured_input_bytes=captured_input_bytes)
    if payload is None:
        return _c._read_json_object(path)
    try:
        return _c._read_json_object_payload(payload, label=label)
    except ValueError as exc:
        raise _c.CommandError(str(exc)) from exc


def verify_stage_a_parse_lineage(
    *,
    selection_path: Path,
    manifest_path: Path,
    clearance_path: Path,
    document_root: Path,
    materialization_paths: Sequence[Path],
    requests_path: Path,
    parser_manifest_path: Path,
    parser_records: Sequence[Mapping[str, Any]],
    parser_run_card_path: Path,
    selection_bytes: bytes,
    requests_bytes: bytes,
    parser_manifest_bytes: bytes,
    parser_run_card_bytes: bytes,
    markdown_root: Path,
    download_records: Sequence[Mapping[str, Any]],
    clearance_bytes: bytes,
    markdown_bytes: Mapping[str, bytes],
) -> None:
    _c = _cli()
    parser_card = _c._projection_json_object(
        parser_run_card_bytes, source=parser_run_card_path
    )
    _c._validate_parser_run_card_commitments(
        parser_card,
        parser_manifest_path=parser_manifest_path,
        parser_manifest_sha256=_c._bytes_sha256(parser_manifest_bytes),
        clearance_path=clearance_path,
        clearance_sha256=_c._bytes_sha256(clearance_bytes),
        parser_record_count=len(parser_records),
    )
    expected_inputs = (
        selection_path,
        requests_path,
        clearance_path,
        *materialization_paths,
    )
    raw_inputs = parser_card.get("input_paths")
    raw_outputs = parser_card.get("output_paths")
    if not isinstance(raw_inputs, Sequence) or isinstance(raw_inputs, (str, bytes)):
        raise _c.CommandError("parse-documents run card lacks exact input paths")
    if not isinstance(raw_outputs, Sequence) or isinstance(raw_outputs, (str, bytes)):
        raise _c.CommandError("parse-documents run card lacks exact output paths")
    actual_inputs = tuple(
        Path(str(path)).resolve() for path in cast(Sequence[object], raw_inputs)
    )
    if actual_inputs != tuple(path.resolve() for path in expected_inputs):
        raise _c.CommandError("parse-documents inputs differ from materialized lineage")
    actual_outputs = tuple(
        Path(str(path)).resolve() for path in cast(Sequence[object], raw_outputs)
    )
    if actual_outputs != (parser_manifest_path.resolve(),):
        raise _c.CommandError("parse-documents output differs from parser manifest")
    commitments = parser_card.get("source_commitments")
    if not isinstance(commitments, Mapping):
        raise _c.CommandError("parse-documents run card lacks source commitments")
    for name, path in (
        ("selection", selection_path),
        ("requests", requests_path),
        ("disclosure_clearance", clearance_path),
    ):
        _c._validate_named_path_commitment(
            cast(Mapping[str, object], commitments),
            name=name,
            expected_path=path,
            expected_sha256=(
                _c._bytes_sha256(clearance_bytes)
                if path == clearance_path
                else _c._bytes_sha256(
                    requests_bytes if path == requests_path else selection_bytes
                )
            ),
        )
    verify_stage_a_parse_records(
        download_records=download_records,
        request_records=_c._projection_jsonl_records(
            requests_bytes, source=requests_path
        ),
        parser_records=parser_records,
        document_root=document_root,
        parser_output_root=parser_manifest_path.parent,
        markdown_root=markdown_root,
        markdown_bytes=markdown_bytes,
    )


def verify_stage_a_parse_records(
    *,
    download_records: Sequence[Mapping[str, Any]],
    request_records: Sequence[Mapping[str, Any]],
    parser_records: Sequence[Mapping[str, Any]],
    document_root: Path,
    parser_output_root: Path,
    markdown_root: Path,
    markdown_bytes: Mapping[str, bytes],
) -> None:
    _c = _cli()

    def keyed(
        records: Sequence[Mapping[str, Any]], *, label: str
    ) -> dict[tuple[str, str], Mapping[str, Any]]:
        result: dict[tuple[str, str], Mapping[str, Any]] = {}
        for record in records:
            key = (
                _c._required_str(record, "candidate_id"),
                _c._required_str(record, "source_document_id"),
            )
            if key in result:
                raise _c.CommandError(f"duplicate {label} row: {key[0]}/{key[1]}")
            result[key] = record
        return result

    downloads = keyed(download_records, label="materialized manifest")
    requests = keyed(request_records, label="parse request")
    parsed = keyed(parser_records, label="parser manifest")
    if not downloads or set(downloads) != set(requests) or set(requests) != set(parsed):
        raise _c.CommandError(
            "materialized documents, parse requests, and parser manifest differ"
        )
    for key, download in downloads.items():
        request = requests[key]
        parser = parsed[key]
        local_path = Path(_c._required_str(download, "local_path"))
        expected_input = (
            local_path if local_path.is_absolute() else document_root / local_path
        ).resolve()
        request_input = Path(_c._required_str(request, "input_path")).resolve()
        if request_input != expected_input:
            raise _c.CommandError(f"parse request input differs: {key[0]}/{key[1]}")
        if request.get("expected_sha256") != _c._required_str(
            download, "sha256"
        ).removeprefix("sha256:") or request.get(
            "expected_byte_count"
        ) != _c._required_int(download, "byte_count"):
            raise _c.CommandError(f"parse request source commitment differs: {key}")
        if parser.get("status") != "succeeded" or parser.get("quality_flags") != []:
            raise _c.CommandError(f"parser record is not clean and successful: {key}")
        if parser.get("source_sha256") != request.get("expected_sha256") or parser.get(
            "source_byte_count"
        ) != request.get("expected_byte_count"):
            raise _c.CommandError(f"parser source commitment differs: {key}")
        request_markdown = Path(_c._required_str(request, "markdown_output_path"))
        expected_markdown = (
            request_markdown
            if request_markdown.is_absolute()
            else parser_output_root / request_markdown
        ).resolve()
        parser_markdown = stage_a_markdown_path(parser, markdown_root=markdown_root)
        if parser_markdown != expected_markdown:
            raise _c.CommandError(f"parser Markdown path differs: {key}")
        extracted = parser.get("extracted_text")
        if not isinstance(extracted, Mapping):
            raise _c.CommandError(f"parser record lacks extracted text: {key}")
        extracted_record = cast(Mapping[str, object], extracted)
        if extracted_record.get("extraction_method") != "mistral_parser_markdown":
            raise _c.CommandError(f"parser record is not live Mistral output: {key}")
        expected_text_sha = extracted_record.get("text_sha256")
        relative_markdown = parser_markdown.relative_to(
            markdown_root.resolve()
        ).as_posix()
        try:
            markdown_payload = markdown_bytes[relative_markdown]
        except KeyError as exc:
            raise _c.CommandError(
                f"parser Markdown snapshot is missing: {key}"
            ) from exc
        # contract-ratchet: allow moved CLI replay still hashes captured Markdown bytes.
        actual_text_sha = hashlib.sha256(markdown_payload).hexdigest()
        if not isinstance(expected_text_sha, str) or (
            expected_text_sha.removeprefix("sha256:") != actual_text_sha
        ):
            raise _c.CommandError(f"parser Markdown hash differs: {key}")
        document_role = download.get("document_role")
        role = document_role if isinstance(document_role, str) else None
        parser_config = parser.get("parser_config")
        strict_quality = isinstance(parser_config, Mapping) and (
            parser_config.get("engine") not in {"fixture", "fixture_markdown"}
        )
        try:
            markdown_text = markdown_payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise _c.CommandError(
                f"parser Markdown is not UTF-8: {key[0]}/{key[1]}"
            ) from exc
        assessment = assess_parsed_text(
            markdown_text,
            role,
            enforce_role_thresholds=strict_quality,
        )
        if assessment.rejected:
            raise _c.CommandError(
                "parser Markdown failed parse-quality gate: "
                f"{key[0]}/{key[1]} ({', '.join(assessment.rejection_reasons)})"
            )


def stage_a_markdown_path(record: Mapping[str, Any], *, markdown_root: Path) -> Path:
    _c = _cli()
    raw = Path(_c._required_str(record, "markdown_path"))
    path = (raw if raw.is_absolute() else markdown_root / raw).resolve()
    root = markdown_root.resolve()
    if not path.is_relative_to(root):
        raise _c.CommandError(f"parser Markdown escapes trusted root: {path}")
    if path.is_symlink() or not path.is_file():
        raise _c.CommandError(f"parser Markdown is not a regular file: {path}")
    return path


def stage_a_markdown_tree_snapshot(
    parser_records: Sequence[Mapping[str, Any]], *, markdown_root: Path
) -> tuple[dict[str, JsonRecord], dict[str, bytes]]:
    _c = _cli()
    root = markdown_root.resolve()
    expected_paths = {
        stage_a_markdown_path(record, markdown_root=markdown_root)
        for record in parser_records
    }
    observed_paths: set[Path] = set()
    for path in markdown_root.rglob("*"):
        if path.is_symlink():
            raise _c.CommandError(f"Markdown tree contains a symlink: {path}")
        if path.is_file() and path.suffix.casefold() == ".md":
            observed_paths.add(path.resolve())
    if observed_paths != expected_paths:
        raise _c.CommandError("Markdown tree differs from exact parser manifest")
    snapshots = {
        path.relative_to(root).as_posix(): _c._read_singly_linked_regular_input(
            path, label="Stage A Markdown"
        )
        for path in sorted(expected_paths)
    }
    return {
        path.relative_to(root).as_posix(): {
            "path": str(path),
            "sha256": _c._bytes_sha256(snapshots[path.relative_to(root).as_posix()]),
            "byte_count": len(snapshots[path.relative_to(root).as_posix()]),
        }
        for path in sorted(expected_paths)
    }, snapshots


def require_stage_a_lineage_unchanged(
    lineage: StageAUnitizationLineage,
) -> None:
    _c = _cli()
    _c._require_snapshot_unchanged(
        lineage.file_snapshots, label="authenticated Stage A input"
    )
    if _c._materializer_tree_snapshot(lineage.document_root) != dict(
        lineage.document_tree
    ):
        raise _c.CommandError("authenticated Stage A document tree changed")
    markdown_paths = {
        lineage.markdown_root / relative_path: payload
        for relative_path, payload in lineage.markdown_bytes.items()
    }
    _c._require_snapshot_unchanged(
        markdown_paths, label="authenticated Stage A Markdown"
    )


def stage_a_provider_attempt_rows(
    path: Path, *, snapshot: sqlite3.Connection | None = None
) -> tuple[JsonRecord, ...]:
    _c = _cli()
    return _c._provider_stage_attempt_rows(path, stage="llm-unitize", snapshot=snapshot)


def verify_stage_a_provider_replay(
    *,
    lineage: StageAUnitizationLineage,
    prediction_units_path: Path,
    audit_path: Path,
    review_queue_path: Path,
    terminal_review_queue_path: Path | None = None,
    provider_attempt_namespace: str | None = None,
    terminal_escalations: Mapping[
        str, tuple[LlmStageAUnitizerTerminalEscalation, Mapping[str, Any]]
    ]
    | None = None,
    captured_input_bytes: Mapping[str, bytes] | None = None,
    journal_snapshot: sqlite3.Connection | None = None,
) -> tuple[dict[str, JsonRecord], str, tuple[JsonRecord, ...]]:
    _c = _cli()
    # Identity and attempt rows must describe one journal state, so both read
    # the same query-only snapshot of a journal SQLite never opens for write.
    owns_snapshot = journal_snapshot is None
    if journal_snapshot is None:
        try:
            journal_snapshot = _c.open_provider_journal_snapshot(
                lineage.provider_journal_path
            )
        except ProviderJournalError as exc:
            raise _c.CommandError(str(exc)) from exc
    try:
        _c.verify_provider_journal_identity(
            lineage.provider_journal_path,
            cycle_id=lineage.cohort_cycle_id,
            provider_cycle_caps_sha256=lineage.provider_caps_sha256,
            snapshot=journal_snapshot,
        )
        all_attempt_rows = stage_a_provider_attempt_rows(
            lineage.provider_journal_path, snapshot=journal_snapshot
        )
    except ProviderJournalError as exc:
        raise _c.CommandError(str(exc)) from exc
    finally:
        if owns_snapshot and journal_snapshot is not None:
            journal_snapshot.close()
    try:
        prompt_records = _c.stage_a_unitization_prompt_records(
            selection_records=lineage.selection_records,
            parser_records=lineage.parser_records,
            markdown_root=lineage.markdown_root,
            markdown_bytes=lineage.markdown_bytes,
            provider_attempt_namespace=provider_attempt_namespace,
        )
    except (OSError, UnicodeError, ValueError) as exc:
        raise _c.CommandError(f"cannot reconstruct Stage A prompts: {exc}") from exc
    prompts_by_candidate: dict[str, Mapping[str, Any]] = {}
    for record in prompt_records:
        candidate_id = _c._required_str(record, "candidate_id")
        if candidate_id in prompts_by_candidate:
            raise _c.CommandError(f"duplicate llm-unitize prompt: {candidate_id}")
        prompts_by_candidate[candidate_id] = record

    def prompt_records_for_contract(
        contract: str | None,
    ) -> tuple[Mapping[str, Any], ...]:
        """Reconstruct the exact prompt family for one durable attempt key."""

        if contract == provider_attempt_namespace:
            return tuple(prompt_records)
        return tuple(
            _c.stage_a_unitization_prompt_records(
                selection_records=lineage.selection_records,
                parser_records=lineage.parser_records,
                markdown_root=lineage.markdown_root,
                markdown_bytes=lineage.markdown_bytes,
                provider_attempt_namespace=contract,
                # The current card has already authenticated the eligibility
                # artifact.  Historical-key reconstruction must not make an
                # old v4/v5 attempt disappear merely because it is not active.
                enforce_target_document_eligibility=(
                    contract
                    not in {
                        STAGE_A_CLAIM_ONTOLOGY_V4_PROMPT_CONTRACT,
                        STAGE_A_CLAIM_ONTOLOGY_V5_PROMPT_CONTRACT,
                    }
                ),
            )
        )

    legacy_prompt_records = (
        tuple(prompt_records)
        if provider_attempt_namespace
        not in {
            STAGE_A_CLAIM_ONTOLOGY_V4_PROMPT_CONTRACT,
            STAGE_A_CLAIM_ONTOLOGY_V5_PROMPT_CONTRACT,
        }
        else prompt_records_for_contract("claim-ontology-v2")
    )
    v4_prompt_records = (
        tuple(prompt_records)
        if provider_attempt_namespace == STAGE_A_CLAIM_ONTOLOGY_V4_PROMPT_CONTRACT
        else prompt_records_for_contract(STAGE_A_CLAIM_ONTOLOGY_V4_PROMPT_CONTRACT)
    )
    v5_prompt_records = (
        tuple(prompt_records)
        if provider_attempt_namespace == STAGE_A_CLAIM_ONTOLOGY_V5_PROMPT_CONTRACT
        else prompt_records_for_contract(STAGE_A_CLAIM_ONTOLOGY_V5_PROMPT_CONTRACT)
    )
    legacy_prompts_by_candidate = {
        _c._required_str(record, "candidate_id"): _c._required_str(record, "prompt")
        for record in legacy_prompt_records
    }
    v4_prompts_by_candidate = {
        _c._required_str(record, "candidate_id"): _c._required_str(record, "prompt")
        for record in v4_prompt_records
    }
    v5_prompts_by_candidate = {
        _c._required_str(record, "candidate_id"): _c._required_str(record, "prompt")
        for record in v5_prompt_records
    }
    raw_records = stage_a_captured_records(
        prediction_units_path,
        label="raw prediction units",
        captured_input_bytes=captured_input_bytes,
    )
    audit_records = stage_a_captured_records(
        audit_path,
        label="llm-unitization audit",
        captured_input_bytes=captured_input_bytes,
    )
    queue_records = stage_a_captured_records(
        review_queue_path,
        label="merged unitization review queue",
        captured_input_bytes=captured_input_bytes,
    )
    terminal_queue_records = (
        stage_a_captured_records(
            terminal_review_queue_path,
            label="unitizer terminal review queue",
            captured_input_bytes=captured_input_bytes,
        )
        if terminal_review_queue_path is not None
        else []
    )
    raw_by_candidate: dict[str, Mapping[str, Any]] = {}
    for record in raw_records:
        candidate_id = _c._required_str(record, "candidate_id")
        if candidate_id in raw_by_candidate:
            raise _c.CommandError(f"duplicate llm-unitize output: {candidate_id}")
        raw_by_candidate[candidate_id] = record
    audit_by_candidate: dict[str, Mapping[str, Any]] = {}
    for record in audit_records:
        candidate_id = _c._required_str(record, "candidate_id")
        if candidate_id in audit_by_candidate:
            raise _c.CommandError(f"duplicate llm-unitize audit: {candidate_id}")
        audit_by_candidate[candidate_id] = record
    candidate_ids = {
        _c._required_str(record, "candidate_id") for record in lineage.selection_records
    }
    selections_by_candidate = {
        _c._required_str(record, "candidate_id"): record
        for record in lineage.selection_records
    }
    if (
        set(prompts_by_candidate) != candidate_ids
        or set(raw_by_candidate) != candidate_ids
        or set(audit_by_candidate) != candidate_ids
    ):
        raise _c.CommandError("llm-unitize candidate coverage differs from selection")
    provider_account = _c._local_provider_account(
        lineage.provider_caps, lineage.registry_entry.provider
    )
    active_keys: dict[str, str] = {}
    recognized_keys: dict[str, frozenset[str]] = {}
    for candidate_id in candidate_ids:
        prompt = _c._required_str(prompts_by_candidate[candidate_id], "prompt")
        active_base_identity = dict(
            stage="llm-unitize",
            candidate_id=candidate_id,
            model_key=lineage.registry_entry.registry_key,
            prompt=prompt,
            model_registry_sha256=lineage.registry_sha256,
            account=provider_account,
        )
        active_keys[candidate_id] = ProviderCallIdentity(
            **active_base_identity,
            prompt_contract=provider_attempt_namespace,
        ).logical_call_key
        legacy_prompt = legacy_prompts_by_candidate[candidate_id]
        v4_prompt = v4_prompts_by_candidate[candidate_id]
        v5_prompt = v5_prompts_by_candidate[candidate_id]
        recognized_keys[candidate_id] = frozenset(
            {
                ProviderCallIdentity(
                    stage="llm-unitize",
                    candidate_id=candidate_id,
                    model_key=lineage.registry_entry.registry_key,
                    prompt=(
                        v4_prompt
                        if contract == STAGE_A_CLAIM_ONTOLOGY_V4_PROMPT_CONTRACT
                        else (
                            v5_prompt
                            if contract == STAGE_A_CLAIM_ONTOLOGY_V5_PROMPT_CONTRACT
                            else legacy_prompt
                        )
                    ),
                    model_registry_sha256=lineage.registry_sha256,
                    prompt_contract=contract,
                    account=provider_account,
                ).logical_call_key
                for contract in (None, *STAGE_A_PROVIDER_ATTEMPT_CONTRACTS)
            }
        )
    rows_by_candidate: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    attempt_rows: list[Mapping[str, Any]] = []
    for row in all_attempt_rows:
        candidate_id = _c._required_str(row, "candidate_id")
        # The provider journal is cycle-wide and append-only. Authenticated
        # successor cohorts therefore retain historical rows for candidates
        # they replaced; only rows for the active selection participate here.
        if candidate_id not in candidate_ids:
            continue
        if (
            row.get("model_key") != lineage.registry_entry.registry_key
            or row.get("logical_call_key") not in recognized_keys[candidate_id]
        ):
            raise _c.CommandError(
                f"llm-unitize provider identity or prompt differs: {candidate_id}"
            )
        if row.get("logical_call_key") != active_keys[candidate_id]:
            continue
        attempt_rows.append(row)
        rows_by_candidate[candidate_id].append(row)
    terminal_by_candidate = dict(terminal_escalations or {})
    if not set(terminal_by_candidate) <= candidate_ids:
        raise _c.CommandError("unitizer terminal escalation coverage differs")
    prompt_commitments: dict[str, JsonRecord] = {}
    journal_queue_by_candidate: dict[str, list[JsonRecord]] = {}
    for candidate_id in sorted(candidate_ids):
        prompt_record = prompts_by_candidate[candidate_id]
        prompt = _c._required_str(prompt_record, "prompt")
        prompt_digest = _c._required_str(prompt_record, "prompt_sha256")
        expected_logical_key = active_keys[candidate_id]
        candidate_rows = rows_by_candidate[candidate_id]
        if any(
            row.get("logical_call_key") != expected_logical_key
            or row.get("model_key") != lineage.registry_entry.registry_key
            or row.get("provider") != lineage.registry_entry.provider
            or row.get("account") != provider_account
            or row.get("prompt_text") != prompt
            or row.get("prompt_sha256") != prompt_digest.removeprefix("sha256:")
            or row.get("model_registry_sha256") != lineage.registry_sha256
            for row in candidate_rows
        ):
            raise _c.CommandError(
                f"llm-unitize provider identity or prompt differs: {candidate_id}"
            )
        terminal = terminal_by_candidate.get(candidate_id)
        if terminal is not None:
            escalation, receipt_commitment = terminal
            raw = raw_by_candidate[candidate_id]
            audit = audit_by_candidate[candidate_id]
            expected_queue = list(
                _c.llm_unitize_cases(
                    selection_records=(selections_by_candidate[candidate_id],),
                    parser_records=lineage.parser_records,
                    markdown_root=lineage.markdown_root,
                    markdown_bytes=lineage.markdown_bytes,
                    registry_entry=lineage.registry_entry,
                    model_registry_sha256=lineage.registry_sha256,
                    terminal_escalations={candidate_id: terminal},
                    provider_attempt_namespace=provider_attempt_namespace,
                ).terminal_review_queue_records
            )
            if (
                raw
                != {
                    "candidate_id": candidate_id,
                    "case_id": prompt_record.get("case_id"),
                    "prediction_units": [],
                }
                or audit.get("status") != "terminal_escalation"
                or audit.get("terminal_escalation") != escalation.to_record()
                or audit.get("terminal_escalation_receipt") != dict(receipt_commitment)
                or audit.get("unitization_review_queue") != []
                or audit.get("unitizer_terminal_review_queue") != expected_queue
            ):
                raise _c.CommandError(
                    f"llm-unitize terminal audit does not replay: {candidate_id}"
                )
            journal_queue_by_candidate[candidate_id] = expected_queue
            prompt_commitments[candidate_id] = {
                "case_id": prompt_record["case_id"],
                "prompt_sha256": prompt_digest,
                "prediction_units_sha256": _c._canonical_json_sha256([]),
                "terminal_escalation_sha256": escalation.escalation_sha256,
                "terminal_escalation_receipt": dict(receipt_commitment),
                "provider_attempt_ordinals": [
                    _c._required_int(attempt, "attempt_ordinal")
                    for attempt in escalation.failed_attempts
                ],
            }
            continue
        settled = [row for row in candidate_rows if row.get("status") == "settled"]
        if len(settled) != 1:
            raise _c.CommandError(
                f"llm-unitize requires exactly one settled attempt: {candidate_id}"
            )
        row = settled[0]
        try:
            normalized = _c.json.loads(
                _c._required_str(row, "normalized_response_json")
            )
            reconstructed = _c.json.loads(
                _c._required_str(row, "reconstructed_result_json")
            )
        except (_c.json.JSONDecodeError, ValueError) as exc:
            raise _c.CommandError(
                f"llm-unitize journal reconstruction is invalid: {candidate_id}"
            ) from exc
        if not isinstance(normalized, Mapping) or not isinstance(
            reconstructed, Mapping
        ):
            raise _c.CommandError(
                f"llm-unitize journal reconstruction is invalid: {candidate_id}"
            )
        reconstructed_units = cast(Mapping[str, object], reconstructed).get(
            "prediction_units"
        )
        reconstructed_review_items: object = cast(
            Mapping[str, object], reconstructed
        ).get("review_items")
        if (
            not isinstance(reconstructed_review_items, Sequence)
            or isinstance(reconstructed_review_items, (str, bytes))
            or not all(
                isinstance(item, Mapping)
                for item in cast(Sequence[object], reconstructed_review_items)
            )
        ):
            raise _c.CommandError(
                f"llm-unitize journal review items are invalid: {candidate_id}"
            )
        raw = raw_by_candidate[candidate_id]
        if (
            raw.get("case_id") != prompt_record.get("case_id")
            or raw.get("prediction_units") != reconstructed_units
        ):
            raise _c.CommandError(
                f"llm-unitize raw units do not reproduce from journal: {candidate_id}"
            )
        audit = audit_by_candidate[candidate_id]
        journal_review_items = [
            dict(cast(Mapping[str, Any], item))
            for item in cast(Sequence[object], reconstructed_review_items)
        ]
        if audit.get("review_items", []) != journal_review_items:
            raise _c.CommandError(
                f"llm-unitize review items do not reproduce from journal: "
                f"{candidate_id}"
            )
        candidate_queue = list(
            _c.unitization_review_queue_records_from_items(
                candidate_id=candidate_id,
                case_id=_c._required_str(prompt_record, "case_id"),
                review_items=journal_review_items,
            )
        )
        if audit.get("unitization_review_queue", []) != candidate_queue:
            raise _c.CommandError(
                f"llm-unitize audit queue does not reproduce from journal: "
                f"{candidate_id}"
            )
        journal_queue_by_candidate[candidate_id] = candidate_queue
        normalized_record = cast(Mapping[str, object], normalized)
        raw_output = normalized_record.get("raw_output")
        if not isinstance(raw_output, str):
            raise _c.CommandError(
                f"llm-unitize journal lacks normalized raw output: {candidate_id}"
            )
        if provider_attempt_namespace in {
            STAGE_A_CLAIM_ONTOLOGY_V4_PROMPT_CONTRACT,
            STAGE_A_CLAIM_ONTOLOGY_V5_PROMPT_CONTRACT,
        }:
            try:
                replayed = _c.reconstruct_stage_a_unitization_response(
                    selection_record=selections_by_candidate[candidate_id],
                    parser_records=lineage.parser_records,
                    markdown_root=lineage.markdown_root,
                    markdown_bytes=lineage.markdown_bytes,
                    raw_output=raw_output,
                    model_key=lineage.registry_entry.registry_key,
                    provider_attempt_namespace=provider_attempt_namespace,
                )
            except (LlmPipelineError, ValueError) as exc:
                raise _c.CommandError(
                    "llm-unitize response does not replay under "
                    f"{provider_attempt_namespace}: {candidate_id}: {exc}"
                ) from exc
            if [unit.to_record() for unit in replayed.units] != reconstructed_units or [
                item.to_record() for item in replayed.review_items
            ] != journal_review_items:
                raise _c.CommandError(
                    "llm-unitize reconstruction differs from response under "
                    f"{provider_attempt_namespace}: {candidate_id}"
                )
        if (
            audit.get("status") not in {"succeeded", "adjudication_pending"}
            or audit.get("model_key") != lineage.registry_entry.registry_key
            or audit.get("model_registry_sha256") != lineage.registry_sha256
            or audit.get("provider_prompt_sha256") != prompt_digest
            or audit.get("raw_output_sha256")
            != _c._bytes_sha256(raw_output.encode("utf-8"))
            or audit.get("input_tokens") != normalized_record.get("input_tokens")
            or audit.get("output_tokens") != normalized_record.get("output_tokens")
            or audit.get("estimated_cost") != normalized_record.get("actual_cost_usd")
        ):
            raise _c.CommandError(
                f"llm-unitize audit does not reproduce from journal: {candidate_id}"
            )
        prompt_commitments[candidate_id] = {
            "case_id": prompt_record["case_id"],
            "prompt_sha256": prompt_digest,
            "raw_output_sha256": audit["raw_output_sha256"],
            "prediction_units_sha256": _c._canonical_json_sha256(
                raw["prediction_units"]
            ),
            "provider_attempt_ordinal": row["attempt_ordinal"],
        }
    journal_queue_records = [
        queue_record
        for audit_record in audit_records
        for queue_record in journal_queue_by_candidate[
            _c._required_str(audit_record, "candidate_id")
        ]
    ]
    ordinary_journal_queue_records = [
        record
        for record in journal_queue_records
        if record.get("review_subject") != "candidate"
    ]
    terminal_journal_queue_records = [
        record
        for record in journal_queue_records
        if record.get("review_subject") == "candidate"
    ]
    if (
        queue_records != ordinary_journal_queue_records
        or terminal_queue_records != terminal_journal_queue_records
    ):
        raise _c.CommandError(
            "llm-unitize review queue does not reproduce from journal"
        )
    audit_queue_records = [
        *_c.unitization_review_queue_records(audit_records),
        *(
            queue
            for audit in audit_records
            for queue in cast(
                Sequence[Mapping[str, Any]],
                audit.get("unitizer_terminal_review_queue", ()),
            )
        ),
    ]
    ordinary_audit_queue_records = [
        record
        for record in audit_queue_records
        if record.get("review_subject") != "candidate"
    ]
    terminal_audit_queue_records = [
        record
        for record in audit_queue_records
        if record.get("review_subject") == "candidate"
    ]
    if (
        queue_records != ordinary_audit_queue_records
        or terminal_queue_records != terminal_audit_queue_records
    ):
        raise _c.CommandError("llm-unitize review queue does not reproduce from audit")
    return (
        prompt_commitments,
        _c._canonical_json_sha256(attempt_rows),
        tuple(dict(row) for row in attempt_rows),
    )


def stage_a_unitization_run_card_extra(
    *,
    lineage: StageAUnitizationLineage,
    markdown_root: Path,
    prediction_units_path: Path,
    audit_path: Path,
    review_queue_path: Path,
    terminal_review_queue_path: Path,
    provider_attempt_namespace: str | None = None,
    terminal_escalations: Mapping[
        str, tuple[LlmStageAUnitizerTerminalEscalation, Mapping[str, Any]]
    ]
    | None = None,
) -> JsonRecord:
    _c = _cli()
    # The explicit root is required to interpret relative parser-manifest paths.
    prompt_records = _c.stage_a_unitization_prompt_records(
        selection_records=lineage.selection_records,
        parser_records=lineage.parser_records,
        markdown_root=markdown_root,
        markdown_bytes=lineage.markdown_bytes,
        provider_attempt_namespace=provider_attempt_namespace,
    )
    prompt_commitments, attempts_sha256, _verified_rows = (
        verify_stage_a_provider_replay(
            lineage=lineage,
            prediction_units_path=prediction_units_path,
            audit_path=audit_path,
            review_queue_path=review_queue_path,
            terminal_review_queue_path=terminal_review_queue_path,
            provider_attempt_namespace=provider_attempt_namespace,
            terminal_escalations=terminal_escalations,
        )
    )
    # verify_stage_a_provider_replay reconstructs prompts independently. This
    # direct equality guard prevents a future root-derivation change from widening
    # the commitment.
    direct_prompt_commitments = {
        _c._required_str(record, "candidate_id"): _c._required_str(
            record, "prompt_sha256"
        )
        for record in prompt_records
    }
    if {
        candidate_id: _c._required_str(record, "prompt_sha256")
        for candidate_id, record in prompt_commitments.items()
    } != direct_prompt_commitments:
        raise _c.CommandError("llm-unitize prompt commitment reconstruction differs")
    model_execution: JsonRecord = {
        "model_key": lineage.registry_entry.registry_key,
        "model_entry_sha256": "sha256:"
        + _c.model_registry_entry_sha256(lineage.registry_entry),
        "model_registry_sha256": lineage.registry_sha256,
        "provider": lineage.registry_entry.provider,
        "provider_journal_schema_version": PROVIDER_JOURNAL_SCHEMA_VERSION,
        "provider_cycle_caps_sha256": lineage.provider_caps_sha256,
        "provider_cycle_caps_cycle_id": lineage.provider_caps.cycle_id,
        "provider_cycle_cap_usd": lineage.provider_caps.cap_usd(
            lineage.registry_entry.provider
        ),
        "provider_attempts_sha256": attempts_sha256,
    }
    if provider_attempt_namespace is not None:
        model_execution["provider_attempt_namespace"] = provider_attempt_namespace
    return {
        "lineage_schema_version": _c._STAGE_A_UNITIZATION_LINEAGE_SCHEMA_VERSION,
        "lineage_complete": True,
        "cohort_cycle_id": lineage.cohort_cycle_id,
        "lineage_roots": {
            "document_root": str(lineage.document_root.resolve()),
            "markdown_root": str(markdown_root.resolve()),
            "provider_journal": str(lineage.provider_journal_path.resolve()),
        },
        "input_commitments": dict(lineage.input_commitments),
        "model_execution": model_execution,
        "prompt_commitments": prompt_commitments,
        "unitizer_terminal_escalations": {
            candidate_id: {
                "terminal_escalation_sha256": escalation.escalation_sha256,
                "receipt": dict(receipt_commitment),
            }
            for candidate_id, (
                escalation,
                receipt_commitment,
            ) in sorted((terminal_escalations or {}).items())
        },
        "output_commitments": {
            "prediction_units": stage_a_file_commitment(prediction_units_path),
            "llm_unitization_audit": stage_a_file_commitment(audit_path),
            "unitization_review_queue": stage_a_file_commitment(review_queue_path),
            "unitizer_terminal_review_queue": stage_a_file_commitment(
                terminal_review_queue_path
            ),
        },
    }


def incomplete_stage_a_unitization_run_card_extra(
    *,
    lineage: StageAUnitizationLineage,
    markdown_root: Path,
    prediction_units_path: Path,
    audit_path: Path,
    review_queue_path: Path,
    terminal_review_queue_path: Path,
    provider_attempt_namespace: str | None = None,
    terminal_escalations: Mapping[
        str, tuple[LlmStageAUnitizerTerminalEscalation, Mapping[str, Any]]
    ]
    | None = None,
) -> JsonRecord:
    """Commit a resumable partial run without making it downstream-admissible."""
    _c = _cli()

    del terminal_escalations
    attempt_rows = tuple(
        row
        for row in stage_a_provider_attempt_rows(lineage.provider_journal_path)
        if row.get("logical_call_key")
        == ProviderCallIdentity(
            stage="llm-unitize",
            candidate_id=_c._required_str(row, "candidate_id"),
            model_key=_c._required_str(row, "model_key"),
            prompt=_c._required_str(row, "prompt_text"),
            model_registry_sha256=_c._required_str(row, "model_registry_sha256"),
            prompt_contract=provider_attempt_namespace,
        ).logical_call_key
    )
    model_execution: JsonRecord = {
        "model_key": lineage.registry_entry.registry_key,
        "model_entry_sha256": "sha256:"
        + _c.model_registry_entry_sha256(lineage.registry_entry),
        "model_registry_sha256": lineage.registry_sha256,
        "provider": lineage.registry_entry.provider,
        "provider_journal_schema_version": PROVIDER_JOURNAL_SCHEMA_VERSION,
        "provider_cycle_caps_sha256": lineage.provider_caps_sha256,
        "provider_cycle_caps_cycle_id": lineage.provider_caps.cycle_id,
        "provider_cycle_cap_usd": lineage.provider_caps.cap_usd(
            lineage.registry_entry.provider
        ),
        "provider_attempts_sha256": _c._canonical_json_sha256(attempt_rows),
    }
    if provider_attempt_namespace is not None:
        model_execution["provider_attempt_namespace"] = provider_attempt_namespace
    return {
        "lineage_schema_version": _c._STAGE_A_UNITIZATION_LINEAGE_SCHEMA_VERSION,
        "lineage_complete": False,
        "cohort_cycle_id": lineage.cohort_cycle_id,
        "lineage_roots": {
            "document_root": str(lineage.document_root.resolve()),
            "markdown_root": str(markdown_root.resolve()),
            "provider_journal": str(lineage.provider_journal_path.resolve()),
        },
        "input_commitments": dict(lineage.input_commitments),
        "model_execution": model_execution,
        "prompt_commitments": {},
        "output_commitments": {
            "prediction_units": stage_a_file_commitment(prediction_units_path),
            "llm_unitization_audit": stage_a_file_commitment(audit_path),
            "unitization_review_queue": stage_a_file_commitment(review_queue_path),
            "unitizer_terminal_review_queue": stage_a_file_commitment(
                terminal_review_queue_path
            ),
        },
    }


def stage_a_committed_path(commitments: Mapping[str, object], name: str) -> Path:
    _c = _cli()
    commitment = commitments.get(name)
    if not isinstance(commitment, Mapping):
        raise _c.CommandError(f"llm-unitize run card lacks {name} commitment")
    raw_path = cast(Mapping[str, object], commitment).get("path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise _c.CommandError(f"llm-unitize run card has invalid {name} path")
    return Path(raw_path)


def capture_stage_a_committed_file(
    commitments: Mapping[str, object], name: str
) -> tuple[Path, bytes]:
    """Capture a named Stage A source only when its exact commitment matches."""
    _c = _cli()

    commitment = commitments.get(name)
    if not isinstance(commitment, Mapping):
        raise _c.CommandError(f"Stage A run card lacks {name} commitment")
    expected = dict(cast(Mapping[str, object], commitment))
    path = stage_a_committed_path(commitments, name)
    payload = _c._read_singly_linked_regular_input(path, label=name.replace("_", " "))
    if stage_a_file_commitment(path, payload=payload) != expected:
        raise _c.CommandError(f"Stage A run card {name} commitment differs")
    return path, payload


def verify_stage_a_unitization_run_card(
    run_card_path: Path,
    *,
    expected_prediction_units_path: Path,
    expected_review_queue_path: Path | None = None,
    expected_audit_path: Path | None = None,
    controlled_private_root: Path | None = None,
    initialization_receipt_path: Path | None = None,
    captured_input_bytes: Mapping[str, bytes] | None = None,
    journal_snapshot: sqlite3.Connection | None = None,
) -> StageAUnitizationLineage:
    """Authenticate the executed llm-unitize run card and its Stage A lineage.

    ``captured_input_bytes`` binds this authentication to bytes the caller
    already captured, so a caller that commits those bytes downstream cannot
    authenticate a different byte set.
    """
    _c = _cli()

    if run_card_path.is_symlink() or not run_card_path.is_file():
        raise _c.CommandError(
            "authenticated llm-unitize run card is not a regular file"
        )
    card = stage_a_captured_json_object(
        run_card_path,
        label="llm-unitize run card",
        captured_input_bytes=captured_input_bytes,
    )
    if (
        card.get("schema_version")
        # contract-ratchet: allow moved CLI replay still matches the frozen run-card id.
        != "legalforecast.acquisition_run_card.v1"
        or card.get("stage") != "llm-unitize"
        or card.get("status") != "completed"
        or card.get("dry_run") is not False
        or card.get("execute") is not True
        or card.get("paid_activity_requested") is not True
        or card.get("paid_activity_executed") is not True
        or card.get("lineage_schema_version")
        != _c._STAGE_A_UNITIZATION_LINEAGE_SCHEMA_VERSION
        or card.get("lineage_complete") is not True
    ):
        raise _c.CommandError("invalid executed authenticated llm-unitize run card")
    inputs = card.get("input_commitments")
    outputs = card.get("output_commitments")
    roots = card.get("lineage_roots")
    execution = card.get("model_execution")
    if not all(
        isinstance(value, Mapping) for value in (inputs, outputs, roots, execution)
    ):
        raise _c.CommandError("llm-unitize run card lacks exact lineage commitments")
    input_records = cast(Mapping[str, object], inputs)
    output_records = cast(Mapping[str, object], outputs)
    root_records = cast(Mapping[str, object], roots)
    execution_record = cast(Mapping[str, object], execution)
    model_key = execution_record.get("model_key")
    if not isinstance(model_key, str) or not model_key.strip():
        raise _c.CommandError("llm-unitize run card lacks model key")
    provider_attempt_namespace_value = execution_record.get(
        "provider_attempt_namespace"
    )
    if provider_attempt_namespace_value is not None and not isinstance(
        provider_attempt_namespace_value, str
    ):
        raise _c.CommandError("llm-unitize provider attempt namespace is invalid")
    provider_attempt_namespace = provider_attempt_namespace_value
    try:
        _c.stage_a_provider_attempt_stage("llm-unitize", provider_attempt_namespace)
    except LlmPipelineError as exc:
        raise _c.CommandError(str(exc)) from exc
    document_root = root_records.get("document_root")
    markdown_root = root_records.get("markdown_root")
    provider_journal = root_records.get("provider_journal")
    if not all(
        isinstance(value, str) and value.strip()
        for value in (document_root, markdown_root, provider_journal)
    ):
        raise _c.CommandError("llm-unitize run card has invalid lineage roots")
    replay_inputs = StageALineageInputs(
        selection=stage_a_committed_path(input_records, "selection"),
        selection_run_card=stage_a_committed_path(input_records, "selection_run_card"),
        download_manifest=stage_a_committed_path(input_records, "download_manifest"),
        disclosure_clearance=stage_a_committed_path(
            input_records, "disclosure_clearance"
        ),
        materialization_run_card=stage_a_committed_path(
            input_records, "materialization_run_card"
        ),
        document_root=Path(cast(str, document_root)),
        parse_requests=stage_a_committed_path(input_records, "parse_requests"),
        parser_manifest=stage_a_committed_path(input_records, "parser_manifest"),
        parser_run_card=stage_a_committed_path(input_records, "parser_run_card"),
        model_registry=stage_a_committed_path(input_records, "model_registry"),
        model_key=model_key,
        provider_cycle_caps=stage_a_committed_path(
            input_records, "provider_cycle_caps"
        ),
        provider_journal=Path(cast(str, provider_journal)),
        controlled_private_root=controlled_private_root,
        purchase_ledger_initialization_receipt=initialization_receipt_path,
    )
    lineage = _c._verify_stage_a_unitization_lineage(
        _c.argparse.Namespace(
            selection=replay_inputs.selection,
            selection_run_card=replay_inputs.selection_run_card,
            download_manifest=replay_inputs.download_manifest,
            disclosure_clearance=replay_inputs.disclosure_clearance,
            materialization_run_card=replay_inputs.materialization_run_card,
            document_root=replay_inputs.document_root,
            parse_requests=replay_inputs.parse_requests,
            parser_manifest=replay_inputs.parser_manifest,
            parser_run_card=replay_inputs.parser_run_card,
            model_registry=replay_inputs.model_registry,
            model_key=replay_inputs.model_key,
            provider_cycle_caps=replay_inputs.provider_cycle_caps,
            provider_journal=replay_inputs.provider_journal,
            controlled_private_root=replay_inputs.controlled_private_root,
            purchase_ledger_initialization_receipt=(
                replay_inputs.purchase_ledger_initialization_receipt
            ),
        ),
        markdown_root=Path(cast(str, markdown_root)),
    )
    if dict(lineage.input_commitments) != dict(input_records):
        raise _c.CommandError("llm-unitize authenticated input commitments changed")
    if card.get("cohort_cycle_id") != lineage.cohort_cycle_id:
        raise _c.CommandError("llm-unitize cohort cycle commitment changed")
    raw_path = stage_a_committed_path(output_records, "prediction_units")
    audit_path = stage_a_committed_path(output_records, "llm_unitization_audit")
    queue_path = stage_a_committed_path(output_records, "unitization_review_queue")
    has_terminal_queue = "unitizer_terminal_review_queue" in output_records
    terminal_queue_path = (
        stage_a_committed_path(output_records, "unitizer_terminal_review_queue")
        if has_terminal_queue
        else None
    )
    if (
        raw_path.resolve() != expected_prediction_units_path.resolve()
        or (
            expected_review_queue_path is not None
            and queue_path.resolve() != expected_review_queue_path.resolve()
        )
        or (
            expected_audit_path is not None
            and audit_path.resolve() != expected_audit_path.resolve()
        )
    ):
        raise _c.CommandError("llm-unitize downstream artifact path differs")
    expected_outputs = {
        "prediction_units": stage_a_file_commitment(
            raw_path,
            payload=stage_a_captured_payload(
                raw_path, captured_input_bytes=captured_input_bytes
            ),
        ),
        "llm_unitization_audit": stage_a_file_commitment(audit_path),
        "unitization_review_queue": stage_a_file_commitment(
            queue_path,
            payload=stage_a_captured_payload(
                queue_path, captured_input_bytes=captured_input_bytes
            ),
        ),
        **(
            {
                "unitizer_terminal_review_queue": stage_a_file_commitment(
                    terminal_queue_path,
                    payload=stage_a_captured_payload(
                        terminal_queue_path,
                        captured_input_bytes=captured_input_bytes,
                    ),
                )
            }
            if terminal_queue_path is not None
            else {}
        ),
    }
    if dict(output_records) != expected_outputs:
        raise _c.CommandError("llm-unitize output commitment changed")
    raw_terminal_commitments = card.get("unitizer_terminal_escalations", {})
    if not isinstance(raw_terminal_commitments, Mapping):
        raise _c.CommandError("llm-unitize terminal escalation commitments are invalid")
    terminal_receipt_paths: list[Path] = []
    for value in cast(Mapping[str, object], raw_terminal_commitments).values():
        if not isinstance(value, Mapping):
            raise _c.CommandError(
                "llm-unitize terminal escalation commitment is invalid"
            )
        receipt_value: object = cast(Mapping[str, object], value).get("receipt")
        if not isinstance(receipt_value, Mapping):
            raise _c.CommandError("llm-unitize terminal receipt commitment is invalid")
        receipt: Mapping[str, object] = cast(Mapping[str, object], receipt_value)
        receipt_commitments: Mapping[str, object] = {"receipt": receipt}
        terminal_receipt_paths.append(
            stage_a_committed_path(receipt_commitments, "receipt")
        )
    terminal_escalations = _c._verified_stage_a_unitizer_terminal_escalations(
        receipt_paths=terminal_receipt_paths,
        lineage=lineage,
        markdown_root=lineage.markdown_root,
        provider_attempt_namespace=provider_attempt_namespace,
    )
    expected_terminal_commitments = {
        candidate_id: {
            "terminal_escalation_sha256": escalation.escalation_sha256,
            "receipt": dict(receipt_commitment),
        }
        for candidate_id, (
            escalation,
            receipt_commitment,
        ) in sorted(terminal_escalations.items())
    }
    if dict(cast(Mapping[str, object], raw_terminal_commitments)) != (
        expected_terminal_commitments
    ):
        raise _c.CommandError("llm-unitize terminal escalation commitment changed")
    if terminal_escalations and terminal_queue_path is None:
        raise _c.CommandError("llm-unitize terminal review queue is missing")
    expected_terminal_queue = [
        queue
        for audit in stage_a_captured_records(
            audit_path,
            label="llm-unitization audit",
            captured_input_bytes=captured_input_bytes,
        )
        for queue in cast(
            Sequence[Mapping[str, Any]],
            audit.get("unitizer_terminal_review_queue", ()),
        )
    ]
    if (
        stage_a_captured_records(
            terminal_queue_path,
            label="unitizer terminal review queue",
            captured_input_bytes=captured_input_bytes,
        )
        if terminal_queue_path is not None
        else []
    ) != expected_terminal_queue:
        raise _c.CommandError("llm-unitize terminal review queue changed")
    prompt_commitments, attempts_sha256, verified_attempt_rows = (
        verify_stage_a_provider_replay(
            lineage=lineage,
            prediction_units_path=raw_path,
            audit_path=audit_path,
            review_queue_path=queue_path,
            terminal_review_queue_path=terminal_queue_path,
            provider_attempt_namespace=provider_attempt_namespace,
            captured_input_bytes=captured_input_bytes,
            journal_snapshot=journal_snapshot,
            terminal_escalations=terminal_escalations,
        )
    )
    if card.get("prompt_commitments") != prompt_commitments:
        raise _c.CommandError("llm-unitize prompt or output commitment changed")
    expected_execution = {
        "model_key": lineage.registry_entry.registry_key,
        "model_entry_sha256": "sha256:"
        + _c.model_registry_entry_sha256(lineage.registry_entry),
        "model_registry_sha256": lineage.registry_sha256,
        "provider": lineage.registry_entry.provider,
        "provider_journal_schema_version": PROVIDER_JOURNAL_SCHEMA_VERSION,
        "provider_cycle_caps_sha256": lineage.provider_caps_sha256,
        "provider_cycle_caps_cycle_id": lineage.provider_caps.cycle_id,
        "provider_cycle_cap_usd": lineage.provider_caps.cap_usd(
            lineage.registry_entry.provider
        ),
        "provider_attempts_sha256": attempts_sha256,
    }
    if provider_attempt_namespace is not None:
        expected_execution["provider_attempt_namespace"] = provider_attempt_namespace
    if dict(execution_record) != expected_execution:
        raise _c.CommandError("llm-unitize model/provider execution commitment changed")
    raw_input_paths = card.get("input_paths")
    raw_output_paths = card.get("output_paths")
    if not isinstance(raw_input_paths, Sequence) or isinstance(
        raw_input_paths, (str, bytes)
    ):
        raise _c.CommandError("llm-unitize run card lacks exact input paths")
    if not isinstance(raw_output_paths, Sequence) or isinstance(
        raw_output_paths, (str, bytes)
    ):
        raise _c.CommandError("llm-unitize run card lacks exact output paths")
    typed_input_paths = cast(Sequence[object], raw_input_paths)
    typed_output_paths = cast(Sequence[object], raw_output_paths)
    if tuple(Path(str(path)).resolve() for path in typed_input_paths) != tuple(
        path.resolve()
        for path in (
            *lineage.input_paths,
            *sorted(
                terminal_receipt_paths,
                key=lambda path: str(path.resolve()),
            ),
        )
    ):
        raise _c.CommandError("llm-unitize input path lineage changed")
    if tuple(Path(str(path)).resolve() for path in typed_output_paths) != (
        raw_path.resolve(),
        audit_path.resolve(),
        queue_path.resolve(),
        *((terminal_queue_path.resolve(),) if terminal_queue_path is not None else ()),
        lineage.provider_journal_path.resolve(),
    ):
        raise _c.CommandError("llm-unitize output paths changed")
    if card.get("record_count") != len(lineage.selection_records):
        raise _c.CommandError("llm-unitize record count changed")
    return replace(
        lineage,
        verified_provider_attempt_rows=verified_attempt_rows,
        unitizer_terminal_escalations=terminal_escalations,
    )


def verify_stage_a_source_authority(
    lineage: StageAUnitizationLineage,
    *,
    expected_selection_path: Path | None,
    expected_parser_manifest_path: Path | None,
    expected_markdown_root: Path | None,
) -> None:
    """Bind every downstream Stage A consumer to unitizer-authenticated sources."""
    _c = _cli()

    expected_files = {
        "selection": expected_selection_path,
        "parser_manifest": expected_parser_manifest_path,
    }
    for name, path in expected_files.items():
        if path is None:
            continue
        committed = lineage.input_commitments.get(name)
        if committed != stage_a_file_commitment(path):
            raise _c.CommandError(
                f"downstream {name} differs from authenticated Stage A"
            )
    if (
        expected_markdown_root is not None
        and expected_markdown_root.resolve() != lineage.markdown_root.resolve()
    ):
        raise _c.CommandError(
            "downstream Markdown root differs from authenticated Stage A"
        )


def verify_stage_a_review_run_card(
    run_card_path: Path,
    *,
    lineage: StageAUnitizationLineage,
    llm_unitization_run_card_path: Path,
    expected_review_queue_path: Path,
    expected_structural_flags_path: Path | None = None,
    expected_audit_path: Path | None = None,
    expected_registry_path: Path | None = None,
    expected_model_key: str | None = None,
    captured_input_bytes: Mapping[str, bytes] | None = None,
) -> None:
    """Authenticate the executed structural-review run card against Stage A.

    ``captured_input_bytes`` binds this authentication to bytes the caller
    already captured, so a caller that commits those bytes downstream cannot
    authenticate a different byte set.
    """
    _c = _cli()

    if run_card_path.is_symlink() or not run_card_path.is_file():
        raise _c.CommandError("llm-review-stage-a run card is not a regular file")
    card = stage_a_captured_json_object(
        run_card_path,
        label="structural-review run card",
        captured_input_bytes=captured_input_bytes,
    )
    if (
        card.get("schema_version")
        # contract-ratchet: allow moved CLI replay still matches the frozen run-card id.
        != "legalforecast.acquisition_run_card.v1"
        or card.get("stage") != "llm-review-stage-a"
        or card.get("status") != "completed"
        or card.get("dry_run") is not False
        or card.get("execute") is not True
        or card.get("paid_activity_requested") is not True
        or card.get("paid_activity_executed") is not True
    ):
        raise _c.CommandError("invalid authenticated llm-review-stage-a run card")
    source = card.get("source_commitments")
    outputs = card.get("output_commitments")
    execution = card.get("model_execution")
    chain = card.get("provider_chain")
    if not all(
        isinstance(value, Mapping) for value in (source, outputs, execution, chain)
    ):
        raise _c.CommandError("llm-review-stage-a run card lacks exact commitments")
    source_records = cast(Mapping[str, object], source)
    output_records = cast(Mapping[str, object], outputs)
    execution_record = cast(Mapping[str, object], execution)
    chain_record = cast(Mapping[str, object], chain)
    unit_card = stage_a_committed_path(source_records, "llm_unitization_run_card")
    if (
        unit_card.resolve() != llm_unitization_run_card_path.resolve()
        or source_records.get("llm_unitization_run_card")
        != stage_a_file_commitment(
            llm_unitization_run_card_path,
            payload=stage_a_captured_payload(
                llm_unitization_run_card_path,
                captured_input_bytes=captured_input_bytes,
            ),
        )
    ):
        raise _c.CommandError("structural review Stage A run-card lineage differs")
    unit_card_record = stage_a_captured_json_object(
        llm_unitization_run_card_path,
        label="llm-unitize run card",
        captured_input_bytes=captured_input_bytes,
    )
    unit_outputs = unit_card_record.get("output_commitments")
    if not isinstance(unit_outputs, Mapping):
        raise _c.CommandError("structural review unitizer outputs are missing")
    expected_stage_a_sources = {
        "selection": lineage.input_commitments.get("selection"),
        "parser_manifest": lineage.input_commitments.get("parser_manifest"),
        "raw_prediction_units": cast(Mapping[str, object], unit_outputs).get(
            "prediction_units"
        ),
        "unitization_review_queue": cast(Mapping[str, object], unit_outputs).get(
            "unitization_review_queue"
        ),
    }
    if any(
        source_records.get(name) != commitment
        for name, commitment in expected_stage_a_sources.items()
    ):
        raise _c.CommandError("structural review source lineage differs from Stage A")
    expected_caps_commitment = lineage.input_commitments.get("provider_cycle_caps")
    review_caps_commitment = source_records.get("provider_cycle_caps")
    if (
        not isinstance(expected_caps_commitment, Mapping)
        or not isinstance(review_caps_commitment, Mapping)
        or cast(Mapping[str, object], review_caps_commitment).get("sha256")
        != cast(Mapping[str, object], expected_caps_commitment).get("sha256")
    ):
        raise _c.CommandError("structural review source lineage differs from Stage A")
    for name in (
        "selection",
        "parser_manifest",
        "raw_prediction_units",
        "unitization_review_queue",
        "model_registry",
        "provider_cycle_caps",
    ):
        path = stage_a_committed_path(source_records, name)
        if source_records.get(name) != stage_a_file_commitment(
            path,
            payload=stage_a_captured_payload(
                path, captured_input_bytes=captured_input_bytes
            ),
        ):
            raise _c.CommandError(f"structural review {name} commitment changed")
    caps_path = stage_a_committed_path(source_records, "provider_cycle_caps")
    if (
        not _c._path_matches_sha256(caps_path, lineage.provider_caps_sha256)
        or chain_record.get("schema_version") != PROVIDER_JOURNAL_SCHEMA_VERSION
        or chain_record.get("cycle_id") != lineage.cohort_cycle_id
        or chain_record.get("provider_cycle_caps_sha256")
        != lineage.provider_caps_sha256
        or chain_record.get("provider_journal")
        != str(lineage.provider_journal_path.resolve())
    ):
        raise _c.CommandError("structural review provider chain identity differs")
    queue_path = stage_a_committed_path(output_records, "review_queue")
    audit_path = stage_a_committed_path(output_records, "audit")
    flags_path = stage_a_committed_path(output_records, "structural_flags")
    if (
        queue_path.resolve() != expected_review_queue_path.resolve()
        or (
            expected_structural_flags_path is not None
            and flags_path.resolve() != expected_structural_flags_path.resolve()
        )
        or (
            expected_audit_path is not None
            and audit_path.resolve() != expected_audit_path.resolve()
        )
    ):
        raise _c.CommandError("structural review output path differs")
    expected_outputs = {
        "structural_flags": stage_a_file_commitment(flags_path),
        "review_queue": stage_a_file_commitment(
            queue_path,
            payload=stage_a_captured_payload(
                queue_path, captured_input_bytes=captured_input_bytes
            ),
        ),
        "audit": stage_a_file_commitment(audit_path),
    }
    if dict(output_records) != expected_outputs:
        raise _c.CommandError("structural review output commitment changed")
    registry_path = stage_a_committed_path(source_records, "model_registry")
    model_key = execution_record.get("model_key")
    if not isinstance(model_key, str) or not model_key.strip():
        raise _c.CommandError("structural review model key is invalid")
    if (
        expected_registry_path is not None
        and registry_path.resolve() != expected_registry_path.resolve()
    ) or (expected_model_key is not None and model_key != expected_model_key):
        raise _c.CommandError("structural review model authority differs")
    entry, registry_sha = _c._registry_entry_for_key(registry_path, model_key)
    provider_attempt_namespace_value = execution_record.get(
        "provider_attempt_namespace"
    )
    if provider_attempt_namespace_value is not None and not isinstance(
        provider_attempt_namespace_value, str
    ):
        raise _c.CommandError("structural review provider attempt namespace is invalid")
    provider_attempt_namespace = provider_attempt_namespace_value
    unitization_namespace = (
        _c._stage_a_provider_attempt_namespace_from_unitization_card_record(
            unit_card_record
        )
    )
    _c._require_stage_a_structural_review_namespace_pair(
        unitization_namespace=unitization_namespace,
        review_namespace=provider_attempt_namespace,
    )
    expected_execution = {
        "model_key": entry.registry_key,
        "model_entry_sha256": "sha256:" + _c.model_registry_entry_sha256(entry),
        "model_registry_sha256": registry_sha,
        "provider": entry.provider,
    }
    if provider_attempt_namespace is not None:
        expected_execution["provider_attempt_namespace"] = provider_attempt_namespace
    if dict(execution_record) != expected_execution:
        raise _c.CommandError("structural review model execution commitment changed")
    selection_path = stage_a_committed_path(source_records, "selection")
    parser_path = stage_a_committed_path(source_records, "parser_manifest")
    raw_units_path = stage_a_committed_path(source_records, "raw_prediction_units")
    original_queue_path = stage_a_committed_path(
        source_records, "unitization_review_queue"
    )
    captured_raw_records = stage_a_captured_records(
        raw_units_path,
        label="raw prediction units",
        captured_input_bytes=captured_input_bytes,
    )
    unitizer_terminal_candidates = set(
        getattr(lineage, "unitizer_terminal_escalations", None) or {}
    )
    structural_selections = tuple(
        record
        for record in _c._read_records(selection_path)
        if _c._required_str(record, "candidate_id") not in unitizer_terminal_candidates
    )
    try:
        prompt_records = _c.stage_a_structural_review_prompt_records(
            selection_records=structural_selections,
            parser_records=_c._read_records(parser_path),
            prediction_unit_records=captured_raw_records,
            markdown_root=lineage.markdown_root,
            provider_attempt_namespace=provider_attempt_namespace,
        )
    except (OSError, UnicodeError, ValueError) as exc:
        raise _c.CommandError(
            f"cannot reconstruct structural-review prompts: {exc}"
        ) from exc
    expected_prompts = {
        (
            _c._required_str(record, "candidate_id"),
            entry.registry_key,
        ): _c._required_str(record, "prompt_sha256")
        for record in prompt_records
    }
    raw_records = captured_raw_records
    raw_by_candidate = {
        _c._required_str(record, "candidate_id"): record for record in raw_records
    }
    selection_by_candidate = {
        _c._required_str(record, "candidate_id"): record
        for record in lineage.selection_records
    }
    if len(selection_by_candidate) != len(lineage.selection_records):
        raise _c.CommandError(
            "structural review selection contains duplicate candidates"
        )
    audit_records = stage_a_captured_records(
        audit_path,
        label="llm-unitization audit",
        captured_input_bytes=captured_input_bytes,
    )
    audit_by_candidate = {
        _c._required_str(record, "candidate_id"): record for record in audit_records
    }
    if len(raw_by_candidate) != len(raw_records) or len(audit_by_candidate) != len(
        audit_records
    ):
        raise _c.CommandError("structural review contains duplicate candidate records")
    for candidate_id in unitizer_terminal_candidates:
        raw = raw_by_candidate.get(candidate_id)
        audit = audit_by_candidate.get(candidate_id)
        selection = selection_by_candidate[candidate_id]
        try:
            _c.validate_unitizer_terminal_preserved_audit_record(
                audit or {},
                candidate_id=candidate_id,
                case_id=_c._required_str(selection, "case_id"),
                reviewer_model_key=entry.registry_key,
                model_registry_sha256=registry_sha,
                raw_prediction_units=raw or {},
            )
        except LlmPipelineError as exc:
            raise _c.CommandError(str(exc)) from exc
    terminal_receipt_paths: list[Path] = []
    terminal_attempt_counts: dict[tuple[str, str], int] = {}
    for candidate_id, audit in audit_by_candidate.items():
        if audit.get("status") != "terminal_escalation":
            continue
        if audit.get("model_key") != entry.registry_key:
            raise _c.CommandError("structural review terminal escalation model differs")
        receipt = audit.get("terminal_escalation_receipt")
        if not isinstance(receipt, Mapping):
            raise _c.CommandError(
                "structural review terminal escalation receipt is invalid"
            )
        receipt_path = stage_a_committed_path(
            {"receipt": cast(Mapping[str, object], receipt)}, "receipt"
        )
        if receipt != stage_a_file_commitment(receipt_path):
            raise _c.CommandError(
                "structural review terminal escalation receipt changed"
            )
        terminal = audit.get("terminal_escalation")
        if not isinstance(terminal, Mapping):
            raise _c.CommandError("structural review terminal escalation is invalid")
        failed_attempts: object = cast(Mapping[str, object], terminal).get(
            "failed_attempts"
        )
        if not isinstance(failed_attempts, Sequence) or isinstance(
            failed_attempts, (str, bytes)
        ):
            raise _c.CommandError("structural review terminal attempts are invalid")
        terminal_receipt_paths.append(receipt_path)
        terminal_attempt_counts[(candidate_id, entry.registry_key)] = len(
            cast(Sequence[object], failed_attempts)
        )
    if len(set(terminal_receipt_paths)) != len(terminal_receipt_paths):
        raise _c.CommandError(
            "structural review terminal escalation receipts duplicate"
        )
    terminal_escalations = _c._verified_stage_a_terminal_escalations(
        receipt_paths=tuple(terminal_receipt_paths),
        lineage=lineage,
        prediction_units_path=raw_units_path,
        markdown_root=lineage.markdown_root,
        registry_entry=entry,
        registry_sha256=registry_sha,
        provider_attempt_namespace=provider_attempt_namespace,
        captured_input_bytes=captured_input_bytes,
    )
    if set(terminal_escalations) != {
        candidate_id
        for candidate_id, audit in audit_by_candidate.items()
        if audit.get("status") == "terminal_escalation"
    }:
        raise _c.CommandError("structural review terminal escalation coverage differs")
    # Both structural-review journal reads share one query-only snapshot, so
    # the committed attempt digest and the replayed rows describe one state.
    try:
        journal_snapshot = _c.open_provider_journal_snapshot(
            lineage.provider_journal_path
        )
    except ProviderJournalError as exc:
        raise _c.CommandError(str(exc)) from exc
    try:
        stage_attempts = _c._verified_provider_stage_attempts(
            stage="llm-review-stage-a",
            journal_path=lineage.provider_journal_path,
            expected_prompts=expected_prompts,
            providers_by_model={entry.registry_key: entry.provider},
            model_registry_sha256=registry_sha,
            expected_nonsettled_statuses={
                key: "reconstruction_failed" for key in terminal_attempt_counts
            },
            expected_nonsettled_attempt_counts=terminal_attempt_counts,
            active_candidate_ids={
                _c._required_str(record, "candidate_id")
                for record in structural_selections
            },
            provider_attempt_namespace=provider_attempt_namespace,
            snapshot=journal_snapshot,
        )
        attempt_rows = _c._provider_stage_attempt_rows(
            lineage.provider_journal_path,
            stage="llm-review-stage-a",
            snapshot=journal_snapshot,
        )
    finally:
        journal_snapshot.close()
    if chain_record.get("stage_attempts") != stage_attempts:
        raise _c.CommandError("structural review provider attempts changed")
    settled_by_candidate: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in attempt_rows:
        candidate_id = _c._required_str(row, "candidate_id")
        expected_key = ProviderCallIdentity(
            stage="llm-review-stage-a",
            candidate_id=candidate_id,
            model_key=_c._required_str(row, "model_key"),
            prompt=_c._required_str(row, "prompt_text"),
            model_registry_sha256=_c._required_str(row, "model_registry_sha256"),
            prompt_contract=provider_attempt_namespace,
        ).logical_call_key
        if row.get("logical_call_key") != expected_key:
            continue
        if row.get("status") == "settled":
            settled_by_candidate[_c._required_str(row, "candidate_id")].append(row)
    reconstructed_flags: list[JsonRecord] = []
    terminal_queue_records: list[JsonRecord] = []
    prompt_by_candidate = {
        _c._required_str(record, "candidate_id"): record for record in prompt_records
    }
    if (
        set(raw_by_candidate) != set(prompt_by_candidate) | unitizer_terminal_candidates
        or set(audit_by_candidate)
        != set(prompt_by_candidate) | unitizer_terminal_candidates
    ):
        raise _c.CommandError("structural review candidate coverage differs")
    for candidate_id, prompt_record in prompt_by_candidate.items():
        terminal = terminal_escalations.get(candidate_id)
        if terminal is not None:
            escalation, receipt_commitment = terminal
            expected_audit = _c.structural_review_terminal_escalation_audit_record(
                escalation,
                receipt_commitment=receipt_commitment,
            )
            if audit_by_candidate[candidate_id] != expected_audit:
                raise _c.CommandError(
                    f"structural review terminal escalation is invalid: {candidate_id}"
                )
            terminal_queue_records.extend(
                _c.structural_review_terminal_escalation_queue_records(
                    escalation,
                    receipt_commitment=receipt_commitment,
                )
            )
            continue
        rows = settled_by_candidate.get(candidate_id, [])
        if len(rows) != 1:
            raise _c.CommandError(
                f"structural review requires one settled reconstruction: {candidate_id}"
            )
        row = rows[0]
        normalized_response_json = _c._required_str(row, "normalized_response_json")
        try:
            normalized_value: object = _c.json.loads(normalized_response_json)
            reconstructed_value: object = _c.json.loads(
                _c._required_str(row, "reconstructed_result_json")
            )
        except (_c.json.JSONDecodeError, ValueError) as exc:
            raise _c.CommandError(
                f"structural review journal reconstruction is invalid: {candidate_id}"
            ) from exc
        if not isinstance(normalized_value, Mapping) or not isinstance(
            reconstructed_value, Mapping
        ):
            raise _c.CommandError(
                f"structural review journal reconstruction is invalid: {candidate_id}"
            )
        normalized = cast(Mapping[str, object], normalized_value)
        reconstructed = cast(Mapping[str, object], reconstructed_value)
        flags: object = reconstructed.get("structural_flags")
        if (
            not isinstance(flags, Sequence)
            or isinstance(flags, (str, bytes))
            or not all(
                isinstance(flag, Mapping) for flag in cast(Sequence[object], flags)
            )
        ):
            raise _c.CommandError(
                f"structural review journal flags are invalid: {candidate_id}"
            )
        if provider_attempt_namespace == STAGE_A_CLAIM_ONTOLOGY_V4_PROMPT_CONTRACT:
            try:
                replayed_flags = _c.reconstruct_stage_a_structural_review_response(
                    selection_record=selection_by_candidate[candidate_id],
                    parser_records=lineage.parser_records,
                    prediction_unit_records=raw_records,
                    markdown_root=lineage.markdown_root,
                    markdown_bytes=lineage.markdown_bytes,
                    normalized_response_json=normalized_response_json,
                )
            except (
                KeyError,
                LlmPipelineError,
                OSError,
                UnicodeError,
                ValueError,
            ) as exc:
                raise _c.CommandError(
                    "structural review raw response does not reconstruct from "
                    f"authenticated v4 inputs: {candidate_id}: {exc}"
                ) from exc
            stored_flags = [
                dict(cast(Mapping[str, Any], flag))
                for flag in cast(Sequence[object], flags)
            ]
            if list(replayed_flags) != stored_flags:
                raise _c.CommandError(
                    "structural review raw response differs from journaled "
                    f"reconstruction: {candidate_id}"
                )
        raw_record = raw_by_candidate[candidate_id]
        raw_sha = _c.canonical_sha256(raw_record)
        candidate_flags = list(
            _c.stage_a_structural_flag_records(
                candidate_id=candidate_id,
                case_id=_c._required_str(prompt_record, "case_id"),
                reviewer_model_key=entry.registry_key,
                model_registry_sha256=registry_sha,
                raw_prediction_units_sha256=raw_sha,
                structural_flags=cast(Sequence[Mapping[str, Any]], flags),
            )
        )
        audit = audit_by_candidate[candidate_id]
        raw_output: object = normalized.get("raw_output")
        if not isinstance(raw_output, str) or any(
            (
                audit.get("status")
                != ("flags_pending" if candidate_flags else "passed"),
                audit.get("case_id") != prompt_record.get("case_id"),
                audit.get("model_key") != entry.registry_key,
                audit.get("model_registry_sha256") != registry_sha,
                audit.get("raw_prediction_units_sha256") != raw_sha,
                audit.get("prompt_sha256") != prompt_record.get("prompt_sha256"),
                audit.get("structural_flags_sha256")
                != _c.canonical_records_sha256(candidate_flags),
                audit.get("flag_count") != len(candidate_flags),
                audit.get("input_tokens") != normalized.get("input_tokens"),
                audit.get("output_tokens") != normalized.get("output_tokens"),
                audit.get("estimated_cost") != normalized.get("actual_cost_usd"),
                audit.get("raw_output_sha256")
                != _c._bytes_sha256(raw_output.encode("utf-8")),
            )
        ):
            raise _c.CommandError(
                f"structural review audit does not reproduce from journal: "
                f"{candidate_id}"
            )
        reconstructed_flags.extend(candidate_flags)
    if _c._read_records(flags_path) != reconstructed_flags:
        raise _c.CommandError("structural review flags do not reproduce from journal")
    expected_queue = list(
        _c.merge_stage_a_review_queue(
            _c._read_records(original_queue_path),
            reconstructed_flags,
            terminal_queue_records,
        )
    )
    if (
        stage_a_captured_records(
            queue_path,
            label="merged unitization review queue",
            captured_input_bytes=captured_input_bytes,
        )
        != expected_queue
    ):
        raise _c.CommandError("structural review queue does not reproduce from journal")
    raw_inputs = card.get("input_paths")
    raw_outputs = card.get("output_paths")
    if not isinstance(raw_inputs, Sequence) or isinstance(raw_inputs, (str, bytes)):
        raise _c.CommandError("structural review run card lacks exact inputs")
    if not isinstance(raw_outputs, Sequence) or isinstance(raw_outputs, (str, bytes)):
        raise _c.CommandError("structural review run card lacks exact outputs")
    expected_inputs = (
        *(
            stage_a_committed_path(source_records, name).resolve()
            for name in (
                "selection",
                "parser_manifest",
                "raw_prediction_units",
                "unitization_review_queue",
                "llm_unitization_run_card",
                "model_registry",
                "provider_cycle_caps",
            )
        ),
        lineage.provider_journal_path.resolve(),
        *(sorted((path.resolve() for path in terminal_receipt_paths), key=str)),
    )
    if (
        tuple(Path(str(path)).resolve() for path in cast(Sequence[object], raw_inputs))
        != expected_inputs
    ):
        raise _c.CommandError("structural review input paths changed")
    if tuple(
        Path(str(path)).resolve() for path in cast(Sequence[object], raw_outputs)
    ) != (
        flags_path.resolve(),
        queue_path.resolve(),
        audit_path.resolve(),
        lineage.provider_journal_path.resolve(),
    ):
        raise _c.CommandError("structural review output paths changed")


@dataclass(frozen=True, slots=True)
class StageAReplay:
    raw_prediction_unit_records: tuple[JsonRecord, ...]
    unitization_audit_records: tuple[JsonRecord, ...]
    original_review_records: tuple[JsonRecord, ...]
    structural_flag_records: tuple[JsonRecord, ...]
    structural_review_audit_records: tuple[JsonRecord, ...]
    merged_review_records: tuple[JsonRecord, ...]
    adjudication_records: tuple[JsonRecord, ...]
    terminal_review_records: tuple[JsonRecord, ...] = ()
    terminal_escalation_records: tuple[JsonRecord, ...] = ()
    terminal_adjudication_records: tuple[JsonRecord, ...] = ()
    terminal_review_path: Path | None = None
    terminal_review_payload: bytes | None = None
    terminal_adjudications_path: Path | None = None
    terminal_adjudications_payload: bytes | None = None


def verify_stage_a_packet_authority(
    *,
    selection_records: Sequence[Mapping[str, Any]],
    parser_records: Sequence[Mapping[str, Any]],
    raw_prediction_units_path: Path,
    unitization_audit_path: Path,
    unitization_run_card_path: Path,
    unitization_provider_journal_path: Path,
    original_review_path: Path,
    structural_flags_path: Path,
    structural_review_audit_path: Path,
    structural_review_run_card_path: Path,
    structural_review_provider_journal_path: Path,
    structural_review_registry_path: Path,
    structural_review_model_key: str,
    merged_review_path: Path,
    finalized_prediction_unit_records: Sequence[Mapping[str, Any]],
    finalized_prediction_units_path: Path,
    adjudications_path: Path,
    apply_unitization_run_card_path: Path,
    controlled_private_root: Path | None,
    initialization_receipt_path: Path | None,
) -> StageAReplay:
    """Authenticate finalized Stage A units before packet bytes are emitted."""
    _c = _cli()

    unitization_card = _c._read_json_object(unitization_run_card_path)
    if (
        unitization_card.get("lineage_schema_version")
        == _c._STAGE_A_UNITIZATION_LINEAGE_SCHEMA_VERSION
    ):
        lineage = verify_stage_a_unitization_run_card(
            unitization_run_card_path,
            expected_prediction_units_path=raw_prediction_units_path,
            expected_review_queue_path=original_review_path,
            expected_audit_path=unitization_audit_path,
            controlled_private_root=controlled_private_root,
            initialization_receipt_path=initialization_receipt_path,
        )
        if tuple(lineage.selection_records) != tuple(selection_records):
            raise _c.CommandError("llm-unitize selection differs from packet selection")
        if tuple(lineage.parser_records) != tuple(parser_records):
            raise _c.CommandError(
                "llm-unitize parser manifest differs from packet parser authority"
            )
        if (
            unitization_provider_journal_path.resolve()
            != lineage.provider_journal_path.resolve()
            or structural_review_provider_journal_path.resolve()
            != lineage.provider_journal_path.resolve()
        ):
            raise _c.CommandError("Stage A packet provider journal authority differs")
        verify_stage_a_review_run_card(
            structural_review_run_card_path,
            lineage=lineage,
            llm_unitization_run_card_path=unitization_run_card_path,
            expected_review_queue_path=merged_review_path,
            expected_structural_flags_path=structural_flags_path,
            expected_audit_path=structural_review_audit_path,
            expected_registry_path=structural_review_registry_path,
            expected_model_key=structural_review_model_key,
        )
        provider_caps_path = stage_a_committed_path(
            lineage.input_commitments,
            "provider_cycle_caps",
        )
        apply_card_payload = _c._read_singly_linked_regular_input(
            apply_unitization_run_card_path,
            label="apply unitization run card",
        )
        apply_card = _c._read_json_object_payload(
            apply_card_payload,
            label="apply unitization run card",
        )
        terminal_review_records: tuple[JsonRecord, ...] = ()
        terminal_escalation_records: tuple[JsonRecord, ...] = ()
        terminal_adjudication_records: tuple[JsonRecord, ...] = ()
        terminal_review_path: Path | None = None
        terminal_review_payload: bytes | None = None
        terminal_adjudications_path: Path | None = None
        terminal_adjudications_payload: bytes | None = None
        if apply_card.get("stage") == "apply-unitizer-terminal-review":
            args = _c.argparse.Namespace(
                unitization_review_run_card=apply_unitization_run_card_path,
                llm_unitization_run_card=unitization_run_card_path,
                llm_review_stage_a_run_card=structural_review_run_card_path,
                provider_cycle_caps=provider_caps_path,
                provider_journal=lineage.provider_journal_path,
                controlled_private_root=controlled_private_root,
                purchase_ledger_initialization_receipt=initialization_receipt_path,
            )
            _c._verify_terminal_apply_run_card(
                args,
                run_card_path=apply_unitization_run_card_path,
                finalized_path=finalized_prediction_units_path,
                expected_selection_path=stage_a_committed_path(
                    lineage.input_commitments, "selection"
                ),
                expected_parser_manifest_path=stage_a_committed_path(
                    lineage.input_commitments, "parser_manifest"
                ),
                expected_markdown_root=lineage.markdown_root,
                run_card_payload=apply_card_payload,
            )
            raw_source_commitments = apply_card.get("source_commitments")
            if not isinstance(raw_source_commitments, Mapping):
                raise _c.CommandError(
                    "apply-unitizer-terminal-review run card lacks source commitments"
                )
            source_commitments = cast(Mapping[str, object], raw_source_commitments)
            _, terminal_escalations_payload = capture_stage_a_committed_file(
                source_commitments,
                "terminal_escalations",
            )
            terminal_review_path, terminal_review_payload = (
                capture_stage_a_committed_file(
                    source_commitments,
                    "unitizer_terminal_review_queue",
                )
            )
            terminal_adjudications_path, terminal_adjudications_payload = (
                capture_stage_a_committed_file(
                    source_commitments,
                    "unitizer_terminal_adjudications",
                )
            )
            terminal_escalation_records = tuple(
                _c._read_jsonl_payload(
                    terminal_escalations_payload,
                    label="unitizer terminal escalations",
                )
            )
            terminal_review_records = tuple(
                _c._read_jsonl_payload(
                    terminal_review_payload,
                    label="unitizer terminal review queue",
                )
            )
            terminal_adjudication_records = tuple(
                _c._read_jsonl_payload(
                    terminal_adjudications_payload,
                    label="unitizer terminal adjudications",
                )
            )
        else:
            _c._verify_unitization_review_run_card(
                apply_unitization_run_card_path,
                llm_unitization_run_card_path=unitization_run_card_path,
                llm_review_stage_a_run_card_path=structural_review_run_card_path,
                raw_prediction_units_path=raw_prediction_units_path,
                original_review_queue_path=original_review_path,
                review_queue_path=merged_review_path,
                adjudications_path=adjudications_path,
                provider_cycle_caps_path=provider_caps_path,
                provider_journal_path=lineage.provider_journal_path,
                finalized_path=finalized_prediction_units_path,
                controlled_private_root=controlled_private_root,
                initialization_receipt_path=initialization_receipt_path,
            )
        raw_records = tuple(_c._read_records(raw_prediction_units_path))
        audit_records = tuple(_c._read_records(unitization_audit_path))
        original_review_records = tuple(_c._read_records(original_review_path))
        structural_flag_records = tuple(_c._read_records(structural_flags_path))
        structural_audit_records = tuple(_c._read_records(structural_review_audit_path))
        merged_review_records = tuple(_c._read_records(merged_review_path))
        adjudication_records = tuple(_c._read_records(adjudications_path))
        finalized_records = tuple(_c._read_records(finalized_prediction_units_path))
        if finalized_records != tuple(finalized_prediction_unit_records):
            raise _c.CommandError("Stage A finalized units differ from apply output")
        registry_payload = structural_review_registry_path.read_bytes()
        structural_review_registry = _c._model_registry_from_payload(
            registry_payload,
            source=structural_review_registry_path,
        )
        try:
            _c.verify_stage_a_readiness_provenance(
                selection_records=selection_records,
                raw_prediction_unit_records=raw_records,
                original_review_records=original_review_records,
                structural_flag_records=structural_flag_records,
                structural_review_audit_records=structural_audit_records,
                merged_review_records=merged_review_records,
                finalized_prediction_unit_records=finalized_records,
                adjudication_records=adjudication_records,
                reviewer_registry_entries=structural_review_registry.entries,
                reviewer_registry_sha256=_c._bytes_sha256(
                    registry_payload
                ).removeprefix("sha256:"),
                reviewer_model_key=structural_review_model_key,
                terminal_review_records=terminal_review_records,
                terminal_escalation_records=terminal_escalation_records,
                terminal_adjudication_records=terminal_adjudication_records,
            )
        except (ReadinessProvenanceError, UnitizationReviewError) as exc:
            raise _c.CommandError(str(exc)) from exc
        return StageAReplay(
            raw_prediction_unit_records=raw_records,
            unitization_audit_records=audit_records,
            original_review_records=original_review_records,
            structural_flag_records=structural_flag_records,
            structural_review_audit_records=structural_audit_records,
            merged_review_records=merged_review_records,
            adjudication_records=adjudication_records,
            terminal_review_records=terminal_review_records,
            terminal_escalation_records=terminal_escalation_records,
            terminal_adjudication_records=terminal_adjudication_records,
            terminal_review_path=terminal_review_path,
            terminal_review_payload=terminal_review_payload,
            terminal_adjudications_path=terminal_adjudications_path,
            terminal_adjudications_payload=terminal_adjudications_payload,
        )

    try:
        unitize_card, unitize_card_payload = _c._executed_stage_run_card_snapshot(
            unitization_run_card_path,
            stage="llm-unitize",
            paid=True,
        )
        unitize_input_paths = _c._stage_card_input_paths(
            unitize_card,
            stage="llm-unitize",
            expected_count=4,
        )
        unitize_sources = _c._stage_card_records(
            unitize_card.get("source_commitments"),
            names_and_paths=(
                ("selection", unitize_input_paths[0]),
                ("parser_manifest", unitize_input_paths[1]),
                ("model_registry", unitize_input_paths[2]),
                ("provider_cycle_caps", unitize_input_paths[3]),
            ),
            label="llm-unitize",
        )
        if tuple(unitize_sources["selection"]) != tuple(selection_records):
            raise _c.CommandError("llm-unitize selection differs from packet selection")
        if tuple(unitize_sources["parser_manifest"]) != tuple(parser_records):
            raise _c.CommandError(
                "llm-unitize parser manifest differs from packet parser authority"
            )
        unitize_outputs = _c._stage_card_records(
            unitize_card.get("output_commitments"),
            names_and_paths=(
                ("prediction_units", raw_prediction_units_path),
                ("unitization_audit", unitization_audit_path),
                ("original_review_queue", original_review_path),
            ),
            label="llm-unitize",
        )
        unitize_provider_records = _c._validate_provider_journal_stage_commitment(
            unitize_card.get("provider_journal_commitment"),
            path=unitization_provider_journal_path,
            stage="llm-unitize",
        )
        _c._verify_unitization_provider_replay(
            provider_records=unitize_provider_records,
            raw_records=unitize_outputs["prediction_units"],
            audit_records=unitize_outputs["unitization_audit"],
        )

        review_card, review_card_payload = _c._executed_stage_run_card_snapshot(
            structural_review_run_card_path,
            stage="llm-review-stage-a",
            paid=True,
        )
        review_input_paths = _c._stage_card_input_paths(
            review_card,
            stage="llm-review-stage-a",
            expected_count=6,
        )
        review_sources = _c._stage_card_records(
            review_card.get("source_commitments"),
            names_and_paths=(
                ("selection", review_input_paths[0]),
                ("parser_manifest", review_input_paths[1]),
                ("prediction_units", raw_prediction_units_path),
                ("original_review_queue", original_review_path),
                ("model_registry", structural_review_registry_path),
                ("provider_cycle_caps", review_input_paths[5]),
            ),
            label="llm-review-stage-a",
        )
        if tuple(review_sources["selection"]) != tuple(selection_records):
            raise _c.CommandError(
                "llm-review-stage-a selection differs from packet selection"
            )
        if tuple(review_sources["parser_manifest"]) != tuple(parser_records):
            raise _c.CommandError(
                "llm-review-stage-a parser manifest differs from packet "
                "parser authority"
            )
        if review_sources["prediction_units"] != unitize_outputs["prediction_units"]:
            raise _c.CommandError("Stage A reviewer raw-unit source mismatch")
        if (
            review_sources["original_review_queue"]
            != unitize_outputs["original_review_queue"]
        ):
            raise _c.CommandError("Stage A reviewer queue source mismatch")
        review_outputs = _c._stage_card_records(
            review_card.get("output_commitments"),
            names_and_paths=(
                ("structural_flags", structural_flags_path),
                ("merged_review_queue", merged_review_path),
                ("structural_review_audit", structural_review_audit_path),
            ),
            label="llm-review-stage-a",
        )
        review_provider_records = _c._validate_provider_journal_stage_commitment(
            review_card.get("provider_journal_commitment"),
            path=structural_review_provider_journal_path,
            stage="llm-review-stage-a",
        )
        _c._verify_structural_provider_replay(
            provider_records=review_provider_records,
            flag_records=review_outputs["structural_flags"],
            audit_records=review_outputs["structural_review_audit"],
        )

        apply_card, apply_card_payload = _c._executed_stage_run_card_snapshot(
            apply_unitization_run_card_path,
            stage="apply-unitization-review",
            paid=False,
        )
        apply_sources = _c._stage_card_records(
            apply_card.get("source_commitments"),
            names_and_paths=(
                ("prediction_units", raw_prediction_units_path),
                ("merged_review_queue", merged_review_path),
                ("adjudications", adjudications_path),
            ),
            label="apply-unitization-review",
        )
        if apply_sources["prediction_units"] != unitize_outputs["prediction_units"]:
            raise _c.CommandError("Stage A apply raw-unit source mismatch")
        if (
            apply_sources["merged_review_queue"]
            != review_outputs["merged_review_queue"]
        ):
            raise _c.CommandError("Stage A apply review-queue source mismatch")
        apply_outputs = _c._stage_card_records(
            apply_card.get("output_commitments"),
            names_and_paths=(
                ("finalized_prediction_units", finalized_prediction_units_path),
            ),
            label="apply-unitization-review",
        )
        if tuple(apply_outputs["finalized_prediction_units"]) != tuple(
            finalized_prediction_unit_records
        ):
            raise _c.CommandError("Stage A finalized units differ from apply output")

        registry_commitment = cast(
            Mapping[str, object],
            cast(Mapping[str, object], review_card["source_commitments"])[
                "model_registry"
            ],
        )
        registry_payload = structural_review_registry_path.read_bytes()
        if _c._bytes_sha256(registry_payload) != registry_commitment.get("sha256"):
            raise _c.CommandError("Stage A reviewer registry commitment mismatch")
        structural_review_registry = _c._model_registry_from_payload(
            registry_payload,
            source=structural_review_registry_path,
        )
        _c.verify_stage_a_readiness_provenance(
            selection_records=selection_records,
            raw_prediction_unit_records=unitize_outputs["prediction_units"],
            original_review_records=unitize_outputs["original_review_queue"],
            structural_flag_records=review_outputs["structural_flags"],
            structural_review_audit_records=review_outputs["structural_review_audit"],
            merged_review_records=review_outputs["merged_review_queue"],
            finalized_prediction_unit_records=finalized_prediction_unit_records,
            adjudication_records=apply_sources["adjudications"],
            reviewer_registry_entries=structural_review_registry.entries,
            reviewer_registry_sha256=_c._bytes_sha256(registry_payload).removeprefix(
                "sha256:"
            ),
            reviewer_model_key=structural_review_model_key,
        )
        for path, payload, label in (
            (unitization_run_card_path, unitize_card_payload, "llm-unitize"),
            (
                structural_review_run_card_path,
                review_card_payload,
                "llm-review-stage-a",
            ),
            (
                apply_unitization_run_card_path,
                apply_card_payload,
                "apply-unitization-review",
            ),
        ):
            if path.read_bytes() != payload:
                raise _c.CommandError(f"{label} run card changed while being replayed")
        return StageAReplay(
            raw_prediction_unit_records=unitize_outputs["prediction_units"],
            unitization_audit_records=unitize_outputs["unitization_audit"],
            original_review_records=unitize_outputs["original_review_queue"],
            structural_flag_records=review_outputs["structural_flags"],
            structural_review_audit_records=review_outputs["structural_review_audit"],
            merged_review_records=review_outputs["merged_review_queue"],
            adjudication_records=apply_sources["adjudications"],
        )
    except (
        ReadinessProvenanceError,
        UnitizationReviewError,
        IndexError,
        KeyError,
        TypeError,
    ) as exc:
        raise _c.CommandError(str(exc)) from exc
