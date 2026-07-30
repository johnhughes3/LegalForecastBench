from __future__ import annotations

import hashlib
import json
import os
import stat
from collections.abc import Callable, Iterator
from dataclasses import replace
from pathlib import Path
from typing import cast

import legalforecast.multiharness.deliverables as deliverables_module
import pytest
from legalforecast.multiharness.deliverables import (
    DELIVERABLE_MANIFEST_SCHEMA_VERSION,
    DeliverableArtifactProjection,
    DeliverableLimits,
    DeliverableManifest,
    DeliverableValidationError,
    seal_deliverable,
    validate_sealed_deliverable,
)
from legalforecast.multiharness.material_separation import deliverable_tree_sha256

TASK_SHA256 = "sha256:" + "1" * 64
RUN_SHA256 = "sha256:" + "2" * 64
CONFIG_SHA256 = "sha256:" + "3" * 64


def _write(path: Path, payload: bytes, *, mode: int = 0o644) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    path.chmod(mode)
    return path


def _projection(source_path: str) -> DeliverableArtifactProjection:
    return DeliverableArtifactProjection(
        artifact_id="answer",
        source_path=source_path,
        path="work-product/answer.md",
        media_type="text/markdown",
        max_size_bytes=64,
    )


def _seal(
    source_root: Path,
    sealed_root: Path,
    projection: DeliverableArtifactProjection,
) -> DeliverableManifest:
    return seal_deliverable(
        source_root=source_root,
        sealed_root=sealed_root,
        task_sha256=TASK_SHA256,
        run_sha256=RUN_SHA256,
        config_sha256=CONFIG_SHA256,
        artifacts=(projection,),
    )


def test_claude_codex_and_native_layouts_normalize_to_same_contract(
    tmp_path: Path,
) -> None:
    layouts = (
        ("claude", "outputs/final.md"),
        ("codex", "workspace/submission.md"),
        ("native", "deliverable.md"),
    )
    manifests: list[DeliverableManifest] = []
    for harness, source_path in layouts:
        source_root = tmp_path / harness
        _write(source_root / source_path, b"# Canonical answer\n")
        manifest = _seal(
            source_root,
            tmp_path / f"{harness}-sealed",
            _projection(source_path),
        )
        manifests.append(manifest)
        assert (
            validate_sealed_deliverable(
                tmp_path / f"{harness}-sealed",
                manifest,
            )
            == manifest
        )
        assert manifest.tree_sha256 == (
            "sha256:"
            + deliverable_tree_sha256(tmp_path / f"{harness}-sealed").removeprefix(
                "sha256:"
            )
        )

    assert manifests[0].to_record() == manifests[1].to_record()
    assert manifests[1].to_record() == manifests[2].to_record()
    assert manifests[0].schema_version == DELIVERABLE_MANIFEST_SCHEMA_VERSION
    assert manifests[0].task_sha256 == TASK_SHA256
    assert manifests[0].run_sha256 == RUN_SHA256
    assert manifests[0].config_sha256 == CONFIG_SHA256
    assert manifests[0].artifacts[0].path == "work-product/answer.md"
    assert manifests[0].artifacts[0].media_type == "text/markdown"


def test_manifest_round_trips_and_rejects_unknown_schema_or_content() -> None:
    record = {
        "schema_version": DELIVERABLE_MANIFEST_SCHEMA_VERSION,
        "task_sha256": TASK_SHA256,
        "run_sha256": RUN_SHA256,
        "config_sha256": CONFIG_SHA256,
        "artifacts": [
            {
                "artifact_id": "answer",
                "path": "answer.txt",
                "media_type": "text/plain",
                "sha256": "sha256:" + "4" * 64,
                "size_bytes": 6,
                "max_size_bytes": 10,
            }
        ],
        "total_size_bytes": 6,
        "max_files": 1,
        "max_total_size_bytes": 10,
        "tree_sha256": "sha256:" + "5" * 64,
        "manifest_sha256": "sha256:" + "6" * 64,
    }
    # The content commitment is intentionally fabricated, so construction fails.
    with pytest.raises(ValueError, match="manifest_sha256"):
        DeliverableManifest.from_record(record)

    unknown = dict(record)
    unknown["schema_version"] = "legalforecast.multiharness.deliverable_manifest.v2"
    with pytest.raises(ValueError, match="schema_version"):
        DeliverableManifest.from_record(unknown)


