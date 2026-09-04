"""Published container-execution projection for multi-harness rows."""

from __future__ import annotations

from typing import Any

_LIVE_TOOLS = "live_tools"
_PLAN_ONLY = "plan_only"


def container_execution_record(
    *,
    configured_mode: str,
    receipt_sha256: str | None,
) -> dict[str, Any]:
    """Describe what the container did, not the run-config default.

    A receipt is hard evidence the container ran, so the published mode is not
    ``plan_only`` and the status is not ``not_run``. Config ``live_tools``
    without a receipt remains ``failed``. Config ``plan_only`` without a
    receipt remains ``not_run``.
    """

    if receipt_sha256 is not None:
        return {
            "mode": _LIVE_TOOLS,
            "status": "succeeded",
            "receipt_sha256": receipt_sha256,
        }
    if configured_mode == _LIVE_TOOLS:
        return {"mode": _LIVE_TOOLS, "status": "failed"}
    return {"mode": _PLAN_ONLY, "status": "not_run"}
