from __future__ import annotations

import os

import pytest

COURTLISTENER_LIVE_ENV = "LFB_COURTLISTENER_LIVE"
LFB_LIVE_SMOKE_ENV = "LFB_LIVE_SMOKE"


def case_dev_live_skip_reason() -> str | None:
    """Skip legacy live case.dev tests unless explicitly opted in."""

    if os.environ.get("CASE_DEV_LIVE", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }:
        return None
    return "set CASE_DEV_LIVE=1 to run live case.dev tests"


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "case_dev_live: marks tests that call the live case.dev API",
    )
    config.addinivalue_line(
        "markers",
        "courtlistener_live: marks tests that call the live CourtListener REST API",
    )
    config.addinivalue_line(
        "markers",
        "lfb_live_smoke: marks the env-gated live local-CLI smoke (excluded from CI)",
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


def lfb_live_smoke_skip_reason() -> str | None:
    """Return a skip reason unless the live local-CLI smoke is opted in.

    CI never sets ``LFB_LIVE_SMOKE``. The one real ``claude`` invocation is
    operator-gated so it cannot spend against a provider from the default suite.
    """

    if os.environ.get(LFB_LIVE_SMOKE_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
    }:
        return None
    return f"set {LFB_LIVE_SMOKE_ENV}=1 to run the live local CLI smoke"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    case_dev_reason = case_dev_live_skip_reason()
    courtlistener_reason = courtlistener_live_skip_reason()
    live_smoke_reason = lfb_live_smoke_skip_reason()
    for item in items:
        if case_dev_reason is not None and "case_dev_live" in item.keywords:
            item.add_marker(pytest.mark.skip(reason=case_dev_reason))
        if courtlistener_reason is not None and "courtlistener_live" in item.keywords:
            item.add_marker(pytest.mark.skip(reason=courtlistener_reason))
        if live_smoke_reason is not None and "lfb_live_smoke" in item.keywords:
            item.add_marker(pytest.mark.skip(reason=live_smoke_reason))
