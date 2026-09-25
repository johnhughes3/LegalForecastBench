"""Arguments for a local, release-backed coding-terminal experiment."""

from __future__ import annotations

import argparse
import math
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from legalforecast.multiharness.auth_profiles import (
    FIXTURE_NONE,
    PUBLISHED_API_KEY,
)
from legalforecast.multiharness.container_harness.images import (
    require_digest_pinned_image,
)
from legalforecast.multiharness.container_harness.model_gateway_plan import (
    MODEL_GATEWAY_PROTECTED_UPSTREAM_BASE_URL,
)
from legalforecast.multiharness.sandbox import BACKEND_DOCKER


@dataclass(frozen=True, slots=True)
class TerminalReleaseOptions:
    """Validated, non-secret command input before any release or key access."""

    forecast_release: Path
    labels_release: Path | None
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
    paid_config_path: Path | None = None
    model_registry_path: Path | None = None
    gateway_upstream_base_url: str | None = None
    gateway_image_digest: str | None = None

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
        approval = getattr(args, "approval_reference", None)
        fixture_base_url = getattr(args, "fixture_base_url", None)
        fixture_egress_network = getattr(args, "fixture_egress_network", None)
        paid_config_path_arg = getattr(args, "paid_config", None)
        model_registry_path_arg = getattr(args, "model_registry", None)
        gateway_upstream_base_url = getattr(args, "gateway_upstream_base_url", None)
        gateway_image_arg = getattr(args, "gateway_image", None)
        gateway_image_digest = (
            str(gateway_image_arg) if gateway_image_arg is not None else None
        )
        paid_config_path = (
            Path(paid_config_path_arg) if paid_config_path_arg is not None else None
        )
        model_registry_path = (
            Path(model_registry_path_arg)
            if model_registry_path_arg is not None
            else None
        )
        if profile == FIXTURE_NONE:
            if (
                amount is not None
                or approval is not None
                or paid_config_path is not None
                or model_registry_path is not None
                or gateway_upstream_base_url is not None
                or gateway_image_digest is not None
            ):
                raise ValueError("fixture-none cannot carry paid-run authority")
            if not isinstance(fixture_base_url, str) or not fixture_base_url.strip():
                raise ValueError("fixture-none requires --fixture-base-url")
            fixture_url = urlsplit(fixture_base_url)
            if (
                fixture_url.scheme not in {"http", "https"}
                or fixture_url.hostname is None
            ):
                raise ValueError("--fixture-base-url must be an HTTP(S) endpoint")
            if fixture_url.scheme == "http" and not fixture_egress_network:
                raise ValueError("an HTTP fixture requires --fixture-egress-network")
        elif profile == PUBLISHED_API_KEY:
            if (
                fixture_base_url is not None
                or fixture_egress_network is not None
                or approval is not None
            ):
                raise ValueError("published-api-key cannot use fixture routing")
            if (
                not isinstance(amount, float | int)
                or not math.isfinite(amount)
                or amount <= 0
            ):
                raise ValueError("published-api-key requires a positive budget")
            if paid_config_path is None or model_registry_path is None:
                raise ValueError(
                    "published-api-key requires --paid-config and --model-registry"
                )
            if gateway_image_digest is None:
                raise ValueError("published-api-key requires --gateway-image")
            require_digest_pinned_image(gateway_image_digest, "gateway-image")
            if gateway_upstream_base_url is None:
                gateway_upstream_base_url = MODEL_GATEWAY_PROTECTED_UPSTREAM_BASE_URL
            if not isinstance(gateway_upstream_base_url, str):
                raise ValueError("--gateway-upstream-base-url must be HTTPS")
            gateway_url = urlsplit(gateway_upstream_base_url)
            if (
                gateway_url.scheme != "https"
                or gateway_url.hostname is None
                or gateway_url.username is not None
                or gateway_url.password is not None
                or gateway_url.path not in {"", "/"}
                or gateway_url.query
                or gateway_url.fragment
            ):
                raise ValueError("--gateway-upstream-base-url must be an HTTPS origin")
            if (
                gateway_url.hostname != "api.anthropic.com"
                or (gateway_url.port or 443) != 443
            ):
                raise ValueError(
                    "protected paid gateway is pinned to api.anthropic.com:443"
                )
            gateway_upstream_base_url = MODEL_GATEWAY_PROTECTED_UPSTREAM_BASE_URL
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
            labels_release=(
                Path(args.labels_release)
                if getattr(args, "labels_release", None) is not None
                else None
            ),
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
            paid_config_path=paid_config_path,
            model_registry_path=model_registry_path,
            gateway_upstream_base_url=gateway_upstream_base_url,
            gateway_image_digest=gateway_image_digest,
        )


def add_terminal_release_parser(
    commands: Any,
    *,
    handler: Callable[[argparse.Namespace], int],
    execute_handler: Callable[[argparse.Namespace], int],
    score_handler: Callable[[argparse.Namespace], int],
) -> None:
    """Register release execution, scoring, and convenience commands."""

    parser = commands.add_parser(
        "release-run",
        help="Run Claude Code on a blinded release and score every selected unit.",
        description=(
            "Execute one Claude Code forecast per case with local tools enabled, "
            "then score the complete selected unit set. The output is a local "
            "experiment, not an official benchmark publication."
        ),
    )
    _add_release_execution_arguments(parser, include_labels=True)
    parser.set_defaults(handler=handler)

    execute = commands.add_parser(
        "release-execute",
        help="Execute Claude Code on a blinded release without loading labels.",
        description=(
            "Execute one Claude Code forecast per case and save the private run "
            "package. This command never accepts or reads labels."
        ),
    )
    _add_release_execution_arguments(execute, include_labels=False)
    execute.set_defaults(handler=execute_handler)

    score = commands.add_parser(
        "release-score",
        help="Score a saved scoreless terminal-release package.",
        description=(
            "Load a saved release-execute package and score it with labels on "
            "the host. No model or container is invoked."
        ),
    )
    score.add_argument("--run-dir", type=Path, required=True)
    score.add_argument("--forecast-release", type=Path, required=True)
    score.add_argument("--labels-release", type=Path, required=True)
    score.add_argument("--artifact-root", type=Path, required=True)
    score.add_argument(
        "--output",
        type=Path,
        help="Score report destination; defaults to RUN_DIR/scores.json.",
    )
    score.set_defaults(handler=score_handler)


def _add_release_execution_arguments(
    parser: argparse.ArgumentParser,
    *,
    include_labels: bool,
) -> None:
    """Add common execution arguments for release-run and release-execute."""

    parser.add_argument(
        "--forecast-release",
        type=Path,
        required=True,
        help="Validated outcome-blinded forecast-release.json.",
    )
    if include_labels:
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
        help="Deprecated paid authority input; protected runs use --paid-config.",
    )
    parser.add_argument(
        "--paid-config",
        type=Path,
        help="Protected workflow paid gateway descriptor (API-key mode only).",
    )
    parser.add_argument(
        "--model-registry",
        type=Path,
        help="Frozen model registry matching --paid-config (API-key mode only).",
    )
    parser.add_argument(
        "--gateway-upstream-base-url",
        help="HTTPS provider origin admitted by the protected gateway.",
    )
    parser.add_argument(
        "--gateway-image",
        help="Pinned digest for the protected model-gateway runtime image.",
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
        choices=(BACKEND_DOCKER,),
        default=BACKEND_DOCKER,
    )
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--run-id", default="claude-code-release")
