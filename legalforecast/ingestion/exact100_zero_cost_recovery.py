"""Bounded public recovery for the one exact-100 missing memorandum.

This producer is deliberately narrower than the general CourtListener clients.
It mints a terminal-exclusion input only after the one closed plan has selected
the authenticated 72449171 / 480673755 memorandum.  A public PDF is useful
recovery evidence, but is never terminal-exclusion authority.
"""

from __future__ import annotations

import hashlib
import json
import re
import urllib.parse
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast

from legalforecast.contracts import (
    EXACT100_ZERO_COST_RECOVERY_PLAN_V1,
    EXACT100_ZERO_COST_RECOVERY_PUBLIC_DOCUMENT_V1,
    EXACT100_ZERO_COST_RECOVERY_RECEIPT_V2,
    EXACT100_ZERO_COST_RECOVERY_REQUEST_V2,
    EXACT100_ZERO_COST_RECOVERY_REST_OBSERVATION_TRANSCRIPT_V1,
    EXACT100_ZERO_COST_RECOVERY_REST_OBSERVATION_V1,
    EXACT100_ZERO_COST_RECOVERY_RUN_V2,
)
from legalforecast.ingestion.canonical_json import canonical_json_bytes
from legalforecast.ingestion.courtlistener_client import (
    DEFAULT_COURTLISTENER_BASE_URL,
    CourtListenerAuthError,
    CourtListenerClient,
    CourtListenerClientError,
    CourtListenerDocketEntry,
    CourtListenerRateLimitError,
    CourtListenerRecapDocument,
    CourtListenerResponseError,
    CourtListenerServerError,
    CourtListenerUnavailableError,
)
from legalforecast.ingestion.exact100_terminal_recovery_authority_v3.authority import (
    VerifiedExact100TerminalRecoveryAuthorityV3,
    mint_exact100_terminal_recovery_authority_v3,
)
from legalforecast.ingestion.free_document_downloader import (
    FreeDocumentDownloadError,
    FreeDocumentDownloadRecord,
    FreeDocumentDownloadRequest,
    FreeDocumentSource,
    download_free_docket_documents,
)
from legalforecast.ingestion.post_selection_terminal_exclusion import (
    VerifiedTerminalExclusionEvidence,
    _mint_terminal_recovery_evidence_from_producer,  # pyright: ignore[reportPrivateUsage]
)
from legalforecast.ingestion.provenance import DocumentRole

JsonRecord = dict[str, Any]

RECOVERY_PLAN_SCHEMA_VERSION = str(EXACT100_ZERO_COST_RECOVERY_PLAN_V1)
RECOVERY_REQUEST_SCHEMA_VERSION = str(EXACT100_ZERO_COST_RECOVERY_REQUEST_V2)
RECOVERY_RECEIPT_SCHEMA_VERSION = str(EXACT100_ZERO_COST_RECOVERY_RECEIPT_V2)
RECOVERY_RUN_CARD_SCHEMA_VERSION = str(EXACT100_ZERO_COST_RECOVERY_RUN_V2)
REST_OBSERVATION_SCHEMA_VERSION = str(EXACT100_ZERO_COST_RECOVERY_REST_OBSERVATION_V1)
REST_OBSERVATION_TRANSCRIPT_SCHEMA_VERSION = str(
    EXACT100_ZERO_COST_RECOVERY_REST_OBSERVATION_TRANSCRIPT_V1
)
PUBLIC_DOCUMENT_SCHEMA_VERSION = str(EXACT100_ZERO_COST_RECOVERY_PUBLIC_DOCUMENT_V1)

_KNOWN_CANDIDATE_ID = "72449171"
_KNOWN_DOCKET_ID = "72449171"
_KNOWN_RECAP_DOCUMENT_ID = "480673755"
_KNOWN_DOCKET_ENTRY_ID = "465468661"
_TARGET_ROLES = frozenset(
    {DocumentRole.MTD_NOTICE.value, DocumentRole.MTD_MEMORANDUM.value}
)
_PUBLIC_DOCUMENT_HOSTS = frozenset(
    {"www.courtlistener.com", "storage.courtlistener.com"}
)
_RECAP_PATH = re.compile(r"recap/[A-Za-z0-9._/-]+\.pdf")


