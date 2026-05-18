"""Fallback reconstruction pilot reporting."""

from __future__ import annotations

import os
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from legalforecast.ingestion.courtlistener_client import (
    COURTLISTENER_API_TOKEN_ENV,
    CourtListenerAuthError,
    CourtListenerClient,
    CourtListenerClientError,
    CourtListenerUnavailableError,
)
from legalforecast.ingestion.recap_client import RECAP_API_TOKEN_ENV
from legalforecast.reporting.pilot_readiness import (
    DOCKET_ENTRY_LISTING_UNAVAILABLE,
    CaseDevSmokeReadinessMetrics,
    parse_case_dev_smoke_markdown,
)
from legalforecast.selection.fallback_rules import FallbackGap

CASE_DEV_API_KEY_ENV = "CASE_DEV_API_KEY"


class FallbackAttemptStatus(StrEnum):
    """Outcome of one bounded fallback reconstruction attempt."""

    BLOCKED_MISSING_COURTLISTENER_TOKEN = "blocked_missing_courtlistener_token"
    NOT_RUN_LIVE_COURTLISTENER_DISABLED = "not_run_live_courtlistener_disabled"
    COURTLISTENER_AUTH_ERROR = "courtlistener_auth_error"
    COURTLISTENER_DOCKET_UNAVAILABLE = "courtlistener_docket_unavailable"
    COURTLISTENER_DOCKET_EMPTY = "courtlistener_docket_empty"
    COURTLISTENER_ERROR = "courtlistener_error"
    DOCKET_RECONSTRUCTED = "docket_reconstructed"


@dataclass(frozen=True, slots=True)
class CaseDevFallbackCandidate:
    """One case.dev candidate that needs targeted fallback."""

    candidate_id: str
    case_id: str
    missing_reasons: tuple[str, ...]
    retrieval_error: str | None

    def __post_init__(self) -> None:
        _require_non_empty(self.candidate_id, "candidate_id")
        _require_non_empty(self.case_id, "case_id")
        for reason in self.missing_reasons:
            _require_non_empty(reason, "missing_reasons")
        if self.retrieval_error is not None:
            _require_non_empty(self.retrieval_error, "retrieval_error")

    @property
    def needs_docket_fallback(self) -> bool:
        return DOCKET_ENTRY_LISTING_UNAVAILABLE in self.missing_reasons


@dataclass(frozen=True, slots=True)
class FallbackCredentialStatus:
    """Secret-safe credential availability summary."""

    case_dev_key_present: bool
    courtlistener_token_present: bool
    recap_access_token_present: bool

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
    ) -> FallbackCredentialStatus:
        values = os.environ if environ is None else environ
        courtlistener_token_present = _has_secret(
            values.get(COURTLISTENER_API_TOKEN_ENV)
        )
        return cls(
            case_dev_key_present=_has_secret(values.get(CASE_DEV_API_KEY_ENV)),
            courtlistener_token_present=courtlistener_token_present,
            recap_access_token_present=(
                _has_secret(values.get(RECAP_API_TOKEN_ENV))
                or courtlistener_token_present
            ),
        )


@dataclass(frozen=True, slots=True)
class FallbackReconstructionAttempt:
    """Auditable result for one candidate's fallback gate."""

    candidate_id: str
    case_id: str
    status: FallbackAttemptStatus
    docket_entry_count: int = 0
    recap_document_handle_count: int = 0
    request_count: int = 0
    missing_reasons: tuple[str, ...] = ()
    detail: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.candidate_id, "candidate_id")
        _require_non_empty(self.case_id, "case_id")
        if self.docket_entry_count < 0:
            raise ValueError("docket_entry_count must be non-negative")
        if self.recap_document_handle_count < 0:
            raise ValueError("recap_document_handle_count must be non-negative")
        if self.request_count < 0:
            raise ValueError("request_count must be non-negative")
        for reason in self.missing_reasons:
            _require_non_empty(reason, "missing_reasons")
        if self.detail is not None:
            _require_non_empty(self.detail, "detail")

    @property
    def reconstructed_docket(self) -> bool:
        return self.status is FallbackAttemptStatus.DOCKET_RECONSTRUCTED

    @property
    def source_class(self) -> str:
        if self.reconstructed_docket:
            return "case.dev-plus-fallback"
        return "excluded"

    @property
    def clean_packet_count(self) -> int:
        return 0


