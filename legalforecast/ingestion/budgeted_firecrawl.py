"""Budget-authorized, resumable scheduling for Firecrawl page targets.

The scheduler is intentionally unaware of CourtListener page semantics.  Its
targets can represent search pages or docket pages, while the supplied source
remains responsible for URL allowlisting and response validation.  Every wire
request is durably authorized at its worst-case credit cost before
``source.scrape_url`` is called.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol, TypedDict, cast

from legalforecast.ingestion.cycle_acquisition_store import (
    CycleAcquisitionStore,
    FirecrawlAttempt,
)
from legalforecast.ingestion.firecrawl_source import (
    FirecrawlAuthError,
    FirecrawlChallengeError,
    FirecrawlError,
    FirecrawlPaymentRequiredError,
    FirecrawlRateLimitError,
    FirecrawlResponseError,
    FirecrawlScrapeResult,
    FirecrawlServerError,
)

FirecrawlTargetKind = Literal["search", "docket"]
_HTTP_STATUS = re.compile(r"\bHTTP\s+(?P<status>[1-5][0-9]{2})\b", re.IGNORECASE)


class FirecrawlCircuitOpenError(RuntimeError):
    """Raised after the configured number of consecutive provider 5xx errors."""


class FirecrawlArtifactError(RuntimeError):
    """Raised when a persisted successful artifact cannot be verified."""


class FirecrawlPageSource(Protocol):
    """Generic bounded-scrape seam used by the scheduler."""

    def scrape_url(self, *, source_url: str) -> FirecrawlScrapeResult:
        """Scrape one already-allowlisted URL."""

        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class FirecrawlTargetSpec:
    """One immutable page target in deterministic scheduling order."""

    target_id: str
    target_kind: FirecrawlTargetKind
    source_url: str
    page_number: int
    ordinal: int

    def __post_init__(self) -> None:
        if not self.target_id.strip():
            raise ValueError("target_id must be nonempty")
        if self.target_kind not in {"search", "docket"}:
            raise ValueError("target_kind must be search or docket")
        if not self.source_url.strip():
            raise ValueError("source_url must be nonempty")
        _require_positive_int(self.page_number, "page_number")
        _require_nonnegative_int(self.ordinal, "ordinal")


@dataclass(frozen=True, slots=True)
class FirecrawlPageRecord:
    """Verified successful page returned to a search or docket caller."""

    target_id: str
    target_kind: FirecrawlTargetKind
    source_url: str
    page_number: int
    ordinal: int
    attempt_id: int
    attempt_number: int
    raw_html: str
    artifact_path: Path
    artifact_sha256: str
    artifact_byte_count: int
    reported_credits: int
    proxy_used: str | None
    target_http_status: int | None


@dataclass(frozen=True, slots=True)
class BudgetedFirecrawlRunResult:
    """Successful pages plus the store's reconciled authorization summary."""

    pages: tuple[FirecrawlPageRecord, ...]
    summary: Mapping[str, object]