class Exact100ZeroCostRecoveryError(ValueError):
    """Raised when this bounded recovery cannot produce safe evidence."""


@dataclass(frozen=True, slots=True)
class Exact100ZeroCostRecoveryRequest:
    """Request derived from one immutable plan and authenticated selection bytes."""

    record: JsonRecord
    record_bytes: bytes
    selection_bytes: bytes


@dataclass(frozen=True, slots=True)
class Exact100ZeroCostRecoveryResult:
    """Either terminal 404 evidence or non-terminal public recovery evidence."""

    request: Exact100ZeroCostRecoveryRequest
    receipt: JsonRecord | None = None
    receipt_bytes: bytes | None = None
    run_card: JsonRecord | None = None
    run_card_bytes: bytes | None = None
    rest_observation: JsonRecord | None = None
    rest_observation_bytes: bytes | None = None
    rest_observation_transcript_bytes: bytes | None = None
    rest_observation_response_bytes: bytes | None = None
    public_document_manifest: JsonRecord | None = None
    public_document_manifest_bytes: bytes | None = None
    public_download: FreeDocumentDownloadRecord | None = None
    terminal_evidence: VerifiedTerminalExclusionEvidence | None = None
    terminal_authority_v3: VerifiedExact100TerminalRecoveryAuthorityV3 | None = None

    @property
    def terminal_exclusion_authority(self) -> bool:
        """Only the terminal verifier may mint such authority after replay."""

        return False


def issue_exact100_zero_cost_recovery_request(
    *, selection_bytes: bytes, plan_bytes: bytes
) -> Exact100ZeroCostRecoveryRequest:
    """Derive the sole permissible GET tuple without execution-time identifiers."""

    plan = _canonical_object(plan_bytes, "zero-cost recovery plan")
    if set(plan) != {"schema_version", "selection_sha256", "records"}:
        raise Exact100ZeroCostRecoveryError(
            "zero-cost recovery plan has unexpected fields"
        )
    if plan.get("schema_version") != RECOVERY_PLAN_SCHEMA_VERSION:
        raise Exact100ZeroCostRecoveryError(
            "zero-cost recovery plan schema is unsupported"
        )
    if plan.get("selection_sha256") != _sha(selection_bytes):
        raise Exact100ZeroCostRecoveryError(
            "zero-cost recovery plan binds another selection"
        )
    raw_records = plan.get("records")
    records = cast(list[object], raw_records) if isinstance(raw_records, list) else ()
    if len(records) != 1 or not isinstance(records[0], Mapping):
        raise Exact100ZeroCostRecoveryError(
            "zero-cost recovery plan must contain one record"
        )
    planned = cast(Mapping[str, object], records[0])
    if set(planned) != {"candidate_id", "source_document_id"}:
        raise Exact100ZeroCostRecoveryError(
            "zero-cost recovery plan record is not closed"
        )
    candidate_id = _positive_id(planned.get("candidate_id"), "planned candidate_id")
    source_document_id = _positive_id(
        planned.get("source_document_id"), "planned source_document_id"
    )
    if (candidate_id, source_document_id) != (
        _KNOWN_CANDIDATE_ID,
        _KNOWN_RECAP_DOCUMENT_ID,
    ):
        raise Exact100ZeroCostRecoveryError(
            "zero-cost recovery plan is outside its fixed allowlist"
        )
    selected = _selection_index(selection_bytes).get(candidate_id)
    if selected is None:
        raise Exact100ZeroCostRecoveryError(
            "planned candidate is absent from selection"
        )
    document = _selected_document(selected, source_document_id)
    docket_id = _positive_id(
        _mapping(selected.get("identity_resolution"), "selection identity").get(
            "courtlistener_docket_id"
        ),
        "selection courtlistener_docket_id",
    )
    docket_entry_id = _positive_id(
        document.get("courtlistener_docket_entry_id"),
        "selection courtlistener_docket_entry_id",
    )
    if docket_id != _KNOWN_DOCKET_ID or docket_entry_id != _KNOWN_DOCKET_ENTRY_ID:
        raise Exact100ZeroCostRecoveryError(
            "selection does not bind the stipulated CourtListener docket and entry"
        )
    document_role = _required_text(document, "document_role")
    if document_role not in _TARGET_ROLES:
        raise Exact100ZeroCostRecoveryError(
            "planned document is not a target-motion document"
        )
    request: JsonRecord = {
        "schema_version": RECOVERY_REQUEST_SCHEMA_VERSION,
        "candidate_id": candidate_id,
        "source_document_id": source_document_id,
        "document_role": document_role,
        "courtlistener_docket_id": docket_id,
        "courtlistener_docket_entry_id": docket_entry_id,
        "recovery_mode": "courtlistener_rest_noncharging_only",
        "paid_permitted": False,
        "pacer_permitted": False,
        "recap_fetch_permitted": False,
        "selection_sha256": _sha(selection_bytes),
    }
    return Exact100ZeroCostRecoveryRequest(
        record=request,
        record_bytes=_bytes(request),
        selection_bytes=selection_bytes,
    )


