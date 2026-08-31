"""Manifest-mode forecast entry: signed manifest in, packets and prompts out.

This is the owner-directed parallel entry to the Cycle 1 forecast run.  It
replaces the lineage roots with one signed manifest and nothing else; every
integrity control the lineage path enforces is enforced here by **reusing the
same code**, not by restating it:

* blinding — packets are built by ``legalforecast.evals.packet_builder``, which
  refuses outcome roles outright, and the manifest's own visibility partition
  refuses them a second time before the builder ever sees them;
* contamination — models come from the evaluation registry through
  ``require_official_registry_entries``, and every case must clear the release
  anchor that registry implies;
* byte identity — every markdown file is re-hashed as it is read and compared
  to the digest the owner signed.

This entry makes **no provider call**.  It builds the packets and prompts the
existing ``legalforecast eval run-case`` executor consumes, and records exactly
what a later lineage reconciliation needs to attach full provenance to the run.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Final, cast

from legalforecast._json_io import write_json_object
from legalforecast.contracts.commitments import RAW_BYTES_RAW_SHA256_V1
from legalforecast.contracts.schemas import (
    OWNER_SIGNED_CORPUS_MANIFEST_V1,
)
from legalforecast.evals.corpus_manifest.records import (
    isoformat_utc,
    registry_record,
    run_record,
    slug,
    write_indented_json,
)
from legalforecast.evals.corpus_manifest.schema import (
    CorpusManifest,
    CorpusManifestError,
    ManifestCase,
    ManifestDocument,
    load_signed_manifest,
)
from legalforecast.evals.inspect_task import render_model_prompt
from legalforecast.evals.model_registry import (
    earliest_eligible_decision_date,
    load_model_registry,
    require_official_registry_entries,
)
from legalforecast.evals.packet_builder import (
    ModelPacket,
    PacketAblation,
    PacketText,
    build_model_packet,
)
from legalforecast.evals.prediction_units import (
    PredictionUnit,
    prediction_unit_from_record,
)
from legalforecast.ingestion.provenance import (
    AvailabilityStatus,
    CasePacketSchema,
    DocumentRole,
    SourceDocumentProvenance,
    sha256_text,
)
from legalforecast.reporting.result_class import (
    classify_decision_against_anchor,
    expected_result_class,
)

# The official shard ablations.  Named here rather than derived from the
# ablation enum so a new PacketAblation member cannot silently join an official
# run; see legalforecast.protocol.policy_artifacts.OFFICIAL_SHARD_ABLATIONS.
FORECAST_ABLATIONS: Final[tuple[PacketAblation, ...]] = (
    PacketAblation.FULL_PACKET,
    PacketAblation.METADATA_ONLY,
)
MODEL_PACKET_KEY_PREFIX: Final[str] = "model-packets"
# Manifest-mode packets carry no controlled docket document, because no docket
# bytes are bound by the owner's signature.  Serving docket entries from
# unbound bytes would put text outside the signed manifest in front of a model,
# so the docket tool is switched off rather than fed.
USE_DOCKET_TOOL: Final[bool] = False
# ``eval run-case`` defaults the docket tool ON and exposes --no-docket-tool.
# The prompt hashes this entry commits are rendered with the tool OFF, so they
# only describe the executed prompts when the runner is invoked with this flag.
# It is recorded in the run record rather than left to operator memory.
REQUIRED_RUN_CASE_FLAGS: Final[tuple[str, ...]] = ("--no-docket-tool",)


class ManifestForecastError(CorpusManifestError):
    """Raised when a manifest-mode forecast build cannot proceed safely."""


@dataclass(frozen=True, slots=True)
class OwnerSignatureReference:
    """Where the owner's signature over the manifest digest is recorded."""

    bead_id: str
    approval_line: str

    def __post_init__(self) -> None:
        if not self.bead_id.strip():
            raise ManifestForecastError("owner signature bead_id is required")
        if not self.approval_line.strip():
            raise ManifestForecastError(
                "owner signature approval_line is required, verbatim"
            )

    def to_record(self) -> dict[str, Any]:
        """Return the recorded signature reference."""

        return {"approval_line": self.approval_line, "bead_id": self.bead_id}

    def require_names_digest(self, digest: str) -> None:
        """Fail closed unless the approval line quotes the manifest digest."""

        if digest not in self.approval_line:
            raise ManifestForecastError(
                "owner approval line does not quote the manifest digest it "
                "authorizes; the signature is not bound to these bytes"
            )


