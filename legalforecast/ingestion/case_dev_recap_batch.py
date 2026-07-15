"""Pure batch reconciliation for free Case.dev enrichment of RECAP discoveries."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import cast
from urllib.parse import urlsplit

from legalforecast.ingestion.case_dev_client import (
    CaseDevAuthError,
    CaseDevClient,
    CaseDevClientError,
    CaseDevRateLimitError,
    CaseDevServerError,
)
from legalforecast.ingestion.case_dev_ranked_selection import (
    CASE_DEV_SOURCE_DOCKET_SCHEMA,
)
from legalforecast.ingestion.case_dev_recap_enrichment import (
    CaseDevRecapEnrichment,
    CaseDevRecapEnrichmentError,
    CaseDevRecapLookupTarget,
    enrich_recap_docket_with_case_dev,
    rank_case_dev_recap_enrichments,
)
from legalforecast.ingestion.firecrawl_recap_discovery import RecapDiscoveredDocket

_DOCKET_ID = re.compile(r"[1-9][0-9]*")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_DOCKET_PATH = re.compile(r"^/docket/(?P<docket_id>[1-9][0-9]*)/[^/]+/$")
_COURTLISTENER_HOST = "www.courtlistener.com"


class RecapDocketRecordError(ValueError):
    """Raised with a stable reason when a discovery record is not canonical."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class CaseDevRecapBatchFailure:
    """One input record that could not produce verified enrichment output."""

    input_index: int
    candidate_id: str | None
    docket_id: str | None
    stage: str
    reason: str
    detail: str

    def to_record(self) -> dict[str, object]:
        return {
            "input_index": self.input_index,
            "candidate_id": self.candidate_id,
            "docket_id": self.docket_id,
            "stage": self.stage,
            "reason": self.reason,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class CaseDevRecapBatchSummary:
    """Reconciled funnel counts for one enrichment batch."""

    input_record_count: int
    converted_docket_count: int
    enrichment_attempt_count: int
    successful_docket_count: int
    failure_count: int
    conversion_failure_count: int
    enrichment_failure_count: int
    failure_reason_counts: tuple[tuple[str, int], ...]
    actual_free_required_document_count: int
    missing_required_document_count: int
    reconciled: bool

    def to_record(self) -> dict[str, object]:
        return {
            "input_record_count": self.input_record_count,
            "converted_docket_count": self.converted_docket_count,
            "enrichment_attempt_count": self.enrichment_attempt_count,
            "successful_docket_count": self.successful_docket_count,
            "failure_count": self.failure_count,
            "conversion_failure_count": self.conversion_failure_count,
            "enrichment_failure_count": self.enrichment_failure_count,
            "failure_reason_counts": dict(self.failure_reason_counts),
            "actual_free_required_document_count": (
                self.actual_free_required_document_count
            ),
            "missing_required_document_count": self.missing_required_document_count,
            "reconciled": self.reconciled,
        }


@dataclass(frozen=True, slots=True)
class CaseDevRecapBatchResult:
    """Deterministically ranked successes and input-ordered failures."""

    successes: tuple[CaseDevRecapEnrichment, ...]
    failures: tuple[CaseDevRecapBatchFailure, ...]
    summary: CaseDevRecapBatchSummary

    @property
    def reconciled(self) -> bool:
        return self.summary.reconciled

    def to_record(self) -> dict[str, object]:
        return {
            "summary": self.summary.to_record(),
            "successes": [success.to_record() for success in self.successes],
            "failures": [failure.to_record() for failure in self.failures],
        }


def recap_discovered_docket_from_record(
    record: Mapping[str, object],
) -> RecapDiscoveredDocket:
    """Convert one discovery JSON record without accepting schema ambiguity."""

    candidate_id = _required_string(record, "candidate_id", "candidate_id_invalid")
    docket_id = _required_string(record, "docket_id", "docket_id_invalid")
    if _DOCKET_ID.fullmatch(docket_id) is None:
        raise RecapDocketRecordError(
            "docket_id_invalid",
            "docket_id must be a canonical positive integer string",
        )
    if candidate_id != f"courtlistener-docket-{docket_id}":
        raise RecapDocketRecordError(
            "candidate_id_mismatch",
            "candidate_id does not match the CourtListener docket identity",
        )
    docket_url = _required_string(record, "docket_url", "docket_url_invalid")
    _validate_docket_url(docket_url, docket_id=docket_id)
    entry_keys = _required_string_list(record, "entry_keys")
    matched_terms = _required_string_list(record, "matched_terms")
    eligibility_status = _required_string(
        record,
        "eligibility_status",
        "eligibility_status_invalid",
    )
    if eligibility_status != "potential_unverified":
        raise RecapDocketRecordError(
            "eligibility_status_invalid",
            "discovered docket must remain potential_unverified before enrichment",
        )
    return RecapDiscoveredDocket(
        docket_id=docket_id,
        docket_url=docket_url,
        entry_keys=entry_keys,
        matched_terms=matched_terms,
    )


def case_dev_recap_lookup_target_from_record(
    record: Mapping[str, object],
    *,
    allow_source_bound: bool = False,
) -> RecapDiscoveredDocket | CaseDevRecapLookupTarget:
    """Convert legacy discovery or a source-bound exact-ID projection."""

    if record.get("schema_version") != CASE_DEV_SOURCE_DOCKET_SCHEMA:
        return recap_discovered_docket_from_record(record)
    if not allow_source_bound:
        raise RecapDocketRecordError(
            "source_schema_not_authorized",
            "source-bound exact-ID records require a verified source projection",
        )
    candidate_id = _required_string(record, "candidate_id", "candidate_id_invalid")
    docket_id = _required_string(record, "docket_id", "docket_id_invalid")
    if _DOCKET_ID.fullmatch(docket_id) is None:
        raise RecapDocketRecordError(
            "docket_id_invalid",
            "docket_id must be a canonical positive integer string",
        )
    if candidate_id != f"courtlistener-docket-{docket_id}":
        raise RecapDocketRecordError(
            "candidate_id_mismatch",
            "candidate_id does not match the CourtListener docket identity",
        )
    if "docket_url" in record:
        raise RecapDocketRecordError(
            "source_docket_url_forbidden",
            "source-bound exact-ID projections must not synthesize a docket URL",
        )
    entry_keys = _required_string_list(record, "entry_keys")
    matched_terms = _required_string_list(record, "matched_terms")
    eligibility_status = _required_string(
        record,
        "eligibility_status",
        "eligibility_status_invalid",
    )
    if eligibility_status != "potential_unverified":
        raise RecapDocketRecordError(
            "eligibility_status_invalid",
            "source docket must remain potential_unverified before enrichment",
        )
    lineage = record.get("source_lineage")
    if not isinstance(lineage, Mapping):
        raise RecapDocketRecordError(
            "source_lineage_invalid",
            "source-bound exact-ID projection requires source_lineage",
        )
    typed_lineage = cast(Mapping[str, object], lineage)
    lineage_docket_id = typed_lineage.get("docket_id")
    if lineage_docket_id != docket_id:
        raise RecapDocketRecordError(
            "source_lineage_docket_id_mismatch",
            "source lineage docket ID does not match the projected docket",
        )
    for field_name in (
        "source_batch_id",
        "source_batch_digest",
        "source_cycle_hash",
        "source_candidate_set_sha256",
    ):
        _required_string(typed_lineage, field_name, "source_lineage_invalid")
    if typed_lineage.get("source_search_type") != "o":
        raise RecapDocketRecordError(
            "source_lineage_invalid",
            "source lineage must identify CourtListener opinion search_type=o",
        )
    for field_name in (
        "source_batch_digest",
        "source_cycle_hash",
        "source_candidate_set_sha256",
    ):
        value = _required_string(
            typed_lineage,
            field_name,
            "source_lineage_invalid",
        )
        if _SHA256.fullmatch(value) is None:
            raise RecapDocketRecordError(
                "source_lineage_invalid",
                f"{field_name} must be a lowercase SHA-256 digest",
            )
    lead_commitment = typed_lineage.get("lead_commitment")
    source_hits = typed_lineage.get("source_hits")
    if not isinstance(lead_commitment, Mapping) or not isinstance(source_hits, list):
        raise RecapDocketRecordError(
            "source_lineage_invalid",
            "source lineage requires lead_commitment and source_hits",
        )
    typed_lead = cast(Mapping[str, object], lead_commitment)
    if (
        typed_lead.get("docket_id") != docket_id
        or typed_lead.get("source_hits") != source_hits
    ):
        raise RecapDocketRecordError(
            "source_lineage_invalid",
            "source lead commitment does not match the projected docket and hits",
        )
    projected_hit_keys: list[str] = []
    projected_terms: list[str] = []
    for source_hit in cast(list[object], source_hits):
        if not isinstance(source_hit, Mapping):
            raise RecapDocketRecordError(
                "source_lineage_invalid",
                "source lineage hit is not an object",
            )
        typed_hit = cast(Mapping[str, object], source_hit)
        provider_hit_id = _required_string(
            typed_hit,
            "provider_hit_id",
            "source_lineage_invalid",
        )
        query_term = _required_string(
            typed_hit,
            "query_term",
            "source_lineage_invalid",
        )
        payload_sha256 = _required_string(
            typed_hit,
            "payload_sha256",
            "source_lineage_invalid",
        )
        if _SHA256.fullmatch(payload_sha256) is None:
            raise RecapDocketRecordError(
                "source_lineage_invalid",
                "source hit payload_sha256 is not a lowercase SHA-256 digest",
            )
        projected_hit_keys.append(provider_hit_id)
        projected_terms.append(query_term)
    if (
        tuple(sorted(set(projected_hit_keys))) != entry_keys
        or tuple(sorted(set(projected_terms))) != matched_terms
    ):
        raise RecapDocketRecordError(
            "source_lineage_invalid",
            "source hit provenance does not match entry_keys and matched_terms",
        )
    return CaseDevRecapLookupTarget(
        docket_id=docket_id,
        docket_url=None,
        entry_keys=entry_keys,
        matched_terms=matched_terms,
    )


def enrich_recap_discovery_batch(
    *,
    client: CaseDevClient,
    records: Iterable[Mapping[str, object]],
    page_size: int = 100,
    max_pages: int = 100,
    allow_source_bound: bool = False,
    eligibility_anchor: date | None = None,
) -> CaseDevRecapBatchResult:
    """Convert and enrich every record into exactly one terminal batch result."""

    if type(page_size) is not int or page_size <= 0:
        raise ValueError("page_size must be a positive integer")
    if type(max_pages) is not int or max_pages <= 0:
        raise ValueError("max_pages must be a positive integer")
    materialized = tuple(records)
    failures: list[CaseDevRecapBatchFailure] = []
    enrichments: list[CaseDevRecapEnrichment] = []
    seen_dockets: set[str] = set()
    converted_docket_count = 0
    enrichment_attempt_count = 0

    for input_index, record in enumerate(materialized):
        candidate_id = _best_effort_string(record, "candidate_id")
        docket_id = _best_effort_string(record, "docket_id")
        try:
            discovery = case_dev_recap_lookup_target_from_record(
                record,
                allow_source_bound=allow_source_bound,
            )
        except RecapDocketRecordError as error:
            failures.append(
                CaseDevRecapBatchFailure(
                    input_index=input_index,
                    candidate_id=candidate_id,
                    docket_id=docket_id,
                    stage="discovery_record",
                    reason=error.reason,
                    detail=str(error),
                )
            )
            continue
        if discovery.docket_id in seen_dockets:
            failures.append(
                CaseDevRecapBatchFailure(
                    input_index=input_index,
                    candidate_id=candidate_id,
                    docket_id=discovery.docket_id,
                    stage="discovery_record",
                    reason="duplicate_discovered_docket",
                    detail=(
                        "a prior input record already claimed this CourtListener "
                        "docket identity"
                    ),
                )
            )
            continue
        seen_dockets.add(discovery.docket_id)
        converted_docket_count += 1
        enrichment_attempt_count += 1
        try:
            enrichment = enrich_recap_docket_with_case_dev(
                client=client,
                discovery=discovery,
                page_size=page_size,
                max_pages=max_pages,
                eligibility_anchor=eligibility_anchor,
            )
        except (CaseDevAuthError, CaseDevRateLimitError, CaseDevServerError):
            raise
        except (CaseDevRecapEnrichmentError, CaseDevClientError) as error:
            failures.append(
                CaseDevRecapBatchFailure(
                    input_index=input_index,
                    candidate_id=candidate_id,
                    docket_id=discovery.docket_id,
                    stage="case_dev_enrichment",
                    reason=_enrichment_failure_reason(error),
                    detail=str(error),
                )
            )
            continue
        enrichments.append(enrichment)

    successes = rank_case_dev_recap_enrichments(enrichments)
    conversion_failure_count = sum(
        failure.stage == "discovery_record" for failure in failures
    )
    enrichment_failure_count = sum(
        failure.stage == "case_dev_enrichment" for failure in failures
    )
    reconciled = (
        len(materialized) == len(successes) + len(failures)
        and converted_docket_count
        == len(successes) + enrichment_failure_count
        == enrichment_attempt_count
        and len(failures) == conversion_failure_count + enrichment_failure_count
    )
    if not reconciled:
        raise RuntimeError("Case.dev RECAP batch outputs do not reconcile to inputs")
    summary = CaseDevRecapBatchSummary(
        input_record_count=len(materialized),
        converted_docket_count=converted_docket_count,
        enrichment_attempt_count=enrichment_attempt_count,
        successful_docket_count=len(successes),
        failure_count=len(failures),
        conversion_failure_count=conversion_failure_count,
        enrichment_failure_count=enrichment_failure_count,
        failure_reason_counts=tuple(
            sorted(Counter(failure.reason for failure in failures).items())
        ),
        actual_free_required_document_count=sum(
            success.actual_free_required_document_count for success in successes
        ),
        missing_required_document_count=sum(
            success.missing_required_document_count for success in successes
        ),
        reconciled=True,
    )
    return CaseDevRecapBatchResult(
        successes=successes,
        failures=tuple(failures),
        summary=summary,
    )


def _validate_docket_url(source_url: str, *, docket_id: str) -> None:
    split = urlsplit(source_url)
    match = _DOCKET_PATH.fullmatch(split.path)
    if (
        split.scheme != "https"
        or split.netloc != _COURTLISTENER_HOST
        or split.query
        or split.fragment
        or match is None
        or match.group("docket_id") != docket_id
    ):
        raise RecapDocketRecordError(
            "docket_url_invalid",
            "docket_url must be the matching canonical public CourtListener URL",
        )


def _required_string_list(
    record: Mapping[str, object],
    field_name: str,
) -> tuple[str, ...]:
    value = record.get(field_name)
    invalid_reason = f"{field_name}_invalid"
    duplicate_reason = f"{field_name}_duplicate"
    if not isinstance(value, list) or not value:
        raise RecapDocketRecordError(
            invalid_reason,
            f"{field_name} must be a non-empty JSON string array",
        )
    values = cast(list[object], value)
    if not all(
        isinstance(item, str) and bool(item) and item == item.strip() for item in values
    ):
        raise RecapDocketRecordError(
            invalid_reason,
            f"{field_name} must contain canonical non-empty strings",
        )
    strings = tuple(cast(list[str], values))
    if len(strings) != len(set(strings)):
        raise RecapDocketRecordError(
            duplicate_reason,
            f"{field_name} must not contain duplicates",
        )
    return strings


def _required_string(
    record: Mapping[str, object],
    field_name: str,
    reason: str,
) -> str:
    value = record.get(field_name)
    if not isinstance(value, str) or not value or value != value.strip():
        raise RecapDocketRecordError(
            reason,
            f"{field_name} must be a canonical non-empty string",
        )
    return value


def _best_effort_string(record: Mapping[str, object], field_name: str) -> str | None:
    value = record.get(field_name)
    return value if isinstance(value, str) and value else None


def _enrichment_failure_reason(
    error: CaseDevRecapEnrichmentError | CaseDevClientError,
) -> str:
    if isinstance(error, CaseDevRecapEnrichmentError):
        prefix = str(error).partition(":")[0].strip()
        return prefix or "case_dev_recap_enrichment_error"
    name = re.sub(r"(?<!^)(?=[A-Z])", "_", type(error).__name__).casefold()
    return name.removesuffix("_error") or "case_dev_client"
