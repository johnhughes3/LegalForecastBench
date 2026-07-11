"""Recover fee-acknowledged purchased documents into provenance records."""

from __future__ import annotations

import hashlib
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from http.client import HTTPMessage
from pathlib import Path
from typing import IO, Any, cast

from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPacerCapability,
    CaseDevPacerPurchaseAttempt,
    CaseDevPacerPurchaseStatus,
)
from legalforecast.ingestion.free_document_downloader import (
    FreeDocumentFetch,
    FreeDocumentSource,
)
from legalforecast.ingestion.missing_core_budget import (
    DEFAULT_MAX_MISSING_CORE_DOCUMENTS_PER_CASE,
    DEFAULT_MAX_PROJECTED_BUDGET_USD,
)
from legalforecast.ingestion.provenance import (
    AvailabilityStatus,
    DocumentRole,
    RedactionOrSealStatus,
    SourceDocumentProvenance,
)
from legalforecast.path_safety import safe_path_component

_PURCHASED_PROVIDER = "case.dev+pacer"
_PURCHASED_PROVIDER_PATH = "case-dev-pacer"
_ALLOWED_PURCHASED_DOCUMENT_HOSTS = frozenset(
    {"api.case.dev", "sandbox.case.dev", "case.dev"}
)
_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
_DEFAULT_USER_AGENT = (
    "LegalForecastBench/0.1 (fee-acknowledged case.dev document recovery)"
)
_DEFAULT_MAX_RESPONSE_BYTES = 100 * 1024 * 1024
_DOWNLOAD_CHUNK_BYTES = 1024 * 1024


class PurchasedDocumentRecoveryError(ValueError):
    """Raised when purchase evidence cannot safely drive document recovery."""


class PurchasedDocumentDownloadError(RuntimeError):
    """Raised when an allowlisted purchased document cannot be downloaded."""


class _ValidatedPurchasedDocumentRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Validate every redirect before opening it and contain bearer credentials."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> urllib.request.Request | None:
        _validate_purchased_document_url(newurl)
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is None:
            return None
        if (
            urllib.parse.urlparse(req.full_url).hostname
            != urllib.parse.urlparse(newurl).hostname
        ):
            redirected.remove_header("Authorization")
        return redirected


@dataclass(frozen=True, slots=True)
class UrlLibPurchasedDocumentSource:
    """Authenticated download-only source for successful case.dev purchases."""

    api_key: str
    timeout_seconds: float = 60.0
    max_retries: int = 2
    retry_backoff_seconds: float = 1.0
    user_agent: str = _DEFAULT_USER_AGENT
    max_response_bytes: int = _DEFAULT_MAX_RESPONSE_BYTES

    def __post_init__(self) -> None:
        if not self.api_key.strip():
            raise PurchasedDocumentRecoveryError(
                "CASE_DEV_API_KEY is required for live purchased-document recovery"
            )
        if self.timeout_seconds <= 0:
            raise PurchasedDocumentRecoveryError("timeout_seconds must be positive")
        if self.max_retries < 0:
            raise PurchasedDocumentRecoveryError("max_retries must be nonnegative")
        if self.retry_backoff_seconds < 0:
            raise PurchasedDocumentRecoveryError(
                "retry_backoff_seconds must be nonnegative"
            )
        if self.max_response_bytes <= 0:
            raise PurchasedDocumentRecoveryError("max_response_bytes must be positive")

    def fetch(self, source_url: str) -> FreeDocumentFetch:
        """Fetch one already-purchased document; never invokes a purchase API."""

        _validate_purchased_document_url(source_url)
        retry_count = 0
        rate_limited = False
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            if attempt > 0:
                retry_count += 1
                time.sleep(self.retry_backoff_seconds * attempt)
            try:
                return self._fetch_once(
                    source_url,
                    retry_count=retry_count,
                    rate_limited=rate_limited,
                )
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code == 429:
                    rate_limited = True
                if (
                    exc.code not in _RETRYABLE_STATUS_CODES
                    or attempt >= self.max_retries
                ):
                    break
            except (TimeoutError, urllib.error.URLError) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
        raise PurchasedDocumentDownloadError(
            f"failed to download purchased case.dev document {source_url}: {last_error}"
        ) from last_error

    def _fetch_once(
        self,
        source_url: str,
        *,
        retry_count: int,
        rate_limited: bool,
    ) -> FreeDocumentFetch:
        request = urllib.request.Request(
            source_url,
            headers={
                "Accept": ("application/pdf,application/octet-stream;q=0.9,*/*;q=0.1"),
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": self.user_agent,
            },
        )
        opener = urllib.request.build_opener(
            _ValidatedPurchasedDocumentRedirectHandler()
        )
        with opener.open(  # nosec B310
            request,
            timeout=self.timeout_seconds,
        ) as response:
            final_url = response.geturl()
            _validate_purchased_document_url(final_url)
            content = _read_bounded_document(
                response,
                source_url=final_url,
                content_length=response.headers.get("Content-Length"),
                max_response_bytes=self.max_response_bytes,
            )
            content_type = response.headers.get_content_type().lower()
        _validate_purchased_document_content(
            source_url=final_url,
            content=content,
            content_type=content_type,
        )
        return FreeDocumentFetch(
            content=content,
            retry_count=retry_count,
            rate_limited=rate_limited,
        )