@pytest.mark.parametrize(
    ("source_path", "canonical_path"),
    (
        ("../escape.txt", "answer.txt"),
        ("safe.txt", "../escape.txt"),
        ("%2e%2e/escape.txt", "answer.txt"),
        ("safe.txt", "nested%2fescape.txt"),
        ("safe.txt", "/absolute.txt"),
    ),
)
def test_projection_rejects_escaping_or_ambiguous_paths(
    source_path: str,
    canonical_path: str,
) -> None:
    with pytest.raises(ValueError, match="path"):
        DeliverableArtifactProjection(
            artifact_id="answer",
            source_path=source_path,
            path=canonical_path,
            media_type="text/plain",
            max_size_bytes=64,
        )


def test_sealing_rejects_missing_extra_and_oversized_outputs(tmp_path: Path) -> None:
    missing_root = tmp_path / "missing"
    missing_root.mkdir()
    with pytest.raises(DeliverableValidationError, match="missing"):
        _seal(missing_root, tmp_path / "missing-sealed", _projection("answer.md"))

    extra_root = tmp_path / "extra"
    _write(extra_root / "answer.md", b"answer")
    _write(extra_root / "surprise.txt", b"extra")
    with pytest.raises(DeliverableValidationError, match="unexpected"):
        _seal(extra_root, tmp_path / "extra-sealed", _projection("answer.md"))

    empty_directory_root = tmp_path / "empty-directory"
    _write(empty_directory_root / "answer.md", b"answer")
    (empty_directory_root / "surprise").mkdir()
    with pytest.raises(DeliverableValidationError, match="unexpected"):
        _seal(
            empty_directory_root,
            tmp_path / "empty-directory-sealed",
            _projection("answer.md"),
        )

    oversized_root = tmp_path / "oversized"
    _write(oversized_root / "answer.md", b"too large")
    with pytest.raises(DeliverableValidationError, match="per-file"):
        _seal(
            oversized_root,
            tmp_path / "oversized-sealed",
            replace(_projection("answer.md"), max_size_bytes=4),
        )


@pytest.mark.parametrize("unexpected_first", (False, True))
def test_unexpected_path_diagnostic_is_independent_of_enumeration_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    unexpected_first: bool,
) -> None:
    source_root = tmp_path / "source"
    _write(source_root / "answer.md", b"answer")
    _write(source_root / "surprise.txt", b"extra")
    real_scandir = deliverables_module.os.scandir

    class OrderedScandir:
        def __init__(self, directory_fd: int) -> None:
            with real_scandir(directory_fd) as entries:
                self.entries = list(entries)
            self.entries.sort(
                key=lambda entry: entry.name == "surprise.txt",
                reverse=unexpected_first,
            )

        def __iter__(self) -> Iterator[os.DirEntry[str]]:
            return iter(self.entries)

        def __enter__(self) -> OrderedScandir:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    monkeypatch.setattr(deliverables_module.os, "scandir", OrderedScandir)

    with pytest.raises(
        DeliverableValidationError,
        match=r"unexpected paths: surprise\.txt",
    ):
        _seal(
            source_root,
            tmp_path / "sealed",
            _projection("answer.md"),
        )


def test_sparse_oversize_and_excess_entries_fail_before_hashing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_hash(*args: object, **kwargs: object) -> tuple[str, int]:
        raise AssertionError("content hashing must not begin")

    monkeypatch.setattr(deliverables_module, "_hash_open_file", unexpected_hash)

    sparse_root = tmp_path / "sparse"
    sparse = _write(sparse_root / "answer.md", b"")
    with sparse.open("r+b") as handle:
        handle.truncate(1024 * 1024 * 1024)
    with pytest.raises(DeliverableValidationError, match="per-file"):
        _seal(sparse_root, tmp_path / "sparse-sealed", _projection("answer.md"))

    extra_root = tmp_path / "extra-before-hash"
    _write(extra_root / "answer.md", b"answer")
    _write(extra_root / "unexpected.txt", b"unexpected")
    with pytest.raises(DeliverableValidationError, match="unexpected"):
        _seal(
            extra_root,
            tmp_path / "extra-before-hash-sealed",
            _projection("answer.md"),
        )

    aggregate_root = tmp_path / "aggregate"
    _write(aggregate_root / "one.txt", b"1234")
    _write(aggregate_root / "two.txt", b"5678")
    with pytest.raises(DeliverableValidationError, match="total"):
        seal_deliverable(
            source_root=aggregate_root,
            sealed_root=tmp_path / "aggregate-sealed",
            task_sha256=TASK_SHA256,
            run_sha256=RUN_SHA256,
            config_sha256=CONFIG_SHA256,
            artifacts=(
                replace(
                    _projection("one.txt"),
                    artifact_id="one",
                    path="one.txt",
                ),
                replace(
                    _projection("two.txt"),
                    artifact_id="two",
                    path="two.txt",
                ),
            ),
            limits=DeliverableLimits(max_files=2, max_total_bytes=7),
        )


