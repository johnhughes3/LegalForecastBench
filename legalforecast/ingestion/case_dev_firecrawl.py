"""Bounded Case.dev-to-Firecrawl acquisition of public docket HTML."""

from __future__ import annotations

import os
import re
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Protocol, cast
from urllib.parse import urlparse

from legalforecast.ingestion.case_dev_client import (
    CaseDevAuthError,
    CaseDevClient,
    CaseDevClientError,
    CaseDevFeatureUnavailableError,
    CaseDevRateLimitError,
    CaseDevServerError,
)
from legalforecast.ingestion.courtlistener_client import CourtListenerDocket
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
    screen_case_dev_docket_metadata,
)
from legalforecast.ingestion.restricted_material import restricted_material_markers
from legalforecast.selection.exclusion_ledger import (
    ExclusionLedgerEntry,
    ExclusionReason,
    ExclusionStage,
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
    case_metadata: Mapping[str, object]

    def to_record(self) -> dict[str, object]:
        """Return a JSON-compatible manifest record."""

        return {
            "case_id": self.case_id,
            "candidate_id": self.candidate_id,
            "source_url": self.source_url,
            "docket_id": self.docket_id,
            "raw_html_path": str(self.raw_html_path),
            "case_metadata": dict(self.case_metadata),
        }


@dataclass(frozen=True, slots=True)
class CaseDevFirecrawlExclusion:
    """A ledger-safe per-candidate failure with no provider response text."""

    case_id: str
    candidate_id: str | None
    reason: str
    secondary_reasons: tuple[str, ...] = ()
    source_url: str | None = None
    docket_id: str | None = None

    def to_record(self) -> dict[str, object]:
        """Return a canonical, mergeable exclusion-ledger record."""

        return {
            "case_id": self.case_id,
            "candidate_id": self.candidate_id or self.case_id,
            "source_url": self.source_url,
            "docket_id": self.docket_id,
            "exclusion_reasons": [self.reason, *self.secondary_reasons],
            "stage": _firecrawl_exclusion_stage(self.reason).value,
            "reason": self.reason,
            "primary_exclusion_reason": self.reason,
            "secondary_exclusion_reasons": list(self.secondary_reasons),
            "source_entry_ids": [],
            "source_document_ids": [],
            "notes": (
                "Case.dev-to-Firecrawl acquisition excluded this candidate for "
                f"{self.reason}."
            ),
        }


@dataclass(frozen=True, slots=True)
class CaseDevFirecrawlResult:
    """Summary and typed records from one bounded acquisition batch."""

    successes: tuple[CaseDevFirecrawlSuccess, ...]
    exclusions: tuple[CaseDevFirecrawlExclusion, ...]
    unique_candidate_count: int
    processed_candidate_count: int
    scrape_count: int


@dataclass(frozen=True, slots=True)
class CaseDevFirecrawlScreeningResult:
    """Reconciled strict-screen outputs for persisted Firecrawl pages."""

    screened_cases: tuple[Mapping[str, Any], ...]
    exclusions: tuple[ExclusionLedgerEntry, ...]
    input_success_count: int

    @property
    def reconciled(self) -> bool:
        return self.input_success_count == len(self.screened_cases) + len(
            self.exclusions
        )


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

        if case.case_id != candidate.case_id:
            exclusions.append(
                _exclusion(candidate, reason="case_dev_identity_mismatch")
            )
            continue
        metadata_screen = screen_case_dev_docket_metadata(case.raw)
        if not metadata_screen.accepted_for_scrape:
            exclusions.append(
                _exclusion(
                    candidate,
                    reason=metadata_screen.exclusion_reasons[0],
                    secondary_reasons=metadata_screen.exclusion_reasons[1:],
                )
            )
            continue
        if case_dev_record_is_restricted(case.raw):
            exclusions.append(_exclusion(candidate, reason="restricted_case_metadata"))
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
                case_metadata=_screening_metadata_record(case.raw),
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


def screen_case_dev_firecrawl_successes(
    *,
    successes: Iterable[Mapping[str, object]],
    raw_html_directory: str | Path,
    decision_filed_on_or_after: date,
) -> CaseDevFirecrawlScreeningResult:
    """Screen persisted Firecrawl pages into planner-compatible case records.

    Every input success is reconciled to either one screened case or one
    canonical exclusion. The manifest's arbitrary path is never trusted; HTML
    is read only from ``<raw_html_directory>/<numeric docket_id>.html``.
    """

    # Import lazily to avoid the ingestion package's public re-export cycle:
    # motion_linkage imports docket_sync while ingestion.__init__ imports this
    # module. The screening kernel itself is only needed when this stage runs.
    from legalforecast.ingestion.courtlistener_acquisition import (
        screen_courtlistener_docket_html,
    )

    root = Path(raw_html_directory)
    screened_cases: list[Mapping[str, Any]] = []
    exclusions: list[ExclusionLedgerEntry] = []
    input_count = 0
    seen_docket_ids: set[str] = set()
    for record in successes:
        input_count += 1
        case_id = _manifest_string(record, "case_id")
        docket_id = _manifest_string(record, "docket_id")
        source_url = _manifest_string(record, "source_url")
        metadata = record.get("case_metadata")
        if (
            case_id is None
            or docket_id is None
            or source_url is None
            or not isinstance(metadata, Mapping)
            or _courtlistener_docket_id(source_url) != docket_id
            or not docket_id.isdigit()
        ):
            exclusions.append(
                _screening_exclusion(
                    candidate_id=_unique_exclusion_candidate_id(
                        input_index=input_count,
                    ),
                    case_id=case_id or "unknown",
                    reason=ExclusionReason.PARSE_ERROR.value,
                    notes=(
                        "Firecrawl success manifest is missing valid identity or "
                        "metadata."
                    ),
                )
            )
            continue
        if docket_id in seen_docket_ids:
            exclusions.append(
                _screening_exclusion(
                    candidate_id=_unique_exclusion_candidate_id(
                        input_index=input_count,
                    ),
                    case_id=case_id,
                    reason="duplicate_firecrawl_success",
                    notes=(
                        "Duplicate CourtListener docket ID in Firecrawl success "
                        "manifest."
                    ),
                )
            )
            continue
        seen_docket_ids.add(docket_id)
        normalized_metadata: dict[str, object] = dict(
            cast(Mapping[str, object], metadata)
        )
        if _manifest_string(normalized_metadata, "case_id") != case_id:
            exclusions.append(
                _screening_exclusion(
                    candidate_id=docket_id,
                    case_id=case_id,
                    reason=ExclusionReason.PARSE_ERROR.value,
                    notes=(
                        "Case.dev identity does not match persisted screening metadata."
                    ),
                )
            )
            continue
        if case_dev_record_is_restricted(normalized_metadata):
            exclusions.append(
                _screening_exclusion(
                    candidate_id=docket_id,
                    case_id=case_id,
                    reason="restricted_case_metadata",
                    notes=(
                        "Persisted Case.dev metadata explicitly marks the case "
                        "non-public."
                    ),
                    stage=ExclusionStage.DISCOVERY,
                )
            )
            continue
        metadata_screen = screen_case_dev_docket_metadata(normalized_metadata)
        html_path = root / f"{docket_id}.html"
        try:
            raw_html = html_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            exclusions.append(
                _screening_exclusion(
                    candidate_id=docket_id,
                    case_id=case_id,
                    reason=ExclusionReason.PARSE_ERROR.value,
                    notes=(
                        "Persisted Firecrawl docket HTML is unavailable: "
                        f"{html_path.name}."
                    ),
                )
            )
            continue
        docket = CourtListenerDocket(
            docket_id=docket_id,
            court_id=_manifest_string(normalized_metadata, "court_id"),
            docket_number=_manifest_string(normalized_metadata, "docket_number"),
            case_name=_manifest_string(normalized_metadata, "case_name") or "unknown",
            date_filed=_manifest_string(normalized_metadata, "date_filed"),
            source_url=source_url,
            raw=normalized_metadata,
        )
        screened, exclusion = screen_courtlistener_docket_html(
            docket=docket,
            metadata_screen=metadata_screen,
            raw_html=raw_html,
            decision_filed_on_or_after=decision_filed_on_or_after,
        )
        if screened is not None:
            screened_cases.append(screened)
        elif exclusion is not None:
            exclusions.append(exclusion)
        else:
            raise RuntimeError("strict Firecrawl screen returned no terminal result")
    result = CaseDevFirecrawlScreeningResult(
        screened_cases=tuple(screened_cases),
        exclusions=tuple(exclusions),
        input_success_count=input_count,
    )
    if not result.reconciled:
        raise RuntimeError("Firecrawl screening outputs do not reconcile to inputs")
    return result


def case_dev_record_is_restricted(record: Mapping[str, object]) -> bool:
    """Return whether explicit Case.dev metadata marks material non-public."""

    return any(
        restricted_material_markers(records=({key: value},))
        for key, value in _walk_mapping(record)
    )


def _screening_metadata_record(record: Mapping[str, object]) -> dict[str, object]:
    metadata = screen_case_dev_docket_metadata(record).metadata.to_record()
    aliases = {
        "date_filed": ("date_filed", "dateFiled", "filingDate"),
        "nos_macro_category": ("nos_macro_category", "nosMacroCategory"),
        "related_family_id": (
            "related_family_id",
            "relatedFamilyId",
            "related_case_family_id",
            "relatedCaseFamilyId",
        ),
        "mdl_family_id": ("mdl_family_id", "mdlFamilyId", "mdl_id", "mdlId"),
    }
    for output_key, source_keys in aliases.items():
        value = _first_record_string(record, source_keys)
        if value is not None:
            metadata[output_key] = value
    return metadata


def _walk_mapping(
    record: Mapping[str, object],
) -> Iterable[tuple[str, object]]:
    for key, value in record.items():
        yield key, value
        if isinstance(value, Mapping):
            yield from _walk_mapping(cast(Mapping[str, object], value))
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            for item in cast(Sequence[object], value):
                if isinstance(item, Mapping):
                    yield from _walk_mapping(cast(Mapping[str, object], item))


def _first_record_string(
    record: Mapping[str, object],
    keys: Sequence[str],
) -> str | None:
    for key, value in _walk_mapping(record):
        if key not in keys:
            continue
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, int) and not isinstance(value, bool):
            return str(value)
    return None


