from __future__ import annotations

from pathlib import Path
from typing import Any

from legalforecast.cli import main
from legalforecast.publication.release_bundle import (
    RELEASE_METADATA_PATHS,
    RELEASE_STATUS,
    ReleaseBundleConfig,
    build_release_bundle,
)

ROOT = Path(__file__).resolve().parents[1]


def test_release_bundle_uses_current_public_docs(tmp_path: Path) -> None:
    fixture_output_dir = tmp_path / "fixture-run"
    output_dir = tmp_path / "release-bundle"

    assert main(["fixture", "e2e", "--output-dir", str(fixture_output_dir)]) == 0

    manifest = build_release_bundle(
        ReleaseBundleConfig(
            fixture_output_dir=fixture_output_dir,
            output_dir=output_dir,
            release_commit="abcdef1",
            package_version="0.1.0a1",
            release_tag="v0.1.0-alpha.1",
            repo_root=ROOT,
        )
    )

    assert manifest["release_status"] == RELEASE_STATUS
    assert "result_tier" not in manifest
    metadata_paths = {
        artifact["path"]
        for artifact in _artifact_records(manifest)
        if artifact["source_class"] == "release_metadata"
    }
    assert {
        f"release-metadata/{path.as_posix()}" for path in RELEASE_METADATA_PATHS
    } <= metadata_paths
    assert (output_dir / "release-metadata/docs/METHODS.md").read_bytes() == (
        ROOT / "docs/METHODS.md"
    ).read_bytes()


def _artifact_records(manifest: dict[str, object]) -> list[dict[str, Any]]:
    value = manifest["artifacts"]
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise AssertionError("release bundle manifest must contain artifact records")
    return value
