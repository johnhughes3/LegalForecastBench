"""Bounded, acknowledged prompt pages over the canonical host tool protocol."""

from __future__ import annotations

import json
import secrets
import socket
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import cast

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


@dataclass
class DocumentDelivery:
    """Track authenticated catalog and document-page delivery to OpenClaw."""

    tool_calls: int = 0
    catalog_parts: list[str] = field(default_factory=lambda: list[str]())
    catalog_next_offset: int = 0
    catalog_paths: tuple[str, ...] = ()
    document_next_offsets: dict[str, int] = field(
        default_factory=lambda: dict[str, int]()
    )
    completed_paths: set[str] = field(default_factory=lambda: set[str]())

    @property
    def complete(self) -> bool:
        """Return whether every catalogued document reached its final page."""

        return (
            bool(self.catalog_paths) and set(self.catalog_paths) <= self.completed_paths
        )

    def observe(
        self,
        *,
        path: str | None,
        offset: int,
        output: Mapping[str, object],
    ) -> None:
        """Validate ordered pages and record only public-safe delivery facts."""

        text = output.get("text")
        next_offset = output.get("next_offset")
        complete = output.get("complete")
        if (
            not isinstance(text, str)
            or type(next_offset) is not int
            or next_offset <= offset
            or type(complete) is not bool
        ):
            raise OpenClawError("OpenClaw document page response was invalid")
        self.tool_calls += 1
        if path is None:
            if offset != self.catalog_next_offset:
                raise OpenClawError("OpenClaw document catalog offset mismatch")
            self.catalog_parts.append(text)
            self.catalog_next_offset = next_offset
            if complete:
                try:
                    decoded: object = json.loads("".join(self.catalog_parts))
                except (TypeError, ValueError) as exc:
                    raise OpenClawError(
                        "OpenClaw document catalog was invalid"
                    ) from exc
                decoded_items = (
                    cast(list[object], decoded) if isinstance(decoded, list) else None
                )
                if (
                    decoded_items is None
                    or not decoded_items
                    or any(
                        not isinstance(item, str)
                        or not item.startswith("documents/")
                        or item in {"documents", "documents/"}
                        for item in decoded_items
                    )
                ):
                    raise OpenClawError("OpenClaw document catalog was invalid")
                self.catalog_paths = tuple(cast(list[str], decoded_items))
            return
        expected_offset = self.document_next_offsets.get(path, 0)
        if offset != expected_offset or path not in self.catalog_paths:
            raise OpenClawError("OpenClaw document page path or offset mismatch")
        self.document_next_offsets[path] = next_offset
        if complete:
            self.completed_paths.add(path)


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


def bridge_documents(
    channel: socket.socket,
    transport: ToolTransport,
    request_id: str,
    delivery: DocumentDelivery,
    failures: list[BaseException],
) -> None:
    """Serve the bounded release-document tool over its private descriptor."""

    try:
        with channel.makefile("rb") as reader:
            while True:
                line = reader.readline(8192)
                if not line:
                    return
                decoded_message: object = cast(object, json.loads(line))
                if not isinstance(decoded_message, dict):
                    raise OpenClawError("OpenClaw document request was invalid")
                message = cast(dict[str, object], decoded_message)
                if set(message) - {"path", "offset"}:
                    raise OpenClawError("OpenClaw document request was invalid")
                path_value = message.get("path")
                offset_value = message.get("offset", 0)
                if (
                    path_value is not None
                    and (not isinstance(path_value, str) or len(path_value) > 512)
                ) or (type(offset_value) is not int or offset_value < 0):
                    raise OpenClawError("OpenClaw document request was invalid")
                path = path_value
                offset = offset_value
                request = ToolRequest(
                    request_id=(
                        f"{request_id}:openclaw:document:{delivery.tool_calls + 1}"
                    ),
                    operation="read_release_document",
                    arguments={"offset": offset},
                    input_paths=() if path is None else (path,),
                )
                response = transport.execute(request)
                if response.status != "succeeded":
                    raise OpenClawError("OpenClaw host document read failed")
                output = response.output
                delivery.observe(path=path, offset=offset, output=output)
                encoded = json.dumps(
                    {"text": json.dumps(dict(output), ensure_ascii=False)}
                ).encode("utf-8")
                if len(encoded) > 1_048_576:
                    raise OpenClawError("OpenClaw document response was too large")
                channel.sendall(encoded + b"\n")
    except (OSError, ValueError, RuntimeError) as exc:
        failures.append(exc)
    finally:
        channel.close()
