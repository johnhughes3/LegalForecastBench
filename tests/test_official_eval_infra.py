from __future__ import annotations

import ast
import copy
import json
import re
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import cast

import pytest
from tests.official_infra_trust_helpers import (
    job_environment,
    job_grants_id_token_write,
    replace_terraform_local,
    role_assuming_jobs,
    terraform_local_string,
    workflow_jobs,
)

ROOT = Path(__file__).resolve().parents[1]
INFRA_ROOT = ROOT / "infra" / "official-eval"
POLICY_ROOT = INFRA_ROOT / "policies"
ENVIRONMENT_MANIFEST = INFRA_ROOT / "github-environments.json"
RUN_BENCHMARK_WORKFLOW = ROOT / ".github" / "workflows" / "run-benchmark.yaml"
PROVIDER_CELL_WORKFLOW = ROOT / ".github" / "workflows" / "official-provider-cell.yaml"
FAN_IN_WORKFLOW = ROOT / ".github" / "workflows" / "fan-in-publish.yaml"
WORKFLOW_ROOT = ROOT / ".github" / "workflows"

OIDC_PROVIDER_ARN = (
    "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"
)
PACKET_BUCKET_ARN = "arn:aws:s3:::lfb-packets"
RESULTS_BUCKET_ARN = "arn:aws:s3:::lfb-results"
PROVIDER_AUTHORITY_TABLE_ARN = (
    "arn:aws:dynamodb:us-east-1:123456789012:table/lfb-provider-authority"
)
REPOSITORY = "johnhughes3/LegalForecastBench"
REF = "refs/heads/main"
CELL_ENVIRONMENT = "legalforecastbench-official-eval"
FAN_IN_ENVIRONMENT = "legalforecastbench-official-eval-fan-in"
SUBJECT_PREFIX = f"repo:{REPOSITORY}"

JsonObject = dict[str, object]
PolicyMutation = Callable[[JsonObject], None]


def _render_template(path: Path, **values: str) -> JsonObject:
    rendered = path.read_text(encoding="utf-8")
    for name, value in values.items():
        rendered = rendered.replace(f"${{{name}}}", value)
    unresolved = re.findall(r"\$\{[^}]+\}", rendered)
    assert unresolved == []
    loaded: object = json.loads(rendered)
    assert isinstance(loaded, dict)
    return cast(JsonObject, loaded)


def _trust_policy(environment: str) -> JsonObject:
    return _render_template(
        POLICY_ROOT / "github-oidc-trust.json.tftpl",
        github_oidc_provider_arn=OIDC_PROVIDER_ARN,
        github_repository=REPOSITORY,
        github_ref=REF,
        github_subject=f"{SUBJECT_PREFIX}:environment:{environment}",
    )


def _cell_policy() -> JsonObject:
    return _render_template(
        POLICY_ROOT / "cell-storage-policy.json.tftpl",
        packet_bucket_arn=PACKET_BUCKET_ARN,
        results_bucket_arn=RESULTS_BUCKET_ARN,
    )


def _fan_in_policy() -> JsonObject:
    return _render_template(
        POLICY_ROOT / "fan-in-storage-policy.json.tftpl",
        results_bucket_arn=RESULTS_BUCKET_ARN,
    )


def _bedrock_policy() -> JsonObject:
    direct_arn = (
        "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-direct-example-v1"
    )
    profile_arn = (
        "arn:aws:bedrock:us-east-1:123456789012:"
        "inference-profile/us.anthropic.claude-profile-example-v1"
    )
    destination_arns = [
        (
            "arn:aws:bedrock:us-east-1::foundation-model/"
            "anthropic.claude-profile-example-v1"
        ),
        (
            "arn:aws:bedrock:us-west-2::foundation-model/"
            "anthropic.claude-profile-example-v1"
        ),
    ]
    return _render_template(
        POLICY_ROOT / "cell-bedrock-policy.json.tftpl",
        bedrock_invoke_model_statements_json=json.dumps(
            [
                {
                    "Sid": "InvokeReviewedDirectFoundationModels",
                    "Effect": "Allow",
                    "Action": "bedrock:InvokeModel",
                    "Resource": [direct_arn],
                },
                {
                    "Sid": "GrantGeographicInferenceProfileExampleAccess",
                    "Effect": "Allow",
                    "Action": "bedrock:InvokeModel",
                    "Resource": [profile_arn],
                },
                {
                    "Sid": "GrantGeographicInferenceProfileExampleModelAccess",
                    "Effect": "Allow",
                    "Action": "bedrock:InvokeModel",
                    "Resource": destination_arns,
                    "Condition": {
                        "StringEquals": {
                            "bedrock:InferenceProfileArn": profile_arn,
                        }
                    },
                },
            ]
        ),
    )


def _provider_authority_policy() -> JsonObject:
    return _render_template(
        POLICY_ROOT / "cell-provider-authority-policy.json.tftpl",
        provider_authority_table_arn=PROVIDER_AUTHORITY_TABLE_ARN,
    )


def _statements_by_sid(policy: Mapping[str, object]) -> dict[str, JsonObject]:
    raw_statements = policy.get("Statement")
    assert isinstance(raw_statements, list)
    by_sid: dict[str, JsonObject] = {}
    for raw_statement in cast(list[object], raw_statements):
        assert isinstance(raw_statement, dict)
        statement = cast(JsonObject, raw_statement)
        sid = statement.get("Sid")
        assert isinstance(sid, str)
        assert sid not in by_sid
        by_sid[sid] = statement
    return by_sid


def _assert_exact_trust(policy: Mapping[str, object], *, environment: str) -> None:
    assert set(policy) == {"Version", "Statement"}
    assert policy["Version"] == "2012-10-17"
    statements = policy["Statement"]
    assert isinstance(statements, list)
    assert statements == [
        {
            "Sid": "GitHubActionsOidc",
            "Effect": "Allow",
            "Action": "sts:AssumeRoleWithWebIdentity",
            "Principal": {"Federated": OIDC_PROVIDER_ARN},
            "Condition": {
                "StringEquals": {
                    "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                    "token.actions.githubusercontent.com:sub": (
                        f"{SUBJECT_PREFIX}:environment:{environment}"
                    ),
                    "token.actions.githubusercontent.com:repository": REPOSITORY,
                    "token.actions.githubusercontent.com:ref": REF,
                }
            },
        }
    ]


