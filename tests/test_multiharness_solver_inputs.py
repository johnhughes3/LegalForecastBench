from __future__ import annotations

import hashlib
import json
import stat
from dataclasses import replace
from pathlib import Path

import pytest
from legalforecast.multiharness.solver_inputs import (
    SOLVER_INPUT_ENTRY_PATH,
    SOLVER_INPUT_INDEX_NAME,
    SolverInputEntry,
    SolverInputError,
    SolverInputPayload,
    SolverInputStore,
    write_solver_input_store,
)
from legalforecast.multiharness.spec import CanonicalTask

SHA256 = "sha256:" + "a" * 64


def test_store_materializes_exact_private_solver_tree(tmp_path: Path) -> None:
    task = _task()
    store = _store(tmp_path, task=task)

    destination = tmp_path / "materialized"
    entry, manifest = store.materialize(task, destination_root=destination)

    assert (destination / SOLVER_INPUT_ENTRY_PATH).read_text() == "private prompt"
    assert not (destination / "source/model-packet.json").exists()
    assert not (destination / "task.json").exists()
    assert entry.tree_sha256.startswith("sha256:")
    assert manifest.task_id == task.task_id
    assert stat.S_IMODE(destination.stat().st_mode) == 0o555
    assert stat.S_IMODE((destination / "prompt.txt").stat().st_mode) == 0o444
    assert stat.S_IMODE(store.root.stat().st_mode) == 0o700
    assert stat.S_IMODE((store.root / SOLVER_INPUT_INDEX_NAME).stat().st_mode) == 0o600
    assert all(
        stat.S_IMODE((store.root / item.source_path).stat().st_mode) == 0o400
        for item in entry.files
    )
    assert all(
        stat.S_IMODE(path.stat().st_mode) == 0o700
        for path in store.root.rglob("*")
        if path.is_dir()
    )


def test_store_refuses_existing_destination_without_mutating_it(
    tmp_path: Path,
) -> None:
    task = _task()
    store = _store(tmp_path, task=task)
    index_before = (store.root / SOLVER_INPUT_INDEX_NAME).read_bytes()

    with pytest.raises(SolverInputError, match="destination must be fresh"):
        write_solver_input_store(
            destination_root=store.root,
            task_index_sha256=SHA256,
            payloads=(
                SolverInputPayload(
                    task=task,
                    prompt="private prompt",
                    source_packet={"private": "packet"},
                ),
            ),
        )

    assert (store.root / SOLVER_INPUT_INDEX_NAME).read_bytes() == index_before


def test_public_task_does_not_contain_private_solver_bytes(tmp_path: Path) -> None:
    task = _task()
    store = _store(tmp_path, task=task)

    public_record = json.dumps(task.to_record(), sort_keys=True)
    assert "private prompt" not in public_record
    assert '"private": "packet"' not in public_record
    assert "private prompt" not in json.dumps(store.index.to_record(), sort_keys=True)


def test_solver_input_entry_reads_pre_commitment_v1_records(tmp_path: Path) -> None:
    entry = _store(tmp_path, task=_task()).index.entries[0]
    legacy_record = entry.to_record()
    legacy_record.pop("task_record_sha256")

    restored = SolverInputEntry.from_record(legacy_record)

    assert restored.task_record_sha256 is None


def test_store_rejects_tampered_source_before_materialization(tmp_path: Path) -> None:
    task = _task()
    store = _store(tmp_path, task=task)
    prompt_entry = next(
        item
        for item in store.index.entries[0].files
        if item.destination_path == SOLVER_INPUT_ENTRY_PATH
    )
    prompt_file = store.root / prompt_entry.source_path
    prompt_file.chmod(0o600)
    prompt_file.write_text("tampered")

    with pytest.raises(ValueError, match=r"changed|hash|sha256|size"):
        store.materialize(task, destination_root=tmp_path / "materialized")


def test_store_rejects_task_identity_mismatch(tmp_path: Path) -> None:
    task = _task()
    store = _store(tmp_path, task=task)

    with pytest.raises(SolverInputError, match="task sha256"):
        store.entry_for(replace(task, task_sha256="sha256:" + "b" * 64))


