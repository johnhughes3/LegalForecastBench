# pyright: reportPrivateUsage=false

from __future__ import annotations

import hashlib
import io
import os
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from legalforecast.multiharness.harvey_lab_output_discovery import (
    HarveyLabOutputDiscoveryError,
    HarveyLabOutputErrorCode,
    HarveyLabOutputLimits,
    _copy_regular_file_from_fd,
    _reject_path_name,
    discover_harvey_lab_outputs,
)
from legalforecast.multiharness.harvey_lab_projection import (
    HarveyLabPin,
    HarveyLabProjectedFile,
    HarveyLabProjectedTask,
    load_harvey_lab_projection_manifest,
    project_harvey_lab_suite,
)
from tests.test_harvey_lab_projection import _issue_196_source

FAKE_SOLVER = (
    Path(__file__).resolve().parent / "fixtures" / "harvey_lab" / "fake_solver.py"
)
PINNED_TASK_ID = "employment-labor/identify-issues-in-counterparty-motion-brief"
BASENAME = "issue-identification-memo.docx"
TASK_SHA256 = "sha256:" + "1" * 64
RUN_SHA256 = "sha256:" + "2" * 64
CONFIG_SHA256 = "sha256:" + "3" * 64
FIXTURE_PIN = HarveyLabPin(
    repository="https://example.com/legalforecast-lab-fixture",
    commit="a" * 40,
    tree="b" * 40,
)


def _directory_fd(path: Path) -> int:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    return os.open(path, flags)


def _docx_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types></Types>")
        archive.writestr("word/document.xml", "<w:document></w:document>")
    return buffer.getvalue()


def _task(
    expected_deliverables: tuple[str, ...] = (BASENAME,),
) -> HarveyLabProjectedTask:
    payload = b"PK\x03\x04doc"
    return HarveyLabProjectedTask(
        task_id=f"harvey_lab:{PINNED_TASK_ID}",
        lab_task_id=PINNED_TASK_ID,
        category="employment-labor",
        relative_path=f"tasks/{PINNED_TASK_ID}",
        task_sha256="1" * 64,
        expected_deliverables=expected_deliverables,
        files=(
            HarveyLabProjectedFile(
                path="documents/briggs-declaration.docx",
                sha256="a" * 64,
                size_bytes=len(payload),
                role="document",
            ),
        ),
    )


def _discover(
    tmp_path: Path,
    *,
    extra_files: dict[str, bytes] | None = None,
    deliverable: bytes | None = None,
    escape_watch: Path | None = None,
    evaluator_private: Path | None = None,
    projection: Path | None = None,
    limits: HarveyLabOutputLimits | None = None,
):
    sandbox = tmp_path / "sandbox"
    output = sandbox / "output"
    output.mkdir(parents=True)
    payload = _docx_bytes() if deliverable is None else deliverable
    (output / BASENAME).write_bytes(payload)
    for relative, content in (extra_files or {}).items():
        path = output / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return discover_harvey_lab_outputs(
        sandbox_root=sandbox,
        output_root=output,
        quarantine_root=tmp_path / "quarantine",
        sealed_root=tmp_path / "sealed",
        task=_task(),
        task_sha256=TASK_SHA256,
        run_sha256=RUN_SHA256,
        config_sha256=CONFIG_SHA256,
        layout="native",
        limits=limits,
        escape_watch_roots=() if escape_watch is None else (escape_watch,),
        evaluator_private_root=evaluator_private,
        projection_root=projection,
    )


def test_valid_docx_seals_and_ignores_empty_quarantine(tmp_path: Path) -> None:
    result = _discover(tmp_path)
    assert result.task_id == f"harvey_lab:{PINNED_TASK_ID}"
    assert result.expected_deliverable == BASENAME
    assert result.quarantined == ()
    assert len(result.sealed.artifacts) == 1
    artifact = result.sealed.artifacts[0]
    assert artifact.path == BASENAME
    assert artifact.sha256.startswith("sha256:")
    assert (tmp_path / "sealed" / BASENAME).is_file()
    assert not (tmp_path / "quarantine").exists()


