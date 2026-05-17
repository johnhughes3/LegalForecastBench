from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from legalforecast.publication.alpha_release_bundle import (
    ALPHA_RELEASE_BUNDLE_SCHEMA_VERSION,
    ALPHA_RELEASE_CHANNEL,
    ALPHA_RESULT_TIER,
    AlphaReleaseBundleConfig,
    AlphaReleaseBundleError,
    build_alpha_release_bundle,
)


def test_alpha_release_bundle_copies_and_hashes_fixture_and_dist_artifacts(
    tmp_path: Path,
) -> None:
    repo_root = _repo_root(tmp_path)
    fixture_dir = _fixture_output_dir(tmp_path)
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    (dist_dir / "legalforecast_mtd-0.1.0a1-py3-none-any.whl").write_bytes(
        b"wheel fixture"
    )
    (dist_dir / "legalforecast_mtd-0.1.0a1.tar.gz").write_bytes(b"sdist fixture")
    output_dir = tmp_path / "bundle"

    manifest = build_alpha_release_bundle(
        AlphaReleaseBundleConfig(
            fixture_output_dir=fixture_dir,
            output_dir=output_dir,
            dist_dir=dist_dir,
            release_commit="abcdef1234567890",
            package_version="0.1.0a1",
            release_tag="v0.1.0-alpha.1",
            repo_root=repo_root,
            generated_at=datetime(2026, 5, 17, 15, 30, tzinfo=UTC),
        )
    )

    written_manifest = json.loads(
        (output_dir / "alpha-release-manifest.json").read_text(encoding="utf-8")
    )
    assert written_manifest == manifest
    assert manifest["schema_version"] == ALPHA_RELEASE_BUNDLE_SCHEMA_VERSION
    assert manifest["release_channel"] == ALPHA_RELEASE_CHANNEL
    assert manifest["release_tag"] == "v0.1.0-alpha.1"
    assert manifest["package_version"] == "0.1.0a1"
    assert manifest["release_commit"] == "abcdef1234567890"
    assert manifest["generated_at"] == "2026-05-17T15:30:00Z"
    assert manifest["result_tier"] == ALPHA_RESULT_TIER
    assert manifest["canonical_leaderboard"] is False
    assert manifest["paid_source_material_included"] is False

    artifact_records = _artifact_records(manifest)
    assert manifest["artifact_count"] == len(artifact_records)
    assert {
        "fixture-e2e/report/leaderboard.json",
        "fixture-e2e/report/leaderboard.md",
        "fixture-e2e/manifests/cycle_fixture_e2e.freeze.json",
        "fixture-e2e/protocols/cycle_fixture_e2e.preregistration.yaml",
        "release-metadata/README.md",
        "release-metadata/docs/README.md",
        "release-metadata/docs/acquisition.md",
        "release-metadata/docs/methodology.md",
        "release-metadata/docs/run_card_template.md",
        "release-metadata/docs/run_card_schema.json",
        "release-metadata/docs/result_tiers.md",
        "dist/legalforecast_mtd-0.1.0a1-py3-none-any.whl",
        "dist/legalforecast_mtd-0.1.0a1.tar.gz",
    } <= {str(record["path"]) for record in artifact_records}
    assert {str(record["source_class"]) for record in artifact_records} == {
        "package_build",
        "release_metadata",
        "synthetic_fixture",
    }
    assert {
        "fixture_report",
        "freeze_bundle",
        "package_build",
        "protocol_example",
        "run_card_example",
        "run_card_schema",
    } <= {str(record["bundle_role"]) for record in artifact_records}

    for record in artifact_records:
        relative_path = Path(str(record["path"]))
        assert not relative_path.is_absolute()
        assert ".." not in relative_path.parts
        artifact_path = output_dir / relative_path
        assert artifact_path.is_file()
        assert record["sha256"] == _sha256_file(artifact_path)
        assert record["size_bytes"] == artifact_path.stat().st_size