def execute_exact100_zero_cost_recovery(
    *,
    selection_bytes: bytes,
    plan_bytes: bytes,
    courtlistener: CourtListenerClient,
    public_document_source: FreeDocumentSource | None = None,
    public_output_root: Path | None = None,
) -> Exact100ZeroCostRecoveryResult:
    """Perform the sole permitted metadata GET and optional safe public download.

    The caller cannot supply a candidate, document, docket, or entry identifier.
    No search, listing, provider broker, PACER, or fee-bearing surface is exposed.
    """

    # The transcript commits the full REST-v4 request path.  Do not mint one
    # from a client pointed at another same-host endpoint.
    if courtlistener.config.base_url != DEFAULT_COURTLISTENER_BASE_URL:
        raise Exact100ZeroCostRecoveryError(
            "exact100 recovery requires the canonical CourtListener REST v4 base"
        )
    request = issue_exact100_zero_cost_recovery_request(
        selection_bytes=selection_bytes, plan_bytes=plan_bytes
    )
    try:
        recap_document = courtlistener.get_recap_document(
            str(request.record["source_document_id"])
        )
    except CourtListenerUnavailableError as exc:
        return _unavailable_result(request, observed_error=exc)
    except (
        CourtListenerAuthError,
        CourtListenerRateLimitError,
        CourtListenerServerError,
        CourtListenerResponseError,
        CourtListenerClientError,
    ) as exc:
        raise Exact100ZeroCostRecoveryError(
            "CourtListener metadata observation is not terminal"
        ) from exc

    _verify_public_document_identity(recap_document, request)
    try:
        docket_entry = courtlistener.get_docket_entry(
            str(request.record["courtlistener_docket_entry_id"])
        )
    except CourtListenerResponseError as exc:
        raise Exact100ZeroCostRecoveryError(
            "CourtListener docket-entry identity drift"
        ) from exc
    except CourtListenerClientError as exc:
        raise Exact100ZeroCostRecoveryError(
            "CourtListener docket-entry verification is not terminal"
        ) from exc
    _verify_public_docket_entry_identity(docket_entry, request)
    if recap_document.is_available is not True:
        raise Exact100ZeroCostRecoveryError(
            "CourtListener metadata does not unambiguously offer a public document"
        )
    if recap_document.is_sealed is not False or recap_document.is_private is not False:
        raise Exact100ZeroCostRecoveryError(
            "CourtListener metadata reports restricted document"
        )
    if public_document_source is None or public_output_root is None:
        raise Exact100ZeroCostRecoveryError(
            "public recovery requires an injected source and output root"
        )
    source_url = _public_download_url(
        recap_document.raw,
        document_id=str(request.record["source_document_id"]),
    )
    try:
        document_role = DocumentRole(str(request.record["document_role"]))
        records = download_free_docket_documents(
            (
                FreeDocumentDownloadRequest(
                    candidate_id=str(request.record["candidate_id"]),
                    source_provider="courtlistener_recap_public",
                    source_document_id=str(request.record["source_document_id"]),
                    docket_entry_number=None,
                    document_role=document_role,
                    source_url=source_url,
                ),
            ),
            output_root=public_output_root,
            source=public_document_source,
            allow_existing=False,
        )
    except (FreeDocumentDownloadError, ValueError) as exc:
        raise Exact100ZeroCostRecoveryError(
            "public PDF recovery did not complete safely"
        ) from exc
    if len(records) != 1:
        raise Exact100ZeroCostRecoveryError("public recovery did not emit one document")
    download = records[0]
    manifest: JsonRecord = {
        "schema_version": PUBLIC_DOCUMENT_SCHEMA_VERSION,
        "recovery_request_sha256": _sha(request.record_bytes),
        "candidate_id": request.record["candidate_id"],
        "source_document_id": request.record["source_document_id"],
        "courtlistener_docket_id": request.record["courtlistener_docket_id"],
        "courtlistener_docket_entry_id": request.record[
            "courtlistener_docket_entry_id"
        ],
        "document": download.to_record(),
        "terminal_exclusion_authority": False,
    }
    return Exact100ZeroCostRecoveryResult(
        request=request,
        public_document_manifest=manifest,
        public_document_manifest_bytes=_bytes(manifest),
        public_download=download,
    )


