"""Bounded Case.dev-to-Firecrawl acquisition of public docket HTML."""

from __future__ import annotations

import os
import re
import tempfile
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse

from legalforecast.ingestion.case_dev_client import (
    CaseDevAuthError,
    CaseDevClient,
    CaseDevClientError,
    CaseDevFeatureUnavailableError,
    CaseDevRateLimitError,
    CaseDevServerError,
)
from legalforecast.ingestion.courtlistener_web import (
    CourtListenerWebParseError,
    parse_courtlistener_docket_html,
)
from legalforecast.ingestion.firecrawl_source import (
    FirecrawlError,
    FirecrawlResponseError,
    FirecrawlURLValidationError,
)
from legalforecast.ingestion.mtd_acquisition_screen import (
    courtlistener_public_docket_url_from_case_dev,
)

_COURTLISTENER_HOSTS = frozenset({"courtlistener.com", "www.courtlistener.com"})
_DOCKET_PATH = re.compile(r"^/docket/(?P<docket_id>[0-9]+)(?:/[^/]+)?/?$")


class CourtListenerHTMLSource(Protocol):
    """Minimal source contract implemented by the Firecrawl adapter."""

    def fetch(self, *, docket_id: str, source_url: str) -> str:
        """Return raw HTML for one public CourtListener docket URL."""

        raise NotImplementedError


class CaseDevFirecrawlBatchError(RuntimeError):
    """Fatal provider blocker carrying all safely checkpointed batch records."""

    def __init__(
        self,
        message: str,
        *,
        partial_result: CaseDevFirecrawlResult,
        provider_error: Exception,
    ) -> None:
        super().__init__(message)
        self.partial_result = partial_result
        self.provider_error = provider_error


@dataclass(frozen=True, slots=True)
class CaseDevFirecrawlCandidate:
    """One Case.dev case selected for a bounded public-page lookup."""

    case_id: str
    candidate_id: str | None = None

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            raise ValueError("candidate case_id must be a nonempty string")
        if self.candidate_id is not None and not self.candidate_id.strip():
            raise ValueError("candidate_id must be nonempty when provided")

    @classmethod
    def from_record(cls, record: Mapping[str, object]) -> CaseDevFirecrawlCandidate:
        """Parse the small candidate shape without accepting coerced values."""

        case_id = record.get("case_id")
        candidate_id = record.get("candidate_id")
        if not isinstance(case_id, str):
            raise ValueError("candidate case_id must be a nonempty string")
        if candidate_id is not None and not isinstance(candidate_id, str):
            raise ValueError("candidate_id must be a string when provided")
        return cls(case_id=case_id.strip(), candidate_id=_stripped(candidate_id))


@dataclass(frozen=True, slots=True)
class CaseDevFirecrawlSuccess:
    """A successfully persisted raw docket page."""

    case_id: str
    candidate_id: str | None
    source_url: str
    docket_id: str
    raw_html_path: Path

    def to_record(self) -> dict[str, object]:
        """Return a JSON-compatible manifest record."""

        return {
            "case_id": self.case_id,
            "candidate_id": self.candidate_id,
            "source_url": self.source_url,
            "docket_id": self.docket_id,
            "raw_html_path": str(self.raw_html_path),
        }


@dataclass(frozen=True, slots=True)
class CaseDevFirecrawlExclusion:
    """A ledger-safe per-candidate failure with no provider response text."""

    case_id: str
    candidate_id: str | None
    reason: str
    source_url: str | None = None
    docket_id: str | None = None

    def to_record(self) -> dict[str, object]:
        """Return a JSON-compatible exclusion-ledger record."""

        return {
            "case_id": self.case_id,
            "candidate_id": self.candidate_id,
            "source_url": self.source_url,
            "docket_id": self.docket_id,
            "exclusion_reasons": [self.reason],
        }


@dataclass(frozen=True, slots=True)
class CaseDevFirecrawlResult:
    """Summary and typed records from one bounded acquisition batch."""

    successes: tuple[CaseDevFirecrawlSuccess, ...]
    exclusions: tuple[CaseDevFirecrawlExclusion, ...]
    unique_candidate_count: int
    processed_candidate_count: int
    scrape_count: int