def test_multiple_declared_docx_outputs_are_all_sealed(tmp_path: Path) -> None:
    sandbox = tmp_path / "sandbox"
    output = sandbox / "output"
    output.mkdir(parents=True)
    for basename in ("analysis.docx", "memo.docx"):
        (output / basename).write_bytes(_docx_bytes())

    result = discover_harvey_lab_outputs(
        sandbox_root=sandbox,
        output_root=output,
        quarantine_root=tmp_path / "quarantine",
        sealed_root=tmp_path / "sealed",
        task=_task(("analysis.docx", "memo.docx")),
        task_sha256=TASK_SHA256,
        run_sha256=RUN_SHA256,
        config_sha256=CONFIG_SHA256,
    )

    assert result.expected_deliverables == ("analysis.docx", "memo.docx")
    assert [artifact.path for artifact in result.sealed.artifacts] == [
        "analysis.docx",
        "memo.docx",
    ]
    assert result.quarantined == ()


def test_no_declared_names_seals_every_bounded_docx_output(tmp_path: Path) -> None:
    sandbox = tmp_path / "sandbox"
    output = sandbox / "output"
    output.mkdir(parents=True)
    for basename in ("issues.docx", "redline.docx"):
        (output / basename).write_bytes(_docx_bytes())

    result = discover_harvey_lab_outputs(
        sandbox_root=sandbox,
        output_root=output,
        quarantine_root=tmp_path / "quarantine",
        sealed_root=tmp_path / "sealed",
        task=_task(()),
        task_sha256=TASK_SHA256,
        run_sha256=RUN_SHA256,
        config_sha256=CONFIG_SHA256,
    )

    assert result.expected_deliverables == ()
    assert [artifact.path for artifact in result.sealed.artifacts] == [
        "issues.docx",
        "redline.docx",
    ]
    assert result.quarantined == ()


def test_missing_one_of_multiple_declared_outputs_refuses_before_sealing(
    tmp_path: Path,
) -> None:
    sandbox = tmp_path / "sandbox"
    output = sandbox / "output"
    output.mkdir(parents=True)
    (output / "analysis.docx").write_bytes(_docx_bytes())

    with pytest.raises(HarveyLabOutputDiscoveryError) as caught:
        discover_harvey_lab_outputs(
            sandbox_root=sandbox,
            output_root=output,
            quarantine_root=tmp_path / "quarantine",
            sealed_root=tmp_path / "sealed",
            task=_task(("analysis.docx", "memo.docx")),
            task_sha256=TASK_SHA256,
            run_sha256=RUN_SHA256,
            config_sha256=CONFIG_SHA256,
        )

    assert caught.value.code == HarveyLabOutputErrorCode.MISSING_DELIVERABLE
    assert "memo.docx" in str(caught.value)
    assert not (tmp_path / "sealed").exists()


def test_fake_solver_output_is_discovered(tmp_path: Path) -> None:
    sandbox = tmp_path / "sandbox"
    output = sandbox / "output"
    output.mkdir(parents=True)
    completed = subprocess.run(
        (
            sys.executable,
            str(FAKE_SOLVER),
            "--output-dir",
            str(output),
            "--basename",
            BASENAME,
        ),
        check=False,
        capture_output=True,
        timeout=10,
    )
    assert completed.returncode == 0
    result = discover_harvey_lab_outputs(
        sandbox_root=sandbox,
        output_root=output,
        quarantine_root=tmp_path / "quarantine",
        sealed_root=tmp_path / "sealed",
        task=_task(),
        task_sha256=TASK_SHA256,
        run_sha256=RUN_SHA256,
        config_sha256=CONFIG_SHA256,
    )
    assert result.sealed.artifacts[0].path == BASENAME


def test_unrecognized_extra_is_quarantined_never_scored(tmp_path: Path) -> None:
    result = _discover(tmp_path, extra_files={"scratch-notes.txt": b"not scored"})
    assert len(result.quarantined) == 1
    extra = result.quarantined[0]
    assert extra.source_relative == "scratch-notes.txt"
    assert extra.size_bytes == len(b"not scored")
    sealed_names = {item.path for item in result.sealed.artifacts}
    assert sealed_names == {BASENAME}
    assert "scratch-notes.txt" not in sealed_names
    quarantined = tmp_path / "quarantine" / "scratch-notes.txt"
    assert quarantined.read_bytes() == b"not scored"


def test_quarantined_extras_are_recorded_in_sorted_order(tmp_path: Path) -> None:
    result = _discover(
        tmp_path,
        extra_files={"z-notes.txt": b"z", "a-notes.txt": b"a"},
    )
    assert [item.source_relative for item in result.quarantined] == [
        "a-notes.txt",
        "z-notes.txt",
    ]


