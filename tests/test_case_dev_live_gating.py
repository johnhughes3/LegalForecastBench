from __future__ import annotations

import pytest
from legalforecast.ingestion.case_dev_config import (
    CASE_DEV_API_KEY_ENV,
    CASE_DEV_LIVE_TESTS_ENV,
)

import conftest


class _FakeItem:
    def __init__(self, keywords: dict[str, object]) -> None:
        self.keywords = keywords
        self.markers: list[pytest.MarkDecorator] = []

    def add_marker(self, marker: pytest.MarkDecorator) -> None:
        self.markers.append(marker)


def test_pytest_collection_skips_case_dev_live_tests_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(CASE_DEV_API_KEY_ENV, raising=False)
    monkeypatch.delenv(CASE_DEV_LIVE_TESTS_ENV, raising=False)
    live_item = _FakeItem({"case_dev_live": object()})
    ordinary_item = _FakeItem({})

    conftest.pytest_collection_modifyitems([live_item, ordinary_item])

    assert len(live_item.markers) == 1
    assert live_item.markers[0].mark.kwargs["reason"] == (
        "set CASE_DEV_LIVE_TESTS=1 to run live case.dev tests"
    )
    assert ordinary_item.markers == []


def test_pytest_collection_leaves_case_dev_live_tests_enabled_with_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(CASE_DEV_API_KEY_ENV, "case-dev-secret-token")
    monkeypatch.setenv(CASE_DEV_LIVE_TESTS_ENV, "1")
    live_item = _FakeItem({"case_dev_live": object()})

    conftest.pytest_collection_modifyitems([live_item])

    assert live_item.markers == []