def acquire_case_dev_firecrawl_html(
    *,
    client: CaseDevClient,
    source: CourtListenerHTMLSource,
    candidates: Iterable[CaseDevFirecrawlCandidate | Mapping[str, object]],
    raw_html_directory: str | Path,
    max_candidates: int,
) -> CaseDevFirecrawlResult:
    """Fetch and persist at most ``max_candidates`` unique public dockets.

    Candidates are deduplicated by Case.dev case ID in input order before the
    explicit limit is applied. Authentication, payment, rate-limit, feature,
    and server failures are intentionally not caught, so the batch stops at
    the first provider-level blocker.
    """

    if max_candidates <= 0:
        raise ValueError("max_candidates must be positive")
    unique_candidates = _deduplicated_candidates(candidates)
    selected_candidates = unique_candidates[:max_candidates]
    output_directory = Path(raw_html_directory)
    output_directory.mkdir(parents=True, exist_ok=True)

    successes: list[CaseDevFirecrawlSuccess] = []
    exclusions: list[CaseDevFirecrawlExclusion] = []
    scrape_count = 0
    processed_candidate_count = 0
    for candidate_index, candidate in enumerate(selected_candidates):
        processed_candidate_count += 1
        try:
            case = client.get_case(candidate.case_id)
        except (
            CaseDevAuthError,
            CaseDevRateLimitError,
            CaseDevServerError,
            CaseDevFeatureUnavailableError,
        ) as error:
            exclusions.append(_exclusion(candidate, reason="case_dev_provider_blocker"))
            raise _batch_error(
                error,
                successes=successes,
                exclusions=exclusions,
                unique_candidate_count=len(unique_candidates),
                processed_candidate_count=processed_candidate_count,
                scrape_count=scrape_count,
                deferred_candidates=(
                    *selected_candidates[candidate_index + 1 :],
                    *unique_candidates[max_candidates:],
                ),
            ) from error
        except CaseDevClientError:
            exclusions.append(_exclusion(candidate, reason="case_dev_response_invalid"))
            continue

        source_url = courtlistener_public_docket_url_from_case_dev(case.raw)
        if source_url is None:
            exclusions.append(_exclusion(candidate, reason="courtlistener_url_missing"))
            continue
        docket_id = _courtlistener_docket_id(source_url)
        if docket_id is None:
            exclusions.append(
                _exclusion(
                    candidate,
                    reason="courtlistener_url_malformed",
                    source_url=source_url,
                )
            )
            continue

        destination = output_directory / f"{docket_id}.html"
        if destination.exists():
            exclusions.append(
                _exclusion(
                    candidate,
                    reason="raw_html_path_exists",
                    source_url=source_url,
                    docket_id=docket_id,
                )
            )
            continue
        try:
            raw_html = source.fetch(docket_id=docket_id, source_url=source_url)
            scrape_count += 1
        except FirecrawlURLValidationError:
            scrape_count += 1
            exclusions.append(
                _exclusion(
                    candidate,
                    reason="courtlistener_url_malformed",
                    source_url=source_url,
                    docket_id=docket_id,
                )
            )
            continue
        except FirecrawlResponseError:
            scrape_count += 1
            exclusions.append(
                _exclusion(
                    candidate,
                    reason="firecrawl_response_invalid",
                    source_url=source_url,
                    docket_id=docket_id,
                )
            )
            continue
        except FirecrawlError as error:
            scrape_count += 1
            exclusions.append(
                _exclusion(
                    candidate,
                    reason="firecrawl_provider_blocker",
                    source_url=source_url,
                    docket_id=docket_id,
                )
            )
            raise _batch_error(
                error,
                successes=successes,
                exclusions=exclusions,
                unique_candidate_count=len(unique_candidates),
                processed_candidate_count=processed_candidate_count,
                scrape_count=scrape_count,
                deferred_candidates=(
                    *selected_candidates[candidate_index + 1 :],
                    *unique_candidates[max_candidates:],
                ),
            ) from error

        if not raw_html.strip():
            exclusions.append(
                _exclusion(
                    candidate,
                    reason="firecrawl_response_invalid",
                    source_url=source_url,
                    docket_id=docket_id,
                )
            )
            continue
        try:
            parse_courtlistener_docket_html(
                raw_html,
                source_url=source_url,
                docket_id=docket_id,
            )
        except CourtListenerWebParseError:
            exclusions.append(
                _exclusion(
                    candidate,
                    reason="firecrawl_response_invalid",
                    source_url=source_url,
                    docket_id=docket_id,
                )
            )
            continue
        try:
            _atomic_write_new(destination, raw_html)
        except FileExistsError:
            exclusions.append(
                _exclusion(
                    candidate,
                    reason="raw_html_path_exists",
                    source_url=source_url,
                    docket_id=docket_id,
                )
            )
            continue
        successes.append(
            CaseDevFirecrawlSuccess(
                case_id=candidate.case_id,
                candidate_id=candidate.candidate_id,
                source_url=source_url,
                docket_id=docket_id,
                raw_html_path=destination,
            )
        )

    exclusions.extend(
        _exclusion(candidate, reason="candidate_limit_deferred")
        for candidate in unique_candidates[max_candidates:]
    )
    return CaseDevFirecrawlResult(
        successes=tuple(successes),
        exclusions=tuple(exclusions),
        unique_candidate_count=len(unique_candidates),
        processed_candidate_count=processed_candidate_count,
        scrape_count=scrape_count,
    )