def test_sealing_rejects_invalid_media_duplicates_and_global_limits(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="media_type"):
        replace(_projection("answer.md"), media_type="not a media type")
    with pytest.raises(ValueError, match="unique"):
        seal_deliverable(
            source_root=tmp_path,
            sealed_root=tmp_path / "sealed",
            task_sha256=TASK_SHA256,
            run_sha256=RUN_SHA256,
            config_sha256=CONFIG_SHA256,
            artifacts=(
                _projection("one.md"),
                replace(_projection("two.md"), source_path="two.md"),
            ),
        )

    source_root = tmp_path / "bounded"
    _write(source_root / "one.txt", b"1234")
    _write(source_root / "two.txt", b"5678")
    artifacts = (
        replace(
            _projection("one.txt"),
            artifact_id="one",
            path="one.txt",
        ),
        replace(
            _projection("two.txt"),
            artifact_id="two",
            path="two.txt",
        ),
    )
    with pytest.raises(DeliverableValidationError, match="total"):
        seal_deliverable(
            source_root=source_root,
            sealed_root=tmp_path / "bounded-sealed",
            task_sha256=TASK_SHA256,
            run_sha256=RUN_SHA256,
            config_sha256=CONFIG_SHA256,
            artifacts=artifacts,
            limits=DeliverableLimits(max_files=2, max_total_bytes=7),
        )


