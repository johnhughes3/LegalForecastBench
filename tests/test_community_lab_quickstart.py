"""The contributor path from a pinned LAB checkout to a scored-shape run.

Before this, the two halves did not meet: nothing issued a projected layout
(GitHub #843), and the only LAB index command required the evaluator-private
``task.json`` a projection deliberately withholds (GitHub #844). These tests
walk the documented contributor commands end to end — project, index, select a
category, run it through the repository's own fixture adapter with no
credentials — so the quickstart cannot silently rot back apart.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast.cli import main
from legalforecast.multiharness import harvey_lab_projection
from legalforecast.multiharness.harvey_lab_projected_tasks import (
    HarveyLabProjectionTaskLoader,
)
from legalforecast.multiharness.harvey_lab_projection import (
    ROOT_MANIFEST_NAME,
    HarveyLabPin,
)
from pytest import CaptureFixture, MonkeyPatch

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ADAPTER_MANIFEST = (
    REPO_ROOT
    / "examples"
    / "adapters"
    / "openai-responses"
    / "fixture-adapter-manifest.json"
)
UPSTREAM_TASKS: dict[str, dict[str, object]] = {
    "immigration/draft-appeal-brief": {
        "deliverables": {"appeal-brief.docx": "appeal-brief.docx"}
    },
    "immigration/draft-response": {"deliverables": {"response.docx": "response.docx"}},
    # The shape the contract cannot carry yet, present in every real category.
    "immigration/extract-penalties": {
        "deliverables": {"a.docx": "a.docx", "b.docx": "b.docx"}
    },
    "tax/draft-opinion": {"deliverables": {"opinion.docx": "opinion.docx"}},
}


def test_contributor_walkthrough_projects_indexes_selects_and_runs(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    lab_root = _pinned_lab_checkout(tmp_path, monkeypatch)
    projected = tmp_path / "projected"
    private = tmp_path / "private"
    index_path = tmp_path / "lab-index.json"
    run_dir = tmp_path / "run"

    assert (
        main(
            [
                "multiharness",
                "tasks",
                "project",
                "--lab-root",
                str(lab_root),
                "--category",
                "immigration",
                "--output-dir",
                str(projected),
                "--evaluator-private-dir",
                str(private),
            ]
        )
        == 0
    )
    # The projected layout is solver-visible only: the gold criteria stay behind.
    assert (
        not (projected / "tasks" / "immigration" / "draft-appeal-brief")
        .joinpath("task.json")
        .exists()
    )
    assert (
        private / "tasks" / "immigration" / "draft-appeal-brief" / "task.json"
    ).is_file()

    assert (
        main(
            [
                "multiharness",
                "tasks",
                "index",
                "--suite",
                "harvey-lab",
                "--projected-root",
                str(projected),
                "--output",
                str(index_path),
            ]
        )
        == 0
    )
    index_record = _read_json(index_path)
    tasks = cast(list[dict[str, Any]], index_record["tasks"])
    assert [task["task_id"] for task in tasks] == [
        "harvey_lab:immigration/draft-appeal-brief",
        "harvey_lab:immigration/draft-response",
    ]
    assert tasks[0]["family"] == "harvey_lab"
    assert tasks[0]["scoring_mode"] == "lab_native"
    assert tasks[0]["metadata"]["module"] == "immigration"

    selection_path = tmp_path / "selection.json"
    assert (
        main(
            [
                "multiharness",
                "tasks",
                "select",
                "--index",
                str(index_path),
                "--category",
                "immigration",
                "--output",
                str(selection_path),
            ]
        )
        == 0
    )
    selection = _read_json(selection_path)
    assert cast(dict[str, Any], selection["selection_result"])["task_ids"] == [
        "harvey_lab:immigration/draft-appeal-brief",
        "harvey_lab:immigration/draft-response",
    ]

    assert (
        main(
            [
                "multiharness",
                "run",
                "--task-index",
                str(index_path),
                "--category",
                "immigration",
                "--adapter-manifest",
                str(FIXTURE_ADAPTER_MANIFEST),
                "--model-key",
                "fixture-model",
                "--output-dir",
                str(run_dir),
                "--run-id",
                "immigration-walkthrough",
            ]
        )
        == 0
    )
    results = [
        json.loads(line)
        for line in (run_dir / "lab" / "task-results.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert len(results) == 2
    assert {record["result"]["status"] for record in results} == {"succeeded"}


def test_projected_index_carries_the_manifest_hashes(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    projected = _projected_root(tmp_path, monkeypatch)
    manifest = harvey_lab_projection.verify_harvey_lab_projection(projected)

    index = HarveyLabProjectionTaskLoader(projected).load_task_index()

    by_id = {task.task_id: task for task in index.tasks}
    for record in manifest.tasks:
        task = by_id[record.task_id]
        # The index must not re-derive the digest receipts are bound to.
        assert task.task_sha256 == record.task_sha256
        assert {artifact.path for artifact in task.artifacts} == {
            f"{record.relative_path}/{item.path}" for item in record.files
        }


def test_projected_index_refuses_tampered_bytes(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    projected = _projected_root(tmp_path, monkeypatch)
    instructions = (
        projected / "tasks" / "immigration" / "draft-appeal-brief" / "instructions.txt"
    )
    instructions.chmod(0o644)
    instructions.write_text("tampered\n", encoding="utf-8")

    with pytest.raises(ValueError) as exc_info:
        HarveyLabProjectionTaskLoader(projected).load_task_index()

    assert "projected file hash mismatch" in str(exc_info.value)
    assert "immigration/draft-appeal-brief/instructions.txt" in str(exc_info.value)


def test_raw_lab_root_pointed_at_a_projection_names_the_right_flag(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    projected = _projected_root(tmp_path, monkeypatch)

    assert (
        main(
            [
                "multiharness",
                "tasks",
                "index",
                "--suite",
                "harvey-lab",
                "--lab-root",
                str(projected),
                "--output",
                str(tmp_path / "index.json"),
            ]
        )
        == 2
    )
    assert "--projected-root" in capsys.readouterr().err


def test_index_refuses_both_lab_root_and_projected_root(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    lab_root = _pinned_lab_checkout(tmp_path, monkeypatch)
    projected = tmp_path / "projected"
    assert (
        main(
            [
                "multiharness",
                "tasks",
                "project",
                "--lab-root",
                str(lab_root),
                "--category",
                "tax",
                "--output-dir",
                str(projected),
                "--evaluator-private-dir",
                str(tmp_path / "private"),
            ]
        )
        == 0
    )

    assert (
        main(
            [
                "multiharness",
                "tasks",
                "index",
                "--suite",
                "harvey-lab",
                "--lab-root",
                str(lab_root),
                "--projected-root",
                str(projected),
                "--output",
                str(tmp_path / "index.json"),
            ]
        )
        == 2
    )
    assert "not both" in capsys.readouterr().err


def test_project_reports_every_skipped_task(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    lab_root = _pinned_lab_checkout(tmp_path, monkeypatch)

    assert (
        main(
            [
                "multiharness",
                "tasks",
                "project",
                "--lab-root",
                str(lab_root),
                "--category",
                "immigration",
                "--output-dir",
                str(tmp_path / "projected"),
                "--evaluator-private-dir",
                str(tmp_path / "private"),
            ]
        )
        == 0
    )

    stderr = capsys.readouterr().err
    assert "Projected 2 of 3 matched Harvey LAB task(s)." in stderr
    assert "immigration/extract-penalties: task.json declares 2 deliverables" in stderr
    assert ROOT_MANIFEST_NAME in stderr
    # A contributor must be told the private root exists and what it means.
    assert "Do not publish them" in stderr


def test_project_can_refuse_instead_of_skipping(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    lab_root = _pinned_lab_checkout(tmp_path, monkeypatch)
    projected = tmp_path / "projected"

    assert (
        main(
            [
                "multiharness",
                "tasks",
                "project",
                "--lab-root",
                str(lab_root),
                "--category",
                "immigration",
                "--output-dir",
                str(projected),
                "--evaluator-private-dir",
                str(tmp_path / "private"),
                "--refuse-unsupported-tasks",
            ]
        )
        == 2
    )
    assert "immigration/extract-penalties" in capsys.readouterr().err
    # A failed projection must not leave a sealed partial tree behind, or the
    # obvious retry fails on "must be a fresh, absent path".
    assert not projected.exists()


def test_project_refuses_an_existing_output_dir_with_the_removal_command(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    lab_root = _pinned_lab_checkout(tmp_path, monkeypatch)
    projected = tmp_path / "projected"
    projected.mkdir()

    assert (
        main(
            [
                "multiharness",
                "tasks",
                "project",
                "--lab-root",
                str(lab_root),
                "--category",
                "tax",
                "--output-dir",
                str(projected),
                "--evaluator-private-dir",
                str(tmp_path / "private"),
            ]
        )
        == 2
    )
    assert "chmod -R u+w" in capsys.readouterr().err


def test_project_names_an_unknown_category_and_lists_the_real_ones(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    lab_root = _pinned_lab_checkout(tmp_path, monkeypatch)

    assert (
        main(
            [
                "multiharness",
                "tasks",
                "project",
                "--lab-root",
                str(lab_root),
                "--category",
                "corporate",
                "--output-dir",
                str(tmp_path / "projected"),
                "--evaluator-private-dir",
                str(tmp_path / "private"),
            ]
        )
        == 2
    )
    stderr = capsys.readouterr().err
    assert "corporate" in stderr
    assert "immigration, tax" in stderr


def test_project_dry_run_writes_nothing(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    lab_root = _pinned_lab_checkout(tmp_path, monkeypatch)
    projected = tmp_path / "projected"

    assert (
        main(
            [
                "multiharness",
                "tasks",
                "project",
                "--lab-root",
                str(lab_root),
                "--category",
                "immigration",
                "--output-dir",
                str(projected),
                "--evaluator-private-dir",
                str(tmp_path / "private"),
                "--dry-run",
            ]
        )
        == 0
    )

    assert not projected.exists()
    assert "3 Harvey LAB task(s) matched" in capsys.readouterr().err


def _projected_root(tmp_path: Path, monkeypatch: MonkeyPatch) -> Path:
    lab_root = _pinned_lab_checkout(tmp_path, monkeypatch)
    projected = tmp_path / "projected"
    assert (
        main(
            [
                "multiharness",
                "tasks",
                "project",
                "--lab-root",
                str(lab_root),
                "--category",
                "immigration",
                "--output-dir",
                str(projected),
                "--evaluator-private-dir",
                str(tmp_path / "private"),
            ]
        )
        == 0
    )
    return projected


def _pinned_lab_checkout(tmp_path: Path, monkeypatch: MonkeyPatch) -> Path:
    """A LAB checkout the CLI accepts as the official pin.

    The contributor CLI has no pin override — a projection must authenticate
    against the recorded pin — so the test moves the pin to the fixture instead
    of moving the fixture off the pin. The real git verification still runs.
    """

    lab_root = tmp_path / "lab"
    for lab_task_id, extra in UPSTREAM_TASKS.items():
        task_dir = lab_root / "tasks" / lab_task_id
        (task_dir / "documents").mkdir(parents=True)
        (task_dir / "documents" / "record.txt").write_text(
            f"{lab_task_id} record\n", encoding="utf-8"
        )
        record: dict[str, object] = {
            "title": lab_task_id,
            "instructions": f"Do {lab_task_id}.",
            "criteria": [{"id": "C-001", "match_criteria": "private rubric"}],
        }
        record.update(extra)
        (task_dir / "task.json").write_text(
            json.dumps(record, indent=2, sort_keys=True), encoding="utf-8"
        )
    _commit(lab_root)
    monkeypatch.setattr(
        harvey_lab_projection,
        "issue_196_pin",
        lambda: HarveyLabPin(
            repository="https://example.com/legalforecast-lab-fixture",
            commit=_git(lab_root, "rev-parse", "HEAD"),
            tree=_git(lab_root, "rev-parse", "HEAD^{tree}"),
        ),
    )
    return lab_root


def _commit(root: Path) -> None:
    identity = (
        "-c",
        "user.name=lab-fixture",
        "-c",
        "user.email=lab-fixture@example.com",
    )
    subprocess.run(["git", "init", "-q", str(root)], check=True, env=_git_env())
    subprocess.run(["git", "-C", str(root), "add", "."], check=True, env=_git_env())
    subprocess.run(
        ["git", "-C", str(root), *identity, "commit", "-qm", "fixture"],
        check=True,
        env=_git_env(),
    )


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        env=_git_env(),
    )
    return completed.stdout.strip()


def _git_env() -> dict[str, str]:
    return {
        **os.environ,
        "GIT_AUTHOR_NAME": "lab-fixture",
        "GIT_AUTHOR_EMAIL": "lab-fixture@example.com",
        "GIT_COMMITTER_NAME": "lab-fixture",
        "GIT_COMMITTER_EMAIL": "lab-fixture@example.com",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
    }


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)
