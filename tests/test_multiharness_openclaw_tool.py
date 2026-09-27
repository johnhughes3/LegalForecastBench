from __future__ import annotations

import json
import socket
import threading
from pathlib import Path

import pytest
from legalforecast.multiharness.openclaw_tool import (
    PromptDelivery,
    bridge_read,
    prompt_pages,
)
from tests.test_multiharness_openclaw import Transport


def test_bridge_uses_production_worker_read_contract(tmp_path: Path) -> None:
    transport = Transport(tmp_path, "Canonical staged task")
    host, child = socket.socketpair()
    failures: list[BaseException] = []
    delivery = PromptDelivery()
    worker = threading.Thread(
        target=bridge_read, args=(host, transport, "test", delivery, failures)
    )
    worker.start()
    try:
        with child.makefile("rb") as reader:
            child.sendall(b'{"page":0,"receipt":""}\n')
            page = json.loads(json.loads(reader.readline())["text"])
            assert page["content"] == "Canonical staged task"
            child.sendall(
                (json.dumps({"page": 1, "receipt": page["receipt"]}) + "\n").encode()
            )
            assert json.loads(json.loads(reader.readline())["text"]) == {
                "complete": True
            }
    finally:
        child.close()
        worker.join(timeout=2)
        transport.executor.close()
    assert failures == []
    assert delivery.complete
    assert delivery.tool_calls == 2
    assert transport.requests[0].operation == "read"
    assert transport.requests[0].arguments == {"file_path": "prompt.txt"}
    assert len(transport.requests) == 1


def test_pages_preserve_unicode_and_long_lines_with_bounded_output() -> None:
    text = "BEGIN" + "𠮷中\\\n" * 10000 + "END"
    pages = prompt_pages(text)
    assert "".join(pages) == text
    assert all(len(json.dumps(page)) <= 12000 for page in pages)


@pytest.mark.parametrize("page,receipt", [(0, ""), (1, "wrong"), (2, "wrong")])
def test_skipped_repeated_or_unacknowledged_pages_refused(
    tmp_path: Path, page: int, receipt: str
) -> None:
    host, child = socket.socketpair()
    delivery = PromptDelivery()
    failures: list[BaseException] = []
    worker = threading.Thread(
        target=bridge_read,
        args=(host, Transport(tmp_path), "test", delivery, failures),
    )
    worker.start()
    try:
        with child.makefile("rb") as reader:
            child.sendall(b'{"page":0,"receipt":""}\n')
            assert reader.readline()
            child.sendall(
                (json.dumps({"page": page, "receipt": receipt}) + "\n").encode()
            )
    finally:
        child.close()
        worker.join(timeout=2)
    assert failures
    assert not delivery.complete
