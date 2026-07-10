"""Run and validate the repository's complete alpha-release quality gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from legalforecast.evals.packet_builder import PacketText, build_model_packet
from legalforecast.ingestion.provenance import (
    CasePacketSchema,
    DocumentRole,
    SourceDocumentProvenance,
    sha256_text,
)
from legalforecast.multiharness.spec import (
    AdapterCapabilities,
    ConformanceReport,
    TaskIndex,
)
from legalforecast.unitization.schemas import (
    ChallengeScope,
    PredictionUnit,
    SourceCitation,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "tmp" / "release-check"
PACKAGE_HASHES_SCHEMA_VERSION = "legalforecast.release.package_hashes.v1"


@dataclass(frozen=True, slots=True)
class CheckStep:
    """One named command in the release-check sequence."""

    label: str
    command: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MultiHarnessSmokePaths:
    """Filesystem contract for release-check multi-harness smoke artifacts."""

    root: Path
    packet_jsonl: Path
    adapter_script: Path
    adapter_manifest: Path
    task_index: Path
    adapter_inspect_dir: Path
    conformance_dir: Path
    run_plan_dir: Path
    community_submissions_dir: Path
    community_aggregate_dir: Path


def build_steps(output_dir: Path) -> tuple[CheckStep, ...]:
    """Build the source-tree checks that run before installed-package smokes."""

    fixture_dir = output_dir / "fixture-run"
    dist_dir = output_dir / "dist"
    multiharness = multiharness_smoke_paths(output_dir)
    return (
        CheckStep("sync locked dependencies", ("uv", "sync", "--locked")),
        CheckStep("check formatting", ("uv", "run", "ruff", "format", "--check", ".")),
        CheckStep("lint", ("uv", "run", "ruff", "check", ".")),
        CheckStep("type-check", ("uv", "run", "pyright")),
        CheckStep(
            "public API docstring coverage",
            (
                "uv",
                "run",
                "interrogate",
                "legalforecast/publication",
                "legalforecast/labeling",
                "scripts/release_check.py",
            ),
        ),
        CheckStep("test", ("uv", "run", "pytest", "-q")),
        CheckStep(
            "review blocker verifier",
            ("uv", "run", "scripts/verify_review_blockers.py"),
        ),
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
        CheckStep(
            "multi-harness schema validation",
            (
                "uv",
                "run",
                "legalforecast",
                "multiharness",
                "adapters",
                "inspect",
                "--adapter-manifest",
                str(multiharness.adapter_manifest),
                "--output-dir",
                str(multiharness.adapter_inspect_dir),
            ),
        ),
        CheckStep(
            "multi-harness task indexing smoke",
            (
                "uv",
                "run",
                "legalforecast",
                "multiharness",
                "tasks",
                "index",
                "--suite",
                "lfb",
                "--input",
                str(multiharness.packet_jsonl),
                "--output",
                str(multiharness.task_index),
            ),
        ),
        CheckStep(
            "multi-harness conformance fixture adapter",
            (
                "uv",
                "run",
                "legalforecast",
                "multiharness",
                "conformance",
                "--adapter-manifest",
                str(multiharness.adapter_manifest),
                "--output-dir",
                str(multiharness.conformance_dir),
                "--timeout-seconds",
                "30",
            ),
        ),
        CheckStep(
            "multi-harness run dry-run",
            (
                "uv",
                "run",
                "legalforecast",
                "multiharness",
                "run",
                "--task-index",
                str(multiharness.task_index),
                "--adapter-manifest",
                str(multiharness.adapter_manifest),
                "--model-key",
                "release-fixture-model",
                "--output-dir",
                str(multiharness.run_plan_dir),
                "--run-id",
                "release-smoke",
                "--dry-run",
            ),
        ),
        CheckStep(
            "community aggregate dry-run",
            (
                "uv",
                "run",
                "legalforecast",
                "multiharness",
                "community",
                "aggregate",
                "--submissions-dir",
                str(multiharness.community_submissions_dir),
                "--output-dir",
                str(multiharness.community_aggregate_dir),
                "--dry-run",
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
    """Build CLI smoke checks for the wheel and source distribution."""

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
    """Validate fixture, multi-harness, and package artifacts from a release run."""

    fixture_dir = output_dir / "fixture-run"
    _validate_fixture_artifacts(fixture_dir)
    _validate_multiharness_smoke_artifacts(multiharness_smoke_paths(output_dir))

    dist_dir = output_dir / "dist"
    _wheel_path(dist_dir)
    _sdist_path(dist_dir)
    _validate_package_hashes(dist_dir)


def _validate_fixture_artifacts(fixture_dir: Path) -> None:
    """Require the complete fixture-E2E artifact set and a nonempty index."""

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


def multiharness_smoke_paths(output_dir: Path) -> MultiHarnessSmokePaths:
    """Resolve every multi-harness smoke path below a release output directory."""

    root = output_dir / "multiharness"
    inputs_dir = root / "inputs"
    return MultiHarnessSmokePaths(
        root=root,
        packet_jsonl=inputs_dir / "lfb-packets.jsonl",
        adapter_script=inputs_dir / "release_fixture_adapter.py",
        adapter_manifest=inputs_dir / "adapter-manifest.json",
        task_index=root / "task-index.json",
        adapter_inspect_dir=root / "adapter-inspect",
        conformance_dir=root / "conformance",
        run_plan_dir=root / "run-dry-run",
        community_submissions_dir=root / "empty-community-submissions",
        community_aggregate_dir=root / "community-aggregate-dry-run",
    )


def prepare_multiharness_smoke_inputs(output_dir: Path) -> MultiHarnessSmokePaths:
    """Write deterministic packet and adapter inputs for multi-harness smokes."""

    paths = multiharness_smoke_paths(output_dir)
    paths.packet_jsonl.parent.mkdir(parents=True, exist_ok=True)
    paths.community_submissions_dir.mkdir(parents=True, exist_ok=True)
    paths.packet_jsonl.write_text(
        json.dumps(_release_smoke_packet_record(), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    paths.adapter_script.write_text(_fixture_adapter_script(), encoding="utf-8")
    paths.adapter_manifest.write_text(
        json.dumps(
            {
                "schema_version": "legalforecast.multiharness.adapter_manifest.v1",
                "adapter_id": "release-fixture-cli",
                "display_name": "Release Fixture CLI Adapter",
                "adapter_version": "0.1.0",
                "command": [sys.executable, str(paths.adapter_script)],
                "contributors": [],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return paths


def _validate_multiharness_smoke_artifacts(paths: MultiHarnessSmokePaths) -> None:
    """Validate schemas and success markers emitted by multi-harness smokes."""

    TaskIndex.from_record(_read_json_object(paths.task_index, "task index"))
    AdapterCapabilities.from_record(
        _read_json_object(
            paths.adapter_inspect_dir / "adapter-capabilities.json",
            "adapter capabilities",
        )
    )
    conformance = ConformanceReport.from_record(
        _read_json_object(
            paths.conformance_dir / "conformance-report.json",
            "conformance report",
        )
    )
    if conformance.status != "passed":
        raise RuntimeError("multi-harness conformance smoke did not pass")
    run_plan = _read_json_object(paths.run_plan_dir / "run-plan.json", "run plan")
    if run_plan.get("dry_run") is not True:
        raise RuntimeError("multi-harness run smoke must be a dry-run plan")
    aggregate_plan = _read_json_object(
        paths.community_aggregate_dir / "community-aggregate-plan.json",
        "community aggregate plan",
    )
    if aggregate_plan.get("dry_run") is not True:
        raise RuntimeError("community aggregate smoke must be a dry-run plan")


def package_hashes_path(dist_dir: Path) -> Path:
    """Return the canonical package-hash manifest path beside the dist directory."""

    return dist_dir.parent / "package-artifact-hashes.json"


def write_package_hashes(dist_dir: Path, *, output_path: Path | None = None) -> Path:
    """Hash package artifacts without recursively including a hash manifest.

    Args:
        dist_dir: Directory containing built wheel and source artifacts.
        output_path: Optional manifest destination; defaults beside ``dist_dir``.

    Returns:
        The path of the written package-hash manifest.

    Raises:
        RuntimeError: If ``dist_dir`` contains no package artifacts to hash.
    """

    output_path = output_path or package_hashes_path(dist_dir)
    excluded_paths = {
        output_path.resolve(),
        (dist_dir / "package-artifact-hashes.json").resolve(),
    }
    artifacts: list[dict[str, object]] = []
    for artifact_path in sorted(dist_dir.iterdir()):
        if not artifact_path.is_file():
            continue
        if artifact_path.resolve() in excluded_paths:
            continue
        artifacts.append(
            {
                "filename": artifact_path.name,
                "sha256": _sha256_file(artifact_path),
                "size_bytes": artifact_path.stat().st_size,
            }
        )
    if not artifacts:
        raise RuntimeError("no package artifacts found for hashing")
    output_path.write_text(
        json.dumps(
            {
                "schema_version": PACKAGE_HASHES_SCHEMA_VERSION,
                "artifacts": artifacts,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_package_hashes(
    dist_dir: Path, *, hashes_path: Path | None = None
) -> None:
    """Verify each declared package hash and size against the current artifacts.

    The active manifest and the legacy in-directory manifest location are excluded
    from the artifact set so a manifest can never authenticate itself.
    """

    hashes_path = hashes_path or package_hashes_path(dist_dir)
    record = _read_json_object(
        hashes_path,
        "package artifact hashes",
    )
    if record.get("schema_version") != PACKAGE_HASHES_SCHEMA_VERSION:
        raise RuntimeError("package artifact hashes schema version is invalid")
    raw_artifacts = record.get("artifacts")
    if not isinstance(raw_artifacts, list) or not raw_artifacts:
        raise RuntimeError("package artifact hashes must include package artifacts")
    artifacts = cast(list[object], raw_artifacts)
    excluded_paths = {
        hashes_path.resolve(),
        (dist_dir / "package-artifact-hashes.json").resolve(),
    }
    by_name = {
        path.name: path
        for path in dist_dir.iterdir()
        if path.is_file() and path.resolve() not in excluded_paths
    }
    for item in artifacts:
        if not isinstance(item, dict):
            raise RuntimeError("package artifact hash entries must be objects")
        item_record = cast(dict[str, object], item)
        filename = item_record.get("filename")
        sha256 = item_record.get("sha256")
        size_bytes = item_record.get("size_bytes")
        if not isinstance(filename, str) or filename not in by_name:
            raise RuntimeError(f"unknown package artifact hash entry: {filename!r}")
        path = by_name[filename]
        if sha256 != _sha256_file(path):
            raise RuntimeError(f"package artifact hash mismatch: {filename}")
        if size_bytes != path.stat().st_size:
            raise RuntimeError(f"package artifact size mismatch: {filename}")


def _read_json_object(path: Path, label: str) -> dict[str, object]:
    """Read a required JSON object or raise a release-check error with context."""

    if not path.is_file():
        raise RuntimeError(f"{label} does not exist: {path}")
    record = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(record, dict):
        raise RuntimeError(f"{label} must be a JSON object: {path}")
    return cast(dict[str, object], record)


def _sha256_file(path: Path) -> str:
    """Return the lowercase SHA-256 hex digest for a file."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _wheel_path(dist_dir: Path) -> Path:
    """Return the first built wheel, failing when the build produced none."""

    wheels = sorted(dist_dir.glob("*.whl"))
    if not wheels:
        raise RuntimeError("package build did not produce a wheel")
    return wheels[0]