def _assert_exact_cell_policy(policy: Mapping[str, object]) -> None:
    assert set(policy) == {"Version", "Statement"}
    assert policy["Version"] == "2012-10-17"
    statements = _statements_by_sid(policy)
    assert set(statements) == {
        "ReadModelPackets",
        "ListModelPackets",
        "ReadFrozenManifests",
        "ListFrozenManifests",
        "ReadManifestRunArtifacts",
        "ListManifestRunArtifacts",
        "ReadWritePerCaseResults",
        "ReadWritePerCaseRunnerLogs",
        "ListPerCaseResults",
        "ReadMutationMarkers",
        "CreateMutationMarkers",
        "ReadCycleSeal",
        "ProbeExactCycleSeal",
    }
    assert statements["ReadModelPackets"] == {
        "Sid": "ReadModelPackets",
        "Effect": "Allow",
        "Action": "s3:GetObject",
        "Resource": f"{PACKET_BUCKET_ARN}/model-packets/*",
    }
    assert statements["ListModelPackets"] == {
        "Sid": "ListModelPackets",
        "Effect": "Allow",
        "Action": "s3:ListBucket",
        "Resource": PACKET_BUCKET_ARN,
        "Condition": {"StringLike": {"s3:prefix": "model-packets/*"}},
    }
    assert statements["ReadFrozenManifests"] == {
        "Sid": "ReadFrozenManifests",
        "Effect": "Allow",
        "Action": "s3:GetObject",
        "Resource": f"{RESULTS_BUCKET_ARN}/manifests/*",
    }
    assert statements["ListFrozenManifests"] == {
        "Sid": "ListFrozenManifests",
        "Effect": "Allow",
        "Action": "s3:ListBucket",
        "Resource": RESULTS_BUCKET_ARN,
        "Condition": {"StringLike": {"s3:prefix": "manifests/*"}},
    }
    assert statements["ReadManifestRunArtifacts"] == {
        "Sid": "ReadManifestRunArtifacts",
        "Effect": "Allow",
        "Action": "s3:GetObject",
        "Resource": f"{RESULTS_BUCKET_ARN}/cycle-1/manifest-runs/*",
    }
    assert statements["ListManifestRunArtifacts"] == {
        "Sid": "ListManifestRunArtifacts",
        "Effect": "Allow",
        "Action": "s3:ListBucket",
        "Resource": RESULTS_BUCKET_ARN,
        "Condition": {
            "StringLike": {"s3:prefix": "cycle-1/manifest-runs/*"},
        },
    }
    assert statements["ReadWritePerCaseResults"] == {
        "Sid": "ReadWritePerCaseResults",
        "Effect": "Allow",
        "Action": ["s3:GetObject", "s3:PutObject"],
        "Resource": f"{RESULTS_BUCKET_ARN}/per-case/*/metrics/*",
    }
    assert statements["ReadWritePerCaseRunnerLogs"] == {
        "Sid": "ReadWritePerCaseRunnerLogs",
        "Effect": "Allow",
        "Action": ["s3:GetObject", "s3:PutObject"],
        "Resource": (f"{RESULTS_BUCKET_ARN}/per-case/*/reports/*/*.runner-log.jsonl"),
    }
    assert statements["ListPerCaseResults"] == {
        "Sid": "ListPerCaseResults",
        "Effect": "Allow",
        "Action": "s3:ListBucket",
        "Resource": RESULTS_BUCKET_ARN,
        "Condition": {"StringLike": {"s3:prefix": "per-case/*"}},
    }
    mutation_resources = [
        f"{RESULTS_BUCKET_ARN}/cycle-publication-state/*/runs/*/*/intent.json",
        f"{RESULTS_BUCKET_ARN}/cycle-publication-state/*/runs/*/*/done.json",
    ]
    assert statements["ReadMutationMarkers"] == {
        "Sid": "ReadMutationMarkers",
        "Effect": "Allow",
        "Action": "s3:GetObject",
        "Resource": mutation_resources,
    }
    assert statements["CreateMutationMarkers"] == {
        "Sid": "CreateMutationMarkers",
        "Effect": "Allow",
        "Action": "s3:PutObject",
        "Resource": mutation_resources,
        "Condition": {"Null": {"s3:if-none-match": "false"}},
    }
    assert statements["ReadCycleSeal"] == {
        "Sid": "ReadCycleSeal",
        "Effect": "Allow",
        "Action": "s3:GetObject",
        "Resource": (f"{RESULTS_BUCKET_ARN}/cycle-publication-state/*/seal.json"),
    }
    assert statements["ProbeExactCycleSeal"] == {
        "Sid": "ProbeExactCycleSeal",
        "Effect": "Allow",
        "Action": "s3:ListBucket",
        "Resource": RESULTS_BUCKET_ARN,
        "Condition": {
            "StringLike": {
                "s3:prefix": "cycle-publication-state/*/seal.json",
            }
        },
    }


