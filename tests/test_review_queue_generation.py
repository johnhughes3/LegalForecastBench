"""Generation-safe review-queue publication stays consistent without the CLI facade."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from legalforecast.unitization import review_queue_generation as generation_module
from legalforecast.unitization.review_queue import (
    ReviewQueueError,
    review_queue_v2_records,
    review_queue_v2_sidecar_path,
    verify_review_queue_v2_coverage,
)
from legalforecast.unitization.review_queue_generation import (
    ReviewQueueGenerationCommitError,
    read_review_queue_generation,
    review_queue_generation_manifest_path,
)

JsonRecord = dict[str, Any]
V1 = "legalforecast.unitization_review_queue.v1"


def _construction_row(unit_id: str, *, reason: str = "low_confidence") -> JsonRecord:
    return {
        "schema_version": V1,
        "status": "pending_adjudication",
        "candidate_id": "cand-1",
        "case_id": "case-1",
        "unit_id": unit_id,
        "review_id": f"cand-1:{unit_id}:stage-a-review",
        "route_reason": reason,
        "review_item": {
            "unit_id": unit_id,
            "reason": reason,
            "notes": "Stage A unit requires blinded pre-decision review.",
        },
    }


def _jsonl_bytes(records: tuple[JsonRecord, ...]) -> bytes:
    return "".join(
        f"{json.dumps(dict(record), sort_keys=True, allow_nan=False)}\n"
        for record in records
    ).encode()


def _publish_generation(queue_path: Path, records: tuple[JsonRecord, ...]) -> None:
    """Publish a digest-bound pair without going through the CLI facade."""

    queue_v2 = review_queue_v2_records(records)
    verify_review_queue_v2_coverage(records, queue_v2)
    v1_bytes = _jsonl_bytes(records)
    v2_bytes = _jsonl_bytes(queue_v2)
    queue_path.write_bytes(v1_bytes)
    review_queue_v2_sidecar_path(queue_path).write_bytes(v2_bytes)
    generation_module.publish_review_queue_generation(
        queue_path, v1_bytes=v1_bytes, v2_bytes=v2_bytes
    )


def test_generation_publish_failure_rolls_back_the_entire_queue_pair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed generation commit cannot leave canonical files ahead of its manifest."""

    queue_path = tmp_path / "unitization-review-queue-reviewed.jsonl"
    sidecar_path = review_queue_v2_sidecar_path(queue_path)
    prior = {queue_path: b"prior-v1\\n", sidecar_path: b"prior-v2\\n"}
    queue_path.write_bytes(b"new-v1\\n")
    sidecar_path.write_bytes(b"new-v2\\n")

    def fail_member(_path: Path, _payload: bytes) -> None:
        raise OSError("generation storage unavailable")

    monkeypatch.setattr(generation_module, "_write_immutable_member", fail_member)

    with pytest.raises(OSError, match="generation storage unavailable"):
        generation_module.publish_review_queue_generation(
            queue_path,
            v1_bytes=b"new-v1\\n",
            v2_bytes=b"new-v2\\n",
            restore_canonical=prior,
        )

    assert queue_path.read_bytes() == b"prior-v1\\n"
    assert sidecar_path.read_bytes() == b"prior-v2\\n"


