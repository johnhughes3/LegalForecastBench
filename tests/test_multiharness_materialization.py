# pyright: reportPrivateUsage=false

from __future__ import annotations

import hashlib
import os
from dataclasses import replace
from pathlib import Path

import pytest
from legalforecast.multiharness import materialization as materialization_module
from legalforecast.multiharness.materialization import (
    MaterializationLimits,
    TaskArtifactProjection,
    TaskMaterializationError,
    TaskMaterializationLayout,
    materialize_task,
)
from legalforecast.multiharness.spec import ArtifactRecord, CanonicalTask


def test_materialization_is_deterministic_across_input_order_and_layouts(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    first = _write(source_root / "documents" / "first.txt", b"first")
    second = _write(source_root / "documents" / "second.txt", b"second")
    private = _write(source_root / "task.json", b'{"criteria":["private"]}')
    artifacts = (
        _artifact("second", second, source_root),
        _artifact("task_json", private, source_root),
        _artifact("first", first, source_root),
    )
    task = _task(artifacts)

    native = materialize_task(
        replace(task, artifacts=tuple(reversed(artifacts))),
        source_root=source_root,
        destination_root=tmp_path / "native",
        layout=TaskMaterializationLayout(
            layout_id="native.v1",
            solver_artifacts=(
                TaskArtifactProjection("first", "input/first.txt"),
                TaskArtifactProjection("second", "input/second.txt"),
            ),
            evaluator_private_artifact_ids=("task_json",),
        ),
    )
    external = materialize_task(
        task,
        source_root=source_root,
        destination_root=tmp_path / "external",
        layout=TaskMaterializationLayout(
            layout_id="external.v1",
            solver_artifacts=(
                TaskArtifactProjection("second", "workspace/b.txt"),
                TaskArtifactProjection("first", "workspace/a.txt"),
            ),
            evaluator_private_artifact_ids=("task_json",),
        ),
    )

    assert native.semantic_bytes_sha256 == external.semantic_bytes_sha256
    assert [entry.artifact_id for entry in native.entries] == ["first", "second"]
    assert (
        native.to_record()
        == materialize_task(
            task,
            source_root=source_root,
            destination_root=tmp_path / "native-repeat",
            layout=TaskMaterializationLayout(
                layout_id="native.v1",
                solver_artifacts=(
                    TaskArtifactProjection("second", "input/second.txt"),
                    TaskArtifactProjection("first", "input/first.txt"),
                ),
                evaluator_private_artifact_ids=("task_json",),
            ),
        ).to_record()
    )
    assert not (tmp_path / "native" / "task.json").exists()
    assert not (tmp_path / "external" / "task.json").exists()


def test_materialization_requires_complete_explicit_visibility_classification(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    document = _write(source_root / "document.txt", b"solver")
    private = _write(source_root / "task.json", b"private criteria")
    task = _task(
        (
            _artifact("document", document, source_root),
            _artifact("task_json", private, source_root),
        )
    )

    with pytest.raises(TaskMaterializationError, match="unclassified"):
        materialize_task(
            task,
            source_root=source_root,
            destination_root=tmp_path / "workspace",
            layout=TaskMaterializationLayout(
                layout_id="missing-private.v1",
                solver_artifacts=(TaskArtifactProjection("document", "document.txt"),),
            ),
        )

    with pytest.raises(TaskMaterializationError, match="both solver-visible"):
        materialize_task(
            task,
            source_root=source_root,
            destination_root=tmp_path / "workspace-conflict",
            layout=TaskMaterializationLayout(
                layout_id="conflict.v1",
                solver_artifacts=(
                    TaskArtifactProjection("document", "document.txt"),
                    TaskArtifactProjection("task_json", "task.json"),
                ),
                evaluator_private_artifact_ids=("task_json",),
            ),
        )


@pytest.mark.parametrize(
    "source_path,destination_path",
    (
        ("documents/%2e%2e/private.txt", "input.txt"),
        ("documents/input.txt", "%2e%2e/private.txt"),
        ("documents/input.txt", "same.txt"),
    ),
)
def test_materialization_rejects_encoded_paths_and_destination_collisions(
    tmp_path: Path,
    source_path: str,
    destination_path: str,
) -> None:
    source_root = tmp_path / "source"
    source = _write(source_root / "documents" / "input.txt", b"solver")
    artifact = replace(
        _artifact("input", source, source_root),
        path=source_path,
    )
    if destination_path == "same.txt":
        second = _write(source_root / "documents" / "second.txt", b"second")
        artifacts = (artifact, _artifact("second", second, source_root))
    else:
        artifacts = (artifact,)

    with pytest.raises(TaskMaterializationError, match=r"path|collision"):
        projections = [TaskArtifactProjection("input", destination_path)]
        if destination_path == "same.txt":
            projections.append(TaskArtifactProjection("second", "SAME.txt"))
        materialize_task(
            _task(artifacts),
            source_root=source_root,
            destination_root=tmp_path / "workspace",
            layout=TaskMaterializationLayout(
                layout_id="hostile.v1",
                solver_artifacts=tuple(projections),
            ),
        )


def test_materialization_rejects_symlinks_hardlinks_and_bounds(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    outside = _write(tmp_path / "outside.txt", b"outside")
    (source_root / "links").mkdir(parents=True)
    (source_root / "links" / "symlink.txt").symlink_to(outside)
    symlink_artifact = ArtifactRecord(
        artifact_id="symlink",
        path="links/symlink.txt",
        sha256=_sha256(outside.read_bytes()),
        media_type="text/plain",
        size_bytes=outside.stat().st_size,
    )
    with pytest.raises(TaskMaterializationError, match=r"symlink|regular|open"):
        materialize_task(
            _task((symlink_artifact,)),
            source_root=source_root,
            destination_root=tmp_path / "symlink-workspace",
            layout=TaskMaterializationLayout(
                layout_id="symlink.v1",
                solver_artifacts=(TaskArtifactProjection("symlink", "input.txt"),),
            ),
        )

    ordinary = _write(source_root / "ordinary.txt", b"ordinary")
    hardlink = source_root / "hardlink.txt"
    os.link(ordinary, hardlink)
    hardlink_artifact = _artifact("hardlink", hardlink, source_root)
    with pytest.raises(TaskMaterializationError, match="hard link"):
        materialize_task(
            _task((hardlink_artifact,)),
            source_root=source_root,
            destination_root=tmp_path / "hardlink-workspace",
            layout=TaskMaterializationLayout(
                layout_id="hardlink.v1",
                solver_artifacts=(TaskArtifactProjection("hardlink", "input.txt"),),
            ),
        )

    bounded = _write(source_root / "bounded.txt", b"too large")
    with pytest.raises(TaskMaterializationError, match="per-file"):
        materialize_task(
            _task((_artifact("bounded", bounded, source_root),)),
            source_root=source_root,
            destination_root=tmp_path / "bounded-workspace",
            layout=TaskMaterializationLayout(
                layout_id="bounded.v1",
                solver_artifacts=(TaskArtifactProjection("bounded", "input.txt"),),
            ),
            limits=MaterializationLimits(max_file_bytes=3),
        )


def test_materialization_enforces_count_total_and_integer_limits(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    first = _write(source_root / "first.txt", b"first")
    second = _write(source_root / "second.txt", b"second")
    task = _task(
        (
            _artifact("first", first, source_root),
            _artifact("second", second, source_root),
        )
    )
    layout = TaskMaterializationLayout(
        layout_id="limits.v1",
        solver_artifacts=(
            TaskArtifactProjection("first", "first.txt"),
            TaskArtifactProjection("second", "second.txt"),
        ),
    )

    with pytest.raises(TaskMaterializationError, match="file-count"):
        materialize_task(
            task,
            source_root=source_root,
            destination_root=tmp_path / "count-workspace",
            layout=layout,
            limits=MaterializationLimits(max_files=1),
        )
    with pytest.raises(TaskMaterializationError, match="total"):
        materialize_task(
            task,
            source_root=source_root,
            destination_root=tmp_path / "total-workspace",
            layout=layout,
            limits=MaterializationLimits(max_total_bytes=9),
        )
    with pytest.raises(ValueError, match="positive integer"):
        MaterializationLimits(max_files=1.5)  # type: ignore[arg-type]


def test_materialization_anchors_source_parent_during_symlink_swap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_root = tmp_path / "source"
    trusted = _write(source_root / "inside" / "input.txt", b"trusted")
    outside = tmp_path / "outside"
    _write(outside / "input.txt", b"untrusted")
    task = _task((_artifact("input", trusted, source_root),))
    original_open = os.open
    swapped = False

    def swap_before_leaf_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal swapped
        if path == "input.txt" and dir_fd is not None and not swapped:
            swapped = True
            (source_root / "inside").rename(source_root / "inside-original")
            (source_root / "inside").symlink_to(outside, target_is_directory=True)
        return original_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", swap_before_leaf_open)

    materialize_task(
        task,
        source_root=source_root,
        destination_root=tmp_path / "workspace",
        layout=TaskMaterializationLayout(
            layout_id="source-race.v1",
            solver_artifacts=(TaskArtifactProjection("input", "output.txt"),),
        ),
    )

    assert (tmp_path / "workspace" / "output.txt").read_bytes() == b"trusted"


def test_materialization_rejects_symlink_in_source_root_ancestor(
    tmp_path: Path,
) -> None:
    real_parent = tmp_path / "real-parent"
    source_root = real_parent / "source"
    source = _write(source_root / "input.txt", b"trusted")
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(real_parent, target_is_directory=True)
    task = _task((_artifact("input", source, source_root),))

    with pytest.raises(TaskMaterializationError, match="source root"):
        materialize_task(
            task,
            source_root=linked_parent / "source",
            destination_root=tmp_path / "workspace",
            layout=TaskMaterializationLayout(
                layout_id="source-root-ancestor.v1",
                solver_artifacts=(TaskArtifactProjection("input", "output.txt"),),
            ),
        )

    assert not (tmp_path / "workspace").exists()


def test_materialization_fails_closed_on_destination_root_parent_swap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_root = tmp_path / "source"
    source = _write(source_root / "input.txt", b"trusted")
    destination_parent = tmp_path / "destination-parent"
    destination_parent.mkdir()
    destination_root = destination_parent / "workspace"
    moved_parent = tmp_path / "destination-parent-owned"
    outside = tmp_path / "outside"
    outside.mkdir()
    marker = _write(outside / "keep.txt", b"keep")
    original_mkdir = os.mkdir
    swapped = False

    def swap_parent_before_root_creation(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> None:
        nonlocal swapped
        if not swapped and (
            Path(path) == destination_root
            or (path == destination_root.name and dir_fd is not None)
        ):
            swapped = True
            destination_parent.rename(moved_parent)
            destination_parent.symlink_to(outside, target_is_directory=True)
        original_mkdir(path, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "mkdir", swap_parent_before_root_creation)

    with pytest.raises(TaskMaterializationError, match="destination parent changed"):
        materialize_task(
            _task((_artifact("input", source, source_root),)),
            source_root=source_root,
            destination_root=destination_root,
            layout=TaskMaterializationLayout(
                layout_id="destination-root-race.v1",
                solver_artifacts=(TaskArtifactProjection("input", "output.txt"),),
            ),
        )

    assert marker.read_bytes() == b"keep"
    assert not (outside / "workspace").exists()


def test_materialization_wraps_destination_root_creation_race(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_root = tmp_path / "source"
    source = _write(source_root / "input.txt", b"trusted")
    destination_root = tmp_path / "workspace"
    original_mkdir = os.mkdir
    appeared = False

    def create_competing_root(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> None:
        nonlocal appeared
        if path == destination_root.name and dir_fd is not None and not appeared:
            appeared = True
            original_mkdir(path, mode, dir_fd=dir_fd)
        original_mkdir(path, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "mkdir", create_competing_root)

    with pytest.raises(
        TaskMaterializationError,
        match="could not create materialization destination root",
    ):
        materialize_task(
            _task((_artifact("input", source, source_root),)),
            source_root=source_root,
            destination_root=destination_root,
            layout=TaskMaterializationLayout(
                layout_id="destination-root-appeared.v1",
                solver_artifacts=(TaskArtifactProjection("input", "output.txt"),),
            ),
        )

    assert destination_root.is_dir()
    assert not any(destination_root.iterdir())


def test_materialization_rejects_destination_root_replaced_before_stat(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_root = tmp_path / "source"
    source = _write(source_root / "input.txt", b"trusted")
    destination_root = tmp_path / "workspace"
    created_root = tmp_path / "workspace-created-by-materializer"
    original_directory_stat = materialization_module._directory_stat_at
    swapped = False

    def replace_root_before_stat(
        parent_fd: int,
        name: str,
        field_name: str,
    ) -> os.stat_result:
        nonlocal swapped
        if field_name == "materialization destination root" and not swapped:
            swapped = True
            destination_root.rename(created_root)
            destination_root.mkdir()
        return original_directory_stat(parent_fd, name, field_name)

    monkeypatch.setattr(
        materialization_module,
        "_directory_stat_at",
        replace_root_before_stat,
    )

    with pytest.raises(TaskMaterializationError, match="root changed"):
        materialize_task(
            _task((_artifact("input", source, source_root),)),
            source_root=source_root,
            destination_root=destination_root,
            layout=TaskMaterializationLayout(
                layout_id="destination-root-pre-stat.v1",
                solver_artifacts=(TaskArtifactProjection("input", "output.txt"),),
            ),
        )

    assert created_root.is_dir()
    assert destination_root.is_dir()
    assert not (destination_root / "output.txt").exists()


def test_materialization_fails_closed_on_destination_parent_swap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_root = tmp_path / "source"
    source = _write(source_root / "input.txt", b"trusted")
    outside = tmp_path / "outside"
    outside.mkdir()
    marker = _write(outside / "keep.txt", b"keep")
    destination_root = tmp_path / "workspace"
    original_open = os.open
    swapped = False

    def swap_before_destination_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal swapped
        if (
            path == "output.txt"
            and flags & os.O_CREAT
            and dir_fd is not None
            and not swapped
        ):
            swapped = True
            (destination_root / "nested").rename(destination_root / "owned")
            (destination_root / "nested").symlink_to(
                outside,
                target_is_directory=True,
            )
        return original_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", swap_before_destination_open)

    with pytest.raises(TaskMaterializationError, match=r"symlink|non-directory"):
        materialize_task(
            _task((_artifact("input", source, source_root),)),
            source_root=source_root,
            destination_root=destination_root,
            layout=TaskMaterializationLayout(
                layout_id="destination-race.v1",
                solver_artifacts=(
                    TaskArtifactProjection("input", "nested/output.txt"),
                ),
            ),
        )

    assert marker.read_bytes() == b"keep"
    assert not (outside / "output.txt").exists()
    assert destination_root.is_dir()


def test_materialization_rejects_replaced_destination_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_root = tmp_path / "source"
    source = _write(source_root / "input.txt", b"trusted")
    destination_root = tmp_path / "workspace"
    original_open = os.open
    swapped = False

    def replace_directory_before_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal swapped
        if path == "nested" and dir_fd is not None and not swapped:
            swapped = True
            (destination_root / "nested").rename(destination_root / "nested-owned")
            replacement = destination_root / "nested"
            replacement.mkdir()
            _write(replacement / "injected.txt", b"not in the manifest")
        return original_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", replace_directory_before_open)

    with pytest.raises(
        TaskMaterializationError,
        match=r"directory changed|unexpected or missing",
    ):
        materialize_task(
            _task((_artifact("input", source, source_root),)),
            source_root=source_root,
            destination_root=destination_root,
            layout=TaskMaterializationLayout(
                layout_id="destination-directory-race.v1",
                solver_artifacts=(
                    TaskArtifactProjection("input", "nested/output.txt"),
                ),
            ),
        )

    assert (destination_root / "nested" / "injected.txt").read_bytes() == (
        b"not in the manifest"
    )


def test_materialization_rejects_destination_directory_replaced_before_stat(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_root = tmp_path / "source"
    source = _write(source_root / "input.txt", b"trusted")
    destination_root = tmp_path / "workspace"
    created_directory = tmp_path / "nested-created-by-materializer"
    original_directory_stat = materialization_module._directory_stat_at
    swapped = False

    def replace_directory_before_stat(
        parent_fd: int,
        name: str,
        field_name: str,
    ) -> os.stat_result:
        nonlocal swapped
        if field_name == "materialization destination directory" and not swapped:
            swapped = True
            (destination_root / "nested").rename(created_directory)
            (destination_root / "nested").mkdir()
        return original_directory_stat(parent_fd, name, field_name)

    monkeypatch.setattr(
        materialization_module,
        "_directory_stat_at",
        replace_directory_before_stat,
    )

    with pytest.raises(TaskMaterializationError, match="directory changed"):
        materialize_task(
            _task((_artifact("input", source, source_root),)),
            source_root=source_root,
            destination_root=destination_root,
            layout=TaskMaterializationLayout(
                layout_id="destination-directory-pre-stat.v1",
                solver_artifacts=(
                    TaskArtifactProjection("input", "nested/output.txt"),
                ),
            ),
        )

    assert created_directory.is_dir()
    assert not (destination_root / "nested" / "output.txt").exists()


def test_materialization_cleanup_never_deletes_replacement_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_root = tmp_path / "source"
    source = _write(source_root / "input.txt", b"trusted")
    destination_root = tmp_path / "workspace"
    created_root = tmp_path / "workspace-created-by-materializer"

    def fail_copy(
        source_fd: int,
        destination_fd: int,
        *,
        artifact: ArtifactRecord,
        max_bytes: int,
    ) -> tuple[str, int]:
        del source_fd, destination_fd, artifact, max_bytes
        destination_root.rename(created_root)
        destination_root.mkdir()
        _write(destination_root / "victim.txt", b"unrelated")
        raise TaskMaterializationError("injected copy failure")

    monkeypatch.setattr(materialization_module, "_copy_verified", fail_copy)

    with pytest.raises(TaskMaterializationError, match="injected copy failure"):
        materialize_task(
            _task((_artifact("input", source, source_root),)),
            source_root=source_root,
            destination_root=destination_root,
            layout=TaskMaterializationLayout(
                layout_id="cleanup-root-race.v1",
                solver_artifacts=(TaskArtifactProjection("input", "output.txt"),),
            ),
        )

    assert (destination_root / "victim.txt").read_bytes() == b"unrelated"
    assert created_root.is_dir()


def test_materialization_final_seal_rejects_unmanifested_destination_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_root = tmp_path / "source"
    source = _write(source_root / "input.txt", b"trusted")
    destination_root = tmp_path / "workspace"
    original_verify = materialization_module._verify_destination_identity
    injected = False

    def inject_then_verify(
        root_fd: int,
        relative_path: str,
        expected_stat: os.stat_result,
        expected_sha256: str,
        expected_size: int,
    ) -> None:
        nonlocal injected
        if not injected:
            injected = True
            _write(destination_root / "injected.txt", b"not in the manifest")
        original_verify(
            root_fd,
            relative_path,
            expected_stat,
            expected_sha256,
            expected_size,
        )

    monkeypatch.setattr(
        materialization_module,
        "_verify_destination_identity",
        inject_then_verify,
    )

    with pytest.raises(TaskMaterializationError, match="unexpected or missing"):
        materialize_task(
            _task((_artifact("input", source, source_root),)),
            source_root=source_root,
            destination_root=destination_root,
            layout=TaskMaterializationLayout(
                layout_id="final-tree-seal.v1",
                solver_artifacts=(TaskArtifactProjection("input", "output.txt"),),
            ),
        )

    assert (destination_root / "injected.txt").read_bytes() == b"not in the manifest"


def test_materialization_final_seal_rechecks_directory_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_root = tmp_path / "source"
    source = _write(source_root / "input.txt", b"trusted")
    destination_root = tmp_path / "workspace"
    original_listdir = os.listdir
    injected = False

    def inject_after_snapshot(path: int) -> list[str]:
        nonlocal injected
        names = original_listdir(path)
        if not injected:
            injected = True
            _write(destination_root / "injected.txt", b"not in the snapshot")
        return names

    monkeypatch.setattr(os, "listdir", inject_after_snapshot)

    with pytest.raises(TaskMaterializationError, match="changed during sealing"):
        materialize_task(
            _task((_artifact("input", source, source_root),)),
            source_root=source_root,
            destination_root=destination_root,
            layout=TaskMaterializationLayout(
                layout_id="final-tree-resnapshot.v1",
                solver_artifacts=(TaskArtifactProjection("input", "output.txt"),),
            ),
        )

    assert (destination_root / "injected.txt").read_bytes() == b"not in the snapshot"


def test_materialization_final_seal_rejects_in_place_destination_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_root = tmp_path / "source"
    source = _write(source_root / "input.txt", b"trusted")
    destination_root = tmp_path / "workspace"
    original_verify = materialization_module._verify_destination_identity
    mutated = False

    def mutate_then_verify(
        root_fd: int,
        relative_path: str,
        expected_stat: os.stat_result,
        expected_sha256: str,
        expected_size: int,
    ) -> None:
        nonlocal mutated
        if not mutated:
            mutated = True
            (destination_root / relative_path).write_bytes(b"tampered")
        original_verify(
            root_fd,
            relative_path,
            expected_stat,
            expected_sha256,
            expected_size,
        )

    monkeypatch.setattr(
        materialization_module,
        "_verify_destination_identity",
        mutate_then_verify,
    )

    with pytest.raises(TaskMaterializationError, match="bytes changed"):
        materialize_task(
            _task((_artifact("input", source, source_root),)),
            source_root=source_root,
            destination_root=destination_root,
            layout=TaskMaterializationLayout(
                layout_id="final-seal.v1",
                solver_artifacts=(
                    TaskArtifactProjection("input", "nested/output.txt"),
                ),
            ),
        )

    assert (destination_root / "nested" / "output.txt").read_bytes() == b"tampered"


def _task(artifacts: tuple[ArtifactRecord, ...]) -> CanonicalTask:
    return CanonicalTask(
        task_id="harvey_lab:fixture/task",
        family="harvey_lab",
        scoring_mode="lab_native",
        suite_version="fixture",
        source_id="fixture-task",
        task_sha256="f" * 64,
        artifacts=artifacts,
    )


def _artifact(artifact_id: str, path: Path, root: Path) -> ArtifactRecord:
    payload = path.read_bytes()
    return ArtifactRecord(
        artifact_id=artifact_id,
        path=path.relative_to(root).as_posix(),
        sha256=_sha256(payload),
        media_type="text/plain",
        size_bytes=len(payload),
    )


def _write(path: Path, payload: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
