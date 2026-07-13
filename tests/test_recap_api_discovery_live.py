"""Live, opt-in CourtListener REST v4 smoke test for decision-first discovery.

This module is skipped unless ``LFB_COURTLISTENER_LIVE=1`` is set (see
``conftest.courtlistener_live_skip_reason``), so CI never touches the network.
When opted in it performs a *bounded* anonymous validation: one decision-first
search page plus one docket reconstruction, hand-spaced by the anonymous pacer.
Keep any manual run well under the 30-request anonymous budget.
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


def test_live_discovery_and_reconstruction_smoke() -> None:
    client = CourtListenerClient(config=CourtListenerConfig.from_env())
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
    assert page.hits, "expected at least one decision-first RECAP hit"

    docket_id = candidate_docket_id(dict(page.hits[0].payload))
    reconstructed = reconstruct_docket_page(client, docket_id, pacer=pacer)
    assert reconstructed.proof.complete is True
    assert reconstructed.page.docket_id == docket_id
