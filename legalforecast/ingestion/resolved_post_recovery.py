"""Immutable lineage for public documents recovered from unknown-status origins."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPurchaseJournal,
    CaseDevPurchaseLedgerError,
    CaseDevPurchasePolicy,
    CaseDevPurchaseSnapshot,
    canonical_purchase_state_sha256,
    validate_unknown_public_recovery_evidence,
)
from legalforecast.ingestion.disclosure_clearance import (
    SCHEMA_VERSION,
    DisclosureClearanceError,
    ReviewAuthority,
    require_clearance_policy,
    validate_review_receipt,
)
from legalforecast.ingestion.disclosure_review_authority import (
    DisclosureReviewAuthority,
)
from legalforecast.ingestion.docket_decision_text_source import (
    VerifiedTerminalPurchaseDispositionAuthority,
    verified_terminal_purchase_disposition_record,
)
from legalforecast.ingestion.provenance_clearance import (
    _consume_recovered_public_clearance_capability,  # pyright: ignore[reportPrivateUsage]
    _consume_recovered_public_terminal_partition,  # pyright: ignore[reportPrivateUsage]
)
from legalforecast.ingestion.recap_fetch_attempt_policy import (
    BOUNDED_FETCH_ATTEMPT_AUTHORITY,
    RECAP_FETCH_ATTEMPT_POLICY_VERSION,
)
from legalforecast.ingestion.recap_fetch_broker import (
    BrokerOutcomeUnknown,
    validate_broker_receipt,
)

RESOLVED_POST_RECOVERY_SCHEMA_VERSION = (
    "legalforecast.resolved_post_recovery_public_document.v1"
)
RESOLVED_POST_RECOVERY_SCHEMA_VERSION_V2 = (
    "legalforecast.resolved_post_recovery_public_document.v2"
)
RESOLVED_POST_RECOVERY_SCHEMA_VERSION_V3 = (
    "legalforecast.resolved_post_recovery_public_document.v3"
)
RESOLVED_POST_RECOVERY_SCHEMA_VERSION_V4 = (
    "legalforecast.resolved_post_recovery_public_document.v4"
)
_DIRECT_QUEUE_RESOLVED_FIELDS = frozenset(
    {
        "schema_version",
        "candidate_id",
        "source_document_id",
        "recovery_origin",
        "attempt_policy_sha256",
        "selection_document_sha256",
        "purchase_operation_sha256",
        "operation_key",
        "delivery_authority",
        "purchase_policy_sha256",
        "direct_queue_delivery_authority",
        "fresh_recap_detail_sha256",
        "download_url_sha256",
        "download_record_sha256",
        "content_sha256",
        "byte_count",
        "clearance_record_sha256",
        "clearance_run_card_sha256",
        "clearance_artifact_sha256",
        "cohort_policy_artifact_sha256",
        "restriction_evidence_artifact_sha256",
        "restriction_evidence_rows_sha256",
        "fresh_detail_public_evidence_sha256",
        "restriction_status",
        "parser_eligible",
        "packet_eligible",
        "clearance_basis",
        "recovered_public_lineage",
        "record_sha256",
    }
)
_LEGACY_DIRECT_QUEUE_RESOLVED_FIELDS = _DIRECT_QUEUE_RESOLVED_FIELDS - {
    "direct_queue_delivery_authority"
} | {"queue_response_sha256"}
UNKNOWN_RECOVERY_ORIGIN = "unknown_status_attempt"
FRESH_PUBLIC_RESTRICTION_SCHEMA_VERSION = (
    "legalforecast.post_recovery_restriction_evidence.v1"
)
FRESH_PUBLIC_RESTRICTION_EVIDENCE = (
    "courtlistener_recap_fetch_fresh_detail_exact_match",
    "courtlistener_recap_fetch_is_available_true",
    "courtlistener_recap_fetch_is_sealed_false",
    "courtlistener_recap_fetch_no_positive_private_marker",
)
FRESH_PUBLIC_UNKNOWN_SEAL_EVIDENCE = (
    "courtlistener_recap_fetch_fresh_detail_exact_match",
    "courtlistener_recap_fetch_is_available_true",
    "courtlistener_recap_fetch_is_sealed_unknown",
    "courtlistener_recap_fetch_no_positive_private_marker",
    "courtlistener_recap_fetch_public_download_url_allowlisted",
)


def _terminal_disposition_capability_boundary() -> tuple[
    Callable[..., object], Callable[[object | None], frozenset[tuple[str, str]]]
]:
    """Require independent terminal-disposition replay before any omission."""

    capabilities: dict[object, frozenset[tuple[str, str]]] = {}

    def issue(
        *,
        authority: VerifiedTerminalPurchaseDispositionAuthority,
        purchase_journal: CaseDevPurchaseJournal,
        verified_recovery_capability: object,
    ) -> object:
        record = verified_terminal_purchase_disposition_record(
            authority,
            purchase_journal=purchase_journal,
        )
        raw_pairs = record.get("terminal_failure_pairs")
        if not isinstance(raw_pairs, list):
            raise ResolvedPostRecoveryError(
                "terminal disposition lacks its exhaustive failure pairs"
            )
        pairs: set[tuple[str, str]] = set()
        for raw_pair in cast(list[object], raw_pairs):
            if not isinstance(raw_pair, Mapping):
                raise ResolvedPostRecoveryError(
                    "terminal disposition contains an invalid failure pair"
                )
            pair_record = cast(Mapping[str, object], raw_pair)
            pair = (
                _required_text(pair_record.get("candidate_id"), "candidate_id"),
                _required_text(
                    pair_record.get("source_document_id"), "source_document_id"
                ),
            )
            if pair in pairs:
                raise ResolvedPostRecoveryError(
                    "terminal disposition repeats a failure pair"
                )
            pairs.add(pair)
        recovery_partition = _consume_recovered_public_terminal_partition(
            verified_recovery_capability
        )
        if recovery_partition is None:
            raise ResolvedPostRecoveryError(
                "terminal disposition lacks a terminal recovery partition"
            )
        if pairs != set(recovery_partition.keys):
            raise ResolvedPostRecoveryError(
                "terminal disposition differs from recovery terminal partition"
            )
        capability = object()
        capabilities[capability] = frozenset(pairs)
        return capability

    def consume(capability: object | None) -> frozenset[tuple[str, str]]:
        try:
            return capabilities[capability]
        except (KeyError, TypeError):
            raise ResolvedPostRecoveryError(
                "terminal omission requires verifier-issued disposition authority"
            ) from None

    return issue, consume


(
    _issue_terminal_disposition_capability,
    _consume_terminal_disposition_capability,
) = _terminal_disposition_capability_boundary()
del _terminal_disposition_capability_boundary

_SHA256 = re.compile(r"[0-9a-f]{64}")
_UUID4 = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
)


class ResolvedPostRecoveryError(ValueError):
    """Raised when unknown-origin bytes lack exact public-clearance lineage."""


@dataclass(frozen=True, slots=True)
class AuthenticatedClearanceLineage:
    """Exact controlled-review commitments from a completed clearance run."""

    clearance_run_card_sha256: str
    clearance_artifact_sha256: str
    reviews_artifact_sha256: str
    review_receipt_sha256: str
    cohort_policy_artifact_sha256: str
    restriction_evidence_artifact_sha256: str
    review_authority_sha256: str
    authority: ReviewAuthority


RECOVERY_CHAIN_VALIDATION_FAILED = "FAILED"
RECOVERY_CHAIN_VALIDATION_NOT_EVALUATED = "NOT_EVALUATED"


@dataclass(frozen=True, slots=True)
class RecoveryChainValidationIssue:
    """One structured recovery-chain validation finding."""

    code: str
    status: str
    layer: str
    artifact: str
    message: str
    field: str | None = None
    blocked_by: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("code", "status", "layer", "artifact", "message"):
            value = cast(object, getattr(self, name))
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")
        if self.status not in {
            RECOVERY_CHAIN_VALIDATION_FAILED,
            RECOVERY_CHAIN_VALIDATION_NOT_EVALUATED,
        }:
            raise ValueError("status must be a supported recovery-chain state")
        field = cast(object, self.field)
        if field is not None and (not isinstance(field, str) or not field):
            raise ValueError("field must be None or a non-empty string")
        if any(not code for code in self.blocked_by):
            raise ValueError("blocked_by must contain only non-empty strings")

    def sort_key(self) -> tuple[str, str, str, str, str, str]:
        return (
            self.artifact,
            self.layer,
            self.code,
            self.status,
            self.field or "",
            self.message,
        )

    def to_record(self) -> dict[str, object]:
        record: dict[str, object] = {
            "code": self.code,
            "status": self.status,
            "layer": self.layer,
            "artifact": self.artifact,
            "message": self.message,
        }
        if self.field is not None:
            record["field"] = self.field
        if self.blocked_by:
            record["blocked_by"] = list(self.blocked_by)
        return record


@dataclass(frozen=True, slots=True)
class RecoveryChainValidationResult:
    """Deterministic collect-all result for resolved post-recovery validation."""

    issues: tuple[RecoveryChainValidationIssue, ...]

    @property
    def ok(self) -> bool:
        return not self.issues

    def to_record(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "issue_count": len(self.issues),
            "issues": [issue.to_record() for issue in self.issues],
        }

    def require_ok(self) -> None:
        if self.ok:
            return
        formatted: list[str] = []
        for issue in self.issues:
            blocked = (
                f" blocked_by={','.join(issue.blocked_by)}" if issue.blocked_by else ""
            )
            field = f" field={issue.field}" if issue.field is not None else ""
            formatted.append(
                f"{issue.artifact} {issue.code} {issue.status}{field}{blocked}: "
                f"{issue.message}"
            )
        raise ResolvedPostRecoveryError(
            "resolved post-recovery validation failed: " + "; ".join(formatted)
        )


def _validation_artifact(key: tuple[str, str]) -> str:
    return f"{key[0]}/{key[1]}"


def _validation_issue(
    *,
    code: str,
    status: str,
    layer: str,
    artifact: str,
    message: str,
    field: str | None = None,
    blocked_by: Sequence[str] = (),
) -> RecoveryChainValidationIssue:
    return RecoveryChainValidationIssue(
        code=code,
        status=status,
        layer=layer,
        artifact=artifact,
        message=message,
        field=field,
        blocked_by=tuple(dict.fromkeys(blocked_by)),
    )


def collect_resolved_post_recovery_build_issues(
    *,
    selection_records: Sequence[Mapping[str, Any]],
    purchase_operation_records: Sequence[Mapping[str, Any]],
    download_records: Sequence[Mapping[str, Any]],
    clearance_records: Sequence[Mapping[str, Any]],
    attempt_policy_artifact: Mapping[str, object],
    clearance_artifact_bytes: bytes,
    clearance_run_card: Mapping[str, Any],
    clearance_run_card_bytes: bytes,
    reviews_artifact_bytes: bytes,
    review_receipt_artifact: Mapping[str, object],
    review_receipt_bytes: bytes,
    review_requests_artifact_bytes: bytes,
    review_worksheet_artifact: Mapping[str, object],
    review_worksheet_bytes: bytes,
    reviewer_policy_bytes: bytes,
    disclosure_authority: DisclosureReviewAuthority | None,
    cohort_policy_artifact_bytes: bytes,
    download_manifest_artifact_bytes: bytes,
    restriction_records: Sequence[Mapping[str, Any]],
    restriction_artifact_bytes: bytes,
    allow_test_service_identity: bool = False,
    verified_lineage_capability: object | None = None,
    verified_recovery_capability: object | None = None,
    verified_terminal_disposition_capability: object | None = None,
) -> RecoveryChainValidationResult:
    """Collect independent build-time violations without mutating state."""

    issues: list[RecoveryChainValidationIssue] = []
    recovered_lineages: Mapping[tuple[str, str], Mapping[str, object]] | None = None
    terminal_keys: frozenset[tuple[str, str]] = frozenset()

    if (
        verified_terminal_disposition_capability is not None
        and verified_recovery_capability is None
    ):
        issues.append(
            _validation_issue(
                code="TERMINAL_DISPOSITION_CAPABILITY_VALIDATION",
                status=RECOVERY_CHAIN_VALIDATION_FAILED,
                layer="capability",
                artifact="global",
                message=(
                    "terminal disposition authority requires recovered-public authority"
                ),
            )
        )
    if (
        verified_recovery_capability is not None
        and verified_lineage_capability is not None
    ):
        issues.append(
            _validation_issue(
                code="CLEARANCE_CAPABILITY_MODE",
                status=RECOVERY_CHAIN_VALIDATION_FAILED,
                layer="capability",
                artifact="global",
                message="conflicting authenticated clearance capabilities",
            )
        )
    if verified_recovery_capability is not None:
        try:
            recovered_lineages = _consume_recovered_public_clearance_capability(
                verified_recovery_capability
            )
        except ResolvedPostRecoveryError as exc:
            issues.append(
                _validation_issue(
                    code="RECOVERED_PUBLIC_CAPABILITY_VALIDATION",
                    status=RECOVERY_CHAIN_VALIDATION_FAILED,
                    layer="capability",
                    artifact="global",
                    message=str(exc),
                )
            )
        if verified_terminal_disposition_capability is not None:
            try:
                terminal_keys = _consume_terminal_disposition_capability(
                    verified_terminal_disposition_capability
                )
            except ResolvedPostRecoveryError as exc:
                issues.append(
                    _validation_issue(
                        code="TERMINAL_DISPOSITION_CAPABILITY_VALIDATION",
                        status=RECOVERY_CHAIN_VALIDATION_FAILED,
                        layer="capability",
                        artifact="global",
                        message=str(exc),
                    )
                )
    elif verified_lineage_capability is not None:
        try:
            _bind_internal_verified_provenance_lineage(
                _consume_verified_lineage_capability(verified_lineage_capability),
                clearance_records=clearance_records,
                clearance_artifact_bytes=clearance_artifact_bytes,
                clearance_run_card=clearance_run_card,
                clearance_run_card_bytes=clearance_run_card_bytes,
                reviews_artifact_bytes=reviews_artifact_bytes,
                review_receipt_bytes=review_receipt_bytes,
                reviewer_policy_bytes=reviewer_policy_bytes,
                cohort_policy_artifact_bytes=cohort_policy_artifact_bytes,
                restriction_records=restriction_records,
                restriction_artifact_bytes=restriction_artifact_bytes,
            )
        except ResolvedPostRecoveryError as exc:
            issues.append(
                _validation_issue(
                    code="CLEARANCE_LINEAGE_VALIDATION",
                    status=RECOVERY_CHAIN_VALIDATION_FAILED,
                    layer="clearance_lineage",
                    artifact="global",
                    message=str(exc),
                )
            )
    elif disclosure_authority is None:
        issues.append(
            _validation_issue(
                code="CLEARANCE_LINEAGE_VALIDATION",
                status=RECOVERY_CHAIN_VALIDATION_FAILED,
                layer="clearance_lineage",
                artifact="global",
                message="legacy clearance authority is missing",
            )
        )
    else:
        try:
            validate_authenticated_clearance_lineage(
                clearance_records=clearance_records,
                clearance_artifact_bytes=clearance_artifact_bytes,
                clearance_run_card=clearance_run_card,
                clearance_run_card_bytes=clearance_run_card_bytes,
                reviews_artifact_bytes=reviews_artifact_bytes,
                review_receipt_artifact=review_receipt_artifact,
                review_receipt_bytes=review_receipt_bytes,
                review_requests_artifact_bytes=review_requests_artifact_bytes,
                review_worksheet_artifact=review_worksheet_artifact,
                review_worksheet_bytes=review_worksheet_bytes,
                reviewer_policy_bytes=reviewer_policy_bytes,
                disclosure_authority=disclosure_authority,
                cohort_policy_artifact_bytes=cohort_policy_artifact_bytes,
                download_manifest_artifact_bytes=download_manifest_artifact_bytes,
                restriction_records=restriction_records,
                restriction_artifact_bytes=restriction_artifact_bytes,
                allow_test_service_identity=allow_test_service_identity,
            )
        except ResolvedPostRecoveryError as exc:
            issues.append(
                _validation_issue(
                    code="CLEARANCE_LINEAGE_VALIDATION",
                    status=RECOVERY_CHAIN_VALIDATION_FAILED,
                    layer="clearance_lineage",
                    artifact="global",
                    message=str(exc),
                )
            )

    try:
        policy_sha256, purchase_policy_sha256, attempt_documents = _attempt_documents(
            attempt_policy_artifact
        )
    except ResolvedPostRecoveryError as exc:
        attempt_documents = None
        policy_sha256 = None
        purchase_policy_sha256 = None
        issues.append(
            _validation_issue(
                code="ATTEMPT_POLICY_VALIDATION",
                status=RECOVERY_CHAIN_VALIDATION_FAILED,
                layer="attempt_policy",
                artifact="global",
                message=str(exc),
            )
        )
    try:
        unknown_selection = _unknown_selection(selection_records)
    except ResolvedPostRecoveryError as exc:
        unknown_selection = None
        issues.append(
            _validation_issue(
                code="UNKNOWN_SELECTION_VALIDATION",
                status=RECOVERY_CHAIN_VALIDATION_FAILED,
                layer="selection",
                artifact="global",
                message=str(exc),
            )
        )
    if unknown_selection is None:
        required: set[tuple[str, str]] | None = None
    else:
        if not terminal_keys <= set(unknown_selection):
            issues.append(
                _validation_issue(
                    code="TERMINAL_SELECTION_PARTITION",
                    status=RECOVERY_CHAIN_VALIDATION_FAILED,
                    layer="selection",
                    artifact="global",
                    message=(
                        "terminal-unavailable partition is outside unknown "
                        "selected documents"
                    ),
                )
            )
        required = set(unknown_selection) - terminal_keys
        if attempt_documents is not None and set(attempt_documents) != set(
            unknown_selection
        ):
            issues.append(
                _validation_issue(
                    code="ATTEMPT_POLICY_COVERAGE",
                    status=RECOVERY_CHAIN_VALIDATION_FAILED,
                    layer="attempt_policy",
                    artifact="global",
                    message=(
                        "attempt policy does not exactly cover unknown "
                        "selected documents"
                    ),
                )
            )
        if recovered_lineages is not None and set(recovered_lineages) != required:
            issues.append(
                _validation_issue(
                    code="RECOVERED_PUBLIC_CAPABILITY_COVERAGE",
                    status=RECOVERY_CHAIN_VALIDATION_FAILED,
                    layer="capability",
                    artifact="global",
                    message=(
                        "recovered-public capability does not exactly cover "
                        "recovered documents"
                    ),
                )
            )
    try:
        operations = _index(purchase_operation_records, "purchase operation")
    except ResolvedPostRecoveryError as exc:
        operations = None
        issues.append(
            _validation_issue(
                code="PURCHASE_OPERATION_INDEX",
                status=RECOVERY_CHAIN_VALIDATION_FAILED,
                layer="purchase_operation",
                artifact="global",
                message=str(exc),
            )
        )
    try:
        downloads = _index(download_records, "download")
    except ResolvedPostRecoveryError as exc:
        downloads = None
        issues.append(
            _validation_issue(
                code="DOWNLOAD_INDEX",
                status=RECOVERY_CHAIN_VALIDATION_FAILED,
                layer="download",
                artifact="global",
                message=str(exc),
            )
        )
    try:
        clearances = _index(clearance_records, "clearance")
    except ResolvedPostRecoveryError as exc:
        clearances = None
        issues.append(
            _validation_issue(
                code="CLEARANCE_INDEX",
                status=RECOVERY_CHAIN_VALIDATION_FAILED,
                layer="clearance",
                artifact="global",
                message=str(exc),
            )
        )
    try:
        restrictions = _group_index(restriction_records, "restriction evidence")
    except ResolvedPostRecoveryError as exc:
        restrictions = None
        issues.append(
            _validation_issue(
                code="RESTRICTION_INDEX",
                status=RECOVERY_CHAIN_VALIDATION_FAILED,
                layer="restriction",
                artifact="global",
                message=str(exc),
            )
        )
    if required is not None:
        if operations is not None:
            missing = sorted(required - set(operations))
            if missing:
                issues.append(
                    _validation_issue(
                        code="PURCHASE_OPERATION_COVERAGE",
                        status=RECOVERY_CHAIN_VALIDATION_FAILED,
                        layer="purchase_operation",
                        artifact="global",
                        message=(
                            "purchase operation lacks unknown-origin coverage: "
                            f"{missing}"
                        ),
                    )
                )
        if downloads is not None:
            missing = sorted(required - set(downloads))
            if missing:
                issues.append(
                    _validation_issue(
                        code="DOWNLOAD_COVERAGE",
                        status=RECOVERY_CHAIN_VALIDATION_FAILED,
                        layer="download",
                        artifact="global",
                        message=f"download lacks unknown-origin coverage: {missing}",
                    )
                )
        if clearances is not None:
            missing = sorted(required - set(clearances))
            if missing:
                issues.append(
                    _validation_issue(
                        code="CLEARANCE_COVERAGE",
                        status=RECOVERY_CHAIN_VALIDATION_FAILED,
                        layer="clearance",
                        artifact="global",
                        message=f"clearance lacks unknown-origin coverage: {missing}",
                    )
                )
    if (
        required is not None
        and operations is not None
        and terminal_keys - set(operations)
    ):
        issues.append(
            _validation_issue(
                code="TERMINAL_SELECTION_COVERAGE",
                status=RECOVERY_CHAIN_VALIDATION_FAILED,
                layer="purchase_operation",
                artifact="global",
                message="purchase operation lacks terminal-unavailable coverage",
            )
        )

    if required is not None:
        known_selection = cast(
            Mapping[tuple[str, str], Mapping[str, Any]], unknown_selection
        )
        for key in sorted(required):
            artifact = _validation_artifact(key)
            selection_document = known_selection[key]
            selection_sha256 = _sha256(selection_document)
            attempt_failed = False
            if (
                attempt_documents is None
                or policy_sha256 is None
                or purchase_policy_sha256 is None
            ):
                attempt_failed = True
                issues.append(
                    _validation_issue(
                        code="ATTEMPT_DOCUMENT_BINDING",
                        status=RECOVERY_CHAIN_VALIDATION_NOT_EVALUATED,
                        layer="attempt_policy",
                        artifact=artifact,
                        message="attempt document could not be evaluated",
                        blocked_by=("ATTEMPT_POLICY_VALIDATION",),
                    )
                )
            else:
                attempt = attempt_documents.get(key)
                if attempt is None:
                    attempt_failed = True
                    issues.append(
                        _validation_issue(
                            code="ATTEMPT_DOCUMENT_BINDING",
                            status=RECOVERY_CHAIN_VALIDATION_FAILED,
                            layer="attempt_policy",
                            artifact=artifact,
                            message="attempt policy lacks selected document",
                        )
                    )
                elif attempt["selection_document_sha256"] != selection_sha256:
                    attempt_failed = True
                    issues.append(
                        _validation_issue(
                            code="ATTEMPT_DOCUMENT_BINDING",
                            status=RECOVERY_CHAIN_VALIDATION_FAILED,
                            layer="attempt_policy",
                            artifact=artifact,
                            field="selection_document_sha256",
                            message="attempt policy selection commitment changed",
                        )
                    )
            operation_failed = True
            if attempt_failed:
                issues.append(
                    _validation_issue(
                        code="PURCHASE_OPERATION_VALIDATION",
                        status=RECOVERY_CHAIN_VALIDATION_NOT_EVALUATED,
                        layer="purchase_operation",
                        artifact=artifact,
                        message=(
                            "purchase operation prerequisites did not authenticate"
                        ),
                        blocked_by=("ATTEMPT_DOCUMENT_BINDING",),
                    )
                )
            elif (
                operations is None
                or policy_sha256 is None
                or purchase_policy_sha256 is None
            ):
                issues.append(
                    _validation_issue(
                        code="PURCHASE_OPERATION_VALIDATION",
                        status=RECOVERY_CHAIN_VALIDATION_NOT_EVALUATED,
                        layer="purchase_operation",
                        artifact=artifact,
                        message="purchase operation index did not authenticate",
                        blocked_by=("PURCHASE_OPERATION_INDEX",),
                    )
                )
            else:
                operation = operations.get(key)
                if operation is None:
                    issues.append(
                        _validation_issue(
                            code="PURCHASE_OPERATION_VALIDATION",
                            status=RECOVERY_CHAIN_VALIDATION_FAILED,
                            layer="purchase_operation",
                            artifact=artifact,
                            message="purchase operation lacks selected document",
                        )
                    )
                else:
                    try:
                        _validate_operation(
                            operation,
                            key=key,
                            attempt_policy_sha256=policy_sha256,
                            selection_document_sha256=selection_sha256,
                            expected_purchase_policy_sha256=purchase_policy_sha256,
                            verified_recovered_lineage=(
                                None
                                if recovered_lineages is None
                                else recovered_lineages.get(key)
                            ),
                        )
                        operation_failed = False
                    except ResolvedPostRecoveryError as exc:
                        issues.append(
                            _validation_issue(
                                code="PURCHASE_OPERATION_VALIDATION",
                                status=RECOVERY_CHAIN_VALIDATION_FAILED,
                                layer="purchase_operation",
                                artifact=artifact,
                                message=str(exc),
                            )
                        )
            download_failed = True
            if operation_failed:
                issues.append(
                    _validation_issue(
                        code="DOWNLOAD_VALIDATION",
                        status=RECOVERY_CHAIN_VALIDATION_NOT_EVALUATED,
                        layer="download",
                        artifact=artifact,
                        message="download prerequisites did not authenticate",
                        blocked_by=("PURCHASE_OPERATION_VALIDATION",),
                    )
                )
            elif downloads is None or policy_sha256 is None or operations is None:
                issues.append(
                    _validation_issue(
                        code="DOWNLOAD_VALIDATION",
                        status=RECOVERY_CHAIN_VALIDATION_NOT_EVALUATED,
                        layer="download",
                        artifact=artifact,
                        message="download index did not authenticate",
                        blocked_by=("DOWNLOAD_INDEX",),
                    )
                )
            else:
                download = downloads.get(key)
                operation = operations[key]
                if download is None:
                    issues.append(
                        _validation_issue(
                            code="DOWNLOAD_VALIDATION",
                            status=RECOVERY_CHAIN_VALIDATION_FAILED,
                            layer="download",
                            artifact=artifact,
                            message="download lacks selected document",
                        )
                    )
                else:
                    try:
                        _validate_download(
                            download,
                            key=key,
                            operation=operation,
                            attempt_policy_sha256=policy_sha256,
                        )
                        download_failed = False
                    except ResolvedPostRecoveryError as exc:
                        issues.append(
                            _validation_issue(
                                code="DOWNLOAD_VALIDATION",
                                status=RECOVERY_CHAIN_VALIDATION_FAILED,
                                layer="download",
                                artifact=artifact,
                                message=str(exc),
                            )
                        )
            clearance_failed = True
            if download_failed:
                issues.append(
                    _validation_issue(
                        code="CLEARANCE_VALIDATION",
                        status=RECOVERY_CHAIN_VALIDATION_NOT_EVALUATED,
                        layer="clearance",
                        artifact=artifact,
                        message="clearance prerequisites did not authenticate",
                        blocked_by=("DOWNLOAD_VALIDATION",),
                    )
                )
            elif clearances is None or downloads is None:
                issues.append(
                    _validation_issue(
                        code="CLEARANCE_VALIDATION",
                        status=RECOVERY_CHAIN_VALIDATION_NOT_EVALUATED,
                        layer="clearance",
                        artifact=artifact,
                        message="clearance index did not authenticate",
                        blocked_by=("CLEARANCE_INDEX",),
                    )
                )
            else:
                clearance = clearances.get(key)
                download = downloads[key]
                if clearance is None:
                    issues.append(
                        _validation_issue(
                            code="CLEARANCE_VALIDATION",
                            status=RECOVERY_CHAIN_VALIDATION_FAILED,
                            layer="clearance",
                            artifact=artifact,
                            message="clearance lacks selected document",
                        )
                    )
                else:
                    try:
                        _validate_clearance(clearance, key=key, download=download)
                        clearance_failed = False
                    except ResolvedPostRecoveryError as exc:
                        issues.append(
                            _validation_issue(
                                code="CLEARANCE_VALIDATION",
                                status=RECOVERY_CHAIN_VALIDATION_FAILED,
                                layer="clearance",
                                artifact=artifact,
                                message=str(exc),
                            )
                        )
            restriction_failed = True
            if operation_failed:
                issues.append(
                    _validation_issue(
                        code="RESTRICTION_VALIDATION",
                        status=RECOVERY_CHAIN_VALIDATION_NOT_EVALUATED,
                        layer="restriction",
                        artifact=artifact,
                        message="restriction prerequisites did not authenticate",
                        blocked_by=("PURCHASE_OPERATION_VALIDATION",),
                    )
                )
            elif restrictions is None or operations is None:
                issues.append(
                    _validation_issue(
                        code="RESTRICTION_VALIDATION",
                        status=RECOVERY_CHAIN_VALIDATION_NOT_EVALUATED,
                        layer="restriction",
                        artifact=artifact,
                        message="restriction index did not authenticate",
                        blocked_by=("RESTRICTION_INDEX",),
                    )
                )
            else:
                operation = operations[key]
                try:
                    _fresh_public_restriction_record(
                        restrictions.get(key, ()),
                        key=key,
                        operation=operation,
                    )
                    restriction_failed = False
                except ResolvedPostRecoveryError as exc:
                    issues.append(
                        _validation_issue(
                            code="RESTRICTION_VALIDATION",
                            status=RECOVERY_CHAIN_VALIDATION_FAILED,
                            layer="restriction",
                            artifact=artifact,
                            message=str(exc),
                        )
                    )
            if clearance_failed or restriction_failed or operation_failed:
                blocked_by: list[str] = []
                if clearance_failed:
                    blocked_by.append("CLEARANCE_VALIDATION")
                if restriction_failed:
                    blocked_by.append("RESTRICTION_VALIDATION")
                if operation_failed:
                    blocked_by.append("PURCHASE_OPERATION_VALIDATION")
                issues.append(
                    _validation_issue(
                        code="RECOVERED_PUBLIC_LINEAGE_VALIDATION",
                        status=RECOVERY_CHAIN_VALIDATION_NOT_EVALUATED,
                        layer="clearance",
                        artifact=artifact,
                        message=(
                            "recovered-public lineage prerequisites did not "
                            "authenticate"
                        ),
                        blocked_by=blocked_by,
                    )
                )
            elif clearances is None or operations is None or restrictions is None:
                issues.append(
                    _validation_issue(
                        code="RECOVERED_PUBLIC_LINEAGE_VALIDATION",
                        status=RECOVERY_CHAIN_VALIDATION_NOT_EVALUATED,
                        layer="clearance",
                        artifact=artifact,
                        message="recovered-public lineage inputs did not authenticate",
                        blocked_by=(
                            "CLEARANCE_INDEX",
                            "PURCHASE_OPERATION_INDEX",
                            "RESTRICTION_INDEX",
                        ),
                    )
                )
            else:
                clearance = clearances[key]
                operation = operations[key]
                fresh_public = _fresh_public_restriction_record(
                    restrictions[key],
                    key=key,
                    operation=operation,
                )
                try:
                    _validate_recovered_public_clearance_lineage(
                        clearance,
                        operation=operation,
                        fresh_public=fresh_public,
                        key=key,
                    )
                except ResolvedPostRecoveryError as exc:
                    issues.append(
                        _validation_issue(
                            code="RECOVERED_PUBLIC_LINEAGE_VALIDATION",
                            status=RECOVERY_CHAIN_VALIDATION_FAILED,
                            layer="clearance",
                            artifact=artifact,
                            message=str(exc),
                        )
                    )
    ordered = tuple(sorted(issues, key=RecoveryChainValidationIssue.sort_key))
    return RecoveryChainValidationResult(issues=ordered)


def _verified_lineage_capability_boundary() -> tuple[
    Callable[..., object],
    Callable[[object | None], AuthenticatedClearanceLineage],
]:
    """Keep authenticated capability state and its sealer closure-local."""

    authenticated_lineages: dict[object, AuthenticatedClearanceLineage] = {}

    def seal(lineage: AuthenticatedClearanceLineage) -> object:
        capability = object()
        authenticated_lineages[capability] = lineage
        return capability

    def issue(
        *,
        clearance_path: Path,
        clearance_run_card_path: Path,
        expected_download_manifest_path: Path,
        expected_restriction_path: Path,
        captured_artifact_bytes: Mapping[str, bytes],
    ) -> object:
        lineage = _authenticate_verified_lineage_from_raw_evidence(
            clearance_path=clearance_path,
            clearance_run_card_path=clearance_run_card_path,
            expected_download_manifest_path=expected_download_manifest_path,
            expected_restriction_path=expected_restriction_path,
            captured_artifact_bytes=captured_artifact_bytes,
        )
        return seal(lineage)

    def consume(capability: object | None) -> AuthenticatedClearanceLineage:
        try:
            return authenticated_lineages[capability]
        except (KeyError, TypeError):
            raise ResolvedPostRecoveryError(
                "verified provenance lineage requires an authenticated capability"
            ) from None

    return issue, consume


(
    _issue_verified_lineage_capability,
    _consume_verified_lineage_capability,
) = _verified_lineage_capability_boundary()


def _authenticate_verified_lineage_from_raw_evidence(
    *,
    clearance_path: Path,
    clearance_run_card_path: Path,
    expected_download_manifest_path: Path,
    expected_restriction_path: Path,
    captured_artifact_bytes: Mapping[str, bytes],
) -> AuthenticatedClearanceLineage:
    """Replay raw provenance evidence and derive authenticated lineage."""

    # Import lazily because the CLI owns the full interactive checkpoint replay while
    # this module owns capability issuance and downstream lineage binding.
    from legalforecast import cli as cli_module

    verify = cast(
        Any,
        cli_module._verify_authenticated_clearance_run_card,  # pyright: ignore[reportPrivateUsage]
    )
    verify(
        clearance_path=clearance_path,
        clearance_run_card_path=clearance_run_card_path,
        expected_download_manifest_path=expected_download_manifest_path,
        expected_restriction_path=expected_restriction_path,
        captured_artifact_bytes=captured_artifact_bytes,
    )
    try:
        run_card_bytes = captured_artifact_bytes[
            os.path.abspath(clearance_run_card_path)
        ]
        clearance_bytes = captured_artifact_bytes[os.path.abspath(clearance_path)]
    except KeyError as exc:
        raise ResolvedPostRecoveryError(
            "authenticated provenance snapshot lacks clearance artifacts"
        ) from exc
    run_card = _json_object_from_bytes(
        run_card_bytes, "authenticated provenance clearance run card"
    )
    sources = _mapping(
        run_card.get("source_commitments"), "provenance source commitments"
    )
    authority = _mapping(
        run_card.get("clearance_authority"), "provenance clearance authority"
    )
    if authority.get("kind") != "provenance_first_with_john_exceptions":
        raise ResolvedPostRecoveryError(
            "verified lineage capability requires provenance-first clearance"
        )

    def committed_bytes(name: str) -> bytes:
        commitment = _mapping(sources.get(name), f"{name} commitment")
        path = Path(_required_text(commitment.get("path"), f"{name} path"))
        try:
            data = captured_artifact_bytes[os.path.abspath(path)]
        except KeyError as exc:
            raise ResolvedPostRecoveryError(
                f"authenticated provenance snapshot lacks {name}"
            ) from exc
        if _commitment_sha256(commitment.get("sha256"), name) != _bytes_sha256(data):
            raise ResolvedPostRecoveryError(
                f"authenticated provenance {name} commitment changed"
            )
        return data

    decisions_bytes = committed_bytes("exception_decisions")
    recorder_bytes = committed_bytes("exception_review_run_card")
    cohort_policy_bytes = committed_bytes("cohort_policy")
    restriction_bytes = committed_bytes("restriction_evidence")
    routing_plan_bytes = committed_bytes("routing_plan")
    decisions = _jsonl_records_from_bytes(
        decisions_bytes, "authenticated provenance exception decisions"
    )
    reviewed_at = max(
        (_required_text(row.get("reviewed_at"), "reviewed_at") for row in decisions),
        default=_required_text(run_card.get("generated_at"), "generated_at"),
    )
    return AuthenticatedClearanceLineage(
        clearance_run_card_sha256=_bytes_sha256(run_card_bytes),
        clearance_artifact_sha256=_bytes_sha256(clearance_bytes),
        reviews_artifact_sha256=_bytes_sha256(decisions_bytes),
        review_receipt_sha256=_bytes_sha256(recorder_bytes),
        cohort_policy_artifact_sha256=_bytes_sha256(cohort_policy_bytes),
        restriction_evidence_artifact_sha256=_bytes_sha256(restriction_bytes),
        review_authority_sha256=_sha256(authority),
        authority=ReviewAuthority(
            reviewer_id="John Hughes",
            controlled_store_uri="private-store://john/disclosure-exception-review",
            authentication_method="interactive_hash_confirmation_only",
            authenticated_at=reviewed_at,
            review_artifact_sha256=_bytes_sha256(decisions_bytes),
            reviewer_policy_sha256=_bytes_sha256(routing_plan_bytes),
        ),
    )


del _verified_lineage_capability_boundary


def validate_authenticated_clearance_lineage(
    *,
    clearance_records: Sequence[Mapping[str, Any]],
    clearance_artifact_bytes: bytes,
    clearance_run_card: Mapping[str, Any],
    clearance_run_card_bytes: bytes,
    reviews_artifact_bytes: bytes,
    review_receipt_artifact: Mapping[str, object],
    review_receipt_bytes: bytes,
    review_requests_artifact_bytes: bytes,
    review_worksheet_artifact: Mapping[str, object],
    review_worksheet_bytes: bytes,
    reviewer_policy_bytes: bytes,
    disclosure_authority: DisclosureReviewAuthority,
    cohort_policy_artifact_bytes: bytes,
    download_manifest_artifact_bytes: bytes,
    restriction_records: Sequence[Mapping[str, Any]],
    restriction_artifact_bytes: bytes,
    allow_test_service_identity: bool = False,
) -> AuthenticatedClearanceLineage:
    """Verify the exact executed clearance inputs, authority, and output bytes."""

    if _json_object_from_bytes(
        clearance_run_card_bytes, "clear-disclosures run card"
    ) != dict(clearance_run_card):
        raise ResolvedPostRecoveryError(
            "clear-disclosures run-card bytes do not match the parsed artifact"
        )
    if _jsonl_records_from_bytes(clearance_artifact_bytes, "disclosure clearance") != [
        dict(record) for record in clearance_records
    ]:
        raise ResolvedPostRecoveryError(
            "disclosure-clearance bytes do not match the parsed records"
        )
    if _json_object_from_bytes(review_receipt_bytes, "review receipt") != dict(
        review_receipt_artifact
    ):
        raise ResolvedPostRecoveryError(
            "review-receipt bytes do not match the parsed artifact"
        )
    if _jsonl_records_from_bytes(
        restriction_artifact_bytes, "restriction evidence"
    ) != [dict(record) for record in restriction_records]:
        raise ResolvedPostRecoveryError(
            "restriction-evidence bytes do not match the parsed records"
        )
    cohort_policy_artifact = _json_object_from_bytes(
        cohort_policy_artifact_bytes, "cohort policy"
    )
    if (
        cohort_policy_artifact.get("policy_sha256")
        != disclosure_authority.identity.cohort_policy_sha256
    ):
        raise ResolvedPostRecoveryError(
            "cohort policy identity differs from disclosure authority"
        )
    if (
        clearance_run_card.get("schema_version")
        != "legalforecast.acquisition_run_card.v1"
        or clearance_run_card.get("stage") != "clear-disclosures"
        or clearance_run_card.get("status") != "completed"
        or clearance_run_card.get("dry_run") is not False
        or clearance_run_card.get("execute") is not True
        or clearance_run_card.get("paid_activity_requested") is not False
        or clearance_run_card.get("paid_activity_executed") is not False
    ):
        raise ResolvedPostRecoveryError(
            "resolved lineage requires an executed nonpaid clear-disclosures run card"
        )
    source = _mapping(
        clearance_run_card.get("source_commitments"), "clearance source commitments"
    )
    output = _mapping(
        clearance_run_card.get("output_commitments"), "clearance output commitments"
    )
    expected_sources = {
        "cohort_policy": _bytes_sha256(cohort_policy_artifact_bytes),
        "download_manifest": _bytes_sha256(download_manifest_artifact_bytes),
        "review_requests": _bytes_sha256(review_requests_artifact_bytes),
        "review_worksheet": _bytes_sha256(review_worksheet_bytes),
        "reviews": _bytes_sha256(reviews_artifact_bytes),
        "review_receipt": _bytes_sha256(review_receipt_bytes),
        "reviewer_policy": _bytes_sha256(reviewer_policy_bytes),
        "restriction_evidence": _bytes_sha256(restriction_artifact_bytes),
    }
    for name, expected in expected_sources.items():
        commitment = _mapping(source.get(name), f"{name} commitment")
        if _commitment_sha256(commitment.get("sha256"), name) != expected:
            raise ResolvedPostRecoveryError(
                f"clear-disclosures {name} commitment mismatch"
            )
    clearance_sha256 = _bytes_sha256(clearance_artifact_bytes)
    clearance_commitment = _mapping(
        output.get("disclosure_clearance"), "disclosure clearance commitment"
    )
    if (
        _commitment_sha256(clearance_commitment.get("sha256"), "disclosure clearance")
        != clearance_sha256
    ):
        raise ResolvedPostRecoveryError("clear-disclosures output commitment mismatch")
    try:
        authority = validate_review_receipt(
            reviews_artifact_bytes,
            review_receipt_artifact,
            reviewer_policy_bytes=reviewer_policy_bytes,
            disclosure_authority=disclosure_authority,
            worksheet_bytes=review_worksheet_bytes,
            worksheet=review_worksheet_artifact,
            review_requests_bytes=review_requests_artifact_bytes,
            download_manifest_bytes=download_manifest_artifact_bytes,
            restriction_evidence_bytes=restriction_artifact_bytes,
            allow_test_service_identity=allow_test_service_identity,
        )
    except DisclosureClearanceError as exc:
        raise ResolvedPostRecoveryError(str(exc)) from exc
    expected_authority: dict[str, object] = {
        "reviewer_id": authority.reviewer_id,
        "controlled_store_uri": authority.controlled_store_uri,
        "authentication_method": authority.authentication_method,
        "authenticated_at": authority.authenticated_at,
        "review_artifact_sha256": "sha256:" + authority.review_artifact_sha256,
        "reviewer_policy_sha256": "sha256:" + authority.reviewer_policy_sha256,
        "disclosure_authority_sha256": (
            "sha256:" + disclosure_authority.authority_sha256
        ),
        "cycle_id": disclosure_authority.identity.cycle_id,
        "cohort_policy_sha256": (
            "sha256:" + disclosure_authority.identity.cohort_policy_sha256
        ),
        "eligibility_anchor": (
            disclosure_authority.identity.eligibility_anchor.isoformat()
        ),
        "ssh_public_key_fingerprint": (disclosure_authority.ssh_public_key_fingerprint),
    }
    if clearance_run_card.get("review_authority") != expected_authority:
        raise ResolvedPostRecoveryError(
            "clear-disclosures review authority does not match its receipt"
        )
    _validate_exact_clearance_projection(
        clearance_records=clearance_records,
        reviews_artifact_bytes=reviews_artifact_bytes,
        worksheet=review_worksheet_artifact,
        download_manifest_bytes=download_manifest_artifact_bytes,
        restriction_records=restriction_records,
    )

    return AuthenticatedClearanceLineage(
        clearance_run_card_sha256=_bytes_sha256(clearance_run_card_bytes),
        clearance_artifact_sha256=clearance_sha256,
        reviews_artifact_sha256=expected_sources["reviews"],
        review_receipt_sha256=expected_sources["review_receipt"],
        cohort_policy_artifact_sha256=expected_sources["cohort_policy"],
        restriction_evidence_artifact_sha256=expected_sources["restriction_evidence"],
        review_authority_sha256=_sha256(expected_authority),
        authority=authority,
    )


def _validate_exact_clearance_projection(
    *,
    clearance_records: Sequence[Mapping[str, Any]],
    reviews_artifact_bytes: bytes,
    worksheet: Mapping[str, object],
    download_manifest_bytes: bytes,
    restriction_records: Sequence[Mapping[str, Any]],
) -> None:
    """Rebuild every mutable clearance field from signed, hash-bound inputs."""

    reviews = _index(
        _jsonl_records_from_bytes(reviews_artifact_bytes, "signed reviews"),
        "signed reviews",
    )
    manifest = _index(
        _jsonl_records_from_bytes(download_manifest_bytes, "download manifest"),
        "download manifest",
    )
    raw_documents = worksheet.get("documents")
    if not isinstance(raw_documents, list) or not raw_documents:
        raise ResolvedPostRecoveryError("review worksheet has no document rows")
    typed_documents = cast(list[object], raw_documents)
    documents = _index(
        [
            dict(cast(Mapping[str, Any], row))
            for row in typed_documents
            if isinstance(row, Mapping)
        ],
        "review worksheet",
    )
    if len(documents) != len(typed_documents):
        raise ResolvedPostRecoveryError("review worksheet has invalid document rows")
    clearance = _index(clearance_records, "clearance")
    restrictions = _group_index(restriction_records, "restriction evidence")
    keys = set(reviews)
    if not (
        keys == set(manifest) == set(documents) == set(clearance) == set(restrictions)
    ):
        raise ResolvedPostRecoveryError(
            "signed review, worksheet, manifest, restrictions, and clearance "
            "coverage differ"
        )
    exact_fields = {
        "schema_version",
        "candidate_id",
        "source_document_id",
        "local_path",
        "sha256",
        "byte_count",
        "status",
        "automated_markers",
        "restriction_status",
        "restriction_evidence",
        "reviewer_id",
        "controlled_store_provenance",
        "reviewed_at",
        "free_or_purchased",
    }
    for key in sorted(keys):
        review = reviews[key]
        document = documents[key]
        source = manifest[key]
        row = clearance[key]
        if set(row) != exact_fields:
            raise ResolvedPostRecoveryError(
                f"clearance row has non-canonical fields: {key}"
            )
        markers = cast(object, document.get("automated_markers"))
        evidence = cast(object, document.get("restriction_evidence"))
        if not isinstance(markers, list) or not all(
            isinstance(item, str) and item for item in cast(list[object], markers)
        ):
            raise ResolvedPostRecoveryError(
                f"review worksheet has invalid marker categories: {key}"
            )
        if not isinstance(evidence, list) or not all(
            isinstance(item, str) and item for item in cast(list[object], evidence)
        ):
            raise ResolvedPostRecoveryError(
                f"review worksheet lacks exact restriction projection: {key}"
            )
        digest = document.get("sha256")
        byte_count = document.get("byte_count")
        phase = document.get("free_or_purchased")
        if (
            source.get("sha256") != digest
            or source.get("byte_count") != byte_count
            or source.get("free_or_purchased") != phase
        ):
            raise ResolvedPostRecoveryError(
                f"download manifest differs from signed worksheet: {key}"
            )
        expected: dict[str, object] = {
            "schema_version": SCHEMA_VERSION,
            "candidate_id": key[0],
            "source_document_id": key[1],
            "local_path": source.get("local_path"),
            "sha256": digest,
            "byte_count": byte_count,
            "status": review.get("status"),
            "automated_markers": cast(list[object], markers),
            "restriction_status": document.get("restriction_status"),
            "restriction_evidence": cast(list[object], evidence),
            "reviewer_id": review.get("reviewer_id"),
            "controlled_store_provenance": review.get("controlled_store_provenance"),
            "reviewed_at": review.get("reviewed_at"),
            "free_or_purchased": phase,
        }
        if row != expected:
            raise ResolvedPostRecoveryError(
                f"clearance row differs from authenticated review projection: {key}"
            )


def _bind_internal_verified_provenance_lineage(
    lineage: AuthenticatedClearanceLineage,
    *,
    clearance_records: Sequence[Mapping[str, Any]],
    clearance_artifact_bytes: bytes,
    clearance_run_card: Mapping[str, Any],
    clearance_run_card_bytes: bytes,
    reviews_artifact_bytes: bytes,
    review_receipt_bytes: bytes,
    reviewer_policy_bytes: bytes,
    cohort_policy_artifact_bytes: bytes,
    restriction_records: Sequence[Mapping[str, Any]],
    restriction_artifact_bytes: bytes,
) -> AuthenticatedClearanceLineage:
    """Bind verifier-owned lineage to the exact bytes consumed downstream."""

    if _json_object_from_bytes(
        clearance_run_card_bytes, "provenance clearance run card"
    ) != dict(clearance_run_card):
        raise ResolvedPostRecoveryError(
            "verified provenance run-card bytes changed before downstream use"
        )
    if _jsonl_records_from_bytes(
        clearance_artifact_bytes, "provenance disclosure clearance"
    ) != [dict(record) for record in clearance_records]:
        raise ResolvedPostRecoveryError(
            "verified provenance clearance bytes changed before downstream use"
        )
    if _jsonl_records_from_bytes(
        restriction_artifact_bytes, "provenance restriction evidence"
    ) != [dict(record) for record in restriction_records]:
        raise ResolvedPostRecoveryError(
            "verified provenance restriction bytes changed before downstream use"
        )
    authority = _mapping(
        clearance_run_card.get("clearance_authority"),
        "provenance clearance authority",
    )
    observed = {
        "clearance_run_card_sha256": _bytes_sha256(clearance_run_card_bytes),
        "clearance_artifact_sha256": _bytes_sha256(clearance_artifact_bytes),
        "reviews_artifact_sha256": _bytes_sha256(reviews_artifact_bytes),
        "review_receipt_sha256": _bytes_sha256(review_receipt_bytes),
        "cohort_policy_artifact_sha256": _bytes_sha256(cohort_policy_artifact_bytes),
        "restriction_evidence_artifact_sha256": _bytes_sha256(
            restriction_artifact_bytes
        ),
        "review_authority_sha256": _sha256(authority),
    }
    for field, actual in observed.items():
        if getattr(lineage, field) != actual:
            raise ResolvedPostRecoveryError(
                f"verified provenance {field} changed before downstream use"
            )
    if lineage.authority.review_artifact_sha256 != _bytes_sha256(
        reviews_artifact_bytes
    ) or lineage.authority.reviewer_policy_sha256 != _bytes_sha256(
        reviewer_policy_bytes
    ):
        raise ResolvedPostRecoveryError(
            "verified provenance reviewer inputs changed before downstream use"
        )
    return lineage


def build_resolved_post_recovery_documents(
    *,
    selection_records: Sequence[Mapping[str, Any]],
    purchase_operation_records: Sequence[Mapping[str, Any]],
    download_records: Sequence[Mapping[str, Any]],
    clearance_records: Sequence[Mapping[str, Any]],
    attempt_policy_artifact: Mapping[str, object],
    clearance_artifact_bytes: bytes,
    clearance_run_card: Mapping[str, Any],
    clearance_run_card_bytes: bytes,
    reviews_artifact_bytes: bytes,
    review_receipt_artifact: Mapping[str, object],
    review_receipt_bytes: bytes,
    review_requests_artifact_bytes: bytes,
    review_worksheet_artifact: Mapping[str, object],
    review_worksheet_bytes: bytes,
    reviewer_policy_bytes: bytes,
    disclosure_authority: DisclosureReviewAuthority,
    cohort_policy_artifact_bytes: bytes,
    download_manifest_artifact_bytes: bytes,
    restriction_records: Sequence[Mapping[str, Any]],
    restriction_artifact_bytes: bytes,
    allow_test_service_identity: bool = False,
) -> tuple[dict[str, object], ...]:
    """Build resolved records from fully authenticated legacy review evidence."""

    return build_resolved_post_recovery_documents_with_authenticated_lineage(
        selection_records=selection_records,
        purchase_operation_records=purchase_operation_records,
        download_records=download_records,
        clearance_records=clearance_records,
        attempt_policy_artifact=attempt_policy_artifact,
        clearance_artifact_bytes=clearance_artifact_bytes,
        clearance_run_card=clearance_run_card,
        clearance_run_card_bytes=clearance_run_card_bytes,
        reviews_artifact_bytes=reviews_artifact_bytes,
        review_receipt_artifact=review_receipt_artifact,
        review_receipt_bytes=review_receipt_bytes,
        review_requests_artifact_bytes=review_requests_artifact_bytes,
        review_worksheet_artifact=review_worksheet_artifact,
        review_worksheet_bytes=review_worksheet_bytes,
        reviewer_policy_bytes=reviewer_policy_bytes,
        disclosure_authority=disclosure_authority,
        cohort_policy_artifact_bytes=cohort_policy_artifact_bytes,
        download_manifest_artifact_bytes=download_manifest_artifact_bytes,
        restriction_records=restriction_records,
        restriction_artifact_bytes=restriction_artifact_bytes,
        allow_test_service_identity=allow_test_service_identity,
    )


def _build_resolved_post_recovery_documents_core(
    *,
    selection_records: Sequence[Mapping[str, Any]],
    purchase_operation_records: Sequence[Mapping[str, Any]],
    download_records: Sequence[Mapping[str, Any]],
    clearance_records: Sequence[Mapping[str, Any]],
    attempt_policy_artifact: Mapping[str, object],
    clearance_artifact_bytes: bytes,
    clearance_run_card: Mapping[str, Any],
    clearance_run_card_bytes: bytes,
    reviews_artifact_bytes: bytes,
    review_receipt_artifact: Mapping[str, object],
    review_receipt_bytes: bytes,
    review_requests_artifact_bytes: bytes,
    review_worksheet_artifact: Mapping[str, object],
    review_worksheet_bytes: bytes,
    reviewer_policy_bytes: bytes,
    disclosure_authority: DisclosureReviewAuthority | None,
    cohort_policy_artifact_bytes: bytes,
    download_manifest_artifact_bytes: bytes,
    restriction_records: Sequence[Mapping[str, Any]],
    restriction_artifact_bytes: bytes,
    allow_test_service_identity: bool = False,
    verified_lineage_capability: object | None = None,
    verified_recovery_capability: object | None = None,
    verified_terminal_disposition_capability: object | None = None,
) -> tuple[dict[str, object], ...]:
    """Build exact resolved records for every unknown-origin selected document."""

    recovered_lineages: Mapping[tuple[str, str], Mapping[str, object]] | None = None
    terminal_keys: frozenset[tuple[str, str]] = frozenset()
    if (
        verified_terminal_disposition_capability is not None
        and verified_recovery_capability is None
    ):
        raise ResolvedPostRecoveryError(
            "terminal disposition authority requires recovered-public authority"
        )
    if verified_recovery_capability is not None:
        if verified_lineage_capability is not None:
            raise ResolvedPostRecoveryError(
                "conflicting authenticated clearance capabilities"
            )
        recovered_lineages = _consume_recovered_public_clearance_capability(
            verified_recovery_capability
        )
        if verified_terminal_disposition_capability is not None:
            terminal_keys = _consume_terminal_disposition_capability(
                verified_terminal_disposition_capability
            )
        clearance_lineage = None
    elif verified_lineage_capability is not None:
        clearance_lineage = _bind_internal_verified_provenance_lineage(
            _consume_verified_lineage_capability(verified_lineage_capability),
            clearance_records=clearance_records,
            clearance_artifact_bytes=clearance_artifact_bytes,
            clearance_run_card=clearance_run_card,
            clearance_run_card_bytes=clearance_run_card_bytes,
            reviews_artifact_bytes=reviews_artifact_bytes,
            review_receipt_bytes=review_receipt_bytes,
            reviewer_policy_bytes=reviewer_policy_bytes,
            cohort_policy_artifact_bytes=cohort_policy_artifact_bytes,
            restriction_records=restriction_records,
            restriction_artifact_bytes=restriction_artifact_bytes,
        )
    elif disclosure_authority is None:
        raise ResolvedPostRecoveryError("legacy clearance authority is missing")
    else:
        clearance_lineage = validate_authenticated_clearance_lineage(
            clearance_records=clearance_records,
            clearance_artifact_bytes=clearance_artifact_bytes,
            clearance_run_card=clearance_run_card,
            clearance_run_card_bytes=clearance_run_card_bytes,
            reviews_artifact_bytes=reviews_artifact_bytes,
            review_receipt_artifact=review_receipt_artifact,
            review_receipt_bytes=review_receipt_bytes,
            review_requests_artifact_bytes=review_requests_artifact_bytes,
            review_worksheet_artifact=review_worksheet_artifact,
            review_worksheet_bytes=review_worksheet_bytes,
            reviewer_policy_bytes=reviewer_policy_bytes,
            disclosure_authority=disclosure_authority,
            cohort_policy_artifact_bytes=cohort_policy_artifact_bytes,
            download_manifest_artifact_bytes=download_manifest_artifact_bytes,
            restriction_records=restriction_records,
            restriction_artifact_bytes=restriction_artifact_bytes,
            allow_test_service_identity=allow_test_service_identity,
        )
    policy_sha256, purchase_policy_sha256, attempt_documents = _attempt_documents(
        attempt_policy_artifact
    )
    unknown_selection = _unknown_selection(selection_records)
    if set(attempt_documents) != set(unknown_selection):
        raise ResolvedPostRecoveryError(
            "attempt policy does not exactly cover unknown selected documents"
        )
    operations = _index(purchase_operation_records, "purchase operation")
    downloads = _index(download_records, "download")
    clearances = _index(clearance_records, "clearance")
    restrictions = _group_index(restriction_records, "restriction evidence")
    if not terminal_keys <= set(unknown_selection):
        raise ResolvedPostRecoveryError(
            "terminal-unavailable partition is outside unknown selected documents"
        )
    if terminal_keys - set(operations):
        raise ResolvedPostRecoveryError(
            "purchase operation lacks terminal-unavailable coverage"
        )
    required = set(unknown_selection) - terminal_keys
    if recovered_lineages is not None and set(recovered_lineages) != required:
        raise ResolvedPostRecoveryError(
            "recovered-public capability does not exactly cover recovered documents"
        )
    for label, index in (
        ("purchase operation", operations),
        ("download", downloads),
        ("clearance", clearances),
    ):
        missing = required - set(index)
        if missing:
            raise ResolvedPostRecoveryError(
                f"{label} lacks unknown-origin coverage: {sorted(missing)}"
            )

    output: list[dict[str, object]] = []
    for key in sorted(required):
        candidate_id, document_id = key
        selection_document = unknown_selection[key]
        attempt = attempt_documents[key]
        operation = operations[key]
        download = downloads[key]
        clearance = clearances[key]
        if recovered_lineages is not None:
            raw_recovered_lineage = clearance.get("recovered_public_lineage")
            if (
                not isinstance(raw_recovered_lineage, Mapping)
                or recovered_lineages.get(key) != raw_recovered_lineage
            ):
                raise ResolvedPostRecoveryError(
                    f"recovered-public clearance capability changed: {key}"
                )
        restriction_rows = restrictions[key]
        selection_sha256 = _sha256(selection_document)
        if attempt["selection_document_sha256"] != selection_sha256:
            raise ResolvedPostRecoveryError(
                f"attempt policy selection commitment changed: {key}"
            )
        _validate_operation(
            operation,
            key=key,
            attempt_policy_sha256=policy_sha256,
            selection_document_sha256=selection_sha256,
            expected_purchase_policy_sha256=purchase_policy_sha256,
            verified_recovered_lineage=(
                None if recovered_lineages is None else recovered_lineages.get(key)
            ),
        )
        _validate_download(
            download,
            key=key,
            operation=operation,
            attempt_policy_sha256=policy_sha256,
        )
        _validate_clearance(clearance, key=key, download=download)
        fresh_public = _fresh_public_restriction_record(
            restriction_rows,
            key=key,
            operation=operation,
        )
        _validate_recovered_public_clearance_lineage(
            clearance, operation=operation, fresh_public=fresh_public, key=key
        )
        material = _mapping(operation.get("material_evidence"), "material evidence")
        delivery_authority = _delivery_authority_fields(
            operation,
            key=key,
            expected_purchase_policy_sha256=purchase_policy_sha256,
            verified_recovered_lineage=(
                None if recovered_lineages is None else recovered_lineages.get(key)
            ),
        )
        schema_version = (
            RESOLVED_POST_RECOVERY_SCHEMA_VERSION_V4
            if delivery_authority.get("delivery_authority")
            == "authenticated_direct_courtlistener_queue"
            else (
                RESOLVED_POST_RECOVERY_SCHEMA_VERSION_V3
                if delivery_authority.get("delivery_authority")
                == "authenticated_public_material_recovery"
                else (
                    RESOLVED_POST_RECOVERY_SCHEMA_VERSION_V2
                    if recovered_lineages is not None
                    else RESOLVED_POST_RECOVERY_SCHEMA_VERSION
                )
            )
        )
        record: dict[str, object] = {
            "schema_version": schema_version,
            "candidate_id": candidate_id,
            "source_document_id": document_id,
            "recovery_origin": UNKNOWN_RECOVERY_ORIGIN,
            "attempt_policy_sha256": policy_sha256,
            "selection_document_sha256": selection_sha256,
            "purchase_operation_sha256": _sha256(operation),
            "operation_key": _uuid4(operation.get("operation_key")),
            **delivery_authority,
            "fresh_recap_detail_sha256": _required_sha(
                material.get("provider_detail_sha256"), "fresh RECAP detail"
            ),
            "download_url_sha256": _required_sha(
                material.get("download_url_sha256"), "download URL"
            ),
            "download_record_sha256": _sha256(download),
            "content_sha256": _required_sha(download.get("sha256"), "content"),
            "byte_count": _positive_int(download.get("byte_count"), "byte_count"),
            "clearance_record_sha256": _sha256(clearance),
            "clearance_run_card_sha256": _bytes_sha256(clearance_run_card_bytes),
            "clearance_artifact_sha256": _bytes_sha256(clearance_artifact_bytes),
            "cohort_policy_artifact_sha256": _bytes_sha256(
                cohort_policy_artifact_bytes
            ),
            "restriction_evidence_artifact_sha256": _bytes_sha256(
                restriction_artifact_bytes
            ),
            "restriction_evidence_rows_sha256": _sha256(restriction_rows),
            "fresh_detail_public_evidence_sha256": _sha256(fresh_public),
            "restriction_status": "public",
            "parser_eligible": True,
            "packet_eligible": True,
        }
        if recovered_lineages is not None:
            record.update(
                {
                    "clearance_basis": "provider_free_recovered_public",
                    "recovered_public_lineage": dict(recovered_lineages[key]),
                }
            )
        else:
            assert clearance_lineage is not None
            record.update(
                {
                    "reviews_artifact_sha256": (
                        clearance_lineage.reviews_artifact_sha256
                    ),
                    "review_receipt_sha256": clearance_lineage.review_receipt_sha256,
                    "review_authority_sha256": (
                        clearance_lineage.review_authority_sha256
                    ),
                }
            )
        record["record_sha256"] = _sha256(record)
        output.append(record)
    return tuple(output)


def _build_resolved_post_recovery_documents_with_authenticated_lineage(  # pyright: ignore[reportUnusedFunction]
    *, verified_lineage_capability: object | None = None, **kwargs: Any
) -> tuple[dict[str, object], ...]:
    """Build through the private capability-bearing provenance path."""

    _consume_verified_lineage_capability(verified_lineage_capability)
    return _build_resolved_post_recovery_documents_core(
        **kwargs,
        verified_lineage_capability=verified_lineage_capability,
    )


def _build_resolved_recovered_public(  # pyright: ignore[reportUnusedFunction]
    *,
    verified_recovery_capability: object | None = None,
    verified_terminal_disposition_capability: object | None = None,
    **kwargs: Any,
) -> tuple[dict[str, object], ...]:
    """Build through the verifier-issued recovered-public capability path."""

    if (
        verified_terminal_disposition_capability is not None
        and verified_recovery_capability is None
    ):
        raise ResolvedPostRecoveryError(
            "terminal disposition authority requires recovered-public authority"
        )
    _consume_recovered_public_clearance_capability(verified_recovery_capability)
    return _build_resolved_post_recovery_documents_core(
        **kwargs,
        verified_recovery_capability=verified_recovery_capability,
        verified_terminal_disposition_capability=(
            verified_terminal_disposition_capability
        ),
    )


def build_resolved_post_recovery_documents_with_authenticated_lineage(
    **kwargs: Any,
) -> tuple[dict[str, object], ...]:
    """Reject caller-supplied lineage; retained for fail-closed compatibility."""

    if kwargs.pop("verified_provenance_lineage", None) is not None or (
        "verified_lineage_capability" in kwargs
    ):
        raise ResolvedPostRecoveryError(
            "caller-supplied authenticated clearance lineage is forbidden"
        )
    return _build_resolved_post_recovery_documents_core(**kwargs)


def require_resolved_post_recovery_documents(
    *,
    selection_records: Sequence[Mapping[str, Any]],
    download_records: Sequence[Mapping[str, Any]],
    clearance_records: Sequence[Mapping[str, Any]],
    resolved_records: Sequence[Mapping[str, Any]],
    clearance_artifact_bytes: bytes,
    clearance_run_card: Mapping[str, Any],
    clearance_run_card_bytes: bytes,
    reviews_artifact_bytes: bytes,
    review_receipt_artifact: Mapping[str, object],
    review_receipt_bytes: bytes,
    review_requests_artifact_bytes: bytes,
    review_worksheet_artifact: Mapping[str, object],
    review_worksheet_bytes: bytes,
    reviewer_policy_bytes: bytes,
    disclosure_authority: DisclosureReviewAuthority,
    cohort_policy_artifact_bytes: bytes,
    download_manifest_artifact_bytes: bytes,
    restriction_records: Sequence[Mapping[str, Any]],
    restriction_artifact_bytes: bytes,
    allow_test_service_identity: bool = False,
) -> None:
    """Require resolved records using authenticated legacy review evidence."""

    require_resolved_post_recovery_documents_with_authenticated_lineage(
        selection_records=selection_records,
        download_records=download_records,
        clearance_records=clearance_records,
        resolved_records=resolved_records,
        clearance_artifact_bytes=clearance_artifact_bytes,
        clearance_run_card=clearance_run_card,
        clearance_run_card_bytes=clearance_run_card_bytes,
        reviews_artifact_bytes=reviews_artifact_bytes,
        review_receipt_artifact=review_receipt_artifact,
        review_receipt_bytes=review_receipt_bytes,
        review_requests_artifact_bytes=review_requests_artifact_bytes,
        review_worksheet_artifact=review_worksheet_artifact,
        review_worksheet_bytes=review_worksheet_bytes,
        reviewer_policy_bytes=reviewer_policy_bytes,
        disclosure_authority=disclosure_authority,
        cohort_policy_artifact_bytes=cohort_policy_artifact_bytes,
        download_manifest_artifact_bytes=download_manifest_artifact_bytes,
        restriction_records=restriction_records,
        restriction_artifact_bytes=restriction_artifact_bytes,
        allow_test_service_identity=allow_test_service_identity,
    )


def _require_resolved_post_recovery_documents_core(
    *,
    selection_records: Sequence[Mapping[str, Any]],
    download_records: Sequence[Mapping[str, Any]],
    clearance_records: Sequence[Mapping[str, Any]],
    resolved_records: Sequence[Mapping[str, Any]],
    clearance_artifact_bytes: bytes,
    clearance_run_card: Mapping[str, Any],
    clearance_run_card_bytes: bytes,
    reviews_artifact_bytes: bytes,
    review_receipt_artifact: Mapping[str, object],
    review_receipt_bytes: bytes,
    review_requests_artifact_bytes: bytes,
    review_worksheet_artifact: Mapping[str, object],
    review_worksheet_bytes: bytes,
    reviewer_policy_bytes: bytes,
    disclosure_authority: DisclosureReviewAuthority | None,
    cohort_policy_artifact_bytes: bytes,
    download_manifest_artifact_bytes: bytes,
    restriction_records: Sequence[Mapping[str, Any]],
    restriction_artifact_bytes: bytes,
    allow_test_service_identity: bool = False,
    verified_lineage_capability: object | None = None,
    verified_recovery_capability: object | None = None,
    verified_terminal_disposition_capability: object | None = None,
) -> None:
    """Require exact resolved coverage whenever selection originated unknown."""

    recovered_lineages: Mapping[tuple[str, str], Mapping[str, object]] | None = None
    terminal_keys: frozenset[tuple[str, str]] = frozenset()
    if (
        verified_terminal_disposition_capability is not None
        and verified_recovery_capability is None
    ):
        raise ResolvedPostRecoveryError(
            "terminal disposition authority requires recovered-public authority"
        )
    if verified_recovery_capability is not None:
        if verified_lineage_capability is not None:
            raise ResolvedPostRecoveryError(
                "conflicting authenticated clearance capabilities"
            )
        recovered_lineages = _consume_recovered_public_clearance_capability(
            verified_recovery_capability
        )
        if verified_terminal_disposition_capability is not None:
            terminal_keys = _consume_terminal_disposition_capability(
                verified_terminal_disposition_capability
            )
        lineage = None
    elif verified_lineage_capability is not None:
        lineage = _bind_internal_verified_provenance_lineage(
            _consume_verified_lineage_capability(verified_lineage_capability),
            clearance_records=clearance_records,
            clearance_artifact_bytes=clearance_artifact_bytes,
            clearance_run_card=clearance_run_card,
            clearance_run_card_bytes=clearance_run_card_bytes,
            reviews_artifact_bytes=reviews_artifact_bytes,
            review_receipt_bytes=review_receipt_bytes,
            reviewer_policy_bytes=reviewer_policy_bytes,
            cohort_policy_artifact_bytes=cohort_policy_artifact_bytes,
            restriction_records=restriction_records,
            restriction_artifact_bytes=restriction_artifact_bytes,
        )
    elif disclosure_authority is None:
        raise ResolvedPostRecoveryError("legacy clearance authority is missing")
    else:
        lineage = validate_authenticated_clearance_lineage(
            clearance_records=clearance_records,
            clearance_artifact_bytes=clearance_artifact_bytes,
            clearance_run_card=clearance_run_card,
            clearance_run_card_bytes=clearance_run_card_bytes,
            reviews_artifact_bytes=reviews_artifact_bytes,
            review_receipt_artifact=review_receipt_artifact,
            review_receipt_bytes=review_receipt_bytes,
            review_requests_artifact_bytes=review_requests_artifact_bytes,
            review_worksheet_artifact=review_worksheet_artifact,
            review_worksheet_bytes=review_worksheet_bytes,
            reviewer_policy_bytes=reviewer_policy_bytes,
            disclosure_authority=disclosure_authority,
            cohort_policy_artifact_bytes=cohort_policy_artifact_bytes,
            download_manifest_artifact_bytes=download_manifest_artifact_bytes,
            restriction_records=restriction_records,
            restriction_artifact_bytes=restriction_artifact_bytes,
            allow_test_service_identity=allow_test_service_identity,
        )
    unknown_selection = set(_unknown_selection(selection_records))
    if not terminal_keys <= unknown_selection:
        raise ResolvedPostRecoveryError(
            "terminal-unavailable partition is outside unknown selected documents"
        )
    required = unknown_selection - terminal_keys
    download_unknown = {
        key
        for key, record in _index(download_records, "download").items()
        if record.get("recovery_origin") == UNKNOWN_RECOVERY_ORIGIN
    }
    if terminal_keys & download_unknown:
        raise ResolvedPostRecoveryError(
            "terminal-unavailable partition overlaps recovered download material"
        )
    required |= download_unknown
    resolved = _index(resolved_records, "resolved post-recovery document")
    if set(resolved) != required:
        raise ResolvedPostRecoveryError(
            "resolved post-recovery coverage mismatch; "
            f"missing={sorted(required - set(resolved))}; "
            f"extra={sorted(set(resolved) - required)}"
        )
    downloads = _index(download_records, "download")
    clearances = _index(clearance_records, "clearance")
    restrictions = _group_index(restriction_records, "restriction evidence")
    for key, record in resolved.items():
        _validate_resolved_record(record, key=key)
        download = downloads.get(key)
        clearance = clearances.get(key)
        if download is None or clearance is None:
            raise ResolvedPostRecoveryError(
                f"resolved document lacks download or clearance: {key}"
            )
        if (
            record.get("download_record_sha256") != _sha256(download)
            or record.get("clearance_record_sha256") != _sha256(clearance)
            or record.get("content_sha256") != download.get("sha256")
            or record.get("byte_count") != download.get("byte_count")
        ):
            raise ResolvedPostRecoveryError(f"resolved document lineage changed: {key}")
        _validate_clearance(clearance, key=key, download=download)
        restriction_rows = restrictions.get(key)
        if restriction_rows is None:
            raise ResolvedPostRecoveryError(
                f"resolved document lacks restriction evidence: {key}"
            )
        expected_external = {
            "clearance_run_card_sha256": _bytes_sha256(clearance_run_card_bytes),
            "clearance_artifact_sha256": _bytes_sha256(clearance_artifact_bytes),
            "cohort_policy_artifact_sha256": _bytes_sha256(
                cohort_policy_artifact_bytes
            ),
            "restriction_evidence_artifact_sha256": _bytes_sha256(
                restriction_artifact_bytes
            ),
            "restriction_evidence_rows_sha256": _sha256(restriction_rows),
        }
        if recovered_lineages is not None:
            if record.get(
                "clearance_basis"
            ) != "provider_free_recovered_public" or not (
                _recovered_lineage_matches_record(record, recovered_lineages.get(key))
            ):
                raise ResolvedPostRecoveryError(
                    f"resolved recovered-public lineage changed: {key}"
                )
        else:
            assert lineage is not None
            expected_external.update(
                {
                    "reviews_artifact_sha256": lineage.reviews_artifact_sha256,
                    "review_receipt_sha256": lineage.review_receipt_sha256,
                    "review_authority_sha256": lineage.review_authority_sha256,
                }
            )
        if any(record.get(name) != value for name, value in expected_external.items()):
            raise ResolvedPostRecoveryError(
                f"resolved document external lineage changed: {key}"
            )
        fresh_public = _fresh_public_restriction_record_from_resolved(
            restriction_rows,
            key=key,
            resolved_record=record,
        )
        if record.get("fresh_detail_public_evidence_sha256") != _sha256(fresh_public):
            raise ResolvedPostRecoveryError(
                f"resolved fresh-detail public proof changed: {key}"
            )


def _require_resolved_post_recovery_documents_with_authenticated_lineage(  # pyright: ignore[reportUnusedFunction]
    *, verified_lineage_capability: object | None = None, **kwargs: Any
) -> None:
    """Require lineage through the private capability-bearing provenance path."""

    _consume_verified_lineage_capability(verified_lineage_capability)
    _require_resolved_post_recovery_documents_core(
        **kwargs,
        verified_lineage_capability=verified_lineage_capability,
    )


def _require_resolved_recovered_public(  # pyright: ignore[reportUnusedFunction]
    *,
    verified_recovery_capability: object | None = None,
    verified_terminal_disposition_capability: object | None = None,
    **kwargs: Any,
) -> None:
    """Require resolved rows through recovered-public verifier authority."""

    if (
        verified_terminal_disposition_capability is not None
        and verified_recovery_capability is None
    ):
        raise ResolvedPostRecoveryError(
            "terminal disposition authority requires recovered-public authority"
        )
    _consume_recovered_public_clearance_capability(verified_recovery_capability)
    _require_resolved_post_recovery_documents_core(
        **kwargs,
        verified_recovery_capability=verified_recovery_capability,
        verified_terminal_disposition_capability=(
            verified_terminal_disposition_capability
        ),
    )


def require_resolved_post_recovery_documents_with_authenticated_lineage(
    **kwargs: Any,
) -> None:
    """Reject caller-supplied lineage; retained for fail-closed compatibility."""

    if kwargs.pop("verified_provenance_lineage", None) is not None or (
        "verified_lineage_capability" in kwargs
    ):
        raise ResolvedPostRecoveryError(
            "caller-supplied authenticated clearance lineage is forbidden"
        )
    _require_resolved_post_recovery_documents_core(**kwargs)


def require_resolved_post_recovery_parse_requests(
    *,
    selection_records: Sequence[Mapping[str, Any]],
    request_records: Sequence[Mapping[str, Any]],
    resolved_records: Sequence[Mapping[str, Any]],
) -> None:
    """Bind parser requests to exact resolved records for unknown origins."""

    _require_resolved_post_recovery_parse_requests_core(
        selection_records=selection_records,
        request_records=request_records,
        resolved_records=resolved_records,
        recovered_lineages=None,
    )


def _require_resolved_recovered_public_parse_requests(  # pyright: ignore[reportUnusedFunction]
    *,
    selection_records: Sequence[Mapping[str, Any]],
    request_records: Sequence[Mapping[str, Any]],
    resolved_records: Sequence[Mapping[str, Any]],
    verified_recovery_capability: object | None = None,
    verified_terminal_disposition_capability: object | None = None,
) -> None:
    """Bind parser requests through recovered-public verifier authority."""

    recovered_lineages = _consume_recovered_public_clearance_capability(
        verified_recovery_capability
    )
    terminal_keys: frozenset[tuple[str, str]] = (
        _consume_terminal_disposition_capability(
            verified_terminal_disposition_capability
        )
        if verified_terminal_disposition_capability is not None
        else frozenset()
    )
    _require_resolved_post_recovery_parse_requests_core(
        selection_records=selection_records,
        request_records=request_records,
        resolved_records=resolved_records,
        recovered_lineages=recovered_lineages,
        terminal_keys=terminal_keys,
    )


def _require_resolved_post_recovery_parse_requests_core(
    *,
    selection_records: Sequence[Mapping[str, Any]],
    request_records: Sequence[Mapping[str, Any]],
    resolved_records: Sequence[Mapping[str, Any]],
    recovered_lineages: Mapping[tuple[str, str], Mapping[str, object]] | None,
    terminal_keys: frozenset[tuple[str, str]] = frozenset(),
) -> None:
    """Bind parser requests with optional verifier-owned recovered lineage."""

    requests = _index(request_records, "parse request")
    unknown_selection = set(_unknown_selection(selection_records))
    if not terminal_keys <= unknown_selection:
        raise ResolvedPostRecoveryError(
            "terminal-unavailable partition is outside unknown selected documents"
        )
    if terminal_keys & set(requests):
        raise ResolvedPostRecoveryError(
            "terminal-unavailable partition overlaps parser requests"
        )
    required = unknown_selection - terminal_keys
    required.update(
        key
        for key, request in requests.items()
        if request.get("recovery_origin") == UNKNOWN_RECOVERY_ORIGIN
    )
    resolved = _index(resolved_records, "resolved post-recovery document")
    if set(resolved) != required:
        raise ResolvedPostRecoveryError(
            "resolved post-recovery parse coverage mismatch"
        )
    for key in required:
        record = resolved[key]
        request = requests.get(key)
        if request is None:
            raise ResolvedPostRecoveryError(
                f"resolved unknown document lacks parse request: {key}"
            )
        if record.get(
            "schema_version"
        ) == RESOLVED_POST_RECOVERY_SCHEMA_VERSION_V4 and (
            recovered_lineages is None
            or not _recovered_lineage_matches_record(
                record, recovered_lineages.get(key)
            )
        ):
            raise ResolvedPostRecoveryError(
                "V4 resolved records require verifier-issued recovery authority"
            )
        _validate_resolved_record(record, key=key)
        if (
            request.get("expected_sha256") != record.get("content_sha256")
            or request.get("expected_byte_count") != record.get("byte_count")
            or request.get("resolved_post_recovery_sha256")
            != record.get("record_sha256")
        ):
            raise ResolvedPostRecoveryError(
                f"parse request does not bind resolved unknown material: {key}"
            )


def require_resolved_post_recovery_operation_bindings(
    *,
    purchase_operation_records: Sequence[Mapping[str, Any]],
    resolved_records: Sequence[Mapping[str, Any]],
    expected_purchase_policy_sha256: str,
) -> None:
    """Verify pre-clear, post-clear, and partially-cleared crash replays exactly."""

    _require_resolved_post_recovery_operation_bindings_core(
        purchase_operation_records=purchase_operation_records,
        resolved_records=resolved_records,
        expected_purchase_policy_sha256=expected_purchase_policy_sha256,
        recovered_lineages=None,
    )


def _require_resolved_recovered_public_operation_bindings(  # pyright: ignore[reportUnusedFunction]
    *,
    purchase_operation_records: Sequence[Mapping[str, Any]],
    resolved_records: Sequence[Mapping[str, Any]],
    expected_purchase_policy_sha256: str,
    verified_recovery_capability: object | None = None,
    verified_terminal_disposition_capability: object | None = None,
) -> None:
    """Verify operation bindings through recovered-public verifier authority."""

    recovered_lineages = _consume_recovered_public_clearance_capability(
        verified_recovery_capability
    )
    terminal_keys: frozenset[tuple[str, str]] = frozenset()
    if verified_terminal_disposition_capability is not None:
        terminal_keys = _consume_terminal_disposition_capability(
            verified_terminal_disposition_capability
        )
    _require_resolved_post_recovery_operation_bindings_core(
        purchase_operation_records=purchase_operation_records,
        resolved_records=resolved_records,
        expected_purchase_policy_sha256=expected_purchase_policy_sha256,
        recovered_lineages=recovered_lineages,
        terminal_keys=terminal_keys,
    )


def _is_legacy_direct_queue_record(record: Mapping[str, object]) -> bool:
    return (
        record.get("schema_version") == RESOLVED_POST_RECOVERY_SCHEMA_VERSION_V4
        and record.get("delivery_authority")
        == "authenticated_direct_courtlistener_queue_recovery"
        and set(record) == set(_LEGACY_DIRECT_QUEUE_RESOLVED_FIELDS)
    )


def _recovered_lineage_matches_record(
    record: Mapping[str, object],
    authenticated_lineage: Mapping[str, object] | None,
) -> bool:
    if authenticated_lineage is None:
        return False
    expected: Mapping[str, object] = authenticated_lineage
    if _is_legacy_direct_queue_record(record):
        if not isinstance(
            authenticated_lineage.get("direct_queue_delivery_authority"), Mapping
        ):
            return False
        expected = {
            name: value
            for name, value in authenticated_lineage.items()
            if name != "direct_queue_delivery_authority"
        }
    return record.get("recovered_public_lineage") == expected


def _require_resolved_post_recovery_operation_bindings_core(
    *,
    purchase_operation_records: Sequence[Mapping[str, Any]],
    resolved_records: Sequence[Mapping[str, Any]],
    expected_purchase_policy_sha256: str,
    recovered_lineages: Mapping[tuple[str, str], Mapping[str, object]] | None,
    terminal_keys: frozenset[tuple[str, str]] = frozenset(),
) -> None:
    """Verify canonical operation state with optional verifier-owned lineage."""

    operations = _index(purchase_operation_records, "purchase operation")
    resolved = _index(resolved_records, "resolved post-recovery document")
    if terminal_keys & set(resolved):
        raise ResolvedPostRecoveryError(
            "terminal-unavailable partition overlaps resolved operation material"
        )
    if set(resolved) - set(operations):
        raise ResolvedPostRecoveryError(
            "canonical purchase journal lacks resolved operation coverage"
        )
    for key, record in resolved.items():
        operation = operations[key]
        _validate_resolved_record(record, key=key)
        legacy_direct = _is_legacy_direct_queue_record(record)
        if record.get(
            "schema_version"
        ) == RESOLVED_POST_RECOVERY_SCHEMA_VERSION_V4 and (
            recovered_lineages is None
            or not _recovered_lineage_matches_record(
                record, recovered_lineages.get(key)
            )
        ):
            raise ResolvedPostRecoveryError(
                "V4 resolved records require verifier-issued recovery authority"
            )
        state = operation.get("material_state")
        if state not in {"recovered_pending_clearance", "cleared_public"}:
            raise ResolvedPostRecoveryError(
                f"canonical purchase material state is not resolvable: {key}"
            )
        material = _mapping(operation.get("material_evidence"), "material evidence")
        preclear = dict(operation)
        preclear["material_state"] = "recovered_pending_clearance"
        preclear_material = dict(material)
        preclear_material.pop("clearance_record_sha256", None)
        preclear["material_evidence"] = preclear_material
        preclear["resolved_document_sha256"] = None
        expected = {
            "candidate_id": operation.get("candidate_id"),
            "source_document_id": operation.get("source_document_id"),
            "operation_key": operation.get("operation_key"),
            "attempt_policy_sha256": operation.get("attempt_policy_sha256"),
            "selection_document_sha256": operation.get("attempt_document_sha256"),
            "fresh_recap_detail_sha256": material.get("provider_detail_sha256"),
            "download_url_sha256": material.get("download_url_sha256"),
            "content_sha256": material.get("content_sha256"),
            "byte_count": material.get("byte_count"),
            **(
                _legacy_direct_queue_delivery_authority_fields(
                    preclear,
                    key=key,
                    expected_purchase_policy_sha256=expected_purchase_policy_sha256,
                    verified_recovered_lineage=(
                        None
                        if recovered_lineages is None
                        else recovered_lineages.get(key)
                    ),
                )
                if legacy_direct
                else _delivery_authority_fields(
                    preclear,
                    key=key,
                    expected_purchase_policy_sha256=expected_purchase_policy_sha256,
                    verified_recovered_lineage=(
                        cast(
                            Mapping[str, object],
                            record.get("recovered_public_lineage"),
                        )
                        if isinstance(record.get("recovered_public_lineage"), Mapping)
                        else None
                    ),
                )
            ),
        }
        if any(record.get(name) != value for name, value in expected.items()):
            raise ResolvedPostRecoveryError(
                f"resolved record differs from canonical purchase journal: {key}"
            )
        if record.get("purchase_operation_sha256") != _sha256(preclear):
            raise ResolvedPostRecoveryError(
                f"resolved purchase operation commitment changed: {key}"
            )
        if state == "cleared_public" and (
            operation.get("resolved_document_sha256") != record.get("record_sha256")
            or material.get("clearance_record_sha256")
            != record.get("clearance_record_sha256")
        ):
            raise ResolvedPostRecoveryError(
                f"canonical purchase journal clearance binding changed: {key}"
            )


def write_resolved_post_recovery_documents(
    path: str | Path, records: Sequence[Mapping[str, object]]
) -> Path:
    """Atomically publish canonical JSONL and refuse changed replays."""

    for record in records:
        _validate_resolved_record(record, key=_key(record))
    payload = b"".join(
        (json.dumps(dict(record), sort_keys=True, separators=(",", ":")) + "\n").encode(
            "utf-8"
        )
        for record in records
    )
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink():
        raise ResolvedPostRecoveryError("resolved output is a symlink")
    if target.exists():
        metadata = target.stat(follow_symlinks=False)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise ResolvedPostRecoveryError(
                "resolved output must be a singly linked regular file"
            )
        if target.read_bytes() != payload:
            raise ResolvedPostRecoveryError(
                "refusing to overwrite different resolved post-recovery bytes"
            )
        return target
    descriptor, temporary_name = tempfile.mkstemp(
        dir=target.parent, prefix=f".{target.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, target)
        directory = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except FileExistsError:
        if target.read_bytes() != payload:
            raise ResolvedPostRecoveryError(
                "resolved output was concurrently created with different bytes"
            ) from None
    finally:
        temporary.unlink(missing_ok=True)
    return target


def _unknown_selection(
    records: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, str], Mapping[str, Any]]:
    output: dict[tuple[str, str], Mapping[str, Any]] = {}
    for selection in records:
        candidate_id = _required_text(selection.get("candidate_id"), "candidate_id")
        documents = selection.get("documents")
        if isinstance(documents, (str, bytes)) or not isinstance(documents, Sequence):
            raise ResolvedPostRecoveryError("selection documents must be a list")
        for item in cast(Sequence[object], documents):
            if not isinstance(item, Mapping):
                raise ResolvedPostRecoveryError("selected document must be an object")
            document = cast(Mapping[str, Any], item)
            key = (
                candidate_id,
                _required_text(
                    document.get("source_document_id"), "source_document_id"
                ),
            )
            paid_recovery = document.get("requires_paid_recovery") is True
            unknown = paid_recovery and (
                document.get("redaction_or_seal_status") != "public"
                or document.get("is_sealed") is not False
                or document.get("is_private") is not False
            )
            if unknown:
                if key in output:
                    raise ResolvedPostRecoveryError(
                        f"duplicate unknown selected document: {key}"
                    )
                output[key] = document
    return output


def _attempt_documents(
    artifact: Mapping[str, object],
) -> tuple[str, str, dict[tuple[str, str], Mapping[str, str]]]:
    if artifact.get("schema_version") != RECAP_FETCH_ATTEMPT_POLICY_VERSION:
        raise ResolvedPostRecoveryError("attempt policy schema is invalid")
    policy = _mapping(artifact.get("policy"), "attempt policy")
    policy_sha256 = _required_sha(artifact.get("policy_sha256"), "attempt policy")
    if _sha256(policy) != policy_sha256:
        raise ResolvedPostRecoveryError("attempt policy hash is invalid")
    if policy.get("authority") != BOUNDED_FETCH_ATTEMPT_AUTHORITY:
        raise ResolvedPostRecoveryError("attempt policy authority is invalid")
    purchase_policy_sha256 = _required_sha(
        policy.get("purchase_policy_sha256"), "purchase policy"
    )
    raw_documents = policy.get("allowed_documents")
    if not isinstance(raw_documents, list):
        raise ResolvedPostRecoveryError("attempt policy documents must be a list")
    output: dict[tuple[str, str], Mapping[str, str]] = {}
    for item in cast(list[object], raw_documents):
        if not isinstance(item, Mapping):
            raise ResolvedPostRecoveryError("attempt document must be an object")
        row = cast(Mapping[str, Any], item)
        if (
            set(row)
            != {
                "case_id",
                "recap_document",
                "evidence_class",
                "selection_document_sha256",
            }
            or row.get("evidence_class") != "unknown_status_quarantine"
        ):
            raise ResolvedPostRecoveryError("attempt document fields are invalid")
        key = (
            _required_text(row.get("case_id"), "case_id"),
            _required_text(row.get("recap_document"), "recap_document"),
        )
        if key in output:
            raise ResolvedPostRecoveryError(f"duplicate attempt document: {key}")
        output[key] = {
            "selection_document_sha256": _required_sha(
                row.get("selection_document_sha256"), "selection document"
            )
        }
    return policy_sha256, purchase_policy_sha256, output


def _validate_operation(
    operation: Mapping[str, Any],
    *,
    key: tuple[str, str],
    attempt_policy_sha256: str,
    selection_document_sha256: str,
    expected_purchase_policy_sha256: str,
    verified_recovered_lineage: Mapping[str, object] | None = None,
) -> None:
    if (
        operation.get("material_authority") != UNKNOWN_RECOVERY_ORIGIN
        or operation.get("attempt_policy_sha256") != attempt_policy_sha256
        or operation.get("attempt_document_sha256") != selection_document_sha256
        or operation.get("material_state") != "recovered_pending_clearance"
        or operation.get("candidate_id") != key[0]
        or operation.get("source_document_id") != key[1]
    ):
        raise ResolvedPostRecoveryError(
            f"purchase operation lacks recovered quarantine lineage: {key}"
        )
    _uuid4(operation.get("operation_key"))
    material = _mapping(operation.get("material_evidence"), "material evidence")
    for field in (
        "provider_detail_sha256",
        "download_url_sha256",
        "content_sha256",
    ):
        _required_sha(material.get(field), field)
    _positive_int(material.get("byte_count"), "byte_count")
    _delivery_authority_fields(
        operation,
        key=key,
        expected_purchase_policy_sha256=expected_purchase_policy_sha256,
        verified_recovered_lineage=verified_recovered_lineage,
    )


def _terminal_delivery_receipt(
    operation: Mapping[str, Any], *, key: tuple[str, str]
) -> Mapping[str, Any]:
    response = _mapping(operation.get("response"), "purchase response")
    history = response.get("broker_receipts")
    if not isinstance(history, list):
        raise ResolvedPostRecoveryError(f"purchase lacks broker receipt: {key}")
    receipts: list[Mapping[str, Any]] = []
    immutable_identity: tuple[object, ...] | None = None
    prior_updated_at: str | None = None
    for item_raw in cast(list[object], history):
        if not isinstance(item_raw, Mapping):
            raise ResolvedPostRecoveryError(
                f"purchase broker receipt history is invalid: {key}"
            )
        item = cast(Mapping[str, Any], item_raw)
        if set(item) != {"sha256", "receipt"}:
            raise ResolvedPostRecoveryError(
                f"purchase broker receipt history is invalid: {key}"
            )
        raw_receipt: object = item.get("receipt")
        if not isinstance(raw_receipt, Mapping) or item.get("sha256") != _sha256(
            cast(Mapping[str, object], raw_receipt)
        ):
            raise ResolvedPostRecoveryError(
                f"purchase broker receipt hash is invalid: {key}"
            )
        try:
            receipt = validate_broker_receipt(cast(Mapping[str, Any], raw_receipt))
        except BrokerOutcomeUnknown as exc:
            raise ResolvedPostRecoveryError(
                f"purchase broker receipt is invalid: {key}"
            ) from exc
        updated_at = _required_text(receipt.get("updated_at"), "receipt updated_at")
        if prior_updated_at is not None and updated_at < prior_updated_at:
            raise ResolvedPostRecoveryError(
                f"purchase broker receipt history is not chronological: {key}"
            )
        prior_updated_at = updated_at
        identity = tuple(
            receipt.get(field)
            for field in (
                "operation_key",
                "reservation_id",
                "cycle_id",
                "purchase_policy_sha256",
                "recap_document",
                "case_id",
                "client_code",
                "reservation_usd",
            )
        )
        if immutable_identity is None:
            immutable_identity = identity
        elif identity != immutable_identity:
            raise ResolvedPostRecoveryError(
                f"purchase broker receipt identity changed: {key}"
            )
        receipts.append(receipt)
    if not receipts:
        raise ResolvedPostRecoveryError(
            f"purchase lacks matching delivery receipt: {key}"
        )
    terminal = receipts[-1]
    if not (
        terminal.get("state") in {"delivered_but_unreconciled", "confirmed"}
        and terminal.get("operation_key") == operation.get("operation_key")
        and terminal.get("case_id") == key[0]
        and terminal.get("recap_document") == key[1]
    ):
        raise ResolvedPostRecoveryError(
            f"purchase broker receipt terminal state is not delivery: {key}"
        )
    return terminal


def _verified_direct_queue_delivery_authority(
    operation: Mapping[str, Any],
    *,
    key: tuple[str, str],
    expected_purchase_policy_sha256: str,
    verified_recovered_lineage: Mapping[str, object] | None,
) -> dict[str, object] | None:
    """Rebuild a direct queued proof only from verifier-issued recovery lineage."""

    if verified_recovered_lineage is None:
        return None
    raw_authority = verified_recovered_lineage.get("direct_queue_delivery_authority")
    if raw_authority is None:
        return None
    if not isinstance(raw_authority, Mapping):
        raise ResolvedPostRecoveryError(
            f"direct queue delivery authority is invalid: {key}"
        )
    response = _mapping(operation.get("response"), "purchase response")
    material = _mapping(operation.get("material_evidence"), "material evidence")
    operation_key = _uuid4(operation.get("operation_key"))
    base_response_fields = {
        "source_provider",
        "reservation_usd",
        "queue_id",
        "reservation_id",
    }
    allowed_response_fields = base_response_fields | {
        "courtlistener_url_commitment_correction"
    }
    queue_id = response.get("queue_id")
    reservation_usd = response.get("reservation_usd")
    purchase_policy_sha256 = _required_sha(
        expected_purchase_policy_sha256, "expected purchase policy"
    )
    if (
        operation.get("status") != "queued"
        or operation.get("actual_usd") is not None
        or operation.get("reconciliation") is not None
        or operation.get("error") is not None
        or response.get("source_provider") != "courtlistener.recap-fetch+pacer"
        or (
            set(response) != base_response_fields
            and set(response) != allowed_response_fields
        )
        or "broker_receipts" in response
        or not isinstance(queue_id, str)
        or re.fullmatch(r"[1-9][0-9]*", queue_id) is None
        or response.get("reservation_id") != f"direct:{operation_key}"
        or not isinstance(reservation_usd, str)
        or re.fullmatch(r"(?:0|[1-9][0-9]*)\.[0-9]{2}", reservation_usd) is None
        or operation.get("reservation_usd") != reservation_usd
        or verified_recovered_lineage.get("purchase_operation_key") != operation_key
        or verified_recovered_lineage.get("purchase_operation_sha256")
        != _sha256(operation)
    ):
        raise ResolvedPostRecoveryError(
            f"direct queue delivery authority conflicts with purchase: {key}"
        )
    correction = response.get("courtlistener_url_commitment_correction")
    if correction is not None and not isinstance(correction, Mapping):
        raise ResolvedPostRecoveryError(
            f"direct queue delivery correction is invalid: {key}"
        )
    authority: dict[str, object] = {
        "schema_version": (
            "legalforecast.direct_courtlistener_queue_delivery_authority.v1"
        ),
        "source_provider": "courtlistener.recap-fetch+pacer",
        "purchase_status": "queued",
        "operation_key": operation_key,
        "queue_id": queue_id,
        "reservation_id": f"direct:{operation_key}",
        "reservation_usd": reservation_usd,
        "queue_response_sha256": _required_sha(
            material.get("queue_response_sha256"), "queue response"
        ),
        "purchase_policy_sha256": purchase_policy_sha256,
        "purchase_operation_sha256": _sha256(operation),
        "purchase_response_sha256": _sha256(response),
        "recovery_run_card_sha256": _required_sha(
            verified_recovered_lineage.get("recovery_run_card_sha256"),
            "recovery run card",
        ),
        "recovery_manifest_sha256": _required_sha(
            verified_recovered_lineage.get("recovery_manifest_sha256"),
            "recovery manifest",
        ),
        "recovery_restriction_evidence_sha256": _required_sha(
            verified_recovered_lineage.get("recovery_restriction_evidence_sha256"),
            "recovery restriction evidence",
        ),
        "purchase_state_sha256": _required_sha(
            verified_recovered_lineage.get("purchase_state_sha256"),
            "purchase state",
        ),
    }
    if dict(cast(Mapping[str, object], raw_authority)) != authority:
        raise ResolvedPostRecoveryError(
            f"direct queue delivery authority changed after verification: {key}"
        )
    return authority


def _legacy_direct_queue_delivery_authority_fields(
    operation: Mapping[str, Any],
    *,
    key: tuple[str, str],
    expected_purchase_policy_sha256: str,
    verified_recovered_lineage: Mapping[str, object] | None,
) -> dict[str, object]:
    """Revalidate and reproduce only the frozen pre-#512 v4 projection."""

    authority = _verified_direct_queue_delivery_authority(
        operation,
        key=key,
        expected_purchase_policy_sha256=expected_purchase_policy_sha256,
        verified_recovered_lineage=verified_recovered_lineage,
    )
    if authority is None:
        raise ResolvedPostRecoveryError(
            f"legacy direct queue delivery lacks verified authority: {key}"
        )
    material = _mapping(operation.get("material_evidence"), "material evidence")
    return {
        "delivery_authority": "authenticated_direct_courtlistener_queue_recovery",
        "purchase_policy_sha256": expected_purchase_policy_sha256,
        "queue_response_sha256": _required_sha(
            material.get("queue_response_sha256"), "queue response"
        ),
    }


