"""Local sandbox failures must precede provider spend authorization."""

from __future__ import annotations

from typing import Any, cast

import legalforecast.runner.managed_execution as managed_execution
import pytest
from legalforecast.runner.managed_execution import ManagedCaseInput
from tests.test_managed_tool_agent import _AttemptHandler, _entry


def test_sandbox_setup_failure_does_not_authorize_spend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    handler = _AttemptHandler()
    observed: list[bytes] = []

    def unavailable(**_kwargs: Any) -> Any:
        raise RuntimeError("Docker backend must be rootless")

    monkeypatch.setattr(
        "legalforecast.runner.tool_runtime.open_official_tool_session", unavailable
    )
    monkeypatch.setattr(
        managed_execution,
        "run_managed_tool_agent",
        lambda *_args, **_kwargs: pytest.fail("provider must not be called"),
    )
    with pytest.raises(RuntimeError, match="Docker backend must be rootless"):
        managed_execution.complete_managed_tool_cell(
            _entry(),
            handler=cast(Any, handler),
            managed_case=ManagedCaseInput(
                case_id="case-1",
                required_unit_ids=("unit-a",),
                documents={"documents/motion.txt": b"motion"},
                unit_descriptions=(),
                document_descriptions=(),
                cell_id="a" * 64,
            ),
            request_body_observer=observed.append,
            environ={"OPENAI_API_KEY": "fixture-key"},
            registry_sha256="b" * 64,
        )
    assert handler.run_count == 0
    assert handler.settlement is None
    assert observed == []
