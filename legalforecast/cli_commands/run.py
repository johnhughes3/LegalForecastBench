# pyright: reportPrivateUsage=false

"""The ``legalforecast run`` release-only execution commands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import cast

from legalforecast.runner import RunConfig, execute_release_run, issue_runner_fixture
from legalforecast.runner.fixture import FIXTURE_MODEL_KEY, FixtureModelTransport


def register(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register provider-free fixture issuance and release execution."""

    run = subparsers.add_parser(
        "run",
        help="Execute a validated forecast release with durable local spend control.",
    )
    commands = run.add_subparsers(dest="run_command", metavar="COMMAND")

    issue_fixture = commands.add_parser(
        "issue-fixture",
        help="Issue the deterministic provider-free three-case runner fixture.",
    )
    issue_fixture.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Create-only destination for the release and fixture model registry.",
    )
    issue_fixture.set_defaults(handler=run_issue_fixture)

    execute = commands.add_parser(
        "execute",
        help="Execute or resume exact cells from an outcome-blinded forecast release.",
    )
    execute.add_argument(
        "--manifest",
        "--run-manifest",
        dest="manifest",
        type=Path,
        help=(
            "Canonical locked benchmark-run manifest selecting the forecast "
            "release cases."
        ),
    )
    execute.add_argument(
        "--forecast",
        type=Path,
        required=True,
        help="Canonical forecast-release.json to authenticate and execute.",
    )
    execute.add_argument(
        "--artifact-root",
        type=Path,
        required=True,
        help="Root containing every artifact committed by the forecast release.",
    )
    execute.add_argument(
        "--model-registry",
        type=Path,
        required=True,
        help="Frozen model registry JSON containing the selected engine.",
    )
    execute.add_argument(
        "--model-key",
        required=True,
        help="Exact provider:model_id registry key for the single run engine.",
    )
    execute.add_argument(
        "--ledger",
        type=Path,
        required=True,
        help="SQLite run/cell/spend ledger; reuse only for this exact run identity.",
    )
    execute.add_argument(
        "--receipts-dir",
        type=Path,
        required=True,
        help="Create-only public-safe receipt directory.",
    )
    execute.add_argument(
        "--ceiling-microusd",
        type=int,
        required=True,
        help="Positive owner-approved total ceiling in millionths of one US dollar.",
    )
    execute.add_argument(
        "--approval-reference",
        required=True,
        help="Nonempty plain reference to the owner approval covering this ceiling.",
    )
    execute.add_argument(
        "--harness",
        default="native",
        choices=("native",),
        help=(
            "Authenticated execution adapter bound into every run cell; "
            "forecast-release.v1 currently supports only native."
        ),
    )
    execute.add_argument(
        "--ablation",
        default="none",
        choices=("none",),
        help=(
            "Authenticated prompt treatment bound into every run cell; "
            "forecast-release.v1 currently supports only none."
        ),
    )
    execute.add_argument(
        "--repeat-count",
        type=int,
        default=1,
        help="Positive repeats per prediction unit (default: 1).",
    )
    execute.add_argument(
        "--account",
        default="default",
        help=(
            "Stable provider-account identity for local spend scope (default: default)."
        ),
    )
    execute.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Use the deterministic no-network fixture transport; requires the "
            f"exact {FIXTURE_MODEL_KEY} fixture engine and writes normal receipts."
        ),
    )
    execute.set_defaults(handler=run_execute)


def run_issue_fixture(args: argparse.Namespace) -> int:
    output_dir = cast(Path, args.output_dir)
    issue_runner_fixture(output_dir)
    print(
        json.dumps(
            {
                "forecast_release": str(
                    output_dir / "release" / "forecast-release.json"
                ),
                "labels_release": str(output_dir / "release" / "labels-release.json"),
                "model_key": FIXTURE_MODEL_KEY,
                "model_registry": str(output_dir / "model-registry.json"),
            },
            sort_keys=True,
        )
    )
    return 0


def run_execute(args: argparse.Namespace) -> int:
    model_key = cast(str, args.model_key)
    dry_run = cast(bool, args.dry_run)
    if dry_run and model_key != FIXTURE_MODEL_KEY:
        raise ValueError(
            "--dry-run requires the exact provider-free fixture model "
            f"{FIXTURE_MODEL_KEY}"
        )
    config = RunConfig(
        forecast_path=cast(Path, args.forecast),
        artifact_root=cast(Path, args.artifact_root),
        model_registry_path=cast(Path, args.model_registry),
        model_key=model_key,
        ledger_path=cast(Path, args.ledger),
        receipts_dir=cast(Path, args.receipts_dir),
        ceiling_microusd=cast(int, args.ceiling_microusd),
        approval_reference=cast(str, args.approval_reference),
        harness=cast(str, args.harness),
        ablation=cast(str, args.ablation),
        repeat_count=cast(int, args.repeat_count),
        account=cast(str, args.account),
        manifest_path=cast(Path | None, args.manifest),
    )
    summary = execute_release_run(
        config,
        transport=FixtureModelTransport() if dry_run else None,
        environ={"OPENAI_API_KEY": "provider-free-fixture-key"} if dry_run else None,
    )
    print(json.dumps(summary.to_record(), sort_keys=True))
    return 0