def test_alpha_release_bundle_rejects_unsafe_fixture_manifest_paths(
    tmp_path: Path,
) -> None:
    repo_root = _repo_root(tmp_path)
    fixture_dir = _fixture_output_dir(tmp_path)
    manifest_path = fixture_dir / "artifact-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifacts"].append("../leak.txt")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(AlphaReleaseBundleError, match="unsafe bundle path"):
        build_alpha_release_bundle(
            AlphaReleaseBundleConfig(
                fixture_output_dir=fixture_dir,
                output_dir=tmp_path / "bundle",
                release_commit="abcdef1",
                package_version="0.1.0a1",
                release_tag="v0.1.0-alpha.1",
                repo_root=repo_root,
            )
        )


def test_alpha_release_bundle_requires_fixture_release_artifacts(
    tmp_path: Path,
) -> None:
    repo_root = _repo_root(tmp_path)
    fixture_dir = _fixture_output_dir(tmp_path)
    manifest_path = fixture_dir / "artifact-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifacts"].remove("report/leaderboard.md")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(AlphaReleaseBundleError, match="missing required artifacts"):
        build_alpha_release_bundle(
            AlphaReleaseBundleConfig(
                fixture_output_dir=fixture_dir,
                output_dir=tmp_path / "bundle",
                release_commit="abcdef1",
                package_version="0.1.0a1",
                release_tag="v0.1.0-alpha.1",
                repo_root=repo_root,
            )
        )


def _repo_root(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    docs_dir = repo_root / "docs"
    docs_dir.mkdir(parents=True)
    (repo_root / "README.md").write_text("README fixture\n", encoding="utf-8")
    for name in ("README.md", "acquisition.md", "methodology.md"):
        (docs_dir / name).write_text(f"{name} fixture\n", encoding="utf-8")
    for name in ("run_card_template.md", "run_card_schema.json", "result_tiers.md"):
        (docs_dir / name).write_text(f"{name} fixture\n", encoding="utf-8")
    return repo_root


def _fixture_output_dir(tmp_path: Path) -> Path:
    fixture_dir = tmp_path / "fixture"
    fixture_files = {
        "candidate-manifest.jsonl": '{"candidate_id":"cand-1"}\n',
        "manifests/cycle_fixture_e2e.freeze.json": '{"cycle_id":"fixture"}\n',
        "protocols/cycle_fixture_e2e.preregistration.yaml": "cycle_id: fixture\n",
        "report/leaderboard.json": '{"rows":[]}\n',
        "report/leaderboard.md": "# Fixture leaderboard\n",
    }
    for relative_path, content in fixture_files.items():
        path = fixture_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    manifest_paths = tuple(
        sorted(
            (
                *fixture_files,
                "artifact-manifest.json",
                "artifact-index.json",
            )
        )
    )
    manifest_path = fixture_dir / "artifact-manifest.json"
    manifest_path.write_text(
        json.dumps({"artifacts": list(manifest_paths)}, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    index_records = []
    for relative_path in manifest_paths:
        if relative_path == "artifact-index.json":
            continue
        artifact_path = fixture_dir / relative_path
        index_records.append(
            {
                "path": relative_path,
                "category": _fixture_category(relative_path),
                "sha256": _sha256_file(artifact_path),
                "size_bytes": artifact_path.stat().st_size,
            }
        )
    (fixture_dir / "artifact-index.json").write_text(
        json.dumps(
            {
                "artifact_count": len(index_records),
                "artifacts": index_records,
                "generated_at": "2026-05-14T12:00:00Z",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return fixture_dir


def _fixture_category(relative_path: str) -> str:
    if relative_path.startswith("report/"):
        return "leaderboard_report"
    if relative_path.startswith("manifests/"):
        return "freeze_bundle"
    if relative_path.startswith("protocols/"):
        return "preregistration"
    if relative_path == "artifact-manifest.json":
        return "manifest"
    return "workflow"


def _artifact_records(manifest: dict[str, object]) -> list[dict[str, object]]:
    records = manifest["artifacts"]
    if not isinstance(records, list) or not all(
        isinstance(item, dict) for item in records
    ):
        raise AssertionError("manifest artifacts must be a list of objects")
    return records


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()
