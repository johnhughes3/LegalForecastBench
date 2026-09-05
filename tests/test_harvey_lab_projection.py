from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest
from legalforecast.multiharness.harvey_lab_projection import (
    ISSUE_196_LAB_TASK_ID,
    NATIVE_LAYOUT_ID,
    ROOT_MANIFEST_NAME,
    SOLVER_VISIBLE_LAYOUT_ID,
    TASK_DESCRIPTOR_NAME,
    HarveyLabPin,
    HarveyLabProjectionError,
    _archive_pinned_source,
    _record_sha256,
    classify_harvey_lab_task,
    harvey_lab_layout_map,
    issue_196_pin,
    load_harvey_lab_projection_manifest,
    project_harvey_lab_suite,
    scan_projection_for_private_markers,
    solver_visible_layout,
    verify_harvey_lab_projection,
)
from legalforecast.multiharness.material_separation import materialize_separated_task

PIN_FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "harvey_lab"
    / "pinned-evaluator-seam-73feb91.json"
)
GOLD_MARKER = "GOLD_ANSWER_PRIVATE"
PRIVATE_CANARY = "EVALUATOR_PRIVATE_CANARY"
FIXTURE_PIN = HarveyLabPin(
    repository="https://example.com/legalforecast-lab-fixture",
    commit="a" * 40,
    tree="b" * 40,
)


def test_issue_196_projection_is_deterministic_and_omits_private_material(
    tmp_path: Path,
) -> None:
    source = _issue_196_source(tmp_path / "lab")
    first = project_harvey_lab_suite(
        source_root=source,
        solver_root=tmp_path / "solver-a",
        evaluator_private_root=tmp_path / "private-a",
        pin=FIXTURE_PIN,
    )
    second = project_harvey_lab_suite(
        source_root=source,
        solver_root=tmp_path / "solver-b",
        evaluator_private_root=tmp_path / "private-b",
        pin=FIXTURE_PIN,
    )

    assert first.manifest.to_record() == second.manifest.to_record()
    assert first.manifest.layout_id == SOLVER_VISIBLE_LAYOUT_ID
    assert first.manifest.pin == FIXTURE_PIN
    assert first.manifest.layout_map == harvey_lab_layout_map()
    assert len(first.manifest.tasks) == 1
    task = first.manifest.tasks[0]
    assert task.lab_task_id == ISSUE_196_LAB_TASK_ID
    assert task.category == "employment-labor"
    assert task.expected_deliverable == "issue-identification-memo.docx"
    assert task.task_id == f"harvey_lab:{ISSUE_196_LAB_TASK_ID}"
    document_names = {
        Path(item.path).name for item in task.files if item.role == "document"
    }
    assert document_names == _pin_document_names()
    assert (first.solver_root / ROOT_MANIFEST_NAME).is_file()
    assert (first.solver_root / task.relative_path / "instructions.txt").read_text(
        encoding="utf-8"
    ) == _pin_instructions()
    assert not (first.solver_root / task.relative_path / "task.json").exists()
    assert not (first.solver_root / task.relative_path / "gold-answers.json").exists()
    assert (
        first.evaluator_private_root / "tasks" / ISSUE_196_LAB_TASK_ID / "task.json"
    ).is_file()
    assert GOLD_MARKER in (
        first.evaluator_private_root
        / "tasks"
        / ISSUE_196_LAB_TASK_ID
        / "gold-answers.json"
    ).read_text(encoding="utf-8")
    scan_projection_for_private_markers(first.solver_root)
    verify_harvey_lab_projection(first.solver_root)
    loaded = load_harvey_lab_projection_manifest(first.solver_root)
    assert loaded.manifest_sha256 == first.manifest.manifest_sha256
    descriptor = json.loads(
        (first.solver_root / task.relative_path / "task-projection.json").read_text(
            encoding="utf-8"
        )
    )
    assert descriptor["task_sha256"] == task.task_sha256
    assert descriptor["expected_deliverables"] == list(task.expected_deliverables)
    descriptor_paths = {item["path"] for item in descriptor["files"]}
    assert "task-projection.json" not in descriptor_paths
    root_paths = {item.path for item in task.files}
    assert "task-projection.json" in root_paths
    assert "criteria" not in json.dumps(first.manifest.to_record())
    assert "match_criteria" not in json.dumps(first.manifest.to_record())
    solver_listing = " ".join(
        path.as_posix() for path in first.solver_root.rglob("*") if path.is_file()
    )
    assert "private" not in solver_listing
    assert first.solver_root.resolve() != first.evaluator_private_root.resolve()
    assert not first.solver_root.resolve().is_relative_to(
        first.evaluator_private_root.resolve()
    )