@dataclass(frozen=True, slots=True)
class ForecastBuildRequest:
    """Every input to one manifest-mode forecast build."""

    manifest_path: Path
    expected_manifest_digest: str
    owner_signature: OwnerSignatureReference
    model_registry_path: Path
    output_dir: Path
    generated_at: datetime
    supplementary: bool = False
    """Build for post-anchor models, whose rows publish as supplementary.

    Set only for a registry whose models were all released after the corpus
    decision window closed. The release-anchor gate inverts rather than relaxes,
    so this cannot be used to route an official model around the official path.
    """


@dataclass(frozen=True, slots=True)
class ForecastBuildResult:
    """What the build produced, and the record that makes it reproducible."""

    manifest_digest: str
    packet_count: int
    model_ids: tuple[str, ...]
    run_record_path: Path
    run_inputs_manifest_path: Path
    packet_store_root: Path


def build_manifest_mode_forecast(
    request: ForecastBuildRequest,
) -> ForecastBuildResult:
    """Build every forecast packet and prompt from one owner-signed manifest."""

    manifest = load_signed_manifest(
        request.manifest_path,
        expected_digest=request.expected_manifest_digest,
    )
    digest = manifest.digest()
    request.owner_signature.require_names_digest(digest)

    registry = load_model_registry(request.model_registry_path)
    entries = require_official_registry_entries(registry.entries)
    release_anchor = earliest_eligible_decision_date(entries)

    units_by_candidate = _prediction_units(manifest)

    packet_store_root = request.output_dir / MODEL_PACKET_KEY_PREFIX
    packet_rows: list[dict[str, Any]] = []
    prompt_commitments: dict[str, str] = {}
    for case in manifest.cases:
        _require_release_anchor(
            case,
            release_anchor=release_anchor,
            supplementary=request.supplementary,
        )
        units = units_by_candidate.get(case.candidate_id)
        if not units:
            raise ManifestForecastError(
                f"{case.candidate_id}: manifest binds no prediction units"
            )
        texts = _verified_case_texts(case)
        case_packet = _case_packet(case, texts=texts, generated_at=request.generated_at)
        for ablation in FORECAST_ABLATIONS:
            packet = _model_packet(
                case,
                case_packet=case_packet,
                texts=texts,
                units=units,
                ablation=ablation,
            )
            row = _write_packet(
                packet,
                case=case,
                cycle_id=manifest.cycle_id,
                output_dir=request.output_dir,
            )
            prompt_sha256 = sha256_text(
                render_model_prompt(packet, use_docket_tool=USE_DOCKET_TOOL)
            )
            # Carried on the packet row as well as the run record: the runner
            # reads it from the manifest and refuses a prompt that does not
            # match, which is what makes --no-docket-tool self-enforcing
            # instead of a note the operator has to remember.
            row["prompt_sha256"] = prompt_sha256
            packet_rows.append(row)
            prompt_commitments[f"{case.candidate_id}:{ablation.value}"] = prompt_sha256

    run_inputs_path = request.output_dir / "run-inputs.json"
    write_indented_json(
        run_inputs_path,
        {
            "cycle_id": manifest.cycle_id,
            "generated_at": isoformat_utc(request.generated_at),
            "model_packets": packet_rows,
        },
    )

    run_record_path = request.output_dir / "manifest-mode-run-record.json"
    write_json_object(
        run_record_path,
        run_record(
            manifest=manifest,
            digest=digest,
            generated_at=request.generated_at,
            owner_signature=request.owner_signature.to_record(),
            docket_tool_enabled=USE_DOCKET_TOOL,
            ablations=[ablation.value for ablation in FORECAST_ABLATIONS],
            required_run_case_flags=REQUIRED_RUN_CASE_FLAGS,
            entries_record=registry_record(entries),
            prompt_commitments=prompt_commitments,
            packet_rows=packet_rows,
            release_anchor=release_anchor.isoformat(),
            run_inputs_path=run_inputs_path,
        ),
    )
    return ForecastBuildResult(
        manifest_digest=digest,
        packet_count=len(packet_rows),
        model_ids=tuple(entry.model_id for entry in entries),
        run_record_path=run_record_path,
        run_inputs_manifest_path=run_inputs_path,
        packet_store_root=packet_store_root,
    )