def test_mismatched_task_digest_is_rejected(tmp_path: Path) -> None:
    sandbox = tmp_path / "sandbox"
    output = sandbox / "output"
    output.mkdir(parents=True)
    (output / BASENAME).write_bytes(_docx_bytes())
    with pytest.raises(HarveyLabOutputDiscoveryError) as caught:
        discover_harvey_lab_outputs(
            sandbox_root=sandbox,
            output_root=output,
            quarantine_root=tmp_path / "quarantine",
            sealed_root=tmp_path / "sealed",
            task=_task(),
            task_sha256="sha256:" + "9" * 64,
            run_sha256=RUN_SHA256,
            config_sha256=CONFIG_SHA256,
        )
    assert caught.value.code == HarveyLabOutputErrorCode.LAYOUT
    assert "task_sha256 does not match" in str(caught.value)
    assert not (tmp_path / "sealed").exists()


def test_sandbox_root_cannot_be_the_output_directory(tmp_path: Path) -> None:
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    (sandbox / BASENAME).write_bytes(_docx_bytes())
    with pytest.raises(HarveyLabOutputDiscoveryError) as caught:
        discover_harvey_lab_outputs(
            sandbox_root=sandbox,
            output_root=sandbox,
            quarantine_root=tmp_path / "quarantine",
            sealed_root=tmp_path / "sealed",
            task=_task(),
            task_sha256=TASK_SHA256,
            run_sha256=RUN_SHA256,
            config_sha256=CONFIG_SHA256,
        )
    assert caught.value.code == HarveyLabOutputErrorCode.LAYOUT
    assert "output_root must be inside sandbox_root" in str(caught.value)
    assert not (tmp_path / "sealed").exists()


def test_hard_linked_output_is_rejected(tmp_path: Path) -> None:
    sandbox = tmp_path / "sandbox"
    output = sandbox / "output"
    output.mkdir(parents=True)
    deliverable = output / BASENAME
    deliverable.write_bytes(_docx_bytes())
    alias = tmp_path / "alias.docx"
    os.link(deliverable, alias)
    with pytest.raises(HarveyLabOutputDiscoveryError) as caught:
        discover_harvey_lab_outputs(
            sandbox_root=sandbox,
            output_root=output,
            quarantine_root=tmp_path / "quarantine",
            sealed_root=tmp_path / "sealed",
            task=_task(),
            task_sha256=TASK_SHA256,
            run_sha256=RUN_SHA256,
            config_sha256=CONFIG_SHA256,
        )
    assert caught.value.code == HarveyLabOutputErrorCode.UNEXPECTED_TYPE
    assert "hard link" in str(caught.value)
    assert not (tmp_path / "sealed").exists()


def test_missing_deliverable_is_typed(tmp_path: Path) -> None:
    sandbox = tmp_path / "sandbox"
    output = sandbox / "output"
    output.mkdir(parents=True)
    with pytest.raises(HarveyLabOutputDiscoveryError) as caught:
        discover_harvey_lab_outputs(
            sandbox_root=sandbox,
            output_root=output,
            quarantine_root=tmp_path / "quarantine",
            sealed_root=tmp_path / "sealed",
            task=_task(),
            task_sha256=TASK_SHA256,
            run_sha256=RUN_SHA256,
            config_sha256=CONFIG_SHA256,
        )
    assert caught.value.code == HarveyLabOutputErrorCode.MISSING_DELIVERABLE
    assert "issue-identification-memo.docx" in str(caught.value)


def test_duplicate_basename_is_typed(tmp_path: Path) -> None:
    with pytest.raises(HarveyLabOutputDiscoveryError) as caught:
        _discover(
            tmp_path,
            extra_files={f"nested/{BASENAME}": _docx_bytes()},
        )
    assert caught.value.code == HarveyLabOutputErrorCode.DUPLICATE_BASENAME


def test_oversized_deliverable_is_typed(tmp_path: Path) -> None:
    limits = HarveyLabOutputLimits(max_file_bytes=32, max_total_bytes=32)
    with pytest.raises(HarveyLabOutputDiscoveryError) as caught:
        _discover(tmp_path, limits=limits)
    assert caught.value.code == HarveyLabOutputErrorCode.OVERSIZED


def test_symlink_output_is_typed(tmp_path: Path) -> None:
    sandbox = tmp_path / "sandbox"
    output = sandbox / "output"
    output.mkdir(parents=True)
    target = output / "real.docx"
    target.write_bytes(_docx_bytes())
    (output / BASENAME).symlink_to(target)
    with pytest.raises(HarveyLabOutputDiscoveryError) as caught:
        discover_harvey_lab_outputs(
            sandbox_root=sandbox,
            output_root=output,
            quarantine_root=tmp_path / "quarantine",
            sealed_root=tmp_path / "sealed",
            task=_task(),
            task_sha256=TASK_SHA256,
            run_sha256=RUN_SHA256,
            config_sha256=CONFIG_SHA256,
        )
    assert caught.value.code == HarveyLabOutputErrorCode.SYMLINK