def test_projection_refuses_a_self_consistent_forged_task_digest(
    tmp_path: Path,
) -> None:
    result = project_harvey_lab_suite(
        source_root=_issue_196_source(tmp_path / "lab"),
        solver_root=tmp_path / "solver",
        evaluator_private_root=tmp_path / "private",
        pin=FIXTURE_PIN,
    )
    _make_tree_writable(result.solver_root)
    manifest_path = result.solver_root / ROOT_MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    task = manifest["tasks"][0]
    forged_digest = "c" * 64
    task["task_sha256"] = forged_digest

    descriptor_path = result.solver_root / task["relative_path"] / TASK_DESCRIPTOR_NAME
    descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
    descriptor["task_sha256"] = forged_digest
    descriptor_path.write_text(
        json.dumps(descriptor, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    descriptor_payload = descriptor_path.read_bytes()
    descriptor_entry = next(
        item for item in task["files"] if item["role"] == "task_descriptor"
    )
    descriptor_entry["sha256"] = hashlib.sha256(descriptor_payload).hexdigest()
    descriptor_entry["size_bytes"] = len(descriptor_payload)
    manifest["manifest_sha256"] = _record_sha256(
        {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(HarveyLabProjectionError, match="task_sha256"):
        verify_harvey_lab_projection(result.solver_root)


def test_native_and_external_layouts_have_equal_semantic_bytes(
    tmp_path: Path,
) -> None:
    source = _issue_196_source(tmp_path / "lab")
    staging = tmp_path / "staging"
    classified = classify_harvey_lab_task(
        source / "tasks" / ISSUE_196_LAB_TASK_ID,
        lab_root=source,
        staging_root=staging,
    )
    native = materialize_separated_task(
        classified.task,
        source_root=classified.staging_root,
        solver_root=tmp_path / "native-solver",
        evaluator_private_root=tmp_path / "native-private",
        layout=solver_visible_layout(
            classified,
            layout_id=NATIVE_LAYOUT_ID,
            destination_prefix="native",
        ),
    )
    external = materialize_separated_task(
        classified.task,
        source_root=classified.staging_root,
        solver_root=tmp_path / "external-solver",
        evaluator_private_root=tmp_path / "external-private",
        layout=solver_visible_layout(classified),
    )
    assert (
        native.solver_manifest.semantic_bytes_sha256
        == external.solver_manifest.semantic_bytes_sha256
    )
    assert native.solver_manifest.layout_id == NATIVE_LAYOUT_ID
    assert external.solver_manifest.layout_id == SOLVER_VISIBLE_LAYOUT_ID
    native_docs = {
        entry.sha256
        for entry in native.solver_manifest.entries
        if entry.artifact_id.startswith("document:")
    }
    external_docs = {
        entry.sha256
        for entry in external.solver_manifest.entries
        if entry.artifact_id.startswith("document:")
    }
    assert native_docs == external_docs


def test_existing_staging_root_is_refused(tmp_path: Path) -> None:
    source = _issue_196_source(tmp_path / "lab")
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "keep.txt").write_text("user data", encoding="utf-8")
    with pytest.raises(HarveyLabProjectionError, match="must be a fresh, absent path"):
        classify_harvey_lab_task(
            source / "tasks" / ISSUE_196_LAB_TASK_ID,
            lab_root=source,
            staging_root=staging,
        )
    assert (staging / "keep.txt").read_text(encoding="utf-8") == "user data"


def test_planting_gold_in_projection_fails_the_absence_scan(tmp_path: Path) -> None:
    source = _issue_196_source(tmp_path / "lab")
    result = project_harvey_lab_suite(
        source_root=source,
        solver_root=tmp_path / "solver",
        evaluator_private_root=tmp_path / "private",
        pin=FIXTURE_PIN,
    )
    planted = result.solver_root / "tasks" / ISSUE_196_LAB_TASK_ID / "gold-answers.json"
    _make_tree_writable(result.solver_root)
    planted.write_text(GOLD_MARKER, encoding="utf-8")
    with pytest.raises(
        HarveyLabProjectionError,
        match="evaluator-private material present",
    ):
        scan_projection_for_private_markers(result.solver_root)


def test_tampered_projected_byte_fails_hash_verification(tmp_path: Path) -> None:
    source = _issue_196_source(tmp_path / "lab")
    result = project_harvey_lab_suite(
        source_root=source,
        solver_root=tmp_path / "solver",
        evaluator_private_root=tmp_path / "private",
        pin=FIXTURE_PIN,
    )
    target = result.solver_root / "tasks" / ISSUE_196_LAB_TASK_ID / "instructions.txt"
    _make_tree_writable(result.solver_root)
    target.write_bytes(target.read_bytes() + b"x")
    with pytest.raises(
        HarveyLabProjectionError,
        match="projected file hash mismatch: "
        f"tasks/{ISSUE_196_LAB_TASK_ID}/instructions.txt",
    ):
        verify_harvey_lab_projection(result.solver_root)


def test_missing_manifest_field_is_named(tmp_path: Path) -> None:
    source = _issue_196_source(tmp_path / "lab")
    result = project_harvey_lab_suite(
        source_root=source,
        solver_root=tmp_path / "solver",
        evaluator_private_root=tmp_path / "private",
        pin=FIXTURE_PIN,
    )
    path = result.solver_root / ROOT_MANIFEST_NAME
    _make_tree_writable(result.solver_root)
    record = json.loads(path.read_text(encoding="utf-8"))
    del record["pin"]
    path.write_text(json.dumps(record, sort_keys=True), encoding="utf-8")
    with pytest.raises(HarveyLabProjectionError, match="missing field\\(s\\): pin"):
        load_harvey_lab_projection_manifest(result.solver_root)


def test_unlisted_file_in_projection_fails_verification(tmp_path: Path) -> None:
    source = _issue_196_source(tmp_path / "lab")
    result = project_harvey_lab_suite(
        source_root=source,
        solver_root=tmp_path / "solver",
        evaluator_private_root=tmp_path / "private",
        pin=FIXTURE_PIN,
    )
    extra = result.solver_root / "tasks" / ISSUE_196_LAB_TASK_ID / "notes.txt"
    _make_tree_writable(result.solver_root)
    extra.write_text("solver-visible extra", encoding="utf-8")
    with pytest.raises(HarveyLabProjectionError, match="unlisted file"):
        verify_harvey_lab_projection(result.solver_root)


def test_unknown_lab_task_id_fails_closed(tmp_path: Path) -> None:
    source = _issue_196_source(tmp_path / "lab")
    solver = tmp_path / "solver"
    private = tmp_path / "private"
    with pytest.raises(
        HarveyLabProjectionError,
        match="were not found: missing-task",
    ):
        project_harvey_lab_suite(
            source_root=source,
            solver_root=solver,
            evaluator_private_root=private,
            pin=FIXTURE_PIN,
            lab_task_ids=(ISSUE_196_LAB_TASK_ID, "missing-task"),
        )
    assert not solver.exists()
    assert not private.exists()


def test_symlink_in_projection_fails_verification(tmp_path: Path) -> None:
    source = _issue_196_source(tmp_path / "lab")
    result = project_harvey_lab_suite(
        source_root=source,
        solver_root=tmp_path / "solver",
        evaluator_private_root=tmp_path / "private",
        pin=FIXTURE_PIN,
    )
    secret = tmp_path / "gold-answers.json"
    secret.write_text("GOLD_ANSWER_PRIVATE hidden", encoding="utf-8")
    planted = result.solver_root / "tasks" / ISSUE_196_LAB_TASK_ID / "leak.json"
    _make_tree_writable(result.solver_root)
    planted.symlink_to(secret)
    with pytest.raises(HarveyLabProjectionError, match="symlink in solver projection"):
        verify_harvey_lab_projection(result.solver_root)
    with pytest.raises(HarveyLabProjectionError, match="symlink in solver projection"):
        scan_projection_for_private_markers(result.solver_root)


def test_fifo_in_source_documents_is_rejected(tmp_path: Path) -> None:
    source = _issue_196_source(tmp_path / "lab")
    os.mkfifo(source / "tasks" / ISSUE_196_LAB_TASK_ID / "documents" / "pipe")
    with pytest.raises(
        HarveyLabProjectionError,
        match="unsupported entry",
    ):
        project_harvey_lab_suite(
            source_root=source,
            solver_root=tmp_path / "solver",
            evaluator_private_root=tmp_path / "private",
            pin=FIXTURE_PIN,
        )


def test_fifo_in_projection_fails_verification(tmp_path: Path) -> None:
    source = _issue_196_source(tmp_path / "lab")
    result = project_harvey_lab_suite(
        source_root=source,
        solver_root=tmp_path / "solver",
        evaluator_private_root=tmp_path / "private",
        pin=FIXTURE_PIN,
    )
    planted = result.solver_root / "tasks" / ISSUE_196_LAB_TASK_ID / "pipe"
    _make_tree_writable(result.solver_root)
    os.mkfifo(planted)
    with pytest.raises(
        HarveyLabProjectionError,
        match="unsupported entry in solver projection",
    ):
        verify_harvey_lab_projection(result.solver_root)


def test_preexisting_staging_directory_is_not_deleted(tmp_path: Path) -> None:
    source = _issue_196_source(tmp_path / "lab")
    leftover = tmp_path / (
        ".harvey-lab-staging-employment-labor-"
        "identify-issues-in-counterparty-motion-brief"
    )
    leftover.mkdir()
    canary = leftover / "keep.txt"
    canary.write_text("keep", encoding="utf-8")
    project_harvey_lab_suite(
        source_root=source,
        solver_root=tmp_path / "solver",
        evaluator_private_root=tmp_path / "private",
        pin=FIXTURE_PIN,
    )
    assert canary.read_text(encoding="utf-8") == "keep"


def test_ignored_worktree_files_fail_official_pin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _issue_196_source(tmp_path / "lab")
    _init_git_repo(source)
    (source / ".gitignore").write_text("ignored.bin\n", encoding="utf-8")
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "lab-fixture",
        "GIT_AUTHOR_EMAIL": "lab-fixture@example.com",
        "GIT_COMMITTER_NAME": "lab-fixture",
        "GIT_COMMITTER_EMAIL": "lab-fixture@example.com",
    }
    subprocess.run(["git", "add", ".gitignore"], cwd=source, check=True, env=env)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=lab-fixture",
            "-c",
            "user.email=lab-fixture@example.com",
            "commit",
            "-qm",
            "ignore",
        ],
        cwd=source,
        check=True,
        env=env,
    )
    (source / "ignored.bin").write_bytes(b"secret")
    commit = (
        subprocess.check_output(
            ["git", "-C", str(source), "rev-parse", "HEAD"],
            text=True,
        )
        .strip()
        .casefold()
    )
    tree = (
        subprocess.check_output(
            ["git", "-C", str(source), "rev-parse", "HEAD^{tree}"],
            text=True,
        )
        .strip()
        .casefold()
    )
    pin = HarveyLabPin(
        repository="https://github.com/harveyai/harvey-labs",
        commit=commit,
        tree=tree,
    )
    monkeypatch.setattr(
        "legalforecast.multiharness.harvey_lab_projection.issue_196_pin",
        lambda: pin,
    )
    with pytest.raises(
        HarveyLabProjectionError,
        match="ignored files not present in the recorded pin",
    ):
        project_harvey_lab_suite(
            source_root=source,
            solver_root=tmp_path / "solver",
            evaluator_private_root=tmp_path / "private",
            pin=pin,
        )


