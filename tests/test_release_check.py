from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_fixture_adapter_script_rendering_is_stable() -> None:
    module = _load_release_check_module()

    rendered = module._fixture_adapter_script()

    assert len(rendered) == 1961
    assert hashlib.sha256(rendered.encode("utf-8")).hexdigest() == (
        "02622270700f1ba4f17689fe9367751038d307a03b43ff807cea51ab52918b39"
    )


def test_release_check_plans_full_gate(tmp_path: Path) -> None:
    module = _load_release_check_module()
    steps = module.build_steps(tmp_path)
    labels = [step.label for step in steps]
    commands = [" ".join(step.command) for step in steps]

    assert labels == [
        "sync locked dependencies",
        "check formatting",
        "lint",
        "type-check",
        "public API docstring coverage",
        "test",
        "review blocker verifier",
        "CLI help smoke",
        "fixture E2E",
        "multi-harness schema validation",
        "multi-harness task indexing smoke",
        "multi-harness conformance fixture adapter",
        "multi-harness run dry-run",
        "community aggregate dry-run",
        "build package",
    ]
    assert "uv sync --locked" in commands
    assert "uv run pyright" in commands
    assert "uv run scripts/verify_review_blockers.py" in commands
    assert any("legalforecast fixture e2e" in command for command in commands)
    assert any(
        "legalforecast multiharness adapters inspect" in command for command in commands
    )
    assert any(
        "legalforecast multiharness tasks index" in command for command in commands
    )
    assert any(
        "legalforecast multiharness conformance" in command for command in commands
    )
    assert any(
        "legalforecast multiharness run" in command and "--dry-run" in command
        for command in commands
    )
    assert any(
        "legalforecast multiharness community aggregate" in command
        and "--dry-run" in command
        for command in commands
    )
    assert any("uv build --out-dir" in command for command in commands)
    assert any(
        "uv run interrogate legalforecast/publication legalforecast/labeling "
        "scripts" in command
        for command in commands
    )


def test_release_check_plans_installed_artifact_smokes(tmp_path: Path) -> None:
    module = _load_release_check_module()
    steps = module.build_installed_cli_steps(
        tmp_path,
        wheel_path=tmp_path / "dist" / "legalforecast_mtd-0.1.0a1-py3-none-any.whl",
        sdist_path=tmp_path / "dist" / "legalforecast_mtd-0.1.0a1.tar.gz",
    )
    labels = [step.label for step in steps]
    commands = [" ".join(step.command) for step in steps]

    assert labels == [
        "installed wheel CLI help smoke",
        "installed wheel fixture E2E",
        "installed sdist CLI help smoke",
    ]
    assert all("--no-project" in command for command in commands)
    assert all("--no-cache" in command for command in commands)
    assert any("legalforecast fixture e2e" in command for command in commands)