def test_archive_extra_is_typed(tmp_path: Path) -> None:
    with pytest.raises(HarveyLabOutputDiscoveryError) as caught:
        _discover(tmp_path, extra_files={"payload.zip": b"PK\x03\x04not-scored"})
    assert caught.value.code == HarveyLabOutputErrorCode.ARCHIVE


def test_unexpected_fifo_is_typed(tmp_path: Path) -> None:
    sandbox = tmp_path / "sandbox"
    output = sandbox / "output"
    output.mkdir(parents=True)
    os.mkfifo(output / BASENAME)
    with pytest.raises(HarveyLabOutputDiscoveryError) as caught:
        discover_harvey_lab_outputs(
            sandbox_root=sandbox,
            output_root=output,
            quarantine_root=tmp_path / "quarantine",
            sealed_root=tmp_path / "sealed",
            task=_task(),
            task_sha256=TASK_SHA256,
            run_sha256=RUN_SHA256,
            config_sha256=CONFIG_SHA256,
        )
    assert caught.value.code == HarveyLabOutputErrorCode.UNEXPECTED_TYPE
    assert stat.S_ISFIFO((output / BASENAME).lstat().st_mode)


def test_non_zip_docx_is_typed(tmp_path: Path) -> None:
    with pytest.raises(HarveyLabOutputDiscoveryError) as caught:
        _discover(tmp_path, deliverable=b"not-a-docx")
    assert caught.value.code == HarveyLabOutputErrorCode.UNEXPECTED_TYPE


def test_sandbox_escape_watch_is_a_finding_not_a_score(tmp_path: Path) -> None:
    watch = tmp_path / "outside"
    watch.mkdir()
    (watch / "escaped.txt").write_text("solver escaped", encoding="utf-8")
    with pytest.raises(HarveyLabOutputDiscoveryError) as caught:
        _discover(tmp_path, escape_watch=watch)
    assert caught.value.code == HarveyLabOutputErrorCode.SANDBOX_ESCAPE
    assert not (tmp_path / "sealed").exists()


def test_escape_watch_symlink_root_is_typed(tmp_path: Path) -> None:
    real = tmp_path / "real-watch"
    real.mkdir()
    (real / "escaped.txt").write_text("solver escaped", encoding="utf-8")
    link = tmp_path / "watch-link"
    link.symlink_to(real)
    with pytest.raises(HarveyLabOutputDiscoveryError) as caught:
        _discover(tmp_path, escape_watch=link)
    assert caught.value.code == HarveyLabOutputErrorCode.SYMLINK
    assert not (tmp_path / "sealed").exists()


def test_leftover_quarantine_is_cleared_when_no_extras(tmp_path: Path) -> None:
    leftover = tmp_path / "quarantine"
    leftover.mkdir()
    (leftover / "old.txt").write_bytes(b"stale")
    result = _discover(tmp_path)
    assert result.quarantined == ()
    assert not leftover.exists()


def test_missing_quarantine_parent_is_created_for_clean_output(tmp_path: Path) -> None:
    sandbox = tmp_path / "sandbox"
    output = sandbox / "output"
    output.mkdir(parents=True)
    (output / BASENAME).write_bytes(_docx_bytes())
    result = discover_harvey_lab_outputs(
        sandbox_root=sandbox,
        output_root=output,
        quarantine_root=tmp_path / "missing" / "nested" / "quarantine",
        sealed_root=tmp_path / "sealed",
        task=_task(),
        task_sha256=TASK_SHA256,
        run_sha256=RUN_SHA256,
        config_sha256=CONFIG_SHA256,
    )
    assert result.quarantined == ()
    assert (tmp_path / "sealed" / BASENAME).is_file()


