#!/usr/bin/env python3
"""Fail-closed helpers for the protected Terraform operator workflow."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any, cast

from legalforecast.contracts import (
    MANIFEST_RAW_SHA256_V1,
    PROVIDER_AUTHORITY_INFRA_IMPORT_RECEIPT_V1,
    PROVIDER_AUTHORITY_INFRA_IMPORT_REQUEST_V1,
    RAW_BYTES_RAW_SHA256_V1,
)

PROVIDER_AUTHORITY_TABLE = "legalforecastbench-official-eval-provider-authority"
OUTSIDE_AUTHORITY_CANARY_TABLE = (
    "legalforecastbench-official-labeling-authority-smoke-canary"
)
LABELING_ROLE = "legalforecastbench-official-labeling-authority"
EVAL_CELL_ROLE = "legalforecastbench-official-eval"
EVAL_FAN_IN_ROLE = f"{EVAL_CELL_ROLE}-fan-in"

PLAN_ADDRESSES: dict[str, frozenset[str]] = {
    "provider-authority": frozenset(
        {
            "aws_dynamodb_table.provider_authority",
            "aws_dynamodb_table.outside_authority_canary",
        }
    ),
    "official-labeling": frozenset(
        {"aws_iam_role.labeling", "aws_iam_role_policy.labeling"}
    ),
    "official-eval": frozenset(
        {
            "aws_iam_role.cell",
            "aws_iam_role.fan_in",
            "aws_iam_role_policy.cell_provider_authority",
            "aws_iam_role_policy.cell_storage",
            "aws_iam_role_policy.fan_in_storage",
            "aws_iam_role_policies_exclusive.cell",
            "aws_iam_role_policies_exclusive.fan_in",
            "aws_iam_role_policy_attachments_exclusive.cell",
            "aws_iam_role_policy_attachments_exclusive.fan_in",
        }
    ),
}
DATA_ADDRESSES: dict[str, frozenset[str]] = {
    "provider-authority": frozenset(),
    "official-labeling": frozenset(
        {
            "data.aws_iam_policy_document.labeling",
            "data.aws_iam_policy_document.labeling_trust",
        }
    ),
    "official-eval": frozenset(),
}

_EVAL_FIXED_IMPORT_IDS: dict[str, str] = {
    "aws_iam_role.cell": EVAL_CELL_ROLE,
    "aws_iam_role.fan_in": EVAL_FAN_IN_ROLE,
    "aws_iam_role_policy.cell_provider_authority": (
        f"{EVAL_CELL_ROLE}:official-eval-cell-exact-provider-authority"
    ),
    "aws_iam_role_policy.cell_storage": (
        f"{EVAL_CELL_ROLE}:official-eval-cell-storage"
    ),
    "aws_iam_role_policy.fan_in_storage": (
        f"{EVAL_FAN_IN_ROLE}:official-eval-fan-in-storage"
    ),
    "aws_iam_role_policies_exclusive.cell": EVAL_CELL_ROLE,
    "aws_iam_role_policies_exclusive.fan_in": EVAL_FAN_IN_ROLE,
    "aws_iam_role_policy_attachments_exclusive.cell": EVAL_CELL_ROLE,
    "aws_iam_role_policy_attachments_exclusive.fan_in": EVAL_FAN_IN_ROLE,
}

_SAFE_ACTIONS = (["no-op"], ["create"], ["update"])


def resolve_import_id(
    module: str,
    address: str,
    protected_values: Mapping[str, str],
) -> str:
    """Resolve one reviewed address to its internally supplied import ID."""

    if module == "provider-authority" and address == (
        "aws_dynamodb_table.provider_authority"
    ):
        return PROVIDER_AUTHORITY_TABLE
    if module == "provider-authority" and address == (
        "aws_dynamodb_table.outside_authority_canary"
    ):
        return OUTSIDE_AUTHORITY_CANARY_TABLE
    if module == "official-labeling":
        if address == "aws_iam_role.labeling":
            return LABELING_ROLE
        if address == "aws_iam_role_policy.labeling":
            return f"{LABELING_ROLE}:official-labeling-exact-provider-authority"
    if module == "official-eval":
        if address in _EVAL_FIXED_IMPORT_IDS:
            return _EVAL_FIXED_IMPORT_IDS[address]
    raise ValueError("module/address is outside the reviewed import allowlist")


def import_authorization_sha256(
    *,
    release_sha: str,
    module: str,
    address: str,
    import_id_sha256: str,
    operator_role_identity_sha256: str,
    state_backend_identity_sha256: str,
    terraform_input_identity_sha256: str,
) -> str:
    """Commit an import approval to the exact release and hidden resource ID."""

    payload = {
        "address": address,
        "import_id_sha256": import_id_sha256,
        "module": module,
        "operator_role_identity_sha256": operator_role_identity_sha256,
        "release_sha": release_sha,
        "schema_version": str(PROVIDER_AUTHORITY_INFRA_IMPORT_REQUEST_V1),
        "state_backend_identity_sha256": state_backend_identity_sha256,
        "terraform_input_identity_sha256": terraform_input_identity_sha256,
    }
    return str(
        MANIFEST_RAW_SHA256_V1.commit(
            payload,
            domain=PROVIDER_AUTHORITY_INFRA_IMPORT_REQUEST_V1,
        ).digest
    )


def _module_resources(module: Mapping[str, Any]) -> Iterator[Mapping[str, Any]]:
    resources = module.get("resources", [])
    if not isinstance(resources, list):
        raise ValueError("Terraform state resources collection is malformed")
    for resource in cast(list[object], resources):
        if not isinstance(resource, dict):
            raise ValueError("Terraform state contains a malformed resource")
        yield cast(dict[str, Any], resource)
    children = module.get("child_modules", [])
    if not isinstance(children, list):
        raise ValueError("Terraform state child_modules collection is malformed")
    for child in cast(list[object], children):
        if not isinstance(child, dict):
            raise ValueError("Terraform state contains a malformed child module")
        yield from _module_resources(cast(dict[str, Any], child))


def _state_resources(state: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    if state.get("format_version") != "1.0":
        raise ValueError("Terraform state JSON has an unsupported format version")
    values = state.get("values")
    if values is None:
        return []
    if not isinstance(values, dict):
        raise ValueError("Terraform state JSON has an invalid values tree")
    typed_values = cast(dict[str, Any], values)
    root_module = typed_values.get("root_module")
    if not isinstance(root_module, dict):
        raise ValueError("Terraform state JSON has an invalid values tree")
    return list(_module_resources(cast(dict[str, Any], root_module)))


def classify_state_binding(
    state: Mapping[str, Any], address: str, import_id: str
) -> str:
    """Classify an exact remote-state binding without exposing its raw ID."""

    target_type, separator, _ = address.partition(".")
    if not separator or re.fullmatch(r"[a-z0-9_]+", target_type) is None:
        raise ValueError("reviewed import address has an invalid resource type")
    resources = _state_resources(state)
    address_matches = [item for item in resources if item.get("address") == address]
    identity_matches: list[Mapping[str, Any]] = []
    for item in resources:
        values = item.get("values")
        if (
            not isinstance(values, dict)
            or cast(dict[str, Any], values).get("id") != import_id
        ):
            continue
        resource_type = item.get("type")
        if (
            not isinstance(resource_type, str)
            or re.fullmatch(r"[a-z0-9_]+", resource_type) is None
        ):
            raise ValueError("Terraform state contains a malformed resource type")
        if item.get("mode") == "managed" and resource_type == target_type:
            identity_matches.append(item)
    if not address_matches:
        if identity_matches:
            raise ValueError(
                "reviewed import identity is already bound to another address"
            )
        return "absent"
    if len(address_matches) != 1:
        raise ValueError(
            "reviewed import address appears more than once in remote state"
        )
    values = address_matches[0].get("values")
    current_id = (
        cast(dict[str, Any], values).get("id") if isinstance(values, dict) else None
    )
    if current_id != import_id:
        raise ValueError("remote-state identity does not match the reviewed import")
    if len(identity_matches) != 1:
        raise ValueError("reviewed import identity is bound to another address")
    return "already_present"


def _canonical_members(value: object) -> set[str]:
    if not isinstance(value, list):
        raise ValueError("authoritative collection has an invalid plan shape")
    return {
        json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        for item in cast(list[object], value)
    }


def _reject_authoritative_contraction(
    address: str, before: object, after: object
) -> None:
    authoritative = address.startswith(
        (
            "aws_iam_role_policies_exclusive.",
            "aws_iam_role_policy_attachments_exclusive.",
        )
    )
    if not authoritative:
        return
    if not isinstance(before, dict) or not isinstance(after, dict):
        raise ValueError("authoritative update has an invalid before/after shape")
    before_values = cast(dict[str, Any], before)
    after_values = cast(dict[str, Any], after)
    if address.startswith("aws_iam_role_policies_exclusive."):
        old = _canonical_members(before_values.get("policy_names"))
        new = _canonical_members(after_values.get("policy_names"))
    elif address.startswith("aws_iam_role_policy_attachments_exclusive."):
        old = _canonical_members(before_values.get("policy_arns"))
        new = _canonical_members(after_values.get("policy_arns"))
    else:
        raise AssertionError("authoritative resource classifier is inconsistent")
    if not old.issubset(new):
        raise ValueError("Terraform plan contracts an authoritative resource")


def validate_plan(module: str, plan: Mapping[str, Any]) -> None:
    """Reject unreviewed addresses and every destructive/future action vector."""

    allowlist = PLAN_ADDRESSES.get(module)
    data_allowlist = DATA_ADDRESSES.get(module)
    if allowlist is None or data_allowlist is None:
        raise ValueError("Terraform module is outside the reviewed plan allowlist")
    if plan.get("format_version") != "1.2":
        raise ValueError("Terraform plan JSON has an unsupported format version")
    changes = plan.get("resource_changes", [])
    if not isinstance(changes, list):
        raise ValueError("Terraform plan has an invalid resource_changes field")
    for raw_item in cast(list[object], changes):
        if not isinstance(raw_item, dict):
            raise ValueError("Terraform plan contains a malformed resource change")
        item = cast(dict[str, Any], raw_item)
        mode = item.get("mode")
        if mode == "data":
            address = item.get("address")
            change = item.get("change")
            actions = (
                cast(dict[str, Any], change).get("actions")
                if isinstance(change, dict)
                else None
            )
            if address not in data_allowlist or actions != ["read"]:
                raise ValueError("Terraform plan contains an unreviewed data read")
            continue
        if mode != "managed":
            raise ValueError("Terraform plan contains an unknown resource mode")
        address = item.get("address")
        change = item.get("change")
        actions = (
            cast(dict[str, Any], change).get("actions")
            if isinstance(change, dict)
            else None
        )
        if address not in allowlist:
            raise ValueError("Terraform plan contains an unreviewed managed address")
        if actions not in _SAFE_ACTIONS:
            raise ValueError("Terraform plan contains a destructive action vector")
        if item.get("action_reason") in {
            "delete_before_create",
            "create_before_destroy",
        }:
            raise ValueError("Terraform plan contains a replacement action")
        if actions == ["update"] and isinstance(address, str):
            _reject_authoritative_contraction(
                address,
                cast(dict[str, Any], change).get("before"),
                cast(dict[str, Any], change).get("after"),
            )


def public_import_receipt(
    *,
    module: str,
    release_sha: str,
    address: str,
    import_id_sha256: str,
    authorization_sha256: str,
    result: str,
    before_state_sha256: str,
    after_state_sha256: str,
    operator_role_identity_sha256: str,
    state_backend_identity_sha256: str,
    terraform_input_identity_sha256: str,
) -> dict[str, str]:
    """Build the public-safe import receipt; raw resource IDs are never accepted."""

    return {
        "schema_version": str(PROVIDER_AUTHORITY_INFRA_IMPORT_RECEIPT_V1),
        "module": module,
        "release_sha": release_sha,
        "import_address": address,
        "import_id_sha256": import_id_sha256,
        "import_authorization_sha256": authorization_sha256,
        "result": result,
        "before_state_sha256": before_state_sha256,
        "after_state_sha256": after_state_sha256,
        "operator_role_identity_sha256": operator_role_identity_sha256,
        "state_backend_identity_sha256": state_backend_identity_sha256,
        "terraform_input_identity_sha256": terraform_input_identity_sha256,
    }


def _require_sha256(value: str, name: str) -> None:
    if re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError(f"{name} must be one lowercase SHA-256 digest")


def _append_lines(path: Path, values: Mapping[str, str]) -> None:
    with path.open("a", encoding="utf-8") as stream:
        for name, value in values.items():
            if "\n" in value or "\r" in value:
                raise ValueError("workflow environment values must be single-line")
            stream.write(f"{name}={value}\n")


def _resolve_import_command(args: argparse.Namespace) -> None:
    protected = {
        "packet_bucket_name": os.environ.get("TF_VAR_packet_bucket_name", ""),
        "results_bucket_name": os.environ.get("TF_VAR_results_bucket_name", ""),
    }
    import_id = resolve_import_id(args.module, args.address, protected)
    actual_id_sha256 = str(
        RAW_BYTES_RAW_SHA256_V1.commit(
            import_id.encode("utf-8"),
            domain=PROVIDER_AUTHORITY_INFRA_IMPORT_REQUEST_V1,
        ).digest
    )
    _require_sha256(args.import_id_sha256, "import_id_sha256")
    _require_sha256(args.authorization_sha256, "import_authorization_sha256")
    if actual_id_sha256 != args.import_id_sha256:
        raise ValueError("protected import ID does not match the reviewed commitment")
    identity_bindings = {
        "operator_role_identity_sha256": os.environ.get(
            "OPERATOR_ROLE_IDENTITY_SHA256", ""
        ),
        "state_backend_identity_sha256": os.environ.get(
            "STATE_BACKEND_IDENTITY_SHA256", ""
        ),
        "terraform_input_identity_sha256": os.environ.get(
            "TERRAFORM_INPUT_IDENTITY_SHA256", ""
        ),
    }
    expected_bindings = {
        "operator_role_identity_sha256": args.operator_role_identity_sha256,
        "state_backend_identity_sha256": args.state_backend_identity_sha256,
        "terraform_input_identity_sha256": args.terraform_input_identity_sha256,
    }
    for name, expected in expected_bindings.items():
        _require_sha256(expected, name)
        if identity_bindings[name] != expected:
            raise ValueError(f"{name} does not match the protected configuration")
    expected_authorization = import_authorization_sha256(
        release_sha=args.release_sha,
        module=args.module,
        address=args.address,
        import_id_sha256=actual_id_sha256,
        **identity_bindings,
    )
    if expected_authorization != args.authorization_sha256:
        raise ValueError("import authorization does not bind the exact request")
    if "\n" in import_id or "\r" in import_id:
        raise ValueError("protected import ID must be single-line")
    file_descriptor = os.open(
        args.import_id_file,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    with os.fdopen(file_descriptor, "w", encoding="utf-8") as stream:
        stream.write(f"{import_id}\n")


def _state_binding_command(args: argparse.Namespace) -> None:
    import_id = os.environ.get("LFB_IMPORT_ID", "")
    if not import_id:
        raise ValueError("protected import ID is unavailable")
    with args.state_json.open(encoding="utf-8") as stream:
        state = cast(object, json.load(stream))
    if not isinstance(state, dict):
        raise ValueError("Terraform state JSON must be an object")
    result = classify_state_binding(
        cast(dict[str, Any], state), args.address, import_id
    )
    if args.require_present and result != "already_present":
        raise ValueError("reviewed import binding is absent after import")
    _append_lines(args.github_output, {"binding": result})


def _validate_plan_command(args: argparse.Namespace) -> None:
    with args.plan_json.open(encoding="utf-8") as stream:
        plan = cast(object, json.load(stream))
    if not isinstance(plan, dict):
        raise ValueError("Terraform plan JSON must be an object")
    validate_plan(args.module, cast(dict[str, Any], plan))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    resolve = commands.add_parser("resolve-import")
    resolve.add_argument("--module", required=True)
    resolve.add_argument("--address", required=True)
    resolve.add_argument("--release-sha", required=True)
    resolve.add_argument("--import-id-sha256", required=True)
    resolve.add_argument("--authorization-sha256", required=True)
    resolve.add_argument("--operator-role-identity-sha256", required=True)
    resolve.add_argument("--state-backend-identity-sha256", required=True)
    resolve.add_argument("--terraform-input-identity-sha256", required=True)
    resolve.add_argument("--import-id-file", required=True, type=Path)
    resolve.set_defaults(handler=_resolve_import_command)

    state = commands.add_parser("state-binding")
    state.add_argument("--state-json", required=True, type=Path)
    state.add_argument("--address", required=True)
    state.add_argument("--github-output", required=True, type=Path)
    state.add_argument("--require-present", action="store_true")
    state.set_defaults(handler=_state_binding_command)

    plan = commands.add_parser("validate-plan")
    plan.add_argument("--module", required=True)
    plan.add_argument("--plan-json", required=True, type=Path)
    plan.set_defaults(handler=_validate_plan_command)
    return parser


def main() -> int:
    """Run one workflow contract operation."""

    args = _parser().parse_args()
    try:
        args.handler(args)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"official infrastructure contract rejected: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
