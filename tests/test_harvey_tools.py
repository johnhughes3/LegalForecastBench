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


def test_harvey_tools_relative_reads_probe_documents_and_output(tmp_path: Path) -> None:
    documents = tmp_path / "documents"
    output = tmp_path / "output"
    documents.mkdir()
    output.mkdir()
    (documents / "motion.txt").write_text("motion\n", encoding="utf-8")
    (output / "answer.md").write_text("answer\n", encoding="utf-8")
    executor = HarveyToolExecutor(
        tmp_path,
        documents_root=documents,
        output_root=output,
    )

    document = _call(executor, tmp_path, "read", file_path="motion.txt")
    result = _call(executor, tmp_path, "read", file_path="answer.md")
    assert document["content"] == "motion\n"
    assert result["content"] == "answer\n"


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


def test_absolute_globs_use_virtual_workspace_paths(tmp_path: Path) -> None:
    executor = HarveyToolExecutor(tmp_path)
    (tmp_path / "documents" / "brief.txt").write_text("brief\n")
    for pattern, path in (
        ("/workspace/**/*", "/workspace"),
        ("/workspace/documents/*", None),
    ):
        arguments: dict[str, object] = {"pattern": pattern}
        if path is not None:
            arguments["path"] = path
        response = executor.execute(
            ToolRequest(
                request_id="absolute-glob", operation="glob", arguments=arguments
            ),
            tmp_path,
        )
        assert response.status == "succeeded"
        assert list(response.output["matches"]) == ["/workspace/documents/brief.txt"]


def test_globs_reject_patterns_outside_virtual_workspace(tmp_path: Path) -> None:
    executor = HarveyToolExecutor(tmp_path)
    for pattern in ("/etc/*", "../*", "/workspace/documents/../../*"):
        response = executor.execute(
            ToolRequest(
                request_id="unsafe-glob",
                operation="glob",
                arguments={"pattern": pattern},
            ),
            tmp_path,
        )
        assert response.status == "failed"
        assert response.error_code == "security_error"


def test_absolute_workspace_globs_include_separate_output_mount(tmp_path: Path) -> None:
    workspace = tmp_path / "input"
    workspace.mkdir()
    output = tmp_path / "output"
    executor = HarveyToolExecutor(workspace, output_root=output)
    (workspace / "documents" / "brief.txt").write_text("brief\n")
    (output / "nested").mkdir()
    (output / "nested" / "notes.txt").write_text("notes\n")
    (output / "answer.json").write_text("{}\n")
    for pattern, expected in (
        (
            "/workspace/**/*",
            {
                "/workspace/documents/brief.txt",
                "/workspace/output/nested/notes.txt",
                "/workspace/output/answer.json",
            },
        ),
        ("/workspace/output/*", {"/workspace/output/answer.json"}),
        ("/workspace/o*/**/*.txt", {"/workspace/output/nested/notes.txt"}),
        ("/workspace/*.txt", set()),
    ):
        result = _call(executor, workspace, "glob", pattern=pattern)
        assert set(result["matches"]) == expected
