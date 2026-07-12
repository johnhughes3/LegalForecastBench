"""Case.dev adapter for durable, order-neutral candidate discovery."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

from legalforecast.ingestion.case_dev_client import CaseDevClient, CaseDevDocketHit
from legalforecast.ingestion.discovery_scheduler import (
    DiscoveryHit,
    DiscoveryPage,
)
from legalforecast.ingestion.mtd_acquisition_screen import (
    courtlistener_public_docket_url_from_case_dev,
    screen_case_dev_docket_metadata,
)

_COURTLISTENER_DOCKET_ID = re.compile(r"/docket/(?P<docket_id>[0-9]+)/")


@dataclass(frozen=True, slots=True)
class CaseDevDiscoverySource:
    """Expose Case.dev legal search pages to the shared scheduler."""

    client: CaseDevClient

    def fetch_page(
        self,
        *,
        term: str,
        cursor: str | None,
        page_size: int,
    ) -> DiscoveryPage:
        page = self.client.search_docket_entries(
            term,
            cursor=cursor,
            limit=page_size,
        )
        return DiscoveryPage(
            hits=tuple(_discovery_hit(hit, query=term) for hit in page.items),
            next_cursor=page.next_cursor,
            # No exhaustion claim is inferred from Case.dev's missing cursor.
            exhausted=None,
        )


def case_dev_firecrawl_candidate_record(hit: DiscoveryHit) -> dict[str, Any]:
    """Build a self-contained Firecrawl candidate without another Case.dev call."""

    raw_hit: dict[str, Any] = dict(hit.payload)
    legal_docket_value = raw_hit.get("legal_docket")
    legal_docket = (
        _string_key_mapping(cast(Mapping[object, object], legal_docket_value))
        if isinstance(legal_docket_value, Mapping)
        else raw_hit
    )
    metadata_screen = screen_case_dev_docket_metadata(legal_docket)
    source_url = courtlistener_public_docket_url_from_case_dev(legal_docket)
    docket_match = _COURTLISTENER_DOCKET_ID.search(source_url or "")
    return {
        "candidate_id": hit.candidate_id,
        "case_id": hit.candidate_id,
        "case_dev_case_id": hit.candidate_id,
        "courtlistener_docket_id": (
            docket_match.group("docket_id") if docket_match is not None else None
        ),
        "courtlistener_url": source_url,
        "case_metadata": legal_docket,
        "normalized_case_metadata": metadata_screen.metadata.to_record(),
        "metadata_exclusion_reasons": list(metadata_screen.exclusion_reasons),
        "case_dev_search_hit": raw_hit,
    }


def _discovery_hit(hit: CaseDevDocketHit, *, query: str) -> DiscoveryHit:
    payload = dict(hit.raw)
    payload["query"] = query
    return DiscoveryHit(
        provider_hit_id=hit.docket_entry_id,
        candidate_id=hit.case_id,
        payload=payload,
    )


def _string_key_mapping(value: Mapping[object, object]) -> dict[str, object]:
    if not all(isinstance(key, str) for key in value):
        raise ValueError("case.dev legal_docket keys must be strings")
    return {cast(str, key): item for key, item in value.items()}
