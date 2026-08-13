from __future__ import annotations

import errno
import json
import weakref
from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest
from legalforecast.ingestion import packet_artifact_serialization
from legalforecast.ingestion.packet_artifact_serialization import (
    PacketArtifactPaths,
    PacketArtifactRecords,
    write_packet_artifacts_incrementally,
)


def test_incremental_packet_artifacts_match_canonical_jsonl_bytes(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    rows = (
        {
            "packet": {"case_id": "case-2", "documents": [{"text": "two"}]},
            "case_packet": {"case_id": "case-2", "audit_only": True},
            "audit": {"case_packet": {"case_id": "case-2"}, "notes": ["two"]},
        },
        {
            "packet": {"case_id": "case-1", "documents": [{"text": "one"}]},
            "case_packet": {"case_id": "case-1", "audit_only": False},
            "audit": {"case_packet": {"case_id": "case-1"}, "notes": ["one"]},
        },
    )

    write_packet_artifacts_incrementally(
        paths=paths,
        source_records=rows,
        build_artifacts=lambda row: PacketArtifactRecords(**row),
    )

    assert paths.packets.read_bytes() == _canonical_jsonl(row["packet"] for row in rows)
    assert paths.case_packets.read_bytes() == _canonical_jsonl(
        row["case_packet"] for row in rows
    )
    assert paths.audit.read_bytes() == _canonical_jsonl(row["audit"] for row in rows)


def test_incremental_packet_artifacts_leave_prior_outputs_unchanged_on_failure(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    original = (b"old packets\n", b"old case packets\n", b"old audit\n")
    for path, payload in zip(
        (paths.packets, paths.case_packets, paths.audit), original, strict=True
    ):
        path.write_bytes(payload)

    def build_artifacts(row: int) -> PacketArtifactRecords:
        if row == 2:
            raise RuntimeError("mid-stream failure")
        return PacketArtifactRecords(
            packet={"row": row}, case_packet={"row": row}, audit={"row": row}
        )

    with pytest.raises(RuntimeError, match="mid-stream failure"):
        write_packet_artifacts_incrementally(
            paths=paths,
            source_records=(1, 2),
            build_artifacts=build_artifacts,
        )

    assert (
        tuple(
            path.read_bytes()
            for path in (paths.packets, paths.case_packets, paths.audit)
        )
        == original
    )
    assert not list(tmp_path.glob(".*.tmp"))


def test_incremental_packet_artifacts_restore_all_prior_outputs_when_publish_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _paths(tmp_path)
    original = (b"old packets\n", b"old case packets\n", b"old audit\n")
    destinations = (paths.packets, paths.case_packets, paths.audit)
    for path, payload in zip(destinations, original, strict=True):
        path.write_bytes(payload)

    real_replace = packet_artifact_serialization.os.replace
    publication_replacements = 0

    def fail_second_publication(source: str | Path, destination: str | Path) -> None:
        nonlocal publication_replacements
        if Path(source).suffix == ".tmp":
            publication_replacements += 1
            if publication_replacements == 2:
                raise OSError("simulated second publication failure")
        real_replace(source, destination)

    monkeypatch.setattr(
        packet_artifact_serialization.os, "replace", fail_second_publication
    )

    with pytest.raises(OSError, match="simulated second publication failure"):
        write_packet_artifacts_incrementally(
            paths=paths,
            source_records=(1,),
            build_artifacts=lambda row: PacketArtifactRecords(
                packet={"row": row}, case_packet={"row": row}, audit={"row": row}
            ),
        )

    assert tuple(path.read_bytes() for path in destinations) == original
    assert not list(tmp_path.glob(".*.tmp"))
    assert not list(tmp_path.glob(".*.backup"))


def test_incremental_packet_artifacts_preserve_backup_when_rollback_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _paths(tmp_path)
    destinations = (paths.packets, paths.case_packets, paths.audit)
    for path in destinations:
        path.write_bytes(f"old {path.name}\n".encode())

    real_replace = packet_artifact_serialization.os.replace
    publication_replacements = 0

    def fail_publication_and_one_restore(
        source: str | Path, destination: str | Path
    ) -> None:
        nonlocal publication_replacements
        source_path = Path(source)
        if source_path.suffix == ".tmp":
            publication_replacements += 1
            if publication_replacements == 2:
                raise OSError("simulated publication failure")
        if source_path.suffix == ".backup" and Path(destination) == paths.packets:
            raise OSError("simulated rollback failure")
        real_replace(source, destination)

    monkeypatch.setattr(
        packet_artifact_serialization.os, "replace", fail_publication_and_one_restore
    )

    with pytest.raises(OSError, match="rollback also failed"):
        write_packet_artifacts_incrementally(
            paths=paths,
            source_records=(1,),
            build_artifacts=lambda row: PacketArtifactRecords(
                packet={"row": row}, case_packet={"row": row}, audit={"row": row}
            ),
        )

    backups = list(tmp_path.glob(".*.backup"))
    assert len(backups) == 1
    assert backups[0].read_bytes() == b"old packets.jsonl\n"


@pytest.mark.parametrize(
    "unsupported_errno",
    (
        errno.ENOTSUP,
        errno.EXDEV,
        errno.EPERM,
        errno.EMLINK,
    ),
)
def test_incremental_packet_artifacts_copy_when_hardlinks_unsupported(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    unsupported_errno: int,
) -> None:
    paths = _paths(tmp_path)
    original = (b"old packets\n", b"old case packets\n", b"old audit\n")
    destinations = (paths.packets, paths.case_packets, paths.audit)
    for path, payload in zip(destinations, original, strict=True):
        path.write_bytes(payload)

    def reject_hardlinks(source: str | Path, destination: str | Path) -> None:
        del source, destination
        raise OSError(unsupported_errno, "hardlinks unsupported")

    monkeypatch.setattr(packet_artifact_serialization.os, "link", reject_hardlinks)

    write_packet_artifacts_incrementally(
        paths=paths,
        source_records=(1,),
        build_artifacts=lambda row: PacketArtifactRecords(
            packet={"row": row}, case_packet={"row": row}, audit={"row": row}
        ),
    )

    expected = _canonical_jsonl(({"row": 1},))
    assert tuple(path.read_bytes() for path in destinations) == (
        expected,
        expected,
        expected,
    )
    assert not list(tmp_path.glob(".*.tmp"))
    assert not list(tmp_path.glob(".*.backup"))


def test_incremental_packet_artifacts_restore_copied_snapshots_when_publish_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _paths(tmp_path)
    original = (b"old packets\n", b"old case packets\n", b"old audit\n")
    destinations = (paths.packets, paths.case_packets, paths.audit)
    for path, payload in zip(destinations, original, strict=True):
        path.write_bytes(payload)
        path.chmod(0o600)

    def reject_hardlinks(source: str | Path, destination: str | Path) -> None:
        del source, destination
        raise OSError(errno.ENOTSUP, "hardlinks unsupported")

    real_replace = packet_artifact_serialization.os.replace
    publication_replacements = 0

    def fail_second_publication(source: str | Path, destination: str | Path) -> None:
        nonlocal publication_replacements
        if Path(source).suffix == ".tmp":
            publication_replacements += 1
            if publication_replacements == 2:
                raise OSError("simulated second publication failure")
        real_replace(source, destination)

    monkeypatch.setattr(packet_artifact_serialization.os, "link", reject_hardlinks)
    monkeypatch.setattr(
        packet_artifact_serialization.os, "replace", fail_second_publication
    )

    with pytest.raises(OSError, match="simulated second publication failure"):
        write_packet_artifacts_incrementally(
            paths=paths,
            source_records=(1,),
            build_artifacts=lambda row: PacketArtifactRecords(
                packet={"row": row}, case_packet={"row": row}, audit={"row": row}
            ),
        )

    assert tuple(path.read_bytes() for path in destinations) == original
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in destinations)
    assert not list(tmp_path.glob(".*.tmp"))
    assert not list(tmp_path.glob(".*.backup"))


def test_incremental_packet_artifacts_leave_prior_outputs_when_snapshot_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _paths(tmp_path)
    original = (b"old packets\n", b"old case packets\n", b"old audit\n")
    destinations = (paths.packets, paths.case_packets, paths.audit)
    for path, payload in zip(destinations, original, strict=True):
        path.write_bytes(payload)

    def fail_hardlinks(source: str | Path, destination: str | Path) -> None:
        del source, destination
        raise OSError(errno.EIO, "simulated snapshot I/O error")

    monkeypatch.setattr(packet_artifact_serialization.os, "link", fail_hardlinks)

    with pytest.raises(OSError, match="simulated snapshot I/O error"):
        write_packet_artifacts_incrementally(
            paths=paths,
            source_records=(1,),
            build_artifacts=lambda row: PacketArtifactRecords(
                packet={"row": row}, case_packet={"row": row}, audit={"row": row}
            ),
        )

    assert tuple(path.read_bytes() for path in destinations) == original
    assert not list(tmp_path.glob(".*.tmp"))
    assert not list(tmp_path.glob(".*.backup"))


def test_incremental_packet_artifacts_retain_only_the_current_case(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    observed: list[weakref.ReferenceType[_TrackedPayload]] = []

    def build_artifacts(row: int) -> PacketArtifactRecords:
        payload = _TrackedPayload({"row": row, "payload": "x" * 4096})
        observed.append(weakref.ref(payload))
        return PacketArtifactRecords(
            packet=payload,
            case_packet=payload,
            audit=payload,
        )

    def source_records() -> Iterator[int]:
        for row in range(32):
            # An aggregating implementation retains prior payloads while it
            # consumes the source. Incremental serialization releases them
            # before requesting the next row.
            assert all(reference() is None for reference in observed)
            yield row

    write_packet_artifacts_incrementally(
        paths=paths,
        source_records=source_records(),
        build_artifacts=build_artifacts,
    )

    # This deterministic retention proxy catches a return to an aggregate
    # ``tuple(build(...))`` implementation without imposing timing thresholds.
    assert all(reference() is None for reference in observed)


class _TrackedPayload(Mapping[str, Any]):
    """Weak-referenceable serialized payload used to observe retention."""

    def __init__(self, data: Mapping[str, Any]) -> None:
        self._data = dict(data)

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)


def _paths(tmp_path: Path) -> PacketArtifactPaths:
    return PacketArtifactPaths(
        packets=tmp_path / "packets.jsonl",
        case_packets=tmp_path / "case-packets.jsonl",
        audit=tmp_path / "packet-audit.jsonl",
    )


def _canonical_jsonl(records: Iterable[Mapping[str, Any]]) -> bytes:
    return b"".join(
        (json.dumps(record, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
        for record in records
    )