def test_copy_rejects_source_mutated_after_stat(tmp_path: Path) -> None:
    source_root = tmp_path / "src"
    source_root.mkdir()
    source = source_root / "scratch.txt"
    source.write_bytes(b"x")
    snapshot = source.stat()
    source.write_bytes(b"xy")
    dest_root = tmp_path / "dest"
    dest_root.mkdir()
    source_fd = _directory_fd(source_root)
    try:
        with pytest.raises(HarveyLabOutputDiscoveryError) as caught:
            _copy_regular_file_from_fd(
                source_fd,
                "scratch.txt",
                destination_root=dest_root,
                destination_relative="scratch.txt",
                expected_stat=snapshot,
                expected_digest=hashlib.sha256(b"x").digest(),
                max_bytes=100,
            )
    finally:
        os.close(source_fd)
    assert caught.value.code == HarveyLabOutputErrorCode.LAYOUT
    assert not (dest_root / "scratch.txt").exists()


def test_copy_rejects_same_size_content_replacement(tmp_path: Path) -> None:
    source_root = tmp_path / "src"
    source_root.mkdir()
    source = source_root / "scratch.txt"
    source.write_bytes(b"abcd")
    snapshot = source.stat()
    source.write_bytes(b"efgh")
    dest_root = tmp_path / "dest"
    dest_root.mkdir()
    source_fd = _directory_fd(source_root)
    try:
        with pytest.raises(HarveyLabOutputDiscoveryError) as caught:
            _copy_regular_file_from_fd(
                source_fd,
                "scratch.txt",
                destination_root=dest_root,
                destination_relative="scratch.txt",
                expected_stat=snapshot,
                expected_digest=hashlib.sha256(b"abcd").digest(),
                max_bytes=100,
            )
    finally:
        os.close(source_fd)
    assert caught.value.code == HarveyLabOutputErrorCode.LAYOUT
    assert not (dest_root / "scratch.txt").exists()


def test_held_output_fd_does_not_follow_replaced_sandbox(tmp_path: Path) -> None:
    sandbox = tmp_path / "sandbox"
    output = sandbox / "output"
    output.mkdir(parents=True)
    payload = b"inside-bytes"
    (output / "scratch.txt").write_bytes(payload)
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    output_fd = os.open(output, flags)
    try:
        outside = tmp_path / "outside"
        (outside / "output").mkdir(parents=True)
        (outside / "output" / "scratch.txt").write_bytes(b"escaped")
        real = tmp_path / "sandbox-real"
        sandbox.rename(real)
        sandbox.symlink_to(outside)
        dest_root = tmp_path / "dest"
        dest_root.mkdir()
        _copy_regular_file_from_fd(
            output_fd,
            "scratch.txt",
            destination_root=dest_root,
            destination_relative="scratch.txt",
            expected_stat=(real / "output" / "scratch.txt").stat(),
            expected_digest=hashlib.sha256(payload).digest(),
            max_bytes=100,
        )
        assert (dest_root / "scratch.txt").read_bytes() == payload
    finally:
        os.close(output_fd)


def test_solver_and_evaluator_roots_must_not_overlap(tmp_path: Path) -> None:
    sandbox = tmp_path / "sandbox"
    output = sandbox / "output"
    output.mkdir(parents=True)
    (output / BASENAME).write_bytes(_docx_bytes())
    with pytest.raises(HarveyLabOutputDiscoveryError) as caught:
        discover_harvey_lab_outputs(
            sandbox_root=sandbox,
            output_root=output,
            quarantine_root=tmp_path / "quarantine",
            sealed_root=tmp_path / "sealed",
            task=_task(),
            task_sha256=TASK_SHA256,
            run_sha256=RUN_SHA256,
            config_sha256=CONFIG_SHA256,
            evaluator_private_root=sandbox,
        )
    assert caught.value.code == HarveyLabOutputErrorCode.MATERIAL_OVERLAP


def test_evaluator_private_gold_is_not_walked_or_scored(tmp_path: Path) -> None:
    private = tmp_path / "evaluator-private"
    private.mkdir()
    (private / "gold-answers.json").write_text(
        "GOLD_ANSWER_PRIVATE",
        encoding="utf-8",
    )
    result = _discover(tmp_path, evaluator_private=private)
    assert result.quarantined == ()
    assert (tmp_path / "sealed" / BASENAME).is_file()
    assert not (tmp_path / "sealed" / "gold-answers.json").exists()
    assert not (tmp_path / "quarantine").exists()


def test_nested_extra_is_quarantined_not_sealed(tmp_path: Path) -> None:
    result = _discover(tmp_path, extra_files={"notes/scratch.txt": b"ignore"})
    assert {item.source_relative for item in result.quarantined} == {
        "notes/scratch.txt"
    }
    assert {item.path for item in result.sealed.artifacts} == {BASENAME}


