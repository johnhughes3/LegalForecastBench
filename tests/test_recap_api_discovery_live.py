"""Live, opt-in CourtListener REST v4 smoke test for decision-first discovery.

This module is skipped unless ``LFB_COURTLISTENER_LIVE=1`` is set (see
``conftest.courtlistener_live_skip_reason``), so CI never touches the network.

Verified live constraints this test respects:

* The v4 *search* index answers anonymously, but ``dockets``/``docket-entries``
  return HTTP 401 without a token, so docket reconstruction is only exercised
  when ``COURTLISTENER_API_TOKEN`` is set; otherwise this test performs a
  single anonymous search request only.
* Anonymous search throttles hard after roughly 40-50 requests, so this smoke
  issues at most one search page (plus one reconstruction when a token exists),
  hand-spaced by the anonymous pacer. Keep manual runs well under budget.
"""

from __future__ import annotations

from datetime import date

import pytest
from legalforecast.ingestion.courtlistener_client import (
    CourtListenerClient,
    CourtListenerConfig,
)
from legalforecast.ingestion.recap_api_discovery import (
    DECISION_FIRST_RECAP_API_SEARCH_TERMS,
    RecapApiDiscoverySource,
    candidate_docket_id,
    pacer_for_client,
    reconstruct_docket_page,
    resolve_auth_mode,
)

pytestmark = pytest.mark.courtlistener_live


def test_live_search_smoke() -> None:
    """One anonymous decision-first search page returns docket-level hits."""

    client = CourtListenerClient(config=CourtListenerConfig.from_env())
    source = RecapApiDiscoverySource(
        client=client,
        entry_date_filed_after=date(2026, 6, 30),
        pacer=pacer_for_client(client),
        auth_mode=resolve_auth_mode(client),
    )
    page = source.fetch_page(
        term=DECISION_FIRST_RECAP_API_SEARCH_TERMS[0],
        cursor=None,
        page_size=20,
    )
    assert page.hits, "expected at least one decision-first RECAP hit"
    assert all(
        hit.candidate_id.startswith("courtlistener-docket-") for hit in page.hits
    )


def test_live_reconstruction_smoke() -> None:
    """Reconstruct one docket completely; requires COURTLISTENER_API_TOKEN."""

    client = CourtListenerClient(config=CourtListenerConfig.from_env())
    if not client.config.api_token:
        pytest.skip(
            "reconstruction is token-required; set COURTLISTENER_API_TOKEN to run"
        )
    pacer = pacer_for_client(client)
    source = RecapApiDiscoverySource(
        client=client,
        entry_date_filed_after=date(2026, 6, 30),
        pacer=pacer,
        auth_mode=resolve_auth_mode(client),
    )
    page = source.fetch_page(
        term=DECISION_FIRST_RECAP_API_SEARCH_TERMS[0],
        cursor=None,
        page_size=20,
    )
    assert page.hits
    docket_id = candidate_docket_id(dict(page.hits[0].payload))
    reconstructed = reconstruct_docket_page(client, docket_id, pacer=pacer)
    assert reconstructed.proof.complete is True
    assert reconstructed.page.docket_id == docket_id
