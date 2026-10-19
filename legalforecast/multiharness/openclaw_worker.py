"""Fixed entrypoint inside the credential-free OpenClaw container image."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from pypdf.errors import PyPdfError

from legalforecast.multiharness.harvey_tools import HarveyToolExecutor
from legalforecast.multiharness.openclaw import OpenClawError
from legalforecast.multiharness.openclaw_runtime import (
    GatewayRuntimeConfig,
    run_openclaw,
)
from legalforecast.multiharness.release_harness import read_release_object
from legalforecast.multiharness.release_runtime import write_release_json_create_only
from legalforecast.multiharness.spec import RunRequest
from legalforecast.multiharness.task_worker import document_page
from legalforecast.multiharness.tool_protocol import ToolRequest, ToolResponse

CAPABILITY_ENV = "LFB_OPENCLAW_GATEWAY_CAPABILITY"


class StagedPromptTransport:
    """Use production worker semantics for fixed prompt and document reads."""

    def __init__(self, workspace: Path, *, document_root: Path | None = None) -> None:
        self.workspace = workspace
        self.document_root = document_root or workspace
        self.executor = HarveyToolExecutor(workspace)

    def execute(self, request: ToolRequest) -> ToolResponse:
        if request.operation == "read_release_document":
            try:
                output = document_page(
                    self.document_root,
                    request.input_paths,
                    dict(request.arguments),
                )
            except (OSError, PyPdfError, UnicodeError, ValueError):
                return ToolResponse(
                    request_id=request.request_id,
                    status="failed",
                    output={},
                    error_code="invalid_release_document_request",
                )
            return ToolResponse(
                request_id=request.request_id,
                status="succeeded",
                output=output,
            )
        if request.operation != "read" or dict(request.arguments) != {
            "file_path": "prompt.txt"
        }:
            raise OpenClawError("contained OpenClaw permits only release reads")
        return self.executor.execute(request, self.workspace)


def execute(workspace: Path) -> None:
    """Run one host-staged request; never discover credentials or endpoints."""
    request = RunRequest.from_record(
        read_release_object(workspace / "openclaw-request.json", "OpenClaw request")
    )
    model = read_release_object(workspace / "openclaw-model.json", "OpenClaw model")
    if set(model) != {"context_limit", "max_output_tokens", "reasoning_effort"}:
        raise OpenClawError("unexpected OpenClaw model settings")
    for field in ("context_limit", "max_output_tokens"):
        if type(model[field]) is not int:
            raise OpenClawError("model limits must be integers")
    if model["reasoning_effort"] != "high":
        raise OpenClawError("OpenClaw requires pinned high reasoning")
    gateway = GatewayRuntimeConfig(
        capability=os.environ[CAPABILITY_ENV],
        context_limit=model["context_limit"],
        max_output_tokens=model["max_output_tokens"],
    )
    result = run_openclaw(
        request,
        workspace,
        StagedPromptTransport(workspace),
        gateway=gateway,
        documents_enabled=True,
    )
    write_release_json_create_only(
        workspace / "openclaw-result.json", result.to_record()
    )
    print(json.dumps({"status": result.status, "request_id": result.request_id}))


def main() -> int:
    """No arbitrary command, path, model, or auth argument is accepted."""
    try:
        if len(sys.argv) != 1:
            raise OpenClawError("contained OpenClaw accepts no command arguments")
        execute(Path("/workspace"))
        return 0
    except Exception:
        print(
            "Contained OpenClaw failed; inspect private gateway/runtime logs",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