@dataclass(frozen=True, slots=True)
class FallbackReconstructionPilotReport:
    """Report inputs for the optional live fallback reconstruction pilot."""

    generated_at: datetime
    smoke_metrics: CaseDevSmokeReadinessMetrics
    credentials: FallbackCredentialStatus
    candidates: tuple[CaseDevFallbackCandidate, ...]
    attempts: tuple[FallbackReconstructionAttempt, ...]
    live_courtlistener_requested: bool

    @property
    def fallback_needed_count(self) -> int:
        return sum(
            1 for candidate in self.candidates if candidate.needs_docket_fallback
        )

    @property
    def reconstructed_docket_count(self) -> int:
        return sum(1 for attempt in self.attempts if attempt.reconstructed_docket)

    @property
    def clean_packet_count(self) -> int:
        return sum(attempt.clean_packet_count for attempt in self.attempts)

    @property
    def courtlistener_request_count(self) -> int:
        return sum(attempt.request_count for attempt in self.attempts)

    @property
    def source_class_counts(self) -> Mapping[str, int]:
        counter: Counter[str] = Counter()
        counter.update(attempt.source_class for attempt in self.attempts)
        return {
            "case.dev-only": 0,
            "case.dev-plus-fallback": counter["case.dev-plus-fallback"],
            "excluded": counter["excluded"],
        }

    @property
    def status_counts(self) -> Mapping[FallbackAttemptStatus, int]:
        counter: Counter[FallbackAttemptStatus] = Counter()
        counter.update(attempt.status for attempt in self.attempts)
        return dict(counter)


def parse_case_dev_fallback_candidates(
    smoke_report_text: str,
) -> tuple[CaseDevFallbackCandidate, ...]:
    """Parse the case.dev smoke candidate ledger."""

    candidates: list[CaseDevFallbackCandidate] = []
    for line in smoke_report_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("| case-dev-smoke-"):
            continue
        parts = [part.strip() for part in stripped.strip("|").split("|")]
        if len(parts) < 5:
            raise ValueError("candidate ledger row must contain five columns")
        missing_reasons = tuple(
            reason
            for reason in (item.strip() for item in parts[3].split(","))
            if reason and reason != "none"
        )
        retrieval_error = None if parts[4] == "none" else parts[4]
        candidates.append(
            CaseDevFallbackCandidate(
                candidate_id=parts[0],
                case_id=parts[1],
                missing_reasons=missing_reasons,
                retrieval_error=retrieval_error,
            )
        )
    return tuple(candidates)


def build_fallback_reconstruction_pilot_report(
    smoke_report_text: str,
    *,
    credentials: FallbackCredentialStatus | None = None,
    attempts: Sequence[FallbackReconstructionAttempt] | None = None,
    attempt_limit: int = 10,
    generated_at: datetime | None = None,
    live_courtlistener_requested: bool = False,
) -> FallbackReconstructionPilotReport:
    """Build a truthful fallback pilot report from current evidence."""

    if attempt_limit <= 0:
        raise ValueError("attempt_limit must be positive")
    credential_status = credentials or FallbackCredentialStatus.from_env()
    candidates = tuple(
        candidate
        for candidate in parse_case_dev_fallback_candidates(smoke_report_text)
        if candidate.needs_docket_fallback
    )[:attempt_limit]
    fallback_attempts = (
        tuple(attempts)
        if attempts is not None
        else _default_attempts(
            candidates,
            credentials=credential_status,
            live_courtlistener_requested=live_courtlistener_requested,
        )
    )
    return FallbackReconstructionPilotReport(
        generated_at=generated_at or datetime.now(UTC),
        smoke_metrics=parse_case_dev_smoke_markdown(smoke_report_text),
        credentials=credential_status,
        candidates=candidates,
        attempts=fallback_attempts,
        live_courtlistener_requested=live_courtlistener_requested,
    )