def _sdist_path(dist_dir: Path) -> Path:
    """Return the first built source distribution, failing when none exists."""

    sdists = sorted(dist_dir.glob("*.tar.gz"))
    if not sdists:
        raise RuntimeError("package build did not produce an sdist")
    return sdists[0]


def main(argv: Sequence[str] | None = None) -> int:
    """Run the release gate or print its deterministic plan for ``--dry-run``."""

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
        _clean_output_dir(output_dir)
    else:
        _validate_output_dir(output_dir)
    output_dir.mkdir(parents=True)
    prepare_multiharness_smoke_inputs(output_dir)

    for step in steps:
        print(f"==> {step.label}", flush=True)
        subprocess.run(step.command, cwd=REPO_ROOT, check=True)

    write_package_hashes(output_dir / "dist")
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


def _release_smoke_packet_record() -> dict[str, object]:
    """Build the deterministic packet record used by release multi-harness smokes."""

    packet = build_model_packet(
        case_packet=CasePacketSchema(
            candidate_id="release-smoke-candidate",
            case_id="release-smoke-case",
            court="S.D.N.Y.",
            docket_number="1:26-cv-9000",
            generated_at=datetime(2026, 5, 14, tzinfo=UTC),
            documents=(
                _release_smoke_document(
                    "complaint",
                    DocumentRole.COMPLAINT,
                    1,
                ),
                _release_smoke_document(
                    "mtd-memo",
                    DocumentRole.MTD_MEMORANDUM,
                    34,
                ),
                _release_smoke_document(
                    "decision",
                    DocumentRole.DECISION,
                    50,
                    mounted=False,
                    predecision=False,
                    outcome=True,
                ),
            ),
        ),
        prediction_units=(
            PredictionUnit(
                unit_id="count_i_issuer",
                count="I",
                claim_name="Section 10(b)",
                defendant_group="Issuer",
                challenged_by_motion=True,
                challenge_scope=ChallengeScope.ENTIRE_CLAIM,
                unit_confidence=0.95,
                source_citations=(SourceCitation(document_id="complaint", page=1),),
            ),
        ),
        texts=(
            PacketText(source_document_id="complaint", text="complaint fixture text"),
            PacketText(source_document_id="mtd-memo", text="motion fixture text"),
        ),
        metadata={"judge": "Judge Release", "nos_macro_category": "securities"},
    )
    return packet.to_record()