def test_release_check_validates_required_artifacts(tmp_path: Path) -> None:
    module = _load_release_check_module()
    fixture_dir = tmp_path / "fixture-run"
    report_dir = fixture_dir / "report"
    manifests_dir = fixture_dir / "manifests"
    dist_dir = tmp_path / "dist"
    multiharness = module.multiharness_smoke_paths(tmp_path)
    report_dir.mkdir(parents=True)
    manifests_dir.mkdir(parents=True)
    dist_dir.mkdir(parents=True)
    multiharness.adapter_inspect_dir.mkdir(parents=True)
    multiharness.conformance_dir.mkdir(parents=True)
    multiharness.run_plan_dir.mkdir(parents=True)
    multiharness.community_aggregate_dir.mkdir(parents=True)

    (fixture_dir / "artifact-index.json").write_text(
        json.dumps({"artifact_count": 1}),
        encoding="utf-8",
    )
    for path in (
        fixture_dir / "artifact-manifest.json",
        report_dir / "leaderboard.json",
        report_dir / "leaderboard.csv",
        report_dir / "leaderboard.md",
        report_dir / "leaderboard.html",
    ):
        path.write_text("ok", encoding="utf-8")
    (manifests_dir / "cycle_fixture_e2e.freeze.json").write_text(
        json.dumps(
            {"artifacts": [{"name": f"artifact-{index}"} for index in range(9)]}
        ),
        encoding="utf-8",
    )
    (dist_dir / "legalforecast_mtd-0.1.0a1-py3-none-any.whl").write_text(
        "wheel",
        encoding="utf-8",
    )
    (dist_dir / "legalforecast_mtd-0.1.0a1.tar.gz").write_text(
        "sdist",
        encoding="utf-8",
    )
    (multiharness.task_index).write_text(
        json.dumps(
            {
                "schema_version": "legalforecast.multiharness.task_index.v1",
                "index_id": "release-smoke",
                "selection_namespace": "legalforecast_mtd",
                "index_sha256": "sha256:" + "1" * 64,
                "tasks": [
                    {
                        "schema_version": "legalforecast.multiharness.task.v1",
                        "task_id": "lfb:release-smoke:full_packet",
                        "family": "legalforecast_mtd",
                        "scoring_mode": "lfb_brier",
                        "suite_version": "release-smoke",
                        "source_id": "release-smoke",
                        "task_sha256": "sha256:" + "2" * 64,
                        "metadata": {},
                        "artifacts": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (multiharness.adapter_inspect_dir / "adapter-capabilities.json").write_text(
        json.dumps(
            {
                "schema_version": (
                    "legalforecast.multiharness.adapter_capabilities.v1"
                ),
                "adapter_id": "release-fixture-cli",
                "adapter_version": "0.1.0",
                "supported_families": ["legalforecast_mtd", "harvey_lab"],
                "supported_scoring_modes": ["lfb_brier", "lab_native"],
                "supports_sandbox_policy": True,
                "capabilities_sha256": "sha256:" + "3" * 64,
            }
        ),
        encoding="utf-8",
    )
    (multiharness.conformance_dir / "conformance-report.json").write_text(
        json.dumps(
            {
                "schema_version": "legalforecast.multiharness.conformance_report.v1",
                "report_id": "release-fixture-cli:0.1.0:conformance",
                "adapter_id": "release-fixture-cli",
                "adapter_version": "0.1.0",
                "status": "passed",
                "checks": {"manifest_validation": "passed: ok"},
                "artifacts": [],
            }
        ),
        encoding="utf-8",
    )
    (multiharness.run_plan_dir / "run-plan.json").write_text(
        json.dumps({"dry_run": True}),
        encoding="utf-8",
    )
    (multiharness.community_aggregate_dir / "community-aggregate-plan.json").write_text(
        json.dumps({"dry_run": True}),
        encoding="utf-8",
    )
    hashes_path = module.write_package_hashes(dist_dir)

    assert hashes_path == tmp_path / "package-artifact-hashes.json"
    assert not (dist_dir / "package-artifact-hashes.json").exists()
    module.validate_artifacts(tmp_path)


def test_package_hashes_ignore_stale_legacy_manifest(tmp_path: Path) -> None:
    module = _load_release_check_module()
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    wheel_path = dist_dir / "legalforecast_mtd-0.1.0a1-py3-none-any.whl"
    wheel_path.write_text("wheel", encoding="utf-8")
    (dist_dir / "package-artifact-hashes.json").write_text(
        '{"stale": true}\n',
        encoding="utf-8",
    )

    hashes_path = module.write_package_hashes(dist_dir)
    record = json.loads(hashes_path.read_text(encoding="utf-8"))

    assert [artifact["filename"] for artifact in record["artifacts"]] == [
        wheel_path.name
    ]
    module._validate_package_hashes(dist_dir, hashes_path=hashes_path)


def test_package_hash_validation_excludes_custom_manifest_path(tmp_path: Path) -> None:
    module = _load_release_check_module()
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    hashes_path = dist_dir / "custom-hashes.json"
    hashes_path.write_text(
        json.dumps(
            {
                "schema_version": module.PACKAGE_HASHES_SCHEMA_VERSION,
                "artifacts": [
                    {
                        "filename": hashes_path.name,
                        "sha256": "sha256:" + "1" * 64,
                        "size_bytes": 0,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="unknown package artifact hash entry"):
        module._validate_package_hashes(dist_dir, hashes_path=hashes_path)


def _load_release_check_module() -> ModuleType:
    script_path = ROOT / "scripts" / "release_check.py"
    spec = importlib.util.spec_from_file_location("release_check", script_path)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load release_check.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module
