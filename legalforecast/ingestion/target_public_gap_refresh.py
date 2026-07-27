"""Exact-target public-gap refresh composed from existing acquisition stages."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import secrets
import stat
import urllib.error
from collections import defaultdict
from collections.abc import Callable, Generator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from typing import Any, Protocol, cast

from legalforecast.ingestion.budgeted_docket_acquisition import (
    BudgetedDocketAcquisitionResult,
    acquire_ranked_dockets,
    render_complete_docket_html,
)
from legalforecast.ingestion.budgeted_firecrawl import (
    BudgetedFirecrawlRunResult,
    BudgetedFirecrawlScheduler,
    FirecrawlTargetSpec,
)
from legalforecast.ingestion.courtlistener_case_dev_bridge import (
    CourtListenerCaseDevBridgeError,
    bridge_free_download_requests_from_selection,
)
from legalforecast.ingestion.cycle_acquisition_store import CycleAcquisitionStore
from legalforecast.ingestion.disclosure_review_bundle import read_unique_regular_file
from legalforecast.ingestion.firecrawl_docket_pagination import (
    CourtListenerDocketBundle,
    CourtListenerDocketPaginationError,
    canonical_courtlistener_docket_page_url,
)
from legalforecast.ingestion.firecrawl_source import FirecrawlCourtListenerHTMLSource
from legalforecast.ingestion.free_document_downloader import (
    FreeDocumentDownloadError,
    FreeDocumentDownloadRecord,
    FreeDocumentDownloadRequest,
    FreeDocumentSource,
    download_free_docket_documents,
)
from legalforecast.ingestion.provenance_clearance import canonical_json_bytes
from legalforecast.ingestion.public_packet_planner import (
    PublicPacketCandidatePlan,
    PublicPacketDocumentPlan,
    plan_public_packet_downloads,
)
from legalforecast.ingestion.recap_api_discovery import public_recap_download_url
from legalforecast.path_safety import safe_path_component

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_TARGET_PUBLIC_GAP_DATA_OUTPUTS = frozenset(
    {
        "target-public-gap-outcomes.jsonl",
        "target-public-gap-discovered-transitions.jsonl",
        "free-document-requests.jsonl",
        "free-document-downloads.jsonl",
    }
)
_TARGET_PUBLIC_GAP_SUMMARY = "target-public-gap-execution-summary.json"
_TARGET_PUBLIC_GAP_RUN_CARD = "run-cards/execute-target-public-gaps.json"
_TARGET_PUBLIC_GAP_LOG = "logs/execute-target-public-gaps.jsonl"
_TARGET_PUBLIC_GAP_COMMITTED_OUTPUTS = frozenset(
    {*_TARGET_PUBLIC_GAP_DATA_OUTPUTS, _TARGET_PUBLIC_GAP_SUMMARY}
)
_TARGET_PUBLIC_GAP_ALL_OUTPUTS = frozenset(
    {
        *_TARGET_PUBLIC_GAP_COMMITTED_OUTPUTS,
        _TARGET_PUBLIC_GAP_RUN_CARD,
        _TARGET_PUBLIC_GAP_LOG,
    }
)
_TARGET_PUBLIC_GAP_RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "stage",
        "status",
        "plan_path",
        "plan_sha256",
        "execution_identity",
        "fresh_credit_cap",
        "input_paths",
        "source_artifact_commitments",
        "output_paths",
        "output_commitments",
        "terminal_commitments",
        "provider_activity_requested",
        "purchased_document_count",
        "purchased_activity_requested",
        "purchased_activity_executed",
        "pacer_authorized",
        "recap_fetch_authorized",
        "document_purchase_authorized",
        "model_calls_authorized",
        "evaluation_authorized",
        "freeze_or_dispatch_authorized",
    }
)
_TARGET_PUBLIC_GAP_SUMMARY_FIELDS = frozenset(
    {
        "schema_version",
        "plan_sha256",
        "terminal_commitments",
        "output_commitments",
        "provider_activity_requested",
        "firecrawl_metered_activity_requested",
        "public_download_activity_requested",
        "purchased_document_count",
        "purchased_activity_requested",
        "purchased_activity_executed",
        "terminal_reconciliation",
        "pacer_authorized",
        "recap_fetch_authorized",
        "document_purchase_authorized",
        "model_calls_authorized",
        "evaluation_authorized",
        "freeze_or_dispatch_authorized",
    }
)
_TARGET_PUBLIC_GAP_TERMINAL_FIELDS = frozenset(
    {
        "schema_version",
        "plan_sha256",
        "target_cohort_root",
        "target_run_card_sha256",
        "target_projection_file_sha256",
        "target_projection_sha256",
        "target_selection_file_sha256",
        "target_free_manifest_file_sha256",
        "selected_candidate_ids_sha256",
        "selected_document_keys_sha256",
        "required_gap_document_ids_sha256",
        "required_gap_document_count",
        "gap_manifest_sha256",
        "docket_manifest_sha256",
        "discovered_transition_manifest_sha256",
        "terminal_outcome_manifest_sha256",
        "newly_free_manifest_sha256",
        "transition_count",
        "exclusion_count",
        "newly_free_document_count",
        "purchased_document_count",
        "purchased_activity_requested",
        "purchased_activity_executed",
        "terminal_reconciliation",
    }
)
_TERMINAL_REMOTE_CONTENT_FAILURE_PREFIXES = (
    "free public document was empty:",
    "free public PDF is missing PDF magic:",
    "free public document URL returned HTML instead of a document:",
    "free public document response did not look like a PDF ",
    "free public document exceeds byte ceiling (",
    "free public document returned invalid Content-Length:",
)


class TargetPublicGapRefreshError(ValueError):
    """Raised when exact target lineage or public recovery cannot be proven."""


class TargetPublicGapScheduler(Protocol):
    """Structural surface provided by the durable budgeted scheduler."""

    def run(
        self,
        targets: Sequence[FirecrawlTargetSpec],
    ) -> BudgetedFirecrawlRunResult: ...


@dataclass(frozen=True, slots=True)
class TargetPublicGapExecutionIdentity:
    """One authorized durable scheduler and output lineage."""

    output_root: Path
    cycle_store_path: Path
    raw_html_root: Path
    document_output_root: Path
    batch_id: str
    run_id: str
    firecrawl_mode: str
    document_mode: str
    firecrawl_proxy: str
    force_browser: bool
    max_attempts_per_page: int
    provider_breaker_threshold: int

    def to_record(self) -> Mapping[str, object]:
        return {
            "output_root": str(self.output_root.resolve()),
            "cycle_store_path": str(self.cycle_store_path.resolve()),
            "raw_html_root": str(self.raw_html_root.resolve()),
            "document_output_root": str(self.document_output_root.resolve()),
            "batch_id": self.batch_id,
            "run_id": self.run_id,
            "firecrawl_mode": self.firecrawl_mode,
            "document_mode": self.document_mode,
            "firecrawl_proxy": self.firecrawl_proxy,
            "force_browser": self.force_browser,
            "max_attempts_per_page": self.max_attempts_per_page,
            "provider_breaker_threshold": self.provider_breaker_threshold,
        }


@dataclass(frozen=True, slots=True)
class TargetPublicGapPlan:
    """Provider-free projection of one authenticated target's missing documents."""

    target_cohort_root: Path
    target_run_card_sha256: str
    target_projection_file_sha256: str
    target_projection_sha256: str
    target_selection_file_sha256: str
    target_free_manifest_file_sha256: str
    selected_candidate_ids_sha256: str
    selected_document_keys_sha256: str
    required_gap_document_ids: tuple[str, ...]
    required_gap_document_ids_sha256: str
    target_cycle_hash: str
    source_artifact_commitments: Mapping[str, str]
    execution_identity: TargetPublicGapExecutionIdentity
    selections: tuple[Mapping[str, Any], ...]
    gaps: tuple[Mapping[str, Any], ...]
    ranked_records: tuple[Mapping[str, Any], ...]
    required_entry_numbers_by_docket: Mapping[str, frozenset[int]]
    selected_document_count: int
    existing_download_count: int
    fresh_credit_cap: int
    workers: int
    max_pages_per_docket: int
    gap_manifest_sha256: str
    docket_manifest_sha256: str
    provider_activity_requested: bool = False

    def to_record(self) -> Mapping[str, object]:
        """Return the deterministic provider-free execution plan."""

        return {
            "schema_version": "legalforecast.target_public_gap_plan.v1",
            "target_cohort_root": str(self.target_cohort_root),
            "target_run_card_sha256": self.target_run_card_sha256,
            "target_projection_file_sha256": self.target_projection_file_sha256,
            "target_projection_sha256": self.target_projection_sha256,
            "target_selection_file_sha256": self.target_selection_file_sha256,
            "target_free_manifest_file_sha256": (self.target_free_manifest_file_sha256),
            "selected_candidate_ids_sha256": self.selected_candidate_ids_sha256,
            "selected_document_keys_sha256": self.selected_document_keys_sha256,
            "required_gap_document_ids": list(self.required_gap_document_ids),
            "required_gap_document_ids_sha256": (self.required_gap_document_ids_sha256),
            "target_cycle_hash": self.target_cycle_hash,
            "source_artifact_commitments": dict(
                sorted(self.source_artifact_commitments.items())
            ),
            "execution_identity": dict(self.execution_identity.to_record()),
            "gaps": [dict(record) for record in self.gaps],
            "dockets": [
                {
                    "courtlistener_docket_id": docket_id,
                    "required_entry_numbers": sorted(required),
                }
                for docket_id, required in sorted(
                    self.required_entry_numbers_by_docket.items()
                )
            ],
            "selected_document_count": self.selected_document_count,
            "existing_download_count": self.existing_download_count,
            "fresh_credit_cap": self.fresh_credit_cap,
            "workers": self.workers,
            "max_pages_per_docket": self.max_pages_per_docket,
            "gap_manifest_sha256": self.gap_manifest_sha256,
            "docket_manifest_sha256": self.docket_manifest_sha256,
            "provider_activity_requested": self.provider_activity_requested,
            "pacer_authorized": False,
            "recap_fetch_authorized": False,
            "document_purchase_authorized": False,
            "model_calls_authorized": False,
            "evaluation_authorized": False,
            "freeze_or_dispatch_authorized": False,
        }


@dataclass(frozen=True, slots=True)
class TargetPublicGapRefreshResult:
    """Public transition candidates plus document-gap failures."""

    transitions: tuple[Mapping[str, Any], ...]
    gap_failures: tuple[Mapping[str, Any], ...]
    download_requests: tuple[FreeDocumentDownloadRequest, ...]
    acquisition: BudgetedDocketAcquisitionResult
    planner_summary: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class TargetPublicGapExecutionResult:
    """Refresh evidence plus canonical PDF-validated free downloads."""

    refresh: TargetPublicGapRefreshResult
    downloads: tuple[FreeDocumentDownloadRecord, ...]
    outcomes: tuple[Mapping[str, Any], ...]
    terminal_commitments: Mapping[str, object]