class PurchasedDocumentRecoveryStatus(StrEnum):
    """Machine-readable recovery result for one purchased document."""

    RECOVERED = "recovered"
    RECOVERED_AUDIT_ONLY = "recovered_audit_only"
    PURCHASE_NOT_EXECUTED = "purchase_not_executed"
    UNAVAILABLE_AFTER_PURCHASE = "unavailable_after_purchase"


@dataclass(frozen=True, slots=True)
class PurchasedDocumentRecoveryRequest:
    """Metadata needed to reconcile one purchased document into provenance."""

    purchase_attempt: CaseDevPacerPurchaseAttempt
    source_case_id: str
    court: str
    docket_number: str
    document_role: DocumentRole
    docket_entry_number: int | None
    pre_purchase_evidence: Mapping[str, str]
    is_predecision_material: bool = True
    contains_target_outcome: bool = False
    file_extension: str = "pdf"


@dataclass(frozen=True, slots=True)
class PurchasedDocumentRecoveryRecord:
    """Stored purchased document plus pre/post purchase audit evidence."""

    candidate_id: str
    source_document_id: str
    status: PurchasedDocumentRecoveryStatus
    free_or_purchased: str
    purchase_cost_usd: str | None
    pre_purchase_evidence: Mapping[str, str]
    post_purchase_evidence: Mapping[str, str]
    provenance: SourceDocumentProvenance | None
    local_path: str | None = None
    sha256: str | None = None
    byte_count: int | None = None
    retry_count: int = 0
    rate_limited: bool = False

    def to_record(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "source_document_id": self.source_document_id,
            "status": self.status.value,
            "free_or_purchased": self.free_or_purchased,
            "purchase_cost_usd": self.purchase_cost_usd,
            "pre_purchase_evidence": dict(self.pre_purchase_evidence),
            "post_purchase_evidence": dict(self.post_purchase_evidence),
            "local_path": self.local_path,
            "sha256": self.sha256,
            "byte_count": self.byte_count,
            "retry_count": self.retry_count,
            "rate_limited": self.rate_limited,
            "provenance": (
                None if self.provenance is None else self.provenance.to_record()
            ),
        }


def purchased_document_recovery_requests_from_records(
    purchase_result: Mapping[str, Any],
    selection_records: Iterable[Mapping[str, Any]],
) -> tuple[PurchasedDocumentRecoveryRequest, ...]:
    """Validate guarded purchase evidence and join attempts to selected documents."""

    attempts = _validated_purchase_attempts(purchase_result)
    documents = _selected_documents_by_key(selection_records)
    requests: list[PurchasedDocumentRecoveryRequest] = []
    for attempt in attempts:
        key = (attempt.candidate_id, attempt.source_document_id)
        try:
            selection, document = documents[key]
        except KeyError as exc:
            raise PurchasedDocumentRecoveryError(
                "purchase attempt has no matching selected document: "
                f"{attempt.candidate_id}/{attempt.source_document_id}"
            ) from exc
        _require_public_recoverable_document(
            document,
            candidate_id=attempt.candidate_id,
            source_document_id=attempt.source_document_id,
        )
        role = DocumentRole(_required_str(document, "document_role"))
        contains_target_outcome = cast(
            bool,
            _optional_bool(
                document,
                "contains_target_outcome",
                default=role in {DocumentRole.ORDER, DocumentRole.DECISION},
            ),
        )
        is_predecision_material = cast(
            bool,
            _optional_bool(
                document,
                "is_predecision_material",
                default=not contains_target_outcome,
            ),
        )
        requests.append(
            PurchasedDocumentRecoveryRequest(
                purchase_attempt=attempt,
                source_case_id=_required_str(selection, "case_id"),
                court=_required_str(selection, "court"),
                docket_number=_required_str(selection, "docket_number"),
                document_role=role,
                docket_entry_number=_optional_int(document, "docket_entry_number"),
                pre_purchase_evidence=_pre_purchase_evidence(document),
                is_predecision_material=is_predecision_material,
                contains_target_outcome=contains_target_outcome,
                file_extension=_file_extension(document),
            )
        )
    return tuple(requests)