def test_path_traversal_names_are_rejected() -> None:
    with pytest.raises(HarveyLabOutputDiscoveryError) as caught:
        _reject_path_name("..", "../secret")
    assert caught.value.code == HarveyLabOutputErrorCode.PATH_TRAVERSAL


def test_lab1_projection_and_fake_solver_stay_material_separated(
    tmp_path: Path,
) -> None:
    projected = project_harvey_lab_suite(
        source_root=_issue_196_source(tmp_path / "lab"),
        solver_root=tmp_path / "solver",
        evaluator_private_root=tmp_path / "private",
        pin=FIXTURE_PIN,
    )
    manifest = load_harvey_lab_projection_manifest(projected.solver_root)
    task = manifest.tasks[0]
    sandbox = tmp_path / "sandbox"
    output = sandbox / "output"
    output.mkdir(parents=True)
    completed = subprocess.run(
        (
            sys.executable,
            str(FAKE_SOLVER),
            "--output-dir",
            str(output),
            "--basename",
            task.expected_deliverable,
        ),
        check=False,
        capture_output=True,
        timeout=10,
    )
    assert completed.returncode == 0
    result = discover_harvey_lab_outputs(
        sandbox_root=sandbox,
        output_root=output,
        quarantine_root=tmp_path / "quarantine",
        sealed_root=tmp_path / "sealed",
        task=task,
        task_sha256="sha256:" + task.task_sha256,
        run_sha256=RUN_SHA256,
        config_sha256=CONFIG_SHA256,
        evaluator_private_root=projected.evaluator_private_root,
        projection_root=projected.solver_root,
    )
    assert result.task_id == task.task_id
    assert result.expected_deliverable == BASENAME
    assert result.quarantined == ()
    sealed_tree = tmp_path / "sealed"
    assert (sealed_tree / BASENAME).is_file()
    assert not list(sealed_tree.rglob("gold-answers.json"))
    assert not list(sealed_tree.rglob("task.json"))
    private_gold = (
        projected.evaluator_private_root
        / "tasks"
        / PINNED_TASK_ID
        / "gold-answers.json"
    )
    assert private_gold.is_file()
    assert "GOLD_ANSWER_PRIVATE" in private_gold.read_text(encoding="utf-8")


def test_total_output_bytes_are_typed(tmp_path: Path) -> None:
    payload = _docx_bytes()
    limits = HarveyLabOutputLimits(
        max_file_bytes=len(payload) + 50,
        max_total_bytes=len(payload) + 30,
    )
    with pytest.raises(HarveyLabOutputDiscoveryError) as caught:
        _discover(
            tmp_path,
            extra_files={"a.txt": b"x" * 20, "b.txt": b"y" * 20},
            limits=limits,
        )
    assert caught.value.code == HarveyLabOutputErrorCode.OVERSIZED


def test_deep_empty_directories_are_typed(tmp_path: Path) -> None:
    sandbox = tmp_path / "sandbox"
    output = sandbox / "output"
    nested = output / "a" / "b" / "c"
    nested.mkdir(parents=True)
    (output / BASENAME).write_bytes(_docx_bytes())
    with pytest.raises(HarveyLabOutputDiscoveryError) as caught:
        discover_harvey_lab_outputs(
            sandbox_root=sandbox,
            output_root=output,
            quarantine_root=tmp_path / "quarantine",
            sealed_root=tmp_path / "sealed",
            task=_task(),
            task_sha256=TASK_SHA256,
            run_sha256=RUN_SHA256,
            config_sha256=CONFIG_SHA256,
            limits=HarveyLabOutputLimits(max_depth=2),
        )
    assert caught.value.code == HarveyLabOutputErrorCode.OVERSIZED


def test_quarantine_parent_symlink_is_typed(tmp_path: Path) -> None:
    source_root = tmp_path / "src"
    source_root.mkdir()
    (source_root / "scratch.txt").write_bytes(b"x")
    dest_root = tmp_path / "dest"
    dest_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (dest_root / "notes").symlink_to(outside)
    source_fd = _directory_fd(source_root)
    try:
        with pytest.raises(HarveyLabOutputDiscoveryError) as caught:
            _copy_regular_file_from_fd(
                source_fd,
                "scratch.txt",
                destination_root=dest_root,
                destination_relative="notes/scratch.txt",
                expected_stat=(source_root / "scratch.txt").stat(),
                expected_digest=hashlib.sha256(b"x").digest(),
                max_bytes=100,
            )
    finally:
        os.close(source_fd)
    assert caught.value.code == HarveyLabOutputErrorCode.SYMLINK
    assert not (outside / "scratch.txt").exists()
