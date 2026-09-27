"""Provider-free regressions for the protected Hermes record surface."""

from __future__ import annotations

import io
import json

import pytest
from legalforecast.multiharness import hermes_runtime, task_worker
from legalforecast.multiharness.spec import TOOL_REQUEST_SCHEMA_VERSION
from legalforecast.multiharness.tool_protocol import decode_tool_response


def exchange(root, paths=(), offset=0):
    outgoing = io.BytesIO()
    task_worker.serve(
        io.BytesIO(
            json.dumps(
                {
                    "schema_version": TOOL_REQUEST_SCHEMA_VERSION,
                    "request_id": "document",
                    "operation": "read_release_document",
                    "arguments": {"offset": offset},
                    "input_paths": list(paths),
                }
            ).encode()
            + b"\n"
        ),
        outgoing,
        root,
    )
    return decode_tool_response(outgoing.getvalue())


def test_staged_document_catalog_and_complete_bounded_text(tmp_path):
    documents = tmp_path / "documents"
    documents.mkdir()
    content = "Pleading evidence\n" * 14000
    (documents / "0000-complaint.txt").write_text(content)
    (tmp_path / "private-label.txt").write_text("UNAVAILABLE OUTCOME")
    catalog = exchange(tmp_path)
    assert catalog.status == "succeeded"
    assert json.loads(catalog.output["text"]) == ["documents/0000-complaint.txt"]
    offset, pieces = 0, []
    while True:
        page = exchange(tmp_path, ("documents/0000-complaint.txt",), offset)
        assert page.status == "succeeded"
        assert len(json.dumps(dict(page.output), ensure_ascii=False)) <= 7500
        pieces.append(page.output["text"])
        assert page.output["next_offset"] > offset
        offset = page.output["next_offset"]
        if page.output["complete"]:
            break
    assert "".join(pieces) == content
    assert len(pieces) > 30


@pytest.mark.parametrize(
    "path",
    [
        "prompt.txt",
        "private-label.txt",
        "documents/../private-label.txt",
        "documents/link.txt",
        "documents/alias/x.txt",
    ],
)
def test_document_reader_refuses_non_record_and_links(tmp_path, path):
    documents = tmp_path / "documents"
    documents.mkdir()
    (tmp_path / "private-label.txt").write_text("UNAVAILABLE OUTCOME")
    (tmp_path / "prompt.txt").write_text("prompt")
    (documents / "link.txt").symlink_to(tmp_path / "private-label.txt")
    (documents / "alias").symlink_to(tmp_path, target_is_directory=True)
    assert exchange(tmp_path, (path,)).status == "failed"


@pytest.mark.parametrize("batched", [False, True])
def test_protected_runtime_forwards_record_reads_without_batched_spill(
    tmp_path, batched
):
    (tmp_path / "documents").mkdir()
    (tmp_path / "documents/record.txt").write_text("FULL RECORD EVIDENCE")
    responses = [
        {"text": "canonical task"},
        dict(exchange(tmp_path).output),
        dict(exchange(tmp_path, ("documents/record.txt",)).output),
    ]
    incoming = io.StringIO(
        "".join(
            json.dumps(
                {
                    "schema_version": "legalforecast.multiharness.tool_response.v1",
                    "request_id": f"case:hermes-tool:{index}",
                    "status": "succeeded",
                    "output": output,
                }
            )
            + "\n"
            for index, output in enumerate(responses, 1)
        )
    )
    handlers = {}

    class Registry:
        def register(self, **kwargs):
            handlers[kwargs["name"]] = kwargs["handler"]

    class Agent:
        def __init__(self, **kwargs):
            self.model = kwargs["model"]
            self.tools = [{"function": {"name": name}} for name in handlers]
            self.step = kwargs["step_callback"]

        def run_conversation(self, _message):
            handlers["read_canonical_task"]({"offset": 0})
            if not batched:
                self.step()
            catalog = json.loads(handlers["read_release_document"]({"offset": 0}))
            path = json.loads(catalog["text"])[0]
            self.step()
            result = json.loads(
                handlers["read_release_document"]({"path": path, "offset": 0})
            )
            assert result["text"] == "FULL RECORD EVIDENCE"
            return {"completed": True}

        def close(self):
            pass

    outgoing = io.StringIO()
    config = {
        "request_id": "case",
        "model": "fixture",
        "session_id": "fresh",
        "required_unit_ids": ["unit"],
        "working_directory": str(tmp_path),
        "solver_input_path": "prompt.txt",
        "tool_request_schema": TOOL_REQUEST_SCHEMA_VERSION,
        "tool_response_schema": "legalforecast.multiharness.tool_response.v1",
        "gateway": {
            "capability_token": "fixture",
            "base_url": "http://127.0.0.1:1",
            "max_output_tokens": 100,
            "reasoning_config": {"effort": "high"},
        },
    }
    if batched:
        with pytest.raises(ValueError, match="one canonical task chunk per model turn"):
            hermes_runtime.execute(config, Agent, Registry(), incoming, outgoing)
        return
    result = hermes_runtime.execute(config, Agent, Registry(), incoming, outgoing)
    assert result["document_tool_call_count"] == 2
    assert result["tool_call_count"] == 3
    assert [
        json.loads(line)["operation"] for line in outgoing.getvalue().splitlines()
    ] == ["read_text", "read_release_document", "read_release_document"]


def test_document_reader_rejects_unreadable_pdf(tmp_path):
    from pypdf import PdfWriter

    documents = tmp_path / "documents"
    documents.mkdir()
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.write(documents / "scan.pdf")
    assert exchange(tmp_path, ("documents/scan.pdf",)).status == "failed"
    (documents / "broken.pdf").write_bytes(b"%PDF-malformed")
    assert exchange(tmp_path, ("documents/broken.pdf",)).status == "failed"


def test_document_reader_extracts_pdf_text(tmp_path):
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    documents = tmp_path / "documents"
    documents.mkdir()
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {NameObject("/F1"): writer._add_object(font)}
            )
        }
    )
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 50 700 Td (Complete pleading text) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    writer.write(documents / "pleading.pdf")
    response = exchange(tmp_path, ("documents/pleading.pdf",))
    assert response.status == "succeeded"
    assert response.output["text"] == "Complete pleading text"
    assert response.output["complete"] is True


def assert_container_documents(session, workspace, root):
    """Check actual staged synthetic documents through ContainerToolSession."""
    from legalforecast.multiharness.tool_protocol import ToolRequest

    def read(paths=(), offset=0):
        return session.execute(
            ToolRequest(
                request_id=f"record-{offset}",
                operation="read_release_document",
                arguments={"offset": offset},
                input_paths=paths,
            ),
            workspace,
        )

    catalog = read()
    assert catalog.status == "succeeded"
    paths = json.loads(catalog.output["text"])
    assert paths == sorted(
        path.relative_to(root).as_posix()
        for path in (root / "documents").rglob("*")
        if path.is_file()
    )
    assert paths
    for path in paths:
        offset, chunks = 0, []
        while True:
            page = read((path,), offset)
            assert page.status == "succeeded"
            chunks.append(page.output["text"])
            offset = page.output["next_offset"]
            if page.output["complete"]:
                break
        assert "".join(chunks) == (root / path).read_text()
    assert read(("forecast-release.json",)).status == "failed"
