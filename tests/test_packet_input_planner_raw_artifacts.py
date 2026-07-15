from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from legalforecast.ingestion.packet_input_planner import (
    PacketInputPlanningError,
    bind_verified_raw_artifacts,
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


def test_bind_verified_raw_artifacts_normalizes_exact_courtlistener_docket_id(
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

    bindings = bind_verified_raw_artifacts(
        ("70649963",),
        artifacts=artifacts,
    )

    binding = bindings["70649963"]
    assert binding.manifest_candidate_id == "courtlistener-docket-70649963"
    assert binding.selection_candidate_id == "70649963"
    assert binding.binding_kind == "courtlistener_docket_numeric_alias"
    assert binding.to_provenance_record() == {
        "selection_candidate_id": "70649963",
        "manifest_candidate_id": "courtlistener-docket-70649963",
        "binding_kind": "courtlistener_docket_numeric_alias",
        "manifest_path": str(raw_path),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "byte_count": len(payload),
    }


@pytest.mark.parametrize(
    "candidate_id",
    (
        "courtlistener-docket-not-numeric",
        "courtlistener-docket-70649963-extra",
        "courtlistener-docket-",
    ),
)
def test_load_verified_raw_artifacts_rejects_nonnumeric_reserved_aliases(
    tmp_path: Path,
    candidate_id: str,
) -> None:
    raw_html_root = tmp_path / "raw-html"
    raw_html_root.mkdir()
    payload = b"<html>canonical docket</html>"
    raw_path = raw_html_root / "70649963.html"
    raw_path.write_bytes(payload)

    with pytest.raises(PacketInputPlanningError, match="nonnumeric CourtListener"):
        load_verified_raw_artifacts(
            [_record(candidate_id, raw_path, payload)],
            raw_html_dir=raw_html_root,
        )


def test_load_verified_raw_artifacts_rejects_cross_candidate_path_substitution(
    tmp_path: Path,
) -> None:
    raw_html_root = tmp_path / "raw-html"
    raw_html_root.mkdir()
    payload = b"<html>different docket</html>"
    substituted_path = raw_html_root / "99999999.html"
    substituted_path.write_bytes(payload)

    with pytest.raises(PacketInputPlanningError, match="path ownership mismatch"):
        load_verified_raw_artifacts(
            [
                _record(
                    "courtlistener-docket-70649963",
                    substituted_path,
                    payload,
                )
            ],
            raw_html_dir=raw_html_root,
        )


def test_bind_verified_raw_artifacts_rejects_alias_collision(
    tmp_path: Path,
) -> None:
    raw_html_root = tmp_path / "raw-html"
    raw_html_root.mkdir()
    first_payload = b"<html>first</html>"
    second_payload = b"<html>second</html>"
    first = raw_html_root / "first.html"
    second = raw_html_root / "70649963.html"
    first.write_bytes(first_payload)
    second.write_bytes(second_payload)
    artifacts = load_verified_raw_artifacts(
        [
            _record("70649963", first, first_payload),
            _record("courtlistener-docket-70649963", second, second_payload),
        ],
        raw_html_dir=raw_html_root,
    )

    with pytest.raises(PacketInputPlanningError, match="alias collision"):
        bind_verified_raw_artifacts(("70649963",), artifacts=artifacts)


def test_bind_verified_raw_artifacts_rejects_multiple_candidate_owners(
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

    with pytest.raises(PacketInputPlanningError, match="multiple candidate owners"):
        bind_verified_raw_artifacts(
            ("70649963", "courtlistener-docket-70649963"),
            artifacts=artifacts,
        )


def test_bind_verified_raw_artifacts_rejects_missing_candidate_ownership(
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

    with pytest.raises(PacketInputPlanningError, match="missing candidate binding"):
        bind_verified_raw_artifacts(("99999999",), artifacts=artifacts)


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