def _assert_exact_fan_in_policy(policy: Mapping[str, object]) -> None:
    assert set(policy) == {"Version", "Statement"}
    assert policy["Version"] == "2012-10-17"
    statements = _statements_by_sid(policy)
    assert set(statements) == {
        "ReadExactPerCaseVersions",
        "ReadShardReceipts",
        "CreateShardReceipts",
        "ReadCycleClosure",
        "CreateCycleClosure",
        "ReadCanonicalPublication",
        "ReadManifestRunArtifacts",
        "CreateCanonicalPublication",
        "ListCurrentPerCaseVersions",
        "ListFanInNamespaces",
    }
    assert statements["ReadExactPerCaseVersions"] == {
        "Sid": "ReadExactPerCaseVersions",
        "Effect": "Allow",
        "Action": ["s3:GetObject", "s3:GetObjectVersion"],
        "Resource": f"{RESULTS_BUCKET_ARN}/per-case/*/metrics/*",
    }
    receipt_resource = f"{RESULTS_BUCKET_ARN}/shard-receipts/*/*/*/*.json"
    assert statements["ReadShardReceipts"] == {
        "Sid": "ReadShardReceipts",
        "Effect": "Allow",
        "Action": "s3:GetObject",
        "Resource": receipt_resource,
    }
    assert statements["CreateShardReceipts"] == {
        "Sid": "CreateShardReceipts",
        "Effect": "Allow",
        "Action": "s3:PutObject",
        "Resource": receipt_resource,
        "Condition": {"Null": {"s3:if-none-match": "false"}},
    }
    closure_resources = [
        f"{RESULTS_BUCKET_ARN}/cycle-publication-state/*/runs/*/*/intent.json",
        f"{RESULTS_BUCKET_ARN}/cycle-publication-state/*/runs/*/*/done.json",
        f"{RESULTS_BUCKET_ARN}/cycle-publication-state/*/seal.json",
    ]
    assert statements["ReadCycleClosure"] == {
        "Sid": "ReadCycleClosure",
        "Effect": "Allow",
        "Action": "s3:GetObject",
        "Resource": closure_resources,
    }
    assert statements["CreateCycleClosure"] == {
        "Sid": "CreateCycleClosure",
        "Effect": "Allow",
        "Action": "s3:PutObject",
        "Resource": closure_resources,
        "Condition": {"Null": {"s3:if-none-match": "false"}},
    }
    report_resource = f"{RESULTS_BUCKET_ARN}/reports/*/multi-ablation/*"
    assert statements["ReadCanonicalPublication"] == {
        "Sid": "ReadCanonicalPublication",
        "Effect": "Allow",
        "Action": "s3:GetObject",
        "Resource": report_resource,
    }
    assert statements["ReadManifestRunArtifacts"] == {
        "Sid": "ReadManifestRunArtifacts",
        "Effect": "Allow",
        "Action": "s3:GetObject",
        "Resource": f"{RESULTS_BUCKET_ARN}/cycle-1/manifest-runs/*",
    }
    assert statements["CreateCanonicalPublication"] == {
        "Sid": "CreateCanonicalPublication",
        "Effect": "Allow",
        "Action": "s3:PutObject",
        "Resource": report_resource,
        "Condition": {"Null": {"s3:if-none-match": "false"}},
    }
    assert statements["ListFanInNamespaces"] == {
        "Sid": "ListFanInNamespaces",
        "Effect": "Allow",
        "Action": "s3:ListBucket",
        "Resource": RESULTS_BUCKET_ARN,
        "Condition": {
            "StringLike": {
                "s3:prefix": [
                    "cycle-publication-state/*/runs/*",
                    "cycle-publication-state/*/seal.json",
                    "cycle-1/manifest-runs/*",
                    "per-case/*",
                    "reports/*/multi-ablation/*",
                    "shard-receipts/*",
                ]
            }
        },
    }
    assert statements["ListCurrentPerCaseVersions"] == {
        "Sid": "ListCurrentPerCaseVersions",
        "Effect": "Allow",
        "Action": "s3:ListBucketVersions",
        "Resource": RESULTS_BUCKET_ARN,
        "Condition": {
            "StringLike": {
                "s3:prefix": "per-case/*",
            }
        },
    }


def test_exact_two_role_topology_and_policy_attachments() -> None:
    terraform = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(INFRA_ROOT.glob("*.tf"))
    )
    roles = set(re.findall(r'resource "aws_iam_role" "([^"]+)"', terraform))
    inline_policies = set(
        re.findall(r'resource "aws_iam_role_policy" "([^"]+)"', terraform)
    )

    assert roles == {"cell", "fan_in"}
    assert inline_policies == {
        "cell_storage",
        "cell_provider_authority",
        "cell_bedrock",
        "fan_in_storage",
    }
    assert set(
        re.findall(
            r'resource "aws_iam_role_policies_exclusive" "([^"]+)"',
            terraform,
        )
    ) == {"cell", "fan_in"}
    assert set(
        re.findall(
            r'resource "aws_iam_role_policy_attachments_exclusive" "([^"]+)"',
            terraform,
        )
    ) == {"cell", "fan_in"}
    assert 'resource "aws_iam_policy"' not in terraform
    assert 'resource "aws_iam_role_policy_attachment"' not in terraform
    assert "aws_dynamodb" not in terraform
    assert "assume_role_policy   = local.cell_trust_policy_json" in terraform
    assert "assume_role_policy   = local.fan_in_trust_policy_json" in terraform
    assert "role   = aws_iam_role.cell.id" in terraform
    assert "policy = local.cell_storage_policy_json" in terraform
    assert "policy = local.cell_provider_authority_policy_json" in terraform
    assert "role   = aws_iam_role.fan_in.id" in terraform
    assert "policy = local.fan_in_storage_policy_json" in terraform
    assert "policy_arns = []" in terraform
    assert "aws_iam_role_policy.cell_bedrock[0].name" in terraform
    assert "aws_iam_role_policy.cell_provider_authority.name" in terraform
    assert "var.enable_bedrock_runtime" in terraform
    assert "computed_provider_authority_resource_identity_sha256 = sha256(" in terraform
    assert "local.computed_provider_authority_resource_identity_sha256" in terraform
    assert "var.provider_authority_resource_identity_sha256" in terraform
    assert (
        'split(":", var.provider_authority_table_arn)[3] == var.aws_region' in terraform
    )
    assert 'split(":", var.provider_authority_table_arn)[4]' in terraform
    assert 'split(":", var.github_oidc_provider_arn)[4]' in terraform
    assert {path.name for path in POLICY_ROOT.glob("*.json.tftpl")} == {
        "cell-bedrock-policy.json.tftpl",
        "cell-provider-authority-policy.json.tftpl",
        "cell-storage-policy.json.tftpl",
        "fan-in-storage-policy.json.tftpl",
        "github-oidc-trust.json.tftpl",
        "tls-only-bucket-policy.json.tftpl",
    }
    assert "LFB_GITHUB_PACKET_READ_ROLE_ARN" in (INFRA_ROOT / "outputs.tf").read_text(
        encoding="utf-8"
    )
    assert "LFB_GITHUB_FAN_IN_ROLE_ARN" in (INFRA_ROOT / "outputs.tf").read_text(
        encoding="utf-8"
    )
    assert "LFB_PROVIDER_AUTHORITY_TABLE" in (INFRA_ROOT / "outputs.tf").read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize(
    "environment",
    [CELL_ENVIRONMENT, FAN_IN_ENVIRONMENT],
)
def test_oidc_trust_is_exact_for_repository_ref_and_environment(
    environment: str,
) -> None:
    _assert_exact_trust(_trust_policy(environment), environment=environment)