def purchased_document_download_manifest_records(
    records: Iterable[PurchasedDocumentRecoveryRecord],
) -> tuple[dict[str, Any], ...]:
    """Convert successful recoveries to the standard parser download manifest."""

    manifest: list[dict[str, Any]] = []
    for record in records:
        if record.status is not PurchasedDocumentRecoveryStatus.RECOVERED:
            continue
        provenance = record.provenance
        if (
            provenance is None
            or record.local_path is None
            or record.sha256 is None
            or record.byte_count is None
        ):
            raise PurchasedDocumentRecoveryError(
                "successful recovery is missing parser-manifest provenance"
            )
        manifest.append(
            {
                "candidate_id": record.candidate_id,
                "source_provider": provenance.source_provider,
                "source_document_id": record.source_document_id,
                "docket_entry_number": provenance.docket_entry_number,
                "document_role": provenance.document_role.value,
                "source_url": provenance.source_url_or_reference,
                "local_path": record.local_path,
                "sha256": record.sha256,
                "byte_count": record.byte_count,
                "free_or_purchased": record.free_or_purchased,
                "purchase_cost_usd": record.purchase_cost_usd,
                "retry_count": record.retry_count,
                "rate_limited": record.rate_limited,
                "reused_existing": False,
            }
        )
    return tuple(manifest)


