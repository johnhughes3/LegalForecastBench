"""Command adapter entry point for the pinned OpenAI Responses baseline."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import sys
from pathlib import Path
from typing import Any, cast

from legalforecast._json_io import write_json_object
from legalforecast.multiharness.openai_responses import (
    OPENAI_PROVIDER_ENV_VAR,
    OPENAI_SDK_MAX_RETRIES,
    OPENAI_SDK_VERSION,
    OpenAIResponsesAdapterError,
    build_capabilities,
    run_offline_protocol_fixture,
    run_openai_responses,
    validate_provider_grant,
)
from legalforecast.multiharness.spec import RunRequest
from legalforecast.multiharness.tool_protocol import (
    MAX_TOOL_MESSAGE_BYTES,
    ToolRequest,
    ToolResponse,
    decode_tool_response,
    encode_tool_message,
)
from legalforecast.openai_transport import (
    OpenAITransportRoute,
    resolve_openai_transport,
)


class StdioToolTransport:
    """Exchange one request and response at a time over the host JSONL channel."""

    def execute(self, request: ToolRequest) -> ToolResponse:
        """Send one bounded request and decode its matching response."""

        sys.stdout.buffer.write(encode_tool_message(request))
        sys.stdout.buffer.flush()
        response = sys.stdin.buffer.readline(MAX_TOOL_MESSAGE_BYTES + 2)
        if not response:
            raise OpenAIResponsesAdapterError("host tool channel closed")
        return decode_tool_response(response)


def main(argv: list[str] | None = None) -> int:
    """Run one adapter protocol command."""

    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="phase", required=True)

    capabilities = subparsers.add_parser("capabilities")
    capabilities.add_argument("--output", type=Path, required=True)

    for phase in ("run", "run-with-tools"):
        command = subparsers.add_parser(phase)
        command.add_argument("--request", type=Path, required=True)
        command.add_argument("--output", type=Path, required=True)
        command.add_argument("--workspace", type=Path, required=True)

    args = parser.parse_args(argv)
    try:
        if args.phase == "capabilities":
            write_json_object(args.output, build_capabilities().to_record())
            return 0

        request = RunRequest.from_record(_read_json_object(args.request))
        if args.phase == "run":
            result = run_offline_protocol_fixture(request, args.workspace)
        else:
            validate_provider_grant(request)
            _verify_sdk()
            api_key = os.environ.get(OPENAI_PROVIDER_ENV_VAR)
            if api_key is None or not api_key.strip():
                raise OpenAIResponsesAdapterError(
                    "OPENAI_API_KEY must be set and non-empty"
                )
            model_id = request.model_key.removeprefix("openai:")
            route = resolve_openai_transport(model_id)
            client = build_openai_client(api_key, route=route)
            result = run_openai_responses(
                request,
                args.workspace,
                tool_transport=StdioToolTransport(),
                client=client,
                transport_route=route,
            )
        write_json_object(args.output, result.to_record())
        return 0
    except Exception:
        print("OpenAI Responses adapter failed closed", file=sys.stderr)
        return 1


def _verify_sdk() -> None:
    observed = importlib.metadata.version("openai")
    if observed != OPENAI_SDK_VERSION:
        raise OpenAIResponsesAdapterError("installed OpenAI SDK version does not match")


def build_openai_client(
    api_key: str,
    *,
    route: OpenAITransportRoute | None = None,
) -> Any:
    """Build the pinned live client with transparent retries disabled."""

    from openai import OpenAI

    if route is not None and route.uses_vercel_gateway:
        return cast(
            Any,
            OpenAI(
                api_key=api_key,
                base_url=route.responses_url.removesuffix("/responses"),
                max_retries=OPENAI_SDK_MAX_RETRIES,
            ),
        )
    return cast(
        Any,
        OpenAI(api_key=api_key, max_retries=OPENAI_SDK_MAX_RETRIES),
    )


def _read_json_object(path: Path) -> dict[str, Any]:
    decoded = cast(object, json.loads(path.read_text(encoding="utf-8")))
    if not isinstance(decoded, dict):
        raise OpenAIResponsesAdapterError("request must be a JSON object")
    return cast(dict[str, Any], decoded)


if __name__ == "__main__":
    raise SystemExit(main())