def _release_smoke_document(
    document_id: str,
    role: DocumentRole,
    docket_entry_number: int,
    *,
    mounted: bool = True,
    predecision: bool = True,
    outcome: bool = False,
) -> SourceDocumentProvenance:
    """Build one synthetic source-document provenance record for release smokes."""

    return SourceDocumentProvenance(
        source_provider="release-check-fixture",
        source_case_id="release-smoke-case",
        source_document_id=document_id,
        court="S.D.N.Y.",
        docket_number="1:26-cv-9000",
        document_role=role,
        retrieved_at=datetime(2026, 5, 14, tzinfo=UTC),
        source_url_or_reference=f"fixture://{document_id}",
        sha256=sha256_text(f"{document_id} release fixture source"),
        is_predecision_material=predecision,
        is_mounted_for_model=mounted,
        docket_entry_number=docket_entry_number,
        contains_target_outcome=outcome,
        packet_section="filings",
    )


def _fixture_adapter_script() -> str:
    """Render the deterministic command-adapter script used by release smokes."""

    return "\n".join(
        (
            "from __future__ import annotations",
            "import argparse",
            "import json",
            "import pathlib",
            "import sys",
            "",
            "ADAPTER_ID = 'release-fixture-cli'",
            "ADAPTER_VERSION = '0.1.0'",
            "",
            "def write_json(path, payload):",
            "    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)",
            "    pathlib.Path(path).write_text(",
            "        json.dumps(payload, sort_keys=True), encoding='utf-8'",
            "    )",
            "",
            "def capabilities(argv):",
            "    parser = argparse.ArgumentParser()",
            "    parser.add_argument('--output', required=True)",
            "    args = parser.parse_args(argv)",
            "    write_json(args.output, {",
            "        'schema_version': (",
            "            'legalforecast.multiharness.adapter_capabilities.v1'",
            "        ),",
            "        'adapter_id': ADAPTER_ID,",
            "        'adapter_version': ADAPTER_VERSION,",
            "        'supported_families': ['legalforecast_mtd', 'harvey_lab'],",
            "        'supported_scoring_modes': ['lfb_brier', 'lab_native'],",
            "        'supports_sandbox_policy': True,",
            "        'capabilities_sha256': 'sha256:' + '1' * 64,",
            "    })",
            "",
            "def run(argv):",
            "    parser = argparse.ArgumentParser()",
            "    parser.add_argument('--request', required=True)",
            "    parser.add_argument('--output', required=True)",
            "    parser.add_argument('--workspace', required=True)",
            "    args = parser.parse_args(argv)",
            "    request = json.loads(pathlib.Path(args.request).read_text())",
            "    write_json(args.output, {",
            "        'schema_version': 'legalforecast.multiharness.run_result.v1',",
            "        'result_id': request['request_id'] + ':result',",
            "        'request_id': request['request_id'],",
            "        'status': 'succeeded',",
            "        'result_sha256': 'sha256:' + '2' * 64,",
            "        'artifacts': [],",
            "        'public_summary': {",
            "            'task_id': request['task']['task_id'],",
            "            'family': request['task']['family'],",
            "            'sandbox_policy_id': request['sandbox_policy']['policy_id'],",
            "        },",
            "    })",
            "",
            "phase = sys.argv[1]",
            "if phase == 'capabilities':",
            "    capabilities(sys.argv[2:])",
            "elif phase == 'run':",
            "    run(sys.argv[2:])",
            "else:",
            "    raise SystemExit('unsupported phase: ' + phase)",
            "",
        )
    )


def _clean_output_dir(output_dir: Path) -> None:
    """Delete a previously validated release output directory."""

    _validate_output_dir(output_dir)
    shutil.rmtree(output_dir)


def _validate_output_dir(output_dir: Path) -> None:
    """Require release output to be a child of the repository's temporary root."""

    tmp_root = (REPO_ROOT / "tmp").resolve()
    if output_dir == tmp_root:
        raise RuntimeError(
            f"refusing to use tmp root directly as output dir: {output_dir}"
        )
    if not output_dir.is_relative_to(tmp_root):
        raise RuntimeError(
            f"refusing to delete output dir outside {tmp_root}: {output_dir}"
        )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