def run_courtlistener_fallback_attempts(
    candidates: Sequence[CaseDevFallbackCandidate],
    *,
    client: CourtListenerClient,
    attempt_limit: int = 10,
    page_size: int = 100,
) -> tuple[FallbackReconstructionAttempt, ...]:
    """Try bounded CourtListener docket reconstruction for smoke candidates."""

    if attempt_limit <= 0:
        raise ValueError("attempt_limit must be positive")
    if page_size <= 0:
        raise ValueError("page_size must be positive")
    attempts: list[FallbackReconstructionAttempt] = []
    for candidate in candidates[:attempt_limit]:
        before_requests = client.request_count
        try:
            client.get_docket(candidate.case_id)
            entries = tuple(
                client.iter_docket_entries(candidate.case_id, page_size=page_size)
            )
        except CourtListenerAuthError as exc:
            attempts.append(
                _error_attempt(
                    candidate,
                    status=FallbackAttemptStatus.COURTLISTENER_AUTH_ERROR,
                    request_count=client.request_count - before_requests,
                    missing_reason="courtlistener_auth_required",
                    detail=str(exc) or type(exc).__name__,
                )
            )
            continue
        except CourtListenerUnavailableError as exc:
            attempts.append(
                _error_attempt(
                    candidate,
                    status=FallbackAttemptStatus.COURTLISTENER_DOCKET_UNAVAILABLE,
                    request_count=client.request_count - before_requests,
                    missing_reason="courtlistener_docket_unavailable",
                    detail=str(exc) or type(exc).__name__,
                )
            )
            continue
        except CourtListenerClientError as exc:
            attempts.append(
                _error_attempt(
                    candidate,
                    status=FallbackAttemptStatus.COURTLISTENER_ERROR,
                    request_count=client.request_count - before_requests,
                    missing_reason=f"courtlistener_error:{type(exc).__name__}",
                    detail=type(exc).__name__,
                )
            )
            continue

        recap_handle_count = sum(len(entry.recap_document_ids) for entry in entries)
        if not entries:
            attempts.append(
                FallbackReconstructionAttempt(
                    candidate_id=candidate.candidate_id,
                    case_id=candidate.case_id,
                    status=FallbackAttemptStatus.COURTLISTENER_DOCKET_EMPTY,
                    request_count=client.request_count - before_requests,
                    missing_reasons=("courtlistener_docket_entries_empty",),
                )
            )
            continue
        attempts.append(
            FallbackReconstructionAttempt(
                candidate_id=candidate.candidate_id,
                case_id=candidate.case_id,
                status=FallbackAttemptStatus.DOCKET_RECONSTRUCTED,
                docket_entry_count=len(entries),
                recap_document_handle_count=recap_handle_count,
                request_count=client.request_count - before_requests,
            )
        )
    return tuple(attempts)