def _delivery_authority_fields(
    operation: Mapping[str, Any],
    *,
    key: tuple[str, str],
    expected_purchase_policy_sha256: str,
    verified_recovered_lineage: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Return one exact delivery authority without synthesizing broker evidence."""

    material = _mapping(operation.get("material_evidence"), "material evidence")
    raw_public_recovery = operation.get("public_material_recovery")
    if raw_public_recovery is None:
        response = _mapping(operation.get("response"), "purchase response")
        reservation_id = response.get("reservation_id")
        claims_direct_delivery = isinstance(
            reservation_id, str
        ) and reservation_id.startswith("direct:")
        direct_authority = _verified_direct_queue_delivery_authority(
            operation,
            key=key,
            expected_purchase_policy_sha256=expected_purchase_policy_sha256,
            verified_recovered_lineage=verified_recovered_lineage,
        )
        if direct_authority is not None:
            return {
                "delivery_authority": "authenticated_direct_courtlistener_queue",
                "purchase_policy_sha256": expected_purchase_policy_sha256,
                "direct_queue_delivery_authority": direct_authority,
            }
        if claims_direct_delivery:
            raise ResolvedPostRecoveryError(
                f"direct queue delivery lacks verified authority: {key}"
            )
        receipt = _terminal_delivery_receipt(operation, key=key)
        purchase_policy_sha256 = _required_sha(
            receipt.get("purchase_policy_sha256"), "purchase policy"
        )
        if purchase_policy_sha256 != _required_sha(
            expected_purchase_policy_sha256, "expected purchase policy"
        ):
            raise ResolvedPostRecoveryError(
                f"purchase policy differs from attempt authority: {key}"
            )
        return {
            "purchase_policy_sha256": purchase_policy_sha256,
            "broker_receipt_sha256": _sha256(receipt),
            "broker_receipt_state": _required_text(receipt.get("state"), "state"),
            "queue_response_sha256": _required_sha(
                material.get("queue_response_sha256"), "queue response"
            ),
        }
    if not isinstance(raw_public_recovery, Mapping):
        raise ResolvedPostRecoveryError(
            f"public material recovery authority is invalid: {key}"
        )
    recovery = cast(Mapping[str, object], raw_public_recovery)
    purchase_policy_sha256 = _required_sha(
        recovery.get("purchase_policy_sha256"), "purchase policy"
    )
    if purchase_policy_sha256 != _required_sha(
        expected_purchase_policy_sha256, "expected purchase policy"
    ):
        raise ResolvedPostRecoveryError(
            f"purchase policy differs from attempt authority: {key}"
        )
    # Recovery authenticates material availability at the time it was recorded;
    # later billing settlement does not invalidate that delivery authority. Keep
    # these accepted purchase states aligned with the journal-side validator.
    try:
        validate_unknown_public_recovery_evidence(
            recovery,
            operation,
            candidate_id=key[0],
            document_id=key[1],
            purchase_policy_sha256=expected_purchase_policy_sha256,
        )
    except CaseDevPurchaseLedgerError as exc:
        raise ResolvedPostRecoveryError(
            f"public material recovery authority conflicts with purchase: {key}"
        ) from exc
    return {
        "delivery_authority": "authenticated_public_material_recovery",
        "purchase_policy_sha256": purchase_policy_sha256,
        "public_material_recovery_sha256": _sha256(recovery),
    }


def _validate_download(
    download: Mapping[str, Any],
    *,
    key: tuple[str, str],
    operation: Mapping[str, Any],
    attempt_policy_sha256: str,
) -> None:
    material = _mapping(operation.get("material_evidence"), "material evidence")
    if (
        download.get("recovery_origin") != UNKNOWN_RECOVERY_ORIGIN
        or download.get("attempt_policy_sha256") != attempt_policy_sha256
        or download.get("purchase_operation_key") != operation.get("operation_key")
        or download.get("sha256") != material.get("content_sha256")
        or download.get("byte_count") != material.get("byte_count")
    ):
        raise ResolvedPostRecoveryError(
            f"download does not bind quarantined purchase material: {key}"
        )


def _validate_clearance(
    clearance: Mapping[str, Any],
    *,
    key: tuple[str, str],
    download: Mapping[str, Any],
) -> None:
    if (
        clearance.get("schema_version") != SCHEMA_VERSION
        or clearance.get("status") != "cleared"
        or clearance.get("restriction_status") != "public"
        or clearance.get("sha256") != download.get("sha256")
        or clearance.get("byte_count") != download.get("byte_count")
    ):
        raise ResolvedPostRecoveryError(
            f"download lacks authenticated public disclosure clearance: {key}"
        )
    try:
        require_clearance_policy(clearance, key=key, label="resolved document")
    except DisclosureClearanceError as exc:
        raise ResolvedPostRecoveryError(str(exc)) from exc


def _validate_recovered_public_clearance_lineage(
    clearance: Mapping[str, Any],
    *,
    operation: Mapping[str, Any],
    fresh_public: Mapping[str, Any],
    key: tuple[str, str],
) -> None:
    """Bind the recovered-public clearance row to purchase and fresh detail."""

    if clearance.get("clearance_basis") != "provider_free_recovered_public":
        return
    raw_lineage = clearance.get("recovered_public_lineage")
    if not isinstance(raw_lineage, Mapping):
        raise ResolvedPostRecoveryError(
            f"recovered-public clearance lacks lineage: {key}"
        )
    lineage = cast(Mapping[str, object], raw_lineage)
    material = _mapping(operation.get("material_evidence"), "material evidence")
    expected = {
        "candidate_id": key[0],
        "source_document_id": key[1],
        "purchase_operation_sha256": _sha256(operation),
        "purchase_operation_key": operation.get("operation_key"),
        "fresh_recap_detail_sha256": material.get("provider_detail_sha256"),
    }
    if any(lineage.get(field) != value for field, value in expected.items()):
        raise ResolvedPostRecoveryError(
            f"recovered-public clearance purchase lineage changed: {key}"
        )
    if fresh_public.get("fresh_recap_detail_sha256") != lineage.get(
        "fresh_recap_detail_sha256"
    ):
        raise ResolvedPostRecoveryError(
            f"recovered-public clearance fresh detail changed: {key}"
        )


def _is_fresh_public_restriction_evidence(
    value: object, *, is_sealed: bool | None
) -> bool:
    expected = (
        FRESH_PUBLIC_RESTRICTION_EVIDENCE
        if is_sealed is False
        else FRESH_PUBLIC_UNKNOWN_SEAL_EVIDENCE
    )
    return (
        isinstance(value, Sequence)
        and not isinstance(value, (str, bytes))
        and tuple(cast(Sequence[object], value)) == expected
    )


def _is_false_or_none(value: object) -> bool:
    return value is False or value is None


def _fresh_public_restriction_record(
    records: Sequence[Mapping[str, Any]],
    *,
    key: tuple[str, str],
    operation: Mapping[str, Any],
) -> Mapping[str, Any]:
    material = _mapping(operation.get("material_evidence"), "material evidence")
    matches = [
        record
        for record in records
        if record.get("schema_version") == FRESH_PUBLIC_RESTRICTION_SCHEMA_VERSION
        and record.get("candidate_id") == key[0]
        and record.get("source_document_id") == key[1]
        and record.get("source_provider") == "courtlistener_recap_fetch_fresh_detail"
        and record.get("fresh_recap_detail_sha256")
        == material.get("provider_detail_sha256")
        and record.get("is_available") is True
        and _is_false_or_none(record.get("is_sealed"))
        and _is_false_or_none(record.get("is_private"))
        and record.get("redaction_or_seal_status") == "public"
        and record.get("restriction_status") == "public"
        and _is_fresh_public_restriction_evidence(
            record.get("restriction_evidence"),
            is_sealed=cast(bool | None, record.get("is_sealed")),
        )
    ]
    if len(matches) != 1:
        raise ResolvedPostRecoveryError(
            f"unknown-origin document lacks exact fresh-detail public proof: {key}"
        )
    return matches[0]


def _fresh_public_restriction_record_from_resolved(
    records: Sequence[Mapping[str, Any]],
    *,
    key: tuple[str, str],
    resolved_record: Mapping[str, Any],
) -> Mapping[str, Any]:
    matches = [
        record
        for record in records
        if record.get("schema_version") == FRESH_PUBLIC_RESTRICTION_SCHEMA_VERSION
        and record.get("candidate_id") == key[0]
        and record.get("source_document_id") == key[1]
        and record.get("source_provider") == "courtlistener_recap_fetch_fresh_detail"
        and record.get("fresh_recap_detail_sha256")
        == resolved_record.get("fresh_recap_detail_sha256")
        and record.get("is_available") is True
        and _is_false_or_none(record.get("is_sealed"))
        and _is_false_or_none(record.get("is_private"))
        and record.get("redaction_or_seal_status") == "public"
        and record.get("restriction_status") == "public"
        and _is_fresh_public_restriction_evidence(
            record.get("restriction_evidence"),
            is_sealed=cast(bool | None, record.get("is_sealed")),
        )
    ]
    if len(matches) != 1:
        raise ResolvedPostRecoveryError(
            f"resolved document lacks exact fresh-detail public proof: {key}"
        )
    return matches[0]


def _validate_resolved_direct_queue_delivery_authority(
    record: Mapping[str, object], *, key: tuple[str, str]
) -> None:
    """Validate the closed direct-queue proof carried by one v4 record."""

    raw = record.get("direct_queue_delivery_authority")
    if not isinstance(raw, Mapping):
        raise ResolvedPostRecoveryError(
            f"resolved direct queue delivery authority is invalid: {key}"
        )
    authority = cast(Mapping[str, object], raw)
    fields = {
        "schema_version",
        "source_provider",
        "purchase_status",
        "operation_key",
        "queue_id",
        "reservation_id",
        "reservation_usd",
        "queue_response_sha256",
        "purchase_policy_sha256",
        "purchase_operation_sha256",
        "purchase_response_sha256",
        "recovery_run_card_sha256",
        "recovery_manifest_sha256",
        "recovery_restriction_evidence_sha256",
        "purchase_state_sha256",
    }
    operation_key = _uuid4(authority.get("operation_key"))
    queue_id = authority.get("queue_id")
    reservation_usd = authority.get("reservation_usd")
    if (
        set(authority) != fields
        or authority.get("schema_version")
        != "legalforecast.direct_courtlistener_queue_delivery_authority.v1"
        or authority.get("source_provider") != "courtlistener.recap-fetch+pacer"
        or authority.get("purchase_status") != "queued"
        or operation_key != record.get("operation_key")
        or authority.get("reservation_id") != f"direct:{operation_key}"
        or not isinstance(queue_id, str)
        or re.fullmatch(r"[1-9][0-9]*", queue_id) is None
        or not isinstance(reservation_usd, str)
        or re.fullmatch(r"(?:0|[1-9][0-9]*)\.[0-9]{2}", reservation_usd) is None
        or authority.get("purchase_policy_sha256")
        != record.get("purchase_policy_sha256")
        or authority.get("purchase_operation_sha256")
        != record.get("purchase_operation_sha256")
    ):
        raise ResolvedPostRecoveryError(
            f"resolved direct queue delivery authority is invalid: {key}"
        )
    for field in (
        "queue_response_sha256",
        "purchase_policy_sha256",
        "purchase_operation_sha256",
        "purchase_response_sha256",
        "recovery_run_card_sha256",
        "recovery_manifest_sha256",
        "recovery_restriction_evidence_sha256",
        "purchase_state_sha256",
    ):
        _required_sha(authority.get(field), field)


def _validate_resolved_record(
    record: Mapping[str, object], *, key: tuple[str, str]
) -> None:
    schema_version = record.get("schema_version")
    provider_free_recovered_public = (
        schema_version
        in {
            RESOLVED_POST_RECOVERY_SCHEMA_VERSION_V2,
            RESOLVED_POST_RECOVERY_SCHEMA_VERSION_V3,
            RESOLVED_POST_RECOVERY_SCHEMA_VERSION_V4,
        }
        and record.get("clearance_basis") == "provider_free_recovered_public"
    )
    if (
        (
            schema_version == RESOLVED_POST_RECOVERY_SCHEMA_VERSION_V2
            and not provider_free_recovered_public
        )
        or (
            schema_version == RESOLVED_POST_RECOVERY_SCHEMA_VERSION_V3
            and record.get("clearance_basis")
            not in {None, "provider_free_recovered_public"}
        )
        or (
            schema_version == RESOLVED_POST_RECOVERY_SCHEMA_VERSION_V4
            and not provider_free_recovered_public
        )
    ):
        raise ResolvedPostRecoveryError(
            f"resolved document schema does not match clearance basis: {key}"
        )
    if (
        record.get("schema_version")
        not in {
            RESOLVED_POST_RECOVERY_SCHEMA_VERSION,
            RESOLVED_POST_RECOVERY_SCHEMA_VERSION_V2,
            RESOLVED_POST_RECOVERY_SCHEMA_VERSION_V3,
            RESOLVED_POST_RECOVERY_SCHEMA_VERSION_V4,
        }
        or record.get("candidate_id") != key[0]
        or record.get("source_document_id") != key[1]
        or record.get("recovery_origin") != UNKNOWN_RECOVERY_ORIGIN
        or record.get("restriction_status") != "public"
        or record.get("parser_eligible") is not True
        or record.get("packet_eligible") is not True
    ):
        raise ResolvedPostRecoveryError(f"resolved document is invalid: {key}")
    digest_fields = [
        "purchase_policy_sha256",
        "attempt_policy_sha256",
        "selection_document_sha256",
        "purchase_operation_sha256",
        "fresh_recap_detail_sha256",
        "download_url_sha256",
        "download_record_sha256",
        "content_sha256",
        "clearance_record_sha256",
        "clearance_run_card_sha256",
        "clearance_artifact_sha256",
        "cohort_policy_artifact_sha256",
        "restriction_evidence_artifact_sha256",
        "restriction_evidence_rows_sha256",
        "fresh_detail_public_evidence_sha256",
    ]
    delivery_authority = record.get("delivery_authority")
    broker_fields = {
        "broker_receipt_sha256",
        "broker_receipt_state",
        "queue_response_sha256",
    }
    public_fields = {"public_material_recovery_sha256"}
    direct_fields = {"direct_queue_delivery_authority"}
    if record.get("schema_version") in {
        RESOLVED_POST_RECOVERY_SCHEMA_VERSION,
        RESOLVED_POST_RECOVERY_SCHEMA_VERSION_V2,
    }:
        if (
            delivery_authority is not None
            or not broker_fields.issubset(record)
            or public_fields.intersection(record)
            or direct_fields.intersection(record)
        ):
            raise ResolvedPostRecoveryError(
                f"resolved broker delivery authority is invalid: {key}"
            )
        digest_fields.extend(("broker_receipt_sha256", "queue_response_sha256"))
        _required_text(record.get("broker_receipt_state"), "broker receipt state")
    elif (
        schema_version == RESOLVED_POST_RECOVERY_SCHEMA_VERSION_V3
        and delivery_authority == "authenticated_public_material_recovery"
    ):
        if (
            not public_fields.issubset(record)
            or broker_fields.intersection(record)
            or direct_fields.intersection(record)
        ):
            raise ResolvedPostRecoveryError(
                f"resolved public delivery authority is invalid: {key}"
            )
        digest_fields.append("public_material_recovery_sha256")
    elif (
        schema_version == RESOLVED_POST_RECOVERY_SCHEMA_VERSION_V4
        and delivery_authority == "authenticated_direct_courtlistener_queue_recovery"
    ):
        # PR #512 strengthened direct-queue authority without changing the v4
        # schema label. Preserve validation of already-frozen pre-#512 rows,
        # but only in their exact historical closed shape.
        if (
            set(record) != set(_LEGACY_DIRECT_QUEUE_RESOLVED_FIELDS)
            or direct_fields.intersection(record)
            or public_fields.intersection(record)
        ):
            raise ResolvedPostRecoveryError(
                f"resolved direct queue delivery authority is invalid: {key}"
            )
        digest_fields.append("queue_response_sha256")
    elif (
        schema_version == RESOLVED_POST_RECOVERY_SCHEMA_VERSION_V4
        and delivery_authority == "authenticated_direct_courtlistener_queue"
    ):
        if (
            set(record) != set(_DIRECT_QUEUE_RESOLVED_FIELDS)
            or broker_fields.intersection(record)
            or public_fields.intersection(record)
        ):
            raise ResolvedPostRecoveryError(
                f"resolved direct queue delivery authority is invalid: {key}"
            )
        _validate_resolved_direct_queue_delivery_authority(record, key=key)
    else:
        raise ResolvedPostRecoveryError(
            f"resolved document delivery authority is invalid: {key}"
        )
    raw_lineage = record.get("recovered_public_lineage")
    review_fields = (
        "reviews_artifact_sha256",
        "review_receipt_sha256",
        "review_authority_sha256",
    )
    if provider_free_recovered_public:
        if not isinstance(raw_lineage, Mapping):
            raise ResolvedPostRecoveryError(
                f"resolved recovered-public lineage is invalid: {key}"
            )
        if any(field in record for field in review_fields):
            raise ResolvedPostRecoveryError(
                f"resolved recovered-public lineage is contradictory: {key}"
            )
        if schema_version == RESOLVED_POST_RECOVERY_SCHEMA_VERSION_V4 and (
            cast(Mapping[str, object], raw_lineage).get(
                "direct_queue_delivery_authority"
            )
            != record.get("direct_queue_delivery_authority")
        ):
            raise ResolvedPostRecoveryError(
                f"resolved direct queue recovery lineage changed: {key}"
            )
    else:
        if raw_lineage is not None:
            raise ResolvedPostRecoveryError(
                f"resolved review lineage is contradictory: {key}"
            )
        digest_fields.extend(review_fields)
    for field in digest_fields:
        _required_sha(record.get(field), field)
    _uuid4(record.get("operation_key"))
    _positive_int(record.get("byte_count"), "byte_count")
    committed = _required_sha(record.get("record_sha256"), "record")
    unhashed = {
        name: value for name, value in record.items() if name != "record_sha256"
    }
    if _sha256(unhashed) != committed:
        raise ResolvedPostRecoveryError(f"resolved document hash changed: {key}")


def _index(
    records: Sequence[Mapping[str, Any]], label: str
) -> dict[tuple[str, str], Mapping[str, Any]]:
    output: dict[tuple[str, str], Mapping[str, Any]] = {}
    for record in records:
        key = _key(record)
        if key in output:
            raise ResolvedPostRecoveryError(f"duplicate {label}: {key}")
        output[key] = record
    return output


def reconstruct_pre_resolution_purchase_snapshot(
    *,
    current_snapshot: CaseDevPurchaseSnapshot,
    resolved_records: Sequence[Mapping[str, Any]],
    policy: CaseDevPurchasePolicy,
    expected_purchase_state_before_sha256: str,
) -> CaseDevPurchaseSnapshot:
    """Reverse only resolver-authorized clearance fields and prove prior state."""

    resolved = _index(resolved_records, "resolved post-recovery document")
    operations = _index(current_snapshot.operations, "purchase operation")
    if set(resolved) - set(operations):
        raise ResolvedPostRecoveryError(
            "canonical purchase journal lacks resolved operation coverage"
        )
    reconstructed: list[Mapping[str, Any]] = []
    for operation in current_snapshot.operations:
        key = _key(operation)
        record = resolved.get(key)
        if record is None:
            reconstructed.append(operation)
            continue
        _validate_resolved_record(record, key=key)
        material = _mapping(operation.get("material_evidence"), "material evidence")
        if (
            operation.get("material_state") != "cleared_public"
            or operation.get("resolved_document_sha256") != record.get("record_sha256")
            or material.get("clearance_record_sha256")
            != record.get("clearance_record_sha256")
        ):
            raise ResolvedPostRecoveryError(
                f"canonical purchase journal clearance binding changed: {key}"
            )
        preclear = dict(operation)
        preclear["material_state"] = "recovered_pending_clearance"
        preclear_material = dict(material)
        preclear_material.pop("clearance_record_sha256", None)
        preclear["material_evidence"] = preclear_material
        preclear["resolved_document_sha256"] = None
        if record.get("purchase_operation_sha256") != _sha256(preclear):
            raise ResolvedPostRecoveryError(
                f"resolved purchase operation commitment changed: {key}"
            )
        reconstructed.append(preclear)
    state_sha256 = canonical_purchase_state_sha256(
        policy,
        committed_amount_usd=current_snapshot.committed_amount_usd,
        operations=reconstructed,
    )
    if state_sha256 != expected_purchase_state_before_sha256:
        raise ResolvedPostRecoveryError(
            "resolved purchase transition does not reproduce its prior state"
        )
    return CaseDevPurchaseSnapshot(
        operations=tuple(reconstructed),
        committed_amount_usd=current_snapshot.committed_amount_usd,
        purchase_state_sha256=state_sha256,
    )


def _group_index(
    records: Sequence[Mapping[str, Any]], label: str
) -> dict[tuple[str, str], tuple[Mapping[str, Any], ...]]:
    output: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for record in records:
        output.setdefault(_key(record), []).append(record)
    if not output and records:
        raise ResolvedPostRecoveryError(f"{label} is invalid")
    return {key: tuple(sorted(rows, key=_sha256)) for key, rows in output.items()}


def _key(record: Mapping[str, object]) -> tuple[str, str]:
    return (
        _required_text(record.get("candidate_id"), "candidate_id"),
        _required_text(record.get("source_document_id"), "source_document_id"),
    )


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ResolvedPostRecoveryError(f"{label} must be an object")
    return cast(Mapping[str, Any], value)


def _required_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ResolvedPostRecoveryError(f"{label} must be a canonical string")
    return value


def _required_sha(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ResolvedPostRecoveryError(f"{label} must be lowercase SHA-256")
    return value


def _commitment_sha256(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise ResolvedPostRecoveryError(f"{label} commitment must be SHA-256")
    return _required_sha(value.removeprefix("sha256:"), f"{label} commitment")


def _uuid4(value: object) -> str:
    if not isinstance(value, str) or _UUID4.fullmatch(value) is None:
        raise ResolvedPostRecoveryError("operation key must be canonical UUIDv4")
    return value


def _positive_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ResolvedPostRecoveryError(f"{label} must be a positive integer")
    return value


def _sha256(value: object) -> str:
    normalized: object = value
    if isinstance(value, Mapping):
        normalized = dict(cast(Mapping[str, object], value))
    elif isinstance(value, tuple):
        normalized = list(cast(tuple[object, ...], value))
    return hashlib.sha256(
        json.dumps(
            normalized, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def _bytes_sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _json_object_from_bytes(value: bytes, label: str) -> dict[str, object]:
    try:
        parsed: object = json.loads(value.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ResolvedPostRecoveryError(f"{label} is not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ResolvedPostRecoveryError(f"{label} must be a JSON object")
    return cast(dict[str, object], parsed)


def _jsonl_records_from_bytes(value: bytes, label: str) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    try:
        text = value.decode("utf-8")
        for line in text.splitlines():
            if not line.strip():
                continue
            parsed: object = json.loads(line)
            if not isinstance(parsed, dict):
                raise ResolvedPostRecoveryError(f"{label} rows must be JSON objects")
            output.append(cast(dict[str, object], parsed))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ResolvedPostRecoveryError(f"{label} is not valid JSONL") from exc
    return output
