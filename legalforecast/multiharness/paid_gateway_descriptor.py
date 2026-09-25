"""Issue the protected paid gateway descriptor for a locked terminal run.

The descriptor is an execution input, not an approval document.  It is issued
only from the authenticated public release inputs and the protected GitHub
Actions environment.  In particular, callers cannot provide the authority
hashes, request bound, cycle identity, or registry hashes as free-form JSON.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from legalforecast.contracts import ARTIFACT_RAW_SHA256_V1, PUBLIC_RUN_IDENTITY_V1
from legalforecast.evals.model_registry import (
    load_model_registry_bytes,
    model_registry_entry_sha256,
    model_registry_sha256,
    require_official_registry_entries,
)
from legalforecast.immutable_io import read_single_link_file, write_file_create_only
from legalforecast.multiharness.container_harness.model_gateway_paid import (
    PAID_GATEWAY_CONFIG_SCHEMA,
    PAID_GATEWAY_WORKFLOW_MARKER,
    worst_case_request_microusd,
)
from legalforecast.multiharness.protected_terminal_paid import (
    ProtectedTerminalPaidError,
    protected_authority_environment,
)
from legalforecast.release import load_forecast_run_inputs
from legalforecast.runner import (
    RunValidationError,
    derive_run_identity_sha256,
    validate_executable_packets,
)

TERMINAL_HARNESS_ID: Final[str] = "claude-code-terminal"
TERMINAL_ABLATION: Final[str] = "none"
TERMINAL_REPEAT_INDEX: Final[int] = 1
# One sidecar is launched per case.  This fixed bound accommodates the
# reviewed Claude Code tool loop while keeping the gateway request envelope
# independent of the total release case count.
PAID_GATEWAY_MAX_REQUESTS_PER_CASE: Final[int] = 8


@dataclass(frozen=True, slots=True)
class ProtectedPaidGatewayDescriptor:
    """The complete descriptor accepted by the protected paid gateway."""

    cycle_id: str
    account: str
    model_key: str
    ceiling_microusd: int
    max_requests: int
    authority_identity_sha256: str
    reservation_ledger_sha256: str
    provider_authority_table: str
    provider_authority_region: str
    provider_authority_resource_identity_sha256: str
    model_registry_sha256: str
    model_registry_entry_sha256: str

    def to_record(self) -> dict[str, object]:
        """Return the exact loader-facing descriptor fields."""

        return {
            "schema_version": PAID_GATEWAY_CONFIG_SCHEMA,
            "workflow_marker": PAID_GATEWAY_WORKFLOW_MARKER,
            "cycle_id": self.cycle_id,
            "account": self.account,
            "model_key": self.model_key,
            "ceiling_microusd": self.ceiling_microusd,
            "max_requests": self.max_requests,
            "authority_identity_sha256": self.authority_identity_sha256,
            "reservation_ledger_sha256": self.reservation_ledger_sha256,
            "provider_authority_table": self.provider_authority_table,
            "provider_authority_region": self.provider_authority_region,
            "provider_authority_resource_identity_sha256": (
                self.provider_authority_resource_identity_sha256
            ),
            "model_registry_sha256": self.model_registry_sha256,
            "model_registry_entry_sha256": self.model_registry_entry_sha256,
            "stage": "official",
            "ablation": TERMINAL_ABLATION,
            "repeat_index": TERMINAL_REPEAT_INDEX,
        }


def issue_paid_gateway_descriptor(
    *,
    manifest_path: Path,
    forecast_path: Path,
    artifact_root: Path,
    model_registry_path: Path,
    model_key: str,
    ceiling_microusd: int,
    account: str,
    environment: Mapping[str, str] | None = None,
) -> ProtectedPaidGatewayDescriptor:
    """Derive one descriptor from locked inputs and protected workflow state.

    This function performs no AWS or provider operation.  The protected
    environment check is still required because a descriptor outside the
    official workflow must never become a paid gateway launch input.
    """

    if not model_key.strip():
        raise ProtectedTerminalPaidError("model_key must be nonempty")
    if not model_key.startswith("anthropic:"):
        raise ProtectedTerminalPaidError(
            "protected Claude Code terminal runs require an Anthropic model key"
        )
    if type(ceiling_microusd) is not int or ceiling_microusd <= 0:
        raise ProtectedTerminalPaidError("ceiling_microusd must be a positive integer")
    if not account.strip():
        raise ProtectedTerminalPaidError("account must be nonempty")

    authority_table, authority_region, authority_resource = (
        protected_authority_environment(environment)
    )
    try:
        run_inputs = load_forecast_run_inputs(
            manifest_path,
            forecast_path,
            artifact_root=artifact_root,
        )
        registry_bytes = read_single_link_file(
            model_registry_path,
            label="model registry",
        )
        registry = load_model_registry_bytes(registry_bytes)
        registry_sha256 = model_registry_sha256(registry_bytes)
        require_official_registry_entries(registry.entries)
        provider, separator, model_id = model_key.partition(":")
        if separator != ":" or provider != "anthropic" or not model_id:
            raise ProtectedTerminalPaidError(
                "model_key must use the canonical anthropic:model_id form"
            )
        try:
            entry = registry.get(provider, model_id)
        except KeyError as exc:
            raise ProtectedTerminalPaidError(
                f"model_key is absent from the locked model registry: {model_key}"
            ) from exc
        if entry.registry_key != model_key:
            raise ProtectedTerminalPaidError(
                "model_key does not match the canonical locked registry key"
            )
        if not entry.network_disabled or not entry.search_disabled:
            raise ProtectedTerminalPaidError(
                "locked Anthropic registry entry must disable network and search"
            )
        try:
            validate_executable_packets(run_inputs.execution)
        except (RunValidationError, ValueError) as exc:
            raise ProtectedTerminalPaidError(
                f"locked paid gateway eligibility validation failed: {exc}"
            ) from exc
    except ProtectedTerminalPaidError:
        raise
    except (OSError, ValueError) as exc:
        raise ProtectedTerminalPaidError(
            f"locked paid gateway inputs are invalid: {exc}"
        ) from exc

    release = run_inputs.execution.release
    manifest_case_count = len(run_inputs.manifest.selected_cases)
    if manifest_case_count != len(release.cases) or manifest_case_count <= 0:
        raise ProtectedTerminalPaidError(
            "locked manifest and forecast release must contain the same cases"
        )
    worst_case_microusd = worst_case_request_microusd(entry)
    if worst_case_microusd > ceiling_microusd:
        raise ProtectedTerminalPaidError(
            "paid gateway worst-case request cost exceeds the approved ceiling"
        )
    run_identity_sha256 = derive_run_identity_sha256(
        execution=run_inputs.execution,
        entry=entry,
        registry_sha256=registry_sha256,
        ceiling_microusd=ceiling_microusd,
        harness=TERMINAL_HARNESS_ID,
        ablation=TERMINAL_ABLATION,
        repeat_count=TERMINAL_REPEAT_INDEX,
        account=account,
        manifest_id=str(run_inputs.manifest.run_id),
        manifest_sha256=run_inputs.manifest_sha256,
    )
    authority_identity_sha256 = str(
        ARTIFACT_RAW_SHA256_V1.commit(
            {
                "account": account,
                "provider": entry.provider,
                "run_identity_sha256": run_identity_sha256,
            },
            domain=PUBLIC_RUN_IDENTITY_V1,
        ).digest
    )
    return ProtectedPaidGatewayDescriptor(
        cycle_id=release.release_id,
        account=account,
        model_key=entry.registry_key,
        ceiling_microusd=ceiling_microusd,
        max_requests=PAID_GATEWAY_MAX_REQUESTS_PER_CASE,
        authority_identity_sha256=authority_identity_sha256,
        reservation_ledger_sha256=run_identity_sha256,
        provider_authority_table=authority_table,
        provider_authority_region=authority_region,
        provider_authority_resource_identity_sha256=authority_resource,
        model_registry_sha256=registry_sha256,
        model_registry_entry_sha256=model_registry_entry_sha256(entry),
    )


def write_paid_gateway_descriptor(
    output_path: Path,
    descriptor: ProtectedPaidGatewayDescriptor,
) -> None:
    """Create the descriptor once with private file permissions."""

    payload = (
        json.dumps(
            descriptor.to_record(),
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
    write_file_create_only(output_path, payload, mode=0o400)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Derive the protected Claude Code paid gateway descriptor from "
            "locked release inputs. This command never contacts AWS or a provider."
        )
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--forecast", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--model-registry", type=Path, required=True)
    parser.add_argument("--model-key", required=True)
    parser.add_argument("--ceiling-microusd", type=int, required=True)
    parser.add_argument("--account", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Issue one descriptor from the protected workflow command line."""

    args = _build_parser().parse_args(argv)
    descriptor = issue_paid_gateway_descriptor(
        manifest_path=args.manifest,
        forecast_path=args.forecast,
        artifact_root=args.artifact_root,
        model_registry_path=args.model_registry,
        model_key=args.model_key,
        ceiling_microusd=args.ceiling_microusd,
        account=args.account,
    )
    write_paid_gateway_descriptor(args.output, descriptor)
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised by the workflow command
    raise SystemExit(main())


__all__ = [
    "PAID_GATEWAY_MAX_REQUESTS_PER_CASE",
    "ProtectedPaidGatewayDescriptor",
    "issue_paid_gateway_descriptor",
    "write_paid_gateway_descriptor",
]