def render_fallback_reconstruction_pilot_markdown(
    report: FallbackReconstructionPilotReport,
) -> str:
    """Render the fallback pilot gate as markdown."""

    source_counts = report.source_class_counts
    status_counts = report.status_counts
    generated_at = _iso_datetime(report.generated_at)
    fallback_attempt_rows = _fallback_attempt_rows(report.attempts)
    status_rows = _status_rows(status_counts)
    candidate_count = len(report.candidates)
    live_mode = "yes" if report.live_courtlistener_requested else "no"
    token_blocked = status_counts.get(
        FallbackAttemptStatus.BLOCKED_MISSING_COURTLISTENER_TOKEN,
        0,
    )
    bottom_line = (
        "The optional CourtListener/RECAP fallback pilot did not produce clean "
        "packets. case.dev has a candidate ledger, but this session lacks a "
        "`COURTLISTENER_API_TOKEN`/RECAP-capable token, so this optional "
        "reconstruction path cannot honestly be run. The official case.dev "
        "path remains blocked on docket-entry/source-document retrieval or a "
        "case.dev-supported export path; a missing CourtListener token is not "
        "itself a v1 dependency blocker and not a basis to fabricate packets."
    )
    if report.reconstructed_docket_count:
        bottom_line = (
            "The fallback pilot reconstructed at least one public docket through "
            "CourtListener, but no clean packets are counted until required "
            "source documents, linkage, leakage review, units, and labels are "
            "completed."
        )

    return (
        "# Phase 0 Fallback Reconstruction Pilot Report\n\n"
        f"- Generated at: {generated_at}\n"
        "- Source smoke report: provided by `--smoke-report`\n\n"
        "## Bottom Line\n\n"
        f"{bottom_line}\n\n"
        "Regenerate this report with:\n\n"
        "```bash\n"
        "legalforecast pilot fallback-reconstruction --smoke-report "
        "tmp/case-dev-smoke.md --output tmp/fallback-reconstruction.md\n"
        "```\n\n"
        "Use `--live-courtlistener` only when the project explicitly enables a "
        "CourtListener/RECAP fallback and a capable token is present; use "
        "`--courtlistener-fixture` for offline reconstruction tests.\n\n"
        "## Readiness Status\n\n"
        "| Field | Result |\n"
        "| --- | --- |\n"
        f"| case.dev key available to this command | "
        f"{_yes_no(report.credentials.case_dev_key_present)} |\n"
        f"| CourtListener token available | "
        f"{_yes_no(report.credentials.courtlistener_token_present)} |\n"
        f"| RECAP access token available | "
        f"{_yes_no(report.credentials.recap_access_token_present)} |\n"
        f"| Live CourtListener requested | {live_mode} |\n"
        f"| case.dev fallback-needed candidates parsed | {candidate_count} |\n"
        f"| CourtListener/RECAP token-blocked candidates | {token_blocked} |\n"
        f"| Dockets reconstructed through fallback | "
        f"{report.reconstructed_docket_count} |\n"
        f"| Clean packets produced | {report.clean_packet_count} |\n"
        f"| case.dev request count from smoke | "
        f"{report.smoke_metrics.request_count} |\n"
        f"| CourtListener request count in this pilot | "
        f"{report.courtlistener_request_count} |\n\n"
        "## Source-Class Distribution\n\n"
        "| Source class | Candidate count | Interpretation |\n"
        "| --- | ---: | --- |\n"
        f"| `case.dev-only` | {source_counts['case.dev-only']} | No case.dev-only "
        "packets could be built while docket entries remain unavailable. |\n"
        f"| `case.dev-plus-fallback` | {source_counts['case.dev-plus-fallback']} | "
        "Docket reconstruction reached a supplemental public-record source. |\n"
        f"| `excluded` | {source_counts['excluded']} | Fallback was blocked or did "
        "not reconstruct public docket rows in this pilot. |\n\n"
        "## Fallback Status Counts\n\n"
        "| Status | Count |\n"
        "| --- | ---: |\n"
        f"{status_rows}\n"
        "## Fallback Attempt Ledger\n\n"
        "| Candidate ID | Case ID | Gap | Status | Docket entries | RECAP handles | "
        "Requests | Missing reasons |\n"
        "| --- | --- | --- | --- | ---: | ---: | ---: | --- |\n"
        f"{fallback_attempt_rows}\n"
        "## Protocol Result\n\n"
        "This optional fallback gate should not be the default blocker for "
        "official evaluation unless the project explicitly chooses "
        "CourtListener/RECAP as a public-record supplement. Without that "
        "choice, the official blocker is case.dev docket-entry/source-document "
        "retrieval or a case.dev-supported export path. If the fallback path is "
        "enabled, the next successful run must show, for each candidate, "
        "whether CourtListener/RECAP can reconstruct the docket, whether "
        "required complaint/motion/briefing/disposition documents can be "
        "recovered, and whether the normal linkage, leakage, unitization, "
        "labeling, and cost reports can run on retained packets.\n\n"
        "Optional fallback checklist:\n\n"
        "- provide a `COURTLISTENER_API_TOKEN` or other RECAP-capable public-record "
        "credential;\n"
        "- verify whether case.dev case IDs map directly to CourtListener docket "
        "IDs or require an ID-resolution step;\n"
        "- run CourtListener docket reconstruction over the bounded case.dev "
        "candidate ledger;\n"
        "- only count clean packets after source-document recovery and normal "
        "LegalForecast packet construction succeeds;\n"
        "- keep case.dev discovery costs separate from CourtListener/RECAP/PACER "
        "fallback costs.\n"
    )