def _manifest_string(record: Mapping[str, object], key: str) -> str | None:
    value = record.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _screening_exclusion(
    *,
    candidate_id: str,
    case_id: str,
    reason: str,
    notes: str,
    stage: ExclusionStage = ExclusionStage.EXTRACTION,
) -> ExclusionLedgerEntry:
    return ExclusionLedgerEntry(
        candidate_id=candidate_id,
        case_id=case_id,
        stage=stage,
        reason=reason,
        source_entry_ids=(),
        notes=notes,
    )


def _unique_exclusion_candidate_id(
    *,
    input_index: int,
) -> str:
    return f"firecrawl-manifest-row-{input_index}"


def _firecrawl_exclusion_stage(reason: str) -> ExclusionStage:
    if reason in {
        "case_dev_provider_blocker",
        "case_dev_response_invalid",
        "firecrawl_provider_blocker",
        "firecrawl_response_invalid",
        "raw_html_path_exists",
    }:
        return ExclusionStage.RETRIEVAL
    return ExclusionStage.DISCOVERY


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
    secondary_reasons: Sequence[str] = (),
    source_url: str | None = None,
    docket_id: str | None = None,
) -> CaseDevFirecrawlExclusion:
    return CaseDevFirecrawlExclusion(
        case_id=candidate.case_id,
        candidate_id=candidate.candidate_id,
        reason=reason,
        secondary_reasons=tuple(
            secondary_reason
            for secondary_reason in secondary_reasons
            if secondary_reason and secondary_reason != reason
        ),
        source_url=source_url,
        docket_id=docket_id,
    )


def _stripped(value: str | None) -> str | None:
    return None if value is None else value.strip()
