from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]


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
        "test",
        "CLI help smoke",
        "fixture E2E",
        "build package",
    ]
    assert "uv sync --locked" in commands
    assert "uv run pyright" in commands
    assert any("legalforecast fixture e2e" in command for command in commands)
    assert any("uv build --out-dir" in command for command in commands)


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
    assert any("legalforecast fixture e2e" in command for command in commands)


def test_release_check_validates_required_artifacts(tmp_path: Path) -> None:
    module = _load_release_check_module()
    fixture_dir = tmp_path / "fixture-run"
    report_dir = fixture_dir / "report"
    manifests_dir = fixture_dir / "manifests"
    dist_dir = tmp_path / "dist"
    report_dir.mkdir(parents=True)
    manifests_dir.mkdir(parents=True)
    dist_dir.mkdir(parents=True)

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
        manifests_dir / "cycle_fixture_e2e.freeze.json",
        fixture_dir / "preregistration-validation.json",
        dist_dir / "legalforecast_mtd-0.1.0a1-py3-none-any.whl",
        dist_dir / "legalforecast_mtd-0.1.0a1.tar.gz",
    ):
        path.write_text("ok", encoding="utf-8")

    module.validate_artifacts(tmp_path)


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
