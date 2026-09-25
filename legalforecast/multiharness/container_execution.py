"""Published container-execution projection for multi-harness rows."""

from __future__ import annotations

from typing import Any

_LIVE_TOOLS = "live_tools"
_PLAN_ONLY = "plan_only"
_HEADLESS_CLI = "headless_cli"


def container_execution_record(
    *,
    configured_mode: str,
    receipt_sha256: str | None,
    result_status: str | None = None,
) -> dict[str, Any]:
    """Describe what the container did, not the run-config default.

    A receipt is hard evidence the host-owned live-tools container ran. The
    adapter-owned ``headless_cli`` path reports its adapter result directly.
    Config ``live_tools`` without a receipt remains ``failed``. Config
    ``plan_only`` without a receipt remains ``not_run``.
    """

    if configured_mode == _HEADLESS_CLI:
        status = "failed"
        if result_status == "succeeded":
            status = "succeeded"
        elif result_status == "interrupted":
            status = "interrupted"
        record: dict[str, Any] = {"mode": _HEADLESS_CLI, "status": status}
        if receipt_sha256 is not None:
            record["receipt_sha256"] = receipt_sha256
        return record
    if receipt_sha256 is not None:
        return {
            "mode": _LIVE_TOOLS,
            "status": "succeeded",
            "receipt_sha256": receipt_sha256,
        }
    if configured_mode == _LIVE_TOOLS:
        return {"mode": _LIVE_TOOLS, "status": "failed"}
    return {"mode": _PLAN_ONLY, "status": "not_run"}
