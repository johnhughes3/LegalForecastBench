from __future__ import annotations

import hashlib
import stat
from dataclasses import replace
from pathlib import Path

import pytest
from legalforecast.multiharness.material_separation import (
    MaterialAccessError,
    MaterialSeparationLayout,
    evaluator_material_access,
    materialize_separated_task,
    solver_material_access,
)
from legalforecast.multiharness.materialization import TaskArtifactProjection
from legalforecast.multiharness.spec import ArtifactRecord, CanonicalTask


def test_materializes_disjoint_read_only_planes_and_manifests(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    document = _write(source_root / "documents" / "input.txt", b"solver input")
    rubric = _write(source_root / "rubrics" / "rubric.json", b'{"private":true}')
    gold = _write(source_root / "answers" / "gold.txt", b"private answer")
    task = _task(
        (
            _artifact("gold", gold, source_root),
            _artifact("document", document, source_root),
            _artifact("rubric", rubric, source_root),
        )
    )

    separated = materialize_separated_task(
        task,
        source_root=source_root,
        solver_root=tmp_path / "solver",
        evaluator_private_root=tmp_path / "evaluator-private",
        layout=MaterialSeparationLayout(
            layout_id="fixture.v1",
            solver_artifacts=(
                TaskArtifactProjection("document", "input/document.txt"),
            ),
            evaluator_private_artifacts=(
                TaskArtifactProjection("rubric", "rubric.json"),
                TaskArtifactProjection("gold", "gold.txt"),
            ),
        ),
    )

    assert (separated.solver_root / "input" / "document.txt").read_bytes() == (
        b"solver input"
    )
    assert not (separated.solver_root / "rubric.json").exists()
    assert not (separated.solver_root / "gold.txt").exists()
    assert (separated.evaluator_private_root / "rubric.json").read_bytes() == (
        b'{"private":true}'
    )
    assert (separated.evaluator_private_root / "gold.txt").read_bytes() == (
        b"private answer"
    )
    assert not (separated.evaluator_private_root / "input" / "document.txt").exists()
    assert [entry.artifact_id for entry in separated.solver_manifest.entries] == [
        "document"
    ]
    assert [
        entry.artifact_id for entry in separated.evaluator_private_manifest.entries
    ] == ["gold", "rubric"]
    assert separated.to_record()["separation_sha256"] == (separated.separation_sha256)
    assert stat.S_IMODE(separated.solver_root.stat().st_mode) == 0o555
    assert stat.S_IMODE(separated.evaluator_private_root.stat().st_mode) == 0o500
    assert (
        stat.S_IMODE((separated.evaluator_private_root / "gold.txt").stat().st_mode)
        == 0o400
    )


def test_hidden_material_canaries_fail_closed_in_both_directions(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    solver_canary = _write(
        source_root / "solver-canary.txt",
        b"SOLVER_ONLY_CANARY",
    )
    private_canary = _write(
        source_root / "private-canary.txt",
        b"EVALUATOR_PRIVATE_CANARY",
    )
    separated = materialize_separated_task(
        _task(
            (
                _artifact("private-canary", private_canary, source_root),
                _artifact("solver-canary", solver_canary, source_root),
            )
        ),
        source_root=source_root,
        solver_root=tmp_path / "solver",
        evaluator_private_root=tmp_path / "evaluator-private",
        layout=MaterialSeparationLayout(
            layout_id="canary.v1",
            solver_artifacts=(
                TaskArtifactProjection("solver-canary", "solver-canary.txt"),
            ),
            evaluator_private_artifacts=(
                TaskArtifactProjection("private-canary", "private-canary.txt"),
            ),
        ),
    )
    deliverable_root = tmp_path / "sealed-deliverable"
    _write(deliverable_root / "answer.txt", b"sealed answer")
    _seal_fixture(deliverable_root)

    solver_access = solver_material_access(separated)
    evaluator_access = evaluator_material_access(
        separated,
        sealed_deliverable_root=deliverable_root,
        sealed_deliverable_sha256="sha256:" + "d" * 64,
    )

    assert solver_access.read_bytes("/workspace/input/solver-canary.txt") == (
        b"SOLVER_ONLY_CANARY"
    )
    assert (
        evaluator_access.read_bytes("/evaluation/private/private-canary.txt")
        == b"EVALUATOR_PRIVATE_CANARY"
    )
    assert evaluator_access.read_bytes("/evaluation/deliverable/answer.txt") == (
        b"sealed answer"
    )
    assert solver_access.list_directory("/workspace/input") == ("solver-canary.txt",)
    assert evaluator_access.list_directory("/evaluation/private") == (
        "private-canary.txt",
    )
    with pytest.raises(MaterialAccessError, match="not mounted"):
        solver_access.read_bytes("/evaluation/private/private-canary.txt")
    with pytest.raises(MaterialAccessError, match="not mounted"):
        solver_access.list_directory("/evaluation/private")
    with pytest.raises(MaterialAccessError, match="not mounted"):
        evaluator_access.read_bytes("/workspace/input/solver-canary.txt")
    with pytest.raises(MaterialAccessError, match="not mounted"):
        evaluator_access.list_directory("/workspace/input")
    assert tuple(mount.purpose for mount in solver_access.mounts) == ("solver_input",)
    assert tuple(mount.purpose for mount in evaluator_access.mounts) == (
        "sealed_deliverable",
        "evaluator_private",
    )


def test_rejects_overlapping_roots_and_incomplete_classification(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    document = _write(source_root / "document.txt", b"solver")
    private = _write(source_root / "private.txt", b"private")
    task = _task(
        (
            _artifact("document", document, source_root),
            _artifact("private", private, source_root),
        )
    )
    layout = MaterialSeparationLayout(
        layout_id="separation.v1",
        solver_artifacts=(TaskArtifactProjection("document", "document.txt"),),
        evaluator_private_artifacts=(TaskArtifactProjection("private", "private.txt"),),
    )

    with pytest.raises(ValueError, match="disjoint"):
        materialize_separated_task(
            task,
            source_root=source_root,
            solver_root=tmp_path / "workspace",
            evaluator_private_root=tmp_path / "workspace" / "private",
            layout=layout,
        )
    with pytest.raises(ValueError, match="classified"):
        materialize_separated_task(
            task,
            source_root=source_root,
            solver_root=tmp_path / "solver",
            evaluator_private_root=tmp_path / "evaluator-private",
            layout=MaterialSeparationLayout(
                layout_id="incomplete.v1",
                solver_artifacts=(TaskArtifactProjection("document", "document.txt"),),
                evaluator_private_artifacts=(),
            ),
        )


def test_access_plans_reject_writable_or_nested_inputs(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    document = _write(source_root / "document.txt", b"solver")
    private = _write(source_root / "private.txt", b"private")
    separated = materialize_separated_task(
        _task(
            (
                _artifact("document", document, source_root),
                _artifact("private", private, source_root),
            )
        ),
        source_root=source_root,
        solver_root=tmp_path / "solver",
        evaluator_private_root=tmp_path / "evaluator-private",
        layout=MaterialSeparationLayout(
            layout_id="access.v1",
            solver_artifacts=(TaskArtifactProjection("document", "document.txt"),),
            evaluator_private_artifacts=(
                TaskArtifactProjection("private", "private.txt"),
            ),
        ),
    )
    writable_deliverable = tmp_path / "writable-deliverable"
    _write(writable_deliverable / "answer.txt", b"answer")

    with pytest.raises(MaterialAccessError, match="read-only"):
        evaluator_material_access(
            separated,
            sealed_deliverable_root=writable_deliverable,
            sealed_deliverable_sha256="sha256:" + "d" * 64,
        )
    with pytest.raises(MaterialAccessError, match="disjoint"):
        evaluator_material_access(
            separated,
            sealed_deliverable_root=separated.evaluator_private_root,
            sealed_deliverable_sha256="sha256:" + "d" * 64,
        )


def test_access_revalidates_manifest_commitments_and_material_bytes(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    document = _write(source_root / "document.txt", b"solver")
    private = _write(source_root / "private.txt", b"private")
    separated = materialize_separated_task(
        _task(
            (
                _artifact("document", document, source_root),
                _artifact("private", private, source_root),
            )
        ),
        source_root=source_root,
        solver_root=tmp_path / "solver",
        evaluator_private_root=tmp_path / "evaluator-private",
        layout=MaterialSeparationLayout(
            layout_id="tamper.v1",
            solver_artifacts=(TaskArtifactProjection("document", "document.txt"),),
            evaluator_private_artifacts=(
                TaskArtifactProjection("private", "private.txt"),
            ),
        ),
    )

    with pytest.raises(ValueError, match="manifest sha256"):
        replace(
            separated.solver_manifest,
            manifest_sha256="sha256:" + "0" * 64,
        )
    solver_file = separated.solver_root / "document.txt"
    solver_file.chmod(0o644)
    solver_file.write_bytes(b"changed")
    solver_file.chmod(0o444)
    with pytest.raises(MaterialAccessError, match=r"bytes changed|size changed"):
        solver_material_access(separated)


def test_access_canaries_reject_encoded_and_traversing_runtime_paths(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    document = _write(source_root / "document.txt", b"solver")
    private = _write(source_root / "private.txt", b"private")
    separated = materialize_separated_task(
        _task(
            (
                _artifact("document", document, source_root),
                _artifact("private", private, source_root),
            )
        ),
        source_root=source_root,
        solver_root=tmp_path / "solver",
        evaluator_private_root=tmp_path / "evaluator-private",
        layout=MaterialSeparationLayout(
            layout_id="runtime-path.v1",
            solver_artifacts=(TaskArtifactProjection("document", "document.txt"),),
            evaluator_private_artifacts=(
                TaskArtifactProjection("private", "private.txt"),
            ),
        ),
    )
    access = solver_material_access(separated)

    with pytest.raises(MaterialAccessError, match="percent encoding"):
        access.read_bytes("/workspace/input/%2e%2e/private.txt")
    with pytest.raises(MaterialAccessError, match=r"traversal|not mounted"):
        access.read_bytes("/workspace/input/../private.txt")


def test_access_sources_remain_anchored_after_working_directory_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_root = tmp_path / "source"
    document = _write(source_root / "document.txt", b"solver")
    private = _write(source_root / "private.txt", b"private")
    monkeypatch.chdir(tmp_path)
    separated = materialize_separated_task(
        _task(
            (
                _artifact("document", document, source_root),
                _artifact("private", private, source_root),
            )
        ),
        source_root=Path("source"),
        solver_root=Path("solver"),
        evaluator_private_root=Path("evaluator-private"),
        layout=MaterialSeparationLayout(
            layout_id="anchored.v1",
            solver_artifacts=(TaskArtifactProjection("document", "document.txt"),),
            evaluator_private_artifacts=(
                TaskArtifactProjection("private", "private.txt"),
            ),
        ),
    )
    other_directory = tmp_path / "other"
    other_directory.mkdir()
    monkeypatch.chdir(other_directory)

    assert separated.solver_root.is_absolute()
    assert (
        solver_material_access(separated).read_bytes("/workspace/input/document.txt")
        == b"solver"
    )


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
        sha256=hashlib.sha256(payload).hexdigest(),
        media_type="text/plain",
        size_bytes=len(payload),
    )


def _write(path: Path, payload: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


def _seal_fixture(root: Path) -> None:
    for path in sorted(root.rglob("*"), reverse=True):
        path.chmod(0o555 if path.is_dir() else 0o444)
    root.chmod(0o555)