def test_archive_exports_pin_tree_after_head_advances(tmp_path: Path) -> None:
    source = _issue_196_source(tmp_path / "lab")
    _init_git_repo(source)
    first_commit = (
        subprocess.check_output(
            ["git", "-C", str(source), "rev-parse", "HEAD"],
            text=True,
        )
        .strip()
        .casefold()
    )
    first_tree = (
        subprocess.check_output(
            ["git", "-C", str(source), "rev-parse", "HEAD^{tree}"],
            text=True,
        )
        .strip()
        .casefold()
    )
    marker = source / "tasks" / ISSUE_196_LAB_TASK_ID / "task.json"
    original = marker.read_bytes()
    marker.write_bytes(original + b"\nMUTATED_HEAD\n")
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "lab-fixture",
        "GIT_AUTHOR_EMAIL": "lab-fixture@example.com",
        "GIT_COMMITTER_NAME": "lab-fixture",
        "GIT_COMMITTER_EMAIL": "lab-fixture@example.com",
    }
    subprocess.run(["git", "add", "."], cwd=source, check=True, env=env)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=lab-fixture",
            "-c",
            "user.email=lab-fixture@example.com",
            "commit",
            "-qm",
            "advance-head",
        ],
        cwd=source,
        check=True,
        env=env,
    )
    snapshot = _archive_pinned_source(
        source,
        HarveyLabPin(
            repository="https://example.com/legalforecast-lab-fixture",
            commit=first_commit,
            tree=first_tree,
        ),
    )
    try:
        archived = snapshot / "tasks" / ISSUE_196_LAB_TASK_ID / "task.json"
        assert archived.read_bytes() == original
    finally:
        shutil.rmtree(snapshot, ignore_errors=True)