def test_validation_rejects_mutation_missing_and_extra_paths(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    _write(source_root / "answer.md", b"answer")
    sealed_root = tmp_path / "sealed"
    manifest = _seal(source_root, sealed_root, _projection("answer.md"))

    answer = sealed_root / "work-product" / "answer.md"
    answer.chmod(0o644)
    with pytest.raises(DeliverableValidationError, match="read-only"):
        validate_sealed_deliverable(sealed_root, manifest)
    answer.chmod(0o444)

    (sealed_root / "work-product").chmod(0o755)
    answer.unlink()
    (sealed_root / "work-product").chmod(0o555)
    with pytest.raises(DeliverableValidationError, match=r"tree|missing"):
        validate_sealed_deliverable(sealed_root, manifest)

    (sealed_root / "work-product").chmod(0o755)
    _write(answer, b"answer", mode=0o444)
    (sealed_root / "work-product").chmod(0o555)
    sealed_root.chmod(0o755)
    _write(sealed_root / "extra.txt", b"extra", mode=0o444)
    sealed_root.chmod(0o555)
    with pytest.raises(DeliverableValidationError, match="unexpected"):
        validate_sealed_deliverable(sealed_root, manifest)


def test_validation_rejects_byte_and_manifest_tampering(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    _write(source_root / "answer.md", b"answer")
    sealed_root = tmp_path / "sealed"
    manifest = _seal(source_root, sealed_root, _projection("answer.md"))
    answer = sealed_root / "work-product" / "answer.md"
    answer.chmod(0o644)
    answer.write_bytes(b"tampered")
    answer.chmod(0o444)
    with pytest.raises(DeliverableValidationError, match=r"tree|hash|size"):
        validate_sealed_deliverable(sealed_root, manifest)

    with pytest.raises(ValueError, match="manifest_sha256"):
        replace(manifest, task_sha256="sha256:" + "9" * 64)


def test_validation_rejects_tree_entries_omitted_from_allowed_paths(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    _write(source_root / "answer.txt", b"answer")
    _write(source_root / "appendix.txt", b"appendix")
    sealed_root = tmp_path / "sealed"
    manifest = seal_deliverable(
        source_root=source_root,
        sealed_root=sealed_root,
        task_sha256=TASK_SHA256,
        run_sha256=RUN_SHA256,
        config_sha256=CONFIG_SHA256,
        artifacts=(
            replace(
                _projection("answer.txt"),
                path="answer.txt",
                media_type="text/plain",
            ),
            DeliverableArtifactProjection(
                artifact_id="appendix",
                source_path="appendix.txt",
                path="appendix.txt",
                media_type="text/plain",
                max_size_bytes=64,
            ),
        ),
    )
    forged_record = manifest.to_record()
    answer_artifact = next(
        artifact for artifact in manifest.artifacts if artifact.artifact_id == "answer"
    )
    forged_record["artifacts"] = [answer_artifact.to_record()]
    forged_record["total_size_bytes"] = 6
    content = dict(forged_record)
    content.pop("manifest_sha256")
    encoded = json.dumps(
        content,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    forged_record["manifest_sha256"] = "sha256:" + hashlib.sha256(encoded).hexdigest()
    forged = DeliverableManifest.from_record(forged_record)

    with pytest.raises(DeliverableValidationError, match="unexpected"):
        validate_sealed_deliverable(sealed_root, forged)


def test_validator_hashes_but_never_executes_contributor_content(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    side_effect = tmp_path / "executed"
    script = f"#!/bin/sh\ntouch {side_effect}\n".encode()
    _write(source_root / "answer.sh", script, mode=0o755)
    sealed_root = tmp_path / "sealed"
    projection = DeliverableArtifactProjection(
        artifact_id="answer",
        source_path="answer.sh",
        path="answer.sh",
        media_type="application/x-sh",
        max_size_bytes=128,
    )

    manifest = _seal(source_root, sealed_root, projection)
    validate_sealed_deliverable(sealed_root, manifest)

    assert not side_effect.exists()
    assert stat.S_IMODE((sealed_root / "answer.sh").stat().st_mode) == 0o444
    json.dumps(manifest.to_record(), sort_keys=True)


def test_digest_media_spelling_and_projection_order_normalize_identity(
    tmp_path: Path,
) -> None:
    first_source = tmp_path / "first-source"
    _write(first_source / "one.txt", b"one")
    _write(first_source / "two.txt", b"two")
    second_source = tmp_path / "second-source"
    _write(second_source / "two.txt", b"two")
    _write(second_source / "one.txt", b"one")
    projections = (
        DeliverableArtifactProjection(
            artifact_id="one",
            source_path="one.txt",
            path="canonical/one.txt",
            media_type="TEXT/PLAIN",
            max_size_bytes=16,
        ),
        DeliverableArtifactProjection(
            artifact_id="two",
            source_path="two.txt",
            path="canonical/two.txt",
            media_type="text/plain",
            max_size_bytes=16,
        ),
    )

    first = seal_deliverable(
        source_root=first_source,
        sealed_root=tmp_path / "first-sealed",
        task_sha256="1" * 64,
        run_sha256=RUN_SHA256,
        config_sha256="3" * 64,
        artifacts=projections,
    )
    second = seal_deliverable(
        source_root=second_source,
        sealed_root=tmp_path / "second-sealed",
        task_sha256=TASK_SHA256,
        run_sha256="2" * 64,
        config_sha256=CONFIG_SHA256,
        artifacts=tuple(reversed(projections)),
    )

    assert first.to_record() == second.to_record()
    assert first.task_sha256 == TASK_SHA256
    assert first.run_sha256 == RUN_SHA256
    assert first.config_sha256 == CONFIG_SHA256
    assert {artifact.media_type for artifact in first.artifacts} == {"text/plain"}
    assert first.max_files == 100


def test_validation_rejects_sparse_growth_before_hashing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_root = tmp_path / "source"
    _write(source_root / "answer.md", b"answer")
    sealed_root = tmp_path / "sealed"
    manifest = _seal(source_root, sealed_root, _projection("answer.md"))
    answer = sealed_root / "work-product" / "answer.md"
    answer.chmod(0o644)
    with answer.open("r+b") as handle:
        handle.truncate(1024 * 1024 * 1024)
    answer.chmod(0o444)

    def unexpected_hash(*args: object, **kwargs: object) -> tuple[str, int]:
        raise AssertionError("content hashing must not begin")

    monkeypatch.setattr(deliverables_module, "_hash_open_file", unexpected_hash)
    with pytest.raises(DeliverableValidationError, match="per-file"):
        validate_sealed_deliverable(sealed_root, manifest)


def test_streaming_hash_aborts_when_file_grows_past_remaining_budget(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = _write(tmp_path / "growing.bin", b"initial")
    file_fd = os.open(path, os.O_RDONLY)
    expected_stat = os.fstat(file_fd)
    real_fdopen = os.fdopen
    grew = False

    def grow_then_open(
        fd: int,
        mode: str,
    ) -> object:
        nonlocal grew
        if not grew:
            with path.open("ab") as handle:
                handle.write(b"x" * 128)
            grew = True
        return real_fdopen(fd, mode)

    monkeypatch.setattr(deliverables_module.os, "fdopen", grow_then_open)
    hash_open_file = cast(
        Callable[..., tuple[str, int]],
        deliverables_module.__dict__["_hash_open_file"],
    )
    try:
        with pytest.raises(DeliverableValidationError, match="per-file"):
            hash_open_file(
                file_fd,
                "growing.bin",
                max_bytes=64,
                remaining_total_bytes=64,
                expected_stat=expected_stat,
                field_name="deliverable",
            )
    finally:
        os.close(file_fd)