class BudgetedFirecrawlScheduler:
    """Run generic page targets with durable budget and retry checkpoints."""

    def __init__(
        self,
        *,
        store: CycleAcquisitionStore,
        source: FirecrawlPageSource,
        run_id: str,
        artifact_dir: str | Path,
        max_attempts: int = 3,
        provider_5xx_circuit_threshold: int = 5,
    ) -> None:
        if not run_id.strip():
            raise ValueError("run_id must be nonempty")
        _require_positive_int(max_attempts, "max_attempts")
        _require_positive_int(
            provider_5xx_circuit_threshold,
            "provider_5xx_circuit_threshold",
        )
        self.store = store
        self.source = source
        self.run_id = run_id
        self.artifact_dir = Path(artifact_dir).resolve()
        self.max_attempts = max_attempts
        self.provider_5xx_circuit_threshold = provider_5xx_circuit_threshold

    def run(self, targets: Sequence[FirecrawlTargetSpec]) -> BudgetedFirecrawlRunResult:
        """Run targets widest-first and return every verified successful page.

        Scheduling is by attempt round: all targets receive attempt one before
        any target receives attempt two.  Provider 5xx errors are isolated
        until the consecutive-error circuit opens.  Authentication, payment,
        rate-limit, budget, and open-circuit failures stop immediately.
        """

        ordered = _ordered_unique_targets(targets)
        for target in ordered:
            self.store.ensure_firecrawl_target(
                self.run_id,
                target_id=target.target_id,
                target_kind=target.target_kind,
                source_url=target.source_url,
                ordinal=target.ordinal,
            )

        self._finalize_abandoned_authorizations()
        consecutive_5xx = _trailing_provider_5xx(
            self.store.firecrawl_attempts(self.run_id)
        )
        if consecutive_5xx >= self.provider_5xx_circuit_threshold:
            self._raise_open_circuit(consecutive_5xx)

        succeeded = self._successful_attempts(ordered)
        terminal_failures = {
            attempt.target_id
            for attempt in self.store.firecrawl_attempts(self.run_id)
            if attempt.failure_transient is False
        }
        for target in ordered:
            if target.target_id in succeeded:
                self.store.set_firecrawl_target_status(
                    self.run_id, target.target_id, "succeeded"
                )

        for attempt_round in range(1, self.max_attempts + 1):
            for target in ordered:
                if target.target_id in succeeded:
                    continue
                if target.target_id in terminal_failures:
                    continue
                attempts = self._target_attempts(target)
                if len(attempts) >= attempt_round:
                    continue
                attempt = self.store.authorize_firecrawl_attempt(
                    self.run_id,
                    target_id=target.target_id,
                    page_number=target.page_number,
                    request_url=target.source_url,
                )
                try:
                    result = self.source.scrape_url(source_url=target.source_url)
                    page = self._commit_success(target, attempt, result)
                except FirecrawlChallengeError as error:
                    self.store.finalize_firecrawl_attempt(
                        attempt.attempt_id,
                        status="provider_error",
                        provider_http_status=error.provider_http_status,
                        **_failure_evidence(error),
                    )
                    raise
                except (
                    FirecrawlAuthError,
                    FirecrawlPaymentRequiredError,
                    FirecrawlRateLimitError,
                ) as error:
                    self.store.finalize_firecrawl_attempt(
                        attempt.attempt_id,
                        status="provider_error",
                        provider_http_status=_global_provider_status(error),
                        **_failure_evidence(error),
                    )
                    raise
                except FirecrawlServerError as error:
                    provider_status = _http_status(error)
                    if provider_status is not None and provider_status >= 500:
                        self.store.finalize_firecrawl_attempt(
                            attempt.attempt_id,
                            status="provider_error",
                            provider_http_status=provider_status,
                            **_failure_evidence(error),
                        )
                        consecutive_5xx += 1
                        if consecutive_5xx >= self.provider_5xx_circuit_threshold:
                            self._raise_open_circuit(consecutive_5xx)
                    else:
                        self.store.finalize_firecrawl_attempt(
                            attempt.attempt_id,
                            status="transport_error",
                            **_failure_evidence(error),
                        )
                        consecutive_5xx = 0
                    continue
                except FirecrawlResponseError as error:
                    self.store.finalize_firecrawl_attempt(
                        attempt.attempt_id,
                        status="target_error",
                        provider_http_status=error.provider_http_status,
                        **_failure_evidence(error),
                    )
                    terminal_failures.add(target.target_id)
                    self.store.set_firecrawl_target_status(
                        self.run_id, target.target_id, "terminal_error"
                    )
                    consecutive_5xx = 0
                    continue
                except FirecrawlError as error:
                    self.store.finalize_firecrawl_attempt(
                        attempt.attempt_id,
                        status="transport_error",
                        provider_http_status=error.provider_http_status,
                        **_failure_evidence(error),
                    )
                    if not error.transient:
                        terminal_failures.add(target.target_id)
                        self.store.set_firecrawl_target_status(
                            self.run_id, target.target_id, "terminal_error"
                        )
                    consecutive_5xx = 0
                    continue
                succeeded[target.target_id] = page
                self.store.set_firecrawl_target_status(
                    self.run_id, target.target_id, "succeeded"
                )
                consecutive_5xx = 0

        for target in ordered:
            if (
                target.target_id not in succeeded
                and target.target_id not in terminal_failures
            ):
                self.store.set_firecrawl_target_status(
                    self.run_id, target.target_id, "retry_exhausted"
                )

        pages = tuple(
            succeeded[target.target_id]
            for target in ordered
            if target.target_id in succeeded
        )
        return BudgetedFirecrawlRunResult(
            pages=pages,
            summary=self.store.firecrawl_run_summary(self.run_id),
        )

    def _commit_success(
        self,
        target: FirecrawlTargetSpec,
        attempt: FirecrawlAttempt,
        result: FirecrawlScrapeResult,
    ) -> FirecrawlPageRecord:
        if result.source_url != target.source_url:
            raise FirecrawlResponseError(
                "Firecrawl result source URL does not match its authorized target"
            )
        reported_credits = _integral_credits(result.credits_used)
        raw = result.raw_html.encode("utf-8")
        artifact_path = self._artifact_path(target)
        finalized = self.store.commit_firecrawl_artifact(
            attempt.attempt_id,
            artifact_path,
            raw,
            reported_credits=reported_credits,
            proxy_used=result.proxy_used,
            target_http_status=result.target_status_code,
        )
        return _page_record(target, finalized, raw_html=result.raw_html)

    def _artifact_path(self, target: FirecrawlTargetSpec) -> Path:
        identity = f"{target.target_id}\0{target.source_url}".encode()
        digest = hashlib.sha256(identity).hexdigest()[:24]
        return self.artifact_dir / (
            f"{target.ordinal:06d}-page-{target.page_number:06d}-{digest}.html"
        )

    def _target_attempts(
        self, target: FirecrawlTargetSpec
    ) -> tuple[FirecrawlAttempt, ...]:
        return tuple(
            attempt
            for attempt in self.store.firecrawl_attempts(self.run_id)
            if attempt.target_id == target.target_id
            and attempt.page_number == target.page_number
        )

    def _successful_attempts(
        self, targets: Sequence[FirecrawlTargetSpec]
    ) -> dict[str, FirecrawlPageRecord]:
        successful: dict[str, FirecrawlPageRecord] = {}
        for target in targets:
            matches = [
                attempt
                for attempt in self._target_attempts(target)
                if attempt.status == "succeeded"
            ]
            if len(matches) > 1:
                raise FirecrawlArtifactError(
                    f"target {target.target_id!r} has multiple successful attempts"
                )
            if not matches:
                continue
            attempt = matches[0]
            raw_html = _read_verified_artifact(attempt)
            successful[target.target_id] = _page_record(
                target, attempt, raw_html=raw_html
            )
        return successful

    def _finalize_abandoned_authorizations(self) -> None:
        for attempt in self.store.firecrawl_attempts(self.run_id):
            if attempt.status == "authorized":
                self.store.finalize_firecrawl_attempt(
                    attempt.attempt_id,
                    status="interrupted",
                )

    def _raise_open_circuit(self, consecutive_5xx: int) -> None:
        raise FirecrawlCircuitOpenError(
            "Firecrawl provider circuit opened after "
            f"{consecutive_5xx} consecutive provider 5xx responses"
        )