def _execute_terminal_recovery_with_verifier(  # pyright: ignore[reportUnusedFunction]
    *,
    selection_bytes: bytes,
    plan_bytes: bytes,
    courtlistener: CourtListenerClient,
) -> Exact100ZeroCostRecoveryResult:
    """Issue terminal authority through the private verifier seam only.

    Production successor replay constructs its own canonical CourtListener
    client before entering this seam.  Tests may inject an offline transport;
    the ordinary public recovery function remains non-authoritative even when
    its caller supplies a self-consistent fixture response.
    """

    result = execute_exact100_zero_cost_recovery(
        selection_bytes=selection_bytes,
        plan_bytes=plan_bytes,
        courtlistener=courtlistener,
    )
    if result.receipt is None:
        return result
    required = (
        result.receipt_bytes,
        result.run_card,
        result.run_card_bytes,
        result.rest_observation,
        result.rest_observation_bytes,
        result.rest_observation_transcript_bytes,
        result.rest_observation_response_bytes,
    )
    if any(payload is None for payload in required):
        raise Exact100ZeroCostRecoveryError(
            "terminal recovery producer lacks its closed evidence bundle"
        )
    terminal_evidence = _mint_terminal_recovery_evidence_from_producer(
        selection_bytes=result.request.selection_bytes,
        request=result.request.record,
        request_bytes=result.request.record_bytes,
        receipt=result.receipt,
        receipt_bytes=cast(bytes, result.receipt_bytes),
        run_card=cast(JsonRecord, result.run_card),
        run_card_bytes=cast(bytes, result.run_card_bytes),
        rest_observation=cast(JsonRecord, result.rest_observation),
        rest_observation_bytes=cast(bytes, result.rest_observation_bytes),
        rest_observation_transcript_bytes=cast(
            bytes, result.rest_observation_transcript_bytes
        ),
        rest_observation_response_bytes=cast(
            bytes, result.rest_observation_response_bytes
        ),
    )
    terminal_authority_v3 = mint_exact100_terminal_recovery_authority_v3(
        selection_bytes=result.request.selection_bytes,
        request=result.request.record,
        request_bytes=result.request.record_bytes,
        observation_status_code=404,
    )
    return replace(
        result,
        terminal_evidence=terminal_evidence,
        terminal_authority_v3=terminal_authority_v3,
    )


