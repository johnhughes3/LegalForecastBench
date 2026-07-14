from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from legalforecast.ingestion.packet_input_planner import (
    PacketInputPlanningError,
    load_verified_raw_artifacts,
)


def _record(candidate_id: str, path: Path, payload: bytes) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "path": str(path),
        "byte_count": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def test_load_verified_raw_artifacts_binds_namespaced_id_to_bare_filename(
    tmp_path: Path,
) -> None:
    raw_html_root = tmp_path / "raw-html"
    raw_html_root.mkdir()
    payload = b"<html>canonical docket</html>"
    raw_path = raw_html_root / "70649963.html"
    raw_path.write_bytes(payload)

    artifacts = load_verified_raw_artifacts(
        [_record("courtlistener-docket-70649963", raw_path, payload)],
        raw_html_dir=raw_html_root,
    )

    artifact = artifacts["courtlistener-docket-70649963"]
    assert artifact.path == raw_path
    assert artifact.text == payload.decode()


@pytest.mark.parametrize("failure", ["traversal", "hash", "byte_count"])
def test_load_verified_raw_artifacts_rejects_tampered_or_escaping_rows(
    tmp_path: Path,
    failure: str,
) -> None:
    raw_html_root = tmp_path / "raw-html"
    raw_html_root.mkdir()
    payload = b"<html>canonical docket</html>"
    raw_path = raw_html_root / "70649963.html"
    raw_path.write_bytes(payload)
    record = _record("courtlistener-docket-70649963", raw_path, payload)
    if failure == "traversal":
        outside = tmp_path / "outside.html"
        outside.write_bytes(payload)
        record["path"] = str(raw_html_root / ".." / outside.name)
    elif failure == "hash":
        record["sha256"] = "0" * 64
    else:
        record["byte_count"] = len(payload) + 1

    with pytest.raises(PacketInputPlanningError):
        load_verified_raw_artifacts([record], raw_html_dir=raw_html_root)


def test_load_verified_raw_artifacts_rejects_symlink(tmp_path: Path) -> None:
    raw_html_root = tmp_path / "raw-html"
    raw_html_root.mkdir()
    payload = b"<html>canonical docket</html>"
    target = raw_html_root / "target.html"
    target.write_bytes(payload)
    symlink = raw_html_root / "70649963.html"
    symlink.symlink_to(target)

    with pytest.raises(PacketInputPlanningError, match="symlink"):
        load_verified_raw_artifacts(
            [_record("courtlistener-docket-70649963", symlink, payload)],
            raw_html_dir=raw_html_root,
        )


@pytest.mark.parametrize("duplicate_key", ["candidate", "path"])
def test_load_verified_raw_artifacts_rejects_duplicate_bindings(
    tmp_path: Path,
    duplicate_key: str,
) -> None:
    raw_html_root = tmp_path / "raw-html"
    raw_html_root.mkdir()
    first_payload = b"<html>first</html>"
    second_payload = b"<html>second</html>"
    first = raw_html_root / "1.html"
    second = raw_html_root / "2.html"
    first.write_bytes(first_payload)
    second.write_bytes(second_payload)
    records = [
        _record("courtlistener-docket-1", first, first_payload),
        _record("courtlistener-docket-2", second, second_payload),
    ]
    if duplicate_key == "candidate":
        records[1]["candidate_id"] = records[0]["candidate_id"]
    else:
        records[1] = _record("courtlistener-docket-2", first, first_payload)

    with pytest.raises(PacketInputPlanningError, match="duplicate"):
        load_verified_raw_artifacts(records, raw_html_dir=raw_html_root)
