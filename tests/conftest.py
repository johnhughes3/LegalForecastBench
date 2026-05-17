from __future__ import annotations

import pytest
from legalforecast.ingestion.case_dev_config import case_dev_live_skip_reason


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "case_dev_live: marks tests that call the live case.dev API",
    )


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    skip_reason = case_dev_live_skip_reason()
    if skip_reason is None:
        return

    marker = pytest.mark.skip(reason=skip_reason)
    for item in items:
        if "case_dev_live" in item.keywords:
            item.add_marker(marker)