def test_manifest_post_commit_fsync_failure_keeps_the_new_canonical_pair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A post-rename durability error cannot roll canonical files backward."""

    queue_path = tmp_path / "unitization-review-queue-reviewed.jsonl"
    sidecar_path = review_queue_v2_sidecar_path(queue_path)
    prior = {queue_path: b"prior-v1\\n", sidecar_path: b"prior-v2\\n"}
    v1_bytes = b"new-v1\\n"
    v2_bytes = b"new-v2\\n"
    queue_path.write_bytes(v1_bytes)
    sidecar_path.write_bytes(v2_bytes)
    original_fsync = generation_module._fsync_directory
    queue_directory_fsyncs = 0

    def fail_final_manifest_fsync(path: Path) -> None:
        nonlocal queue_directory_fsyncs
        if path == queue_path.parent:
            queue_directory_fsyncs += 1
            if queue_directory_fsyncs == 2:
                raise OSError("manifest directory unavailable")
        original_fsync(path)

    monkeypatch.setattr(
        generation_module, "_fsync_directory", fail_final_manifest_fsync
    )

    with pytest.raises(ReviewQueueGenerationCommitError):
        generation_module.publish_review_queue_generation(
            queue_path,
            v1_bytes=v1_bytes,
            v2_bytes=v2_bytes,
            restore_canonical=prior,
        )

    generation = read_review_queue_generation(queue_path)
    assert queue_path.read_bytes() == v1_bytes
    assert sidecar_path.read_bytes() == v2_bytes
    assert generation.v1_bytes == v1_bytes
    assert generation.v2_bytes == v2_bytes


def test_generation_publisher_rejects_an_existing_member_symlink(
    tmp_path: Path,
) -> None:
    """Publishing cannot bless a symlink that its own reader rejects."""

    queue_path = tmp_path / "unitization-review-queue-reviewed.jsonl"
    _publish_generation(queue_path, (_construction_row("unit-1"),))
    generation = read_review_queue_generation(queue_path)
    outside = tmp_path / "outside-v1.jsonl"
    outside.write_bytes(generation.v1_bytes)
    generation.v1_path.unlink()
    generation.v1_path.symlink_to(outside)

    with pytest.raises(ReviewQueueError, match="member is a symlink"):
        generation_module.publish_review_queue_generation(
            queue_path,
            v1_bytes=generation.v1_bytes,
            v2_bytes=generation.v2_bytes,
        )


def test_generation_publisher_and_reader_reject_member_hard_links(
    tmp_path: Path,
) -> None:
    """Immutable generation members must be regular files with one link."""

    queue_path = tmp_path / "unitization-review-queue-reviewed.jsonl"
    _publish_generation(queue_path, (_construction_row("unit-1"),))
    generation = read_review_queue_generation(queue_path)
    outside = tmp_path / "outside-v1.jsonl"
    outside.hardlink_to(generation.v1_path)

    with pytest.raises(ReviewQueueError, match="one link"):
        generation_module.publish_review_queue_generation(
            queue_path,
            v1_bytes=generation.v1_bytes,
            v2_bytes=generation.v2_bytes,
        )
    with pytest.raises(ReviewQueueError, match="one link"):
        read_review_queue_generation(queue_path)


def test_generation_reader_rejects_an_ancestor_symlink_swap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A queue-directory swap cannot redirect an already-validated member path."""

    queue_directory = tmp_path / "queue"
    queue_directory.mkdir()
    queue_path = queue_directory / "unitization-review-queue-reviewed.jsonl"
    _publish_generation(queue_path, (_construction_row("unit-1"),))
    external = tmp_path / "external"
    shutil.copytree(queue_directory, external)
    real_queue_directory = tmp_path / "queue-real"

    original_resolve = generation_module._resolve_member_path
    swapped = False

    def swap_after_resolve(
        relative: str, *, manifest_path: Path, generation_id: str
    ) -> Path:
        nonlocal swapped
        resolved = original_resolve(
            relative, manifest_path=manifest_path, generation_id=generation_id
        )
        if not swapped:
            swapped = True
            queue_directory.rename(real_queue_directory)
            queue_directory.symlink_to(external, target_is_directory=True)
        return resolved

    monkeypatch.setattr(generation_module, "_resolve_member_path", swap_after_resolve)

    with pytest.raises(ReviewQueueError, match="unreadable"):
        read_review_queue_generation(queue_path)


def test_generation_reader_rejects_a_member_from_a_different_generation(
    tmp_path: Path,
) -> None:
    """A valid digest in a sibling generation cannot be relabeled as current."""

    queue_path = tmp_path / "unitization-review-queue-reviewed.jsonl"
    _publish_generation(queue_path, (_construction_row("unit-1"),))
    first = read_review_queue_generation(queue_path)
    _publish_generation(
        queue_path, (_construction_row("unit-1"), _construction_row("unit-2"))
    )
    manifest_path = review_queue_generation_manifest_path(queue_path)
    manifest = json.loads(manifest_path.read_bytes())
    manifest["members"]["v2"]["path"] = first.v2_path.relative_to(
        manifest_path.parent
    ).as_posix()
    manifest_path.write_bytes(json.dumps(manifest, sort_keys=True).encode())

    with pytest.raises(ReviewQueueError, match="immutable generation"):
        read_review_queue_generation(queue_path)