def test_cell_policy_matches_current_call_graph_exactly() -> None:
    _assert_exact_cell_policy(_cell_policy())


def test_cell_provider_authority_policy_is_exact_table_data_plane_only() -> None:
    assert _provider_authority_policy() == {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "ExactProviderAuthorityDataPlane",
                "Effect": "Allow",
                "Action": [
                    "dynamodb:ConditionCheckItem",
                    "dynamodb:DescribeTable",
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                ],
                "Resource": PROVIDER_AUTHORITY_TABLE_ARN,
            }
        ],
    }


def test_fan_in_policy_matches_current_call_graph_exactly() -> None:
    _assert_exact_fan_in_policy(_fan_in_policy())


def test_optional_bedrock_policy_separates_direct_and_profile_grants() -> None:
    direct_arn = (
        "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-direct-example-v1"
    )
    profile_arn = (
        "arn:aws:bedrock:us-east-1:123456789012:"
        "inference-profile/us.anthropic.claude-profile-example-v1"
    )
    destination_arns = [
        (
            "arn:aws:bedrock:us-east-1::foundation-model/"
            "anthropic.claude-profile-example-v1"
        ),
        (
            "arn:aws:bedrock:us-west-2::foundation-model/"
            "anthropic.claude-profile-example-v1"
        ),
    ]
    assert _bedrock_policy() == {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "InvokeReviewedDirectFoundationModels",
                "Effect": "Allow",
                "Action": "bedrock:InvokeModel",
                "Resource": [direct_arn],
            },
            {
                "Sid": "GrantGeographicInferenceProfileExampleAccess",
                "Effect": "Allow",
                "Action": "bedrock:InvokeModel",
                "Resource": [profile_arn],
            },
            {
                "Sid": "GrantGeographicInferenceProfileExampleModelAccess",
                "Effect": "Allow",
                "Action": "bedrock:InvokeModel",
                "Resource": destination_arns,
                "Condition": {
                    "StringEquals": {
                        "bedrock:InferenceProfileArn": profile_arn,
                    }
                },
            },
        ],
    }
    statements = _statements_by_sid(_bedrock_policy())
    direct = statements["InvokeReviewedDirectFoundationModels"]
    profile = statements["GrantGeographicInferenceProfileExampleAccess"]
    profile_models = statements["GrantGeographicInferenceProfileExampleModelAccess"]
    assert "Condition" not in direct
    assert direct["Resource"] == [direct_arn]
    assert "Condition" not in profile
    assert profile["Resource"] == [profile_arn]
    assert profile_models["Resource"] == destination_arns
    assert profile_models["Condition"] == {
        "StringEquals": {"bedrock:InferenceProfileArn": profile_arn}
    }
    assert not set(cast(list[str], direct["Resource"])) & set(destination_arns)
    assert profile_arn not in cast(list[str], profile_models["Resource"])


def test_optional_bedrock_contract_is_default_off_cell_only_and_rejects_global() -> (
    None
):
    terraform = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(INFRA_ROOT.glob("*.tf"))
    )
    locals_source = (INFRA_ROOT / "locals.tf").read_text(encoding="utf-8")
    variables_source = (INFRA_ROOT / "variables.tf").read_text(encoding="utf-8")
    assert 'variable "enable_bedrock_runtime"' in terraform
    assert "default     = false" in terraform
    assert 'variable "bedrock_direct_foundation_model_arns"' in terraform
    assert 'variable "bedrock_geographic_inference_profiles"' in terraform
    assert "length(var.bedrock_direct_foundation_model_arns) > 0" in terraform
    assert "length(var.bedrock_geographic_inference_profiles) > 0" in terraform
    assert (
        "Resource = sort(tolist(var.bedrock_direct_foundation_model_arns))"
        in locals_source
    )
    assert (
        "Resource = [var.bedrock_geographic_inference_profiles"
        "[profile_key].inference_profile_arn]" in locals_source
    )
    assert (
        "var.bedrock_geographic_inference_profiles"
        "[profile_key].destination_foundation_model_arns" in locals_source
    )
    assert '"bedrock:InferenceProfileArn"' in locals_source
    assert (
        '"bedrock:InferenceProfileArn" = '
        "var.bedrock_geographic_inference_profiles"
        "[profile_key].inference_profile_arn" in locals_source
    )
    assert ":inference-profile/global." in variables_source
    assert "Global Bedrock inference profiles are unsupported" in variables_source
    assert "distinct three-part policy contract" in variables_source
    assert "(us|eu|apac)" in variables_source
    assert "length(profile.destination_foundation_model_arns) > 0" in variables_source
    assert (
        "Each geographic Bedrock inference-profile ARN must appear" in variables_source
    )
    assert "application-inference-profile" not in terraform
    assert "bedrock:InvokeModel" not in json.dumps(_fan_in_policy())


def _add_statement(policy: JsonObject) -> None:
    raw_statements = policy["Statement"]
    assert isinstance(raw_statements, list)
    statements = cast(list[object], raw_statements)
    statements.append(
        {
            "Sid": "Broadening",
            "Effect": "Allow",
            "Action": "s3:*",
            "Resource": "*",
        }
    )


def _add_action(policy: JsonObject) -> None:
    statement = _statements_by_sid(policy)["ReadWritePerCaseResults"]
    raw_actions = statement["Action"]
    assert isinstance(raw_actions, list)
    actions = cast(list[object], raw_actions)
    actions.append("s3:DeleteObject")


def _add_resource(policy: JsonObject) -> None:
    raw_statements = policy["Statement"]
    assert isinstance(raw_statements, list)
    statement: JsonObject | None = None
    for item in cast(list[object], raw_statements):
        if isinstance(item, dict):
            candidate = cast(JsonObject, item)
            if candidate.get("Sid") == "ReadWritePerCaseResults":
                statement = candidate
                break
    assert statement is not None
    statement["Resource"] = [
        statement["Resource"],
        f"{RESULTS_BUCKET_ARN}/reports/*",
    ]


