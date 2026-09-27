"""Read-only staged release worker for the network-disabled tool container."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path, PurePosixPath
from typing import BinaryIO

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from legalforecast.immutable_io import read_single_link_file
from legalforecast.multiharness.solver_inputs import SOLVER_INPUT_ENTRY_PATH
from legalforecast.multiharness.tool_protocol import (
    MAX_TOOL_MESSAGE_BYTES,
    ToolResponse,
    decode_tool_request,
    encode_tool_message,
)


def _document_page(
    root: Path, paths: tuple[str, ...], arguments: dict[str, object]
) -> dict[str, object]:
    """Read only release-staged documents, with bounded model-visible pages."""

    offset = arguments.get("offset", 0)
    if set(arguments) - {"offset"} or type(offset) is not int or offset < 0:
        raise ValueError("invalid document offset")
    if not paths:
        documents = root / "documents"
        if documents.is_symlink():
            raise ValueError("document directory must not be a link")
        text = json.dumps(
            [
                path.relative_to(root).as_posix()
                for path in sorted(documents.rglob("*"))
                if path.is_file() and not path.is_symlink()
            ]
        )
    else:
        if len(paths) != 1:
            raise ValueError("one document per request")
        path = PurePosixPath(paths[0])
        if (
            len(path.parts) < 2
            or path.is_absolute()
            or path.parts[0] != "documents"
            or ".." in path.parts
            or path.as_posix() != paths[0]
        ):
            raise ValueError("only staged release documents may be read")
        payload = read_single_link_file(root / path, label="release document")
        if payload.startswith(b"%PDF-"):
            pages = [
                page.extract_text() or ""
                for page in PdfReader(io.BytesIO(payload)).pages
            ]
            if not pages or any(not page.strip() for page in pages):
                raise ValueError("release document requires OCR")
            text = "\n\n".join(pages)
        else:
            text = payload.decode("utf-8")
        if not text.strip():
            raise ValueError("release document has no text")
    if offset >= len(text):
        raise ValueError("document offset is beyond the text")
    end = min(offset + 6000, len(text))
    while True:
        page: dict[str, object] = {
            "text": text[offset:end],
            "next_offset": end,
            "complete": end == len(text),
        }
        if len(json.dumps(page, ensure_ascii=False)) <= 7500:
            return page
        end = offset + (end - offset) // 2


def serve(incoming: BinaryIO, outgoing: BinaryIO, input_root: Path) -> int:
    """Serve only the host-staged prompt and documents over bounded JSONL."""

    while line := incoming.readline(MAX_TOOL_MESSAGE_BYTES + 1):
        request_id = "invalid-request"
        try:
            request = decode_tool_request(line)
            request_id = request.request_id
            if request.operation == "read_release_document":
                output = _document_page(
                    input_root, request.input_paths, dict(request.arguments)
                )
            elif (
                request.operation != "read_text"
                or request.input_paths != (SOLVER_INPUT_ENTRY_PATH,)
                or dict(request.arguments) != {"encoding": "utf-8"}
            ):
                raise ValueError("only the canonical prompt may be read")
            else:
                payload = read_single_link_file(
                    input_root / SOLVER_INPUT_ENTRY_PATH, label="canonical prompt"
                )
                if len(payload) > MAX_TOOL_MESSAGE_BYTES:
                    raise ValueError("canonical prompt exceeds the tool frame limit")
                output = {"text": payload.decode("utf-8")}
            response = ToolResponse(
                request_id=request_id,
                status="succeeded",
                output=output,
            )
            encoded = encode_tool_message(response)
        except (OSError, ValueError, UnicodeError, PyPdfError):
            encoded = encode_tool_message(
                ToolResponse(
                    request_id=request_id,
                    status="failed",
                    output={},
                    error_code="invalid_canonical_task_request",
                )
            )
        outgoing.write(encoded)
        outgoing.flush()
    return 0


def main() -> int:
    """Run inside the canonical read-only, network-disabled container policy."""

    return serve(sys.stdin.buffer, sys.stdout.buffer, Path("/workspace/input"))


if __name__ == "__main__":
    raise SystemExit(main())
