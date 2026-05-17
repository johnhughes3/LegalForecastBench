from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "tmp" / "alpha-release-check"


@dataclass(frozen=True, slots=True)
class CheckStep:
    label: str
    command: tuple[str, ...]


def build_steps(output_dir: Path) -> tuple[CheckStep, ...]:
    fixture_dir = output_dir / "fixture-run"
    dist_dir = output_dir / "dist"
    return (
        CheckStep("sync locked dependencies", ("uv", "sync", "--locked")),
        CheckStep("check formatting", ("uv", "run", "ruff", "format", "--check", ".")),
        CheckStep("lint", ("uv", "run", "ruff", "check", ".")),
        CheckStep("type-check", ("uv", "run", "pyright")),
        CheckStep("test", ("uv", "run", "pytest", "-q")),
        CheckStep("CLI help smoke", ("uv", "run", "legalforecast", "--help")),
        CheckStep(
            "fixture E2E",
            (
                "uv",
                "run",
                "legalforecast",
                "fixture",
                "e2e",
                "--output-dir",
                str(fixture_dir),
            ),
        ),
        CheckStep("build package", ("uv", "build", "--out-dir", str(dist_dir))),
    )


def build_installed_cli_steps(
    output_dir: Path,
    *,
    wheel_path: Path,
    sdist_path: Path,
) -> tuple[CheckStep, ...]:
    installed_fixture_dir = output_dir / "installed-fixture-run"
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    base_command = ("uv", "run", "--no-project", "--python", python_version)
    return (
        CheckStep(
            "installed wheel CLI help smoke",
            (*base_command, "--with", str(wheel_path), "legalforecast", "--help"),
        ),
        CheckStep(
            "installed wheel fixture E2E",
            (
                *base_command,
                "--with",
                str(wheel_path),
                "legalforecast",
                "fixture",
                "e2e",
                "--output-dir",
                str(installed_fixture_dir),
            ),
        ),
        CheckStep(
            "installed sdist CLI help smoke",
            (*base_command, "--with", str(sdist_path), "legalforecast", "--help"),
        ),
    )


def validate_artifacts(output_dir: Path) -> None:
    fixture_dir = output_dir / "fixture-run"
    _validate_fixture_artifacts(fixture_dir)

    dist_dir = output_dir / "dist"
    _wheel_path(dist_dir)
    _sdist_path(dist_dir)


def _validate_fixture_artifacts(fixture_dir: Path) -> None:
    required_paths = (
        fixture_dir / "artifact-index.json",
        fixture_dir / "artifact-manifest.json",
        fixture_dir / "report" / "leaderboard.json",
        fixture_dir / "report" / "leaderboard.csv",
        fixture_dir / "report" / "leaderboard.md",
        fixture_dir / "report" / "leaderboard.html",
        fixture_dir / "manifests" / "cycle_fixture_e2e.freeze.json",
        fixture_dir / "preregistration-validation.json",
    )
    missing = [path for path in required_paths if not path.is_file()]
    if missing:
        formatted = "\n".join(f"- {path.relative_to(REPO_ROOT)}" for path in missing)
        raise RuntimeError(f"release-check artifacts missing:\n{formatted}")

    artifact_index = json.loads((fixture_dir / "artifact-index.json").read_text())
    artifact_count = artifact_index.get("artifact_count")
    if not isinstance(artifact_count, int) or artifact_count <= 0:
        raise RuntimeError("artifact-index.json must include a positive artifact_count")


def _wheel_path(dist_dir: Path) -> Path:
    wheels = sorted(dist_dir.glob("*.whl"))
    if not wheels:
        raise RuntimeError("package build did not produce a wheel")
    return wheels[0]


def _sdist_path(dist_dir: Path) -> Path:
    sdists = sorted(dist_dir.glob("*.tar.gz"))
    if not sdists:
        raise RuntimeError("package build did not produce an sdist")
    return sdists[0]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the full LegalForecast-MTD v0.1 alpha release check."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for fixture and build artifacts.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the planned commands without executing them.",
    )
    args = parser.parse_args(argv)

    output_dir = args.output_dir.resolve()
    steps = build_steps(output_dir)
    if args.dry_run:
        for step in steps:
            print(f"{step.label}: {' '.join(step.command)}")
        for step in build_installed_cli_steps(
            output_dir,
            wheel_path=Path("<built-wheel>"),
            sdist_path=Path("<built-sdist>"),
        ):
            print(f"{step.label}: {' '.join(step.command)}")
        print(f"artifact output: {output_dir}")
        return 0

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    for step in steps:
        print(f"==> {step.label}", flush=True)
        subprocess.run(step.command, cwd=REPO_ROOT, check=True)

    validate_artifacts(output_dir)
    print("==> artifact validation")
    dist_dir = output_dir / "dist"
    for step in build_installed_cli_steps(
        output_dir,
        wheel_path=_wheel_path(dist_dir),
        sdist_path=_sdist_path(dist_dir),
    ):
        print(f"==> {step.label}", flush=True)
        subprocess.run(step.command, cwd=output_dir, check=True)

    _validate_fixture_artifacts(output_dir / "installed-fixture-run")
    print("==> installed artifact validation")
    print(f"fixture artifacts: {output_dir / 'fixture-run'}")
    print(f"installed fixture artifacts: {output_dir / 'installed-fixture-run'}")
    print(f"package artifacts: {output_dir / 'dist'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