@pytest.mark.parametrize(
    "mutation",
    [_add_statement, _add_action, _add_resource],
)
def test_cell_contract_guard_rejects_policy_broadening(
    mutation: PolicyMutation,
) -> None:
    policy = copy.deepcopy(_cell_policy())
    mutation(policy)
    with pytest.raises(AssertionError):
        _assert_exact_cell_policy(policy)


def test_trust_contract_guard_rejects_extra_principal_or_claim_drift() -> None:
    policy = copy.deepcopy(_trust_policy(CELL_ENVIRONMENT))
    raw_statements = policy["Statement"]
    assert isinstance(raw_statements, list)
    statements = cast(list[object], raw_statements)
    statement = statements[0]
    assert isinstance(statement, dict)
    statement = cast(JsonObject, statement)
    statement["Principal"] = {
        "Federated": [OIDC_PROVIDER_ARN, "arn:aws:iam::123456789012:root"]
    }
    with pytest.raises(AssertionError):
        _assert_exact_trust(policy, environment=CELL_ENVIRONMENT)

    policy = copy.deepcopy(_trust_policy(CELL_ENVIRONMENT))
    raw_statements = policy["Statement"]
    assert isinstance(raw_statements, list)
    statements = cast(list[object], raw_statements)
    statement = statements[0]
    assert isinstance(statement, dict)
    statement = cast(JsonObject, statement)
    condition = statement["Condition"]
    assert isinstance(condition, dict)
    condition = cast(JsonObject, condition)
    string_equals = condition["StringEquals"]
    assert isinstance(string_equals, dict)
    string_equals = cast(JsonObject, string_equals)
    string_equals["token.actions.githubusercontent.com:ref"] = "refs/heads/*"
    with pytest.raises(AssertionError):
        _assert_exact_trust(policy, environment=CELL_ENVIRONMENT)


def _workflow_texts() -> dict[str, str]:
    paths = sorted([*WORKFLOW_ROOT.glob("*.yml"), *WORKFLOW_ROOT.glob("*.yaml")])
    assert paths
    return {path.name: path.read_text(encoding="utf-8") for path in paths}


def _assert_eval_trust_refs_satisfiable(
    *,
    locals_text: str,
    manifest_text: str,
    workflow_texts: Mapping[str, str],
) -> None:
    """Raise unless the cell/fan-in trust conditions stay reachable.

    Reads only production bytes: the Terraform locals that render
    github-oidc-trust.json.tftpl for both roles, the environment manifest,
    and every repository workflow, sweeping each role-assuming job. Any
    drift this catches would surface as an AssumeRoleWithWebIdentity denial
    at run time.
    """
    ref = terraform_local_string(locals_text, "github_ref")
    repository = terraform_local_string(locals_text, "github_repository")
    cell_environment = terraform_local_string(locals_text, "cell_environment_name")
    fan_in_environment = terraform_local_string(locals_text, "fan_in_environment_name")

    # Both trust renders must be fed from these exact locals, and the pinned
    # subjects must be built from the same repository and environment names;
    # otherwise the values parsed above are not the ones AWS evaluates.
    wirings = re.findall(
        r"^\s*github_ref\s*=\s*local\.github_ref\s*$",
        locals_text,
        flags=re.MULTILINE,
    )
    assert len(wirings) == 2
    assert (
        terraform_local_string(locals_text, "github_subject_prefix")
        == "repo:${local.github_repository}"
    )
    for subject_template in (
        '"${local.github_subject_prefix}:environment:${local.cell_environment_name}"',
        '"${local.github_subject_prefix}:environment:${local.fan_in_environment_name}"',
    ):
        assert subject_template in locals_text

    # `:sub` and `:repository` match only if the manifest provisions the same
    # environments, for the same repository, with the same subjects.
    loaded: object = json.loads(manifest_text)
    assert isinstance(loaded, dict)
    manifest = cast(JsonObject, loaded)
    assert manifest["repository"] == repository
    rows = manifest["environments"]
    assert isinstance(rows, list)
    subjects = {
        cast(JsonObject, row)["name"]: cast(JsonObject, row)["aws_oidc_subject"]
        for row in cast(list[object], rows)
    }
    for environment in (cell_environment, fan_in_environment):
        assert environment in subjects
        assert subjects[environment] == f"repo:{repository}:environment:{environment}"

    # `:ref` matches only from the single branch the manifest lets these
    # environments deploy from.
    protection = manifest["common_protection"]
    assert isinstance(protection, dict)
    raw_branches = cast(JsonObject, protection)["custom_branch_policies"]
    assert isinstance(raw_branches, list)
    branches = cast(list[object], raw_branches)
    assert len(branches) == 1
    branch = branches[0]
    assert isinstance(branch, str)
    assert ref == f"refs/heads/{branch}"

    # The provider-cell reusable workflow uses the single provisioned evaluation
    # environment. Validate that binding once, then validate every dispatcher
    # caller maps one provider to that same environment. A called workflow
    # cannot inherit the caller's job-level environment, so the called job's
    # literal binding is the actual OIDC claim source.
    provider_cell_name = PROVIDER_CELL_WORKFLOW.name
    provider_cell_text = workflow_texts.get(provider_cell_name)
    assert provider_cell_text is not None
    assert re.search(
        r"^      environment_name:\s*$\n"
        r"        required: true\s*$\n"
        r"        type: string\s*$",
        provider_cell_text,
        flags=re.MULTILINE,
    )
    assert "    environment: legalforecastbench-official-eval" in provider_cell_text

    expected_provider_lanes = {
        "run-openai": ("openai", cell_environment),
        "run-anthropic": ("anthropic", cell_environment),
        "run-gemini": ("gemini", cell_environment),
    }
    caller_lanes: dict[str, tuple[str, str]] = {}
    for job_id, block in workflow_jobs(
        workflow_texts[RUN_BENCHMARK_WORKFLOW.name]
    ).items():
        if "uses: ./.github/workflows/official-provider-cell.yaml" not in block:
            continue
        provider_match = re.search(r"^      provider: (\S+)\s*$", block, re.MULTILINE)
        environment_match = re.search(
            r"^      environment_name: (\S+)\s*$", block, re.MULTILINE
        )
        assert provider_match is not None, job_id
        assert environment_match is not None, job_id
        caller_lanes[job_id] = (provider_match.group(1), environment_match.group(1))
    assert caller_lanes == expected_provider_lanes

    # Every job in any workflow that assumes one of these roles must itself
    # bind that role's provisioned environment and grant itself the OIDC
    # token; a workflow-wide substring cannot see which job carries the
    # binding. Jobs assuming other roles (operator, labeling) belong to
    # other trust roots and are skipped, but each of these two roles must
    # keep at least one conforming producer or its trust is unsatisfiable.
    role_environments = {
        "LFB_GITHUB_PACKET_READ_ROLE_ARN": cell_environment,
        "LFB_GITHUB_FAN_IN_ROLE_ARN": fan_in_environment,
    }
    producers = {variable: 0 for variable in role_environments}
    for workflow_name, workflow_text in workflow_texts.items():
        for job_id, block in role_assuming_jobs(workflow_text).items():
            label = f"{workflow_name}:{job_id}"
            assumed: list[str] = re.findall(
                r"role-to-assume: \$\{\{ env\.([A-Z0-9_]+) \}\}", block
            )
            assert assumed, label
            for variable in assumed:
                if variable not in role_environments:
                    continue
                environment = job_environment(block)
                if workflow_name == provider_cell_name:
                    assert variable == "LFB_GITHUB_PACKET_READ_ROLE_ARN", label
                    assert environment == role_environments[variable], label
                else:
                    assert environment == role_environments[variable], label
                assert job_grants_id_token_write(block), label
                producers[variable] += 1
    for variable, count in producers.items():
        assert count > 0, f"no workflow job can satisfy the {variable} trust"