def _unavailable_result(
    request: Exact100ZeroCostRecoveryRequest,
    *,
    observed_error: CourtListenerUnavailableError,
) -> Exact100ZeroCostRecoveryResult:
    """Emit the exact v2/v1 terminal surface for one authoritative 404."""

    expected_path = f"/recap-documents/{request.record['source_document_id']}/"
    if (
        observed_error.method != "GET"
        or observed_error.path != expected_path
        or observed_error.status_code != 404
        or observed_error.response_bytes is None
    ):
        raise Exact100ZeroCostRecoveryError(
            "CourtListener 404 lacks an exact replayable response observation"
        )
    response_bytes = observed_error.response_bytes
    transcript: JsonRecord = {
        "schema_version": REST_OBSERVATION_TRANSCRIPT_SCHEMA_VERSION,
        "candidate_id": request.record["candidate_id"],
        "source_document_id": request.record["source_document_id"],
        "document_role": request.record["document_role"],
        "courtlistener_docket_id": request.record["courtlistener_docket_id"],
        "courtlistener_docket_entry_id": request.record[
            "courtlistener_docket_entry_id"
        ],
        "request_method": "GET",
        "request_path": f"/api/rest/v4{expected_path}",
        "status_code": 404,
        "response_sha256": _sha(response_bytes),
        "terminal_status": "unavailable",
        "terminal": True,
    }
    transcript_bytes = _bytes(transcript)
    observation: JsonRecord = {
        "schema_version": REST_OBSERVATION_SCHEMA_VERSION,
        "candidate_id": request.record["candidate_id"],
        "source_document_id": request.record["source_document_id"],
        "document_role": request.record["document_role"],
        "courtlistener_docket_id": request.record["courtlistener_docket_id"],
        "courtlistener_docket_entry_id": request.record[
            "courtlistener_docket_entry_id"
        ],
        "request_sha256": _sha(request.record_bytes),
        "terminal_status": "unavailable",
        "completed": True,
        "retryable": False,
        "recovered": False,
        "transcript_sha256": _sha(transcript_bytes),
        "transcript_record_count": 1,
    }
    observation_bytes = _bytes(observation)
    receipt: JsonRecord = {
        "schema_version": RECOVERY_RECEIPT_SCHEMA_VERSION,
        "candidate_id": request.record["candidate_id"],
        "source_document_id": request.record["source_document_id"],
        "document_role": request.record["document_role"],
        "recovery_mode": request.record["recovery_mode"],
        "terminal_status": "unavailable",
        "completed": True,
        "retryable": False,
        "recovered": False,
        "paid_activity_executed": False,
        "pacer_activity_executed": False,
        "recap_fetch_activity_executed": False,
        "fee_acknowledged": False,
        "request_sha256": _sha(request.record_bytes),
        "rest_observation_sha256": _sha(observation_bytes),
        "rest_observation_transcript_sha256": _sha(transcript_bytes),
    }
    receipt_bytes = _bytes(receipt)
    run_card: JsonRecord = {
        "schema_version": RECOVERY_RUN_CARD_SCHEMA_VERSION,
        "stage": "recover-exact100-target-document-zero-cost",
        "status": "completed",
        "dry_run": False,
        "execute": True,
        "record_count": 1,
        "provider_activity_requested": True,
        "provider_activity_executed": True,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "pacer_activity_executed": False,
        "recap_fetch_activity_executed": False,
        "fee_acknowledged": False,
        "input_commitments": {
            "request": _sha(request.record_bytes),
            "selection": _sha(request.selection_bytes),
        },
        "output_commitments": {
            "receipt": _sha(receipt_bytes),
            "rest_observation": _sha(observation_bytes),
            "rest_observation_transcript": _sha(transcript_bytes),
            "rest_observation_response": _sha(response_bytes),
        },
    }
    return Exact100ZeroCostRecoveryResult(
        request=request,
        receipt=receipt,
        receipt_bytes=receipt_bytes,
        run_card=run_card,
        run_card_bytes=_bytes(run_card),
        rest_observation=observation,
        rest_observation_bytes=observation_bytes,
        rest_observation_transcript_bytes=transcript_bytes,
        rest_observation_response_bytes=response_bytes,
    )


def _verify_public_document_identity(
    recap_document: CourtListenerRecapDocument,
    request: Exact100ZeroCostRecoveryRequest,
) -> None:
    if (
        recap_document.document_id != request.record["source_document_id"]
        or recap_document.docket_entry_id
        != request.record["courtlistener_docket_entry_id"]
    ):
        raise Exact100ZeroCostRecoveryError(
            "CourtListener recap-document identity drift"
        )


def _verify_public_docket_entry_identity(
    docket_entry: CourtListenerDocketEntry,
    request: Exact100ZeroCostRecoveryRequest,
) -> None:
    if (
        docket_entry.docket_entry_id != request.record["courtlistener_docket_entry_id"]
        or docket_entry.docket_id != request.record["courtlistener_docket_id"]
        or request.record["source_document_id"] not in docket_entry.recap_document_ids
    ):
        raise Exact100ZeroCostRecoveryError("CourtListener docket-entry identity drift")