def _verified_case_texts(case: ManifestCase) -> dict[str, str]:
    """Read every model-visible markdown file, refusing any byte drift."""

    document_bytes: dict[str, bytes] = {}
    for document in case.model_visible_documents:
        if document.markdown_path is None or document.markdown_sha256 is None:
            raise ManifestForecastError(
                f"{case.candidate_id}/{document.source_document_id}: "
                "model-visible document has no bound markdown"
            )
        path = Path(document.markdown_path)
        try:
            payload = path.read_bytes()
        except OSError as exc:
            raise ManifestForecastError(
                f"{case.candidate_id}/{document.source_document_id}: "
                f"markdown is unreadable at freeze-recorded path {path.name}"
            ) from exc
        document_bytes[document.source_document_id] = payload
    return _verified_case_texts_from_bytes(case, document_bytes)


def _verified_case_texts_from_bytes(
    case: ManifestCase,
    document_bytes: Mapping[str, bytes],
) -> dict[str, str]:
    """Verify and decode exactly the markdown bytes captured by the caller."""

    texts: dict[str, str] = {}
    for document in case.model_visible_documents:
        payload = document_bytes.get(document.source_document_id)
        if payload is None or document.markdown_sha256 is None:
            raise ManifestForecastError(
                f"{case.candidate_id}/{document.source_document_id}: "
                "model-visible document has no captured markdown"
            )
        digest = str(
            RAW_BYTES_RAW_SHA256_V1.commit(
                payload,
                domain=OWNER_SIGNED_CORPUS_MANIFEST_V1,
            ).digest
        )
        if digest != document.markdown_sha256:
            raise ManifestForecastError(
                f"{case.candidate_id}/{document.source_document_id}: markdown "
                "bytes differ from the digest the owner signed"
            )
        texts[document.source_document_id] = payload.decode("utf-8")
    return texts


def _case_packet(
    case: ManifestCase,
    *,
    texts: Mapping[str, str],
    generated_at: datetime,
) -> CasePacketSchema:
    # Every manifest document enters the case packet — model-visible ones as
    # mounted documents, audit-only ones as unmounted provenance the builder
    # records as excluded.  The condition reads as a filter but admits all of
    # them, because `texts` only ever holds model-visible documents.
    documents = tuple(
        _provenance(case, document, generated_at=generated_at)
        for document in case.documents
        if document.model_visible or document.source_document_id not in texts
    )
    return CasePacketSchema(
        candidate_id=case.candidate_id,
        case_id=case.case_id,
        court=case.court,
        docket_number=case.docket_number,
        generated_at=generated_at,
        documents=documents,
    )


def _provenance(
    case: ManifestCase,
    document: ManifestDocument,
    *,
    generated_at: datetime,
) -> SourceDocumentProvenance:
    outcome_bearing = document.document_role in {
        DocumentRole.ORDER,
        DocumentRole.DECISION,
    }
    return SourceDocumentProvenance(
        source_provider="legalforecast-manifest",
        source_case_id=case.case_id,
        source_document_id=document.source_document_id,
        court=case.court,
        docket_number=case.docket_number,
        document_role=document.document_role,
        retrieved_at=generated_at,
        source_url_or_reference=document.source_url,
        sha256=document.pdf_sha256,
        is_predecision_material=not outcome_bearing,
        is_mounted_for_model=document.model_visible,
        availability_status=AvailabilityStatus.AVAILABLE,
        docket_entry_number=document.docket_entry_number,
        contains_target_outcome=outcome_bearing,
        packet_section="audit_only" if outcome_bearing else None,
    )


def _model_packet(
    case: ManifestCase,
    *,
    case_packet: CasePacketSchema,
    texts: Mapping[str, str],
    units: Sequence[PredictionUnit],
    ablation: PacketAblation,
) -> ModelPacket:
    packet_texts = tuple(
        PacketText(
            source_document_id=document_id,
            text=text,
            text_sha256=sha256_text(text),
        )
        for document_id, text in sorted(texts.items())
    )
    try:
        return build_model_packet(
            case_packet=case_packet,
            prediction_units=units,
            texts=packet_texts,
            metadata=_metadata(case),
            ablation=ablation,
            decision_date=case.decision_date,
        )
    except ValueError as exc:
        raise ManifestForecastError(f"{case.candidate_id}: {exc}") from exc


def _metadata(case: ManifestCase) -> dict[str, str]:
    metadata = {"court": case.court, "docket_number": case.docket_number}
    if case.decision_date:
        metadata["decision_date"] = case.decision_date
    return metadata