def test_trust_ref_condition_is_satisfiable_from_the_only_deployable_branch() -> None:
    """The pinned `:ref` must name the one branch these environments can deploy.

    Reviewers have twice argued that `:ref` cannot match and should be deleted:
    once on the premise that an environment-scoped token omits a `ref` claim,
    once on the premise that AWS never populates the key. Both are false --
    GitHub emits `ref` alongside an environment-qualified `sub`, and AWS
    documents `:ref` on its GitHub condition-key tab, where "available in
    session: no" means trust-policy-only rather than unavailable. See
    docs/github-aws-oidc-trust-claims.md for the primary sources.

    What actually has to hold is that the pinned value is reachable. An
    environment-bound job can only run from a branch the environment's
    deployment branch policy allows, so `:ref` is satisfiable exactly when it
    names that branch. The guard therefore binds to the production Terraform
    locals, the manifest, and the exact role-assuming jobs -- never to
    test-owned copies -- and the companion mutation test drifts those same
    production bytes to prove the fence discriminates.
    """
    locals_text = (INFRA_ROOT / "locals.tf").read_text(encoding="utf-8")
    _assert_eval_trust_refs_satisfiable(
        locals_text=locals_text,
        manifest_text=ENVIRONMENT_MANIFEST.read_text(encoding="utf-8"),
        workflow_texts=_workflow_texts(),
    )

    # The exact-trust renders in this module pin these copies; keep each equal
    # to its production local so drift cannot hide behind a test-owned value.
    assert REPOSITORY == terraform_local_string(locals_text, "github_repository")
    assert REF == terraform_local_string(locals_text, "github_ref")
    assert CELL_ENVIRONMENT == terraform_local_string(
        locals_text, "cell_environment_name"
    )
    assert FAN_IN_ENVIRONMENT == terraform_local_string(
        locals_text, "fan_in_environment_name"
    )


def test_eval_trust_satisfiability_fence_discriminates_on_real_drift() -> None:
    """Drifting the production inputs must redden the satisfiability fence.

    Every case mutates the real bytes -- never a test-owned copy -- and each
    models a drift that a copy-based or workflow-wide check would miss while
    the deployed roles became unassumable.
    """
    locals_text = (INFRA_ROOT / "locals.tf").read_text(encoding="utf-8")
    manifest_text = ENVIRONMENT_MANIFEST.read_text(encoding="utf-8")
    workflow_texts = _workflow_texts()
    run_workflow_text = workflow_texts[RUN_BENCHMARK_WORKFLOW.name]

    def check(
        *,
        mutated_locals: str | None = None,
        mutated_manifest: str | None = None,
        mutated_run_workflow: str | None = None,
    ) -> None:
        swept = dict(workflow_texts)
        if mutated_run_workflow is not None:
            swept[RUN_BENCHMARK_WORKFLOW.name] = mutated_run_workflow
        _assert_eval_trust_refs_satisfiable(
            locals_text=locals_text if mutated_locals is None else mutated_locals,
            manifest_text=(
                manifest_text if mutated_manifest is None else mutated_manifest
            ),
            workflow_texts=swept,
        )

    check()

    # Repoint the production ref local at a branch the manifest forbids.
    with pytest.raises(AssertionError):
        check(
            mutated_locals=replace_terraform_local(
                locals_text, "github_ref", "refs/heads/release"
            )
        )

    # Widen the manifest to a second deployable branch.
    widened = manifest_text.replace(
        '"custom_branch_policies": ["main"]',
        '"custom_branch_policies": ["main", "release"]',
    )
    assert widened != manifest_text
    with pytest.raises(AssertionError):
        check(mutated_manifest=widened)

    # Rename the cell environment local: the trust would pin a subject that
    # no provisioned environment carries.
    with pytest.raises(AssertionError):
        check(
            mutated_locals=replace_terraform_local(
                locals_text,
                "cell_environment_name",
                "legalforecastbench-unprovisioned",
            )
        )

    # Rebind one role-assuming job onto an unprovisioned environment.
    cell_environment = terraform_local_string(locals_text, "cell_environment_name")
    rebound = run_workflow_text.replace(
        f"\n    environment: {cell_environment}\n",
        "\n    environment: legalforecastbench-unprovisioned\n",
        1,
    )
    assert rebound != run_workflow_text
    with pytest.raises(AssertionError):
        check(mutated_run_workflow=rebound)


