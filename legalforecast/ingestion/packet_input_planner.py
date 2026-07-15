"""Plan packet-build and private-store inputs from acquisition manifests."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast

from legalforecast.ingestion.courtlistener_dates import parse_courtlistener_filed_date
from legalforecast.ingestion.courtlistener_web import (
    CourtListenerWebDocketEntry,
    parse_courtlistener_docket_html,
)
from legalforecast.ingestion.docket_markdown import (
    ControlledDocketMarkdownArtifacts,
    ControlledDocketMarkdownEntry,
    DocketMarkdownMetadata,
    render_controlled_docket_markdown,
)
from legalforecast.ingestion.mtd_acquisition_screen import (
    MtdDocketScreenStatus,
    screen_courtlistener_docket_for_mtd_decision,
)
from legalforecast.ingestion.provenance import (
    AvailabilityStatus,
    DocumentRole,
    sha256_text,
)
from legalforecast.path_safety import safe_path_component
from legalforecast.selection.contamination_filters import (
    LeakageSource,
    LeakageSourceKind,
    OutcomeLeakageFilterResult,
    detect_outcome_leakage,
)
from legalforecast.selection.exclusion_ledger import (
    ExclusionLedgerEntry,
    ExclusionReason,
    ExclusionStage,
)
from legalforecast.unitization.review import (
    UnitizationReviewError,
    require_finalized_envelopes,
)


class PacketInputPlanningError(ValueError):
    """Raised when acquisition artifacts cannot produce packet-build inputs."""


_COURTLISTENER_DOCKET_CANDIDATE_PREFIX = "courtlistener-docket-"
_COURTLISTENER_DOCKET_CANDIDATE_ID = re.compile(
    rf"{re.escape(_COURTLISTENER_DOCKET_CANDIDATE_PREFIX)}(?P<docket_id>[0-9]+)\Z"
)


@dataclass(frozen=True, slots=True)
class VerifiedRawArtifact:
    """One manifest-bound raw docket artifact verified before parsing."""

    manifest_candidate_id: str
    manifest_path: str
    path: Path
    text: str
    sha256: str
    byte_count: int


@dataclass(frozen=True, slots=True)
class VerifiedRawArtifactBinding:
    """Unambiguous ownership of one verified raw artifact by one selection."""

    selection_candidate_id: str
    manifest_candidate_id: str
    binding_kind: str
    artifact: VerifiedRawArtifact

    def to_provenance_record(self) -> dict[str, str | int]:
        """Return the audit-only provenance preserved in planner outputs."""

        return {
            "selection_candidate_id": self.selection_candidate_id,
            "manifest_candidate_id": self.manifest_candidate_id,
            "binding_kind": self.binding_kind,
            "manifest_path": self.artifact.manifest_path,
            "sha256": self.artifact.sha256,
            "byte_count": self.artifact.byte_count,
        }


def load_verified_raw_artifacts(
    records: Iterable[Mapping[str, Any]],
    *,
    raw_html_dir: str | Path,
) -> Mapping[str, VerifiedRawArtifact]:
    """Verify and bind canonical raw-artifact rows by namespaced candidate ID."""

    lexical_root = Path(os.path.abspath(os.fspath(Path(raw_html_dir).expanduser())))
    try:
        if lexical_root.is_symlink():
            raise PacketInputPlanningError(
                f"raw docket HTML root must not be a symlink: {lexical_root}"
            )
        resolved_root = lexical_root.resolve(strict=True)
    except OSError as exc:
        raise PacketInputPlanningError(
            f"raw docket HTML root is unavailable: {lexical_root}"
        ) from exc
    if not resolved_root.is_dir():
        raise PacketInputPlanningError(
            f"raw docket HTML root is not a directory: {lexical_root}"
        )

    artifacts: dict[str, VerifiedRawArtifact] = {}
    paths: dict[Path, str] = {}
    for line_number, record in enumerate(records, start=1):
        candidate_id = _required_str(record, "candidate_id")
        namespaced_candidate = _COURTLISTENER_DOCKET_CANDIDATE_ID.fullmatch(
            candidate_id
        )
        if (
            candidate_id.startswith(_COURTLISTENER_DOCKET_CANDIDATE_PREFIX)
            and namespaced_candidate is None
        ):
            raise PacketInputPlanningError(
                "raw-artifact manifest contains a nonnumeric CourtListener docket "
                f"candidate alias on line {line_number}: {candidate_id}"
            )
        if candidate_id in artifacts:
            raise PacketInputPlanningError(
                f"duplicate raw-artifact candidate binding: {candidate_id}"
            )
        raw_path = _required_str(record, "path")
        supplied_path = Path(raw_path).expanduser()
        lexical_path = Path(
            os.path.abspath(
                os.fspath(
                    supplied_path
                    if supplied_path.is_absolute()
                    else lexical_root / supplied_path
                )
            )
        )
        try:
            relative_path = lexical_path.relative_to(lexical_root)
        except ValueError as exc:
            raise PacketInputPlanningError(
                "raw-artifact path escapes --raw-html-dir on line "
                f"{line_number}: {lexical_path}"
            ) from exc
        if lexical_path in paths:
            raise PacketInputPlanningError(
                "duplicate raw-artifact path binding for candidates "
                f"{paths[lexical_path]} and {candidate_id}: {lexical_path}"
            )
        if (
            namespaced_candidate is not None
            and lexical_path.name != f"{namespaced_candidate.group('docket_id')}.html"
        ):
            raise PacketInputPlanningError(
                "raw-artifact candidate/path ownership mismatch on line "
                f"{line_number}: {candidate_id} cannot own {lexical_path.name}"
            )

        current = lexical_root
        try:
            for component in relative_path.parts:
                current /= component
                mode = current.lstat().st_mode
                if stat.S_ISLNK(mode):
                    raise PacketInputPlanningError(
                        f"raw-artifact path contains a symlink: {lexical_path}"
                    )
            if not stat.S_ISREG(lexical_path.lstat().st_mode):
                raise PacketInputPlanningError(
                    f"raw-artifact path is not a regular file: {lexical_path}"
                )
            resolved_path = lexical_path.resolve(strict=True)
        except PacketInputPlanningError:
            raise
        except OSError as exc:
            raise PacketInputPlanningError(
                f"raw-artifact path is unavailable: {lexical_path}"
            ) from exc
        if not resolved_path.is_relative_to(resolved_root):
            raise PacketInputPlanningError(
                f"raw-artifact resolved path escapes --raw-html-dir: {lexical_path}"
            )

        expected_byte_count = record.get("byte_count")
        if (
            not isinstance(expected_byte_count, int)
            or isinstance(expected_byte_count, bool)
            or expected_byte_count < 0
        ):
            raise PacketInputPlanningError(
                f"raw-artifact byte_count is invalid on line {line_number}"
            )
        expected_sha256 = record.get("sha256")
        if (
            not isinstance(expected_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None
        ):
            raise PacketInputPlanningError(
                f"raw-artifact sha256 is invalid on line {line_number}"
            )
        try:
            payload = lexical_path.read_bytes()
        except OSError as exc:
            raise PacketInputPlanningError(
                f"raw-artifact path is unreadable: {lexical_path}"
            ) from exc
        if len(payload) != expected_byte_count:
            raise PacketInputPlanningError(
                f"raw-artifact byte_count mismatch: {lexical_path}"
            )
        actual_sha256 = hashlib.sha256(payload).hexdigest()
        if actual_sha256 != expected_sha256:
            raise PacketInputPlanningError(
                f"raw-artifact sha256 mismatch: {lexical_path}"
            )
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise PacketInputPlanningError(
                f"raw-artifact is not UTF-8: {lexical_path}"
            ) from exc
        artifacts[candidate_id] = VerifiedRawArtifact(
            manifest_candidate_id=candidate_id,
            manifest_path=raw_path,
            path=lexical_path,
            text=text,
            sha256=actual_sha256,
            byte_count=len(payload),
        )
        paths[lexical_path] = candidate_id
    return artifacts


def bind_verified_raw_artifacts(
    selection_candidate_ids: Iterable[str],
    *,
    artifacts: Mapping[str, VerifiedRawArtifact],
) -> Mapping[str, VerifiedRawArtifactBinding]:
    """Bind selections to exact or canonical CourtListener manifest identities.

    Only the exact ``courtlistener-docket-<digits>`` namespace may be stripped.
    The complete manifest is indexed first so exact/alias collisions fail even
    when record ordering would otherwise make one match appear preferable.
    """

    artifacts_by_binding_id: dict[str, list[VerifiedRawArtifact]] = defaultdict(list)
    for manifest_candidate_id, artifact in artifacts.items():
        if artifact.manifest_candidate_id != manifest_candidate_id:
            raise PacketInputPlanningError(
                "raw-artifact manifest identity drift for binding key: "
                f"{manifest_candidate_id}"
            )
        artifacts_by_binding_id[manifest_candidate_id].append(artifact)
        match = _COURTLISTENER_DOCKET_CANDIDATE_ID.fullmatch(manifest_candidate_id)
        if match is not None:
            artifacts_by_binding_id[match.group("docket_id")].append(artifact)

    for binding_id, matches in artifacts_by_binding_id.items():
        unique_manifest_ids = {artifact.manifest_candidate_id for artifact in matches}
        if len(unique_manifest_ids) > 1:
            raise PacketInputPlanningError(
                "raw-artifact candidate alias collision for "
                f"{binding_id}: {', '.join(sorted(unique_manifest_ids))}"
            )

    bindings: dict[str, VerifiedRawArtifactBinding] = {}
    owners_by_manifest_id: dict[str, str] = {}
    for selection_candidate_id in selection_candidate_ids:
        if not selection_candidate_id:
            raise PacketInputPlanningError(
                "selection candidate_id for raw-artifact ownership must be non-empty"
            )
        if selection_candidate_id in bindings:
            raise PacketInputPlanningError(
                "duplicate selection candidate_id in raw-artifact ownership: "
                f"{selection_candidate_id}"
            )
        matches = artifacts_by_binding_id.get(selection_candidate_id, ())
        if len(matches) != 1:
            if not matches:
                raise PacketInputPlanningError(
                    "raw-artifacts manifest missing candidate binding: "
                    f"{selection_candidate_id}"
                )
            raise PacketInputPlanningError(
                "raw-artifacts manifest has multiple candidate matches: "
                f"{selection_candidate_id}"
            )
        artifact = matches[0]
        prior_owner = owners_by_manifest_id.get(artifact.manifest_candidate_id)
        if prior_owner is not None:
            raise PacketInputPlanningError(
                "raw-artifact manifest binding has multiple candidate owners: "
                f"{prior_owner} and {selection_candidate_id} own "
                f"{artifact.manifest_candidate_id}"
            )
        owners_by_manifest_id[artifact.manifest_candidate_id] = selection_candidate_id
        bindings[selection_candidate_id] = VerifiedRawArtifactBinding(
            selection_candidate_id=selection_candidate_id,
            manifest_candidate_id=artifact.manifest_candidate_id,
            binding_kind=(
                "exact_candidate_id"
                if selection_candidate_id == artifact.manifest_candidate_id
                else "courtlistener_docket_numeric_alias"
            ),
            artifact=artifact,
        )
    return bindings


@dataclass(frozen=True, slots=True)
class PacketInputPlan:
    """Artifacts needed by build-packets and private-store export."""

    packet_build_records: tuple[dict[str, Any], ...]
    document_manifest_records: tuple[dict[str, Any], ...]
    candidate_manifest_records: tuple[dict[str, Any], ...]
    extracted_text_records: tuple[dict[str, Any], ...]
    exclusion_ledger_records: tuple[dict[str, Any], ...] = ()

    @property
    def case_count(self) -> int:
        return len(self.packet_build_records)


def plan_packet_build_inputs(
    *,
    selection_records: Iterable[Mapping[str, Any]],
    download_records: Iterable[Mapping[str, Any]],
    parser_records: Iterable[Mapping[str, Any]],
    prediction_unit_records: Iterable[Mapping[str, Any]],
    raw_html_dir: str | Path,
    raw_artifact_records: Iterable[Mapping[str, Any]] | None = None,
    document_root: str | Path,
    markdown_root: str | Path,
    source_dir: str | Path,
    generated_at: datetime | None = None,
    search_query: str = "refined MTD decision terms",
    search_window: str = "not recorded",
    decision_filed_on_or_after: date | None = None,
) -> PacketInputPlan:
    """Create packet-build and private-store manifest rows from acquisition rows."""

    timestamp = generated_at or datetime.now(UTC)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise PacketInputPlanningError("generated_at must be timezone-aware")

    selections = tuple(selection_records)
    raw_html_root = Path(raw_html_dir)
    verified_raw_artifacts = (
        load_verified_raw_artifacts(
            raw_artifact_records,
            raw_html_dir=raw_html_root,
        )
        if raw_artifact_records is not None
        else None
    )
    source_root = Path(source_dir).resolve()
    document_root_path = Path(document_root).resolve()
    markdown_root_path = Path(markdown_root).resolve()
    downloads = _index_by_candidate_and_document(download_records)
    parser_by_key = _index_by_candidate_and_document(parser_records)
    try:
        finalized_records = require_finalized_envelopes(prediction_unit_records)
    except UnitizationReviewError as exc:
        raise PacketInputPlanningError(
            f"prediction units must be finalized: {exc}"
        ) from exc
    prediction_units = _index_prediction_units(finalized_records)
    excluded_candidate_ids = {
        _required_str(record, "candidate_id")
        for record in finalized_records
        if record.get("status") == "candidate_excluded"
    }
    active_selection_candidate_ids = tuple(
        _required_str(selection, "candidate_id")
        for selection in selections
        if _required_str(selection, "candidate_id") not in excluded_candidate_ids
    )
    raw_artifact_bindings = (
        bind_verified_raw_artifacts(
            active_selection_candidate_ids,
            artifacts=verified_raw_artifacts,
        )
        if verified_raw_artifacts is not None
        else None
    )

    packet_build: list[dict[str, Any]] = []
    document_manifest: list[dict[str, Any]] = []
    candidate_manifest: list[dict[str, Any]] = []
    extracted_texts: list[dict[str, Any]] = []
    exclusion_ledger: list[dict[str, Any]] = []

    for selection in selections:
        candidate_id = _required_str(selection, "candidate_id")
        if candidate_id in excluded_candidate_ids:
            continue
        planned = _plan_candidate(
            selection,
            downloads=downloads,
            parser_records=parser_by_key,
            prediction_units=prediction_units,
            raw_html_root=raw_html_root,
            raw_artifact_binding=(
                raw_artifact_bindings[candidate_id]
                if raw_artifact_bindings is not None
                else None
            ),
            document_root=document_root_path,
            markdown_root=markdown_root_path,
            source_root=source_root,
            generated_at=timestamp,
            search_query=search_query,
            search_window=search_window,
            decision_filed_on_or_after=decision_filed_on_or_after,
        )
        if planned.packet_build_record is not None:
            packet_build.append(planned.packet_build_record)
        document_manifest.extend(planned.document_manifest_records)
        candidate_manifest.append(planned.candidate_manifest_record)
        extracted_texts.extend(planned.extracted_text_records)
        exclusion_ledger.extend(planned.exclusion_ledger_records)

    return PacketInputPlan(
        packet_build_records=tuple(packet_build),
        document_manifest_records=tuple(document_manifest),
        candidate_manifest_records=tuple(candidate_manifest),
        extracted_text_records=tuple(extracted_texts),
        exclusion_ledger_records=tuple(exclusion_ledger),
    )


@dataclass(frozen=True, slots=True)
class _PlannedCandidate:
    packet_build_record: dict[str, Any] | None
    document_manifest_records: tuple[dict[str, Any], ...]
    candidate_manifest_record: dict[str, Any]
    extracted_text_records: tuple[dict[str, Any], ...]
    exclusion_ledger_records: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True, slots=True)
class _DocketEntryPlan:
    entries: tuple[ControlledDocketMarkdownEntry, ...]
    exclusion_ledger_records: tuple[dict[str, Any], ...]


def _plan_candidate(
    selection: Mapping[str, Any],
    *,
    downloads: Mapping[tuple[str, str], Mapping[str, Any]],
    parser_records: Mapping[tuple[str, str], Mapping[str, Any]],
    prediction_units: Mapping[str, tuple[dict[str, Any], ...]],
    raw_html_root: Path,
    raw_artifact_binding: VerifiedRawArtifactBinding | None,
    document_root: Path,
    markdown_root: Path,
    source_root: Path,
    generated_at: datetime,
    search_query: str,
    search_window: str,
    decision_filed_on_or_after: date | None,
) -> _PlannedCandidate:
    candidate_id = _required_str(selection, "candidate_id")
    units = prediction_units.get(candidate_id)
    if units is None:
        raise PacketInputPlanningError(
            f"prediction units missing for candidate: {candidate_id}"
        )
    if raw_artifact_binding is None:
        html_path = raw_html_root / f"{candidate_id}.html"
        if not html_path.is_file():
            raise PacketInputPlanningError(f"raw docket HTML missing: {html_path}")
        html_text = html_path.read_text(encoding="utf-8")
        raw_artifact_provenance: dict[str, str | int] | None = None
    else:
        if raw_artifact_binding.selection_candidate_id != candidate_id:
            raise PacketInputPlanningError(
                "raw-artifact ownership does not match planned candidate: "
                f"{raw_artifact_binding.selection_candidate_id} != {candidate_id}"
            )
        artifact = raw_artifact_binding.artifact
        html_text = artifact.text
        raw_artifact_provenance = raw_artifact_binding.to_provenance_record()
    page = parse_courtlistener_docket_html(
        html_text,
        source_url=_optional_str(selection, "source_url"),
        docket_id=candidate_id,
    )
    docket_screen = screen_courtlistener_docket_for_mtd_decision(
        page,
        candidate_text=_optional_str(selection, "case_name"),
    )
    docket_screen_record = docket_screen.to_record()
    if decision_filed_on_or_after is not None:
        docket_screen_record = _docket_screen_with_first_disposition_anchor(
            docket_screen_record,
            decision_filed_on_or_after=decision_filed_on_or_after,
        )
    if decision_filed_on_or_after is not None and (
        _required_str(docket_screen_record, "status")
        == MtdDocketScreenStatus.EXCLUDED.value
    ):
        exclusion_record = _release_anchor_exclusion_record(
            selection,
            docket_screen=docket_screen_record,
            decision_filed_on_or_after=decision_filed_on_or_after,
        )
        return _PlannedCandidate(
            packet_build_record=None,
            document_manifest_records=(),
            candidate_manifest_record=_candidate_manifest_record(
                selection,
                documents=(),
                mtd_decision_screen=docket_screen_record,
                exclusion_ledger_entries=(exclusion_record,),
                raw_artifact_provenance=raw_artifact_provenance,
            ),
            extracted_text_records=(),
            exclusion_ledger_records=(exclusion_record,),
        )

    original_to_packet_id: dict[str, str] = {}
    source_documents: list[dict[str, Any]] = []
    parsed_documents: list[dict[str, Any]] = []
    candidate_documents: list[dict[str, Any]] = []
    document_manifest: list[dict[str, Any]] = []
    extracted_texts: list[dict[str, Any]] = []
    exclusion_ledger_records: list[dict[str, Any]] = []

    for document in _record_sequence(selection.get("documents"), "documents"):
        original_id = _required_str(document, "source_document_id")
        packet_document_id = _packet_document_id(candidate_id, original_id)
        original_to_packet_id[original_id] = packet_document_id
        download = _required_indexed_record(
            downloads,
            candidate_id=candidate_id,
            source_document_id=original_id,
            label="download manifest",
        )
        parser_record = parser_records.get((candidate_id, original_id))
        source_record = _source_document_record(
            selection=selection,
            document=document,
            download=download,
            packet_document_id=packet_document_id,
            generated_at=generated_at,
        )
        is_public_document = _required_str(
            source_record,
            "redaction_or_seal_status",
        ) in {"public", "redacted"}
        if is_public_document:
            document_manifest.append(
                {
                    "source_document_id": packet_document_id,
                    "path": _manifest_path(
                        document_root / _required_str(download, "local_path"),
                        source_root=source_root,
                    ),
                }
            )
        if (
            is_public_document
            and parser_record is not None
            and _optional_str(parser_record, "status") == "succeeded"
        ):
            if _required_bool(source_record, "is_mounted_for_model"):
                document_leakage = _document_leakage_result(
                    parser_record,
                    packet_document_id=packet_document_id,
                    markdown_root=markdown_root,
                    evaluation_timestamp=generated_at,
                )
                if document_leakage.findings:
                    exclusion_ledger_records.append(
                        _document_leakage_exclusion_record(
                            leakage_result=document_leakage,
                            packet_document_id=packet_document_id,
                            candidate_id=candidate_id,
                            case_id=_required_str(selection, "case_id"),
                            court=_optional_str(selection, "court"),
                            decision_date=_optional_date(selection, "decision_date")
                            or _optional_date(selection, "decision_entered_date"),
                        )
                    )
                    source_record = {
                        **source_record,
                        "is_mounted_for_model": False,
                        "contains_target_outcome": True,
                        "packet_section": "post_decision",
                        "notes": (
                            f"{_required_str(source_record, 'notes')}; excluded "
                            "from model packet by packet-time outcome leakage screen"
                        ),
                    }
            parsed = _parsed_document_record(
                parser_record,
                packet_document_id=packet_document_id,
                markdown_root=markdown_root,
            )
            parsed_documents.append(parsed)
            extracted_text = parsed.get("extracted_text")
            if isinstance(extracted_text, Mapping):
                extracted_texts.append(dict(cast(Mapping[str, Any], extracted_text)))
        source_documents.append(source_record)
        candidate_documents.append(_candidate_document_record(source_record))

    docket_entry_plan = _docket_entries(
        page.entries,
        selection=selection,
        source_document_ids_by_entry=_source_document_ids_by_entry(source_documents),
        generated_at=generated_at,
    )
    exclusion_ledger_records.extend(docket_entry_plan.exclusion_ledger_records)
    if exclusion_ledger_records:
        exclusion_record = _merge_leakage_exclusion_records(
            selection,
            exclusion_ledger_records,
        )
        return _PlannedCandidate(
            packet_build_record=None,
            document_manifest_records=tuple(document_manifest),
            candidate_manifest_record=_candidate_manifest_record(
                selection,
                documents=candidate_documents,
                mtd_decision_screen=docket_screen_record,
                exclusion_ledger_entries=(exclusion_record,),
                raw_artifact_provenance=raw_artifact_provenance,
            ),
            extracted_text_records=tuple(extracted_texts),
            exclusion_ledger_records=(exclusion_record,),
        )
    packet_build_record = {
        "candidate_id": candidate_id,
        "case_id": _required_str(selection, "case_id"),
        "court": _required_str(selection, "court"),
        "docket_number": _required_str(selection, "docket_number"),
        "decision_date": _format_optional_date(_selection_decision_date(selection)),
        "related_family_id": _optional_str(selection, "related_family_id"),
        "mdl_family_id": _optional_str(selection, "mdl_family_id"),
        "case_type_stratum": _optional_str(selection, "case_type_stratum"),
        "generated_at": _format_datetime(generated_at),
        "docket_markdown": _controlled_docket_record(
            render_controlled_docket_markdown(
                _docket_metadata(
                    selection,
                    generated_at=generated_at,
                    search_query=search_query,
                    search_window=search_window,
                ),
                docket_entry_plan.entries,
            )
        ),
        "mtd_decision_screen": docket_screen_record,
        "documents": source_documents,
        "parsed_documents": parsed_documents,
        "prediction_units": _prediction_units_with_packet_document_ids(
            units,
            original_to_packet_id=original_to_packet_id,
        ),
        "target_docket_entry_numbers": _target_docket_entry_numbers(
            selection,
        ),
        "metadata": _packet_metadata(
            selection,
            docket_screen=docket_screen_record,
            search_query=search_query,
            search_window=search_window,
            decision_filed_on_or_after=decision_filed_on_or_after,
        ),
        **(
            {"raw_artifact_provenance": raw_artifact_provenance}
            if raw_artifact_provenance is not None
            else {}
        ),
    }
    return _PlannedCandidate(
        packet_build_record=packet_build_record,
        document_manifest_records=tuple(document_manifest),
        candidate_manifest_record=_candidate_manifest_record(
            selection,
            documents=candidate_documents,
            mtd_decision_screen=docket_screen_record,
            exclusion_ledger_entries=exclusion_ledger_records,
            raw_artifact_provenance=raw_artifact_provenance,
        ),
        extracted_text_records=tuple(extracted_texts),
        exclusion_ledger_records=tuple(exclusion_ledger_records),
    )


def _target_docket_entry_numbers(selection: Mapping[str, Any]) -> tuple[int, ...]:
    target_entries = set(_int_tuple(selection.get("target_motion_entry_numbers")))
    for document in _record_sequence(selection.get("documents"), "documents"):
        role = _optional_str(document, "document_role")
        if role not in {
            DocumentRole.MTD_NOTICE.value,
            DocumentRole.MTD_MEMORANDUM.value,
        }:
            continue
        entry_number = _optional_int(document, "docket_entry_number")
        if entry_number is not None:
            target_entries.add(entry_number)
    return tuple(sorted(target_entries))


def _index_by_candidate_and_document(
    records: Iterable[Mapping[str, Any]],
) -> dict[tuple[str, str], Mapping[str, Any]]:
    return {
        (
            _required_str(record, "candidate_id"),
            _required_str(record, "source_document_id"),
        ): record
        for record in records
    }


def _index_prediction_units(
    records: Iterable[Mapping[str, Any]],
) -> dict[str, tuple[dict[str, Any], ...]]:
    units_by_candidate: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        candidate_id = _required_str(record, "candidate_id")
        if "prediction_units" in record:
            units_by_candidate[candidate_id].extend(
                dict(unit)
                for unit in _record_sequence(
                    record.get("prediction_units"),
                    "prediction_units",
                )
            )
        else:
            unit = dict(record)
            unit.pop("candidate_id", None)
            units_by_candidate[candidate_id].append(unit)
    return {
        candidate_id: tuple(units)
        for candidate_id, units in units_by_candidate.items()
        if units
    }


def _required_indexed_record(
    records: Mapping[tuple[str, str], Mapping[str, Any]],
    *,
    candidate_id: str,
    source_document_id: str,
    label: str,
) -> Mapping[str, Any]:
    key = (candidate_id, source_document_id)
    try:
        return records[key]
    except KeyError as exc:
        raise PacketInputPlanningError(
            f"{label} missing {candidate_id}/{source_document_id}"
        ) from exc


def _source_document_record(
    *,
    selection: Mapping[str, Any],
    document: Mapping[str, Any],
    download: Mapping[str, Any],
    packet_document_id: str,
    generated_at: datetime,
) -> dict[str, Any]:
    role = DocumentRole(_required_str(document, "document_role"))
    model_visible = _required_bool(document, "model_visible")
    contains_target_outcome = _required_bool(document, "contains_target_outcome")
    is_outcome_document = contains_target_outcome or role in {
        DocumentRole.ORDER,
        DocumentRole.DECISION,
    }
    redaction_or_seal_status = _redaction_or_seal_status(document, download)
    is_public_document = redaction_or_seal_status in {"public", "redacted"}
    return {
        "source_provider": _optional_str(download, "source_provider")
        or "courtlistener",
        "source_case_id": _required_str(selection, "case_id"),
        "source_document_id": packet_document_id,
        "court": _required_str(selection, "court"),
        "docket_number": _required_str(selection, "docket_number"),
        "document_role": role.value,
        "retrieved_at": _format_datetime(generated_at),
        "source_url_or_reference": _required_str(download, "source_url"),
        "sha256": _required_str(download, "sha256"),
        "is_predecision_material": not is_outcome_document,
        "is_mounted_for_model": (
            model_visible and not is_outcome_document and is_public_document
        ),
        "availability_status": (
            AvailabilityStatus.AVAILABLE.value
            if is_public_document
            else AvailabilityStatus.RESTRICTED.value
        ),
        "redaction_or_seal_status": redaction_or_seal_status,
        "docket_entry_number": _optional_int(document, "docket_entry_number"),
        "contains_target_outcome": contains_target_outcome,
        "packet_section": _packet_section(role, contains_target_outcome),
        "notes": (
            "Prepared from public CourtListener/RECAP acquisition manifest; "
            "original_source_document_id="
            f"{_required_str(document, 'source_document_id')}"
            + (
                ""
                if is_public_document
                else "; non-public source retained as audit metadata only and "
                "never mounted or forwarded to packet artifacts"
            )
        ),
    }


def _redaction_or_seal_status(
    document: Mapping[str, Any],
    download: Mapping[str, Any],
) -> str:
    statuses: list[str] = []
    for record in (document, download):
        for field_name, restricted_status in (
            ("is_sealed", "sealed"),
            ("is_private", "private"),
            ("is_restricted", "restricted"),
        ):
            value = record.get(field_name)
            if value is not None and not isinstance(value, bool):
                return "restricted"
            if value is True:
                statuses.append(restricted_status)
        availability_status = _optional_str(record, "availability_status")
        if availability_status is not None and availability_status.strip().lower() in {
            "private",
            "restricted",
            "sealed",
        }:
            statuses.append(availability_status.strip().lower())
        for field_name in ("redaction_or_seal_status", "seal_status"):
            status = _optional_str(record, field_name)
            if status is not None:
                statuses.append(status.strip().lower())

    for restricted_status in ("sealed", "private", "restricted", "unknown"):
        if restricted_status in statuses:
            return restricted_status
    for status in statuses:
        if status not in {"public", "redacted"}:
            return status
    if not _has_restriction_evidence(document, download):
        return "unknown"
    if not any(status in {"public", "redacted"} for status in statuses):
        return "unknown"
    return "redacted" if "redacted" in statuses else "public"


def _has_restriction_evidence(*records: Mapping[str, Any]) -> bool:
    for record in records:
        value = record.get("restriction_evidence")
        if isinstance(value, str):
            if value.strip():
                return True
            continue
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            if any(
                isinstance(item, str) and bool(item.strip())
                for item in cast(Sequence[object], value)
            ):
                return True
    return False


def _packet_section(role: DocumentRole, contains_target_outcome: bool) -> str:
    if contains_target_outcome or role in {DocumentRole.ORDER, DocumentRole.DECISION}:
        return "post_decision"
    if role in {DocumentRole.COMPLAINT, DocumentRole.AMENDED_COMPLAINT}:
        return "pleadings"
    if role in {
        DocumentRole.MTD_NOTICE,
        DocumentRole.MTD_MEMORANDUM,
        DocumentRole.OPPOSITION,
        DocumentRole.REPLY,
    }:
        return "briefing"
    return "other"


def _candidate_document_record(source_record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "source_provider": _required_str(source_record, "source_provider"),
        "source_document_id": _required_str(source_record, "source_document_id"),
        "document_role": _required_str(source_record, "document_role"),
        "sha256": _required_str(source_record, "sha256"),
        "source_url_or_reference": _required_str(
            source_record,
            "source_url_or_reference",
        ),
        "is_mounted_for_model": _required_bool(
            source_record,
            "is_mounted_for_model",
        ),
    }


def _candidate_manifest_record(
    selection: Mapping[str, Any],
    *,
    documents: Sequence[Mapping[str, Any]],
    mtd_decision_screen: Mapping[str, Any] | None = None,
    exclusion_ledger_entries: Sequence[Mapping[str, Any]] = (),
    raw_artifact_provenance: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "candidate_id": _required_str(selection, "candidate_id"),
        "case_id": _required_str(selection, "case_id"),
        "case_name": _optional_str(selection, "case_name"),
        "court": _required_str(selection, "court"),
        "docket_number": _required_str(selection, "docket_number"),
        "nature_of_suit": _optional_str(selection, "nature_of_suit"),
        "nos_macro_category": _optional_str(selection, "nos_macro_category"),
        "related_family_id": _optional_str(selection, "related_family_id"),
        "mdl_family_id": _optional_str(selection, "mdl_family_id"),
        "case_type_stratum": _optional_str(selection, "case_type_stratum"),
        "source_url": _optional_str(selection, "source_url"),
        "documents": [dict(document) for document in documents],
        "mtd_decision_screen": (
            dict(mtd_decision_screen) if mtd_decision_screen is not None else None
        ),
        "exclusion_ledger_entries": [dict(entry) for entry in exclusion_ledger_entries],
        **(
            {"raw_artifact_provenance": dict(raw_artifact_provenance)}
            if raw_artifact_provenance is not None
            else {}
        ),
    }
    return {**record, "manifest_record_hash": _record_hash(record)}


def _packet_metadata(
    selection: Mapping[str, Any],
    *,
    docket_screen: Mapping[str, Any],
    search_query: str,
    search_window: str,
    decision_filed_on_or_after: date | None,
) -> dict[str, str]:
    metadata = {
        "case_name": _optional_str(selection, "case_name") or "",
        "source_url": _optional_str(selection, "source_url") or "",
        "search_query": search_query,
        "search_window": search_window,
        "mtd_decision_screen_status": _required_str(docket_screen, "status"),
    }
    decision_date = _selection_decision_date(selection)
    if decision_date is not None:
        metadata["decision_date"] = decision_date.isoformat()
    if decision_filed_on_or_after is not None:
        metadata["decision_filed_on_or_after"] = decision_filed_on_or_after.isoformat()
    for field_name in (
        "nature_of_suit",
        "nos_macro_category",
        "case_type_stratum",
    ):
        value = _optional_str(selection, field_name)
        if value is not None:
            metadata[field_name] = value
    return metadata


def _selection_decision_date(selection: Mapping[str, Any]) -> date | None:
    return _optional_date(selection, "decision_date") or _optional_date(
        selection,
        "decision_entered_date",
    )


def _format_optional_date(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


def _release_anchor_exclusion_record(
    selection: Mapping[str, Any],
    *,
    docket_screen: Mapping[str, Any],
    decision_filed_on_or_after: date,
) -> dict[str, Any]:
    screen_reasons = tuple(_str_tuple(docket_screen.get("exclusion_reasons")))
    first_disposition_date = _optional_str(
        docket_screen,
        "first_written_mtd_disposition_date",
    )
    return ExclusionLedgerEntry(
        candidate_id=_required_str(selection, "candidate_id"),
        case_id=_required_str(selection, "case_id"),
        court=_optional_str(selection, "court"),
        decision_date=_optional_date(selection, "decision_date")
        or _optional_date(selection, "decision_entered_date"),
        stage=ExclusionStage.ELIGIBILITY,
        reason=ExclusionReason.DECISION_BEFORE_RELEASE_ANCHOR.value,
        secondary_reasons=screen_reasons,
        source_entry_ids=tuple(_decision_entry_source_ids(docket_screen)),
        notes=(
            "Candidate excluded because its chronologically first written MTD "
            "disposition was not proven to be on or after "
            f"{decision_filed_on_or_after.isoformat()}; "
            f"first_disposition_date={first_disposition_date or 'unverified'}; "
            f"screen_status={_required_str(docket_screen, 'status')}"
        ),
    ).to_record()


def _docket_screen_with_first_disposition_anchor(
    docket_screen: Mapping[str, Any],
    *,
    decision_filed_on_or_after: date,
) -> dict[str, Any]:
    record = dict(docket_screen)
    decision_entries = _record_sequence(
        docket_screen.get("decision_entries"),
        "decision_entries",
    )
    dated_entries: list[tuple[date, Mapping[str, Any]]] = []
    undated_entries: list[Mapping[str, Any]] = []
    for entry in decision_entries:
        filed_date = parse_courtlistener_filed_date(_optional_str(entry, "filed_at"))
        if filed_date is None:
            undated_entries.append(entry)
        else:
            dated_entries.append((filed_date, entry))

    first_date: date | None = None
    first_entry: Mapping[str, Any] | None = None
    exclusion_reasons = tuple(_str_tuple(docket_screen.get("exclusion_reasons")))
    if undated_entries:
        first_entry = undated_entries[0]
        exclusion_reasons = ("first_written_mtd_disposition_date_unverified",)
    elif dated_entries:
        first_date, first_entry = min(dated_entries, key=lambda item: item[0])
        if first_date < decision_filed_on_or_after:
            exclusion_reasons = ("first_written_mtd_disposition_before_release_anchor",)
    elif not exclusion_reasons:
        exclusion_reasons = ("first_written_mtd_disposition_not_found",)

    anchor_passed = (
        first_date is not None
        and first_date >= decision_filed_on_or_after
        and not undated_entries
    )
    record.update(
        {
            "status": (
                _required_str(docket_screen, "status")
                if anchor_passed
                else MtdDocketScreenStatus.EXCLUDED.value
            ),
            "exclusion_reasons": list(exclusion_reasons),
            "first_written_mtd_disposition_entry": (
                None if first_entry is None else dict(first_entry)
            ),
            "first_written_mtd_disposition_date": (
                None if first_date is None else first_date.isoformat()
            ),
            "decision_filed_on_or_after": decision_filed_on_or_after.isoformat(),
            "first_written_mtd_disposition_anchor_passed": anchor_passed,
        }
    )
    return record


def _decision_entry_source_ids(docket_screen: Mapping[str, Any]) -> tuple[str, ...]:
    first_entry = docket_screen.get("first_written_mtd_disposition_entry")
    if isinstance(first_entry, Mapping):
        first_entry_record = cast(Mapping[str, Any], first_entry)
        row_id = _optional_str(first_entry_record, "row_id")
        entry_number = _optional_str(first_entry_record, "entry_number")
        if row_id is not None:
            return (row_id,)
        if entry_number is not None:
            return (f"entry-{entry_number}",)
    source_ids: list[str] = []
    for entry in _record_sequence(
        docket_screen.get("decision_entries"),
        "decision_entries",
    ):
        row_id = _optional_str(entry, "row_id")
        entry_number = _optional_str(entry, "entry_number")
        if row_id is not None:
            source_ids.append(row_id)
        elif entry_number is not None:
            source_ids.append(f"entry-{entry_number}")
    return tuple(source_ids)


def _parsed_document_record(
    parser_record: Mapping[str, Any],
    *,
    packet_document_id: str,
    markdown_root: Path,
) -> dict[str, Any]:
    markdown_path = Path(_required_str(parser_record, "markdown_path"))
    resolved_markdown_path = (
        markdown_path if markdown_path.is_absolute() else markdown_root / markdown_path
    )
    extracted = parser_record.get("extracted_text")
    extracted_text = None
    extraction_method = "mistral_markdown"
    if isinstance(extracted, Mapping):
        extracted_mapping = cast(Mapping[str, Any], extracted)
        extracted_text = {
            **dict(extracted_mapping),
            "source_document_id": packet_document_id,
        }
        extraction_method = (
            _optional_str(extracted_mapping, "extraction_method") or extraction_method
        )
    return {
        "source_document_id": packet_document_id,
        "markdown_path": str(resolved_markdown_path),
        "extraction_method": extraction_method,
        "quality_flags": list(_str_tuple(parser_record.get("quality_flags"))),
        "extracted_text": extracted_text,
    }


def _controlled_docket_record(
    artifacts: ControlledDocketMarkdownArtifacts,
) -> dict[str, str]:
    return {
        "model_visible_markdown": artifacts.model_visible_markdown,
        "audit_markdown": artifacts.audit_markdown,
    }


def _docket_metadata(
    selection: Mapping[str, Any],
    *,
    generated_at: datetime,
    search_query: str,
    search_window: str,
) -> DocketMarkdownMetadata:
    candidate_id = _required_str(selection, "candidate_id")
    return DocketMarkdownMetadata(
        candidate_id=candidate_id,
        case_id=_required_str(selection, "case_id"),
        case_name=_optional_str(selection, "case_name") or candidate_id,
        court=_required_str(selection, "court"),
        docket_number=_required_str(selection, "docket_number"),
        source_provider="courtlistener",
        source_case_id=candidate_id,
        source_url=_optional_str(selection, "source_url") or "not recorded",
        search_query=search_query,
        search_window=search_window,
        discovered_at=_format_datetime(generated_at),
    )


def _docket_entries(
    entries: Iterable[CourtListenerWebDocketEntry],
    *,
    selection: Mapping[str, Any],
    source_document_ids_by_entry: Mapping[int, tuple[str, ...]],
    generated_at: datetime,
) -> _DocketEntryPlan:
    decision_entry_numbers = _required_int_tuple(selection, "decision_entry_numbers")
    if not decision_entry_numbers:
        raise PacketInputPlanningError("decision_entry_numbers must not be empty")
    decision_entries = set(decision_entry_numbers)
    decision_floor = min(decision_entries) if decision_entries else None
    rendered: list[ControlledDocketMarkdownEntry] = []
    leakage_sources: list[LeakageSource] = []
    docket_entries = tuple(entries)
    for entry in docket_entries:
        entry_number = _entry_number(entry)
        predecision = entry_number is not None and (
            decision_floor is None or entry_number < decision_floor
        )
        docket_entry_id = entry.row_id or f"entry-{entry.entry_number or 'unknown'}"
        if predecision and entry.text.strip():
            leakage_sources.append(
                LeakageSource(
                    source_id=docket_entry_id,
                    source_kind=LeakageSourceKind.DOCKET_ENTRY,
                    text=entry.text,
                    observed_at=generated_at,
                )
            )
    leakage_result = detect_outcome_leakage(
        tuple(leakage_sources),
        evaluation_timestamp=generated_at,
    )
    leakage_source_ids = {finding.source_id for finding in leakage_result.findings}
    for entry in docket_entries:
        entry_number = _entry_number(entry)
        predecision = entry_number is not None and (
            decision_floor is None or entry_number < decision_floor
        )
        docket_entry_id = entry.row_id or f"entry-{entry.entry_number or 'unknown'}"
        contains_target_outcome = (
            entry_number in decision_entries if entry_number is not None else False
        ) or docket_entry_id in leakage_source_ids
        rendered.append(
            ControlledDocketMarkdownEntry(
                docket_entry_id=docket_entry_id,
                entry_number=entry.entry_number,
                filed_at=entry.filed_at,
                entry_text=entry.text,
                packet_section="docket" if predecision else "post_decision",
                source_url=_entry_url(selection, entry_number),
                source_document_ids=source_document_ids_by_entry.get(
                    entry_number or -1,
                    (),
                ),
                is_predecision_material=predecision,
                contains_target_outcome=contains_target_outcome or not predecision,
                free_text_available=True,
            )
        )
    ledger_records: tuple[dict[str, Any], ...] = ()
    if leakage_result.findings:
        ledger_records = (
            ExclusionLedgerEntry.from_outcome_leakage(
                candidate_id=_required_str(selection, "candidate_id"),
                case_id=_required_str(selection, "case_id"),
                court=_optional_str(selection, "court"),
                decision_date=_optional_date(selection, "decision_date")
                or _optional_date(selection, "decision_entered_date"),
                leakage_result=leakage_result,
            ).to_record(),
        )
    return _DocketEntryPlan(
        entries=tuple(rendered),
        exclusion_ledger_records=ledger_records,
    )


def _document_leakage_result(
    parser_record: Mapping[str, Any],
    *,
    packet_document_id: str,
    markdown_root: Path,
    evaluation_timestamp: datetime,
) -> OutcomeLeakageFilterResult:
    markdown_path = Path(_required_str(parser_record, "markdown_path"))
    resolved_markdown_path = (
        markdown_path if markdown_path.is_absolute() else markdown_root / markdown_path
    )
    text = resolved_markdown_path.read_text(encoding="utf-8")
    return detect_outcome_leakage(
        (
            LeakageSource(
                source_id=packet_document_id,
                source_kind=LeakageSourceKind.DOCUMENT_TEXT,
                text=text,
                observed_at=evaluation_timestamp,
            ),
        ),
        evaluation_timestamp=evaluation_timestamp,
    )


def _document_leakage_exclusion_record(
    *,
    leakage_result: OutcomeLeakageFilterResult,
    packet_document_id: str,
    candidate_id: str,
    case_id: str,
    court: str | None,
    decision_date: date | None,
) -> dict[str, Any]:
    if not leakage_result.findings:
        raise PacketInputPlanningError(
            "document leakage exclusion requires at least one finding"
        )
    return ExclusionLedgerEntry(
        candidate_id=candidate_id,
        case_id=case_id,
        court=court,
        decision_date=decision_date,
        stage=ExclusionStage.LEAKAGE,
        reason=ExclusionReason.OUTCOME_LEAKAGE.value,
        secondary_reasons=tuple(
            finding.leakage_type.value for finding in leakage_result.findings
        ),
        source_entry_ids=(),
        source_document_ids=(packet_document_id,),
        notes="; ".join(finding.reason for finding in leakage_result.findings),
    ).to_record()


def _merge_leakage_exclusion_records(
    selection: Mapping[str, Any],
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    secondary_reasons = _deduplicated_record_strings(
        records,
        "secondary_exclusion_reasons",
    )
    source_entry_ids = _deduplicated_record_strings(records, "source_entry_ids")
    source_document_ids = _deduplicated_record_strings(
        records,
        "source_document_ids",
    )
    notes = tuple(
        note
        for record in records
        if (note := _optional_str(record, "notes")) is not None
    )
    return ExclusionLedgerEntry(
        candidate_id=_required_str(selection, "candidate_id"),
        case_id=_required_str(selection, "case_id"),
        court=_optional_str(selection, "court"),
        decision_date=_optional_date(selection, "decision_date")
        or _optional_date(selection, "decision_entered_date"),
        stage=ExclusionStage.LEAKAGE,
        reason=ExclusionReason.OUTCOME_LEAKAGE.value,
        secondary_reasons=secondary_reasons,
        source_entry_ids=source_entry_ids,
        source_document_ids=source_document_ids,
        notes="; ".join(dict.fromkeys(notes)),
    ).to_record()


def _deduplicated_record_strings(
    records: Sequence[Mapping[str, Any]],
    field_name: str,
) -> tuple[str, ...]:
    values = (
        value for record in records for value in _str_tuple(record.get(field_name))
    )
    return tuple(dict.fromkeys(values))


def _source_document_ids_by_entry(
    documents: Iterable[Mapping[str, Any]],
) -> dict[int, tuple[str, ...]]:
    grouped: dict[int, list[str]] = defaultdict(list)
    for document in documents:
        entry_number = _optional_int(document, "docket_entry_number")
        if entry_number is not None:
            grouped[entry_number].append(_required_str(document, "source_document_id"))
    return {entry: tuple(ids) for entry, ids in grouped.items()}


def _prediction_units_with_packet_document_ids(
    units: Sequence[Mapping[str, Any]],
    *,
    original_to_packet_id: Mapping[str, str],
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for unit in units:
        record = dict(unit)
        citations: list[dict[str, Any]] = []
        for citation in _record_sequence(
            record.get("source_citations"),
            "source_citations",
        ):
            citation_record = dict(citation)
            document_id = _required_str(citation_record, "document_id")
            citation_record["document_id"] = original_to_packet_id.get(
                document_id,
                document_id,
            )
            citations.append(citation_record)
        record["source_citations"] = citations
        normalized.append(record)
    return normalized


def _packet_document_id(candidate_id: str, source_document_id: str) -> str:
    return "-".join(
        (
            safe_path_component(candidate_id, field_name="candidate_id"),
            safe_path_component(source_document_id, field_name="source_document_id"),
        )
    )


def _manifest_path(path: Path, *, source_root: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(source_root).as_posix()
    except ValueError:
        return str(resolved)


def _entry_url(selection: Mapping[str, Any], entry_number: int | None) -> str | None:
    source_url = _optional_str(selection, "source_url")
    if source_url is None or entry_number is None:
        return source_url
    return f"{source_url.rstrip('/')}#entry-{entry_number}"


def _entry_number(entry: CourtListenerWebDocketEntry) -> int | None:
    if entry.entry_number is None:
        return None
    digits = ""
    for character in entry.entry_number.strip():
        if not character.isdigit():
            break
        digits += character
    return int(digits) if digits else None


def _record_hash(record: Mapping[str, Any]) -> str:
    return sha256_text(json.dumps(record, sort_keys=True, separators=(",", ":")))


def _format_datetime(timestamp: datetime) -> str:
    return timestamp.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _record_sequence(value: object, field_name: str) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise PacketInputPlanningError(f"{field_name} must be a list")
    records: list[Mapping[str, Any]] = []
    for item in cast(Sequence[object], value):
        if not isinstance(item, Mapping):
            raise PacketInputPlanningError(f"{field_name} must contain objects")
        records.append(cast(Mapping[str, Any], item))
    return tuple(records)


def _required_str(record: Mapping[str, Any], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PacketInputPlanningError(f"{key} is required")
    return value


def _optional_str(record: Mapping[str, Any], key: str) -> str | None:
    value = record.get(key)
    return value if isinstance(value, str) and value.strip() else None


def _required_bool(record: Mapping[str, Any], key: str) -> bool:
    value = record.get(key)
    if not isinstance(value, bool):
        raise PacketInputPlanningError(f"{key} must be a boolean")
    return value


def _optional_int(record: Mapping[str, Any], key: str) -> int | None:
    value = record.get(key)
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _optional_date(record: Mapping[str, Any], key: str) -> date | None:
    value = _optional_str(record, key)
    if value is None:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _required_int_tuple(
    record: Mapping[str, Any],
    key: str,
) -> tuple[int, ...]:
    value = record.get(key)
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise PacketInputPlanningError(f"{key} must be a non-empty list of integers")
    numbers: list[int] = []
    for item in cast(Sequence[object], value):
        if isinstance(item, int) and not isinstance(item, bool):
            numbers.append(item)
        elif isinstance(item, str) and item.strip().isdigit():
            numbers.append(int(item.strip()))
        else:
            raise PacketInputPlanningError(
                f"{key} must contain only positive integer entry numbers"
            )
    if not numbers:
        raise PacketInputPlanningError(f"{key} must not be empty")
    return tuple(numbers)


def _int_tuple(value: object) -> tuple[int, ...]:
    if not isinstance(value, Sequence) or isinstance(value, str):
        return ()
    numbers: list[int] = []
    for item in cast(Sequence[object], value):
        if isinstance(item, int):
            numbers.append(item)
        elif isinstance(item, str) and item.strip().isdigit():
            numbers.append(int(item.strip()))
    return tuple(numbers)


def _str_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, str):
        return ()
    return tuple(
        item for item in cast(Sequence[object], value) if isinstance(item, str)
    )
