from __future__ import annotations

from pathlib import Path

from legalforecast.multiharness.harvey_tools import HarveyToolExecutor
from legalforecast.multiharness.tool_protocol import ToolRequest


def _call(
    executor: HarveyToolExecutor, root: Path, operation: str, **arguments: object
):
    response = executor.execute(
        ToolRequest(
            request_id=f"test-{operation}", operation=operation, arguments=arguments
        ),
        root,
    )
    assert response.status == "succeeded", response
    return dict(response.output)


def test_harvey_tools_read_search_and_output_workspace(tmp_path: Path) -> None:
    documents = tmp_path / "documents"
    documents.mkdir()
    (documents / "brief.txt").write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
    executor = HarveyToolExecutor(tmp_path)

    read = _call(
        executor, tmp_path, "read", file_path="documents/brief.txt", offset=1, limit=1
    )
    assert read["content"] == "beta\n"
    assert list(_call(executor, tmp_path, "glob", pattern="*.txt")["matches"]) == [
        "/workspace/documents/brief.txt"
    ]
    grep = _call(executor, tmp_path, "grep", pattern="beta", output_mode="content")
    assert [dict(item) for item in grep["matches"]] == [
        {
            "file_path": "/workspace/documents/brief.txt",
            "line_number": 2,
            "line": "beta",
        }
    ]

    _call(executor, tmp_path, "write", file_path="answer.txt", content="draft")
    assert (tmp_path / "output" / "answer.txt").read_text() == "draft"
    _call(
        executor,
        tmp_path,
        "edit",
        file_path="answer.txt",
        old_string="draft",
        new_string="final",
    )
    assert (tmp_path / "output" / "answer.txt").read_text() == "final"
    executor.close()


def test_harvey_tools_reads_a_requested_slice_of_a_large_document(
    tmp_path: Path,
) -> None:
    documents = tmp_path / "documents"
    documents.mkdir()
    payload = ("x" * 1000 + "\n") * 800
    (documents / "long-pleading.txt").write_text(payload, encoding="utf-8")
    executor = HarveyToolExecutor(tmp_path)

    result = _call(
        executor,
        tmp_path,
        "read",
        file_path="documents/long-pleading.txt",
        offset=799,
        limit=1,
    )
    assert result["content"] == "x" * 1000 + "\n"
    executor.close()


def test_harvey_tools_keep_bash_cwd_and_reject_document_writes(tmp_path: Path) -> None:
    executor = HarveyToolExecutor(tmp_path)
    (tmp_path / "output" / "nested").mkdir(parents=True)
    changed = _call(executor, tmp_path, "bash", command="cd output/nested && printf ok")
    assert changed["output"] == "ok"
    current = _call(executor, tmp_path, "bash", command="pwd")
    assert current["cwd"] == "/workspace/output/nested"
    forbidden = executor.execute(
        ToolRequest(
            request_id="forbidden",
            operation="write",
            arguments={"file_path": "../documents/x", "content": "bad"},
        ),
        tmp_path,
    )
    assert forbidden.status == "failed"
    assert not (tmp_path / "documents" / "x").exists()
    executor.close()