@dataclass(slots=True)
class TargetPublicGapExecutionBinding:
    """Pinned writable directories retained through terminal publication."""

    plan_identity: TargetPublicGapExecutionIdentity
    runtime_identity: TargetPublicGapExecutionIdentity
    raw_pages_root: Path
    _directories: tuple[tuple[Path, int, str], ...]

    def require_current(self, plan: TargetPublicGapPlan | None = None) -> None:
        """Fail when any caller-visible path no longer names its pinned inode."""

        if plan is not None and plan.execution_identity != self.plan_identity:
            raise TargetPublicGapRefreshError(
                "execution binding belongs to a different public-gap plan"
            )
        for path, descriptor, label in self._directories:
            _require_named_directory_binding(path, descriptor, label=label)

    def _directory_fd(self, label: str) -> int:
        for _, descriptor, candidate_label in self._directories:
            if candidate_label == label:
                return descriptor
        raise TargetPublicGapRefreshError(
            f"execution binding is missing its {label} directory"
        )


@dataclass(slots=True)
class _TargetDocumentDirectoryBinding:
    directories_by_request: Mapping[str, Path]
    directory_fds_by_request: Mapping[str, int]
    _directories: tuple[tuple[Path, int, str], ...]

    def require_current(self) -> None:
        for path, descriptor, label in self._directories:
            _require_named_directory_binding(path, descriptor, label=label)


@contextmanager
def bind_target_public_gap_execution(
    plan: TargetPublicGapPlan,
) -> Generator[TargetPublicGapExecutionBinding]:
    """Create and pin every writable directory before provider construction."""

    identity = plan.execution_identity
    specifications = (
        ("output parent", identity.output_root.parent),
        ("cycle store parent", identity.cycle_store_path.parent),
        ("raw HTML root", identity.raw_html_root),
        ("raw HTML pages", identity.raw_html_root / "pages"),
        ("document output root", identity.document_output_root),
    )
    opened: list[tuple[Path, int, str]] = []
    try:
        for label, path in specifications:
            descriptor = _open_or_create_directory_no_follow(path, label=label)
            opened.append((Path(os.path.abspath(path)), descriptor, label))
        by_label = {label: descriptor for _, descriptor, label in opened}
        runtime_identity = replace(
            identity,
            output_root=(
                _descriptor_path(by_label["output parent"]) / identity.output_root.name
            ),
            cycle_store_path=(
                _descriptor_path(by_label["cycle store parent"])
                / identity.cycle_store_path.name
            ),
            raw_html_root=_descriptor_path(by_label["raw HTML root"]),
            document_output_root=_descriptor_path(by_label["document output root"]),
        )
        binding = TargetPublicGapExecutionBinding(
            plan_identity=identity,
            runtime_identity=runtime_identity,
            raw_pages_root=_descriptor_path(by_label["raw HTML pages"]),
            _directories=tuple(opened),
        )
        binding.require_current(plan)
        yield binding
    finally:
        for _, descriptor, _ in reversed(opened):
            os.close(descriptor)


@contextmanager
def _bind_target_document_directories(
    execution_binding: TargetPublicGapExecutionBinding,
    requests: Sequence[FreeDocumentDownloadRequest],
) -> Generator[_TargetDocumentDirectoryBinding]:
    """Pin every request's candidate/provider directory before source creation."""

    root_fd = execution_binding._directory_fd(  # pyright: ignore[reportPrivateUsage]
        "document output root"
    )
    original_root = execution_binding.plan_identity.document_output_root
    opened: list[tuple[Path, int, str]] = []
    candidate_fds: dict[str, int] = {}
    provider_fds: dict[tuple[str, str], int] = {}
    request_directories: dict[str, Path] = {}
    try:
        for request in requests:
            candidate = safe_path_component(
                request.candidate_id,
                field_name="candidate_id",
            )
            provider = safe_path_component(
                request.source_provider,
                field_name="source_provider",
            )
            candidate_fd = candidate_fds.get(candidate)
            if candidate_fd is None:
                candidate_fd = _open_or_create_child_directory(
                    root_fd,
                    candidate,
                    label=f"document candidate directory {candidate}",
                )
                candidate_fds[candidate] = candidate_fd
                opened.append(
                    (
                        original_root / candidate,
                        candidate_fd,
                        f"document candidate directory {candidate}",
                    )
                )
            provider_key = (candidate, provider)
            provider_fd = provider_fds.get(provider_key)
            if provider_fd is None:
                provider_fd = _open_or_create_child_directory(
                    candidate_fd,
                    provider,
                    label=(f"document provider directory {candidate}/{provider}"),
                )
                provider_fds[provider_key] = provider_fd
                opened.append(
                    (
                        original_root / candidate / provider,
                        provider_fd,
                        f"document provider directory {candidate}/{provider}",
                    )
                )
            request_directories[_download_request_key(request)] = _descriptor_path(
                provider_fd
            )
        binding = _TargetDocumentDirectoryBinding(
            directories_by_request=request_directories,
            directory_fds_by_request={
                request_key: provider_fds[
                    (
                        safe_path_component(
                            request.candidate_id,
                            field_name="candidate_id",
                        ),
                        safe_path_component(
                            request.source_provider,
                            field_name="source_provider",
                        ),
                    )
                ]
                for request in requests
                for request_key in (_download_request_key(request),)
            },
            _directories=tuple(opened),
        )
        binding.require_current()
        yield binding
    finally:
        for _, descriptor, _ in reversed(opened):
            os.close(descriptor)


@contextmanager
def bind_verified_target_public_gap_downloads(
    *,
    execution_binding: TargetPublicGapExecutionBinding,
    requests: Sequence[FreeDocumentDownloadRequest],
    downloads: Sequence[FreeDocumentDownloadRecord],
) -> Generator[None]:
    """Reauthenticate and pin downloaded PDFs through terminal publication."""

    execution_binding.require_current()
    with _bind_target_document_directories(execution_binding, requests) as binding:
        _verify_bound_target_public_gap_downloads(
            binding=binding,
            requests=requests,
            downloads=downloads,
        )
        yield
        binding.require_current()
        _verify_bound_target_public_gap_downloads(
            binding=binding,
            requests=requests,
            downloads=downloads,
        )
        execution_binding.require_current()


def _verify_bound_target_public_gap_downloads(
    *,
    binding: _TargetDocumentDirectoryBinding,
    requests: Sequence[FreeDocumentDownloadRequest],
    downloads: Sequence[FreeDocumentDownloadRecord],
) -> None:
    requests_by_key: dict[str, FreeDocumentDownloadRequest] = {}
    for request in requests:
        key = _download_request_key(request)
        if key in requests_by_key:
            raise TargetPublicGapRefreshError(
                "target public-gap download request identity is duplicated"
            )
        requests_by_key[key] = request
    seen: set[str] = set()
    for record in downloads:
        key = "\0".join(
            (
                record.candidate_id,
                record.source_provider,
                record.source_document_id,
            )
        )
        request = requests_by_key.get(key)
        if request is None or key in seen:
            raise TargetPublicGapRefreshError(
                "target public-gap download manifest identity differs"
            )
        seen.add(key)
        local_path = PurePosixPath(record.local_path)
        candidate = safe_path_component(
            request.candidate_id,
            field_name="candidate_id",
        )
        provider = safe_path_component(
            request.source_provider,
            field_name="source_provider",
        )
        if (
            local_path.is_absolute()
            or len(local_path.parts) != 3
            or local_path.parts[:2] != (candidate, provider)
            or any(part in {"", ".", ".."} for part in local_path.parts)
            or record.docket_entry_number != request.docket_entry_number
            or record.document_role is not request.document_role
            or record.source_url != request.source_url
            or record.free_or_purchased != "free"
        ):
            raise TargetPublicGapRefreshError(
                "target public-gap download manifest differs from its request"
            )
        descriptor = binding.directory_fds_by_request.get(key)
        if descriptor is None:
            raise TargetPublicGapRefreshError(
                "target public-gap download directory binding is missing"
            )
        payload = _read_unique_regular_file_at_named(
            descriptor,
            local_path.parts[2],
            label=f"target public-gap document {record.local_path}",
        )
        if (
            len(payload) != record.byte_count
            or hashlib.sha256(payload).hexdigest() != record.sha256
        ):
            raise TargetPublicGapRefreshError(
                "target public-gap download bytes differ from their manifest"
            )