def _public_download_url(raw: Mapping[str, Any], *, document_id: str) -> str:
    value = raw.get("filepath_local", raw.get("download_url"))
    if not isinstance(value, str) or not value or value.strip() != value:
        raise Exact100ZeroCostRecoveryError("public document lacks a safe download URL")
    if value.startswith("recap/"):
        if (
            _RECAP_PATH.fullmatch(value) is None
            or ".." in value.split("/")
            or value.rsplit("/", maxsplit=1)[-1] != f"{document_id}.pdf"
        ):
            raise Exact100ZeroCostRecoveryError("public document RECAP path is unsafe")
        return f"https://storage.courtlistener.com/{value}"
    url = urllib.parse.urljoin("https://www.courtlistener.com", value)
    parsed = urllib.parse.urlparse(url)
    try:
        port = parsed.port
    except ValueError as exc:
        raise Exact100ZeroCostRecoveryError(
            "public document URL has invalid port"
        ) from exc
    if (
        parsed.scheme != "https"
        or parsed.hostname not in _PUBLIC_DOCUMENT_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
        or not parsed.path.lower().endswith(".pdf")
        or parsed.path.rsplit("/", maxsplit=1)[-1] != f"{document_id}.pdf"
        or parsed.query
        or parsed.fragment
        or urllib.parse.unquote(parsed.path) != parsed.path
    ):
        raise Exact100ZeroCostRecoveryError(
            "public document URL is not allowlisted and document-bound"
        )
    return url


def require_exact100_public_document_url(url: str, *, document_id: str) -> None:
    """Require every live redirect target to remain bound to the exact document."""

    if _public_download_url({"download_url": url}, document_id=document_id) != url:
        raise Exact100ZeroCostRecoveryError(
            "public document URL changed during bounded retrieval"
        )


def _selection_index(selection_bytes: bytes) -> dict[str, Mapping[str, object]]:
    records = _jsonl_records(selection_bytes, "selection")
    indexed: dict[str, Mapping[str, object]] = {}
    for record in records:
        candidate_id = _positive_id(
            record.get("candidate_id"), "selection candidate_id"
        )
        if candidate_id in indexed:
            raise Exact100ZeroCostRecoveryError("selection repeats candidate_id")
        indexed[candidate_id] = record
    return indexed


def _selected_document(
    selected: Mapping[str, object], source_document_id: str
) -> Mapping[str, object]:
    raw_documents = selected.get("documents")
    if not isinstance(raw_documents, list):
        raise Exact100ZeroCostRecoveryError("selection candidate lacks documents")
    documents = cast(list[object], raw_documents)
    matches: list[Mapping[str, object]] = []
    for raw_document in documents:
        if not isinstance(raw_document, Mapping):
            continue
        document = cast(Mapping[str, object], raw_document)
        if document.get("source_document_id") == source_document_id:
            matches.append(document)
    if len(matches) != 1:
        raise Exact100ZeroCostRecoveryError(
            "planned document is not unique in selection"
        )
    return matches[0]


def _canonical_object(payload: bytes, label: str) -> JsonRecord:
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Exact100ZeroCostRecoveryError(f"{label} is not JSON") from exc
    if not isinstance(value, dict):
        raise Exact100ZeroCostRecoveryError(f"{label} is not canonical JSON")
    record = cast(JsonRecord, value)
    if _bytes(record) != payload:
        raise Exact100ZeroCostRecoveryError(f"{label} is not canonical JSON")
    return record


def _jsonl_records(payload: bytes, label: str) -> tuple[Mapping[str, object], ...]:
    lines = payload.splitlines()
    if not lines or any(not line for line in lines):
        raise Exact100ZeroCostRecoveryError(f"{label} must be nonempty canonical JSONL")
    records: list[Mapping[str, object]] = []
    for line in lines:
        record = _canonical_object(line + b"\n", label)
        records.append(record)
    return tuple(records)


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise Exact100ZeroCostRecoveryError(f"{label} must be an object")
    return cast(Mapping[str, object], value)


def _required_text(record: Mapping[str, object], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value:
        raise Exact100ZeroCostRecoveryError(f"selection {field} must be nonempty text")
    return value


def _positive_id(value: object, label: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[1-9][0-9]*", value) is None:
        raise Exact100ZeroCostRecoveryError(
            f"{label} must be a positive decimal identifier"
        )
    return value


def _bytes(value: object) -> bytes:
    return canonical_json_bytes(
        value,
        error_type=Exact100ZeroCostRecoveryError,
        error_message="zero-cost recovery serialization failed",
    )


def _sha(payload: bytes) -> str:
    # contract-ratchet: allow frozen exact-byte recovery/verifier commitment
    return "sha256:" + hashlib.sha256(payload).hexdigest()
