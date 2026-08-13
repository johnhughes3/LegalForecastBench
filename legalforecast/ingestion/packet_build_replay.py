# pyright: reportPrivateUsage=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportUnknownParameterType=false

"""Importable packet-build and packet-planner run-card replay helpers."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from legalforecast.ingestion.target_raw_docket_auxiliary_provenance import (
    TargetRawDocketAuxiliaryProvenanceError,
    VerifiedTargetRawDocketAuxiliaryProvenanceBridge,
)

JsonRecord = dict[str, Any]


def _cli() -> Any:
    from legalforecast import cli as cli_module

    return cli_module


@dataclass(frozen=True, slots=True)
class PacketBuildReplay:
    packet_records: tuple[JsonRecord, ...]
    packets_sha256: str
    build_run_card_sha256: str = ""


def packet_card_committed_directory(
    parameters: Mapping[str, object],
    *,
    name: str,
    expected_path: Path | None = None,
) -> Path:
    _cli_ns = _cli()
    CohortDocumentMaterializationError = _cli_ns.CohortDocumentMaterializationError
    CommandError = _cli_ns.CommandError
    require_non_symlink_components = _cli_ns.require_non_symlink_components
    raw_path = parameters.get(name)
    if not isinstance(raw_path, str) or not raw_path:
        raise CommandError(f"packet planner parameter {name} is invalid")
    path = Path(raw_path)
    try:
        require_non_symlink_components(path)
    except CohortDocumentMaterializationError as exc:
        raise CommandError(str(exc)) from exc
    if path.is_symlink() or not path.is_dir():
        raise CommandError(f"packet planner directory {name} is missing or unsafe")
    if expected_path is not None:
        try:
            require_non_symlink_components(expected_path)
        except CohortDocumentMaterializationError as exc:
            raise CommandError(str(exc)) from exc
        if expected_path.is_symlink() or not expected_path.is_dir():
            raise CommandError(
                f"packet planner expected directory {name} is missing or unsafe"
            )
        if path.resolve() != expected_path.resolve():
            raise CommandError(f"packet planner directory {name} path mismatch")
    return path


def replay_packet_planner_run_card(
    card: Mapping[str, object],
    *,
    run_card_sha256: str,
    run_card_path: Path,
    packet_build_input_path: Path,
    selection_path: Path,
    download_manifest_path: Path,
    parser_manifest_path: Path,
    clearance_path: Path,
    prediction_units_path: Path,
    model_registry_path: Path,
    raw_html_dir: Path,
    raw_artifacts_manifest_path: Path,
    document_root: Path,
    markdown_root: Path,
    resolved_post_recovery_documents_path: Path | None,
    docket_decision_descriptor: object | None = None,
) -> object:
    """Re-run packet planning from its exact committed inputs and parameters."""

    _cli_ns = _cli()
    CommandError = _cli_ns.CommandError
    _PacketPlannerReplay = _cli_ns._PacketPlannerReplay
    _bytes_sha256 = _cli_ns._bytes_sha256
    _consume_materialized_docket_decision_authority = (
        _cli_ns._consume_materialized_docket_decision_authority
    )
    _mapping = _cli_ns._mapping
    _materializer_tree_snapshot = _cli_ns._materializer_tree_snapshot
    _model_registry_from_payload = _cli_ns._model_registry_from_payload
    _packet_card_committed_snapshot = _cli_ns._packet_card_committed_snapshot
    _parse_datetime = _cli_ns._parse_datetime
    _projection_jsonl_bytes = _cli_ns._projection_jsonl_bytes
    _projection_jsonl_records = _cli_ns._projection_jsonl_records
    _require_packet_raw_provenance_bridge_commitment = (
        _cli_ns._require_packet_raw_provenance_bridge_commitment
    )
    earliest_eligible_decision_date = _cli_ns.earliest_eligible_decision_date
    load_verified_target_raw_docket_auxiliary_provenance_bridge = (
        _cli_ns.load_verified_target_raw_docket_auxiliary_provenance_bridge
    )
    plan_packet_build_inputs = _cli_ns.plan_packet_build_inputs
    require_official_registry_entries = _cli_ns.require_official_registry_entries
    parameters = card.get("deterministic_parameters")
    sources = card.get("replay_source_commitments")
    outputs = card.get("output_commitments")
    if not isinstance(parameters, Mapping) or not isinstance(sources, Mapping):
        raise CommandError("packet planner run card lacks deterministic replay data")
    if not isinstance(outputs, Mapping):
        raise CommandError("packet planner run card lacks output commitments")
    typed_parameters = cast(Mapping[str, object], parameters)
    typed_sources = cast(Mapping[str, object], sources)
    typed_outputs = cast(Mapping[str, object], outputs)
    required_parameter_names = {
        "generated_at",
        "search_query",
        "search_window",
        "decision_filed_on_or_after",
        "source_dir",
        "raw_html_dir",
        "document_root",
        "markdown_root",
    }
    if set(typed_parameters) != required_parameter_names:
        raise CommandError("packet planner deterministic parameters are incomplete")
    required_source_names = {
        "selection",
        "download_manifest",
        "parser_manifest",
        "disclosure_clearance",
        "prediction_units",
        "model_registry",
        "raw_artifacts_manifest",
    }
    if not required_source_names.issubset(typed_sources) or set(typed_sources) - (
        required_source_names
        | {"resolved_post_recovery_documents", "raw_provenance_bridge"}
    ):
        raise CommandError("packet planner replay source commitments are incomplete")
    if set(typed_outputs) != {
        "packet_build_input",
        "document_manifest",
        "candidate_manifest",
        "extracted_texts",
        "exclusion_ledger",
    }:
        raise CommandError("packet planner output commitments are incomplete")

    raw_materialization_lineage = card.get("authenticated_materialization_lineage")
    if not isinstance(raw_materialization_lineage, Sequence) or isinstance(
        raw_materialization_lineage, (str, bytes)
    ):
        raise CommandError("packet planner run card lacks materialization lineage")
    materialization_lineage = tuple(
        dict(_mapping(item, f"materialization lineage item {index}"))
        for index, item in enumerate(
            cast(Sequence[object], raw_materialization_lineage)
        )
    )

    committed_selection, selection_payload = _packet_card_committed_snapshot(
        typed_sources, name="selection", expected_path=selection_path
    )
    committed_downloads, downloads_payload = _packet_card_committed_snapshot(
        typed_sources,
        name="download_manifest",
        expected_path=download_manifest_path,
    )
    _clearance_path, clearance_payload = _packet_card_committed_snapshot(
        typed_sources,
        name="disclosure_clearance",
        expected_path=clearance_path,
    )
    parser_manifest, parser_payload = _packet_card_committed_snapshot(
        typed_sources,
        name="parser_manifest",
        expected_path=parser_manifest_path,
    )
    prediction_units, prediction_units_payload = _packet_card_committed_snapshot(
        typed_sources,
        name="prediction_units",
        expected_path=prediction_units_path,
    )
    model_registry, model_registry_payload = _packet_card_committed_snapshot(
        typed_sources,
        name="model_registry",
        expected_path=model_registry_path,
    )
    raw_artifacts_manifest, raw_artifacts_payload = _packet_card_committed_snapshot(
        typed_sources,
        name="raw_artifacts_manifest",
        expected_path=raw_artifacts_manifest_path,
    )
    raw_provenance_bridge: VerifiedTargetRawDocketAuxiliaryProvenanceBridge | None = (
        None
    )
    if "raw_provenance_bridge" in typed_sources:
        bridge_path, bridge_payload = _packet_card_committed_snapshot(
            typed_sources, name="raw_provenance_bridge"
        )
        try:
            raw_provenance_bridge = cast(
                VerifiedTargetRawDocketAuxiliaryProvenanceBridge,
                load_verified_target_raw_docket_auxiliary_provenance_bridge(
                    bridge_path
                ),
            )
        except TargetRawDocketAuxiliaryProvenanceError as exc:
            raise CommandError(str(exc)) from exc
        if (
            raw_provenance_bridge.raw_artifacts_manifest_path
            != raw_artifacts_manifest_path.resolve()
            or raw_provenance_bridge.source_raw_html_dir != raw_html_dir.resolve()
        ):
            raise CommandError("packet planner raw-provenance bridge differs")
        _require_packet_raw_provenance_bridge_commitment(
            raw_provenance_bridge,
            bridge_payload,
        )
    has_resolved_source = "resolved_post_recovery_documents" in typed_sources
    if has_resolved_source != (resolved_post_recovery_documents_path is not None):
        raise CommandError("packet planner resolved-document source coverage mismatch")
    if resolved_post_recovery_documents_path is not None:
        _packet_card_committed_snapshot(
            typed_sources,
            name="resolved_post_recovery_documents",
            expected_path=resolved_post_recovery_documents_path,
        )

    def required_string(name: str) -> str:
        value = typed_parameters.get(name)
        if not isinstance(value, str) or not value:
            raise CommandError(f"packet planner parameter {name} is invalid")
        return value

    generated_at = _parse_datetime(required_string("generated_at"))
    committed_source_dir = packet_card_committed_directory(
        typed_parameters,
        name="source_dir",
    )
    committed_raw_html_dir = packet_card_committed_directory(
        typed_parameters,
        name="raw_html_dir",
        expected_path=raw_html_dir,
    )
    committed_document_root = packet_card_committed_directory(
        typed_parameters,
        name="document_root",
        expected_path=document_root,
    )
    committed_markdown_root = packet_card_committed_directory(
        typed_parameters,
        name="markdown_root",
        expected_path=markdown_root,
    )
    raw_html_snapshot = _materializer_tree_snapshot(committed_raw_html_dir)
    markdown_snapshot = _materializer_tree_snapshot(committed_markdown_root)
    committed_eligible_date = required_string("decision_filed_on_or_after")
    registry = _model_registry_from_payload(
        model_registry_payload, source=model_registry
    )
    actual_eligible_date = earliest_eligible_decision_date(
        require_official_registry_entries(registry.entries)
    )
    if committed_eligible_date != actual_eligible_date.isoformat():
        raise CommandError(
            "packet planner eligibility parameter does not match registry"
        )
    selection_records = _projection_jsonl_records(
        selection_payload, source=committed_selection
    )
    parser_records = _projection_jsonl_records(parser_payload, source=parser_manifest)
    clearance_records = _projection_jsonl_records(
        clearance_payload, source=clearance_path
    )
    prediction_unit_records = _projection_jsonl_records(
        prediction_units_payload, source=prediction_units
    )
    download_records = _projection_jsonl_records(
        downloads_payload, source=committed_downloads
    )
    raw_artifact_records = _projection_jsonl_records(
        raw_artifacts_payload, source=raw_artifacts_manifest
    )
    plan = _consume_materialized_docket_decision_authority(
        docket_decision_descriptor,
        lambda authority, journal: plan_packet_build_inputs(
            selection_records=selection_records,
            download_records=download_records,
            parser_records=parser_records,
            prediction_unit_records=prediction_unit_records,
            raw_html_dir=committed_raw_html_dir,
            raw_artifact_records=raw_artifact_records,
            raw_artifact_bytes=raw_html_snapshot,
            auxiliary_raw_artifact_bytes_by_path=(
                raw_provenance_bridge.raw_artifact_bytes_by_path
                if raw_provenance_bridge is not None
                else None
            ),
            document_root=committed_document_root,
            markdown_root=committed_markdown_root,
            markdown_bytes=markdown_snapshot,
            source_dir=committed_source_dir,
            generated_at=generated_at,
            search_query=required_string("search_query"),
            search_window=required_string("search_window"),
            decision_filed_on_or_after=actual_eligible_date,
            docket_decision_authority=authority,
            purchase_journal=journal,
        ),
    )
    expected_payloads = {
        "packet_build_input": _projection_jsonl_bytes(plan.packet_build_records),
        "document_manifest": _projection_jsonl_bytes(plan.document_manifest_records),
        "candidate_manifest": _projection_jsonl_bytes(plan.candidate_manifest_records),
        "extracted_texts": _projection_jsonl_bytes(plan.extracted_text_records),
        "exclusion_ledger": _projection_jsonl_bytes(plan.exclusion_ledger_records),
    }
    for name, expected_payload in expected_payloads.items():
        _output_path, output_payload = _packet_card_committed_snapshot(
            typed_outputs,
            name=name,
            expected_path=(
                packet_build_input_path if name == "packet_build_input" else None
            ),
        )
        if output_payload != expected_payload:
            raise CommandError(f"packet planner replay mismatch for {name}")
    if _materializer_tree_snapshot(committed_raw_html_dir) != raw_html_snapshot:
        raise CommandError("packet planner raw HTML tree changed during replay")
    if _materializer_tree_snapshot(committed_markdown_root) != markdown_snapshot:
        raise CommandError("packet planner Markdown tree changed during replay")
    packet_build_payload = expected_payloads["packet_build_input"]
    return _PacketPlannerReplay(
        packet_build_records=tuple(
            dict(record) for record in plan.packet_build_records
        ),
        packet_build_input_sha256=_bytes_sha256(packet_build_payload),
        selection_records=tuple(dict(record) for record in selection_records),
        download_records=tuple(dict(record) for record in download_records),
        parser_records=tuple(dict(record) for record in parser_records),
        clearance_records=tuple(dict(record) for record in clearance_records),
        clearance_sha256=_bytes_sha256(clearance_payload),
        parser_manifest_sha256=_bytes_sha256(parser_payload),
        parser_record_count=len(parser_records),
        prediction_unit_records=tuple(
            dict(record) for record in prediction_unit_records
        ),
        model_registry=registry,
        model_registry_sha256=_bytes_sha256(model_registry_payload),
        planner_run_card_sha256=run_card_sha256,
        planner_run_card_path=str(run_card_path.resolve()),
        authenticated_materialization_lineage=materialization_lineage,
    )


def replay_packet_build_run_card(
    card: Mapping[str, object],
    *,
    run_card_sha256: str,
    packet_build_records: Sequence[Mapping[str, Any]],
    packets_path: Path,
) -> PacketBuildReplay:
    """Re-run packet assembly and byte-compare every committed output."""

    _cli_ns = _cli()
    CommandError = _cli_ns.CommandError
    PacketAblation = _cli_ns.PacketAblation
    _bytes_sha256 = _cli_ns._bytes_sha256
    _model_packet_assembly = _cli_ns._model_packet_assembly
    _packet_card_committed_snapshot = _cli_ns._packet_card_committed_snapshot
    _projection_jsonl_bytes = _cli_ns._projection_jsonl_bytes
    parameters = card.get("deterministic_parameters")
    outputs = card.get("output_commitments")
    if not isinstance(parameters, Mapping):
        raise CommandError("packet build run card lacks deterministic parameters")
    typed_parameters = cast(Mapping[str, object], parameters)
    if set(typed_parameters) != {"ablation"}:
        raise CommandError("packet build run card lacks deterministic parameters")
    if not isinstance(outputs, Mapping):
        raise CommandError("packet build run card lacks exact output commitments")
    typed_outputs = cast(Mapping[str, object], outputs)
    if set(typed_outputs) != {
        "packets",
        "case_packets",
        "packet_audit",
    }:
        raise CommandError("packet build run card lacks exact output commitments")
    ablation_value = typed_parameters.get("ablation")
    if not isinstance(ablation_value, str):
        raise CommandError("packet build ablation parameter is invalid")
    try:
        ablation = PacketAblation(ablation_value)
    except ValueError as exc:
        raise CommandError("packet build ablation parameter is invalid") from exc
    assemblies = tuple(
        _model_packet_assembly(record, ablation=ablation)
        for record in packet_build_records
    )
    expected_payloads = {
        "packets": _projection_jsonl_bytes(
            assembly.model_packet.to_record() for assembly in assemblies
        ),
        "case_packets": _projection_jsonl_bytes(
            assembly.case_packet.to_record() for assembly in assemblies
        ),
        "packet_audit": _projection_jsonl_bytes(
            assembly.audit_bundle for assembly in assemblies
        ),
    }
    for name, expected_payload in expected_payloads.items():
        _output_path, output_payload = _packet_card_committed_snapshot(
            typed_outputs,
            name=name,
            expected_path=(packets_path if name == "packets" else None),
        )
        if output_payload != expected_payload:
            raise CommandError(f"packet build replay mismatch for {name}")
    packets_payload = expected_payloads["packets"]
    return PacketBuildReplay(
        packet_records=tuple(
            dict(assembly.model_packet.to_record()) for assembly in assemblies
        ),
        packets_sha256=_bytes_sha256(packets_payload),
        build_run_card_sha256=run_card_sha256,
    )


def verify_packet_raw_artifacts_snapshot_binding(
    *,
    raw_html_dir: Path,
    raw_artifacts_manifest_path: Path,
    screening_snapshot_manifest_path: Path,
    raw_provenance_bridge: VerifiedTargetRawDocketAuxiliaryProvenanceBridge
    | None = None,
) -> None:
    """Bind packet docket bytes to the authenticated screening snapshot."""

    _cli_ns = _cli()
    CommandError = _cli_ns.CommandError
    _normalize_owned_raw_records = _cli_ns._normalize_owned_raw_records
    _owned_raw_records_from_snapshot = _cli_ns._owned_raw_records_from_snapshot
    _read_jsonl_payload = _cli_ns._read_jsonl_payload
    _require_materializer_artifact = _cli_ns._require_materializer_artifact
    snapshot_path = screening_snapshot_manifest_path.parent
    snapshot_raw_artifacts_path = snapshot_path / "raw-artifacts.jsonl"
    snapshot_raw_artifacts_bytes = _require_materializer_artifact(
        snapshot_raw_artifacts_path,
        label="screening snapshot raw artifacts",
    )
    raw_artifacts_manifest_bytes = _require_materializer_artifact(
        raw_artifacts_manifest_path,
        label="packet raw-artifact manifest",
    )
    if raw_provenance_bridge is not None:
        if (
            raw_artifacts_manifest_path.resolve()
            != raw_provenance_bridge.raw_artifacts_manifest_path
            or raw_html_dir.resolve() != raw_provenance_bridge.source_raw_html_dir
            or screening_snapshot_manifest_path.resolve()
            != raw_provenance_bridge.source_snapshot_path / "manifest.json"
        ):
            raise CommandError(
                "raw-provenance bridge does not bind packet screening inputs"
            )
        if hashlib.sha256(raw_artifacts_manifest_bytes).hexdigest() != (
            raw_provenance_bridge.raw_artifacts_manifest_sha256
        ):
            raise CommandError("raw-provenance bridge manifest commitment differs")
        return
    expected_records = _owned_raw_records_from_snapshot(
        snapshot_path,
        archived_records=_normalize_owned_raw_records(
            _read_jsonl_payload(
                snapshot_raw_artifacts_bytes, label=str(snapshot_raw_artifacts_path)
            )
        ),
    )
    if (
        _read_jsonl_payload(
            raw_artifacts_manifest_bytes, label=str(raw_artifacts_manifest_path)
        )
        != expected_records
    ):
        raise CommandError(
            "packet raw-artifact manifest differs from authenticated snapshot"
        )
    packet_card_committed_directory(
        {"raw_html_dir": str(raw_html_dir)},
        name="raw_html_dir",
        expected_path=raw_html_dir,
    )


def validate_packet_build_run_card(
    run_card_path: Path,
    *,
    packet_input_run_card_path: Path,
    packet_build_input_path: Path,
    packet_build_records: Sequence[Mapping[str, Any]],
    packets_path: Path,
    selection_path: Path,
    download_manifest_path: Path,
    clearance_path: Path,
    document_root: Path,
    materialization_run_card_path: Path,
    expected_model_registry_sha256: str,
    packet_input_run_card_sha256: str | None = None,
    authenticated_materialization_lineage: Sequence[Mapping[str, Any]] | None = None,
) -> PacketBuildReplay:
    """Replay the exact planner, materialization, input, and packet outputs."""

    _cli_ns = _cli()
    CommandError = _cli_ns.CommandError
    _bytes_sha256 = _cli_ns._bytes_sha256
    _normalize_expected_sha256 = _cli_ns._normalize_expected_sha256
    _packet_materialization_lineage_commitments = (
        _cli_ns._packet_materialization_lineage_commitments
    )
    _path_sha256 = _cli_ns._path_sha256
    _projection_json_object = _cli_ns._projection_json_object
    _require_materializer_artifact = _cli_ns._require_materializer_artifact
    _validate_named_path_commitment = _cli_ns._validate_named_path_commitment
    card_payload = _require_materializer_artifact(
        run_card_path, label="packet build run card"
    )
    card = _projection_json_object(card_payload, source=run_card_path)
    if (
        card.get("schema_version") != "legalforecast.acquisition_run_card.v1"
        or card.get("stage") != "build-packets"
        or card.get("status") != "completed"
        or card.get("dry_run") is not False
        or card.get("execute") is not True
        or card.get("paid_activity_requested") is not False
        or card.get("paid_activity_executed") is not False
    ):
        raise CommandError("finalization requires an executed packet build run card")
    expected_lineage = (
        [dict(record) for record in authenticated_materialization_lineage]
        if authenticated_materialization_lineage is not None
        else _packet_materialization_lineage_commitments(
            selection_path=selection_path,
            download_manifest_path=download_manifest_path,
            clearance_path=clearance_path,
            document_root=document_root,
            materialization_run_card_path=materialization_run_card_path,
        )
    )
    if card.get("authenticated_materialization_lineage") != expected_lineage:
        raise CommandError(
            "packet build run card belongs to different materialized inputs"
        )
    if card.get("expected_model_registry_sha256") != _normalize_expected_sha256(
        expected_model_registry_sha256,
        label="expected model registry digest",
    ):
        raise CommandError("packet build run card has different frozen registry digest")
    source_commitments = card.get("source_commitments")
    output_commitments = card.get("output_commitments")
    if not isinstance(source_commitments, Mapping) or not isinstance(
        output_commitments, Mapping
    ):
        raise CommandError("packet build run card lacks exact commitments")
    typed_sources = cast(Mapping[str, object], source_commitments)
    typed_outputs = cast(Mapping[str, object], output_commitments)
    _validate_named_path_commitment(
        typed_sources,
        name="packet_input_run_card",
        expected_path=packet_input_run_card_path,
        expected_sha256=(
            packet_input_run_card_sha256
            if packet_input_run_card_sha256 is not None
            else _path_sha256(packet_input_run_card_path)
        ),
    )
    _validate_named_path_commitment(
        typed_sources,
        name="packet_build_input",
        expected_path=packet_build_input_path,
        expected_sha256=_path_sha256(packet_build_input_path),
    )
    _validate_named_path_commitment(
        typed_outputs,
        name="packets",
        expected_path=packets_path,
        expected_sha256=_path_sha256(packets_path),
    )
    replay = replay_packet_build_run_card(
        card,
        run_card_sha256=_bytes_sha256(card_payload),
        packet_build_records=packet_build_records,
        packets_path=packets_path,
    )
    if (
        _require_materializer_artifact(run_card_path, label="packet build run card")
        != card_payload
    ):
        raise CommandError("packet build run card changed while being replayed")
    return replay