def test_store_rejects_prompt_commitment_mismatch_at_lookup(tmp_path: Path) -> None:
    task = _task()
    store = _store(tmp_path, task=task)

    with pytest.raises(SolverInputError, match="prompt sha256"):
        store.entry_for(
            replace(
                task,
                metadata={
                    **task.metadata,
                    "prompt_sha256": "sha256:" + "b" * 64,
                },
            )
        )


def test_store_rejects_tampered_index(tmp_path: Path) -> None:
    store = _store(tmp_path, task=_task())
    index_path = store.root / SOLVER_INPUT_INDEX_NAME
    record = json.loads(index_path.read_text())
    record["task_index_sha256"] = "sha256:" + "b" * 64
    index_path.write_text(json.dumps(record))

    with pytest.raises(SolverInputError, match="index sha256"):
        SolverInputStore.load(store.root)


def test_store_load_rejects_non_private_or_symlinked_root(tmp_path: Path) -> None:
    store = _store(tmp_path, task=_task())
    store.root.chmod(0o755)
    with pytest.raises(SolverInputError, match="permissions"):
        SolverInputStore.load(store.root)

    store.root.chmod(0o700)
    link = tmp_path / "store-link"
    link.symlink_to(store.root, target_is_directory=True)
    with pytest.raises(SolverInputError, match="unsafe"):
        SolverInputStore.load(link)


def test_store_rejects_prompt_or_packet_not_bound_to_task(tmp_path: Path) -> None:
    task = _task()
    with pytest.raises(SolverInputError, match="prompt sha256"):
        write_solver_input_store(
            destination_root=tmp_path / "wrong-prompt",
            task_index_sha256=SHA256,
            payloads=(
                SolverInputPayload(
                    task=task,
                    prompt="wrong prompt",
                    source_packet={"private": "packet"},
                ),
            ),
        )
    with pytest.raises(SolverInputError, match="source packet sha256"):
        write_solver_input_store(
            destination_root=tmp_path / "wrong-packet",
            task_index_sha256=SHA256,
            payloads=(
                SolverInputPayload(
                    task=task,
                    prompt="private prompt",
                    source_packet={"private": "wrong packet"},
                ),
            ),
        )


def test_store_preserves_exact_packet_bytes_and_rejects_later_tampering(
    tmp_path: Path,
) -> None:
    packet_bytes = b'{"private":"packet"}\n'
    task = replace(
        _task(),
        task_sha256="sha256:" + hashlib.sha256(packet_bytes).hexdigest(),
    )
    store = write_solver_input_store(
        destination_root=tmp_path / "exact-store",
        task_index_sha256=SHA256,
        payloads=(
            SolverInputPayload(
                task=task,
                prompt="private prompt",
                source_packet_bytes=packet_bytes,
            ),
        ),
    )
    packet_entry = next(
        item
        for item in store.index.entries[0].files
        if item.destination_path == "source/model-packet.json"
    )
    packet_path = store.root / packet_entry.source_path
    assert packet_path.read_bytes() == packet_bytes

    packet_path.chmod(0o600)
    packet_path.write_bytes(b'{"private":"changed"}\n')
    packet_path.chmod(0o400)
    with pytest.raises(SolverInputError, match=r"size|sha256"):
        store.entry_for(task)


def _store(tmp_path: Path, *, task: CanonicalTask) -> SolverInputStore:
    return write_solver_input_store(
        destination_root=tmp_path / "solver-inputs",
        task_index_sha256=SHA256,
        payloads=(
            SolverInputPayload(
                task=task,
                prompt="private prompt",
                source_packet={"private": "packet"},
            ),
        ),
    )


def _task() -> CanonicalTask:
    packet_bytes = json.dumps(
        {"private": "packet"}, sort_keys=True, separators=(",", ":")
    ).encode()
    return CanonicalTask(
        task_id="lfb:fixture:full_packet",
        family="legalforecast_mtd",
        scoring_mode="lfb_brier",
        suite_version="fixture-suite",
        source_id="fixture",
        task_sha256="sha256:" + hashlib.sha256(packet_bytes).hexdigest(),
        metadata={"prompt_sha256": hashlib.sha256(b"private prompt").hexdigest()},
    )
