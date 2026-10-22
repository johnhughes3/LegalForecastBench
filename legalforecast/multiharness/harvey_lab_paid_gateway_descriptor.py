"""Issue the protected paid descriptor for clean-native Harvey LAB.

This issuer consumes the authenticated LAB projection rather than a forecast
release. It performs no AWS or provider request; the protected environment is
checked only so its output cannot be minted as a local paid-launch input.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from legalforecast.contracts import ARTIFACT_RAW_SHA256_V1, PUBLIC_RUN_IDENTITY_V1
from legalforecast.multiharness.claude_code import ClaudeCodeCliAdapterError
from legalforecast.multiharness.claude_code_harvey_lab_guards import (
    require_authentic_prepared_private_material,
)
from legalforecast.multiharness.container_harness.model_gateway_paid import (
    CLAUDE_CODE_HARVEY_LAB_HARNESS_ID,
)
from legalforecast.multiharness.harvey_lab.evaluation_contract import (
    harvey_lab_private_material_sha256,
)
from legalforecast.multiharness.harvey_lab_projection import (
    ISSUE_196_LAB_TASK_ID,
    HarveyLabPin,
    harvey_lab_v1_1_pin,
    verify_harvey_lab_projection,
    verify_harvey_lab_source_pin,
)
from legalforecast.multiharness.paid_gateway_descriptor import (
    PAID_GATEWAY_MAX_REQUESTS_PER_CASE,
    ProtectedPaidGatewayDescriptor,
    load_paid_gateway_issuance_context,
    write_paid_gateway_descriptor,
)
from legalforecast.multiharness.protected_terminal_paid import (
    ProtectedTerminalPaidError,
)

HARVEY_LAB_CYCLE_ID: Final[str] = "harvey-lab-v1.1.0"


@dataclass(frozen=True, slots=True)
class HarveyLabPaidInputIdentity:
    """Authenticated clean-native inputs bound into a paid descriptor."""

    projection_manifest_sha256: str
    private_material_sha256: str
    task_id: str
    source_commit: str
    source_tree: str


def authenticate_harvey_lab_paid_inputs(
    *,
    source_root: Path,
    projection_root: Path,
    evaluator_private_root: Path,
    pin: HarveyLabPin | None = None,
) -> HarveyLabPaidInputIdentity:
    """Reproduce and authenticate every LAB input before paid authority use."""

    selected_pin = pin or harvey_lab_v1_1_pin()
    try:
        verify_harvey_lab_source_pin(source_root, selected_pin)
        manifest = verify_harvey_lab_projection(projection_root)
        if manifest.pin != selected_pin:
            raise ProtectedTerminalPaidError(
                "Harvey LAB projection does not match the selected source pin"
            )
        if (
            len(manifest.tasks) != 1
            or manifest.tasks[0].lab_task_id != ISSUE_196_LAB_TASK_ID
        ):
            raise ProtectedTerminalPaidError(
                "Harvey LAB descriptor requires exactly the issue-196 task"
            )
        require_authentic_prepared_private_material(
            source_root=source_root,
            evaluator_private_root=evaluator_private_root,
            pin=selected_pin,
            lab_task_id=ISSUE_196_LAB_TASK_ID,
        )
        private_digest = harvey_lab_private_material_sha256(
            evaluator_private_root
        ).removeprefix("sha256:")
    except ProtectedTerminalPaidError:
        raise
    except (ClaudeCodeCliAdapterError, OSError, ValueError) as exc:
        raise ProtectedTerminalPaidError(
            f"Harvey LAB descriptor inputs are invalid: {exc}"
        ) from exc
    return HarveyLabPaidInputIdentity(
        projection_manifest_sha256=manifest.manifest_sha256,
        private_material_sha256=private_digest,
        task_id=ISSUE_196_LAB_TASK_ID,
        source_commit=selected_pin.commit,
        source_tree=selected_pin.tree,
    )


def issue_harvey_lab_paid_gateway_descriptor(
    *,
    source_root: Path,
    projection_root: Path,
    evaluator_private_root: Path,
    model_registry_path: Path,
    model_key: str,
    ceiling_microusd: int,
    account: str,
    environment: Mapping[str, str] | None = None,
) -> ProtectedPaidGatewayDescriptor:
    """Bind one ceiling/journal identity to authentic LAB inputs and pricing."""

    identity = authenticate_harvey_lab_paid_inputs(
        source_root=source_root,
        projection_root=projection_root,
        evaluator_private_root=evaluator_private_root,
    )

    context = load_paid_gateway_issuance_context(
        model_registry_path=model_registry_path,
        model_key=model_key,
        ceiling_microusd=ceiling_microusd,
        account=account,
        harness_id=CLAUDE_CODE_HARVEY_LAB_HARNESS_ID,
        environment=environment,
    )
    run_identity = str(
        ARTIFACT_RAW_SHA256_V1.commit(
            {
                "account": context.account,
                "ceiling_microusd": context.ceiling_microusd,
                "cycle_id": HARVEY_LAB_CYCLE_ID,
                "harness_id": CLAUDE_CODE_HARVEY_LAB_HARNESS_ID,
                "model_key": context.model_key,
                "model_registry_entry_sha256": (context.model_registry_entry_sha256),
                "model_registry_sha256": context.model_registry_sha256,
                "private_material_sha256": identity.private_material_sha256,
                "projection_manifest_sha256": (identity.projection_manifest_sha256),
                "source_commit": identity.source_commit,
                "source_tree": identity.source_tree,
                "task_id": identity.task_id,
            },
            domain=PUBLIC_RUN_IDENTITY_V1,
        ).digest
    )
    authority_identity = str(
        ARTIFACT_RAW_SHA256_V1.commit(
            {
                "account": context.account,
                "provider": context.registry_entry.provider,
                "run_identity_sha256": run_identity,
            },
            domain=PUBLIC_RUN_IDENTITY_V1,
        ).digest
    )
    return ProtectedPaidGatewayDescriptor(
        cycle_id=HARVEY_LAB_CYCLE_ID,
        account=context.account,
        model_key=context.model_key,
        ceiling_microusd=context.ceiling_microusd,
        max_requests=PAID_GATEWAY_MAX_REQUESTS_PER_CASE,
        authority_identity_sha256=authority_identity,
        reservation_ledger_sha256=run_identity,
        provider_authority_table=context.authority_table,
        provider_authority_region=context.authority_region,
        provider_authority_resource_identity_sha256=(
            context.authority_resource_identity_sha256
        ),
        model_registry_sha256=context.model_registry_sha256,
        model_registry_entry_sha256=context.model_registry_entry_sha256,
        harness_id=CLAUDE_CODE_HARVEY_LAB_HARNESS_ID,
        harvey_lab_projection_manifest_sha256=(identity.projection_manifest_sha256),
        harvey_lab_private_material_sha256=identity.private_material_sha256,
        harvey_lab_task_id=identity.task_id,
        harvey_lab_source_commit=identity.source_commit,
        harvey_lab_source_tree=identity.source_tree,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Issue a protected clean-native Harvey LAB paid descriptor from "
            "authenticated prepared inputs. This command never contacts AWS "
            "or a model provider."
        )
    )
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--projection-dir", type=Path, required=True)
    parser.add_argument("--evaluator-private-dir", type=Path, required=True)
    parser.add_argument("--model-registry", type=Path, required=True)
    parser.add_argument("--model-key", required=True)
    parser.add_argument("--ceiling-microusd", type=int, required=True)
    parser.add_argument("--account", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Issue one create-only descriptor from the protected command line."""

    args = _build_parser().parse_args(argv)
    descriptor = issue_harvey_lab_paid_gateway_descriptor(
        source_root=args.source_root,
        projection_root=args.projection_dir,
        evaluator_private_root=args.evaluator_private_dir,
        model_registry_path=args.model_registry,
        model_key=args.model_key,
        ceiling_microusd=args.ceiling_microusd,
        account=args.account,
    )
    write_paid_gateway_descriptor(args.output, descriptor)
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised by the workflow
    raise SystemExit(main())


__all__ = [
    "HARVEY_LAB_CYCLE_ID",
    "HarveyLabPaidInputIdentity",
    "authenticate_harvey_lab_paid_inputs",
    "issue_harvey_lab_paid_gateway_descriptor",
]