def test_archive_ignores_inherited_tar_options(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _issue_196_source(tmp_path / "lab")
    _init_git_repo(source)
    commit = (
        subprocess.check_output(
            ["git", "-C", str(source), "rev-parse", "HEAD"],
            text=True,
        )
        .strip()
        .casefold()
    )
    tree = (
        subprocess.check_output(
            ["git", "-C", str(source), "rev-parse", "HEAD^{tree}"],
            text=True,
        )
        .strip()
        .casefold()
    )
    monkeypatch.setenv("TAR_OPTIONS", "--transform=s,tasks,moved,")
    snapshot = _archive_pinned_source(
        source,
        HarveyLabPin(
            repository="https://example.com/legalforecast-lab-fixture",
            commit=commit,
            tree=tree,
        ),
    )
    try:
        assert (snapshot / "tasks" / ISSUE_196_LAB_TASK_ID / "task.json").is_file()
        assert not (snapshot / "moved").exists()
    finally:
        shutil.rmtree(snapshot, ignore_errors=True)


def test_official_pin_requires_authenticated_checkout(tmp_path: Path) -> None:
    source = _issue_196_source(tmp_path / "lab")
    with pytest.raises(
        HarveyLabProjectionError,
        match="not a Git checkout of the recorded pin",
    ):
        project_harvey_lab_suite(
            source_root=source,
            solver_root=tmp_path / "solver",
            evaluator_private_root=tmp_path / "private",
            pin=issue_196_pin(),
        )


def test_git_checkout_pin_mismatch_fails_closed(tmp_path: Path) -> None:
    source = _issue_196_source(tmp_path / "lab")
    _init_git_repo(source)
    with pytest.raises(
        HarveyLabProjectionError,
        match="does not match the recorded pin",
    ):
        project_harvey_lab_suite(
            source_root=source,
            solver_root=tmp_path / "solver",
            evaluator_private_root=tmp_path / "private",
        )


def test_unclassified_source_file_fails_closed(tmp_path: Path) -> None:
    source = _issue_196_source(tmp_path / "lab")
    notes = source / "tasks" / ISSUE_196_LAB_TASK_ID / "notes.txt"
    notes.write_text("not classified", encoding="utf-8")
    with pytest.raises(HarveyLabProjectionError, match="unclassified"):
        project_harvey_lab_suite(
            source_root=source,
            solver_root=tmp_path / "solver",
            evaluator_private_root=tmp_path / "private",
            pin=FIXTURE_PIN,
        )


def test_pinned_checkout_projection_preserves_document_hashes(
    tmp_path: Path,
) -> None:
    raw_root = os.environ.get("HARVEY_LAB_ROOT")
    if raw_root is None:
        pytest.skip("set HARVEY_LAB_ROOT to verify the pinned upstream checkout")
    result = project_harvey_lab_suite(
        source_root=Path(raw_root),
        solver_root=tmp_path / "solver",
        evaluator_private_root=tmp_path / "private",
        lab_task_ids=(ISSUE_196_LAB_TASK_ID,),
    )
    projected = {
        Path(item.path).name: item.sha256
        for item in result.manifest.tasks[0].files
        if item.role == "document"
    }
    expected = {Path(item["path"]).name: item["sha256"] for item in _pin_documents()}
    assert projected == expected
    scan_projection_for_private_markers(result.solver_root)


def test_pinned_checkout_projects_multi_and_undeclared_output_shapes(
    tmp_path: Path,
) -> None:
    raw_root = os.environ.get("HARVEY_LAB_ROOT")
    if raw_root is None:
        pytest.skip("set HARVEY_LAB_ROOT to verify the pinned upstream checkout")
    task_ids = (
        "contracts/healthcare/clinical-trial-agreement-first-draft",
        "corporate-governance/draft-markup-of-proposed-settlement-agreement",
    )

    result = project_harvey_lab_suite(
        source_root=Path(raw_root),
        solver_root=tmp_path / "solver",
        evaluator_private_root=tmp_path / "private",
        lab_task_ids=task_ids,
    )

    tasks = {task.lab_task_id: task for task in result.manifest.tasks}
    assert tasks[task_ids[0]].expected_deliverables == ()
    assert tasks[task_ids[1]].expected_deliverables == (
        "redlined-settlement-agreement.docx",
        "settlement-markup-commentary-memo.docx",
    )
    assert result.skipped == ()
    verify_harvey_lab_projection(result.solver_root)


def test_pinned_checkout_projects_every_xlsx_output_shape(tmp_path: Path) -> None:
    raw_root = os.environ.get("HARVEY_LAB_ROOT")
    if raw_root is None:
        pytest.skip("set HARVEY_LAB_ROOT to verify the pinned upstream checkout")
    source_root = Path(raw_root)
    xlsx_task_ids: list[str] = []
    mixed_count = 0
    xlsx_only_count = 0
    for task_json in sorted((source_root / "tasks").rglob("task.json")):
        record = json.loads(task_json.read_text(encoding="utf-8"))
        declared = record.get("deliverables", {})
        assert isinstance(declared, dict)
        suffixes = {Path(str(value)).suffix for value in declared.values()}
        if ".xlsx" not in suffixes:
            continue
        xlsx_task_ids.append(
            task_json.parent.relative_to(source_root / "tasks").as_posix()
        )
        if suffixes == {".xlsx"}:
            xlsx_only_count += 1
        else:
            mixed_count += 1

    assert (len(xlsx_task_ids), mixed_count, xlsx_only_count) == (39, 35, 4)
    result = project_harvey_lab_suite(
        source_root=source_root,
        solver_root=tmp_path / "solver",
        evaluator_private_root=tmp_path / "private",
        lab_task_ids=tuple(xlsx_task_ids),
    )

    assert len(result.manifest.tasks) == 39
    assert result.skipped == ()
    assert all(
        any(name.endswith(".xlsx") for name in task.expected_deliverables)
        for task in result.manifest.tasks
    )
    verify_harvey_lab_projection(result.solver_root)


def _issue_196_source(lab_root: Path) -> Path:
    task_dir = lab_root / "tasks" / ISSUE_196_LAB_TASK_ID
    documents_dir = task_dir / "documents"
    documents_dir.mkdir(parents=True)
    criteria = [
        {
            "id": f"c{index:02d}",
            "title": f"Criterion {index}",
            "match_criteria": f"{PRIVATE_CANARY} private rubric {index}",
            "deliverables": ["issue-identification-memo.docx"],
        }
        for index in range(1, 24)
    ]
    (task_dir / "task.json").write_text(
        json.dumps(
            {
                "id": ISSUE_196_LAB_TASK_ID,
                "instructions": _pin_instructions(),
                "expected_deliverable": "issue-identification-memo.docx",
                "criteria": criteria,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (task_dir / "gold-answers.json").write_text(
        json.dumps({"marker": GOLD_MARKER, "answers": ["sealed"]}),
        encoding="utf-8",
    )
    for index, document in enumerate(_pin_documents(), start=1):
        name = Path(document["path"]).name
        (documents_dir / name).write_bytes(f"fixture-document-{index}\n".encode())
    return lab_root


def _add_unselected_task(lab_root: Path) -> None:
    """Plant a valid lexically earlier task that Tier-0 must never select."""

    task_dir = lab_root / "tasks" / "aaa-practice" / "decoy-task"
    documents_dir = task_dir / "documents"
    documents_dir.mkdir(parents=True)
    (task_dir / "task.json").write_text(
        json.dumps(
            {
                "id": "aaa-practice/decoy-task",
                "instructions": "Produce decoy.docx.",
                "expected_deliverable": "decoy.docx",
                "criteria": [
                    {
                        "id": "decoy",
                        "title": "Decoy criterion",
                        "match_criteria": "Evaluator-private decoy criterion",
                        "deliverables": ["decoy.docx"],
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (documents_dir / "decoy.txt").write_text("decoy\n", encoding="utf-8")


def _pin_fixture() -> dict[str, object]:
    return json.loads(PIN_FIXTURE.read_text(encoding="utf-8"))


def _pin_instructions() -> str:
    task = _pin_fixture()["task"]
    assert isinstance(task, dict)
    visible = task["solver_visible"]
    assert isinstance(visible, dict)
    instructions = visible["instructions"]
    assert isinstance(instructions, str)
    return instructions


def _pin_documents() -> list[dict[str, str]]:
    task = _pin_fixture()["task"]
    assert isinstance(task, dict)
    visible = task["solver_visible"]
    assert isinstance(visible, dict)
    documents = visible["documents"]
    assert isinstance(documents, list)
    return [
        {"path": str(item["path"]), "sha256": str(item["sha256"])}
        for item in documents
        if isinstance(item, dict)
    ]


def _pin_document_names() -> set[str]:
    return {Path(item["path"]).name for item in _pin_documents()}


def _make_tree_writable(root: Path) -> None:
    for path in [root, *root.rglob("*")]:
        mode = path.stat().st_mode
        path.chmod(mode | stat.S_IWUSR | stat.S_IXUSR | stat.S_IRUSR)


def _init_git_repo(root: Path) -> None:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "lab-fixture",
        "GIT_AUTHOR_EMAIL": "lab-fixture@example.com",
        "GIT_COMMITTER_NAME": "lab-fixture",
        "GIT_COMMITTER_EMAIL": "lab-fixture@example.com",
    }
    subprocess.run(["git", "init", "-q"], cwd=root, check=True, env=env)
    subprocess.run(["git", "add", "."], cwd=root, check=True, env=env)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=lab-fixture",
            "-c",
            "user.email=lab-fixture@example.com",
            "commit",
            "-qm",
            "fixture",
        ],
        cwd=root,
        check=True,
        env=env,
    )