def _batch_error(
    error: Exception,
    *,
    successes: list[CaseDevFirecrawlSuccess],
    exclusions: list[CaseDevFirecrawlExclusion],
    unique_candidate_count: int,
    processed_candidate_count: int,
    scrape_count: int,
    deferred_candidates: tuple[CaseDevFirecrawlCandidate, ...],
) -> CaseDevFirecrawlBatchError:
    return CaseDevFirecrawlBatchError(
        f"provider blocker: {type(error).__name__}",
        partial_result=CaseDevFirecrawlResult(
            successes=tuple(successes),
            exclusions=(
                *exclusions,
                *(
                    _exclusion(candidate, reason="provider_blocker_deferred")
                    for candidate in deferred_candidates
                ),
            ),
            unique_candidate_count=unique_candidate_count,
            processed_candidate_count=processed_candidate_count,
            scrape_count=scrape_count,
        ),
        provider_error=error,
    )


def _deduplicated_candidates(
    candidates: Iterable[CaseDevFirecrawlCandidate | Mapping[str, object]],
) -> list[CaseDevFirecrawlCandidate]:
    unique: list[CaseDevFirecrawlCandidate] = []
    seen_case_ids: set[str] = set()
    for candidate_record in candidates:
        candidate = (
            candidate_record
            if isinstance(candidate_record, CaseDevFirecrawlCandidate)
            else CaseDevFirecrawlCandidate.from_record(candidate_record)
        )
        if candidate.case_id in seen_case_ids:
            continue
        seen_case_ids.add(candidate.case_id)
        unique.append(candidate)
    return unique


def _courtlistener_docket_id(source_url: str) -> str | None:
    parsed = urlparse(source_url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in _COURTLISTENER_HOSTS
        or parsed.port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.params
    ):
        return None
    match = _DOCKET_PATH.fullmatch(parsed.path)
    return None if match is None else match.group("docket_id")


def _atomic_write_new(destination: Path, content: str) -> None:
    file_descriptor, temporary_name = tempfile.mkstemp(
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary_path, destination)
    finally:
        temporary_path.unlink(missing_ok=True)


def _exclusion(
    candidate: CaseDevFirecrawlCandidate,
    *,
    reason: str,
    source_url: str | None = None,
    docket_id: str | None = None,
) -> CaseDevFirecrawlExclusion:
    return CaseDevFirecrawlExclusion(
        case_id=candidate.case_id,
        candidate_id=candidate.candidate_id,
        reason=reason,
        source_url=source_url,
        docket_id=docket_id,
    )


def _stripped(value: str | None) -> str | None:
    return None if value is None else value.strip()