def load_successful_firecrawl_pages(
    *,
    store: CycleAcquisitionStore,
    run_id: str,
) -> tuple[FirecrawlPageRecord, ...]:
    """Reload and verify every successful page committed by one durable run."""

    attempts = store.firecrawl_attempts(run_id)
    pages: list[FirecrawlPageRecord] = []
    for stored_target in store.firecrawl_targets(run_id):
        matches = tuple(
            attempt
            for attempt in attempts
            if attempt.target_id == stored_target.target_id
            and attempt.status == "succeeded"
        )
        if len(matches) > 1:
            raise FirecrawlArtifactError(
                f"target {stored_target.target_id!r} has multiple successful attempts"
            )
        if not matches:
            continue
        attempt = matches[0]
        target = FirecrawlTargetSpec(
            target_id=stored_target.target_id,
            target_kind=cast(FirecrawlTargetKind, stored_target.target_kind),
            source_url=stored_target.source_url,
            page_number=attempt.page_number,
            ordinal=stored_target.ordinal,
        )
        pages.append(
            _page_record(
                target,
                attempt,
                raw_html=_read_verified_artifact(attempt),
            )
        )
    return tuple(pages)


def _ordered_unique_targets(
    targets: Sequence[FirecrawlTargetSpec],
) -> tuple[FirecrawlTargetSpec, ...]:
    ordered = tuple(
        sorted(targets, key=lambda target: (target.ordinal, target.target_id))
    )
    ids = [target.target_id for target in ordered]
    if len(ids) != len(set(ids)):
        raise ValueError("target_id values must be unique within a scheduler run")
    return ordered


