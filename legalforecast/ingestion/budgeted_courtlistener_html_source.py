"""Durable budgeted Firecrawl source for CourtListener docket HTML.

The adapter implements the discovery screen's ``fetch`` protocol while routing
every provider request through the cycle-wide Firecrawl authorization ledger.
It deliberately supports only one-credit ``basic`` proxy requests and at most
three durably accounted attempts for each immutable docket target.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from pathlib import Path

from legalforecast.ingestion.budgeted_firecrawl import (
    BudgetedFirecrawlScheduler,
    FirecrawlArtifactError,
    FirecrawlTargetSpec,
    is_retryable_target_accepted,
)
from legalforecast.ingestion.courtlistener_client import (
    CourtListenerProviderExhaustedError,
    CourtListenerUnavailableError,
)
from legalforecast.ingestion.cycle_acquisition_store import (
    CycleAcquisitionStore,
    FirecrawlAttempt,
)
from legalforecast.ingestion.firecrawl_source import (
    FirecrawlCourtListenerHTMLSource,
    canonicalize_courtlistener_source_url,
    validate_courtlistener_docket_url,
)

_TARGET_PREFIX = "courtlistener-docket:"
_UNAVAILABLE_TARGET_STATUSES = frozenset({404, 410})
_SHA256 = re.compile(r"[0-9a-f]{64}")
_MAX_ATTEMPTS_PER_TARGET = 3


class DurableBudgetedCourtListenerHTMLSource:
    """Fetch one immutable CourtListener docket through durable authorization."""

    def __init__(
        self,
        *,
        store: CycleAcquisitionStore,
        source: FirecrawlCourtListenerHTMLSource,
        run_id: str,
        raw_html_dir: str | Path,
    ) -> None:
        if source.config.proxy != "basic":
            raise ValueError(
                "durable CourtListener docket HTML requires Firecrawl's basic proxy"
            )
        if not run_id.strip():
            raise ValueError("run_id must be nonempty")
        self.store = store
        self.source = source
        self.run_id = run_id
        self.raw_html_dir = Path(raw_html_dir).resolve()

    def fetch(self, *, docket_id: str, source_url: str) -> str:
        """Return verified HTML or a durable unavailable/fail-closed outcome.

        URL and expected docket identity validation happens before the scheduler
        is allowed to create a target or reserve credits. The canonical URL is
        the immutable source identity, independent of presentation slugs.
        """

        normalized_docket_id = validate_courtlistener_docket_url(
            source_url,
            expected_docket_id=docket_id,
        )
        canonical_source_url = canonicalize_courtlistener_source_url(source_url)
        expected_path = self.raw_html_dir / f"{normalized_docket_id}.html"
        target = FirecrawlTargetSpec(
            target_id=self.target_id(normalized_docket_id),
            target_kind="docket",
            source_url=canonical_source_url,
            page_number=1,
            ordinal=int(normalized_docket_id),
        )
        existing_target = any(
            stored.target_id == target.target_id
            for stored in self.store.firecrawl_targets(self.run_id)
        )
        if expected_path.exists() and not existing_target:
            return self.verify_existing_raw_html(
                normalized_docket_id,
                canonical_source_url,
                expected_path,
            )
        scheduler = BudgetedFirecrawlScheduler(
            store=self.store,
            source=self.source,
            run_id=self.run_id,
            artifact_dir=self.raw_html_dir,
            artifact_path_resolver=self._artifact_path,
            max_attempts=_MAX_ATTEMPTS_PER_TARGET,
            max_workers=1,
            terminalize_abandoned_authorizations=True,
        )
        result = scheduler.run((target,))
        if len(result.pages) == 1:
            return result.pages[0].raw_html
        if result.pages:
            raise FirecrawlArtifactError(
                f"docket target {target.target_id!r} produced multiple artifacts"
            )

        attempts = tuple(
            attempt
            for attempt in self.store.firecrawl_attempts(self.run_id)
            if attempt.target_id == target.target_id and attempt.page_number == 1
        )
        terminal_attempt = attempts[-1] if attempts else None
        if terminal_attempt is not None and self._is_unavailable_attempt(
            terminal_attempt
        ):
            raise CourtListenerUnavailableError(
                f"CourtListener docket {normalized_docket_id} is unavailable"
            )
        if terminal_attempt is not None and self._is_abandoned_attempt(
            terminal_attempt
        ):
            if terminal_attempt.failure_code == "authorization_abandoned_with_orphan":
                self._quarantine_abandoned_raw_html(
                    normalized_docket_id,
                    terminal_attempt,
                    expected_path,
                )
            raise CourtListenerUnavailableError(
                f"CourtListener docket {normalized_docket_id} acquisition was "
                "interrupted after durable authorization; the original credit "
                "reservation was retained"
            )
        if terminal_attempt is not None and self._is_result_commit_failure(
            terminal_attempt
        ):
            if terminal_attempt.failure_code == "result_commit_failed_with_orphan":
                self._quarantine_abandoned_raw_html(
                    normalized_docket_id,
                    terminal_attempt,
                    expected_path,
                )
            raise FirecrawlArtifactError(
                f"durable Firecrawl target {target.target_id!r} has a terminal "
                f"local commit failure ({terminal_attempt.failure_code})"
            )
        if self._is_exhausted_provider_lineage(attempts):
            self.store.set_firecrawl_target_status(
                self.run_id,
                target.target_id,
                "terminal_error",
            )
            raise CourtListenerProviderExhaustedError(
                f"CourtListener docket {normalized_docket_id} acquisition exhausted "
                f"{_MAX_ATTEMPTS_PER_TARGET} bounded provider attempts"
            )
        failure_code = terminal_attempt.failure_code if terminal_attempt else None
        detail = f" ({failure_code})" if failure_code is not None else ""
        raise FirecrawlArtifactError(
            f"durable Firecrawl target {target.target_id!r} did not produce a "
            f"verified docket artifact{detail}"
        )

    def audit_summary(self) -> Mapping[str, object]:
        """Return cumulative durable budget and terminal-target accounting."""

        summary = dict(self.store.firecrawl_run_summary(self.run_id))
        attempts = self.store.firecrawl_attempts(self.run_id)
        targets = self.store.firecrawl_targets(self.run_id)
        provider_unavailable_ids = {
            attempt.target_id
            for attempt in attempts
            if self._is_unavailable_attempt(attempt)
        }
        abandoned_ids = {
            attempt.target_id
            for attempt in attempts
            if self._is_abandoned_attempt(attempt)
        }
        provider_exhausted_ids = {
            target.target_id
            for target in targets
            if self._is_exhausted_provider_lineage(
                tuple(
                    attempt
                    for attempt in attempts
                    if attempt.target_id == target.target_id
                )
            )
        }
        unavailable_ids = (
            provider_unavailable_ids | abandoned_ids | provider_exhausted_ids
        )
        summary.update(
            {
                "schema_version": (
                    "legalforecast.budgeted_courtlistener_html_audit.v1"
                ),
                "source": "courtlistener-rest-firecrawl-html",
                "proxy": "basic",
                "max_attempts_per_target": _MAX_ATTEMPTS_PER_TARGET,
                "successful_docket_count": sum(
                    target.status == "succeeded" for target in targets
                ),
                "unavailable_docket_count": len(unavailable_ids),
                "provider_unavailable_docket_count": len(provider_unavailable_ids),
                "provider_exhausted_docket_count": len(provider_exhausted_ids),
                "abandoned_docket_count": len(abandoned_ids),
                "target_count": len(targets),
            }
        )
        return summary

    def verify_existing_raw_html(
        self,
        docket_id: str,
        source_url: str,
        path: Path,
    ) -> str:
        """Verify a raw file against its immutable target and attempt commitment.

        This method is intentionally read-only. An untracked file cannot create a
        target, reserve credits, or become trusted merely because its name looks
        like a docket identifier.
        """

        normalized_docket_id = validate_courtlistener_docket_url(
            source_url,
            expected_docket_id=docket_id,
        )
        canonical_source_url = canonicalize_courtlistener_source_url(source_url)
        target_id = self.target_id(normalized_docket_id)
        expected_path = (self.raw_html_dir / f"{normalized_docket_id}.html").resolve()
        if path.resolve() != expected_path:
            raise FirecrawlArtifactError(
                f"raw docket HTML path does not match durable target {target_id!r}"
            )

        targets = tuple(
            target
            for target in self.store.firecrawl_targets(self.run_id)
            if target.target_id == target_id
        )
        if len(targets) != 1:
            raise FirecrawlArtifactError(
                f"raw docket HTML has no unique durable target {target_id!r}"
            )
        target = targets[0]
        if (
            target.target_kind != "docket"
            or target.source_url != canonical_source_url
            or target.ordinal != int(normalized_docket_id)
            or target.status != "succeeded"
        ):
            raise FirecrawlArtifactError(
                f"raw docket HTML target commitment mismatch for {target_id!r}"
            )

        attempts = tuple(
            attempt
            for attempt in self.store.firecrawl_attempts(self.run_id)
            if attempt.target_id == target_id and attempt.page_number == 1
        )
        successful = tuple(
            attempt for attempt in attempts if attempt.status == "succeeded"
        )
        if (
            not attempts
            or len(attempts) > _MAX_ATTEMPTS_PER_TARGET
            or len(successful) != 1
            or successful[0] != attempts[-1]
            or any(not self._is_retryable_attempt(attempt) for attempt in attempts[:-1])
        ):
            raise FirecrawlArtifactError(
                f"raw docket HTML lacks a bounded successful attempt lineage for "
                f"{target_id!r}"
            )
        attempt = successful[0]
        if (
            attempt.request_url != canonical_source_url
            or attempt.artifact_path != expected_path
            or attempt.artifact_sha256 is None
            or attempt.artifact_byte_count is None
            or attempt.target_http_status != 200
        ):
            raise FirecrawlArtifactError(
                f"raw docket HTML attempt commitment mismatch for {target_id!r}"
            )
        try:
            raw = expected_path.read_bytes()
        except OSError as error:
            raise FirecrawlArtifactError(
                f"cannot read committed raw docket HTML for {target_id!r}"
            ) from error
        if (
            len(raw) != attempt.artifact_byte_count
            or hashlib.sha256(raw).hexdigest() != attempt.artifact_sha256
        ):
            raise FirecrawlArtifactError(
                f"raw docket HTML artifact hash mismatch for {target_id!r}"
            )
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError as error:
            raise FirecrawlArtifactError(
                f"raw docket HTML is not UTF-8 for {target_id!r}"
            ) from error

    def successful_artifact_receipts(
        self,
        *,
        batch_digest: str,
    ) -> Mapping[str, Mapping[str, object]]:
        """Return source-and-batch-bound receipts for every successful docket."""

        if _SHA256.fullmatch(batch_digest) is None:
            raise ValueError("batch_digest must be a lowercase SHA-256 digest")
        targets = {
            target.target_id: target
            for target in self.store.firecrawl_targets(self.run_id)
            if target.status == "succeeded"
        }
        attempts = self.store.firecrawl_attempts(self.run_id)
        receipts: dict[str, Mapping[str, object]] = {}
        for target_id, target in sorted(targets.items()):
            if not target_id.startswith(_TARGET_PREFIX):
                raise FirecrawlArtifactError(
                    "successful Firecrawl run contains a non-docket target"
                )
            docket_id = target_id.removeprefix(_TARGET_PREFIX)
            path = self.raw_html_dir / f"{docket_id}.html"
            self.verify_existing_raw_html(docket_id, target.source_url, path)
            matching = tuple(
                attempt
                for attempt in attempts
                if attempt.target_id == target_id
                and attempt.page_number == 1
                and attempt.status == "succeeded"
            )
            if len(matching) != 1:
                raise FirecrawlArtifactError(
                    f"successful docket target {target_id!r} lacks one receipt"
                )
            attempt = matching[0]
            receipts[docket_id] = {
                "schema_version": (
                    "legalforecast.firecrawl_docket_html_source_receipt.v1"
                ),
                "docket_html_source": "firecrawl",
                "batch_digest": batch_digest,
                "firecrawl_run_id": self.run_id,
                "firecrawl_target_id": target_id,
                "firecrawl_attempt_id": attempt.attempt_id,
                "request_url": attempt.request_url,
                "reserved_credits": attempt.reserved_credits,
                "reported_credits": attempt.reported_credits,
                "proxy_used": attempt.proxy_used,
                "target_http_status": attempt.target_http_status,
                "artifact_sha256": attempt.artifact_sha256,
                "artifact_byte_count": attempt.artifact_byte_count,
                "authorized_at": attempt.authorized_at,
                "completed_at": attempt.completed_at,
            }
        return receipts

    @staticmethod
    def target_id(docket_id: str) -> str:
        """Return the immutable scheduler identity for one numeric docket."""

        if not docket_id.isascii() or not docket_id.isdigit():
            raise ValueError("CourtListener docket ID must be numeric")
        return f"{_TARGET_PREFIX}{docket_id}"

    def _artifact_path(self, target: FirecrawlTargetSpec) -> Path:
        if target.target_kind != "docket" or not target.target_id.startswith(
            _TARGET_PREFIX
        ):
            raise FirecrawlArtifactError(
                "durable CourtListener source received a non-docket target"
            )
        docket_id = target.target_id.removeprefix(_TARGET_PREFIX)
        if self.target_id(docket_id) != target.target_id:
            raise FirecrawlArtifactError(
                "durable CourtListener source received an invalid target identity"
            )
        return self.raw_html_dir / f"{docket_id}.html"

    @staticmethod
    def _is_unavailable_attempt(attempt: FirecrawlAttempt) -> bool:
        return (
            attempt.status == "target_error"
            and attempt.failure_code == "target_http_status_invalid"
            and attempt.target_http_status in _UNAVAILABLE_TARGET_STATUSES
        )

    @staticmethod
    def _is_abandoned_attempt(attempt: FirecrawlAttempt) -> bool:
        return (
            attempt.status == "interrupted"
            and attempt.failure_code
            in {
                "authorization_abandoned",
                "authorization_abandoned_with_orphan",
            }
            and attempt.failure_transient is False
        )

    @staticmethod
    def _is_result_commit_failure(attempt: FirecrawlAttempt) -> bool:
        return (
            attempt.status == "interrupted"
            and attempt.failure_code
            in {
                "result_commit_failed",
                "result_commit_failed_with_orphan",
            }
            and attempt.failure_transient is False
        )

    @staticmethod
    def _is_retryable_attempt(attempt: FirecrawlAttempt) -> bool:
        return (
            (
                attempt.status in {"provider_error", "transport_error"}
                and attempt.failure_transient is True
            )
            or is_retryable_target_accepted(attempt)
        ) and (
            attempt.artifact_path is None
            and attempt.artifact_sha256 is None
            and attempt.artifact_byte_count is None
        )

    @classmethod
    def _is_exhausted_provider_lineage(
        cls,
        attempts: tuple[FirecrawlAttempt, ...],
    ) -> bool:
        return (
            len(attempts) == _MAX_ATTEMPTS_PER_TARGET
            and [attempt.attempt_number for attempt in attempts]
            == list(range(1, _MAX_ATTEMPTS_PER_TARGET + 1))
            and all(cls._is_retryable_attempt(attempt) for attempt in attempts)
        )

    def _quarantine_abandoned_raw_html(
        self,
        docket_id: str,
        attempt: FirecrawlAttempt,
        path: Path,
    ) -> None:
        """Move an unreceipted crash orphan outside packet-bound raw artifacts."""

        if not path.exists():
            return
        if path.is_symlink() or not path.is_file():
            raise FirecrawlArtifactError(
                f"abandoned raw docket artifact is not a regular file: {path}"
            )
        try:
            content = path.read_bytes()
        except OSError as error:
            raise FirecrawlArtifactError(
                f"cannot read abandoned raw docket artifact: {path}"
            ) from error
        digest = hashlib.sha256(content).hexdigest()
        quarantine_dir = (
            self.store.path.resolve().parent / "firecrawl-untrusted-orphans"
        )
        quarantine_dir.mkdir(parents=True, exist_ok=True)
        destination = quarantine_dir / (
            f"docket-{docket_id}-attempt-{attempt.attempt_id}-{digest}.html"
        )
        if destination.exists():
            if destination.is_symlink() or not destination.is_file():
                raise FirecrawlArtifactError(
                    f"abandoned artifact quarantine path is unsafe: {destination}"
                )
            if destination.read_bytes() != content:
                raise FirecrawlArtifactError(
                    "abandoned artifact quarantine commitment mismatch"
                )
            path.unlink()
            return
        try:
            path.replace(destination)
        except OSError as error:
            raise FirecrawlArtifactError(
                f"cannot quarantine abandoned raw docket artifact: {path}"
            ) from error
