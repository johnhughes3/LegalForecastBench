"""Bounded, acknowledged prompt pages over the canonical host tool protocol."""

from __future__ import annotations

import json
import secrets
import socket
from dataclasses import dataclass

from legalforecast.multiharness.openclaw import OpenClawError, ToolTransport
from legalforecast.multiharness.solver_inputs import SOLVER_INPUT_ENTRY_PATH
from legalforecast.multiharness.tool_protocol import ToolRequest

# Pinned OpenClaw's smallest automatic per-result cap is 16,000 weighted chars.
# ASCII-escaped JSON avoids its larger CJK weights; reserve room for metadata.
PAGE_TEXT_BUDGET = 12_000


@dataclass
class PromptDelivery:
    """Host-observed delivery, independent of the model's success envelope."""

    tool_calls: int = 0
    complete: bool = False


def prompt_pages(content: str) -> list[str]:
    """Partition without dropping characters, bounding encoded tool text."""
    pages: list[str] = []
    offset = 0
    while offset < len(content):
        size = min(6000, len(content) - offset)
        while len(json.dumps(content[offset : offset + size])) > PAGE_TEXT_BUDGET:
            size //= 2
        pages.append(content[offset : offset + size])
        offset += size
    if not pages:
        raise OpenClawError("OpenClaw solver prompt is empty")
    return pages


def bridge_read(
    channel: socket.socket,
    transport: ToolTransport,
    request_id: str,
    delivery: PromptDelivery,
    failures: list[BaseException],
) -> None:
    """Read the fixed staged path once, then deliver every page in order.

    The next call must echo the preceding page's trailing receipt. A final
    acknowledgement is required, so a model stopping early or a truncated page
    cannot turn a merely successful provider response into a successful run.
    This serves a tool; OpenClaw still owns every model turn.
    """
    try:
        pages: list[str] | None = None
        expected = 0
        receipt = ""
        with channel.makefile("rb") as reader:
            while True:
                message = json.loads(reader.readline(1024))
                if message != {"page": expected, "receipt": receipt}:
                    raise OpenClawError("OpenClaw prompt page or receipt mismatch")
                if pages is None:
                    request = ToolRequest(
                        request_id=f"{request_id}:openclaw:read",
                        operation="read",
                        arguments={"file_path": SOLVER_INPUT_ENTRY_PATH},
                        input_paths=(SOLVER_INPUT_ENTRY_PATH,),
                    )
                    response = transport.execute(request)
                    if (
                        response.request_id != request.request_id
                        or response.status != "succeeded"
                    ):
                        raise OpenClawError(
                            "OpenClaw host tool response failed or mismatched"
                        )
                    content = response.output.get("content")
                    if not isinstance(content, str):
                        raise OpenClawError("OpenClaw host read content is missing")
                    pages = prompt_pages(content)
                delivery.tool_calls += 1
                if expected == len(pages):
                    channel.sendall(b'{"text":"{\\"complete\\":true}"}\n')
                    delivery.complete = True
                    return
                receipt = secrets.token_hex(16)
                # Keep the receipt last, beyond the content whose delivery it
                # acknowledges. Preserve escapes all the way to the model.
                text = json.dumps(
                    {
                        "page": expected,
                        "total_pages": len(pages),
                        "content": pages[expected],
                        "next_page": expected + 1,
                        "receipt": receipt,
                    }
                )
                channel.sendall((json.dumps({"text": text}) + "\n").encode())
                expected += 1
    except (OSError, ValueError, RuntimeError) as exc:
        failures.append(exc)
    finally:
        channel.close()