def recover_purchased_documents(
    requests: tuple[PurchasedDocumentRecoveryRequest, ...],
    *,
    output_root: str | Path,
    source: FreeDocumentSource,
    retrieved_at: datetime,
) -> tuple[PurchasedDocumentRecoveryRecord, ...]:
    """Fetch successful purchase attempts and write provenance-safe records."""

    root = Path(output_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return tuple(
        _recover_one(
            request,
            output_root=root,
            source=source,
            retrieved_at=retrieved_at,
        )
        for request in requests
    )


def _recover_one(
    request: PurchasedDocumentRecoveryRequest,
    *,
    output_root: Path,
    source: FreeDocumentSource,
    retrieved_at: datetime,
) -> PurchasedDocumentRecoveryRecord:
    attempt = request.purchase_attempt
    purchase_cost = _purchase_cost(attempt)
    if attempt.status is not CaseDevPacerPurchaseStatus.PURCHASED:
        return _not_recovered_record(
            request,
            status=PurchasedDocumentRecoveryStatus.PURCHASE_NOT_EXECUTED,
            post_purchase_evidence={
                "availability": "not_checked",
                "purchase_status": attempt.status.value,
                "reason": attempt.reason or "",
            },
        )
    if attempt.download_url is None:
        return _not_recovered_record(
            request,
            status=PurchasedDocumentRecoveryStatus.UNAVAILABLE_AFTER_PURCHASE,
            post_purchase_evidence={
                "availability": "missing",
                "purchase_status": attempt.status.value,
                "reason": "missing_post_purchase_download_url",
            },
        )
    try:
        fetch = source.fetch(attempt.download_url)
    except RuntimeError as exc:
        return _not_recovered_record(
            request,
            status=PurchasedDocumentRecoveryStatus.UNAVAILABLE_AFTER_PURCHASE,
            post_purchase_evidence={
                "availability": "missing",
                "purchase_status": attempt.status.value,
                "reason": str(exc),
            },
        )

    output_path = _document_output_path(output_root, request)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(fetch.content)
    digest = hashlib.sha256(fetch.content).hexdigest()
    is_mounted = request.is_predecision_material and not request.contains_target_outcome
    status = (
        PurchasedDocumentRecoveryStatus.RECOVERED
        if is_mounted
        else PurchasedDocumentRecoveryStatus.RECOVERED_AUDIT_ONLY
    )
    local_path = output_path.relative_to(output_root).as_posix()
    provenance = SourceDocumentProvenance(
        source_provider=_PURCHASED_PROVIDER,
        source_case_id=request.source_case_id,
        source_document_id=attempt.source_document_id,
        court=request.court,
        docket_number=request.docket_number,
        document_role=request.document_role,
        retrieved_at=retrieved_at,
        source_url_or_reference=attempt.download_url,
        sha256=digest,
        is_predecision_material=request.is_predecision_material,
        is_mounted_for_model=is_mounted,
        availability_status=AvailabilityStatus.AVAILABLE,
        redaction_or_seal_status=RedactionOrSealStatus.PUBLIC,
        docket_entry_number=request.docket_entry_number,
        contains_target_outcome=request.contains_target_outcome,
        packet_section="filings" if is_mounted else None,
        notes=(
            "Purchased through case.dev PACER recovery for "
            f"{purchase_cost or 'unknown'}"
        ),
    )
    return PurchasedDocumentRecoveryRecord(
        candidate_id=attempt.candidate_id,
        source_document_id=attempt.source_document_id,
        status=status,
        free_or_purchased="purchased",
        purchase_cost_usd=purchase_cost,
        pre_purchase_evidence=dict(request.pre_purchase_evidence),
        post_purchase_evidence=_post_purchase_evidence(
            attempt,
            digest=digest,
            fetch=fetch,
        ),
        provenance=provenance,
        local_path=local_path,
        sha256=digest,
        byte_count=len(fetch.content),
        retry_count=fetch.retry_count,
        rate_limited=fetch.rate_limited,
    )


def _not_recovered_record(
    request: PurchasedDocumentRecoveryRequest,
    *,
    status: PurchasedDocumentRecoveryStatus,
    post_purchase_evidence: Mapping[str, str],
) -> PurchasedDocumentRecoveryRecord:
    attempt = request.purchase_attempt
    return PurchasedDocumentRecoveryRecord(
        candidate_id=attempt.candidate_id,
        source_document_id=attempt.source_document_id,
        status=status,
        free_or_purchased="purchased",
        purchase_cost_usd=_purchase_cost(attempt),
        pre_purchase_evidence=dict(request.pre_purchase_evidence),
        post_purchase_evidence=dict(post_purchase_evidence),
        provenance=None,
    )


def _post_purchase_evidence(
    attempt: CaseDevPacerPurchaseAttempt,
    *,
    digest: str,
    fetch: FreeDocumentFetch,
) -> dict[str, str]:
    return {
        "availability": "available",
        "purchase_status": attempt.status.value,
        "download_url": attempt.download_url or "",
        "sha256": digest,
        "byte_count": str(len(fetch.content)),
        "retry_count": str(fetch.retry_count),
        "rate_limited": "true" if fetch.rate_limited else "false",
    }


def _document_output_path(
    output_root: Path,
    request: PurchasedDocumentRecoveryRequest,
) -> Path:
    attempt = request.purchase_attempt
    candidate_id = safe_path_component(attempt.candidate_id, field_name="candidate_id")
    document_id = safe_path_component(
        attempt.source_document_id,
        field_name="source_document_id",
    )
    extension = safe_path_component(
        request.file_extension.removeprefix("."),
        field_name="file_extension",
    )
    entry_prefix = (
        "entry-unknown"
        if request.docket_entry_number is None
        else f"entry-{request.docket_entry_number}"
    )
    filename = f"{entry_prefix}_{document_id}.{extension}"
    output_path = (
        output_root / candidate_id / _PURCHASED_PROVIDER_PATH / filename
    ).resolve()
    output_path.relative_to(output_root)
    return output_path


def _validate_purchased_document_url(source_url: str) -> None:
    parsed = urllib.parse.urlparse(source_url)
    hostname = parsed.hostname.lower() if parsed.hostname is not None else None
    if parsed.scheme != "https" or hostname not in _ALLOWED_PURCHASED_DOCUMENT_HOSTS:
        allowed = ", ".join(sorted(_ALLOWED_PURCHASED_DOCUMENT_HOSTS))
        raise PurchasedDocumentRecoveryError(
            f"purchased-document download URL must use HTTPS on one of: {allowed}"
        )
    if parsed.username is not None or parsed.password is not None:
        raise PurchasedDocumentRecoveryError(
            "purchased-document download URL must not include credentials"
        )
    try:
        port = parsed.port
    except ValueError as exc:
        raise PurchasedDocumentRecoveryError(
            "purchased-document download URL port must be valid"
        ) from exc
    if port not in {None, 443}:
        raise PurchasedDocumentRecoveryError(
            "purchased-document download URL must not use a non-default port"
        )


def _validate_purchased_document_content(
    *,
    source_url: str,
    content: bytes,
    content_type: str,
) -> None:
    if not content:
        raise PurchasedDocumentDownloadError(
            f"purchased case.dev document was empty: {source_url}"
        )
    prefix = content[:512].lstrip().lower()
    if prefix.startswith((b"<!doctype html", b"<html")):
        raise PurchasedDocumentDownloadError(
            "purchased case.dev document URL returned HTML instead of a document: "
            f"{source_url}"
        )
    if content.lstrip().startswith(b"%PDF") or "pdf" in content_type:
        return
    parsed = urllib.parse.urlparse(source_url)
    if parsed.path.lower().endswith(".pdf") and content_type in {
        "",
        "application/octet-stream",
        "binary/octet-stream",
    }:
        return
    raise PurchasedDocumentDownloadError(
        "purchased case.dev document response did not look like a PDF "
        f"(content-type={content_type or 'unknown'}): {source_url}"
    )


def _read_bounded_document(
    stream: IO[bytes],
    *,
    source_url: str,
    content_length: str | None,
    max_response_bytes: int,
) -> bytes:
    if content_length is not None:
        try:
            declared_bytes = int(content_length)
        except ValueError as exc:
            raise PurchasedDocumentDownloadError(
                f"purchased case.dev document returned invalid Content-Length: "
                f"{source_url}"
            ) from exc
        if declared_bytes < 0:
            raise PurchasedDocumentDownloadError(
                f"purchased case.dev document returned invalid Content-Length: "
                f"{source_url}"
            )
        if declared_bytes > max_response_bytes:
            raise PurchasedDocumentDownloadError(
                "purchased case.dev document Content-Length "
                f"{declared_bytes} exceeds the {max_response_bytes}-byte maximum: "
                f"{source_url}"
            )

    content = bytearray()
    while True:
        read_size = min(
            _DOWNLOAD_CHUNK_BYTES,
            max_response_bytes + 1 - len(content),
        )
        chunk = stream.read(read_size)
        if not chunk:
            return bytes(content)
        content.extend(chunk)
        if len(content) > max_response_bytes:
            raise PurchasedDocumentDownloadError(
                "purchased case.dev document response exceeds the "
                f"{max_response_bytes}-byte maximum: {source_url}"
            )


def _purchase_cost(attempt: CaseDevPacerPurchaseAttempt) -> str | None:
    if attempt.pacer_fees is None:
        return None
    return attempt.pacer_fees.get("total_usd")


def _validated_purchase_attempts(
    purchase_result: Mapping[str, Any],
) -> tuple[CaseDevPacerPurchaseAttempt, ...]:
    if purchase_result.get("live") is not True:
        raise PurchasedDocumentRecoveryError("recovery requires a live purchase result")
    if purchase_result.get("acknowledge_pacer_fees") is not True:
        raise PurchasedDocumentRecoveryError(
            "recovery requires explicit PACER fee acknowledgment"
        )
    if purchase_result.get("capability") != (
        CaseDevPacerCapability.DOCUMENT_LEVEL_PURCHASE.value
    ):
        raise PurchasedDocumentRecoveryError(
            "recovery requires proven document-level capability"
        )
    if purchase_result.get("dry_run") is not False:
        raise PurchasedDocumentRecoveryError(
            "recovery requires an executed purchase result, not a dry run"
        )
    configured_cap = DEFAULT_MAX_PROJECTED_BUDGET_USD
    recorded_cap = _money(
        purchase_result.get("max_projected_budget_usd"),
        "max_projected_budget_usd",
    )
    if recorded_cap > configured_cap:
        raise PurchasedDocumentRecoveryError(
            f"recorded purchase cap ${recorded_cap:.2f} exceeds configured cap "
            f"${configured_cap:.2f}"
        )
    projected_cost = _money(
        purchase_result.get("projected_cost_usd"),
        "projected_cost_usd",
    )
    if projected_cost > recorded_cap:
        raise PurchasedDocumentRecoveryError(
            f"projected cost ${projected_cost:.2f} exceeds recorded cap "
            f"${recorded_cap:.2f}"
        )

    attempts = tuple(
        _purchase_attempt(record)
        for record in _record_sequence(purchase_result.get("attempts"), "attempts")
    )
    intended_purchase_count = _required_count(
        purchase_result,
        "intended_purchase_count",
    )
    if intended_purchase_count != len(attempts):
        raise PurchasedDocumentRecoveryError(
            f"intended_purchase_count {intended_purchase_count} does not match "
            f"{len(attempts)} attempts"
        )
    executed_purchase_count = _required_count(
        purchase_result,
        "executed_purchase_count",
    )
    purchased_attempt_count = sum(
        attempt.status is CaseDevPacerPurchaseStatus.PURCHASED for attempt in attempts
    )
    if executed_purchase_count != purchased_attempt_count:
        raise PurchasedDocumentRecoveryError(
            f"executed_purchase_count {executed_purchase_count} does not match "
            f"{purchased_attempt_count} purchased attempts"
        )
    attempts_per_candidate: dict[str, int] = {}
    for attempt in attempts:
        attempts_per_candidate[attempt.candidate_id] = (
            attempts_per_candidate.get(attempt.candidate_id, 0) + 1
        )
    over_cap = {
        candidate_id: count
        for candidate_id, count in attempts_per_candidate.items()
        if count > DEFAULT_MAX_MISSING_CORE_DOCUMENTS_PER_CASE
    }
    if over_cap:
        candidate_id, count = sorted(over_cap.items())[0]
        raise PurchasedDocumentRecoveryError(
            f"{candidate_id} has {count} purchase attempts; per-case cap is "
            f"{DEFAULT_MAX_MISSING_CORE_DOCUMENTS_PER_CASE}"
        )
    purchased = tuple(
        attempt
        for attempt in attempts
        if attempt.status is CaseDevPacerPurchaseStatus.PURCHASED
    )
    actual_cost = sum(
        (
            _money(
                None
                if attempt.pacer_fees is None
                else attempt.pacer_fees.get("total_usd"),
                "pacer_fees.total_usd",
            )
            for attempt in purchased
        ),
        Decimal("0"),
    )
    if actual_cost > recorded_cap:
        raise PurchasedDocumentRecoveryError(
            f"actual purchase cost ${actual_cost:.2f} exceeds recorded cap "
            f"${recorded_cap:.2f}"
        )
    for attempt in purchased:
        if attempt.fee_acknowledged is not True:
            raise PurchasedDocumentRecoveryError(
                "successful purchase attempt lacks fee acknowledgment: "
                f"{attempt.candidate_id}/{attempt.source_document_id}"
            )
    return attempts


def _purchase_attempt(record: Mapping[str, Any]) -> CaseDevPacerPurchaseAttempt:
    fees_value = record.get("pacer_fees")
    fees = None
    if fees_value is not None:
        if not isinstance(fees_value, Mapping):
            raise PurchasedDocumentRecoveryError("pacer_fees must be an object")
        fees_record = cast(Mapping[str, Any], fees_value)
        fees = {
            str(key): str(value)
            for key, value in fees_record.items()
            if value is not None
        }
    return CaseDevPacerPurchaseAttempt(
        candidate_id=_required_str(record, "candidate_id"),
        source_document_id=_required_str(record, "source_document_id"),
        status=CaseDevPacerPurchaseStatus(_required_str(record, "status")),
        reason=_optional_str(record, "reason"),
        fee_acknowledged=_optional_bool(record, "fee_acknowledged", default=None),
        pacer_fees=fees,
        download_url=_optional_str(record, "download_url"),
    )


def _selected_documents_by_key(
    selection_records: Iterable[Mapping[str, Any]],
) -> dict[tuple[str, str], tuple[Mapping[str, Any], Mapping[str, Any]]]:
    indexed: dict[tuple[str, str], tuple[Mapping[str, Any], Mapping[str, Any]]] = {}
    for selection in selection_records:
        candidate_id = _required_str(selection, "candidate_id")
        for document in _record_sequence(selection.get("documents"), "documents"):
            key = (candidate_id, _required_str(document, "source_document_id"))
            if key in indexed:
                raise PurchasedDocumentRecoveryError(
                    f"duplicate selected document: {key[0]}/{key[1]}"
                )
            indexed[key] = (selection, document)
    return indexed


def _pre_purchase_evidence(document: Mapping[str, Any]) -> dict[str, str]:
    evidence = {
        "availability": _optional_str(document, "availability_status") or "unknown",
        "requires_paid_recovery": (
            "true"
            if _optional_bool(document, "requires_paid_recovery", default=True)
            else "false"
        ),
    }
    source_url = _optional_str(document, "source_url") or _optional_str(
        document,
        "source_url_or_reference",
    )
    if source_url is not None:
        evidence["source_url_or_reference"] = source_url
    return evidence


def _require_public_recoverable_document(
    document: Mapping[str, Any],
    *,
    candidate_id: str,
    source_document_id: str,
) -> None:
    records = [document]
    provenance = document.get("provenance")
    if isinstance(provenance, Mapping):
        records.append(cast(Mapping[str, Any], provenance))
    restricted = False
    for record in records:
        if record.get("is_sealed") is True or record.get("is_private") is True:
            restricted = True
        availability = _optional_str(record, "availability_status")
        if availability in {"restricted", "private", "sealed"}:
            restricted = True
        for field_name in ("redaction_or_seal_status", "seal_status"):
            status = _optional_str(record, field_name)
            if status in {"restricted", "private", "sealed"}:
                restricted = True
    if restricted:
        raise PurchasedDocumentRecoveryError(
            "sealed/private/restricted document cannot be recovered into "
            "acquisition artifacts: "
            f"{candidate_id}/{source_document_id}"
        )


def _file_extension(document: Mapping[str, Any]) -> str:
    explicit = _optional_str(document, "file_extension")
    if explicit is not None:
        return explicit.removeprefix(".")
    source_url = _optional_str(document, "source_url") or ""
    suffix = Path(source_url.split("?", maxsplit=1)[0]).suffix.removeprefix(".")
    return suffix or "pdf"


def _record_sequence(value: object, field_name: str) -> tuple[Mapping[str, Any], ...]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise PurchasedDocumentRecoveryError(f"{field_name} must be a list")
    records: list[Mapping[str, Any]] = []
    for item in cast(Sequence[object], value):
        if not isinstance(item, Mapping):
            raise PurchasedDocumentRecoveryError(
                f"{field_name} entries must be objects"
            )
        records.append(cast(Mapping[str, Any], item))
    return tuple(records)


def _required_str(record: Mapping[str, Any], field_name: str) -> str:
    value = _optional_str(record, field_name)
    if value is None:
        raise PurchasedDocumentRecoveryError(f"{field_name} is required")
    return value


def _optional_str(record: Mapping[str, Any], field_name: str) -> str | None:
    value = record.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise PurchasedDocumentRecoveryError(f"{field_name} must be a string")
    return value.strip() or None


def _optional_int(record: Mapping[str, Any], field_name: str) -> int | None:
    value = record.get(field_name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise PurchasedDocumentRecoveryError(f"{field_name} must be a positive integer")
    return value


def _required_count(record: Mapping[str, Any], field_name: str) -> int:
    value = record.get(field_name)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise PurchasedDocumentRecoveryError(
            f"{field_name} must be a non-negative integer"
        )
    return value


def _optional_bool(
    record: Mapping[str, Any],
    field_name: str,
    *,
    default: bool | None,
) -> bool | None:
    value = record.get(field_name)
    if value is None:
        return default
    if not isinstance(value, bool):
        raise PurchasedDocumentRecoveryError(f"{field_name} must be a boolean")
    return value


def _money(value: object, field_name: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise PurchasedDocumentRecoveryError(
            f"{field_name} must be a decimal dollar amount"
        )
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise PurchasedDocumentRecoveryError(
            f"{field_name} must be a decimal dollar amount"
        ) from exc
    if not amount.is_finite() or amount < 0:
        raise PurchasedDocumentRecoveryError(
            f"{field_name} must be a non-negative finite amount"
        )
    return amount