def _write_packet(
    packet: ModelPacket,
    *,
    case: ManifestCase,
    cycle_id: str,
    output_dir: Path,
) -> dict[str, Any]:
    object_key = "/".join(
        (
            MODEL_PACKET_KEY_PREFIX,
            slug(cycle_id),
            slug(case.case_id),
            f"{packet.ablation.value}.json",
        )
    )
    path = output_dir / object_key
    payload = write_indented_json(path, packet.to_record())
    digest = str(
        RAW_BYTES_RAW_SHA256_V1.commit(
            payload,
            domain=OWNER_SIGNED_CORPUS_MANIFEST_V1,
        ).digest
    )
    return {
        "ablation": packet.ablation.value,
        "candidate_id": case.candidate_id,
        "case_id": case.case_id,
        "decision_date": case.decision_date,
        "packet_object_key": object_key,
        "packet_sha256": digest,
        "packet_size_bytes": len(payload),
        "source_document_ids": sorted(packet.source_hashes),
        "source_hashes": dict(packet.source_hashes),
    }


def _prediction_units(
    manifest: CorpusManifest,
) -> dict[str, tuple[PredictionUnit, ...]]:
    """Load the prediction units the manifest binds, verifying their bytes."""

    path = Path(manifest.prediction_units_source.path)
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise ManifestForecastError(
            f"prediction units are unreadable at the bound path {path.name}"
        ) from exc
    return _prediction_units_from_bytes(manifest, payload)


def _prediction_units_from_bytes(
    manifest: CorpusManifest,
    payload: bytes,
) -> dict[str, tuple[PredictionUnit, ...]]:
    """Verify and parse exactly the unit bytes captured by the caller."""

    path = Path(manifest.prediction_units_source.path)
    digest = str(
        RAW_BYTES_RAW_SHA256_V1.commit(
            payload,
            domain=OWNER_SIGNED_CORPUS_MANIFEST_V1,
        ).digest
    )
    if digest != manifest.prediction_units_source.sha256:
        raise ManifestForecastError(
            "prediction unit bytes differ from the digest the owner signed"
        )
    records: list[dict[str, Any]] = []
    try:
        lines = payload.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise ManifestForecastError(f"prediction units are not UTF-8: {path}") from exc
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            value: object = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ManifestForecastError(
                f"prediction unit row {line_number} in {path} is invalid JSON"
            ) from exc
        if not isinstance(value, dict):
            raise ManifestForecastError(
                f"prediction unit row {line_number} in {path} is not an object"
            )
        records.append(cast(dict[str, Any], value))
    units: dict[str, tuple[PredictionUnit, ...]] = {}
    for record in records:
        candidate_id = record.get("candidate_id")
        rows = record.get("prediction_units")
        if not isinstance(candidate_id, str) or not isinstance(rows, list):
            continue
        units[candidate_id] = tuple(
            prediction_unit_from_record(row) for row in cast("list[object]", rows)
        )
    return units


def _require_release_anchor(
    case: ManifestCase,
    *,
    release_anchor: date,
    supplementary: bool = False,
) -> None:
    """Require every case to match the execution mode's contamination posture.

    Official mode is unchanged: a decision must postdate the evaluated models'
    release, or the run cannot claim the model could not have trained on the
    outcome.

    Supplementary mode inverts the same comparison rather than dropping it.
    Being post-anchor is *why* a run is supplementary, so requiring
    ``decision_date >= release_anchor`` there is not a passable condition. The
    inverted gate stays fail-closed in the other direction: a pre-anchor
    (official-classed) model run in supplementary mode is refused here, so the
    supplementary lane cannot be used to route an official model around the
    official gates.
    """

    if not case.decision_date:
        raise ManifestForecastError(
            f"{case.candidate_id}: decision_date is required to clear the "
            "evaluation-registry release anchor"
        )
    observed = classify_decision_against_anchor(
        decision_date=date.fromisoformat(case.decision_date),
        release_anchor=release_anchor,
    )
    expected = expected_result_class(supplementary=supplementary)
    if observed is expected:
        return
    if supplementary:
        raise ManifestForecastError(
            f"{case.candidate_id}: decision_date {case.decision_date} does not "
            f"precede the evaluation-registry release anchor {release_anchor}; a "
            "supplementary run requires post-anchor models"
        )
    raise ManifestForecastError(
        f"{case.candidate_id}: decision_date {case.decision_date} precedes "
        f"the evaluation-registry release anchor {release_anchor}"
    )
