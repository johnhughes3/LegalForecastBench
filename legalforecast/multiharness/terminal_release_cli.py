"""Arguments for a local, release-backed coding-terminal experiment."""

from __future__ import annotations

import argparse
import math
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from legalforecast.multiharness.auth_profiles import (
    FIXTURE_NONE,
    PUBLISHED_API_KEY,
)
from legalforecast.multiharness.container_harness.images import (
    require_digest_pinned_image,
)
from legalforecast.multiharness.sandbox import BACKEND_DOCKER, BACKEND_PODMAN


@dataclass(frozen=True, slots=True)
class TerminalReleaseOptions:
    """Validated, non-secret command input before any release or key access."""

    forecast_release: Path
    labels_release: Path
    artifact_root: Path
    output_dir: Path
    model_key: str
    image: str
    auth_profile: str
    max_budget_usd: float | None
    approval_reference: str | None
    fixture_base_url: str | None
    fixture_egress_network: str | None
    backend: str
    timeout_seconds: int
    run_id: str

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> TerminalReleaseOptions:
        """Refuse ambiguous spend and stale output before creating artifacts."""

        image = str(args.image)
        require_digest_pinned_image(image, "image")
        output_dir = Path(args.output_dir)
        if output_dir.exists() or output_dir.is_symlink():
            raise ValueError("--output-dir must be a fresh, absent path")
        profile = str(args.auth_profile)
        amount = args.max_budget_usd
        approval = args.approval_reference
        fixture_base_url = args.fixture_base_url
        fixture_egress_network = args.fixture_egress_network
        if profile == FIXTURE_NONE:
            if amount is not None or approval is not None:
                raise ValueError("fixture-none cannot carry paid-run authority")
            if not isinstance(fixture_base_url, str) or not fixture_base_url.strip():
                raise ValueError("fixture-none requires --fixture-base-url")
        elif profile == PUBLISHED_API_KEY:
            if fixture_base_url is not None or fixture_egress_network is not None:
                raise ValueError("published-api-key cannot use fixture routing")
            if (
                not isinstance(amount, float | int)
                or not math.isfinite(amount)
                or amount <= 0
            ):
                raise ValueError("published-api-key requires a positive budget")
            if not isinstance(approval, str) or not approval.strip():
                raise ValueError(
                    "published-api-key requires an existing approval reference"
                )
        else:
            raise ValueError(f"unsupported auth profile: {profile}")
        model_key = str(args.model_key)
        run_id = str(args.run_id)
        if not model_key.strip() or not run_id.strip():
            raise ValueError("model key and run ID must be non-empty")
        timeout = int(args.timeout_seconds)
        if timeout <= 0:
            raise ValueError("--timeout-seconds must be positive")
        return cls(
            forecast_release=Path(args.forecast_release),
            labels_release=Path(args.labels_release),
            artifact_root=Path(args.artifact_root),
            output_dir=output_dir,
            model_key=model_key,
            image=image,
            auth_profile=profile,
            max_budget_usd=float(amount) if amount is not None else None,
            approval_reference=approval,
            fixture_base_url=fixture_base_url,
            fixture_egress_network=fixture_egress_network,
            backend=str(args.backend),
            timeout_seconds=timeout,
            run_id=run_id,
        )


def add_terminal_release_parser(
    commands: Any,
    *,
    handler: Callable[[argparse.Namespace], int],
) -> None:
    """Register one command that executes and scores a blinded release."""

    parser = commands.add_parser(
        "release-run",
        help="Run Claude Code on a blinded release and score every selected unit.",
        description=(
            "Execute one Claude Code forecast per case with local tools enabled, "
            "then score the complete selected unit set. The output is a local "
            "experiment, not an official benchmark publication."
        ),
    )
    parser.add_argument(
        "--forecast-release",
        type=Path,
        required=True,
        help="Validated outcome-blinded forecast-release.json.",
    )
    parser.add_argument(
        "--labels-release",
        type=Path,
        required=True,
        help="Separate labels-release.json, read only for host-side scoring.",
    )
    parser.add_argument(
        "--artifact-root",
        type=Path,
        required=True,
        help="Root holding all release packet, prompt, and document bytes.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Fresh private directory for run records, transcripts, and scores.",
    )
    parser.add_argument(
        "--model-key",
        required=True,
        help="Requested model identity recorded separately from the served model.",
    )
    parser.add_argument(
        "--image",
        required=True,
        help="Locally built Claude Code image pinned by its sha256 image ID.",
    )
    parser.add_argument(
        "--auth-profile",
        choices=(FIXTURE_NONE, PUBLISHED_API_KEY),
        default=FIXTURE_NONE,
        help=(
            "Fixture uses no provider credential; API-key mode requires "
            "spend authority."
        ),
    )
    parser.add_argument(
        "--max-budget-usd",
        type=float,
        help="Total provider charge ceiling; required for API-key mode.",
    )
    parser.add_argument(
        "--approval-reference",
        help="Existing owner approval reference for a paid run.",
    )
    parser.add_argument(
        "--fixture-base-url",
        help="Anthropic-compatible fixture endpoint for credential-free tests.",
    )
    parser.add_argument(
        "--fixture-egress-network",
        help="Existing container network hosting the fixture endpoint.",
    )
    parser.add_argument(
        "--backend",
        choices=(BACKEND_DOCKER, BACKEND_PODMAN),
        default=BACKEND_DOCKER,
    )
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--run-id", default="claude-code-release")
    parser.set_defaults(handler=handler)
