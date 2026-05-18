from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from legalforecast import __version__
from legalforecast.publication.release_bundle import (
    ReleaseBundleConfig,
    build_release_bundle,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "tmp" / "release-bundle"
DEFAULT_RELEASE_TAG = "v0.1.0-alpha.1"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a LegalForecast-MTD v0.1 alpha release artifact bundle."
    )
    parser.add_argument(
        "--fixture-output-dir",
        type=Path,
        required=True,
        help="Existing legalforecast fixture e2e output directory.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory where the bundle and release-manifest.json are written.",
    )
    parser.add_argument(
        "--dist-dir",
        type=Path,
        help="Optional directory containing built wheel and sdist artifacts.",
    )
    parser.add_argument(
        "--commit",
        help=(
            "Release commit SHA recorded in the bundle manifest. "
            "Defaults to git rev-parse HEAD after arguments are parsed."
        ),
    )
    parser.add_argument(
        "--version",
        default=__version__,
        help="Python package version recorded in the bundle manifest.",
    )
    parser.add_argument(
        "--tag",
        default=DEFAULT_RELEASE_TAG,
        help="GitHub release tag recorded in the bundle manifest.",
    )
    parser.add_argument(
        "--generated-at",
        help="Optional ISO timestamp for deterministic release-candidate rebuilds.",
    )
    args = parser.parse_args(argv)

    try:
        release_commit = args.commit or _git_head(REPO_ROOT)
    except RuntimeError as exc:
        parser.error(str(exc))
    manifest = build_release_bundle(
        ReleaseBundleConfig(
            fixture_output_dir=args.fixture_output_dir.resolve(),
            output_dir=args.output_dir.resolve(),
            dist_dir=args.dist_dir.resolve() if args.dist_dir is not None else None,
            release_commit=release_commit,
            package_version=args.version,
            release_tag=args.tag,
            repo_root=REPO_ROOT,
            generated_at=(
                _parse_generated_at(args.generated_at)
                if args.generated_at is not None
                else None
            ),
        )
    )
    print(
        json.dumps(
            {
                "manifest": str(args.output_dir / "release-manifest.json"),
                "artifact_count": manifest["artifact_count"],
            },
            sort_keys=True,
        )
    )
    return 0


def _git_head(repo_root: Path) -> str:
    try:
        return subprocess.check_output(
            ("git", "rev-parse", "HEAD"),
            cwd=repo_root,
            text=True,
            stderr=subprocess.STDOUT,
        ).strip()
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(
            "could not determine git HEAD; pass --commit explicitly"
        ) from exc


def _parse_generated_at(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