@pytest.mark.parametrize(
    ("policy_factory", "sid"),
    [
        (_cell_policy, "CreateMutationMarkers"),
        (_fan_in_policy, "CreateShardReceipts"),
        (_fan_in_policy, "CreateCycleClosure"),
        (_fan_in_policy, "CreateCanonicalPublication"),
    ],
)
def test_immutable_write_contract_rejects_missing_or_wrong_precondition(
    policy_factory: Callable[[], JsonObject],
    sid: str,
) -> None:
    for replacement in (
        None,
        {"Null": {"s3:if-none-match": "true"}},
        {"Null": {"s3:wrong-header": "false"}},
    ):
        policy = copy.deepcopy(policy_factory())
        statement = _statements_by_sid(policy)[sid]
        if replacement is None:
            statement.pop("Condition")
        else:
            statement["Condition"] = replacement
        with pytest.raises(AssertionError):
            if policy_factory is _cell_policy:
                _assert_exact_cell_policy(policy)
            else:
                _assert_exact_fan_in_policy(policy)


def _function_source(
    path: Path,
    function_name: str,
    *,
    owner: str | None = None,
) -> str:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    scope: list[ast.stmt] = tree.body
    if owner is not None:
        owners = [
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == owner
        ]
        assert len(owners) == 1
        scope = owners[0].body
    matches = [
        node
        for node in scope
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == function_name
    ]
    assert len(matches) == 1
    segment = ast.get_source_segment(source, matches[0])
    assert segment is not None
    return segment


def test_official_workflows_do_not_silently_default_lfb_aws_region() -> None:
    offenders = [
        path.relative_to(ROOT).as_posix()
        for path in sorted(
            [*WORKFLOW_ROOT.glob("*.yml"), *WORKFLOW_ROOT.glob("*.yaml")]
        )
        if "vars.LFB_AWS_REGION ||" in path.read_text(encoding="utf-8")
    ]

    assert offenders == []


def test_cross_file_workflow_and_python_call_graph_matches_policy_contract() -> None:
    run_workflow = RUN_BENCHMARK_WORKFLOW.read_text(encoding="utf-8")
    provider_workflow = PROVIDER_CELL_WORKFLOW.read_text(encoding="utf-8")
    fan_in_workflow = FAN_IN_WORKFLOW.read_text(encoding="utf-8")
    per_case_source = ROOT / "legalforecast" / "evals" / "per_case_runner.py"
    bedrock_source = ROOT / "legalforecast" / "evals" / "live_model_solver.py"
    closure_source = ROOT / "legalforecast" / "publication" / "cycle_closure.py"
    receipt_source = ROOT / "legalforecast" / "publication" / "shard_receipt.py"
    publish_source = ROOT / "legalforecast" / "publication" / "shard_fan_in_publish.py"

    assert "environment: legalforecastbench-official-eval" in run_workflow
    assert "LFB_GITHUB_PACKET_READ_ROLE_ARN" in run_workflow
    assert "environment: legalforecastbench-official-eval-fan-in" in run_workflow
    assert "LFB_GITHUB_FAN_IN_ROLE_ARN" in run_workflow
    assert "environment: legalforecastbench-official-eval" in provider_workflow
    assert "LFB_GITHUB_PACKET_READ_ROLE_ARN" in provider_workflow
    assert '--packet-store-root "s3://${LFB_PACKET_BUCKET}"' in provider_workflow
    assert (
        '--results-store-root "s3://${LFB_RESULTS_BUCKET}/per-case/${CYCLE_ID}"'
        in provider_workflow
    )
    for runtime in ("bedrock", "aws-bedrock", "aws_bedrock"):
        assert runtime in provider_workflow
    assert "LFB_ANTHROPIC_BEDROCK_MODEL_ID" in provider_workflow
    assert "LFB_PROVIDER_AUTHORITY_TABLE" in provider_workflow
    assert "LFB_PROVIDER_ACCOUNT_ALIAS" not in provider_workflow
    assert "--provider-account" not in provider_workflow
    assert "--provider-authority-table" in provider_workflow
    assert "--provider-authority-region" in provider_workflow

    assert "environment: legalforecastbench-official-eval-fan-in" in fan_in_workflow
    assert "LFB_GITHUB_FAN_IN_ROLE_ARN" in fan_in_workflow
    assert (
        '"s3://${LFB_RESULTS_BUCKET}/reports/${CYCLE_ID}/multi-ablation/"'
        in fan_in_workflow
    )

    output_keys_source = _function_source(per_case_source, "_output_keys")
    assert 'f"metrics/{cycle_slug}/{run_id}.runs.jsonl"' in output_keys_source
    assert 'f"metrics/{cycle_slug}/{run_id}.recovery.json"' in output_keys_source
    run_source = _function_source(per_case_source, "run_per_case_evaluation")
    assert 'f"reports/{_cycle_slug(packet_object)}/{run_id}.runner-log.jsonl"' in (
        run_source
    )
    assert "aws s3 sync \\" in run_workflow
    assert '"s3://${LFB_RESULTS_BUCKET}/per-case/${CYCLE_ID}/" \\' in run_workflow
    ordinary_put_source = _function_source(per_case_source, "_upload_path")
    assert '"put-object"' in ordinary_put_source
    assert '"--if-none-match"' not in ordinary_put_source

    bedrock_call_source = _function_source(
        bedrock_source,
        "_invoke_bedrock_runtime_json",
    )
    assert '"bedrock-runtime"' in bedrock_call_source
    assert '"invoke-model"' in bedrock_call_source

    for path, function_name, owner in (
        (closure_source, "create", "_S3ObjectStore"),
        (receipt_source, "write_receipt_once", None),
        (publish_source, "_put_s3_file_once", None),
    ):
        immutable_put_source = _function_source(path, function_name, owner=owner)
        assert '"put-object"' in immutable_put_source
        assert '"--if-none-match"' in immutable_put_source
        assert '"*"' in immutable_put_source

    assert 'return f"{_STATE_NAMESPACE}/{cycle}/seal.json"' in _function_source(
        closure_source,
        "seal_key",
    )
    assert 'return f"shard-receipts/{cycle_id}/' in _function_source(
        receipt_source,
        "receipt_key",
    )
    assert 'f"reports/{cycle_id}/multi-ablation"' in _function_source(
        publish_source,
        "_require_canonical_publish_root",
    )


