from __future__ import annotations

import os

import pytest
from legalforecast.ingestion.case_dev_config import case_dev_live_skip_reason

COURTLISTENER_LIVE_ENV = "LFB_COURTLISTENER_LIVE"


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "case_dev_live: marks tests that call the live case.dev API",
    )
    config.addinivalue_line(
        "markers",
        "courtlistener_live: marks tests that call the live CourtListener REST API",
    )


def courtlistener_live_skip_reason() -> str | None:
    """Return a skip reason unless live CourtListener API access is opted in.

    CI never sets ``LFB_COURTLISTENER_LIVE``, so these network-touching smoke
    tests are skipped by default and only run when an operator explicitly opts
    in for a bounded, hand-spaced anonymous validation.
    """

    if os.environ.get(COURTLISTENER_LIVE_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
    }:
        return None
    return f"set {COURTLISTENER_LIVE_ENV}=1 to run live CourtListener smoke tests"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    case_dev_reason = case_dev_live_skip_reason()
    courtlistener_reason = courtlistener_live_skip_reason()
    for item in items:
        if case_dev_reason is not None and "case_dev_live" in item.keywords:
            item.add_marker(pytest.mark.skip(reason=case_dev_reason))
        if courtlistener_reason is not None and "courtlistener_live" in item.keywords:
            item.add_marker(pytest.mark.skip(reason=courtlistener_reason))