def _integral_credits(value: float | None) -> int:
    if value is None or isinstance(value, bool) or not float(value).is_integer():
        raise FirecrawlResponseError(
            "Firecrawl successful result must report integral creditsUsed"
        )
    credits = int(value)
    if credits < 0:
        raise FirecrawlResponseError("Firecrawl creditsUsed must be non-negative")
    return credits


def _require_positive_int(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


def _require_nonnegative_int(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")


def _http_status(error: BaseException) -> int | None:
    if isinstance(error, FirecrawlError) and error.provider_http_status is not None:
        return error.provider_http_status
    match = _HTTP_STATUS.search(str(error))
    return int(match.group("status")) if match is not None else None


def _global_provider_status(error: BaseException) -> int:
    parsed = _http_status(error)
    if parsed is not None:
        return parsed
    if isinstance(error, FirecrawlAuthError):
        return 401
    if isinstance(error, FirecrawlPaymentRequiredError):
        return 402
    if isinstance(error, FirecrawlRateLimitError):
        return 429
    raise AssertionError("unexpected global provider error")


def _trailing_provider_5xx(attempts: Sequence[FirecrawlAttempt]) -> int:
    consecutive = 0
    for attempt in attempts:
        if (
            attempt.status == "provider_error"
            and attempt.provider_http_status is not None
            and attempt.provider_http_status >= 500
        ):
            consecutive += 1
        else:
            consecutive = 0
    return consecutive


class _FailureEvidence(TypedDict):
    failure_code: str
    failure_message: str
    failure_transient: bool
    failure_response_sha256: str | None


def _failure_evidence(error: FirecrawlError) -> _FailureEvidence:
    return {
        "failure_code": error.failure_code,
        "failure_message": error.safe_message,
        "failure_transient": error.transient,
        "failure_response_sha256": error.response_sha256,
    }


def _page_record(
    target: FirecrawlTargetSpec,
    attempt: FirecrawlAttempt,
    *,
    raw_html: str,
) -> FirecrawlPageRecord:
    if (
        attempt.status != "succeeded"
        or attempt.artifact_path is None
        or attempt.artifact_sha256 is None
        or attempt.artifact_byte_count is None
        or attempt.reported_credits is None
    ):
        raise FirecrawlArtifactError(
            f"successful attempt {attempt.attempt_id} has incomplete metadata"
        )
    return FirecrawlPageRecord(
        target_id=target.target_id,
        target_kind=target.target_kind,
        source_url=target.source_url,
        page_number=target.page_number,
        ordinal=target.ordinal,
        attempt_id=attempt.attempt_id,
        attempt_number=attempt.attempt_number,
        raw_html=raw_html,
        artifact_path=attempt.artifact_path,
        artifact_sha256=attempt.artifact_sha256,
        artifact_byte_count=attempt.artifact_byte_count,
        reported_credits=attempt.reported_credits,
        proxy_used=attempt.proxy_used,
        target_http_status=attempt.target_http_status,
    )


def _read_verified_artifact(attempt: FirecrawlAttempt) -> str:
    if (
        attempt.artifact_path is None
        or attempt.artifact_sha256 is None
        or attempt.artifact_byte_count is None
    ):
        raise FirecrawlArtifactError(
            f"successful attempt {attempt.attempt_id} has incomplete artifact metadata"
        )
    try:
        raw = attempt.artifact_path.read_bytes()
    except OSError as error:
        raise FirecrawlArtifactError(
            f"cannot read artifact for successful attempt {attempt.attempt_id}"
        ) from error
    if len(raw) != attempt.artifact_byte_count:
        raise FirecrawlArtifactError(
            f"artifact byte count mismatch for attempt {attempt.attempt_id}"
        )
    if hashlib.sha256(raw).hexdigest() != attempt.artifact_sha256:
        raise FirecrawlArtifactError(
            f"artifact SHA-256 mismatch for attempt {attempt.attempt_id}"
        )
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise FirecrawlArtifactError(
            f"artifact is not UTF-8 for attempt {attempt.attempt_id}"
        ) from error