def test_storage_is_private_owned_encrypted_versioned_and_tls_only() -> None:
    storage = (INFRA_ROOT / "storage.tf").read_text(encoding="utf-8")
    tls_policy = _render_template(
        POLICY_ROOT / "tls-only-bucket-policy.json.tftpl",
        bucket_arn=RESULTS_BUCKET_ARN,
    )

    assert storage.count('resource "aws_s3_bucket"') == 2
    assert storage.count('resource "aws_s3_bucket_public_access_block"') == 2
    assert storage.count('resource "aws_s3_bucket_ownership_controls"') == 2
    assert (
        storage.count('resource "aws_s3_bucket_server_side_encryption_configuration"')
        == 2
    )
    assert storage.count('resource "aws_s3_bucket_versioning"') == 2
    assert storage.count('resource "aws_s3_bucket_policy"') == 2
    assert storage.count("BucketOwnerEnforced") == 2
    assert storage.count('sse_algorithm = "AES256"') == 2
    assert storage.count('status = "Enabled"') >= 2
    assert tls_policy == {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "DenyInsecureTransport",
                "Effect": "Deny",
                "Principal": "*",
                "Action": "s3:*",
                "Resource": [RESULTS_BUCKET_ARN, f"{RESULTS_BUCKET_ARN}/*"],
                "Condition": {"Bool": {"aws:SecureTransport": "false"}},
            }
        ],
    }


def test_lifecycle_preserves_audit_versions_and_only_expires_negative_controls() -> (
    None
):
    storage = (INFRA_ROOT / "storage.tf").read_text(encoding="utf-8")

    assert "per-case/" not in storage
    assert "noncurrent_result_retention_days" not in storage
    assert 'prefix = "reports/security-negative-controls/"' in storage
    assert "var.negative_control_retention_days" in storage
    assert storage.count("abort_incomplete_multipart_upload") == 2


def test_s3_inputs_enforce_global_bucket_names_and_whole_retention_days() -> None:
    variables = (INFRA_ROOT / "variables.tf").read_text(encoding="utf-8")

    for variable_name in ("packet_bucket_name", "results_bucket_name"):
        reference = f"var.{variable_name}"
        assert f'!strcontains({reference}, "..")' in variables
        assert (
            'length(regexall("^[0-9]{1,3}([.][0-9]{1,3}){3}$", '
            f"{reference})) == 0" in variables
        )
        for reserved_prefix in ("xn--", "sthree-", "amzn-s3-demo-"):
            assert f'!startswith({reference}, "{reserved_prefix}")' in variables
        for reserved_suffix in (
            "-s3alias",
            "--ol-s3",
            ".mrap",
            "--x-s3",
            "--table-s3",
            "-an",
        ):
            assert f'!endswith({reference}, "{reserved_suffix}")' in variables

    assert (
        "floor(var.negative_control_retention_days) == "
        "var.negative_control_retention_days" in variables
    )


def test_docs_record_unapplied_import_remote_state_and_live_acceptance_boundaries() -> (
    None
):
    readme = (INFRA_ROOT / "README.md").read_text(encoding="utf-8")
    runbook = (ROOT / "docs" / "official-run-runbook.md").read_text(encoding="utf-8")
    combined = f"{readme}\n{runbook}"
    runbook_boundary = runbook.split(
        "The intended AWS boundary is defined, but not applied", 1
    )[1].split("The packet/result role used by each case writer", 1)[0]

    assert runbook_boundary.count("`LFB_AWS_REGION`") == 2
    assert "the same reviewed `LFB_AWS_REGION`" in runbook_boundary

    for required in (
        CELL_ENVIRONMENT,
        FAN_IN_ENVIRONMENT,
        "LFB_GITHUB_PACKET_READ_ROLE_ARN",
        "LFB_GITHUB_FAN_IN_ROLE_ARN",
        "LFB_PROVIDER_AUTHORITY_TABLE",
        "LFB_PROVIDER_ACCOUNT_ALIAS",
        "provider_authority_resource_identity_sha256",
        "terraform import",
        "aws_iam_role_policies_exclusive",
        "aws_iam_role_policy_attachments_exclusive",
        "remote state",
        "reports/security-negative-controls/",
        "VersionId",
        "PII",
        "plan",
        "apply",
        "post-provision",
        "main",
        "LFB_ANTHROPIC_RUNTIME",
        "bedrock_direct_foundation_model_arns",
        "bedrock_geographic_inference_profiles",
        "bedrock:InferenceProfileArn",
        "global inference profiles",
    ):
        assert required in combined

    for required in (
        "get-bucket-lifecycle-configuration",
        "get-bucket-policy",
        "full-replacement surfaces",
        "no unintended deletion",
        "Before live acceptance",
        "both `legalforecastbench-official-eval` and "
        "`legalforecastbench-official-eval-fan-in`",
        "fan-in environment has no provider secrets",
        "LFB_OFFICIAL_EVAL_INVENTORY_DIR",
        "set -euo pipefail",
        "NoSuchLifecycleConfiguration",
        "NoSuchBucketPolicy",
        "Any other AWS CLI error stops reconciliation",
        "Successful inventory responses remain as JSON",
        "--output json --no-cli-pager",
        'grep -Fq "($absent_code)"',
        'cat "$error_path" >&2',
    ):
        assert required in readme

    inventories_complete_index = readme.index(
        "NoSuchBucketPolicy results_policy_exists"
    )
    for presence_variable, terraform_resource in (
        (
            "packet_lifecycle_exists",
            "aws_s3_bucket_lifecycle_configuration.packet",
        ),
        (
            "results_lifecycle_exists",
            "aws_s3_bucket_lifecycle_configuration.results",
        ),
        ("packet_policy_exists", "aws_s3_bucket_policy.packet"),
        ("results_policy_exists", "aws_s3_bucket_policy.results"),
    ):
        assert f'if [[ "${presence_variable}" == true ]]' in readme
        assert inventories_complete_index < readme.index(terraform_resource)

    assert "code validation is not live acceptance" in readme
    for dated_observation in (
        "As observed on ",
        "GET returned 403",
        "GET returned 404",
        "does not yet exist",
        "has never run",
        "during this review",
    ):
        assert dated_observation not in combined
    assert "five environments" not in combined