def _default_attempts(
    candidates: Sequence[CaseDevFallbackCandidate],
    *,
    credentials: FallbackCredentialStatus,
    live_courtlistener_requested: bool,
) -> tuple[FallbackReconstructionAttempt, ...]:
    status = (
        FallbackAttemptStatus.NOT_RUN_LIVE_COURTLISTENER_DISABLED
        if credentials.courtlistener_token_present and not live_courtlistener_requested
        else FallbackAttemptStatus.BLOCKED_MISSING_COURTLISTENER_TOKEN
    )
    missing_reason = (
        "live_courtlistener_not_enabled"
        if status is FallbackAttemptStatus.NOT_RUN_LIVE_COURTLISTENER_DISABLED
        else "missing_courtlistener_api_token"
    )
    return tuple(
        FallbackReconstructionAttempt(
            candidate_id=candidate.candidate_id,
            case_id=candidate.case_id,
            status=status,
            missing_reasons=(missing_reason,),
        )
        for candidate in candidates
    )


def _error_attempt(
    candidate: CaseDevFallbackCandidate,
    *,
    status: FallbackAttemptStatus,
    request_count: int,
    missing_reason: str,
    detail: str,
) -> FallbackReconstructionAttempt:
    return FallbackReconstructionAttempt(
        candidate_id=candidate.candidate_id,
        case_id=candidate.case_id,
        status=status,
        request_count=request_count,
        missing_reasons=(missing_reason,),
        detail=detail,
    )


def _fallback_attempt_rows(
    attempts: Sequence[FallbackReconstructionAttempt],
) -> str:
    if not attempts:
        return "| none | none | none | none | 0 | 0 | 0 | none |\n\n"
    lines: list[str] = []
    for attempt in attempts:
        lines.append(
            "| {candidate_id} | {case_id} | {gap} | {status} | {entries} | "
            "{recap_handles} | {requests} | {missing} |".format(
                candidate_id=attempt.candidate_id,
                case_id=attempt.case_id,
                gap=FallbackGap.DOCKET_ENTRY_LISTING_UNAVAILABLE.value,
                status=attempt.status.value,
                entries=attempt.docket_entry_count,
                recap_handles=attempt.recap_document_handle_count,
                requests=attempt.request_count,
                missing=", ".join(attempt.missing_reasons) or "none",
            )
        )
    return "\n".join(lines) + "\n\n"


def _status_rows(status_counts: Mapping[FallbackAttemptStatus, int]) -> str:
    if not status_counts:
        return "| none | 0 |\n\n"
    lines = [
        f"| `{status.value}` | {count} |"
        for status, count in sorted(status_counts.items(), key=lambda item: item[0])
    ]
    return "\n".join(lines) + "\n\n"


def _has_secret(value: str | None) -> bool:
    return value is not None and bool(value.strip())


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _iso_datetime(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