def target_public_gap_plan_bytes(plan: TargetPublicGapPlan) -> bytes:
    """Serialize one immutable plan in its closed canonical representation."""

    return (
        json.dumps(
            plan.to_record(),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode()


def publish_target_public_gap_plan(
    path: Path,
    plan: TargetPublicGapPlan,
) -> str:
    """Atomically publish or exact-byte resume one provider-free plan."""

    payload = target_public_gap_plan_bytes(plan)
    digest = hashlib.sha256(payload).hexdigest()
    destination = Path(os.path.abspath(path))
    parent_fd = _open_existing_directory_no_follow(
        destination.parent,
        label="target public-gap plan parent",
    )
    temporary_name = f".{destination.name}.{secrets.token_hex(16)}.partial"
    temporary_created = False
    try:
        _require_named_directory_binding(
            destination.parent,
            parent_fd,
            label="target public-gap plan parent",
        )
        resolved_parent = Path(os.readlink(f"/proc/self/fd/{parent_fd}"))
        resolved_destination = resolved_parent / destination.name
        _reject_plan_destination_overlap(resolved_destination, plan=plan)
        try:
            existing = _read_unique_regular_file_at(parent_fd, destination.name)
        except FileNotFoundError:
            existing = None
        if existing is not None:
            if existing != payload:
                raise TargetPublicGapRefreshError(
                    "target public-gap plan already exists with different bytes"
                )
            _require_named_directory_binding(
                destination.parent,
                parent_fd,
                label="target public-gap plan parent",
            )
            return digest
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
        descriptor = os.open(
            temporary_name,
            flags,
            0o600,
            dir_fd=parent_fd,
        )
        temporary_created = True
        try:
            view = memoryview(payload)
            while view:
                written = os.write(descriptor, view)
                view = view[written:]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        try:
            _require_named_directory_binding(
                destination.parent,
                parent_fd,
                label="target public-gap plan parent",
            )
            os.link(
                temporary_name,
                destination.name,
                src_dir_fd=parent_fd,
                dst_dir_fd=parent_fd,
                follow_symlinks=False,
            )
        except FileExistsError as exc:
            if _read_unique_regular_file_at(parent_fd, destination.name) != payload:
                raise TargetPublicGapRefreshError(
                    "target public-gap plan publication raced with different bytes"
                ) from exc
        os.unlink(temporary_name, dir_fd=parent_fd)
        temporary_created = False
        os.fsync(parent_fd)
        _require_named_directory_binding(
            destination.parent,
            parent_fd,
            label="target public-gap plan parent",
        )
        if _read_unique_regular_file_at(parent_fd, destination.name) != payload:
            raise TargetPublicGapRefreshError(
                "published target public-gap plan changed"
            )
        _require_named_directory_binding(
            destination.parent,
            parent_fd,
            label="target public-gap plan parent",
        )
        return digest
    except TargetPublicGapRefreshError:
        raise
    except OSError as exc:
        raise TargetPublicGapRefreshError(
            f"target public-gap plan cannot be safely published: {destination}"
        ) from exc
    finally:
        if temporary_created:
            try:
                os.unlink(temporary_name, dir_fd=parent_fd)
            except FileNotFoundError:
                pass
        os.close(parent_fd)


def verify_target_public_gap_plan(
    path: Path,
    *,
    expected_sha256: str,
    reconstructed: TargetPublicGapPlan,
) -> TargetPublicGapPlan:
    """Authenticate exact plan bytes and replay them from current sources."""

    if _SHA256.fullmatch(expected_sha256) is None:
        raise TargetPublicGapRefreshError("plan SHA-256 is invalid")
    payload = read_unique_regular_file(path)
    if hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise TargetPublicGapRefreshError("plan SHA-256 mismatch")
    if payload != target_public_gap_plan_bytes(reconstructed):
        raise TargetPublicGapRefreshError(
            "plan does not reproduce from authenticated target sources"
        )
    return reconstructed


def require_target_public_gap_sources_unchanged(
    plan: TargetPublicGapPlan,
) -> None:
    """Reread the complete canonical-verifier closure fail closed."""

    for raw_path, expected_sha256 in plan.source_artifact_commitments.items():
        try:
            payload = read_unique_regular_file(Path(raw_path))
        except (OSError, ValueError) as exc:
            raise TargetPublicGapRefreshError(
                f"target source artifact changed: {raw_path}"
            ) from exc
        if hashlib.sha256(payload).hexdigest() != expected_sha256:
            raise TargetPublicGapRefreshError(
                f"target source artifact changed: {raw_path}"
            )


def preflight_target_public_gap_execution(
    plan: TargetPublicGapPlan,
    *,
    expected_plan_sha256: str | None = None,
) -> None:
    """Validate every writable namespace before provider construction."""

    source_paths = tuple(
        Path(path).resolve() for path in plan.source_artifact_commitments
    )
    identity = plan.execution_identity
    writable = (
        ("output root", identity.output_root.absolute(), True),
        ("cycle store", identity.cycle_store_path.absolute(), False),
        ("raw HTML root", identity.raw_html_root.absolute(), True),
        (
            "document output root",
            identity.document_output_root.absolute(),
            True,
        ),
    )
    if identity.output_root.exists() or identity.output_root.is_symlink():
        if expected_plan_sha256 is None:
            raise TargetPublicGapRefreshError(
                "preexisting final output requires its expected plan SHA-256"
            )
        _verify_completed_output_for_plan(
            plan,
            expected_plan_sha256=expected_plan_sha256,
        )
    for label, path, is_tree in writable:
        _reject_symlink_components(path, label=label)
        if path == plan.target_cohort_root or path.is_relative_to(
            plan.target_cohort_root
        ):
            raise TargetPublicGapRefreshError(
                f"{label} overlaps authenticated source target root"
            )
        for source in source_paths:
            if (
                path == source
                or (is_tree and source.is_relative_to(path))
                or path.is_relative_to(source)
            ):
                raise TargetPublicGapRefreshError(
                    f"{label} overlaps authenticated source: {source}"
                )
            if path.exists() and source.exists():
                try:
                    if path.samefile(source):
                        raise TargetPublicGapRefreshError(
                            f"{label} aliases authenticated source by hard-link"
                        )
                except OSError as exc:
                    raise TargetPublicGapRefreshError(
                        f"cannot inspect {label} alias safety"
                    ) from exc
        if path.exists():
            metadata = path.lstat()
            if is_tree:
                if not stat.S_ISDIR(metadata.st_mode):
                    raise TargetPublicGapRefreshError(
                        f"{label} must be a non-symlink directory"
                    )
                if label != "output root":
                    _reject_existing_work_tree(path, label=label)
            elif not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                raise TargetPublicGapRefreshError(
                    f"{label} must be a singly linked regular file"
                )
    for index, (left_label, left, left_tree) in enumerate(writable):
        for right_label, right, right_tree in writable[index + 1 :]:
            if (
                left == right
                or (left_tree and right.is_relative_to(left))
                or (right_tree and left.is_relative_to(right))
            ):
                raise TargetPublicGapRefreshError(
                    f"writable namespaces overlap: {left_label}/{right_label}"
                )
            if left.exists() and right.exists():
                try:
                    if left.samefile(right):
                        raise TargetPublicGapRefreshError(
                            "writable namespaces hard-link or alias: "
                            f"{left_label}/{right_label}"
                        )
                except OSError as exc:
                    raise TargetPublicGapRefreshError(
                        "cannot inspect writable namespace aliases"
                    ) from exc


def publish_target_public_gap_outputs(
    *,
    plan: TargetPublicGapPlan,
    plan_sha256: str,
    payloads: Mapping[str, bytes],
    execution_binding: TargetPublicGapExecutionBinding | None = None,
) -> None:
    """Publish the deterministic terminal tree under one exclusive lock."""

    if _SHA256.fullmatch(plan_sha256) is None:
        raise TargetPublicGapRefreshError("plan SHA-256 is invalid")
    expected = _validated_relative_payloads(payloads)
    if execution_binding is None:
        with bind_target_public_gap_execution(plan) as binding:
            publish_target_public_gap_outputs(
                plan=plan,
                plan_sha256=plan_sha256,
                payloads=expected,
                execution_binding=binding,
            )
        return
    execution_binding.require_current(plan)
    _publish_target_public_gap_outputs_bound(
        plan=plan,
        plan_sha256=plan_sha256,
        expected=expected,
        execution_binding=execution_binding,
    )


def _publish_target_public_gap_outputs_bound(
    *,
    plan: TargetPublicGapPlan,
    plan_sha256: str,
    expected: Mapping[str, bytes],
    execution_binding: TargetPublicGapExecutionBinding,
) -> None:
    """Publish through pinned directory descriptors without pathname traversal."""

    parent_fd = execution_binding._directory_fd(  # pyright: ignore[reportPrivateUsage]
        "output parent"
    )
    output_name = plan.execution_identity.output_root.name
    stage_name = f".{output_name}.{plan_sha256}.partial"
    lock_fd = _acquire_output_lock_at(parent_fd, f".{output_name}.lock")
    stage_fd: int | None = None
    child_bindings: list[tuple[int, str, int, str]] = []
    try:
        output_fd = _open_child_directory_if_present(
            parent_fd,
            output_name,
            label="published output",
        )
        if output_fd is not None:
            try:
                if _read_directory_tree_at(output_fd) != expected:
                    raise TargetPublicGapRefreshError(
                        "published output differs from current exact execution"
                    )
                _require_child_directory_binding(
                    parent_fd,
                    output_name,
                    output_fd,
                    label="published output",
                )
            finally:
                os.close(output_fd)
            execution_binding.require_current(plan)
            return
        stage_fd = _open_or_create_child_directory(
            parent_fd,
            stage_name,
            label="partial output",
        )
        child_bindings.append((parent_fd, stage_name, stage_fd, "partial output"))
        current = _read_directory_tree_at(stage_fd)
        unexpected = set(current) - set(expected)
        if unexpected or any(current[name] != expected[name] for name in current):
            raise TargetPublicGapRefreshError(
                "partial output is incompatible with current exact execution"
            )
        directory_fds: dict[tuple[str, ...], int] = {(): stage_fd}
        for relative, payload in expected.items():
            parts = Path(relative).parts
            parent_parts: tuple[str, ...] = ()
            destination_parent_fd = stage_fd
            for component in parts[:-1]:
                child_parts = (*parent_parts, component)
                child_fd = directory_fds.get(child_parts)
                if child_fd is None:
                    child_fd = _open_or_create_child_directory(
                        destination_parent_fd,
                        component,
                        label=f"partial output directory {'/'.join(child_parts)}",
                    )
                    directory_fds[child_parts] = child_fd
                    child_bindings.append(
                        (
                            destination_parent_fd,
                            component,
                            child_fd,
                            f"partial output directory {'/'.join(child_parts)}",
                        )
                    )
                destination_parent_fd = child_fd
                parent_parts = child_parts
            _write_unique_regular_file_at(
                destination_parent_fd,
                parts[-1],
                payload,
                label=f"partial output artifact {relative}",
            )
        if _read_directory_tree_at(stage_fd) != expected:
            raise TargetPublicGapRefreshError(
                "staged output does not exactly match terminal payloads"
            )
        for parent, name, descriptor, label in child_bindings:
            _require_child_directory_binding(
                parent,
                name,
                descriptor,
                label=label,
            )
        for descriptor in reversed(tuple(directory_fds.values())):
            os.fsync(descriptor)
        execution_binding.require_current(plan)
        os.rename(
            stage_name,
            output_name,
            src_dir_fd=parent_fd,
            dst_dir_fd=parent_fd,
        )
        os.fsync(parent_fd)
        _require_child_directory_binding(
            parent_fd,
            output_name,
            stage_fd,
            label="published output",
        )
        execution_binding.require_current(plan)
    finally:
        closed: set[int] = set()
        for _, _, descriptor, _ in reversed(child_bindings):
            if descriptor not in closed:
                os.close(descriptor)
                closed.add(descriptor)
        _release_output_lock(lock_fd)


def plan_target_public_gaps(
    *,
    verified_projection: Mapping[str, object],
    target_cohort_root: Path,
    expected_target_run_card_sha256: str,
    fresh_credit_cap: int,
    workers: int,
    max_pages_per_docket: int,
    execution_identity: TargetPublicGapExecutionIdentity,
) -> TargetPublicGapPlan:
    """Project gaps only after the canonical target verifier has succeeded."""

    if _SHA256.fullmatch(expected_target_run_card_sha256) is None:
        raise TargetPublicGapRefreshError("target run-card SHA-256 is invalid")
    run_card_bytes = verified_projection.get("run_card_bytes")
    if (
        not isinstance(run_card_bytes, bytes)
        or hashlib.sha256(run_card_bytes).hexdigest() != expected_target_run_card_sha256
    ):
        raise TargetPublicGapRefreshError("target run-card SHA-256 mismatch")
    if not 1 <= fresh_credit_cap <= 500:
        raise TargetPublicGapRefreshError(
            "fresh Firecrawl credit cap must be between 1 and 500"
        )
    if not 1 <= workers <= 10:
        raise TargetPublicGapRefreshError("workers must be between 1 and 10")
    if not 1 <= max_pages_per_docket <= 100:
        raise TargetPublicGapRefreshError(
            "max pages per docket must be between 1 and 100"
        )
    if (
        not execution_identity.batch_id.strip()
        or not execution_identity.run_id.strip()
        or execution_identity.firecrawl_mode not in {"live", "fixture"}
        or execution_identity.document_mode not in {"live", "fixture"}
        or execution_identity.firecrawl_proxy not in {"basic", "auto", "enhanced"}
        or execution_identity.max_attempts_per_page <= 0
        or execution_identity.provider_breaker_threshold <= 0
    ):
        raise TargetPublicGapRefreshError(
            "target public-gap execution identity is invalid"
        )

    summary = _mapping(verified_projection.get("summary"), "target summary")
    selections = _records(
        verified_projection.get("selection_records"),
        "target selections",
    )
    free_manifest = _records(
        verified_projection.get("free_manifest"),
        "target free manifest",
    )
    selected_case_count = _positive_int(
        summary.get("selected_case_count"),
        "selected case count",
    )
    if selected_case_count != len(selections):
        raise TargetPublicGapRefreshError("target selection count differs")
    projection_sha256 = _digest(
        summary.get("projection_sha256"),
        "target projection SHA-256",
    )
    selected_candidate_ids_sha256 = _digest(
        summary.get("selected_candidate_ids_sha256"),
        "selected candidate IDs SHA-256",
    )
    cycle_hash = _digest(
        summary.get("snapshot_cycle_hash"),
        "target cycle hash",
    ).removeprefix("sha256:")

    selection_by_candidate: dict[str, Mapping[str, Any]] = {}
    documents: dict[tuple[str, str], Mapping[str, Any]] = {}
    ordered_document_keys: list[tuple[str, str]] = []
    selected_candidate_ids: list[str] = []
    source_document_ids: set[str] = set()
    for selection in selections:
        candidate_id = _text(selection.get("candidate_id"), "candidate ID")
        if (
            candidate_id in selection_by_candidate
            or selection.get("selected") is not True
        ):
            raise TargetPublicGapRefreshError(
                f"target candidate is duplicate or unselected: {candidate_id}"
            )
        selection_by_candidate[candidate_id] = selection
        selected_candidate_ids.append(candidate_id)
        _canonical_docket_url(selection, candidate_id)
        for document in _records(selection.get("documents"), "target documents"):
            source_document_id = _text(
                document.get("source_document_id"),
                "source document ID",
            )
            key = (
                candidate_id,
                source_document_id,
            )
            if (
                key in documents
                or source_document_id in source_document_ids
                or document.get("candidate_id") != candidate_id
            ):
                raise TargetPublicGapRefreshError(
                    f"target document identity is invalid: {key}"
                )
            documents[key] = document
            ordered_document_keys.append(key)
            source_document_ids.add(source_document_id)
            _positive_int(document.get("docket_entry_number"), "docket entry number")

    downloaded: set[tuple[str, str]] = set()
    for record in free_manifest:
        key = (
            _text(record.get("candidate_id"), "download candidate ID"),
            _text(record.get("source_document_id"), "download source document ID"),
        )
        if key not in documents or key in downloaded:
            raise TargetPublicGapRefreshError(
                f"target free manifest identity is invalid: {key}"
            )
        downloaded.add(key)

    if _semantic_sha256(selected_candidate_ids) != selected_candidate_ids_sha256:
        raise TargetPublicGapRefreshError("selected candidate commitment differs")

    gaps: list[Mapping[str, Any]] = []
    gap_candidates: set[str] = set()
    gap_entries_by_candidate: dict[str, set[int]] = defaultdict(set)
    for key in ordered_document_keys:
        if key in downloaded:
            continue
        candidate_id, source_document_id = key
        document = documents[key]
        if (
            document.get("availability_status") != "unavailable"
            or document.get("requires_paid_recovery") is not True
        ):
            raise TargetPublicGapRefreshError(
                f"undownloaded target document is not a paid gap: {key}"
            )
        gap_candidates.add(candidate_id)
        docket_entry_number = _positive_int(
            document.get("docket_entry_number"),
            "docket entry number",
        )
        gap_entries_by_candidate[candidate_id].add(docket_entry_number)
        gaps.append(
            {
                "candidate_id": candidate_id,
                "courtlistener_docket_id": candidate_id,
                "courtlistener_docket_entry_id": _text(
                    document.get("courtlistener_docket_entry_id"),
                    "CourtListener docket-entry ID",
                ),
                "docket_entry_number": docket_entry_number,
                "source_document_id": source_document_id,
                "document_role": _text(
                    document.get("document_role"),
                    "document role",
                ),
                "description": _text(
                    document.get("description"),
                    "document description",
                ),
                "prior_source_url": _text(
                    document.get("source_url")
                    or document.get("source_url_or_reference"),
                    "prior source URL",
                ),
            }
        )

    ranked_records = tuple(
        {
            "identity": {
                "courtlistener_docket_id": candidate_id,
                "courtlistener_url": _canonical_docket_url(
                    selection_by_candidate[candidate_id],
                    candidate_id,
                ),
            },
            "ranking_key": [rank, candidate_id],
        }
        for rank, candidate_id in enumerate(sorted(gap_candidates))
    )
    required = {
        candidate_id: frozenset(gap_entries_by_candidate[candidate_id])
        for candidate_id in sorted(gap_candidates)
    }
    docket_records = tuple(
        {
            "courtlistener_docket_id": candidate_id,
            "required_entry_numbers": sorted(required[candidate_id]),
        }
        for candidate_id in sorted(required)
    )
    resolved_target_root = target_cohort_root.resolve()
    run_card_path = _path(
        verified_projection.get("run_card_path"),
        "target run-card path",
    )
    summary_path = _path(
        verified_projection.get("summary_path"),
        "target projection path",
    )
    selection_path = _path(
        verified_projection.get("selection_path"),
        "target selection path",
    )
    free_manifest_path = _path(
        verified_projection.get("free_manifest_path"),
        "target free manifest path",
    )
    for label, path in (
        ("target run-card", run_card_path),
        ("target projection", summary_path),
        ("target selection", selection_path),
        ("target free manifest", free_manifest_path),
    ):
        if not path.resolve().is_relative_to(resolved_target_root):
            raise TargetPublicGapRefreshError(f"{label} is outside target root")
    artifact_bytes = _mapping(
        verified_projection.get("verified_artifact_bytes"),
        "verified target artifact bytes",
    )
    gap_document_ids = tuple(cast(str, gap["source_document_id"]) for gap in gaps)
    return TargetPublicGapPlan(
        target_cohort_root=resolved_target_root,
        target_run_card_sha256=expected_target_run_card_sha256,
        target_projection_file_sha256=_file_sha256(
            artifact_bytes,
            summary_path,
            "target projection",
        ),
        target_projection_sha256=projection_sha256,
        target_selection_file_sha256=_file_sha256(
            artifact_bytes,
            selection_path,
            "target selection",
        ),
        target_free_manifest_file_sha256=_file_sha256(
            artifact_bytes,
            free_manifest_path,
            "target free manifest",
        ),
        selected_candidate_ids_sha256=selected_candidate_ids_sha256,
        selected_document_keys_sha256=_semantic_sha256(
            [list(key) for key in ordered_document_keys]
        ),
        required_gap_document_ids=gap_document_ids,
        required_gap_document_ids_sha256=_semantic_sha256(list(gap_document_ids)),
        target_cycle_hash=cycle_hash,
        source_artifact_commitments=_source_artifact_commitments(artifact_bytes),
        execution_identity=execution_identity,
        selections=tuple(selections),
        gaps=tuple(gaps),
        ranked_records=ranked_records,
        required_entry_numbers_by_docket=required,
        selected_document_count=len(documents),
        existing_download_count=len(downloaded),
        fresh_credit_cap=fresh_credit_cap,
        workers=workers,
        max_pages_per_docket=max_pages_per_docket,
        gap_manifest_sha256=_records_sha256(gaps),
        docket_manifest_sha256=_records_sha256(docket_records),
    )


def refresh_target_public_gaps(
    *,
    plan: TargetPublicGapPlan,
    scheduler: TargetPublicGapScheduler,
) -> TargetPublicGapRefreshResult:
    """Acquire exact rows, reuse public planning, and reconcile old/new identity."""

    acquisition = acquire_ranked_dockets(
        records=plan.ranked_records,
        scheduler=cast(BudgetedFirecrawlScheduler, scheduler),
        limit=len(plan.ranked_records),
        max_pages_per_docket=plan.max_pages_per_docket,
        decision_anchor=None,
        required_entry_numbers_by_docket=plan.required_entry_numbers_by_docket,
    )
    bundle_by_candidate = {bundle.docket_id: bundle for bundle in acquisition.bundles}
    selection_by_candidate = {
        _text(selection.get("candidate_id"), "candidate ID"): selection
        for selection in plan.selections
    }
    successful_ids = set(bundle_by_candidate)
    screened_records = tuple(
        _screened_record(selection_by_candidate[candidate_id])
        for candidate_id in sorted(successful_ids)
    )
    if screened_records:
        planner = plan_public_packet_downloads(
            screened_records,
            raw_html_bytes_by_candidate={
                candidate_id: render_complete_docket_html(bundle).encode()
                for candidate_id, bundle in bundle_by_candidate.items()
            },
            target_clean_cases=len(screened_records),
        )
        planned_by_candidate = {
            candidate.candidate_id: candidate for candidate in planner.candidate_plans
        }
        planner_summary = planner.summary_record()
    else:
        planned_by_candidate = {}
        planner_summary = {
            "schema_version": "legalforecast.public_packet_download_plan.v1",
            "candidate_count": 0,
            "target_clean_cases": 0,
        }
    failure_by_candidate = {
        failure.docket_id: failure for failure in acquisition.failures
    }

    transitions: list[Mapping[str, Any]] = []
    gap_failures: list[Mapping[str, Any]] = []
    recovered_by_candidate: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for gap in plan.gaps:
        candidate_id = cast(str, gap["candidate_id"])
        if candidate_id in failure_by_candidate:
            gap_failures.append(
                _gap_failure(
                    gap,
                    failure_by_candidate[candidate_id].failure_reason,
                )
            )
            continue
        planned = planned_by_candidate.get(candidate_id)
        bundle = bundle_by_candidate.get(candidate_id)
        if planned is None or bundle is None:
            gap_failures.append(_gap_failure(gap, "public_planner_candidate_missing"))
            continue
        match = _unique_planned_document(gap, planned=planned, bundle=bundle)
        if match is None:
            reason = (
                ";".join(planned.paid_gap_reasons)
                or ";".join(planned.exclusion_reasons)
                or "public_document_identity_unproven"
            )
            gap_failures.append(_gap_failure(gap, reason))
            continue
        page = _source_page(gap, bundle)
        document = {
            **match.to_record(),
            "source_document_id": gap["source_document_id"],
            "source_provider": "courtlistener",
            "source_url_or_reference": match.source_url,
            "file_extension": "pdf",
            "availability_status": "available",
            "requires_paid_recovery": False,
            "resolved_from_paid_gap": True,
        }
        recovered_by_candidate[candidate_id].append(document)
        core = {
            **dict(gap),
            "new_source_url": match.source_url,
            "new_availability_status": "available",
            "new_requires_paid_recovery": False,
            "source_page_sha256": "sha256:" + page.sha256,
            "source_page_completeness": (
                "required_entries_only"
                if bundle.stopped_at_required_entries
                else "exhaustive_docket"
            ),
        }
        transitions.append(
            {
                "schema_version": (
                    "legalforecast.target_public_gap_identity_transition.v1"
                ),
                "transition_id": _value_sha256(core),
                **core,
            }
        )

    requests: list[FreeDocumentDownloadRequest] = []
    for candidate_id, recovered in sorted(recovered_by_candidate.items()):
        try:
            requests.extend(
                bridge_free_download_requests_from_selection(
                    {
                        "candidate_id": candidate_id,
                        "documents": recovered,
                    }
                )
            )
        except CourtListenerCaseDevBridgeError as exc:
            raise TargetPublicGapRefreshError(str(exc)) from exc
    if len(transitions) + len(gap_failures) != len(plan.gaps):
        raise TargetPublicGapRefreshError(
            "public-gap terminal outputs do not reconcile"
        )
    return TargetPublicGapRefreshResult(
        transitions=tuple(transitions),
        gap_failures=tuple(gap_failures),
        download_requests=tuple(requests),
        acquisition=acquisition,
        planner_summary=planner_summary,
    )


def execute_target_public_gap_refresh(
    *,
    plan: TargetPublicGapPlan,
    expected_plan_sha256: str,
    firecrawl_source_factory: Callable[[], FirecrawlCourtListenerHTMLSource],
    document_source_factory: Callable[[], FreeDocumentSource],
    allow_existing_downloads: bool,
    execution_binding: TargetPublicGapExecutionBinding | None = None,
) -> TargetPublicGapExecutionResult:
    """Execute after exact authority through the canonical acquisition stages."""

    if _SHA256.fullmatch(expected_plan_sha256) is None:
        raise TargetPublicGapRefreshError("plan SHA-256 is invalid")
    if (
        hashlib.sha256(target_public_gap_plan_bytes(plan)).hexdigest()
        != expected_plan_sha256
    ):
        raise TargetPublicGapRefreshError("plan SHA-256 mismatch")
    preflight_target_public_gap_execution(
        plan,
        expected_plan_sha256=expected_plan_sha256,
    )
    require_target_public_gap_sources_unchanged(plan)
    if execution_binding is None:
        with bind_target_public_gap_execution(plan) as binding:
            return execute_target_public_gap_refresh(
                plan=plan,
                expected_plan_sha256=expected_plan_sha256,
                firecrawl_source_factory=firecrawl_source_factory,
                document_source_factory=document_source_factory,
                allow_existing_downloads=allow_existing_downloads,
                execution_binding=binding,
            )
    execution_binding.require_current(plan)
    preflight_target_public_gap_execution(
        plan,
        expected_plan_sha256=expected_plan_sha256,
    )
    require_target_public_gap_sources_unchanged(plan)
    if plan.execution_identity.output_root.exists():
        raise TargetPublicGapRefreshError(
            "target public-gap execution is already completed; refusing "
            "provider re-execution"
        )
    identity = execution_binding.runtime_identity
    firecrawl_source = firecrawl_source_factory()
    execution_binding.require_current(plan)
    require_target_public_gap_sources_unchanged(plan)
    if (
        firecrawl_source.config.proxy != identity.firecrawl_proxy
        or firecrawl_source.config.force_browser != identity.force_browser
    ):
        raise TargetPublicGapRefreshError(
            "Firecrawl source configuration differs from the plan-bound "
            "execution identity"
        )
    batch_config = {
        "schema_version": "legalforecast.target_public_gap_refresh_batch.v1",
        "purpose": "exact-target-public-gap-refresh",
        "plan_sha256": expected_plan_sha256,
        "target_run_card_sha256": plan.target_run_card_sha256,
        "target_projection_file_sha256": plan.target_projection_file_sha256,
        "target_projection_sha256": plan.target_projection_sha256,
        "target_selection_file_sha256": plan.target_selection_file_sha256,
        "target_free_manifest_file_sha256": (plan.target_free_manifest_file_sha256),
        "selected_candidate_ids_sha256": plan.selected_candidate_ids_sha256,
        "selected_document_keys_sha256": plan.selected_document_keys_sha256,
        "required_gap_document_ids_sha256": (plan.required_gap_document_ids_sha256),
        "gap_manifest_sha256": plan.gap_manifest_sha256,
        "docket_manifest_sha256": plan.docket_manifest_sha256,
        "public_recovery_only": True,
        "pacer_authorized": False,
        "recap_fetch_authorized": False,
        "document_purchase_authorized": False,
        "model_calls_authorized": False,
        "evaluation_authorized": False,
        "freeze_or_dispatch_authorized": False,
    }
    run_config = {
        **batch_config,
        "workers": plan.workers,
        "max_pages_per_docket": plan.max_pages_per_docket,
        "max_attempts_per_page": identity.max_attempts_per_page,
        "provider_breaker_threshold": identity.provider_breaker_threshold,
        "raw_artifact_root": str(identity.raw_html_root.resolve()),
        "firecrawl_proxy": identity.firecrawl_proxy,
        "firecrawl_force_browser": identity.force_browser,
    }
    with CycleAcquisitionStore(identity.cycle_store_path) as store:
        execution_binding.require_current(plan)
        if store.cycle_hash != plan.target_cycle_hash:
            raise TargetPublicGapRefreshError(
                "cycle store differs from authenticated target projection"
            )
        store.ensure_batch(identity.batch_id, batch_config)
        store.ensure_firecrawl_run(
            identity.run_id,
            batch_id=identity.batch_id,
            config=run_config,
            credit_cap=plan.fresh_credit_cap,
            reserved_credits_per_attempt=(
                firecrawl_source.config.max_credits_per_scrape
            ),
        )
        preflight_target_public_gap_execution(
            plan,
            expected_plan_sha256=expected_plan_sha256,
        )
        execution_binding.require_current(plan)
        require_target_public_gap_sources_unchanged(plan)
        refresh = refresh_target_public_gaps(
            plan=plan,
            scheduler=BudgetedFirecrawlScheduler(
                store=store,
                source=firecrawl_source,
                run_id=identity.run_id,
                artifact_dir=execution_binding.raw_pages_root,
                max_attempts=identity.max_attempts_per_page,
                provider_5xx_circuit_threshold=identity.provider_breaker_threshold,
                max_workers=plan.workers,
            ),
        )
    execution_binding.require_current(plan)
    with _bind_target_document_directories(
        execution_binding,
        refresh.download_requests,
    ) as document_binding:
        document_source = document_source_factory()
        document_binding.require_current()
        execution_binding.require_current(plan)
        typed_downloads, typed_outcomes = download_target_public_gap_requests(
            refresh=refresh,
            document_source=document_source,
            document_output_root=identity.document_output_root,
            allow_existing_downloads=allow_existing_downloads,
            bound_output_directories=document_binding.directories_by_request,
        )
        document_binding.require_current()
    execution_binding.require_current(plan)
    terminal_commitments = target_public_gap_terminal_commitments(
        plan=plan,
        plan_sha256=expected_plan_sha256,
        refresh=refresh,
        downloads=typed_downloads,
        outcomes=typed_outcomes,
    )
    execution_binding.require_current(plan)
    require_target_public_gap_sources_unchanged(plan)
    return TargetPublicGapExecutionResult(
        refresh=refresh,
        downloads=typed_downloads,
        outcomes=typed_outcomes,
        terminal_commitments=terminal_commitments,
    )


def download_target_public_gap_requests(
    *,
    refresh: TargetPublicGapRefreshResult,
    document_source: FreeDocumentSource,
    document_output_root: Path,
    allow_existing_downloads: bool,
    bound_output_directories: Mapping[str, Path] | None = None,
) -> tuple[
    tuple[FreeDocumentDownloadRecord, ...],
    tuple[Mapping[str, Any], ...],
]:
    """Durably download each identity and retain terminal content failures."""

    transition_by_key = {
        (
            cast(str, transition["candidate_id"]),
            cast(str, transition["source_document_id"]),
        ): transition
        for transition in refresh.transitions
    }
    downloads: list[FreeDocumentDownloadRecord] = []
    outcomes: list[Mapping[str, Any]] = list(refresh.gap_failures)
    for request in refresh.download_requests:
        key = (request.candidate_id, request.source_document_id)
        transition = transition_by_key[key]
        try:
            record = download_free_docket_documents(
                (request,),
                output_root=document_output_root,
                source=document_source,
                allow_existing=allow_existing_downloads,
                bound_output_directories=bound_output_directories,
            )[0]
        except FreeDocumentDownloadError as exc:
            if _retryable_download_failure(exc):
                raise
            if not _terminal_remote_content_failure(exc):
                raise
            outcomes.append(
                _gap_failure(
                    transition,
                    f"terminal_public_document_failure:{exc}",
                )
            )
            continue
        downloads.append(record)
        outcomes.append(
            {
                "schema_version": "legalforecast.target_public_gap_outcome.v1",
                "candidate_id": record.candidate_id,
                "source_document_id": record.source_document_id,
                "outcome": "newly_free",
                "transition_id": transition["transition_id"],
                "source_url": record.source_url,
                "local_path": record.local_path,
                "sha256": record.sha256,
                "byte_count": record.byte_count,
            }
        )
    typed_downloads = tuple(downloads)
    typed_outcomes = tuple(outcomes)
    return typed_downloads, typed_outcomes


def target_public_gap_terminal_commitments(
    *,
    plan: TargetPublicGapPlan,
    plan_sha256: str,
    refresh: TargetPublicGapRefreshResult,
    downloads: Sequence[FreeDocumentDownloadRecord],
    outcomes: Sequence[Mapping[str, Any]] | None = None,
) -> Mapping[str, object]:
    """Authenticate the terminal partition and newly free manifest."""

    if _SHA256.fullmatch(plan_sha256) is None:
        raise TargetPublicGapRefreshError("plan SHA-256 is invalid")
    expected = {
        (
            cast(str, gap["candidate_id"]),
            cast(str, gap["source_document_id"]),
        )
        for gap in plan.gaps
    }
    discovered = {
        (
            cast(str, record["candidate_id"]),
            cast(str, record["source_document_id"]),
        )
        for record in refresh.transitions
    }
    predownload_failures = {
        (
            cast(str, record["candidate_id"]),
            cast(str, record["source_document_id"]),
        )
        for record in refresh.gap_failures
    }
    if (
        len(discovered) != len(refresh.transitions)
        or len(predownload_failures) != len(refresh.gap_failures)
        or discovered & predownload_failures
        or discovered | predownload_failures != expected
    ):
        raise TargetPublicGapRefreshError(
            "public-gap terminal identity partition does not reconcile"
        )
    download_records = tuple(record.to_record() for record in downloads)
    downloaded = {
        (record.candidate_id, record.source_document_id) for record in downloads
    }
    terminal_outcomes = (
        tuple(outcomes)
        if outcomes is not None
        else tuple(
            [
                *refresh.gap_failures,
                *(
                    {
                        "schema_version": (
                            "legalforecast.target_public_gap_outcome.v1"
                        ),
                        "candidate_id": record.candidate_id,
                        "source_document_id": record.source_document_id,
                        "outcome": "newly_free",
                        "sha256": record.sha256,
                    }
                    for record in downloads
                ),
            ]
        )
    )
    terminal_keys = [
        (
            cast(str, outcome["candidate_id"]),
            cast(str, outcome["source_document_id"]),
        )
        for outcome in terminal_outcomes
    ]
    newly_free_keys = {
        key
        for key, outcome in zip(terminal_keys, terminal_outcomes, strict=True)
        if outcome.get("outcome") == "newly_free"
    }
    if (
        len(downloaded) != len(download_records)
        or downloaded != newly_free_keys
        or len(terminal_keys) != len(set(terminal_keys))
        or set(terminal_keys) != expected
        or any(
            outcome.get("outcome") not in {"newly_free", "terminal_gap_failure"}
            for outcome in terminal_outcomes
        )
        or any(record.free_or_purchased != "free" for record in downloads)
    ):
        raise TargetPublicGapRefreshError(
            "newly free download manifest does not match transitions"
        )
    return {
        "schema_version": ("legalforecast.target_public_gap_terminal_commitments.v1"),
        "plan_sha256": plan_sha256,
        "target_cohort_root": str(plan.target_cohort_root),
        "target_run_card_sha256": plan.target_run_card_sha256,
        "target_projection_file_sha256": plan.target_projection_file_sha256,
        "target_projection_sha256": plan.target_projection_sha256,
        "target_selection_file_sha256": plan.target_selection_file_sha256,
        "target_free_manifest_file_sha256": (plan.target_free_manifest_file_sha256),
        "selected_candidate_ids_sha256": plan.selected_candidate_ids_sha256,
        "selected_document_keys_sha256": plan.selected_document_keys_sha256,
        "required_gap_document_ids_sha256": (plan.required_gap_document_ids_sha256),
        "required_gap_document_count": len(plan.required_gap_document_ids),
        "gap_manifest_sha256": plan.gap_manifest_sha256,
        "docket_manifest_sha256": plan.docket_manifest_sha256,
        "discovered_transition_manifest_sha256": _records_sha256(refresh.transitions),
        "terminal_outcome_manifest_sha256": _records_sha256(terminal_outcomes),
        "newly_free_manifest_sha256": _records_sha256(download_records),
        "transition_count": len(newly_free_keys),
        "exclusion_count": len(terminal_outcomes) - len(newly_free_keys),
        "newly_free_document_count": len(download_records),
        "purchased_document_count": 0,
        "purchased_activity_requested": False,
        "purchased_activity_executed": False,
        "terminal_reconciliation": True,
    }


def _unique_planned_document(
    gap: Mapping[str, Any],
    *,
    planned: PublicPacketCandidatePlan,
    bundle: CourtListenerDocketBundle,
) -> PublicPacketDocumentPlan | None:
    entry_number = cast(int, gap["docket_entry_number"])
    role = cast(str, gap["document_role"])
    matches = tuple(
        document
        for document in planned.documents
        if document.docket_entry_number == entry_number
        and document.document_role.value == role
    )
    if len(matches) != 1:
        return None
    planned_document = matches[0]
    entries = tuple(
        entry for entry in bundle.entries if entry.entry_number == str(entry_number)
    )
    if len(entries) != 1 or entries[0].restricted:
        return None
    free_documents = tuple(
        document
        for document in entries[0].documents
        if document.freely_available and document.href == planned_document.source_url
    )
    if len(free_documents) != 1:
        return None
    observed = free_documents[0]
    source_document_id = cast(str, gap["source_document_id"])
    exact_description = " ".join(
        cast(str, gap["description"]).lower().split()
    ) == " ".join(observed.description.lower().split())
    if source_document_id not in planned_document.source_url and not exact_description:
        return None
    try:
        if public_recap_download_url(planned_document.source_url) != (
            planned_document.source_url
        ):
            return None
    except ValueError:
        return None
    return planned_document


def _source_page(
    gap: Mapping[str, Any],
    bundle: CourtListenerDocketBundle,
):
    entry_id = cast(str, gap["courtlistener_docket_entry_id"])
    row_ids = {f"entry-{entry_id}", f"minute-entry-{entry_id}"}
    pages = tuple(
        page for page in bundle.pages if row_ids.intersection(page.entry_row_ids)
    )
    if len(pages) != 1:
        raise TargetPublicGapRefreshError("gap entry lacks unique page provenance")
    return pages[0]


def _screened_record(selection: Mapping[str, Any]) -> Mapping[str, Any]:
    candidate_id = _text(selection.get("candidate_id"), "candidate ID")
    return {
        "candidate": {
            "docket_id": candidate_id,
            "url": _canonical_docket_url(selection, candidate_id),
            "metadata": {
                name: selection.get(name)
                for name in (
                    "case_id",
                    "case_name",
                    "court",
                    "docket_number",
                    "nature_of_suit",
                    "nos_macro_category",
                    "related_family_id",
                    "mdl_family_id",
                    "case_type_stratum",
                )
            },
        },
        "ai": {
            "target_motion_entry_numbers": selection.get("target_motion_entry_numbers"),
            "decision_entry_numbers": selection.get("decision_entry_numbers"),
        },
        "first_written_mtd_disposition_date": selection.get("decision_date"),
    }


def _canonical_docket_url(selection: Mapping[str, Any], candidate_id: str) -> str:
    source_url = _text(selection.get("source_url"), "CourtListener docket URL")
    try:
        canonical_courtlistener_docket_page_url(source_url, page_number=1)
    except CourtListenerDocketPaginationError as exc:
        raise TargetPublicGapRefreshError(str(exc)) from exc
    if f"/docket/{candidate_id}/" not in source_url:
        raise TargetPublicGapRefreshError("target docket URL identity mismatch")
    return source_url


def _gap_failure(gap: Mapping[str, Any], reason: str) -> Mapping[str, Any]:
    return {
        "schema_version": "legalforecast.target_public_gap_outcome.v1",
        "candidate_id": gap["candidate_id"],
        "source_document_id": gap["source_document_id"],
        "outcome": "terminal_gap_failure",
        "reason": reason,
    }


def _retryable_download_failure(error: FreeDocumentDownloadError) -> bool:
    cause = error.__cause__
    if isinstance(cause, urllib.error.HTTPError):
        return cause.code in {408, 425, 429, 500, 502, 503, 504}
    return isinstance(cause, (TimeoutError, urllib.error.URLError))


def _terminal_remote_content_failure(error: FreeDocumentDownloadError) -> bool:
    return str(error).startswith(_TERMINAL_REMOTE_CONTENT_FAILURE_PREFIXES)


def _records(value: object, label: str) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise TargetPublicGapRefreshError(f"{label} must be a sequence")
    records: list[Mapping[str, Any]] = []
    for record in cast(Sequence[object], value):
        if not isinstance(record, Mapping):
            raise TargetPublicGapRefreshError(f"{label} must contain objects")
        records.append(cast(Mapping[str, Any], record))
    return tuple(records)


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TargetPublicGapRefreshError(f"{label} must be an object")
    return cast(Mapping[str, Any], value)


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TargetPublicGapRefreshError(f"{label} must be nonempty")
    return value.strip()


def _positive_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise TargetPublicGapRefreshError(f"{label} must be positive")
    return value


def _path(value: object, label: str) -> Path:
    if not isinstance(value, Path):
        raise TargetPublicGapRefreshError(f"{label} must be a path")
    return value


def _digest(value: object, label: str) -> str:
    text = _text(value, label)
    digest = text.removeprefix("sha256:")
    if _SHA256.fullmatch(digest) is None:
        raise TargetPublicGapRefreshError(f"{label} is invalid")
    return "sha256:" + digest


def _file_sha256(
    artifact_bytes: Mapping[str, Any],
    path: Path,
    label: str,
) -> str:
    payload = artifact_bytes.get(str(path.absolute()))
    if not isinstance(payload, bytes):
        raise TargetPublicGapRefreshError(
            f"{label} bytes are absent from authenticated target snapshot"
        )
    return hashlib.sha256(payload).hexdigest()


def _source_artifact_commitments(
    artifact_bytes: Mapping[str, Any],
) -> Mapping[str, str]:
    commitments: dict[str, str] = {}
    for raw_path, raw_payload in artifact_bytes.items():
        if not Path(raw_path).is_absolute():
            raise TargetPublicGapRefreshError(
                "verified target artifact path must be absolute"
            )
        if not isinstance(raw_payload, bytes):
            raise TargetPublicGapRefreshError(
                "verified target artifact snapshot must contain bytes"
            )
        path = str(Path(raw_path).resolve())
        if path in commitments:
            raise TargetPublicGapRefreshError(
                "verified target artifact paths alias after resolution"
            )
        commitments[path] = hashlib.sha256(raw_payload).hexdigest()
    if not commitments:
        raise TargetPublicGapRefreshError("verified target artifact closure is empty")
    return dict(sorted(commitments.items()))


def _records_sha256(records: Sequence[Mapping[str, Any]]) -> str:
    return (
        "sha256:"
        + hashlib.sha256(
            b"".join(canonical_json_bytes(dict(record)) for record in records)
        ).hexdigest()
    )


def _value_sha256(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _semantic_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _open_existing_directory_no_follow(path: Path, *, label: str) -> int:
    absolute = Path(os.path.abspath(path))
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    directory_fd: int | None = None
    try:
        directory_fd = os.open(absolute.anchor, flags)
        for component in absolute.parts[1:]:
            next_fd = os.open(component, flags, dir_fd=directory_fd)
            os.close(directory_fd)
            directory_fd = next_fd
        return directory_fd
    except OSError as exc:
        if directory_fd is not None:
            os.close(directory_fd)
        raise TargetPublicGapRefreshError(
            f"{label} traverses a symlink or is not an existing directory"
        ) from exc


def _open_or_create_directory_no_follow(path: Path, *, label: str) -> int:
    absolute = Path(os.path.abspath(path))
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    directory_fd: int | None = None
    try:
        directory_fd = os.open(absolute.anchor, flags)
        for component in absolute.parts[1:]:
            try:
                next_fd = os.open(component, flags, dir_fd=directory_fd)
            except FileNotFoundError:
                os.mkdir(component, mode=0o700, dir_fd=directory_fd)
                os.fsync(directory_fd)
                next_fd = os.open(component, flags, dir_fd=directory_fd)
            os.close(directory_fd)
            directory_fd = next_fd
        _require_named_directory_binding(
            absolute,
            directory_fd,
            label=label,
        )
        return directory_fd
    except TargetPublicGapRefreshError:
        if directory_fd is not None:
            os.close(directory_fd)
        raise
    except OSError as exc:
        if directory_fd is not None:
            os.close(directory_fd)
        raise TargetPublicGapRefreshError(
            f"{label} cannot be created or opened without following links"
        ) from exc


def _open_or_create_child_directory(
    parent_fd: int,
    name: str,
    *,
    label: str,
) -> int:
    if not name or "/" in name or name in {".", ".."}:
        raise TargetPublicGapRefreshError(f"{label} has an invalid child name")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    try:
        descriptor = os.open(name, flags, dir_fd=parent_fd)
    except FileNotFoundError:
        try:
            os.mkdir(name, mode=0o700, dir_fd=parent_fd)
            os.fsync(parent_fd)
            descriptor = os.open(name, flags, dir_fd=parent_fd)
        except OSError as exc:
            raise TargetPublicGapRefreshError(
                f"{label} cannot be created without following links"
            ) from exc
    except OSError as exc:
        raise TargetPublicGapRefreshError(
            f"{label} cannot be opened without following links"
        ) from exc
    metadata = os.fstat(descriptor)
    if not stat.S_ISDIR(metadata.st_mode):
        os.close(descriptor)
        raise TargetPublicGapRefreshError(f"{label} is not a directory")
    return descriptor


def _open_child_directory_if_present(
    parent_fd: int,
    name: str,
    *,
    label: str,
) -> int | None:
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    try:
        return os.open(name, flags, dir_fd=parent_fd)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise TargetPublicGapRefreshError(
            f"{label} must be a non-symlink directory"
        ) from exc


def _require_child_directory_binding(
    parent_fd: int,
    name: str,
    descriptor: int,
    *,
    label: str,
) -> None:
    opened = os.fstat(descriptor)
    try:
        named = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except OSError as exc:
        raise TargetPublicGapRefreshError(
            f"{label} changed while its directory binding was active"
        ) from exc
    if (
        not stat.S_ISDIR(opened.st_mode)
        or not stat.S_ISDIR(named.st_mode)
        or (opened.st_dev, opened.st_ino) != (named.st_dev, named.st_ino)
    ):
        raise TargetPublicGapRefreshError(
            f"{label} changed while its directory binding was active"
        )


def _read_unique_regular_file_at_named(
    parent_fd: int,
    name: str,
    *,
    label: str,
) -> bytes:
    descriptor: int | None = None
    try:
        descriptor = os.open(
            name,
            os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=parent_fd,
        )
        before = os.fstat(descriptor)
        named_before = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or _stable_stat_identity(before) != _stable_stat_identity(named_before)
        ):
            raise TargetPublicGapRefreshError(
                f"{label} is not a stable unique regular file"
            )
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
        after = os.fstat(descriptor)
        named_after = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if _stable_stat_identity(before) != _stable_stat_identity(
            after
        ) or _stable_stat_identity(before) != _stable_stat_identity(named_after):
            raise TargetPublicGapRefreshError(f"{label} changed while it was read")
        payload = b"".join(chunks)
        if len(payload) != after.st_size:
            raise TargetPublicGapRefreshError(f"{label} changed while it was read")
        return payload
    except OSError as exc:
        raise TargetPublicGapRefreshError(
            f"{label} is not a stable unique regular file"
        ) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _read_directory_tree_at(root_fd: int) -> dict[str, bytes]:
    result: dict[str, bytes] = {}

    def visit(directory_fd: int, prefix: tuple[str, ...]) -> None:
        try:
            names = sorted(os.listdir(directory_fd))
        except OSError as exc:
            raise TargetPublicGapRefreshError(
                "published output directory cannot be enumerated safely"
            ) from exc
        for name in names:
            relative = "/".join((*prefix, name))
            try:
                metadata = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            except OSError as exc:
                raise TargetPublicGapRefreshError(
                    f"published output contains an unsafe artifact: {relative}"
                ) from exc
            if stat.S_ISDIR(metadata.st_mode):
                child_fd = _open_child_directory_if_present(
                    directory_fd,
                    name,
                    label=f"published output directory {relative}",
                )
                if child_fd is None:
                    raise TargetPublicGapRefreshError(
                        f"published output directory changed: {relative}"
                    )
                try:
                    visit(child_fd, (*prefix, name))
                    _require_child_directory_binding(
                        directory_fd,
                        name,
                        child_fd,
                        label=f"published output directory {relative}",
                    )
                finally:
                    os.close(child_fd)
            elif stat.S_ISREG(metadata.st_mode) and metadata.st_nlink == 1:
                result[relative] = _read_unique_regular_file_at_named(
                    directory_fd,
                    name,
                    label=f"published output artifact {relative}",
                )
            else:
                raise TargetPublicGapRefreshError(
                    f"published output contains an unsafe artifact: {relative}"
                )

    visit(root_fd, ())
    return result


def _write_unique_regular_file_at(
    parent_fd: int,
    name: str,
    payload: bytes,
    *,
    label: str,
) -> None:
    try:
        existing = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        existing = None
    except OSError as exc:
        raise TargetPublicGapRefreshError(f"{label} cannot be inspected") from exc
    if existing is not None:
        if _read_unique_regular_file_at_named(parent_fd, name, label=label) != payload:
            raise TargetPublicGapRefreshError(f"{label} differs")
        return
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
    try:
        descriptor = os.open(name, flags, 0o600, dir_fd=parent_fd)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.fsync(parent_fd)
    except OSError as exc:
        raise TargetPublicGapRefreshError(
            f"{label} cannot be published as a unique regular file"
        ) from exc


def _descriptor_path(descriptor: int) -> Path:
    return Path(f"/proc/self/fd/{descriptor}")


def _download_request_key(request: FreeDocumentDownloadRequest) -> str:
    return "\0".join(
        (
            request.candidate_id,
            request.source_provider,
            request.source_document_id,
        )
    )


def _read_unique_regular_file_at(directory_fd: int, name: str) -> bytes:
    flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC
    descriptor = os.open(name, flags, dir_fd=directory_fd)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise TargetPublicGapRefreshError(
                "target public-gap plan is not a unique regular file"
            )
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
        after = os.fstat(descriptor)
        stable_fields = (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_nlink",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
        if any(
            getattr(before, field) != getattr(after, field) for field in stable_fields
        ):
            raise TargetPublicGapRefreshError(
                "target public-gap plan changed while it was read"
            )
        payload = b"".join(chunks)
        if len(payload) != after.st_size:
            raise TargetPublicGapRefreshError(
                "target public-gap plan changed while it was read"
            )
        named = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if any(
            getattr(after, field) != getattr(named, field) for field in stable_fields
        ):
            raise TargetPublicGapRefreshError(
                "target public-gap plan directory entry changed while it was read"
            )
        return payload
    finally:
        os.close(descriptor)


def _require_named_directory_binding(
    path: Path,
    directory_fd: int,
    *,
    label: str,
) -> None:
    opened = os.fstat(directory_fd)
    try:
        named = os.stat(path, follow_symlinks=False)
    except OSError as exc:
        raise TargetPublicGapRefreshError(
            f"{label} changed while its directory binding was active"
        ) from exc
    if (
        not stat.S_ISDIR(opened.st_mode)
        or not stat.S_ISDIR(named.st_mode)
        or (opened.st_dev, opened.st_ino) != (named.st_dev, named.st_ino)
    ):
        raise TargetPublicGapRefreshError(
            f"{label} changed while its directory binding was active"
        )


def _reject_plan_destination_overlap(
    destination: Path,
    *,
    plan: TargetPublicGapPlan,
) -> None:
    resolved_destination = destination.resolve(strict=False)
    tree_roots = (
        ("target root", plan.target_cohort_root.resolve()),
        ("final output root", plan.execution_identity.output_root.resolve()),
        ("raw HTML root", plan.execution_identity.raw_html_root.resolve()),
        (
            "document output root",
            plan.execution_identity.document_output_root.resolve(),
        ),
    )
    for label, root in tree_roots:
        if (
            resolved_destination == root
            or resolved_destination.is_relative_to(root)
            or root.is_relative_to(resolved_destination)
        ):
            raise TargetPublicGapRefreshError(f"plan output overlaps {label}")
    cycle_store = plan.execution_identity.cycle_store_path.resolve()
    if (
        resolved_destination == cycle_store
        or resolved_destination.is_relative_to(cycle_store)
        or cycle_store.is_relative_to(resolved_destination)
    ):
        raise TargetPublicGapRefreshError("plan output overlaps cycle store")
    for raw_source in plan.source_artifact_commitments:
        source = Path(raw_source).resolve()
        if (
            resolved_destination == source
            or resolved_destination.is_relative_to(source)
            or source.is_relative_to(resolved_destination)
        ):
            raise TargetPublicGapRefreshError(
                f"plan output overlaps authenticated source: {source}"
            )


def _reject_symlink_components(path: Path, *, label: str) -> None:
    current = path
    existing: list[Path] = []
    while True:
        if current.exists() or current.is_symlink():
            existing.append(current)
        if current == current.parent:
            break
        current = current.parent
    for component in reversed(existing):
        try:
            if stat.S_ISLNK(component.lstat().st_mode):
                raise TargetPublicGapRefreshError(
                    f"{label} traverses a symlink: {component}"
                )
        except OSError as exc:
            raise TargetPublicGapRefreshError(
                f"cannot inspect {label} path safety"
            ) from exc


def _validated_relative_payloads(
    payloads: Mapping[str, bytes],
) -> dict[str, bytes]:
    if not payloads:
        raise TargetPublicGapRefreshError("terminal payload set is empty")
    result: dict[str, bytes] = {}
    for relative, payload in sorted(payloads.items()):
        path = Path(relative)
        if (
            not relative
            or path.is_absolute()
            or any(part in {"", ".", ".."} for part in path.parts)
        ):
            raise TargetPublicGapRefreshError(
                "terminal payload path or bytes are invalid"
            )
        result[path.as_posix()] = payload
    return result


def _reject_existing_work_tree(root: Path, *, label: str) -> None:
    for path in root.rglob("*"):
        metadata = path.lstat()
        if stat.S_ISDIR(metadata.st_mode):
            continue
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
            or path.is_symlink()
        ):
            raise TargetPublicGapRefreshError(
                f"{label} contains a symlink, hard-link, or special file"
            )


def _stable_stat_identity(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_nlink,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _published_tree_bytes(root: Path) -> dict[str, bytes]:
    root_fd = _open_existing_directory_no_follow(
        root,
        label="published output",
    )
    try:
        tree = _read_directory_tree_at(root_fd)
        _require_named_directory_binding(
            root,
            root_fd,
            label="published output",
        )
        return tree
    finally:
        os.close(root_fd)


def _verify_completed_output_for_plan(
    plan: TargetPublicGapPlan,
    *,
    expected_plan_sha256: str,
) -> None:
    if _SHA256.fullmatch(expected_plan_sha256) is None:
        raise TargetPublicGapRefreshError("plan SHA-256 is invalid")
    root = plan.execution_identity.output_root.absolute()
    tree = _published_tree_bytes(root)
    if set(tree) != set(_TARGET_PUBLIC_GAP_ALL_OUTPUTS):
        raise TargetPublicGapRefreshError(
            "preexisting final output tree lacks the exact required artifacts"
        )
    try:
        loaded_run_card: object = json.loads(tree[_TARGET_PUBLIC_GAP_RUN_CARD])
        loaded_summary: object = json.loads(tree[_TARGET_PUBLIC_GAP_SUMMARY])
        log_lines = tree[_TARGET_PUBLIC_GAP_LOG].splitlines()
        loaded_log: object = json.loads(log_lines[0])
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise TargetPublicGapRefreshError(
            "preexisting final output lacks a valid execution receipt"
        ) from exc
    if (
        not isinstance(loaded_run_card, Mapping)
        or not isinstance(loaded_summary, Mapping)
        or not isinstance(loaded_log, Mapping)
    ):
        raise TargetPublicGapRefreshError(
            "preexisting final output receipt must contain objects"
        )
    run_card = cast(Mapping[str, object], loaded_run_card)
    summary = cast(Mapping[str, object], loaded_summary)
    log = cast(Mapping[str, object], loaded_log)
    if set(run_card) != set(_TARGET_PUBLIC_GAP_RECEIPT_FIELDS):
        raise TargetPublicGapRefreshError(
            "preexisting final output receipt has an invalid closed schema"
        )
    if set(summary) != set(_TARGET_PUBLIC_GAP_SUMMARY_FIELDS):
        raise TargetPublicGapRefreshError(
            "preexisting final output summary has an invalid closed schema"
        )
    if set(log) != {
        "schema_version",
        "event",
        "plan_sha256",
        "run_card_sha256",
    }:
        raise TargetPublicGapRefreshError(
            "preexisting final output log has an invalid closed schema"
        )
    plan_path = run_card.get("plan_path")
    if (
        run_card.get("schema_version")
        != "legalforecast.target_public_gap_execution_receipt.v1"
        or run_card.get("stage") != "execute-target-public-gaps"
        or run_card.get("status") != "completed"
        or not isinstance(plan_path, str)
        or not Path(plan_path).is_absolute()
        or run_card.get("plan_sha256") != expected_plan_sha256
        or run_card.get("execution_identity") != plan.execution_identity.to_record()
        or run_card.get("fresh_credit_cap") != plan.fresh_credit_cap
        or run_card.get("input_paths") != sorted(plan.source_artifact_commitments)
        or run_card.get("source_artifact_commitments")
        != plan.source_artifact_commitments
        or run_card.get("purchased_document_count") != 0
        or not isinstance(run_card.get("provider_activity_requested"), bool)
        or any(
            run_card.get(field) is not False
            for field in (
                "pacer_authorized",
                "recap_fetch_authorized",
                "document_purchase_authorized",
                "model_calls_authorized",
                "evaluation_authorized",
                "freeze_or_dispatch_authorized",
                "purchased_activity_requested",
                "purchased_activity_executed",
            )
        )
        or len(log_lines) != 1
        or log.get("schema_version")
        != "legalforecast.target_public_gap_execution_log.v1"
        or log.get("event") != "completed"
        or log.get("plan_sha256") != expected_plan_sha256
        or log.get("run_card_sha256")
        != hashlib.sha256(tree[_TARGET_PUBLIC_GAP_RUN_CARD]).hexdigest()
    ):
        raise TargetPublicGapRefreshError(
            "preexisting final output receipt differs from current execution"
        )
    raw_paths_object = run_card.get("output_paths")
    commitments_object = run_card.get("output_commitments")
    if (
        not isinstance(raw_paths_object, Sequence)
        or isinstance(raw_paths_object, (str, bytes))
        or not isinstance(commitments_object, Mapping)
    ):
        raise TargetPublicGapRefreshError(
            "preexisting final output receipt lacks exact commitments"
        )
    raw_paths = cast(Sequence[object], raw_paths_object)
    untyped_commitments = cast(Mapping[object, object], commitments_object)
    if any(not isinstance(key, str) for key in untyped_commitments):
        raise TargetPublicGapRefreshError(
            "preexisting final output receipt commitment name is invalid"
        )
    commitments = cast(Mapping[str, object], commitments_object)
    expected_names: list[str] = []
    for raw_path in raw_paths:
        if not isinstance(raw_path, str):
            raise TargetPublicGapRefreshError(
                "preexisting final output path is invalid"
            )
        path = Path(raw_path).absolute()
        try:
            expected_names.append(path.relative_to(root).as_posix())
        except ValueError as exc:
            raise TargetPublicGapRefreshError(
                "preexisting final output path escapes its root"
            ) from exc
    if len(expected_names) != len(set(expected_names)) or set(expected_names) != set(
        _TARGET_PUBLIC_GAP_ALL_OUTPUTS
    ):
        raise TargetPublicGapRefreshError(
            "preexisting final output tree differs from its receipt"
        )
    if set(commitments) != set(_TARGET_PUBLIC_GAP_COMMITTED_OUTPUTS):
        raise TargetPublicGapRefreshError(
            "preexisting final output receipt lacks exact core commitments"
        )
    for raw_name, raw_digest in commitments.items():
        if (
            not isinstance(raw_digest, str)
            or _SHA256.fullmatch(raw_digest) is None
            or raw_name not in tree
            or hashlib.sha256(tree[raw_name]).hexdigest() != raw_digest
        ):
            raise TargetPublicGapRefreshError(
                "preexisting final output commitment differs"
            )
    _verify_target_public_gap_summary(
        plan,
        expected_plan_sha256=expected_plan_sha256,
        tree=tree,
        run_card=run_card,
        summary=summary,
    )


def _verify_target_public_gap_summary(
    plan: TargetPublicGapPlan,
    *,
    expected_plan_sha256: str,
    tree: Mapping[str, bytes],
    run_card: Mapping[str, object],
    summary: Mapping[str, object],
) -> None:
    summary_commitments_object = summary.get("output_commitments")
    terminal_commitments_object = summary.get("terminal_commitments")
    if (
        not isinstance(summary_commitments_object, Mapping)
        or not isinstance(terminal_commitments_object, Mapping)
        or run_card.get("terminal_commitments") != terminal_commitments_object
        or summary.get("schema_version")
        != "legalforecast.target_public_gap_execution_summary.v1"
        or summary.get("plan_sha256") != expected_plan_sha256
        or summary.get("terminal_reconciliation") is not True
        or not isinstance(summary.get("provider_activity_requested"), bool)
        or not isinstance(
            summary.get("firecrawl_metered_activity_requested"),
            bool,
        )
        or not isinstance(
            summary.get("public_download_activity_requested"),
            bool,
        )
        or summary.get("provider_activity_requested")
        != (
            summary.get("firecrawl_metered_activity_requested") is True
            or summary.get("public_download_activity_requested") is True
        )
        or run_card.get("provider_activity_requested")
        != summary.get("provider_activity_requested")
        or summary.get("purchased_document_count") != 0
        or any(
            summary.get(field) is not False
            for field in (
                "pacer_authorized",
                "recap_fetch_authorized",
                "document_purchase_authorized",
                "model_calls_authorized",
                "evaluation_authorized",
                "freeze_or_dispatch_authorized",
                "purchased_activity_requested",
                "purchased_activity_executed",
            )
        )
    ):
        raise TargetPublicGapRefreshError(
            "preexisting final output summary differs from current execution"
        )
    untyped_summary_commitments = cast(
        Mapping[object, object],
        summary_commitments_object,
    )
    if any(not isinstance(key, str) for key in untyped_summary_commitments):
        raise TargetPublicGapRefreshError(
            "preexisting final output summary commitment name is invalid"
        )
    summary_commitments = cast(Mapping[str, object], summary_commitments_object)
    if set(summary_commitments) != set(_TARGET_PUBLIC_GAP_DATA_OUTPUTS):
        raise TargetPublicGapRefreshError(
            "preexisting final output summary lacks exact data commitments"
        )
    for raw_name, raw_digest in summary_commitments.items():
        if (
            not isinstance(raw_digest, str)
            or _SHA256.fullmatch(raw_digest) is None
            or hashlib.sha256(tree[raw_name]).hexdigest() != raw_digest
        ):
            raise TargetPublicGapRefreshError(
                "preexisting final output summary commitment differs"
            )
    _verify_target_public_gap_terminal_commitments(
        plan,
        expected_plan_sha256=expected_plan_sha256,
        tree=tree,
        terminal_commitments=cast(
            Mapping[str, object],
            terminal_commitments_object,
        ),
    )


def _verify_target_public_gap_terminal_commitments(
    plan: TargetPublicGapPlan,
    *,
    expected_plan_sha256: str,
    tree: Mapping[str, bytes],
    terminal_commitments: Mapping[str, object],
) -> None:
    if set(terminal_commitments) != set(_TARGET_PUBLIC_GAP_TERMINAL_FIELDS):
        raise TargetPublicGapRefreshError(
            "preexisting terminal commitments have an invalid closed schema"
        )
    static_expected: Mapping[str, object] = {
        "schema_version": ("legalforecast.target_public_gap_terminal_commitments.v1"),
        "plan_sha256": expected_plan_sha256,
        "target_cohort_root": str(plan.target_cohort_root),
        "target_run_card_sha256": plan.target_run_card_sha256,
        "target_projection_file_sha256": plan.target_projection_file_sha256,
        "target_projection_sha256": plan.target_projection_sha256,
        "target_selection_file_sha256": plan.target_selection_file_sha256,
        "target_free_manifest_file_sha256": plan.target_free_manifest_file_sha256,
        "selected_candidate_ids_sha256": plan.selected_candidate_ids_sha256,
        "selected_document_keys_sha256": plan.selected_document_keys_sha256,
        "required_gap_document_ids_sha256": plan.required_gap_document_ids_sha256,
        "required_gap_document_count": len(plan.required_gap_document_ids),
        "gap_manifest_sha256": plan.gap_manifest_sha256,
        "docket_manifest_sha256": plan.docket_manifest_sha256,
        "purchased_document_count": 0,
        "purchased_activity_requested": False,
        "purchased_activity_executed": False,
        "terminal_reconciliation": True,
    }
    if any(
        terminal_commitments.get(field) != expected
        for field, expected in static_expected.items()
    ):
        raise TargetPublicGapRefreshError(
            "preexisting terminal commitments differ from current plan"
        )
    transitions = _jsonl_mapping_records(
        tree["target-public-gap-discovered-transitions.jsonl"],
        label="discovered transitions",
    )
    outcomes = _jsonl_mapping_records(
        tree["target-public-gap-outcomes.jsonl"],
        label="terminal outcomes",
    )
    downloads = _jsonl_mapping_records(
        tree["free-document-downloads.jsonl"],
        label="free document downloads",
    )
    requests = _jsonl_mapping_records(
        tree["free-document-requests.jsonl"],
        label="free document requests",
    )
    transition_keys = [
        _artifact_identity(transition, label="discovered transition")
        for transition in transitions
    ]
    request_keys = [
        _artifact_identity(request, label="free document request")
        for request in requests
    ]
    outcome_keys = [
        _artifact_identity(outcome, label="terminal outcome") for outcome in outcomes
    ]
    expected_keys = {
        (gap["candidate_id"], gap["source_document_id"]) for gap in plan.gaps
    }
    newly_free = [
        outcome for outcome in outcomes if outcome.get("outcome") == "newly_free"
    ]
    newly_free_keys = {
        _artifact_identity(outcome, label="newly free outcome")
        for outcome in newly_free
    }
    download_keys = {
        _artifact_identity(download, label="free document download")
        for download in downloads
    }
    newly_free_by_key = {
        _artifact_identity(outcome, label="newly free outcome"): outcome
        for outcome in newly_free
    }
    downloads_by_key = {
        _artifact_identity(download, label="free document download"): download
        for download in downloads
    }
    excluded = [
        outcome
        for outcome in outcomes
        if outcome.get("outcome") == "terminal_gap_failure"
    ]
    if (
        len(transition_keys) != len(set(transition_keys))
        or len(request_keys) != len(set(request_keys))
        or set(transition_keys) != set(request_keys)
        or len(outcome_keys) != len(set(outcome_keys))
        or set(outcome_keys) != expected_keys
        or download_keys != newly_free_keys
        or len(download_keys) != len(downloads)
        or any(
            newly_free_by_key[key].get(field) != downloads_by_key[key].get(field)
            for key in download_keys
            for field in (
                "source_url",
                "local_path",
                "sha256",
                "byte_count",
            )
        )
        or len(newly_free) + len(excluded) != len(outcomes)
        or terminal_commitments.get("discovered_transition_manifest_sha256")
        != _records_sha256(transitions)
        or terminal_commitments.get("terminal_outcome_manifest_sha256")
        != _records_sha256(outcomes)
        or terminal_commitments.get("newly_free_manifest_sha256")
        != _records_sha256(downloads)
        or terminal_commitments.get("transition_count") != len(newly_free)
        or terminal_commitments.get("exclusion_count") != len(excluded)
        or terminal_commitments.get("newly_free_document_count") != len(downloads)
    ):
        raise TargetPublicGapRefreshError(
            "preexisting terminal commitments do not reconcile"
        )


def _artifact_identity(
    record: Mapping[str, Any],
    *,
    label: str,
) -> tuple[str, str]:
    candidate_id = record.get("candidate_id")
    source_document_id = record.get("source_document_id")
    if (
        not isinstance(candidate_id, str)
        or not candidate_id
        or not isinstance(source_document_id, str)
        or not source_document_id
    ):
        raise TargetPublicGapRefreshError(f"preexisting {label} identity is invalid")
    return candidate_id, source_document_id


def _jsonl_mapping_records(
    payload: bytes,
    *,
    label: str,
) -> tuple[Mapping[str, Any], ...]:
    try:
        lines = payload.splitlines()
        if any(not line.strip() for line in lines):
            raise ValueError
        loaded = tuple(json.loads(line) for line in lines)
    except (TypeError, ValueError) as exc:
        raise TargetPublicGapRefreshError(
            f"preexisting {label} artifact is invalid"
        ) from exc
    if any(not isinstance(record, Mapping) for record in loaded):
        raise TargetPublicGapRefreshError(
            f"preexisting {label} artifact must contain objects"
        )
    return cast(tuple[Mapping[str, Any], ...], loaded)


def _acquire_output_lock_at(parent_fd: int, name: str) -> int:
    flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC
    descriptor: int | None = None
    try:
        descriptor = os.open(name, flags, 0o600, dir_fd=parent_fd)
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise TargetPublicGapRefreshError(
                "output lock must be a singly linked regular file"
            )
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        named = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if (
            not stat.S_ISREG(named.st_mode)
            or named.st_nlink != 1
            or (metadata.st_dev, metadata.st_ino) != (named.st_dev, named.st_ino)
        ):
            raise TargetPublicGapRefreshError("output lock changed while acquiring")
        return descriptor
    except Exception:
        if descriptor is not None:
            os.close(descriptor)
        raise


def _release_output_lock(descriptor: int) -> None:
    try:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)
