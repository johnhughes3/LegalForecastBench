from __future__ import annotations

import pytest
from legalforecast.ingestion.disclosure_uri import (
    is_allowlisted_public_recap_uri,
    is_canonical_private_store_uri,
)


@pytest.mark.parametrize(
    "value",
    (
        "https://storage.courtlistener.com/recap/document.pdf",
        "https://STORAGE.COURTLISTENER.COM/recap/case/file%20name.pdf",
    ),
)
def test_public_recap_uri_accepts_canonical_values(value: str) -> None:
    assert is_allowlisted_public_recap_uri(value)


@pytest.mark.parametrize(
    "value",
    (
        "http://storage.courtlistener.com/recap/document.pdf",
        "https://storage.courtlistener.com:443/recap/document.pdf",
        "https://storage.courtlistener.com:8443/recap/document.pdf",
        "https://storage.courtlistener.com:invalid/recap/document.pdf",
        "https://user@storage.courtlistener.com/recap/document.pdf",
        "https://storage.courtlistener.com./recap/document.pdf",
        "https://xn--courtlistener-2jg.com/recap/document.pdf",
        "https://storage.courtlistener.com/recap/",
        "https://storage.courtlistener.com/recap//document.pdf",
        "https://storage.courtlistener.com/recap/../private/document.pdf",
        "https://storage.courtlistener.com/recap/%2e%2e/private/document.pdf",
        "https://storage.courtlistener.com/recap/%2Fprivate",
        "https://storage.courtlistener.com/recap/%FF.pdf",
        "https://storage.courtlistener.com/recap/%C0%AFprivate.pdf",
        "https://storage.courtlistener.com/recap\\document.pdf",
        "https://storage.courtlistener.com/recap/document.pdf?download=1",
        "https://storage.courtlistener.com/recap/document.pdf#fragment",
        "https://storage.courtlistener.com/\nrecap/document.pdf",
        "https://storage.courtlistener.com/recap/\ud800.pdf",
    ),
)
def test_public_recap_uri_rejects_noncanonical_values(value: str) -> None:
    assert not is_allowlisted_public_recap_uri(value)


@pytest.mark.parametrize(
    "value",
    (
        "private-store://cycle-1",
        "private-store://cycle-1/",
        "private-store://cycle-1/reviews/",
        "private-store://cycle-1/reviews/batch%20001",
    ),
)
def test_private_store_uri_accepts_canonical_values(value: str) -> None:
    assert is_canonical_private_store_uri(value)


@pytest.mark.parametrize(
    "value",
    (
        "private-store:///reviews/batch-001",
        "private-store://user@cycle-1/reviews/batch-001",
        "private-store://user:password@cycle-1/reviews/batch-001",
        "private-store://cycle-1:8443/reviews/batch-001",
        "private-store://cycle-1:invalid/reviews/batch-001",
        "private-store://cycle-1/reviews//batch-001",
        "private-store://cycle-1/reviews/../batch-001",
        "private-store://cycle-1/reviews/%2e%2e/batch-001",
        "private-store://cycle-1/reviews/%2Fbatch-001",
        "private-store://cycle-1/reviews/%FF",
        "private-store://cycle-1/reviews\\batch-001",
        "private-store://cycle-1/reviews/batch-001?version=1",
        "private-store://cycle-1/reviews/batch-001#fragment",
        "private-store://cycle-1/\nreviews/batch-001",
        "private-store://cycle-1/reviews/\ud800",
    ),
)
def test_private_store_uri_rejects_noncanonical_values(value: str) -> None:
    assert not is_canonical_private_store_uri(value)
