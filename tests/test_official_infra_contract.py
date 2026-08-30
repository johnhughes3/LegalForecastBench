from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
from pathlib import Path

import pytest
from legalforecast.contracts import (
    PROVIDER_AUTHORITY_INFRA_IMPORT_RECEIPT_V1,
    PROVIDER_AUTHORITY_INFRA_IMPORT_REQUEST_V1,
)

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "scripts/official_infra_contract.py"


def _load_contract():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location(
        "official_infra_contract", CONTRACT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _state(*resources: tuple[str, str]) -> dict[str, object]:
    return {
        "format_version": "1.0",
        "values": {
            "root_module": {
                "resources": [
                    {
                        "address": address,
                        "mode": "managed",
                        "type": address.split(".", maxsplit=1)[0],
                        "values": {"id": value},
                    }
                    for address, value in resources
                ]
            }
        },
    }


def test_import_ids_are_derived_from_one_closed_module_address_mapping() -> None:
    contract = _load_contract()
    protected: dict[str, str] = {}

    expected_eval_import_ids = {
        "aws_iam_role.cell": "legalforecastbench-official-eval",
        "aws_iam_role.prepare_inputs": (
            "legalforecastbench-official-eval-prepare-inputs"
        ),
        "aws_iam_role.fan_in": "legalforecastbench-official-eval-fan-in",
        "aws_iam_role_policy.cell_provider_authority": (
            "legalforecastbench-official-eval:"
            "official-eval-cell-exact-provider-authority"
        ),
        "aws_iam_role_policy.cell_storage": (
            "legalforecastbench-official-eval:official-eval-cell-storage"
        ),
        "aws_iam_role_policy.prepare_inputs_storage": (
            "legalforecastbench-official-eval-prepare-inputs:"
            "official-eval-prepare-inputs-storage"
        ),
        "aws_iam_role_policy.fan_in_storage": (
            "legalforecastbench-official-eval-fan-in:official-eval-fan-in-storage"
        ),
        "aws_iam_role_policies_exclusive.cell": "legalforecastbench-official-eval",
        "aws_iam_role_policies_exclusive.prepare_inputs": (
            "legalforecastbench-official-eval-prepare-inputs"
        ),
        "aws_iam_role_policies_exclusive.fan_in": (
            "legalforecastbench-official-eval-fan-in"
        ),
        "aws_iam_role_policy_attachments_exclusive.cell": (
            "legalforecastbench-official-eval"
        ),
        "aws_iam_role_policy_attachments_exclusive.prepare_inputs": (
            "legalforecastbench-official-eval-prepare-inputs"
        ),
        "aws_iam_role_policy_attachments_exclusive.fan_in": (
            "legalforecastbench-official-eval-fan-in"
        ),
    }

    assert (
        contract.resolve_import_id(
            "provider-authority", "aws_dynamodb_table.provider_authority", protected
        )
        == "legalforecastbench-official-eval-provider-authority"
    )
    assert (
        contract.resolve_import_id(
            "provider-authority",
            "aws_dynamodb_table.outside_authority_canary",
            protected,
        )
        == "legalforecastbench-official-labeling-authority-smoke-canary"
    )
    assert contract.resolve_import_id(
        "official-labeling", "aws_iam_role_policy.labeling", protected
    ) == (
        "legalforecastbench-official-labeling-authority:"
        "official-labeling-exact-provider-authority"
    )
    assert (
        contract.resolve_import_id(
            "official-eval", "aws_iam_role_policy.fan_in_storage", protected
        )
        == "legalforecastbench-official-eval-fan-in:official-eval-fan-in-storage"
    )
    resolved_eval_addresses = {
        address: contract.resolve_import_id("official-eval", address, protected)
        for address in contract.PLAN_ADDRESSES["official-eval"]
    }
    assert resolved_eval_addresses.keys() == contract.PLAN_ADDRESSES["official-eval"]
    assert resolved_eval_addresses == {
        **expected_eval_import_ids,
        "aws_iam_role.manifest_staging": (
            "legalforecastbench-official-eval-manifest-staging"
        ),
        "aws_iam_role_policy.manifest_staging_storage": (
            "legalforecastbench-official-eval-manifest-staging:"
            "official-eval-manifest-staging-storage"
        ),
        "aws_iam_role_policies_exclusive.manifest_staging": (
            "legalforecastbench-official-eval-manifest-staging"
        ),
        "aws_iam_role_policy_attachments_exclusive.manifest_staging": (
            "legalforecastbench-official-eval-manifest-staging"
        ),
    }

    for module, address in (
        ("../official-eval", "aws_iam_role.cell"),
        ("official-eval", "aws_s3_bucket.unrelated"),
        ("official-eval", "module.other.aws_s3_bucket.packet"),
        ("official-eval", "aws_iam_role_policy.cell_bedrock[0]"),
        ("official-eval", "aws_iam_role_policy.prepare_inputs"),
        ("provider-authority", "aws_s3_bucket.packet"),
    ):
        with pytest.raises(ValueError, match="reviewed import allowlist"):
            contract.resolve_import_id(module, address, protected)


def test_import_authorization_binds_release_module_address_and_hidden_id() -> None:
    contract = _load_contract()
    raw_id = "legalforecastbench-official-eval"
    id_sha256 = hashlib.sha256(raw_id.encode()).hexdigest()
    first = contract.import_authorization_sha256(
        release_sha="a" * 40,
        module="official-eval",
        address="aws_iam_role.cell",
        import_id_sha256=id_sha256,
        operator_role_identity_sha256="d" * 64,
        state_backend_identity_sha256="e" * 64,
        terraform_input_identity_sha256="f" * 64,
    )
    second = contract.import_authorization_sha256(
        release_sha="a" * 40,
        module="official-eval",
        address="aws_iam_role.fan_in",
        import_id_sha256=id_sha256,
        operator_role_identity_sha256="d" * 64,
        state_backend_identity_sha256="e" * 64,
        terraform_input_identity_sha256="f" * 64,
    )
    different_backend = contract.import_authorization_sha256(
        release_sha="a" * 40,
        module="official-eval",
        address="aws_iam_role.cell",
        import_id_sha256=id_sha256,
        operator_role_identity_sha256="d" * 64,
        state_backend_identity_sha256="0" * 64,
        terraform_input_identity_sha256="f" * 64,
    )

    assert first != second
    assert first != different_backend
    expected_payload = {
        "address": "aws_iam_role.cell",
        "import_id_sha256": id_sha256,
        "module": "official-eval",
        "operator_role_identity_sha256": "d" * 64,
        "release_sha": "a" * 40,
        "schema_version": str(PROVIDER_AUTHORITY_INFRA_IMPORT_REQUEST_V1),
        "state_backend_identity_sha256": "e" * 64,
        "terraform_input_identity_sha256": "f" * 64,
    }
    expected_authorization = hashlib.sha256(
        json.dumps(expected_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert first == expected_authorization
    assert raw_id not in json.dumps(
        contract.public_import_receipt(
            module="official-eval",
            release_sha="a" * 40,
            address="aws_iam_role.cell",
            import_id_sha256=id_sha256,
            authorization_sha256=first,
            result="imported",
            before_state_sha256="b" * 64,
            after_state_sha256="c" * 64,
            operator_role_identity_sha256="d" * 64,
            state_backend_identity_sha256="e" * 64,
            terraform_input_identity_sha256="f" * 64,
        )
    )
    assert contract.public_import_receipt(
        module="official-eval",
        release_sha="a" * 40,
        address="aws_iam_role.cell",
        import_id_sha256=id_sha256,
        authorization_sha256=first,
        result="imported",
        before_state_sha256="b" * 64,
        after_state_sha256="c" * 64,
        operator_role_identity_sha256="d" * 64,
        state_backend_identity_sha256="e" * 64,
        terraform_input_identity_sha256="f" * 64,
    )["schema_version"] == str(PROVIDER_AUTHORITY_INFRA_IMPORT_RECEIPT_V1)


def test_resolve_import_cli_uses_mode_0600_file_not_job_environment(
    tmp_path: Path,
) -> None:
    contract = _load_contract()
    raw_id = "legalforecastbench-official-eval"
    id_sha256 = hashlib.sha256(raw_id.encode()).hexdigest()
    identities = {
        "operator_role_identity_sha256": "d" * 64,
        "state_backend_identity_sha256": "e" * 64,
        "terraform_input_identity_sha256": "f" * 64,
    }
    authorization = contract.import_authorization_sha256(
        release_sha="a" * 40,
        module="official-eval",
        address="aws_iam_role.cell",
        import_id_sha256=id_sha256,
        **identities,
    )
    import_id_file = tmp_path / "protected-import-id"
    result = subprocess.run(
        [
            str(CONTRACT_PATH),
            "resolve-import",
            "--module",
            "official-eval",
            "--address",
            "aws_iam_role.cell",
            "--release-sha",
            "a" * 40,
            "--import-id-sha256",
            id_sha256,
            "--authorization-sha256",
            authorization,
            "--operator-role-identity-sha256",
            identities["operator_role_identity_sha256"],
            "--state-backend-identity-sha256",
            identities["state_backend_identity_sha256"],
            "--terraform-input-identity-sha256",
            identities["terraform_input_identity_sha256"],
            "--import-id-file",
            str(import_id_file),
        ],
        check=False,
        capture_output=True,
        env={
            **os.environ,
            "OPERATOR_ROLE_IDENTITY_SHA256": identities[
                "operator_role_identity_sha256"
            ],
            "STATE_BACKEND_IDENTITY_SHA256": identities[
                "state_backend_identity_sha256"
            ],
            "TERRAFORM_INPUT_IDENTITY_SHA256": identities[
                "terraform_input_identity_sha256"
            ],
        },
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert import_id_file.read_text(encoding="utf-8") == f"{raw_id}\n"
    assert import_id_file.stat().st_mode & 0o777 == 0o600


def test_state_binding_is_idempotent_and_rejects_wrong_or_duplicate_identity() -> None:
    contract = _load_contract()
    address = "aws_iam_role.cell"
    import_id = "legalforecastbench-official-eval"

    assert contract.classify_state_binding(_state(), address, import_id) == "absent"
    assert (
        contract.classify_state_binding({"format_version": "1.0"}, address, import_id)
        == "absent"
    )
    assert (
        contract.classify_state_binding(
            _state((address, import_id)), address, import_id
        )
        == "already_present"
    )
    with pytest.raises(ValueError, match="does not match"):
        contract.classify_state_binding(_state((address, "wrong")), address, import_id)
    with pytest.raises(ValueError, match="another address"):
        contract.classify_state_binding(
            _state(("aws_iam_role.fan_in", import_id)), address, import_id
        )
    with pytest.raises(ValueError, match="format version"):
        contract.classify_state_binding({}, address, import_id)
    for malformed in (
        {
            "format_version": "1.0",
            "values": {"root_module": {"resources": "corrupt"}},
        },
        {
            "format_version": "1.0",
            "values": {"root_module": {"resources": ["corrupt"]}},
        },
        {
            "format_version": "1.0",
            "values": {"root_module": {"child_modules": "corrupt"}},
        },
        {
            "format_version": "1.0",
            "values": {
                "root_module": {
                    "resources": [
                        {
                            "address": address,
                            "mode": "managed",
                            "values": {"id": import_id},
                        }
                    ]
                }
            },
        },
    ):
        with pytest.raises(ValueError, match="malformed"):
            contract.classify_state_binding(malformed, address, import_id)


def test_state_binding_allows_reviewed_resource_types_to_share_import_id() -> None:
    contract = _load_contract()
    role_id = "legalforecastbench-official-eval"
    role_state = _state(
        ("aws_iam_role.cell", role_id),
        ("aws_iam_role_policies_exclusive.cell", role_id),
        ("aws_iam_role_policy_attachments_exclusive.cell", role_id),
    )
    for address in (
        "aws_iam_role.cell",
        "aws_iam_role_policies_exclusive.cell",
        "aws_iam_role_policy_attachments_exclusive.cell",
    ):
        assert (
            contract.classify_state_binding(role_state, address, role_id)
            == "already_present"
        )


def test_plan_guard_accepts_only_reviewed_addresses_and_safe_action_vectors() -> None:
    contract = _load_contract()

    safe = {
        "format_version": "1.2",
        "resource_changes": [
            {
                "address": "aws_iam_role.cell",
                "mode": "managed",
                "change": {"actions": ["update"]},
            }
        ],
    }
    contract.validate_plan("official-eval", safe)

    for address, actions in (
        ("aws_iam_role.unrelated", ["update"]),
        ("aws_iam_role.cell", []),
        ("aws_iam_role.cell", ["delete"]),
        ("aws_iam_role.cell", ["create", "delete"]),
        ("aws_iam_role.cell", ["delete", "create"]),
    ):
        plan = {
            "format_version": "1.2",
            "resource_changes": [
                {
                    "address": address,
                    "mode": "managed",
                    "change": {"actions": actions},
                }
            ],
        }
        with pytest.raises(ValueError):
            contract.validate_plan("official-eval", plan)

    replacement = {
        "format_version": "1.2",
        "resource_changes": [
            {
                "address": "aws_iam_role.cell",
                "mode": "managed",
                "action_reason": "create_before_destroy",
                "change": {"actions": ["update"]},
            }
        ],
    }
    with pytest.raises(ValueError, match="replacement"):
        contract.validate_plan("official-eval", replacement)

    contraction = {
        "format_version": "1.2",
        "resource_changes": [
            {
                "address": "aws_iam_role_policies_exclusive.cell",
                "mode": "managed",
                "change": {
                    "actions": ["update"],
                    "before": {"policy_names": ["required", "removed"]},
                    "after": {"policy_names": ["required"]},
                },
            }
        ],
    }
    with pytest.raises(ValueError, match="contracts"):
        contract.validate_plan("official-eval", contraction)

    for malformed in (
        {"format_version": "1.2", "resource_changes": ["bad"]},
        {
            "format_version": "1.2",
            "resource_changes": [
                {
                    "address": "aws_iam_role.cell",
                    "mode": "future-mode",
                    "change": {"actions": ["update"]},
                }
            ],
        },
    ):
        with pytest.raises(ValueError):
            contract.validate_plan("official-eval", malformed)
