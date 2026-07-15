"""Durable budgeted Firecrawl source for CourtListener docket HTML.

The adapter implements the discovery screen's ``fetch`` protocol while routing
every provider request through the cycle-wide Firecrawl authorization ledger.
It deliberately supports only one-credit ``basic`` proxy requests and only one
attempt for each immutable docket target.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path

from legalforecast.ingestion.budgeted_firecrawl import (
    BudgetedFirecrawlScheduler,
    FirecrawlArtifactError,
    FirecrawlTargetSpec,
)
from legalforecast.ingestion.courtlistener_client import (
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
        if expected_path.exists():
            return self.verify_existing_raw_html(
                normalized_docket_id,
                canonical_source_url,
                expected_path,
            )
        target = FirecrawlTargetSpec(
            target_id=self.target_id(normalized_docket_id),
            target_kind="docket",
            source_url=canonical_source_url,
            page_number=1,
            ordinal=int(normalized_docket_id),
        )
        scheduler = BudgetedFirecrawlScheduler(
            store=self.store,
            source=self.source,
            run_id=self.run_id,
            artifact_dir=self.raw_html_dir,
            artifact_path_resolver=self._artifact_path,
            max_attempts=1,
            max_workers=1,
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
        if len(attempts) == 1 and self._is_unavailable_attempt(attempts[0]):
            raise CourtListenerUnavailableError(
                f"CourtListener docket {normalized_docket_id} is unavailable"
            )
        failure_code = attempts[0].failure_code if len(attempts) == 1 else None
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
        unavailable_ids = {
            attempt.target_id
            for attempt in attempts
            if self._is_unavailable_attempt(attempt)
        }
        summary.update(
            {
                "schema_version": (
                    "legalforecast.budgeted_courtlistener_html_audit.v1"
                ),
                "source": "courtlistener-rest-firecrawl-html",
                "proxy": "basic",
                "max_attempts_per_target": 1,
                "successful_docket_count": sum(
                    target.status == "succeeded" for target in targets
                ),
                "unavailable_docket_count": len(unavailable_ids),
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
        if len(attempts) != 1 or attempts[0].status != "succeeded":
            raise FirecrawlArtifactError(
                f"raw docket HTML lacks one successful committed attempt for "
                f"{target_id!r}"
            )
        attempt = attempts[0]
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
