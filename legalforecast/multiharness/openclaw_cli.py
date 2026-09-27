"""Public command-adapter entrypoint for the pinned OpenClaw community bridge."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from legalforecast._json_io import write_json_object
from legalforecast.multiharness.openclaw import (
    capabilities,
    offline_fixture,
)
from legalforecast.multiharness.openclaw_runtime import run_openclaw
from legalforecast.multiharness.spec import RunRequest
from legalforecast.multiharness.tool_protocol import (
    MAX_TOOL_MESSAGE_BYTES,
    ToolRequest,
    ToolResponse,
    decode_tool_response,
    encode_tool_message,
)


class StdioTransport:
    """Use the command adapter's existing host container JSONL channel."""

    def execute(self, request: ToolRequest) -> ToolResponse:
        """Send one request without placing runtime credentials on the channel."""
        sys.stdout.buffer.write(encode_tool_message(request))
        sys.stdout.buffer.flush()
        return decode_tool_response(
            sys.stdin.buffer.readline(MAX_TOOL_MESSAGE_BYTES + 2)
        )


def main(argv: list[str] | None = None) -> int:
    """Run offline conformance or an explicit credentialed host-tool operation."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="phase", required=True)
    sub.add_parser(
        "capabilities", help="Report LFB-only protocol capabilities"
    ).add_argument("--output", type=Path, required=True)
    for phase in ("run", "run-with-tools"):
        command = sub.add_parser(
            phase,
            help="Offline conformance"
            if phase == "run"
            else "Run the pinned OpenClaw agent with host container tools",
        )
        command.add_argument("--request", type=Path, required=True)
        command.add_argument("--output", type=Path, required=True)
        command.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.phase == "capabilities":
            record = capabilities().to_record()
        else:
            request = RunRequest.from_record(json.loads(args.request.read_text()))
            result = (
                offline_fixture(request)
                if args.phase == "run"
                else run_openclaw(request, args.workspace, StdioTransport())
            )
            record = result.to_record()
        write_json_object(args.output, record)
        return 0
    except (OSError, ValueError, RuntimeError):
        # Child diagnostics and model text stay in private-logs. Never echo a
        # provider error or raw transcript onto the public tool channel.
        print("OpenClaw adapter failed closed; inspect private logs", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
